"""
Comprehensive tests for ToolRegistry in src/ai/agents/registry.py.

All methods are pure dict operations with no I/O, so no mocking is needed.

Test classes:
  TestToolRegistryInit          (6)
  TestGetTool                   (8)
  TestListTools                 (5)
  TestRegisterTool              (8)
  TestRemoveTool                (8)
  TestGetToolsForAgent         (12)
  TestDefaultToolStructure      (8)
  ── extra parametrized edge-case classes (keeps the existing coverage) ──
  TestDefaultToolParameterCounts
  TestCaseSensitivity
  TestModuleLevelSingleton
"""

import sys
import logging
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.agents.registry import ToolRegistry, tool_registry
from ai.agents.models import Tool, ToolParameter


# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------

ALL_DEFAULT_TOOL_NAMES = [
    "search_icd_codes",
    "lookup_drug_interactions",
    "search_medications",
    "calculate_dosage",
    "check_contraindications",
    "format_prescription",
    "check_duplicate_therapy",
    "format_referral",
    "extract_vitals",
    "calculate_bmi",
]

MEDICATION_TOOL_NAMES = [
    "lookup_drug_interactions",
    "search_medications",
    "calculate_dosage",
    "check_contraindications",
    "format_prescription",
    "check_duplicate_therapy",
]

DIAGNOSTIC_TOOL_NAMES = [
    "search_icd_codes",
    "extract_vitals",
    "calculate_bmi",
]

REFERRAL_TOOL_NAMES = [
    "format_referral",
]


@pytest.fixture
def registry():
    return ToolRegistry()


def make_tool(name="test_tool", description="A test tool", params=None):
    params = params or []
    return Tool(name=name, description=description, parameters=params)


def make_param(name="p", type_="string", required=True, default=None):
    return ToolParameter(
        name=name,
        type=type_,
        description=f"Parameter {name}",
        required=required,
        default=default,
    )


def _get_param(registry: ToolRegistry, tool_name: str, param_name: str):
    """Return the named ToolParameter from the named tool, or None."""
    tool = registry.get_tool(tool_name)
    assert tool is not None, f"Tool '{tool_name}' not found in registry"
    for p in tool.parameters:
        if p.name == param_name:
            return p
    return None


# ===========================================================================
# TestToolRegistryInit  (6 tests)
# ===========================================================================

class TestToolRegistryInit:
    """Instance creation and initial state."""

    def test_instance_created_without_error(self):
        reg = ToolRegistry()
        assert reg is not None

    def test_has_ten_default_tools(self, registry):
        assert len(registry._tools) == 10

    def test_spot_check_five_default_tool_names_present(self, registry):
        spot_check = [
            "search_icd_codes",
            "calculate_bmi",
            "format_prescription",
            "extract_vitals",
            "lookup_drug_interactions",
        ]
        for name in spot_check:
            assert name in registry._tools, f"Expected default tool '{name}' not found"

    def test_tools_attribute_is_dict(self, registry):
        assert isinstance(registry._tools, dict)

    def test_list_tools_returns_copy_not_reference(self, registry):
        copy = registry.list_tools()
        copy["injected"] = make_tool("injected")
        assert "injected" not in registry._tools

    def test_each_default_tool_is_tool_instance(self, registry):
        for name, tool in registry._tools.items():
            assert isinstance(tool, Tool), (
                f"Tool '{name}' is {type(tool)}, expected Tool"
            )


# ===========================================================================
# TestGetTool  (8 tests)
# ===========================================================================

class TestGetTool:
    """ToolRegistry.get_tool behaviour."""

    def test_get_tool_returns_correct_tool_for_known_name(self, registry):
        tool = registry.get_tool("calculate_bmi")
        assert tool is not None
        assert tool.name == "calculate_bmi"

    def test_get_tool_returns_none_for_unknown_name(self, registry):
        assert registry.get_tool("nonexistent_tool") is None

    def test_get_tool_returns_none_for_empty_string(self, registry):
        assert registry.get_tool("") is None

    def test_get_tool_is_case_sensitive_wrong_case_returns_none(self, registry):
        assert registry.get_tool("Calculate_BMI") is None
        assert registry.get_tool("CALCULATE_BMI") is None
        assert registry.get_tool("Search_ICD_Codes") is None

    def test_get_tool_calculate_bmi_has_correct_name_attribute(self, registry):
        tool = registry.get_tool("calculate_bmi")
        assert tool is not None
        assert tool.name == "calculate_bmi"

    def test_get_tool_search_icd_codes_has_icd_in_description(self, registry):
        tool = registry.get_tool("search_icd_codes")
        assert tool is not None
        assert "ICD" in tool.description or "icd" in tool.description.lower()

    def test_get_tool_after_register_returns_new_tool(self, registry):
        new_tool = make_tool("brand_new_tool", "Brand new")
        registry.register_tool(new_tool)
        result = registry.get_tool("brand_new_tool")
        assert result is not None
        assert result.name == "brand_new_tool"

    def test_get_tool_after_remove_returns_none(self, registry):
        registry.remove_tool("calculate_bmi")
        assert registry.get_tool("calculate_bmi") is None


# ===========================================================================
# TestListTools  (5 tests)
# ===========================================================================

class TestListTools:
    """ToolRegistry.list_tools behaviour."""

    def test_list_tools_has_ten_entries_initially(self, registry):
        assert len(registry.list_tools()) == 10

    def test_list_tools_returns_dict(self, registry):
        assert isinstance(registry.list_tools(), dict)

    def test_list_tools_is_a_copy_mutating_does_not_affect_registry(self, registry):
        listing = registry.list_tools()
        listing["phantom"] = make_tool("phantom")
        assert "phantom" not in registry._tools

    def test_list_tools_includes_all_registered_tools_after_register_tool(self, registry):
        extra = make_tool("extra_tool")
        registry.register_tool(extra)
        listing = registry.list_tools()
        assert "extra_tool" in listing

    def test_list_tools_has_one_fewer_after_remove_tool(self, registry):
        before = len(registry.list_tools())
        registry.remove_tool("extract_vitals")
        after = len(registry.list_tools())
        assert after == before - 1


# ===========================================================================
# TestRegisterTool  (8 tests)
# ===========================================================================

class TestRegisterTool:
    """ToolRegistry.register_tool behaviour."""

    def test_register_tool_adds_new_tool_size_increases_by_one(self, registry):
        before = len(registry._tools)
        registry.register_tool(make_tool("new_tool"))
        assert len(registry._tools) == before + 1

    def test_register_tool_returns_none(self, registry):
        result = registry.register_tool(make_tool("silent_tool"))
        assert result is None

    def test_register_tool_overwrites_existing_tool_with_same_name(self, registry):
        replacement = Tool(
            name="calculate_bmi",
            description="Overwritten description",
            parameters=[],
        )
        registry.register_tool(replacement)
        tool = registry.get_tool("calculate_bmi")
        assert tool.description == "Overwritten description"

    def test_registered_tool_is_retrievable_by_get_tool(self, registry):
        t = make_tool("retrievable_tool", "A tool to retrieve")
        registry.register_tool(t)
        assert registry.get_tool("retrievable_tool") is t

    def test_register_tool_with_custom_parameters(self, registry):
        params = [
            make_param("dose", "string"),
            make_param("route", "string"),
        ]
        t = make_tool("custom_params_tool", "Tool with params", params=params)
        registry.register_tool(t)
        result = registry.get_tool("custom_params_tool")
        assert result is not None
        param_names = [p.name for p in result.parameters]
        assert "dose" in param_names
        assert "route" in param_names

    def test_multiple_register_tool_calls_work_correctly(self, registry):
        for i in range(5):
            registry.register_tool(make_tool(f"bulk_tool_{i}"))
        for i in range(5):
            assert registry.get_tool(f"bulk_tool_{i}") is not None

    def test_register_tool_with_minimal_tool(self, registry):
        minimal = Tool(name="minimal", description="min")
        registry.register_tool(minimal)
        assert registry.get_tool("minimal") is not None

    def test_overwrite_does_not_duplicate_entry(self, registry):
        original_size = len(registry._tools)
        dup = Tool(name="search_icd_codes", description="duplicate", parameters=[])
        registry.register_tool(dup)
        assert len(registry._tools) == original_size


# ===========================================================================
# TestRemoveTool  (8 tests)
# ===========================================================================

class TestRemoveTool:
    """ToolRegistry.remove_tool behaviour."""

    def test_remove_existing_tool_returns_true(self, registry):
        assert registry.remove_tool("calculate_bmi") is True

    def test_remove_missing_tool_returns_false(self, registry):
        assert registry.remove_tool("does_not_exist") is False

    def test_remove_tool_reduces_size_by_one(self, registry):
        before = len(registry._tools)
        registry.remove_tool("extract_vitals")
        assert len(registry._tools) == before - 1

    def test_removed_tool_is_no_longer_retrievable(self, registry):
        registry.remove_tool("format_referral")
        assert registry.get_tool("format_referral") is None

    def test_remove_tool_on_empty_registry_returns_false(self):
        empty_reg = ToolRegistry()
        for name in ALL_DEFAULT_TOOL_NAMES:
            empty_reg.remove_tool(name)
        assert len(empty_reg._tools) == 0
        assert empty_reg.remove_tool("anything") is False

    def test_remove_tool_twice_returns_false_on_second_call(self, registry):
        first = registry.remove_tool("search_medications")
        second = registry.remove_tool("search_medications")
        assert first is True
        assert second is False

    def test_remove_calculate_bmi_then_get_returns_none(self, registry):
        registry.remove_tool("calculate_bmi")
        assert registry.get_tool("calculate_bmi") is None

    def test_remove_all_default_tools_one_by_one(self, registry):
        for name in ALL_DEFAULT_TOOL_NAMES:
            result = registry.remove_tool(name)
            assert result is True, f"Expected True when removing '{name}'"
        assert len(registry._tools) == 0


# ===========================================================================
# TestGetToolsForAgent  (12 tests)
# ===========================================================================

class TestGetToolsForAgent:
    """ToolRegistry.get_tools_for_agent behaviour."""

    def test_medication_agent_returns_six_tools(self, registry):
        assert len(registry.get_tools_for_agent("medication")) == 6

    def test_diagnostic_agent_returns_three_tools(self, registry):
        assert len(registry.get_tools_for_agent("diagnostic")) == 3

    def test_referral_agent_returns_one_tool(self, registry):
        assert len(registry.get_tools_for_agent("referral")) == 1

    def test_unknown_agent_type_returns_empty_dict(self, registry):
        assert registry.get_tools_for_agent("unknown_type") == {}

    def test_empty_string_agent_type_returns_empty_dict(self, registry):
        assert registry.get_tools_for_agent("") == {}

    def test_case_insensitive_medication_uppercase(self, registry):
        tools = registry.get_tools_for_agent("MEDICATION")
        assert len(tools) == 6

    def test_case_insensitive_diagnostic_mixed_case(self, registry):
        tools = registry.get_tools_for_agent("Diagnostic")
        assert len(tools) == 3

    def test_case_insensitive_referral_mixed_case(self, registry):
        tools = registry.get_tools_for_agent("Referral")
        assert len(tools) == 1

    def test_medication_tools_include_lookup_drug_interactions(self, registry):
        tools = registry.get_tools_for_agent("medication")
        assert "lookup_drug_interactions" in tools

    def test_diagnostic_tools_include_expected_names(self, registry):
        tools = registry.get_tools_for_agent("diagnostic")
        assert "search_icd_codes" in tools
        assert "extract_vitals" in tools
        assert "calculate_bmi" in tools

    def test_after_removing_a_medication_tool_get_tools_for_agent_returns_subset(self, registry):
        registry.remove_tool("lookup_drug_interactions")
        tools = registry.get_tools_for_agent("medication")
        assert "lookup_drug_interactions" not in tools
        assert len(tools) == 5

    def test_result_is_a_dict_with_tool_values(self, registry):
        tools = registry.get_tools_for_agent("diagnostic")
        assert isinstance(tools, dict)
        for key, value in tools.items():
            assert isinstance(key, str)
            assert isinstance(value, Tool)


# ===========================================================================
# TestDefaultToolStructure  (8 tests)
# ===========================================================================

class TestDefaultToolStructure:
    """Checks parameter-level details of the 10 default tools."""

    def test_search_icd_codes_has_at_least_one_param_named_query(self, registry):
        param = _get_param(registry, "search_icd_codes", "query")
        assert param is not None, "Expected parameter 'query' in 'search_icd_codes'"

    def test_calculate_bmi_has_weight_kg_and_height_cm_params(self, registry):
        weight_param = _get_param(registry, "calculate_bmi", "weight_kg")
        height_param = _get_param(registry, "calculate_bmi", "height_cm")
        assert weight_param is not None, "Expected 'weight_kg' in 'calculate_bmi'"
        assert height_param is not None, "Expected 'height_cm' in 'calculate_bmi'"

    def test_lookup_drug_interactions_medications_param_is_array_type(self, registry):
        param = _get_param(registry, "lookup_drug_interactions", "medications")
        assert param is not None
        assert param.type == "array"

    def test_calculate_dosage_renal_function_default_is_normal(self, registry):
        param = _get_param(registry, "calculate_dosage", "renal_function")
        assert param is not None
        assert param.default == "normal"

    def test_format_prescription_refills_param_required_is_false(self, registry):
        param = _get_param(registry, "format_prescription", "refills")
        assert param is not None
        assert param.required is False

    def test_check_contraindications_patient_allergies_default_is_empty_list(self, registry):
        param = _get_param(registry, "check_contraindications", "patient_allergies")
        assert param is not None
        assert param.default == []

    def test_format_referral_urgency_default_is_routine(self, registry):
        param = _get_param(registry, "format_referral", "urgency")
        assert param is not None
        assert param.default == "routine"

    def test_all_ten_default_tools_have_non_empty_descriptions(self, registry):
        for name in ALL_DEFAULT_TOOL_NAMES:
            tool = registry.get_tool(name)
            assert tool is not None, f"Default tool '{name}' missing"
            assert tool.description.strip(), f"Tool '{name}' has an empty description"


# ===========================================================================
# Supplementary parametrized tests (preserves coverage from previous version)
# ===========================================================================

class TestDefaultToolParameterCounts:
    """Exact parameter counts for each default tool."""

    @pytest.mark.parametrize("tool_name,expected_count", [
        ("search_icd_codes", 2),
        ("lookup_drug_interactions", 1),
        ("search_medications", 3),
        ("calculate_dosage", 5),
        ("check_contraindications", 3),
        ("format_prescription", 8),
        ("check_duplicate_therapy", 2),
        ("format_referral", 3),
        ("extract_vitals", 1),
        ("calculate_bmi", 2),
    ])
    def test_parameter_count(self, registry, tool_name, expected_count):
        tool = registry.get_tool(tool_name)
        assert tool is not None
        assert len(tool.parameters) == expected_count, (
            f"'{tool_name}': expected {expected_count} params, "
            f"got {len(tool.parameters)}"
        )

    def test_search_icd_codes_query_param_required(self, registry):
        param = _get_param(registry, "search_icd_codes", "query")
        assert param.required is True

    def test_search_icd_codes_limit_param_optional_with_default_10(self, registry):
        param = _get_param(registry, "search_icd_codes", "limit")
        assert param.required is False
        assert param.default == 10

    def test_calculate_bmi_params_are_number_type(self, registry):
        tool = registry.get_tool("calculate_bmi")
        for param in tool.parameters:
            assert param.type == "number"

    def test_check_contraindications_has_array_params(self, registry):
        tool = registry.get_tool("check_contraindications")
        array_params = [p for p in tool.parameters if p.type == "array"]
        assert len(array_params) >= 1


class TestCaseSensitivity:
    """Verify get_tools_for_agent is case-insensitive; get_tool is case-sensitive."""

    def test_medication_uppercase_equals_lowercase(self, registry):
        lower = registry.get_tools_for_agent("medication")
        upper = registry.get_tools_for_agent("MEDICATION")
        assert set(lower.keys()) == set(upper.keys())

    def test_diagnostic_uppercase_equals_lowercase(self, registry):
        lower = registry.get_tools_for_agent("diagnostic")
        upper = registry.get_tools_for_agent("DIAGNOSTIC")
        assert set(lower.keys()) == set(upper.keys())

    def test_referral_uppercase_equals_lowercase(self, registry):
        lower = registry.get_tools_for_agent("referral")
        upper = registry.get_tools_for_agent("REFERRAL")
        assert set(lower.keys()) == set(upper.keys())

    def test_get_tool_case_sensitive_uppercase_returns_none(self, registry):
        assert registry.get_tool("SEARCH_ICD_CODES") is None
        assert registry.get_tool("Search_ICD_Codes") is None


class TestModuleLevelSingleton:
    """The module-level tool_registry singleton is a fully initialised ToolRegistry."""

    def test_is_tool_registry_instance(self):
        assert isinstance(tool_registry, ToolRegistry)

    def test_has_at_least_ten_default_tools(self):
        assert len(tool_registry.list_tools()) >= 10

    def test_has_search_icd_codes(self):
        assert tool_registry.get_tool("search_icd_codes") is not None

    def test_has_calculate_bmi(self):
        assert tool_registry.get_tool("calculate_bmi") is not None

    def test_medication_tools_count(self):
        tools = tool_registry.get_tools_for_agent("medication")
        assert len(tools) == 6

    def test_list_tools_returns_dict(self):
        assert isinstance(tool_registry.list_tools(), dict)

    def test_register_and_cleanup_does_not_corrupt_singleton(self):
        initial_count = len(tool_registry.list_tools())
        tmp = make_tool("_tmp_singleton_test_tool")
        tool_registry.register_tool(tmp)
        assert tool_registry.get_tool("_tmp_singleton_test_tool") is not None
        tool_registry.remove_tool("_tmp_singleton_test_tool")
        assert len(tool_registry.list_tools()) == initial_count

    def test_overwrite_logs_warning(self, caplog):
        reg = ToolRegistry()
        replacement = Tool(
            name="search_icd_codes", description="replacement", parameters=[]
        )
        with caplog.at_level(logging.WARNING):
            reg.register_tool(replacement)
        assert any("search_icd_codes" in record.message for record in caplog.records)
