from __future__ import annotations
from typing import Any


#  Tier 1: Persistent project context

class ProjectContext:
    """
    Structured summary of what the agent knows about the project.
    Pinned as messages[1] so it survives every context-window trim.
    """

    def __init__(self):
        self.file_summaries: dict[str, str] = {}
        self.symbols: dict[str, str] = {}
        self.facts: dict[str, str] = {}

    def merge(self, updates: dict) -> None:
        """
        Merge a partial update dict. All keys are optional.

        Expected shape:
        {
            "file_summaries": {"path": "what this file does"},
            "symbols":        {"name": "which file - what it does"},
            "facts":          {"key": "value"},
        }
        """
        self.file_summaries.update(updates.get("file_summaries") or {})
        self.symbols.update(updates.get("symbols") or {})
        self.facts.update(updates.get("facts") or {})

    def is_empty(self) -> bool:
        return not (self.file_summaries or self.symbols or self.facts)

    def to_prompt_block(self) -> str:
        if self.is_empty():
            return ""
        parts = ["<project_context>"]

        if self.file_summaries:
            parts.append("Files:")
            for path, summary in sorted(self.file_summaries.items()):
                parts.append(f"  {path}: {summary}")

        if self.symbols:
            parts.append("Known symbols (use search_files for exact location before editing):")
            for name, info in sorted(self.symbols.items()):
                parts.append(f"  {name}: {info}")

        if self.facts:
            parts.append("Facts:")
            for key, val in sorted(self.facts.items()):
                parts.append(f"  {key}: {val}")

        parts.append("</project_context>")
        return "\n".join(parts)


#  Tier 2: Conversation window with hard trim

class MemoryManager:
    def __init__(self, system_prompt: str, max_history_messages: int = 60):
        self.system_prompt = system_prompt
        self.max_history_messages = max_history_messages
        self.project = ProjectContext()
        self._context_injected = False
        self.messages: list[dict[str, Any]] = []
        self.clear()

    def clear(self) -> None:
        """Reset conversation. Project context survives."""
        self.messages = [{"role": "system", "content": self.system_prompt}]
        self._context_injected = False
        self._sync_context_slot()

    def get_messages(self) -> list[dict[str, Any]]:
        return self.messages

    def add_user_message(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})
        self._enforce_context_limit()

    def add_assistant_message(self, message_obj: Any) -> None:
        self.messages.append(message_obj)
        self._enforce_context_limit()

    def add_tool_observation(self, tool_call_id: str, tool_name: str, content: str) -> None:
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": content,
        })
        self._enforce_context_limit()

    def update_project_context(self, updates: dict) -> None:
        self.project.merge(updates)
        self._sync_context_slot()

    def window_size(self) -> int:
        """Number of messages in the sliding conversation window."""
        return len(self.messages) - self._conv_start()

    def _sync_context_slot(self) -> None:
        block = self.project.to_prompt_block()
        if block:
            msg = {"role": "system", "content": block}
            if self._context_injected:
                self.messages[1] = msg          # update in-place
            else:
                self.messages.insert(1, msg)    # insert after system prompt
                self._context_injected = True
        else:
            if self._context_injected:
                self.messages.pop(1)
                self._context_injected = False

    def _conv_start(self) -> int:
        """Index of the first conversation (non-pinned) message."""
        return 2 if self._context_injected else 1


    def _enforce_context_limit(self) -> None:
        """
        Drop oldest complete exchanges until window_size <= max_history_messages.
        """
        conv_start = self._conv_start()

        while len(self.messages) - conv_start > self.max_history_messages:
            # Find the boundary of the next user message after the first one
            next_user = None
            for i in range(conv_start + 1, len(self.messages)):
                msg = self.messages[i]
                role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", None)
                if role == "user":
                    next_user = i
                    break

            if next_user is None:
                # Only one exchange left - can't trim further without losing everything
                break

            # Drop everything from conv_start up to (not including) next_user
            del self.messages[conv_start:next_user]