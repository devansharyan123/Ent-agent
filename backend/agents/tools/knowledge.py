"""Knowledge base/cache lookup tool"""
from typing import Dict, Any, Optional
from langchain.tools import tool
from sqlalchemy import text
from backend.database.session import SessionLocal


@tool
def knowledge_lookup(query: str) -> Dict[str, Any]:
    """
    Query the knowledge base/cache for previously answered questions.

    Args:
        query: Question text to search for

    Returns:
        Cached answer if found, None otherwise
    """
    db = SessionLocal()
    try:
        # Search for similar queries in the cache
        search_query = text("""
            SELECT answer, created_at, hit_count
            FROM app.query_cache
            WHERE query ILIKE :query
            ORDER BY hit_count DESC, created_at DESC
            LIMIT 1
        """)

        result = db.execute(search_query, {"query": f"%{query}%"}).fetchone()

        if result:
            # Update hit count
            update_query = text("""
                UPDATE app.query_cache
                SET hit_count = hit_count + 1
                WHERE query ILIKE :query
            """)
            db.execute(update_query, {"query": f"%{query}%"})
            db.commit()

            return {
                "status": "hit",
                "answer": result.answer,
                "cached_at": str(result.created_at),
                "hit_count": result.hit_count + 1
            }
        else:
            return {
                "status": "miss",
                "answer": None,
                "message": "No cached answer found for this query"
            }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }
    finally:
        db.close()


def get_knowledge_tool():
    """Returns the knowledge tool for LangChain agent"""
    return knowledge_lookup
