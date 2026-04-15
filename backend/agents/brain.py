"""
Agent Brain — LangChain/LangGraph ReAct agent.

Two tools are registered: policy_retrieval_tool and summarization_tool.
The comparison_tool is also added as Tool #4.
All other legacy tools (retrieval, knowledge, recommendation) remain removed.
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from backend.config import settings
from backend.agents.tools.policy_retrieval_tool import policy_retrieval_tool as _policy_fn
from backend.agents.tools.summarization_tool import summarization_tool as _summary_fn
from backend.agents.tools.comparison_tool import comparison_tool as _compare_fn
from backend.agents.tools.recommendation_tool import recommendation_tool as _recommend_fn

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LangChain @tool wrapper
# ---------------------------------------------------------------------------

@tool
def search_policy(query: str, user_role: str = "employee") -> str:
    """
    Search company policy documents and return a grounded answer.

    Use this whenever the user asks about any company policy, rule,
    procedure, leave entitlement, HR guideline, or admin regulation.

    Args:
        query:     The user's question about company policy.
        user_role: The role of the requesting user
                   (admin | hr | employee).  Defaults to 'employee'.

    Returns:
        JSON string containing: answer, sources, retrieved_chunks.
    """
    import json
    try:
        result = _policy_fn(query=query, user_role=user_role, top_k=5)
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        logger.error("search_policy tool error: %s", exc)
        return json.dumps({"answer": f"Tool error: {exc}", "sources": [], "retrieved_chunks": []})


@tool
def summarize_document(query: str, user_role: str = "employee") -> str:
    """
    Summarize a specified company policy document.

    Use this whenever the user explicitly asks for a summary or an overview
    of a document or policy category (e.g., "summarize the leave policy").

    Args:
        query:     The user's summarization request.
        user_role: The role of the requesting user. Defaults to 'employee'.

    Returns:
        JSON string containing: answer, sources, retrieved_chunks.
    """
    import json
    try:
        result = _summary_fn(query=query, user_role=user_role)
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        logger.error("summarize_document tool error: %s", exc)
        return json.dumps({"answer": f"Tool error: {exc}", "sources": [], "retrieved_chunks": []})


@tool
def compare_policies(query: str, user_role: str = "employee") -> str:
    """
    Compare two company policies or documents.

    Use this whenever the user explicitly asks to compare two things
    or highlight differences between policies (e.g., "Compare X and Y").

    Args:
        query:     The user's comparison request.
        user_role: The role of the requesting user. Defaults to 'employee'.

    Returns:
        JSON string containing: answer, sources, retrieved_chunks.
    """
    import json
    try:
        result = _compare_fn(query=query, user_role=user_role)
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        logger.error("compare_policies tool error: %s", exc)
        return json.dumps({"answer": f"Tool error: {exc}", "sources": [], "retrieved_chunks": []})

        return json.dumps({"answer": f"Tool error: {exc}", "sources": [], "retrieved_chunks": []})


@tool
def recommend_policies(query: str, user_role: str = "employee") -> str:
    """
    Recommend or suggest policies and documents related to a topic.

    Use this whenever the user asks for suggestions, recommendations, or related 
    policies (e.g., "suggest policies about remote work" or "what other policies are related to leave?").

    Args:
        query:     The user's recommendation request.
        user_role: The role of the requesting user. Defaults to 'employee'.

    Returns:
        JSON string containing: answer, sources, retrieved_chunks.
    """
    import json
    try:
        result = _recommend_fn(query=query, user_role=user_role)
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        logger.error("recommend_policies tool error: %s", exc)
        return json.dumps({"answer": f"Tool error: {exc}", "sources": [], "retrieved_chunks": []})
# ---------------------------------------------------------------------------
# AgentBrain
# ---------------------------------------------------------------------------

class AgentBrain:
    """Thin orchestrator that wraps the LangGraph ReAct agent."""

    _SYSTEM_PROMPT = (
        "You are an Enterprise Policy Assistant for Artemis.\n"
        "Your ONLY authoritative sources of information are the search_policy, summarize_document, compare_policies, and recommend_policies tools.\n\n"
        "Rules:\n"
        "1. For any question about company policy, HR rules, leave, payroll, "
        "   IT security, or admin procedures — call search_policy first.\n"
        "2. If the user explicitly asks to summarize or give an overview of a document, call summarize_document.\n"
        "3. If the user explicitly asks to compare two things, call compare_policies.\n"
        "4. If the user asks for suggestions, recommendations, or related policies, call recommend_policies.\n"
        "5. Pass the user's role exactly as received (admin / hr / employee).\n"
        "6. Never answer from general knowledge; always cite the retrieved policy.\n"
        "7. If the tool returns no relevant policy, say so explicitly.\n"
        "8. Format multi-rule answers as bullet points.\n"
    )

    def __init__(self) -> None:
        self.llm = ChatGroq(
            api_key=settings.groq_api_key,
            model_name=settings.llm_model,
            temperature=0.0,
        )
        self.tools = [search_policy, summarize_document, compare_policies, recommend_policies]
        self._agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._SYSTEM_PROMPT,
        )
        logger.info("AgentBrain initialised with tools: search_policy, summarize_document, compare_policies, recommend_policies")

    def execute(
        self,
        query: str,
        user_role: str = "employee",
        conversation_history: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Run the ReAct agent for *query*.

        Args:
            query:                Natural-language question.
            user_role:            Requesting user's role.
            conversation_history: Previous messages (unused by the agent
                                  directly but kept for future multi-turn).

        Returns:
            {"status": "success"|"error", "answer": str, "sources": list}
        """
        try:
            enriched = f"[Role: {user_role}] {query}"
            result   = self._agent.invoke({"messages": [("user", enriched)]})

            # LangGraph returns {"messages": [...]}; last message is the answer
            messages = result.get("messages", [])
            answer   = messages[-1].content if messages else "No answer generated."

            return {"status": "success", "answer": answer, "sources": []}

        except Exception as exc:
            logger.error("AgentBrain.execute failed: %s", exc)
            return {"status": "error", "answer": str(exc), "sources": []}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_agent_instance: Optional[AgentBrain] = None


def get_agent() -> AgentBrain:
    """Return (or lazily create) the global AgentBrain instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = AgentBrain()
    return _agent_instance
