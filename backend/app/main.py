import uvicorn
import json
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Any
import uuid
from .agent_orchestrator import CodingAgent
from .database import engine, Base, get_db
from .models import ChatSession
from sqlalchemy.orm import Session

Base.metadata.create_all(bind=engine)

app = FastAPI()

class InitRequest(BaseModel):
    tools_list: list[dict[str, Any]]

class ChatRequest(BaseModel):
    prompt: Optional[str] = None
    cwd: Optional[str] = None
    session_id: str
    tool_result: Optional[dict[str, Any]] = None

@app.post("/api/init-session")
async def tools(request: InitRequest, db: Session=Depends(get_db)):
    session_id = str(uuid.uuid4())
    print(f"Starting new session: {session_id}")
    
    try:
        chat_session = ChatSession(
            id=session_id,
            tools_list=request.tools_list,
            contents=[]
        )

        db.add(chat_session)
        db.commit()
        db.refresh(chat_session)

        return {"session_id": session_id}
    except Exception as e:
        db.rollback()
        print(f"Error initializing agent: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.post("/api/chat")
async def chat(request: ChatRequest, db: Session=Depends(get_db)):

    chat_session: ChatSession | None = db.query(ChatSession).filter(
        ChatSession.id == request.session_id
    ).first()

    if not chat_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found. Please initialize a new session"
        )

    agent = CodingAgent(
        session_id=request.session_id,
        tools_list=chat_session.tools_list,
        contents_json=chat_session.contents,
    )
    
    if request.tool_result:
        agent.add_tool_response(request.tool_result)

    def stream_with_persist():
        try:
            for chunk in agent.run(prompt=request.prompt):
                yield chunk
        finally:
            try:
                chat_session.contents = agent.contents_as_json()
                db.add(chat_session)
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"Error saving session {request.session_id}: {e}")

    return StreamingResponse(
        stream_with_persist(), 
        media_type="application/x-ndjson"
    )

if __name__ == "__main__":
    print("Starting backend server on http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
