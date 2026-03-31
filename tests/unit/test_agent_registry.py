"""
Tests for ToolRegistry in src/ai/agents/registry.py

Covers default tool initialization, register_tool (new/overwrite),
get_tool (found/not found), list_tools (copy semantics), remove_tool
(found/not found), get_tools_for_agent (medication/diagnostic/referral/unknown).
No network, no Tkinter, no file I/O.
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

from ai.agents.registry import ToolRegistry
from ai.agents.models import Tool, ToolParameter


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def registry() -> ToolRegistry:
    return ToolRegistry()


def _make_tool(name: str, required_param: bool = False) -> Tool:
    params = []
    if required_param:
        params.append(ToolParameter(name="query", type="string",
                                    description="test param", required=True))
    return Tool(name=name, description=f"Test tool: {name}", parameters=params)


# ===========================================================================
# Default initialization
# ===========================================================================

class TestDefaultInitialization:
    def test_registry_has_tools_after_init(self, registry):
        assert len(registry._tools) > 0

    def test_search_icd_codes_present(self, registry):
        assert "search_icd_codes" in registry._tools

    def test_lookup_drug_interactions_present(self, registry):
        assert "lookup_drug_interactions" in registry._tools

    def test_search_medications_present(self, registry):
        assert "search_medications" in registry._tools

    def test_calculate_dosage_present(self, registry):
        assert "calculate_dosage" in registry._tools

    def test_check_contraindications_present(self, registry):
        assert "check_contraindications" in registry._tools

    def test_format_prescription_present(self, registry):
        assert "format_prescription" in registry._tools

    def test_check_duplicate_therapy_present(self, registry):
        assert "check_duplicate_therapy" in registry._tools

    def test_format_referral_present(self, registry):
        assert "format_referral" in registry._tools

    def test_extract_vitals_present(self, registry):
        assert "extract_vitals" in registry._tools

    def test_calculate_bmi_present(self, registry):
        assert "calculate_bmi" in registry._tools

    def test_all_tools_are_tool_instances(self, registry):
        for name, tool in registry._tools.items():
            assert isinstance(tool, Tool), f"'{name}' is not a Tool instance"

    def test_all_tool_names_are_strings(self, registry):
        for name in registry._tools:
            assert isinstance(name, str)


# ===========================================================================
# register_tool
# ===========================================================================

class TestRegisterTool:
    def test_register_new_tool_adds_it(self, registry):
        tool = _make_tool("new_tool")
        registry.register_tool(tool)
        assert "new_tool" in registry._tools

    def test_registered_tool_is_retrievable(self, registry):
        tool = _make_tool("my_tool")
        registry.register_tool(tool)
        assert registry._tools["my_tool"] is tool

    def test_register_overwrites_existing(self, registry):
        original = _make_tool("search_icd_codes")
        new = _make_tool("search_icd_codes")
        registry.register_tool(new)
        assert registry._tools["search_icd_codes"] is new
        assert registry._tools["search_icd_codes"] is not original

    def test_register_multiple_tools(self, registry):
        count_before = len(registry._tools)
        registry.register_tool(_make_tool("tool_a"))
        registry.register_tool(_make_tool("tool_b"))
        assert len(registry._tools) == count_before + 2


# ===========================================================================
# get_tool
# ===========================================================================

class TestGetTool:
    def test_get_existing_tool_returns_tool(self, registry):
        result = registry.get_tool("search_icd_codes")
        assert isinstance(result, Tool)

    def test_get_existing_tool_name_matches(self, registry):
        result = registry.get_tool("calculate_bmi")
        assert result.name == "calculate_bmi"

    def test_get_nonexistent_returns_none(self, registry):
        assert registry.get_tool("totally_fake_tool") is None

    def test_get_empty_string_returns_none(self, registry):
        assert registry.get_tool("") is None

    def test_get_after_register(self, registry):
        tool = _make_tool("fresh_tool")
        registry.register_tool(tool)
        assert registry.get_tool("fresh_tool") is tool


# ===========================================================================
# list_tools
# ===========================================================================

class TestListTools:
    def test_returns_dict(self, registry):
        assert isinstance(registry.list_tools(), dict)

    def test_contains_all_default_tools(self, registry):
        listed = registry.list_tools()
        assert "search_icd_codes" in listed
        assert "calculate_bmi" in listed

    def test_returns_copy_not_original(self, registry):
        listed = registry.list_tools()
        listed["injected"] = _make_tool("injected")
        assert "injected" not in registry._tools

    def test_size_matches_internal(self, registry):
        assert len(registry.list_tools()) == len(registry._tools)


# ===========================================================================
# remove_tool
# ===========================================================================

class TestRemoveTool:
    def test_remove_existing_returns_true(self, registry):
        assert registry.remove_tool("calculate_bmi") is True

    def test_remove_existing_deletes_it(self, registry):
        registry.remove_tool("extract_vitals")
        assert "extract_vitals" not in registry._tools

    def test_remove_nonexistent_returns_false(self, registry):
        assert registry.remove_tool("does_not_exist") is False

    def test_remove_twice_second_returns_false(self, registry):
        registry.remove_tool("calculate_bmi")
        assert registry.remove_tool("calculate_bmi") is False

    def test_remove_reduces_count(self, registry):
        count_before = len(registry._tools)
        registry.remove_tool("format_referral")
        assert len(registry._tools) == count_before - 1


# ===========================================================================
# get_tools_for_agent
# ===========================================================================

class TestGetToolsForAgent:
    def test_medication_agent_returns_dict(self, registry):
        result = registry.get_tools_for_agent("medication")
        assert isinstance(result, dict)

    def test_medication_agent_has_drug_interactions(self, registry):
        result = registry.get_tools_for_agent("medication")
        assert "lookup_drug_interactions" in result

    def test_medication_agent_has_search_medications(self, registry):
        result = registry.get_tools_for_agent("medication")
        assert "search_medications" in result

    def test_medication_agent_has_calculate_dosage(self, registry):
        result = registry.get_tools_for_agent("medication")
        assert "calculate_dosage" in result

    def test_medication_agent_has_check_contraindications(self, registry):
        result = registry.get_tools_for_agent("medication")
        assert "check_contraindications" in result

    def test_medication_agent_has_format_prescription(self, registry):
        result = registry.get_tools_for_agent("medication")
        assert "format_prescription" in result

    def test_medication_agent_has_duplicate_therapy(self, registry):
        result = registry.get_tools_for_agent("medication")
        assert "check_duplicate_therapy" in result

    def test_diagnostic_agent_returns_dict(self, registry):
        result = registry.get_tools_for_agent("diagnostic")
        assert isinstance(result, dict)

    def test_diagnostic_agent_has_search_icd(self, registry):
        result = registry.get_tools_for_agent("diagnostic")
        assert "search_icd_codes" in result

    def test_diagnostic_agent_has_extract_vitals(self, registry):
        result = registry.get_tools_for_agent("diagnostic")
        assert "extract_vitals" in result

    def test_diagnostic_agent_has_calculate_bmi(self, registry):
        result = registry.get_tools_for_agent("diagnostic")
        assert "calculate_bmi" in result

    def test_referral_agent_returns_dict(self, registry):
        result = registry.get_tools_for_agent("referral")
        assert isinstance(result, dict)

    def test_referral_agent_has_format_referral(self, registry):
        result = registry.get_tools_for_agent("referral")
        assert "format_referral" in result

    def test_unknown_agent_returns_empty_dict(self, registry):
        result = registry.get_tools_for_agent("unknown_type")
        assert result == {}

    def test_case_insensitive_agent_type(self, registry):
        upper = registry.get_tools_for_agent("MEDICATION")
        assert isinstance(upper, dict)

    def test_returned_tools_are_tool_instances(self, registry):
        result = registry.get_tools_for_agent("diagnostic")
        for name, tool in result.items():
            assert isinstance(tool, Tool)

    def test_medication_does_not_include_referral_tools(self, registry):
        result = registry.get_tools_for_agent("medication")
        assert "format_referral" not in result

    def test_diagnostic_does_not_include_prescription_tools(self, registry):
        result = registry.get_tools_for_agent("diagnostic")
        assert "format_prescription" not in result
