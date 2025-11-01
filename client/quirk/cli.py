import os
import sys, time
import asyncio
import subprocess
import socket
import httpx
import argparse
import importlib.metadata
import random
import questionary
from questionary import Style
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

BACKEND_URL = "http://127.0.0.1:8000/api"
INIT_URL = f"{BACKEND_URL}/init-session"
CHAT_URL = f"{BACKEND_URL}/chat"
MCP_SERVER_URL = "http://127.0.0.1:9000/mcp"
MAX_ITERS = 12 # will put this in backend later

tool_actions = {
    "get_file_info": "Scanning Files",
    "read_file": "Reading File Contents",
    "write_file": "Writing...",
    "delete_path": "Deleting..",
    "copy_file": "Copying File...",
    "run_file": "Executing Script..",
    "create_directory": "Creating folder",
    "rename_path": "Renaming path..",
    "_default": "Quirking"
}

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

class QuirkApp:
    def __init__(self):
        self.mcp_process: subprocess.Popen | None = None
        self.session_id: str | None = None
        self.style = quirk_style

    def _ensure_mcp_process(self):
        if is_port_in_use(9000):
            print_agent("MCP server already running..", "gray")
            return
        print_agent("Starting MCP server", "gray")
        try:
            self.mcp_process = subprocess.Popen(
                [sys.executable, "-m", "quirk.mcp_server"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )
            time.sleep(1)
            if is_port_in_use(9000):
                print_agent("MCP server started", "gray")
            else:
                print_agent("MCP server failed to start", "yellow")
        except Exception as e:
            print_agent(f"Error starting MCP server: {e}", "yellow")
            print_agent("Cannot perform file operations.", "yellow")

    def close(self):
        if self.mcp_process and self.mcp_process.poll() is None:
            self.mcp_process.terminate()
            try:
                self.mcp_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                print_agent("MCP server not responding. Forcing kill..", "yellow")
                self.mcp_process.kill()
                self.mcp_process.wait()
            print_agent("MCP server stopped", "gray")
    
    async def _safe_input(self, prompt: str):
        """Lets us use input() without freezing the async event loop"""
        return await asyncio.to_thread(input, prompt)

    async def run_quirk(self, prompt: str, mcp_session: ClientSession):
        """
        Runs the agent loop for a prompt.
        It uses session_id for context
        """

        tool_result_payload = None
        cwd = os.getcwd()

        current_prompt = prompt

        async with httpx.AsyncClient() as http_client:
            for _ in range(MAX_ITERS):
                payload = {
                    "prompt": current_prompt,
                    "cwd": cwd,
                    "session_id": self.session_id,
                    "tool_result": tool_result_payload,
                }

                try:
                    resp = await http_client.post(CHAT_URL, json=payload, timeout=60)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    print_agent(f"Error connecting to backend at: {e}", "yellow")
                    return
                
                current_prompt = None
                tool_result_payload = None
                self.session_id = data.get("session_id")

                if data.get("final_answer"):
                    print_agent(data['final_answer'], "text")
                    return

                elif data.get("tool_call"):
                    call = data["tool_call"]
                    tool_name = call["tool_name"]
                    params = call.get("params", {})
                    action_msg = tool_actions.get(tool_name, tool_actions["_default"])
                    
                    if data.get("thought"):
                        print_agent(data["thought"], "text")

                    print_agent(action_msg, "quirk")

                    if tool_name in {"write_file", "delete_path"}:
                        confirm = (await self._safe_input("Apply this change? [y/N]: ")).strip().lower()
                        if confirm != "y":
                            print_agent("request denied", "yellow")
                            tool_result_payload = {
                                "tool_name": tool_name,
                                "response": {"error": "User denied write request"}
                            }
                            continue

                    status_task = None
                        
                    try:
                        status_task = asyncio.create_task(self._show_tool_status(action_msg))
                        result = await mcp_session.call_tool(tool_name, params)
                        status_task.cancel()
                        await asyncio.wait([status_task], timeout=0.2)
                        output = getattr(result, "content", None)
                        
                        if isinstance(output, list) and output:
                            item = output[0].text if hasattr(output[0], "text") else str(output[0])
                        else:
                            item = str(output)

                        tool_result_payload = {
                            "tool_name": tool_name,
                            "response": item
                        }
                    except Exception as e:
                        if status_task and not status_task.done():
                            status_task.cancel()
                            await asyncio.wait([status_task], timeout=0.2)
                        print_agent(f"Error {action_msg}\n{e}", "yellow")
                        tool_result_payload = {
                            "tool_name": tool_name,
                            "response": {"error": str(e)}
                        }
                    continue
                else:
                    print_agent("No tool call or final response. Stopping..", "gray")
                    return
            else:
                print_agent(f"Maximum steps ({MAX_ITERS}) reached. Forcing final answer.", "yellow")
                try:
                    await http_client.post(
                        BACKEND_URL,
                        json={
                            "prompt": "Maximum steps reached. Summarize progress and return final answer immediately.",
                            "cwd": cwd,
                            "session_id": self.session_id,
                            "tool_result": None,
                        },
                        timeout=60
                    )
                except Exception as e:
                    print_agent(f"Failed to send final prompt: {e}", "yellow")
                
    async def _chat_loop(self):
        self.session_id = None

        try:
            async with streamablehttp_client(MCP_SERVER_URL) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as mcp_session:
                    await mcp_session.initialize()
                    
                    tools_obj = await mcp_session.list_tools()
                    tools_list = [tool.model_dump() for tool in tools_obj.tools]

                    payload = {
                        "tools_list": tools_list,
                    }

                    try:
                        async with httpx.AsyncClient() as http_client:
                            resp = await http_client.post(INIT_URL, json=payload, timeout=30)
                            resp.raise_for_status()
                            data = resp.json()
                            self.session_id = data.get("session_id")
                            
                            if not self.session_id:
                                print_agent("Error: Session ID wasn't created.", "yellow")
                                return
                    except Exception as e:
                        print_agent(f"Could not initialize backend session: {e}", "yellow")
                        return

                    while True:
                        question = await questionary.text(
                            "You",
                            style=quirk_style,
                            instruction="",
                            multiline=True,
                        ).ask_async()

                        if not question:
                            continue

                        if question.strip().lower() in ("/exit", "/back"):
                            print_agent("Exiting chat session..", "gray")
                            break

                        await self._thinking_animation(glitch, duration=8)
                        await self.run_quirk(question, mcp_session)
        except Exception as e:
            print_agent(f"Could not connnect to MCP server: {e}", "yellow")
            print_agent("Chat session exited", "gray")

    async def _thinking_animation(self, msgs, duration=10) -> None:
        spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        for _ in range(duration):
            msg = random.choice(msgs)
            for s in spinner:
                print(f"\r\033[38;5;39m{s}\033[0m {msg}...", end="", flush=True)
                await asyncio.sleep(0.08)
        print("\r" + " " * 40 + "\r", end="")

    async def _show_tool_status(self, action_message: str):
        spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        i = 0
        try:
            while True:
                s = spinner[i % len(spinner)]
                print(f"\r\033[38;5;39m{s}\033[0m {action_message}..", end="", flush=True)
                await asyncio.sleep(0.08)
                i += 1
        except asyncio.CancelledError:
            print("\r" + " " * (len(action_message) + 10) + "\r", end="")
            print_agent(f"✔ Done", "gray")
            raise

    async def _main_menu(self) -> str:
        return await questionary.select(
            "Action",
            choices=[
                "Ask Quirk",
                "Show Configured Tools",
                "Exit",
            ],
            style=quirk_style,
            pointer="➜ ",
            instruction="(↑/↓, Enter)",
        ).ask_async()
    
    async def _choose_api(self) -> None:
        ans = await questionary.select(
            "Gemini model",
            choices=[
                "Yes - my own API key (can get a smarter model)",
                "No - free version",
            ],
            style=quirk_style,
            instruction="(↑/↓, Enter)",
        ).ask_async()

        if ans and "Yes" in ans:
            key = await questionary.password(
                "Enter Gemini API key:",
                style=quirk_style,
            ).ask_async()
            if key:
                # os.environ["GEMINI_API_KEY"] = key
                print_agent("API key saved for this session.", "green")
            else:
                print_agent("No key entered – using free model.", "yellow")
        else:
            print_agent("Using free model.", "gray")
        
    async def run(self):
        self._ensure_mcp_process()
        time.sleep(0.8)
        banner()
        await self._choose_api()

        while True:
            action = await self._main_menu()

            if action == "Exit":
                print_agent("Goodbye!", "text")
                print_agent("Keep building. Keep quirking.", "quirk")
                break

            if action.endswith("Tools"):
                print_agent("Available tools:", "green")
                print_agent("  • write files    • read files    • run python", "text")
                print_agent("  • delete files   • move files    • get folder structure", "text")
                continue

            if action == "Ask Quirk":
                await self._chat_loop()


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

glitch = ["Decoding", "Thinking", "Quirking", "Analyzing"]

def banner() -> None:
    title = "Quirk"
    line = "─" * (len(title) + 8)
    print(f"\n\033[38;5;180m{line}\033[0m")
    print(f"\033[1m\033[38;5;179m   {title}   \033[0m")
    print(f"\033[38;5;180m{line}\033[0m\n")

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


def main():
    parser = argparse.ArgumentParser(
        prog="quirk",
        description="Quirk - Smart coding assistant"
    )

    parser.add_argument("-v", "--version", action="store_true", help="Show installed version")

    args = parser.parse_args()

    if args.version:
        try:
            version = importlib.metadata.version("quirk")
        except importlib.metadata.PackageNotFoundError:
            version = "unknown"
        print(f"quirk {version}")
        return
    
    app = QuirkApp()
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        print_agent("\nInterrupted.", "yellow")
    except Exception as e:
        print_agent(f"Error: {e}", "yellow")
    finally:
        app.close()

if __name__ == "__main__":
    main()
