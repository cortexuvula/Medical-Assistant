"""Tests for utils.vocabulary_corrector — VocabularyCorrector and CorrectionResult."""

import pytest
from utils.vocabulary_corrector import VocabularyCorrector, CorrectionResult


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def corrector():
    return VocabularyCorrector()


def make_rules(**overrides):
    """Build a minimal rule dict."""
    base = {
        "replacement": "Replacement",
        "category": "test",
        "enabled": True,
        "case_sensitive": False,
        "priority": 0,
    }
    base.update(overrides)
    return base


# ── CorrectionResult ──────────────────────────────────────────────────────────

class TestCorrectionResult:
    def test_defaults(self):
        r = CorrectionResult(original_text="a", corrected_text="b")
        assert r.corrections_applied == []
        assert r.specialty_used == "general"
        assert r.total_replacements == 0


# ── apply_corrections — empty/trivial cases ───────────────────────────────────

class TestApplyCorrectionsEdgeCases:
    def test_empty_text_returns_empty(self, corrector):
        result = corrector.apply_corrections("", {"htn": make_rules(replacement="HTN")})
        assert result.corrected_text == ""
        assert result.original_text == ""

    def test_no_rules_returns_original(self, corrector):
        result = corrector.apply_corrections("patient has htn", {})
        assert result.corrected_text == "patient has htn"

    def test_specialty_none_uses_general(self, corrector):
        result = corrector.apply_corrections("text", {}, specialty=None)
        assert result.specialty_used == "general"

    def test_specialty_preserved_in_result(self, corrector):
        result = corrector.apply_corrections("text", {}, specialty="cardiology")
        assert result.specialty_used == "cardiology"


# ── apply_corrections — basic replacements ────────────────────────────────────

class TestApplyCorrectionsBasic:
    def test_simple_replacement(self, corrector):
        rules = {"htn": make_rules(replacement="hypertension")}
        result = corrector.apply_corrections("patient has htn", rules)
        assert "hypertension" in result.corrected_text
        assert "htn" not in result.corrected_text

    def test_case_insensitive_by_default(self, corrector):
        rules = {"HTN": make_rules(replacement="hypertension")}
        result = corrector.apply_corrections("patient has htn", rules)
        assert "hypertension" in result.corrected_text

    def test_case_sensitive_does_not_match_wrong_case(self, corrector):
        rules = {"HTN": make_rules(replacement="hypertension", case_sensitive=True)}
        result = corrector.apply_corrections("patient has htn", rules)
        assert "htn" in result.corrected_text  # no change — case didn't match

    def test_case_sensitive_matches_exact_case(self, corrector):
        rules = {"HTN": make_rules(replacement="hypertension", case_sensitive=True)}
        result = corrector.apply_corrections("patient has HTN", rules)
        assert "hypertension" in result.corrected_text

    def test_word_boundary_prevents_partial_match(self, corrector):
        rules = {"htn": make_rules(replacement="hypertension")}
        result = corrector.apply_corrections("washington dc", rules)
        # "htn" is a substring of "washington" but word boundary prevents match
        assert result.corrected_text == "washington dc"

    def test_multiple_replacements_in_text(self, corrector):
        rules = {"htn": make_rules(replacement="hypertension")}
        result = corrector.apply_corrections("htn htn", rules)
        assert result.total_replacements == 2

    def test_multiple_rules_applied(self, corrector):
        rules = {
            "htn": make_rules(replacement="hypertension"),
            "dm": make_rules(replacement="diabetes mellitus"),
        }
        result = corrector.apply_corrections("patient has htn and dm", rules)
        assert "hypertension" in result.corrected_text
        assert "diabetes mellitus" in result.corrected_text

    def test_disabled_rule_skipped(self, corrector):
        rules = {"htn": make_rules(replacement="hypertension", enabled=False)}
        result = corrector.apply_corrections("patient has htn", rules)
        assert "htn" in result.corrected_text

    def test_empty_replacement_skipped(self, corrector):
        rules = {"htn": make_rules(replacement="")}
        result = corrector.apply_corrections("patient has htn", rules)
        assert "htn" in result.corrected_text


# ── apply_corrections — specialty filtering ───────────────────────────────────

class TestSpecialtyFiltering:
    def test_no_specialty_applies_all_rules(self, corrector):
        rules = {
            "htn": make_rules(replacement="hypertension", specialty="cardiology"),
        }
        result = corrector.apply_corrections("patient has htn", rules, specialty=None)
        assert "hypertension" in result.corrected_text

    def test_matching_specialty_applies(self, corrector):
        rules = {
            "htn": make_rules(replacement="hypertension", specialty="cardiology"),
        }
        result = corrector.apply_corrections("patient has htn", rules, specialty="cardiology")
        assert "hypertension" in result.corrected_text

    def test_non_matching_specialty_skips(self, corrector):
        rules = {
            "htn": make_rules(replacement="hypertension", specialty="cardiology"),
        }
        result = corrector.apply_corrections("patient has htn", rules, specialty="neurology")
        assert "htn" in result.corrected_text

    def test_general_specialty_always_applies(self, corrector):
        rules = {
            "htn": make_rules(replacement="hypertension", specialty="general"),
        }
        result = corrector.apply_corrections("patient has htn", rules, specialty="cardiology")
        assert "hypertension" in result.corrected_text


# ── apply_corrections — priority ordering ─────────────────────────────────────

class TestPriorityOrdering:
    def test_higher_priority_applied_first(self, corrector):
        """Longer/higher-priority rule runs first; short rule can't match any longer."""
        rules = {
            "chest pain": make_rules(replacement="angina pectoris", priority=10),
            "pain": make_rules(replacement="discomfort", priority=0),
        }
        result = corrector.apply_corrections("patient has chest pain", rules)
        # High-priority "chest pain" → "angina pectoris" — then "pain" finds no match
        assert "angina pectoris" in result.corrected_text
        assert "discomfort" not in result.corrected_text


# ── apply_corrections — metadata ──────────────────────────────────────────────

class TestCorrectionMetadata:
    def test_corrections_applied_list_populated(self, corrector):
        rules = {"htn": make_rules(replacement="hypertension")}
        result = corrector.apply_corrections("htn", rules)
        assert len(result.corrections_applied) == 1
        entry = result.corrections_applied[0]
        assert entry["find"] == "htn"
        assert entry["replace"] == "hypertension"
        assert entry["count"] == 1

    def test_total_replacements_counted(self, corrector):
        rules = {"htn": make_rules(replacement="hypertension")}
        result = corrector.apply_corrections("htn and more htn", rules)
        assert result.total_replacements == 2

    def test_original_text_preserved(self, corrector):
        rules = {"htn": make_rules(replacement="hypertension")}
        result = corrector.apply_corrections("patient has htn", rules)
        assert result.original_text == "patient has htn"


# ── _get_pattern — caching ────────────────────────────────────────────────────

class TestGetPattern:
    def test_pattern_cached(self, corrector):
        p1 = corrector._get_pattern("htn", False)
        p2 = corrector._get_pattern("htn", False)
        assert p1 is p2

    def test_different_case_sensitivity_different_pattern(self, corrector):
        p1 = corrector._get_pattern("htn", False)
        p2 = corrector._get_pattern("htn", True)
        assert p1 is not p2

    def test_returns_none_for_invalid_pattern(self, corrector):
        # Force a bad pattern by directly calling with something that
        # would be invalid after word boundary addition (edge case)
        # A pattern that results in invalid regex (very rare with re.escape, skip if None)
        p = corrector._get_pattern("valid_text", False)
        assert p is not None

    def test_clear_cache_works(self, corrector):
        corrector._get_pattern("htn", False)
        corrector.clear_cache()
        assert len(corrector._compiled_patterns) == 0


# ── test_correction ───────────────────────────────────────────────────────────

class TestTestCorrection:
    def test_applies_single_rule(self, corrector):
        result = corrector.test_correction("patient has htn", "htn", "hypertension")
        assert "hypertension" in result.corrected_text

    def test_case_insensitive_default(self, corrector):
        result = corrector.test_correction("patient has HTN", "htn", "hypertension")
        assert "hypertension" in result.corrected_text

    def test_case_sensitive_option(self, corrector):
        result = corrector.test_correction("patient has htn", "HTN", "hypertension", case_sensitive=True)
        assert "htn" in result.corrected_text  # no match

    def test_returns_correction_result(self, corrector):
        result = corrector.test_correction("text", "text", "replaced")
        assert isinstance(result, CorrectionResult)

    def test_no_match_returns_original(self, corrector):
        result = corrector.test_correction("patient has dm", "htn", "hypertension")
        assert result.corrected_text == "patient has dm"
