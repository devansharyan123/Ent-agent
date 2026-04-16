import pytest
import numpy as np
from unittest.mock import Mock, patch

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


# RBAC TESTS

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
        "guest", "manager", "CEO", "123", "", "  ",
        None, "hacker", "root", "dev"
    ])
    def test_invalid_roles(self, invalid_role):
        with pytest.raises(ValueError):
            get_allowed_categories(invalid_role)



# POLICY TOOL TESTS

class TestPolicyRetrievalTool:

    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    @patch("backend.agents.tools.policy_retrieval_tool.ChatGroq")
    def test_successful_retrieval_structure(
        self, mock_llm, mock_embedder, mock_conn, mock_db_row
    ):
        mock_emb_inst = Mock()
        mock_emb_inst.encode.return_value = np.array([0.1] * 768)
        mock_embedder.return_value = mock_emb_inst

        mock_cursor = mock_conn.return_value.cursor.return_value
        mock_cursor.fetchall.return_value = [mock_db_row]

        mock_llm.return_value.invoke.return_value = Mock(content="Answer")

        result = policy_retrieval_tool("query", "employee")

        assert "answer" in result
        assert "sources" in result
        assert "file_path" not in result["sources"][0]


    # RBAC SQL enforcement

    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_rbac_enforcement_at_sql_level(self, mock_embedder, mock_conn):
        mock_emb_inst = Mock()
        mock_emb_inst.encode.return_value = np.array([0.1] * 768)
        mock_embedder.return_value = mock_emb_inst

        mock_cursor = mock_conn.return_value.cursor.return_value
        mock_cursor.fetchall.return_value = []

        policy_retrieval_tool("query", "employee")

        search_call = mock_cursor.execute.call_args_list[0]
        sql_params = search_call[0][1]

        assert set(sql_params[0]) == {"general", "leave"}



    # top_k tests

    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_top_k_parameter_passing(self, mock_embedder, mock_conn):
        mock_cursor = mock_conn.return_value.cursor.return_value
        mock_cursor.fetchall.return_value = []

        policy_retrieval_tool("query", "admin", top_k=15)

        search_call = mock_cursor.execute.call_args_list[0]
        sql_params = search_call[0][1]

        assert sql_params[2] == 15

    @pytest.mark.parametrize("top_k", [0, -1, 1000])
    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_top_k_edge_cases(self, mock_embedder, mock_conn, top_k):
        mock_cursor = mock_conn.return_value.cursor.return_value
        mock_cursor.fetchall.return_value = []

        policy_retrieval_tool("query", "admin", top_k=top_k)

        search_call = mock_cursor.execute.call_args_list[0]
        sql_params = search_call[0][1]

        assert sql_params[2] == top_k



    # Input edge cases

    @pytest.mark.parametrize("query", ["", None, 123])
    def test_invalid_query_inputs(self, query):
        result = policy_retrieval_tool(query, "admin")
        assert "answer" in result


    # Embedding edge cases

    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_embedding_service_failure(self, mock_embedder):
        mock_embedder.side_effect = Exception("Service Down")

        result = policy_retrieval_tool("query", "admin")

        assert "Embedding service error" in result["answer"]

    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_embedding_wrong_shape(self, mock_embedder):
        mock_emb_inst = Mock()
        mock_emb_inst.encode.return_value = np.array([0.1, 0.2])  # wrong shape
        mock_embedder.return_value = mock_emb_inst

        result = policy_retrieval_tool("query", "admin")
        assert "answer" in result


    # DB edge cases

    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_database_connection_failure(self, mock_embedder, mock_conn):
        mock_conn.side_effect = Exception("DB Connection Error")

        result = policy_retrieval_tool("query", "admin")

        assert "temporarily unavailable" in result["answer"]

    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_empty_db_results(self, mock_embedder, mock_conn):
        mock_cursor = mock_conn.return_value.cursor.return_value
        mock_cursor.fetchall.return_value = None

        result = policy_retrieval_tool("query", "admin")

        assert "answer" in result

    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_malformed_db_row(self, mock_embedder, mock_conn):
        mock_cursor = mock_conn.return_value.cursor.return_value
        mock_cursor.fetchall.return_value = [("bad_row",)]

        result = policy_retrieval_tool("query", "admin")

        assert "answer" in result



    # LLM edge cases

    @patch("backend.agents.tools.policy_retrieval_tool.ChatGroq")
    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_llm_failure(self, mock_embedder, mock_conn, mock_llm):
        mock_llm.return_value.invoke.side_effect = Exception("LLM crash")

        mock_cursor = mock_conn.return_value.cursor.return_value
        mock_cursor.fetchall.return_value = []

        result = policy_retrieval_tool("query", "admin")

        assert "answer" in result

    @patch("backend.agents.tools.policy_retrieval_tool.ChatGroq")
    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_llm_returns_none(self, mock_embedder, mock_conn, mock_llm):
        mock_llm.return_value.invoke.return_value = Mock(content=None)

        mock_cursor = mock_conn.return_value.cursor.return_value
        mock_cursor.fetchall.return_value = []

        result = policy_retrieval_tool("query", "admin")

        assert "answer" in result


    # Source edge cases

    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_empty_sources(self, mock_embedder, mock_conn):
        mock_cursor = mock_conn.return_value.cursor.return_value
        mock_cursor.fetchall.return_value = []

        result = policy_retrieval_tool("query", "admin")

        assert isinstance(result["sources"], list)



# NORMALIZATION TESTS

class TestNormalization:

    @pytest.mark.parametrize("raw, expected", [
        ("Source: manual.pdf\nText here", "Text here"),
        ("SOURCE: HR.pdf\nMore text", "More text"),
        ("Answer without source", "Answer without source"),
        ("source: hallucination\nFinal answer", "Final answer"),
    ] * 10)
    def test_answer_normalization(self, raw, expected):
        assert _normalize_answer(raw) == expected

    @pytest.mark.parametrize("raw, expected", [
        ("", ""),
        ("Source:", ""),
        ("Source: file\n", ""),
        ("   Source: file\nAnswer   ", "Answer"),
    ])
    def test_normalization_edge_cases(self, raw, expected):
        assert _normalize_answer(raw) == expected