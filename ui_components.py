import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from typing import Callable, Dict, Any, List, Optional
import logging
from tooltip import ToolTip
from settings import SETTINGS
from utils import get_valid_microphones
import speech_recognition as sr

class UIComponents:
    """Helper class to build and manage UI components for the Medical Dictation app."""
    
    def __init__(self, parent):
        """Initialize the UI component builder.
        
        Args:
            parent: The parent window or frame
        """
        self.parent = parent
        self.style = ttk.Style()
        self._configure_styles()
        
    def _configure_styles(self):
        """Configure custom styles for the application."""
        # Configure notebook with success color for active tabs
        success_color = self.style.colors.success
        
        self.style.configure("Green.TNotebook", background="white", borderwidth=0)
        self.style.configure("Green.TNotebook.Tab", padding=[10, 5], background="lightgrey", foreground="black")
        
        # Map the foreground (text color) and background based on tab state
        self.style.map("Green.TNotebook.Tab",
            background=[("selected", success_color), ("active", success_color), ("!selected", "lightgrey")],
            foreground=[("selected", "white"), ("!selected", "black")]
        )
        
        # Configure custom style for refresh button - using ttkbootstrap's info color for light mode
        # This makes it match the theme button color which uses bootstyle="info" in light mode
        info_color = self.style.colors.info  # Get the info color from ttkbootstrap
        self.style.configure("Refresh.TButton", foreground="white", background=info_color)
        self.style.map("Refresh.TButton", 
            foreground=[("pressed", "white"), ("active", "white")],
            background=[("pressed", info_color), ("active", info_color)])
    
    def create_microphone_frame(self, on_provider_change: Callable, on_stt_change: Callable, 
                              refresh_microphones: Callable, toggle_theme: Callable = None) -> tuple:
        """Create the microphone selection section with provider and STT options.
        
        Returns:
            tuple: (mic_frame, mic_combobox, provider_combobox, stt_combobox, theme_btn, theme_label)
        """
        # Main frame for microphone selection
        mic_frame = ttk.Frame(self.parent, padding=10)
        
        # Left side - microphone selection
        mic_select_frame = ttk.Frame(mic_frame)
        mic_select_frame.pack(side=LEFT, fill=tk.X, expand=True)
        
        ttk.Label(mic_select_frame, text="Select Microphone:").pack(side=LEFT, padx=(0, 10))
        
        mic_combobox = ttk.Combobox(
            mic_select_frame,
            values=get_valid_microphones() or sr.Microphone.list_microphone_names(),
            state="readonly",
            width=45
        )
        mic_combobox.pack(side=LEFT, padx=(0, 5), fill=None, expand=False)
        
        if len(mic_combobox["values"]) > 0:
            mic_combobox.current(0)
        
        # Determine if currently in dark mode
        is_dark = self.parent.current_theme in ["darkly", "solar", "cyborg", "superhero"]
        
        refresh_btn = ttk.Button(
            mic_select_frame,
            text="⟳",
            command=refresh_microphones,
            width=3,
            bootstyle="info" if not is_dark else "dark",  # Match theme button's "info" style in light mode
            style="Refresh.TButton"
        )
        refresh_btn.pack(side=LEFT, padx=(0, 10))
        ToolTip(refresh_btn, "Refresh microphone list")
        
        # Middle - Provider selection
        provider_frame = ttk.Frame(mic_frame)
        provider_frame.pack(side=LEFT, fill=tk.X, expand=False)
        
        ttk.Label(provider_frame, text="Provider:").pack(side=LEFT)
        
        provider_values = ["OpenAI", "Grok", "Perplexity"]
        provider = SETTINGS.get("ai_provider", "openai")
        
        provider_combobox = ttk.Combobox(
            provider_frame,
            values=provider_values,
            state="readonly",
            width=12
        )
        provider_combobox.pack(side=LEFT, padx=5)
        
        try:
            provider_index = [p.lower() for p in provider_values].index(provider.lower())
            provider_combobox.current(provider_index)
        except (ValueError, IndexError):
            provider_combobox.current(0)
        
        provider_combobox.bind("<<ComboboxSelected>>", on_provider_change)
        ToolTip(provider_combobox, "Select which AI provider to use for text processing")
        
        # STT Provider selection
        stt_frame = ttk.Frame(mic_frame)
        stt_frame.pack(side=LEFT, fill=tk.X, expand=False, padx=(10, 0))
        
        ttk.Label(stt_frame, text="STT:").pack(side=LEFT)
        
        stt_providers = ["groq", "elevenlabs", "deepgram"]
        stt_display = ["GROQ", "ElevenLabs", "Deepgram"]
        stt_provider = SETTINGS.get("stt_provider", "groq")
        
        stt_combobox = ttk.Combobox(
            stt_frame,
            values=stt_display,
            state="readonly",
            width=12
        )
        stt_combobox.pack(side=LEFT)
        
        try:
            stt_index = stt_providers.index(stt_provider.lower())
            stt_combobox.current(stt_index)
        except (ValueError, IndexError):
            stt_combobox.current(0)
        
        stt_combobox.bind("<<ComboboxSelected>>", on_stt_change)
        ToolTip(stt_combobox, "Select which Speech-to-Text provider to use")
        
        # Initialize theme button and label
        theme_btn = None
        theme_label = None
        
        # NEW: Add theme toggle button
        if toggle_theme:
            theme_frame = ttk.Frame(mic_frame)
            theme_frame.pack(side=LEFT, padx=(15, 0), fill=tk.X, expand=False)
            
            # Get current theme to determine icon and tooltip
            current_theme = SETTINGS.get("theme", "flatly")
            is_dark = current_theme in ["darkly", "solar", "cyborg", "superhero"]
            
            # Use correct icon and tooltip text based on the CURRENT theme
            # In light mode, show moon icon and "Switch to Dark Mode" tooltip
            # In dark mode, show sun icon and "Switch to Light Mode" tooltip
            icon = "🌙" if not is_dark else "☀️"
            tooltip_text = "Switch to Dark Mode" if not is_dark else "Switch to Light Mode"
            
            # Create a more visible theme toggle button with a distinct appearance
            theme_btn = ttk.Button(
                theme_frame,
                text=f"{icon} Theme",  # Add 'Theme' text next to icon
                command=toggle_theme,
                bootstyle="info" if not is_dark else "warning",  # Different style per mode
                width=15  # Increased width from 10 to 15
            )
            theme_btn.pack(side=LEFT, fill=tk.X)
            
            # Add theme indicator label - should show current mode
            mode_text = "Light Mode" if not is_dark else "Dark Mode"
            theme_label = ttk.Label(theme_frame, text=f"({mode_text})", width=12)
            theme_label.pack(side=LEFT, padx=(5, 0))
            
            # Store the tooltip directly on the button as an attribute
            theme_btn._tooltip = ToolTip(theme_btn, tooltip_text)
        
        return mic_frame, mic_combobox, provider_combobox, stt_combobox, theme_btn, theme_label
    
    def create_notebook(self) -> tuple:
        """Create the notebook with tabs for transcript, soap note, referral, and dictation.
        
        Returns:
            tuple: (notebook, transcript_text, soap_text, referral_text, dictation_text)
        """
        notebook = ttk.Notebook(self.parent, style="Green.TNotebook")
        
        # Create frames for each tab
        transcript_frame = ttk.Frame(notebook)
        soap_frame = ttk.Frame(notebook)
        referral_frame = ttk.Frame(notebook)
        dictation_frame = ttk.Frame(notebook)
        
        # Add tabs to notebook
        notebook.add(transcript_frame, text="Transcript")
        notebook.add(soap_frame, text="SOAP Note")
        notebook.add(referral_frame, text="Referral")
        notebook.add(dictation_frame, text="Dictation")
        
        # Create text widgets for each tab - use relative sizing
        text_kwargs = {
            "wrap": tk.WORD, 
            "undo": True, 
            "autoseparators": False,
            "font": ("Segoe UI", 11)
        }
        
        transcript_text = tk.scrolledtext.ScrolledText(transcript_frame, **text_kwargs)
        transcript_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        soap_text = tk.scrolledtext.ScrolledText(soap_frame, **text_kwargs)
        soap_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        referral_text = tk.scrolledtext.ScrolledText(referral_frame, **text_kwargs)
        referral_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        dictation_text = tk.scrolledtext.ScrolledText(dictation_frame, **text_kwargs)
        dictation_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        return notebook, transcript_text, soap_text, referral_text, dictation_text
    
    def create_control_panel(self, command_map: Dict[str, Callable]) -> ttk.Frame:
        """Create the control panel with buttons for recording, editing, and AI features.
        
        Args:
            command_map: Dictionary mapping button names to their command functions
            
        Returns:
            ttk.Frame: The control panel frame
        """
        control_frame = ttk.Frame(self.parent, padding=5)  # Reduced padding
        
        # Set up responsive grid configuration
        control_frame.columnconfigure(0, weight=1)
        
        # Create a more compact layout with sections side by side
        main_section = ttk.Frame(control_frame)
        main_section.grid(row=0, column=0, sticky="ew", pady=(5, 0))
        main_section.columnconfigure(0, weight=1)
        main_section.columnconfigure(1, weight=1)
        
        # Left side - Individual controls section
        individual_section = ttk.Frame(main_section)
        individual_section.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        individual_section.columnconfigure(0, weight=1)
        
        ttk.Label(individual_section, text="Individual Controls", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w", padx=5, pady=(0, 3))  # Reduced padding
        
        main_controls = ttk.Frame(individual_section)
        main_controls.grid(row=1, column=0, sticky="ew")
        
        # Configure main_controls for responsive layout
        for i in range(8):  # Enough columns for all buttons
            main_controls.columnconfigure(i, weight=1)
        
        # Main control buttons
        buttons = [
            {"name": "record", "text": "Start Dictation", "width": 15, "column": 0, 
             "command": command_map.get("toggle_recording"), "bootstyle": "success",
             "tooltip": "Start or stop recording audio."},
             
            {"name": "new_session", "text": "New Session", "width": 12, "column": 1,
             "command": command_map.get("new_session"), "bootstyle": "warning",
             "tooltip": "Start a new session and clear all text."},
             
            {"name": "undo", "text": "Undo", "width": 10, "column": 3,
             "command": command_map.get("undo_text"), "bootstyle": "SECONDARY",
             "tooltip": "Undo the last change."},
             
            {"name": "redo", "text": "Redo", "width": 10, "column": 4,
             "command": command_map.get("redo_text"), "bootstyle": "SECONDARY",
             "tooltip": "Redo the last undone change."},
             
            {"name": "copy", "text": "Copy Text", "width": 10, "column": 5,
             "command": command_map.get("copy_text"), "bootstyle": "PRIMARY",
             "tooltip": "Copy the text to the clipboard."},
             
            {"name": "save", "text": "Save", "width": 10, "column": 6,
             "command": command_map.get("save_text"), "bootstyle": "PRIMARY",
             "tooltip": "Save the transcription and audio to files."},
             
            {"name": "load", "text": "Load", "width": 10, "column": 7,
             "command": command_map.get("load_audio_file"), "bootstyle": "PRIMARY",
             "tooltip": "Load an audio file and transcribe."}
        ]
        
        button_widgets = {}
        for btn in buttons:
            button = ttk.Button(
                main_controls, 
                text=btn["text"], 
                width=btn["width"],
                command=btn["command"],
                bootstyle=btn.get("bootstyle", "")
            )
            button.grid(row=0, column=btn["column"], padx=3, pady=3, sticky="ew")  # Reduced padding
            ToolTip(button, btn["tooltip"])
            button_widgets[btn["name"]] = button
        
        # Right side - AI Assist section
        ai_section = ttk.Frame(main_section)
        ai_section.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        ai_section.columnconfigure(0, weight=1)
        
        ttk.Label(ai_section, text="AI Assist", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w", padx=5, pady=(0, 3))  # Reduced padding
        
        # Create a notebook for AI controls to save vertical space
        ai_notebook = ttk.Notebook(ai_section, style="Green.TNotebook")
        ai_notebook.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        
        # Individual AI controls tab
        individual_ai_frame = ttk.Frame(ai_notebook)
        ai_notebook.add(individual_ai_frame, text="Text Processing")
        
        for i in range(5):  # Enough columns for all AI buttons
            individual_ai_frame.columnconfigure(i, weight=1)
        
        # AI control buttons
        ai_btn_list = [
            {"name": "refine", "text": "Refine Text", "width": 15, "column": 0,
             "command": command_map.get("refine_text"), "bootstyle": "SECONDARY",
             "tooltip": "Refine text using AI."},
             
            {"name": "improve", "text": "Improve Text", "width": 15, "column": 1,
             "command": command_map.get("improve_text"), "bootstyle": "SECONDARY",
             "tooltip": "Improve text clarity using AI."},
             
            {"name": "soap", "text": "SOAP Note", "width": 15, "column": 2,
             "command": command_map.get("create_soap_note"), "bootstyle": "SECONDARY",
             "tooltip": "Create a SOAP note using AI."},
             
            {"name": "referral", "text": "Referral", "width": 15, "column": 3,
             "command": command_map.get("create_referral"), "bootstyle": "SECONDARY",
             "tooltip": "Generate a referral paragraph using AI."},
             
            {"name": "letter", "text": "Letter", "width": 15, "column": 4,
             "command": command_map.get("create_letter"), "bootstyle": "SECONDARY",
             "tooltip": "Generate a professional letter from text."}
        ]
        
        for btn in ai_btn_list:
            button = ttk.Button(
                individual_ai_frame, 
                text=btn["text"], 
                width=btn["width"],
                command=btn["command"],
                bootstyle=btn.get("bootstyle", "")
            )
            button.grid(row=0, column=btn["column"], padx=3, pady=3, sticky="ew")  # Reduced padding
            ToolTip(button, btn["tooltip"])
            button_widgets[btn["name"]] = button
        
        # Automation controls tab
        automation_frame = ttk.Frame(ai_notebook)
        ai_notebook.add(automation_frame, text="SOAP Automation")
        
        # Configure automation_frame for responsive layout
        for i in range(3):  # Enough columns for all automation buttons
            automation_frame.columnconfigure(i, weight=1)
        
        # SOAP recording buttons
        record_soap_button = ttk.Button(
            automation_frame, text="Record SOAP Note", width=25,
            command=command_map.get("toggle_soap_recording"), bootstyle="success"
        )
        record_soap_button.grid(row=0, column=0, padx=3, pady=3, sticky="ew")  # Reduced padding
        ToolTip(record_soap_button, "Record audio for SOAP note without live transcription.")
        
        pause_soap_button = ttk.Button(
            automation_frame, text="Pause", width=15,
            command=command_map.get("toggle_soap_pause"), bootstyle="SECONDARY", state=tk.DISABLED
        )
        pause_soap_button.grid(row=0, column=1, padx=3, pady=3, sticky="ew")  # Reduced padding
        ToolTip(pause_soap_button, "Pause/Resume the SOAP note recording.")
        
        # Add Cancel button
        cancel_soap_button = ttk.Button(
            automation_frame, text="Cancel", width=15,
            command=command_map.get("cancel_soap_recording"), bootstyle="danger", state=tk.DISABLED
        )
        cancel_soap_button.grid(row=0, column=2, padx=3, pady=3, sticky="ew")  # Reduced padding
        ToolTip(cancel_soap_button, "Cancel the current SOAP note recording without processing.")
        
        button_widgets["record_soap"] = record_soap_button
        button_widgets["pause_soap"] = pause_soap_button
        button_widgets["cancel_soap"] = cancel_soap_button
        
        return control_frame, button_widgets
    
    def create_status_bar(self) -> tuple:
        """Create the status bar at the bottom of the application.
        
        Returns:
            tuple: (status_frame, status_icon_label, status_label, provider_indicator, progress_bar)
        """
        status_frame = ttk.Frame(self.parent, padding=(10, 5))
        
        # Configure for responsive layout
        status_frame.columnconfigure(1, weight=1)  # Status label should expand
        
        # Status icon
        status_icon_label = ttk.Label(status_frame, text="•", font=("Segoe UI", 16), foreground="gray")
        status_icon_label.pack(side=LEFT, padx=(5, 0))
        
        # Status text
        status_label = ttk.Label(
            status_frame, 
            text="Status: Idle", 
            anchor="w",
            font=("Segoe UI", 10)
        )
        status_label.pack(side=LEFT, fill=tk.X, expand=True, padx=(5, 0))
        
        # Provider indicator
        provider = SETTINGS.get("ai_provider", "openai").capitalize()
        provider_indicator = ttk.Label(
            status_frame, 
            text=f"Using: {provider}",
            anchor="e",
            font=("Segoe UI", 9),
            foreground="gray"
        )
        provider_indicator.pack(side=LEFT, padx=(0, 10))
        
        # Progress bar
        progress_bar = ttk.Progressbar(status_frame, mode="indeterminate")
        progress_bar.pack(side=RIGHT, padx=10)
        progress_bar.stop()
        progress_bar.pack_forget()
        
        return status_frame, status_icon_label, status_label, provider_indicator, progress_bar
