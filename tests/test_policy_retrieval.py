"""
Test Suite for policy_retrieval_tool

Tests RBAC enforcement, vector search, answer generation,
and tool logging for the Enterprise Knowledge Assistant.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4

from backend.agents.tools.policy_retrieval_tool import (
    get_allowed_categories,
    policy_retrieval_tool,
)


# ============================================================================
# TEST 1: Role-Based Category Access Control
# ============================================================================

class TestRoleAccess:
    """Verify that role → category mapping is correct."""

    def test_admin_access(self):
        """Admin can access all categories."""
        categories = get_allowed_categories("admin")
        assert set(categories) == {"admin", "hr", "general"}

    def test_admin_access_uppercase(self):
        """Role normalization works (uppercase → lowercase)."""
        categories = get_allowed_categories("ADMIN")
        assert set(categories) == {"admin", "hr", "general"}

    def test_hr_access(self):
        """HR can access HR and general categories."""
        categories = get_allowed_categories("hr")
        assert set(categories) == {"hr", "general"}

    def test_employee_access(self):
        """Employee can access only general category."""
        categories = get_allowed_categories("employee")
        assert categories == ["general"]

    def test_invalid_role(self):
        """Invalid role raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_allowed_categories("invalid_role")
        assert "Invalid role" in str(exc_info.value)

    def test_empty_role(self):
        """Empty role raises ValueError."""
        with pytest.raises(ValueError):
            get_allowed_categories("")

    def test_whitespace_normalization(self):
        """Whitespace is normalized."""
        categories = get_allowed_categories("  employee  ")
        assert categories == ["general"]


# ============================================================================
# TEST 2: Access Control Enforcement (RBAC Security)
# ============================================================================

class TestRBACEnforcement:
    """
    Verify that chunks from unauthorized categories are NEVER returned,
    even if semantically relevant.
    """

    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_employee_cannot_access_hr_policy(self, mock_embedder, mock_conn):
        """
        TEST 2.1: Employee asks about maternity leave.
        - Query: "What is maternity leave policy?"
        - Expected: only GENERAL chunks returned, not HR chunks.
        """
        # Mock embedder
        mock_emb_instance = Mock()
        mock_emb_instance.encode.return_value = MagicMock(tolist=Mock(return_value=[0.1] * 768))
        mock_embedder.return_value = mock_emb_instance

        # Mock database connection
        mock_cursor = Mock()
        mock_db_conn = Mock()
        mock_conn.return_value = mock_db_conn
        mock_db_conn.cursor.return_value = mock_cursor

        # Mock only GENERAL category chunks (no HR chunks returned due to RBAC)
        mock_cursor.fetchall.return_value = [
            (
                "Leave can be requested through the HR portal.",
                0,
                5,
                "General_Policy.pdf",
                "general",
                "/storage/policies/general/General_Policy.pdf",
            )
        ]

        result = policy_retrieval_tool(
            query="What is maternity leave policy?",
            user_role="employee",
            top_k=5,
        )

        # Verify only general category is present
        assert result["answer"]  # Non-empty answer
        assert len(result["sources"]) >= 0
        for source in result["sources"]:
            assert source["category"] == "general", "Employee received unauthorized category!"

    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_hr_can_access_hr_policy(self, mock_embedder, mock_conn):
        """
        TEST 2.2: HR asks about maternity leave.
        - Query: "What is maternity leave policy?"
        - Expected: both HR and GENERAL chunks may be returned.
        """
        mock_emb_instance = Mock()
        mock_emb_instance.encode.return_value = MagicMock(tolist=Mock(return_value=[0.1] * 768))
        mock_embedder.return_value = mock_emb_instance

        mock_cursor = Mock()
        mock_db_conn = Mock()
        mock_conn.return_value = mock_db_conn
        mock_db_conn.cursor.return_value = mock_cursor

        # Mock HR + general chunks
        mock_cursor.fetchall.return_value = [
            (
                "Maternity leave: 180 days paid.",
                1,
                12,
                "HR_Policy.pdf",
                "hr",
                "/storage/policies/hr/HR_Policy.pdf",
            ),
            (
                "All leaves must be approved by manager.",
                0,
                3,
                "General_Policy.pdf",
                "general",
                "/storage/policies/general/General_Policy.pdf",
            ),
        ]

        result = policy_retrieval_tool(
            query="What is maternity leave policy?",
            user_role="hr",
            top_k=5,
        )

        # Verify multiple categories allowed
        categories = {source["category"] for source in result["sources"]}
        assert categories.issubset({"hr", "general"}), "HR received unauthorized category!"

    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_admin_can_access_all(self, mock_embedder, mock_conn):
        """
        TEST 2.3: Admin asks about payroll (admin category).
        - Expected: admin + hr + general categories accessible.
        """
        mock_emb_instance = Mock()
        mock_emb_instance.encode.return_value = MagicMock(tolist=Mock(return_value=[0.1] * 768))
        mock_embedder.return_value = mock_emb_instance

        mock_cursor = Mock()
        mock_db_conn = Mock()
        mock_conn.return_value = mock_db_conn
        mock_db_conn.cursor.return_value = mock_cursor

        # Mock all categories
        mock_cursor.fetchall.return_value = [
            ("Payroll processed monthly.", 2, 8, "Admin_Policy.pdf", "admin", "/storage/policies/admin/Admin_Policy.pdf"),
            ("Salary details in dashboard.", 0, 5, "HR_Policy.pdf", "hr", "/storage/policies/hr/HR_Policy.pdf"),
        ]

        result = policy_retrieval_tool(
            query="What is payroll policy?",
            user_role="admin",
            top_k=5,
        )

        categories = {source["category"] for source in result["sources"]}
        assert categories.issubset({"admin", "hr", "general"}), "Admin received unauthorized category!"


# ============================================================================
# TEST 3: Error Handling
# ============================================================================

class TestErrorHandling:
    """Verify graceful error handling."""

    def test_invalid_role_returns_error(self):
        """Invalid role returns error message, not exception."""
        result = policy_retrieval_tool(
            query="test",
            user_role="invalid",
            top_k=5,
        )
        assert "Invalid role" in result["answer"]
        assert result["sources"] == []

    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_embedding_failure_handled(self, mock_embedder):
        """Embedding failure returns graceful error."""
        mock_embedder.side_effect = Exception("Embedding service down")

        result = policy_retrieval_tool(
            query="test",
            user_role="employee",
            top_k=5,
        )
        assert "unavailable" in result["answer"].lower()
        assert result["sources"] == []

    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_no_matching_chunks(self, mock_embedder, mock_conn):
        """
        When no authorized chunks match query, return explicit message.
        """
        mock_emb_instance = Mock()
        mock_emb_instance.encode.return_value = MagicMock(tolist=Mock(return_value=[0.1] * 768))
        mock_embedder.return_value = mock_emb_instance

        mock_cursor = Mock()
        mock_db_conn = Mock()
        mock_conn.return_value = mock_db_conn
        mock_db_conn.cursor.return_value = mock_cursor

        # No results
        mock_cursor.fetchall.return_value = []

        result = policy_retrieval_tool(
            query="some obscure policy",
            user_role="employee",
            top_k=5,
        )
        assert "not available" in result["answer"] or "not found" in result["answer"].lower()
        assert result["sources"] == []


# ============================================================================
# TEST 4: Answer Grounding
# ============================================================================

class TestAnswerGeneration:
    """Verify answers are grounded in retrieved chunks."""

    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.ChatGroq")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_answer_includes_source_names(self, mock_embedder, mock_llm_class, mock_conn):
        """
        Generated answer should mention policy document names
        to show it's grounded.
        """
        mock_emb_instance = Mock()
        mock_emb_instance.encode.return_value = MagicMock(tolist=Mock(return_value=[0.1] * 768))
        mock_embedder.return_value = mock_emb_instance

        mock_cursor = Mock()
        mock_db_conn = Mock()
        mock_conn.return_value = mock_db_conn
        mock_db_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            ("Sick leave: 10 days per year.", 0, 3, "HR_Policy.pdf", "hr", "/storage/policies/hr/HR_Policy.pdf"),
        ]

        # Mock LLM response to include document reference
        mock_llm = Mock()
        mock_llm.invoke.return_value = Mock(
            content="According to HR_Policy.pdf, employees get 10 days of sick leave per year."
        )
        mock_llm_class.return_value = mock_llm

        result = policy_retrieval_tool(
            query="How much sick leave?",
            user_role="hr",
            top_k=5,
        )

        # Answer should contain source document name
        assert "HR_Policy" in result["answer"] or "sick leave" in result["answer"].lower()


# ============================================================================
# TEST 5: Tool Observability Logging
# ============================================================================

class TestToolLogging:
    """Verify tool invocations are logged."""

    @patch("backend.agents.tools.policy_retrieval_tool._log_tool_call")
    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_logging_called(self, mock_embedder, mock_conn, mock_log):
        """Every tool call should be logged."""
        mock_emb_instance = Mock()
        mock_emb_instance.encode.return_value = MagicMock(tolist=Mock(return_value=[0.1] * 768))
        mock_embedder.return_value = mock_emb_instance

        mock_cursor = Mock()
        mock_db_conn = Mock()
        mock_conn.return_value = mock_db_conn
        mock_db_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        policy_retrieval_tool(
            query="test",
            user_role="employee",
            top_k=5,
            conversation_id="test-conv-id",
        )

        # Verify logging was called
        assert mock_log.call_count >= 1


# ============================================================================
# TEST 6: Response Format
# ============================================================================

class TestResponseFormat:
    """Verify response structure matches specification."""

    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.ChatGroq")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_response_has_required_keys(self, mock_embedder, mock_llm_class, mock_conn):
        """Response must have answer, sources, retrieved_chunks."""
        mock_emb_instance = Mock()
        mock_emb_instance.encode.return_value = MagicMock(tolist=Mock(return_value=[0.1] * 768))
        mock_embedder.return_value = mock_emb_instance

        mock_cursor = Mock()
        mock_db_conn = Mock()
        mock_conn.return_value = mock_db_conn
        mock_db_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            ("Policy text", 0, 1, "doc.pdf", "general", "/path/doc.pdf"),
        ]

        mock_llm = Mock()
        mock_llm.invoke.return_value = Mock(content="Answer")
        mock_llm_class.return_value = mock_llm

        result = policy_retrieval_tool(
            query="test",
            user_role="employee",
            top_k=5,
        )

        # Verify required keys
        assert "answer" in result
        assert "sources" in result
        assert "retrieved_chunks" in result

    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.ChatGroq")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_sources_have_required_fields(self, mock_embedder, mock_llm_class, mock_conn):
        """Each source must have: file_name, page_number, chunk_index, category."""
        mock_emb_instance = Mock()
        mock_emb_instance.encode.return_value = MagicMock(tolist=Mock(return_value=[0.1] * 768))
        mock_embedder.return_value = mock_emb_instance

        mock_cursor = Mock()
        mock_db_conn = Mock()
        mock_conn.return_value = mock_db_conn
        mock_db_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            ("Policy text", 5, 10, "doc.pdf", "general", "/path/doc.pdf"),
        ]

        mock_llm = Mock()
        mock_llm.invoke.return_value = Mock(content="Answer")
        mock_llm_class.return_value = mock_llm

        result = policy_retrieval_tool(
            query="test",
            user_role="employee",
            top_k=5,
        )

        # Verify source structure
        assert len(result["sources"]) == 1
        source = result["sources"][0]
        assert "file_name" in source
        assert "page_number" in source
        assert "chunk_index" in source
        assert "category" in source
        assert "file_path" not in source, "file_path should not be in public response!"


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
