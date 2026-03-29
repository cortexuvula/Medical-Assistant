"""Tests for ComplianceAgent pure-logic methods."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest

from ai.agents.compliance import ComplianceAgent, DISCLAIMER


def _make_agent():
    return ComplianceAgent(ai_caller=MagicMock())


def _make_finding(status, finding="", guideline_reference="", recommendation="", citation_verified=False):
    """Create a finding as SimpleNamespace (works regardless of MODELS_AVAILABLE)."""
    return SimpleNamespace(
        status=status,
        finding=finding,
        guideline_reference=guideline_reference,
        recommendation=recommendation,
        citation_verified=citation_verified,
    )


def _make_condition(condition_name, findings, status="REVIEW", score=0.0, guidelines_matched=0):
    """Create a condition as SimpleNamespace."""
    return SimpleNamespace(
        condition=condition_name,
        findings=findings,
        status=status,
        score=score,
        guidelines_matched=guidelines_matched,
    )


def _make_result(conditions=None, overall_score=0.0, has_sufficient_data=False,
                 guidelines_searched=0):
    """Create a result as SimpleNamespace."""
    return SimpleNamespace(
        conditions=conditions or [],
        overall_score=overall_score,
        has_sufficient_data=has_sufficient_data,
        guidelines_searched=guidelines_searched,
        disclaimer=DISCLAIMER,
    )


# ---------------------------------------------------------------------------
# TestVerifyCitation
# ---------------------------------------------------------------------------

class TestVerifyCitation:
    """Tests for ComplianceAgent._verify_citation."""

    def setup_method(self):
        self.agent = _make_agent()

    def test_empty_reference_text_returns_false(self):
        result = self.agent._verify_citation("", ["some guideline text with words"])
        assert result is False

    def test_empty_string_reference_returns_false(self):
        result = self.agent._verify_citation("", ["guideline"])
        assert result is False

    def test_empty_guideline_texts_list_returns_false(self):
        result = self.agent._verify_citation("some reference text here", [])
        assert result is False

    def test_short_reference_under_10_chars_returns_false(self):
        result = self.agent._verify_citation("abc", ["abc is mentioned here in the guideline"])
        assert result is False

    def test_short_reference_exactly_9_chars_returns_false(self):
        result = self.agent._verify_citation("abcdefghi", ["abcdefghi mentioned in guideline text"])
        assert result is False

    def test_good_match_above_threshold_returns_true(self):
        # reference has 5 words > 3 chars, 3 appear in guideline => 3/5 = 0.6 >= 0.4
        reference = "aspirin therapy recommended blood pressure"
        guideline = "aspirin therapy recommended for cardiovascular disease"
        result = self.agent._verify_citation(reference, [guideline])
        assert result is True

    def test_partial_match_exactly_40_percent_returns_true(self):
        # 2 of 5 words match => 0.4 >= 0.4 → True
        reference = "aspirin therapy omega delta epsilon"
        guideline = "aspirin therapy should be considered for patients"
        result = self.agent._verify_citation(reference, [guideline])
        assert result is True

    def test_below_threshold_returns_false(self):
        # 1 of 5 words match => 0.2 < 0.4 → False
        reference = "aspirin zeta omega delta epsilon"
        guideline = "aspirin is mentioned once here"
        result = self.agent._verify_citation(reference, [guideline])
        assert result is False

    def test_all_reference_words_in_guideline_returns_true(self):
        reference = "beta blockers recommended hypertension"
        guideline = "beta blockers are recommended for hypertension management"
        result = self.agent._verify_citation(reference, [guideline])
        assert result is True

    def test_none_of_reference_words_in_guideline_returns_false(self):
        reference = "aspirin therapy recommended patients treatment"
        guideline = "completely unrelated content about surgery procedures"
        result = self.agent._verify_citation(reference, [guideline])
        assert result is False

    def test_case_insensitive_matching_returns_true(self):
        reference = "ASPIRIN therapy RECOMMENDED"
        guideline = "aspirin therapy recommended for patients"
        result = self.agent._verify_citation(reference, [guideline])
        assert result is True

    def test_short_words_not_counted_as_ref_words(self):
        # Only words with len > 3 are ref_words
        # "the", "is", "for", "and" (all <= 3 chars) don't count
        reference = "aspirin therapy recommended blood pressure"
        guideline = "aspirin therapy recommended for the management of blood pressure"
        result = self.agent._verify_citation(reference, [guideline])
        assert result is True

    def test_reference_with_only_short_words_returns_false(self):
        # All words <= 3 chars → ref_words is empty → False
        # "the"=3, "and"=3, "for"=3, "all"=3, "is"=2, "it"=2, "to"=2
        reference = "the and for all is it to"
        guideline = "the and for all is it to"
        result = self.agent._verify_citation(reference, [guideline])
        assert result is False

    def test_multiple_guideline_texts_match_in_second_returns_true(self):
        reference = "aspirin therapy recommended blood pressure management"
        guideline1 = "completely unrelated content about surgery"
        guideline2 = "aspirin therapy recommended for blood pressure management"
        result = self.agent._verify_citation(reference, [guideline1, guideline2])
        assert result is True

    def test_multiple_guideline_texts_no_match_returns_false(self):
        reference = "aspirin therapy recommended blood pressure management"
        guideline1 = "completely unrelated surgery content here"
        guideline2 = "another unrelated section about imaging studies"
        result = self.agent._verify_citation(reference, [guideline1, guideline2])
        assert result is False

    def test_reference_length_exactly_10_chars_not_rejected(self):
        # "1234567890" is 10 chars, len(ref_lower) is 10, not < 10, passes check
        # It is one word of length 10 > 3, so ref_words = ["1234567890"]
        reference = "1234567890"
        guideline = "1234567890 some guideline text"
        result = self.agent._verify_citation(reference, [guideline])
        assert result is True

    def test_reference_length_9_chars_returns_false(self):
        reference = "123456789"  # 9 chars → < 10 → False
        guideline = "123456789 mentioned in guideline text"
        result = self.agent._verify_citation(reference, [guideline])
        assert result is False


# ---------------------------------------------------------------------------
# TestBuildConditionPrompt
# ---------------------------------------------------------------------------

class TestBuildConditionPrompt:
    """Tests for ComplianceAgent._build_condition_prompt."""

    def setup_method(self):
        self.agent = _make_agent()
        self.soap_note = "S: Patient complains of chest pain.\nO: BP 140/90.\nA: Hypertension.\nP: Lisinopril 10mg."
        self.extracted_conditions = [
            {"condition": "Hypertension", "medications": ["Lisinopril"]},
        ]
        self.guidelines_by_condition = {}

    def test_returns_string(self):
        result = self.agent._build_condition_prompt(
            self.soap_note, self.extracted_conditions, self.guidelines_by_condition
        )
        assert isinstance(result, str)

    def test_contains_analyze_treatment_decisions(self):
        result = self.agent._build_condition_prompt(
            self.soap_note, self.extracted_conditions, self.guidelines_by_condition
        )
        assert "Analyze whether the treatment decisions" in result

    def test_contains_clinical_guidelines_by_condition_header(self):
        result = self.agent._build_condition_prompt(
            self.soap_note, self.extracted_conditions, self.guidelines_by_condition
        )
        assert "# CLINICAL GUIDELINES BY CONDITION" in result

    def test_contains_soap_note_text(self):
        result = self.agent._build_condition_prompt(
            self.soap_note, self.extracted_conditions, self.guidelines_by_condition
        )
        assert self.soap_note in result

    def test_no_additional_context_label_absent(self):
        result = self.agent._build_condition_prompt(
            self.soap_note, self.extracted_conditions, self.guidelines_by_condition,
            additional_context=None
        )
        assert "Additional Context:" not in result

    def test_additional_context_present_when_provided(self):
        result = self.agent._build_condition_prompt(
            self.soap_note, self.extracted_conditions, self.guidelines_by_condition,
            additional_context="some context"
        )
        assert "Additional Context:" in result

    def test_additional_context_value_included(self):
        result = self.agent._build_condition_prompt(
            self.soap_note, self.extracted_conditions, self.guidelines_by_condition,
            additional_context="some context"
        )
        assert "some context" in result

    def test_condition_name_appears_in_result(self):
        result = self.agent._build_condition_prompt(
            self.soap_note, self.extracted_conditions, self.guidelines_by_condition
        )
        assert "Hypertension" in result

    def test_no_matching_guidelines_message_when_empty(self):
        result = self.agent._build_condition_prompt(
            self.soap_note, self.extracted_conditions, {}
        )
        assert "No matching guidelines found" in result

    def test_medication_list_included_when_non_empty(self):
        result = self.agent._build_condition_prompt(
            self.soap_note, self.extracted_conditions, self.guidelines_by_condition
        )
        assert "Lisinopril" in result

    def test_no_medication_label_when_empty(self):
        conditions_no_meds = [{"condition": "Hypertension", "medications": []}]
        result = self.agent._build_condition_prompt(
            self.soap_note, conditions_no_meds, self.guidelines_by_condition
        )
        assert "Current medications:" not in result

    def test_guidelines_count_shown(self):
        guideline = SimpleNamespace(
            guideline_source="ACC/AHA",
            guideline_title="Hypertension Guidelines",
            guideline_version="2023",
            recommendation_class="I",
            evidence_level="A",
            chunk_text="Beta-blockers recommended for stage 2 hypertension"
        )
        guidelines_by_condition = {"Hypertension": [guideline]}
        result = self.agent._build_condition_prompt(
            self.soap_note, self.extracted_conditions, guidelines_by_condition
        )
        assert "Relevant guidelines (1 found):" in result

    def test_guideline_source_included(self):
        guideline = SimpleNamespace(
            guideline_source="ACC/AHA",
            guideline_title="Hypertension Guidelines",
            guideline_version="2023",
            recommendation_class="I",
            evidence_level="A",
            chunk_text="Beta-blockers recommended for stage 2 hypertension"
        )
        guidelines_by_condition = {"Hypertension": [guideline]}
        result = self.agent._build_condition_prompt(
            self.soap_note, self.extracted_conditions, guidelines_by_condition
        )
        assert "ACC/AHA" in result

    def test_guideline_title_included(self):
        guideline = SimpleNamespace(
            guideline_source="ACC/AHA",
            guideline_title="Hypertension Guidelines",
            guideline_version="2023",
            recommendation_class="I",
            evidence_level="A",
            chunk_text="Beta-blockers recommended for stage 2 hypertension"
        )
        guidelines_by_condition = {"Hypertension": [guideline]}
        result = self.agent._build_condition_prompt(
            self.soap_note, self.extracted_conditions, guidelines_by_condition
        )
        assert "Hypertension Guidelines" in result

    def test_guideline_chunk_text_included(self):
        guideline = SimpleNamespace(
            guideline_source="ACC/AHA",
            guideline_title="Hypertension Guidelines",
            guideline_version="2023",
            recommendation_class="I",
            evidence_level="A",
            chunk_text="Beta-blockers recommended for stage 2 hypertension"
        )
        guidelines_by_condition = {"Hypertension": [guideline]}
        result = self.agent._build_condition_prompt(
            self.soap_note, self.extracted_conditions, guidelines_by_condition
        )
        assert "Beta-blockers recommended for stage 2 hypertension" in result

    def test_multiple_conditions_appear_in_result(self):
        conditions = [
            {"condition": "Hypertension", "medications": ["Lisinopril"]},
            {"condition": "Diabetes", "medications": ["Metformin"]},
        ]
        result = self.agent._build_condition_prompt(
            self.soap_note, conditions, {}
        )
        assert "Hypertension" in result
        assert "Diabetes" in result

    def test_guideline_version_shown_when_present(self):
        guideline = SimpleNamespace(
            guideline_source="ACC/AHA",
            guideline_title="Hypertension Guidelines",
            guideline_version="2023",
            recommendation_class="I",
            evidence_level="A",
            chunk_text="some guideline text"
        )
        guidelines_by_condition = {"Hypertension": [guideline]}
        result = self.agent._build_condition_prompt(
            self.soap_note, self.extracted_conditions, guidelines_by_condition
        )
        assert "2023" in result

    def test_multiple_guidelines_count_shown(self):
        g1 = SimpleNamespace(
            guideline_source="ACC/AHA", guideline_title="Title1",
            guideline_version="2023", recommendation_class="I", evidence_level="A",
            chunk_text="guideline text one"
        )
        g2 = SimpleNamespace(
            guideline_source="JNC8", guideline_title="Title2",
            guideline_version="2023", recommendation_class="II", evidence_level="B",
            chunk_text="guideline text two"
        )
        guidelines_by_condition = {"Hypertension": [g1, g2]}
        result = self.agent._build_condition_prompt(
            self.soap_note, self.extracted_conditions, guidelines_by_condition
        )
        assert "Relevant guidelines (2 found):" in result

    def test_empty_conditions_list_still_returns_string(self):
        result = self.agent._build_condition_prompt(
            self.soap_note, [], {}
        )
        assert isinstance(result, str)
        assert "# CLINICAL GUIDELINES BY CONDITION" in result


# ---------------------------------------------------------------------------
# TestComputeScores
# ---------------------------------------------------------------------------

class TestComputeScores:
    """Tests for ComplianceAgent._compute_scores."""

    def setup_method(self):
        self.agent = _make_agent()

    def test_empty_conditions_overall_score_zero(self):
        result = _make_result(conditions=[], overall_score=0.0)
        self.agent._compute_scores(result)
        assert result.overall_score == 0.0

    def test_all_aligned_score_1_and_status_aligned(self):
        findings = [
            _make_finding("ALIGNED"),
            _make_finding("ALIGNED"),
            _make_finding("ALIGNED"),
        ]
        cond = _make_condition("Hypertension", findings)
        result = _make_result(conditions=[cond])
        self.agent._compute_scores(result)
        assert cond.score == 1.0
        assert cond.status == "ALIGNED"

    def test_all_gap_score_zero_and_status_gap(self):
        findings = [_make_finding("GAP"), _make_finding("GAP")]
        cond = _make_condition("Hypertension", findings)
        result = _make_result(conditions=[cond])
        self.agent._compute_scores(result)
        assert cond.score == 0.0
        assert cond.status == "GAP"

    def test_all_review_score_zero_and_status_review(self):
        # 0 / (0 + 0 + 2*0.5) = 0/1 = 0.0
        findings = [_make_finding("REVIEW"), _make_finding("REVIEW")]
        cond = _make_condition("Hypertension", findings)
        result = _make_result(conditions=[cond])
        self.agent._compute_scores(result)
        assert cond.score == 0.0
        assert cond.status == "REVIEW"

    def test_mixed_aligned_and_gap_score_half_status_gap(self):
        # 1 / (1 + 1 + 0) = 0.5
        findings = [_make_finding("ALIGNED"), _make_finding("GAP")]
        cond = _make_condition("Hypertension", findings)
        result = _make_result(conditions=[cond])
        self.agent._compute_scores(result)
        assert cond.score == 0.5
        assert cond.status == "GAP"

    def test_mixed_aligned_and_review_score_and_status_review(self):
        # 1 / (1 + 0 + 1*0.5) = 1/1.5 = 0.67
        findings = [_make_finding("ALIGNED"), _make_finding("REVIEW")]
        cond = _make_condition("Hypertension", findings)
        result = _make_result(conditions=[cond])
        self.agent._compute_scores(result)
        assert cond.score == round(1 / 1.5, 2)
        assert cond.status == "REVIEW"

    def test_no_findings_score_zero_status_review(self):
        cond = _make_condition("Hypertension", [])
        result = _make_result(conditions=[cond])
        self.agent._compute_scores(result)
        assert cond.score == 0.0
        assert cond.status == "REVIEW"

    def test_two_conditions_all_aligned_overall_score_1(self):
        findings1 = [_make_finding("ALIGNED"), _make_finding("ALIGNED")]
        findings2 = [_make_finding("ALIGNED"), _make_finding("ALIGNED")]
        cond1 = _make_condition("Hypertension", findings1)
        cond2 = _make_condition("Diabetes", findings2)
        result = _make_result(conditions=[cond1, cond2])
        self.agent._compute_scores(result)
        assert result.overall_score == 1.0

    def test_overall_score_mixed_across_conditions(self):
        # cond1: 2 ALIGNED, cond2: 1 ALIGNED + 1 GAP
        # total: 3 aligned, 1 gap, 0 review
        # overall = 3 / (3 + 1 + 0) = 0.75
        findings1 = [_make_finding("ALIGNED"), _make_finding("ALIGNED")]
        findings2 = [_make_finding("ALIGNED"), _make_finding("GAP")]
        cond1 = _make_condition("Hypertension", findings1)
        cond2 = _make_condition("Diabetes", findings2)
        result = _make_result(conditions=[cond1, cond2])
        self.agent._compute_scores(result)
        assert result.overall_score == 0.75

    def test_overall_score_updated_in_place(self):
        findings = [_make_finding("ALIGNED")]
        cond = _make_condition("Hypertension", findings)
        result = _make_result(conditions=[cond], overall_score=0.0)
        self.agent._compute_scores(result)
        assert result.overall_score == 1.0

    def test_condition_score_updated_in_place(self):
        findings = [_make_finding("ALIGNED"), _make_finding("ALIGNED")]
        cond = _make_condition("Hypertension", findings, score=0.0)
        result = _make_result(conditions=[cond])
        self.agent._compute_scores(result)
        assert cond.score == 1.0

    def test_condition_status_updated_in_place(self):
        findings = [_make_finding("GAP")]
        cond = _make_condition("Hypertension", findings, status="REVIEW")
        result = _make_result(conditions=[cond])
        self.agent._compute_scores(result)
        assert cond.status == "GAP"

    def test_score_rounded_to_2_decimal_places(self):
        # 1 aligned, 1 review: 1 / (1 + 0.5) = 0.666... → 0.67
        findings = [_make_finding("ALIGNED"), _make_finding("REVIEW")]
        cond = _make_condition("Hypertension", findings)
        result = _make_result(conditions=[cond])
        self.agent._compute_scores(result)
        assert cond.score == 0.67

    def test_gap_takes_priority_over_review_for_status(self):
        findings = [_make_finding("ALIGNED"), _make_finding("REVIEW"), _make_finding("GAP")]
        cond = _make_condition("Hypertension", findings)
        result = _make_result(conditions=[cond])
        self.agent._compute_scores(result)
        assert cond.status == "GAP"

    def test_review_takes_priority_over_aligned_for_status(self):
        findings = [_make_finding("ALIGNED"), _make_finding("ALIGNED"), _make_finding("REVIEW")]
        cond = _make_condition("Hypertension", findings)
        result = _make_result(conditions=[cond])
        self.agent._compute_scores(result)
        assert cond.status == "REVIEW"

    def test_single_aligned_finding_status_aligned(self):
        findings = [_make_finding("ALIGNED")]
        cond = _make_condition("Hypertension", findings)
        result = _make_result(conditions=[cond])
        self.agent._compute_scores(result)
        assert cond.status == "ALIGNED"
        assert cond.score == 1.0

    def test_overall_score_zero_when_all_gaps(self):
        findings = [_make_finding("GAP"), _make_finding("GAP")]
        cond = _make_condition("Hypertension", findings)
        result = _make_result(conditions=[cond])
        self.agent._compute_scores(result)
        assert result.overall_score == 0.0

    def test_dict_findings_also_work(self):
        # _compute_scores uses hasattr(f, 'status') or f['status']
        dict_finding = {
            "status": "ALIGNED", "finding": "test",
            "guideline_reference": "", "recommendation": "", "citation_verified": False
        }
        cond = SimpleNamespace(
            condition="Hypertension", findings=[dict_finding],
            score=0.0, status="REVIEW", guidelines_matched=0
        )
        result = _make_result(conditions=[cond])
        self.agent._compute_scores(result)
        assert cond.score == 1.0
        assert cond.status == "ALIGNED"

    def test_three_conditions_varied_findings_overall_score(self):
        # cond1: 1 ALIGNED → 1 aligned
        # cond2: 1 GAP → 1 gap
        # cond3: 1 REVIEW → 0.5 in denominator
        # total: 1 aligned, 1 gap, 1 review
        # overall = 1 / (1 + 1 + 0.5) = 1/2.5 = 0.4
        cond1 = _make_condition("A", [_make_finding("ALIGNED")])
        cond2 = _make_condition("B", [_make_finding("GAP")])
        cond3 = _make_condition("C", [_make_finding("REVIEW")])
        result = _make_result(conditions=[cond1, cond2, cond3])
        self.agent._compute_scores(result)
        assert result.overall_score == 0.4


# ---------------------------------------------------------------------------
# TestFormatReadable
# ---------------------------------------------------------------------------

class TestFormatReadable:
    """Tests for ComplianceAgent._format_readable."""

    def setup_method(self):
        self.agent = _make_agent()

    def test_returns_string(self):
        result = _make_result()
        output = self.agent._format_readable(result)
        assert isinstance(output, str)

    def test_contains_compliance_analysis_summary(self):
        result = _make_result()
        output = self.agent._format_readable(result)
        assert "COMPLIANCE ANALYSIS SUMMARY" in output

    def test_score_75_shows_75_percent(self):
        result = _make_result(overall_score=0.75, has_sufficient_data=True)
        output = self.agent._format_readable(result)
        assert "75%" in output

    def test_score_0_shows_0_percent(self):
        result = _make_result(overall_score=0.0)
        output = self.agent._format_readable(result)
        assert "0%" in output

    def test_insufficient_data_false_shows_insufficient_data(self):
        result = _make_result(has_sufficient_data=False)
        output = self.agent._format_readable(result)
        assert "INSUFFICIENT DATA" in output

    def test_insufficient_data_false_shows_disclaimer(self):
        result = _make_result(has_sufficient_data=False)
        output = self.agent._format_readable(result)
        assert DISCLAIMER in output

    def test_sufficient_data_true_no_insufficient_data_text(self):
        findings = [_make_finding("ALIGNED", finding="Treatment aligned")]
        cond = _make_condition("Hypertension", findings, status="ALIGNED", score=1.0)
        result = _make_result(conditions=[cond], has_sufficient_data=True, overall_score=1.0)
        output = self.agent._format_readable(result)
        assert "INSUFFICIENT DATA" not in output

    def test_aligned_condition_shows_checkmark(self):
        findings = [_make_finding("ALIGNED", finding="Treatment aligned")]
        cond = _make_condition("Hypertension", findings, status="ALIGNED", score=1.0)
        result = _make_result(conditions=[cond], has_sufficient_data=True)
        output = self.agent._format_readable(result)
        assert "\u2713" in output  # ✓

    def test_gap_condition_shows_x_mark(self):
        findings = [_make_finding("GAP", finding="Treatment gap identified")]
        cond = _make_condition("Hypertension", findings, status="GAP", score=0.0)
        result = _make_result(conditions=[cond], has_sufficient_data=True)
        output = self.agent._format_readable(result)
        assert "\u2717" in output  # ✗

    def test_review_condition_shows_question_mark(self):
        findings = [_make_finding("REVIEW", finding="Needs review")]
        cond = _make_condition("Hypertension", findings, status="REVIEW", score=0.0)
        result = _make_result(conditions=[cond], has_sufficient_data=True)
        output = self.agent._format_readable(result)
        assert "?" in output

    def test_detailed_findings_section_when_sufficient_data(self):
        findings = [_make_finding("ALIGNED", finding="Treatment aligned")]
        cond = _make_condition("Hypertension", findings, status="ALIGNED", score=1.0)
        result = _make_result(conditions=[cond], has_sufficient_data=True)
        output = self.agent._format_readable(result)
        assert "DETAILED FINDINGS" in output

    def test_finding_status_shown_in_bracket_format(self):
        findings = [_make_finding("ALIGNED", finding="Treatment aligned")]
        cond = _make_condition("Hypertension", findings, status="ALIGNED", score=1.0)
        result = _make_result(conditions=[cond], has_sufficient_data=True)
        output = self.agent._format_readable(result)
        assert "[ALIGNED]" in output

    def test_guideline_reference_shown_when_non_empty(self):
        findings = [_make_finding("ALIGNED", finding="Treatment aligned",
                                  guideline_reference="ACC/AHA recommends ACE inhibitors")]
        cond = _make_condition("Hypertension", findings, status="ALIGNED", score=1.0)
        result = _make_result(conditions=[cond], has_sufficient_data=True)
        output = self.agent._format_readable(result)
        assert "ACC/AHA recommends ACE inhibitors" in output

    def test_recommendation_shown_when_non_empty(self):
        findings = [_make_finding("GAP", finding="Missing beta-blocker",
                                  recommendation="Consider adding beta-blocker")]
        cond = _make_condition("Hypertension", findings, status="GAP", score=0.0)
        result = _make_result(conditions=[cond], has_sufficient_data=True)
        output = self.agent._format_readable(result)
        assert "Consider adding beta-blocker" in output

    def test_disclaimer_appended_to_output(self):
        findings = [_make_finding("ALIGNED", finding="Treatment aligned")]
        cond = _make_condition("Hypertension", findings, status="ALIGNED", score=1.0)
        result = _make_result(conditions=[cond], has_sufficient_data=True)
        output = self.agent._format_readable(result)
        assert DISCLAIMER in output

    def test_guidelines_searched_count_shown(self):
        result = _make_result(guidelines_searched=10)
        output = self.agent._format_readable(result)
        assert "10" in output

    def test_guidelines_searched_zero_shown(self):
        result = _make_result(guidelines_searched=0)
        output = self.agent._format_readable(result)
        assert "Guidelines Searched: 0" in output

    def test_condition_name_in_detailed_findings(self):
        findings = [_make_finding("ALIGNED", finding="Treatment aligned")]
        cond = _make_condition("Type 2 Diabetes", findings, status="ALIGNED", score=1.0)
        result = _make_result(conditions=[cond], has_sufficient_data=True)
        output = self.agent._format_readable(result)
        assert "Type 2 Diabetes" in output

    def test_gap_status_label_shows_gap_identified(self):
        findings = [_make_finding("GAP", finding="Treatment gap")]
        cond = _make_condition("Hypertension", findings, status="GAP", score=0.0)
        result = _make_result(conditions=[cond], has_sufficient_data=True)
        output = self.agent._format_readable(result)
        assert "GAP IDENTIFIED" in output

    def test_review_status_label_shows_needs_review(self):
        findings = [_make_finding("REVIEW", finding="Needs review")]
        cond = _make_condition("Hypertension", findings, status="REVIEW", score=0.0)
        result = _make_result(conditions=[cond], has_sufficient_data=True)
        output = self.agent._format_readable(result)
        assert "NEEDS REVIEW" in output

    def test_aligned_status_label_shows_aligned(self):
        findings = [_make_finding("ALIGNED", finding="Treatment aligned")]
        cond = _make_condition("Hypertension", findings, status="ALIGNED", score=1.0)
        result = _make_result(conditions=[cond], has_sufficient_data=True)
        output = self.agent._format_readable(result)
        assert "[ALIGNED]" in output

    def test_conditions_count_shown(self):
        findings = [_make_finding("ALIGNED")]
        cond1 = _make_condition("Hypertension", findings, status="ALIGNED")
        cond2 = _make_condition("Diabetes", findings, status="ALIGNED")
        result = _make_result(conditions=[cond1, cond2], has_sufficient_data=True)
        output = self.agent._format_readable(result)
        assert "Conditions Analyzed: 2" in output

    def test_finding_text_shown_in_output(self):
        findings = [_make_finding("ALIGNED", finding="Beta-blockers prescribed correctly")]
        cond = _make_condition("Hypertension", findings, status="ALIGNED", score=1.0)
        result = _make_result(conditions=[cond], has_sufficient_data=True)
        output = self.agent._format_readable(result)
        assert "Beta-blockers prescribed correctly" in output

    def test_empty_guideline_reference_not_shown(self):
        findings = [_make_finding("ALIGNED", finding="Treatment aligned", guideline_reference="")]
        cond = _make_condition("Hypertension", findings, status="ALIGNED", score=1.0)
        result = _make_result(conditions=[cond], has_sufficient_data=True)
        output = self.agent._format_readable(result)
        assert "Guideline [" not in output

    def test_empty_recommendation_not_shown(self):
        findings = [_make_finding("ALIGNED", finding="Treatment aligned", recommendation="")]
        cond = _make_condition("Hypertension", findings, status="ALIGNED", score=1.0)
        result = _make_result(conditions=[cond], has_sufficient_data=True)
        output = self.agent._format_readable(result)
        assert "Recommendation:" not in output

    def test_overall_score_100_shows_100_percent(self):
        result = _make_result(overall_score=1.0, has_sufficient_data=True)
        output = self.agent._format_readable(result)
        assert "100%" in output

    def test_dict_findings_work_in_format_readable(self):
        # _format_readable supports both SimpleNamespace and dict findings
        dict_finding = {
            "status": "ALIGNED", "finding": "Treatment fine",
            "guideline_reference": "ACC guideline text",
            "recommendation": "", "citation_verified": True
        }
        cond = SimpleNamespace(
            condition="Hypertension", findings=[dict_finding],
            status="ALIGNED", score=1.0, guidelines_matched=1
        )
        result = _make_result(conditions=[cond], has_sufficient_data=True, overall_score=1.0)
        output = self.agent._format_readable(result)
        assert "Treatment fine" in output
        assert "[ALIGNED]" in output

    def test_gap_finding_shown_with_x_in_conditions_strip(self):
        findings = [_make_finding("GAP", finding="Gap found")]
        cond = _make_condition("Hypertension", findings, status="GAP", score=0.0)
        result = _make_result(conditions=[cond], has_sufficient_data=True)
        output = self.agent._format_readable(result)
        # Conditions strip line contains condition name + ✗
        assert "Hypertension \u2717" in output

    def test_aligned_finding_shown_with_check_in_conditions_strip(self):
        findings = [_make_finding("ALIGNED")]
        cond = _make_condition("Diabetes", findings, status="ALIGNED", score=1.0)
        result = _make_result(conditions=[cond], has_sufficient_data=True)
        output = self.agent._format_readable(result)
        assert "Diabetes \u2713" in output

    def test_review_finding_shown_with_question_in_conditions_strip(self):
        findings = [_make_finding("REVIEW")]
        cond = _make_condition("Asthma", findings, status="REVIEW", score=0.0)
        result = _make_result(conditions=[cond], has_sufficient_data=True)
        output = self.agent._format_readable(result)
        assert "Asthma ?" in output


# ---------------------------------------------------------------------------
# TestComplianceAgentDefaults
# ---------------------------------------------------------------------------

class TestComplianceAgentDefaults:
    """Tests for ComplianceAgent.DEFAULT_CONFIG values."""

    def test_default_config_name_is_compliance_agent(self):
        assert ComplianceAgent.DEFAULT_CONFIG.name == "ComplianceAgent"

    def test_default_config_temperature_is_0_2(self):
        assert ComplianceAgent.DEFAULT_CONFIG.temperature == 0.2
