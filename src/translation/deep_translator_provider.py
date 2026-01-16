"""
Deep Translator provider implementation supporting multiple translation services.
"""

import logging
from typing import List, Tuple, Optional
from deep_translator import GoogleTranslator, DeeplTranslator, MicrosoftTranslator
from deep_translator.exceptions import (
    NotValidLength, 
    RequestError, 
    TooManyRequests,
    LanguageNotSupportedException
)

from .base import BaseTranslationProvider
from utils.exceptions import TranslationError, APIError, RateLimitError
from utils.error_handling import ErrorContext
from utils.resilience import resilient_api_call
from utils.security_decorators import secure_api_call
from settings.settings import SETTINGS


class DeepTranslatorProvider(BaseTranslationProvider):
    """Translation provider using deep-translator library with multiple backends."""
    
    # Language codes and names supported by most providers
    COMMON_LANGUAGES = [
        ("en", "English"),
        ("es", "Spanish"),
        ("fr", "French"),
        ("de", "German"),
        ("it", "Italian"),
        ("pt", "Portuguese"),
        ("ru", "Russian"),
        ("ja", "Japanese"),
        ("ko", "Korean"),
        ("zh-CN", "Chinese (Simplified)"),
        ("zh-TW", "Chinese (Traditional)"),
        ("ar", "Arabic"),
        ("hi", "Hindi"),
        ("tr", "Turkish"),
        ("pl", "Polish"),
        ("nl", "Dutch"),
        ("sv", "Swedish"),
        ("da", "Danish"),
        ("no", "Norwegian"),
        ("fi", "Finnish"),
        ("cs", "Czech"),
        ("hu", "Hungarian"),
        ("el", "Greek"),
        ("he", "Hebrew"),
        ("th", "Thai"),
        ("vi", "Vietnamese"),
        ("id", "Indonesian"),
        ("ms", "Malay"),
        ("ro", "Romanian"),
        ("uk", "Ukrainian"),
        ("bg", "Bulgarian"),
        ("hr", "Croatian"),
        ("sr", "Serbian"),
        ("sk", "Slovak"),
        ("sl", "Slovenian"),
        ("et", "Estonian"),
        ("lv", "Latvian"),
        ("lt", "Lithuanian"),
        ("fa", "Persian"),
        ("ur", "Urdu"),
        ("bn", "Bengali"),
        ("ta", "Tamil"),
        ("te", "Telugu"),
        ("ml", "Malayalam"),
        ("mr", "Marathi"),
        ("gu", "Gujarati"),
        ("kn", "Kannada"),
        ("pa", "Punjabi"),
        ("ne", "Nepali"),
        ("si", "Sinhala"),
        ("my", "Burmese"),
        ("km", "Khmer"),
        ("lo", "Lao"),
        ("ka", "Georgian"),
        ("am", "Amharic"),
        ("sw", "Swahili"),
        ("yo", "Yoruba"),
        ("zu", "Zulu"),
        ("xh", "Xhosa"),
        ("af", "Afrikaans"),
        ("sq", "Albanian"),
        ("eu", "Basque"),
        ("be", "Belarusian"),
        ("bs", "Bosnian"),
        ("ca", "Catalan"),
        ("ceb", "Cebuano"),
        ("ny", "Chichewa"),
        ("co", "Corsican"),
        ("eo", "Esperanto"),
        ("tl", "Filipino"),
        ("fy", "Frisian"),
        ("gl", "Galician"),
        ("ht", "Haitian Creole"),
        ("ha", "Hausa"),
        ("haw", "Hawaiian"),
        ("hmn", "Hmong"),
        ("is", "Icelandic"),
        ("ig", "Igbo"),
        ("ga", "Irish"),
        ("jw", "Javanese"),
        ("kk", "Kazakh"),
        ("ku", "Kurdish"),
        ("ky", "Kyrgyz"),
        ("la", "Latin"),
        ("lb", "Luxembourgish"),
        ("mk", "Macedonian"),
        ("mg", "Malagasy"),
        ("mt", "Maltese"),
        ("mi", "Maori"),
        ("mn", "Mongolian"),
        ("ps", "Pashto"),
        ("sm", "Samoan"),
        ("gd", "Scots Gaelic"),
        ("st", "Sesotho"),
        ("sn", "Shona"),
        ("sd", "Sindhi"),
        ("so", "Somali"),
        ("su", "Sundanese"),
        ("tg", "Tajik"),
        ("tt", "Tatar"),
        ("uz", "Uzbek"),
        ("cy", "Welsh"),
        ("yi", "Yiddish")
    ]
    
    def __init__(self, provider_type: str = "google", api_key: str = ""):
        """Initialize the Deep Translator provider.
        
        Args:
            provider_type: Type of translator backend ('google', 'deepl', 'microsoft')
            api_key: API key for the translation service (required for DeepL and Microsoft)
        """
        super().__init__(api_key)
        self.provider_type = provider_type.lower()
        self._translator = None
        self._initialize_translator()
    
    def _initialize_translator(self):
        """Initialize the appropriate translator based on provider type."""
        try:
            if self.provider_type == "google":
                # Google Translate doesn't require API key
                self._translator = None  # We'll create per-request
            elif self.provider_type == "deepl":
                if not self._check_api_key():
                    raise ValueError("DeepL requires an API key")
                # We'll create per-request with language pairs
            elif self.provider_type == "microsoft":
                if not self._check_api_key():
                    raise ValueError("Microsoft Translator requires an API key")
                # We'll create per-request with language pairs
            else:
                raise ValueError(f"Unsupported provider type: {self.provider_type}")
        except Exception as e:
            self.logger.error(f"Failed to initialize translator: {e}")
            raise
    
    @resilient_api_call(
        max_retries=3,
        initial_delay=1.0,
        backoff_factor=2.0,
        failure_threshold=5,
        recovery_timeout=60
    )
    def _make_translation_call(self, translator, text: str) -> str:
        """Make the actual translation API call.
        
        Args:
            translator: The translator instance
            text: Text to translate
            
        Returns:
            Translated text
            
        Raises:
            APIError: On API failures
        """
        try:
            return translator.translate(text)
        except TooManyRequests as e:
            raise RateLimitError(f"Translation rate limit exceeded: {str(e)}")
        except RequestError as e:
            raise APIError(f"Translation API error: {str(e)}")
        except Exception as e:
            raise APIError(f"Translation failed: {str(e)}")
    
    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text from source to target language.
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            Translated text or empty string if failed
        """
        if not text:
            return ""
        
        try:
            # Create translator instance for this request
            if self.provider_type == "google":
                translator = GoogleTranslator(source=source_lang, target=target_lang)
            elif self.provider_type == "deepl":
                # DeepL uses different language codes
                deepl_source = self._map_to_deepl_code(source_lang)
                deepl_target = self._map_to_deepl_code(target_lang)
                translator = DeeplTranslator(
                    api_key=self.api_key,
                    source=deepl_source,
                    target=deepl_target,
                    use_free_api=True  # Use free API by default
                )
            elif self.provider_type == "microsoft":
                translator = MicrosoftTranslator(
                    api_key=self.api_key,
                    source=source_lang,
                    target=target_lang
                )
            else:
                raise ValueError(f"Unsupported provider: {self.provider_type}")
            
            # Make the translation call
            # For providers that need API keys, use secure call
            if self.provider_type in ["deepl", "microsoft"]:
                # Apply security decorator dynamically
                from functools import wraps
                secure_call = secure_api_call(self.provider_type)(self._make_translation_call)
                result = secure_call(translator, text)
            else:
                # Google doesn't need API key
                result = self._make_translation_call(translator, text)
            
            # Log successful translation
            self.logger.info(f"Translated {len(text)} chars from {source_lang} to {target_lang}")
            
            return result or ""
            
        except (RateLimitError, APIError):
            # Re-raise these as they're already handled
            raise
        except NotValidLength as e:
            ctx = ErrorContext.capture(
                operation="Translate text",
                exception=e,
                error_code="TRANSLATION_TEXT_TOO_LONG",
                provider=self.provider_type,
                text_length=len(text),
                source_lang=source_lang,
                target_lang=target_lang
            )
            ctx.log()
            raise TranslationError(f"Text exceeds maximum length for {self.provider_type}")
        except LanguageNotSupportedException as e:
            ctx = ErrorContext.capture(
                operation="Translate text",
                exception=e,
                error_code="TRANSLATION_LANGUAGE_NOT_SUPPORTED",
                provider=self.provider_type,
                source_lang=source_lang,
                target_lang=target_lang
            )
            ctx.log()
            raise TranslationError(f"Language pair {source_lang}->{target_lang} not supported by {self.provider_type}")
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Translate text",
                exception=e,
                error_code="TRANSLATION_UNEXPECTED_ERROR",
                provider=self.provider_type,
                text_length=len(text),
                source_lang=source_lang,
                target_lang=target_lang
            )
            ctx.log()
            raise TranslationError(f"Translation failed: {str(e)}")
    
    def get_supported_languages(self) -> List[Tuple[str, str]]:
        """Return list of supported languages.
        
        Returns:
            List of (code, name) tuples for supported languages
        """
        if self.provider_type == "deepl":
            # DeepL has more limited language support
            return [
                ("en", "English"),
                ("bg", "Bulgarian"),
                ("cs", "Czech"),
                ("da", "Danish"),
                ("de", "German"),
                ("el", "Greek"),
                ("es", "Spanish"),
                ("et", "Estonian"),
                ("fi", "Finnish"),
                ("fr", "French"),
                ("hu", "Hungarian"),
                ("id", "Indonesian"),
                ("it", "Italian"),
                ("ja", "Japanese"),
                ("ko", "Korean"),
                ("lt", "Lithuanian"),
                ("lv", "Latvian"),
                ("nb", "Norwegian"),
                ("nl", "Dutch"),
                ("pl", "Polish"),
                ("pt", "Portuguese"),
                ("ro", "Romanian"),
                ("ru", "Russian"),
                ("sk", "Slovak"),
                ("sl", "Slovenian"),
                ("sv", "Swedish"),
                ("tr", "Turkish"),
                ("uk", "Ukrainian"),
                ("zh", "Chinese")
            ]
        else:
            # Google and Microsoft support most languages
            return self.COMMON_LANGUAGES
    
    def detect_language(self, text: str) -> Optional[str]:
        """Detect the language of the given text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Language code or None if detection failed
        """
        if not text:
            return None
        
        try:
            if self.provider_type == "google":
                # Google Translate in deep-translator doesn't have built-in detection
                # We'll use a simple approach - try common languages
                # In production, you might want to use a dedicated language detection library
                # like langdetect
                self.logger.warning("Language detection not fully implemented for Google Translate")
                return None
            else:
                # For other providers, use Google for detection
                translator = GoogleTranslator()
                result = translator.detect(text)
                if isinstance(result, list) and result:
                    return result[0].get('language', None)
                elif isinstance(result, str):
                    return result
            
            return None
            
        except Exception as e:
            self.logger.error(f"Language detection failed: {e}")
            return None
    
    def _map_to_deepl_code(self, code: str) -> str:
        """Map common language codes to DeepL-specific codes.
        
        Args:
            code: Standard language code
            
        Returns:
            DeepL-compatible language code
        """
        # DeepL uses some different codes
        deepl_mappings = {
            "zh-CN": "zh",
            "zh-TW": "zh",
            "no": "nb",  # Norwegian
            "pt-BR": "pt-BR",
            "pt-PT": "pt-PT",
            "en-US": "en-US",
            "en-GB": "en-GB",
        }
        
        # Return mapped code or original
        return deepl_mappings.get(code, code)