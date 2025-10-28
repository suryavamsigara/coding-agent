
import os
import asyncio
from typing import Optional, Any
from dotenv import load_dotenv
from google import genai
from google.genai.types import Tool, FunctionDeclaration, GenerateContentConfig, Content, Part

load_dotenv()


class CodingAgent:
    def __init__(self, session_id: str, model="gemini-2.0-flash-001"):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("Gemini API key missing")
        
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.session_id = session_id
        self.contents = []
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

    async def run(
        self,
        tools_list: list[dict[str, Any]],
        prompt: Optional[str] = None,
        tool_result: Optional[dict[str, Any]] = None,
    ):
        if prompt:
            self.contents.append(Content(role="user", parts=[Part(text=prompt)]))

        if tool_result:
            self.contents.append(Content(
                role="tool",
                parts=[Part.from_function_response(
                    name=tool_result["tool_name"],
                    response={"result": tool_result["response"]},
                )]
            ))

        gen_tools = Tool(
            function_declarations=[
                FunctionDeclaration(
                    name=t["name"],
                    description=t["description"],
                    parameters=t.get("inputSchema", {}),
                ) for t in tools_list
            ]
        )

        config = GenerateContentConfig(
            tools=[gen_tools],
            system_instruction=self.system_prompt,
        )

        def generate():
            return self.client.models.generate_content(
                model=self.model,
                contents=self.contents,
                config=config,
            )

        loop = asyncio.get_running_loop()
        try:
            response = await loop.run_in_executor(None, generate)
        except Exception as e:
            return {"final_answer": f"LLM Error: {e}"}

        if not response or not response.candidates:
            return {"final_answer": "Empty response from LLM"}

        candidate = response.candidates[0]
        self.contents.append(candidate.content)

        if response.function_calls:
            fc = response.function_calls[0]
            return {
                "tool_call": {
                    "tool_name": fc.name,
                    "params": dict(fc.args)
                }
            }

        text = candidate.content.parts[0].text if candidate.content.parts else None
        return {"final_answer": text or "⚠ Empty answer"}

