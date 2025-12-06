import os
import json
from typing import Optional, Any, Generator
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.types import Tool, FunctionDeclaration, GenerateContentConfig, Content, Part

load_dotenv()

def contents_from_json(contents_json: list[dict[str, Any]]) -> list[Content]:
    result: list[Content] = []
    
    for item in contents_json:
        role = item["role"]
        parts = []
        for p in item["parts"]:
            if "text" in p:
                parts.append(Part(text=p["text"]))
            elif "function_call" in p:
                parts.append(Part.from_function_call(
                    name=p["function_call"]["name"],
                    args=p["function_call"].get("args", {})
                ))
            elif "function_response" in p:
                parts.append(Part.from_function_response(
                    name=p["function_response"]["name"],
                    response=p["function_response"]["response"],
                ))
        result.append(Content(role=role, parts=parts))
    return result

def contents_to_json(contents: list[Content]) -> list[dict[str, Any]]:
    """Converts list[Content] into JSON for DB."""
    out: list[dict[str, Any]] = []
    
    for c in contents:
        parts_list = []
        for p in c.parts:
            if getattr(p, "text", None):
                parts_list.append({"text": p.text})
            elif getattr(p, "function_call", None):
                parts_list.append({
                    "function_call": {
                        "name": p.function_call.name,
                        "args": dict(p.function_call.args),
                    }
                })
            elif getattr(p, "function_response", None):
                parts_list.append({
                    "function_response": {
                        "name": p.function_response.name,
                        "response": p.function_response.response,
                    }
                })
        out.append({"role": c.role, "parts": parts_list})
    return out

class CodingAgent:
    def __init__(
        self,
        session_id: str,
        tools_list: list[dict[str, Any]],
        model="gemini-2.5-flash",
        contents_json: Optional[list[dict[str, Any]]] = None,
    ):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("Gemini API key missing")
        
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.session_id = session_id
        self.tools_list = tools_list
        self.contents: list[Content] = contents_from_json(contents_json or [])
        self.system_prompt = """
        You are "Quirk", an autonomous AI coding agent that operates on the codebase in the working directory.

        ## Rules
        1. **FIRST ACTION:** You can call `get_file_info` with `directory='.'` if you need to know the file structure.

        2. **ONE TOOL PER TURN:** Return exactly ONE tool call per response. Never return multiple tools.

        3. **BE BRIEF:** Before calling a tool, output short summary about what you're doing.
        
        4. **NO EXPLANATIONS:** Do NOT explain your plan or reasoning in detail. Just act.

        5. **AUTO-DECIDE:** Never ask which file to read/modify. Analyze and decide yourself.

        6. **RELATIVE PATHS:** All paths relative to working directory (e.g., `src/main.py`).

        7. **COMPLETION:** When done, provide a brief final answer.

        8. **NO MARKDOWN:** Plain text only. No `**` or `**bold**` or `*italic*`.

        9. ALWAYS be friendly and ALWAYS ask relevant **follow up** questions.

        10. **DO NOT build** the entire projects in one go. You **must** ask user follow up questions about how they want.

        ## Available Actions
        - List/read/write/delete files
        - Create/rename/copy/move files and directories  
        - Execute Python scripts

        Work autonomously. Be decisive. Be concise.
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
            thinking_config=types.ThinkingConfig(
                thinking_budget=128,
                include_thoughts=False
            )
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
                for part in chunk.parts:
                    buffered_parts.extend(chunk.parts)

                    if part.function_call:
                        is_tool_call = True

                    if part.text and not is_tool_call:
                        yield json.dumps({"answer_chunk": part.text}) + "\n"
        
        if buffered_parts:
            self.contents.append(Content(role="model", parts=buffered_parts))

        if is_tool_call:
            function_call = None
            for part in buffered_parts:
                if part.function_call:
                    function_call = part.function_call
                    break
            
            if function_call:
                yield json.dumps({
                    "tool_call": {
                        "tool_name": function_call.name,
                        "params": dict(function_call.args)
                    }
                }) + "\n"
        return
    
    def contents_as_json(self) -> list[dict[str, Any]]:
        return contents_to_json(self.contents)

