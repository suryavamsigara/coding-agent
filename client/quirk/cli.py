import os
import sys
import asyncio
from pathlib import Path
import questionary
from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters
from .agent_orchestrator import CodingAgent

async def main_async():
    server_path = Path(__file__).parent / "mcp_server.py"
    if not server_path.exists():
        print(f"Error: mcp_server.py not found.")
        sys.exit(1)

    server_params = StdioServerParameters(
        command="python3",
        args=[str(server_path)]
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            agent = CodingAgent(session=session)
            print("MCP CODING AGENT")
            await agent.run()

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
