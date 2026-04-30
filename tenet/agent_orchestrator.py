# my_agent/core/loop.py
import json
from typing import List, Dict, Any

from tenet.client import get_agent_response
from tenet.tools.executor import execute_tool

SYSTEM_PROMPT = """You are a highly capable CLI coding agent. 
You can inspect directories, read, write, and execute code. 
Always use the provided tools to verify the state of the filesystem before and after making changes."""

def run_agent_loop(user_prompt: str, message_history: List[Dict[str, Any]] = None) -> str:
    """
    The core Reason-Act-Observe loop. 
    Continues running until the LLM decides it has fully answered the user.
    """
    
    if message_history is None:
        message_history = [{"role": "system", "content": SYSTEM_PROMPT}]
        
    message_history.append({"role": "user", "content": user_prompt})
    
    print("Thinking...")

    while True:
        response_message = get_agent_response(message_history)
        
        message_history.append(response_message)
        
        if response_message.tool_calls:
            for tool_call in response_message.tool_calls:
                tool_name = tool_call.function.name
                
                try:
                    tool_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}
                    print(f"⚠️ Warning: LLM provided invalid JSON for tool {tool_name}")

                print(f"🛠️  Executing: {tool_name}({', '.join(f'{k}={v}' for k, v in tool_args.items())})")
                
                observation = execute_tool(tool_name, **tool_args)
                
                message_history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": str(observation) 
                })

                print(message_history)
            
        else:
            print(response_message.content)
            return response_message.content

run_agent_loop("what files are there in current dir? I just want the list.")