"""Summarization tool for document chunks"""
from typing import List, Dict, Any
from langchain.tools import tool
from langchain_groq import ChatGroq
from backend.config import settings


@tool
def summarization_tool(text: str, max_length: int = 200) -> Dict[str, Any]:
    """
    Summarize provided text using LLM.

    Args:
        text: Text to summarize
        max_length: Maximum length of summary in words

    Returns:
        Dictionary with original text and summary
    """
    try:
        llm = ChatGroq(
            api_key=settings.groq_api_key,
            model_name=settings.llm_model,
            temperature=settings.agent_temperature
        )

        prompt = f"""Please provide a concise summary of the following text in at most {max_length} words:

{text}

Summary:"""

        response = llm.invoke(prompt)
        summary = response.content

        return {
            "status": "success",
            "original_length": len(text.split()),
            "summary": summary,
            "summary_length": len(summary.split())
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def get_summarization_tool():
    """Returns the summarization tool for LangChain agent"""
    return summarization_tool
