"""
Recordings Dialog Manager Module

Handles the recordings database dialog, including listing, searching,
loading, deleting, and exporting recordings.
"""

import os
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
import tkinter as tk
from tkinter import messagebox, filedialog
import ttkbootstrap as ttk

from database.database import Database
from ui.dialogs.dialogs import create_toplevel_dialog
from settings.settings_manager import settings_manager
from ui.status_manager import StatusManager
from utils.structured_logging import get_logger
from utils.error_handling import ErrorContext

logger = get_logger(__name__)


class RecordingsDialogManager:
    """Manages the recordings database dialog."""
    
    def __init__(self, parent_app):
        """Initialize the recordings dialog manager.
        
        Args:
            parent_app: The main application instance
        """
        self.app = parent_app
        self.db = parent_app.db
        self.status_manager = parent_app.status_manager
        
    def show_dialog(self) -> None:
        """Show the recordings database dialog."""
        dialog = create_toplevel_dialog(self.app, "Recordings Database", "1000x600")
        
        # Create UI components
        controls_frame = self._create_controls_frame(dialog)
        tree_frame, tree = self._create_tree_view(dialog)
        button_frame = self._create_button_frame(dialog, tree)
        
        # Store references for event handlers
        self.dialog = dialog
        self.tree = tree
        self.search_var = controls_frame.search_var
        
        # Load initial data
        self._load_recordings()
        
        # Bind events
        self._bind_events(controls_frame, tree)
        
    def _create_controls_frame(self, dialog: tk.Toplevel) -> ttk.Frame:
        """Create the top controls frame with search and refresh."""
        controls_frame = ttk.Frame(dialog)
        controls_frame.pack(fill="x", padx=10, pady=5)
        
        # Add search entry
        ttk.Label(controls_frame, text="Search:").pack(side="left", padx=(0, 5))
        search_var = tk.StringVar()
        search_entry = ttk.Entry(controls_frame, textvariable=search_var, width=30)
        search_entry.pack(side="left", padx=(0, 10))
        
        # Add refresh button
        refresh_button = ttk.Button(
            controls_frame, 
            text="Refresh", 
            bootstyle="outline",
            command=self._load_recordings
        )
        refresh_button.pack(side="right", padx=5)
        
        # Store search_var as attribute for access
        controls_frame.search_var = search_var
        
        return controls_frame
    
    def _create_tree_view(self, dialog: tk.Toplevel) -> tuple:
        """Create the treeview for displaying recordings."""
        # Create frame
        tree_frame = ttk.Frame(dialog)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Create scrollbars
        y_scrollbar = ttk.Scrollbar(tree_frame)
        y_scrollbar.pack(side="right", fill="y")
        
        x_scrollbar = ttk.Scrollbar(tree_frame, orient="horizontal")
        x_scrollbar.pack(side="bottom", fill="x")
        
        # Create treeview
        columns = ("id", "filename", "timestamp", "has_transcript", "has_soap", "has_referral", "has_letter")
        tree = ttk.Treeview(
            tree_frame, 
            columns=columns, 
            show="headings",
            yscrollcommand=y_scrollbar.set, 
            xscrollcommand=x_scrollbar.set
        )
        
        # Configure scrollbars
        y_scrollbar.config(command=tree.yview)
        x_scrollbar.config(command=tree.xview)
        
        # Define columns
        self._setup_tree_columns(tree)
        
        # Configure tag colors
        tree.tag_configure("complete", foreground="green")
        tree.tag_configure("partial", foreground="orange")
        tree.tag_configure("empty", foreground="gray")
        
        tree.pack(fill="both", expand=True)
        
        return tree_frame, tree
    
    def _setup_tree_columns(self, tree: ttk.Treeview):
        """Set up treeview columns."""
        # Define column headings
        tree.heading("id", text="ID", anchor="center")
        tree.heading("filename", text="Filename", anchor="center")
        tree.heading("timestamp", text="Date/Time", anchor="center")
        tree.heading("has_transcript", text="Transcript", anchor="center")
        tree.heading("has_soap", text="SOAP Note", anchor="center")
        tree.heading("has_referral", text="Referral", anchor="center")
        tree.heading("has_letter", text="Letter", anchor="center")
        
        # Set column widths
        tree.column("id", width=60, minwidth=60, anchor="center")
        tree.column("filename", width=300, minwidth=200, anchor="center")
        tree.column("timestamp", width=180, minwidth=150, anchor="center")
        tree.column("has_transcript", width=100, minwidth=80, anchor="center")
        tree.column("has_soap", width=100, minwidth=80, anchor="center")
        tree.column("has_referral", width=100, minwidth=80, anchor="center")
        tree.column("has_letter", width=100, minwidth=80, anchor="center")
    
    def _create_button_frame(self, dialog: tk.Toplevel, tree: ttk.Treeview) -> ttk.Frame:
        """Create the bottom button frame."""
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        # Load button
        load_button = ttk.Button(
            button_frame,
            text="Load Selected",
            command=lambda: self._load_selected_recording(tree),
            bootstyle="primary"
        )
        load_button.pack(side="left", padx=5)
        
        # Delete button
        delete_button = ttk.Button(
            button_frame,
            text="Delete Selected",
            command=lambda: self._delete_selected_recordings(tree),
            bootstyle="danger"
        )
        delete_button.pack(side="left", padx=5)
        
        # Export button
        export_button = ttk.Button(
            button_frame,
            text="Export Selected",
            command=lambda: self._export_selected_recordings(tree),
            bootstyle="success"
        )
        export_button.pack(side="left", padx=5)
        
        # Status label
        status_label = ttk.Label(button_frame, text="", foreground="gray")
        status_label.pack(side="left", padx=20)
        button_frame.status_label = status_label
        
        # Close button
        close_button = ttk.Button(
            button_frame,
            text="Close",
            command=dialog.destroy,
            bootstyle="secondary"
        )
        close_button.pack(side="right", padx=5)
        
        return button_frame
    
    def _bind_events(self, controls_frame: ttk.Frame, tree: ttk.Treeview):
        """Bind event handlers."""
        # Search functionality
        search_var = controls_frame.search_var
        search_var.trace("w", lambda *args: self._filter_recordings(search_var.get()))
        
        # Double-click to load
        tree.bind("<Double-Button-1>", lambda event: self._load_selected_recording(tree))
        
        # Keyboard shortcuts
        self.dialog.bind("<Escape>", lambda event: self.dialog.destroy())
        self.dialog.bind("<Delete>", lambda event: self._delete_selected_recordings(tree))
        self.dialog.bind("<Return>", lambda event: self._load_selected_recording(tree))
    
    def _load_recordings(self):
        """Load recordings from database."""
        def task():
            try:
                # Use lightweight query - fetches only essential columns + has_* flags
                # This avoids loading large text fields (transcript, soap_note, etc.)
                # saving 50-100x data transfer compared to get_all_recordings()
                if hasattr(self.db, 'get_recordings_lightweight'):
                    recordings = self.db.get_recordings_lightweight(limit=500)
                else:
                    recordings = self.db.get_all_recordings()

                # Update UI on main thread
                self.app.after(0, lambda: self._update_tree_view(recordings))

            except Exception as e:
                ctx = ErrorContext.capture(
                    operation="Loading recordings from database",
                    exception=e,
                    input_summary="recordings list query"
                )
                logger.error(ctx.to_log_string())
                self.app.after(0, lambda: messagebox.showerror("Database Error", ctx.user_message))

        # Run in background
        threading.Thread(target=task, daemon=True).start()
    
    def _update_tree_view(self, recordings: List[Dict[str, Any]]):
        """Update treeview with recordings data."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Add recordings
        for recording in recordings:
            try:
                # Extract data
                rec_id = recording['id']
                filename = recording['filename'] or "N/A"
                created_at = recording['timestamp'] or "N/A"

                # Use has_* flags from lightweight query (avoids loading full text)
                # Falls back to checking full text if flags not present (legacy support)
                has_transcript_flag = recording.get('has_transcript')
                has_soap_flag = recording.get('has_soap')
                has_referral_flag = recording.get('has_referral')
                has_letter_flag = recording.get('has_letter')

                # If flags not present, fall back to checking full text
                if has_transcript_flag is None:
                    has_transcript_flag = bool(recording.get('transcript', ''))
                if has_soap_flag is None:
                    has_soap_flag = bool(recording.get('soap_note', ''))
                if has_referral_flag is None:
                    has_referral_flag = bool(recording.get('referral', ''))
                if has_letter_flag is None:
                    has_letter_flag = bool(recording.get('letter', ''))

                # Determine status marks
                has_transcript = "✓" if has_transcript_flag else "✗"
                has_soap = "✓" if has_soap_flag else "✗"
                has_referral_mark = "✓" if has_referral_flag else "✗"
                has_letter_mark = "✓" if has_letter_flag else "✗"

                # Determine tag
                if has_transcript_flag and has_soap_flag:
                    tag = "complete"
                elif has_transcript_flag or has_soap_flag:
                    tag = "partial"
                else:
                    tag = "empty"
                
                # Insert into tree
                self.tree.insert(
                    "", "end",
                    values=(rec_id, filename, created_at, has_transcript, 
                           has_soap, has_referral_mark, has_letter_mark),
                    tags=(tag,)
                )
                
            except Exception as e:
                ctx = ErrorContext.capture(
                    operation="Adding recording to tree view",
                    exception=e,
                    input_summary=f"recording_id={recording.get('id', 'unknown')}"
                )
                logger.error(ctx.to_log_string())
        
        # Update status
        count = len(self.tree.get_children())
        if hasattr(self, 'dialog'):
            for widget in self.dialog.winfo_children():
                if isinstance(widget, ttk.Frame) and hasattr(widget, 'status_label'):
                    widget.status_label.config(text=f"{count} recordings")
    
    def _filter_recordings(self, search_text: str):
        """Filter recordings based on search text."""
        search_text = search_text.lower()
        
        # Show all items if search is empty
        if not search_text:
            for item in self.tree.get_children():
                self.tree.item(item, tags=self.tree.item(item, "tags"))
            return
        
        # Filter items
        for item in self.tree.get_children():
            values = self.tree.item(item, "values")
            # Search in filename and timestamp
            if any(search_text in str(v).lower() for v in values[1:3]):
                # Keep visible
                current_tags = list(self.tree.item(item, "tags"))
                if "hidden" in current_tags:
                    current_tags.remove("hidden")
                self.tree.item(item, tags=current_tags)
            else:
                # Hide item
                current_tags = list(self.tree.item(item, "tags"))
                if "hidden" not in current_tags:
                    current_tags.append("hidden")
                self.tree.item(item, tags=current_tags)
        
        # Configure hidden tag
        self.tree.tag_configure("hidden", foreground="lightgray")
    
    def _load_selected_recording(self, tree: ttk.Treeview):
        """Load the selected recording into the main application."""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a recording to load.")
            return
        
        # Get recording ID
        item = selection[0]
        values = tree.item(item, "values")
        recording_id = values[0]
        
        try:
            # Get full recording data
            recording = self.db.get_recording(recording_id)
            if not recording:
                messagebox.showerror("Error", "Recording not found in database.")
                return
            
            # Load into application
            self._load_recording_data(recording)
            
            # Close dialog
            self.dialog.destroy()
            
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Loading selected recording",
                exception=e,
                input_summary=f"recording_id={recording_id}"
            )
            logger.error(ctx.to_log_string())
            messagebox.showerror("Load Error", ctx.user_message)
    
    def _load_recording_data(self, recording: Dict[str, Any]):
        """Load recording data into the application."""
        # Extract data
        rec_id = recording['id']
        filename = recording['filename']
        created_at = recording['timestamp']
        transcript = recording.get('transcript', '')
        soap_note = recording.get('soap_note', '')
        
        # Clear existing content
        from utils.cleanup_utils import clear_all_content
        clear_all_content(self.app)
        
        # Load transcript
        if transcript:
            self.app.transcript_text.insert("1.0", transcript)
            self.app.notebook.select(0)  # Switch to transcript tab
        
        # Load SOAP note
        if soap_note:
            self.app.soap_text.insert("1.0", soap_note)
            if not transcript:
                self.app.notebook.select(1)  # Switch to SOAP tab if no transcript
                self.app.soap_text.focus_set()  # Give focus to SOAP text widget
        
        # Update status
        self.status_manager.success(f"Loaded recording from {created_at}")
        
        # Update current recording ID
        self.app.current_recording_id = rec_id
    
    def _delete_selected_recordings(self, tree: ttk.Treeview):
        """Delete selected recordings from database."""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select recordings to delete.")
            return
        
        # Confirm deletion
        count = len(selection)
        message = f"Are you sure you want to delete {count} recording(s)?"
        if not messagebox.askyesno("Confirm Delete", message):
            return
        
        # Delete recordings
        deleted = 0
        for item in selection:
            values = tree.item(item, "values")
            recording_id = values[0]
            
            try:
                self.db.delete_recording(recording_id)
                tree.delete(item)
                deleted += 1
            except Exception as e:
                ctx = ErrorContext.capture(
                    operation="Deleting recording",
                    exception=e,
                    input_summary=f"recording_id={recording_id}"
                )
                logger.error(ctx.to_log_string())
        
        # Update status
        if deleted > 0:
            self.status_manager.success(f"Deleted {deleted} recording(s)")
            # Update count
            for widget in self.dialog.winfo_children():
                if isinstance(widget, ttk.Frame) and hasattr(widget, 'status_label'):
                    count = len(tree.get_children())
                    widget.status_label.config(text=f"{count} recordings")
    
    def _export_selected_recordings(self, tree: ttk.Treeview):
        """Export selected recordings to files."""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select recordings to export.")
            return
        
        # Ask for export directory
        export_dir = filedialog.askdirectory(
            title="Select Export Directory",
            initialdir=settings_manager.get("default_folder", "")
        )
        
        if not export_dir:
            return
        
        # Export recordings
        def export_task():
            exported = 0
            errors = 0
            
            for item in selection:
                values = tree.item(item, "values")
                recording_id = values[0]
                
                try:
                    # Get full recording data
                    recording = self.db.get_recording(recording_id)
                    if recording:
                        # Export to file
                        self._export_recording_to_file(recording, export_dir)
                        exported += 1
                except Exception as e:
                    ctx = ErrorContext.capture(
                        operation="Exporting recording",
                        exception=e,
                        input_summary=f"recording_id={recording_id}"
                    )
                    logger.error(ctx.to_log_string())
                    errors += 1
            
            # Update status on main thread
            message = f"Exported {exported} recording(s)"
            if errors > 0:
                message += f" ({errors} errors)"
            
            self.app.after(0, lambda: self.status_manager.success(message))
        
        # Run in background
        threading.Thread(target=export_task, daemon=True).start()
    
    def _export_recording_to_file(self, recording: Dict[str, Any], export_dir: str):
        """Export a single recording to file."""
        rec_id = recording['id']
        filename = recording['filename']
        created_at = recording['timestamp']
        transcript = recording.get('transcript', '')
        soap_note = recording.get('soap_note', '')
        
        # Create filename
        timestamp = created_at.replace(":", "-").replace(" ", "_")
        base_filename = f"recording_{rec_id}_{timestamp}"
        
        # Export transcript
        if transcript:
            transcript_path = os.path.join(export_dir, f"{base_filename}_transcript.txt")
            with open(transcript_path, 'w', encoding='utf-8') as f:
                f.write(transcript)
        
        # Export SOAP note
        if soap_note:
            soap_path = os.path.join(export_dir, f"{base_filename}_soap.txt")
            with open(soap_path, 'w', encoding='utf-8') as f:
                f.write(soap_note)