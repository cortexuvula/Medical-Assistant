"""
Base class for translation providers.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class BaseTranslationProvider(ABC):
    """Base class that all translation providers must implement."""

    def __init__(self, api_key: str = ""):
        """Initialize the provider with API key.

        Args:
            api_key: API key for the translation service
        """
        self.api_key = api_key
        # Using module-level logger
    
    @abstractmethod
    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text from source to target language.
        
        Args:
            text: Text to translate
            source_lang: Source language code (e.g., 'en', 'es')
            target_lang: Target language code (e.g., 'en', 'es')
            
        Returns:
            Translated text or empty string if failed
        """
        pass
    
    @abstractmethod
    def get_supported_languages(self) -> List[Tuple[str, str]]:
        """Return list of supported languages.
        
        Returns:
            List of (code, name) tuples for supported languages
        """
        pass
    
    @abstractmethod
    def detect_language(self, text: str) -> Optional[str]:
        """Detect the language of the given text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Language code or None if detection failed
        """
        pass
    
    def _check_api_key(self) -> bool:
        """Check if the API key is available.
        
        Returns:
            True if API key is available, False otherwise
        """
        if not self.api_key:
            logger.warning(f"{self.__class__.__name__} API key not found")
            return False
        return True
    
    def test_connection(self) -> bool:
        """Test the connection to the translation service.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Try a simple translation
            result = self.translate("Hello", "en", "es")
            return bool(result)
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False