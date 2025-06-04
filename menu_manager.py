"""
Menu Manager Module

Handles the creation and management of application menus including
File, Settings, and Help menus with their respective commands.
"""

import tkinter as tk
import os
import openai
from dialogs import show_api_keys_dialog


class MenuManager:
    """Manages application menu creation and actions."""
    
    def __init__(self, parent_app):
        """Initialize the menu manager.
        
        Args:
            parent_app: The main application instance
        """
        self.app = parent_app
        
    def create_menu(self) -> None:
        """Create the application menu bar with all menus and options."""
        menubar = tk.Menu(self.app)
        
        # Create File menu
        self._create_file_menu(menubar)
        
        # Create Settings menu
        self._create_settings_menu(menubar)
        
        # Create Help menu
        self._create_help_menu(menubar)
        
        # Configure the menu bar
        self.app.config(menu=menubar)
    
    def _create_file_menu(self, menubar: tk.Menu) -> None:
        """Create the File menu.
        
        Args:
            menubar: The main menu bar to add the File menu to
        """
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="New", command=self.app.new_session, accelerator="Ctrl+N")
        filemenu.add_command(label="Save", command=self.app.save_text, accelerator="Ctrl+S")
        filemenu.add_command(label="View Recordings", command=self.app.show_recordings_dialog)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.app.on_closing)
        menubar.add_cascade(label="File", menu=filemenu)
    
    def _create_settings_menu(self, menubar: tk.Menu) -> None:
        """Create the Settings menu with all submenus.
        
        Args:
            menubar: The main menu bar to add the Settings menu to
        """
        settings_menu = tk.Menu(menubar, tearoff=0)
        
        # Add API Keys option at the top of the settings menu
        settings_menu.add_command(label="Update API Keys", command=self.show_api_keys_dialog)
        settings_menu.add_separator()
        
        # Add STT provider settings menu options
        settings_menu.add_command(label="ElevenLabs Settings", command=self.app.show_elevenlabs_settings)
        settings_menu.add_command(label="Deepgram Settings", command=self.app.show_deepgram_settings)
        settings_menu.add_command(label="Temperature Settings", command=self.app.show_temperature_settings)
        
        # Create prompt settings submenu
        self._create_prompt_settings_submenu(settings_menu)
        
        # Add other settings options
        settings_menu.add_command(label="Export Prompts", command=self.app.export_prompts)
        settings_menu.add_command(label="Import Prompts", command=self.app.import_prompts)
        settings_menu.add_command(label="Set Storage Folder", command=self.app.set_default_folder)
        settings_menu.add_command(label="Record Prefix Audio", command=self.app.record_prefix_audio)
        settings_menu.add_command(label="Toggle Theme", command=self.app.toggle_theme)
        settings_menu.add_command(label="Switch UI Mode", command=self._toggle_ui_mode)
        
        menubar.add_cascade(label="Settings", menu=settings_menu)
    
    def _create_prompt_settings_submenu(self, settings_menu: tk.Menu) -> None:
        """Create the Prompt Settings submenu.
        
        Args:
            settings_menu: The settings menu to add the submenu to
        """
        text_settings_menu = tk.Menu(settings_menu, tearoff=0)
        text_settings_menu.add_command(label="Refine Prompt Settings", command=self.app.show_refine_settings_dialog)
        text_settings_menu.add_command(label="Improve Prompt Settings", command=self.app.show_improve_settings_dialog)
        text_settings_menu.add_command(label="SOAP Note Settings", command=self.app.show_soap_settings_dialog)
        text_settings_menu.add_command(label="Referral Settings", command=self.app.show_referral_settings_dialog)
        
        settings_menu.add_cascade(label="Prompt Settings", menu=text_settings_menu)
    
    def _create_help_menu(self, menubar: tk.Menu) -> None:
        """Create the Help menu.
        
        Args:
            menubar: The main menu bar to add the Help menu to
        """
        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="About", command=self.app.show_about)
        helpmenu.add_command(label="Keyboard Shortcuts", command=self.app.show_shortcuts)
        helpmenu.add_command(label="View Logs", command=self.app.view_logs)
        menubar.add_cascade(label="Help", menu=helpmenu)
    
    def show_api_keys_dialog(self) -> None:
        """Shows a dialog to update API keys and updates the .env file."""
        # Call the refactored function from dialogs.py
        show_api_keys_dialog(self.app)
        
        # Refresh API keys in the application
        openai.api_key = os.getenv("OPENAI_API_KEY")
        
        # Update audio handler with the new API keys
        self.app.audio_handler.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self.app.audio_handler.deepgram_api_key = os.getenv("DEEPGRAM_API_KEY", "")
        self.app.audio_handler.groq_api_key = os.getenv("GROQ_API_KEY", "")
        
        # Update the STT providers with new keys
        self.app.audio_handler.elevenlabs_provider.api_key = self.app.audio_handler.elevenlabs_api_key
        self.app.audio_handler.deepgram_provider.api_key = self.app.audio_handler.deepgram_api_key
        self.app.audio_handler.groq_provider.api_key = self.app.audio_handler.groq_api_key
    
    def _toggle_ui_mode(self):
        """Toggle between classic and workflow UI modes."""
        from settings import SETTINGS, save_settings
        from tkinter import messagebox
        
        current_mode = SETTINGS.get("ui_mode", "workflow")
        new_mode = "classic" if current_mode == "workflow" else "workflow"
        
        result = messagebox.askyesno(
            "Switch UI Mode",
            f"Switch from {current_mode.title()} UI to {new_mode.title()} UI?\n\n"
            f"The application will need to restart to apply the change.",
            icon="question"
        )
        
        if result:
            # Update settings
            SETTINGS["ui_mode"] = new_mode
            save_settings(SETTINGS)
            
            # Show restart message
            messagebox.showinfo(
                "UI Mode Changed",
                f"UI mode changed to {new_mode.title()}.\n\n"
                f"Please restart the application to see the new interface."
            )