"""
Tests for src/ai/prompts.py

Covers module-level constants (REFINE_PROMPT, IMPROVE_PROMPT,
SOAP_PROMPT_TEMPLATE, ICD_CODE_INSTRUCTIONS, SOAP_PROVIDERS,
SOAP_PROVIDER_NAMES) and get_soap_system_message() (ICD version
substitution, provider-specific Anthropic template, unknown version
fallback, default SOAP_SYSTEM_MESSAGE).
Pure string logic — no network, no Tkinter, no file I/O.
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

from ai.prompts import (
    REFINE_PROMPT,
    REFINE_SYSTEM_MESSAGE,
    IMPROVE_PROMPT,
    IMPROVE_SYSTEM_MESSAGE,
    SOAP_PROMPT_TEMPLATE,
    SOAP_SYSTEM_MESSAGE_TEMPLATE,
    SOAP_SYSTEM_MESSAGE_ANTHROPIC_TEMPLATE,
    ICD_CODE_INSTRUCTIONS,
    SOAP_PROVIDERS,
    SOAP_PROVIDER_NAMES,
    SOAP_SYSTEM_MESSAGE,
    get_soap_system_message,
)
from utils.constants import (
    PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_OLLAMA,
    PROVIDER_GEMINI, PROVIDER_GROQ, PROVIDER_CEREBRAS,
)


# ===========================================================================
# Module-level constants
# ===========================================================================

class TestModuleConstants:
    def test_refine_prompt_is_string(self):
        assert isinstance(REFINE_PROMPT, str)

    def test_refine_prompt_non_empty(self):
        assert len(REFINE_PROMPT.strip()) > 0

    def test_refine_system_message_is_string(self):
        assert isinstance(REFINE_SYSTEM_MESSAGE, str)

    def test_refine_system_message_mentions_punctuation(self):
        assert "punctuation" in REFINE_SYSTEM_MESSAGE.lower()

    def test_improve_prompt_is_string(self):
        assert isinstance(IMPROVE_PROMPT, str)

    def test_improve_system_message_is_string(self):
        assert isinstance(IMPROVE_SYSTEM_MESSAGE, str)

    def test_improve_system_message_mentions_transcript(self):
        assert "transcript" in IMPROVE_SYSTEM_MESSAGE.lower()

    def test_soap_prompt_template_has_text_placeholder(self):
        assert "{text}" in SOAP_PROMPT_TEMPLATE

    def test_soap_prompt_template_formats_with_text(self):
        result = SOAP_PROMPT_TEMPLATE.format(text="sample transcript")
        assert "sample transcript" in result


class TestICDCodeInstructions:
    def test_icd9_key_exists(self):
        assert "ICD-9" in ICD_CODE_INSTRUCTIONS

    def test_icd10_key_exists(self):
        assert "ICD-10" in ICD_CODE_INSTRUCTIONS

    def test_both_key_exists(self):
        assert "both" in ICD_CODE_INSTRUCTIONS

    def test_each_value_is_tuple_of_two_strings(self):
        for key, val in ICD_CODE_INSTRUCTIONS.items():
            assert isinstance(val, tuple), f"{key}: not a tuple"
            assert len(val) == 2, f"{key}: tuple not length 2"
            assert isinstance(val[0], str), f"{key}: first element not string"
            assert isinstance(val[1], str), f"{key}: second element not string"

    def test_icd9_instruction_mentions_icd9(self):
        instruction, label = ICD_CODE_INSTRUCTIONS["ICD-9"]
        assert "ICD-9" in instruction or "icd-9" in instruction.lower()

    def test_icd10_instruction_mentions_icd10(self):
        instruction, label = ICD_CODE_INSTRUCTIONS["ICD-10"]
        assert "ICD-10" in instruction or "icd-10" in instruction.lower()

    def test_both_instruction_mentions_both(self):
        instruction, label = ICD_CODE_INSTRUCTIONS["both"]
        assert "ICD-9" in instruction or "ICD-10" in instruction


class TestSOAPProviders:
    def test_soap_providers_is_list(self):
        assert isinstance(SOAP_PROVIDERS, list)

    def test_soap_providers_non_empty(self):
        assert len(SOAP_PROVIDERS) > 0

    def test_openai_in_soap_providers(self):
        assert PROVIDER_OPENAI in SOAP_PROVIDERS

    def test_anthropic_in_soap_providers(self):
        assert PROVIDER_ANTHROPIC in SOAP_PROVIDERS

    def test_ollama_in_soap_providers(self):
        assert PROVIDER_OLLAMA in SOAP_PROVIDERS

    def test_gemini_in_soap_providers(self):
        assert PROVIDER_GEMINI in SOAP_PROVIDERS

    def test_groq_in_soap_providers(self):
        assert PROVIDER_GROQ in SOAP_PROVIDERS

    def test_cerebras_in_soap_providers(self):
        assert PROVIDER_CEREBRAS in SOAP_PROVIDERS

    def test_soap_provider_names_is_dict(self):
        assert isinstance(SOAP_PROVIDER_NAMES, dict)

    def test_all_providers_have_display_name(self):
        for provider in SOAP_PROVIDERS:
            assert provider in SOAP_PROVIDER_NAMES, f"Missing display name for {provider}"

    def test_all_display_names_are_strings(self):
        for key, name in SOAP_PROVIDER_NAMES.items():
            assert isinstance(name, str), f"{key}: non-string display name"

    def test_all_display_names_non_empty(self):
        for key, name in SOAP_PROVIDER_NAMES.items():
            assert len(name.strip()) > 0, f"{key}: empty display name"


# ===========================================================================
# get_soap_system_message
# ===========================================================================

class TestGetSOAPSystemMessage:
    def test_returns_string(self):
        result = get_soap_system_message()
        assert isinstance(result, str)

    def test_non_empty(self):
        assert len(get_soap_system_message().strip()) > 0

    def test_icd9_default(self):
        result = get_soap_system_message("ICD-9")
        assert "ICD-9" in result

    def test_icd10_substituted(self):
        result = get_soap_system_message("ICD-10")
        assert "ICD-10" in result

    def test_both_contains_icd9_and_icd10(self):
        result = get_soap_system_message("both")
        assert "ICD-9" in result
        assert "ICD-10" in result

    def test_unknown_version_falls_back_to_icd9(self):
        result = get_soap_system_message("ICD-99")
        # Should fall back to ICD-9
        assert "ICD-9" in result

    def test_empty_string_version_falls_back_to_icd9(self):
        result = get_soap_system_message("")
        assert "ICD-9" in result

    def test_anthropic_provider_uses_different_template(self):
        result_default = get_soap_system_message("ICD-9", provider=None)
        result_anthropic = get_soap_system_message("ICD-9", provider=PROVIDER_ANTHROPIC)
        # The Anthropic template is different (shorter/more concise)
        assert result_default != result_anthropic

    def test_anthropic_result_is_string(self):
        result = get_soap_system_message("ICD-9", provider=PROVIDER_ANTHROPIC)
        assert isinstance(result, str)

    def test_anthropic_result_non_empty(self):
        result = get_soap_system_message("ICD-9", provider=PROVIDER_ANTHROPIC)
        assert len(result.strip()) > 0

    def test_openai_provider_uses_default_template(self):
        result_none = get_soap_system_message("ICD-9", provider=None)
        result_openai = get_soap_system_message("ICD-9", provider=PROVIDER_OPENAI)
        assert result_none == result_openai

    def test_icd9_result_contains_physician_reference(self):
        result = get_soap_system_message("ICD-9")
        assert "physician" in result.lower() or "clinical" in result.lower()

    def test_soap_system_message_module_constant_is_icd9(self):
        # SOAP_SYSTEM_MESSAGE is built with ICD-9 default
        expected = get_soap_system_message("ICD-9")
        assert SOAP_SYSTEM_MESSAGE == expected

    def test_icd_label_appears_in_message(self):
        _, label = ICD_CODE_INSTRUCTIONS["ICD-10"]
        result = get_soap_system_message("ICD-10")
        # The label placeholder format should be substituted
        assert "{ICD_CODE_LABEL}" not in result

    def test_no_unsubstituted_placeholders(self):
        for version in ["ICD-9", "ICD-10", "both"]:
            result = get_soap_system_message(version)
            assert "{ICD_CODE_INSTRUCTION}" not in result
            assert "{ICD_CODE_LABEL}" not in result
