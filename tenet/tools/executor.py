from __future__ import annotations

from typing import Callable

from tenet.tools.file_ops import *
from tenet.tools.shell_ops import run_command

_BASE_REGISTRY: dict[str, callable] = {
    "get_file_info":    get_file_info,
    "read_file":        read_file,
    "read_file_range":  read_file_range,
    "write_file":       write_file,
    "create_file":      create_file,
    "replace_in_file":  replace_in_file,
    "patch_file_lines": patch_file_lines,
    "apply_patch":      apply_patch,
    "get_diff":         get_diff,
    "create_directory": create_directory,
    "list_files":       list_files,
    "directory_tree":   directory_tree,
    "copy_file":        copy_file,
    "rename_path":      rename_path,
    "delete_path":      delete_path,
    "search_files":     search_files,
    "find_symbol":      find_symbol,
    "run_command":      run_command,
}

class ToolExecutor:
    """
    Dispatches tool calls. One instance per CodingAgent.

    The `context_updater` callable is bound to that agent's MemoryManager,
    so there is no shared global state even when multiple agents coexist.
    """

    def __init__(self, context_updater: Callable) -> None:
        self._registry: dict[str, Callable] = {
            **_BASE_REGISTRY,
            "update_project_context": context_updater,
        }

    @property
    def tool_names(self) -> list[str]:
        return sorted(self._registry.keys())

    def execute(self, tool_name: str, **args):
        if tool_name not in self._registry:
            available = ", ".join(self.tool_names)
            return f"Error: tool '{tool_name}' does not exist. Available: {available}"
        try:
            return self._registry[tool_name](**args)
        except TypeError as exc:
            return f"Error: wrong arguments for '{tool_name}': {exc}"
        except Exception as exc:
            return f"Error executing '{tool_name}': {exc}"