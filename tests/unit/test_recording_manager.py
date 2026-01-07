"""Test recording manager functionality."""
import pytest
from unittest.mock import Mock, patch, MagicMock
import time
from datetime import datetime
import numpy as np
from pydub import AudioSegment
import sys
import os
import tempfile

# Add the parent directory to the path so we can import from the main project
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from audio.recording_manager import RecordingManager
from audio.audio import AudioHandler
from audio.audio_state_manager import AudioStateManager, RecordingState
from ui.status_manager import StatusManager


class TestRecordingManager:
    """Test recording manager functionality."""

    @pytest.fixture
    def mock_audio_handler(self):
        """Create mock audio handler."""
        handler = Mock(spec=AudioHandler)
        handler.sample_rate = 48000
        handler.sample_width = 2
        handler.channels = 1
        handler.transcribe_audio_file = Mock(return_value="Test transcript")
        return handler

    @pytest.fixture
    def mock_status_manager(self):
        """Create mock status manager."""
        return Mock(spec=StatusManager)

    @pytest.fixture
    def mock_audio_state_manager(self):
        """Create mock audio state manager."""
        manager = Mock(spec=AudioStateManager)
        manager.get_state.return_value = RecordingState.IDLE
        manager.is_recording.return_value = False
        manager.is_paused.return_value = False
        manager.has_audio.return_value = False
        manager.get_recording_metadata.return_value = {
            'recording_duration': 0,
            'pause_duration': 0,
            'start_time': None
        }
        manager.get_segment_stats.return_value = (0, 0, 0)  # pending, chunks, total
        manager.get_combined_audio.return_value = None
        return manager

    @pytest.fixture
    def recording_manager(self, mock_audio_handler, mock_status_manager, mock_audio_state_manager):
        """Create recording manager instance."""
        manager = RecordingManager(mock_audio_handler, mock_status_manager, mock_audio_state_manager)
        yield manager
        # Cleanup - no need to stop since we're using mocks

    @pytest.fixture
    def mock_audio_callback(self):
        """Create mock audio callback."""
        return Mock()

    def test_initialization(self, recording_manager, mock_audio_handler, mock_status_manager, mock_audio_state_manager):
        """Test recording manager initialization."""
        assert recording_manager.audio_handler is mock_audio_handler
        assert recording_manager.status_manager is mock_status_manager
        assert recording_manager.audio_state_manager is mock_audio_state_manager
        # Properties delegate to audio_state_manager
        assert recording_manager.is_recording is False
        assert recording_manager.is_paused is False

    def test_is_recording_property(self, recording_manager, mock_audio_state_manager):
        """Test is_recording property delegates to audio_state_manager."""
        mock_audio_state_manager.is_recording.return_value = True
        assert recording_manager.is_recording is True
        mock_audio_state_manager.is_recording.assert_called()

    def test_is_paused_property(self, recording_manager, mock_audio_state_manager):
        """Test is_paused property delegates to audio_state_manager."""
        mock_audio_state_manager.is_paused.return_value = True
        assert recording_manager.is_paused is True
        mock_audio_state_manager.is_paused.assert_called()

    def test_recording_duration_property(self, recording_manager, mock_audio_state_manager):
        """Test recording_duration property delegates to audio_state_manager."""
        mock_audio_state_manager.get_recording_metadata.return_value = {
            'recording_duration': 5.5,
            'pause_duration': 0,
            'start_time': datetime.now()
        }
        assert recording_manager.recording_duration == 5.5
        mock_audio_state_manager.get_recording_metadata.assert_called()

    def test_start_recording(self, recording_manager, mock_audio_state_manager, mock_audio_callback):
        """Test starting a recording."""
        mock_audio_state_manager.get_state.return_value = RecordingState.IDLE

        result = recording_manager.start_recording(mock_audio_callback)

        assert result is True
        mock_audio_state_manager.start_recording.assert_called_once()

    def test_start_recording_when_already_recording(self, recording_manager, mock_audio_state_manager, mock_audio_callback):
        """Test starting recording when already recording."""
        mock_audio_state_manager.get_state.return_value = RecordingState.RECORDING
        mock_audio_state_manager.start_recording.side_effect = RuntimeError("Already recording")

        result = recording_manager.start_recording(mock_audio_callback)

        assert result is False

    def test_stop_recording_when_not_recording(self, recording_manager, mock_audio_state_manager):
        """Test stopping when not recording."""
        mock_audio_state_manager.get_state.return_value = RecordingState.IDLE

        result = recording_manager.stop_recording()

        assert result is None

    def test_stop_recording(self, recording_manager, mock_audio_state_manager):
        """Test stopping a recording."""
        # Setup mock for active recording
        mock_audio_state_manager.get_state.return_value = RecordingState.RECORDING
        mock_audio_state_manager.get_recording_metadata.return_value = {
            'recording_duration': 10.5,
            'pause_duration': 1.0,
            'start_time': datetime.now()
        }
        mock_audio_state_manager.get_segment_stats.return_value = (0, 2, 5)  # pending, chunks, total
        mock_audio = AudioSegment.silent(duration=1000)
        mock_audio_state_manager.get_combined_audio.return_value = mock_audio

        result = recording_manager.stop_recording()

        assert result is not None
        assert 'duration' in result
        assert 'segment_count' in result
        assert 'audio' in result
        assert 'start_time' in result
        assert 'pause_duration' in result
        assert result['duration'] == 10.5
        assert result['segment_count'] == 5
        mock_audio_state_manager.stop_recording.assert_called_once()

    def test_pause_recording_success(self, recording_manager, mock_audio_state_manager):
        """Test pausing a recording successfully."""
        result = recording_manager.pause_recording()

        assert result is True
        mock_audio_state_manager.pause_recording.assert_called_once()

    def test_pause_recording_when_not_recording(self, recording_manager, mock_audio_state_manager):
        """Test pausing when not recording."""
        mock_audio_state_manager.pause_recording.side_effect = RuntimeError("Not recording")

        result = recording_manager.pause_recording()

        assert result is False

    def test_pause_when_already_paused(self, recording_manager, mock_audio_state_manager):
        """Test pausing when already paused."""
        mock_audio_state_manager.pause_recording.side_effect = RuntimeError("Already paused")

        result = recording_manager.pause_recording()

        assert result is False

    def test_resume_recording_success(self, recording_manager, mock_audio_state_manager):
        """Test resuming a paused recording."""
        result = recording_manager.resume_recording()

        assert result is True
        mock_audio_state_manager.resume_recording.assert_called_once()

    def test_resume_when_not_paused(self, recording_manager, mock_audio_state_manager):
        """Test resuming when not paused."""
        mock_audio_state_manager.resume_recording.side_effect = RuntimeError("Not paused")

        result = recording_manager.resume_recording()

        assert result is False

    def test_add_audio_segment(self, recording_manager, mock_audio_state_manager, mock_audio_handler):
        """Test adding audio segments during recording."""
        segment = np.ones(1000, dtype=np.int16)

        recording_manager.add_audio_segment(segment)

        mock_audio_state_manager.add_segment.assert_called_once()
        call_args = mock_audio_state_manager.add_segment.call_args
        np.testing.assert_array_equal(call_args[0][0], segment)
        assert call_args.kwargs['sample_rate'] == 48000

    def test_cancel_recording(self, recording_manager, mock_audio_state_manager):
        """Test cancelling recording."""
        recording_manager.cancel_recording()

        mock_audio_state_manager.clear_all.assert_called_once()

    def test_process_recording(self, recording_manager, mock_audio_handler):
        """Test processing a recording."""
        # Create a mock audio segment
        audio_segment = AudioSegment.silent(duration=1000)  # 1 second of silence

        # Set up callbacks
        text_callback = Mock()
        fallback_callback = Mock()
        recording_manager.on_text_recognized = text_callback
        recording_manager.on_transcription_fallback = fallback_callback

        # Mock the export method of AudioSegment to avoid actual file I/O
        with patch.object(audio_segment, 'export') as mock_export:
            # Process recording
            result = recording_manager.process_recording(audio_segment, "Test context")

            assert result['success'] is True
            assert result['transcript'] == "Test transcript"
            assert 'audio_data' in result

            # Verify audio handler was called
            mock_audio_handler.transcribe_audio_file.assert_called_once()

    def test_soap_recording_property(self, recording_manager, mock_audio_state_manager):
        """Test soap_recording legacy property."""
        mock_audio_state_manager.get_state.return_value = RecordingState.RECORDING
        assert recording_manager.soap_recording is True

        mock_audio_state_manager.get_state.return_value = RecordingState.IDLE
        assert recording_manager.soap_recording is False

    def test_soap_paused_property(self, recording_manager, mock_audio_state_manager):
        """Test soap_paused legacy property."""
        mock_audio_state_manager.is_paused.return_value = True
        assert recording_manager.soap_paused is True

        mock_audio_state_manager.is_paused.return_value = False
        assert recording_manager.soap_paused is False

    def test_callbacks_initialization(self, recording_manager):
        """Test that callbacks are properly initialized."""
        assert recording_manager.on_recording_complete is None
        assert recording_manager.on_text_recognized is None
        assert recording_manager.on_transcription_fallback is None
        assert recording_manager.on_device_disconnected is None

    def test_callbacks_can_be_set(self, recording_manager):
        """Test that callbacks can be set."""
        callback = Mock()
        recording_manager.on_recording_complete = callback
        recording_manager.on_text_recognized = callback
        recording_manager.on_transcription_fallback = callback
        recording_manager.on_device_disconnected = callback

        assert recording_manager.on_recording_complete is callback
        assert recording_manager.on_text_recognized is callback
        assert recording_manager.on_transcription_fallback is callback
        assert recording_manager.on_device_disconnected is callback
