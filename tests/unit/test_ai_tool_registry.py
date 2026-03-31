"""
Tests for src/ai/tools/tool_registry.py

Covers ToolRegistry (singleton) register/register_tool/get_tool/
get_tool_definition/list_tools/get_all_definitions/get_cache_info/
_invalidate_cache/clear/clear_category and the global tool_registry instance.

This is distinct from tests/unit/test_agent_tool_registry.py, which tests
src/ai/agents/registry.py.  This file targets the BaseTool-based registry at
src/ai/tools/tool_registry.py.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.tools.tool_registry import ToolRegistry, tool_registry as global_registry
from ai.tools.base_tool import BaseTool
from ai.agents.models import Tool, ToolParameter


# ---------------------------------------------------------------------------
# Minimal concrete BaseTool subclass used across all tests
# ---------------------------------------------------------------------------

class _FakeTool(BaseTool):
    """Minimal concrete BaseTool for testing the registry."""
    category = "test"

    def get_definition(self) -> Tool:
        return Tool(name="fake_tool", description="Test tool", parameters=[])

    def execute(self, **kwargs):
        from ai.tools.base_tool import ToolResult
        return ToolResult(success=True, output={"result": "ok"})


class _AnotherFakeTool(BaseTool):
    """Second concrete tool with a different name and category."""
    category = "other"

    def get_definition(self) -> Tool:
        return Tool(
            name="another_tool",
            description="Another test tool",
            parameters=[
                ToolParameter(
                    name="query", type="string",
                    description="A query", required=True
                )
            ],
        )

    def execute(self, **kwargs):
        from ai.tools.base_tool import ToolResult
        return ToolResult(success=True, output={"result": "another_ok"})


class _ToolWithParam(BaseTool):
    """Tool that carries a parameter, used for definition tests."""
    category = "test"

    def get_definition(self) -> Tool:
        return Tool(
            name="param_tool",
            description="Tool with params",
            parameters=[
                ToolParameter(
                    name="value", type="integer",
                    description="An integer value", required=True
                )
            ],
        )

    def execute(self, **kwargs):
        from ai.tools.base_tool import ToolResult
        return ToolResult(success=True, output=None)


# ---------------------------------------------------------------------------
# Singleton reset fixture
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_registry():
    """Reset the ToolRegistry singleton between tests."""
    ToolRegistry._instance = None
    yield
    ToolRegistry._instance = None


@pytest.fixture
def registry() -> ToolRegistry:
    """Return a fresh, empty ToolRegistry."""
    return ToolRegistry()


# ===========================================================================
# Initialisation
# ===========================================================================

class TestToolRegistryInit:
    def test_creates_successfully(self, registry):
        assert registry is not None

    def test_starts_empty_tools(self, registry):
        assert registry.list_tools() == []

    def test_initialized_flag_set(self, registry):
        assert registry._initialized is True

    def test_cache_initially_none(self, registry):
        assert registry._definitions_cache is None

    def test_cache_version_starts_at_zero(self, registry):
        # Fresh registry: no tools registered yet so version is still 0
        assert registry._cache_version == 0

    def test_second_init_does_not_reset_state(self, registry):
        registry.register(_FakeTool)
        # Calling the constructor again must return the SAME singleton
        same = ToolRegistry()
        assert same.list_tools() == ["fake_tool"]


# ===========================================================================
# register (class-based)
# ===========================================================================

class TestRegister:
    def test_register_adds_tool(self, registry):
        registry.register(_FakeTool)
        assert "fake_tool" in registry.list_tools()

    def test_get_tool_returns_instance_after_register(self, registry):
        registry.register(_FakeTool)
        instance = registry.get_tool("fake_tool")
        assert instance is not None
        assert isinstance(instance, BaseTool)

    def test_register_two_tools(self, registry):
        registry.register(_FakeTool)
        registry.register(_AnotherFakeTool)
        assert "fake_tool" in registry.list_tools()
        assert "another_tool" in registry.list_tools()

    def test_register_overwrite_logs_warning(self, registry):
        registry.register(_FakeTool)
        with patch("ai.tools.tool_registry.logger") as mock_logger:
            registry.register(_FakeTool)
            mock_logger.warning.assert_called_once()

    def test_register_overwrite_keeps_new_instance(self, registry):
        registry.register(_FakeTool)
        instance_before = registry.get_tool("fake_tool")
        registry.register(_FakeTool)
        instance_after = registry.get_tool("fake_tool")
        # Both are _FakeTool instances; the registry should hold one
        assert isinstance(instance_after, _FakeTool)

    def test_register_invalidates_cache(self, registry):
        registry.register(_FakeTool)
        # Prime the cache
        registry.get_all_definitions()
        _, cached = registry.get_cache_info()
        assert cached is True
        # Registering again must invalidate it
        registry.register(_AnotherFakeTool)
        _, cached_after = registry.get_cache_info()
        assert cached_after is False

    def test_register_increments_cache_version(self, registry):
        v0 = registry._cache_version
        registry.register(_FakeTool)
        assert registry._cache_version == v0 + 1


# ===========================================================================
# register_tool (instance-based)
# ===========================================================================

class TestRegisterTool:
    def test_register_tool_instance(self, registry):
        instance = _FakeTool()
        registry.register_tool(instance)
        assert "fake_tool" in registry.list_tools()

    def test_get_tool_returns_same_instance(self, registry):
        instance = _FakeTool()
        registry.register_tool(instance)
        assert registry.get_tool("fake_tool") is instance

    def test_register_tool_overwrite_logs_warning(self, registry):
        registry.register_tool(_FakeTool())
        with patch("ai.tools.tool_registry.logger") as mock_logger:
            registry.register_tool(_FakeTool())
            mock_logger.warning.assert_called_once()

    def test_register_tool_increments_cache_version(self, registry):
        v0 = registry._cache_version
        registry.register_tool(_FakeTool())
        assert registry._cache_version == v0 + 1

    def test_register_tool_stores_class_in_tools_dict(self, registry):
        instance = _FakeTool()
        registry.register_tool(instance)
        assert registry._tools["fake_tool"] is _FakeTool

    def test_register_tool_adds_to_list(self, registry):
        registry.register_tool(_AnotherFakeTool())
        assert "another_tool" in registry.list_tools()


# ===========================================================================
# get_tool
# ===========================================================================

class TestGetTool:
    def test_existing_tool_returns_instance(self, registry):
        registry.register(_FakeTool)
        result = registry.get_tool("fake_tool")
        assert isinstance(result, BaseTool)

    def test_missing_tool_returns_none(self, registry):
        result = registry.get_tool("no_such_tool_xyz")
        assert result is None

    def test_get_tool_after_clear_returns_none(self, registry):
        registry.register(_FakeTool)
        registry.clear()
        assert registry.get_tool("fake_tool") is None

    def test_get_tool_correct_type(self, registry):
        registry.register(_FakeTool)
        assert isinstance(registry.get_tool("fake_tool"), _FakeTool)


# ===========================================================================
# get_tool_definition
# ===========================================================================

class TestGetToolDefinition:
    def test_existing_tool_returns_tool(self, registry):
        registry.register(_FakeTool)
        defn = registry.get_tool_definition("fake_tool")
        assert isinstance(defn, Tool)

    def test_definition_name_matches(self, registry):
        registry.register(_FakeTool)
        defn = registry.get_tool_definition("fake_tool")
        assert defn.name == "fake_tool"

    def test_definition_has_description(self, registry):
        registry.register(_FakeTool)
        defn = registry.get_tool_definition("fake_tool")
        assert isinstance(defn.description, str)
        assert len(defn.description) > 0

    def test_definition_with_parameters(self, registry):
        registry.register(_ToolWithParam)
        defn = registry.get_tool_definition("param_tool")
        assert len(defn.parameters) == 1
        assert defn.parameters[0].name == "value"

    def test_missing_tool_returns_none(self, registry):
        result = registry.get_tool_definition("no_such_tool_xyz")
        assert result is None


# ===========================================================================
# list_tools
# ===========================================================================

class TestListTools:
    def test_empty_registry_returns_empty_list(self, registry):
        assert registry.list_tools() == []

    def test_returns_list(self, registry):
        assert isinstance(registry.list_tools(), list)

    def test_contains_registered_name(self, registry):
        registry.register(_FakeTool)
        assert "fake_tool" in registry.list_tools()

    def test_count_increases_on_register(self, registry):
        registry.register(_FakeTool)
        registry.register(_AnotherFakeTool)
        assert len(registry.list_tools()) == 2

    def test_count_decreases_after_clear(self, registry):
        registry.register(_FakeTool)
        registry.clear()
        assert registry.list_tools() == []

    def test_returns_independent_copy(self, registry):
        registry.register(_FakeTool)
        names = registry.list_tools()
        names.append("injected")
        # Internal state must be unchanged
        assert "injected" not in registry.list_tools()


# ===========================================================================
# get_all_definitions
# ===========================================================================

class TestGetAllDefinitions:
    def test_empty_registry_returns_empty_list(self, registry):
        result = registry.get_all_definitions()
        assert result == []

    def test_returns_list_of_tool(self, registry):
        registry.register(_FakeTool)
        defs = registry.get_all_definitions()
        assert isinstance(defs, list)
        assert all(isinstance(d, Tool) for d in defs)

    def test_count_matches_registered_tools(self, registry):
        registry.register(_FakeTool)
        registry.register(_AnotherFakeTool)
        assert len(registry.get_all_definitions()) == 2

    def test_cached_on_second_call(self, registry):
        registry.register(_FakeTool)
        first = registry.get_all_definitions()
        second = registry.get_all_definitions()
        assert first is second  # same list object — cached

    def test_cache_invalidated_after_new_register(self, registry):
        registry.register(_FakeTool)
        first = registry.get_all_definitions()
        registry.register(_AnotherFakeTool)
        second = registry.get_all_definitions()
        assert first is not second  # cache was rebuilt

    def test_definitions_contain_correct_names(self, registry):
        registry.register(_FakeTool)
        registry.register(_AnotherFakeTool)
        names = {d.name for d in registry.get_all_definitions()}
        assert names == {"fake_tool", "another_tool"}


# ===========================================================================
# get_cache_info
# ===========================================================================

class TestGetCacheInfo:
    def test_returns_tuple(self, registry):
        result = registry.get_cache_info()
        assert isinstance(result, tuple)

    def test_tuple_has_two_elements(self, registry):
        result = registry.get_cache_info()
        assert len(result) == 2

    def test_initially_not_cached(self, registry):
        _, is_cached = registry.get_cache_info()
        assert is_cached is False

    def test_cached_after_get_all_definitions(self, registry):
        registry.register(_FakeTool)
        registry.get_all_definitions()
        _, is_cached = registry.get_cache_info()
        assert is_cached is True

    def test_not_cached_after_invalidation(self, registry):
        registry.register(_FakeTool)
        registry.get_all_definitions()
        registry.register(_AnotherFakeTool)
        _, is_cached = registry.get_cache_info()
        assert is_cached is False

    def test_version_increments_on_register(self, registry):
        v0, _ = registry.get_cache_info()
        registry.register(_FakeTool)
        v1, _ = registry.get_cache_info()
        assert v1 == v0 + 1

    def test_version_increments_twice_on_two_registers(self, registry):
        v0, _ = registry.get_cache_info()
        registry.register(_FakeTool)
        registry.register(_AnotherFakeTool)
        v2, _ = registry.get_cache_info()
        assert v2 == v0 + 2

    def test_version_is_int(self, registry):
        version, _ = registry.get_cache_info()
        assert isinstance(version, int)


# ===========================================================================
# _invalidate_cache (internal)
# ===========================================================================

class TestInvalidateCache:
    def test_invalidate_clears_cache(self, registry):
        registry.register(_FakeTool)
        registry.get_all_definitions()  # prime cache
        registry._invalidate_cache()
        assert registry._definitions_cache is None

    def test_invalidate_increments_version(self, registry):
        v0 = registry._cache_version
        registry._invalidate_cache()
        assert registry._cache_version == v0 + 1


# ===========================================================================
# clear
# ===========================================================================

class TestClear:
    def test_clear_empties_list_tools(self, registry):
        registry.register(_FakeTool)
        registry.register(_AnotherFakeTool)
        registry.clear()
        assert registry.list_tools() == []

    def test_clear_empties_instances(self, registry):
        registry.register(_FakeTool)
        registry.clear()
        assert registry._instances == {}

    def test_clear_empties_tools_dict(self, registry):
        registry.register(_FakeTool)
        registry.clear()
        assert registry._tools == {}

    def test_clear_invalidates_cache(self, registry):
        registry.register(_FakeTool)
        registry.get_all_definitions()
        registry.clear()
        _, is_cached = registry.get_cache_info()
        assert is_cached is False

    def test_clear_on_empty_registry_no_error(self, registry):
        try:
            registry.clear()
        except Exception as exc:
            pytest.fail(f"clear() on empty registry raised: {exc}")

    def test_can_register_after_clear(self, registry):
        registry.register(_FakeTool)
        registry.clear()
        registry.register(_FakeTool)
        assert "fake_tool" in registry.list_tools()


# ===========================================================================
# clear_category
# ===========================================================================

class TestClearCategory:
    def test_clears_matching_category(self, registry):
        registry.register(_FakeTool)       # category = "test"
        registry.register(_AnotherFakeTool)  # category = "other"
        registry.clear_category("test")
        assert "fake_tool" not in registry.list_tools()

    def test_keeps_non_matching_category(self, registry):
        registry.register(_FakeTool)       # category = "test"
        registry.register(_AnotherFakeTool)  # category = "other"
        registry.clear_category("test")
        assert "another_tool" in registry.list_tools()

    def test_unknown_category_no_error(self, registry):
        registry.register(_FakeTool)
        try:
            registry.clear_category("nonexistent_category")
        except Exception as exc:
            pytest.fail(f"clear_category raised: {exc}")

    def test_unknown_category_leaves_tools_intact(self, registry):
        registry.register(_FakeTool)
        registry.clear_category("nonexistent_category")
        assert "fake_tool" in registry.list_tools()

    def test_clear_category_invalidates_cache(self, registry):
        registry.register(_FakeTool)
        registry.get_all_definitions()  # prime cache
        registry.clear_category("test")
        _, is_cached = registry.get_cache_info()
        assert is_cached is False

    def test_clear_category_tool_without_category_attr(self, registry):
        # Tool without a 'category' attribute must not be removed
        class _NoCategoryTool(BaseTool):
            def get_definition(self):
                return Tool(name="no_cat_tool", description="No category", parameters=[])
            def execute(self, **kwargs):
                from ai.tools.base_tool import ToolResult
                return ToolResult(success=True, output=None)

        registry.register(_NoCategoryTool)
        registry.clear_category("test")
        assert "no_cat_tool" in registry.list_tools()


# ===========================================================================
# Global tool_registry instance
# ===========================================================================

class TestGlobalToolRegistry:
    def test_global_is_tool_registry(self):
        # We must NOT use the autouse fixture for this check because the
        # module-level global was created before the fixture ran.
        # Just verify its type directly.
        from ai.tools.tool_registry import tool_registry as gr
        assert isinstance(gr, ToolRegistry)

    def test_global_singleton_flag_set(self):
        from ai.tools.tool_registry import tool_registry as gr
        assert gr._initialized is True
