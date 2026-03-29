"""
Tests for ExecutionContext and ChainExecutor built-in transformers/conditions
in src/ai/agents/chain_builder.py

Covers ExecutionContext (init defaults, get/set, add_result, add_error),
ChainExecutor's 3 default transformers (json_to_dict, extract_field,
format_template) and 3 default conditions (has_key, is_not_empty, contains_text),
plus register_transformer and register_condition.
No network, no Tkinter, no file I/O.
"""

import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.agents.chain_builder import ExecutionContext, ChainExecutor


# ===========================================================================
# ExecutionContext
# ===========================================================================

class TestExecutionContext:
    def test_data_default_empty(self):
        ctx = ExecutionContext()
        assert ctx.data == {}

    def test_results_default_empty(self):
        ctx = ExecutionContext()
        assert ctx.results == {}

    def test_errors_default_empty(self):
        ctx = ExecutionContext()
        assert ctx.errors == []

    def test_executed_nodes_default_empty(self):
        ctx = ExecutionContext()
        assert ctx.executed_nodes == []

    def test_set_stores_value(self):
        ctx = ExecutionContext()
        ctx.set("key", "value")
        assert ctx.data["key"] == "value"

    def test_get_returns_stored_value(self):
        ctx = ExecutionContext()
        ctx.set("name", "Alice")
        assert ctx.get("name") == "Alice"

    def test_get_returns_default_for_missing(self):
        ctx = ExecutionContext()
        assert ctx.get("missing") is None

    def test_get_returns_custom_default(self):
        ctx = ExecutionContext()
        assert ctx.get("missing", "fallback") == "fallback"

    def test_add_error_appends_to_list(self):
        ctx = ExecutionContext()
        ctx.add_error("something broke")
        assert ctx.errors == ["something broke"]

    def test_add_multiple_errors(self):
        ctx = ExecutionContext()
        ctx.add_error("err1")
        ctx.add_error("err2")
        assert len(ctx.errors) == 2
        assert "err1" in ctx.errors
        assert "err2" in ctx.errors

    def test_add_result_stores_in_results(self):
        ctx = ExecutionContext()
        mock_response = object()
        ctx.add_result("node1", mock_response)
        assert ctx.results["node1"] is mock_response

    def test_add_result_appends_to_executed_nodes(self):
        ctx = ExecutionContext()
        ctx.add_result("node_a", object())
        assert "node_a" in ctx.executed_nodes

    def test_add_result_multiple_nodes(self):
        ctx = ExecutionContext()
        ctx.add_result("node1", object())
        ctx.add_result("node2", object())
        assert len(ctx.executed_nodes) == 2

    def test_set_overwrites_existing_value(self):
        ctx = ExecutionContext()
        ctx.set("x", 1)
        ctx.set("x", 2)
        assert ctx.get("x") == 2


# ===========================================================================
# ChainExecutor — initialization
# ===========================================================================

class TestChainExecutorInit:
    def test_has_three_default_transformers(self):
        ex = ChainExecutor()
        assert "json_to_dict" in ex.transformers
        assert "extract_field" in ex.transformers
        assert "format_template" in ex.transformers

    def test_has_three_default_conditions(self):
        ex = ChainExecutor()
        assert "has_key" in ex.conditions
        assert "is_not_empty" in ex.conditions
        assert "contains_text" in ex.conditions

    def test_register_transformer_adds_custom(self):
        ex = ChainExecutor()
        ex.register_transformer("upper", lambda data, cfg: str(data).upper())
        assert "upper" in ex.transformers

    def test_register_condition_adds_custom(self):
        ex = ChainExecutor()
        ex.register_condition("always_true", lambda ctx: True)
        assert "always_true" in ex.conditions


# ===========================================================================
# ChainExecutor — transformer: json_to_dict
# ===========================================================================

class TestTransformerJsonToDict:
    def setup_method(self):
        self.fn = ChainExecutor().transformers["json_to_dict"]

    def test_valid_json_object(self):
        result = self.fn('{"key": "value"}', {})
        assert result == {"key": "value"}

    def test_valid_json_with_numbers(self):
        result = self.fn('{"a": 1, "b": 2.5}', {})
        assert result == {"a": 1, "b": 2.5}

    def test_invalid_json_returns_empty_dict(self):
        result = self.fn("not json", {})
        assert result == {}

    def test_none_input_returns_empty_dict(self):
        result = self.fn(None, {})
        assert result == {}

    def test_empty_object_json(self):
        result = self.fn("{}", {})
        assert result == {}

    def test_nested_json(self):
        result = self.fn('{"a": {"b": 1}}', {})
        assert result["a"]["b"] == 1


# ===========================================================================
# ChainExecutor — transformer: extract_field
# ===========================================================================

class TestTransformerExtractField:
    def setup_method(self):
        self.fn = ChainExecutor().transformers["extract_field"]

    def test_extracts_existing_field(self):
        result = self.fn({"name": "Alice", "age": 30}, {"field": "name"})
        assert result == "Alice"

    def test_returns_none_for_missing_field(self):
        result = self.fn({"x": 1}, {"field": "y"})
        assert result is None

    def test_returns_none_when_no_field_config(self):
        result = self.fn({"x": 1}, {})
        assert result is None

    def test_extracts_numeric_value(self):
        result = self.fn({"count": 42}, {"field": "count"})
        assert result == 42

    def test_extracts_nested_dict_value(self):
        data = {"info": {"name": "Bob"}}
        result = self.fn(data, {"field": "info"})
        assert result == {"name": "Bob"}


# ===========================================================================
# ChainExecutor — transformer: format_template
# ===========================================================================

class TestTransformerFormatTemplate:
    def setup_method(self):
        self.fn = ChainExecutor().transformers["format_template"]

    def test_format_with_dict(self):
        result = self.fn({"name": "Alice"}, {"template": "Hello {name}"})
        assert result == "Hello Alice"

    def test_format_with_positional_arg(self):
        result = self.fn("world", {"template": "Hello {}"})
        assert result == "Hello world"

    def test_missing_key_returns_str_of_data(self):
        result = self.fn({"x": 1}, {"template": "Hello {name}"})
        # KeyError falls back to str(data)
        assert isinstance(result, str)

    def test_no_template_returns_str(self):
        result = self.fn("hello", {})
        assert isinstance(result, str)

    def test_multiple_placeholders(self):
        result = self.fn({"first": "John", "last": "Doe"},
                         {"template": "{first} {last}"})
        assert result == "John Doe"


# ===========================================================================
# ChainExecutor — condition: has_key
# ===========================================================================

class TestConditionHasKey:
    def setup_method(self):
        self.fn = ChainExecutor().conditions["has_key"]

    def test_returns_true_when_key_present(self):
        ctx = ExecutionContext()
        ctx.set("mykey", "hello")
        ctx.set("condition_key", "mykey")
        assert self.fn(ctx) is True

    def test_returns_false_when_key_absent(self):
        ctx = ExecutionContext()
        ctx.set("condition_key", "missing_key")
        assert self.fn(ctx) is False

    def test_returns_false_when_no_condition_key(self):
        ctx = ExecutionContext()
        assert self.fn(ctx) is False


# ===========================================================================
# ChainExecutor — condition: is_not_empty
# ===========================================================================

class TestConditionIsNotEmpty:
    def setup_method(self):
        self.fn = ChainExecutor().conditions["is_not_empty"]

    def test_returns_true_for_non_empty_value(self):
        ctx = ExecutionContext()
        ctx.set("condition_key", "result")
        ctx.set("result", "some text")
        assert self.fn(ctx) is True

    def test_returns_false_for_empty_string(self):
        ctx = ExecutionContext()
        ctx.set("condition_key", "result")
        ctx.set("result", "")
        assert self.fn(ctx) is False

    def test_returns_false_for_none(self):
        ctx = ExecutionContext()
        ctx.set("condition_key", "result")
        ctx.set("result", None)
        assert self.fn(ctx) is False

    def test_returns_false_when_no_condition_key(self):
        ctx = ExecutionContext()
        assert self.fn(ctx) is False


# ===========================================================================
# ChainExecutor — condition: contains_text
# ===========================================================================

class TestConditionContainsText:
    def setup_method(self):
        self.fn = ChainExecutor().conditions["contains_text"]

    def test_returns_true_when_text_contains_substring(self):
        ctx = ExecutionContext()
        ctx.set("text_key", "content")
        ctx.set("content", "diabetes treatment")
        ctx.set("search_text", "diabetes")
        assert self.fn(ctx) is True

    def test_returns_false_when_text_not_contains(self):
        ctx = ExecutionContext()
        ctx.set("text_key", "content")
        ctx.set("content", "hypertension")
        ctx.set("search_text", "diabetes")
        assert self.fn(ctx) is False

    def test_returns_false_when_no_text_key(self):
        ctx = ExecutionContext()
        ctx.set("search_text", "diabetes")
        assert self.fn(ctx) is False

    def test_returns_false_when_no_search_text(self):
        ctx = ExecutionContext()
        ctx.set("text_key", "content")
        ctx.set("content", "some text")
        assert self.fn(ctx) is False
