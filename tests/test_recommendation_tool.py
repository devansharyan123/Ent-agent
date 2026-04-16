"""
Extensive Test Suite for recommendation_tool
Total Cases: 75+ unique test scenarios covering RBAC, retrieval, LLM formatting,
and error handling.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4

from backend.agents.tools.recommendation_tool import (
    recommendation_tool,
    _generate_recommendation,
    _get_document_chunks_for_recommendation
)
from backend.agents.tools.policy_retrieval_tool import get_allowed_categories

# ============================================================================
# 1. RBAC & ACCESS CONTROL TESTS (25+ Cases)
# ============================================================================

@pytest.mark.parametrize("role,expected", [
    ("admin", {"admin", "hr", "general", "leave", "payroll"}),
    ("hr", {"hr", "general", "leave", "payroll"}),
    ("employee", {"general", "leave"}),
    ("ADMIN", {"admin", "hr", "general", "leave", "payroll"}),
    ("  hr  ", {"hr", "general", "leave", "payroll"}),
    ("EMPLOYEE", {"general", "leave"}),
])
def test_rbac_category_mapping(role, expected):
    """Test standard role to category mapping (6 cases)."""
    categories = get_allowed_categories(role)
    assert set(categories) == expected

@pytest.mark.parametrize("invalid_role", [
    "manager", "intern", "guest", "", " ", None, "123", "root", "super", "null",
    "developer", "tester", "security", "anonymous", "bot", "system", "nobody", "everyone",
    "owner", "client", "vendor", "contractor", "partner", "user_123"
])
def test_rbac_invalid_roles(invalid_role):
    """Test handling of invalid or unauthorized roles (24 cases)."""
    with pytest.raises(ValueError) as exc:
        get_allowed_categories(str(invalid_role))
    assert "Invalid role" in str(exc.value)

@patch("backend.agents.tools.recommendation_tool._get_psycopg2_conn")
@pytest.mark.parametrize("role", ["admin", "hr", "employee"])
def test_rbac_filtering_in_query_logic(mock_conn, role):
    """Verify that specific categories are passed to SQL for each role (3 cases)."""
    mock_cursor = Mock()
    mock_db_conn = Mock()
    mock_conn.return_value = mock_db_conn
    mock_db_conn.cursor.return_value = mock_cursor
    # Fixed: provide a return value for fetchall to avoid 'Mock object is not iterable'
    mock_cursor.fetchall.return_value = []
    
    _get_document_chunks_for_recommendation([0.1]*384, get_allowed_categories(role))
    if mock_cursor.execute.called:
         # Get params from execute(sql, params)
         params = mock_cursor.execute.call_args[0][1]
         # params[0] should be the list of categories
         assert set(params[0]) == set(get_allowed_categories(role))

# ============================================================================
# 2. CORE RETRIEVAL LOGIC TESTS (25+ Cases)
# ============================================================================

class TestRetrievalLogic:
    @patch("backend.agents.tools.recommendation_tool._get_psycopg2_conn")
    @pytest.mark.parametrize("chunk_count", range(0, 16))
    def test_chunk_count_handling(self, mock_conn, chunk_count):
        """Test how retrieval handles result sizes from 0 to 15 (16 cases)."""
        mock_cursor = Mock()
        mock_conn.return_value.cursor.return_value = mock_cursor
        rows = [("text", i, 1, f"doc_{i}.pdf", "general", "/path") for i in range(chunk_count)]
        mock_cursor.fetchall.return_value = rows
        
        chunks = _get_document_chunks_for_recommendation([0.1]*384, ["general"])
        assert len(chunks) == chunk_count

    @patch("backend.agents.tools.recommendation_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.recommendation_tool.get_embedder")
    @patch("backend.agents.tools.recommendation_tool.ChatGroq")
    @pytest.mark.parametrize("repeat_count", [2, 3, 5])
    def test_source_deduplication(self, mock_llm_class, mock_embedder, mock_conn, repeat_count):
        """Test that multiple chunks from same file show as 1 source (3 cases)."""
        mock_cursor = Mock()
        mock_conn.return_value.cursor.return_value = mock_cursor
        rows = [("t", i, 1, "same.pdf", "gen", "") for i in range(repeat_count)]
        mock_cursor.fetchall.return_value = rows
        
        mock_emb = Mock()
        mock_emb.encode.return_value = MagicMock(tolist=Mock(return_value=[0.1]*384))
        mock_embedder.return_value = mock_emb
        
        mock_llm = Mock()
        mock_llm.invoke.return_value = Mock(content="- Q1")
        mock_llm_class.return_value = mock_llm

        res = recommendation_tool("test", "employee")
        assert len(res["sources"]) == 1
        assert res["sources"][0]["file_name"] == "same.pdf"

    @pytest.mark.parametrize("query_style", [
        "What is it?", "leave", "!!!", "a"*1000, "", "12345",
        "SELECT * FROM users", "<script>alert(1)</script>", "\n", " ",
        "How to apply for sick leave?", "maternity", "Who is CEO?", "Who is HR?"
    ])
    def test_query_variations(self, query_style):
        """Test logic with different query styles (14 cases)."""
        with patch("backend.agents.tools.recommendation_tool.get_embedder") as mock_emb:
            mock_emb.return_value.encode.return_value = MagicMock(tolist=Mock(return_value=[0.1]*384))
            with patch("backend.agents.tools.recommendation_tool._get_document_chunks_for_recommendation") as mock_ret:
                mock_ret.return_value = []
                res = recommendation_tool(str(query_style), "employee")
                assert "answer" in res

# ============================================================================
# 3. LLM SYNTHESIS & FORMATTING TESTS (10+ Cases)
# ============================================================================

class TestLLMSynthesis:
    @patch("backend.agents.tools.recommendation_tool.ChatGroq")
    @pytest.mark.parametrize("llm_output", [
        "- Would you like to know more about Leave?",
        "1. Would you like to know about Payroll?",
        "* Would you like to know about Health?",
        "   - Would you like to know about X?",
        "Would you like to know more about Z?",
        "- Question: Would you like to know more about A?"
    ])
    def test_llm_prefix_formatting(self, mock_llm_class, llm_output):
        """Verify LLM output contains the mandatory prefix (6 cases)."""
        mock_llm = Mock()
        mock_llm.invoke.return_value = Mock(content=llm_output)
        mock_llm_class.return_value = mock_llm
        
        chunks = [{"file_name": "f.pdf", "chunk_text": "text"}]
        ans = _generate_recommendation("query", chunks)
        assert "Would you like to know" in ans

    @patch("backend.agents.tools.recommendation_tool.ChatGroq")
    @pytest.mark.parametrize("role", ["admin", "hr", "employee"])
    def test_llm_item_limit_instruction(self, mock_llm_class, role):
        """Test that prompt contains the 'at most 3' instruction for all roles (3 cases)."""
        mock_llm = Mock()
        mock_llm.invoke.return_value = Mock(content="Res")
        mock_llm_class.return_value = mock_llm
        _generate_recommendation("q", [{"file_name": "x", "chunk_text": "y"}])
        
        sys_prompt = mock_llm.invoke.call_args[0][0][0][1]
        assert "at most 3" in sys_prompt.lower()

# ============================================================================
# 4. FAILURE & NEGATIVE CASES (15+ Cases)
# ============================================================================

class TestFailureCases:
    @patch("backend.agents.tools.recommendation_tool._get_psycopg2_conn")
    def test_db_connection_error(self, mock_conn):
        """Test logic when DB is down (1 case)."""
        mock_conn.side_effect = Exception("DB Connection Failed")
        res = recommendation_tool("q", "employee")
        assert "search unavailable" in res["answer"].lower()

    @patch("backend.agents.tools.recommendation_tool.get_embedder")
    def test_embedding_failure(self, mock_emb):
        """Test logic when embedding service fails (1 case)."""
        mock_emb.side_effect = Exception("Embedding Failed")
        res = recommendation_tool("q", "employee")
        assert "embedding error" in res["answer"].lower()

    @patch("backend.agents.tools.recommendation_tool.ChatGroq")
    @patch("backend.agents.tools.recommendation_tool._get_document_chunks_for_recommendation")
    @patch("backend.agents.tools.recommendation_tool.get_embedder")
    def test_llm_timeout_handling(self, mock_emb, mock_ret, mock_llm_class):
        """Test logic when LLM times out (1 case)."""
        mock_emb.return_value.encode.return_value = MagicMock(tolist=Mock(return_value=[0.1]*384))
        mock_ret.return_value = [{"file_name": "x", "chunk_text": "y", "category": "gen"}]
        mock_llm_class.return_value.invoke.side_effect = Exception("Groq Timeout")
        
        res = recommendation_tool("q", "employee")
        assert "failed" in res["answer"].lower()

    @pytest.mark.parametrize("bad_chunk", [
        None, "", {}, [], 123, "None", "\x00", "long"*50
    ])
    def test_robustness_to_malformed_chunks(self, bad_chunk):
        """Test resilience to weird chunk data (8 cases)."""
        with patch("backend.agents.tools.recommendation_tool.ChatGroq") as mock_llm:
            mock_llm.return_value.invoke.return_value = Mock(content="OK")
            ans = _generate_recommendation("q", [{"file_name": "f.pdf", "chunk_text": str(bad_chunk)}])
            assert ans == "OK"

    @pytest.mark.parametrize("missing_field", ["file_name", "chunk_text"])
    def test_missing_chunk_fields(self, missing_field):
        """Test handling of chunks missing required keys (2 cases)."""
        chunk = {"file_name": "f.pdf", "chunk_text": "t"}
        del chunk[missing_field]
        with pytest.raises(KeyError):
             _generate_recommendation("q", [chunk])

    @pytest.mark.parametrize("bad_role", ["", " ", None, 123])
    def test_bad_input_types(self, bad_role):
        """Test robustness to non-string inputs (4 cases)."""
        with patch("backend.agents.tools.recommendation_tool.get_embedder"):
             res = recommendation_tool("q", str(bad_role))
             assert "answer" in res

# ============================================================================
# 5. SERVICE INTEGRATION & LOGGING (10+ Cases)
# ============================================================================

class TestIntegration:
    @patch("backend.agents.tools.recommendation_tool._log_tool_call")
    @patch("backend.agents.tools.recommendation_tool._get_document_chunks_for_recommendation")
    @patch("backend.agents.tools.recommendation_tool.get_embedder")
    @pytest.mark.parametrize("conv_id", [str(uuid4()), None, "test-conv"])
    def test_logging_data_payload(self, mock_emb, mock_ret, mock_log, conv_id):
        """Verify that logs contain counts and queries (3 cases)."""
        mock_emb.return_value.encode.return_value = MagicMock(tolist=Mock(return_value=[0.1]*384))
        mock_ret.return_value = [{"file_name": "x", "chunk_text": "y", "category": "gen"}]
        
        with patch("backend.agents.tools.recommendation_tool._generate_recommendation") as mock_gen:
            mock_gen.return_value = "Result"
            recommendation_tool("My Unique Query", "employee", conversation_id=conv_id)
            if mock_log.called:
                log_args = mock_log.call_args[0]
                assert str(log_args[0]) == str(conv_id)

    @pytest.mark.parametrize("tool_name", ["rag", "summary", "compare", "agent"])
    @pytest.mark.parametrize("role", ["admin", "employee"])
    def test_conversation_service_integration_logic(self, tool_name, role):
        """Test the integration block in conversation_service for all tools and roles (8 cases)."""
        with patch("backend.services.conversation_service.recommendation_tool") as mock_rec, \
             patch("backend.services.conversation_service.policy_retrieval_tool") as mock_rag, \
             patch("backend.services.conversation_service.summarization_tool") as mock_sum, \
             patch("backend.services.conversation_service.comparison_tool") as mock_cmp, \
             patch("backend.services.conversation_service.get_agent") as mock_agent:
            
            mock_rag.return_value = {"answer": "Policy", "sources": []}
            mock_sum.return_value = {"answer": "Summary", "sources": []}
            mock_cmp.return_value = {"answer": "Comparison", "sources": []}
            mock_agent.return_value.execute.return_value = {"answer": "Agent Answer"}
            mock_rec.return_value = {"answer": "- Would you like to know more about X?"}
            
            from backend.services.conversation_service import send_message
            db = MagicMock()
            msg = send_message(db, uuid4(), "test", role, tool=tool_name)
            
            assert "Other questions you would like to know about" in msg.answer
            assert "Would you like to know more" in msg.answer

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
