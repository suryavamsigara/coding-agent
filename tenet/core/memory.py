from __future__ import annotations

from typing import TYPE_CHECKING, Any
import re

if TYPE_CHECKING:
    from tenet.core.agent_orchestrator import AssistantMessage, ToolCall


#  Tier 1: Project context (pinned, never trimmed)

class ProjectContext:
    """
    Persistent knowledge about the project. Rendered as a pinned system message.
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
        self._summary_injected = False
        self.messages: list[Any] = []

        self.clear()

    # Public API

    def clear(self) -> None:
        """Reset conversation. Project context (knowledge) survives."""
        self.messages = [{"role": "system", "content": self.system_prompt}]
        self._context_injected = False
        self._summary_injected = False
        self._sync_context_slot()

    def inject_summary(self, summary_text: str) -> None:
        """
        Insert or update the pinned summary block that sits just before
        the recent conversation window. Called by the orchestrator after
        each compression run.
        """
        msg = {
            "role": "system",
            "content": (
                "PROGRESS SUMMARY (history compressed — treat this as ground truth):\n\n"
                + summary_text
            ),
        }
        idx = self._summary_slot()
        if self._summary_injected:
            self.messages[idx] = msg          # update in place
        else:
            self.messages.insert(idx, msg)    # insert after pinned slots
            self._summary_injected = True
    
    def trim_to_recent(self, keep_exchanges: int) -> None:
        """
        After compression, discard old exchanges keeping only the most
        recent `keep_exchanges` complete exchanges in the window.
        A complete exchange = one user message and everything until the next.
        """
        cs = self._conv_start()
        # Collect indices of user messages in the window
        user_indices = [
            i for i in range(cs, len(self.messages))
            if _msg_role(self.messages[i]) == "user"
        ]
        if len(user_indices) <= keep_exchanges:
            return  # already short enough
        # Cut everything before the Nth-from-last user message
        cut_from = user_indices[-keep_exchanges]
        del self.messages[cs:cut_from]

    def _summary_slot(self) -> int:
        """Index where the summary message lives (or should be inserted)."""
        # After system prompt + optional project context
        return 2 if self._context_injected else 1
            

    def get_messages(self) -> list[dict]:
        """Return serialised message list ready to POST to the API."""
        return [_serialise(m) for m in self.messages]

    def add_user_message(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})
        # Trim only happens here - at a safe exchange boundary
        self._trim()

    def add_assistant_message(self, msg: Any) -> None:
        """Store AssistantMessage (or raw SDK object) - reasoning_content intact."""
        self.messages.append(msg)

    def add_tool_observation(self, tool_call_id: str, tool_name: str, content: str) -> None:
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": content,
        })

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

    def update_project_context(self, **updates) -> str:
        self.project.merge(updates)
        self._sync_context_slot()
        return "Project context updated."

    def mark_file_read(self, path: str) -> None:
        self.project.mark_read(path)
        self._sync_context_slot()

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
        """Index of the first conversation message (after all pinned slots)."""
        base = 1
        if self._context_injected:
            base += 1
        if self._summary_injected:
            base += 1
        return base

    # Debug snapshots

    def _safe_name(self, text: str) -> str:
        text = text.strip().lower()
        text = re.sub(r"[^a-z0-9._-]+", "_", text)
        return text[:80] or "snapshot"

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
