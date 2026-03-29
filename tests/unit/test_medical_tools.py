"""
Tests for src/ai/tools/medical_tools.py

Covers DrugInteractionTool, BMICalculatorTool, and DosageCalculatorTool.
Uses a fresh ToolRegistry singleton per test to avoid cross-test registration
pollution from the @register_tool class decorator.
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

from ai.tools.tool_registry import ToolRegistry


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset the ToolRegistry singleton before and after every test."""
    ToolRegistry._instance = None
    yield
    ToolRegistry._instance = None


def get_tools():
    """
    Import (and reload) the medical_tools module so that @register_tool
    fires against the freshly-reset singleton.
    """
    import importlib
    import ai.tools.medical_tools as _mt
    importlib.reload(_mt)
    from ai.tools.medical_tools import (
        DrugInteractionTool,
        BMICalculatorTool,
        DosageCalculatorTool,
    )
    return DrugInteractionTool, BMICalculatorTool, DosageCalculatorTool


# ---------------------------------------------------------------------------
# Convenience factories — call INSIDE each test after reset_registry runs
# ---------------------------------------------------------------------------

def make_drug_tool():
    DrugInteractionTool, _, _ = get_tools()
    return DrugInteractionTool()


def make_bmi_tool():
    _, BMICalculatorTool, _ = get_tools()
    return BMICalculatorTool()


def make_dose_tool():
    _, _, DosageCalculatorTool = get_tools()
    return DosageCalculatorTool()


# ===========================================================================
# DrugInteractionTool – get_definition()
# ===========================================================================

class TestDrugInteractionToolDefinition:

    def test_returns_tool_object(self):
        from ai.agents.models import Tool
        tool = make_drug_tool()
        assert isinstance(tool.get_definition(), Tool)

    def test_name_is_check_drug_interaction(self):
        tool = make_drug_tool()
        assert tool.get_definition().name == "check_drug_interaction"

    def test_has_non_empty_description(self):
        tool = make_drug_tool()
        assert len(tool.get_definition().description) > 0

    def test_has_exactly_two_parameters(self):
        tool = make_drug_tool()
        assert len(tool.get_definition().parameters) == 2

    def test_parameter_names_include_drug1(self):
        tool = make_drug_tool()
        names = [p.name for p in tool.get_definition().parameters]
        assert "drug1" in names

    def test_parameter_names_include_drug2(self):
        tool = make_drug_tool()
        names = [p.name for p in tool.get_definition().parameters]
        assert "drug2" in names

    def test_drug1_is_required(self):
        tool = make_drug_tool()
        param = next(p for p in tool.get_definition().parameters if p.name == "drug1")
        assert param.required is True

    def test_drug2_is_required(self):
        tool = make_drug_tool()
        param = next(p for p in tool.get_definition().parameters if p.name == "drug2")
        assert param.required is True

    def test_drug1_type_is_string(self):
        tool = make_drug_tool()
        param = next(p for p in tool.get_definition().parameters if p.name == "drug1")
        assert param.type == "string"

    def test_drug2_type_is_string(self):
        tool = make_drug_tool()
        param = next(p for p in tool.get_definition().parameters if p.name == "drug2")
        assert param.type == "string"


# ===========================================================================
# DrugInteractionTool – execute()
# ===========================================================================

class TestDrugInteractionToolExecute:

    # --- warfarin + aspirin ---

    def test_warfarin_aspirin_success_true(self):
        result = make_drug_tool().execute("warfarin", "aspirin")
        assert result.success is True

    def test_warfarin_aspirin_interaction_found(self):
        result = make_drug_tool().execute("warfarin", "aspirin")
        assert result.output["interaction_found"] is True

    def test_warfarin_aspirin_severity_major(self):
        result = make_drug_tool().execute("warfarin", "aspirin")
        assert result.output["severity"] == "Major"

    def test_warfarin_aspirin_has_description(self):
        result = make_drug_tool().execute("warfarin", "aspirin")
        assert result.output.get("description", "")

    def test_warfarin_aspirin_has_recommendation(self):
        result = make_drug_tool().execute("warfarin", "aspirin")
        assert "recommendation" in result.output

    def test_warfarin_aspirin_has_disclaimer(self):
        result = make_drug_tool().execute("warfarin", "aspirin")
        assert "disclaimer" in result.output

    def test_warfarin_aspirin_drug1_preserved(self):
        result = make_drug_tool().execute("warfarin", "aspirin")
        assert result.output["drug1"] == "warfarin"

    def test_warfarin_aspirin_drug2_preserved(self):
        result = make_drug_tool().execute("warfarin", "aspirin")
        assert result.output["drug2"] == "aspirin"

    def test_warfarin_aspirin_no_error(self):
        result = make_drug_tool().execute("warfarin", "aspirin")
        assert result.error is None

    def test_warfarin_aspirin_metadata_tool_key(self):
        result = make_drug_tool().execute("warfarin", "aspirin")
        assert result.metadata.get("tool") == "drug_interaction_checker"

    # --- reverse order ---

    def test_aspirin_warfarin_reverse_interaction_found(self):
        result = make_drug_tool().execute("aspirin", "warfarin")
        assert result.output["interaction_found"] is True

    def test_aspirin_warfarin_reverse_severity_major(self):
        result = make_drug_tool().execute("aspirin", "warfarin")
        assert result.output["severity"] == "Major"

    def test_aspirin_warfarin_reverse_success_true(self):
        result = make_drug_tool().execute("aspirin", "warfarin")
        assert result.success is True

    # --- case insensitivity ---

    def test_uppercase_warfarin_aspirin_found(self):
        result = make_drug_tool().execute("WARFARIN", "ASPIRIN")
        assert result.output["interaction_found"] is True

    def test_mixed_case_warfarin_aspirin_found(self):
        result = make_drug_tool().execute("Warfarin", "Aspirin")
        assert result.output["interaction_found"] is True

    def test_mixed_case_severity_still_major(self):
        result = make_drug_tool().execute("WaRfArIn", "AsPiRiN")
        assert result.output["severity"] == "Major"

    def test_whitespace_stripped_normalization(self):
        result = make_drug_tool().execute("  warfarin  ", "  aspirin  ")
        assert result.output["interaction_found"] is True

    # --- lisinopril + potassium ---

    def test_lisinopril_potassium_success_true(self):
        result = make_drug_tool().execute("lisinopril", "potassium")
        assert result.success is True

    def test_lisinopril_potassium_interaction_found(self):
        result = make_drug_tool().execute("lisinopril", "potassium")
        assert result.output["interaction_found"] is True

    def test_lisinopril_potassium_severity_moderate(self):
        result = make_drug_tool().execute("lisinopril", "potassium")
        assert result.output["severity"] == "Moderate"

    def test_potassium_lisinopril_reverse_found(self):
        result = make_drug_tool().execute("potassium", "lisinopril")
        assert result.output["interaction_found"] is True

    # --- metformin + alcohol ---

    def test_metformin_alcohol_success_true(self):
        result = make_drug_tool().execute("metformin", "alcohol")
        assert result.success is True

    def test_metformin_alcohol_interaction_found(self):
        result = make_drug_tool().execute("metformin", "alcohol")
        assert result.output["interaction_found"] is True

    def test_metformin_alcohol_severity_moderate(self):
        result = make_drug_tool().execute("metformin", "alcohol")
        assert result.output["severity"] == "Moderate"

    def test_alcohol_metformin_reverse_found(self):
        result = make_drug_tool().execute("alcohol", "metformin")
        assert result.output["interaction_found"] is True

    # --- unknown drugs ---

    def test_unknown_drugs_success_true(self):
        result = make_drug_tool().execute("ibuprofen", "acetaminophen")
        assert result.success is True

    def test_unknown_drugs_interaction_found_false(self):
        result = make_drug_tool().execute("ibuprofen", "acetaminophen")
        assert result.output["interaction_found"] is False

    def test_unknown_drugs_has_message_field(self):
        result = make_drug_tool().execute("ibuprofen", "acetaminophen")
        assert "message" in result.output

    def test_unknown_drugs_no_severity_field(self):
        result = make_drug_tool().execute("ibuprofen", "acetaminophen")
        assert "severity" not in result.output

    def test_unknown_drugs_drug1_preserved(self):
        result = make_drug_tool().execute("ibuprofen", "acetaminophen")
        assert result.output["drug1"] == "ibuprofen"

    def test_unknown_drugs_drug2_preserved(self):
        result = make_drug_tool().execute("ibuprofen", "acetaminophen")
        assert result.output["drug2"] == "acetaminophen"

    def test_unknown_drugs_no_error(self):
        result = make_drug_tool().execute("drug_x", "drug_y")
        assert result.error is None


# ===========================================================================
# BMICalculatorTool – get_definition()
# ===========================================================================

class TestBMICalculatorToolDefinition:

    def test_returns_tool_object(self):
        from ai.agents.models import Tool
        tool = make_bmi_tool()
        assert isinstance(tool.get_definition(), Tool)

    def test_name_is_calculate_bmi(self):
        tool = make_bmi_tool()
        assert tool.get_definition().name == "calculate_bmi"

    def test_has_non_empty_description(self):
        tool = make_bmi_tool()
        assert len(tool.get_definition().description) > 0

    def test_has_exactly_two_parameters(self):
        tool = make_bmi_tool()
        assert len(tool.get_definition().parameters) == 2

    def test_parameter_names_include_weight(self):
        tool = make_bmi_tool()
        names = [p.name for p in tool.get_definition().parameters]
        assert "weight" in names

    def test_parameter_names_include_height(self):
        tool = make_bmi_tool()
        names = [p.name for p in tool.get_definition().parameters]
        assert "height" in names

    def test_weight_is_required(self):
        tool = make_bmi_tool()
        param = next(p for p in tool.get_definition().parameters if p.name == "weight")
        assert param.required is True

    def test_height_is_required(self):
        tool = make_bmi_tool()
        param = next(p for p in tool.get_definition().parameters if p.name == "height")
        assert param.required is True

    def test_weight_type_is_number(self):
        tool = make_bmi_tool()
        param = next(p for p in tool.get_definition().parameters if p.name == "weight")
        assert param.type == "number"

    def test_height_type_is_number(self):
        tool = make_bmi_tool()
        param = next(p for p in tool.get_definition().parameters if p.name == "height")
        assert param.type == "number"


# ===========================================================================
# BMICalculatorTool – execute()
# ===========================================================================

class TestBMICalculatorToolExecute:

    # --- normal weight: 70 kg, 175 cm ---

    def test_normal_weight_success_true(self):
        result = make_bmi_tool().execute(70, 175)
        assert result.success is True

    def test_normal_weight_bmi_approx_22_9(self):
        result = make_bmi_tool().execute(70, 175)
        # 70 / (1.75^2) = 22.857... rounds to 22.9
        assert abs(result.output["bmi"] - 22.9) < 0.2

    def test_normal_weight_category(self):
        result = make_bmi_tool().execute(70, 175)
        assert result.output["category"] == "Normal weight"

    def test_normal_weight_no_error(self):
        result = make_bmi_tool().execute(70, 175)
        assert result.error is None

    # --- underweight: 50 kg, 175 cm ---

    def test_underweight_category(self):
        result = make_bmi_tool().execute(50, 175)
        assert result.output["category"] == "Underweight"

    def test_underweight_bmi_below_18_5(self):
        result = make_bmi_tool().execute(50, 175)
        assert result.output["bmi"] < 18.5

    # --- overweight: 90 kg, 175 cm ---

    def test_overweight_category(self):
        result = make_bmi_tool().execute(90, 175)
        assert result.output["category"] == "Overweight"

    def test_overweight_bmi_in_range(self):
        result = make_bmi_tool().execute(90, 175)
        assert 25 <= result.output["bmi"] < 30

    # --- obese class I: 100 kg, 175 cm → BMI ≈ 32.7 ---

    def test_obese_class_1_category(self):
        result = make_bmi_tool().execute(100, 175)
        assert result.output["category"] == "Obese Class I"

    def test_obese_class_1_bmi_in_range(self):
        result = make_bmi_tool().execute(100, 175)
        assert 30 <= result.output["bmi"] < 35

    # --- obese class II: 115 kg, 175 cm → BMI ≈ 37.6 ---

    def test_obese_class_2_category(self):
        result = make_bmi_tool().execute(115, 175)
        assert result.output["category"] == "Obese Class II"

    def test_obese_class_2_bmi_in_range(self):
        result = make_bmi_tool().execute(115, 175)
        assert 35 <= result.output["bmi"] < 40

    # --- obese class III: 130 kg, 175 cm → BMI ≈ 42.4 ---

    def test_obese_class_3_category(self):
        result = make_bmi_tool().execute(130, 175)
        assert result.output["category"] == "Obese Class III"

    def test_obese_class_3_bmi_gte_40(self):
        result = make_bmi_tool().execute(130, 175)
        assert result.output["bmi"] >= 40

    # --- BMI rounding ---

    def test_bmi_rounded_to_one_decimal(self):
        result = make_bmi_tool().execute(70, 175)
        bmi = result.output["bmi"]
        assert round(bmi, 1) == bmi

    # --- ideal weight range ---

    def test_ideal_weight_range_present(self):
        result = make_bmi_tool().execute(70, 175)
        assert "ideal_weight_range" in result.output

    def test_ideal_weight_range_has_min_kg(self):
        result = make_bmi_tool().execute(70, 175)
        assert "min_kg" in result.output["ideal_weight_range"]

    def test_ideal_weight_range_has_max_kg(self):
        result = make_bmi_tool().execute(70, 175)
        assert "max_kg" in result.output["ideal_weight_range"]

    def test_ideal_weight_range_min_less_than_max(self):
        result = make_bmi_tool().execute(70, 175)
        rng = result.output["ideal_weight_range"]
        assert rng["min_kg"] < rng["max_kg"]

    def test_ideal_weight_range_min_matches_bmi_18_5(self):
        result = make_bmi_tool().execute(70, 175)
        expected_min = round(18.5 * (1.75 ** 2), 1)
        assert abs(result.output["ideal_weight_range"]["min_kg"] - expected_min) < 0.2

    def test_ideal_weight_range_max_matches_bmi_24_9(self):
        result = make_bmi_tool().execute(70, 175)
        expected_max = round(24.9 * (1.75 ** 2), 1)
        assert abs(result.output["ideal_weight_range"]["max_kg"] - expected_max) < 0.2

    # --- echoed fields ---

    def test_weight_kg_echoed_in_output(self):
        result = make_bmi_tool().execute(70, 175)
        assert result.output["weight_kg"] == 70

    def test_height_cm_echoed_in_output(self):
        result = make_bmi_tool().execute(70, 175)
        assert result.output["height_cm"] == 175

    def test_health_risk_present(self):
        result = make_bmi_tool().execute(70, 175)
        assert "health_risk" in result.output

    def test_metadata_calculation_bmi(self):
        result = make_bmi_tool().execute(70, 175)
        assert result.metadata.get("calculation") == "BMI"

    # --- invalid inputs ---

    def test_height_zero_success_false(self):
        result = make_bmi_tool().execute(70, 0)
        assert result.success is False

    def test_height_zero_output_none(self):
        result = make_bmi_tool().execute(70, 0)
        assert result.output is None

    def test_height_zero_has_error_message(self):
        result = make_bmi_tool().execute(70, 0)
        assert result.error and len(result.error) > 0

    def test_weight_zero_success_false(self):
        result = make_bmi_tool().execute(0, 175)
        assert result.success is False

    def test_weight_zero_output_none(self):
        result = make_bmi_tool().execute(0, 175)
        assert result.output is None

    def test_negative_height_success_false(self):
        result = make_bmi_tool().execute(70, -175)
        assert result.success is False

    def test_negative_weight_success_false(self):
        result = make_bmi_tool().execute(-70, 175)
        assert result.success is False

    def test_both_negative_success_false(self):
        result = make_bmi_tool().execute(-70, -175)
        assert result.success is False

    # --- boundary values ---

    def test_bmi_exactly_18_5_is_normal_weight(self):
        """Weight = 18.5 * (1.75^2) ≈ 56.6 kg → BMI = 18.5 → Normal weight."""
        height_m = 1.75
        weight = 18.5 * (height_m ** 2)
        result = make_bmi_tool().execute(weight, 175)
        assert result.output["category"] == "Normal weight"

    def test_bmi_just_below_18_5_is_underweight(self):
        height_m = 1.75
        weight = 18.4 * (height_m ** 2)
        result = make_bmi_tool().execute(weight, 175)
        assert result.output["category"] == "Underweight"


# ===========================================================================
# DosageCalculatorTool – get_definition()
# ===========================================================================

class TestDosageCalculatorToolDefinition:

    def test_returns_tool_object(self):
        from ai.agents.models import Tool
        tool = make_dose_tool()
        assert isinstance(tool.get_definition(), Tool)

    def test_name_is_calculate_dosage(self):
        tool = make_dose_tool()
        assert tool.get_definition().name == "calculate_dosage"

    def test_has_non_empty_description(self):
        tool = make_dose_tool()
        assert len(tool.get_definition().description) > 0

    def test_has_medication_parameter(self):
        tool = make_dose_tool()
        names = [p.name for p in tool.get_definition().parameters]
        assert "medication" in names

    def test_has_dose_per_kg_parameter(self):
        tool = make_dose_tool()
        names = [p.name for p in tool.get_definition().parameters]
        assert "dose_per_kg" in names

    def test_has_weight_parameter(self):
        tool = make_dose_tool()
        names = [p.name for p in tool.get_definition().parameters]
        assert "weight" in names

    def test_has_frequency_parameter(self):
        tool = make_dose_tool()
        names = [p.name for p in tool.get_definition().parameters]
        assert "frequency" in names

    def test_has_max_dose_parameter(self):
        tool = make_dose_tool()
        names = [p.name for p in tool.get_definition().parameters]
        assert "max_dose" in names

    def test_medication_is_required(self):
        tool = make_dose_tool()
        param = next(p for p in tool.get_definition().parameters if p.name == "medication")
        assert param.required is True

    def test_dose_per_kg_is_required(self):
        tool = make_dose_tool()
        param = next(p for p in tool.get_definition().parameters if p.name == "dose_per_kg")
        assert param.required is True

    def test_weight_is_required(self):
        tool = make_dose_tool()
        param = next(p for p in tool.get_definition().parameters if p.name == "weight")
        assert param.required is True

    def test_frequency_is_not_required(self):
        tool = make_dose_tool()
        param = next(p for p in tool.get_definition().parameters if p.name == "frequency")
        assert param.required is False

    def test_max_dose_is_not_required(self):
        tool = make_dose_tool()
        param = next(p for p in tool.get_definition().parameters if p.name == "max_dose")
        assert param.required is False


# ===========================================================================
# DosageCalculatorTool – execute()
# ===========================================================================

class TestDosageCalculatorToolExecute:

    # --- basic once-daily ---

    def test_basic_once_daily_success_true(self):
        result = make_dose_tool().execute("amoxicillin", 1.0, 70, "once daily")
        assert result.success is True

    def test_basic_once_daily_calculated_dose(self):
        """1 mg/kg * 70 kg = 70 mg."""
        result = make_dose_tool().execute("amoxicillin", 1.0, 70, "once daily")
        assert abs(result.output["calculated_dose_mg"] - 70.0) < 0.01

    def test_basic_once_daily_actual_dose_equals_calculated(self):
        result = make_dose_tool().execute("amoxicillin", 1.0, 70, "once daily")
        assert abs(result.output["actual_dose_mg"] - 70.0) < 0.01

    def test_basic_once_daily_daily_total(self):
        result = make_dose_tool().execute("amoxicillin", 1.0, 70, "once daily")
        assert abs(result.output["daily_total_mg"] - 70.0) < 0.01

    def test_basic_once_daily_doses_per_day(self):
        result = make_dose_tool().execute("amoxicillin", 1.0, 70, "once daily")
        assert result.output["doses_per_day"] == 1

    def test_basic_once_daily_no_error(self):
        result = make_dose_tool().execute("amoxicillin", 1.0, 70, "once daily")
        assert result.error is None

    # --- frequency mapping ---

    def test_twice_daily_doses_per_day(self):
        result = make_dose_tool().execute("amoxicillin", 1.0, 70, "twice daily")
        assert result.output["doses_per_day"] == 2

    def test_twice_daily_daily_total_doubled(self):
        result = make_dose_tool().execute("amoxicillin", 1.0, 70, "twice daily")
        assert abs(result.output["daily_total_mg"] - 140.0) < 0.01

    def test_three_times_daily_doses_per_day(self):
        result = make_dose_tool().execute("drug", 1.0, 60, "three times daily")
        assert result.output["doses_per_day"] == 3

    def test_three_times_daily_daily_total(self):
        result = make_dose_tool().execute("drug", 1.0, 60, "three times daily")
        assert abs(result.output["daily_total_mg"] - 180.0) < 0.01

    def test_four_times_daily_doses_per_day(self):
        result = make_dose_tool().execute("drug", 1.0, 60, "four times daily")
        assert result.output["doses_per_day"] == 4

    def test_every_8_hours_doses_per_day(self):
        result = make_dose_tool().execute("drug", 1.0, 60, "every 8 hours")
        assert result.output["doses_per_day"] == 3

    def test_every_12_hours_doses_per_day(self):
        result = make_dose_tool().execute("drug", 1.0, 60, "every 12 hours")
        assert result.output["doses_per_day"] == 2

    def test_every_6_hours_doses_per_day(self):
        result = make_dose_tool().execute("drug", 1.0, 60, "every 6 hours")
        assert result.output["doses_per_day"] == 4

    def test_every_4_hours_doses_per_day(self):
        result = make_dose_tool().execute("drug", 1.0, 60, "every 4 hours")
        assert result.output["doses_per_day"] == 6

    def test_unknown_frequency_defaults_to_1_dose_per_day(self):
        """Unrecognised frequency string should fall back to 1 dose/day."""
        result = make_dose_tool().execute("amoxicillin", 1.0, 70, "weekly")
        assert result.success is True
        assert result.output["doses_per_day"] == 1
        assert abs(result.output["daily_total_mg"] - 70.0) < 0.01

    # --- max_dose capping ---

    def test_max_dose_limits_actual_dose(self):
        """1 mg/kg * 70 kg = 70 mg, capped at 50 mg."""
        result = make_dose_tool().execute("amoxicillin", 1.0, 70, "once daily", max_dose=50.0)
        assert abs(result.output["actual_dose_mg"] - 50.0) < 0.01

    def test_max_dose_calculated_dose_unchanged(self):
        result = make_dose_tool().execute("amoxicillin", 1.0, 70, "once daily", max_dose=50.0)
        assert abs(result.output["calculated_dose_mg"] - 70.0) < 0.01

    def test_max_dose_dose_limited_true(self):
        result = make_dose_tool().execute("amoxicillin", 1.0, 70, "once daily", max_dose=50.0)
        assert result.output["dose_limited"] is True

    def test_max_dose_warning_present(self):
        result = make_dose_tool().execute("amoxicillin", 1.0, 70, "once daily", max_dose=50.0)
        assert "warning" in result.output

    def test_max_dose_daily_total_uses_capped_actual_dose(self):
        """daily_total = actual_dose * doses_per_day (50 mg * 2 = 100 mg)."""
        result = make_dose_tool().execute("amoxicillin", 1.0, 70, "twice daily", max_dose=50.0)
        assert abs(result.output["daily_total_mg"] - 100.0) < 0.01

    def test_no_max_dose_dose_limited_false(self):
        result = make_dose_tool().execute("amoxicillin", 1.0, 70, "once daily")
        assert result.output["dose_limited"] is False

    def test_max_dose_not_exceeded_dose_limited_false(self):
        result = make_dose_tool().execute("amoxicillin", 1.0, 70, "once daily", max_dose=100.0)
        assert result.output["dose_limited"] is False

    # --- invalid inputs ---

    def test_weight_zero_success_false(self):
        result = make_dose_tool().execute("amoxicillin", 1.0, 0)
        assert result.success is False

    def test_weight_zero_output_none(self):
        result = make_dose_tool().execute("amoxicillin", 1.0, 0)
        assert result.output is None

    def test_weight_zero_has_error(self):
        result = make_dose_tool().execute("amoxicillin", 1.0, 0)
        assert result.error is not None

    def test_dose_per_kg_zero_success_false(self):
        result = make_dose_tool().execute("amoxicillin", 0, 70)
        assert result.success is False

    def test_negative_weight_success_false(self):
        result = make_dose_tool().execute("amoxicillin", 1.0, -70)
        assert result.success is False

    # --- result structure ---

    def test_medication_name_echoed(self):
        result = make_dose_tool().execute("amoxicillin", 1.0, 70)
        assert result.output["medication"] == "amoxicillin"

    def test_patient_weight_echoed(self):
        result = make_dose_tool().execute("amoxicillin", 1.0, 70)
        assert result.output["patient_weight_kg"] == 70

    def test_frequency_echoed(self):
        result = make_dose_tool().execute("amoxicillin", 1.0, 70, "twice daily")
        assert result.output["frequency"] == "twice daily"

    def test_metadata_calculation_dosage(self):
        result = make_dose_tool().execute("amoxicillin", 1.0, 70)
        assert result.metadata.get("calculation") == "dosage"

    def test_default_frequency_is_once_daily(self):
        """Calling without explicit frequency defaults to once daily."""
        result = make_dose_tool().execute("amoxicillin", 1.0, 70)
        assert result.output["doses_per_day"] == 1

    def test_fractional_dose_per_kg(self):
        """0.5 mg/kg * 60 kg = 30 mg."""
        result = make_dose_tool().execute("drug", 0.5, 60, "once daily")
        assert abs(result.output["calculated_dose_mg"] - 30.0) < 0.01
