import os
import time
import logging
import threading
import numpy as np
import platform
from pydub import AudioSegment
from typing import List, Optional, Callable, Any, Dict, Tuple, Union
from pathlib import Path
from settings.settings import SETTINGS
from stt_providers import DeepgramProvider, ElevenLabsProvider, GroqProvider, WhisperProvider
from core.config import get_config
from audio.constants import (
    DEFAULT_SAMPLE_RATE,
    DEFAULT_SAMPLE_WIDTH,
    DEFAULT_CHANNELS,
    SAMPLE_WIDTH_16BIT,
)

# Try to import audio.audio libraries - they may fail in CI environments
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
    
    # Get configuration
    _config = get_config()
    
    # Default audio chunk duration in seconds
    DEFAULT_PHRASE_TIME_LIMIT = _config.transcription.chunk_duration_seconds
    
    # Track active listening sessions for proper cleanup
    _active_streams = {}  # Class variable to track all active streams by purpose
    
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
        self.sample_rate = DEFAULT_SAMPLE_RATE  # Hz - Higher sample rate for better quality
        self.channels = DEFAULT_CHANNELS  # Mono
        self.sample_width = DEFAULT_SAMPLE_WIDTH  # Bytes (16-bit)
        self.recording = False
        self.recording_thread = None
        self.recorded_frames = []
        self.callback_function = None
        self.listening_device = None
        
        # Silence detection threshold - can be adjusted dynamically
        self.silence_threshold = 0.001
        
        # Special SOAP mode flag
        self.soap_mode = False
        
        # Cache for prefix audio to avoid repeated file loading
        self._prefix_audio_cache = None
        self._prefix_audio_checked = False
        
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
            from settings.settings import SETTINGS, save_settings
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
        logging.debug("AudioHandler: Cleaning up audio resources...")
        
        # Clean up any active streams from the class list
        streams_closed = 0
        stream_purposes = list(AudioHandler._active_streams.keys())
        for purpose in stream_purposes:
            try:
                stream_info = AudioHandler._active_streams.pop(purpose, None)
                if stream_info and 'stream' in stream_info:
                    stream = stream_info['stream']
                    stream.stop()
                    stream.close()
                    streams_closed += 1
                    # Give it a tiny bit of time to fully release resources
                    time.sleep(0.1)
            except Exception as e:
                logging.error(f"AudioHandler: Error stopping stream for {purpose}: {str(e)}", exc_info=True)
        
        # Terminate sounddevice streams if any are active
        try:
            sd.stop()
        except Exception as e:
            logging.error(f"AudioHandler: Error stopping sounddevice: {str(e)}", exc_info=True)
            
        # Reset any internal state variables that might persist
        self.soap_mode = False
        
        # Single summary log
        if streams_closed > 0:
            logging.info(f"AudioHandler: Cleanup complete, {streams_closed} stream(s) closed")
    
    def reset_prefix_audio_cache(self) -> None:
        """Reset the prefix audio cache to force reloading.
        
        Call this after recording new prefix audio to ensure it's used.
        """
        self._prefix_audio_cache = None
        self._prefix_audio_checked = False
        logging.info("Prefix audio cache reset - will reload on next use")

    def transcribe_audio_without_prefix(self, segment: AudioSegment) -> str:
        """Transcribe audio using selected provider without adding prefix audio.
        
        This method is used for conversational transcription where medical
        terminology prefix is not needed (e.g., translation dialog).
        
        Args:
            segment: AudioSegment to transcribe
            
        Returns:
            Transcription text or empty string if transcription failed
        """
        # Get the selected STT provider from settings
        primary_provider = SETTINGS.get("stt_provider", "deepgram")
        
        # Track if we've already tried fallback options
        fallback_attempted = False
        
        # First attempt with selected provider
        transcript = self._try_transcription_with_provider(segment, primary_provider)
        
        # Only use fallback if there's an actual error (empty string)
        # For successful API calls that return a result (even placeholders like "[Silence...]"), 
        # we don't want to retry with different providers
        if transcript == "" and self.fallback_callback and not fallback_attempted:
            logging.info("Primary STT provider failed, attempting fallback")
            fallback_attempted = True
            
            # Try fallback providers
            fallback_providers = [p for p in ["groq", "deepgram", "elevenlabs"] if p != primary_provider]
            for provider in fallback_providers:
                transcript = self._try_transcription_with_provider(segment, provider)
                if transcript:
                    logging.info(f"Fallback to {provider} successful")
                    break
        
        return transcript
    
    def transcribe_audio(self, segment: AudioSegment) -> str:
        """Transcribe audio using selected provider with fallback options.
        
        Args:
            segment: AudioSegment to transcribe
            
        Returns:
            Transcription text or empty string if transcription failed
        """
        # Check if there's a prefix audio file to prepend (use cache to avoid repeated loading)
        if not self._prefix_audio_checked:
            self._prefix_audio_checked = True
            from managers.data_folder_manager import data_folder_manager
            prefix_audio_path = str(data_folder_manager.app_data_folder / "prefix_audio.mp3")
            logging.debug(f"Checking for prefix audio at: {prefix_audio_path}")
            if os.path.exists(prefix_audio_path):
                try:
                    # Load the prefix audio once and cache it
                    logging.info(f"Loading prefix audio from {prefix_audio_path}")
                    self._prefix_audio_cache = AudioSegment.from_file(prefix_audio_path)
                    logging.info(f"Cached prefix audio (length: {len(self._prefix_audio_cache)}ms)")
                except Exception as e:
                    logging.error(f"Error loading prefix audio: {e}", exc_info=True)
                    self._prefix_audio_cache = None
            else:
                logging.debug(f"No prefix audio file found at: {prefix_audio_path}")
        
        # If we have cached prefix audio, prepend it
        if self._prefix_audio_cache:
            try:
                # Prepend the prefix audio to the segment
                combined_segment = self._prefix_audio_cache + segment
                # Use the combined segment for transcription
                segment = combined_segment
                logging.debug("Successfully prepended cached prefix audio to recording")
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
                
                # Check if audio is already clipping
                if max_amp >= 0.99:
                    logging.warning(f"Input audio is clipping! Max amplitude: {max_amp:.6f}")
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
                            logging.debug(f"SOAP mode: Applying boost factor of {boost_factor:.2f}x")
                        else:
                            boost_factor = min(5.0, 0.8 / max_amp)  # Standard boost for Voicemeeter
                            logging.debug(f"Applying boost factor of {boost_factor:.2f}x for Voicemeeter")
                        
                        # Apply the boost
                        audio_data = audio_data * boost_factor
                        
                        # Log the new max amplitude
                        new_max_amp = np.abs(audio_data).max()
                        logging.debug(f"After gain boost: max amplitude is now {new_max_amp:.6f}")
                    else:
                        logging.debug(f"Audio level sufficient ({max_amp:.3f}), no boost needed")
                
                # Skip if amplitude is still too low after boosting
                # Use a more permissive threshold for SOAP mode
                effective_threshold = self.silence_threshold if self.soap_mode else 0.001
                if np.abs(audio_data).max() < effective_threshold:
                    logging.warning(f"Audio level still too low after boost: {np.abs(audio_data).max():.6f}")
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
                try:
                    # Ensure directory exists
                    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
                except Exception as dir_e:
                    logging.error(f"Failed to create directory for {file_path}: {str(dir_e)}")
                    return False
                    
                logging.info(f"Exporting audio to {file_path} with format=mp3, bitrate=192k")
                combined.export(file_path, format="mp3", bitrate="192k")
                
                # Verify file was created
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    logging.info(f"Audio successfully saved to {file_path} (size: {file_size} bytes)")
                else:
                    logging.error(f"Audio export completed but file not found at {file_path}")
                    return False
                    
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
            if not SOUNDCARD_AVAILABLE:
                self.logger.warning("Soundcard not available, returning empty device list")
                return []
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
        # Use the default phrase time limit if none is provided
        if phrase_time_limit is None:
            phrase_time_limit = self.DEFAULT_PHRASE_TIME_LIMIT
            
        # Log the actual phrase time limit being used
        logging.info(f"Starting background listening with phrase_time_limit: {phrase_time_limit} seconds")
        
        # Check if a stream with this purpose already exists
        if stream_purpose in self._active_streams:
            logging.warning(f"Stream with purpose '{stream_purpose}' already exists. Stopping existing stream.")
            # Get the existing stream info
            existing_info = self._active_streams.get(stream_purpose)
            if existing_info and 'stream' in existing_info:
                try:
                    existing_info['stream'].stop()
                    existing_info['stream'].close()
                except Exception as e:
                    logging.error(f"Error stopping existing stream: {e}")
            self._active_streams.pop(stream_purpose, None)
        
        try:
            logging.info(f"Attempting to start background listening for device: {mic_name}")
            self.listening_device = mic_name # Store the requested name
            self.callback_function = callback # Store callback

            # Determine if sounddevice should be used (typically for Voicemeeter/virtual cables)
            # or if soundcard should be attempted (for physical devices, though problematic).
            # Let's prefer sounddevice if possible as it seems more reliable with indexing.
            use_sounddevice = True # Default to sounddevice for now based on previous issues


            if use_sounddevice:
                logging.info(f"Using sounddevice backend for: {mic_name}")
                # Delegate to the sounddevice-specific method, passing the name
                stop_function = self._listen_with_sounddevice(mic_name, callback, phrase_time_limit, stream_purpose)
                return stop_function
            else:
                # --- Soundcard Logic (currently disabled, potentially problematic) ---
                logging.info(f"Attempting to use soundcard backend for: {mic_name}")
                if not SOUNDCARD_AVAILABLE:
                    logging.error("Soundcard not available, cannot use soundcard backend")
                    return lambda: None
                try:
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
                        return self._listen_with_sounddevice(mic_name, callback, phrase_time_limit, stream_purpose)
                except Exception as e:
                    logging.error(f"Soundcard backend failed: {e}. Falling back to sounddevice.")
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
            return lambda _=True: None

    def _resolve_device_index(self, device_name: str) -> Optional[int]:
        """Resolve device name to sounddevice index.
        
        Args:
            device_name: The target device name string.
            
        Returns:
            Device index or None if not found.
        """
        logging.debug(f"Resolving sounddevice index for: '{device_name}'")
        devices = sd.query_devices()
        device_id = None
        current_platform = platform.system().lower()

        # Build list of input devices
        input_device_indices = []
        for i, dev in enumerate(devices):
            is_input = dev['max_input_channels'] > 0
            if is_input:
                input_device_indices.append(i)

        # 1. Try exact name match
        for i in input_device_indices:
            if devices[i]['name'] == device_name:
                device_id = i
                logging.debug(f"Exact match found: Index={device_id}, Name='{devices[i]['name']}'")
                break

        # 2. If no exact match, try case-insensitive match
        if device_id is None:
            for i in input_device_indices:
                if devices[i]['name'].lower() == device_name.lower():
                    device_id = i
                    logging.debug(f"Case-insensitive match found: Index={device_id}, Name='{devices[i]['name']}'")
                    break
        
        # 3. Try partial match
        if device_id is None:
            for i in input_device_indices:
                if device_name in devices[i]['name'] or devices[i]['name'] in device_name:
                    device_id = i
                    logging.debug(f"Partial match found: Index={device_id}, Name='{devices[i]['name']}'")
                    break
        
        # 3.5 Platform-specific matching
        if device_id is None and current_platform == 'windows':
            # On Windows, try matching without WASAPI/WDM suffixes
            device_name_clean = device_name.replace(' (Device ', '|').split('|')[0]
            for i in input_device_indices:
                dev_name = devices[i]['name']
                # Remove Windows API suffixes for comparison
                dev_name_clean = dev_name
                for suffix in [' (Windows WASAPI)', ' (Windows WDM-KS)', ' (Windows DirectSound)']:
                    dev_name_clean = dev_name_clean.replace(suffix, '')
                
                if device_name_clean.lower() in dev_name_clean.lower() or dev_name_clean.lower() in device_name_clean.lower():
                    device_id = i
                    logging.debug(f"Windows platform match found: Index={device_id}, Name='{devices[i]['name']}'")
                    break
        
        # 4. Special handling for device names with "(Device X)" suffix
        if device_id is None and "(Device " in device_name:
            # Extract device index from name like "HDA Intel PCH: 92HD95 Analog (hw:0,0) (Device 0)"
            try:
                import re
                match = re.search(r'\(Device (\d+)\)', device_name)
                if match:
                    potential_id = int(match.group(1))
                    if potential_id in input_device_indices:
                        device_id = potential_id
                        logging.info(f"Extracted device index from name: Index={device_id}, Name='{devices[device_id]['name']}'")
            except Exception as e:
                logging.debug(f"Failed to extract device index from name: {e}")

        if device_id is None:
            logging.error(f"Could not find device '{device_name}' in sounddevice list")
            
        return device_id

    def _setup_audio_parameters(self, device_id: int) -> Tuple[int, int]:
        """Setup audio parameters for the device.
        
        Args:
            device_id: The sounddevice device index.
            
        Returns:
            Tuple of (channels, sample_rate).
        """
        device_info = sd.query_devices(device_id)
        
        # Determine optimal channel count
        channels = 1  # Default to mono
        max_channels = device_info.get('max_input_channels', 1)
        
        try:
            # Try to use mono if available
            if max_channels >= 1:
                channels = 1
            else:
                logging.warning(f"Device {device_info['name']} reports {max_channels} input channels")
        except Exception as e:
            logging.warning(f"Error determining channel count for {device_info['name']}: {e}. Defaulting to {channels}.")

        self.channels = channels
        # Use 48000 Hz for better quality, falling back to device default if not supported
        device_default = int(device_info.get('default_samplerate', 48000))
        self.sample_rate = 48000 if device_default >= 48000 else device_default
        
        return channels, self.sample_rate

    def _create_stop_function(self, stream: sd.InputStream, flush_callback: Callable = None, stream_purpose: str = "default") -> Callable:
        """Create the stop function for the audio stream.
        
        Args:
            stream: The sounddevice InputStream.
            flush_callback: Optional callback to flush any remaining audio data.
            stream_purpose: Purpose identifier for this stream
            
        Returns:
            Function to stop the stream.
        """
        def stop_stream(wait_for_stop: bool = False) -> None:
            if stream:
                try:
                    # First, flush any accumulated audio if callback provided
                    if flush_callback:
                        flush_callback()
                    
                    stream.stop()
                    stream.close()
                    logging.info("sounddevice InputStream stopped and closed")
                except Exception as e:
                    logging.error(f"Error stopping sounddevice stream: {e}", exc_info=True)
                finally:
                    # Clear references
                    self.listening_device = None
                    self.callback_function = None
                    
                    # Remove from active streams by purpose
                    if stream_purpose in self._active_streams:
                        self._active_streams.pop(stream_purpose, None)
        
        return stop_stream

    def _create_audio_callback(self, phrase_time_limit: int) -> Tuple[Callable, Callable]:
        """Create the audio callback function for sounddevice.
        
        Args:
            phrase_time_limit: Maximum length of audio capture in seconds.
            
        Returns:
            Tuple of (callback_function, flush_function).
        """
        # Buffer to accumulate audio data
        accumulated_data = []
        accumulated_frames = 0
        target_frames = int(self.sample_rate * phrase_time_limit)
        
        logging.info(f"Audio will accumulate until {target_frames} frames (approx. {phrase_time_limit} seconds) before processing")

        def flush_accumulated_audio():
            """Flush any accumulated audio data."""
            nonlocal accumulated_data, accumulated_frames
            if self.callback_function and accumulated_data and accumulated_frames > 0:
                try:
                    # Combine all accumulated chunks
                    combined_data = np.vstack(accumulated_data) if len(accumulated_data) > 1 else accumulated_data[0]
                    logging.info(f"Flushing accumulated audio: frames={accumulated_frames}, shape={combined_data.shape}, max_amplitude={np.abs(combined_data).max():.6f}")
                    # Call the callback with the combined data
                    self.callback_function(combined_data)
                except Exception as e:
                    logging.error(f"Error flushing accumulated audio: {e}", exc_info=True)
                finally:
                    # Reset for next accumulation
                    accumulated_data = []
                    accumulated_frames = 0

        def audio_callback_sd(indata: np.ndarray, frames: int, _: Any, status: sd.CallbackFlags) -> None:
            nonlocal accumulated_data, accumulated_frames
            
            if status:
                logging.warning(f"sounddevice status: {status}")
            try:
                # Make a copy to avoid issues with buffer overwriting
                audio_data_copy = indata.copy()
                
                # Check for clipping and normalize if needed
                max_val = np.abs(audio_data_copy).max()
                if max_val >= 0.99:
                    # Audio is clipping, normalize it
                    audio_data_copy = audio_data_copy * 0.8
                    if len(accumulated_data) <= 3:
                        logging.warning(f"Audio callback {len(accumulated_data) + 1}: CLIPPING DETECTED AND NORMALIZED! Original max={max_val:.6f}")
                
                # Add to accumulated buffer
                accumulated_data.append(audio_data_copy)
                accumulated_frames += frames
                
                
                # Only call the callback when we've accumulated enough data
                if accumulated_frames >= target_frames:
                    if self.callback_function and accumulated_data:
                        # Combine all accumulated chunks
                        combined_data = np.vstack(accumulated_data) if len(accumulated_data) > 1 else accumulated_data[0]
                        # Ensure data is in the right shape (flatten to 1D if needed)
                        if len(combined_data.shape) > 1 and combined_data.shape[1] == 1:
                            combined_data = combined_data.flatten()
                        self.callback_function(combined_data)
                        
                        # Reset for next accumulation
                        accumulated_data = []
                        accumulated_frames = 0
            except Exception as e_cb:
                logging.error(f"Error in sounddevice audio_callback_sd: {e_cb}", exc_info=True)
                # Reset accumulation on error
                accumulated_data = []
                accumulated_frames = 0
        
        return audio_callback_sd, flush_accumulated_audio

    def _listen_with_sounddevice(self, device_name: str, callback: Callable, phrase_time_limit: int = None, stream_purpose: str = "default") -> Callable:
        """Listen using sounddevice library, resolving name to index just-in-time.

        Args:
            device_name: The target device name string.
            callback: Function to call with audio data.
            phrase_time_limit: Maximum length of audio capture in seconds (uses DEFAULT_PHRASE_TIME_LIMIT if None).
            stream_purpose: Purpose identifier for this stream (e.g., "soap", "translation")

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

            # Resolve device name to index
            device_id = self._resolve_device_index(device_name)
            logging.info(f"Device resolution result: device_name='{device_name}' -> device_id={device_id}")
            if device_id is None:
                # Try to use default input device as a fallback
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
            
            # Setup audio parameters
            self._setup_audio_parameters(device_id)
            
            # Create audio callback
            audio_callback_sd, flush_callback = self._create_audio_callback(phrase_time_limit)

            # Get device info for logging
            device_info = sd.query_devices(device_id)
            
            # Log detailed device information before starting stream
            logging.info(f"Creating stream with parameters: samplerate={self.sample_rate}, device={device_id}, channels={self.channels}")
            logging.info(f"Device info: name='{device_info['name']}', hostapi={device_info['hostapi']}, max_input_channels={device_info['max_input_channels']}")
            
            stream = sd.InputStream(
                samplerate=self.sample_rate,
                device=device_id,
                channels=self.channels,
                callback=audio_callback_sd,
                blocksize=0,
                dtype='float32'
            )
            stream.start()
            logging.info(f"sounddevice InputStream started successfully for '{device_info['name']}'")

            # Add to active streams with purpose
            self._active_streams[stream_purpose] = {
                'stream': stream,
                'device': device_name,
                'callback': callback
            }
            
            # Create stop function with flush callback
            stop_function = self._create_stop_function(stream, flush_callback, stream_purpose)
            
            return stop_function # Return the specific closer for this stream

        except sd.PortAudioError as pae:
            logging.error(f"PortAudioError in _listen_with_sounddevice for '{device_name}': {pae}")
            logging.error(f"PortAudio error details: Host Error={pae.hostApiErrorInfo}")
            raise ValueError(f"Audio device error for '{device_name}': {pae}") from pae
        except Exception as e:
            logging.error(f"Error in _listen_with_sounddevice for '{device_name}': {e}", exc_info=True)
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
                     logging.error(f"Error during cleanup in _listen_with_sounddevice: {e_clean}")
            raise e # Re-raise the exception

    def _background_recording_thread(self, device_index: int, phrase_time_limit: float) -> None:
        """ Background thread that records audio using soundcard (potentially problematic). """
        # This method seems deprecated in favor of _listen_with_sounddevice and soundcard issues
        # Keeping it for reference but should likely be removed or refactored if soundcard is needed.
        logging.warning("_background_recording_thread (soundcard) is likely deprecated.")
        if not SOUNDCARD_AVAILABLE:
            logging.error("Soundcard not available, cannot use soundcard backend")
            return
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

                        if self.callback_function:
                            try:
                                self.callback_function(processed_data)
                            except Exception as cb_err:
                                logging.error(f"Error in soundcard callback execution: {cb_err}", exc_info=True)

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
