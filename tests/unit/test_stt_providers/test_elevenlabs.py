"""Test ElevenLabs STT provider functionality."""
import pytest
import logging
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import numpy as np
from pydub import AudioSegment

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from stt_providers.elevenlabs import ElevenLabsProvider


class TestElevenLabsProvider:
    """Test ElevenLabs STT provider functionality."""

    @pytest.fixture(autouse=True)
    def mock_security(self):
        """Mock security manager for all tests."""
        with patch('utils.security_decorators.get_security_manager') as mock_security:
            mock_sec_mgr = MagicMock()
            mock_sec_mgr.get_api_key.return_value = "test-elevenlabs-key"
            mock_sec_mgr.validate_api_key.return_value = (True, None)
            mock_sec_mgr.check_rate_limit.return_value = (True, None)
            mock_sec_mgr.generate_secure_token.return_value = "mock-token"
            mock_security.return_value = mock_sec_mgr
            yield mock_security

    @pytest.fixture
    def provider(self):
        """Create an ElevenLabs provider instance."""
        return ElevenLabsProvider(api_key="test-elevenlabs-key", language="en-US")

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

    @pytest.fixture
    def mock_elevenlabs_response(self):
        """Create a mock ElevenLabs API response."""
        return {
            "text": "This is a test transcription",
            "words": [
                {"word": "This", "start": 0.0, "end": 0.2},
                {"word": "is", "start": 0.2, "end": 0.3},
                {"word": "a", "start": 0.3, "end": 0.4},
                {"word": "test", "start": 0.4, "end": 0.6},
                {"word": "transcription", "start": 0.6, "end": 1.0}
            ]
        }

    @pytest.fixture
    def mock_http_session(self):
        """Create a mock HTTP session."""
        session = MagicMock()
        return session

    def test_initialization(self):
        """Test provider initialization."""
        provider = ElevenLabsProvider(api_key="test-key", language="es-ES")

        assert provider.api_key == "test-key"
        assert provider.language == "es-ES"
        # Logger can be either standard Logger or StructuredLogger
        assert hasattr(provider.logger, 'info') and hasattr(provider.logger, 'error')

    def test_initialization_without_api_key(self):
        """Test provider initialization without API key."""
        provider = ElevenLabsProvider()

        assert provider.api_key == ""
        assert provider.language == "en-US"

    def test_provider_name(self, provider):
        """Test provider name property."""
        assert provider.provider_name == "elevenlabs"

    def test_supports_diarization(self, provider):
        """Test diarization support property."""
        assert provider.supports_diarization is True

    @patch('stt_providers.elevenlabs.settings_manager')
    @patch('stt_providers.elevenlabs.get_http_client_manager')
    def test_transcribe_success(self, mock_get_http_manager, mock_settings, provider, mock_audio_segment, mock_elevenlabs_response):
        """Test successful transcription."""
        # Mock settings
        mock_settings.get.return_value = {
            "diarize": False,
            "model_id": "scribe_v1",
            "tag_audio_events": True
        }

        # Mock HTTP session
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "mock response text"
        mock_response.json.return_value = mock_elevenlabs_response
        mock_session.post.return_value = mock_response

        mock_manager = MagicMock()
        mock_manager.get_requests_session.return_value = mock_session
        mock_get_http_manager.return_value = mock_manager

        result = provider.transcribe(mock_audio_segment)

        assert result == "This is a test transcription"

        # Verify API call was made
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert call_args[0][0] == "https://api.elevenlabs.io/v1/speech-to-text"
        assert call_args[1]["headers"]["xi-api-key"] == "test-elevenlabs-key"

    @patch('stt_providers.elevenlabs.settings_manager')
    @patch('stt_providers.elevenlabs.get_http_client_manager')
    def test_transcribe_with_diarization(self, mock_get_http_manager, mock_settings, provider, mock_audio_segment):
        """Test transcription with diarization enabled."""
        # Mock settings with diarization
        mock_settings.get.return_value = {
            "diarize": True,
            "num_speakers": 2,
            "language_code": "en-US",
            "timestamps_granularity": "word",
            "model_id": "scribe_v1",
            "tag_audio_events": True
        }

        # Mock response with speaker information
        mock_response_data = {
            "text": "Hello there Hi how are you",
            "words": [
                {"word": "Hello", "speaker": 0},
                {"word": "there", "speaker": 0},
                {"word": "Hi", "speaker": 1},
                {"word": "how", "speaker": 1},
                {"word": "are", "speaker": 1},
                {"word": "you", "speaker": 1}
            ]
        }

        # Mock HTTP session
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "mock response text"
        mock_response.json.return_value = mock_response_data
        mock_session.post.return_value = mock_response

        mock_manager = MagicMock()
        mock_manager.get_requests_session.return_value = mock_session
        mock_get_http_manager.return_value = mock_manager

        result = provider.transcribe(mock_audio_segment)

        # Check that diarization parameters were sent
        call_args = mock_session.post.call_args
        assert call_args[1]["data"]["diarize"] is True
        assert call_args[1]["data"]["num_speakers"] == 2
        assert call_args[1]["data"]["language_code"] == "en-US"
        assert call_args[1]["data"]["timestamps_granularity"] == "word"

        # Verify diarized output has speaker labels
        assert "Speaker 0:" in result
        assert "Speaker 1:" in result

    def test_transcribe_without_api_key(self, mock_audio_segment):
        """Test transcription without API key."""
        provider = ElevenLabsProvider()

        result = provider.transcribe(mock_audio_segment)

        assert result == ""

    @patch('stt_providers.elevenlabs.settings_manager')
    @patch('stt_providers.elevenlabs.get_http_client_manager')
    def test_transcribe_api_error(self, mock_get_http_manager, mock_settings, provider, mock_audio_segment):
        """Test handling of API errors."""
        # Mock settings
        mock_settings.get.return_value = {"diarize": False, "model_id": "scribe_v1", "tag_audio_events": True}

        # Mock HTTP session with error response
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_session.post.return_value = mock_response

        mock_manager = MagicMock()
        mock_manager.get_requests_session.return_value = mock_session
        mock_get_http_manager.return_value = mock_manager

        result = provider.transcribe(mock_audio_segment)

        # Should return empty string on API error
        assert result == ""

    @patch('stt_providers.elevenlabs.settings_manager')
    @patch('stt_providers.elevenlabs.get_http_client_manager')
    def test_transcribe_network_error(self, mock_get_http_manager, mock_settings, provider, mock_audio_segment):
        """Test handling of network errors."""
        # Mock settings
        mock_settings.get.return_value = {"diarize": False, "model_id": "scribe_v1", "tag_audio_events": True}

        # Mock HTTP session that raises an exception
        mock_session = MagicMock()
        mock_session.post.side_effect = Exception("Network error")

        mock_manager = MagicMock()
        mock_manager.get_requests_session.return_value = mock_session
        mock_get_http_manager.return_value = mock_manager

        result = provider.transcribe(mock_audio_segment)

        # Should return empty string on network error
        assert result == ""

    @patch('stt_providers.elevenlabs.settings_manager')
    @patch('stt_providers.elevenlabs.get_http_client_manager')
    def test_transcribe_timeout_calculation(self, mock_get_http_manager, mock_settings, provider, mock_audio_segment):
        """Test timeout calculation based on audio buffer size."""
        # Mock settings
        mock_settings.get.return_value = {"diarize": False, "model_id": "scribe_v1", "tag_audio_events": True}

        # Mock HTTP session
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"text": "test"}
        mock_session.post.return_value = mock_response

        mock_manager = MagicMock()
        mock_manager.get_requests_session.return_value = mock_session
        mock_get_http_manager.return_value = mock_manager

        result = provider.transcribe(mock_audio_segment)

        # Verify a timeout was set (minimum 60 seconds)
        call_args = mock_session.post.call_args
        assert call_args[1]["timeout"] >= 60

    def test_format_diarized_transcript(self, provider):
        """Test formatting of diarized transcript."""
        words = [
            {"word": "Hello", "speaker": 0},
            {"word": "there", "speaker": 0},
            {"word": ".", "speaker": 0},
            {"word": "Hi", "speaker": 1},
            {"word": "!", "speaker": 1},
        ]

        result = provider._format_diarized_transcript(words)

        assert "Speaker 0: Hello there." in result
        assert "Speaker 1: Hi!" in result

    def test_format_diarized_transcript_with_speaker_id(self, provider):
        """Test formatting with speaker_id field."""
        words = [
            {"word": "Hello", "speaker_id": "A"},
            {"word": "world", "speaker_id": "A"},
            {"word": "Hi", "speaker_id": "B"},
        ]

        result = provider._format_diarized_transcript(words)

        assert "Speaker A: Hello world" in result
        assert "Speaker B: Hi" in result

    def test_format_diarized_transcript_empty(self, provider):
        """Test formatting of empty transcript."""
        result = provider._format_diarized_transcript([])
        assert result == ""

    def test_format_diarized_transcript_no_speaker(self, provider):
        """Test formatting with missing speaker information."""
        words = [
            {"word": "Hello"},
            {"word": "world", "speaker": 0},
        ]

        result = provider._format_diarized_transcript(words)

        # Should use "Unknown" for words without speaker info
        assert "Speaker Unknown: Hello" in result
        assert "Speaker 0: world" in result

    def test_format_diarized_transcript_from_segments(self, provider):
        """Test formatting diarized transcript from segments structure."""
        result_data = {
            "diarization": [
                {"speaker": 0, "text": "Hello there."},
                {"speaker": 1, "text": "Hi, how are you?"},
                {"speaker": 0, "text": "I'm good, thanks!"}
            ]
        }

        formatted = provider._format_diarized_transcript_from_segments(result_data)

        assert "Speaker 0: Hello there." in formatted
        assert "Speaker 1: Hi, how are you?" in formatted
        assert "Speaker 0: I'm good, thanks!" in formatted

    def test_format_diarized_transcript_from_speakers(self, provider):
        """Test formatting diarized transcript from speakers structure."""
        result_data = {
            "speakers": [
                {
                    "id": 0,
                    "segments": [
                        {"text": "Hello there."},
                        {"text": " How's it going?"}
                    ]
                },
                {
                    "id": 1,
                    "segments": [
                        {"text": "Hi! "},
                        {"text": "I'm doing well."}
                    ]
                }
            ]
        }

        formatted = provider._format_diarized_transcript_from_speakers(result_data)

        assert "Speaker 0: Hello there. How's it going?" in formatted
        assert "Speaker 1: Hi! I'm doing well." in formatted

    def test_validate_and_log_audio(self, provider, mock_audio_segment):
        """Test audio validation logging."""
        details = provider._validate_and_log_audio(mock_audio_segment)

        assert 'duration_ms' in details
        assert 'frame_rate' in details
        assert 'channels' in details
        assert 'sample_width' in details
        assert details['frame_rate'] == 44100
        assert details['channels'] == 1

    @patch('stt_providers.elevenlabs.settings_manager')
    @patch('stt_providers.elevenlabs.get_http_client_manager')
    def test_transcribe_with_entity_detection(self, mock_get_http_manager, mock_settings, provider, mock_audio_segment):
        """Test transcription with entity detection enabled (scribe_v2 feature)."""
        # Mock settings with entity detection
        mock_settings.get.return_value = {
            "diarize": False,
            "model_id": "scribe_v2",
            "tag_audio_events": True,
            "entity_detection": ["phi", "pii"]
        }

        # Mock response with entity information
        mock_response_data = {
            "text": "Patient John Smith has diabetes",
            "entities": [
                {"entity_type": "pii", "text": "John Smith", "start_char": 8, "end_char": 18},
                {"entity_type": "phi", "text": "diabetes", "start_char": 23, "end_char": 31}
            ]
        }

        # Mock HTTP session
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "mock response text"
        mock_response.json.return_value = mock_response_data
        mock_session.post.return_value = mock_response

        mock_manager = MagicMock()
        mock_manager.get_requests_session.return_value = mock_session
        mock_get_http_manager.return_value = mock_manager

        result = provider.transcribe(mock_audio_segment)

        # Check that entity_detection was sent in request
        call_args = mock_session.post.call_args
        assert call_args[1]["data"]["entity_detection"] == ["phi", "pii"]
        assert result == "Patient John Smith has diabetes"

    @patch('stt_providers.elevenlabs.settings_manager')
    @patch('stt_providers.elevenlabs.get_http_client_manager')
    def test_transcribe_with_keyterms(self, mock_get_http_manager, mock_settings, provider, mock_audio_segment):
        """Test transcription with keyterms enabled (scribe_v2 feature)."""
        # Mock settings with keyterms
        mock_settings.get.return_value = {
            "diarize": False,
            "model_id": "scribe_v2",
            "tag_audio_events": True,
            "keyterms": ["hypertension", "metformin", "COPD"]
        }

        mock_response_data = {
            "text": "Patient has hypertension and takes metformin"
        }

        # Mock HTTP session
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "mock response text"
        mock_response.json.return_value = mock_response_data
        mock_session.post.return_value = mock_response

        mock_manager = MagicMock()
        mock_manager.get_requests_session.return_value = mock_session
        mock_get_http_manager.return_value = mock_manager

        result = provider.transcribe(mock_audio_segment)

        # Check that keyterms was sent in request
        call_args = mock_session.post.call_args
        assert call_args[1]["data"]["keyterms"] == ["hypertension", "metformin", "COPD"]
        assert result == "Patient has hypertension and takes metformin"

    @patch('stt_providers.elevenlabs.settings_manager')
    @patch('stt_providers.elevenlabs.get_http_client_manager')
    def test_transcribe_with_scribe_v2_model(self, mock_get_http_manager, mock_settings, provider, mock_audio_segment):
        """Test transcription with scribe_v2 model (new default)."""
        # Mock settings with scribe_v2
        mock_settings.get.return_value = {
            "diarize": False,
            "model_id": "scribe_v2",
            "tag_audio_events": True,
            "entity_detection": [],
            "keyterms": []
        }

        mock_response_data = {
            "text": "Test with scribe v2 model"
        }

        # Mock HTTP session
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "mock response text"
        mock_response.json.return_value = mock_response_data
        mock_session.post.return_value = mock_response

        mock_manager = MagicMock()
        mock_manager.get_requests_session.return_value = mock_session
        mock_get_http_manager.return_value = mock_manager

        result = provider.transcribe(mock_audio_segment)

        # Check that scribe_v2 model was used
        call_args = mock_session.post.call_args
        assert call_args[1]["data"]["model_id"] == "scribe_v2"
        assert result == "Test with scribe v2 model"

    @patch('stt_providers.elevenlabs.settings_manager')
    @patch('stt_providers.elevenlabs.get_http_client_manager')
    def test_default_model_is_scribe_v2(self, mock_get_http_manager, mock_settings, provider, mock_audio_segment):
        """Test that the default model is scribe_v2."""
        # Mock settings with empty model_id (should default to scribe_v2)
        mock_settings.get.return_value = {
            "diarize": False,
            "tag_audio_events": True
        }

        mock_response_data = {
            "text": "Test default model"
        }

        # Mock HTTP session
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "mock response text"
        mock_response.json.return_value = mock_response_data
        mock_session.post.return_value = mock_response

        mock_manager = MagicMock()
        mock_manager.get_requests_session.return_value = mock_session
        mock_get_http_manager.return_value = mock_manager

        result = provider.transcribe(mock_audio_segment)

        # Check that default model is scribe_v2
        call_args = mock_session.post.call_args
        assert call_args[1]["data"]["model_id"] == "scribe_v2"
