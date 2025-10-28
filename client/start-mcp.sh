echo "Starting Quirk MCP Server..."
echo "Directory: $(pwd)"
echo "----------------------------------------"

source .venv/bin/activate
uv run -m quirk/mcp_server
