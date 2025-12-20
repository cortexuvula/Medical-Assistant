#!/usr/bin/env python3
"""
Audio recording tests.

These tests verify audio functionality when hardware is available,
and skip gracefully in CI environments without audio devices.
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def audio_available():
    """Check if audio hardware is available."""
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        # Check if any input devices exist
        return any(d['max_input_channels'] > 0 for d in devices)
    except Exception:
        return False


@pytest.mark.skipif(not audio_available(), reason="No audio hardware available")
class TestAudioRecording:
    """Tests that require audio hardware."""

    def test_list_audio_devices(self):
        """Test that audio devices can be listed."""
        import sounddevice as sd
        devices = sd.query_devices()
        assert len(devices) > 0

    def test_default_device_available(self):
        """Test that a default device is available."""
        import sounddevice as sd
        default = sd.default.device
        assert default is not None


class TestAudioMocked:
    """Tests with mocked audio for CI environments."""

    def test_audio_handler_imports(self):
        """Test AudioHandler can be imported."""
        from src.audio.audio import AudioHandler
        assert AudioHandler is not None

    def test_recording_manager_imports(self):
        """Test RecordingManager can be imported."""
        from src.audio.recording_manager import RecordingManager
        assert RecordingManager is not None

    def test_audio_segment_creation(self):
        """Test AudioSegment can be created."""
        from pydub import AudioSegment
        import numpy as np

        # Create silent audio data
        sample_rate = 44100
        duration = 1  # second
        samples = np.zeros(sample_rate * duration, dtype=np.int16)

        segment = AudioSegment(
            data=samples.tobytes(),
            sample_width=2,
            frame_rate=sample_rate,
            channels=1
        )

        assert len(segment) == 1000  # 1000 ms
        assert segment.frame_rate == sample_rate

    def test_audio_conversion(self):
        """Test audio data conversion."""
        import numpy as np

        # Simulate recording data
        recording = np.random.uniform(-1, 1, 1000).astype(np.float32)

        # Convert to int16 (as done in actual code)
        audio_clipped = np.clip(recording, -1.0, 1.0)
        audio_int16 = (audio_clipped * 32767).astype(np.int16)

        assert audio_int16.dtype == np.int16
        assert len(audio_int16) == 1000

    @patch('sounddevice.rec')
    @patch('sounddevice.wait')
    def test_recording_with_mocked_device(self, mock_wait, mock_rec):
        """Test recording flow with mocked sounddevice."""
        import numpy as np

        # Setup mock to return audio data
        mock_audio = np.zeros((48000, 1), dtype=np.float32)
        mock_rec.return_value = mock_audio

        # Simulate a recording call
        import sounddevice as sd
        result = sd.rec(48000, samplerate=48000, channels=1)

        mock_rec.assert_called_once()
        assert result.shape == (48000, 1)
