# Tenet

A terminal AI coding agent. Describe what you want, and Tenet explores your codebase, plans the changes, executes them, and verifies - narrating every step in real time.

---

## What you can use it for

- Building features from scratch
- Debugging and fixing errors
- Refactoring and cleaning up code
- Writing and running tests
- Understanding an unfamiliar codebase
- Anything you'd pair-program on

---

---
 
## How it works
 
Tenet runs a Reason → Act → Observe loop powered by DeepSeek V4. It uses a structured set of tools - file search, targeted reads, surgical edits, shell commands — and enforces strict rules to prevent wasteful or destructive behaviour:
 
- **Always plans before touching existing files** — a `submit_plan` step shows you what will change and waits for your approval
- **Always confirms destructive operations** — `delete_path` and `rm`-style commands require explicit confirmation
- **Surgical edits only** — `replace_in_file` for single changes, `apply_patch` for multi-location diffs; `write_file` is for new files only
The agent signals every phase transition (EXPLORING → PLANNING → EXECUTING → VERIFYING → DONE) so you always know where it is.
 
---

## Models

| Alias | Model | Notes |
|---|---|---|
| `flash` | `deepseek-v4-flash` | Default. Fast, great for most tasks |
| `flash-t` | `deepseek-v4-flash` + thinking | Slower, better reasoning |
| `pro` | `deepseek-v4-pro` | More capable |
| `pro-t` | `deepseek-v4-pro` + thinking | Maximum reasoning, complex tasks |

Switch at any time with `/model pro` or `/model flash-t`.

---

## Installation

Requires Python 3.12+ and [uv](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/yourname/tenet
cd tenet
uv tool install .
```
`uv tool install` makes `tenet` available globally — no virtual environment activation needed, works from any folder.

Set your DeepSeek API key:

```bash
export DEEPSEEK_API_KEY=sk-...
```

Add that to your `.bashrc` / `.zshrc` to make it permanent.

---

## Usage

Works like `git` — run it from whatever project you're in:

```bash
cd ~/any-project
tenet
```

### Commands

| Command | Description |
|---|---|
| `/model [alias]` | Show or switch model |
| `/reset` | Clear conversation, start fresh |
| `/context` | Show what Tenet knows about the project |
| `/tree` | Print the directory tree |
| `/ls` | List project files |
| `/tools` | List available tools |
| `/log` | Path to the current session log |
| `/help` | Show help |
| `exit` / `quit` | Quit |

---
 
## Project structure
 
```
tenet/
├── core/
│   ├── agent_orchestrator.py   # Reason-Act-Observe loop
│   ├── memory.py               # Two-tier conversation memory + project context
│   └── session_logger.py       # JSONL + human-readable session logs
├── tools/
│   ├── executor.py             # Tool registry, dispatch, and read guards
│   ├── file_ops.py             # File system operations
│   ├── shell_ops.py            # Shell command execution
│   ├── context_ops.py          # Per-agent project context updater
│   └── tool_schema.py          # OpenAI-compatible tool definitions
├── ui/
│   ├── cli.py                  # Interactive CLI (prompt_toolkit)
│   └── display.py              # Rich terminal UI
├── llm/
│   └── client.py               # DeepSeek API client
├── prompts/
│   └── TENET.md                # System prompt
└── config.py                   # Working directory (Path.cwd())
```
 
---

## Memory model
 
Tenet has two memory tiers:
 
**Project context** — persists across the whole session. File summaries, symbol locations, and architectural facts are stored here immediately after every file read or write. Never trimmed. This is what lets the agent avoid re-reading files.
 
**Conversation window** — the last N message exchanges with the model. Trimmed by complete exchange (user → tools → assistant) so tool call / result pairs are never split. Reasoning content is stripped before each new user turn per DeepSeek's multi-turn contract.
 
---

## Safety model
 
- All file paths are resolved relative to `cwd()` and rejected if they escape it
- `write_file` refuses to overwrite existing files
- `read_file` is blocked on already-tracked files and files over the size limit
- `read_file_range` is blocked for spans over 100 lines
- `delete_path` always prompts for confirmation
- Shell commands matching destructive patterns (`rm`, `DROP TABLE`, etc.) always prompt for confirmation
---

## Requirements

- Python 3.12+
- uv
- DeepSeek API key - get one at [platform.deepseek.com](https://platform.deepseek.com)
