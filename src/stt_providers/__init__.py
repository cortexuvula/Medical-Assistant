"""
Speech-to-Text (STT) providers package.

This package provides a unified interface for speech-to-text transcription
using various providers (Deepgram, ElevenLabs, Groq, local Whisper).

Usage:
    from stt_providers import DeepgramProvider, TranscriptionResult

    provider = DeepgramProvider(api_key="...", language="en-US")
    if provider.test_connection():
        result = provider.transcribe_with_result(audio_segment)
        if result.success:
            print(result.text)
"""

from .base import BaseSTTProvider, TranscriptionResult
from .elevenlabs import ElevenLabsProvider
from .deepgram import DeepgramProvider
from .groq import GroqProvider
from .whisper import WhisperProvider

__all__ = [
    'BaseSTTProvider',
    'TranscriptionResult',
    'ElevenLabsProvider',
    'DeepgramProvider',
    'GroqProvider',
    'WhisperProvider'
]
