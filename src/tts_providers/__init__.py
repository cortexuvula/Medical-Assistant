"""TTS (Text-to-Speech) providers module."""

from .base import BaseTTSProvider
from .pyttsx_provider import PyttsxProvider
from .elevenlabs_tts import ElevenLabsTTSProvider
from .google_tts import GoogleTTSProvider

__all__ = [
    'BaseTTSProvider',
    'PyttsxProvider', 
    'ElevenLabsTTSProvider',
    'GoogleTTSProvider'
]