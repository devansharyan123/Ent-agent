from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database.session import get_db
from services.conversation_service import start_conversation, send_message, get_history

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