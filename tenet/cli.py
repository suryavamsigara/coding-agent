from __future__ import annotations

import sys
import logging

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

from tenet.llm.client import client
from tenet.core.agent_orchestrator import CodingAgent, MODEL_FLASH, MODEL_PRO

console = Console()

PROMPT_STYLE = Style.from_dict({"prompt": "ansicyan bold"})
HISTORY_FILE = ".tenet_history"

MODEL_ALIASES: dict[str, tuple[str, bool]] = {
    "flash":   (MODEL_FLASH, False),
    "flash-t": (MODEL_FLASH, True),
    "pro":     (MODEL_PRO,   False),
    "pro-t":   (MODEL_PRO,   True),
}

HELP_TEXT = """
**Tenet Commands**

| Command         | Description                                          |
|-----------------|------------------------------------------------------|
| /reset          | Clear conversation history (project context survives)|
| /model          | Show current model                                   |
| /model flash    | deepseek-v4-flash  (fast, default)                   |
| /model flash-t  | deepseek-v4-flash + thinking mode                    |
| /model pro      | deepseek-v4-pro  (more capable)                      |
| /model pro-t    | deepseek-v4-pro + thinking mode                      |
| /context        | Show current project context                         |
| /tree           | Show project directory tree                          |
| /ls             | List all project files                               |
| /tools          | List available tools                                 |
| /help           | Show this help                                       |
| exit / quit     | Quit Tenet                                           |
"""


def _model_label(model: str, thinking: bool) -> str:
    tag = " [dim][thinking][/dim]" if thinking else ""
    return f"[bold cyan]{model}[/bold cyan]{tag}"


def print_welcome_banner(agent: CodingAgent) -> None:
    t = Text()
    t.append("TENET\n", style="bold cyan")
    t.append(f"model: {agent.model}", style="dim white")
    if agent.thinking:
        t.append("  [thinking]", style="dim yellow")
    t.append("  •  /model flash|pro[-t]  •  exit to quit", style="dim white")
    console.print(Panel(t, border_style="cyan", padding=(0, 2)))


def handle_slash_command(cmd: str, agent: CodingAgent) -> bool:
    parts = cmd.strip().split()
    base = parts[0].lower()

    if base == "/reset":
        agent.reset_conversation()
        return True

    if base == "/model":
        if len(parts) == 1:
            console.print(f"Current model: {_model_label(agent.model, agent.thinking)}")
        else:
            key = parts[1].lower()
            if key in MODEL_ALIASES:
                agent.model, agent.thinking = MODEL_ALIASES[key]
                console.print(f"[green]✓[/green] Switched to {_model_label(agent.model, agent.thinking)}")
            else:
                opts = ", ".join(MODEL_ALIASES)
                console.print(f"[red]Unknown model alias '{parts[1]}'. Options: {opts}[/red]")
        return True

    if base == "/context":
        block = agent.memory.project.to_prompt_block()
        if block:
            console.print(Panel(block, title="[dim]Project Context[/dim]", border_style="dim"))
        else:
            console.print("[dim]No project context recorded yet.[/dim]")
        return True

    if base == "/tree":
        result = agent.executor.execute("directory_tree", dir_path=".", max_depth=4)
        console.print(Panel(str(result), title="[dim]Project Tree[/dim]", border_style="dim"))
        return True

    if base == "/ls":
        result = agent.executor.execute("list_files")
        if isinstance(result, dict) and "files" in result:
            files = "\n".join(result["files"]) or "(no files found)"
            console.print(Panel(files, title=f"[dim]{result['count']} files[/dim]", border_style="dim"))
        else:
            console.print(str(result))
        return True

    if base == "/tools":
        table = Table(title="Available Tools", box=box.SIMPLE, border_style="cyan")
        table.add_column("Tool", style="bold cyan", no_wrap=True)
        table.add_column("Category", style="dim")
        categories = {
            "get_file_info":          "metadata",
            "read_file":              "read",
            "read_file_range":        "read",
            "write_file":             "write",
            "create_file":            "write",
            "replace_in_file":        "edit",
            "patch_file_lines":       "edit",
            "apply_patch":            "edit",
            "get_diff":               "edit",
            "create_directory":       "directory",
            "list_files":             "directory",
            "directory_tree":         "directory",
            "copy_file":              "files",
            "rename_path":            "files",
            "delete_path":            "files",
            "search_files":           "search",
            "find_symbol":            "search",
            "run_command":            "shell",
            "update_project_context": "memory",
        }
        for name in agent.executor.tool_names:
            table.add_row(name, categories.get(name, ""))
        console.print(table)
        return True

    if base in ("/help", "/?"):
        console.print(Markdown(HELP_TEXT))
        return True

    # Unknown command - show a hint but don't abort
    console.print(f"[yellow]Unknown command '{base}'. Type /help for a list of commands.[/yellow]")
    return True


def main() -> None:
    agent = CodingAgent(client=client, model=MODEL_FLASH, thinking=False)
    print_welcome_banner(agent)

    session: PromptSession = PromptSession(
        history=FileHistory(HISTORY_FILE),
        auto_suggest=AutoSuggestFromHistory(),
    )

    while True:
        try:
            user_input = session.prompt("\nYou: ", style=PROMPT_STYLE).strip()
        except KeyboardInterrupt:
            console.print("\n[bold yellow]Interrupted. Type 'exit' to quit.[/bold yellow]")
            continue
        except EOFError:
            console.print("\n[bold red]Goodbye![/bold red]")
            sys.exit(0)

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            console.print("\n[bold red]Shutting down Tenet. Goodbye![/bold red]")
            break

        if user_input.startswith("/"):
            handle_slash_command(user_input, agent)
            continue

        console.print()
        try:
            answer = agent.run_agent_loop(user_prompt=user_input)
            console.print()
            if answer:
                label = f"[bold green]Tenet[/bold green]  [dim]{agent.model}"
                if agent.thinking:
                    label += "  thinking"
                label += "[/dim]"
                console.print(Panel(Markdown(answer), title=label, border_style="green", padding=(1, 2)))
            else:
                console.print("[dim](no response)[/dim]")
        except KeyboardInterrupt:
            console.print("\n[bold yellow]⚠  Task interrupted.[/bold yellow]")
        except Exception as exc:
            console.print(f"\n[bold red]Error:[/bold red] {exc}")
            logging.getLogger(__name__).exception("Unhandled error in agent loop")


if __name__ == "__main__":
    main()