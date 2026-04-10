from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from uuid import UUID


from backend.routes import conversation

from backend.database.session import get_db
from backend.auth.logic import login_user
from backend.services.auth_service import create_user
from backend.services.agent_service import AgentService
from backend.database.models import User
from backend.database.schemas import UserCreate, UserLogin, AskRequest


app = FastAPI()

app.include_router(conversation.router)
@app.post("/register")
def register(request: UserCreate, db: Session = Depends(get_db)):
    user = create_user(db, request.username, request.email, request.password, request.role)
    return {"message": "User created", "user_id": str(user.id)}


@app.post("/login")
def login(request: UserLogin, db: Session = Depends(get_db)):
    user, error = login_user(db, request.username, request.password)

    if error:
        return {"error": error}

    return {
        "message": "Login successful",
        "user_id": str(user.id),
        "role": user.role
    }


@app.post("/ask")
def ask_agent(request: AskRequest, db: Session = Depends(get_db)):
    """
    Ask the agent a question.

    Args:
        request: AskRequest containing user_id, question, and optional conversation_id

    Returns:
        Agent answer and metadata
    """
    try:
        # Get user and their role
        user = db.query(User).filter(User.id == request.user_id).first()
        if not user:
            return {"error": "User not found"}

        # Get or create conversation
        conv_id = AgentService.get_or_create_conversation(request.user_id, request.conversation_id, db)

        # Execute query
        result = AgentService.execute_query(request.user_id, UUID(conv_id), request.question, user.role, db)

        return result

    except Exception as e:
        return {"error": str(e)}


@app.get("/conversation/{conversation_id}")
def get_conversation(conversation_id: UUID, user_id: UUID = None, db: Session = Depends(get_db)):
    """
    Get conversation history.

    Args:
        conversation_id: Conversation ID
        user_id: User ID (for verification)

    Returns:
        List of messages in conversation
    """
    try:
        messages = AgentService.get_conversation_history(conversation_id, db)

        return {
            "status": "success",
            "conversation_id": str(conversation_id),
            "messages": messages,
            "total_messages": len(messages)
        }

    except Exception as e:
        return {"error": str(e)}


@app.get("/documents")
def get_documents(user_id: UUID, db: Session = Depends(get_db)):
    """
    Get accessible documents for the user.

    Args:
        user_id: User ID making the request

    Returns:
        List of accessible documents
    """
    try:
        # Get user and their role
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"error": "User not found"}

        documents = AgentService.get_documents(user.role, db)

        return {
            "status": "success",
            "documents": documents,
            "total_documents": len(documents),
            "user_role": user.role
        }

    except Exception as e:
        return {"error": str(e)}