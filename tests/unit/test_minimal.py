#!/usr/bin/env python3
"""
Minimal smoke tests for Medical Assistant.

These tests verify that core modules can be imported and basic functionality works.
They don't require external dependencies like audio hardware or API keys.
"""

import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest


class TestCoreImports:
    """Test that core modules can be imported."""

    def test_import_settings(self):
        """Test settings module can be imported."""
        from settings.settings import SETTINGS
        assert SETTINGS is not None
        assert isinstance(SETTINGS, dict)

    def test_import_prompts(self):
        """Test prompts module can be imported."""
        from ai.prompts import SOAP_PROMPT_TEMPLATE, get_soap_system_message
        assert SOAP_PROMPT_TEMPLATE is not None
        assert callable(get_soap_system_message)

    def test_import_ui_constants(self):
        """Test UI constants can be imported."""
        from ui.ui_constants import Icons, SidebarConfig, Fonts
        assert Icons is not None
        assert SidebarConfig is not None

    @pytest.mark.requires_audio
    def test_import_audio_state_manager(self):
        """Test audio state manager can be imported."""
        pytest.importorskip("pydub")
        pytest.importorskip("numpy")
        from audio.audio_state_manager import AudioStateManager, RecordingState
        assert AudioStateManager is not None
        assert RecordingState is not None


class TestUtilsImports:
    """Test that utility modules can be imported."""

    def test_import_validation(self):
        """Test validation module can be imported."""
        from utils.validation import validate_api_key, safe_filename
        assert callable(validate_api_key)
        assert callable(safe_filename)

    def test_import_exceptions(self):
        """Test exceptions module can be imported."""
        from utils.exceptions import APIError, RateLimitError
        assert APIError is not None
        assert RateLimitError is not None

    def test_import_resilience(self):
        """Test resilience module can be imported."""
        from utils.resilience import retry, CircuitBreaker
        assert callable(retry)
        assert CircuitBreaker is not None


class TestSOAPPromptStructure:
    """Test SOAP prompt has expected structure."""

    def test_soap_prompt_contains_required_sections(self):
        """Test SOAP system message contains all required sections."""
        from ai.prompts import get_soap_system_message

        system_message = get_soap_system_message("ICD-10")

        # Check for required section headers
        required_sections = [
            "Subjective",
            "Objective",
            "Assessment",
            "Differential Diagnosis",
            "Plan",
            "Follow up",
        ]

        for section in required_sections:
            assert section in system_message, f"Missing section: {section}"

    def test_soap_prompt_icd_versions(self):
        """Test SOAP prompt handles different ICD versions."""
        from ai.prompts import get_soap_system_message

        icd9_msg = get_soap_system_message("ICD-9")
        icd10_msg = get_soap_system_message("ICD-10")
        both_msg = get_soap_system_message("both")

        assert "ICD-9" in icd9_msg
        assert "ICD-10" in icd10_msg
        assert "ICD-9" in both_msg and "ICD-10" in both_msg


class TestBasicFunctionality:
    """Test basic functionality without external dependencies."""

    def test_safe_filename_generation(self):
        """Test safe filename generation."""
        from utils.validation import safe_filename

        # Test normal names
        assert safe_filename("document.txt") == "document.txt"

        # Test names with invalid characters
        result = safe_filename("file<>name.txt")
        assert "<" not in result
        assert ">" not in result

        # Test empty names
        assert safe_filename("") == "unnamed"

    @pytest.mark.requires_audio
    def test_recording_state_enum(self):
        """Test RecordingState enum values."""
        pytest.importorskip("pydub")
        pytest.importorskip("numpy")
        from audio.audio_state_manager import RecordingState

        assert RecordingState.IDLE.value == "idle"
        assert RecordingState.RECORDING.value == "recording"
        assert RecordingState.PAUSED.value == "paused"
        assert RecordingState.PROCESSING.value == "processing"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
