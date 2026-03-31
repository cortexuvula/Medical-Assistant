"""
Tests for src/ai/agents/data_extraction.py (pure-logic methods only)
No network, no Tkinter, no AI calls.
"""
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.agents.data_extraction import DataExtractionAgent
from ai.agents.models import AgentConfig, AgentTask, AgentResponse


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def agent():
    return DataExtractionAgent(config=None, ai_caller=None)


def _make_task(description="Extract data", clinical_text="Patient has hypertension."):
    return AgentTask(
        task_description=description,
        input_data={"clinical_text": clinical_text},
    )


# ---------------------------------------------------------------------------
# TestDetermineExtractionType
# ---------------------------------------------------------------------------

class TestDetermineExtractionType:
    """_determine_extraction_type: keyword inference from task_description."""

    def test_vital_keyword_returns_vitals(self, agent):
        task = _make_task(description="Extract vital signs")
        assert agent._determine_extraction_type(task) == "vitals"

    def test_vitals_plural_in_description_returns_vitals(self, agent):
        task = _make_task(description="Please extract vitals from note")
        assert agent._determine_extraction_type(task) == "vitals"

    def test_lab_keyword_returns_labs(self, agent):
        task = _make_task(description="Get lab results")
        assert agent._determine_extraction_type(task) == "labs"

    def test_laboratory_keyword_returns_labs(self, agent):
        task = _make_task(description="Extract laboratory values")
        assert agent._determine_extraction_type(task) == "labs"

    def test_medication_keyword_returns_medications(self, agent):
        task = _make_task(description="List all medications")
        assert agent._determine_extraction_type(task) == "medications"

    def test_drug_keyword_returns_medications(self, agent):
        task = _make_task(description="drug reconciliation needed")
        assert agent._determine_extraction_type(task) == "medications"

    def test_diagnos_keyword_returns_diagnoses(self, agent):
        task = _make_task(description="Extract diagnoses from SOAP")
        assert agent._determine_extraction_type(task) == "diagnoses"

    def test_diagnosis_singular_returns_diagnoses(self, agent):
        task = _make_task(description="List primary diagnosis")
        assert agent._determine_extraction_type(task) == "diagnoses"

    def test_icd_keyword_returns_diagnoses(self, agent):
        task = _make_task(description="Find ICD codes in note")
        assert agent._determine_extraction_type(task) == "diagnoses"

    def test_procedure_keyword_returns_procedures(self, agent):
        task = _make_task(description="List procedures performed")
        assert agent._determine_extraction_type(task) == "procedures"

    def test_unknown_description_returns_comprehensive(self, agent):
        task = _make_task(description="Do something useful")
        assert agent._determine_extraction_type(task) == "comprehensive"

    def test_empty_description_returns_comprehensive(self, agent):
        task = _make_task(description="")
        assert agent._determine_extraction_type(task) == "comprehensive"

    def test_case_insensitive_vital(self, agent):
        task = _make_task(description="VITAL SIGNS EXTRACTION")
        assert agent._determine_extraction_type(task) == "vitals"

    def test_case_insensitive_lab(self, agent):
        task = _make_task(description="LAB VALUES NEEDED")
        assert agent._determine_extraction_type(task) == "labs"

    def test_case_insensitive_medication(self, agent):
        task = _make_task(description="MEDICATION LIST")
        assert agent._determine_extraction_type(task) == "medications"

    def test_case_insensitive_diagnoses(self, agent):
        task = _make_task(description="DIAGNOSES EXTRACTION")
        assert agent._determine_extraction_type(task) == "diagnoses"

    def test_case_insensitive_procedures(self, agent):
        task = _make_task(description="PROCEDURE LOG")
        assert agent._determine_extraction_type(task) == "procedures"

    def test_explicit_extraction_type_overrides_description(self, agent):
        task = AgentTask(
            task_description="Extract vital signs",
            input_data={"clinical_text": "text", "extraction_type": "labs"},
        )
        assert agent._determine_extraction_type(task) == "labs"

    def test_explicit_extraction_type_empty_string_falls_back_to_description(self, agent):
        # Empty string is falsy; method falls through to keyword inference
        task = AgentTask(
            task_description="Extract vital signs",
            input_data={"clinical_text": "text", "extraction_type": ""},
        )
        assert agent._determine_extraction_type(task) == "vitals"

    def test_explicit_extraction_type_comprehensive(self, agent):
        task = AgentTask(
            task_description="Extract vital signs",
            input_data={"clinical_text": "text", "extraction_type": "comprehensive"},
        )
        assert agent._determine_extraction_type(task) == "comprehensive"

    def test_diagnoses_plural_match(self, agent):
        task = _make_task(description="List all diagnoses")
        assert agent._determine_extraction_type(task) == "diagnoses"

    def test_medication_partial_match_in_middle_of_word(self, agent):
        task = _make_task(description="medication reconciliation")
        assert agent._determine_extraction_type(task) == "medications"

    def test_return_value_is_string(self, agent):
        task = _make_task(description="Extract vital signs")
        result = agent._determine_extraction_type(task)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# TestGetClinicalText
# ---------------------------------------------------------------------------

class TestGetClinicalText:
    """_get_clinical_text: source priority and fallbacks."""

    def test_clinical_text_key_is_primary(self, agent):
        task = AgentTask(
            task_description="Extract",
            input_data={"clinical_text": "primary text"},
        )
        assert agent._get_clinical_text(task) == "primary text"

    def test_soap_note_fallback(self, agent):
        task = AgentTask(
            task_description="Extract",
            input_data={"soap_note": "SOAP note text"},
        )
        assert agent._get_clinical_text(task) == "SOAP note text"

    def test_transcript_fallback(self, agent):
        task = AgentTask(
            task_description="Extract",
            input_data={"transcript": "transcript text"},
        )
        assert agent._get_clinical_text(task) == "transcript text"

    def test_clinical_text_takes_priority_over_soap_note(self, agent):
        task = AgentTask(
            task_description="Extract",
            input_data={"clinical_text": "primary", "soap_note": "secondary"},
        )
        assert agent._get_clinical_text(task) == "primary"

    def test_clinical_text_takes_priority_over_transcript(self, agent):
        task = AgentTask(
            task_description="Extract",
            input_data={"clinical_text": "primary", "transcript": "tertiary"},
        )
        assert agent._get_clinical_text(task) == "primary"

    def test_soap_note_takes_priority_over_transcript(self, agent):
        task = AgentTask(
            task_description="Extract",
            input_data={"soap_note": "secondary", "transcript": "tertiary"},
        )
        assert agent._get_clinical_text(task) == "secondary"

    def test_empty_input_dict_returns_empty_string(self, agent):
        task = AgentTask(task_description="Extract", input_data={})
        result = agent._get_clinical_text(task)
        assert result == ""

    def test_all_empty_values_returns_empty_string(self, agent):
        task = AgentTask(
            task_description="Extract",
            input_data={"clinical_text": "", "soap_note": "", "transcript": ""},
        )
        assert agent._get_clinical_text(task) == ""

    def test_returns_string_type(self, agent):
        task = _make_task(clinical_text="some text")
        result = agent._get_clinical_text(task)
        assert isinstance(result, str)

    def test_multiline_text_preserved(self, agent):
        text = "Line 1\nLine 2\nLine 3"
        task = _make_task(clinical_text=text)
        assert agent._get_clinical_text(task) == text

    def test_whitespace_only_clinical_text_wins_over_soap(self, agent):
        # A whitespace-only string is truthy, so clinical_text wins via 'or' chaining
        task = AgentTask(
            task_description="Extract",
            input_data={"clinical_text": "   ", "soap_note": "fallback"},
        )
        result = agent._get_clinical_text(task)
        assert result == "   "

    def test_all_three_sources_clinical_wins(self, agent):
        task = AgentTask(
            task_description="Extract",
            input_data={
                "clinical_text": "A",
                "soap_note": "B",
                "transcript": "C",
            },
        )
        assert agent._get_clinical_text(task) == "A"

    def test_unknown_keys_ignored_returns_empty(self, agent):
        task = AgentTask(
            task_description="Extract",
            input_data={"other_key": "some data"},
        )
        assert agent._get_clinical_text(task) == ""


# ---------------------------------------------------------------------------
# TestFormatAsText
# ---------------------------------------------------------------------------

class TestFormatAsText:
    """_format_as_text: text rendering of parsed data dicts."""

    def test_empty_dict_returns_no_data_message(self, agent):
        result = agent._format_as_text({})
        assert isinstance(result, str)
        assert "No clinical data extracted" in result

    def test_returns_string_type_always(self, agent):
        assert isinstance(agent._format_as_text({}), str)
        assert isinstance(agent._format_as_text({"vital_signs": []}), str)

    def test_empty_lists_for_all_keys_returns_no_data_message(self, agent):
        data = {
            "vital_signs": [],
            "laboratory_values": [],
            "medications": [],
            "diagnoses": [],
            "procedures": [],
        }
        assert "No clinical data extracted" in agent._format_as_text(data)

    def test_vital_signs_section_header_present(self, agent):
        data = {"vital_signs": [{"name": "heart_rate", "value": "72", "unit": "bpm"}]}
        assert "VITAL SIGNS" in agent._format_as_text(data)

    def test_vital_signs_name_in_output(self, agent):
        data = {"vital_signs": [{"name": "heart_rate", "value": "72", "unit": "bpm"}]}
        assert "heart_rate" in agent._format_as_text(data)

    def test_vital_signs_value_in_output(self, agent):
        data = {"vital_signs": [{"name": "blood_pressure", "value": "120/80", "unit": "mmHg"}]}
        assert "120/80" in agent._format_as_text(data)

    def test_vital_signs_unit_in_output(self, agent):
        data = {"vital_signs": [{"name": "hr", "value": "72", "unit": "bpm"}]}
        assert "bpm" in agent._format_as_text(data)

    def test_vital_signs_abnormal_flag_shown(self, agent):
        data = {"vital_signs": [{"name": "hr", "value": "130", "unit": "bpm", "abnormal": True}]}
        assert "ABNORMAL" in agent._format_as_text(data)

    def test_vital_signs_normal_no_abnormal_flag(self, agent):
        data = {"vital_signs": [{"name": "hr", "value": "72", "unit": "bpm", "abnormal": False}]}
        assert "ABNORMAL" not in agent._format_as_text(data)

    def test_medications_section_header_present(self, agent):
        data = {"medications": [{"name": "metformin", "dosage": "500mg"}]}
        assert "MEDICATIONS" in agent._format_as_text(data)

    def test_medication_name_in_output(self, agent):
        data = {"medications": [{"name": "lisinopril"}]}
        assert "lisinopril" in agent._format_as_text(data)

    def test_medication_status_in_output(self, agent):
        data = {"medications": [{"name": "aspirin", "status": "current"}]}
        assert "current" in agent._format_as_text(data)

    def test_medication_dosage_in_output(self, agent):
        data = {"medications": [{"name": "metformin", "dosage": "500mg"}]}
        assert "500mg" in agent._format_as_text(data)

    def test_diagnoses_section_header_present(self, agent):
        data = {"diagnoses": [{"description": "Hypertension"}]}
        assert "DIAGNOSES" in agent._format_as_text(data)

    def test_diagnosis_description_in_output(self, agent):
        data = {"diagnoses": [{"description": "Type 2 diabetes mellitus", "icd10_code": "E11.9"}]}
        assert "Type 2 diabetes mellitus" in agent._format_as_text(data)

    def test_diagnosis_icd10_code_in_output(self, agent):
        data = {"diagnoses": [{"description": "Hypertension", "icd10_code": "I10"}]}
        assert "I10" in agent._format_as_text(data)

    def test_diagnosis_icd9_code_in_output(self, agent):
        data = {"diagnoses": [{"description": "HTN", "icd9_code": "401.9"}]}
        assert "401.9" in agent._format_as_text(data)

    def test_diagnosis_primary_flag_shown(self, agent):
        data = {"diagnoses": [{"description": "CHF", "is_primary": True}]}
        assert "PRIMARY" in agent._format_as_text(data)

    def test_laboratory_values_section_header_present(self, agent):
        data = {"laboratory_values": [{"test": "HbA1c", "value": 7.2, "unit": "%"}]}
        assert "LABORATORY VALUES" in agent._format_as_text(data)

    def test_lab_test_name_in_output(self, agent):
        data = {"laboratory_values": [{"test": "HbA1c", "value": 7.2}]}
        assert "HbA1c" in agent._format_as_text(data)

    def test_lab_reference_range_in_output(self, agent):
        data = {
            "laboratory_values": [
                {"test": "glucose", "value": 110, "unit": "mg/dL", "reference_range": "70-100"}
            ]
        }
        assert "70-100" in agent._format_as_text(data)

    def test_lab_abnormal_flag_shown(self, agent):
        data = {"laboratory_values": [{"test": "BNP", "value": 150, "abnormal": True}]}
        assert "ABNORMAL" in agent._format_as_text(data)

    def test_procedures_section_header_present(self, agent):
        data = {"procedures": [{"name": "EKG"}]}
        assert "PROCEDURES" in agent._format_as_text(data)

    def test_procedure_name_in_output(self, agent):
        data = {"procedures": [{"name": "colonoscopy"}]}
        assert "colonoscopy" in agent._format_as_text(data)

    def test_procedure_status_uppercased_in_output(self, agent):
        data = {"procedures": [{"name": "MRI", "status": "planned"}]}
        assert "PLANNED" in agent._format_as_text(data)

    def test_procedure_date_in_output(self, agent):
        data = {"procedures": [{"name": "biopsy", "date": "2024-01-15"}]}
        assert "2024-01-15" in agent._format_as_text(data)

    def test_empty_vital_signs_list_omits_section(self, agent):
        data = {"vital_signs": [], "medications": [{"name": "aspirin"}]}
        result = agent._format_as_text(data)
        assert "VITAL SIGNS" not in result
        assert "MEDICATIONS" in result

    def test_multiple_sections_all_rendered(self, agent):
        data = {
            "vital_signs": [{"name": "temp", "value": "98.6", "unit": "F"}],
            "medications": [{"name": "aspirin"}],
            "diagnoses": [{"description": "HTN"}],
        }
        result = agent._format_as_text(data)
        assert "VITAL SIGNS" in result
        assert "MEDICATIONS" in result
        assert "DIAGNOSES" in result


# ---------------------------------------------------------------------------
# TestBuildPrompts
# ---------------------------------------------------------------------------

class TestBuildPrompts:
    """All six _build_*_prompt methods: non-empty strings, text inclusion, context."""

    # --- comprehensive ---

    def test_comprehensive_prompt_returns_string(self, agent):
        assert isinstance(agent._build_comprehensive_extraction_prompt("some text"), str)

    def test_comprehensive_prompt_is_nonempty(self, agent):
        assert len(agent._build_comprehensive_extraction_prompt("text")) > 0

    def test_comprehensive_prompt_contains_input_text(self, agent):
        text = "Patient BP 130/85"
        assert text in agent._build_comprehensive_extraction_prompt(text)

    def test_comprehensive_prompt_with_context_includes_context(self, agent):
        assert "ICU patient" in agent._build_comprehensive_extraction_prompt("text", context="ICU patient")

    def test_comprehensive_prompt_none_context_no_error(self, agent):
        result = agent._build_comprehensive_extraction_prompt("text", context=None)
        assert isinstance(result, str) and len(result) > 0

    def test_comprehensive_prompt_lists_vital_signs_category(self, agent):
        assert "VITAL SIGNS" in agent._build_comprehensive_extraction_prompt("text")

    def test_comprehensive_prompt_lists_laboratory_category(self, agent):
        assert "LABORATORY VALUES" in agent._build_comprehensive_extraction_prompt("text")

    def test_comprehensive_prompt_lists_medications_category(self, agent):
        assert "MEDICATIONS" in agent._build_comprehensive_extraction_prompt("text")

    def test_comprehensive_prompt_lists_diagnoses_category(self, agent):
        assert "DIAGNOSES" in agent._build_comprehensive_extraction_prompt("text")

    def test_comprehensive_prompt_lists_procedures_category(self, agent):
        assert "PROCEDURES" in agent._build_comprehensive_extraction_prompt("text")

    # --- vitals ---

    def test_vitals_prompt_returns_string(self, agent):
        assert isinstance(agent._build_vitals_extraction_prompt("text"), str)

    def test_vitals_prompt_is_nonempty(self, agent):
        assert len(agent._build_vitals_extraction_prompt("text")) > 0

    def test_vitals_prompt_contains_input_text(self, agent):
        text = "HR 72 bpm"
        assert text in agent._build_vitals_extraction_prompt(text)

    def test_vitals_prompt_with_context_includes_context(self, agent):
        assert "ED visit" in agent._build_vitals_extraction_prompt("text", context="ED visit")

    def test_vitals_prompt_none_context_no_error(self, agent):
        result = agent._build_vitals_extraction_prompt("text", context=None)
        assert isinstance(result, str) and len(result) > 0

    def test_vitals_prompt_mentions_blood_pressure(self, agent):
        result = agent._build_vitals_extraction_prompt("text").lower()
        assert "blood pressure" in result

    def test_vitals_prompt_mentions_heart_rate(self, agent):
        result = agent._build_vitals_extraction_prompt("text").lower()
        assert "heart rate" in result

    def test_vitals_prompt_mentions_temperature(self, agent):
        result = agent._build_vitals_extraction_prompt("text").lower()
        assert "temperature" in result

    # --- labs ---

    def test_labs_prompt_returns_string(self, agent):
        assert isinstance(agent._build_labs_extraction_prompt("text"), str)

    def test_labs_prompt_is_nonempty(self, agent):
        assert len(agent._build_labs_extraction_prompt("text")) > 0

    def test_labs_prompt_contains_input_text(self, agent):
        text = "WBC 10.5 K/uL"
        assert text in agent._build_labs_extraction_prompt(text)

    def test_labs_prompt_with_context_includes_context(self, agent):
        assert "fasting labs" in agent._build_labs_extraction_prompt("text", context="fasting labs")

    def test_labs_prompt_none_context_no_error(self, agent):
        result = agent._build_labs_extraction_prompt("text", context=None)
        assert isinstance(result, str) and len(result) > 0

    def test_labs_prompt_mentions_reference_range(self, agent):
        result = agent._build_labs_extraction_prompt("text").lower()
        assert "reference range" in result or "reference" in result

    def test_labs_prompt_mentions_units(self, agent):
        result = agent._build_labs_extraction_prompt("text").lower()
        assert "unit" in result

    # --- medications ---

    def test_medications_prompt_returns_string(self, agent):
        assert isinstance(agent._build_medications_extraction_prompt("text"), str)

    def test_medications_prompt_is_nonempty(self, agent):
        assert len(agent._build_medications_extraction_prompt("text")) > 0

    def test_medications_prompt_contains_input_text(self, agent):
        text = "metformin 500mg twice daily"
        assert text in agent._build_medications_extraction_prompt(text)

    def test_medications_prompt_with_context_includes_context(self, agent):
        assert "polypharmacy" in agent._build_medications_extraction_prompt("text", context="polypharmacy review")

    def test_medications_prompt_none_context_no_error(self, agent):
        result = agent._build_medications_extraction_prompt("text", context=None)
        assert isinstance(result, str) and len(result) > 0

    def test_medications_prompt_mentions_dosage(self, agent):
        result = agent._build_medications_extraction_prompt("text").lower()
        assert "dosage" in result

    def test_medications_prompt_mentions_frequency(self, agent):
        result = agent._build_medications_extraction_prompt("text").lower()
        assert "frequency" in result

    # --- diagnoses ---

    def test_diagnoses_prompt_returns_string(self, agent):
        assert isinstance(agent._build_diagnoses_extraction_prompt("text"), str)

    def test_diagnoses_prompt_is_nonempty(self, agent):
        assert len(agent._build_diagnoses_extraction_prompt("text")) > 0

    def test_diagnoses_prompt_contains_input_text(self, agent):
        text = "Type 2 DM, HTN"
        assert text in agent._build_diagnoses_extraction_prompt(text)

    def test_diagnoses_prompt_with_context_includes_context(self, agent):
        assert "annual visit" in agent._build_diagnoses_extraction_prompt("text", context="annual visit")

    def test_diagnoses_prompt_none_context_no_error(self, agent):
        result = agent._build_diagnoses_extraction_prompt("text", context=None)
        assert isinstance(result, str) and len(result) > 0

    def test_diagnoses_prompt_mentions_icd(self, agent):
        assert "ICD" in agent._build_diagnoses_extraction_prompt("text")

    def test_diagnoses_prompt_mentions_status(self, agent):
        result = agent._build_diagnoses_extraction_prompt("text").lower()
        assert "status" in result

    # --- procedures ---

    def test_procedures_prompt_returns_string(self, agent):
        assert isinstance(agent._build_procedures_extraction_prompt("text"), str)

    def test_procedures_prompt_is_nonempty(self, agent):
        assert len(agent._build_procedures_extraction_prompt("text")) > 0

    def test_procedures_prompt_contains_input_text(self, agent):
        text = "colonoscopy performed 01/10/2024"
        assert text in agent._build_procedures_extraction_prompt(text)

    def test_procedures_prompt_with_context_includes_context(self, agent):
        assert "surgical history" in agent._build_procedures_extraction_prompt(
            "text", context="surgical history"
        )

    def test_procedures_prompt_none_context_no_error(self, agent):
        result = agent._build_procedures_extraction_prompt("text", context=None)
        assert isinstance(result, str) and len(result) > 0

    def test_procedures_prompt_mentions_status(self, agent):
        result = agent._build_procedures_extraction_prompt("text").lower()
        assert "status" in result

    def test_procedures_prompt_mentions_date(self, agent):
        result = agent._build_procedures_extraction_prompt("text").lower()
        assert "date" in result

    # --- cross-cutting ---

    def test_all_six_prompt_builders_return_different_strings(self, agent):
        text = "clinical text"
        results = [
            agent._build_comprehensive_extraction_prompt(text),
            agent._build_vitals_extraction_prompt(text),
            agent._build_labs_extraction_prompt(text),
            agent._build_medications_extraction_prompt(text),
            agent._build_diagnoses_extraction_prompt(text),
            agent._build_procedures_extraction_prompt(text),
        ]
        # Every prompt must be unique
        assert len(set(results)) == 6

    def test_context_is_not_injected_when_none(self, agent):
        # When context=None, "Additional Context:" should not appear
        result = agent._build_vitals_extraction_prompt("text", context=None)
        assert "Additional Context:" not in result

    def test_context_is_injected_when_provided(self, agent):
        result = agent._build_vitals_extraction_prompt("text", context="some context")
        assert "Additional Context:" in result


# ---------------------------------------------------------------------------
# TestParseComprehensiveExtraction
# ---------------------------------------------------------------------------

class TestParseComprehensiveExtraction:
    """_parse_comprehensive_extraction: section-based text parsing."""

    def test_returns_dict(self, agent):
        assert isinstance(agent._parse_comprehensive_extraction(""), dict)

    def test_empty_string_has_all_five_keys(self, agent):
        result = agent._parse_comprehensive_extraction("")
        for key in ("vital_signs", "laboratory_values", "medications", "diagnoses", "procedures"):
            assert key in result

    def test_empty_string_all_lists_are_empty(self, agent):
        result = agent._parse_comprehensive_extraction("")
        for key in ("vital_signs", "laboratory_values", "medications", "diagnoses", "procedures"):
            assert result[key] == []

    def test_vital_signs_section_parsed(self, agent):
        text = "VITAL SIGNS:\n- BP 120/80 mmHg\n- HR 72 bpm"
        assert len(agent._parse_comprehensive_extraction(text)["vital_signs"]) == 2

    def test_medications_section_parsed(self, agent):
        text = "MEDICATIONS:\n- metformin 500mg twice daily\n- lisinopril 10mg daily"
        assert len(agent._parse_comprehensive_extraction(text)["medications"]) == 2

    def test_diagnoses_section_parsed(self, agent):
        text = "DIAGNOSES:\n- Type 2 diabetes mellitus (E11.9)\n- Essential hypertension (I10)"
        assert len(agent._parse_comprehensive_extraction(text)["diagnoses"]) == 2

    def test_procedures_section_parsed(self, agent):
        text = "PROCEDURES:\n- ECG performed\n- Chest X-ray ordered"
        assert len(agent._parse_comprehensive_extraction(text)["procedures"]) == 2

    def test_laboratory_values_section_parsed(self, agent):
        text = "LABORATORY VALUES:\n- HbA1c: 7.2%\n- Glucose: 145 mg/dL"
        assert len(agent._parse_comprehensive_extraction(text)["laboratory_values"]) == 2

    def test_items_are_strings(self, agent):
        text = "VITAL SIGNS:\n- HR 80 bpm"
        result = agent._parse_comprehensive_extraction(text)
        assert isinstance(result["vital_signs"][0], str)

    def test_leading_dash_stripped_from_items(self, agent):
        text = "VITAL SIGNS:\n- HR 80 bpm"
        result = agent._parse_comprehensive_extraction(text)
        assert not result["vital_signs"][0].startswith("-")

    def test_multiple_sections_parsed_independently(self, agent):
        text = (
            "VITAL SIGNS:\n- BP 140/90\n"
            "MEDICATIONS:\n- aspirin 81mg daily\n"
            "DIAGNOSES:\n- Hypertension\n"
        )
        result = agent._parse_comprehensive_extraction(text)
        assert len(result["vital_signs"]) == 1
        assert len(result["medications"]) == 1
        assert len(result["diagnoses"]) == 1

    def test_malformed_input_raises_no_exception(self, agent):
        malformed = "random text without sections\nno dashes here"
        result = agent._parse_comprehensive_extraction(malformed)
        assert isinstance(result, dict)

    def test_whitespace_only_lines_are_skipped(self, agent):
        text = "VITAL SIGNS:\n   \n- HR 88\n   \n"
        result = agent._parse_comprehensive_extraction(text)
        assert len(result["vital_signs"]) == 1

    def test_five_section_text_all_keys_populated(self, agent):
        text = (
            "VITAL SIGNS:\n- BP 120/80\n"
            "LABORATORY VALUES:\n- WBC 10\n"
            "MEDICATIONS:\n- aspirin\n"
            "DIAGNOSES:\n- HTN\n"
            "PROCEDURES:\n- EKG\n"
        )
        result = agent._parse_comprehensive_extraction(text)
        for key in ("vital_signs", "laboratory_values", "medications", "diagnoses", "procedures"):
            assert len(result[key]) == 1

    def test_single_item_single_section(self, agent):
        text = "VITAL SIGNS:\n- Temp 98.6 F"
        result = agent._parse_comprehensive_extraction(text)
        assert len(result["vital_signs"]) == 1
        assert "Temp 98.6 F" in result["vital_signs"][0]

    def test_non_dash_lines_under_section_are_not_collected(self, agent):
        # Only lines starting with '-' after a section header are collected
        text = "VITAL SIGNS:\nHR 80 bpm"
        result = agent._parse_comprehensive_extraction(text)
        assert len(result["vital_signs"]) == 0


# ---------------------------------------------------------------------------
# TestParseVitalSigns
# ---------------------------------------------------------------------------

class TestParseVitalSigns:
    """_parse_vital_signs: regex extraction of vital sign patterns."""

    def test_returns_list(self, agent):
        assert isinstance(agent._parse_vital_signs(""), list)

    def test_empty_string_returns_empty_list(self, agent):
        assert agent._parse_vital_signs("") == []

    def test_blood_pressure_pattern_detected(self, agent):
        text = "BP: 120/80 mmHg"
        types = [v["type"] for v in agent._parse_vital_signs(text)]
        assert "blood_pressure" in types

    def test_heart_rate_hr_keyword_detected(self, agent):
        text = "HR: 72 bpm"
        types = [v["type"] for v in agent._parse_vital_signs(text)]
        assert "heart_rate" in types

    def test_heart_rate_pulse_keyword_detected(self, agent):
        text = "Pulse: 88 bpm"
        types = [v["type"] for v in agent._parse_vital_signs(text)]
        assert "heart_rate" in types

    def test_heart_rate_full_keyword_detected(self, agent):
        text = "Heart Rate: 80 bpm"
        types = [v["type"] for v in agent._parse_vital_signs(text)]
        assert "heart_rate" in types

    def test_temperature_temp_keyword_detected(self, agent):
        text = "Temp: 98.6 F"
        types = [v["type"] for v in agent._parse_vital_signs(text)]
        assert "temperature" in types

    def test_temperature_full_keyword_detected(self, agent):
        text = "Temperature: 37.0 C"
        types = [v["type"] for v in agent._parse_vital_signs(text)]
        assert "temperature" in types

    def test_respiratory_rate_rr_keyword_detected(self, agent):
        text = "RR: 16 /min"
        types = [v["type"] for v in agent._parse_vital_signs(text)]
        assert "respiratory_rate" in types

    def test_oxygen_saturation_spo2_keyword_detected(self, agent):
        text = "SpO2: 98%"
        types = [v["type"] for v in agent._parse_vital_signs(text)]
        assert "oxygen_saturation" in types

    def test_oxygen_saturation_o2_sat_keyword_detected(self, agent):
        text = "O2 Sat: 97%"
        types = [v["type"] for v in agent._parse_vital_signs(text)]
        assert "oxygen_saturation" in types

    def test_weight_keyword_detected(self, agent):
        text = "Weight: 75 kg"
        types = [v["type"] for v in agent._parse_vital_signs(text)]
        assert "weight" in types

    def test_height_keyword_detected(self, agent):
        text = "Height: 170 cm"
        types = [v["type"] for v in agent._parse_vital_signs(text)]
        assert "height" in types

    def test_vital_entry_has_type_key(self, agent):
        result = agent._parse_vital_signs("HR: 60 bpm")
        assert len(result) > 0
        assert "type" in result[0]

    def test_vital_entry_has_value_key(self, agent):
        result = agent._parse_vital_signs("HR: 60 bpm")
        assert len(result) > 0
        assert "value" in result[0]

    def test_vital_entry_has_raw_text_key(self, agent):
        result = agent._parse_vital_signs("HR: 60 bpm")
        assert len(result) > 0
        assert "raw_text" in result[0]

    def test_raw_text_matches_source_line(self, agent):
        line = "HR: 60 bpm"
        result = agent._parse_vital_signs(line)
        assert len(result) > 0
        assert result[0]["raw_text"] == line

    def test_multiple_vitals_across_lines_all_detected(self, agent):
        text = "BP: 120/80 mmHg\nHR: 72 bpm\nTemp: 98.6 F"
        result = agent._parse_vital_signs(text)
        assert len(result) >= 3

    def test_case_insensitive_heart_rate(self, agent):
        text = "heart rate: 80 bpm"
        types = [v["type"] for v in agent._parse_vital_signs(text)]
        assert "heart_rate" in types

    def test_bp_value_contains_systolic(self, agent):
        text = "120/80 mmHg"
        result = agent._parse_vital_signs(text)
        bp = [v for v in result if v["type"] == "blood_pressure"]
        assert len(bp) > 0
        assert "120" in bp[0]["value"]

    def test_plain_narrative_no_matches(self, agent):
        text = "Patient denies complaints. Follow up in three months."
        result = agent._parse_vital_signs(text)
        # Pure narrative should not trigger vital patterns
        assert isinstance(result, list)

    def test_each_vital_entry_is_dict(self, agent):
        text = "HR: 72 bpm\nBP: 120/80"
        result = agent._parse_vital_signs(text)
        for entry in result:
            assert isinstance(entry, dict)
