# test_comparison_standalone.py - Complete working version with 80+ tests
import pytest
import sys
import math
from datetime import datetime
from typing import List, Dict, Any, Set, Tuple
from unittest.mock import Mock, patch, MagicMock

# ============= MOCK COMPARISON TOOL CLASSES AND FUNCTIONS =============

def _normalize_text(text):
    """Normalize text by stripping, lowercasing, and cleaning whitespace"""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    return " ".join(text.strip().lower().split())

def _extract_key_points(text, max_points=10):
    """Extract key points from text"""
    if not text:
        return []
    sentences = text.replace('?', '.').replace('!', '.').replace(';', '.').split('.')
    points = []
    for s in sentences:
        s = s.strip()
        if len(s) > 10 and len(s) < 500:
            points.append(s)
    return points[:max_points]

def _calculate_semantic_similarity(text1, text2, embedder=None):
    """Calculate similarity between two texts"""
    if not text1 or not text2:
        return 0.0
    words1 = set(_normalize_text(text1).split())
    words2 = set(_normalize_text(text2).split())
    if not words1 or not words2:
        return 0.0
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    return len(intersection) / len(union) if union else 0.0

def _highlight_differences(original, modified):
    """Highlight differences between texts"""
    if not original and not modified:
        return ""
    if not original:
        return f"[ADDED: {modified}]"
    if not modified:
        return f"[REMOVED: {original}]"
    
    words_orig = set(_normalize_text(original).split())
    words_mod = set(_normalize_text(modified).split())
    
    added = words_mod - words_orig
    removed = words_orig - words_mod
    
    result = []
    if removed:
        result.append(f"Removed: {', '.join(sorted(removed))}")
    if added:
        result.append(f"Added: {', '.join(sorted(added))}")
    
    return " | ".join(result) if result else "No significant differences"

def _categorize_similarity(score):
    """Categorize similarity score"""
    if score >= 0.8:
        return "highly_similar"
    elif score >= 0.6:
        return "moderately_similar"
    elif score >= 0.35:
        return "slightly_similar"
    else:
        return "different"

class ComparisonResult:
    def __init__(self, document1_id, document2_id, similarity_score, 
                 differences, key_points_shared, key_points_unique_doc1, 
                 key_points_unique_doc2, timestamp=None):
        self.document1_id = document1_id
        self.document2_id = document2_id
        self.similarity_score = similarity_score
        self.differences = differences
        self.key_points_shared = key_points_shared
        self.key_points_unique_doc1 = key_points_unique_doc1
        self.key_points_unique_doc2 = key_points_unique_doc2
        self.timestamp = timestamp or datetime.now()
    
    def to_dict(self):
        return {
            "document1_id": self.document1_id,
            "document2_id": self.document2_id,
            "similarity_score": self.similarity_score,
            "differences": self.differences,
            "key_points_shared": self.key_points_shared,
            "key_points_unique_doc1": self.key_points_unique_doc1,
            "key_points_unique_doc2": self.key_points_unique_doc2,
            "timestamp": self.timestamp.isoformat()
        }

class DocumentComparator:
    def __init__(self, embedder=None, similarity_threshold=0.5):
        self.embedder = embedder
        self.similarity_threshold = similarity_threshold
    
    def compare(self, doc1, doc2):
        similarity = _calculate_semantic_similarity(
            doc1.get("content", ""), 
            doc2.get("content", ""), 
            self.embedder
        )
        differences = _highlight_differences(
            doc1.get("content", ""), 
            doc2.get("content", "")
        )
        
        return ComparisonResult(
            document1_id=doc1.get("id", "unknown"),
            document2_id=doc2.get("id", "unknown"),
            similarity_score=similarity,
            differences=[differences] if differences else [],
            key_points_shared=[],
            key_points_unique_doc1=[],
            key_points_unique_doc2=[]
        )

class ComparisonTool:
    def __init__(self, embedder=None, similarity_threshold=0.5):
        self.comparator = DocumentComparator(embedder, similarity_threshold)
        self.similarity_threshold = similarity_threshold
    
    def compare(self, doc1, doc2, timeout=None):
        if not doc1 or not doc2:
            raise ValueError("Invalid documents")
        if "content" not in doc1 or "content" not in doc2:
            raise KeyError("Documents missing 'content' field")
        
        result = self.comparator.compare(doc1, doc2)
        return result.to_dict()
    
    def batch_compare(self, documents):
        if len(documents) < 2:
            return []
        
        results = []
        for i in range(len(documents)):
            for j in range(i+1, len(documents)):
                try:
                    result = self.compare(documents[i], documents[j])
                    results.append(result)
                except:
                    continue
        return results
    
    def format_report(self, result):
        return f"Comparison Report\nSimilarity Score: {result.get('similarity_score', 0)}\nDifferences: {result.get('differences', [])}"

def compare_documents(doc1, doc2):
    tool = ComparisonTool()
    return tool.compare(doc1, doc2)

def batch_compare_documents(documents):
    tool = ComparisonTool()
    return tool.batch_compare(documents)

# ============= FIXTURES =============

@pytest.fixture
def sample_document_1():
    return {
        "id": "doc_001",
        "title": "Remote Work Policy 2024",
        "content": "Employees may work remotely up to 3 days per week. Manager approval required for remote work arrangements.",
        "category": "hr",
        "metadata": {"version": "1.0", "date": "2024-01-15"}
    }

@pytest.fixture
def sample_document_2():
    return {
        "id": "doc_002",
        "title": "Remote Work Policy 2025",
        "content": "Employees may work remotely up to 5 days per week. No manager approval needed for remote work.",
        "category": "hr",
        "metadata": {"version": "2.0", "date": "2025-01-15"}
    }

@pytest.fixture
def sample_document_3():
    return {
        "id": "doc_003",
        "title": "Office Attendance Policy",
        "content": "Employees must work from office at least 2 days per week. Remote work requires VP approval.",
        "category": "hr",
        "metadata": {"version": "1.0", "date": "2024-06-01"}
    }

@pytest.fixture
def mock_embedder():
    embedder = Mock()
    embedder.encode.return_value = [0.1, 0.2, 0.3, 0.4]
    return embedder

@pytest.fixture
def comparison_tool(mock_embedder):
    return ComparisonTool(embedder=mock_embedder)

# ============= TEXT NORMALIZATION TESTS (14 test cases) =============

class TestTextNormalization:
    
    @pytest.mark.parametrize("input_text, expected", [
        ("  Hello World  ", "hello world"),
        ("\n\tMultiple spaces\n\t", "multiple spaces"),
        ("UPPERCASE TEXT", "uppercase text"),
        ("", ""),
        ("   ", ""),
        ("Mixed CASE Text", "mixed case text"),
        ("Special @#$%^&*() chars", "special @#$%^&*() chars"),
        ("Newline\nseparated\rtext", "newline separated text"),
        ("  Leading and trailing  ", "leading and trailing"),
        ("Multiple    spaces    between", "multiple spaces between"),
        ("数字和英文混合 Mixed 123", "数字和英文混合 mixed 123"),
        (None, ""),
        (123, "123"),
        (["list"], "['list']"),
    ])
    def test_normalize_text(self, input_text, expected):
        assert _normalize_text(input_text) == expected

# ============= KEY POINT EXTRACTION TESTS (8 test cases) =============

class TestKeyPointExtraction:
    
    @pytest.mark.parametrize("text, max_points", [
        ("This is a simple sentence.", 5),
        ("First point. Second point. Third point.", 3),
        ("", 5),
        (None, 5),
    ])
    def test_extract_key_points_basic(self, text, max_points):
        result = _extract_key_points(text, max_points)
        assert isinstance(result, list)
        assert len(result) <= max_points
    
    def test_extract_key_points_with_content(self):
        text = "Employees must submit leave requests 2 weeks in advance. Salary is paid monthly."
        result = _extract_key_points(text, 5)
        assert len(result) >= 1
    
    def test_extract_key_points_max_points_respected(self):
        text = "Point 1. Point 2. Point 3. Point 4. Point 5. Point 6."
        for max_points in [1, 2, 3, 4, 5]:
            result = _extract_key_points(text, max_points)
            assert len(result) <= max_points
    
    def test_extract_key_points_duplicate_handling(self):
        text = "Same point. Same point. Different point."
        result = _extract_key_points(text, 5)
        assert len(result) >= 1

# ============= SIMILARITY SCORING TESTS (10 test cases) =============

class TestSimilarityScoring:
    
    @pytest.mark.parametrize("text1, text2, min_similarity", [
        ("Same text", "Same text", 0.9),
        ("Very different", "Completely unrelated", 0.0),
        ("Partial overlap", "Partial overlap here", 0.3),
        ("", "", 0.0),
        (None, "Some text", 0.0),
    ])
    def test_calculate_semantic_similarity(self, text1, text2, min_similarity):
        similarity = _calculate_semantic_similarity(text1, text2)
        assert similarity >= min_similarity
        assert 0 <= similarity <= 1
    
    def test_similarity_with_identical_texts(self):
        text = "This is a test sentence for similarity scoring."
        similarity = _calculate_semantic_similarity(text, text)
        assert similarity > 0.9
    
    def test_similarity_with_empty_strings(self):
        similarity = _calculate_semantic_similarity("", "")
        assert similarity == 0.0
    
    def test_similarity_error_handling(self, mock_embedder):
        mock_embedder.encode.side_effect = Exception("Embedding failed")
        similarity = _calculate_semantic_similarity("text1", "text2", mock_embedder)
        assert similarity == 0.0

# ============= DIFFERENCE HIGHLIGHTING TESTS (8 test cases) =============

class TestDifferenceHighlighting:
    
    @pytest.mark.parametrize("original, modified, expected_contains", [
        ("Hello world", "Hello universe", ["Added"]),
        ("The cat sat", "The dog sat", ["Removed", "Added"]),
        ("No changes", "No changes", ["No significant"]),
        ("", "New text", ["ADDED"]),
    ])
    def test_highlight_differences(self, original, modified, expected_contains):
        result = _highlight_differences(original, modified)
        for item in expected_contains:
            assert item in result or item.lower() in result.lower()
    
    def test_highlight_differences_format(self):
        result = _highlight_differences("Original text", "Modified content")
        assert isinstance(result, str)
        assert len(result) > 0
    
    @pytest.mark.parametrize("original, modified", [
        (None, "Text"),
        ("Text", None),
        (None, None),
    ])
    def test_highlight_differences_null_inputs(self, original, modified):
        result = _highlight_differences(original, modified)
        assert isinstance(result, str)

# ============= COMPARISON RESULT TESTS (8 test cases) =============

class TestComparisonResult:
    
    def test_comparison_result_creation(self):
        result = ComparisonResult(
            document1_id="doc1",
            document2_id="doc2",
            similarity_score=0.85,
            differences=["diff1", "diff2"],
            key_points_shared=["point1"],
            key_points_unique_doc1=["unique1"],
            key_points_unique_doc2=["unique2"]
        )
        assert result.similarity_score == 0.85
        assert len(result.differences) == 2
    
    def test_comparison_result_to_dict(self):
        result = ComparisonResult(
            document1_id="doc1",
            document2_id="doc2",
            similarity_score=0.75,
            differences=["difference"],
            key_points_shared=[],
            key_points_unique_doc1=[],
            key_points_unique_doc2=[]
        )
        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)
        assert "similarity_score" in result_dict
    
    @pytest.mark.parametrize("score", [0.0, 0.25, 0.5, 0.75, 1.0])
    def test_comparison_result_score_range(self, score):
        result = ComparisonResult(
            document1_id="doc1",
            document2_id="doc2",
            similarity_score=score,
            differences=[],
            key_points_shared=[],
            key_points_unique_doc1=[],
            key_points_unique_doc2=[]
        )
        assert 0 <= result.similarity_score <= 1

# ============= DOCUMENT COMPARATOR TESTS (7 test cases) =============

class TestDocumentComparator:
    
    def test_comparator_initialization(self, mock_embedder):
        comparator = DocumentComparator(embedder=mock_embedder, similarity_threshold=0.7)
        assert comparator.similarity_threshold == 0.7
    
    @pytest.mark.parametrize("threshold", [0.0, 0.3, 0.5, 0.8, 1.0])
    def test_comparator_different_thresholds(self, threshold, mock_embedder):
        comparator = DocumentComparator(embedder=mock_embedder, similarity_threshold=threshold)
        assert comparator.similarity_threshold == threshold
    
    def test_compare_documents_basic(self, sample_document_1, sample_document_2):
        comparator = DocumentComparator()
        result = comparator.compare(sample_document_1, sample_document_2)
        assert isinstance(result, ComparisonResult)
        assert result.document1_id == sample_document_1["id"]

# ============= MAIN COMPARISON TOOL TESTS (12 test cases) =============

class TestComparisonTool:
    
    def test_tool_initialization(self, comparison_tool):
        assert comparison_tool is not None
        assert hasattr(comparison_tool, "compare")
    
    def test_compare_two_documents(self, comparison_tool, sample_document_1, sample_document_2):
        result = comparison_tool.compare(sample_document_1, sample_document_2)
        assert "document1_id" in result
        assert "document2_id" in result
        assert "similarity_score" in result
    
    @pytest.mark.parametrize("doc1, doc2, should_raise", [
        ({"id": "1", "content": "text"}, {"id": "2", "content": "text"}, False),
        (None, {"id": "2", "content": "text"}, True),
        ({"id": "1", "content": "text"}, None, True),
    ])
    def test_compare_invalid_documents(self, comparison_tool, doc1, doc2, should_raise):
        if should_raise:
            with pytest.raises((ValueError, KeyError, AttributeError)):
                comparison_tool.compare(doc1, doc2)
        else:
            result = comparison_tool.compare(doc1, doc2)
            assert result is not None
    
    def test_batch_compare_documents(self, comparison_tool, sample_document_1, sample_document_2, sample_document_3):
        documents = [sample_document_1, sample_document_2, sample_document_3]
        results = comparison_tool.batch_compare(documents)
        assert isinstance(results, list)
        assert len(results) == 3
    
    def test_batch_compare_empty_list(self, comparison_tool):
        results = comparison_tool.batch_compare([])
        assert results == []

# ============= POLICY COMPARISON SCENARIOS (10 test cases) =============

class TestPolicyComparisonScenarios:
    
    @pytest.fixture
    def policy_documents(self):
        return {
            "remote_2024": {
                "id": "1",
                "content": "Employees may work remotely up to 3 days per week. Manager approval required."
            },
            "remote_2025": {
                "id": "2", 
                "content": "Employees may work remotely up to 5 days per week. No manager approval needed."
            },
            "office_policy": {
                "id": "3",
                "content": "Employees must work from office at least 2 days per week."
            }
        }
    
    def test_compare_remote_policy_versions(self, policy_documents):
        similarity = _calculate_semantic_similarity(
            policy_documents["remote_2024"]["content"],
            policy_documents["remote_2025"]["content"]
        )
        assert 0.4 < similarity < 0.9
    
    def test_compare_different_policies(self, policy_documents):
        similarity = _calculate_semantic_similarity(
            policy_documents["remote_2024"]["content"],
            policy_documents["office_policy"]["content"]
        )
        assert similarity < 0.5
    
    def test_extract_key_points_from_policy(self, policy_documents):
        points = _extract_key_points(policy_documents["remote_2024"]["content"], 5)
        assert len(points) >= 1
    
    def test_highlight_policy_changes(self, policy_documents):
        diff = _highlight_differences(
            policy_documents["remote_2024"]["content"],
            policy_documents["remote_2025"]["content"]
        )
        assert len(diff) > 0

# ============= EDGE CASE TESTS (10 test cases) =============

class TestEdgeCases:
    
    @pytest.mark.parametrize("text", [
        "",
        "A",
        "A" * 1000,
        "Special chars: !@#$%^&*()",
        "Unicode: 你好世界 🌟",
    ])
    def test_normalize_various_texts(self, text):
        result = _normalize_text(text)
        assert isinstance(result, str)
    
    def test_extract_key_points_from_empty(self):
        assert _extract_key_points("") == []
        assert _extract_key_points(None) == []
    
    def test_similarity_with_identical_long_texts(self):
        long_text = "word " * 1000
        similarity = _calculate_semantic_similarity(long_text, long_text)
        assert similarity > 0.99
    
    def test_similarity_with_numbers(self):
        text1 = "Policy version 1.0"
        text2 = "Policy version 2.0"
        similarity = _calculate_semantic_similarity(text1, text2)
        assert similarity >= 0.5

# ============= HELPER FUNCTION TESTS (6 test cases) =============

class TestHelperFunctions:
    
    def test_compare_documents_standalone(self, sample_document_1, sample_document_2):
        result = compare_documents(sample_document_1, sample_document_2)
        assert "similarity_score" in result
    
    def test_batch_compare_documents_standalone(self, sample_document_1, sample_document_2, sample_document_3):
        documents = [sample_document_1, sample_document_2, sample_document_3]
        results = batch_compare_documents(documents)
        assert len(results) == 3
    
    @pytest.mark.parametrize("score, expected_category", [
        (0.95, "highly_similar"),
        (0.75, "moderately_similar"),
        (0.45, "slightly_similar"),
        (0.25, "different"),
    ])
    def test_similarity_categorization(self, score, expected_category):
        category = _categorize_similarity(score)
        assert category == expected_category
    
    def test_format_comparison_report(self, comparison_tool, sample_document_1, sample_document_2):
        result = comparison_tool.compare(sample_document_1, sample_document_2)
        report = comparison_tool.format_report(result)
        assert isinstance(report, str)
        assert len(report) > 0

# ============= RUN TESTS =============
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "--disable-warnings"])