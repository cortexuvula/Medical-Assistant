"""Extended test suite for audio.py to increase test coverage."""
import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock, call
import tempfile
from pathlib import Path
import os
import threading
import time
from pydub import AudioSegment

# Try to import audio.audio libraries - they may fail in CI environments
try:
    import sounddevice as sd
except (ImportError, OSError):
    sd = None

try:
    import soundcard
except (ImportError, AssertionError, OSError):
    soundcard = None

from audio.audio import AudioHandler, AudioData
from settings.settings import SETTINGS


class TestAudioDataClass:
    """Test the AudioData class."""
    
    def test_audio_data_initialization(self):
        """Test AudioData class initialization."""
        frame_data = b"test_data"
        sample_rate = 44100
        sample_width = 2
        channels = 1
        
        audio_data = AudioData(frame_data, sample_rate, sample_width, channels)
        
        assert audio_data.frame_data == frame_data
        assert audio_data.sample_rate == sample_rate
        assert audio_data.sample_width == sample_width
        assert audio_data.channels == channels
        
    def test_audio_data_get_raw_data(self):
        """Test AudioData.get_raw_data() method."""
        frame_data = b"raw_audio_data"
        audio_data = AudioData(frame_data, 44100, 2)
        
        assert audio_data.get_raw_data() == frame_data


class TestAudioHandlerErrorHandling:
    """Test error handling paths in AudioHandler."""
    
    @pytest.fixture
    def audio_handler(self):
        """Create a basic audio handler for testing."""
        return AudioHandler(
            deepgram_api_key="test_key",
            elevenlabs_api_key="test_key",
            groq_api_key="test_key"
        )
    
    def test_combine_audio_segments_error_handling(self, audio_handler):
        """Test error handling in combine_audio_segments (lines 131-138)."""
        # Create mock segments that will cause an error
        mock_segment1 = MagicMock(spec=AudioSegment)
        mock_segment2 = MagicMock(spec=AudioSegment)
        mock_result = MagicMock(spec=AudioSegment)
        
        # Set up the __add__ method to return the result
        mock_segment1.__add__.return_value = mock_result
        
        with patch('logging.error') as mock_log_error:
            with patch('logging.info') as mock_log_info:
                # Create segments that will fail on first method but succeed on fallback
                segments = [mock_segment1, mock_segment2]
                
                # Mock sum() to raise an exception to trigger the fallback
                with patch('builtins.sum', side_effect=Exception("Combine error")):
                    result = audio_handler.combine_audio_segments(segments)
                
                    # Check that error was logged
                    mock_log_error.assert_called()
                    assert "Error combining audio segments" in str(mock_log_error.call_args)
                    
                    # Check that fallback was used
                    mock_log_info.assert_called_with("Falling back to iterative concatenation due to error.")
                    
                    # Check that result is returned
                    assert result == mock_result
    
    def test_try_transcription_with_provider_unknown_provider(self, audio_handler):
        """Test handling of unknown provider (lines 273-274)."""
        segment = AudioSegment.silent(duration=1000)
        
        with patch('logging.warning') as mock_warning:
            result = audio_handler._try_transcription_with_provider(segment, "unknown_provider")
            
            assert result == ""
            mock_warning.assert_called_with("Unknown provider: unknown_provider")
    
    def test_try_transcription_with_provider_exception(self, audio_handler):
        """Test exception handling in _try_transcription_with_provider (lines 276-278)."""
        segment = AudioSegment.silent(duration=1000)
        
        # Mock provider to raise exception
        with patch.object(audio_handler.deepgram_provider, 'transcribe', side_effect=Exception("API Error")):
            with patch('logging.error') as mock_error:
                result = audio_handler._try_transcription_with_provider(segment, "deepgram")
                
                assert result == ""
                mock_error.assert_called()
                assert "Error with deepgram transcription" in str(mock_error.call_args)
    
    def test_process_audio_data_invalid_type(self, audio_handler):
        """Test process_audio_data with invalid input type."""
        with patch('logging.error') as mock_error:
            segment, transcript = audio_handler.process_audio_data("invalid_type")
            
            assert segment is None
            assert transcript == ""
            mock_error.assert_called()
            assert "Unsupported audio data type" in str(mock_error.call_args)
    
    def test_load_audio_file_unsupported_format(self, audio_handler):
        """Test loading unsupported audio file format."""
        with patch('logging.error') as mock_error:
            segment, transcript = audio_handler.load_audio_file("test.unsupported")
            
            assert segment is None
            assert transcript == ""
            mock_error.assert_called()
    
    def test_save_audio_exception(self, audio_handler):
        """Test save_audio exception handling."""
        segments = [AudioSegment.silent(duration=1000)]
        
        with patch.object(AudioSegment, 'export', side_effect=Exception("Export error")):
            with patch('logging.error') as mock_error:
                result = audio_handler.save_audio(segments, "test.mp3")
                
                assert result is False
                mock_error.assert_called()
                assert "Error saving audio" in str(mock_error.call_args)
    
    def test_get_input_devices_exception(self, audio_handler):
        """Test get_input_devices exception handling."""
        # Create a mock soundcard module that raises an exception
        mock_soundcard = Mock()
        mock_soundcard.all_microphones.side_effect = Exception("Device error")
        
        with patch('audio.soundcard', mock_soundcard):
            with patch('audio.SOUNDCARD_AVAILABLE', True):
                with patch('logging.error') as mock_error:
                    devices = audio_handler.get_input_devices()
                    
                    assert devices == []
                    mock_error.assert_called()
                    assert "Error getting input devices" in str(mock_error.call_args)


class TestSoapAudioProcessor:
    """Test SOAP audio processor functionality (lines 698-771)."""
    
    @pytest.fixture
    def audio_handler(self):
        """Create audio handler for SOAP testing."""
        handler = AudioHandler()
        handler.soap_mode = True
        return handler
    
    def test_add_segment_soap_mode(self, audio_handler):
        """Test add_segment in SOAP mode with various audio levels."""
        # Test with normal audio
        audio_data = np.random.uniform(-0.1, 0.1, 48000).astype(np.float32)
        audio_handler.add_segment(audio_data)
        assert len(audio_handler.recorded_frames) == 1
        
        # Test with very quiet audio that needs boosting
        quiet_audio = np.random.uniform(-0.001, 0.001, 48000).astype(np.float32)
        with patch('logging.info') as mock_info:
            audio_handler.add_segment(quiet_audio)
            
            # Check that boost was applied
            boost_logged = False
            for call in mock_info.call_args_list:
                if "Boosted audio by factor" in str(call):
                    boost_logged = True
                    break
            assert boost_logged
            assert len(audio_handler.recorded_frames) == 2
    
    def test_add_segment_with_callback(self, audio_handler):
        """Test add_segment with callback function."""
        callback_called = False
        callback_segment = None
        
        def test_callback(segment):
            nonlocal callback_called, callback_segment
            callback_called = True
            callback_segment = segment
        
        audio_handler.callback_function = test_callback
        
        audio_data = np.random.uniform(-0.1, 0.1, 48000).astype(np.float32)
        audio_handler.add_segment(audio_data)
        
        assert callback_called
        assert callback_segment is not None
    
    def test_add_segment_callback_error(self, audio_handler):
        """Test add_segment when callback raises exception."""
        def failing_callback(segment):
            raise Exception("Callback error")
        
        audio_handler.callback_function = failing_callback
        
        audio_data = np.random.uniform(-0.1, 0.1, 48000).astype(np.float32)
        
        with patch('logging.error') as mock_error:
            audio_handler.add_segment(audio_data)
            
            mock_error.assert_called()
            assert "Error in new segment callback" in str(mock_error.call_args)
    
    def test_add_segment_none_data(self, audio_handler):
        """Test add_segment with None data."""
        with patch('logging.warning') as mock_warning:
            audio_handler.add_segment(None)
            
            mock_warning.assert_called_with("SOAP recording: Received None audio data")
            assert len(audio_handler.recorded_frames) == 0
    
    def test_add_segment_no_shape_attribute(self, audio_handler):
        """Test add_segment with data that has no shape attribute."""
        with patch('logging.warning') as mock_warning:
            audio_handler.add_segment("invalid_data")
            
            mock_warning.assert_called()
            assert "No audio segment created from data of type" in str(mock_warning.call_args)
    
    def test_add_segment_empty_array(self, audio_handler):
        """Test add_segment with empty array."""
        empty_array = np.array([])
        
        with patch('logging.warning') as mock_warning:
            audio_handler.add_segment(empty_array)
            
            # Should log warning about max amplitude
            mock_warning.assert_called()
    
    def test_add_segment_int16_input(self, audio_handler):
        """Test add_segment with int16 input data."""
        audio_data = np.random.uniform(-16000, 16000, 48000).astype(np.int16)
        audio_handler.add_segment(audio_data)
        
        assert len(audio_handler.recorded_frames) == 1
    
    def test_add_segment_other_dtype(self, audio_handler):
        """Test add_segment with other dtype."""
        audio_data = np.random.uniform(-0.1, 0.1, 48000).astype(np.float64)
        audio_handler.add_segment(audio_data)
        
        assert len(audio_handler.recorded_frames) == 1


class TestBackgroundListening:
    """Test background listening functionality."""
    
    @pytest.fixture
    def audio_handler(self):
        """Create audio handler for testing."""
        return AudioHandler()
    
    @patch('sounddevice.query_devices')
    @patch('sounddevice.InputStream')
    def test_listen_in_background_with_sounddevice_fallback(self, mock_stream_class, mock_query_devices, audio_handler):
        """Test listen_in_background with sounddevice and default device fallback."""
        # Mock no matching device found
        mock_query_devices.return_value = [
            {
                'name': 'Different Device',
                'max_input_channels': 2,
                'default_samplerate': 48000,
                'hostapi': 0,
                'index': 0
            }
        ]
        
        # Mock default device
        with patch('sounddevice.query_devices') as mock_query_single:
            # First call returns device list, second call returns default device
            mock_query_single.side_effect = [
                mock_query_devices.return_value,
                {'name': 'Default Device', 'index': 0, 'max_input_channels': 2, 'default_samplerate': 48000}
            ]
            
            mock_stream = Mock()
            mock_stream_class.return_value = mock_stream
            
            callback = Mock()
            
            with patch('logging.warning') as mock_warning:
                stop_function = audio_handler.listen_in_background(
                    mic_name="Nonexistent Device",
                    callback=callback
                )
                
                # Should fall back to default
                assert "Falling back to default sounddevice input" in str(mock_warning.call_args)
    
    @patch('sounddevice.InputStream')
    def test_listen_in_background_port_audio_error(self, mock_stream_class, audio_handler):
        """Test handling of PortAudioError."""
        # Create a mock PortAudioError
        mock_error = sd.PortAudioError("Test error")
        mock_error.hostApiErrorInfo = "Host API Error"
        
        mock_stream_class.side_effect = mock_error
        
        # The function catches the error and returns a no-op lambda
        stop_function = audio_handler.listen_in_background("Test Device", Mock())
        
        # Verify that a function was returned (no-op lambda on error)
        assert callable(stop_function)
        
        # Verify the function works without error
        stop_function()  # Should not raise
    
    def test_stop_listening_not_recording(self, audio_handler):
        """Test _stop_listening when not recording."""
        audio_handler.recording = False
        
        result = audio_handler._stop_listening()
        
        assert result is False
    
    def test_stop_listening_with_active_thread(self, audio_handler):
        """Test _stop_listening with active thread."""
        audio_handler.recording = True
        
        # Create a mock thread that's alive
        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        audio_handler.recording_thread = mock_thread
        
        result = audio_handler._stop_listening(wait_for_stop=True)
        
        assert result is True
        assert audio_handler.recording is False
        mock_thread.join.assert_called_once_with(timeout=2.0)


class TestSpeechRecognitionMethods:
    """Test speech recognition methods (lines 860-929)."""
    
    @pytest.fixture
    def audio_handler(self):
        """Create audio handler for testing."""
        return AudioHandler()
    
    def test_background_recording_thread_soundcard(self, audio_handler):
        """Test _background_recording_thread with soundcard."""
        # Create a mock soundcard module
        mock_soundcard = Mock()
        
        # Create mock microphone
        mock_mic = Mock()
        mock_mic.name = "Test Microphone"
        mock_soundcard.get_microphone.return_value = mock_mic
        
        # Create mock recorder context
        mock_recorder = Mock()
        mock_recorder.record.return_value = np.random.uniform(-0.1, 0.1, 48000).astype(np.float32)
        
        # Set up the context manager properly
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_recorder
        mock_context.__exit__.return_value = None
        mock_mic.recorder.return_value = mock_context
        
        # Set up recording state
        audio_handler.recording = True
        audio_handler.callback_function = Mock()
        
        # Patch the soundcard module
        with patch('audio.soundcard', mock_soundcard):
            with patch('audio.SOUNDCARD_AVAILABLE', True):
                # Run in a thread and stop after a short time
                thread = threading.Thread(
                    target=audio_handler._background_recording_thread,
                    args=(0, 1.0)
                )
                thread.start()
                
                # Let it run briefly
                time.sleep(0.1)
                audio_handler.recording = False
                thread.join(timeout=1.0)
                
                # Verify callback was called
                audio_handler.callback_function.assert_called()
    
    def test_background_recording_thread_no_microphone(self, audio_handler):
        """Test _background_recording_thread when microphone not found."""
        # Create a mock soundcard module
        mock_soundcard = Mock()
        mock_soundcard.get_microphone.return_value = None
        
        with patch('audio.soundcard', mock_soundcard):
            with patch('audio.SOUNDCARD_AVAILABLE', True):
                with patch('logging.error') as mock_error:
                    audio_handler._background_recording_thread(0, 1.0)
                    
                    mock_error.assert_called()
                    assert "could not get microphone" in str(mock_error.call_args)
                
                assert audio_handler.recording is False
    
    def test_background_recording_thread_sc(self, audio_handler):
        """Test _background_recording_thread_sc method."""
        # Create mock device
        mock_device = Mock()
        mock_device.name = "Test Device"
        
        # Create mock recorder
        mock_recorder = Mock()
        test_data = np.random.uniform(-0.1, 0.1, 48000).astype(np.float64)  # Use float64 to test conversion
        mock_recorder.record.return_value = test_data
        
        # Set up the context manager properly
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_recorder
        mock_context.__exit__.return_value = None
        mock_device.recorder.return_value = mock_context
        
        # Set up handler state
        audio_handler.recording = True
        callback_called = False
        received_data = None
        
        def test_callback(data):
            nonlocal callback_called, received_data
            callback_called = True
            received_data = data
            # Stop recording after first callback
            audio_handler.recording = False
        
        audio_handler.callback_function = test_callback
        
        # Run the recording thread
        audio_handler._background_recording_thread_sc(mock_device, 1.0)
        
        assert callback_called
        assert received_data is not None
        assert received_data.dtype == np.float32  # Should be converted
    
    def test_background_recording_thread_sc_exception(self, audio_handler):
        """Test _background_recording_thread_sc with exception."""
        mock_device = Mock()
        mock_device.name = "Test Device"
        mock_device.recorder.side_effect = Exception("Recorder error")
        
        with patch('logging.error') as mock_error:
            audio_handler._background_recording_thread_sc(mock_device, 1.0)
            
            mock_error.assert_called()
            assert "Error in soundcard recording thread" in str(mock_error.call_args)
        
        assert audio_handler.recording is False


class TestDeviceMonitoring:
    """Test device monitoring and resolution methods."""
    
    @pytest.fixture
    def audio_handler(self):
        """Create audio handler for testing."""
        return AudioHandler()
    
    def test_resolve_device_index_exact_match(self, audio_handler):
        """Test _resolve_device_index with exact name match."""
        mock_devices = [
            {'name': 'USB Microphone', 'max_input_channels': 2},
            {'name': 'Built-in Mic', 'max_input_channels': 2}
        ]
        
        with patch('sounddevice.query_devices', return_value=mock_devices):
            index = audio_handler._resolve_device_index('USB Microphone')
            
            assert index == 0
    
    def test_resolve_device_index_case_insensitive(self, audio_handler):
        """Test _resolve_device_index with case-insensitive match."""
        mock_devices = [
            {'name': 'USB Microphone', 'max_input_channels': 2},
            {'name': 'Built-in Mic', 'max_input_channels': 2}
        ]
        
        with patch('sounddevice.query_devices', return_value=mock_devices):
            index = audio_handler._resolve_device_index('usb microphone')
            
            assert index == 0
    
    def test_resolve_device_index_partial_match(self, audio_handler):
        """Test _resolve_device_index with partial match."""
        mock_devices = [
            {'name': 'USB Microphone Pro', 'max_input_channels': 2},
            {'name': 'Built-in Mic', 'max_input_channels': 2}
        ]
        
        with patch('sounddevice.query_devices', return_value=mock_devices):
            index = audio_handler._resolve_device_index('USB Microphone')
            
            assert index == 0
    
    @patch('platform.system')
    def test_resolve_device_index_windows_specific(self, mock_platform, audio_handler):
        """Test Windows-specific device matching."""
        mock_platform.return_value = 'Windows'
        
        mock_devices = [
            {'name': 'Microphone (Windows WASAPI)', 'max_input_channels': 2},
            {'name': 'Other Device', 'max_input_channels': 2}
        ]
        
        with patch('sounddevice.query_devices', return_value=mock_devices):
            index = audio_handler._resolve_device_index('Microphone')
            
            assert index == 0
    
    def test_resolve_device_index_with_device_suffix(self, audio_handler):
        """Test device resolution with (Device X) suffix."""
        mock_devices = [
            {'name': 'HDA Intel PCH: 92HD95 Analog (hw:0,0)', 'max_input_channels': 2},
            {'name': 'USB Device', 'max_input_channels': 2}
        ]
        
        with patch('sounddevice.query_devices', return_value=mock_devices):
            index = audio_handler._resolve_device_index('HDA Intel PCH: 92HD95 Analog (hw:0,0) (Device 0)')
            
            assert index == 0
    
    def test_resolve_device_index_not_found(self, audio_handler):
        """Test _resolve_device_index when device not found."""
        mock_devices = [
            {'name': 'USB Microphone', 'max_input_channels': 2}
        ]
        
        with patch('sounddevice.query_devices', return_value=mock_devices):
            with patch('logging.error') as mock_error:
                index = audio_handler._resolve_device_index('Nonexistent Device')
                
                assert index is None
                mock_error.assert_called()


class TestProcessMonitor:
    """Test process monitoring functionality."""
    
    @pytest.fixture
    def audio_handler(self):
        """Create audio handler for testing."""
        return AudioHandler()
    
    def test_cleanup_resources_with_sd_stop_error(self, audio_handler):
        """Test cleanup_resources when sd.stop() raises error."""
        # Add a mock stream
        mock_stream = Mock()
        audio_handler._active_streams.append(mock_stream)
        
        with patch('sounddevice.stop', side_effect=Exception("Stop error")):
            with patch('logging.error') as mock_error:
                audio_handler.cleanup_resources()
                
                # Should still complete cleanup
                assert len(audio_handler._active_streams) == 0
                mock_stream.stop.assert_called_once()
                mock_stream.close.assert_called_once()
                
                # Should log the sounddevice error
                error_logged = False
                for call in mock_error.call_args_list:
                    if "Error stopping sounddevice" in str(call):
                        error_logged = True
                        break
                assert error_logged
    
    def test_cleanup_resources_stream_stop_error(self, audio_handler):
        """Test cleanup_resources when stream.stop() raises error."""
        # Add a mock stream that raises on stop
        mock_stream = Mock()
        mock_stream.stop.side_effect = Exception("Stream stop error")
        audio_handler._active_streams.append(mock_stream)
        
        with patch('logging.error') as mock_error:
            audio_handler.cleanup_resources()
            
            # Should still clear the list
            assert len(audio_handler._active_streams) == 0
            
            # Should log the error
            mock_error.assert_called()
            assert "Error stopping stream" in str(mock_error.call_args)
    
    def test_whisper_available_property(self, audio_handler):
        """Test whisper_available property."""
        # Mock whisper provider availability
        with patch.object(audio_handler.whisper_provider, 'is_available', True):
            assert audio_handler.whisper_available is True
        
        with patch.object(audio_handler.whisper_provider, 'is_available', False):
            assert audio_handler.whisper_available is False
    
    def test_set_fallback_callback(self, audio_handler):
        """Test set_fallback_callback method."""
        def test_callback():
            pass
        
        audio_handler.set_fallback_callback(test_callback)
        
        assert audio_handler.fallback_callback == test_callback
    
    def test_create_audio_callback_flush(self, audio_handler):
        """Test audio callback flush functionality."""
        audio_handler.sample_rate = 48000
        audio_handler.callback_function = Mock()
        
        # Create callback and flush function
        callback, flush_func = audio_handler._create_audio_callback(phrase_time_limit=2)
        
        # Add some data via callback (not enough to trigger automatic processing)
        test_data = np.random.uniform(-0.1, 0.1, 1000).astype(np.float32)
        callback(test_data, 1000, None, sd.CallbackFlags())
        
        # Callback shouldn't have been called yet
        audio_handler.callback_function.assert_not_called()
        
        # Now flush
        flush_func()
        
        # Callback should have been called with accumulated data
        audio_handler.callback_function.assert_called_once()
    
    def test_create_audio_callback_clipping_detection(self, audio_handler):
        """Test audio callback clipping detection."""
        audio_handler.sample_rate = 48000
        audio_handler.callback_function = Mock()
        
        # Create callback
        callback, _ = audio_handler._create_audio_callback(phrase_time_limit=1)
        
        # Create clipping audio data
        clipping_data = np.ones((48000, 1), dtype=np.float32) * 0.99
        
        with patch('logging.warning') as mock_warning:
            callback(clipping_data, 48000, None, sd.CallbackFlags())
            
            # Should warn about clipping
            warning_found = False
            for call in mock_warning.call_args_list:
                if "CLIPPING DETECTED" in str(call):
                    warning_found = True
                    break
            assert warning_found


class TestPrefixAudioHandling:
    """Test prefix audio handling functionality."""
    
    @pytest.fixture
    def audio_handler(self):
        """Create audio handler for testing."""
        return AudioHandler()
    
    def test_transcribe_audio_with_prefix(self, audio_handler, tmp_path):
        """Test transcribe_audio with prefix audio file."""
        # Create a mock prefix audio file
        prefix_path = tmp_path / "prefix_audio.mp3"
        prefix_audio = AudioSegment.silent(duration=500)
        prefix_audio.export(str(prefix_path), format="mp3")
        
        # Mock the path to use our temp file
        with patch('os.path.dirname', return_value=str(tmp_path)):
            with patch('os.path.exists', return_value=True):
                with patch.object(AudioSegment, 'from_file', return_value=prefix_audio):
                    # Reset the cache flags
                    audio_handler._prefix_audio_checked = False
                    audio_handler._prefix_audio_cache = None
                    
                    # Create test segment
                    test_segment = AudioSegment.silent(duration=1000)
                    
                    # Mock transcription
                    with patch.object(audio_handler.deepgram_provider, 'transcribe', return_value="Test") as mock_transcribe:
                        result = audio_handler.transcribe_audio(test_segment)
                        
                        # Should have loaded and cached the prefix
                        assert audio_handler._prefix_audio_cache is not None
                        assert audio_handler._prefix_audio_checked is True
                        
                        # Transcribe should be called with combined audio
                        call_args = mock_transcribe.call_args[0][0]
                        assert len(call_args) == 1500  # 500ms prefix + 1000ms test
    
    def test_transcribe_audio_prefix_load_error(self, audio_handler):
        """Test transcribe_audio when prefix audio fails to load."""
        with patch('os.path.exists', return_value=True):
            with patch.object(AudioSegment, 'from_file', side_effect=Exception("Load error")):
                with patch('logging.error') as mock_error:
                    # Reset cache flags
                    audio_handler._prefix_audio_checked = False
                    audio_handler._prefix_audio_cache = None
                    
                    test_segment = AudioSegment.silent(duration=1000)
                    
                    with patch.object(audio_handler.deepgram_provider, 'transcribe', return_value="Test"):
                        result = audio_handler.transcribe_audio(test_segment)
                        
                        # Should log error but continue
                        mock_error.assert_called()
                        assert "Error loading prefix audio" in str(mock_error.call_args)
                        assert audio_handler._prefix_audio_cache is None
    
    def test_transcribe_audio_prefix_prepend_error(self, audio_handler):
        """Test transcribe_audio when prepending prefix fails."""
        # Create a real AudioSegment for testing
        test_segment = AudioSegment.silent(duration=1000)
        
        # Create mock prefix that will fail when combined
        # We need to patch the AudioSegment.__add__ method to fail
        with patch.object(AudioSegment, '__add__', side_effect=Exception("Combine error")):
            # Set up the prefix cache
            audio_handler._prefix_audio_checked = True
            audio_handler._prefix_audio_cache = AudioSegment.silent(duration=100)
            
            with patch('audio.logging.error') as mock_error:
                with patch.object(audio_handler.deepgram_provider, 'transcribe', return_value="Test") as mock_transcribe:
                    result = audio_handler.transcribe_audio(test_segment)
                    
                    # Should log error but continue with original segment
                    mock_error.assert_called()
                    assert "Error prepending prefix audio" in str(mock_error.call_args)
                    
                    # Should transcribe original segment
                    mock_transcribe.assert_called_with(test_segment)


class TestFallbackMechanism:
    """Test transcription fallback mechanism."""
    
    @pytest.fixture
    def audio_handler(self):
        """Create audio handler for testing."""
        handler = AudioHandler()
        handler.fallback_callback = Mock()
        return handler
    
    def test_transcribe_audio_with_fallback_callback(self, audio_handler):
        """Test transcription fallback with callback notification."""
        segment = AudioSegment.silent(duration=1000)
        
        # Set primary provider
        with patch.dict('settings.SETTINGS', {'stt_provider': 'deepgram'}):
            # Make primary fail
            with patch.object(audio_handler.deepgram_provider, 'transcribe', return_value=""):
                # Make fallback succeed
                with patch.object(audio_handler.groq_provider, 'transcribe', return_value="Fallback result"):
                    result = audio_handler.transcribe_audio(segment)
                    
                    # Callback should be called
                    audio_handler.fallback_callback.assert_called_with('deepgram', 'groq')
                    assert result == "Fallback result"
    
    def test_transcribe_all_providers_fail(self, audio_handler):
        """Test when all transcription providers fail."""
        segment = AudioSegment.silent(duration=1000)
        
        with patch.dict('settings.SETTINGS', {'stt_provider': 'deepgram'}):
            # Mock all providers to fail
            with patch.object(audio_handler.deepgram_provider, 'transcribe', return_value=""):
                with patch.object(audio_handler.elevenlabs_provider, 'transcribe', return_value=""):
                    with patch.object(audio_handler.groq_provider, 'transcribe', return_value=""):
                        with patch.object(audio_handler.whisper_provider, 'transcribe', return_value=""):
                            result = audio_handler.transcribe_audio(segment)
                            
                            assert result == ""
                            # Fallback callback should have been called multiple times
                            assert audio_handler.fallback_callback.call_count >= 3


class TestProcessAudioDataEdgeCases:
    """Test edge cases in process_audio_data method."""
    
    @pytest.fixture
    def audio_handler(self):
        """Create audio handler for testing."""
        return AudioHandler()
    
    def test_process_audio_data_clipping_input(self, audio_handler):
        """Test process_audio_data with clipping audio input."""
        # Create clipping audio
        clipping_audio = np.ones(48000, dtype=np.float32) * 1.2  # Over maximum
        
        with patch('logging.warning') as mock_warning:
            with patch.object(audio_handler, 'transcribe_audio', return_value="Test"):
                segment, transcript = audio_handler.process_audio_data(clipping_audio)
                
                # Should warn about clipping
                mock_warning.assert_called()
                assert "Input audio is clipping" in str(mock_warning.call_args)
                assert segment is not None
    
    def test_process_audio_data_voicemeeter_boost(self, audio_handler):
        """Test audio boost for Voicemeeter devices."""
        audio_handler.listening_device = "VoiceMeeter Output"
        
        # Create quiet audio that needs boost
        quiet_audio = np.random.uniform(-0.01, 0.01, 48000).astype(np.float32)
        
        with patch('logging.debug') as mock_debug:
            with patch.object(audio_handler, 'transcribe_audio', return_value="Test"):
                segment, transcript = audio_handler.process_audio_data(quiet_audio)
                
                # Should apply boost
                boost_logged = False
                for call in mock_debug.call_args_list:
                    if "Applying boost factor" in str(call) and "Voicemeeter" in str(call):
                        boost_logged = True
                        break
                assert boost_logged
    
    def test_process_audio_data_soap_mode_boost(self, audio_handler):
        """Test enhanced boost in SOAP mode."""
        audio_handler.soap_mode = True
        
        # Create quiet audio
        quiet_audio = np.random.uniform(-0.01, 0.01, 48000).astype(np.float32)
        
        with patch('logging.debug') as mock_debug:
            with patch.object(audio_handler, 'transcribe_audio', return_value="Test"):
                segment, transcript = audio_handler.process_audio_data(quiet_audio)
                
                # Should apply SOAP mode boost
                soap_boost_logged = False
                for call in mock_debug.call_args_list:
                    if "SOAP mode: Applying boost factor" in str(call):
                        soap_boost_logged = True
                        break
                assert soap_boost_logged
    
    def test_process_audio_data_legacy_audio_data(self, audio_handler):
        """Test process_audio_data with legacy AudioData object."""
        # Create AudioData object
        raw_data = np.random.uniform(-16000, 16000, 48000).astype(np.int16).tobytes()
        audio_data = AudioData(raw_data, 44100, 2, 1)
        
        with patch.object(audio_handler, 'transcribe_audio', return_value="Legacy test"):
            segment, transcript = audio_handler.process_audio_data(audio_data)
            
            assert segment is not None
            assert transcript == "Legacy test"
    
    def test_process_audio_data_empty_audio_data(self, audio_handler):
        """Test process_audio_data with empty AudioData."""
        audio_data = AudioData(b'', 44100, 2, 1)
        
        with patch('logging.warning') as mock_warning:
            segment, transcript = audio_handler.process_audio_data(audio_data)
            
            assert segment is None
            assert transcript == ""
            mock_warning.assert_called_with("Empty audio data received")


class TestAudioStreamManagement:
    """Test audio stream management functionality."""
    
    @pytest.fixture
    def audio_handler(self):
        """Create audio handler for testing."""
        return AudioHandler()
    
    def test_listen_with_sounddevice_stream_cleanup_on_error(self, audio_handler):
        """Test stream cleanup when error occurs during setup."""
        mock_stream = Mock()
        mock_stream.stopped = False
        
        # Mock device info - query_devices returns list when called without args
        mock_devices_list = [{
            'name': 'Test Device',
            'hostapi': 0,
            'max_input_channels': 2,
            'index': 0,
            'default_samplerate': 48000
        }]
        
        # Mock device info for specific device query
        mock_device_info = {
            'name': 'Test Device',
            'hostapi': 0,
            'max_input_channels': 2,
            'index': 0,
            'default_samplerate': 48000
        }
        
        def mock_query_devices(index=None):
            if index is None:
                return mock_devices_list
            else:
                return mock_device_info
        
        with patch('sounddevice.query_devices', side_effect=mock_query_devices):
            with patch('sounddevice.InputStream', return_value=mock_stream):
                # Make start() raise an exception
                mock_stream.start.side_effect = Exception("Start failed")
                
                with pytest.raises(Exception, match="Start failed"):
                    audio_handler._listen_with_sounddevice("Test Device", Mock())
                
                # Stream should be cleaned up
                mock_stream.stop.assert_called_once()
                mock_stream.close.assert_called_once()
    
    def test_create_stop_function_with_flush(self, audio_handler):
        """Test stop function with flush callback."""
        mock_stream = Mock()
        mock_flush = Mock()
        
        # Add stream to active list
        audio_handler._active_streams.append(mock_stream)
        audio_handler.listening_device = "Test Device"
        audio_handler.callback_function = Mock()
        
        stop_func = audio_handler._create_stop_function(mock_stream, mock_flush)
        
        # Call stop function
        stop_func()
        
        # Verify flush was called
        mock_flush.assert_called_once()
        
        # Verify stream was stopped and closed
        mock_stream.stop.assert_called_once()
        mock_stream.close.assert_called_once()
        
        # Verify cleanup
        assert audio_handler.listening_device is None
        assert audio_handler.callback_function is None
        assert mock_stream not in audio_handler._active_streams
    
    def test_setup_audio_parameters_multi_channel(self, audio_handler):
        """Test audio parameter setup with multi-channel device."""
        device_info = {
            'name': 'Multi-channel Device',
            'max_input_channels': 8,
            'default_samplerate': 96000
        }
        
        with patch('sounddevice.query_devices', return_value=device_info):
            channels, sample_rate = audio_handler._setup_audio_parameters(0)
            
            assert channels == 1  # Should default to mono
            assert sample_rate == 48000  # Should use 48000 when device supports it
    
    def test_setup_audio_parameters_low_sample_rate_device(self, audio_handler):
        """Test audio parameter setup with low sample rate device."""
        device_info = {
            'name': 'Low Sample Rate Device',
            'max_input_channels': 2,
            'default_samplerate': 22050
        }
        
        with patch('sounddevice.query_devices', return_value=device_info):
            channels, sample_rate = audio_handler._setup_audio_parameters(0)
            
            assert channels == 1
            assert sample_rate == 22050  # Should fall back to device default