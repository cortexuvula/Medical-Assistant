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

from audio import AudioHandler
from status_manager import StatusManager


class RecordingManager:
    """Manages SOAP recording functionality."""
    
    def __init__(self, audio_handler: AudioHandler, status_manager: StatusManager):
        """Initialize the recording manager.
        
        Args:
            audio_handler: AudioHandler instance for audio processing
            status_manager: StatusManager instance for status updates
        """
        self.audio_handler = audio_handler
        self.status_manager = status_manager
        
        # Recording state
        self.soap_recording = False
        self.soap_paused = False
        self.audio_segments = []
        self.soap_start_time = None
        self.soap_pause_start_time = None
        self.total_pause_duration = 0
        self.recording_thread = None
        
        # Callbacks
        self.on_recording_complete: Optional[Callable] = None
        self.on_text_recognized: Optional[Callable] = None
        self.on_transcription_fallback: Optional[Callable] = None
        
    def start_recording(self, callback: Callable[[np.ndarray], None]) -> bool:
        """Start SOAP recording.
        
        Args:
            callback: Function to call with audio data
            
        Returns:
            bool: True if recording started successfully
        """
        if self.soap_recording:
            return False
            
        try:
            # Reset recording state
            self.audio_segments = []
            self.soap_start_time = dt.now()
            self.soap_paused = False
            self.total_pause_duration = 0
            
            # Start recording
            self.soap_recording = True
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
            self.soap_recording = False
            return False
    
    def stop_recording(self) -> Optional[Dict[str, Any]]:
        """Stop SOAP recording and return recording data.
        
        Returns:
            Optional[Dict[str, Any]]: Recording data or None if no recording
        """
        if not self.soap_recording:
            return None
            
        # Stop recording
        self.soap_recording = False
        self.soap_paused = False
        
        # Wait for recording thread to finish
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=2.0)
        
        # Calculate recording duration
        if self.soap_start_time:
            total_duration = (dt.now() - self.soap_start_time).total_seconds()
            actual_duration = total_duration - self.total_pause_duration
        else:
            actual_duration = 0
        
        # Log segment count for debugging
        logging.info(f"RecordingManager: Stopping with {len(self.audio_segments)} segments")
        
        # Combine audio segments
        combined_audio = self._combine_audio_segments()
        
        # Even if no segments were recorded through RecordingManager, return valid recording data
        # The app will handle combining the segments from pending_soap_segments
        recording_data = {
            'audio': combined_audio,  # May be None, app will check
            'duration': actual_duration,
            'start_time': self.soap_start_time,
            'segment_count': len(self.audio_segments)
        }
        
        if combined_audio:
            logging.info(f"SOAP recording stopped. Duration: {actual_duration:.1f}s, Segments: {len(self.audio_segments)}")
        else:
            logging.warning("RecordingManager: No segments in RecordingManager, app will use pending_soap_segments")
        
        return recording_data
    
    def pause_recording(self) -> bool:
        """Pause SOAP recording.
        
        Returns:
            bool: True if paused successfully
        """
        if not self.soap_recording or self.soap_paused:
            return False
            
        self.soap_paused = True
        self.soap_pause_start_time = dt.now()
        logging.info("SOAP recording paused")
        return True
    
    def resume_recording(self) -> bool:
        """Resume SOAP recording.
        
        Returns:
            bool: True if resumed successfully
        """
        if not self.soap_recording or not self.soap_paused:
            return False
            
        # Calculate pause duration
        if self.soap_pause_start_time:
            pause_duration = (dt.now() - self.soap_pause_start_time).total_seconds()
            self.total_pause_duration += pause_duration
            
        self.soap_paused = False
        self.soap_pause_start_time = None
        logging.info("SOAP recording resumed")
        return True
    
    def cancel_recording(self) -> None:
        """Cancel SOAP recording without processing."""
        self.soap_recording = False
        self.soap_paused = False
        self.audio_segments = []
        self.soap_start_time = None
        self.total_pause_duration = 0
        
        # Wait for recording thread
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=2.0)
            
        logging.info("SOAP recording cancelled")
    
    def add_audio_segment(self, audio_data: np.ndarray) -> None:
        """Add audio segment to recording.
        
        Args:
            audio_data: Audio data as numpy array
        """
        if self.soap_recording and not self.soap_paused:
            self.audio_segments.append(audio_data)
            logging.debug(f"RecordingManager: Added segment #{len(self.audio_segments)}, shape={audio_data.shape if hasattr(audio_data, 'shape') else 'unknown'}")
        else:
            logging.debug(f"RecordingManager: Segment not added - recording={self.soap_recording}, paused={self.soap_paused}")
    
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
    
    def _recording_loop(self, callback: Callable[[np.ndarray], None]) -> None:
        """Recording loop thread function.
        
        Args:
            callback: Function to call with audio data
        """
        while self.soap_recording:
            if not self.soap_paused:
                # Get audio data (implement based on your audio capture method)
                # This is a placeholder - actual implementation depends on audio source
                time.sleep(0.1)  # Prevent busy loop
            else:
                time.sleep(0.1)  # Check less frequently when paused
    
    def _combine_audio_segments(self) -> Optional[AudioSegment]:
        """Combine audio segments into single AudioSegment.
        
        Returns:
            Optional[AudioSegment]: Combined audio or None if no segments
        """
        if not self.audio_segments:
            return None
            
        try:
            # Convert numpy arrays to AudioSegment
            combined = AudioSegment.empty()
            
            for segment in self.audio_segments:
                if isinstance(segment, AudioSegment):
                    # Already an AudioSegment, just add it
                    combined += segment
                elif isinstance(segment, np.ndarray):
                    # Convert numpy array to AudioSegment
                    # Get sample rate from audio handler (should be 48000)
                    sample_rate = getattr(self.audio_handler, 'sample_rate', 48000)
                    
                    # Ensure correct format
                    if segment.dtype == np.float32:
                        # Convert float32 to int16
                        audio_data = (segment * 32767).astype(np.int16)
                    else:
                        audio_data = segment.astype(np.int16)
                    
                    audio_segment = AudioSegment(
                        audio_data.tobytes(),
                        frame_rate=sample_rate,  # Use actual sample rate
                        sample_width=2,
                        channels=1
                    )
                    combined += audio_segment
                else:
                    logging.warning(f"Unknown audio segment type: {type(segment)}")
            
            return combined
            
        except Exception as e:
            logging.error(f"Failed to combine audio segments: {e}")
            return None
    
    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self.soap_recording
    
    @property
    def is_paused(self) -> bool:
        """Check if recording is paused."""
        return self.soap_paused
    
    @property
    def recording_duration(self) -> float:
        """Get current recording duration in seconds."""
        if not self.soap_start_time:
            return 0.0
            
        total_duration = (dt.now() - self.soap_start_time).total_seconds()
        return total_duration - self.total_pause_duration