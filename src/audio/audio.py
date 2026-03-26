"""
Audio Handler - Facade module

This module provides the AudioHandler class which combines all audio functionality
through mixin inheritance. It serves as the single entry point for audio operations.

All existing imports like ``from audio.audio import AudioHandler, AudioData`` continue
to work unchanged.
"""

import atexit
import threading

from core.config import get_config
from stt_providers import DeepgramProvider, ElevenLabsProvider, GroqProvider, WhisperProvider, ModulateProvider
from utils.structured_logging import get_logger
from audio.constants import (
    DEFAULT_SAMPLE_RATE,
    DEFAULT_SAMPLE_WIDTH,
    DEFAULT_CHANNELS,
)

# Re-export availability flags and library references so that existing code
# (including test patches like ``patch('audio.audio.soundcard', ...)``) keeps working.
try:
    import soundcard
    SOUNDCARD_AVAILABLE = True
except (ImportError, AssertionError, OSError):
    soundcard = None
    SOUNDCARD_AVAILABLE = False

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except (ImportError, OSError):
    sd = None
    SOUNDDEVICE_AVAILABLE = False

# Import all mixins
from audio.mixins.transcription_mixin import TranscriptionMixin
from audio.mixins.device_mixin import DeviceMixin
from audio.mixins.file_mixin import FileMixin
from audio.mixins.processing_mixin import ProcessingMixin
from audio.mixins.recording_mixin import RecordingMixin


# Define AudioData type for annotations
class AudioData:
    """Simple class to mimic speech_recognition.AudioData for backward compatibility"""
    def __init__(self, frame_data, sample_rate, sample_width, channels=1):
        self.frame_data = frame_data
        self.sample_rate = sample_rate
        self.sample_width = sample_width
        self.channels = channels

    def get_raw_data(self) -> bytes:
        return self.frame_data


logger = get_logger(__name__)


class AudioHandler(
    TranscriptionMixin,
    DeviceMixin,
    FileMixin,
    ProcessingMixin,
    RecordingMixin,
):
    """Class to handle all audio-related functionality including recording, transcription, and file operations.

    Resource Management:
        Audio streams are tracked both at class level (for global cleanup) and
        instance level (for per-instance cleanup). This ensures proper resource
        release even when instances are garbage collected.

    This class composes functionality from:
    - TranscriptionMixin: STT provider management, transcription with prefix/fallback
    - DeviceMixin: Input device enumeration, device index resolution
    - FileMixin: Audio file loading, saving, validation
    - ProcessingMixin: Audio segment combination, conversion, SOAP segment handling
    - RecordingMixin: Background listening, stream lifecycle, soundcard threads
    """

    # Get configuration
    _config = get_config()

    # Default audio chunk duration in seconds
    DEFAULT_PHRASE_TIME_LIMIT = _config.transcription.chunk_duration_seconds

    # Track active listening sessions for proper cleanup (class level)
    _active_streams = {}  # Class variable to track all active streams by purpose
    _streams_lock = threading.Lock()  # Lock for thread-safe stream management
    _instances = []  # Track all instances for atexit cleanup
    _instances_lock = threading.Lock()

    def __init__(self, elevenlabs_api_key: str = "", deepgram_api_key: str = "", recognition_language: str = "en-US", groq_api_key: str = "", modulate_api_key: str = ""):
        """Initialize the AudioHandler with necessary API keys and settings.

        Args:
            elevenlabs_api_key: API key for ElevenLabs
            deepgram_api_key: API key for Deepgram
            recognition_language: Language code for speech recognition
            groq_api_key: API key for GROQ (default STT provider)
            modulate_api_key: API key for Modulate (Velma Transcribe)
        """
        self.elevenlabs_api_key = elevenlabs_api_key
        self.deepgram_api_key = deepgram_api_key
        self.groq_api_key = groq_api_key
        self.modulate_api_key = modulate_api_key
        self.recognition_language = recognition_language

        # Initialize STT providers
        self.elevenlabs_provider = ElevenLabsProvider(elevenlabs_api_key, recognition_language)
        self.deepgram_provider = DeepgramProvider(deepgram_api_key, recognition_language)
        self.groq_provider = GroqProvider(groq_api_key, recognition_language)
        self.whisper_provider = WhisperProvider("", recognition_language)
        self.modulate_provider = ModulateProvider(modulate_api_key, recognition_language)

        # Initialize fallback callback to None
        self.fallback_callback = None

        # Default audio parameters for recording
        self.sample_rate = DEFAULT_SAMPLE_RATE  # Hz - Higher sample rate for better quality
        self.channels = DEFAULT_CHANNELS  # Mono
        self.sample_width = DEFAULT_SAMPLE_WIDTH  # Bytes (16-bit)
        self.recording = False
        self.recording_thread = None
        self.recorded_frames = []
        self.callback_function = None
        self.listening_device = None

        # Silence detection threshold - can be adjusted dynamically
        self.silence_threshold = 0.001

        # Special SOAP mode flag
        self.soap_mode = False

        # Cache for prefix audio to avoid repeated file loading
        # Tracks file mtime so cache is invalidated when file changes
        self._prefix_audio_cache = None
        self._prefix_audio_checked = False
        self._prefix_audio_mtime = None  # Last known modification time of prefix file

        # Track streams owned by this instance for proper cleanup
        self._instance_streams: set = set()  # Set of stream purposes owned by this instance

        # Register this instance for atexit cleanup
        import weakref
        with AudioHandler._instances_lock:
            AudioHandler._instances.append(weakref.ref(self))

    @property
    def whisper_available(self) -> bool:
        """Check if Whisper is available on the system.

        Returns:
            True if Whisper is available, False otherwise
        """
        return self.whisper_provider.is_available

    def set_fallback_callback(self, callback) -> None:
        """Set the fallback callback for when transcription fails.

        Args:
            callback: Function to call when transcription fails
        """
        self.fallback_callback = callback

    def cleanup_resources(self) -> None:
        """Cleanup all audio resources owned by this instance.

        This method ensures all audio streams owned by this instance are properly
        closed and resources are released to prevent issues on application restart.

        Thread-safe: Uses class-level lock to prevent race conditions.
        """
        logger.debug("AudioHandler: Cleaning up audio resources...")

        streams_closed = 0

        with AudioHandler._streams_lock:
            # Clean up streams owned by THIS instance
            for purpose in list(self._instance_streams):
                try:
                    stream_info = AudioHandler._active_streams.pop(purpose, None)
                    if stream_info and 'stream' in stream_info:
                        stream = stream_info['stream']
                        try:
                            stream.stop()
                            stream.close()
                            streams_closed += 1
                        except (OSError, AttributeError) as e:
                            logger.error(f"AudioHandler: Error stopping stream for {purpose}: {str(e)}")
                except (OSError, KeyError) as e:
                    logger.error(f"AudioHandler: Error cleaning up stream {purpose}: {str(e)}", exc_info=True)

            # Clear instance stream tracking
            self._instance_streams.clear()

        # Terminate sounddevice streams if any are active (outside lock to avoid deadlock)
        try:
            if SOUNDDEVICE_AVAILABLE:
                sd.stop()
        except (OSError, AttributeError) as e:
            logger.error(f"AudioHandler: Error stopping sounddevice: {str(e)}", exc_info=True)

        # Reset any internal state variables that might persist
        self.soap_mode = False
        self.listening_device = None
        self.callback_function = None

        # Single summary log
        if streams_closed > 0:
            logger.info(f"AudioHandler: Cleanup complete, {streams_closed} stream(s) closed")

    def __del__(self):
        """Ensure cleanup on garbage collection.

        This is a safety net - explicit cleanup_resources() is preferred.
        """
        try:
            # Only cleanup if we have streams to clean
            if hasattr(self, '_instance_streams') and self._instance_streams:
                self.cleanup_resources()
        except Exception as e:
            # Log but don't raise in __del__ to avoid exceptions during GC
            try:
                logger.debug(f"AudioHandler.__del__ cleanup error (non-fatal): {e}")
            except Exception:
                pass  # Logger may be unavailable during shutdown


def _atexit_cleanup_audio():
    """Clean up all AudioHandler instances on interpreter shutdown.

    Registered via atexit to ensure audio streams are properly closed
    even if cleanup_resources() was never called explicitly.
    """
    with AudioHandler._instances_lock:
        for ref in AudioHandler._instances:
            instance = ref()
            if instance is not None:
                try:
                    instance.cleanup_resources()
                except Exception:
                    pass  # Best-effort during shutdown
        AudioHandler._instances.clear()


atexit.register(_atexit_cleanup_audio)
