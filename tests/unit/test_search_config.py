"""
Tests for src/rag/search_config.py

Covers SearchQualityConfig defaults, __post_init__ validation,
weight normalization, from_dict(), to_dict(), and singleton helpers
(get_search_quality_config, reset_search_quality_config).
Pure dataclass/dict logic — no network, no Tkinter, no file I/O.
"""

import sys
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

import rag.search_config as sc_module
from rag.search_config import (
    SearchQualityConfig,
    get_search_quality_config,
    reset_search_quality_config,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_search_quality_config()
    yield
    reset_search_quality_config()


# ===========================================================================
# Default values
# ===========================================================================

class TestDefaults:
    def setup_method(self):
        self.cfg = SearchQualityConfig()

    def test_enable_adaptive_threshold_true(self):
        assert self.cfg.enable_adaptive_threshold is True

    def test_min_threshold_0_2(self):
        assert self.cfg.min_threshold == pytest.approx(0.2)

    def test_max_threshold_0_8(self):
        assert self.cfg.max_threshold == pytest.approx(0.8)

    def test_target_result_count_5(self):
        assert self.cfg.target_result_count == 5

    def test_enable_query_expansion_true(self):
        assert self.cfg.enable_query_expansion is True

    def test_expand_abbreviations_true(self):
        assert self.cfg.expand_abbreviations is True

    def test_expand_synonyms_true(self):
        assert self.cfg.expand_synonyms is True

    def test_max_expansion_terms_3(self):
        assert self.cfg.max_expansion_terms == 3

    def test_enable_bm25_true(self):
        assert self.cfg.enable_bm25 is True

    def test_vector_weight_0_5(self):
        assert self.cfg.vector_weight == pytest.approx(0.5)

    def test_bm25_weight_0_3(self):
        assert self.cfg.bm25_weight == pytest.approx(0.3)

    def test_graph_weight_0_2(self):
        assert self.cfg.graph_weight == pytest.approx(0.2)

    def test_enable_mmr_true(self):
        assert self.cfg.enable_mmr is True

    def test_mmr_lambda_0_7(self):
        assert self.cfg.mmr_lambda == pytest.approx(0.7)

    def test_weights_sum_to_1(self):
        total = self.cfg.vector_weight + self.cfg.bm25_weight + self.cfg.graph_weight
        assert total == pytest.approx(1.0)


# ===========================================================================
# __post_init__ validation
# ===========================================================================

class TestValidation:
    def test_min_threshold_out_of_range_raises(self):
        with pytest.raises(ValueError, match="min_threshold"):
            SearchQualityConfig(min_threshold=-0.1)

    def test_min_threshold_above_1_raises(self):
        with pytest.raises(ValueError, match="min_threshold"):
            SearchQualityConfig(min_threshold=1.1)

    def test_max_threshold_out_of_range_raises(self):
        with pytest.raises(ValueError, match="max_threshold"):
            SearchQualityConfig(max_threshold=1.5)

    def test_min_gt_max_raises(self):
        with pytest.raises(ValueError, match="min_threshold"):
            SearchQualityConfig(min_threshold=0.8, max_threshold=0.2)

    def test_mmr_lambda_out_of_range_raises(self):
        with pytest.raises(ValueError, match="mmr_lambda"):
            SearchQualityConfig(mmr_lambda=1.5)

    def test_mmr_lambda_negative_raises(self):
        with pytest.raises(ValueError, match="mmr_lambda"):
            SearchQualityConfig(mmr_lambda=-0.1)

    def test_all_zero_weights_raises(self):
        with pytest.raises(ValueError, match="weight"):
            SearchQualityConfig(vector_weight=0.0, bm25_weight=0.0, graph_weight=0.0)

    def test_valid_boundary_thresholds(self):
        # 0.0 and 1.0 are valid boundary values
        cfg = SearchQualityConfig(min_threshold=0.0, max_threshold=1.0)
        assert cfg.min_threshold == pytest.approx(0.0)
        assert cfg.max_threshold == pytest.approx(1.0)

    def test_equal_min_max_threshold_valid(self):
        cfg = SearchQualityConfig(min_threshold=0.5, max_threshold=0.5)
        assert cfg.min_threshold == pytest.approx(0.5)


# ===========================================================================
# Weight normalization
# ===========================================================================

class TestWeightNormalization:
    def test_unequal_weights_normalized(self):
        # 1.0 + 1.0 + 1.0 = 3.0; each should normalize to 1/3
        cfg = SearchQualityConfig(vector_weight=1.0, bm25_weight=1.0, graph_weight=1.0)
        assert cfg.vector_weight == pytest.approx(1/3, rel=1e-6)
        assert cfg.bm25_weight == pytest.approx(1/3, rel=1e-6)
        assert cfg.graph_weight == pytest.approx(1/3, rel=1e-6)

    def test_normalized_weights_sum_to_1(self):
        cfg = SearchQualityConfig(vector_weight=2.0, bm25_weight=1.0, graph_weight=1.0)
        total = cfg.vector_weight + cfg.bm25_weight + cfg.graph_weight
        assert total == pytest.approx(1.0)

    def test_already_summing_to_1_unchanged(self):
        cfg = SearchQualityConfig(vector_weight=0.5, bm25_weight=0.3, graph_weight=0.2)
        # They already sum to 1.0 within tolerance
        total = cfg.vector_weight + cfg.bm25_weight + cfg.graph_weight
        assert total == pytest.approx(1.0)

    def test_single_nonzero_weight_normalizes_to_1(self):
        cfg = SearchQualityConfig(vector_weight=5.0, bm25_weight=0.0, graph_weight=0.0)
        assert cfg.vector_weight == pytest.approx(1.0)
        assert cfg.bm25_weight == pytest.approx(0.0)
        assert cfg.graph_weight == pytest.approx(0.0)


# ===========================================================================
# from_dict()
# ===========================================================================

class TestFromDict:
    def test_empty_dict_uses_defaults(self):
        cfg = SearchQualityConfig.from_dict({})
        assert cfg.enable_bm25 is True

    def test_valid_keys_applied(self):
        cfg = SearchQualityConfig.from_dict({"min_threshold": 0.3, "max_threshold": 0.9})
        assert cfg.min_threshold == pytest.approx(0.3)
        assert cfg.max_threshold == pytest.approx(0.9)

    def test_unknown_keys_ignored(self):
        # Should not raise
        cfg = SearchQualityConfig.from_dict({"unknown_key": 999, "min_threshold": 0.3})
        assert cfg.min_threshold == pytest.approx(0.3)

    def test_enable_bm25_false(self):
        cfg = SearchQualityConfig.from_dict({"enable_bm25": False})
        assert cfg.enable_bm25 is False

    def test_enable_mmr_false(self):
        cfg = SearchQualityConfig.from_dict({"enable_mmr": False})
        assert cfg.enable_mmr is False

    def test_returns_search_quality_config(self):
        assert isinstance(SearchQualityConfig.from_dict({}), SearchQualityConfig)

    def test_all_valid_keys_applied(self):
        d = {
            "enable_adaptive_threshold": False,
            "min_threshold": 0.1,
            "max_threshold": 0.9,
            "target_result_count": 10,
            "enable_query_expansion": False,
            "expand_abbreviations": False,
            "expand_synonyms": False,
            "max_expansion_terms": 5,
            "enable_bm25": False,
            "vector_weight": 0.6,
            "bm25_weight": 0.3,
            "graph_weight": 0.1,
            "enable_mmr": False,
            "mmr_lambda": 0.5,
        }
        cfg = SearchQualityConfig.from_dict(d)
        assert cfg.enable_adaptive_threshold is False
        assert cfg.target_result_count == 10
        assert cfg.mmr_lambda == pytest.approx(0.5)


# ===========================================================================
# to_dict()
# ===========================================================================

class TestToDict:
    def test_returns_dict(self):
        assert isinstance(SearchQualityConfig().to_dict(), dict)

    def test_all_keys_present(self):
        d = SearchQualityConfig().to_dict()
        expected_keys = {
            "enable_adaptive_threshold", "min_threshold", "max_threshold",
            "target_result_count", "enable_query_expansion", "expand_abbreviations",
            "expand_synonyms", "max_expansion_terms", "enable_bm25",
            "vector_weight", "bm25_weight", "graph_weight", "enable_mmr", "mmr_lambda",
        }
        assert set(d.keys()) == expected_keys

    def test_roundtrip(self):
        original = SearchQualityConfig()
        d = original.to_dict()
        restored = SearchQualityConfig.from_dict(d)
        assert restored.min_threshold == pytest.approx(original.min_threshold)
        assert restored.mmr_lambda == pytest.approx(original.mmr_lambda)
        assert restored.enable_bm25 == original.enable_bm25

    def test_modified_values_in_dict(self):
        cfg = SearchQualityConfig(min_threshold=0.3, enable_bm25=False)
        d = cfg.to_dict()
        assert d["min_threshold"] == pytest.approx(0.3)
        assert d["enable_bm25"] is False


# ===========================================================================
# Singleton helpers
# ===========================================================================

class TestSingletonHelpers:
    def test_get_search_quality_config_returns_instance(self):
        assert isinstance(get_search_quality_config(), SearchQualityConfig)

    def test_get_search_quality_config_same_instance(self):
        a = get_search_quality_config()
        b = get_search_quality_config()
        assert a is b

    def test_reset_clears_singleton(self):
        a = get_search_quality_config()
        reset_search_quality_config()
        b = get_search_quality_config()
        assert a is not b
