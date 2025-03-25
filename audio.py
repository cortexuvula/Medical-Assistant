import os
import json
import uuid
import time
import logging
from io import BytesIO
import soundcard
import sounddevice as sd
import numpy as np
import wave
import threading
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
        
    def get_raw_data(self):
        return self.frame_data

class AudioHandler:
    """Class to handle all audio-related functionality including recording, transcription, and file operations."""
    
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
        """Combine multiple audio segments into a single segment.
        
        Args:
            segments: List of AudioSegment objects
            
        Returns:
            Combined AudioSegment or None if list is empty
        """
        if not segments:
            return None
        combined = segments[0]
        for segment in segments[1:]:
            combined += segment
        return combined

    def set_fallback_callback(self, callback: Callable[[str, str], None]) -> None:
        """Set a callback function to be called when service fallback occurs.
        
        Args:
            callback: Function taking (primary_provider, fallback_provider) as parameters
        """
        self.fallback_callback = callback

    def transcribe_audio(self, segment: AudioSegment) -> str:
        """Transcribe audio using selected provider with fallback options.
        
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
            
    def listen_in_background(self, device_index: int, callback: Callable[[np.ndarray], None], 
                            phrase_time_limit: int = 10) -> Callable[[], None]:
        """Start listening in the background using sounddevice.
        
        Args:
            device_index: Index of the microphone to use
            callback: Function to call with the audio data
            phrase_time_limit: Maximum duration of each audio chunk in seconds
            
        Returns:
            Function to stop the background listening
        """
        try:
            # Store callback function
            self.callback_function = callback
            
            # Get the list of microphones using the same method as utils.get_valid_microphones()
            from utils import get_valid_microphones
            mic_names = get_valid_microphones()
            
            if not mic_names:
                raise ValueError("No microphone devices found")
                
            # Validate device index
            if device_index >= len(mic_names):
                logging.warning(f"Invalid device index {device_index}, using default device")
                device_index = 0
            
            # Get the device name from the index
            device_name = mic_names[device_index]
            
            # Check if this is a Voicemeeter device - these often have issues with soundcard
            is_voicemeeter = "voicemeeter" in device_name.lower() or "vb-audio" in device_name.lower()
            
            # Choose recording method based on device type
            if is_voicemeeter:
                logging.info(f"Using sounddevice for Voicemeeter device: {device_name}")
                return self._listen_with_sounddevice(device_name, callback, phrase_time_limit)
            else:
                logging.info(f"Using soundcard for device: {device_name}")
                # Find the matching soundcard device
                mics = soundcard.all_microphones()
                selected_device = None
                
                for mic in mics:
                    if mic.name == device_name:
                        selected_device = mic
                        break
                        
                if not selected_device:
                    # Fallback to first available device
                    if mics:
                        selected_device = mics[0]
                        logging.warning(f"Could not find exact device match for {device_name}, using {selected_device.name}")
                    else:
                        raise ValueError(f"No microphone device found matching name: {device_name}")
                
                # Store the selected device
                self.listening_device = {'name': device_name, 'object': selected_device}
                
                logging.info(f"Starting background listening on device: {device_name}")
                
                # Set recording flag
                self.recording = True
                self.recorded_frames = []
                
                # Start recording thread
                self.recording_thread = threading.Thread(
                    target=self._background_recording_thread,
                    args=(self.listening_device, phrase_time_limit),
                    daemon=True
                )
                self.recording_thread.start()
                
                # Return a function to stop listening
                return lambda wait_for_stop=True: self._stop_listening(wait_for_stop)
            
        except Exception as e:
            logging.error(f"Error starting background listening: {str(e)}", exc_info=True)
            return lambda wait_for_stop=True: None
            
    def _listen_with_sounddevice(self, device_name: str, callback: Callable[[np.ndarray], None],
                           phrase_time_limit: int = 10) -> Callable[[], None]:
        """Listen using sounddevice library for microphone input.
        
        Args:
            device_name: Device name string
            callback: Function to call with audio data
            phrase_time_limit: Maximum length of audio capture in seconds
            
        Returns:
            Function to stop listening
        """
        try:
            # Store the device name
            self.listening_device = device_name
            
            # Find device by name - more thorough search for Voicemeeter devices
            device_id = None
            devices = sd.query_devices()
            
            # Debug logging - print all available devices
            logging.info("Available audio devices:")
            for i, device in enumerate(devices):
                device_name_lower = device['name'].lower()
                is_input = device['max_input_channels'] > 0
                channels = device['max_input_channels']
                logging.info(f"  [{i}] {device['name']} - Input: {is_input}, Channels: {channels}")
                
                # More flexible matching for Voicemeeter devices
                if device_name.lower() in device_name_lower and is_input:
                    device_id = i
                    logging.info(f"Selected device {i}: {device['name']}")
                    break
                    
            if device_id is None:
                logging.error(f"Could not find device: {device_name}, falling back to default input")
                # Get default input device
                device_info = sd.query_devices(kind='input')
                device_id = device_info['index'] if 'index' in device_info else 0
                logging.info(f"Using default input device: {device_info['name']}")
            
            # Store callback
            self.callback_function = callback
            
            # Calculate buffer size based on phrase time limit
            buffer_size = int(self.sample_rate * phrase_time_limit)
            
            # Log buffer size
            logging.info(f"Started sounddevice recording on {device_name} (ID: {device_id}) with buffer {buffer_size}")
            
            # Global variables for thread
            accumulated_frames = np.array([], dtype=np.float32)
            stop_event = threading.Event()
            stream = None
            
            def audio_callback(indata, frames, time, status):
                nonlocal accumulated_frames
                
                if status:
                    # Log any errors but continue recording
                    logging.warning(f"Recording status: {status}")
                
                # Log the maximum amplitude of this chunk
                if indata is not None and indata.size > 0:
                    max_amp = np.abs(indata).max()
                    # if self.soap_mode:
                    #     logging.info(f"Audio chunk received: shape={indata.shape}, max_amp={max_amp:.6f}")
                    # else:
                    #     logging.debug(f"Audio chunk received: shape={indata.shape}, max_amp={max_amp:.6f}")
                    
                    # When in SOAP mode, normalize audio to ensure it's not too quiet
                    if self.soap_mode and max_amp > 0.0001:  # Only normalize if there's some sound
                        # Normalize to reasonable level if the audio is too quiet
                        if max_amp < 0.1:  # Boost quiet audio
                            # Calculate scaling factor - boost quiet audio
                            scale_factor = min(10.0, 0.5 / max(0.001, np.abs(indata).max()))
                            indata = indata * scale_factor
                            logging.debug(f"Boosted audio by factor {scale_factor:.2f}")
                    
                    # Always append data to accumulated buffer for SOAP recording
                    # For stereo input, average the channels to get mono
                    if indata.shape[1] > 1:  # If stereo
                        mono_data = np.mean(indata, axis=1)
                        accumulated_frames = np.append(accumulated_frames, mono_data)
                        logging.debug(f"Converted stereo to mono, shape now: {mono_data.shape}")
                    else:
                        accumulated_frames = np.append(accumulated_frames, indata[:, 0])  # Take first channel
                else:
                    logging.warning("Received empty audio chunk")
            
            def audio_processing_thread():
                nonlocal accumulated_frames, stream
                
                # Define chunk size (process in 100ms chunks)
                chunk_seconds = 0.1
                chunk_frames = int(self.sample_rate * chunk_seconds)
                
                try:
                    # Start the audio processing loop
                    while not stop_event.is_set():
                        # Process accumulated frames in chunks
                        if len(accumulated_frames) >= chunk_frames:
                            try:
                                # Extract current chunk
                                current_chunk = accumulated_frames[:chunk_frames]
                                
                                # Process only if above silence threshold
                                max_amp = np.abs(current_chunk).max()
                                
                                # In SOAP mode, always log the amplitude for debugging
                                if self.soap_mode:
                                    #logging.info(f"SOAP audio chunk amplitude: {max_amp:.6f} (threshold: {self.silence_threshold:.6f})")
                                    
                                    # For SOAP recording, we want to capture everything, so boost the signal if needed
                                    if max_amp > 0.0001 and max_amp < 0.1:  # Only boost if there's some sound but it's quiet
                                        scale_factor = min(10.0, 0.3 / max_amp)
                                        current_chunk = current_chunk * scale_factor
                                        new_max = np.abs(current_chunk).max()
                                        logging.debug(f"Boosted SOAP chunk from {max_amp:.6f} to {new_max:.6f}")
                                
                                # Process all audio regardless of amplitude in SOAP mode
                                # Force the callback to be called even with low amplitude
                                if self.soap_mode or max_amp >= self.silence_threshold:
                                    try:
                                        # Always call the callback with the data in SOAP mode
                                        if self.callback_function:
                                            logging.debug(f"Calling audio callback with data: shape={current_chunk.shape}, max_amp={max_amp:.6f}")
                                            self.callback_function(current_chunk)
                                        else:
                                            logging.warning("No callback function set")
                                    except Exception as cb_error:
                                        logging.error(f"Error in audio callback: {str(cb_error)}", exc_info=True)
                                else:
                                    # More verbose in normal mode
                                    logging.debug(f"Skipping silent chunk with amplitude {max_amp:.6f} (below threshold {self.silence_threshold:.6f})")
                                
                                # Keep any remaining frames for next chunk
                                accumulated_frames = accumulated_frames[chunk_frames:]
                                
                            except Exception as e:
                                logging.error(f"Error processing audio chunk: {str(e)}", exc_info=True)
                                accumulated_frames = np.array([], dtype=np.float32)  # Reset on error
                                
                        # Small sleep to prevent CPU hogging
                        time.sleep(0.01)
                        
                except Exception as e:
                    logging.error(f"Error in audio processing thread: {str(e)}", exc_info=True)
                finally:
                    # Ensure stream is stopped
                    if stream is not None and stream.active:
                        try:
                            stream.stop()
                            stream.close()
                            logging.info(f"Closed sounddevice stream for {device_name}")
                        except Exception as close_error:
                            logging.error(f"Error closing stream: {str(close_error)}")
            
            # Start the audio stream
            stream = sd.InputStream(
                device=device_id,
                channels=self.channels,
                samplerate=self.sample_rate,
                callback=audio_callback,
                blocksize=1024  # Process in small blocks for lower latency
            )
            stream.start()
            logging.info(f"Started sounddevice stream for {device_name}")
            
            # Start the processing thread
            processing_thread = threading.Thread(target=audio_processing_thread, daemon=True)
            processing_thread.start()
            
            # Return stop function
            def stop_listening(wait_for_stop=False):
                try:
                    stop_event.set()
                    
                    # Give the thread a chance to clean up
                    if wait_for_stop:
                        processing_thread.join(timeout=2.0)
                        
                    logging.info("Background listening stopped")
                    return True
                except Exception as e:
                    logging.error(f"Error stopping listening: {str(e)}")
                    return False
                    
            return stop_listening
            
        except Exception as e:
            logging.error(f"Error setting up sounddevice listening: {str(e)}", exc_info=True)
            return lambda wait_for_stop=False: None

    def _stop_listening(self, wait_for_stop: bool = True) -> None:
        """Stop the background listening.
        
        Args:
            wait_for_stop: Whether to wait for the recording thread to stop
        """
        if self.recording:
            self.recording = False
            
            if wait_for_stop and self.recording_thread:
                self.recording_thread.join(timeout=2)
                
            logging.info("Background listening stopped")
                
    def _background_recording_thread(self, device: Dict[str, Any], phrase_time_limit: int) -> None:
        """Background thread to record audio in chunks.
        
        Args:
            device: Dictionary with device information
            phrase_time_limit: Maximum duration of each audio chunk in seconds
        """
        try:
            mic = device['object']
            buffer_size = int(self.sample_rate * phrase_time_limit)
            
            logging.info(f"Recording thread started with buffer size: {buffer_size}")
            
            while self.recording:
                try:
                    # Record a chunk of audio
                    with mic.recorder(samplerate=self.sample_rate, channels=self.channels) as recorder:
                        # Record audio for phrase_time_limit seconds or until recording is stopped
                        data = recorder.record(numframes=buffer_size)
                        
                        # Apply gain to boost low-level signals if needed (multiply to increase volume)
                        # This helps with Voicemeeter outputs that might have lower levels
                        if np.abs(data).max() < 0.01:  # If the signal is weak but not silent
                            # Calculate scaling factor - boost quiet audio
                            gain_factor = min(10.0, 0.01 / max(0.001, np.abs(data).max()))
                            data = data * gain_factor
                            logging.debug(f"Applied gain factor of {gain_factor:.2f} to boost low audio")
                        
                        # Skip processing if recording was stopped during this chunk
                        if not self.recording:
                            break
                            
                        # Get maximum amplitude for debug
                        max_amplitude = np.abs(data).max()
                        logging.debug(f"Audio chunk max amplitude: {max_amplitude:.6f}")
                        
                        # Skip processing if data is too quiet (silence) - using a much lower threshold
                        if max_amplitude < self.silence_threshold:  # Use dynamic threshold
                            # In SOAP mode, be more verbose about skipping audio
                            if self.soap_mode:
                                logging.debug(f"SOAP mode: Skipping audio chunk with amplitude {max_amplitude:.6f}")
                            else:
                                logging.debug("Skipping silent audio chunk")
                            continue
                            
                        # Process this chunk of audio
                        if self.callback_function:
                            # Pass the numpy array directly to the callback function
                            self.callback_function(data)
                            
                except Exception as chunk_error:
                    logging.error(f"Error recording audio chunk: {str(chunk_error)}", exc_info=True)
                    # Sleep briefly to avoid tight loop on error
                    time.sleep(0.5)
                    
        except Exception as e:
            logging.error(f"Background recording thread error: {str(e)}", exc_info=True)
            self.recording = False
