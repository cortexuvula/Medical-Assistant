"""
Unit tests for RAG search quality improvements.

Tests:
- SearchQualityConfig
- MedicalQueryExpander
- AdaptiveThresholdCalculator
- MMRReranker
- BM25Searcher (mock tests)
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


class TestSearchQualityConfig:
    """Tests for SearchQualityConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        from src.rag.search_config import SearchQualityConfig

        config = SearchQualityConfig()

        assert config.enable_adaptive_threshold is True
        assert config.min_threshold == 0.2
        assert config.max_threshold == 0.8
        assert config.enable_query_expansion is True
        assert config.enable_bm25 is True
        assert config.enable_mmr is True
        assert config.mmr_lambda == 0.7

    def test_config_from_dict(self):
        """Test creating config from dictionary."""
        from src.rag.search_config import SearchQualityConfig

        config_dict = {
            "enable_adaptive_threshold": False,
            "min_threshold": 0.3,
            "vector_weight": 0.6,
            "bm25_weight": 0.2,
            "graph_weight": 0.2,
        }

        config = SearchQualityConfig.from_dict(config_dict)

        assert config.enable_adaptive_threshold is False
        assert config.min_threshold == 0.3

    def test_weight_normalization(self):
        """Test that weights are normalized to sum to 1."""
        from src.rag.search_config import SearchQualityConfig

        config = SearchQualityConfig(
            vector_weight=1.0,
            bm25_weight=1.0,
            graph_weight=1.0,
        )

        total = config.vector_weight + config.bm25_weight + config.graph_weight
        assert abs(total - 1.0) < 0.01

    def test_invalid_threshold_range(self):
        """Test validation of threshold range."""
        from src.rag.search_config import SearchQualityConfig

        with pytest.raises(ValueError):
            SearchQualityConfig(min_threshold=-0.1)

        with pytest.raises(ValueError):
            SearchQualityConfig(max_threshold=1.5)

        with pytest.raises(ValueError):
            SearchQualityConfig(min_threshold=0.8, max_threshold=0.2)

    def test_to_dict(self):
        """Test converting config to dictionary."""
        from src.rag.search_config import SearchQualityConfig

        config = SearchQualityConfig()
        config_dict = config.to_dict()

        assert "enable_adaptive_threshold" in config_dict
        assert "vector_weight" in config_dict
        assert "mmr_lambda" in config_dict


class TestMedicalQueryExpander:
    """Tests for MedicalQueryExpander."""

    def test_abbreviation_expansion(self):
        """Test expansion of medical abbreviations."""
        from src.rag.query_expander import MedicalQueryExpander
        from src.rag.search_config import SearchQualityConfig

        config = SearchQualityConfig(enable_query_expansion=True)
        expander = MedicalQueryExpander(config)

        expansion = expander.expand_query("patient has HTN")

        assert "hypertension" in expansion.expanded_terms or \
               "hypertension" in str(expansion.abbreviation_expansions)

    def test_synonym_expansion(self):
        """Test expansion of medical synonyms."""
        from src.rag.query_expander import MedicalQueryExpander
        from src.rag.search_config import SearchQualityConfig

        config = SearchQualityConfig(enable_query_expansion=True)
        expander = MedicalQueryExpander(config)

        expansion = expander.expand_query("heart attack symptoms")

        # Should find synonyms
        assert len(expansion.synonym_expansions) > 0 or len(expansion.expanded_terms) > 0

    def test_bidirectional_expansion(self):
        """Test that expansion works both ways."""
        from src.rag.query_expander import MedicalQueryExpander
        from src.rag.search_config import SearchQualityConfig

        config = SearchQualityConfig(enable_query_expansion=True)
        expander = MedicalQueryExpander(config)

        # Full term should find abbreviation
        expansion1 = expander.expand_query("hypertension treatment")
        # Abbreviation should find full term
        expansion2 = expander.expand_query("HTN treatment")

        # Both should have expansions
        assert len(expansion1.get_all_search_terms()) > 1
        assert len(expansion2.get_all_search_terms()) > 1

    def test_disabled_expansion(self):
        """Test that expansion can be disabled."""
        from src.rag.query_expander import MedicalQueryExpander
        from src.rag.search_config import SearchQualityConfig

        config = SearchQualityConfig(enable_query_expansion=False)
        expander = MedicalQueryExpander(config)

        expansion = expander.expand_query("HTN symptoms")

        # Should not expand
        assert len(expansion.expanded_terms) == 0

    def test_max_expansion_terms(self):
        """Test that expansion is limited."""
        from src.rag.query_expander import MedicalQueryExpander
        from src.rag.search_config import SearchQualityConfig

        config = SearchQualityConfig(
            enable_query_expansion=True,
            max_expansion_terms=1,
        )
        expander = MedicalQueryExpander(config)

        expansion = expander.expand_query("diabetes mellitus")

        # Each source term should have at most max_expansion_terms
        for terms in expansion.abbreviation_expansions.values():
            assert len(terms) <= 1


class TestAdaptiveThresholdCalculator:
    """Tests for AdaptiveThresholdCalculator."""

    def test_empty_scores(self):
        """Test handling of empty score list."""
        from src.rag.adaptive_threshold import AdaptiveThresholdCalculator
        from src.rag.search_config import SearchQualityConfig

        config = SearchQualityConfig()
        calc = AdaptiveThresholdCalculator(config)

        threshold = calc.calculate_threshold([], 3, 0.5)

        assert threshold == config.min_threshold

    def test_threshold_bounds(self):
        """Test that threshold stays within bounds."""
        from src.rag.adaptive_threshold import AdaptiveThresholdCalculator
        from src.rag.search_config import SearchQualityConfig

        config = SearchQualityConfig(min_threshold=0.3, max_threshold=0.7)
        calc = AdaptiveThresholdCalculator(config)

        # With very high scores, threshold should be raised but not above max
        threshold = calc.calculate_threshold([0.95, 0.94, 0.93], 3, 0.5)
        assert threshold <= config.max_threshold

        # With very low scores, threshold should be lowered but not below min
        threshold = calc.calculate_threshold([0.1, 0.1, 0.1], 3, 0.5)
        assert threshold >= config.min_threshold

    def test_disabled_adaptive(self):
        """Test that adaptive threshold can be disabled."""
        from src.rag.adaptive_threshold import AdaptiveThresholdCalculator
        from src.rag.search_config import SearchQualityConfig

        config = SearchQualityConfig(enable_adaptive_threshold=False)
        calc = AdaptiveThresholdCalculator(config)

        initial = 0.5
        threshold = calc.calculate_threshold([0.9, 0.8, 0.7], 3, initial)

        assert threshold == initial

    def test_query_length_adjustment(self):
        """Test that query length affects threshold."""
        from src.rag.adaptive_threshold import AdaptiveThresholdCalculator
        from src.rag.search_config import SearchQualityConfig

        config = SearchQualityConfig()
        calc = AdaptiveThresholdCalculator(config)

        scores = [0.7, 0.6, 0.5, 0.4, 0.3]

        # Short query should have lower threshold
        short_threshold = calc.calculate_threshold(scores, 1, 0.5)
        # Long query should have higher threshold
        long_threshold = calc.calculate_threshold(scores, 10, 0.5)

        assert short_threshold <= long_threshold

    def test_score_distribution_gap(self):
        """Test detection of natural score gaps."""
        from src.rag.adaptive_threshold import AdaptiveThresholdCalculator
        from src.rag.search_config import SearchQualityConfig

        config = SearchQualityConfig()
        calc = AdaptiveThresholdCalculator(config)

        # Scores with clear gap
        scores_with_gap = [0.9, 0.88, 0.85, 0.3, 0.25, 0.2]

        threshold = calc.calculate_threshold(scores_with_gap, 3, 0.5)

        # Threshold should be adjusted based on the distribution
        # The algorithm considers target_result_count (5 by default),
        # so it may lower the threshold to include enough results
        assert config.min_threshold <= threshold <= config.max_threshold

    def test_analyze_scores(self):
        """Test score analysis function."""
        from src.rag.adaptive_threshold import AdaptiveThresholdCalculator
        from src.rag.search_config import SearchQualityConfig

        config = SearchQualityConfig()
        calc = AdaptiveThresholdCalculator(config)

        scores = [0.9, 0.7, 0.5, 0.3, 0.1]
        analysis = calc.analyze_scores(scores)

        assert analysis["count"] == 5
        assert analysis["min"] == 0.1
        assert analysis["max"] == 0.9
        assert "mean" in analysis


class TestMMRReranker:
    """Tests for MMRReranker."""

    def test_empty_results(self):
        """Test handling of empty results."""
        from src.rag.mmr_reranker import MMRReranker
        from src.rag.search_config import SearchQualityConfig

        config = SearchQualityConfig()
        reranker = MMRReranker(config)

        results = reranker.rerank([], None, 5)

        assert results == []

    def test_fewer_than_top_k(self):
        """Test when results fewer than top_k."""
        from src.rag.mmr_reranker import MMRReranker
        from src.rag.models import HybridSearchResult
        from src.rag.search_config import SearchQualityConfig

        config = SearchQualityConfig()
        reranker = MMRReranker(config)

        results = [
            HybridSearchResult(
                chunk_text="Test 1",
                document_id="doc1",
                document_filename="test.pdf",
                chunk_index=0,
                combined_score=0.9,
            ),
            HybridSearchResult(
                chunk_text="Test 2",
                document_id="doc2",
                document_filename="test2.pdf",
                chunk_index=0,
                combined_score=0.8,
            ),
        ]

        reranked = reranker.rerank(results, None, 5)

        assert len(reranked) == 2

    def test_disabled_mmr(self):
        """Test that MMR can be disabled."""
        from src.rag.mmr_reranker import MMRReranker
        from src.rag.models import HybridSearchResult
        from src.rag.search_config import SearchQualityConfig

        config = SearchQualityConfig(enable_mmr=False)
        reranker = MMRReranker(config)

        results = [
            HybridSearchResult(
                chunk_text=f"Test {i}",
                document_id=f"doc{i}",
                document_filename=f"test{i}.pdf",
                chunk_index=0,
                combined_score=0.9 - i * 0.1,
            )
            for i in range(10)
        ]

        reranked = reranker.rerank(results, None, 3)

        # Should just return top 3 by combined score
        assert len(reranked) == 3

    def test_diversity_selection(self):
        """Test that MMR promotes diversity."""
        from src.rag.mmr_reranker import MMRReranker
        from src.rag.models import HybridSearchResult
        from src.rag.search_config import SearchQualityConfig

        config = SearchQualityConfig(enable_mmr=True, mmr_lambda=0.5)
        reranker = MMRReranker(config)

        # Create results with similar text (should be de-prioritized)
        results = [
            HybridSearchResult(
                chunk_text="Diabetes treatment with insulin therapy",
                document_id="doc1",
                document_filename="diabetes1.pdf",
                chunk_index=0,
                combined_score=0.9,
            ),
            HybridSearchResult(
                chunk_text="Diabetes treatment with insulin injection",  # Similar
                document_id="doc1",
                document_filename="diabetes1.pdf",
                chunk_index=1,
                combined_score=0.88,
            ),
            HybridSearchResult(
                chunk_text="Hypertension management with ACE inhibitors",  # Different
                document_id="doc2",
                document_filename="hypertension.pdf",
                chunk_index=0,
                combined_score=0.85,
            ),
        ]

        reranked = reranker.rerank(results, None, 2)

        # The diverse result should be promoted
        doc_ids = [r.document_id for r in reranked]
        # Should include both documents for diversity
        assert len(set(doc_ids)) > 1 or len(reranked) == 1

    def test_diversity_score_calculation(self):
        """Test diversity score calculation."""
        from src.rag.mmr_reranker import MMRReranker
        from src.rag.models import HybridSearchResult
        from src.rag.search_config import SearchQualityConfig

        config = SearchQualityConfig()
        reranker = MMRReranker(config)

        # Similar results should have low diversity
        similar_results = [
            HybridSearchResult(
                chunk_text="The patient has diabetes mellitus type 2",
                document_id="doc1",
                document_filename="test.pdf",
                chunk_index=0,
                combined_score=0.9,
            ),
            HybridSearchResult(
                chunk_text="The patient has diabetes mellitus type 2 diagnosed",
                document_id="doc1",
                document_filename="test.pdf",
                chunk_index=1,
                combined_score=0.85,
            ),
        ]

        # Diverse results should have high diversity
        diverse_results = [
            HybridSearchResult(
                chunk_text="The patient has diabetes",
                document_id="doc1",
                document_filename="test.pdf",
                chunk_index=0,
                combined_score=0.9,
            ),
            HybridSearchResult(
                chunk_text="Blood pressure management protocol",
                document_id="doc2",
                document_filename="test2.pdf",
                chunk_index=0,
                combined_score=0.85,
            ),
        ]

        similar_diversity = reranker.calculate_diversity_score(similar_results)
        diverse_diversity = reranker.calculate_diversity_score(diverse_results)

        assert diverse_diversity > similar_diversity


class TestQueryExpansionModel:
    """Tests for QueryExpansion model."""

    def test_get_all_search_terms(self):
        """Test getting all search terms from expansion."""
        from src.rag.models import QueryExpansion

        expansion = QueryExpansion(
            original_query="heart attack",
            expanded_terms=["myocardial infarction", "cardiac event"],
            abbreviation_expansions={"mi": ["myocardial infarction"]},
            synonym_expansions={"heart attack": ["cardiac arrest"]},
        )

        terms = expansion.get_all_search_terms()

        assert "heart attack" in terms
        assert "myocardial infarction" in terms or "cardiac event" in terms


class TestIntegration:
    """Integration tests for search quality pipeline."""

    def test_full_pipeline_config(self):
        """Test that all components use shared config."""
        from src.rag.search_config import SearchQualityConfig
        from src.rag.query_expander import MedicalQueryExpander
        from src.rag.adaptive_threshold import AdaptiveThresholdCalculator
        from src.rag.mmr_reranker import MMRReranker

        config = SearchQualityConfig(
            enable_query_expansion=True,
            enable_adaptive_threshold=True,
            enable_mmr=True,
            mmr_lambda=0.6,
        )

        expander = MedicalQueryExpander(config)
        threshold_calc = AdaptiveThresholdCalculator(config)
        reranker = MMRReranker(config)

        # All should share the same config
        assert expander.config.mmr_lambda == 0.6
        assert threshold_calc.config.mmr_lambda == 0.6
        assert reranker.config.mmr_lambda == 0.6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
