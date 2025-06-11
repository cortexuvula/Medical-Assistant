"""
Unit tests for AudioStateManager class.

Tests thread safety, state management, audio combination, and memory cleanup.
"""

import unittest
import threading
import time
import numpy as np
from pydub import AudioSegment
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))

from audio.audio_state_manager import AudioStateManager, RecordingState


class TestAudioStateManager(unittest.TestCase):
    """Test cases for AudioStateManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.manager = AudioStateManager(combine_threshold=3)
        
    def tearDown(self):
        """Clean up after tests."""
        self.manager.clear_all()
        
    def test_initial_state(self):
        """Test initial state of AudioStateManager."""
        self.assertEqual(self.manager.get_state(), RecordingState.IDLE)
        self.assertFalse(self.manager.is_recording())
        self.assertFalse(self.manager.is_paused())
        self.assertFalse(self.manager.has_audio())
        
    def test_start_recording(self):
        """Test starting a recording."""
        self.manager.start_recording()
        self.assertEqual(self.manager.get_state(), RecordingState.RECORDING)
        self.assertTrue(self.manager.is_recording())
        self.assertFalse(self.manager.is_paused())
        
    def test_pause_resume_recording(self):
        """Test pausing and resuming a recording."""
        self.manager.start_recording()
        
        # Pause
        self.manager.pause_recording()
        self.assertEqual(self.manager.get_state(), RecordingState.PAUSED)
        self.assertFalse(self.manager.is_recording())
        self.assertTrue(self.manager.is_paused())
        
        # Resume
        self.manager.resume_recording()
        self.assertEqual(self.manager.get_state(), RecordingState.RECORDING)
        self.assertTrue(self.manager.is_recording())
        self.assertFalse(self.manager.is_paused())
        
    def test_stop_recording(self):
        """Test stopping a recording."""
        self.manager.start_recording()
        self.manager.stop_recording()
        self.assertEqual(self.manager.get_state(), RecordingState.PROCESSING)
        
    def test_add_segment(self):
        """Test adding audio segments."""
        self.manager.start_recording()
        
        # Create test audio data
        audio_data = np.random.randint(-32768, 32767, size=1000, dtype=np.int16)
        
        # Add segment
        self.manager.add_segment(audio_data)
        self.assertTrue(self.manager.has_audio())
        
        # Check segment stats
        pending, chunks, total = self.manager.get_segment_stats()
        self.assertEqual(pending, 1)
        self.assertEqual(chunks, 0)
        self.assertEqual(total, 1)
        
    def test_segment_combination(self):
        """Test automatic segment combination at threshold."""
        self.manager.start_recording()
        
        # Add segments up to threshold
        for i in range(3):  # threshold is 3
            audio_data = np.random.randint(-32768, 32767, size=1000, dtype=np.int16)
            self.manager.add_segment(audio_data)
        
        # Check that segments were combined
        pending, chunks, total = self.manager.get_segment_stats()
        self.assertEqual(pending, 0)  # All segments should be combined
        self.assertEqual(chunks, 1)   # Into one chunk
        self.assertEqual(total, 3)    # Total of 3 segments
        
    def test_get_combined_audio(self):
        """Test getting combined audio."""
        self.manager.start_recording()
        
        # Add multiple segments
        for i in range(5):
            audio_data = np.random.randint(-32768, 32767, size=1000, dtype=np.int16)
            self.manager.add_segment(audio_data)
        
        self.manager.stop_recording()
        
        # Get combined audio
        combined = self.manager.get_combined_audio()
        self.assertIsNotNone(combined)
        self.assertIsInstance(combined, AudioSegment)
        
        # Should be approximately 5000 samples at 16kHz = ~312ms
        self.assertGreater(len(combined), 300)
        
    def test_clear_all(self):
        """Test clearing all audio data."""
        self.manager.start_recording()
        
        # Add some segments
        for i in range(3):
            audio_data = np.random.randint(-32768, 32767, size=1000, dtype=np.int16)
            self.manager.add_segment(audio_data)
        
        # Clear all
        self.manager.clear_all()
        
        # Check state is reset
        self.assertEqual(self.manager.get_state(), RecordingState.IDLE)
        self.assertFalse(self.manager.has_audio())
        self.assertIsNone(self.manager.get_combined_audio())
        
    def test_recording_metadata(self):
        """Test recording metadata tracking."""
        self.manager.start_recording()
        time.sleep(0.1)  # Let some time pass
        
        metadata = self.manager.get_recording_metadata()
        
        self.assertEqual(metadata['state'], 'recording')
        self.assertIsNotNone(metadata['start_time'])
        self.assertGreater(metadata['total_duration'], 0)
        self.assertEqual(metadata['pause_duration'], 0)
        
    def test_pause_duration_tracking(self):
        """Test pause duration calculation."""
        self.manager.start_recording()
        time.sleep(0.1)
        
        self.manager.pause_recording()
        time.sleep(0.1)
        
        self.manager.resume_recording()
        
        metadata = self.manager.get_recording_metadata()
        self.assertGreater(metadata['pause_duration'], 0)
        self.assertLess(metadata['recording_duration'], metadata['total_duration'])
        
    def test_thread_safety(self):
        """Test thread-safe operations."""
        self.manager.start_recording()
        
        errors = []
        
        def add_segments():
            """Add segments from multiple threads."""
            try:
                for i in range(10):
                    audio_data = np.random.randint(-32768, 32767, size=100, dtype=np.int16)
                    self.manager.add_segment(audio_data)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=add_segments)
            t.start()
            threads.append(t)
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # Check no errors occurred
        self.assertEqual(len(errors), 0)
        
        # Check segments were added
        self.assertTrue(self.manager.has_audio())
        
    def test_invalid_state_transitions(self):
        """Test invalid state transitions raise errors."""
        # Can't pause when not recording
        with self.assertRaises(RuntimeError):
            self.manager.pause_recording()
        
        # Can't resume when not paused
        with self.assertRaises(RuntimeError):
            self.manager.resume_recording()
        
        # Can't stop when not recording
        with self.assertRaises(RuntimeError):
            self.manager.stop_recording()
        
        # Can't start when already recording
        self.manager.start_recording()
        with self.assertRaises(RuntimeError):
            self.manager.start_recording()
            
    def test_segment_ignored_when_not_recording(self):
        """Test segments are ignored when not recording."""
        # Add segment when idle
        audio_data = np.random.randint(-32768, 32767, size=1000, dtype=np.int16)
        self.manager.add_segment(audio_data)
        
        # Should have no audio
        self.assertFalse(self.manager.has_audio())
        
        # Start recording and pause
        self.manager.start_recording()
        self.manager.pause_recording()
        
        # Add segment when paused
        self.manager.add_segment(audio_data)
        
        # Should still have no audio
        self.assertFalse(self.manager.has_audio())
        
    def test_float_to_int16_conversion(self):
        """Test float audio data conversion to int16."""
        self.manager.start_recording()
        
        # Create float audio data
        float_data = np.random.uniform(-1.0, 1.0, size=1000).astype(np.float32)
        
        # Add segment
        self.manager.add_segment(float_data)
        
        # Get combined audio and verify it's valid
        self.manager.stop_recording()
        combined = self.manager.get_combined_audio()
        self.assertIsNotNone(combined)
        
    def test_empty_recording(self):
        """Test handling of empty recording."""
        self.manager.start_recording()
        self.manager.stop_recording()
        
        # Should return None for empty recording
        combined = self.manager.get_combined_audio()
        self.assertIsNone(combined)


if __name__ == '__main__':
    unittest.main()