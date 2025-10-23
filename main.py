import os
import sys
from dotenv import load_dotenv
from google import genai
from google.genai import types
from tools.files_info import get_file_info_function
from tools.read_file import read_file_function
from tools.write_file import write_file_function
from tools.delete_path import delete_path_function
from call_function import call_function
from typing import Optional, List

def main():
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)

    system_prompt = """
    You are an autonomous AI coding agent.

    Your purpose is to understand and operate on the codebase in the working directory to answer questions, analyze functionality, or perform debugging and modification tasks.

    You can perform the following operations:
    - List files and directories
    - Read file contents
    - Write to a file
    - Delete a file or directory

    Core behavior:
    1. ALWAYS start by calling `get_file_info` with `directory='.'` to list **all files recursively** within the project.
    2. After receiving the result, you MUST analyze the returned directory and file paths — including those inside nested folders.
    3. You should then decide which specific files to read or modify based on the user's request, using the full relative paths returned (e.g. `subdir/code.py`).
    4. You should automatically decide which files to inspect or execute — the user does NOT need to specify them.
    5. Never perform unnecessary or repetitive function calls.
    6. All paths you reference should be relative to the working directory.
    7. The working directory is implicitly handled — do not include it in your function calls.

    Your goal is to behave like a self-directed software engineer who can explore, reason about, and act on a local codebase intelligently.
    """

    if len(sys.argv) < 2:
        print("Enter your question..")
        sys.exit(1)

    prompt = sys.argv[1]

    tools = types.Tool(
        function_declarations=[
            types.FunctionDeclaration(**get_file_info_function),
            types.FunctionDeclaration(**read_file_function),
            types.FunctionDeclaration(**write_file_function),
            types.FunctionDeclaration(**delete_path_function),
        ]
    )

    config = types.GenerateContentConfig(
        tools=[tools],
        system_instruction=system_prompt
    )

    contents = [
        types.Content(role="user", parts=[types.Part(text=prompt)]),
    ]

    max_iters = 20
    for _ in range(0, max_iters):
        response = client.models.generate_content(
            model = "gemini-2.0-flash-001",
            contents = contents,
            config=config,
        )

        if response is None:
            print("no response")
            return

        if response.candidates:
            contents.append(response.candidates[0].content)

        if response.function_calls:
            all_parts = []
            function_calls: Optional[List[types.FunctionCall]] = response.function_calls
            print(f"\nFUNCTION CALLS: {function_calls}\n")
            for function_call_part in response.function_calls:
                result = call_function(function_call_part)
                print("--------------------------------------------------")
                all_parts.extend(result.parts)
                print(f"-> Function executed: {function_call_part.name}")
                print("--------------------------------------------------")
                print(result)
            tool_response = types.Content(role="tool", parts=all_parts)
            contents.append(tool_response)
        else:
            # final agent text message
            print("\nFINAL RESPONSEE\n")
            print(response.text)
            return

if __name__ == "__main__":
    main()