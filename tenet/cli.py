import sys
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import box

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

from tenet.llm.client import client
from tenet.core.agent_orchestrator import CodingAgent
from tenet.tools.executor import execute_tool

console = Console()

PROMPT_STYLE = Style.from_dict({"prompt": "ansicyan bold"})

HISTORY_FILE = ".tenet_history"

HELP_TEXT = """
**Tenet Commands**

| Command   | Description                         |
|-----------|-------------------------------------|
| /reset    | Clear conversation history          |
| /tree     | Show project directory tree         |
| /ls       | List all project files              |
| /tools    | List available tools                |
| /help     | Show this help                      |
| exit      | Exit Tenet                          |

**Tips:**
- Use ↑/↓ arrow keys to navigate history
- Tenet automatically searches, reads, edits and runs code
- For multi-line input, paste freely — just hit Enter when done
"""


def print_welcome_banner() -> None:
    banner = Text()
    banner.append("TENET\n", style="bold cyan")
    banner.append("AI coding agent  •  ", style="dim white")
    banner.append("Type ", style="white")
    banner.append("/help", style="bold yellow")
    banner.append(" for commands  •  ", style="white")
    banner.append("exit", style="bold red")
    banner.append(" to quit", style="white")
    console.print(Panel(banner, border_style="cyan", padding=(0, 2)))


def handle_slash_command(cmd: str, agent: CodingAgent) -> bool:
    """
    Handle /commands. Returns True if the input was a slash command, False otherwise.
    """
    cmd = cmd.strip().lower()

    if cmd == "/reset":
        agent.reset_conversation()
        console.print("[bold green]✓[/bold green] Conversation history cleared.")
        return True

    if cmd == "/tree":
        result = execute_tool("directory_tree", dir_path=".", max_depth=4)
        console.print(Panel(result, title="[dim]Project Tree[/dim]", border_style="dim"))
        return True

    if cmd == "/ls":
        result = execute_tool("list_files")
        if isinstance(result, dict) and "files" in result:
            files = "\n".join(result["files"])
            console.print(Panel(files, title=f"[dim]{result['count']} files[/dim]", border_style="dim"))
        else:
            console.print(result)
        return True

    if cmd == "/tools":
        from tenet.tools.executor import TOOL_REGISTRY
        table = Table(title="Available Tools", box=box.SIMPLE, border_style="cyan")
        table.add_column("Tool", style="bold cyan", no_wrap=True)
        table.add_column("Category", style="dim")
        categories = {
            "get_file_info": "metadata",
            "read_file": "read", "read_file_range": "read",
            "write_file": "write", "create_file": "write",
            "replace_in_file": "edit", "apply_patch": "edit", "get_diff": "edit",
            "create_directory": "directory", "list_files": "directory", "directory_tree": "directory",
            "copy_file": "files", "rename_path": "files", "delete_path": "files",
            "search_files": "search", "find_symbol": "search",
            "run_command": "shell",
        }
        for name in sorted(TOOL_REGISTRY.keys()):
            table.add_row(name, categories.get(name, ""))
        console.print(table)
        return True

    if cmd in ("/help", "/?"):
        console.print(Markdown(HELP_TEXT))
        return True

    return False  # not a slash command


def main() -> None:
    print_welcome_banner()

    agent = CodingAgent(client=client, max_history_messages=60)

    session = PromptSession(
        history=FileHistory(HISTORY_FILE),
        auto_suggest=AutoSuggestFromHistory(),
    )

    while True:
        try:
            user_input = session.prompt("\nYou: ", style=PROMPT_STYLE).strip()
        except KeyboardInterrupt:
            console.print("\n[bold red]Interrupted. Type 'exit' to quit.[/bold red]")
            continue
        except EOFError:
            console.print("\n[bold red]Goodbye![/bold red]")
            sys.exit(0)

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            console.print("\n[bold red]Shutting down Tenet. Goodbye![/bold red]")
            break

        # Handle /commands
        if user_input.startswith("/"):
            handle_slash_command(user_input, agent)
            continue

        # Normal agent invocation
        console.print()  # breathing room
        try:
            # Tool call output is printed live inside run_agent_loop
            final_answer = agent.run_agent_loop(
                user_prompt=user_input,
                max_iterations=60,
            )

            console.print()
            if final_answer:
                console.print(
                    Panel(
                        Markdown(final_answer),
                        title="[bold green]Tenet[/bold green]",
                        border_style="green",
                        padding=(1, 2),
                    )
                )
            else:
                console.print("[dim](no response)[/dim]")

        except KeyboardInterrupt:
            console.print("\n[bold yellow]⚠  Task interrupted.[/bold yellow]")
        except Exception as e:
            console.print(f"\n[bold red]Error:[/bold red] {e}")
            logger_main = __import__("logging").getLogger(__name__)
            logger_main.exception("Unhandled error in main loop")


if __name__ == "__main__":
    main()