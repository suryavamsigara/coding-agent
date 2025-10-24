import os
import sys
from fastapi import FastAPI
from .agent.agent_orchestrator import CodingAgent

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "My coding agent API."}

def run_agent():
    if len(sys.argv) < 2:
        print("Enter a question..\n")
        print("Format: uv run -m backend.app.main 'question'")
        sys.exit(1)
    
    prompt = sys.argv[1]
    agent = CodingAgent()
    agent.run(prompt)

if __name__ == "__main__":
    run_agent()
    