import json
from typing import Any
from tenet.tools.file_ops import *

TOOL_REGISTRY: dict[str, callable] = {
    "read_file": read_file,
    "write_file": write_file,
    "create_file": create_file,
    "copy_file": copy_file,
}

def execute_tool(tool_name: str, **args):
    if tool_name not in TOOL_REGISTRY:
        return f"Error: Tool '{tool_name}' does not exist. Please use an available tool."
    
    try:
        tool_function = TOOL_REGISTRY[tool_name]
        result = tool_function(**args)
        return result
    except Exception as e:
        return f"Error executing {tool_name}: {str(e)}"