OPENAI_TOOLS_LIST = [
    # ────────────────────────────────────────────
    #  File metadata
    # ────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_file_info",
            "description": "Get metadata about a file or directory: size, modification time, type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path to the file or directory."}
                },
                "required": ["file_path"],
            },
        },
    },

    # ────────────────────────────────────────────
    #  Read
    # ────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the full contents of a text file. "
                "Use read_file_range instead when you only need part of a large file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path to the file."}
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file_range",
            "description": "Read a specific line range from a file (1-indexed, inclusive). Prefer this over read_file for large files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path to the file."},
                    "start_line": {"type": "integer", "description": "First line to read (1-indexed)."},
                    "end_line": {"type": "integer", "description": "Last line to read (inclusive)."},
                },
                "required": ["file_path", "start_line", "end_line"],
            },
        },
    },

    # ────────────────────────────────────────────
    #  Write / edit
    # ────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write (overwrite or create) a file with the given content. "
                "Use for new files or when replacing the entire content. "
                "Prefer replace_in_file or apply_patch for surgical edits."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path to the file."},
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
            "description": "Create an empty file (and parent directories). Use before write_file if the path might not exist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path to create."}
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "replace_in_file",
            "description": (
                "Replace the FIRST occurrence of an exact string in a file. "
                "Best for surgical edits (renaming a function, changing a constant, etc.). "
                "search_text must exactly match the file content including whitespace. "
                "Read the file first if unsure of exact content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path to the file."},
                    "search_text": {"type": "string", "description": "Exact string to find. Must match file content exactly."},
                    "replace_text": {"type": "string", "description": "String to replace it with."},
                },
                "required": ["file_path", "search_text", "replace_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_patch",
            "description": (
                "Apply a unified diff patch to a file. "
                "Use when you need to apply multiple changes at different locations in one shot. "
                "The patch must be in standard unified diff format (diff -u / git diff). "
                "Example:\n"
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
                    "patch": {"type": "string", "description": "Unified diff patch content."},
                },
                "required": ["file_path", "patch"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_diff",
            "description": "Preview a unified diff between the current file content and a proposed new content. Use before write_file to confirm what will change.",
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

    # ────────────────────────────────────────────
    #  Directory
    # ────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Create a directory and all needed parent directories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dir_path": {"type": "string", "description": "Relative path to the directory."}
                },
                "required": ["dir_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files matching a glob pattern in the working directory. Default lists all files.",
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
            "description": "Show an ASCII tree of a directory (like the `tree` command). Good for understanding project structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dir_path": {
                        "type": "string",
                        "description": "Relative path to the directory. Default: project root.",
                        "default": ".",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum depth to recurse. Default: 4.",
                        "default": 4,
                    },
                },
                "required": [],
            },
        },
    },

    # ────────────────────────────────────────────
    #  File management
    # ────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "copy_file",
            "description": "Copy a file to a new path.",
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
            "description": "Delete a file or directory (recursively). Use with care.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to delete."}
                },
                "required": ["path"],
            },
        },
    },

    # ────────────────────────────────────────────
    #  Search
    # ────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": (
                "Grep-style regex search across all project files. "
                "Returns matches with surrounding context lines. "
                "Use to find usages, error messages, TODOs, or any pattern in the codebase. "
                "Supports file glob filtering (e.g. only search Python files)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Python regex pattern to search for. E.g. 'def train\\b', 'TODO', 'import torch'.",
                    },
                    "file_glob": {
                        "type": "string",
                        "description": "Glob to restrict which files are searched (e.g. '**/*.py', '**/*.ts'). Default: '**/*'.",
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
                        "description": "Number of lines of context around each match. Default: 2.",
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
                "Find where a function, class, or variable is defined or used in the codebase. "
                "E.g. find_symbol('CodingAgent') finds its definition and references."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Name of the function, class, or variable to find.",
                    },
                    "file_glob": {
                        "type": "string",
                        "description": "Glob to restrict search (default: '**/*.py').",
                        "default": "**/*.py",
                    },
                },
                "required": ["symbol"],
            },
        },
    },

    # ────────────────────────────────────────────
    #  Shell
    # ────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Run a shell command in the project directory. "
                "Use for: running tests (pytest), linting (ruff, mypy), installing packages (pip install), "
                "building projects (npm run build), running scripts, git operations. "
                "Commands must start with an allowed prefix. Avoid destructive operations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to run. E.g. 'pytest tests/ -v', 'npm run build', 'git status'.",
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Subdirectory to run the command in (relative to project root). Default: '.' (project root).",
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
]