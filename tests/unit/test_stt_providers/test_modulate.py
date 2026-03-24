"""Test Modulate STT provider functionality against the real Velma-2 Batch API spec."""
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import numpy as np
from pydub import AudioSegment

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from stt_providers.modulate import ModulateProvider, MODULATE_BATCH_ENGLISH_URL, MODULATE_BATCH_MULTILINGUAL_URL


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


# Mock response matching the real Velma-2 Batch API spec
MOCK_API_RESPONSE = {
    "text": "I've been having these headaches for about a week now. Let me take a look.",
    "duration_ms": 5200,
    "utterances": [
        {
            "utterance_uuid": "e5f6a7b8-c9d0-1234-efab-345678901234",
            "text": "I've been having these headaches for about a week now.",
            "start_ms": 0,
            "duration_ms": 3200,
            "speaker": 1,
            "language": "en",
            "emotion": "Anxious",
            "accent": "American",
        },
        {
            "utterance_uuid": "f6a7b8c9-d0e1-2345-fabc-456789012345",
            "text": "Let me take a look.",
            "start_ms": 3500,
            "duration_ms": 1700,
            "speaker": 2,
            "language": "en",
            "emotion": "Calm",
            "accent": "American",
        },
    ],
}

MOCK_SINGLE_SPEAKER_RESPONSE = {
    "text": "I've been having these headaches for about a week now",
    "duration_ms": 3200,
    "utterances": [
        {
            "utterance_uuid": "e5f6a7b8-c9d0-1234-efab-345678901234",
            "text": "I've been having these headaches for about a week now",
            "start_ms": 0,
            "duration_ms": 3200,
            "speaker": 1,
            "language": "en",
            "emotion": "Anxious",
            "accent": None,
        },
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
    """Test Modulate transcription against real API response format."""

    @patch("utils.security_decorators.get_security_manager")
    @patch("stt_providers.modulate.get_http_client_manager")
    @patch("stt_providers.modulate.settings_manager")
    def test_transcribe_success(self, mock_settings, mock_get_manager, mock_get_sm, provider, mock_audio_segment):
        mock_get_sm.return_value = _make_mock_security_manager()
        mock_settings.get.return_value = {"model": "batch-english-fast",
                                           "enable_emotions": True, "enable_diarization": True}
        mock_manager, mock_session, _ = _make_mock_session(MOCK_API_RESPONSE)
        mock_get_manager.return_value = mock_manager

        result = provider.transcribe(mock_audio_segment)

        assert "headaches" in result
        mock_session.post.assert_called_once()

    @patch("utils.security_decorators.get_security_manager")
    @patch("stt_providers.modulate.get_http_client_manager")
    @patch("stt_providers.modulate.settings_manager")
    def test_transcribe_uses_correct_auth_header(self, mock_settings, mock_get_manager, mock_get_sm, provider, mock_audio_segment):
        """Verify X-API-Key header is used (not Authorization: Bearer)."""
        mock_get_sm.return_value = _make_mock_security_manager()
        mock_settings.get.return_value = {"model": "batch-english-fast"}
        mock_manager, mock_session, _ = _make_mock_session(MOCK_API_RESPONSE)
        mock_get_manager.return_value = mock_manager

        provider.transcribe(mock_audio_segment)

        call_args = mock_session.post.call_args
        headers = call_args[1].get('headers', call_args[0][1] if len(call_args[0]) > 1 else {})
        assert 'X-API-Key' in headers
        assert 'Authorization' not in headers

    @patch("utils.security_decorators.get_security_manager")
    @patch("stt_providers.modulate.get_http_client_manager")
    @patch("stt_providers.modulate.settings_manager")
    def test_transcribe_uses_correct_file_field(self, mock_settings, mock_get_manager, mock_get_sm, provider, mock_audio_segment):
        """Verify upload_file field name is used (not file)."""
        mock_get_sm.return_value = _make_mock_security_manager()
        mock_settings.get.return_value = {"model": "batch-english-fast"}
        mock_manager, mock_session, _ = _make_mock_session(MOCK_API_RESPONSE)
        mock_get_manager.return_value = mock_manager

        provider.transcribe(mock_audio_segment)

        call_args = mock_session.post.call_args
        files = call_args[1].get('files', {})
        assert 'upload_file' in files
        assert 'file' not in files

    @patch("utils.security_decorators.get_security_manager")
    @patch("stt_providers.modulate.get_http_client_manager")
    @patch("stt_providers.modulate.settings_manager")
    def test_transcribe_uses_correct_feature_params(self, mock_settings, mock_get_manager, mock_get_sm, provider, mock_audio_segment):
        """Verify API-correct parameter names for features."""
        mock_get_sm.return_value = _make_mock_security_manager()
        mock_settings.get.return_value = {
            "model": "batch-english-fast",
            "enable_diarization": True,
            "enable_emotions": True,
            "enable_accent_detection": True,
            "enable_pii_tagging": True,
        }
        mock_manager, mock_session, _ = _make_mock_session(MOCK_API_RESPONSE)
        mock_get_manager.return_value = mock_manager

        provider.transcribe(mock_audio_segment)

        call_args = mock_session.post.call_args
        data = call_args[1].get('data', {})
        assert data.get('speaker_diarization') == 'true'
        assert data.get('emotion_signal') == 'true'
        assert data.get('accent_signal') == 'true'
        assert data.get('pii_phi_tagging') == 'true'
        # Old param names should NOT be present
        assert 'diarize' not in data
        assert 'enable_emotions' not in data

    @patch("utils.security_decorators.get_security_manager")
    @patch("stt_providers.modulate.get_http_client_manager")
    @patch("stt_providers.modulate.settings_manager")
    def test_transcribe_diarized_multi_speaker(self, mock_settings, mock_get_manager, mock_get_sm, provider, mock_audio_segment):
        """Verify diarized output with multiple speakers."""
        mock_get_sm.return_value = _make_mock_security_manager()
        mock_settings.get.return_value = {"model": "batch-english-fast", "enable_diarization": True}
        mock_manager, _, _ = _make_mock_session(MOCK_API_RESPONSE)
        mock_get_manager.return_value = mock_manager

        result = provider.transcribe(mock_audio_segment)

        assert "Speaker 1:" in result
        assert "Speaker 2:" in result
        assert "headaches" in result

    @patch("utils.security_decorators.get_security_manager")
    @patch("stt_providers.modulate.get_http_client_manager")
    @patch("stt_providers.modulate.settings_manager")
    def test_transcribe_single_speaker_still_has_label(self, mock_settings, mock_get_manager, mock_get_sm, provider, mock_audio_segment):
        """Single speaker should still show speaker label when diarization is enabled."""
        mock_get_sm.return_value = _make_mock_security_manager()
        mock_settings.get.return_value = {"model": "batch-english-fast", "enable_diarization": True}
        mock_manager, _, _ = _make_mock_session(MOCK_SINGLE_SPEAKER_RESPONSE)
        mock_get_manager.return_value = mock_manager

        result = provider.transcribe(mock_audio_segment)

        assert "Speaker 1:" in result
        assert "headaches" in result

    @patch("utils.security_decorators.get_security_manager")
    @patch("stt_providers.modulate.get_http_client_manager")
    @patch("stt_providers.modulate.settings_manager")
    def test_transcribe_with_result_has_emotion_data(self, mock_settings, mock_get_manager, mock_get_sm, provider, mock_audio_segment):
        mock_get_sm.return_value = _make_mock_security_manager()
        mock_settings.get.return_value = {"model": "batch-english-fast",
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
    def test_emotion_data_transformed_for_processor(self, mock_settings, mock_get_manager, mock_get_sm, provider, mock_audio_segment):
        """Verify emotions are transformed into v2 format expected by emotion_processor."""
        mock_get_sm.return_value = _make_mock_security_manager()
        mock_settings.get.return_value = {"model": "batch-english-fast", "enable_emotions": True}
        mock_manager, _, _ = _make_mock_session(MOCK_API_RESPONSE)
        mock_get_manager.return_value = mock_manager

        result = provider.transcribe_with_result(mock_audio_segment)
        emotion_data = result.metadata.get("emotion_data", {})

        # Should be version 2
        assert emotion_data.get("version") == 2

        # Should have segments list (format for emotion_processor)
        assert "segments" in emotion_data
        assert isinstance(emotion_data["segments"], list)
        assert len(emotion_data["segments"]) == 2

        # First utterance: emotion_label is clinical name, emotion_raw is original
        seg0 = emotion_data["segments"][0]
        assert seg0["emotion_label"] == "anxiety"
        assert seg0["emotion_raw"] == "Anxious"
        # Backward compat emotions dict present with clinical name
        assert "anxiety" in seg0["emotions"]
        assert seg0["emotions"]["anxiety"] == 1.0
        # No fake neutral score
        assert "neutral" not in seg0["emotions"]

        # Overall uses emotion_distribution (not average_emotions)
        assert "overall" in emotion_data
        assert "dominant_emotion" in emotion_data["overall"]
        assert "emotion_distribution" in emotion_data["overall"]
        assert "average_emotions" not in emotion_data["overall"]
        assert "total_segments" in emotion_data["overall"]

    @patch("utils.security_decorators.get_security_manager")
    @patch("stt_providers.modulate.get_http_client_manager")
    @patch("stt_providers.modulate.settings_manager")
    def test_emotion_data_v2_overall_has_distribution(self, mock_settings, mock_get_manager, mock_get_sm, provider, mock_audio_segment):
        """Verify the v2 overall structure contains correct distribution and counts."""
        mock_get_sm.return_value = _make_mock_security_manager()
        mock_settings.get.return_value = {"model": "batch-english-fast", "enable_emotions": True}
        mock_manager, _, _ = _make_mock_session(MOCK_API_RESPONSE)
        mock_get_manager.return_value = mock_manager

        result = provider.transcribe_with_result(mock_audio_segment)
        emotion_data = result.metadata.get("emotion_data", {})
        overall = emotion_data["overall"]

        # emotion_distribution should be raw counts (not proportions)
        assert overall["emotion_distribution"] == {"anxiety": 1, "calm": 1}
        assert overall["total_segments"] == 2
        # dominant_emotion should be one of the tied emotions
        assert overall["dominant_emotion"] in ("anxiety", "calm")

    @patch("utils.security_decorators.get_security_manager")
    @patch("stt_providers.modulate.get_http_client_manager")
    @patch("stt_providers.modulate.settings_manager")
    def test_accent_data_in_metadata(self, mock_settings, mock_get_manager, mock_get_sm, provider, mock_audio_segment):
        """Verify accent detection data is captured in metadata."""
        mock_get_sm.return_value = _make_mock_security_manager()
        mock_settings.get.return_value = {"model": "batch-english-fast", "enable_accent_detection": True}
        mock_manager, _, _ = _make_mock_session(MOCK_API_RESPONSE)
        mock_get_manager.return_value = mock_manager

        result = provider.transcribe_with_result(mock_audio_segment)

        assert "accent_detection" in result.metadata
        assert "American" in result.metadata["accent_detection"]["accents"]


class TestModulateEndpointSelection:
    """Test model-to-endpoint mapping."""

    def test_english_fast_endpoint(self):
        provider = ModulateProvider(api_key="test-key")
        url = provider._get_endpoint_url({"model": "batch-english-fast"})
        assert url == MODULATE_BATCH_ENGLISH_URL

    def test_multilingual_endpoint(self):
        provider = ModulateProvider(api_key="test-key")
        url = provider._get_endpoint_url({"model": "batch-multilingual"})
        assert url == MODULATE_BATCH_MULTILINGUAL_URL

    def test_default_endpoint(self):
        provider = ModulateProvider(api_key="test-key")
        url = provider._get_endpoint_url({"model": "default"})
        assert url == MODULATE_BATCH_ENGLISH_URL

    def test_unknown_model_falls_back(self):
        provider = ModulateProvider(api_key="test-key")
        url = provider._get_endpoint_url({"model": "nonexistent"})
        assert url == MODULATE_BATCH_ENGLISH_URL


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

    @patch("time.sleep")
    @patch("utils.security_decorators.get_security_manager")
    @patch("stt_providers.modulate.get_http_client_manager")
    @patch("stt_providers.modulate.settings_manager")
    def test_forbidden_error_403(self, mock_settings, mock_get_manager, mock_get_sm, mock_sleep, provider, mock_audio_segment):
        mock_get_sm.return_value = _make_mock_security_manager()
        mock_settings.get.return_value = {}
        mock_manager, _, _ = _make_mock_session({"error": "model not enabled"}, status_code=403)
        mock_get_manager.return_value = mock_manager

        from utils.exceptions import TranscriptionError
        with pytest.raises(TranscriptionError, match="access forbidden"):
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
    def test_connection_uses_correct_headers(self, mock_get_manager, provider):
        """Verify test_connection uses X-API-Key header."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_session = Mock()
        mock_session.post.return_value = mock_response
        mock_manager = Mock()
        mock_manager.get_requests_session.return_value = mock_session
        mock_get_manager.return_value = mock_manager

        provider.test_connection()

        call_args = mock_session.post.call_args
        headers = call_args[1].get('headers', {})
        assert 'X-API-Key' in headers

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

    @patch("stt_providers.modulate.get_http_client_manager")
    def test_connection_forbidden_403(self, mock_get_manager, provider):
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = "Model not enabled"
        mock_session = Mock()
        mock_session.post.return_value = mock_response
        mock_manager = Mock()
        mock_manager.get_requests_session.return_value = mock_session
        mock_get_manager.return_value = mock_manager

        result = provider.test_connection()
        assert result is False
