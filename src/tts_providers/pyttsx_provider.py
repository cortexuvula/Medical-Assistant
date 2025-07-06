"""
Pyttsx3 TTS provider for offline text-to-speech synthesis.
"""

import logging
import pyttsx3
import tempfile
import os
from typing import List, Dict, Optional
from pydub import AudioSegment
import threading

from .base import BaseTTSProvider
from settings.settings import SETTINGS


class PyttsxProvider(BaseTTSProvider):
    """Offline TTS provider using pyttsx3."""
    
    # Common language mappings
    LANGUAGE_MAPPINGS = {
        "en": "english",
        "es": "spanish", 
        "fr": "french",
        "de": "german",
        "it": "italian",
        "pt": "portuguese",
        "ru": "russian",
        "ja": "japanese",
        "ko": "korean",
        "zh": "chinese",
        "zh-CN": "chinese",
        "zh-TW": "chinese",
        "ar": "arabic",
        "hi": "hindi",
        "tr": "turkish",
        "pl": "polish",
        "nl": "dutch",
        "sv": "swedish",
        "da": "danish",
        "no": "norwegian",
        "fi": "finnish"
    }
    
    def __init__(self, api_key: str = ""):
        """Initialize the pyttsx3 provider.
        
        Args:
            api_key: Not used for offline TTS
        """
        super().__init__(api_key)
        self._engine = None
        self._lock = threading.Lock()  # Thread safety for engine access
        self._initialize_engine()
    
    def _initialize_engine(self):
        """Initialize the pyttsx3 engine with settings."""
        try:
            with self._lock:
                self._engine = pyttsx3.init()
                
                # Get TTS settings
                tts_settings = SETTINGS.get("tts", {})
                
                # Set voice properties
                rate = tts_settings.get("rate", 150)
                volume = tts_settings.get("volume", 1.0)
                
                self._engine.setProperty('rate', rate)
                self._engine.setProperty('volume', volume)
                
                # Try to set a default voice based on system
                voices = self._engine.getProperty('voices')
                if voices and tts_settings.get("voice", "default") != "default":
                    voice_id = tts_settings.get("voice")
                    # Try to find the voice by ID
                    for voice in voices:
                        if voice.id == voice_id:
                            self._engine.setProperty('voice', voice.id)
                            break
                
                self.logger.info("Pyttsx3 engine initialized successfully")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize pyttsx3 engine: {e}")
            raise
    
    def synthesize(self, text: str, language: str = "en", voice: Optional[str] = None, **kwargs) -> AudioSegment:
        """Convert text to speech and return AudioSegment.
        
        Args:
            text: Text to convert to speech
            language: Language code (limited support based on system voices)
            voice: Optional voice ID to use
            **kwargs: Additional parameters (rate, volume)
            
        Returns:
            AudioSegment containing the synthesized speech
        """
        if not text:
            raise ValueError("Text cannot be empty")
        
        # Create temporary file for audio output
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp:
                temp_file = temp.name
            
            with self._lock:
                # Apply any runtime settings
                if 'rate' in kwargs:
                    self._engine.setProperty('rate', kwargs['rate'])
                if 'volume' in kwargs:
                    self._engine.setProperty('volume', kwargs['volume'])
                
                # Set voice if specified
                if voice:
                    voices = self._engine.getProperty('voices')
                    for v in voices:
                        if v.id == voice or voice in v.name:
                            self._engine.setProperty('voice', v.id)
                            break
                else:
                    # Try to select voice based on language
                    self._set_voice_for_language(language)
                
                # Save to file
                self._engine.save_to_file(text, temp_file)
                self._engine.runAndWait()
            
            # Load the audio file
            audio = AudioSegment.from_wav(temp_file)
            
            self.logger.info(f"Synthesized {len(text)} characters of text")
            return audio
            
        except Exception as e:
            self.logger.error(f"Synthesis failed: {e}")
            raise
        finally:
            # Clean up temp file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    pass
    
    def get_available_voices(self, language: str = None) -> List[Dict[str, str]]:
        """Get available voices from the system.
        
        Args:
            language: Optional language code to filter voices
            
        Returns:
            List of voice dictionaries
        """
        voices = []
        
        try:
            with self._lock:
                system_voices = self._engine.getProperty('voices')
                
                for voice in system_voices:
                    # Extract voice info
                    voice_info = {
                        'id': voice.id,
                        'name': voice.name,
                        'language': self._extract_language_from_voice(voice),
                        'gender': self._extract_gender_from_voice(voice),
                        'description': f"{voice.name} ({voice.id})"
                    }
                    
                    # Filter by language if specified
                    if language is None or voice_info['language'].startswith(language):
                        voices.append(voice_info)
            
            return voices
            
        except Exception as e:
            self.logger.error(f"Failed to get voices: {e}")
            return []
    
    def get_supported_languages(self) -> List[Dict[str, str]]:
        """Get languages supported by available system voices.
        
        Returns:
            List of language dictionaries
        """
        languages = {}
        
        try:
            # Get all available voices
            voices = self.get_available_voices()
            
            # Extract unique languages
            for voice in voices:
                lang_code = voice['language'].split('-')[0] if voice['language'] else 'unknown'
                if lang_code not in languages and lang_code != 'unknown':
                    # Try to get a friendly name
                    lang_name = self._get_language_name(lang_code)
                    languages[lang_code] = {
                        'code': lang_code,
                        'name': lang_name
                    }
            
            # Always include English as it's typically available
            if 'en' not in languages:
                languages['en'] = {'code': 'en', 'name': 'English'}
            
            return list(languages.values())
            
        except Exception as e:
            self.logger.error(f"Failed to get supported languages: {e}")
            # Return minimal set
            return [
                {'code': 'en', 'name': 'English'}
            ]
    
    def _set_voice_for_language(self, language: str):
        """Try to set an appropriate voice for the given language.
        
        Args:
            language: Language code
        """
        try:
            voices = self._engine.getProperty('voices')
            
            # First try exact match
            for voice in voices:
                voice_lang = self._extract_language_from_voice(voice)
                if voice_lang.startswith(language):
                    self._engine.setProperty('voice', voice.id)
                    self.logger.info(f"Set voice {voice.name} for language {language}")
                    return
            
            # Try to find by language name in voice
            lang_name = self._get_language_name(language)
            for voice in voices:
                if lang_name.lower() in voice.name.lower():
                    self._engine.setProperty('voice', voice.id)
                    self.logger.info(f"Set voice {voice.name} for language {language}")
                    return
            
            self.logger.warning(f"No voice found for language {language}, using default")
            
        except Exception as e:
            self.logger.error(f"Failed to set voice for language: {e}")
    
    def _extract_language_from_voice(self, voice) -> str:
        """Extract language code from voice object.
        
        Args:
            voice: pyttsx3 voice object
            
        Returns:
            Language code or 'unknown'
        """
        # Different TTS engines store language differently
        if hasattr(voice, 'languages') and voice.languages:
            return voice.languages[0]
        elif hasattr(voice, 'id'):
            # Try to extract from ID (e.g., "HKEY_LOCAL_MACHINE\\SOFTWARE\\...\\en-US")
            id_parts = voice.id.split('\\')
            for part in id_parts:
                if '-' in part and len(part) <= 10:  # Likely a language code
                    return part
        
        # Try to guess from name
        name_lower = voice.name.lower()
        for code, name in self.LANGUAGE_MAPPINGS.items():
            if name in name_lower:
                return code
        
        return 'unknown'
    
    def _extract_gender_from_voice(self, voice) -> str:
        """Extract gender from voice object.
        
        Args:
            voice: pyttsx3 voice object
            
        Returns:
            'male', 'female', or 'neutral'
        """
        if hasattr(voice, 'gender'):
            return voice.gender.lower()
        
        # Try to guess from name
        name_lower = voice.name.lower()
        if any(word in name_lower for word in ['female', 'woman', 'girl', 'zira', 'hazel', 'susan']):
            return 'female'
        elif any(word in name_lower for word in ['male', 'man', 'boy', 'david', 'mark', 'george']):
            return 'male'
        
        return 'neutral'
    
    def _get_language_name(self, code: str) -> str:
        """Get friendly language name from code.
        
        Args:
            code: Language code
            
        Returns:
            Language name
        """
        language_names = {
            'en': 'English',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'it': 'Italian',
            'pt': 'Portuguese',
            'ru': 'Russian',
            'ja': 'Japanese',
            'ko': 'Korean',
            'zh': 'Chinese',
            'ar': 'Arabic',
            'hi': 'Hindi',
            'tr': 'Turkish',
            'pl': 'Polish',
            'nl': 'Dutch',
            'sv': 'Swedish',
            'da': 'Danish',
            'no': 'Norwegian',
            'fi': 'Finnish'
        }
        
        return language_names.get(code, code.upper())