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
from ui.status_manager import StatusManager


class RecordingManager:
    """Manages SOAP recording functionality."""
    
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
        sample_rate = getattr(self.audio_handler, 'sample_rate', 48000)
        sample_width = getattr(self.audio_handler, 'sample_width', 2)
        channels = getattr(self.audio_handler, 'channels', 1)
        
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
    
    def _recording_loop(self, callback: Callable[[np.ndarray], None]) -> None:
        """Recording loop thread function.
        
        Args:
            callback: Function to call with audio data
        """
        while self.audio_state_manager.get_state() in [RecordingState.RECORDING, RecordingState.PAUSED]:
            if self.audio_state_manager.is_recording():
                # Get audio data (implement based on your audio capture method)
                # This is a placeholder - actual implementation depends on audio source
                time.sleep(0.1)  # Prevent busy loop
            else:
                time.sleep(0.1)  # Check less frequently when paused
    
    
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