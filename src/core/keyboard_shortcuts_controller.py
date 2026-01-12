"""
Keyboard Shortcuts Controller Module

Handles keyboard shortcut binding and event handling for the application.

This controller extracts keyboard shortcuts logic from the main App class
to improve maintainability and separation of concerns.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.app import MedicalDictationApp

logger = logging.getLogger(__name__)


class KeyboardShortcutsController:
    """Controller for managing keyboard shortcuts.

    This class coordinates:
    - Binding all keyboard shortcuts
    - Handling special key events (like space for pause/resume)
    """

    def __init__(self, app: 'MedicalDictationApp'):
        """Initialize the keyboard shortcuts controller.

        Args:
            app: Reference to the main application instance
        """
        self.app = app

    def bind_shortcuts(self) -> None:
        """Bind all keyboard shortcuts to their respective actions."""
        # Basic shortcuts
        self.app.bind("<Control-n>", lambda _: self.app.new_session())
        self.app.bind("<Control-s>", lambda _: self.app.save_text())
        self.app.bind("<Control-c>", lambda _: self.app.copy_text())
        self.app.bind("<Control-l>", lambda _: self.app.load_audio_file())
        self.app.bind("<Control-z>", lambda _: self.app.undo_text())
        self.app.bind("<Control-y>", lambda _: self.app.redo_text())
        self.app.bind("<Alt-t>", lambda _: self.app.toggle_theme())
        self.app.bind("<F1>", lambda _: self.app.show_shortcuts())
        self.app.bind("<Control-e>", lambda _: self.app.export_as_pdf())
        self.app.bind("<Control-p>", lambda _: self.app.print_document())
        self.app.bind("<Control-slash>", lambda _: self.app._focus_chat_input())
        self.app.bind("<Control-comma>", lambda _: self.app.show_preferences())

        # Export shortcuts
        self.app.bind("<Control-Shift-w>", lambda _: self.app.export_as_word())
        self.app.bind("<Control-Shift-W>", lambda _: self.app.export_as_word())
        self.app.bind("<Control-Shift-f>", lambda _: self.app.export_as_fhir())
        self.app.bind("<Control-Shift-F>", lambda _: self.app.export_as_fhir())

        # AI Analysis shortcuts
        self.app.bind("<Control-d>", lambda _: self.app.create_diagnostic_analysis())
        self.app.bind("<Control-D>", lambda _: self.app.create_diagnostic_analysis())

        # Recording shortcuts - use bind_all for global access
        self.app.bind_all("<F5>", lambda _: self.app.toggle_soap_recording())
        self.app.bind_all("<Control-Shift-S>", lambda _: self.app.toggle_soap_recording())
        self.app.bind_all("<Key-space>", lambda _: self.handle_space_key())
        self.app.bind_all("<Escape>", lambda _: self.app.cancel_soap_recording())

        # Set focus to main window to ensure shortcuts work
        self.app.focus_set()

    def handle_space_key(self) -> None:
        """Handle space key press - only trigger pause/resume if currently recording."""
        # Only handle space key for recording pause/resume if we're actually recording
        if hasattr(self.app, 'soap_recording') and self.app.soap_recording:
            # Check if focus is not on a text widget to avoid interfering with typing
            focused_widget = self.app.focus_get()
            if focused_widget and hasattr(focused_widget, 'winfo_class'):
                widget_class = focused_widget.winfo_class()
                # Don't trigger pause if user is typing in a text widget
                if widget_class in ['Text', 'Entry', 'Combobox']:
                    return

            # Safe to trigger pause/resume
            self.app.toggle_soap_pause()
