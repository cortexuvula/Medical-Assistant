"""Regression tests for settings persistence.

These tests verify that settings are correctly saved, loaded,
merged with defaults, and that nested settings are preserved.
"""
import pytest
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestSettingsLoad:
    """Tests for loading settings."""

    def test_load_settings_returns_dict(self, tmp_path):
        """load_settings() should return a dictionary."""
        from src.settings.settings import load_settings, _DEFAULT_SETTINGS

        # Patch SETTINGS_FILE to use temp path
        settings_file = tmp_path / "settings.json"

        with patch("src.settings.settings.SETTINGS_FILE", str(settings_file)):
            # No file exists yet, should return defaults
            settings = load_settings()

        assert isinstance(settings, dict)

    def test_load_settings_creates_defaults_when_no_file(self, tmp_path):
        """load_settings() should return defaults when no file exists."""
        from src.settings.settings import load_settings, _DEFAULT_SETTINGS

        settings_file = tmp_path / "settings.json"

        with patch("src.settings.settings.SETTINGS_FILE", str(settings_file)):
            settings = load_settings()

        # Should have key default settings
        assert "ai_provider" in settings
        assert "stt_provider" in settings
        assert "agent_config" in settings

    def test_load_settings_reads_existing_file(self, tmp_path):
        """load_settings() should read settings from existing file."""
        from src.settings.settings import load_settings

        settings_file = tmp_path / "settings.json"
        custom_settings = {
            "ai_provider": "anthropic",
            "custom_key": "custom_value"
        }

        with open(settings_file, "w") as f:
            json.dump(custom_settings, f)

        with patch("src.settings.settings.SETTINGS_FILE", str(settings_file)):
            settings = load_settings()

        assert settings["ai_provider"] == "anthropic"
        assert settings["custom_key"] == "custom_value"

    def test_load_settings_handles_corrupted_file(self, tmp_path):
        """load_settings() should handle corrupted JSON gracefully."""
        from src.settings.settings import load_settings, _DEFAULT_SETTINGS

        settings_file = tmp_path / "settings.json"

        # Write invalid JSON
        with open(settings_file, "w") as f:
            f.write("{invalid json content")

        with patch("src.settings.settings.SETTINGS_FILE", str(settings_file)):
            settings = load_settings()

        # Should return defaults on error
        assert isinstance(settings, dict)


class TestSettingsSave:
    """Tests for saving settings."""

    def test_save_settings_creates_file(self, tmp_path):
        """save_settings() should create the settings file."""
        from src.settings.settings import save_settings

        settings_file = tmp_path / "settings.json"
        test_settings = {"test_key": "test_value"}

        with patch("src.settings.settings.SETTINGS_FILE", str(settings_file)):
            save_settings(test_settings)

        assert settings_file.exists()

    def test_save_settings_writes_valid_json(self, tmp_path):
        """save_settings() should write valid JSON."""
        from src.settings.settings import save_settings

        settings_file = tmp_path / "settings.json"
        test_settings = {
            "string_key": "value",
            "int_key": 42,
            "nested": {"inner": "data"}
        }

        with patch("src.settings.settings.SETTINGS_FILE", str(settings_file)):
            save_settings(test_settings)

        # Should be readable as JSON
        with open(settings_file) as f:
            loaded = json.load(f)

        assert loaded == test_settings

    def test_save_settings_preserves_unicode(self, tmp_path):
        """save_settings() should preserve unicode characters."""
        from src.settings.settings import save_settings

        settings_file = tmp_path / "settings.json"
        test_settings = {
            "unicode_key": "Test with émojis 🏥 and ñ"
        }

        with patch("src.settings.settings.SETTINGS_FILE", str(settings_file)):
            save_settings(test_settings)

        with open(settings_file, encoding="utf-8") as f:
            loaded = json.load(f)

        assert loaded["unicode_key"] == "Test with émojis 🏥 and ñ"


class TestSettingsMerge:
    """Tests for merging settings with defaults."""

    def test_merge_adds_missing_keys(self):
        """merge_settings_with_defaults() should add missing keys."""
        from src.settings.settings import merge_settings_with_defaults

        settings = {"existing_key": "value"}
        defaults = {
            "existing_key": "default",
            "missing_key": "default_value"
        }

        merged = merge_settings_with_defaults(settings, defaults)

        assert merged["existing_key"] == "value"  # Preserved
        assert merged["missing_key"] == "default_value"  # Added

    def test_merge_preserves_existing_values(self):
        """merge_settings_with_defaults() should preserve existing values."""
        from src.settings.settings import merge_settings_with_defaults

        settings = {
            "key1": "user_value",
            "key2": 42
        }
        defaults = {
            "key1": "default_value",
            "key2": 0,
            "key3": "new_default"
        }

        merged = merge_settings_with_defaults(settings, defaults)

        assert merged["key1"] == "user_value"
        assert merged["key2"] == 42
        assert merged["key3"] == "new_default"

    def test_merge_handles_nested_dicts(self):
        """merge_settings_with_defaults() should merge nested dictionaries."""
        from src.settings.settings import merge_settings_with_defaults

        settings = {
            "nested": {
                "existing": "user_value"
            }
        }
        defaults = {
            "nested": {
                "existing": "default",
                "missing": "default_value"
            }
        }

        merged = merge_settings_with_defaults(settings, defaults)

        assert merged["nested"]["existing"] == "user_value"
        assert merged["nested"]["missing"] == "default_value"

    def test_merge_deeply_nested(self):
        """merge_settings_with_defaults() should handle deeply nested structures."""
        from src.settings.settings import merge_settings_with_defaults

        settings = {
            "level1": {
                "level2": {
                    "level3": "user_value"
                }
            }
        }
        defaults = {
            "level1": {
                "level2": {
                    "level3": "default",
                    "new_key": "new_value"
                },
                "other": "value"
            }
        }

        merged = merge_settings_with_defaults(settings, defaults)

        assert merged["level1"]["level2"]["level3"] == "user_value"
        assert merged["level1"]["level2"]["new_key"] == "new_value"
        assert merged["level1"]["other"] == "value"


class TestAgentConfigPersistence:
    """Tests for agent configuration persistence."""

    def test_agent_config_structure(self, tmp_path):
        """Agent config should have correct structure."""
        from src.settings.settings import _DEFAULT_SETTINGS

        agent_config = _DEFAULT_SETTINGS["agent_config"]

        # Check required agent types
        assert "synopsis" in agent_config
        assert "diagnostic" in agent_config
        assert "medication" in agent_config

    def test_agent_config_has_required_fields(self, tmp_path):
        """Each agent config should have required fields."""
        from src.settings.settings import _DEFAULT_SETTINGS

        required_fields = ["enabled", "provider", "model", "temperature"]

        for agent_name, agent_config in _DEFAULT_SETTINGS["agent_config"].items():
            for field in required_fields:
                assert field in agent_config, f"{agent_name} missing {field}"

    def test_agent_config_persists_changes(self, tmp_path):
        """Changes to agent config should persist."""
        from src.settings.settings import save_settings, load_settings

        settings_file = tmp_path / "settings.json"

        # Create settings with modified agent config
        test_settings = {
            "agent_config": {
                "synopsis": {
                    "enabled": False,
                    "provider": "anthropic",
                    "model": "claude-3-opus",
                    "temperature": 0.5,
                    "system_prompt": "Custom prompt"
                }
            }
        }

        with patch("src.settings.settings.SETTINGS_FILE", str(settings_file)):
            save_settings(test_settings)
            loaded = load_settings()

        assert loaded["agent_config"]["synopsis"]["enabled"] is False
        assert loaded["agent_config"]["synopsis"]["provider"] == "anthropic"


class TestProviderSettings:
    """Tests for provider-specific settings."""

    def test_deepgram_settings_structure(self):
        """Deepgram settings should have correct structure."""
        from src.settings.settings import _DEFAULT_SETTINGS

        deepgram = _DEFAULT_SETTINGS["deepgram"]

        assert "model" in deepgram
        assert "language" in deepgram
        assert "smart_format" in deepgram

    def test_elevenlabs_settings_structure(self):
        """ElevenLabs settings should have correct structure."""
        from src.settings.settings import _DEFAULT_SETTINGS

        elevenlabs = _DEFAULT_SETTINGS["elevenlabs"]

        assert "model_id" in elevenlabs
        assert "language_code" in elevenlabs

    def test_provider_settings_persist(self, tmp_path):
        """Provider settings should persist correctly."""
        from src.settings.settings import save_settings, load_settings

        settings_file = tmp_path / "settings.json"

        test_settings = {
            "deepgram": {
                "model": "nova-2-general",
                "language": "en-GB",
                "smart_format": False
            },
            "groq": {
                "model": "whisper-large-v3"
            }
        }

        with patch("src.settings.settings.SETTINGS_FILE", str(settings_file)):
            save_settings(test_settings)
            loaded = load_settings()

        assert loaded["deepgram"]["model"] == "nova-2-general"
        assert loaded["deepgram"]["language"] == "en-GB"


class TestChatInterfaceSettings:
    """Tests for chat interface settings."""

    def test_chat_interface_defaults(self):
        """Chat interface should have default settings."""
        from src.settings.settings import _DEFAULT_SETTINGS

        chat = _DEFAULT_SETTINGS["chat_interface"]

        assert "enabled" in chat
        assert "max_input_length" in chat
        assert "temperature" in chat

    def test_custom_suggestions_structure(self):
        """Custom suggestions should have correct structure."""
        from src.settings.settings import _DEFAULT_SETTINGS

        suggestions = _DEFAULT_SETTINGS["custom_chat_suggestions"]

        assert "global" in suggestions
        assert "transcript" in suggestions
        assert "soap" in suggestions

    def test_suggestions_persist(self, tmp_path):
        """Custom suggestions should persist."""
        from src.settings.settings import save_settings, load_settings

        settings_file = tmp_path / "settings.json"

        test_settings = {
            "custom_chat_suggestions": {
                "global": ["Custom suggestion 1", "Custom suggestion 2"],
                "transcript": {
                    "with_content": ["Custom transcript suggestion"]
                }
            }
        }

        with patch("src.settings.settings.SETTINGS_FILE", str(settings_file)):
            save_settings(test_settings)
            loaded = load_settings()

        assert "Custom suggestion 1" in loaded["custom_chat_suggestions"]["global"]


class TestTranslationSettings:
    """Tests for translation settings."""

    def test_translation_defaults(self):
        """Translation settings should have defaults."""
        from src.settings.settings import _DEFAULT_SETTINGS

        translation = _DEFAULT_SETTINGS["translation"]

        assert "provider" in translation
        assert "patient_language" in translation
        assert "doctor_language" in translation

    def test_canned_responses_structure(self):
        """Canned responses should have correct structure."""
        from src.settings.settings import _DEFAULT_SETTINGS

        canned = _DEFAULT_SETTINGS["translation_canned_responses"]

        assert "categories" in canned
        assert "responses" in canned
        assert isinstance(canned["categories"], list)
        assert isinstance(canned["responses"], dict)


class TestVocabularySettings:
    """Tests for custom vocabulary settings."""

    def test_vocabulary_defaults(self):
        """Vocabulary settings should have defaults."""
        from src.settings.settings import _DEFAULT_SETTINGS

        vocab = _DEFAULT_SETTINGS["custom_vocabulary"]

        assert "enabled" in vocab
        assert "default_specialty" in vocab
        assert "corrections" in vocab

    def test_vocabulary_corrections_persist(self, tmp_path):
        """Custom vocabulary corrections should persist."""
        from src.settings.settings import save_settings, load_settings

        settings_file = tmp_path / "settings.json"

        test_settings = {
            "custom_vocabulary": {
                "enabled": True,
                "default_specialty": "cardiology",
                "corrections": {
                    "hart": {
                        "replacement": "heart",
                        "category": "anatomy"
                    }
                }
            }
        }

        with patch("src.settings.settings.SETTINGS_FILE", str(settings_file)):
            save_settings(test_settings)
            loaded = load_settings()

        assert loaded["custom_vocabulary"]["corrections"]["hart"]["replacement"] == "heart"


@pytest.mark.regression
class TestSettingsRegressionSuite:
    """Comprehensive regression tests for settings."""

    def test_full_settings_cycle(self, tmp_path):
        """Test complete save-load-modify-save cycle."""
        from src.settings.settings import save_settings, load_settings, _DEFAULT_SETTINGS

        settings_file = tmp_path / "settings.json"

        with patch("src.settings.settings.SETTINGS_FILE", str(settings_file)):
            # Start with defaults
            settings = _DEFAULT_SETTINGS.copy()

            # Modify some settings
            settings["ai_provider"] = "anthropic"
            settings["theme"] = "darkly"

            # Save
            save_settings(settings)

            # Load
            loaded = load_settings()

            # Verify
            assert loaded["ai_provider"] == "anthropic"
            assert loaded["theme"] == "darkly"

            # Modify again
            loaded["stt_provider"] = "whisper"
            save_settings(loaded)

            # Load again
            final = load_settings()
            assert final["stt_provider"] == "whisper"
            assert final["ai_provider"] == "anthropic"  # Still preserved

    def test_settings_backward_compatibility(self, tmp_path):
        """Settings should be backward compatible with older formats."""
        from src.settings.settings import save_settings, load_settings

        settings_file = tmp_path / "settings.json"

        # Simulate old settings format (minimal)
        old_settings = {
            "ai_provider": "openai",
            "stt_provider": "deepgram"
        }

        with patch("src.settings.settings.SETTINGS_FILE", str(settings_file)):
            save_settings(old_settings)
            loaded = load_settings()

        # Should have merged with defaults
        assert "agent_config" in loaded
        assert "chat_interface" in loaded

    def test_all_default_settings_valid(self):
        """All default settings should have valid values."""
        from src.settings.settings import _DEFAULT_SETTINGS

        # Check critical settings exist and have valid types
        assert isinstance(_DEFAULT_SETTINGS["ai_provider"], str)
        assert isinstance(_DEFAULT_SETTINGS["stt_provider"], str)
        assert isinstance(_DEFAULT_SETTINGS["theme"], str)
        assert isinstance(_DEFAULT_SETTINGS["agent_config"], dict)
        assert isinstance(_DEFAULT_SETTINGS["chat_interface"], dict)
        assert isinstance(_DEFAULT_SETTINGS["translation"], dict)

    def test_settings_handles_special_characters(self, tmp_path):
        """Settings should handle special characters in values."""
        from src.settings.settings import save_settings, load_settings

        settings_file = tmp_path / "settings.json"

        test_settings = {
            "soap_note": {
                "system_message": "Test with 'quotes' and \"double quotes\" and\nnewlines"
            },
            "custom_context": "Path: C:\\Users\\Test\\File.txt"
        }

        with patch("src.settings.settings.SETTINGS_FILE", str(settings_file)):
            save_settings(test_settings)
            loaded = load_settings()

        assert "quotes" in loaded["soap_note"]["system_message"]
        assert "C:\\Users\\Test" in loaded["custom_context"]

    def test_temperature_values_preserved(self, tmp_path):
        """Temperature values should be preserved exactly."""
        from src.settings.settings import save_settings, load_settings

        settings_file = tmp_path / "settings.json"

        test_settings = {
            "agent_config": {
                "synopsis": {
                    "enabled": True,
                    "provider": "openai",
                    "model": "gpt-4",
                    "temperature": 0.7,
                    "system_prompt": "Test"
                }
            },
            "refine_text": {
                "temperature": 0.0,
                "openai_temperature": 0.0
            }
        }

        with patch("src.settings.settings.SETTINGS_FILE", str(settings_file)):
            save_settings(test_settings)
            loaded = load_settings()

        assert loaded["agent_config"]["synopsis"]["temperature"] == 0.7
        assert loaded["refine_text"]["temperature"] == 0.0

    def test_boolean_values_preserved(self, tmp_path):
        """Boolean values should be preserved correctly."""
        from src.settings.settings import save_settings, load_settings

        settings_file = tmp_path / "settings.json"

        test_settings = {
            "quick_continue_mode": True,
            "auto_retry_failed": False,
            "autosave_enabled": True,
            "agent_config": {
                "synopsis": {
                    "enabled": False,
                    "provider": "openai",
                    "model": "gpt-4",
                    "temperature": 0.3,
                    "system_prompt": "Test"
                }
            }
        }

        with patch("src.settings.settings.SETTINGS_FILE", str(settings_file)):
            save_settings(test_settings)
            loaded = load_settings()

        assert loaded["quick_continue_mode"] is True
        assert loaded["auto_retry_failed"] is False
        assert loaded["agent_config"]["synopsis"]["enabled"] is False
