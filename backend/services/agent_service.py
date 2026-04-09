"""Agent service for orchestrating agent execution and database operations"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.database.session import SessionLocal
from backend.agents.brain import get_agent
from backend.config import settings


class AgentService:
    """Service layer for agent operations"""

    @staticmethod
    def create_conversation(user_id: UUID, db: Session) -> Dict[str, Any]:
        """Create a new conversation for a user"""
        try:
            conversation_id = str(uuid4())

            query = text("""
                INSERT INTO app.conversations (id, user_id)
                VALUES (:id, :user_id)
                RETURNING id
            """)

            result = db.execute(
                query,
                {
                    "id": conversation_id,
                    "user_id": str(user_id)
                }
            )
            db.commit()

            return {
                "status": "success",
                "conversation_id": conversation_id
            }
        except Exception as e:
            db.rollback()
            return {
                "status": "error",
                "error": str(e)
            }

    @staticmethod
    def get_or_create_conversation(user_id: UUID, conversation_id: Optional[UUID] = None, db: Session = None) -> str:
        """Get existing conversation or create a new one"""
        if db is None:
            db = SessionLocal()

        if conversation_id:
            # Check if conversation exists
            query = text("SELECT id FROM app.conversations WHERE id = :id AND user_id = :user_id")
            result = db.execute(query, {"id": str(conversation_id), "user_id": str(user_id)}).fetchone()
            if result:
                return str(conversation_id)

        # Create new conversation
        result = AgentService.create_conversation(user_id, db)
        if result["status"] == "success":
            return result["conversation_id"]
        raise Exception("Failed to create conversation")

    @staticmethod
    def get_conversation_history(conversation_id: UUID, db: Session = None) -> List[Dict[str, Any]]:
        """Retrieve conversation history"""
        if db is None:
            db = SessionLocal()

        try:
            query = text("""
                SELECT id, question, answer, sequence_no, created_at
                FROM app.messages
                WHERE conversation_id = :conversation_id
                ORDER BY sequence_no ASC
                LIMIT :limit
            """)

            results = db.execute(
                query,
                {
                    "conversation_id": str(conversation_id),
                    "limit": settings.max_conversation_history
                }
            ).fetchall()

            messages = []
            for row in results:
                messages.append({
                    "id": str(row.id),
                    "question": row.question,
                    "answer": row.answer,
                    "sequence_no": row.sequence_no,
                    "created_at": str(row.created_at)
                })

            return messages

        except Exception as e:
            return []

    @staticmethod
    def execute_query(user_id: UUID, conversation_id: UUID, query: str, user_role: str, db: Session = None) -> Dict[str, Any]:
        """Execute a query through the agent and store results"""
        if db is None:
            db = SessionLocal()

        try:
            # Get conversation history for context
            history = AgentService.get_conversation_history(conversation_id, db)

            # Execute agent
            agent = get_agent()
            agent_response = agent.execute(query, user_role, history)

            if agent_response["status"] != "success":
                return agent_response

            answer = agent_response["answer"]

            # Get the next sequence number
            seq_query = text("""
                SELECT MAX(sequence_no) as max_seq
                FROM app.messages
                WHERE conversation_id = :conversation_id
            """)
            seq_result = db.execute(seq_query, {"conversation_id": str(conversation_id)}).fetchone()
            next_seq = (seq_result.max_seq or 0) + 1

            # Store message
            message_id = str(uuid4())
            now = datetime.utcnow()

            insert_query = text("""
                INSERT INTO app.messages (id, conversation_id, question, answer, sequence_no, created_at)
                VALUES (:id, :conversation_id, :question, :answer, :sequence_no, :created_at)
                RETURNING id
            """)

            db.execute(
                insert_query,
                {
                    "id": message_id,
                    "conversation_id": str(conversation_id),
                    "question": query,
                    "answer": answer,
                    "sequence_no": next_seq,
                    "created_at": now
                }
            )

            # Cache the response
            AgentService.cache_query_result(query, answer, db)

            # Log tool usage if available
            AgentService.log_tool_usage("agent_query_executed", {"query": query}, {"answer": answer}, user_id, db)

            db.commit()

            return {
                "status": "success",
                "message_id": message_id,
                "conversation_id": str(conversation_id),
                "answer": answer,
                "sequence_no": next_seq
            }

        except Exception as e:
            db.rollback()
            return {
                "status": "error",
                "error": str(e)
            }

    @staticmethod
    def cache_query_result(query: str, answer: str, db: Session) -> bool:
        """Cache a query result"""
        try:
            cache_id = str(uuid4())
            now = datetime.utcnow()

            # Check if query already cached
            check_query = text("SELECT id FROM app.query_cache WHERE query = :query")
            existing = db.execute(check_query, {"query": query}).fetchone()

            if existing:
                # Update existing cache
                update_query = text("""
                    UPDATE app.query_cache
                    SET answer = :answer, hit_count = hit_count + 1, updated_at = :updated_at
                    WHERE query = :query
                """)
                db.execute(
                    update_query,
                    {
                        "query": query,
                        "answer": answer,
                        "updated_at": now
                    }
                )
            else:
                # Insert new cache
                insert_query = text("""
                    INSERT INTO app.query_cache (id, query, answer, hit_count, created_at)
                    VALUES (:id, :query, :answer, 1, :created_at)
                """)
                db.execute(
                    insert_query,
                    {
                        "id": cache_id,
                        "query": query,
                        "answer": answer,
                        "created_at": now
                    }
                )

            db.commit()
            return True

        except Exception as e:
            db.rollback()
            return False

    @staticmethod
    def log_tool_usage(tool_name: str, input_params: Dict, output: Dict, user_id: UUID, db: Session) -> bool:
        """Log tool usage for audit trail"""
        try:
            import json
            log_id = str(uuid4())
            now = datetime.utcnow()

            insert_query = text("""
                INSERT INTO app.tool_logs (id, user_id, tool_name, input_params, output, created_at)
                VALUES (:id, :user_id, :tool_name, :input_params, :output, :created_at)
            """)

            db.execute(
                insert_query,
                {
                    "id": log_id,
                    "user_id": str(user_id),
                    "tool_name": tool_name,
                    "input_params": json.dumps(input_params),
                    "output": json.dumps(output),
                    "created_at": now
                }
            )

            db.commit()
            return True

        except Exception as e:
            db.rollback()
            return False

    @staticmethod
    def get_documents(user_role: str, db: Session = None) -> List[Dict[str, Any]]:
        """Get accessible documents for a user role"""
        if db is None:
            db = SessionLocal()

        try:
            # Map role to categories
            role_categories = {
                "admin": ["admin", "hr", "general"],
                "hr": ["hr", "general"],
                "employee": ["general"]
            }

            categories = role_categories.get(user_role, ["general"])

            query = text("""
                SELECT id, filename, category, description, file_path, created_at
                FROM app.documents
                WHERE category = ANY(:categories)
                ORDER BY created_at DESC
            """)

            results = db.execute(query, {"categories": categories}).fetchall()

            documents = []
            for row in results:
                documents.append({
                    "id": str(row.id),
                    "filename": row.filename,
                    "category": row.category,
                    "description": row.description,
                    "created_at": str(row.created_at)
                })

            return documents

        except Exception as e:
            return []
