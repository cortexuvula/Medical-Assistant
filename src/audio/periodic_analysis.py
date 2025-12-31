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
    """Manages periodic analysis of audio during recording.

    Thread Safety:
        This class uses threading.Event for clean shutdown coordination
        and callback completion signaling. The timer thread is daemon
        to prevent blocking application exit.
    """

    def __init__(self, interval_seconds: int = 120):
        """Initialize the periodic analyzer.

        Args:
            interval_seconds: Interval between analyses in seconds (default: 120 = 2 minutes)
        """
        self.interval_seconds = interval_seconds
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._callback_complete = threading.Event()  # Signals when callback finishes
        self._callback_complete.set()  # Initially set (no callback running)

        # Protected by _lock
        self._timer: Optional[threading.Timer] = None
        self._countdown_thread: Optional[threading.Thread] = None
        self._is_running = False
        self._start_time: Optional[float] = None
        self._analysis_count = 0
        self._callback: Optional[Callable] = None
        self._countdown_callback: Optional[Callable[[int], None]] = None
        self._seconds_remaining = 0

    @property
    def is_running(self) -> bool:
        """Thread-safe check if analyzer is running."""
        with self._lock:
            return self._is_running

    @property
    def analysis_count(self) -> int:
        """Thread-safe access to analysis count."""
        with self._lock:
            return self._analysis_count

    def set_interval(self, seconds: int) -> None:
        """Set the analysis interval.

        Args:
            seconds: New interval in seconds (takes effect on next cycle)
        """
        with self._lock:
            self.interval_seconds = seconds
            logging.info(f"Analysis interval set to {seconds}s")

    def set_countdown_callback(self, callback: Optional[Callable[[int], None]]) -> None:
        """Set a callback to receive countdown updates.

        Args:
            callback: Function that receives seconds remaining, or None to disable
        """
        with self._lock:
            self._countdown_callback = callback

    def start(self, callback: Callable):
        """Start periodic analysis.

        Args:
            callback: Function to call for each analysis
        """
        with self._lock:
            if self._is_running:
                logging.warning("Periodic analyzer is already running")
                return

            self._is_running = True
            self._stop_event.clear()
            self._start_time = time.time()
            self._analysis_count = 0
            self._callback = callback

        # Schedule first analysis after interval
        self._schedule_next_analysis()
        logging.info(f"Started periodic analysis with {self.interval_seconds}s interval")

    def stop(self, wait_for_callback: bool = True, timeout: float = 5.0):
        """Stop periodic analysis gracefully.

        Args:
            wait_for_callback: If True, wait for any in-progress callback to complete
            timeout: Maximum time to wait for callback completion
        """
        with self._lock:
            if not self._is_running:
                return

            self._is_running = False
            self._stop_event.set()
            self._seconds_remaining = 0  # Stop countdown

            # Cancel pending timer (legacy support)
            if self._timer:
                self._timer.cancel()
                timer = self._timer
                self._timer = None
            else:
                timer = None

            # Get reference to countdown thread
            countdown_thread = self._countdown_thread
            self._countdown_thread = None

            analysis_count = self._analysis_count

        # Wait for timer thread to finish if it was running (legacy)
        if timer and timer.is_alive():
            timer.join(timeout=2.0)

        # Wait for countdown thread to finish
        if countdown_thread and countdown_thread.is_alive():
            countdown_thread.join(timeout=2.0)

        # Wait for callback to complete using Event (thread-safe, no busy-wait)
        if wait_for_callback:
            if not self._callback_complete.wait(timeout=timeout):
                logging.warning("Callback did not complete within timeout")

        # Clear countdown display
        with self._lock:
            callback = self._countdown_callback
        if callback:
            try:
                callback(-1)  # Signal stop (negative = hide countdown)
            except Exception:
                pass

        logging.info(f"Stopped periodic analysis after {analysis_count} analyses")

    def _schedule_next_analysis(self):
        """Schedule the next analysis with countdown updates."""
        with self._lock:
            if not self._is_running:
                return

            self._seconds_remaining = self.interval_seconds

            # Start countdown thread for per-second updates
            self._countdown_thread = threading.Thread(
                target=self._countdown_loop,
                daemon=True,
                name=f"PeriodicAnalysisCountdown-{self._analysis_count + 1}"
            )
            self._countdown_thread.start()

    def _countdown_loop(self):
        """Countdown loop that updates every second and triggers analysis."""
        try:
            while self._seconds_remaining > 0 and not self._stop_event.is_set():
                # Send countdown update if callback is set
                with self._lock:
                    callback = self._countdown_callback

                if callback:
                    try:
                        callback(self._seconds_remaining)
                    except Exception as e:
                        logging.error(f"Error in countdown callback: {e}")

                time.sleep(1)
                self._seconds_remaining -= 1

            # Time's up - perform analysis if not stopped
            if not self._stop_event.is_set():
                # Signal "Analyzing..." (0 seconds)
                with self._lock:
                    callback = self._countdown_callback
                if callback:
                    try:
                        callback(0)
                    except Exception:
                        pass

                self._perform_analysis()

        except Exception as e:
            logging.error(f"Error in countdown loop: {e}")

    def _perform_analysis(self):
        """Perform the periodic analysis."""
        # Check if we should run (outside lock first for quick exit)
        if self._stop_event.is_set():
            return

        callback = None
        elapsed_time = 0.0
        analysis_num = 0

        # Signal that callback is starting
        self._callback_complete.clear()

        with self._lock:
            if not self._is_running or not self._callback:
                self._callback_complete.set()
                return

            self._analysis_count += 1
            analysis_num = self._analysis_count
            elapsed_time = time.time() - self._start_time if self._start_time else 0.0
            callback = self._callback

        try:
            logging.info(f"Performing periodic analysis #{analysis_num} at {elapsed_time:.1f}s")

            # Call the callback function (outside lock to prevent blocking)
            if callback:
                callback(analysis_num, elapsed_time)

        except Exception as e:
            logging.error(f"Error in periodic analysis callback: {e}", exc_info=True)
        finally:
            # Signal that callback is complete
            self._callback_complete.set()

            # Schedule next analysis (only if still running)
            if not self._stop_event.is_set():
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