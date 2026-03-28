"""Tests for ai.agents.medication_prompts — MedicationPromptMixin."""

import pytest
from ai.agents.medication_prompts import MedicationPromptMixin


class ConcretePromptBuilder(MedicationPromptMixin):
    """Concrete class so we can instantiate the mixin."""
    pass


@pytest.fixture
def builder():
    return ConcretePromptBuilder()


# ── _build_extraction_prompt ──────────────────────────────────────────────────

class TestBuildExtractionPrompt:
    def test_returns_string(self, builder):
        result = builder._build_extraction_prompt("Patient takes aspirin 81mg daily.")
        assert isinstance(result, str)

    def test_includes_clinical_text(self, builder):
        result = builder._build_extraction_prompt("Metformin 500mg twice daily")
        assert "Metformin 500mg twice daily" in result

    def test_includes_extraction_label(self, builder):
        result = builder._build_extraction_prompt("Some text")
        assert "Extracted Medications:" in result

    def test_with_context_includes_context(self, builder):
        result = builder._build_extraction_prompt("text", context="Diabetic patient")
        assert "Diabetic patient" in result

    def test_without_context_no_context_label(self, builder):
        result = builder._build_extraction_prompt("text", context=None)
        assert "Additional Context:" not in result

    def test_mentions_dosage_fields(self, builder):
        result = builder._build_extraction_prompt("text")
        assert "Dosage" in result or "dosage" in result.lower()

    def test_mentions_frequency(self, builder):
        result = builder._build_extraction_prompt("text")
        assert "Frequency" in result or "frequency" in result.lower()


# ── _build_interaction_prompt ─────────────────────────────────────────────────

class TestBuildInteractionPrompt:
    def test_returns_string(self, builder):
        result = builder._build_interaction_prompt(["aspirin", "warfarin"])
        assert isinstance(result, str)

    def test_includes_all_medications(self, builder):
        result = builder._build_interaction_prompt(["metformin", "glipizide", "lisinopril"])
        assert "metformin" in result
        assert "glipizide" in result
        assert "lisinopril" in result

    def test_empty_list_safe(self, builder):
        result = builder._build_interaction_prompt([])
        assert isinstance(result, str)

    def test_with_context(self, builder):
        result = builder._build_interaction_prompt(["aspirin"], context="Cardiac patient")
        assert "Cardiac patient" in result

    def test_includes_priority_structure(self, builder):
        result = builder._build_interaction_prompt(["aspirin", "warfarin"])
        assert "HIGH PRIORITY" in result or "MODERATE" in result

    def test_includes_actionable_recommendations(self, builder):
        result = builder._build_interaction_prompt(["aspirin"])
        assert "ACTIONABLE" in result or "Recommendations" in result.upper()


# ── _build_prescription_prompt ────────────────────────────────────────────────

class TestBuildPrescriptionPrompt:
    def test_returns_string(self, builder):
        result = builder._build_prescription_prompt(
            {"name": "Lisinopril", "dose": "10mg"},
            {"age": 60, "weight_kg": 75},
            "hypertension"
        )
        assert isinstance(result, str)

    def test_includes_medication_name(self, builder):
        result = builder._build_prescription_prompt(
            {"name": "Metformin"},
            {},
            "diabetes"
        )
        assert "Metformin" in result

    def test_includes_indication(self, builder):
        result = builder._build_prescription_prompt(
            {"name": "Aspirin"},
            {},
            "secondary prevention"
        )
        assert "secondary prevention" in result

    def test_includes_patient_info_when_provided(self, builder):
        result = builder._build_prescription_prompt(
            {"name": "Aspirin"},
            {"age": 65, "weight_kg": 70},
            "pain"
        )
        assert "age" in result.lower() or "65" in result

    def test_no_indication_handled_gracefully(self, builder):
        result = builder._build_prescription_prompt({"name": "Med"}, {}, "")
        assert isinstance(result, str)

    def test_with_context(self, builder):
        result = builder._build_prescription_prompt(
            {"name": "Med"},
            {},
            "indication",
            context="Renal impairment"
        )
        assert "Renal impairment" in result

    def test_includes_prescription_label(self, builder):
        result = builder._build_prescription_prompt({"name": "Med"}, {}, "ind")
        assert "Prescription:" in result

    def test_unknown_medication_uses_fallback(self, builder):
        result = builder._build_prescription_prompt({}, {}, "ind")
        assert "Unknown" in result


# ── _build_dosing_prompt ──────────────────────────────────────────────────────

class TestBuildDosingPrompt:
    def test_returns_string(self, builder):
        result = builder._build_dosing_prompt(
            {"name": "Metformin", "dose": "500mg", "frequency": "BID"},
            {"egfr": 45}
        )
        assert isinstance(result, str)

    def test_includes_medication_name(self, builder):
        result = builder._build_dosing_prompt(
            {"name": "Vancomycin", "dose": "1g", "frequency": "Q12H"},
            {}
        )
        assert "Vancomycin" in result

    def test_includes_egfr_section_when_provided(self, builder):
        result = builder._build_dosing_prompt(
            {"name": "Med", "dose": "100mg", "frequency": "daily"},
            {"egfr": 30}
        )
        assert "RENAL DOSE ADJUSTMENT" in result or "eGFR" in result

    def test_no_egfr_section_when_absent(self, builder):
        result = builder._build_dosing_prompt(
            {"name": "Med", "dose": "100mg", "frequency": "daily"},
            {"weight_kg": 70}
        )
        assert "RENAL DOSE ADJUSTMENT" not in result

    def test_includes_hepatic_section_when_provided(self, builder):
        result = builder._build_dosing_prompt(
            {"name": "Med", "dose": "100mg", "frequency": "daily"},
            {"hepatic_function": "Child-Pugh B"}
        )
        assert "HEPATIC DOSE ADJUSTMENT" in result

    def test_no_hepatic_section_when_absent(self, builder):
        result = builder._build_dosing_prompt(
            {"name": "Med", "dose": "100mg", "frequency": "daily"},
            {}
        )
        assert "HEPATIC DOSE ADJUSTMENT" not in result

    def test_with_context(self, builder):
        result = builder._build_dosing_prompt(
            {"name": "Med", "dose": "100mg", "frequency": "daily"},
            {},
            context="Post-transplant patient"
        )
        assert "Post-transplant patient" in result

    def test_includes_assessment_section(self, builder):
        result = builder._build_dosing_prompt(
            {"name": "Med", "dose": "100mg", "frequency": "daily"},
            {}
        )
        assert "ASSESSMENT" in result or "assessment" in result.lower()


# ── _build_alternatives_prompt ────────────────────────────────────────────────

class TestBuildAlternativesPrompt:
    def test_returns_string(self, builder):
        result = builder._build_alternatives_prompt(
            {"name": "Atenolol"},
            "side effects",
            {"age": 55}
        )
        assert isinstance(result, str)

    def test_includes_current_medication(self, builder):
        result = builder._build_alternatives_prompt(
            {"name": "Metoprolol"},
            "poor tolerance",
            {}
        )
        assert "Metoprolol" in result

    def test_includes_reason_for_change(self, builder):
        result = builder._build_alternatives_prompt(
            {"name": "Med"},
            "bradycardia",
            {}
        )
        assert "bradycardia" in result

    def test_includes_patient_factors(self, builder):
        result = builder._build_alternatives_prompt(
            {"name": "Med"},
            "reason",
            {"age": 70, "weight_kg": 60}
        )
        assert "70" in result or "weight" in result.lower()

    def test_empty_patient_factors_safe(self, builder):
        result = builder._build_alternatives_prompt({"name": "Med"}, "reason", {})
        assert isinstance(result, str)

    def test_with_context(self, builder):
        result = builder._build_alternatives_prompt(
            {"name": "Med"},
            "reason",
            {},
            context="Pregnancy"
        )
        assert "Pregnancy" in result

    def test_mentions_alternatives_count(self, builder):
        result = builder._build_alternatives_prompt({"name": "Med"}, "reason", {})
        assert "3" in result or "alternative" in result.lower()


# ── _format_patient_context ───────────────────────────────────────────────────

class TestFormatPatientContext:
    def test_empty_dict_returns_empty_string(self, builder):
        result = builder._format_patient_context({})
        assert result == ""

    def test_none_equivalent_handled(self, builder):
        result = builder._format_patient_context({})
        assert result == ""

    def test_age_included(self, builder):
        result = builder._format_patient_context({"age": 45})
        assert "45" in result

    def test_pediatric_flag_when_age_lt_12(self, builder):
        result = builder._format_patient_context({"age": 8})
        assert "PEDIATRIC" in result or "pediatric" in result.lower()

    def test_geriatric_flag_when_age_ge_65(self, builder):
        result = builder._format_patient_context({"age": 70})
        assert "GERIATRIC" in result or "geriatric" in result.lower()

    def test_adult_no_age_flag(self, builder):
        result = builder._format_patient_context({"age": 45})
        assert "PEDIATRIC" not in result
        assert "GERIATRIC" not in result

    def test_weight_included(self, builder):
        result = builder._format_patient_context({"weight_kg": 65})
        assert "65" in result

    def test_low_weight_flag(self, builder):
        result = builder._format_patient_context({"weight_kg": 40})
        assert "Low body weight" in result or "dose reduction" in result.lower()

    def test_egfr_severe_flag(self, builder):
        result = builder._format_patient_context({"egfr": 20})
        assert "SEVERE" in result

    def test_egfr_moderate_flag(self, builder):
        result = builder._format_patient_context({"egfr": 45})
        assert "MODERATE" in result

    def test_egfr_mild_note(self, builder):
        result = builder._format_patient_context({"egfr": 75})
        assert "Mild" in result or "mild" in result.lower()

    def test_hepatic_child_pugh_c_flag(self, builder):
        result = builder._format_patient_context({"hepatic_function": "Child-Pugh C"})
        assert "SEVERE" in result

    def test_hepatic_child_pugh_b_flag(self, builder):
        result = builder._format_patient_context({"hepatic_function": "Child-Pugh B"})
        assert "MODERATE" in result

    def test_hepatic_child_pugh_a_note(self, builder):
        result = builder._format_patient_context({"hepatic_function": "Child-Pugh A"})
        assert "Mild" in result

    def test_allergies_included(self, builder):
        result = builder._format_patient_context({"allergies": ["penicillin", "sulfa"]})
        assert "penicillin" in result
        assert "sulfa" in result

    def test_empty_allergies_not_shown(self, builder):
        result = builder._format_patient_context({"allergies": []})
        assert "allergies" not in result.lower() or "Known allergies" not in result


# ── _build_comprehensive_prompt ───────────────────────────────────────────────

class TestBuildComprehensivePrompt:
    def test_returns_string(self, builder):
        result = builder._build_comprehensive_prompt(
            "Patient has diabetes and hypertension",
            ["metformin", "lisinopril"]
        )
        assert isinstance(result, str)

    def test_includes_clinical_text(self, builder):
        result = builder._build_comprehensive_prompt("chest pain note", [])
        assert "chest pain note" in result

    def test_includes_current_medications(self, builder):
        result = builder._build_comprehensive_prompt("text", ["aspirin", "warfarin"])
        assert "aspirin" in result
        assert "warfarin" in result

    def test_with_context(self, builder):
        result = builder._build_comprehensive_prompt("text", [], context="ICU patient")
        assert "ICU patient" in result

    def test_includes_renal_section_when_egfr(self, builder):
        result = builder._build_comprehensive_prompt(
            "text", [], patient_context={"egfr": 25}
        )
        assert "RENAL DOSE ADJUSTMENTS" in result

    def test_no_renal_section_without_egfr(self, builder):
        result = builder._build_comprehensive_prompt("text", [], patient_context={})
        assert "RENAL DOSE ADJUSTMENTS" not in result

    def test_includes_hepatic_section_when_provided(self, builder):
        result = builder._build_comprehensive_prompt(
            "text", [], patient_context={"hepatic_function": "Child-Pugh B"}
        )
        assert "HEPATIC DOSE ADJUSTMENTS" in result

    def test_deprescribing_section_for_elderly(self, builder):
        result = builder._build_comprehensive_prompt(
            "text", ["aspirin"], patient_context={"age": 70}
        )
        assert "DE-PRESCRIBING" in result

    def test_deprescribing_section_for_polypharmacy(self, builder):
        meds = ["med1", "med2", "med3", "med4", "med5", "med6"]
        result = builder._build_comprehensive_prompt("text", meds, patient_context={"age": 50})
        assert "DE-PRESCRIBING" in result

    def test_no_deprescribing_for_young_patient_few_meds(self, builder):
        result = builder._build_comprehensive_prompt(
            "text", ["aspirin"], patient_context={"age": 40}
        )
        assert "DE-PRESCRIBING" not in result

    def test_includes_actionable_recommendations(self, builder):
        result = builder._build_comprehensive_prompt("text", [])
        assert "ACTIONABLE RECOMMENDATIONS" in result

    def test_includes_summary_section(self, builder):
        result = builder._build_comprehensive_prompt("text", [])
        assert "SUMMARY" in result

    def test_empty_text_and_meds_safe(self, builder):
        result = builder._build_comprehensive_prompt("", [])
        assert isinstance(result, str)
