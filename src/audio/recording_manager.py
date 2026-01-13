"""
Recording Manager Module

Handles all SOAP recording functionality including start/stop/pause/resume,
audio segment management, and recording processing.
"""

import logging
import threading
import time
from datetime import datetime as dt
from typing import Optional, List, Callable, Dict, Any
import numpy as np
from pydub import AudioSegment
import tempfile
import os

from audio.audio import AudioHandler
from audio.audio_state_manager import AudioStateManager, RecordingState
from audio.constants import SAMPLE_RATE_48K, DEFAULT_SAMPLE_WIDTH, DEFAULT_CHANNELS
from ui.status_manager import StatusManager
from utils.exceptions import DeviceDisconnectedError, AudioError


class RecordingManager:
    """Manages SOAP recording functionality."""

    # Device health check interval in seconds
    DEVICE_CHECK_INTERVAL = 10.0  # Increased from 5.0 to reduce false positives

    # Device cache TTL in seconds (avoids re-enumerating devices on every call)
    DEVICE_CACHE_TTL = 30.0

    def __init__(self, audio_handler: AudioHandler, status_manager: StatusManager,
                 audio_state_manager: AudioStateManager):
        """Initialize the recording manager.

        Args:
            audio_handler: AudioHandler instance for audio processing
            status_manager: StatusManager instance for status updates
            audio_state_manager: AudioStateManager instance for audio state management
        """
        self.audio_handler = audio_handler
        self.status_manager = status_manager
        self.audio_state_manager = audio_state_manager

        # Recording thread
        self.recording_thread = None

        # Device monitoring
        self._current_device_name: Optional[str] = None
        self._last_device_check = 0.0
        self._device_error_count = 0
        self._max_device_errors = 5  # Increased from 3 for more tolerance with virtual audio devices

        # Device caching (saves 100-500ms on device enumeration)
        self._device_cache: Optional[List[Any]] = None
        self._device_cache_time: float = 0.0

        # Callbacks
        self.on_recording_complete: Optional[Callable] = None
        self.on_text_recognized: Optional[Callable] = None
        self.on_transcription_fallback: Optional[Callable] = None
        self.on_device_disconnected: Optional[Callable[[str], None]] = None
        
    def start_recording(self, callback: Callable[[np.ndarray], None]) -> bool:
        """Start SOAP recording.
        
        Args:
            callback: Function to call with audio data
            
        Returns:
            bool: True if recording started successfully
        """
        try:
            # Start recording in audio state manager
            self.audio_state_manager.start_recording()
            
            # Start recording thread
            self.recording_thread = threading.Thread(
                target=self._recording_loop,
                args=(callback,)
            )
            self.recording_thread.daemon = True
            self.recording_thread.start()
            
            logging.info("SOAP recording started")
            return True
            
        except Exception as e:
            logging.error(f"Failed to start recording: {e}")
            return False
    
    def stop_recording(self) -> Optional[Dict[str, Any]]:
        """Stop SOAP recording and return recording data.
        
        Returns:
            Optional[Dict[str, Any]]: Recording data or None if no recording
        """
        if self.audio_state_manager.get_state() == RecordingState.IDLE:
            return None
            
        # Stop recording in state manager
        self.audio_state_manager.stop_recording()
        
        # Wait for recording thread to finish
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=2.0)
        
        # Get metadata and combined audio
        metadata = self.audio_state_manager.get_recording_metadata()
        combined_audio = self.audio_state_manager.get_combined_audio()
        
        # Get segment statistics
        pending, chunks, total = self.audio_state_manager.get_segment_stats()
        
        # Log segment count for debugging
        logging.info(f"RecordingManager: Stopping with {total} total segments")
        
        recording_data = {
            'audio': combined_audio,
            'duration': metadata['recording_duration'],
            'start_time': metadata['start_time'],
            'segment_count': total,
            'pause_duration': metadata['pause_duration']
        }
        
        if combined_audio:
            logging.info(f"SOAP recording stopped. Duration: {metadata['recording_duration']:.1f}s, Segments: {total}")
        else:
            logging.warning("RecordingManager: No audio segments recorded")
        
        return recording_data
    
    def pause_recording(self) -> bool:
        """Pause SOAP recording.
        
        Returns:
            bool: True if paused successfully
        """
        try:
            self.audio_state_manager.pause_recording()
            logging.info("SOAP recording paused")
            return True
        except RuntimeError:
            return False
    
    def resume_recording(self) -> bool:
        """Resume SOAP recording.
        
        Returns:
            bool: True if resumed successfully
        """
        try:
            self.audio_state_manager.resume_recording()
            logging.info("SOAP recording resumed")
            return True
        except RuntimeError:
            return False
    
    def cancel_recording(self) -> None:
        """Cancel SOAP recording without processing."""
        # Clear all audio data
        self.audio_state_manager.clear_all()
        
        # Wait for recording thread
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=2.0)
            
        logging.info("SOAP recording cancelled")
    
    def add_audio_segment(self, audio_data: np.ndarray) -> None:
        """Add audio segment to recording.
        
        Args:
            audio_data: Audio data as numpy array
        """
        # Get audio format from handler
        sample_rate = getattr(self.audio_handler, 'sample_rate', SAMPLE_RATE_48K)
        sample_width = getattr(self.audio_handler, 'sample_width', DEFAULT_SAMPLE_WIDTH)
        channels = getattr(self.audio_handler, 'channels', DEFAULT_CHANNELS)
        
        # Add to state manager
        self.audio_state_manager.add_segment(
            audio_data, 
            sample_rate=sample_rate,
            sample_width=sample_width,
            channels=channels
        )
    
    def process_recording(self, audio_data: AudioSegment, context: str = "") -> Dict[str, Any]:
        """Process completed recording through STT.
        
        Args:
            audio_data: Combined audio data
            context: Additional context for transcription
            
        Returns:
            Dict[str, Any]: Processing results
        """
        try:
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                audio_data.export(temp_file.name, format="mp3")
                temp_path = temp_file.name
            
            # Transcribe
            transcript = self.audio_handler.transcribe_audio_file(
                temp_path,
                callback=self.on_text_recognized,
                on_transcription_fallback=self.on_transcription_fallback
            )
            
            # Clean up
            os.unlink(temp_path)
            
            return {
                'success': True,
                'transcript': transcript,
                'audio_data': audio_data
            }
            
        except Exception as e:
            logging.error(f"Failed to process recording: {e}")
            return {
                'success': False,
                'error': str(e),
                'audio_data': audio_data
            }
    
    def _check_device_health(self) -> bool:
        """Check if the recording device is still available.

        Returns:
            True if device is healthy, False if disconnected

        Raises:
            DeviceDisconnectedError: If device has been lost after max retries
        """
        current_time = time.time()

        # Only check periodically to avoid performance impact
        if current_time - self._last_device_check < self.DEVICE_CHECK_INTERVAL:
            return True

        self._last_device_check = current_time

        try:
            # FIRST: Check if the audio stream is still active and receiving data
            # This is more reliable than device enumeration for virtual audio devices
            if self._is_stream_active():
                self._device_error_count = 0  # Reset on success
                return True

            # SECOND: Check if the listening device still exists via enumeration
            listening_device = getattr(self.audio_handler, 'listening_device', None)

            if listening_device is None:
                # No specific device selected, using default - check if any device is available
                available_devices = self._get_available_devices()
                if not available_devices:
                    self._device_error_count += 1
                    logging.warning(f"No audio devices available (error {self._device_error_count}/{self._max_device_errors})")
                else:
                    self._device_error_count = 0  # Reset on success
                    return True
            else:
                # Check if the specific device still exists
                device_name = self._current_device_name or str(listening_device)

                if self._find_device_by_name(device_name):
                    self._device_error_count = 0  # Reset on success
                    return True
                else:
                    self._device_error_count += 1
                    logging.warning(f"Device '{device_name}' not found (error {self._device_error_count}/{self._max_device_errors})")

            # Check if we've exceeded max errors
            if self._device_error_count >= self._max_device_errors:
                device_name = self._current_device_name or "Unknown device"
                raise DeviceDisconnectedError(
                    f"Audio device '{device_name}' appears to be disconnected",
                    device_name=device_name
                )

            return self._device_error_count == 0

        except DeviceDisconnectedError:
            raise
        except Exception as e:
            logging.error(f"Error checking device health: {e}")
            self._device_error_count += 1
            return self._device_error_count < self._max_device_errors

    def _is_stream_active(self) -> bool:
        """Check if the audio stream is still active and receiving data.

        Returns:
            True if stream is active, False otherwise
        """
        try:
            # Check if audio handler has active streams
            active_streams = getattr(self.audio_handler, '_active_streams', {})

            for purpose, stream_info in active_streams.items():
                stream = stream_info.get('stream')
                if stream:
                    # For sounddevice streams, check if active
                    if hasattr(stream, 'active') and stream.active:
                        return True
                    # For streams without active property, check if not stopped
                    if hasattr(stream, 'stopped') and not stream.stopped:
                        return True

            # Also check if we've received audio data recently
            # The audio state manager tracks this
            if self.audio_state_manager:
                state = self.audio_state_manager.get_state()
                if state == RecordingState.RECORDING:
                    # Check if audio data is being accumulated (thread-safe method)
                    if self.audio_state_manager.has_audio():
                        return True

            return False
        except Exception as e:
            logging.debug(f"Error checking stream active status: {e}")
            return False

    def _find_device_by_name(self, device_name: str) -> bool:
        """Find a device using multiple matching strategies in a single pass.

        Combines 4 matching strategies into one iteration for 4x better performance:
        1. Exact match (case-insensitive)
        2. Clean name contained in device string
        3. Device base name contained in our name
        4. Common prefix match (15 chars) for truncated names

        Args:
            device_name: The device name to search for

        Returns:
            True if device found, False otherwise
        """
        available_devices = self._get_available_devices()
        if not available_devices:
            return False

        # Pre-compute values once instead of in each iteration
        clean_name = device_name.split('(Device ')[0].strip() if '(Device ' in device_name else device_name
        device_name_lower = device_name.lower()
        clean_name_lower = clean_name.lower()

        # Single-pass: check all strategies for each device
        for dev in available_devices:
            dev_str = str(dev).lower()

            # Strategy 1: Exact match (case-insensitive)
            if device_name_lower == dev_str:
                return True

            # Strategy 2: Clean name contained in device string
            if clean_name_lower in dev_str:
                return True

            # Strategy 3: Device base name contained in our name (for truncated names)
            dev_base = dev_str.split('(')[0].strip() if '(' in dev_str else dev_str
            if dev_base and dev_base in device_name_lower:
                return True

            # Strategy 4: Common prefix match (15 chars) for truncated names
            if len(clean_name_lower) >= 15 and len(dev_str) >= 15:
                if clean_name_lower[:15] == dev_str[:15]:
                    return True

        return False

    def _get_available_devices(self, force_refresh: bool = False) -> List[Any]:
        """Get list of available audio input devices.

        Uses caching to avoid expensive device enumeration on every call.
        Saves 100-500ms per call when cache is valid.

        Args:
            force_refresh: Force refresh of device list ignoring cache

        Returns:
            List of available devices
        """
        current_time = time.time()

        # Return cached devices if still valid
        if (not force_refresh
                and self._device_cache is not None
                and current_time - self._device_cache_time < self.DEVICE_CACHE_TTL):
            return self._device_cache

        try:
            devices = []

            # Try soundcard first
            try:
                import soundcard
                devices = list(soundcard.all_microphones())
            except (ImportError, Exception):
                pass

            # Try sounddevice if soundcard didn't work
            if not devices:
                try:
                    import sounddevice as sd
                    all_devices = sd.query_devices()
                    devices = [d for d in all_devices if d.get('max_input_channels', 0) > 0]
                except (ImportError, Exception):
                    pass

            # Update cache
            self._device_cache = devices
            self._device_cache_time = current_time

            return devices

        except Exception as e:
            logging.error(f"Error getting available devices: {e}")
            # Return cached devices if available, otherwise empty list
            return self._device_cache if self._device_cache else []

    def invalidate_device_cache(self) -> None:
        """Invalidate the device cache to force refresh on next call."""
        self._device_cache = None
        self._device_cache_time = 0.0

    def _handle_device_disconnection(self, error: DeviceDisconnectedError) -> None:
        """Handle device disconnection gracefully.

        Args:
            error: The DeviceDisconnectedError that was raised
        """
        logging.error(f"Device disconnected: {error}")

        # Pause recording to preserve data
        try:
            self.audio_state_manager.pause_recording()
        except RuntimeError:
            pass

        # Notify via callback if registered
        if self.on_device_disconnected:
            try:
                self.on_device_disconnected(error.device_name or "Unknown")
            except Exception as e:
                logging.error(f"Error in device disconnection callback: {e}")

        # Update status
        if self.status_manager:
            self.status_manager.error(
                f"Audio device disconnected: {error.device_name or 'Unknown'}. "
                "Recording paused. Please reconnect the device or select a new one."
            )

    def _recording_loop(self, callback: Callable[[np.ndarray], None]) -> None:
        """Recording loop thread function.

        Args:
            callback: Function to call with audio data
        """
        while self.audio_state_manager.get_state() in [RecordingState.RECORDING, RecordingState.PAUSED]:
            try:
                # Check device health periodically
                if self.audio_state_manager.is_recording():
                    try:
                        self._check_device_health()
                    except DeviceDisconnectedError as e:
                        self._handle_device_disconnection(e)
                        break  # Exit recording loop

                    # Get audio data (implement based on your audio capture method)
                    # This is a placeholder - actual implementation depends on audio source
                    time.sleep(0.1)  # Prevent busy loop
                else:
                    time.sleep(0.1)  # Check less frequently when paused

            except Exception as e:
                logging.error(f"Error in recording loop: {e}")
                time.sleep(0.1)  # Prevent tight error loop
    
    
    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self.audio_state_manager.is_recording()
    
    @property
    def is_paused(self) -> bool:
        """Check if recording is paused."""
        return self.audio_state_manager.is_paused()
    
    @property
    def recording_duration(self) -> float:
        """Get current recording duration in seconds."""
        metadata = self.audio_state_manager.get_recording_metadata()
        return metadata['recording_duration']
    
    @property
    def soap_recording(self) -> bool:
        """Legacy property for backward compatibility."""
        return self.audio_state_manager.get_state() != RecordingState.IDLE
    
    @property
    def soap_paused(self) -> bool:
        """Legacy property for backward compatibility."""
        return self.audio_state_manager.is_paused()