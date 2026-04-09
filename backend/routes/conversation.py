from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database.session import get_db
from backend.services.conversation_service import start_conversation, send_message, get_history,get_conversations_by_user

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/start")
def start(user_id: str, db: Session = Depends(get_db)):
    return start_conversation(db, user_id)


@router.post("/message")
def message(conversation_id: str, question: str, db: Session = Depends(get_db)):
    return send_message(db, conversation_id, question)


@router.get("/history/{conversation_id}")
def history(conversation_id: str, db: Session = Depends(get_db)):
    return get_history(db, conversation_id)
@router.get("/user/{user_id}")
def get_user_conversations(user_id: str, db: Session = Depends(get_db)):
    conversations = get_conversations_by_user(db, user_id)

    return [
        {
            "conversation_id": str(c.id),
            "title": c.title,
            "created_at": c.created_at
        }
        for c in conversations
    ]