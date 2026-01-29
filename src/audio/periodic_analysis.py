"""
Periodic Analysis Module

Handles periodic transcription and analysis of audio during recording
for real-time differential diagnosis generation.
"""

import threading
import time
from datetime import datetime
from typing import Optional, Callable, List, Dict, Any
import numpy as np
from pydub import AudioSegment

from utils.structured_logging import get_logger

logger = get_logger(__name__)


class PeriodicAnalyzer:
    """Manages periodic analysis of audio during recording.

    Thread Safety:
        This class uses threading.Event for clean shutdown coordination
        and callback completion signaling. The timer thread is daemon
        to prevent blocking application exit.
    """

    # Default maximum history entries to keep
    DEFAULT_MAX_HISTORY = 20

    def __init__(self, interval_seconds: int = 120, max_history_items: int = None):
        """Initialize the periodic analyzer.

        Args:
            interval_seconds: Interval between analyses in seconds (default: 120 = 2 minutes)
            max_history_items: Maximum number of analysis results to keep in history
        """
        self.interval_seconds = interval_seconds
        self.max_history_items = max_history_items or self.DEFAULT_MAX_HISTORY
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

        # Analysis history for accumulating results
        self._analysis_history: List[Dict[str, Any]] = []

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

    @property
    def analysis_history(self) -> List[Dict[str, Any]]:
        """Thread-safe access to analysis history.

        Returns:
            Copy of the analysis history list
        """
        with self._lock:
            return list(self._analysis_history)

    def add_to_history(
        self,
        result_text: str,
        elapsed_seconds: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add an analysis result to the history.

        Args:
            result_text: The analysis result text
            elapsed_seconds: Time elapsed since recording started
            metadata: Optional additional metadata (differentials, red flags, etc.)
        """
        with self._lock:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "elapsed_seconds": elapsed_seconds,
                "analysis_number": self._analysis_count,
                "result_text": result_text,
                "metadata": metadata or {}
            }
            self._analysis_history.append(entry)

            # Trim history if exceeded max
            if len(self._analysis_history) > self.max_history_items:
                self._analysis_history.pop(0)

            logger.debug(f"Added analysis #{self._analysis_count} to history "
                         f"(total: {len(self._analysis_history)})")

    def get_history_summary(self) -> Dict[str, Any]:
        """Get a summary of the analysis history.

        Returns:
            Dictionary containing summary statistics and condensed history
        """
        with self._lock:
            if not self._analysis_history:
                return {
                    "total_analyses": 0,
                    "entries": [],
                    "first_analysis": None,
                    "last_analysis": None,
                    "total_duration_seconds": 0
                }

            first = self._analysis_history[0]
            last = self._analysis_history[-1]

            return {
                "total_analyses": len(self._analysis_history),
                "entries": [
                    {
                        "analysis_number": entry["analysis_number"],
                        "timestamp": entry["timestamp"],
                        "elapsed_seconds": entry["elapsed_seconds"],
                        "preview": entry["result_text"][:200] + "..." if len(entry["result_text"]) > 200 else entry["result_text"],
                        "has_metadata": bool(entry.get("metadata"))
                    }
                    for entry in self._analysis_history
                ],
                "first_analysis": first["timestamp"],
                "last_analysis": last["timestamp"],
                "total_duration_seconds": last["elapsed_seconds"]
            }

    def get_combined_history_text(self) -> str:
        """Get all analysis results combined as a single text.

        Useful for saving the entire session's analysis to database or file.

        Returns:
            Combined text of all analyses in the history
        """
        with self._lock:
            if not self._analysis_history:
                return ""

            parts = []
            for entry in self._analysis_history:
                formatted_time = f"{int(entry['elapsed_seconds'] // 60)}:{int(entry['elapsed_seconds'] % 60):02d}"
                header = f"Analysis #{entry['analysis_number']} (recording time: {formatted_time})"
                parts.append(f"{header}\n{entry['result_text']}")

            return "\n\n" + "─" * 50 + "\n\n".join(parts)

    def clear_history(self) -> None:
        """Clear the analysis history."""
        with self._lock:
            self._analysis_history.clear()
            logger.info("Cleared analysis history")

    def set_interval(self, seconds: int) -> None:
        """Set the analysis interval.

        Args:
            seconds: New interval in seconds (takes effect on next cycle)
        """
        with self._lock:
            self.interval_seconds = seconds
            logger.info(f"Analysis interval set to {seconds}s")

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
                logger.warning("Periodic analyzer is already running")
                return

            self._is_running = True
            self._stop_event.clear()
            self._start_time = time.time()
            self._analysis_count = 0
            self._callback = callback
            # Clear history for fresh session
            self._analysis_history.clear()

        # Schedule first analysis after interval
        self._schedule_next_analysis()
        logger.info(f"Started periodic analysis with {self.interval_seconds}s interval")

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
                logger.warning("Callback did not complete within timeout")

        # Clear countdown display
        with self._lock:
            callback = self._countdown_callback
        if callback:
            try:
                callback(-1)  # Signal stop (negative = hide countdown)
            except Exception as e:
                logger.debug(f"Error in countdown callback during stop: {e}")

        logger.info(f"Stopped periodic analysis after {analysis_count} analyses")

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
                        logger.error(f"Error in countdown callback: {e}")

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
                    except Exception as e:
                        logger.debug(f"Error signaling 'Analyzing...' state to countdown callback: {e}")

                self._perform_analysis()

        except Exception as e:
            logger.error(f"Error in countdown loop: {e}")

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
            logger.info(f"Performing periodic analysis #{analysis_num} at {elapsed_time:.1f}s")

            # Call the callback function (outside lock to prevent blocking)
            if callback:
                callback(analysis_num, elapsed_time)

        except Exception as e:
            logger.error(f"Error in periodic analysis callback: {e}", exc_info=True)
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
                logger.warning("No audio data available for analysis")
                return None
                
            # get_combined_audio() already returns an AudioSegment object
            # No need to convert, just return it directly
            return combined_audio
            
        except Exception as e:
            logger.error(f"Error extracting audio segment: {e}")
            return None