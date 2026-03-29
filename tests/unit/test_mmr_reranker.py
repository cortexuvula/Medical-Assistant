"""
Tests for src/rag/mmr_reranker.py

Covers MMRReranker methods (_cosine_similarity, _jaccard_similarity,
_tokenize, rerank with embedding-based and text-based paths,
calculate_diversity_score) and module-level helpers
(get_mmr_reranker, reset_mmr_reranker, rerank_with_mmr).
Pure math/logic — no network, no Tkinter, no file I/O.
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

import rag.mmr_reranker as mmr_module
from rag.mmr_reranker import (
    MMRReranker,
    get_mmr_reranker,
    reset_mmr_reranker,
    rerank_with_mmr,
)
from rag.models import HybridSearchResult
from rag.search_config import SearchQualityConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config(enable_mmr: bool = True, mmr_lambda: float = 0.7) -> SearchQualityConfig:
    cfg = SearchQualityConfig()
    cfg.enable_mmr = enable_mmr
    cfg.mmr_lambda = mmr_lambda
    return cfg


_ctr = 0


def _result(chunk_text: str = "text", combined_score: float = 0.5,
            embedding: list[float] | None = None) -> HybridSearchResult:
    global _ctr
    _ctr += 1
    return HybridSearchResult(
        chunk_text=chunk_text,
        document_id=f"doc-{_ctr}",
        document_filename=f"file-{_ctr}.pdf",
        chunk_index=_ctr,
        combined_score=combined_score,
        embedding=embedding,
    )


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_mmr_reranker()
    yield
    reset_mmr_reranker()


# ===========================================================================
# _cosine_similarity
# ===========================================================================

class TestCosineSimilarity:
    def setup_method(self):
        self.r = MMRReranker(_config())

    def test_identical_vectors_returns_1(self):
        v = [1.0, 0.0, 0.0]
        assert self.r._cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors_returns_0(self):
        assert self.r._cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_opposite_vectors_returns_minus_1(self):
        assert self.r._cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_45_degree_angle(self):
        # cos(45°) = sqrt(2)/2
        v1 = [1.0, 0.0]
        v2 = [1.0, 1.0]
        expected = 1.0 / math.sqrt(2)
        assert self.r._cosine_similarity(v1, v2) == pytest.approx(expected, abs=1e-9)

    def test_empty_vec1_returns_0(self):
        assert self.r._cosine_similarity([], [1.0, 0.0]) == pytest.approx(0.0)

    def test_empty_vec2_returns_0(self):
        assert self.r._cosine_similarity([1.0, 0.0], []) == pytest.approx(0.0)

    def test_mismatched_lengths_returns_0(self):
        assert self.r._cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == pytest.approx(0.0)

    def test_zero_vector_returns_0(self):
        assert self.r._cosine_similarity([0.0, 0.0], [1.0, 0.0]) == pytest.approx(0.0)

    def test_both_zero_vectors_returns_0(self):
        assert self.r._cosine_similarity([0.0, 0.0], [0.0, 0.0]) == pytest.approx(0.0)

    def test_multi_dim_known_value(self):
        v1 = [1.0, 2.0, 3.0]
        v2 = [1.0, 2.0, 3.0]
        assert self.r._cosine_similarity(v1, v2) == pytest.approx(1.0)

    def test_result_is_float(self):
        result = self.r._cosine_similarity([1.0], [1.0])
        assert isinstance(result, float)


# ===========================================================================
# _jaccard_similarity
# ===========================================================================

class TestJaccardSimilarity:
    def setup_method(self):
        self.r = MMRReranker(_config())

    def test_identical_sets(self):
        s = {"a", "b", "c"}
        assert self.r._jaccard_similarity(s, s) == pytest.approx(1.0)

    def test_disjoint_sets(self):
        assert self.r._jaccard_similarity({"a", "b"}, {"c", "d"}) == pytest.approx(0.0)

    def test_half_overlap(self):
        # {a,b} ∩ {b,c} = {b}, union = {a,b,c} → 1/3
        result = self.r._jaccard_similarity({"a", "b"}, {"b", "c"})
        assert result == pytest.approx(1.0 / 3.0)

    def test_one_empty_set_returns_0(self):
        assert self.r._jaccard_similarity(set(), {"a"}) == pytest.approx(0.0)

    def test_both_empty_sets_returns_0(self):
        assert self.r._jaccard_similarity(set(), set()) == pytest.approx(0.0)

    def test_subset_relation(self):
        # {a} ⊂ {a,b,c} → 1/3
        result = self.r._jaccard_similarity({"a"}, {"a", "b", "c"})
        assert result == pytest.approx(1.0 / 3.0)

    def test_result_is_float(self):
        result = self.r._jaccard_similarity({"x"}, {"x"})
        assert isinstance(result, float)

    def test_result_in_0_1_range(self):
        result = self.r._jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"})
        assert 0.0 <= result <= 1.0


# ===========================================================================
# _tokenize
# ===========================================================================

class TestTokenize:
    def setup_method(self):
        self.r = MMRReranker(_config())

    def test_returns_set(self):
        assert isinstance(self.r._tokenize("hello world"), set)

    def test_simple_words(self):
        assert self.r._tokenize("hello world") == {"hello", "world"}

    def test_lowercase_normalized(self):
        assert self.r._tokenize("Hello World") == {"hello", "world"}

    def test_punctuation_stripped(self):
        result = self.r._tokenize("hello, world!")
        assert "hello" in result
        assert "world" in result

    def test_empty_string_returns_empty_set(self):
        assert self.r._tokenize("") == set()

    def test_deduplication(self):
        result = self.r._tokenize("cat cat dog")
        assert result == {"cat", "dog"}

    def test_numeric_tokens(self):
        result = self.r._tokenize("patient 42 years")
        assert "42" in result
        assert "years" in result


# ===========================================================================
# rerank — MMR disabled path
# ===========================================================================

class TestRerankMMRDisabled:
    def setup_method(self):
        self.r = MMRReranker(_config(enable_mmr=False))

    def test_mmr_disabled_returns_top_k_slice(self):
        results = [_result(combined_score=0.9 - i * 0.1) for i in range(5)]
        out = self.r.rerank(results, top_k=3)
        assert len(out) == 3
        assert out is not results  # It's a slice (new list ref)

    def test_mmr_disabled_preserves_order(self):
        results = [_result(combined_score=float(i)) for i in range(5)]
        out = self.r.rerank(results, top_k=2)
        assert out[0].combined_score == pytest.approx(0.0)

    def test_mmr_disabled_empty_input_returns_empty(self):
        assert self.r.rerank([], top_k=3) == []


# ===========================================================================
# rerank — edge cases
# ===========================================================================

class TestRerankEdgeCases:
    def setup_method(self):
        self.r = MMRReranker(_config())

    def test_empty_results_returns_empty(self):
        assert self.r.rerank([], top_k=5) == []

    def test_fewer_results_than_top_k_returns_all(self):
        results = [_result(combined_score=0.9), _result(combined_score=0.5)]
        out = self.r.rerank(results, top_k=5)
        assert len(out) == 2

    def test_fewer_results_sets_mmr_score(self):
        r = _result(combined_score=0.8)
        self.r.rerank([r], top_k=5)
        assert r.mmr_score == pytest.approx(0.8)

    def test_exactly_top_k_returns_all(self):
        results = [_result(combined_score=0.9 - i * 0.1) for i in range(5)]
        out = self.r.rerank(results, top_k=5)
        assert len(out) == 5


# ===========================================================================
# rerank — text-based path (no embeddings)
# ===========================================================================

class TestRerankTextBased:
    def setup_method(self):
        self.r = MMRReranker(_config(mmr_lambda=0.7))

    def test_no_embeddings_falls_back_to_text_based(self):
        results = [
            _result("the cat sat on the mat", combined_score=0.9),
            _result("the cat sat on the mat", combined_score=0.8),
            _result("unrelated medical terms aspirin dosage", combined_score=0.7),
            _result("different topic entirely oxygen therapy", combined_score=0.6),
        ]
        out = self.r.rerank(results, top_k=3)
        assert len(out) == 3

    def test_text_based_returns_list(self):
        results = [_result(f"doc {i}", combined_score=1.0 - i * 0.1)
                   for i in range(6)]
        out = self.r.rerank(results, top_k=3)
        assert isinstance(out, list)

    def test_text_based_sets_mmr_score_on_selected(self):
        results = [_result(f"document {i}", combined_score=0.9 - i * 0.1)
                   for i in range(6)]
        out = self.r.rerank(results, top_k=3)
        for r in out:
            assert r.mmr_score is not None

    def test_diverse_text_preferred_over_duplicate(self):
        """With lambda=0.7, a moderately-relevant diverse doc beats a duplicate high-relevance."""
        high_dup = _result("aspirin aspirin aspirin", combined_score=0.95)
        medium_dup = _result("aspirin aspirin aspirin", combined_score=0.85)
        diverse = _result("oxygen therapy breathing", combined_score=0.75)
        extra = _result("blood pressure measurement", combined_score=0.65)
        results = [high_dup, medium_dup, diverse, extra]
        out = self.r.rerank(results, top_k=2)
        # First pick should be the highest scorer
        assert out[0] is high_dup
        # Second pick should prefer the diverse doc over the duplicate
        assert out[1] is not medium_dup


# ===========================================================================
# rerank — embedding-based path
# ===========================================================================

class TestRerankEmbeddingBased:
    def setup_method(self):
        self.r = MMRReranker(_config(mmr_lambda=0.7))

    def _make_result(self, embedding, score):
        return _result(chunk_text="text", combined_score=score, embedding=embedding)

    def test_embedding_based_returns_top_k(self):
        results = [
            self._make_result([1.0, 0.0], 0.9),
            self._make_result([0.0, 1.0], 0.8),
            self._make_result([1.0, 0.0], 0.7),
            self._make_result([0.0, 1.0], 0.6),
        ]
        out = self.r.rerank(results, top_k=2)
        assert len(out) == 2

    def test_embedding_based_sets_mmr_score(self):
        results = [
            self._make_result([1.0, 0.0], 0.9),
            self._make_result([0.0, 1.0], 0.8),
            self._make_result([1.0, 0.0], 0.7),
        ]
        out = self.r.rerank(results, top_k=2)
        for r in out:
            assert r.mmr_score is not None

    def test_orthogonal_embeddings_selected_diversely(self):
        """Orthogonal embeddings (sim=0) → diversity is free, so relevance dominates."""
        r1 = self._make_result([1.0, 0.0], 0.9)
        r2 = self._make_result([0.0, 1.0], 0.8)
        r3 = self._make_result([1.0, 0.0], 0.7)  # similar to r1
        results = [r1, r2, r3]
        out = self.r.rerank(results, top_k=2)
        # r1 should be first (highest score)
        assert out[0] is r1
        # r2 should be second (diverse + high score beats r3 which is similar to r1)
        assert out[1] is r2

    def test_first_selected_has_no_diversity_penalty(self):
        """First pick is always highest combined_score (no prior selected set)."""
        results = [
            self._make_result([1.0, 0.0], 0.9),
            self._make_result([1.0, 0.0], 0.95),  # highest
            self._make_result([0.0, 1.0], 0.8),
        ]
        out = self.r.rerank(results, top_k=1)
        assert out[0].combined_score == pytest.approx(0.95)


# ===========================================================================
# calculate_diversity_score
# ===========================================================================

class TestCalculateDiversityScore:
    def setup_method(self):
        self.r = MMRReranker(_config())

    def test_single_result_returns_1(self):
        assert self.r.calculate_diversity_score([_result()]) == pytest.approx(1.0)

    def test_empty_list_returns_1(self):
        assert self.r.calculate_diversity_score([]) == pytest.approx(1.0)

    def test_identical_text_results_are_not_diverse(self):
        results = [_result("cat sat mat"), _result("cat sat mat")]
        score = self.r.calculate_diversity_score(results)
        # Jaccard similarity will be 1.0 (identical) → diversity = 0.0
        assert score == pytest.approx(0.0)

    def test_disjoint_text_results_are_fully_diverse(self):
        results = [_result("alpha beta gamma"), _result("one two three")]
        score = self.r.calculate_diversity_score(results)
        assert score == pytest.approx(1.0)

    def test_partial_diversity_is_between_0_and_1(self):
        results = [_result("cat dog bird"), _result("cat fish snake")]
        score = self.r.calculate_diversity_score(results)
        assert 0.0 < score < 1.0

    def test_embedding_based_diversity(self):
        r1 = _result(embedding=[1.0, 0.0])
        r2 = _result(embedding=[0.0, 1.0])
        score = self.r.calculate_diversity_score([r1, r2])
        # cos([1,0],[0,1])=0 → diversity=1.0
        assert score == pytest.approx(1.0)

    def test_identical_embeddings_zero_diversity(self):
        r1 = _result(embedding=[1.0, 0.0])
        r2 = _result(embedding=[1.0, 0.0])
        score = self.r.calculate_diversity_score([r1, r2])
        assert score == pytest.approx(0.0)

    def test_result_is_float(self):
        score = self.r.calculate_diversity_score([_result("a"), _result("b")])
        assert isinstance(score, float)

    def test_three_results_uses_all_pairs(self):
        """Ensure 3-result diversity is calculated (3 pairs: (0,1),(0,2),(1,2))."""
        results = [_result("abc"), _result("def"), _result("ghi")]
        score = self.r.calculate_diversity_score(results)
        assert score == pytest.approx(1.0)  # all disjoint


# ===========================================================================
# Singleton and module helpers
# ===========================================================================

class TestSingletonAndHelpers:
    def test_get_mmr_reranker_returns_mmr_reranker(self):
        assert isinstance(get_mmr_reranker(), MMRReranker)

    def test_get_mmr_reranker_returns_same_instance(self):
        a = get_mmr_reranker()
        b = get_mmr_reranker()
        assert a is b

    def test_reset_clears_singleton(self):
        a = get_mmr_reranker()
        reset_mmr_reranker()
        b = get_mmr_reranker()
        assert a is not b

    def test_rerank_with_mmr_empty_returns_empty(self):
        assert rerank_with_mmr([]) == []

    def test_rerank_with_mmr_returns_list(self):
        results = [_result(f"doc {i}", combined_score=0.9 - i * 0.1) for i in range(3)]
        out = rerank_with_mmr(results, top_k=2)
        assert isinstance(out, list)

    def test_rerank_with_mmr_respects_top_k(self):
        results = [_result(combined_score=0.9 - i * 0.1) for i in range(10)]
        out = rerank_with_mmr(results, top_k=3)
        assert len(out) == 3
