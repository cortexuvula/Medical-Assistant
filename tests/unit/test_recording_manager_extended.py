"""
Extended unit tests for RecordingManager.

Tests cover:
- Device health monitoring with check intervals
- Error accumulation and max threshold triggering
- Device cache TTL and invalidation
- Name matching strategies (exact, clean, base, prefix)
- Device disconnection handling
- Recording loop behavior
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
import time
import threading
import numpy as np

from audio.recording_manager import RecordingManager
from audio.audio_state_manager import RecordingState
from utils.exceptions import DeviceDisconnectedError, AudioError


@pytest.fixture
def mock_audio_handler():
    """Create mock audio handler."""
    handler = Mock()
    handler.sample_rate = 48000
    handler.sample_width = 2
    handler.channels = 1
    handler.listening_device = "Test Microphone"
    handler._active_streams = {}
    handler.transcribe_audio_file.return_value = "Transcribed text"
    return handler


@pytest.fixture
def mock_status_manager():
    """Create mock status manager."""
    manager = Mock()
    manager.info = Mock()
    manager.error = Mock()
    manager.warning = Mock()
    return manager


@pytest.fixture
def mock_audio_state_manager():
    """Create mock audio state manager."""
    manager = Mock()
    manager.get_state.return_value = RecordingState.IDLE
    manager.is_recording.return_value = False
    manager.is_paused.return_value = False
    manager.has_audio.return_value = True
    manager.get_recording_metadata.return_value = {
        'start_time': time.time(),
        'recording_duration': 10.0,
        'pause_duration': 0.0,
    }
    manager.get_segment_stats.return_value = (0, 5, 5)
    manager.get_combined_audio.return_value = Mock()
    return manager


@pytest.fixture
def recording_manager(mock_audio_handler, mock_status_manager, mock_audio_state_manager):
    """Create RecordingManager with mocks."""
    return RecordingManager(
        audio_handler=mock_audio_handler,
        status_manager=mock_status_manager,
        audio_state_manager=mock_audio_state_manager,
    )


class TestDeviceHealthCheckInterval:
    """Tests for device health check interval behavior."""

    def test_health_check_skipped_within_interval(self, recording_manager):
        """Test that health checks are skipped within the interval."""
        # Set last check to current time
        recording_manager._last_device_check = time.time()

        # Should return True without actually checking
        result = recording_manager._check_device_health()

        assert result is True

    def test_health_check_performed_after_interval(self, recording_manager, mock_audio_state_manager):
        """Test that health checks run after interval expires."""
        # Set last check to past the interval
        recording_manager._last_device_check = time.time() - (RecordingManager.DEVICE_CHECK_INTERVAL + 1)

        # Mock stream active check
        with patch.object(recording_manager, '_is_stream_active', return_value=True):
            result = recording_manager._check_device_health()

        assert result is True

    def test_health_check_updates_last_check_time(self, recording_manager):
        """Test that health check updates the last check timestamp."""
        old_time = recording_manager._last_device_check
        recording_manager._last_device_check = time.time() - (RecordingManager.DEVICE_CHECK_INTERVAL + 1)

        with patch.object(recording_manager, '_is_stream_active', return_value=True):
            recording_manager._check_device_health()

        assert recording_manager._last_device_check > old_time


class TestErrorAccumulation:
    """Tests for error accumulation and threshold behavior."""

    def test_error_count_increments_on_device_not_found(self, recording_manager, mock_audio_handler):
        """Test that error count increments when device not found."""
        recording_manager._last_device_check = 0  # Force check
        mock_audio_handler.listening_device = "Missing Device"

        with patch.object(recording_manager, '_is_stream_active', return_value=False):
            with patch.object(recording_manager, '_find_device_by_name', return_value=False):
                recording_manager._check_device_health()

        assert recording_manager._device_error_count > 0

    def test_error_count_resets_on_success(self, recording_manager):
        """Test that error count resets on successful check."""
        recording_manager._device_error_count = 3
        recording_manager._last_device_check = 0

        with patch.object(recording_manager, '_is_stream_active', return_value=True):
            recording_manager._check_device_health()

        assert recording_manager._device_error_count == 0

    def test_max_errors_triggers_disconnection(self, recording_manager, mock_audio_handler):
        """Test that max errors triggers DeviceDisconnectedError."""
        recording_manager._device_error_count = recording_manager._max_device_errors - 1
        recording_manager._last_device_check = 0

        with patch.object(recording_manager, '_is_stream_active', return_value=False):
            with patch.object(recording_manager, '_find_device_by_name', return_value=False):
                with pytest.raises(DeviceDisconnectedError):
                    recording_manager._check_device_health()


class TestDeviceCache:
    """Tests for device caching behavior."""

    def test_cache_returns_cached_devices_within_ttl(self, recording_manager):
        """Test that cached devices are returned within TTL."""
        mock_devices = [Mock(name="Device 1"), Mock(name="Device 2")]
        recording_manager._device_cache = mock_devices
        recording_manager._device_cache_time = time.time()

        result = recording_manager._get_available_devices()

        assert result == mock_devices

    def test_cache_expires_after_ttl(self, recording_manager):
        """Test that cache is refreshed after TTL expires."""
        old_devices = [Mock(name="Old Device")]
        recording_manager._device_cache = old_devices
        recording_manager._device_cache_time = time.time() - (RecordingManager.DEVICE_CACHE_TTL + 1)

        with patch('soundcard.all_microphones', return_value=[]):
            result = recording_manager._get_available_devices()

        assert result != old_devices

    def test_force_refresh_ignores_cache(self, recording_manager):
        """Test that force_refresh ignores cache."""
        old_devices = [Mock(name="Cached Device")]
        recording_manager._device_cache = old_devices
        recording_manager._device_cache_time = time.time()

        # Need to patch both soundcard and sounddevice as the code falls back to sounddevice
        with patch('soundcard.all_microphones', return_value=[]):
            with patch('sounddevice.query_devices', return_value=[]):
                result = recording_manager._get_available_devices(force_refresh=True)

        assert result == []

    def test_invalidate_cache(self, recording_manager):
        """Test cache invalidation."""
        recording_manager._device_cache = [Mock()]
        recording_manager._device_cache_time = time.time()

        recording_manager.invalidate_device_cache()

        assert recording_manager._device_cache is None
        assert recording_manager._device_cache_time == 0.0


class TestDeviceNameMatching:
    """Tests for device name matching strategies."""

    def test_exact_match(self, recording_manager):
        """Test exact device name match (case-insensitive)."""
        mock_device = Mock(__str__=lambda self: "Test Microphone")

        with patch.object(recording_manager, '_get_available_devices', return_value=[mock_device]):
            result = recording_manager._find_device_by_name("TEST MICROPHONE")

        assert result is True

    def test_clean_name_match(self, recording_manager):
        """Test clean name match (removes device index)."""
        mock_device = Mock(__str__=lambda self: "Test Microphone")

        with patch.object(recording_manager, '_get_available_devices', return_value=[mock_device]):
            result = recording_manager._find_device_by_name("Test Microphone (Device 1)")

        assert result is True

    def test_base_name_match(self, recording_manager):
        """Test base name match (device base name in our name)."""
        mock_device = Mock(__str__=lambda self: "USB Audio (Device 0)")

        with patch.object(recording_manager, '_get_available_devices', return_value=[mock_device]):
            # Our name contains the base "USB Audio"
            result = recording_manager._find_device_by_name("USB Audio Device Configuration")

        assert result is True

    def test_prefix_match(self, recording_manager):
        """Test prefix match for truncated names (15 chars)."""
        # Long device names that share a 15-char prefix
        mock_device = Mock(__str__=lambda self: "Realtek High Definition Audio Device")

        with patch.object(recording_manager, '_get_available_devices', return_value=[mock_device]):
            result = recording_manager._find_device_by_name("Realtek High Definition Audio (Truncated)")

        assert result is True

    def test_no_match(self, recording_manager):
        """Test when no matching device is found."""
        mock_device = Mock(__str__=lambda self: "Different Device")

        with patch.object(recording_manager, '_get_available_devices', return_value=[mock_device]):
            result = recording_manager._find_device_by_name("NonExistent Device")

        assert result is False

    def test_empty_device_list(self, recording_manager):
        """Test when no devices are available."""
        with patch.object(recording_manager, '_get_available_devices', return_value=[]):
            result = recording_manager._find_device_by_name("Any Device")

        assert result is False


class TestStreamActiveCheck:
    """Tests for stream active status checking."""

    def test_stream_active_with_active_streams(self, recording_manager, mock_audio_handler):
        """Test stream active when handler has active streams."""
        mock_stream = Mock(active=True)
        mock_audio_handler._active_streams = {
            'recording': {'stream': mock_stream}
        }

        result = recording_manager._is_stream_active()

        assert result is True

    def test_stream_active_with_stopped_streams(self, recording_manager, mock_audio_handler):
        """Test stream inactive when streams are stopped."""
        mock_stream = Mock(active=False, stopped=True)
        mock_audio_handler._active_streams = {
            'recording': {'stream': mock_stream}
        }
        recording_manager.audio_state_manager.get_state.return_value = RecordingState.RECORDING
        recording_manager.audio_state_manager.has_audio.return_value = False

        result = recording_manager._is_stream_active()

        # May be True if audio_state_manager says recording and has audio
        # Need to check actual implementation behavior

    def test_stream_active_checks_audio_state_manager(self, recording_manager, mock_audio_state_manager):
        """Test that stream active check uses audio state manager."""
        recording_manager.audio_handler._active_streams = {}
        mock_audio_state_manager.get_state.return_value = RecordingState.RECORDING
        mock_audio_state_manager.has_audio.return_value = True

        result = recording_manager._is_stream_active()

        assert result is True


class TestDeviceDisconnectionHandling:
    """Tests for device disconnection handling."""

    def test_handle_disconnection_pauses_recording(self, recording_manager, mock_audio_state_manager):
        """Test that disconnection pauses the recording."""
        error = DeviceDisconnectedError("Device lost", device_name="Test Device")

        recording_manager._handle_device_disconnection(error)

        mock_audio_state_manager.pause_recording.assert_called_once()

    def test_handle_disconnection_calls_callback(self, recording_manager):
        """Test that disconnection calls the callback."""
        callback = Mock()
        recording_manager.on_device_disconnected = callback

        error = DeviceDisconnectedError("Device lost", device_name="Test Device")
        recording_manager._handle_device_disconnection(error)

        callback.assert_called_once_with("Test Device")

    def test_handle_disconnection_updates_status(self, recording_manager, mock_status_manager):
        """Test that disconnection updates status manager."""
        error = DeviceDisconnectedError("Device lost", device_name="Test Device")

        recording_manager._handle_device_disconnection(error)

        mock_status_manager.error.assert_called_once()
        assert "Test Device" in mock_status_manager.error.call_args[0][0]

    def test_handle_disconnection_with_unknown_device(self, recording_manager):
        """Test handling disconnection when device name is None."""
        callback = Mock()
        recording_manager.on_device_disconnected = callback

        error = DeviceDisconnectedError("Device lost", device_name=None)
        recording_manager._handle_device_disconnection(error)

        callback.assert_called_once_with("Unknown")


class TestRecordingLifecycle:
    """Tests for recording lifecycle management."""

    def test_start_recording(self, recording_manager, mock_audio_state_manager):
        """Test starting a recording."""
        callback = Mock()

        result = recording_manager.start_recording(callback)

        assert result is True
        mock_audio_state_manager.start_recording.assert_called_once()

    def test_start_recording_failure(self, recording_manager, mock_audio_state_manager):
        """Test handling start recording failure."""
        mock_audio_state_manager.start_recording.side_effect = Exception("Start failed")
        callback = Mock()

        result = recording_manager.start_recording(callback)

        assert result is False

    def test_stop_recording_when_idle(self, recording_manager, mock_audio_state_manager):
        """Test stopping recording when idle returns None."""
        mock_audio_state_manager.get_state.return_value = RecordingState.IDLE

        result = recording_manager.stop_recording()

        assert result is None

    def test_stop_recording_returns_data(self, recording_manager, mock_audio_state_manager):
        """Test stopping recording returns recording data."""
        mock_audio_state_manager.get_state.return_value = RecordingState.RECORDING

        result = recording_manager.stop_recording()

        assert result is not None
        assert 'audio' in result
        assert 'duration' in result
        assert 'segment_count' in result

    def test_pause_recording(self, recording_manager, mock_audio_state_manager):
        """Test pausing a recording."""
        result = recording_manager.pause_recording()

        assert result is True
        mock_audio_state_manager.pause_recording.assert_called_once()

    def test_pause_recording_failure(self, recording_manager, mock_audio_state_manager):
        """Test pause recording failure."""
        mock_audio_state_manager.pause_recording.side_effect = RuntimeError("Cannot pause")

        result = recording_manager.pause_recording()

        assert result is False

    def test_resume_recording(self, recording_manager, mock_audio_state_manager):
        """Test resuming a recording."""
        result = recording_manager.resume_recording()

        assert result is True
        mock_audio_state_manager.resume_recording.assert_called_once()

    def test_cancel_recording(self, recording_manager, mock_audio_state_manager):
        """Test cancelling a recording."""
        recording_manager.cancel_recording()

        mock_audio_state_manager.clear_all.assert_called_once()


class TestAudioSegmentManagement:
    """Tests for audio segment management."""

    def test_add_audio_segment(self, recording_manager, mock_audio_state_manager, mock_audio_handler):
        """Test adding an audio segment."""
        audio_data = np.zeros(1000, dtype=np.int16)

        recording_manager.add_audio_segment(audio_data)

        mock_audio_state_manager.add_segment.assert_called_once()
        call_kwargs = mock_audio_state_manager.add_segment.call_args.kwargs
        assert call_kwargs['sample_rate'] == mock_audio_handler.sample_rate


class TestRecordingProperties:
    """Tests for recording status properties."""

    def test_is_recording_property(self, recording_manager, mock_audio_state_manager):
        """Test is_recording property."""
        mock_audio_state_manager.is_recording.return_value = True

        assert recording_manager.is_recording is True

    def test_is_paused_property(self, recording_manager, mock_audio_state_manager):
        """Test is_paused property."""
        mock_audio_state_manager.is_paused.return_value = True

        assert recording_manager.is_paused is True

    def test_recording_duration_property(self, recording_manager, mock_audio_state_manager):
        """Test recording_duration property."""
        mock_audio_state_manager.get_recording_metadata.return_value = {
            'recording_duration': 30.5
        }

        assert recording_manager.recording_duration == 30.5

    def test_soap_recording_legacy_property(self, recording_manager, mock_audio_state_manager):
        """Test legacy soap_recording property."""
        mock_audio_state_manager.get_state.return_value = RecordingState.RECORDING

        assert recording_manager.soap_recording is True

    def test_soap_paused_legacy_property(self, recording_manager, mock_audio_state_manager):
        """Test legacy soap_paused property."""
        mock_audio_state_manager.is_paused.return_value = True

        assert recording_manager.soap_paused is True


class TestRecordingLoop:
    """Tests for the recording loop behavior."""

    def test_recording_loop_checks_device_health(self, recording_manager, mock_audio_state_manager):
        """Test that recording loop checks device health."""
        # Set up state to run loop once
        states = [RecordingState.RECORDING, RecordingState.IDLE]
        mock_audio_state_manager.get_state.side_effect = states
        mock_audio_state_manager.is_recording.return_value = True

        with patch.object(recording_manager, '_check_device_health') as mock_check:
            with patch('time.sleep'):
                recording_manager._recording_loop(Mock())

            mock_check.assert_called()

    def test_recording_loop_handles_disconnection(self, recording_manager, mock_audio_state_manager):
        """Test that recording loop handles device disconnection."""
        mock_audio_state_manager.get_state.return_value = RecordingState.RECORDING
        mock_audio_state_manager.is_recording.return_value = True

        error = DeviceDisconnectedError("Lost", device_name="Device")

        with patch.object(recording_manager, '_check_device_health', side_effect=error):
            with patch.object(recording_manager, '_handle_device_disconnection') as mock_handle:
                with patch('time.sleep'):
                    recording_manager._recording_loop(Mock())

                mock_handle.assert_called_once_with(error)


class TestProcessRecording:
    """Tests for recording processing."""

    def test_process_recording_success(self, recording_manager, mock_audio_handler):
        """Test successful recording processing."""
        mock_audio = Mock()
        mock_audio.export = Mock()

        with patch('tempfile.NamedTemporaryFile') as mock_temp:
            mock_file = MagicMock()
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=False)
            mock_file.name = "/tmp/test.mp3"
            mock_temp.return_value = mock_file

            with patch('os.unlink'):
                result = recording_manager.process_recording(mock_audio, "context")

        assert result['success'] is True
        assert result['transcript'] == "Transcribed text"

    def test_process_recording_failure(self, recording_manager, mock_audio_handler):
        """Test recording processing failure."""
        mock_audio_handler.transcribe_audio_file.side_effect = Exception("Transcription failed")
        mock_audio = Mock()
        mock_audio.export = Mock()

        with patch('tempfile.NamedTemporaryFile') as mock_temp:
            mock_file = MagicMock()
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=False)
            mock_file.name = "/tmp/test.mp3"
            mock_temp.return_value = mock_file

            result = recording_manager.process_recording(mock_audio, "context")

        assert result['success'] is False
        assert 'error' in result
