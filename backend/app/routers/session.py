from fastapi import status, HTTPException, Depends, APIRouter
from sqlalchemy.orm import Session
import uuid
from ..schemas import InitRequest
from ..database import get_db
from ..models import AgentSession
from ..agent_orchestrator import CodingAgent

router = APIRouter(
    prefix="/api",
    tags=["Session"]
)

ACTIVE_SESSIONS: dict[str, CodingAgent] = {}

@router.post("/init-session")
async def tools(request: InitRequest, db: Session = Depends(get_db)):
    session_id = str(uuid.uuid4())
    print(f"Starting new session: {session_id}")
    
    try:
        agent = CodingAgent(session_id=session_id,
                            tools_list=request.tools_list)
        
        db_session = AgentSession(
            session_id=session_id,
            user_id=1,
            conversation_history=[],
            meta_data={"tools": request.tools_list}
        )

        db.add(db_session)
        db.commit()
        db.refresh(db_session)
        return {"session_id": session_id}
    except Exception as e:
        print(f"Error initializing agent: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    
