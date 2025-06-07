"""Test ElevenLabs STT provider functionality."""
import pytest
import os
import json
import tempfile
import logging
from unittest.mock import Mock, patch, MagicMock, mock_open
import numpy as np
from pydub import AudioSegment

from stt_providers.elevenlabs import ElevenLabsProvider


class TestElevenLabsProvider:
    """Test ElevenLabs STT provider functionality."""
    
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
    
    def test_initialization(self):
        """Test provider initialization."""
        provider = ElevenLabsProvider(api_key="test-key", language="es-ES")
        
        assert provider.api_key == "test-key"
        assert provider.language == "es-ES"
        assert isinstance(provider.logger, logging.Logger)
    
    def test_initialization_without_api_key(self):
        """Test provider initialization without API key."""
        provider = ElevenLabsProvider()
        
        assert provider.api_key == ""
        assert provider.language == "en-US"
    
    @patch('stt_providers.elevenlabs.SETTINGS')
    @patch('stt_providers.elevenlabs.requests.post')
    @patch('stt_providers.elevenlabs.tempfile.NamedTemporaryFile')
    def test_transcribe_success(self, mock_temp_file, mock_post, mock_settings, provider, mock_audio_segment, mock_elevenlabs_response):
        """Test successful transcription."""
        # Mock settings
        mock_settings.get.return_value = {
            "diarize": False
        }
        
        # Mock temporary file
        mock_temp = MagicMock()
        mock_temp.name = "/tmp/test_audio.wav"
        mock_temp_file.return_value.__enter__.return_value = mock_temp
        
        # Mock file operations
        mock_file = MagicMock()
        mock_file.read.return_value = b"fake audio data"
        
        # Use a context manager to properly mock open()
        with patch('builtins.open', return_value=mock_file):
            with patch('os.path.getsize', return_value=1024):  # 1KB file
                # Mock successful API response
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.text = "mock response text"  # Add text attribute for len() call
                mock_response.json.return_value = mock_elevenlabs_response
                mock_post.return_value = mock_response
                
                result = provider.transcribe(mock_audio_segment)
        
        assert result == "This is a test transcription"
        
        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://api.elevenlabs.io/v1/speech-to-text"
        assert call_args[1]["headers"]["xi-api-key"] == "test-elevenlabs-key"
        assert call_args[1]["data"]["model_id"] == "scribe_v1"
    
    @patch('stt_providers.elevenlabs.SETTINGS')
    @patch('stt_providers.elevenlabs.requests.post')
    @patch('stt_providers.elevenlabs.tempfile.NamedTemporaryFile')
    def test_transcribe_with_diarization(self, mock_temp_file, mock_post, mock_settings, provider, mock_audio_segment):
        """Test transcription with diarization enabled."""
        # Mock settings with diarization
        mock_settings.get.return_value = {
            "diarize": True,
            "num_speakers": 2,
            "language_code": "en-US",
            "timestamps_granularity": "word"
        }
        
        # Mock temporary file
        mock_temp = MagicMock()
        mock_temp.name = "/tmp/test_audio.wav"
        mock_temp_file.return_value.__enter__.return_value = mock_temp
        
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
        
        # Mock file operations
        mock_file = MagicMock()
        mock_file.read.return_value = b"fake audio data"
        
        # Use a context manager to properly mock open()
        with patch('builtins.open', return_value=mock_file):
            with patch('os.path.getsize', return_value=1024):
                # Mock successful API response
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.text = "mock response text"  # Add text attribute for len() call
                mock_response.json.return_value = mock_response_data
                mock_post.return_value = mock_response
                
                result = provider.transcribe(mock_audio_segment)
        
        # Check that diarization parameters were sent
        call_args = mock_post.call_args
        assert call_args[1]["data"]["diarize"] is True
        assert call_args[1]["data"]["num_speakers"] == 2
        assert call_args[1]["data"]["language_code"] == "en-US"
        assert call_args[1]["data"]["timestamps_granularity"] == "word"
        
        # Verify diarized output
        assert "Speaker 0:" in result
        assert "Speaker 1:" in result
    
    def test_transcribe_without_api_key(self, mock_audio_segment):
        """Test transcription without API key."""
        provider = ElevenLabsProvider()
        
        result = provider.transcribe(mock_audio_segment)
        
        assert result == ""
    
    @patch('stt_providers.elevenlabs.SETTINGS')
    @patch('stt_providers.elevenlabs.requests.post')
    @patch('stt_providers.elevenlabs.tempfile.NamedTemporaryFile')
    def test_transcribe_api_error(self, mock_temp_file, mock_post, mock_settings, provider, mock_audio_segment):
        """Test handling of API errors."""
        # Mock settings
        mock_settings.get.return_value = {"diarize": False}
        
        # Mock temporary file
        mock_temp = MagicMock()
        mock_temp.name = "/tmp/test_audio.wav"
        mock_temp_file.return_value.__enter__.return_value = mock_temp
        
        # Mock file operations
        mock_file = MagicMock()
        mock_file.read.return_value = b"fake audio data"
        
        # Use a context manager to properly mock open()
        with patch('builtins.open', return_value=mock_file):
            with patch('os.path.getsize', return_value=1024):
                # Mock API error response
                mock_response = Mock()
                mock_response.status_code = 401
                mock_response.text = "Unauthorized"
                mock_post.return_value = mock_response
                
                result = provider.transcribe(mock_audio_segment)
        
        assert result == ""
    
    @patch('stt_providers.elevenlabs.SETTINGS')
    @patch('stt_providers.elevenlabs.requests.post')
    @patch('stt_providers.elevenlabs.tempfile.NamedTemporaryFile')
    def test_transcribe_network_error(self, mock_temp_file, mock_post, mock_settings, provider, mock_audio_segment):
        """Test handling of network errors."""
        # Mock settings
        mock_settings.get.return_value = {"diarize": False}
        
        # Mock temporary file
        mock_temp = MagicMock()
        mock_temp.name = "/tmp/test_audio.wav"
        mock_temp_file.return_value.__enter__.return_value = mock_temp
        
        # Mock file operations
        mock_file = MagicMock()
        mock_file.read.return_value = b"fake audio data"
        
        # Use a context manager to properly mock open()
        with patch('builtins.open', return_value=mock_file):
            with patch('os.path.getsize', return_value=1024):
                # Mock network error
                mock_post.side_effect = Exception("Network error")
                
                result = provider.transcribe(mock_audio_segment)
        
        assert result == ""
    
    @patch('stt_providers.elevenlabs.SETTINGS')
    @patch('stt_providers.elevenlabs.requests.post')
    @patch('stt_providers.elevenlabs.tempfile.NamedTemporaryFile')
    def test_transcribe_timeout_calculation(self, mock_temp_file, mock_post, mock_settings, provider, mock_audio_segment):
        """Test timeout calculation based on file size."""
        # Mock settings
        mock_settings.get.return_value = {"diarize": False}
        
        # Mock temporary file
        mock_temp = MagicMock()
        mock_temp.name = "/tmp/test_audio.wav"
        mock_temp_file.return_value.__enter__.return_value = mock_temp
        
        # Test different file sizes
        test_cases = [
            (100 * 1024, 60),     # 100KB -> 60s (minimum)
            (500 * 1024, 60),     # 500KB -> 60s (minimum)
            (1000 * 1024, 120),   # 1MB -> 120s
            (2500 * 1024, 300),   # 2.5MB -> 300s
        ]
        
        for file_size, expected_timeout in test_cases:
            with patch('builtins.open', mock_open()):
                with patch('os.path.getsize', return_value=file_size):
                    # Mock successful API response
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = {"text": "test"}
                    mock_post.return_value = mock_response
                    
                    provider.transcribe(mock_audio_segment)
                    
                    # Check timeout parameter
                    call_args = mock_post.call_args
                    assert call_args[1]["timeout"] == expected_timeout
    
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
    
    @patch('stt_providers.elevenlabs.SETTINGS')
    @patch('stt_providers.elevenlabs.requests.post')
    @patch('stt_providers.elevenlabs.tempfile.NamedTemporaryFile')
    def test_file_cleanup_on_success(self, mock_temp_file, mock_post, mock_settings, provider, mock_audio_segment):
        """Test that temporary files are cleaned up on success."""
        # Mock settings
        mock_settings.get.return_value = {"diarize": False}
        
        # Mock temporary file
        mock_temp = MagicMock()
        temp_file_path = "/tmp/test_audio.wav"
        mock_temp.name = temp_file_path
        mock_temp_file.return_value.__enter__.return_value = mock_temp
        
        # Track file operations
        file_deleted = False
        
        def mock_unlink(path):
            nonlocal file_deleted
            if path == temp_file_path:
                file_deleted = True
        
        with patch('builtins.open', mock_open()):
            with patch('os.path.getsize', return_value=1024):
                with patch('os.path.exists', return_value=True):
                    with patch('os.unlink', side_effect=mock_unlink):
                        # Mock successful API response
                        mock_response = Mock()
                        mock_response.status_code = 200
                        mock_response.json.return_value = {"text": "test"}
                        mock_post.return_value = mock_response
                        
                        provider.transcribe(mock_audio_segment)
        
        assert file_deleted, "Temporary file should be deleted"
    
    @patch('stt_providers.elevenlabs.SETTINGS')
    @patch('stt_providers.elevenlabs.requests.post')
    @patch('stt_providers.elevenlabs.tempfile.NamedTemporaryFile')
    def test_file_cleanup_on_error(self, mock_temp_file, mock_post, mock_settings, provider, mock_audio_segment):
        """Test that temporary files are cleaned up on error."""
        # Mock settings
        mock_settings.get.return_value = {"diarize": False}
        
        # Mock temporary file
        mock_temp = MagicMock()
        temp_file_path = "/tmp/test_audio.wav"
        mock_temp.name = temp_file_path
        mock_temp_file.return_value.__enter__.return_value = mock_temp
        
        # Track cleanup attempts
        cleanup_attempted = False
        
        def mock_unlink(path):
            nonlocal cleanup_attempted
            if path == temp_file_path:
                cleanup_attempted = True
        
        with patch('builtins.open', mock_open()):
            with patch('os.path.getsize', return_value=1024):
                with patch('os.path.exists', return_value=True):
                    with patch('os.unlink', side_effect=mock_unlink):
                        # Mock API error
                        mock_post.side_effect = Exception("API Error")
                        
                        provider.transcribe(mock_audio_segment)
        
        assert cleanup_attempted, "Cleanup should be attempted even on error"
    
    @patch('stt_providers.elevenlabs.SETTINGS')
    def test_format_diarized_transcript_from_segments(self, mock_settings, provider):
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
    
    @patch('stt_providers.elevenlabs.SETTINGS')
    def test_format_diarized_transcript_from_speakers(self, mock_settings, provider):
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