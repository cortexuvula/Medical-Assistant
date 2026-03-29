"""
Tests for src/ai/prompts.py

Covers module-level string constants (type, non-empty), ICD_CODE_INSTRUCTIONS
structure, SOAP_PROVIDERS and SOAP_PROVIDER_NAMES, and the pure function
get_soap_system_message() (ICD-9/10/both, invalid fallback, anthropic branch).
No network, no Tkinter, no file I/O.
"""

import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.prompts import (
    REFINE_PROMPT,
    REFINE_SYSTEM_MESSAGE,
    IMPROVE_PROMPT,
    IMPROVE_SYSTEM_MESSAGE,
    SOAP_PROMPT_TEMPLATE,
    SOAP_PROVIDERS,
    SOAP_PROVIDER_NAMES,
    ICD_CODE_INSTRUCTIONS,
    get_soap_system_message,
    SOAP_SYSTEM_MESSAGE,
)
from utils.constants import (
    PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_OLLAMA,
    PROVIDER_GEMINI, PROVIDER_GROQ, PROVIDER_CEREBRAS,
)


# ===========================================================================
# Module-level string constants
# ===========================================================================

class TestStringConstants:
    def test_refine_prompt_is_string(self):
        assert isinstance(REFINE_PROMPT, str)

    def test_refine_prompt_non_empty(self):
        assert len(REFINE_PROMPT.strip()) > 0

    def test_refine_system_message_is_string(self):
        assert isinstance(REFINE_SYSTEM_MESSAGE, str)

    def test_refine_system_message_non_empty(self):
        assert len(REFINE_SYSTEM_MESSAGE.strip()) > 0

    def test_improve_prompt_is_string(self):
        assert isinstance(IMPROVE_PROMPT, str)

    def test_improve_prompt_non_empty(self):
        assert len(IMPROVE_PROMPT.strip()) > 0

    def test_improve_system_message_is_string(self):
        assert isinstance(IMPROVE_SYSTEM_MESSAGE, str)

    def test_improve_system_message_non_empty(self):
        assert len(IMPROVE_SYSTEM_MESSAGE.strip()) > 0

    def test_soap_prompt_template_is_string(self):
        assert isinstance(SOAP_PROMPT_TEMPLATE, str)

    def test_soap_prompt_template_contains_text_placeholder(self):
        assert "{text}" in SOAP_PROMPT_TEMPLATE

    def test_soap_system_message_is_string(self):
        assert isinstance(SOAP_SYSTEM_MESSAGE, str)

    def test_soap_system_message_non_empty(self):
        assert len(SOAP_SYSTEM_MESSAGE.strip()) > 0


# ===========================================================================
# ICD_CODE_INSTRUCTIONS
# ===========================================================================

class TestICDCodeInstructions:
    def test_is_dict(self):
        assert isinstance(ICD_CODE_INSTRUCTIONS, dict)

    def test_has_icd9_key(self):
        assert "ICD-9" in ICD_CODE_INSTRUCTIONS

    def test_has_icd10_key(self):
        assert "ICD-10" in ICD_CODE_INSTRUCTIONS

    def test_has_both_key(self):
        assert "both" in ICD_CODE_INSTRUCTIONS

    def test_three_keys_total(self):
        assert len(ICD_CODE_INSTRUCTIONS) == 3

    def test_all_values_are_tuples(self):
        for key, value in ICD_CODE_INSTRUCTIONS.items():
            assert isinstance(value, tuple), f"'{key}' value is not a tuple"

    def test_all_tuples_have_two_elements(self):
        for key, value in ICD_CODE_INSTRUCTIONS.items():
            assert len(value) == 2, f"'{key}' tuple does not have 2 elements"

    def test_all_tuple_elements_are_strings(self):
        for key, (instruction, label) in ICD_CODE_INSTRUCTIONS.items():
            assert isinstance(instruction, str)
            assert isinstance(label, str)

    def test_icd9_instruction_non_empty(self):
        instruction, _ = ICD_CODE_INSTRUCTIONS["ICD-9"]
        assert len(instruction.strip()) > 0

    def test_icd10_label_contains_icd10(self):
        _, label = ICD_CODE_INSTRUCTIONS["ICD-10"]
        assert "ICD-10" in label

    def test_both_label_contains_both_versions(self):
        _, label = ICD_CODE_INSTRUCTIONS["both"]
        assert "ICD-9" in label and "ICD-10" in label


# ===========================================================================
# SOAP_PROVIDERS and SOAP_PROVIDER_NAMES
# ===========================================================================

class TestSOAPProviders:
    def test_soap_providers_is_list(self):
        assert isinstance(SOAP_PROVIDERS, list)

    def test_soap_providers_six_entries(self):
        assert len(SOAP_PROVIDERS) == 6

    def test_openai_in_providers(self):
        assert PROVIDER_OPENAI in SOAP_PROVIDERS

    def test_anthropic_in_providers(self):
        assert PROVIDER_ANTHROPIC in SOAP_PROVIDERS

    def test_ollama_in_providers(self):
        assert PROVIDER_OLLAMA in SOAP_PROVIDERS

    def test_gemini_in_providers(self):
        assert PROVIDER_GEMINI in SOAP_PROVIDERS

    def test_groq_in_providers(self):
        assert PROVIDER_GROQ in SOAP_PROVIDERS

    def test_cerebras_in_providers(self):
        assert PROVIDER_CEREBRAS in SOAP_PROVIDERS

    def test_all_providers_are_strings(self):
        for p in SOAP_PROVIDERS:
            assert isinstance(p, str)

    def test_soap_provider_names_is_dict(self):
        assert isinstance(SOAP_PROVIDER_NAMES, dict)

    def test_provider_names_six_entries(self):
        assert len(SOAP_PROVIDER_NAMES) == 6

    def test_openai_display_name(self):
        assert SOAP_PROVIDER_NAMES[PROVIDER_OPENAI] == "OpenAI"

    def test_anthropic_display_name(self):
        assert SOAP_PROVIDER_NAMES[PROVIDER_ANTHROPIC] == "Anthropic"

    def test_all_display_names_are_strings(self):
        for provider, name in SOAP_PROVIDER_NAMES.items():
            assert isinstance(name, str)

    def test_all_display_names_non_empty(self):
        for provider, name in SOAP_PROVIDER_NAMES.items():
            assert len(name.strip()) > 0


# ===========================================================================
# get_soap_system_message
# ===========================================================================

class TestGetSOAPSystemMessage:
    def test_returns_string(self):
        assert isinstance(get_soap_system_message(), str)

    def test_default_icd9_non_empty(self):
        assert len(get_soap_system_message().strip()) > 0

    def test_icd9_explicit_returns_string(self):
        assert isinstance(get_soap_system_message("ICD-9"), str)

    def test_icd10_returns_string(self):
        assert isinstance(get_soap_system_message("ICD-10"), str)

    def test_both_returns_string(self):
        assert isinstance(get_soap_system_message("both"), str)

    def test_icd10_message_different_from_icd9(self):
        icd9 = get_soap_system_message("ICD-9")
        icd10 = get_soap_system_message("ICD-10")
        assert icd9 != icd10

    def test_both_message_different_from_icd9(self):
        icd9 = get_soap_system_message("ICD-9")
        both = get_soap_system_message("both")
        assert icd9 != both

    def test_invalid_version_falls_back_to_icd9(self):
        invalid = get_soap_system_message("INVALID_VERSION")
        default = get_soap_system_message("ICD-9")
        assert invalid == default

    def test_icd10_label_appears_in_icd10_message(self):
        _, label = ICD_CODE_INSTRUCTIONS["ICD-10"]
        msg = get_soap_system_message("ICD-10")
        # The label format string parts appear in the result
        assert "ICD-10" in msg

    def test_both_labels_appear_in_both_message(self):
        msg = get_soap_system_message("both")
        assert "ICD-9" in msg
        assert "ICD-10" in msg

    def test_anthropic_provider_returns_string(self):
        result = get_soap_system_message("ICD-9", provider=PROVIDER_ANTHROPIC)
        assert isinstance(result, str)

    def test_anthropic_message_different_from_default(self):
        default = get_soap_system_message("ICD-9")
        anthropic = get_soap_system_message("ICD-9", provider=PROVIDER_ANTHROPIC)
        assert default != anthropic

    def test_anthropic_message_non_empty(self):
        result = get_soap_system_message("ICD-10", provider=PROVIDER_ANTHROPIC)
        assert len(result.strip()) > 0

    def test_openai_provider_uses_default_template(self):
        openai_msg = get_soap_system_message("ICD-9", provider=PROVIDER_OPENAI)
        default_msg = get_soap_system_message("ICD-9", provider=None)
        assert openai_msg == default_msg

    def test_ollama_provider_uses_default_template(self):
        ollama_msg = get_soap_system_message("ICD-9", provider=PROVIDER_OLLAMA)
        default_msg = get_soap_system_message("ICD-9", provider=None)
        assert ollama_msg == default_msg

    def test_none_provider_same_as_no_provider(self):
        with_none = get_soap_system_message("ICD-9", provider=None)
        without = get_soap_system_message("ICD-9")
        assert with_none == without

    def test_anthropic_icd10_returns_icd10_content(self):
        result = get_soap_system_message("ICD-10", provider=PROVIDER_ANTHROPIC)
        assert "ICD-10" in result
