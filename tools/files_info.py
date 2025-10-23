import os

def get_file_info(working_directory: str, directory: str = "."):
    absolute_working_directory = os.path.abspath(working_directory)
    absolute_directory = os.path.abspath(os.path.join(absolute_working_directory, directory))

    if not os.path.isdir(absolute_working_directory):
        return f"Error: Working directory '{working_directory}' does not exist."

    if not absolute_directory.startswith(absolute_working_directory):
        return f"Error: Directory '{directory}' is not in working directory."
    
    if not os.path.isdir(absolute_directory):
        return f"Error: Directory {directory} does not exist"
    
    file_paths = []
    dir_paths = []
    
    for root, dirs, files in os.walk(absolute_directory):
        relative_root = os.path.relpath(root, absolute_directory)

        for file in files:
            if relative_root == ".":
                file_paths.append(file)
            else:
                file_paths.append(os.path.join(relative_root, file))
        
        for dir_name in dirs:
            if relative_root == ".":
                dir_paths.append(dir_name)
            else:
                dir_paths.append(os.path.join(relative_root, dir_name))

    return {"directories":dir_paths, "files":file_paths}

get_file_info_function = {
    "name": "get_file_info",
    "description": "Lists all files and directories recursively starting from a given directory.",
    "parameters": {
        "type": "object",
        "properties": {
            "directory": {
                "type": "string",
                "description": "The directory to list files from, relative to the working directory. Use '.' for the current working directory.",
            }
        },
        "required": ["directory"]
    }
}