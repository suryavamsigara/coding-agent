import os

def write_file(working_directory: str, file_path: str, content: str):
    print("Function call")
    absolute_working_directory = os.path.abspath(working_directory)

    if not os.path.isdir(absolute_working_directory):
        return f"Working directory '{working_directory}' does not exist."
    absolute_file_path = os.path.abspath(os.path.join(working_directory, file_path))

    if not absolute_file_path.startswith(absolute_working_directory):
        return f"Error: '{file_path}' does not exist or is not a file."
    
    os.makedirs(os.path.dirname(absolute_file_path), exist_ok=True)

    try:
        with open(absolute_file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to '{file_path}'"
    except Exception as e:
        return f"Failed to write to '{file_path}', {e}"

write_file_function = {
    "name": "write_file",
    "description": "Create a new file or overwrite an existing file with the specified content in the working directory. Can create required parent directories too.",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Relative path of the file to write."
            },
            "content": {
                "type": "string",
                "description": "The text content to write into the file."
            }
        },
        "required": ["file_path", "content"]
    },
}