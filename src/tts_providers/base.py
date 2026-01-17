"""
Base class for TTS (Text-to-Speech) providers.

This module defines the interface that all TTS providers must implement,
ensuring consistent behavior across different speech synthesis services.

Error Handling:
    - synthesize() raises Exception on failure (callers should catch)
    - test_connection() returns bool, never raises exceptions
    - get_available_voices() returns empty list on failure
    - APIError raised for provider-specific API failures

Logging:
    - Each provider uses get_logger(self.__class__.__name__)
    - Logs include text length, language, voice, and timing
    - API keys are not logged

Usage:
    provider = ElevenLabsTTSProvider(api_key="...")
    audio = provider.synthesize("Hello world", language="en")
    # audio is a pydub AudioSegment ready for playback
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Union
from pydub import AudioSegment
import io

from utils.structured_logging import get_logger


class BaseTTSProvider(ABC):
    """Base class that all TTS providers must implement."""
    
    def __init__(self, api_key: str = ""):
        """Initialize the provider with API key.
        
        Args:
            api_key: API key for the TTS service (if required)
        """
        self.api_key = api_key
        self.logger = get_logger(self.__class__.__name__)
    
    @abstractmethod
    def synthesize(self, text: str, language: str = "en", voice: Optional[str] = None, **kwargs) -> AudioSegment:
        """Convert text to speech and return AudioSegment.
        
        Args:
            text: Text to convert to speech
            language: Language code (e.g., 'en', 'es')
            voice: Optional voice ID/name to use
            **kwargs: Additional provider-specific parameters
            
        Returns:
            AudioSegment containing the synthesized speech
            
        Raises:
            Exception: On synthesis failure
        """
        pass
    
    @abstractmethod
    def get_available_voices(self, language: str = None) -> List[Dict[str, str]]:
        """Get available voices for a language.
        
        Args:
            language: Optional language code to filter voices
            
        Returns:
            List of voice dictionaries with keys:
                - id: Voice identifier
                - name: Human-readable voice name
                - language: Language code
                - gender: Voice gender (male/female/neutral)
                - description: Optional voice description
        """
        pass
    
    @abstractmethod
    def get_supported_languages(self) -> List[Dict[str, str]]:
        """Get list of supported languages.
        
        Returns:
            List of language dictionaries with keys:
                - code: Language code (e.g., 'en', 'es')
                - name: Human-readable language name
        """
        pass
    
    def synthesize_to_file(self, text: str, output_path: str, language: str = "en", 
                          voice: Optional[str] = None, format: str = "mp3", **kwargs) -> str:
        """Synthesize text and save to file.
        
        Args:
            text: Text to synthesize
            output_path: Path where audio file should be saved
            language: Language code
            voice: Optional voice ID/name
            format: Audio format (mp3, wav, etc.)
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Path to the saved audio file
        """
        try:
            # Get audio segment
            audio = self.synthesize(text, language, voice, **kwargs)
            
            # Export to file
            audio.export(output_path, format=format)
            
            self.logger.info(f"Synthesized audio saved to: {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"Failed to synthesize to file: {e}")
            raise
    
    def synthesize_to_bytes(self, text: str, language: str = "en", 
                           voice: Optional[str] = None, format: str = "mp3", **kwargs) -> bytes:
        """Synthesize text and return as bytes.
        
        Args:
            text: Text to synthesize
            language: Language code
            voice: Optional voice ID/name
            format: Audio format
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Audio data as bytes
        """
        try:
            # Get audio segment
            audio = self.synthesize(text, language, voice, **kwargs)
            
            # Export to bytes
            buffer = io.BytesIO()
            audio.export(buffer, format=format)
            return buffer.getvalue()
            
        except Exception as e:
            self.logger.error(f"Failed to synthesize to bytes: {e}")
            raise
    
    def _check_api_key(self) -> bool:
        """Check if the API key is available.
        
        Returns:
            True if API key is available, False otherwise
        """
        if not self.api_key:
            self.logger.warning(f"{self.__class__.__name__} API key not found")
            return False
        return True
    
    def test_connection(self) -> bool:
        """Test the connection to the TTS service.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Try a simple synthesis
            audio = self.synthesize("Hello", "en")
            return audio is not None and len(audio) > 0
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
    
    def estimate_duration(self, text: str, words_per_minute: int = 150) -> float:
        """Estimate the duration of synthesized speech.
        
        Args:
            text: Text to estimate duration for
            words_per_minute: Average speaking rate
            
        Returns:
            Estimated duration in seconds
        """
        # Simple estimation based on word count
        word_count = len(text.split())
        return (word_count / words_per_minute) * 60