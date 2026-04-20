# backend/agents/tools/recommendation_tool.py - COMPLETE WORKING CODE

"""
Recommendation Tool — Tool #5 for Enterprise Knowledge Assistant

Performs document retrieval and uses Groq LLM to suggest related policies or documents.
Enforces role-based access control and logs to app.tool_logs.
"""

import json
import logging
import uuid
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional
import psycopg2
from langchain_groq import ChatGroq
import numpy as np

from backend.config import settings
from backend.agents.tools.policy_retrieval_tool import get_allowed_categories, _get_psycopg2_conn
from backend.services.vector_store import get_embedder

logger = logging.getLogger(__name__)


def _log_tool_call(
    conversation_id: Optional[str],
    tool_input: Dict,
    tool_output: Dict,
) -> None:
    """Insert a row into app.tool_logs for the recommendation tool."""
    try:
        conn = _get_psycopg2_conn()
        cur = conn.cursor()
        
        # Handle conversation_id - allow NULL
        valid_conversation_id = None
        if conversation_id:
            try:
                uuid.UUID(str(conversation_id))
                valid_conversation_id = str(conversation_id)
            except (ValueError, AttributeError):
                pass
        
        cur.execute(
            """
            INSERT INTO app.tool_logs
                (id, conversation_id, tool_name, tool_input, tool_output, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid.uuid4()),
                valid_conversation_id,
                "recommendation_tool",
                json.dumps(tool_input),
                json.dumps(tool_output),
                datetime.now(UTC),
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as exc:
        logger.warning(f"tool_logs insert failed (non-critical): {exc}")


def _get_document_chunks_for_recommendation(
    query_embedding: List[float], 
    allowed_categories: List[str], 
    top_k: int = 20
) -> List[Dict[str, Any]]:
    """
    Retrieve document chunks for recommendation using vector similarity.
    """
    conn = None
    try:
        conn = _get_psycopg2_conn()
        cur = conn.cursor()
        
        # Convert to numpy array for pgvector
        embedding_array = np.array(query_embedding, dtype=np.float32)
        
        logger.info(f"🔍 Searching in categories: {allowed_categories}")
        
        # Execute vector similarity search
        cur.execute(
            """
            SELECT
                dc.chunk_text,
                dc.chunk_index,
                dc.page_number,
                d.file_name,
                d.category,
                d.file_path,
                (re.embedding <=> %s::vector) as distance
            FROM vector_store.rag_embeddings re
            JOIN vector_store.document_chunks dc ON re.chunk_id = dc.id
            JOIN app.documents d ON dc.document_id = d.id
            WHERE d.category = ANY(%s)
              AND d.is_active = TRUE
            ORDER BY re.embedding <=> %s::vector
            LIMIT %s
            """,
            (embedding_array, allowed_categories, embedding_array, top_k),
        )
        
        rows = cur.fetchall()
        cur.close()
        
        # Log which categories were found
        categories_found = set()
        results = []
        for row in rows:
            category = row[4]
            categories_found.add(category)
            results.append({
                "chunk_text": row[0],
                "chunk_index": row[1],
                "page_number": row[2],
                "file_name": row[3],
                "category": category,
                "file_path": row[5] if len(row) > 5 else None,
                "distance": row[6] if len(row) > 6 else None
            })
        
        logger.info(f"✅ Retrieved {len(results)} chunks from categories: {categories_found}")
        
        # If payroll category is allowed but not found, log warning
        if 'payroll' in allowed_categories and 'payroll' not in categories_found:
            logger.warning("⚠️ Payroll category is allowed but no chunks were retrieved!")
            # Try to get payroll documents directly
            cur = conn.cursor()
            cur.execute(
                """
                SELECT COUNT(*) FROM app.documents 
                WHERE category = 'payroll' AND is_active = TRUE
                """
            )
            payroll_count = cur.fetchone()[0]
            logger.info(f"📊 Payroll documents in DB: {payroll_count}")
            cur.close()
        
        return results
        
    except Exception as e:
        logger.error(f"Vector search error: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()


def _generate_recommendation(query: str, chunks: List[Dict[str, Any]]) -> str:
    """
    Generate policy recommendations using Groq LLM.
    """
    if not chunks:
        return "- No relevant policies found to recommend based on your query."
    
    # Group chunks by document
    documents = {}
    for chunk in chunks:
        doc_name = chunk['file_name']
        category = chunk['category']
        if doc_name not in documents:
            documents[doc_name] = {
                'category': category,
                'chunks': []
            }
        documents[doc_name]['chunks'].append(chunk['chunk_text'])
    
    # Build context - prioritize payroll documents if query is about payroll
    payroll_keywords = ['payroll', 'salary', 'deduction', 'overtime', 'grievance', 'payment']
    is_payroll_query = any(keyword in query.lower() for keyword in payroll_keywords)
    
    # Sort documents: put payroll docs first if payroll query
    doc_items = list(documents.items())
    if is_payroll_query:
        doc_items.sort(key=lambda x: 0 if x[1]['category'] == 'payroll' else 1)
    
    context_parts = []
    for doc_name, doc_info in doc_items[:5]:  # Max 5 documents
        part = f"Document: {doc_name} (Category: {doc_info['category']})\n"
        # Take first 3 chunks per document
        for i, chunk in enumerate(doc_info['chunks'][:3]):
            chunk_preview = chunk[:350] + "..." if len(chunk) > 350 else chunk
            part += f"  [{i+1}] {chunk_preview}\n"
        context_parts.append(part)
    
    context = "\n".join(context_parts)
    
    # System prompt
    system_prompt = """You are an enterprise policy assistant. Based on the retrieved document excerpts, suggest relevant follow-up questions.

RULES:
1. Output ONLY bullet points - no introductions, no explanations
2. Each bullet MUST follow: "- Would you like to know more about [Policy Name]?"
3. Suggest 2-4 questions
4. Base recommendations on the actual documents retrieved
5. If the user asks about payroll, focus on payroll-related policies

Examples:
- Would you like to know more about Salary Disbursement Policy?
- Would you like to know more about Leave Encashment Policy?
- Would you like to know more about Overtime Calculation Policy?

Output ONLY the bullet points, nothing else!"""
    
    user_prompt = f"""User Query: {query}

Retrieved Documents:
{context}

Based on the user's query about "{query}", suggest relevant follow-up questions."""

    try:
        llm = ChatGroq(
            api_key=settings.groq_api_key,
            model_name=settings.llm_model,
            temperature=0.3,
            max_tokens=300,
        )
        
        response = llm.invoke([
            ("system", system_prompt),
            ("human", user_prompt)
        ])
        
        result = response.content.strip()
        
        # Ensure response starts with bullet
        if not result.startswith("-"):
            result = "- Would you like to know more about相关政策?\n" + result
        
        return result
        
    except Exception as e:
        logger.error(f"LLM recommendation failed: {str(e)}")
        return "- Unable to generate recommendations at this time. Please try again later."


def recommendation_tool(
    query: str,
    user_role: str,
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Main recommendation tool function.
    """
    
    tool_input = {
        "query": query,
        "user_role": user_role,
    }
    
    logger.info(f"🎯 Recommendation tool - Role: {user_role}, Query: {query[:100]}...")
    
    # Step 1: Get allowed categories
    try:
        allowed_categories = get_allowed_categories(user_role)
        logger.info(f"📋 Allowed categories for {user_role}: {allowed_categories}")
    except ValueError as exc:
        result = {
            "answer": f"Invalid user role: {user_role}",
            "sources": [],
            "retrieved_chunks": []
        }
        _log_tool_call(conversation_id, tool_input, result)
        return result
    
    # Step 2: Generate embedding
    try:
        embedder = get_embedder()
        query_embedding = embedder.encode(query, convert_to_numpy=True).tolist()
        logger.info("✅ Query embedding generated")
    except Exception as exc:
        logger.error(f"❌ Embedding failed: {exc}")
        result = {
            "answer": "I'm having trouble understanding your question. Please try again.",
            "sources": [],
            "retrieved_chunks": []
        }
        _log_tool_call(conversation_id, tool_input, result)
        return result
    
    # Step 3: Retrieve chunks
    try:
        chunks = _get_document_chunks_for_recommendation(
            query_embedding, 
            allowed_categories, 
            top_k=20
        )
        logger.info(f"✅ Retrieved {len(chunks)} chunks")
    except Exception as exc:
        logger.error(f"❌ Retrieval failed: {exc}")
        result = {
            "answer": "Unable to access documents. Please try again later.",
            "sources": [],
            "retrieved_chunks": []
        }
        _log_tool_call(conversation_id, tool_input, result)
        return result
    
    # Step 4: Handle no chunks
    if not chunks:
        result = {
            "answer": "No relevant policies found in your access scope.",
            "sources": [],
            "retrieved_chunks": [],
        }
        _log_tool_call(conversation_id, tool_input, result)
        return result
    
    # Step 5: Generate recommendations
    try:
        answer = _generate_recommendation(query, chunks)
        logger.info("✅ Recommendations generated")
    except Exception as exc:
        logger.error(f"❌ LLM failed: {exc}")
        answer = "- Unable to generate recommendations at this time."
    
    # Step 6: Extract unique sources
    seen = set()
    unique_sources = []
    for chunk in chunks:
        key = (chunk["file_name"], chunk["category"])
        if key not in seen:
            seen.add(key)
            unique_sources.append({
                "file_name": chunk["file_name"],
                "category": chunk["category"]
            })
    
    logger.info(f"📚 Sources found: {[s['category'] for s in unique_sources]}")
    
    # Step 7: Prepare result
    result = {
        "answer": answer,
        "sources": unique_sources,
        "retrieved_chunks": [c["chunk_text"][:200] + "..." for c in chunks[:5]],
    }
    
    # Step 8: Log
    _log_tool_call(
        conversation_id,
        tool_input,
        {
            "answer_preview": answer[:100],
            "sources_count": len(unique_sources),
            "categories_found": [s['category'] for s in unique_sources],
        },
    )
    
    return result


# =========================
# 🧪 TEST
# =========================
if __name__ == "__main__":
    import os
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    
    print("=" * 70)
    print("TESTING RECOMMENDATION TOOL AS HR")
    print("=" * 70)
    
    result = recommendation_tool(
        query="explain payroll policy",
        user_role="hr",  # HR role
        conversation_id=None
    )
    
    print(f"\n📋 RECOMMENDATIONS:")
    print(result['answer'])
    
    print(f"\n📚 SOURCES ({len(result['sources'])}):")
    for source in result['sources']:
        print(f"   • {source['file_name']} (Category: {source['category']})")