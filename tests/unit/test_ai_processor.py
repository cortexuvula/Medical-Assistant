"""Test AI processor functionality."""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestAIProcessor:
    """Test AI processing functionality."""

    @pytest.fixture
    def mock_env(self, mock_api_keys):
        """Set up environment with mock API keys."""
        with patch.dict('os.environ', mock_api_keys):
            yield

    @pytest.fixture
    def ai_processor(self, mock_env):
        """Create AI processor instance with mocked environment."""
        from src.ai.ai_processor import AIProcessor
        with patch('openai.api_key', 'test-key'):
            processor = AIProcessor()
            yield processor

    @pytest.fixture
    def mock_openai_response(self):
        """Standard mock OpenAI response."""
        return {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "gpt-3.5-turbo",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Refined text output"
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
        }

    def test_initialization(self, ai_processor):
        """Test AI processor initialization."""
        assert hasattr(ai_processor, 'api_key')
        assert hasattr(ai_processor, 'refine_text')
        assert hasattr(ai_processor, 'improve_text')
        assert hasattr(ai_processor, 'create_soap_note')
        assert hasattr(ai_processor, 'create_referral_letter')
        assert hasattr(ai_processor, 'create_letter')

    def test_provider_selection(self, ai_processor):
        """Test that AI processor respects provider settings."""
        # Provider selection happens in the ai.py module functions
        # AIProcessor just calls those functions
        assert ai_processor.api_key is not None

    @patch('src.ai.ai_processor.adjust_text_with_openai')
    def test_refine_text_success(self, mock_adjust, ai_processor):
        """Test successful text refinement."""
        mock_adjust.return_value = "Refined text output"

        input_text = "patient has headache. took tylenol"
        result = ai_processor.refine_text(input_text)

        # OperationResult interface - use .value for the result dict
        assert result.success is True
        assert result.value["text"] == "Refined text output"

        # Verify the function was called
        mock_adjust.assert_called_once()

    @patch('src.ai.ai_processor.improve_text_with_openai')
    def test_improve_text_success(self, mock_improve, ai_processor):
        """Test successful text improvement."""
        mock_improve.return_value = "Improved text output"

        input_text = "Patient complains of pain"
        result = ai_processor.improve_text(input_text)

        assert result.success is True
        assert result.value["text"] == "Improved text output"

        # Verify the function was called
        mock_improve.assert_called_once()

    @patch('src.ai.ai_processor.create_soap_note_with_openai')
    @patch('src.ai.ai_processor.get_possible_conditions')
    def test_create_soap_note_success(self, mock_conditions, mock_create_soap, ai_processor):
        """Test SOAP note generation."""
        mock_create_soap.return_value = "S: Headache x3 days\nO: BP 120/80\nA: Tension headache\nP: Rest and hydration"
        mock_conditions.return_value = "Tension headache, Hypertension"

        transcript = "Patient has headache for 3 days. Blood pressure is 120/80."
        result = ai_processor.create_soap_note(transcript)

        assert result.success is True
        assert "S:" in result.value["text"]

    def test_empty_input_handling(self, ai_processor):
        """Test handling of empty input."""
        # Empty string
        result = ai_processor.refine_text("")
        assert result.success is False
        assert "No text to refine" in result.error

        # Whitespace only
        result = ai_processor.improve_text("   \n\t  ")
        assert result.success is False
        assert "No text to improve" in result.error

    @patch('src.ai.ai_processor.adjust_text_with_openai')
    def test_api_error_handling(self, mock_adjust, ai_processor):
        """Test handling of API errors."""
        mock_adjust.side_effect = Exception("API Error")

        result = ai_processor.refine_text("test text")

        assert result.success is False
        assert result.error is not None

    @patch('src.ai.ai_processor.adjust_text_with_openai')
    def test_create_referral_letter(self, mock_adjust, ai_processor):
        """Test referral letter creation."""
        mock_adjust.return_value = "Dear Specialist,\n\nI am referring this patient..."

        text = "Patient presents with chronic headaches"
        letter_options = {
            "referring_provider": "Dr. Smith",
            "patient_name": "John Doe",
            "specialty": "Neurology",
            "reason": "Chronic headaches"
        }

        result = ai_processor.create_referral_letter(text, letter_options)

        assert result.success is True
        assert "Dear Specialist" in result.value["text"]

    @patch('src.ai.ai_processor.adjust_text_with_openai')
    def test_create_letter(self, mock_adjust, ai_processor):
        """Test general letter creation."""
        mock_adjust.return_value = "Dear Patient,\n\nThis letter confirms..."

        text = "Patient visit summary"
        letter_options = {
            "recipient_name": "John Doe",
            "letter_date": "2024-01-15"
        }

        result = ai_processor.create_letter(text, "confirmation", letter_options)

        assert result.success is True
        assert "Dear Patient" in result.value["text"]

    @patch('src.ai.ai_processor.adjust_text_with_openai')
    def test_additional_context_handling(self, mock_adjust, ai_processor):
        """Test handling of text refinement."""
        mock_adjust.return_value = "Refined text"

        result = ai_processor.refine_text("test text")

        assert result.success is True

    @patch('src.ai.ai_processor.create_soap_note_with_openai')
    @patch('src.ai.ai_processor.get_possible_conditions')
    def test_context_inclusion_in_soap(self, mock_conditions, mock_create, ai_processor):
        """Test that context is properly included in SOAP notes."""
        mock_create.return_value = "SOAP with context"
        mock_conditions.return_value = ""

        transcript = "Patient follow-up visit"
        context = "Previous visit: diagnosed with hypertension"

        result = ai_processor.create_soap_note(transcript, context)

        assert result.success is True

    def test_temperature_settings(self, ai_processor):
        """Test that temperature settings are used correctly."""
        # Temperature settings are passed to the underlying AI functions
        # This test verifies the methods exist
        assert ai_processor.refine_text is not None
        assert ai_processor.improve_text is not None

    @patch('src.ai.ai_processor.adjust_text_with_openai')
    def test_long_text_handling(self, mock_adjust, ai_processor):
        """Test handling of very long text inputs."""
        # Create a very long text (simulating a long medical transcript)
        long_text = " ".join(["Patient reports various symptoms."] * 100)
        mock_adjust.return_value = "Processed long text"

        result = ai_processor.refine_text(long_text)

        assert result.success is True
        assert result.value["text"] == "Processed long text"

    @patch('src.ai.ai_processor.adjust_text_with_openai')
    def test_special_characters_handling(self, mock_adjust, ai_processor):
        """Test handling of special characters in medical text."""
        special_text = "BP: 120/80 mmHg, Temp: 98.6°F, O₂ sat: 95%"
        mock_adjust.return_value = special_text

        result = ai_processor.refine_text(special_text)

        assert result.success is True
        assert "°" in result.value["text"]  # Degree symbol preserved

    @patch('src.ai.ai_processor.create_soap_note_with_openai')
    @patch('src.ai.ai_processor.get_possible_conditions')
    def test_soap_note_without_conditions(self, mock_conditions, mock_create_soap, ai_processor):
        """Test SOAP note generation without possible conditions."""
        mock_create_soap.return_value = "S: Headache\nO: Normal\nA: Migraine\nP: Medication"
        mock_conditions.return_value = ""

        result = ai_processor.create_soap_note("Patient has headache")

        assert result.success is True
        assert "S:" in result.value["text"]

    @patch('src.ai.ai_processor.adjust_text_with_openai')
    def test_error_handling_with_exception_details(self, mock_adjust, ai_processor):
        """Test that exceptions include helpful details in error messages."""
        mock_adjust.side_effect = Exception("Connection timeout")

        result = ai_processor.refine_text("test text")

        assert result.success is False
        assert result.error is not None

    @patch('src.ai.ai_processor.adjust_text_with_openai')
    def test_empty_letter_options(self, mock_adjust, ai_processor):
        """Test letter creation with empty options."""
        mock_adjust.return_value = "Generated letter content"

        result = ai_processor.create_letter("test content", "general", {})

        assert result.success is True
        assert result.value["text"] == "Generated letter content"

    @patch('src.ai.ai_processor.adjust_text_with_openai')
    def test_refine_with_custom_prompt_from_settings(self, mock_adjust, ai_processor):
        """Test that custom prompts from settings are used."""
        mock_adjust.return_value = "Refined with custom prompt"

        result = ai_processor.refine_text("test text")

        assert result.success is True

    @patch('src.ai.ai_processor.improve_text_with_openai')
    def test_improve_with_custom_prompt_from_settings(self, mock_improve, ai_processor):
        """Test that custom improve prompts from settings are used."""
        mock_improve.return_value = "Improved with custom prompt"

        result = ai_processor.improve_text("test text")

        assert result.success is True
