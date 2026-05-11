from __future__ import annotations

import time
from typing import Any, Callable

from tenet.tools.file_ops import (
    apply_patch, copy_file, create_directory, create_file,
    delete_path, directory_tree, find_symbol, get_diff, get_file_info,
    list_files, patch_file_lines, read_file, read_file_range,
    rename_path, replace_in_file, search_files, write_file,
)
from tenet.tools.shell_ops import run_command

#Hard limits
_MAX_READ_FILE_LINES  = 100      # read_file refused above this line count
_MAX_READ_FILE_CHARS  = 3_000   # read_file refused above this char count
_MAX_RANGE_LINES      = 80     # read_file_range refused above this span

# Patterns in a shell command that require user confirmation before running
_DESTRUCTIVE_CMD_PATTERNS = (
    "rm ", "rm\t", "rmdir",
    "drop ", "truncate ", "format ",
    "mkfs", "> /dev/",
    "shutdown", "reboot", "halt", "poweroff",
    "DROP TABLE", "DELETE FROM",
)


def _is_error(result: Any) -> bool:
    return isinstance(result, str) and result.lower().startswith("error")


class ToolExecutor:
    """
    Per-agent tool executor. All I/O goes through injected display + logger.
    No module-level globals.
    """

    def __init__(
        self,
        context_updater: Callable,       # update_project_context bound to memory
        file_read_tracker: Callable,      # memory.mark_file_read — auto-tracks reads
        display,                          # AgentDisplay instance
        logger,                           # SessionLogger instance
        known_files: set[str] | None = None,  # live reference to memory.project.read_files
    ) -> None:
        self._display = display
        self._logger = logger
        self._file_read_tracker = file_read_tracker
        # Live reference — mutations in MemoryManager are visible here automatically
        self._known_files: set[str] = known_files if known_files is not None else set()

        # Base file/shell tools — guarded variants replace the raw ones
        self._registry: dict[str, Callable] = {
            "get_file_info":    get_file_info,
            "read_file":        self._guarded_read_file,
            "read_file_range":  self._guarded_read_file_range,
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
            "delete_path":      self._guarded_delete,
            "search_files":     search_files,
            "find_symbol":      find_symbol,
            "run_command":      self._guarded_run_command,
            "update_project_context": context_updater,
            # Phase / planning tools
            "begin_phase":          self._handle_begin_phase,
            "submit_plan":          self._handle_submit_plan,
            "request_confirmation": self._handle_request_confirmation,
        }

    @property
    def tool_names(self) -> list[str]:
        return sorted(self._registry.keys())

    # Public dispatch

    def execute(self, tool_name: str, **args: Any) -> Any:
        if tool_name not in self._registry:
            available = ", ".join(self.tool_names)
            return f"Error: tool '{tool_name}' does not exist. Available: {available}"

        self._display.show_tool_call(tool_name, args)

        start = time.monotonic()
        try:
            result = self._registry[tool_name](**args)
            success = not _is_error(result)
        except TypeError as exc:
            result = f"Error: wrong arguments for '{tool_name}': {exc}"
            success = False
        except Exception as exc:
            result = f"Error executing '{tool_name}': {exc}"
            success = False
        duration_ms = int((time.monotonic() - start) * 1000)

        # Auto-track file reads and writes - model never needs to remember this
        if success and tool_name in ("read_file", "write_file", "create_file"):
            path = args.get("file_path")
            if path:
                self._file_read_tracker(path)

        self._display.show_tool_result(tool_name, args, result)
        self._logger.log_tool_call(tool_name, args, result, duration_ms, success)

        return result

    # ── Read guards ───────────────────────────────────────────────────────────

    def _guarded_read_file(self, file_path: str) -> Any:
        """
        Block read_file if:
          - the file is already tracked in <project_context> (use search_files instead)
          - the file exceeds _MAX_READ_FILE_LINES / _MAX_READ_FILE_CHARS
        """
        if file_path in self._known_files:
            return (
                f"Error: '{file_path}' is already in <project_context> — do NOT read_file it again. "
                "Use search_files(pattern=..., context_lines=4) to locate the section, "
                "then read_file_range for just those lines."
            )

        # Read the file to measure it; reject if oversized
        raw = read_file(file_path=file_path)
        if isinstance(raw, str) and not raw.lower().startswith("error"):
            lines = raw.count("\n") + 1
            chars = len(raw)
            if lines > _MAX_READ_FILE_LINES or chars > _MAX_READ_FILE_CHARS:
                return (
                    f"Error: '{file_path}' is too large for read_file "
                    f"({lines} lines, {chars:,} chars — limits: {_MAX_READ_FILE_LINES} lines / "
                    f"{_MAX_READ_FILE_CHARS:,} chars). "
                    "Use search_files(pattern=..., context_lines=4) to find the exact section, "
                    f"then read_file_range with a span ≤ {_MAX_RANGE_LINES} lines."
                )
        return raw

    def _guarded_read_file_range(
        self, file_path: str, start_line: int, end_line: int
    ) -> Any:
        """
        Block read_file_range when the requested span exceeds _MAX_RANGE_LINES.
        Wide ranges are almost always a sign the model is trying to read the whole file.
        """
        span = end_line - start_line + 1
        if span > _MAX_RANGE_LINES:
            return (
                f"Error: range {start_line}–{end_line} is {span} lines "
                f"(limit: {_MAX_RANGE_LINES}). "
                "Narrow the range: use search_files(context_lines=4) to pin-point the "
                "exact lines you need, then request a focused slice."
            )
        return read_file_range(
            file_path=file_path, start_line=start_line, end_line=end_line
        )

    # Special tool handlers

    def _handle_begin_phase(self, phase: str, description: str = "") -> str:
        self._display.show_phase(phase, description)
        self._logger.log_phase(phase, description)
        return f"Phase set: {phase}"

    def _handle_submit_plan(
        self,
        goal: str,
        steps: list[str],
        files_to_modify: list[str] | None = None,
        estimated_changes: str = "",
    ) -> str:
        # If the model passes a plain string instead of a list
        if isinstance(steps, str):
            steps = [s.strip() for s in steps.split("\n") if s.strip()]

        # If steps is a list of single chars
        if steps and all(len(s) <= 2 for s in steps):
            steps = ["".join(steps)]

        decision = self._display.prompt_plan_approval(
            goal=goal,
            steps=steps,
            files_to_modify=files_to_modify or [],
            estimated_changes=estimated_changes,
        )
        self._logger.log_plan(goal, steps, files_to_modify or [], decision)
        return decision

    def _handle_request_confirmation(
        self, action: str, details: str, risk: str = "medium"
    ) -> str:
        decision = self._display.prompt_confirmation(action, details, risk)
        self._logger.log_confirmation(action, decision)
        return decision

    # Guarded tools

    def _guarded_delete(self, path: str) -> Any:
        """Always confirm before deleting."""
        decision = self._handle_request_confirmation(
            action="delete_path",
            details=f"Permanently delete: {path}",
            risk="high",
        )
        if decision != "APPROVED":
            return f"Cancelled: delete_path({path!r}) was not approved by user."
        return delete_path(path)

    def _guarded_run_command(
        self,
        command: str,
        working_dir: str = ".",
        timeout: int = 60,
        env_vars: dict | None = None,
    ) -> Any:
        """Intercept destructive shell commands and ask for confirmation."""
        cmd_lower = command.lower()
        is_destructive = any(p in cmd_lower for p in _DESTRUCTIVE_CMD_PATTERNS)
        if is_destructive:
            decision = self._handle_request_confirmation(
                action="run_command",
                details=f"$ {command}",
                risk="high",
            )
            if decision != "APPROVED":
                return {
                    "command": command,
                    "stdout": "",
                    "stderr": "Cancelled by user.",
                    "exit_code": -1,
                    "success": False,
                    "timed_out": False,
                }
        return run_command(command=command, working_dir=working_dir, timeout=timeout)