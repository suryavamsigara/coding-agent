# Quirk: Terminal-Based AI Coding Agent

Quirk is a CLI-based autonomous coding agent that lives in your terminal. It leverages the Model Context Protocol (MCP) to interact with the local file system while offloading the reasoning and planning to a cloud-hosted backend powered by Google Gemini 2.5 Flash.

<img width="1079" height="596" alt="image" src="https://github.com/user-attachments/assets/3ce0bca0-d048-4f90-9d7a-43ca464c0337" />

## Features:
* Terminal native: A beautiful TUI (Terminal User Interface) built with questionary library.
* Backend: Runs on Render (FastAPI + PostgreSQL). Manages session history and orchestrates the agentic workflow using Gemini 2.5 Flash.
* Client: Runs locally. Uses an MCP server to safely perform file operations (Read, Write, Create, Delete, Move) and execute shell commands.
* Human in the loop: Critical actions like writing files, deleting paths, rrunning shell commands require explicit user confirmation.
* Persistent memory: Chat sessions are stored in a PostgreSQL database, allowing Quirk to maintain context across turns.
* Streaming Responses: Real-time feedback and animations whiel the agent plans its next move.

## Architecture:

```
User [Terminal] --> TUI
CLI --> Backend
Backend --> Postgres DB
Backend --> Gemini
CLI --> Local Files
```
1. The client captures user input and sends it to the backend.
2. The backend processes the prompt, retrieves history from DB, and queries Gemini.
3. Gemini decides if it needs to read, write, or create files. It sends a tool call back.
4. The client intercepts the tool call, spins up a local mcp process, executes the action, and sends the result back to the backend.

## Project Structure:
```
coding-agent/
├── backend/                      # FastAPI Cloud Server
|   ├── app/
│   |   ├── agent_orchestrator.py # Gemini Logic
│   |   ├── database.py           # SQLAlchemy connection
│   |   ├── main.py               # API Endpoints
│   |   └── models.py             # DB Models
|   └── pyproject.toml            # Backens dependencies
├── client/                 # Local CLI Tool
│   ├── quirk/
│   │   ├── cli.py          # Entry point & TUI Logic
│   │   ├── mcp_server.py   # Local FastMCP Server (File Ops)
│   │   └── tui.py          # Styling & Animations
│   └── pyproject.toml      # Client dependencies
```

## Installation:
```
git clone https://github.com/suryavamsigara/coding-agent.git
cd coding-agent/client
uv sync
source .venv/bin/activate

quirk
```
