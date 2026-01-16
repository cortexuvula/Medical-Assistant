"""
Standalone RSVP Reader Dialog

A comprehensive RSVP reader that accepts text input via:
- Paste text directly
- Upload PDF files (with OCR fallback for scanned documents)
- Upload text files (.txt, .md, .rtf)

Features:
- Two modes: Input Mode and Reading Mode
- Full RSVP display with ORP (Optimal Recognition Point) highlighting
- Keyboard shortcuts for efficient navigation
- Settings persistence between sessions
- Light/Dark theme support

This dialog coordinates between the InputModePanel and ReadingModePanel
components for a modular architecture.
"""

import tkinter as tk
import ttkbootstrap as ttk
from tkinter import messagebox
from typing import Optional
import logging

from settings.settings import SETTINGS, save_settings
from .rsvp import RSVPEngine, RSVPSettings, RSVPTheme, InputModePanel, ReadingModePanel

logger = logging.getLogger(__name__)


class StandaloneRSVPDialog:
    """Standalone RSVP reader dialog with input and reading modes."""

    def __init__(self, parent):
        """Initialize standalone RSVP dialog.

        Args:
            parent: Parent window
        """
        self.parent = parent
        self.mode = "input"  # "input" or "reading"

        # Initialize engine
        self.engine = RSVPEngine()

        # Load settings
        self._load_settings()

        # Set theme colors
        self.colors = RSVPTheme.get_colors(self.settings.dark_theme)

        # Panel references
        self.input_panel: Optional[InputModePanel] = None
        self.reading_panel: Optional[ReadingModePanel] = None

        # Create and show dialog
        self._create_dialog()
        self._show_input_mode()

    def _load_settings(self) -> None:
        """Load settings from storage."""
        rsvp_settings = SETTINGS.get("rsvp", {})
        rsvp_reader_settings = SETTINGS.get("rsvp_reader", {})

        self.settings = RSVPSettings(
            wpm=rsvp_settings.get("wpm", 300),
            font_size=rsvp_settings.get("font_size", 48),
            chunk_size=rsvp_settings.get("chunk_size", 1),
            dark_theme=rsvp_settings.get("dark_theme", True),
            audio_cue=rsvp_settings.get("audio_cue", False),
            show_context=rsvp_settings.get("show_context", False)
        )

        # Validate loaded settings
        self.settings.wpm = self.settings.validate_wpm(self.settings.wpm)
        self.settings.font_size = self.settings.validate_font_size(self.settings.font_size)
        self.settings.chunk_size = self.settings.validate_chunk_size(self.settings.chunk_size)

        # Reader-specific settings
        self.last_directory = rsvp_reader_settings.get("last_directory", "")

    def _create_dialog(self) -> None:
        """Create the main dialog window."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("RSVP Reader")
        self.dialog.geometry("900x700")
        self.dialog.configure(bg=self.colors['bg'])
        self.dialog.resizable(True, True)
        self.dialog.minsize(700, 500)

        # Center on screen
        self.dialog.update_idletasks()
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        x = (screen_width // 2) - (900 // 2)
        y = (screen_height // 2) - (700 // 2)
        self.dialog.geometry(f"900x700+{x}+{y}")

        # Make modal
        self.dialog.transient(self.parent)
        self.dialog.deiconify()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        # Handle window close
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

        # Main container
        self.main_frame = ttk.Frame(self.dialog)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

    def _clear_main_frame(self) -> None:
        """Clear the main frame of all widgets."""
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    # =========================================================================
    # MODE SWITCHING
    # =========================================================================

    def _show_input_mode(self) -> None:
        """Show the input mode UI."""
        self.mode = "input"
        self._clear_main_frame()

        # Create input panel
        self.input_panel = InputModePanel(
            parent_frame=self.main_frame,
            colors=self.colors,
            on_start_reading=self._on_start_reading,
            on_theme_toggle=self._toggle_theme,
            last_directory=self.last_directory
        )

        # Update theme button
        self.input_panel.update_theme_button(self.settings.dark_theme)

        # Bind keyboard shortcuts for input mode
        self.dialog.bind('<Escape>', lambda e: self._on_close())
        self.dialog.bind('<Control-Return>', lambda e: self._on_start_reading(
            self.input_panel.get_text() if self.input_panel else ""
        ))

    def _on_start_reading(self, text: str) -> None:
        """Handle start reading event from input panel.

        Args:
            text: Text to read
        """
        if not text:
            messagebox.showwarning(
                "No Text",
                "Please enter or load some text first.",
                parent=self.dialog
            )
            return

        # Parse text with engine
        self.engine.parse_text(text)

        if self.engine.get_word_count() == 0:
            messagebox.showwarning(
                "No Content",
                "No readable text found.",
                parent=self.dialog
            )
            return

        # Update last directory from input panel
        if self.input_panel:
            self.last_directory = self.input_panel.last_directory
            self._save_reader_settings()

        self._show_reading_mode()

    def _show_reading_mode(self) -> None:
        """Show the reading mode UI."""
        self.mode = "reading"
        self._clear_main_frame()

        # Create reading panel
        self.reading_panel = ReadingModePanel(
            parent_frame=self.main_frame,
            dialog=self.dialog,
            engine=self.engine,
            settings=self.settings,
            colors=self.colors,
            on_back=self._back_to_input,
            on_theme_toggle=self._toggle_theme,
            on_settings_save=self._save_rsvp_settings
        )

        # Update theme button
        self.reading_panel.update_theme_button(self.settings.dark_theme)

    def _back_to_input(self) -> None:
        """Switch back to input mode, preserving the text."""
        text = self.engine.text
        self._show_input_mode()

        # Restore the text
        if self.input_panel and text:
            self.input_panel.set_text(text)

    # =========================================================================
    # THEME MANAGEMENT
    # =========================================================================

    def _toggle_theme(self) -> None:
        """Toggle between light and dark themes."""
        self.settings.dark_theme = not self.settings.dark_theme
        self.colors = RSVPTheme.get_colors(self.settings.dark_theme)

        # Update dialog background
        self.dialog.configure(bg=self.colors['bg'])

        # Update current panel
        if self.mode == "reading" and self.reading_panel:
            self.reading_panel.update_colors(self.colors)
            self.reading_panel.update_theme_button(self.settings.dark_theme)
        elif self.mode == "input" and self.input_panel:
            # Input mode needs to be rebuilt for full theme update
            # For simplicity, just update what we can
            self.input_panel.update_colors(self.colors)
            self.input_panel.update_theme_button(self.settings.dark_theme)

        self._save_rsvp_settings()

    # =========================================================================
    # SETTINGS PERSISTENCE
    # =========================================================================

    def _save_rsvp_settings(self) -> None:
        """Save RSVP display settings."""
        if "rsvp" not in SETTINGS:
            SETTINGS["rsvp"] = {}

        SETTINGS["rsvp"]["wpm"] = self.settings.wpm
        SETTINGS["rsvp"]["font_size"] = self.settings.font_size
        SETTINGS["rsvp"]["chunk_size"] = self.settings.chunk_size
        SETTINGS["rsvp"]["dark_theme"] = self.settings.dark_theme
        SETTINGS["rsvp"]["audio_cue"] = self.settings.audio_cue
        SETTINGS["rsvp"]["show_context"] = self.settings.show_context

        save_settings(SETTINGS)

    def _save_reader_settings(self) -> None:
        """Save reader-specific settings."""
        if "rsvp_reader" not in SETTINGS:
            SETTINGS["rsvp_reader"] = {}

        SETTINGS["rsvp_reader"]["last_directory"] = self.last_directory

        save_settings(SETTINGS)

    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================

    def _on_close(self) -> None:
        """Handle dialog close."""
        # Pause reading if in reading mode
        if self.reading_panel:
            self.reading_panel.pause()

        try:
            self.dialog.destroy()
        except tk.TclError:
            pass


__all__ = ["StandaloneRSVPDialog"]
