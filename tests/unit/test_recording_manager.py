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

from recording_manager import RecordingManager
from audio import AudioHandler
from status_manager import StatusManager


class TestRecordingManager:
    """Test recording manager functionality."""
    
    @pytest.fixture
    def mock_audio_handler(self):
        """Create mock audio handler."""
        handler = Mock(spec=AudioHandler)
        handler.sample_rate = 48000
        handler.transcribe_audio_file = Mock(return_value="Test transcript")
        return handler
    
    @pytest.fixture
    def mock_status_manager(self):
        """Create mock status manager."""
        return Mock(spec=StatusManager)
    
    @pytest.fixture
    def recording_manager(self, mock_audio_handler, mock_status_manager):
        """Create recording manager instance."""
        manager = RecordingManager(mock_audio_handler, mock_status_manager)
        yield manager
        # Cleanup
        if manager.is_recording:
            manager.stop_recording()
    
    @pytest.fixture
    def mock_audio_callback(self):
        """Create mock audio callback."""
        return Mock()
    
    def test_initialization(self, recording_manager):
        """Test recording manager initialization."""
        assert recording_manager.is_recording is False
        assert recording_manager.is_paused is False
        assert recording_manager.soap_start_time is None
        assert recording_manager.audio_segments == []
        assert recording_manager.total_pause_duration == 0
    
    def test_start_recording(self, recording_manager, mock_audio_callback):
        """Test starting a recording."""
        result = recording_manager.start_recording(mock_audio_callback)
        
        assert result is True
        assert recording_manager.is_recording is True
        assert recording_manager.is_paused is False
        assert recording_manager.soap_start_time is not None
        assert recording_manager.audio_segments == []
        # Note: callback is not stored as an attribute in the actual implementation
    
    def test_start_recording_when_already_recording(self, recording_manager, mock_audio_callback):
        """Test starting recording when already recording."""
        # Start first recording
        recording_manager.start_recording(mock_audio_callback)
        
        # Try to start again
        result = recording_manager.start_recording(mock_audio_callback)
        
        assert result is False
    
    def test_stop_recording(self, recording_manager, mock_audio_callback):
        """Test stopping a recording."""
        # Start recording first
        recording_manager.start_recording(mock_audio_callback)
        
        # Add some mock audio segments
        recording_manager.audio_segments = [
            np.ones(1000, dtype=np.int16),
            np.ones(2000, dtype=np.int16)
        ]
        
        # Stop recording
        result = recording_manager.stop_recording()
        
        assert result is not None
        assert recording_manager.is_recording is False
        assert recording_manager.is_paused is False
        assert 'duration' in result
        assert 'segment_count' in result
        assert 'audio' in result
        assert 'start_time' in result
        assert result['segment_count'] == 2
    
    def test_stop_recording_when_not_recording(self, recording_manager):
        """Test stopping when not recording."""
        result = recording_manager.stop_recording()
        assert result is None
    
    def test_pause_recording(self, recording_manager, mock_audio_callback):
        """Test pausing a recording."""
        # Start recording
        recording_manager.start_recording(mock_audio_callback)
        time.sleep(0.1)  # Let some time pass
        
        # Pause
        result = recording_manager.pause_recording()
        
        assert result is True
        assert recording_manager.is_recording is True
        assert recording_manager.is_paused is True
        assert recording_manager.soap_pause_start_time is not None
    
    def test_pause_when_not_recording(self, recording_manager):
        """Test pausing when not recording."""
        result = recording_manager.pause_recording()
        assert result is False
    
    def test_pause_when_already_paused(self, recording_manager, mock_audio_callback):
        """Test pausing when already paused."""
        recording_manager.start_recording(mock_audio_callback)
        recording_manager.pause_recording()
        
        # Try to pause again
        result = recording_manager.pause_recording()
        assert result is False
    
    def test_resume_recording(self, recording_manager, mock_audio_callback):
        """Test resuming a paused recording."""
        # Start and pause recording
        recording_manager.start_recording(mock_audio_callback)
        recording_manager.pause_recording()
        pause_start = recording_manager.soap_pause_start_time
        
        # Wait a bit
        time.sleep(0.1)
        
        # Resume
        result = recording_manager.resume_recording()
        
        assert result is True
        assert recording_manager.is_recording is True
        assert recording_manager.is_paused is False
        assert recording_manager.soap_pause_start_time is None
        assert recording_manager.total_pause_duration > 0
    
    def test_resume_when_not_paused(self, recording_manager, mock_audio_callback):
        """Test resuming when not paused."""
        recording_manager.start_recording(mock_audio_callback)
        
        result = recording_manager.resume_recording()
        assert result is False
    
    def test_get_recording_duration(self, recording_manager, mock_audio_callback):
        """Test getting recording duration."""
        # Not recording
        assert recording_manager.recording_duration == 0
        
        # Start recording
        recording_manager.start_recording(mock_audio_callback)
        start_time = time.time()
        
        # Wait a bit
        time.sleep(0.2)
        
        # Check duration
        duration = recording_manager.recording_duration
        assert duration > 0
        assert duration < 1.0  # Should be less than 1 second
        
        # During pause, the duration continues to increase because
        # total_pause_duration is only updated on resume
        recording_manager.pause_recording()
        paused_duration = recording_manager.recording_duration
        time.sleep(0.1)
        
        # Resume to update the pause duration
        recording_manager.resume_recording()
        resumed_duration = recording_manager.recording_duration
        
        # The resumed duration should be close to the paused duration
        # because the pause time is now accounted for
        assert abs(resumed_duration - paused_duration) < 0.02  # Allow small tolerance
    
    def test_add_audio_segment(self, recording_manager, mock_audio_callback):
        """Test adding audio segments during recording."""
        recording_manager.start_recording(mock_audio_callback)
        
        # Add segments
        segment1 = np.ones(1000, dtype=np.int16)
        segment2 = np.ones(2000, dtype=np.int16)
        
        recording_manager.add_audio_segment(segment1)
        recording_manager.add_audio_segment(segment2)
        
        assert len(recording_manager.audio_segments) == 2
        assert len(recording_manager.audio_segments[0]) == 1000
        assert len(recording_manager.audio_segments[1]) == 2000
    
    def test_add_audio_segment_when_paused(self, recording_manager, mock_audio_callback):
        """Test that audio isn't added when paused."""
        recording_manager.start_recording(mock_audio_callback)
        recording_manager.pause_recording()
        
        # Try to add segment while paused
        segment = np.ones(1000, dtype=np.int16)
        recording_manager.add_audio_segment(segment)
        
        # Segment should not be added
        assert len(recording_manager.audio_segments) == 0
    
    def test_cancel_recording(self, recording_manager, mock_audio_callback):
        """Test cancelling recording."""
        # Set up some data
        recording_manager.start_recording(mock_audio_callback)
        recording_manager.audio_segments = [np.ones(1000)]
        recording_manager.total_pause_duration = 10
        
        # Cancel
        recording_manager.cancel_recording()
        
        assert recording_manager.audio_segments == []
        assert recording_manager.total_pause_duration == 0
        assert recording_manager.is_recording is False
        assert recording_manager.is_paused is False
    
    def test_combine_audio_segments(self, recording_manager):
        """Test combining audio segments."""
        # No segments
        assert recording_manager._combine_audio_segments() is None
        
        # Add numpy array segments
        recording_manager.audio_segments = [
            np.ones(1000, dtype=np.int16),
            np.ones(2000, dtype=np.int16) * 2
        ]
        
        audio_data = recording_manager._combine_audio_segments()
        assert audio_data is not None
        assert isinstance(audio_data, AudioSegment)
        assert len(audio_data) > 0  # AudioSegment length is in milliseconds
    
    def test_combine_audio_segments_float32(self, recording_manager):
        """Test combining audio segments with float32 data."""
        # Add float32 numpy array segments
        recording_manager.audio_segments = [
            np.ones(1000, dtype=np.float32) * 0.5,
            np.ones(2000, dtype=np.float32) * 0.25
        ]
        
        audio_data = recording_manager._combine_audio_segments()
        assert audio_data is not None
        assert isinstance(audio_data, AudioSegment)
        assert len(audio_data) > 0
    
    def test_combine_audio_segments_mixed(self, recording_manager):
        """Test combining mixed audio segment types."""
        # Mix AudioSegment and numpy arrays
        recording_manager.audio_segments = [
            AudioSegment.silent(duration=500),  # 500ms AudioSegment
            np.ones(1000, dtype=np.int16),  # numpy array
            AudioSegment.silent(duration=300)  # another AudioSegment
        ]
        
        audio_data = recording_manager._combine_audio_segments()
        assert audio_data is not None
        assert isinstance(audio_data, AudioSegment)
    
    def test_multiple_pause_resume_cycles(self, recording_manager, mock_audio_callback):
        """Test multiple pause/resume cycles."""
        recording_manager.start_recording(mock_audio_callback)
        
        total_pause_time = 0
        
        # Multiple pause/resume cycles
        for i in range(3):
            recording_manager.pause_recording()
            time.sleep(0.05)
            recording_manager.resume_recording()
            total_pause_time += 0.05
        
        # Total pause duration should accumulate
        assert recording_manager.total_pause_duration >= total_pause_time * 0.8  # Allow some tolerance
    
    def test_process_recording(self, recording_manager):
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
            
            # Verify audio handler was called with the temp file path
            recording_manager.audio_handler.transcribe_audio_file.assert_called_once()
            call_args = recording_manager.audio_handler.transcribe_audio_file.call_args
            temp_path = call_args[0][0]
            assert temp_path.endswith('.mp3')
            
            # Verify export was called
            mock_export.assert_called_once()
    
    def test_recording_state_consistency(self, recording_manager, mock_audio_callback):
        """Test that recording state remains consistent."""
        # Initial state
        assert not recording_manager.is_recording
        assert not recording_manager.is_paused
        
        # Start recording
        recording_manager.start_recording(mock_audio_callback)
        assert recording_manager.is_recording
        assert not recording_manager.is_paused
        
        # Pause
        recording_manager.pause_recording()
        assert recording_manager.is_recording
        assert recording_manager.is_paused
        
        # Resume
        recording_manager.resume_recording()
        assert recording_manager.is_recording
        assert not recording_manager.is_paused
        
        # Stop
        recording_manager.stop_recording()
        assert not recording_manager.is_recording
        assert not recording_manager.is_paused
    
    def test_concurrent_operations_protection(self, recording_manager, mock_audio_callback):
        """Test protection against concurrent operations."""
        recording_manager.start_recording(mock_audio_callback)
        
        # These should all be protected
        assert not recording_manager.start_recording(mock_audio_callback)  # Can't start twice
        
        recording_manager.pause_recording()
        assert not recording_manager.pause_recording()  # Can't pause twice
        
        recording_manager.resume_recording()
        assert not recording_manager.resume_recording()  # Can't resume when not paused
    
    def test_properties(self, recording_manager, mock_audio_callback):
        """Test recording manager properties."""
        # Initial state
        assert recording_manager.is_recording is False
        assert recording_manager.is_paused is False
        assert recording_manager.recording_duration == 0
        
        # Start recording
        recording_manager.start_recording(mock_audio_callback)
        assert recording_manager.is_recording is True
        assert recording_manager.is_paused is False
        
        # Pause recording
        recording_manager.pause_recording()
        assert recording_manager.is_recording is True
        assert recording_manager.is_paused is True
        
        # Stop recording
        recording_manager.stop_recording()
        assert recording_manager.is_recording is False
        assert recording_manager.is_paused is False
    
    def test_recording_metadata(self, recording_manager, mock_audio_callback):
        """Test recording metadata generation."""
        recording_manager.start_recording(mock_audio_callback)
        
        # Add some segments
        for i in range(5):
            recording_manager.add_audio_segment(np.ones(1000 * (i + 1)))
        
        # Add pause time
        recording_manager.pause_recording()
        time.sleep(0.1)
        recording_manager.resume_recording()
        
        # Stop and get metadata
        result = recording_manager.stop_recording()
        
        assert 'start_time' in result
        assert 'duration' in result
        assert 'segment_count' in result
        assert 'audio' in result
        assert result['segment_count'] == 5
        # Duration should account for pause time
        assert result['duration'] >= 0