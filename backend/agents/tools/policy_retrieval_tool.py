"""
Policy Retrieval Tool — Tool #1 for Enterprise Knowledge Assistant

Performs role-filtered vector similarity search against pgvector,
generates grounded answers via Groq LLM, and logs every invocation
to app.tool_logs for full observability.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
import re
import psycopg2
from langchain_groq import ChatGroq
from pgvector.psycopg2 import register_vector

from backend.config import settings
from backend.services.vector_store import get_embedder

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Access Matrix
# ---------------------------------------------------------------------------

_ROLE_CATEGORY_MAP: Dict[str, List[str]] = {
   "admin":    ["admin", "hr", "general", "leave", "payroll"],
    "hr":       ["hr", "general", "leave", "payroll"],
    "employee": ["general", "leave"],
}


def get_allowed_categories(role: str) -> List[str]:
    """
    Return the list of document categories accessible to *role*.

    Args:
        role: User role string (case-insensitive).

    Returns:
        List[str] of allowed category names.

    Raises:
        ValueError: If *role* is not a recognised value.
    """
    normalised = role.strip().lower() if role else ""
    if normalised not in _ROLE_CATEGORY_MAP:
        raise ValueError(
            f"Invalid role '{role}'. Must be one of: "
            + ", ".join(_ROLE_CATEGORY_MAP.keys())
        )
    return _ROLE_CATEGORY_MAP[normalised]


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_psycopg2_conn():
    """
    Open a raw psycopg2 connection with pgvector type registered.
    pgvector's <=> operator requires the Vector type adapter to be active;
    SQLAlchemy's text() binding does not automatically handle this.
    """
    try:
        # Strip the sqlalchemy dialect prefix if present
        db_url = settings.database_url.replace("postgresql+psycopg2://", "postgresql://")
        logger.info(f"Connecting to database: {db_url.split('@')[1] if '@' in db_url else db_url}")
        conn = psycopg2.connect(db_url)
        register_vector(conn)
        logger.info("Database connection established with pgvector")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {str(e)}", exc_info=True)
        raise


def _log_tool_call(
    conversation_id: Optional[str],
    tool_input: Dict,
    tool_output: Dict,
) -> None:
    """Insert a row into app.tool_logs (best-effort, never raises)."""
    try:
        conn = _get_psycopg2_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO app.tool_logs
                (id, conversation_id, tool_name, tool_input, tool_output, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid4()),
                str(conversation_id) if conversation_id else None,
                "policy_retrieval_tool",
                json.dumps(tool_input),
                json.dumps(tool_output),
                datetime.utcnow(),
            ),
        )
        cur.close()
        conn.close()
    except Exception as exc:  # pragma: no cover
        logger.warning("tool_logs insert failed: %s", exc)


# ---------------------------------------------------------------------------
# Core retrieval
# ---------------------------------------------------------------------------

def _vector_search(
    query_embedding: List[float],
    allowed_categories: List[str],
    top_k: int,
) -> List[Dict[str, Any]]:
    """
    Run role-filtered cosine similarity search using pgvector.

    The category filter (WHERE d.category = ANY(%s)) is applied BEFORE
    ranking so no unauthorised chunk is ever scored or returned.

    Args:
        query_embedding: 768-dim float list produced by the embedder.
        allowed_categories: Categories the requesting user may access.
        top_k: Maximum number of chunks to return.

    Returns:
        List of dicts with keys: chunk_text, chunk_index, page_number,
        file_name, category, file_path.
    """
    conn = _get_psycopg2_conn()
    try:
        cur = conn.cursor()
        logger.info(f"Executing vector search with categories: {allowed_categories}")

        # Convert embedding to proper numpy array for pgvector
        import numpy as np
        embedding_array = np.array(query_embedding, dtype=np.float32)

        cur.execute(
            """
            SELECT
                dc.chunk_text,
                dc.chunk_index,
                dc.page_number,
                d.file_name,
                d.category,
                d.file_path
            FROM vector_store.rag_embeddings  re
            JOIN vector_store.document_chunks dc ON re.chunk_id = dc.id
            JOIN app.documents                d  ON dc.document_id = d.id
            WHERE d.category = ANY(%s)
              AND d.is_active = TRUE
            ORDER BY re.embedding <=> %s::vector
            LIMIT %s
            """,
            (allowed_categories, embedding_array, top_k),
        )
        rows = cur.fetchall()
        logger.info(f"Vector search returned {len(rows)} chunks")
        cur.close()
        return [
            {
                "chunk_text":  row[0],
                "chunk_index": row[1],
                "page_number": row[2],
                "file_name":   row[3],
                "category":    row[4],
                "file_path":   row[5],
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"Vector search error: {str(e)}", exc_info=True)
        raise
    finally:
        conn.close()

def _normalize_answer(text: str) -> str:
    # Previously, this aggressively stripped bullets and newlines, ruining LLM formatting.
    # We now pass the LLM output basically raw, just stripping any literal 'Source: ...' hallucinated by the model.
    if not text:
        return text
    text = re.sub(r'(?i)\bSource:.*\n?', '', text)
    return text.strip()

def _generate_answer(query: str, chunks: List[Dict[str, Any]]) -> str:
    """
    Generate a grounded answer from retrieved chunks using Groq LLM.

    The prompt strictly instructs the model NOT to invent policy rules.
    """
    context_parts = []
    for c in chunks:
        context_parts.append(f"--- Document: {c['file_name']}, Page: {c['page_number']} ---\n{c['chunk_text']}\n")
    context = "\n".join(context_parts)

    system_prompt = (
        "You are an enterprise policy assistant.\n"
        "Answer the user's question using ONLY the provided policy excerpts.\n"
        "Do NOT invent or infer policy rules that are not present in the excerpts.\n"
        "When listing multiple rules, use bullet points clearly.\n"
        "Always mention the policy document name when referencing a rule.\n"
        "If the excerpts do not contain the answer, you must respond with exactly:\n"
        "The requested policy information is not available in your accessible documents."
    )

    user_prompt = f"Policy Excerpts:\n\n{context}\n\nQuestion: {query}"

    llm = ChatGroq(
        api_key=settings.groq_api_key,
        model_name=settings.llm_model,
        temperature=0.0,   # deterministic for policy answers
    )

    response = llm.invoke([
        ("system", system_prompt),
        ("human", user_prompt)
    ])
    return response.content



# ---------------------------------------------------------------------------
# Public Tool Function
# ---------------------------------------------------------------------------

def policy_retrieval_tool(
    query: str,
    user_role: str,
    top_k: int = 5,
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Primary RAG tool for the Enterprise Knowledge Assistant.

    Enforces RBAC, performs pgvector similarity search, generates a
    grounded answer, and writes an observability log to app.tool_logs.

    Args:
        query:           Natural-language question from the user.
        user_role:       Role of the requesting user (admin / hr / employee).
        top_k:           Number of chunks to retrieve (default 5).
        conversation_id: Optional conversation UUID for logging.

    Returns:
        {
            "answer":           str,
            "sources":          [{"file_name", "page_number",
                                  "chunk_index", "category"}, ...],
            "retrieved_chunks": [str, ...]
        }

    Security guarantees:
        - Chunks from categories outside the user's allowed set are
          NEVER fetched, scored, or returned.
        - File paths are stripped from the public return payload.
    """
    tool_input = {
        "query":    query,
        "user_role": user_role,
        "top_k":    top_k,
    }

    # --- Step 1: resolve allowed categories (raises on invalid role) -------
    try:
        allowed_categories = get_allowed_categories(user_role)
    except ValueError as exc:
        result = {
            "answer":           str(exc),
            "sources":          [],
            "retrieved_chunks": [],
        }
        _log_tool_call(conversation_id, tool_input, result)
        return result

    # --- Step 2: embed query -----------------------------------------------
    try:
        logger.info(f"Encoding query: {query[:50]}...")
        embedder = get_embedder()
        query_embedding = embedder.encode(query, convert_to_numpy=True).tolist()
        logger.info(f"Query embedding generated: {len(query_embedding)} dimensions")
    except Exception as exc:
        logger.error(f"Embedding failed: {exc}", exc_info=True)
        result = {
            "answer":           f"Embedding service error: {str(exc)[:100]}",
            "sources":          [],
            "retrieved_chunks": [],
        }
        _log_tool_call(conversation_id, tool_input, result)
        return result

    # --- Step 3: role-filtered vector search --------------------------------
    try:
        chunks = _vector_search(query_embedding, allowed_categories, top_k)
    except Exception as exc:
        logger.error("Vector search failed: %s", exc)
        result = {
            "answer":           "Document search temporarily unavailable.",
            "sources":          [],
            "retrieved_chunks": [],
        }
        _log_tool_call(conversation_id, tool_input, result)
        return result

    # --- No authorised chunks found ----------------------------------------
    if not chunks:
        result = {
            "answer": (
                "No relevant policy found in your accessible document scope."
            ),
            "sources":          [],
            "retrieved_chunks": [],
        }
        _log_tool_call(conversation_id, tool_input, result)
        return result

    # --- Step 4: generate grounded answer -----------------------------------
    try:
        answer = _generate_answer(query, chunks)
    except Exception as exc:
        logger.error("LLM generation failed: %s", exc)
        answer = "Answer generation failed. Please try again."
    answer = _normalize_answer(answer)
    # Build response (file_path intentionally excluded from sources)
    sources = [
        {
            "file_name":   c["file_name"],
            "page_number": c["page_number"],
            "chunk_index": c["chunk_index"],
            "category":    c["category"],
        }
        for c in chunks
    ]
    retrieved_texts = [c["chunk_text"] for c in chunks]

    result = {
        "answer":           answer,
        "sources":          sources,
        "retrieved_chunks": retrieved_texts,
    }

    # --- Step 5: observability log ------------------------------------------
    _log_tool_call(
        conversation_id,
        tool_input,
        {
            "answer":        answer,
            "sources_count": len(sources),
            "chunks_count":  len(retrieved_texts),
        },
    )

    return result
