from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from tenet.core.memory import MemoryManager


def make_context_updater(memory: "MemoryManager") -> Callable:
    """
    Return a callable that the ToolExecutor will register as 'update_project_context'.
    """

    def update_project_context(
        file_summaries: dict[str, str] | None = None,
        symbols: dict[str, str] | None = None,
        facts: dict[str, str] | None = None,
    ) -> str:
        """
        Saves what it learned about this project into persistent memory.

        Args:
            file_summaries: {path: "one-line summary of what the file owns"}
            symbols:        {name: "file - what the symbol does, its role"}
            facts:          {key: "stable fact about state, conventions, patterns"}
        """
        updates = {}
        if file_summaries is not None:
            updates["file_summaries"] = file_summaries
        if symbols is not None:
            updates["symbols"] = symbols
        if facts is not None:
            updates["facts"] = facts
        return memory.update_project_context(**updates)

    return update_project_context
