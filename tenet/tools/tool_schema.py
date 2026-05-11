OPENAI_TOOLS_LIST = [

    #  PHASE MANAGEMENT

    {
        "type": "function",
        "function": {
            "name": "begin_phase",
            "description": (
                "Signal a phase transition to the user. MUST be called at every major stage:\n"
                "  • Start of any exploration: begin_phase('EXPLORING', 'Reading auth module')\n"
                "  • Before executing changes: begin_phase('EXECUTING', 'Updating 3 files')\n"
                "  • Before running tests: begin_phase('VERIFYING', 'Running pytest')\n"
                "  • When done: begin_phase('DONE', 'All changes complete')\n\n"
                "Call this as the VERY FIRST tool in each phase. Do not call it mid-phase."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "phase": {
                        "type": "string",
                        "enum": ["EXPLORING", "PLANNING", "EXECUTING", "VERIFYING", "DONE"],
                        "description": "The phase you are entering.",
                    },
                    "description": {
                        "type": "string",
                        "description": "One sentence: what you will do in this phase.",
                    },
                },
                "required": ["phase"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_plan",
            "description": (
                "Present your proposed plan to the user and wait for approval.\n\n"
                "WHEN to call:\n"
                "  • After exploring, before making any changes to EXISTING files\n"
                "  • When the task modifies more than 1 file\n"
                "  • When the task is complex or has unclear requirements\n\n"
                "WHEN to skip:\n"
                "  • Purely additive tasks: creating a new standalone file\n"
                "  • Simple 1-file edits the user explicitly described\n\n"
                "The tool PAUSES execution and returns one of:\n"
                "  'APPROVED'              → proceed as planned\n"
                "  'REJECTED: <reason>'    → replan and call submit_plan again\n"
                "  'MODIFIED: <feedback>'  → adapt your plan to the feedback, then proceed\n\n"
                "You MUST read and act on the return value."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": "One sentence describing the overall objective.",
                    },
                    "steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ordered list of concrete steps you will take.",
                    },
                    "files_to_modify": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "File paths that will be changed (not created).",
                    },
                    "estimated_changes": {
                        "type": "string",
                        "description": "Optional: brief description of the change scope.",
                    },
                },
                "required": ["goal", "steps"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_confirmation",
            "description": (
                "Ask the user to confirm before an irreversible action.\n\n"
                "WHEN to call:\n"
                "  • Before any shell command that destroys data (rm, DROP TABLE, etc.)\n"
                "  • Note: delete_path and destructive run_command call this automatically.\n"
                "    Only call manually for other high-risk actions.\n\n"
                "Returns 'APPROVED' or 'CANCELLED'. You MUST check the return value."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Short label for the action, e.g. 'Drop production database'.",
                    },
                    "details": {
                        "type": "string",
                        "description": "Full command or details of what will happen.",
                    },
                    "risk": {
                        "type": "string",
                        "enum": ["medium", "high"],
                        "description": "'high' for irreversible data loss; 'medium' for recoverable but disruptive.",
                    },
                },
                "required": ["action", "details"],
            },
        },
    },

    #  SEARCH

    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": (
                "Grep-style regex search with surrounding context lines.\n\n"
                "This is your PRIMARY tool before any edit. Use it to:\n"
                "  • Get exact line numbers for read_file_range / replace_in_file\n"
                "  • Verify that a change was applied (instead of re-reading the file)\n"
                "  • Find all usages of a symbol before renaming it\n\n"
                "context_lines=4 gives enough surrounding text to use directly in replace_in_file.\n"
                "The returned 'line' numbers are exact — use them directly with read_file_range."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Python regex. E.g. 'def train\\\\b', 'class Auth', 'TODO'.",
                    },
                    "file_glob": {
                        "type": "string",
                        "description": "Restrict search. E.g. '**/*.py', 'src/**/*.ts'. Default: '**/*'.",
                        "default": "**/*",
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Default: false.",
                        "default": False,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Default: 50.",
                        "default": 50,
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "Lines of context per match. Use 4–5 when you need text for replace_in_file. Default: 2.",
                        "default": 2,
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_symbol",
            "description": (
                "Find where a function, class, or variable is defined or used.\n\n"
                "Use as first step when you know the name of what you want to change. "
                "Returns file path + line numbers → use with read_file_range to read, "
                "and replace_in_file to edit."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Exact name of the function, class, or variable.",
                    },
                    "file_glob": {
                        "type": "string",
                        "description": "Default: '**/*' (all files).",
                        "default": "**/*",
                    },
                },
                "required": ["symbol"],
            },
        },
    },

    #  READ

    {
        "type": "function",
        "function": {
            "name": "get_file_info",
            "description": "Get metadata (size, modified time, type). Use to check if a path exists or to gauge file size before deciding to read it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path."},
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the ENTIRE content of a file.\n\n"
                "ONLY call this when ALL conditions are met:\n"
                "  1. The file does NOT appear in <project_context> (not yet known)\n"
                "  2. The file cannot be navigated with search_files alone\n"
                "  3. The file is small — verify with get_file_info if unsure\n\n"
                "NEVER call this on a file already in <project_context>.\n"
                "NEVER call this to verify an edit — use search_files instead.\n\n"
                "After calling: IMMEDIATELY call update_project_context with a summary."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path to the file."},
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file_range",
            "description": (
                "Read specific lines from a file (1-indexed, inclusive).\n\n"
                "PRECONDITION: start_line and end_line MUST come from search_files or "
                "find_symbol output. NEVER guess them.\n\n"
                "This is the correct tool after search_files gives you line numbers. "
                "Do NOT use read_file when you already have a target location."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path to the file."},
                    "start_line": {"type": "integer", "description": "First line (1-indexed). Must come from search_files output."},
                    "end_line": {"type": "integer", "description": "Last line (inclusive). Must come from search_files output."},
                },
                "required": ["file_path", "start_line", "end_line"],
            },
        },
    },

    #  WRITE / CREATE

    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Create a new file with the given content.\n\n"
                "ONLY for NEW files that do not yet exist.\n"
                "Will REFUSE if the file already exists — use replace_in_file or apply_patch instead.\n\n"
                "After writing: IMMEDIATELY call update_project_context with a summary of what you created."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path. Must NOT already exist."},
                    "content": {"type": "string", "description": "Full file content."},
                },
                "required": ["file_path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create an empty file and any needed parent directories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path to create."},
                },
                "required": ["file_path"],
            },
        },
    },

    #  EDIT  (primary tools for modifying existing files)

    {
        "type": "function",
        "function": {
            "name": "replace_in_file",
            "description": (
                "Replace the FIRST occurrence of an exact string. PRIMARY edit tool.\n\n"
                "Rules:\n"
                "  • search_text must be BYTE-FOR-BYTE identical to the file\n"
                "  • Copy search_text from read_file_range output — never type from memory\n"
                "  • Include 2–3 lines of surrounding context to ensure uniqueness\n"
                "  • On success ('changed': true): DO NOT re-read to verify\n"
                "  • On 'not found': run search_files to get exact current text, then retry\n\n"
                "Use apply_patch when editing 3+ separate locations at once."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "search_text": {"type": "string", "description": "Exact text to find. Copied verbatim from the file."},
                    "replace_text": {"type": "string", "description": "Replacement text."},
                },
                "required": ["file_path", "search_text", "replace_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "patch_file_lines",
            "description": (
                "Replace an exact line range with new content.\n\n"
                "Use when you have line numbers from search_files and want to replace a block wholesale. "
                "Faster than apply_patch for single contiguous replacements."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "start_line": {"type": "integer", "description": "From search_files output."},
                    "end_line": {"type": "integer", "description": "From search_files output."},
                    "new_content": {"type": "string", "description": "Replacement text for lines start_line through end_line."},
                },
                "required": ["file_path", "start_line", "end_line", "new_content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_patch",
            "description": (
                "Apply a unified diff patch. Use for 3+ separate edits to one file in one shot.\n\n"
                "@@ line numbers must be EXACT — get them from search_files first.\n"
                "If patch fails, the tool returns the current file content — use that to rebuild.\n"
                "Prefer replace_in_file for single-block changes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "patch": {"type": "string", "description": "Unified diff (diff -u format). @@ numbers must be exact."},
                },
                "required": ["file_path", "patch"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_diff",
            "description": "Preview a unified diff between current file content and proposed new content. Use before write_file on a new file to verify what will be created.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "new_content": {"type": "string"},
                },
                "required": ["file_path", "new_content"],
            },
        },
    },

    #  DIRECTORY / FILE MANAGEMENT

    {
        "type": "function",
        "function": {
            "name": "directory_tree",
            "description": "ASCII tree view of a directory. Best first call for understanding project structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dir_path": {"type": "string", "default": ".", "description": "Root to display. Default: '.'"},
                    "max_depth": {"type": "integer", "default": 4, "description": "Max recursion depth."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files matching a glob pattern. Use when you need a flat list to iterate over.",
            "parameters": {
                "type": "object",
                "properties": {
                    "glob_pattern": {"type": "string", "default": "**/*"},
                    "max_results": {"type": "integer", "default": 200},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Create a directory and all needed parent directories.",
            "parameters": {
                "type": "object",
                "properties": {"dir_path": {"type": "string"}},
                "required": ["dir_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "copy_file",
            "description": "Copy a file to a new path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_path": {"type": "string"},
                    "destination_path": {"type": "string"},
                },
                "required": ["source_path", "destination_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rename_path",
            "description": "Rename or move a file or directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "old_path": {"type": "string"},
                    "new_path": {"type": "string"},
                },
                "required": ["old_path", "new_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_path",
            "description": (
                "Delete a file or directory (recursively). ALWAYS asks for user confirmation first. "
                "The confirmation is automatic — you do not need to call request_confirmation separately."
            ),
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },

    # SHELL

    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Run a shell command in the project directory.\n\n"
                "Use for: pytest, ruff, mypy, pip install, npm run, git, cargo, make.\n"
                "Destructive commands (rm, DROP TABLE, etc.) automatically ask for confirmation.\n"
                "Do not use for file manipulation — use the file tools.\n\n"
                "NEVER use interactive scaffolding commands (npm create, create-react-app, etc.) "
                "— they prompt for input and will hang. Write config files directly instead.\n\n"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "E.g. 'pytest tests/ -x -q', 'git status'."},
                    "working_dir": {"type": "string", "default": "."},
                    "timeout": {"type": "integer", "default": 60},
                },
                "required": ["command"],
            },
        },
    },

    #  MEMORY

    {
        "type": "function",
        "function": {
            "name": "update_project_context",
            "description": (
                "Save what you learned into persistent memory that survives context trimming.\n\n"
                "WHEN: Immediately after read_file, read_file_range, OR write_file.\n"
                "Do NOT wait until the end of a task — do it right after each file operation.\n\n"
                "NEVER store line numbers (they go stale after edits).\n\n"
                "After this call, the file path appears in <project_context>. "
                "You MUST NOT call read_file on it again — use search_files + read_file_range.\n\n"
                "Example:\n"
                "  file_summaries: {'src/auth.py': 'JWT: login, logout, verify_token. Uses PyJWT.'}\n"
                "  symbols: {'verify_token': 'auth.py — validates JWT, raises AuthError, returns User'}\n"
                "  facts: {'token_header': 'Bearer in Authorization, extracted by middleware'}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_summaries": {
                        "type": "object",
                        "description": "{path: one-line summary of what the file owns and exports}",
                        "additionalProperties": {"type": "string"},
                    },
                    "symbols": {
                        "type": "object",
                        "description": "{name: 'filename — what it does'}. No line numbers.",
                        "additionalProperties": {"type": "string"},
                    },
                    "facts": {
                        "type": "object",
                        "description": "{key: stable convention, state shape, or architectural fact}",
                        "additionalProperties": {"type": "string"},
                    },
                },
                "required": [],
            },
        },
    },
]