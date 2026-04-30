OPENAI_TOOLS_LIST = [
    {
        "type": "function",
        "function": {
            "name": "get_file_info",
            "description": "Return recursive directory and file info relative to the working directory. Skips dev/system dirs like venv or .git.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "The directory to inspect, relative to the working directory. Defaults to '.' (the root working directory)."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Creates a new, empty file. Automatically creates needed parent folders.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The path and name of the file to create, relative to the working directory."
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Create a directory (including parent directories if they don't exist).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path of the directory to create, relative to the working directory."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads the contents of a specified file. Can optionally read only the first N lines.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The path to the file to read, relative to the working directory."
                    },
                    "max_lines": {
                        "type": "integer",
                        "description": "Optional limit on the number of lines to read. Useful for inspecting large files."
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create a new file and write or overwrite an existing file with the specified content inside the working directory. Automatically creates needed parent folders.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The path to the file to write to, relative to the working directory."
                    },
                    "content": {
                        "type": "string",
                        "description": "The complete text or code to write into the file."
                    }
                },
                "required": ["file_path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_path",
            "description": "Delete a file or directory inside the working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path to the file or directory to delete, relative to the working directory."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "copy_file",
            "description": "Copy a file or directory inside the working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "The path of the source file or directory to copy."
                    },
                    "destination": {
                        "type": "string",
                        "description": "The destination path where the copy should be placed."
                    }
                },
                "required": ["source", "destination"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rename_path",
            "description": "Rename or move a file/directory within the working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "old_path": {
                        "type": "string",
                        "description": "The current path of the file or directory."
                    },
                    "new_path": {
                        "type": "string",
                        "description": "The new path or name for the file or directory."
                    }
                },
                "required": ["old_path", "new_path"]
            }
        }
    }
]