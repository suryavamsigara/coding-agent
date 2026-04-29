import json
from typing import Any
from tenet.tools.file_ops import *

tool_registry: dict[str, callable] = {
    "read_file": read_file,
    "write_file": write_file,
    "create_file": create_file,
    "copy_file": copy_file
}

def execute_tool(tool_call: Any):
    # tool_call = json.loads(tool_call)
    func_name = tool_call.get('function_name')
    args = tool_call.get('function').get('arguments')

    try:
        function = tool_registry[func_name]
        result = function(**args)
        return result
    except Exception as e:
        return f"Error executing {func_name}: {str(e)}"