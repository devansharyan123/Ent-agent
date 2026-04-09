from backend.database.models import Conversation, Message


def start_conversation(db, user_id):
    convo = Conversation(user_id=user_id, title="New Chat")
    db.add(convo)
    db.commit()
    db.refresh(convo)

    return {"conversation_id": str(convo.id)}


def send_message(db, conversation_id, question):
    count = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).count()

    sequence_no = count + 1

    answer = f"AI response to: {question}"

    msg = Message(
        conversation_id=conversation_id,
        sequence_no=sequence_no,
        question=question,
        answer=answer
    )

    db.add(msg)
    db.commit()

    return {"answer": answer}


def get_history(db, conversation_id):
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.sequence_no).all()

    return [
        {"q": m.question, "a": m.answer}
        for m in messages
    ]
def get_conversations_by_user(db, user_id):
    conversations = db.query(Conversation).filter(
        Conversation.user_id == user_id
    ).order_by(Conversation.created_at.desc()).all()

    return conversations