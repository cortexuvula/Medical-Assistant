"""
Audio Transcription Mixin

Provides transcription functionality for the AudioHandler class.
"""

import os
from typing import TYPE_CHECKING, Optional
from pydub import AudioSegment

if TYPE_CHECKING:
    from stt_providers.base import TranscriptionResult

from settings.settings_manager import settings_manager
from managers.vocabulary_manager import vocabulary_manager
from utils.structured_logging import get_logger
from utils.constants import (
    STT_ELEVENLABS, STT_DEEPGRAM, STT_GROQ, STT_WHISPER, STT_MODULATE,
)

logger = get_logger(__name__)


class TranscriptionMixin:
    """Mixin providing transcription methods for AudioHandler.

    This mixin expects the following attributes on the class:
    - elevenlabs_provider: ElevenLabsProvider instance
    - deepgram_provider: DeepgramProvider instance
    - groq_provider: GroqProvider instance
    - whisper_provider: WhisperProvider instance
    - fallback_callback: Optional callback for fallback notifications
    - _prefix_audio_cache: Cached prefix audio segment
    - _prefix_audio_checked: Flag indicating if prefix audio was checked
    """

    def set_stt_provider(self, provider: str) -> None:
        """Set the STT provider to use for transcription.

        Args:
            provider: Provider name ('elevenlabs', 'deepgram', 'groq', or 'whisper')
        """
        if provider in [STT_ELEVENLABS, STT_DEEPGRAM, STT_GROQ, STT_WHISPER, STT_MODULATE]:
            settings_manager.set("stt_provider", provider)
            logger.info(f"STT provider set to {provider}")
        else:
            logger.warning(f"Unknown STT provider: {provider}")

    def reset_prefix_audio_cache(self) -> None:
        """Reset the prefix audio cache.

        Call this when the prefix audio file changes to force reload.
        """
        self._prefix_audio_cache = None
        self._prefix_audio_checked = False
        self._prefix_audio_mtime = None
        logger.debug("Prefix audio cache reset")

    def _prefix_audio_needs_reload(self, path: str) -> bool:
        """Check if prefix audio file has been modified since last load."""
        try:
            if not os.path.exists(path):
                return self._prefix_audio_cache is not None  # Need to clear cache
            current_mtime = os.path.getmtime(path)
            return current_mtime != self._prefix_audio_mtime
        except OSError:
            return False

    def transcribe_audio_without_prefix(self, segment: AudioSegment, **kwargs) -> str:
        """Transcribe audio using selected provider without adding prefix audio.

        This method is used for conversational transcription where medical
        terminology prefix is not needed (e.g., translation dialog).

        Args:
            segment: AudioSegment to transcribe
            **kwargs: Additional keyword arguments passed to the STT provider
                (e.g., diarize_override=False to disable diarization without
                mutating global settings)

        Returns:
            Transcription text or empty string if transcription failed
        """
        primary_provider = settings_manager.get("stt_provider", STT_ELEVENLABS)
        fallback_attempted = False

        # First attempt with selected provider
        transcript = self._try_transcription_with_provider(segment, primary_provider, **kwargs)

        # Only use fallback if there's an actual error (empty string)
        if transcript == "" and self.fallback_callback and not fallback_attempted:
            logger.info("Primary STT provider failed, attempting fallback")
            fallback_attempted = True

            # Try fallback providers
            fallback_providers = [p for p in [STT_GROQ, STT_DEEPGRAM, STT_ELEVENLABS, STT_MODULATE] if p != primary_provider]
            for provider in fallback_providers:
                transcript = self._try_transcription_with_provider(segment, provider, **kwargs)
                if transcript:
                    logger.info(f"Fallback to {provider} successful")
                    break

        return transcript

    def transcribe_audio(self, segment: AudioSegment) -> str:
        """Transcribe audio using selected provider with fallback options.

        Args:
            segment: AudioSegment to transcribe

        Returns:
            Transcription text or empty string if transcription failed
        """
        # Check if there's a prefix audio file to prepend (use cache with mtime tracking)
        from managers.data_folder_manager import data_folder_manager
        prefix_audio_path = str(data_folder_manager.app_data_folder / "prefix_audio.mp3")

        if not self._prefix_audio_checked or self._prefix_audio_needs_reload(prefix_audio_path):
            self._prefix_audio_checked = True
            logger.debug(f"Checking for prefix audio at: {prefix_audio_path}")
            if os.path.exists(prefix_audio_path):
                try:
                    current_mtime = os.path.getmtime(prefix_audio_path)
                    if self._prefix_audio_cache is None or current_mtime != self._prefix_audio_mtime:
                        logger.info(f"Loading prefix audio from {prefix_audio_path}")
                        self._prefix_audio_cache = AudioSegment.from_file(prefix_audio_path)
                        self._prefix_audio_mtime = current_mtime
                        logger.info(f"Cached prefix audio (length: {len(self._prefix_audio_cache)}ms)")
                except Exception as e:
                    logger.error(f"Error loading prefix audio: {e}", exc_info=True)
                    self._prefix_audio_cache = None
                    self._prefix_audio_mtime = None
            else:
                logger.debug(f"No prefix audio file found at: {prefix_audio_path}")
                self._prefix_audio_cache = None
                self._prefix_audio_mtime = None

        # If we have cached prefix audio, prepend it
        if self._prefix_audio_cache:
            try:
                combined_segment = self._prefix_audio_cache + segment
                segment = combined_segment
                logger.debug("Successfully prepended cached prefix audio to recording")
            except Exception as e:
                logger.error(f"Error prepending prefix audio: {e}", exc_info=True)

        # Get the selected STT provider from settings
        primary_provider = settings_manager.get("stt_provider", STT_ELEVENLABS)
        fallback_attempted = False

        # First attempt with selected provider
        transcript = self._try_transcription_with_provider(segment, primary_provider)

        # Only use fallback if there's an actual error (empty string)
        if transcript == "" and not fallback_attempted:
            fallback_providers = [STT_DEEPGRAM, STT_ELEVENLABS, STT_GROQ, STT_WHISPER, STT_MODULATE]
            if primary_provider in fallback_providers:
                fallback_providers.remove(primary_provider)

            for provider in fallback_providers:
                logger.info(f"Trying fallback provider: {provider}")

                if self.fallback_callback:
                    self.fallback_callback(primary_provider, provider)

                transcript = self._try_transcription_with_provider(segment, provider)
                if transcript != "":
                    logger.info(f"Transcription successful with fallback provider: {provider}")
                    break

        # Apply vocabulary corrections
        if transcript:
            transcript = vocabulary_manager.correct_transcript(transcript)

        return transcript or ""

    def _try_transcription_with_provider(self, segment: AudioSegment, provider: str, **kwargs) -> str:
        """Try to transcribe with a specific provider, handling errors.

        Args:
            segment: AudioSegment to transcribe
            provider: Provider name ('elevenlabs', 'deepgram', 'groq', or 'whisper')
            **kwargs: Additional keyword arguments passed to the provider
                (e.g., diarize_override for ElevenLabs)

        Returns:
            Transcription text or empty string if failed
        """
        try:
            if provider == STT_ELEVENLABS:
                return self.elevenlabs_provider.transcribe(segment, **kwargs)
            elif provider == STT_DEEPGRAM:
                return self.deepgram_provider.transcribe(segment)
            elif provider == STT_GROQ:
                return self.groq_provider.transcribe(segment)
            elif provider == STT_WHISPER:
                return self.whisper_provider.transcribe(segment)
            elif provider == STT_MODULATE:
                return self.modulate_provider.transcribe(segment, **kwargs)
            else:
                logger.warning(f"Unknown provider: {provider}")
                return ""
        except Exception as e:
            logger.error(f"Error with {provider} transcription: {str(e)}", exc_info=True)
            return ""


    def transcribe_audio_with_metadata(self, segment: AudioSegment) -> 'TranscriptionResult':
        """Transcribe audio and return structured result with metadata.

        When Modulate is the active provider, this returns a TranscriptionResult
        that includes emotion data in .metadata. For other providers, wraps the
        plain text result.

        Args:
            segment: AudioSegment to transcribe

        Returns:
            TranscriptionResult with text and optional emotion metadata
        """
        from stt_providers.base import TranscriptionResult

        primary_provider = settings_manager.get("stt_provider", STT_ELEVENLABS)

        if primary_provider == STT_MODULATE and hasattr(self, 'modulate_provider'):
            try:
                result = self.modulate_provider.transcribe_with_result(segment)
                if result.success:
                    # Apply vocabulary corrections
                    if result.text:
                        result.text = vocabulary_manager.correct_transcript(result.text)
                    return result
            except Exception as e:
                logger.error(f"Modulate transcribe_with_result failed: {e}", exc_info=True)

        # Fallback: use standard transcribe and wrap result
        text = self.transcribe_audio(segment)
        if text:
            return TranscriptionResult.success_result(text=text)
        return TranscriptionResult.failure_result(error="Transcription returned empty result")


__all__ = ["TranscriptionMixin"]
