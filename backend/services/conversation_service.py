from backend.database.models import Conversation, Message
from backend.services.external_knowledge_service import get_external_answer
import uuid


# ---------------- START CONVERSATION ----------------
def start_conversation(db, user_id):
    convo = Conversation(
        id=uuid.uuid4(),
        user_id=uuid.UUID(str(user_id)),
        title="New Chat"
    )

    db.add(convo)
    db.commit()
    db.refresh(convo)

    return convo


# ---------------- SEND MESSAGE ----------------
def send_message(db, conversation_id, question, role):
    conversation_id = uuid.UUID(str(conversation_id))

    # Get last sequence number
    last_msg = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.sequence_no.desc()).first()

    sequence_no = 1 if not last_msg else last_msg.sequence_no + 1

    # 🔥 External Knowledge (for now)
    answer = get_external_answer(question, role)

    msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        sequence_no=sequence_no,
        question=question,
        answer=answer
    )

    db.add(msg)

    # 🔥 UPDATE TITLE (IMPORTANT FIX)
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id
    ).first()

    if conversation and conversation.title == "New Chat":
        conversation.title = question[:40]

    db.commit()
    db.refresh(msg)

    return msg


# ---------------- GET HISTORY ----------------
def get_history(db, conversation_id):
    conversation_id = uuid.UUID(str(conversation_id))

    return db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.sequence_no).all()


# ---------------- GET USER CONVERSATIONS ----------------
def get_conversations_by_user(db, user_id):
    user_id = uuid.UUID(str(user_id))

    return db.query(Conversation).filter(
        Conversation.user_id == user_id
    ).order_by(Conversation.created_at.desc()).all()


# ---------------- DELETE CONVERSATION ----------------
def delete_conversation(db, conversation_id):
    conversation_id = uuid.UUID(str(conversation_id))

    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id
    ).first()

    if not conv:
        return False

    db.delete(conv)
    db.commit()
    return True