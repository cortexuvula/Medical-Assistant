"""
Tests for pure-logic methods of MCPToolWrapper in src/ai/mcp/mcp_tool_wrapper.py.

Covers:
  - MCPToolWrapper.validate_args(**kwargs) -> Optional[str]
  - MCPToolWrapper._get_cache_key(**kwargs) -> str

No network, no MCP server, no Tkinter.
ResultCache tests are in test_mcp_result_cache.py — not duplicated here.
"""

import sys
import hashlib
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.mcp.mcp_tool_wrapper import MCPToolWrapper


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------

def make_wrapper(server_name="test_server", original_name="test_tool", tool_info=None):
    """Return an MCPToolWrapper backed by a MagicMock manager."""
    if tool_info is None:
        tool_info = {"name": original_name, "description": "A test tool"}
    return MCPToolWrapper(MagicMock(), server_name, tool_info)


def make_wrapper_with_schema(
    server_name="test_server",
    original_name="test_tool",
    properties=None,
    required=None,
):
    """Return an MCPToolWrapper with a given inputSchema."""
    schema = {}
    if properties is not None:
        schema["properties"] = properties
    if required is not None:
        schema["required"] = required
    tool_info = {
        "name": original_name,
        "description": "A test tool",
        "inputSchema": schema,
    }
    return MCPToolWrapper(MagicMock(), server_name, tool_info)


# ===========================================================================
# MCPToolWrapper construction sanity
# ===========================================================================

class TestMCPToolWrapperInit:
    def test_name_is_mcp_server_original(self):
        w = make_wrapper(server_name="srv", original_name="tool")
        assert w.name == "mcp_srv_tool"

    def test_original_name_stored(self):
        w = make_wrapper(original_name="search")
        assert w.original_name == "search"

    def test_server_name_stored(self):
        w = make_wrapper(server_name="brave-search")
        assert w.server_name == "brave-search"

    def test_input_schema_defaults_to_empty_dict_when_absent(self):
        w = make_wrapper()
        assert w.input_schema == {}

    def test_input_schema_stored_when_present(self):
        props = {"q": {"type": "string"}}
        w = make_wrapper_with_schema(properties=props)
        assert w.input_schema["properties"] == props

    def test_description_stored(self):
        tool_info = {"name": "t", "description": "Does something"}
        w = MCPToolWrapper(MagicMock(), "s", tool_info)
        assert w.description == "Does something"

    def test_description_defaults_to_server_name(self):
        tool_info = {"name": "t"}
        w = MCPToolWrapper(MagicMock(), "myserver", tool_info)
        assert "myserver" in w.description

    def test_category_is_mcp(self):
        w = make_wrapper()
        assert w.category == "mcp"


# ===========================================================================
# validate_args — no schema
# ===========================================================================

class TestValidateArgsNoSchema:
    def test_empty_input_schema_always_returns_none(self):
        w = make_wrapper()  # input_schema == {}
        assert w.validate_args() is None

    def test_empty_schema_ignores_extra_kwargs(self):
        w = make_wrapper()
        assert w.validate_args(foo="bar", baz=42) is None

    def test_schema_without_properties_key_returns_none(self):
        # inputSchema present but has no "properties"
        tool_info = {"name": "t", "description": "d", "inputSchema": {"type": "object"}}
        w = MCPToolWrapper(MagicMock(), "s", tool_info)
        assert w.validate_args(anything="ok") is None

    def test_schema_without_properties_ignores_required(self):
        # Even if schema has required but no properties, no check runs
        tool_info = {
            "name": "t",
            "description": "d",
            "inputSchema": {"required": ["q"]},
        }
        w = MCPToolWrapper(MagicMock(), "s", tool_info)
        assert w.validate_args() is None


# ===========================================================================
# validate_args — required field checks
# ===========================================================================

class TestValidateArgsRequired:
    def test_required_field_present_returns_none(self):
        w = make_wrapper_with_schema(
            properties={"q": {"type": "string"}},
            required=["q"],
        )
        assert w.validate_args(q="hello") is None

    def test_required_field_missing_returns_error(self):
        w = make_wrapper_with_schema(
            properties={"q": {"type": "string"}},
            required=["q"],
        )
        result = w.validate_args()
        assert result == "Missing required field: q"

    def test_required_field_missing_error_contains_field_name(self):
        w = make_wrapper_with_schema(
            properties={"patient_id": {"type": "string"}},
            required=["patient_id"],
        )
        result = w.validate_args()
        assert "patient_id" in result

    def test_two_required_both_present_returns_none(self):
        w = make_wrapper_with_schema(
            properties={
                "q": {"type": "string"},
                "count": {"type": "number"},
            },
            required=["q", "count"],
        )
        assert w.validate_args(q="test", count=5) is None

    def test_two_required_first_missing(self):
        w = make_wrapper_with_schema(
            properties={
                "q": {"type": "string"},
                "count": {"type": "number"},
            },
            required=["q", "count"],
        )
        # Only provide count
        result = w.validate_args(count=5)
        assert result == "Missing required field: q"

    def test_two_required_second_missing(self):
        w = make_wrapper_with_schema(
            properties={
                "q": {"type": "string"},
                "count": {"type": "number"},
            },
            required=["q", "count"],
        )
        # Only provide q
        result = w.validate_args(q="test")
        assert result is not None
        assert "count" in result

    def test_no_required_key_in_schema_accepts_empty_kwargs(self):
        w = make_wrapper_with_schema(properties={"q": {"type": "string"}})
        assert w.validate_args() is None

    def test_no_required_key_in_schema_accepts_any_provided_args(self):
        w = make_wrapper_with_schema(properties={"q": {"type": "string"}})
        assert w.validate_args(q="hello") is None

    def test_empty_required_list_returns_none(self):
        w = make_wrapper_with_schema(
            properties={"q": {"type": "string"}},
            required=[],
        )
        assert w.validate_args() is None


# ===========================================================================
# validate_args — string type
# ===========================================================================

class TestValidateArgsStringType:
    def _w(self):
        return make_wrapper_with_schema(properties={"q": {"type": "string"}})

    def test_string_value_returns_none(self):
        assert self._w().validate_args(q="hello") is None

    def test_int_value_for_string_field_returns_error(self):
        result = self._w().validate_args(q=42)
        assert result == "Field q must be a string"

    def test_float_value_for_string_field_returns_error(self):
        result = self._w().validate_args(q=3.14)
        assert result == "Field q must be a string"

    def test_none_value_for_string_field_returns_error(self):
        result = self._w().validate_args(q=None)
        assert result == "Field q must be a string"

    def test_list_value_for_string_field_returns_error(self):
        result = self._w().validate_args(q=["a", "b"])
        assert result == "Field q must be a string"

    def test_empty_string_is_valid(self):
        assert self._w().validate_args(q="") is None

    def test_bool_value_for_string_field_returns_error(self):
        # bool is a subclass of int, not str
        result = self._w().validate_args(q=True)
        assert result == "Field q must be a string"


# ===========================================================================
# validate_args — number type
# ===========================================================================

class TestValidateArgsNumberType:
    def _w(self):
        return make_wrapper_with_schema(properties={"count": {"type": "number"}})

    def test_int_value_returns_none(self):
        assert self._w().validate_args(count=10) is None

    def test_float_value_returns_none(self):
        assert self._w().validate_args(count=3.14) is None

    def test_zero_int_returns_none(self):
        assert self._w().validate_args(count=0) is None

    def test_negative_number_returns_none(self):
        assert self._w().validate_args(count=-5) is None

    def test_string_value_for_number_field_returns_error(self):
        result = self._w().validate_args(count="ten")
        assert result == "Field count must be a number"

    def test_none_value_for_number_field_returns_error(self):
        result = self._w().validate_args(count=None)
        assert result == "Field count must be a number"

    def test_list_value_for_number_field_returns_error(self):
        result = self._w().validate_args(count=[1, 2])
        assert result == "Field count must be a number"


# ===========================================================================
# validate_args — boolean type
# ===========================================================================

class TestValidateArgsBooleanType:
    def _w(self):
        return make_wrapper_with_schema(properties={"flag": {"type": "boolean"}})

    def test_true_returns_none(self):
        assert self._w().validate_args(flag=True) is None

    def test_false_returns_none(self):
        assert self._w().validate_args(flag=False) is None

    def test_int_one_returns_error(self):
        # bool is subclass of int but int is NOT bool
        result = self._w().validate_args(flag=1)
        assert result == "Field flag must be a boolean"

    def test_int_zero_returns_error(self):
        result = self._w().validate_args(flag=0)
        assert result == "Field flag must be a boolean"

    def test_string_returns_error(self):
        result = self._w().validate_args(flag="true")
        assert result == "Field flag must be a boolean"

    def test_none_returns_error(self):
        result = self._w().validate_args(flag=None)
        assert result == "Field flag must be a boolean"


# ===========================================================================
# validate_args — array type
# ===========================================================================

class TestValidateArgsArrayType:
    def _w(self):
        return make_wrapper_with_schema(properties={"items": {"type": "array"}})

    def test_list_returns_none(self):
        assert self._w().validate_args(items=["a", "b"]) is None

    def test_empty_list_returns_none(self):
        assert self._w().validate_args(items=[]) is None

    def test_tuple_returns_error(self):
        result = self._w().validate_args(items=("a", "b"))
        assert result == "Field items must be an array"

    def test_string_returns_error(self):
        result = self._w().validate_args(items="abc")
        assert result == "Field items must be an array"

    def test_dict_returns_error(self):
        result = self._w().validate_args(items={"a": 1})
        assert result == "Field items must be an array"

    def test_none_returns_error(self):
        result = self._w().validate_args(items=None)
        assert result == "Field items must be an array"


# ===========================================================================
# validate_args — object type
# ===========================================================================

class TestValidateArgsObjectType:
    def _w(self):
        return make_wrapper_with_schema(properties={"data": {"type": "object"}})

    def test_dict_returns_none(self):
        assert self._w().validate_args(data={"key": "value"}) is None

    def test_empty_dict_returns_none(self):
        assert self._w().validate_args(data={}) is None

    def test_string_returns_error(self):
        result = self._w().validate_args(data="hello")
        assert result == "Field data must be an object"

    def test_list_returns_error(self):
        result = self._w().validate_args(data=[1, 2])
        assert result == "Field data must be an object"

    def test_none_returns_error(self):
        result = self._w().validate_args(data=None)
        assert result == "Field data must be an object"


# ===========================================================================
# validate_args — edge cases
# ===========================================================================

class TestValidateArgsEdgeCases:
    def test_unknown_field_not_in_properties_returns_none(self):
        # Fields not in properties are silently allowed
        w = make_wrapper_with_schema(properties={"q": {"type": "string"}})
        assert w.validate_args(unknown_field="anything") is None

    def test_field_with_no_type_key_returns_none(self):
        # Property defined but without a "type" key
        w = make_wrapper_with_schema(properties={"q": {"description": "a query"}})
        assert w.validate_args(q=42) is None

    def test_empty_kwargs_no_required_returns_none(self):
        w = make_wrapper_with_schema(
            properties={"q": {"type": "string"}},
            required=[],
        )
        assert w.validate_args() is None

    def test_required_field_provided_and_type_passes(self):
        w = make_wrapper_with_schema(
            properties={"q": {"type": "string"}},
            required=["q"],
        )
        assert w.validate_args(q="valid string") is None

    def test_required_field_provided_but_wrong_type_fails_type_check(self):
        w = make_wrapper_with_schema(
            properties={"q": {"type": "string"}},
            required=["q"],
        )
        # Required field is present but wrong type — type error takes effect
        result = w.validate_args(q=123)
        assert result == "Field q must be a string"

    def test_multiple_fields_first_bad_type_reported(self):
        # With two fields both having wrong types, the first one encountered
        # in kwargs iteration triggers the error
        w = make_wrapper_with_schema(
            properties={
                "q": {"type": "string"},
                "count": {"type": "number"},
            }
        )
        result = w.validate_args(q=99, count="bad")
        # At least one error must be reported
        assert result is not None
        assert "must be" in result


# ===========================================================================
# _get_cache_key
# ===========================================================================

class TestGetCacheKey:
    def test_returns_string(self):
        w = make_wrapper()
        key = w._get_cache_key(q="hello")
        assert isinstance(key, str)

    def test_returns_32_char_hex(self):
        w = make_wrapper()
        key = w._get_cache_key(q="hello")
        assert len(key) == 32
        assert all(c in "0123456789abcdef" for c in key)

    def test_deterministic_same_kwargs(self):
        w = make_wrapper()
        key1 = w._get_cache_key(q="test", count=5)
        key2 = w._get_cache_key(q="test", count=5)
        assert key1 == key2

    def test_different_kwargs_produce_different_keys(self):
        w = make_wrapper()
        key1 = w._get_cache_key(q="hello")
        key2 = w._get_cache_key(q="world")
        assert key1 != key2

    def test_empty_kwargs(self):
        w = make_wrapper()
        key = w._get_cache_key()
        assert len(key) == 32

    def test_empty_kwargs_matches_expected_md5(self):
        w = make_wrapper(server_name="test_server", original_name="test_tool")
        # name == "mcp_test_server_test_tool", kwargs == {}
        args_str = json.dumps({}, sort_keys=True, default=str)
        key_content = f"mcp_test_server_test_tool:{args_str}"
        expected = hashlib.md5(key_content.encode(), usedforsecurity=False).hexdigest()
        assert w._get_cache_key() == expected

    def test_key_ordering_does_not_matter(self):
        w = make_wrapper()
        key_ab = w._get_cache_key(a=1, b=2)
        key_ba = w._get_cache_key(b=2, a=1)
        assert key_ab == key_ba

    def test_key_ordering_three_args(self):
        w = make_wrapper()
        key1 = w._get_cache_key(z="last", a="first", m="middle")
        key2 = w._get_cache_key(a="first", m="middle", z="last")
        assert key1 == key2

    def test_different_values_same_keys_differ(self):
        w = make_wrapper()
        key1 = w._get_cache_key(q="a")
        key2 = w._get_cache_key(q="b")
        assert key1 != key2

    def test_two_wrappers_same_names_same_key(self):
        w1 = make_wrapper(server_name="srv", original_name="tool")
        w2 = make_wrapper(server_name="srv", original_name="tool")
        assert w1._get_cache_key(q="x") == w2._get_cache_key(q="x")

    def test_two_wrappers_different_server_different_key(self):
        w1 = make_wrapper(server_name="srv1", original_name="tool")
        w2 = make_wrapper(server_name="srv2", original_name="tool")
        assert w1._get_cache_key(q="x") != w2._get_cache_key(q="x")

    def test_two_wrappers_different_tool_different_key(self):
        w1 = make_wrapper(server_name="srv", original_name="tool_a")
        w2 = make_wrapper(server_name="srv", original_name="tool_b")
        assert w1._get_cache_key(q="x") != w2._get_cache_key(q="x")

    def test_non_serializable_value_still_returns_32_char_hex(self):
        w = make_wrapper()

        class _Unserializable:
            def __str__(self):
                return "custom_repr"

        key = w._get_cache_key(obj=_Unserializable())
        assert isinstance(key, str)
        assert len(key) == 32

    def test_non_serializable_uses_default_str(self):
        """json.dumps with default=str converts the object via str(); key is stable."""
        w = make_wrapper(server_name="s", original_name="t")

        class _Fixed:
            def __str__(self):
                return "fixed_repr"

        key1 = w._get_cache_key(obj=_Fixed())
        key2 = w._get_cache_key(obj=_Fixed())
        assert key1 == key2

    def test_key_includes_tool_name(self):
        w1 = make_wrapper(server_name="s", original_name="alpha")
        w2 = make_wrapper(server_name="s", original_name="beta")
        # Same empty args, different names — keys must differ
        assert w1._get_cache_key() != w2._get_cache_key()

    def test_integer_and_float_kwargs(self):
        w = make_wrapper()
        key_int = w._get_cache_key(n=1)
        key_float = w._get_cache_key(n=1.0)
        # json.dumps serialises 1 and 1.0 differently, keys may differ
        assert isinstance(key_int, str) and len(key_int) == 32
        assert isinstance(key_float, str) and len(key_float) == 32

    def test_nested_dict_kwargs(self):
        w = make_wrapper()
        key = w._get_cache_key(config={"a": 1, "b": [2, 3]})
        assert len(key) == 32

    def test_list_kwargs(self):
        w = make_wrapper()
        key = w._get_cache_key(items=["x", "y", "z"])
        assert len(key) == 32

    def test_none_kwarg(self):
        w = make_wrapper()
        key = w._get_cache_key(val=None)
        assert len(key) == 32

    def test_matches_manual_md5_with_args(self):
        w = make_wrapper(server_name="srv", original_name="search")
        kwargs = {"q": "diabetes", "count": 5}
        args_str = json.dumps(kwargs, sort_keys=True, default=str)
        key_content = f"mcp_srv_search:{args_str}"
        expected = hashlib.md5(key_content.encode(), usedforsecurity=False).hexdigest()
        assert w._get_cache_key(**kwargs) == expected

    def test_bool_kwarg_serialised(self):
        w = make_wrapper()
        key = w._get_cache_key(flag=True)
        assert len(key) == 32

    def test_empty_string_kwarg(self):
        w = make_wrapper()
        key = w._get_cache_key(q="")
        assert len(key) == 32

    def test_unicode_kwarg(self):
        w = make_wrapper()
        key = w._get_cache_key(q="héllo wörld")
        assert len(key) == 32
