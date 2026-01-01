"""
Periodic Analysis Controller Module

Handles periodic analysis during recording including differential diagnosis
generation, audio segment extraction, and analysis display updates.

This controller extracts periodic analysis logic from the main App class
to improve maintainability and separation of concerns.
"""

import logging
import tkinter as tk
from typing import TYPE_CHECKING, Optional

from audio.periodic_analysis import PeriodicAnalyzer, AudioSegmentExtractor

if TYPE_CHECKING:
    from core.app import MedicalDictationApp

logger = logging.getLogger(__name__)


class PeriodicAnalysisController:
    """Controller for managing periodic analysis during recording.

    This class coordinates:
    - Starting/stopping periodic analysis
    - Audio segment extraction for analysis
    - Transcription and differential diagnosis generation
    - Analysis display updates in the UI
    - Countdown timer display
    - Patient context integration
    """

    def __init__(self, app: 'MedicalDictationApp'):
        """Initialize the periodic analysis controller.

        Args:
            app: Reference to the main application instance
        """
        self.app = app
        self.patient_context: str = ""

    def start_periodic_analysis(self) -> None:
        """Start periodic analysis during recording."""
        try:
            # Get interval from UI (default 2 minutes = 120 seconds)
            interval_seconds = 120
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
            logging.info(f"Started periodic analysis with {interval_seconds}s interval")

        except Exception as e:
            logging.error(f"Failed to start periodic analysis: {e}")
            self.app.status_manager.error("Failed to start advanced analysis")

    def _capture_patient_context(self) -> None:
        """Capture patient context from the Context panel."""
        try:
            self.patient_context = ""
            if hasattr(self.app, 'ui') and hasattr(self.app.ui, 'components'):
                context_widget = self.app.ui.components.get('context_text')
                if context_widget:
                    self.patient_context = context_widget.get("1.0", "end-1c").strip()
                    if self.patient_context:
                        logging.info(f"Captured {len(self.patient_context)} chars of patient context")
        except Exception as e:
            logging.error(f"Error capturing patient context: {e}")

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
            logging.error(f"Error updating countdown: {e}")

    def stop_periodic_analysis(self) -> None:
        """Stop periodic analysis."""
        try:
            if self.app.periodic_analyzer and self.app.periodic_analyzer.is_running:
                self.app.periodic_analyzer.stop()
                self.app.periodic_analyzer = None  # Clear reference to prevent reuse
                logging.info("Stopped periodic analysis")
        except Exception as e:
            logging.error(f"Error stopping periodic analysis: {e}")

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
                logging.warning("No audio available for periodic analysis")
                return

            # Transcribe the audio segment
            self.app.status_manager.info(f"Transcribing for analysis #{analysis_count}...")
            transcript = self.app.audio_handler.transcribe_audio(audio_segment)

            if not transcript:
                logging.warning("No transcript generated for periodic analysis")
                return

            # Build enhanced transcript with context if available
            enhanced_transcript = transcript
            if self.patient_context:
                enhanced_transcript = (
                    f"Patient Context:\n{self.patient_context}\n\n"
                    f"Current Transcript:\n{transcript}"
                )
                logging.info("Including patient context in differential diagnosis")

            # Generate differential diagnosis
            self.app.status_manager.info("Generating differential diagnosis...")
            result = self.app.ai_processor.generate_differential_diagnosis(enhanced_transcript)

            # OperationResult: check .success and access .value for data
            if result.success:
                # Format analysis text (simpler format - timestamp added by UI)
                formatted_time = f"{int(elapsed_time // 60)}:{int(elapsed_time % 60):02d}"
                result_text = result.value.get('text', '') if result.value else ''
                analysis_text = (
                    f"Analysis #{analysis_count} (recording time: {formatted_time})\n"
                    f"{result_text}"
                )

                # Update UI on main thread using accumulated display
                self.app.after(0, lambda: self.update_analysis_display(analysis_text))
                self.app.status_manager.success(f"Analysis #{analysis_count} completed")
            else:
                error_msg = result.error or 'Unknown error'
                logging.error(f"Failed to generate analysis: {error_msg}")
                self.app.status_manager.error("Failed to generate analysis")

        except Exception as e:
            logging.error(f"Error in periodic analysis: {e}")
            self.app.status_manager.error("Error during advanced analysis")

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
                    text_widget.insert(tk.END, "\n\n" + "─" * 50 + "\n\n")

                text_widget.insert(tk.END, analysis_text)
                text_widget.see(tk.END)
        except Exception as e:
            logging.error(f"Error updating analysis display: {e}")

    def clear_advanced_analysis_text(self) -> None:
        """Clear the Advanced Analysis Results text area and show empty state."""
        try:
            # Use RecordTab's clear method which shows empty state hint
            if hasattr(self.app, 'ui') and hasattr(self.app.ui, 'record_tab'):
                record_tab = self.app.ui.record_tab
                if hasattr(record_tab, '_clear_analysis'):
                    record_tab._clear_analysis()
                    logging.info("Cleared advanced analysis text")
                    return

            # Fallback to direct clear
            if 'record_notes_text' in self.app.ui.components:
                self.app.ui.components['record_notes_text'].delete('1.0', tk.END)
                logging.info("Cleared advanced analysis text")
        except Exception as e:
            logging.error(f"Error clearing advanced analysis text: {e}")
