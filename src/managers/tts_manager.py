"""
TTS Manager for handling text-to-speech providers.

This module provides the TTSManager class for handling text-to-speech
operations with multiple provider backends. All public methods provide
both exception-based (original) and OperationResult-based (safe) variants
for flexibility in error handling.
"""

import logging
import pygame
import threading
from typing import Optional, Dict, Any, List
from pydub import AudioSegment
from pydub.playback import play

from tts_providers.base import BaseTTSProvider
from tts_providers.pyttsx_provider import PyttsxProvider
from tts_providers.elevenlabs_tts import ElevenLabsTTSProvider
from tts_providers.google_tts import GoogleTTSProvider
from settings.settings import SETTINGS
from utils.security import get_security_manager
from utils.exceptions import APIError
from utils.error_handling import OperationResult


class TTSManager:
    """Manages TTS providers and handles speech synthesis operations."""
    
    def __init__(self):
        """Initialize the TTSManager."""
        self.logger = logging.getLogger(__name__)
        self.providers = {
            "pyttsx3": PyttsxProvider,
            "elevenlabs": ElevenLabsTTSProvider,
            "google": GoogleTTSProvider,
        }
        self._current_provider = None
        self._provider_instance = None
        self.security_manager = get_security_manager()
        
        # Initialize pygame mixer for audio playback
        try:
            pygame.mixer.init()
            self._pygame_available = True
        except (pygame.error, RuntimeError, OSError) as e:
            self._pygame_available = False
            self.logger.warning(f"pygame mixer not available, will use pydub for playback: {e}")
    
    def get_provider(self) -> BaseTTSProvider:
        """Get the current TTS provider instance.
        
        Returns:
            Current TTS provider instance
            
        Raises:
            APIError: If provider cannot be initialized
        """
        try:
            # Get provider settings
            tts_settings = SETTINGS.get("tts", {})
            provider_name = tts_settings.get("provider", "pyttsx3")
            
            # Check if we need to recreate the provider
            if self._current_provider != provider_name or self._provider_instance is None:
                self._create_provider(provider_name)
                self._current_provider = provider_name
            
            return self._provider_instance
            
        except Exception as e:
            self.logger.error(f"Failed to get TTS provider: {e}")
            raise APIError(f"Failed to initialize TTS provider: {str(e)}")
    
    def _create_provider(self, provider_name: str):
        """Create a new provider instance.
        
        Args:
            provider_name: Name of the provider
        """
        if provider_name not in self.providers:
            raise ValueError(f"Unknown provider: {provider_name}")
        
        # Get provider class
        provider_class = self.providers[provider_name]
        
        # Get API key if needed
        api_key = ""
        if provider_name == "elevenlabs":
            api_key = self.security_manager.get_api_key("elevenlabs") or ""
        elif provider_name == "google_cloud":  # Future Google Cloud TTS
            api_key = self.security_manager.get_api_key("google_cloud") or ""
        
        # Create provider instance
        self._provider_instance = provider_class(api_key=api_key)
        
        self.logger.info(f"Created {provider_name} TTS provider")
    
    def synthesize(self, text: str, language: str = None, voice: str = None, **kwargs) -> AudioSegment:
        """Synthesize text to speech.

        Args:
            text: Text to synthesize
            language: Language code (if None, uses settings)
            voice: Voice ID/name (if None, uses default)
            **kwargs: Additional provider-specific parameters

        Returns:
            AudioSegment containing synthesized speech

        Raises:
            ValueError: If text is empty
            Exception: If synthesis fails

        Note:
            For non-throwing version, use synthesize_safe() which returns OperationResult.
        """
        if not text:
            raise ValueError("Text cannot be empty")

        try:
            provider = self.get_provider()

            # Get language from settings if not provided
            if language is None:
                tts_settings = SETTINGS.get("tts", {})
                translation_settings = SETTINGS.get("translation", {})
                language = tts_settings.get("language", translation_settings.get("patient_language", "en"))

            # Get voice from settings if not provided
            if voice is None:
                tts_settings = SETTINGS.get("tts", {})
                voice = tts_settings.get("voice", None)

            # Synthesize speech
            audio = provider.synthesize(text, language, voice, **kwargs)

            self.logger.info(f"Synthesized {len(text)} characters in {language}")
            return audio

        except Exception as e:
            self.logger.error(f"TTS synthesis failed: {e}")
            raise

    def synthesize_safe(self, text: str, language: str = None, voice: str = None, **kwargs) -> OperationResult[AudioSegment]:
        """Synthesize text to speech with OperationResult return type.

        This is the recommended method for new code as it provides structured
        error handling without exceptions.

        Args:
            text: Text to synthesize
            language: Language code (if None, uses settings)
            voice: Voice ID/name (if None, uses default)
            **kwargs: Additional provider-specific parameters

        Returns:
            OperationResult containing AudioSegment on success, or error details on failure

        Example:
            result = manager.synthesize_safe("Hello world")
            if result.success:
                play_audio(result.value)
            else:
                print(f"Error: {result.error}")
        """
        if not text:
            return OperationResult.failure(
                "Text cannot be empty",
                error_code="EMPTY_TEXT"
            )

        try:
            audio = self.synthesize(text, language, voice, **kwargs)
            return OperationResult.success(
                audio,
                language=language,
                voice=voice,
                text_length=len(text)
            )
        except Exception as e:
            return OperationResult.failure(
                f"TTS synthesis failed: {str(e)}",
                error_code="SYNTHESIS_ERROR",
                exception=e,
                language=language,
                voice=voice
            )
    
    def synthesize_and_play(self, text: str, language: str = None, voice: str = None, 
                           blocking: bool = False, output_device: str = None, **kwargs):
        """Synthesize text and play the audio.
        
        Args:
            text: Text to synthesize
            language: Language code
            voice: Voice ID/name
            blocking: If True, wait for playback to complete
            output_device: Specific output device to use for playback
            **kwargs: Additional provider-specific parameters
        """
        try:
            # Synthesize audio
            audio = self.synthesize(text, language, voice, **kwargs)
            
            # Play audio with specified device
            if blocking:
                self._play_audio_blocking(audio, output_device)
            else:
                self._play_audio_async(audio, output_device)
                
        except Exception as e:
            self.logger.error(f"Failed to synthesize and play: {e}")
            raise
    
    def _play_audio_blocking(self, audio: AudioSegment, output_device: str = None):
        """Play audio synchronously (blocking).
        
        Args:
            audio: AudioSegment to play
            output_device: Specific output device to use
        """
        try:
            if output_device:
                # Use sounddevice for device-specific playback
                import sounddevice as sd
                import numpy as np
                
                # Convert AudioSegment to numpy array
                samples = np.array(audio.get_array_of_samples())
                
                # Normalize to float32 in range [-1, 1]
                if audio.sample_width == 2:  # 16-bit
                    samples = samples.astype(np.float32) / 32768.0
                elif audio.sample_width == 1:  # 8-bit
                    samples = (samples.astype(np.float32) - 128) / 128.0
                    
                # Reshape for channels
                if audio.channels == 2:
                    samples = samples.reshape((-1, 2))
                    
                # Find device index
                devices = sd.query_devices()
                device_idx = None
                for idx, dev in enumerate(devices):
                    if dev['name'] == output_device and dev['max_output_channels'] > 0:
                        device_idx = idx
                        break
                
                if device_idx is None:
                    self.logger.warning(f"Output device '{output_device}' not found. Using default.")
                        
                # Play audio
                try:
                    sd.play(samples, samplerate=audio.frame_rate, device=device_idx)
                    sd.wait()  # Wait for playback to complete
                except Exception as e:
                    self.logger.warning(f"Failed to play on device '{output_device}': {e}. Falling back to default.")
                    # Fallback to default device
                    try:
                        sd.play(samples, samplerate=audio.frame_rate)
                        sd.wait()
                    except Exception as e2:
                        self.logger.error(f"Fallback to default device also failed: {e2}")
                        # Last resort: use pygame or pydub
                        if self._pygame_available:
                            import tempfile
                            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=True) as temp:
                                audio.export(temp.name, format='mp3')
                                pygame.mixer.music.load(temp.name)
                                pygame.mixer.music.play()
                                while pygame.mixer.music.get_busy():
                                    pygame.time.Clock().tick(10)
                        else:
                            play(audio)
                
            elif self._pygame_available:
                # Export to temporary file for pygame
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=True) as temp:
                    audio.export(temp.name, format='mp3')
                    pygame.mixer.music.load(temp.name)
                    pygame.mixer.music.play()
                    
                    # Wait for playback to complete
                    while pygame.mixer.music.get_busy():
                        pygame.time.Clock().tick(10)
            else:
                # Use pydub playback
                play(audio)
                
        except Exception as e:
            self.logger.error(f"Audio playback failed: {e}")
            raise
    
    def _play_audio_async(self, audio: AudioSegment, output_device: str = None):
        """Play audio asynchronously (non-blocking).
        
        Args:
            audio: AudioSegment to play
            output_device: Specific output device to use
        """
        # Create thread for playback
        thread = threading.Thread(target=self._play_audio_blocking, args=(audio, output_device))
        thread.daemon = True
        thread.start()
    
    def stop_playback(self):
        """Stop any ongoing audio playback."""
        if self._pygame_available and pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
    
    def get_available_voices(self, language: str = None) -> List[Dict[str, Any]]:
        """Get available voices for current provider.

        Args:
            language: Optional language code to filter voices

        Returns:
            List of voice dictionaries

        Note:
            For structured error handling, use get_available_voices_safe().
        """
        try:
            provider = self.get_provider()
            return provider.get_available_voices(language)
        except Exception as e:
            self.logger.error(f"Failed to get available voices: {e}")
            return []

    def get_available_voices_safe(self, language: str = None) -> OperationResult[List[Dict[str, Any]]]:
        """Get available voices with OperationResult return type.

        Args:
            language: Optional language code to filter voices

        Returns:
            OperationResult containing list of voice dictionaries on success
        """
        try:
            provider = self.get_provider()
            voices = provider.get_available_voices(language)
            return OperationResult.success(voices, language=language)
        except Exception as e:
            return OperationResult.failure(
                f"Failed to get available voices: {str(e)}",
                error_code="VOICES_ERROR",
                exception=e,
                language=language
            )

    def get_supported_languages(self) -> List[Dict[str, Any]]:
        """Get supported languages for current provider.

        Returns:
            List of language dictionaries

        Note:
            For structured error handling, use get_supported_languages_safe().
        """
        try:
            provider = self.get_provider()
            return provider.get_supported_languages()
        except Exception as e:
            self.logger.error(f"Failed to get supported languages: {e}")
            return []

    def get_supported_languages_safe(self) -> OperationResult[List[Dict[str, Any]]]:
        """Get supported languages with OperationResult return type.

        Returns:
            OperationResult containing list of language dictionaries on success
        """
        try:
            provider = self.get_provider()
            languages = provider.get_supported_languages()
            return OperationResult.success(languages)
        except Exception as e:
            return OperationResult.failure(
                f"Failed to get supported languages: {str(e)}",
                error_code="LANGUAGES_ERROR",
                exception=e
            )

    def test_connection(self) -> bool:
        """Test connection to the TTS service.

        Returns:
            True if connection successful, False otherwise

        Note:
            For structured error handling, use test_connection_safe().
        """
        try:
            provider = self.get_provider()
            return provider.test_connection()
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False

    def test_connection_safe(self) -> OperationResult[bool]:
        """Test connection with OperationResult return type.

        Returns:
            OperationResult containing True on success, or error details on failure
        """
        try:
            provider = self.get_provider()
            result = provider.test_connection()
            if result:
                return OperationResult.success(True)
            else:
                return OperationResult.failure(
                    "Connection test failed",
                    error_code="CONNECTION_FAILED"
                )
        except Exception as e:
            return OperationResult.failure(
                f"Connection test error: {str(e)}",
                error_code="CONNECTION_ERROR",
                exception=e
            )
    
    def estimate_duration(self, text: str) -> float:
        """Estimate the duration of synthesized speech.
        
        Args:
            text: Text to estimate duration for
            
        Returns:
            Estimated duration in seconds
        """
        try:
            provider = self.get_provider()
            return provider.estimate_duration(text)
        except Exception as e:
            self.logger.error(f"Duration estimation failed: {e}")
            # Fallback estimation
            words = len(text.split())
            return (words / 150) * 60  # 150 words per minute average
    
    def update_settings(self, settings: Dict[str, Any]):
        """Update TTS settings.
        
        Args:
            settings: New TTS settings
        """
        # Update settings
        SETTINGS["tts"] = settings
        
        # Clear current provider to force recreation
        self._current_provider = None
        self._provider_instance = None
        
        self.logger.info("TTS settings updated")


# Global instance with thread-safe initialization
_tts_manager = None
_tts_manager_lock = threading.Lock()


def get_tts_manager() -> TTSManager:
    """Get or create the global TTSManager instance.

    Thread-safe implementation using double-checked locking pattern.

    Returns:
        TTSManager instance
    """
    global _tts_manager
    if _tts_manager is None:
        with _tts_manager_lock:
            # Double-check after acquiring lock
            if _tts_manager is None:
                _tts_manager = TTSManager()
    return _tts_manager