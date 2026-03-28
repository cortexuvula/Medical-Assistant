"""
Comprehensive unit tests for RAG search quality modules:
- MedicalQueryExpander (src/rag/query_expander.py)
- AdaptiveThresholdCalculator (src/rag/adaptive_threshold.py)
- MMRReranker (src/rag/mmr_reranker.py)
"""

import math
import os
import sys
import unittest

# Add project paths
project_root = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "src"))

from rag.search_config import SearchQualityConfig
from rag.query_expander import (
    MEDICAL_ABBREVIATIONS,
    MEDICAL_SYNONYMS,
    REVERSE_SYNONYMS,
    TERM_TO_ABBREVIATIONS,
    MedicalQueryExpander,
)
from rag.adaptive_threshold import AdaptiveThresholdCalculator
from rag.mmr_reranker import MMRReranker
from rag.models import HybridSearchResult, QueryExpansion


# ---------------------------------------------------------------------------
# Helper: create a default config with all features enabled
# ---------------------------------------------------------------------------
def _config(**overrides):
    defaults = dict(
        enable_query_expansion=True,
        expand_abbreviations=True,
        expand_synonyms=True,
        max_expansion_terms=3,
        enable_adaptive_threshold=True,
        min_threshold=0.2,
        max_threshold=0.8,
        target_result_count=5,
        enable_mmr=True,
        mmr_lambda=0.7,
    )
    defaults.update(overrides)
    return SearchQualityConfig(**defaults)


def _make_result(text, score, doc_id="doc1", filename="test.pdf",
                 chunk_index=0, embedding=None):
    """Helper to create a HybridSearchResult."""
    return HybridSearchResult(
        chunk_text=text,
        document_id=doc_id,
        document_filename=filename,
        chunk_index=chunk_index,
        combined_score=score,
        embedding=embedding,
    )


# =========================================================================
# MedicalQueryExpander tests
# =========================================================================
class TestMedicalQueryExpanderAbbreviations(unittest.TestCase):
    """Test abbreviation expansion in MedicalQueryExpander."""

    def setUp(self):
        self.config = _config()
        self.expander = MedicalQueryExpander(self.config)

    # -- individual abbreviations -----------------------------------------

    def test_htn_expands_to_hypertension(self):
        expansion = self.expander.expand_query("HTN")
        all_terms = [t.lower() for t in expansion.get_all_search_terms()]
        self.assertIn("hypertension", all_terms)

    def test_dm_expands_to_diabetes(self):
        expansion = self.expander.expand_query("DM")
        all_terms = [t.lower() for t in expansion.get_all_search_terms()]
        self.assertIn("diabetes mellitus", all_terms)

    def test_copd_expands(self):
        expansion = self.expander.expand_query("COPD")
        all_terms = [t.lower() for t in expansion.get_all_search_terms()]
        self.assertIn("chronic obstructive pulmonary disease", all_terms)

    def test_mi_expands_to_myocardial_infarction(self):
        expansion = self.expander.expand_query("MI")
        all_terms = [t.lower() for t in expansion.get_all_search_terms()]
        self.assertIn("myocardial infarction", all_terms)

    def test_chf_expands(self):
        expansion = self.expander.expand_query("CHF")
        all_terms = [t.lower() for t in expansion.get_all_search_terms()]
        self.assertTrue(
            "congestive heart failure" in all_terms or "heart failure" in all_terms
        )

    def test_cva_expands_to_stroke(self):
        expansion = self.expander.expand_query("CVA")
        all_terms = [t.lower() for t in expansion.get_all_search_terms()]
        self.assertIn("stroke", all_terms)

    def test_gerd_expands(self):
        expansion = self.expander.expand_query("GERD")
        all_terms = [t.lower() for t in expansion.get_all_search_terms()]
        self.assertIn("gastroesophageal reflux disease", all_terms)

    def test_uti_expands(self):
        expansion = self.expander.expand_query("UTI")
        all_terms = [t.lower() for t in expansion.get_all_search_terms()]
        self.assertIn("urinary tract infection", all_terms)

    # -- abbreviation appears in abbreviation_expansions dict -------------

    def test_abbreviation_recorded_in_expansion_dict(self):
        expansion = self.expander.expand_query("HTN")
        self.assertIn("htn", expansion.abbreviation_expansions)
        self.assertTrue(len(expansion.abbreviation_expansions["htn"]) > 0)


class TestMedicalQueryExpanderBidirectional(unittest.TestCase):
    """Test bidirectional expansion (abbreviation <-> full term)."""

    def setUp(self):
        self.config = _config()
        self.expander = MedicalQueryExpander(self.config)

    def test_full_term_resolves_to_abbreviation(self):
        """'hypertension' should yield 'htn'."""
        expansion = self.expander.expand_query("hypertension")
        all_terms = [t.lower() for t in expansion.get_all_search_terms()]
        self.assertIn("htn", all_terms)

    def test_diabetes_mellitus_resolves_to_dm(self):
        expansion = self.expander.expand_query("diabetes mellitus")
        all_terms = [t.lower() for t in expansion.get_all_search_terms()]
        self.assertIn("dm", all_terms)

    def test_stroke_resolves_to_cva(self):
        expansion = self.expander.expand_query("stroke")
        all_terms = [t.lower() for t in expansion.get_all_search_terms()]
        self.assertIn("cva", all_terms)

    def test_myocardial_infarction_resolves_to_mi(self):
        expansion = self.expander.expand_query("myocardial infarction")
        all_terms = [t.lower() for t in expansion.get_all_search_terms()]
        self.assertIn("mi", all_terms)

    def test_both_directions_produce_overlapping_terms(self):
        """Expanding the abbreviation and the full term should share terms."""
        exp_abbr = self.expander.expand_query("HTN")
        exp_full = self.expander.expand_query("hypertension")
        shared = set(t.lower() for t in exp_abbr.get_all_search_terms()) & \
                 set(t.lower() for t in exp_full.get_all_search_terms())
        # At least one term in common (e.g. 'hypertension' or 'htn')
        self.assertTrue(len(shared) > 0)


class TestMedicalQueryExpanderSynonyms(unittest.TestCase):
    """Test synonym expansion."""

    def setUp(self):
        self.config = _config()
        self.expander = MedicalQueryExpander(self.config)

    def test_heart_attack_yields_mi(self):
        expansion = self.expander.expand_query("heart attack")
        all_terms = [t.lower() for t in expansion.get_all_search_terms()]
        self.assertTrue(
            "myocardial infarction" in all_terms or "mi" in all_terms
        )

    def test_headache_yields_cephalgia(self):
        expansion = self.expander.expand_query("headache")
        all_terms = [t.lower() for t in expansion.get_all_search_terms()]
        self.assertIn("cephalgia", all_terms)

    def test_chest_pain_yields_angina(self):
        expansion = self.expander.expand_query("chest pain")
        all_terms = [t.lower() for t in expansion.get_all_search_terms()]
        self.assertIn("angina", all_terms)

    def test_fever_yields_pyrexia(self):
        expansion = self.expander.expand_query("fever")
        all_terms = [t.lower() for t in expansion.get_all_search_terms()]
        self.assertIn("pyrexia", all_terms)

    def test_reverse_synonym_lookup(self):
        """A synonym should resolve back to the primary term."""
        expansion = self.expander.expand_query("dyspnea")
        all_terms = [t.lower() for t in expansion.get_all_search_terms()]
        self.assertIn("shortness of breath", all_terms)

    def test_synonym_expansions_dict_populated(self):
        expansion = self.expander.expand_query("heart attack")
        self.assertTrue(len(expansion.synonym_expansions) > 0)


class TestMedicalQueryExpanderEdgeCases(unittest.TestCase):
    """Edge-case and miscellaneous tests for MedicalQueryExpander."""

    def setUp(self):
        self.config = _config()
        self.expander = MedicalQueryExpander(self.config)

    def test_empty_string(self):
        expansion = self.expander.expand_query("")
        self.assertEqual(expansion.original_query, "")
        self.assertEqual(expansion.expanded_query, "")

    def test_no_medical_terms(self):
        """A query with no medical terms should remain essentially unchanged."""
        expansion = self.expander.expand_query("weather today sunny")
        self.assertEqual(expansion.expanded_query, "weather today sunny")
        self.assertEqual(len(expansion.expanded_terms), 0)

    def test_multiple_abbreviations_in_one_query(self):
        expansion = self.expander.expand_query("patient with HTN and DM")
        all_terms = [t.lower() for t in expansion.get_all_search_terms()]
        self.assertIn("hypertension", all_terms)
        self.assertTrue(
            "diabetes mellitus" in all_terms or "diabetes" in all_terms
        )

    def test_mixed_case_input(self):
        """Expansion should work regardless of casing."""
        expansion = self.expander.expand_query("htn")
        all_terms = [t.lower() for t in expansion.get_all_search_terms()]
        self.assertIn("hypertension", all_terms)

    def test_expansion_disabled(self):
        config = _config(enable_query_expansion=False)
        expander = MedicalQueryExpander(config)
        expansion = expander.expand_query("HTN")
        self.assertEqual(expansion.expanded_query, "HTN")
        self.assertEqual(len(expansion.expanded_terms), 0)

    def test_abbreviations_disabled_synonyms_enabled(self):
        config = _config(expand_abbreviations=False, expand_synonyms=True)
        expander = MedicalQueryExpander(config)
        expansion = expander.expand_query("HTN")
        # HTN won't appear in abbreviation_expansions
        self.assertEqual(len(expansion.abbreviation_expansions), 0)

    def test_synonyms_disabled_abbreviations_enabled(self):
        config = _config(expand_abbreviations=True, expand_synonyms=False)
        expander = MedicalQueryExpander(config)
        expansion = expander.expand_query("heart attack")
        self.assertEqual(len(expansion.synonym_expansions), 0)

    def test_max_expansion_terms_limit(self):
        config = _config(max_expansion_terms=1)
        expander = MedicalQueryExpander(config)
        expansion = expander.expand_query("COPD")
        # Each abbreviation should have at most 1 expansion
        for terms in expansion.abbreviation_expansions.values():
            self.assertLessEqual(len(terms), 1)

    def test_expanded_query_contains_original(self):
        expansion = self.expander.expand_query("HTN treatment")
        self.assertTrue(expansion.expanded_query.startswith("HTN treatment"))

    def test_expanded_terms_are_deduplicated(self):
        expansion = self.expander.expand_query("heart attack MI")
        term_list = [t.lower() for t in expansion.expanded_terms]
        self.assertEqual(len(term_list), len(set(term_list)))

    def test_get_all_search_terms_includes_original(self):
        expansion = self.expander.expand_query("test query")
        self.assertIn("test query", expansion.get_all_search_terms())


class TestQueryExpanderDataIntegrity(unittest.TestCase):
    """Verify the static dictionaries are internally consistent."""

    def test_reverse_mapping_covers_all_abbreviations(self):
        """Every abbreviation's expansion terms should appear in TERM_TO_ABBREVIATIONS."""
        for abbr, terms in MEDICAL_ABBREVIATIONS.items():
            for term in terms:
                self.assertIn(
                    term.lower(), TERM_TO_ABBREVIATIONS,
                    f"'{term}' (from abbr '{abbr}') missing from TERM_TO_ABBREVIATIONS"
                )

    def test_reverse_synonym_mapping_populated(self):
        """Every synonym value should appear in REVERSE_SYNONYMS."""
        for term, synonyms in MEDICAL_SYNONYMS.items():
            for syn in synonyms:
                self.assertIn(
                    syn.lower(), REVERSE_SYNONYMS,
                    f"'{syn}' (synonym of '{term}') missing from REVERSE_SYNONYMS"
                )


# =========================================================================
# AdaptiveThresholdCalculator tests
# =========================================================================
class TestAdaptiveThresholdEmpty(unittest.TestCase):
    """Test adaptive threshold with boundary inputs."""

    def setUp(self):
        self.config = _config()
        self.calc = AdaptiveThresholdCalculator(self.config)

    def test_empty_scores_returns_min_threshold(self):
        threshold = self.calc.calculate_threshold([], 3, 0.5)
        self.assertEqual(threshold, self.config.min_threshold)

    def test_single_score(self):
        threshold = self.calc.calculate_threshold([0.7], 3, 0.5)
        self.assertGreaterEqual(threshold, self.config.min_threshold)
        self.assertLessEqual(threshold, self.config.max_threshold)

    def test_all_identical_scores(self):
        threshold = self.calc.calculate_threshold([0.6, 0.6, 0.6, 0.6], 3, 0.5)
        self.assertGreaterEqual(threshold, self.config.min_threshold)
        self.assertLessEqual(threshold, self.config.max_threshold)


class TestAdaptiveThresholdBounds(unittest.TestCase):
    """Test that adaptive threshold always stays within configured bounds."""

    def test_extreme_high_scores_capped_at_max(self):
        config = _config(min_threshold=0.2, max_threshold=0.8)
        calc = AdaptiveThresholdCalculator(config)
        threshold = calc.calculate_threshold([0.99, 0.98, 0.97, 0.96, 0.95], 3, 0.9)
        self.assertLessEqual(threshold, 0.8)

    def test_extreme_low_scores_floored_at_min(self):
        config = _config(min_threshold=0.2, max_threshold=0.8)
        calc = AdaptiveThresholdCalculator(config)
        threshold = calc.calculate_threshold([0.05, 0.04, 0.03], 3, 0.1)
        self.assertGreaterEqual(threshold, 0.2)

    def test_initial_threshold_below_min_is_clamped(self):
        config = _config(min_threshold=0.3, max_threshold=0.8)
        calc = AdaptiveThresholdCalculator(config)
        threshold = calc.calculate_threshold([0.5, 0.4, 0.3], 3, 0.1)
        self.assertGreaterEqual(threshold, 0.3)

    def test_initial_threshold_above_max_is_clamped(self):
        config = _config(min_threshold=0.2, max_threshold=0.7)
        calc = AdaptiveThresholdCalculator(config)
        threshold = calc.calculate_threshold([0.5, 0.4, 0.3], 3, 0.95)
        self.assertLessEqual(threshold, 0.7)


class TestAdaptiveThresholdScoreGap(unittest.TestCase):
    """Test detection of natural score gaps."""

    def setUp(self):
        self.config = _config(target_result_count=3)
        self.calc = AdaptiveThresholdCalculator(self.config)

    def test_clear_gap_raises_threshold(self):
        """Scores with an obvious gap should result in a higher threshold."""
        scores_with_gap = [0.9, 0.88, 0.85, 0.4, 0.35, 0.3]
        threshold = self.calc.calculate_threshold(scores_with_gap, 3, 0.3)
        # The gap between 0.85 and 0.4 is 0.45 which is > 0.15,
        # so gap_threshold should be ~0.4
        self.assertGreater(threshold, 0.3)

    def test_no_significant_gap(self):
        """Evenly distributed scores should not trigger gap detection."""
        even_scores = [0.8, 0.75, 0.70, 0.65, 0.60]
        threshold = self.calc.calculate_threshold(even_scores, 3, 0.5)
        # No gap > 0.15, so gap detection won't raise the threshold
        self.assertGreaterEqual(threshold, self.config.min_threshold)
        self.assertLessEqual(threshold, self.config.max_threshold)


class TestAdaptiveThresholdQueryLength(unittest.TestCase):
    """Test that query length adjusts the threshold."""

    def setUp(self):
        self.config = _config()
        self.calc = AdaptiveThresholdCalculator(self.config)
        self.scores = [0.7, 0.6, 0.5, 0.4, 0.3]

    def test_short_query_lowers_threshold(self):
        """1-2 word queries multiply threshold by 0.85, reducing it."""
        short = self.calc.calculate_threshold(self.scores, 1, 0.5)
        medium = self.calc.calculate_threshold(self.scores, 4, 0.5)
        self.assertLessEqual(short, medium)

    def test_long_query_raises_threshold(self):
        """6+ word queries add up to 0.1 to the threshold."""
        medium = self.calc.calculate_threshold(self.scores, 4, 0.5)
        long_ = self.calc.calculate_threshold(self.scores, 10, 0.5)
        self.assertGreaterEqual(long_, medium)

    def test_very_long_query_adjustment_capped(self):
        """Adjustment for long queries is capped at +0.1."""
        t10 = self.calc.calculate_threshold(self.scores, 10, 0.5)
        t50 = self.calc.calculate_threshold(self.scores, 50, 0.5)
        # Both should get the max +0.1 adjustment, so they should be equal
        self.assertAlmostEqual(t10, t50, places=5)


class TestAdaptiveThresholdResultCount(unittest.TestCase):
    """Test threshold adjustment to meet target_result_count."""

    def test_too_few_results_lowers_threshold(self):
        """When current threshold excludes too many results, it should lower."""
        config = _config(target_result_count=5)
        calc = AdaptiveThresholdCalculator(config)
        # All scores below 0.5 but we start at 0.5
        scores = [0.45, 0.40, 0.35, 0.30, 0.25]
        threshold = calc.calculate_threshold(scores, 3, 0.5)
        # Should lower to include target_result_count results
        self.assertLess(threshold, 0.5)

    def test_too_many_results_raises_threshold(self):
        """When far too many results pass the threshold, it should raise."""
        config = _config(target_result_count=2)
        calc = AdaptiveThresholdCalculator(config)
        # 20 scores all above initial threshold; >3x target (6) pass
        scores = [0.95 - i * 0.01 for i in range(20)]
        threshold = calc.calculate_threshold(scores, 3, 0.3)
        self.assertGreater(threshold, 0.3)


class TestAdaptiveThresholdDisabled(unittest.TestCase):
    """Test that disabling adaptive threshold returns initial value."""

    def test_returns_initial_when_disabled(self):
        config = _config(enable_adaptive_threshold=False)
        calc = AdaptiveThresholdCalculator(config)
        self.assertEqual(
            calc.calculate_threshold([0.9, 0.8, 0.7], 3, 0.42),
            0.42,
        )


class TestAdaptiveThresholdHighTopScore(unittest.TestCase):
    """Test behavior when the top score is very high."""

    def test_high_top_score_raises_threshold(self):
        """When the top score > 0.8, _adjust_for_distribution raises the
        threshold to at least top_score - 0.2.  However, if there are fewer
        than target_result_count results above that threshold, the later
        _adjust_for_result_count step may lower it again.  We use enough
        high scores here so the result-count step does not override."""
        config = _config(target_result_count=3)
        calc = AdaptiveThresholdCalculator(config)
        # 5 scores well above 0.75; target_result_count=3 is satisfied
        scores = [0.95, 0.92, 0.90, 0.88, 0.85]
        threshold = calc.calculate_threshold(scores, 3, 0.3)
        # Distribution adjustment: threshold >= 0.95 - 0.2 = 0.75
        self.assertGreaterEqual(threshold, 0.7)


class TestAdaptiveThresholdAnalyzeScores(unittest.TestCase):
    """Test the analyze_scores debugging helper."""

    def setUp(self):
        self.calc = AdaptiveThresholdCalculator(_config())

    def test_empty_returns_empty_flag(self):
        result = self.calc.analyze_scores([])
        self.assertTrue(result["empty"])

    def test_single_score(self):
        result = self.calc.analyze_scores([0.8])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["min"], 0.8)
        self.assertEqual(result["max"], 0.8)

    def test_multiple_scores_statistics(self):
        result = self.calc.analyze_scores([0.9, 0.7, 0.5, 0.3, 0.1])
        self.assertEqual(result["count"], 5)
        self.assertAlmostEqual(result["min"], 0.1)
        self.assertAlmostEqual(result["max"], 0.9)
        self.assertAlmostEqual(result["mean"], 0.5)
        self.assertIn("std_dev", result)
        self.assertIn("largest_gaps", result)
        self.assertTrue(len(result["largest_gaps"]) <= 3)


# =========================================================================
# MMRReranker tests
# =========================================================================
class TestMMRRerankerEmpty(unittest.TestCase):
    """Test MMR reranker with empty or trivial input."""

    def setUp(self):
        self.config = _config()
        self.reranker = MMRReranker(self.config)

    def test_empty_results_returns_empty(self):
        self.assertEqual(self.reranker.rerank([], None, 5), [])

    def test_single_result(self):
        results = [_make_result("only item", 0.9)]
        reranked = self.reranker.rerank(results, None, 5)
        self.assertEqual(len(reranked), 1)
        self.assertAlmostEqual(reranked[0].mmr_score, 0.9)


class TestMMRRerankerFewerThanTopK(unittest.TestCase):
    """When results < top_k, all results returned with mmr_score set."""

    def test_returns_all_with_mmr_score(self):
        config = _config()
        reranker = MMRReranker(config)
        results = [
            _make_result("item A", 0.9, doc_id="d1"),
            _make_result("item B", 0.7, doc_id="d2"),
        ]
        reranked = reranker.rerank(results, None, 5)
        self.assertEqual(len(reranked), 2)
        for r in reranked:
            self.assertAlmostEqual(r.mmr_score, r.combined_score)


class TestMMRRerankerDisabled(unittest.TestCase):
    """Test that disabling MMR returns top_k by combined_score order."""

    def test_disabled_returns_top_k_slice(self):
        config = _config(enable_mmr=False)
        reranker = MMRReranker(config)
        results = [_make_result(f"item {i}", 0.9 - i * 0.1) for i in range(8)]
        reranked = reranker.rerank(results, None, 3)
        self.assertEqual(len(reranked), 3)
        # Should be first 3 from original order
        self.assertAlmostEqual(reranked[0].combined_score, 0.9)
        self.assertAlmostEqual(reranked[1].combined_score, 0.8)
        self.assertAlmostEqual(reranked[2].combined_score, 0.7)


class TestMMRRerankerEmbeddingBased(unittest.TestCase):
    """Test embedding-based MMR reranking."""

    @staticmethod
    def _unit_vec(angle_deg, dim=8):
        """Create a unit vector pointing in the given angle (uses first 2 dims)."""
        rad = math.radians(angle_deg)
        vec = [0.0] * dim
        vec[0] = math.cos(rad)
        vec[1] = math.sin(rad)
        return vec

    def test_diverse_embeddings_preferred(self):
        """With lambda < 1, diverse documents should be preferred over
        similar high-scoring ones."""
        config = _config(mmr_lambda=0.5)
        reranker = MMRReranker(config)

        # Two similar embeddings (angle 0 and 5) and one orthogonal (angle 90)
        results = [
            _make_result("doc A similar", 0.95, "d1", embedding=self._unit_vec(0)),
            _make_result("doc B similar", 0.90, "d2", embedding=self._unit_vec(5)),
            _make_result("doc C diverse", 0.80, "d3", embedding=self._unit_vec(90)),
        ]

        reranked = reranker.rerank(results, None, 2)
        ids = [r.document_id for r in reranked]

        # First pick should be highest score
        self.assertEqual(ids[0], "d1")
        # Second pick should be the diverse one (d3), not the similar one (d2)
        self.assertEqual(ids[1], "d3")

    def test_lambda_1_equals_pure_relevance(self):
        """With lambda=1.0, the diversity penalty vanishes so results are
        ordered purely by combined_score."""
        config = _config(mmr_lambda=1.0)
        reranker = MMRReranker(config)

        results = [
            _make_result("A", 0.95, "d1", embedding=self._unit_vec(0)),
            _make_result("B", 0.90, "d2", embedding=self._unit_vec(1)),
            _make_result("C", 0.80, "d3", embedding=self._unit_vec(90)),
        ]

        reranked = reranker.rerank(results, None, 3)
        scores = [r.combined_score for r in reranked]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_lambda_0_maximises_diversity(self):
        """With lambda=0.0, relevance is ignored so the most different
        document should be picked second."""
        config = _config(mmr_lambda=0.0)
        reranker = MMRReranker(config)

        results = [
            _make_result("A", 0.95, "d1", embedding=self._unit_vec(0)),
            _make_result("B", 0.90, "d2", embedding=self._unit_vec(1)),
            _make_result("C", 0.10, "d3", embedding=self._unit_vec(180)),
        ]

        reranked = reranker.rerank(results, None, 2)
        # After d1 is selected, d3 (opposite direction) has the lowest
        # max_sim_to_selected, so the penalty -1 * max_sim is least negative
        self.assertEqual(reranked[1].document_id, "d3")

    def test_mmr_score_set_on_selected(self):
        config = _config(mmr_lambda=0.7)
        reranker = MMRReranker(config)

        results = [
            _make_result("A", 0.9, "d1", embedding=[1, 0]),
            _make_result("B", 0.8, "d2", embedding=[0, 1]),
            _make_result("C", 0.7, "d3", embedding=[1, 1]),
        ]

        reranked = reranker.rerank(results, None, 2)
        for r in reranked:
            self.assertIsNotNone(r.mmr_score)


class TestMMRRerankerTextBased(unittest.TestCase):
    """Test text-based (Jaccard) fallback when embeddings are absent."""

    def setUp(self):
        self.config = _config(mmr_lambda=0.5)
        self.reranker = MMRReranker(self.config)

    def test_no_embeddings_uses_text_fallback(self):
        """If embeddings are None, reranker should fall back to Jaccard."""
        results = [
            _make_result("diabetes insulin therapy glucose", 0.9, "d1"),
            _make_result("diabetes insulin injection dosing", 0.85, "d2"),
            _make_result("hypertension ACE inhibitor blood pressure", 0.80, "d3"),
        ]
        reranked = self.reranker.rerank(results, None, 2)
        self.assertEqual(len(reranked), 2)
        # The diverse doc (d3) should be promoted over the similar doc (d2)
        ids = [r.document_id for r in reranked]
        self.assertIn("d3", ids)

    def test_mixed_embeddings_uses_text_fallback(self):
        """If some results lack embeddings, should fall back to text."""
        results = [
            _make_result("alpha beta", 0.9, "d1", embedding=[1, 0]),
            _make_result("alpha gamma", 0.8, "d2"),  # no embedding
            _make_result("delta epsilon", 0.7, "d3"),  # no embedding
        ]
        # has_embeddings = all(r.embedding is not None ...) -> False
        reranked = self.reranker.rerank(results, None, 2)
        self.assertEqual(len(reranked), 2)

    def test_identical_texts_penalised(self):
        """Identical texts should have high Jaccard similarity and be penalised."""
        results = [
            _make_result("the same text repeated", 0.9, "d1"),
            _make_result("the same text repeated", 0.85, "d2"),
            _make_result("completely different content", 0.80, "d3"),
        ]
        reranked = self.reranker.rerank(results, None, 2)
        ids = [r.document_id for r in reranked]
        # After d1 is picked, d2 is identical so d3 should be promoted
        self.assertEqual(ids[1], "d3")


class TestMMRRerankerHelpers(unittest.TestCase):
    """Test internal helper methods of MMRReranker."""

    def setUp(self):
        self.reranker = MMRReranker(_config())

    # -- cosine similarity ------------------------------------------------

    def test_cosine_identical_vectors(self):
        vec = [1.0, 2.0, 3.0]
        self.assertAlmostEqual(self.reranker._cosine_similarity(vec, vec), 1.0, places=5)

    def test_cosine_orthogonal_vectors(self):
        self.assertAlmostEqual(
            self.reranker._cosine_similarity([1, 0], [0, 1]),
            0.0,
            places=5,
        )

    def test_cosine_opposite_vectors(self):
        self.assertAlmostEqual(
            self.reranker._cosine_similarity([1, 0], [-1, 0]),
            -1.0,
            places=5,
        )

    def test_cosine_empty_vector(self):
        self.assertAlmostEqual(self.reranker._cosine_similarity([], [1, 0]), 0.0)

    def test_cosine_zero_vector(self):
        self.assertAlmostEqual(self.reranker._cosine_similarity([0, 0], [1, 1]), 0.0)

    def test_cosine_different_lengths(self):
        self.assertAlmostEqual(
            self.reranker._cosine_similarity([1, 0], [1, 0, 0]),
            0.0,
        )

    # -- jaccard similarity -----------------------------------------------

    def test_jaccard_identical_sets(self):
        s = {"a", "b", "c"}
        self.assertAlmostEqual(self.reranker._jaccard_similarity(s, s), 1.0)

    def test_jaccard_disjoint_sets(self):
        self.assertAlmostEqual(
            self.reranker._jaccard_similarity({"a"}, {"b"}),
            0.0,
        )

    def test_jaccard_partial_overlap(self):
        self.assertAlmostEqual(
            self.reranker._jaccard_similarity({"a", "b"}, {"b", "c"}),
            1.0 / 3.0,
            places=5,
        )

    def test_jaccard_empty_set(self):
        self.assertAlmostEqual(self.reranker._jaccard_similarity(set(), {"a"}), 0.0)

    # -- tokenize ---------------------------------------------------------

    def test_tokenize_lowercases(self):
        tokens = self.reranker._tokenize("Hello WORLD")
        self.assertIn("hello", tokens)
        self.assertIn("world", tokens)

    def test_tokenize_returns_set(self):
        tokens = self.reranker._tokenize("word word word")
        self.assertIsInstance(tokens, set)
        self.assertEqual(len(tokens), 1)


class TestMMRDiversityScore(unittest.TestCase):
    """Test calculate_diversity_score method."""

    def setUp(self):
        self.reranker = MMRReranker(_config())

    def test_single_result_is_max_diversity(self):
        results = [_make_result("anything", 0.9)]
        self.assertAlmostEqual(self.reranker.calculate_diversity_score(results), 1.0)

    def test_empty_results_is_max_diversity(self):
        self.assertAlmostEqual(self.reranker.calculate_diversity_score([]), 1.0)

    def test_identical_texts_low_diversity(self):
        results = [
            _make_result("same text here", 0.9, "d1"),
            _make_result("same text here", 0.8, "d2"),
        ]
        score = self.reranker.calculate_diversity_score(results)
        self.assertLess(score, 0.3)

    def test_different_texts_high_diversity(self):
        results = [
            _make_result("alpha beta gamma", 0.9, "d1"),
            _make_result("delta epsilon zeta", 0.8, "d2"),
        ]
        score = self.reranker.calculate_diversity_score(results)
        self.assertGreater(score, 0.8)

    def test_diversity_with_embeddings(self):
        """When embeddings present, diversity should use cosine similarity."""
        results = [
            _make_result("x", 0.9, "d1", embedding=[1, 0]),
            _make_result("y", 0.8, "d2", embedding=[0, 1]),
        ]
        score = self.reranker.calculate_diversity_score(results)
        # Orthogonal embeddings -> cosine sim = 0 -> diversity = 1
        self.assertAlmostEqual(score, 1.0, places=5)

    def test_diverse_greater_than_similar(self):
        """Diverse result set should have higher diversity score."""
        similar = [
            _make_result("diabetes treatment insulin", 0.9, "d1"),
            _make_result("diabetes treatment insulin dose", 0.8, "d2"),
        ]
        diverse = [
            _make_result("diabetes treatment insulin", 0.9, "d1"),
            _make_result("hypertension management guidelines", 0.8, "d2"),
        ]
        self.assertGreater(
            self.reranker.calculate_diversity_score(diverse),
            self.reranker.calculate_diversity_score(similar),
        )


# =========================================================================
# Cross-module integration
# =========================================================================
class TestCrossModuleIntegration(unittest.TestCase):
    """Light integration tests combining the three modules."""

    def test_expanded_query_fed_to_threshold_calculator(self):
        """Ensure query expansion output can be used to drive threshold calc."""
        config = _config()
        expander = MedicalQueryExpander(config)
        calc = AdaptiveThresholdCalculator(config)

        expansion = expander.expand_query("patient with HTN and DM")
        query_words = expansion.expanded_query.split()

        scores = [0.85, 0.7, 0.55, 0.4, 0.3]
        threshold = calc.calculate_threshold(scores, len(query_words), 0.5)

        self.assertGreaterEqual(threshold, config.min_threshold)
        self.assertLessEqual(threshold, config.max_threshold)

    def test_reranker_on_results_after_threshold_filter(self):
        """Simulate filtering results by threshold, then reranking."""
        config = _config(mmr_lambda=0.5)
        calc = AdaptiveThresholdCalculator(config)
        reranker = MMRReranker(config)

        scores = [0.9, 0.85, 0.75, 0.4, 0.35]
        threshold = calc.calculate_threshold(scores, 3, 0.5)

        results = [
            _make_result(f"doc {i}", s, f"d{i}")
            for i, s in enumerate(scores) if s >= threshold
        ]

        reranked = reranker.rerank(results, None, 3)
        self.assertLessEqual(len(reranked), 3)
        self.assertTrue(all(r.combined_score >= threshold for r in reranked))


if __name__ == "__main__":
    unittest.main()
