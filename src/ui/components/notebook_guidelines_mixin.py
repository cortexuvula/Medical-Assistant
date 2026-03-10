"""
Guidelines-related mixin for NotebookTabs.

This mixin provides all clinical guidelines related methods for the
NotebookTabs class, including guidelines upload, library management,
batch progress tracking, and batch results display.
"""

from __future__ import annotations

import tkinter as tk
from typing import Any, Dict, List

from utils.structured_logging import get_logger

logger = get_logger(__name__)


class NotebookGuidelinesMixin:
    """Mixin providing clinical guidelines methods for NotebookTabs.

    Expects the host class to provide:
        - self.parent: The parent window (WorkflowUI)
        - self.components: Dict of UI component references
    """

    def _show_guidelines_upload_dialog(self) -> None:
        """Show the clinical guidelines upload dialog."""
        try:
            # Check if the guidelines upload manager is available before opening dialog.
            # Catch all exceptions (not just ImportError) because importing the rag
            # package may trigger cascading imports that fail with other error types
            # in a frozen PyInstaller bundle.
            try:
                from rag.guidelines_upload_manager import get_guidelines_upload_manager
            except Exception:
                logger.info("Guidelines upload manager not available")
                # Use status bar instead of messagebox to avoid potential Tk
                # grab_set() conflicts that crash macOS .app bundles.
                if hasattr(self.parent, 'status_manager'):
                    self.parent.status_manager.info(
                        "Guidelines not configured \u2013 "
                        "go to Settings \u2192 Preferences \u2192 RAG & Guidelines"
                    )
                else:
                    self._show_guidelines_not_implemented()
                return

            from ui.dialogs.guidelines_upload_dialog import GuidelinesUploadDialog

            self._guidelines_dialog = None

            def on_upload(files: List[str], options: Dict[str, Any]) -> None:
                """Handle upload start."""
                self._process_guidelines_uploads(files, options)

            dialog = GuidelinesUploadDialog(self.parent, on_upload=on_upload)
            self._guidelines_dialog = dialog
            # REMOVED: dialog.wait_window()  # Don't block - let dialog be non-modal
            # Dialog will auto-close when upload starts or user cancels

        except Exception as e:
            self._guidelines_dialog = None
            logger.error(f"Error showing guidelines upload dialog: {e}", exc_info=True)
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error(f"Failed to open guidelines upload: {e}")

    def _process_guidelines_uploads(self, files: List[str], options: Dict[str, Any]) -> None:
        """Queue guidelines for background processing.

        Args:
            files: List of file paths to upload
            options: Upload options (specialty, source, version, etc.)
        """
        try:
            # Get processing queue
            queue = self.parent.processing_queue

            if not queue:
                from tkinter import messagebox
                messagebox.showerror(
                    "Processing Queue Unavailable",
                    "Background processing is not available.",
                    parent=self.parent
                )
                return

            # Add batch to queue (returns immediately)
            batch_id = queue.add_guideline_batch(files, options)

            logger.info(f"Queued {len(files)} guidelines", batch_id=batch_id)

            # Show non-modal progress dialog
            self.parent.after(0, lambda: self._show_guideline_batch_progress(batch_id))

        except Exception as e:
            logger.error(f"Failed to queue guidelines: {e}")
            from tkinter import messagebox
            messagebox.showerror("Upload Error", f"Failed to start upload: {e}", parent=self.parent)

    def _dismiss_guidelines_dialog_and_notify(self) -> None:
        """Safely dismiss the guidelines dialog before showing a notification.

        This prevents Tk grab conflicts on macOS where showing a messagebox
        while another dialog holds grab_set() causes the app to crash.
        """
        dialog = getattr(self, '_guidelines_dialog', None)
        if dialog:
            try:
                dialog.destroy()
            except Exception:
                pass
            self._guidelines_dialog = None
        self._show_guidelines_not_implemented()

    def _show_guideline_batch_progress(self, batch_id: str) -> None:
        """Show non-modal progress dialog for guideline batch.

        Args:
            batch_id: Batch identifier from queue
        """
        from ui.dialogs.guidelines_upload_dialog import GuidelinesUploadProgressDialog

        queue = self.parent.processing_queue
        batch_info = queue.get_guideline_batch_status(batch_id)

        if not batch_info:
            logger.error("Batch not found", batch_id=batch_id)
            return

        # Create non-modal progress dialog
        dialog = GuidelinesUploadProgressDialog(
            parent=self.parent,
            batch_id=batch_id,
            queue_manager=queue
        )

        # Track dialog for "show progress" menu item
        if not hasattr(self.parent, 'guideline_progress_dialogs'):
            self.parent.guideline_progress_dialogs = {}
        self.parent.guideline_progress_dialogs[batch_id] = dialog

        dialog.show()

    def _show_guideline_batch_results(self, batch_info: dict) -> None:
        """Show batch results dialog for guideline uploads (Fix 9).

        Args:
            batch_info: Batch status dictionary from processing queue
        """
        try:
            from ui.dialogs.guidelines_batch_results_dialog import GuidelinesBatchResultsDialog
            import os

            # Build results list from batch info
            results = []
            for fp in batch_info.get("file_paths", []):
                fname = os.path.basename(fp)
                is_error = any(
                    e.get("file_path") == fp or e.get("filename") == fname
                    for e in batch_info.get("errors", [])
                )
                is_skipped = fname in batch_info.get("skipped_files", [])
                if is_error:
                    error_msg = next(
                        (e.get("error_message", "Unknown error")
                         for e in batch_info.get("errors", [])
                         if e.get("file_path") == fp or e.get("filename") == fname),
                        "Unknown error"
                    )
                    results.append({
                        "filename": fname,
                        "file_path": fp,
                        "status": "failed",
                        "error": error_msg,
                    })
                elif is_skipped:
                    results.append({
                        "filename": fname,
                        "file_path": fp,
                        "status": "skipped",
                        "error": "Duplicate",
                    })
                else:
                    results.append({
                        "filename": fname,
                        "file_path": fp,
                        "status": "success",
                        "error": "",
                    })

            def retry_failed(failed_paths):
                if failed_paths:
                    self._process_guidelines_uploads(failed_paths, batch_info.get("options", {}))

            GuidelinesBatchResultsDialog(
                self.parent,
                results=results,
                on_retry=retry_failed,
            )
        except Exception as e:
            logger.error(f"Failed to show batch results: {e}")

    def _show_guidelines_library_dialog(self) -> None:
        """Show the clinical guidelines library dialog."""
        try:
            from ui.dialogs.guidelines_library_dialog import GuidelinesLibraryDialog
            from rag.guidelines_vector_store import get_guidelines_vector_store

            store = get_guidelines_vector_store()

            def on_delete(guideline_id: str) -> bool:
                return store.delete_guideline_complete(guideline_id)

            def on_refresh():
                return store.list_guidelines()

            dialog = GuidelinesLibraryDialog(
                self.parent,
                on_delete=on_delete,
                on_refresh=on_refresh,
            )
            dialog.wait_window()

        except Exception as e:
            logger.error(f"Error showing guidelines library dialog: {e}", exc_info=True)
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error(f"Failed to open guidelines library: {e}")

    def _show_guidelines_not_implemented(self) -> None:
        """Show message that guidelines upload is not yet fully implemented."""
        from tkinter import messagebox
        messagebox.showinfo(
            "Guidelines Upload",
            "Guidelines upload manager is being set up.\n\n"
            "Please ensure the clinical guidelines database is configured:\n"
            "\u2022 Set CLINICAL_GUIDELINES_DATABASE_URL in .env\n"
            "\u2022 Run guidelines migrations",
            parent=self.parent
        )
