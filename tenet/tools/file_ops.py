import os
import re
import shutil
import difflib
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Union

from tenet.config import get_working_directory

EXCLUDE_DIRS = {"venv", ".venv", "env", "node_modules", ".git", "__pycache__", "dist", "build", ".mypy_cache", ".pytest_cache"}
EXCLUDE_FILES = {"package-lock.json", "yarn.lock", "poetry.lock", ".DS_Store"}

def _resolve_safe_path(file_path: str) -> Path:
    base_dir: Path = get_working_directory().resolve()
    target_path: Path = (base_dir / file_path).resolve()
    try:
        target_path.relative_to(base_dir)
    except Exception:
        raise ValueError(f"Path '{file_path}' is outside the working directory.")
    return target_path

def get_file_info(file_path: str) -> Union[dict, str]:
    """Return metadata about a file or directory."""
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
            "extension": target_path.suffix if target_path.is_file() else None,
        }
    except Exception as e:
        return f"Error getting file info for '{file_path}': {e}"

def read_file(file_path: str) -> str:
    """Read the full contents of a text file."""
    try:
        target_path = _resolve_safe_path(file_path)
        if not target_path.is_file():
            return f"Error: '{file_path}' does not exist or is not a file."
        return target_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file '{file_path}': {e}"

def read_file_range(file_path: str, start_line: int, end_line: int) -> str:
    """Read a specific line range from a file (1-indexed, inclusive)."""
    try:
        target_path = _resolve_safe_path(file_path)
        if not target_path.is_file():
            return f"Error: '{file_path}' does not exist or is not a file."
        if start_line < 1 or end_line < start_line:
            return "Error: invalid line range — start_line must be >= 1 and <= end_line."
        lines = target_path.read_text(encoding="utf-8").splitlines()
        selected = lines[start_line - 1 : end_line]
        if not selected:
            return f"No content in lines {start_line}–{end_line} (file has {len(lines)} lines)."
        return "\n".join(f"{i + start_line}: {line}" for i, line in enumerate(selected))
    except Exception as e:
        return f"Error reading file range for '{file_path}': {e}"

def write_file(file_path: str, content: str) -> str:
    """Overwrite (or create) a file with the given content."""
    try:
        target_path = _resolve_safe_path(file_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")
        return f"File '{file_path}' written successfully ({len(content)} bytes)."
    except Exception as e:
        return f"Error writing file '{file_path}': {e}"


def create_file(file_path: str) -> str:
    """Create an empty file, making parent directories as needed."""
    try:
        target_path = _resolve_safe_path(file_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.touch(exist_ok=True)
        return f"File '{file_path}' created successfully."
    except Exception as e:
        return f"Error creating file '{file_path}': {e}"

def replace_in_file(file_path: str, search_text: str, replace_text: str) -> Union[dict, str]:
    """
    Exact string replacement - replaces the FIRST occurrence only.
    Use this for surgical edits. search_text must match the file exactly (including whitespace/indentation).
    Returns an error if search_text is not found.
    """
    try:
        target_path = _resolve_safe_path(file_path)
        if not target_path.is_file():
            return f"Error: '{file_path}' does not exist or is not a file."
        original = target_path.read_text(encoding="utf-8")
        if search_text not in original:
            return (
                f"Error: search text not found in '{file_path}'.\n"
                "Hint: use read_file or read_file_range to verify the exact content first."
            )
        updated = original.replace(search_text, replace_text, 1)
        target_path.write_text(updated, encoding="utf-8")
        return {
            "path": file_path,
            "changed": True,
            "message": "Replacement applied successfully.",
        }
    except Exception as e:
        return f"Error replacing text in '{file_path}': {e}"

def patch_file_lines(file_path: str, start_line: int, end_line: int, new_content: str) -> dict | str:
    """
    Replaces exact line numbers with new content. No unified diff math required.
    """
    try:
        target_path = _resolve_safe_path(file_path)
        if not target_path.is_file():
            return f"Error: '{file_path}' does not exist."

        lines = target_path.read_text(encoding="utf-8").splitlines(keepends=True)
        
        # 0-indexed math
        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines), end_line)

        # Ensure newline consistency
        if new_content and not new_content.endswith("\n"):
            new_content += "\n"
            
        new_lines = [new_content] if new_content else []
        
        # Slice out the old lines and drop in the new ones
        updated_lines = lines[:start_idx] + new_lines + lines[end_idx:]
        
        target_path.write_text("".join(updated_lines), encoding="utf-8")
        
        return {
            "path": file_path,
            "changed": True,
            "message": f"Replaced lines {start_line} to {end_line} successfully."
        }
    except Exception as e:
        return f"Error patching lines in '{file_path}': {e}"

def apply_patch(file_path: str, patch: str) -> str:
    """
    Apply a unified diff patch to a file.

    The patch should be a standard unified diff (as produced by `diff -u` or `git diff`).
    Example format:
        --- a/src/main.py
        +++ b/src/main.py
        @@ -10,6 +10,7 @@
         existing line
        -old line
        +new line
         existing line

    Returns success message or detailed error.
    """
    try:
        target_path = _resolve_safe_path(file_path)
        if not target_path.is_file():
            return f"Error: '{file_path}' does not exist or is not a file."

        original_lines = target_path.read_text(encoding="utf-8").splitlines(keepends=True)

        # Write original + patch to temp files, apply with `patch`
        with tempfile.NamedTemporaryFile(mode="w", suffix=".orig", delete=False, encoding="utf-8") as orig_f:
            orig_f.writelines(original_lines)
            orig_path = orig_f.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False, encoding="utf-8") as patch_f:
            patch_f.write(patch)
            patch_path = patch_f.name

        try:
            result = subprocess.run(
                ["patch", "--no-backup-if-mismatch", "-o", "-", orig_path, patch_path],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                # Return current file content (first 120 lines) so the LLM can
                # build a correct patch without an extra read_file round-trip.
                current = target_path.read_text(encoding="utf-8")
                preview_lines = current.splitlines()[:120]
                preview = "\n".join(f"{i+1}: {l}" for i, l in enumerate(preview_lines))
                truncated = " (truncated)" if len(current.splitlines()) > 120 else ""
                return (
                    f"PATCH_FAILED — hunk offsets did not match.\n"
                    f"Error: {result.stderr.strip()}\n\n"
                    f"Current file content{truncated} (use these exact lines to rebuild your patch):\n"
                    f"{preview}"
                )

            target_path.write_text(result.stdout, encoding="utf-8")
            return f"Patch applied successfully to '{file_path}'."
        finally:
            os.unlink(orig_path)
            os.unlink(patch_path)

    except FileNotFoundError:
        # `patch` not installed — fall back to Python difflib
        return _apply_patch_python(file_path, patch)
    except Exception as e:
        return f"Error applying patch to '{file_path}': {e}"


def _apply_patch_python(file_path: str, patch: str) -> str:
    """Fallback Python-based unified diff applier when `patch` binary is unavailable."""
    try:
        target_path = _resolve_safe_path(file_path)
        original = target_path.read_text(encoding="utf-8")
        original_lines = original.splitlines(keepends=True)

        patch_lines = patch.splitlines(keepends=True)
        # Skip header lines (--- +++ lines)
        hunks_start = 0
        for i, line in enumerate(patch_lines):
            if line.startswith("@@"):
                hunks_start = i
                break

        result_lines = list(original_lines)
        offset = 0

        i = hunks_start
        while i < len(patch_lines):
            line = patch_lines[i]
            if line.startswith("@@"):
                # Parse @@ -start,count +start,count @@
                m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
                if not m:
                    i += 1
                    continue
                orig_start = int(m.group(1)) - 1  # 0-indexed
                orig_count = int(m.group(2)) if m.group(2) else 1
                i += 1
                hunk_lines = []
                while i < len(patch_lines) and not patch_lines[i].startswith("@@"):
                    hunk_lines.append(patch_lines[i])
                    i += 1

                removes = [l[1:] for l in hunk_lines if l.startswith("-")]
                adds = [l[1:] for l in hunk_lines if l.startswith("+")]
                ctx_plus_rem = [l[1:] if l[0] in "-+" else l[1:] for l in hunk_lines if not l.startswith("+")]

                pos = orig_start + offset
                result_lines[pos : pos + orig_count] = adds
                offset += len(adds) - orig_count
            else:
                i += 1

        target_path.write_text("".join(result_lines), encoding="utf-8")
        return f"Patch applied (Python fallback) to '{file_path}'."
    except Exception as e:
        return f"Error applying patch (Python fallback) to '{file_path}': {e}"


def get_diff(file_path: str, new_content: str) -> str:
    """
    Show a unified diff between the current file content and new_content.
    Useful for previewing changes before writing.
    """
    try:
        target_path = _resolve_safe_path(file_path)
        original = target_path.read_text(encoding="utf-8") if target_path.is_file() else ""
        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        )
        result = "".join(diff)
        return result if result else "No differences."
    except Exception as e:
        return f"Error generating diff for '{file_path}': {e}"

def create_directory(dir_path: str) -> str:
    """Create a directory (and all parents)."""
    try:
        target_path = _resolve_safe_path(dir_path)
        target_path.mkdir(parents=True, exist_ok=True)
        return f"Directory '{dir_path}' created successfully."
    except Exception as e:
        return f"Error creating directory '{dir_path}': {e}"


def list_files(glob_pattern: str = "**/*", max_results: int = 200) -> dict:
    """List files matching a glob pattern within the working directory."""
    try:
        base_dir: Path = get_working_directory()
        results = []
        for path in base_dir.glob(glob_pattern):
            if len(results) >= max_results:
                break
            if not path.is_file():
                continue
            parts = set(path.parts)
            if parts & EXCLUDE_DIRS or path.name in EXCLUDE_FILES:
                continue
            results.append(str(path.relative_to(base_dir)))
        return {"files": results, "count": len(results)}
    except Exception as e:
        return {"error": f"Error listing files: {e}"}


def directory_tree(dir_path: str = ".", max_depth: int = 4) -> str:
    """
    Return an ASCII directory tree (like the `tree` command).
    Excludes common noise dirs (node_modules, .git, __pycache__, etc.).
    """
    try:
        base = _resolve_safe_path(dir_path)
        if not base.is_dir():
            return f"Error: '{dir_path}' is not a directory."
        lines = [str(base.relative_to(get_working_directory().resolve()))]

        def _recurse(path: Path, prefix: str, depth: int):
            if depth > max_depth:
                return
            entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
            entries = [e for e in entries if e.name not in EXCLUDE_DIRS and e.name not in EXCLUDE_FILES and not e.name.startswith(".")]
            for i, entry in enumerate(entries):
                connector = "└── " if i == len(entries) - 1 else "├── "
                lines.append(prefix + connector + entry.name)
                if entry.is_dir():
                    extension = "    " if i == len(entries) - 1 else "│   "
                    _recurse(entry, prefix + extension, depth + 1)

        _recurse(base, "", 1)
        return "\n".join(lines)
    except Exception as e:
        return f"Error building directory tree for '{dir_path}': {e}"

def copy_file(source_path: str, destination_path: str) -> str:
    try:
        src = _resolve_safe_path(source_path)
        dest = _resolve_safe_path(destination_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return f"Copied '{source_path}' → '{destination_path}'."
    except Exception as e:
        return f"Error copying file: {e}"


def rename_path(old_path: str, new_path: str) -> str:
    try:
        src = _resolve_safe_path(old_path)
        dest = _resolve_safe_path(new_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dest)
        return f"Renamed '{old_path}' → '{new_path}'."
    except Exception as e:
        return f"Error renaming path: {e}"


def delete_path(path: str) -> str:
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

def search_files(
    pattern: str,
    file_glob: str = "**/*",
    case_sensitive: bool = False,
    max_results: int = 50,
    context_lines: int = 2,
) -> dict:
    """
    Grep-style regex search across all project files.

    Args:
        pattern: Python regex pattern to search for.
        file_glob: Limit search to files matching this glob (e.g. "**/*.py").
        case_sensitive: Whether the regex is case-sensitive.
        max_results: Maximum number of matches to return.
        context_lines: Number of surrounding lines to include per match.

    Returns a dict with matches grouped by file:
        {
            "pattern": "...",
            "matches": [
                {
                    "file": "src/main.py",
                    "line": 42,
                    "column": 8,
                    "match": "matched text",
                    "context": "...surrounding lines..."
                },
                ...
            ],
            "total_matches": N,
            "truncated": bool
        }
    """
    try:
        base_dir = get_working_directory()
        flags = 0 if case_sensitive else re.IGNORECASE
        regex = re.compile(pattern, flags)

        matches = []
        searched = 0

        for path in sorted(base_dir.glob(file_glob)):
            if not path.is_file():
                continue
            parts = set(path.parts)
            if parts & EXCLUDE_DIRS or path.name in EXCLUDE_FILES:
                continue
            # Skip binary files
            try:
                text = path.read_text(encoding="utf-8", errors="strict")
            except (UnicodeDecodeError, PermissionError):
                continue

            searched += 1
            lines = text.splitlines()

            for line_no, line in enumerate(lines, start=1):
                for m in regex.finditer(line):
                    # context
                    ctx_start = max(0, line_no - 1 - context_lines)
                    ctx_end = min(len(lines), line_no + context_lines)
                    context = "\n".join(
                        f"{'>' if i + 1 == line_no else ' '} {i + 1}: {lines[i]}"
                        for i in range(ctx_start, ctx_end)
                    )
                    matches.append({
                        "file": str(path.relative_to(base_dir)),
                        "line": line_no,
                        "column": m.start() + 1,
                        "match": m.group(0),
                        "context": context,
                    })
                    if len(matches) >= max_results:
                        return {
                            "pattern": pattern,
                            "matches": matches,
                            "total_matches": len(matches),
                            "files_searched": searched,
                            "truncated": True,
                        }

        return {
            "pattern": pattern,
            "matches": matches,
            "total_matches": len(matches),
            "files_searched": searched,
            "truncated": False,
        }
    except re.error as e:
        return {"error": f"Invalid regex pattern '{pattern}': {e}"}
    except Exception as e:
        return {"error": f"Error searching files: {e}"}


def find_symbol(symbol: str, file_glob: str = "**/*") -> dict:
    """
    Find where a function, class, or variable is defined or referenced.
    Wraps search_files with a pre-built definition pattern.

    Searches for:
      - def symbol(
      - class symbol(
      - symbol =
      - symbol:

    Returns grouped matches.
    """
    pattern = rf"\b(def|class|function|const|let|var)\s+{re.escape(symbol)}\b|{re.escape(symbol)}\s*[=:\(]"
    return search_files(pattern=pattern, file_glob=file_glob, max_results=30, context_lines=1)