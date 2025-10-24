import os
import subprocess

def run_file(working_directory: str, file_path: str, args = None):
    absolute_working_directory = os.path.abspath(working_directory)

    if not os.path.isdir(absolute_working_directory):
        return f"Working directory '{working_directory}' does not exist."
    
    absolute_file_path = os.path.abspath(os.path.join(working_directory, file_path))

    if args is None:
        args = []

    if not absolute_file_path.startswith(absolute_working_directory):
        return f"Error: Access outside the working directory is denied."
    
    if not os.path.isfile(absolute_file_path):
        return f"Error: The file '{file_path}' is not a file."

    try:
        result = subprocess.run(
            ["python3", absolute_file_path] + args,
            capture_output=True,
            text=True,
            cwd=absolute_working_directory,
            timeout=30
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode
        }
    except Exception as e:
        return {"Error": e}

run_file_function = {
    "name": "run_file",
    "description": "Executes a Python file within the working directory.",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Relative path to the Python file to execute."
            },
            "args": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "Optional command line arguments passed to the file."
            }
        },
        "required": ["file_path"]
    }
}