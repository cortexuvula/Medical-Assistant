"""Test Deepgram STT provider functionality."""
import pytest
import json
import logging
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO
import numpy as np
from pydub import AudioSegment

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.stt_providers.deepgram import DeepgramProvider
from src.utils.exceptions import TranscriptionError, APIError, RateLimitError, ServiceUnavailableError


class TestDeepgramProvider:
    """Test Deepgram STT provider functionality."""
    
    @pytest.fixture
    def provider(self):
        """Create a Deepgram provider instance."""
        with patch('stt_providers.deepgram.DeepgramClient'):
            provider = DeepgramProvider(api_key="test-deepgram-key", language="en-US")
        return provider
    
    @pytest.fixture
    def mock_audio_segment(self):
        """Create a mock AudioSegment for testing."""
        # Create a simple audio segment
        duration_ms = 1000  # 1 second
        sample_rate = 44100
        samples = np.zeros(int(sample_rate * duration_ms / 1000))
        
        # Convert to AudioSegment
        audio_segment = AudioSegment(
            samples.tobytes(),
            frame_rate=sample_rate,
            sample_width=2,  # 16-bit
            channels=1
        )
        return audio_segment
    
    @pytest.fixture
    def mock_deepgram_response(self):
        """Create a mock Deepgram API response."""
        response = Mock()
        response.to_json.return_value = json.dumps({
            "request_id": "test-request-123",
            "metadata": {
                "duration": 2.5,
                "channels": 1,
                "sample_rate": 44100
            },
            "results": {
                "channels": [{
                    "alternatives": [{
                        "transcript": "This is a test transcription",
                        "confidence": 0.95,
                        "words": [
                            {"word": "This", "start": 0.0, "end": 0.2, "confidence": 0.99},
                            {"word": "is", "start": 0.2, "end": 0.3, "confidence": 0.98},
                            {"word": "a", "start": 0.3, "end": 0.4, "confidence": 0.97},
                            {"word": "test", "start": 0.4, "end": 0.6, "confidence": 0.96},
                            {"word": "transcription", "start": 0.6, "end": 1.0, "confidence": 0.95}
                        ]
                    }]
                }]
            }
        })
        return response
    
    def test_initialization_with_api_key(self):
        """Test provider initialization with API key."""
        with patch('src.stt_providers.deepgram.DeepgramClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            provider = DeepgramProvider(api_key="test-key", language="en-GB")
            
            assert provider.api_key == "test-key"
            assert provider.language == "en-GB"
            assert provider.client == mock_client
            mock_client_class.assert_called_once_with(api_key="test-key")
    
    def test_initialization_without_api_key(self):
        """Test provider initialization without API key."""
        provider = DeepgramProvider()
        
        assert provider.api_key == ""
        assert provider.language == "en-US"
        assert provider.client is None
    
    @patch('src.stt_providers.deepgram.get_config')
    @patch('src.stt_providers.deepgram.SETTINGS')
    def test_transcribe_success(self, mock_settings, mock_get_config, provider, mock_audio_segment, mock_deepgram_response):
        """Test successful transcription."""
        # Mock settings
        mock_settings.get.return_value = {
            "model": "nova-2-medical",
            "language": "en-US",
            "smart_format": True,
            "diarize": False,
            "profanity_filter": False,
            "redact": False,
            "alternatives": 1
        }
        
        # Mock config
        mock_config = Mock()
        mock_config.api.timeout = 60
        mock_get_config.return_value = mock_config
        
        # Mock the API call
        with patch.object(provider, '_make_api_call', return_value=mock_deepgram_response):
            result = provider.transcribe(mock_audio_segment)
        
        assert result == "This is a test transcription"
    
    @patch('src.stt_providers.deepgram.get_config')
    @patch('src.stt_providers.deepgram.SETTINGS')
    def test_transcribe_with_diarization(self, mock_settings, mock_get_config, provider, mock_audio_segment):
        """Test transcription with diarization enabled."""
        # Mock settings with diarization
        mock_settings.get.return_value = {
            "model": "nova-2-medical",
            "language": "en-US",
            "smart_format": True,
            "diarize": True,
            "profanity_filter": False,
            "redact": False,
            "alternatives": 1
        }
        
        # Mock config
        mock_config = Mock()
        mock_config.api.timeout = 60
        mock_get_config.return_value = mock_config
        
        # Mock response with speaker information
        response = Mock()
        response.to_json.return_value = json.dumps({
            "request_id": "test-request-123",
            "metadata": {"duration": 2.5, "channels": 1, "sample_rate": 44100},
            "results": {
                "channels": [{
                    "alternatives": [{
                        "transcript": "Hello how are you I am fine",
                        "words": [
                            {"word": "Hello", "speaker": 0},
                            {"word": "how", "speaker": 0},
                            {"word": "are", "speaker": 0},
                            {"word": "you", "speaker": 0},
                            {"word": "I", "speaker": 1},
                            {"word": "am", "speaker": 1},
                            {"word": "fine", "speaker": 1}
                        ]
                    }]
                }]
            }
        })
        
        with patch.object(provider, '_make_api_call', return_value=response):
            result = provider.transcribe(mock_audio_segment)
        
        assert "Speaker 0:" in result
        assert "Speaker 1:" in result
        assert "Hello how are you" in result
        assert "I am fine" in result
    
    def test_transcribe_without_client(self, mock_audio_segment):
        """Test transcription without initialized client."""
        provider = DeepgramProvider()  # No API key
        
        with pytest.raises(TranscriptionError) as exc_info:
            provider.transcribe(mock_audio_segment)
        
        assert "client not initialized" in str(exc_info.value)
    
    @patch('src.stt_providers.deepgram.get_config')
    @patch('src.stt_providers.deepgram.SETTINGS')
    def test_transcribe_api_error(self, mock_settings, mock_get_config, provider, mock_audio_segment):
        """Test handling of API errors."""
        # Mock settings
        mock_settings.get.return_value = {
            "model": "nova-2-medical",
            "language": "en-US",
            "smart_format": True,
            "diarize": False,
            "profanity_filter": False,
            "redact": False,
            "alternatives": 1
        }
        
        # Mock config
        mock_config = Mock()
        mock_config.api.timeout = 60
        mock_get_config.return_value = mock_config
        
        # Mock API error
        with patch.object(provider, '_make_api_call', side_effect=APIError("API error occurred")):
            with pytest.raises(TranscriptionError) as exc_info:
                provider.transcribe(mock_audio_segment)
        
        assert "Failed to transcribe audio" in str(exc_info.value)
    
    @patch('src.utils.security_decorators.get_security_manager')
    def test_make_api_call_rate_limit(self, mock_get_security_manager, provider):
        """Test handling of rate limit errors."""
        # Mock security manager to return API key and rate limit
        mock_security_manager = Mock()
        mock_security_manager.get_api_key.return_value = "test-api-key"
        mock_security_manager.check_rate_limit.return_value = (True, 0)  # Allowed, no wait
        mock_security_manager.validate_api_key.return_value = (True, None)  # Valid key
        mock_security_manager.generate_secure_token.return_value = "test-token"
        mock_get_security_manager.return_value = mock_security_manager
        
        mock_buffer = BytesIO()
        mock_options = Mock()
        
        # Mock the client to raise rate limit error
        error = Exception("Rate limit exceeded")
        provider.client.listen.rest.v.return_value.transcribe_file.side_effect = error
        
        with pytest.raises(RateLimitError) as exc_info:
            provider._make_api_call(mock_buffer, mock_options, 60)
        
        assert "rate limit exceeded" in str(exc_info.value).lower()
    
    @patch('src.utils.security_decorators.get_security_manager')
    def test_make_api_call_timeout(self, mock_get_security_manager, provider):
        """Test handling of timeout errors."""
        # Mock security manager to return API key and rate limit
        mock_security_manager = Mock()
        mock_security_manager.get_api_key.return_value = "test-api-key"
        mock_security_manager.check_rate_limit.return_value = (True, 0)  # Allowed, no wait
        mock_security_manager.validate_api_key.return_value = (True, None)  # Valid key
        mock_security_manager.generate_secure_token.return_value = "test-token"
        mock_get_security_manager.return_value = mock_security_manager
        
        mock_buffer = BytesIO()
        mock_options = Mock()
        
        # Mock the client to raise timeout error
        error = Exception("Request timeout")
        provider.client.listen.rest.v.return_value.transcribe_file.side_effect = error
        
        with pytest.raises(ServiceUnavailableError) as exc_info:
            provider._make_api_call(mock_buffer, mock_options, 60)
        
        assert "request timeout" in str(exc_info.value).lower()
    
    @patch('src.utils.security_decorators.get_security_manager')
    def test_make_api_call_generic_error(self, mock_get_security_manager, provider):
        """Test handling of generic API errors."""
        # Mock security manager to return API key and rate limit
        mock_security_manager = Mock()
        mock_security_manager.get_api_key.return_value = "test-api-key"
        mock_security_manager.check_rate_limit.return_value = (True, 0)  # Allowed, no wait
        mock_security_manager.validate_api_key.return_value = (True, None)  # Valid key
        mock_security_manager.generate_secure_token.return_value = "test-token"
        mock_get_security_manager.return_value = mock_security_manager
        
        mock_buffer = BytesIO()
        mock_options = Mock()
        
        # Mock the client to raise generic error
        error = Exception("Something went wrong")
        provider.client.listen.rest.v.return_value.transcribe_file.side_effect = error
        
        with pytest.raises(APIError) as exc_info:
            provider._make_api_call(mock_buffer, mock_options, 60)
        
        assert "Deepgram API error" in str(exc_info.value)
    
    @patch('src.stt_providers.deepgram.get_config')
    @patch('src.stt_providers.deepgram.SETTINGS')
    def test_transcribe_empty_transcript(self, mock_settings, mock_get_config, provider, mock_audio_segment):
        """Test handling of empty transcript in response."""
        # Mock settings
        mock_settings.get.return_value = {
            "model": "nova-2-medical",
            "language": "en-US",
            "smart_format": True,
            "diarize": False,
            "profanity_filter": False,
            "redact": False,
            "alternatives": 1
        }
        
        # Mock config
        mock_config = Mock()
        mock_config.api.timeout = 60
        mock_get_config.return_value = mock_config
        
        # Mock response with no transcript
        response = Mock()
        response.to_json.return_value = json.dumps({
            "results": {
                "channels": [{
                    "alternatives": [{}]  # No transcript field
                }]
            }
        })
        
        with patch.object(provider, '_make_api_call', return_value=response):
            with pytest.raises(TranscriptionError) as exc_info:
                provider.transcribe(mock_audio_segment)
        
        assert "No transcript found" in str(exc_info.value)
    
    @patch('src.stt_providers.deepgram.get_config')
    @patch('src.stt_providers.deepgram.SETTINGS')
    def test_transcribe_invalid_response_structure(self, mock_settings, mock_get_config, provider, mock_audio_segment):
        """Test handling of invalid response structure."""
        # Mock settings
        mock_settings.get.return_value = {
            "model": "nova-2-medical",
            "language": "en-US",
            "smart_format": True,
            "diarize": False,
            "profanity_filter": False,
            "redact": False,
            "alternatives": 1
        }
        
        # Mock config
        mock_config = Mock()
        mock_config.api.timeout = 60
        mock_get_config.return_value = mock_config
        
        # Mock response with invalid structure
        response = Mock()
        response.to_json.return_value = json.dumps({})  # Missing results
        
        with patch.object(provider, '_make_api_call', return_value=response):
            with pytest.raises(TranscriptionError) as exc_info:
                provider.transcribe(mock_audio_segment)
        
        assert "Invalid response structure" in str(exc_info.value)
    
    def test_format_diarized_transcript(self, provider):
        """Test formatting of diarized transcript."""
        words = [
            {"word": "Hello", "speaker": 0},
            {"word": "there", "speaker": 0},
            {"word": ".", "speaker": 0},
            {"word": "Hi", "speaker": 1},
            {"word": "!", "speaker": 1},
            {"word": "How", "speaker": 0},
            {"word": "are", "speaker": 0},
            {"word": "you", "speaker": 0},
            {"word": "?", "speaker": 0},
        ]
        
        result = provider._format_diarized_transcript(words)
        
        assert "Speaker 0: Hello there." in result
        assert "Speaker 1: Hi!" in result
        assert "Speaker 0: How are you?" in result
    
    def test_format_diarized_transcript_empty(self, provider):
        """Test formatting of empty diarized transcript."""
        result = provider._format_diarized_transcript([])
        assert result == ""
    
    def test_format_diarized_transcript_no_speaker(self, provider):
        """Test formatting of transcript without speaker information."""
        words = [
            {"word": "Hello"},
            {"word": "world"}
        ]
        
        result = provider._format_diarized_transcript(words)
        assert result == ""  # Should skip words without speaker info
    
    @patch('src.stt_providers.deepgram.get_config')
    @patch('src.stt_providers.deepgram.SETTINGS')
    @patch('src.stt_providers.deepgram._DEFAULT_SETTINGS')
    def test_transcribe_with_custom_settings(self, mock_default_settings, mock_settings, mock_get_config, provider, mock_audio_segment, mock_deepgram_response):
        """Test transcription with custom settings."""
        # Mock custom settings
        mock_settings.get.return_value = {
            "model": "custom-model",
            "language": "es-ES",
            "smart_format": False,
            "diarize": True,
            "profanity_filter": True,
            "redact": True,
            "alternatives": 3
        }
        
        # Mock default settings (fallback)
        mock_default_settings.__getitem__.return_value = {
            "deepgram": {
                "model": "nova-2-medical",
                "language": "en-US",
                "smart_format": True,
                "diarize": False,
                "profanity_filter": False,
                "redact": False,
                "alternatives": 1
            }
        }
        
        # Mock config
        mock_config = Mock()
        mock_config.api.timeout = 60
        mock_get_config.return_value = mock_config
        
        # Capture the options passed to _make_api_call
        captured_options = None
        def capture_options(buffer, options, timeout):
            nonlocal captured_options
            captured_options = options
            return mock_deepgram_response
        
        with patch.object(provider, '_make_api_call', side_effect=capture_options):
            provider.transcribe(mock_audio_segment)
        
        # Verify custom settings were used
        assert captured_options.model == "custom-model"
        assert captured_options.language == "es-ES"
        assert captured_options.smart_format is False
        assert captured_options.diarize is True
        assert captured_options.profanity_filter is True
        assert captured_options.redact is True
        assert captured_options.alternatives == 3
    
    @patch('src.stt_providers.deepgram.get_config')
    @patch('src.stt_providers.deepgram.SETTINGS')
    def test_buffer_cleanup_on_error(self, mock_settings, mock_get_config, provider, mock_audio_segment):
        """Test that buffer is cleaned up even on error."""
        # Mock settings
        mock_settings.get.return_value = {
            "model": "nova-2-medical",
            "language": "en-US",
            "smart_format": True,
            "diarize": False,
            "profanity_filter": False,
            "redact": False,
            "alternatives": 1
        }
        
        # Mock config
        mock_config = Mock()
        mock_config.api.timeout = 60
        mock_get_config.return_value = mock_config
        
        # Track buffer close calls
        buffer_closed = False
        original_bytesio = BytesIO
        
        class TrackingBytesIO(original_bytesio):
            def close(self):
                nonlocal buffer_closed
                buffer_closed = True
                super().close()
        
        with patch('src.stt_providers.deepgram.BytesIO', TrackingBytesIO):
            with patch.object(provider, '_make_api_call', side_effect=APIError("Test error")):
                with pytest.raises(TranscriptionError):
                    provider.transcribe(mock_audio_segment)
        
        assert buffer_closed, "Buffer should be closed even on error"