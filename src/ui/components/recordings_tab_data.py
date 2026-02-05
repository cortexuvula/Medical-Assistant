"""
Recordings Tab Data Mixin

Provides data loading, caching, filtering, and export operations.
Extracted from RecordingsTab for better separation of concerns.
"""

import tkinter as tk
import tkinter.messagebox
import threading
import os
import time
from typing import Optional, List, Dict, Any
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class RecordingsTabDataMixin:
    """Mixin providing data handling methods for RecordingsTab.

    This mixin expects the following attributes on the class:
    - parent: Reference to main application
    - data_provider: RecordingsDataProvider instance
    - recordings_tree: Treeview widget
    - recordings_search_var: StringVar for search
    - recording_count_label: Label for count display
    - _recordings_cache: Cache for recordings list
    - _recordings_cache_time: Time of last cache update
    - RECORDINGS_CACHE_TTL: Cache time-to-live in seconds
    - _auto_refresh_interval: Auto-refresh interval in ms
    - _auto_refresh_job: After job ID for auto-refresh
    - _refresh_in_progress: Flag to prevent concurrent refreshes
    """

    def _refresh_recordings_list(self, force_refresh: bool = False) -> None:
        """Refresh the recordings list from database with caching.

        Uses a cache to avoid reloading on every tab switch.
        Runs database queries in background thread to avoid blocking UI.

        Args:
            force_refresh: Force reload from database ignoring cache
        """
        if self._refresh_in_progress:
            logger.debug("Refresh already in progress, skipping")
            return

        current_time = time.time()

        # Check cache first
        if (not force_refresh
                and self._recordings_cache is not None
                and current_time - self._recordings_cache_time < self.RECORDINGS_CACHE_TTL):
            self._populate_recordings_tree(self._recordings_cache)
            return

        self._show_loading_state()
        self._refresh_in_progress = True

        def task():
            try:
                if hasattr(self.data_provider, 'get_recordings_lightweight'):
                    recordings = self.data_provider.get_recordings_lightweight(limit=500)
                else:
                    recordings = self.data_provider.get_all_recordings()

                self._recordings_cache = recordings
                self._recordings_cache_time = time.time()

                if self.parent and hasattr(self.parent, 'after'):
                    try:
                        self.parent.after(0, lambda: self._on_refresh_complete(recordings))
                    except RuntimeError:
                        pass
            except Exception as e:
                logger.error(f"Error loading recordings: {e}")
                if self.parent and hasattr(self.parent, 'after') and hasattr(self, 'recording_count_label'):
                    try:
                        error_msg = str(e)
                        self.parent.after(0, lambda msg=error_msg: self._on_refresh_error(msg))
                    except RuntimeError:
                        pass
            finally:
                self._refresh_in_progress = False

        threading.Thread(target=task, daemon=True).start()

    def _on_refresh_complete(self, recordings: List[Dict[str, Any]]) -> None:
        """Handle successful refresh completion on main thread."""
        self._populate_recordings_tree(recordings)

    def _on_refresh_error(self, error_msg: str) -> None:
        """Handle refresh error on main thread."""
        self._show_error_state(error_msg)

    def invalidate_recordings_cache(self) -> None:
        """Invalidate the recordings cache to force refresh on next access."""
        self._recordings_cache = None
        self._recordings_cache_time = 0.0

    # ========================================
    # Auto-refresh
    # ========================================

    def start_auto_refresh(self) -> None:
        """Start periodic auto-refresh of recordings list."""
        self.stop_auto_refresh()
        self._schedule_auto_refresh()
        logger.debug("Recordings auto-refresh started (60s interval)")

    def _schedule_auto_refresh(self) -> None:
        """Schedule the next auto-refresh."""
        try:
            if self.parent and hasattr(self.parent, 'after'):
                self._auto_refresh_job = self.parent.after(
                    self._auto_refresh_interval,
                    self._perform_auto_refresh
                )
        except Exception as e:
            logger.debug(f"Could not schedule auto-refresh: {e}")

    def _perform_auto_refresh(self) -> None:
        """Perform auto-refresh and schedule next one."""
        try:
            if self.parent and hasattr(self.parent, 'winfo_exists') and self.parent.winfo_exists():
                self._refresh_recordings_list(force_refresh=True)
                self._schedule_auto_refresh()
        except Exception as e:
            logger.debug(f"Auto-refresh skipped: {e}")

    def stop_auto_refresh(self) -> None:
        """Stop periodic auto-refresh."""
        if self._auto_refresh_job:
            try:
                if self.parent and hasattr(self.parent, 'after_cancel'):
                    self.parent.after_cancel(self._auto_refresh_job)
            except Exception:
                pass
            self._auto_refresh_job = None
            logger.debug("Recordings auto-refresh stopped")

    # ========================================
    # Filtering
    # ========================================

    def _filter_recordings(self) -> None:
        """Filter recordings based on search text."""
        search_text = self.recordings_search_var.get().lower()

        if not search_text:
            for item in self.recordings_tree.get_children():
                self.recordings_tree.reattach(item, '', 'end')
        else:
            for item in self.recordings_tree.get_children():
                values = self.recordings_tree.item(item, 'values')
                id_text = self.recordings_tree.item(item, 'text')
                searchable_values = list(values) + [id_text]
                if any(search_text in str(v).lower() for v in searchable_values):
                    self.recordings_tree.reattach(item, '', 'end')
                else:
                    self.recordings_tree.detach(item)

    # ========================================
    # Load Recording
    # ========================================

    def _load_selected_recording(self) -> None:
        """Load the selected recording into the main application."""
        selection = self.recordings_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select a recording to load.")
            return

        if len(selection) > 1:
            tk.messagebox.showinfo("Multiple Selection", "Multiple recordings selected. Loading the first one.")

        item = selection[0]
        rec_id = int(self.recordings_tree.item(item, 'text'))

        try:
            recording = self.data_provider.get_recording(rec_id)
            if not recording:
                tk.messagebox.showerror("Error", "Recording not found in database.")
                return

            from utils.cleanup_utils import clear_all_content
            clear_all_content(self.parent)

            if recording.get('transcript'):
                self.parent.transcript_text.insert("1.0", recording['transcript'])
                self.parent.notebook.select(0)

            if recording.get('soap_note'):
                self.parent.soap_text.insert("1.0", recording['soap_note'])
                if not recording.get('transcript'):
                    self.parent.notebook.select(1)
                    self.parent.soap_text.focus_set()

            if recording.get('referral'):
                self.parent.referral_text.insert("1.0", recording['referral'])

            if recording.get('letter'):
                self.parent.letter_text.insert("1.0", recording['letter'])

            if hasattr(self.parent, 'chat_text') and recording.get('chat'):
                self.parent.chat_text.insert("1.0", recording['chat'])

            self.parent.status_manager.success(f"Loaded recording #{rec_id}")
            self.parent.current_recording_id = rec_id
            self.parent.selected_recording_id = rec_id

            # Load saved analyses from database
            self._load_saved_analyses(rec_id)

        except Exception as e:
            logger.error(f"Error loading recording: {e}")
            tk.messagebox.showerror("Load Error", f"Failed to load recording: {str(e)}")

    def _load_saved_analyses(self, recording_id: int) -> None:
        """Load saved medication and differential analyses for a recording.

        Args:
            recording_id: The recording ID
        """
        try:
            from processing.analysis_storage import get_analysis_storage

            storage = get_analysis_storage()
            analyses = storage.get_analyses_for_recording(recording_id)

            has_medication = analyses.get('medication') is not None
            has_differential = analyses.get('differential') is not None
            has_compliance = analyses.get('compliance') is not None

            # Update analysis panels if UI components available
            if hasattr(self.parent, 'ui') and hasattr(self.parent.ui, 'notebook_tabs'):
                notebook_tabs = self.parent.ui.notebook_tabs

                # Clear existing analysis panels first
                if hasattr(notebook_tabs, 'clear_analysis_panels'):
                    notebook_tabs.clear_analysis_panels()

                # Load saved analyses into panels
                if has_medication or has_differential or has_compliance:
                    if hasattr(notebook_tabs, 'load_saved_analyses'):
                        notebook_tabs.load_saved_analyses(recording_id)

            # Update sidebar indicators
            self._update_soap_indicators(has_medication, has_differential, has_compliance)

        except Exception as e:
            logger.debug(f"Could not load saved analyses: {e}")

    def _update_soap_indicators(self, has_medication: bool, has_differential: bool, has_compliance: bool = False) -> None:
        """Update sidebar SOAP sub-item indicators.

        Args:
            has_medication: Whether medication analysis exists
            has_differential: Whether differential diagnosis exists
            has_compliance: Whether compliance analysis exists
        """
        try:
            if hasattr(self.parent, 'ui') and hasattr(self.parent.ui, 'sidebar_navigation'):
                sidebar_nav = self.parent.ui.sidebar_navigation
                if hasattr(sidebar_nav, 'update_soap_indicators'):
                    sidebar_nav.update_soap_indicators(
                        has_medication=has_medication,
                        has_differential=has_differential,
                        has_compliance=has_compliance
                    )
        except Exception as e:
            logger.debug(f"Could not update SOAP indicators: {e}")

    # ========================================
    # Export Recording
    # ========================================

    def _export_selected_recording(self) -> None:
        """Export the selected recording."""
        selection = self.recordings_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select a recording to export.")
            return

        item = selection[0]
        rec_id = int(self.recordings_tree.item(item, 'text'))

        try:
            recording = self.data_provider.get_recording(rec_id)
            if not recording:
                tk.messagebox.showerror("Error", "Recording not found in database.")
                return

            from tkinter import filedialog
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[
                    ("Text files", "*.txt"),
                    ("All files", "*.*")
                ],
                title="Export Recording"
            )

            if not file_path:
                return

            content = []
            content.append(f"Medical Recording Export - ID: {rec_id}")
            content.append(f"Date: {recording.get('timestamp', 'Unknown')}")
            content.append(f"Patient: {recording.get('patient_name', 'Unknown')}")
            content.append("=" * 50)

            if recording.get('transcript'):
                content.append("\nTRANSCRIPT:")
                content.append(recording['transcript'])

            if recording.get('soap_note'):
                content.append("\n\nSOAP NOTE:")
                content.append(recording['soap_note'])

            if recording.get('referral'):
                content.append("\n\nREFERRAL:")
                content.append(recording['referral'])

            if recording.get('letter'):
                content.append("\n\nLETTER:")
                content.append(recording['letter'])

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(content))

            self.parent.status_manager.success(f"Recording exported to {os.path.basename(file_path)}")

        except Exception as e:
            logger.error(f"Error exporting recording: {e}")
            tk.messagebox.showerror("Export Error", f"Failed to export recording: {str(e)}")


__all__ = ["RecordingsTabDataMixin"]
