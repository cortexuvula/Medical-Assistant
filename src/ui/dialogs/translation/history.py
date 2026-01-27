"""
Translation History Module

Provides conversation history panel, session management, and export functionality.
"""

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, X, Y, VERTICAL, LEFT, RIGHT, NW, W, HORIZONTAL, NORMAL, DISABLED
import threading
import json
from typing import TYPE_CHECKING, Optional, Callable, List, Dict

from ui.tooltip import ToolTip
from models.translation_session import TranslationEntry, Speaker
from utils.structured_logging import get_logger
from utils.error_handling import ErrorContext

if TYPE_CHECKING:
    from managers.translation_session_manager import TranslationSessionManager
    from managers.tts_manager import TTSManager


class HistoryMixin:
    """Mixin for conversation history management."""

    dialog: Optional[tk.Toplevel]
    session_manager: "TranslationSessionManager"
    tts_manager: "TTSManager"
    patient_language: str
    doctor_language: str
    logger: "get_logger"  # Uses structured logger
    _undo_stack: List[Dict]

    # UI components
    history_canvas: tk.Canvas
    history_window: int
    history_entries_frame: ttk.Frame
    session_stats_label: ttk.Label
    undo_button: ttk.Button
    patient_original_text: tk.Text
    patient_translated_text: tk.Text
    play_button: ttk.Button
    stop_button: ttk.Button
    recording_status: ttk.Label
    selected_output: tk.StringVar

    # Methods from other mixins
    def _dialog_exists(self) -> bool: ...
    def _safe_after(self, delay: int, callback: Callable, *args): ...
    def _safe_ui_update(self, callback: Callable): ...
    def _clear_all(self): ...
    def _on_playback_complete(self): ...
    def _on_playback_error(self, error: str): ...

    def _create_history_panel(self, parent):
        """Create the conversation history panel.

        Args:
            parent: Parent widget for the history panel
        """
        # History frame with labelframe styling
        history_frame = ttk.Labelframe(parent, text="Conversation History", padding=10)
        history_frame.pack(fill=BOTH, expand=True)

        # Header with controls
        header_frame = ttk.Frame(history_frame)
        header_frame.pack(fill=X, pady=(0, 5))

        ttk.Button(
            header_frame,
            text="New Session",
            command=self._start_new_session,
            bootstyle="outline-primary",
            width=12
        ).pack(side=LEFT, padx=(0, 5))

        ttk.Button(
            header_frame,
            text="Export",
            command=self._export_session,
            bootstyle="outline-info",
            width=10
        ).pack(side=LEFT)

        # Session statistics label
        self.session_stats_label = ttk.Label(
            history_frame,
            text="Entries: 0 | Patient: 0 | Doctor: 0",
            font=("", 8),
            foreground="gray"
        )
        self.session_stats_label.pack(fill=X, pady=(0, 5))

        # Create canvas for scrollable history
        canvas_frame = ttk.Frame(history_frame)
        canvas_frame.pack(fill=BOTH, expand=True)

        self.history_canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        history_scrollbar = ttk.Scrollbar(
            canvas_frame,
            orient=VERTICAL,
            command=self.history_canvas.yview
        )

        # Create frame inside canvas for entries
        self.history_entries_frame = ttk.Frame(self.history_canvas)

        # Configure canvas window
        self.history_window = self.history_canvas.create_window(
            (0, 0),
            window=self.history_entries_frame,
            anchor=NW
        )

        # Pack scrollbar and canvas
        history_scrollbar.pack(side=RIGHT, fill=Y)
        self.history_canvas.pack(side=LEFT, fill=BOTH, expand=True)

        # Configure scrolling
        self.history_canvas.configure(yscrollcommand=history_scrollbar.set)

        # Bind events for scrolling
        self.history_entries_frame.bind("<Configure>", self._on_history_frame_configure)
        self.history_canvas.bind("<Configure>", self._on_history_canvas_configure)

        # Bind mouse wheel scrolling
        self.history_canvas.bind_all("<MouseWheel>", self._on_history_mousewheel)
        self.history_canvas.bind_all("<Button-4>", self._on_history_mousewheel)
        self.history_canvas.bind_all("<Button-5>", self._on_history_mousewheel)

        # Welcome message
        self._add_history_welcome()

    def _on_history_frame_configure(self, event):
        """Update scroll region when history frame size changes."""
        self.history_canvas.configure(scrollregion=self.history_canvas.bbox("all"))

    def _on_history_canvas_configure(self, event):
        """Update window width when canvas size changes."""
        self.history_canvas.itemconfig(self.history_window, width=event.width)

    def _on_history_mousewheel(self, event):
        """Handle mouse wheel scrolling in history panel."""
        if event.num == 4 or event.delta > 0:
            self.history_canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.history_canvas.yview_scroll(1, "units")

    def _add_history_welcome(self):
        """Add welcome message to history panel."""
        welcome_frame = ttk.Frame(self.history_entries_frame, padding=10)
        welcome_frame.pack(fill=X, pady=5)

        ttk.Label(
            welcome_frame,
            text="Session started",
            font=("", 9, "italic"),
            foreground="gray"
        ).pack(anchor=W)

        ttk.Label(
            welcome_frame,
            text=f"Patient: {self.patient_language} | Doctor: {self.doctor_language}",
            font=("", 8),
            foreground="gray"
        ).pack(anchor=W)

    def _add_history_entry(self, entry: TranslationEntry):
        """Add a translation entry to the history panel.

        Args:
            entry: TranslationEntry to display
        """
        # Create entry frame
        entry_frame = ttk.Frame(self.history_entries_frame, padding=5)
        entry_frame.pack(fill=X, pady=2, padx=2)

        # Speaker color
        speaker_color = "#0066cc" if entry.speaker == Speaker.DOCTOR else "#cc6600"
        speaker_label = entry.speaker.value.title()

        # Header row with speaker and time
        header_frame = ttk.Frame(entry_frame)
        header_frame.pack(fill=X)

        ttk.Label(
            header_frame,
            text=speaker_label,
            foreground=speaker_color,
            font=("", 9, "bold")
        ).pack(side=LEFT)

        time_str = entry.timestamp.strftime("%H:%M:%S")
        ttk.Label(
            header_frame,
            text=time_str,
            foreground="gray",
            font=("", 8)
        ).pack(side=RIGHT)

        # Original text
        ttk.Label(
            entry_frame,
            text=f"[{entry.original_language}] {entry.original_text}",
            wraplength=250,
            font=("", 9),
            justify=LEFT
        ).pack(fill=X, anchor=W)

        # Translated text
        display_translation = entry.llm_refined_text or entry.translated_text
        ttk.Label(
            entry_frame,
            text=f"[{entry.target_language}] {display_translation}",
            wraplength=250,
            font=("", 9),
            foreground="gray",
            justify=LEFT
        ).pack(fill=X, anchor=W)

        # Action buttons row
        action_frame = ttk.Frame(entry_frame)
        action_frame.pack(fill=X, pady=(3, 0))

        # Copy button
        copy_btn = ttk.Button(
            action_frame,
            text="📋",
            command=lambda e=entry: self._copy_history_entry(e),
            bootstyle="outline-secondary",
            width=3
        )
        copy_btn.pack(side=LEFT, padx=(0, 3))
        ToolTip(copy_btn, "Copy to clipboard")

        # Replay button (for doctor entries - plays TTS, for patient - shows in patient area)
        if entry.speaker == Speaker.DOCTOR:
            replay_btn = ttk.Button(
                action_frame,
                text="🔊",
                command=lambda e=entry: self._replay_doctor_entry(e),
                bootstyle="outline-success",
                width=3
            )
            replay_btn.pack(side=LEFT, padx=(0, 3))
            ToolTip(replay_btn, "Play translation again")
        else:
            # For patient entries, allow loading back to input
            load_btn = ttk.Button(
                action_frame,
                text="↗",
                command=lambda e=entry: self._load_patient_entry(e),
                bootstyle="outline-info",
                width=3
            )
            load_btn.pack(side=LEFT, padx=(0, 3))
            ToolTip(load_btn, "Load to current patient area")

        # Separator
        ttk.Separator(entry_frame, orient=HORIZONTAL).pack(fill=X, pady=(5, 0))

        # Auto-scroll to bottom
        self.history_canvas.update_idletasks()
        self.history_canvas.yview_moveto(1.0)

        # Save to undo stack
        self._undo_stack.append({
            'frame': entry_frame,
            'entry': entry
        })
        self._update_undo_button_state()

        # Update statistics
        self._update_session_stats()

    def _copy_history_entry(self, entry: TranslationEntry):
        """Copy a history entry to clipboard.

        Args:
            entry: TranslationEntry to copy
        """
        try:
            display_translation = entry.llm_refined_text or entry.translated_text
            text = f"[{entry.original_language}] {entry.original_text}\n[{entry.target_language}] {display_translation}"
            try:
                import pyperclip
                pyperclip.copy(text)
            except Exception:
                self.dialog.clipboard_clear()
                self.dialog.clipboard_append(text)
                self.dialog.update()
            self.recording_status.config(text="Copied to clipboard", foreground="green")
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Copying history entry to clipboard",
                exception=e
            )
            self.logger.error(ctx.to_log_string())

    def _replay_doctor_entry(self, entry: TranslationEntry):
        """Replay a doctor entry via TTS.

        Args:
            entry: TranslationEntry to replay
        """
        display_translation = entry.llm_refined_text or entry.translated_text
        if not display_translation:
            return

        # Update button states for playback
        self.play_button.config(state=tk.DISABLED, text="🔊 Playing...")
        self.stop_button.config(state=tk.NORMAL)
        self.recording_status.config(text="Replaying...", foreground="blue")

        def play_audio():
            try:
                self.tts_manager.synthesize_and_play(
                    display_translation,
                    language=entry.target_language,
                    blocking=True,
                    output_device=self.selected_output.get()
                )
                self._safe_after(0, lambda: self._safe_ui_update(
                    lambda: self._on_playback_complete()
                ))
            except Exception as e:
                ctx = ErrorContext.capture(
                    operation="Replaying doctor entry via TTS",
                    exception=e,
                    input_summary=f"language={entry.target_language}"
                )
                self.logger.error(ctx.to_log_string(), exc_info=True)
                self._safe_after(0, lambda msg=ctx.user_message: self._safe_ui_update(
                    lambda: self._on_playback_error(msg)
                ))

        threading.Thread(target=play_audio, daemon=True).start()

    def _load_patient_entry(self, entry: TranslationEntry):
        """Load a patient entry back to the patient text areas.

        Args:
            entry: TranslationEntry to load
        """
        # Load to patient text areas
        self.patient_original_text.delete("1.0", tk.END)
        self.patient_original_text.insert("1.0", entry.original_text)

        display_translation = entry.llm_refined_text or entry.translated_text
        self.patient_translated_text.delete("1.0", tk.END)
        self.patient_translated_text.insert("1.0", display_translation)

        self.recording_status.config(text="Entry loaded", foreground="green")

    def _update_undo_button_state(self):
        """Update the undo button state based on stack contents."""
        if not self._dialog_exists():
            return
        try:
            if hasattr(self, 'undo_button'):
                state = NORMAL if self._undo_stack else DISABLED
                self.undo_button.config(state=state)
        except tk.TclError:
            pass

    def _undo_last_entry(self):
        """Undo the last history entry."""
        if not self._undo_stack:
            return

        try:
            # Pop last entry from stack
            last_item = self._undo_stack.pop()
            entry_frame = last_item['frame']
            entry = last_item['entry']

            # Destroy the UI frame
            if entry_frame and entry_frame.winfo_exists():
                entry_frame.destroy()

            # Remove from session entries
            session = self.session_manager.current_session
            if session and entry in session.entries:
                session.entries.remove(entry)

            # Update UI
            self._update_undo_button_state()
            self._update_session_stats()
            self.recording_status.config(text="Entry undone", foreground="green")

            # Update canvas
            self.history_canvas.update_idletasks()

        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Undoing last history entry",
                exception=e
            )
            self.logger.error(ctx.to_log_string(), exc_info=True)
            self.recording_status.config(text=f"Undo error: {ctx.user_message[:40]}", foreground="red")

    def _update_session_stats(self):
        """Update the session statistics display."""
        if not self.session_manager.current_session:
            self.session_stats_label.config(text="No active session")
            return

        session = self.session_manager.current_session
        total = len(session.entries)
        patient_count = sum(1 for e in session.entries if e.speaker == Speaker.PATIENT)
        doctor_count = sum(1 for e in session.entries if e.speaker == Speaker.DOCTOR)

        self.session_stats_label.config(
            text=f"Entries: {total} | Patient: {patient_count} | Doctor: {doctor_count}"
        )

    def _start_new_session(self):
        """Start a new translation session."""
        # End any existing session
        if self.session_manager.current_session:
            self.session_manager.end_session()

        # Clear history display
        for widget in self.history_entries_frame.winfo_children():
            widget.destroy()

        # Clear undo stack
        self._undo_stack.clear()
        self._update_undo_button_state()

        # Start new session
        self.session_manager.start_session(
            patient_language=self.patient_language,
            doctor_language=self.doctor_language
        )

        # Add welcome message
        self._add_history_welcome()

        # Clear current text areas
        self._clear_all()

        self.logger.info("Started new translation session")

    def _export_session(self):
        """Export the current session to a file."""
        if not self.session_manager.current_session:
            from tkinter import messagebox
            messagebox.showwarning(
                "No Session",
                "No active translation session to export.",
                parent=self.dialog
            )
            return

        from tkinter import filedialog

        # Get save location
        filename = filedialog.asksaveasfilename(
            parent=self.dialog,
            title="Export Session",
            defaultextension=".txt",
            filetypes=[
                ("Text files", "*.txt"),
                ("JSON files", "*.json"),
                ("All files", "*.*")
            ]
        )

        if not filename:
            return

        try:
            session = self.session_manager.current_session

            if filename.endswith('.json'):
                # Export as JSON
                data = {
                    'session_id': session.session_id,
                    'start_time': session.start_time.isoformat(),
                    'end_time': session.end_time.isoformat() if session.end_time else None,
                    'patient_language': session.patient_language,
                    'doctor_language': session.doctor_language,
                    'entries': [
                        {
                            'speaker': e.speaker.value,
                            'original_language': e.original_language,
                            'original_text': e.original_text,
                            'target_language': e.target_language,
                            'translated_text': e.translated_text,
                            'llm_refined_text': e.llm_refined_text,
                            'timestamp': e.timestamp.isoformat()
                        }
                        for e in session.entries
                    ]
                }
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                # Export as plain text
                lines = [
                    f"Translation Session",
                    f"==================",
                    f"Started: {session.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
                    f"Languages: {session.patient_language} <-> {session.doctor_language}",
                    f"",
                ]

                for entry in session.entries:
                    speaker = entry.speaker.value.upper()
                    time_str = entry.timestamp.strftime('%H:%M:%S')
                    display_translation = entry.llm_refined_text or entry.translated_text

                    lines.append(f"[{time_str}] {speaker}")
                    lines.append(f"  [{entry.original_language}] {entry.original_text}")
                    lines.append(f"  [{entry.target_language}] {display_translation}")
                    lines.append("")

                with open(filename, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines))

            self.recording_status.config(text=f"Exported to {filename}", foreground="green")

        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Exporting session",
                exception=e,
                input_summary=f"filename={filename if 'filename' in dir() else 'unknown'}"
            )
            self.logger.error(ctx.to_log_string())
            self.recording_status.config(text=f"Export error: {ctx.user_message}", foreground="red")


__all__ = ["HistoryMixin"]
