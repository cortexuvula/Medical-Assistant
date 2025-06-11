"""
Base class for STT (Speech-to-Text) providers.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional
from pydub import AudioSegment

class BaseSTTProvider(ABC):
    """Base class that all STT providers must implement."""
    
    def __init__(self, api_key: str = "", language: str = "en-US"):
        """Initialize the provider with API key and language settings.
        
        Args:
            api_key: API key for the STT service
            language: Language code for speech recognition
        """
        self.api_key = api_key
        self.language = language
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def transcribe(self, segment: AudioSegment) -> str:
        """Transcribe the provided audio segment.
        
        Args:
            segment: Audio segment to transcribe
            
        Returns:
            Transcription text or empty string if failed
        """
        pass
    
    def _check_api_key(self) -> bool:
        """Check if the API key is available.
        
        Returns:
            True if API key is available, False otherwise
        """
        if not self.api_key:
            self.logger.warning(f"{self.__class__.__name__} API key not found")
            return False
        return True
