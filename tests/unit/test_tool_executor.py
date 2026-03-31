"""
Tests for ToolExecutor in src/ai/tools/tool_executor.py

Covers initialization (defaults), _record_execution (appends record,
correct keys, caps at 100), get_execution_history (copy semantics),
clear_history (empties list), and shutdown (no error).
No network, no Tkinter, no real tool calls.
"""

import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.tools.tool_executor import ToolExecutor
from ai.tools.base_tool import ToolResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _executor() -> ToolExecutor:
    return ToolExecutor()


def _ok_result() -> ToolResult:
    return ToolResult(success=True, output="ok")


def _fail_result(error="error msg") -> ToolResult:
    return ToolResult(success=False, output=None, error=error)


# ===========================================================================
# Initialization
# ===========================================================================

class TestInit:
    def test_execution_history_empty(self):
        te = _executor()
        assert te._execution_history == []

    def test_confirm_callback_default_none(self):
        te = ToolExecutor()
        assert te.confirm_callback is None

    def test_confirm_callback_stored(self):
        cb = lambda x: True
        te = ToolExecutor(confirm_callback=cb)
        assert te.confirm_callback is cb

    def test_timeout_seconds_is_int_or_float(self):
        te = _executor()
        assert isinstance(te.timeout_seconds, (int, float))

    def test_timeout_positive(self):
        te = _executor()
        assert te.timeout_seconds > 0

    def test_max_retries_non_negative(self):
        te = _executor()
        assert te.max_retries >= 0


# ===========================================================================
# _record_execution
# ===========================================================================

class TestRecordExecution:
    def test_appends_record(self):
        te = _executor()
        te._record_execution("my_tool", {}, _ok_result(), 0.1)
        assert len(te._execution_history) == 1

    def test_record_has_tool_name(self):
        te = _executor()
        te._record_execution("my_tool", {}, _ok_result(), 0.1)
        assert te._execution_history[0]["tool_name"] == "my_tool"

    def test_record_has_arguments(self):
        te = _executor()
        args = {"query": "diabetes"}
        te._record_execution("t", args, _ok_result(), 0.1)
        assert te._execution_history[0]["arguments"] == args

    def test_record_success_true_for_ok_result(self):
        te = _executor()
        te._record_execution("t", {}, _ok_result(), 0.0)
        assert te._execution_history[0]["success"] is True

    def test_record_success_false_for_fail_result(self):
        te = _executor()
        te._record_execution("t", {}, _fail_result(), 0.0)
        assert te._execution_history[0]["success"] is False

    def test_record_execution_time(self):
        te = _executor()
        te._record_execution("t", {}, _ok_result(), 1.23)
        assert te._execution_history[0]["execution_time"] == pytest.approx(1.23)

    def test_record_error_for_fail(self):
        te = _executor()
        te._record_execution("t", {}, _fail_result("oops"), 0.0)
        assert te._execution_history[0]["error"] == "oops"

    def test_record_error_none_for_success(self):
        te = _executor()
        te._record_execution("t", {}, _ok_result(), 0.0)
        assert te._execution_history[0]["error"] is None

    def test_record_has_timestamp(self):
        import time
        te = _executor()
        before = time.time()
        te._record_execution("t", {}, _ok_result(), 0.0)
        assert te._execution_history[0]["timestamp"] >= before

    def test_multiple_records_appended_in_order(self):
        te = _executor()
        te._record_execution("tool_a", {}, _ok_result(), 0.1)
        te._record_execution("tool_b", {}, _ok_result(), 0.2)
        assert te._execution_history[0]["tool_name"] == "tool_a"
        assert te._execution_history[1]["tool_name"] == "tool_b"

    def test_caps_at_100_entries(self):
        te = _executor()
        for i in range(110):
            te._record_execution(f"tool_{i}", {}, _ok_result(), 0.0)
        assert len(te._execution_history) == 100

    def test_oldest_pruned_when_over_100(self):
        te = _executor()
        for i in range(110):
            te._record_execution(f"tool_{i}", {}, _ok_result(), 0.0)
        # After capping, first entry should be tool_10 (first 10 pruned)
        assert te._execution_history[0]["tool_name"] == "tool_10"

    def test_exactly_100_entries_not_pruned(self):
        te = _executor()
        for i in range(100):
            te._record_execution(f"t{i}", {}, _ok_result(), 0.0)
        assert len(te._execution_history) == 100


# ===========================================================================
# get_execution_history
# ===========================================================================

class TestGetExecutionHistory:
    def test_returns_list(self):
        te = _executor()
        assert isinstance(te.get_execution_history(), list)

    def test_empty_when_no_executions(self):
        assert _executor().get_execution_history() == []

    def test_returns_copy_not_original(self):
        te = _executor()
        te._record_execution("t", {}, _ok_result(), 0.0)
        history = te.get_execution_history()
        history.append({"injected": True})
        assert len(te._execution_history) == 1  # Not modified

    def test_contains_all_recorded(self):
        te = _executor()
        te._record_execution("a", {}, _ok_result(), 0.1)
        te._record_execution("b", {}, _ok_result(), 0.2)
        history = te.get_execution_history()
        assert len(history) == 2


# ===========================================================================
# clear_history
# ===========================================================================

class TestClearHistory:
    def test_empties_history(self):
        te = _executor()
        te._record_execution("t", {}, _ok_result(), 0.0)
        te.clear_history()
        assert te._execution_history == []

    def test_get_history_returns_empty_after_clear(self):
        te = _executor()
        te._record_execution("t", {}, _ok_result(), 0.0)
        te.clear_history()
        assert te.get_execution_history() == []

    def test_clear_empty_history_no_error(self):
        te = _executor()
        te.clear_history()  # Should not raise

    def test_clear_twice_no_error(self):
        te = _executor()
        te.clear_history()
        te.clear_history()
        assert te.get_execution_history() == []


# ===========================================================================
# shutdown
# ===========================================================================

class TestShutdown:
    def test_shutdown_no_error(self):
        te = _executor()
        te.shutdown()  # Should not raise

    def test_shutdown_after_clear_no_error(self):
        te = _executor()
        te.clear_history()
        te.shutdown()
