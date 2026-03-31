"""
Tests for src/rag/query_expander.py

Covers module-level dictionaries (MEDICAL_ABBREVIATIONS,
TERM_TO_ABBREVIATIONS, MEDICAL_SYNONYMS, REVERSE_SYNONYMS),
MedicalQueryExpander private methods (_tokenize, _expand_abbreviations,
_expand_synonyms, _build_expanded_query), expand_query() with all
config paths, get_search_terms(), and singleton helpers.
Pure regex/dict logic — no network, no Tkinter, no file I/O.
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

import rag.query_expander as qe_module
from rag.query_expander import (
    MEDICAL_ABBREVIATIONS,
    TERM_TO_ABBREVIATIONS,
    MEDICAL_SYNONYMS,
    REVERSE_SYNONYMS,
    MedicalQueryExpander,
    get_query_expander,
    reset_query_expander,
    expand_medical_query,
)
from rag.models import QueryExpansion
from rag.search_config import SearchQualityConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config(
    enable_query_expansion: bool = True,
    expand_abbreviations: bool = True,
    expand_synonyms: bool = True,
    max_expansion_terms: int = 5,
) -> SearchQualityConfig:
    cfg = SearchQualityConfig()
    cfg.enable_query_expansion = enable_query_expansion
    cfg.expand_abbreviations = expand_abbreviations
    cfg.expand_synonyms = expand_synonyms
    cfg.max_expansion_terms = max_expansion_terms
    return cfg


def _expander(**kwargs) -> MedicalQueryExpander:
    return MedicalQueryExpander(_config(**kwargs))


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_query_expander()
    yield
    reset_query_expander()


# ===========================================================================
# Module-level dictionaries
# ===========================================================================

class TestMedicalAbbreviations:
    def test_htn_expands_to_hypertension(self):
        assert "hypertension" in MEDICAL_ABBREVIATIONS["htn"]

    def test_mi_expands_to_myocardial_infarction(self):
        assert "myocardial infarction" in MEDICAL_ABBREVIATIONS["mi"]

    def test_dm_expands_to_diabetes(self):
        assert "diabetes mellitus" in MEDICAL_ABBREVIATIONS["dm"]

    def test_copd_expands_to_full_name(self):
        assert "chronic obstructive pulmonary disease" in MEDICAL_ABBREVIATIONS["copd"]

    def test_uti_expands_to_urinary_tract_infection(self):
        assert "urinary tract infection" in MEDICAL_ABBREVIATIONS["uti"]

    def test_all_values_are_lists(self):
        for abbr, vals in MEDICAL_ABBREVIATIONS.items():
            assert isinstance(vals, list), f"{abbr} has non-list value"

    def test_no_empty_expansion_lists(self):
        for abbr, vals in MEDICAL_ABBREVIATIONS.items():
            assert len(vals) > 0, f"{abbr} has empty expansion list"


class TestTermToAbbreviations:
    def test_hypertension_maps_to_htn(self):
        assert "htn" in TERM_TO_ABBREVIATIONS.get("hypertension", [])

    def test_myocardial_infarction_maps_to_mi(self):
        assert "mi" in TERM_TO_ABBREVIATIONS.get("myocardial infarction", [])

    def test_diabetes_mellitus_maps_back(self):
        assert "dm" in TERM_TO_ABBREVIATIONS.get("diabetes mellitus", [])

    def test_all_keys_are_lowercase(self):
        for key in TERM_TO_ABBREVIATIONS:
            assert key == key.lower(), f"Key not lowercase: {key}"

    def test_all_values_are_lists(self):
        for term, vals in TERM_TO_ABBREVIATIONS.items():
            assert isinstance(vals, list), f"{term} has non-list value"

    def test_no_duplicates_in_values(self):
        for term, vals in TERM_TO_ABBREVIATIONS.items():
            assert len(vals) == len(set(vals)), f"Duplicates in {term}"


class TestMedicalSynonyms:
    def test_heart_attack_includes_mi(self):
        assert "myocardial infarction" in MEDICAL_SYNONYMS["heart attack"]

    def test_hypertension_includes_high_blood_pressure(self):
        assert "high blood pressure" in MEDICAL_SYNONYMS["hypertension"]

    def test_stroke_includes_cva(self):
        assert "cerebrovascular accident" in MEDICAL_SYNONYMS["stroke"]

    def test_fatigue_includes_tiredness(self):
        assert "tiredness" in MEDICAL_SYNONYMS["fatigue"]

    def test_all_values_are_lists(self):
        for term, syns in MEDICAL_SYNONYMS.items():
            assert isinstance(syns, list), f"{term} has non-list value"

    def test_no_empty_synonym_lists(self):
        for term, syns in MEDICAL_SYNONYMS.items():
            assert len(syns) > 0, f"{term} has empty synonym list"


class TestReverseSynonyms:
    def test_myocardial_infarction_maps_to_heart_attack(self):
        assert "heart attack" in REVERSE_SYNONYMS.get("myocardial infarction", [])

    def test_all_keys_are_lowercase(self):
        for key in REVERSE_SYNONYMS:
            assert key == key.lower(), f"Key not lowercase: {key}"

    def test_all_values_are_lists(self):
        for term, vals in REVERSE_SYNONYMS.items():
            assert isinstance(vals, list)

    def test_no_duplicates_in_values(self):
        for term, vals in REVERSE_SYNONYMS.items():
            assert len(vals) == len(set(vals)), f"Duplicates in {term}"


# ===========================================================================
# _tokenize
# ===========================================================================

class TestTokenize:
    def setup_method(self):
        self.e = _expander()

    def test_returns_list(self):
        assert isinstance(self.e._tokenize("htn"), list)

    def test_single_word(self):
        tokens = self.e._tokenize("htn")
        assert "htn" in tokens

    def test_lowercase_normalized(self):
        tokens = self.e._tokenize("HTN")
        assert "htn" in tokens

    def test_two_words_produce_bigram(self):
        tokens = self.e._tokenize("heart attack")
        assert "heart attack" in tokens
        assert "heart" in tokens
        assert "attack" in tokens

    def test_three_words_produce_trigram(self):
        tokens = self.e._tokenize("chest pain assessment")
        assert "chest pain assessment" in tokens

    def test_empty_string_returns_empty_list(self):
        assert self.e._tokenize("") == []

    def test_strips_whitespace(self):
        tokens = self.e._tokenize("  htn  ")
        assert "htn" in tokens

    def test_multi_word_phrase_count(self):
        # "a b c" → words: [a,b,c], bigrams: [a b, b c], trigrams: [a b c] → 6 tokens
        tokens = self.e._tokenize("a b c")
        assert len(tokens) == 6


# ===========================================================================
# _expand_abbreviations
# ===========================================================================

class TestExpandAbbreviations:
    def setup_method(self):
        self.e = _expander()

    def test_known_abbreviation_expands(self):
        result = self.e._expand_abbreviations(["htn"])
        assert "htn" in result
        assert "hypertension" in result["htn"]

    def test_full_term_maps_to_abbreviation(self):
        result = self.e._expand_abbreviations(["hypertension"])
        assert "hypertension" in result
        assert "htn" in result["hypertension"]

    def test_unknown_token_not_in_result(self):
        result = self.e._expand_abbreviations(["xyzzy"])
        assert "xyzzy" not in result

    def test_empty_tokens_returns_empty_dict(self):
        assert self.e._expand_abbreviations([]) == {}

    def test_max_expansion_terms_respected(self):
        e = _expander(max_expansion_terms=1)
        # copd expands to 3 terms normally
        result = e._expand_abbreviations(["copd"])
        assert len(result["copd"]) <= 1

    def test_returns_dict(self):
        assert isinstance(self.e._expand_abbreviations(["mi"]), dict)

    def test_mi_expands(self):
        result = self.e._expand_abbreviations(["mi"])
        assert "mi" in result
        assert "myocardial infarction" in result["mi"]


# ===========================================================================
# _expand_synonyms
# ===========================================================================

class TestExpandSynonyms:
    def setup_method(self):
        self.e = _expander()

    def test_stroke_expands_to_synonyms(self):
        tokens = self.e._tokenize("stroke")
        result = self.e._expand_synonyms(tokens, "stroke")
        assert "stroke" in result
        assert "cerebrovascular accident" in result["stroke"]

    def test_heart_attack_phrase_matched(self):
        tokens = self.e._tokenize("heart attack")
        result = self.e._expand_synonyms(tokens, "heart attack")
        assert "heart attack" in result
        assert "myocardial infarction" in result["heart attack"]

    def test_reverse_synonym_found(self):
        tokens = self.e._tokenize("myocardial infarction")
        result = self.e._expand_synonyms(tokens, "myocardial infarction")
        # "myocardial infarction" is in REVERSE_SYNONYMS (from "heart attack" → "myocardial infarction")
        assert "myocardial infarction" in result

    def test_unknown_term_returns_empty_dict(self):
        result = self.e._expand_synonyms(["xyzzy"], "xyzzy")
        assert "xyzzy" not in result

    def test_returns_dict(self):
        tokens = self.e._tokenize("fatigue")
        result = self.e._expand_synonyms(tokens, "fatigue")
        assert isinstance(result, dict)

    def test_max_expansion_terms_respected(self):
        e = _expander(max_expansion_terms=1)
        tokens = e._tokenize("fatigue")
        result = e._expand_synonyms(tokens, "fatigue")
        if "fatigue" in result:
            assert len(result["fatigue"]) <= 1

    def test_empty_tokens_still_checks_full_query(self):
        # "heart attack" is a key in MEDICAL_SYNONYMS, should be found via full_query
        result = self.e._expand_synonyms([], "heart attack")
        assert "heart attack" in result


# ===========================================================================
# _build_expanded_query
# ===========================================================================

class TestBuildExpandedQuery:
    def setup_method(self):
        self.e = _expander()

    def test_no_expanded_terms_returns_original(self):
        result = self.e._build_expanded_query("htn", [])
        assert result == "htn"

    def test_with_expanded_terms_includes_original(self):
        result = self.e._build_expanded_query("htn", ["hypertension"])
        assert "htn" in result

    def test_with_expanded_terms_includes_expansions(self):
        result = self.e._build_expanded_query("htn", ["hypertension"])
        assert "hypertension" in result

    def test_limits_to_five_expanded_terms(self):
        terms = [f"term{i}" for i in range(10)]
        result = self.e._build_expanded_query("q", terms)
        # Original + at most 5 expanded terms = at most 6 space-separated parts
        parts = result.split()
        assert len(parts) <= 6

    def test_returns_string(self):
        assert isinstance(self.e._build_expanded_query("x", ["y"]), str)


# ===========================================================================
# expand_query() — main method
# ===========================================================================

class TestExpandQuery:
    def setup_method(self):
        self.e = _expander()

    def test_returns_query_expansion_instance(self):
        result = self.e.expand_query("htn")
        assert isinstance(result, QueryExpansion)

    def test_original_query_preserved(self):
        result = self.e.expand_query("hypertension")
        assert result.original_query == "hypertension"

    def test_expansion_disabled_returns_original(self):
        e = _expander(enable_query_expansion=False)
        result = e.expand_query("htn")
        assert result.expanded_query == "htn"
        assert result.expanded_terms == []

    def test_expansion_disabled_no_abbreviations(self):
        e = _expander(enable_query_expansion=False)
        result = e.expand_query("htn")
        assert result.abbreviation_expansions == {}

    def test_abbreviation_expansion_found(self):
        result = self.e.expand_query("htn")
        assert "htn" in result.abbreviation_expansions

    def test_abbreviations_disabled_no_abbr_expansions(self):
        e = _expander(expand_abbreviations=False)
        result = e.expand_query("htn")
        assert result.abbreviation_expansions == {}

    def test_synonym_expansion_found(self):
        result = self.e.expand_query("stroke")
        assert "stroke" in result.synonym_expansions

    def test_synonyms_disabled_no_syn_expansions(self):
        e = _expander(expand_synonyms=False)
        result = e.expand_query("stroke")
        assert result.synonym_expansions == {}

    def test_expanded_terms_are_list(self):
        result = self.e.expand_query("htn")
        assert isinstance(result.expanded_terms, list)

    def test_expanded_query_is_string(self):
        result = self.e.expand_query("htn")
        assert isinstance(result.expanded_query, str)

    def test_expanded_query_includes_original(self):
        result = self.e.expand_query("htn")
        assert "htn" in result.expanded_query

    def test_no_duplicate_terms(self):
        result = self.e.expand_query("mi")
        lower_terms = [t.lower() for t in result.expanded_terms]
        assert len(lower_terms) == len(set(lower_terms))

    def test_original_not_in_expanded_terms(self):
        result = self.e.expand_query("htn")
        assert "htn" not in [t.lower() for t in result.expanded_terms]

    def test_empty_query_returns_expansion(self):
        result = self.e.expand_query("")
        assert isinstance(result, QueryExpansion)
        assert result.original_query == ""

    def test_unknown_query_has_empty_expansions(self):
        result = self.e.expand_query("xyzzy unknown term zzz")
        assert result.expanded_terms == []

    def test_mi_expands_both_abbreviation_and_synonym(self):
        result = self.e.expand_query("mi")
        all_terms = result.get_all_search_terms()
        # Should include at least the original + some expansions
        assert len(all_terms) >= 2

    def test_heart_attack_phrase_expanded(self):
        result = self.e.expand_query("heart attack")
        assert "heart attack" in result.synonym_expansions


# ===========================================================================
# get_search_terms
# ===========================================================================

class TestGetSearchTerms:
    def setup_method(self):
        self.e = _expander()

    def test_returns_list(self):
        expansion = self.e.expand_query("htn")
        result = self.e.get_search_terms(expansion)
        assert isinstance(result, list)

    def test_includes_original_query(self):
        expansion = self.e.expand_query("htn")
        result = self.e.get_search_terms(expansion)
        assert "htn" in result

    def test_delegates_to_query_expansion(self):
        expansion = self.e.expand_query("stroke")
        result = self.e.get_search_terms(expansion)
        assert result == expansion.get_all_search_terms()


# ===========================================================================
# Singleton and module helpers
# ===========================================================================

class TestSingletonAndHelpers:
    def test_get_query_expander_returns_instance(self):
        assert isinstance(get_query_expander(), MedicalQueryExpander)

    def test_get_query_expander_same_instance(self):
        a = get_query_expander()
        b = get_query_expander()
        assert a is b

    def test_reset_clears_singleton(self):
        a = get_query_expander()
        reset_query_expander()
        b = get_query_expander()
        assert a is not b

    def test_expand_medical_query_returns_query_expansion(self):
        result = expand_medical_query("htn")
        assert isinstance(result, QueryExpansion)

    def test_expand_medical_query_original_preserved(self):
        result = expand_medical_query("stroke")
        assert result.original_query == "stroke"

    def test_expand_medical_query_empty_string(self):
        result = expand_medical_query("")
        assert isinstance(result, QueryExpansion)


# ===========================================================================
# TestMultiWordAbbreviations
# ===========================================================================

class TestMultiWordAbbreviations:
    """Test multi-word keys in dictionaries."""

    def test_c_diff_exists_in_abbreviations(self):
        assert "c diff" in MEDICAL_ABBREVIATIONS

    def test_c_diff_expands_to_clostridioides(self):
        expansions = MEDICAL_ABBREVIATIONS["c diff"]
        assert any("clostridioides" in e.lower() or "clostridium" in e.lower()
                    for e in expansions)

    def test_bidirectional_abbreviation_to_synonym(self):
        # "mi" → "myocardial infarction" (abbreviation)
        # "myocardial infarction" has synonyms like "heart attack"
        e = _expander()
        result = e.expand_query("mi")
        all_terms = result.get_all_search_terms()
        # Should contain "myocardial infarction" from abbreviation expansion
        assert any("myocardial infarction" in t.lower() for t in all_terms)

    def test_n_v_abbreviation_exists(self):
        assert "n/v" in MEDICAL_ABBREVIATIONS

    def test_heart_attack_is_synonym_key(self):
        assert "heart attack" in MEDICAL_SYNONYMS


# ===========================================================================
# TestOverlappingSynonyms
# ===========================================================================

class TestOverlappingSynonyms:
    """Test overlapping synonym expansion behavior."""

    def test_low_back_pain_contains_back_pain_key(self):
        # "back pain" is in MEDICAL_SYNONYMS
        assert "back pain" in MEDICAL_SYNONYMS
        e = _expander()
        result = e.expand_query("low back pain")
        # Should find "back pain" as a substring match in full_query
        assert "back pain" in result.synonym_expansions

    def test_repeated_terms_no_duplicate_expansions(self):
        e = _expander()
        result = e.expand_query("pain pain pain")
        # "pain" should appear in synonyms only once as a key
        terms = result.expanded_terms
        lower_terms = [t.lower() for t in terms]
        assert len(lower_terms) == len(set(lower_terms))

    def test_chest_pain_expands_both_as_phrase(self):
        e = _expander()
        result = e.expand_query("chest pain")
        # "chest pain" is a key in MEDICAL_SYNONYMS
        assert "chest pain" in result.synonym_expansions

    def test_original_not_in_expanded_terms(self):
        e = _expander()
        result = e.expand_query("headache")
        lower_expanded = [t.lower() for t in result.expanded_terms]
        assert "headache" not in lower_expanded


# ===========================================================================
# TestExpansionLimits
# ===========================================================================

class TestExpansionLimits:
    """Test expansion with very long queries and limits."""

    def test_very_long_query_max_5_expansion_terms(self):
        # Build a 25-word query
        words = [f"word{i}" for i in range(25)]
        query = " ".join(words)
        e = _expander(max_expansion_terms=5)
        result = e.expand_query(query)
        # No medical terms → no expansions
        assert result.expanded_terms == []

    def test_long_medical_query_limited_expansion(self):
        e = _expander(max_expansion_terms=2)
        result = e.expand_query("htn dm copd")
        # Each abbreviation limited to 2 expansions max
        for terms in result.abbreviation_expansions.values():
            assert len(terms) <= 2

    def test_query_already_expanded_form(self):
        e = _expander()
        result = e.expand_query("hypertension")
        # "hypertension" is a full term → should get abbreviation "htn" back
        assert "hypertension" in result.abbreviation_expansions
        assert "htn" in result.abbreviation_expansions["hypertension"]

    def test_expanded_query_string_max_6_parts(self):
        # _build_expanded_query limits to original + 5 terms
        e = _expander()
        terms = [f"term{i}" for i in range(10)]
        result = e._build_expanded_query("original", terms)
        parts = result.split()
        assert len(parts) <= 6

    def test_max_expansion_terms_1(self):
        e = _expander(max_expansion_terms=1)
        result = e.expand_query("mi")
        # "mi" has multiple expansions but limited to 1
        if "mi" in result.abbreviation_expansions:
            assert len(result.abbreviation_expansions["mi"]) <= 1

    def test_empty_query_no_expansions(self):
        e = _expander()
        result = e.expand_query("")
        assert result.expanded_terms == []
        assert result.expanded_query == ""
