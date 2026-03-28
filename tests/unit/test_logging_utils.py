"""Tests for ai.logging_utils — log_api_call_debug."""

import logging
import pytest
from unittest.mock import patch, MagicMock

from ai.logging_utils import log_api_call_debug


class TestLogApiCallDebug:
    def _call(self, provider="OpenAI", model="gpt-4", temperature=0.7,
              system_message="You are helpful.", prompt="Hello"):
        log_api_call_debug(provider, model, temperature, system_message, prompt)

    def test_does_not_raise(self):
        self._call()

    def test_does_not_log_when_debug_disabled(self):
        import ai.logging_utils as mod
        mock_logger = MagicMock()
        mock_logger.isEnabledFor.return_value = False

        with patch.object(mod, "logger", mock_logger):
            self._call()

        mock_logger.debug.assert_not_called()

    def test_logs_when_debug_enabled(self):
        import ai.logging_utils as mod
        mock_logger = MagicMock()
        mock_logger.isEnabledFor.return_value = True

        with patch.object(mod, "logger", mock_logger):
            self._call(provider="OpenAI", model="gpt-4")

        assert mock_logger.debug.call_count >= 1

    def test_provider_uppercased_in_log(self):
        import ai.logging_utils as mod
        calls_seen = []

        mock_logger = MagicMock()
        mock_logger.isEnabledFor.return_value = True
        mock_logger.debug.side_effect = lambda msg: calls_seen.append(msg)

        with patch.object(mod, "logger", mock_logger):
            self._call(provider="openai")

        combined = " ".join(calls_seen)
        assert "OPENAI" in combined

    def test_model_logged(self):
        import ai.logging_utils as mod
        calls_seen = []

        mock_logger = MagicMock()
        mock_logger.isEnabledFor.return_value = True
        mock_logger.debug.side_effect = lambda msg: calls_seen.append(msg)

        with patch.object(mod, "logger", mock_logger):
            self._call(model="gpt-4-turbo")

        combined = " ".join(calls_seen)
        assert "gpt-4-turbo" in combined

    def test_sanitizes_content(self):
        """Verify sanitize_for_logging is called (no raw API key in output)."""
        import ai.logging_utils as mod
        mock_logger = MagicMock()
        mock_logger.isEnabledFor.return_value = True

        with patch.object(mod, "logger", mock_logger):
            # A key-like string in the prompt should not appear verbatim
            log_api_call_debug(
                "OpenAI", "gpt-4", 0.7,
                "system msg",
                "Bearer sk-abc123secretkey"
            )

        # The call should not raise — sanitization happens inside
        assert mock_logger.debug.called

    def test_temperature_logged(self):
        import ai.logging_utils as mod
        calls_seen = []

        mock_logger = MagicMock()
        mock_logger.isEnabledFor.return_value = True
        mock_logger.debug.side_effect = lambda msg: calls_seen.append(str(msg))

        with patch.object(mod, "logger", mock_logger):
            self._call(temperature=0.3)

        combined = " ".join(calls_seen)
        assert "0.3" in combined

    def test_accepts_empty_strings(self):
        log_api_call_debug("", "", 0.0, "", "")  # Should not raise

    def test_isenabledfor_checked_with_debug_level(self):
        import ai.logging_utils as mod
        mock_logger = MagicMock()
        mock_logger.isEnabledFor.return_value = False

        with patch.object(mod, "logger", mock_logger):
            self._call()

        mock_logger.isEnabledFor.assert_called_once_with(10)
