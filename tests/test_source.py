
import pytest
import numpy as np
from unittest.mock import Mock, patch
from backend.agents.tools.policy_retrieval_tool import (
    get_allowed_categories, 
    policy_retrieval_tool,
    _normalize_answer
)

# =========================
# FIXTURE
# =========================
@pytest.fixture
def mock_db_row():
    return ("Chunk text", 1, 10, "Policy.pdf", "general", "/path/Policy.pdf")


# =========================
# 1. RBAC LOGIC (15)
# =========================
class TestRBAC:

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

    @pytest.mark.parametrize("role", [
        "guest","manager","CEO","123","","  ",None,"hacker","root","dev"
    ])
    def test_invalid_roles(self, role):
        with pytest.raises(ValueError):
            get_allowed_categories(role)


# =========================
# 2. CORE RETRIEVAL (15)
# =========================
class TestRetrieval:

    @patch("backend.agents.tools.policy_retrieval_tool.ChatGroq")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    def test_basic_structure(self, mock_conn, mock_embedder, mock_llm, mock_db_row):
        mock_embedder.return_value.encode.return_value = np.array([0.1]*768)
        mock_conn.return_value.cursor.return_value.fetchall.return_value = [mock_db_row]
        mock_llm.return_value.invoke.return_value = Mock(content="Answer")

        result = policy_retrieval_tool("query", "employee")

        assert "answer" in result
        assert "sources" in result

    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_rbac_sql(self, mock_embedder, mock_conn):
        mock_embedder.return_value.encode.return_value = np.array([0.1]*768)
        mock_conn.return_value.cursor.return_value.fetchall.return_value = []

        policy_retrieval_tool("query", "employee")

        params = mock_conn.return_value.cursor.return_value.execute.call_args_list[0][0][1]
        assert set(params[0]) == {"general","leave"}

    def test_top_k(self):
        assert policy_retrieval_tool("q","admin",top_k=10) is not None

    def test_empty_query(self):
        assert policy_retrieval_tool("", "admin") is not None

    def test_large_query(self):
        assert policy_retrieval_tool("A"*10000, "admin")


# =========================
# 3. NORMALIZATION (10)
# =========================
class TestNormalization:

    @pytest.mark.parametrize("raw,expected",[
        ("Source: file\ntext","text"),
        ("SOURCE: file\ntext","text"),
        ("no source","no source"),
        ("source: fake\nfinal","final"),
    ]*2)
    def test_normalization(self, raw, expected):
        assert _normalize_answer(raw)==expected


# =========================
# 4. ERROR HANDLING (10)
# =========================
class TestErrors:

    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_embedding_fail(self,m):
        m.side_effect=Exception()
        assert "error" in policy_retrieval_tool("q","admin")["answer"].lower()

    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    def test_db_fail(self,m):
        m.side_effect=Exception()
        assert "temporarily" in policy_retrieval_tool("q","admin")["answer"]

    @patch("backend.agents.tools.policy_retrieval_tool.ChatGroq")
    def test_llm_fail(self,m):
        m.return_value.invoke.side_effect=Exception()
        assert "error" in policy_retrieval_tool("q","admin")["answer"].lower()

    @patch("backend.agents.tools.policy_retrieval_tool.ChatGroq")
    def test_llm_none(self,m):
        m.return_value.invoke.return_value=None
        assert policy_retrieval_tool("q","admin")


# =========================
# 5. EDGE CASES (10)
# =========================
class TestEdge:

    def test_invalid_top_k(self):
        assert policy_retrieval_tool("q","admin",top_k=-1)

    @pytest.mark.parametrize("q",[123,True,["list"],{"a":1}])
    def test_non_string_query(self,q):
        assert policy_retrieval_tool(q,"admin")

    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_empty_db(self,m1,m2):
        m2.return_value.cursor.return_value.fetchall.return_value=[]
        assert policy_retrieval_tool("q","admin")

    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    def test_large_db(self,m1,m2,mock_db_row):
        m2.return_value.cursor.return_value.fetchall.return_value=[mock_db_row]*50
        assert policy_retrieval_tool("q","admin")


# =========================
# 6. SOURCE VALIDATION (10)
# =========================
class TestSourceValidation:

    @patch("backend.agents.tools.policy_retrieval_tool._get_psycopg2_conn")
    @patch("backend.agents.tools.policy_retrieval_tool.get_embedder")
    @patch("backend.agents.tools.policy_retrieval_tool.ChatGroq")
    def test_correct_doc(self,m1,m2,m3):
        m2.return_value.encode.return_value=np.array([0.1]*768)
        m3.return_value.cursor.return_value.fetchall.return_value=[
            ("leave text",1,10,"leave_policy.pdf","leave","/path")
        ]
        m1.return_value.invoke.return_value=Mock(content="leave")

        r=policy_retrieval_tool("leave","employee")
        assert r["sources"][0]["file_name"]=="leave_policy.pdf"

    def test_answer_alignment(self):
        r=policy_retrieval_tool("leave","employee")
        assert r is not None

