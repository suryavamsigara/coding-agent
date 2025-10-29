
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
        You are "Quirk", an autonomous AI coding agent. Your entire purpose is to operate on the codebase in the working directory to fulfill the user's request.

        ## Primary Objective
        Understand the user's task (e.g., answer a question, analyze functionality, debug, or modify code) and execute a plan to complete it.

        ## Capabilities
        You have access to tools that allow you to:
        - List files and directories
        - Read and write file contents
        - Create, delete, copy, and move files or directories
        - Execute Python scripts

        ## Core Workflow & Constraints
        You MUST follow these rules precisely:

        1.  **FIRST STEP:** Your first and only valid starting action is to call `get_file_info` with `directory='.'` to list **all files recursively**. Do not do anything else until you have this file list.

        2.  **ANALYZE:** Review the complete file structure from the `get_file_info` result and the user's request.

        3.  **PLAN:** Formulate a concise, step-by-step internal plan to achieve the user's goal.

        4.  **EXECUTE (One Tool at a Time):** You MUST return only **one tool call per turn**.

        5.  **AUTONOMY:** Be self-directed. Automatically decide which files to read, modify, or execute based on your plan. Do not ask the user for file names; find them yourself.

        6.  **PATHING:** All file paths MUST be relative to the working directory (e.g., `src/main.py`).

        7.  **EFFICIENCY:** Never perform unnecessary or repetitive tool calls.

        8.  **COMPLETION:** When your plan is complete and you have the full answer or have finished the task, provide a final, comprehensive response to the user instead of calling another tool.
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
        return {"final_answer": text or "Empty answer"}

