OPENAI_TOOLS_LIST = [

    # Metadata
    {
        "type": "function",
        "function": {
            "name": "get_file_info",
            "description": (
                "Get metadata (size, modified time, type) for a file or directory. "
                "Use to check if a path exists before creating it, or to get file size "
                "before deciding whether read_file is safe."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path to the file or directory."},
                },
                "required": ["file_path"],
            },
        },
    },

    # Read
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the ENTIRE content of a file.\n\n"
                "ONLY call this when ALL of the following are true:\n"
                "  1. The file does NOT appear in <project_context>.\n"
                "  2. You cannot find what you need with search_files.\n"
                "  3. The file is small (check with get_file_info first if unsure).\n\n"
                "NEVER call this if the file path is already in <project_context> — "
                "use search_files + read_file_range instead.\n\n"
                "After calling read_file, you MUST immediately call update_project_context "
                "to record what you learned. Do not proceed to any other step first."
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
                "Read a specific line range from a file (1-indexed, inclusive).\n\n"
                "PRECONDITION: You MUST have exact line numbers from search_files or "
                "find_symbol before calling this. NEVER guess start_line or end_line.\n\n"
                "Use this instead of read_file whenever you already know roughly where "
                "the code you need is located."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path to the file."},
                    "start_line": {"type": "integer", "description": "First line to read (1-indexed). Must come from search_files output."},
                    "end_line": {"type": "integer", "description": "Last line to read (inclusive). Must come from search_files output."},
                },
                "required": ["file_path", "start_line", "end_line"],
            },
        },
    },

    # Write / create
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write full content to a file, creating it (and parent directories) if needed.\n\n"
                "ONLY use this to CREATE a new file that does not exist yet.\n\n"
                "NEVER use this to modify a file that already exists — it silently overwrites "
                "the ENTIRE file. For existing files, use replace_in_file, apply_patch, or "
                "patch_file_lines."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path. Must NOT already exist."},
                    "content": {"type": "string", "description": "Full content to write."},
                },
                "required": ["file_path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create an empty file and any needed parent directories. Use when you need the path to exist before writing to it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path to create."},
                },
                "required": ["file_path"],
            },
        },
    },

    # Edit
    {
        "type": "function",
        "function": {
            "name": "replace_in_file",
            "description": (
                "Replace the FIRST occurrence of an exact string in a file.\n\n"
                "This is the PRIMARY tool for editing existing files.\n\n"
                "Rules:\n"
                "  - search_text must be byte-for-byte identical to the file content "
                "(copy from read_file_range output, never type from memory)\n"
                "  - Include 2–3 lines of surrounding context to make search_text unique\n"
                "  - If the replacement fails, run search_files to get the current exact text\n\n"
                "Use apply_patch instead when you need to edit 3+ separate locations at once."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path to the file."},
                    "search_text": {"type": "string", "description": "Exact string to find. Must match file content exactly including whitespace and indentation."},
                    "replace_text": {"type": "string", "description": "String to replace it with."},
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
                "Replace an exact range of line numbers with new content.\n\n"
                "Use when you know the precise line range (from search_files) and "
                "want to replace it wholesale — faster than apply_patch for single-block "
                "replacements when you have exact line numbers.\n\n"
                "PRECONDITION: line numbers must come from search_files, never guessed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path to the file."},
                    "start_line": {"type": "integer", "description": "First line to replace (1-indexed). From search_files."},
                    "end_line": {"type": "integer", "description": "Last line to replace (inclusive). From search_files."},
                    "new_content": {"type": "string", "description": "Replacement text. Replaces lines start_line through end_line entirely."},
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
                "Apply a unified diff patch to a file.\n\n"
                "Use when you need to make 3+ separate changes to a file in one shot.\n"
                "For a single block change, prefer replace_in_file (simpler and safer).\n\n"
                "The patch must be standard unified diff format (diff -u / git diff).\n"
                "@@ line numbers must be EXACT — get them from search_files first.\n"
                "If the patch fails, the tool returns the current file content — "
                "use that exact content to rebuild the patch.\n\n"
                "Example format:\n"
                "--- a/src/main.py\n"
                "+++ b/src/main.py\n"
                "@@ -10,4 +10,5 @@\n"
                " existing line\n"
                "-old line\n"
                "+new line\n"
                " existing line\n"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path to the file to patch."},
                    "patch": {"type": "string", "description": "Unified diff patch string. @@ numbers must be exact."},
                },
                "required": ["file_path", "patch"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_diff",
            "description": "Preview a unified diff between the current file content and proposed new content. Use to verify what will change before committing a write_file call on a new file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path to the file."},
                    "new_content": {"type": "string", "description": "Proposed new file content."},
                },
                "required": ["file_path", "new_content"],
            },
        },
    },

    # Directory
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Create a directory and all needed parent directories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dir_path": {"type": "string", "description": "Relative path to the directory."},
                },
                "required": ["dir_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files matching a glob pattern. Use directory_tree for structure overview; use list_files when you need a flat list to iterate over.",
            "parameters": {
                "type": "object",
                "properties": {
                    "glob_pattern": {
                        "type": "string",
                        "description": "Glob pattern (e.g. '**/*.py', 'src/**/*.ts'). Default: '**/*'.",
                        "default": "**/*",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of files to return. Default: 200.",
                        "default": 200,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "directory_tree",
            "description": "Show an ASCII tree of a directory (like the `tree` command). Best first call for understanding a new project's layout.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dir_path": {
                        "type": "string",
                        "description": "Relative path to the directory. Default: project root ('.').",
                        "default": ".",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum recursion depth. Default: 4.",
                        "default": 4,
                    },
                },
                "required": [],
            },
        },
    },

    # File management
    {
        "type": "function",
        "function": {
            "name": "copy_file",
            "description": "Copy a file to a new path. Useful for creating a file from a template.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_path": {"type": "string", "description": "Relative source path."},
                    "destination_path": {"type": "string", "description": "Relative destination path."},
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
                    "old_path": {"type": "string", "description": "Current relative path."},
                    "new_path": {"type": "string", "description": "New relative path."},
                },
                "required": ["old_path", "new_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_path",
            "description": "Delete a file or directory (recursively if directory). Irreversible — confirm the path before calling.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to delete."},
                },
                "required": ["path"],
            },
        },
    },

    # Search
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": (
                "Grep-style regex search across project files with surrounding context.\n\n"
                "This is your FIRST tool for any editing task — use it to get exact "
                "line numbers before calling read_file_range, replace_in_file, or apply_patch.\n\n"
                "Returns line numbers, column, matched text, and context lines. "
                "Use these line numbers directly — do not add or subtract offsets.\n\n"
                "Tips:\n"
                "  - Use file_glob to narrow the search: '**/*.py', 'src/**/*.ts'\n"
                "  - Increase context_lines (3–5) to get enough context for replace_in_file\n"
                "  - Search for error message strings to locate where they're raised"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Python regex pattern. E.g. 'def train\\\\b', 'class Auth', 'TODO'.",
                    },
                    "file_glob": {
                        "type": "string",
                        "description": "Glob to restrict search (e.g. '**/*.py'). Default: '**/*'.",
                        "default": "**/*",
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Whether the search is case-sensitive. Default: false.",
                        "default": False,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max matches to return. Default: 50.",
                        "default": 50,
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "Lines of context around each match. Default: 2. Use 4–5 when you need context for replace_in_file.",
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
                "Use this as your first step when you know the name of what you want to change. "
                "Returns which file it lives in and the line numbers — then use read_file_range "
                "to see the full definition, and replace_in_file to edit it.\n\n"
                "Examples: find_symbol('CodingAgent'), find_symbol('MAX_RETRIES')"
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
                        "description": "Glob to restrict search. Default: '**/*' (all files).",
                        "default": "**/*",
                    },
                },
                "required": ["symbol"],
            },
        },
    },

    # Shell
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Run a shell command in the project directory.\n\n"
                "Use for: running tests (pytest -x -q), linting (ruff, mypy), "
                "installing packages (pip install), building (npm run build), git operations.\n\n"
                "Commands must start with an allowed prefix (python, pip, node, npm, git, "
                "pytest, ruff, mypy, cargo, make, etc.). Do not use for file manipulation — "
                "use the file tools instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command. E.g. 'pytest tests/ -x -q', 'git diff HEAD', 'ruff check src/'.",
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Subdirectory to run in (relative to project root). Default: '.'.",
                        "default": ".",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds. Default: 60.",
                        "default": 60,
                    },
                },
                "required": ["command"],
            },
        },
    },

    # ── Memory ────────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "update_project_context",
            "description": (
                "Save what you learned about this project into persistent memory.\n\n"
                "WHEN: Call this IMMEDIATELY after read_file or read_file_range on a file "
                "you have not read before. Do this before any other step.\n\n"
                "WHY: Once a file is recorded here, you MUST NOT read_file it again. "
                "The <project_context> block is shown to you at every turn — this is your "
                "memory. Everything you record here survives context trimming.\n\n"
                "WHAT to store:\n"
                "  file_summaries: what each file owns (exports, classes, key functions)\n"
                "  symbols:        what each key function/class does and where it lives\n"
                "  facts:          stable conventions (state shape, patterns, config)\n\n"
                "DO NOT store line numbers — they go stale after edits.\n\n"
                "Example:\n"
                "  file_summaries: {'src/auth.py': 'JWT auth: login, logout, verify_token'}\n"
                "  symbols: {'verify_token': 'auth.py — validates JWT, raises AuthError'}\n"
                "  facts: {'token_header': 'Bearer in Authorization, extracted by middleware'}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_summaries": {
                        "type": "object",
                        "description": "{path: one-line summary of what the file owns}",
                        "additionalProperties": {"type": "string"},
                    },
                    "symbols": {
                        "type": "object",
                        "description": "{name: 'filename — what it does, its role'}. No line numbers.",
                        "additionalProperties": {"type": "string"},
                    },
                    "facts": {
                        "type": "object",
                        "description": "{key: stable fact about state, conventions, or patterns}",
                        "additionalProperties": {"type": "string"},
                    },
                },
                "required": [],
            },
        },
    },
]