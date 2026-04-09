"""Document comparison tool"""
from typing import Dict, Any, List
from langchain.tools import tool
from langchain_groq import ChatGroq
from backend.config import settings
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.database.session import SessionLocal


@tool
def comparison_tool(document_ids: List[str]) -> Dict[str, Any]:
    """
    Compare multiple documents and identify similarities and differences.

    Args:
        document_ids: List of document IDs to compare

    Returns:
        Comparison analysis with similarities and differences
    """
    if not document_ids or len(document_ids) < 2:
        return {
            "status": "error",
            "error": "At least 2 documents required for comparison"
        }

    db = SessionLocal()
    try:
        # Fetch documents
        docs = []
        for doc_id in document_ids:
            query = text("""
                SELECT id, filename, category, file_path
                FROM app.documents
                WHERE id = :doc_id
            """)
            result = db.execute(query, {"doc_id": doc_id}).fetchone()
            if result:
                docs.append({
                    "id": str(result.id),
                    "filename": result.filename,
                    "category": result.category,
                    "file_path": result.file_path
                })

        if len(docs) < 2:
            return {
                "status": "error",
                "error": "Could not find all requested documents"
            }

        # Generate comparison using LLM
        llm = ChatGroq(
            api_key=settings.groq_api_key,
            model_name=settings.llm_model,
            temperature=settings.agent_temperature
        )

        doc_names = ", ".join([d["filename"] for d in docs])
        prompt = f"""Compare the following documents and identify key similarities and differences:

Documents: {doc_names}
Categories: {', '.join([d['category'] for d in docs])}

Please provide:
1. Key similarities
2. Key differences
3. Which document is more relevant for specific use cases
4. Any recommendations for usage"""

        response = llm.invoke(prompt)
        comparison = response.content

        return {
            "status": "success",
            "documents_compared": doc_names,
            "comparison": comparison
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }
    finally:
        db.close()


def get_comparison_tool():
    """Returns the comparison tool for LangChain agent"""
    return comparison_tool
