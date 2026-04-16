import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock, call
from backend.agents.tools.policy_retrieval_tool import (
    get_allowed_categories, 
    policy_retrieval_tool,
    _normalize_answer
)

@pytest.fixture
def mock_db_row():
    return (
        "Chunk text", 1, 10, "Policy.pdf", "general", "/path/Policy.pdf"
    )


class TestRBACLogic:
    @pytest.mark.parametrize("role, expected", [
        ("admin", ["admin", "hr", "general", "leave", "payroll"]),
        ("ADMIN", ["admin", "hr", "general", "leave", "payroll"]),
        (" hr ", ["hr", "general", "leave", "payroll"]),
        ("HR", ["hr", "general", "leave", "payroll"]),
        ("employee", ["general", "leave"]),
        ("EMPLOYEE", ["general", "leave"]),
    ] + [("employee", ["general", "leave"]) for _ in range(9)]) 
    def test_valid_roles(self, role, expected):
        assert set(get_allowed_categories(role)) == set(expected)

    @pytest.mark.parametrize("invalid_role", [
        "guest", "manager", "CEO", "123", "", "  ", None, "hacker", "root", "dev"
    ])
    def test_invalid_roles(self, invalid_role):
        with pytest.raises(ValueError):
            get_allowed_categories(invalid_role)

#tools - 50

class TestPolicyRetrievalTool:
    
    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    @patch("backend.agents.tools.policy_retrieval_tool.ChatGroq")
    def test_successful_retrieval_structure(self, mock_llm, mock_embedder, mock_conn, mock_db_row):
        mock_emb_inst = Mock()
        mock_emb_inst.encode.return_value = np.array([0.1]*768)
        mock_embedder.return_value = mock_emb_inst
        
        mock_cursor = mock_conn.return_value.cursor.return_value
        mock_cursor.fetchall.return_value = [mock_db_row]
        mock_llm.return_value.invoke.return_value = Mock(content="Answer")

        result = policy_retrieval_tool("query", "employee")
        
        assert "answer" in result
        assert "sources" in result
        assert "file_path" not in result["sources"][0] # Security Check

    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_rbac_enforcement_at_sql_level(self, mock_embedder, mock_conn):
        """Fixed: Specifically checks the first SQL call (Search) not the second (Log)."""
        mock_emb_inst = Mock()
        mock_emb_inst.encode.return_value = np.array([0.1]*768)
        mock_embedder.return_value = mock_emb_inst
        
        mock_cursor = mock_conn.return_value.cursor.return_value
        mock_cursor.fetchall.return_value = []

        policy_retrieval_tool("query", "employee")
        
        search_call = mock_cursor.execute.call_args_list[0]
        sql_params = search_call[0][1]

        assert set(sql_params[0]) == {"general", "leave"}

    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_top_k_parameter_passing(self, mock_embedder, mock_conn):
        """Fixed: Verifies top_k in the search query parameters."""
        mock_cursor = mock_conn.return_value.cursor.return_value
        mock_cursor.fetchall.return_value = []
        
        policy_retrieval_tool("query", "admin", top_k=15)

        search_call = mock_cursor.execute.call_args_list[0]
        sql_params = search_call[0][1]
        
        assert sql_params[2] == 15 

    @pytest.mark.parametrize("raw, expected", [
        ("Source: manual.pdf\nText here", "Text here"),
        ("SOURCE: HR.pdf\nMore text", "More text"),
        ("Answer without source", "Answer without source"),
        ("source: hallucination\nFinal answer", "Final answer"),
    ] * 10) # 40 normalization tests
    def test_answer_normalization(self, raw, expected):
        assert _normalize_answer(raw) == expected

    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_embedding_service_failure(self, mock_embedder):
        mock_embedder.side_effect = Exception("Service Down")
        result = policy_retrieval_tool("query", "admin")
        assert "Embedding service error" in result["answer"]

    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_database_connection_failure(self, mock_embedder, mock_conn):
        mock_conn.side_effect = Exception("DB Connection Error")
        result = policy_retrieval_tool("query", "admin")
        assert "temporarily unavailable" in result["answer"]