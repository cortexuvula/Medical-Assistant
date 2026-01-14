"""
Recordings Tab Events Mixin

Provides event handlers for button clicks, batch processing, and selection changes.
Extracted from RecordingsTab for better separation of concerns.
"""

import tkinter as tk
import tkinter.messagebox
import logging
import threading
from typing import Optional

from ui.ui_constants import Colors


class RecordingsTabEventsMixin:
    """Mixin providing event handling methods for RecordingsTab.

    This mixin expects the following attributes on the class:
    - parent: Reference to main application
    - components: Dictionary of UI components
    - data_provider: RecordingsDataProvider instance
    - recordings_tree: Treeview widget
    - recording_count_label: Label for count display
    - batch_progress_dialog: Dialog for batch progress
    - batch_failed_count: Count of failed items in batch
    """

    # ========================================
    # Delete Operations
    # ========================================

    def _delete_selected_recording(self) -> None:
        """Delete the selected recording(s)."""
        selection = self.recordings_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select a recording to delete.")
            return

        count = len(selection)
        if count == 1:
            message = "Are you sure you want to delete this recording?"
        else:
            message = f"Are you sure you want to delete {count} recordings?"

        if not tk.messagebox.askyesno("Confirm Delete", message):
            return

        deleted_count = 0
        errors = []

        for item in selection:
            rec_id = int(self.recordings_tree.item(item, 'text'))

            try:
                self.data_provider.delete_recording(rec_id)
                self.recordings_tree.delete(item)
                deleted_count += 1

            except Exception as e:
                logging.error(f"Error deleting recording {rec_id}: {e}")
                errors.append(f"Recording {rec_id}: {str(e)}")

        self.invalidate_recordings_cache()

        total_count = len(self.recordings_tree.get_children())
        self.recording_count_label.config(text=f"{total_count} recording{'s' if total_count != 1 else ''}")

        if deleted_count == count:
            self.parent.status_manager.success(f"{deleted_count} recording{'s' if deleted_count > 1 else ''} deleted")
        else:
            error_msg = f"Deleted {deleted_count} of {count} recordings. Errors:\n" + "\n".join(errors[:3])
            if len(errors) > 3:
                error_msg += f"\n... and {len(errors) - 3} more errors"
            tk.messagebox.showwarning("Partial Delete", error_msg)

    def _clear_all_recordings(self) -> None:
        """Clear all recordings from the database."""
        result = tkinter.messagebox.askyesno(
            "Clear All Recordings",
            "WARNING: This will permanently delete ALL recordings from the database.\n\n"
            "This action cannot be undone!\n\n"
            "Are you absolutely sure you want to continue?",
            icon="warning"
        )

        if not result:
            return

        result2 = tkinter.messagebox.askyesno(
            "Final Confirmation",
            "This is your last chance to cancel.\n\n"
            "Delete ALL recordings permanently?",
            icon="warning"
        )

        if not result2:
            return

        try:
            success = self.data_provider.clear_all_recordings()

            if success:
                for item in self.recordings_tree.get_children():
                    self.recordings_tree.delete(item)

                self.recording_count_label.config(text="0 recordings")

                from utils.cleanup_utils import clear_all_content
                clear_all_content(self.parent)

                self.parent.current_recording_id = None
                self.invalidate_recordings_cache()

                self.parent.status_manager.success("All recordings cleared from database")

                tkinter.messagebox.showinfo(
                    "Success",
                    "All recordings have been cleared from the database."
                )
            else:
                tkinter.messagebox.showerror(
                    "Error",
                    "Failed to clear recordings from database."
                )

        except Exception as e:
            logging.error(f"Error clearing all recordings: {e}")
            tkinter.messagebox.showerror(
                "Clear Error",
                f"Failed to clear recordings: {str(e)}"
            )

    # ========================================
    # Reprocess Operations
    # ========================================

    def _reprocess_failed_recordings(self) -> None:
        """Reprocess selected failed recordings."""
        selection = self.recordings_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select failed recordings to reprocess.")
            return

        failed_recording_ids = []
        non_failed_count = 0

        for item in selection:
            rec_id = int(self.recordings_tree.item(item, 'text'))

            try:
                recording = self.data_provider.get_recording(rec_id)
                if recording and recording.get('processing_status') == 'failed':
                    failed_recording_ids.append(rec_id)
                else:
                    non_failed_count += 1
            except Exception as e:
                logging.error(f"Error checking recording {rec_id}: {e}")

        if not failed_recording_ids:
            if non_failed_count > 0:
                tk.messagebox.showinfo("No Failed Recordings",
                    "None of the selected recordings have failed status.")
            return

        count = len(failed_recording_ids)
        message = f"Reprocess {count} failed recording{'s' if count > 1 else ''}?"
        if non_failed_count > 0:
            message += f"\n\n({non_failed_count} non-failed recording{'s' if non_failed_count > 1 else ''} will be skipped)"

        if not tk.messagebox.askyesno("Confirm Reprocess", message):
            return

        try:
            if hasattr(self.parent, 'reprocess_failed_recordings'):
                self.parent.reprocess_failed_recordings(failed_recording_ids)
                self.parent.status_manager.success(f"Queued {count} recording{'s' if count > 1 else ''} for reprocessing")
                self.parent.after(1000, lambda: self._refresh_recordings_list(force_refresh=True))
            else:
                tk.messagebox.showerror("Error", "Reprocessing functionality not available")

        except Exception as e:
            logging.error(f"Error reprocessing recordings: {e}")
            tk.messagebox.showerror("Reprocess Error", f"Failed to reprocess recordings: {str(e)}")

    # ========================================
    # Batch Processing
    # ========================================

    def _process_selected_recordings(self) -> None:
        """Process selected recordings in batch."""
        selection = self.recordings_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select recordings to process.")
            return

        recording_ids = []
        for item in selection:
            rec_id = int(self.recordings_tree.item(item, 'text'))
            recording_ids.append(rec_id)

        from ui.dialogs.batch_processing_dialog import BatchProcessingDialog

        dialog = BatchProcessingDialog(self.parent, recording_ids)
        result = dialog.show()

        if result:
            self._start_batch_processing(result)

    def _batch_process_files(self) -> None:
        """Open dialog to process audio files in batch."""
        from ui.dialogs.batch_processing_dialog import BatchProcessingDialog

        dialog = BatchProcessingDialog(self.parent)
        result = dialog.show()

        if result:
            self._start_batch_processing(result)

    def _start_batch_processing(self, options: dict) -> None:
        """Start batch processing of recordings or files."""
        from ui.dialogs.batch_progress_dialog import BatchProgressDialog

        if options['source'] == 'database':
            total_count = len(options['recording_ids'])
            item_type = "recordings"
        else:
            total_count = len(options['files'])
            item_type = "files"

        self.batch_progress_dialog = BatchProgressDialog(self.parent, "batch_" + str(id(options)), total_count)

        self.parent.status_manager.progress(f"Starting batch processing of {total_count} {item_type}...")

        process_btn = self.components.get('batch_process_button')
        batch_files_btn = self.components.get('batch_files_button')
        if process_btn:
            process_btn.config(state=tk.DISABLED)
        if batch_files_btn:
            batch_files_btn.config(state=tk.DISABLED)

        self.batch_failed_count = 0

        def task():
            try:
                if options['source'] == 'database':
                    self.parent.document_generators.process_batch_recordings(
                        options['recording_ids'],
                        options,
                        on_complete=lambda: self.parent.after(0, self._on_batch_complete),
                        on_progress=lambda msg, count, total: self.parent.after(0,
                            lambda: self._update_batch_progress(msg, count, total))
                    )
                else:
                    self.parent.document_generators.process_batch_files(
                        options['files'],
                        options,
                        on_complete=lambda: self.parent.after(0, self._on_batch_complete),
                        on_progress=lambda msg, count, total: self.parent.after(0,
                            lambda: self._update_batch_progress(msg, count, total))
                    )
            except Exception as e:
                logging.error(f"Batch processing error: {e}")
                self.parent.after(0, lambda: [
                    self.parent.status_manager.error(f"Batch processing failed: {str(e)}"),
                    self.batch_progress_dialog.add_detail(f"Batch processing failed: {str(e)}", "error"),
                    self._on_batch_complete()
                ])

        def cancel_batch(batch_id):
            if hasattr(self.parent, 'processing_queue') and self.parent.processing_queue:
                self.parent.processing_queue.cancel_batch(batch_id)

        self.batch_progress_dialog.set_cancel_callback(cancel_batch)

        threading.Thread(target=task, daemon=True).start()

    def _update_batch_progress(self, message: str, completed: int, total: int) -> None:
        """Update batch processing progress."""
        self.parent.status_manager.show_determinate_progress(completed, total, message)

        if hasattr(self, 'batch_progress_dialog') and self.batch_progress_dialog:
            failed = self.batch_failed_count
            if "failed" in message.lower():
                self.batch_failed_count += 1
                failed = self.batch_failed_count

            self.batch_progress_dialog.update_progress(completed - failed, failed, message)

            if completed > 0:
                self.batch_progress_dialog.add_detail(
                    f"Recording {completed}/{total}: {message}",
                    "error" if "failed" in message.lower() else "success"
                )

    def _on_batch_complete(self) -> None:
        """Handle batch processing completion."""
        process_btn = self.components.get('batch_process_button')
        batch_files_btn = self.components.get('batch_files_button')
        if process_btn:
            process_btn.config(state=tk.NORMAL)
        if batch_files_btn:
            batch_files_btn.config(state=tk.NORMAL)

        self.parent.status_manager.reset_progress()
        self._refresh_recordings_list()
        self.parent.status_manager.success("Batch processing completed!")

        if hasattr(self, 'batch_progress_dialog') and self.batch_progress_dialog:
            self.batch_progress_dialog = None

        self.batch_failed_count = 0

    # ========================================
    # Selection Change
    # ========================================

    def _on_selection_change(self, event) -> None:
        """Handle selection change in recordings tree."""
        selection = self.recordings_tree.selection()
        total_count = len(self.recordings_tree.get_children())
        selected_count = len(selection)

        if selected_count > 1:
            self.recording_count_label.config(
                text=f"{selected_count} of {total_count} recordings selected"
            )
        else:
            self.recording_count_label.config(
                text=f"{total_count} recording{'s' if total_count != 1 else ''}"
            )


__all__ = ["RecordingsTabEventsMixin"]
