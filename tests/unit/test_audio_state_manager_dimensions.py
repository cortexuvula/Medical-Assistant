"""
Test AudioStateManager with different audio dimensions.

Tests handling of 1D vs 2D arrays (mono vs stereo audio).
"""

import unittest
import numpy as np
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))

from audio.audio_state_manager import AudioStateManager, RecordingState


class TestAudioStateManagerDimensions(unittest.TestCase):
    """Test cases for handling different audio dimensions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.manager = AudioStateManager(combine_threshold=3)
        
    def test_mixed_dimensions(self):
        """Test combining segments with mixed 1D and 2D arrays."""
        self.manager.start_recording()
        
        # Add 1D array (mono)
        mono_data = np.random.randint(-32768, 32767, size=1000, dtype=np.int16)
        self.manager.add_segment(mono_data)
        
        # Add 2D array (stereo)
        stereo_data = np.random.randint(-32768, 32767, size=(1000, 2), dtype=np.int16)
        self.manager.add_segment(stereo_data)
        
        # Add another 1D array
        mono_data2 = np.random.randint(-32768, 32767, size=1000, dtype=np.int16)
        self.manager.add_segment(mono_data2)
        
        # This should trigger combination without error
        self.assertTrue(self.manager.has_audio())
        
        # Get combined audio
        self.manager.stop_recording()
        combined = self.manager.get_combined_audio()
        self.assertIsNotNone(combined)
        
    def test_stereo_to_mono_conversion(self):
        """Test that stereo audio is properly converted to mono."""
        self.manager.start_recording()
        
        # Add only stereo segments
        for i in range(3):
            stereo_data = np.random.randint(-32768, 32767, size=(500, 2), dtype=np.int16)
            self.manager.add_segment(stereo_data)
        
        self.manager.stop_recording()
        combined = self.manager.get_combined_audio()
        self.assertIsNotNone(combined)
        self.assertEqual(combined.channels, 1)  # Should be mono
        
    def test_single_channel_2d_array(self):
        """Test handling of 2D arrays with single channel."""
        self.manager.start_recording()
        
        # Add 2D array with shape (samples, 1)
        single_channel_2d = np.random.randint(-32768, 32767, size=(1000, 1), dtype=np.int16)
        self.manager.add_segment(single_channel_2d)
        
        # Add normal 1D array
        mono_data = np.random.randint(-32768, 32767, size=1000, dtype=np.int16)
        self.manager.add_segment(mono_data)
        
        # Add another single channel 2D
        single_channel_2d2 = np.random.randint(-32768, 32767, size=(1000, 1), dtype=np.int16)
        self.manager.add_segment(single_channel_2d2)
        
        self.manager.stop_recording()
        combined = self.manager.get_combined_audio()
        self.assertIsNotNone(combined)
        
    def test_high_dimensional_arrays(self):
        """Test handling of arrays with more than 2 dimensions."""
        self.manager.start_recording()
        
        # Add 3D array (should be flattened)
        weird_data = np.random.randint(-32768, 32767, size=(100, 5, 2), dtype=np.int16)
        self.manager.add_segment(weird_data)
        
        # Add normal data
        normal_data = np.random.randint(-32768, 32767, size=1000, dtype=np.int16)
        self.manager.add_segment(normal_data)
        
        # This should not crash
        self.manager.stop_recording()
        combined = self.manager.get_combined_audio()
        self.assertIsNotNone(combined)


if __name__ == '__main__':
    unittest.main()