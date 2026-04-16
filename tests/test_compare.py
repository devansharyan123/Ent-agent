import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import List, Dict, Any, Optional

# Assuming your comparison tool is at: backend.agents.tools.comparison_tool.py
from backend.agents.tools.comparison_tool import (
    ComparisonTool,
    ComparisonResult,
    DocumentComparator,
    SimilarityScorer,
    _normalize_text,
    _extract_key_points,
    _calculate_semantic_similarity,
    _highlight_differences,
    compare_documents,
    batch_compare_documents
)


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
    embedder.encode.return_value = np.array([0.1, 0.2, 0.3, 0.4])
    return embedder


@pytest.fixture
def comparison_tool(mock_embedder):
    with patch("backend.agents.tools.comparison_tool.get_embedder", return_value=mock_embedder):
        return ComparisonTool()


# ============= TEXT NORMALIZATION TESTS (10 test cases) =============

class TestTextNormalization:
    
    @pytest.mark.parametrize("input_text, expected", [
        ("  Hello World  ", "Hello World"),
        ("\n\tMultiple spaces\n\t", "Multiple spaces"),
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


# ============= KEY POINT EXTRACTION TESTS (15 test cases) =============

class TestKeyPointExtraction:
    
    @pytest.mark.parametrize("text, max_points, expected_length_range", [
        ("This is a simple sentence.", 5, (1, 2)),
        ("First point. Second point. Third point.", 3, (2, 4)),
        ("", 5, (0, 1)),
        (None, 5, (0, 1)),
        ("Very long " * 100 + "text.", 10, (1, 11)),
    ])
    def test_extract_key_points_basic(self, text, max_points, expected_length_range):
        result = _extract_key_points(text, max_points)
        assert expected_length_range[0] <= len(result) <= expected_length_range[1]
    
    @pytest.mark.parametrize("text, expected_keywords", [
        ("Employees must submit leave requests 2 weeks in advance.", ["leave", "requests", "weeks"]),
        ("Salary is paid on the last working day of each month.", ["salary", "paid", "month"]),
        ("Health insurance covers dental and vision.", ["health", "insurance", "dental", "vision"]),
    ])
    def test_extract_key_points_keywords(self, text, expected_keywords):
        result = _extract_key_points(text, 5)
        result_text = " ".join(result).lower()
        for keyword in expected_keywords:
            assert keyword in result_text
    
    def test_extract_key_points_max_points_respected(self):
        text = "Point 1. Point 2. Point 3. Point 4. Point 5. Point 6."
        for max_points in [1, 2, 3, 4, 5]:
            result = _extract_key_points(text, max_points)
            assert len(result) <= max_points
    
    def test_extract_key_points_duplicate_handling(self):
        text = "Same point. Same point. Different point."
        result = _extract_key_points(text, 5)
        # Should handle duplicates gracefully
        assert len(result) >= 1


# ============= SIMILARITY SCORING TESTS (15 test cases) =============

class TestSimilarityScoring:
    
    @pytest.mark.parametrize("text1, text2, min_similarity, max_similarity", [
        ("Same text", "Same text", 0.9, 1.0),
        ("Very different", "Completely unrelated", 0.0, 0.5),
        ("Partial overlap", "Partial overlap here", 0.5, 0.9),
        ("", "", 0.0, 0.1),
        (None, "Some text", 0.0, 0.1),
        ("Short", "Very long text with much more content", 0.0, 0.5),
    ])
    def test_calculate_semantic_similarity(self, text1, text2, min_similarity, max_similarity, mock_embedder):
        similarity = _calculate_semantic_similarity(text1, text2, mock_embedder)
        assert min_similarity <= similarity <= max_similarity
    
    def test_similarity_with_identical_texts(self, mock_embedder):
        text = "This is a test sentence for similarity scoring."
        similarity = _calculate_semantic_similarity(text, text, mock_embedder)
        assert similarity > 0.95
    
    def test_similarity_with_empty_strings(self, mock_embedder):
        similarity = _calculate_semantic_similarity("", "", mock_embedder)
        assert similarity == 0.0
    
    @pytest.mark.parametrize("embedding_dim", [128, 256, 512, 768, 1024])
    def test_similarity_different_embedding_dimensions(self, embedding_dim, mock_embedder):
        mock_embedder.encode.return_value = np.array([0.1] * embedding_dim)
        similarity = _calculate_semantic_similarity("text1", "text2", mock_embedder)
        assert 0 <= similarity <= 1
    
    def test_similarity_error_handling(self, mock_embedder):
        mock_embedder.encode.side_effect = Exception("Embedding failed")
        similarity = _calculate_semantic_similarity("text1", "text2", mock_embedder)
        assert similarity == 0.0


# ============= DIFFERENCE HIGHLIGHTING TESTS (10 test cases) =============

class TestDifferenceHighlighting:
    
    @pytest.mark.parametrize("original, modified, expected_contains", [
        ("Hello world", "Hello universe", ["Hello", "universe"]),
        ("The cat sat", "The dog sat", ["dog", "sat"]),
        ("No changes", "No changes", []),
        ("", "New text", ["New", "text"]),
    ])
    def test_highlight_differences(self, original, modified, expected_contains):
        result = _highlight_differences(original, modified)
        for item in expected_contains:
            assert item in result
    
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
    
    def test_highlight_differences_long_text(self):
        long_text = "word " * 1000
        result = _highlight_differences(long_text, long_text + " extra")
        assert "extra" in result


# ============= COMPARISON RESULT TESTS (10 test cases) =============

class TestComparisonResult:
    
    def test_comparison_result_creation(self):
        result = ComparisonResult(
            document1_id="doc1",
            document2_id="doc2",
            similarity_score=0.85,
            differences=["diff1", "diff2"],
            key_points_shared=["point1"],
            key_points_unique_doc1=["unique1"],
            key_points_unique_doc2=["unique2"],
            timestamp=datetime.now()
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
        assert "differences" in result_dict
    
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
    
    def test_comparison_result_empty_lists(self):
        result = ComparisonResult(
            document1_id="doc1",
            document2_id="doc2",
            similarity_score=0.5,
            differences=[],
            key_points_shared=[],
            key_points_unique_doc1=[],
            key_points_unique_doc2=[]
        )
        assert len(result.differences) == 0


# ============= DOCUMENT COMPARATOR TESTS (10 test cases) =============

class TestDocumentComparator:
    
    def test_comparator_initialization(self, mock_embedder):
        comparator = DocumentComparator(embedder=mock_embedder, similarity_threshold=0.7)
        assert comparator.similarity_threshold == 0.7
    
    @pytest.mark.parametrize("threshold", [0.0, 0.3, 0.5, 0.8, 1.0])
    def test_comparator_different_thresholds(self, threshold, mock_embedder):
        comparator = DocumentComparator(embedder=mock_embedder, similarity_threshold=threshold)
        assert comparator.similarity_threshold == threshold
    
    def test_compare_documents_basic(self, sample_document_1, sample_document_2, mock_embedder):
        comparator = DocumentComparator(embedder=mock_embedder)
        result = comparator.compare(sample_document_1, sample_document_2)
        
        assert isinstance(result, ComparisonResult)
        assert result.document1_id == sample_document_1["id"]
        assert result.document2_id == sample_document_2["id"]
    
    def test_compare_identical_documents(self, sample_document_1, mock_embedder):
        comparator = DocumentComparator(embedder=mock_embedder)
        result = comparator.compare(sample_document_1, sample_document_1)
        
        assert result.similarity_score > 0.9
        assert len(result.differences) == 0
    
    def test_compare_different_documents(self, sample_document_1, sample_document_3, mock_embedder):
        comparator = DocumentComparator(embedder=mock_embedder)
        result = comparator.compare(sample_document_1, sample_document_3)
        
        # Different policies should have lower similarity
        assert result.similarity_score < 0.7
    
    @patch("backend.agents.tools.comparison_tool._calculate_semantic_similarity")
    def test_compare_with_mock_similarity(self, mock_similarity, sample_document_1, sample_document_2):
        mock_similarity.return_value = 0.95
        comparator = DocumentComparator(embedder=Mock())
        result = comparator.compare(sample_document_1, sample_document_2)
        
        assert result.similarity_score == 0.95


# ============= MAIN COMPARISON TOOL TESTS (15 test cases) =============

class TestComparisonTool:
    
    def test_tool_initialization(self, comparison_tool):
        assert comparison_tool is not None
        assert hasattr(comparison_tool, "compare")
        assert hasattr(comparison_tool, "batch_compare")
    
    def test_compare_two_documents(self, comparison_tool, sample_document_1, sample_document_2):
        result = comparison_tool.compare(sample_document_1, sample_document_2)
        
        assert "document1_id" in result
        assert "document2_id" in result
        assert "similarity_score" in result
        assert "differences" in result
    
    @pytest.mark.parametrize("doc1, doc2, should_raise", [
        ({"id": "1", "content": "text"}, {"id": "2", "content": "text"}, False),
        (None, {"id": "2", "content": "text"}, True),
        ({"id": "1", "content": "text"}, None, True),
        ({}, {"id": "2", "content": "text"}, True),
        ({"id": "1"}, {"id": "2", "content": "text"}, True),
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
        # Should have C(3,2) = 3 comparisons
        assert len(results) == 3
    
    def test_batch_compare_empty_list(self, comparison_tool):
        results = comparison_tool.batch_compare([])
        assert results == []
    
    def test_batch_compare_single_document(self, comparison_tool, sample_document_1):
        results = comparison_tool.batch_compare([sample_document_1])
        assert results == []
    
    @pytest.mark.parametrize("batch_size", [2, 5, 10])
    def test_batch_compare_with_large_batch(self, comparison_tool, batch_size):
        documents = [{"id": str(i), "content": f"Document {i}"} for i in range(batch_size)]
        results = comparison_tool.batch_compare(documents)
        
        expected_pairs = batch_size * (batch_size - 1) // 2
        assert len(results) == expected_pairs
    
    @patch("backend.agents.tools.comparison_tool.DocumentComparator")
    def test_compare_with_custom_threshold(self, mock_comparator_class, mock_embedder):
        mock_comparator = Mock()
        mock_comparator.compare.return_value = ComparisonResult(
            document1_id="doc1", document2_id="doc2", similarity_score=0.8,
            differences=[], key_points_shared=[], key_points_unique_doc1=[],
            key_points_unique_doc2=[]
        )
        mock_comparator_class.return_value = mock_comparator
        
        tool = ComparisonTool(embedder=mock_embedder, similarity_threshold=0.75)
        result = tool.compare({"id": "doc1", "content": "text"}, {"id": "doc2", "content": "text"})
        
        assert result.similarity_score == 0.8
    
    def test_compare_documents_with_metadata(self, comparison_tool, sample_document_1, sample_document_2):
        result = comparison_tool.compare(sample_document_1, sample_document_2)
        
        assert isinstance(result, dict)
        assert "document1_id" in result
        assert "document2_id" in result


# ============= INTEGRATION EDGE CASE TESTS (10 test cases) =============

class TestEdgeCasesAndIntegration:
    
    @pytest.mark.parametrize("content_type", [
        "text/plain",
        "text/markdown",
        "application/pdf",
        "application/docx",
    ])
    def test_different_content_types(self, content_type, comparison_tool):
        doc1 = {"id": "1", "content": "Sample text", "content_type": content_type}
        doc2 = {"id": "2", "content": "Sample text", "content_type": content_type}
        
        result = comparison_tool.compare(doc1, doc2)
        assert result is not None
    
    def test_very_large_documents(self, comparison_tool):
        large_content = "This is a sentence. " * 10000
        doc1 = {"id": "1", "content": large_content}
        doc2 = {"id": "2", "content": large_content + " Additional text."}
        
        result = comparison_tool.compare(doc1, doc2)
        assert "similarity_score" in result
    
    def test_unicode_and_special_characters(self, comparison_tool):
        doc1 = {"id": "1", "content": "Café résumé naïve 你好 🌟"}
        doc2 = {"id": "2", "content": "Cafe resume naive 你好 🌟"}
        
        result = comparison_tool.compare(doc1, doc2)
        assert result is not None
    
    @pytest.mark.parametrize("language", ["en", "es", "fr", "de", "zh", "ja", "ar"])
    def test_multilingual_documents(self, comparison_tool, language):
        contents = {
            "en": "Hello world",
            "es": "Hola mundo",
            "fr": "Bonjour le monde",
            "de": "Hallo Welt",
            "zh": "你好世界",
            "ja": "こんにちは世界",
            "ar": "مرحبا بالعالم"
        }
        
        doc1 = {"id": "1", "content": contents.get(language, "Test")}
        doc2 = {"id": "2", "content": contents.get(language, "Test")}
        
        result = comparison_tool.compare(doc1, doc2)
        assert result is not None
    
    def test_concurrent_comparisons(self, comparison_tool, sample_document_1, sample_document_2):
        import threading
        results = []
        
        def compare_wrapper():
            result = comparison_tool.compare(sample_document_1, sample_document_2)
            results.append(result)
        
        threads = [threading.Thread(target=compare_wrapper) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(results) == 10
        assert all(r is not None for r in results)
    
    def test_memory_usage_with_many_comparisons(self, comparison_tool):
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        
        documents = [{"id": str(i), "content": f"Document {i} content"} for i in range(50)]
        results = comparison_tool.batch_compare(documents)
        
        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = memory_after - memory_before
        
        # Memory increase should be reasonable (< 500MB)
        assert memory_increase < 500
        assert len(results) == 1225  # 50*49/2
    
    @patch("backend.agents.tools.comparison_tool.time.sleep")
    def test_timeout_handling(self, mock_sleep, comparison_tool):
        mock_sleep.side_effect = TimeoutError("Operation timed out")
        
        with pytest.raises(TimeoutError):
            # Assuming comparison tool has timeout mechanism
            comparison_tool.compare(
                {"id": "1", "content": "text"},
                {"id": "2", "content": "text"},
                timeout=0.001
            )
    
    def test_caching_mechanism(self, comparison_tool, sample_document_1, sample_document_2):
        # First comparison
        result1 = comparison_tool.compare(sample_document_1, sample_document_2)
        
        # Second comparison (should use cache)
        result2 = comparison_tool.compare(sample_document_1, sample_document_2)
        
        assert result1 == result2
    
    def test_error_recovery(self, comparison_tool, mock_embedder):
        # Make embedder fail on first call, succeed on second
        call_count = 0
        def failing_encode(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Temporary failure")
            return np.array([0.1, 0.2, 0.3])
        
        mock_embedder.encode.side_effect = failing_encode
        
        result = comparison_tool.compare(
            {"id": "1", "content": "text"},
            {"id": "2", "content": "text"}
        )
        
        assert result is not None
        assert call_count == 2
    
    def test_logging_and_audit(self, comparison_tool, sample_document_1, sample_document_2):
        with patch("logging.getLogger") as mock_logger:
            comparison_tool.compare(sample_document_1, sample_document_2)
            
            # Verify that comparison was logged
            mock_logger.return_value.info.assert_called()


# ============= HELPER FUNCTION TESTS (Additional test cases) =============

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
        (0.15, "different"),
    ])
    def test_similarity_categorization(self, score, expected_category):
        from backend.agents.tools.comparison_tool import _categorize_similarity
        category = _categorize_similarity(score)
        assert category == expected_category
    
    def test_format_comparison_report(self, comparison_tool, sample_document_1, sample_document_2):
        result = comparison_tool.compare(sample_document_1, sample_document_2)
        report = comparison_tool.format_report(result)
        
        assert isinstance(report, str)
        assert len(report) > 0
        assert "Similarity Score" in report or "similarity" in report.lower()


# ============= RUN TESTS =============
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])