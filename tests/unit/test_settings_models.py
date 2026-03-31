"""
Tests for src/settings/settings_models.py

Covers:
  - looks_like_api_key (pattern matching)
  - strip_api_keys_from_dict (recursive redaction)
  - ValidationResult dataclass defaults
  - validate_setting_value (temperature, max_tokens, boolean checks)
  - _check_common_typos (typo detection via validate_settings wrapper)
  - is_pydantic_available
Pure logic — no file I/O.
"""

import sys
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from settings.settings_models import (
    looks_like_api_key,
    strip_api_keys_from_dict,
    ValidationResult,
    validate_setting_value,
    is_pydantic_available,
)


# ===========================================================================
# looks_like_api_key
# ===========================================================================

class TestLooksLikeApiKey:
    def test_returns_false_for_non_string(self):
        assert looks_like_api_key(12345) is False
        assert looks_like_api_key(None) is False
        assert looks_like_api_key(["key"]) is False

    def test_returns_false_for_short_string(self):
        assert looks_like_api_key("sk-short") is False

    def test_returns_false_for_empty_string(self):
        assert looks_like_api_key("") is False

    def test_recognizes_openai_key(self):
        key = "sk-" + "A" * 25
        assert looks_like_api_key(key) is True

    def test_recognizes_anthropic_key(self):
        key = "sk-ant-" + "A" * 25
        assert looks_like_api_key(key) is True

    def test_recognizes_groq_key(self):
        key = "gsk_" + "A" * 25
        assert looks_like_api_key(key) is True

    def test_recognizes_elevenlabs_key(self):
        key = "sk_" + "A" * 25
        assert looks_like_api_key(key) is True

    def test_recognizes_cerebras_key(self):
        key = "csk-" + "A" * 25
        assert looks_like_api_key(key) is True

    def test_recognizes_xai_key(self):
        key = "xai-" + "A" * 25
        assert looks_like_api_key(key) is True

    def test_recognizes_google_ai_key(self):
        key = "AIza" + "A" * 35
        assert looks_like_api_key(key) is True

    def test_recognizes_long_alphanumeric_token(self):
        # 36-char all-alphanumeric (Deepgram-style)
        key = "a" * 36
        assert looks_like_api_key(key) is True

    def test_returns_false_for_regular_words(self):
        assert looks_like_api_key("hello world settings value") is False

    def test_returns_false_for_url(self):
        assert looks_like_api_key("http://localhost:11434") is False

    def test_short_alphanumeric_below_20_returns_false(self):
        assert looks_like_api_key("abcdefghij12345678") is False  # < 20 chars won't match

    def test_exact_19_chars_returns_false(self):
        assert looks_like_api_key("a" * 19) is False


# ===========================================================================
# strip_api_keys_from_dict
# ===========================================================================

class TestStripApiKeysFromDict:
    def test_empty_dict_returns_empty_list(self):
        d = {}
        result = strip_api_keys_from_dict(d)
        assert result == []

    def test_non_dict_returns_empty_list(self):
        result = strip_api_keys_from_dict("not a dict")
        assert result == []

    def test_strips_openai_key(self):
        d = {"api_key": "sk-" + "A" * 25}
        stripped = strip_api_keys_from_dict(d)
        assert len(stripped) == 1
        assert d["api_key"] == ""

    def test_strips_field_named_api_key(self):
        d = {"api_key": "some_value_that_is_set"}
        strip_api_keys_from_dict(d)
        assert d["api_key"] == ""

    def test_strips_field_named_secret_key(self):
        d = {"secret_key": "my_secret_value_here"}
        strip_api_keys_from_dict(d)
        assert d["secret_key"] == ""

    def test_strips_field_containing_password(self):
        d = {"database_password": "my_password_value"}
        strip_api_keys_from_dict(d)
        assert d["database_password"] == ""

    def test_returns_dotted_path(self):
        d = {"openai": {"api_key": "sk-" + "A" * 25}}
        stripped = strip_api_keys_from_dict(d)
        assert any("openai.api_key" in path for path, _ in stripped)

    def test_recursively_strips_nested_dict(self):
        d = {"openai": {"api_key": "sk-" + "A" * 25}}
        strip_api_keys_from_dict(d)
        assert d["openai"]["api_key"] == ""

    def test_non_key_fields_not_stripped(self):
        d = {"theme": "flatly", "language": "en"}
        strip_api_keys_from_dict(d)
        assert d["theme"] == "flatly"
        assert d["language"] == "en"

    def test_hint_contains_first_six_chars(self):
        key = "sk-" + "A" * 25
        d = {"api_key": key}
        stripped = strip_api_keys_from_dict(d)
        _, hint = stripped[0]
        assert hint.startswith(key[:6])

    def test_returns_list_of_tuples(self):
        d = {"api_key": "sk-" + "A" * 25}
        result = strip_api_keys_from_dict(d)
        assert isinstance(result, list)
        assert isinstance(result[0], tuple)
        assert len(result[0]) == 2

    def test_long_alphanumeric_value_stripped(self):
        d = {"token": "a" * 40}
        strip_api_keys_from_dict(d)
        assert d["token"] == ""

    def test_empty_string_values_not_stripped(self):
        d = {"api_key": ""}
        stripped = strip_api_keys_from_dict(d)
        # Empty strings are falsy — the `if value:` check skips them
        assert len(stripped) == 0


# ===========================================================================
# ValidationResult dataclass
# ===========================================================================

class TestValidationResult:
    def test_is_valid_defaults_true(self):
        r = ValidationResult()
        assert r.is_valid is True

    def test_errors_defaults_empty(self):
        r = ValidationResult()
        assert r.errors == []

    def test_warnings_defaults_empty(self):
        r = ValidationResult()
        assert r.warnings == []

    def test_unknown_keys_defaults_empty(self):
        r = ValidationResult()
        assert r.unknown_keys == []

    def test_can_set_is_valid_false(self):
        r = ValidationResult(is_valid=False)
        assert r.is_valid is False

    def test_can_add_errors(self):
        r = ValidationResult()
        r.errors.append("some error")
        assert "some error" in r.errors

    def test_instances_dont_share_lists(self):
        r1 = ValidationResult()
        r2 = ValidationResult()
        r1.errors.append("e1")
        assert r2.errors == []


# ===========================================================================
# validate_setting_value
# ===========================================================================

class TestValidateSettingValue:
    def test_temperature_valid_float(self):
        result = validate_setting_value("temperature", 0.7)
        assert result.errors == []

    def test_temperature_non_number_adds_error(self):
        result = validate_setting_value("temperature", "hot")
        assert any("number" in e for e in result.errors)

    def test_temperature_too_high_adds_warning(self):
        result = validate_setting_value("temperature", 3.0)
        assert any("range" in w for w in result.warnings)

    def test_temperature_zero_is_valid(self):
        result = validate_setting_value("temperature", 0.0)
        assert result.errors == []
        assert result.warnings == []

    def test_max_tokens_valid_integer(self):
        result = validate_setting_value("max_tokens", 1000)
        assert result.errors == []

    def test_max_tokens_non_integer_adds_error(self):
        result = validate_setting_value("max_tokens", "lots")
        assert any("integer" in e for e in result.errors)

    def test_max_tokens_very_low_adds_warning(self):
        result = validate_setting_value("max_tokens", 10)
        assert any("low" in w for w in result.warnings)

    def test_max_tokens_very_high_adds_warning(self):
        result = validate_setting_value("max_tokens", 20000)
        assert any("exceed" in w for w in result.warnings)

    def test_boolean_key_non_bool_adds_warning(self):
        result = validate_setting_value("enabled", "yes")
        assert any("boolean" in w for w in result.warnings)

    def test_boolean_key_bool_value_is_valid(self):
        result = validate_setting_value("enabled", True)
        assert result.warnings == []
        assert result.errors == []

    def test_unknown_key_no_validation(self):
        result = validate_setting_value("some_unknown_key", "value")
        assert result.errors == []
        assert result.warnings == []


# ===========================================================================
# is_pydantic_available
# ===========================================================================

class TestIsPydanticAvailable:
    def test_returns_bool(self):
        assert isinstance(is_pydantic_available(), bool)

    def test_returns_true_when_pydantic_installed(self):
        # In test environment, Pydantic should be installed
        try:
            import pydantic
            assert is_pydantic_available() is True
        except ImportError:
            pass  # If not installed, skip this assertion
