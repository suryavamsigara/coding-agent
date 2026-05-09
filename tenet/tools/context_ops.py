from __future__ import annotations

_memory_ref = None


def bind_memory(memory_manager) -> None:
    global _memory_ref
    _memory_ref = memory_manager


def update_project_context(
    file_summaries: dict[str, str] | None = None,
    symbols: dict[str, str] | None = None,
    facts: dict[str, str] | None = None,
) -> dict:
    """
    Writes what it learned about this project into persistent memory.
    This memory survives context-window trims and calls it after reading any file.

    Args:
        file_summaries: {
            "path/to/file.ext": "what this file owns / is responsible for"
        }
        symbols: {
            "symbolName": "filename.ext — what it does"
            # NO line numbers — they go stale after edits.
            # Use search_files to find exact location before editing.
        }
        facts: {
            "any key": "any stable fact about the project",
            # Examples:
            # "state.posts": "Array<Post> — {id, name, handle, time, text, imageData, likes}",
            # "modal": "toggled via .hidden CSS class on #postModal",
            # "post rendering": "renderPost() in app.js builds the DOM node",
        }

    Returns a confirmation with current context totals.
    """
    if _memory_ref is None:
        return {"error": "Memory not initialised."}

    updates = {}
    if file_summaries:
        updates["file_summaries"] = file_summaries
    if symbols:
        updates["symbols"] = symbols
    if facts:
        updates["facts"] = facts

    if not updates:
        return {"message": "Nothing to update."}

    _memory_ref.update_project_context(updates)
    ctx = _memory_ref.project
    return {
        "ok": True,
        "totals": {
            "files": len(ctx.file_summaries),
            "symbols": len(ctx.symbols),
            "facts": len(ctx.facts),
        },
    }