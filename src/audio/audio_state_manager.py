"""
Audio State Manager Module

Provides centralized, thread-safe management of audio state and segments
for the recording functionality. This consolidates all audio segment
storage and manipulation into a single source of truth.
"""

import threading
import logging
from typing import List, Optional, Tuple
from enum import Enum
from datetime import datetime
import numpy as np
from pydub import AudioSegment

from audio.constants import (
    MAX_AUDIO_MEMORY_MB,
    MAX_RECORDING_DURATION_MINUTES,
    SEGMENT_COMBINE_THRESHOLD,
)


class RecordingState(Enum):
    """Recording state enumeration."""
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    PROCESSING = "processing"


class AudioStateManager:
    """
    Centralized, thread-safe audio state management.
    
    This class consolidates all audio segment storage and provides
    thread-safe operations for adding, combining, and retrieving audio data.
    """
    
    def __init__(self, combine_threshold: int = SEGMENT_COMBINE_THRESHOLD):
        """
        Initialize the AudioStateManager.

        Args:
            combine_threshold: Number of segments before automatic combination
        """
        self._lock = threading.Lock()
        self._segments: List[np.ndarray] = []
        self._combined_chunks: List[AudioSegment] = []
        self._recording_state = RecordingState.IDLE
        self._combine_threshold = combine_threshold

        # Recording metadata
        self._start_time: Optional[datetime] = None
        self._pause_start_time: Optional[datetime] = None
        self._total_pause_duration: float = 0.0

        # Audio format parameters (set during first segment)
        self._sample_rate: Optional[int] = None
        self._sample_width: Optional[int] = None
        self._channels: Optional[int] = None

        # Memory tracking
        self._estimated_memory_bytes: int = 0
        self._memory_warning_issued: bool = False
        self._max_memory_bytes: int = MAX_AUDIO_MEMORY_MB * 1024 * 1024
        self._max_duration_seconds: float = MAX_RECORDING_DURATION_MINUTES * 60

        logging.info(f"AudioStateManager initialized with combine_threshold={combine_threshold}, "
                    f"max_memory={MAX_AUDIO_MEMORY_MB}MB, max_duration={MAX_RECORDING_DURATION_MINUTES}min")
    
    def start_recording(self) -> None:
        """Start a new recording session."""
        with self._lock:
            if self._recording_state != RecordingState.IDLE:
                raise RuntimeError(f"Cannot start recording in {self._recording_state} state")
            
            # Clear any previous data
            self._clear_internal()
            
            # Set new recording state
            self._recording_state = RecordingState.RECORDING
            self._start_time = datetime.now()
            self._total_pause_duration = 0.0
            
            logging.info("Recording started")
    
    def pause_recording(self) -> None:
        """Pause the current recording."""
        with self._lock:
            if self._recording_state != RecordingState.RECORDING:
                raise RuntimeError(f"Cannot pause recording in {self._recording_state} state")
            
            self._recording_state = RecordingState.PAUSED
            self._pause_start_time = datetime.now()
            
            logging.info("Recording paused")
    
    def resume_recording(self) -> None:
        """Resume a paused recording."""
        with self._lock:
            if self._recording_state != RecordingState.PAUSED:
                raise RuntimeError(f"Cannot resume recording in {self._recording_state} state")
            
            if self._pause_start_time:
                pause_duration = (datetime.now() - self._pause_start_time).total_seconds()
                self._total_pause_duration += pause_duration
            
            self._recording_state = RecordingState.RECORDING
            self._pause_start_time = None
            
            logging.info("Recording resumed")
    
    def stop_recording(self) -> None:
        """Stop the current recording."""
        with self._lock:
            if self._recording_state not in [RecordingState.RECORDING, RecordingState.PAUSED]:
                raise RuntimeError(f"Cannot stop recording in {self._recording_state} state")
            
            # Handle pause duration if still paused
            if self._recording_state == RecordingState.PAUSED and self._pause_start_time:
                pause_duration = (datetime.now() - self._pause_start_time).total_seconds()
                self._total_pause_duration += pause_duration
            
            self._recording_state = RecordingState.PROCESSING
            
            logging.info("Recording stopped")
    
    def add_segment(self, audio_data: np.ndarray, sample_rate: int = 16000,
                   sample_width: int = 2, channels: int = 1) -> bool:
        """
        Add an audio segment to the manager.

        Args:
            audio_data: Numpy array of audio data
            sample_rate: Sample rate of the audio
            sample_width: Sample width in bytes
            channels: Number of audio channels

        Returns:
            True if segment was added, False if limits exceeded
        """
        with self._lock:
            if self._recording_state != RecordingState.RECORDING:
                logging.debug(f"Ignoring audio segment in {self._recording_state} state")
                return False

            # Store audio format from first segment
            if self._sample_rate is None:
                self._sample_rate = sample_rate
                self._sample_width = sample_width
                self._channels = channels

            # Track memory usage
            segment_bytes = audio_data.nbytes
            self._estimated_memory_bytes += segment_bytes

            # Check memory limits and warn if approaching
            if not self._memory_warning_issued and self._estimated_memory_bytes > self._max_memory_bytes * 0.8:
                memory_mb = self._estimated_memory_bytes / (1024 * 1024)
                logging.warning(f"Recording memory usage high: {memory_mb:.1f}MB "
                              f"(80% of {MAX_AUDIO_MEMORY_MB}MB limit)")
                self._memory_warning_issued = True

            # Check duration limits
            if self._start_time:
                elapsed = (datetime.now() - self._start_time).total_seconds() - self._total_pause_duration
                if elapsed > self._max_duration_seconds:
                    logging.error(f"Recording exceeded max duration of {MAX_RECORDING_DURATION_MINUTES} minutes")
                    return False

            # Log incoming segment info
            logging.debug(f"Incoming audio segment: shape={audio_data.shape}, "
                        f"dtype={audio_data.dtype}, ndim={audio_data.ndim}")

            # Add segment to list
            self._segments.append(audio_data.copy())  # Copy to prevent external modifications

            # Check if we should combine segments
            if len(self._segments) >= self._combine_threshold:
                self._combine_segments()

            logging.debug(f"Added audio segment: total_segments={len(self._segments)}, "
                        f"combined_chunks={len(self._combined_chunks)}, "
                        f"memory={self._estimated_memory_bytes / (1024*1024):.1f}MB")
            return True
    
    def _combine_segments(self) -> None:
        """Combine pending segments into a larger chunk. Must be called within lock."""
        if not self._segments or self._sample_rate is None:
            return
        
        try:
            # Normalize all segments to have consistent shape
            normalized_segments = []
            for i, segment in enumerate(self._segments):
                # Ensure segment is numpy array
                if not isinstance(segment, np.ndarray):
                    segment = np.array(segment)
                
                # Handle different dimensions
                if segment.ndim == 2:
                    # If stereo (2D), convert to mono by averaging channels
                    if segment.shape[1] == 2:
                        segment = segment.mean(axis=1)
                    else:
                        # If 2D but single channel, flatten it
                        segment = segment.flatten()
                elif segment.ndim > 2:
                    # Flatten any higher dimensional arrays
                    segment = segment.flatten()
                
                # Ensure 1D array
                segment = segment.flatten()
                normalized_segments.append(segment)
                
                logging.debug(f"Normalized segment {i}: shape={segment.shape}, dtype={segment.dtype}")
            
            # Concatenate all normalized arrays
            combined_array = np.concatenate(normalized_segments)
            
            # Ensure correct data type
            if combined_array.dtype != np.int16:
                if combined_array.dtype in [np.float32, np.float64]:
                    # Scale float to int16
                    combined_array = np.clip(combined_array, -1.0, 1.0)
                    combined_array = (combined_array * 32767).astype(np.int16)
                else:
                    combined_array = combined_array.astype(np.int16)
            
            # Create AudioSegment
            combined_segment = AudioSegment(
                data=combined_array.tobytes(),
                sample_width=self._sample_width,
                frame_rate=self._sample_rate,
                channels=self._channels
            )
            
            self._combined_chunks.append(combined_segment)
            num_segments = len(self._segments)
            self._segments.clear()
            
            logging.debug(f"Combined {num_segments} segments into chunk "
                        f"(duration: {len(combined_segment)}ms)")
            
        except Exception as e:
            logging.error(f"Error combining segments: {e}", exc_info=True)
    
    def get_combined_audio(self) -> Optional[AudioSegment]:
        """
        Get all audio combined into a single AudioSegment.
        
        Returns:
            Combined AudioSegment or None if no audio
        """
        with self._lock:
            # First combine any remaining segments
            if self._segments:
                self._combine_segments()
            
            if not self._combined_chunks:
                return None
            
            # Combine all chunks
            try:
                combined = self._combined_chunks[0]
                for chunk in self._combined_chunks[1:]:
                    combined += chunk

                # Log comprehensive audio details for debugging truncation issues
                logging.info(f"Combined audio: duration={len(combined)}ms, "
                           f"frame_rate={combined.frame_rate}, channels={combined.channels}, "
                           f"sample_width={combined.sample_width}, frame_count={combined.frame_count()}")
                return combined
                
            except Exception as e:
                logging.error(f"Error combining audio chunks: {e}", exc_info=True)
                return None
    
    def get_recording_metadata(self) -> dict:
        """
        Get metadata about the current/last recording.
        
        Returns:
            Dictionary with recording metadata
        """
        with self._lock:
            if self._start_time:
                total_duration = (datetime.now() - self._start_time).total_seconds()
                recording_duration = total_duration - self._total_pause_duration
            else:
                total_duration = 0.0
                recording_duration = 0.0
            
            return {
                'state': self._recording_state.value,
                'start_time': self._start_time.isoformat() if self._start_time else None,
                'total_duration': total_duration,
                'recording_duration': recording_duration,
                'pause_duration': self._total_pause_duration,
                'segment_count': len(self._segments),
                'chunk_count': len(self._combined_chunks),
                'sample_rate': self._sample_rate,
                'channels': self._channels
            }
    
    def get_state(self) -> RecordingState:
        """Get the current recording state."""
        with self._lock:
            return self._recording_state
    
    def is_recording(self) -> bool:
        """Check if currently recording (not paused)."""
        with self._lock:
            return self._recording_state == RecordingState.RECORDING
    
    def is_paused(self) -> bool:
        """Check if recording is paused."""
        with self._lock:
            return self._recording_state == RecordingState.PAUSED
    
    def has_audio(self) -> bool:
        """Check if any audio data is stored."""
        with self._lock:
            return bool(self._segments or self._combined_chunks)
    
    def clear_all(self) -> None:
        """Clear all audio data and reset state."""
        with self._lock:
            self._clear_internal()
            self._recording_state = RecordingState.IDLE
            logging.info("All audio data cleared")
    
    def _clear_internal(self) -> None:
        """Internal method to clear data. Must be called within lock."""
        self._segments.clear()
        self._combined_chunks.clear()
        self._start_time = None
        self._pause_start_time = None
        self._total_pause_duration = 0.0
        self._sample_rate = None
        self._sample_width = None
        self._channels = None
        # Reset memory tracking
        self._estimated_memory_bytes = 0
        self._memory_warning_issued = False
    
    def get_segment_stats(self) -> Tuple[int, int, int]:
        """
        Get statistics about stored segments.

        Returns:
            Tuple of (pending_segments, combined_chunks, total_segments)
        """
        with self._lock:
            pending = len(self._segments)
            chunks = len(self._combined_chunks)
            # Estimate segments in chunks
            total = pending + (chunks * self._combine_threshold)
            return (pending, chunks, total)

    def get_memory_stats(self) -> dict:
        """
        Get memory usage statistics.

        Returns:
            Dictionary with memory stats in MB and percentage
        """
        with self._lock:
            used_mb = self._estimated_memory_bytes / (1024 * 1024)
            max_mb = self._max_memory_bytes / (1024 * 1024)
            percentage = (self._estimated_memory_bytes / self._max_memory_bytes) * 100 if self._max_memory_bytes > 0 else 0

            return {
                'used_mb': round(used_mb, 2),
                'max_mb': round(max_mb, 2),
                'percentage': round(percentage, 1),
                'warning_issued': self._memory_warning_issued
            }