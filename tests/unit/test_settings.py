"""
Tests for src/settings/settings.py

Covers the two pure utility functions:
  - merge_settings_with_defaults (recursive dict merge with system_prompt edge case)
  - _migrate_suggestions_to_favorites (list-of-strings / nested-dict migration)
  - _make_provider_model_config (pure config generation)
  - invalidate_settings_cache (cache reset)
  - _DEFAULT_SETTINGS structure

No file I/O — all tests operate on in-memory dicts.
"""

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

# Patch data_folder_manager before import to avoid file system side-effects
with patch("managers.data_folder_manager.data_folder_manager") as _mock_dfm:
    _mock_dfm.settings_file_path = "/tmp/test_settings.json"
    from settings.settings import (
        merge_settings_with_defaults,
        _migrate_suggestions_to_favorites,
        _make_provider_model_config,
        invalidate_settings_cache,
        _DEFAULT_SETTINGS,
        SETTINGS_CACHE_TTL,
    )


# ===========================================================================
# merge_settings_with_defaults
# ===========================================================================

class TestMergeSettingsWithDefaults:
    def test_returns_dict(self):
        result = merge_settings_with_defaults({}, {})
        assert isinstance(result, dict)

    def test_empty_settings_returns_all_defaults(self):
        defaults = {"a": 1, "b": 2}
        result = merge_settings_with_defaults({}, defaults)
        assert result == {"a": 1, "b": 2}

    def test_existing_keys_not_overwritten(self):
        settings = {"a": 99}
        defaults = {"a": 1, "b": 2}
        result = merge_settings_with_defaults(settings, defaults)
        assert result["a"] == 99
        assert result["b"] == 2

    def test_missing_keys_added_from_defaults(self):
        settings = {"a": 1}
        defaults = {"a": 1, "b": 2, "c": 3}
        result = merge_settings_with_defaults(settings, defaults)
        assert result["b"] == 2
        assert result["c"] == 3

    def test_recursive_merge_of_nested_dicts(self):
        settings = {"nested": {"x": 10}}
        defaults = {"nested": {"x": 1, "y": 2}}
        result = merge_settings_with_defaults(settings, defaults)
        assert result["nested"]["x"] == 10   # preserved
        assert result["nested"]["y"] == 2    # added from defaults

    def test_deep_recursive_merge(self):
        settings = {"a": {"b": {"c": 99}}}
        defaults = {"a": {"b": {"c": 1, "d": 2}, "e": 3}}
        result = merge_settings_with_defaults(settings, defaults)
        assert result["a"]["b"]["c"] == 99
        assert result["a"]["b"]["d"] == 2
        assert result["a"]["e"] == 3

    def test_empty_string_system_prompt_replaced(self):
        settings = {"system_prompt": ""}
        defaults = {"system_prompt": "Default prompt"}
        result = merge_settings_with_defaults(settings, defaults)
        assert result["system_prompt"] == "Default prompt"

    def test_non_empty_system_prompt_preserved(self):
        settings = {"system_prompt": "Custom prompt"}
        defaults = {"system_prompt": "Default prompt"}
        result = merge_settings_with_defaults(settings, defaults)
        assert result["system_prompt"] == "Custom prompt"

    def test_does_not_mutate_input_settings(self):
        original = {"a": 1}
        defaults = {"b": 2}
        merge_settings_with_defaults(original, defaults)
        assert "b" not in original

    def test_does_not_mutate_input_defaults(self):
        settings = {"a": 1}
        defaults = {"b": 2}
        merge_settings_with_defaults(settings, defaults)
        assert len(defaults) == 1

    def test_none_value_in_settings_not_overridden(self):
        settings = {"a": None}
        defaults = {"a": "default"}
        result = merge_settings_with_defaults(settings, defaults)
        assert result["a"] is None

    def test_false_value_in_settings_not_overridden(self):
        settings = {"flag": False}
        defaults = {"flag": True}
        result = merge_settings_with_defaults(settings, defaults)
        assert result["flag"] is False

    def test_nested_dict_in_settings_vs_non_dict_default(self):
        # If settings has a dict but default is not a dict, settings value kept
        settings = {"key": {"nested": "value"}}
        defaults = {"key": "string_default"}
        result = merge_settings_with_defaults(settings, defaults)
        assert result["key"] == {"nested": "value"}


# ===========================================================================
# _migrate_suggestions_to_favorites
# ===========================================================================

class TestMigrateSuggestionsToFavorites:
    def test_returns_list_for_list_input(self):
        result = _migrate_suggestions_to_favorites(["text1", "text2"])
        assert isinstance(result, list)

    def test_converts_strings_to_object_format(self):
        result = _migrate_suggestions_to_favorites(["hello", "world"])
        assert result == [
            {"text": "hello", "favorite": False},
            {"text": "world", "favorite": False},
        ]

    def test_already_object_format_preserved(self):
        input_data = [{"text": "hi", "favorite": True}]
        result = _migrate_suggestions_to_favorites(input_data)
        assert result == [{"text": "hi", "favorite": True}]

    def test_mixed_list_converted_correctly(self):
        input_data = [
            "plain string",
            {"text": "already object", "favorite": True},
        ]
        result = _migrate_suggestions_to_favorites(input_data)
        assert result[0] == {"text": "plain string", "favorite": False}
        assert result[1] == {"text": "already object", "favorite": True}

    def test_empty_list_returns_empty_list(self):
        assert _migrate_suggestions_to_favorites([]) == []

    def test_handles_nested_dict(self):
        input_data = {
            "with_content": ["note a", "note b"],
            "without_content": ["quick note"],
        }
        result = _migrate_suggestions_to_favorites(input_data)
        assert isinstance(result, dict)
        assert result["with_content"] == [
            {"text": "note a", "favorite": False},
            {"text": "note b", "favorite": False},
        ]
        assert result["without_content"] == [
            {"text": "quick note", "favorite": False},
        ]

    def test_invalid_list_entries_skipped(self):
        input_data = ["valid", 42, None, {"text": "obj", "favorite": False}]
        result = _migrate_suggestions_to_favorites(input_data)
        # 42 and None are neither string nor dict-with-text, so skipped
        assert {"text": "valid", "favorite": False} in result
        assert {"text": "obj", "favorite": False} in result
        # 42 and None should not appear
        for item in result:
            assert item is not None
            assert isinstance(item, dict)

    def test_non_list_non_dict_returned_unchanged(self):
        result = _migrate_suggestions_to_favorites("raw string")
        assert result == "raw string"

    def test_deeply_nested_dict(self):
        input_data = {
            "outer": {
                "inner": ["text1"],
            }
        }
        result = _migrate_suggestions_to_favorites(input_data)
        assert result["outer"]["inner"] == [{"text": "text1", "favorite": False}]


# ===========================================================================
# _make_provider_model_config
# ===========================================================================

class TestMakeProviderModelConfig:
    def test_returns_dict(self):
        result = _make_provider_model_config()
        assert isinstance(result, dict)

    def test_contains_model_key(self):
        result = _make_provider_model_config(openai_model="gpt-4")
        assert result["model"] == "gpt-4"

    def test_contains_all_provider_models(self):
        result = _make_provider_model_config()
        for key in ("model", "ollama_model", "anthropic_model", "gemini_model",
                    "groq_model", "cerebras_model"):
            assert key in result

    def test_temperature_applied_to_all_providers(self):
        result = _make_provider_model_config(temperature=0.5)
        for key in ("temperature", "openai_temperature", "ollama_temperature",
                    "anthropic_temperature", "gemini_temperature",
                    "groq_temperature", "cerebras_temperature"):
            assert result[key] == 0.5

    def test_custom_models_stored(self):
        result = _make_provider_model_config(
            openai_model="gpt-4",
            anthropic_model="claude-3",
            ollama_model="llama3.1",
        )
        assert result["model"] == "gpt-4"
        assert result["anthropic_model"] == "claude-3"
        assert result["ollama_model"] == "llama3.1"


# ===========================================================================
# invalidate_settings_cache
# ===========================================================================

class TestInvalidateSettingsCache:
    def test_does_not_raise(self):
        invalidate_settings_cache()  # Should not raise

    def test_is_callable(self):
        assert callable(invalidate_settings_cache)


# ===========================================================================
# _DEFAULT_SETTINGS structure
# ===========================================================================

class TestDefaultSettings:
    def test_is_dict(self):
        assert isinstance(_DEFAULT_SETTINGS, dict)

    def test_has_expected_top_level_keys(self):
        for key in ("ai_provider", "stt_provider", "theme"):
            assert key in _DEFAULT_SETTINGS

    def test_cache_ttl_is_positive(self):
        assert SETTINGS_CACHE_TTL > 0
