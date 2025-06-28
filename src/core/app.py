# Import console suppression patch first (Windows only)
try:
    from hooks import suppress_console
except ImportError:
    pass  # Not critical if it fails

# json import removed - not needed after refactoring
from string import punctuation
import logging
import os
import sys
import concurrent.futures
import tkinter as tk
from tkinter import messagebox, filedialog
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
# Import tkinter constants for compatibility
from tkinter import TOP, BOTTOM, LEFT, RIGHT, NORMAL, DISABLED
from dotenv import load_dotenv
import openai
from managers.data_folder_manager import data_folder_manager
from typing import Callable, Optional
import threading
import numpy as np
from pydub import AudioSegment
import tempfile
from datetime import datetime
import asyncio
from utils.cleanup_utils import clear_all_content, clear_content_except_context
from database.database import Database
from audio.audio import AudioHandler
from audio.periodic_analysis import PeriodicAnalyzer, AudioSegmentExtractor

# Initialize logging
from managers.log_manager import setup_application_logging
log_manager = setup_application_logging()


# Requests is imported later if needed

from utils.utils import get_valid_microphones
from ai.ai import create_soap_note_with_openai
from settings.settings import SETTINGS
from ui.dialogs.dialogs import create_toplevel_dialog, show_settings_dialog, show_api_keys_dialog, show_shortcuts_dialog, show_about_dialog, show_letter_options_dialog, show_elevenlabs_settings_dialog, show_deepgram_settings_dialog  # Add this import
from ui.tooltip import ToolTip

# Add near the top of the file
import time

# Add these imports:
from core.app_initializer import AppInitializer
from audio.ffmpeg_utils import configure_pydub
from ui.menu_manager import MenuManager
from audio.soap_audio_processor import SOAPAudioProcessor
from ai.chat_processor import ChatProcessor
from ui.chat_ui import ChatUI

# Modify the main function to only create the app if check_api_keys returns True
def main() -> None:
    """Main function to start the application."""
    # Configure FFmpeg paths before anything else
    configure_pydub()
    
    # Load environment variables from .env file
    load_dotenv(dotenv_path=str(data_folder_manager.env_file_path))
    
    # Log application startup
    logging.info("Medical Dictation application starting")
    
    # Check for .env file
    # Commented out to skip API key dialog
    # if not check_api_keys():
    #     return
        
    # Create and start main app
    app = MedicalDictationApp()
    
    # Configure exception handler to log uncaught exceptions
    def handle_exception(exc_type, exc_value, exc_traceback):
        try:
            # Try to log the error
            logging.error(f"Uncaught exception: type: {exc_type}")
        except:
            # If logging fails, just print to stderr
            logging.debug(f"Error: {exc_type.__name__}: {exc_value}", file=sys.stderr)
        
        # Don't show popup for TclErrors - these are usually harmless UI timing issues
        if exc_type.__name__ != "TclError":
            # Show error message to user for other types of errors
            try:
                messagebox.showerror("Error", f"An unexpected error occurred:\n{exc_type.__name__}: {str(exc_value)}")
            except:
                pass
    
    # Set exception handler for uncaught exceptions - bind to the app instance
    app.report_callback_exception = lambda exc_type, exc_value, exc_tb: handle_exception(exc_type, exc_value, exc_tb)
    
    # Start the app
    app.mainloop()
    
    # Log application shutdown
    logging.info("Medical Dictation application shutting down")

class MedicalDictationApp(ttk.Window):
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
        
        ttk.Label(provider_frame, text="AI:").pack(side=LEFT, padx=(10, 5))
        self.provider_combobox = ttk.Combobox(
            provider_frame, 
            values=["OpenAI", "Grok", "Perplexity", "Anthropic"],
            state="readonly",
            width=12
        )
        self.provider_combobox.pack(side=LEFT)
        self.provider_combobox.bind("<<ComboboxSelected>>", self._on_provider_change)
        
        ttk.Label(provider_frame, text="STT:").pack(side=LEFT, padx=(10, 5))
        self.stt_combobox = ttk.Combobox(
            provider_frame,
            values=["GROQ", "ElevenLabs", "Deepgram"],
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
        
        # Create workflow tabs
        self.workflow_notebook = self.ui.create_workflow_tabs(command_map)
        self.workflow_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 2))
        
        # Create the text notebook (for transcripts, SOAP, etc.)
        self.notebook, self.transcript_text, self.soap_text, self.referral_text, self.letter_text, self.chat_text, _ = self.ui.create_notebook()
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
    
    def _initialize_provider_selections(self):
        """Initialize provider dropdown selections."""
        # Set AI provider
        ai_provider = SETTINGS.get("ai_provider", "openai")
        provider_map = {"openai": 0, "grok": 1, "perplexity": 2}
        if ai_provider in provider_map:
            self.provider_combobox.current(provider_map[ai_provider])
        
        # Set STT provider
        stt_provider = SETTINGS.get("stt_provider", "groq")
        stt_map = {"groq": 0, "elevenlabs": 1, "deepgram": 2}
        if stt_provider in stt_map:
            self.stt_combobox.current(stt_map[stt_provider])

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

    def show_refine_settings_dialog(self) -> None:
        from settings.settings import SETTINGS, _DEFAULT_SETTINGS
        from ai.prompts import REFINE_PROMPT, REFINE_SYSTEM_MESSAGE
        cfg = SETTINGS.get("refine_text", {})
        show_settings_dialog(
            parent=self,
            title="Refine Text Settings",
            config=cfg,
            default=_DEFAULT_SETTINGS["refine_text"],
            current_prompt=cfg.get("prompt", REFINE_PROMPT),
            current_model=cfg.get("model", _DEFAULT_SETTINGS["refine_text"].get("model", "gpt-3.5-turbo")),
            current_perplexity=cfg.get("perplexity_model", _DEFAULT_SETTINGS["refine_text"].get("perplexity_model", "sonar-reasoning-pro")),
            current_grok=cfg.get("grok_model", _DEFAULT_SETTINGS["refine_text"].get("grok_model", "grok-1")),
            save_callback=self.save_refine_settings,
            current_ollama=cfg.get("ollama_model", _DEFAULT_SETTINGS["refine_text"].get("ollama_model", "llama3")),
            current_system_prompt=cfg.get("system_message", REFINE_SYSTEM_MESSAGE),
            current_anthropic=cfg.get("anthropic_model", _DEFAULT_SETTINGS["refine_text"].get("anthropic_model", "claude-3-sonnet-20240229"))
        )

    def show_improve_settings_dialog(self) -> None:
        from settings.settings import SETTINGS, _DEFAULT_SETTINGS
        from ai.prompts import IMPROVE_PROMPT, IMPROVE_SYSTEM_MESSAGE
        cfg = SETTINGS.get("improve_text", {})
        show_settings_dialog(
            parent=self,
            title="Improve Text Settings",
            config=cfg,
            default=_DEFAULT_SETTINGS["improve_text"],
            current_prompt=cfg.get("prompt", IMPROVE_PROMPT),
            current_model=cfg.get("model", _DEFAULT_SETTINGS["improve_text"].get("model", "gpt-3.5-turbo")),
            current_perplexity=cfg.get("perplexity_model", _DEFAULT_SETTINGS["improve_text"].get("perplexity_model", "sonar-reasoning-pro")),
            current_grok=cfg.get("grok_model", _DEFAULT_SETTINGS["improve_text"].get("grok_model", "grok-1")),
            save_callback=self.save_improve_settings,
            current_ollama=cfg.get("ollama_model", _DEFAULT_SETTINGS["improve_text"].get("ollama_model", "llama3")),
            current_system_prompt=cfg.get("system_message", IMPROVE_SYSTEM_MESSAGE),
            current_anthropic=cfg.get("anthropic_model", _DEFAULT_SETTINGS["improve_text"].get("anthropic_model", "claude-3-sonnet-20240229"))
        )

    def show_soap_settings_dialog(self) -> None:
        from settings.settings import SETTINGS, _DEFAULT_SETTINGS
        from ai.prompts import SOAP_PROMPT_TEMPLATE, SOAP_SYSTEM_MESSAGE
        cfg = SETTINGS.get("soap_note", {})
        default_system_prompt = _DEFAULT_SETTINGS["soap_note"].get("system_message", SOAP_SYSTEM_MESSAGE)
        default_model = _DEFAULT_SETTINGS["soap_note"].get("model", "")
        show_settings_dialog(
            parent=self,
            title="SOAP Note Settings",
            config=cfg,
            default=_DEFAULT_SETTINGS["soap_note"],
            current_prompt=cfg.get("prompt", SOAP_PROMPT_TEMPLATE),
            current_model=cfg.get("model", default_model),
            current_perplexity=cfg.get("perplexity_model", _DEFAULT_SETTINGS["soap_note"].get("perplexity_model", "sonar-reasoning-pro")),
            current_grok=cfg.get("grok_model", _DEFAULT_SETTINGS["soap_note"].get("grok_model", "grok-1")),
            save_callback=self.save_soap_settings,
            current_ollama=cfg.get("ollama_model", _DEFAULT_SETTINGS["soap_note"].get("ollama_model", "llama3")),
            current_system_prompt=cfg.get("system_message", default_system_prompt),
            current_anthropic=cfg.get("anthropic_model", _DEFAULT_SETTINGS["soap_note"].get("anthropic_model", "claude-3-sonnet-20240229"))
        )

    def show_referral_settings_dialog(self) -> None:
        from settings.settings import SETTINGS, _DEFAULT_SETTINGS
        cfg = SETTINGS.get("referral", {})
        default_prompt = _DEFAULT_SETTINGS["referral"].get("prompt", "")
        default_system_prompt = _DEFAULT_SETTINGS["referral"].get("system_message", "")
        default_model = _DEFAULT_SETTINGS["referral"].get("model", "")
        show_settings_dialog(
            parent=self,
            title="Referral Prompt Settings",
            config=cfg,
            default=_DEFAULT_SETTINGS["referral"],
            current_prompt=cfg.get("prompt", default_prompt),
            current_model=cfg.get("model", default_model),
            current_perplexity=cfg.get("perplexity_model", _DEFAULT_SETTINGS["referral"].get("perplexity_model", "sonar-reasoning-pro")),
            current_grok=cfg.get("grok_model", _DEFAULT_SETTINGS["referral"].get("grok_model", "grok-1")),
            save_callback=self.save_referral_settings,
            current_ollama=cfg.get("ollama_model", _DEFAULT_SETTINGS["referral"].get("ollama_model", "llama3")),
            current_system_prompt=cfg.get("system_message", default_system_prompt),
            current_anthropic=cfg.get("anthropic_model", _DEFAULT_SETTINGS["referral"].get("anthropic_model", "claude-3-sonnet-20240229"))
        )

    def show_advanced_analysis_settings_dialog(self) -> None:
        from settings.settings import SETTINGS, _DEFAULT_SETTINGS
        cfg = SETTINGS.get("advanced_analysis", {})
        default_prompt = _DEFAULT_SETTINGS["advanced_analysis"].get("prompt", "")
        default_system_prompt = _DEFAULT_SETTINGS["advanced_analysis"].get("system_message", "")
        default_model = _DEFAULT_SETTINGS["advanced_analysis"].get("model", "")
        show_settings_dialog(
            parent=self,
            title="Advanced Analysis Settings",
            config=cfg,
            default=_DEFAULT_SETTINGS["advanced_analysis"],
            current_prompt=cfg.get("prompt", default_prompt),
            current_model=cfg.get("model", default_model),
            current_perplexity=cfg.get("perplexity_model", _DEFAULT_SETTINGS["advanced_analysis"].get("perplexity_model", "sonar-reasoning-pro")),
            current_grok=cfg.get("grok_model", _DEFAULT_SETTINGS["advanced_analysis"].get("grok_model", "grok-1")),
            save_callback=self.save_advanced_analysis_settings,
            current_ollama=cfg.get("ollama_model", _DEFAULT_SETTINGS["advanced_analysis"].get("ollama_model", "llama3")),
            current_system_prompt=cfg.get("system_message", default_system_prompt),
            current_anthropic=cfg.get("anthropic_model", _DEFAULT_SETTINGS["advanced_analysis"].get("anthropic_model", "claude-3-sonnet-20240229"))
        )

    def show_temperature_settings(self) -> None:
        """Show dialog to configure temperature settings for each AI provider."""
        from ui.dialogs.temperature_dialog import show_temperature_settings_dialog
        show_temperature_settings_dialog(self)
        self.status_manager.success("Temperature settings saved successfully")

    def show_agent_settings(self) -> None:
        """Show dialog to configure AI agent settings."""
        # Check if advanced settings should be shown based on a setting or default to basic
        from settings.settings import SETTINGS
        use_advanced = SETTINGS.get("use_advanced_agent_settings", True)
        
        try:
            if use_advanced:
                from ui.dialogs.advanced_agent_settings_dialog import show_advanced_agent_settings_dialog
                show_advanced_agent_settings_dialog(self)
            else:
                from ui.dialogs.agent_settings_dialog import show_agent_settings_dialog
                show_agent_settings_dialog(self)
                
            # Reload agents after settings change
            from managers.agent_manager import agent_manager
            agent_manager.reload_agents()
            
            self.status_manager.success("Agent settings saved successfully")
        except Exception as e:
            # Fall back to basic dialog on error
            logger.error(f"Error showing agent settings dialog: {e}", exc_info=True)
            try:
                from ui.dialogs.agent_settings_dialog import show_agent_settings_dialog
                show_agent_settings_dialog(self)
                self.status_manager.warning("Showing basic agent settings due to error")
            except Exception as e2:
                logger.error(f"Error showing basic dialog: {e2}", exc_info=True)
                self.status_manager.error("Failed to show agent settings dialog")

    def save_refine_settings(self, prompt: str, openai_model: str, perplexity_model: str, grok_model: str, ollama_model: str, system_prompt: str, anthropic_model: str) -> None:
        from settings.settings import save_settings, SETTINGS
        SETTINGS["refine_text"] = {
            "prompt": prompt,
            "system_message": system_prompt,
            "model": openai_model,
            "perplexity_model": perplexity_model,
            "grok_model": grok_model,
            "ollama_model": ollama_model,
            "anthropic_model": anthropic_model
        }
        save_settings(SETTINGS)
        self.status_manager.success("Refine text settings saved successfully")

    def save_improve_settings(self, prompt: str, openai_model: str, perplexity_model: str, grok_model: str, ollama_model: str, system_prompt: str, anthropic_model: str) -> None:
        from settings.settings import save_settings, SETTINGS
        SETTINGS["improve_text"] = {
            "prompt": prompt,
            "system_message": system_prompt,
            "model": openai_model,
            "perplexity_model": perplexity_model,
            "grok_model": grok_model,
            "ollama_model": ollama_model,
            "anthropic_model": anthropic_model
        }
        save_settings(SETTINGS)
        self.status_manager.success("Improve text settings saved successfully")

    def save_soap_settings(self, prompt: str, openai_model: str, perplexity_model: str, grok_model: str, ollama_model: str, system_prompt: str, anthropic_model: str) -> None:
        from settings.settings import save_settings, SETTINGS
        # Preserve existing temperature settings
        SETTINGS["soap_note"]["prompt"] = prompt
        SETTINGS["soap_note"]["system_message"] = system_prompt
        SETTINGS["soap_note"]["model"] = openai_model
        SETTINGS["soap_note"]["perplexity_model"] = perplexity_model
        SETTINGS["soap_note"]["grok_model"] = grok_model
        SETTINGS["soap_note"]["ollama_model"] = ollama_model
        SETTINGS["soap_note"]["anthropic_model"] = anthropic_model
        save_settings(SETTINGS)
        self.status_manager.success("SOAP note settings saved successfully")

    def save_referral_settings(self, prompt: str, openai_model: str, perplexity_model: str, grok_model: str, ollama_model: str, system_prompt: str, anthropic_model: str) -> None:
        from settings.settings import save_settings, SETTINGS
        # Preserve existing temperature settings
        SETTINGS["referral"]["prompt"] = prompt
        SETTINGS["referral"]["system_message"] = system_prompt
        SETTINGS["referral"]["model"] = openai_model
        SETTINGS["referral"]["perplexity_model"] = perplexity_model
        SETTINGS["referral"]["grok_model"] = grok_model
        SETTINGS["referral"]["ollama_model"] = ollama_model
        SETTINGS["referral"]["anthropic_model"] = anthropic_model
        save_settings(SETTINGS)
        self.status_manager.success("Referral settings saved successfully")

    def save_advanced_analysis_settings(self, prompt: str, openai_model: str, perplexity_model: str, grok_model: str, ollama_model: str, system_prompt: str, anthropic_model: str) -> None:
        from settings.settings import save_settings, SETTINGS
        # Preserve existing temperature settings
        SETTINGS["advanced_analysis"]["prompt"] = prompt
        SETTINGS["advanced_analysis"]["system_message"] = system_prompt
        SETTINGS["advanced_analysis"]["model"] = openai_model
        SETTINGS["advanced_analysis"]["perplexity_model"] = perplexity_model
        SETTINGS["advanced_analysis"]["grok_model"] = grok_model
        SETTINGS["advanced_analysis"]["ollama_model"] = ollama_model
        SETTINGS["advanced_analysis"]["anthropic_model"] = anthropic_model
        save_settings(SETTINGS)
        self.status_manager.success("Advanced analysis settings saved successfully")

    def show_voice_mode_settings(self) -> None:
        """Show dialog to configure voice mode settings."""
        from settings.settings import SETTINGS
        from ui.dialogs.dialogs import show_voice_mode_settings_dialog
        
        # Get current voice mode configuration
        voice_config = SETTINGS.get("voice_mode", {})
        
        # Show the dialog
        show_voice_mode_settings_dialog(self, voice_config, self.save_voice_mode_settings)

    def save_voice_mode_settings(self, ai_provider: str, ai_model: str, ai_temperature: float,
                                 system_prompt: str, tts_provider: str, tts_voice: str,
                                 enable_interruptions: bool, openai_model: str, perplexity_model: str,
                                 grok_model: str, ollama_model: str, anthropic_model: str) -> None:
        """Save voice mode settings to configuration."""
        from settings.settings import save_settings, SETTINGS
        
        # Update voice mode settings
        SETTINGS["voice_mode"] = {
            "ai_provider": ai_provider,
            "ai_model": ai_model,
            "ai_temperature": ai_temperature,
            "system_prompt": system_prompt,
            "tts_provider": tts_provider,
            "tts_voice": tts_voice,
            "stt_provider": SETTINGS.get("voice_mode", {}).get("stt_provider", "deepgram"),
            "enable_interruptions": enable_interruptions,
            "response_delay_ms": SETTINGS.get("voice_mode", {}).get("response_delay_ms", 500),
            "max_context_length": SETTINGS.get("voice_mode", {}).get("max_context_length", 4000),
            "openai_model": openai_model,
            "grok_model": grok_model,
            "perplexity_model": perplexity_model,
            "ollama_model": ollama_model,
            "anthropic_model": anthropic_model,
            "openai_temperature": ai_temperature if ai_provider == "openai" else SETTINGS.get("voice_mode", {}).get("openai_temperature", 0.7),
            "grok_temperature": ai_temperature if ai_provider == "grok" else SETTINGS.get("voice_mode", {}).get("grok_temperature", 0.7),
            "perplexity_temperature": ai_temperature if ai_provider == "perplexity" else SETTINGS.get("voice_mode", {}).get("perplexity_temperature", 0.7),
            "ollama_temperature": ai_temperature if ai_provider == "ollama" else SETTINGS.get("voice_mode", {}).get("ollama_temperature", 0.7),
            "anthropic_temperature": ai_temperature if ai_provider == "anthropic" else SETTINGS.get("voice_mode", {}).get("anthropic_temperature", 0.7)
        }
        
        # Save settings
        save_settings(SETTINGS)
        self.status_manager.success("Voice mode settings saved successfully")

    def new_session(self) -> None:
        if messagebox.askyesno("New Dictation", "Start a new session? Unsaved changes will be lost."):
            clear_all_content(self)


    def save_text(self) -> None:
        """Save text using FileManager."""
        text = self.transcript_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Save Text", "No text to save.")
            return
        
        # Save text file
        file_path = self.file_manager.save_text_file(text, "Save Transcript")
        
        if file_path and self.audio_segments:
            # Also save audio if available
            audio_data = self.audio_handler.combine_audio_segments(self.audio_segments)
            if audio_data:
                # audio_path = file_path.replace('.txt', '.mp3')  # Not used after refactoring
                saved_audio_path = self.file_manager.save_audio_file(audio_data, "Save Audio")
                if saved_audio_path:
                    self.status_manager.success("Text and audio saved successfully")
                else:
                    self.status_manager.warning("Text saved, but audio save was cancelled")
        elif file_path:
            self.status_manager.success("Text saved successfully")

    def copy_text(self) -> None:
        active_widget = self.get_active_text_widget()
        self.clipboard_clear()
        self.clipboard_append(active_widget.get("1.0", tk.END))
        self.update_status("Text copied to clipboard.")

    def clear_text(self) -> None:
        if messagebox.askyesno("Clear Text", "Clear the text?"):
            self.transcript_text.delete("1.0", tk.END)
            self.text_chunks.clear()
            self.audio_segments.clear()

    def append_text(self, text: str) -> None:
        current = self.transcript_text.get("1.0", "end-1c")
        if (self.capitalize_next or not current or current[-1] in ".!?") and text:
            text = text[0].upper() + text[1:]
            self.capitalize_next = False
        self.transcript_text.insert(tk.END, (" " if current and current[-1] != "\n" else "") + text)
        self.text_chunks.append(f"chunk_{len(self.text_chunks)}")
        self.transcript_text.see(tk.END)

    def scratch_that(self) -> None:
        if not self.text_chunks:
            self.update_status("Nothing to scratch.")
            return
        tag = self.text_chunks.pop()
        ranges = self.transcript_text.tag_ranges(tag)
        if ranges:
            self.transcript_text.delete(ranges[0], ranges[1])
            self.transcript_text.tag_delete(tag)
            self.update_status("Last added text removed.")
        else:
            self.update_status("No tagged text found.")

    def delete_last_word(self) -> None:
        current = self.transcript_text.get("1.0", "end-1c")
        if current:
            words = current.split()
            self.transcript_text.delete("1.0", tk.END)
            self.transcript_text.insert(tk.END, " ".join(words[:-1]))
            self.transcript_text.see(tk.END)

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
        text = target_widget.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Process Text", "There is no text to process.")
            return
        self.status_manager.progress("Processing text...")
        button.config(state=DISABLED)
        self.progress_bar.pack(side=RIGHT, padx=10)
        self.progress_bar.start()
        
        def task() -> None:
            try:
                # Use IO executor for the AI API call (I/O-bound operation)
                result_future = self.io_executor.submit(api_func, text)
                # Get result with timeout to prevent hanging
                result = result_future.result(timeout=60) # Add timeout to prevent hanging
                
                # Schedule UI update on the main thread
                self.after(0, lambda: self._update_text_area(result, success_message, button, target_widget))
            except concurrent.futures.TimeoutError:
                self.after(0, lambda: [
                    self.status_manager.error("AI processing timed out. Please try again."),
                    button.config(state=NORMAL),
                    self.progress_bar.stop(),
                    self.progress_bar.pack_forget()
                ])
            except Exception as e:
                error_msg = f"Error processing text: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.after(0, lambda: [
                    self.status_manager.error(error_msg),
                    button.config(state=NORMAL),
                    self.progress_bar.stop(),
                    self.progress_bar.pack_forget()
                ])

        # Use I/O executor for the task since it involves UI coordination
        self.executor.submit(task)

    def _update_text_area(self, new_text: str, success_message: str, button: ttk.Button, target_widget: tk.Widget) -> None:
        target_widget.edit_separator()
        target_widget.delete("1.0", tk.END)
        target_widget.insert(tk.END, new_text)
        target_widget.edit_separator()
        
        # Update database if we have a current recording and this is one of the main content areas
        if self.current_recording_id is not None:
            try:
                # Determine which field to update based on the target widget
                field_name = None
                if target_widget == self.soap_text:
                    field_name = 'soap_note'
                elif target_widget == self.referral_text:
                    field_name = 'referral'
                elif target_widget == self.letter_text:
                    field_name = 'letter'
                elif target_widget == self.transcript_text:
                    field_name = 'transcript'
                elif target_widget == self.chat_text:
                    field_name = 'chat'
                
                # Update database if we identified a field to update
                if field_name:
                    # Create kwargs dictionary with just the field to update
                    update_kwargs = {field_name: new_text}
                    
                    # Update the database
                    if self.db.update_recording(self.current_recording_id, **update_kwargs):
                        logging.info(f"Updated recording ID {self.current_recording_id} with new {field_name}")
                        # Add database update confirmation to success message
                        success_message = f"{success_message} and saved to database"
                    else:
                        logging.warning(f"Failed to update recording ID {self.current_recording_id} with {field_name}")
            except Exception as e:
                logging.error(f"Error updating database: {str(e)}", exc_info=True)
        
        self.status_manager.success(success_message)
        button.config(state=NORMAL)
        self.status_manager.show_progress(False)

    def get_active_text_widget(self) -> tk.Widget:
        # Get the currently selected tab index
        selected_tab = self.notebook.index('current')
        
        # Return the appropriate text widget based on the selected tab
        if selected_tab == 0:  # Transcript tab
            return self.transcript_text
        elif selected_tab == 1:  # SOAP Note tab
            return self.soap_text
        elif selected_tab == 2:  # Referral tab
            return self.referral_text
        elif selected_tab == 3:  # Letter tab
            return self.letter_text
        else:
            # Default to transcript text if for some reason we can't determine the active tab
            return self.transcript_text


    def refine_text(self) -> None:
        """Refine text using AI processor."""
        active_widget = self.get_active_text_widget()
        text = active_widget.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Empty Text", "Please add text before refining.")
            return
        
        # Show progress
        self.status_manager.progress("Refining text...")
        self.refine_button.config(state=DISABLED)
        self.progress_bar.pack(side=RIGHT, padx=10)
        self.progress_bar.start()
        
        def task():
            # Use AI processor
            result = self.ai_processor.refine_text(text)
            
            # Update UI on main thread
            self.after(0, lambda: self._handle_ai_result(result, "refine", active_widget))
        
        # Run in background
        self.io_executor.submit(task)

    def improve_text(self) -> None:
        """Improve text using AI processor."""
        active_widget = self.get_active_text_widget()
        text = active_widget.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Empty Text", "Please add text before improving.")
            return
        
        # Show progress
        self.status_manager.progress("Improving text...")
        self.improve_button.config(state=DISABLED)
        self.progress_bar.pack(side=RIGHT, padx=10)
        self.progress_bar.start()
        
        def task():
            # Use AI processor
            result = self.ai_processor.improve_text(text)
            
            # Update UI on main thread
            self.after(0, lambda: self._handle_ai_result(result, "improve", active_widget))
        
        # Run in background
        self.io_executor.submit(task)

    def _handle_ai_result(self, result: dict, operation: str, widget: tk.Widget):
        """Handle AI processing result."""
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        
        if result["success"]:
            # Update text widget
            widget.delete("1.0", tk.END)
            widget.insert("1.0", result["text"])
            self.status_manager.success(f"Text {operation}d successfully")
        else:
            self.status_manager.error(f"Failed to {operation} text: {result['error']}")
        
        # Re-enable button
        if operation == "refine":
            self.refine_button.config(state=NORMAL)
        elif operation == "improve":
            self.improve_button.config(state=NORMAL)

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
        except:
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
                    
            except Exception:
                logging.error("Error refreshing microphones", exc_info=True)
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
                except:
                    pass
        
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
                except:
                    try:
                        self.config(cursor="arrow")
                    except:
                        pass
                # Re-enable refresh button
                refresh_btn = self.ui.components.get('refresh_btn')
                if refresh_btn:
                    refresh_btn.config(text="⟳", state=tk.NORMAL)
        except Exception as e:
            logging.error(f"Error in cursor reset fallback: {e}")


    def toggle_soap_recording(self) -> None:
        """Toggle SOAP recording using RecordingManager."""
        if not self.recording_manager.is_recording:
            # Switch focus to the SOAP tab
            self.notebook.select(1)
            
            # Clear all text fields and audio segments before starting a new recording (including context)
            clear_all_content(self)
            
            # Start recording
            self.status_manager.info("Starting SOAP recording...")
            
            # Get selected device
            selected_device = self.mic_combobox.get()
            
            # Set up audio handler for SOAP mode
            self.audio_handler.soap_mode = True
            self.audio_handler.silence_threshold = 0.0001  # Much lower for SOAP recording
            
            # Start recording with callback
            if self.recording_manager.start_recording(self.soap_callback):
                # Only update UI state AFTER recording successfully starts
                # Use after() to ensure UI update happens on next event loop cycle
                self.after(0, lambda: self._update_recording_ui_state(recording=True, caller="toggle_start"))
                self.play_recording_sound(start=True)
                # Store the stop function for pause/cancel functionality
                self.soap_stop_listening_function = self.audio_handler.listen_in_background(
                    mic_name=selected_device,
                    callback=self.soap_callback,
                    phrase_time_limit=3
                )
                self.soap_recording = True
                logging.info("SOAP recording started successfully - UI updated")
                
                # Clear the analysis text area (always clear it when starting a new recording)
                if 'record_notes_text' in self.ui.components:
                    self.ui.components['record_notes_text'].delete("1.0", tk.END)
                    
                    # Check if Advanced Analysis is enabled
                    if hasattr(self.ui, 'advanced_analysis_var') and self.ui.advanced_analysis_var.get():
                        self.ui.components['record_notes_text'].insert("1.0", 
                            "Advanced Analysis enabled. First analysis will appear after 2 minutes...\n\n")
                        
                        # Start periodic analysis
                        self._start_periodic_analysis()
            else:
                self.status_manager.error("Failed to start recording")
                # Ensure UI stays in idle state if recording failed to start
                self._update_recording_ui_state(recording=False, caller="toggle_start_failed")
        else:
            # Stop recording
            self.status_manager.info("Stopping SOAP recording...")
            # Temporarily disable the record button during stop process
            main_record_btn = self.ui.components.get('main_record_button')
            if main_record_btn:
                main_record_btn.config(state=tk.DISABLED)
            
            # Stop the background listening
            if self.soap_stop_listening_function:
                self.soap_stop_listening_function()
                self.soap_stop_listening_function = None
            
            # Stop periodic analysis if running
            self._stop_periodic_analysis()
            
            # Reset audio handler settings
            self.audio_handler.soap_mode = False
            self.audio_handler.silence_threshold = 0.001  # Reset to normal
            
            # Stop and get recording data
            recording_data = self.recording_manager.stop_recording()
            if recording_data:
                self.play_recording_sound(start=False)
                self.soap_recording = False
                self._finalize_soap_recording(recording_data)
            else:
                self.status_manager.error("No recording data available")
                self._update_recording_ui_state(recording=False, caller="toggle_stop_no_data")
                self.soap_recording = False

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
        else:
            # Current behavior - process immediately
            self.process_soap_recording()
            # Reset all button states after processing is complete
            self.after(0, lambda: self._update_recording_ui_state(recording=False, caller="finalize_delayed"))


    def toggle_soap_pause(self) -> None:
        """Toggle pause for SOAP recording."""
        if self.soap_recording:
            if self.soap_stop_listening_function:
                # Currently recording, so pause
                self.pause_soap_recording()
            else:
                # Currently paused, so resume
                self.resume_soap_recording()

    def pause_soap_recording(self) -> None:
        """Pause SOAP recording."""
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
        """Resume SOAP recording after pause using the selected microphone."""
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
        """Cancel the current SOAP note recording without processing."""
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
        try:
            widget = self.get_active_text_widget()
            widget.edit_undo()
            self.update_status("Undo performed.")
        except Exception:
            self.update_status("Nothing to undo.")

    def redo_text(self) -> None:
        try:
            widget = self.get_active_text_widget()
            widget.edit_redo()
            self.update_status("Redo performed.")
        except Exception:
            self.update_status("Nothing to redo.")

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

    def _on_provider_change(self, _):
        from settings.settings import SETTINGS, save_settings  # Import locally if preferred
        
        selected_index = self.provider_combobox.current()
        providers = ["openai", "grok", "perplexity", "anthropic"]
        provider_display = ["OpenAI", "Grok", "Perplexity", "Anthropic"]
        
        if 0 <= selected_index < len(providers):
            selected_provider = providers[selected_index]
            SETTINGS["ai_provider"] = selected_provider
            save_settings(SETTINGS)
            self.update_status(f"AI Provider set to {provider_display[selected_index]}")

    def _on_stt_change(self, _) -> None:
        """Update STT provider when dropdown selection changes."""
        selected_index = self.stt_combobox.current()
        if selected_index >= 0:
            # Map display values to actual provider values
            stt_providers = ["groq", "elevenlabs", "deepgram"]
            stt_display = ["GROQ", "ElevenLabs", "Deepgram"]
            
            # Update settings
            provider = stt_providers[selected_index]
            from settings.settings import SETTINGS, save_settings
            SETTINGS["stt_provider"] = provider
            save_settings(SETTINGS)
            
            # Update the audio handler with the new provider
            self.audio_handler.set_stt_provider(provider)
            
            # Update status with the new provider info
            self.status_manager.update_provider_info()
            self.update_status(f"Speech-to-Text provider set to {stt_display[selected_index]}")

    def _on_microphone_change(self, _) -> None:
        """Save the selected microphone to settings."""
        selected_mic = self.mic_combobox.get()
        if selected_mic and selected_mic != "No microphones found":
            # Update the settings with the selected microphone
            from settings.settings import SETTINGS, save_settings
            SETTINGS["selected_microphone"] = selected_mic
            save_settings(SETTINGS)
            logging.info(f"Saved selected microphone: {selected_mic}")
    
    # Handle notification of transcription service fallback.
    #     
    def on_transcription_fallback(self, primary_provider: str, fallback_provider: str) -> None:
        """Handle notification of transcription service fallback.
        
        Args:
            primary_provider: Name of the primary provider that failed
            fallback_provider: Name of the fallback provider being used
        """
        # Create readable provider names for display
        provider_names = {
            "elevenlabs": "ElevenLabs",
            "deepgram": "Deepgram",
            "groq": "GROQ",
            "google": "Google"
        }
        
        primary_display = provider_names.get(primary_provider, primary_provider)
        fallback_display = provider_names.get(fallback_provider, fallback_provider)
        
        # Update status with warning about fallback
        message = f"{primary_display} transcription failed. Falling back to {fallback_display}."
        
        # Update STT provider dropdown to reflect actual service being used
        try:
            stt_providers = ["groq", "elevenlabs", "deepgram"]
            fallback_index = stt_providers.index(fallback_provider)
            self.after(0, lambda: [
                self.status_manager.warning(message),
                self.stt_combobox.current(fallback_index)
            ])
        except (ValueError, IndexError):
            # Just show the warning if we can't update the dropdown
            self.after(0, lambda: self.status_manager.warning(message))

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
        
        Args:
            recording: Whether recording is active
            paused: Whether recording is paused
            caller: Identifier for debugging which code called this method
        """
        logging.info(f"_update_recording_ui_state called by {caller}: recording={recording}, paused={paused}")
        
        # Update workflow UI
        if hasattr(self.ui, 'set_recording_state'):
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
        current = widget.get("1.0", "end-1c")
        if self.capitalize_next and text:
            text = text[0].upper() + text[1:]
            self.capitalize_next = False
        widget.insert(tk.END, (" " if current and current[-1] != "\n" else "") + text)
        widget.see(tk.END)
        
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
            if os.name == 'nt':  # Windows
                os.startfile(log_dir)
            else:  # macOS or Linux
                import subprocess
                subprocess.Popen(['open', log_dir] if sys.platform == 'darwin' else ['xdg-open', log_dir])
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
    
    def _handle_chat_message(self, message: str):
        """Handle chat message from the chat UI."""
        logging.info(f"Chat message received: {message}")
        
        if not hasattr(self, 'chat_processor') or not self.chat_processor:
            self.status_manager.error("Chat processor not available")
            if hasattr(self, 'chat_ui') and self.chat_ui:
                self.chat_ui.set_processing(False)
            return
            
        # Update status
        self.status_manager.info("Processing your request...")
        
        # Process the message
        def on_complete():
            """Called when chat processing is complete."""
            if hasattr(self, 'chat_ui') and self.chat_ui:
                self.chat_ui.set_processing(False)
            self.status_manager.success("Chat response ready")
            
        self.chat_processor.process_message(message, on_complete)
    
    def _update_chat_suggestions(self):
        """Update chat suggestions based on current tab and content."""
        if not hasattr(self, 'chat_ui') or not self.chat_ui:
            return
            
        current_tab = self.notebook.index(self.notebook.select())
        suggestions = []
        
        # Get current content
        content = self.active_text_widget.get("1.0", tk.END).strip()
        has_content = bool(content)
        
        # Get custom suggestions from settings
        from settings.settings import SETTINGS
        custom_suggestions = SETTINGS.get("custom_chat_suggestions", {})
        
        # Add global custom suggestions first
        global_custom = custom_suggestions.get("global", [])
        suggestions.extend(global_custom)
        
        # Determine context and content state
        context_map = {0: "transcript", 1: "soap", 2: "referral", 3: "letter", 4: "chat"}
        context = context_map.get(current_tab, "transcript")
        content_state = "with_content" if has_content else "without_content"
        
        # Add context-specific custom suggestions
        context_custom = custom_suggestions.get(context, {}).get(content_state, [])
        suggestions.extend(context_custom)
        
        # Add built-in suggestions as fallback/additional options
        builtin_suggestions = self._get_builtin_suggestions(current_tab, has_content)
        suggestions.extend(builtin_suggestions)
        
        # Remove duplicates while preserving order (custom suggestions first)
        seen = set()
        unique_suggestions = []
        for suggestion in suggestions:
            if suggestion not in seen:
                seen.add(suggestion)
                unique_suggestions.append(suggestion)
        
        # Limit to max 6 suggestions to avoid UI clutter
        self.chat_ui.set_suggestions(unique_suggestions[:6])
    
    def _get_builtin_suggestions(self, current_tab: int, has_content: bool):
        """Get built-in suggestions for the given context."""
        if current_tab == 0:  # Transcript
            if has_content:
                return [
                    "Summarize key points",
                    "Extract symptoms mentioned",
                    "Identify medications"
                ]
            else:
                return [
                    "Analyze uploaded audio",
                    "Extract medical terms",
                    "Create summary"
                ]
        elif current_tab == 1:  # SOAP
            if has_content:
                return [
                    "Improve grammar and clarity",
                    "Add more detail to assessment",
                    "Suggest differential diagnoses"
                ]
            else:
                return [
                    "Create SOAP from transcript",
                    "Generate assessment",
                    "Suggest treatment plan"
                ]
        elif current_tab == 2:  # Referral
            if has_content:
                return [
                    "Make more formal",
                    "Add urgency indicators",
                    "Include relevant history"
                ]
            else:
                return [
                    "Generate referral letter",
                    "Create specialist request",
                    "Draft consultation note"
                ]
        elif current_tab == 3:  # Letter
            if has_content:
                return [
                    "Improve tone and clarity",
                    "Make more empathetic",
                    "Simplify language"
                ]
            else:
                return [
                    "Draft patient letter",
                    "Create discharge summary",
                    "Write follow-up instructions"
                ]
        elif current_tab == 4:  # Chat
            if has_content:
                return [
                    "Clear chat history",
                    "Summarize our conversation",
                    "What else can you help with?"
                ]
            else:
                # Include tool examples if tools are enabled
                chat_config = SETTINGS.get("chat_interface", {})
                if chat_config.get("enable_tools", True):
                    return [
                        "Calculate BMI for 70kg, 175cm",
                        "Check drug interaction warfarin aspirin",
                        "What's 15 * 8 + 32?",
                        "What's the current time?",
                        "Calculate dosage: 25mg/kg for 30kg",
                        "Explain this medical term"
                    ]
                else:
                    return [
                        "What is this medication for?",
                        "Explain this medical term",
                        "Help me understand my diagnosis"
                    ]
        return []
    
    def _focus_chat_input(self):
        """Focus the chat input field."""
        if hasattr(self, 'chat_ui') and self.chat_ui:
            self.chat_ui.focus_input()

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
                'context': context_text
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
    
    # Voice Mode Integration Methods
    def start_voice_mode(self):
        """Start voice mode for advanced voice interactions."""
        try:
            # Initialize voice interaction manager if not exists
            if not hasattr(self, 'voice_manager'):
                from voice.voice_interaction_manager import VoiceInteractionManager
                self.voice_manager = VoiceInteractionManager(self.audio_handler)
                
                # Set callbacks
                self.voice_manager.on_state_change = self._on_voice_state_change
                self.voice_manager.on_transcript = self._on_voice_transcript
                self.voice_manager.on_ai_response = self._on_voice_ai_response
                self.voice_manager.on_error = self._on_voice_error
                
                # Configure voice settings from saved voice mode settings
                voice_mode_config = SETTINGS.get("voice_mode", {})
                
                # Determine which model to use based on provider
                ai_provider = voice_mode_config.get("ai_provider", "openai")
                if ai_provider == "openai":
                    ai_model = voice_mode_config.get("openai_model", "gpt-4")
                elif ai_provider == "perplexity":
                    ai_model = voice_mode_config.get("perplexity_model", "sonar-reasoning-pro")
                elif ai_provider == "grok":
                    ai_model = voice_mode_config.get("grok_model", "grok-1")
                elif ai_provider == "ollama":
                    ai_model = voice_mode_config.get("ollama_model", "llama3")
                elif ai_provider == "anthropic":
                    ai_model = voice_mode_config.get("anthropic_model", "claude-3-sonnet-20240229")
                else:
                    ai_model = voice_mode_config.get("ai_model", "gpt-4")
                
                voice_settings = {
                    "ai_provider": ai_provider,
                    "ai_model": ai_model,
                    "ai_temperature": voice_mode_config.get("ai_temperature", 0.7),
                    "system_prompt": voice_mode_config.get("system_prompt", 
                        """You are a medical AI assistant in voice mode. Provide helpful, conversational responses about medical topics. Keep responses concise and natural for voice interaction. When discussing medical conditions, be clear about when professional medical advice is needed."""),
                    "tts_provider": voice_mode_config.get("tts_provider", "openai"),
                    "tts_voice": voice_mode_config.get("tts_voice", "nova"),
                    "stt_provider": voice_mode_config.get("stt_provider", "deepgram"),
                    "enable_interruptions": voice_mode_config.get("enable_interruptions", True),
                    "response_delay_ms": voice_mode_config.get("response_delay_ms", 500),
                    "max_context_length": voice_mode_config.get("max_context_length", 4000)
                }
                self.voice_manager.configure(voice_settings)
                
                # Initialize components
                asyncio.run(self.voice_manager.initialize())
            
            # Get medical context
            context_data = self._get_medical_context_for_voice()
            
            # Start voice session
            session_data = {
                "medical_context": context_data,
                "timestamp": datetime.now()
            }
            
            asyncio.run(self.voice_manager.start_session(session_data))
            
            # Start audio capture thread
            self._start_voice_audio_capture()
            
            logging.info("Voice mode started successfully")
            
        except Exception as e:
            logging.error(f"Failed to start voice mode: {e}")
            self.status_manager.error("Failed to start voice mode")
            if hasattr(self.ui.components.get('voice_ui'), 'add_system_message'):
                self.ui.components['voice_ui'].add_system_message(f"Error: {str(e)}")
    
    def stop_voice_mode(self):
        """Stop voice mode."""
        try:
            if hasattr(self, 'voice_manager'):
                # Stop audio capture
                self._stop_voice_audio_capture()
                
                # End voice session
                asyncio.run(self.voice_manager.end_session())
                
                # Get conversation transcript
                transcript = self.voice_manager.get_conversation_transcript()
                
                # Save transcript if not empty
                if transcript:
                    self._save_voice_transcript(transcript)
                
                logging.info("Voice mode stopped successfully")
                
        except Exception as e:
            logging.error(f"Failed to stop voice mode: {e}")
            self.status_manager.error("Failed to stop voice mode")
    
    def _voice_recording_loop(self, callback):
        """Continuous recording loop for voice mode.
        
        Args:
            callback: Function to call with audio data
        """
        try:
            import pyaudio
            
            # Audio parameters
            CHUNK = 1024
            FORMAT = pyaudio.paInt16
            CHANNELS = 1
            RATE = 16000
            
            # Initialize PyAudio
            p = pyaudio.PyAudio()
            
            # Get the selected microphone from audio handler
            mic_index = None
            if hasattr(self.audio_handler, 'selected_device'):
                mic_index = self.audio_handler.selected_device
            
            # Open audio stream
            stream = p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=mic_index,
                frames_per_buffer=CHUNK
            )
            
            logging.info(f"Voice recording started on device {mic_index}")
            
            # Continuous recording loop
            while self.voice_recording_active:
                try:
                    # Read audio data
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    
                    # Only send to callback if not speaking
                    # This prevents feedback loop where TTS output is picked up by mic
                    if hasattr(self, 'voice_manager') and self.voice_manager:
                        from voice.voice_interaction_manager import ConversationState
                        if self.voice_manager.state != ConversationState.SPEAKING:
                            callback(data)
                        else:
                            # During speaking, send silence to keep connection alive
                            silence = b'\x00' * len(data)
                            callback(silence)
                    else:
                        callback(data)
                    
                except Exception as e:
                    logging.error(f"Error in voice recording loop: {e}")
                    
            # Clean up
            stream.stop_stream()
            stream.close()
            p.terminate()
            
            logging.info("Voice recording loop ended")
            
        except Exception as e:
            logging.error(f"Voice recording loop failed: {e}")
            if hasattr(self, 'voice_manager'):
                self.voice_manager.on_error(f"Audio capture error: {e}")
    
    def interrupt_voice(self):
        """Interrupt current voice interaction."""
        try:
            if hasattr(self, 'voice_manager'):
                self.voice_manager.interrupt()
                
        except Exception as e:
            logging.error(f"Failed to interrupt voice: {e}")
    
    def set_voice_volume(self, volume: float):
        """Set voice playback volume.
        
        Args:
            volume: Volume level (0.0 to 1.0)
        """
        try:
            if hasattr(self, 'voice_manager'):
                self.voice_manager.playback_manager.set_volume(volume)
                
        except Exception as e:
            logging.error(f"Failed to set voice volume: {e}")
    
    def set_voice_interruptions(self, enabled: bool):
        """Enable/disable voice interruptions.
        
        Args:
            enabled: Whether interruptions are enabled
        """
        try:
            if hasattr(self, 'voice_manager'):
                self.voice_manager.settings["enable_interruptions"] = enabled
                
        except Exception as e:
            logging.error(f"Failed to set voice interruptions: {e}")
    
    def export_voice_transcript(self, content: str):
        """Export voice conversation transcript.
        
        Args:
            content: Transcript content
        """
        try:
            # Use file dialog to save
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"voice_transcript_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )
            
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.status_manager.success(f"Transcript saved to {filename}")
                
        except Exception as e:
            logging.error(f"Failed to export voice transcript: {e}")
            self.status_manager.error("Failed to save transcript")
    
    def add_to_context(self, content: str, source: str = "Voice"):
        """Add content to context tab.
        
        Args:
            content: Content to add
            source: Source of content
        """
        try:
            # Add header
            header = f"\n\n--- {source} ({datetime.now().strftime('%Y-%m-%d %H:%M')}) ---\n\n"
            
            # Add to context
            self.context_text.insert(tk.END, header + content)
            
            # Focus context tab
            self.notebook.select(4)  # Context tab
            
            self.status_manager.success(f"{source} added to context")
            
        except Exception as e:
            logging.error(f"Failed to add to context: {e}")
    
    def _get_medical_context_for_voice(self) -> dict:
        """Get current medical context for voice mode.
        
        Returns:
            Dictionary with medical context
        """
        context = {}
        
        # Get context text
        context_content = self.context_text.get("1.0", tk.END).strip()
        if context_content:
            context["context_notes"] = context_content
        
        # Get latest SOAP note if available
        soap_content = self.soap_text.get("1.0", tk.END).strip()
        if soap_content:
            context["latest_soap"] = soap_content[:1000]  # First 1000 chars
        
        # Get patient info from context
        patient_name = self._extract_patient_name(context_content)
        if patient_name:
            context["patient_name"] = patient_name
        
        return context
    
    def _start_voice_audio_capture(self):
        """Start capturing audio for voice mode."""
        try:
            # Create a callback for continuous audio streaming
            def voice_audio_callback(audio_data):
                """Callback for streaming audio to voice manager."""
                if hasattr(self, 'voice_manager') and self.voice_manager.is_active:
                    # Convert bytes to numpy array
                    audio_array = np.frombuffer(audio_data, dtype=np.int16)
                    # Send to voice manager for processing
                    self.voice_manager.process_audio(audio_array)
            
            # Start recording with the audio handler
            # Use continuous streaming mode for voice
            self.voice_recording_active = True
            self.voice_recording_thread = threading.Thread(
                target=self._voice_recording_loop,
                args=(voice_audio_callback,),
                daemon=True
            )
            self.voice_recording_thread.start()
            
            logging.info("Voice audio capture started")
            
        except Exception as e:
            logging.error(f"Failed to start voice audio capture: {e}")
            self.status_manager.error("Failed to start audio capture")
    
    def _stop_voice_audio_capture(self):
        """Stop capturing audio for voice mode."""
        logging.info("Voice audio capture would stop here")
        # TODO: Implement actual audio capture stop
    
    def _process_voice_audio(self, audio_data):
        """Process audio data for voice mode.
        
        Args:
            audio_data: Raw audio data
        """
        try:
            if hasattr(self, 'voice_manager') and self.voice_manager.is_active:
                # Convert audio data to numpy array
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                
                # Send to voice manager
                self.voice_manager.process_audio(audio_array)
                
        except Exception as e:
            logging.error(f"Error processing voice audio: {e}")
    
    def _on_voice_state_change(self, state: str):
        """Handle voice state change.
        
        Args:
            state: New voice state
        """
        # Update UI
        if hasattr(self.ui.components.get('voice_ui'), 'update_state'):
            self.ui.components['voice_ui'].update_state(state)
    
    def _on_voice_transcript(self, data: dict):
        """Handle voice transcript.
        
        Args:
            data: Transcript data
        """
        if data.get('is_final'):
            # Add to UI
            if hasattr(self.ui.components.get('voice_ui'), 'add_user_message'):
                self.ui.components['voice_ui'].add_user_message(
                    data['text'],
                    data.get('timestamp')
                )
    
    def _on_voice_ai_response(self, data: dict):
        """Handle voice AI response.
        
        Args:
            data: AI response data
        """
        # Add to UI
        if hasattr(self.ui.components.get('voice_ui'), 'add_assistant_message'):
            self.ui.components['voice_ui'].add_assistant_message(
                data['text'],
                data.get('timestamp')
            )
    
    def _on_voice_error(self, error: str):
        """Handle voice error.
        
        Args:
            error: Error message
        """
        logging.error(f"Voice error: {error}")
        self.status_manager.error(f"Voice error: {error}")
        
        # Add to UI
        if hasattr(self.ui.components.get('voice_ui'), '_add_system_message'):
            self.ui.components['voice_ui']._add_system_message(f"Error: {error}")
    
    def _save_voice_transcript(self, transcript: str):
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
