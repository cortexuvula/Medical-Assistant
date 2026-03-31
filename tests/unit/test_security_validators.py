"""
Tests for src/utils/security/validators.py

Covers pure-logic methods only:
  - APIKeyValidator._validate_key_format
  - APIKeyValidator.update_format
  - InputSanitizer._sanitize_generic

Methods that import from utils.validation at runtime (validate, _sanitize_prompt,
_sanitize_filename) are intentionally excluded.
"""

import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from utils.security.validators import APIKeyValidator, InputSanitizer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _openai_key(total_len: int = 20) -> str:
    """Return a well-formed OpenAI key of the given total length."""
    prefix = "sk-"
    body = "a" * (total_len - len(prefix))
    return prefix + body


def _anthropic_key(total_len: int = 90) -> str:
    """Return a well-formed Anthropic key of the given total length."""
    prefix = "sk-ant-"
    body = "a" * (total_len - len(prefix))
    return prefix + body


def _groq_key(total_len: int = 40) -> str:
    prefix = "gsk_"
    body = "a" * (total_len - len(prefix))
    return prefix + body


def _elevenlabs_key(total_len: int = 30) -> str:
    prefix = "sk_"
    body = "a" * (total_len - len(prefix))
    return prefix + body


def _gemini_key(total_len: int = 35) -> str:
    prefix = "AIza"
    body = "a" * (total_len - len(prefix))
    return prefix + body


def _cerebras_key(total_len: int = 20) -> str:
    prefix = "csk-"
    body = "a" * (total_len - len(prefix))
    return prefix + body


# ---------------------------------------------------------------------------
# TestAPIKeyValidatorInit
# ---------------------------------------------------------------------------

class TestAPIKeyValidatorInit:
    """5 tests: validator instantiation and format dictionary shape."""

    def test_validator_can_be_created(self):
        validator = APIKeyValidator()
        assert validator is not None

    def test_api_key_formats_is_dict(self):
        validator = APIKeyValidator()
        assert isinstance(validator.api_key_formats, dict)

    def test_api_key_formats_has_seven_entries(self):
        validator = APIKeyValidator()
        assert len(validator.api_key_formats) == 7

    def test_openai_prefix_is_sk_dash(self):
        validator = APIKeyValidator()
        assert validator.api_key_formats["openai"]["prefix"] == "sk-"

    def test_all_expected_providers_present(self):
        validator = APIKeyValidator()
        expected = {"openai", "anthropic", "cerebras", "gemini", "deepgram", "groq", "elevenlabs"}
        assert expected == set(validator.api_key_formats.keys())


# ---------------------------------------------------------------------------
# TestValidateKeyFormatUnknownProvider
# ---------------------------------------------------------------------------

class TestValidateKeyFormatUnknownProvider:
    """6 tests: provider not in api_key_formats — fallback length checks."""

    def setup_method(self):
        self.validator = APIKeyValidator()

    def test_unknown_provider_short_key_is_invalid(self):
        valid, msg = self.validator._validate_key_format("short", "unknown_provider")
        assert valid is False
        assert "too short" in msg

    def test_unknown_provider_key_of_9_chars_is_invalid(self):
        valid, msg = self.validator._validate_key_format("a" * 9, "unknown_provider")
        assert valid is False
        assert "too short" in msg

    def test_unknown_provider_key_of_501_chars_is_invalid(self):
        valid, msg = self.validator._validate_key_format("a" * 501, "unknown_provider")
        assert valid is False
        assert "too long" in msg

    def test_unknown_provider_key_of_exactly_10_chars_is_valid(self):
        valid, msg = self.validator._validate_key_format("a" * 10, "unknown_provider")
        assert valid is True
        assert msg is None

    def test_unknown_provider_key_of_exactly_500_chars_is_valid(self):
        valid, msg = self.validator._validate_key_format("a" * 500, "unknown_provider")
        assert valid is True
        assert msg is None

    def test_unknown_provider_key_of_100_chars_is_valid(self):
        valid, msg = self.validator._validate_key_format("a" * 100, "my_custom_provider")
        assert valid is True
        assert msg is None


# ---------------------------------------------------------------------------
# TestValidateKeyFormatPrefix
# ---------------------------------------------------------------------------

class TestValidateKeyFormatPrefix:
    """4 tests: prefix enforcement."""

    def setup_method(self):
        self.validator = APIKeyValidator()

    def test_missing_prefix_returns_false(self):
        # OpenAI requires "sk-" prefix — provide a key without it
        key_without_prefix = "a" * 30
        valid, msg = self.validator._validate_key_format(key_without_prefix, "openai")
        assert valid is False

    def test_missing_prefix_error_mentions_expected_prefix(self):
        key_without_prefix = "a" * 30
        _, msg = self.validator._validate_key_format(key_without_prefix, "openai")
        assert "sk-" in msg

    def test_wrong_prefix_returns_false_with_correct_hint(self):
        # Anthropic key accidentally given OpenAI prefix
        key = "sk-" + "a" * 90
        valid, msg = self.validator._validate_key_format(key, "anthropic")
        assert valid is False
        assert "sk-ant-" in msg

    def test_correct_prefix_passes_prefix_check(self):
        # Key with correct prefix and exactly min_length for openai (20)
        key = _openai_key(20)
        valid, msg = self.validator._validate_key_format(key, "openai")
        assert valid is True
        assert msg is None


# ---------------------------------------------------------------------------
# TestValidateKeyFormatLength
# ---------------------------------------------------------------------------

class TestValidateKeyFormatLength:
    """8 tests: min/max length boundaries for OpenAI and Groq."""

    def setup_method(self):
        self.validator = APIKeyValidator()

    # --- OpenAI (min=20, max=200) ---

    def test_openai_key_below_min_length_is_invalid(self):
        key = _openai_key(19)
        valid, msg = self.validator._validate_key_format(key, "openai")
        assert valid is False
        assert "too short" in msg

    def test_openai_key_at_min_length_is_valid(self):
        key = _openai_key(20)
        valid, msg = self.validator._validate_key_format(key, "openai")
        assert valid is True
        assert msg is None

    def test_openai_key_at_max_length_is_valid(self):
        key = _openai_key(200)
        valid, msg = self.validator._validate_key_format(key, "openai")
        assert valid is True
        assert msg is None

    def test_openai_key_above_max_length_is_invalid(self):
        key = _openai_key(201)
        valid, msg = self.validator._validate_key_format(key, "openai")
        assert valid is False
        assert "too long" in msg

    # --- Groq (min=40, max=100, chars=alnum) ---

    def test_groq_key_below_min_length_is_invalid(self):
        key = _groq_key(39)
        valid, msg = self.validator._validate_key_format(key, "groq")
        assert valid is False
        assert "too short" in msg

    def test_groq_key_at_min_length_is_valid(self):
        key = _groq_key(40)
        valid, msg = self.validator._validate_key_format(key, "groq")
        assert valid is True
        assert msg is None

    def test_groq_key_at_max_length_is_valid(self):
        key = _groq_key(100)
        valid, msg = self.validator._validate_key_format(key, "groq")
        assert valid is True
        assert msg is None

    def test_groq_key_above_max_length_is_invalid(self):
        key = _groq_key(101)
        valid, msg = self.validator._validate_key_format(key, "groq")
        assert valid is False
        assert "too long" in msg


# ---------------------------------------------------------------------------
# TestValidateKeyFormatCharacters
# ---------------------------------------------------------------------------

class TestValidateKeyFormatCharacters:
    """8 tests: character set validation for alnum and alnum_dash providers."""

    def setup_method(self):
        self.validator = APIKeyValidator()

    # --- alnum (Groq): gsk_ + alphanumeric only ---

    def test_groq_alnum_valid_body(self):
        # gsk_ + 36 pure-alphanumeric chars = 40 total
        key = "gsk_" + "aB3" * 12
        valid, msg = self.validator._validate_key_format(key, "groq")
        assert valid is True
        assert msg is None

    def test_groq_alnum_invalid_with_dash(self):
        key = "gsk_" + "a-b" + "c" * 33
        valid, msg = self.validator._validate_key_format(key, "groq")
        assert valid is False
        assert "letters and numbers" in msg

    def test_groq_alnum_invalid_with_special_char(self):
        key = "gsk_" + "a@b" + "c" * 33
        valid, msg = self.validator._validate_key_format(key, "groq")
        assert valid is False

    def test_groq_alnum_invalid_with_underscore(self):
        # underscore is not alphanumeric
        key = "gsk_" + "a_b" + "c" * 33
        valid, msg = self.validator._validate_key_format(key, "groq")
        assert valid is False

    # --- alnum_dash (OpenAI): sk- + alphanumeric, dash, underscore ---

    def test_openai_alnum_dash_valid_with_underscore(self):
        # sk- + 17+ chars including underscore
        key = "sk-" + "abc_DEF" + "a" * 10
        valid, msg = self.validator._validate_key_format(key, "openai")
        assert valid is True
        assert msg is None

    def test_openai_alnum_dash_valid_with_hyphen(self):
        key = "sk-" + "abc-DEF" + "a" * 10
        valid, msg = self.validator._validate_key_format(key, "openai")
        assert valid is True
        assert msg is None

    def test_openai_alnum_dash_invalid_with_at_sign(self):
        key = "sk-" + "abc@DEF" + "a" * 10
        valid, msg = self.validator._validate_key_format(key, "openai")
        assert valid is False
        assert "invalid characters" in msg

    def test_openai_alnum_dash_invalid_with_space(self):
        key = "sk-" + "abc DEF" + "a" * 10
        valid, msg = self.validator._validate_key_format(key, "openai")
        assert valid is False


# ---------------------------------------------------------------------------
# TestValidateKeyFormatOpenAI
# ---------------------------------------------------------------------------

class TestValidateKeyFormatOpenAI:
    """5 tests: full OpenAI key validation scenarios via _validate_key_format."""

    def setup_method(self):
        self.validator = APIKeyValidator()

    def test_valid_openai_key(self):
        key = _openai_key(50)
        valid, msg = self.validator._validate_key_format(key, "openai")
        assert valid is True
        assert msg is None

    def test_openai_bad_prefix(self):
        key = "pk-" + "a" * 47
        valid, msg = self.validator._validate_key_format(key, "openai")
        assert valid is False
        assert "sk-" in msg

    def test_openai_too_short(self):
        # "sk-" + 5 chars = 8, below min=20
        key = "sk-" + "a" * 5
        valid, msg = self.validator._validate_key_format(key, "openai")
        assert valid is False
        assert "too short" in msg

    def test_openai_too_long(self):
        # "sk-" + 300 chars = 303, above max=200
        key = "sk-" + "a" * 300
        valid, msg = self.validator._validate_key_format(key, "openai")
        assert valid is False
        assert "too long" in msg

    def test_openai_invalid_chars(self):
        # "sk-" + "a!b" + 17 chars = 23 total, within length limits but has '!'
        key = "sk-" + "a!b" + "c" * 17
        valid, msg = self.validator._validate_key_format(key, "openai")
        assert valid is False
        assert "invalid characters" in msg


# ---------------------------------------------------------------------------
# TestValidateKeyFormatAnthropic
# ---------------------------------------------------------------------------

class TestValidateKeyFormatAnthropic:
    """5 tests: full Anthropic key validation scenarios via _validate_key_format."""

    def setup_method(self):
        self.validator = APIKeyValidator()

    def test_valid_anthropic_key(self):
        key = _anthropic_key(100)
        valid, msg = self.validator._validate_key_format(key, "anthropic")
        assert valid is True
        assert msg is None

    def test_anthropic_bad_prefix(self):
        # Correct length but wrong prefix — "sk-" instead of "sk-ant-"
        key = "sk-" + "a" * 90
        valid, msg = self.validator._validate_key_format(key, "anthropic")
        assert valid is False
        assert "sk-ant-" in msg

    def test_anthropic_too_short(self):
        # "sk-ant-" + 10 chars = 17, well below min=90
        key = "sk-ant-" + "a" * 10
        valid, msg = self.validator._validate_key_format(key, "anthropic")
        assert valid is False
        assert "too short" in msg

    def test_anthropic_too_long(self):
        # "sk-ant-" + 300 chars = 307, above max=200
        key = "sk-ant-" + "a" * 300
        valid, msg = self.validator._validate_key_format(key, "anthropic")
        assert valid is False
        assert "too long" in msg

    def test_anthropic_invalid_chars(self):
        # 97 chars total with correct prefix but '!' in body
        key = "sk-ant-" + "a!b" + "c" * 87
        valid, msg = self.validator._validate_key_format(key, "anthropic")
        assert valid is False
        assert "invalid characters" in msg


# ---------------------------------------------------------------------------
# TestUpdateFormat
# ---------------------------------------------------------------------------

class TestUpdateFormat:
    """8 tests: update_format creates and modifies format entries."""

    def setup_method(self):
        self.validator = APIKeyValidator()

    def test_update_format_creates_new_provider(self):
        self.validator.update_format("my_new_provider", prefix="np-", min_length=15)
        assert "my_new_provider" in self.validator.api_key_formats

    def test_update_format_sets_prefix_on_new_provider(self):
        self.validator.update_format("prov_a", prefix="pa-")
        assert self.validator.api_key_formats["prov_a"]["prefix"] == "pa-"

    def test_update_format_sets_min_length_on_new_provider(self):
        self.validator.update_format("prov_b", min_length=25)
        assert self.validator.api_key_formats["prov_b"]["min_length"] == 25

    def test_update_format_sets_max_length_on_new_provider(self):
        self.validator.update_format("prov_c", max_length=300)
        assert self.validator.api_key_formats["prov_c"]["max_length"] == 300

    def test_update_format_does_not_store_none_fields(self):
        # Create provider with only prefix; min_length should not be stored at all
        self.validator.update_format("prov_d", prefix="pd-")
        rules = self.validator.api_key_formats["prov_d"]
        assert "min_length" not in rules

    def test_update_format_updates_existing_openai_prefix(self):
        self.validator.update_format("openai", prefix="sk2-")
        assert self.validator.api_key_formats["openai"]["prefix"] == "sk2-"

    def test_update_format_updates_existing_min_length(self):
        self.validator.update_format("openai", min_length=50)
        assert self.validator.api_key_formats["openai"]["min_length"] == 50

    def test_update_format_none_args_leave_existing_values_unchanged(self):
        # Only update prefix (same value); min_length kwarg omitted — must remain 20
        original_min = self.validator.api_key_formats["openai"]["min_length"]
        self.validator.update_format("openai", prefix="sk-")
        assert self.validator.api_key_formats["openai"]["min_length"] == original_min


# ---------------------------------------------------------------------------
# TestInputSanitizerGeneric
# ---------------------------------------------------------------------------

class TestInputSanitizerGeneric:
    """10 tests: _sanitize_generic pure logic."""

    def setup_method(self):
        self.sanitizer = InputSanitizer()

    def test_empty_string_returns_empty(self):
        result = self.sanitizer._sanitize_generic("")
        assert result == ""

    def test_normal_text_is_preserved(self):
        text = "Hello, this is a normal sentence."
        result = self.sanitizer._sanitize_generic(text)
        assert result == text

    def test_control_char_below_32_is_removed(self):
        # chr(1) is SOH — a control character that must be stripped
        text = "before\x01after"
        result = self.sanitizer._sanitize_generic(text)
        assert "\x01" not in result
        assert result == "beforeafter"

    def test_newline_is_preserved(self):
        text = "line1\nline2"
        result = self.sanitizer._sanitize_generic(text)
        assert "\n" in result
        assert result == "line1\nline2"

    def test_tab_is_preserved(self):
        text = "col1\tcol2"
        result = self.sanitizer._sanitize_generic(text)
        assert "\t" in result
        assert result == "col1\tcol2"

    def test_exactly_10000_chars_not_truncated(self):
        text = "a" * 10000
        result = self.sanitizer._sanitize_generic(text)
        assert len(result) == 10000

    def test_10001_chars_truncated_to_10000(self):
        text = "a" * 10001
        result = self.sanitizer._sanitize_generic(text)
        assert len(result) == 10000

    def test_all_control_chars_removed_except_newline_and_tab(self):
        # Build a string containing every control char from 0–31 except \t (9) and \n (10)
        control_chars = "".join(chr(i) for i in range(32) if i not in (9, 10))
        text = "start" + control_chars + "end"
        result = self.sanitizer._sanitize_generic(text)
        assert result == "startend"

    def test_leading_and_trailing_whitespace_stripped(self):
        text = "   padded text   "
        result = self.sanitizer._sanitize_generic(text)
        assert result == "padded text"

    def test_mixed_content_control_chars_and_normal_text(self):
        # \x00 null, \x07 bell, \x1b ESC removed; \n preserved
        text = "\x00Hello\x07 World\nFoo\x1bBar"
        result = self.sanitizer._sanitize_generic(text)
        assert result == "Hello World\nFooBar"
