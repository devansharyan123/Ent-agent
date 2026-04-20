"""
Summarization Tool — Tool #2 for Enterprise Knowledge Assistant

Performs document retrieval and end-to-end summarization using Groq LLM.
Enforces role-based access control and logs to app.tool_logs.
"""

import json
import logging
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional
from uuid import uuid4
import psycopg2
from langchain_groq import ChatGroq
import numpy as np

from backend.config import settings
from backend.agents.tools.policy_retrieval_tool import get_allowed_categories, _get_psycopg2_conn
from backend.services.vector_store import get_embedder

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Logging utilities
# ---------------------------------------------------------------------------

def _log_tool_call(
    conversation_id: Optional[str],
    tool_input: Dict,
    tool_output: Dict,
) -> None:
    """Insert a row into app.tool_logs for the summarization tool."""
    try:
        conn = _get_psycopg2_conn()
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
                "summarization_tool",
                json.dumps(tool_input),
                json.dumps(tool_output),
                datetime.now(UTC),
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as exc:  # pragma: no cover
        logger.warning("tool_logs insert failed: %s", exc)

# ---------------------------------------------------------------------------
# Vector retrieval
# ---------------------------------------------------------------------------

def _get_document_chunks_for_summary(query_embedding: List[float], allowed_categories: List[str], top_k: int = 15) -> List[Dict[str, Any]]:
    conn = _get_psycopg2_conn()
    try:
        cur = conn.cursor()
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
        cur.close()
        return [
            {
                "chunk_text":  row[0],
                "chunk_index": row[1],
                "page_number": row[2],
                "file_name":   row[3],
                "category":    row[4],
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"Vector search error: {str(e)}", exc_info=True)
        raise
    finally:
        conn.close()

# ---------------------------------------------------------------------------
# Summary generation
# ---------------------------------------------------------------------------

def _generate_summary(query: str, chunks: List[Dict[str, Any]]) -> str:
    # Group by file_name to structure the prompt better
    files = {}
    for c in chunks:
        fname = c.get('file_name', 'Unknown Document')
        if fname not in files:
            files[fname] = []
        files[fname].append(c)

    context_parts = []
    for fname, fchunks in files.items():
        # Sort chunks by naturally index/page to maintain continuity
        fchunks.sort(key=lambda x: (x.get('page_number') or 0, x.get('chunk_index') or 0))
        part = f"--- Document: {fname} ---\n"
        for cx in fchunks:
            part += f"{cx['chunk_text']}\n\n"
        context_parts.append(part)

    context = "".join(context_parts)

    system_prompt = (
        "You are an enterprise policy assistant.\n"
        "Your task is to analyze the provided policy excerpts and provide a structured, concise summary STRICTLY related to the user's request.\n"
        "IGNORE any excerpts or topics that do not directly relate to the user's intended topic.\n"
        "Highlight the key points, main rules, and critical information for that specific topic.\n"
        "Organize the summary logically, using clear headings or bullet points.\n"
        "Always mention the policy document names you are summarizing from.\n"
        "If none of the excerpts address the user's request, state that no relevant information was found."
    )

    user_prompt = f"User Request: {query}\n\nPolicy Excerpts:\n\n{context}\n\nPlease summarize ONLY the points related to the User Request."

    llm = ChatGroq(
        api_key=settings.groq_api_key,
        model_name=settings.llm_model,
        temperature=0.2, # slightly higher temp for summarization
    )

    response = llm.invoke([
        ("system", system_prompt),
        ("human", user_prompt)
    ])
    return response.content

# ---------------------------------------------------------------------------
# Main tool entry point
# ---------------------------------------------------------------------------

def summarization_tool(
    query: str,
    user_role: str,
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    tool_input = {
        "query": query,
        "user_role": user_role,
    }

    try:
        allowed_categories = get_allowed_categories(user_role)
    except ValueError as exc:
        result = {"answer": str(exc), "sources": [], "retrieved_chunks": []}
        _log_tool_call(conversation_id, tool_input, result)
        return result

    try:
        embedder = get_embedder()
        query_embedding = embedder.encode(query, convert_to_numpy=True).tolist()
    except Exception as exc:
        logger.error(f"Embedding failed: {exc}")
        result = {"answer": "Embedding error.", "sources": [], "retrieved_chunks": []}
        _log_tool_call(conversation_id, tool_input, result)
        return result

    try:
        # Increase top_k to get enough chunk content to form a good summary
        chunks = _get_document_chunks_for_summary(query_embedding, allowed_categories, top_k=20)
    except Exception as exc:
        logger.error(f"Retrieval failed: {exc}")
        result = {"answer": "Document search unavailable.", "sources": [], "retrieved_chunks": []}
        _log_tool_call(conversation_id, tool_input, result)
        return result

    if not chunks:
        result = {
            "answer": "No relevant policy documents found to summarize in your access scope.",
            "sources": [],
            "retrieved_chunks": [],
        }
        _log_tool_call(conversation_id, tool_input, result)
        return result

    try:
        answer = _generate_summary(query, chunks)
    except Exception as exc:
        logger.error(f"LLM summarization failed: {exc}")
        answer = "Summarization generation failed. Please try again."

    # Format sources for return payload
    seen = set()
    unique_sources = []
    for c in chunks:
        fname = c.get("file_name", "Unknown Document")
        cat = c.get("category", "general")
        key = (fname, cat)
        if key not in seen:
            seen.add(key)
            unique_sources.append({"file_name": fname, "category": cat})

    result = {
        "answer": answer,
        "sources": unique_sources,
        "retrieved_chunks": [c["chunk_text"] for c in chunks],
    }

    _log_tool_call(
        conversation_id,
        tool_input,
        {
            "answer": answer,
            "sources_count": len(unique_sources),
            "chunks_count": len(result["retrieved_chunks"]),
        },
    )

    return result