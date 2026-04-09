"""
Agent Brain — LangChain/LangGraph ReAct agent.

Only one tool is registered: policy_retrieval_tool.
All other legacy tools (retrieval, summarization, comparison,
knowledge, recommendation) have been removed; they were unused,
broken stubs that caused import errors.
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from backend.config import settings
from backend.agents.tools.policy_retrieval_tool import policy_retrieval_tool as _policy_fn

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


# ---------------------------------------------------------------------------
# AgentBrain
# ---------------------------------------------------------------------------

class AgentBrain:
    """Thin orchestrator that wraps the LangGraph ReAct agent."""

    _SYSTEM_PROMPT = (
        "You are an Enterprise Policy Assistant for Artemis.\n"
        "Your ONLY authoritative source of information is the search_policy tool.\n\n"
        "Rules:\n"
        "1. For any question about company policy, HR rules, leave, payroll, "
        "   IT security, or admin procedures — call search_policy first.\n"
        "2. Pass the user's role exactly as received (admin / hr / employee).\n"
        "3. Never answer from general knowledge; always cite the retrieved policy.\n"
        "4. If the tool returns no relevant policy, say so explicitly.\n"
        "5. Format multi-rule answers as bullet points.\n"
    )

    def __init__(self) -> None:
        self.llm = ChatGroq(
            api_key=settings.groq_api_key,
            model_name=settings.llm_model,
            temperature=0.0,
        )
        self.tools = [search_policy]
        self._agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._SYSTEM_PROMPT,
        )
        logger.info("AgentBrain initialised with tool: search_policy")

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
