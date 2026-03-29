"""
Tests for src/ai/providers/base.py

Covers get_model_key_for_task — routing logic based on system_message/prompt
keywords. Tests SOAP detection, refine/improve detection, referral/medication
detection, and the default fallback.
No network, no Tkinter, no API calls.
"""

import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.providers.base import get_model_key_for_task


# ===========================================================================
# get_model_key_for_task
# ===========================================================================

class TestGetModelKeyForTask:
    # ----- SOAP detection -----

    def test_soap_in_system_message(self):
        assert get_model_key_for_task("Generate a SOAP note", "") == "soap_note"

    def test_soap_in_prompt(self):
        assert get_model_key_for_task("", "Create a SOAP note for the patient") == "soap_note"

    def test_soap_lowercase_not_matched(self):
        # "soap" (lowercase) does not trigger soap_note — only uppercase "SOAP"
        result = get_model_key_for_task("soap", "")
        assert result != "soap_note"

    def test_soap_in_both(self):
        assert get_model_key_for_task("SOAP", "SOAP") == "soap_note"

    # ----- Refine detection -----

    def test_refine_in_system_message_lowercase(self):
        assert get_model_key_for_task("Please refine this text", "") == "refine_text"

    def test_refine_in_prompt_lowercase(self):
        assert get_model_key_for_task("", "refine the transcript") == "refine_text"

    def test_refine_uppercase_in_system(self):
        assert get_model_key_for_task("REFINE THIS TEXT", "") == "refine_text"

    # ----- Improve detection -----

    def test_improve_in_system_message(self):
        assert get_model_key_for_task("improve the wording", "") == "improve_text"

    def test_improve_in_prompt(self):
        assert get_model_key_for_task("", "improve this sentence") == "improve_text"

    def test_improve_uppercase_in_prompt(self):
        assert get_model_key_for_task("", "IMPROVE this text") == "improve_text"

    # ----- Referral detection -----

    def test_referral_in_system_message(self):
        assert get_model_key_for_task("write a referral letter", "") == "referral"

    def test_referral_in_prompt(self):
        assert get_model_key_for_task("", "create a referral for cardiology") == "referral"

    def test_referral_uppercase(self):
        assert get_model_key_for_task("REFERRAL NOTE", "") == "referral"

    # ----- Medication detection -----

    def test_medication_in_system_message(self):
        assert get_model_key_for_task("check medication interactions", "") == "medication"

    def test_medication_in_prompt(self):
        assert get_model_key_for_task("", "list the patient's medication") == "medication"

    def test_drug_in_system_message(self):
        assert get_model_key_for_task("review drug interactions", "") == "medication"

    def test_drug_in_prompt(self):
        assert get_model_key_for_task("", "check for drug contraindications") == "medication"

    # ----- Default fallback -----

    def test_empty_messages_default(self):
        assert get_model_key_for_task("", "") == "improve_text"

    def test_unrelated_topic_default(self):
        assert get_model_key_for_task("summarize the patient chart", "") == "improve_text"

    def test_returns_string(self):
        result = get_model_key_for_task("some system message", "some prompt")
        assert isinstance(result, str)

    # ----- Priority ordering -----

    def test_soap_takes_priority_over_refine(self):
        # Both "SOAP" and "refine" present — SOAP should win (checked first)
        result = get_model_key_for_task("SOAP note and refine text", "")
        assert result == "soap_note"

    def test_refine_takes_priority_over_improve(self):
        # "refine" checked before "improve"
        result = get_model_key_for_task("refine and improve this", "")
        assert result == "refine_text"
