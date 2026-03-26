"""
Unit tests for TTSManager.

Tests cover provider management, synthesis operations, playback,
voice/language retrieval, connection testing, and settings management.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock, call
import sys
import threading
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# We need to mock pygame before importing tts_manager since it's imported at module level
@pytest.fixture(autouse=True)
def mock_pygame():
    """Mock pygame to avoid needing audio hardware."""
    mock_pg = MagicMock()
    mock_pg.mixer.init.return_value = None
    mock_pg.mixer.music.get_busy.return_value = False
    mock_pg.error = Exception
    with patch.dict('sys.modules', {'pygame': mock_pg}):
        yield mock_pg


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the TTS manager singleton before each test."""
    import src.managers.tts_manager as tm
    original = tm._tts_manager
    tm._tts_manager = None
    yield
    tm._tts_manager = original


def _make_manager(mock_pygame_fixture=None):
    """Helper to create a TTSManager with all externals mocked."""
    with patch('src.managers.tts_manager.get_security_manager') as mock_sec, \
         patch('src.managers.tts_manager.PyttsxProvider'), \
         patch('src.managers.tts_manager.ElevenLabsTTSProvider'), \
         patch('src.managers.tts_manager.GoogleTTSProvider'), \
         patch('src.managers.tts_manager.pygame') as mock_pg:
        mock_sec.return_value = Mock()
        mock_pg.mixer.init.return_value = None
        mock_pg.error = Exception
        from src.managers.tts_manager import TTSManager
        manager = TTSManager()
        return manager


class TestTTSManagerInitialization:
    """Tests for TTSManager initialization."""

    def test_initialization_creates_provider_registry(self):
        """Test that providers dict is populated on init."""
        manager = _make_manager()
        assert "pyttsx3" in manager.providers
        assert "elevenlabs" in manager.providers
        assert "google" in manager.providers

    def test_initialization_no_current_provider(self):
        """Test that no provider is active initially."""
        manager = _make_manager()
        assert manager._current_provider is None
        assert manager._provider_instance is None

    def test_initialization_gets_security_manager(self):
        """Test that security manager is obtained during init."""
        with patch('src.managers.tts_manager.get_security_manager') as mock_sec, \
             patch('src.managers.tts_manager.PyttsxProvider'), \
             patch('src.managers.tts_manager.ElevenLabsTTSProvider'), \
             patch('src.managers.tts_manager.GoogleTTSProvider'), \
             patch('src.managers.tts_manager.pygame') as mock_pg:
            mock_sm = Mock()
            mock_sec.return_value = mock_sm
            mock_pg.mixer.init.return_value = None
            mock_pg.error = Exception
            from src.managers.tts_manager import TTSManager
            manager = TTSManager()
            mock_sec.assert_called_once()
            assert manager.security_manager is mock_sm

    def test_initialization_pygame_available(self):
        """Test pygame available flag when mixer init succeeds."""
        manager = _make_manager()
        assert manager._pygame_available is True

    def test_initialization_pygame_unavailable(self):
        """Test pygame available flag when mixer init fails."""
        with patch('src.managers.tts_manager.get_security_manager') as mock_sec, \
             patch('src.managers.tts_manager.PyttsxProvider'), \
             patch('src.managers.tts_manager.ElevenLabsTTSProvider'), \
             patch('src.managers.tts_manager.GoogleTTSProvider'), \
             patch('src.managers.tts_manager.pygame') as mock_pg:
            mock_sec.return_value = Mock()
            mock_pg.error = Exception
            mock_pg.mixer.init.side_effect = RuntimeError("No audio device")
            from src.managers.tts_manager import TTSManager
            manager = TTSManager()
            assert manager._pygame_available is False


class TestGetProvider:
    """Tests for provider retrieval and caching."""

    def setup_method(self):
        self.manager = _make_manager()

    @patch('src.managers.tts_manager.settings_manager')
    def test_get_provider_creates_pyttsx3_by_default(self, mock_settings):
        """Test that pyttsx3 is the default provider."""
        mock_settings.get.return_value = {}

        with patch.object(self.manager, '_create_provider') as mock_create:
            self.manager.get_provider()
            mock_create.assert_called_once_with("pyttsx3")

    @patch('src.managers.tts_manager.settings_manager')
    def test_get_provider_creates_elevenlabs_from_settings(self, mock_settings):
        """Test provider creation from settings."""
        mock_settings.get.return_value = {"provider": "elevenlabs"}

        with patch.object(self.manager, '_create_provider') as mock_create:
            self.manager.get_provider()
            mock_create.assert_called_once_with("elevenlabs")

    @patch('src.managers.tts_manager.settings_manager')
    def test_get_provider_caches_instance(self, mock_settings):
        """Test that provider instance is cached between calls."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}

        mock_provider = Mock()
        self.manager._provider_instance = mock_provider
        self.manager._current_provider = "pyttsx3"

        result = self.manager.get_provider()

        assert result is mock_provider

    @patch('src.managers.tts_manager.settings_manager')
    def test_get_provider_recreates_on_provider_change(self, mock_settings):
        """Test that provider is recreated when setting changes."""
        mock_settings.get.return_value = {"provider": "elevenlabs"}

        self.manager._current_provider = "pyttsx3"
        self.manager._provider_instance = Mock()

        with patch.object(self.manager, '_create_provider') as mock_create:
            self.manager.get_provider()
            mock_create.assert_called_once_with("elevenlabs")

    @patch('src.managers.tts_manager.settings_manager')
    def test_get_provider_raises_api_error_on_failure(self, mock_settings):
        """Test that APIError is raised when provider creation fails."""
        from utils.exceptions import APIError
        mock_settings.get.return_value = {"provider": "pyttsx3"}

        with patch.object(self.manager, '_create_provider', side_effect=Exception("init failed")):
            with pytest.raises(APIError) as exc_info:
                self.manager.get_provider()
            assert "init failed" in str(exc_info.value)


class TestCreateProvider:
    """Tests for provider creation."""

    def setup_method(self):
        self.manager = _make_manager()

    def test_create_provider_unknown_raises_value_error(self):
        """Test that unknown provider name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            self.manager._create_provider("unknown_provider")
        assert "Unknown provider" in str(exc_info.value)

    def test_create_provider_pyttsx3(self):
        """Test creating pyttsx3 provider."""
        mock_class = Mock()
        mock_instance = Mock()
        mock_class.return_value = mock_instance
        self.manager.providers["pyttsx3"] = mock_class

        self.manager._create_provider("pyttsx3")

        mock_class.assert_called_once_with(api_key="")
        assert self.manager._provider_instance is mock_instance

    def test_create_provider_elevenlabs_gets_api_key(self):
        """Test that ElevenLabs provider gets API key from security manager."""
        mock_class = Mock()
        mock_instance = Mock()
        mock_class.return_value = mock_instance
        self.manager.providers["elevenlabs"] = mock_class
        self.manager.security_manager.get_api_key.return_value = "el-key-123"

        self.manager._create_provider("elevenlabs")

        self.manager.security_manager.get_api_key.assert_called_with("elevenlabs")
        mock_class.assert_called_once_with(api_key="el-key-123")

    def test_create_provider_elevenlabs_handles_none_api_key(self):
        """Test that None API key is converted to empty string."""
        mock_class = Mock()
        mock_class.return_value = Mock()
        self.manager.providers["elevenlabs"] = mock_class
        self.manager.security_manager.get_api_key.return_value = None

        self.manager._create_provider("elevenlabs")

        mock_class.assert_called_once_with(api_key="")

    def test_create_provider_google(self):
        """Test creating Google TTS provider."""
        mock_class = Mock()
        mock_instance = Mock()
        mock_class.return_value = mock_instance
        self.manager.providers["google"] = mock_class

        self.manager._create_provider("google")

        mock_class.assert_called_once_with(api_key="")
        assert self.manager._provider_instance is mock_instance


class TestSynthesize:
    """Tests for text synthesis."""

    def setup_method(self):
        self.manager = _make_manager()
        self.mock_provider = Mock()
        self.manager._provider_instance = self.mock_provider
        self.manager._current_provider = "pyttsx3"

    def test_synthesize_empty_text_raises_value_error(self):
        """Test that empty text raises ValueError."""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            self.manager.synthesize("")

    def test_synthesize_none_text_raises_value_error(self):
        """Test that None text raises ValueError."""
        with pytest.raises(ValueError):
            self.manager.synthesize(None)

    @patch('src.managers.tts_manager.settings_manager')
    def test_synthesize_with_explicit_params(self, mock_settings):
        """Test synthesis with explicit language and voice."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        mock_audio = Mock()
        self.mock_provider.synthesize.return_value = mock_audio

        result = self.manager.synthesize("Hello world", language="en", voice="voice1")

        self.mock_provider.synthesize.assert_called_once_with("Hello world", "en", "voice1")
        assert result is mock_audio

    @patch('src.managers.tts_manager.settings_manager')
    def test_synthesize_uses_settings_for_language(self, mock_settings):
        """Test that language is fetched from settings when not provided."""
        mock_settings.get.side_effect = lambda key, default=None: {
            "tts": {"provider": "pyttsx3", "language": "es", "voice": "voice2"},
            "translation": {"patient_language": "fr"},
        }.get(key, default)
        mock_audio = Mock()
        self.mock_provider.synthesize.return_value = mock_audio

        self.manager.synthesize("Hola")

        # Should use tts language setting
        call_args = self.mock_provider.synthesize.call_args
        assert call_args[0][1] == "es"

    @patch('src.managers.tts_manager.settings_manager')
    def test_synthesize_falls_back_to_translation_language(self, mock_settings):
        """Test fallback to translation settings for language."""
        mock_settings.get.side_effect = lambda key, default=None: {
            "tts": {"provider": "pyttsx3"},
            "translation": {"patient_language": "fr"},
        }.get(key, default)
        mock_audio = Mock()
        self.mock_provider.synthesize.return_value = mock_audio

        self.manager.synthesize("Bonjour")

        call_args = self.mock_provider.synthesize.call_args
        assert call_args[0][1] == "fr"

    @patch('src.managers.tts_manager.settings_manager')
    def test_synthesize_uses_settings_for_voice(self, mock_settings):
        """Test that voice is fetched from settings when not provided."""
        mock_settings.get.side_effect = lambda key, default=None: {
            "tts": {"provider": "pyttsx3", "voice": "my-voice-id"},
            "translation": {},
        }.get(key, default)
        mock_audio = Mock()
        self.mock_provider.synthesize.return_value = mock_audio

        self.manager.synthesize("Hello")

        call_args = self.mock_provider.synthesize.call_args
        assert call_args[0][2] == "my-voice-id"

    @patch('src.managers.tts_manager.settings_manager')
    def test_synthesize_propagates_provider_error(self, mock_settings):
        """Test that provider errors are re-raised."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        self.mock_provider.synthesize.side_effect = RuntimeError("API failure")

        with pytest.raises(RuntimeError, match="API failure"):
            self.manager.synthesize("Hello", language="en")

    @patch('src.managers.tts_manager.settings_manager')
    def test_synthesize_passes_kwargs(self, mock_settings):
        """Test that extra kwargs are passed to provider."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        mock_audio = Mock()
        self.mock_provider.synthesize.return_value = mock_audio

        self.manager.synthesize("Hello", language="en", voice="v1", model="turbo")

        self.mock_provider.synthesize.assert_called_once_with("Hello", "en", "v1", model="turbo")


class TestSynthesizeSafe:
    """Tests for synthesize_safe (OperationResult variant)."""

    def setup_method(self):
        self.manager = _make_manager()
        self.mock_provider = Mock()
        self.manager._provider_instance = self.mock_provider
        self.manager._current_provider = "pyttsx3"

    def test_synthesize_safe_empty_text_returns_failure(self):
        """Test that empty text returns failure result."""
        result = self.manager.synthesize_safe("")
        assert result.success is False
        assert result.error_code == "EMPTY_TEXT"
        assert "empty" in result.error.lower()

    @patch('src.managers.tts_manager.settings_manager')
    def test_synthesize_safe_success(self, mock_settings):
        """Test successful synthesis returns success result."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        mock_audio = Mock()
        self.mock_provider.synthesize.return_value = mock_audio

        result = self.manager.synthesize_safe("Hello", language="en", voice="v1")

        assert result.success is True
        assert result.value is mock_audio

    @patch('src.managers.tts_manager.settings_manager')
    def test_synthesize_safe_failure_returns_error_result(self, mock_settings):
        """Test that provider failure returns failure result, not exception."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        self.mock_provider.synthesize.side_effect = RuntimeError("API down")

        result = self.manager.synthesize_safe("Hello", language="en")

        assert result.success is False
        assert result.error_code == "SYNTHESIS_ERROR"
        assert "API down" in result.error

    @patch('src.managers.tts_manager.settings_manager')
    def test_synthesize_safe_includes_metadata(self, mock_settings):
        """Test that success result includes metadata."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        mock_audio = Mock()
        self.mock_provider.synthesize.return_value = mock_audio

        result = self.manager.synthesize_safe("Hello world", language="en", voice="v1")

        assert result.success is True
        assert result.details.get("text_length") == 11


class TestSynthesizeAndPlay:
    """Tests for synthesize_and_play."""

    def setup_method(self):
        self.manager = _make_manager()
        self.mock_provider = Mock()
        self.manager._provider_instance = self.mock_provider
        self.manager._current_provider = "pyttsx3"

    @patch('src.managers.tts_manager.settings_manager')
    def test_synthesize_and_play_blocking(self, mock_settings):
        """Test blocking synthesis and playback."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        mock_audio = Mock()
        self.mock_provider.synthesize.return_value = mock_audio

        with patch.object(self.manager, 'stop_playback') as mock_stop, \
             patch.object(self.manager, '_play_audio_blocking') as mock_play:
            self.manager.synthesize_and_play("Hello", language="en", blocking=True)

            mock_stop.assert_called_once()
            mock_play.assert_called_once_with(mock_audio, None)

    @patch('src.managers.tts_manager.settings_manager')
    def test_synthesize_and_play_async(self, mock_settings):
        """Test async synthesis and playback."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        mock_audio = Mock()
        self.mock_provider.synthesize.return_value = mock_audio

        with patch.object(self.manager, 'stop_playback'), \
             patch.object(self.manager, '_play_audio_async') as mock_play:
            self.manager.synthesize_and_play("Hello", language="en", blocking=False)

            mock_play.assert_called_once_with(mock_audio, None)

    @patch('src.managers.tts_manager.settings_manager')
    def test_synthesize_and_play_passes_output_device(self, mock_settings):
        """Test that output device is passed to playback."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        mock_audio = Mock()
        self.mock_provider.synthesize.return_value = mock_audio

        with patch.object(self.manager, 'stop_playback'), \
             patch.object(self.manager, '_play_audio_blocking') as mock_play:
            self.manager.synthesize_and_play(
                "Hello", language="en", blocking=True, output_device="Speaker"
            )
            mock_play.assert_called_once_with(mock_audio, "Speaker")

    @patch('src.managers.tts_manager.settings_manager')
    def test_synthesize_and_play_stops_existing_playback(self, mock_settings):
        """Test that existing playback is stopped first."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        self.mock_provider.synthesize.side_effect = RuntimeError("fail")

        with patch.object(self.manager, 'stop_playback') as mock_stop:
            with pytest.raises(RuntimeError):
                self.manager.synthesize_and_play("Hello", language="en")
            # stop_playback should be called even if synthesis fails
            mock_stop.assert_called_once()

    @patch('src.managers.tts_manager.settings_manager')
    def test_synthesize_and_play_propagates_errors(self, mock_settings):
        """Test that errors are propagated."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        self.mock_provider.synthesize.side_effect = RuntimeError("synthesis error")

        with patch.object(self.manager, 'stop_playback'):
            with pytest.raises(RuntimeError, match="synthesis error"):
                self.manager.synthesize_and_play("Hello", language="en")


class TestPlayAudioBlocking:
    """Tests for _play_audio_blocking."""

    def setup_method(self):
        self.manager = _make_manager()

    @patch('src.managers.tts_manager.pygame')
    def test_play_audio_blocking_with_pygame(self, mock_pg):
        """Test blocking playback with pygame."""
        self.manager._pygame_available = True
        mock_audio = Mock()
        mock_audio.__len__ = Mock(return_value=1000)
        mock_audio.channels = 1
        mock_audio.sample_width = 2
        mock_audio.frame_rate = 44100

        mock_pg.mixer.music.get_busy.side_effect = [True, False]

        with patch('tempfile.NamedTemporaryFile') as mock_tmp:
            mock_tmp.return_value.__enter__ = Mock(return_value=Mock(name="/tmp/test.mp3"))
            mock_tmp.return_value.__exit__ = Mock(return_value=False)

            self.manager._play_audio_blocking(mock_audio)

            mock_audio.export.assert_called_once()
            mock_pg.mixer.music.load.assert_called_once()
            mock_pg.mixer.music.play.assert_called_once()

    @patch('src.managers.tts_manager.play')
    def test_play_audio_blocking_with_pydub_fallback(self, mock_pydub_play):
        """Test blocking playback with pydub when pygame is unavailable."""
        self.manager._pygame_available = False
        mock_audio = Mock()
        mock_audio.__len__ = Mock(return_value=1000)
        mock_audio.channels = 1
        mock_audio.sample_width = 2
        mock_audio.frame_rate = 44100

        self.manager._play_audio_blocking(mock_audio)

        mock_pydub_play.assert_called_once_with(mock_audio)


class TestPlayAudioAsync:
    """Tests for _play_audio_async."""

    def setup_method(self):
        self.manager = _make_manager()

    def test_play_audio_async_creates_daemon_thread(self):
        """Test that async playback creates a daemon thread."""
        mock_audio = Mock()

        with patch('threading.Thread') as mock_thread_class:
            mock_thread = Mock()
            mock_thread_class.return_value = mock_thread

            self.manager._play_audio_async(mock_audio, "Speaker")

            mock_thread_class.assert_called_once_with(
                target=self.manager._play_audio_blocking,
                args=(mock_audio, "Speaker")
            )
            assert mock_thread.daemon is True
            mock_thread.start.assert_called_once()


class TestStopPlayback:
    """Tests for stop_playback."""

    def setup_method(self):
        self.manager = _make_manager()

    @patch('src.managers.tts_manager.pygame')
    def test_stop_playback_stops_pygame(self, mock_pg):
        """Test that pygame playback is stopped."""
        self.manager._pygame_available = True
        mock_pg.mixer.music.get_busy.return_value = True

        with patch('time.sleep'):
            self.manager.stop_playback()

        mock_pg.mixer.music.stop.assert_called_once()

    @patch('src.managers.tts_manager.pygame')
    def test_stop_playback_skips_pygame_if_not_busy(self, mock_pg):
        """Test that stop is not called if pygame is not playing."""
        self.manager._pygame_available = True
        mock_pg.mixer.music.get_busy.return_value = False

        with patch('time.sleep'):
            self.manager.stop_playback()

        mock_pg.mixer.music.stop.assert_not_called()

    @patch('src.managers.tts_manager.pygame')
    def test_stop_playback_handles_sounddevice_import_error(self, mock_pg):
        """Test graceful handling when sounddevice is not available."""
        self.manager._pygame_available = False
        mock_pg.mixer.music.get_busy.side_effect = Exception("not init")

        with patch.dict('sys.modules', {'sounddevice': None}), \
             patch('time.sleep'):
            # Should not raise
            self.manager.stop_playback()

    @patch('src.managers.tts_manager.pygame')
    def test_stop_playback_handles_all_errors_gracefully(self, mock_pg):
        """Test that stop_playback doesn't raise on any error."""
        self.manager._pygame_available = True
        mock_pg.mixer.music.get_busy.side_effect = RuntimeError("crashed")

        with patch('time.sleep'):
            # Should not raise even if everything fails
            self.manager.stop_playback()


class TestGetAvailableVoices:
    """Tests for get_available_voices."""

    def setup_method(self):
        self.manager = _make_manager()
        self.mock_provider = Mock()
        self.manager._provider_instance = self.mock_provider
        self.manager._current_provider = "pyttsx3"

    @patch('src.managers.tts_manager.settings_manager')
    def test_get_available_voices_success(self, mock_settings):
        """Test successful voice listing."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        expected = [{"id": "v1", "name": "Voice 1"}, {"id": "v2", "name": "Voice 2"}]
        self.mock_provider.get_available_voices.return_value = expected

        result = self.manager.get_available_voices()

        assert result == expected

    @patch('src.managers.tts_manager.settings_manager')
    def test_get_available_voices_with_language_filter(self, mock_settings):
        """Test voice listing with language filter."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        self.mock_provider.get_available_voices.return_value = [{"id": "v1"}]

        self.manager.get_available_voices(language="en")

        self.mock_provider.get_available_voices.assert_called_once_with("en")

    @patch('src.managers.tts_manager.settings_manager')
    def test_get_available_voices_returns_empty_on_error(self, mock_settings):
        """Test that empty list is returned on error."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        self.mock_provider.get_available_voices.side_effect = Exception("API error")

        result = self.manager.get_available_voices()

        assert result == []


class TestGetAvailableVoicesSafe:
    """Tests for get_available_voices_safe."""

    def setup_method(self):
        self.manager = _make_manager()
        self.mock_provider = Mock()
        self.manager._provider_instance = self.mock_provider
        self.manager._current_provider = "pyttsx3"

    @patch('src.managers.tts_manager.settings_manager')
    def test_get_available_voices_safe_success(self, mock_settings):
        """Test successful voice listing returns OperationResult."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        expected = [{"id": "v1"}]
        self.mock_provider.get_available_voices.return_value = expected

        result = self.manager.get_available_voices_safe(language="en")

        assert result.success is True
        assert result.value == expected

    @patch('src.managers.tts_manager.settings_manager')
    def test_get_available_voices_safe_failure(self, mock_settings):
        """Test that failure returns error result."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        self.mock_provider.get_available_voices.side_effect = RuntimeError("timeout")

        result = self.manager.get_available_voices_safe()

        assert result.success is False
        assert result.error_code == "VOICES_ERROR"
        assert "timeout" in result.error


class TestGetSupportedLanguages:
    """Tests for get_supported_languages."""

    def setup_method(self):
        self.manager = _make_manager()
        self.mock_provider = Mock()
        self.manager._provider_instance = self.mock_provider
        self.manager._current_provider = "pyttsx3"

    @patch('src.managers.tts_manager.settings_manager')
    def test_get_supported_languages_success(self, mock_settings):
        """Test successful language listing."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        expected = [{"code": "en", "name": "English"}]
        self.mock_provider.get_supported_languages.return_value = expected

        result = self.manager.get_supported_languages()

        assert result == expected

    @patch('src.managers.tts_manager.settings_manager')
    def test_get_supported_languages_returns_empty_on_error(self, mock_settings):
        """Test that empty list is returned on error."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        self.mock_provider.get_supported_languages.side_effect = Exception("fail")

        result = self.manager.get_supported_languages()

        assert result == []


class TestGetSupportedLanguagesSafe:
    """Tests for get_supported_languages_safe."""

    def setup_method(self):
        self.manager = _make_manager()
        self.mock_provider = Mock()
        self.manager._provider_instance = self.mock_provider
        self.manager._current_provider = "pyttsx3"

    @patch('src.managers.tts_manager.settings_manager')
    def test_get_supported_languages_safe_success(self, mock_settings):
        """Test successful language listing returns OperationResult."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        expected = [{"code": "en"}]
        self.mock_provider.get_supported_languages.return_value = expected

        result = self.manager.get_supported_languages_safe()

        assert result.success is True
        assert result.value == expected

    @patch('src.managers.tts_manager.settings_manager')
    def test_get_supported_languages_safe_failure(self, mock_settings):
        """Test failure returns error result."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        self.mock_provider.get_supported_languages.side_effect = RuntimeError("err")

        result = self.manager.get_supported_languages_safe()

        assert result.success is False
        assert result.error_code == "LANGUAGES_ERROR"


class TestTestConnection:
    """Tests for test_connection."""

    def setup_method(self):
        self.manager = _make_manager()
        self.mock_provider = Mock()
        self.manager._provider_instance = self.mock_provider
        self.manager._current_provider = "pyttsx3"

    @patch('src.managers.tts_manager.settings_manager')
    def test_test_connection_success(self, mock_settings):
        """Test successful connection test."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        self.mock_provider.test_connection.return_value = True

        result = self.manager.test_connection()

        assert result is True

    @patch('src.managers.tts_manager.settings_manager')
    def test_test_connection_failure(self, mock_settings):
        """Test connection test failure."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        self.mock_provider.test_connection.return_value = False

        result = self.manager.test_connection()

        assert result is False

    @patch('src.managers.tts_manager.settings_manager')
    def test_test_connection_returns_false_on_error(self, mock_settings):
        """Test that False is returned on connection error."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        self.mock_provider.test_connection.side_effect = Exception("timeout")

        result = self.manager.test_connection()

        assert result is False


class TestTestConnectionSafe:
    """Tests for test_connection_safe."""

    def setup_method(self):
        self.manager = _make_manager()
        self.mock_provider = Mock()
        self.manager._provider_instance = self.mock_provider
        self.manager._current_provider = "pyttsx3"

    @patch('src.managers.tts_manager.settings_manager')
    def test_test_connection_safe_success(self, mock_settings):
        """Test successful connection returns success result."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        self.mock_provider.test_connection.return_value = True

        result = self.manager.test_connection_safe()

        assert result.success is True
        assert result.value is True

    @patch('src.managers.tts_manager.settings_manager')
    def test_test_connection_safe_failed_connection(self, mock_settings):
        """Test failed connection returns failure result."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        self.mock_provider.test_connection.return_value = False

        result = self.manager.test_connection_safe()

        assert result.success is False
        assert result.error_code == "CONNECTION_FAILED"

    @patch('src.managers.tts_manager.settings_manager')
    def test_test_connection_safe_exception(self, mock_settings):
        """Test connection exception returns error result."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        self.mock_provider.test_connection.side_effect = RuntimeError("network error")

        result = self.manager.test_connection_safe()

        assert result.success is False
        assert result.error_code == "CONNECTION_ERROR"
        assert "network error" in result.error


class TestEstimateDuration:
    """Tests for estimate_duration."""

    def setup_method(self):
        self.manager = _make_manager()
        self.mock_provider = Mock()
        self.manager._provider_instance = self.mock_provider
        self.manager._current_provider = "pyttsx3"

    @patch('src.managers.tts_manager.settings_manager')
    def test_estimate_duration_success(self, mock_settings):
        """Test successful duration estimation."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        self.mock_provider.estimate_duration.return_value = 5.0

        result = self.manager.estimate_duration("Hello world this is a test")

        assert result == 5.0

    @patch('src.managers.tts_manager.settings_manager')
    def test_estimate_duration_fallback_on_error(self, mock_settings):
        """Test fallback estimation when provider fails."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        self.mock_provider.estimate_duration.side_effect = Exception("not supported")

        # "Hello world" = 2 words, (2 / 150) * 60 = 0.8 seconds
        result = self.manager.estimate_duration("Hello world")

        assert abs(result - 0.8) < 0.01

    @patch('src.managers.tts_manager.settings_manager')
    def test_estimate_duration_fallback_empty_text(self, mock_settings):
        """Test fallback with empty text returns zero."""
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        self.mock_provider.estimate_duration.side_effect = Exception("fail")

        result = self.manager.estimate_duration("")

        # "".split() returns [], len=0, so (0/150)*60 = 0.0
        assert result == 0.0


class TestUpdateSettings:
    """Tests for settings update."""

    def setup_method(self):
        self.manager = _make_manager()
        self.manager._current_provider = "pyttsx3"
        self.manager._provider_instance = Mock()

    @patch('src.managers.tts_manager.settings_manager')
    def test_update_settings_saves_to_settings_manager(self, mock_settings):
        """Test that settings are persisted."""
        new_settings = {"provider": "elevenlabs", "voice": "v1"}

        self.manager.update_settings(new_settings)

        mock_settings.set.assert_called_once_with("tts", new_settings)

    @patch('src.managers.tts_manager.settings_manager')
    def test_update_settings_clears_provider_cache(self, mock_settings):
        """Test that provider cache is cleared on settings update."""
        self.manager.update_settings({"provider": "elevenlabs"})

        assert self.manager._current_provider is None
        assert self.manager._provider_instance is None


class TestGetTTSManager:
    """Tests for the global singleton getter."""

    def test_get_tts_manager_returns_instance(self):
        """Test that get_tts_manager returns an instance."""
        import src.managers.tts_manager as tm
        tm._tts_manager = None

        with patch.object(tm.TTSManager, '__init__', return_value=None):
            manager = tm.get_tts_manager()
            assert manager is not None

    def test_get_tts_manager_returns_same_instance(self):
        """Test singleton behavior."""
        import src.managers.tts_manager as tm
        tm._tts_manager = None

        with patch.object(tm.TTSManager, '__init__', return_value=None):
            manager1 = tm.get_tts_manager()
            manager2 = tm.get_tts_manager()
            assert manager1 is manager2

    def test_get_tts_manager_thread_safe(self):
        """Test that singleton creation is thread-safe."""
        import src.managers.tts_manager as tm
        tm._tts_manager = None

        instances = []
        barrier = threading.Barrier(5)

        def get_instance():
            barrier.wait()
            with patch.object(tm.TTSManager, '__init__', return_value=None):
                inst = tm.get_tts_manager()
                instances.append(inst)

        threads = [threading.Thread(target=get_instance) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        # All threads should get the same instance
        assert len(set(id(i) for i in instances)) == 1


class TestProviderSwitching:
    """Tests for switching between providers."""

    def setup_method(self):
        self.manager = _make_manager()

    @patch('src.managers.tts_manager.settings_manager')
    def test_switch_from_pyttsx3_to_elevenlabs(self, mock_settings):
        """Test switching provider clears old and creates new."""
        mock_class_pyttsx3 = Mock()
        mock_class_el = Mock()
        mock_instance_pyttsx3 = Mock()
        mock_instance_el = Mock()
        mock_class_pyttsx3.return_value = mock_instance_pyttsx3
        mock_class_el.return_value = mock_instance_el
        self.manager.providers["pyttsx3"] = mock_class_pyttsx3
        self.manager.providers["elevenlabs"] = mock_class_el
        self.manager.security_manager.get_api_key.return_value = "key123"

        # Start with pyttsx3
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        self.manager.get_provider()
        assert self.manager._provider_instance is mock_instance_pyttsx3

        # Switch to elevenlabs
        mock_settings.get.return_value = {"provider": "elevenlabs"}
        self.manager.get_provider()
        assert self.manager._provider_instance is mock_instance_el
        assert self.manager._current_provider == "elevenlabs"

    @patch('src.managers.tts_manager.settings_manager')
    def test_update_settings_forces_provider_recreation(self, mock_settings):
        """Test that update_settings forces provider recreation on next call."""
        mock_class = Mock()
        mock_class.return_value = Mock()
        self.manager.providers["pyttsx3"] = mock_class

        # Set initial provider
        mock_settings.get.return_value = {"provider": "pyttsx3"}
        self.manager.get_provider()

        # Update settings
        self.manager.update_settings({"provider": "pyttsx3", "voice": "new_voice"})

        # Next get_provider should create a new instance
        mock_class.reset_mock()
        self.manager.get_provider()
        mock_class.assert_called_once()
