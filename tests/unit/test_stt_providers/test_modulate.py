"""Test Modulate STT provider functionality."""
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import numpy as np
from pydub import AudioSegment

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from stt_providers.modulate import ModulateProvider


def _make_mock_security_manager():
    """Create a mock security manager that returns a valid API key."""
    mock_sm = Mock()
    mock_sm.get_api_key.return_value = "test-modulate-key"
    mock_sm.validate_api_key.return_value = (True, None)
    mock_sm.check_rate_limit.return_value = (True, 0)
    mock_sm.generate_secure_token.return_value = "test-token-123"
    return mock_sm


class TestModulateProviderInitialization:
    """Test Modulate provider initialization."""

    def test_initialization_with_api_key(self):
        provider = ModulateProvider(api_key="test-modulate-key")
        assert provider.api_key == "test-modulate-key"

    def test_initialization_without_api_key(self):
        provider = ModulateProvider()
        assert provider.api_key == ""

    def test_initialization_with_language(self):
        provider = ModulateProvider(api_key="test-key", language="en-US")
        assert provider.api_key == "test-key"
        assert provider.language == "en-US"

    def test_provider_name(self):
        provider = ModulateProvider(api_key="test-key")
        assert provider.provider_name == "modulate"

    def test_supports_diarization(self):
        provider = ModulateProvider(api_key="test-key")
        assert provider.supports_diarization is True


@pytest.fixture
def provider():
    return ModulateProvider(api_key="test-modulate-key")


@pytest.fixture
def mock_audio_segment():
    duration_ms = 1000
    sample_rate = 44100
    samples = np.zeros(int(sample_rate * duration_ms / 1000), dtype=np.int16)
    return AudioSegment(
        samples.tobytes(), frame_rate=sample_rate, sample_width=2, channels=1
    )


MOCK_API_RESPONSE = {
    "text": "I've been having these headaches for about a week now",
    "emotion_data": [
        {
            "start_time": 0.0,
            "end_time": 5.2,
            "speaker": "speaker_0",
            "text": "I've been having these headaches for about a week now",
            "emotions": {
                "anxiety": 0.72,
                "sadness": 0.15,
                "neutral": 0.45,
                "anger": 0.05,
                "joy": 0.02,
                "fear": 0.31,
            },
        }
    ],
}


def _make_mock_session(response_data, status_code=200):
    """Create a mock requests session that returns the given response."""
    mock_response = Mock()
    mock_response.status_code = status_code
    mock_response.json.return_value = response_data
    mock_response.text = str(response_data)
    mock_response.raise_for_status = Mock()

    mock_session = Mock()
    mock_session.post.return_value = mock_response
    mock_session.get.return_value = mock_response

    mock_manager = Mock()
    mock_manager.get_requests_session.return_value = mock_session
    return mock_manager, mock_session, mock_response


class TestModulateTranscription:
    """Test Modulate transcription and emotion parsing."""

    @patch("utils.security_decorators.get_security_manager")
    @patch("stt_providers.modulate.get_http_client_manager")
    @patch("stt_providers.modulate.settings_manager")
    def test_transcribe_success(self, mock_settings, mock_get_manager, mock_get_sm, provider, mock_audio_segment):
        mock_get_sm.return_value = _make_mock_security_manager()
        mock_settings.get.return_value = {"model": "default", "language": "en-US",
                                           "enable_emotions": True, "enable_diarization": True}
        mock_manager, mock_session, _ = _make_mock_session(MOCK_API_RESPONSE)
        mock_get_manager.return_value = mock_manager

        result = provider.transcribe(mock_audio_segment)

        assert "headaches" in result
        mock_session.post.assert_called_once()

    @patch("utils.security_decorators.get_security_manager")
    @patch("stt_providers.modulate.get_http_client_manager")
    @patch("stt_providers.modulate.settings_manager")
    def test_transcribe_with_result_has_emotion_data(self, mock_settings, mock_get_manager, mock_get_sm, provider, mock_audio_segment):
        mock_get_sm.return_value = _make_mock_security_manager()
        mock_settings.get.return_value = {"model": "default", "language": "en-US",
                                           "enable_emotions": True, "enable_diarization": True}
        mock_manager, _, _ = _make_mock_session(MOCK_API_RESPONSE)
        mock_get_manager.return_value = mock_manager

        result = provider.transcribe_with_result(mock_audio_segment)

        assert result.success
        assert "headaches" in result.text
        assert "emotion_data" in result.metadata

    @patch("utils.security_decorators.get_security_manager")
    @patch("stt_providers.modulate.get_http_client_manager")
    @patch("stt_providers.modulate.settings_manager")
    def test_transcribe_parses_emotions(self, mock_settings, mock_get_manager, mock_get_sm, provider, mock_audio_segment):
        mock_get_sm.return_value = _make_mock_security_manager()
        mock_settings.get.return_value = {"model": "default", "language": "en-US",
                                           "enable_emotions": True, "enable_diarization": True}
        mock_manager, _, _ = _make_mock_session(MOCK_API_RESPONSE)
        mock_get_manager.return_value = mock_manager

        result = provider.transcribe_with_result(mock_audio_segment)
        emotion_data = result.metadata.get("emotion_data", [])

        assert isinstance(emotion_data, list)
        assert len(emotion_data) > 0
        assert emotion_data[0]["emotions"]["anxiety"] == 0.72


class TestModulateDiarization:
    """Test Modulate diarization formatting."""

    DIARIZED_RESPONSE = {
        "text": "Hello how are you I am doing well",
        "words": [
            {"word": "Hello", "start": 0.0, "end": 0.5, "speaker_id": 0},
            {"word": "how", "start": 0.5, "end": 0.8, "speaker_id": 0},
            {"word": "are", "start": 0.8, "end": 1.0, "speaker_id": 0},
            {"word": "you", "start": 1.0, "end": 1.5, "speaker_id": 0},
            {"word": "I", "start": 3.5, "end": 3.7, "speaker_id": 1},
            {"word": "am", "start": 3.7, "end": 4.0, "speaker_id": 1},
            {"word": "doing", "start": 4.0, "end": 4.5, "speaker_id": 1},
            {"word": "well", "start": 4.5, "end": 5.0, "speaker_id": 1},
        ],
    }

    @patch("utils.security_decorators.get_security_manager")
    @patch("stt_providers.modulate.get_http_client_manager")
    @patch("stt_providers.modulate.settings_manager")
    def test_diarization_formatting(self, mock_settings, mock_get_manager, mock_get_sm, mock_audio_segment):
        mock_get_sm.return_value = _make_mock_security_manager()
        mock_settings.get.return_value = {"model": "default", "language": "en-US",
                                           "enable_emotions": True, "enable_diarization": True}
        mock_manager, _, _ = _make_mock_session(self.DIARIZED_RESPONSE)
        mock_get_manager.return_value = mock_manager

        provider = ModulateProvider(api_key="test-key")
        result = provider.transcribe(mock_audio_segment)

        assert isinstance(result, str)
        assert len(result) > 0


class TestModulateErrorHandling:
    """Test Modulate provider error handling."""

    @patch("time.sleep")  # Skip retry delays
    @patch("utils.security_decorators.get_security_manager")
    @patch("stt_providers.modulate.get_http_client_manager")
    @patch("stt_providers.modulate.settings_manager")
    def test_rate_limit_error_429(self, mock_settings, mock_get_manager, mock_get_sm, mock_sleep, provider, mock_audio_segment):
        mock_get_sm.return_value = _make_mock_security_manager()
        mock_settings.get.return_value = {}
        mock_manager, _, _ = _make_mock_session({"error": "rate limit"}, status_code=429)
        mock_get_manager.return_value = mock_manager

        # The provider raises TranscriptionError on 429 after retries
        from utils.exceptions import TranscriptionError
        with pytest.raises(TranscriptionError, match="rate limit"):
            provider.transcribe(mock_audio_segment)

    @patch("time.sleep")  # Skip retry delays
    @patch("utils.security_decorators.get_security_manager")
    @patch("stt_providers.modulate.get_http_client_manager")
    @patch("stt_providers.modulate.settings_manager")
    def test_server_error_500(self, mock_settings, mock_get_manager, mock_get_sm, mock_sleep, provider, mock_audio_segment):
        mock_get_sm.return_value = _make_mock_security_manager()
        mock_settings.get.return_value = {}
        mock_manager, _, _ = _make_mock_session({"error": "server error"}, status_code=500)
        mock_get_manager.return_value = mock_manager

        from utils.exceptions import TranscriptionError
        with pytest.raises(TranscriptionError, match="service error"):
            provider.transcribe(mock_audio_segment)

    def test_transcribe_without_api_key(self, mock_audio_segment):
        provider = ModulateProvider()
        result = provider.transcribe(mock_audio_segment)
        assert result == ""


class TestModulateTestConnection:
    """Test the test_connection method."""

    @patch("stt_providers.modulate.get_http_client_manager")
    def test_connection_success(self, mock_get_manager, provider):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_session = Mock()
        mock_session.post.return_value = mock_response
        mock_manager = Mock()
        mock_manager.get_requests_session.return_value = mock_session
        mock_get_manager.return_value = mock_manager

        result = provider.test_connection()
        assert result is True

    @patch("stt_providers.modulate.get_http_client_manager")
    def test_connection_failure(self, mock_get_manager, provider):
        import requests
        mock_session = Mock()
        mock_session.post.side_effect = requests.exceptions.ConnectionError("Connection refused")
        mock_manager = Mock()
        mock_manager.get_requests_session.return_value = mock_session
        mock_get_manager.return_value = mock_manager

        result = provider.test_connection()
        assert result is False

    def test_connection_without_api_key(self):
        provider = ModulateProvider()
        result = provider.test_connection()
        assert result is False

    @patch("stt_providers.modulate.get_http_client_manager")
    def test_connection_timeout(self, mock_get_manager, provider):
        import requests
        mock_session = Mock()
        mock_session.post.side_effect = requests.exceptions.Timeout("Timed out")
        mock_manager = Mock()
        mock_manager.get_requests_session.return_value = mock_session
        mock_get_manager.return_value = mock_manager

        result = provider.test_connection()
        assert result is False
