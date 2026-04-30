# my_agent/llm/client.py
import os
from dotenv import load_dotenv
from openai import OpenAI
from typing import Any

from tenet.tools.tool_schema import OPENAI_TOOLS_LIST

load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    raise EnvironmentError("GEMINI_API_KEY not set")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com"
)

def get_agent_response(message_history: list[dict[str, Any]]) -> Any:
    """
    Sends the conversation history to OpenAI and returns the model's response.
    Includes the tool registry so the model knows what actions it can take.
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=message_history,
            tools=OPENAI_TOOLS_LIST,
            tool_choice="auto",
            temperature=0.2,
        )
        
        return response.choices[0].message
        
    except Exception as e:
        print(f"\nAPI Error: {str(e)}")
        raise e