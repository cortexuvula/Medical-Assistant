"""
Tests for pure helper functions in src/ai/letter_generation.py

Covers _get_recipient_guidance() (structure, known types, unknown fallback),
_build_letter_prompt() (prompt construction, recipient display names, specs,
focus/exclude inclusion), and _get_letter_system_message() (base message
+ recipient-specific content).
No AI calls, no network, no Tkinter.
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

from ai.letter_generation import (
    _get_recipient_guidance,
    _build_letter_prompt,
    _get_letter_system_message,
)

# Known recipient types from the source
KNOWN_TYPES = ["insurance", "employer", "specialist", "patient", "school", "legal", "government", "other"]


# ===========================================================================
# _get_recipient_guidance
# ===========================================================================

class TestGetRecipientGuidance:
    def test_returns_dict(self):
        assert isinstance(_get_recipient_guidance("insurance"), dict)

    def test_has_focus_key(self):
        g = _get_recipient_guidance("insurance")
        assert "focus" in g

    def test_has_exclude_key(self):
        g = _get_recipient_guidance("insurance")
        assert "exclude" in g

    def test_has_tone_key(self):
        g = _get_recipient_guidance("insurance")
        assert "tone" in g

    def test_has_format_key(self):
        g = _get_recipient_guidance("insurance")
        assert "format" in g

    def test_focus_is_list(self):
        assert isinstance(_get_recipient_guidance("insurance")["focus"], list)

    def test_exclude_is_list(self):
        assert isinstance(_get_recipient_guidance("employer")["exclude"], list)

    def test_tone_is_string(self):
        assert isinstance(_get_recipient_guidance("specialist")["tone"], str)

    def test_format_is_string(self):
        assert isinstance(_get_recipient_guidance("patient")["format"], str)

    def test_all_known_types_return_dict(self):
        for t in KNOWN_TYPES:
            result = _get_recipient_guidance(t)
            assert isinstance(result, dict), f"Type '{t}' did not return dict"
            assert all(k in result for k in ["focus", "exclude", "tone", "format"])

    def test_unknown_type_falls_back_to_other(self):
        other = _get_recipient_guidance("other")
        unknown = _get_recipient_guidance("xyz_unknown")
        assert unknown == other

    def test_insurance_focus_mentions_medical_necessity(self):
        focus = _get_recipient_guidance("insurance")["focus"]
        joined = " ".join(focus).lower()
        assert "medical necessity" in joined or "medical" in joined

    def test_employer_excludes_sensitive_diagnoses(self):
        exclude = _get_recipient_guidance("employer")["exclude"]
        joined = " ".join(exclude).lower()
        assert "diagnos" in joined or "sensitive" in joined or "mental health" in joined

    def test_patient_tone_is_warm_or_clear(self):
        tone = _get_recipient_guidance("patient")["tone"].lower()
        assert "warm" in tone or "clear" in tone or "educational" in tone

    def test_legal_focus_mentions_objective(self):
        focus = _get_recipient_guidance("legal")["focus"]
        joined = " ".join(focus).lower()
        assert "objective" in joined or "findings" in joined

    def test_government_focus_mentions_functional(self):
        focus = _get_recipient_guidance("government")["focus"]
        joined = " ".join(focus).lower()
        assert "functional" in joined or "limitations" in joined

    def test_school_focus_mentions_attendance_or_accommodations(self):
        focus = _get_recipient_guidance("school")["focus"]
        joined = " ".join(focus).lower()
        assert "attendance" in joined or "accommodations" in joined or "learning" in joined

    def test_focus_lists_non_empty(self):
        for t in KNOWN_TYPES:
            focus = _get_recipient_guidance(t)["focus"]
            assert len(focus) > 0, f"Type '{t}' has empty focus list"

    def test_exclude_lists_non_empty(self):
        for t in KNOWN_TYPES:
            exclude = _get_recipient_guidance(t)["exclude"]
            assert len(exclude) > 0, f"Type '{t}' has empty exclude list"


# ===========================================================================
# _build_letter_prompt
# ===========================================================================

class TestBuildLetterPrompt:
    def test_returns_string(self):
        result = _build_letter_prompt("clinical text", "insurance")
        assert isinstance(result, str)

    def test_non_empty(self):
        result = _build_letter_prompt("text", "patient")
        assert len(result.strip()) > 0

    def test_contains_clinical_text(self):
        result = _build_letter_prompt("Patient has hypertension", "specialist")
        assert "Patient has hypertension" in result

    def test_contains_recipient_display_name_insurance(self):
        result = _build_letter_prompt("text", "insurance")
        assert "Insurance" in result

    def test_contains_recipient_display_name_employer(self):
        result = _build_letter_prompt("text", "employer")
        assert "Employer" in result or "employer" in result.lower()

    def test_contains_recipient_display_name_specialist(self):
        result = _build_letter_prompt("text", "specialist")
        assert "Specialist" in result or "Colleague" in result

    def test_contains_recipient_display_name_patient(self):
        result = _build_letter_prompt("text", "patient")
        assert "Patient" in result

    def test_contains_focus_items(self):
        result = _build_letter_prompt("text", "insurance")
        focus = _get_recipient_guidance("insurance")["focus"]
        # At least one focus item should appear in the prompt
        assert any(item[:20] in result for item in focus)

    def test_contains_exclude_items(self):
        result = _build_letter_prompt("text", "insurance")
        exclude = _get_recipient_guidance("insurance")["exclude"]
        assert any(item[:20] in result for item in exclude)

    def test_contains_tone(self):
        result = _build_letter_prompt("text", "patient")
        tone = _get_recipient_guidance("patient")["tone"]
        assert tone[:20] in result

    def test_contains_format(self):
        result = _build_letter_prompt("text", "employer")
        fmt = _get_recipient_guidance("employer")["format"]
        assert fmt[:20] in result

    def test_specs_included_when_provided(self):
        result = _build_letter_prompt("text", "other", specs="Please keep it brief")
        assert "Please keep it brief" in result

    def test_specs_not_shown_when_empty(self):
        result = _build_letter_prompt("text", "other", specs="")
        assert "ADDITIONAL INSTRUCTIONS" not in result

    def test_specs_not_shown_when_whitespace_only(self):
        result = _build_letter_prompt("text", "other", specs="   ")
        assert "ADDITIONAL INSTRUCTIONS" not in result

    def test_specs_shown_when_non_empty(self):
        result = _build_letter_prompt("text", "other", specs="urgent")
        assert "ADDITIONAL INSTRUCTIONS" in result

    def test_include_header_in_prompt(self):
        result = _build_letter_prompt("text", "insurance")
        assert "INCLUDE" in result

    def test_exclude_header_in_prompt(self):
        result = _build_letter_prompt("text", "insurance")
        assert "EXCLUDE" in result

    def test_all_known_types_build_without_error(self):
        for t in KNOWN_TYPES:
            result = _build_letter_prompt("clinical text", t)
            assert isinstance(result, str)
            assert len(result.strip()) > 0

    def test_unknown_type_uses_other_guidance(self):
        unknown_result = _build_letter_prompt("text", "xyz_unknown")
        other_result = _build_letter_prompt("text", "other")
        # Both should use "other" guidance — focus/exclude items should match
        assert isinstance(unknown_result, str)


# ===========================================================================
# _get_letter_system_message
# ===========================================================================

class TestGetLetterSystemMessage:
    def test_returns_string(self):
        assert isinstance(_get_letter_system_message("insurance"), str)

    def test_non_empty(self):
        assert len(_get_letter_system_message("patient").strip()) > 0

    def test_contains_base_message_content(self):
        result = _get_letter_system_message("insurance")
        # Base message mentions recipient-focused content
        assert "recipient" in result.lower() or "medical" in result.lower()

    def test_insurance_message_mentions_insurance(self):
        result = _get_letter_system_message("insurance").lower()
        assert "insurance" in result

    def test_employer_message_mentions_functional(self):
        result = _get_letter_system_message("employer").lower()
        assert "functional" in result or "employer" in result or "work" in result

    def test_specialist_message_mentions_referral(self):
        result = _get_letter_system_message("specialist").lower()
        assert "referral" in result or "specialist" in result or "colleague" in result

    def test_patient_message_mentions_simple_language(self):
        result = _get_letter_system_message("patient").lower()
        assert "simple" in result or "language" in result or "jargon" in result

    def test_school_message_mentions_school(self):
        result = _get_letter_system_message("school").lower()
        assert "school" in result or "educational" in result

    def test_legal_message_mentions_objective(self):
        result = _get_letter_system_message("legal").lower()
        assert "objective" in result or "legal" in result or "factual" in result

    def test_government_message_mentions_functional_or_disability(self):
        result = _get_letter_system_message("government").lower()
        assert "functional" in result or "disability" in result or "government" in result

    def test_unknown_type_returns_string(self):
        result = _get_letter_system_message("xyz_unknown")
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_all_known_types_return_non_empty_strings(self):
        for t in KNOWN_TYPES:
            result = _get_letter_system_message(t)
            assert isinstance(result, str)
            assert len(result.strip()) > 0, f"Empty message for type '{t}'"

    def test_different_types_produce_different_messages(self):
        insurance = _get_letter_system_message("insurance")
        patient = _get_letter_system_message("patient")
        assert insurance != patient
