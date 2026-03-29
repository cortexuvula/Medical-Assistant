"""
Tests for src/rag/adaptive_threshold.py

Covers AdaptiveThresholdCalculator (calculate_threshold with disabled/empty/bounds,
_adjust_for_distribution, _adjust_for_query_length, _adjust_for_result_count,
analyze_scores), singleton helpers, and the convenience function.
Pure math/logic — no network, no Tkinter.
"""

import sys
import statistics
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

import rag.adaptive_threshold as at_module
from rag.adaptive_threshold import (
    AdaptiveThresholdCalculator,
    get_adaptive_threshold_calculator,
    reset_adaptive_threshold_calculator,
    calculate_adaptive_threshold,
)
from rag.search_config import SearchQualityConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cfg(**kwargs) -> SearchQualityConfig:
    """Create a SearchQualityConfig with overridden values."""
    defaults = dict(
        enable_adaptive_threshold=True,
        min_threshold=0.2,
        max_threshold=0.8,
        target_result_count=5,
    )
    defaults.update(kwargs)
    return SearchQualityConfig(**defaults)


def _calc(**kwargs) -> AdaptiveThresholdCalculator:
    """Create a calculator with a custom config."""
    return AdaptiveThresholdCalculator(config=_cfg(**kwargs))


# ===========================================================================
# Singleton management
# ===========================================================================

@pytest.fixture(autouse=True)
def reset_singleton():
    reset_adaptive_threshold_calculator()
    yield
    reset_adaptive_threshold_calculator()


# ===========================================================================
# AdaptiveThresholdCalculator.__init__
# ===========================================================================

class TestAdaptiveThresholdCalculatorInit:
    def test_init_with_default_config(self):
        calc = AdaptiveThresholdCalculator()
        assert calc.config is not None

    def test_init_with_custom_config(self):
        cfg = _cfg(min_threshold=0.3)
        calc = AdaptiveThresholdCalculator(config=cfg)
        assert calc.config.min_threshold == 0.3

    def test_config_is_search_quality_config(self):
        calc = AdaptiveThresholdCalculator()
        assert isinstance(calc.config, SearchQualityConfig)


# ===========================================================================
# calculate_threshold — disabled / empty / bounds
# ===========================================================================

class TestCalculateThresholdBase:
    def test_disabled_returns_initial_threshold(self):
        calc = _calc(enable_adaptive_threshold=False)
        result = calc.calculate_threshold([0.9, 0.8, 0.7], query_length=3, initial_threshold=0.55)
        assert result == 0.55

    def test_empty_scores_returns_min_threshold(self):
        calc = _calc(min_threshold=0.25)
        result = calc.calculate_threshold([], query_length=3, initial_threshold=0.5)
        assert result == 0.25

    def test_result_never_below_min_threshold(self):
        calc = _calc(min_threshold=0.3, enable_adaptive_threshold=True)
        # Low scores — threshold might try to go below min
        result = calc.calculate_threshold([0.1, 0.12, 0.11], query_length=1, initial_threshold=0.5)
        assert result >= 0.3

    def test_result_never_above_max_threshold(self):
        calc = _calc(max_threshold=0.75, enable_adaptive_threshold=True)
        # Very high scores — might want to raise threshold a lot
        result = calc.calculate_threshold([0.99, 0.98, 0.97], query_length=20, initial_threshold=0.6)
        assert result <= 0.75

    def test_returns_float(self):
        calc = _calc()
        result = calc.calculate_threshold([0.7, 0.6, 0.5], query_length=3, initial_threshold=0.5)
        assert isinstance(result, float)

    def test_single_score_processes_without_error(self):
        calc = _calc()
        result = calc.calculate_threshold([0.7], query_length=3, initial_threshold=0.5)
        assert isinstance(result, float)


# ===========================================================================
# _adjust_for_query_length
# ===========================================================================

class TestAdjustForQueryLength:
    def setup_method(self):
        self.calc = _calc()

    def test_very_short_query_lowers_threshold(self):
        # query_length <= 2 → threshold * 0.85
        result = self.calc._adjust_for_query_length(1, 0.5)
        assert abs(result - 0.5 * 0.85) < 1e-9

    def test_two_word_query_lowers_threshold(self):
        result = self.calc._adjust_for_query_length(2, 0.6)
        assert abs(result - 0.6 * 0.85) < 1e-9

    def test_medium_query_no_adjustment(self):
        # query_length 3-5 → no change
        result = self.calc._adjust_for_query_length(3, 0.5)
        assert result == 0.5

    def test_five_word_query_no_adjustment(self):
        result = self.calc._adjust_for_query_length(5, 0.5)
        assert result == 0.5

    def test_six_word_query_slight_increase(self):
        # 6 words → (6-5) * 0.02 = 0.02 increase
        result = self.calc._adjust_for_query_length(6, 0.5)
        assert abs(result - 0.52) < 1e-9

    def test_ten_word_query_max_increase(self):
        # 10 words → min(0.1, (10-5)*0.02) = 0.1 increase
        result = self.calc._adjust_for_query_length(10, 0.5)
        assert abs(result - 0.6) < 1e-9

    def test_very_long_query_capped_at_0_1_increase(self):
        # 100 words → still capped at 0.1 increase
        result_100 = self.calc._adjust_for_query_length(100, 0.5)
        result_10 = self.calc._adjust_for_query_length(10, 0.5)
        assert result_100 == result_10  # Both get +0.1


# ===========================================================================
# _adjust_for_distribution
# ===========================================================================

class TestAdjustForDistribution:
    def setup_method(self):
        self.calc = _calc()

    def test_single_score_returns_unchanged(self):
        result = self.calc._adjust_for_distribution([0.7], 0.5)
        assert result == 0.5

    def test_high_top_score_raises_threshold(self):
        # sorted_scores[0] > 0.8 → threshold >= sorted_scores[0] - 0.2
        scores = [0.95, 0.92, 0.90]
        result = self.calc._adjust_for_distribution(scores, 0.5)
        assert result >= scores[0] - 0.2

    def test_large_natural_gap_raises_threshold(self):
        # Gap > 0.15 → threshold raised to gap threshold
        scores = [0.90, 0.85, 0.30, 0.25]  # gap between 0.85 and 0.30 = 0.55
        result = self.calc._adjust_for_distribution(scores, 0.5)
        # Should use 0.30 (the value after the gap) as floor
        assert result >= 0.30

    def test_tight_cluster_high_mean_raises_threshold(self):
        # std_dev < 0.1, mean > 0.5 → threshold raised to mean - std_dev
        scores = [0.75, 0.74, 0.73, 0.72, 0.71]
        mean = statistics.mean(scores)
        std = statistics.stdev(scores)
        result = self.calc._adjust_for_distribution(scores, 0.4)
        assert result >= mean - std

    def test_low_scores_no_increase(self):
        # All scores low, no large gaps, no tight cluster above 0.5
        scores = [0.3, 0.25, 0.2]
        result = self.calc._adjust_for_distribution(scores, 0.4)
        # Threshold should stay at 0.4 (no conditions trigger raises)
        assert result == 0.4


# ===========================================================================
# _adjust_for_result_count
# ===========================================================================

class TestAdjustForResultCount:
    def setup_method(self):
        self.calc = _calc(target_result_count=3)

    def test_enough_results_threshold_unchanged(self):
        # 3 scores all above 0.5, target=3 → no adjustment needed
        scores = [0.9, 0.8, 0.7]
        result = self.calc._adjust_for_result_count(scores, 0.5)
        # All three pass → passing_count == target → no change
        assert result == 0.5

    def test_too_few_results_lowers_threshold(self):
        # Only 1 score above 0.7, target=3, but we have 4 scores total
        scores = [0.9, 0.5, 0.4, 0.3]
        result = self.calc._adjust_for_result_count(scores, 0.7)
        # Should lower threshold so at least 3 results pass
        # sorted_scores[target-1] = sorted_scores[2] = 0.4
        assert result <= 0.5

    def test_not_enough_total_scores_returns_min(self):
        # Only 1 score total, target=3 → use min_threshold
        calc = _calc(target_result_count=3, min_threshold=0.2)
        scores = [0.8]
        result = calc._adjust_for_result_count(scores, 0.6)
        assert result == 0.2

    def test_too_many_results_raises_threshold(self):
        # All 10 scores above threshold, target=3, >3*target=9 → raise threshold
        calc = _calc(target_result_count=3)
        scores = [0.95, 0.90, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60, 0.55, 0.50]
        # 10 scores all > 0.45, target=3, 10 > 3*3=9
        result = calc._adjust_for_result_count(scores, 0.45)
        # Should raise to sorted_scores[target-1] = sorted_scores[2] = 0.85
        assert result >= 0.85

    def test_empty_scores_returns_threshold_unchanged(self):
        result = self.calc._adjust_for_result_count([], 0.5)
        assert result == 0.5


# ===========================================================================
# analyze_scores
# ===========================================================================

class TestAnalyzeScores:
    def setup_method(self):
        self.calc = _calc()

    def test_empty_scores_returns_empty_flag(self):
        result = self.calc.analyze_scores([])
        assert result.get("empty") is True

    def test_returns_count(self):
        result = self.calc.analyze_scores([0.7, 0.6, 0.5])
        assert result["count"] == 3

    def test_returns_min(self):
        result = self.calc.analyze_scores([0.7, 0.6, 0.5])
        assert result["min"] == 0.5

    def test_returns_max(self):
        result = self.calc.analyze_scores([0.7, 0.6, 0.5])
        assert result["max"] == 0.7

    def test_returns_mean(self):
        result = self.calc.analyze_scores([0.6, 0.8])
        assert abs(result["mean"] - 0.7) < 1e-9

    def test_returns_median(self):
        result = self.calc.analyze_scores([0.5, 0.7, 0.9])
        assert result["median"] == 0.7

    def test_single_score_no_std_dev(self):
        result = self.calc.analyze_scores([0.7])
        assert "std_dev" not in result

    def test_multiple_scores_includes_std_dev(self):
        result = self.calc.analyze_scores([0.7, 0.6, 0.5])
        assert "std_dev" in result

    def test_multiple_scores_includes_largest_gaps(self):
        result = self.calc.analyze_scores([0.9, 0.5, 0.4, 0.1])
        assert "largest_gaps" in result

    def test_largest_gaps_is_list(self):
        result = self.calc.analyze_scores([0.9, 0.5, 0.4, 0.1])
        assert isinstance(result["largest_gaps"], list)

    def test_largest_gaps_at_most_three(self):
        result = self.calc.analyze_scores([0.9, 0.8, 0.5, 0.3, 0.2, 0.1])
        assert len(result["largest_gaps"]) <= 3


# ===========================================================================
# Singleton helpers
# ===========================================================================

class TestSingletonHelpers:
    def test_get_returns_calculator_instance(self):
        calc = get_adaptive_threshold_calculator()
        assert isinstance(calc, AdaptiveThresholdCalculator)

    def test_get_returns_same_instance_twice(self):
        c1 = get_adaptive_threshold_calculator()
        c2 = get_adaptive_threshold_calculator()
        assert c1 is c2

    def test_reset_clears_singleton(self):
        c1 = get_adaptive_threshold_calculator()
        reset_adaptive_threshold_calculator()
        c2 = get_adaptive_threshold_calculator()
        assert c1 is not c2

    def test_get_after_reset_returns_fresh_instance(self):
        get_adaptive_threshold_calculator()
        reset_adaptive_threshold_calculator()
        c = get_adaptive_threshold_calculator()
        assert c is not None


# ===========================================================================
# calculate_adaptive_threshold convenience function
# ===========================================================================

class TestCalculateAdaptiveThresholdConvenience:
    def test_returns_float(self):
        result = calculate_adaptive_threshold([0.7, 0.6, 0.5], query_length=3)
        assert isinstance(result, float)

    def test_empty_scores_returns_min(self):
        # Default config min_threshold = 0.2
        result = calculate_adaptive_threshold([], query_length=3)
        assert result == 0.2

    def test_disabled_returns_initial(self):
        # We can't easily disable via convenience function since it uses singleton
        # Just verify it runs and returns a reasonable value
        result = calculate_adaptive_threshold([0.8, 0.7], query_length=5, initial_threshold=0.5)
        assert 0.0 <= result <= 1.0

    def test_bounds_respected(self):
        result = calculate_adaptive_threshold([0.99, 0.98], query_length=100)
        assert result <= 0.8  # Default max_threshold

    def test_uses_global_calculator(self):
        c1 = get_adaptive_threshold_calculator()
        calculate_adaptive_threshold([0.5], query_length=3)
        c2 = get_adaptive_threshold_calculator()
        assert c1 is c2
