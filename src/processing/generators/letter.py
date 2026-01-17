"""
Letter Generator Module

Handles letter generation from transcripts and SOAP notes.
"""

from tkinter import messagebox
from tkinter.constants import DISABLED, NORMAL, RIGHT
from typing import TYPE_CHECKING

from ai.ai import create_letter_streaming
from utils.structured_logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from core.app import MedicalAssistantApp


class LetterGeneratorMixin:
    """Mixin for letter generation functionality."""

    app: "MedicalAssistantApp"

    def create_letter(self) -> None:
        """Create a letter from transcript with streaming display.

        Shows AI-generated text progressively as it's generated, providing
        better user feedback during long generation operations.
        """
        # Get source, recipient type, and specifications
        source, recipient_type, specs = self.app.show_letter_options_dialog()

        if source is None:  # User cancelled
            return

        # Get the appropriate text based on source
        if source == "transcript":
            text = self.app.transcript_text.get("1.0", "end").strip()
            source_name = "Transcript"
        else:  # source == "soap"
            text = self.app.soap_text.get("1.0", "end").strip()
            source_name = "SOAP"

        if not text:
            messagebox.showwarning("Empty Text", f"The {source_name} tab is empty. Please add content before creating a letter.")
            return

        # Get recipient type display name for status messages
        recipient_names = {
            "insurance": "Insurance Company",
            "employer": "Employer",
            "specialist": "Specialist",
            "patient": "Patient",
            "school": "School",
            "legal": "Legal/Attorney",
            "government": "Government Agency",
            "other": "Other"
        }
        recipient_display = recipient_names.get(recipient_type, "recipient")

        # Disable button and show progress
        if self.app.letter_button:
            self.app.letter_button.config(state=DISABLED)
        self.app.progress_bar.pack(side=RIGHT, padx=10)
        self.app.progress_bar.start()

        # Prepare letter text widget for streaming
        self._start_streaming_display(self.app.letter_text, f"Generating letter to {recipient_display}...")

        # Switch to Letter tab to show streaming output
        self.app.after(0, lambda: self.app.notebook.select(3))

        # Create streaming callback
        def on_chunk(chunk: str):
            """Called for each chunk of streaming response."""
            self._append_streaming_chunk(self.app.letter_text, chunk)

        def task() -> None:
            try:
                # Log that we're starting letter generation
                logger.info(f"Starting letter generation from {source_name} to {recipient_type} with specs: {specs}")

                # Use streaming API call
                result = create_letter_streaming(
                    text,
                    recipient_type,
                    specs,
                    on_chunk=on_chunk
                )

                # Log the successful completion
                logger.info(f"Successfully generated letter to {recipient_type}")

                # Check if result contains error message
                if result.startswith("[Error"):
                    raise Exception(result)

                # Schedule UI finalization on main thread
                def finalize():
                    # Stop progress indicator
                    self.app.progress_bar.stop()
                    self.app.progress_bar.pack_forget()

                    # Re-enable button
                    if self.app.letter_button:
                        self.app.letter_button.config(state=NORMAL)

                    # Add edit separator for undo support
                    try:
                        self.app.letter_text.edit_separator()
                    except Exception:
                        pass

                    # Update status
                    self.app.status_manager.success(f"Letter to {recipient_display} generated from {source_name}")

                self.app.after(0, finalize)

            except Exception as e:
                logger.error(f"Letter creation failed: {e}")
                def handle_error():
                    self.app.progress_bar.stop()
                    self.app.progress_bar.pack_forget()
                    if self.app.letter_button:
                        self.app.letter_button.config(state=NORMAL)
                    self.app.status_manager.error(f"Letter creation failed: {str(e)}")
                self.app.after(0, handle_error)

        # Submit the task to be executed
        self.app.io_executor.submit(task)


__all__ = ["LetterGeneratorMixin"]
