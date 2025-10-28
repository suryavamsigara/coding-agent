# quirk/cli.py
import os
import json
import asyncio
import httpx
import argparse
import questionary
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
                print(f"\nFinal Response:\n{data["final_answer"]}")
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
                                item = output[0].text if hasattr(output[0], "text") else str(item)

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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", type=str)
    args = parser.parse_args()

    try:
        asyncio.run(run_quirk(args.prompt))
    except KeyboardInterrupt:
        print("\nInterrupted..")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
