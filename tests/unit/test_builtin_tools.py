"""
Tests for built-in tools in src/ai/tools/builtin_tools.py

Covers _validate_file_path (home dir allowed, outside blocked, empty, null byte),
CalculatorTool.execute (basic arithmetic, sqrt, unary minus, division by zero,
invalid expression), DateTimeTool.execute (now/today/add_days/format/unknown op),
and JSONTool.execute (parse valid, parse invalid, format, get_value by path,
list index, path not found, unknown operation).
No network, no Tkinter, no file I/O beyond path validation.
"""

import sys
import datetime
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.tools.builtin_tools import (
    _validate_file_path, CalculatorTool, DateTimeTool, JSONTool,
)
from ai.tools.base_tool import ToolResult

HOME_DIR = str(Path.home())


# ===========================================================================
# _validate_file_path
# ===========================================================================

class TestValidateFilePath:
    def test_path_within_home_is_valid(self):
        valid, err = _validate_file_path(HOME_DIR + "/test_file.txt")
        assert valid is True
        assert err == ""

    def test_home_dir_itself_is_valid(self):
        valid, err = _validate_file_path(HOME_DIR)
        assert valid is True

    def test_path_outside_home_denied(self):
        valid, err = _validate_file_path("/etc/passwd")
        assert valid is False
        assert "Access denied" in err or len(err) > 0

    def test_empty_path_invalid(self):
        valid, err = _validate_file_path("")
        assert valid is False

    def test_null_byte_invalid(self):
        valid, err = _validate_file_path("file\x00name")
        assert valid is False

    def test_returns_tuple(self):
        result = _validate_file_path(HOME_DIR + "/file.txt")
        assert isinstance(result, tuple) and len(result) == 2

    def test_path_error_is_string(self):
        _, err = _validate_file_path("/etc/shadow")
        assert isinstance(err, str)


# ===========================================================================
# CalculatorTool
# ===========================================================================

class TestCalculatorTool:
    def setup_method(self):
        self.tool = CalculatorTool()

    def test_addition(self):
        r = self.tool.execute("2 + 2")
        assert r.success is True
        assert r.output == 4

    def test_subtraction(self):
        r = self.tool.execute("10 - 3")
        assert r.success is True
        assert r.output == 7

    def test_multiplication(self):
        r = self.tool.execute("4 * 5")
        assert r.success is True
        assert r.output == 20

    def test_division(self):
        r = self.tool.execute("10 / 4")
        assert r.success is True
        assert r.output == 2.5

    def test_power(self):
        r = self.tool.execute("2 ** 8")
        assert r.success is True
        assert r.output == 256

    def test_sqrt(self):
        r = self.tool.execute("sqrt(16)")
        assert r.success is True
        assert r.output == 4.0

    def test_unary_minus(self):
        r = self.tool.execute("-5")
        assert r.success is True
        assert r.output == -5

    def test_complex_expression(self):
        r = self.tool.execute("(2 + 3) * 4")
        assert r.success is True
        assert r.output == 20

    def test_division_by_zero_fails(self):
        r = self.tool.execute("1 / 0")
        assert r.success is False
        assert r.error is not None

    def test_invalid_expression_fails(self):
        r = self.tool.execute("import os")
        assert r.success is False

    def test_returns_tool_result(self):
        r = self.tool.execute("1 + 1")
        assert isinstance(r, ToolResult)

    def test_metadata_has_expression(self):
        r = self.tool.execute("3 + 4")
        assert "expression" in r.metadata

    def test_abs_function(self):
        r = self.tool.execute("abs(-10)")
        assert r.success is True
        assert r.output == 10

    def test_round_function(self):
        r = self.tool.execute("round(3.7)")
        assert r.success is True
        assert r.output == 4

    def test_min_function(self):
        r = self.tool.execute("min(5, 3, 8)")
        assert r.success is True
        assert r.output == 3

    def test_max_function(self):
        r = self.tool.execute("max(5, 3, 8)")
        assert r.success is True
        assert r.output == 8


# ===========================================================================
# DateTimeTool
# ===========================================================================

class TestDateTimeTool:
    def setup_method(self):
        self.tool = DateTimeTool()

    def test_today_operation_succeeds(self):
        r = self.tool.execute("today")
        assert r.success is True

    def test_today_output_is_string(self):
        r = self.tool.execute("today")
        assert isinstance(r.output, str)

    def test_today_is_iso_format(self):
        r = self.tool.execute("today")
        # Should be YYYY-MM-DD format
        parts = r.output.split("-")
        assert len(parts) == 3
        assert len(parts[0]) == 4  # year

    def test_now_operation_succeeds(self):
        r = self.tool.execute("now")
        assert r.success is True
        assert isinstance(r.output, str)

    def test_add_days_positive(self):
        r = self.tool.execute("add_days", days=7)
        assert r.success is True
        assert isinstance(r.output, str)

    def test_add_days_negative(self):
        r = self.tool.execute("add_days", days=-7)
        assert r.success is True

    def test_add_days_zero(self):
        r = self.tool.execute("add_days", days=0)
        assert r.success is True

    def test_format_operation_succeeds(self):
        r = self.tool.execute("format", format="%Y")
        assert r.success is True
        # Should just be the 4-digit year
        assert len(r.output) == 4

    def test_unknown_operation_fails(self):
        r = self.tool.execute("unknown_operation")
        assert r.success is False
        assert "Unknown operation" in r.error

    def test_metadata_has_operation(self):
        r = self.tool.execute("today")
        assert "operation" in r.metadata

    def test_returns_tool_result(self):
        r = self.tool.execute("today")
        assert isinstance(r, ToolResult)

    def test_now_contains_year(self):
        r = self.tool.execute("now")
        current_year = str(datetime.datetime.now().year)
        assert current_year in r.output


# ===========================================================================
# JSONTool
# ===========================================================================

class TestJSONTool:
    def setup_method(self):
        self.tool = JSONTool()

    def test_parse_valid_json(self):
        r = self.tool.execute("parse", '{"key": "value"}')
        assert r.success is True
        assert r.output == {"key": "value"}

    def test_parse_array_json(self):
        r = self.tool.execute("parse", '[1, 2, 3]')
        assert r.success is True
        assert r.output == [1, 2, 3]

    def test_parse_invalid_json_fails(self):
        r = self.tool.execute("parse", "not json")
        assert r.success is False
        assert r.error is not None

    def test_format_operation(self):
        r = self.tool.execute("format", '{"key": "value"}', indent=2)
        assert r.success is True
        assert "  " in r.output  # Indented

    def test_format_output_is_string(self):
        r = self.tool.execute("format", '{"a": 1}')
        assert isinstance(r.output, str)

    def test_get_value_top_level(self):
        r = self.tool.execute("get_value", '{"name": "Alice"}', path="name")
        assert r.success is True
        assert r.output == "Alice"

    def test_get_value_nested(self):
        r = self.tool.execute("get_value", '{"a": {"b": 42}}', path="a.b")
        assert r.success is True
        assert r.output == 42

    def test_get_value_list_index(self):
        r = self.tool.execute("get_value", '{"items": [10, 20, 30]}', path="items.1")
        assert r.success is True
        assert r.output == 20

    def test_get_value_path_not_found(self):
        r = self.tool.execute("get_value", '{"a": 1}', path="b.c")
        assert r.success is False
        assert "not found" in r.error.lower() or r.error is not None

    def test_get_value_no_path_returns_object(self):
        r = self.tool.execute("get_value", '{"key": 99}')
        assert r.success is True
        assert r.output == {"key": 99}

    def test_unknown_operation_fails(self):
        r = self.tool.execute("merge", '{}')
        assert r.success is False
        assert r.error is not None

    def test_returns_tool_result(self):
        r = self.tool.execute("parse", '{}')
        assert isinstance(r, ToolResult)

    def test_parse_nested_json(self):
        r = self.tool.execute("parse", '{"a": {"b": {"c": "deep"}}}')
        assert r.success is True
        assert r.output["a"]["b"]["c"] == "deep"

    def test_format_deeply_indented(self):
        r = self.tool.execute("format", '{"a": 1}', indent=4)
        assert r.success is True
        assert "    " in r.output
