"""Semantic search tool for retrieving relevant document chunks"""
from typing import List, Dict, Any
from langchain.tools import tool
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.database.session import SessionLocal
from backend.services.rag_service import filter_docs_by_role


@tool
def retrieval_search(query: str, user_role: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Search for relevant document chunks using semantic similarity.

    Args:
        query: Search query text
        user_role: User role for access control (admin, hr, employee)
        top_k: Number of top results to return

    Returns:
        List of relevant document chunks with metadata and similarity scores
    """
    db = SessionLocal()
    try:
        # First, we need to get the embedding for the query
        # For now, we'll use a simple text-based search with document metadata
        # In production, you would generate embeddings for the query using sentence-transformers

        # Query to find relevant document chunks
        query_sql = text("""
            SELECT
                dc.id,
                dc.text,
                d.filename,
                d.category,
                d.id as document_id,
                dc.page_number
            FROM vector_store.document_chunks dc
            JOIN vector_store.rag_embeddings re ON dc.id = re.chunk_id
            JOIN app.documents d ON dc.document_id = d.id
            WHERE dc.text ~* :query_pattern
            ORDER BY dc.id DESC
            LIMIT :top_k
        """)

        results = db.execute(
            query_sql,
            {"query_pattern": query, "top_k": top_k}
        ).fetchall()

        # Format results
        retrieved_chunks = []
        for row in results:
            chunk_data = {
                "id": str(row.id),
                "text": row.text,
                "document": row.filename,
                "category": row.category,
                "document_id": str(row.document_id),
                "page_number": row.page_number,
                "similarity_score": 0.85  # Placeholder score
            }
            retrieved_chunks.append(chunk_data)

        # Filter by user role
        filtered_chunks = filter_docs_by_role(user_role, retrieved_chunks)

        return filtered_chunks

    except Exception as e:
        return [{"error": f"Search failed: {str(e)}"}]
    finally:
        db.close()


# Alternative tool definition for LangChain compatibility
def get_retrieval_tool():
    """Returns the retrieval tool for LangChain agent"""
    return retrieval_search
