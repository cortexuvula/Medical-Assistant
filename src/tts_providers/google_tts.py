"""
Google Text-to-Speech (gTTS) provider implementation.
"""

import logging
import io
from typing import List, Dict, Optional
from gtts import gTTS, lang
from pydub import AudioSegment

from .base import BaseTTSProvider
from utils.exceptions import APIError


class GoogleTTSProvider(BaseTTSProvider):
    """TTS provider using Google Text-to-Speech (gTTS)."""
    
    def __init__(self, api_key: str = ""):
        """Initialize the Google TTS provider.
        
        Args:
            api_key: Not required for gTTS (uses free API)
        """
        super().__init__(api_key)
        self._supported_languages = None
    
    def synthesize(self, text: str, language: str = "en", voice: Optional[str] = None, **kwargs) -> AudioSegment:
        """Convert text to speech using Google TTS.
        
        Args:
            text: Text to convert to speech
            language: Language code (e.g., 'en', 'es', 'fr')
            voice: Not used for gTTS (single voice per language)
            **kwargs: Additional parameters (slow, tld)
            
        Returns:
            AudioSegment containing the synthesized speech
        """
        if not text:
            raise ValueError("Text cannot be empty")
        
        try:
            # Map language codes to gTTS format
            gtts_lang = self._map_language_code(language)
            
            # Check if language is supported
            if not self._is_language_supported(gtts_lang):
                raise ValueError(f"Language '{language}' is not supported by Google TTS")
            
            # Get additional parameters
            slow = kwargs.get("slow", False)
            tld = kwargs.get("tld", "com")  # Top-level domain for accent variation
            
            # Create gTTS object
            tts = gTTS(text=text, lang=gtts_lang, slow=slow, tld=tld)
            
            # Save to BytesIO
            audio_buffer = io.BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_buffer.seek(0)
            
            # Convert to AudioSegment
            audio = AudioSegment.from_mp3(audio_buffer)
            
            self.logger.info(f"Synthesized {len(text)} characters in {language}")
            return audio
            
        except Exception as e:
            self.logger.error(f"Google TTS synthesis failed: {e}")
            raise APIError(f"Failed to synthesize speech: {str(e)}")
    
    def get_available_voices(self, language: str = None) -> List[Dict[str, str]]:
        """Get available voices for Google TTS.
        
        Note: gTTS has one voice per language, so this returns language info.
        
        Args:
            language: Optional language code to filter
            
        Returns:
            List of voice dictionaries
        """
        voices = []
        
        # Get supported languages
        supported_langs = self.get_supported_languages()
        
        for lang_info in supported_langs:
            if language is None or lang_info["code"].startswith(language):
                # Create voice entry for each language/accent combination
                voice_info = {
                    "id": lang_info["code"],
                    "name": f"Google {lang_info['name']}",
                    "language": lang_info["code"],
                    "gender": "neutral",  # gTTS doesn't specify gender
                    "description": f"Google Text-to-Speech voice for {lang_info['name']}"
                }
                voices.append(voice_info)
        
        return voices
    
    def get_supported_languages(self) -> List[Dict[str, str]]:
        """Get list of languages supported by Google TTS.
        
        Returns:
            List of language dictionaries
        """
        if self._supported_languages is not None:
            return self._supported_languages
        
        try:
            # Get all supported languages from gTTS
            gtts_languages = lang.tts_langs()
            
            languages = []
            for code, name in gtts_languages.items():
                languages.append({
                    "code": code,
                    "name": name
                })
            
            # Sort by name
            languages.sort(key=lambda x: x["name"])
            
            # Cache the result
            self._supported_languages = languages
            
            return languages
            
        except Exception as e:
            self.logger.error(f"Failed to get supported languages: {e}")
            # Return basic set
            return [
                {"code": "en", "name": "English"},
                {"code": "es", "name": "Spanish"},
                {"code": "fr", "name": "French"},
                {"code": "de", "name": "German"},
                {"code": "it", "name": "Italian"},
                {"code": "pt", "name": "Portuguese"},
                {"code": "ru", "name": "Russian"},
                {"code": "ja", "name": "Japanese"},
                {"code": "ko", "name": "Korean"},
                {"code": "zh", "name": "Chinese"}
            ]
    
    def _map_language_code(self, code: str) -> str:
        """Map common language codes to gTTS codes.
        
        Args:
            code: Language code
            
        Returns:
            gTTS-compatible language code
        """
        # Common mappings
        mappings = {
            "zh": "zh-CN",      # Chinese defaults to Simplified
            "zh-Hans": "zh-CN", # Simplified Chinese
            "zh-Hant": "zh-TW", # Traditional Chinese
            "pt": "pt",         # Portuguese (can also use pt-BR)
            "no": "no",         # Norwegian
            "nb": "no",         # Norwegian Bokmål
            "nn": "no",         # Norwegian Nynorsk
        }
        
        return mappings.get(code, code)
    
    def _is_language_supported(self, language: str) -> bool:
        """Check if a language is supported.
        
        Args:
            language: Language code
            
        Returns:
            True if supported, False otherwise
        """
        try:
            supported = lang.tts_langs()
            return language in supported
        except (RuntimeError, ValueError, ConnectionError):
            # Fallback check when language list unavailable
            common_langs = ["en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh-CN", "ar", "hi"]
            return language in common_langs