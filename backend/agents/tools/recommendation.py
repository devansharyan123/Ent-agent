"""Document recommendation tool"""
from typing import Dict, Any, List
from langchain.tools import tool
from sqlalchemy import text
from backend.database.session import SessionLocal
from backend.services.rag_service import filter_docs_by_role


@tool
def recommendation_tool(query: str, user_role: str, top_k: int = 3) -> Dict[str, Any]:
    """
    Recommend relevant documents based on query and user role.

    Args:
        query: Search query or context
        user_role: User role for access control
        top_k: Number of recommendations to return

    Returns:
        List of recommended documents with metadata
    """
    db = SessionLocal()
    try:
        # Get all accessible documents for the user
        docs_query = text("""
            SELECT id, filename, category, description
            FROM app.documents
            ORDER BY created_at DESC
            LIMIT :limit
        """)

        results = db.execute(docs_query, {"limit": top_k * 2}).fetchall()

        documents = []
        for row in results:
            doc_data = {
                "id": str(row.id),
                "filename": row.filename,
                "category": row.category,
                "description": row.description or "",
                "relevance_score": 0.7  # Placeholder score
            }
            documents.append(doc_data)

        # Filter by user role
        filtered_docs = filter_docs_by_role(user_role, documents)

        # Return top recommendations
        recommendations = filtered_docs[:top_k]

        return {
            "status": "success",
            "query": query,
            "recommendations": recommendations,
            "total_found": len(recommendations)
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }
    finally:
        db.close()


def get_recommendation_tool():
    """Returns the recommendation tool for LangChain agent"""
    return recommendation_tool
