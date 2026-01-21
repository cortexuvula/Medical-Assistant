"""Test Groq STT provider functionality."""
import pytest
import logging
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import numpy as np
from pydub import AudioSegment

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from stt_providers.groq import GroqProvider
from utils.exceptions import TranscriptionError


class TestGroqProvider:
    """Test Groq STT provider functionality."""

    @pytest.fixture
    def provider(self):
        """Create a Groq provider instance."""
        return GroqProvider(api_key="test-groq-key", language="en-US")

    @pytest.fixture
    def mock_audio_segment(self):
        """Create a mock AudioSegment for testing."""
        # Create a simple audio segment
        duration_ms = 1000  # 1 second
        sample_rate = 44100
        samples = np.zeros(int(sample_rate * duration_ms / 1000), dtype=np.int16)

        # Convert to AudioSegment
        audio_segment = AudioSegment(
            samples.tobytes(),
            frame_rate=sample_rate,
            sample_width=2,  # 16-bit
            channels=1
        )
        return audio_segment

    def test_initialization(self):
        """Test provider initialization."""
        provider = GroqProvider(api_key="test-key", language="es-ES")

        assert provider.api_key == "test-key"
        assert provider.language == "es-ES"
        # Logger might be a StructuredLogger or standard Logger
        assert hasattr(provider.logger, 'info') and hasattr(provider.logger, 'error')

    def test_initialization_without_api_key(self):
        """Test provider initialization without API key."""
        provider = GroqProvider()

        assert provider.api_key == ""
        assert provider.language == "en-US"

    def test_provider_name(self, provider):
        """Test provider name property."""
        assert provider.provider_name == "groq"

    def test_supports_diarization(self, provider):
        """Test diarization support property."""
        assert provider.supports_diarization is False

    @patch('stt_providers.groq.SETTINGS')
    @patch('stt_providers.groq.get_config')
    @patch('stt_providers.groq.get_security_manager')
    @patch('stt_providers.groq.get_http_client_manager')
    @patch('openai.OpenAI')
    def test_transcribe_success(self, mock_openai_class, mock_get_http_manager, mock_get_security_manager, mock_get_config, mock_settings, provider, mock_audio_segment):
        """Test successful transcription."""
        # Mock config
        mock_config = Mock()
        mock_config.api.timeout = 60
        mock_get_config.return_value = mock_config

        # Mock settings
        mock_settings.get.return_value = {
            "model": "whisper-large-v3-turbo",
            "language": "",
            "prompt": ""
        }

        # Mock security manager
        mock_security_manager = Mock()
        mock_security_manager.get_api_key.return_value = "test-groq-key"
        mock_get_security_manager.return_value = mock_security_manager

        # Mock HTTP client manager
        mock_http_client = MagicMock()
        mock_manager = MagicMock()
        mock_manager.get_httpx_client.return_value = mock_http_client
        mock_get_http_manager.return_value = mock_manager

        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "This is a test transcription"
        mock_client.audio.transcriptions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        result = provider.transcribe(mock_audio_segment)

        assert result == "This is a test transcription"

        # Verify OpenAI client initialization
        mock_openai_class.assert_called_once()
        call_kwargs = mock_openai_class.call_args[1]
        assert call_kwargs["api_key"] == "test-groq-key"
        assert call_kwargs["base_url"] == "https://api.groq.com/openai/v1"

        # Verify transcription call
        mock_client.audio.transcriptions.create.assert_called_once()

    def test_transcribe_without_api_key(self, mock_audio_segment):
        """Test transcription without API key."""
        provider = GroqProvider()

        with pytest.raises(TranscriptionError) as exc_info:
            provider.transcribe(mock_audio_segment)

        assert "API key not configured" in str(exc_info.value)

    @patch('stt_providers.groq.SETTINGS')
    @patch('stt_providers.groq.get_config')
    @patch('stt_providers.groq.get_security_manager')
    @patch('stt_providers.groq.get_http_client_manager')
    @patch('openai.OpenAI')
    def test_transcribe_api_key_not_found(self, mock_openai_class, mock_get_http_manager, mock_get_security_manager, mock_get_config, mock_settings, provider, mock_audio_segment):
        """Test transcription when API key is not found in secure storage."""
        # Mock config
        mock_config = Mock()
        mock_config.api.timeout = 60
        mock_get_config.return_value = mock_config

        # Mock settings
        mock_settings.get.return_value = {}

        # Mock security manager returning None
        mock_security_manager = Mock()
        mock_security_manager.get_api_key.return_value = None
        mock_get_security_manager.return_value = mock_security_manager

        # Set provider api_key to empty
        provider.api_key = ""

        with pytest.raises(TranscriptionError) as exc_info:
            provider.transcribe(mock_audio_segment)

        assert "API key not configured" in str(exc_info.value)

    @patch('stt_providers.groq.SETTINGS')
    @patch('stt_providers.groq.get_config')
    @patch('stt_providers.groq.get_security_manager')
    @patch('stt_providers.groq.get_http_client_manager')
    @patch('openai.OpenAI')
    def test_transcribe_timeout_calculation(self, mock_openai_class, mock_get_http_manager, mock_get_security_manager, mock_get_config, mock_settings, provider, mock_audio_segment):
        """Test timeout calculation based on buffer size."""
        # Mock settings
        mock_settings.get.return_value = {
            "model": "whisper-large-v3-turbo",
            "language": "",
            "prompt": ""
        }

        # Mock security manager
        mock_security_manager = Mock()
        mock_security_manager.get_api_key.return_value = "test-groq-key"
        mock_get_security_manager.return_value = mock_security_manager

        # Mock HTTP client manager
        mock_manager = MagicMock()
        mock_get_http_manager.return_value = mock_manager

        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "test"
        mock_client.audio.transcriptions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        # Mock config with specific base timeout
        mock_config = Mock()
        mock_config.api.timeout = 60
        mock_get_config.return_value = mock_config

        provider.transcribe(mock_audio_segment)

        # Check timeout parameter was set (minimum 60 seconds)
        call_args = mock_client.audio.transcriptions.create.call_args
        assert call_args[1]["timeout"] >= 60

    @patch('stt_providers.groq.SETTINGS')
    @patch('stt_providers.groq.get_config')
    @patch('stt_providers.groq.get_security_manager')
    @patch('stt_providers.groq.get_http_client_manager')
    @patch('openai.OpenAI')
    def test_transcribe_api_error(self, mock_openai_class, mock_get_http_manager, mock_get_security_manager, mock_get_config, mock_settings, provider, mock_audio_segment):
        """Test handling of API errors."""
        # Mock config
        mock_config = Mock()
        mock_config.api.timeout = 60
        mock_get_config.return_value = mock_config

        # Mock settings
        mock_settings.get.return_value = {}

        # Mock security manager
        mock_security_manager = Mock()
        mock_security_manager.get_api_key.return_value = "test-groq-key"
        mock_get_security_manager.return_value = mock_security_manager

        # Mock HTTP client manager
        mock_manager = MagicMock()
        mock_get_http_manager.return_value = mock_manager

        # Mock OpenAI client that raises error
        mock_client = Mock()
        mock_client.audio.transcriptions.create.side_effect = Exception("API Error")
        mock_openai_class.return_value = mock_client

        with pytest.raises(TranscriptionError) as exc_info:
            provider.transcribe(mock_audio_segment)

        # Error goes through retry logic and is wrapped as "GROQ transcription failed"
        assert "GROQ transcription failed" in str(exc_info.value) or "API Error" in str(exc_info.value)

    @patch('stt_providers.groq.SETTINGS')
    @patch('stt_providers.groq.get_config')
    @patch('stt_providers.groq.get_security_manager')
    @patch('stt_providers.groq.get_http_client_manager')
    @patch('openai.OpenAI')
    def test_transcribe_unexpected_response_format(self, mock_openai_class, mock_get_http_manager, mock_get_security_manager, mock_get_config, mock_settings, provider, mock_audio_segment):
        """Test handling of unexpected response format."""
        # Mock config
        mock_config = Mock()
        mock_config.api.timeout = 60
        mock_get_config.return_value = mock_config

        # Mock settings
        mock_settings.get.return_value = {}

        # Mock security manager
        mock_security_manager = Mock()
        mock_security_manager.get_api_key.return_value = "test-groq-key"
        mock_get_security_manager.return_value = mock_security_manager

        # Mock HTTP client manager
        mock_manager = MagicMock()
        mock_get_http_manager.return_value = mock_manager

        # Mock OpenAI client with response that has no text attribute
        mock_client = Mock()
        mock_response = Mock(spec=[])  # No attributes
        mock_client.audio.transcriptions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        with pytest.raises(TranscriptionError) as exc_info:
            provider.transcribe(mock_audio_segment)

        assert "Unexpected response format from GROQ API" in str(exc_info.value)

    @patch('stt_providers.groq.SETTINGS')
    @patch('stt_providers.groq.get_config')
    @patch('stt_providers.groq.get_security_manager')
    @patch('stt_providers.groq.get_http_client_manager')
    @patch('openai.OpenAI')
    def test_language_code_extraction(self, mock_openai_class, mock_get_http_manager, mock_get_security_manager, mock_get_config, mock_settings, mock_audio_segment):
        """Test language code extraction from full language tags."""
        # Mock config
        mock_config = Mock()
        mock_config.api.timeout = 60
        mock_get_config.return_value = mock_config

        # Mock settings with no language override
        mock_settings.get.return_value = {
            "model": "whisper-large-v3-turbo",
            "language": "",
            "prompt": ""
        }

        # Mock security manager
        mock_security_manager = Mock()
        mock_security_manager.get_api_key.return_value = "test-groq-key"
        mock_get_security_manager.return_value = mock_security_manager

        # Mock HTTP client manager
        mock_manager = MagicMock()
        mock_get_http_manager.return_value = mock_manager

        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "test"
        mock_client.audio.transcriptions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        # Test different language formats
        test_cases = [
            ("en-US", "en"),
            ("es-ES", "es"),
            ("fr", "fr"),
            ("pt-BR", "pt"),
            ("zh-CN", "zh"),
        ]

        for full_lang, expected_lang in test_cases:
            mock_client.audio.transcriptions.create.reset_mock()
            provider = GroqProvider(api_key="test-groq-key", language=full_lang)
            provider.transcribe(mock_audio_segment)

            # Check language parameter was extracted correctly
            call_args = mock_client.audio.transcriptions.create.call_args
            assert call_args[1]["language"] == expected_lang

    def test_provider_inheritance(self, provider):
        """Test that provider properly inherits from base."""
        from stt_providers.base import BaseSTTProvider

        assert isinstance(provider, BaseSTTProvider)
        assert hasattr(provider, 'transcribe')
        assert hasattr(provider, '_check_api_key')
        assert hasattr(provider, 'api_key')
        assert hasattr(provider, 'language')
        assert hasattr(provider, 'logger')

    @patch('stt_providers.groq.SETTINGS')
    @patch('stt_providers.groq.get_config')
    @patch('stt_providers.groq.get_security_manager')
    @patch('stt_providers.groq.get_http_client_manager')
    @patch('openai.OpenAI')
    def test_uses_settings_model(self, mock_openai_class, mock_get_http_manager, mock_get_security_manager, mock_get_config, mock_settings, provider, mock_audio_segment):
        """Test that the model from settings is used."""
        # Mock config
        mock_config = Mock()
        mock_config.api.timeout = 60
        mock_get_config.return_value = mock_config

        # Mock settings with custom model
        mock_settings.get.return_value = {
            "model": "whisper-large-v3",
            "language": "",
            "prompt": ""
        }

        # Mock security manager
        mock_security_manager = Mock()
        mock_security_manager.get_api_key.return_value = "test-groq-key"
        mock_get_security_manager.return_value = mock_security_manager

        # Mock HTTP client manager
        mock_manager = MagicMock()
        mock_get_http_manager.return_value = mock_manager

        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "test"
        mock_client.audio.transcriptions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        provider.transcribe(mock_audio_segment)

        # Check model parameter
        call_args = mock_client.audio.transcriptions.create.call_args
        assert call_args[1]["model"] == "whisper-large-v3"

    @patch('stt_providers.groq.SETTINGS')
    @patch('stt_providers.groq.get_config')
    @patch('stt_providers.groq.get_security_manager')
    @patch('stt_providers.groq.get_http_client_manager')
    @patch('openai.OpenAI')
    def test_uses_prompt_from_settings(self, mock_openai_class, mock_get_http_manager, mock_get_security_manager, mock_get_config, mock_settings, provider, mock_audio_segment):
        """Test that prompt from settings is used for context."""
        # Mock config
        mock_config = Mock()
        mock_config.api.timeout = 60
        mock_get_config.return_value = mock_config

        # Mock settings with prompt
        mock_settings.get.return_value = {
            "model": "whisper-large-v3-turbo",
            "language": "",
            "prompt": "Medical terminology: hypertension, diabetes"
        }

        # Mock security manager
        mock_security_manager = Mock()
        mock_security_manager.get_api_key.return_value = "test-groq-key"
        mock_get_security_manager.return_value = mock_security_manager

        # Mock HTTP client manager
        mock_manager = MagicMock()
        mock_get_http_manager.return_value = mock_manager

        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "test"
        mock_client.audio.transcriptions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        provider.transcribe(mock_audio_segment)

        # Check prompt parameter was included
        call_args = mock_client.audio.transcriptions.create.call_args
        assert call_args[1]["prompt"] == "Medical terminology: hypertension, diabetes"
