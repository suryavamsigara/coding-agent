from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from tenet.config import get_working_directory


def get_log_directory() -> Path:
    """Resolve the session log directory from env or default location."""
    env = os.environ.get("TENET_LOG_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return get_working_directory() / ".tenet" / "logs" / "sessions"


class SessionLogger:
    """
    Per-session structured logger.

    All public methods are safe to call even if the log directory cannot
    be created (errors are swallowed so logging never crashes the agent).
    """

    def __init__(self, log_dir: Path | None = None) -> None:
        self._start = time.monotonic()
        self._session_id = (
            datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:6]
        )
        self._tool_calls = 0
        self._iterations = 0

        log_dir = log_dir or get_log_directory()

        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            self._jsonl = (log_dir / f"{self._session_id}.jsonl").open(
                "a", encoding="utf-8"
            )
            self._text = (log_dir / f"{self._session_id}.log").open(
                "a", encoding="utf-8"
            )
            self._ok = True
        except Exception as exc:
            logging.getLogger("tenet.logger").warning(
                "SessionLogger: cannot open log files: %s", exc
            )
            self._ok = False

    @property
    def session_id(self) -> str:
        return self._session_id

    # Public API

    def log_session_start(self, prompt: str, model: str, thinking: bool) -> None:
        self._emit("SESSION_START", {
            "prompt": prompt,
            "model": model,
            "thinking": thinking,
        })
        self._text_line(
            f"[SESSION] id={self._session_id}  model={model}  thinking={thinking}"
        )
        self._text_line(f"[PROMPT]  {prompt[:300]}")

    def log_llm_turn(
        self, iteration: int, window_size: int, tool_call_count: int
    ) -> None:
        self._iterations = max(self._iterations, iteration)
        self._emit("LLM_TURN", {
            "iteration": iteration,
            "window_size": window_size,
            "tool_calls": tool_call_count,
        })
        self._text_line(
            f"[LLM]     iter={iteration}  window={window_size}  tool_calls={tool_call_count}"
        )

    def log_tool_call(
        self,
        name: str,
        args: dict,
        result: Any,
        duration_ms: int,
        success: bool,
    ) -> None:
        self._tool_calls += 1
        # Summarise result for log (don't bloat with full content)
        result_summary = _summarise_result(name, result)
        self._emit("TOOL", {
            "name": name,
            "args": _safe_args(args),
            "result_summary": result_summary,
            "duration_ms": duration_ms,
            "success": success,
        })
        status = "✓" if success else "✗"
        self._text_line(
            f"[TOOL]    {status} {name:<26} {result_summary[:80]}  ({duration_ms}ms)"
        )

    def log_phase(self, phase: str, description: str) -> None:
        self._emit("PHASE", {"phase": phase, "description": description})
        self._text_line(f"[PHASE]   {phase}  {description}")

    def log_plan(
        self,
        goal: str,
        steps: list[str],
        files_to_modify: list[str],
        decision: str,
    ) -> None:
        self._emit("PLAN", {
            "goal": goal,
            "steps": steps,
            "files_to_modify": files_to_modify,
            "decision": decision,
        })
        self._text_line(f"[PLAN]    goal={goal!r}  decision={decision!r}")

    def log_confirmation(self, action: str, decision: str) -> None:
        self._emit("CONFIRM", {"action": action, "decision": decision})
        self._text_line(f"[CONFIRM] action={action!r}  decision={decision!r}")

    def log_user_message(self, content: str) -> None:
        self._emit("USER_MESSAGE", {"content": content[:500]})

    def log_session_end(self) -> None:
        elapsed = round(time.monotonic() - self._start, 1)
        self._emit("SESSION_END", {
            "total_iterations": self._iterations,
            "total_tool_calls": self._tool_calls,
            "elapsed_seconds": elapsed,
        })
        self._text_line(
            f"[SESSION] END  iterations={self._iterations}  "
            f"tools={self._tool_calls}  elapsed={elapsed}s"
        )
        self._text_line("─" * 72)
        self._flush()

    def log_error(self, message: str, exc: Exception | None = None) -> None:
        self._emit("ERROR", {"message": message, "exc": str(exc) if exc else None})
        self._text_line(f"[ERROR]   {message}" + (f"  {exc}" if exc else ""))

    # ── Internal ──────────────────────────────────────────────────────────────

    def _emit(self, event: str, data: dict) -> None:
        if not self._ok:
            return
        record = {
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "elapsed_s": round(time.monotonic() - self._start, 3),
            "event": event,
            **data,
        }
        try:
            self._jsonl.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _text_line(self, line: str) -> None:
        if not self._ok:
            return
        try:
            ts = datetime.now().strftime("%H:%M:%S")
            self._text.write(f"{ts}  {line}\n")
        except Exception:
            pass

    def _flush(self) -> None:
        if not self._ok:
            return
        try:
            self._jsonl.flush()
            self._text.flush()
        except Exception:
            pass

    def __del__(self) -> None:
        if self._ok:
            try:
                self._jsonl.close()
                self._text.close()
            except Exception:
                pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _summarise_result(tool_name: str, result: Any) -> str:
    """One-line summary of a tool result for the log."""
    if isinstance(result, str) and result.startswith("Error"):
        return result[:120]
    match tool_name:
        case "search_files":
            if isinstance(result, dict):
                n = result.get("total_matches", 0)
                f = result.get("files_searched", 0)
                return f"{n} matches in {f} files"
        case "read_file":
            return f"{len(result):,} chars" if isinstance(result, str) else str(result)[:80]
        case "read_file_range":
            lines = result.count("\n") + 1 if isinstance(result, str) else 0
            return f"{lines} lines"
        case "replace_in_file" | "apply_patch" | "patch_file_lines":
            if isinstance(result, dict):
                return "changed=True" if result.get("changed") else str(result)
        case "write_file" | "create_file":
            return str(result)[:80]
        case "run_command":
            if isinstance(result, dict):
                return f"exit={result.get('exit_code')} success={result.get('success')}"
        case "update_project_context":
            return "ok"
        case "begin_phase" | "submit_plan" | "request_confirmation":
            return str(result)[:60]
    if isinstance(result, dict):
        return str(list(result.keys()))[:80]
    return str(result)[:80]


def _safe_args(args: dict) -> dict:
    """Truncate large arg values so they don't bloat the JSONL log."""
    out = {}
    for k, v in args.items():
        if isinstance(v, str) and len(v) > 200:
            out[k] = v[:200] + f"…[{len(v)} chars]"
        else:
            out[k] = v
    return out