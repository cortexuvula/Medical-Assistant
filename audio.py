import os
import json
import uuid
import time
import logging
import threading
import queue
from io import BytesIO
import soundcard
import sounddevice as sd
import numpy as np
import wave
from pydub import AudioSegment
import requests
from typing import List, Optional, Callable, Any, Dict, Tuple, Union, TYPE_CHECKING
from pathlib import Path
from settings import SETTINGS
import tempfile
from stt_providers import BaseSTTProvider, DeepgramProvider, ElevenLabsProvider, GroqProvider, WhisperProvider

# Define AudioData type for annotations
class AudioData:
    """Simple class to mimic speech_recognition.AudioData for backward compatibility"""
    def __init__(self, frame_data, sample_rate, sample_width, channels=1):
        self.frame_data = frame_data
        self.sample_rate = sample_rate
        self.sample_width = sample_width
        self.channels = channels
        
    def get_raw_data(self) -> bytes:
        return self.frame_data

class AudioHandler:
    """Class to handle all audio-related functionality including recording, transcription, and file operations."""
    
    # Default audio chunk duration in seconds
    DEFAULT_PHRASE_TIME_LIMIT = 30
    
    # Track active listening sessions for proper cleanup
    _active_streams = []  # Class variable to track all active streams
    
    def __init__(self, elevenlabs_api_key: str = "", deepgram_api_key: str = "", recognition_language: str = "en-US", groq_api_key: str = ""):
        """Initialize the AudioHandler with necessary API keys and settings.
        
        Args:
            elevenlabs_api_key: API key for ElevenLabs
            deepgram_api_key: API key for Deepgram
            recognition_language: Language code for speech recognition
            groq_api_key: API key for GROQ (default STT provider)
        """
        self.elevenlabs_api_key = elevenlabs_api_key
        self.deepgram_api_key = deepgram_api_key
        self.groq_api_key = groq_api_key
        self.recognition_language = recognition_language
        
        # Initialize STT providers
        self.elevenlabs_provider = ElevenLabsProvider(elevenlabs_api_key, recognition_language)
        self.deepgram_provider = DeepgramProvider(deepgram_api_key, recognition_language)
        self.groq_provider = GroqProvider(groq_api_key, recognition_language)
        self.whisper_provider = WhisperProvider("", recognition_language)
        
        # Initialize fallback callback to None
        self.fallback_callback = None
        
        # Default audio parameters for recording
        self.sample_rate = 44100  # Hz
        self.channels = 1  # Mono
        self.sample_width = 2  # Bytes (16-bit)
        self.recording = False
        self.recording_thread = None
        self.recorded_frames = []
        self.callback_function = None
        self.listening_device = None
        
        # Silence detection threshold - can be adjusted dynamically
        self.silence_threshold = 0.001
        
        # Special SOAP mode flag
        self.soap_mode = False
        
    @property
    def whisper_available(self) -> bool:
        """Check if Whisper is available on the system.
        
        Returns:
            True if Whisper is available, False otherwise
        """
        return self.whisper_provider.is_available
        
    def set_stt_provider(self, provider: str) -> None:
        """Set the STT provider to use for transcription.
        
        Args:
            provider: Provider name ('elevenlabs', 'deepgram', 'groq', or 'whisper')
        """
        if provider in ["elevenlabs", "deepgram", "groq", "whisper"]:
            # Update the setting
            from settings import SETTINGS, save_settings
            SETTINGS["stt_provider"] = provider
            save_settings(SETTINGS)
            logging.info(f"STT provider set to {provider}")
        else:
            logging.warning(f"Unknown STT provider: {provider}")
        
    def combine_audio_segments(self, segments: List[AudioSegment]) -> Optional[AudioSegment]:
        """Combine multiple audio segments into a single segment efficiently.
        
        Args:
            segments: List of AudioSegment objects
            
        Returns:
            Combined AudioSegment or None if list is empty
        """
        if not segments:
            logging.warning("combine_audio_segments called with empty list")
            return None
            
        # Using sum() is significantly faster for combining many segments
        # than iterative concatenation with +=
        try:
            # Start with the first segment to ensure correct parameters (frame rate, channels, etc.)
            # Adding subsequent segments ensures compatibility.
            # Using sum directly might implicitly start with AudioSegment.empty(), 
            # which could lead to issues if segment parameters differ.
            combined = segments[0]
            if len(segments) > 1:
                 combined = sum(segments[1:], start=combined) # More explicit and safer than sum(segments)
            return combined
        except Exception as e:
            logging.error(f"Error combining audio segments: {e}", exc_info=True)
            # Fallback to original method in case of unexpected issues with sum()
            logging.info("Falling back to iterative concatenation due to error.")
            combined_fallback = segments[0]
            for segment in segments[1:]:
                combined_fallback += segment
            return combined_fallback

    def set_fallback_callback(self, callback: Callable) -> None:
        """Set the fallback callback for when transcription fails.
        
        Args:
            callback: Function to call when transcription fails
        """
        self.fallback_callback = callback
        
    def cleanup_resources(self) -> None:
        """Cleanup all audio resources before the application closes.
        
        This method ensures all audio streams are properly closed and resources
        are released to prevent issues on application restart.
        """
        logging.info("AudioHandler: Cleaning up audio resources...")
        
        # Clean up any active streams from the class list
        while AudioHandler._active_streams:
            try:
                stop_func = AudioHandler._active_streams.pop()
                if callable(stop_func):
                    logging.info("AudioHandler: Stopping active stream")
                    stop_func(wait_for_stop=True)
                    # Give it a tiny bit of time to fully release resources
                    time.sleep(0.1)
            except Exception as e:
                logging.error(f"AudioHandler: Error stopping stream: {str(e)}", exc_info=True)
        
        # Terminate sounddevice streams if any are active
        try:
            logging.info("AudioHandler: Ensuring sounddevice streams are closed")
            sd.stop()
        except Exception as e:
            logging.error(f"AudioHandler: Error stopping sounddevice: {str(e)}", exc_info=True)
            
        # Reset any internal state variables that might persist
        self.soap_mode = False
        
        # Final log indication that cleanup is complete
        logging.info("AudioHandler: Audio resources cleanup complete")

    def transcribe_audio(self, segment: AudioSegment) -> str:
        """Transcribe audio using selected provider with fallback options.
        
        Args:
            segment: AudioSegment to transcribe
            
        Returns:
            Transcription text or empty string if transcription failed
        """
        # Check if there's a prefix audio file to prepend
        prefix_audio_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prefix_audio.mp3")
        if os.path.exists(prefix_audio_path):
            try:
                # Load the prefix audio
                logging.info(f"Found prefix audio at {prefix_audio_path}, prepending to recording")
                prefix_segment = AudioSegment.from_file(prefix_audio_path)
                
                # Prepend the prefix audio to the segment
                combined_segment = prefix_segment + segment
                
                # Use the combined segment for transcription
                segment = combined_segment
                logging.info(f"Successfully prepended prefix audio (length: {len(prefix_segment)}ms) to recording")
            except Exception as e:
                logging.error(f"Error prepending prefix audio: {e}", exc_info=True)
                # Continue with original segment if there's an error
        
        # Get the selected STT provider from settings
        primary_provider = SETTINGS.get("stt_provider", "deepgram")
        
        # Track if we've already tried fallback options
        fallback_attempted = False
        
        # First attempt with selected provider
        transcript = self._try_transcription_with_provider(segment, primary_provider)
        
        # Only use fallback if there's an actual error (empty string)
        # For successful API calls that return a result (even placeholders like "[Silence...]"), 
        # we'll keep that result and not fall back
        if transcript == "" and not fallback_attempted:
            fallback_providers = ["deepgram", "elevenlabs", "groq", "whisper"]
            # Remove primary provider from fallbacks to avoid duplicate attempt
            if primary_provider in fallback_providers:
                fallback_providers.remove(primary_provider)
                
            for provider in fallback_providers:
                logging.info(f"Trying fallback provider: {provider}")
                
                # Notify UI about fallback through callback
                if self.fallback_callback:
                    self.fallback_callback(primary_provider, provider)
                
                transcript = self._try_transcription_with_provider(segment, provider)
                if transcript != "":
                    logging.info(f"Transcription successful with fallback provider: {provider}")
                    break
                    
        return transcript or ""  # Return empty string if all providers failed

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
                logging.warning(f"Unknown provider: {provider}")
                return ""
                
        except Exception as e:
            logging.error(f"Error with {provider} transcription: {str(e)}", exc_info=True)
            return ""

    def process_audio_data(self, audio_data: Union[AudioData, np.ndarray]) -> tuple[Optional[AudioSegment], str]:
        """Process audio data to get an AudioSegment and transcription.
        
        Args:
            audio_data: AudioData object or numpy array from sounddevice
            
        Returns:
            Tuple of (AudioSegment, transcription_text)
        """
        try:
            # Handle different input types
            if isinstance(audio_data, AudioData):
                # Legacy AudioData handling
                channels = getattr(audio_data, "channels", 1)
                sample_width = getattr(audio_data, "sample_width", None)
                sample_rate = getattr(audio_data, "sample_rate", None)
                
                # Log diagnostic info
                logging.debug(f"Processing legacy AudioData: channels={channels}, width={sample_width}, rate={sample_rate}")
                
                # Validate audio data
                if not audio_data.get_raw_data():
                    logging.warning("Empty audio data received")
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
                logging.debug(f"Processing sounddevice audio: shape={audio_data.shape}, dtype={audio_data.dtype}")
                
                # Validate audio data
                if audio_data.size == 0:
                    logging.warning("Empty audio data received")
                    return None, ""
                
                # Check amplitude and apply gain boost for Voicemeeter outputs
                max_amp = np.abs(audio_data).max()
                logging.debug(f"Audio max amplitude before processing: {max_amp:.6f}")
                
                # For Voicemeeter devices or in SOAP mode, apply gain boost
                if (self.listening_device and "voicemeeter" in str(self.listening_device).lower()) or self.soap_mode:
                    # In SOAP mode, apply much higher gain boost
                    if self.soap_mode:
                        boost_factor = 50.0  # More aggressive boost in SOAP mode
                        logging.debug(f"SOAP mode: Applying aggressive boost factor of {boost_factor}x")
                    else:
                        boost_factor = 10.0  # Standard boost for Voicemeeter
                        logging.debug(f"Applying standard boost factor of {boost_factor}x for Voicemeeter")
                    
                    # Apply the boost
                    audio_data = audio_data * boost_factor
                    
                    # Log the new max amplitude
                    new_max_amp = np.abs(audio_data).max()
                    logging.debug(f"After gain boost: max amplitude is now {new_max_amp:.6f}")
                
                # Skip if amplitude is still too low after boosting
                # Use a more permissive threshold for SOAP mode
                effective_threshold = self.silence_threshold if self.soap_mode else 0.001
                if np.abs(audio_data).max() < effective_threshold:
                    logging.warning(f"Audio level still too low after boost: {np.abs(audio_data).max():.6f}")
                    return None, ""
                
                # Convert float32 to int16 for compatibility
                if audio_data.dtype == np.float32:
                    audio_int16 = (audio_data * 32767).astype(np.int16)
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
                logging.error(f"Unsupported audio data type: {type(audio_data)}")
                return None, ""
            
            # Get transcript
            transcript = self.transcribe_audio(segment)
            
            return segment, transcript
                
        except Exception as e:
            error_msg = f"Audio processing error: {str(e)}"
            logging.error(error_msg, exc_info=True)
            return None, ""

    def load_audio_file(self, file_path: str) -> tuple[Optional[AudioSegment], str]:
        """Load and transcribe audio from a file.
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Tuple of (AudioSegment, transcription_text)
        """
        try:
            if (file_path.lower().endswith(".mp3")):
                seg = AudioSegment.from_file(file_path, format="mp3")
            elif (file_path.lower().endswith(".wav")):
                seg = AudioSegment.from_file(file_path, format="wav")
            else:
                raise ValueError("Unsupported audio format. Only .wav and .mp3 supported.")
                
            transcript = self.transcribe_audio(seg)
            return seg, transcript
            
        except Exception as e:
            logging.error(f"Error loading audio file: {str(e)}", exc_info=True)
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
                logging.warning("No audio segments to save")
                return False
                
            combined = self.combine_audio_segments(segments)
            if combined:
                # Ensure directory exists
                Path(file_path).parent.mkdir(parents=True, exist_ok=True)
                combined.export(file_path, format="mp3")
                logging.info(f"Audio saved to {file_path}")
                return True
            return False
        except Exception as e:
            logging.error(f"Error saving audio: {str(e)}", exc_info=True)
            return False
            
    def get_input_devices(self) -> List[Dict[str, Any]]:
        """Get a list of available input devices using soundcard.
        
        Returns:
            List of dictionaries with device information (name, id, etc.)
        """
        try:
            devices = []
            # Get all microphones from soundcard
            mics = soundcard.all_microphones(include_loopback=False)
            
            for i, mic in enumerate(mics):
                device_info = {
                    "id": i,  # Index for use with sounddevice
                    "name": mic.name,
                    "channels": mic.channels,
                    "object": mic  # Store the actual soundcard mic object
                }
                devices.append(device_info)
                
            return devices
        except Exception as e:
            logging.error(f"Error getting input devices: {str(e)}", exc_info=True)
            return []
            
    def listen_in_background(self, mic_name: str, callback: Callable, phrase_time_limit: Optional[int] = None) -> Callable:
        """Start listening in the background for phrases.
        
        Args:
            mic_name: Name of the microphone to use
            callback: Function to call for each detected phrase
            phrase_time_limit: Max seconds for a phrase, or None for no limit
            
        Returns:
            Function that when called stops the background listener
        """
        # Use the default phrase time limit if none is provided
        if phrase_time_limit is None:
            phrase_time_limit = self.DEFAULT_PHRASE_TIME_LIMIT
            
        # Log the actual phrase time limit being used
        logging.info(f"Starting background listening with phrase_time_limit: {phrase_time_limit} seconds")
        try:
            logging.info(f"Attempting to start background listening for device: {mic_name}")
            self.listening_device = mic_name # Store the requested name
            self.callback_function = callback # Store callback

            # Determine if sounddevice should be used (typically for Voicemeeter/virtual cables)
            # or if soundcard should be attempted (for physical devices, though problematic).
            # Let's prefer sounddevice if possible as it seems more reliable with indexing.
            use_sounddevice = True # Default to sounddevice for now based on previous issues

            # Optional: Add logic here if we want to try soundcard for specific non-Voicemeeter devices
            # is_voicemeeter = "voicemeeter" in mic_name.lower() or "vb-audio" in mic_name.lower()
            # if not is_voicemeeter:
            #    use_sounddevice = False

            if use_sounddevice:
                logging.info(f"Using sounddevice backend for: {mic_name}")
                # Delegate to the sounddevice-specific method, passing the name
                stop_function = self._listen_with_sounddevice(mic_name, callback, phrase_time_limit)
                return stop_function
            else:
                # --- Soundcard Logic (currently disabled, potentially problematic) ---
                logging.info(f"Attempting to use soundcard backend for: {mic_name}")
                mics = soundcard.all_microphones(include_loopback=True)
                selected_sc_device = None
                for mic in mics:
                    # Need a robust way to match mic_name to soundcard mic object name
                    if mic_name in mic.name: # Simple substring match, might be fragile
                        selected_sc_device = mic
                        logging.info(f"Found soundcard match: {mic.name}")
                        break

                if not selected_sc_device:
                    logging.error(f"Could not find a matching soundcard device for '{mic_name}'. Falling back to sounddevice.")
                    # Fallback to sounddevice if soundcard match fails
                    return self._listen_with_sounddevice(mic_name, callback, phrase_time_limit)

                # Start recording thread using soundcard
                self.recording = True
                self.recorded_frames = []
                self.recording_thread = threading.Thread(
                    target=self._background_recording_thread_sc,
                    args=(selected_sc_device, phrase_time_limit), # Pass soundcard device object
                    daemon=True
                )
                self.recording_thread.start()
                logging.info(f"Started soundcard background thread for {selected_sc_device.name}")
                return lambda wait_for_stop=True: self._stop_listening(wait_for_stop)

        except Exception as e:
            logging.error(f"Error in listen_in_background for '{mic_name}': {e}", exc_info=True)
            # Return a no-op function on error
            return lambda wait_for_stop=True: None

    def _listen_with_sounddevice(self, device_name: str, callback: Callable, phrase_time_limit: int = None) -> Callable:
        """Listen using sounddevice library, resolving name to index just-in-time.

        Args:
            device_name: The target device name string.
            callback: Function to call with audio data.
            phrase_time_limit: Maximum length of audio capture in seconds (uses DEFAULT_PHRASE_TIME_LIMIT if None).

        Returns:
            Function to stop listening.
        """
        # Use the default phrase time limit if none is provided
        if phrase_time_limit is None:
            phrase_time_limit = self.DEFAULT_PHRASE_TIME_LIMIT
        stream = None # Initialize stream variable
        try:
            self.listening_device = device_name # Store the name being used
            self.callback_function = callback # Store callback

            # --- JIT Device Index Resolution ---
            logging.info(f"Resolving sounddevice index for: '{device_name}'")
            devices = sd.query_devices()
            device_id = None

            # Log available devices for debugging
            logging.debug("Sounddevice List for Index Resolution:")
            input_device_indices = []
            for i, dev in enumerate(devices):
                is_input = dev['max_input_channels'] > 0
                logging.debug(f"  [{i}] {dev['name']} (In={is_input}, Chan={dev['max_input_channels']}) HostAPI: {dev['hostapi']}")
                if is_input:
                    input_device_indices.append(i)

            # 1. Try exact name match
            for i in input_device_indices:
                if devices[i]['name'] == device_name:
                    device_id = i
                    logging.info(f"Exact match found: Index={device_id}, Name='{devices[i]['name']}'")
                    break

            # 2. If no exact match, try case-insensitive match
            if device_id is None:
                for i in input_device_indices:
                    if devices[i]['name'].lower() == device_name.lower():
                        device_id = i
                        logging.info(f"Case-insensitive match found: Index={device_id}, Name='{devices[i]['name']}'")
                        break
            
            # 3. Try partial match (e.g., user selected "Microphone (Realtek)" but sd lists "Microphone (Realtek High Definition Audio)")
            if device_id is None:
                 for i in input_device_indices:
                     if device_name in devices[i]['name']:
                         device_id = i
                         logging.info(f"Partial match found: Index={device_id}, Name='{devices[i]['name']}'")
                         break # Take the first partial match

            # 4. Handle failure to find device
            if device_id is None:
                logging.error(f"Could not find '{device_name}' in sounddevice input list. Available devices logged above.")
                # Attempt to use default input device as a fallback
                try:
                    default_input = sd.query_devices(kind='input')
                    if default_input and isinstance(default_input, dict) and 'index' in default_input:
                       device_id = default_input['index']
                       logging.warning(f"Falling back to default sounddevice input: Index={device_id}, Name='{default_input['name']}'")
                    else:
                         raise ValueError("Could not find specified or default sounddevice input device.")
                except Exception as e_def:
                    logging.error(f"Failed to get default sounddevice input: {e_def}")
                    raise ValueError(f"Device '{device_name}' not found and default could not be determined.")
            # --- End JIT Resolution ---

            device_info = devices[device_id]
            channels = 1 # Default to mono
            try:
                channels = int(device_info['max_input_channels'])
                # Clamp channels to 1 or 2 if device supports more, prefer mono
                if channels >= 2:
                     channels = 1 # Force mono for simplicity unless stereo is required
                     logging.info(f"Device supports {device_info['max_input_channels']} channels, using {channels} for recording.")
                elif channels == 0:
                    logging.warning(f"Device '{device_info['name']}' reports 0 input channels, forcing to 1.")
                    channels = 1
            except Exception as e:
                logging.warning(f"Error determining channel count for {device_info['name']}: {e}. Defaulting to {channels}.")

            self.channels = channels # Store the actual channels being used
            self.sample_rate = int(device_info.get('default_samplerate', 44100))
            buffer_size = int(self.sample_rate * phrase_time_limit) # Use phrase_time_limit for buffer

            logging.info(f"Creating sounddevice InputStream: DeviceID={device_id}, Name='{device_info['name']}', Rate={self.sample_rate}, Channels={self.channels}, Buffer={buffer_size}")

            # Buffer to accumulate audio data until it reaches phrase_time_limit
            accumulated_data = []
            accumulated_frames = 0
            target_frames = int(self.sample_rate * phrase_time_limit)
            
            logging.info(f"Audio will accumulate until {target_frames} frames (approx. {phrase_time_limit} seconds) before processing")

            # --- Internal Audio Callback ---
            # This runs in a separate thread managed by sounddevice
            def audio_callback_sd(indata: np.ndarray, frames: int, time: Any, status: sd.CallbackFlags) -> None:
                nonlocal accumulated_data, accumulated_frames
                
                if status:
                    # Log PortAudio statuses: https://python-sounddevice.readthedocs.io/en/0.4.6/api/status.html
                    logging.warning(f"sounddevice status: {status}")
                try:
                    # Make a copy to avoid issues with buffer overwriting
                    audio_data_copy = indata.copy()
                    
                    # Add to accumulated buffer
                    accumulated_data.append(audio_data_copy)
                    accumulated_frames += frames
                    
                    # Only call the callback when we've accumulated enough data
                    # or if the SOAP recording was just stopped (to ensure we process remaining data)
                    if accumulated_frames >= target_frames or not self.callback_function:
                        if self.callback_function and accumulated_data:
                            # Combine all accumulated chunks
                            combined_data = np.vstack(accumulated_data) if len(accumulated_data) > 1 else accumulated_data[0]
                            # Call the callback with the combined data
                            self.callback_function(combined_data)
                            
                            # Reset for next accumulation
                            accumulated_data = []
                            accumulated_frames = 0
                except Exception as e_cb:
                    logging.error(f"Error in sounddevice audio_callback_sd: {e_cb}", exc_info=True)
                    # Reset accumulation on error
                    accumulated_data = []
                    accumulated_frames = 0
            # --- End Internal Audio Callback ---

            stream = sd.InputStream(
                samplerate=self.sample_rate,
                device=device_id,
                channels=self.channels,
                callback=audio_callback_sd,
                blocksize=0, # Let sounddevice choose optimal block size based on buffer
                dtype='float32' # Use float32 as it's common and allows easy amplitude checks
                # latency='low' # Optional: can try 'low' latency if needed
            )
            stream.start()
            logging.info(f"sounddevice InputStream started for '{device_info['name']}'")

            # Define the stop function specific to this stream
            def stop_stream(wait_for_stop: bool = False) -> None: # wait_for_stop isn't used by sounddevice stream.stop
                nonlocal stream, accumulated_data, accumulated_frames
                if stream:
                    try:
                        # Process any remaining accumulated data before stopping
                        if self.callback_function and accumulated_data:
                            try:
                                combined_data = np.vstack(accumulated_data) if len(accumulated_data) > 1 else accumulated_data[0]
                                self.callback_function(combined_data)
                                logging.info(f"Processed final audio chunk of {accumulated_frames} frames before stopping")
                            except Exception as e_final:
                                logging.error(f"Error processing final audio chunk: {e_final}", exc_info=True)
                        
                        # Reset accumulation buffers
                        accumulated_data = []
                        accumulated_frames = 0
                        
                        if not stream.stopped:
                            stream.stop()
                            logging.info(f"sounddevice InputStream stopped for '{self.listening_device}'")
                        stream.close()
                        logging.info(f"sounddevice InputStream closed for '{self.listening_device}'")
                    except Exception as e_stop:
                        logging.error(f"Error stopping/closing sounddevice stream: {e_stop}", exc_info=True)
                    finally:
                        stream = None
                        self.listening_device = None
                        self.callback_function = None
            
            return stop_stream # Return the specific closer for this stream

        except sd.PortAudioError as pae:
            logging.error(f"PortAudioError in _listen_with_sounddevice for '{device_name}': {pae}")
            logging.error(f"PortAudio error details: Host Error={pae.hostApiErrorInfo}")
            raise ValueError(f"Audio device error for '{device_name}': {pae}") from pae
        except Exception as e:
            logging.error(f"Error in _listen_with_sounddevice for '{device_name}': {e}", exc_info=True)
            # Clean up stream if it was partially created
            if stream:
                 try:
                     if not stream.stopped: stream.stop()
                     stream.close()
                 except Exception as e_clean:
                     logging.error(f"Error during cleanup in _listen_with_sounddevice: {e_clean}")
            raise e # Re-raise the exception

    def _background_recording_thread(self, device_index: int, phrase_time_limit: float) -> None:
        """ Background thread that records audio using soundcard (potentially problematic). """
        # This method seems deprecated in favor of _listen_with_sounddevice and soundcard issues
        # Keeping it for reference but should likely be removed or refactored if soundcard is needed.
        logging.warning("_background_recording_thread (soundcard) is likely deprecated.")
        try:
            # Simplified - assumes device_index corresponds to soundcard's list which might not be true
            mic = soundcard.get_microphone(device_index, include_loopback=True)
            if not mic:
                logging.error(f"Soundcard could not get microphone for index {device_index}")
                self.recording = False
                return

            logging.info(f"Starting soundcard recording thread for {mic.name}")
            with mic.recorder(samplerate=self.sample_rate, channels=self.channels) as recorder:
                while self.recording:
                    # Record data for the phrase time limit
                    # Note: soundcard's record method blocks, which might not be ideal for continuous listening
                    data = recorder.record(numframes=int(self.sample_rate * phrase_time_limit))
                    if not self.recording: # Check again after blocking call
                        break
                    if data is not None and data.size > 0:
                         # Convert soundcard data (usually float64) to float32 if needed
                        if data.dtype != np.float32:
                            data = data.astype(np.float32)
                        logging.debug(f"Soundcard recorded chunk: Shape={data.shape}, Dtype={data.dtype}")
                        if self.callback_function:
                            self.callback_function(data)
                    else:
                        logging.debug("Soundcard recorder yielded empty data chunk.")
                        time.sleep(0.01) # Small sleep if no data

        except Exception as e:
            logging.error(f"Error in soundcard recording thread: {e}", exc_info=True)
        finally:
            self.recording = False
            logging.info(f"Soundcard recording thread finished.")

    # --- Add a separate method for soundcard if needed ---
    def _background_recording_thread_sc(self, selected_device: Any, phrase_time_limit: float) -> None:
        """Background thread specifically for soundcard recording."""
        try:
            logging.info(f"Starting soundcard recording thread for {selected_device.name}")
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
                        
                        # logging.debug(f"Soundcard SC thread recorded chunk: Shape={processed_data.shape}, Dtype={processed_data.dtype}")
                        
                        if self.callback_function:
                            try:
                                self.callback_function(processed_data)
                            except Exception as cb_err:
                                logging.error(f"Error in soundcard callback execution: {cb_err}", exc_info=True)
                    # else:
                    #     logging.debug("Soundcard recorder SC thread yielded no data or recording stopped during record.")
                    #     time.sleep(0.01) # Prevent busy-waiting if record returns None quickly

        except Exception as e:
            logging.error(f"Error in soundcard recording thread (_sc): {e}", exc_info=True)
        finally:
            self.recording = False
            logging.info(f"Soundcard recording thread (_sc) finished for {selected_device.name}.")

    def add_segment(self, audio_data: np.ndarray) -> None:
        """
        Add an audio segment to the list of segments.

        Args:
            audio_data: Audio data as a numpy array.
        """
        try:
            if audio_data is None:
                logging.warning("SOAP recording: Received None audio data")
                return
                
            # Check if the audio data has a valid shape and type
            if not hasattr(audio_data, 'shape'):
                logging.warning(f"SOAP recording: No audio segment created from data of type {type(audio_data)}")
                return
                
            # Get the maximum amplitude
            max_amp = np.max(np.abs(audio_data)) if audio_data.size > 0 else 0.0
            
            # Always log the max amplitude for debugging
            if max_amp > 0.0:
                logging.info(f"SOAP recording: Audio segment with max amplitude {max_amp:.6f}")
            else:
                logging.warning(f"SOAP recording: Max amplitude was {max_amp}")
            
            # Apply an aggressive boost to ensure we capture even quiet audio
            if max_amp > 0.0001 and max_amp < 0.1:  # There's some audio but it's quiet
                boost_factor = min(20.0, 0.5 / max_amp)  # Very high boost for quiet audio
                audio_data = audio_data * boost_factor
                logging.info(f"SOAP recording: Boosted audio by factor {boost_factor:.2f}")
                
            # For SOAP mode, always create a segment regardless of amplitude
            # This is crucial for ensuring the recording works even with very quiet audio
            if self.soap_mode or max_amp > 0.0001:  # Ultra-low threshold or SOAP mode
                # Convert float32 to int16 for compatibility
                if audio_data.dtype == np.float32:
                    audio_int16 = (audio_data * 32767).astype(np.int16)
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
                logging.info(f"SOAP recording: Created segment, total segments: {len(self.recorded_frames)}")
                
                if self.callback_function:
                    try:
                        self.callback_function(segment)
                    except Exception as e:
                        logging.error(f"Error in new segment callback: {e}")
            else:
                logging.warning(f"SOAP recording: Amplitude {max_amp:.8f} too low to create segment")
                
        except Exception as e:
            logging.error(f"Error adding segment: {e}", exc_info=True)

    def _stop_listening(self, wait_for_stop=True):
        """Stop the background listening thread.
        
        Args:
            wait_for_stop: If True, wait for the thread to stop
        """
        if self.recording:
            self.recording = False
            
            if wait_for_stop and self.recording_thread and self.recording_thread.is_alive():
                self.recording_thread.join(timeout=2.0)
                
            logging.info("Background listening stopped")
            return True
        return False
