"""
Recordings Tab UI Mixin

Provides widget creation and layout for the recordings tab.
Extracted from RecordingsTab for better separation of concerns.
"""

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, X, Y, LEFT, RIGHT
from typing import Optional, List, Dict, Any
from datetime import datetime
from utils.structured_logging import get_logger

from ui.tooltip import ToolTip

logger = get_logger(__name__)
from ui.scaling_utils import ui_scaler
from ui.hover_effects import ButtonHoverEffect, add_hover_to_treeview
from ui.loading_indicator import PulsingLabel
from ui.ui_constants import Colors, Fonts


class RecordingsTabUIMixin:
    """Mixin providing UI creation methods for RecordingsTab.

    This mixin expects the following attributes on the class:
    - parent_ui: Reference to parent WorkflowUI
    - parent: Reference to main application
    - components: Dictionary of UI components
    - recordings_tree: Treeview widget
    - recordings_search_var: StringVar for search
    - recording_count_label: PulsingLabel for count display
    - recordings_context_menu: Context menu
    """

    def create_recordings_tab(self, command_map: dict) -> ttk.Frame:
        """Create the Recordings workflow tab (legacy wrapper).

        Args:
            command_map: Dictionary mapping button names to their command functions

        Returns:
            ttk.Frame: The recordings tab frame
        """
        return self.create_recordings_panel(self.parent)

    def create_recordings_panel(self, parent) -> ttk.Frame:
        """Create the recordings panel for the shared panel area.

        Args:
            parent: Parent widget for the panel

        Returns:
            ttk.Frame: The recordings panel frame
        """
        recordings_frame = ttk.Frame(parent)

        recordings_panel = self._create_recordings_panel(recordings_frame)
        recordings_panel.pack(fill=BOTH, expand=True, padx=10, pady=10)
        self.components['recordings_panel'] = recordings_panel

        return recordings_frame

    def _create_recordings_panel(self, parent_frame: ttk.Frame) -> ttk.Labelframe:
        """Create a panel showing recent recordings.

        Args:
            parent_frame: Parent frame to place the panel in

        Returns:
            ttk.Labelframe: The recordings panel
        """
        recordings_frame = ttk.Labelframe(parent_frame, text="Recent Recordings", padding=5)

        # Create controls frame at the top
        controls_frame = ttk.Frame(recordings_frame)
        controls_frame.pack(fill=X, pady=(0, 5))

        # Search box
        search_frame = ttk.Frame(controls_frame)
        search_frame.pack(side=LEFT, fill=X, expand=True)

        ttk.Label(search_frame, text="Search:", font=Fonts.get_font(Fonts.SIZE_SM)).pack(side=LEFT, padx=(0, 5))
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

        scrollbar = ttk.Scrollbar(tree_container)
        scrollbar.pack(side=RIGHT, fill=Y)

        # Create compact treeview
        columns = ("date", "time", "transcription", "soap", "referral", "letter")
        self.recordings_tree = ttk.Treeview(
            tree_container,
            columns=columns,
            show="tree headings",
            height=7,
            selectmode="extended",
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.recordings_tree.yview)
        self.recordings_tree.pack(side=LEFT, fill=BOTH, expand=True)

        # Configure columns
        self._configure_tree_columns()

        # Configure tags for styling
        self._configure_tree_tags()

        # Add hover effects to treeview rows
        add_hover_to_treeview(self.recordings_tree)

        # Create action buttons
        self._create_action_buttons(recordings_frame)

        # Bind events
        self._bind_tree_events()

        # Create context menu
        self._create_recordings_context_menu()

        # Load initial recordings
        self._refresh_recordings_list()

        return recordings_frame

    def _configure_tree_columns(self) -> None:
        """Configure the treeview columns."""
        self.recordings_tree.heading("#0", text="ID", anchor=tk.W)
        self.recordings_tree.heading("date", text="Date", anchor=tk.W)
        self.recordings_tree.heading("time", text="Time", anchor=tk.W)
        self.recordings_tree.heading("transcription", text="Transcription", anchor=tk.CENTER)
        self.recordings_tree.heading("soap", text="SOAP Note", anchor=tk.CENTER)
        self.recordings_tree.heading("referral", text="Referral", anchor=tk.CENTER)
        self.recordings_tree.heading("letter", text="Letter", anchor=tk.CENTER)

        self.recordings_tree.column("#0", width=50, minwidth=40, stretch=False, anchor=tk.W)
        self.recordings_tree.column("date", width=100, minwidth=80, anchor=tk.W)
        self.recordings_tree.column("time", width=80, minwidth=60, anchor=tk.W)
        self.recordings_tree.column("transcription", width=90, minwidth=70, anchor=tk.CENTER)
        self.recordings_tree.column("soap", width=90, minwidth=70, anchor=tk.CENTER)
        self.recordings_tree.column("referral", width=80, minwidth=60, anchor=tk.CENTER)
        self.recordings_tree.column("letter", width=80, minwidth=60, anchor=tk.CENTER)

    def _configure_tree_tags(self) -> None:
        """Configure treeview tags for styling."""
        self.recordings_tree.tag_configure("complete", foreground=Colors.CONTENT_COMPLETE)
        self.recordings_tree.tag_configure("processing", foreground=Colors.CONTENT_PROCESSING)
        self.recordings_tree.tag_configure("partial", foreground=Colors.CONTENT_PARTIAL)
        self.recordings_tree.tag_configure("failed", foreground=Colors.CONTENT_FAILED)
        self.recordings_tree.tag_configure("has_content", foreground=Colors.CONTENT_COMPLETE)
        self.recordings_tree.tag_configure("no_content", foreground=Colors.CONTENT_NONE)
        self.recordings_tree.tag_configure("processing_content", foreground=Colors.CONTENT_PROCESSING)
        self.recordings_tree.tag_configure("failed_content", foreground=Colors.CONTENT_FAILED)

    def _create_action_buttons(self, parent_frame: ttk.Frame) -> None:
        """Create the action buttons for the recordings panel.

        Args:
            parent_frame: Parent frame for buttons
        """
        actions_frame = ttk.Frame(parent_frame)
        actions_frame.pack(fill=X, pady=(5, 0))

        # First row of buttons
        row1_frame = ttk.Frame(actions_frame)
        row1_frame.pack(fill=X)

        BTN_WIDTH_SM = ui_scaler.get_button_width(10)

        # Load button
        load_btn = ttk.Button(
            row1_frame,
            text="Load",
            command=self._load_selected_recording,
            bootstyle="primary-outline",
            width=BTN_WIDTH_SM
        )
        load_btn.pack(side=LEFT, padx=(0, 5))
        ToolTip(load_btn, "Load selected recording")
        ButtonHoverEffect(load_btn, hover_bootstyle="primary")

        # Delete button
        delete_btn = ttk.Button(
            row1_frame,
            text="Delete",
            command=self._delete_selected_recording,
            bootstyle="danger-outline",
            width=BTN_WIDTH_SM
        )
        delete_btn.pack(side=LEFT, padx=(0, 5))
        ToolTip(delete_btn, "Delete selected recording")
        ButtonHoverEffect(delete_btn, hover_bootstyle="danger")

        # Export button
        export_btn = ttk.Button(
            row1_frame,
            text="Export",
            command=self._export_selected_recording,
            bootstyle="info-outline",
            width=BTN_WIDTH_SM
        )
        export_btn.pack(side=LEFT, padx=(0, 5))
        ToolTip(export_btn, "Export selected recording")
        ButtonHoverEffect(export_btn, hover_bootstyle="info")

        # Clear All button
        clear_all_btn = ttk.Button(
            row1_frame,
            text="Clear All",
            command=self._clear_all_recordings,
            bootstyle="danger-outline",
            width=BTN_WIDTH_SM
        )
        clear_all_btn.pack(side=LEFT)
        ToolTip(clear_all_btn, "Clear all recordings from database")
        ButtonHoverEffect(clear_all_btn, hover_bootstyle="danger")

        # Second row
        row2_frame = ttk.Frame(actions_frame)
        row2_frame.pack(fill=X, pady=(5, 0))

        BTN_WIDTH_LG = ui_scaler.get_button_width(15)

        # Process Selected button
        process_btn = ttk.Button(
            row2_frame,
            text="Process Selected",
            command=self._process_selected_recordings,
            bootstyle="success-outline",
            width=BTN_WIDTH_LG
        )
        process_btn.pack(side=LEFT, padx=(0, 5))
        ToolTip(process_btn, "Process selected recordings in batch")
        ButtonHoverEffect(process_btn, hover_bootstyle="success")
        self.components['batch_process_button'] = process_btn

        # Batch Process Files button
        batch_files_btn = ttk.Button(
            row2_frame,
            text="Batch Process Files",
            command=self._batch_process_files,
            bootstyle="primary-outline",
            width=BTN_WIDTH_LG
        )
        batch_files_btn.pack(side=LEFT, padx=(0, 5))
        ToolTip(batch_files_btn, "Select audio files to process in batch")
        ButtonHoverEffect(batch_files_btn, hover_bootstyle="primary")
        self.components['batch_files_button'] = batch_files_btn

        # Reprocess Failed button
        reprocess_btn = ttk.Button(
            row2_frame,
            text="Reprocess Failed",
            command=self._reprocess_failed_recordings,
            bootstyle="warning-outline",
            width=BTN_WIDTH_LG
        )
        reprocess_btn.pack(side=LEFT, padx=(0, 10))
        ToolTip(reprocess_btn, "Reprocess selected failed recordings")
        ButtonHoverEffect(reprocess_btn, hover_bootstyle="warning")
        self.components['reprocess_failed_button'] = reprocess_btn

        # Recording count label
        self.recording_count_label = PulsingLabel(
            row2_frame,
            text="0 recordings",
            font=Fonts.get_font(Fonts.SIZE_SM),
            foreground=Colors.STATUS_IDLE,
            pulse_color=Colors.STATUS_INFO,
            normal_color=Colors.CONTENT_NONE
        )
        self.recording_count_label.pack(side=LEFT)

    def _bind_tree_events(self) -> None:
        """Bind event handlers to the treeview."""
        self.recordings_tree.bind("<Double-Button-1>", lambda e: self._load_selected_recording())
        self.recordings_tree.bind("<<TreeviewSelect>>", self._on_selection_change)
        self.recordings_tree.bind("<Button-3>", self._show_recordings_context_menu)

    def _create_recordings_context_menu(self) -> None:
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

    def _show_recordings_context_menu(self, event) -> None:
        """Show context menu for recordings tree."""
        try:
            item = self.recordings_tree.identify_row(event.y)
            if item:
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

                if has_failed:
                    self.recordings_context_menu.entryconfig("Reprocess (if failed)", state=tk.NORMAL)
                else:
                    self.recordings_context_menu.entryconfig("Reprocess (if failed)", state=tk.DISABLED)

                self.recordings_context_menu.post(event.x_root, event.y_root)
        except Exception as e:
            logger.error(f"Error showing context menu: {e}")

    # ========================================
    # Display State Methods
    # ========================================

    def _show_loading_state(self) -> None:
        """Show loading state in the recordings tree."""
        for item in self.recordings_tree.get_children():
            self.recordings_tree.delete(item)

        if self.recording_count_label:
            self.recording_count_label.config(text="Loading recordings...", foreground=Colors.STATUS_INFO)
            if hasattr(self.recording_count_label, 'start_pulse'):
                self.recording_count_label.start_pulse()

    def _show_error_state(self, error_msg: str) -> None:
        """Show error state when loading fails."""
        if self.recording_count_label and hasattr(self.recording_count_label, 'stop_pulse'):
            self.recording_count_label.stop_pulse()

        for item in self.recordings_tree.get_children():
            self.recordings_tree.delete(item)

        if self.recording_count_label:
            self.recording_count_label.config(text="Error loading recordings", foreground=Colors.STATUS_ERROR)

    def _show_empty_state(self) -> None:
        """Show empty state with helpful message when no recordings exist."""
        if self.recording_count_label and hasattr(self.recording_count_label, 'stop_pulse'):
            self.recording_count_label.stop_pulse()

        if self.recording_count_label:
            self.recording_count_label.config(
                text="No recordings yet - Start recording in the Record tab!",
                foreground=Colors.CONTENT_NONE
            )

    def _populate_recordings_tree(self, recordings: List[Dict[str, Any]]) -> None:
        """Populate the recordings tree with data.

        Args:
            recordings: List of recording dictionaries
        """
        if self.recording_count_label and hasattr(self.recording_count_label, 'stop_pulse'):
            self.recording_count_label.stop_pulse()

        for item in self.recordings_tree.get_children():
            self.recordings_tree.delete(item)

        if not recordings:
            self._show_empty_state()
            return

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

                # Determine completion status
                has_transcript = bool(recording.get('transcript'))
                has_soap = bool(recording.get('soap_note'))
                has_referral = bool(recording.get('referral'))
                has_letter = bool(recording.get('letter'))
                processing_status = recording.get('processing_status', '')

                # Status indicators
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

                    content_count = sum([has_transcript, has_soap, has_referral, has_letter])
                    if content_count == 4:
                        tag = "complete"
                    elif content_count >= 2:
                        tag = "partial"
                    elif content_count == 1:
                        tag = "has_content"
                    else:
                        tag = "no_content"

                self.recordings_tree.insert(
                    "", "end",
                    text=str(rec_id),
                    values=(date_str, time_str, transcript_status, soap_status, referral_status, letter_status),
                    tags=(tag,)
                )
            except Exception as e:
                logger.error(f"Error adding recording to tree: {e}")

        count = len(self.recordings_tree.get_children())
        self.recording_count_label.config(
            text=f"{count} recording{'s' if count != 1 else ''}",
            foreground=Colors.STATUS_IDLE
        )


__all__ = ["RecordingsTabUIMixin"]
