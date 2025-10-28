import os
import sys, time
import json
import asyncio
import httpx
import questionary
from questionary import Style
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

BACKEND_URL = "http://127.0.0.1:8000/chat"
MCP_SERVER_URL = "http://127.0.0.1:9000/mcp"
MAX_ITERS = 8

async def safe_input(prompt: str) -> str:
    """Lets us use input() without freezing the async event loop"""
    return await asyncio.to_thread(input, prompt)

async def run_quirk(prompt: str):
    session_id = None
    tool_result_payload = None
    tools_list = None
    cwd = os.getcwd()

    try:
        async with streamablehttp_client(MCP_SERVER_URL) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_obj = await session.list_tools()
                tools_list = [tool.model_dump() for tool in tools_obj.tools]
        print(f"MCP connected: {len(tools_list)} tools found.")
    except Exception as e:
        print(f"Error connecting to MCP server at {MCP_SERVER_URL}: {e}")
        return

    current_prompt = prompt

    async with httpx.AsyncClient() as client:
        for _ in range(MAX_ITERS):
            payload = {
                "prompt": current_prompt,
                "cwd": cwd,
                "session_id": session_id,
                "tool_result": tool_result_payload,
                "tools_list": tools_list
            }

            print("\nSending to backend:", json.dumps(payload, indent=2, default=str))

            try:
                resp = await client.post(BACKEND_URL, json=payload, timeout=40)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                print(f"Error connecting to backend at {BACKEND_URL}: {e}")
                return

            current_prompt = None
            tools_list = None
            tool_result_payload = None
            session_id = data.get("session_id")

            if data.get("final_answer"):
                print(f"\nFinal Response:\n{data['final_answer']}")
                return

            elif data.get("tool_call"):
                call = data["tool_call"]
                tool_name = call["tool_name"]
                params = call.get("params", {})
                print(f"\nRequest: {tool_name}({params})")

                if tool_name in {"write_file", "delete_path"}:
                    confirm = (await safe_input("Apply this change? [y/N]: ")).strip().lower()
                    if confirm != "y":
                        print("Request denied")
                        tool_result_payload = {
                            "tool_name": tool_name,
                            "response": {"error": "User denied write request"}
                        }
                        continue

                try:
                    async with streamablehttp_client(MCP_SERVER_URL) as (read, write, _):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            result = await session.call_tool(tool_name, params)

                            output = getattr(result, "content", None)
                            print("\n======a=a=a=a=aa=a=a==\n")
                            print(output)
                            print("\n=a=a===========aa\n")
                            
                            if isinstance(output, list) and output:
                                item = output[0].text if hasattr(output[0], "text") else str(output[0])
                            else:
                                item = str(output)

                            print(f"Tool Output: {str(item)[:180]}..")

                            tool_result_payload = {
                                "tool_name": tool_name,
                                "response": item
                            }

                            print("\n=========================\n")
                            print(tool_result_payload)
                            print("\n==========================\n")

                except Exception as e:
                    print(f"Error calling tool '{tool_name}': {e}")
                    tool_result_payload = {
                        "tool_name": tool_name,
                        "response": {"error": str(e)}
                    }
                continue

            print("No tool call or final response. Stopping..")
            return

quirk_style = Style(
    [
        ("qmark",       "fg:#5fafff bold"),      # bright blue
        ("question",    "fg:#ffffff bold"),
        ("answer",      "fg:#aaffaa bold"),      # light green
        ("pointer",     "fg:#ffaf5f bold"),      # orange pointer
        ("highlighted", "fg:#ffaf5f bold"),
        ("selected",    "fg:#5fffff bold"),
        ("separator",   "fg:#444444"),
        ("instruction", "fg:#888888 italic"),
        ("text",        "fg:#cccccc"),
        ("disabled",    "fg:#555555 italic"),
    ]
)

def banner() -> None:
    title = "Quirk"
    line = "─" * (len(title) + 8)
    print(f"\n\033[38;5;39m{line}\033[0m")
    print(f"\033[1m\033[38;5;39m   {title}   \033[0m")
    print(f"\033[38;5;39m{line}\033[0m\n")

def main_menu() -> str:
    return questionary.select(
        "Action",
        choices=[
            "Ask Quirk",
            "Show Tools",
            "Exit",
        ],
        style=quirk_style,
        pointer="➜ ",
        instruction="(↑/↓ to move, Enter to select)",
    ).ask()

def print_agent(msg: str, color: str = "") -> None:
    prefix = "\033[38;5;240m│\033[0m"
    reset = "\033[0m"

    if color == "quirk":
        msg_color = "\033[1m\033[38;5;153m"
        msg = f"{msg}"
    elif color == "green":
        msg_color = "\033[38;5;140m"
    elif color == "yellow":
        msg_color = "\033[38;5;228m"
    elif color == "gray":
        msg_color = "\033[38;5;244m"
    else:
        msg_color = "\033[38;5;252m"

    print(f"{prefix} {msg_color}{msg}{reset}")


def thinking_animation(msg: str = "Quirk is thinking") -> None:
    spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    for _ in range(12):
        for s in spinner:
            print(f"\r\033[38;5;39m{s}\033[0m {msg}...", end="", flush=True)
            time.sleep(0.08)
    print("\r" + " " * 40 + "\r", end="")


def choose_api() -> None:
    ans = questionary.select(
        "Gemini model",
        choices=[
            "Yes – use my own API key (smarter model)",
            "No – free version",
        ],
        style=quirk_style,
        instruction="(Select with ↑/↓, confirm with Enter)",
    ).ask()

    if ans and "Yes" in ans:
        key = questionary.password(
            "Enter Gemini API key:",
            style=quirk_style,
        ).ask()
        if key:
            # os.environ["GEMINI_API_KEY"] = key
            print_agent("API key saved for this session.", "green")
        else:
            print_agent("No key entered – using free model.", "yellow")
    else:
        print_agent("Using free model.", "gray")


def start_ui() -> None:
    banner()
    choose_api()

    while True:
        action = main_menu()

        if action == "Exit":
            print_agent("Goodbye!", "gray")
            print_agent("Keep building. Keep quirking.", "quirk")
            break

        if action == "Show Tools":
            print_agent("Available tools:", "green")
            print("  • write_file   • read_file   • run_file")
            print("  • delete_path  • copy_file   • get_file_info")
            continue

        if action == "Ask Quirk":
            question = questionary.text(
                "Your request",
                style=quirk_style,
                instruction="(type your prompt and press Enter)",
            ).ask()
            if not question:
                print_agent("No prompt entered.", "yellow")
                continue

            thinking_animation()
            asyncio.run(run_quirk(question))

            again = questionary.confirm(
                "Ask another question?",
                default=True,
                style=quirk_style,
            ).ask()
            if not again:
                print_agent("Goodbye!", "green")
                print_agent("Keep building. Keep quirking.", "quirk")
                break

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        print("Quirk is ready! Run: quirk")
        return
    try:
        start_ui()
    except KeyboardInterrupt:
        print_agent("\nInterrupted.", "yellow")
    except Exception as e:
        print_agent(f"Error: {e}", "yellow")

if __name__ == "__main__":
    main()
