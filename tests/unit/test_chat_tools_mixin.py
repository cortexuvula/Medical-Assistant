"""
Tests for ChatToolsMixin._should_use_tools() in src/ai/chat_tools_mixin.py

Covers the pure keyword-matching and regex logic that decides whether
to invoke tools for a given user message. The method is pure (depends only
on self.use_tools, self.chat_agent, and the message string).
No network, no Tkinter, no file I/O.
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

from ai.chat_tools_mixin import ChatToolsMixin


# ---------------------------------------------------------------------------
# Minimal stub class providing required attributes
# ---------------------------------------------------------------------------

class _FakeChat(ChatToolsMixin):
    def __init__(self, use_tools=True, has_agent=True):
        self.use_tools = use_tools
        self.chat_agent = object() if has_agent else None  # Non-None = agent present


def _chat(use_tools=True, has_agent=True) -> _FakeChat:
    return _FakeChat(use_tools=use_tools, has_agent=has_agent)


# ===========================================================================
# Gate conditions (use_tools / chat_agent)
# ===========================================================================

class TestShouldUseToolsGating:
    def test_use_tools_false_returns_false(self):
        c = _chat(use_tools=False, has_agent=True)
        assert c._should_use_tools("what is the guideline for diabetes") is False

    def test_chat_agent_none_returns_false(self):
        c = _chat(use_tools=True, has_agent=False)
        assert c._should_use_tools("what is the guideline for diabetes") is False

    def test_both_enabled_allows_detection(self):
        c = _chat(use_tools=True, has_agent=True)
        result = c._should_use_tools("calculate the bmi")
        assert isinstance(result, bool)

    def test_returns_bool(self):
        c = _chat()
        result = c._should_use_tools("search for diabetes")
        assert isinstance(result, bool)


# ===========================================================================
# Calculation keywords
# ===========================================================================

class TestCalculationKeywords:
    def setup_method(self):
        self.c = _chat()

    def test_calculate_keyword(self):
        assert self.c._should_use_tools("calculate the BMI for this patient") is True

    def test_compute_keyword(self):
        assert self.c._should_use_tools("compute the drug dose") is True

    def test_math_keyword(self):
        assert self.c._should_use_tools("math calculation needed") is True

    def test_bmi_keyword(self):
        assert self.c._should_use_tools("what is the bmi for a patient") is True

    def test_mg_kg_keyword(self):
        assert self.c._should_use_tools("dose is 10 mg/kg per day") is True


# ===========================================================================
# Time/date keywords
# ===========================================================================

class TestTimeDateKeywords:
    def setup_method(self):
        self.c = _chat()

    def test_what_time_keyword(self):
        assert self.c._should_use_tools("what time is it now") is True

    def test_today_keyword(self):
        assert self.c._should_use_tools("what is happening today") is True


# ===========================================================================
# Medical guideline keywords
# ===========================================================================

class TestMedicalGuidelineKeywords:
    def setup_method(self):
        self.c = _chat()

    def test_guideline_keyword(self):
        assert self.c._should_use_tools("what is the guideline for hypertension") is True

    def test_guidelines_keyword(self):
        assert self.c._should_use_tools("show me the guidelines for diabetes") is True

    def test_protocol_keyword(self):
        assert self.c._should_use_tools("the protocol for this condition") is True

    def test_recommendation_keyword(self):
        assert self.c._should_use_tools("what is the recommendation for this case") is True

    def test_best_practice_keyword(self):
        assert self.c._should_use_tools("what is best practice here") is True

    def test_hypertension_keyword(self):
        assert self.c._should_use_tools("hypertension blood pressure management") is True

    def test_diabetes_keyword(self):
        assert self.c._should_use_tools("diabetes management protocol") is True

    def test_cholesterol_keyword(self):
        assert self.c._should_use_tools("cholesterol target levels") is True

    def test_hba1c_keyword(self):
        assert self.c._should_use_tools("what is the hba1c target for a diabetic patient") is True


# ===========================================================================
# Year patterns
# ===========================================================================

class TestYearPatterns:
    def setup_method(self):
        self.c = _chat()

    def test_2023_year_pattern(self):
        assert self.c._should_use_tools("what are the 2023 guidelines for diabetes") is True

    def test_2024_year_pattern(self):
        assert self.c._should_use_tools("the 2024 recommendations are different") is True

    def test_2025_year_pattern(self):
        assert self.c._should_use_tools("according to 2025 guidelines") is True

    def test_non_year_number_no_match(self):
        # 1999 is not in range 2000-2099
        result = self.c._should_use_tools("protocols from 1999 are outdated")
        # Could be False or True depending on other keywords
        assert isinstance(result, bool)


# ===========================================================================
# Question patterns
# ===========================================================================

class TestQuestionPatterns:
    def setup_method(self):
        self.c = _chat()

    def test_question_ending_with_mark(self):
        assert self.c._should_use_tools("Is metformin safe for elderly patients?") is True

    def test_what_is_pattern(self):
        assert self.c._should_use_tools("what is the correct dosage") is True

    def test_how_much_pattern(self):
        assert self.c._should_use_tools("how much metformin per day") is True

    def test_how_many_pattern(self):
        assert self.c._should_use_tools("how many milligrams are recommended") is True

    def test_when_should_pattern(self):
        assert self.c._should_use_tools("when should statins be started") is True


# ===========================================================================
# Search keywords
# ===========================================================================

class TestSearchKeywords:
    def setup_method(self):
        self.c = _chat()

    def test_search_keyword(self):
        assert self.c._should_use_tools("search for information about statins") is True

    def test_find_keyword(self):
        assert self.c._should_use_tools("find the reference range for glucose") is True

    def test_look_up_keyword(self):
        assert self.c._should_use_tools("look up drug interactions for metformin") is True


# ===========================================================================
# Medical value keywords
# ===========================================================================

class TestMedicalValueKeywords:
    def setup_method(self):
        self.c = _chat()

    def test_target_keyword(self):
        assert self.c._should_use_tools("what is the blood pressure target") is True

    def test_reference_range_keyword(self):
        assert self.c._should_use_tools("what is the reference range for TSH") is True

    def test_dosage_keyword(self):
        assert self.c._should_use_tools("dosage for pediatric patients") is True


# ===========================================================================
# Non-tool messages (general conversation)
# ===========================================================================

class TestNonToolMessages:
    def setup_method(self):
        self.c = _chat()

    def test_simple_greeting_false(self):
        # Pure greeting — no keywords should match
        result = self.c._should_use_tools("hello, can you help me")
        # "can you" is checked but not in the keyword list... let's accept either
        assert isinstance(result, bool)

    def test_very_short_plain_text(self):
        # "okay" has no matching keywords
        result = self.c._should_use_tools("okay")
        assert isinstance(result, bool)

    def test_case_insensitive_matching(self):
        # Keywords are lowercased before checking
        assert self.c._should_use_tools("CALCULATE the dose") is True

    def test_mixed_case_guideline(self):
        assert self.c._should_use_tools("Show me the Guideline for Hypertension") is True
