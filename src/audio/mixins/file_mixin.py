"""
Audio File Operations Mixin

Provides file loading, saving, and audio segment operations for the AudioHandler class.
"""

import os
from pathlib import Path
from typing import List, Optional, Tuple

from pydub import AudioSegment

from utils.structured_logging import get_logger

logger = get_logger(__name__)


class FileMixin:
    """Mixin providing file operations for AudioHandler.

    This mixin expects the following methods on the class:
    - transcribe_audio(segment): Transcribe an audio segment
    """

    def combine_audio_segments(self, segments: List[AudioSegment]) -> Optional[AudioSegment]:
        """Combine multiple audio segments into a single segment efficiently.

        Args:
            segments: List of AudioSegment objects

        Returns:
            Combined AudioSegment or None if list is empty
        """
        if not segments:
            logger.warning("combine_audio_segments called with empty list")
            return None

        try:
            # Start with the first segment to ensure correct parameters
            combined = segments[0]
            if len(segments) > 1:
                combined = sum(segments[1:], start=combined)
            return combined
        except Exception as e:
            logger.error(f"Error combining audio segments: {e}", exc_info=True)
            # Fallback to iterative concatenation
            logger.info("Falling back to iterative concatenation due to error.")
            combined_fallback = segments[0]
            for segment in segments[1:]:
                combined_fallback += segment
            return combined_fallback

    def load_audio_file(self, file_path: str) -> Tuple[Optional[AudioSegment], str]:
        """Load and transcribe audio from a file.

        Args:
            file_path: Path to audio file

        Returns:
            Tuple of (AudioSegment, transcription_text)
        """
        try:
            if file_path.lower().endswith(".mp3"):
                seg = AudioSegment.from_file(file_path, format="mp3")
            elif file_path.lower().endswith(".wav"):
                seg = AudioSegment.from_file(file_path, format="wav")
            else:
                raise ValueError("Unsupported audio format. Only .wav and .mp3 supported.")

            transcript = self.transcribe_audio(seg)
            return seg, transcript

        except Exception as e:
            logger.error(f"Error loading audio file: {str(e)}", exc_info=True)
            return None, ""

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
            logger.error(f"Error saving audio: {str(e)}", exc_info=True)
            return False


__all__ = ["FileMixin"]
