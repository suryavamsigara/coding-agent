import os
import sys, time
import json
import asyncio
import subprocess
import socket
import httpx
import random
import questionary
from questionary import Style
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

BACKEND_URL = "http://127.0.0.1:8000/chat"
MCP_SERVER_URL = "http://127.0.0.1:9000/mcp"
MAX_ITERS = 8

mcp_process = None

tool_actions = {
    "get_file_info": "Scanning Files...",
    "read_file": "Reading File Contents..",
    "write_file": "Applying Modifications...",
    "delete_path": "Deleting..",
    "copy_file": "Copying File...",
    "run_file": "Executing Script..",
    "_default": "Quirking"
}

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def ensure_mcp_server():
    global mcp_process
    if is_port_in_use(9000):
        print_agent("MCP server already running..", "gray")
        return
    print_agent("Starting MCP server", "gray")

    try:
        mcp_process = subprocess.Popen(
            [sys.executable, "-m", "quirk.mcp_server"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        time.sleep(2)
        if is_port_in_use(9000):
            print_agent("MCP server started..", "gray")
        else:
            print_agent("MCP server failed to start", "yellow")
    except Exception as e:
        print_agent(f"Error starting MCP server: {e}", "yellow")

def stop_mcp_server():
    global mcp_process
    if mcp_process and mcp_process.poll() is None:
        print_agent("Stoppign MCP server...", "gray")
        mcp_process.terminate()
        try:
            mcp_process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            mcp_process.kill()
        print_agent("MCP server stopped", "gray")

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
    except Exception as e:
        print_agent(f"MCP server failed to start: {e}", "yellow")
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
                print_agent(data['final_answer'])
                return

            elif data.get("tool_call"):
                call = data["tool_call"]
                tool_name = call["tool_name"]
                params = call.get("params", {})
                action_msg = tool_actions.get(tool_name, tool_actions["_default"])
                print_agent(action_msg, "quirk")

                if tool_name in {"write_file", "delete_path"}:
                    confirm = (await safe_input("Apply this change? [y/N]: ")).strip().lower()
                    if confirm != "y":
                        print_agent("request denied", "yellow")
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
                            
                            if isinstance(output, list) and output:
                                item = output[0].text if hasattr(output[0], "text") else str(output[0])
                            else:
                                item = str(output)

                            print_agent("✔ Done", "gray")

                            tool_result_payload = {
                                "tool_name": tool_name,
                                "response": item
                            }
                except Exception as e:
                    print_agent(f"Error {tool_actions.get(tool_name)}\n{e}", "yellow")
                    tool_result_payload = {
                        "tool_name": tool_name,
                        "response": {"error": str(e)}
                    }
                continue

            print("No tool call or final response. Stopping..")
            return

quirk_style = Style(
    [
        ("qmark",       "fg:#5fafff bold"),
        ("question",    "fg:#ffffff bold"),
        ("answer",      "fg:#aaffaa bold"),
        ("pointer",     "fg:#ffaf5f bold"),
        ("highlighted", "fg:#ffaf5f bold"),
        ("selected",    "fg:#5fffff bold"),
        ("separator",   "fg:#444444"),
        ("instruction", "fg:#888888 italic"),
        ("text",        "fg:#cccccc"),
        ("disabled",    "fg:#555555 italic"),
    ]
)

glitch = ["Decoding", "Thinking", "Re-routing synapses", "Quantum whispering",
          "Breaking reality", "Aligning bits", "Quirking"]

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
            "Show Configured Tools",
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
    elif color == "text":
        msg_color = "\033[38;5;15m"
    else:
        msg_color = "\033[38;5;252m"

    print(f"{prefix} {msg_color}{msg}{reset}")


def thinking_animation(msgs, duration=10) -> None:
    spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    for _ in range(duration):
        msg = random.choice(msgs)
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
    ensure_mcp_server()
    banner()
    choose_api()

    while True:
        action = main_menu()

        if action == "Exit":
            print_agent("Goodbye!", "gray")
            print_agent("Keep building. Keep quirking.", "quirk")
            stop_mcp_server()
            break

        if action.endswith("Tools"):
            print_agent("Available tools:", "green")
            print_agent("  • write files   • read files   • run python", "text")
            print_agent("  • delete files  • move files   • get folder structure", "text")
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

            thinking_animation(glitch, duration=5)
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
    finally:
        stop_mcp_server()

if __name__ == "__main__":
    main()
