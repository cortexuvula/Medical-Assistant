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
from tkinter import messagebox, TOP, BOTTOM, LEFT, RIGHT, NORMAL, DISABLED
import ttkbootstrap as ttk
from dotenv import load_dotenv
from managers.data_folder_manager import data_folder_manager
from managers.autosave_manager import AutoSaveManager, AutoSaveDataProvider
from typing import Callable, Optional, Dict, Any, List
import threading
from pydub import AudioSegment
from datetime import datetime
from utils.cleanup_utils import clear_all_content, clear_content_except_context
from utils.security import get_security_manager
from database.database import Database
from audio.audio import AudioHandler
from audio.periodic_analysis import PeriodicAnalyzer, AudioSegmentExtractor

# Initialize logging
from managers.log_manager import setup_application_logging
log_manager = setup_application_logging()


from utils.utils import get_valid_microphones
from settings.settings import SETTINGS, save_settings
from ui.dialogs.dialogs import show_settings_dialog, show_api_keys_dialog, show_shortcuts_dialog, show_about_dialog, show_letter_options_dialog, show_elevenlabs_settings_dialog, show_deepgram_settings_dialog, show_groq_settings_dialog
from ui.tooltip import ToolTip

import time

from core.app_initializer import AppInitializer
from core.app_settings_mixin import AppSettingsMixin
from core.app_chat_mixin import AppChatMixin
from core.navigation_controller import NavigationController
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
        security_manager = get_security_manager()
        has_any_llm = any([
            security_manager.get_api_key("openai"),
            security_manager.get_api_key("anthropic"),
            security_manager.get_api_key("gemini"),
            os.getenv("OLLAMA_API_URL")
        ])
        if has_any_llm:
            if self.refine_button:
                self.refine_button.config(state=NORMAL)
            if self.improve_button:
                self.improve_button.config(state=NORMAL)
            if self.soap_button:
                self.soap_button.config(state=NORMAL)
        else:
            if self.refine_button:
                self.refine_button.config(state=DISABLED)
            if self.improve_button:
                self.improve_button.config(state=DISABLED)
            if self.soap_button:
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

    def show_groq_settings(self) -> None:
        """Show dialog to configure Groq settings."""
        # Call the dialog function
        show_groq_settings_dialog(self)

        # Refresh the audio handler with potentially new settings
        self.audio_handler = AudioHandler(
            elevenlabs_api_key=self.elevenlabs_api_key,
            deepgram_api_key=self.deepgram_api_key,
            groq_api_key=self.groq_api_key,
            recognition_language=self.recognition_language
        )
        self.status_manager.success("Groq settings saved successfully")

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

    def import_contacts_from_csv(self) -> None:
        """Show dialog to import contacts from CSV file."""
        from ui.dialogs.import_contacts_dialog import ImportContactsDialog
        dialog = ImportContactsDialog(self)
        result = dialog.show()
        if result and result.get("imported", 0) > 0:
            # Contacts were imported successfully
            pass

    def manage_address_book(self) -> None:
        """Show dialog to manage address book contacts."""
        from ui.dialogs.manage_recipients_dialog import ManageRecipientsDialog
        dialog = ManageRecipientsDialog(self)
        dialog.show()

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
        
        # Create status bar at the bottom FIRST (so it stays at bottom)
        status_frame, self.status_icon_label, self.status_label, self.provider_indicator, self.progress_bar = self.ui.create_status_bar()
        status_frame.pack(side=BOTTOM, fill=tk.X)

        # Create main container with horizontal split (3-pane: sidebar | content | context)
        main_container = ttk.Panedwindow(self, orient="horizontal")
        main_container.pack(fill=tk.BOTH, expand=True)

        # Initialize navigation controller
        self.navigation_controller = NavigationController(self)

        # Left sidebar - navigation panel
        self.sidebar = self.ui.create_sidebar(command_map)
        main_container.add(self.sidebar, weight=0)

        # Center - main content area
        left_frame = ttk.Frame(main_container)
        main_container.add(left_frame, weight=3)
        
        # Top bar with provider settings
        top_bar = ttk.Frame(left_frame)
        top_bar.pack(side=TOP, fill=tk.X, padx=10, pady=5)

        # Provider selection frame
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
        
        # Create prominent recording header at top (matches reference design)
        self.recording_header = self.ui.create_recording_header(command_map, parent=left_frame)
        self.recording_header.pack(fill=tk.X)

        # Redirect mic_combobox to use recording header's device selector
        # This maintains compatibility with existing code that uses self.mic_combobox
        self.mic_combobox = self.ui.components.get('header_device_combo')

        # Create a vertical PanedWindow for resizable layout
        self.content_paned = ttk.Panedwindow(left_frame, orient=tk.VERTICAL)
        self.content_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 5))

        # Create the text notebook (for transcripts, SOAP, etc.)
        # SOAP tab includes split layout with medication and differential analysis panels
        (self.notebook, self.transcript_text, self.soap_text, self.referral_text,
         self.letter_text, self.chat_text, self.rag_text, _,
         self.medication_analysis_text, self.differential_analysis_text) = self.ui.create_notebook()
        self.content_paned.add(self.notebook, weight=1)

        # Bottom section frame for chat and shared panel
        bottom_section = ttk.Frame(self.content_paned)
        self.content_paned.add(bottom_section, weight=1)

        # Store references for collapsible panel coordination
        self.ui.components['content_paned'] = self.content_paned
        self.ui.components['bottom_section'] = bottom_section

        # Create header row with single collapse button for entire bottom section
        bottom_header = ttk.Frame(bottom_section)
        bottom_header.pack(fill=tk.X, padx=10, pady=(8, 5))

        # Single collapse button for both panels
        self._bottom_collapsed = SETTINGS.get("bottom_section_collapsed", False)
        collapse_icon = "▶" if self._bottom_collapsed else "▼"
        self._bottom_collapse_btn = ttk.Button(
            bottom_header,
            text=collapse_icon,
            width=3,
            bootstyle="secondary-outline",
            command=self._toggle_bottom_section
        )
        self._bottom_collapse_btn.pack(side=tk.LEFT, padx=(0, 5))

        # Title label
        bottom_title = ttk.Label(
            bottom_header,
            text="AI Assistant & Analysis",
            font=("", 10, "bold")
        )
        bottom_title.pack(side=tk.LEFT)
        self.ui.components['bottom_header'] = bottom_header

        # Create a horizontal PanedWindow inside bottom_section for chat and analysis
        # This allows both panels to be visible side by side
        bottom_paned = ttk.Panedwindow(bottom_section, orient=tk.HORIZONTAL)
        self.ui.components['bottom_paned'] = bottom_paned
        self._bottom_content = bottom_paned  # Store reference for collapse toggle

        # Only pack if not collapsed
        if not self._bottom_collapsed:
            bottom_paned.pack(fill=tk.BOTH, expand=True)

        # Create frames for each panel in the horizontal paned window
        chat_container = ttk.Frame(bottom_paned)
        analysis_container = ttk.Frame(bottom_paned)

        # Add to paned window - chat on left (smaller), analysis on right (larger)
        bottom_paned.add(chat_container, weight=1)
        bottom_paned.add(analysis_container, weight=3)

        # Create chat interface in chat container (without its own collapse button)
        self.chat_ui = ChatUI(chat_container, self, show_collapse_button=False)
        self.chat_ui.set_send_callback(self._handle_chat_message)

        # Apply initial theme to chat UI
        self.after(50, lambda: self.chat_ui.update_theme())

        # Set initial chat suggestions
        self.after(100, self._update_chat_suggestions)

        # Create shared panel (Analysis/Recordings) in analysis container
        self.shared_panel = self.ui.create_shared_panel(command_map, show_collapse_button=False)
        self.shared_panel.pack(in_=analysis_container, fill=tk.BOTH, expand=True)

        # Always adjust sash position on startup to ensure proper sizing
        # Use longer delay to ensure window is fully rendered
        self.after(500, self._adjust_bottom_sash)

        # Set horizontal sash position for Chat (25%) vs Analysis (75%)
        self.after(600, self._adjust_horizontal_sash)

        # Bind Configure event to maintain sash position on resize
        self._last_height = 0
        self.content_paned.bind('<Configure>', self._on_content_paned_configure)
        
        # Right side - context panel
        self.context_panel = self.ui.create_context_panel()
        main_container.add(self.context_panel, weight=1)
        
        # Get context text widget from UI
        self.context_text = self.ui.components['context_text']
        
        # Set initial active text widget
        self.active_text_widget = self.transcript_text
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        # Track content modifications for background update protection
        self._content_modified = {
            'transcript': False,
            'soap': False,
            'referral': False,
            'letter': False
        }
        self._current_recording_id: Optional[int] = None
        self._setup_modification_tracking()

        # Store button references for compatibility
        self._store_workflow_button_references()

        # Note: _initialize_provider_selections() and _initialize_autosave()
        # are now called from AppInitializer._finalize_ui() after controllers
        # are created, so they can properly delegate to their controllers.
    
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

    def _setup_modification_tracking(self) -> None:
        """Set up event bindings to track content modifications.

        This allows the app to protect user edits from being overwritten
        by background queue processing updates.
        """
        # Map text widgets to their modification keys
        widget_map = {
            self.transcript_text: 'transcript',
            self.soap_text: 'soap',
            self.referral_text: 'referral',
            self.letter_text: 'letter'
        }

        for widget, key in widget_map.items():
            # Bind to key press events to detect modifications
            widget.bind('<Key>', lambda e, k=key: self._on_content_modified(k))
            # Also bind to mouse button (for paste via right-click)
            widget.bind('<Button-3>', lambda e, k=key: self._on_content_modified(k))
            # Bind to Control-V for paste
            widget.bind('<Control-v>', lambda e, k=key: self._on_content_modified(k))
            widget.bind('<Control-V>', lambda e, k=key: self._on_content_modified(k))

    def _on_content_modified(self, tab_name: str) -> None:
        """Called when user modifies content in a tab.

        Args:
            tab_name: Name of the tab that was modified
        """
        self._content_modified[tab_name] = True

    def reset_content_modified(self, tab_name: Optional[str] = None) -> None:
        """Reset the content modified flag for a tab or all tabs.

        Args:
            tab_name: Specific tab to reset, or None for all tabs
        """
        if tab_name:
            self._content_modified[tab_name] = False
        else:
            for key in self._content_modified:
                self._content_modified[key] = False

    def is_content_modified(self, tab_name: str) -> bool:
        """Check if content in a tab has been modified by user.

        Args:
            tab_name: Name of the tab to check

        Returns:
            True if content was modified since last reset
        """
        return self._content_modified.get(tab_name, False)

    def can_update_tab_from_background(self, tab_name: str, recording_id: int) -> bool:
        """Check if it's safe to update a tab with background results.

        Args:
            tab_name: Name of the tab to check
            recording_id: ID of the recording being loaded

        Returns:
            True if safe to update (empty or same recording and not modified)
        """
        # Get the text widget for this tab
        widget_map = {
            'transcript': self.transcript_text,
            'soap': self.soap_text,
            'referral': self.referral_text,
            'letter': self.letter_text
        }

        widget = widget_map.get(tab_name)
        if not widget:
            return False

        # Always safe if tab is empty
        content = widget.get("1.0", "end-1c").strip()
        if not content:
            return True

        # Safe if same recording and not modified
        if (self._current_recording_id == recording_id and
            not self._content_modified.get(tab_name, False)):
            return True

        return False

    def _get_available_ai_providers(self):
        """Get list of AI providers that have API keys configured.

        Note: This method is called during create_widgets before controllers exist,
        so it cannot delegate to ProviderConfigController.
        """
        from utils.security import get_security_manager
        security_mgr = get_security_manager()

        all_providers = [
            ("openai", "OpenAI"),
            ("anthropic", "Anthropic"),
            ("gemini", "Gemini"),
        ]

        available = []
        display_names = []

        for provider_key, display_name in all_providers:
            api_key = security_mgr.get_api_key(provider_key)
            if api_key:
                available.append(provider_key)
                display_names.append(display_name)

        if not available:
            logging.warning("No AI providers have API keys configured, showing all options")
            available = [p[0] for p in all_providers]
            display_names = [p[1] for p in all_providers]

        return available, display_names

    def _get_available_stt_providers(self):
        """Get list of STT providers that have API keys configured.

        Note: This method is called during create_widgets before controllers exist,
        so it cannot delegate to ProviderConfigController.
        """
        from utils.security import get_security_manager
        security_mgr = get_security_manager()

        all_providers = [
            ("groq", "GROQ"),
            ("elevenlabs", "ElevenLabs"),
            ("deepgram", "Deepgram"),
        ]

        available = []
        display_names = []

        for provider_key, display_name in all_providers:
            api_key = security_mgr.get_api_key(provider_key)
            if api_key:
                available.append(provider_key)
                display_names.append(display_name)

        if not available:
            logging.warning("No STT providers have API keys configured, showing all options")
            available = [p[0] for p in all_providers]
            display_names = [p[1] for p in all_providers]

        return available, display_names

    def _initialize_provider_selections(self) -> None:
        """Initialize provider selections. Delegates to ProviderConfigController."""
        self.provider_config_controller.initialize_provider_selections()

    def _initialize_autosave(self) -> None:
        """Initialize auto-save functionality. Delegates to AutoSaveController."""
        self.autosave_controller.initialize_autosave()

    def _check_and_restore_autosave(self) -> None:
        """Check for existing auto-save. Delegates to AutoSaveController."""
        self.autosave_controller.check_and_restore_autosave()

    def _update_restore_button_visibility(self) -> None:
        """Update restore button visibility. Delegates to AutoSaveController."""
        self.autosave_controller.update_restore_button_visibility()

    def _restore_from_autosave(self, data: Dict[str, Any]) -> None:
        """Restore from auto-save data. Delegates to AutoSaveController."""
        self.autosave_controller.restore_from_autosave(data)

    def restore_autosave(self) -> None:
        """Manually restore from auto-save. Delegates to AutoSaveController."""
        self.autosave_controller.restore_autosave()

    def bind_shortcuts(self) -> None:
        """Bind keyboard shortcuts. Delegates to KeyboardShortcutsController."""
        self.keyboard_shortcuts_controller.bind_shortcuts()

    def _handle_space_key(self) -> None:
        """Handle space key for pause/resume. Delegates to KeyboardShortcutsController."""
        self.keyboard_shortcuts_controller.handle_space_key()

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

    def export_as_pdf_letterhead(self) -> None:
        """Export current document as PDF with letterhead. Delegates to DocumentExportController."""
        self.document_export_controller.export_as_pdf_letterhead()

    def export_as_word(self) -> None:
        """Export current document as Word document. Delegates to DocumentExportController."""
        self.document_export_controller.export_as_word()

    def export_as_fhir(self) -> None:
        """Export current document as FHIR JSON. Delegates to DocumentExportController."""
        self.document_export_controller.export_as_fhir()

    def copy_fhir_to_clipboard(self) -> None:
        """Copy current document as FHIR JSON to clipboard. Delegates to DocumentExportController."""
        self.document_export_controller.copy_fhir_to_clipboard()

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
        """Refresh microphone list. Delegates to MicrophoneController."""
        self.microphone_controller.refresh_microphones()

    def _reset_cursor_fallback(self) -> None:
        """Fallback cursor reset. Delegates to MicrophoneController."""
        self.microphone_controller.reset_cursor_fallback()


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

    def show_undo_history(self) -> None:
        """Show the undo history dialog for the active text widget."""
        from ui.dialogs.undo_history_dialog import show_undo_history_dialog

        active_widget_name = self.text_processing_controller.get_active_widget_name()

        def undo_callback() -> bool:
            """Callback to perform a single undo operation."""
            return self.text_processing_controller.undo_text()

        show_undo_history_dialog(self, active_widget_name, undo_callback)

    def on_closing(self) -> None:
        """Clean up resources before closing. Delegates to WindowStateController."""
        self.window_state_controller.on_closing()

    def _toggle_bottom_section(self) -> None:
        """Toggle collapse/expand of the entire bottom section (Chat + Analysis)."""
        self._bottom_collapsed = not self._bottom_collapsed

        # Save state to settings
        SETTINGS["bottom_section_collapsed"] = self._bottom_collapsed
        save_settings(SETTINGS)

        if self._bottom_collapsed:
            # Collapse: hide the content
            self._bottom_content.pack_forget()
            self._bottom_collapse_btn.config(text="▶")
        else:
            # Expand: show the content
            self._bottom_content.pack(fill=tk.BOTH, expand=True)
            self._bottom_collapse_btn.config(text="▼")

        # Adjust the sash position
        self._adjust_bottom_sash()

    def _on_content_paned_configure(self, event=None) -> None:
        """Handle resize events on content_paned to maintain sash proportions."""
        try:
            content_paned = self.ui.components.get('content_paned')
            if not content_paned:
                return

            new_height = content_paned.winfo_height()
            # Only adjust if height changed significantly (avoid jitter)
            if abs(new_height - self._last_height) > 20:
                self._last_height = new_height
                # Use after to debounce rapid resize events
                if hasattr(self, '_resize_after_id'):
                    self.after_cancel(self._resize_after_id)
                self._resize_after_id = self.after(50, self._adjust_bottom_sash)
        except Exception:
            pass

    def _adjust_bottom_sash(self) -> None:
        """Adjust the content_paned sash based on bottom section collapse state."""
        try:
            content_paned = self.ui.components.get('content_paned')
            if not content_paned:
                return

            content_paned.update_idletasks()
            total_height = content_paned.winfo_height()

            if total_height <= 1:
                # Window not fully rendered yet, retry later
                self.after(200, self._adjust_bottom_sash)
                return

            if self._bottom_collapsed:
                # Collapsed - just header visible (~50px for header + padding)
                new_sash_pos = total_height - 50
            else:
                # Expanded - 55% for notebook, 45% for bottom (more space for bottom panels)
                new_sash_pos = int(total_height * 0.55)

            content_paned.sashpos(0, new_sash_pos)
            self._last_height = total_height
            logging.debug(f"Set sash position: {new_sash_pos} of {total_height} (collapsed={self._bottom_collapsed})")

        except Exception as e:
            logging.debug(f"Could not adjust bottom sash: {e}")

    def _adjust_horizontal_sash(self) -> None:
        """Adjust the horizontal sash for Chat (25%) vs Analysis (75%) split."""
        try:
            bottom_paned = self.ui.components.get('bottom_paned')
            if not bottom_paned:
                return

            bottom_paned.update_idletasks()
            total_width = bottom_paned.winfo_width()

            if total_width <= 1:
                # Not rendered yet, retry
                self.after(200, self._adjust_horizontal_sash)
                return

            # Chat gets 25%, Analysis gets 75%
            sash_pos = int(total_width * 0.25)
            bottom_paned.sashpos(0, sash_pos)
            logging.debug(f"Set horizontal sash: {sash_pos} of {total_width}")

        except Exception as e:
            logging.debug(f"Could not adjust horizontal sash: {e}")

    def on_tab_changed(self, event=None) -> None:
        """Handle tab changes. Delegates to WindowStateController."""
        self.window_state_controller.on_tab_changed(event)

        # Sync sidebar navigation with the current tab
        try:
            current_tab = self.notebook.index(self.notebook.select())
            if hasattr(self, 'navigation_controller'):
                self.navigation_controller.sync_with_notebook(current_tab)
        except Exception as e:
            logging.debug(f"Error syncing navigation: {e}")

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

    def show_diagnostic_history(self) -> None:
        """Show the diagnostic analysis history dialog."""
        from ui.dialogs.diagnostic_history_dialog import DiagnosticHistoryDialog

        try:
            dialog = DiagnosticHistoryDialog(
                self,
                on_view_callback=self._view_diagnostic_analysis
            )
            dialog.show()
        except Exception as e:
            self.logger.error(f"Failed to open diagnostic history: {e}")
            self.status_manager.error(f"Failed to open diagnostic history: {str(e)}")

    def show_diagnostic_comparison(self) -> None:
        """Show the diagnostic comparison dialog for side-by-side analysis."""
        from ui.dialogs.diagnostic_comparison_dialog import DiagnosticComparisonDialog

        try:
            dialog = DiagnosticComparisonDialog(self)
            dialog.show()
        except Exception as e:
            self.logger.error(f"Failed to open diagnostic comparison: {e}")
            self.status_manager.error(f"Failed to open diagnostic comparison: {str(e)}")

    def _view_diagnostic_analysis(self, analysis: dict) -> None:
        """Callback to view a diagnostic analysis from history.

        Args:
            analysis: The analysis dictionary from database
        """
        from ui.dialogs.diagnostic_results_dialog import DiagnosticResultsDialog
        import json

        try:
            # Parse metadata - may already be a dict from _parse_analysis_row
            metadata = {}
            metadata_raw = analysis.get('metadata_json')
            if metadata_raw:
                if isinstance(metadata_raw, dict):
                    metadata = metadata_raw
                elif isinstance(metadata_raw, str):
                    try:
                        metadata = json.loads(metadata_raw)
                    except (json.JSONDecodeError, TypeError):
                        pass

            # Show in results dialog
            results_dialog = DiagnosticResultsDialog(self)
            results_dialog.show_results(
                analysis=analysis.get('result_text', ''),
                source=analysis.get('source_type', 'History'),
                metadata=metadata,
                recording_id=analysis.get('recording_id'),
                source_text=analysis.get('source_text', '')
            )
        except Exception as e:
            self.logger.error(f"Failed to view diagnostic analysis: {e}")
            self.status_manager.error(f"Failed to view analysis: {str(e)}")

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

    def show_translation_assistant(self) -> None:
        """Alias for open_translation_dialog for menu consistency."""
        self.open_translation_dialog()

    

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
        """View logs via popup menu. Delegates to LogsViewerController."""
        self.logs_viewer_controller.view_logs()

    def _show_log_contents(self, log_file: str) -> None:
        """Show log contents in a window. Delegates to LogsViewerController."""
        self.logs_viewer_controller.show_log_contents(log_file)

    def _open_logs_folder(self, log_dir: str) -> None:
        """Open logs folder in file explorer. Delegates to LogsViewerController."""
        self.logs_viewer_controller.open_logs_folder(log_dir)

    def _open_logs_folder_menu(self) -> None:
        """Menu wrapper for opening logs folder. Delegates to LogsViewerController."""
        self.logs_viewer_controller.open_logs_folder_menu()

    def _show_log_contents_menu(self) -> None:
        """Menu wrapper for showing log contents. Delegates to LogsViewerController."""
        self.logs_viewer_controller.show_log_contents_menu()

    def on_window_configure(self, event) -> None:
        """Handle window configure events. Delegates to WindowStateController."""
        # Guard against early calls before controller is initialized
        if hasattr(self, 'window_state_controller') and self.window_state_controller:
            self.window_state_controller.on_window_configure(event)

    def save_window_dimensions(self) -> None:
        """Save window dimensions. Delegates to WindowStateController."""
        self.window_state_controller.save_window_dimensions()

    # Chat-related methods are provided by AppChatMixin

    def play_recording_sound(self, start=True):
        """Play a sound to indicate recording start/stop."""
        # Sound disabled - just log the event
        logging.debug(f"Recording {'started' if start else 'stopped'}")
    
    def _queue_recording_for_processing(self, recording_data: dict) -> None:
        """Queue recording for processing. Delegates to QueueProcessingController."""
        self.queue_processing_controller.queue_recording_for_processing(recording_data)

    def _reset_ui_for_next_patient(self) -> None:
        """Reset UI for next patient. Delegates to QueueProcessingController."""
        self.queue_processing_controller.reset_ui_for_next_patient()

    def _extract_patient_name(self, context_text: str) -> Optional[str]:
        """Extract patient name from context. Delegates to QueueProcessingController."""
        return self.queue_processing_controller.extract_patient_name(context_text)

    def toggle_quick_continue_mode(self) -> None:
        """Toggle quick continue mode. Delegates to QueueProcessingController."""
        self.queue_processing_controller.toggle_quick_continue_mode()

    def reprocess_failed_recordings(self, recording_ids: List[int]) -> None:
        """Reprocess failed recordings. Delegates to QueueProcessingController."""
        self.queue_processing_controller.reprocess_failed_recordings(recording_ids)
    
    def _start_periodic_analysis(self):
        """Start periodic analysis. Delegates to PeriodicAnalysisController."""
        self.periodic_analysis_controller.start_periodic_analysis()

    def _stop_periodic_analysis(self):
        """Stop periodic analysis. Delegates to PeriodicAnalysisController."""
        self.periodic_analysis_controller.stop_periodic_analysis()

    def _perform_periodic_analysis(self, analysis_count: int, elapsed_time: float):
        """Perform periodic analysis. Delegates to PeriodicAnalysisController."""
        self.periodic_analysis_controller.perform_periodic_analysis(analysis_count, elapsed_time)

    def _update_analysis_display(self, analysis_text: str):
        """Update analysis display. Delegates to PeriodicAnalysisController."""
        self.periodic_analysis_controller.update_analysis_display(analysis_text)

    def clear_advanced_analysis_text(self) -> None:
        """Clear analysis text. Delegates to PeriodicAnalysisController."""
        self.periodic_analysis_controller.clear_advanced_analysis_text()
    
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
