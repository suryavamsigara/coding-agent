import os
import json
import asyncio
import httpx
import argparse
import questionary
from typing import Optional, Any
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

BACKEND_URL = "http://127.0.0.1:8000/chat"
MCP_SERVER_URL = "http://127.0.0.1:9000/mcp"
TOOLS_REQ = "http://127.0.0.1:8000/tools"

async def safe_input(prompt: str) -> str:
    """Lets us use input() without freezing the async event loop"""
    return await asyncio.to_thread(input, prompt)

async def run_quirk(prompt: str):
    tool_response: Optional[Any] = None
    
    async with httpx.AsyncClient() as client:
        while True:
            print("\nSending context to backend..")
            payload = {
                "prompt": prompt,
                "tool_response": tool_response
            }
            print(payload)
        
            try:
                resp = await client.post(BACKEND_URL, json=payload, timeout=30.0)
                resp.raise_for_status()
                data = resp.json()
                print(data)
            except httpx.HTTPStatusError as e:
                print(f"HTTP error from backend: {e.response.status_code}")
                break
            except httpx.RequestError as e:
                print(f"Error connecting to backend at {BACKEND_URL}: {e}")
                break

            if data.get("final_answer"):
                print(f"\nFinal Response: {data['final_answer']}")
                break
            
            elif data.get("tool_call"):
                call = data['tool_call']
                tool_name = call['tool_name']
                params = call.get('params', {})
                print(f"Quirk wants to run: {tool_name}({params})")

                try:
                    async with streamablehttp_client(MCP_SERVER_URL) as (read, write, _):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            result = await session.call_tool(tool_name, params)

                            output = getattr(result, "content")
                            
                            print_output = str(output)
                            if len(print_output) > 200:
                                print_output = print_output[:200] + "..."
                            
                            print(f"Tool Result: {print_output}")
                            tool_response = output
                except Exception as e:
                    print(f"Error connecting to local MCP server at {MCP_SERVER_URL}: {e}")
                    tool_response = f"Error: {e}"
                    break
            else:
                print("No response from llm.")
       
            await asyncio.sleep(0.5)

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
