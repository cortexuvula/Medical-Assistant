"""Tests for safe expression evaluator."""

import unittest
from unittest.mock import patch

from utils.safe_eval import (
    SafeExpressionEvaluator,
    _safe_getattr,
    get_safe_evaluator,
    safe_eval,
)


class TestSafeGetattr(unittest.TestCase):
    """Tests for _safe_getattr."""

    def test_blocks_dunder(self):
        with self.assertRaises(AttributeError):
            _safe_getattr("hello", "__class__")

    def test_blocks_private(self):
        with self.assertRaises(AttributeError):
            _safe_getattr("hello", "_private")

    def test_allows_public(self):
        result = _safe_getattr("hello", "upper")
        self.assertTrue(callable(result))

    def test_returns_default(self):
        result = _safe_getattr("hello", "nonexistent", "default")
        self.assertEqual(result, "default")


class TestSafeExpressionEvaluatorInit(unittest.TestCase):
    """Tests for evaluator initialization."""

    def test_default_functions(self):
        evaluator = SafeExpressionEvaluator()
        self.assertIn("len", evaluator._functions)
        self.assertIn("str", evaluator._functions)
        self.assertIn("max", evaluator._functions)

    def test_extra_functions(self):
        evaluator = SafeExpressionEvaluator(extra_functions={"custom": abs})
        self.assertIn("custom", evaluator._functions)


class TestEvaluate(unittest.TestCase):
    """Tests for evaluate() method."""

    def setUp(self):
        self.evaluator = SafeExpressionEvaluator()

    def test_empty_expression(self):
        self.assertFalse(self.evaluator.evaluate(""))

    def test_none_expression(self):
        self.assertFalse(self.evaluator.evaluate(None))

    def test_simple_comparison(self):
        result = self.evaluator.evaluate("x == 5", {"x": 5})
        self.assertTrue(result)

    def test_simple_comparison_false(self):
        result = self.evaluator.evaluate("x == 5", {"x": 3})
        self.assertFalse(result)

    def test_greater_than(self):
        result = self.evaluator.evaluate("x > 3", {"x": 5})
        self.assertTrue(result)

    def test_less_than(self):
        result = self.evaluator.evaluate("x < 3", {"x": 1})
        self.assertTrue(result)

    def test_not_equal(self):
        result = self.evaluator.evaluate("x != 3", {"x": 5})
        self.assertTrue(result)

    def test_membership_check(self):
        result = self.evaluator.evaluate(
            "'hello' in items", {"items": ["hello", "world"]}
        )
        self.assertTrue(result)

    def test_membership_check_false(self):
        result = self.evaluator.evaluate(
            "'foo' in items", {"items": ["hello", "world"]}
        )
        self.assertFalse(result)

    def test_boolean_true(self):
        result = self.evaluator.evaluate("True")
        self.assertTrue(result)

    def test_boolean_false(self):
        result = self.evaluator.evaluate("False")
        self.assertFalse(result)

    def test_context_variable_boolean(self):
        result = self.evaluator.evaluate("enabled", {"enabled": True})
        self.assertTrue(result)

    def test_default_on_error(self):
        result = self.evaluator.evaluate("invalid!!!", default="fallback")
        self.assertEqual(result, "fallback")

    def test_string_literal_comparison(self):
        result = self.evaluator.evaluate("status == 'active'", {"status": "active"})
        self.assertTrue(result)

    def test_numeric_comparison(self):
        result = self.evaluator.evaluate("count >= 10", {"count": 15})
        self.assertTrue(result)

    def test_none_context(self):
        result = self.evaluator.evaluate("True", None)
        self.assertTrue(result)


class TestFallbackEvaluator(unittest.TestCase):
    """Tests for fallback evaluator (when simpleeval not available)."""

    def setUp(self):
        self.evaluator = SafeExpressionEvaluator()
        # Force fallback mode
        self.evaluator._evaluator = None

    def test_blocks_import(self):
        result = self.evaluator.evaluate("import os")
        self.assertFalse(result)

    def test_blocks_dunder(self):
        result = self.evaluator.evaluate("x.__class__")
        self.assertFalse(result)

    def test_simple_comparison_fallback(self):
        result = self.evaluator.evaluate("x == 5", {"x": 5})
        self.assertTrue(result)

    def test_membership_fallback(self):
        result = self.evaluator.evaluate(
            "'a' in items", {"items": ["a", "b"]}
        )
        self.assertTrue(result)

    def test_boolean_fallback(self):
        result = self.evaluator.evaluate("True")
        self.assertTrue(result)

    def test_complex_expression_returns_default(self):
        result = self.evaluator.evaluate("x + y * z", {"x": 1, "y": 2, "z": 3})
        self.assertFalse(result)

    def test_greater_equal(self):
        result = self.evaluator.evaluate("x >= 5", {"x": 5})
        self.assertTrue(result)

    def test_less_equal(self):
        result = self.evaluator.evaluate("x <= 3", {"x": 2})
        self.assertTrue(result)


class TestResolveValue(unittest.TestCase):
    """Tests for _resolve_value."""

    def setUp(self):
        self.evaluator = SafeExpressionEvaluator()

    def test_string_literal_single_quotes(self):
        result = self.evaluator._resolve_value("'hello'", {})
        self.assertEqual(result, "hello")

    def test_string_literal_double_quotes(self):
        result = self.evaluator._resolve_value('"world"', {})
        self.assertEqual(result, "world")

    def test_integer(self):
        result = self.evaluator._resolve_value("42", {})
        self.assertEqual(result, 42)

    def test_float(self):
        result = self.evaluator._resolve_value("3.14", {})
        self.assertAlmostEqual(result, 3.14)

    def test_true(self):
        self.assertTrue(self.evaluator._resolve_value("True", {}))

    def test_false(self):
        self.assertFalse(self.evaluator._resolve_value("False", {}))

    def test_none(self):
        self.assertIsNone(self.evaluator._resolve_value("None", {}))

    def test_context_variable(self):
        result = self.evaluator._resolve_value("x", {"x": 99})
        self.assertEqual(result, 99)

    def test_len_call(self):
        result = self.evaluator._resolve_value("len(items)", {"items": [1, 2, 3]})
        self.assertEqual(result, 3)

    def test_unknown_returns_string(self):
        result = self.evaluator._resolve_value("unknown", {})
        self.assertEqual(result, "unknown")


class TestGlobalFunctions(unittest.TestCase):
    """Tests for module-level convenience functions."""

    def test_get_safe_evaluator_singleton(self):
        e1 = get_safe_evaluator()
        e2 = get_safe_evaluator()
        self.assertIs(e1, e2)

    def test_safe_eval_convenience(self):
        result = safe_eval("x == 5", {"x": 5})
        self.assertTrue(result)

    def test_safe_eval_with_default(self):
        result = safe_eval("", default="fallback")
        self.assertEqual(result, "fallback")


if __name__ == '__main__':
    unittest.main()
