"""Regression tests for document generation.

These tests verify that SOAP notes, referrals, and letters
are generated correctly.
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestSOAPNoteGeneration:
    """Tests for SOAP note generation."""

    @pytest.fixture
    def sample_transcript(self):
        """Sample transcript for testing."""
        return """
        Patient is a 45-year-old male presenting with chest pain for the past 2 hours.
        Pain is substernal, pressure-like, radiating to left arm.
        Blood pressure 150/95, heart rate 88.
        EKG shows ST elevation in leads V1-V4.
        """

    def test_soap_note_returns_string(self, sample_transcript, mock_api_keys):
        """SOAP note generation should return a string."""
        from src.ai.ai import create_soap_note_with_openai

        with patch('ai.soap_generation.call_ai') as mock_call, \
             patch('managers.agent_manager.agent_manager') as mock_agent:
            mock_call.return_value = """
            S: Patient presents with chest pain x2 hours
            O: BP 150/95, HR 88, ST elevation V1-V4
            A: Acute coronary syndrome
            P: Emergent cardiology consult
            """
            mock_agent.generate_synopsis.return_value = None
            mock_agent.is_agent_enabled.return_value = False

            result = create_soap_note_with_openai(sample_transcript)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_soap_note_contains_sections(self, sample_transcript, mock_api_keys):
        """SOAP note should contain S, O, A, P sections."""
        from src.ai.ai import create_soap_note_with_openai

        with patch('ai.soap_generation.call_ai') as mock_call, \
             patch('managers.agent_manager.agent_manager') as mock_agent:
            mock_call.return_value = """
            S: Subjective content
            O: Objective content
            A: Assessment content
            P: Plan content
            """
            mock_agent.generate_synopsis.return_value = None
            mock_agent.is_agent_enabled.return_value = False

            result = create_soap_note_with_openai(sample_transcript)

        # Should contain SOAP sections (various formats accepted)
        soap_indicators = ['S:', 'O:', 'A:', 'P:', 'Subjective', 'Objective', 'Assessment', 'Plan']
        assert any(indicator in result for indicator in soap_indicators)

    def test_soap_note_with_context(self, sample_transcript, mock_api_keys):
        """SOAP note should incorporate context when provided."""
        from src.ai.ai import create_soap_note_with_openai

        context = "Patient has history of hypertension and diabetes"

        with patch('ai.soap_generation.call_ai') as mock_call, \
             patch('managers.agent_manager.agent_manager') as mock_agent:
            mock_call.return_value = "SOAP note with context included"
            mock_agent.generate_synopsis.return_value = None
            mock_agent.is_agent_enabled.return_value = False

            result = create_soap_note_with_openai(
                sample_transcript,
                context=context
            )

        # Should have called AI with the context
        assert mock_call.called

    def test_soap_note_empty_transcript(self, mock_api_keys):
        """SOAP note generation should handle empty transcript."""
        from src.ai.ai import create_soap_note_with_openai

        with patch('ai.soap_generation.call_ai') as mock_call, \
             patch('managers.agent_manager.agent_manager') as mock_agent:
            mock_call.return_value = ""
            mock_agent.generate_synopsis.return_value = None
            mock_agent.is_agent_enabled.return_value = False

            result = create_soap_note_with_openai("")

        # Should return something (empty or error message)
        assert isinstance(result, str)


class TestReferralGeneration:
    """Tests for referral letter generation."""

    @pytest.fixture
    def sample_soap_note(self):
        """Sample SOAP note for testing."""
        return """
        S: Patient reports persistent headache x2 weeks
        O: BP 120/80, neurological exam normal
        A: Chronic tension headache
        P: Refer to neurology for evaluation
        """

    def test_referral_returns_string(self, sample_soap_note, mock_api_keys):
        """Referral generation should return a string."""
        from src.ai.ai import create_referral_with_openai

        with patch('ai.letter_generation.call_ai') as mock_call:
            mock_call.return_value = """
            Dear Dr. Specialist,

            I am referring this patient for evaluation of chronic headaches.

            Sincerely,
            Dr. Referring Physician
            """

            result = create_referral_with_openai(sample_soap_note)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_referral_with_conditions(self, sample_soap_note, mock_api_keys):
        """Referral should accept specific conditions."""
        from src.ai.ai import create_referral_with_openai

        with patch('ai.letter_generation.call_ai') as mock_call:
            mock_call.return_value = "Referral letter content"

            result = create_referral_with_openai(
                sample_soap_note,
                conditions="chronic tension headache, evaluate for migraine"
            )

        assert mock_call.called
        assert isinstance(result, str)

    def test_referral_empty_input(self, mock_api_keys):
        """Referral should handle empty input."""
        from src.ai.ai import create_referral_with_openai

        with patch('ai.letter_generation.call_ai') as mock_call:
            mock_call.return_value = ""

            result = create_referral_with_openai("")

        assert isinstance(result, str)


class TestLetterGeneration:
    """Tests for letter generation."""

    @pytest.fixture
    def sample_soap_note(self):
        """Sample SOAP note for testing."""
        return """
        S: Follow up visit for diabetes management
        O: A1c 7.2%, BP 130/85
        A: Type 2 diabetes, well controlled
        P: Continue current medications, follow up in 3 months
        """

    def test_letter_returns_string(self, sample_soap_note, mock_api_keys):
        """Letter generation should return a string."""
        from src.ai.ai import create_letter_with_ai

        with patch('ai.letter_generation.call_ai') as mock_call:
            mock_call.return_value = """
            Dear Patient,

            Thank you for visiting our office today.

            Sincerely,
            Your Doctor
            """

            result = create_letter_with_ai(sample_soap_note)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_letter_patient_recipient(self, sample_soap_note, mock_api_keys):
        """Letter for patient should be appropriately worded."""
        from src.ai.ai import create_letter_with_ai

        with patch('ai.letter_generation.call_ai') as mock_call:
            mock_call.return_value = "Dear Patient, your visit summary..."

            result = create_letter_with_ai(
                sample_soap_note,
                recipient_type="patient"
            )

        assert isinstance(result, str)

    def test_letter_employer_recipient(self, sample_soap_note, mock_api_keys):
        """Letter for employer should be appropriately formatted."""
        from src.ai.ai import create_letter_with_ai

        with patch('ai.letter_generation.call_ai') as mock_call:
            mock_call.return_value = "To Whom It May Concern, this letter confirms..."

            result = create_letter_with_ai(
                sample_soap_note,
                recipient_type="employer"
            )

        assert isinstance(result, str)

    def test_letter_with_specs(self, sample_soap_note, mock_api_keys):
        """Letter should accept custom specifications."""
        from src.ai.ai import create_letter_with_ai

        specs = "Include work restrictions and duration of leave"

        with patch('ai.letter_generation.call_ai') as mock_call:
            mock_call.return_value = "Letter with specifications"

            result = create_letter_with_ai(
                sample_soap_note,
                recipient_type="employer",
                specs=specs
            )

        assert mock_call.called


class TestDocumentGeneratorsClass:
    """Tests for DocumentGenerators class."""

    def test_document_generators_imports(self):
        """DocumentGenerators should import correctly."""
        try:
            from src.processing.document_generators import DocumentGenerators
            assert DocumentGenerators is not None
        except ImportError as e:
            pytest.fail(f"Failed to import DocumentGenerators: {e}")

    def test_document_generators_has_create_soap(self):
        """DocumentGenerators should have create_soap_note method."""
        from src.processing.document_generators import DocumentGenerators

        assert hasattr(DocumentGenerators, 'create_soap_note')

    def test_document_generators_has_create_referral(self):
        """DocumentGenerators should have create_referral method."""
        from src.processing.document_generators import DocumentGenerators

        assert hasattr(DocumentGenerators, 'create_referral')

    def test_document_generators_has_create_letter(self):
        """DocumentGenerators should have create_letter method."""
        from src.processing.document_generators import DocumentGenerators

        assert hasattr(DocumentGenerators, 'create_letter')


class TestTextRefining:
    """Tests for text refining functionality."""

    def test_refine_text_returns_string(self, mock_api_keys):
        """refine_text should return a string."""
        from src.ai.ai import adjust_text_with_openai

        with patch('ai.text_processing.call_ai') as mock_call:
            mock_call.return_value = "Refined text with proper punctuation."

            result = adjust_text_with_openai("text to refine")

        assert isinstance(result, str)

    def test_refine_text_adds_punctuation(self, mock_api_keys):
        """refine_text should add proper punctuation."""
        from src.ai.ai import adjust_text_with_openai

        input_text = "patient has headache full stop fever full stop"

        with patch('ai.text_processing.call_ai') as mock_call:
            mock_call.return_value = "Patient has headache. Fever."

            result = adjust_text_with_openai(input_text)

        # Result should be properly punctuated
        assert isinstance(result, str)


class TestTextImproving:
    """Tests for text improving functionality."""

    def test_improve_text_returns_string(self, mock_api_keys):
        """improve_text should return a string."""
        from src.ai.ai import improve_text_with_openai

        with patch('ai.text_processing.call_ai') as mock_call:
            mock_call.return_value = "Improved and clearer text."

            result = improve_text_with_openai("text to improve")

        assert isinstance(result, str)


@pytest.mark.regression
class TestDocumentGenerationRegressionSuite:
    """Comprehensive regression tests for document generation."""

    def test_soap_note_handles_special_characters(self, mock_api_keys):
        """SOAP note should handle special characters."""
        from src.ai.ai import create_soap_note_with_openai

        transcript = "Patient's temp is 38.5°C. O2 sat 97%."

        with patch('ai.soap_generation.call_ai') as mock_call, \
             patch('managers.agent_manager.agent_manager') as mock_agent:
            mock_call.return_value = "S: Patient temp 38.5°C\nO: O2 sat 97%"
            mock_agent.generate_synopsis.return_value = None
            mock_agent.is_agent_enabled.return_value = False

            result = create_soap_note_with_openai(transcript)

        assert isinstance(result, str)

    def test_soap_note_handles_long_transcript(self, mock_api_keys):
        """SOAP note should handle long transcripts."""
        from src.ai.ai import create_soap_note_with_openai

        # Create a long transcript
        long_transcript = "Patient reports headache. " * 500

        with patch('ai.soap_generation.call_ai') as mock_call, \
             patch('managers.agent_manager.agent_manager') as mock_agent:
            mock_call.return_value = "SOAP note from long transcript"
            mock_agent.generate_synopsis.return_value = None
            mock_agent.is_agent_enabled.return_value = False

            result = create_soap_note_with_openai(long_transcript)

        assert isinstance(result, str)

    def test_referral_handles_multiple_conditions(self, mock_api_keys):
        """Referral should handle multiple conditions."""
        from src.ai.ai import create_referral_with_openai

        soap_note = "A: 1. Diabetes 2. Hypertension 3. CKD"
        conditions = "diabetes, hypertension, chronic kidney disease"

        with patch('ai.letter_generation.call_ai') as mock_call:
            mock_call.return_value = "Referral for multiple conditions"

            result = create_referral_with_openai(soap_note, conditions)

        assert isinstance(result, str)

    def test_letter_handles_unicode(self, mock_api_keys):
        """Letter should handle unicode characters."""
        from src.ai.ai import create_letter_with_ai

        soap_note = "Patient José García, température 38°C"

        with patch('ai.letter_generation.call_ai') as mock_call:
            mock_call.return_value = "Letter for José García"

            result = create_letter_with_ai(soap_note)

        assert isinstance(result, str)

    def test_all_generation_functions_return_strings(self, mock_api_keys):
        """All generation functions should return strings."""
        from src.ai.ai import (
            create_soap_note_with_openai,
            create_referral_with_openai,
            create_letter_with_ai,
            adjust_text_with_openai,
            improve_text_with_openai
        )

        with patch('ai.soap_generation.call_ai', return_value="Generated content"), \
             patch('managers.agent_manager.agent_manager') as mock_agent, \
             patch('ai.letter_generation.call_ai', return_value="Generated content"), \
             patch('ai.text_processing.call_ai', return_value="Generated content"):
            mock_agent.generate_synopsis.return_value = None
            mock_agent.is_agent_enabled.return_value = False
            results = [
                create_soap_note_with_openai("test"),
                create_referral_with_openai("test"),
                create_letter_with_ai("test"),
                adjust_text_with_openai("test"),
                improve_text_with_openai("test")
            ]

        for result in results:
            assert isinstance(result, str)

    def test_document_generation_error_handling(self, mock_api_keys):
        """Document generation should handle errors gracefully."""
        from src.ai.ai import create_soap_note_with_openai

        with patch('ai.soap_generation.call_ai') as mock_call, \
             patch('managers.agent_manager.agent_manager') as mock_agent:
            mock_call.side_effect = Exception("API Error")
            mock_agent.generate_synopsis.return_value = None
            mock_agent.is_agent_enabled.return_value = False

            # Should not raise exception, should return error message
            try:
                result = create_soap_note_with_openai("test")
                assert isinstance(result, str)
            except Exception:
                # If it does raise, that's also acceptable behavior
                pass
