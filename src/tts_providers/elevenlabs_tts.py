"""
ElevenLabs TTS provider implementation.
"""

import logging
import requests
import io
from typing import List, Dict, Optional
from pydub import AudioSegment

from .base import BaseTTSProvider
from utils.exceptions import APIError, RateLimitError, AuthenticationError
from utils.resilience import resilient_api_call
from utils.security_decorators import secure_api_call
from settings.settings import SETTINGS


class ElevenLabsTTSProvider(BaseTTSProvider):
    """TTS provider using ElevenLabs API."""
    
    API_BASE_URL = "https://api.elevenlabs.io/v1"
    
    # Language to model mapping for multilingual support
    # Latest models as of 2024
    TURBO_V2_5 = "eleven_turbo_v2_5"  # Newest, fastest model with low latency
    MULTILINGUAL_V2 = "eleven_multilingual_v2"  # High quality multilingual
    MONOLINGUAL_V1 = "eleven_monolingual_v1"  # Original English model
    
    # Default models for backward compatibility
    MULTILINGUAL_MODEL_ID = MULTILINGUAL_V2
    MONOLINGUAL_MODEL_ID = TURBO_V2_5  # Use Turbo v2.5 as default for English
    
    # Supported languages for multilingual model
    SUPPORTED_LANGUAGES = [
        {"code": "en", "name": "English"},
        {"code": "es", "name": "Spanish"},
        {"code": "fr", "name": "French"},
        {"code": "de", "name": "German"},
        {"code": "it", "name": "Italian"},
        {"code": "pt", "name": "Portuguese"},
        {"code": "pl", "name": "Polish"},
        {"code": "tr", "name": "Turkish"},
        {"code": "ru", "name": "Russian"},
        {"code": "nl", "name": "Dutch"},
        {"code": "cs", "name": "Czech"},
        {"code": "ar", "name": "Arabic"},
        {"code": "zh", "name": "Chinese"},
        {"code": "ja", "name": "Japanese"},
        {"code": "ko", "name": "Korean"},
        {"code": "hi", "name": "Hindi"},
        {"code": "sv", "name": "Swedish"},
        {"code": "da", "name": "Danish"},
        {"code": "fi", "name": "Finnish"},
        {"code": "no", "name": "Norwegian"},
        {"code": "hr", "name": "Croatian"},
        {"code": "uk", "name": "Ukrainian"},
        {"code": "el", "name": "Greek"},
        {"code": "he", "name": "Hebrew"},
        {"code": "ro", "name": "Romanian"},
        {"code": "hu", "name": "Hungarian"},
        {"code": "bg", "name": "Bulgarian"},
        {"code": "id", "name": "Indonesian"},
        {"code": "ms", "name": "Malay"},
        {"code": "vi", "name": "Vietnamese"},
        {"code": "th", "name": "Thai"},
        {"code": "ta", "name": "Tamil"},
        {"code": "te", "name": "Telugu"},
        {"code": "fil", "name": "Filipino"},
    ]
    
    def __init__(self, api_key: str = ""):
        """Initialize the ElevenLabs TTS provider.
        
        Args:
            api_key: ElevenLabs API key
        """
        super().__init__(api_key)
        self._voices_cache = None
        self._default_voice_id = None
    
    @secure_api_call("elevenlabs")
    @resilient_api_call(
        max_retries=3,
        initial_delay=1.0,
        backoff_factor=2.0,
        failure_threshold=5,
        recovery_timeout=60
    )
    def _make_tts_call(self, voice_id: str, text: str, model_id: str, voice_settings: dict) -> bytes:
        """Make the actual TTS API call to ElevenLabs.
        
        Args:
            voice_id: Voice ID to use
            text: Text to synthesize
            model_id: Model ID to use
            voice_settings: Voice settings dictionary
            
        Returns:
            Audio data as bytes
            
        Raises:
            APIError: On API failures
        """
        url = f"{self.API_BASE_URL}/text-to-speech/{voice_id}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        
        data = {
            "text": text,
            "model_id": model_id,
            "voice_settings": voice_settings
        }
        
        # Log API call details
        self.logger.debug(f"ElevenLabs TTS API call to {url}")
        self.logger.debug(f"Model: {model_id}, Voice: {voice_id}")
        
        response = requests.post(url, json=data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            return response.content
        elif response.status_code == 401:
            raise AuthenticationError("Invalid ElevenLabs API key")
        elif response.status_code == 429:
            raise RateLimitError("ElevenLabs rate limit exceeded")
        else:
            raise APIError(f"ElevenLabs API error: {response.status_code} - {response.text}")
    
    def synthesize(self, text: str, language: str = "en", voice: Optional[str] = None, **kwargs) -> AudioSegment:
        """Convert text to speech using ElevenLabs API.
        
        Args:
            text: Text to convert to speech
            language: Language code
            voice: Optional voice ID or name
            **kwargs: Additional parameters (stability, similarity_boost, style, use_speaker_boost)
            
        Returns:
            AudioSegment containing the synthesized speech
        """
        if not self._check_api_key():
            raise AuthenticationError("ElevenLabs API key not configured")
        
        if not text:
            raise ValueError("Text cannot be empty")
        
        try:
            # Get voice ID
            if voice:
                self.logger.info(f"Using provided voice: {voice}")
                voice_id = self._resolve_voice_id(voice)
            else:
                self.logger.info(f"Getting default voice for language: {language}")
                voice_id = self._get_default_voice_for_language(language)
            
            self.logger.info(f"Resolved voice ID: {voice_id}")
            
            if not voice_id:
                raise ValueError(f"No suitable voice found for language: {language}")
            
            # Get model from settings or kwargs
            tts_settings = SETTINGS.get("tts", {})
            
            # Check for model in kwargs first, then settings, then use defaults
            if "model_id" in kwargs:
                model_id = kwargs["model_id"]
            elif "elevenlabs_model" in tts_settings:
                model_id = tts_settings["elevenlabs_model"]
            else:
                # Default based on language
                if language == "en":
                    model_id = self.MONOLINGUAL_MODEL_ID
                else:
                    model_id = self.MULTILINGUAL_MODEL_ID
            
            # Get voice settings from kwargs or use defaults
            voice_settings = {
                "stability": kwargs.get("stability", 0.5),
                "similarity_boost": kwargs.get("similarity_boost", 0.75),
                "style": kwargs.get("style", 0.0),
                "use_speaker_boost": kwargs.get("use_speaker_boost", True)
            }
            
            # Make API call
            audio_data = self._make_tts_call(voice_id, text, model_id, voice_settings)
            
            # Convert to AudioSegment
            audio = AudioSegment.from_mp3(io.BytesIO(audio_data))
            
            self.logger.info(f"Synthesized {len(text)} characters using voice {voice_id}")
            return audio
            
        except (AuthenticationError, RateLimitError, APIError):
            # Re-raise API errors
            raise
        except Exception as e:
            self.logger.error(f"TTS synthesis failed: {e}")
            raise APIError(f"Failed to synthesize speech: {str(e)}")
    
    def get_available_voices(self, language: str = None) -> List[Dict[str, str]]:
        """Get available voices from ElevenLabs API.
        
        Args:
            language: Optional language code to filter voices
            
        Returns:
            List of voice dictionaries
        """
        if not self._check_api_key():
            return []
        
        # Use cache if available
        if self._voices_cache is not None:
            voices = self._voices_cache
        else:
            voices = self._fetch_voices()
            self._voices_cache = voices
        
        # Filter by language if specified
        if language:
            # ElevenLabs doesn't provide language info per voice,
            # so we return all voices and note they support multiple languages
            pass
        
        return voices
    
    def get_supported_languages(self) -> List[Dict[str, str]]:
        """Get list of supported languages.
        
        Returns:
            List of language dictionaries
        """
        return self.SUPPORTED_LANGUAGES.copy()
    
    def _fetch_voices(self) -> List[Dict[str, str]]:
        """Fetch available voices from ElevenLabs API.
        
        Returns:
            List of voice dictionaries
        """
        try:
            url = f"{self.API_BASE_URL}/voices"
            headers = {
                "Accept": "application/json",
                "xi-api-key": self.api_key
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                self.logger.error(f"Failed to fetch voices: {response.status_code}")
                return []
            
            voices_data = response.json()
            voices = []
            
            for voice in voices_data.get("voices", []):
                voice_info = {
                    "id": voice["voice_id"],
                    "name": voice["name"],
                    "language": "multilingual",  # ElevenLabs voices support multiple languages
                    "gender": self._guess_gender_from_labels(voice.get("labels", {})),
                    "description": voice.get("description", "")
                }
                
                # Add category info if available
                if voice.get("category"):
                    voice_info["description"] = f"{voice['category']} - {voice_info['description']}"
                
                voices.append(voice_info)
            
            return voices
            
        except Exception as e:
            self.logger.error(f"Error fetching voices: {e}")
            return []
    
    def _resolve_voice_id(self, voice_identifier: str) -> Optional[str]:
        """Resolve voice name or ID to voice ID.
        
        Args:
            voice_identifier: Voice ID or name
            
        Returns:
            Voice ID or None if not found
        """
        # If it looks like an ID (long string), return as is
        # ElevenLabs voice IDs are typically 20+ characters
        if len(voice_identifier) >= 20:
            return voice_identifier
        
        # Otherwise, try to find by name
        voices = self.get_available_voices()
        
        for voice in voices:
            if voice["name"].lower() == voice_identifier.lower():
                return voice["id"]
        
        # Try partial match
        for voice in voices:
            if voice_identifier.lower() in voice["name"].lower():
                return voice["id"]
        
        return None
    
    def _get_default_voice_for_language(self, language: str) -> Optional[str]:
        """Get a default voice for the given language.
        
        Args:
            language: Language code
            
        Returns:
            Voice ID or None
        """
        # Check if we have a default voice ID set
        if self._default_voice_id:
            self.logger.info(f"Using default voice ID: {self._default_voice_id}")
            return self._default_voice_id
        
        # Get voice from settings
        from settings.settings import SETTINGS
        tts_settings = SETTINGS.get("tts", {})
        voice_id = tts_settings.get("voice", None)
        
        self.logger.info(f"Voice from settings: {voice_id}")
        
        if voice_id:
            return voice_id
        
        # Get all voices
        voices = self.get_available_voices()
        
        if not voices:
            return None
        
        # Try to find a voice with appropriate accent/label
        language_preferences = {
            "en": ["american", "british", "english"],
            "es": ["spanish", "mexican"],
            "fr": ["french"],
            "de": ["german"],
            "it": ["italian"],
            "pt": ["portuguese", "brazilian"],
            "ja": ["japanese"],
            "ko": ["korean"],
            "zh": ["chinese", "mandarin"],
            "hi": ["hindi", "indian"],
            "ar": ["arabic"]
        }
        
        preferences = language_preferences.get(language, [])
        
        # Search for preferred voice
        for voice in voices:
            voice_lower = voice["name"].lower()
            desc_lower = voice.get("description", "").lower()
            
            for pref in preferences:
                if pref in voice_lower or pref in desc_lower:
                    self._default_voice_id = voice["id"]
                    return voice["id"]
        
        # Fall back to first voice
        self._default_voice_id = voices[0]["id"]
        return self._default_voice_id
    
    def _guess_gender_from_labels(self, labels: dict) -> str:
        """Guess gender from voice labels.
        
        Args:
            labels: Voice labels dictionary
            
        Returns:
            'male', 'female', or 'neutral'
        """
        # Check for gender in labels
        if labels.get("gender") == "male":
            return "male"
        elif labels.get("gender") == "female":
            return "female"
        
        # Check accent label which sometimes includes gender
        accent = labels.get("accent", "").lower()
        if "female" in accent or "woman" in accent:
            return "female"
        elif "male" in accent or "man" in accent:
            return "male"
        
        return "neutral"