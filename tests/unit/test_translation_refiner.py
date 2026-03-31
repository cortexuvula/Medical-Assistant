"""
Tests for src/ai/translation_refiner.py

Covers RefinementResult dataclass, MEDICAL_INDICATORS list,
TranslationRefiner.should_refine() and _extract_medical_terms().
The refine_translation() method makes live AI calls and is not unit-tested.
Pure string/list logic — no network, no Tkinter, no file I/O.
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

from ai.translation_refiner import RefinementResult, TranslationRefiner


# ---------------------------------------------------------------------------
# Helper — create refiner with refinement enabled
# ---------------------------------------------------------------------------

def _refiner(enabled: bool = True) -> TranslationRefiner:
    r = TranslationRefiner()
    r.refinement_enabled = enabled
    return r


# ===========================================================================
# RefinementResult dataclass
# ===========================================================================

class TestRefinementResult:
    def test_fields_stored(self):
        r = RefinementResult(
            original_translation="orig",
            refined_translation="refined",
            was_refined=True,
            confidence_score=0.9,
            medical_terms_detected=["pain"],
        )
        assert r.original_translation == "orig"
        assert r.refined_translation == "refined"
        assert r.was_refined is True
        assert r.confidence_score == pytest.approx(0.9)
        assert r.medical_terms_detected == ["pain"]

    def test_was_refined_false(self):
        r = RefinementResult("x", "x", False, 1.0, [])
        assert r.was_refined is False

    def test_empty_medical_terms(self):
        r = RefinementResult("x", "x", False, 1.0, [])
        assert r.medical_terms_detected == []

    def test_instances_dont_share_medical_terms_list(self):
        r1 = RefinementResult("a", "a", False, 1.0, [])
        r2 = RefinementResult("b", "b", False, 1.0, [])
        r1.medical_terms_detected.append("pain")
        assert r2.medical_terms_detected == []


# ===========================================================================
# MEDICAL_INDICATORS
# ===========================================================================

class TestMedicalIndicators:
    def setup_method(self):
        self.indicators = TranslationRefiner.MEDICAL_INDICATORS

    def test_is_list(self):
        assert isinstance(self.indicators, list)

    def test_non_empty(self):
        assert len(self.indicators) > 0

    def test_pain_included(self):
        assert "pain" in self.indicators

    def test_fever_included(self):
        assert "fever" in self.indicators

    def test_medication_included(self):
        assert "medication" in self.indicators

    def test_all_lowercase(self):
        bad = [t for t in self.indicators if t != t.lower()]
        assert bad == [], f"Non-lowercase indicators: {bad}"

    def test_no_empty_strings(self):
        assert all(len(t.strip()) > 0 for t in self.indicators)

    def test_heart_included(self):
        assert "heart" in self.indicators

    def test_spanish_terms_included(self):
        # Should have some Spanish indicators
        spanish_terms = {"dolor", "fiebre", "sangre", "corazon"}
        found = spanish_terms & set(self.indicators)
        assert len(found) > 0


# ===========================================================================
# should_refine
# ===========================================================================

class TestShouldRefine:
    def setup_method(self):
        self.r = _refiner(enabled=True)

    def test_refinement_disabled_returns_false(self):
        r = _refiner(enabled=False)
        assert r.should_refine("patient has pain and fever") is False

    def test_text_with_medical_term_returns_true(self):
        assert self.r.should_refine("The patient has chest pain") is True

    def test_text_with_fever_returns_true(self):
        assert self.r.should_refine("She has a fever of 38°C") is True

    def test_text_with_medication_returns_true(self):
        assert self.r.should_refine("Take this medication twice daily") is True

    def test_non_medical_text_returns_false(self):
        assert self.r.should_refine("The weather is nice today") is False

    def test_empty_string_returns_false(self):
        assert self.r.should_refine("") is False

    def test_case_insensitive(self):
        # "PAIN" should match "pain" indicator
        assert self.r.should_refine("PAIN in the lower back") is True

    def test_spanish_medical_term_returns_true(self):
        assert self.r.should_refine("El paciente tiene dolor fuerte") is True

    def test_heart_text_returns_true(self):
        assert self.r.should_refine("Heart rate is elevated") is True

    def test_mg_dosing_returns_true(self):
        assert self.r.should_refine("Take 500 mg three times daily") is True

    def test_returns_bool(self):
        result = self.r.should_refine("some text")
        assert isinstance(result, bool)


# ===========================================================================
# _extract_medical_terms
# ===========================================================================

class TestExtractMedicalTerms:
    def setup_method(self):
        self.r = _refiner()

    def test_returns_list(self):
        assert isinstance(self.r._extract_medical_terms(""), list)

    def test_empty_text_returns_empty_list(self):
        assert self.r._extract_medical_terms("") == []

    def test_non_medical_text_returns_empty_list(self):
        result = self.r._extract_medical_terms("The weather is sunny today")
        assert result == []

    def test_pain_detected(self):
        result = self.r._extract_medical_terms("Patient reports pain in the knee")
        assert "pain" in result

    def test_fever_detected(self):
        result = self.r._extract_medical_terms("High fever persists")
        assert "fever" in result

    def test_multiple_terms_detected(self):
        result = self.r._extract_medical_terms("fever and pain and cough")
        assert "fever" in result
        assert "pain" in result
        assert "cough" in result

    def test_case_insensitive(self):
        result = self.r._extract_medical_terms("FEVER and PAIN")
        assert "fever" in result
        assert "pain" in result

    def test_no_duplicates_for_same_occurrence(self):
        # "pain" appears once, should appear once in result
        result = self.r._extract_medical_terms("pain")
        assert result.count("pain") == 1

    def test_spanish_term_detected(self):
        result = self.r._extract_medical_terms("El paciente tiene dolor fuerte")
        assert "dolor" in result

    def test_all_returned_terms_are_in_indicators(self):
        result = self.r._extract_medical_terms("fever pain cough heart")
        for term in result:
            assert term in TranslationRefiner.MEDICAL_INDICATORS
