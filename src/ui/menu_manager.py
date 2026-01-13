"""
Menu Manager Module

Handles the creation and management of application menus including
File, Settings, and Help menus with their respective commands.
"""

import tkinter as tk
import os
from ui.dialogs.dialogs import show_api_keys_dialog
from ui.dialogs.unified_settings_dialog import show_unified_settings_dialog


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
        # Determine if we're in dark mode
        is_dark = self.app.current_theme in ["darkly", "solar", "cyborg", "superhero"]
        
        # Create menubar with custom styling
        menubar = tk.Menu(self.app, tearoff=0)
        self._style_menu(menubar, is_dark)
        
        # Create File menu
        self._create_file_menu(menubar)

        # Create Edit menu
        self._create_edit_menu(menubar)

        # Create Settings menu
        self._create_settings_menu(menubar)

        # Create Tools menu
        self._create_tools_menu(menubar)

        # Create Help menu
        self._create_help_menu(menubar)
        
        # Configure the menu bar
        self.app.config(menu=menubar)
    
    def _style_menu(self, menu: tk.Menu, is_dark: bool) -> None:
        """Apply custom styling to a menu based on theme.
        
        Args:
            menu: The menu to style
            is_dark: Whether dark theme is active
        """
        if is_dark:
            # Dark theme colors
            menu.config(
                bg="#2b2b2b",  # Dark background
                fg="#ffffff",  # White text
                activebackground="#0d6efd",  # Blue highlight
                activeforeground="#ffffff",  # White text on highlight
                borderwidth=1,
                relief="flat",
                font=("Segoe UI", 10)
            )
        else:
            # Light theme colors
            menu.config(
                bg="#ffffff",  # White background
                fg="#212529",  # Dark text
                activebackground="#0d6efd",  # Blue highlight
                activeforeground="#ffffff",  # White text on highlight
                borderwidth=1,
                relief="flat",
                font=("Segoe UI", 10)
            )
    
    def _add_menu_item(self, menu: tk.Menu, label: str, command=None, accelerator=None, padded=True) -> None:
        """Add a menu item with optional padding.
        
        Args:
            menu: The menu to add item to
            label: The text label for the menu item
            command: The command to execute when clicked
            accelerator: Keyboard shortcut text to display
            padded: Whether to add padding to the label
        """
        if padded:
            # Add padding with spaces
            padded_label = f"  {label}  "
        else:
            padded_label = label
            
        menu.add_command(label=padded_label, command=command, accelerator=accelerator)
    
    def _create_file_menu(self, menubar: tk.Menu) -> None:
        """Create the File menu.
        
        Args:
            menubar: The main menu bar to add the File menu to
        """
        is_dark = self.app.current_theme in ["darkly", "solar", "cyborg", "superhero"]
        filemenu = tk.Menu(menubar, tearoff=0)
        self._style_menu(filemenu, is_dark)
        
        # Add menu items
        filemenu.add_command(label="New", command=self.app.new_session, accelerator="Ctrl+N")
        filemenu.add_command(label="Save", command=self.app.save_text, accelerator="Ctrl+S")
        filemenu.add_separator()
        
        # Export submenu
        export_menu = tk.Menu(filemenu, tearoff=0)
        self._style_menu(export_menu, is_dark)
        export_menu.add_command(label="Export as PDF...", command=self.app.export_as_pdf, accelerator="Ctrl+E")
        export_menu.add_command(label="Export as PDF (Letterhead)...", command=self.app.export_as_pdf_letterhead)
        export_menu.add_command(label="Export as Word...", command=self.app.export_as_word, accelerator="Ctrl+Shift+W")
        export_menu.add_separator()
        export_menu.add_command(label="Export as FHIR...", command=self.app.export_as_fhir, accelerator="Ctrl+Shift+F")
        export_menu.add_command(label="Export FHIR to Clipboard", command=self.app.copy_fhir_to_clipboard)
        export_menu.add_separator()
        export_menu.add_command(label="Export All Documents...", command=self.app.export_all_as_pdf)
        filemenu.add_cascade(label="Export", menu=export_menu)
        
        filemenu.add_separator()
        filemenu.add_command(label="Print...", command=self.app.print_document, accelerator="Ctrl+P")
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.app.on_closing)
        menubar.add_cascade(label="File", menu=filemenu)

    def _create_edit_menu(self, menubar: tk.Menu) -> None:
        """Create the Edit menu with undo/redo controls.

        Args:
            menubar: The main menu bar to add the Edit menu to
        """
        is_dark = self.app.current_theme in ["darkly", "solar", "cyborg", "superhero"]
        edit_menu = tk.Menu(menubar, tearoff=0)
        self._style_menu(edit_menu, is_dark)

        # Undo/Redo
        edit_menu.add_command(label="Undo", command=self.app.undo_text, accelerator="Ctrl+Z")
        edit_menu.add_command(label="Redo", command=self.app.redo_text, accelerator="Ctrl+Y")
        edit_menu.add_separator()

        # Copy (already has Ctrl+C bound)
        edit_menu.add_command(label="Copy", command=self.app.copy_text, accelerator="Ctrl+C")
        edit_menu.add_separator()

        # Undo History
        edit_menu.add_command(label="Undo History...", command=self.app.show_undo_history)

        menubar.add_cascade(label="Edit", menu=edit_menu)

    def _create_settings_menu(self, menubar: tk.Menu) -> None:
        """Create the Settings menu with organized submenus.

        Args:
            menubar: The main menu bar to add the Settings menu to
        """
        is_dark = self.app.current_theme in ["darkly", "solar", "cyborg", "superhero"]
        settings_menu = tk.Menu(menubar, tearoff=0)
        self._style_menu(settings_menu, is_dark)

        # Preferences (unified dialog) at top - primary entry point
        settings_menu.add_command(
            label="Preferences...",
            command=self.show_preferences_dialog,
            accelerator="Ctrl+,"
        )
        settings_menu.add_separator()

        # API Keys - keep at top level for quick access
        settings_menu.add_command(label="Update API Keys", command=self.show_api_keys_dialog)
        settings_menu.add_separator()

        # Organized submenus
        self._create_audio_stt_submenu(settings_menu)
        self._create_ai_models_submenu(settings_menu)
        self._create_prompt_settings_submenu(settings_menu)
        self._create_data_storage_submenu(settings_menu)

        settings_menu.add_separator()

        # Import/Export
        settings_menu.add_command(label="Export Prompts", command=self.app.export_prompts)
        settings_menu.add_command(label="Import Prompts", command=self.app.import_prompts)
        settings_menu.add_separator()

        # Quick toggles at bottom
        settings_menu.add_checkbutton(
            label="Quick Continue Mode",
            command=self.app.toggle_quick_continue_mode,
            variable=self.app.quick_continue_var if hasattr(self.app, 'quick_continue_var') else None
        )
        settings_menu.add_command(label="Toggle Theme", command=self.app.toggle_theme, accelerator="Alt+T")

        menubar.add_cascade(label="Settings", menu=settings_menu)

    def _create_tools_menu(self, menubar: tk.Menu) -> None:
        """Create the Tools menu.

        Args:
            menubar: The main menu bar to add the Tools menu to
        """
        is_dark = self.app.current_theme in ["darkly", "solar", "cyborg", "superhero"]
        tools_menu = tk.Menu(menubar, tearoff=0)
        self._style_menu(tools_menu, is_dark)

        # Diagnostic tools
        tools_menu.add_command(
            label="Run Diagnostic Analysis",
            command=self.app.create_diagnostic_analysis,
            accelerator="Ctrl+D"
        )
        tools_menu.add_command(
            label="Diagnostic History",
            command=self.app.show_diagnostic_history
        )
        tools_menu.add_command(
            label="Compare Diagnoses",
            command=self.app.show_diagnostic_comparison
        )
        tools_menu.add_separator()

        # Medication tools
        tools_menu.add_command(
            label="Medication Analysis",
            command=self.app.analyze_medications
        )
        tools_menu.add_separator()

        # Translation tools
        tools_menu.add_command(
            label="Translation Assistant",
            command=self.app.show_translation_assistant
        )

        menubar.add_cascade(label="Tools", menu=tools_menu)

    def _create_audio_stt_submenu(self, settings_menu: tk.Menu) -> None:
        """Create the Audio & Transcription submenu.

        Args:
            settings_menu: The settings menu to add the submenu to
        """
        is_dark = self.app.current_theme in ["darkly", "solar", "cyborg", "superhero"]
        audio_menu = tk.Menu(settings_menu, tearoff=0)
        self._style_menu(audio_menu, is_dark)

        audio_menu.add_command(label="ElevenLabs Settings", command=self.app.show_elevenlabs_settings)
        audio_menu.add_command(label="Deepgram Settings", command=self.app.show_deepgram_settings)
        audio_menu.add_command(label="Groq Settings", command=self.app.show_groq_settings)
        audio_menu.add_separator()
        audio_menu.add_command(label="TTS Settings", command=self.app.show_tts_settings)

        settings_menu.add_cascade(label="Audio & Transcription", menu=audio_menu)

    def _create_ai_models_submenu(self, settings_menu: tk.Menu) -> None:
        """Create the AI & Models submenu.

        Args:
            settings_menu: The settings menu to add the submenu to
        """
        is_dark = self.app.current_theme in ["darkly", "solar", "cyborg", "superhero"]
        ai_menu = tk.Menu(settings_menu, tearoff=0)
        self._style_menu(ai_menu, is_dark)

        ai_menu.add_command(label="Temperature Settings", command=self.app.show_temperature_settings)
        ai_menu.add_command(label="Agent Settings", command=self.app.show_agent_settings)
        ai_menu.add_separator()
        ai_menu.add_command(label="Translation Settings", command=self.app.show_translation_settings)
        ai_menu.add_command(label="MCP Tools", command=self.app.show_mcp_config)

        settings_menu.add_cascade(label="AI & Models", menu=ai_menu)

    def _create_data_storage_submenu(self, settings_menu: tk.Menu) -> None:
        """Create the Data & Storage submenu.

        Args:
            settings_menu: The settings menu to add the submenu to
        """
        is_dark = self.app.current_theme in ["darkly", "solar", "cyborg", "superhero"]
        data_menu = tk.Menu(settings_menu, tearoff=0)
        self._style_menu(data_menu, is_dark)

        data_menu.add_command(label="Custom Vocabulary", command=self.app.show_vocabulary_settings)
        data_menu.add_separator()
        data_menu.add_command(label="Manage Address Book...", command=self.app.manage_address_book)
        data_menu.add_command(label="Import Contacts from CSV...", command=self.app.import_contacts_from_csv)
        data_menu.add_separator()
        data_menu.add_command(label="Set Storage Folder", command=self.app.set_default_folder)
        data_menu.add_command(label="Record Prefix Audio", command=self.app.record_prefix_audio)

        settings_menu.add_cascade(label="Data & Storage", menu=data_menu)
    
    def _create_prompt_settings_submenu(self, settings_menu: tk.Menu) -> None:
        """Create the Prompt Settings submenu.
        
        Args:
            settings_menu: The settings menu to add the submenu to
        """
        is_dark = self.app.current_theme in ["darkly", "solar", "cyborg", "superhero"]
        text_settings_menu = tk.Menu(settings_menu, tearoff=0)
        self._style_menu(text_settings_menu, is_dark)
        
        # Add items with padding
        self._add_menu_item(text_settings_menu, "Refine Prompt Settings", command=self.app.show_refine_settings_dialog)
        self._add_menu_item(text_settings_menu, "Improve Prompt Settings", command=self.app.show_improve_settings_dialog)
        self._add_menu_item(text_settings_menu, "SOAP Note Settings", command=self.app.show_soap_settings_dialog)
        self._add_menu_item(text_settings_menu, "Referral Settings", command=self.app.show_referral_settings_dialog)
        self._add_menu_item(text_settings_menu, "Advanced Analysis Settings", command=self.app.show_advanced_analysis_settings_dialog)
        
        settings_menu.add_cascade(label="Prompt Settings", menu=text_settings_menu)
    
    def _create_help_menu(self, menubar: tk.Menu) -> None:
        """Create the Help menu.
        
        Args:
            menubar: The main menu bar to add the Help menu to
        """
        is_dark = self.app.current_theme in ["darkly", "solar", "cyborg", "superhero"]
        helpmenu = tk.Menu(menubar, tearoff=0)
        self._style_menu(helpmenu, is_dark)
        
        helpmenu.add_command(label="About", command=self.app.show_about)
        helpmenu.add_command(label="Keyboard Shortcuts", command=self.app.show_shortcuts)
        
        # Create logs submenu
        self._create_logs_submenu(helpmenu)
        
        menubar.add_cascade(label="Help", menu=helpmenu)
    
    def _create_logs_submenu(self, helpmenu: tk.Menu) -> None:
        """Create the Logs submenu.
        
        Args:
            helpmenu: The help menu to add the submenu to
        """
        is_dark = self.app.current_theme in ["darkly", "solar", "cyborg", "superhero"]
        logs_menu = tk.Menu(helpmenu, tearoff=0)
        self._style_menu(logs_menu, is_dark)
        
        # Add items with padding
        self._add_menu_item(logs_menu, "Open Logs Folder", command=self.app._open_logs_folder_menu)
        self._add_menu_item(logs_menu, "View Log Contents", command=self.app._show_log_contents_menu)
        
        helpmenu.add_cascade(label="View Logs", menu=logs_menu)
    
    def show_preferences_dialog(self) -> None:
        """Show the unified Preferences dialog."""
        show_unified_settings_dialog(self.app)

    def show_api_keys_dialog(self) -> None:
        """Shows a dialog to update API keys and updates the .env file."""
        # Call the refactored function from dialogs.py
        show_api_keys_dialog(self.app)

        # Note: OpenAI API key is read from env/security manager by modern provider modules

        # Update audio handler with the new API keys
        self.app.audio_handler.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self.app.audio_handler.deepgram_api_key = os.getenv("DEEPGRAM_API_KEY", "")
        self.app.audio_handler.groq_api_key = os.getenv("GROQ_API_KEY", "")
        
        # Update the STT providers with new keys
        self.app.audio_handler.elevenlabs_provider.api_key = self.app.audio_handler.elevenlabs_api_key
        self.app.audio_handler.deepgram_provider.api_key = self.app.audio_handler.deepgram_api_key
        self.app.audio_handler.groq_provider.api_key = self.app.audio_handler.groq_api_key

        # Refresh provider dropdowns to show only providers with API keys
        if hasattr(self.app, 'refresh_provider_dropdowns'):
            self.app.refresh_provider_dropdowns()
    
    def update_menu_theme(self) -> None:
        """Update menu styling when theme changes."""
        # Recreate the menu with new theme
        self.create_menu()
    
