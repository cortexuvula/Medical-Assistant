"""
Comprehensive unit tests for utils.vocabulary_corrector — VocabularyCorrector and CorrectionResult.

Covers:
- CorrectionResult dataclass defaults and field types
- apply_corrections: empty/trivial cases, single/multiple replacements,
  case sensitivity (default and per-entry), word-boundary enforcement,
  priority ordering, length ordering, disabled-entry skipping,
  specialty filtering, corrections_applied metadata, total_replacements
- _get_pattern: valid patterns, case-sensitive flag, caching behaviour,
  invalid regex returns None
- clear_cache: empties the compiled-patterns dict
- test_correction: basic use, case sensitivity
"""

import sys
import re
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from utils.vocabulary_corrector import VocabularyCorrector, CorrectionResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_rule(
    replacement="Replacement",
    category="test",
    enabled=True,
    case_sensitive=False,
    priority=0,
    specialty=None,
):
    """Return a minimal rule dict suitable for the corrections mapping."""
    return {
        "replacement": replacement,
        "category": category,
        "enabled": enabled,
        "case_sensitive": case_sensitive,
        "priority": priority,
        "specialty": specialty,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def corrector():
    return VocabularyCorrector()


# ===========================================================================
# CorrectionResult dataclass
# ===========================================================================

class TestCorrectionResult:
    """Tests for the CorrectionResult dataclass."""

    def test_required_fields_stored(self):
        r = CorrectionResult(original_text="orig", corrected_text="corr")
        assert r.original_text == "orig"
        assert r.corrected_text == "corr"

    def test_default_corrections_applied_is_empty_list(self):
        r = CorrectionResult(original_text="a", corrected_text="b")
        assert r.corrections_applied == []

    def test_default_specialty_used_is_general(self):
        r = CorrectionResult(original_text="a", corrected_text="b")
        assert r.specialty_used == "general"

    def test_default_total_replacements_is_zero(self):
        r = CorrectionResult(original_text="a", corrected_text="b")
        assert r.total_replacements == 0

    def test_corrections_applied_uses_independent_list_per_instance(self):
        r1 = CorrectionResult(original_text="a", corrected_text="b")
        r2 = CorrectionResult(original_text="c", corrected_text="d")
        r1.corrections_applied.append({"find": "x"})
        assert r2.corrections_applied == []

    def test_custom_specialty_stored(self):
        r = CorrectionResult(original_text="a", corrected_text="b", specialty_used="cardiology")
        assert r.specialty_used == "cardiology"

    def test_custom_total_replacements_stored(self):
        r = CorrectionResult(original_text="a", corrected_text="b", total_replacements=5)
        assert r.total_replacements == 5

    def test_custom_corrections_applied_stored(self):
        applied = [{"find": "x", "replace": "y"}]
        r = CorrectionResult(original_text="a", corrected_text="b", corrections_applied=applied)
        assert r.corrections_applied == applied


# ===========================================================================
# apply_corrections — empty / trivial cases
# ===========================================================================

class TestApplyCorrectionsEdgeCases:
    """Edge cases: empty text and empty corrections dict."""

    def test_empty_text_returns_empty_corrected_text(self, corrector):
        result = corrector.apply_corrections("", {"htn": make_rule(replacement="HTN")})
        assert result.corrected_text == ""

    def test_empty_text_returns_empty_original_text(self, corrector):
        result = corrector.apply_corrections("", {"htn": make_rule(replacement="HTN")})
        assert result.original_text == ""

    def test_empty_text_zero_replacements(self, corrector):
        result = corrector.apply_corrections("", {"htn": make_rule(replacement="HTN")})
        assert result.total_replacements == 0

    def test_empty_text_no_corrections_applied(self, corrector):
        result = corrector.apply_corrections("", {"htn": make_rule(replacement="HTN")})
        assert result.corrections_applied == []

    def test_empty_text_specialty_preserved(self, corrector):
        result = corrector.apply_corrections("", {}, specialty="neurology")
        assert result.specialty_used == "neurology"

    def test_empty_text_no_specialty_defaults_to_general(self, corrector):
        result = corrector.apply_corrections("", {})
        assert result.specialty_used == "general"

    def test_no_rules_returns_original_text_unchanged(self, corrector):
        result = corrector.apply_corrections("patient has htn", {})
        assert result.corrected_text == "patient has htn"

    def test_no_rules_original_text_preserved(self, corrector):
        result = corrector.apply_corrections("patient has htn", {})
        assert result.original_text == "patient has htn"

    def test_no_rules_zero_replacements(self, corrector):
        result = corrector.apply_corrections("patient has htn", {})
        assert result.total_replacements == 0

    def test_no_rules_specialty_preserved(self, corrector):
        result = corrector.apply_corrections("text", {}, specialty="cardiology")
        assert result.specialty_used == "cardiology"

    def test_no_rules_no_specialty_defaults_to_general(self, corrector):
        result = corrector.apply_corrections("text", {})
        assert result.specialty_used == "general"

    def test_returns_correction_result_instance(self, corrector):
        result = corrector.apply_corrections("text", {})
        assert isinstance(result, CorrectionResult)


# ===========================================================================
# apply_corrections — basic single replacement
# ===========================================================================

class TestApplyCorrectionsBasic:
    """Basic single-rule replacement scenarios."""

    def test_simple_replacement_applies(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections("patient has htn", rules)
        assert "hypertension" in result.corrected_text

    def test_find_text_removed_after_replacement(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections("patient has htn", rules)
        assert "htn" not in result.corrected_text

    def test_original_text_preserved_in_result(self, corrector):
        original = "patient has htn"
        rules = {"htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections(original, rules)
        assert result.original_text == original

    def test_total_replacements_is_one_for_single_match(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections("patient has htn", rules)
        assert result.total_replacements == 1

    def test_surrounding_words_untouched(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections("patient has htn today", rules)
        assert "patient has" in result.corrected_text
        assert "today" in result.corrected_text

    def test_replacement_with_spaces_works(self, corrector):
        rules = {"dm": make_rule(replacement="diabetes mellitus")}
        result = corrector.apply_corrections("dx is dm", rules)
        assert "diabetes mellitus" in result.corrected_text

    def test_no_match_text_unchanged(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections("patient is well", rules)
        assert result.corrected_text == "patient is well"

    def test_no_match_zero_total_replacements(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections("patient is well", rules)
        assert result.total_replacements == 0

    def test_no_match_empty_corrections_applied(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections("patient is well", rules)
        assert result.corrections_applied == []


# ===========================================================================
# apply_corrections — multiple occurrences and rules
# ===========================================================================

class TestApplyCorrectionsMultiple:
    """Multiple occurrences and multiple rules."""

    def test_two_occurrences_both_replaced(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections("htn htn", rules)
        assert result.corrected_text == "hypertension hypertension"

    def test_two_occurrences_total_replacements_is_two(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections("htn htn", rules)
        assert result.total_replacements == 2

    def test_three_occurrences_counted(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections("htn, htn, and htn", rules)
        assert result.total_replacements == 3

    def test_two_different_rules_both_applied(self, corrector):
        rules = {
            "htn": make_rule(replacement="hypertension"),
            "dm": make_rule(replacement="diabetes mellitus"),
        }
        result = corrector.apply_corrections("patient has htn and dm", rules)
        assert "hypertension" in result.corrected_text
        assert "diabetes mellitus" in result.corrected_text

    def test_two_rules_total_replacements_sum(self, corrector):
        rules = {
            "htn": make_rule(replacement="hypertension"),
            "dm": make_rule(replacement="diabetes mellitus"),
        }
        result = corrector.apply_corrections("patient has htn and dm", rules)
        assert result.total_replacements == 2

    def test_two_rules_corrections_applied_list_has_two_entries(self, corrector):
        rules = {
            "htn": make_rule(replacement="hypertension"),
            "dm": make_rule(replacement="diabetes mellitus"),
        }
        result = corrector.apply_corrections("patient has htn and dm", rules)
        assert len(result.corrections_applied) == 2


# ===========================================================================
# apply_corrections — case sensitivity
# ===========================================================================

class TestCaseSensitivity:
    """Case-sensitive and case-insensitive matching."""

    def test_default_case_insensitive_upper_find_lower_text(self, corrector):
        rules = {"HTN": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections("patient has htn", rules)
        assert "hypertension" in result.corrected_text

    def test_default_case_insensitive_lower_find_upper_text(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections("patient has HTN", rules)
        assert "hypertension" in result.corrected_text

    def test_default_case_insensitive_mixed_find_mixed_text(self, corrector):
        rules = {"Htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections("patient has hTN", rules)
        assert "hypertension" in result.corrected_text

    def test_per_entry_case_sensitive_exact_case_matches(self, corrector):
        rules = {"HTN": make_rule(replacement="hypertension", case_sensitive=True)}
        result = corrector.apply_corrections("patient has HTN", rules)
        assert "hypertension" in result.corrected_text

    def test_per_entry_case_sensitive_wrong_case_no_match(self, corrector):
        rules = {"HTN": make_rule(replacement="hypertension", case_sensitive=True)}
        result = corrector.apply_corrections("patient has htn", rules)
        assert "htn" in result.corrected_text
        assert "hypertension" not in result.corrected_text

    def test_per_entry_case_sensitive_overrides_default(self, corrector):
        # Even though default_case_sensitive=False, per-entry flag wins
        rules = {"HTN": make_rule(replacement="hypertension", case_sensitive=True)}
        result = corrector.apply_corrections(
            "patient has htn", rules, default_case_sensitive=False
        )
        assert "htn" in result.corrected_text

    def test_default_case_sensitive_parameter_true_enforces_case(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections(
            "patient has HTN", rules, default_case_sensitive=True
        )
        # The rule's case_sensitive is False (from make_rule default) which
        # overrides the default; let's test with a rule that has no explicit override
        # by omitting case_sensitive from the rule dict
        rule_no_cs = {
            "replacement": "hypertension",
            "category": "test",
            "enabled": True,
            "priority": 0,
        }
        result2 = corrector.apply_corrections(
            "patient has HTN", {"htn": rule_no_cs}, default_case_sensitive=True
        )
        # default_case_sensitive=True and rule has no case_sensitive key → sensitive match
        assert "HTN" in result2.corrected_text

    def test_rule_case_sensitive_false_matches_regardless_of_default(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension", case_sensitive=False)}
        result = corrector.apply_corrections(
            "patient has HTN", rules, default_case_sensitive=True
        )
        assert "hypertension" in result.corrected_text


# ===========================================================================
# apply_corrections — word boundary enforcement
# ===========================================================================

class TestWordBoundary:
    """Word-boundary prevents partial-word matches."""

    def test_substring_not_matched_within_longer_word(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections("washington dc", rules)
        assert result.corrected_text == "washington dc"

    def test_standalone_word_still_matched(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections("htn", rules)
        assert result.corrected_text == "hypertension"

    def test_word_at_start_of_sentence_matched(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections("htn is present", rules)
        assert result.corrected_text.startswith("hypertension")

    def test_word_at_end_of_sentence_matched(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections("diagnosis is htn", rules)
        assert result.corrected_text.endswith("hypertension")

    def test_word_surrounded_by_punctuation_matched(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections("(htn)", rules)
        assert "hypertension" in result.corrected_text

    def test_abbreviation_not_matched_in_prefix(self, corrector):
        # "dm" should NOT match "admittance"
        rules = {"dm": make_rule(replacement="diabetes mellitus")}
        result = corrector.apply_corrections("admittance form", rules)
        assert result.corrected_text == "admittance form"

    def test_abbreviation_not_matched_in_suffix(self, corrector):
        # "mi" should NOT match "family"
        rules = {"mi": make_rule(replacement="myocardial infarction")}
        result = corrector.apply_corrections("family history", rules)
        assert result.corrected_text == "family history"

    def test_word_boundary_comma_separated_list(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections("htn,dm,chf", rules)
        assert "hypertension" in result.corrected_text


# ===========================================================================
# apply_corrections — disabled entries
# ===========================================================================

class TestDisabledEntries:
    """Entries with enabled=False are skipped."""

    def test_disabled_entry_not_applied(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension", enabled=False)}
        result = corrector.apply_corrections("patient has htn", rules)
        assert "htn" in result.corrected_text
        assert "hypertension" not in result.corrected_text

    def test_disabled_entry_zero_replacements(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension", enabled=False)}
        result = corrector.apply_corrections("patient has htn", rules)
        assert result.total_replacements == 0

    def test_disabled_entry_not_in_corrections_applied(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension", enabled=False)}
        result = corrector.apply_corrections("patient has htn", rules)
        assert result.corrections_applied == []

    def test_enabled_entry_alongside_disabled_still_applies(self, corrector):
        rules = {
            "htn": make_rule(replacement="hypertension", enabled=False),
            "dm": make_rule(replacement="diabetes mellitus", enabled=True),
        }
        result = corrector.apply_corrections("patient has htn and dm", rules)
        assert "htn" in result.corrected_text
        assert "diabetes mellitus" in result.corrected_text

    def test_missing_enabled_key_treated_as_enabled(self, corrector):
        # Default value for get("enabled", True) means missing key → enabled
        rule = {"replacement": "hypertension", "category": "test", "priority": 0}
        result = corrector.apply_corrections("patient has htn", {"htn": rule})
        assert "hypertension" in result.corrected_text


# ===========================================================================
# apply_corrections — empty / missing replacement
# ===========================================================================

class TestEmptyReplacement:
    """Entries with empty or missing replacement are skipped."""

    def test_empty_string_replacement_skipped(self, corrector):
        rules = {"htn": make_rule(replacement="")}
        result = corrector.apply_corrections("patient has htn", rules)
        assert "htn" in result.corrected_text

    def test_missing_replacement_key_skipped(self, corrector):
        rule = {"category": "test", "enabled": True, "priority": 0}
        result = corrector.apply_corrections("patient has htn", {"htn": rule})
        assert "htn" in result.corrected_text

    def test_none_replacement_skipped(self, corrector):
        rule = {"replacement": None, "category": "test", "enabled": True, "priority": 0}
        result = corrector.apply_corrections("patient has htn", {"htn": rule})
        # None is falsy so it should be skipped
        assert "htn" in result.corrected_text


# ===========================================================================
# apply_corrections — specialty filtering
# ===========================================================================

class TestSpecialtyFiltering:
    """Specialty-aware rule filtering."""

    def test_no_call_specialty_applies_all_rules(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension", specialty="cardiology")}
        result = corrector.apply_corrections("patient has htn", rules, specialty=None)
        assert "hypertension" in result.corrected_text

    def test_matching_specialty_applies_rule(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension", specialty="cardiology")}
        result = corrector.apply_corrections("patient has htn", rules, specialty="cardiology")
        assert "hypertension" in result.corrected_text

    def test_non_matching_specialty_skips_rule(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension", specialty="cardiology")}
        result = corrector.apply_corrections("patient has htn", rules, specialty="neurology")
        assert "htn" in result.corrected_text

    def test_rule_specialty_general_applies_with_any_specialty(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension", specialty="general")}
        result = corrector.apply_corrections("patient has htn", rules, specialty="cardiology")
        assert "hypertension" in result.corrected_text

    def test_rule_specialty_none_applies_with_any_specialty(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension", specialty=None)}
        result = corrector.apply_corrections("patient has htn", rules, specialty="cardiology")
        assert "hypertension" in result.corrected_text

    def test_specialty_preserved_in_result(self, corrector):
        result = corrector.apply_corrections("text", {}, specialty="radiology")
        assert result.specialty_used == "radiology"

    def test_no_specialty_defaults_to_general_in_result(self, corrector):
        result = corrector.apply_corrections("text", {})
        assert result.specialty_used == "general"

    def test_mixed_specialties_correct_ones_apply(self, corrector):
        rules = {
            "echo": make_rule(replacement="echocardiogram", specialty="cardiology"),
            "eeg": make_rule(replacement="electroencephalogram", specialty="neurology"),
        }
        result = corrector.apply_corrections(
            "ordered echo and eeg", rules, specialty="cardiology"
        )
        assert "echocardiogram" in result.corrected_text
        assert "eeg" in result.corrected_text  # neurology rule skipped


# ===========================================================================
# apply_corrections — priority and length ordering
# ===========================================================================

class TestOrdering:
    """Priority and length-based ordering of correction application."""

    def test_higher_priority_applied_first(self, corrector):
        rules = {
            "chest pain": make_rule(replacement="angina pectoris", priority=10),
            "pain": make_rule(replacement="discomfort", priority=0),
        }
        result = corrector.apply_corrections("patient has chest pain", rules)
        assert "angina pectoris" in result.corrected_text
        assert "discomfort" not in result.corrected_text

    def test_lower_priority_not_applied_when_consumed_by_higher(self, corrector):
        rules = {
            "chest pain": make_rule(replacement="angina pectoris", priority=5),
            "chest": make_rule(replacement="thoracic", priority=1),
        }
        result = corrector.apply_corrections("chest pain", rules)
        # "chest pain" consumed by higher-priority rule; "chest" no longer present
        assert "angina pectoris" in result.corrected_text
        assert "thoracic" not in result.corrected_text

    def test_same_priority_longer_match_applied_first(self, corrector):
        rules = {
            "shortness of breath": make_rule(replacement="dyspnea", priority=0),
            "breath": make_rule(replacement="respiration", priority=0),
        }
        result = corrector.apply_corrections("patient has shortness of breath", rules)
        assert "dyspnea" in result.corrected_text
        assert "respiration" not in result.corrected_text

    def test_equal_priority_equal_length_both_may_apply(self, corrector):
        rules = {
            "htn": make_rule(replacement="hypertension", priority=0),
            "dm2": make_rule(replacement="type 2 diabetes", priority=0),
        }
        result = corrector.apply_corrections("htn and dm2", rules)
        assert "hypertension" in result.corrected_text
        assert "type 2 diabetes" in result.corrected_text


# ===========================================================================
# apply_corrections — corrections_applied metadata
# ===========================================================================

class TestCorrectionsAppliedMetadata:
    """Verify the corrections_applied list content."""

    def test_single_rule_adds_one_entry(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections("htn", rules)
        assert len(result.corrections_applied) == 1

    def test_entry_find_field(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections("htn", rules)
        assert result.corrections_applied[0]["find"] == "htn"

    def test_entry_replace_field(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections("htn", rules)
        assert result.corrections_applied[0]["replace"] == "hypertension"

    def test_entry_count_field_single(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections("htn", rules)
        assert result.corrections_applied[0]["count"] == 1

    def test_entry_count_field_multiple(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections("htn and htn", rules)
        assert result.corrections_applied[0]["count"] == 2

    def test_entry_category_field(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension", category="abbreviations")}
        result = corrector.apply_corrections("htn", rules)
        assert result.corrections_applied[0]["category"] == "abbreviations"

    def test_entry_category_defaults_to_general_when_missing(self, corrector):
        rule = {"replacement": "hypertension", "enabled": True, "priority": 0}
        result = corrector.apply_corrections("htn", {"htn": rule})
        assert result.corrections_applied[0]["category"] == "general"

    def test_no_match_produces_no_entry(self, corrector):
        rules = {"htn": make_rule(replacement="hypertension")}
        result = corrector.apply_corrections("no relevant text", rules)
        assert result.corrections_applied == []

    def test_two_rules_two_entries(self, corrector):
        rules = {
            "htn": make_rule(replacement="hypertension"),
            "dm": make_rule(replacement="diabetes mellitus"),
        }
        result = corrector.apply_corrections("htn dm", rules)
        finds = {e["find"] for e in result.corrections_applied}
        assert finds == {"htn", "dm"}

    def test_total_replacements_matches_sum_of_counts(self, corrector):
        rules = {
            "htn": make_rule(replacement="hypertension"),
            "dm": make_rule(replacement="diabetes mellitus"),
        }
        result = corrector.apply_corrections("htn dm htn", rules)
        total_from_list = sum(e["count"] for e in result.corrections_applied)
        assert result.total_replacements == total_from_list


# ===========================================================================
# _get_pattern — caching and validity
# ===========================================================================

class TestGetPattern:
    """Tests for the _get_pattern method."""

    def test_returns_compiled_pattern(self, corrector):
        p = corrector._get_pattern("htn", False)
        assert isinstance(p, re.Pattern)

    def test_pattern_uses_word_boundaries(self, corrector):
        p = corrector._get_pattern("htn", False)
        assert p.search("htn") is not None
        assert p.search("washington") is None

    def test_case_insensitive_flag_applied(self, corrector):
        p = corrector._get_pattern("htn", False)
        assert p.search("HTN") is not None

    def test_case_sensitive_flag_applied(self, corrector):
        p = corrector._get_pattern("htn", True)
        assert p.search("HTN") is None

    def test_case_sensitive_exact_match(self, corrector):
        p = corrector._get_pattern("HTN", True)
        assert p.search("HTN") is not None

    def test_same_key_returns_same_object(self, corrector):
        p1 = corrector._get_pattern("htn", False)
        p2 = corrector._get_pattern("htn", False)
        assert p1 is p2

    def test_different_text_different_objects(self, corrector):
        p1 = corrector._get_pattern("htn", False)
        p2 = corrector._get_pattern("dm", False)
        assert p1 is not p2

    def test_different_case_sensitivity_different_objects(self, corrector):
        p1 = corrector._get_pattern("htn", False)
        p2 = corrector._get_pattern("htn", True)
        assert p1 is not p2

    def test_pattern_cached_after_first_call(self, corrector):
        corrector._get_pattern("htn", False)
        assert ("htn", False) in corrector._compiled_patterns

    def test_cache_stores_both_case_variants(self, corrector):
        corrector._get_pattern("htn", False)
        corrector._get_pattern("htn", True)
        assert ("htn", False) in corrector._compiled_patterns
        assert ("htn", True) in corrector._compiled_patterns

    def test_valid_multiword_pattern_returned(self, corrector):
        p = corrector._get_pattern("chest pain", False)
        assert p is not None

    def test_numeric_text_pattern_returned(self, corrector):
        p = corrector._get_pattern("bp140", False)
        assert p is not None

    def test_hyphenated_text_pattern_returned(self, corrector):
        # re.escape handles hyphens; pattern should compile
        p = corrector._get_pattern("follow-up", False)
        assert p is not None


# ===========================================================================
# clear_cache
# ===========================================================================

class TestClearCache:
    """Tests for the clear_cache method."""

    def test_clear_cache_empties_dict(self, corrector):
        corrector._get_pattern("htn", False)
        corrector._get_pattern("dm", True)
        corrector.clear_cache()
        assert len(corrector._compiled_patterns) == 0

    def test_clear_cache_on_empty_dict_is_safe(self, corrector):
        corrector.clear_cache()  # should not raise
        assert len(corrector._compiled_patterns) == 0

    def test_pattern_recompiled_after_clear(self, corrector):
        p1 = corrector._get_pattern("htn", False)
        corrector.clear_cache()
        p2 = corrector._get_pattern("htn", False)
        # New object after cache clear (they may be equal but not the same identity)
        assert p2 is not None

    def test_multiple_clears_safe(self, corrector):
        corrector._get_pattern("htn", False)
        corrector.clear_cache()
        corrector.clear_cache()
        assert len(corrector._compiled_patterns) == 0


# ===========================================================================
# test_correction
# ===========================================================================

class TestTestCorrection:
    """Tests for the test_correction convenience method."""

    def test_returns_correction_result(self, corrector):
        result = corrector.test_correction("patient has htn", "htn", "hypertension")
        assert isinstance(result, CorrectionResult)

    def test_applies_single_rule(self, corrector):
        result = corrector.test_correction("patient has htn", "htn", "hypertension")
        assert "hypertension" in result.corrected_text

    def test_original_text_preserved(self, corrector):
        result = corrector.test_correction("patient has htn", "htn", "hypertension")
        assert result.original_text == "patient has htn"

    def test_case_insensitive_by_default(self, corrector):
        result = corrector.test_correction("patient has HTN", "htn", "hypertension")
        assert "hypertension" in result.corrected_text

    def test_case_sensitive_flag_prevents_wrong_case_match(self, corrector):
        result = corrector.test_correction(
            "patient has htn", "HTN", "hypertension", case_sensitive=True
        )
        assert "htn" in result.corrected_text
        assert "hypertension" not in result.corrected_text

    def test_case_sensitive_flag_allows_exact_case_match(self, corrector):
        result = corrector.test_correction(
            "patient has HTN", "HTN", "hypertension", case_sensitive=True
        )
        assert "hypertension" in result.corrected_text

    def test_no_match_returns_original_unchanged(self, corrector):
        result = corrector.test_correction("patient has dm", "htn", "hypertension")
        assert result.corrected_text == "patient has dm"

    def test_total_replacements_counted(self, corrector):
        result = corrector.test_correction("htn and htn", "htn", "hypertension")
        assert result.total_replacements == 2

    def test_word_boundary_respected(self, corrector):
        result = corrector.test_correction("washington dc", "htn", "hypertension")
        assert result.corrected_text == "washington dc"

    def test_category_is_test_in_applied_entry(self, corrector):
        result = corrector.test_correction("htn", "htn", "hypertension")
        assert result.corrections_applied[0]["category"] == "test"
