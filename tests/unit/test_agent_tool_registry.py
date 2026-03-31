"""
Tests for src/ai/agents/registry.py

Covers:
- ToolRegistry initialization (default tools populated)
- register_tool (new, overwrite existing)
- get_tool (existing, missing)
- list_tools (returns copy, count)
- remove_tool (existing, non-existing)
- get_tools_for_agent (medication, diagnostic, referral, unknown)
- tool_registry global singleton
No network, no Tkinter, no I/O.
"""

import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.agents.registry import ToolRegistry, tool_registry
from ai.agents.models import Tool, ToolParameter


def _make_tool(name: str = "test_tool") -> Tool:
    """Create a minimal Tool for testing."""
    return Tool(
        name=name,
        description=f"A test tool called {name}",
        parameters=[
            ToolParameter(name="query", type="string", description="Input", required=True)
        ]
    )


# ===========================================================================
# ToolRegistry initialization
# ===========================================================================

class TestToolRegistryInit:
    def test_creates_successfully(self):
        registry = ToolRegistry()
        assert registry is not None

    def test_has_default_tools(self):
        registry = ToolRegistry()
        tools = registry.list_tools()
        assert len(tools) > 0

    def test_search_icd_codes_registered(self):
        registry = ToolRegistry()
        assert registry.get_tool("search_icd_codes") is not None

    def test_lookup_drug_interactions_registered(self):
        registry = ToolRegistry()
        assert registry.get_tool("lookup_drug_interactions") is not None

    def test_search_medications_registered(self):
        registry = ToolRegistry()
        assert registry.get_tool("search_medications") is not None

    def test_calculate_dosage_registered(self):
        registry = ToolRegistry()
        assert registry.get_tool("calculate_dosage") is not None

    def test_check_contraindications_registered(self):
        registry = ToolRegistry()
        assert registry.get_tool("check_contraindications") is not None

    def test_format_prescription_registered(self):
        registry = ToolRegistry()
        assert registry.get_tool("format_prescription") is not None

    def test_check_duplicate_therapy_registered(self):
        registry = ToolRegistry()
        assert registry.get_tool("check_duplicate_therapy") is not None

    def test_format_referral_registered(self):
        registry = ToolRegistry()
        assert registry.get_tool("format_referral") is not None

    def test_extract_vitals_registered(self):
        registry = ToolRegistry()
        assert registry.get_tool("extract_vitals") is not None

    def test_calculate_bmi_registered(self):
        registry = ToolRegistry()
        assert registry.get_tool("calculate_bmi") is not None


# ===========================================================================
# register_tool
# ===========================================================================

class TestRegisterTool:
    def test_register_new_tool(self):
        registry = ToolRegistry()
        tool = _make_tool("brand_new_tool")
        registry.register_tool(tool)
        assert registry.get_tool("brand_new_tool") is not None

    def test_registered_tool_is_same_object(self):
        registry = ToolRegistry()
        tool = _make_tool("my_special_tool")
        registry.register_tool(tool)
        assert registry.get_tool("my_special_tool") is tool

    def test_overwrite_existing_tool(self):
        registry = ToolRegistry()
        tool_v1 = Tool(name="dup", description="v1", parameters=[])
        tool_v2 = Tool(name="dup", description="v2", parameters=[])
        registry.register_tool(tool_v1)
        registry.register_tool(tool_v2)
        assert registry.get_tool("dup").description == "v2"

    def test_register_increases_count(self):
        registry = ToolRegistry()
        before = len(registry.list_tools())
        registry.register_tool(_make_tool("new_unique_tool_xyz"))
        after = len(registry.list_tools())
        assert after == before + 1


# ===========================================================================
# get_tool
# ===========================================================================

class TestGetTool:
    def test_existing_tool_returns_tool(self):
        registry = ToolRegistry()
        result = registry.get_tool("search_icd_codes")
        assert result is not None

    def test_existing_tool_is_tool_instance(self):
        registry = ToolRegistry()
        result = registry.get_tool("calculate_bmi")
        assert isinstance(result, Tool)

    def test_missing_tool_returns_none(self):
        registry = ToolRegistry()
        result = registry.get_tool("completely_nonexistent_tool_xyz")
        assert result is None

    def test_tool_name_matches(self):
        registry = ToolRegistry()
        tool = registry.get_tool("extract_vitals")
        assert tool.name == "extract_vitals"

    def test_tool_has_description(self):
        registry = ToolRegistry()
        tool = registry.get_tool("search_medications")
        assert isinstance(tool.description, str)
        assert len(tool.description) > 0

    def test_tool_has_parameters(self):
        registry = ToolRegistry()
        tool = registry.get_tool("search_icd_codes")
        assert len(tool.parameters) > 0


# ===========================================================================
# list_tools
# ===========================================================================

class TestListTools:
    def test_returns_dict(self):
        registry = ToolRegistry()
        result = registry.list_tools()
        assert isinstance(result, dict)

    def test_non_empty(self):
        registry = ToolRegistry()
        assert len(registry.list_tools()) > 0

    def test_returns_copy(self):
        registry = ToolRegistry()
        original = registry.list_tools()
        original["mutated_key"] = "mutated_value"
        # Internal state should be unchanged
        fresh = registry.list_tools()
        assert "mutated_key" not in fresh

    def test_all_values_are_tools(self):
        registry = ToolRegistry()
        for name, tool in registry.list_tools().items():
            assert isinstance(tool, Tool), f"{name} should be a Tool"

    def test_keys_match_tool_names(self):
        registry = ToolRegistry()
        for name, tool in registry.list_tools().items():
            assert tool.name == name


# ===========================================================================
# remove_tool
# ===========================================================================

class TestRemoveTool:
    def test_remove_existing_returns_true(self):
        registry = ToolRegistry()
        registry.register_tool(_make_tool("to_remove"))
        result = registry.remove_tool("to_remove")
        assert result is True

    def test_removed_tool_not_found(self):
        registry = ToolRegistry()
        registry.register_tool(_make_tool("bye_tool"))
        registry.remove_tool("bye_tool")
        assert registry.get_tool("bye_tool") is None

    def test_remove_decreases_count(self):
        registry = ToolRegistry()
        registry.register_tool(_make_tool("count_tool"))
        before = len(registry.list_tools())
        registry.remove_tool("count_tool")
        after = len(registry.list_tools())
        assert after == before - 1

    def test_remove_nonexistent_returns_false(self):
        registry = ToolRegistry()
        result = registry.remove_tool("does_not_exist_xyz")
        assert result is False

    def test_remove_nonexistent_no_error(self):
        registry = ToolRegistry()
        try:
            registry.remove_tool("no_such_tool")
        except Exception as exc:
            pytest.fail(f"remove_tool raised: {exc}")


# ===========================================================================
# get_tools_for_agent
# ===========================================================================

class TestGetToolsForAgent:
    def test_medication_agent_has_tools(self):
        registry = ToolRegistry()
        tools = registry.get_tools_for_agent("medication")
        assert len(tools) > 0

    def test_diagnostic_agent_has_tools(self):
        registry = ToolRegistry()
        tools = registry.get_tools_for_agent("diagnostic")
        assert len(tools) > 0

    def test_referral_agent_has_tools(self):
        registry = ToolRegistry()
        tools = registry.get_tools_for_agent("referral")
        assert len(tools) > 0

    def test_unknown_agent_returns_empty(self):
        registry = ToolRegistry()
        tools = registry.get_tools_for_agent("unknown_type_xyz")
        assert len(tools) == 0

    def test_returns_dict(self):
        registry = ToolRegistry()
        result = registry.get_tools_for_agent("medication")
        assert isinstance(result, dict)

    def test_medication_contains_drug_interactions(self):
        registry = ToolRegistry()
        tools = registry.get_tools_for_agent("medication")
        assert "lookup_drug_interactions" in tools

    def test_diagnostic_contains_icd_search(self):
        registry = ToolRegistry()
        tools = registry.get_tools_for_agent("diagnostic")
        assert "search_icd_codes" in tools

    def test_referral_contains_format_referral(self):
        registry = ToolRegistry()
        tools = registry.get_tools_for_agent("referral")
        assert "format_referral" in tools

    def test_case_insensitive(self):
        registry = ToolRegistry()
        tools_lower = registry.get_tools_for_agent("medication")
        tools_upper = registry.get_tools_for_agent("MEDICATION")
        assert tools_lower == tools_upper


# ===========================================================================
# Global singleton
# ===========================================================================

class TestToolRegistrySingleton:
    def test_tool_registry_is_tool_registry_instance(self):
        assert isinstance(tool_registry, ToolRegistry)

    def test_tool_registry_has_tools(self):
        assert len(tool_registry.list_tools()) > 0

    def test_tool_registry_has_search_icd_codes(self):
        assert tool_registry.get_tool("search_icd_codes") is not None
