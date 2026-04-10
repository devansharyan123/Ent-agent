from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.services.conversation_service import (
    start_conversation,
    send_message,
    get_history,
    get_conversations_by_user,
    delete_conversation
)

router = APIRouter(prefix="/chat", tags=["Chat"])


# ---------------- START ----------------
@router.post("/start")
def start(user_id: str, db: Session = Depends(get_db)):
    conv = start_conversation(db, user_id)

    return {
        "conversation_id": str(conv.id),
        "title": conv.title
    }


# ---------------- MESSAGE ----------------
@router.post("/message")
def message(conversation_id: str, question: str, role: str, db: Session = Depends(get_db)):
    msg = send_message(db, conversation_id, question, role)

    return {
        "question": msg.question,
        "answer": msg.answer
    }


# ---------------- HISTORY ----------------
@router.get("/history/{conversation_id}")
def history(conversation_id: str, db: Session = Depends(get_db)):
    messages = get_history(db, conversation_id)

    return [
        {
            "question": m.question,
            "answer": m.answer
        }
        for m in messages
    ]


# ---------------- USER CONVERSATIONS ----------------
@router.get("/user/{user_id}")
def get_user_conversations(user_id: str, db: Session = Depends(get_db)):
    conversations = get_conversations_by_user(db, user_id)

    return [
        {
            "conversation_id": str(c.id),
            "title": c.title
        }
        for c in conversations
    ]


# ---------------- DELETE ----------------
@router.delete("/{conversation_id}")
def delete(conv_id: str = None, conversation_id: str = None, db: Session = Depends(get_db)):
    # support both param names
    cid = conversation_id or conv_id

    success = delete_conversation(db, cid)

    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {"message": "Deleted successfully"}