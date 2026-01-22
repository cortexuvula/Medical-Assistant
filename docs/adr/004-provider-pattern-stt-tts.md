# ADR-004: Provider Pattern for STT/TTS Services

## Status

Accepted

## Date

2024-03

## Context

Medical Assistant requires speech-to-text (STT) for transcribing clinical encounters and text-to-speech (TTS) for reading back generated content. The application needs to:

- Support multiple STT providers (Deepgram, Groq, ElevenLabs, local Whisper)
- Support multiple TTS providers (ElevenLabs, system TTS)
- Allow users to choose providers based on accuracy, speed, cost, and privacy preferences
- Switch providers without code changes (configuration-driven)
- Handle provider-specific features (medical vocabulary, speaker diarization)
- Gracefully handle provider failures with fallbacks

## Decision

We implemented a **Provider Pattern** with abstract base classes and provider-specific implementations.

```
src/stt_providers/
├── base.py              # BaseSTTProvider abstract class
├── deepgram.py          # Deepgram (nova-2-medical)
├── groq.py              # Groq (whisper-large-v3-turbo)
├── elevenlabs.py        # ElevenLabs (scribe_v1)
└── whisper.py           # Local Whisper (turbo model)

src/tts_providers/
├── base.py              # BaseTTSProvider abstract class
└── elevenlabs_tts.py    # ElevenLabs TTS
```

### Interface Contract

```python
class BaseSTTProvider(ABC):
    @abstractmethod
    def transcribe(self, audio: AudioSegment) -> str:
        """Transcribe audio to text."""
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Test API connectivity."""
        pass
```

## Consequences

### Positive

- **Flexibility**: Users choose the best provider for their needs
- **No vendor lock-in**: Easy to add or remove providers
- **Consistent interface**: UI code doesn't care which provider is active
- **Testability**: Mock providers for unit tests
- **Graceful degradation**: Fall back to local Whisper if cloud APIs fail
- **Feature parity**: All providers implement the same core interface
- **Configuration-driven**: Provider selection via settings.json, no code changes

### Negative

- **Lowest common denominator**: Advanced features (diarization, word timestamps) not universally available
- **Testing burden**: Each provider needs integration tests
- **Documentation**: Must document provider-specific settings and quirks
- **SDK management**: Multiple SDKs with different versioning (deepgram-sdk, elevenlabs, openai-whisper)

### Neutral

- Provider-specific settings stored in separate config sections
- Some providers require API keys, others (Whisper) run locally

## Provider Comparison

### STT Providers

| Provider | Model | Speed | Accuracy | Cost | Medical Vocab | Offline |
|----------|-------|-------|----------|------|---------------|---------|
| Deepgram | nova-2-medical | Fast | High | $$ | Excellent | No |
| Groq | whisper-large-v3-turbo | Very Fast | High | $ | Good | No |
| ElevenLabs | scribe_v1 | Medium | High | $$ | Good | No |
| Whisper | turbo | Slow | High | Free | Good | Yes |

### TTS Providers

| Provider | Models | Latency | Quality | Cost |
|----------|--------|---------|---------|------|
| ElevenLabs | Flash v2.5, Turbo v2.5, Multilingual v2 | Low-Medium | Excellent | $$ |

## Alternatives Considered

### Single Provider (Deepgram Only)

**Rejected because:**
- No offline fallback
- Users locked into one pricing model
- No choice for privacy-conscious users

### Direct API Calls (No Abstraction)

**Rejected because:**
- Code duplication across providers
- Harder to add new providers
- Provider-specific code scattered throughout codebase
- No consistent error handling

### Third-Party Abstraction (SpeechRecognition library)

**Rejected because:**
- Limited provider support
- Less control over provider-specific features
- Additional dependency with its own update cycle
- Medical vocabulary support varies

## Implementation Details

### Provider Selection Flow

```python
# In settings.json
{
    "stt_provider": "groq",  # or "deepgram", "elevenlabs", "whisper"
    "groq": {
        "model": "whisper-large-v3-turbo",
        "language": "en"
    }
}

# In code
from stt_providers import get_stt_provider
provider = get_stt_provider()  # Returns configured provider instance
transcript = provider.transcribe(audio_segment)
```

### Error Handling

```python
try:
    transcript = provider.transcribe(audio)
except ConnectionError:
    # Fall back to local Whisper
    fallback = WhisperProvider()
    transcript = fallback.transcribe(audio)
except RateLimitError:
    # Queue for retry or notify user
    pass
```

### Provider-Specific Features

While the base interface is minimal, providers can expose additional capabilities:

```python
# Deepgram-specific
class DeepgramProvider(BaseSTTProvider):
    def transcribe_with_diarization(self, audio) -> dict:
        """Returns transcript with speaker labels."""
        pass

# Groq-specific
class GroqProvider(BaseSTTProvider):
    def transcribe_with_timestamps(self, audio) -> list:
        """Returns word-level timestamps."""
        pass
```

## References

- [src/stt_providers/](../../src/stt_providers/) - STT implementations
- [src/tts_providers/](../../src/tts_providers/) - TTS implementations
- [Deepgram Nova-2 Medical](https://deepgram.com/product/nova-2)
- [Groq Whisper](https://groq.com/)
- [ElevenLabs](https://elevenlabs.io/)
- [OpenAI Whisper](https://github.com/openai/whisper)
