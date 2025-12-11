"""
Periodic Analysis Controller Module

Handles periodic analysis during recording including differential diagnosis
generation, audio segment extraction, and analysis display updates.

This controller extracts periodic analysis logic from the main App class
to improve maintainability and separation of concerns.
"""

import logging
import tkinter as tk
from typing import TYPE_CHECKING

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
    """

    def __init__(self, app: 'MedicalDictationApp'):
        """Initialize the periodic analysis controller.

        Args:
            app: Reference to the main application instance
        """
        self.app = app

    def start_periodic_analysis(self) -> None:
        """Start periodic analysis during recording."""
        try:
            # Create periodic analyzer if not exists
            if not self.app.periodic_analyzer:
                self.app.periodic_analyzer = PeriodicAnalyzer(interval_seconds=120)  # 2 minutes

            # Start the periodic analysis
            self.app.periodic_analyzer.start(self.perform_periodic_analysis)
            logging.info("Started periodic analysis for advanced diagnosis")

        except Exception as e:
            logging.error(f"Failed to start periodic analysis: {e}")
            self.app.status_manager.error("Failed to start advanced analysis")

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

            # Generate differential diagnosis
            self.app.status_manager.info("Generating differential diagnosis...")
            result = self.app.ai_processor.generate_differential_diagnosis(transcript)

            if result.get('success'):
                # Format and display the analysis
                formatted_time = f"{int(elapsed_time // 60)}:{int(elapsed_time % 60):02d}"
                analysis_text = (
                    f"{'='*60}\n"
                    f"Analysis #{analysis_count} at {formatted_time}\n"
                    f"{'='*60}\n\n"
                    f"{result['text']}\n\n"
                )

                # Update UI on main thread
                self.app.after(0, lambda: self.update_analysis_display(analysis_text))
                self.app.status_manager.success(f"Analysis #{analysis_count} completed")
            else:
                error_msg = result.get('error', 'Unknown error')
                logging.error(f"Failed to generate analysis: {error_msg}")
                self.app.status_manager.error("Failed to generate analysis")

        except Exception as e:
            logging.error(f"Error in periodic analysis: {e}")
            self.app.status_manager.error("Error during advanced analysis")

    def update_analysis_display(self, analysis_text: str) -> None:
        """Update the analysis display in the UI.

        Args:
            analysis_text: The analysis text to display
        """
        try:
            if 'record_notes_text' in self.app.ui.components:
                # Clear existing content first
                self.app.ui.components['record_notes_text'].delete('1.0', tk.END)
                # Insert new analysis text
                self.app.ui.components['record_notes_text'].insert(tk.END, analysis_text)
                # Scroll to bottom
                self.app.ui.components['record_notes_text'].see(tk.END)
        except Exception as e:
            logging.error(f"Error updating analysis display: {e}")

    def clear_advanced_analysis_text(self) -> None:
        """Clear the Advanced Analysis Results text area."""
        try:
            if 'record_notes_text' in self.app.ui.components:
                self.app.ui.components['record_notes_text'].delete('1.0', tk.END)
                logging.info("Cleared advanced analysis text")
        except Exception as e:
            logging.error(f"Error clearing advanced analysis text: {e}")
