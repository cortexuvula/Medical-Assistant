"""
Tests for src/ai/tools/medical_tools.py

Covers DrugInteractionTool, BMICalculatorTool, and DosageCalculatorTool —
all three are pure-logic tools with no external I/O.
Also covers BaseTool.validate_arguments and _validate_type.
No Tkinter, no network, no file I/O.
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

from ai.tools.medical_tools import (
    DrugInteractionTool,
    BMICalculatorTool,
    DosageCalculatorTool,
)
from ai.tools.base_tool import ToolResult


# ===========================================================================
# DrugInteractionTool
# ===========================================================================

class TestDrugInteractionTool:
    def setup_method(self):
        self.tool = DrugInteractionTool()

    # ---------- get_definition ----------

    def test_definition_name(self):
        defn = self.tool.get_definition()
        assert defn.name == "check_drug_interaction"

    def test_definition_has_two_parameters(self):
        defn = self.tool.get_definition()
        assert len(defn.parameters) == 2

    def test_definition_drug1_required(self):
        defn = self.tool.get_definition()
        drug1_param = next(p for p in defn.parameters if p.name == "drug1")
        assert drug1_param.required is True

    def test_definition_drug2_required(self):
        defn = self.tool.get_definition()
        drug2_param = next(p for p in defn.parameters if p.name == "drug2")
        assert drug2_param.required is True

    # ---------- known interactions ----------

    def test_warfarin_aspirin_interaction_found(self):
        result = self.tool.execute(drug1="warfarin", drug2="aspirin")
        assert result.success is True
        assert result.output["interaction_found"] is True

    def test_warfarin_aspirin_severity_major(self):
        result = self.tool.execute(drug1="warfarin", drug2="aspirin")
        assert result.output["severity"] == "Major"

    def test_aspirin_warfarin_reversed_order_also_found(self):
        result = self.tool.execute(drug1="aspirin", drug2="warfarin")
        assert result.output["interaction_found"] is True

    def test_lisinopril_potassium_interaction_found(self):
        result = self.tool.execute(drug1="lisinopril", drug2="potassium")
        assert result.output["interaction_found"] is True
        assert result.output["severity"] == "Moderate"

    def test_metformin_alcohol_interaction_found(self):
        result = self.tool.execute(drug1="metformin", drug2="alcohol")
        assert result.output["interaction_found"] is True

    # ---------- case insensitivity ----------

    def test_uppercase_drugs_normalized(self):
        result = self.tool.execute(drug1="WARFARIN", drug2="ASPIRIN")
        assert result.output["interaction_found"] is True

    def test_mixed_case_drugs(self):
        result = self.tool.execute(drug1="Warfarin", drug2="Aspirin")
        assert result.output["interaction_found"] is True

    # ---------- no interaction ----------

    def test_unknown_drug_pair_no_interaction(self):
        result = self.tool.execute(drug1="ibuprofen", drug2="zinc_tablet")
        assert result.success is True
        assert result.output["interaction_found"] is False

    def test_no_interaction_result_has_message(self):
        result = self.tool.execute(drug1="vitamin_c", drug2="magnesium")
        assert "message" in result.output

    # ---------- result structure ----------

    def test_result_is_tool_result(self):
        result = self.tool.execute(drug1="warfarin", drug2="aspirin")
        assert isinstance(result, ToolResult)

    def test_result_output_contains_drug_names(self):
        result = self.tool.execute(drug1="warfarin", drug2="aspirin")
        assert "warfarin" in result.output["drug1"].lower() or "warfarin" == result.output["drug1"].lower()

    def test_interaction_result_has_disclaimer(self):
        result = self.tool.execute(drug1="warfarin", drug2="aspirin")
        assert "disclaimer" in result.output or "DEMO" in str(result.output)

    def test_interaction_result_has_recommendation(self):
        result = self.tool.execute(drug1="warfarin", drug2="aspirin")
        assert "recommendation" in result.output

    def test_metadata_contains_tool_key(self):
        result = self.tool.execute(drug1="warfarin", drug2="aspirin")
        assert "tool" in result.metadata


# ===========================================================================
# BMICalculatorTool
# ===========================================================================

class TestBMICalculatorTool:
    def setup_method(self):
        self.tool = BMICalculatorTool()

    # ---------- get_definition ----------

    def test_definition_name(self):
        defn = self.tool.get_definition()
        assert defn.name == "calculate_bmi"

    def test_definition_has_two_parameters(self):
        defn = self.tool.get_definition()
        assert len(defn.parameters) == 2

    # ---------- BMI calculation correctness ----------

    def test_normal_weight_bmi(self):
        # 70kg, 175cm → BMI ≈ 22.9
        result = self.tool.execute(weight=70, height=175)
        assert result.success is True
        assert abs(result.output["bmi"] - 22.9) < 0.2

    def test_underweight_category(self):
        # 45kg, 175cm → BMI ≈ 14.7 → Underweight
        result = self.tool.execute(weight=45, height=175)
        assert "Underweight" in result.output["category"]

    def test_normal_weight_category(self):
        # 70kg, 175cm → BMI ≈ 22.9 → Normal weight
        result = self.tool.execute(weight=70, height=175)
        assert "Normal" in result.output["category"]

    def test_overweight_category(self):
        # 85kg, 175cm → BMI ≈ 27.8 → Overweight
        result = self.tool.execute(weight=85, height=175)
        assert "Overweight" in result.output["category"]

    def test_obese_class_i_category(self):
        # 100kg, 175cm → BMI ≈ 32.7 → Obese Class I
        result = self.tool.execute(weight=100, height=175)
        assert "Obese Class I" in result.output["category"]

    def test_obese_class_ii_category(self):
        # 120kg, 175cm → BMI ≈ 39.2 → Obese Class II
        result = self.tool.execute(weight=120, height=175)
        assert "Obese Class II" in result.output["category"]

    def test_obese_class_iii_category(self):
        # 150kg, 175cm → BMI ≈ 49 → Obese Class III
        result = self.tool.execute(weight=150, height=175)
        assert "Obese Class III" in result.output["category"]

    def test_ideal_weight_range_min_is_positive(self):
        result = self.tool.execute(weight=70, height=175)
        assert result.output["ideal_weight_range"]["min_kg"] > 0

    def test_ideal_weight_range_max_greater_than_min(self):
        result = self.tool.execute(weight=70, height=175)
        rng = result.output["ideal_weight_range"]
        assert rng["max_kg"] > rng["min_kg"]

    def test_result_contains_health_risk(self):
        result = self.tool.execute(weight=70, height=175)
        assert "health_risk" in result.output

    def test_result_contains_weight_and_height(self):
        result = self.tool.execute(weight=70, height=175)
        assert result.output["weight_kg"] == 70
        assert result.output["height_cm"] == 175

    # ---------- validation ----------

    def test_zero_height_returns_failure(self):
        result = self.tool.execute(weight=70, height=0)
        assert result.success is False
        assert result.error is not None

    def test_zero_weight_returns_failure(self):
        result = self.tool.execute(weight=0, height=175)
        assert result.success is False

    def test_negative_height_returns_failure(self):
        result = self.tool.execute(weight=70, height=-10)
        assert result.success is False

    def test_negative_weight_returns_failure(self):
        result = self.tool.execute(weight=-5, height=175)
        assert result.success is False

    # ---------- BMI boundary values ----------

    def test_bmi_boundary_18_5_is_normal(self):
        # At exactly 18.5, should be "Normal weight"
        # weight = 18.5 * (1.75)^2 ≈ 56.6 kg
        height_m = 1.75
        weight = 18.5 * height_m ** 2
        result = self.tool.execute(weight=weight, height=175)
        assert "Normal" in result.output["category"]

    def test_bmi_rounding_to_one_decimal(self):
        result = self.tool.execute(weight=70, height=175)
        bmi = result.output["bmi"]
        # Should be rounded to 1 decimal place
        assert bmi == round(bmi, 1)

    def test_metadata_contains_calculation_key(self):
        result = self.tool.execute(weight=70, height=175)
        assert result.metadata.get("calculation") == "BMI"


# ===========================================================================
# DosageCalculatorTool
# ===========================================================================

class TestDosageCalculatorTool:
    def setup_method(self):
        self.tool = DosageCalculatorTool()

    # ---------- get_definition ----------

    def test_definition_name(self):
        defn = self.tool.get_definition()
        assert defn.name == "calculate_dosage"

    def test_definition_has_five_parameters(self):
        defn = self.tool.get_definition()
        assert len(defn.parameters) == 5

    def test_frequency_parameter_has_default(self):
        defn = self.tool.get_definition()
        freq_param = next(p for p in defn.parameters if p.name == "frequency")
        assert freq_param.required is False

    # ---------- basic calculation ----------

    def test_simple_dosage_calculation(self):
        # 2mg/kg, 50kg patient → 100mg
        result = self.tool.execute(
            medication="amoxicillin",
            dose_per_kg=2.0,
            weight=50.0
        )
        assert result.success is True
        assert result.output["calculated_dose_mg"] == 100.0

    def test_once_daily_frequency(self):
        result = self.tool.execute(
            medication="amoxicillin",
            dose_per_kg=2.0,
            weight=50.0,
            frequency="once daily"
        )
        assert result.output["doses_per_day"] == 1
        assert result.output["daily_total_mg"] == 100.0

    def test_twice_daily_frequency(self):
        result = self.tool.execute(
            medication="amoxicillin",
            dose_per_kg=2.0,
            weight=50.0,
            frequency="twice daily"
        )
        assert result.output["doses_per_day"] == 2
        assert result.output["daily_total_mg"] == 200.0

    def test_three_times_daily_frequency(self):
        result = self.tool.execute(
            medication="amoxicillin",
            dose_per_kg=2.0,
            weight=50.0,
            frequency="three times daily"
        )
        assert result.output["doses_per_day"] == 3

    def test_every_8_hours_frequency(self):
        result = self.tool.execute(
            medication="amoxicillin",
            dose_per_kg=2.0,
            weight=50.0,
            frequency="every 8 hours"
        )
        assert result.output["doses_per_day"] == 3

    def test_every_6_hours_frequency(self):
        result = self.tool.execute(
            medication="amoxicillin",
            dose_per_kg=2.0,
            weight=50.0,
            frequency="every 6 hours"
        )
        assert result.output["doses_per_day"] == 4

    def test_every_4_hours_frequency(self):
        result = self.tool.execute(
            medication="amoxicillin",
            dose_per_kg=2.0,
            weight=50.0,
            frequency="every 4 hours"
        )
        assert result.output["doses_per_day"] == 6

    def test_every_12_hours_frequency(self):
        result = self.tool.execute(
            medication="amoxicillin",
            dose_per_kg=2.0,
            weight=50.0,
            frequency="every 12 hours"
        )
        assert result.output["doses_per_day"] == 2

    # ---------- max dose limiting ----------

    def test_max_dose_limits_actual_dose(self):
        # 2mg/kg * 100kg = 200mg, but max is 150mg
        result = self.tool.execute(
            medication="medication_x",
            dose_per_kg=2.0,
            weight=100.0,
            max_dose=150.0
        )
        assert result.success is True
        assert result.output["actual_dose_mg"] == 150.0
        assert result.output["dose_limited"] is True

    def test_below_max_dose_not_limited(self):
        # 2mg/kg * 50kg = 100mg, max is 200mg — no limiting
        result = self.tool.execute(
            medication="medication_x",
            dose_per_kg=2.0,
            weight=50.0,
            max_dose=200.0
        )
        assert result.output["dose_limited"] is False
        assert result.output["actual_dose_mg"] == 100.0

    def test_dose_limited_includes_warning(self):
        result = self.tool.execute(
            medication="medication_x",
            dose_per_kg=2.0,
            weight=100.0,
            max_dose=150.0
        )
        assert "warning" in result.output

    # ---------- validation ----------

    def test_zero_weight_returns_failure(self):
        result = self.tool.execute(
            medication="amoxicillin",
            dose_per_kg=2.0,
            weight=0
        )
        assert result.success is False

    def test_zero_dose_per_kg_returns_failure(self):
        result = self.tool.execute(
            medication="amoxicillin",
            dose_per_kg=0,
            weight=50.0
        )
        assert result.success is False

    def test_negative_weight_returns_failure(self):
        result = self.tool.execute(
            medication="amoxicillin",
            dose_per_kg=2.0,
            weight=-10
        )
        assert result.success is False

    # ---------- result structure ----------

    def test_result_contains_medication_name(self):
        result = self.tool.execute(
            medication="amoxicillin",
            dose_per_kg=2.0,
            weight=50.0
        )
        assert result.output["medication"] == "amoxicillin"

    def test_result_contains_patient_weight(self):
        result = self.tool.execute(
            medication="amoxicillin",
            dose_per_kg=2.0,
            weight=70.5
        )
        assert result.output["patient_weight_kg"] == 70.5

    def test_metadata_contains_calculation(self):
        result = self.tool.execute(
            medication="amoxicillin",
            dose_per_kg=2.0,
            weight=50.0
        )
        assert result.metadata.get("calculation") == "dosage"

    def test_unknown_frequency_defaults_to_once_daily(self):
        result = self.tool.execute(
            medication="amoxicillin",
            dose_per_kg=2.0,
            weight=50.0,
            frequency="bi-weekly"  # Not in frequency_map
        )
        # Unknown frequency → doses_per_day = 1
        assert result.output["doses_per_day"] == 1


# ===========================================================================
# BaseTool: validate_arguments and _validate_type (via concrete subclass)
# ===========================================================================

class TestBaseTool:
    def setup_method(self):
        # Use BMICalculatorTool as a concrete BaseTool for testing
        self.tool = BMICalculatorTool()

    def test_validate_type_string(self):
        assert self.tool._validate_type("hello", "string") is True

    def test_validate_type_integer(self):
        assert self.tool._validate_type(42, "integer") is True

    def test_validate_type_float_as_number(self):
        assert self.tool._validate_type(3.14, "number") is True

    def test_validate_type_int_as_number(self):
        assert self.tool._validate_type(5, "number") is True

    def test_validate_type_bool(self):
        assert self.tool._validate_type(True, "boolean") is True

    def test_validate_type_list_as_array(self):
        assert self.tool._validate_type([1, 2], "array") is True

    def test_validate_type_dict_as_object(self):
        assert self.tool._validate_type({"k": "v"}, "object") is True

    def test_validate_type_unknown_type_returns_true(self):
        assert self.tool._validate_type("anything", "custom_type") is True

    def test_validate_type_wrong_type_returns_false(self):
        assert self.tool._validate_type("hello", "integer") is False

    def test_validate_type_float_not_string(self):
        assert self.tool._validate_type(3.14, "string") is False

    def test_validate_arguments_valid_bmi(self):
        error = self.tool.validate_arguments(weight=70, height=175)
        assert error is None

    def test_validate_arguments_missing_required(self):
        error = self.tool.validate_arguments(weight=70)  # missing height
        assert error is not None
        assert "height" in error

    def test_validate_arguments_wrong_type(self):
        error = self.tool.validate_arguments(weight="heavy", height=175)
        assert error is not None

    def test_safe_execute_validates_first(self):
        # Missing required arg → safe_execute returns failure
        result = self.tool.safe_execute(weight=70)
        assert result.success is False
        assert result.error is not None

    def test_safe_execute_success_path(self):
        result = self.tool.safe_execute(weight=70, height=175)
        assert result.success is True
