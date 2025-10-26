import os
import shutil
from ....app.config import get_working_directory

def copy_file(source: str, destination: str):
    absolute_working_directory = get_working_directory()
    working_directory = os.path.dirname(absolute_working_directory)

    if not os.path.isdir(absolute_working_directory):
        return f"Working directory '{working_directory}' does not exist."
    
    absolute_source_path = os.path.join(absolute_working_directory, source)
    absolute_destination_path = os.path.join(absolute_working_directory, destination)

    if not absolute_source_path.startswith(absolute_working_directory) or not absolute_destination_path.startswith(absolute_working_directory):
        return f"Error: Access outside the working directory is denied."
    
    if not os.path.isfile(absolute_source_path):
        return f"Error: '{source}' does not exist or is not a file."
    
    try:    
        if os.path.isdir(absolute_destination_path):
            shutil.copy(absolute_source_path, absolute_destination_path)
            return f"Successfully copied '{source}' into directory '{destination}'."
        else:
            os.makedirs(os.path.dirname(absolute_destination_path), exist_ok=True)
            shutil.copy(absolute_source_path, absolute_destination_path)
            return f"Copied '{source}' to '{destination}'."
    except Exception as e:
        return f"Error: Could not copy the file: {e}"
    
copy_file_function = {
    "name": "copy_file",
    "description": "Copies a file from source to destination within the working directory. Creates parent directories if needed.",
    "parameters": {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "Relative path of the source file to copy.",
            },
            "destination": {
                "type": "string",
                "description": "Relative path where the file should be copied to. Can be a file path or a directory path."
            }
        },
        "required": ["source", "destination"]
    }
}
