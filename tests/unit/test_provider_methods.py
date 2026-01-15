#!/usr/bin/env python3
"""
Tests for provider methods in the MedicalDictationApp.

This module tests the _get_available_providers method which was
refactored from two duplicate methods into a single generic implementation.

Note: These tests require importing MedicalDictationApp which may fail
in some CI environments due to tkinter/display dependencies.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest

# Try to import the required modules - skip tests if import fails
try:
    import utils.security as security_module
    from core.app import MedicalDictationApp
    IMPORTS_AVAILABLE = True
except (ImportError, AssertionError, Exception) as e:
    IMPORTS_AVAILABLE = False
    IMPORT_ERROR = str(e)
    security_module = None  # Placeholder to avoid NameError


def create_mock_app():
    """Create a minimal mock app instance without full initialization."""
    if IMPORTS_AVAILABLE:
        return object.__new__(MedicalDictationApp)
    return None


# Skip all tests if imports failed
pytestmark = pytest.mark.skipif(
    not IMPORTS_AVAILABLE,
    reason=f"Could not import required modules for provider tests"
)


class TestProviderMethods:
    """Test provider availability methods."""

    def test_get_available_providers_ai_with_keys(self):
        """Test AI providers returned when API keys exist."""
        mock_security_mgr = Mock()
        mock_security_mgr.get_api_key.side_effect = lambda key: {
            "openai": "sk-test-key",
            "anthropic": "sk-ant-test",
            "gemini": None,
        }.get(key)

        app = create_mock_app()

        with patch.object(security_module, 'get_security_manager', return_value=mock_security_mgr):
            keys, names = app._get_available_providers("ai")

        assert "openai" in keys
        assert "anthropic" in keys
        assert "gemini" not in keys
        assert "OpenAI" in names
        assert "Anthropic" in names

    def test_get_available_providers_stt_with_keys(self):
        """Test STT providers returned when API keys exist."""
        mock_security_mgr = Mock()
        mock_security_mgr.get_api_key.side_effect = lambda key: {
            "groq": "gsk-test-key",
            "elevenlabs": None,
            "deepgram": "dg-test-key",
        }.get(key)

        app = create_mock_app()

        with patch.object(security_module, 'get_security_manager', return_value=mock_security_mgr):
            keys, names = app._get_available_providers("stt")

        assert "groq" in keys
        assert "deepgram" in keys
        assert "elevenlabs" not in keys
        assert "GROQ" in names
        assert "Deepgram" in names

    def test_get_available_providers_no_keys_fallback(self):
        """Test fallback to all providers when no API keys configured."""
        mock_security_mgr = Mock()
        mock_security_mgr.get_api_key.return_value = None

        app = create_mock_app()

        with patch.object(security_module, 'get_security_manager', return_value=mock_security_mgr):
            keys, names = app._get_available_providers("ai")

        # Fallback behavior: returns all providers when none have keys
        assert len(keys) == 3
        assert "openai" in keys
        assert "anthropic" in keys
        assert "gemini" in keys

    def test_get_available_providers_invalid_type(self):
        """Test graceful handling of invalid provider type."""
        mock_security_mgr = Mock()

        app = create_mock_app()

        with patch.object(security_module, 'get_security_manager', return_value=mock_security_mgr):
            keys, names = app._get_available_providers("invalid")

        assert len(keys) == 0
        assert len(names) == 0


class TestProviderConfiguration:
    """Test provider configuration constants."""

    def test_ai_provider_configs(self):
        """Test AI provider configuration list."""
        expected_ai = {
            "openai": "OpenAI",
            "anthropic": "Anthropic",
            "gemini": "Gemini"
        }

        mock_security_mgr = Mock()
        mock_security_mgr.get_api_key.return_value = "test-key"

        app = create_mock_app()

        with patch.object(security_module, 'get_security_manager', return_value=mock_security_mgr):
            keys, names = app._get_available_providers("ai")

        for key, name in expected_ai.items():
            assert key in keys, f"Missing AI provider key: {key}"
            assert name in names, f"Missing AI provider name: {name}"

    def test_stt_provider_configs(self):
        """Test STT provider configuration list."""
        expected_stt = {
            "groq": "GROQ",
            "elevenlabs": "ElevenLabs",
            "deepgram": "Deepgram"
        }

        mock_security_mgr = Mock()
        mock_security_mgr.get_api_key.return_value = "test-key"

        app = create_mock_app()

        with patch.object(security_module, 'get_security_manager', return_value=mock_security_mgr):
            keys, names = app._get_available_providers("stt")

        for key, name in expected_stt.items():
            assert key in keys, f"Missing STT provider key: {key}"
            assert name in names, f"Missing STT provider name: {name}"


class TestProviderKeyRetrieval:
    """Test security manager integration for key retrieval."""

    def test_security_manager_called_for_each_provider(self):
        """Test security manager is called for each provider."""
        mock_security_mgr = Mock()
        mock_security_mgr.get_api_key.return_value = "test-key"

        app = create_mock_app()

        with patch.object(security_module, 'get_security_manager', return_value=mock_security_mgr):
            app._get_available_providers("ai")

        assert mock_security_mgr.get_api_key.call_count >= 3

    def test_empty_api_key_treated_as_missing(self):
        """Test empty string API key behavior."""
        mock_security_mgr = Mock()
        mock_security_mgr.get_api_key.side_effect = lambda key: {
            "openai": "",  # Empty string - falsy
            "anthropic": "  ",  # Whitespace - truthy
            "gemini": "valid-key",
        }.get(key, None)

        app = create_mock_app()

        with patch.object(security_module, 'get_security_manager', return_value=mock_security_mgr):
            keys, names = app._get_available_providers("ai")

        assert "gemini" in keys
        assert "anthropic" in keys
        assert "openai" not in keys


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
