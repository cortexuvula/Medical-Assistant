"""
Translation Manager for handling translation providers.
"""

import logging
from typing import Optional, Dict, Any

from translation.base import BaseTranslationProvider
from translation.deep_translator_provider import DeepTranslatorProvider
from settings.settings import SETTINGS
from utils.security import get_security_manager
from utils.exceptions import TranslationError


class TranslationManager:
    """Manages translation providers and handles translation operations."""
    
    def __init__(self):
        """Initialize the TranslationManager."""
        self.logger = logging.getLogger(__name__)
        self.providers = {
            "deep_translator": DeepTranslatorProvider,
        }
        self._current_provider = None
        self._provider_instance = None
        self.security_manager = get_security_manager()
    
    def get_provider(self) -> BaseTranslationProvider:
        """Get the current translation provider instance.
        
        Returns:
            Current translation provider instance
            
        Raises:
            TranslationError: If provider cannot be initialized
        """
        try:
            # Get provider settings
            translation_settings = SETTINGS.get("translation", {})
            provider_name = translation_settings.get("provider", "deep_translator")
            sub_provider = translation_settings.get("sub_provider", "google")
            
            # Check if we need to recreate the provider
            provider_key = f"{provider_name}:{sub_provider}"
            if self._current_provider != provider_key or self._provider_instance is None:
                self._create_provider(provider_name, sub_provider)
                self._current_provider = provider_key
            
            return self._provider_instance
            
        except Exception as e:
            self.logger.error(f"Failed to get translation provider: {e}")
            raise TranslationError(f"Failed to initialize translation provider: {str(e)}")
    
    def _create_provider(self, provider_name: str, sub_provider: str = None):
        """Create a new provider instance.
        
        Args:
            provider_name: Name of the provider
            sub_provider: Sub-provider for deep_translator (google, deepl, microsoft)
        """
        if provider_name not in self.providers:
            raise ValueError(f"Unknown provider: {provider_name}")
        
        # Get provider class
        provider_class = self.providers[provider_name]
        
        # Get API key if needed
        api_key = ""
        if provider_name == "deep_translator" and sub_provider in ["deepl", "microsoft"]:
            # Get API key from security manager
            key_name = f"{sub_provider}_translation"
            api_key = self.security_manager.get_api_key(key_name) or ""
        
        # Create provider instance
        if provider_name == "deep_translator":
            self._provider_instance = provider_class(
                provider_type=sub_provider or "google",
                api_key=api_key
            )
        else:
            self._provider_instance = provider_class(api_key=api_key)
        
        self.logger.info(f"Created {provider_name} provider with sub-provider: {sub_provider}")
    
    def translate(self, text: str, source_lang: str = None, target_lang: str = None) -> str:
        """Translate text using the current provider.
        
        Args:
            text: Text to translate
            source_lang: Source language code (if None, will auto-detect)
            target_lang: Target language code (if None, uses settings)
            
        Returns:
            Translated text
        """
        if not text:
            return ""
        
        try:
            provider = self.get_provider()
            
            # Get language settings if not provided
            translation_settings = SETTINGS.get("translation", {})
            if source_lang is None:
                # Try to detect language
                detected_lang = provider.detect_language(text)
                source_lang = detected_lang or translation_settings.get("patient_language", "es")
            
            if target_lang is None:
                target_lang = translation_settings.get("doctor_language", "en")
            
            # Perform translation
            result = provider.translate(text, source_lang, target_lang)
            
            self.logger.info(f"Translated text from {source_lang} to {target_lang}")
            return result
            
        except Exception as e:
            self.logger.error(f"Translation failed: {e}")
            raise
    
    def detect_language(self, text: str) -> Optional[str]:
        """Detect the language of the given text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Language code or None if detection failed
        """
        try:
            provider = self.get_provider()
            return provider.detect_language(text)
        except Exception as e:
            self.logger.error(f"Language detection failed: {e}")
            return None
    
    def get_supported_languages(self) -> list:
        """Get list of supported languages for current provider.
        
        Returns:
            List of (code, name) tuples
        """
        try:
            provider = self.get_provider()
            return provider.get_supported_languages()
        except Exception as e:
            self.logger.error(f"Failed to get supported languages: {e}")
            return []
    
    def test_connection(self) -> bool:
        """Test connection to the translation service.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            provider = self.get_provider()
            return provider.test_connection()
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
    
    def update_settings(self, settings: Dict[str, Any]):
        """Update translation settings.
        
        Args:
            settings: New translation settings
        """
        # Update settings
        SETTINGS["translation"] = settings
        
        # Clear current provider to force recreation
        self._current_provider = None
        self._provider_instance = None
        
        self.logger.info("Translation settings updated")


# Global instance
_translation_manager = None


def get_translation_manager() -> TranslationManager:
    """Get or create the global TranslationManager instance.
    
    Returns:
        TranslationManager instance
    """
    global _translation_manager
    if _translation_manager is None:
        _translation_manager = TranslationManager()
    return _translation_manager