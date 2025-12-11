# Import console suppression patch first (Windows only)
try:
    from hooks import suppress_console
except ImportError:
    pass  # Not critical if it fails

from string import punctuation
import logging
import os
import sys
import concurrent.futures
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
# Import tkinter constants for compatibility
from tkinter import TOP, BOTTOM, LEFT, RIGHT, NORMAL, DISABLED
from dotenv import load_dotenv
import openai
from managers.data_folder_manager import data_folder_manager
from managers.autosave_manager import AutoSaveManager, AutoSaveDataProvider
from typing import Callable, Optional, Dict, Any, List
import threading
from pydub import AudioSegment
from datetime import datetime
from utils.cleanup_utils import clear_all_content, clear_content_except_context
from database.database import Database
from audio.audio import AudioHandler
from audio.periodic_analysis import PeriodicAnalyzer, AudioSegmentExtractor

# Initialize logging
from managers.log_manager import setup_application_logging
log_manager = setup_application_logging()


from utils.utils import get_valid_microphones
from settings.settings import SETTINGS
from ui.dialogs.dialogs import show_settings_dialog, show_api_keys_dialog, show_shortcuts_dialog, show_about_dialog, show_letter_options_dialog, show_elevenlabs_settings_dialog, show_deepgram_settings_dialog
from ui.tooltip import ToolTip

import time

from core.app_initializer import AppInitializer
from core.app_settings_mixin import AppSettingsMixin
from core.app_chat_mixin import AppChatMixin
from audio.ffmpeg_utils import configure_pydub
from ui.menu_manager import MenuManager
from audio.soap_audio_processor import SOAPAudioProcessor
from ui.chat_ui import ChatUI

def main() -> None:
    """Main function to start the application."""
    # Configure FFmpeg paths before anything else
    configure_pydub()
    
    # Load environment variables from .env file
    load_dotenv(dotenv_path=str(data_folder_manager.env_file_path))
    
    # Log application startup
    logging.info("Medical Dictation application starting")
    
        
    # Create and start main app
    app = MedicalDictationApp()
    
    # Configure exception handler to log uncaught exceptions
    def handle_exception(exc_type, exc_value, exc_traceback):
        try:
            # Try to log the error with full traceback
            import traceback
            tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            logging.error(f"Uncaught exception: type: {exc_type}\n{''.join(tb_lines)}")
        except (OSError, IOError):
            # If logging fails, write to stderr as fallback
            sys.stderr.write(f"Error: {exc_type.__name__}: {exc_value}\n")

        # Don't show popup for TclErrors - these are usually harmless UI timing issues
        if exc_type.__name__ != "TclError":
            # Show error message to user for other types of errors
            try:
                messagebox.showerror("Error", f"An unexpected error occurred:\n{exc_type.__name__}: {str(exc_value)}")
            except tk.TclError:
                pass  # UI may be unavailable during shutdown
    
    # Set exception handler for uncaught exceptions - bind to the app instance
    app.report_callback_exception = lambda exc_type, exc_value, exc_tb: handle_exception(exc_type, exc_value, exc_tb)
    
    # Start the app
    app.mainloop()
    
    # Log application shutdown
    logging.info("Medical Dictation application shutting down")

class MedicalDictationApp(ttk.Window, AppSettingsMixin, AppChatMixin):
    """Main application class for the Medical Dictation App.

    This class inherits from ttk.Window and uses mixins to organize functionality:
    - AppSettingsMixin: Settings dialog and save settings methods
    - AppChatMixin: Chat-related methods and suggestions
    """

    def __init__(self) -> None:
        """Initialize the Medical Dictation App using AppInitializer."""
        # Use AppInitializer to handle the complex initialization process
        initializer = AppInitializer(self)
        initializer.initialize_application()

    def create_menu(self) -> None:
        """Create the application menu using MenuManager."""
        self.menu_manager = MenuManager(self)
        self.menu_manager.create_menu()

    def show_api_keys_dialog(self) -> None:
        """Shows a dialog to update API keys and updates the .env file."""
        # Delegate to menu manager
        self.menu_manager.show_api_keys_dialog()
        
        # Update local properties
        self.deepgram_api_key = os.getenv("DEEPGRAM_API_KEY", "")
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        
        # Update UI components based on API availability
        if openai.api_key:
            self.refine_button.config(state=NORMAL)
            self.improve_button.config(state=NORMAL)
            self.soap_button.config(state=NORMAL)
        else:
            self.refine_button.config(state=DISABLED)
            self.improve_button.config(state=DISABLED)
            self.soap_button.config(state=DISABLED)
            
        # Reinitialize audio handler with new API keys
        self.audio_handler = AudioHandler(
            elevenlabs_api_key=self.elevenlabs_api_key,
            deepgram_api_key=self.deepgram_api_key,
            groq_api_key=self.groq_api_key,
            recognition_language=self.recognition_language
        )
        
        self.status_manager.success("API keys updated successfully")

    def show_about(self) -> None:
        # Call the refactored function from dialogs.py
        show_about_dialog(self)

    def show_shortcuts(self) -> None:
        # Call the refactored function from dialogs.py
        show_shortcuts_dialog(self)
        
    def show_letter_options_dialog(self) -> tuple:
        # Call the refactored function from dialogs.py
        return show_letter_options_dialog(self)
        
    def show_elevenlabs_settings(self) -> None:
        # Call the refactored function from dialogs.py
        show_elevenlabs_settings_dialog(self)
        
        # Refresh the audio handler with potentially new settings
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self.audio_handler = AudioHandler(
            elevenlabs_api_key=self.elevenlabs_api_key,
            deepgram_api_key=self.deepgram_api_key,
            groq_api_key=self.groq_api_key,
            recognition_language=self.recognition_language
        )
        self.status_manager.success("ElevenLabs settings saved successfully")
        
    def record_prefix_audio(self) -> None:
        """Shows a dialog to record and save a prefix audio file."""
        self.audio_dialog_manager.show_prefix_recording_dialog()

    def show_deepgram_settings(self) -> None:
        """Show dialog to configure Deepgram settings."""
        # Call the dialog function
        show_deepgram_settings_dialog(self)
        
        # Refresh the audio handler with potentially new settings
        self.audio_handler = AudioHandler(
            elevenlabs_api_key=self.elevenlabs_api_key,
            deepgram_api_key=self.deepgram_api_key,
            groq_api_key=self.groq_api_key,
            recognition_language=self.recognition_language
        )
        self.status_manager.success("Deepgram settings saved successfully")
    
    def show_translation_settings(self) -> None:
        """Show dialog to configure translation settings."""
        from ui.dialogs.dialogs import show_translation_settings_dialog
        show_translation_settings_dialog(self)
        self.status_manager.success("Translation settings saved successfully")
    
    def show_tts_settings(self) -> None:
        """Show dialog to configure TTS settings."""
        from ui.dialogs.dialogs import show_tts_settings_dialog
        show_tts_settings_dialog(self)
        self.status_manager.success("TTS settings saved successfully")

    def set_default_folder(self) -> None:
        """Set the default storage folder using FolderDialogManager."""
        self.folder_dialog_manager.show_storage_folder_dialog()


    def export_prompts(self) -> None:
        """Export prompts using FileManager."""
        self.file_manager.export_prompts()

    def import_prompts(self) -> None:
        """Import prompts using FileManager."""
        self.file_manager.import_prompts()

    def create_widgets(self) -> None:
        """Create widgets for the workflow UI mode."""
        # Define command mapping for buttons
        command_map = {
            "new_session": self.new_session,
            "undo_text": self.undo_text,
            "redo_text": self.redo_text,
            "copy_text": self.copy_text,
            "save_text": self.save_text,
            "load_audio_file": self.load_audio_file,
            "refine_text": self.refine_text,
            "improve_text": self.improve_text,
            "create_soap_note": self.create_soap_note,
            "create_referral": self.create_referral,
            "create_letter": self.create_letter,
            "create_diagnostic_analysis": self.create_diagnostic_analysis,
            "analyze_medications": self.analyze_medications,
            "extract_clinical_data": self.extract_clinical_data,
            "manage_workflow": self.manage_workflow,
            "open_translation": self.open_translation_dialog,
            "toggle_soap_recording": self.toggle_soap_recording,
            "toggle_soap_pause": self.toggle_soap_pause,
            "cancel_soap_recording": self.cancel_soap_recording,
            "clear_advanced_analysis": self.clear_advanced_analysis_text
        }
        
        # Create main container with horizontal split
        main_container = ttk.PanedWindow(self, orient="horizontal")
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Left side - main content area
        left_frame = ttk.Frame(main_container)
        main_container.add(left_frame, weight=3)
        
        # Create status bar at the bottom
        status_frame, self.status_icon_label, self.status_label, self.provider_indicator, self.progress_bar = self.ui.create_status_bar()
        status_frame.pack(side=BOTTOM, fill=tk.X)
        
        # Top bar with microphone and provider settings
        top_bar = ttk.Frame(left_frame)
        top_bar.pack(side=TOP, fill=tk.X, padx=10, pady=5)
        
        # Microphone selection
        mic_frame = ttk.Frame(top_bar)
        mic_frame.pack(side=LEFT, fill=tk.X, expand=True)
        
        ttk.Label(mic_frame, text="Microphone:").pack(side=LEFT, padx=(0, 5))
        
        # Get available microphones and populate dropdown
        mic_names = get_valid_microphones() or []
        self.mic_combobox = ttk.Combobox(mic_frame, values=mic_names, state="readonly", width=40)
        self.mic_combobox.pack(side=LEFT, padx=(0, 10))
        self.mic_combobox.bind("<<ComboboxSelected>>", self._on_microphone_change)
        
        # Set initial selection if microphones are available
        if len(mic_names) > 0:
            saved_mic = SETTINGS.get("selected_microphone", "")
            if saved_mic and saved_mic in mic_names:
                self.mic_combobox.set(saved_mic)
            else:
                self.mic_combobox.current(0)
        
        # Refresh button
        refresh_btn = ttk.Button(mic_frame, text="⟳", width=3, command=self.refresh_microphones)
        refresh_btn.pack(side=LEFT)
        self.ui.components['refresh_btn'] = refresh_btn
        ToolTip(refresh_btn, "Refresh microphone list")
        
        # Provider selection
        provider_frame = ttk.Frame(top_bar)
        provider_frame.pack(side=LEFT)

        # Get available providers (those with API keys configured)
        self._available_ai_providers, self._ai_display_names = self._get_available_ai_providers()
        self._available_stt_providers, self._stt_display_names = self._get_available_stt_providers()

        ttk.Label(provider_frame, text="AI:").pack(side=LEFT, padx=(10, 5))
        self.provider_combobox = ttk.Combobox(
            provider_frame,
            values=self._ai_display_names,
            state="readonly",
            width=12
        )
        self.provider_combobox.pack(side=LEFT)
        self.provider_combobox.bind("<<ComboboxSelected>>", self._on_provider_change)

        ttk.Label(provider_frame, text="STT:").pack(side=LEFT, padx=(10, 5))
        self.stt_combobox = ttk.Combobox(
            provider_frame,
            values=self._stt_display_names,
            state="readonly",
            width=12
        )
        self.stt_combobox.pack(side=LEFT)
        self.stt_combobox.bind("<<ComboboxSelected>>", self._on_stt_change)
        
        # Copy button - easily accessible
        copy_btn = ttk.Button(
            provider_frame,
            text="Copy",
            command=self.copy_text,
            width=10,
            bootstyle="primary"
        )
        copy_btn.pack(side=LEFT, padx=(10, 0))
        ToolTip(copy_btn, "Copy current text to clipboard (Ctrl+C)")
        
        # Theme toggle
        self.theme_btn = ttk.Button(
            provider_frame,
            text="Theme",
            command=self.toggle_theme,
            width=10
        )
        self.theme_btn.pack(side=LEFT, padx=(10, 0))
        self.theme_label = ttk.Label(provider_frame, text="(Light Mode)", width=12)
        self.theme_label.pack(side=LEFT, padx=(5, 0))
        
        # Restore auto-save button (initially hidden)
        self.restore_btn = ttk.Button(
            provider_frame,
            text="↻ Restore",
            command=self.restore_autosave,
            width=10,
            bootstyle="warning"
        )
        self.restore_btn.pack(side=LEFT, padx=(10, 0))
        self.restore_btn.pack_forget()  # Initially hidden
        ToolTip(self.restore_btn, "Restore from auto-saved session")
        
        # Create workflow tabs
        self.workflow_notebook = self.ui.create_workflow_tabs(command_map)
        self.workflow_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 2))
        
        # Create the text notebook (for transcripts, SOAP, etc.)
        self.notebook, self.transcript_text, self.soap_text, self.referral_text, self.letter_text, self.chat_text, self.rag_text, _ = self.ui.create_notebook()
        self.notebook.pack(in_=left_frame, fill=tk.BOTH, expand=True, padx=10, pady=(2, 0))
        
        # Create chat interface below the notebook
        self.chat_ui = ChatUI(left_frame, self)
        self.chat_ui.set_send_callback(self._handle_chat_message)
        
        # Apply initial theme to chat UI
        self.after(50, lambda: self.chat_ui.update_theme())
        
        # Set initial chat suggestions
        self.after(100, self._update_chat_suggestions)
        
        # Right side - context panel
        self.context_panel = self.ui.create_context_panel()
        main_container.add(self.context_panel, weight=1)
        
        # Get context text widget from UI
        self.context_text = self.ui.components['context_text']
        
        # Set initial active text widget
        self.active_text_widget = self.transcript_text
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
        # Store button references for compatibility
        self._store_workflow_button_references()
        
        # Set initial provider selections
        self._initialize_provider_selections()
        
        # Initialize auto-save manager
        self._initialize_autosave()
    
    def _store_workflow_button_references(self):
        """Store workflow button references for compatibility with existing code."""
        # Map workflow UI buttons to expected button names
        ui_components = self.ui.components
        
        self.buttons = {
            "refine": ui_components.get("process_refine_button"),
            "improve": ui_components.get("process_improve_button"),
            "soap": ui_components.get("generate_soap_button"),
            "referral": ui_components.get("generate_referral_button"),
            "letter": ui_components.get("generate_letter_button"),
            "record_soap": ui_components.get("main_record_button"),
            "pause_soap": ui_components.get("pause_button"),
            "cancel_soap": ui_components.get("cancel_button"),
            "load": ui_components.get("file_load_button"),
            "save": ui_components.get("file_save_button"),
            "new_session": ui_components.get("file_new_session_button")
        }
        
        # Store specific button references
        self.refine_button = self.buttons["refine"]
        self.improve_button = self.buttons["improve"]
        self.soap_button = self.buttons["soap"]
        self.referral_button = self.buttons["referral"]
        self.letter_button = self.buttons["letter"]
        self.record_soap_button = self.buttons["record_soap"]
        self.pause_soap_button = self.buttons["pause_soap"]
        self.cancel_soap_button = self.buttons["cancel_soap"]
        self.load_button = self.buttons["load"]
        self.save_button = self.buttons["save"]
    
    def _get_available_ai_providers(self):
        """Get available AI providers. Delegates to ProviderConfigController."""
        return self.provider_config_controller.get_available_ai_providers()

    def _get_available_stt_providers(self):
        """Get available STT providers. Delegates to ProviderConfigController."""
        return self.provider_config_controller.get_available_stt_providers()

    def _initialize_provider_selections(self):
        """Initialize provider selections. Delegates to ProviderConfigController."""
        self.provider_config_controller.initialize_provider_selections()

    def _initialize_autosave(self):
        """Initialize the auto-save manager."""
        # Create auto-save manager
        autosave_interval = SETTINGS.get("autosave_interval", 300)  # 5 minutes default
        self.autosave_manager = AutoSaveManager(interval_seconds=autosave_interval)
        
        # Register data providers
        self.autosave_manager.register_data_provider(
            "transcript",
            AutoSaveDataProvider.create_text_widget_provider(self.transcript_text, "Transcript")
        )
        self.autosave_manager.register_data_provider(
            "soap_note",
            AutoSaveDataProvider.create_text_widget_provider(self.soap_text, "SOAP Note")
        )
        self.autosave_manager.register_data_provider(
            "referral",
            AutoSaveDataProvider.create_text_widget_provider(self.referral_text, "Referral")
        )
        self.autosave_manager.register_data_provider(
            "letter",
            AutoSaveDataProvider.create_text_widget_provider(self.letter_text, "Letter")
        )
        self.autosave_manager.register_data_provider(
            "context",
            AutoSaveDataProvider.create_text_widget_provider(self.context_text, "Context")
        )
        self.autosave_manager.register_data_provider(
            "chat",
            AutoSaveDataProvider.create_text_widget_provider(self.chat_text, "Chat")
        )
        self.autosave_manager.register_data_provider(
            "recording_state",
            AutoSaveDataProvider.create_recording_state_provider(self)
        )
        
        # Set up callbacks (deferred until status_manager is available)
        def setup_autosave_callbacks():
            if hasattr(self, 'status_manager') and self.status_manager:
                self.autosave_manager.on_save_start = lambda: self.status_manager.info("Auto-saving...")
                self.autosave_manager.on_save_complete = lambda: self.status_manager.success("Auto-save complete")
                self.autosave_manager.on_save_error = lambda e: self.status_manager.error(f"Auto-save failed: {e}")
            else:
                # Try again after a short delay
                self.after(100, setup_autosave_callbacks)
        
        # Delay callback setup until status_manager is ready
        self.after(100, setup_autosave_callbacks)
        
        # Check for existing auto-save and offer to restore
        self._check_and_restore_autosave()
        
        # Start auto-save if enabled
        if SETTINGS.get("autosave_enabled", True):
            self.autosave_manager.start()
            
        # Save on significant events
        self.bind("<<DocumentGenerated>>", lambda e: self.autosave_manager.perform_save())
        self.bind("<<RecordingComplete>>", lambda e: self.autosave_manager.perform_save())

    def _check_and_restore_autosave(self):
        """Check for existing auto-save and make it available for manual restoration."""
        if not self.autosave_manager.has_unsaved_data():
            self.has_available_autosave = False
            return
            
        # Load latest auto-save
        saved_data = self.autosave_manager.load_latest()
        if not saved_data or "data" not in saved_data:
            self.has_available_autosave = False
            return
            
        # Check if data is recent (within last 24 hours)
        try:
            saved_time = datetime.fromisoformat(saved_data["timestamp"])
            age_hours = (datetime.now() - saved_time).total_seconds() / 3600

            if age_hours > 24:
                # Too old, clear it
                self.autosave_manager.clear_saves()
                self.has_available_autosave = False
                return
        except (ValueError, TypeError, KeyError) as e:
            logging.debug(f"Error checking autosave age: {e}")
            self.has_available_autosave = False
            return
            
        # Store the availability of auto-save data
        self.has_available_autosave = True
        self.last_autosave_timestamp = saved_data["timestamp"]
        
        # Update UI to show restore button if available
        self._update_restore_button_visibility()
    
    def _restore_from_autosave(self, data: Dict[str, Any]):
        """Restore application state from auto-save data."""
        try:
            # Restore text content
            for field, widget in [
                ("transcript", self.transcript_text),
                ("soap_note", self.soap_text),
                ("referral", self.referral_text),
                ("letter", self.letter_text),
                ("context", self.context_text),
                ("chat", self.chat_text)
            ]:
                if field in data and data[field] and "content" in data[field]:
                    widget.delete("1.0", "end")
                    widget.insert("1.0", data[field]["content"])
            
            # Restore recording state if applicable
            if "recording_state" in data and data["recording_state"]:
                state = data["recording_state"]
                self.current_recording_id = state.get("current_recording_id")
            
            if hasattr(self, 'status_manager') and self.status_manager:
                self.status_manager.success("Auto-save restored successfully")
            else:
                logging.info("Auto-save restored successfully")
            
        except Exception as e:
            logging.error(f"Failed to restore from auto-save: {e}")
            if hasattr(self, 'status_manager') and self.status_manager:
                self.status_manager.error("Failed to restore auto-save")
            else:
                logging.error("Failed to restore auto-save")
    
    def _update_restore_button_visibility(self):
        """Update the visibility of the restore button based on auto-save availability."""
        if hasattr(self, 'restore_btn'):
            if self.has_available_autosave:
                self.restore_btn.pack(side=LEFT, padx=(10, 0))
                # Update tooltip with timestamp
                if hasattr(self, 'last_autosave_timestamp'):
                    ToolTip(self.restore_btn, f"Restore from auto-save ({self.last_autosave_timestamp})")
            else:
                self.restore_btn.pack_forget()
    
    def restore_autosave(self):
        """Manually restore from auto-save when button is clicked."""
        if not hasattr(self, 'has_available_autosave') or not self.has_available_autosave:
            self.status_manager.warning("No auto-save data available")
            return
            
        # Load latest auto-save
        saved_data = self.autosave_manager.load_latest()
        if not saved_data or "data" not in saved_data:
            self.status_manager.error("Failed to load auto-save data")
            self.has_available_autosave = False
            self._update_restore_button_visibility()
            return
            
        # Confirm restoration
        result = messagebox.askyesno(
            "Restore Auto-Save",
            f"Restore your work from {saved_data['timestamp']}?\n\n"
            "This will replace all current content.",
            parent=self
        )
        
        if result:
            self._restore_from_autosave(saved_data["data"])
            # Clear auto-saves after successful restoration
            self.autosave_manager.clear_saves()
            self.has_available_autosave = False
            self._update_restore_button_visibility()
            self.status_manager.success("Auto-save restored successfully")

    def bind_shortcuts(self) -> None:
        # Basic shortcuts
        self.bind("<Control-n>", lambda _: self.new_session())
        self.bind("<Control-s>", lambda _: self.save_text())
        self.bind("<Control-c>", lambda _: self.copy_text())
        self.bind("<Control-l>", lambda _: self.load_audio_file())
        self.bind("<Control-z>", lambda _: self.undo_text())
        self.bind("<Control-y>", lambda _: self.redo_text())
        self.bind("<Alt-t>", lambda _: self.toggle_theme())
        self.bind("<F1>", lambda _: self.show_shortcuts())
        self.bind("<Control-e>", lambda _: self.export_as_pdf())
        self.bind("<Control-p>", lambda _: self.print_document())
        self.bind("<Control-slash>", lambda _: self._focus_chat_input())
        
        # Recording shortcuts - use bind_all for global access
        self.bind_all("<F5>", lambda _: self.toggle_soap_recording())
        self.bind_all("<Control-Shift-S>", lambda _: self.toggle_soap_recording())
        self.bind_all("<Key-space>", lambda _: self._handle_space_key())
        self.bind_all("<Escape>", lambda _: self.cancel_soap_recording())
        
        # Set focus to main window to ensure shortcuts work
        self.focus_set()

    def _handle_space_key(self) -> None:
        """Handle space key press - only trigger pause/resume if currently recording."""
        # Only handle space key for recording pause/resume if we're actually recording
        if hasattr(self, 'soap_recording') and self.soap_recording:
            # Check if focus is not on a text widget to avoid interfering with typing
            focused_widget = self.focus_get()
            if focused_widget and hasattr(focused_widget, 'winfo_class'):
                widget_class = focused_widget.winfo_class()
                # Don't trigger pause if user is typing in a text widget
                if widget_class in ['Text', 'Entry', 'Combobox']:
                    return
            
            # Safe to trigger pause/resume
            self.toggle_soap_pause()

    # Settings dialog methods are provided by AppSettingsMixin

    def new_session(self) -> None:
        if messagebox.askyesno("New Dictation", "Start a new session? Unsaved changes will be lost."):
            clear_all_content(self)


    def save_text(self) -> None:
        """Save text using FileManager. Delegates to DocumentExportController."""
        self.document_export_controller.save_text()

    def export_as_pdf(self) -> None:
        """Export current document as PDF. Delegates to DocumentExportController."""
        self.document_export_controller.export_as_pdf()

    def export_all_as_pdf(self) -> None:
        """Export all documents as separate PDFs. Delegates to DocumentExportController."""
        self.document_export_controller.export_all_as_pdf()

    def print_document(self) -> None:
        """Print current document. Delegates to DocumentExportController."""
        self.document_export_controller.print_document()

    def _parse_soap_sections(self, content: str) -> Dict[str, str]:
        """Parse SOAP note content into sections. Delegates to DocumentExportController."""
        return self.document_export_controller.parse_soap_sections(content)

    def copy_text(self) -> None:
        """Copy text to clipboard. Delegates to TextProcessingController."""
        self.text_processing_controller.copy_text()

    def clear_text(self) -> None:
        """Clear transcript text. Delegates to TextProcessingController."""
        self.text_processing_controller.clear_text()

    def append_text(self, text: str) -> None:
        """Append text to transcript. Delegates to TextProcessingController."""
        self.text_processing_controller.append_text(text)

    def scratch_that(self) -> None:
        """Remove last text chunk. Delegates to TextProcessingController."""
        self.text_processing_controller.scratch_that()

    def delete_last_word(self) -> None:
        """Delete last word. Delegates to TextProcessingController."""
        self.text_processing_controller.delete_last_word()

    def update_status(self, message: str, status_type="info") -> None:
        self.status_manager.update_status(message, status_type)

    def reset_status(self) -> None:
        self.status_manager.reset_status()

    def process_soap_recording(self) -> None:
        """Process SOAP recording using AudioHandler with improved concurrency."""
        self.soap_processor.process_soap_recording()

    def handle_recognized_text(self, text: str) -> None:
        if not text.strip():
            return
        # Use the active text widget instead of transcript_text directly
        active_widget = self.get_active_text_widget()
        commands = {
            "new paragraph": lambda: active_widget.insert(tk.END, "\n\n"),
            "new line": lambda: active_widget.insert(tk.END, "\n"),
            "full stop": lambda: active_widget.insert(tk.END, ". "),
            "comma": lambda: active_widget.insert(tk.END, ", "),
            "question mark": lambda: active_widget.insert(tk.END, "? "),
            "exclamation point": lambda: active_widget.insert(tk.END, "! "),
            "semicolon": lambda: active_widget.insert(tk.END, "; "),
            "colon": lambda: active_widget.insert(tk.END, ": "),
            "open quote": lambda: active_widget.insert(tk.END, "\""),
            "close quote": lambda: active_widget.insert(tk.END, "\""),
            "open parenthesis": lambda: active_widget.insert(tk.END, "("),
            "close parenthesis": lambda: active_widget.insert(tk.END, ")"),
            "delete last word": self.delete_last_word,
            "scratch that": self.scratch_that,
            "new dictation": self.new_session,
            "clear text": self.clear_text,
            "copy text": self.copy_text,
            "save text": self.save_text,
        }
        cleaned = text.lower().strip().translate(str.maketrans('', '', punctuation))
        if cleaned in commands:
            commands[cleaned]()
        else:
            self.append_text_to_widget(text, active_widget)

    def _process_text_with_ai(self, api_func: Callable[[str], str], success_message: str, button: ttk.Button, target_widget: tk.Widget) -> None:
        """Process text with AI. Delegates to TextProcessingController."""
        self.text_processing_controller.process_text_with_ai(api_func, success_message, button, target_widget)

    def _update_text_area(self, new_text: str, success_message: str, button: ttk.Button, target_widget: tk.Widget) -> None:
        """Update text area with new content. Delegates to TextProcessingController."""
        self.text_processing_controller._update_text_area(new_text, success_message, button, target_widget)

    def get_active_text_widget(self) -> tk.Widget:
        """Get the currently active text widget. Delegates to TextProcessingController."""
        return self.text_processing_controller.get_active_text_widget()

    def refine_text(self) -> None:
        """Refine text using AI processor. Delegates to TextProcessingController."""
        self.text_processing_controller.refine_text()

    def improve_text(self) -> None:
        """Improve text using AI processor. Delegates to TextProcessingController."""
        self.text_processing_controller.improve_text()

    def _handle_ai_result(self, result: dict, operation: str, widget: tk.Widget):
        """Handle AI processing result. Delegates to TextProcessingController."""
        self.text_processing_controller._handle_ai_result(result, operation, widget)

    def create_soap_note(self) -> None:
        """Create a SOAP note using DocumentGenerators."""
        self.document_generators.create_soap_note()

    def refresh_microphones(self) -> None:
        """Refresh the list of available microphones with simple animation."""
        # Find the refresh button
        refresh_btn = self.ui.components.get('refresh_btn')
        
        # If animation is already in progress, return
        if hasattr(self, '_refreshing') and self._refreshing:
            return
            
        # Mark as refreshing
        self._refreshing = True
        
        # Disable the button during refresh
        if refresh_btn:
            refresh_btn.config(state=tk.DISABLED)
            
        # Set wait cursor (use watch which is cross-platform)
        try:
            self.config(cursor="watch")
        except tk.TclError:
            # Some platforms may not support cursor changes
            pass
        
        # Define the animation frames
        animation_chars = ["⟳", "⟲", "↻", "↺", "⟳"]
        
        def animate_refresh(frame=0):
            """Simple animation function to rotate the refresh button text."""
            if frame < len(animation_chars) * 2:  # Repeat animation twice
                if refresh_btn:
                    refresh_btn.config(text=animation_chars[frame % len(animation_chars)])
                self.after(100, lambda: animate_refresh(frame + 1))
            else:
                # Animation complete, perform actual refresh
                logging.debug("Microphone refresh animation complete, starting refresh")
                do_refresh()
                
        def do_refresh():
            """Perform the actual microphone refresh."""
            try:
                # Get available microphones using common method
                from utils.utils import get_valid_microphones
                from settings.settings import SETTINGS, save_settings
                
                mic_names = get_valid_microphones()
                
                # Clear existing items
                self.mic_combobox['values'] = []
                
                # Add device names to dropdown
                if mic_names:
                    self.mic_combobox['values'] = mic_names
                    
                    # Try to select previously saved microphone or select first one
                    saved_mic = SETTINGS.get("selected_microphone", "")
                    if saved_mic and saved_mic in mic_names:
                        self.mic_combobox.set(saved_mic)
                    else:
                        # Select first device and save it
                        self.mic_combobox.current(0)
                        SETTINGS["selected_microphone"] = self.mic_combobox.get()
                        save_settings(SETTINGS)
                else:
                    self.mic_combobox['values'] = ["No microphones found"]
                    self.mic_combobox.current(0)
                    self.update_status("No microphones detected", "warning")
                    
            except (OSError, RuntimeError, tk.TclError) as e:
                logging.error(f"Error refreshing microphones: {e}", exc_info=True)
                self.update_status("Error detecting microphones", "error")
            finally:
                # Reset animation state
                self._refreshing = False
                logging.debug("Resetting microphone refresh state and cursor")
                
                # Reset button state and cursor
                if refresh_btn:
                    refresh_btn.config(text="⟳", state=tk.NORMAL)
                
                # Reset cursor - try multiple approaches
                cursor_reset = False
                try:
                    self.config(cursor="")
                    cursor_reset = True
                    logging.debug("Cursor reset to default successfully")
                except Exception as e:
                    logging.debug(f"Failed to reset cursor to default: {e}")
                    try:
                        self.config(cursor="arrow")
                        cursor_reset = True
                        logging.debug("Cursor reset to arrow successfully")
                    except Exception as e2:
                        logging.debug(f"Failed to reset cursor to arrow: {e2}")
                        try:
                            self.config(cursor="left_ptr")
                            cursor_reset = True
                            logging.debug("Cursor reset to left_ptr successfully")
                        except Exception as e3:
                            logging.debug(f"Failed to reset cursor to left_ptr: {e3}")
                
                if not cursor_reset:
                    logging.warning("Could not reset cursor after microphone refresh")

                # Force cursor update by updating the window
                try:
                    self.update_idletasks()
                except tk.TclError:
                    pass  # Window may be closing
        
        # Start the animation
        animate_refresh()
        
        # Add a fallback cursor reset in case something goes wrong
        self.after(3000, self._reset_cursor_fallback)
    
    def _reset_cursor_fallback(self):
        """Fallback method to reset cursor if it gets stuck."""
        try:
            if hasattr(self, '_refreshing') and self._refreshing:
                logging.warning("Cursor reset fallback triggered - microphone refresh may have failed")
                self._refreshing = False
                # Try to reset cursor
                try:
                    self.config(cursor="")
                except tk.TclError:
                    try:
                        self.config(cursor="arrow")
                    except tk.TclError:
                        pass  # Cursor change not supported
                # Re-enable refresh button
                refresh_btn = self.ui.components.get('refresh_btn')
                if refresh_btn:
                    refresh_btn.config(text="⟳", state=tk.NORMAL)
        except Exception as e:
            logging.error(f"Error in cursor reset fallback: {e}")


    def toggle_soap_recording(self) -> None:
        """Toggle SOAP recording using RecordingController.

        This method delegates to the RecordingController for centralized recording management.
        """
        # Delegate to recording controller if available
        if hasattr(self, 'recording_controller') and self.recording_controller:
            self.recording_controller.toggle_recording()
        else:
            # Fallback to legacy implementation (should not happen in normal use)
            self._toggle_soap_recording_legacy()

    def _finalize_soap_recording(self, recording_data: dict = None):
        """Complete the SOAP recording process with recording data from RecordingManager."""
        # Recording data should come from RecordingManager which uses AudioStateManager
        if not recording_data or not recording_data.get('audio'):
            self.status_manager.error("No audio data available")
            self._update_recording_ui_state(recording=False, caller="finalize_no_audio")
            return
        
        # Check if quick continue mode is enabled
        if SETTINGS.get("quick_continue_mode", True):
            # Queue for background processing
            self._queue_recording_for_processing(recording_data)
            # Reset UI immediately
            self._reset_ui_for_next_patient()
            # Show status
            self.status_manager.info("Recording queued • Ready for next patient")
            
            # Trigger recording complete event for auto-save (also when queued)
            self.event_generate("<<RecordingComplete>>", when="tail")
        else:
            # Current behavior - process immediately
            self.process_soap_recording()
            # Reset all button states after processing is complete
            self.after(0, lambda: self._update_recording_ui_state(recording=False, caller="finalize_delayed"))
            
            # Trigger recording complete event for auto-save
            self.event_generate("<<RecordingComplete>>", when="tail")


    def toggle_soap_pause(self) -> None:
        """Toggle pause for SOAP recording.

        This method delegates to the RecordingController for centralized recording management.
        """
        # Delegate to recording controller if available
        if hasattr(self, 'recording_controller') and self.recording_controller:
            self.recording_controller.toggle_pause()
        elif self.soap_recording:
            # Fallback to legacy behavior
            if self.soap_stop_listening_function:
                self.pause_soap_recording()
            else:
                self.resume_soap_recording()

    def pause_soap_recording(self) -> None:
        """Pause SOAP recording.

        This method delegates to the RecordingController for centralized recording management.
        """
        # Delegate to recording controller if available
        if hasattr(self, 'recording_controller') and self.recording_controller:
            self.recording_controller.pause()
            return

        # Legacy implementation (fallback)
        if self.soap_stop_listening_function:
            # Play pause sound (quick beep)
            self.play_recording_sound(start=False)
            
            # Pause the recording manager
            self.recording_manager.pause_recording()
            
            # Stop the current recording
            self.soap_stop_listening_function()
            self.soap_stop_listening_function = None
            
            # Update UI
            self._update_recording_ui_state(recording=True, paused=True, caller="pause")
            self.update_status("SOAP recording paused. Press Resume to continue.", "info")

    def resume_soap_recording(self) -> None:
        """Resume SOAP recording after pause using the selected microphone.

        This method delegates to the RecordingController for centralized recording management.
        """
        # Delegate to recording controller if available
        if hasattr(self, 'recording_controller') and self.recording_controller:
            self.recording_controller.resume()
            return

        # Legacy implementation (fallback)
        try:
            # Play resume sound
            self.play_recording_sound(start=True)
            
            # Resume the recording manager
            self.recording_manager.resume_recording()
            
            # Get selected microphone name
            selected_device = self.mic_combobox.get()
            
            # Get the actual device index if using the new naming format
            from utils.utils import get_device_index_from_name
            device_index = get_device_index_from_name(selected_device)
            
            # Log the selected device information
            logging.info(f"Resuming SOAP recording with device: {selected_device} (index {device_index})")
            
            # Start new recording session
            self.soap_stop_listening_function = self.audio_handler.listen_in_background(
                mic_name=selected_device,
                callback=self.soap_callback,
                phrase_time_limit=3  # Use 3 seconds for more frequent processing
            )
            
            # Update UI
            self._update_recording_ui_state(recording=True, paused=False, caller="resume")
            self.update_status("SOAP recording resumed.", "info")
            
        except Exception as e:
            logging.error("Error resuming SOAP recording", exc_info=True)
            self.update_status(f"Error resuming SOAP recording: {str(e)}", "error")

    def soap_callback(self, audio_data) -> None:
        """Callback for SOAP note recording using SOAPAudioProcessor."""
        self.soap_audio_processor.process_soap_callback(audio_data)
                
    def cancel_soap_recording(self) -> None:
        """Cancel the current SOAP note recording without processing.

        This method delegates to the RecordingController for centralized recording management.
        """
        # Delegate to recording controller if available
        if hasattr(self, 'recording_controller') and self.recording_controller:
            self.recording_controller.cancel()
            return

        # Legacy implementation (fallback)
        if not self.soap_recording:
            return

        # Show confirmation dialog before canceling
        # Force focus to ensure keyboard shortcuts work
        self.focus_force()
        self.update()

        if not messagebox.askyesno("Cancel Recording",
                                  "Are you sure you want to cancel the current recording?\n\nAll recorded audio will be discarded.",
                                  icon="warning",
                                  parent=self):
            return  # User clicked "No", abort cancellation
            
        self.update_status("Cancelling recording...")
        
        def cancel_task():
            # Stop listening with wait_for_stop=True to ensure clean shutdown
            if self.soap_stop_listening_function:
                self.soap_stop_listening_function(True)
                
            # Wait a small additional time to ensure processing completes
            time.sleep(0.5)
                
            # Update UI on main thread
            self.after(0, lambda: [
                self._cancel_soap_recording_finalize()
            ])
            
        # Run the cancellation process in a separate thread to avoid freezing the UI
        threading.Thread(target=cancel_task, daemon=True).start()
        
        # Update status immediately
        self.update_status("Cancelling SOAP recording...", "info")
        # Disable main record button during cancellation
        main_record_btn = self.ui.components.get('main_record_button')
        if main_record_btn:
            main_record_btn.config(state=tk.DISABLED)

    def _cancel_soap_recording_finalize(self):
        """Finalize the cancellation of SOAP recording."""
        # Stop periodic analysis if running
        self._stop_periodic_analysis()
        
        # Clear content except context when cancelling
        clear_content_except_context(self)
        
        # Reset state variables
        self.soap_recording = False
        
        # Reset UI buttons
        self._update_recording_ui_state(recording=False, caller="cancel_finalize")
        
        # Update status
        self.status_manager.warning("SOAP note recording cancelled.")

    def undo_text(self) -> None:
        """Undo text operation. Delegates to TextProcessingController."""
        self.text_processing_controller.undo_text()

    def redo_text(self) -> None:
        """Redo text operation. Delegates to TextProcessingController."""
        self.text_processing_controller.redo_text()

    def on_closing(self) -> None:
        """Clean up resources and save settings before closing the application."""
        # Save window dimensions before closing
        self.save_window_dimensions()
        
        try:
            # Explicitly stop the background listener if it's running (e.g., SOAP recording)
            if hasattr(self, 'soap_stop_listening_function') and self.soap_stop_listening_function:
                logging.info("Stopping SOAP recording before exit...")
                try:
                    self.soap_stop_listening_function(True)
                    self.soap_stop_listening_function = None  # Prevent double calls
                    # Give the audio thread a moment to release resources
                    time.sleep(0.2)
                except Exception as e:
                    logging.error(f"Error stopping SOAP recording: {str(e)}", exc_info=True)
                    
            # Stop periodic analysis if running
            if hasattr(self, 'periodic_analyzer') and self.periodic_analyzer:
                logging.info("Stopping periodic analyzer...")
                try:
                    self._stop_periodic_analysis()
                except Exception as e:
                    logging.error(f"Error stopping periodic analyzer: {str(e)}", exc_info=True)
                    
            # Stop any active listening in the audio handler
            if hasattr(self, 'audio_handler'):
                logging.info("Ensuring audio handler is properly closed...")
                try:
                    self.audio_handler.cleanup_resources()
                except Exception as e:
                    logging.error(f"Error cleaning up audio handler: {str(e)}", exc_info=True)
            
            # Shutdown processing queue if it exists
            if hasattr(self, 'processing_queue') and self.processing_queue:
                logging.info("Shutting down processing queue...")
                try:
                    self.processing_queue.shutdown(wait=True)
                except Exception as e:
                    logging.error(f"Error shutting down processing queue: {str(e)}", exc_info=True)
            
            # Cleanup notification manager if it exists
            if hasattr(self, 'notification_manager') and self.notification_manager:
                logging.info("Cleaning up notification manager...")
                try:
                    self.notification_manager.cleanup()
                except Exception as e:
                    logging.error(f"Error cleaning up notification manager: {str(e)}", exc_info=True)
            
            # Shutdown MCP servers
            from ai.mcp.mcp_manager import mcp_manager
            logging.info("Shutting down MCP servers...")
            try:
                mcp_manager.stop_all()
            except Exception as e:
                logging.error(f"Error shutting down MCP servers: {str(e)}", exc_info=True)
            
            # Shutdown all executor pools properly - wait for tasks to complete
            logging.info("Shutting down executor pools...")
            for executor_name in ['io_executor', 'cpu_executor', 'executor']:
                if hasattr(self, executor_name) and getattr(self, executor_name) is not None:
                    try:
                        executor = getattr(self, executor_name)
                        logging.info(f"Shutting down {executor_name}")
                        # Use wait=True to ensure all tasks complete before closing
                        executor.shutdown(wait=True, cancel_futures=True)
                    except TypeError:
                        # Handle older Python versions without cancel_futures parameter
                        executor.shutdown(wait=True)
                    except Exception as e:
                        logging.error(f"Error shutting down {executor_name}: {str(e)}", exc_info=True)
                        
            # Final logging message before closing
            logging.info("Application shutdown complete")
            
        except Exception as e:
            logging.error(f"Error during application cleanup: {str(e)}", exc_info=True)
        
        # Destroy the window
        self.destroy()

    def on_tab_changed(self, _) -> None:
        current = self.notebook.index(self.notebook.select())
        if current == 0:
            self.active_text_widget = self.transcript_text
        elif current == 1:
            self.active_text_widget = self.soap_text
        elif current == 2:
            self.active_text_widget = self.referral_text
        elif current == 3:
            self.active_text_widget = self.letter_text
        elif current == 4:
            self.active_text_widget = self.chat_text
        elif current == 5:
            self.active_text_widget = self.context_text
        else:
            self.active_text_widget = self.transcript_text
            
        # Update chat UI context indicator
        if hasattr(self, 'chat_ui') and self.chat_ui:
            self.chat_ui.update_context_indicator()
            self._update_chat_suggestions()

    def schedule_status_update(self, delay_ms: int, message: str, status_type: str = "info") -> None:
        """Schedule a status update that won't be automatically cleared after timeout"""
        return self.status_manager.schedule_status_update(delay_ms, message, status_type)

    def create_letter(self) -> None:
        """Create a letter using DocumentGenerators."""
        self.document_generators.create_letter()
    
    def create_diagnostic_analysis(self) -> None:
        """Create a diagnostic analysis using DocumentGenerators."""
        self.document_generators.create_diagnostic_analysis()
    
    def analyze_medications(self) -> None:
        """Analyze medications using DocumentGenerators."""
        self.document_generators.analyze_medications()
    
    def extract_clinical_data(self) -> None:
        """Extract clinical data using DocumentGenerators."""
        self.document_generators.extract_clinical_data()
    
    def manage_workflow(self) -> None:
        """Manage clinical workflows using DocumentGenerators."""
        self.document_generators.manage_workflow()
    
    def open_translation_dialog(self) -> None:
        """Open the bidirectional translation dialog."""
        from ui.dialogs.translation_dialog import TranslationDialog
        
        try:
            dialog = TranslationDialog(self, self.audio_handler)
            dialog.show()
        except Exception as e:
            self.logger.error(f"Failed to open translation dialog: {e}")
            self.status_manager.error(f"Failed to open translation dialog: {str(e)}")

    

    def _save_soap_recording_to_database(self, filename: str, transcript: str, soap_note: str, 
                                        audio_path: str = "", duration: float = 0) -> None:
        """Save SOAP recording using DatabaseManager.
        
        Args:
            filename: The filename of the recorded audio
            transcript: The transcript from the recording
            soap_note: The generated SOAP note content
            audio_path: Path to the audio file (optional)
            duration: Recording duration in seconds (optional)
        """
        recording_data = {
            "transcript": transcript,
            "audio_path": audio_path or filename,
            "duration": duration,
            "soap_note": soap_note,
            "metadata": {
                "provider": SETTINGS.get("selected_stt_provider", "unknown"),
                "language": self.recognition_language,
                "filename": filename
            }
        }
        
        recording_id = self.db_manager.save_soap_recording(recording_data)
        if recording_id:
            self.current_recording_id = recording_id
        else:
            self.status_manager.error("Failed to save recording to database")

    def _on_provider_change(self, event=None):
        """Handle AI provider change. Delegates to ProviderConfigController."""
        self.provider_config_controller.on_provider_change(event)

    def _on_stt_change(self, event=None) -> None:
        """Handle STT provider change. Delegates to ProviderConfigController."""
        self.provider_config_controller.on_stt_change(event)

    def refresh_provider_dropdowns(self) -> None:
        """Refresh provider dropdowns. Delegates to ProviderConfigController."""
        self.provider_config_controller.refresh_provider_dropdowns()

    def _on_microphone_change(self, event=None) -> None:
        """Handle microphone change. Delegates to ProviderConfigController."""
        self.provider_config_controller.on_microphone_change(event)

    def on_transcription_fallback(self, primary_provider: str, fallback_provider: str) -> None:
        """Handle transcription fallback. Delegates to ProviderConfigController."""
        self.provider_config_controller.on_transcription_fallback(primary_provider, fallback_provider)

    def toggle_theme(self):
        """Toggle between light and dark themes using ThemeManager."""
        self.theme_manager.toggle_theme()
    
    def on_workflow_changed(self, workflow: str):
        """Handle workflow tab changes.
        
        Args:
            workflow: The current workflow tab ("record", "process", "generate", or "recordings")
        """
        logging.info(f"Workflow changed to: {workflow}")
        
        # Update UI based on workflow
        if workflow == "record":
            # Focus on transcript tab
            self.notebook.select(0)
        elif workflow == "process":
            # Ensure there's text to process
            if not self.transcript_text.get("1.0", tk.END).strip():
                self.status_manager.info("Load audio or paste text to process")
        elif workflow == "generate":
            # Check if we have content to generate from
            if not self.transcript_text.get("1.0", tk.END).strip():
                self.status_manager.info("No transcript available for document generation")
            else:
                # Show suggestions based on available content
                self._show_generation_suggestions()
        elif workflow == "recordings":
            # Show status when refreshing recordings
            self.status_manager.info("Refreshing recordings list...")
    
    def _update_recording_ui_state(self, recording: bool, paused: bool = False, caller: str = "unknown"):
        """Update recording UI state for workflow UI.

        This method delegates to the UIStateManager for centralized state management.

        Args:
            recording: Whether recording is active
            paused: Whether recording is paused
            caller: Identifier for debugging which code called this method
        """
        logging.info(f"_update_recording_ui_state called by {caller}: recording={recording}, paused={paused}")

        # Delegate to UI state manager if available
        if hasattr(self, 'ui_state_manager') and self.ui_state_manager:
            self.ui_state_manager.set_recording_state(recording, paused, caller)
        elif hasattr(self.ui, 'set_recording_state'):
            # Fallback to direct UI call
            self.ui.set_recording_state(recording, paused)
    
    def _show_generation_suggestions(self):
        """Show smart suggestions for document generation."""
        suggestions = []
        
        # Check what content is available
        has_transcript = bool(self.transcript_text.get("1.0", tk.END).strip())
        has_soap = bool(self.soap_text.get("1.0", tk.END).strip())
        has_referral = bool(self.referral_text.get("1.0", tk.END).strip())
        
        if has_transcript and not has_soap:
            suggestions.append("📋 Create SOAP Note from transcript")
        
        if has_soap and not has_referral:
            suggestions.append("🏥 Generate Referral from SOAP note")
        
        if has_transcript or has_soap:
            suggestions.append("✉️ Create Letter from available content")
        
        # Update suggestions in UI if available
        if hasattr(self.ui, 'show_suggestions'):
            self.ui.show_suggestions(suggestions)

    def create_referral(self) -> None:
        """Create a referral using DocumentGenerators."""
        self.document_generators.create_referral()


    def load_audio_file(self) -> None:
        """Load and transcribe audio file using FileProcessor."""
        self.file_processor.load_audio_file()

    def append_text_to_widget(self, text: str, widget: tk.Widget) -> None:
        """Append text to a widget. Delegates to TextProcessingController."""
        self.text_processing_controller.append_text_to_widget(text, widget)
        
    def show_recordings_dialog(self) -> None:
        """Show a dialog with all recordings from the database"""
        self.recordings_dialog_manager.show_dialog()
        return  # Exit early - everything handled by manager
        
    def view_logs(self) -> None:
        """Open the logs directory in file explorer or view log contents"""
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        log_file = os.path.join(log_dir, "medical_dictation.log")
        
        if not os.path.exists(log_dir):
            messagebox.showinfo("Logs", "The logs directory does not exist yet. It will be created when logs are generated.")
            return
            
        # Log that logs are being viewed
        logging.info("User accessed logs directory")

        # Create a dropdown menu for log actions
        log_menu = tk.Menu(self, tearoff=0)
        log_menu.add_command(label="Open Logs Folder", command=lambda: self._open_logs_folder(log_dir))
        log_menu.add_command(label="View Log Contents", command=lambda: self._show_log_contents(log_file))
        
        # Get the position of the mouse
        try:
            x = self.winfo_pointerx()
            y = self.winfo_pointery()
            log_menu.tk_popup(x, y)
        finally:
            # Make sure to release the grab
            log_menu.grab_release()
    
    def _show_log_contents(self, log_file):
        """Show the contents of the log file in a new window"""
        try:
            if os.path.exists(log_file):
                # Create a new top-level window
                log_window = tk.Toplevel(self)
                log_window.title("Log Contents")
                log_window.geometry("800x600")
                
                # Create text widget with scrollbar
                frame = ttk.Frame(log_window)
                frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                
                text_widget = tk.Text(frame, wrap=tk.WORD)
                scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text_widget.yview)
                text_widget.configure(yscrollcommand=scrollbar.set)
                
                text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                
                # Read and display log contents
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    text_widget.insert('1.0', content)
                    text_widget.config(state=tk.DISABLED)  # Make read-only
                
                # Add close button
                close_btn = ttk.Button(log_window, text="Close", command=log_window.destroy)
                close_btn.pack(pady=5)
            else:
                messagebox.showwarning("File Not Found", "Log file not found.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open log file: {str(e)}")
    
    def _open_logs_folder(self, log_dir):
        """Open the logs directory using file explorer"""
        try:
            from utils.validation import open_file_or_folder_safely
            success, error = open_file_or_folder_safely(log_dir, operation="open")
            if not success:
                messagebox.showerror("Error", f"Could not open logs directory: {error}")
                logging.error(f"Error opening logs directory: {error}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open logs directory: {str(e)}")
            logging.error(f"Error opening logs directory: {str(e)}")
    
    def _open_logs_folder_menu(self):
        """Wrapper method for menu to open logs folder"""
        from managers.data_folder_manager import data_folder_manager
        log_dir = str(data_folder_manager.logs_folder)
        if not os.path.exists(log_dir):
            messagebox.showinfo("Logs", "The logs directory does not exist yet. It will be created when logs are generated.")
            return
        logging.info("User accessed logs directory from menu")
        self._open_logs_folder(log_dir)
    
    def _show_log_contents_menu(self):
        """Wrapper method for menu to show log contents"""
        from managers.data_folder_manager import data_folder_manager
        log_dir = str(data_folder_manager.logs_folder)
        log_file = os.path.join(log_dir, "medical_dictation.log")
        if not os.path.exists(log_dir):
            messagebox.showinfo("Logs", "The logs directory does not exist yet. It will be created when logs are generated.")
            return
        logging.info("User viewed log contents from menu")
        self._show_log_contents(log_file)

    def on_window_configure(self, event):
        """
        Handle window configuration events.
        Only save dimensions when the window size actually changes and after resizing stops.
        """
        # Skip if this is not the main window configure event or if size hasn't changed
        if event.widget != self or (self.last_width == self.winfo_width() and self.last_height == self.winfo_height()):
            return
            
        # Update last known dimensions
        self.last_width = self.winfo_width()
        self.last_height = self.winfo_height()
        
        # Cancel previous timer if it exists
        if self.resize_timer is not None:
            self.after_cancel(self.resize_timer)
            
        # Set a new timer to save settings after resizing stops (500ms delay)
        self.resize_timer = self.after(500, self.save_window_dimensions)
    
    def save_window_dimensions(self):
        """Save the current window dimensions to settings."""
        from settings.settings import SETTINGS, save_settings
        SETTINGS["window_width"] = self.last_width
        SETTINGS["window_height"] = self.last_height
        save_settings(SETTINGS)
        # No status message needed for this automatic action
        self.resize_timer = None  # Clear the timer reference

    # Chat-related methods are provided by AppChatMixin

    def play_recording_sound(self, start=True):
        """Play a sound to indicate recording start/stop."""
        # Sound disabled - just log the event
        logging.debug(f"Recording {'started' if start else 'stopped'}")
    
    def _queue_recording_for_processing(self, recording_data: dict):
        """Queue recording for background processing."""
        try:
            # Get patient name - try to extract from context or use default
            context_text = self.context_text.get("1.0", tk.END).strip()
            patient_name = self._extract_patient_name(context_text) or "Patient"
            
            # Save to database with 'pending' status
            recording_id = self.db.add_recording(
                filename=f"queued_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3",
                processing_status='pending',
                patient_name=patient_name
            )
            
            # Get audio data from recording_data if available, otherwise use chunks
            audio_to_process = None
            if recording_data and recording_data.get('audio'):
                audio_to_process = recording_data['audio']
            elif self.combined_soap_chunks:
                audio_to_process = self.combined_soap_chunks
            else:
                raise ValueError("No audio data available for processing")
            
            # Prepare task data
            task_data = {
                'recording_id': recording_id,
                'audio_data': audio_to_process,
                'patient_name': patient_name,
                'context': context_text,
                'process_options': {
                    'generate_soap': True,
                    'generate_referral': False,
                    'generate_letter': False
                }
            }
            
            # Add to processing queue
            task_id = self.processing_queue.add_recording(task_data)
            
            # Update status
            self.status_manager.info(f"Recording for {patient_name} added to queue")
            
            logging.info(f"Queued recording {recording_id} as task {task_id}")
            
        except Exception as e:
            logging.error(f"Failed to queue recording: {str(e)}", exc_info=True)
            self.status_manager.error("Failed to queue recording for processing")
            # Fall back to immediate processing
            self.process_soap_recording()
    
    def _reset_ui_for_next_patient(self):
        """Reset UI for next patient recording."""
        # DON'T clear content here - preserve context and previous recording data
        # Content will only be cleared when starting a new recording
        
        # Reset recording state
        self.soap_recording = False
        
        # Reset UI buttons
        self._update_recording_ui_state(recording=False, caller="reset_for_next")
        
        # Focus on transcript tab
        self.notebook.select(0)
        
        # Update status
        self.status_manager.success("Ready for next patient")
    
    def _extract_patient_name(self, context_text: str) -> Optional[str]:
        """Try to extract patient name from context."""
        # Simple extraction - look for "Patient:" or "Name:" in context
        lines = context_text.split('\n')
        for line in lines:
            if line.startswith(('Patient:', 'Name:', 'Patient Name:')):
                name = line.split(':', 1)[1].strip()
                if name:
                    return name
        return None
    
    def toggle_quick_continue_mode(self):
        """Toggle the quick continue mode setting."""
        new_value = self.quick_continue_var.get()
        SETTINGS["quick_continue_mode"] = new_value
        from settings.settings import save_settings
        save_settings(SETTINGS)
        
        # Update status
        if new_value:
            self.status_manager.success("Quick Continue Mode enabled - recordings will process in background")
        else:
            self.status_manager.info("Quick Continue Mode disabled - recordings will process immediately")
        
        logging.info(f"Quick Continue Mode set to: {new_value}")
    
    def reprocess_failed_recordings(self, recording_ids: List[int]):
        """Reprocess failed recordings by re-adding them to the queue.
        
        Args:
            recording_ids: List of recording IDs to reprocess
        """
        try:
            if not hasattr(self, 'processing_queue') or not self.processing_queue:
                self.status_manager.error("Processing queue not available")
                return
            
            # Reprocess each recording
            success_count = 0
            failed_count = 0
            
            for rec_id in recording_ids:
                task_id = self.processing_queue.reprocess_failed_recording(rec_id)
                if task_id:
                    success_count += 1
                    logging.info(f"Recording {rec_id} queued for reprocessing as task {task_id}")
                else:
                    failed_count += 1
                    logging.error(f"Failed to reprocess recording {rec_id}")
            
            # Show status
            if success_count > 0:
                self.status_manager.success(f"Queued {success_count} recording{'s' if success_count > 1 else ''} for reprocessing")
            
            if failed_count > 0:
                self.status_manager.warning(f"Failed to reprocess {failed_count} recording{'s' if failed_count > 1 else ''}")
                
        except Exception as e:
            logging.error(f"Error reprocessing recordings: {str(e)}", exc_info=True)
            self.status_manager.error(f"Failed to reprocess recordings: {str(e)}")
    
    def _start_periodic_analysis(self):
        """Start periodic analysis during recording."""
        try:
            # Create periodic analyzer if not exists
            if not self.periodic_analyzer:
                self.periodic_analyzer = PeriodicAnalyzer(interval_seconds=120)  # 2 minutes
            
            # Start the periodic analysis
            self.periodic_analyzer.start(self._perform_periodic_analysis)
            logging.info("Started periodic analysis for advanced diagnosis")
            
        except Exception as e:
            logging.error(f"Failed to start periodic analysis: {e}")
            self.status_manager.error("Failed to start advanced analysis")
    
    def _stop_periodic_analysis(self):
        """Stop periodic analysis."""
        try:
            if self.periodic_analyzer and self.periodic_analyzer.is_running:
                self.periodic_analyzer.stop()
                self.periodic_analyzer = None  # Clear reference to prevent reuse
                logging.info("Stopped periodic analysis")
        except Exception as e:
            logging.error(f"Error stopping periodic analysis: {e}")
    
    def _perform_periodic_analysis(self, analysis_count: int, elapsed_time: float):
        """Perform periodic analysis callback."""
        try:
            # Get current audio segment
            audio_segment = AudioSegmentExtractor.extract_audio_segment(
                self.recording_manager,
                self.audio_state_manager
            )
            
            if not audio_segment:
                logging.warning("No audio available for periodic analysis")
                return
            
            # Transcribe the audio segment directly
            # Transcribe the audio
            self.status_manager.info(f"Transcribing for analysis #{analysis_count}...")
            transcript = self.audio_handler.transcribe_audio(audio_segment)
            
            if not transcript:
                logging.warning("No transcript generated for periodic analysis")
                return
            
            # Generate differential diagnosis
            self.status_manager.info("Generating differential diagnosis...")
            result = self.ai_processor.generate_differential_diagnosis(transcript)
            
            if result.get('success'):
                # Format and display the analysis
                formatted_time = f"{int(elapsed_time // 60)}:{int(elapsed_time % 60):02d}"
                analysis_text = (
                    f"{'='*60}\n"
                    f"Analysis #{analysis_count} at {formatted_time}\n"
                    f"{'='*60}\n\n"
                    f"{result['text']}\n\n"
                )
                
                # Update UI on main thread
                self.after(0, lambda: self._update_analysis_display(analysis_text))
                self.status_manager.success(f"Analysis #{analysis_count} completed")
            else:
                error_msg = result.get('error', 'Unknown error')
                logging.error(f"Failed to generate analysis: {error_msg}")
                self.status_manager.error("Failed to generate analysis")
                    
                    
        except Exception as e:
            logging.error(f"Error in periodic analysis: {e}")
            self.status_manager.error("Error during advanced analysis")
    
    def _update_analysis_display(self, analysis_text: str):
        """Update the analysis display in the UI."""
        try:
            if 'record_notes_text' in self.ui.components:
                # Clear existing content first
                self.ui.components['record_notes_text'].delete('1.0', tk.END)
                # Insert new analysis text
                self.ui.components['record_notes_text'].insert(tk.END, analysis_text)
                # Scroll to bottom
                self.ui.components['record_notes_text'].see(tk.END)
        except Exception as e:
            logging.error(f"Error updating analysis display: {e}")
    
    def clear_advanced_analysis_text(self) -> None:
        """Clear the Advanced Analysis Results text area."""
        try:
            if 'record_notes_text' in self.ui.components:
                self.ui.components['record_notes_text'].delete('1.0', tk.END)
                logging.info("Cleared advanced analysis text")
        except Exception as e:
            logging.error(f"Error clearing advanced analysis text: {e}")
    
        """Save voice transcript to database.
        
        Args:
            transcript: Conversation transcript
        """
        try:
            # Create a recording entry for the voice conversation
            filename = f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            recording_id = self.db.add_recording(
                filename=filename,
                transcript=transcript,
                processing_status='completed',
                patient_name="Voice Conversation"
            )
            
            logging.info(f"Saved voice transcript as recording {recording_id}")
            
        except Exception as e:
            logging.error(f"Failed to save voice transcript: {e}")

if __name__ == "__main__":
    main()
