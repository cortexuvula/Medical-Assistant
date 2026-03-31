"""
Tests for src/rag/medical_code_lookup.py

Covers ICD10_CODES and RXNORM_CODES static dictionaries (structure integrity),
lookup_icd10, lookup_rxnorm, and enrich_entity_codes — all pure dict-lookup logic.
Also covers SearchQualityConfig defaults and the singleton helper in search_config.py.
No Tkinter, no network, no file I/O.
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

from rag.medical_code_lookup import (
    ICD10_CODES,
    RXNORM_CODES,
    lookup_icd10,
    lookup_rxnorm,
    enrich_entity_codes,
)
import rag.search_config as sc_module
from rag.search_config import (
    SearchQualityConfig,
    get_search_quality_config,
    reset_search_quality_config,
)


# ===========================================================================
# ICD10_CODES static data
# ===========================================================================

class TestIcd10CodesData:
    def test_is_dict(self):
        assert isinstance(ICD10_CODES, dict)

    def test_non_empty(self):
        assert len(ICD10_CODES) >= 50

    def test_all_keys_are_lowercase(self):
        for key in ICD10_CODES:
            assert key == key.lower(), f"Key not lowercase: {key!r}"

    def test_all_keys_are_strings(self):
        for key in ICD10_CODES:
            assert isinstance(key, str)

    def test_all_values_are_strings(self):
        for key, val in ICD10_CODES.items():
            assert isinstance(val, str), f"Non-string value for {key}"

    def test_all_values_non_empty(self):
        for key, val in ICD10_CODES.items():
            assert val.strip(), f"Empty value for {key}"

    def test_contains_hypertension(self):
        assert "hypertension" in ICD10_CODES

    def test_contains_diabetes(self):
        assert "diabetes" in ICD10_CODES

    def test_contains_copd(self):
        assert "copd" in ICD10_CODES

    def test_hypertension_code(self):
        assert ICD10_CODES["hypertension"] == "I10"

    def test_diabetes_mellitus_code(self):
        assert ICD10_CODES["diabetes mellitus"] == "E11.9"

    def test_abbreviations_present(self):
        # Common abbreviations should be included
        assert "htn" in ICD10_CODES or "afib" in ICD10_CODES


# ===========================================================================
# RXNORM_CODES static data
# ===========================================================================

class TestRxNormCodesData:
    def test_is_dict(self):
        assert isinstance(RXNORM_CODES, dict)

    def test_non_empty(self):
        assert len(RXNORM_CODES) >= 30

    def test_all_keys_are_lowercase(self):
        for key in RXNORM_CODES:
            assert key == key.lower(), f"Key not lowercase: {key!r}"

    def test_all_keys_are_strings(self):
        for key in RXNORM_CODES:
            assert isinstance(key, str)

    def test_all_values_are_strings(self):
        for key, val in RXNORM_CODES.items():
            assert isinstance(val, str), f"Non-string value for {key}"

    def test_all_values_non_empty(self):
        for key, val in RXNORM_CODES.items():
            assert val.strip(), f"Empty value for {key}"

    def test_contains_aspirin(self):
        assert "aspirin" in RXNORM_CODES

    def test_contains_metformin(self):
        assert "metformin" in RXNORM_CODES

    def test_aspirin_rxnorm_code(self):
        assert "RxNorm" in RXNORM_CODES["aspirin"]

    def test_values_start_with_rxnorm_prefix(self):
        for key, val in RXNORM_CODES.items():
            assert val.startswith("RxNorm:"), f"Unexpected format for {key}: {val}"


# ===========================================================================
# lookup_icd10
# ===========================================================================

class TestLookupIcd10:
    def test_empty_string_returns_none(self):
        assert lookup_icd10("") is None

    def test_none_like_empty_returns_none(self):
        # The function checks `if not condition` so empty string returns None
        assert lookup_icd10("") is None

    def test_known_condition_returns_code(self):
        assert lookup_icd10("hypertension") == "I10"

    def test_case_insensitive_lookup(self):
        assert lookup_icd10("Hypertension") == "I10"
        assert lookup_icd10("HYPERTENSION") == "I10"

    def test_whitespace_stripped(self):
        assert lookup_icd10("  hypertension  ") == "I10"

    def test_unknown_condition_returns_none(self):
        assert lookup_icd10("xyzzy_disease_not_real") is None

    def test_abbreviation_lookup(self):
        # "htn" should map to I10
        assert lookup_icd10("htn") == "I10"

    def test_diabetes_abbreviation(self):
        assert lookup_icd10("dm") == "E11.9"

    def test_copd_abbreviation(self):
        result = lookup_icd10("copd")
        assert result is not None
        assert result.startswith("J")

    def test_returns_string_for_known(self):
        result = lookup_icd10("diabetes")
        assert isinstance(result, str)

    def test_mixed_case_abbreviation(self):
        result = lookup_icd10("COPD")
        assert result is not None


# ===========================================================================
# lookup_rxnorm
# ===========================================================================

class TestLookupRxnorm:
    def test_empty_string_returns_none(self):
        assert lookup_rxnorm("") is None

    def test_known_medication_returns_code(self):
        result = lookup_rxnorm("aspirin")
        assert result is not None
        assert "RxNorm" in result

    def test_case_insensitive(self):
        assert lookup_rxnorm("Aspirin") == lookup_rxnorm("aspirin")
        assert lookup_rxnorm("ASPIRIN") == lookup_rxnorm("aspirin")

    def test_whitespace_stripped(self):
        assert lookup_rxnorm("  aspirin  ") == lookup_rxnorm("aspirin")

    def test_unknown_medication_returns_none(self):
        assert lookup_rxnorm("unobtanium_pill") is None

    def test_metformin_lookup(self):
        result = lookup_rxnorm("metformin")
        assert result is not None

    def test_returns_string_for_known(self):
        assert isinstance(lookup_rxnorm("aspirin"), str)


# ===========================================================================
# enrich_entity_codes
# ===========================================================================

class TestEnrichEntityCodes:
    def test_condition_type_returns_icd10(self):
        result = enrich_entity_codes("hypertension", "condition")
        assert "icd10" in result
        assert result["icd10"] == "I10"

    def test_condition_type_no_rxnorm(self):
        result = enrich_entity_codes("hypertension", "condition")
        assert "rxnorm" not in result

    def test_diagnosis_type_returns_icd10(self):
        result = enrich_entity_codes("diabetes", "diagnosis")
        assert "icd10" in result

    def test_symptom_type_returns_icd10(self):
        result = enrich_entity_codes("hypertension", "symptom")
        assert "icd10" in result

    def test_medication_type_returns_rxnorm(self):
        result = enrich_entity_codes("aspirin", "medication")
        assert "rxnorm" in result

    def test_medication_type_no_icd10(self):
        result = enrich_entity_codes("aspirin", "medication")
        assert "icd10" not in result

    def test_drug_type_returns_rxnorm(self):
        result = enrich_entity_codes("metformin", "drug")
        assert "rxnorm" in result

    def test_unknown_entity_tries_both(self):
        # Entity type "unknown" or "" tries both lookups
        result_icd = enrich_entity_codes("hypertension", "unknown")
        # hypertension is in ICD10 dict
        assert "icd10" in result_icd

    def test_empty_entity_type_tries_both(self):
        result = enrich_entity_codes("aspirin", "")
        assert "rxnorm" in result

    def test_entity_type_tries_both(self):
        result = enrich_entity_codes("aspirin", "entity")
        assert "rxnorm" in result

    def test_unknown_name_returns_empty_dict(self):
        result = enrich_entity_codes("unobtanium", "condition")
        assert result == {}

    def test_returns_dict(self):
        result = enrich_entity_codes("hypertension", "condition")
        assert isinstance(result, dict)

    def test_entity_type_case_insensitive(self):
        result_lower = enrich_entity_codes("hypertension", "condition")
        result_upper = enrich_entity_codes("hypertension", "CONDITION")
        assert result_lower == result_upper

    def test_empty_name_returns_empty_dict(self):
        result = enrich_entity_codes("", "condition")
        assert result == {}

    def test_unrecognized_entity_type_returns_empty(self):
        # Entity type not in recognized list — no lookups performed
        result = enrich_entity_codes("hypertension", "foobar_type")
        assert result == {}


# ===========================================================================
# SearchQualityConfig defaults
# ===========================================================================

class TestSearchQualityConfig:
    def test_enable_adaptive_threshold_default(self):
        cfg = SearchQualityConfig()
        assert cfg.enable_adaptive_threshold is True

    def test_min_threshold_default(self):
        cfg = SearchQualityConfig()
        assert cfg.min_threshold == 0.2

    def test_max_threshold_default(self):
        cfg = SearchQualityConfig()
        assert cfg.max_threshold == 0.8

    def test_target_result_count_default(self):
        cfg = SearchQualityConfig()
        assert cfg.target_result_count == 5

    def test_enable_query_expansion_default(self):
        cfg = SearchQualityConfig()
        assert cfg.enable_query_expansion is True

    def test_enable_bm25_default(self):
        cfg = SearchQualityConfig()
        assert cfg.enable_bm25 is True

    def test_vector_weight_default(self):
        cfg = SearchQualityConfig()
        assert cfg.vector_weight == 0.5

    def test_bm25_weight_default(self):
        cfg = SearchQualityConfig()
        assert cfg.bm25_weight == 0.3

    def test_enable_mmr_default(self):
        cfg = SearchQualityConfig()
        assert cfg.enable_mmr is True

    def test_mmr_lambda_default(self):
        cfg = SearchQualityConfig()
        assert cfg.mmr_lambda == 0.7

    def test_custom_values(self):
        cfg = SearchQualityConfig(min_threshold=0.35, max_threshold=0.9)
        assert cfg.min_threshold == 0.35
        assert cfg.max_threshold == 0.9


# ===========================================================================
# get_search_quality_config / reset_search_quality_config singleton
# ===========================================================================

@pytest.fixture(autouse=True)
def reset_search_config():
    reset_search_quality_config()
    yield
    reset_search_quality_config()


class TestSearchQualityConfigSingleton:
    def test_returns_config_instance(self):
        cfg = get_search_quality_config()
        assert isinstance(cfg, SearchQualityConfig)

    def test_same_instance_on_repeated_calls(self):
        c1 = get_search_quality_config()
        c2 = get_search_quality_config()
        assert c1 is c2

    def test_reset_clears_singleton(self):
        c1 = get_search_quality_config()
        reset_search_quality_config()
        c2 = get_search_quality_config()
        assert c1 is not c2

    def test_new_instance_after_reset_is_fresh(self):
        reset_search_quality_config()
        cfg = get_search_quality_config()
        assert cfg is not None
