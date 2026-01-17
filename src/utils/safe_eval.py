"""
Safe Expression Evaluator Module

Provides a secure alternative to Python's eval() function for evaluating
condition expressions in agent chains and sub-agent configurations.

Uses the simpleeval library which restricts available operations and
prevents access to dangerous Python features.
"""

from typing import Any, Dict, Optional

try:
    from simpleeval import SimpleEval, EvalWithCompoundTypes
except ImportError:
    SimpleEval = None
    EvalWithCompoundTypes = None

from utils.structured_logging import get_logger

logger = get_logger(__name__)


def _safe_getattr(obj: Any, name: str, default: Any = None) -> Any:
    """
    Safe getattr that blocks access to dunder attributes.

    Args:
        obj: Object to get attribute from
        name: Attribute name
        default: Default value if attribute doesn't exist

    Returns:
        Attribute value or default
    """
    if name.startswith('_'):
        raise AttributeError(f"Access to private attribute '{name}' is not allowed")
    return getattr(obj, name, default)


class SafeExpressionEvaluator:
    """
    Safe expression evaluator that restricts available operations.

    This class provides a secure way to evaluate condition expressions
    without the security risks of Python's built-in eval() function.

    Supported operations:
    - Comparison operators: ==, !=, <, >, <=, >=
    - Boolean operators: and, or, not
    - Membership: in, not in
    - Attribute access on allowed objects
    - Function calls to whitelisted functions
    - Basic arithmetic: +, -, *, /, //, %

    Explicitly blocked:
    - Import statements
    - Access to __builtins__, __globals__, etc.
    - Code execution functions (exec, eval, compile)
    - File operations
    - Network operations
    """

    # Default safe functions available in expressions
    DEFAULT_FUNCTIONS = {
        'len': len,
        'str': str,
        'int': int,
        'float': float,
        'bool': bool,
        'abs': abs,
        'min': min,
        'max': max,
        'sum': sum,
        'any': any,
        'all': all,
        'round': round,
        'sorted': sorted,
        'list': list,
        'dict': dict,
        'tuple': tuple,
        'set': set,
        'isinstance': isinstance,
        'hasattr': hasattr,
        'getattr': _safe_getattr,
    }

    def __init__(self, extra_functions: Optional[Dict[str, callable]] = None):
        """
        Initialize the safe evaluator.

        Args:
            extra_functions: Additional functions to make available in expressions
        """
        self._evaluator = None
        self._functions = self.DEFAULT_FUNCTIONS.copy()

        if extra_functions:
            self._functions.update(extra_functions)

        self._initialize_evaluator()

    def _initialize_evaluator(self):
        """Initialize the simpleeval evaluator with safe defaults."""
        if EvalWithCompoundTypes is None:
            logger.warning(
                "simpleeval not installed. Safe evaluation will use fallback mode. "
                "Install with: pip install simpleeval"
            )
            return

        self._evaluator = EvalWithCompoundTypes()
        self._evaluator.functions.update(self._functions)

    def evaluate(
        self,
        expression: str,
        context: Optional[Dict[str, Any]] = None,
        default: Any = False
    ) -> Any:
        """
        Safely evaluate an expression.

        Args:
            expression: The expression to evaluate
            context: Variables available in the expression
            default: Default value to return on error

        Returns:
            The result of evaluating the expression, or default on error
        """
        if not expression:
            return default

        context = context or {}

        # Use simpleeval if available
        if self._evaluator is not None:
            return self._evaluate_with_simpleeval(expression, context, default)

        # Fallback to restricted evaluation
        return self._evaluate_fallback(expression, context, default)

    def _evaluate_with_simpleeval(
        self,
        expression: str,
        context: Dict[str, Any],
        default: Any
    ) -> Any:
        """Evaluate using simpleeval library."""
        try:
            self._evaluator.names = context
            result = self._evaluator.eval(expression)
            return result
        except Exception as e:
            logger.warning(f"Failed to evaluate expression '{expression}': {e}")
            return default

    def _evaluate_fallback(
        self,
        expression: str,
        context: Dict[str, Any],
        default: Any
    ) -> Any:
        """
        Fallback evaluation with strict restrictions.

        Only supports a very limited set of safe expressions when
        simpleeval is not available.
        """
        try:
            # Only allow very simple comparisons as fallback
            # This is much more restrictive than simpleeval

            # Check for dangerous patterns
            dangerous_patterns = [
                '__', 'import', 'exec', 'eval', 'compile', 'open',
                'file', 'input', 'globals', 'locals', 'vars',
                'getattr', 'setattr', 'delattr', 'dir',
                'lambda', 'class', 'def',
            ]

            expr_lower = expression.lower()
            for pattern in dangerous_patterns:
                if pattern in expr_lower:
                    logger.warning(f"Blocked dangerous pattern '{pattern}' in expression")
                    return default

            # Only allow specific simple patterns
            # Pattern: "key in context" or "key == value" style
            if self._is_simple_membership_check(expression, context):
                return self._eval_simple_membership(expression, context)

            if self._is_simple_comparison(expression, context):
                return self._eval_simple_comparison(expression, context)

            if self._is_simple_boolean(expression, context):
                return self._eval_simple_boolean(expression, context)

            logger.warning(
                f"Expression '{expression}' too complex for fallback evaluator. "
                "Install simpleeval for full expression support."
            )
            return default

        except Exception as e:
            logger.warning(f"Fallback evaluation failed for '{expression}': {e}")
            return default

    def _is_simple_membership_check(self, expression: str, context: Dict[str, Any]) -> bool:
        """Check if expression is a simple 'x in y' membership test."""
        return ' in ' in expression and ' and ' not in expression and ' or ' not in expression

    def _eval_simple_membership(self, expression: str, context: Dict[str, Any]) -> bool:
        """Evaluate simple membership check."""
        parts = expression.split(' in ', 1)
        if len(parts) != 2:
            return False

        needle = parts[0].strip().strip("'\"")
        haystack_key = parts[1].strip()

        # Check if needle is a string literal or a context variable
        if needle.startswith("'") or needle.startswith('"'):
            needle = needle.strip("'\"")
        elif needle in context:
            needle = context[needle]

        # Get the haystack from context
        if haystack_key in context:
            haystack = context[haystack_key]
        else:
            return False

        return needle in haystack if hasattr(haystack, '__contains__') else False

    def _is_simple_comparison(self, expression: str, context: Dict[str, Any]) -> bool:
        """Check if expression is a simple comparison."""
        operators = ['==', '!=', '>=', '<=', '>', '<']
        return any(op in expression for op in operators)

    def _eval_simple_comparison(self, expression: str, context: Dict[str, Any]) -> bool:
        """Evaluate simple comparison."""
        operators = [('>=', lambda a, b: a >= b),
                     ('<=', lambda a, b: a <= b),
                     ('!=', lambda a, b: a != b),
                     ('==', lambda a, b: a == b),
                     ('>', lambda a, b: a > b),
                     ('<', lambda a, b: a < b)]

        for op_str, op_func in operators:
            if op_str in expression:
                parts = expression.split(op_str, 1)
                if len(parts) == 2:
                    left = self._resolve_value(parts[0].strip(), context)
                    right = self._resolve_value(parts[1].strip(), context)
                    return op_func(left, right)
        return False

    def _is_simple_boolean(self, expression: str, context: Dict[str, Any]) -> bool:
        """Check if expression is a simple boolean value."""
        return expression.strip().lower() in ('true', 'false') or expression.strip() in context

    def _eval_simple_boolean(self, expression: str, context: Dict[str, Any]) -> bool:
        """Evaluate simple boolean."""
        expr = expression.strip()
        if expr.lower() == 'true':
            return True
        if expr.lower() == 'false':
            return False
        if expr in context:
            return bool(context[expr])
        return False

    def _resolve_value(self, value_str: str, context: Dict[str, Any]) -> Any:
        """Resolve a value string to its actual value."""
        value_str = value_str.strip()

        # Check for string literals
        if (value_str.startswith("'") and value_str.endswith("'")) or \
           (value_str.startswith('"') and value_str.endswith('"')):
            return value_str[1:-1]

        # Check for numeric literals
        try:
            if '.' in value_str:
                return float(value_str)
            return int(value_str)
        except ValueError:
            pass

        # Check for boolean literals
        if value_str.lower() == 'true':
            return True
        if value_str.lower() == 'false':
            return False
        if value_str.lower() == 'none':
            return None

        # Check for context variables
        if value_str in context:
            return context[value_str]

        # Handle len() calls
        if value_str.startswith('len(') and value_str.endswith(')'):
            inner = value_str[4:-1].strip()
            if inner in context:
                return len(context[inner])

        return value_str


# Global evaluator instance for convenience
_evaluator = None


def get_safe_evaluator() -> SafeExpressionEvaluator:
    """Get the global safe evaluator instance."""
    global _evaluator
    if _evaluator is None:
        _evaluator = SafeExpressionEvaluator()
    return _evaluator


def safe_eval(
    expression: str,
    context: Optional[Dict[str, Any]] = None,
    default: Any = False
) -> Any:
    """
    Convenience function for safe expression evaluation.

    Args:
        expression: The expression to evaluate
        context: Variables available in the expression
        default: Default value to return on error

    Returns:
        The result of evaluating the expression, or default on error

    Example:
        >>> safe_eval("len(items) > 0", {"items": [1, 2, 3]})
        True
        >>> safe_eval("status == 'active'", {"status": "active"})
        True
        >>> safe_eval("'urgent' in text", {"text": "This is urgent!"})
        True
    """
    return get_safe_evaluator().evaluate(expression, context, default)
