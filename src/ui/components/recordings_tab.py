"""
Recordings Tab Component for Medical Assistant
Handles recordings management UI and operations
"""

import tkinter as tk
import tkinter.messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from typing import Dict, Callable, Optional, List, Protocol, runtime_checkable, Any
import logging
import threading
import os
from datetime import datetime
from ui.tooltip import ToolTip
from ui.scaling_utils import ui_scaler
from settings.settings import SETTINGS


@runtime_checkable
class RecordingsDataProvider(Protocol):
    """Protocol defining the interface for recordings data access.

    This protocol decouples the RecordingsTab UI from the database layer,
    allowing for easier testing and potential swapping of data sources.
    """

    def get_all_recordings(self) -> List[Dict[str, Any]]:
        """Get all recordings from the data source."""
        ...

    def get_recording(self, recording_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific recording by ID."""
        ...

    def delete_recording(self, recording_id: int) -> bool:
        """Delete a recording by ID."""
        ...

    def clear_all_recordings(self) -> bool:
        """Clear all recordings from the data source."""
        ...


class RecordingsTab:
    """Manages the Recordings workflow tab UI components."""

    def __init__(self, parent_ui, data_provider: Optional[RecordingsDataProvider] = None):
        """Initialize the RecordingsTab component.

        Args:
            parent_ui: Reference to the parent WorkflowUI instance
            data_provider: Optional data provider for recordings. If None,
                          falls back to parent.db for backwards compatibility.
        """
        self.parent_ui = parent_ui
        self.parent = parent_ui.parent
        self.components = parent_ui.components

        # Data provider - use injected provider or fall back to parent.db
        self._data_provider = data_provider

        # Recording tree components
        self.recordings_tree = None
        self.recordings_search_var = None
        self.recording_count_label = None
        self.recordings_context_menu = None

        # Batch processing state
        self.batch_progress_dialog = None
        self.batch_failed_count = 0

    @property
    def data_provider(self) -> RecordingsDataProvider:
        """Get the data provider, falling back to parent.db if not set.

        This property enables gradual migration from tight coupling to
        dependency injection without breaking existing code.
        """
        if self._data_provider is not None:
            return self._data_provider
        # Backwards compatibility: use parent.db
        return self.parent.db

    @data_provider.setter
    def data_provider(self, provider: RecordingsDataProvider) -> None:
        """Set the data provider."""
        self._data_provider = provider
        
    def create_recordings_tab(self, command_map: Dict[str, Callable]) -> ttk.Frame:
        """Create the Recordings workflow tab.
        
        Args:
            command_map: Dictionary mapping button names to their command functions
            
        Returns:
            ttk.Frame: The recordings tab frame
        """
        recordings_frame = ttk.Frame(self.parent)
        
        # Create the recordings panel that fills the entire tab
        recordings_panel = self._create_recordings_panel(recordings_frame)
        recordings_panel.pack(fill=BOTH, expand=True, padx=10, pady=10)
        self.components['recordings_panel'] = recordings_panel
        
        return recordings_frame
    
    def _create_recordings_panel(self, parent_frame: ttk.Frame) -> ttk.LabelFrame:
        """Create a panel showing recent recordings.
        
        Args:
            parent_frame: Parent frame to place the panel in
            
        Returns:
            ttk.LabelFrame: The recordings panel
        """
        # Create the labeled frame
        recordings_frame = ttk.LabelFrame(parent_frame, text="Recent Recordings", padding=5)
        
        # Create controls frame at the top
        controls_frame = ttk.Frame(recordings_frame)
        controls_frame.pack(fill=X, pady=(0, 5))
        
        # Search box
        search_frame = ttk.Frame(controls_frame)
        search_frame.pack(side=LEFT, fill=X, expand=True)
        
        ttk.Label(search_frame, text="Search:", font=("Segoe UI", 9)).pack(side=LEFT, padx=(0, 5))
        self.recordings_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.recordings_search_var, width=30)
        search_entry.pack(side=LEFT, fill=X, expand=True)
        search_entry.bind("<KeyRelease>", lambda e: self._filter_recordings())
        
        # Refresh button
        refresh_btn = ttk.Button(controls_frame, text="⟳", width=3, 
                                command=self._refresh_recordings_list)
        refresh_btn.pack(side=RIGHT, padx=(5, 0))
        ToolTip(refresh_btn, "Refresh recordings list")
        
        # Create treeview with scrollbar
        tree_container = ttk.Frame(recordings_frame)
        tree_container.pack(fill=BOTH, expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_container)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        # Create compact treeview
        columns = ("date", "time", "transcription", "soap", "referral", "letter")
        self.recordings_tree = ttk.Treeview(
            tree_container,
            columns=columns,
            show="tree headings",
            height=7,  # Show 7 rows for better visibility
            selectmode="extended",  # Allow multiple selection
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.recordings_tree.yview)
        self.recordings_tree.pack(side=LEFT, fill=BOTH, expand=True)
        
        # Configure columns
        self.recordings_tree.heading("#0", text="ID", anchor=tk.W)
        self.recordings_tree.heading("date", text="Date", anchor=tk.W)
        self.recordings_tree.heading("time", text="Time", anchor=tk.W)
        self.recordings_tree.heading("transcription", text="Transcription", anchor=tk.CENTER)
        self.recordings_tree.heading("soap", text="SOAP Note", anchor=tk.CENTER)
        self.recordings_tree.heading("referral", text="Referral", anchor=tk.CENTER)
        self.recordings_tree.heading("letter", text="Letter", anchor=tk.CENTER)
        
        # Set column widths with anchor for centering
        self.recordings_tree.column("#0", width=50, minwidth=40, stretch=False, anchor=tk.W)
        self.recordings_tree.column("date", width=100, minwidth=80, anchor=tk.W)
        self.recordings_tree.column("time", width=80, minwidth=60, anchor=tk.W)
        self.recordings_tree.column("transcription", width=90, minwidth=70, anchor=tk.CENTER)
        self.recordings_tree.column("soap", width=90, minwidth=70, anchor=tk.CENTER)
        self.recordings_tree.column("referral", width=80, minwidth=60, anchor=tk.CENTER)
        self.recordings_tree.column("letter", width=80, minwidth=60, anchor=tk.CENTER)
        
        # Configure tags for styling
        self.recordings_tree.tag_configure("complete", foreground="#27ae60")
        self.recordings_tree.tag_configure("processing", foreground="#f39c12")
        self.recordings_tree.tag_configure("partial", foreground="#3498db")
        self.recordings_tree.tag_configure("failed", foreground="#e74c3c")
        
        # Configure column-specific styling
        self.recordings_tree.tag_configure("has_content", foreground="#27ae60")  # Green for checkmarks
        self.recordings_tree.tag_configure("no_content", foreground="#888888")   # Gray for dashes
        self.recordings_tree.tag_configure("processing_content", foreground="#f39c12")  # Orange for processing
        self.recordings_tree.tag_configure("failed_content", foreground="#e74c3c")  # Red for failed
        
        # Action buttons - split into two rows for better layout
        actions_frame = ttk.Frame(recordings_frame)
        actions_frame.pack(fill=X, pady=(5, 0))
        
        # First row of buttons
        row1_frame = ttk.Frame(actions_frame)
        row1_frame.pack(fill=X)
        
        # Load button
        load_btn = ttk.Button(
            row1_frame,
            text="Load",
            command=self._load_selected_recording,
            bootstyle="primary-outline",
            width=ui_scaler.get_button_width(10)
        )
        load_btn.pack(side=LEFT, padx=(0, 5))
        ToolTip(load_btn, "Load selected recording")
        
        # Delete button
        delete_btn = ttk.Button(
            row1_frame,
            text="Delete",
            command=self._delete_selected_recording,
            bootstyle="danger-outline",
            width=ui_scaler.get_button_width(10)
        )
        delete_btn.pack(side=LEFT, padx=(0, 5))
        ToolTip(delete_btn, "Delete selected recording")
        
        # Export button
        export_btn = ttk.Button(
            row1_frame,
            text="Export",
            command=self._export_selected_recording,
            bootstyle="info-outline",
            width=ui_scaler.get_button_width(10)
        )
        export_btn.pack(side=LEFT, padx=(0, 5))
        ToolTip(export_btn, "Export selected recording")
        
        # Clear All button
        clear_all_btn = ttk.Button(
            row1_frame,
            text="Clear All",
            command=self._clear_all_recordings,
            bootstyle="danger-outline",
            width=ui_scaler.get_button_width(10)
        )
        clear_all_btn.pack(side=LEFT)
        ToolTip(clear_all_btn, "Clear all recordings from database")
        
        # Recording count label - place in second row
        row2_frame = ttk.Frame(actions_frame)
        row2_frame.pack(fill=X, pady=(5, 0))
        
        # Process Selected button (in second row)
        process_btn = ttk.Button(
            row2_frame,
            text="Process Selected",
            command=self._process_selected_recordings,
            bootstyle="success-outline",
            width=ui_scaler.get_button_width(15)
        )
        process_btn.pack(side=LEFT, padx=(0, 5))
        ToolTip(process_btn, "Process selected recordings in batch")
        self.components['batch_process_button'] = process_btn
        
        # Batch Process Files button
        batch_files_btn = ttk.Button(
            row2_frame,
            text="Batch Process Files",
            command=self._batch_process_files,
            bootstyle="primary-outline",
            width=ui_scaler.get_button_width(15)
        )
        batch_files_btn.pack(side=LEFT, padx=(0, 5))
        ToolTip(batch_files_btn, "Select audio files to process in batch")
        self.components['batch_files_button'] = batch_files_btn
        
        # Reprocess Failed button
        reprocess_btn = ttk.Button(
            row2_frame,
            text="Reprocess Failed",
            command=self._reprocess_failed_recordings,
            bootstyle="warning-outline",
            width=ui_scaler.get_button_width(15)
        )
        reprocess_btn.pack(side=LEFT, padx=(0, 10))
        ToolTip(reprocess_btn, "Reprocess selected failed recordings")
        self.components['reprocess_failed_button'] = reprocess_btn
        
        self.recording_count_label = ttk.Label(
            row2_frame,
            text="0 recordings",
            font=("Segoe UI", 9),
            foreground="gray"
        )
        self.recording_count_label.pack(side=LEFT)
        
        # Bind double-click to load
        self.recordings_tree.bind("<Double-Button-1>", lambda e: self._load_selected_recording())
        
        # Bind selection change to update count
        self.recordings_tree.bind("<<TreeviewSelect>>", self._on_selection_change)
        
        # Bind right-click for context menu
        self.recordings_tree.bind("<Button-3>", self._show_recordings_context_menu)
        
        # Create context menu
        self._create_recordings_context_menu()
        
        # Load initial recordings
        self._refresh_recordings_list()
        
        return recordings_frame
    
    def _refresh_recordings_list(self):
        """Refresh the recordings list from database."""
        def task():
            try:
                # Get recent recordings from database
                recordings = self.data_provider.get_all_recordings()
                # Update UI on main thread - check if parent still exists
                if self.parent and hasattr(self.parent, 'after'):
                    try:
                        self.parent.after(0, lambda: self._populate_recordings_tree(recordings))
                    except RuntimeError:
                        # Window might be closing
                        pass
            except Exception as e:
                logging.error(f"Error loading recordings: {e}")
                # Check if parent and label still exist before updating
                if self.parent and hasattr(self.parent, 'after') and hasattr(self, 'recording_count_label'):
                    try:
                        self.parent.after(0, lambda: self.recording_count_label.config(text="Error loading recordings"))
                    except RuntimeError:
                        # Window might be closing
                        pass
        
        # Run in background thread
        threading.Thread(target=task, daemon=True).start()
    
    def _populate_recordings_tree(self, recordings: list):
        """Populate the recordings tree with data."""
        # Clear existing items
        for item in self.recordings_tree.get_children():
            self.recordings_tree.delete(item)
        
        # Add recordings
        for recording in recordings:
            try:
                rec_id = recording['id']
                
                # Parse timestamp
                timestamp = recording.get('timestamp', '')
                if timestamp:
                    try:
                        dt_obj = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        date_str = dt_obj.strftime("%Y-%m-%d")
                        time_str = dt_obj.strftime("%H:%M")
                    except (ValueError, AttributeError):
                        date_str = timestamp.split()[0] if ' ' in timestamp else timestamp
                        time_str = timestamp.split()[1] if ' ' in timestamp else ""
                else:
                    date_str = "Unknown"
                    time_str = ""
                
                # Determine completion status for each type
                has_transcript = bool(recording.get('transcript'))
                has_soap = bool(recording.get('soap_note'))
                has_referral = bool(recording.get('referral'))
                has_letter = bool(recording.get('letter'))
                processing_status = recording.get('processing_status', '')
                
                # Status indicators with standard checkmarks
                if processing_status == 'processing':
                    transcript_status = "🔄" if not has_transcript else "✓"
                    soap_status = "🔄" if not has_soap else "✓"
                    referral_status = "🔄" if not has_referral else "✓"
                    letter_status = "🔄" if not has_letter else "✓"
                    tag = "processing"
                elif processing_status == 'failed':
                    transcript_status = "❌" if not has_transcript else "✓"
                    soap_status = "❌" if not has_soap else "✓"
                    referral_status = "❌" if not has_referral else "✓"
                    letter_status = "❌" if not has_letter else "✓"
                    tag = "failed"
                else:
                    transcript_status = "✓" if has_transcript else "—"
                    soap_status = "✓" if has_soap else "—"
                    referral_status = "✓" if has_referral else "—"
                    letter_status = "✓" if has_letter else "—"
                    
                    # Determine overall tag based on what content exists
                    content_count = sum([has_transcript, has_soap, has_referral, has_letter])
                    if content_count == 4:
                        tag = "complete"  # All green
                    elif content_count >= 2:
                        tag = "partial"   # Mixed green/gray
                    elif content_count == 1:
                        tag = "has_content"  # Some green
                    else:
                        tag = "no_content"   # All gray
                
                # Insert into tree with appropriate tag for coloring
                self.recordings_tree.insert(
                    "", "end",
                    text=str(rec_id),
                    values=(date_str, time_str, transcript_status, soap_status, referral_status, letter_status),
                    tags=(tag,)
                )
            except Exception as e:
                logging.error(f"Error adding recording to tree: {e}")
        
        # Update count
        count = len(self.recordings_tree.get_children())
        self.recording_count_label.config(text=f"{count} recording{'s' if count != 1 else ''}")
    
    def _filter_recordings(self):
        """Filter recordings based on search text."""
        search_text = self.recordings_search_var.get().lower()
        
        if not search_text:
            # Show all items
            for item in self.recordings_tree.get_children():
                self.recordings_tree.reattach(item, '', 'end')
        else:
            # Hide non-matching items
            for item in self.recordings_tree.get_children():
                values = self.recordings_tree.item(item, 'values')
                # Search in date, time, and completion status columns
                # Also search in the ID (text field)
                id_text = self.recordings_tree.item(item, 'text')
                searchable_values = list(values) + [id_text]
                if any(search_text in str(v).lower() for v in searchable_values):
                    self.recordings_tree.reattach(item, '', 'end')
                else:
                    self.recordings_tree.detach(item)
    
    def _load_selected_recording(self):
        """Load the selected recording into the main application."""
        selection = self.recordings_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select a recording to load.")
            return
        
        # For multiple selection, only load the first one
        if len(selection) > 1:
            tk.messagebox.showinfo("Multiple Selection", "Multiple recordings selected. Loading the first one.")
        
        # Get recording ID
        item = selection[0]
        rec_id = int(self.recordings_tree.item(item, 'text'))
        
        try:
            # Get full recording data
            recording = self.data_provider.get_recording(rec_id)
            if not recording:
                tk.messagebox.showerror("Error", "Recording not found in database.")
                return

            # Clear existing content
            from utils.cleanup_utils import clear_all_content
            clear_all_content(self.parent)
            
            # Load data into UI
            if recording.get('transcript'):
                self.parent.transcript_text.insert("1.0", recording['transcript'])
                self.parent.notebook.select(0)  # Switch to transcript tab
            
            if recording.get('soap_note'):
                self.parent.soap_text.insert("1.0", recording['soap_note'])
                if not recording.get('transcript'):
                    self.parent.notebook.select(1)  # Switch to SOAP tab
                    self.parent.soap_text.focus_set()  # Give focus to SOAP text widget
            
            if recording.get('referral'):
                self.parent.referral_text.insert("1.0", recording['referral'])
            
            if recording.get('letter'):
                self.parent.letter_text.insert("1.0", recording['letter'])
            
            # Load chat content if available
            if hasattr(self.parent, 'chat_text') and recording.get('chat'):
                self.parent.chat_text.insert("1.0", recording['chat'])
            
            # Update status
            self.parent.status_manager.success(f"Loaded recording #{rec_id}")
            
            # Update current recording ID
            self.parent.current_recording_id = rec_id
            
        except Exception as e:
            logging.error(f"Error loading recording: {e}")
            tk.messagebox.showerror("Load Error", f"Failed to load recording: {str(e)}")
    
    def _delete_selected_recording(self):
        """Delete the selected recording(s)."""
        selection = self.recordings_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select a recording to delete.")
            return
        
        # Handle multiple selection
        count = len(selection)
        if count == 1:
            message = "Are you sure you want to delete this recording?"
        else:
            message = f"Are you sure you want to delete {count} recordings?"
        
        # Confirm deletion
        if not tk.messagebox.askyesno("Confirm Delete", message):
            return
        
        deleted_count = 0
        errors = []
        
        # Delete each selected recording
        for item in selection:
            rec_id = int(self.recordings_tree.item(item, 'text'))
            
            try:
                # Delete from database
                self.data_provider.delete_recording(rec_id)
                
                # Remove from tree
                self.recordings_tree.delete(item)
                deleted_count += 1
                
            except Exception as e:
                logging.error(f"Error deleting recording {rec_id}: {e}")
                errors.append(f"Recording {rec_id}: {str(e)}")
        
        # Update count
        total_count = len(self.recordings_tree.get_children())
        self.recording_count_label.config(text=f"{total_count} recording{'s' if total_count != 1 else ''}")
        
        # Update status
        if deleted_count == count:
            self.parent.status_manager.success(f"{deleted_count} recording{'s' if deleted_count > 1 else ''} deleted")
        else:
            error_msg = f"Deleted {deleted_count} of {count} recordings. Errors:\n" + "\n".join(errors[:3])
            if len(errors) > 3:
                error_msg += f"\n... and {len(errors) - 3} more errors"
            tk.messagebox.showwarning("Partial Delete", error_msg)
    
    def _export_selected_recording(self):
        """Export the selected recording."""
        selection = self.recordings_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select a recording to export.")
            return
        
        # Get recording ID
        item = selection[0]
        rec_id = int(self.recordings_tree.item(item, 'text'))
        
        try:
            # Get full recording data
            recording = self.data_provider.get_recording(rec_id)
            if not recording:
                tk.messagebox.showerror("Error", "Recording not found in database.")
                return

            # Ask for export format
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
            
            # Create export content
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
            
            # Write to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(content))
            
            self.parent.status_manager.success(f"Recording exported to {os.path.basename(file_path)}")
            
        except Exception as e:
            logging.error(f"Error exporting recording: {e}")
            tk.messagebox.showerror("Export Error", f"Failed to export recording: {str(e)}")
    
    def _clear_all_recordings(self):
        """Clear all recordings from the database."""
        # Confirm deletion with a strong warning
        result = tkinter.messagebox.askyesno(
            "Clear All Recordings",
            "WARNING: This will permanently delete ALL recordings from the database.\n\n"
            "This action cannot be undone!\n\n"
            "Are you absolutely sure you want to continue?",
            icon="warning"
        )
        
        if not result:
            return
        
        # Double confirmation for safety
        result2 = tkinter.messagebox.askyesno(
            "Final Confirmation",
            "This is your last chance to cancel.\n\n"
            "Delete ALL recordings permanently?",
            icon="warning"
        )
        
        if not result2:
            return
        
        try:
            # Clear all recordings from database
            success = self.data_provider.clear_all_recordings()
            
            if success:
                # Clear the tree view
                for item in self.recordings_tree.get_children():
                    self.recordings_tree.delete(item)
                
                # Update count
                self.recording_count_label.config(text="0 recordings")
                
                # Clear any currently loaded content
                from utils.cleanup_utils import clear_all_content
                clear_all_content(self.parent)
                
                # Reset current recording ID
                self.parent.current_recording_id = None
                
                # Update status
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
    
    def _reprocess_failed_recordings(self):
        """Reprocess selected failed recordings."""
        selection = self.recordings_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select failed recordings to reprocess.")
            return
        
        # Get recording IDs and check if they're failed
        failed_recording_ids = []
        non_failed_count = 0
        
        for item in selection:
            rec_id = int(self.recordings_tree.item(item, 'text'))
            values = self.recordings_tree.item(item, 'values')
            
            # Check processing status (it's in the values)
            try:
                # Get the recording to check status
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
        
        # Confirm reprocessing
        count = len(failed_recording_ids)
        message = f"Reprocess {count} failed recording{'s' if count > 1 else ''}?"
        if non_failed_count > 0:
            message += f"\n\n({non_failed_count} non-failed recording{'s' if non_failed_count > 1 else ''} will be skipped)"
        
        if not tk.messagebox.askyesno("Confirm Reprocess", message):
            return
        
        # Reprocess the recordings
        try:
            if hasattr(self.parent, 'reprocess_failed_recordings'):
                self.parent.reprocess_failed_recordings(failed_recording_ids)
                self.parent.status_manager.success(f"Queued {count} recording{'s' if count > 1 else ''} for reprocessing")
                
                # Refresh the list after a short delay
                self.parent.after(1000, self._refresh_recordings_list)
            else:
                tk.messagebox.showerror("Error", "Reprocessing functionality not available")
                
        except Exception as e:
            logging.error(f"Error reprocessing recordings: {e}")
            tk.messagebox.showerror("Reprocess Error", f"Failed to reprocess recordings: {str(e)}")
    
    def _process_selected_recordings(self):
        """Process selected recordings in batch."""
        selection = self.recordings_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select recordings to process.")
            return
        
        # Get recording IDs
        recording_ids = []
        for item in selection:
            rec_id = int(self.recordings_tree.item(item, 'text'))
            recording_ids.append(rec_id)
        
        # Import dialog here to avoid circular imports
        from ui.dialogs.batch_processing_dialog import BatchProcessingDialog
        
        # Show batch processing dialog
        dialog = BatchProcessingDialog(self.parent, recording_ids)
        result = dialog.show()
        
        if result:
            # Start batch processing
            self._start_batch_processing(result)
    
    def _batch_process_files(self):
        """Open dialog to process audio files in batch."""
        # Import dialog here to avoid circular imports
        from ui.dialogs.batch_processing_dialog import BatchProcessingDialog
        
        # Show batch processing dialog with no pre-selected recordings
        dialog = BatchProcessingDialog(self.parent)
        result = dialog.show()
        
        if result:
            # Start batch processing
            self._start_batch_processing(result)
    
    def _start_batch_processing(self, options: dict):
        """Start batch processing of recordings or files."""
        # Import here to avoid circular imports
        from ui.dialogs.batch_progress_dialog import BatchProgressDialog
        
        # Determine count based on source
        if options['source'] == 'database':
            total_count = len(options['recording_ids'])
            item_type = "recordings"
        else:
            total_count = len(options['files'])
            item_type = "files"
        
        # Create progress dialog
        self.batch_progress_dialog = BatchProgressDialog(self.parent, "batch_" + str(id(options)), total_count)
        
        # Update status
        self.parent.status_manager.progress(f"Starting batch processing of {total_count} {item_type}...")
        
        # Disable process buttons during processing
        process_btn = self.components.get('batch_process_button')
        batch_files_btn = self.components.get('batch_files_button')
        if process_btn:
            process_btn.config(state=tk.DISABLED)
        if batch_files_btn:
            batch_files_btn.config(state=tk.DISABLED)
        
        # Track processing state
        self.batch_failed_count = 0
        
        # Create task for batch processing
        def task():
            try:
                if options['source'] == 'database':
                    # Use existing batch processing for database recordings
                    self.parent.document_generators.process_batch_recordings(
                        options['recording_ids'], 
                        options,
                        on_complete=lambda: self.parent.after(0, self._on_batch_complete),
                        on_progress=lambda msg, count, total: self.parent.after(0, 
                            lambda: self._update_batch_progress(msg, count, total))
                    )
                else:
                    # Process audio files
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
        
        # Set cancel callback
        def cancel_batch(batch_id):
            if hasattr(self.parent, 'processing_queue') and self.parent.processing_queue:
                self.parent.processing_queue.cancel_batch(batch_id)
        
        self.batch_progress_dialog.set_cancel_callback(cancel_batch)
        
        # Submit task
        threading.Thread(target=task, daemon=True).start()
    
    def _update_batch_progress(self, message: str, completed: int, total: int):
        """Update batch processing progress."""
        # Update status bar
        self.parent.status_manager.progress(f"{message} ({completed}/{total})")
        
        # Update progress dialog
        if hasattr(self, 'batch_progress_dialog') and self.batch_progress_dialog:
            # Estimate failed count based on message
            failed = self.batch_failed_count
            if "failed" in message.lower():
                self.batch_failed_count += 1
                failed = self.batch_failed_count
            
            self.batch_progress_dialog.update_progress(completed - failed, failed, message)
            
            # Add detailed message
            if completed > 0:
                self.batch_progress_dialog.add_detail(f"Recording {completed}/{total}: {message}", 
                                                    "error" if "failed" in message.lower() else "success")
    
    def _on_batch_complete(self):
        """Handle batch processing completion."""
        # Re-enable process buttons
        process_btn = self.components.get('batch_process_button')
        batch_files_btn = self.components.get('batch_files_button')
        if process_btn:
            process_btn.config(state=tk.NORMAL)
        if batch_files_btn:
            batch_files_btn.config(state=tk.NORMAL)
        
        # Refresh recordings list
        self._refresh_recordings_list()
        
        # Show completion message
        self.parent.status_manager.success("Batch processing completed!")
        
        # Close progress dialog if it exists
        if hasattr(self, 'batch_progress_dialog') and self.batch_progress_dialog:
            # Dialog will handle its own completion state
            pass
    
    def _on_selection_change(self, event):
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
    
    def _create_recordings_context_menu(self):
        """Create the context menu for recordings tree."""
        self.recordings_context_menu = tk.Menu(self.parent, tearoff=0)
        
        self.recordings_context_menu.add_command(
            label="Load",
            command=self._load_selected_recording,
            accelerator="Double-click"
        )
        
        self.recordings_context_menu.add_separator()
        
        self.recordings_context_menu.add_command(
            label="Reprocess (if failed)",
            command=self._reprocess_failed_recordings
        )
        
        self.recordings_context_menu.add_command(
            label="Export",
            command=self._export_selected_recording
        )
        
        self.recordings_context_menu.add_separator()
        
        self.recordings_context_menu.add_command(
            label="Delete",
            command=self._delete_selected_recording
        )
    
    def _show_recordings_context_menu(self, event):
        """Show context menu for recordings tree."""
        try:
            # Select the item under the cursor
            item = self.recordings_tree.identify_row(event.y)
            if item:
                # If item not already selected, select it
                if item not in self.recordings_tree.selection():
                    self.recordings_tree.selection_set(item)
                
                # Check if any selected recording is failed
                has_failed = False
                for selected in self.recordings_tree.selection():
                    rec_id = int(self.recordings_tree.item(selected, 'text'))
                    recording = self.data_provider.get_recording(rec_id)
                    if recording and recording.get('processing_status') == 'failed':
                        has_failed = True
                        break
                
                # Enable/disable reprocess option based on failed status
                if has_failed:
                    self.recordings_context_menu.entryconfig("Reprocess (if failed)", state=tk.NORMAL)
                else:
                    self.recordings_context_menu.entryconfig("Reprocess (if failed)", state=tk.DISABLED)
                
                # Show the menu
                self.recordings_context_menu.post(event.x_root, event.y_root)
        except Exception as e:
            logging.error(f"Error showing context menu: {e}")