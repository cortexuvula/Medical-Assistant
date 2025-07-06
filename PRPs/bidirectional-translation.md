# PRP: Bidirectional Translation Feature

## Overview
Implement a bidirectional translation system for medical consultations with non-English speaking patients. The system will:
1. Capture patient speech in their native language via STT
2. Translate to English for the doctor
3. Accept doctor's typed response in English
4. Translate to patient's language
5. Generate TTS audio and play to patient

## Context and Research

### Existing Patterns to Follow
- **Provider Pattern**: Follow the STT provider pattern at `src/stt_providers/base.py:10-45`
- **Dialog Pattern**: Follow medication dialog pattern at `src/ui/dialogs/medication_analysis_dialog.py:14-100`
- **Settings Integration**: Follow Deepgram settings pattern at `src/ui/dialogs/dialogs.py:1693-1792`
- **API Key Management**: Use existing security manager at `src/utils/security.py`
- **UI Button Integration**: Add to Generate tab following pattern at `src/ui/workflow_ui.py:500-514`

### External APIs Documentation
- **Translation**: https://pypi.org/project/deep-translator/ (supports multiple providers)
- **DeepL Official**: https://developers.deepl.com/docs
- **TTS - ElevenLabs**: https://docs.elevenlabs.io/api-reference/text-to-speech
- **TTS - Google Cloud**: https://cloud.google.com/text-to-speech/docs/libraries
- **TTS - pyttsx3 (offline)**: https://pypi.org/project/pyttsx3/

### Key Libraries to Install
```bash
pip install deep-translator  # Translation support
pip install pyttsx3         # Offline TTS
pip install gtts           # Google TTS
```

## Implementation Blueprint

### Phase 1: Translation Provider Infrastructure

#### 1.1 Create Base Translation Provider
```python
# src/translation_providers/base.py
from abc import ABC, abstractmethod
from typing import List, Tuple

class BaseTranslationProvider(ABC):
    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text from source to target language."""
        pass
    
    @abstractmethod
    def get_supported_languages(self) -> List[Tuple[str, str]]:
        """Return list of (code, name) tuples for supported languages."""
        pass
```

#### 1.2 Implement Translation Providers
```python
# src/translation_providers/deep_translator_provider.py
from deep_translator import GoogleTranslator, DeeplTranslator
from .base import BaseTranslationProvider

class DeepTranslatorProvider(BaseTranslationProvider):
    def __init__(self, provider_type: str = "google", api_key: str = ""):
        super().__init__(api_key)
        self.provider_type = provider_type
        
    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        # Implementation using deep-translator
        if self.provider_type == "google":
            translator = GoogleTranslator(source=source_lang, target=target_lang)
        elif self.provider_type == "deepl":
            translator = DeeplTranslator(api_key=self.api_key, 
                                       source=source_lang, 
                                       target=target_lang)
        return translator.translate(text)
```

### Phase 2: TTS Provider Infrastructure

#### 2.1 Create Base TTS Provider
```python
# src/tts_providers/base.py
from abc import ABC, abstractmethod
from pydub import AudioSegment

class BaseTTSProvider(ABC):
    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def synthesize(self, text: str, language: str = "en") -> AudioSegment:
        """Convert text to speech and return AudioSegment."""
        pass
    
    @abstractmethod
    def get_available_voices(self, language: str) -> List[dict]:
        """Get available voices for a language."""
        pass
```

#### 2.2 Implement TTS Providers
```python
# src/tts_providers/elevenlabs_tts.py
class ElevenLabsTTSProvider(BaseTTSProvider):
    def synthesize(self, text: str, language: str = "en") -> AudioSegment:
        # Use existing ElevenLabs integration
        # Call their TTS API endpoint
        pass

# src/tts_providers/pyttsx_provider.py  
class PyttsxProvider(BaseTTSProvider):
    def synthesize(self, text: str, language: str = "en") -> AudioSegment:
        # Offline TTS using pyttsx3
        engine = pyttsx3.init()
        # Configure and generate audio
        pass
```

### Phase 3: Translation Dialog UI

#### 3.1 Create Translation Dialog
```python
# src/ui/dialogs/translation_dialog.py
class TranslationDialog:
    def __init__(self, parent, stt_provider, translation_provider, tts_provider):
        self.parent = parent
        self.stt_provider = stt_provider
        self.translation_provider = translation_provider
        self.tts_provider = tts_provider
        self.is_recording = False
        
    def show(self):
        # Create dialog window
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Bidirectional Translation")
        
        # Language selection dropdowns
        # Patient language selector
        # Doctor language (default English)
        
        # Patient section (top half)
        # - Record button for patient speech
        # - Patient speech text area (original language)
        # - Translated text area (English for doctor)
        
        # Doctor section (bottom half)  
        # - Text input for doctor's response
        # - Translated response (patient's language)
        # - Play TTS button
```

### Phase 4: Integration

#### 4.1 Add to Generate Tab
```python
# In src/ui/workflow_ui.py _create_generate_tab method, add:
{
    "name": "translation",
    "text": "Translation Assistant",
    "description": "Real-time bidirectional translation for patient communication",
    "command": command_map.get("open_translation"),
    "bootstyle": "info"
}
```

#### 4.2 Wire Command in App
```python
# In src/core/app.py create_widgets method, add to command_map:
"open_translation": self.open_translation_dialog

# Add method:
def open_translation_dialog(self):
    from ui.dialogs.translation_dialog import TranslationDialog
    dialog = TranslationDialog(
        self,
        stt_provider=self.audio_handler.get_stt_provider(),
        translation_provider=self.translation_manager.get_provider(),
        tts_provider=self.tts_manager.get_provider()
    )
    dialog.show()
```

#### 4.3 Add Settings
```python
# In settings.json default settings:
"translation": {
    "provider": "deep_translator",
    "sub_provider": "google",  # google, deepl, microsoft
    "patient_language": "es",  # Spanish default
    "doctor_language": "en"
},
"tts": {
    "provider": "pyttsx3",  # offline by default
    "voice": "default",
    "rate": 150,
    "volume": 1.0
}
```

### Phase 5: Manager Classes

#### 5.1 Translation Manager
```python
# src/managers/translation_manager.py
class TranslationManager:
    def __init__(self):
        self.providers = {
            "deep_translator": DeepTranslatorProvider,
            "deepl": DeepLProvider,
            # Add more providers
        }
        
    def get_provider(self) -> BaseTranslationProvider:
        provider_name = SETTINGS.get("translation", {}).get("provider")
        # Return configured provider instance
```

#### 5.2 TTS Manager
```python
# src/managers/tts_manager.py  
class TTSManager:
    def __init__(self):
        self.providers = {
            "pyttsx3": PyttsxProvider,
            "elevenlabs": ElevenLabsTTSProvider,
            "google": GoogleTTSProvider
        }
        
    def get_provider(self) -> BaseTTSProvider:
        provider_name = SETTINGS.get("tts", {}).get("provider")
        # Return configured provider instance
```

## Implementation Tasks

1. **Create Provider Infrastructure** [Priority: High]
   - [ ] Create translation provider base class and implementations
   - [ ] Create TTS provider base class and implementations
   - [ ] Add provider directories to project structure

2. **Build Translation Dialog** [Priority: High]  
   - [ ] Create TranslationDialog class with UI layout
   - [ ] Implement recording controls for patient speech
   - [ ] Add language selection dropdowns
   - [ ] Create text areas for original/translated content
   - [ ] Add TTS playback controls

3. **Integrate Providers** [Priority: High]
   - [ ] Create TranslationManager and TTSManager
   - [ ] Add API key management for new services
   - [ ] Update security configuration

4. **UI Integration** [Priority: Medium]
   - [ ] Add Translation button to Generate tab
   - [ ] Wire command in app.py
   - [ ] Create settings dialogs for providers

5. **Settings & Configuration** [Priority: Medium]
   - [ ] Add default settings to settings.json
   - [ ] Create provider settings dialogs
   - [ ] Add language pair configuration

6. **Testing & Polish** [Priority: Low]
   - [ ] Test with multiple language pairs
   - [ ] Add error handling for API failures
   - [ ] Optimize audio playback
   - [ ] Add usage logging

## Validation Gates

```bash
# Syntax and style check
ruff check --fix src/

# Type checking
mypy src/

# Run tests
pytest tests/unit/test_translation_providers.py -v
pytest tests/unit/test_tts_providers.py -v
pytest tests/integration/test_translation_dialog.py -v

# Manual testing checklist
# 1. Record Spanish speech → English translation appears
# 2. Type English response → Spanish translation appears  
# 3. Click Play → Spanish TTS audio plays
# 4. Test language switching
# 5. Test provider switching
# 6. Test offline mode (pyttsx3)
```

## Error Handling Strategy

1. **Network Failures**: Fall back to offline providers (pyttsx3)
2. **API Limits**: Queue and retry with exponential backoff
3. **Unsupported Languages**: Show clear error message with supported languages
4. **Audio Playback Issues**: Provide download option as fallback

## Security Considerations

1. Store API keys encrypted using existing security manager
2. Sanitize all text inputs before sending to APIs
3. Rate limit API calls to prevent abuse
4. Clear translation history on session end

## Success Metrics

- One-pass implementation using this PRP
- Clean integration with existing codebase patterns
- All validation gates pass
- Feature works offline with pyttsx3

## Confidence Score: 8/10

High confidence due to:
- Clear existing patterns to follow
- Well-documented external APIs
- Modular design allowing incremental implementation
- Fallback options for offline use

Lower confidence areas:
- Audio playback synchronization 
- Real-time translation performance
- Language detection accuracy

## Next Steps

1. Install required dependencies
2. Create provider directories and base classes
3. Implement simplest provider first (pyttsx3 for offline TTS)
4. Build basic dialog UI
5. Iterate on features