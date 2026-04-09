"""Main agent brain/orchestrator"""
from typing import List, Dict, Any

# Core LangChain & Execution
from langchain_classic.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import Tool  # Moved to langchain_core for stability
from langchain_groq import ChatGroq

# Project-specific imports (ensure your folder structure matches these)
from backend.config import settings
from backend.agents.tools.retrieval import retrieval_search
from backend.agents.tools.summarization import summarization_tool
from backend.agents.tools.comparison import comparison_tool
from backend.agents.tools.knowledge import knowledge_lookup
from backend.agents.tools.recommendation import recommendation_tool



class AgentBrain:
    """Main agent orchestrator for handling user queries"""

    def __init__(self):
        """Initialize the agent with all tools"""
        self.llm = ChatGroq(
            api_key=settings.groq_api_key,
            model_name=settings.llm_model,
            temperature=settings.agent_temperature
        )

        # Define tools for the agent
        self.tools = [
            Tool(
                name="retrieval_search",
                func=self._wrap_retrieval,
                description="Search for relevant document chunks using semantic similarity. Input: query (string) and user_role (admin/hr/employee)"
            ),
            Tool(
                name="summarization",
                func=self._wrap_summarization,
                description="Summarize document text. Input: text to summarize"
            ),
            Tool(
                name="comparison",
                func=self._wrap_comparison,
                description="Compare multiple documents. Input: comma-separated document IDs"
            ),
            Tool(
                name="knowledge_lookup",
                func=knowledge_lookup,
                description="Look up cached answers for similar questions. Input: question text"
            ),
            Tool(
                name="recommendation",
                func=self._wrap_recommendation,
                description="Get document recommendations. Input: query text and user_role"
            ),
        ]

        # Create the agent
        self.agent_executor = self._create_agent()

    def _wrap_retrieval(self, query: str) -> str:
        """Wrapper for retrieval tool"""
        try:
            results = retrieval_search(query, user_role="admin", top_k=5)
            return str(results)
        except Exception as e:
            return f"Error in retrieval: {str(e)}"

    def _wrap_summarization(self, text: str) -> str:
        """Wrapper for summarization tool"""
        try:
            result = summarization_tool(text)
            return result.get("summary", "No summary generated")
        except Exception as e:
            return f"Error in summarization: {str(e)}"

    def _wrap_comparison(self, doc_ids: str) -> str:
        """Wrapper for comparison tool"""
        try:
            doc_list = [d.strip() for d in doc_ids.split(",")]
            result = comparison_tool(doc_list)
            return result.get("comparison", "No comparison generated")
        except Exception as e:
            return f"Error in comparison: {str(e)}"

    def _wrap_recommendation(self, query: str) -> str:
        """Wrapper for recommendation tool"""
        try:
            result = recommendation_tool(query, user_role="admin")
            recommendations = result.get("recommendations", [])
            return str([r["filename"] for r in recommendations])
        except Exception as e:
            return f"Error in recommendation: {str(e)}"

    def _create_agent(self) -> AgentExecutor:
        """Create the ReAct agent with tools"""
        system_prompt = """You are a helpful AI assistant specialized in answering questions about company policies and documents.

You have access to the following tools:
- retrieval_search: Find relevant documents and information
- summarization: Summarize long documents
- comparison: Compare multiple documents
- knowledge_lookup: Check cached answers
- recommendation: Get document recommendations

When answering questions:
1. First try to look up if this question was answered before using knowledge_lookup
2. If not cached, use retrieval_search to find relevant documents
3. Use the document information to provide a comprehensive answer
4. Be precise and reference the source documents
5. Respect user role-based access control

Always be helpful, accurate, and cite your sources."""

        prompt = PromptTemplate.from_template(
            template=system_prompt + "\n\n{input}\n\nAgent Scratch Pad:\n{agent_scratchpad}",
            input_variables=["input", "agent_scratchpad"]
        )

        agent = create_react_agent(self.llm, self.tools, prompt)
        agent_executor = AgentExecutor.from_agent_and_tools(
            agent=agent,
            tools=self.tools,
            verbose=True,
            max_iterations=10,
            handle_parsing_errors=True
        )

        return agent_executor

    def execute(self, query: str, user_role: str = "employee", conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """
        Execute a query through the agent.

        Args:
            query: User's question
            user_role: User role for access control
            conversation_history: Previous messages for context

        Returns:
            Agent response with answer and metadata
        """
        try:
            # Build context from conversation history
            context = ""
            if conversation_history:
                context = "\n".join([
                    f"Q: {msg.get('question')}\nA: {msg.get('answer')}"
                    for msg in conversation_history[-settings.max_conversation_history:]
                ])

            # Prepare the prompt with context
            full_prompt = f"""User Role: {user_role}

Previous conversation context:
{context}

New question: {query}"""

            # Execute the agent
            response = self.agent_executor.invoke({"input": full_prompt})

            return {
                "status": "success",
                "answer": response.get("output", "No answer generated"),
                "query": query,
                "user_role": user_role
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "query": query,
                "answer": "Sorry, I encountered an error processing your question."
            }


# Global agent instance
_agent_instance = None


def get_agent() -> AgentBrain:
    """Get or create the global agent instance"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = AgentBrain()
    return _agent_instance


def initialize_agent() -> AgentBrain:
    """Initialize the agent"""
    return get_agent()
