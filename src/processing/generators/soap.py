"""
SOAP Note Generator Module

Handles SOAP note generation from transcripts.
"""

from tkinter import messagebox
from tkinter.constants import DISABLED, NORMAL, RIGHT
from typing import TYPE_CHECKING

from ai.ai import create_soap_note_streaming
from utils.structured_logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from core.app import MedicalAssistantApp


class SOAPGeneratorMixin:
    """Mixin for SOAP note generation functionality."""

    app: "MedicalAssistantApp"

    def create_soap_note(self) -> None:
        """Create a SOAP note from the selected text using AI with streaming display.

        Shows AI-generated text progressively as it's generated, providing
        better user feedback during long generation operations.
        """
        transcript = self.app.transcript_text.get("1.0", "end").strip()
        if not transcript:
            messagebox.showwarning("Create SOAP Note", "There is no transcript to process.")
            return

        # Get context before starting background task
        context_text = self.app.context_text.get("1.0", "end").strip()

        # Disable button and show progress
        if self.app.soap_button:
            self.app.soap_button.config(state=DISABLED)
        self.app.progress_bar.pack(side=RIGHT, padx=10)
        self.app.progress_bar.start()

        # Prepare SOAP text widget for streaming
        self._start_streaming_display(self.app.soap_text, "Generating SOAP note...")

        # Switch to SOAP tab to show streaming output
        self.app.after(0, lambda: self.app.notebook.select(1))

        # Create streaming callback
        def on_chunk(chunk: str):
            """Called for each chunk of streaming response."""
            self._append_streaming_chunk(self.app.soap_text, chunk)

        def task() -> None:
            try:
                # Use streaming API call
                result = create_soap_note_streaming(
                    transcript,
                    context_text,
                    on_chunk=on_chunk
                )

                # Store the values we need for database operations
                soap_note = result
                filename = "Transcript"

                # Schedule UI finalization on main thread
                def finalize():
                    # Stop progress indicator
                    self.app.progress_bar.stop()
                    self.app.progress_bar.pack_forget()

                    # Re-enable button
                    if self.app.soap_button:
                        self.app.soap_button.config(state=NORMAL)

                    # Replace streaming content with formatted version
                    # The result from create_soap_note_streaming is cleaned and formatted
                    self._update_text_widget_content(self.app.soap_text, soap_note)

                    # Update status
                    self.app.status_manager.success("SOAP note created")

                    # Give focus to SOAP text widget
                    self.app.soap_text.focus_set()

                    # Save to database - only create new entry if no current recording exists
                    if hasattr(self.app, 'current_recording_id') and self.app.current_recording_id:
                        logger.debug(f"Updating existing recording {self.app.current_recording_id} with SOAP note")
                        success = self.app.db.update_recording(
                            self.app.current_recording_id,
                            soap_note=soap_note
                        )
                        if success:
                            logger.info(f"Updated existing recording {self.app.current_recording_id} with SOAP note")
                            # Set selected_recording_id so analyses can save correctly
                            self.app.selected_recording_id = self.app.current_recording_id
                            logger.debug(f"Set selected_recording_id to {self.app.selected_recording_id} for analysis save")
                        else:
                            logger.error(f"Failed to update recording {self.app.current_recording_id} with SOAP note")
                    else:
                        logger.debug("No current_recording_id set, creating new database entry")
                        self.app._save_soap_recording_to_database(filename, transcript, soap_note)
                        logger.info(f"Created new recording with ID: {self.app.current_recording_id}")

                    # Auto-run all analyses in parallel to the side panels
                    # Each method submits work to thread pool, so they can safely run concurrently
                    logger.info(f"Scheduling auto-analysis for SOAP note ({len(soap_note)} chars)")

                    self.app.after(0, lambda sn=soap_note: self._run_medication_to_panel(sn))
                    self.app.after(0, lambda sn=soap_note: self._run_diagnostic_to_panel(sn))
                    self.app.after(0, lambda sn=soap_note: self._run_compliance_to_panel(sn))

                self.app.after(0, finalize)

            except Exception as e:
                logger.error(f"SOAP note creation failed: {e}")
                error_msg = str(e)  # Capture before closure
                def handle_error():
                    self.app.progress_bar.stop()
                    self.app.progress_bar.pack_forget()
                    if self.app.soap_button:
                        self.app.soap_button.config(state=NORMAL)
                    self.app.status_manager.error(f"SOAP note creation failed: {error_msg}")
                self.app.after(0, handle_error)

        # Use I/O executor for task management since it involves UI coordination
        self.app.io_executor.submit(task)


__all__ = ["SOAPGeneratorMixin"]
