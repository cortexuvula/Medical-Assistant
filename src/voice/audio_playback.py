"""
Audio Playback System for Text-to-Speech Output

Handles audio playback with streaming support for real-time TTS in advanced voice mode.
"""

import logging
import threading
import queue
import time
from typing import Optional, Callable, Union, List, Dict, Any
import numpy as np
import sounddevice as sd
import soundcard as sc
from pydub import AudioSegment
from io import BytesIO
import wave


class AudioPlaybackManager:
    """Manages audio playback for TTS output."""
    
    def __init__(self, sample_rate: int = 24000, channels: int = 1):
        """Initialize audio playback manager.
        
        Args:
            sample_rate: Sample rate for audio playback (24kHz for high quality speech)
            channels: Number of audio channels (1 for mono, 2 for stereo)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = 1024  # Chunk size for streaming
        
        # Playback state
        self.is_playing = False
        self.is_paused = False
        self.should_stop = False
        
        # Audio queue for streaming playback
        self.audio_queue = queue.Queue()
        self.playback_thread = None
        
        # Output device
        self.output_device = None
        self.output_device_index = None
        
        # Callbacks
        self.on_playback_start: Optional[Callable] = None
        self.on_playback_end: Optional[Callable] = None
        self.on_playback_error: Optional[Callable] = None
        
        # Volume control (0.0 to 1.0)
        self.volume = 1.0
        
        # Initialize audio backend
        self._init_audio_backend()
        
    def _init_audio_backend(self):
        """Initialize the audio backend and detect output devices."""
        try:
            # Try sounddevice first
            devices = sd.query_devices()
            default_output = sd.default.device[1]  # Output device
            
            if default_output is not None:
                self.output_device_index = default_output
                device_info = devices[default_output]
                self.output_device = device_info['name']
                logging.info(f"Using sounddevice output: {self.output_device}")
            else:
                # Fallback to soundcard
                speakers = sc.all_speakers()
                if speakers:
                    self.output_device = speakers[0]
                    logging.info(f"Using soundcard output: {self.output_device.name}")
                else:
                    logging.warning("No audio output devices found")
                    
        except Exception as e:
            logging.error(f"Error initializing audio backend: {e}")
            
    def get_output_devices(self) -> List[Dict[str, Any]]:
        """Get list of available output devices.
        
        Returns:
            List of device info dictionaries
        """
        devices = []
        
        try:
            # Get sounddevice devices
            sd_devices = sd.query_devices()
            for i, device in enumerate(sd_devices):
                if device['max_output_channels'] > 0:
                    devices.append({
                        'index': i,
                        'name': device['name'],
                        'channels': device['max_output_channels'],
                        'sample_rate': device['default_samplerate'],
                        'backend': 'sounddevice'
                    })
                    
            # Get soundcard devices if no sounddevice found
            if not devices:
                for speaker in sc.all_speakers():
                    devices.append({
                        'index': None,
                        'name': speaker.name,
                        'channels': speaker.channels,
                        'backend': 'soundcard',
                        'object': speaker
                    })
                    
        except Exception as e:
            logging.error(f"Error getting output devices: {e}")
            
        return devices
        
    def set_output_device(self, device_index: Optional[int] = None, 
                         device_name: Optional[str] = None):
        """Set the output device for playback.
        
        Args:
            device_index: Device index for sounddevice
            device_name: Device name for soundcard
        """
        try:
            if device_index is not None:
                # Use sounddevice
                self.output_device_index = device_index
                device_info = sd.query_devices(device_index)
                self.output_device = device_info['name']
                logging.info(f"Set output device to: {self.output_device}")
                
            elif device_name:
                # Use soundcard
                for speaker in sc.all_speakers():
                    if speaker.name == device_name:
                        self.output_device = speaker
                        self.output_device_index = None
                        logging.info(f"Set output device to: {device_name}")
                        break
                        
        except Exception as e:
            logging.error(f"Error setting output device: {e}")
            
    def set_volume(self, volume: float):
        """Set playback volume.
        
        Args:
            volume: Volume level (0.0 to 1.0)
        """
        self.volume = max(0.0, min(1.0, volume))
        
    def play_audio(self, audio_data: Union[np.ndarray, AudioSegment, bytes], 
                   block: bool = False):
        """Play audio data.
        
        Args:
            audio_data: Audio data as numpy array, AudioSegment, or bytes
            block: Whether to block until playback completes
        """
        if self.is_playing and not block:
            logging.warning("Already playing audio")
            return
            
        # Convert audio data to numpy array
        audio_array = self._convert_to_array(audio_data)
        
        if audio_array is None:
            logging.error("Failed to convert audio data")
            return
            
        if block:
            # Blocking playback
            self._play_blocking(audio_array)
        else:
            # Non-blocking playback
            self._play_nonblocking(audio_array)
            
    def _convert_to_array(self, audio_data: Union[np.ndarray, AudioSegment, bytes]) -> Optional[np.ndarray]:
        """Convert various audio formats to numpy array.
        
        Args:
            audio_data: Audio data in various formats
            
        Returns:
            Numpy array or None if conversion failed
        """
        try:
            if isinstance(audio_data, np.ndarray):
                return audio_data
                
            elif isinstance(audio_data, AudioSegment):
                # Convert AudioSegment to numpy array
                samples = np.array(audio_data.get_array_of_samples())
                
                # Normalize to float32 [-1, 1]
                if audio_data.sample_width == 2:
                    samples = samples.astype(np.float32) / 32768.0
                elif audio_data.sample_width == 1:
                    samples = (samples.astype(np.float32) - 128) / 128.0
                    
                # Handle stereo to mono conversion if needed
                if audio_data.channels == 2 and self.channels == 1:
                    samples = samples.reshape(-1, 2).mean(axis=1)
                    
                return samples
                
            elif isinstance(audio_data, bytes):
                # Assume WAV format bytes
                buf = BytesIO(audio_data)
                with wave.open(buf, 'rb') as wav:
                    frames = wav.readframes(wav.getnframes())
                    dtype = np.int16 if wav.getsampwidth() == 2 else np.int8
                    samples = np.frombuffer(frames, dtype=dtype)
                    
                    # Normalize
                    if dtype == np.int16:
                        samples = samples.astype(np.float32) / 32768.0
                    else:
                        samples = (samples.astype(np.float32) - 128) / 128.0
                        
                    return samples
                    
        except Exception as e:
            logging.error(f"Error converting audio data: {e}")
            return None
            
    def _play_blocking(self, audio_array: np.ndarray):
        """Play audio in blocking mode.
        
        Args:
            audio_array: Audio data as numpy array
        """
        try:
            # Apply volume
            audio_array = audio_array * self.volume
            
            # Trigger start callback
            if self.on_playback_start:
                self.on_playback_start()
                
            # Play using sounddevice
            sd.play(audio_array, self.sample_rate, device=self.output_device_index)
            sd.wait()  # Block until playback completes
            
            # Trigger end callback
            if self.on_playback_end:
                self.on_playback_end()
                
        except Exception as e:
            logging.error(f"Error in blocking playback: {e}")
            if self.on_playback_error:
                self.on_playback_error(str(e))
                
    def _play_nonblocking(self, audio_array: np.ndarray):
        """Play audio in non-blocking mode.
        
        Args:
            audio_array: Audio data as numpy array
        """
        # Add to queue
        self.audio_queue.put(audio_array)
        
        # Start playback thread if not running
        if not self.is_playing:
            self.is_playing = True
            self.should_stop = False
            self.playback_thread = threading.Thread(target=self._playback_worker)
            self.playback_thread.daemon = True
            self.playback_thread.start()
            
    def _playback_worker(self):
        """Worker thread for audio playback."""
        try:
            # Trigger start callback
            if self.on_playback_start:
                self.on_playback_start()
                
            while not self.should_stop:
                try:
                    # Get audio from queue
                    audio_array = self.audio_queue.get(timeout=0.1)
                    
                    # Apply volume
                    audio_array = audio_array * self.volume
                    
                    # Play audio
                    if not self.is_paused:
                        sd.play(audio_array, self.sample_rate, 
                               device=self.output_device_index)
                        sd.wait()
                        
                except queue.Empty:
                    # Check if we should continue
                    if self.audio_queue.empty() and not self.should_stop:
                        time.sleep(0.01)
                        
                except Exception as e:
                    logging.error(f"Error in playback worker: {e}")
                    if self.on_playback_error:
                        self.on_playback_error(str(e))
                        
        finally:
            self.is_playing = False
            
            # Trigger end callback
            if self.on_playback_end:
                self.on_playback_end()
                
    def stream_audio(self, audio_chunk: np.ndarray):
        """Stream audio chunk for continuous playback.
        
        Args:
            audio_chunk: Audio chunk to stream
        """
        if not self.is_playing:
            # Start playback worker
            self._play_nonblocking(audio_chunk)
        else:
            # Add to queue
            self.audio_queue.put(audio_chunk)
            
    def pause(self):
        """Pause audio playback."""
        self.is_paused = True
        
    def resume(self):
        """Resume audio playback."""
        self.is_paused = False
        
    def stop(self):
        """Stop audio playback."""
        self.should_stop = True
        
        # Clear queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except:
                break
                
        # Stop any current playback
        sd.stop()
        
        # Wait for playback thread
        if self.playback_thread:
            self.playback_thread.join(timeout=2)
            
        self.is_playing = False
        self.is_paused = False
        
    def is_active(self) -> bool:
        """Check if playback is active.
        
        Returns:
            True if currently playing
        """
        return self.is_playing
        
    def get_queue_size(self) -> int:
        """Get number of audio chunks in queue.
        
        Returns:
            Queue size
        """
        return self.audio_queue.qsize()
        
    def clear_queue(self):
        """Clear the audio queue."""
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except:
                break


class AudioMixer:
    """Mixes multiple audio streams for simultaneous playback."""
    
    def __init__(self, sample_rate: int = 24000):
        """Initialize audio mixer.
        
        Args:
            sample_rate: Sample rate for mixing
        """
        self.sample_rate = sample_rate
        self.streams = {}
        self.mix_levels = {}
        
    def add_stream(self, stream_id: str, level: float = 1.0):
        """Add a stream to the mixer.
        
        Args:
            stream_id: Unique stream identifier
            level: Mix level (0.0 to 1.0)
        """
        self.streams[stream_id] = []
        self.mix_levels[stream_id] = level
        
    def remove_stream(self, stream_id: str):
        """Remove a stream from the mixer.
        
        Args:
            stream_id: Stream identifier
        """
        if stream_id in self.streams:
            del self.streams[stream_id]
            del self.mix_levels[stream_id]
            
    def add_audio(self, stream_id: str, audio_data: np.ndarray):
        """Add audio data to a stream.
        
        Args:
            stream_id: Stream identifier
            audio_data: Audio data to add
        """
        if stream_id in self.streams:
            self.streams[stream_id].append(audio_data)
            
    def get_mixed_audio(self, duration_samples: int) -> np.ndarray:
        """Get mixed audio for specified duration.
        
        Args:
            duration_samples: Number of samples to mix
            
        Returns:
            Mixed audio array
        """
        mixed = np.zeros(duration_samples, dtype=np.float32)
        
        for stream_id, chunks in self.streams.items():
            if not chunks:
                continue
                
            # Concatenate chunks
            stream_audio = np.concatenate(chunks)
            
            # Apply mix level
            stream_audio *= self.mix_levels[stream_id]
            
            # Mix into output (handle different lengths)
            mix_length = min(len(stream_audio), duration_samples)
            mixed[:mix_length] += stream_audio[:mix_length]
            
            # Remove used audio
            if len(stream_audio) > duration_samples:
                # Keep remaining audio
                self.streams[stream_id] = [stream_audio[duration_samples:]]
            else:
                # Clear stream
                self.streams[stream_id] = []
                
        # Normalize to prevent clipping
        max_val = np.max(np.abs(mixed))
        if max_val > 1.0:
            mixed /= max_val
            
        return mixed