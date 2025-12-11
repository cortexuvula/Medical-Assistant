"""
Text Processing Controller Module

Handles text editing and AI processing operations including refine,
improve, copy, clear, append, and scratch/delete operations.

This controller extracts text processing logic from the main App class
to improve maintainability and separation of concerns.
"""

import logging
import tkinter as tk
from tkinter import messagebox, DISABLED, NORMAL, RIGHT, END
from typing import TYPE_CHECKING, Callable, Optional
import concurrent.futures

if TYPE_CHECKING:
    from core.app import MedicalDictationApp
    import ttkbootstrap as ttk

logger = logging.getLogger(__name__)


class TextProcessingController:
    """Controller for managing text processing operations.

    This class coordinates:
    - Text refinement via AI
    - Text improvement via AI
    - Copy/clear/append operations
    - Scratch that / delete last word
    - Active widget management
    - Database updates for text changes
    """

    def __init__(self, app: 'MedicalDictationApp'):
        """Initialize the text processing controller.

        Args:
            app: Reference to the main application instance
        """
        self.app = app

    def get_active_text_widget(self) -> tk.Widget:
        """Get the currently active text widget based on selected tab.

        Returns:
            The text widget for the currently selected tab
        """
        # Get the currently selected tab index
        selected_tab = self.app.notebook.index('current')

        # Return the appropriate text widget based on the selected tab
        if selected_tab == 0:  # Transcript tab
            return self.app.transcript_text
        elif selected_tab == 1:  # SOAP Note tab
            return self.app.soap_text
        elif selected_tab == 2:  # Referral tab
            return self.app.referral_text
        elif selected_tab == 3:  # Letter tab
            return self.app.letter_text
        else:
            # Default to transcript text if we can't determine the active tab
            return self.app.transcript_text

    def refine_text(self) -> None:
        """Refine text using AI processor."""
        active_widget = self.get_active_text_widget()
        text = active_widget.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Empty Text", "Please add text before refining.")
            return

        # Show progress
        self.app.status_manager.progress("Refining text...")
        self.app.refine_button.config(state=DISABLED)
        self.app.progress_bar.pack(side=RIGHT, padx=10)
        self.app.progress_bar.start()

        def task():
            # Use AI processor
            result = self.app.ai_processor.refine_text(text)

            # Update UI on main thread
            self.app.after(0, lambda: self._handle_ai_result(result, "refine", active_widget))

        # Run in background
        self.app.io_executor.submit(task)

    def improve_text(self) -> None:
        """Improve text using AI processor."""
        active_widget = self.get_active_text_widget()
        text = active_widget.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Empty Text", "Please add text before improving.")
            return

        # Show progress
        self.app.status_manager.progress("Improving text...")
        self.app.improve_button.config(state=DISABLED)
        self.app.progress_bar.pack(side=RIGHT, padx=10)
        self.app.progress_bar.start()

        def task():
            # Use AI processor
            result = self.app.ai_processor.improve_text(text)

            # Update UI on main thread
            self.app.after(0, lambda: self._handle_ai_result(result, "improve", active_widget))

        # Run in background
        self.app.io_executor.submit(task)

    def _handle_ai_result(self, result: dict, operation: str, widget: tk.Widget) -> None:
        """Handle AI processing result.

        Args:
            result: Result dictionary from AI processor
            operation: Operation type ('refine' or 'improve')
            widget: Target text widget
        """
        self.app.progress_bar.stop()
        self.app.progress_bar.pack_forget()

        if result["success"]:
            # Update text widget
            widget.delete("1.0", tk.END)
            widget.insert("1.0", result["text"])
            self.app.status_manager.success(f"Text {operation}d successfully")
        else:
            self.app.status_manager.error(f"Failed to {operation} text: {result['error']}")

        # Re-enable button
        if operation == "refine":
            self.app.refine_button.config(state=NORMAL)
        elif operation == "improve":
            self.app.improve_button.config(state=NORMAL)

    def process_text_with_ai(
        self,
        api_func: Callable[[str], str],
        success_message: str,
        button: 'ttk.Button',
        target_widget: tk.Widget,
        processor_type: str = "text"
    ) -> None:
        """Process text with AI using a generic approach.

        Args:
            api_func: The API function to call for processing
            success_message: Message to show on success
            button: Button to disable during processing
            target_widget: Text widget containing the text
            processor_type: Type of processor for error messages
        """
        text = target_widget.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Process Text", "There is no text to process.")
            return

        self.app.status_manager.progress("Processing text...")
        button.config(state=DISABLED)
        self.app.progress_bar.pack(side=RIGHT, padx=10)
        self.app.progress_bar.start()

        def task() -> None:
            try:
                # Use IO executor for the AI API call (I/O-bound operation)
                result_future = self.app.io_executor.submit(api_func, text)
                # Get result with timeout to prevent hanging
                result = result_future.result(timeout=60)

                # Schedule UI update on the main thread
                self.app.after(0, lambda: self._update_text_area(
                    result, success_message, button, target_widget
                ))
            except concurrent.futures.TimeoutError:
                self.app.after(0, lambda: [
                    self.app.status_manager.error(f"Timeout processing {processor_type}"),
                    button.config(state=NORMAL),
                    self.app.progress_bar.stop(),
                    self.app.progress_bar.pack_forget()
                ])
            except Exception as e:
                logging.error(f"Error processing text: {str(e)}", exc_info=True)
                self.app.after(0, lambda: [
                    self.app.status_manager.error(f"Error processing {processor_type}: {str(e)}"),
                    button.config(state=NORMAL),
                    self.app.progress_bar.stop(),
                    self.app.progress_bar.pack_forget()
                ])

        # Use executor for the task since it involves UI coordination
        self.app.executor.submit(task)

    def _update_text_area(
        self,
        new_text: str,
        success_message: str,
        button: 'ttk.Button',
        target_widget: tk.Widget
    ) -> None:
        """Update text widget with new content and sync to database.

        Args:
            new_text: The new text content
            success_message: Message to show on success
            button: Button to re-enable
            target_widget: Text widget to update
        """
        target_widget.edit_separator()
        target_widget.delete("1.0", tk.END)
        target_widget.insert(tk.END, new_text)
        target_widget.edit_separator()

        # Update database if we have a current recording
        if self.app.current_recording_id is not None:
            try:
                # Determine which field to update based on the target widget
                field_name = self._get_field_name_for_widget(target_widget)

                # Update database if we identified a field to update
                if field_name:
                    update_kwargs = {field_name: new_text}
                    if self.app.db.update_recording(self.app.current_recording_id, **update_kwargs):
                        logging.info(f"Updated recording ID {self.app.current_recording_id} with new {field_name}")
                        success_message = f"{success_message} and saved to database"
                    else:
                        logging.warning(f"Failed to update recording ID {self.app.current_recording_id} with {field_name}")
            except Exception as e:
                logging.error(f"Error updating database: {str(e)}", exc_info=True)

        self.app.status_manager.success(success_message)
        button.config(state=NORMAL)
        self.app.status_manager.show_progress(False)

        # Trigger document generated event for auto-save
        self.app.event_generate("<<DocumentGenerated>>", when="tail")

    def _get_field_name_for_widget(self, widget: tk.Widget) -> Optional[str]:
        """Get the database field name for a text widget.

        Args:
            widget: The text widget

        Returns:
            Field name string or None if not found
        """
        if widget == self.app.soap_text:
            return 'soap_note'
        elif widget == self.app.referral_text:
            return 'referral'
        elif widget == self.app.letter_text:
            return 'letter'
        elif widget == self.app.transcript_text:
            return 'transcript'
        elif widget == self.app.chat_text:
            return 'chat'
        return None

    def copy_text(self) -> None:
        """Copy active text widget content to clipboard."""
        active_widget = self.get_active_text_widget()
        self.app.clipboard_clear()
        self.app.clipboard_append(active_widget.get("1.0", tk.END))
        self.app.update_status("Text copied to clipboard.")

    def clear_text(self) -> None:
        """Clear transcript text after confirmation."""
        if messagebox.askyesno("Clear Text", "Clear the text?"):
            self.app.transcript_text.delete("1.0", tk.END)
            self.app.text_chunks.clear()
            self.app.audio_segments.clear()

    def append_text(self, text: str) -> None:
        """Append text to transcript with proper formatting.

        Args:
            text: Text to append
        """
        current = self.app.transcript_text.get("1.0", "end-1c")
        if (self.app.capitalize_next or not current or current[-1] in ".!?") and text:
            text = text[0].upper() + text[1:]
            self.app.capitalize_next = False
        self.app.transcript_text.insert(tk.END, (" " if current and current[-1] != "\n" else "") + text)
        self.app.text_chunks.append(f"chunk_{len(self.app.text_chunks)}")
        self.app.transcript_text.see(tk.END)

    def scratch_that(self) -> None:
        """Remove the last added text chunk."""
        if not self.app.text_chunks:
            self.app.update_status("Nothing to scratch.")
            return
        tag = self.app.text_chunks.pop()
        ranges = self.app.transcript_text.tag_ranges(tag)
        if ranges:
            self.app.transcript_text.delete(ranges[0], ranges[1])
            self.app.transcript_text.tag_delete(tag)
            self.app.update_status("Last added text removed.")
        else:
            self.app.update_status("No tagged text found.")

    def delete_last_word(self) -> None:
        """Delete the last word from transcript."""
        current = self.app.transcript_text.get("1.0", "end-1c")
        if current:
            words = current.split()
            self.app.transcript_text.delete("1.0", tk.END)
            self.app.transcript_text.insert(tk.END, " ".join(words[:-1]))
            self.app.transcript_text.see(tk.END)

    def append_text_to_widget(self, text: str, widget: tk.Widget) -> None:
        """Append text to a specific widget with proper formatting.

        Args:
            text: Text to append
            widget: Target text widget
        """
        current = widget.get("1.0", "end-1c")
        if (self.app.capitalize_next or not current or current[-1] in ".!?") and text:
            text = text[0].upper() + text[1:]
            self.app.capitalize_next = False

        # Add space if needed
        separator = " " if current and current[-1] not in ("\n", " ") else ""
        widget.insert(tk.END, separator + text)
        widget.see(tk.END)

    def undo_text(self) -> None:
        """Undo the last text operation."""
        try:
            active_widget = self.get_active_text_widget()
            active_widget.edit_undo()
        except tk.TclError:
            self.app.update_status("Nothing to undo.")

    def redo_text(self) -> None:
        """Redo the last undone text operation."""
        try:
            active_widget = self.get_active_text_widget()
            active_widget.edit_redo()
        except tk.TclError:
            self.app.update_status("Nothing to redo.")
