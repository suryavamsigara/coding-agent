import os
import json
from typing import Optional, Any, Generator
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.types import Tool, FunctionDeclaration, GenerateContentConfig, Content, Part

load_dotenv()


class CodingAgent:
    def __init__(self, session_id: str, tools_list: Optional[list[dict[str, Any]]], model="gemini-2.0-flash-001"):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("Gemini API key missing")
        
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.session_id = session_id
        self.tools_list = tools_list
        self.contents = []
        self.system_prompt = """
        You are "Quirk", an autonomous AI coding agent. Your entire purpose is to operate on the codebase in the working directory to fulfill the user's request.

        ## Primary Objective
        Understand the user's task (e.g., answer a question, analyze functionality, debug, or modify code) and execute a plan to complete it. You can ask clairifying questions.

        ## Capabilities
        You have access to tools that allow you to:
        - List files and directories
        - Read and write file contents
        - Create, delete, copy, and move files or directories
        - Execute Python scripts

        ## Core Workflow & Constraints
        You MUST follow these rules precisely:

        1.  **FIRST STEP:** Based on the user's task, your first valid starting action is to call `get_file_info` with `directory='.'` to list **all files recursively** if you need files structure. You must call it to know the paths of files to call tools.

        2.  **ANALYZE:** Review the complete file structure from the `get_file_info` result and the user's request.

        3.  **PLAN:** Formulate a concise, step-by-step internal plan to achieve the user's goal.

        4.  **EXECUTE (One Tool at a Time):** You MUST return only **one tool call per turn**.

        5.  **AUTONOMY:** Be self-directed. Automatically decide which files to read, modify, or execute based on your plan. Do not ask the user for file names; find them yourself.

        6.  **PATHING:** All file paths MUST be relative to the working directory (e.g., `src/main.py`).

        7.  **EFFICIENCY:** Never perform unnecessary or repetitive tool calls.

        8.  **COMPLETION:** When your plan is complete and you have the full answer or have finished the task, provide a final, comprehensive response to the user instead of calling another tool.

        9. IBased on user's task, you can create different files and folders to build and execute the plan. You need to know the CONTEXT before starting, so READ RELEVANT files FIRST.

        When you need to use a tool, provide a brief, single-line 'thought' (e.g., 'Okay, I'll read that file.') *before* you call the tool.
        
        Do not use Markdown (like `**` or `*`). All output must be plain text.
        """
        self.gen_tools = Tool(
            function_declarations=[
                FunctionDeclaration(
                    name=t["name"],
                    description=t["description"],
                    parameters=t.get("inputSchema", {}),
                ) for t in self.tools_list
            ]
        )
    
    def add_tool_response(self, tool_result: dict[str, Any]):
        self.contents.append(Content(
            role="tool",
            parts=[Part.from_function_response(
                name=tool_result["tool_name"],
                response={"result": tool_result["response"]},
            )]
        ))

    def run(
        self,
        prompt: Optional[str] = None,
    ) -> Generator[str, None, None]:
        
        if prompt:
            self.contents.append(Content(role="user", parts=[Part(text=prompt)]))

        config = GenerateContentConfig(
            tools=[self.gen_tools],
            system_instruction=self.system_prompt,
            # thinking_config=types.ThinkingConfig(
            #     thinking_budget=200
            # )
        )

        try:
            stream = self.client.models.generate_content_stream(
                model=self.model,
                contents=self.contents,
                config=config,
            )
        except Exception as e:
            yield json.dumps({"final_answer": f"LLM Error: {e}"}) + "\n"
            return

        buffered_parts = []
        is_tool_call = False

        for chunk in stream:
            if not chunk.candidates:
                continue
            
            if chunk.parts:
                buffered_parts.extend(chunk.parts)

            if any(part.function_call for part in chunk.parts):
                is_tool_call = True
            
            if not is_tool_call and chunk.text:
                yield json.dumps({"final_answer_chunk": chunk.text}) + "\n"

        if buffered_parts:
            self.contents.append(Content(role="model", parts=buffered_parts))

        if is_tool_call:
            function_call = None
            for part in buffered_parts:
                if part.function_call:
                    function_call = part.function_call
            
            if function_call:
                yield json.dumps({
                    "tool_call": {
                        "tool_name": function_call.name,
                        "params": dict(function_call.args)
                    }
                }) + "\n"

