from tools.files_info import get_file_info
from tools.read_file import read_file
from tools.write_file import write_file
from tools.delete_path import delete_path
from tools.copy_file import copy_file
from tools.run_file import run_file
from google.genai import types

working_directory = "testing_directory"

def call_function(function_call):

    print(f"-> Calling function: {function_call.name}({function_call.args})")

    try:
        result = ""
        if function_call.name == "get_file_info":
            result = get_file_info(working_directory, **function_call.args)
        elif function_call.name == "read_file":
            result = read_file(working_directory, **function_call.args)
        elif function_call.name == "write_file":
            result = write_file(working_directory, **function_call.args)
        elif function_call.name == "delete_path":
            result = delete_path(working_directory, **function_call.args)
        elif function_call.name == "copy_file":
            result = copy_file(working_directory, **function_call.args)
        elif function_call.name == "run_file":
            result = run_file(working_directory, **function_call.args)
        else:
            result = {"error": f"Unknown function: {function_call.name}"}

        return types.Content(
            role="function",
            parts=[
                types.Part.from_function_response(
                    name=function_call.name,
                    response={"result": result},
                )
            ],
        )
    
    except Exception as e:
        error = f"Error calling {function_call.name}: {e}"
        return types.Content(
            role="function",
            parts=[
                types.Part.from_function_response(
                    name=function_call.name,
                    response={"error": error},
                )
            ],
        )
    