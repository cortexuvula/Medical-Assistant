"""
Periodic Analysis Module

Handles periodic transcription and analysis of audio during recording
for real-time differential diagnosis generation.
"""

import logging
import threading
import time
from datetime import datetime
from typing import Optional, Callable
import numpy as np
from pydub import AudioSegment


class PeriodicAnalyzer:
    """Manages periodic analysis of audio during recording."""
    
    def __init__(self, interval_seconds: int = 120):
        """Initialize the periodic analyzer.
        
        Args:
            interval_seconds: Interval between analyses in seconds (default: 120 = 2 minutes)
        """
        self.interval_seconds = interval_seconds
        self.timer: Optional[threading.Timer] = None
        self.is_running = False
        self.start_time: Optional[float] = None
        self.analysis_count = 0
        self.callback: Optional[Callable] = None
        
    def start(self, callback: Callable):
        """Start periodic analysis.
        
        Args:
            callback: Function to call for each analysis
        """
        if self.is_running:
            logging.warning("Periodic analyzer is already running")
            return
            
        self.is_running = True
        self.start_time = time.time()
        self.analysis_count = 0
        self.callback = callback
        
        # Schedule first analysis after interval
        self._schedule_next_analysis()
        logging.info(f"Started periodic analysis with {self.interval_seconds}s interval")
        
    def stop(self):
        """Stop periodic analysis."""
        self.is_running = False
        
        if self.timer:
            self.timer.cancel()
            self.timer = None
            
        logging.info(f"Stopped periodic analysis after {self.analysis_count} analyses")
        
    def _schedule_next_analysis(self):
        """Schedule the next analysis."""
        if not self.is_running:
            return
            
        self.timer = threading.Timer(self.interval_seconds, self._perform_analysis)
        self.timer.daemon = True  # Make timer thread daemon so it doesn't prevent shutdown
        self.timer.start()
        
    def _perform_analysis(self):
        """Perform the periodic analysis."""
        if not self.is_running or not self.callback:
            return
            
        try:
            self.analysis_count += 1
            elapsed_time = time.time() - self.start_time
            
            logging.info(f"Performing periodic analysis #{self.analysis_count} at {elapsed_time:.1f}s")
            
            # Call the callback function
            self.callback(self.analysis_count, elapsed_time)
            
            # Schedule next analysis
            self._schedule_next_analysis()
            
        except Exception as e:
            logging.error(f"Error in periodic analysis: {e}")
            # Continue scheduling even if there's an error
            self._schedule_next_analysis()


class AudioSegmentExtractor:
    """Extracts audio segments for periodic analysis."""
    
    @staticmethod
    def extract_audio_segment(recording_manager, audio_state_manager) -> Optional[AudioSegment]:
        """Extract current audio segment from recording.
        
        Args:
            recording_manager: The recording manager instance
            audio_state_manager: The audio state manager instance
            
        Returns:
            AudioSegment or None if no audio available
        """
        try:
            # Get current audio data from state manager
            combined_audio = audio_state_manager.get_combined_audio()
            
            if combined_audio is None or len(combined_audio) == 0:
                logging.warning("No audio data available for analysis")
                return None
                
            # get_combined_audio() already returns an AudioSegment object
            # No need to convert, just return it directly
            return combined_audio
            
        except Exception as e:
            logging.error(f"Error extracting audio segment: {e}")
            return None