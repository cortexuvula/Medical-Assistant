"""
Translation Manager for handling translation providers.

This module provides the TranslationManager class for handling translation
operations with multiple provider backends. All public methods provide
both exception-based (original) and OperationResult-based (safe) variants
for flexibility in error handling.
"""

import threading
from typing import Optional, Dict, Any, List, Tuple

from translation.base import BaseTranslationProvider
from utils.structured_logging import get_logger
from translation.deep_translator_provider import DeepTranslatorProvider
from settings.settings_manager import settings_manager
from utils.security import get_security_manager
from utils.exceptions import TranslationError
from utils.error_handling import OperationResult


class TranslationManager:
    """Manages translation providers and handles translation operations."""

    def __init__(self) -> None:
        """Initialize the TranslationManager."""
        self.logger = get_logger(__name__)
        self.providers = {
            "deep_translator": DeepTranslatorProvider,
        }
        self._current_provider: Optional[str] = None
        self._provider_instance: Optional[BaseTranslationProvider] = None
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
            translation_settings = settings_manager.get("translation", {})
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
    
    def _create_provider(self, provider_name: str, sub_provider: Optional[str] = None) -> None:
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
    
    def translate(
        self,
        text: str,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None,
        refine_medical: Optional[bool] = None
    ) -> str:
        """Translate text using the current provider.

        Args:
            text: Text to translate
            source_lang: Source language code (if None, will auto-detect)
            target_lang: Target language code (if None, uses settings)
            refine_medical: If True, use LLM to refine medical terminology.
                          If None, uses setting from translation.llm_refinement_enabled

        Returns:
            Translated text (optionally refined for medical accuracy)

        Raises:
            Exception: If translation fails

        Note:
            For non-throwing version, use translate_safe() which returns OperationResult.
        """
        if not text:
            return ""

        try:
            provider = self.get_provider()

            # Get language settings if not provided
            translation_settings = settings_manager.get("translation", {})
            if source_lang is None:
                # Try to detect language
                detected_lang = provider.detect_language(text)
                source_lang = detected_lang or translation_settings.get("patient_language", "es")

            if target_lang is None:
                target_lang = translation_settings.get("doctor_language", "en")

            # Log the actual language codes being used
            self.logger.debug(f"Translation request: source={source_lang}, target={target_lang}, text_length={len(text)}")

            # Perform initial translation (Google/DeepL)
            result = provider.translate(text, source_lang, target_lang)

            self.logger.info(f"Translated text from {source_lang} to {target_lang}")

            # Optional LLM refinement for medical terminology
            if refine_medical is None:
                refine_medical = translation_settings.get("llm_refinement_enabled", False)

            if refine_medical:
                try:
                    from ai.translation_refiner import get_translation_refiner
                    refiner = get_translation_refiner()

                    refinement = refiner.refine_translation(
                        source_text=text,
                        initial_translation=result,
                        source_lang=source_lang,
                        target_lang=target_lang
                    )

                    if refinement.was_refined:
                        self.logger.info(f"LLM refined translation (detected terms: {refinement.medical_terms_detected})")
                        return refinement.refined_translation
                except Exception as e:
                    self.logger.warning(f"LLM refinement failed, using original translation: {e}")

            return result

        except Exception as e:
            self.logger.error(f"Translation failed: {e}")
            raise

    def translate_safe(self, text: str, source_lang: Optional[str] = None, target_lang: Optional[str] = None) -> OperationResult[str]:
        """Translate text using the current provider with OperationResult return type.

        This is the recommended method for new code as it provides structured
        error handling without exceptions.

        Args:
            text: Text to translate
            source_lang: Source language code (if None, will auto-detect)
            target_lang: Target language code (if None, uses settings)

        Returns:
            OperationResult containing translated text on success, or error details on failure

        Example:
            result = manager.translate_safe("Hello")
            if result.success:
                print(result.value)
            else:
                print(f"Error: {result.error}")
        """
        if not text:
            return OperationResult.success("")

        try:
            result = self.translate(text, source_lang, target_lang)
            return OperationResult.success(
                result,
                source_language=source_lang,
                target_language=target_lang
            )
        except Exception as e:
            return OperationResult.failure(
                f"Translation failed: {str(e)}",
                error_code="TRANSLATION_ERROR",
                exception=e,
                source_language=source_lang,
                target_language=target_lang
            )
    
    def detect_language(self, text: str) -> Optional[str]:
        """Detect the language of the given text.

        Args:
            text: Text to analyze

        Returns:
            Language code or None if detection failed

        Note:
            For structured error handling, use detect_language_safe().
        """
        try:
            provider = self.get_provider()
            return provider.detect_language(text)
        except Exception as e:
            self.logger.error(f"Language detection failed: {e}")
            return None

    def detect_language_safe(self, text: str) -> OperationResult[str]:
        """Detect the language of the given text with OperationResult return type.

        Args:
            text: Text to analyze

        Returns:
            OperationResult containing language code on success, or error details on failure
        """
        if not text:
            return OperationResult.failure(
                "Cannot detect language of empty text",
                error_code="EMPTY_TEXT"
            )

        try:
            provider = self.get_provider()
            result = provider.detect_language(text)
            if result:
                return OperationResult.success(result)
            else:
                return OperationResult.failure(
                    "Language detection returned no result",
                    error_code="DETECTION_FAILED"
                )
        except Exception as e:
            return OperationResult.failure(
                f"Language detection failed: {str(e)}",
                error_code="DETECTION_ERROR",
                exception=e
            )

    def get_supported_languages(self) -> List[Tuple[str, str]]:
        """Get list of supported languages for current provider.

        Returns:
            List of (code, name) tuples

        Note:
            For structured error handling, use get_supported_languages_safe().
        """
        try:
            provider = self.get_provider()
            return provider.get_supported_languages()
        except Exception as e:
            self.logger.error(f"Failed to get supported languages: {e}")
            return []

    def get_supported_languages_safe(self) -> OperationResult[List[Tuple[str, str]]]:
        """Get list of supported languages with OperationResult return type.

        Returns:
            OperationResult containing list of (code, name) tuples on success
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
        """Test connection to the translation service.

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
        """Test connection to the translation service with OperationResult return type.

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
    
    def update_settings(self, settings: Dict[str, Any]) -> None:
        """Update translation settings.

        Args:
            settings: New translation settings
        """
        # Update settings
        settings_manager.set("translation", settings)

        # Clear current provider to force recreation
        self._current_provider = None
        self._provider_instance = None

        self.logger.info("Translation settings updated")


# Global instance with thread-safe initialization
_translation_manager = None
_translation_manager_lock = threading.Lock()


def get_translation_manager() -> TranslationManager:
    """Get or create the global TranslationManager instance.

    Thread-safe implementation using double-checked locking pattern.

    Returns:
        TranslationManager instance
    """
    global _translation_manager
    if _translation_manager is None:
        with _translation_manager_lock:
            # Double-check after acquiring lock
            if _translation_manager is None:
                _translation_manager = TranslationManager()
    return _translation_manager