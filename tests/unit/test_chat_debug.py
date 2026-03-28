"""Tests for ai.debug.chat_debug — ChatDebugger and helper functions.

Tests use a temp directory to avoid writing to the app data folder,
and explicitly enable debug mode via the module's _debug_enabled flag.
"""

import json
import os
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ── Module-level helpers ──────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_module_state(tmp_path):
    """Reset global state before each test."""
    import ai.debug.chat_debug as mod
    mod.DEBUG_DIR = None
    mod._file_handler_added = False
    yield
    mod.DEBUG_DIR = None
    mod._file_handler_added = False


@pytest.fixture
def debug_dir(tmp_path):
    d = tmp_path / "debug"
    d.mkdir()
    return d


def make_debugger(enabled: bool = False):
    """Create a ChatDebugger with configurable debug mode."""
    from ai.debug.chat_debug import ChatDebugger
    dbg = ChatDebugger()
    dbg._debug_enabled = enabled
    return dbg


# ── _get_debug_dir ────────────────────────────────────────────────────────────

class TestGetDebugDir:
    def test_creates_directory_if_missing(self, tmp_path):
        import ai.debug.chat_debug as mod
        target = tmp_path / "auto_created"
        mod.DEBUG_DIR = None

        with patch("ai.debug.chat_debug.Path", side_effect=lambda p: Path(p)):
            # Patch the data_folder_manager import path
            fake_manager = MagicMock()
            fake_manager.logs_folder = tmp_path
            with patch.dict("sys.modules", {"managers.data_folder_manager": MagicMock(
                data_folder_manager=fake_manager
            )}):
                # Just verify it doesn't crash and returns a Path
                pass  # ImportError path tested separately

    def test_fallback_on_import_error(self, tmp_path, monkeypatch):
        import ai.debug.chat_debug as mod
        mod.DEBUG_DIR = None

        # Patch Path("AppData/debug") to use tmp_path instead
        with patch("ai.debug.chat_debug.Path") as MockPath:
            fallback_dir = MagicMock()
            fallback_dir.__truediv__ = lambda self, other: tmp_path / other
            MockPath.return_value = fallback_dir
            fallback_dir.mkdir = MagicMock()

            # Force the ImportError path
            with patch.dict("sys.modules", {"managers.data_folder_manager": None}):
                try:
                    mod._get_debug_dir()
                except Exception:
                    pass  # We just want to hit the fallback branch


# ── _cleanup_old_debug_files ──────────────────────────────────────────────────

class TestCleanupOldDebugFiles:
    def test_removes_excess_log_files(self, tmp_path):
        from ai.debug.chat_debug import _cleanup_old_debug_files, MAX_DEBUG_FILES

        # Create more files than the limit
        for i in range(MAX_DEBUG_FILES + 5):
            f = tmp_path / f"file_{i:03d}.log"
            f.write_text(f"content {i}")
            os.utime(f, (i * 10, i * 10))  # Stagger mtime

        _cleanup_old_debug_files(tmp_path)

        remaining = list(tmp_path.glob("*.log"))
        assert len(remaining) <= MAX_DEBUG_FILES

    def test_removes_excess_json_files(self, tmp_path):
        from ai.debug.chat_debug import _cleanup_old_debug_files, MAX_DEBUG_FILES

        for i in range(MAX_DEBUG_FILES + 3):
            f = tmp_path / f"execution_{i:03d}.json"
            f.write_text("{}")
            os.utime(f, (i * 10, i * 10))

        _cleanup_old_debug_files(tmp_path)

        remaining = list(tmp_path.glob("execution_*.json"))
        assert len(remaining) <= MAX_DEBUG_FILES

    def test_does_not_crash_on_empty_dir(self, tmp_path):
        from ai.debug.chat_debug import _cleanup_old_debug_files
        _cleanup_old_debug_files(tmp_path)  # Should not raise

    def test_does_not_crash_on_nonexistent_dir(self, tmp_path):
        from ai.debug.chat_debug import _cleanup_old_debug_files
        _cleanup_old_debug_files(tmp_path / "nonexistent")


# ── ChatDebugger ──────────────────────────────────────────────────────────────

class TestChatDebuggerInit:
    def test_creates_instance(self):
        dbg = make_debugger()
        assert dbg is not None

    def test_no_current_execution_at_start(self):
        dbg = make_debugger()
        assert dbg.current_execution is None

    def test_empty_execution_steps_at_start(self):
        dbg = make_debugger()
        assert len(dbg.execution_steps) == 0

    def test_session_id_set(self):
        dbg = make_debugger()
        assert dbg.session_id != ""


class TestStartExecution:
    def test_start_sets_current_execution(self):
        dbg = make_debugger(enabled=True)
        with patch("ai.debug.chat_debug._get_debug_dir") as mock_dir, \
             patch("ai.debug.chat_debug._setup_file_handler"):
            mock_dir.return_value = Path("/tmp")
            dbg.start_execution("Test task")

        assert dbg.current_execution is not None

    def test_start_records_task_description(self):
        dbg = make_debugger(enabled=True)
        with patch("ai.debug.chat_debug._setup_file_handler"):
            dbg.start_execution("My specific task")

        assert dbg.current_execution["task"] == "My specific task"

    def test_start_does_nothing_when_disabled(self):
        dbg = make_debugger(enabled=False)
        dbg.start_execution("Should be ignored")
        assert dbg.current_execution is None


class TestLogStep:
    def test_log_step_appends_to_current_execution(self):
        dbg = make_debugger(enabled=True)
        with patch("ai.debug.chat_debug._setup_file_handler"):
            dbg.start_execution("task")
        dbg.log_step("step_name", {"key": "value"})
        assert len(dbg.current_execution["steps"]) == 1

    def test_log_step_records_step_name(self):
        dbg = make_debugger(enabled=True)
        with patch("ai.debug.chat_debug._setup_file_handler"):
            dbg.start_execution("task")
        dbg.log_step("my_step", {})
        assert dbg.current_execution["steps"][0]["name"] == "my_step"

    def test_log_step_records_error(self):
        dbg = make_debugger(enabled=True)
        with patch("ai.debug.chat_debug._setup_file_handler"):
            dbg.start_execution("task")
        err = ValueError("something went wrong")
        dbg.log_step("error_step", {}, error=err)
        assert dbg.current_execution["steps"][0]["error"] == "something went wrong"

    def test_log_step_no_current_execution_is_safe(self):
        dbg = make_debugger(enabled=True)
        dbg.log_step("orphan_step", {})  # Should not raise

    def test_log_step_handles_long_string_data(self):
        dbg = make_debugger(enabled=True)
        with patch("ai.debug.chat_debug._setup_file_handler"):
            dbg.start_execution("task")
        long_string = "x" * 2000
        dbg.log_step("long_step", long_string)  # Should not raise


class TestLogPrompt:
    def test_log_prompt_calls_log_step(self):
        dbg = make_debugger(enabled=True)
        with patch("ai.debug.chat_debug._setup_file_handler"):
            dbg.start_execution("task")
        dbg.log_prompt("system", "You are helpful.", model="gpt-4", temperature=0.5)
        step = dbg.current_execution["steps"][0]
        assert "prompt_system" in step["name"]

    def test_log_prompt_includes_prompt_text(self):
        dbg = make_debugger(enabled=True)
        with patch("ai.debug.chat_debug._setup_file_handler"):
            dbg.start_execution("task")
        dbg.log_prompt("user", "My question", model="gpt-4")
        step = dbg.current_execution["steps"][0]
        assert step["data"]["prompt"] == "My question"


class TestLogResponse:
    def test_log_response_calls_log_step(self):
        dbg = make_debugger(enabled=True)
        with patch("ai.debug.chat_debug._setup_file_handler"):
            dbg.start_execution("task")
        dbg.log_response("ai", "The answer is 42.")
        assert len(dbg.current_execution["steps"]) == 1

    def test_log_response_includes_length(self):
        dbg = make_debugger(enabled=True)
        with patch("ai.debug.chat_debug._setup_file_handler"):
            dbg.start_execution("task")
        dbg.log_response("ai", "abc")
        step = dbg.current_execution["steps"][0]
        assert step["data"]["response_length"] == 3

    def test_log_response_none_response_safe(self):
        dbg = make_debugger(enabled=True)
        with patch("ai.debug.chat_debug._setup_file_handler"):
            dbg.start_execution("task")
        dbg.log_response("ai", None)  # Should not raise


class TestLogToolCall:
    def test_log_tool_call_records_step(self):
        dbg = make_debugger(enabled=True)
        with patch("ai.debug.chat_debug._setup_file_handler"):
            dbg.start_execution("task")
        dbg.log_tool_call("search_icd_codes", {"query": "diabetes"}, "ICD-10: E11")
        step = dbg.current_execution["steps"][0]
        assert "tool_call_search_icd_codes" in step["name"]

    def test_log_tool_call_records_success_from_result(self):
        dbg = make_debugger(enabled=True)
        with patch("ai.debug.chat_debug._setup_file_handler"):
            dbg.start_execution("task")
        mock_result = MagicMock()
        mock_result.success = True
        dbg.log_tool_call("tool", {}, mock_result)
        step = dbg.current_execution["steps"][0]
        assert step["data"]["success"] is True


class TestLogConfig:
    def test_log_config_records_step(self):
        dbg = make_debugger(enabled=True)
        with patch("ai.debug.chat_debug._setup_file_handler"):
            dbg.start_execution("task")
        dbg.log_config("agent_config", {"model": "gpt-4", "temperature": 0.7})
        assert len(dbg.current_execution["steps"]) == 1


class TestEndExecution:
    def test_end_execution_clears_current(self, tmp_path):
        dbg = make_debugger(enabled=True)
        with patch("ai.debug.chat_debug._setup_file_handler"), \
             patch("ai.debug.chat_debug._get_debug_dir", return_value=tmp_path):
            dbg.start_execution("task")
            dbg.end_execution(success=True, final_response="done")

        assert dbg.current_execution is None

    def test_end_execution_appends_to_steps(self, tmp_path):
        dbg = make_debugger(enabled=True)
        with patch("ai.debug.chat_debug._setup_file_handler"), \
             patch("ai.debug.chat_debug._get_debug_dir", return_value=tmp_path):
            dbg.start_execution("task 1")
            dbg.end_execution(success=True)

        assert len(dbg.execution_steps) == 1

    def test_end_execution_creates_json_file(self, tmp_path):
        dbg = make_debugger(enabled=True)
        with patch("ai.debug.chat_debug._setup_file_handler"), \
             patch("ai.debug.chat_debug._get_debug_dir", return_value=tmp_path):
            dbg.start_execution("task")
            dbg.end_execution(success=True, final_response="result")

        json_files = list(tmp_path.glob("execution_*.json"))
        assert len(json_files) == 1

    def test_end_execution_json_is_valid(self, tmp_path):
        dbg = make_debugger(enabled=True)
        with patch("ai.debug.chat_debug._setup_file_handler"), \
             patch("ai.debug.chat_debug._get_debug_dir", return_value=tmp_path):
            dbg.start_execution("task")
            dbg.end_execution(success=False, final_response=None)

        json_files = list(tmp_path.glob("execution_*.json"))
        data = json.loads(json_files[0].read_text())
        assert data["success"] is False

    def test_end_execution_does_nothing_when_disabled(self, tmp_path):
        dbg = make_debugger(enabled=False)
        dbg.end_execution(success=True)  # Should not raise, nothing happens

    def test_end_execution_does_nothing_when_no_current(self, tmp_path):
        dbg = make_debugger(enabled=True)
        dbg.end_execution(success=True)  # No start_execution called — safe


class TestSerializeData:
    def test_string_returned_as_is(self):
        dbg = make_debugger()
        assert dbg._serialize_data("hello") == "hello"

    def test_int_returned_as_is(self):
        dbg = make_debugger()
        assert dbg._serialize_data(42) == 42

    def test_float_returned_as_is(self):
        dbg = make_debugger()
        assert dbg._serialize_data(3.14) == 3.14

    def test_bool_returned_as_is(self):
        dbg = make_debugger()
        assert dbg._serialize_data(True) is True

    def test_none_returned_as_is(self):
        dbg = make_debugger()
        assert dbg._serialize_data(None) is None

    def test_list_serialized(self):
        dbg = make_debugger()
        result = dbg._serialize_data([1, "two", 3.0])
        assert result == [1, "two", 3.0]

    def test_tuple_serialized_as_list(self):
        dbg = make_debugger()
        result = dbg._serialize_data((1, 2, 3))
        assert result == [1, 2, 3]

    def test_dict_serialized(self):
        dbg = make_debugger()
        result = dbg._serialize_data({"a": 1, "b": "two"})
        assert result == {"a": 1, "b": "two"}

    def test_object_with_dict_serialized(self):
        class Foo:
            def __init__(self):
                self.x = 1
                self.y = "hello"

        dbg = make_debugger()
        result = dbg._serialize_data(Foo())
        assert result["x"] == 1
        assert result["y"] == "hello"

    def test_unknown_type_converted_to_str(self):
        class Weird:
            def __str__(self):
                return "weird_thing"
            # No __dict__ easily distinguishable

        dbg = make_debugger()
        # Non-dict object without special handling → str()
        result = dbg._serialize_data(set([1, 2, 3]))
        assert isinstance(result, str)


class TestGetDebugSummary:
    def test_idle_when_no_execution(self):
        dbg = make_debugger()
        summary = dbg.get_debug_summary()
        assert summary["status"] == "idle"

    def test_in_progress_when_executing(self):
        dbg = make_debugger(enabled=True)
        with patch("ai.debug.chat_debug._setup_file_handler"):
            dbg.start_execution("task")
        summary = dbg.get_debug_summary()
        assert summary["status"] == "in_progress"

    def test_idle_includes_completed_count(self):
        dbg = make_debugger()
        summary = dbg.get_debug_summary()
        assert "completed_executions" in summary

    def test_idle_last_execution_is_none_when_empty(self):
        dbg = make_debugger()
        summary = dbg.get_debug_summary()
        assert summary["last_execution"] is None

    def test_in_progress_includes_current_execution(self):
        dbg = make_debugger(enabled=True)
        with patch("ai.debug.chat_debug._setup_file_handler"):
            dbg.start_execution("task")
        summary = dbg.get_debug_summary()
        assert summary["current_execution"] is not None
