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
    
    def create_microphone_frame(self, on_provider_change: Callable, on_stt_change: Callable, 
                              refresh_microphones: Callable) -> ttk.Frame:
        """Create the microphone selection and provider dropdown frame.
        
        Returns:
            ttk.Frame: The microphone selection frame
        """
        mic_frame = ttk.Frame(self.parent, padding=10)
        
        # Microphone selection
        ttk.Label(mic_frame, text="Select Microphone:").pack(side=LEFT, padx=(0, 10))
        mic_names = get_valid_microphones() or sr.Microphone.list_microphone_names()
        mic_combobox = ttk.Combobox(mic_frame, values=mic_names, state="readonly", width=50)
        mic_combobox.pack(side=LEFT)
        if mic_names:
            mic_combobox.current(0)
        else:
            mic_combobox.set("No microphone found")
            
        refresh_btn = ttk.Button(mic_frame, text="Refresh", command=refresh_microphones, bootstyle="PRIMARY")
        refresh_btn.pack(side=LEFT, padx=10)
        ToolTip(refresh_btn, "Refresh the list of available microphones.")
        
        # Provider selection frame
        provider_frame = ttk.Frame(mic_frame)
        provider_frame.pack(side=LEFT, padx=10)
        
        # Provider dropdown
        ttk.Label(provider_frame, text="Provider:").pack(side=LEFT, padx=(0, 5))
        provider = SETTINGS.get("ai_provider", "openai")
        providers = ["openai", "perplexity", "grok"]
        provider_display = ["OpenAI", "Perplexity", "Grok"]
        
        provider_combobox = ttk.Combobox(
            provider_frame, 
            values=provider_display,
            state="readonly",
            width=12
        )
        provider_combobox.pack(side=LEFT)
        
        # Set current provider
        try:
            current_index = providers.index(provider.lower())
            provider_combobox.current(current_index)
        except (ValueError, IndexError):
            provider_combobox.current(0)
        
        provider_combobox.bind("<<ComboboxSelected>>", on_provider_change)
        ToolTip(provider_combobox, "Select which AI provider to use")
        
        # STT provider selection
        stt_frame = ttk.Frame(mic_frame)
        stt_frame.pack(side=LEFT, padx=10)
        
        ttk.Label(stt_frame, text="Speech To Text:").pack(side=LEFT, padx=(0, 5))
        stt_providers = ["elevenlabs", "deepgram"]
        stt_display = ["ElevenLabs", "Deepgram"]
        stt_provider = SETTINGS.get("stt_provider", "deepgram")
        
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
        
        return mic_frame, mic_combobox, provider_combobox, stt_combobox
    
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
        
        # Create text widgets for each tab
        text_kwargs = {
            "wrap": tk.WORD, 
            "width": 80, 
            "height": 12, 
            "font": ("Segoe UI", 11),
            "undo": True, 
            "autoseparators": False
        }
        
        transcript_text = tk.scrolledtext.ScrolledText(transcript_frame, **text_kwargs)
        transcript_text.pack(fill=tk.BOTH, expand=True)
        
        soap_text = tk.scrolledtext.ScrolledText(soap_frame, **text_kwargs)
        soap_text.pack(fill=tk.BOTH, expand=True)
        
        referral_text = tk.scrolledtext.ScrolledText(referral_frame, **text_kwargs)
        referral_text.pack(fill=tk.BOTH, expand=True)
        
        dictation_text = tk.scrolledtext.ScrolledText(dictation_frame, **text_kwargs)
        dictation_text.pack(fill=tk.BOTH, expand=True)
        
        return notebook, transcript_text, soap_text, referral_text, dictation_text
    
    def create_control_panel(self, command_map: Dict[str, Callable]) -> ttk.Frame:
        """Create the control panel with buttons for recording, editing, and AI features.
        
        Args:
            command_map: Dictionary mapping button names to their command functions
            
        Returns:
            ttk.Frame: The control panel frame
        """
        control_frame = ttk.Frame(self.parent, padding=10)
        
        # Individual controls section
        ttk.Label(control_frame, text="Individual Controls", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w", padx=5, pady=(0, 5))
        
        main_controls = ttk.Frame(control_frame)
        main_controls.grid(row=1, column=0, sticky="w")
        
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
            button.grid(row=0, column=btn["column"], padx=5, pady=5)
            ToolTip(button, btn["tooltip"])
            button_widgets[btn["name"]] = button
        
        # AI Assist section
        ttk.Label(control_frame, text="AI Assist", font=("Segoe UI", 11, "bold")).grid(
            row=2, column=0, sticky="w", padx=5, pady=(10, 5))
            
        ttk.Label(control_frame, text="Individual Controls", font=("Segoe UI", 10, "italic")).grid(
            row=3, column=0, sticky="w", padx=5, pady=(0, 5))
        
        ai_buttons = ttk.Frame(control_frame)
        ai_buttons.grid(row=4, column=0, sticky="w")
        
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
                ai_buttons, 
                text=btn["text"], 
                width=btn["width"],
                command=btn["command"],
                bootstyle=btn.get("bootstyle", "")
            )
            button.grid(row=0, column=btn["column"], padx=5, pady=5)
            ToolTip(button, btn["tooltip"])
            button_widgets[btn["name"]] = button
        
        # Automation Controls section
        ttk.Label(control_frame, text="Automation Controls", font=("Segoe UI", 10, "italic")).grid(
            row=5, column=0, sticky="w", padx=5, pady=(0, 5))
        
        automation_frame = ttk.Frame(control_frame)
        automation_frame.grid(row=6, column=0, sticky="w")
        
        # SOAP recording buttons
        record_soap_button = ttk.Button(
            automation_frame, text="Record SOAP Note", width=25,
            command=command_map.get("toggle_soap_recording"), bootstyle="success"
        )
        record_soap_button.grid(row=0, column=0, padx=5, pady=5)
        ToolTip(record_soap_button, "Record audio for SOAP note without live transcription.")
        
        pause_soap_button = ttk.Button(
            automation_frame, text="Pause", width=15,
            command=command_map.get("toggle_soap_pause"), bootstyle="SECONDARY", state=tk.DISABLED
        )
        pause_soap_button.grid(row=0, column=1, padx=5, pady=5)
        ToolTip(pause_soap_button, "Pause/Resume the SOAP note recording.")
        
        # Add Cancel button
        cancel_soap_button = ttk.Button(
            automation_frame, text="Cancel", width=15,
            command=command_map.get("cancel_soap_recording"), bootstyle="danger", state=tk.DISABLED
        )
        cancel_soap_button.grid(row=0, column=2, padx=5, pady=5)
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
