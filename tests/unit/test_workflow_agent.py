"""Tests for WorkflowAgent pure-logic methods."""

import pytest
from unittest.mock import MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from ai.agents.workflow import WorkflowAgent
from ai.agents.models import AgentTask


def _make_agent():
    return WorkflowAgent(ai_caller=MagicMock())


def _make_task(description="test task", input_data=None):
    return AgentTask(
        task_description=description,
        input_data=input_data or {}
    )


# ---------------------------------------------------------------------------
# TestWorkflowAgentDefaults
# ---------------------------------------------------------------------------

class TestWorkflowAgentDefaults:
    """Tests for WorkflowAgent.DEFAULT_CONFIG values."""

    def test_default_config_name_is_workflow_agent(self):
        assert WorkflowAgent.DEFAULT_CONFIG.name == "WorkflowAgent"

    def test_default_config_temperature_is_0_3(self):
        assert WorkflowAgent.DEFAULT_CONFIG.temperature == 0.3


# ---------------------------------------------------------------------------
# TestParseWorkflow
# ---------------------------------------------------------------------------

class TestParseWorkflow:
    """Tests for WorkflowAgent._parse_workflow."""

    # ------------------------------------------------------------------
    # 1. Empty string → empty containers and default duration
    # ------------------------------------------------------------------

    def test_empty_string_steps_is_empty_list(self):
        agent = _make_agent()
        result = agent._parse_workflow("", "general")
        assert result["steps"] == []

    def test_empty_string_checkpoints_is_empty_list(self):
        agent = _make_agent()
        result = agent._parse_workflow("", "general")
        assert result["checkpoints"] == []

    def test_empty_string_duration_defaults_to_varies(self):
        agent = _make_agent()
        result = agent._parse_workflow("", "general")
        assert result["duration"] == "Varies"

    # ------------------------------------------------------------------
    # 2. workflow_type stored in result["type"]
    # ------------------------------------------------------------------

    def test_workflow_type_patient_intake_stored(self):
        agent = _make_agent()
        result = agent._parse_workflow("", "patient_intake")
        assert result["type"] == "patient_intake"

    def test_workflow_type_general_stored(self):
        agent = _make_agent()
        result = agent._parse_workflow("", "general")
        assert result["type"] == "general"

    def test_workflow_type_diagnostic_workup_stored(self):
        agent = _make_agent()
        result = agent._parse_workflow("", "diagnostic_workup")
        assert result["type"] == "diagnostic_workup"

    def test_workflow_type_treatment_protocol_stored(self):
        agent = _make_agent()
        result = agent._parse_workflow("", "treatment_protocol")
        assert result["type"] == "treatment_protocol"

    # ------------------------------------------------------------------
    # 3. Single numbered step with name only
    # ------------------------------------------------------------------

    def test_single_step_count_is_one(self):
        agent = _make_agent()
        result = agent._parse_workflow("1. Step Name", "general")
        assert len(result["steps"]) == 1

    def test_single_step_number_is_int_one(self):
        agent = _make_agent()
        result = agent._parse_workflow("1. Step Name", "general")
        assert result["steps"][0]["number"] == 1

    def test_single_step_name_extracted(self):
        agent = _make_agent()
        result = agent._parse_workflow("1. Step Name", "general")
        assert result["steps"][0]["name"] == "Step Name"

    def test_single_step_duration_is_none_when_absent(self):
        agent = _make_agent()
        result = agent._parse_workflow("1. Step Name", "general")
        assert result["steps"][0]["duration"] is None

    def test_single_step_description_is_none_when_absent(self):
        agent = _make_agent()
        result = agent._parse_workflow("1. Step Name", "general")
        assert result["steps"][0]["description"] is None

    # ------------------------------------------------------------------
    # 4. Step with duration field only
    # ------------------------------------------------------------------

    def test_step_with_duration_duration_value(self):
        agent = _make_agent()
        result = agent._parse_workflow("1. Step Name - 5 mins", "general")
        assert result["steps"][0]["duration"] == "5 mins"

    def test_step_with_duration_name_correct(self):
        agent = _make_agent()
        result = agent._parse_workflow("1. Step Name - 5 mins", "general")
        assert result["steps"][0]["name"] == "Step Name"

    def test_step_with_duration_description_still_none(self):
        agent = _make_agent()
        result = agent._parse_workflow("1. Step Name - 5 mins", "general")
        assert result["steps"][0]["description"] is None

    # ------------------------------------------------------------------
    # 5. Step with duration and description — all three fields set
    # ------------------------------------------------------------------

    def test_step_full_name(self):
        agent = _make_agent()
        result = agent._parse_workflow("1. Step Name - 5 mins - Do the thing", "general")
        assert result["steps"][0]["name"] == "Step Name"

    def test_step_full_duration(self):
        agent = _make_agent()
        result = agent._parse_workflow("1. Step Name - 5 mins - Do the thing", "general")
        assert result["steps"][0]["duration"] == "5 mins"

    def test_step_full_description(self):
        agent = _make_agent()
        result = agent._parse_workflow("1. Step Name - 5 mins - Do the thing", "general")
        assert result["steps"][0]["description"] == "Do the thing"

    # ------------------------------------------------------------------
    # 6. Multiple steps parsed in order
    # ------------------------------------------------------------------

    def test_multiple_steps_count(self):
        agent = _make_agent()
        text = "1. First Step\n2. Second Step\n3. Third Step"
        result = agent._parse_workflow(text, "general")
        assert len(result["steps"]) == 3

    def test_multiple_steps_first_number(self):
        agent = _make_agent()
        text = "1. First Step\n2. Second Step\n3. Third Step"
        result = agent._parse_workflow(text, "general")
        assert result["steps"][0]["number"] == 1

    def test_multiple_steps_last_number(self):
        agent = _make_agent()
        text = "1. First Step\n2. Second Step\n3. Third Step"
        result = agent._parse_workflow(text, "general")
        assert result["steps"][2]["number"] == 3

    def test_multiple_steps_all_names_present(self):
        agent = _make_agent()
        text = "1. First Step\n2. Second Step\n3. Third Step"
        result = agent._parse_workflow(text, "general")
        names = [s["name"] for s in result["steps"]]
        assert "First Step" in names
        assert "Second Step" in names
        assert "Third Step" in names

    # ------------------------------------------------------------------
    # 7. Single checkpoint
    # ------------------------------------------------------------------

    def test_single_checkpoint_value(self):
        agent = _make_agent()
        result = agent._parse_workflow("✓ Checkpoint: Verify vitals", "general")
        assert result["checkpoints"] == ["Verify vitals"]

    def test_single_checkpoint_stripped(self):
        agent = _make_agent()
        result = agent._parse_workflow("✓ Checkpoint:   Verify vitals  ", "general")
        assert result["checkpoints"][0] == "Verify vitals"

    # ------------------------------------------------------------------
    # 8. Multiple checkpoints
    # ------------------------------------------------------------------

    def test_multiple_checkpoints_count(self):
        agent = _make_agent()
        text = "✓ Checkpoint: Verify vitals\n✓ Checkpoint: Confirm consent"
        result = agent._parse_workflow(text, "general")
        assert len(result["checkpoints"]) == 2

    def test_multiple_checkpoints_first_value(self):
        agent = _make_agent()
        text = "✓ Checkpoint: Verify vitals\n✓ Checkpoint: Confirm consent"
        result = agent._parse_workflow(text, "general")
        assert "Verify vitals" in result["checkpoints"]

    def test_multiple_checkpoints_second_value(self):
        agent = _make_agent()
        text = "✓ Checkpoint: Verify vitals\n✓ Checkpoint: Confirm consent"
        result = agent._parse_workflow(text, "general")
        assert "Confirm consent" in result["checkpoints"]

    # ------------------------------------------------------------------
    # 9. DURATION: line sets duration field
    # ------------------------------------------------------------------

    def test_duration_line_sets_duration_field(self):
        agent = _make_agent()
        result = agent._parse_workflow("DURATION: 30 minutes", "general")
        assert result["duration"] == "30 minutes"

    # ------------------------------------------------------------------
    # 10. DURATION: value is stripped
    # ------------------------------------------------------------------

    def test_duration_value_leading_spaces_stripped(self):
        agent = _make_agent()
        result = agent._parse_workflow("DURATION:   45 minutes   ", "general")
        assert result["duration"] == "45 minutes"

    # ------------------------------------------------------------------
    # 11. No DURATION line → stays "Varies"
    # ------------------------------------------------------------------

    def test_no_duration_line_stays_varies(self):
        agent = _make_agent()
        result = agent._parse_workflow("1. Some step", "general")
        assert result["duration"] == "Varies"

    def test_only_steps_no_duration_stays_varies(self):
        agent = _make_agent()
        result = agent._parse_workflow("1. Step A\n2. Step B", "general")
        assert result["duration"] == "Varies"

    # ------------------------------------------------------------------
    # 12. Mixed text with steps and checkpoints
    # ------------------------------------------------------------------

    def test_mixed_text_step_count(self):
        agent = _make_agent()
        text = (
            "1. Registration - 5 mins - Collect patient info\n"
            "✓ Checkpoint: ID verified\n"
            "2. Consent - 10 mins - Sign forms\n"
            "✓ Checkpoint: Signed consent\n"
        )
        result = agent._parse_workflow(text, "patient_intake")
        assert len(result["steps"]) == 2

    def test_mixed_text_checkpoint_count(self):
        agent = _make_agent()
        text = (
            "1. Registration - 5 mins - Collect patient info\n"
            "✓ Checkpoint: ID verified\n"
            "2. Consent - 10 mins - Sign forms\n"
            "✓ Checkpoint: Signed consent\n"
        )
        result = agent._parse_workflow(text, "patient_intake")
        assert len(result["checkpoints"]) == 2

    # ------------------------------------------------------------------
    # 13. steps list initially empty (not None)
    # ------------------------------------------------------------------

    def test_steps_is_list_not_none(self):
        agent = _make_agent()
        result = agent._parse_workflow("", "general")
        assert result["steps"] is not None

    def test_steps_is_a_list_type(self):
        agent = _make_agent()
        result = agent._parse_workflow("", "general")
        assert isinstance(result["steps"], list)

    # ------------------------------------------------------------------
    # 14. checkpoints list initially empty (not None)
    # ------------------------------------------------------------------

    def test_checkpoints_is_list_not_none(self):
        agent = _make_agent()
        result = agent._parse_workflow("", "general")
        assert result["checkpoints"] is not None

    def test_checkpoints_is_a_list_type(self):
        agent = _make_agent()
        result = agent._parse_workflow("", "general")
        assert isinstance(result["checkpoints"], list)

    # ------------------------------------------------------------------
    # 15. decision_points key exists
    # ------------------------------------------------------------------

    def test_decision_points_key_exists(self):
        agent = _make_agent()
        result = agent._parse_workflow("", "general")
        assert "decision_points" in result

    def test_decision_points_is_a_list(self):
        agent = _make_agent()
        result = agent._parse_workflow("", "general")
        assert isinstance(result["decision_points"], list)

    # ------------------------------------------------------------------
    # 16. safety_checkpoints key exists
    # ------------------------------------------------------------------

    def test_safety_checkpoints_key_exists(self):
        agent = _make_agent()
        result = agent._parse_workflow("", "general")
        assert "safety_checkpoints" in result

    def test_safety_checkpoints_is_a_list(self):
        agent = _make_agent()
        result = agent._parse_workflow("", "general")
        assert isinstance(result["safety_checkpoints"], list)

    # ------------------------------------------------------------------
    # Additional edge cases
    # ------------------------------------------------------------------

    def test_two_digit_step_number_parsed(self):
        agent = _make_agent()
        text = "\n".join(f"{i}. Step {i}" for i in range(1, 11))
        result = agent._parse_workflow(text, "general")
        numbers = [s["number"] for s in result["steps"]]
        assert 10 in numbers

    def test_step_name_stripped_of_whitespace(self):
        agent = _make_agent()
        result = agent._parse_workflow("1.   Padded Step Name  ", "general")
        assert result["steps"][0]["name"] == "Padded Step Name"

    def test_duration_with_complex_value(self):
        agent = _make_agent()
        result = agent._parse_workflow("DURATION: 1 hour 30 minutes", "general")
        assert result["duration"] == "1 hour 30 minutes"

    def test_full_workflow_text_all_fields(self):
        agent = _make_agent()
        text = (
            "DURATION: 45 minutes\n"
            "1. Assessment - 10 mins - Initial review\n"
            "✓ Checkpoint: Patient stable\n"
            "2. Treatment - 20 mins - Administer medication\n"
            "✓ Checkpoint: Medication given\n"
            "3. Recovery - 15 mins - Monitor patient\n"
        )
        result = agent._parse_workflow(text, "treatment_protocol")
        assert result["type"] == "treatment_protocol"
        assert result["duration"] == "45 minutes"
        assert len(result["steps"]) == 3
        assert len(result["checkpoints"]) == 2


# ---------------------------------------------------------------------------
# TestExtractDiagnosticTests
# ---------------------------------------------------------------------------

class TestExtractDiagnosticTests:
    """Tests for WorkflowAgent._extract_diagnostic_tests."""

    # ------------------------------------------------------------------
    # 1. Empty string → []
    # ------------------------------------------------------------------

    def test_empty_string_returns_empty_list(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("")
        assert result == []

    # ------------------------------------------------------------------
    # 2. "Lab tests: CBC" → one test
    # ------------------------------------------------------------------

    def test_lab_tests_single_item_count(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Lab tests: CBC")
        assert len(result) == 1

    def test_lab_tests_single_item_name(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Lab tests: CBC")
        assert result[0]["name"] == "CBC"

    def test_lab_tests_single_item_priority_routine(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Lab tests: CBC")
        assert result[0]["priority"] == "Routine"

    def test_lab_tests_single_item_category_laboratory(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Lab tests: CBC")
        assert result[0]["category"] == "Laboratory"

    # ------------------------------------------------------------------
    # 3. "Lab tests: CBC, BMP" → two tests
    # ------------------------------------------------------------------

    def test_lab_tests_two_items_count(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Lab tests: CBC, BMP")
        assert len(result) == 2

    def test_lab_tests_two_items_first_name(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Lab tests: CBC, BMP")
        names = [t["name"] for t in result]
        assert "CBC" in names

    def test_lab_tests_two_items_second_name(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Lab tests: CBC, BMP")
        names = [t["name"] for t in result]
        assert "BMP" in names

    # ------------------------------------------------------------------
    # 4. "Lab tests: STAT CBC" → priority="STAT"
    # ------------------------------------------------------------------

    def test_stat_keyword_sets_priority_stat(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Lab tests: STAT CBC")
        assert result[0]["priority"] == "STAT"

    def test_urgent_uppercase_sets_priority_stat(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Lab tests: URGENT troponin")
        assert result[0]["priority"] == "STAT"

    # ------------------------------------------------------------------
    # 5. "Lab tests: urgent potassium" — "URGENT" is in item.upper(), so STAT wins
    #    per the implementation's STAT check ordering before the Urgent check.
    # ------------------------------------------------------------------

    def test_urgent_lowercase_priority_is_stat_due_to_upper_check(self):
        # The implementation checks `any(word in test.upper() for word in ["STAT","URGENT","IMMEDIATE"])`
        # BEFORE checking `"urgent" in test.lower()`, so "urgent potassium".upper()
        # contains "URGENT" → priority is "STAT".
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Lab tests: urgent potassium")
        assert result[0]["priority"] == "STAT"

    # ------------------------------------------------------------------
    # 6. "Imaging: Chest X-ray" → category="Imaging"
    # ------------------------------------------------------------------

    def test_imaging_category_is_imaging(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Imaging: Chest X-ray")
        assert len(result) == 1
        assert result[0]["category"] == "Imaging"

    def test_imaging_name_extracted(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Imaging: Chest X-ray")
        assert result[0]["name"] == "Chest X-ray"

    # ------------------------------------------------------------------
    # 7. "Test: EKG" → category="Imaging" (third pattern, no "lab")
    # ------------------------------------------------------------------

    def test_test_colon_category_is_imaging(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Test: EKG")
        assert result[0]["category"] == "Imaging"

    def test_test_colon_name_extracted(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Test: EKG")
        assert result[0]["name"] == "EKG"

    # ------------------------------------------------------------------
    # 8. "Order: Urinalysis" → category="Imaging"
    # ------------------------------------------------------------------

    def test_order_colon_category_is_imaging(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Order: Urinalysis")
        assert result[0]["category"] == "Imaging"

    def test_order_colon_name_extracted(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Order: Urinalysis")
        assert result[0]["name"] == "Urinalysis"

    # ------------------------------------------------------------------
    # 9. Semicolon separator splits correctly
    # ------------------------------------------------------------------

    def test_semicolon_separator_count(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Lab tests: CBC; BMP; LFTs")
        assert len(result) == 3

    def test_semicolon_separator_names(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Lab tests: CBC; BMP")
        names = [t["name"] for t in result]
        assert "CBC" in names
        assert "BMP" in names

    # ------------------------------------------------------------------
    # 10. "Blood tests: Thyroid panel" → category="Laboratory"
    # ------------------------------------------------------------------

    def test_blood_tests_category_laboratory(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Blood tests: Thyroid panel")
        assert result[0]["category"] == "Laboratory"

    def test_blood_tests_name_extracted(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Blood tests: Thyroid panel")
        assert result[0]["name"] == "Thyroid panel"

    # ------------------------------------------------------------------
    # 11. "Laboratory tests: LFTs" → category="Laboratory"
    # ------------------------------------------------------------------

    def test_laboratory_tests_category_laboratory(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Laboratory tests: LFTs")
        assert result[0]["category"] == "Laboratory"

    def test_laboratory_tests_name_extracted(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Laboratory tests: LFTs")
        assert result[0]["name"] == "LFTs"

    # ------------------------------------------------------------------
    # 12. IMMEDIATE in test name → priority="STAT"
    # ------------------------------------------------------------------

    def test_immediate_keyword_sets_priority_stat(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Lab tests: IMMEDIATE glucose check")
        assert result[0]["priority"] == "STAT"

    # ------------------------------------------------------------------
    # 13. Empty items after split are skipped
    # ------------------------------------------------------------------

    def test_empty_items_after_comma_split_skipped(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Lab tests: CBC,, BMP")
        names = [t["name"] for t in result]
        assert "" not in names

    def test_double_comma_correct_count(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Lab tests: CBC,, BMP")
        assert len(result) == 2

    # ------------------------------------------------------------------
    # 14. Case-insensitive matching: "LAB TESTS: CBC"
    # ------------------------------------------------------------------

    def test_case_insensitive_lab_tests_upper(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("LAB TESTS: CBC")
        assert len(result) == 1
        assert result[0]["category"] == "Laboratory"

    def test_case_insensitive_imaging_upper(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("IMAGING: MRI Brain")
        assert len(result) == 1
        assert result[0]["category"] == "Imaging"

    # ------------------------------------------------------------------
    # Additional edge cases
    # ------------------------------------------------------------------

    def test_radiology_pattern_category_imaging(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Radiology: CT Abdomen")
        assert result[0]["category"] == "Imaging"

    def test_multiple_patterns_in_same_text(self):
        agent = _make_agent()
        text = "Lab tests: CBC\nImaging: Chest X-ray\nTest: EKG"
        result = agent._extract_diagnostic_tests(text)
        assert len(result) == 3

    def test_routine_priority_when_no_urgency_keywords(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Lab tests: hemoglobin A1c")
        assert result[0]["priority"] == "Routine"

    def test_all_tests_have_name_key(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Lab tests: CBC, BMP\nImaging: X-ray")
        for test in result:
            assert "name" in test

    def test_all_tests_have_priority_key(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Lab tests: CBC, BMP\nImaging: X-ray")
        for test in result:
            assert "priority" in test

    def test_all_tests_have_category_key(self):
        agent = _make_agent()
        result = agent._extract_diagnostic_tests("Lab tests: CBC, BMP\nImaging: X-ray")
        for test in result:
            assert "category" in test


# ---------------------------------------------------------------------------
# TestExtractMonitoringParameters
# ---------------------------------------------------------------------------

class TestExtractMonitoringParameters:
    """Tests for WorkflowAgent._extract_monitoring_parameters."""

    # ------------------------------------------------------------------
    # 1. Empty string → []
    # ------------------------------------------------------------------

    def test_empty_string_returns_empty_list(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("")
        assert result == []

    # ------------------------------------------------------------------
    # 2. "Monitor: Blood pressure" → one param
    # ------------------------------------------------------------------

    def test_monitor_colon_one_param_count(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Monitor: Blood pressure")
        assert len(result) == 1

    def test_monitor_colon_parameter_name(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Monitor: Blood pressure")
        assert result[0]["parameter"] == "Blood pressure"

    def test_monitor_colon_frequency_as_needed(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Monitor: Blood pressure")
        assert result[0]["frequency"] == "As needed"

    # ------------------------------------------------------------------
    # 3. "Monitoring: Heart rate" works
    # ------------------------------------------------------------------

    def test_monitoring_colon_count(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Monitoring: Heart rate")
        assert len(result) == 1

    def test_monitoring_colon_parameter_name(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Monitoring: Heart rate")
        assert result[0]["parameter"] == "Heart rate"

    # ------------------------------------------------------------------
    # 4. "Check: daily blood glucose" → frequency="Daily"
    # ------------------------------------------------------------------

    def test_daily_in_param_sets_frequency_daily(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Check: daily blood glucose")
        assert result[0]["frequency"] == "Daily"

    # ------------------------------------------------------------------
    # 5. "Check: weekly weight" → frequency="Weekly"
    # ------------------------------------------------------------------

    def test_weekly_in_param_sets_frequency_weekly(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Check: weekly weight")
        assert result[0]["frequency"] == "Weekly"

    # ------------------------------------------------------------------
    # 6. "Monitor: monthly INR" → frequency="Monthly"
    # ------------------------------------------------------------------

    def test_monthly_in_param_sets_frequency_monthly(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Monitor: monthly INR")
        assert result[0]["frequency"] == "Monthly"

    # ------------------------------------------------------------------
    # 7. "Assess: lung sounds" → frequency="As needed"
    # ------------------------------------------------------------------

    def test_assess_colon_count(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Assess: lung sounds")
        assert len(result) == 1

    def test_assess_colon_parameter_name(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Assess: lung sounds")
        assert result[0]["parameter"] == "lung sounds"

    def test_assess_colon_frequency_as_needed(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Assess: lung sounds")
        assert result[0]["frequency"] == "As needed"

    # ------------------------------------------------------------------
    # 8. "Measure: temperature" works
    # ------------------------------------------------------------------

    def test_measure_colon_count(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Measure: temperature")
        assert len(result) == 1

    def test_measure_colon_parameter_name(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Measure: temperature")
        assert result[0]["parameter"] == "temperature"

    # ------------------------------------------------------------------
    # 9. "Parameters: SpO2, HR" → two params split on comma
    # ------------------------------------------------------------------

    def test_parameters_colon_comma_count(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Parameters: SpO2, HR")
        assert len(result) == 2

    def test_parameters_colon_first_name(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Parameters: SpO2, HR")
        params = [p["parameter"] for p in result]
        assert "SpO2" in params

    def test_parameters_colon_second_name(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Parameters: SpO2, HR")
        params = [p["parameter"] for p in result]
        assert "HR" in params

    # ------------------------------------------------------------------
    # 10. "Parameter: BP" (singular) works
    # ------------------------------------------------------------------

    def test_parameter_singular_count(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Parameter: BP")
        assert len(result) == 1

    def test_parameter_singular_name(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Parameter: BP")
        assert result[0]["parameter"] == "BP"

    # ------------------------------------------------------------------
    # 11. Empty items after split are skipped
    # ------------------------------------------------------------------

    def test_empty_items_after_split_skipped(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Monitor: SpO2,, HR")
        params = [p["parameter"] for p in result]
        assert "" not in params

    def test_double_comma_correct_count(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Monitor: SpO2,, HR")
        assert len(result) == 2

    # ------------------------------------------------------------------
    # 12. Case-insensitive matching "MONITOR: SpO2"
    # ------------------------------------------------------------------

    def test_case_insensitive_monitor_upper(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("MONITOR: SpO2")
        assert len(result) == 1
        assert result[0]["parameter"] == "SpO2"

    def test_case_insensitive_check_upper(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("CHECK: Heart rate")
        assert len(result) == 1

    # ------------------------------------------------------------------
    # 13. Multiple patterns in same text
    # ------------------------------------------------------------------

    def test_multiple_patterns_count(self):
        agent = _make_agent()
        text = "Monitor: Blood pressure\nCheck: pulse rate\nAssess: oxygen saturation"
        result = agent._extract_monitoring_parameters(text)
        assert len(result) == 3

    def test_multiple_patterns_all_names_present(self):
        agent = _make_agent()
        text = "Monitor: Blood pressure\nCheck: pulse rate\nAssess: oxygen saturation"
        result = agent._extract_monitoring_parameters(text)
        params = [p["parameter"] for p in result]
        assert "Blood pressure" in params
        assert "pulse rate" in params
        assert "oxygen saturation" in params

    # ------------------------------------------------------------------
    # 14. Semicolon separator splits params
    # ------------------------------------------------------------------

    def test_semicolon_separator_count(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Monitor: SpO2; HR; RR")
        assert len(result) == 3

    def test_semicolon_separator_names(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Monitor: SpO2; HR")
        params = [p["parameter"] for p in result]
        assert "SpO2" in params
        assert "HR" in params

    # ------------------------------------------------------------------
    # Additional edge cases
    # ------------------------------------------------------------------

    def test_all_params_have_parameter_key(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Monitor: BP, HR\nCheck: SpO2")
        for param in result:
            assert "parameter" in param

    def test_all_params_have_frequency_key(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Monitor: BP, HR\nCheck: SpO2")
        for param in result:
            assert "frequency" in param

    def test_daily_case_insensitive_in_param(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Monitor: DAILY glucose")
        assert result[0]["frequency"] == "Daily"

    def test_weekly_case_insensitive_in_param(self):
        agent = _make_agent()
        result = agent._extract_monitoring_parameters("Monitor: WEEKLY labs")
        assert result[0]["frequency"] == "Weekly"


# ---------------------------------------------------------------------------
# TestGenerateFollowUpSchedule
# ---------------------------------------------------------------------------

class TestGenerateFollowUpSchedule:
    """Tests for WorkflowAgent._generate_follow_up_schedule."""

    def _empty_workflow(self):
        return {"steps": [], "checkpoints": [], "decision_points": [], "duration": "Varies"}

    # ------------------------------------------------------------------
    # 1. Empty steps + "3 months" → 3 monthly entries
    # ------------------------------------------------------------------

    def test_three_months_creates_three_entries(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "3 months")
        assert len(schedule) == 3

    # ------------------------------------------------------------------
    # 2. "1 month" → 1 entry: interval="1 month", days_from_start=30
    # ------------------------------------------------------------------

    def test_one_month_creates_one_entry(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "1 month")
        assert len(schedule) == 1

    def test_one_month_interval_label(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "1 month")
        assert schedule[0]["interval"] == "1 month"

    def test_one_month_days_from_start_is_30(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "1 month")
        assert schedule[0]["days_from_start"] == 30

    # ------------------------------------------------------------------
    # 3. "6 months" → 6 entries
    # ------------------------------------------------------------------

    def test_six_months_creates_six_entries(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "6 months")
        assert len(schedule) == 6

    # ------------------------------------------------------------------
    # 4. "2 months" → 2 entries
    # ------------------------------------------------------------------

    def test_two_months_creates_two_entries(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "2 months")
        assert len(schedule) == 2

    # ------------------------------------------------------------------
    # 5. No digits in "month" duration → default 6 entries
    # ------------------------------------------------------------------

    def test_no_digits_in_month_duration_uses_default_six(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "several months")
        assert len(schedule) == 6

    # ------------------------------------------------------------------
    # 6. Non-month duration → schedule=[]
    # ------------------------------------------------------------------

    def test_weeks_duration_no_schedule(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "3 weeks")
        assert schedule == []

    def test_empty_duration_no_schedule(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "")
        assert schedule == []

    def test_year_duration_no_schedule(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "1 year")
        assert schedule == []

    # ------------------------------------------------------------------
    # 7. Correct days_from_start values
    # ------------------------------------------------------------------

    def test_first_month_days_from_start_is_30(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "3 months")
        assert schedule[0]["days_from_start"] == 30

    def test_second_month_days_from_start_is_60(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "3 months")
        assert schedule[1]["days_from_start"] == 60

    def test_third_month_days_from_start_is_90(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "3 months")
        assert schedule[2]["days_from_start"] == 90

    # ------------------------------------------------------------------
    # 8. All entries have appointment_type="Follow-up"
    # ------------------------------------------------------------------

    def test_all_entries_have_appointment_type_follow_up(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "3 months")
        for entry in schedule:
            assert entry["appointment_type"] == "Follow-up"

    # ------------------------------------------------------------------
    # 9. All entries have purpose="Progress evaluation"
    # ------------------------------------------------------------------

    def test_all_entries_have_purpose_progress_evaluation(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "3 months")
        for entry in schedule:
            assert entry["purpose"] == "Progress evaluation"

    # ------------------------------------------------------------------
    # 10. Step with "follow-up" and "1 week" → step-based entry
    # ------------------------------------------------------------------

    def test_step_follow_up_1_week_count(self):
        agent = _make_agent()
        workflow = {
            "steps": [
                {"number": 1, "name": "1 week follow-up appointment", "duration": None, "description": None}
            ],
            "checkpoints": [],
            "decision_points": [],
        }
        schedule = agent._generate_follow_up_schedule(workflow, "1 year")
        assert len(schedule) == 1

    def test_step_follow_up_1_week_interval(self):
        agent = _make_agent()
        workflow = {
            "steps": [
                {"number": 1, "name": "1 week follow-up appointment", "duration": None, "description": None}
            ],
            "checkpoints": [],
            "decision_points": [],
        }
        schedule = agent._generate_follow_up_schedule(workflow, "1 year")
        assert schedule[0]["interval"] == "1 week"

    def test_step_follow_up_1_week_days_from_start(self):
        agent = _make_agent()
        workflow = {
            "steps": [
                {"number": 1, "name": "1 week follow-up appointment", "duration": None, "description": None}
            ],
            "checkpoints": [],
            "decision_points": [],
        }
        schedule = agent._generate_follow_up_schedule(workflow, "1 year")
        assert schedule[0]["days_from_start"] == 7

    # ------------------------------------------------------------------
    # 11. Step with "appointment" in name → detected
    # ------------------------------------------------------------------

    def test_step_appointment_keyword_detected(self):
        agent = _make_agent()
        workflow = {
            "steps": [
                {"number": 1, "name": "2 weeks appointment check", "duration": None, "description": None}
            ],
            "checkpoints": [],
            "decision_points": [],
        }
        schedule = agent._generate_follow_up_schedule(workflow, "1 year")
        assert len(schedule) == 1
        assert schedule[0]["interval"] == "2 weeks"
        assert schedule[0]["days_from_start"] == 14

    # ------------------------------------------------------------------
    # 12. Step with "follow" but no recognized interval → fallback fires
    # ------------------------------------------------------------------

    def test_step_with_follow_no_interval_triggers_fallback(self):
        agent = _make_agent()
        workflow = {
            "steps": [
                {"number": 1, "name": "follow up with specialist", "duration": None, "description": None}
            ],
            "checkpoints": [],
            "decision_points": [],
        }
        # Steps produce 0 entries (no interval match), so fallback fires for "2 months"
        schedule = agent._generate_follow_up_schedule(workflow, "2 months")
        assert len(schedule) == 2

    # ------------------------------------------------------------------
    # 13. Steps schedule takes priority (no monthly fallback when steps match)
    # ------------------------------------------------------------------

    def test_steps_schedule_prevents_monthly_fallback(self):
        agent = _make_agent()
        workflow = {
            "steps": [
                {"number": 1, "name": "1 month follow-up visit", "duration": None, "description": None}
            ],
            "checkpoints": [],
            "decision_points": [],
        }
        schedule = agent._generate_follow_up_schedule(workflow, "6 months")
        # Only one step-based entry, not six monthly fallback entries
        assert len(schedule) == 1
        assert schedule[0]["interval"] == "1 month"

    # ------------------------------------------------------------------
    # 14. "month" NOT in duration → returns []
    # ------------------------------------------------------------------

    def test_month_not_in_duration_returns_empty(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "Varies")
        assert schedule == []

    def test_days_duration_not_month_returns_empty(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "30 days")
        assert schedule == []

    # ------------------------------------------------------------------
    # 15. "7 months" → capped at 6 entries (min(8, 7) = 7, range(1,7) = 6)
    # ------------------------------------------------------------------

    def test_seven_months_capped_at_six_entries(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "7 months")
        assert len(schedule) == 6

    def test_eight_months_also_capped_at_six_entries(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "8 months")
        assert len(schedule) == 6

    # ------------------------------------------------------------------
    # Additional edge cases
    # ------------------------------------------------------------------

    def test_all_schedule_entries_have_interval_key(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "3 months")
        for entry in schedule:
            assert "interval" in entry

    def test_all_schedule_entries_have_days_from_start_key(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "3 months")
        for entry in schedule:
            assert "days_from_start" in entry

    def test_all_schedule_entries_have_appointment_type_key(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "3 months")
        for entry in schedule:
            assert "appointment_type" in entry

    def test_all_schedule_entries_have_purpose_key(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "3 months")
        for entry in schedule:
            assert "purpose" in entry

    def test_monthly_interval_labels_correct(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "3 months")
        assert schedule[0]["interval"] == "1 month"
        assert schedule[1]["interval"] == "2 months"
        assert schedule[2]["interval"] == "3 months"

    def test_four_months_creates_four_entries(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "4 months")
        assert len(schedule) == 4

    def test_five_months_creates_five_entries(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "5 months")
        assert len(schedule) == 5

    def test_monthly_days_are_multiples_of_30(self):
        agent = _make_agent()
        schedule = agent._generate_follow_up_schedule(self._empty_workflow(), "5 months")
        for i, entry in enumerate(schedule, start=1):
            assert entry["days_from_start"] == i * 30

    def test_step_with_3_months_interval(self):
        agent = _make_agent()
        workflow = {
            "steps": [
                {"number": 1, "name": "follow-up at 3 months", "duration": None, "description": None}
            ],
            "checkpoints": [],
            "decision_points": [],
        }
        schedule = agent._generate_follow_up_schedule(workflow, "1 year")
        assert len(schedule) == 1
        assert schedule[0]["interval"] == "3 months"
        assert schedule[0]["days_from_start"] == 90

    def test_step_with_6_months_interval(self):
        agent = _make_agent()
        workflow = {
            "steps": [
                {"number": 1, "name": "follow-up 6 months after discharge", "duration": None, "description": None}
            ],
            "checkpoints": [],
            "decision_points": [],
        }
        schedule = agent._generate_follow_up_schedule(workflow, "1 year")
        assert schedule[0]["interval"] == "6 months"
        assert schedule[0]["days_from_start"] == 180

    def test_step_with_1_year_interval(self):
        agent = _make_agent()
        workflow = {
            "steps": [
                {"number": 1, "name": "annual follow-up 1 year", "duration": None, "description": None}
            ],
            "checkpoints": [],
            "decision_points": [],
        }
        schedule = agent._generate_follow_up_schedule(workflow, "1 year")
        assert schedule[0]["interval"] == "1 year"
        assert schedule[0]["days_from_start"] == 365

    def test_step_based_entry_appointment_type_is_follow_up(self):
        agent = _make_agent()
        workflow = {
            "steps": [
                {"number": 1, "name": "1 week follow-up", "duration": None, "description": None}
            ],
            "checkpoints": [],
            "decision_points": [],
        }
        schedule = agent._generate_follow_up_schedule(workflow, "1 year")
        assert schedule[0]["appointment_type"] == "Follow-up"
