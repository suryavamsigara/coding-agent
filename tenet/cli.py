# main.py
import sys
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style

from tenet.llm.client import client
from tenet.core.agent_orchestrator import CodingAgent

console = Console()

style = Style.from_dict({
    'prompt': 'ansicyan bold',
})

def print_welcome_banner():
    """Draws a nice welcome panel when the CLI starts."""
    banner_text = Text("Tenet Initialized\n", style="bold green")
    banner_text.append("Type your request below. Use ", style="white")
    banner_text.append("Up-Arrow", style="bold yellow")
    banner_text.append(" for history. Type ", style="white")
    banner_text.append("'exit'", style="bold red")
    banner_text.append(" to quit.", style="white")
    
    console.print(Panel(banner_text, title="[bold cyan]TENET[/bold cyan]", border_style="cyan"))

def main():
    print_welcome_banner()
    
    # Initialize the agent
    agent = CodingAgent(client=client)

    session = PromptSession(history=InMemoryHistory())

    while True:
        try:
            user_input = session.prompt('\nYou: ', style=style).strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ['exit', 'quit']:
                console.print("\n[bold red]Shutting down Tenet. Goodbye![/bold red]")
                break
                
            with console.status("[bold yellow]Thinking and executing tools...[/bold yellow]", spinner="dots"):
                final_answer = agent.run_agent_loop(user_prompt=user_input)
            
            console.print("\n")
            console.print(Panel(Markdown(final_answer), title="[bold green]Tenet[/bold green]", border_style="green"))
            
        except KeyboardInterrupt:
            console.print("\n[bold red]Process interrupted by user. Shutting down...[/bold red]")
            sys.exit(0)
        except Exception as e:
            console.print(f"\n[bold red]An unexpected error occurred:[/bold red] {e}")

if __name__ == "__main__":
    main()