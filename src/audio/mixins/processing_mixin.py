"""
Audio Processing Mixin

Provides audio data conversion, processing, and segment combination
for the AudioHandler class.
"""

from typing import List, Optional, Union

import numpy as np
from pydub import AudioSegment

from utils.error_handling import ErrorContext
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class ProcessingMixin:
    """Mixin providing audio processing methods for AudioHandler.

    This mixin expects the following attributes on the class:
    - sample_rate: Current sample rate
    - channels: Current channel count
    - silence_threshold: Threshold for silence detection
    - soap_mode: Whether SOAP recording mode is active
    - listening_device: Currently selected device name
    - recorded_frames: List of recorded AudioSegment frames
    - callback_function: Current callback function
    And the following methods:
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
            # Start with the first segment to ensure correct parameters (frame rate, channels, etc.)
            combined = segments[0]
            if len(segments) > 1:
                combined = sum(segments[1:], start=combined)
            return combined
        except Exception as e:
            logger.error(f"Error combining audio segments: {e}", exc_info=True)
            # Fallback to iterative concatenation in case of unexpected issues with sum()
            logger.info("Falling back to iterative concatenation due to error.")
            combined_fallback = segments[0]
            for segment in segments[1:]:
                combined_fallback += segment
            return combined_fallback

    def convert_audio_to_segment(self, audio_data) -> Optional[AudioSegment]:
        """Convert audio data to AudioSegment without transcribing.

        Use this for accumulating audio segments during recording when you
        want to transcribe the combined audio later (e.g., translation dialog).

        Args:
            audio_data: AudioData object or numpy array from sounddevice

        Returns:
            AudioSegment or None if conversion failed
        """
        # Import here to avoid circular imports; AudioData is defined in audio.audio
        from audio.audio import AudioData

        try:
            # Handle different input types
            if isinstance(audio_data, AudioData):
                # Legacy AudioData handling
                channels = getattr(audio_data, "channels", 1)
                sample_width = getattr(audio_data, "sample_width", None)
                sample_rate = getattr(audio_data, "sample_rate", None)

                if not audio_data.get_raw_data():
                    logger.warning("Empty audio data received")
                    return None

                return AudioSegment(
                    data=audio_data.get_raw_data(),
                    sample_width=sample_width,
                    frame_rate=sample_rate,
                    channels=channels
                )
            elif isinstance(audio_data, np.ndarray):
                if audio_data.size == 0:
                    logger.warning("Empty audio data received")
                    return None

                # Convert float32 to int16 for compatibility
                if audio_data.dtype == np.float32:
                    audio_clipped = np.clip(audio_data, -1.0, 1.0)
                    audio_int16 = (audio_clipped * 32767).astype(np.int16)
                elif audio_data.dtype == np.int16:
                    audio_int16 = audio_data
                else:
                    audio_int16 = audio_data.astype(np.int16)

                raw_data = audio_int16.tobytes()

                return AudioSegment(
                    data=raw_data,
                    sample_width=2,
                    frame_rate=self.sample_rate,
                    channels=self.channels
                )
            else:
                logger.error(f"Unsupported audio data type: {type(audio_data)}")
                return None
        except Exception as e:
            logger.error(f"Error converting audio to segment: {e}", exc_info=True)
            return None

    def process_audio_data(self, audio_data) -> tuple[Optional[AudioSegment], str]:
        """Process audio data to get an AudioSegment and transcription.

        Args:
            audio_data: AudioData object or numpy array from sounddevice

        Returns:
            Tuple of (AudioSegment, transcription_text)
        """
        from audio.audio import AudioData

        try:
            # Handle different input types
            if isinstance(audio_data, AudioData):
                # Legacy AudioData handling
                channels = getattr(audio_data, "channels", 1)
                sample_width = getattr(audio_data, "sample_width", None)
                sample_rate = getattr(audio_data, "sample_rate", None)

                # Log diagnostic info
                logger.debug(f"Processing legacy AudioData: channels={channels}, width={sample_width}, rate={sample_rate}")

                # Validate audio data
                if not audio_data.get_raw_data():
                    logger.warning("Empty audio data received")
                    return None, ""

                # Convert to AudioSegment
                segment = AudioSegment(
                    data=audio_data.get_raw_data(),
                    sample_width=sample_width,
                    frame_rate=sample_rate,
                    channels=channels
                )
            elif isinstance(audio_data, np.ndarray):
                # Sounddevice numpy array handling
                logger.debug(f"Processing sounddevice audio: shape={audio_data.shape}, dtype={audio_data.dtype}")

                # Validate audio data
                if audio_data.size == 0:
                    logger.warning("Empty audio data received")
                    return None, ""

                # Check amplitude and apply gain boost for Voicemeeter outputs
                max_amp = np.abs(audio_data).max()
                logger.debug(f"Audio max amplitude before processing: {max_amp:.6f}")

                # Check if audio is already clipping
                if max_amp >= 0.99:
                    logger.warning(f"Input audio is clipping! Max amplitude: {max_amp:.6f}")
                    # Normalize the audio to prevent further clipping
                    audio_data = audio_data * 0.8  # Scale down to 80% to give headroom
                    max_amp = np.abs(audio_data).max()

                # For Voicemeeter devices or in SOAP mode, apply gain boost only if needed
                if (self.listening_device and "voicemeeter" in str(self.listening_device).lower()) or self.soap_mode:
                    # Only boost if the signal is weak
                    if max_amp < 0.1:  # Only boost quiet signals
                        # In SOAP mode, apply much higher gain boost
                        if self.soap_mode:
                            boost_factor = min(10.0, 0.8 / max_amp)  # Limit boost to prevent clipping
                            logger.debug(f"SOAP mode: Applying boost factor of {boost_factor:.2f}x")
                        else:
                            boost_factor = min(5.0, 0.8 / max_amp)  # Standard boost for Voicemeeter
                            logger.debug(f"Applying boost factor of {boost_factor:.2f}x for Voicemeeter")

                        # Apply the boost
                        audio_data = audio_data * boost_factor

                        # Log the new max amplitude
                        new_max_amp = np.abs(audio_data).max()
                        logger.debug(f"After gain boost: max amplitude is now {new_max_amp:.6f}")
                    else:
                        logger.debug(f"Audio level sufficient ({max_amp:.3f}), no boost needed")

                # Skip if amplitude is still too low after boosting
                # Use a more permissive threshold for SOAP mode
                effective_threshold = self.silence_threshold if self.soap_mode else 0.001
                if np.abs(audio_data).max() < effective_threshold:
                    logger.warning(f"Audio level still too low after boost: {np.abs(audio_data).max():.6f}")
                    return None, ""

                # Convert float32 to int16 for compatibility
                if audio_data.dtype == np.float32:
                    # Clip to prevent overflow when converting
                    audio_clipped = np.clip(audio_data, -1.0, 1.0)
                    audio_int16 = (audio_clipped * 32767).astype(np.int16)
                elif audio_data.dtype == np.int16:
                    audio_int16 = audio_data
                else:
                    audio_int16 = audio_data.astype(np.int16)

                # Convert to bytes
                raw_data = audio_int16.tobytes()

                # Convert to AudioSegment
                segment = AudioSegment(
                    data=raw_data,
                    sample_width=2,  # 2 bytes for int16
                    frame_rate=self.sample_rate,
                    channels=self.channels
                )
            else:
                logger.error(f"Unsupported audio data type: {type(audio_data)}")
                return None, ""

            # Get transcript
            transcript = self.transcribe_audio(segment)

            return segment, transcript

        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Process audio data",
                exception=e,
                error_code="AUDIO_PROCESSING_ERROR",
                audio_data_type=type(audio_data).__name__,
                soap_mode=self.soap_mode
            )
            ctx.log()
            return None, ""

    def add_segment(self, audio_data: np.ndarray) -> None:
        """
        Add an audio segment to the list of segments.

        Args:
            audio_data: Audio data as a numpy array.
        """
        try:
            if audio_data is None:
                logger.warning("SOAP recording: Received None audio data")
                return

            # Check if the audio data has a valid shape and type
            if not hasattr(audio_data, 'shape'):
                logger.warning(f"SOAP recording: No audio segment created from data of type {type(audio_data)}")
                return

            # Get the maximum amplitude
            max_amp = np.max(np.abs(audio_data)) if audio_data.size > 0 else 0.0

            # Always log the max amplitude for debugging
            if max_amp > 0.0:
                logger.info(f"SOAP recording: Audio segment with max amplitude {max_amp:.6f}")
            else:
                logger.warning(f"SOAP recording: Max amplitude was {max_amp}")

            # Apply an aggressive boost to ensure we capture even quiet audio
            if max_amp > 0.0001 and max_amp < 0.1:  # There's some audio but it's quiet
                boost_factor = min(20.0, 0.5 / max_amp)  # Very high boost for quiet audio
                audio_data = audio_data * boost_factor
                logger.info(f"SOAP recording: Boosted audio by factor {boost_factor:.2f}")

            # For SOAP mode, always create a segment regardless of amplitude
            # This is crucial for ensuring the recording works even with very quiet audio
            if self.soap_mode or max_amp > 0.0001:  # Ultra-low threshold or SOAP mode
                # Convert float32 to int16 for compatibility
                if audio_data.dtype == np.float32:
                    # Clip to prevent overflow when converting
                    audio_clipped = np.clip(audio_data, -1.0, 1.0)
                    audio_int16 = (audio_clipped * 32767).astype(np.int16)
                elif audio_data.dtype == np.int16:
                    audio_int16 = audio_data
                else:
                    audio_int16 = audio_data.astype(np.int16)

                # Convert to bytes
                raw_data = audio_int16.tobytes()

                # Create a new segment using the same pattern as process_audio_data
                segment = AudioSegment(
                    data=raw_data,
                    sample_width=2,  # 2 bytes for int16
                    frame_rate=self.sample_rate,
                    channels=self.channels
                )

                # Add the segment to the list
                self.recorded_frames.append(segment)
                logger.info(f"SOAP recording: Created segment, total segments: {len(self.recorded_frames)}")

                if self.callback_function:
                    try:
                        self.callback_function(segment)
                    except Exception as e:
                        logger.error(f"Error in new segment callback: {e}")
            else:
                logger.warning(f"SOAP recording: Amplitude {max_amp:.8f} too low to create segment")

        except Exception as e:
            logger.error(f"Error adding segment: {e}", exc_info=True)


__all__ = ["ProcessingMixin"]
