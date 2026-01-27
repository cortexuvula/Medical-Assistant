"""
Audio Transcription Mixin

Provides transcription functionality for the AudioHandler class.
"""

import os
from typing import Optional
from pydub import AudioSegment

from settings.settings import SETTINGS
from managers.vocabulary_manager import vocabulary_manager
from utils.structured_logging import get_logger

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
        if provider in ["elevenlabs", "deepgram", "groq", "whisper"]:
            from settings.settings import save_settings
            SETTINGS["stt_provider"] = provider
            save_settings(SETTINGS)
            logger.info(f"STT provider set to {provider}")
        else:
            logger.warning(f"Unknown STT provider: {provider}")

    def reset_prefix_audio_cache(self) -> None:
        """Reset the prefix audio cache.

        Call this when the prefix audio file changes to force reload.
        """
        self._prefix_audio_cache = None
        self._prefix_audio_checked = False
        logger.debug("Prefix audio cache reset")

    def transcribe_audio_without_prefix(self, segment: AudioSegment) -> str:
        """Transcribe audio using selected provider without adding prefix audio.

        This method is used for conversational transcription where medical
        terminology prefix is not needed (e.g., translation dialog).

        Args:
            segment: AudioSegment to transcribe

        Returns:
            Transcription text or empty string if transcription failed
        """
        primary_provider = SETTINGS.get("stt_provider", "elevenlabs")
        fallback_attempted = False

        # First attempt with selected provider
        transcript = self._try_transcription_with_provider(segment, primary_provider)

        # Only use fallback if there's an actual error (empty string)
        if transcript == "" and self.fallback_callback and not fallback_attempted:
            logger.info("Primary STT provider failed, attempting fallback")
            fallback_attempted = True

            # Try fallback providers
            fallback_providers = [p for p in ["groq", "deepgram", "elevenlabs"] if p != primary_provider]
            for provider in fallback_providers:
                transcript = self._try_transcription_with_provider(segment, provider)
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
        # Check if there's a prefix audio file to prepend (use cache)
        if not self._prefix_audio_checked:
            self._prefix_audio_checked = True
            from managers.data_folder_manager import data_folder_manager
            prefix_audio_path = str(data_folder_manager.app_data_folder / "prefix_audio.mp3")
            logger.debug(f"Checking for prefix audio at: {prefix_audio_path}")
            if os.path.exists(prefix_audio_path):
                try:
                    logger.info(f"Loading prefix audio from {prefix_audio_path}")
                    self._prefix_audio_cache = AudioSegment.from_file(prefix_audio_path)
                    logger.info(f"Cached prefix audio (length: {len(self._prefix_audio_cache)}ms)")
                except Exception as e:
                    logger.error(f"Error loading prefix audio: {e}", exc_info=True)
                    self._prefix_audio_cache = None
            else:
                logger.debug(f"No prefix audio file found at: {prefix_audio_path}")

        # If we have cached prefix audio, prepend it
        if self._prefix_audio_cache:
            try:
                combined_segment = self._prefix_audio_cache + segment
                segment = combined_segment
                logger.debug("Successfully prepended cached prefix audio to recording")
            except Exception as e:
                logger.error(f"Error prepending prefix audio: {e}", exc_info=True)

        # Get the selected STT provider from settings
        primary_provider = SETTINGS.get("stt_provider", "elevenlabs")
        fallback_attempted = False

        # First attempt with selected provider
        transcript = self._try_transcription_with_provider(segment, primary_provider)

        # Only use fallback if there's an actual error (empty string)
        if transcript == "" and not fallback_attempted:
            fallback_providers = ["deepgram", "elevenlabs", "groq", "whisper"]
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

    def _try_transcription_with_provider(self, segment: AudioSegment, provider: str) -> str:
        """Try to transcribe with a specific provider, handling errors.

        Args:
            segment: AudioSegment to transcribe
            provider: Provider name ('elevenlabs', 'deepgram', 'groq', or 'whisper')

        Returns:
            Transcription text or empty string if failed
        """
        try:
            if provider == "elevenlabs":
                return self.elevenlabs_provider.transcribe(segment)
            elif provider == "deepgram":
                return self.deepgram_provider.transcribe(segment)
            elif provider == "groq":
                return self.groq_provider.transcribe(segment)
            elif provider == "whisper":
                return self.whisper_provider.transcribe(segment)
            else:
                logger.warning(f"Unknown provider: {provider}")
                return ""
        except Exception as e:
            logger.error(f"Error with {provider} transcription: {str(e)}", exc_info=True)
            return ""


__all__ = ["TranscriptionMixin"]
