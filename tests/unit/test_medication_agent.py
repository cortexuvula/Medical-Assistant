"""
Tests for src/ai/agents/medication.py (pure-logic methods only)
No network, no Tkinter, no AI calls.
"""
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.agents.medication import MedicationAgent, TDM_DRUGS, BEERS_HIGH_RISK
from ai.agents.models import AgentConfig, AgentTask


@pytest.fixture
def agent():
    return MedicationAgent(config=None, ai_caller=None)


def _make_task(description="Extract medications", clinical_text="Patient takes aspirin 81mg daily."):
    return AgentTask(
        task_description=description,
        input_data={"clinical_text": clinical_text}
    )


# ---------------------------------------------------------------------------
# TestDetermineTaskType
# ---------------------------------------------------------------------------

class TestDetermineTaskType:
    """Tests for MedicationAgent._determine_task_type."""

    def test_extract_keyword_returns_extract(self, agent):
        task = _make_task(description="Extract all medications from text")
        assert agent._determine_task_type(task) == "extract"

    def test_identify_keyword_returns_extract(self, agent):
        task = _make_task(description="Identify medications in this note")
        assert agent._determine_task_type(task) == "extract"

    def test_interaction_keyword_returns_check_interactions(self, agent):
        task = _make_task(description="Check interaction between drugs")
        assert agent._determine_task_type(task) == "check_interactions"

    def test_drug_interaction_phrase_returns_check_interactions(self, agent):
        task = _make_task(description="Drug interaction analysis needed")
        assert agent._determine_task_type(task) == "check_interactions"

    def test_check_interaction_phrase_returns_check_interactions(self, agent):
        task = _make_task(description="Please check interaction for patient")
        assert agent._determine_task_type(task) == "check_interactions"

    def test_prescription_keyword_returns_generate_prescription(self, agent):
        task = _make_task(description="Write a prescription for this medication")
        assert agent._determine_task_type(task) == "generate_prescription"

    def test_prescribe_keyword_returns_generate_prescription(self, agent):
        task = _make_task(description="Prescribe lisinopril for hypertension")
        assert agent._determine_task_type(task) == "generate_prescription"

    def test_dosing_keyword_returns_validate_dosing(self, agent):
        task = _make_task(description="Verify dosing for renal patient")
        assert agent._determine_task_type(task) == "validate_dosing"

    def test_dose_keyword_returns_validate_dosing(self, agent):
        task = _make_task(description="Is this dose appropriate?")
        assert agent._determine_task_type(task) == "validate_dosing"

    def test_alternative_keyword_returns_suggest_alternatives(self, agent):
        task = _make_task(description="Suggest alternative to metformin")
        assert agent._determine_task_type(task) == "suggest_alternatives"

    def test_substitute_keyword_returns_suggest_alternatives(self, agent):
        task = _make_task(description="Substitute for atenolol in patient")
        assert agent._determine_task_type(task) == "suggest_alternatives"

    def test_unknown_description_returns_comprehensive(self, agent):
        task = _make_task(description="Analyze the medications for this patient")
        assert agent._determine_task_type(task) == "comprehensive"

    def test_no_matching_keyword_returns_comprehensive(self, agent):
        task = AgentTask(task_description="no special keyword here", input_data={})
        assert agent._determine_task_type(task) == "comprehensive"

    def test_case_insensitive_extract(self, agent):
        task = _make_task(description="EXTRACT medications now")
        assert agent._determine_task_type(task) == "extract"

    def test_case_insensitive_interaction(self, agent):
        task = _make_task(description="Check INTERACTION between drugs")
        assert agent._determine_task_type(task) == "check_interactions"

    def test_case_insensitive_prescription(self, agent):
        task = _make_task(description="Generate PRESCRIPTION details")
        assert agent._determine_task_type(task) == "generate_prescription"

    def test_case_insensitive_dosing(self, agent):
        task = _make_task(description="Validate DOSING schedule")
        assert agent._determine_task_type(task) == "validate_dosing"

    def test_case_insensitive_alternative(self, agent):
        task = _make_task(description="Find ALTERNATIVE medications")
        assert agent._determine_task_type(task) == "suggest_alternatives"

    def test_case_insensitive_substitute(self, agent):
        task = _make_task(description="SUBSTITUTE therapy options")
        assert agent._determine_task_type(task) == "suggest_alternatives"

    def test_extract_takes_priority_over_unrelated_words(self, agent):
        task = _make_task(description="Please extract and list all medications")
        assert agent._determine_task_type(task) == "extract"

    def test_comprehensive_description_defaults_to_comprehensive(self, agent):
        task = _make_task(description="Review the chart for this patient")
        assert agent._determine_task_type(task) == "comprehensive"

    def test_full_word_no_match_falls_to_comprehensive(self, agent):
        # "full" is not a routing keyword; should fall through to comprehensive
        task = _make_task(description="Full review of all medications")
        assert agent._determine_task_type(task) == "comprehensive"

    def test_identify_returns_extract_not_comprehensive(self, agent):
        task = _make_task(description="Identify all drugs in chart")
        assert agent._determine_task_type(task) != "comprehensive"

    def test_prescriptions_plural_matches_generate_prescription(self, agent):
        # "prescriptions" contains "prescription"
        task = _make_task(description="Prescriptions to be written")
        assert agent._determine_task_type(task) == "generate_prescription"

    def test_dosing_partial_match(self, agent):
        task = _make_task(description="Adjust dosing for elderly patient")
        assert agent._determine_task_type(task) == "validate_dosing"

    def test_return_value_is_string(self, agent):
        task = _make_task(description="Extract all medications")
        result = agent._determine_task_type(task)
        assert isinstance(result, str)

    def test_comprehensive_is_default_fallback_value(self, agent):
        task = _make_task(description="routine patient visit summary")
        assert agent._determine_task_type(task) == "comprehensive"


# ---------------------------------------------------------------------------
# TestParseMedicationList
# ---------------------------------------------------------------------------

class TestParseMedicationList:
    """Tests for MedicationAgent._parse_medication_list."""

    def test_returns_list_type(self, agent):
        result = agent._parse_medication_list("- Aspirin 81mg")
        assert isinstance(result, list)

    def test_empty_string_returns_empty_list(self, agent):
        result = agent._parse_medication_list("")
        assert result == []

    def test_whitespace_only_returns_empty_list(self, agent):
        result = agent._parse_medication_list("   \n  \n  ")
        assert result == []

    def test_single_dash_medication_parsed(self, agent):
        result = agent._parse_medication_list("- Aspirin 81mg")
        assert len(result) == 1

    def test_single_medication_has_name_key(self, agent):
        result = agent._parse_medication_list("- Metformin 500mg")
        assert "name" in result[0]

    def test_single_medication_name_extracted(self, agent):
        result = agent._parse_medication_list("- Aspirin 81mg")
        assert "Aspirin 81mg" in result[0]["name"]

    def test_numbered_list_format_parsed(self, agent):
        result = agent._parse_medication_list("1. Aspirin 81mg")
        assert len(result) == 1

    def test_numbered_list_name_extracted(self, agent):
        result = agent._parse_medication_list("1. Aspirin 81mg")
        assert "Aspirin" in result[0]["name"]

    def test_multiple_dash_medications_returns_multiple(self, agent):
        text = "- Aspirin 81mg\n- Metformin 500mg"
        result = agent._parse_medication_list(text)
        assert len(result) == 2

    def test_multiple_numbered_medications_returns_multiple(self, agent):
        text = "1. Aspirin 81mg\n2. Metformin 500mg"
        result = agent._parse_medication_list(text)
        assert len(result) == 2

    def test_medication_with_colon_property_extracted(self, agent):
        text = "- Aspirin\nDose: 81mg"
        result = agent._parse_medication_list(text)
        assert len(result) >= 1
        assert result[0].get("dose") == "81mg"

    def test_frequency_extracted_from_colon_property(self, agent):
        text = "- Lisinopril\nFrequency: Once daily"
        result = agent._parse_medication_list(text)
        assert result[0].get("frequency") == "Once daily"

    def test_raw_key_present(self, agent):
        result = agent._parse_medication_list("- Aspirin 81mg")
        assert "raw" in result[0]

    def test_raw_contains_original_line(self, agent):
        result = agent._parse_medication_list("- Aspirin 81mg")
        assert result[0]["raw"] == "- Aspirin 81mg"

    def test_dash_prefix_stripped_from_name(self, agent):
        result = agent._parse_medication_list("- Metformin 500mg BID")
        assert not result[0]["name"].startswith("-")

    def test_number_prefix_stripped_from_name(self, agent):
        result = agent._parse_medication_list("1. Aspirin 81mg")
        assert not result[0]["name"][0].isdigit()

    def test_blank_line_separates_medication_blocks(self, agent):
        text = "- Aspirin\nDose: 81mg\n\n- Metformin\nDose: 500mg"
        result = agent._parse_medication_list(text)
        assert len(result) == 2

    def test_medication_with_parentheses_parsed(self, agent):
        result = agent._parse_medication_list("- Acetaminophen (Tylenol) 500mg")
        assert len(result) == 1
        assert "Acetaminophen" in result[0]["name"]

    def test_colon_property_key_lowercased(self, agent):
        text = "- Aspirin\nDOSE: 81mg"
        result = agent._parse_medication_list(text)
        assert "dose" in result[0]

    def test_colon_property_key_spaces_replaced_with_underscore(self, agent):
        text = "- Aspirin\nRoute of Admin: Oral"
        result = agent._parse_medication_list(text)
        assert "route_of_admin" in result[0]

    def test_colon_value_whitespace_stripped(self, agent):
        text = "- Aspirin\nDose:  81mg  "
        result = agent._parse_medication_list(text)
        assert result[0]["dose"] == "81mg"

    def test_three_medications_correct_count(self, agent):
        text = "- Aspirin 81mg\n- Metformin 500mg\n- Lisinopril 10mg"
        result = agent._parse_medication_list(text)
        assert len(result) == 3

    def test_medication_bid_frequency_preserved_in_name(self, agent):
        result = agent._parse_medication_list("- Metformin 500mg BID")
        assert "Metformin 500mg BID" in result[0]["name"]

    def test_multiline_with_multiple_colon_properties(self, agent):
        text = "- Warfarin\nDose: 5mg\nFrequency: Daily\nIndication: AFib"
        result = agent._parse_medication_list(text)
        assert result[0].get("dose") == "5mg"
        assert result[0].get("frequency") == "Daily"
        assert result[0].get("indication") == "AFib"

    def test_colon_in_value_splits_only_on_first_colon(self, agent):
        # Value itself contains a colon; only the first split is used as key
        text = "- Aspirin\nTiming: 08:00 daily"
        result = agent._parse_medication_list(text)
        assert "timing" in result[0]
        assert result[0]["timing"] == "08:00 daily"

    def test_numbered_list_with_two_digit_number(self, agent):
        result = agent._parse_medication_list("2. Lisinopril 10mg")
        assert "Lisinopril 10mg" in result[0]["name"]

    def test_result_dicts_are_nonempty(self, agent):
        result = agent._parse_medication_list("- Aspirin 81mg\n- Metformin 500mg")
        assert all(len(med) > 0 for med in result)


# ---------------------------------------------------------------------------
# TestExtractMedicationsFromText
# ---------------------------------------------------------------------------

class TestExtractMedicationsFromText:
    """Tests for MedicationAgent.extract_medications_from_text."""

    def test_returns_list_on_success(self, agent):
        from ai.agents.models import AgentResponse
        mock_response = AgentResponse(
            result="- Aspirin 81mg",
            success=True,
            metadata={"medications": [{"name": "Aspirin 81mg", "raw": "- Aspirin 81mg"}]}
        )
        agent.execute = MagicMock(return_value=mock_response)
        result = agent.extract_medications_from_text("Patient takes aspirin 81mg daily.")
        assert isinstance(result, list)

    def test_returns_medications_from_metadata_on_success(self, agent):
        from ai.agents.models import AgentResponse
        meds = [{"name": "Aspirin 81mg", "raw": "- Aspirin 81mg"}]
        mock_response = AgentResponse(
            result="- Aspirin 81mg",
            success=True,
            metadata={"medications": meds}
        )
        agent.execute = MagicMock(return_value=mock_response)
        result = agent.extract_medications_from_text("Patient takes aspirin 81mg daily.")
        assert result == meds

    def test_returns_empty_list_on_failure(self, agent):
        from ai.agents.models import AgentResponse
        mock_response = AgentResponse(
            result="",
            success=False,
            error="No clinical text provided"
        )
        agent.execute = MagicMock(return_value=mock_response)
        result = agent.extract_medications_from_text("")
        assert result == []

    def test_returns_empty_list_when_execute_returns_none(self, agent):
        agent.execute = MagicMock(return_value=None)
        result = agent.extract_medications_from_text("Patient on aspirin.")
        assert result == []

    def test_task_built_with_extract_in_description(self, agent):
        from ai.agents.models import AgentResponse
        mock_response = AgentResponse(result="", success=True, metadata={"medications": []})
        agent.execute = MagicMock(return_value=mock_response)
        agent.extract_medications_from_text("some text")
        call_args = agent.execute.call_args[0][0]
        assert "extract" in call_args.task_description.lower()

    def test_task_built_with_clinical_text_in_input_data(self, agent):
        from ai.agents.models import AgentResponse
        mock_response = AgentResponse(result="", success=True, metadata={"medications": []})
        agent.execute = MagicMock(return_value=mock_response)
        agent.extract_medications_from_text("Patient takes metformin 500mg BID.")
        call_args = agent.execute.call_args[0][0]
        assert call_args.input_data.get("clinical_text") == "Patient takes metformin 500mg BID."

    def test_realistic_clinical_text_returns_list(self, agent):
        from ai.agents.models import AgentResponse
        meds = [
            {"name": "Metformin 500mg BID", "raw": "- Metformin 500mg BID"},
            {"name": "Lisinopril 10mg daily", "raw": "- Lisinopril 10mg daily"},
        ]
        mock_response = AgentResponse(
            result="- Metformin 500mg BID\n- Lisinopril 10mg daily",
            success=True,
            metadata={"medications": meds}
        )
        agent.execute = MagicMock(return_value=mock_response)
        clinical_text = (
            "56yo male with T2DM and hypertension. Currently on Metformin 500mg BID "
            "and Lisinopril 10mg daily. Labs reviewed today."
        )
        result = agent.extract_medications_from_text(clinical_text)
        assert len(result) == 2

    def test_empty_metadata_medications_key_returns_empty_list(self, agent):
        from ai.agents.models import AgentResponse
        mock_response = AgentResponse(
            result="No medications found.",
            success=True,
            metadata={}
        )
        agent.execute = MagicMock(return_value=mock_response)
        result = agent.extract_medications_from_text("Patient denies all medications.")
        assert result == []

    def test_multiple_medications_in_metadata_all_returned(self, agent):
        from ai.agents.models import AgentResponse
        meds = [
            {"name": "Aspirin 81mg"},
            {"name": "Atorvastatin 40mg"},
            {"name": "Metoprolol 25mg"},
        ]
        mock_response = AgentResponse(
            result="...",
            success=True,
            metadata={"medications": meds}
        )
        agent.execute = MagicMock(return_value=mock_response)
        result = agent.extract_medications_from_text("...")
        assert len(result) == 3

    def test_execute_called_once(self, agent):
        from ai.agents.models import AgentResponse
        mock_response = AgentResponse(result="", success=True, metadata={"medications": []})
        agent.execute = MagicMock(return_value=mock_response)
        agent.extract_medications_from_text("some clinical text")
        agent.execute.assert_called_once()


# ---------------------------------------------------------------------------
# TestParseMedicationListIntegration
# ---------------------------------------------------------------------------

class TestParseMedicationListIntegration:
    """Integration-style tests exercising _parse_medication_list with realistic AI-like output."""

    def test_realistic_extraction_output_two_medications(self, agent):
        text = (
            "- Aspirin 81mg\n"
            "Frequency: Once daily\n"
            "Indication: Antiplatelet\n"
            "\n"
            "- Metformin 500mg\n"
            "Frequency: BID\n"
            "Indication: Type 2 Diabetes\n"
        )
        result = agent._parse_medication_list(text)
        assert len(result) == 2
        names = [m["name"] for m in result]
        assert any("Aspirin" in n for n in names)
        assert any("Metformin" in n for n in names)

    def test_numbered_with_route_and_frequency_properties(self, agent):
        text = (
            "1. Lisinopril 10mg\n"
            "Route: Oral\n"
            "Frequency: Daily\n"
            "\n"
            "2. Atorvastatin 40mg\n"
            "Route: Oral\n"
            "Frequency: Nightly\n"
        )
        result = agent._parse_medication_list(text)
        assert len(result) == 2
        assert result[0].get("route") == "Oral"
        assert result[1].get("frequency") == "Nightly"

    def test_medication_with_brand_name_in_parentheses(self, agent):
        text = "- Acetylsalicylic acid (Aspirin) 81mg daily"
        result = agent._parse_medication_list(text)
        assert len(result) == 1
        assert "Acetylsalicylic acid" in result[0]["name"]

    def test_mixed_dash_and_numbered_medications(self, agent):
        text = (
            "- Warfarin 5mg\n"
            "Indication: AFib\n"
            "\n"
            "1. Digoxin 0.125mg\n"
            "Indication: Heart failure\n"
        )
        result = agent._parse_medication_list(text)
        assert len(result) == 2

    def test_single_medication_no_properties(self, agent):
        result = agent._parse_medication_list("- Vancomycin 1g IV q12h")
        assert len(result) == 1
        assert "name" in result[0]

    def test_five_medications_returns_five(self, agent):
        lines = "\n".join([f"- Drug{i} {i * 10}mg" for i in range(1, 6)])
        result = agent._parse_medication_list(lines)
        assert len(result) == 5


# ---------------------------------------------------------------------------
# TestModuleLevelData
# ---------------------------------------------------------------------------

class TestModuleLevelData:
    """Tests for module-level reference data correctness."""

    def test_tdm_drugs_is_dict(self):
        assert isinstance(TDM_DRUGS, dict)

    def test_tdm_drugs_not_empty(self):
        assert len(TDM_DRUGS) > 0

    def test_vancomycin_in_tdm_drugs(self):
        assert "vancomycin" in TDM_DRUGS

    def test_digoxin_in_tdm_drugs(self):
        assert "digoxin" in TDM_DRUGS

    def test_lithium_in_tdm_drugs(self):
        assert "lithium" in TDM_DRUGS

    def test_warfarin_in_tdm_drugs(self):
        assert "warfarin" in TDM_DRUGS

    def test_phenytoin_in_tdm_drugs(self):
        assert "phenytoin" in TDM_DRUGS

    def test_tdm_entry_has_target_key(self):
        for drug, data in TDM_DRUGS.items():
            assert "target" in data, f"{drug} missing 'target' key"

    def test_tdm_entry_has_timing_key(self):
        for drug, data in TDM_DRUGS.items():
            assert "timing" in data, f"{drug} missing 'timing' key"

    def test_tdm_entry_has_guideline_key(self):
        for drug, data in TDM_DRUGS.items():
            assert "guideline" in data, f"{drug} missing 'guideline' key"

    def test_beers_high_risk_is_list(self):
        assert isinstance(BEERS_HIGH_RISK, list)

    def test_beers_high_risk_not_empty(self):
        assert len(BEERS_HIGH_RISK) > 0

    def test_diphenhydramine_in_beers(self):
        assert "diphenhydramine" in BEERS_HIGH_RISK

    def test_diazepam_in_beers(self):
        assert "diazepam" in BEERS_HIGH_RISK

    def test_amitriptyline_in_beers(self):
        assert "amitriptyline" in BEERS_HIGH_RISK

    def test_beers_entries_are_lowercase_strings(self):
        assert all(isinstance(entry, str) for entry in BEERS_HIGH_RISK)

    def test_cyclobenzaprine_in_beers(self):
        assert "cyclobenzaprine" in BEERS_HIGH_RISK

    def test_lorazepam_in_beers(self):
        assert "lorazepam" in BEERS_HIGH_RISK

    def test_tdm_target_values_are_strings(self):
        for drug, data in TDM_DRUGS.items():
            assert isinstance(data["target"], str), f"{drug} target is not a string"


# ---------------------------------------------------------------------------
# TestAgentInitialization
# ---------------------------------------------------------------------------

class TestAgentInitialization:
    """Tests for MedicationAgent construction and default configuration."""

    def test_agent_instantiates_with_none_config(self):
        ag = MedicationAgent(config=None, ai_caller=None)
        assert ag is not None

    def test_agent_uses_default_config_when_none_provided(self):
        ag = MedicationAgent(config=None, ai_caller=None)
        assert ag.config is not None

    def test_default_config_name_is_medication_agent(self):
        ag = MedicationAgent(config=None, ai_caller=None)
        assert ag.config.name == "MedicationAgent"

    def test_default_config_temperature_is_low(self):
        ag = MedicationAgent(config=None, ai_caller=None)
        assert ag.config.temperature <= 0.3

    def test_default_config_max_tokens_set(self):
        ag = MedicationAgent(config=None, ai_caller=None)
        assert ag.config.max_tokens is not None
        assert ag.config.max_tokens > 0

    def test_custom_config_respected(self):
        custom = AgentConfig(
            name="CustomMed",
            description="custom",
            system_prompt="test",
            model="gpt-3.5-turbo",
            temperature=0.5,
        )
        ag = MedicationAgent(config=custom, ai_caller=None)
        assert ag.config.name == "CustomMed"
        assert ag.config.temperature == 0.5

    def test_history_starts_empty(self):
        ag = MedicationAgent(config=None, ai_caller=None)
        assert ag.history == []

    def test_agent_has_execute_method(self):
        ag = MedicationAgent(config=None, ai_caller=None)
        assert callable(ag.execute)

    def test_agent_has_extract_medications_from_text_method(self):
        ag = MedicationAgent(config=None, ai_caller=None)
        assert callable(ag.extract_medications_from_text)

    def test_agent_has_check_drug_interactions_method(self):
        ag = MedicationAgent(config=None, ai_caller=None)
        assert callable(ag.check_drug_interactions)

    def test_agent_has_parse_medication_list_method(self):
        ag = MedicationAgent(config=None, ai_caller=None)
        assert callable(ag._parse_medication_list)

    def test_agent_has_determine_task_type_method(self):
        ag = MedicationAgent(config=None, ai_caller=None)
        assert callable(ag._determine_task_type)


# ---------------------------------------------------------------------------
# TestDetermineTaskTypeEdgeCases
# ---------------------------------------------------------------------------

class TestDetermineTaskTypeEdgeCases:
    """Edge-case tests for task type determination."""

    def test_multiple_keywords_extract_wins_over_dose(self, agent):
        # "extract" is tested before "dose" in the if-elif chain
        task = _make_task(description="Extract and validate dose")
        assert agent._determine_task_type(task) == "extract"

    def test_multiple_keywords_interaction_wins_over_prescription(self, agent):
        # "interaction" is tested before "prescription" in the chain
        task = _make_task(description="Interaction check before prescription writing")
        assert agent._determine_task_type(task) == "check_interactions"

    def test_prescription_wins_over_dosing(self, agent):
        # "prescription" is tested before "dose" in the chain
        task = _make_task(description="Generate prescription with correct dose")
        assert agent._determine_task_type(task) == "generate_prescription"

    def test_alternative_wins_over_comprehensive(self, agent):
        task = _make_task(description="Find alternative for patient review")
        assert agent._determine_task_type(task) == "suggest_alternatives"

    def test_mixed_case_identify_returns_extract(self, agent):
        task = _make_task(description="Please Identify Medications Here")
        assert agent._determine_task_type(task) == "extract"

    def test_mixed_case_substitute_returns_suggest_alternatives(self, agent):
        task = _make_task(description="Need a Substitute for this drug")
        assert agent._determine_task_type(task) == "suggest_alternatives"

    def test_result_never_none(self, agent):
        for desc in ["anything", "review", "chart", "patient", "list meds"]:
            task = _make_task(description=desc)
            result = agent._determine_task_type(task)
            assert result is not None
