from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Generator

from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()

# ── Phase config ──────────────────────────────────────────────────────────────

_PHASE_META: dict[str, tuple[str, str]] = {
    "EXPLORING": ("🔍", "cyan"),
    "PLANNING":  ("📋", "yellow"),
    "EXECUTING": ("⚡", "blue"),
    "VERIFYING": ("✅", "green"),
    "DONE":      ("🎯", "bold green"),
}

# ── Tool display icons ────────────────────────────────────────────────────────

_TOOL_ICONS: dict[str, str] = {
    "search_files":           "🔎",
    "find_symbol":            "🔎",
    "read_file":              "📖",
    "read_file_range":        "📖",
    "get_file_info":          "ℹ️ ",
    "write_file":             "✏️ ",
    "create_file":            "✏️ ",
    "replace_in_file":        "✏️ ",
    "patch_file_lines":       "✏️ ",
    "apply_patch":            "✏️ ",
    "get_diff":               "📊",
    "directory_tree":         "🗂 ",
    "list_files":             "🗂 ",
    "create_directory":       "📁",
    "copy_file":              "📋",
    "rename_path":            "📋",
    "delete_path":            "🗑 ",
    "run_command":            "💻",
    "update_project_context": "🧠",
    "begin_phase":            "→ ",
    "submit_plan":            "📋",
    "request_confirmation":   "⚠️ ",
}

_DESTRUCTIVE_TOOLS = {"delete_path"}
_DESTRUCTIVE_CMD_PATTERNS = (
    "rm ", "drop ", "truncate ", "format ", "mkfs",
    "del ", "> /dev/", "shutdown", "reboot",
)


class AgentDisplay:
    """Central display controller. One instance per CodingAgent."""

    def __init__(self, con: Console | None = None) -> None:
        self.con = con or console
        self._current_phase: str | None = None

    # ── Phase ─────────────────────────────────────────────────────────────────

    def show_phase(self, phase: str, description: str = "") -> None:
        icon, colour = _PHASE_META.get(phase.upper(), ("▶", "white"))
        label = Text()
        label.append(f"{icon}  {phase.upper()}", style=f"bold {colour}")
        if description:
            label.append(f"  —  {description}", style="dim white")
        self.con.print()
        self.con.print(Rule(label, style=colour, align="left"))
        self._current_phase = phase.upper()

    # ── Tool call / result ────────────────────────────────────────────────────

    def show_tool_call(self, name: str, args: dict) -> None:
        icon = _TOOL_ICONS.get(name, "🔧")
        preview = _args_preview(name, args)
        self.con.print(f"\n  {icon}  [bold cyan]{name}[/bold cyan]  [dim]{preview}[/dim]")

    def show_tool_result(self, name: str, args: dict, result: Any) -> None:
        """Show a concise, tool-aware result summary (never raw JSON dumps)."""
        is_error = isinstance(result, str) and result.lower().startswith("error")
        summary = _result_summary(name, args, result)

        if is_error:
            self.con.print(f"     [red]✗  {summary}[/red]")
            return

        # Commands get their stdout/stderr shown
        if name == "run_command" and isinstance(result, dict):
            _show_command_result(self.con, result)
            return

        # search_files shows match locations (not full context)
        if name == "search_files" and isinstance(result, dict):
            _show_search_result(self.con, result)
            return

        self.con.print(f"     [dim]{summary}[/dim]")

    # ── Streaming live view ───────────────────────────────────────────────────

    @contextmanager
    def streaming_panel(self) -> Generator[list[str], None, None]:
        """
        Context manager for live-streaming LLM text.

        Behaviour:
          • Before the first token: a spinner ("Thinking…") animates so the
            terminal never looks frozen.
          • After the first token: the spinner is replaced by a live Markdown
            view that updates as chunks arrive.

        Usage:
            with display.streaming_panel() as buf:
                for chunk in stream:
                    buf.append(chunk)
        """
        buf: list[str] = []
        spinner = Spinner("dots", text=" [dim]Thinking…[/dim]")

        def _render() -> Any:
            if not buf:
                return spinner
            text = "".join(buf)
            return Markdown(text) if text.strip() else Text("")

        with Live(
            _render(),
            console=self.con,
            refresh_per_second=15,
            vertical_overflow="visible",
        ) as live:

            class _Proxy(list):  # type: ignore[type-arg]
                def append(self_, item: str) -> None:  # type: ignore[override]
                    super().append(item)
                    live.update(_render())

            proxy = _Proxy()
            yield proxy

    # ── Narration persistence ─────────────────────────────────────────────────

    def show_narration(self, text: str) -> None:
        """
        Print intermediate LLM commentary that accompanied tool calls so it is
        never silently discarded.

        Called by the orchestrator when a turn had both content AND tool_calls.
        This keeps the agent's "Now I'll update the init section:" context
        visible between tool-call blocks.
        """
        stripped = text.strip()
        if not stripped:
            return
        self.con.print()
        self.con.print(
            Panel(
                Markdown(stripped),
                border_style="dim cyan",
                padding=(0, 1),
            )
        )

    # ── Plan approval ─────────────────────────────────────────────────────────

    def prompt_plan_approval(
        self,
        goal: str,
        steps: list[str],
        files_to_modify: list[str] | None,
        estimated_changes: str = "",
    ) -> str:
        """
        Show the proposed plan and prompt the user.

        Returns one of:
          "APPROVED"
          "REJECTED: <reason>"
          "MODIFIED: <instructions>"
        """
        self.con.print()
        content = Text()
        content.append("Goal\n", style="bold yellow")
        content.append(f"  {goal}\n\n", style="white")

        content.append("Steps\n", style="bold yellow")
        for i, step in enumerate(steps, 1):
            content.append(f"  {i}. {step}\n", style="white")

        if files_to_modify:
            content.append("\nFiles to modify\n", style="bold yellow")
            for f in files_to_modify:
                content.append(f"  • {f}\n", style="dim cyan")

        if estimated_changes:
            content.append(f"\n{estimated_changes}\n", style="dim white")

        self.con.print(Panel(
            content,
            title="[bold yellow]📋  PLAN[/bold yellow]",
            border_style="yellow",
            padding=(1, 2),
        ))

        self.con.print(
            "  [dim]Options:[/dim]  "
            "[bold green]y[/bold green] approve  "
            "[bold red]n[/bold red] reject  "
            "[bold cyan]e[/bold cyan] edit/instructions"
        )

        while True:
            choice = Prompt.ask(
                "\n  [bold yellow]▶[/bold yellow]",
                console=self.con,
                default="y",
            ).strip().lower()

            if choice in ("y", "yes", ""):
                self.con.print("  [green]✓ Plan approved — proceeding.[/green]")
                return "APPROVED"

            if choice in ("n", "no"):
                reason = Prompt.ask("  Reason (optional)", console=self.con, default="")
                self.con.print("  [red]✗ Plan rejected.[/red]")
                return f"REJECTED: {reason}" if reason else "REJECTED"

            if choice in ("e", "edit"):
                instructions = Prompt.ask(
                    "  Instructions for the agent",
                    console=self.con,
                    default="",
                )
                self.con.print("  [cyan]↩ Plan sent back with modifications.[/cyan]")
                return f"MODIFIED: {instructions}"

            self.con.print("  [dim]Please enter y, n, or e.[/dim]")

    # ── Confirmation for destructive ops ──────────────────────────────────────

    def prompt_confirmation(self, action: str, details: str, risk: str = "medium") -> str:
        """
        Show a confirmation prompt before an irreversible action.

        Returns "APPROVED" or "CANCELLED".
        """
        self.con.print()
        colour = "red" if risk == "high" else "yellow"
        icon = "🔴" if risk == "high" else "⚠️ "
        content = Text()
        content.append(f"{details}\n", style=f"bold {colour}")
        content.append(f"This action is {risk}-risk and may be irreversible.", style="dim")
        self.con.print(Panel(
            content,
            title=f"[bold {colour}]{icon}  CONFIRM: {action}[/bold {colour}]",
            border_style=colour,
            padding=(1, 2),
        ))

        confirmed = Confirm.ask(
            f"  [bold {colour}]Proceed?[/bold {colour}]",
            console=self.con,
            default=False,
        )
        if confirmed:
            self.con.print(f"  [{colour}]✓ Confirmed.[/{colour}]")
            return "APPROVED"
        self.con.print("  [dim]Cancelled.[/dim]")
        return "CANCELLED"

    # ── Final answer ──────────────────────────────────────────────────────────

    def show_final_answer(self, text: str, model: str, thinking: bool) -> None:
        if not text:
            self.con.print("[dim](no response)[/dim]")
            return
        self.con.print()
        tag = "  thinking" if thinking else ""
        self.con.print(Panel(
            Markdown(text),
            title=f"[bold green]Tenet[/bold green]  [dim]{model}{tag}[/dim]",
            border_style="green",
            padding=(1, 2),
        ))

    # ── Misc ──────────────────────────────────────────────────────────────────

    def show_error(self, message: str) -> None:
        self.con.print(f"\n[bold red]Error:[/bold red] {message}")

    def show_interrupted(self) -> None:
        self.con.print("\n[bold yellow]⚠  Task interrupted.[/bold yellow]")

    def show_iteration_warning(self, max_iter: int) -> None:
        self.con.print(
            f"\n[yellow]⚠  Reached {max_iter}-iteration limit.[/yellow]"
        )


# ── Formatting helpers ────────────────────────────────────────────────────────

def _args_preview(tool_name: str, args: dict) -> str:
    """Compact, tool-aware argument preview for the terminal."""
    match tool_name:
        case "search_files":
            glob = args.get("file_glob", "**/*")
            ctx = f"  ctx={args['context_lines']}" if "context_lines" in args else ""
            return f'"{args.get("pattern", "")}"  [{glob}]{ctx}'
        case "find_symbol":
            return f'"{args.get("symbol", "")}"  [{args.get("file_glob", "**/*")}]'
        case "read_file":
            return args.get("file_path", "")
        case "read_file_range":
            return f'{args.get("file_path", "")}:{args.get("start_line")}–{args.get("end_line")}'
        case "replace_in_file":
            old_len = len(args.get("search_text", ""))
            new_len = len(args.get("replace_text", ""))
            return f'{args.get("file_path", "")}  [{old_len}→{new_len} chars]'
        case "write_file":
            size = len(args.get("content", ""))
            return f'{args.get("file_path", "")}  ({size:,} bytes)'
        case "apply_patch":
            return args.get("file_path", "")
        case "patch_file_lines":
            return f'{args.get("file_path", "")}:{args.get("start_line")}–{args.get("end_line")}'
        case "run_command":
            return f'$ {args.get("command", "")}'
        case "directory_tree":
            return f'{args.get("dir_path", ".")}  depth={args.get("max_depth", 4)}'
        case "begin_phase":
            return f'{args.get("phase", "")}  —  {args.get("description", "")}'
        case "submit_plan":
            return args.get("goal", "")[:80]
        case "request_confirmation":
            return args.get("action", "")
        case _:
            raw = json.dumps(args, ensure_ascii=False)
            return raw[:160] + "…" if len(raw) > 160 else raw


def _result_summary(tool_name: str, args: dict, result: Any) -> str:
    """One-line human summary of a tool result."""
    if isinstance(result, str) and result.lower().startswith("error"):
        return result[:200]
    match tool_name:
        case "search_files":
            if isinstance(result, dict):
                n = result.get("total_matches", 0)
                f = result.get("files_searched", 0)
                trunc = "  (truncated)" if result.get("truncated") else ""
                return f"Found {n} match{'es' if n != 1 else ''} in {f} file{'s' if f != 1 else ''}{trunc}"
        case "find_symbol":
            if isinstance(result, dict):
                n = result.get("total_matches", 0)
                return f"Found {n} reference{'s' if n != 1 else ''}"
        case "read_file":
            chars = len(result) if isinstance(result, str) else 0
            return f"Read {chars:,} chars  ←  {args.get('file_path', '')}"
        case "read_file_range":
            lines = result.count("\n") + 1 if isinstance(result, str) else 0
            return f"Read {lines} lines  ←  {args.get('file_path', '')}"
        case "replace_in_file":
            if isinstance(result, dict) and result.get("changed"):
                return f"✓ Applied  →  {args.get('file_path', '')}"
        case "patch_file_lines":
            if isinstance(result, dict) and result.get("changed"):
                return f"✓ {result.get('message', 'Applied')}"
        case "apply_patch":
            if isinstance(result, str) and "applied" in result.lower():
                return f"✓ {result}"
        case "write_file" | "create_file":
            return str(result)
        case "delete_path":
            return str(result)
        case "directory_tree":
            lines = result.count("\n") if isinstance(result, str) else 0
            return f"{lines} entries"
        case "list_files":
            if isinstance(result, dict):
                return f"{result.get('count', 0)} files"
        case "update_project_context":
            return "✓ Context saved"
        case "run_command":
            return ""  # handled separately
        case "begin_phase" | "submit_plan" | "request_confirmation":
            return ""
    return str(result)[:120]


def _show_command_result(con: Console, result: dict) -> None:
    success = result.get("success", False)
    exit_code = result.get("exit_code", -1)
    stdout = result.get("stdout", "").strip()
    stderr = result.get("stderr", "").strip()

    status_colour = "green" if success else "red"
    status_icon = "✓" if success else "✗"
    con.print(f"     [{status_colour}]{status_icon}  exit {exit_code}[/{status_colour}]")

    if stdout:
        for line in stdout.splitlines()[:30]:
            con.print(f"     [dim]{line}[/dim]")
        if stdout.count("\n") >= 30:
            con.print("     [dim]… (truncated)[/dim]")
    if stderr:
        for line in stderr.splitlines()[:10]:
            con.print(f"     [yellow]{line}[/yellow]")


def _show_search_result(con: Console, result: dict) -> None:
    matches = result.get("matches", [])
    total = result.get("total_matches", 0)
    files_searched = result.get("files_searched", 0)
    trunc = result.get("truncated", False)

    if not matches:
        con.print(f"     [dim]No matches in {files_searched} files[/dim]")
        return

    con.print(
        f"     [dim]Found {total} match{'es' if total != 1 else ''}"
        f" in {files_searched} file{'s' if files_searched != 1 else ''}"
        f"{'  (truncated)' if trunc else ''}[/dim]"
    )
    # Show first few match locations (file:line only, not full context)
    shown = set()
    for m in matches[:8]:
        loc = f"  {m['file']}:{m['line']}"
        if loc not in shown:
            con.print(f"     [dim cyan]{loc}[/dim cyan]")
            shown.add(loc)
    if total > 8:
        con.print(f"     [dim]  … and {total - 8} more[/dim]")