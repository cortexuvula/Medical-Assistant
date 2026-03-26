"""
Audio File Operations Mixin

Provides file loading, saving, and validation for the AudioHandler class.
"""

import os
from pathlib import Path
from typing import List, Optional, Tuple, TYPE_CHECKING

from pydub import AudioSegment

if TYPE_CHECKING:
    from stt_providers.base import TranscriptionResult

from settings.settings_manager import settings_manager
from utils.error_handling import ErrorContext
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class FileMixin:
    """Mixin providing file operations for AudioHandler.

    This mixin expects the following methods on the class:
    - transcribe_audio(segment): Transcribe an audio segment
    - transcribe_audio_with_metadata(segment): Transcribe with metadata
    - combine_audio_segments(segments): Combine audio segments
    """

    @staticmethod
    def validate_audio_file_size(file_path: str, max_size_mb: float = None) -> tuple[bool, float, float]:
        """Validate that an audio file is within the allowed size limit.

        Args:
            file_path: Path to the audio file.
            max_size_mb: Maximum allowed size in MB. Reads from settings_manager if None.

        Returns:
            Tuple of (is_valid, file_size_mb, max_mb).
        """
        if max_size_mb is None:
            max_size_mb = settings_manager.get("max_audio_file_size_mb", 500)
        try:
            file_size_bytes = os.path.getsize(file_path)
        except OSError:
            return True, 0.0, max_size_mb  # Let downstream handle missing files
        file_size_mb = file_size_bytes / (1024 * 1024)
        return file_size_mb <= max_size_mb, round(file_size_mb, 1), max_size_mb

    def load_audio_file(self, file_path: str) -> tuple[Optional[AudioSegment], str]:
        """Load and transcribe audio from a file.

        Args:
            file_path: Path to audio file

        Returns:
            Tuple of (AudioSegment, transcription_text)
        """
        result = self.load_audio_file_with_metadata(file_path)
        return result[0], result[1]

    def load_audio_file_with_metadata(self, file_path: str) -> tuple[Optional[AudioSegment], str, Optional[dict]]:
        """Load and transcribe audio from a file, capturing metadata.

        Uses transcribe_audio_with_metadata() to capture emotion data
        from providers like Modulate.ai.

        Args:
            file_path: Path to audio file

        Returns:
            Tuple of (AudioSegment, transcription_text, metadata_dict_or_None)
        """
        try:
            # Validate file size before loading into memory
            is_valid, file_size_mb, max_mb = self.validate_audio_file_size(file_path)
            if not is_valid:
                raise ValueError(
                    f"Audio file is too large ({file_size_mb} MB). "
                    f"Maximum allowed size is {max_mb} MB. "
                    f"Please use a smaller file or increase the limit in Settings."
                )

            if (file_path.lower().endswith(".mp3")):
                seg = AudioSegment.from_file(file_path, format="mp3")
            elif (file_path.lower().endswith(".wav")):
                seg = AudioSegment.from_file(file_path, format="wav")
            else:
                raise ValueError("Unsupported audio format. Only .wav and .mp3 supported.")

            # Use metadata-aware transcription to capture emotion data
            result = self.transcribe_audio_with_metadata(seg)
            if result.success and result.text:
                return seg, result.text, result.metadata

            # Fallback to plain transcription
            transcript = self.transcribe_audio(seg)
            return seg, transcript, None

        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Load audio file",
                exception=e,
                error_code="AUDIO_FILE_LOAD_ERROR",
                file_path=file_path
            )
            ctx.log()
            return None, "", None

    def save_audio(self, segments: List[AudioSegment], file_path: str) -> bool:
        """Save combined audio segments to file.

        Args:
            segments: List of AudioSegment objects
            file_path: Path to save the combined audio

        Returns:
            True if successful, False otherwise
        """
        try:
            if not segments:
                logger.warning("No audio segments to save")
                return False

            combined = self.combine_audio_segments(segments)
            if combined:
                try:
                    # Ensure directory exists
                    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
                except Exception as dir_e:
                    logger.error(f"Failed to create directory for {file_path}: {str(dir_e)}")
                    return False

                logger.info(f"Exporting audio to {file_path} with format=mp3, bitrate=192k")
                combined.export(file_path, format="mp3", bitrate="192k")

                # Verify file was created
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    logger.info(f"Audio successfully saved to {file_path} (size: {file_size} bytes)")
                else:
                    logger.error(f"Audio export completed but file not found at {file_path}")
                    return False

                return True
            return False
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Save audio file",
                exception=e,
                error_code="AUDIO_FILE_SAVE_ERROR",
                file_path=file_path,
                segment_count=len(segments) if segments else 0
            )
            ctx.log()
            return False


__all__ = ["FileMixin"]
