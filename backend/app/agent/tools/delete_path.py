import os
import shutil

def delete_path(working_directory: str, path: str):
    absolute_working_directory = os.path.abspath(working_directory)

    if not os.path.isdir(absolute_working_directory):
        return f"Error: Working directory '{working_directory}' does not exist."
    
    absolute_path = os.path.abspath(os.path.join(working_directory, path))

    if not absolute_path.startswith(absolute_working_directory):
        return f"Error: '{path}' is not in working directory"
    
    if not os.path.exists(absolute_path):
        return f"Error: '{path}' does not exist."
    
    try:
        if os.path.isfile(absolute_path):
            os.remove(absolute_path)
            return f"Successfully deleted the file '{path}'"
        elif os.path.isdir(absolute_path):
            shutil.rmtree(absolute_path)
            return f"Successfully deleted the directory '{path}'"
    except Exception as e:
        return f"Error: Could not delete '{path}' - {e}"

delete_path_function = {
    "name": "delete_path",
    "description": "Deletes a specified file or directory from the working directory.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The relative path to the file or directory to delete."
            },
        },
        "required": ["path"]
    }
}

