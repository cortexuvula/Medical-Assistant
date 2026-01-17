"""
Base Generators Module

Provides streaming helpers and shared utilities for document generation.
"""

from tkinter.constants import DISABLED, NORMAL, RIGHT
from typing import TYPE_CHECKING

from utils.structured_logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from core.app import MedicalAssistantApp


class StreamingMixin:
    """Mixin providing streaming display utilities for document generation."""

    app: "MedicalAssistantApp"  # Type hint for inherited attribute

    def _append_streaming_chunk(self, widget, chunk: str) -> None:
        """Append a chunk of text to widget during streaming.

        Thread-safe method to update text widget from streaming callback.

        Args:
            widget: The text widget to update
            chunk: The text chunk to append
        """
        def update():
            try:
                # Enable editing temporarily
                current_state = widget.cget('state')
                widget.configure(state='normal')
                # Insert chunk at end
                widget.insert('end', chunk)
                # Auto-scroll to show new content
                widget.see('end')
                # Restore state if it was disabled
                if current_state == 'disabled':
                    widget.configure(state='disabled')
                # Force update to show changes immediately
                widget.update_idletasks()
            except Exception as e:
                logger.debug(f"Error appending streaming chunk: {e}")

        # Schedule UI update on main thread
        self.app.after(0, update)

    def _start_streaming_display(self, widget, status_msg: str) -> None:
        """Prepare widget for streaming display.

        Args:
            widget: The text widget to prepare
            status_msg: Status message to display
        """
        def setup():
            try:
                # Clear the widget
                widget.configure(state='normal')
                widget.delete('1.0', 'end')
                widget.update_idletasks()
            except Exception as e:
                logger.debug(f"Error preparing streaming display: {e}")

        self.app.after(0, setup)
        self.app.status_manager.progress(status_msg)

    def _finish_streaming_display(self, widget, success_msg: str, button=None) -> None:
        """Finalize widget after streaming completes.

        Args:
            widget: The text widget that was updated
            success_msg: Success message to display
            button: Optional button to re-enable
        """
        def finish():
            try:
                # Add edit separator for undo history
                widget.edit_separator()
                # Stop progress
                self.app.progress_bar.stop()
                self.app.progress_bar.pack_forget()
                # Re-enable button if provided
                if button:
                    button.config(state=NORMAL)
                # Update status
                self.app.status_manager.success(success_msg)
            except Exception as e:
                logger.debug(f"Error finishing streaming display: {e}")

        self.app.after(0, finish)

    def _update_text_widget_content(self, widget, content: str) -> None:
        """Replace text widget content with new content.

        Used to update streaming output with formatted/cleaned version.

        Args:
            widget: The text widget to update
            content: The new content to display
        """
        try:
            widget.configure(state='normal')
            widget.delete('1.0', 'end')
            widget.insert('1.0', content)
            widget.see('1.0')  # Scroll to top
            widget.edit_separator()  # Add undo separator
            widget.update_idletasks()  # Force widget refresh
            logger.debug("Updated text widget with formatted content")
        except Exception as e:
            logger.error(f"Error updating text widget: {e}")

    def _update_analysis_panel(self, widget, content: str) -> None:
        """Update an analysis panel with new content.

        Args:
            widget: The text widget to update
            content: The content to display
        """
        if widget is None:
            return

        try:
            widget.config(state='normal')
            widget.delete('1.0', 'end')
            widget.insert('1.0', content)
            widget.config(state='disabled')
        except Exception as e:
            logger.error(f"Failed to update analysis panel: {e}")


__all__ = ["StreamingMixin"]
