"""
Tests for src/ai/agents/diagnostic.py (pure-logic methods only)
No network, no Tkinter, no AI calls.
"""
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.agents.diagnostic import DiagnosticAgent
from ai.agents.models import AgentConfig, AgentTask, AgentResponse


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def agent():
    return DiagnosticAgent(config=None, ai_caller=None)


# ---------------------------------------------------------------------------
# Sample text constants reused across tests
# ---------------------------------------------------------------------------

FULL_ANALYSIS = """CLINICAL SUMMARY: 45-year-old male presenting with chest pain and dyspnea.

DIFFERENTIAL DIAGNOSES:
1. Acute coronary syndrome - 80% (ICD-10: I21.9, ICD-9: 410.90)
- Supporting: Chest pain, diaphoresis, elevated troponin
- Against: No prior cardiac history
- Next steps: ECG, troponin trend, cardiology consult
2. Pulmonary embolism - 55% (ICD-10: I26.99, ICD-9: 415.19)
- Supporting: Dyspnea, tachycardia
- Against: No leg swelling, Wells score low
- Next steps: D-dimer, CT pulmonary angiography
3. Musculoskeletal chest pain - 25% (ICD-10: M54.6, ICD-9: 786.59)
- Supporting: Reproducible with palpation
- Against: Severity inconsistent
- Next steps: Clinical observation

RED FLAGS:
- ⚠ Elevated troponin - possible STEMI
- ⚠ Hemodynamic instability

RECOMMENDED INVESTIGATIONS:
- CBC - Urgent - Baseline assessment
- ECG - Urgent - Rule out STEMI
- CT chest - Routine - Rule out PE
- MRI brain - Optional - Neurological symptoms

CLINICAL PEARLS:
- Always consider ACS in middle-aged males with exertional chest pain
- D-dimer has high sensitivity but low specificity
- 1. Troponin should be trended at 3 and 6 hours
"""

MINIMAL_FULL_ANALYSIS = """CLINICAL SUMMARY: Brief presentation.

DIFFERENTIAL DIAGNOSES:
1. Hypertension - 60% (ICD-10: I10, ICD-9: 401.9)
- Supporting: Elevated BP readings

RED FLAGS:
- None identified

RECOMMENDED INVESTIGATIONS:
- Blood pressure monitoring - Routine - Serial measurements

CLINICAL PEARLS:
- Monitor blood pressure regularly
"""


# ===========================================================================
# Tests for _safe_extract_section
# ===========================================================================

class TestSafeExtractSection:
    """Tests for DiagnosticAgent._safe_extract_section (static method)."""

    def test_returns_string(self, agent):
        result = agent._safe_extract_section("START: content END:", "START:")
        assert isinstance(result, str)

    def test_basic_extraction(self, agent):
        text = "HEADER: some content here FOOTER: other"
        result = agent._safe_extract_section(text, "HEADER:", ["FOOTER:"])
        assert "some content here" in result

    def test_returns_empty_when_marker_missing(self, agent):
        result = agent._safe_extract_section("no marker here", "MISSING:")
        assert result == ""

    def test_returns_empty_on_empty_text(self, agent):
        result = agent._safe_extract_section("", "MARKER:")
        assert result == ""

    def test_no_end_markers_returns_rest(self, agent):
        text = "SECTION: first second third"
        result = agent._safe_extract_section(text, "SECTION:")
        assert result == "first second third"

    def test_strips_leading_trailing_whitespace(self, agent):
        text = "SECTION:   \n   content \n   "
        result = agent._safe_extract_section(text, "SECTION:")
        assert result == result.strip()

    def test_uses_first_matching_end_marker(self, agent):
        text = "START: alpha MIDDLE: beta END: gamma"
        result = agent._safe_extract_section(text, "START:", ["MIDDLE:", "END:"])
        assert "alpha" in result
        assert "beta" not in result

    def test_skips_absent_end_marker_uses_present_one(self, agent):
        text = "START: content FINISH: tail"
        result = agent._safe_extract_section(text, "START:", ["NOTPRESENT:", "FINISH:"])
        assert "content" in result
        assert "tail" not in result

    def test_multiple_end_markers_picks_first_present(self, agent):
        text = "A: body B: rest C: more"
        result = agent._safe_extract_section(text, "A:", ["B:", "C:"])
        assert "body" in result
        assert "rest" not in result

    def test_marker_at_very_end_returns_empty(self, agent):
        text = "prefix MARKER:"
        result = agent._safe_extract_section(text, "MARKER:")
        assert result == ""

    def test_end_marker_not_in_section_returns_full_rest(self, agent):
        text = "START: hello WORLD:"
        result = agent._safe_extract_section(text, "START:", ["NOTHERE:"])
        assert "hello" in result

    def test_multiline_content_extracted(self, agent):
        text = "SECTION:\nline1\nline2\nline3\nEND:"
        result = agent._safe_extract_section(text, "SECTION:", ["END:"])
        assert "line1" in result
        assert "line2" in result
        assert "line3" in result

    def test_marker_appearing_twice_splits_on_first(self, agent):
        text = "MARKER: first MARKER: second"
        result = agent._safe_extract_section(text, "MARKER:")
        # split on 1st occurrence only — result contains " first MARKER: second"
        assert "first" in result

    def test_case_sensitive_no_match_lowercase_marker(self, agent):
        # _safe_extract_section does NOT lowercase – marker must match case exactly
        result = agent._safe_extract_section("section: content", "SECTION:")
        assert result == ""

    def test_none_end_markers_defaults_safely(self, agent):
        text = "M: content"
        result = agent._safe_extract_section(text, "M:", None)
        assert "content" in result

    def test_static_method_callable_on_class_directly(self):
        text = "K: value"
        result = DiagnosticAgent._safe_extract_section(text, "K:")
        assert "value" in result


# ===========================================================================
# Tests for _get_validation_warnings
# ===========================================================================

class TestGetValidationWarnings:
    """Tests for DiagnosticAgent._get_validation_warnings."""

    def test_returns_list(self, agent):
        result = agent._get_validation_warnings([])
        assert isinstance(result, list)

    def test_empty_results_returns_empty_list(self, agent):
        assert agent._get_validation_warnings([]) == []

    def test_invalid_code_produces_warning(self, agent):
        results = [{'code': 'ZZZ999', 'is_valid': False, 'warning': None}]
        warnings = agent._get_validation_warnings(results)
        assert len(warnings) == 1
        assert "ZZZ999" in warnings[0]
        assert "Invalid" in warnings[0]

    def test_valid_code_no_warning_field_produces_no_warning(self, agent):
        results = [{'code': 'I10', 'is_valid': True, 'warning': None}]
        warnings = agent._get_validation_warnings(results)
        assert warnings == []

    def test_valid_code_with_warning_field_produces_warning(self, agent):
        results = [{'code': 'I10', 'is_valid': True, 'warning': 'Unverified code'}]
        warnings = agent._get_validation_warnings(results)
        assert len(warnings) == 1
        assert "I10" in warnings[0]
        assert "Unverified" in warnings[0]

    def test_mixed_results_correct_count(self, agent):
        results = [
            {'code': 'I21.9', 'is_valid': True, 'warning': None},
            {'code': 'INVALID', 'is_valid': False, 'warning': None},
            {'code': 'J06.9', 'is_valid': True, 'warning': 'Not in DB'},
        ]
        warnings = agent._get_validation_warnings(results)
        # One invalid + one with warning = 2
        assert len(warnings) == 2

    def test_all_valid_no_warnings_returns_empty(self, agent):
        results = [
            {'code': 'I10', 'is_valid': True, 'warning': None},
            {'code': 'E11.9', 'is_valid': True, 'warning': None},
        ]
        assert agent._get_validation_warnings(results) == []

    def test_missing_is_valid_key_treated_as_valid(self, agent):
        # is_valid missing → get(..., True) → treated as valid, no invalid warning
        results = [{'code': 'X00', 'warning': None}]
        warnings = agent._get_validation_warnings(results)
        assert warnings == []

    def test_warning_message_contains_code_and_warning_text(self, agent):
        results = [{'code': 'G43.009', 'is_valid': True, 'warning': 'Not found in ICD-10 DB'}]
        warnings = agent._get_validation_warnings(results)
        assert "G43.009" in warnings[0]
        assert "Not found in ICD-10 DB" in warnings[0]

    def test_multiple_invalid_codes_all_warned(self, agent):
        results = [
            {'code': 'BAD1', 'is_valid': False, 'warning': None},
            {'code': 'BAD2', 'is_valid': False, 'warning': None},
        ]
        warnings = agent._get_validation_warnings(results)
        assert len(warnings) == 2
        assert any("BAD1" in w for w in warnings)
        assert any("BAD2" in w for w in warnings)


# ===========================================================================
# Tests for _append_validation_warnings
# ===========================================================================

class TestAppendValidationWarnings:
    """Tests for DiagnosticAgent._append_validation_warnings."""

    def test_returns_string(self, agent):
        result = agent._append_validation_warnings("analysis", ["warning 1"])
        assert isinstance(result, str)

    def test_empty_warnings_returns_original_unchanged(self, agent):
        original = "some analysis text"
        result = agent._append_validation_warnings(original, [])
        assert result == original

    def test_warnings_appended_to_analysis(self, agent):
        result = agent._append_validation_warnings("analysis", ["Invalid code: X1"])
        assert "Invalid code: X1" in result

    def test_section_header_present(self, agent):
        result = agent._append_validation_warnings("analysis", ["warning"])
        assert "ICD CODE VALIDATION NOTES" in result

    def test_footer_instruction_present(self, agent):
        result = agent._append_validation_warnings("analysis", ["w1"])
        assert "verify" in result.lower() or "ICD references" in result

    def test_multiple_warnings_all_present(self, agent):
        warnings = ["Warning A", "Warning B", "Warning C"]
        result = agent._append_validation_warnings("analysis", warnings)
        for w in warnings:
            assert w in result

    def test_original_analysis_preserved(self, agent):
        original = "CLINICAL SUMMARY: Patient has fever."
        result = agent._append_validation_warnings(original, ["w1"])
        assert original in result

    def test_each_warning_on_separate_bullet(self, agent):
        warnings = ["Alpha", "Beta"]
        result = agent._append_validation_warnings("analysis", warnings)
        assert "- Alpha" in result
        assert "- Beta" in result

    def test_appended_after_original_text(self, agent):
        original = "original content"
        result = agent._append_validation_warnings(original, ["warn"])
        assert result.index(original) < result.index("ICD CODE VALIDATION")


# ===========================================================================
# Tests for _extract_clinical_findings
# ===========================================================================

class TestExtractClinicalFindings:
    """Tests for DiagnosticAgent._extract_clinical_findings."""

    def test_returns_string(self, agent):
        result = agent._extract_clinical_findings("SUBJECTIVE: patient complains")
        assert isinstance(result, str)

    def test_empty_soap_returns_empty(self, agent):
        result = agent._extract_clinical_findings("")
        assert result == ""

    def test_extracts_subjective_section(self, agent):
        soap = "SUBJECTIVE: headache and nausea\nOBJECTIVE: BP 120/80"
        result = agent._extract_clinical_findings(soap)
        assert "headache and nausea" in result

    def test_extracts_objective_section(self, agent):
        soap = "SUBJECTIVE: headache\nOBJECTIVE: BP 120/80, HR 78"
        result = agent._extract_clinical_findings(soap)
        assert "BP 120/80" in result

    def test_extracts_assessment_section(self, agent):
        soap = "ASSESSMENT: hypertension\nPLAN: start lisinopril"
        result = agent._extract_clinical_findings(soap)
        assert "hypertension" in result

    def test_labels_subjective_as_patient_complaints(self, agent):
        soap = "SUBJECTIVE: chest pain\nOBJECTIVE: normal exam"
        result = agent._extract_clinical_findings(soap)
        assert "Patient Complaints" in result

    def test_labels_objective_as_examination_findings(self, agent):
        soap = "OBJECTIVE: clear lungs\nASSESSMENT: healthy"
        result = agent._extract_clinical_findings(soap)
        assert "Examination Findings" in result

    def test_labels_assessment_as_current_assessment(self, agent):
        soap = "ASSESSMENT: Type 2 diabetes\nPLAN: metformin"
        result = agent._extract_clinical_findings(soap)
        assert "Current Assessment" in result

    def test_sections_separated_by_double_newline(self, agent):
        soap = "SUBJECTIVE: cough\nOBJECTIVE: rhonchi\nASSESSMENT: pneumonia"
        result = agent._extract_clinical_findings(soap)
        assert "\n\n" in result

    def test_no_soap_sections_returns_empty(self, agent):
        result = agent._extract_clinical_findings("This is free text with no SOAP labels.")
        assert result == ""

    def test_plan_section_content_not_included(self, agent):
        soap = "SUBJECTIVE: back pain\nPLAN: physical therapy"
        result = agent._extract_clinical_findings(soap)
        assert "physical therapy" not in result

    def test_assessment_bounded_by_plan(self, agent):
        soap = "ASSESSMENT: migraine\nPLAN: sumatriptan"
        result = agent._extract_clinical_findings(soap)
        assert "sumatriptan" not in result

    def test_full_soap_all_three_sections_present(self, agent):
        soap = (
            "SUBJECTIVE: patient reports fatigue\n"
            "OBJECTIVE: pale conjunctiva\n"
            "ASSESSMENT: anemia\n"
            "PLAN: CBC, ferritin"
        )
        result = agent._extract_clinical_findings(soap)
        assert "fatigue" in result
        assert "pale conjunctiva" in result
        assert "anemia" in result

    def test_only_subjective_present(self, agent):
        soap = "SUBJECTIVE: sore throat"
        result = agent._extract_clinical_findings(soap)
        assert "sore throat" in result

    def test_subjective_stops_before_objective(self, agent):
        soap = "SUBJECTIVE: nausea\nOBJECTIVE: abdomen soft"
        result = agent._extract_clinical_findings(soap)
        # Subjective block must not bleed into objective content
        subjective_prefix = "Patient Complaints:"
        if subjective_prefix in result:
            sub_idx = result.index(subjective_prefix)
            obj_idx = result.find("Examination Findings:")
            if obj_idx != -1:
                between = result[sub_idx:obj_idx]
                assert "abdomen soft" not in between


# ===========================================================================
# Tests for _get_specialty_instructions
# ===========================================================================

class TestGetSpecialtyInstructions:
    """Tests for DiagnosticAgent._get_specialty_instructions."""

    def test_returns_string(self, agent):
        result = agent._get_specialty_instructions("general")
        assert isinstance(result, str)

    def test_non_empty_for_general(self, agent):
        assert agent._get_specialty_instructions("general") != ""

    def test_all_known_specialties_return_non_empty(self, agent):
        specialties = [
            "general", "emergency", "internal", "pediatric",
            "cardiology", "pulmonology", "gi", "neurology",
            "psychiatry", "orthopedic", "oncology", "geriatric",
        ]
        for spec in specialties:
            result = agent._get_specialty_instructions(spec)
            assert result, f"Expected non-empty instructions for specialty: {spec}"

    def test_unknown_specialty_falls_back_to_general(self, agent):
        general = agent._get_specialty_instructions("general")
        unknown = agent._get_specialty_instructions("xenobiology")
        assert unknown == general

    def test_emergency_mentions_life_threatening(self, agent):
        result = agent._get_specialty_instructions("emergency")
        assert "life-threatening" in result.lower() or "prioriti" in result.lower()

    def test_pediatric_mentions_age_or_development(self, agent):
        result = agent._get_specialty_instructions("pediatric")
        assert "age" in result.lower() or "develop" in result.lower() or "pediatric" in result.lower()

    def test_cardiology_mentions_cardiovascular(self, agent):
        result = agent._get_specialty_instructions("cardiology")
        assert "cardiovascular" in result.lower() or "cardiac" in result.lower()

    def test_neurology_mentions_neurological(self, agent):
        result = agent._get_specialty_instructions("neurology")
        assert "neurological" in result.lower() or "neuro" in result.lower()

    def test_oncology_mentions_malignancy(self, agent):
        result = agent._get_specialty_instructions("oncology")
        assert "malignancy" in result.lower() or "cancer" in result.lower() or "oncol" in result.lower()

    def test_geriatric_mentions_elderly_or_age(self, agent):
        result = agent._get_specialty_instructions("geriatric")
        assert "elderly" in result.lower() or "age" in result.lower() or "geriatric" in result.lower()

    def test_empty_string_specialty_falls_back_to_general(self, agent):
        general = agent._get_specialty_instructions("general")
        result = agent._get_specialty_instructions("")
        assert result == general

    def test_returns_different_instructions_for_different_specialties(self, agent):
        em = agent._get_specialty_instructions("emergency")
        psych = agent._get_specialty_instructions("psychiatry")
        assert em != psych

    def test_psychiatry_mentions_biopsychosocial_or_organic(self, agent):
        result = agent._get_specialty_instructions("psychiatry")
        assert "psychiatric" in result.lower() or "organic" in result.lower() or "biopsycho" in result.lower()

    def test_gi_mentions_gastrointestinal(self, agent):
        result = agent._get_specialty_instructions("gi")
        assert "gastrointestinal" in result.lower() or "gi" in result.lower() or "hepato" in result.lower()


# ===========================================================================
# Tests for _structure_diagnostic_response
# ===========================================================================

class TestStructureDiagnosticResponse:
    """Tests for DiagnosticAgent._structure_diagnostic_response."""

    def test_returns_string(self, agent):
        result = agent._structure_diagnostic_response("some analysis")
        assert isinstance(result, str)

    def test_properly_structured_returned_unchanged(self, agent):
        proper = (
            "CLINICAL SUMMARY: summary\n"
            "DIFFERENTIAL DIAGNOSES: diffs\n"
            "RED FLAGS: flags\n"
            "RECOMMENDED INVESTIGATIONS: tests\n"
            "CLINICAL PEARLS: pearls"
        )
        result = agent._structure_diagnostic_response(proper)
        assert result == proper

    def test_unstructured_preserves_original_text(self, agent):
        unstructured = "Patient has headache and nausea."
        result = agent._structure_diagnostic_response(unstructured)
        assert "headache and nausea" in result

    def test_unstructured_gets_diagnostic_analysis_header(self, agent):
        unstructured = "Random clinical notes without proper structure."
        result = agent._structure_diagnostic_response(unstructured)
        assert "DIAGNOSTIC ANALYSIS" in result

    def test_missing_one_section_triggers_reformat(self, agent):
        # All sections except CLINICAL PEARLS
        text = (
            "CLINICAL SUMMARY: s\n"
            "DIFFERENTIAL DIAGNOSES: d\n"
            "RED FLAGS: r\n"
            "RECOMMENDED INVESTIGATIONS: i\n"
        )
        result = agent._structure_diagnostic_response(text)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_analysis_returns_non_empty_string(self, agent):
        result = agent._structure_diagnostic_response("")
        assert isinstance(result, str)

    def test_fully_structured_text_not_modified(self, agent):
        result = agent._structure_diagnostic_response(FULL_ANALYSIS)
        assert result == FULL_ANALYSIS


# ===========================================================================
# Tests for _extract_diagnoses
# ===========================================================================

class TestExtractDiagnoses:
    """Tests for DiagnosticAgent._extract_diagnoses."""

    def test_returns_list(self, agent):
        result = agent._extract_diagnoses(FULL_ANALYSIS)
        assert isinstance(result, list)

    def test_empty_analysis_returns_empty_list(self, agent):
        assert agent._extract_diagnoses("") == []

    def test_no_differential_section_returns_empty(self, agent):
        text = "CLINICAL SUMMARY: something\nRED FLAGS: none"
        assert agent._extract_diagnoses(text) == []

    def test_extracts_numbered_items(self, agent):
        text = (
            "DIFFERENTIAL DIAGNOSES:\n"
            "1. Hypertension - 70% (ICD-10: I10)\n"
            "2. Migraine - 40% (ICD-10: G43.009)\n"
            "RED FLAGS:\n"
        )
        results = agent._extract_diagnoses(text)
        assert len(results) >= 2

    def test_diagnoses_are_strings(self, agent):
        results = agent._extract_diagnoses(FULL_ANALYSIS)
        for item in results:
            assert isinstance(item, str)

    def test_extracts_icd10_codes_into_output(self, agent):
        text = (
            "DIFFERENTIAL DIAGNOSES:\n"
            "1. Acute MI - 80% (ICD-10: I21.9, ICD-9: 410.90)\n"
            "RED FLAGS:\n"
        )
        results = agent._extract_diagnoses(text)
        assert any("I21.9" in r for r in results)

    def test_bulleted_list_with_dash_extracted(self, agent):
        text = (
            "DIFFERENTIAL DIAGNOSES:\n"
            "- Pneumonia (ICD-10: J18.9)\n"
            "- Bronchitis (ICD-10: J40)\n"
            "RED FLAGS:\n"
        )
        results = agent._extract_diagnoses(text)
        assert len(results) >= 1

    def test_bullet_with_bullet_character_extracted(self, agent):
        text = (
            "DIFFERENTIAL DIAGNOSES:\n"
            "• Asthma (ICD-10: J45.909)\n"
            "RED FLAGS:\n"
        )
        results = agent._extract_diagnoses(text)
        assert isinstance(results, list)

    def test_icd9_codes_extracted(self, agent):
        text = (
            "DIFFERENTIAL DIAGNOSES:\n"
            "1. Pneumonia - 60% (ICD-10: J18.9, ICD-9: 486)\n"
            "RED FLAGS:\n"
        )
        results = agent._extract_diagnoses(text)
        assert any("ICD-9" in r for r in results)

    def test_full_analysis_returns_at_least_three_diagnoses(self, agent):
        results = agent._extract_diagnoses(FULL_ANALYSIS)
        assert len(results) >= 3

    def test_section_stops_at_red_flags(self, agent):
        text = (
            "DIFFERENTIAL DIAGNOSES:\n"
            "1. Flu - 50%\n"
            "RED FLAGS:\n"
            "1. Fever over 40 degrees\n"
        )
        results = agent._extract_diagnoses(text)
        # Items in RED FLAGS must not pollute the differential list
        assert not any("40 degrees" in r for r in results)

    def test_diagnosis_names_stripped_of_leading_numbers(self, agent):
        text = (
            "DIFFERENTIAL DIAGNOSES:\n"
            "1. Hypertension - 80%\n"
            "RED FLAGS:\n"
        )
        results = agent._extract_diagnoses(text)
        assert results
        assert not results[0].startswith("1.")

    def test_no_diagnoses_when_section_empty(self, agent):
        text = "DIFFERENTIAL DIAGNOSES:\nRED FLAGS:\n"
        results = agent._extract_diagnoses(text)
        assert isinstance(results, list)


# ===========================================================================
# Tests for _extract_structured_differentials
# ===========================================================================

class TestExtractStructuredDifferentials:
    """Tests for DiagnosticAgent._extract_structured_differentials."""

    def test_returns_list(self, agent):
        result = agent._extract_structured_differentials(FULL_ANALYSIS)
        assert isinstance(result, list)

    def test_empty_analysis_returns_empty(self, agent):
        assert agent._extract_structured_differentials("") == []

    def test_no_section_returns_empty(self, agent):
        assert agent._extract_structured_differentials("RED FLAGS: none") == []

    def test_items_are_dicts(self, agent):
        result = agent._extract_structured_differentials(FULL_ANALYSIS)
        for item in result:
            assert isinstance(item, dict)

    def test_expected_keys_present(self, agent):
        result = agent._extract_structured_differentials(FULL_ANALYSIS)
        assert result
        required_keys = {
            'rank', 'diagnosis_name', 'icd10_code', 'icd9_code',
            'confidence_score', 'confidence_level', 'reasoning',
            'supporting_findings', 'against_findings', 'next_steps', 'is_red_flag'
        }
        for item in result:
            assert required_keys.issubset(item.keys()), f"Missing keys in: {item}"

    def test_rank_values_sequential(self, agent):
        result = agent._extract_structured_differentials(FULL_ANALYSIS)
        ranks = [item['rank'] for item in result]
        assert ranks == [1, 2, 3]

    def test_confidence_score_is_float(self, agent):
        result = agent._extract_structured_differentials(FULL_ANALYSIS)
        for item in result:
            assert isinstance(item['confidence_score'], float)

    def test_confidence_score_in_range_0_to_1(self, agent):
        result = agent._extract_structured_differentials(FULL_ANALYSIS)
        for item in result:
            assert 0.0 <= item['confidence_score'] <= 1.0

    def test_high_confidence_level_label_above_70(self, agent):
        text = (
            "DIFFERENTIAL DIAGNOSES:\n"
            "1. ACS - 85% (ICD-10: I21.9)\n"
            "RED FLAGS:\n"
        )
        result = agent._extract_structured_differentials(text)
        assert result[0]['confidence_level'] == 'high'

    def test_medium_confidence_level_label_40_to_70(self, agent):
        text = (
            "DIFFERENTIAL DIAGNOSES:\n"
            "1. PE - 50% (ICD-10: I26.99)\n"
            "RED FLAGS:\n"
        )
        result = agent._extract_structured_differentials(text)
        assert result[0]['confidence_level'] == 'medium'

    def test_low_confidence_level_label_below_40(self, agent):
        text = (
            "DIFFERENTIAL DIAGNOSES:\n"
            "1. Rare cancer - 20% (ICD-10: C80.1)\n"
            "RED FLAGS:\n"
        )
        result = agent._extract_structured_differentials(text)
        assert result[0]['confidence_level'] == 'low'

    def test_icd10_code_extracted_correctly(self, agent):
        result = agent._extract_structured_differentials(FULL_ANALYSIS)
        assert result[0]['icd10_code'] == 'I21.9'

    def test_icd9_code_extracted_correctly(self, agent):
        result = agent._extract_structured_differentials(FULL_ANALYSIS)
        assert result[0]['icd9_code'] == '410.90'

    def test_supporting_findings_populated(self, agent):
        result = agent._extract_structured_differentials(FULL_ANALYSIS)
        assert result[0]['supporting_findings']

    def test_against_findings_populated(self, agent):
        result = agent._extract_structured_differentials(FULL_ANALYSIS)
        assert result[0]['against_findings']

    def test_next_steps_populated(self, agent):
        result = agent._extract_structured_differentials(FULL_ANALYSIS)
        assert result[0]['next_steps']

    def test_is_red_flag_true_when_urgent_in_line(self, agent):
        text = (
            "DIFFERENTIAL DIAGNOSES:\n"
            "1. STEMI - 90% (ICD-10: I21.01) urgent\n"
            "RED FLAGS:\n"
        )
        result = agent._extract_structured_differentials(text)
        assert result[0]['is_red_flag'] is True

    def test_is_red_flag_false_when_not_urgent(self, agent):
        text = (
            "DIFFERENTIAL DIAGNOSES:\n"
            "1. Tension headache - 60% (ICD-10: G44.20)\n"
            "RED FLAGS:\n"
        )
        result = agent._extract_structured_differentials(text)
        assert result[0]['is_red_flag'] is False

    def test_no_confidence_score_defaults_to_medium(self, agent):
        text = (
            "DIFFERENTIAL DIAGNOSES:\n"
            "1. Hypertension\n"
            "RED FLAGS:\n"
        )
        result = agent._extract_structured_differentials(text)
        assert result[0]['confidence_level'] == 'medium'
        assert result[0]['confidence_score'] == 0.5

    def test_text_confidence_high_keyword(self, agent):
        text = (
            "DIFFERENTIAL DIAGNOSES:\n"
            "1. Infection - high confidence\n"
            "RED FLAGS:\n"
        )
        result = agent._extract_structured_differentials(text)
        assert result[0]['confidence_level'] == 'high'

    def test_text_confidence_low_keyword(self, agent):
        text = (
            "DIFFERENTIAL DIAGNOSES:\n"
            "1. Rare disorder - low confidence\n"
            "RED FLAGS:\n"
        )
        result = agent._extract_structured_differentials(text)
        assert result[0]['confidence_level'] == 'low'


# ===========================================================================
# Tests for _extract_investigations
# ===========================================================================

class TestExtractInvestigations:
    """Tests for DiagnosticAgent._extract_investigations."""

    def test_returns_list(self, agent):
        result = agent._extract_investigations(FULL_ANALYSIS)
        assert isinstance(result, list)

    def test_empty_analysis_returns_empty(self, agent):
        assert agent._extract_investigations("") == []

    def test_no_section_returns_empty(self, agent):
        assert agent._extract_investigations("CLINICAL SUMMARY: text") == []

    def test_items_are_dicts(self, agent):
        result = agent._extract_investigations(FULL_ANALYSIS)
        for item in result:
            assert isinstance(item, dict)

    def test_expected_keys_present(self, agent):
        result = agent._extract_investigations(FULL_ANALYSIS)
        assert result
        required_keys = {'investigation_name', 'investigation_type', 'priority', 'rationale', 'status'}
        for item in result:
            assert required_keys.issubset(item.keys())

    def test_status_always_pending(self, agent):
        result = agent._extract_investigations(FULL_ANALYSIS)
        for item in result:
            assert item['status'] == 'pending'

    def test_urgent_priority_detected(self, agent):
        result = agent._extract_investigations(FULL_ANALYSIS)
        priorities = [item['priority'] for item in result]
        assert 'urgent' in priorities

    def test_routine_priority_detected(self, agent):
        result = agent._extract_investigations(FULL_ANALYSIS)
        priorities = [item['priority'] for item in result]
        assert 'routine' in priorities

    def test_optional_priority_detected(self, agent):
        result = agent._extract_investigations(FULL_ANALYSIS)
        priorities = [item['priority'] for item in result]
        assert 'optional' in priorities

    def test_lab_type_detected_for_cbc(self, agent):
        text = (
            "RECOMMENDED INVESTIGATIONS:\n"
            "- CBC - Urgent - Rule out infection\n"
            "CLINICAL PEARLS:\n"
        )
        result = agent._extract_investigations(text)
        assert result[0]['investigation_type'] == 'lab'

    def test_imaging_type_detected_for_ct(self, agent):
        text = (
            "RECOMMENDED INVESTIGATIONS:\n"
            "- CT chest - Routine - Assess lung\n"
            "CLINICAL PEARLS:\n"
        )
        result = agent._extract_investigations(text)
        assert result[0]['investigation_type'] == 'imaging'

    def test_mri_classified_as_imaging(self, agent):
        result = agent._extract_investigations(FULL_ANALYSIS)
        mri_items = [i for i in result if 'MRI' in i['investigation_name']]
        assert mri_items and mri_items[0]['investigation_type'] == 'imaging'

    def test_referral_type_detected(self, agent):
        text = (
            "RECOMMENDED INVESTIGATIONS:\n"
            "- Cardiology referral - Routine - Specialist input\n"
            "CLINICAL PEARLS:\n"
        )
        result = agent._extract_investigations(text)
        assert result[0]['investigation_type'] == 'referral'

    def test_investigation_name_not_empty(self, agent):
        result = agent._extract_investigations(FULL_ANALYSIS)
        for item in result:
            assert item['investigation_name'] != ''

    def test_full_analysis_returns_four_investigations(self, agent):
        # FULL_ANALYSIS has 4 investigation bullets: CBC, ECG, CT chest, MRI brain
        result = agent._extract_investigations(FULL_ANALYSIS)
        assert len(result) == 4

    def test_default_priority_is_routine(self, agent):
        text = (
            "RECOMMENDED INVESTIGATIONS:\n"
            "- Blood cultures - No priority mentioned\n"
            "CLINICAL PEARLS:\n"
        )
        result = agent._extract_investigations(text)
        assert result[0]['priority'] == 'routine'


# ===========================================================================
# Tests for _extract_clinical_pearls
# ===========================================================================

class TestExtractClinicalPearls:
    """Tests for DiagnosticAgent._extract_clinical_pearls."""

    def test_returns_list(self, agent):
        result = agent._extract_clinical_pearls(FULL_ANALYSIS)
        assert isinstance(result, list)

    def test_empty_analysis_returns_empty(self, agent):
        assert agent._extract_clinical_pearls("") == []

    def test_no_section_returns_empty(self, agent):
        assert agent._extract_clinical_pearls("DIFFERENTIAL DIAGNOSES: stuff") == []

    def test_items_are_dicts(self, agent):
        result = agent._extract_clinical_pearls(FULL_ANALYSIS)
        for item in result:
            assert isinstance(item, dict)

    def test_expected_keys_present(self, agent):
        result = agent._extract_clinical_pearls(FULL_ANALYSIS)
        assert result
        for item in result:
            assert 'pearl_text' in item
            assert 'category' in item

    def test_category_is_diagnostic(self, agent):
        result = agent._extract_clinical_pearls(FULL_ANALYSIS)
        for item in result:
            assert item['category'] == 'diagnostic'

    def test_pearl_text_not_empty(self, agent):
        result = agent._extract_clinical_pearls(FULL_ANALYSIS)
        for item in result:
            assert item['pearl_text'] != ''

    def test_dash_bullets_extracted(self, agent):
        text = (
            "CLINICAL PEARLS:\n"
            "- Always check troponin\n"
            "- D-dimer is sensitive, not specific\n"
        )
        result = agent._extract_clinical_pearls(text)
        assert len(result) == 2

    def test_numbered_items_extracted(self, agent):
        text = (
            "CLINICAL PEARLS:\n"
            "1. Consider atypical MI in women\n"
            "2. Elderly patients may not have classic symptoms\n"
        )
        result = agent._extract_clinical_pearls(text)
        assert len(result) == 2

    def test_full_analysis_returns_three_pearls(self, agent):
        # FULL_ANALYSIS has 3 pearl lines: 2 dash-bulleted + 1 numbered
        result = agent._extract_clinical_pearls(FULL_ANALYSIS)
        assert len(result) == 3

    def test_leading_dash_stripped_from_pearl_text(self, agent):
        text = "CLINICAL PEARLS:\n- Consider systemic causes\n"
        result = agent._extract_clinical_pearls(text)
        assert not result[0]['pearl_text'].startswith('-')

    def test_leading_bullet_stripped_from_pearl_text(self, agent):
        text = "CLINICAL PEARLS:\n• Check renal function\n"
        result = agent._extract_clinical_pearls(text)
        if result:
            assert not result[0]['pearl_text'].startswith('•')

    def test_pearl_text_contains_content(self, agent):
        text = "CLINICAL PEARLS:\n- Always consider ACS in middle-aged males\n"
        result = agent._extract_clinical_pearls(text)
        assert result
        assert "ACS" in result[0]['pearl_text'] or "middle-aged" in result[0]['pearl_text']


# ===========================================================================
# Tests for get_structured_analysis
# ===========================================================================

class TestGetStructuredAnalysis:
    """Tests for DiagnosticAgent.get_structured_analysis."""

    def test_returns_dict(self, agent):
        result = agent.get_structured_analysis(FULL_ANALYSIS)
        assert isinstance(result, dict)

    def test_required_keys_present(self, agent):
        result = agent.get_structured_analysis(FULL_ANALYSIS)
        required_keys = {'differentials', 'investigations', 'clinical_pearls', 'red_flags', 'clinical_summary'}
        assert required_keys.issubset(result.keys())

    def test_differentials_is_list(self, agent):
        result = agent.get_structured_analysis(FULL_ANALYSIS)
        assert isinstance(result['differentials'], list)

    def test_investigations_is_list(self, agent):
        result = agent.get_structured_analysis(FULL_ANALYSIS)
        assert isinstance(result['investigations'], list)

    def test_clinical_pearls_is_list(self, agent):
        result = agent.get_structured_analysis(FULL_ANALYSIS)
        assert isinstance(result['clinical_pearls'], list)

    def test_red_flags_is_list(self, agent):
        result = agent.get_structured_analysis(FULL_ANALYSIS)
        assert isinstance(result['red_flags'], list)

    def test_clinical_summary_is_string(self, agent):
        result = agent.get_structured_analysis(FULL_ANALYSIS)
        assert isinstance(result['clinical_summary'], str)

    def test_empty_input_returns_empty_collections(self, agent):
        result = agent.get_structured_analysis("")
        assert result['differentials'] == []
        assert result['investigations'] == []
        assert result['clinical_pearls'] == []
        assert result['red_flags'] == []
        assert result['clinical_summary'] == ''

    def test_differentials_count_matches_full_analysis(self, agent):
        result = agent.get_structured_analysis(FULL_ANALYSIS)
        assert len(result['differentials']) == 3

    def test_investigations_count_matches_full_analysis(self, agent):
        result = agent.get_structured_analysis(FULL_ANALYSIS)
        assert len(result['investigations']) == 4

    def test_clinical_pearls_count_matches_full_analysis(self, agent):
        result = agent.get_structured_analysis(FULL_ANALYSIS)
        assert len(result['clinical_pearls']) == 3

    def test_red_flags_extracted_from_full_analysis(self, agent):
        result = agent.get_structured_analysis(FULL_ANALYSIS)
        assert len(result['red_flags']) > 0

    def test_clinical_summary_contains_expected_text(self, agent):
        result = agent.get_structured_analysis(FULL_ANALYSIS)
        assert "45-year-old" in result['clinical_summary']

    def test_minimal_analysis_parses_without_error(self, agent):
        result = agent.get_structured_analysis(MINIMAL_FULL_ANALYSIS)
        assert isinstance(result, dict)

    def test_red_flags_none_value_excluded(self, agent):
        text = (
            "RED FLAGS:\n"
            "- None\n"
            "RECOMMENDED INVESTIGATIONS:\n"
        )
        result = agent.get_structured_analysis(text)
        assert 'None' not in result['red_flags']
        assert 'none' not in result['red_flags']

    def test_red_flags_na_value_excluded(self, agent):
        text = (
            "RED FLAGS:\n"
            "- N/A\n"
            "RECOMMENDED INVESTIGATIONS:\n"
        )
        result = agent.get_structured_analysis(text)
        assert not any(v.lower() == 'n/a' for v in result['red_flags'])

    def test_minimal_analysis_differentials_non_empty(self, agent):
        result = agent.get_structured_analysis(MINIMAL_FULL_ANALYSIS)
        assert len(result['differentials']) >= 1

    def test_minimal_analysis_clinical_summary_non_empty(self, agent):
        result = agent.get_structured_analysis(MINIMAL_FULL_ANALYSIS)
        assert result['clinical_summary'] != ''


# ===========================================================================
# Tests for _get_medication_considerations
# ===========================================================================

class TestGetMedicationConsiderations:
    """Tests for DiagnosticAgent._get_medication_considerations."""

    def test_returns_none_when_disabled(self, agent):
        result = agent._get_medication_considerations(
            "patient on aspirin", {}, enable_cross_reference=False
        )
        assert result is None

    def test_returns_none_when_no_medications_in_text_or_context(self, agent):
        result = agent._get_medication_considerations(
            "patient has headache without any drug history",
            {},
            enable_cross_reference=True,
        )
        assert result is None

    def test_no_exception_raised_on_none_ai_caller(self, agent):
        try:
            result = agent._get_medication_considerations(
                "taking lisinopril daily", None, enable_cross_reference=True
            )
            assert result is None or isinstance(result, str)
        except Exception:
            pytest.fail("_get_medication_considerations raised an unexpected exception")

    def test_patient_context_accepted_without_exception(self, agent):
        context = {'current_medications': 'metformin 500mg twice daily'}
        try:
            result = agent._get_medication_considerations(
                "fatigue and dizziness", context, enable_cross_reference=True
            )
            assert result is None or isinstance(result, str)
        except Exception:
            pytest.fail("Unexpected exception with patient context")

    def test_enable_cross_reference_false_always_returns_none(self, agent):
        # Even with rich medication data, disabled flag must return None
        context = {'current_medications': 'aspirin, warfarin, metformin'}
        result = agent._get_medication_considerations(
            "taking aspirin warfarin metformin", context, enable_cross_reference=False
        )
        assert result is None


# ===========================================================================
# Tests for _append_medication_considerations
# ===========================================================================

class TestAppendMedicationConsiderations:
    """Tests for DiagnosticAgent._append_medication_considerations."""

    def test_returns_string(self, agent):
        result = agent._append_medication_considerations("analysis text", "med section")
        assert isinstance(result, str)

    def test_none_section_returns_original_unchanged(self, agent):
        original = "original analysis"
        result = agent._append_medication_considerations(original, None)
        assert result == original

    def test_empty_section_returns_original_unchanged(self, agent):
        original = "original analysis"
        result = agent._append_medication_considerations(original, "")
        assert result == original

    def test_inserted_before_clinical_pearls(self, agent):
        analysis = "DIFFERENTIAL: d\nCLINICAL PEARLS: pearls here"
        med_section = "\nMEDICATION CONSIDERATIONS:\naspirin\n"
        result = agent._append_medication_considerations(analysis, med_section)
        med_pos = result.find("MEDICATION CONSIDERATIONS")
        pearls_pos = result.find("CLINICAL PEARLS")
        assert med_pos < pearls_pos

    def test_appended_at_end_when_no_clinical_pearls(self, agent):
        analysis = "DIFFERENTIAL DIAGNOSES: some stuff"
        med_section = "\nMEDICATION NOTE: warfarin"
        result = agent._append_medication_considerations(analysis, med_section)
        assert "warfarin" in result

    def test_original_content_preserved_with_pearls(self, agent):
        analysis = "CLINICAL SUMMARY: chest pain\nCLINICAL PEARLS: monitor"
        med_section = "\nMEDICATION CONSIDERATIONS:\nwarfarin\n"
        result = agent._append_medication_considerations(analysis, med_section)
        assert "chest pain" in result
        assert "monitor" in result
        assert "warfarin" in result

    def test_med_section_content_present_in_result(self, agent):
        analysis = "some analysis without pearls"
        med_section = "MEDICATION CONSIDERATIONS:\naspirin warning"
        result = agent._append_medication_considerations(analysis, med_section)
        assert "aspirin warning" in result

    def test_pearls_still_present_after_insertion(self, agent):
        analysis = "DIFFERENTIAL DIAGNOSES: d\nCLINICAL PEARLS:\n- Always check troponin"
        med_section = "\nMEDICATION CONSIDERATIONS:\nwarfarin interaction\n"
        result = agent._append_medication_considerations(analysis, med_section)
        assert "Always check troponin" in result


# ===========================================================================
# Integration-style tests (no AI calls – pure data flow through multiple methods)
# ===========================================================================

class TestIntegration:
    """Multi-method data-flow tests using pre-built strings, no AI calls."""

    def test_extract_section_then_count_pearls(self, agent):
        pearl_section = agent._safe_extract_section(
            FULL_ANALYSIS, "CLINICAL PEARLS:", ["ICD CODE VALIDATION"]
        )
        assert len(pearl_section.strip()) > 0

    def test_get_structured_analysis_roundtrip_list_keys(self, agent):
        result = agent.get_structured_analysis(FULL_ANALYSIS)
        for key in ('differentials', 'investigations', 'clinical_pearls', 'red_flags'):
            assert isinstance(result[key], list), f"Key '{key}' should be a list"

    def test_append_warnings_then_extract_validation_section(self, agent):
        analysis_with_warnings = agent._append_validation_warnings(
            FULL_ANALYSIS, ["Invalid code: ZZZ"]
        )
        section = agent._safe_extract_section(
            analysis_with_warnings, "ICD CODE VALIDATION NOTES:"
        )
        assert "ZZZ" in section

    def test_structure_response_preserves_extractability(self, agent):
        unstructured = "Patient has fever and cough."
        structured = agent._structure_diagnostic_response(unstructured)
        assert isinstance(structured, str)
        assert len(structured) > 0

    def test_extract_findings_then_validate_type(self, agent):
        soap = (
            "SUBJECTIVE: severe headache 8/10\n"
            "OBJECTIVE: BP 180/110, HR 95\n"
            "ASSESSMENT: hypertensive urgency\n"
            "PLAN: labetalol IV"
        )
        findings = agent._extract_clinical_findings(soap)
        assert isinstance(findings, str)
        assert "headache" in findings or "BP 180" in findings

    def test_specialty_instructions_non_trivial_length(self, agent):
        em_instr = agent._get_specialty_instructions("emergency")
        gen_instr = agent._get_specialty_instructions("general")
        assert len(em_instr) > 20
        assert len(gen_instr) > 20

    def test_extract_diagnoses_from_minimal_analysis(self, agent):
        results = agent._extract_diagnoses(MINIMAL_FULL_ANALYSIS)
        assert isinstance(results, list)
        assert len(results) >= 1

    def test_get_structured_analysis_from_minimal_analysis_has_summary(self, agent):
        result = agent.get_structured_analysis(MINIMAL_FULL_ANALYSIS)
        assert result['clinical_summary'] != ''
        assert len(result['differentials']) >= 1

    def test_validation_warnings_then_append_and_verify(self, agent):
        results = [
            {'code': 'BAD', 'is_valid': False, 'warning': None},
            {'code': 'G43.009', 'is_valid': True, 'warning': 'Not in DB'},
        ]
        warnings = agent._get_validation_warnings(results)
        original = "some analysis"
        final = agent._append_validation_warnings(original, warnings)
        assert "BAD" in final
        assert "G43.009" in final

    def test_structured_differentials_count_not_greater_than_extract_diagnoses(self, agent):
        # _extract_structured_differentials parses main numbered items only;
        # _extract_diagnoses may include sub-bullet lines too
        structured = agent._extract_structured_differentials(FULL_ANALYSIS)
        simple = agent._extract_diagnoses(FULL_ANALYSIS)
        assert len(structured) <= len(simple)
