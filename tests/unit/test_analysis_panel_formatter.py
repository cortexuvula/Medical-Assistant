"""
Tests for src/ui/components/analysis_panel_formatter.py

Covers:
  - SeverityConfig dataclass
  - AnalysisPanelFormatter.SEVERITY_COLORS constant
  - AnalysisPanelFormatter.WARNING_COLORS constant
  - _is_section_header(line)
  - _detect_severity(line)
  - _detect_confidence_level(line)
  - _is_warning_line(line)
  - _detect_warning_type(line)
  - _is_red_flag(line)
  - _is_recommendation(line)
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ui.components.analysis_panel_formatter import AnalysisPanelFormatter, SeverityConfig


@pytest.fixture
def formatter():
    widget = MagicMock()
    return AnalysisPanelFormatter(widget)


# ---------------------------------------------------------------------------
# TestSeverityConfigDataclass
# ---------------------------------------------------------------------------

class TestSeverityConfigDataclass:
    """Tests for the SeverityConfig dataclass."""

    def test_required_fields_stored(self):
        cfg = SeverityConfig(background="#ff0000", foreground="white")
        assert cfg.background == "#ff0000"
        assert cfg.foreground == "white"

    def test_font_weight_default_is_bold(self):
        cfg = SeverityConfig(background="#000000", foreground="black")
        assert cfg.font_weight == "bold"

    def test_font_weight_can_be_overridden(self):
        cfg = SeverityConfig(background="#000000", foreground="black", font_weight="normal")
        assert cfg.font_weight == "normal"

    def test_instances_are_equal_with_same_values(self):
        cfg1 = SeverityConfig(background="#aabbcc", foreground="white")
        cfg2 = SeverityConfig(background="#aabbcc", foreground="white")
        assert cfg1 == cfg2

    def test_instances_differ_when_fields_differ(self):
        cfg1 = SeverityConfig(background="#aabbcc", foreground="white")
        cfg2 = SeverityConfig(background="#aabbcc", foreground="black")
        assert cfg1 != cfg2


# ---------------------------------------------------------------------------
# TestSeverityColorsConstant
# ---------------------------------------------------------------------------

class TestSeverityColorsConstant:
    """Tests for AnalysisPanelFormatter.SEVERITY_COLORS class attribute."""

    def test_has_exactly_seven_entries(self):
        assert len(AnalysisPanelFormatter.SEVERITY_COLORS) == 7

    def test_contains_all_expected_keys(self):
        expected_keys = {"contraindicated", "major", "moderate", "minor", "high", "medium", "low"}
        assert set(AnalysisPanelFormatter.SEVERITY_COLORS.keys()) == expected_keys

    def test_all_values_are_severity_config_instances(self):
        for key, value in AnalysisPanelFormatter.SEVERITY_COLORS.items():
            assert isinstance(value, SeverityConfig), f"Key '{key}' does not map to SeverityConfig"

    def test_contraindicated_is_red_with_white_text(self):
        cfg = AnalysisPanelFormatter.SEVERITY_COLORS["contraindicated"]
        assert cfg.background == "#dc3545"
        assert cfg.foreground == "white"

    def test_moderate_is_yellow_with_black_text(self):
        cfg = AnalysisPanelFormatter.SEVERITY_COLORS["moderate"]
        assert cfg.background == "#ffc107"
        assert cfg.foreground == "black"


# ---------------------------------------------------------------------------
# TestWarningColorsConstant
# ---------------------------------------------------------------------------

class TestWarningColorsConstant:
    """Tests for AnalysisPanelFormatter.WARNING_COLORS class attribute."""

    def test_has_exactly_five_entries(self):
        assert len(AnalysisPanelFormatter.WARNING_COLORS) == 5

    def test_contains_all_expected_keys(self):
        expected_keys = {"allergy", "renal", "hepatic", "red_flag", "general"}
        assert set(AnalysisPanelFormatter.WARNING_COLORS.keys()) == expected_keys

    def test_all_values_are_severity_config_instances(self):
        for key, value in AnalysisPanelFormatter.WARNING_COLORS.items():
            assert isinstance(value, SeverityConfig), f"Key '{key}' does not map to SeverityConfig"

    def test_allergy_is_red_with_white_text(self):
        cfg = AnalysisPanelFormatter.WARNING_COLORS["allergy"]
        assert cfg.background == "#dc3545"
        assert cfg.foreground == "white"


# ---------------------------------------------------------------------------
# TestIsSectionHeader
# ---------------------------------------------------------------------------

class TestIsSectionHeader:
    """Tests for AnalysisPanelFormatter._is_section_header(line)."""

    # --- colon-ending patterns ---

    def test_medications_with_colon(self, formatter):
        assert formatter._is_section_header("MEDICATIONS:") is True

    def test_medication_singular_with_colon(self, formatter):
        assert formatter._is_section_header("MEDICATION:") is True

    def test_meds_with_colon(self, formatter):
        assert formatter._is_section_header("MEDS:") is True

    def test_interactions_with_colon(self, formatter):
        assert formatter._is_section_header("INTERACTIONS:") is True

    def test_drug_interaction_with_colon(self, formatter):
        assert formatter._is_section_header("DRUG INTERACTION:") is True

    def test_warnings_with_colon(self, formatter):
        assert formatter._is_section_header("WARNINGS:") is True

    def test_alerts_with_colon(self, formatter):
        assert formatter._is_section_header("ALERTS:") is True

    def test_recommendations_with_colon(self, formatter):
        assert formatter._is_section_header("RECOMMENDATIONS:") is True

    def test_clinical_summary_with_colon(self, formatter):
        assert formatter._is_section_header("CLINICAL SUMMARY:") is True

    def test_summary_with_colon(self, formatter):
        assert formatter._is_section_header("SUMMARY:") is True

    def test_differential_with_colon(self, formatter):
        assert formatter._is_section_header("DIFFERENTIAL:") is True

    def test_diagnoses_with_colon(self, formatter):
        assert formatter._is_section_header("DIAGNOSES:") is True

    def test_red_flags_with_colon(self, formatter):
        assert formatter._is_section_header("RED FLAGS:") is True

    def test_investigations_with_colon(self, formatter):
        assert formatter._is_section_header("INVESTIGATIONS:") is True

    def test_monitoring_with_colon(self, formatter):
        assert formatter._is_section_header("MONITORING:") is True

    def test_workup_with_colon(self, formatter):
        assert formatter._is_section_header("WORKUP:") is True

    def test_tests_with_colon(self, formatter):
        assert formatter._is_section_header("TESTS:") is True

    # --- all-caps patterns (no colon) ---

    def test_all_caps_medications_no_colon(self, formatter):
        assert formatter._is_section_header("MEDICATIONS") is True

    def test_all_caps_warnings_no_colon(self, formatter):
        assert formatter._is_section_header("WARNINGS") is True

    def test_all_caps_summary_no_colon(self, formatter):
        assert formatter._is_section_header("SUMMARY") is True

    def test_all_caps_differential_no_colon(self, formatter):
        assert formatter._is_section_header("DIFFERENTIAL") is True

    def test_all_caps_red_flags_no_colon(self, formatter):
        assert formatter._is_section_header("RED FLAGS") is True

    # --- non-header cases ---

    def test_plain_sentence_is_not_header(self, formatter):
        assert formatter._is_section_header("Patient has a history of hypertension.") is False

    def test_lowercase_word_with_colon_is_not_header(self, formatter):
        assert formatter._is_section_header("note:") is False

    def test_empty_string_is_not_header(self, formatter):
        assert formatter._is_section_header("") is False

    def test_colon_only_no_keyword_is_not_header(self, formatter):
        assert formatter._is_section_header("PATIENT:") is False

    def test_all_caps_long_line_is_not_header(self, formatter):
        long_line = "MEDICATIONS " + "A" * 50
        assert formatter._is_section_header(long_line) is False

    def test_mixed_case_with_colon_still_matches_keyword(self, formatter):
        # line.upper() is used for comparison, so "Medications:" should work
        assert formatter._is_section_header("Medications:") is True

    def test_lowercase_medications_without_colon_is_not_header(self, formatter):
        # No colon, and not isupper() → False
        assert formatter._is_section_header("medications") is False


# ---------------------------------------------------------------------------
# TestDetectSeverity
# ---------------------------------------------------------------------------

class TestDetectSeverity:
    """Tests for AnalysisPanelFormatter._detect_severity(line)."""

    # --- contraindicated ---

    def test_contraindicated_keyword(self, formatter):
        assert formatter._detect_severity("This combination is contraindicated.") == "contraindicated"

    def test_do_not_use_phrase(self, formatter):
        assert formatter._detect_severity("Do not use these together.") == "contraindicated"

    def test_avoid_combination_phrase(self, formatter):
        assert formatter._detect_severity("Avoid combination with warfarin.") == "contraindicated"

    def test_never_use_together_phrase(self, formatter):
        assert formatter._detect_severity("Never use together with MAOIs.") == "contraindicated"

    def test_absolute_contraindication_phrase(self, formatter):
        assert formatter._detect_severity("Absolute contraindication in pregnancy.") == "contraindicated"

    def test_contraindicated_case_insensitive(self, formatter):
        assert formatter._detect_severity("CONTRAINDICATED in renal failure") == "contraindicated"

    # --- major ---

    def test_major_bracket_tag(self, formatter):
        assert formatter._detect_severity("[MAJOR] interaction detected") == "major"

    def test_major_bracket_tag_lowercase(self, formatter):
        assert formatter._detect_severity("[major] risk noted") == "major"

    def test_severity_major_phrase(self, formatter):
        assert formatter._detect_severity("Severity: Major") == "major"

    def test_major_interaction_phrase(self, formatter):
        assert formatter._detect_severity("Major interaction between drugs") == "major"

    def test_major_with_interaction_word(self, formatter):
        assert formatter._detect_severity("This is a major drug interaction") == "major"

    def test_major_with_severity_word(self, formatter):
        assert formatter._detect_severity("major severity noted here") == "major"

    def test_major_with_risk_word(self, formatter):
        assert formatter._detect_severity("major risk of bleeding") == "major"

    # --- moderate ---

    def test_moderate_bracket_tag(self, formatter):
        assert formatter._detect_severity("[MODERATE] combination") == "moderate"

    def test_severity_moderate_phrase(self, formatter):
        assert formatter._detect_severity("Severity: Moderate, monitor closely") == "moderate"

    def test_moderate_interaction_phrase(self, formatter):
        assert formatter._detect_severity("Moderate interaction possible") == "moderate"

    def test_moderate_with_risk_word(self, formatter):
        assert formatter._detect_severity("moderate risk of hepatotoxicity") == "moderate"

    def test_moderate_with_severity_word(self, formatter):
        assert formatter._detect_severity("This is moderate severity") == "moderate"

    # --- minor ---

    def test_minor_bracket_tag(self, formatter):
        assert formatter._detect_severity("[minor] effect") == "minor"

    def test_severity_minor_phrase(self, formatter):
        assert formatter._detect_severity("Severity: minor") == "minor"

    def test_minor_interaction_phrase(self, formatter):
        assert formatter._detect_severity("Minor interaction between aspirin and ibuprofen") == "minor"

    def test_minor_with_interaction_word(self, formatter):
        assert formatter._detect_severity("minor drug interaction possible") == "minor"

    def test_minor_with_risk_word(self, formatter):
        assert formatter._detect_severity("minor risk, no action needed") == "minor"

    # --- None cases ---

    def test_no_severity_plain_text(self, formatter):
        assert formatter._detect_severity("Take with food.") is None

    def test_no_severity_empty_string(self, formatter):
        assert formatter._detect_severity("") is None

    def test_no_severity_unrelated_clinical_text(self, formatter):
        assert formatter._detect_severity("Patient has hypertension and diabetes.") is None

    def test_major_alone_without_context_word_returns_none(self, formatter):
        # 'major' alone without 'interaction', 'severity', or 'risk' and no bracket
        assert formatter._detect_severity("This is a major concern") is None

    def test_moderate_alone_without_context_word_returns_none(self, formatter):
        assert formatter._detect_severity("Patient shows moderate improvement") is None

    def test_minor_alone_without_context_word_returns_none(self, formatter):
        assert formatter._detect_severity("Minor adjustment needed") is None


# ---------------------------------------------------------------------------
# TestDetectConfidenceLevel
# ---------------------------------------------------------------------------

class TestDetectConfidenceLevel:
    """Tests for AnalysisPanelFormatter._detect_confidence_level(line)."""

    # --- percentage patterns ---

    def test_70_percent_returns_high(self, formatter):
        assert formatter._detect_confidence_level("Likelihood: 70%") == "high"

    def test_85_percent_returns_high(self, formatter):
        assert formatter._detect_confidence_level("Diagnosis [85%] confirmed") == "high"

    def test_100_percent_returns_high(self, formatter):
        assert formatter._detect_confidence_level("100% match") == "high"

    def test_40_percent_returns_medium(self, formatter):
        assert formatter._detect_confidence_level("Confidence 40%") == "medium"

    def test_55_percent_returns_medium(self, formatter):
        assert formatter._detect_confidence_level("55% probability") == "medium"

    def test_69_percent_returns_medium(self, formatter):
        assert formatter._detect_confidence_level("69% chance") == "medium"

    def test_0_percent_returns_low(self, formatter):
        assert formatter._detect_confidence_level("0% likelihood") == "low"

    def test_20_percent_returns_low(self, formatter):
        assert formatter._detect_confidence_level("[20%] diagnosis") == "low"

    def test_39_percent_returns_low(self, formatter):
        assert formatter._detect_confidence_level("39 % match") == "low"

    # --- bracket patterns ---

    def test_bracket_HIGH_returns_high(self, formatter):
        assert formatter._detect_confidence_level("[HIGH] likelihood") == "high"

    def test_bracket_LIKELY_returns_high(self, formatter):
        assert formatter._detect_confidence_level("[LIKELY] diagnosis") == "high"

    def test_bracket_high_lowercase_returns_high(self, formatter):
        assert formatter._detect_confidence_level("[high] confidence") == "high"

    def test_bracket_MEDIUM_returns_medium(self, formatter):
        assert formatter._detect_confidence_level("[MEDIUM] probability") == "medium"

    def test_bracket_MODERATE_returns_medium(self, formatter):
        assert formatter._detect_confidence_level("[MODERATE] confidence") == "medium"

    def test_bracket_POSSIBLE_returns_medium(self, formatter):
        assert formatter._detect_confidence_level("[POSSIBLE] diagnosis") == "medium"

    def test_bracket_LOW_returns_low(self, formatter):
        assert formatter._detect_confidence_level("[LOW] probability") == "low"

    def test_bracket_UNLIKELY_returns_low(self, formatter):
        assert formatter._detect_confidence_level("[UNLIKELY] diagnosis") == "low"

    # --- text confidence patterns ---

    def test_high_confidence_text(self, formatter):
        assert formatter._detect_confidence_level("high confidence in this diagnosis") == "high"

    def test_likely_confidence_text(self, formatter):
        assert formatter._detect_confidence_level("likely, confidence supported by labs") == "high"

    def test_medium_confidence_text(self, formatter):
        assert formatter._detect_confidence_level("medium confidence rating") == "medium"

    def test_moderate_confidence_text(self, formatter):
        assert formatter._detect_confidence_level("moderate confidence in differential") == "medium"

    def test_moderate_probability_text(self, formatter):
        assert formatter._detect_confidence_level("moderate probability of disease") == "medium"

    def test_low_confidence_text(self, formatter):
        assert formatter._detect_confidence_level("low confidence in this finding") == "low"

    def test_low_probability_text(self, formatter):
        assert formatter._detect_confidence_level("low probability of malignancy") == "low"

    # --- None cases ---

    def test_plain_text_returns_none(self, formatter):
        assert formatter._detect_confidence_level("Patient presents with chest pain.") is None

    def test_empty_string_returns_none(self, formatter):
        assert formatter._detect_confidence_level("") is None

    def test_high_without_confidence_returns_none(self, formatter):
        assert formatter._detect_confidence_level("high blood pressure noted") is None

    def test_low_without_confidence_or_probability_returns_none(self, formatter):
        assert formatter._detect_confidence_level("low grade fever") is None

    def test_moderate_without_confidence_or_probability_returns_none(self, formatter):
        assert formatter._detect_confidence_level("moderate exercise recommended") is None

    # --- percentage takes priority over bracket patterns ---

    def test_percentage_takes_priority_over_bracket(self, formatter):
        # 85% is >=70 → high; bracket [LOW] would also match but regex fires first
        result = formatter._detect_confidence_level("[LOW] probability 85%")
        assert result == "high"


# ---------------------------------------------------------------------------
# TestIsWarningLine
# ---------------------------------------------------------------------------

class TestIsWarningLine:
    """Tests for AnalysisPanelFormatter._is_warning_line(line)."""

    def test_allergy_term(self, formatter):
        assert formatter._is_warning_line("Patient has penicillin allergy") is True

    def test_allergic_term(self, formatter):
        assert formatter._is_warning_line("allergic reaction reported") is True

    def test_hypersensitivity_term(self, formatter):
        assert formatter._is_warning_line("Hypersensitivity to sulfa drugs") is True

    def test_renal_term(self, formatter):
        assert formatter._is_warning_line("Renal dose adjustment required") is True

    def test_kidney_term(self, formatter):
        assert formatter._is_warning_line("kidney function impaired") is True

    def test_egfr_term(self, formatter):
        assert formatter._is_warning_line("eGFR < 30 mL/min") is True

    def test_creatinine_term(self, formatter):
        assert formatter._is_warning_line("Creatinine elevated at 2.1") is True

    def test_hepatic_term(self, formatter):
        assert formatter._is_warning_line("Hepatic clearance reduced") is True

    def test_liver_term(self, formatter):
        assert formatter._is_warning_line("liver function tests abnormal") is True

    def test_ast_term(self, formatter):
        assert formatter._is_warning_line("AST/ALT elevated") is True

    def test_alt_term(self, formatter):
        assert formatter._is_warning_line("alt levels need monitoring") is True

    def test_caution_term(self, formatter):
        assert formatter._is_warning_line("Caution when combining these drugs") is True

    def test_warning_term(self, formatter):
        assert formatter._is_warning_line("Warning: potential interaction") is True

    def test_alert_term(self, formatter):
        assert formatter._is_warning_line("Alert: critical value") is True

    def test_monitor_term(self, formatter):
        assert formatter._is_warning_line("Monitor blood pressure weekly") is True

    def test_check_term(self, formatter):
        assert formatter._is_warning_line("check electrolytes") is True

    def test_careful_term(self, formatter):
        assert formatter._is_warning_line("Be careful with dosing") is True

    def test_mixed_case_terms(self, formatter):
        assert formatter._is_warning_line("MONITOR potassium levels") is True

    def test_non_warning_plain_text(self, formatter):
        assert formatter._is_warning_line("Take tablet once daily with food.") is False

    def test_empty_string_is_not_warning(self, formatter):
        assert formatter._is_warning_line("") is False

    def test_unrelated_clinical_note_is_not_warning(self, formatter):
        assert formatter._is_warning_line("Patient reports improved sleep.") is False


# ---------------------------------------------------------------------------
# TestDetectWarningType
# ---------------------------------------------------------------------------

class TestDetectWarningType:
    """Tests for AnalysisPanelFormatter._detect_warning_type(line)."""

    # --- allergy ---

    def test_allergy_keyword_returns_allergy(self, formatter):
        assert formatter._detect_warning_type("Known allergy to penicillin") == "allergy"

    def test_allergic_keyword_returns_allergy(self, formatter):
        assert formatter._detect_warning_type("allergic to sulfa") == "allergy"

    def test_hypersensitivity_keyword_returns_allergy(self, formatter):
        assert formatter._detect_warning_type("Hypersensitivity documented") == "allergy"

    # --- renal ---

    def test_renal_keyword_returns_renal(self, formatter):
        assert formatter._detect_warning_type("Renal impairment present") == "renal"

    def test_kidney_keyword_returns_renal(self, formatter):
        assert formatter._detect_warning_type("kidney disease stage 3") == "renal"

    def test_egfr_keyword_returns_renal(self, formatter):
        assert formatter._detect_warning_type("eGFR is 25") == "renal"

    def test_creatinine_keyword_returns_renal(self, formatter):
        assert formatter._detect_warning_type("Creatinine clearance low") == "renal"

    # --- hepatic ---

    def test_hepatic_keyword_returns_hepatic(self, formatter):
        assert formatter._detect_warning_type("Hepatic failure reported") == "hepatic"

    def test_liver_keyword_returns_hepatic(self, formatter):
        assert formatter._detect_warning_type("liver enzymes elevated") == "hepatic"

    def test_ast_keyword_returns_hepatic(self, formatter):
        assert formatter._detect_warning_type("AST is three times normal") == "hepatic"

    def test_alt_keyword_returns_hepatic(self, formatter):
        assert formatter._detect_warning_type("alt raised significantly") == "hepatic"

    # --- allergy takes priority over renal when both present ---

    def test_allergy_takes_priority_over_renal(self, formatter):
        assert formatter._detect_warning_type("allergy and renal issue") == "allergy"

    # --- general fallback ---

    def test_caution_falls_back_to_general(self, formatter):
        assert formatter._detect_warning_type("Caution with this combination") == "general"

    def test_warning_falls_back_to_general(self, formatter):
        assert formatter._detect_warning_type("Warning: monitor closely") == "general"

    def test_monitor_falls_back_to_general(self, formatter):
        assert formatter._detect_warning_type("Monitor blood pressure") == "general"

    def test_alert_falls_back_to_general(self, formatter):
        assert formatter._detect_warning_type("Alert: dose check needed") == "general"

    def test_unrelated_text_falls_back_to_general(self, formatter):
        assert formatter._detect_warning_type("Routine follow-up in 3 months") == "general"


# ---------------------------------------------------------------------------
# TestIsRedFlag
# ---------------------------------------------------------------------------

class TestIsRedFlag:
    """Tests for AnalysisPanelFormatter._is_red_flag(line)."""

    # --- 'red flag' text always returns True ---

    def test_red_flag_text_alone(self, formatter):
        assert formatter._is_red_flag("red flag present") is True

    def test_red_flag_text_uppercase(self, formatter):
        assert formatter._is_red_flag("RED FLAG: consider sepsis") is True

    def test_red_flag_text_mixed_case(self, formatter):
        assert formatter._is_red_flag("This is a Red Flag finding") is True

    # --- symbol + danger keyword ---

    def test_asterisk_with_urgent(self, formatter):
        assert formatter._is_red_flag("* Urgent referral needed") is True

    def test_exclamation_with_urgent(self, formatter):
        assert formatter._is_red_flag("! Urgent: call 911") is True

    def test_asterisk_with_emergent(self, formatter):
        assert formatter._is_red_flag("* Emergent transfer required") is True

    def test_exclamation_with_immediate(self, formatter):
        assert formatter._is_red_flag("! Immediate action required") is True

    def test_asterisk_with_critical(self, formatter):
        assert formatter._is_red_flag("* Critical lab value") is True

    def test_exclamation_with_serious(self, formatter):
        assert formatter._is_red_flag("! Serious adverse effect") is True

    def test_asterisk_with_severe(self, formatter):
        assert formatter._is_red_flag("* Severe hypotension") is True

    def test_exclamation_with_dangerous(self, formatter):
        assert formatter._is_red_flag("! Dangerous drug level") is True

    # --- symbol without danger keyword → False ---

    def test_asterisk_without_danger_keyword(self, formatter):
        assert formatter._is_red_flag("* Take with food") is False

    def test_exclamation_without_danger_keyword(self, formatter):
        assert formatter._is_red_flag("! Patient is stable") is False

    # --- no symbol, no 'red flag' text → False ---

    def test_plain_urgent_without_symbol(self, formatter):
        assert formatter._is_red_flag("urgent followup scheduled") is False

    def test_plain_text_returns_false(self, formatter):
        assert formatter._is_red_flag("Routine check-up required") is False

    def test_empty_string_returns_false(self, formatter):
        assert formatter._is_red_flag("") is False

    # --- case insensitivity ---

    def test_asterisk_with_danger_keyword_uppercase(self, formatter):
        assert formatter._is_red_flag("* URGENT transfer") is True


# ---------------------------------------------------------------------------
# TestIsRecommendation
# ---------------------------------------------------------------------------

class TestIsRecommendation:
    """Tests for AnalysisPanelFormatter._is_recommendation(line)."""

    # --- numbered with rec_terms → True ---

    def test_numbered_period_recommend(self, formatter):
        assert formatter._is_recommendation("1. Recommend cardiology referral") is True

    def test_numbered_paren_suggest(self, formatter):
        assert formatter._is_recommendation("2) Suggest dose reduction") is True

    def test_numbered_period_consider(self, formatter):
        assert formatter._is_recommendation("3. Consider statin therapy") is True

    def test_numbered_period_should(self, formatter):
        assert formatter._is_recommendation("4. Patient should avoid NSAIDs") is True

    def test_numbered_period_monitor(self, formatter):
        assert formatter._is_recommendation("5. Monitor renal function") is True

    def test_numbered_period_follow(self, formatter):
        assert formatter._is_recommendation("1. Follow up in two weeks") is True

    def test_numbered_period_check(self, formatter):
        assert formatter._is_recommendation("2. Check electrolytes before next dose") is True

    def test_numbered_period_review(self, formatter):
        assert formatter._is_recommendation("3. Review current medications") is True

    def test_numbered_period_obtain(self, formatter):
        assert formatter._is_recommendation("4. Obtain chest X-ray") is True

    def test_numbered_period_order(self, formatter):
        assert formatter._is_recommendation("5. Order CBC and CMP") is True

    def test_numbered_period_refer(self, formatter):
        assert formatter._is_recommendation("1. Refer to nephrology") is True

    def test_numbered_period_start(self, formatter):
        assert formatter._is_recommendation("2. Start metformin 500 mg daily") is True

    def test_numbered_period_continue(self, formatter):
        assert formatter._is_recommendation("3. Continue current regimen") is True

    def test_numbered_period_discontinue(self, formatter):
        assert formatter._is_recommendation("4. Discontinue NSAIDs immediately") is True

    def test_large_number_with_rec_term(self, formatter):
        assert formatter._is_recommendation("12. Consider alternative antibiotic") is True

    # --- numbered but without rec_terms → False ---

    def test_numbered_without_rec_term(self, formatter):
        assert formatter._is_recommendation("1. Patient is feeling better today.") is False

    def test_numbered_paren_without_rec_term(self, formatter):
        assert formatter._is_recommendation("3) Vitamin D levels normal.") is False

    # --- bullet patterns → False ---

    def test_bullet_asterisk_with_rec_term(self, formatter):
        assert formatter._is_recommendation("* Recommend dose adjustment") is False

    def test_bullet_dash_with_rec_term(self, formatter):
        assert formatter._is_recommendation("- Consider MRI") is False

    def test_bullet_dot_with_rec_term(self, formatter):
        assert formatter._is_recommendation("• Monitor CBC weekly") is False

    # --- edge cases ---

    def test_empty_string_returns_false(self, formatter):
        assert formatter._is_recommendation("") is False

    def test_plain_text_with_rec_term_no_number(self, formatter):
        assert formatter._is_recommendation("We recommend daily aspirin") is False

    def test_leading_whitespace_with_number_and_rec_term(self, formatter):
        # The regex allows leading whitespace: r'^\s*\d+[.\)]\s+'
        assert formatter._is_recommendation("   1. Monitor potassium") is True
