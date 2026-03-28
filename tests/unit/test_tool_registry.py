"""Tests for ai.agents.registry — ToolRegistry for agent tools."""

import pytest

from ai.agents.registry import ToolRegistry, tool_registry
from ai.agents.models import Tool, ToolParameter


def make_tool(name: str, description: str = "A test tool") -> Tool:
    """Helper to create a simple Tool."""
    return Tool(
        name=name,
        description=description,
        parameters=[
            ToolParameter(name="query", type="string", description="Query", required=True)
        ]
    )


class TestToolRegistryInit:
    def test_creates_registry(self):
        registry = ToolRegistry()
        assert registry is not None

    def test_default_tools_populated(self):
        registry = ToolRegistry()
        tools = registry.list_tools()
        assert len(tools) > 0

    def test_default_tools_include_expected_names(self):
        registry = ToolRegistry()
        tools = registry.list_tools()
        expected = [
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
        for name in expected:
            assert name in tools, f"Expected default tool '{name}' not found"

    def test_module_level_instance_exists(self):
        assert tool_registry is not None
        assert isinstance(tool_registry, ToolRegistry)


class TestRegisterTool:
    def test_register_new_tool(self):
        registry = ToolRegistry()
        tool = make_tool("my_custom_tool")
        registry.register_tool(tool)
        assert registry.get_tool("my_custom_tool") is not None

    def test_register_overwrites_existing(self):
        registry = ToolRegistry()
        tool1 = Tool(name="search_icd_codes", description="Original description", parameters=[])
        tool2 = Tool(name="search_icd_codes", description="New description", parameters=[])
        registry.register_tool(tool1)
        registry.register_tool(tool2)
        assert registry.get_tool("search_icd_codes").description == "New description"

    def test_register_returns_none(self):
        registry = ToolRegistry()
        tool = make_tool("another_tool")
        result = registry.register_tool(tool)
        assert result is None  # register_tool doesn't return a value


class TestGetTool:
    def test_get_existing_tool(self):
        registry = ToolRegistry()
        tool = registry.get_tool("search_icd_codes")
        assert tool is not None
        assert tool.name == "search_icd_codes"

    def test_get_nonexistent_tool_returns_none(self):
        registry = ToolRegistry()
        assert registry.get_tool("nonexistent_tool") is None

    def test_get_returns_tool_with_correct_type(self):
        registry = ToolRegistry()
        tool = registry.get_tool("calculate_bmi")
        assert isinstance(tool, Tool)

    def test_get_tool_has_parameters(self):
        registry = ToolRegistry()
        tool = registry.get_tool("calculate_bmi")
        assert len(tool.parameters) > 0


class TestListTools:
    def test_returns_dict(self):
        registry = ToolRegistry()
        tools = registry.list_tools()
        assert isinstance(tools, dict)

    def test_returns_copy(self):
        registry = ToolRegistry()
        tools1 = registry.list_tools()
        tools1["injected"] = make_tool("injected")
        tools2 = registry.list_tools()
        assert "injected" not in tools2

    def test_includes_registered_tool(self):
        registry = ToolRegistry()
        tool = make_tool("new_special_tool")
        registry.register_tool(tool)
        assert "new_special_tool" in registry.list_tools()


class TestRemoveTool:
    def test_remove_existing_tool_returns_true(self):
        registry = ToolRegistry()
        result = registry.remove_tool("calculate_bmi")
        assert result is True

    def test_remove_existing_tool_removes_it(self):
        registry = ToolRegistry()
        registry.remove_tool("calculate_bmi")
        assert registry.get_tool("calculate_bmi") is None

    def test_remove_nonexistent_tool_returns_false(self):
        registry = ToolRegistry()
        result = registry.remove_tool("nonexistent_tool")
        assert result is False

    def test_remove_then_register_again(self):
        registry = ToolRegistry()
        registry.remove_tool("calculate_bmi")
        tool = make_tool("calculate_bmi")
        registry.register_tool(tool)
        assert registry.get_tool("calculate_bmi") is not None


class TestGetToolsForAgent:
    def test_medication_agent_gets_medication_tools(self):
        registry = ToolRegistry()
        tools = registry.get_tools_for_agent("medication")
        assert "lookup_drug_interactions" in tools
        assert "search_medications" in tools
        assert "calculate_dosage" in tools
        assert "check_contraindications" in tools
        assert "format_prescription" in tools
        assert "check_duplicate_therapy" in tools

    def test_diagnostic_agent_gets_diagnostic_tools(self):
        registry = ToolRegistry()
        tools = registry.get_tools_for_agent("diagnostic")
        assert "search_icd_codes" in tools
        assert "extract_vitals" in tools
        assert "calculate_bmi" in tools

    def test_referral_agent_gets_referral_tools(self):
        registry = ToolRegistry()
        tools = registry.get_tools_for_agent("referral")
        assert "format_referral" in tools

    def test_unknown_agent_returns_empty_dict(self):
        registry = ToolRegistry()
        tools = registry.get_tools_for_agent("unknown_agent")
        assert tools == {}

    def test_case_insensitive_agent_type(self):
        registry = ToolRegistry()
        tools_lower = registry.get_tools_for_agent("medication")
        tools_upper = registry.get_tools_for_agent("MEDICATION")
        assert set(tools_lower.keys()) == set(tools_upper.keys())

    def test_returns_dict(self):
        registry = ToolRegistry()
        tools = registry.get_tools_for_agent("medication")
        assert isinstance(tools, dict)

    def test_medication_tools_not_in_diagnostic(self):
        registry = ToolRegistry()
        diagnostic_tools = registry.get_tools_for_agent("diagnostic")
        # Medication-only tools shouldn't appear in diagnostic
        assert "format_prescription" not in diagnostic_tools
        assert "check_duplicate_therapy" not in diagnostic_tools

    def test_tools_are_tool_instances(self):
        registry = ToolRegistry()
        tools = registry.get_tools_for_agent("diagnostic")
        for name, tool in tools.items():
            assert isinstance(tool, Tool)
            assert tool.name == name


class TestDefaultToolStructure:
    def test_search_icd_codes_has_required_query_param(self):
        registry = ToolRegistry()
        tool = registry.get_tool("search_icd_codes")
        param_names = [p.name for p in tool.parameters]
        assert "query" in param_names
        query_param = next(p for p in tool.parameters if p.name == "query")
        assert query_param.required is True

    def test_search_icd_codes_has_optional_limit_param(self):
        registry = ToolRegistry()
        tool = registry.get_tool("search_icd_codes")
        param_names = [p.name for p in tool.parameters]
        assert "limit" in param_names
        limit_param = next(p for p in tool.parameters if p.name == "limit")
        assert limit_param.required is False
        assert limit_param.default == 10

    def test_calculate_bmi_has_weight_and_height(self):
        registry = ToolRegistry()
        tool = registry.get_tool("calculate_bmi")
        param_names = [p.name for p in tool.parameters]
        assert "weight_kg" in param_names
        assert "height_cm" in param_names

    def test_check_contraindications_has_array_params(self):
        registry = ToolRegistry()
        tool = registry.get_tool("check_contraindications")
        array_params = [p for p in tool.parameters if p.type == "array"]
        assert len(array_params) >= 1
