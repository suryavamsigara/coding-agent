import os
import subprocess
import shutil
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from quirk.config import get_working_directory

mcp = FastMCP("Quirk Tools", host="127.0.0.1", port=9000)

EXCLUDE_DIRS = {"venv", ".venv", "env", "node_modukles", ".git", "__pycache__"}

@mcp.tool()
def get_file_info(directory: str = "."):
    """
    Return recursive directory and file info relative to the working directory. (skips dev/system dirs).
    """
    working_dir: Path = get_working_directory()
    target_dir: Path = (working_dir / directory).resolve()

    if not target_dir.relative_to(working_dir):
        return {"error": f"Directory '{directory}' is outside working directory."}
    
    if not target_dir.exists():
        return {"error": f"Directory '{directory}' doesn't exist"}
    
    if not target_dir.is_dir():
        return {"error": f"'{directory}' is not a directory."}
    
    directories = []
    files = []
    
    for path in target_dir.rglob("*"):
        rel = path.relative_to(target_dir)

        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue

        if path.is_file():
            files.append(str(rel))
        elif path.is_dir():
            directories.append(str(rel))

    return {"directories": sorted(directories), "files": sorted(files)}


@mcp.tool()
def create_file(file_path: str):
    """
    Creates a new, empty file. Automatically creates needed parent folders.
    """
    base_dir: Path = get_working_directory()

    if not base_dir.is_dir():
        return f"Error: Working dir '{base_dir}' doesn't exist."
    
    target_path: Path = (base_dir / file_path).resolve()

    if not target_path.is_relative_to(base_dir):
        return f"Error: '{file_path}' is outside the working directory."
    
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.touch()

        return f"Successfully created empty file '{file_path}'"
    except Exception as e:
        return f"Error: Failed to create '{file_path}': {e}"
    

@mcp.tool()
def create_directory(path: str):
    """Create a directory (including parents)."""
    base_dir: Path = get_working_directory()
    if not base_dir.is_dir():
        return f"Error: Working dir '{base_dir}' doesn't exist."
    
    target_dir: Path = (base_dir / path).resolve()

    if not target_dir.is_relative_to(base_dir):
        return f"Error: '{path}' is outside working directory."
    
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        return f"Directory created: {path}"
    except Exception as e:
        return f"Error creating directory '{path}': {e}"


@mcp.tool()
def read_file(file_path: str, max_lines: int | None = None):
    """
    Reads the contents of a specified file. Can optionally read only the first N lines
    """
    
    base_dir: Path = get_working_directory()

    if not base_dir.is_dir():
        return f"Error: Working dir '{base_dir}' doesn't exist."
    
    target_path: Path = (base_dir / file_path).resolve()

    if not target_path.is_relative_to(base_dir):
        return f"Error: File '{file_path}' is outside the working directory."
    
    if not target_path.is_file():
        return f"Error: '{file_path}' does not exist or is not a file."

    try:
        text = []
        with target_path.open("r", encoding="utf-8") as f:
            if max_lines and max_lines > 0:
                for i, line in enumerate(f):
                    if i >= max_lines:
                        text.append(f"\nFile truncated at {max_lines} lines")
                        break
                    text.append(line)
                return "".join(text)
            else:
                return f.read()
    except Exception as e:
        return f"Error reading file '{file_path}': {e}"


@mcp.tool()
def write_file(file_path: str, content: str):
    """
    Create a new file and write or overwrite an existing file with the specified content inside the working directory. Automatically creates needed parent folders.
    """
    base_dir: Path = get_working_directory()

    if not base_dir.is_dir():
        return f"Error: Working directory '{base_dir}' does not exist."
    
    target_path: Path = (base_dir / file_path).resolve()

    if not target_path.is_relative_to(base_dir):
        return f"Error: '{file_path} is outside the working directory."
    
    target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        target_path.write_text(content, encoding="utf-8")
        return f"Successfully wrote to '{file_path}'"
    except Exception as e:
        return f"Failed to write to '{file_path}': {e}"


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
    """
    Delete a file or directory inside the working directory.
    """
    base_dir: Path = get_working_directory()

    if not base_dir.is_dir():
        return f"Error: Working directory '{base_dir}' does not exist."
    
    target_path: Path = (base_dir / path).resolve()

    if not target_path.is_relative_to(base_dir):
        return f"Error: '{path}' is outside the working directory."
    
    if not target_path.exists():
        return f"Error: '{path}' does not exist."
    
    try:
        if target_path.is_file():
            target_path.unlink()
            return f"Successfully deleted file '{path}'"
        elif target_path.is_dir():
            shutil.rmtree(target_path)
            return f"Successfully deleted directory '{path}'"
        else:
            return f"Error: Unknown file type for '{path}'"
    except Exception as e:
        return f"Error: Could not delete '{path}': {e}"
    

@mcp.tool()
def copy_file(source: str, destination: str):
    """Copy a file or directory inside the working directory."""
    base_dir: Path = get_working_directory()
    src_path: Path = (base_dir / source).resolve()
    dest_path: Path = (base_dir / destination).resolve()
    
    if not src_path.is_relative_to(base_dir):
        return f"Error: '{source}' is outside the working directory."
    if not dest_path.is_relative_to(base_dir):
        return f"Error: '{destination}' is outside the working directory."
    
    if not src_path.exists():
        return f"Error: Source '{source}' doesn't exist."
    
    try:    
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        if src_path.is_file():
            shutil.copy2(src_path, dest_path)
        else:
            shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
        return f"Copied '{source}' to '{destination}'"
    except Exception as e:
        return f"Error: Could not copy the file: {e}"
    
@mcp.tool()
def rename_path(old_path: str, new_path: str):
    """
    Rename or move a file/directory within working directory.
    """
    base_dir: Path = get_working_directory()
    old: Path = (base_dir / old_path).resolve()
    new: Path = (base_dir / new_path).resolve()
    
    if not old.is_relative_to(base_dir):
        return f"Error: '{old_path}' is outside the working directory."
    if not new.is_relative_to(base_dir):
        return f"Error: '{new_path}' is outside the working directory."
    
    if not old.exists():
        return f"Error: '{old_path}' doesn't exist."
    
    new.parent.mkdir(parents=True, exist_ok=True)

    try:
        old.rename(new)
        return f"Renamed/moved '{old_path}' to '{new_path}'"
    except Exception as e:
        return f"Error: Rename/move failed: {e}"

if __name__=="__main__":
    mcp.run(transport="streamable-http")
