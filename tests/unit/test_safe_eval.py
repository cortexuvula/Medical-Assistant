"""
Tests for src/utils/safe_eval.py

Coverage:
- _safe_getattr: normal attrs, private attrs, missing attrs
- SafeExpressionEvaluator.DEFAULT_FUNCTIONS contents
- SafeExpressionEvaluator.__init__: _functions dict, extra_functions merging
- evaluate: empty/None expression returns default
- evaluate: boolean literals
- evaluate: comparison expressions with context
- evaluate: membership check "a in b"
- evaluate: numeric comparisons
- evaluate: string comparisons
- safe_eval convenience function
- get_safe_evaluator singleton behaviour
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from utils.safe_eval import (
    _safe_getattr,
    SafeExpressionEvaluator,
    get_safe_evaluator,
    safe_eval,
)

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _SimpleObj:
    """A minimal object used to test _safe_getattr."""
    public_attr = "hello"
    _private_attr = "secret"


# ---------------------------------------------------------------------------
# 1. _safe_getattr
# ---------------------------------------------------------------------------

class TestSafeGetattr:
    def test_returns_existing_public_attribute(self):
        obj = _SimpleObj()
        assert _safe_getattr(obj, "public_attr") == "hello"

    def test_returns_default_none_for_missing_attribute(self):
        obj = _SimpleObj()
        assert _safe_getattr(obj, "nonexistent") is None

    def test_returns_custom_default_for_missing_attribute(self):
        obj = _SimpleObj()
        assert _safe_getattr(obj, "nonexistent", "fallback") == "fallback"

    def test_raises_for_single_underscore_prefix(self):
        obj = _SimpleObj()
        with pytest.raises(AttributeError, match="private"):
            _safe_getattr(obj, "_private_attr")

    def test_raises_for_dunder_attribute(self):
        obj = _SimpleObj()
        with pytest.raises(AttributeError, match="private"):
            _safe_getattr(obj, "__class__")

    def test_raises_for_any_leading_underscore(self):
        obj = _SimpleObj()
        with pytest.raises(AttributeError):
            _safe_getattr(obj, "_anything")

    def test_works_on_builtin_type(self):
        result = _safe_getattr("hello", "upper")
        assert callable(result)

    def test_default_is_none_when_omitted(self):
        result = _safe_getattr(object(), "does_not_exist")
        assert result is None

    def test_raises_attribute_error_not_other_exception(self):
        with pytest.raises(AttributeError):
            _safe_getattr(42, "_hidden")

    def test_public_numeric_attribute_on_custom_class(self):
        class Obj:
            value = 42
        assert _safe_getattr(Obj(), "value") == 42

    def test_double_underscore_prefix_blocked(self):
        with pytest.raises(AttributeError):
            _safe_getattr(object(), "__dict__")


# ---------------------------------------------------------------------------
# 2. SafeExpressionEvaluator.DEFAULT_FUNCTIONS
# ---------------------------------------------------------------------------

class TestDefaultFunctions:
    def test_has_len(self):
        assert "len" in SafeExpressionEvaluator.DEFAULT_FUNCTIONS

    def test_has_str(self):
        assert "str" in SafeExpressionEvaluator.DEFAULT_FUNCTIONS

    def test_has_int(self):
        assert "int" in SafeExpressionEvaluator.DEFAULT_FUNCTIONS

    def test_has_float(self):
        assert "float" in SafeExpressionEvaluator.DEFAULT_FUNCTIONS

    def test_has_bool(self):
        assert "bool" in SafeExpressionEvaluator.DEFAULT_FUNCTIONS

    def test_has_abs(self):
        assert "abs" in SafeExpressionEvaluator.DEFAULT_FUNCTIONS

    def test_has_min(self):
        assert "min" in SafeExpressionEvaluator.DEFAULT_FUNCTIONS

    def test_has_max(self):
        assert "max" in SafeExpressionEvaluator.DEFAULT_FUNCTIONS

    def test_has_sum(self):
        assert "sum" in SafeExpressionEvaluator.DEFAULT_FUNCTIONS

    def test_has_any(self):
        assert "any" in SafeExpressionEvaluator.DEFAULT_FUNCTIONS

    def test_has_all(self):
        assert "all" in SafeExpressionEvaluator.DEFAULT_FUNCTIONS

    def test_has_round(self):
        assert "round" in SafeExpressionEvaluator.DEFAULT_FUNCTIONS

    def test_has_sorted(self):
        assert "sorted" in SafeExpressionEvaluator.DEFAULT_FUNCTIONS

    def test_has_isinstance(self):
        assert "isinstance" in SafeExpressionEvaluator.DEFAULT_FUNCTIONS

    def test_has_hasattr(self):
        assert "hasattr" in SafeExpressionEvaluator.DEFAULT_FUNCTIONS

    def test_len_maps_to_builtin_len(self):
        assert SafeExpressionEvaluator.DEFAULT_FUNCTIONS["len"] is len

    def test_getattr_maps_to_safe_getattr(self):
        assert SafeExpressionEvaluator.DEFAULT_FUNCTIONS["getattr"] is _safe_getattr

    def test_default_functions_is_a_dict(self):
        assert isinstance(SafeExpressionEvaluator.DEFAULT_FUNCTIONS, dict)


# ---------------------------------------------------------------------------
# 3. SafeExpressionEvaluator.__init__
# ---------------------------------------------------------------------------

class TestSafeExpressionEvaluatorInit:
    def test_creates_functions_dict(self):
        ev = SafeExpressionEvaluator()
        assert isinstance(ev._functions, dict)

    def test_functions_contains_default_keys(self):
        ev = SafeExpressionEvaluator()
        for key in ("len", "str", "int", "float", "bool"):
            assert key in ev._functions

    def test_extra_functions_merged(self):
        def my_func(x):
            return x * 2

        ev = SafeExpressionEvaluator(extra_functions={"double": my_func})
        assert "double" in ev._functions
        assert ev._functions["double"] is my_func

    def test_extra_functions_do_not_remove_defaults(self):
        ev = SafeExpressionEvaluator(extra_functions={"extra": lambda x: x})
        assert "len" in ev._functions

    def test_no_extra_functions_leaves_defaults_intact(self):
        ev = SafeExpressionEvaluator()
        assert ev._functions == SafeExpressionEvaluator.DEFAULT_FUNCTIONS

    def test_extra_functions_none_is_ignored(self):
        ev = SafeExpressionEvaluator(extra_functions=None)
        assert ev._functions == SafeExpressionEvaluator.DEFAULT_FUNCTIONS

    def test_extra_function_can_override_default(self):
        custom_len = lambda x: -1
        ev = SafeExpressionEvaluator(extra_functions={"len": custom_len})
        assert ev._functions["len"] is custom_len

    def test_default_functions_not_mutated_by_init(self):
        original_keys = set(SafeExpressionEvaluator.DEFAULT_FUNCTIONS.keys())
        SafeExpressionEvaluator(extra_functions={"brand_new": lambda: None})
        assert set(SafeExpressionEvaluator.DEFAULT_FUNCTIONS.keys()) == original_keys

    def test_multiple_extra_functions_all_merged(self):
        extras = {"fn_a": lambda: 1, "fn_b": lambda: 2}
        ev = SafeExpressionEvaluator(extra_functions=extras)
        assert "fn_a" in ev._functions
        assert "fn_b" in ev._functions


# ---------------------------------------------------------------------------
# 4. evaluate: empty / None expression returns default
# ---------------------------------------------------------------------------

class TestEvaluateEmptyExpression:
    def setup_method(self):
        self.ev = SafeExpressionEvaluator()

    def test_empty_string_returns_false_default(self):
        assert self.ev.evaluate("") is False

    def test_empty_string_returns_custom_default(self):
        assert self.ev.evaluate("", default="MISSING") == "MISSING"

    def test_none_expression_returns_false_default(self):
        assert self.ev.evaluate(None) is False

    def test_none_expression_returns_custom_default(self):
        assert self.ev.evaluate(None, default=42) == 42

    def test_whitespace_only_string_returns_default(self):
        # "   " is falsy in Python, so `if not expression` fires
        assert self.ev.evaluate("   ") is False

    def test_default_value_none_returned_as_none(self):
        assert self.ev.evaluate("", default=None) is None


# ---------------------------------------------------------------------------
# 5. evaluate: simple boolean literals
# ---------------------------------------------------------------------------

class TestEvaluateBooleanLiterals:
    def setup_method(self):
        self.ev = SafeExpressionEvaluator()

    def test_true_literal(self):
        assert self.ev.evaluate("True") is True

    def test_false_literal(self):
        assert self.ev.evaluate("False") is False

    def test_true_with_context(self):
        assert self.ev.evaluate("True", context={"x": 99}) is True

    def test_false_with_context(self):
        assert self.ev.evaluate("False", context={"x": 99}) is False

    def test_context_variable_truthy(self):
        assert self.ev.evaluate("enabled", context={"enabled": True}) is True

    def test_context_variable_falsy(self):
        assert not self.ev.evaluate("enabled", context={"enabled": False})


# ---------------------------------------------------------------------------
# 6. evaluate: comparison expressions
# ---------------------------------------------------------------------------

class TestEvaluateComparisons:
    def setup_method(self):
        self.ev = SafeExpressionEvaluator()

    def test_equal_int_true(self):
        assert self.ev.evaluate("x == 5", context={"x": 5}) is True

    def test_equal_int_false(self):
        assert self.ev.evaluate("x == 5", context={"x": 3}) is False

    def test_not_equal_true(self):
        assert self.ev.evaluate("x != 5", context={"x": 3}) is True

    def test_not_equal_false(self):
        assert self.ev.evaluate("x != 5", context={"x": 5}) is False

    def test_greater_than_true(self):
        assert self.ev.evaluate("count > 0", context={"count": 1}) is True

    def test_greater_than_false(self):
        assert self.ev.evaluate("count > 0", context={"count": 0}) is False

    def test_less_than_true(self):
        assert self.ev.evaluate("x < 10", context={"x": 5}) is True

    def test_less_than_false(self):
        assert self.ev.evaluate("x < 10", context={"x": 15}) is False

    def test_greater_than_or_equal_true(self):
        assert self.ev.evaluate("x >= 5", context={"x": 5}) is True

    def test_greater_than_or_equal_false(self):
        assert self.ev.evaluate("x >= 5", context={"x": 4}) is False

    def test_less_than_or_equal_true(self):
        assert self.ev.evaluate("x <= 5", context={"x": 5}) is True

    def test_less_than_or_equal_false(self):
        assert self.ev.evaluate("x <= 5", context={"x": 6}) is False

    def test_equal_string_true(self):
        result = self.ev.evaluate("status == 'active'", context={"status": "active"})
        assert result is True

    def test_equal_string_false(self):
        result = self.ev.evaluate("status == 'active'", context={"status": "inactive"})
        assert result is False


# ---------------------------------------------------------------------------
# 7. evaluate: membership check "a in b"
# ---------------------------------------------------------------------------

class TestEvaluateMembership:
    def setup_method(self):
        self.ev = SafeExpressionEvaluator()

    def test_string_in_list_true(self):
        result = self.ev.evaluate("'apple' in fruits", context={"fruits": ["apple", "banana"]})
        assert result is True

    def test_string_in_list_false(self):
        result = self.ev.evaluate("'mango' in fruits", context={"fruits": ["apple", "banana"]})
        assert result is False

    def test_string_in_string_true(self):
        result = self.ev.evaluate("'urgent' in text", context={"text": "This is urgent!"})
        assert result is True

    def test_string_in_string_false(self):
        result = self.ev.evaluate("'urgent' in text", context={"text": "Everything is fine"})
        assert result is False

    def test_key_in_dict_true(self):
        result = self.ev.evaluate("'name' in data", context={"data": {"name": "Alice"}})
        assert result is True

    def test_key_in_dict_false(self):
        result = self.ev.evaluate("'age' in data", context={"data": {"name": "Alice"}})
        assert result is False

    def test_integer_in_list_true(self):
        result = self.ev.evaluate("5 in nums", context={"nums": [1, 3, 5, 7]})
        assert result is True


# ---------------------------------------------------------------------------
# 8. evaluate: numeric comparisons
# ---------------------------------------------------------------------------

class TestEvaluateNumericComparisons:
    def setup_method(self):
        self.ev = SafeExpressionEvaluator()

    def test_count_greater_than_zero_true(self):
        assert self.ev.evaluate("count > 0", context={"count": 5}) is True

    def test_count_greater_than_zero_false(self):
        assert self.ev.evaluate("count > 0", context={"count": 0}) is False

    def test_negative_count_less_than_zero(self):
        assert self.ev.evaluate("count < 0", context={"count": -1}) is True

    def test_float_comparison_true(self):
        assert self.ev.evaluate("score >= 0.5", context={"score": 0.75}) is True

    def test_float_comparison_false(self):
        assert self.ev.evaluate("score >= 0.5", context={"score": 0.25}) is False

    def test_len_comparison_nonempty(self):
        assert self.ev.evaluate("len(items) > 0", context={"items": [1, 2, 3]}) is True

    def test_len_comparison_empty(self):
        assert self.ev.evaluate("len(items) > 0", context={"items": []}) is False

    def test_equality_at_boundary(self):
        assert self.ev.evaluate("x == 0", context={"x": 0}) is True


# ---------------------------------------------------------------------------
# 9. evaluate: string comparisons
# ---------------------------------------------------------------------------

class TestEvaluateStringComparisons:
    def setup_method(self):
        self.ev = SafeExpressionEvaluator()

    def test_status_active_true(self):
        result = self.ev.evaluate("status == 'active'", context={"status": "active"})
        assert result is True

    def test_status_active_false(self):
        result = self.ev.evaluate("status == 'active'", context={"status": "inactive"})
        assert result is False

    def test_status_not_equal_true(self):
        result = self.ev.evaluate("status != 'active'", context={"status": "pending"})
        assert result is True

    def test_status_not_equal_false(self):
        result = self.ev.evaluate("status != 'active'", context={"status": "active"})
        assert result is False

    def test_literal_on_left_side(self):
        result = self.ev.evaluate("'active' == status", context={"status": "active"})
        assert result is True

    def test_double_quoted_string_literal(self):
        result = self.ev.evaluate('status == "active"', context={"status": "active"})
        assert result is True


# ---------------------------------------------------------------------------
# 10. safe_eval convenience function: literals
# ---------------------------------------------------------------------------

class TestSafeEvalLiterals:
    def test_true_literal(self):
        assert safe_eval("True") is True

    def test_false_literal(self):
        assert safe_eval("False") is False

    def test_empty_expression_returns_default_false(self):
        assert safe_eval("") is False

    def test_empty_expression_returns_custom_default(self):
        assert safe_eval("", default="empty") == "empty"

    def test_none_expression_returns_default(self):
        assert safe_eval(None) is False

    def test_none_expression_returns_custom_default(self):
        assert safe_eval(None, default=99) == 99


# ---------------------------------------------------------------------------
# 11. safe_eval: comparison with context
# ---------------------------------------------------------------------------

class TestSafeEvalWithContext:
    def test_x_equals_5_true(self):
        assert safe_eval("x == 5", context={"x": 5}) is True

    def test_x_equals_5_false(self):
        assert safe_eval("x == 5", context={"x": 3}) is False

    def test_count_greater_than_zero(self):
        assert safe_eval("count > 0", context={"count": 10}) is True

    def test_status_active(self):
        assert safe_eval("status == 'active'", context={"status": "active"}) is True

    def test_membership_check(self):
        assert safe_eval("'error' in message", context={"message": "an error occurred"}) is True

    def test_len_check(self):
        assert safe_eval("len(items) > 0", context={"items": [1, 2, 3]}) is True

    def test_not_equal_with_context(self):
        assert safe_eval("x != 0", context={"x": 7}) is True

    def test_boolean_context_variable(self):
        assert safe_eval("flag", context={"flag": True}) is True


# ---------------------------------------------------------------------------
# 12. safe_eval: unknown / complex expression returns default
# ---------------------------------------------------------------------------

class TestSafeEvalUnknownExpression:
    def test_import_statement_blocked(self):
        result = safe_eval("import os", default=False)
        assert result is False

    def test_completely_invalid_expression_returns_default(self):
        result = safe_eval("@@@not valid@@@", default="INVALID")
        assert result == "INVALID"

    def test_undefined_variable_returns_default(self):
        result = safe_eval("undefined_var > 0", default=False)
        assert result is False

    def test_default_false_when_unspecified(self):
        result = safe_eval("totally_nonexistent_variable")
        assert result is False

    def test_custom_default_returned_on_failure(self):
        result = safe_eval("!!!bad!!!", default="NOPE")
        assert result == "NOPE"

    def test_custom_numeric_default_on_failure(self):
        result = safe_eval("@bad@", default=-1)
        assert result == -1


# ---------------------------------------------------------------------------
# 13. get_safe_evaluator: singleton behaviour
# ---------------------------------------------------------------------------

class TestGetSafeEvaluatorSingleton:
    def test_returns_safe_expression_evaluator_instance(self):
        ev = get_safe_evaluator()
        assert isinstance(ev, SafeExpressionEvaluator)

    def test_same_object_on_two_calls(self):
        ev1 = get_safe_evaluator()
        ev2 = get_safe_evaluator()
        assert ev1 is ev2

    def test_same_object_across_five_calls(self):
        instances = [get_safe_evaluator() for _ in range(5)]
        assert all(inst is instances[0] for inst in instances)

    def test_singleton_has_functions_dict(self):
        ev = get_safe_evaluator()
        assert hasattr(ev, "_functions")
        assert "len" in ev._functions

    def test_singleton_evaluates_true_literal(self):
        ev = get_safe_evaluator()
        assert ev.evaluate("True") is True

    def test_singleton_evaluates_comparison(self):
        ev = get_safe_evaluator()
        assert ev.evaluate("x == 1", context={"x": 1}) is True
