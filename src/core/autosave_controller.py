"""
Auto-Save Controller Module

Handles auto-save functionality including initialization, restoration,
and UI updates for the restore button.

This controller extracts auto-save logic from the main App class
to improve maintainability and separation of concerns.
"""

import logging
from datetime import datetime
from tkinter import messagebox, LEFT
from typing import TYPE_CHECKING, Dict, Any

from managers.autosave_manager import AutoSaveManager, AutoSaveDataProvider
from settings.settings import SETTINGS
from ui.tooltip import ToolTip

if TYPE_CHECKING:
    from core.app import MedicalDictationApp

logger = logging.getLogger(__name__)


class AutoSaveController:
    """Controller for managing auto-save functionality.

    This class coordinates:
    - Auto-save initialization and configuration
    - Data provider registration
    - Auto-save restoration
    - Restore button visibility
    """

    def __init__(self, app: 'MedicalDictationApp'):
        """Initialize the auto-save controller.

        Args:
            app: Reference to the main application instance
        """
        self.app = app

    def initialize_autosave(self) -> None:
        """Initialize the auto-save manager."""
        # Create auto-save manager
        autosave_interval = SETTINGS.get("autosave_interval", 300)  # 5 minutes default
        self.app.autosave_manager = AutoSaveManager(interval_seconds=autosave_interval)

        # Register data providers
        self.app.autosave_manager.register_data_provider(
            "transcript",
            AutoSaveDataProvider.create_text_widget_provider(self.app.transcript_text, "Transcript")
        )
        self.app.autosave_manager.register_data_provider(
            "soap_note",
            AutoSaveDataProvider.create_text_widget_provider(self.app.soap_text, "SOAP Note")
        )
        self.app.autosave_manager.register_data_provider(
            "referral",
            AutoSaveDataProvider.create_text_widget_provider(self.app.referral_text, "Referral")
        )
        self.app.autosave_manager.register_data_provider(
            "letter",
            AutoSaveDataProvider.create_text_widget_provider(self.app.letter_text, "Letter")
        )
        self.app.autosave_manager.register_data_provider(
            "context",
            AutoSaveDataProvider.create_text_widget_provider(self.app.context_text, "Context")
        )
        self.app.autosave_manager.register_data_provider(
            "chat",
            AutoSaveDataProvider.create_text_widget_provider(self.app.chat_text, "Chat")
        )
        self.app.autosave_manager.register_data_provider(
            "recording_state",
            AutoSaveDataProvider.create_recording_state_provider(self.app)
        )

        # Set up callbacks (deferred until status_manager is available)
        def setup_autosave_callbacks():
            if hasattr(self.app, 'status_manager') and self.app.status_manager:
                self.app.autosave_manager.on_save_start = lambda: self.app.status_manager.info("Auto-saving...")
                self.app.autosave_manager.on_save_complete = lambda: self.app.status_manager.success("Auto-save complete")
                self.app.autosave_manager.on_save_error = lambda e: self.app.status_manager.error(f"Auto-save failed: {e}")
            else:
                # Try again after a short delay
                self.app.after(100, setup_autosave_callbacks)

        # Delay callback setup until status_manager is ready
        self.app.after(100, setup_autosave_callbacks)

        # Check for existing auto-save and offer to restore
        self.check_and_restore_autosave()

        # Start auto-save if enabled
        if SETTINGS.get("autosave_enabled", True):
            self.app.autosave_manager.start()

        # Save on significant events
        self.app.bind("<<DocumentGenerated>>", lambda e: self.app.autosave_manager.perform_save())
        self.app.bind("<<RecordingComplete>>", lambda e: self.app.autosave_manager.perform_save())

    def check_and_restore_autosave(self) -> None:
        """Check for existing auto-save and make it available for manual restoration."""
        if not self.app.autosave_manager.has_unsaved_data():
            self.app.has_available_autosave = False
            return

        # Load latest auto-save
        saved_data = self.app.autosave_manager.load_latest()
        if not saved_data or "data" not in saved_data:
            self.app.has_available_autosave = False
            return

        # Check if data is recent (within last 24 hours)
        try:
            saved_time = datetime.fromisoformat(saved_data["timestamp"])
            age_hours = (datetime.now() - saved_time).total_seconds() / 3600

            if age_hours > 24:
                # Too old, clear it
                self.app.autosave_manager.clear_saves()
                self.app.has_available_autosave = False
                return
        except (ValueError, TypeError, KeyError) as e:
            logging.debug(f"Error checking autosave age: {e}")
            self.app.has_available_autosave = False
            return

        # Store the availability of auto-save data
        self.app.has_available_autosave = True
        self.app.last_autosave_timestamp = saved_data["timestamp"]

        # Update UI to show restore button if available
        self.update_restore_button_visibility()

    def restore_from_autosave(self, data: Dict[str, Any]) -> None:
        """Restore application state from auto-save data.

        Args:
            data: Auto-save data dictionary
        """
        try:
            # Restore text content
            for field, widget in [
                ("transcript", self.app.transcript_text),
                ("soap_note", self.app.soap_text),
                ("referral", self.app.referral_text),
                ("letter", self.app.letter_text),
                ("context", self.app.context_text),
                ("chat", self.app.chat_text)
            ]:
                if field in data and data[field] and "content" in data[field]:
                    widget.delete("1.0", "end")
                    widget.insert("1.0", data[field]["content"])

            # Restore recording state if applicable
            if "recording_state" in data and data["recording_state"]:
                state = data["recording_state"]
                self.app.current_recording_id = state.get("current_recording_id")

            if hasattr(self.app, 'status_manager') and self.app.status_manager:
                self.app.status_manager.success("Auto-save restored successfully")
            else:
                logging.info("Auto-save restored successfully")

        except Exception as e:
            logging.error(f"Failed to restore from auto-save: {e}")
            if hasattr(self.app, 'status_manager') and self.app.status_manager:
                self.app.status_manager.error("Failed to restore auto-save")
            else:
                logging.error("Failed to restore auto-save")

    def update_restore_button_visibility(self) -> None:
        """Update the visibility of the restore button based on auto-save availability."""
        if hasattr(self.app, 'restore_btn'):
            if self.app.has_available_autosave:
                self.app.restore_btn.pack(side=LEFT, padx=(10, 0))
                # Update tooltip with timestamp
                if hasattr(self.app, 'last_autosave_timestamp'):
                    ToolTip(self.app.restore_btn, f"Restore from auto-save ({self.app.last_autosave_timestamp})")
            else:
                self.app.restore_btn.pack_forget()

    def restore_autosave(self) -> None:
        """Manually restore from auto-save when button is clicked."""
        if not hasattr(self.app, 'has_available_autosave') or not self.app.has_available_autosave:
            self.app.status_manager.warning("No auto-save data available")
            return

        # Load latest auto-save
        saved_data = self.app.autosave_manager.load_latest()
        if not saved_data or "data" not in saved_data:
            self.app.status_manager.error("Failed to load auto-save data")
            self.app.has_available_autosave = False
            self.update_restore_button_visibility()
            return

        # Confirm restoration
        result = messagebox.askyesno(
            "Restore Auto-Save",
            f"Restore your work from {saved_data['timestamp']}?\n\n"
            "This will replace all current content.",
            parent=self.app
        )

        if result:
            self.restore_from_autosave(saved_data["data"])
            # Clear auto-saves after successful restoration
            self.app.autosave_manager.clear_saves()
            self.app.has_available_autosave = False
            self.update_restore_button_visibility()
            self.app.status_manager.success("Auto-save restored successfully")
