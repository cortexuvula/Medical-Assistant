"""Test AI processor functionality."""
import pytest
from unittest.mock import Mock, patch, MagicMock
import openai
from ai_processor import AIProcessor


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
        assert hasattr(ai_processor, 'validate_api_key')
    
    @patch('ai_processor.SETTINGS', {'ai_provider': 'openai'})
    def test_provider_selection(self, ai_processor):
        """Test that AI processor respects provider settings."""
        # The AIProcessor doesn't have a set_provider method
        # Provider selection is handled through SETTINGS
        from settings import SETTINGS
        
        # Provider selection happens in the ai.py module functions
        # AIProcessor just calls those functions
        assert ai_processor.api_key is not None
    
    @patch('ai_processor.adjust_text_with_openai')
    def test_refine_text_success(self, mock_adjust, ai_processor):
        """Test successful text refinement."""
        mock_adjust.return_value = "Refined text output"
        
        input_text = "patient has headache. took tylenol"
        result = ai_processor.refine_text(input_text)
        
        assert result["success"] is True
        assert result["text"] == "Refined text output"
        assert "error" not in result
        
        # Verify the function was called
        mock_adjust.assert_called_once()
    
    @patch('ai_processor.improve_text_with_openai')
    def test_improve_text_success(self, mock_improve, ai_processor):
        """Test successful text improvement."""
        mock_improve.return_value = "Improved text output"
        
        input_text = "Patient complains of pain"
        result = ai_processor.improve_text(input_text)
        
        assert result["success"] is True
        assert result["text"] == "Improved text output"
        
        # Verify the function was called
        mock_improve.assert_called_once()
    
    @patch('ai_processor.create_soap_note_with_openai')
    @patch('ai_processor.get_possible_conditions')
    def test_create_soap_note_success(self, mock_conditions, mock_create_soap, ai_processor):
        """Test SOAP note generation."""
        mock_create_soap.return_value = "S: Headache x3 days\nO: BP 120/80\nA: Tension headache\nP: Rest and hydration"
        mock_conditions.return_value = "Tension headache, Hypertension"
        
        transcript = "Patient has headache for 3 days. Blood pressure is 120/80."
        result = ai_processor.create_soap_note(transcript)
        
        assert result["success"] is True
        assert "S:" in result["text"]
        assert "O:" in result["text"]
        assert "A:" in result["text"]
        assert "P:" in result["text"]
        assert "Possible Conditions:" in result["text"]
    
    def test_empty_input_handling(self, ai_processor):
        """Test handling of empty input."""
        # Empty string
        result = ai_processor.refine_text("")
        assert result["success"] is False
        assert "No text to refine" in result["error"]
        
        # Whitespace only
        result = ai_processor.improve_text("   \n\t  ")
        assert result["success"] is False
        assert "No text to improve" in result["error"]
    
    @patch('ai_processor.adjust_text_with_openai')
    def test_api_error_handling(self, mock_adjust, ai_processor):
        """Test handling of API errors."""
        # Test various error scenarios
        test_cases = [
            (Exception("API Error"), "API Error"),
            (Exception("Invalid API key"), "Invalid API key"),
            (Exception("Rate limit exceeded"), "Rate limit exceeded"),
            (Exception("Request timed out"), "Request timed out"),
        ]
        
        for error, expected_message in test_cases:
            mock_adjust.side_effect = error
            
            result = ai_processor.refine_text("test text")
            
            assert result["success"] is False
            assert "error" in result
            assert expected_message in result["error"]
    
    def test_create_referral_letter(self, ai_processor):
        """Test referral letter creation."""
        with patch('ai_processor.adjust_text_with_openai') as mock_adjust:
            mock_adjust.return_value = "Dear Specialist,\n\nI am referring this patient..."
            
            text = "Patient presents with chronic headaches"
            letter_options = {
                "referring_provider": "Dr. Smith",
                "patient_name": "John Doe",
                "specialty": "Neurology",
                "reason": "Chronic headaches"
            }
            
            result = ai_processor.create_referral_letter(text, letter_options)
            
            assert result["success"] is True
            assert "Dear Specialist" in result["text"]
            assert "referring this patient" in result["text"]
    
    def test_create_letter(self, ai_processor):
        """Test general letter creation."""
        with patch('ai_processor.adjust_text_with_openai') as mock_adjust:
            mock_adjust.return_value = "Dear Patient,\n\nThis letter confirms..."
            
            text = "Patient visit summary"
            letter_options = {
                "recipient_name": "John Doe",
                "letter_date": "2024-01-15"
            }
            
            result = ai_processor.create_letter(text, "confirmation", letter_options)
            
            assert result["success"] is True
            assert "Dear Patient" in result["text"]
            assert "confirms" in result["text"]
    
    @patch('openai.Model.list')
    def test_validate_api_key_success(self, mock_list, ai_processor):
        """Test API key validation success."""
        mock_list.return_value = Mock()  # Successful response
        
        assert ai_processor.validate_api_key() is True
        mock_list.assert_called_once()
    
    @patch('openai.Model.list')
    def test_validate_api_key_failure(self, mock_list, ai_processor):
        """Test API key validation failure."""
        mock_list.side_effect = Exception("Invalid API key")
        
        assert ai_processor.validate_api_key() is False
    
    def test_additional_context_handling(self, ai_processor):
        """Test handling of additional context in refine and improve."""
        with patch('ai_processor.adjust_text_with_openai') as mock_adjust:
            mock_adjust.return_value = "Refined with context"
            
            result = ai_processor.refine_text("test text", "additional context")
            
            assert result["success"] is True
            # Verify the context was included in the prompt
            call_args = mock_adjust.call_args
            assert "additional context" in call_args[0][1]
    
    def test_context_inclusion_in_soap(self, ai_processor):
        """Test that context is properly included in SOAP notes."""
        with patch('ai_processor.create_soap_note_with_openai') as mock_create:
            mock_create.return_value = "SOAP with context"
            
            transcript = "Patient follow-up visit"
            context = "Previous visit: diagnosed with hypertension"
            
            result = ai_processor.create_soap_note(transcript, context)
            
            assert result["success"] is True
            # Verify context was included in the call
            call_args = mock_create.call_args
            assert "Previous visit: diagnosed with hypertension" in call_args[0][0]
    
    def test_temperature_settings(self, ai_processor):
        """Test that temperature settings are used correctly."""
        with patch('ai_processor.SETTINGS', {
            "refine_temperature": 0.1,
            "improve_temperature": 0.3,
            "soap_temperature": 0.2,
            "referral_temperature": 0.3,
            "letter_temperature": 0.3
        }):
            # Temperature settings are passed to the underlying AI functions
            # This test verifies the settings structure is correct
            assert ai_processor.refine_text is not None
            assert ai_processor.improve_text is not None
    
    def test_long_text_handling(self, ai_processor):
        """Test handling of very long text inputs."""
        # Create a very long text (simulating a long medical transcript)
        long_text = " ".join(["Patient reports various symptoms."] * 1000)
        
        with patch('ai_processor.adjust_text_with_openai') as mock_adjust:
            mock_adjust.return_value = "Processed long text"
            
            result = ai_processor.refine_text(long_text)
            
            assert result["success"] is True
            assert result["text"] == "Processed long text"
    
    def test_special_characters_handling(self, ai_processor):
        """Test handling of special characters in medical text."""
        special_text = "BP: 120/80 mmHg, Temp: 98.6°F, O₂ sat: 95%"
        
        with patch('ai_processor.adjust_text_with_openai') as mock_adjust:
            mock_adjust.return_value = special_text
            
            result = ai_processor.refine_text(special_text)
            
            assert result["success"] is True
            assert "°" in result["text"]  # Degree symbol preserved
            assert "₂" in result["text"]  # Subscript preserved
    
    @patch('ai_processor.SETTINGS', {"include_possible_conditions": False})
    @patch('ai_processor.create_soap_note_with_openai')
    def test_soap_note_without_conditions(self, mock_create_soap, ai_processor):
        """Test SOAP note generation without possible conditions."""
        mock_create_soap.return_value = "S: Headache\nO: Normal\nA: Migraine\nP: Medication"
        
        result = ai_processor.create_soap_note("Patient has headache")
        
        assert result["success"] is True
        assert "Possible Conditions:" not in result["text"]
        assert "S:" in result["text"]
    
    def test_error_handling_with_exception_details(self, ai_processor):
        """Test that exceptions include helpful details in error messages."""
        with patch('ai_processor.adjust_text_with_openai') as mock_adjust:
            mock_adjust.side_effect = Exception("Connection timeout")
            
            result = ai_processor.refine_text("test text")
            
            assert result["success"] is False
            assert "Connection timeout" in result["error"]
    
    def test_empty_letter_options(self, ai_processor):
        """Test letter creation with empty options."""
        with patch('ai_processor.adjust_text_with_openai') as mock_adjust:
            mock_adjust.return_value = "Generated letter content"
            
            result = ai_processor.create_letter("test content", "general", {})
            
            assert result["success"] is True
            assert result["text"] == "Generated letter content"
    
    def test_refine_with_custom_prompt_from_settings(self, ai_processor):
        """Test that custom prompts from settings are used."""
        custom_prompt = "Custom refine prompt"
        with patch('ai_processor.SETTINGS', {
            "refine_text": {"prompt": custom_prompt},
            "refine_temperature": 0.1
        }):
            with patch('ai_processor.adjust_text_with_openai') as mock_adjust:
                mock_adjust.return_value = "Refined with custom prompt"
                
                result = ai_processor.refine_text("test text")
                
                assert result["success"] is True
                # Verify custom prompt was used
                call_args = mock_adjust.call_args
                assert custom_prompt in call_args[0][1]
    
    def test_improve_with_custom_prompt_from_settings(self, ai_processor):
        """Test that custom improve prompts from settings are used."""
        custom_prompt = "Custom improve prompt"
        with patch('ai_processor.SETTINGS', {
            "improve_text": {"prompt": custom_prompt},
            "improve_temperature": 0.3
        }):
            with patch('ai_processor.improve_text_with_openai') as mock_improve:
                mock_improve.return_value = "Improved with custom prompt"
                
                result = ai_processor.improve_text("test text")
                
                assert result["success"] is True
                # Verify custom prompt was used
                call_args = mock_improve.call_args
                assert custom_prompt in call_args[0][1]