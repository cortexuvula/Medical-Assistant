"""
TTS Manager for handling text-to-speech providers.
"""

import logging
import pygame
import threading
from typing import Optional, Dict, Any
from pydub import AudioSegment
from pydub.playback import play

from tts_providers.base import BaseTTSProvider
from tts_providers.pyttsx_provider import PyttsxProvider
from tts_providers.elevenlabs_tts import ElevenLabsTTSProvider
from tts_providers.google_tts import GoogleTTSProvider
from settings.settings import SETTINGS
from utils.security import get_security_manager
from utils.exceptions import APIError


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
        except:
            self._pygame_available = False
            self.logger.warning("pygame mixer not available, will use pydub for playback")
    
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
    
    def synthesize_and_play(self, text: str, language: str = None, voice: str = None, 
                           blocking: bool = False, **kwargs):
        """Synthesize text and play the audio.
        
        Args:
            text: Text to synthesize
            language: Language code
            voice: Voice ID/name
            blocking: If True, wait for playback to complete
            **kwargs: Additional provider-specific parameters
        """
        try:
            # Synthesize audio
            audio = self.synthesize(text, language, voice, **kwargs)
            
            # Play audio
            if blocking:
                self._play_audio_blocking(audio)
            else:
                self._play_audio_async(audio)
                
        except Exception as e:
            self.logger.error(f"Failed to synthesize and play: {e}")
            raise
    
    def _play_audio_blocking(self, audio: AudioSegment):
        """Play audio synchronously (blocking).
        
        Args:
            audio: AudioSegment to play
        """
        try:
            if self._pygame_available:
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
    
    def _play_audio_async(self, audio: AudioSegment):
        """Play audio asynchronously (non-blocking).
        
        Args:
            audio: AudioSegment to play
        """
        # Create thread for playback
        thread = threading.Thread(target=self._play_audio_blocking, args=(audio,))
        thread.daemon = True
        thread.start()
    
    def stop_playback(self):
        """Stop any ongoing audio playback."""
        if self._pygame_available and pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
    
    def get_available_voices(self, language: str = None) -> list:
        """Get available voices for current provider.
        
        Args:
            language: Optional language code to filter voices
            
        Returns:
            List of voice dictionaries
        """
        try:
            provider = self.get_provider()
            return provider.get_available_voices(language)
        except Exception as e:
            self.logger.error(f"Failed to get available voices: {e}")
            return []
    
    def get_supported_languages(self) -> list:
        """Get supported languages for current provider.
        
        Returns:
            List of language dictionaries
        """
        try:
            provider = self.get_provider()
            return provider.get_supported_languages()
        except Exception as e:
            self.logger.error(f"Failed to get supported languages: {e}")
            return []
    
    def test_connection(self) -> bool:
        """Test connection to the TTS service.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            provider = self.get_provider()
            return provider.test_connection()
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
    
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


# Global instance
_tts_manager = None


def get_tts_manager() -> TTSManager:
    """Get or create the global TTSManager instance.
    
    Returns:
        TTSManager instance
    """
    global _tts_manager
    if _tts_manager is None:
        _tts_manager = TTSManager()
    return _tts_manager