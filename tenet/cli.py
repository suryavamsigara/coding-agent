import os
import sys, time
import asyncio
import subprocess
import socket
import httpx
import json
import argparse
import importlib.metadata
import random
import questionary
from .tui import (
    tool_actions,
    quirk_style,
    glitch,
    banner,
    print_agent
)
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

# BACKEND_URL = "http://127.0.0.1:8000/api"
BACKEND_URL = "https://quirk-agent-backend.onrender.com/api"
INIT_URL = f"{BACKEND_URL}/init-session"
CHAT_URL = f"{BACKEND_URL}/chat"
MCP_SERVER_URL = "http://127.0.0.1:9000/mcp"
MAX_ITERS = 12 # will put this in backend later

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

    async def _handle_tool_call(self, data: dict, mcp_session: ClientSession) -> dict:
        """
        Handles tool call and showing loading spinner
        Returns the tool_result_payload.
        """
        call = data["tool_call"]
        tool_name = call["tool_name"]
        params = call.get("params", {})
        action_msg = tool_actions.get(tool_name, tool_actions["_default"])
        status_task = None
        
        if tool_name in {"write_file", "delete_path", "run_shell_command"}:
            confirm = await questionary.confirm(
                "Apply this change?", 
                default=False, 
                style=self.style
            ).ask_async()
            if not confirm:
                print_agent("request denied", "yellow")
                return {"tool_name": tool_name, "response": {"error": "User denied write request"}}
                
        try:
            status_task = asyncio.create_task(self._show_tool_status(action_msg))
            result = await mcp_session.call_tool(tool_name, params)
            status_task.cancel()
            await asyncio.wait([status_task], timeout=0.2)
            
            output = getattr(result, "content", None)
            item = str(output)
            if isinstance(output, list) and output:
                item = output[0].text if hasattr(output[0], "text") else str(output[0])
            
            return {"tool_name": tool_name, "response": item}
        
        except Exception as e:
            if status_task and not status_task.done():
                status_task.cancel()
                await asyncio.wait([status_task], timeout=0.2)
            print_agent(f"Error {action_msg}\n{e}", "yellow")
            return {"tool_name": tool_name, "response": {"error": str(e)}}

    async def run_quirk(self, prompt: str, mcp_session: ClientSession, thinking_task: asyncio.Task):
        tool_result_payload = None
        cwd = os.getcwd()
        current_prompt = prompt
        is_streaming_text = False

        for _ in range(MAX_ITERS):
            payload = {
                "prompt": current_prompt,
                "cwd": cwd,
                "session_id": self.session_id,
                "tool_result": tool_result_payload,
            }

            current_prompt = None
            tool_result_payload = None
            is_streaming_text = False
                
            try:
                async with httpx.AsyncClient() as http_client:
                    async with http_client.stream("POST", CHAT_URL, json=payload, timeout=None) as resp:
                        resp.raise_for_status()
                        
                        async for line in resp.aiter_lines():
                            if not thinking_task.done():
                                thinking_task.cancel()
                                await asyncio.wait([thinking_task], timeout=0.2)

                            if not line.strip():
                                continue

                            data = json.loads(line)
                            self.session_id = data.get("session_id") or self.session_id

                            if data.get("answer_chunk"):
                                if not is_streaming_text:
                                    print_agent(" ", "text", end="")
                                    is_streaming_text = True
                                print_agent(data["answer_chunk"], "text", end="")
                                continue

                            if data.get("tool_call"):
                                if not thinking_task.done():
                                    thinking_task.cancel()
                                    await asyncio.wait([thinking_task], timeout=0.2)
                                if is_streaming_text:
                                    print()
                                    is_streaming_text = False
                                tool_result_payload = await self._handle_tool_call(data, mcp_session)
                                break
                            
                            if data.get("final_answer"):
                                if is_streaming_text:
                                    print()
                                    is_streaming_text = False
                                else:
                                    print_agent(data['final_answer'], "text")
                                return
                
            except Exception as e:
                if not thinking_task.done():
                    thinking_task.cancel()
                    await asyncio.wait([thinking_task], timeout=0.2)
                print_agent(f"Error connecting to backend at: {e}", "yellow")           
                return
            finally:
                if thinking_task and not thinking_task.done():
                    thinking_task.cancel()
                    try:
                        await thinking_task
                    except asyncio.CancelledError:
                        pass

            if tool_result_payload:
                continue
            else:
                if is_streaming_text:
                    print()
                return
            
        if thinking_task and not thinking_task.done():
            thinking_task.cancel()
            await asyncio.wait([thinking_task], timeout=0.2)
              
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
                    
                    thinking_task = None

                    while True:
                        print()
                        try:
                            question = await questionary.text(
                                "You",
                                style=quirk_style,
                                instruction="",
                                multiline=True,
                                qmark=">"
                            ).ask_async()

                            if not question:
                                continue

                            if question.strip().lower() in ("/exit", "/back"):
                                print_agent("Exiting chat session..", "gray")
                                break

                            thinking_task = asyncio.create_task(self._thinking_animation(glitch))

                            await self.run_quirk(question, mcp_session, thinking_task)

                            if thinking_task and not thinking_task.done():
                                thinking_task.cancel()
                                try:
                                    await thinking_task
                                except asyncio.CancelledError:
                                    pass
                        except asyncio.CancelledError:
                            if thinking_task and not thinking_task.done():
                                thinking_task.cancel()
                                try:
                                    await thinking_task
                                except asyncio.CancelledError:
                                    pass
                            raise
                    
                        except KeyboardInterrupt:
                            print_agent("\nInterrupted by user", "yellow")
                            if thinking_task and not thinking_task.done():
                                thinking_task.cancel()
                                try:
                                    await thinking_task
                                except asyncio.CancelledError:
                                    pass
                            break
        except Exception as e:
            print_agent(f"Could not connnect to MCP server: {e}", "yellow")
            print_agent("Chat session exited", "gray")

    async def _thinking_animation(self, msgs) -> None:
        spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        try:
            while True:
                msg = random.choice(msgs)
                for s in spinner:
                    print(f"\r\033[38;5;39m{s}\033[0m {msg}...", end="", flush=True)
                    await asyncio.sleep(0.08)
        except asyncio.CancelledError:
            print("\r" + " " * 40 + "\r", end="")
            raise

    async def _show_tool_status(self, action_message: str):
        spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        i = 0
        try:
            while True:
                s = spinner[i % len(spinner)]
                print_agent(f"\r{s} {action_message}..", "quirk", end="")
                await asyncio.sleep(0.08)
                i += 1
        except asyncio.CancelledError:
            print()
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
            qmark="$"
        ).ask_async()
        
    async def run(self):
        self._ensure_mcp_process()
        time.sleep(0.8)
        banner()

        while True:
            action = await self._main_menu()

            if action == "Exit":
                print_agent("Goodbye!", "text")
                break

            if action.endswith("Tools"):
                print_agent("Available tools:", "green")
                print_agent("  • write files    • read files    • run python", "text")
                print_agent("  • delete files   • move files    • get folder structure", "text")
                print_agent("  • copy files    • rename path    • create dir", "text")
                continue

            if action == "Ask Quirk":
                await self._chat_loop()


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
