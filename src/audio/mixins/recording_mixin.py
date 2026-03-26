"""
Audio Recording Mixin

Provides background listening, stream management, and recording
functionality for the AudioHandler class.
"""

import time
import threading
from typing import Callable, Optional, Any, Tuple

import numpy as np

# Import audio libraries conditionally
try:
    import soundcard
    SOUNDCARD_AVAILABLE = True
except (ImportError, AssertionError, OSError):
    soundcard = None
    SOUNDCARD_AVAILABLE = False

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except (ImportError, OSError):
    sd = None
    SOUNDDEVICE_AVAILABLE = False

from utils.structured_logging import get_logger

logger = get_logger(__name__)


class RecordingMixin:
    """Mixin providing recording and listening methods for AudioHandler.

    This mixin expects the following attributes on the class:
    - sample_rate: Current sample rate
    - channels: Current channel count
    - recording: Whether recording is active
    - recording_thread: Background recording thread
    - callback_function: Current callback function
    - listening_device: Currently selected device name
    - _instance_streams: Set of stream purposes owned by this instance
    - DEFAULT_PHRASE_TIME_LIMIT: Default phrase time limit

    And the following class-level attributes on AudioHandler:
    - _active_streams: Dict of active streams by purpose
    - _streams_lock: Lock for thread-safe stream management

    And the following methods (from DeviceMixin):
    - _resolve_device_index(device_name): Resolve name to index
    - _setup_audio_parameters(device_id): Setup audio parameters
    """

    def listen_in_background(self, mic_name: str, callback: Callable, phrase_time_limit: Optional[int] = None, stream_purpose: str = "default") -> Callable:
        """Start listening in the background for phrases.

        Args:
            mic_name: Name of the microphone to use
            callback: Function to call for each detected phrase
            phrase_time_limit: Max seconds for a phrase, or None for no limit
            stream_purpose: Purpose identifier for this stream (e.g., "soap", "translation")

        Returns:
            Function that when called stops the background listener
        """
        # Avoid circular import at module level
        from audio.audio import AudioHandler

        # Use the default phrase time limit if none is provided
        if phrase_time_limit is None:
            phrase_time_limit = self.DEFAULT_PHRASE_TIME_LIMIT

        # Log the actual phrase time limit being used
        logger.info(f"Starting background listening with phrase_time_limit: {phrase_time_limit} seconds")

        # Check if a stream with this purpose already exists (thread-safe)
        with AudioHandler._streams_lock:
            if stream_purpose in AudioHandler._active_streams:
                logger.warning(f"Stream with purpose '{stream_purpose}' already exists. Stopping existing stream.")
                # Get the existing stream info
                existing_info = AudioHandler._active_streams.get(stream_purpose)
                if existing_info and 'stream' in existing_info:
                    try:
                        existing_info['stream'].stop()
                        existing_info['stream'].close()
                    except (OSError, AttributeError) as e:
                        logger.error(f"Error stopping existing stream: {e}")
                AudioHandler._active_streams.pop(stream_purpose, None)
                # Also remove from instance tracking if present
                self._instance_streams.discard(stream_purpose)

        try:
            logger.info(f"Attempting to start background listening for device: {mic_name}")
            self.listening_device = mic_name  # Store the requested name
            self.callback_function = callback  # Store callback

            logger.info(f"Using sounddevice backend for: {mic_name}")
            stop_function = self._listen_with_sounddevice(mic_name, callback, phrase_time_limit, stream_purpose)
            return stop_function

        except Exception as e:
            logger.error(f"Error in listen_in_background for '{mic_name}': {e}", exc_info=True)
            # Return a no-op function on error
            return lambda _=True: None

    def _create_stop_function(self, stream, flush_callback: Callable = None, stream_purpose: str = "default", mark_stopping: Callable = None, stream_started: threading.Event = None) -> Callable:
        """Create the stop function for the audio stream.

        Args:
            stream: The sounddevice InputStream.
            flush_callback: Optional callback to flush any remaining audio data.
            stream_purpose: Purpose identifier for this stream
            mark_stopping: Optional function to signal the audio callback to stop
                          processing before the stream is stopped.
            stream_started: Optional event that is set when the stream has finished
                          starting.

        Returns:
            Function to stop the stream.
        """
        from audio.audio import AudioHandler

        # Capture reference to self for use in closure
        handler_instance = self

        def stop_stream(wait_for_stop: bool = False) -> None:
            if stream:
                try:
                    # If the stream is still starting in a background thread,
                    # wait for it to finish before stopping
                    if stream_started and not stream_started.is_set():
                        logger.info("Waiting for audio stream to finish starting before stopping...")
                        stream_started.wait(timeout=3.0)

                    # Signal the audio callback to stop processing BEFORE
                    # stopping the stream.
                    if mark_stopping:
                        mark_stopping()

                    stream.stop()

                    # Flush remaining accumulated audio AFTER the stream is stopped.
                    if flush_callback:
                        flush_callback()

                    stream.close()
                    logger.info("sounddevice InputStream stopped and closed")
                except (OSError, AttributeError) as e:
                    logger.error(f"Error stopping sounddevice stream: {e}", exc_info=True)
                finally:
                    # Clear references
                    handler_instance.listening_device = None
                    handler_instance.callback_function = None

                    # Remove from active streams by purpose (thread-safe)
                    with AudioHandler._streams_lock:
                        if stream_purpose in AudioHandler._active_streams:
                            AudioHandler._active_streams.pop(stream_purpose, None)
                        # Remove from instance tracking
                        handler_instance._instance_streams.discard(stream_purpose)

        return stop_stream

    def _create_audio_callback(self, phrase_time_limit: int, callback: Callable = None) -> Tuple[Callable, Callable, Callable]:
        """Create the audio callback function for sounddevice.

        Args:
            phrase_time_limit: Maximum length of audio capture in seconds.
            callback: The callback function to call with accumulated audio data.
                     If None, falls back to self.callback_function (legacy behavior).

        Returns:
            Tuple of (callback_function, flush_function, mark_stopping_function).
        """
        # Buffer to accumulate audio data
        accumulated_data = []
        accumulated_frames = 0
        target_frames = int(self.sample_rate * phrase_time_limit)

        # Capture the callback in a closure variable to avoid race conditions
        captured_callback = callback if callback is not None else self.callback_function

        # Flag to prevent the PortAudio callback thread from calling into
        # Python/tkinter during stream shutdown.
        _stopping = [False]

        def mark_stopping():
            """Signal the audio callback to stop calling captured_callback."""
            _stopping[0] = True

        logger.info(f"Audio will accumulate until {target_frames} frames (approx. {phrase_time_limit} seconds) before processing")

        def flush_accumulated_audio():
            """Flush any accumulated audio data."""
            nonlocal accumulated_data, accumulated_frames
            if captured_callback and accumulated_data and accumulated_frames > 0:
                try:
                    # Combine all accumulated chunks
                    combined_data = np.vstack(accumulated_data) if len(accumulated_data) > 1 else accumulated_data[0]
                    logger.info(f"Flushing accumulated audio: frames={accumulated_frames}, shape={combined_data.shape}, max_amplitude={np.abs(combined_data).max():.6f}")
                    # Call the callback with the combined data
                    captured_callback(combined_data)
                except Exception as e:
                    logger.error(f"Error flushing accumulated audio: {e}", exc_info=True)
                finally:
                    # Reset for next accumulation
                    accumulated_data = []
                    accumulated_frames = 0

        def audio_callback_sd(indata: np.ndarray, frames: int, _: Any, status) -> None:
            nonlocal accumulated_data, accumulated_frames

            # Check stopping flag first
            if _stopping[0]:
                return

            if status:
                logger.warning(f"sounddevice status: {status}")
            try:
                # Make a copy to avoid issues with buffer overwriting
                audio_data_copy = indata.copy()

                # Log clipping but do NOT normalize per-chunk
                max_val = np.abs(audio_data_copy).max()
                if max_val >= 0.99:
                    if len(accumulated_data) <= 3:
                        logger.warning(f"Audio callback {len(accumulated_data) + 1}: clipping detected (max={max_val:.6f}), not normalizing to preserve diarization")

                # Add to accumulated buffer
                accumulated_data.append(audio_data_copy)
                accumulated_frames += frames

                # Only call the callback when we've accumulated enough data
                if accumulated_frames >= target_frames:
                    if captured_callback and accumulated_data:
                        # Combine all accumulated chunks
                        combined_data = np.vstack(accumulated_data) if len(accumulated_data) > 1 else accumulated_data[0]
                        # Ensure data is in the right shape (flatten to 1D if needed)
                        if len(combined_data.shape) > 1 and combined_data.shape[1] == 1:
                            combined_data = combined_data.flatten()
                        captured_callback(combined_data)

                        # Reset for next accumulation
                        accumulated_data = []
                        accumulated_frames = 0
            except Exception as e_cb:
                logger.error(f"Error in sounddevice audio_callback_sd: {e_cb}", exc_info=True)
                # Reset accumulation on error
                accumulated_data = []
                accumulated_frames = 0

        return audio_callback_sd, flush_accumulated_audio, mark_stopping

    def _listen_with_sounddevice(self, device_name: str, callback: Callable, phrase_time_limit: int = None, stream_purpose: str = "default") -> Callable:
        """Listen using sounddevice library, resolving name to index just-in-time.

        Args:
            device_name: The target device name string.
            callback: Function to call with audio data.
            phrase_time_limit: Maximum length of audio capture in seconds.
            stream_purpose: Purpose identifier for this stream.

        Returns:
            Function to stop listening.
        """
        from audio.audio import AudioHandler

        # Use the default phrase time limit if none is provided
        if phrase_time_limit is None:
            phrase_time_limit = self.DEFAULT_PHRASE_TIME_LIMIT
        stream = None  # Initialize stream variable
        try:
            self.listening_device = device_name  # Store the name being used
            self.callback_function = callback  # Store callback

            # Resolve device name to index
            device_id = self._resolve_device_index(device_name)
            logger.info(f"Device resolution result: device_name='{device_name}' -> device_id={device_id}")
            if device_id is None:
                # Try to use default input device as a fallback
                try:
                    default_input = sd.query_devices(kind='input')
                    if default_input and isinstance(default_input, dict) and 'index' in default_input:
                        device_id = default_input['index']
                        logger.warning(f"Falling back to default sounddevice input: Index={device_id}, Name='{default_input['name']}'")
                    else:
                        raise ValueError("Could not find specified or default sounddevice input device.")
                except Exception as e_def:
                    logger.error(f"Failed to get default sounddevice input: {e_def}")
                    raise ValueError(f"Device '{device_name}' not found and default could not be determined.")

            # Setup audio parameters
            self._setup_audio_parameters(device_id)

            # Create audio callback with the callback captured in a closure
            audio_callback_sd, flush_callback, mark_stopping = self._create_audio_callback(phrase_time_limit, callback)

            # Get device info for logging
            device_info = sd.query_devices(device_id)

            # Log detailed device information before starting stream
            logger.info(f"Creating stream with parameters: samplerate={self.sample_rate}, device={device_id}, channels={self.channels}")
            logger.info(f"Device info: name='{device_info['name']}', hostapi={device_info['hostapi']}, max_input_channels={device_info['max_input_channels']}")

            stream = sd.InputStream(
                samplerate=self.sample_rate,
                device=device_id,
                channels=self.channels,
                callback=audio_callback_sd,
                blocksize=0,
                dtype='float32'
            )

            # Start stream in a background thread to avoid blocking the Tk main thread.
            stream_started = threading.Event()
            stream_start_error = [None]

            def _start_stream_bg():
                try:
                    stream.start()
                    logger.info(f"sounddevice InputStream started successfully for '{device_info['name']}'")
                except Exception as e:
                    stream_start_error[0] = e
                    logger.error(f"Error starting audio stream in background: {e}")
                finally:
                    stream_started.set()

            start_thread = threading.Thread(target=_start_stream_bg, daemon=True)
            start_thread.start()

            # Wait briefly for the stream to start
            if not stream_started.wait(timeout=0.5):
                logger.info(
                    f"Audio stream start still initializing for '{device_info['name']}', "
                    "continuing in background"
                )

            # Check for immediate errors
            if stream_start_error[0] is not None:
                raise stream_start_error[0]

            # Add to active streams with purpose (thread-safe)
            with AudioHandler._streams_lock:
                AudioHandler._active_streams[stream_purpose] = {
                    'stream': stream,
                    'device': device_name,
                    'callback': callback
                }
                # Track that this instance owns this stream
                self._instance_streams.add(stream_purpose)

            # Create stop function with flush callback, stopping flag, and
            # stream_started event so stop can wait for start to complete
            stop_function = self._create_stop_function(stream, flush_callback, stream_purpose, mark_stopping, stream_started)

            return stop_function  # Return the specific closer for this stream

        except sd.PortAudioError as pae:
            logger.error(f"PortAudioError in _listen_with_sounddevice for '{device_name}': {pae}")
            logger.error(f"PortAudio error details: Host Error={pae.hostApiErrorInfo}")
            raise ValueError(f"Audio device error for '{device_name}': {pae}") from pae
        except Exception as e:
            logger.error(f"Error in _listen_with_sounddevice for '{device_name}': {e}", exc_info=True)
            # Clean up stream if it was partially created
            if stream:
                try:
                    # Check if the stream has a stopped attribute before accessing it
                    if hasattr(stream, 'stopped') and not stream.stopped:
                        stream.stop()
                    elif not hasattr(stream, 'stopped'):
                        # If no stopped attribute, try to stop anyway
                        stream.stop()
                    stream.close()
                except Exception as e_clean:
                    logger.error(f"Error during cleanup in _listen_with_sounddevice: {e_clean}")
            raise e  # Re-raise the exception

    def _background_recording_thread(self, device_index: int, phrase_time_limit: float) -> None:
        """ Background thread that records audio using soundcard (potentially problematic). """
        logger.warning("_background_recording_thread (soundcard) is likely deprecated.")
        if not SOUNDCARD_AVAILABLE:
            logger.error("Soundcard not available, cannot use soundcard backend")
            return
        try:
            mic = soundcard.get_microphone(device_index, include_loopback=True)
            if not mic:
                logger.error(f"Soundcard could not get microphone for index {device_index}")
                self.recording = False
                return

            logger.info(f"Starting soundcard recording thread for {mic.name}")
            with mic.recorder(samplerate=self.sample_rate, channels=self.channels) as recorder:
                while self.recording:
                    data = recorder.record(numframes=int(self.sample_rate * phrase_time_limit))
                    if not self.recording:  # Check again after blocking call
                        break
                    if data is not None and data.size > 0:
                        # Convert soundcard data (usually float64) to float32 if needed
                        if data.dtype != np.float32:
                            data = data.astype(np.float32)
                        logger.debug(f"Soundcard recorded chunk: Shape={data.shape}, Dtype={data.dtype}")
                        if self.callback_function:
                            self.callback_function(data)
                    else:
                        logger.debug("Soundcard recorder yielded empty data chunk.")
                        time.sleep(0.01)  # Small sleep if no data

        except Exception as e:
            logger.error(f"Error in soundcard recording thread: {e}", exc_info=True)
        finally:
            self.recording = False
            logger.info(f"Soundcard recording thread finished.")

    def _background_recording_thread_sc(self, selected_device: Any, phrase_time_limit: float) -> None:
        """Background thread specifically for soundcard recording."""
        try:
            logger.info(f"Starting soundcard recording thread for {selected_device.name}")
            num_frames_to_record = int(self.sample_rate * phrase_time_limit)

            with selected_device.recorder(samplerate=self.sample_rate, channels=self.channels, blocksize=num_frames_to_record) as recorder:
                while self.recording:
                    data = recorder.record(numframes=num_frames_to_record)
                    if not self.recording:  # Check recording flag immediately after record returns
                        break

                    if data is not None and data.size > 0:
                        # Ensure data is float32 for consistency
                        if data.dtype != np.float32:
                            processed_data = data.astype(np.float32)
                        else:
                            processed_data = data.copy()

                        if self.callback_function:
                            try:
                                self.callback_function(processed_data)
                            except Exception as cb_err:
                                logger.error(f"Error in soundcard callback execution: {cb_err}", exc_info=True)

        except Exception as e:
            logger.error(f"Error in soundcard recording thread (_sc): {e}", exc_info=True)
        finally:
            self.recording = False
            logger.info(f"Soundcard recording thread (_sc) finished for {selected_device.name}.")

    def _stop_listening(self, wait_for_stop=True):
        """Stop the background listening thread.

        Args:
            wait_for_stop: If True, wait for the thread to stop
        """
        if self.recording:
            self.recording = False

            if wait_for_stop and self.recording_thread and self.recording_thread.is_alive():
                self.recording_thread.join(timeout=2.0)

            logger.info("Background listening stopped")
            return True
        return False


__all__ = ["RecordingMixin"]
