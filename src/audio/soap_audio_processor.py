"""
SOAP Audio Processor Module

Handles audio processing for SOAP note recording including numpy array handling,
audio segment creation, silence detection, and incremental combination logic.
"""

import threading

import numpy as np
from pydub import AudioSegment

from utils.structured_logging import get_logger

logger = get_logger(__name__)


class SOAPAudioProcessor:
    """Manages SOAP-specific audio processing functionality."""

    def __init__(self, parent_app):
        """Initialize the SOAP audio processor.

        Args:
            parent_app: The main application instance
        """
        self.app = parent_app

    # Counter for logging periodic updates
    _callback_count = 0

    def process_soap_callback(self, audio_data) -> None:
        """Callback for SOAP note recording using RecordingManager.

        This method is called from the PortAudio callback thread during
        recording, and from the main thread during flush. ALL tkinter
        calls (including winfo_exists, after, configure, etc.) are
        unsafe from non-main threads and will cause a fatal GIL crash
        (PyEval_RestoreThread) when stream.stop() is called concurrently.
        Only do data processing here; skip UI updates from non-main threads.
        """
        # Add audio segment to recording manager (thread-safe, no tkinter)
        if isinstance(audio_data, np.ndarray):
            SOAPAudioProcessor._callback_count += 1
            self.app.recording_manager.add_audio_segment(audio_data)
            # Log every 10 callbacks at INFO level to track audio flow
            if SOAPAudioProcessor._callback_count == 1 or SOAPAudioProcessor._callback_count % 10 == 0:
                logger.info(f"SOAP callback #{SOAPAudioProcessor._callback_count}: "
                           f"shape={audio_data.shape}, dtype={audio_data.dtype}, "
                           f"max_amp={np.abs(audio_data).max():.4f}")
            else:
                logger.debug(f"Added audio segment to RecordingManager: shape={audio_data.shape}, dtype={audio_data.dtype}")

        # Skip ALL tkinter/UI operations when called from the PortAudio
        # callback thread. Any tkinter call from a non-main thread can
        # cause a fatal crash because tcl is not thread-safe.
        if threading.current_thread() is not threading.main_thread():
            return

        # Visual feedback for UI updates (only reached from main thread)
        try:
            if isinstance(audio_data, np.ndarray):
                max_amp = np.abs(audio_data).max()

                # Visual feedback based on audio level
                if max_amp < 0.005:
                    self.app.after(0, lambda: self.app.update_status("Audio level too low - please speak louder", "warning"))
                else:
                    self.app.after(0, lambda: self.app.update_status("Recording SOAP note...", "info"))
            else:
                # For non-numpy data, convert and add to recording manager
                try:
                    new_segment, _ = self.app.audio_handler.process_audio_data(audio_data)
                    if new_segment:
                        # Convert AudioSegment to numpy array
                        raw_data = np.frombuffer(new_segment.raw_data, dtype=np.int16)
                        self.app.recording_manager.add_audio_segment(raw_data)

                        # Visual feedback
                        self.app.after(0, lambda: self.app.update_status("Recording SOAP note...", "info"))
                    else:
                        logger.warning(f"SOAP recording: No audio segment created from data of type {type(audio_data)}")
                except Exception as e:
                    logger.error(f"Error processing non-numpy audio data: {str(e)}", exc_info=True)

        except Exception as e:
            logger.error(f"Error in SOAP audio callback: {str(e)}", exc_info=True)
    
    
