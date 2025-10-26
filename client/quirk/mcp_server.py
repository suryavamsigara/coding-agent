import os
import subprocess
import shutil
import argparse
import uvicorn
from mcp.server.fastmcp import FastMCP
from quirk.config import get_working_directory

mcp = FastMCP("Quirk Tools")

@mcp.tool()
def get_file_info(directory: str = "."):
    """List all files and directories recursively starting from a given directory."""
    absolute_working_directory = get_working_directory()
    absolute_directory = os.path.abspath(os.path.join(absolute_working_directory, directory))
    working_directory = os.path.dirname(absolute_working_directory)

    if not os.path.isdir(absolute_working_directory):
        return f"Error: Working directory '{working_directory}' does not exist."

    if not absolute_directory.startswith(absolute_working_directory):
        return f"Error: Directory '{directory}' is not in working directory."
    
    if not os.path.isdir(absolute_directory):
        return f"Error: Directory '{directory}' does not exist"
    
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

    return {"directories": dir_paths, "files": file_paths}


@mcp.tool()
def read_file(file_path: str, max_lines: int | None = None):
    """Reads the contents of a specified file. Can optionally read only the first N lines"""
    absolute_working_directory = get_working_directory()
    working_directory = os.path.dirname(absolute_working_directory)

    if not os.path.isdir(absolute_working_directory):
        return f"Working directory '{working_directory}' does not exist."
    
    absolute_file_path = os.path.join(absolute_working_directory, file_path)

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
    

@mcp.tool()
def write_file(file_path: str, content: str):
    """Create a new file or overwrite an existing file with the specified content in the working directory. Can create required parent directories too."""
    absolute_working_directory = get_working_directory()

    if not os.path.isdir(absolute_working_directory):
        return f"Working directory '{working_directory}' does not exist."
    
    working_directory = os.path.dirname(absolute_working_directory)
    absolute_file_path = os.path.join(absolute_working_directory, file_path)

    if not absolute_file_path.startswith(absolute_working_directory):
        return f"Error: '{file_path}' does not exist or is not a file."
    
    os.makedirs(os.path.dirname(absolute_file_path), exist_ok=True)

    try:
        with open(absolute_file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to '{file_path}'"
    except Exception as e:
        return f"Failed to write to '{file_path}', {e}"


@mcp.tool()
def run_file(file_path: str, args = None):
    """Executes a Python file within the working directory."""
    absolute_working_directory = get_working_directory()
    working_directory = os.path.dirname(absolute_working_directory)

    if not os.path.isdir(absolute_working_directory):
        return f"Working directory '{working_directory}' does not exist."
    
    absolute_file_path = os.path.join(absolute_working_directory, file_path)

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


@mcp.tool()
def delete_path(path: str):
    """Delete a file or directory."""
    absolute_working_directory = get_working_directory()
    working_directory = os.path.dirname(absolute_working_directory)

    if not os.path.isdir(absolute_working_directory):
        return f"Error: Working directory '{working_directory}' does not exist."
    
    absolute_path = os.path.join(absolute_working_directory, path)

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
    

@mcp.tool()
def copy_file(source: str, destination: str):
    """Delete a file or directory."""
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
    

def create_app():
    return mcp.sse_app()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.transport == "sse":
        app = create_app()
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    else:
        mcp.run(transport="stdio")
