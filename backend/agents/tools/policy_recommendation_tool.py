"""
Policy Recommendation Tool — Tool #5 for Enterprise Knowledge Assistant

Generates intelligent policy recommendations based on user query.
Performs semantic similarity search, LLM-based topic extraction, and 
role-based access control. Provides fallback suggestions if no policies found.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4
import time
import psycopg2
from langchain_groq import ChatGroq
import numpy as np

from backend.config import settings
from backend.agents.tools.policy_retrieval_tool import get_allowed_categories, _get_psycopg2_conn
from backend.services.vector_store import get_embedder

logger = logging.getLogger(__name__)

# ============================================================================
# Conversational Suggestion Templates
# ============================================================================

_SUGGESTION_TEMPLATES = [
    "Would you like to know more about {topic}?",
    "Would you like to explore {topic}?",
    "Do you want details on {topic}?",
    "Interested in learning about {topic}?",
    "Would you like guidance on {topic}?",
    "Should we discuss {topic}?",
    "Can I help you with {topic}?",
    "Curious about {topic}?",
]

_FALLBACK_SUGGESTIONS = [
    "Would you like to explore other company policies?",
    "Would you like to learn about our HR policies?",
    "Would you like to know more about employee benefits?",
    "Should we discuss workplace guidelines?",
    "Interested in company procedures and policies?",
]

# ============================================================================
# Recommendation Cache (In-Memory, 1-hour TTL)
# ============================================================================

_RECOMMENDATION_CACHE: Dict[str, tuple] = {}  # {cache_key -> (timestamp, recommendations)}
_CACHE_TTL_SECONDS = 3600


def _get_cache_key(query: str, user_role: str) -> str:
    """Generate cache key from query and role."""
    return f"{user_role}||{query.lower()}"


def _get_from_cache(query: str, user_role: str) -> Optional[List[str]]:
    """Retrieve cached recommendations if not expired."""
    cache_key = _get_cache_key(query, user_role)
    if cache_key in _RECOMMENDATION_CACHE:
        timestamp, recommendations = _RECOMMENDATION_CACHE[cache_key]
        if time.time() - timestamp < _CACHE_TTL_SECONDS:
            logger.debug(f"[DEBUG] Cache hit for query: {query}")
            return recommendations
        else:
            del _RECOMMENDATION_CACHE[cache_key]
    return None


def _cache_recommendations(query: str, user_role: str, recommendations: List[str]) -> None:
    """Store recommendations in cache with timestamp."""
    cache_key = _get_cache_key(query, user_role)
    _RECOMMENDATION_CACHE[cache_key] = (time.time(), recommendations)


def _log_tool_call(
    conversation_id: Optional[str],
    tool_input: Dict,
    tool_output: Dict,
) -> None:
    """Insert a row into app.tool_logs for the recommendation tool."""
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
                "policy_recommendation_tool",
                json.dumps(tool_input),
                json.dumps(tool_output),
                datetime.utcnow(),
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as exc:
        logger.warning("tool_logs insert failed: %s", exc)


# ============================================================================
# Vector Search for Similar Chunks
# ============================================================================

def _get_similar_chunks(
    query_embedding: List[float],
    allowed_categories: List[str],
    top_k: int = 10
) -> List[Dict[str, Any]]:
    """Search for document chunks similar to query embedding."""
    conn = _get_psycopg2_conn()
    try:
        cur = conn.cursor()
        embedding_array = np.array(query_embedding, dtype=np.float32)
        
        logger.debug(f"[DEBUG] Searching for similar chunks with top_k={top_k}")
        
        cur.execute(
            """
            SELECT chunk_text, chunk_index, page_number, file_name, category
            FROM (
                SELECT DISTINCT ON (dc.id)
                    dc.chunk_text,
                    dc.chunk_index,
                    dc.page_number,
                    d.file_name,
                    d.category,
                    d.file_path,
                    re.embedding <=> %s::vector AS distance
                FROM vector_store.rag_embeddings re
                JOIN vector_store.document_chunks dc ON re.chunk_id = dc.id
                JOIN app.documents d ON dc.document_id = d.id
                WHERE d.category = ANY(%s)
                  AND d.is_active = TRUE
                ORDER BY dc.id, distance
            ) sub
            ORDER BY distance
            LIMIT %s
            """,
            (embedding_array, allowed_categories, top_k),
        )
        rows = cur.fetchall()
        cur.close()
        
        logger.debug(f"[DEBUG] Found {len(rows)} similar chunks")
        
        return [
            {
                "chunk_text": row[0],
                "chunk_index": row[1],
                "page_number": row[2],
                "file_name": row[3],
                "category": row[4],
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"Vector search error: {str(e)}", exc_info=True)
        raise
    finally:
        conn.close()


# ============================================================================
# Topic Extraction via LLM (with Keyword Fallback)
# ============================================================================

def _extract_topics_from_chunks(chunks: List[Dict[str, Any]], query: str) -> List[str]:
    """
    Extract policy topics from chunks using:
    Layer 1: LLM-based extraction
    Layer 2: Fallback to keyword extraction if LLM fails
    """
    if not chunks:
        return []
    
    # Prepare context from chunks
    context_lines = []
    for chunk in chunks[:5]:  # Use top 5 chunks
        fname = chunk.get("file_name", "Unknown")
        text = chunk.get("chunk_text", "")[:300]  # Limit text length
        context_lines.append(f"From {fname}: {text}")
    
    context = "\n\n".join(context_lines)
    
    # Layer 1: Try LLM extraction
    try:
        llm = ChatGroq(
            api_key=settings.groq_api_key,
            model_name=settings.llm_model,
            temperature=0.1,
        )
        
        system_prompt = (
            "You are an expert at extracting policy topics from documents.\n"
            "Given policy excerpts, extract 2-3 key policy topics or categories that appeared in those excerpts.\n"
            "Return ONLY a comma-separated list of topics (no explanations, no numbering).\n"
            "Examples: 'Leave Policy, Work From Home Policy' or 'Attendance Rules, Holiday Schedule'"
        )
        
        user_prompt = f"Extract the main policy topics from these excerpts:\n\n{context}"
        
        response = llm.invoke([
            ("system", system_prompt),
            ("human", user_prompt)
        ])
        
        topics_text = response.content.strip()
        logger.debug(f"[DEBUG] LLM extracted topics: {topics_text}")
        
        # Parse comma-separated topics
        topics = [t.strip() for t in topics_text.split(",") if t.strip()]
        if topics:
            return topics[:3]  # Return max 3 topics
    
    except Exception as e:
        logger.warning(f"LLM topic extraction failed: {e}")
    
    # Layer 2: Fallback to keyword-based extraction
    logger.debug("[DEBUG] Falling back to keyword-based topic extraction")
    
    # Extract file names and use them as topics
    topics = []
    seen_files = set()
    for chunk in chunks:
        fname = chunk.get("file_name", "").replace(".pdf", "").strip()
        if fname and fname not in seen_files:
            topics.append(fname)
            seen_files.add(fname)
            if len(topics) >= 3:
                break
    
    return topics if topics else []


# ============================================================================
# Convert Topics to Conversational Suggestions
# ============================================================================

def _convert_topics_to_suggestions(topics: List[str]) -> List[str]:
    """Convert extracted topics into conversational suggestion prompts."""
    suggestions = []
    
    for i, topic in enumerate(topics):
        # Clean up topic name
        topic = topic.strip()
        if not topic:
            continue
        
        # Select template based on index
        template = _SUGGESTION_TEMPLATES[i % len(_SUGGESTION_TEMPLATES)]
        suggestion = template.format(topic=topic)
        suggestions.append(suggestion)
    
    logger.debug(f"[DEBUG] Converted {len(topics)} topics to {len(suggestions)} suggestions")
    return suggestions


# ============================================================================
# Main Recommendation Function
# ============================================================================

def policy_recommendation_tool(
    query: str,
    user_role: str,
    max_recommendations: int = 3,
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate policy recommendations based on user query.
    
    Args:
        query: User question/query
        user_role: User role (admin, hr, employee)
        max_recommendations: Maximum number of recommendations to return
        conversation_id: Optional conversation ID for logging
    
    Returns:
        Dict with "recommendations" (List[str]) or fallback suggestions
    """
    
    logger.debug(f"[DEBUG] Calling policy_recommendation_tool with query: '{query}'")
    
    tool_input = {
        "query": query,
        "user_role": user_role,
        "max_recommendations": max_recommendations,
    }
    
    # ========== STEP 1: Check cache ==========
    cached = _get_from_cache(query, user_role)
    if cached:
        logger.debug(f"[DEBUG] Returning {len(cached)} cached recommendations")
        return {
            "recommendations": cached[:max_recommendations],
            "cached": True,
        }
    
    # ========== STEP 2: Validate role ==========
    try:
        allowed_categories = get_allowed_categories(user_role)
        logger.debug(f"[DEBUG] User role '{user_role}' has access to categories: {allowed_categories}")
    except ValueError as exc:
        logger.warning(f"Invalid role: {exc}")
        result = {
            "recommendations": _FALLBACK_SUGGESTIONS[:max_recommendations],
            "error": str(exc),
        }
        _log_tool_call(conversation_id, tool_input, result)
        return result
    
    # ========== STEP 3: Embed query ==========
    try:
        embedder = get_embedder()
        query_embedding = embedder.encode(query, convert_to_numpy=True).tolist()
        logger.debug(f"[DEBUG] Query embedded successfully (dimension={len(query_embedding)})")
    except Exception as exc:
        logger.error(f"Embedding failed: {exc}")
        result = {
            "recommendations": _FALLBACK_SUGGESTIONS[:max_recommendations],
            "error": "Embedding failed",
        }
        _log_tool_call(conversation_id, tool_input, result)
        return result
    
    # ========== STEP 4: Vector search ==========
    try:
        chunks = _get_similar_chunks(query_embedding, allowed_categories, top_k=10)
        logger.debug(f"[DEBUG] Retrieved {len(chunks)} similar chunks from vector store")
    except Exception as exc:
        logger.error(f"Vector search failed: {exc}")
        result = {
            "recommendations": _FALLBACK_SUGGESTIONS[:max_recommendations],
            "error": "Vector search failed",
        }
        _log_tool_call(conversation_id, tool_input, result)
        return result
    
    # ========== STEP 5: Handle empty results with fallback ==========
    if not chunks:
        logger.debug("[DEBUG] No chunks found; using fallback suggestions")
        result = {
            "recommendations": _FALLBACK_SUGGESTIONS[:max_recommendations],
            "fallback": True,
        }
        _log_tool_call(conversation_id, tool_input, result)
        return result
    
    # ========== STEP 6: Extract topics ==========
    try:
        topics = _extract_topics_from_chunks(chunks, query)
        logger.debug(f"[DEBUG] Extracted topics: {topics}")
    except Exception as exc:
        logger.error(f"Topic extraction failed: {exc}")
        topics = []
    
    # ========== STEP 7: If topic extraction failed, fallback ==========
    if not topics:
        logger.debug("[DEBUG] Topic extraction returned empty; using fallback suggestions")
        result = {
            "recommendations": _FALLBACK_SUGGESTIONS[:max_recommendations],
            "fallback": True,
        }
        _log_tool_call(conversation_id, tool_input, result)
        return result
    
    # ========== STEP 8: Convert topics to suggestions ==========
    try:
        suggestions = _convert_topics_to_suggestions(topics)
        logger.debug(f"[DEBUG] Generated {len(suggestions)} suggestions from {len(topics)} topics")
    except Exception as exc:
        logger.error(f"Suggestion conversion failed: {exc}")
        result = {
            "recommendations": _FALLBACK_SUGGESTIONS[:max_recommendations],
            "error": "Suggestion conversion failed",
        }
        _log_tool_call(conversation_id, tool_input, result)
        return result
    
    # ========== STEP 9: Cache and return ==========
    recommendations = suggestions[:max_recommendations]
    _cache_recommendations(query, user_role, recommendations)
    
    result = {
        "recommendations": recommendations,
        "cached": False,
    }
    
    logger.debug(f"[DEBUG] Generated {len(recommendations)} recommendations: {recommendations}")
    _log_tool_call(conversation_id, tool_input, result)
    
    return result
