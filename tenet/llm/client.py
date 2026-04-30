# my_agent/llm/client.py
import os
from dotenv import load_dotenv
from openai import OpenAI
from typing import Any

load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    raise EnvironmentError("GEMINI_API_KEY not set")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com"
)
