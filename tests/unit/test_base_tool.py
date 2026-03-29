"""
Tests for BaseTool and ToolResult in src/ai/tools/base_tool.py

Covers ToolResult (Pydantic model fields, defaults), BaseTool._validate_type
(all supported types + unknown), BaseTool.validate_arguments (required check,
type check, valid pass), and BaseTool.safe_execute (delegates to execute,
catches validation errors, catches execute exceptions).
No network, no Tkinter, no file I/O.
"""

import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.tools.base_tool import BaseTool, ToolResult
from ai.agents.models import Tool, ToolParameter


# ---------------------------------------------------------------------------
# Concrete stub implementing the abstract methods
# ---------------------------------------------------------------------------

class _SimpleTool(BaseTool):
    """Minimal concrete tool for testing BaseTool logic."""

    def __init__(self, required_params=None, raises_in_execute=False):
        super().__init__()
        self._param_defs = required_params if required_params is not None else [
            ToolParameter(name="text", type="string",
                          description="input text", required=True),
            ToolParameter(name="count", type="integer",
                          description="optional count", required=False),
        ]
        self._raises = raises_in_execute

    def get_definition(self) -> Tool:
        return Tool(
            name="simple_tool",
            description="A simple test tool",
            parameters=self._param_defs,
        )

    def execute(self, **kwargs) -> ToolResult:
        if self._raises:
            raise RuntimeError("execute failed")
        return ToolResult(success=True, output=f"processed: {kwargs.get('text', '')}")


# ===========================================================================
# ToolResult
# ===========================================================================

class TestToolResult:
    def test_success_and_output_required(self):
        r = ToolResult(success=True, output="hello")
        assert r.success is True
        assert r.output == "hello"

    def test_error_default_none(self):
        r = ToolResult(success=True, output="ok")
        assert r.error is None

    def test_metadata_default_empty(self):
        r = ToolResult(success=True, output="ok")
        assert r.metadata == {}

    def test_requires_confirmation_default_false(self):
        r = ToolResult(success=True, output="ok")
        assert r.requires_confirmation is False

    def test_confirmation_message_default_none(self):
        r = ToolResult(success=True, output="ok")
        assert r.confirmation_message is None

    def test_error_stored(self):
        r = ToolResult(success=False, output=None, error="something went wrong")
        assert r.error == "something went wrong"

    def test_requires_confirmation_true(self):
        r = ToolResult(success=True, output="ok",
                       requires_confirmation=True,
                       confirmation_message="Are you sure?")
        assert r.requires_confirmation is True
        assert r.confirmation_message == "Are you sure?"

    def test_metadata_stored(self):
        r = ToolResult(success=True, output="ok", metadata={"key": "val"})
        assert r.metadata == {"key": "val"}

    def test_output_none_allowed(self):
        r = ToolResult(success=False, output=None)
        assert r.output is None


# ===========================================================================
# BaseTool._validate_type
# ===========================================================================

class TestValidateType:
    def setup_method(self):
        self.tool = _SimpleTool()

    def test_string_type_valid(self):
        assert self.tool._validate_type("hello", "string") is True

    def test_string_type_invalid_int(self):
        assert self.tool._validate_type(42, "string") is False

    def test_integer_type_valid(self):
        assert self.tool._validate_type(42, "integer") is True

    def test_integer_type_invalid_str(self):
        assert self.tool._validate_type("42", "integer") is False

    def test_number_accepts_int(self):
        assert self.tool._validate_type(5, "number") is True

    def test_number_accepts_float(self):
        assert self.tool._validate_type(3.14, "number") is True

    def test_number_invalid_str(self):
        assert self.tool._validate_type("3.14", "number") is False

    def test_boolean_valid(self):
        assert self.tool._validate_type(True, "boolean") is True

    def test_boolean_invalid_str(self):
        assert self.tool._validate_type("true", "boolean") is False

    def test_array_valid(self):
        assert self.tool._validate_type([1, 2, 3], "array") is True

    def test_array_invalid_dict(self):
        assert self.tool._validate_type({}, "array") is False

    def test_object_valid(self):
        assert self.tool._validate_type({"key": "val"}, "object") is True

    def test_object_invalid_list(self):
        assert self.tool._validate_type([], "object") is False

    def test_unknown_type_allows_any_value(self):
        assert self.tool._validate_type("anything", "custom_type") is True
        assert self.tool._validate_type(42, "custom_type") is True


# ===========================================================================
# BaseTool.validate_arguments
# ===========================================================================

class TestValidateArguments:
    def setup_method(self):
        self.tool = _SimpleTool()

    def test_valid_required_param_returns_none(self):
        assert self.tool.validate_arguments(text="hello") is None

    def test_missing_required_param_returns_error(self):
        result = self.tool.validate_arguments()
        assert result is not None
        assert "text" in result

    def test_wrong_type_required_param_returns_error(self):
        result = self.tool.validate_arguments(text=42)
        assert result is not None
        assert "text" in result

    def test_optional_param_not_required(self):
        # Omitting 'count' (optional) should be fine
        assert self.tool.validate_arguments(text="hello") is None

    def test_optional_param_with_wrong_type_returns_error(self):
        result = self.tool.validate_arguments(text="hello", count="not_an_int")
        assert result is not None
        assert "count" in result

    def test_all_params_correct_returns_none(self):
        assert self.tool.validate_arguments(text="hello", count=5) is None

    def test_error_message_is_string(self):
        result = self.tool.validate_arguments()
        assert isinstance(result, str)

    def test_no_params_tool_accepts_anything(self):
        no_param_tool = _SimpleTool(required_params=[])
        assert no_param_tool.validate_arguments(extra="ignored") is None


# ===========================================================================
# BaseTool.safe_execute
# ===========================================================================

class TestSafeExecute:
    def test_valid_args_returns_success_result(self):
        tool = _SimpleTool()
        result = tool.safe_execute(text="hello")
        assert result.success is True

    def test_valid_args_output_contains_input(self):
        tool = _SimpleTool()
        result = tool.safe_execute(text="world")
        assert "world" in str(result.output)

    def test_missing_required_returns_failure(self):
        tool = _SimpleTool()
        result = tool.safe_execute()
        assert result.success is False
        assert result.error is not None

    def test_wrong_type_returns_failure(self):
        tool = _SimpleTool()
        result = tool.safe_execute(text=123)
        assert result.success is False

    def test_execute_exception_returns_failure(self):
        tool = _SimpleTool(raises_in_execute=True)
        result = tool.safe_execute(text="hello")
        assert result.success is False
        assert result.error is not None

    def test_execute_exception_error_message_contains_detail(self):
        tool = _SimpleTool(raises_in_execute=True)
        result = tool.safe_execute(text="hello")
        assert "execute failed" in result.error

    def test_returns_tool_result_on_validation_failure(self):
        tool = _SimpleTool()
        result = tool.safe_execute()
        assert isinstance(result, ToolResult)

    def test_returns_tool_result_on_success(self):
        tool = _SimpleTool()
        result = tool.safe_execute(text="ok")
        assert isinstance(result, ToolResult)
