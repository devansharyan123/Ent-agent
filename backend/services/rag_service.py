from backend.database.session import SessionLocal
from backend.database.models import DocumentChunk, RagEmbedding, Document
from pgvector.sqlalchemy import Vector
from sentence_transformers import SentenceTransformer

ROLE_PERMISSIONS = {
    "admin": ["admin", "hr", "general"],
    "hr": ["hr", "general"],
    "employee": ["general"]
}

_embedder = None


def get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer("all-mpnet-base-v2")
    return _embedder


def retrieve_with_role_filter(query: str, user_role: str, top_k: int = 5):
    """
    1. Embed the query
    2. Search pgvector for similar chunks
    3. Filter by role permissions
    """
    user_role_normalized = str(user_role or "").strip().lower()
    allowed_categories = ROLE_PERMISSIONS.get(user_role_normalized, [])
    if not allowed_categories:
        return []

    db = SessionLocal()
    try:

        embedder = get_embedder()
        query_embedding = embedder.encode(query)

        embedding_count = db.query(RagEmbedding).count()
        if embedding_count == 0:
            return []
        results = db.query(
            DocumentChunk.chunk_text,
            Document.file_name,
            Document.category
        ).join(
            RagEmbedding, RagEmbedding.chunk_id == DocumentChunk.id
        ).join(
            Document, Document.id == DocumentChunk.document_id
        ).filter(
            Document.category.in_(allowed_categories),
            Document.is_active == True
        ).order_by(
            RagEmbedding.embedding.op('<->')(query_embedding)
        ).limit(top_k).all()

        formatted_results = [
            {
                "text": r[0],
                "source": r[1],
                "category": r[2]
            }
            for r in results
        ]

        return formatted_results

    except Exception as e:
        print(f"Error in retrieve_with_role_filter: {str(e)}")
        return []
    finally:
        db.close()