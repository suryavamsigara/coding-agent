import uvicorn
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from typing import Optional, Any
import uuid
from agent_orchestrator import CodingAgent

app = FastAPI()

SESSIONS: dict[str, CodingAgent] = {}

class ChatRequest(BaseModel):
    prompt: Optional[str] = None
    cwd: Optional[str] = None
    session_id: Optional[str] = None
    tool_result: Optional[dict[str, Any]] = None
    tools_list: Optional[list[dict[str, Any]]] = None

@app.post("/chat")
async def chat(request: ChatRequest):
    agent: CodingAgent
    tools: list[dict[str, Any]]

    if request.session_id and request.session_id in SESSIONS:
        print(f"Resuming session: {request.session_id}")
        agent = SESSIONS[request.session_id]["agent"]
        tools = SESSIONS[request.session_id]["tools"]

    elif request.prompt and request.tools_list:
        session_id = str(uuid.uuid4())
        print(f"Starting new session: {session_id}")
        agent = CodingAgent(session_id=session_id)
        tools = request.tools_list

        SESSIONS[session_id] = {"agent": agent, "tools": tools}
    
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"New session requires prompt and tools_list")
    
    response_data = await agent.run(
        tools_list=tools,
        prompt=request.prompt,
        tool_result=request.tool_result
    )

    response_data["session_id"] = agent.session_id
    return response_data

if __name__ == "__main__":
    print("Starting remote LLM backend simulation on http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)











"""
def run_agent():
    try:
       agent = CodingAgent()
    except Exception as e:
        print(f"[Initialization Error] {e}")
        sys.exit(1)

    while True:
        try:
            prompt = questionary.text("User: ").ask()

            if prompt is None or prompt.lower() in ['exit', 'quit']:
                print("\nExiting...")
                break

            if not prompt.strip():
                continue
            agent.run(prompt)

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print("\nError: ", e)
            pass

if __name__ == "__main__":
    run_agent()
"""

