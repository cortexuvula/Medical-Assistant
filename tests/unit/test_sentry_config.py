"""
Tests for src/utils/sentry_config.py

Covers _scrub_data, _before_send, _before_send_transaction, init_sentry,
and _get_release_version — all pure-logic except init_sentry which uses env vars.
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from utils.sentry_config import (
    _scrub_data,
    _before_send,
    _before_send_transaction,
    init_sentry,
    _get_release_version,
)

_SENTINEL = object()  # unique marker for "key was not in sys.modules"


# ===========================================================================
# _scrub_data
# ===========================================================================

class TestScrubData:
    def test_sensitive_field_replaced(self):
        from utils.structured_logging import SENSITIVE_FIELDS
        # Use a known sensitive field
        sensitive = next(iter(SENSITIVE_FIELDS))
        data = {sensitive: "real value"}
        result = _scrub_data(data)
        assert result[sensitive] == "[Filtered]"

    def test_non_sensitive_field_preserved(self):
        data = {"action": "view", "count": 5}
        result = _scrub_data(data)
        assert result["action"] == "view"
        assert result["count"] == 5

    def test_nested_dict_scrubbed(self):
        from utils.structured_logging import SENSITIVE_FIELDS
        sensitive = next(iter(SENSITIVE_FIELDS))
        data = {"outer": {sensitive: "secret"}}
        result = _scrub_data(data)
        assert result["outer"][sensitive] == "[Filtered]"

    def test_list_of_dicts_scrubbed(self):
        from utils.structured_logging import SENSITIVE_FIELDS
        sensitive = next(iter(SENSITIVE_FIELDS))
        data = {"items": [{sensitive: "secret"}, {"ok": "value"}]}
        result = _scrub_data(data)
        assert result["items"][0][sensitive] == "[Filtered]"
        assert result["items"][1]["ok"] == "value"

    def test_list_of_primitives_preserved(self):
        data = {"tags": ["python", "medical"]}
        result = _scrub_data(data)
        assert result["tags"] == ["python", "medical"]

    def test_long_string_truncated(self):
        long_text = "A" * 600
        data = {"description": long_text}
        result = _scrub_data(data)
        assert result["description"].endswith("...[truncated]")
        assert len(result["description"]) < len(long_text)

    def test_short_string_not_truncated(self):
        data = {"description": "short text"}
        result = _scrub_data(data)
        assert result["description"] == "short text"

    def test_exactly_500_chars_not_truncated(self):
        data = {"description": "x" * 500}
        result = _scrub_data(data)
        assert "...[truncated]" not in result["description"]

    def test_501_chars_truncated(self):
        data = {"description": "x" * 501}
        result = _scrub_data(data)
        assert "...[truncated]" in result["description"]

    def test_non_dict_input_returned_as_is(self):
        assert _scrub_data("string") == "string"
        assert _scrub_data(42) == 42
        assert _scrub_data(None) is None

    def test_empty_dict_returns_empty(self):
        assert _scrub_data({}) == {}

    def test_returns_new_dict_not_mutates(self):
        data = {"action": "test"}
        result = _scrub_data(data)
        assert result is not data

    def test_case_insensitive_key_matching(self):
        from utils.structured_logging import SENSITIVE_FIELDS
        # Fields in SENSITIVE_FIELDS are lowercase; test that uppercase key matches
        sensitive = next(iter(SENSITIVE_FIELDS))
        data = {sensitive.upper(): "value"}
        result = _scrub_data(data)
        assert result[sensitive.upper()] == "[Filtered]"

    def test_integer_value_preserved(self):
        data = {"count": 42}
        result = _scrub_data(data)
        assert result["count"] == 42

    def test_none_value_preserved(self):
        data = {"optional": None}
        result = _scrub_data(data)
        assert result["optional"] is None


# ===========================================================================
# _before_send
# ===========================================================================

class TestBeforeSend:
    def _make_event(self, **kwargs):
        return dict(**kwargs)

    def test_returns_event_unchanged_when_no_phi(self):
        event = {"message": "something happened", "level": "error"}
        result = _before_send(event, {})
        assert result is event

    def test_scrubs_exception_frame_vars(self):
        from utils.structured_logging import SENSITIVE_FIELDS
        sensitive = next(iter(SENSITIVE_FIELDS))
        event = {
            "exception": {
                "values": [
                    {
                        "stacktrace": {
                            "frames": [
                                {"vars": {sensitive: "secret_value", "ok": "fine"}}
                            ]
                        }
                    }
                ]
            }
        }
        result = _before_send(event, {})
        frame_vars = result["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"]
        assert frame_vars[sensitive] == "[Filtered]"
        assert frame_vars["ok"] == "fine"

    def test_exception_without_stacktrace_not_broken(self):
        event = {"exception": {"values": [{"type": "ValueError"}]}}
        result = _before_send(event, {})
        assert result == event

    def test_exception_without_vars_not_broken(self):
        event = {
            "exception": {
                "values": [
                    {"stacktrace": {"frames": [{"function": "foo"}]}}
                ]
            }
        }
        result = _before_send(event, {})
        assert result is event

    def test_scrubs_breadcrumb_data(self):
        from utils.structured_logging import SENSITIVE_FIELDS
        sensitive = next(iter(SENSITIVE_FIELDS))
        event = {
            "breadcrumbs": {
                "values": [
                    {"data": {sensitive: "secret"}, "message": "click"}
                ]
            }
        }
        result = _before_send(event, {})
        crumb = result["breadcrumbs"]["values"][0]
        assert crumb["data"][sensitive] == "[Filtered]"

    def test_truncates_long_breadcrumb_message(self):
        event = {
            "breadcrumbs": {
                "values": [
                    {"message": "A" * 600}
                ]
            }
        }
        result = _before_send(event, {})
        msg = result["breadcrumbs"]["values"][0]["message"]
        assert "...[truncated]" in msg

    def test_scrubs_extra_context(self):
        from utils.structured_logging import SENSITIVE_FIELDS
        sensitive = next(iter(SENSITIVE_FIELDS))
        event = {"extra": {sensitive: "private"}}
        result = _before_send(event, {})
        assert result["extra"][sensitive] == "[Filtered]"

    def test_scrubs_tags(self):
        from utils.structured_logging import SENSITIVE_FIELDS
        sensitive = next(iter(SENSITIVE_FIELDS))
        event = {"tags": {sensitive: "secret"}}
        result = _before_send(event, {})
        assert result["tags"][sensitive] == "[Filtered]"

    def test_scrubs_user_context(self):
        from utils.structured_logging import SENSITIVE_FIELDS
        sensitive = next(iter(SENSITIVE_FIELDS))
        event = {"user": {sensitive: "user_data"}}
        result = _before_send(event, {})
        assert result["user"][sensitive] == "[Filtered]"

    def test_event_with_no_known_sections_returned(self):
        event = {"level": "info", "platform": "python"}
        result = _before_send(event, {})
        assert result["level"] == "info"


# ===========================================================================
# _before_send_transaction
# ===========================================================================

class TestBeforeSendTransaction:
    def test_scrubs_tags(self):
        from utils.structured_logging import SENSITIVE_FIELDS
        sensitive = next(iter(SENSITIVE_FIELDS))
        event = {"tags": {sensitive: "secret"}, "type": "transaction"}
        result = _before_send_transaction(event, {})
        assert result["tags"][sensitive] == "[Filtered]"

    def test_scrubs_extra(self):
        from utils.structured_logging import SENSITIVE_FIELDS
        sensitive = next(iter(SENSITIVE_FIELDS))
        event = {"extra": {sensitive: "secret"}, "type": "transaction"}
        result = _before_send_transaction(event, {})
        assert result["extra"][sensitive] == "[Filtered]"

    def test_no_tags_or_extra_returns_unchanged(self):
        event = {"type": "transaction", "name": "GET /api/health"}
        result = _before_send_transaction(event, {})
        assert result["name"] == "GET /api/health"


# ===========================================================================
# init_sentry
# ===========================================================================

class TestInitSentry:
    def test_no_dsn_returns_false(self):
        with patch.dict(os.environ, {"SENTRY_DSN": ""}, clear=False):
            result = init_sentry()
        assert result is False

    def test_no_dsn_env_var_returns_false(self):
        env = {k: v for k, v in os.environ.items() if k != "SENTRY_DSN"}
        with patch.dict(os.environ, env, clear=True):
            result = init_sentry()
        assert result is False

    def test_whitespace_only_dsn_returns_false(self):
        with patch.dict(os.environ, {"SENTRY_DSN": "   "}):
            result = init_sentry()
        assert result is False

    @pytest.fixture(autouse=True)
    def _mock_sentry_env(self):
        """Ensure each test gets a clean sentry_sdk mock in sys.modules."""
        self.mock_sentry = MagicMock()
        # Save and restore any real sentry_sdk to avoid cross-test pollution
        saved = sys.modules.get("sentry_sdk", _SENTINEL)
        sys.modules["sentry_sdk"] = self.mock_sentry
        yield
        if saved is _SENTINEL:
            sys.modules.pop("sentry_sdk", None)
        else:
            sys.modules["sentry_sdk"] = saved

    def test_valid_dsn_initializes_sentry(self):
        with patch.dict(os.environ, {"SENTRY_DSN": "https://fake@sentry.io/123"}):
            result = init_sentry()
        assert result is True
        self.mock_sentry.init.assert_called_once()

    def test_sentry_not_installed_returns_false(self):
        sys.modules["sentry_sdk"] = None  # triggers ImportError on `import`
        with patch.dict(os.environ, {"SENTRY_DSN": "https://fake@sentry.io/123"}):
            result = init_sentry()
        assert result is False

    def test_sentry_init_exception_returns_false(self):
        self.mock_sentry.init.side_effect = Exception("init failed")
        with patch.dict(os.environ, {"SENTRY_DSN": "https://fake@sentry.io/123"}):
            result = init_sentry()
        assert result is False

    def test_environment_default(self):
        env = {k: v for k, v in os.environ.items() if k != "MEDICAL_ASSISTANT_ENV"}
        env["SENTRY_DSN"] = "https://fake@sentry.io/123"
        with patch.dict(os.environ, env, clear=True):
            init_sentry()
        call_kwargs = self.mock_sentry.init.call_args[1]
        assert call_kwargs["environment"] == "production"

    def test_environment_override(self):
        env = {"SENTRY_DSN": "https://fake@sentry.io/123", "MEDICAL_ASSISTANT_ENV": "staging"}
        with patch.dict(os.environ, env):
            init_sentry()
        call_kwargs = self.mock_sentry.init.call_args[1]
        assert call_kwargs["environment"] == "staging"

    def test_phi_protection_flags(self):
        with patch.dict(os.environ, {"SENTRY_DSN": "https://fake@sentry.io/123"}):
            init_sentry()
        call_kwargs = self.mock_sentry.init.call_args[1]
        assert call_kwargs["send_default_pii"] is False
        assert call_kwargs["before_send"] is _before_send
        assert call_kwargs["before_send_transaction"] is _before_send_transaction


# ===========================================================================
# _get_release_version
# ===========================================================================

class TestGetReleaseVersion:
    def test_returns_string(self):
        result = _get_release_version()
        assert isinstance(result, str)

    def test_contains_app_name(self):
        result = _get_release_version()
        assert "medical-assistant" in result

    def test_git_sha_used_when_available(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "abc1234\n"
        with patch("subprocess.run", return_value=mock_result):
            result = _get_release_version()
        assert "abc1234" in result

    def test_fallback_when_git_not_found(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = _get_release_version()
        assert result == "medical-assistant@unknown"

    def test_fallback_when_git_times_out(self):
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 5)):
            result = _get_release_version()
        assert result == "medical-assistant@unknown"

    def test_fallback_when_git_fails(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            result = _get_release_version()
        assert result == "medical-assistant@unknown"
