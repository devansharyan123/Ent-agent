from backend.database.models import Conversation, Message
from backend.services.external_knowledge_service import get_external_answer
from backend.agents.tools.policy_retrieval_tool import policy_retrieval_tool
import uuid
import logging

logger = logging.getLogger(__name__)


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
def send_message(db, conversation_id, question, role, tool="auto"):
    """
    tool: "auto" (default) = try RAG then fallback to LLM
          "rag" = policy-only (no LLM fallback)
          "llm" = LLM-only
    """
    conversation_id = uuid.UUID(str(conversation_id))

    # Get last sequence number
    last_msg = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.sequence_no.desc()).first()

    sequence_no = 1 if not last_msg else last_msg.sequence_no + 1

    answer = None

    if str(tool).lower() == "rag":
        # Strict policy-only path (no LLM fallback)
        try:
            rag_result = policy_retrieval_tool(
                query=question,
                user_role=role,
                top_k=5,
                conversation_id=str(conversation_id)
            )
            answer = (rag_result.get("answer") or "").strip()
            # If the tool explicitly returned the "no policy" sentinel, keep that message
            if not answer:
                answer = "No relevant policy found in your accessible document scope."
            # Optionally include sources for traceability
            sources = rag_result.get("sources", [])
            if sources:
                citations = []
                for s in sources:
                    fn = s.get("file_name", "Unknown")
                    pg = s.get("page_number")
                    if pg is not None:
                        citations.append(f"- {fn} (page {pg})")
                    else:
                        citations.append(f"- {fn}")
                answer = f"{answer}\n\nSources:\n" + "\n".join(citations)
        except Exception:
            logger.exception("Policy RAG failed (tool=rag); returning failure message without LLM fallback")
            answer = "Policy retrieval failed. Please try again later."

    elif str(tool).lower() == "llm":
        # Strict LLM-only path
        try:
            answer = get_external_answer(question, role)
        except Exception:
            logger.exception("LLM call failed (tool=llm)")
            answer = "LLM answer failed. Please try again later."

    else:
        # auto: try RAG first, fall back to LLM if no policy found or rag errors
        try:
            rag_result = policy_retrieval_tool(
                query=question,
                user_role=role,
                top_k=5,
                conversation_id=str(conversation_id)
            )
            rag_answer = (rag_result.get("answer") or "").strip()
            no_policy_messages = [
                "No relevant policy found in your accessible document scope.",
                "The requested policy information is not available in your accessible documents."
            ]
            if rag_answer and not any(msg in rag_answer for msg in no_policy_messages):
                sources = rag_result.get("sources", [])
                if sources:
                    citations = []
                    for s in sources:
                        fn = s.get("file_name", "Unknown")
                        pg = s.get("page_number")
                        if pg is not None:
                            citations.append(f"- {fn} (page {pg})")
                        else:
                            citations.append(f"- {fn}")
                    answer = f"{rag_answer}\n\nSources:\n" + "\n".join(citations)
                else:
                    answer = rag_answer
            else:
                logger.info("RAG returned no policy; falling back to external LLM")
                answer = get_external_answer(question, role)
        except Exception:
            logger.exception("RAG failed in auto mode; falling back to external LLM")
            try:
                answer = get_external_answer(question, role)
            except Exception:
                logger.exception("LLM fallback failed")
                answer = "Both policy retrieval and LLM failed. Please try again later."

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