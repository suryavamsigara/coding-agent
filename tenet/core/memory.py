from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
import json
import re

if TYPE_CHECKING:
    from tenet.core.agent_orchestrator import AssistantMessage, ToolCall


#  Tier 1: Project context (pinned, never trimmed)

class ProjectContext:
    """
    Structured summary of what the agent knows about the project.
    Pinned as messages[1] so it survives every context-window trim.
    """
    def __init__(self) -> None:
        self.file_summaries: dict[str, str] = {}
        self.symbols: dict[str, str] = {}
        self.facts: dict[str, str] = {}
        self.read_files: set[str] = set()   # files the agent has already read

    def merge(self, updates: dict) -> None:
        self.file_summaries.update(updates.get("file_summaries") or {})
        self.symbols.update(updates.get("symbols") or {})
        self.facts.update(updates.get("facts") or {})
        for path in updates.get("file_summaries") or {}:
            self.read_files.add(path)

    def mark_read(self, path: str) -> None:
        self.read_files.add(path)

    def is_empty(self) -> bool:
        return not (self.file_summaries or self.symbols or self.facts)

    def to_prompt_block(self) -> str:
        if self.is_empty():
            return ""
        parts = ["<project_context>"]
        if self.read_files:
            already = ", ".join(sorted(self.read_files))
            parts.append(f"Already read (DO NOT read_file these again): {already}")
        if self.file_summaries:
            parts.append("Files:")
            for path, summary in sorted(self.file_summaries.items()):
                parts.append(f"  {path}: {summary}")
        if self.symbols:
            parts.append("Symbols (use search_files for exact location before editing):")
            for name, info in sorted(self.symbols.items()):
                parts.append(f"  {name}: {info}")
        if self.facts:
            parts.append("Facts:")
            for key, val in sorted(self.facts.items()):
                parts.append(f"  {key}: {val}")
        parts.append("</project_context>")
        return "\n".join(parts)


#  Serialisation helpers

def _msg_role(msg: Any) -> str | None:
    if isinstance(msg, dict):
        return msg.get("role")
    return getattr(msg, "role", None)


def _serialise(msg: Any) -> dict:
    """
    Convert any message representation to a plain dict suitable for the API.

    Handles:
      - dicts (tool messages, user messages) - returned as-is
      - AssistantMessage dataclass instances - converted field by field
      - Raw OpenAI SDK objects — best-effort via getattr
    """
    if isinstance(msg, dict):
        return msg

    d: dict[str, Any] = {"role": getattr(msg, "role", "assistant")}

    content = getattr(msg, "content", None)
    if content is not None:
        d["content"] = content

    reasoning = getattr(msg, "reasoning_content", None)
    if reasoning is not None:
        d["reasoning_content"] = reasoning

    tool_calls = getattr(msg, "tool_calls", None)
    if tool_calls:
        serialised_tcs = []
        for tc in tool_calls:
            fn = tc.function if hasattr(tc, "function") else {}
            serialised_tcs.append({
                "id": tc.id if hasattr(tc, "id") else tc.get("id", ""),
                "type": "function",
                "function": {
                    "name": getattr(fn, "name", fn.get("name", "") if isinstance(fn, dict) else ""),
                    "arguments": getattr(fn, "arguments", fn.get("arguments", "") if isinstance(fn, dict) else ""),
                },
            })
        d["tool_calls"] = serialised_tcs

    return d


#  MemoryManager

class MemoryManager:
    def __init__(self, system_prompt: str, max_history_messages: int = 60) -> None:
        self.system_prompt = system_prompt
        self.max_history_messages = max_history_messages
        self.project = ProjectContext()
        self._context_injected = False
        self.messages: list[Any] = []

        self.debug_dir = Path("debug_history")
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self._snapshot_id = 0

        self.clear()

    def clear(self) -> None:
        """Reset conversation. Project context (knowledge) survives."""
        self.messages = [{"role": "system", "content": self.system_prompt}]
        self._context_injected = False
        self._sync_context_slot()
        self._dump_history_snapshot("clear")

    def get_messages(self) -> list[dict]:
        """Return serialised message list ready to POST to the API."""
        return [_serialise(m) for m in self.messages]

    def add_user_message(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})
        self._trim()
        self._dump_history_snapshot("add_user")

    def add_assistant_message(self, msg: Any) -> None:
        """Store AssistantMessage (or raw SDK object) - reasoning_content intact."""
        self.messages.append(msg)
        self._dump_history_snapshot("add_assistant")

    def add_tool_observation(self, tool_call_id: str, tool_name: str, content: str) -> None:
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": content,
        })
        self._dump_history_snapshot(f"tool_{self._safe_name(tool_name)}")

    def strip_reasoning_content(self) -> None:
        """
        Remove reasoning_content from all stored assistant messages.
        Must be called before every new user turn (DeepSeek multi-turn contract).
        """
        for msg in self.messages:
            if isinstance(msg, dict):
                msg.pop("reasoning_content", None)
            else:
                try:
                    msg.reasoning_content = None
                except AttributeError:
                    pass
        self._dump_history_snapshot("strip_reasoning")

    def update_project_context(self, **updates) -> str:
        self.project.merge(updates)
        self._sync_context_slot()
        self._dump_history_snapshot("project_context_update")
        return "Project context updated."

    def mark_file_read(self, path: str) -> None:
        self.project.mark_read(path)
        self._sync_context_slot()
        self._dump_history_snapshot(f"mark_read_{self._safe_name(Path(path).name)}")

    def window_size(self) -> int:
        return len(self.messages) - self._conv_start()

    # Pinned context slot

    def _sync_context_slot(self) -> None:
        block = self.project.to_prompt_block()
        if block:
            msg = {"role": "system", "content": block}
            if self._context_injected:
                self.messages[1] = msg
            else:
                self.messages.insert(1, msg)
                self._context_injected = True
        else:
            if self._context_injected:
                self.messages.pop(1)
                self._context_injected = False

    def _conv_start(self) -> int:
        """Index of the first conversation message (after pinned slots)."""
        return 2 if self._context_injected else 1

    # Debug snapshots

    def _safe_name(self, text: str) -> str:
        text = text.strip().lower()
        text = re.sub(r"[^a-z0-9._-]+", "_", text)
        return text[:80] or "snapshot"

    def _dump_history_snapshot(self, reason: str) -> None:
        self._snapshot_id += 1
        payload = {
            "snapshot_id": self._snapshot_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "window_size": self.window_size(),
            "messages": self.get_messages(),
        }

        safe_reason = self._safe_name(reason)
        path = self.debug_dir / f"{self._snapshot_id:04d}_{safe_reason}.json"
        latest = self.debug_dir / "latest.json"

        text = json.dumps(payload, indent=2, ensure_ascii=False)
        path.write_text(text, encoding="utf-8")
        latest.write_text(text, encoding="utf-8")

    # Hard trim

    def _trim(self) -> None:
        """
        Drop the oldest COMPLETE exchange whenever the window exceeds the limit.

        A complete exchange starts at a user message and ends just before the
        next user message.  We only trim full exchanges so we never strand
        orphaned tool_result messages without their paired tool_call.

        Called only from add_user_message() - a safe boundary where the
        previous exchange is guaranteed to be complete.
        """
        cs = self._conv_start()
        trimmed = False

        while len(self.messages) - cs > self.max_history_messages:
            # messages[cs] must be the oldest user message.
            # Find the NEXT user message to know where the first exchange ends.
            next_user: int | None = None
            for i in range(cs + 1, len(self.messages)):
                if _msg_role(self.messages[i]) == "user":
                    next_user = i
                    break

            if next_user is None:
                # Only one exchange remains - cannot trim safely.
                break

            del self.messages[cs:next_user]
            trimmed = True

        if trimmed:
            self._dump_history_snapshot("trim")