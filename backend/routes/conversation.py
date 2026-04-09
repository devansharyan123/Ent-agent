from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from backend.database.session import get_db
from backend.services.conversation_service import (
    start_conversation,
    send_message,
    get_history,
    get_conversations_by_user
)

router = APIRouter(prefix="/chat", tags=["Chat"])


# ---------------- START CONVERSATION ----------------
@router.post("/start")
def start(user_id: str, db: Session = Depends(get_db)):
    try:
        conv = start_conversation(db, user_id)

        return {
            "conversation_id": str(conv.id),
            "title": conv.title,
            "created_at": conv.created_at
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------- SEND MESSAGE ----------------
@router.post("/message")
def message(conversation_id: str, question: str, role: str, db: Session = Depends(get_db)):
    try:
        msg = send_message(db, conversation_id, question, role)

        return {
            "question": msg.question,
            "answer": msg.answer
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------- GET CHAT HISTORY ----------------
@router.get("/history/{conversation_id}")
def history(conversation_id: str, db: Session = Depends(get_db)):
    try:
        messages = get_history(db, conversation_id)

        return [
            {
                "question": m.question,
                "answer": m.answer,
                "sequence_no": m.sequence_no
            }
            for m in messages
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------- GET USER CONVERSATIONS ----------------
@router.get("/user/{user_id}")
def get_user_conversations(user_id: str, db: Session = Depends(get_db)):
    try:
        conversations = get_conversations_by_user(db, user_id)

        return [
            {
                "conversation_id": str(c.id),
                "title": c.title,
                "created_at": c.created_at
            }
            for c in conversations
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))