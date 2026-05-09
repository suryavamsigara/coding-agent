from tenet.tools.file_ops import *
from tenet.tools.shell_ops import run_command
from tenet.tools.context_ops import update_project_context

TOOL_REGISTRY: dict[str, callable] = {
    "get_file_info":    get_file_info,
    "read_file":        read_file,
    "read_file_range":  read_file_range,
    "write_file":       write_file,
    "create_file":      create_file,
    "replace_in_file":  replace_in_file,
    "apply_patch":      apply_patch,
    "get_diff":         get_diff,
    "create_directory": create_directory,
    "list_files":       list_files,
    "directory_tree":   directory_tree,
    "copy_file":        copy_file,
    "rename_path":      rename_path,
    "delete_path":      delete_path,
    "search_files":     search_files,
    "find_symbol":      find_symbol,
    "run_command":      run_command,
    "update_project_context": update_project_context,
}

def execute_tool(tool_name: str, **args):
    if tool_name not in TOOL_REGISTRY:
        available = ", ".join(sorted(TOOL_REGISTRY.keys()))
        return f"Error: Tool '{tool_name}' does not exist. Available tools: {available}"
    
    try:
        return TOOL_REGISTRY[tool_name](**args)
    except TypeError as e:
        return f"Error: wrong arguments for tool '{tool_name}': {e}"
    except Exception as e:
        return f"Error executing '{tool_name}': {e}"