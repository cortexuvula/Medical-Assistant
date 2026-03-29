"""
Tests for MedicationPromptMixin in src/ai/agents/medication_prompts.py

All methods are pure string-builders with no side effects, so these tests
verify the exact content and structure of the returned strings.
"""

import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.agents.medication_prompts import MedicationPromptMixin


class ConcreteMixin(MedicationPromptMixin):
    pass


@pytest.fixture
def mixin():
    return ConcreteMixin()


# ---------------------------------------------------------------------------
# TestBuildExtractionPrompt  (12 tests)
# ---------------------------------------------------------------------------

class TestBuildExtractionPrompt:
    """Tests for _build_extraction_prompt(text, context=None)."""

    def test_returns_string(self, mixin):
        result = mixin._build_extraction_prompt("patient takes aspirin")
        assert isinstance(result, str)

    def test_no_context_starts_with_extract(self, mixin):
        result = mixin._build_extraction_prompt("patient takes aspirin")
        assert result.startswith("Extract all medications")

    def test_with_context_starts_with_additional_context(self, mixin):
        result = mixin._build_extraction_prompt("patient takes aspirin", context="Cardiology visit")
        assert result.startswith("Additional Context: Cardiology visit")

    def test_context_value_embedded_correctly(self, mixin):
        result = mixin._build_extraction_prompt("text", context="Oncology notes")
        assert "Additional Context: Oncology notes" in result

    def test_ends_with_extracted_medications_no_context(self, mixin):
        result = mixin._build_extraction_prompt("patient takes metformin")
        assert result.endswith("Extracted Medications:")

    def test_ends_with_extracted_medications_with_context(self, mixin):
        result = mixin._build_extraction_prompt("patient takes metformin", context="Diabetes")
        assert result.endswith("Extracted Medications:")

    def test_contains_generic_and_brand_names(self, mixin):
        result = mixin._build_extraction_prompt("lisinopril 10mg daily")
        assert "Generic and brand names" in result

    def test_contains_dosage_and_strength(self, mixin):
        result = mixin._build_extraction_prompt("lisinopril 10mg daily")
        assert "Dosage and strength" in result

    def test_contains_route_of_administration(self, mixin):
        result = mixin._build_extraction_prompt("lisinopril 10mg daily")
        assert "Route of administration" in result

    def test_contains_frequency(self, mixin):
        result = mixin._build_extraction_prompt("lisinopril 10mg daily")
        assert "Frequency" in result

    def test_contains_duration_or_status(self, mixin):
        result = mixin._build_extraction_prompt("lisinopril 10mg daily")
        assert "Duration or status" in result

    def test_contains_indication_if_mentioned(self, mixin):
        result = mixin._build_extraction_prompt("lisinopril 10mg daily")
        assert "Indication if mentioned" in result

    def test_embeds_text_as_clinical_text_block(self, mixin):
        clinical = "Patient is on warfarin 5mg"
        result = mixin._build_extraction_prompt(clinical)
        assert f"Clinical Text:\n{clinical}\n" in result

    def test_no_context_does_not_contain_additional_context_label(self, mixin):
        result = mixin._build_extraction_prompt("text without context")
        assert "Additional Context:" not in result

    def test_empty_text_still_contains_required_structure(self, mixin):
        result = mixin._build_extraction_prompt("")
        assert "Extract all medications" in result
        assert "Extracted Medications:" in result

    def test_multiline_text_preserved_in_clinical_block(self, mixin):
        text = "Line one.\nLine two."
        result = mixin._build_extraction_prompt(text)
        assert f"Clinical Text:\n{text}\n" in result


# ---------------------------------------------------------------------------
# TestBuildInteractionPrompt  (10 tests)
# ---------------------------------------------------------------------------

class TestBuildInteractionPrompt:
    """Tests for _build_interaction_prompt(medications, context=None)."""

    def test_returns_string(self, mixin):
        result = mixin._build_interaction_prompt(["warfarin", "aspirin"])
        assert isinstance(result, str)

    def test_each_medication_listed_with_dash(self, mixin):
        meds = ["warfarin", "aspirin", "metoprolol"]
        result = mixin._build_interaction_prompt(meds)
        for med in meds:
            assert f"- {med}" in result

    def test_contains_high_priority(self, mixin):
        result = mixin._build_interaction_prompt(["warfarin", "aspirin"])
        assert "HIGH PRIORITY" in result

    def test_contains_moderate_priority(self, mixin):
        result = mixin._build_interaction_prompt(["warfarin", "aspirin"])
        assert "MODERATE PRIORITY" in result

    def test_contains_low_priority(self, mixin):
        result = mixin._build_interaction_prompt(["warfarin", "aspirin"])
        assert "LOW PRIORITY" in result

    def test_contains_actionable_recommendations(self, mixin):
        result = mixin._build_interaction_prompt(["warfarin", "aspirin"])
        assert "ACTIONABLE RECOMMENDATIONS" in result

    def test_contains_patient_counseling(self, mixin):
        result = mixin._build_interaction_prompt(["warfarin", "aspirin"])
        assert "PATIENT COUNSELING" in result

    def test_with_context_prepended(self, mixin):
        result = mixin._build_interaction_prompt(["warfarin"], context="Post-op patient")
        assert result.startswith("Additional Context: Post-op patient")

    def test_without_context_no_additional_context_label(self, mixin):
        result = mixin._build_interaction_prompt(["warfarin", "aspirin"])
        assert "Additional Context:" not in result

    def test_single_medication_still_contains_structure(self, mixin):
        result = mixin._build_interaction_prompt(["metformin"])
        assert "- metformin" in result
        assert "HIGH PRIORITY" in result

    def test_empty_medication_list_still_returns_structure(self, mixin):
        result = mixin._build_interaction_prompt([])
        assert "HIGH PRIORITY" in result
        assert "ACTIONABLE RECOMMENDATIONS" in result


# ---------------------------------------------------------------------------
# TestBuildPrescriptionPrompt  (12 tests)
# ---------------------------------------------------------------------------

class TestBuildPrescriptionPrompt:
    """Tests for _build_prescription_prompt(medication, patient_info, indication, context=None)."""

    def test_returns_string(self, mixin):
        result = mixin._build_prescription_prompt(
            {"name": "lisinopril"}, {"age": 55}, "hypertension"
        )
        assert isinstance(result, str)

    def test_contains_medication_name(self, mixin):
        result = mixin._build_prescription_prompt({"name": "lisinopril"}, {}, "hypertension")
        assert "Medication: lisinopril" in result

    def test_missing_name_key_uses_unknown(self, mixin):
        result = mixin._build_prescription_prompt({}, {}, "")
        assert "Medication: Unknown" in result

    def test_with_indication_shows_indication(self, mixin):
        result = mixin._build_prescription_prompt({"name": "lisinopril"}, {}, "hypertension")
        assert "Indication: hypertension" in result

    def test_empty_indication_not_in_output(self, mixin):
        result = mixin._build_prescription_prompt({"name": "metformin"}, {}, "")
        assert "Indication:" not in result

    def test_with_patient_info_shows_header(self, mixin):
        result = mixin._build_prescription_prompt(
            {"name": "metformin"}, {"age": 50, "weight": "70kg"}, "T2DM"
        )
        assert "Patient Information:" in result

    def test_patient_info_key_value_pairs(self, mixin):
        result = mixin._build_prescription_prompt(
            {"name": "metformin"}, {"age": 50, "weight": "70kg"}, "T2DM"
        )
        assert "- age: 50" in result
        assert "- weight: 70kg" in result

    def test_empty_patient_info_no_patient_information_header(self, mixin):
        result = mixin._build_prescription_prompt({"name": "metformin"}, {}, "T2DM")
        assert "Patient Information:" not in result

    def test_contains_exact_dosing_with_units(self, mixin):
        result = mixin._build_prescription_prompt({"name": "metformin"}, {}, "T2DM")
        assert "Exact dosing with units" in result

    def test_contains_route_of_administration(self, mixin):
        result = mixin._build_prescription_prompt({"name": "metformin"}, {}, "T2DM")
        assert "Route of administration" in result

    def test_contains_frequency_and_timing(self, mixin):
        result = mixin._build_prescription_prompt({"name": "metformin"}, {}, "T2DM")
        assert "Frequency and timing" in result

    def test_contains_duration_of_treatment(self, mixin):
        result = mixin._build_prescription_prompt({"name": "metformin"}, {}, "T2DM")
        assert "Duration of treatment" in result

    def test_ends_with_prescription(self, mixin):
        result = mixin._build_prescription_prompt({"name": "metformin"}, {}, "T2DM")
        assert result.endswith("Prescription:")

    def test_with_context_prepended(self, mixin):
        result = mixin._build_prescription_prompt(
            {"name": "lisinopril"}, {}, "HTN", context="Renal patient"
        )
        assert result.startswith("Additional Context: Renal patient")

    def test_without_context_no_additional_context_label(self, mixin):
        result = mixin._build_prescription_prompt({"name": "metformin"}, {}, "T2DM")
        assert "Additional Context:" not in result


# ---------------------------------------------------------------------------
# TestBuildDosingPrompt  (15 tests: basic, with egfr, with hepatic, both)
# ---------------------------------------------------------------------------

class TestBuildDosingPrompt:
    """Tests for _build_dosing_prompt(medication, patient_factors, context=None)."""

    def _base_med(self):
        return {"name": "vancomycin", "dose": "1g", "frequency": "q12h"}

    # basic
    def test_returns_string(self, mixin):
        result = mixin._build_dosing_prompt(self._base_med(), {})
        assert isinstance(result, str)

    def test_contains_validate_dosing_phrase(self, mixin):
        result = mixin._build_dosing_prompt(self._base_med(), {})
        assert "Validate the following medication dosing:" in result

    def test_contains_medication_name(self, mixin):
        result = mixin._build_dosing_prompt(self._base_med(), {})
        assert "Medication: vancomycin" in result

    def test_contains_dose(self, mixin):
        result = mixin._build_dosing_prompt(self._base_med(), {})
        assert "Dose: 1g" in result

    def test_contains_frequency(self, mixin):
        result = mixin._build_dosing_prompt(self._base_med(), {})
        assert "Frequency: q12h" in result

    def test_contains_dosing_assessment(self, mixin):
        result = mixin._build_dosing_prompt(self._base_med(), {})
        assert "DOSING ASSESSMENT" in result

    def test_contains_actionable_recommendations(self, mixin):
        result = mixin._build_dosing_prompt(self._base_med(), {})
        assert "ACTIONABLE RECOMMENDATIONS" in result

    def test_contains_monitoring_requirements(self, mixin):
        result = mixin._build_dosing_prompt(self._base_med(), {})
        assert "MONITORING REQUIREMENTS" in result

    def test_contains_summary(self, mixin):
        result = mixin._build_dosing_prompt(self._base_med(), {})
        assert "SUMMARY" in result

    # with egfr
    def test_with_egfr_adds_renal_section(self, mixin):
        result = mixin._build_dosing_prompt(self._base_med(), {"egfr": 25})
        assert "RENAL DOSE ADJUSTMENT" in result

    def test_with_egfr_shows_egfr_value_in_section_header(self, mixin):
        result = mixin._build_dosing_prompt(self._base_med(), {"egfr": 25})
        assert "eGFR: 25 mL/min" in result

    def test_with_egfr_contains_ckd_stage_table(self, mixin):
        result = mixin._build_dosing_prompt(self._base_med(), {"egfr": 25})
        assert "CKD Stage" in result

    def test_without_egfr_no_renal_section(self, mixin):
        result = mixin._build_dosing_prompt(self._base_med(), {})
        assert "RENAL DOSE ADJUSTMENT" not in result

    # with hepatic
    def test_with_hepatic_function_adds_hepatic_section(self, mixin):
        result = mixin._build_dosing_prompt(self._base_med(), {"hepatic_function": "Child-Pugh B"})
        assert "HEPATIC DOSE ADJUSTMENT" in result

    def test_with_hepatic_function_shows_value_in_section_header(self, mixin):
        result = mixin._build_dosing_prompt(self._base_med(), {"hepatic_function": "Child-Pugh B"})
        assert "Child-Pugh B" in result

    def test_with_hepatic_contains_child_pugh_classification(self, mixin):
        result = mixin._build_dosing_prompt(self._base_med(), {"hepatic_function": "Child-Pugh A"})
        assert "Child-Pugh Classification" in result

    def test_without_hepatic_function_no_hepatic_section(self, mixin):
        result = mixin._build_dosing_prompt(self._base_med(), {})
        assert "HEPATIC DOSE ADJUSTMENT" not in result

    # both
    def test_with_both_egfr_and_hepatic_both_sections_present(self, mixin):
        result = mixin._build_dosing_prompt(
            self._base_med(),
            {"egfr": 20, "hepatic_function": "Child-Pugh C"}
        )
        assert "RENAL DOSE ADJUSTMENT" in result
        assert "HEPATIC DOSE ADJUSTMENT" in result

    def test_with_context_prepended(self, mixin):
        result = mixin._build_dosing_prompt(self._base_med(), {}, context="ICU patient")
        assert result.startswith("Additional Context: ICU patient")

    def test_without_context_no_additional_context_label(self, mixin):
        result = mixin._build_dosing_prompt(self._base_med(), {})
        assert "Additional Context:" not in result

    def test_indication_in_medication_dict_included(self, mixin):
        med = {"name": "amoxicillin", "dose": "500mg", "frequency": "tid", "indication": "pneumonia"}
        result = mixin._build_dosing_prompt(med, {})
        assert "Indication: pneumonia" in result

    def test_patient_factors_listed_as_key_value_pairs(self, mixin):
        result = mixin._build_dosing_prompt(self._base_med(), {"age": 72, "weight_kg": 65})
        assert "- age: 72" in result
        assert "- weight_kg: 65" in result


# ---------------------------------------------------------------------------
# TestBuildAlternativesPrompt  (10 tests)
# ---------------------------------------------------------------------------

class TestBuildAlternativesPrompt:
    """Tests for _build_alternatives_prompt(current_medication, reason, patient_factors, context=None)."""

    def test_returns_string(self, mixin):
        result = mixin._build_alternatives_prompt(
            {"name": "atorvastatin"}, "muscle pain", {}
        )
        assert isinstance(result, str)

    def test_contains_current_medication_name(self, mixin):
        result = mixin._build_alternatives_prompt({"name": "atorvastatin"}, "muscle pain", {})
        assert "Current Medication: atorvastatin" in result

    def test_missing_name_key_uses_unknown(self, mixin):
        result = mixin._build_alternatives_prompt({}, "side effects", {})
        assert "Current Medication: Unknown" in result

    def test_contains_reason_for_change(self, mixin):
        result = mixin._build_alternatives_prompt({"name": "atorvastatin"}, "myopathy", {})
        assert "Reason for Change: myopathy" in result

    def test_contains_alternative_label(self, mixin):
        result = mixin._build_alternatives_prompt({"name": "atorvastatin"}, "myopathy", {})
        assert "Alternative" in result

    def test_with_patient_factors_shows_key_value_pairs(self, mixin):
        result = mixin._build_alternatives_prompt(
            {"name": "atorvastatin"}, "myopathy", {"age": 70, "egfr": 45}
        )
        assert "- age: 70" in result
        assert "- egfr: 45" in result

    def test_empty_patient_factors_no_patient_factors_header(self, mixin):
        result = mixin._build_alternatives_prompt({"name": "atorvastatin"}, "myopathy", {})
        assert "Patient Factors:" not in result

    def test_contains_switching_instructions(self, mixin):
        result = mixin._build_alternatives_prompt({"name": "atorvastatin"}, "myopathy", {})
        assert "Switching Instructions" in result

    def test_contains_evidence_guideline_support(self, mixin):
        result = mixin._build_alternatives_prompt({"name": "atorvastatin"}, "myopathy", {})
        assert "Evidence" in result or "Guideline" in result

    def test_with_context_prepended(self, mixin):
        result = mixin._build_alternatives_prompt(
            {"name": "atorvastatin"}, "myopathy", {}, context="Statin intolerance"
        )
        assert result.startswith("Additional Context: Statin intolerance")

    def test_without_context_no_additional_context_label(self, mixin):
        result = mixin._build_alternatives_prompt({"name": "atorvastatin"}, "myopathy", {})
        assert "Additional Context:" not in result


# ---------------------------------------------------------------------------
# TestFormatPatientContext  (20 tests)
# ---------------------------------------------------------------------------

class TestFormatPatientContext:
    """Tests for _format_patient_context(patient_context)."""

    def test_empty_dict_returns_empty_string(self, mixin):
        assert mixin._format_patient_context({}) == ""

    def test_non_empty_context_returns_non_empty_string(self, mixin):
        result = mixin._format_patient_context({"age": 30})
        assert result != ""

    def test_contains_patient_factors_header(self, mixin):
        result = mixin._format_patient_context({"age": 30})
        assert "PATIENT FACTORS" in result

    # age
    def test_age_shown_in_years(self, mixin):
        result = mixin._format_patient_context({"age": 45})
        assert "- Age: 45 years" in result

    def test_age_11_shows_pediatric(self, mixin):
        result = mixin._format_patient_context({"age": 11})
        assert "PEDIATRIC" in result

    def test_age_0_shows_pediatric(self, mixin):
        result = mixin._format_patient_context({"age": 0})
        assert "PEDIATRIC" in result

    def test_age_12_does_not_show_pediatric(self, mixin):
        result = mixin._format_patient_context({"age": 12})
        assert "PEDIATRIC" not in result

    def test_age_65_shows_geriatric(self, mixin):
        result = mixin._format_patient_context({"age": 65})
        assert "GERIATRIC" in result

    def test_age_64_does_not_show_geriatric(self, mixin):
        result = mixin._format_patient_context({"age": 64})
        assert "GERIATRIC" not in result

    def test_age_40_shows_neither_flag(self, mixin):
        result = mixin._format_patient_context({"age": 40})
        assert "PEDIATRIC" not in result
        assert "GERIATRIC" not in result

    # weight_kg
    def test_weight_shown_in_kg(self, mixin):
        result = mixin._format_patient_context({"weight_kg": 70})
        assert "- Weight: 70 kg" in result

    def test_weight_below_50_shows_low_body_weight(self, mixin):
        result = mixin._format_patient_context({"weight_kg": 45})
        assert "Low body weight" in result

    def test_weight_exactly_50_does_not_show_low_body_weight(self, mixin):
        result = mixin._format_patient_context({"weight_kg": 50})
        assert "Low body weight" not in result

    def test_weight_above_50_does_not_show_low_body_weight(self, mixin):
        result = mixin._format_patient_context({"weight_kg": 80})
        assert "Low body weight" not in result

    # egfr
    def test_egfr_shown_with_units(self, mixin):
        result = mixin._format_patient_context({"egfr": 55})
        assert "- eGFR: 55 mL/min" in result

    def test_egfr_below_30_shows_severe_renal(self, mixin):
        result = mixin._format_patient_context({"egfr": 20})
        assert "SEVERE renal" in result

    def test_egfr_exactly_30_shows_moderate_renal(self, mixin):
        # 30 is not < 30, so it falls to the elif egfr < 60 branch
        result = mixin._format_patient_context({"egfr": 30})
        assert "MODERATE renal" in result

    def test_egfr_59_shows_moderate_renal(self, mixin):
        result = mixin._format_patient_context({"egfr": 59})
        assert "MODERATE renal" in result

    def test_egfr_60_shows_mild_renal(self, mixin):
        # 60 is not < 60, so it falls to elif egfr < 90 branch
        result = mixin._format_patient_context({"egfr": 60})
        assert "Mild renal" in result

    def test_egfr_89_shows_mild_renal(self, mixin):
        result = mixin._format_patient_context({"egfr": 89})
        assert "Mild renal" in result

    def test_egfr_90_shows_no_severity_flag(self, mixin):
        result = mixin._format_patient_context({"egfr": 90})
        assert "SEVERE renal" not in result
        assert "MODERATE renal" not in result
        assert "Mild renal" not in result

    def test_egfr_29_shows_severe_renal(self, mixin):
        result = mixin._format_patient_context({"egfr": 29})
        assert "SEVERE renal" in result

    # hepatic_function
    def test_hepatic_function_value_shown(self, mixin):
        result = mixin._format_patient_context({"hepatic_function": "Child-Pugh A"})
        assert "- Hepatic function: Child-Pugh A" in result

    def test_child_pugh_c_shows_severe_hepatic(self, mixin):
        result = mixin._format_patient_context({"hepatic_function": "Child-Pugh C"})
        assert "SEVERE hepatic" in result

    def test_child_pugh_b_shows_moderate_hepatic(self, mixin):
        result = mixin._format_patient_context({"hepatic_function": "Child-Pugh B"})
        assert "MODERATE hepatic" in result

    def test_child_pugh_a_shows_mild_hepatic(self, mixin):
        result = mixin._format_patient_context({"hepatic_function": "Child-Pugh A"})
        assert "Mild hepatic" in result

    # allergies
    def test_allergies_listed_joined(self, mixin):
        result = mixin._format_patient_context({"allergies": ["penicillin", "sulfa"]})
        assert "penicillin" in result
        assert "sulfa" in result

    def test_allergies_cross_reactivity_warning_present(self, mixin):
        result = mixin._format_patient_context({"allergies": ["penicillin"]})
        assert "CHECK" in result or "cross-reactivity" in result.lower()

    def test_empty_allergies_list_no_allergy_line(self, mixin):
        result = mixin._format_patient_context({"allergies": []})
        assert "Known allergies" not in result

    def test_all_fields_combined_includes_all_flags(self, mixin):
        ctx = {
            "age": 70,
            "weight_kg": 45,
            "egfr": 25,
            "hepatic_function": "Child-Pugh C",
            "allergies": ["penicillin"],
        }
        result = mixin._format_patient_context(ctx)
        assert "GERIATRIC" in result
        assert "Low body weight" in result
        assert "SEVERE renal" in result
        assert "SEVERE hepatic" in result
        assert "penicillin" in result


# ---------------------------------------------------------------------------
# TestBuildComprehensivePrompt  (20 tests)
# ---------------------------------------------------------------------------

class TestBuildComprehensivePrompt:
    """Tests for _build_comprehensive_prompt(text, current_medications, context, patient_context)."""

    def test_returns_string(self, mixin):
        result = mixin._build_comprehensive_prompt("text", ["aspirin"])
        assert isinstance(result, str)

    def test_contains_comprehensive_medication_analysis(self, mixin):
        result = mixin._build_comprehensive_prompt("text", ["aspirin"])
        assert "comprehensive medication analysis" in result

    def test_contains_high_priority_issues(self, mixin):
        result = mixin._build_comprehensive_prompt("text", ["aspirin"])
        assert "HIGH PRIORITY ISSUES" in result

    def test_contains_moderate_priority_issues(self, mixin):
        result = mixin._build_comprehensive_prompt("text", ["aspirin"])
        assert "MODERATE PRIORITY ISSUES" in result

    def test_contains_low_priority_monitoring(self, mixin):
        result = mixin._build_comprehensive_prompt("text", ["aspirin"])
        assert "LOW PRIORITY" in result

    def test_contains_therapeutic_drug_monitoring(self, mixin):
        result = mixin._build_comprehensive_prompt("text", ["aspirin"])
        assert "THERAPEUTIC DRUG MONITORING" in result

    def test_contains_cost_considerations(self, mixin):
        result = mixin._build_comprehensive_prompt("text", ["aspirin"])
        assert "COST CONSIDERATIONS" in result

    def test_medications_listed_with_dash(self, mixin):
        meds = ["aspirin", "metformin", "lisinopril"]
        result = mixin._build_comprehensive_prompt("text", meds)
        for med in meds:
            assert f"- {med}" in result

    def test_text_embedded_as_clinical_text_block(self, mixin):
        clinical = "Patient presents with chest pain"
        result = mixin._build_comprehensive_prompt(clinical, [])
        assert f"CLINICAL TEXT:\n{clinical}" in result

    def test_with_context_appears_in_output(self, mixin):
        result = mixin._build_comprehensive_prompt("text", [], context="ED visit")
        assert "Additional Context: ED visit" in result

    def test_without_context_no_additional_context_label(self, mixin):
        result = mixin._build_comprehensive_prompt("text", [])
        assert "Additional Context:" not in result

    # patient_context with egfr
    def test_patient_context_with_egfr_adds_renal_dose_adjustments(self, mixin):
        result = mixin._build_comprehensive_prompt(
            "text", ["vancomycin"], patient_context={"egfr": 30}
        )
        assert "RENAL DOSE ADJUSTMENTS" in result

    def test_patient_context_with_egfr_shows_value_in_header(self, mixin):
        result = mixin._build_comprehensive_prompt(
            "text", ["vancomycin"], patient_context={"egfr": 30}
        )
        assert "eGFR: 30 mL/min" in result

    def test_no_patient_context_no_renal_section(self, mixin):
        result = mixin._build_comprehensive_prompt("text", ["vancomycin"])
        assert "RENAL DOSE ADJUSTMENTS" not in result

    def test_patient_context_without_egfr_no_renal_section(self, mixin):
        result = mixin._build_comprehensive_prompt(
            "text", ["vancomycin"], patient_context={"age": 50}
        )
        assert "RENAL DOSE ADJUSTMENTS" not in result

    # patient_context with hepatic_function
    def test_patient_context_with_hepatic_adds_hepatic_dose_adjustments(self, mixin):
        result = mixin._build_comprehensive_prompt(
            "text", ["metoprolol"], patient_context={"hepatic_function": "Child-Pugh B"}
        )
        assert "HEPATIC DOSE ADJUSTMENTS" in result

    def test_patient_context_with_hepatic_shows_value_in_header(self, mixin):
        result = mixin._build_comprehensive_prompt(
            "text", ["metoprolol"], patient_context={"hepatic_function": "Child-Pugh B"}
        )
        assert "Child-Pugh B" in result

    def test_no_patient_context_no_hepatic_section(self, mixin):
        result = mixin._build_comprehensive_prompt("text", ["metoprolol"])
        assert "HEPATIC DOSE ADJUSTMENTS" not in result

    # de-prescribing triggers
    def test_age_65_triggers_deprescribing(self, mixin):
        result = mixin._build_comprehensive_prompt(
            "text", ["aspirin"], patient_context={"age": 65}
        )
        assert "DE-PRESCRIBING" in result

    def test_age_80_triggers_deprescribing(self, mixin):
        result = mixin._build_comprehensive_prompt(
            "text", ["aspirin"], patient_context={"age": 80}
        )
        assert "DE-PRESCRIBING" in result

    def test_age_64_few_meds_no_deprescribing(self, mixin):
        result = mixin._build_comprehensive_prompt(
            "text", ["aspirin", "metformin"], patient_context={"age": 64}
        )
        assert "DE-PRESCRIBING" not in result

    def test_six_medications_triggers_deprescribing(self, mixin):
        meds = ["aspirin", "metformin", "lisinopril", "atorvastatin", "omeprazole", "amlodipine"]
        result = mixin._build_comprehensive_prompt("text", meds, patient_context={"age": 50})
        assert "DE-PRESCRIBING" in result

    def test_five_medications_young_patient_no_deprescribing(self, mixin):
        meds = ["aspirin", "metformin", "lisinopril", "atorvastatin", "omeprazole"]
        result = mixin._build_comprehensive_prompt("text", meds, patient_context={"age": 40})
        assert "DE-PRESCRIBING" not in result

    def test_no_patient_context_no_deprescribing(self, mixin):
        meds = ["aspirin", "metformin", "lisinopril", "atorvastatin", "omeprazole", "amlodipine"]
        result = mixin._build_comprehensive_prompt("text", meds)
        assert "DE-PRESCRIBING" not in result

    def test_patient_context_included_via_format_patient_context(self, mixin):
        result = mixin._build_comprehensive_prompt(
            "text", [], patient_context={"age": 70}
        )
        assert "PATIENT FACTORS" in result

    def test_both_egfr_and_hepatic_both_sections_present(self, mixin):
        result = mixin._build_comprehensive_prompt(
            "text",
            ["vancomycin"],
            patient_context={"egfr": 20, "hepatic_function": "Child-Pugh C"}
        )
        assert "RENAL DOSE ADJUSTMENTS" in result
        assert "HEPATIC DOSE ADJUSTMENTS" in result

    def test_empty_text_still_produces_full_structure(self, mixin):
        result = mixin._build_comprehensive_prompt("", [])
        assert "comprehensive medication analysis" in result
        assert "HIGH PRIORITY ISSUES" in result

    def test_contains_actionable_recommendations_section(self, mixin):
        result = mixin._build_comprehensive_prompt("text", [])
        assert "ACTIONABLE RECOMMENDATIONS" in result

    def test_contains_summary_section(self, mixin):
        result = mixin._build_comprehensive_prompt("text", [])
        assert "SUMMARY" in result
