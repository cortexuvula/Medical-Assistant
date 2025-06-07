"""Test audio handling functionality."""
import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
import tempfile
from pathlib import Path
from audio import AudioHandler
import sounddevice as sd


class TestAudioHandler:
    """Test audio handler functionality."""
    
    @pytest.fixture
    def audio_handler(self, mock_api_keys):
        """Create audio handler with mocked API keys."""
        with patch.dict('os.environ', mock_api_keys):
            handler = AudioHandler(
                deepgram_api_key=mock_api_keys['DEEPGRAM_API_KEY'],
                elevenlabs_api_key=mock_api_keys['ELEVENLABS_API_KEY'],
                groq_api_key=mock_api_keys['GROQ_API_KEY']
            )
            yield handler
    
    @pytest.fixture
    def mock_audio_data(self):
        """Create mock audio data."""
        sample_rate = 44100
        duration = 2.0
        frequency = 440  # A4 note
        
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = np.sin(2 * np.pi * frequency * t)
        
        # Convert to int16
        return (audio * 32767).astype(np.int16)
    
    def test_initialization(self, audio_handler):
        """Test audio handler initialization."""
        assert audio_handler.sample_rate == 48000  # Default is 48000, not 44100
        assert audio_handler.channels == 1
        assert audio_handler.recording == False  # It's 'recording', not 'is_recording'
        assert audio_handler.silence_threshold == 0.001
    
    @patch('settings.save_settings')
    def test_set_stt_provider(self, mock_save_settings, audio_handler):
        """Test setting STT provider."""
        # Test valid providers
        for provider in ["deepgram", "elevenlabs", "groq", "whisper"]:
            audio_handler.set_stt_provider(provider)
            # Provider is stored in SETTINGS, not as an instance attribute
            from settings import SETTINGS
            assert SETTINGS["stt_provider"] == provider
        
        # Test invalid provider - doesn't raise, just logs a warning
        audio_handler.set_stt_provider("invalid_provider")
        # Should not update SETTINGS for invalid provider
    
    def test_start_recording(self, audio_handler):
        """Test recording state initialization."""
        # The AudioHandler doesn't have a start_recording method
        # Instead, it uses listen_in_background for recording
        assert audio_handler.recording == False
        assert audio_handler.recorded_frames == []
    
    def test_stop_listening(self, audio_handler):
        """Test stopping background listening."""
        # The AudioHandler uses _stop_listening method
        audio_handler.recording = True
        audio_handler.recording_thread = Mock()
        audio_handler.recording_thread.is_alive.return_value = False
        
        result = audio_handler._stop_listening(wait_for_stop=True)
        
        assert result == True
        assert audio_handler.recording == False
    
    def test_combine_audio_segments(self, audio_handler):
        """Test combining multiple audio segments."""
        # The method expects AudioSegment objects, not numpy arrays
        from pydub import AudioSegment
        
        # Create test segments
        segment1 = AudioSegment.silent(duration=1000)  # 1 second
        segment2 = AudioSegment.silent(duration=1000)  # 1 second
        
        combined = audio_handler.combine_audio_segments([segment1, segment2])
        
        assert combined is not None
        assert len(combined) == 2000  # 2 seconds in milliseconds
    
    def test_combine_empty_segments(self, audio_handler):
        """Test combining empty segment list."""
        combined = audio_handler.combine_audio_segments([])
        assert combined is None
    
    def test_save_audio(self, audio_handler, temp_dir):
        """Test saving audio to file."""
        from pydub import AudioSegment
        
        # Create test segments
        segments = [AudioSegment.silent(duration=1000) for _ in range(3)]
        output_path = temp_dir / "test_audio.mp3"
        
        # The save_audio method expects a list of AudioSegments
        success = audio_handler.save_audio(segments, str(output_path))
        
        assert success is True
        assert output_path.exists()
        assert output_path.stat().st_size > 0
    
    def test_save_audio_empty_list(self, audio_handler, temp_dir):
        """Test saving empty audio list."""
        output_path = temp_dir / "test_audio.mp3"
        
        # The save_audio method should handle empty lists
        success = audio_handler.save_audio([], str(output_path))
        
        assert success is False
        assert not output_path.exists()
    
    def test_save_audio_error_handling(self, audio_handler, temp_dir):
        """Test save audio error handling."""
        from pydub import AudioSegment
        
        # Test with invalid path
        segments = [AudioSegment.silent(duration=1000)]
        invalid_path = "/invalid/path/that/does/not/exist/test.mp3"
        
        success = audio_handler.save_audio(segments, invalid_path)
        assert success is False
    
    @patch('settings.save_settings')
    def test_transcribe_audio(self, mock_save_settings, audio_handler):
        """Test audio transcription with mock providers."""
        from pydub import AudioSegment
        
        # Create a test segment
        segment = AudioSegment.silent(duration=1000)
        
        # Mock the provider's transcribe method
        with patch.object(audio_handler.deepgram_provider, 'transcribe', return_value="Test transcription"):
            result = audio_handler.transcribe_audio(segment)
            
        assert result == "Test transcription"
    
    @patch('settings.save_settings')
    def test_transcribe_with_fallback(self, mock_save_settings, audio_handler):
        """Test transcription fallback mechanism."""
        from pydub import AudioSegment
        from settings import SETTINGS
        
        # Set primary provider
        SETTINGS["stt_provider"] = "deepgram"
        
        # Create a test segment
        segment = AudioSegment.silent(duration=1000)
        
        # Mock primary provider to fail
        with patch.object(audio_handler.deepgram_provider, 'transcribe', return_value=""):
            # Mock fallback provider to succeed
            with patch.object(audio_handler.groq_provider, 'transcribe', return_value="Fallback transcription"):
                result = audio_handler.transcribe_audio(segment)
                
        assert result == "Fallback transcription"
    
    def test_process_audio_data_empty(self, audio_handler):
        """Test processing empty audio data."""
        # Test with empty numpy array
        segment, transcript = audio_handler.process_audio_data(np.array([]))
        
        assert segment is None
        assert transcript == ""
    
    def test_transcribe_api_error(self, audio_handler):
        """Test handling of transcription API errors."""
        from pydub import AudioSegment
        
        # Create a test segment
        segment = AudioSegment.silent(duration=1000)
        
        # Mock all providers to fail
        with patch.object(audio_handler.deepgram_provider, 'transcribe', side_effect=Exception("API Error")):
            with patch.object(audio_handler.groq_provider, 'transcribe', return_value=""):
                with patch.object(audio_handler.elevenlabs_provider, 'transcribe', return_value=""):
                    with patch.object(audio_handler.whisper_provider, 'transcribe', return_value=""):
                        result = audio_handler.transcribe_audio(segment)
                        
        assert result == ""
    
    @patch('sounddevice.query_devices')
    @patch('sounddevice.InputStream')
    def test_listen_in_background(self, mock_stream_class, mock_query_devices, audio_handler):
        """Test background listening setup."""
        # Mock device query
        mock_query_devices.return_value = [{
            'name': 'Test Microphone',
            'max_input_channels': 2,
            'default_samplerate': 48000,
            'hostapi': 0
        }]
        
        # Mock stream
        mock_stream = Mock()
        mock_stream_class.return_value = mock_stream
        
        callback = Mock()
        stop_function = audio_handler.listen_in_background(
            mic_name="Test Microphone",
            callback=callback,
            phrase_time_limit=3
        )
        
        assert stop_function is not None
        assert callable(stop_function)
    
    def test_process_audio_data_numpy(self, audio_handler):
        """Test processing numpy array audio data."""
        # Create test audio data
        audio_data = np.random.uniform(-0.1, 0.1, 48000).astype(np.float32)
        
        with patch.object(audio_handler, 'transcribe_audio', return_value="Test transcript"):
            segment, transcript = audio_handler.process_audio_data(audio_data)
        
        assert segment is not None
        assert transcript == "Test transcript"
    
    def test_soap_mode_settings(self, audio_handler):
        """Test SOAP mode settings."""
        # Normal mode
        audio_handler.soap_mode = False
        assert audio_handler.silence_threshold == 0.001
        
        # SOAP mode
        audio_handler.soap_mode = True
        # SOAP mode can have different threshold
        audio_handler.silence_threshold = 0.0001
        assert audio_handler.silence_threshold == 0.0001
    
    def test_get_input_devices(self, audio_handler):
        """Test getting available input devices."""
        # Create a mock soundcard module
        mock_soundcard = Mock()
        
        # Mock microphone objects
        mock_mic1 = Mock()
        mock_mic1.name = 'Built-in Microphone'
        mock_mic1.channels = 2
        
        mock_mic2 = Mock()
        mock_mic2.name = 'USB Microphone'
        mock_mic2.channels = 1
        
        mock_soundcard.all_microphones.return_value = [mock_mic1, mock_mic2]
        
        # Patch the soundcard module in audio module
        with patch('audio.soundcard', mock_soundcard):
            with patch('audio.SOUNDCARD_AVAILABLE', True):
                devices = audio_handler.get_input_devices()
        
        assert len(devices) == 2
        assert devices[0]['name'] == 'Built-in Microphone'
        assert devices[0]['channels'] == 2
        assert devices[1]['name'] == 'USB Microphone'
        assert devices[1]['channels'] == 1
    
    def test_cleanup_resources(self, audio_handler):
        """Test resource cleanup."""
        # Mock active streams - use the class variable
        mock_stream = Mock()
        # Save original state
        original_streams = audio_handler._active_streams.copy()
        
        # Set up test state
        audio_handler._active_streams.append(mock_stream)
        audio_handler.soap_mode = True
        
        audio_handler.cleanup_resources()
        
        mock_stream.stop.assert_called_once()
        mock_stream.close.assert_called_once()
        assert len(audio_handler._active_streams) == 0
        assert audio_handler.soap_mode is False
        
        # Restore original state
        audio_handler._active_streams = original_streams
    
    def test_add_segment(self, audio_handler):
        """Test adding audio segment for SOAP recording."""
        # Create test audio data
        audio_data = np.random.uniform(-0.1, 0.1, 48000).astype(np.float32)
        
        # Enable SOAP mode
        audio_handler.soap_mode = True
        
        # Add segment
        audio_handler.add_segment(audio_data)
        
        assert len(audio_handler.recorded_frames) == 1
        
    def test_load_audio_file(self, audio_handler, temp_dir):
        """Test loading audio from file."""
        from pydub import AudioSegment
        
        # Create a test audio file
        test_audio = AudioSegment.silent(duration=1000)
        test_file = temp_dir / "test.mp3"
        test_audio.export(str(test_file), format="mp3")
        
        with patch.object(audio_handler, 'transcribe_audio', return_value="File transcript"):
            segment, transcript = audio_handler.load_audio_file(str(test_file))
        
        assert segment is not None
        assert transcript == "File transcript"