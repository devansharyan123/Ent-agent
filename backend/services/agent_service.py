"""
Agent Service — orchestrates query execution, conversation management,
caching and tool observability.

All document retrieval now delegates to policy_retrieval_tool which
enforces RBAC at the SQL level before any chunk is returned.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database.session import SessionLocal

logger = logging.getLogger(__name__)


class AgentService:
    """Service layer for agent operations."""

    # ------------------------------------------------------------------
    # Conversation management
    # ------------------------------------------------------------------

    @staticmethod
    def create_conversation(user_id: UUID, db: Session) -> Dict[str, Any]:
        """Create a new conversation row and return its id."""
        try:
            conversation_id = str(uuid4())
            db.execute(
                text("""
                    INSERT INTO app.conversations (id, user_id)
                    VALUES (:id, :user_id)
                """),
                {"id": conversation_id, "user_id": str(user_id)},
            )
            db.commit()
            return {"status": "success", "conversation_id": conversation_id}
        except Exception as exc:
            db.rollback()
            logger.error("create_conversation failed: %s", exc)
            return {"status": "error", "error": str(exc)}

    @staticmethod
    def get_or_create_conversation(
        user_id: UUID,
        conversation_id: Optional[UUID] = None,
        db: Session = None,
    ) -> str:
        """Return an existing conversation id or create a new one."""
        if db is None:
            db = SessionLocal()

        if conversation_id:
            row = db.execute(
                text("SELECT id FROM app.conversations WHERE id = :id AND user_id = :uid"),
                {"id": str(conversation_id), "uid": str(user_id)},
            ).fetchone()
            if row:
                return str(conversation_id)

        result = AgentService.create_conversation(user_id, db)
        if result["status"] == "success":
            return result["conversation_id"]
        raise RuntimeError("Failed to create conversation")

    @staticmethod
    def get_conversation_history(
        conversation_id: UUID,
        db: Session = None,
    ) -> List[Dict[str, Any]]:
        """Return ordered messages for a conversation (oldest first)."""
        if db is None:
            db = SessionLocal()
        try:
            rows = db.execute(
                text("""
                    SELECT id, question, answer, sequence_no, created_at
                    FROM app.messages
                    WHERE conversation_id = :cid
                    ORDER BY sequence_no ASC
                    LIMIT :lim
                """),
                {"cid": str(conversation_id), "lim": settings.max_conversation_history},
            ).fetchall()
            return [
                {
                    "id":          str(r.id),
                    "question":    r.question,
                    "answer":      r.answer,
                    "sequence_no": r.sequence_no,
                    "created_at":  str(r.created_at),
                }
                for r in rows
            ]
        except Exception as exc:
            logger.warning("get_conversation_history failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Core query execution
    # ------------------------------------------------------------------

    @staticmethod
    def execute_query(
        user_id: UUID,
        conversation_id: UUID,
        query: str,
        user_role: str,
        db: Session = None,
    ) -> Dict[str, Any]:
        """
        Run the policy retrieval tool, store the message, cache and log.

        Uses policy_retrieval_tool which enforces RBAC at the SQL level
        before any chunk is returned to this layer.
        """
        if db is None:
            db = SessionLocal()

        try:
            from backend.agents.tools.policy_retrieval_tool import policy_retrieval_tool

            # ---- RAG retrieval with RBAC ----------------------------------
            rag_result = policy_retrieval_tool(
                query=query,
                user_role=user_role,
                top_k=5,
                conversation_id=str(conversation_id),
            )
            answer  = rag_result["answer"]
            sources = rag_result["sources"]

            # ---- Persist message -----------------------------------------
            seq_row = db.execute(
                text("""
                    SELECT COALESCE(MAX(sequence_no), 0) AS max_seq
                    FROM app.messages
                    WHERE conversation_id = :cid
                """),
                {"cid": str(conversation_id)},
            ).fetchone()
            next_seq   = seq_row.max_seq + 1
            message_id = str(uuid4())
            now        = datetime.utcnow()

            db.execute(
                text("""
                    INSERT INTO app.messages
                        (id, conversation_id, question, answer, sequence_no, created_at)
                    VALUES (:id, :cid, :q, :a, :seq, :ts)
                """),
                {
                    "id":  message_id,
                    "cid": str(conversation_id),
                    "q":   query,
                    "a":   answer,
                    "seq": next_seq,
                    "ts":  now,
                },
            )

            # ---- Cache result --------------------------------------------
            AgentService._cache_query(query, answer, db)

            db.commit()

            return {
                "status":          "success",
                "message_id":      message_id,
                "conversation_id": str(conversation_id),
                "answer":          answer,
                "sources":         sources,
                "sequence_no":     next_seq,
            }

        except Exception as exc:
            db.rollback()
            logger.error("execute_query failed: %s", exc)
            return {"status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # Caching
    # ------------------------------------------------------------------

    @staticmethod
    def _cache_query(query: str, answer: str, db: Session) -> None:
        """Insert response into query_cache if not already present."""
        try:
            existing = db.execute(
                text("SELECT id FROM app.query_cache WHERE query_text = :qt"),
                {"qt": query},
            ).fetchone()
            if not existing:
                db.execute(
                    text("""
                        INSERT INTO app.query_cache
                            (id, user_id, query_text, response_text, created_at)
                        VALUES (:id, NULL, :qt, :rt, :ts)
                    """),
                    {
                        "id": str(uuid4()),
                        "qt": query,
                        "rt": answer,
                        "ts": datetime.utcnow(),
                    },
                )
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning("_cache_query failed: %s", exc)

    # ------------------------------------------------------------------
    # Document listing (for /documents endpoint)
    # ------------------------------------------------------------------

    @staticmethod
    def get_documents(user_role: str, db: Session = None) -> List[Dict[str, Any]]:
        """Return documents accessible to *user_role* (by category)."""
        if db is None:
            db = SessionLocal()

        role_categories: Dict[str, List[str]] = {
            "admin":    ["admin", "hr", "general"],
            "hr":       ["hr", "general"],
            "employee": ["general"],
        }
        categories = role_categories.get(user_role.lower(), ["general"])

        try:
            rows = db.execute(
                text("""
                    SELECT id, file_name, category, file_path, created_at
                    FROM app.documents
                    WHERE category = ANY(:cats) AND is_active = TRUE
                    ORDER BY created_at DESC
                """),
                {"cats": categories},
            ).fetchall()
            return [
                {
                    "id":         str(r.id),
                    "filename":   r.file_name,
                    "category":   r.category,
                    "created_at": str(r.created_at),
                }
                for r in rows
            ]
        except Exception as exc:
            logger.warning("get_documents failed: %s", exc)
            return []
