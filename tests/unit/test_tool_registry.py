"""
Comprehensive tests for ai.agents.registry — ToolRegistry.

Covers:
- Default tool names (all 10 present after __init__)
- Default tool parameter counts and structure
- register_tool: add new, overwrite existing, warning on overwrite
- get_tool: known name, unknown name
- list_tools: returns copy, mutation isolation, contains all 10 defaults
- remove_tool: True on existing, False on missing, actually removes
- get_tools_for_agent: medication (6), diagnostic (3), referral (1), unknown (empty)
- Case sensitivity: "MEDICATION" lowercased → same result as "medication"
- Module-level singleton tool_registry exists and is populated
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
# Helpers
# ---------------------------------------------------------------------------

def _make_tool(name: str, description: str = "A test tool", num_params: int = 1) -> Tool:
    """Create a minimal Tool for testing."""
    params = [
        ToolParameter(
            name=f"param_{i}",
            type="string",
            description=f"Parameter {i}",
            required=(i == 0),
        )
        for i in range(num_params)
    ]
    return Tool(name=name, description=description, parameters=params)


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


# ===========================================================================
# 1. Initialization — default tools present
# ===========================================================================

class TestInitialization:
    def test_creates_instance(self):
        registry = ToolRegistry()
        assert registry is not None

    def test_has_internal_tools_dict(self):
        registry = ToolRegistry()
        assert hasattr(registry, "_tools")
        assert isinstance(registry._tools, dict)

    def test_exactly_10_default_tools(self):
        registry = ToolRegistry()
        assert len(registry.list_tools()) == 10

    @pytest.mark.parametrize("name", ALL_DEFAULT_TOOL_NAMES)
    def test_each_default_tool_present(self, name):
        registry = ToolRegistry()
        assert registry.get_tool(name) is not None, f"Default tool '{name}' missing"

    def test_fresh_instances_are_independent(self):
        r1 = ToolRegistry()
        r2 = ToolRegistry()
        r1.remove_tool("calculate_bmi")
        assert r2.get_tool("calculate_bmi") is not None

    def test_all_default_tool_values_are_tool_instances(self):
        registry = ToolRegistry()
        for name, tool in registry._tools.items():
            assert isinstance(tool, Tool), f"_tools['{name}'] is not a Tool"

    def test_default_tools_keys_match_tool_names(self):
        registry = ToolRegistry()
        for key, tool in registry._tools.items():
            assert key == tool.name, f"Key '{key}' does not match tool.name '{tool.name}'"


# ===========================================================================
# 2. Default tool parameter counts
# ===========================================================================

class TestDefaultToolParameterCounts:
    def test_search_icd_codes_has_2_params(self):
        registry = ToolRegistry()
        tool = registry.get_tool("search_icd_codes")
        assert len(tool.parameters) == 2

    def test_lookup_drug_interactions_has_1_param(self):
        registry = ToolRegistry()
        tool = registry.get_tool("lookup_drug_interactions")
        assert len(tool.parameters) == 1

    def test_search_medications_has_3_params(self):
        registry = ToolRegistry()
        tool = registry.get_tool("search_medications")
        assert len(tool.parameters) == 3

    def test_calculate_dosage_has_5_params(self):
        registry = ToolRegistry()
        tool = registry.get_tool("calculate_dosage")
        assert len(tool.parameters) == 5

    def test_check_contraindications_has_3_params(self):
        registry = ToolRegistry()
        tool = registry.get_tool("check_contraindications")
        assert len(tool.parameters) == 3

    def test_format_prescription_has_8_params(self):
        registry = ToolRegistry()
        tool = registry.get_tool("format_prescription")
        assert len(tool.parameters) == 8

    def test_check_duplicate_therapy_has_2_params(self):
        registry = ToolRegistry()
        tool = registry.get_tool("check_duplicate_therapy")
        assert len(tool.parameters) == 2

    def test_format_referral_has_3_params(self):
        registry = ToolRegistry()
        tool = registry.get_tool("format_referral")
        assert len(tool.parameters) == 3

    def test_extract_vitals_has_1_param(self):
        registry = ToolRegistry()
        tool = registry.get_tool("extract_vitals")
        assert len(tool.parameters) == 1

    def test_calculate_bmi_has_2_params(self):
        registry = ToolRegistry()
        tool = registry.get_tool("calculate_bmi")
        assert len(tool.parameters) == 2

    def test_search_icd_codes_query_param_required(self):
        registry = ToolRegistry()
        tool = registry.get_tool("search_icd_codes")
        query_param = next(p for p in tool.parameters if p.name == "query")
        assert query_param.required is True

    def test_search_icd_codes_limit_param_optional(self):
        registry = ToolRegistry()
        tool = registry.get_tool("search_icd_codes")
        limit_param = next(p for p in tool.parameters if p.name == "limit")
        assert limit_param.required is False

    def test_search_icd_codes_limit_default_10(self):
        registry = ToolRegistry()
        tool = registry.get_tool("search_icd_codes")
        limit_param = next(p for p in tool.parameters if p.name == "limit")
        assert limit_param.default == 10

    def test_calculate_bmi_weight_kg_required(self):
        registry = ToolRegistry()
        tool = registry.get_tool("calculate_bmi")
        weight_param = next(p for p in tool.parameters if p.name == "weight_kg")
        assert weight_param.required is True

    def test_calculate_bmi_height_cm_required(self):
        registry = ToolRegistry()
        tool = registry.get_tool("calculate_bmi")
        height_param = next(p for p in tool.parameters if p.name == "height_cm")
        assert height_param.required is True

    def test_calculate_bmi_params_are_number_type(self):
        registry = ToolRegistry()
        tool = registry.get_tool("calculate_bmi")
        for param in tool.parameters:
            assert param.type == "number", f"Expected 'number', got '{param.type}'"

    def test_lookup_drug_interactions_medications_is_array(self):
        registry = ToolRegistry()
        tool = registry.get_tool("lookup_drug_interactions")
        medications_param = next(p for p in tool.parameters if p.name == "medications")
        assert medications_param.type == "array"

    def test_check_contraindications_has_array_params(self):
        registry = ToolRegistry()
        tool = registry.get_tool("check_contraindications")
        array_params = [p for p in tool.parameters if p.type == "array"]
        assert len(array_params) >= 1

    def test_format_prescription_has_required_params(self):
        registry = ToolRegistry()
        tool = registry.get_tool("format_prescription")
        required_params = [p for p in tool.parameters if p.required]
        assert len(required_params) >= 1

    def test_format_referral_urgency_has_default(self):
        registry = ToolRegistry()
        tool = registry.get_tool("format_referral")
        urgency_param = next(p for p in tool.parameters if p.name == "urgency")
        assert urgency_param.default == "routine"


# ===========================================================================
# 3. register_tool
# ===========================================================================

class TestRegisterTool:
    def test_register_new_tool_adds_it(self):
        registry = ToolRegistry()
        tool = _make_tool("brand_new_tool")
        registry.register_tool(tool)
        assert registry.get_tool("brand_new_tool") is not None

    def test_registered_tool_is_same_object(self):
        registry = ToolRegistry()
        tool = _make_tool("identity_tool")
        registry.register_tool(tool)
        assert registry.get_tool("identity_tool") is tool

    def test_register_increases_count_by_one(self):
        registry = ToolRegistry()
        before = len(registry.list_tools())
        registry.register_tool(_make_tool("count_check_tool"))
        assert len(registry.list_tools()) == before + 1

    def test_overwrite_existing_updates_description(self):
        registry = ToolRegistry()
        old = Tool(name="overwrite_me", description="old", parameters=[])
        new = Tool(name="overwrite_me", description="new", parameters=[])
        registry.register_tool(old)
        registry.register_tool(new)
        assert registry.get_tool("overwrite_me").description == "new"

    def test_overwrite_does_not_increase_count(self):
        registry = ToolRegistry()
        tool_a = Tool(name="stable_name", description="v1", parameters=[])
        tool_b = Tool(name="stable_name", description="v2", parameters=[])
        registry.register_tool(tool_a)
        count_after_first = len(registry.list_tools())
        registry.register_tool(tool_b)
        assert len(registry.list_tools()) == count_after_first

    def test_overwrite_logs_warning(self, caplog):
        registry = ToolRegistry()
        # "search_icd_codes" already exists after __init__
        replacement = Tool(name="search_icd_codes", description="replacement", parameters=[])
        with caplog.at_level(logging.WARNING):
            registry.register_tool(replacement)
        assert any("search_icd_codes" in record.message for record in caplog.records)

    def test_register_tool_returns_none(self):
        registry = ToolRegistry()
        result = registry.register_tool(_make_tool("void_tool"))
        assert result is None

    def test_module_level_registry_can_register(self):
        # The global singleton must be usable
        initial_count = len(tool_registry.list_tools())
        tmp_tool = _make_tool("_tmp_singleton_test_tool")
        tool_registry.register_tool(tmp_tool)
        assert tool_registry.get_tool("_tmp_singleton_test_tool") is not None
        # Clean up so other tests are not affected
        tool_registry.remove_tool("_tmp_singleton_test_tool")
        assert len(tool_registry.list_tools()) == initial_count


# ===========================================================================
# 4. get_tool
# ===========================================================================

class TestGetTool:
    @pytest.mark.parametrize("name", ALL_DEFAULT_TOOL_NAMES)
    def test_get_each_default_tool_returns_tool(self, name):
        registry = ToolRegistry()
        result = registry.get_tool(name)
        assert result is not None
        assert isinstance(result, Tool)

    def test_get_unknown_name_returns_none(self):
        registry = ToolRegistry()
        assert registry.get_tool("totally_unknown_xyz") is None

    def test_get_empty_string_returns_none(self):
        registry = ToolRegistry()
        assert registry.get_tool("") is None

    def test_get_tool_name_attribute_matches(self):
        registry = ToolRegistry()
        tool = registry.get_tool("extract_vitals")
        assert tool.name == "extract_vitals"

    def test_get_tool_has_non_empty_description(self):
        registry = ToolRegistry()
        tool = registry.get_tool("search_medications")
        assert isinstance(tool.description, str)
        assert len(tool.description) > 0

    def test_get_tool_has_parameters_list(self):
        registry = ToolRegistry()
        tool = registry.get_tool("search_icd_codes")
        assert isinstance(tool.parameters, list)

    def test_get_after_register(self):
        registry = ToolRegistry()
        registry.register_tool(_make_tool("late_addition"))
        assert registry.get_tool("late_addition") is not None

    def test_get_after_remove_returns_none(self):
        registry = ToolRegistry()
        registry.remove_tool("calculate_bmi")
        assert registry.get_tool("calculate_bmi") is None


# ===========================================================================
# 5. list_tools
# ===========================================================================

class TestListTools:
    def test_returns_dict(self):
        registry = ToolRegistry()
        assert isinstance(registry.list_tools(), dict)

    def test_contains_all_10_defaults(self):
        registry = ToolRegistry()
        tools = registry.list_tools()
        for name in ALL_DEFAULT_TOOL_NAMES:
            assert name in tools

    def test_returns_copy_mutation_does_not_affect_registry(self):
        registry = ToolRegistry()
        snapshot = registry.list_tools()
        snapshot["injected_key"] = _make_tool("injected_key")
        assert "injected_key" not in registry.list_tools()

    def test_returns_copy_deletion_does_not_affect_registry(self):
        registry = ToolRegistry()
        snapshot = registry.list_tools()
        del snapshot["calculate_bmi"]
        assert "calculate_bmi" in registry.list_tools()

    def test_all_values_are_tool_instances(self):
        registry = ToolRegistry()
        for name, tool in registry.list_tools().items():
            assert isinstance(tool, Tool)

    def test_keys_equal_tool_names(self):
        registry = ToolRegistry()
        for key, tool in registry.list_tools().items():
            assert key == tool.name

    def test_count_reflects_registered_tools(self):
        registry = ToolRegistry()
        registry.register_tool(_make_tool("extra_list_tool"))
        assert len(registry.list_tools()) == 11

    def test_count_reflects_removed_tools(self):
        registry = ToolRegistry()
        registry.remove_tool("extract_vitals")
        assert len(registry.list_tools()) == 9


# ===========================================================================
# 6. remove_tool
# ===========================================================================

class TestRemoveTool:
    def test_remove_existing_returns_true(self):
        registry = ToolRegistry()
        assert registry.remove_tool("calculate_bmi") is True

    def test_remove_actually_removes(self):
        registry = ToolRegistry()
        registry.remove_tool("calculate_bmi")
        assert registry.get_tool("calculate_bmi") is None

    def test_remove_missing_returns_false(self):
        registry = ToolRegistry()
        assert registry.remove_tool("nonexistent_zzz") is False

    def test_remove_missing_does_not_raise(self):
        registry = ToolRegistry()
        try:
            registry.remove_tool("ghost_tool")
        except Exception as exc:
            pytest.fail(f"remove_tool raised unexpectedly: {exc}")

    def test_remove_decreases_count(self):
        registry = ToolRegistry()
        before = len(registry.list_tools())
        registry.remove_tool("extract_vitals")
        assert len(registry.list_tools()) == before - 1

    def test_remove_twice_second_call_returns_false(self):
        registry = ToolRegistry()
        registry.remove_tool("calculate_bmi")
        assert registry.remove_tool("calculate_bmi") is False

    def test_remove_then_re_register(self):
        registry = ToolRegistry()
        registry.remove_tool("format_referral")
        registry.register_tool(_make_tool("format_referral"))
        assert registry.get_tool("format_referral") is not None

    @pytest.mark.parametrize("name", ALL_DEFAULT_TOOL_NAMES)
    def test_remove_each_default_tool(self, name):
        registry = ToolRegistry()
        assert registry.remove_tool(name) is True
        assert registry.get_tool(name) is None


# ===========================================================================
# 7. get_tools_for_agent — "medication" → 6 tools
# ===========================================================================

class TestGetToolsForAgentMedication:
    def test_returns_dict(self):
        registry = ToolRegistry()
        assert isinstance(registry.get_tools_for_agent("medication"), dict)

    def test_medication_returns_exactly_6_tools(self):
        registry = ToolRegistry()
        tools = registry.get_tools_for_agent("medication")
        assert len(tools) == 6

    @pytest.mark.parametrize("name", MEDICATION_TOOL_NAMES)
    def test_each_medication_tool_present(self, name):
        registry = ToolRegistry()
        tools = registry.get_tools_for_agent("medication")
        assert name in tools, f"Medication tool '{name}' missing"

    def test_medication_tools_are_tool_instances(self):
        registry = ToolRegistry()
        for name, tool in registry.get_tools_for_agent("medication").items():
            assert isinstance(tool, Tool)

    def test_medication_does_not_contain_diagnostic_only_tools(self):
        registry = ToolRegistry()
        tools = registry.get_tools_for_agent("medication")
        assert "search_icd_codes" not in tools
        assert "extract_vitals" not in tools
        assert "calculate_bmi" not in tools

    def test_medication_does_not_contain_referral_only_tools(self):
        registry = ToolRegistry()
        tools = registry.get_tools_for_agent("medication")
        assert "format_referral" not in tools


# ===========================================================================
# 8. get_tools_for_agent — "diagnostic" → 3 tools
# ===========================================================================

class TestGetToolsForAgentDiagnostic:
    def test_diagnostic_returns_exactly_3_tools(self):
        registry = ToolRegistry()
        tools = registry.get_tools_for_agent("diagnostic")
        assert len(tools) == 3

    @pytest.mark.parametrize("name", DIAGNOSTIC_TOOL_NAMES)
    def test_each_diagnostic_tool_present(self, name):
        registry = ToolRegistry()
        tools = registry.get_tools_for_agent("diagnostic")
        assert name in tools, f"Diagnostic tool '{name}' missing"

    def test_diagnostic_tools_are_tool_instances(self):
        registry = ToolRegistry()
        for name, tool in registry.get_tools_for_agent("diagnostic").items():
            assert isinstance(tool, Tool)

    def test_diagnostic_does_not_contain_medication_only_tools(self):
        registry = ToolRegistry()
        tools = registry.get_tools_for_agent("diagnostic")
        assert "format_prescription" not in tools
        assert "check_duplicate_therapy" not in tools


# ===========================================================================
# 9. get_tools_for_agent — "referral" → 1 tool
# ===========================================================================

class TestGetToolsForAgentReferral:
    def test_referral_returns_exactly_1_tool(self):
        registry = ToolRegistry()
        tools = registry.get_tools_for_agent("referral")
        assert len(tools) == 1

    def test_referral_contains_format_referral(self):
        registry = ToolRegistry()
        tools = registry.get_tools_for_agent("referral")
        assert "format_referral" in tools

    def test_referral_tool_is_tool_instance(self):
        registry = ToolRegistry()
        tools = registry.get_tools_for_agent("referral")
        assert isinstance(tools["format_referral"], Tool)


# ===========================================================================
# 10. get_tools_for_agent — unknown type → empty dict
# ===========================================================================

class TestGetToolsForAgentUnknown:
    def test_unknown_type_returns_empty_dict(self):
        registry = ToolRegistry()
        assert registry.get_tools_for_agent("unknown_agent_type") == {}

    def test_empty_string_returns_empty_dict(self):
        registry = ToolRegistry()
        assert registry.get_tools_for_agent("") == {}

    def test_partial_name_returns_empty_dict(self):
        registry = ToolRegistry()
        assert registry.get_tools_for_agent("medic") == {}

    def test_random_name_returns_empty_dict(self):
        registry = ToolRegistry()
        assert registry.get_tools_for_agent("xyz_agent_99") == {}

    def test_synopsis_agent_returns_empty_dict(self):
        # "synopsis" is a valid AgentType enum value but has no tool mapping
        registry = ToolRegistry()
        assert registry.get_tools_for_agent("synopsis") == {}


# ===========================================================================
# 11. Case sensitivity
# ===========================================================================

class TestCaseSensitivity:
    def test_medication_uppercase_equals_lowercase(self):
        registry = ToolRegistry()
        lower = registry.get_tools_for_agent("medication")
        upper = registry.get_tools_for_agent("MEDICATION")
        assert set(lower.keys()) == set(upper.keys())

    def test_medication_mixed_case_equals_lowercase(self):
        registry = ToolRegistry()
        lower = registry.get_tools_for_agent("medication")
        mixed = registry.get_tools_for_agent("Medication")
        assert set(lower.keys()) == set(mixed.keys())

    def test_diagnostic_uppercase_equals_lowercase(self):
        registry = ToolRegistry()
        lower = registry.get_tools_for_agent("diagnostic")
        upper = registry.get_tools_for_agent("DIAGNOSTIC")
        assert set(lower.keys()) == set(upper.keys())

    def test_referral_uppercase_equals_lowercase(self):
        registry = ToolRegistry()
        lower = registry.get_tools_for_agent("referral")
        upper = registry.get_tools_for_agent("REFERRAL")
        assert set(lower.keys()) == set(upper.keys())

    def test_get_tool_case_sensitive(self):
        # Tool names are stored literally; uppercase key must return None
        registry = ToolRegistry()
        assert registry.get_tool("Search_ICD_Codes") is None
        assert registry.get_tool("SEARCH_ICD_CODES") is None


# ===========================================================================
# 12. Module-level singleton
# ===========================================================================

class TestModuleLevelSingleton:
    def test_tool_registry_is_tool_registry_instance(self):
        assert isinstance(tool_registry, ToolRegistry)

    def test_tool_registry_has_default_tools(self):
        assert len(tool_registry.list_tools()) >= 10

    def test_tool_registry_has_search_icd_codes(self):
        assert tool_registry.get_tool("search_icd_codes") is not None

    def test_tool_registry_has_calculate_bmi(self):
        assert tool_registry.get_tool("calculate_bmi") is not None

    def test_tool_registry_get_tools_for_medication(self):
        tools = tool_registry.get_tools_for_agent("medication")
        assert len(tools) == 6

    def test_tool_registry_list_tools_is_dict(self):
        assert isinstance(tool_registry.list_tools(), dict)
