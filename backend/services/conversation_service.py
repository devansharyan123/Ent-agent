
from backend.database.models import Conversation, Message
from backend.services.external_knowledge_service import get_external_answer
from backend.agents.tools.policy_retrieval_tool import policy_retrieval_tool
from backend.agents.tools.summarization_tool import summarization_tool
from backend.agents.tools.comparison_tool import comparison_tool
from backend.agents.tools.recommendation_tool import recommendation_tool
from backend.agents.brain import get_agent
import uuid
import logging

logger = logging.getLogger(__name__)


# ---------------- HELPER: FORMAT SOURCES ----------------
def format_sources(sources):
    """
    Centralized source formatting (FIXES ALL TEST FAILURES)
    """
    if not sources or not isinstance(sources, list):
        return ""

    formatted = []

    for s in sources:
        if not isinstance(s, dict):
            continue

        file_name = s.get("file_name", "Unknown")
        page = s.get("page_number")

        # 🔥 CRITICAL FIX (handles page=0 correctly)
        if page is not None:
            formatted.append(f"- {file_name} (page {page})")
        else:
            formatted.append(f"- {file_name}")

    if not formatted:
        return ""

    return "\n\nSources:\n" + "\n".join(formatted)


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
    conversation_id = uuid.UUID(str(conversation_id))

    last_msg = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.sequence_no.desc()).first()

    sequence_no = 1 if not last_msg else last_msg.sequence_no + 1

    answer = None

    # =========================
    # RAG ONLY
    # =========================
    if str(tool).lower() == "rag":
        try:
            rag_result = policy_retrieval_tool(
                query=question,
                user_role=role,
                top_k=5,
                conversation_id=str(conversation_id)
            )

            base_answer = (rag_result.get("answer") or "").strip()

            if not base_answer:
                base_answer = "No relevant policy found in your accessible document scope."

            sources_block = format_sources(rag_result.get("sources"))

            answer = base_answer + sources_block

        except Exception:
            logger.exception("RAG failed")
            answer = "Policy retrieval failed. Please try again later."


    # =========================
    # LLM ONLY
    # =========================
    elif str(tool).lower() == "llm":
        try:
            answer = get_external_answer(question, role)
        except Exception:
            logger.exception("LLM failed")
            answer = "LLM answer failed. Please try again later."


    # =========================
    # SUMMARY TOOL
    # =========================
    elif str(tool).lower() == "summary":
        try:
            summary_result = summarization_tool(
                query=question,
                user_role=role,
                conversation_id=str(conversation_id)
            )

            base_answer = (summary_result.get("answer") or "").strip()

            if not base_answer:
                base_answer = "No relevant policy documents found to summarize."

            sources_block = format_sources(summary_result.get("sources"))

            answer = base_answer + sources_block

        except Exception:
            logger.exception("Summary failed")
            answer = "Document summarization failed."


    # =========================
    # COMPARE TOOL
    # =========================
    elif str(tool).lower() == "compare":
        try:
            compare_result = comparison_tool(
                query=question,
                user_role=role,
                conversation_id=str(conversation_id)
            )

            answer = (compare_result.get("answer") or "").strip()

            if not answer:
                answer = "No relevant comparison could be generated."

            sources_block = format_sources(compare_result.get("sources"))
            answer = answer + sources_block

        except Exception:
            logger.exception("Comparison failed")
            answer = "Comparison failed. Please try again later."

    elif str(tool).lower() == "recommend":
        # Recommendation Tool
        try:
            recommend_result = recommendation_tool(
                query=question,
                user_role=role,
                conversation_id=str(conversation_id)
            )
            answer = (recommend_result.get("answer") or "").strip()
            if not answer:
                answer = "No relevant policy documents found to recommend in your access scope."
            sources = recommend_result.get("sources", [])
            if sources:
                citations = []
                for s in sources:
                    fn = s.get("file_name", "Unknown")
                    citations.append(f"- {fn}")
                answer = f"{answer}\n\nSources:\n" + "\n".join(citations)
        except Exception:
            logger.exception("Recommendation sequence failed (tool=recommend)")
            answer = "Document recommendation failed. Please try again later."

    elif str(tool).lower() == "agent":
        try:
            agent_result = get_agent().execute(query=question, user_role=role)
            answer = agent_result.get("answer", "Agent failed to generate an answer.")
            if not answer or not answer.strip():
                answer = "Agent generated an empty response."
        except Exception:
            logger.exception("Agent call failed (tool=agent)")
            answer = "Agent processing failed. Please try again later."

            result = get_agent().execute(query=question, user_role=role)
            answer = result.get("answer", "Agent failed")

        except Exception:
            logger.exception("Agent failed")
            answer = "Agent processing failed."


    # =========================
    # AUTO MODE
    # =========================
    else:
        try:
            rag_result = policy_retrieval_tool(
                query=question,
                user_role=role,
                top_k=5,
                conversation_id=str(conversation_id)
            )

            rag_answer = (rag_result.get("answer") or "").strip()

            if rag_answer:
                sources_block = format_sources(rag_result.get("sources"))
                answer = rag_answer + sources_block
            else:
                answer = get_external_answer(question, role)

        except Exception:
            logger.exception("Auto failed → fallback LLM")
            try:
                answer = get_external_answer(question, role)
            except Exception:
                answer = "Both RAG and LLM failed."

    is_external_tool = str(tool).lower() in ["llm", "recommend"]
    
    # We show recommendations only if:
    # 1. It is not an external-only tool (like pure LLM)
    # 2. It is not the recommendation tool itself
    # 3. We didn't fall back to LLM in auto mode (if answer contains the fallback string)
    no_policy_messages = [
        "No relevant policy found in your accessible document scope.",
        "The requested policy information is not available in your accessible documents."
    ]
    is_fallback = any(msg in (answer or "") for msg in no_policy_messages)
    
    if not is_external_tool and not is_fallback and answer:
        try:
            recommend_result = recommendation_tool(
                query=question,
                user_role=role,
                conversation_id=str(conversation_id)
            )
            rec_text = (recommend_result.get("answer") or "").strip()
            
            # Additional check: don't append if the tool basically said 'no topics found'
            if rec_text and "no relevant policy documents found" not in rec_text.lower():
                header = "### Other questions you would like to know about"
                answer = f"{answer}\n\n{header}\n{rec_text}"
        except Exception:
            logger.warning("Failed to append recommendations to response")

    msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        sequence_no=sequence_no,
        question=question,
        answer=answer
    )

    db.add(msg)

    # UPDATE TITLE
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


# ---------------- DELETE ----------------
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

