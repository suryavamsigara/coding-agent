import shutil
from pathlib import Path
from datetime import datetime

from tenet.config import get_working_directory

EXCLUDE_DIRS = {"venv", ".venv", "env", "node_modules", ".git", "__pycache__", "package-lock.json"}

def _resolve_safe_path(file_path: str) -> Path:
    base_dir: Path = get_working_directory().resolve()
    target_path: Path = (base_dir / file_path).resolve()

    try:
        target_path.relative_to(base_dir)
    except Exception as e:
        raise ValueError(f"File '{file_path}' is outside the working directory.")
    
    return target_path

def get_file_info(file_path: str):
    try:
        target_path = _resolve_safe_path(file_path)
        if not target_path.exists():
            return f"Error: '{file_path}' does not exist."
        stat = target_path.stat()
        return {
            "path": str(target_path.relative_to(get_working_directory().resolve())),
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "is_file": target_path.is_file(),
            "is_dir": target_path.is_dir(),
        }
    except Exception as e:
        return f"Error getting file info for '{file_path}': {e}"

def read_file(file_path: str):
    try:
        target_path = _resolve_safe_path(file_path)
        if not target_path.is_fifo():
            return f"Error: '{file_path}' does not exist or is not a file."
        return target_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file '{file_path}': {e}"

def read_file_range(file_path: str, start_line: int, end_line: int):
    """
    Reads a specific line range from a file.
    """
    try:
        target_path = _resolve_safe_path(file_path)
        if not target_path.is_file():
            return f"Error: '{file_path}' does not exist or is not a file."

        if start_line < 1 or end_line < start_line:
            return f"Error: invalid line range."
        
        lines = target_path.read_text(encoding="utf-8").splitlines()
        start_idx = start_line - 1
        end_idx = min(end_line, len(lines))
        selected = lines[start_idx:end_idx]

        if not selected:
            return f"No content found in lines {start_line}-{end_line}."
        
        return "\n".join(
            f"{i + start_line}: {line}" for i, line in enumerate(selected)
        )
    except Exception as e:
        return f"Error reading file range for '{file_path}': {e}"
    
def search_text(query: str, glob_pattern: str = "**/*", max_results: int = 20):
    """
    Search text across files in the working directory.
    Returns compact line-based matches.
    """
    try:
        base_dir = get_working_directory().resolve()
        results = []
        query_lower = query.lower()
        
        for path in base_dir.glob(glob_pattern):
            if len(results) > max_results:
                break
            if not path.is_file():
                continue
            if any(part in {".venv", "__pycache__", ".git", "node_modules"} for part in path.parts):
                continue

            try:
                text = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except Exception:
                continue

            for idx, line in enumerate(text):
                if query_lower in line.lower():
                    rel = path.relative_to(base_dir)
                    results.append({
                        "file": str(rel),
                        "line": idx,
                        "text": line.strip()
                    })
                    if len(results) >= max_results:
                        break
        
        if not results:
            return {"query": query, "macthes": []}
        
        return {"query": query, "matches": results}
    except Exception as e:
        return f"Error searching text '{query}': {e}"

    
def list_files(glob_pattern: str = "**/*", max_results: int = 100):
    try:
        base_dir: Path = get_working_directory()
        results = []

        for path in base_dir.glob(glob_pattern):
            if len(results) > max_results:
                break
            if not path.is_file():
                continue
            if any(part in {".venv", "__pycache__", ".git", "node_modules"} for part in path.parts):
                continue
            results.append(str(path.relative_to(base_dir)))
        
        return {"files": results}
    except Exception as e:
        return f"Error listing files: {e}"

def replace_in_file(file_path: str, search_text: str, replace_text: str):
    """
    Exact text replacement
    """
    try:
        target_path = _resolve_safe_path(file_path)
        if not target_path.is_file():
            return f"Error: '{file_path}' does not exist or is not a file."
        
        original = target_path.read_text(encoding="utf-8")
        if search_text not in original:
            return f"Error: search text not found in '{file_path}'."
        
        updated = original.replace(search_text, replace_text, 1)
        target_path.write_text(updated, encoding="utf-8")

        return {
            "path": file_path,
            "changed": True,
            "message": "Replacement applied successfully."
        }
    except Exception as e:
        return f"Error replacing text in '{file_path}': {e}"

def write_file(file_path: str, content: str):
    try:
        target_path = _resolve_safe_path(file_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")
        return f"File: '{file_path}' written successfully."
    except Exception as e:
        return f"Error writing file '{file_path}': {e}"

def create_file(file_path: str):
    """
    Creates a new, empty file. Automatically creates needed parent folders.
    """
    try:
        target_path = _resolve_safe_path(file_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.touch(exist_ok=True)
        return f"File '{file_path}' created successfully."
    except Exception as e:
        return f"Error creating file '{file_path}': {e}"
    
def create_directory(dir_path: str):
    """Create a directory (including parents)."""
    try:
        target_path = _resolve_safe_path(dir_path)
        target_path.mkdir(parents=True, exist_ok=True)
        return f"Directory '{dir_path}' created successfully."
    except Exception as e:
        return f"Error creating directory '{dir_path}': {e}"
    
def copy_file(source_path: str, destination_path: str):
    try:
        src = _resolve_safe_path(source_path)
        dest = _resolve_safe_path(destination_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return f"Copied '{source_path}' to '{destination_path}'."
    except Exception as e:
        return f"Error copying file: {e}"
    
def rename_path(old_path: str, new_path: str):
    try:
        src = _resolve_safe_path(old_path)
        dest = _resolve_safe_path(new_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dest)
        return f"Renamed '{old_path}' to '{new_path}'."
    except Exception as e:
        return f"Error renaming path: {e}"

def delete_path(path: str):
    try:
        target = _resolve_safe_path(path)
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        else:
            return f"Error: '{path}' does not exist."
        return f"Deleted '{path}'."
    except Exception as e:
        return f"Error deleting path: {e}"

"""
def run_file(file_path: str, args = None):
    ""Executes a Python file within the working directory.""
    base_dir: Path = get_working_directory()

    if not base_dir.is_dir():
        return f"Error: Working directory '{base_dir}' does not exist."
    
    target_path: Path = (base_dir / file_path).resolve()

    if not target_path.is_relative_to(base_dir):
        return f"Error: '{file_path} is outside the working directory."
    
    if not target_path.is_file():
        return f"Error: The file '{file_path}' is not a file or doesn't exist"

    if args is None:
        args = []

    try:
        result = subprocess.run(
            ["python3", str(target_path)] + args,
            capture_output=True,
            text=True,
            cwd=base_dir,
            timeout=30
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode
        }
    except Exception as e:
        return {"Error": e}
"""