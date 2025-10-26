import os
import json
from dotenv import load_dotenv
from typing import Optional, List
from google import genai
from google.genai import types
from .tools.files_info import get_file_info_function
from .tools.read_file import read_file_function
from .tools.write_file import write_file_function
from .tools.delete_path import delete_path_function
from .tools.copy_file import copy_file_function
from .tools.run_file import run_file_function
from ..call_function import call_function

load_dotenv()

class CodingAgent:
    def __init__(self, model="gemini-2.0-flash-001"):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Gemini API key not set.")
        self.client = genai.Client(api_key=api_key)
        self.model = model

        self.system_prompt = """
        You are an autonomous AI coding agent.

        Your purpose is to understand and operate on the codebase in the working directory to answer questions, analyze functionality, or perform debugging and modification tasks.

        You can perform the following operations:
        - List files and directories
        - Read file contents
        - Write to a file
        - Delete a file or directory
        - Copy a file from source to destination
        - Execute python files

        Core behavior:
        1. ALWAYS start by calling `get_file_info` with `directory='.'` to list **all files recursively** within the project.
        2. After receiving the result, you MUST analyze the returned directory and file paths — including those inside nested folders.
        3. You should then decide which specific files to read or modify based on the user's request, using the full relative paths returned (e.g. `subdir/code.py`).
        4. You should automatically decide which files to inspect or execute — the user does NOT need to specify them.
        5. Before calling copy_file, check if the destination already exists to copy to that instead of creating a new one.
        6. Never perform unnecessary or repetitive function calls.
        7. All paths you reference should be relative to the working directory.
        8. The working directory is implicitly handled — do not include it in your function calls.

        Your goal is to behave like a self-directed software engineer who can explore, reason about, and act on a local codebase intelligently.
        """
        self.tools = types.Tool(
            function_declarations=[
                types.FunctionDeclaration(**get_file_info_function),
                types.FunctionDeclaration(**read_file_function),
                types.FunctionDeclaration(**write_file_function),
                types.FunctionDeclaration(**delete_path_function),
                types.FunctionDeclaration(**copy_file_function),
                types.FunctionDeclaration(**run_file_function),
            ]
        )

    def _think(self, msg: str):
        print(f"\n[Thinking] {msg}")
    
    def _calling(self, fc: types.FunctionCall):
        args = ", ".join(f"{k}={v!r}" for k, v in fc.args.items())
        print(f"\n[Calling] {fc.name}({args})")

    def _fc_result(self, result):
        for part in result.parts:
            if not hasattr(part, "function_response"):
                continue
            response = part.function_response.response
            if "error" in response:
                print(f"[Error] {response['error']}")
                return
            data = response.get("result", {})
            if isinstance(data, dict):
                self._print_strctured_result(data)
            else:
                print(f"[Result] {data}")

    def _print_strctured_result(self, result_data: dict):
        
        if "stdout" in result_data or "stderr" in result_data:
            print(f"[Execution] Output")
            if result_data.get("stdout"):
                print(f"STDOUT:\n{result_data["stdout"]}")
            if result_data.get("stderr"):
                print(f"STDERR:\n{result_data["stderr"]}")
        else:
            result = json.dumps(result_data)
            print(f"Result:\n{result}")

    def run(self, prompt: str, max_iters: int=20) -> str:
        config = types.GenerateContentConfig(
            tools=[self.tools],
            system_instruction=self.system_prompt
        )

        contents = [
            types.Content(role="user", parts=[types.Part(text=prompt)]),
        ]

        for i in range(0, max_iters):
            self._think(f"Sending request (iteration {i+1})")
            response = self.client.models.generate_content(
                model = self.model,
                contents = contents,
                config=config,
            )

            if not response or not response.candidates:
                return f"Error: No response from LLM"

            candidate = response.candidates[0]
            contents.append(candidate.content)

            if response.function_calls:
                all_parts = []

                for function_call_part in response.function_calls:
                    self._calling(function_call_part)
                    result = call_function(function_call_part)
                    self._fc_result(result)
                    all_parts.extend(result.parts)
                tool_response = types.Content(role="tool", parts=all_parts)
                contents.append(tool_response)
                continue
            
            final_text = candidate.content.parts[0].text if candidate.content.parts else ""
            print("\n[Final Answer]")
            print("-"*50)
            print(final_text.strip())
            print("-"*50)
            return final_text.strip()
        return "Error: Maximum iterations reached.  "
