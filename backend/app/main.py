import uvicorn
import json
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Any
import uuid
from agent_orchestrator import CodingAgent

app = FastAPI()

SESSIONS: dict[str, CodingAgent] = {}

class InitRequest(BaseModel):
    tools_list: list[dict[str, Any]]

class ChatRequest(BaseModel):
    prompt: Optional[str] = None
    cwd: Optional[str] = None
    session_id: str
    tool_result: Optional[dict[str, Any]] = None

@app.post("/api/init-session")
async def tools(request: InitRequest):
    session_id = str(uuid.uuid4())
    print(f"Starting new session: {session_id}")
    
    try:
        agent = CodingAgent(session_id=session_id, tools_list=request.tools_list)
        SESSIONS[session_id] = agent
        return {"session_id": session_id}
    except Exception as e:
        print(f"Error initializing agent: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.post("/api/chat")
async def chat(request: ChatRequest):
    agent = SESSIONS.get(request.session_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found. Please initialize a new session."
        )
    
    if request.tool_result:
        agent.add_tool_response(request.tool_result)

    return StreamingResponse(
        agent.run(prompt=request.prompt), 
        media_type="application/x-ndjson"
    )

if __name__ == "__main__":
    print("Starting backend server on http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)

