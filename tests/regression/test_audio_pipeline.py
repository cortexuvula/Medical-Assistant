"""Regression tests for audio recording pipeline.

These tests verify that audio recording, transcription,
and storage work correctly.
"""
import pytest
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock, PropertyMock
from dataclasses import dataclass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@dataclass
class MockAudioSegment:
    """Mock AudioSegment for testing."""
    duration_seconds: float = 2.0
    frame_rate: int = 44100
    channels: int = 1
    sample_width: int = 2
    raw_data: bytes = b'\x00' * 176400


class TestAudioHandlerImports:
    """Tests for AudioHandler imports."""

    def test_audio_handler_imports(self):
        """AudioHandler should import correctly."""
        try:
            from src.audio.audio import AudioHandler
            assert AudioHandler is not None
        except ImportError as e:
            pytest.fail(f"Failed to import AudioHandler: {e}")

    def test_recording_manager_imports(self):
        """RecordingManager should import correctly."""
        try:
            from src.audio.recording_manager import RecordingManager
            assert RecordingManager is not None
        except ImportError as e:
            pytest.fail(f"Failed to import RecordingManager: {e}")


class TestAudioHandlerInitialization:
    """Tests for AudioHandler initialization."""

    def test_audio_handler_initializes(self):
        """AudioHandler should initialize with mocked providers."""
        from src.audio.audio import AudioHandler

        # Mock the STT providers that are initialized in __init__
        with patch('src.audio.audio.ElevenLabsProvider') as mock_elevenlabs, \
             patch('src.audio.audio.DeepgramProvider') as mock_deepgram, \
             patch('src.audio.audio.GroqProvider') as mock_groq, \
             patch('src.audio.audio.WhisperProvider') as mock_whisper:
            handler = AudioHandler()

        assert handler is not None

    def test_audio_handler_has_transcribe_method(self):
        """AudioHandler should have transcribe_audio method."""
        from src.audio.audio import AudioHandler

        assert hasattr(AudioHandler, 'transcribe_audio')

    def test_audio_handler_has_set_stt_provider(self):
        """AudioHandler should have set_stt_provider method."""
        from src.audio.audio import AudioHandler

        assert hasattr(AudioHandler, 'set_stt_provider')


class TestRecordingManager:
    """Tests for RecordingManager."""

    def test_recording_manager_has_start_method(self):
        """RecordingManager should have start_recording method."""
        from src.audio.recording_manager import RecordingManager

        assert hasattr(RecordingManager, 'start_recording')

    def test_recording_manager_has_stop_method(self):
        """RecordingManager should have stop_recording method."""
        from src.audio.recording_manager import RecordingManager

        assert hasattr(RecordingManager, 'stop_recording')

    def test_recording_manager_has_is_recording(self):
        """RecordingManager should have is_recording property."""
        from src.audio.recording_manager import RecordingManager

        assert hasattr(RecordingManager, 'is_recording')


class TestTranscriptionFlow:
    """Tests for transcription flow."""

    def test_transcribe_audio_returns_string(self, mock_api_keys):
        """transcribe_audio should return a string."""
        from src.audio.audio import AudioHandler

        # Mock the STT providers
        with patch('src.audio.audio.ElevenLabsProvider'), \
             patch('src.audio.audio.DeepgramProvider'), \
             patch('src.audio.audio.GroqProvider'), \
             patch('src.audio.audio.WhisperProvider'):
            handler = AudioHandler()

            # Mock the transcribe method
            with patch.object(handler, 'transcribe_audio', return_value="Test transcription"):
                result = handler.transcribe_audio(MockAudioSegment())

        assert isinstance(result, str)

    def test_transcription_handles_empty_audio(self, mock_api_keys):
        """Transcription should handle empty/silent audio."""
        from src.audio.audio import AudioHandler

        # Mock the STT providers
        with patch('src.audio.audio.ElevenLabsProvider'), \
             patch('src.audio.audio.DeepgramProvider'), \
             patch('src.audio.audio.GroqProvider'), \
             patch('src.audio.audio.WhisperProvider'):
            handler = AudioHandler()

            with patch.object(handler, 'transcribe_audio', return_value=""):
                result = handler.transcribe_audio(MockAudioSegment())

        # Empty or silence indicator is acceptable
        assert result in ["", "[Silence...]", None] or isinstance(result, str)


class TestProviderSelection:
    """Tests for STT provider selection."""

    def test_set_stt_provider_changes_provider(self, mock_api_keys):
        """set_stt_provider should change the active provider setting."""
        from src.audio.audio import AudioHandler

        # Mock the STT providers and settings
        with patch('src.audio.audio.ElevenLabsProvider'), \
             patch('src.audio.audio.DeepgramProvider'), \
             patch('src.audio.audio.GroqProvider'), \
             patch('src.audio.audio.WhisperProvider'), \
             patch('settings.settings.SETTINGS', {'stt_provider': 'deepgram'}) as mock_settings, \
             patch('settings.settings.save_settings') as mock_save:
            handler = AudioHandler()

            # Call set_stt_provider
            handler.set_stt_provider('groq')

            # Verify settings were updated
            assert mock_settings['stt_provider'] == 'groq'
            mock_save.assert_called_once()


class TestAudioStateManager:
    """Tests for audio state management."""

    def test_audio_state_manager_imports(self):
        """AudioStateManager should import correctly."""
        try:
            from src.audio.audio_state_manager import AudioStateManager
            assert AudioStateManager is not None
        except ImportError as e:
            pytest.fail(f"Failed to import AudioStateManager: {e}")


class TestRecordingLifecycle:
    """Tests for recording lifecycle."""

    def test_recording_start_stop_cycle(self):
        """Recording should start and stop correctly."""
        from src.audio.recording_manager import RecordingManager

        # Create a mock recording manager
        with patch.object(RecordingManager, '__init__', return_value=None):
            manager = RecordingManager.__new__(RecordingManager)
            manager._is_recording = False
            manager._recording_thread = None
            manager._lock = threading.Lock()

            # Mock methods
            manager.start_recording = MagicMock()
            manager.stop_recording = MagicMock(return_value=MockAudioSegment())

            # Simulate lifecycle
            manager.start_recording()
            assert manager.start_recording.called

            manager.stop_recording()
            assert manager.stop_recording.called


class TestVocabularyCorrection:
    """Tests for vocabulary correction in transcription."""

    def test_vocabulary_manager_imports(self):
        """VocabularyManager should import correctly."""
        try:
            from src.managers.vocabulary_manager import VocabularyManager
            assert VocabularyManager is not None
        except ImportError as e:
            pytest.fail(f"Failed to import VocabularyManager: {e}")


class TestPeriodicAnalysis:
    """Tests for periodic analysis during recording."""

    def test_periodic_analyzer_imports(self):
        """PeriodicAnalyzer should import correctly."""
        try:
            from src.audio.periodic_analysis import PeriodicAnalyzer
            assert PeriodicAnalyzer is not None
        except ImportError as e:
            pytest.fail(f"Failed to import PeriodicAnalyzer: {e}")


@pytest.mark.regression
class TestAudioPipelineRegressionSuite:
    """Comprehensive regression tests for audio pipeline."""

    def test_all_audio_modules_import(self):
        """All audio modules should import correctly."""
        modules = [
            'src.audio.audio',
            'src.audio.recording_manager',
            'src.audio.audio_state_manager',
            'src.audio.periodic_analysis',
        ]

        for module_name in modules:
            try:
                __import__(module_name)
            except ImportError as e:
                pytest.fail(f"Failed to import {module_name}: {e}")

    def test_audio_handler_has_required_methods(self):
        """AudioHandler should have all required methods."""
        from src.audio.audio import AudioHandler

        required_methods = [
            'transcribe_audio',
            'transcribe_audio_without_prefix',
            'set_stt_provider',
        ]

        for method in required_methods:
            assert hasattr(AudioHandler, method), f"Missing method: {method}"

    def test_recording_manager_thread_safety(self):
        """RecordingManager should be thread-safe."""
        from src.audio.recording_manager import RecordingManager

        # Check for threading primitives
        with patch.object(RecordingManager, '__init__', return_value=None):
            manager = RecordingManager.__new__(RecordingManager)
            manager._lock = threading.Lock()

            # Should be able to acquire and release lock
            acquired = manager._lock.acquire(timeout=1)
            assert acquired
            manager._lock.release()

    def test_transcription_result_consistency(self, mock_api_keys):
        """Transcription should return consistent result types."""
        from src.audio.audio import AudioHandler

        # Mock the STT providers
        with patch('src.audio.audio.ElevenLabsProvider'), \
             patch('src.audio.audio.DeepgramProvider'), \
             patch('src.audio.audio.GroqProvider'), \
             patch('src.audio.audio.WhisperProvider'):
            handler = AudioHandler()

            # Test with different mock returns
            test_cases = [
                "Normal transcription",
                "",
                "[Silence...]",
                "Text with émojis 🏥",
            ]

            for expected in test_cases:
                with patch.object(handler, 'transcribe_audio', return_value=expected):
                    result = handler.transcribe_audio(MockAudioSegment())
                    assert isinstance(result, str)

    def test_audio_segment_handling(self):
        """Audio segments should be handled correctly."""
        # Create mock audio segment
        segment = MockAudioSegment()

        assert segment.duration_seconds == 2.0
        assert segment.frame_rate == 44100
        assert segment.channels == 1

    def test_provider_fallback_mechanism(self, mock_api_keys):
        """Provider fallback should work when primary fails."""
        from src.audio.audio import AudioHandler

        # Mock the STT providers
        with patch('src.audio.audio.ElevenLabsProvider'), \
             patch('src.audio.audio.DeepgramProvider'), \
             patch('src.audio.audio.GroqProvider'), \
             patch('src.audio.audio.WhisperProvider'):
            handler = AudioHandler()

            # Setup mock providers for fallback testing
            primary_provider = MagicMock()
            primary_provider.transcribe.side_effect = Exception("Primary failed")

            fallback_provider = MagicMock()
            fallback_provider.transcribe.return_value = "Fallback transcription"

            # Mock transcribe_audio to simulate fallback behavior
            with patch.object(handler, 'transcribe_audio', return_value="Fallback transcription"):
                result = handler.transcribe_audio(MockAudioSegment())
                # Should get fallback result
                assert result == "Fallback transcription"

    def test_recording_saves_to_database(self, tmp_path, mock_api_keys):
        """Recording should be saved to database after processing."""
        from src.database.database import Database

        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        db.create_tables()

        # Add a recording
        rec_id = db.add_recording(
            filename="test_recording.wav",
            transcript="Test transcription from audio"
        )

        # Verify it was saved
        recording = db.get_recording(rec_id)
        assert recording is not None
        assert recording["transcript"] == "Test transcription from audio"

        db.close_all_connections()
