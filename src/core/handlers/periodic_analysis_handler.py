"""
Periodic Analysis Handler

Provides real-time differential diagnosis analysis during recording sessions.
Extracted from RecordingController for better separation of concerns.
"""

import threading
import tkinter as tk
from typing import TYPE_CHECKING, Optional, Dict, Any, List

from audio.periodic_analysis import PeriodicAnalyzer, AudioSegmentExtractor
from utils.differential_tracker import DifferentialTracker
from utils.constants import TimingConstants
from database.database import Database
from utils.structured_logging import get_logger

if TYPE_CHECKING:
    from core.app import MedicalDictationApp

logger = get_logger(__name__)


class PeriodicAnalysisHandler:
    """Handles periodic analysis operations during recording.

    This handler manages:
    - Starting/stopping periodic analysis
    - Performing differential diagnosis analysis
    - Tracking differential evolution across analyses
    - Saving analysis history to database
    - Updating analysis display in UI
    """

    def __init__(self, app: 'MedicalDictationApp'):
        """Initialize the periodic analysis handler.

        Args:
            app: Reference to the main application instance
        """
        self.app = app

        # Analysis state
        self.patient_context: str = ""
        self.differential_tracker = DifferentialTracker()
        self._db: Optional[Database] = None
        self._last_session_id: Optional[int] = None
        self._current_recording_id: Optional[int] = None

    # ========================================
    # Database Access
    # ========================================

    def _get_database(self) -> Database:
        """Get or create database connection."""
        if self._db is None:
            self._db = Database()
        return self._db

    # ========================================
    # Recording ID Management
    # ========================================

    def set_recording_id(self, recording_id: Optional[int]) -> None:
        """Set the current recording ID for linking periodic analyses.

        Args:
            recording_id: The recording ID to link analyses to
        """
        self._current_recording_id = recording_id

    def get_last_session_id(self) -> Optional[int]:
        """Get the last saved periodic analysis session ID.

        Returns:
            The session ID if analyses were saved, None otherwise
        """
        return self._last_session_id

    # ========================================
    # Periodic Analysis Start/Stop
    # ========================================

    def start_periodic_analysis(self) -> None:
        """Start periodic analysis during recording."""
        try:
            # Clear differential tracker for fresh analysis session
            self.differential_tracker.clear()

            # Get interval from UI (default from TimingConstants)
            interval_seconds = TimingConstants.PERIODIC_ANALYSIS_INTERVAL
            if hasattr(self.app, 'ui') and hasattr(self.app.ui, 'record_tab'):
                record_tab = self.app.ui.record_tab
                if hasattr(record_tab, 'get_analysis_interval_seconds'):
                    interval_seconds = record_tab.get_analysis_interval_seconds()

            # Capture patient context from Context panel
            self._capture_patient_context()

            # Create periodic analyzer if not exists
            if not self.app.periodic_analyzer:
                self.app.periodic_analyzer = PeriodicAnalyzer(interval_seconds=interval_seconds)

            # Set countdown callback for UI updates
            self.app.periodic_analyzer.set_countdown_callback(self._on_countdown_update)

            # Start the periodic analysis
            self.app.periodic_analyzer.start(self.perform_periodic_analysis)
            logger.info(f"Started periodic analysis with {interval_seconds}s interval")

            # Run immediate analysis with accumulated audio if recording is in progress
            self._run_immediate_analysis_if_needed()

        except Exception as e:
            logger.error(f"Failed to start periodic analysis: {e}")
            self.app.status_manager.error("Failed to start advanced analysis")

    def stop_periodic_analysis(self, save_to_database: bool = True) -> Optional[int]:
        """Stop periodic analysis and optionally save history to database.

        Args:
            save_to_database: Whether to save the analysis history to database

        Returns:
            The session ID if saved, None otherwise
        """
        session_id = None
        try:
            if self.app.periodic_analyzer and self.app.periodic_analyzer.is_running:
                # Save history before stopping
                if save_to_database:
                    session_id = self._save_periodic_history()

                self.app.periodic_analyzer.stop()
                self.app.periodic_analyzer = None  # Clear reference to prevent reuse
                logger.info("Stopped periodic analysis")

                # Store for later retrieval
                self._last_session_id = session_id
        except Exception as e:
            logger.error(f"Error stopping periodic analysis: {e}")

        return session_id

    # ========================================
    # Context and Immediate Analysis
    # ========================================

    def _capture_patient_context(self) -> None:
        """Capture patient context from the Context panel."""
        try:
            self.patient_context = ""
            if hasattr(self.app, 'ui') and hasattr(self.app.ui, 'components'):
                context_widget = self.app.ui.components.get('context_text')
                if context_widget:
                    self.patient_context = context_widget.get("1.0", "end-1c").strip()
                    if self.patient_context:
                        logger.info(f"Captured {len(self.patient_context)} chars of patient context")
        except Exception as e:
            logger.error(f"Error capturing patient context: {e}")

    def _run_immediate_analysis_if_needed(self) -> None:
        """Run immediate analysis with accumulated audio if recording has been going on.

        This handles the case where user enables Advanced Analysis mid-recording
        and we want to immediately analyze all audio captured so far.
        """
        try:
            # Check if there's accumulated audio worth analyzing
            if not self.app.audio_state_manager:
                return

            # Get actual recording elapsed time from metadata
            metadata = self.app.audio_state_manager.get_recording_metadata()
            elapsed_time = metadata.get('recording_duration', 0)

            # Log segment stats for debugging
            pending, chunks, total = self.app.audio_state_manager.get_segment_stats()
            logger.info(f"Immediate analysis check: elapsed={elapsed_time:.1f}s, "
                        f"pending_segments={pending}, chunks={chunks}, total={total}")

            # Only run immediate analysis if recording has been going for minimum time
            # This avoids running analysis for minimal audio at recording start
            if elapsed_time < TimingConstants.PERIODIC_ANALYSIS_MIN_ELAPSED:
                logger.info("Skipping immediate analysis - recording just started")
                return

            # Check if there's actual audio data
            combined_audio = AudioSegmentExtractor.extract_audio_segment(
                self.app.recording_manager,
                self.app.audio_state_manager
            )
            if combined_audio is None or len(combined_audio) == 0:
                logger.info("Skipping immediate analysis - no audio accumulated yet")
                return

            logger.info(f"Running immediate analysis with {elapsed_time:.1f}s of accumulated audio "
                        f"(actual audio duration: {len(combined_audio)}ms)")

            # Run the analysis in a separate thread to avoid blocking audio capture
            def run_analysis():
                try:
                    self.perform_periodic_analysis(0, elapsed_time)
                except Exception as e:
                    logger.error(f"Error in immediate analysis thread: {e}")

            analysis_thread = threading.Thread(target=run_analysis, daemon=True)
            analysis_thread.start()
            logger.info("Immediate analysis started in background thread")

        except Exception as e:
            logger.error(f"Error running immediate analysis: {e}")
            # Don't fail the whole start - periodic analysis will still run normally

    # ========================================
    # Countdown Updates
    # ========================================

    def _on_countdown_update(self, seconds: int) -> None:
        """Handle countdown updates from the analyzer.

        Args:
            seconds: Seconds remaining (-1 = stopped, 0 = analyzing, >0 = countdown)
        """
        try:
            # Update UI on main thread
            def update_ui():
                if hasattr(self.app, 'ui') and hasattr(self.app.ui, 'record_tab'):
                    record_tab = self.app.ui.record_tab
                    if hasattr(record_tab, 'update_countdown'):
                        if seconds < 0:
                            record_tab.update_countdown(0, clear=True)
                        else:
                            record_tab.update_countdown(seconds)

            self.app.after(0, update_ui)
        except Exception as e:
            logger.error(f"Error updating countdown: {e}")

    # ========================================
    # Save History to Database
    # ========================================

    def _save_periodic_history(self) -> Optional[int]:
        """Save the periodic analysis history to database.

        Returns:
            The session ID (first analysis ID) if saved, None otherwise
        """
        if not self.app.periodic_analyzer:
            return None

        history = self.app.periodic_analyzer.analysis_history
        if not history:
            return None

        try:
            db = self._get_database()
            session_id = None

            # Combine all analyses for the session
            combined_text = self.app.periodic_analyzer.get_combined_history_text()

            # Save the combined session as a single analysis
            metadata = {
                "analysis_type": "periodic_session",
                "total_analyses": len(history),
                "session_start": history[0]["timestamp"] if history else None,
                "session_end": history[-1]["timestamp"] if history else None,
                "total_duration_seconds": history[-1]["elapsed_seconds"] if history else 0,
                "individual_analyses": [
                    {
                        "analysis_number": entry.get("analysis_number"),
                        "elapsed_seconds": entry.get("elapsed_seconds"),
                        "timestamp": entry.get("timestamp"),
                        "differential_count": entry.get("metadata", {}).get("differential_count", 0)
                    }
                    for entry in history
                ]
            }

            # Save to analysis_results table
            session_id = db.save_analysis_result(
                analysis_type="periodic",
                result_text=combined_text,
                recording_id=self._current_recording_id,
                analysis_subtype="differential_evolution",
                result_json=None,
                metadata=metadata,
                patient_context=self.patient_context if self.patient_context else None,
                source_type="Recording",
                source_text=None
            )

            if session_id:
                logger.info(
                    f"Saved periodic analysis session {session_id} "
                    f"with {len(history)} analyses to database"
                )

            # Also save individual analyses for detailed tracking
            for entry in history:
                try:
                    entry_metadata = {
                        "analysis_type": "periodic_individual",
                        "parent_session_id": session_id,
                        "analysis_number": entry.get("analysis_number"),
                        "elapsed_seconds": entry.get("elapsed_seconds"),
                        "differentials": entry.get("metadata", {}).get("differentials", []),
                        "differential_count": entry.get("metadata", {}).get("differential_count", 0)
                    }

                    db.save_analysis_result(
                        analysis_type="periodic",
                        result_text=entry.get("result_text", ""),
                        recording_id=self._current_recording_id,
                        analysis_subtype="differential_snapshot",
                        result_json=entry.get("metadata", {}),
                        metadata=entry_metadata,
                        patient_context=None,
                        source_type="Recording",
                        source_text=None
                    )
                except Exception as e:
                    logger.warning(f"Error saving individual periodic analysis: {e}")

            return session_id

        except Exception as e:
            logger.error(f"Error saving periodic history to database: {e}")
            return None

    # ========================================
    # Session Retrieval
    # ========================================

    def get_periodic_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a saved periodic analysis session.

        Args:
            session_id: The session ID to retrieve

        Returns:
            Session data dictionary or None if not found
        """
        try:
            db = self._get_database()
            # Get the session record
            analyses = db.get_recent_analysis_results(
                analysis_type="periodic",
                limit=200
            )

            for analysis in analyses:
                if analysis.get('id') == session_id:
                    return analysis

            return None
        except Exception as e:
            logger.error(f"Error retrieving periodic session: {e}")
            return None

    def get_linked_periodic_analyses(self, recording_id: int) -> List[Dict[str, Any]]:
        """Get all periodic analyses linked to a recording.

        Args:
            recording_id: The recording ID to search for

        Returns:
            List of periodic analysis records
        """
        try:
            db = self._get_database()
            analyses = db.get_recent_analysis_results(
                analysis_type="periodic",
                limit=500
            )

            return [
                a for a in analyses
                if a.get('recording_id') == recording_id
            ]
        except Exception as e:
            logger.error(f"Error getting linked periodic analyses: {e}")
            return []

    # ========================================
    # Perform Analysis
    # ========================================

    def perform_periodic_analysis(self, analysis_count: int, elapsed_time: float) -> None:
        """Perform periodic analysis callback.

        Args:
            analysis_count: Number of analyses performed so far
            elapsed_time: Time elapsed since recording started
        """
        try:
            # Get current audio segment
            audio_segment = AudioSegmentExtractor.extract_audio_segment(
                self.app.recording_manager,
                self.app.audio_state_manager
            )

            if not audio_segment:
                logger.warning("No audio available for periodic analysis")
                return

            # Transcribe the audio segment
            self.app.status_manager.info(f"Transcribing for analysis #{analysis_count}...")
            transcript = self.app.audio_handler.transcribe_audio(audio_segment)

            if not transcript:
                logger.warning("No transcript generated for periodic analysis")
                return

            # Build enhanced transcript with context if available
            enhanced_transcript = transcript
            if self.patient_context:
                enhanced_transcript = (
                    f"Patient Context:\n{self.patient_context}\n\n"
                    f"Current Transcript:\n{transcript}"
                )
                logger.info("Including patient context in differential diagnosis")

            # Generate differential diagnosis
            self.app.status_manager.info("Generating differential diagnosis...")
            result = self.app.ai_processor.generate_differential_diagnosis(enhanced_transcript)

            # OperationResult: check .success and access .value for data
            if result.success:
                # Format analysis text (simpler format - timestamp added by UI)
                formatted_time = f"{int(elapsed_time // 60)}:{int(elapsed_time % 60):02d}"
                result_text = result.value.get('text', '') if result.value else ''

                # Track differential evolution
                evolution_text = ""
                current_differentials = []
                try:
                    # Parse differentials from the result
                    current_differentials = self.differential_tracker.parse_differentials(result_text)

                    if current_differentials:
                        # Compare with previous
                        evolutions, removed = self.differential_tracker.compare_differentials(current_differentials)

                        # Format evolution text
                        evolution_text = self.differential_tracker.format_evolution_text(
                            evolutions, removed, analysis_count
                        )

                        # Update tracker for next comparison
                        self.differential_tracker.update(current_differentials)

                        logger.info(f"Tracked {len(current_differentials)} differentials, "
                                   f"{len([e for e in evolutions if e.status.value == 'new'])} new, "
                                   f"{len(removed)} removed")
                except Exception as e:
                    logger.error(f"Error tracking differential evolution: {e}")

                analysis_text = (
                    f"Analysis #{analysis_count} (recording time: {formatted_time})\n"
                    f"{result_text}"
                    f"{evolution_text}"
                )

                # Add to history for persistence and retrieval
                if self.app.periodic_analyzer:
                    metadata = {
                        "differentials": [d.__dict__ if hasattr(d, '__dict__') else str(d) for d in current_differentials],
                        "differential_count": len(current_differentials),
                        "has_evolution": bool(evolution_text)
                    }
                    self.app.periodic_analyzer.add_to_history(
                        result_text=result_text + evolution_text,
                        elapsed_seconds=elapsed_time,
                        metadata=metadata
                    )

                # Update UI on main thread using accumulated display
                self.app.after(0, lambda: self.update_analysis_display(analysis_text))
                self.app.status_manager.success(f"Analysis #{analysis_count} completed")
            else:
                error_msg = result.error or 'Unknown error'
                logger.error(f"Failed to generate analysis: {error_msg}")
                self.app.status_manager.error("Failed to generate analysis")

        except Exception as e:
            logger.error(f"Error in periodic analysis: {e}")
            self.app.status_manager.error("Error during advanced analysis")

    # ========================================
    # Display Methods
    # ========================================

    def update_analysis_display(self, analysis_text: str) -> None:
        """Update the analysis display in the UI using accumulated display.

        Args:
            analysis_text: The analysis text to append
        """
        try:
            # Use RecordTab's accumulated display method
            if hasattr(self.app, 'ui') and hasattr(self.app.ui, 'record_tab'):
                record_tab = self.app.ui.record_tab
                if hasattr(record_tab, 'update_analysis_display'):
                    record_tab.update_analysis_display(analysis_text)
                    return

            # Fallback to direct text widget update if RecordTab method not available
            if 'record_notes_text' in self.app.ui.components:
                text_widget = self.app.ui.components['record_notes_text']
                current = text_widget.get('1.0', 'end-1c')

                # Don't overwrite, accumulate
                if current.strip() and "will appear here" not in current:
                    text_widget.insert(tk.END, "\n\n" + "-" * 50 + "\n\n")

                text_widget.insert(tk.END, analysis_text)
                text_widget.see(tk.END)
        except Exception as e:
            logger.error(f"Error updating analysis display: {e}")

    def clear_advanced_analysis_text(self) -> None:
        """Clear the Advanced Analysis Results text area and show empty state."""
        try:
            # Clear differential tracker
            self.differential_tracker.clear()

            # Clear analyzer history if available
            if self.app.periodic_analyzer:
                self.app.periodic_analyzer.clear_history()

            # Use RecordTab's clear method which shows empty state hint
            if hasattr(self.app, 'ui') and hasattr(self.app.ui, 'record_tab'):
                record_tab = self.app.ui.record_tab
                if hasattr(record_tab, '_clear_analysis'):
                    record_tab._clear_analysis()
                    logger.info("Cleared advanced analysis text, differential tracker, and history")
                    return

            # Fallback to direct clear
            if 'record_notes_text' in self.app.ui.components:
                self.app.ui.components['record_notes_text'].delete('1.0', tk.END)
                logger.info("Cleared advanced analysis text, differential tracker, and history")
        except Exception as e:
            logger.error(f"Error clearing advanced analysis text: {e}")

    def get_analysis_history(self) -> dict:
        """Get the analysis history summary.

        Returns:
            Dictionary containing analysis history summary, or empty dict if no analyzer
        """
        if self.app.periodic_analyzer:
            return self.app.periodic_analyzer.get_history_summary()
        return {"total_analyses": 0, "entries": []}

    def get_combined_analysis_text(self) -> str:
        """Get all analysis results combined as text.

        Returns:
            Combined text of all analyses, or empty string if no analyzer
        """
        if self.app.periodic_analyzer:
            return self.app.periodic_analyzer.get_combined_history_text()
        return ""

    def initialize_analysis_display(self) -> None:
        """Initialize the analysis text area for a new recording."""
        if 'record_notes_text' in self.app.ui.components:
            text_widget = self.app.ui.components['record_notes_text']
            text_widget.delete("1.0", tk.END)

            # Show message if Advanced Analysis is enabled
            if hasattr(self.app.ui, 'advanced_analysis_var') and self.app.ui.advanced_analysis_var.get():
                text_widget.insert(
                    "1.0",
                    "Advanced Analysis enabled. First analysis will appear after 2 minutes...\n\n"
                )


__all__ = ["PeriodicAnalysisHandler"]
