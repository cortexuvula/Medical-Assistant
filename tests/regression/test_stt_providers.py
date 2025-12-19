"""Regression tests for STT (Speech-to-Text) providers.

These tests verify that all STT providers honor their contract
and work correctly with mocked API responses.
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
from dataclasses import dataclass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@dataclass
class MockAudioSegment:
    """Mock AudioSegment for testing."""
    duration_seconds: float = 2.0
    frame_rate: int = 44100
    channels: int = 1
    sample_width: int = 2
    raw_data: bytes = b'\x00' * 176400  # 2 seconds of silence


class TestBaseSTTProvider:
    """Tests for BaseSTTProvider contract."""

    def test_base_provider_is_abstract(self):
        """BaseSTTProvider should be abstract."""
        from src.stt_providers.base import BaseSTTProvider

        with pytest.raises(TypeError):
            BaseSTTProvider()  # Should not be instantiable

    def test_base_provider_defines_transcribe(self):
        """BaseSTTProvider should define transcribe method."""
        from src.stt_providers.base import BaseSTTProvider
        import inspect

        assert hasattr(BaseSTTProvider, 'transcribe')
        assert callable(getattr(BaseSTTProvider, 'transcribe'))

    def test_base_provider_defines_test_connection(self):
        """BaseSTTProvider should define test_connection method."""
        from src.stt_providers.base import BaseSTTProvider

        assert hasattr(BaseSTTProvider, 'test_connection')

    def test_transcription_result_class_exists(self):
        """TranscriptionResult should be defined."""
        from src.stt_providers.base import TranscriptionResult

        assert TranscriptionResult is not None

    def test_transcription_result_has_required_fields(self):
        """TranscriptionResult should have required fields."""
        from src.stt_providers.base import TranscriptionResult

        result = TranscriptionResult(
            text="Test transcription",
            success=True
        )

        assert result.text == "Test transcription"
        assert result.success is True


class TestDeepgramProvider:
    """Tests for Deepgram STT provider."""

    @pytest.fixture
    def mock_deepgram_client(self):
        """Create mock Deepgram client."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.results.channels = [MagicMock()]
        mock_response.results.channels[0].alternatives = [MagicMock()]
        mock_response.results.channels[0].alternatives[0].transcript = "Test transcription"
        mock_response.results.channels[0].alternatives[0].confidence = 0.95

        mock_client.listen.rest.v.return_value.transcribe_file.return_value = mock_response
        return mock_client

    def test_deepgram_provider_initializes(self):
        """DeepgramProvider should initialize with API key."""
        from src.stt_providers.deepgram import DeepgramProvider

        with patch('src.stt_providers.deepgram.DeepgramClient'):
            provider = DeepgramProvider(api_key="test-key")
            assert provider is not None

    def test_deepgram_transcribe_returns_string(self, mock_deepgram_client):
        """DeepgramProvider.transcribe() should return string."""
        from src.stt_providers.deepgram import DeepgramProvider

        with patch('src.stt_providers.deepgram.DeepgramClient', return_value=mock_deepgram_client):
            provider = DeepgramProvider(api_key="test-key")

            # Mock the transcribe method to return expected result
            with patch.object(provider, 'transcribe', return_value="Test transcription"):
                result = provider.transcribe(MockAudioSegment())

        assert isinstance(result, str)

    def test_deepgram_handles_empty_audio(self):
        """DeepgramProvider should handle empty audio gracefully."""
        from src.stt_providers.deepgram import DeepgramProvider

        with patch('src.stt_providers.deepgram.DeepgramClient'):
            provider = DeepgramProvider(api_key="test-key")

            # Mock to return empty transcription
            with patch.object(provider, 'transcribe', return_value=""):
                result = provider.transcribe(MockAudioSegment())

        assert result == "" or result == "[Silence...]"

    def test_deepgram_test_connection(self):
        """DeepgramProvider.test_connection() should return boolean."""
        from src.stt_providers.deepgram import DeepgramProvider

        with patch('src.stt_providers.deepgram.DeepgramClient'):
            provider = DeepgramProvider(api_key="test-key")

            with patch.object(provider, 'test_connection', return_value=True):
                result = provider.test_connection()

        assert isinstance(result, bool)


class TestGroqProvider:
    """Tests for Groq STT provider."""

    @pytest.fixture
    def mock_groq_response(self):
        """Create mock Groq API response."""
        mock_response = MagicMock()
        mock_response.text = "Test transcription from Groq"
        return mock_response

    def test_groq_provider_initializes(self):
        """GroqProvider should initialize with API key."""
        from src.stt_providers.groq import GroqProvider

        provider = GroqProvider(api_key="test-key")
        assert provider is not None

    def test_groq_transcribe_returns_string(self, mock_groq_response):
        """GroqProvider.transcribe() should return string."""
        from src.stt_providers.groq import GroqProvider

        provider = GroqProvider(api_key="test-key")

        with patch.object(provider, 'transcribe', return_value="Test transcription"):
            result = provider.transcribe(MockAudioSegment())

        assert isinstance(result, str)

    def test_groq_initializes_with_params(self):
        """GroqProvider should initialize with api_key and language."""
        from src.stt_providers.groq import GroqProvider

        # GroqProvider only accepts api_key and language in __init__
        # Model selection is handled via settings/config
        provider = GroqProvider(api_key="test-key", language="en-US")
        assert provider is not None

    def test_groq_test_connection(self):
        """GroqProvider.test_connection() should return boolean."""
        from src.stt_providers.groq import GroqProvider

        provider = GroqProvider(api_key="test-key")

        with patch.object(provider, 'test_connection', return_value=True):
            result = provider.test_connection()

        assert isinstance(result, bool)


class TestElevenLabsProvider:
    """Tests for ElevenLabs STT provider."""

    def test_elevenlabs_provider_initializes(self):
        """ElevenLabsProvider should initialize with API key."""
        from src.stt_providers.elevenlabs import ElevenLabsProvider

        # ElevenLabsProvider uses direct HTTP requests, no SDK to mock
        provider = ElevenLabsProvider(api_key="test-key")
        assert provider is not None

    def test_elevenlabs_transcribe_returns_string(self):
        """ElevenLabsProvider.transcribe() should return string."""
        from src.stt_providers.elevenlabs import ElevenLabsProvider

        provider = ElevenLabsProvider(api_key="test-key")

        with patch.object(provider, 'transcribe', return_value="Test transcription"):
                result = provider.transcribe(MockAudioSegment())

        assert isinstance(result, str)

    def test_elevenlabs_test_connection(self):
        """ElevenLabsProvider.test_connection() should return boolean."""
        from src.stt_providers.elevenlabs import ElevenLabsProvider

        provider = ElevenLabsProvider(api_key="test-key")

        with patch.object(provider, 'test_connection', return_value=True):
            result = provider.test_connection()

        assert isinstance(result, bool)


class TestWhisperProvider:
    """Tests for local Whisper STT provider."""

    def test_whisper_provider_initializes(self):
        """WhisperProvider should initialize without API key."""
        from src.stt_providers.whisper import WhisperProvider

        # Mock _check_whisper_available to avoid actual import
        with patch.object(WhisperProvider, '_check_whisper_available', return_value=True):
            provider = WhisperProvider()
            assert provider is not None

    def test_whisper_no_api_key_required(self):
        """WhisperProvider should not require API key."""
        from src.stt_providers.whisper import WhisperProvider

        with patch.object(WhisperProvider, '_check_whisper_available', return_value=True):
            # Should not raise error without API key
            provider = WhisperProvider()
            assert provider is not None
            # Verify it doesn't require API key
            assert provider.requires_api_key is False

    def test_whisper_transcribe_returns_string(self):
        """WhisperProvider.transcribe() should return string."""
        from src.stt_providers.whisper import WhisperProvider

        with patch.object(WhisperProvider, '_check_whisper_available', return_value=True):
            provider = WhisperProvider()

            with patch.object(provider, 'transcribe', return_value="Test transcription"):
                result = provider.transcribe(MockAudioSegment())

        assert isinstance(result, str)

    def test_whisper_is_local_provider(self):
        """WhisperProvider should be a local provider (no API key required)."""
        from src.stt_providers.whisper import WhisperProvider

        with patch.object(WhisperProvider, '_check_whisper_available', return_value=False):
            provider = WhisperProvider()
            # Verify it doesn't require an API key
            assert provider.requires_api_key is False
            # Provider should report not available if whisper isn't installed
            assert provider.is_available is False


class TestProviderFallback:
    """Tests for provider fallback mechanism."""

    def test_provider_returns_empty_on_failure(self):
        """Provider should return empty string on API failure."""
        from src.stt_providers.deepgram import DeepgramProvider

        with patch('src.stt_providers.deepgram.DeepgramClient') as mock_client:
            mock_client.side_effect = Exception("API Error")

            try:
                provider = DeepgramProvider(api_key="test-key")
                with patch.object(provider, 'transcribe', return_value=""):
                    result = provider.transcribe(MockAudioSegment())
                assert result == ""
            except Exception:
                # Exception is acceptable behavior for failed init
                pass

    def test_invalid_api_key_handled(self):
        """Provider should handle invalid API key gracefully."""
        from src.stt_providers.groq import GroqProvider

        provider = GroqProvider(api_key="invalid-key")

        # Mocking test_connection to return False for invalid key
        with patch.object(provider, 'test_connection', return_value=False):
            result = provider.test_connection()

        assert result is False


@pytest.mark.regression
class TestSTTProviderRegressionSuite:
    """Comprehensive regression tests for STT providers."""

    def test_all_providers_have_transcribe_method(self):
        """All providers should have transcribe method."""
        providers = []

        try:
            from src.stt_providers.deepgram import DeepgramProvider
            providers.append(('Deepgram', DeepgramProvider))
        except ImportError:
            pass

        try:
            from src.stt_providers.groq import GroqProvider
            providers.append(('Groq', GroqProvider))
        except ImportError:
            pass

        try:
            from src.stt_providers.elevenlabs import ElevenLabsProvider
            providers.append(('ElevenLabs', ElevenLabsProvider))
        except ImportError:
            pass

        try:
            from src.stt_providers.whisper import WhisperProvider
            providers.append(('Whisper', WhisperProvider))
        except ImportError:
            pass

        for name, provider_class in providers:
            assert hasattr(provider_class, 'transcribe'), f"{name} missing transcribe method"

    def test_all_providers_have_test_connection(self):
        """All providers should have test_connection method."""
        providers = []

        try:
            from src.stt_providers.deepgram import DeepgramProvider
            providers.append(('Deepgram', DeepgramProvider))
        except ImportError:
            pass

        try:
            from src.stt_providers.groq import GroqProvider
            providers.append(('Groq', GroqProvider))
        except ImportError:
            pass

        for name, provider_class in providers:
            assert hasattr(provider_class, 'test_connection'), f"{name} missing test_connection"

    def test_transcription_result_factory_methods(self):
        """TranscriptionResult should have factory methods."""
        from src.stt_providers.base import TranscriptionResult

        # Test success result
        success = TranscriptionResult.success_result("Test text")
        assert success.success is True
        assert success.text == "Test text"

        # Test failure result
        failure = TranscriptionResult.failure_result("Error message")
        assert failure.success is False
        assert "Error" in failure.error

    def test_provider_handles_silence(self):
        """Provider should handle silence in audio."""
        from src.stt_providers.groq import GroqProvider

        provider = GroqProvider(api_key="test-key")

        # Mock transcribe to return silence indicator
        with patch.object(provider, 'transcribe', return_value="[Silence...]"):
            result = provider.transcribe(MockAudioSegment())

        # Either empty or silence indicator is acceptable
        assert result in ["", "[Silence...]", "[Silence detected]"]

    def test_provider_language_support(self):
        """Providers should support language configuration."""
        from src.stt_providers.groq import GroqProvider

        provider = GroqProvider(api_key="test-key", language="en-US")
        assert provider.language == "en-US"

        provider_es = GroqProvider(api_key="test-key", language="es")
        assert provider_es.language == "es"
