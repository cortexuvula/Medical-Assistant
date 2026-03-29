"""Tests for SafeExpressionEvaluator fallback methods and _safe_getattr."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

import pytest
from utils.safe_eval import SafeExpressionEvaluator, _safe_getattr


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fallback_evaluator():
    """Return a SafeExpressionEvaluator forced into fallback mode."""
    ev = SafeExpressionEvaluator()
    ev._evaluator = None  # Force fallback mode
    return ev


# ---------------------------------------------------------------------------
# TestSafeGetattr
# ---------------------------------------------------------------------------

class TestSafeGetattr:
    """Tests for the module-level _safe_getattr helper."""

    def test_returns_public_attribute(self):
        class Obj:
            value = 42
        assert _safe_getattr(Obj(), "value") == 42

    def test_raises_for_single_underscore_prefix(self):
        class Obj:
            _private = "secret"
        with pytest.raises(AttributeError):
            _safe_getattr(Obj(), "_private")

    def test_raises_for_dunder_attribute(self):
        class Obj:
            pass
        with pytest.raises(AttributeError):
            _safe_getattr(Obj(), "__dunder__")

    def test_missing_attribute_returns_none_by_default(self):
        class Obj:
            pass
        assert _safe_getattr(Obj(), "missing") is None

    def test_missing_attribute_returns_explicit_default(self):
        class Obj:
            pass
        assert _safe_getattr(Obj(), "missing", "fallback") == "fallback"

    def test_works_on_dict_returns_method(self):
        d = {"a": 1}
        result = _safe_getattr(d, "keys")
        assert callable(result)
        assert list(result()) == ["a"]


# ---------------------------------------------------------------------------
# TestIsSimpleMembershipCheck
# ---------------------------------------------------------------------------

class TestIsSimpleMembershipCheck:
    """Tests for SafeExpressionEvaluator._is_simple_membership_check."""

    def setup_method(self):
        self.ev = _make_fallback_evaluator()
        self.ctx = {}

    def test_simple_in_expression(self):
        assert self.ev._is_simple_membership_check("x in items", self.ctx) is True

    def test_false_when_and_present(self):
        assert self.ev._is_simple_membership_check("x in items and y", self.ctx) is False

    def test_false_when_or_present(self):
        assert self.ev._is_simple_membership_check("x in items or y", self.ctx) is False

    def test_false_when_no_in(self):
        assert self.ev._is_simple_membership_check("x == y", self.ctx) is False

    def test_string_literal_key_in_data(self):
        assert self.ev._is_simple_membership_check("'key' in data", self.ctx) is True


# ---------------------------------------------------------------------------
# TestEvalSimpleMembership
# ---------------------------------------------------------------------------

class TestEvalSimpleMembership:
    """Tests for SafeExpressionEvaluator._eval_simple_membership."""

    def setup_method(self):
        self.ev = _make_fallback_evaluator()

    def test_string_literal_needle_in_list_true(self):
        ctx = {"items": ["hello", "world"]}
        assert self.ev._eval_simple_membership("'hello' in items", ctx) is True

    def test_string_literal_needle_not_in_list(self):
        ctx = {"items": ["hello"]}
        assert self.ev._eval_simple_membership("'bye' in items", ctx) is False

    def test_context_variable_needle_in_dict(self):
        ctx = {"key": "x", "data": {"x": 1}}
        assert self.ev._eval_simple_membership("key in data", ctx) is True

    def test_context_variable_haystack_missing_returns_false(self):
        ctx = {"key": "x"}
        assert self.ev._eval_simple_membership("key in data", ctx) is False

    def test_string_literal_needle_missing_haystack_returns_false(self):
        ctx = {}
        assert self.ev._eval_simple_membership("'item' in missing_key", ctx) is False


# ---------------------------------------------------------------------------
# TestIsSimpleComparison
# ---------------------------------------------------------------------------

class TestIsSimpleComparison:
    """Tests for SafeExpressionEvaluator._is_simple_comparison."""

    def setup_method(self):
        self.ev = _make_fallback_evaluator()
        self.ctx = {}

    def test_equality_operator(self):
        assert self.ev._is_simple_comparison("x == 5", self.ctx) is True

    def test_not_equal_operator(self):
        assert self.ev._is_simple_comparison("x != 0", self.ctx) is True

    def test_greater_equal_operator(self):
        assert self.ev._is_simple_comparison("x >= 3", self.ctx) is True

    def test_in_operator_no_comparison(self):
        # "x in items" contains no comparison operator
        assert self.ev._is_simple_comparison("x in items", self.ctx) is False

    def test_plain_boolean_no_comparison(self):
        assert self.ev._is_simple_comparison("True", self.ctx) is False


# ---------------------------------------------------------------------------
# TestEvalSimpleComparison
# ---------------------------------------------------------------------------

class TestEvalSimpleComparison:
    """Tests for SafeExpressionEvaluator._eval_simple_comparison."""

    def setup_method(self):
        self.ev = _make_fallback_evaluator()

    def test_equal_true(self):
        assert self.ev._eval_simple_comparison("x == 5", {"x": 5}) is True

    def test_equal_false(self):
        assert self.ev._eval_simple_comparison("x == 5", {"x": 3}) is False

    def test_not_equal_true(self):
        assert self.ev._eval_simple_comparison("x != 3", {"x": 5}) is True

    def test_greater_than_true(self):
        assert self.ev._eval_simple_comparison("x > 3", {"x": 5}) is True

    def test_less_than_false(self):
        assert self.ev._eval_simple_comparison("x < 3", {"x": 5}) is False

    def test_greater_equal_true(self):
        assert self.ev._eval_simple_comparison("x >= 5", {"x": 5}) is True

    def test_less_equal_false(self):
        assert self.ev._eval_simple_comparison("x <= 4", {"x": 5}) is False

    def test_float_literals_equal(self):
        assert self.ev._eval_simple_comparison("3.14 == 3.14", {}) is True

    def test_string_literal_equal_true(self):
        assert self.ev._eval_simple_comparison("'hello' == 'hello'", {}) is True

    def test_string_literal_equal_false(self):
        assert self.ev._eval_simple_comparison("'hello' == 'world'", {}) is False


# ---------------------------------------------------------------------------
# TestIsSimpleBoolean
# ---------------------------------------------------------------------------

class TestIsSimpleBoolean:
    """Tests for SafeExpressionEvaluator._is_simple_boolean."""

    def setup_method(self):
        self.ev = _make_fallback_evaluator()

    def test_lowercase_true(self):
        assert self.ev._is_simple_boolean("true", {}) is True

    def test_lowercase_false(self):
        assert self.ev._is_simple_boolean("false", {}) is True

    def test_titlecase_true(self):
        assert self.ev._is_simple_boolean("True", {}) is True

    def test_titlecase_false(self):
        assert self.ev._is_simple_boolean("False", {}) is True

    def test_context_key_present(self):
        assert self.ev._is_simple_boolean("my_flag", {"my_flag": True}) is True

    def test_unknown_key_not_in_context(self):
        assert self.ev._is_simple_boolean("unknown", {}) is False

    def test_comparison_expression_is_not_simple_boolean(self):
        assert self.ev._is_simple_boolean("x == y", {}) is False


# ---------------------------------------------------------------------------
# TestEvalSimpleBoolean
# ---------------------------------------------------------------------------

class TestEvalSimpleBoolean:
    """Tests for SafeExpressionEvaluator._eval_simple_boolean."""

    def setup_method(self):
        self.ev = _make_fallback_evaluator()

    def test_lowercase_true(self):
        assert self.ev._eval_simple_boolean("true", {}) is True

    def test_lowercase_false(self):
        assert self.ev._eval_simple_boolean("false", {}) is False

    def test_titlecase_true(self):
        assert self.ev._eval_simple_boolean("True", {}) is True

    def test_titlecase_false(self):
        assert self.ev._eval_simple_boolean("False", {}) is False

    def test_context_flag_truthy(self):
        assert self.ev._eval_simple_boolean("my_flag", {"my_flag": True}) is True

    def test_context_flag_falsy(self):
        assert self.ev._eval_simple_boolean("my_flag", {"my_flag": 0}) is False

    def test_unknown_key_returns_false(self):
        assert self.ev._eval_simple_boolean("unknown", {}) is False


# ---------------------------------------------------------------------------
# TestEvaluateFallback
# ---------------------------------------------------------------------------

class TestEvaluateFallback:
    """Tests for SafeExpressionEvaluator._evaluate_fallback."""

    def setup_method(self):
        self.ev = _make_fallback_evaluator()

    def test_blocks_import_keyword(self):
        assert self.ev._evaluate_fallback("import os", {}, "DEFAULT") == "DEFAULT"

    def test_blocks_dunder_pattern(self):
        assert self.ev._evaluate_fallback("__builtins__", {}, "DEFAULT") == "DEFAULT"

    def test_blocks_exec_keyword(self):
        assert self.ev._evaluate_fallback("exec('x')", {}, "DEFAULT") == "DEFAULT"

    def test_simple_boolean_true(self):
        result = self.ev._evaluate_fallback("true", {}, False)
        assert result is True

    def test_simple_comparison_equal(self):
        result = self.ev._evaluate_fallback("x == 5", {"x": 5}, False)
        assert result is True

    def test_membership_check(self):
        result = self.ev._evaluate_fallback(
            "x in items", {"x": "a", "items": ["a", "b"]}, False
        )
        assert result is True

    def test_complex_expression_returns_default(self):
        # An expression using 'and' with no comparison/membership/boolean
        # operators that the fallback recognises — hits the "too complex" path.
        result = self.ev._evaluate_fallback(
            "x and y",
            {"x": True, "y": True},
            "DEFAULT",
        )
        assert result == "DEFAULT"

    def test_empty_string_returns_default(self):
        # Empty string won't match any simple pattern
        result = self.ev._evaluate_fallback("", {}, "DEFAULT")
        assert result == "DEFAULT"


# ---------------------------------------------------------------------------
# TestEvaluate
# ---------------------------------------------------------------------------

class TestEvaluate:
    """Tests for SafeExpressionEvaluator.evaluate (public API)."""

    def test_empty_string_returns_default_false(self):
        ev = SafeExpressionEvaluator()
        assert ev.evaluate("") is False

    def test_empty_string_returns_custom_default(self):
        ev = SafeExpressionEvaluator()
        assert ev.evaluate("", default="CUSTOM") == "CUSTOM"

    def test_fallback_true_literal(self):
        ev = _make_fallback_evaluator()
        assert ev.evaluate("true", {}, False) is True

    def test_evaluate_returns_default_on_dangerous_expression(self):
        ev = _make_fallback_evaluator()
        result = ev.evaluate("import os", {}, "SAFE")
        assert result == "SAFE"

    def test_evaluate_context_none_treated_as_empty(self):
        ev = _make_fallback_evaluator()
        result = ev.evaluate("true", None, False)
        assert result is True

    def test_evaluate_comparison_via_public_api(self):
        ev = _make_fallback_evaluator()
        assert ev.evaluate("x == 10", {"x": 10}, False) is True

    def test_evaluate_membership_via_public_api(self):
        ev = _make_fallback_evaluator()
        ctx = {"needle": "a", "haystack": ["a", "b", "c"]}
        assert ev.evaluate("needle in haystack", ctx, False) is True
