"""
Tests for pure methods of DeepTranslatorProvider in
src/translation/deep_translator_provider.py.

Covers:
  - COMMON_LANGUAGES class constant
  - get_supported_languages() for google / microsoft / deepl provider types
  - _map_to_deepl_code()

No network calls are made.  Heavy dependencies (deep_translator,
utils.resilience, utils.security_decorators) are stubbed out before import.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Stub ONLY external / unavailable packages BEFORE importing the module under test.
# Do NOT stub project modules (utils.resilience, utils.security_decorators) —
# those are real importable modules and stubbing them pollutes other test files.
# ---------------------------------------------------------------------------
_STUBS = [
    "deep_translator",
    "deep_translator.exceptions",
]
for _mod in _STUBS:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

_project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / "src"))

from translation.deep_translator_provider import DeepTranslatorProvider  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def make_provider(provider_type: str = "google") -> DeepTranslatorProvider:
    """Instantiate DeepTranslatorProvider bypassing __init__."""
    inst = object.__new__(DeepTranslatorProvider)
    inst.provider_type = provider_type
    inst.logger = MagicMock()
    return inst


@pytest.fixture
def google_provider() -> DeepTranslatorProvider:
    return make_provider("google")


@pytest.fixture
def deepl_provider() -> DeepTranslatorProvider:
    return make_provider("deepl")


@pytest.fixture
def microsoft_provider() -> DeepTranslatorProvider:
    return make_provider("microsoft")


# ---------------------------------------------------------------------------
# TestCommonLanguagesConstant  (8 tests)
# ---------------------------------------------------------------------------

class TestCommonLanguagesConstant:
    """Tests for the COMMON_LANGUAGES class-level constant."""

    def test_is_list(self):
        assert isinstance(DeepTranslatorProvider.COMMON_LANGUAGES, list)

    def test_has_at_least_40_entries(self):
        assert len(DeepTranslatorProvider.COMMON_LANGUAGES) >= 40

    def test_all_entries_are_two_tuples(self):
        for entry in DeepTranslatorProvider.COMMON_LANGUAGES:
            assert isinstance(entry, tuple), f"Expected tuple, got {type(entry)}"
            assert len(entry) == 2, f"Expected 2-tuple, got length {len(entry)}"

    def test_first_element_is_string(self):
        for code, _ in DeepTranslatorProvider.COMMON_LANGUAGES:
            assert isinstance(code, str), f"Language code {code!r} is not a str"

    def test_second_element_is_string(self):
        for _, name in DeepTranslatorProvider.COMMON_LANGUAGES:
            assert isinstance(name, str), f"Language name {name!r} is not a str"

    def test_contains_english(self):
        assert ("en", "English") in DeepTranslatorProvider.COMMON_LANGUAGES

    def test_contains_chinese_simplified(self):
        assert ("zh-CN", "Chinese (Simplified)") in DeepTranslatorProvider.COMMON_LANGUAGES

    def test_contains_arabic(self):
        assert ("ar", "Arabic") in DeepTranslatorProvider.COMMON_LANGUAGES

    def test_all_codes_are_non_empty(self):
        for code, _ in DeepTranslatorProvider.COMMON_LANGUAGES:
            assert code, f"Empty language code found in COMMON_LANGUAGES"


# ---------------------------------------------------------------------------
# TestGetSupportedLanguagesGoogle  (6 tests)
# ---------------------------------------------------------------------------

class TestGetSupportedLanguagesGoogle:
    """get_supported_languages() when provider_type == 'google'."""

    def test_returns_list(self, google_provider):
        result = google_provider.get_supported_languages()
        assert isinstance(result, list)

    def test_returns_same_as_common_languages(self, google_provider):
        result = google_provider.get_supported_languages()
        assert result == DeepTranslatorProvider.COMMON_LANGUAGES

    def test_length_matches_common_languages(self, google_provider):
        result = google_provider.get_supported_languages()
        assert len(result) == len(DeepTranslatorProvider.COMMON_LANGUAGES)

    def test_contains_english(self, google_provider):
        result = google_provider.get_supported_languages()
        assert ("en", "English") in result

    def test_contains_chinese_simplified(self, google_provider):
        result = google_provider.get_supported_languages()
        assert ("zh-CN", "Chinese (Simplified)") in result

    def test_all_entries_are_two_tuples(self, google_provider):
        result = google_provider.get_supported_languages()
        for entry in result:
            assert isinstance(entry, tuple) and len(entry) == 2


# ---------------------------------------------------------------------------
# TestGetSupportedLanguagesMicrosoft  (5 tests)
# ---------------------------------------------------------------------------

class TestGetSupportedLanguagesMicrosoft:
    """get_supported_languages() when provider_type == 'microsoft'."""

    def test_returns_list(self, microsoft_provider):
        result = microsoft_provider.get_supported_languages()
        assert isinstance(result, list)

    def test_equal_to_common_languages(self, microsoft_provider):
        result = microsoft_provider.get_supported_languages()
        assert result == DeepTranslatorProvider.COMMON_LANGUAGES

    def test_length_matches_common_languages(self, microsoft_provider):
        result = microsoft_provider.get_supported_languages()
        assert len(result) == len(DeepTranslatorProvider.COMMON_LANGUAGES)

    def test_contains_spanish(self, microsoft_provider):
        result = microsoft_provider.get_supported_languages()
        assert ("es", "Spanish") in result

    def test_all_entries_are_two_tuples(self, microsoft_provider):
        result = microsoft_provider.get_supported_languages()
        for entry in result:
            assert isinstance(entry, tuple) and len(entry) == 2


# ---------------------------------------------------------------------------
# TestGetSupportedLanguagesDeepL  (8 tests)
# ---------------------------------------------------------------------------

class TestGetSupportedLanguagesDeepL:
    """get_supported_languages() when provider_type == 'deepl'."""

    def test_returns_list(self, deepl_provider):
        result = deepl_provider.get_supported_languages()
        assert isinstance(result, list)

    def test_different_from_common_languages(self, deepl_provider):
        result = deepl_provider.get_supported_languages()
        assert result != DeepTranslatorProvider.COMMON_LANGUAGES

    def test_shorter_than_common_languages(self, deepl_provider):
        result = deepl_provider.get_supported_languages()
        assert len(result) < len(DeepTranslatorProvider.COMMON_LANGUAGES)

    def test_contains_english(self, deepl_provider):
        result = deepl_provider.get_supported_languages()
        assert ("en", "English") in result

    def test_contains_chinese_zh_not_zh_cn(self, deepl_provider):
        result = deepl_provider.get_supported_languages()
        assert ("zh", "Chinese") in result

    def test_does_not_contain_chinese_simplified(self, deepl_provider):
        result = deepl_provider.get_supported_languages()
        assert ("zh-CN", "Chinese (Simplified)") not in result

    def test_contains_german(self, deepl_provider):
        result = deepl_provider.get_supported_languages()
        assert ("de", "German") in result

    def test_has_at_least_25_entries(self, deepl_provider):
        result = deepl_provider.get_supported_languages()
        assert len(result) >= 25

    def test_all_entries_are_two_tuples(self, deepl_provider):
        result = deepl_provider.get_supported_languages()
        for entry in result:
            assert isinstance(entry, tuple) and len(entry) == 2


# ---------------------------------------------------------------------------
# TestMapToDeeplCode  (15 tests)
# ---------------------------------------------------------------------------

class TestMapToDeeplCode:
    """_map_to_deepl_code() covers explicit mappings and passthrough behaviour."""

    # --- Codes with explicit mappings ---

    def test_zh_cn_maps_to_zh(self, google_provider):
        assert google_provider._map_to_deepl_code("zh-CN") == "zh"

    def test_zh_tw_maps_to_zh(self, google_provider):
        assert google_provider._map_to_deepl_code("zh-TW") == "zh"

    def test_no_maps_to_nb(self, google_provider):
        assert google_provider._map_to_deepl_code("no") == "nb"

    def test_pt_br_maps_to_pt_br(self, google_provider):
        assert google_provider._map_to_deepl_code("pt-BR") == "pt-BR"

    def test_pt_pt_maps_to_pt_pt(self, google_provider):
        assert google_provider._map_to_deepl_code("pt-PT") == "pt-PT"

    def test_en_us_maps_to_en_us(self, google_provider):
        assert google_provider._map_to_deepl_code("en-US") == "en-US"

    def test_en_gb_maps_to_en_gb(self, google_provider):
        assert google_provider._map_to_deepl_code("en-GB") == "en-GB"

    # --- Codes NOT in the mapping (returned unchanged) ---

    def test_en_returns_en(self, google_provider):
        assert google_provider._map_to_deepl_code("en") == "en"

    def test_de_returns_de(self, google_provider):
        assert google_provider._map_to_deepl_code("de") == "de"

    def test_fr_returns_fr(self, google_provider):
        assert google_provider._map_to_deepl_code("fr") == "fr"

    def test_es_returns_es(self, google_provider):
        assert google_provider._map_to_deepl_code("es") == "es"

    def test_ja_returns_ja(self, google_provider):
        assert google_provider._map_to_deepl_code("ja") == "ja"

    def test_ko_returns_ko(self, google_provider):
        assert google_provider._map_to_deepl_code("ko") == "ko"

    def test_empty_string_returns_empty_string(self, google_provider):
        assert google_provider._map_to_deepl_code("") == ""

    def test_unknown_code_returns_unchanged(self, google_provider):
        assert google_provider._map_to_deepl_code("unknown_code") == "unknown_code"
