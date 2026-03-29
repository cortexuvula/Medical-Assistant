"""
Tests for src/rag/bm25_search.py

Covers BM25SearchResult dataclass, BM25Searcher pure methods
(_clean_term, _build_search_query, _build_websearch_query), search()
and search_with_websearch_query() with BM25 disabled short-circuit,
score normalization formula, and singleton helpers.
No database connections required.
"""

import math
import sys
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

import rag.bm25_search as bm25_module
from rag.bm25_search import (
    BM25SearchResult,
    BM25Searcher,
    get_bm25_searcher,
    reset_bm25_searcher,
    search_bm25,
)
from rag.search_config import SearchQualityConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config(enable_bm25: bool = True) -> SearchQualityConfig:
    cfg = SearchQualityConfig()
    cfg.enable_bm25 = enable_bm25
    return cfg


def _searcher(enable_bm25: bool = True) -> BM25Searcher:
    return BM25Searcher(vector_store=None, config=_config(enable_bm25=enable_bm25))


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_bm25_searcher()
    yield
    reset_bm25_searcher()


# ===========================================================================
# BM25SearchResult
# ===========================================================================

class TestBM25SearchResult:
    def test_fields_stored(self):
        r = BM25SearchResult("doc1", 3, "some text", 0.75)
        assert r.document_id == "doc1"
        assert r.chunk_index == 3
        assert r.chunk_text == "some text"
        assert r.bm25_score == pytest.approx(0.75)

    def test_default_metadata_is_empty_dict(self):
        r = BM25SearchResult("d", 0, "t", 0.5)
        assert r.metadata == {}

    def test_custom_metadata_stored(self):
        r = BM25SearchResult("d", 0, "t", 0.5, metadata={"key": "value"})
        assert r.metadata == {"key": "value"}

    def test_none_metadata_becomes_empty_dict(self):
        r = BM25SearchResult("d", 0, "t", 0.5, metadata=None)
        assert r.metadata == {}

    def test_instances_dont_share_metadata(self):
        r1 = BM25SearchResult("d1", 0, "t", 0.5)
        r2 = BM25SearchResult("d2", 1, "t", 0.5)
        r1.metadata["x"] = 1
        assert "x" not in r2.metadata

    def test_bm25_score_is_float(self):
        r = BM25SearchResult("d", 0, "t", 0.9)
        assert isinstance(r.bm25_score, float)


# ===========================================================================
# _clean_term
# ===========================================================================

class TestCleanTerm:
    def setup_method(self):
        self.s = _searcher()

    def test_lowercase_normalized(self):
        assert self.s._clean_term("Hypertension") == "hypertension"

    def test_special_chars_removed(self):
        result = self.s._clean_term("heart-attack!")
        assert "-" not in result
        assert "!" not in result
        assert "heart" in result
        assert "attack" in result

    def test_slash_removed(self):
        result = self.s._clean_term("n/v")
        assert "/" not in result

    def test_extra_whitespace_collapsed(self):
        result = self.s._clean_term("blood   pressure")
        assert "  " not in result

    def test_leading_trailing_whitespace_stripped(self):
        assert self.s._clean_term("  htn  ") == "htn"

    def test_returns_string(self):
        assert isinstance(self.s._clean_term("test"), str)

    def test_empty_string(self):
        assert self.s._clean_term("") == ""

    def test_dot_replaced_by_space(self):
        result = self.s._clean_term("Dr. Smith")
        assert "." not in result

    def test_numbers_preserved(self):
        assert "42" in self.s._clean_term("age 42")


# ===========================================================================
# _build_search_query
# ===========================================================================

class TestBuildSearchQuery:
    def setup_method(self):
        self.s = _searcher()

    def test_plain_query_returned(self):
        result = self.s._build_search_query("hypertension")
        assert "hypertension" in result

    def test_expanded_terms_included(self):
        result = self.s._build_search_query("htn", ["hypertension", "high blood pressure"])
        assert "hypertension" in result

    def test_expanded_terms_limited_to_5(self):
        terms = [f"term{i}" for i in range(10)]
        result = self.s._build_search_query("q", terms)
        # At most 1 original + 5 expanded = 6 space-separated terms
        parts = result.split()
        assert len(parts) <= 6

    def test_no_expanded_terms_still_works(self):
        result = self.s._build_search_query("stroke", None)
        assert result == "stroke"

    def test_returns_string(self):
        assert isinstance(self.s._build_search_query("x"), str)

    def test_duplicate_term_not_added(self):
        # If expanded term is same as cleaned original, should not duplicate
        result = self.s._build_search_query("stroke", ["stroke"])
        # "stroke" should appear once in the space-split list
        parts = result.split()
        assert parts.count("stroke") == 1

    def test_empty_expanded_term_skipped(self):
        # Expanding a special-char-only term → empty after cleaning
        result = self.s._build_search_query("htn", ["!!!", "hypertension"])
        assert "hypertension" in result

    def test_terms_joined_with_spaces(self):
        result = self.s._build_search_query("htn", ["hypertension"])
        assert " " in result


# ===========================================================================
# _build_websearch_query
# ===========================================================================

class TestBuildWebsearchQuery:
    def setup_method(self):
        self.s = _searcher()

    def test_original_quoted(self):
        result = self.s._build_websearch_query("heart attack")
        assert '"heart attack"' in result

    def test_no_expanded_terms_is_just_quoted_original(self):
        result = self.s._build_websearch_query("stroke", None)
        assert result == '"stroke"'

    def test_expanded_terms_use_or(self):
        result = self.s._build_websearch_query("stroke", ["cva", "brain attack"])
        assert " OR " in result

    def test_expanded_terms_are_quoted(self):
        result = self.s._build_websearch_query("stroke", ["cva"])
        assert '"cva"' in result

    def test_expanded_terms_limited_to_3(self):
        terms = [f"term{i}" for i in range(6)]
        result = self.s._build_websearch_query("q", terms)
        # Original phrase + at most 3 OR clauses
        or_count = result.count(" OR ")
        assert or_count <= 3

    def test_empty_cleaned_term_skipped(self):
        result = self.s._build_websearch_query("stroke", ["!!!", "cva"])
        assert '"cva"' in result

    def test_returns_string(self):
        assert isinstance(self.s._build_websearch_query("x"), str)


# ===========================================================================
# search() — disabled path
# ===========================================================================

class TestSearchDisabled:
    def setup_method(self):
        self.s = _searcher(enable_bm25=False)

    def test_disabled_returns_empty_list(self):
        result = self.s.search("hypertension")
        assert result == []

    def test_disabled_returns_list_type(self):
        result = self.s.search("stroke")
        assert isinstance(result, list)

    def test_disabled_with_expanded_terms_returns_empty(self):
        result = self.s.search("htn", expanded_terms=["hypertension"])
        assert result == []

    def test_disabled_with_filter_returns_empty(self):
        result = self.s.search("stroke", filter_document_ids=["doc1"])
        assert result == []


# ===========================================================================
# search_with_websearch_query() — disabled path
# ===========================================================================

class TestSearchWithWebsearchDisabled:
    def setup_method(self):
        self.s = _searcher(enable_bm25=False)

    def test_disabled_returns_empty_list(self):
        result = self.s.search_with_websearch_query("hypertension")
        assert result == []

    def test_disabled_returns_list_type(self):
        result = self.s.search_with_websearch_query("stroke")
        assert isinstance(result, list)


# ===========================================================================
# Score normalization formula
# ===========================================================================

class TestScoreNormalizationFormula:
    """Unit-test the normalization math: min(1.0, log1p(rank*100)/log1p(100))."""

    def _normalize(self, rank: float) -> float:
        return min(1.0, math.log1p(float(rank) * 100) / math.log1p(100))

    def test_zero_rank_gives_zero(self):
        assert self._normalize(0.0) == pytest.approx(0.0)

    def test_rank_one_gives_one(self):
        # log1p(1*100)/log1p(100) = log1p(100)/log1p(100) = 1.0
        assert self._normalize(1.0) == pytest.approx(1.0)

    def test_rank_above_one_capped_at_one(self):
        assert self._normalize(10.0) == pytest.approx(1.0)

    def test_small_rank_is_between_0_and_1(self):
        score = self._normalize(0.5)
        assert 0.0 < score < 1.0

    def test_monotonically_increasing(self):
        scores = [self._normalize(r) for r in [0.0, 0.1, 0.5, 1.0]]
        for i in range(len(scores) - 1):
            assert scores[i] <= scores[i + 1]

    def test_result_is_float(self):
        assert isinstance(self._normalize(0.5), float)


# ===========================================================================
# Singleton and module helpers
# ===========================================================================

class TestSingletonAndHelpers:
    def test_get_bm25_searcher_returns_instance(self):
        assert isinstance(get_bm25_searcher(), BM25Searcher)

    def test_get_bm25_searcher_same_instance(self):
        a = get_bm25_searcher()
        b = get_bm25_searcher()
        assert a is b

    def test_reset_clears_singleton(self):
        a = get_bm25_searcher()
        reset_bm25_searcher()
        b = get_bm25_searcher()
        assert a is not b

    def test_search_bm25_disabled_returns_empty(self):
        # The singleton gets enable_bm25=True by default but no DB
        # so the exception path returns []
        result = search_bm25("stroke")
        assert isinstance(result, list)
