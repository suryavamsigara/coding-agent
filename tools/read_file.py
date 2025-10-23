import os

def read_file(working_directory: str, file_path: str, max_lines: int | None = None):
    absolute_working_directory = os.path.abspath(working_directory)

    if not os.path.isdir(absolute_working_directory):
        return f"Working directory '{working_directory}' does not exist."
    
    absolute_file_path = os.path.abspath(os.path.join(working_directory, file_path))

    if not absolute_file_path.startswith(absolute_working_directory):
        return f"File '{file_path}' is not in working directory."

    if not os.path.isfile(absolute_file_path):
        return f"Error: '{file_path}' does not exist or is not a file."

    try:
        with open(absolute_file_path, 'r', encoding='utf-8') as f:
            if max_lines is not None and max_lines > 0:
                lines = []
                truncated = False
                for i, line in enumerate(f):
                    if i >= max_lines:
                        truncated = True
                        break
                    lines.append(line)
                file_content = "".join(lines)
                if truncated:
                    file_content += f"\n File truncated at {max_lines} lines"
            else:
                file_content = f.read()
        return file_content

    except Exception as e:
        return f"Error: could not read file '{file_path}', details: {e}"
        
read_file_function = {
    "name": "read_file",
    "description": "Reads the contents of a specified text file. Can optionally read only the first N lines.",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The relative path to the file from the working directory.",
            },
            "max_lines": {
                "type": "integer",
                "description": "Optional. The maximum number of lines to read from the start of the file. If omitted, the entire file is read.",
            }
        },
        "required": ["file_path"]
    }
}