import os
import json
import string
import logging
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import multiprocessing
import tkinter as tk
from tkinter import messagebox, filedialog, scrolledtext, ttk
import speech_recognition as sr
from pydub import AudioSegment
from deepgram import DeepgramClient, PrerecordedOptions
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from dotenv import load_dotenv
import openai
import pyaudio
from typing import Callable, Optional

# Add this import for creating .env file
from pathlib import Path

# Add to imports
import requests

from utils import get_valid_microphones
from ai import adjust_text_with_openai, improve_text_with_openai, create_soap_note_with_openai, get_possible_conditions, create_letter_with_ai
from tooltip import ToolTip
from settings import SETTINGS, save_settings  # Add save_settings here
from dialogs import create_toplevel_dialog, show_settings_dialog, askstring_min, ask_conditions_dialog, show_api_keys_dialog, show_shortcuts_dialog, show_about_dialog, show_letter_options_dialog, show_elevenlabs_settings_dialog, show_deepgram_settings_dialog  # Add this import

# Add near the top of the file
import time
import uuid
from requests.exceptions import RequestException, Timeout, ConnectionError

# Add to imports section
from audio import AudioHandler

# Add these imports:
from ui_components import UIComponents
from text_processor import TextProcessor

# Add this import at the top with other imports
from status_manager import StatusManager

# Completely revised check_env_file function to handle the tkinter window properly
def check_env_file():
    """Check if .env file exists and create it if needed.
    
    Returns:
        bool: True if the app should continue, False if it should exit
    """
    env_path = Path(".env")
    
    # If .env file exists, just return True to continue
    if env_path.exists():
        return True
    
    # Setup API key collection using standard Tk approach (not Toplevel)
    # This avoids window destruction issues
    import sys
    
    def collect_api_keys():
        # Create a new root window specifically for API key collection
        api_root = tk.Tk()
        api_root.title("Medical Dictation App - API Keys Setup")
        api_root.geometry("500x600")
        should_continue = [False]  # Use list for mutable reference
        
        # Headers
        tk.Label(api_root, text="Welcome to Medical Dictation App!", 
                font=("Segoe UI", 14, "bold")).pack(pady=(20, 5))
        
        tk.Label(api_root, text="Please enter at least one of the following API keys to continue:",
                font=("Segoe UI", 11)).pack(pady=(0, 5))
        
        tk.Label(api_root, text="OpenAI, Grok, or Perplexity API key is required. Either Deepgram or ElevenLabs API key is mandatory for speech recognition.",
                wraplength=450).pack(pady=(0, 20))
        
        # Create frame for keys
        keys_frame = tk.Frame(api_root)
        keys_frame.pack(fill="both", expand=True, padx=20)
        
        # Create entries for mandatory API keys first
        tk.Label(keys_frame, text="OpenAI API Key:").grid(row=0, column=0, sticky="w", pady=5)
        openai_entry = tk.Entry(keys_frame, width=40)
        openai_entry.grid(row=0, column=1, sticky="ew", pady=5)
        
        tk.Label(keys_frame, text="Grok API Key:").grid(row=1, column=0, sticky="w", pady=5)
        grok_entry = tk.Entry(keys_frame, width=40)
        grok_entry.grid(row=1, column=1, sticky="ew", pady=5)
        
        tk.Label(keys_frame, text="Perplexity API Key:").grid(row=2, column=0, sticky="w", pady=5)
        perplexity_entry = tk.Entry(keys_frame, width=40)
        perplexity_entry.grid(row=2, column=1, sticky="ew", pady=5)
        
        # Create entry for optional API key last
        tk.Label(keys_frame, text="Deepgram API Key:").grid(row=3, column=0, sticky="w", pady=5)
        deepgram_entry = tk.Entry(keys_frame, width=40)
        deepgram_entry.grid(row=3, column=1, sticky="ew", pady=5)
        
        # NEW: Add ElevenLabs API Key field
        tk.Label(keys_frame, text="ElevenLabs API Key:").grid(row=4, column=0, sticky="w", pady=5)
        elevenlabs_entry = tk.Entry(keys_frame, width=40)
        elevenlabs_entry.grid(row=4, column=1, sticky="ew", pady=5)
        
        # Add info about where to find the keys
        info_text = ("Get your API keys at:\n"
                    "• OpenAI: https://platform.openai.com/account/api-keys\n"
                    "• Grok (X.AI): https://x.ai\n"
                    "• Perplexity: https://docs.perplexity.ai/\n"
                    "• Deepgram: https://console.deepgram.com/signup\n"
                    "• ElevenLabs: https://elevenlabs.io/app/speech-to-text")
        tk.Label(keys_frame, text=info_text, justify="left", wraplength=450).grid(
            row=5, column=0, columnspan=2, sticky="w", pady=10)
        
        error_var = tk.StringVar()
        error_label = tk.Label(api_root, textvariable=error_var, foreground="red", wraplength=450)
        error_label.pack(pady=5)
        
        def validate_and_save():
            openai_key = openai_entry.get().strip()
            deepgram_key = deepgram_entry.get().strip()
            grok_key = grok_entry.get().strip()
            perplexity_key = perplexity_entry.get().strip()
            elevenlabs_key = elevenlabs_entry.get().strip()  # NEW: Get ElevenLabs key
            
            # Check if at least one of OpenAI, Grok, or Perplexity keys is provided
            if not (openai_key or grok_key or perplexity_key):
                error_var.set("Error: At least one of OpenAI, Grok, or Perplexity API keys is required.")
                return
                
            # Check if at least one speech-to-text API key is provided
            if not (deepgram_key or elevenlabs_key):
                error_var.set("Error: Either Deepgram or ElevenLabs API key is required for speech recognition.")
                return
            
            # Create the .env file with the provided keys
            with open(".env", "w") as f:
                if openai_key:
                    f.write(f"OPENAI_API_KEY={openai_key}\n")
                if deepgram_key:
                    f.write(f"DEEPGRAM_API_KEY={deepgram_key}\n")
                if grok_key:
                    f.write(f"GROK_API_KEY={grok_key}\n")
                if perplexity_key:
                    f.write(f"PERPLEXITY_API_KEY={perplexity_key}\n")
                # NEW: Add ElevenLabs key if provided
                if elevenlabs_key:
                    f.write(f"ELEVENLABS_API_KEY={elevenlabs_key}\n")
                f.write(f"RECOGNITION_LANGUAGE=en-US\n")
            
            should_continue[0] = True
            api_root.quit()
        
        def on_cancel():
            api_root.quit()
        
        # Create a button frame
        button_frame = tk.Frame(api_root)
        button_frame.pack(pady=(0, 20))
        
        # Add Cancel and Save buttons
        tk.Button(button_frame, text="Cancel", command=on_cancel).pack(side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="Save and Continue", command=validate_and_save).pack(side=tk.LEFT, padx=10)
        
        # Center the window
        api_root.update_idletasks()
        width = api_root.winfo_width()
        height = api_root.winfo_height()
        x = (api_root.winfo_screenwidth() // 2) - (width // 2)
        y = (api_root.winfo_screenheight() // 2) - (height // 2)
        api_root.geometry(f'{width}x{height}+{x}+{y}')
        
        api_root.protocol("WM_DELETE_WINDOW", on_cancel)
        api_root.mainloop()
        
        # Important: destroy the window only after mainloop exits
        api_root.destroy()
        return should_continue[0]
    
    # Collect API keys and determine whether to continue
    should_continue = collect_api_keys()
    
    # If user cancelled or closed the window without saving, exit the program
    if not should_continue:
        sys.exit(0)
    
    return True

# Modify the main function to only create the app if check_env_file returns True
def main() -> None:
    # First check for .env file - only proceed if successful
    if check_env_file():
        # Load environment variables
        load_dotenv()
        
        try:
            # Only create the app if we got past the env check
            app = MedicalDictationApp()
            app.mainloop()
        except Exception as e:
            logging.error(f"Error in main application: {e}", exc_info=True)

class MedicalDictationApp(ttk.Window):
    def __init__(self) -> None:
        # Determine number of CPU cores available for optimal threading configuration
        cpu_count = multiprocessing.cpu_count()
        
        # Initialize ThreadPoolExecutor for I/O-bound tasks (network calls, file operations)
        # Use more threads for I/O operations since they spend most of their time waiting
        self.io_executor = ThreadPoolExecutor(max_workers=min(32, cpu_count * 4))
        
        # Initialize ProcessPoolExecutor for CPU-bound tasks (text processing, analysis)
        # Use number of physical cores for CPU-intensive tasks to avoid context switching overhead
        self.cpu_executor = ProcessPoolExecutor(max_workers=max(2, cpu_count - 1))
        
        # Maintain the original executor for backwards compatibility
        self.executor = self.io_executor
        
        # Get theme from settings or use default
        self.current_theme = SETTINGS.get("theme", "flatly")
        
        super().__init__(themename=self.current_theme)
        self.title("Medical Assistant")
        
        # Get screen dimensions and calculate appropriate window size
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Calculate responsive window size (80% of screen size, but not larger than 1700x950)
        window_width = min(int(screen_width * 0.8), 1700)
        window_height = min(int(screen_height * 0.8), 950)
        
        # Apply the calculated window size
        self.geometry(f"{window_width}x{window_height}")
        
        # Set a reasonable minimum size that ensures all UI elements are visible
        self.minsize(1100, 750)
        
        # Center the window on the screen
        self.update_idletasks()  # Ensure window dimensions are calculated
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # Initialize API keys and handlers
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.deepgram_api_key = os.getenv("DEEPGRAM_API_KEY", "")
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self.recognition_language = os.getenv("RECOGNITION_LANGUAGE", "en-US")
        
        # Check for necessary API keys for at least one STT provider
        elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
        deepgram_key = os.getenv("DEEPGRAM_API_KEY")
        
        if not (elevenlabs_key or deepgram_key):
            messagebox.showwarning(
                "Missing STT API Keys", 
                "No Speech-to-Text API keys found. Either Deepgram or ElevenLabs API key " +
                "is required for speech recognition functionality.\n\n" +
                "Please add at least one of these API keys in the settings."
            )
        
        # Initialize audio handler
        self.audio_handler = AudioHandler(
            elevenlabs_api_key=self.elevenlabs_api_key,
            deepgram_api_key=self.deepgram_api_key,
            recognition_language=self.recognition_language
        )
        
        # Register fallback notification callback with error handling
        try:
            self.audio_handler.set_fallback_callback(self.on_transcription_fallback)
        except AttributeError:
            logging.warning("Audio handler doesn't support fallback callback - update your audio.py file")
            
        # Initialize text processor
        self.text_processor = TextProcessor()
        
        self.appended_chunks = []
        self.capitalize_next = False
        self.audio_segments = []
        self.soap_recording = False
        self.soap_audio_segments = []
        self.soap_stop_listening_function = None

        # Create UI using the component builder
        self.ui = UIComponents(self)
        self.create_menu()
        self.create_widgets()
        self.bind_shortcuts()

        # Initialize status manager
        self.status_manager = StatusManager(
            self,
            self.status_icon_label,
            self.status_label,
            self.provider_indicator,
            self.progress_bar
        )
        
        if not openai.api_key:
            self.buttons["refine"].config(state=DISABLED)
            self.buttons["improve"].config(state=DISABLED)
            self.status_manager.warning("Warning: OpenAI API key not provided. AI features disabled.")

        self.recognizer = sr.Recognizer()
        self.listening = False
        self.stop_listening_function = None

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Add a list to track all scheduled status updates
        self.status_timers = []
        self.status_timer = None

    def create_menu(self) -> None:
        menubar = tk.Menu(self)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="New", command=self.new_session, accelerator="Ctrl+N")
        filemenu.add_command(label="Save", command=self.save_text, accelerator="Ctrl+S")
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.on_closing)
        menubar.add_cascade(label="File", menu=filemenu)

        settings_menu = tk.Menu(menubar, tearoff=0)
        # Add API Keys option at the top of the settings menu
        settings_menu.add_command(label="Update API Keys", command=self.show_api_keys_dialog)
        settings_menu.add_separator()
        
        # Add STT provider settings menu options
        settings_menu.add_command(label="ElevenLabs Settings", command=self.show_elevenlabs_settings)
        settings_menu.add_command(label="Deepgram Settings", command=self.show_deepgram_settings)  # Add this line
        
        # Update this section to add all prompt settings options to the submenu
        text_settings_menu = tk.Menu(settings_menu, tearoff=0)
        text_settings_menu.add_command(label="Refine Prompt Settings", command=self.show_refine_settings_dialog)
        text_settings_menu.add_command(label="Improve Prompt Settings", command=self.show_improve_settings_dialog)
        text_settings_menu.add_command(label="SOAP Note Settings", command=self.show_soap_settings_dialog)
        text_settings_menu.add_command(label="Referral Settings", command=self.show_referral_settings_dialog)
        
        settings_menu.add_cascade(label="Prompt Settings", menu=text_settings_menu)
        settings_menu.add_command(label="Export Prompts", command=self.export_prompts)
        settings_menu.add_command(label="Import Prompts", command=self.import_prompts)
        settings_menu.add_command(label="Set Storage Folder", command=self.set_default_folder)
        settings_menu.add_command(label="Toggle Theme", command=self.toggle_theme)  # NEW: Add toggle theme option
        menubar.add_cascade(label="Settings", menu=settings_menu)

        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="About", command=self.show_about)
        helpmenu.add_command(label="Shortcuts & Voice Commands", command=self.show_shortcuts)
        menubar.add_cascade(label="Help", menu=helpmenu)

        self.config(menu=menubar)

    def show_api_keys_dialog(self) -> None:
        """Shows a dialog to update API keys and updates the .env file."""
        # Call the refactored function from dialogs.py
        show_api_keys_dialog(self)
        
        # Refresh API keys in the application
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.deepgram_api_key = os.getenv("DEEPGRAM_API_KEY", "")
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "")
        
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
            recognition_language=self.recognition_language
        )
        self.status_manager.success("ElevenLabs settings saved successfully")

    def show_deepgram_settings(self) -> None:
        """Show dialog to configure Deepgram settings."""
        # Call the dialog function
        show_deepgram_settings_dialog(self)
        
        # Refresh the audio handler with potentially new settings
        self.audio_handler = AudioHandler(
            elevenlabs_api_key=self.elevenlabs_api_key,
            deepgram_api_key=self.deepgram_api_key,
            recognition_language=self.recognition_language
        )
        self.status_manager.success("Deepgram settings saved successfully")

    def set_default_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select Storage Folder")
        if folder:
            try:
                from settings import SETTINGS, save_settings
                SETTINGS["default_storage_folder"] = folder
                save_settings(SETTINGS)
                self.update_status(f"Default storage folder set to: {folder}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to set folder: {e}")

    def export_prompts(self) -> None:
        from settings import SETTINGS, _DEFAULT_SETTINGS
        data = {}
        for key in ("refine_text", "improve_text", "soap_note"):
            default = _DEFAULT_SETTINGS.get(key, {})
            current = SETTINGS.get(key, {})
            entry = {}
            if key == "soap_note":
                entry["prompt"] = current.get("system_message", default.get("system_message", ""))
            else:
                entry["prompt"] = current.get("prompt", default.get("prompt", ""))
            entry["model"] = current.get("model", default.get("model", ""))
            data[key] = entry
        file_path = filedialog.asksaveasfilename(
            title="Export Prompts and Models",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                messagebox.showinfo("Export Prompts", f"Prompts and models exported to {file_path}")
            except Exception as e:
                messagebox.showerror("Export Prompts", f"Error exporting prompts: {e}")

    def import_prompts(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Import Prompts and Models",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                from settings import SETTINGS, save_settings
                for key in ("refine_text", "improve_text", "soap_note"):
                    if key in data:
                        SETTINGS[key] = data[key]
                save_settings(SETTINGS)
                messagebox.showinfo("Import Prompts", "Prompts and models updated successfully.")
            except Exception as e:
                messagebox.showerror("Import Prompts", f"Error importing prompts: {e}")

    def create_widgets(self) -> None:
        # Define command mapping for buttons
        command_map = {
            "toggle_recording": self.toggle_recording,
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
            "toggle_soap_recording": self.toggle_soap_recording,
            "toggle_soap_pause": self.toggle_soap_pause,
            "cancel_soap_recording": self.cancel_soap_recording
        }
        
        # Create a main content frame to hold everything except the status bar
        main_content = ttk.Frame(self)
        main_content.pack(side=TOP, fill=tk.BOTH, expand=True)
        
        # Create status bar - placed first in packing order but with side=BOTTOM
        status_frame, self.status_icon_label, self.status_label, self.provider_indicator, self.progress_bar = self.ui.create_status_bar()
        status_frame.pack(side=BOTTOM, fill=tk.X)
        
        # Create microphone frame with theme button references - inside main_content
        mic_frame, self.mic_combobox, self.provider_combobox, self.stt_combobox, self.theme_btn, self.theme_label = self.ui.create_microphone_frame(
            on_provider_change=self._on_provider_change,
            on_stt_change=self._on_stt_change,
            refresh_microphones=self.refresh_microphones,
            toggle_theme=self.toggle_theme  # Pass the toggle_theme method to the UI
        )
        mic_frame.pack(side=TOP, fill=tk.X, padx=10, pady=(10, 5))
        
        # Create control panel with buttons - inside main_content
        self.control_frame, self.buttons = self.ui.create_control_panel(command_map)
        self.control_frame.pack(side=TOP, fill=tk.X, padx=10, pady=5)
        
        # Create notebook with text areas - inside main_content with expand=True
        self.notebook, self.transcript_text, self.soap_text, self.referral_text, self.dictation_text = self.ui.create_notebook()
        self.notebook.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
        
        # Set initial active text widget and bind tab change event
        self.active_text_widget = self.transcript_text
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
        # Access common buttons from self.buttons
        self.record_button = self.buttons["record"]
        self.refine_button = self.buttons["refine"]
        self.improve_button = self.buttons["improve"]
        self.soap_button = self.buttons["soap"]
        self.referral_button = self.buttons["referral"]
        self.letter_button = self.buttons["letter"]
        self.record_soap_button = self.buttons["record_soap"]
        self.pause_soap_button = self.buttons["pause_soap"]
        
        # Add missing button references
        self.load_button = self.buttons["load"]
        self.save_button = self.buttons["save"]
        self.cancel_soap_button = self.buttons["cancel_soap"]
        
        # Create status bar
        # status_frame, self.status_icon_label, self.status_label, self.provider_indicator, self.progress_bar = self.ui.create_status_bar()
        # status_frame.pack(side=BOTTOM, fill=tk.X)

    def bind_shortcuts(self) -> None:
        self.bind("<Control-n>", lambda event: self.new_session())
        self.bind("<Control-s>", lambda event: self.save_text())
        self.bind("<Control-c>", lambda event: self.copy_text())
        self.bind("<Control-l>", lambda event: self.load_audio_file())
        self.bind("<Control-z>", lambda event: self.undo_text())
        self.bind("<Control-y>", lambda event: self.redo_text())
        self.bind("<F5>", lambda event: self.toggle_recording())
        self.bind("<Control-Shift-S>", lambda event: self.toggle_soap_recording())
        self.bind("<Alt-t>", lambda event: self.toggle_theme())

    def show_about(self) -> None:
        # Call the refactored function from dialogs.py
        show_about_dialog(self)

    def show_shortcuts(self) -> None:
        # Call the refactored function from dialogs.py
        show_shortcuts_dialog(self)

    def show_refine_settings_dialog(self) -> None:
        from settings import SETTINGS, _DEFAULT_SETTINGS
        cfg = SETTINGS.get("refine_text", {})
        show_settings_dialog(
            parent=self,
            title="Refine Text Settings",
            config=cfg,
            default=_DEFAULT_SETTINGS["refine_text"],
            current_prompt=cfg.get("prompt", ""),
            current_model=cfg.get("model", ""),
            current_perplexity=cfg.get("perplexity_model", ""),
            current_grok=cfg.get("grok_model", ""),
            save_callback=self.save_refine_settings,
            current_ollama=cfg.get("ollama_model", "")
        )

    def show_improve_settings_dialog(self) -> None:
        from settings import SETTINGS, _DEFAULT_SETTINGS
        cfg = SETTINGS.get("improve_text", {})
        show_settings_dialog(
            parent=self,
            title="Improve Text Settings",
            config=cfg,
            default=_DEFAULT_SETTINGS["improve_text"],
            current_prompt=cfg.get("prompt", ""),
            current_model=cfg.get("model", ""),
            current_perplexity=cfg.get("perplexity_model", ""),
            current_grok=cfg.get("grok_model", ""),
            save_callback=self.save_improve_settings,
            current_ollama=cfg.get("ollama_model", "")
        )

    def show_soap_settings_dialog(self) -> None:
        from settings import SETTINGS, _DEFAULT_SETTINGS
        cfg = SETTINGS.get("soap_note", {})
        default_prompt = _DEFAULT_SETTINGS["soap_note"].get("system_message", "")
        default_model = _DEFAULT_SETTINGS["soap_note"].get("model", "")
        show_settings_dialog(
            parent=self,
            title="SOAP Note Settings",
            config=cfg,
            default=_DEFAULT_SETTINGS["soap_note"],
            current_prompt=cfg.get("system_message") or default_prompt,
            current_model=cfg.get("model") or default_model,
            current_perplexity=cfg.get("perplexity_model", ""),
            current_grok=cfg.get("grok_model", ""),
            save_callback=self.save_soap_settings,
            current_ollama=cfg.get("ollama_model", "")
        )

    def show_referral_settings_dialog(self) -> None:
        from settings import SETTINGS, _DEFAULT_SETTINGS
        cfg = SETTINGS.get("referral", {})
        default_prompt = _DEFAULT_SETTINGS["referral"].get("prompt", "")
        default_model = _DEFAULT_SETTINGS["referral"].get("model", "")
        show_settings_dialog(
            parent=self,
            title="Referral Prompt Settings",
            config=cfg,
            default=_DEFAULT_SETTINGS["referral"],
            current_prompt=cfg.get("prompt", default_prompt),
            current_model=cfg.get("model", default_model),
            current_perplexity=cfg.get("perplexity_model", ""),
            current_grok=cfg.get("grok_model", ""),
            save_callback=self.save_referral_settings,
            current_ollama=cfg.get("ollama_model", "")
        )

    def save_refine_settings(self, prompt: str, openai_model: str, perplexity_model: str, grok_model: str, ollama_model: str) -> None:
        from settings import save_settings, SETTINGS
        SETTINGS["refine_text"] = {
            "prompt": prompt,
            "model": openai_model,
            "perplexity_model": perplexity_model,
            "grok_model": grok_model,
            "ollama_model": ollama_model
        }
        save_settings(SETTINGS)
        self.status_manager.success("Refine text settings saved successfully")

    def save_improve_settings(self, prompt: str, openai_model: str, perplexity_model: str, grok_model: str, ollama_model: str) -> None:
        from settings import save_settings, SETTINGS
        SETTINGS["improve_text"] = {
            "prompt": prompt,
            "model": openai_model,
            "perplexity_model": perplexity_model,
            "grok_model": grok_model,
            "ollama_model": ollama_model
        }
        save_settings(SETTINGS)
        self.status_manager.success("Improve text settings saved successfully")

    def save_soap_settings(self, prompt: str, openai_model: str, perplexity_model: str, grok_model: str, ollama_model: str) -> None:
        from settings import save_settings, SETTINGS
        SETTINGS["soap_note"] = {
            "system_message": prompt,
            "model": openai_model,
            "perplexity_model": perplexity_model,
            "grok_model": grok_model,
            "ollama_model": ollama_model
        }
        save_settings(SETTINGS)
        self.status_manager.success("SOAP note settings saved successfully")

    def save_referral_settings(self, prompt: str, openai_model: str, perplexity_model: str, grok_model: str, ollama_model: str) -> None:
        from settings import save_settings, SETTINGS
        SETTINGS["referral"] = {
            "prompt": prompt,
            "model": openai_model,
            "perplexity_model": perplexity_model,
            "grok_model": grok_model,
            "ollama_model": ollama_model
        }
        save_settings(SETTINGS)
        self.status_manager.success("Referral settings saved successfully")

    def new_session(self) -> None:
        if messagebox.askyesno("New Dictation", "Start a new session? Unsaved changes will be lost."):
            # Clear text and reset undo/redo history for all tabs
            for widget in [self.transcript_text, self.soap_text, self.referral_text, self.dictation_text]:
                widget.delete("1.0", tk.END)
                widget.edit_reset()  # Clear undo/redo history
            # Clear audio segments and other stored data
            self.appended_chunks.clear()
            self.audio_segments.clear()
            self.soap_audio_segments.clear()

    def save_text(self) -> None:
        """Save text and audio to files using AudioHandler."""
        text = self.transcript_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Save Text", "No text to save.")
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(text)
                
                # Save audio if available using the AudioHandler
                if self.audio_segments:
                    base, _ = os.path.splitext(file_path)
                    audio_path = f"{base}.wav"
                    if self.audio_handler.save_audio(self.audio_segments, audio_path):
                        messagebox.showinfo("Save Audio", f"Audio saved as: {audio_path}")
                
                messagebox.showinfo("Save Text", "Text saved successfully.")
            except Exception as e:
                messagebox.showerror("Save Text", f"Error: {e}")

    def copy_text(self) -> None:
        active_widget = self.get_active_text_widget()
        self.clipboard_clear()
        self.clipboard_append(active_widget.get("1.0", tk.END))
        self.update_status("Text copied to clipboard.")

    def clear_text(self) -> None:
        if messagebox.askyesno("Clear Text", "Clear the text?"):
            self.transcript_text.delete("1.0", tk.END)
            self.appended_chunks.clear()
            self.audio_segments.clear()

    def append_text(self, text: str) -> None:
        current = self.transcript_text.get("1.0", "end-1c")
        if (self.capitalize_next or not current or current[-1] in ".!?") and text:
            text = text[0].upper() + text[1:]
            self.capitalize_next = False
        self.transcript_text.insert(tk.END, (" " if current and current[-1] != "\n" else "") + text)
        self.appended_chunks.append(f"chunk_{len(self.appended_chunks)}")
        self.transcript_text.see(tk.END)

    def scratch_that(self) -> None:
        if not self.appended_chunks:
            self.update_status("Nothing to scratch.")
            return
        tag = self.appended_chunks.pop()
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

    def toggle_recording(self) -> None:
        """Toggle between starting and stopping recording"""
        if not self.listening:
            # Start recording
            self.start_recording()
        else:
            # Stop recording
            self.stop_recording()

    def start_recording(self) -> None:
        # Switch focus to the Dictation tab (index 3)
        self.notebook.select(3)
        if not self.listening:
            self.update_status("Listening...")
            try:
                import speech_recognition as sr
                selected_index = self.mic_combobox.current()
                mic = sr.Microphone(device_index=selected_index)
                self.stop_listening_function = self.recognizer.listen_in_background(mic, self.callback, phrase_time_limit=10)
                self.listening = True
                self.record_button.config(text="Stop", bootstyle="danger")
            except Exception as e:
                logging.error("Error creating microphone", exc_info=True)
                self.update_status("Error accessing microphone.")
        else:
            self.update_status("Already listening.")

    def stop_recording(self) -> None:
        if self.listening and self.stop_listening_function:
            self.stop_listening_function(wait_for_stop=False)
            self.listening = False
            self.record_button.config(text="Start Dictation", bootstyle="success")
            self.update_status("Stopped listening.")

    def callback(self, recognizer: sr.Recognizer, audio: sr.AudioData) -> None:
        """Handle speech recognition callback with better concurrency."""
        # Use the I/O executor for speech recognition as it involves network and file I/O
        self.io_executor.submit(self.process_audio, recognizer, audio)

    def process_audio(self, recognizer: sr.Recognizer, audio: sr.AudioData) -> None:
        """Process audio with better error handling using AudioHandler."""
        segment, transcript = self.audio_handler.process_audio_data(audio)
        
        if segment:
            # Store segment
            self.audio_segments.append(segment)
            
            # Handle transcript result
            if transcript:
                self.after(0, self.handle_recognized_text, transcript)
            else:
                self.after(0, self.update_status, "No transcript was produced", "warning")
        else:
            self.after(0, self.update_status, "Failed to process audio", "error")

    def process_soap_recording(self) -> None:
        """Process SOAP recording using AudioHandler with improved concurrency."""
        # Safety check - if no audio segments, don't proceed
        if not self.soap_audio_segments:
            self.after(0, lambda: [
                self.status_manager.error("No audio data available to process"),
                self.progress_bar.stop(),
                self.progress_bar.pack_forget(),
                self.record_soap_button.config(text="Record SOAP Note", bootstyle="success", state=tk.NORMAL)
            ])
            return
            
        def task() -> None:
            try:
                # Log audio segments information for debugging
                segment_count = len(self.soap_audio_segments)
                total_duration_ms = sum(len(seg.raw_data) / (seg.frame_rate * seg.frame_width) * 1000 for seg in self.soap_audio_segments)
                logging.info(f"Processing SOAP recording with {segment_count} segments, total duration: {total_duration_ms:.2f}ms")
                
                # First combine the audio segments using I/O operations
                combined = self.audio_handler.combine_audio_segments(self.soap_audio_segments)
                if not combined:
                    raise ValueError("Failed to combine audio segments")
                
                # Log combined audio information
                combined_size = len(combined.raw_data)
                combined_duration_ms = len(combined.raw_data) / (combined.frame_rate * combined.frame_width) * 1000
                logging.info(f"Combined audio size: {combined_size} bytes, duration: {combined_duration_ms:.2f}ms")
                
                # Load the saved audio file instead of transcribing the segments directly
                # Get the most recently created wav file in the storage folder
                folder = SETTINGS.get("default_storage_folder")
                if not folder or not os.path.exists(folder):
                    raise ValueError("Storage folder not found")
                
                # Find wav files and sort by creation time (newest first)
                wav_files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.wav')]
                if not wav_files:
                    raise ValueError("No WAV files found in storage folder")
                
                wav_files.sort(key=lambda x: os.path.getctime(x), reverse=True)
                latest_wav = wav_files[0]
                logging.info(f"Using latest saved WAV file for transcription: {latest_wav}")
                
                # Try transcription with fallbacks
                transcript = ""
                
                # For SOAP notes, explicitly try ElevenLabs first if available
                if self.elevenlabs_api_key:
                    self.after(0, lambda: self.status_manager.progress("Transcribing SOAP note with ElevenLabs (best quality)..."))
                    logging.info("Attempting SOAP note transcription with ElevenLabs")
                    
                    # Use the elevenlabs method directly with the file
                    from pydub import AudioSegment as PyAudioSegment
                    audio_segment = PyAudioSegment.from_file(latest_wav, format="wav")
                    
                    # Try ElevenLabs
                    transcript = self.audio_handler._transcribe_with_elevenlabs(audio_segment)
                
                # If ElevenLabs failed or is not available, try Deepgram
                if not transcript:
                    if self.elevenlabs_api_key:
                        self.after(0, lambda: self.status_manager.progress("ElevenLabs transcription failed, trying Deepgram..."))
                        logging.info("ElevenLabs transcription failed, falling back to Deepgram")
                    else:
                        self.after(0, lambda: self.status_manager.progress("Transcribing SOAP note with Deepgram..."))
                        logging.info("ElevenLabs API key not available, using Deepgram")
                    
                    # Try with Deepgram directly
                    if self.deepgram_api_key:
                        transcript = self.audio_handler._transcribe_with_deepgram(audio_segment)
                    
                    # If both ElevenLabs and Deepgram failed or aren't available, try Whisper
                    if not transcript and self.audio_handler.whisper_available:
                        self.after(0, lambda: self.status_manager.progress("Trying local Whisper model for transcription..."))
                        logging.info("Trying local Whisper model as last resort")
                        transcript = self.audio_handler._transcribe_with_whisper(audio_segment)
                
                # If all transcription methods failed
                if not transcript:
                    raise ValueError("All transcription methods failed - no text recognized")
                
                # Log success and progress
                logging.info(f"Successfully transcribed audio, length: {len(transcript)} chars")
                self.after(0, lambda: self.status_manager.progress("Creating SOAP note from transcript..."))
                
                # Use CPU executor for the AI-intensive SOAP note creation
                future = self.cpu_executor.submit(create_soap_note_with_openai, transcript)
                
                # Get result with timeout to prevent hanging
                soap_note = future.result(timeout=120)
                
                def update_ui():
                    # Update Transcript tab with the obtained transcript
                    self.transcript_text.delete("1.0", tk.END)
                    self.transcript_text.insert(tk.END, transcript)
                    
                    # Update SOAP Note tab with the generated SOAP note
                    self._update_text_area(soap_note, "SOAP note created from recording.", self.record_soap_button, self.soap_text)
                    
                    # Switch focus to the SOAP Note tab (index 1)
                    self.notebook.select(1)
                    
                    # Stop and hide progress bar
                    self.progress_bar.stop()
                    self.progress_bar.pack_forget()
                    
                self.after(0, update_ui)
                
            except concurrent.futures.TimeoutError:
                self.after(0, lambda: [
                    self.status_manager.error("SOAP note creation timed out. Please try again."),
                    self.progress_bar.stop(),
                    self.progress_bar.pack_forget(),
                    self.record_soap_button.config(text="Record SOAP Note", bootstyle="success", state=tk.NORMAL)
                ])
            except Exception as e:
                error_msg = f"Error processing SOAP note: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.after(0, lambda: [
                    self.status_manager.error(error_msg),
                    self.progress_bar.stop(),
                    self.progress_bar.pack_forget(),
                    self.record_soap_button.config(text="Record SOAP Note", bootstyle="success", state=tk.NORMAL)
                ])
                
        # Use IO executor for the CPU-intensive audio processing
        self.io_executor.submit(task)

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
        cleaned = text.lower().strip().translate(str.maketrans('', '', string.punctuation))
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
                # Use CPU executor for the actual AI processing which is CPU-intensive
                result_future = self.cpu_executor.submit(api_func, text)
                # Get result with timeout to prevent hanging
                result = result_future.result(timeout=60)  # Add timeout to prevent hanging
                
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
        self.io_executor.submit(task)

    def _update_text_area(self, new_text: str, success_message: str, button: ttk.Button, target_widget: tk.Widget) -> None:
        target_widget.edit_separator()
        target_widget.delete("1.0", tk.END)
        target_widget.insert(tk.END, new_text)
        target_widget.edit_separator()
        self.status_manager.success(success_message)
        button.config(state=NORMAL)
        self.status_manager.show_progress(False)

    def get_active_text_widget(self) -> tk.Widget:
        return self.active_text_widget

    def refine_text(self) -> None:
        active_widget = self.get_active_text_widget()
        self._process_text_with_ai(adjust_text_with_openai, "Text refined.", self.refine_button, active_widget)

    def improve_text(self) -> None:
        active_widget = self.get_active_text_widget()
        self._process_text_with_ai(improve_text_with_openai, "Text improved.", self.improve_button, active_widget)

    def create_soap_note(self) -> None:
        """Create a SOAP note from the selected text using AI with improved concurrency."""
        transcript = self.transcript_text.get("1.0", tk.END).strip()
        if not transcript:
            messagebox.showwarning("Create SOAP Note", "There is no transcript to process.")
            return

        self.status_manager.progress("Creating SOAP note (this may take a moment)...")
        self.soap_button.config(state=DISABLED)
        self.progress_bar.pack(side=RIGHT, padx=10)
        self.progress_bar.start()

        def task() -> None:
            try:
                # Get the appropriate AI model based on settings
                provider = SETTINGS.get("soap_provider", "openai")
                
                # Use CPU executor for the AI processing which is CPU-intensive
                future = self.cpu_executor.submit(
                    create_soap_note_with_openai if provider == "openai" else
                    create_soap_note_with_other_provider,
                    transcript
                )
                
                # Get result with timeout to prevent hanging
                result = future.result(timeout=120)
                
                # Schedule UI update on the main thread
                self.after(0, lambda: [
                    self._update_text_area(result, "SOAP note created", self.soap_button, self.soap_text),
                    self.notebook.select(1)  # Switch to SOAP tab
                ])
            except concurrent.futures.TimeoutError:
                self.after(0, lambda: [
                    self.status_manager.error("SOAP note creation timed out. Please try again."),
                    self.soap_button.config(state=NORMAL),
                    self.progress_bar.stop(),
                    self.progress_bar.pack_forget()
                ])
            except Exception as e:
                error_msg = f"Error creating SOAP note: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.after(0, lambda: [
                    self.status_manager.error(error_msg),
                    self.soap_button.config(state=NORMAL),
                    self.progress_bar.stop(),
                    self.progress_bar.pack_forget()
                ])

        # Use I/O executor for task management since it involves UI coordination
        self.io_executor.submit(task)

    def refresh_microphones(self) -> None:
        names = get_valid_microphones() or sr.Microphone.list_microphone_names()
        self.mic_combobox['values'] = names
        if names:
            self.mic_combobox.current(0)
        else:
            self.mic_combobox.set("No microphone found")
        self.update_status("Microphone list refreshed.")

    def toggle_soap_recording(self) -> None:
        """Toggle SOAP note recording using AudioHandler."""
        if not self.soap_recording:
            # Clear all text areas and reset audio segments before starting a new SOAP recording session
            self.transcript_text.delete("1.0", tk.END)
            self.soap_text.delete("1.0", tk.END)
            self.referral_text.delete("1.0", tk.END)   # NEW: clear referral tab
            self.dictation_text.delete("1.0", tk.END)   # NEW: clear dictation tab
            self.appended_chunks.clear()
            self.soap_audio_segments.clear()
            self.soap_recording = True
            self.soap_paused = False  # NEW: reset pause state
            self.record_soap_button.config(text="Stop", bootstyle="danger")
            self.pause_soap_button.config(state=tk.NORMAL, text="Pause")  # enable pause button
            self.cancel_soap_button.config(state=tk.NORMAL)  # enable cancel button
            self.update_status("Recording SOAP note...")
            try:
                import speech_recognition as sr
                selected_index = self.mic_combobox.current()
                mic = sr.Microphone(device_index=selected_index)
            except Exception as e:
                logging.error("Error creating microphone for SOAP recording", exc_info=True)
                self.update_status("Error accessing microphone for SOAP note.")
                return
            self.soap_stop_listening_function = self.recognizer.listen_in_background(mic, self.soap_callback, phrase_time_limit=10)
        else:
            # Stopping SOAP recording
            self.update_status("Finalizing recording (processing last chunk)...")
            
            def stop_recording_task():
                # Stop listening with wait_for_stop=True to ensure last chunk is processed
                if self.soap_stop_listening_function:
                    self.soap_stop_listening_function(wait_for_stop=True)
                
                # Wait a small additional time to ensure processing completes
                time.sleep(0.5)
                
                # Update UI on main thread
                self.after(0, lambda: [
                    self._finalize_soap_recording()
                ])
            
            # Run the stopping process in a separate thread to avoid freezing the UI
            self.io_executor.submit(stop_recording_task)

    def _finalize_soap_recording(self):
        """Complete the SOAP recording process after ensuring all audio is captured."""
        self.soap_recording = False
        self.soap_paused = False
        
        # Update UI elements
        self.pause_soap_button.config(state=tk.DISABLED, text="Pause")
        self.cancel_soap_button.config(state=tk.DISABLED)
        self.record_soap_button.config(text="Record SOAP Note", bootstyle="SECONDARY", state=tk.DISABLED)
        
        # Check if we have any audio segments to process
        if not self.soap_audio_segments:
            self.update_status("No audio recorded. Try again.")
            self.after(1000, lambda: self.record_soap_button.config(text="Record SOAP Note", bootstyle="success", state=tk.NORMAL))
            return
            
        self.update_status("Saving SOAP note audio recording...")
        
        # Save the recorded audio
        import datetime
        folder = SETTINGS.get("default_storage_folder")
        if folder and not os.path.exists(folder):
            os.makedirs(folder)
            
        now_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
        audio_file_path = os.path.join(folder, f"{now_str}.wav") if folder else f"{now_str}.wav"
        
        # Use a thread to save the audio without blocking the UI
        def save_and_process_audio():
            try:
                # Save the combined audio to file
                self.audio_handler.save_audio(self.soap_audio_segments, audio_file_path)
                
                # Update UI from main thread
                self.after(0, lambda: self.update_status(f"SOAP audio saved to: {audio_file_path}"))
                
                # After saving is complete, start transcription
                self.after(0, lambda: [
                    self.update_status("Transcribing SOAP note with ElevenLabs (best quality)..."),
                    self.progress_bar.pack(side=RIGHT, padx=10),
                    self.progress_bar.start(),
                    self.process_soap_recording()
                ])
                
            except Exception as e:
                error_msg = f"Error saving SOAP audio: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.after(0, lambda: self.update_status(f"Error saving audio: {str(e)}", "error"))
                self.after(0, lambda: self.record_soap_button.config(text="Record SOAP Note", bootstyle="success", state=tk.NORMAL))
        
        # Execute the save and transcription process in a background thread
        self.io_executor.submit(save_and_process_audio)
        
        # Re-enable the record button after 5 seconds
        self.after(5000, lambda: self.record_soap_button.config(text="Record SOAP Note", bootstyle="success", state=tk.NORMAL))

    def toggle_soap_pause(self) -> None:
        if self.soap_paused:
            self.resume_soap_recording()
        else:
            self.pause_soap_recording()

    def pause_soap_recording(self) -> None:
        if self.soap_recording and not self.soap_paused:
            if self.soap_stop_listening_function:
                self.soap_stop_listening_function(wait_for_stop=False)
            self.soap_paused = True
            self.pause_soap_button.config(text="Resume")
            self.update_status("SOAP note recording paused.")

    def resume_soap_recording(self) -> None:
        """Resume SOAP recording after pause using the selected microphone."""
        if self.soap_recording and self.soap_paused:
            try:
                import speech_recognition as sr
                # Use the selected microphone from combobox
                selected_index = self.mic_combobox.current()
                mic = sr.Microphone(device_index=selected_index)
                logging.info(f"Resuming SOAP recording with microphone index: {selected_index}")
            except Exception as e:
                error_msg = f"Error accessing microphone: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.update_status(error_msg)
                return
                
            # Restart the background listening with same callback
            self.soap_stop_listening_function = self.recognizer.listen_in_background(mic, self.soap_callback, phrase_time_limit=10)
            self.soap_paused = False
            self.pause_soap_button.config(text="Pause")
            self.update_status("SOAP note recording resumed.")

    def soap_callback(self, recognizer: sr.Recognizer, audio: sr.AudioData) -> None:
        """Callback for SOAP note recording using AudioHandler."""
        try:
            # Log that we received audio data
            audio_size = len(audio.get_raw_data()) if audio else 0
            logging.info(f"SOAP callback received audio chunk of size: {audio_size} bytes")
            
            if not audio or audio_size == 0:
                logging.warning("Empty audio data received in SOAP callback")
                return
                
            # Convert audio data to segment WITHOUT transcribing
            # Extract raw audio data from AudioData
            raw_data = audio.get_raw_data()
            sample_rate = audio.sample_rate
            sample_width = audio.sample_width
            
            # Create AudioSegment directly from raw data
            from pydub import AudioSegment as PyAudioSegment
            segment = PyAudioSegment(
                data=raw_data,
                sample_width=sample_width,
                frame_rate=sample_rate,
                channels=1  # Speech recognition typically uses mono
            )
            
            if segment:
                segment_length = len(segment.raw_data)
                logging.info(f"Adding audio segment of length {segment_length} bytes to SOAP recording")
                self.soap_audio_segments.append(segment)
            else:
                logging.warning("Failed to create audio segment from valid audio data")
                
        except Exception as e:
            logging.error(f"Error recording SOAP note chunk: {str(e)}", exc_info=True)

    def cancel_soap_recording(self) -> None:
        """Cancel the current SOAP note recording without processing."""
        if not self.soap_recording:
            return
            
        # Show confirmation dialog before canceling
        if not messagebox.askyesno("Cancel Recording", 
                                  "Are you sure you want to cancel the current recording?\n\nAll recorded audio will be discarded.",
                                  icon="warning"):
            return  # User clicked "No", abort cancellation
            
        self.update_status("Cancelling recording...")
        
        def cancel_task():
            # Stop listening with wait_for_stop=True to ensure clean shutdown
            if self.soap_stop_listening_function:
                self.soap_stop_listening_function(wait_for_stop=True)
                
            # Update UI on main thread
            self.after(0, lambda: [
                self._cancel_soap_recording_finalize()
            ])
            
        # Run the cancellation process in a separate thread to avoid freezing the UI
        self.io_executor.submit(cancel_task)
        
    def _cancel_soap_recording_finalize(self):
        """Finalize the cancellation of SOAP recording."""
        # Clear the audio segments
        self.soap_audio_segments.clear()
        
        # Reset state variables
        self.soap_recording = False
        self.soap_paused = False
        
        # Reset UI buttons
        self.pause_soap_button.config(state=tk.DISABLED, text="Pause")
        self.cancel_soap_button.config(state=tk.DISABLED)
        self.record_soap_button.config(text="Record SOAP Note", bootstyle="success", state=tk.NORMAL)
        
        # Update status
        self.status_manager.warning("SOAP note recording cancelled.")

    def undo_text(self) -> None:
        try:
            widget = self.get_active_text_widget()
            widget.edit_undo()
            self.update_status("Undo performed.")
        except Exception as e:
            self.update_status("Nothing to undo.")

    def redo_text(self) -> None:
        try:
            widget = self.get_active_text_widget()
            widget.edit_redo()
            self.update_status("Redo performed.")
        except Exception as e:
            self.update_status("Nothing to redo.")

    def on_closing(self) -> None:
        try:
            # Shutdown all executor pools properly
            for executor_name in ['io_executor', 'cpu_executor', 'executor']:
                if hasattr(self, executor_name) and getattr(self, executor_name) is not None:
                    try:
                        executor = getattr(self, executor_name)
                        logging.info(f"Shutting down {executor_name}")
                        executor.shutdown(wait=False)
                    except Exception as e:
                        logging.error(f"Error shutting down {executor_name}: {str(e)}", exc_info=True)
        except Exception as e:
            logging.error(f"Error during executor shutdown: {str(e)}", exc_info=True)
        
        self.destroy()

    def on_tab_changed(self, event: tk.Event) -> None:
        current = self.notebook.index(self.notebook.select())
        if current == 0:
            self.active_text_widget = self.transcript_text
        elif current == 1:
            self.active_text_widget = self.soap_text
        elif current == 2:
            self.active_text_widget = self.referral_text
        elif current == 3:  # NEW: Dictation tab
            self.active_text_widget = self.dictation_text
        else:
            self.active_text_widget = self.transcript_text

    def schedule_status_update(self, delay_ms: int, message: str, status_type: str = "info") -> None:
        """Schedule a status update that won't be automatically cleared after timeout"""
        return self.status_manager.schedule_status_update(delay_ms, message, status_type)

    def show_letter_options_dialog(self) -> tuple:
        # Call the refactored function from dialogs.py
        return show_letter_options_dialog(self)

    def create_letter(self) -> None:
        """Create a letter from the selected text source with AI assistance"""
        # Get source and specifications
        source, specs = self.show_letter_options_dialog()
        
        if source is None:  # User cancelled
            return
            
        # Get the text based on selected source
        if source == "transcript":
            text = self.transcript_text.get("1.0", tk.END).strip()
            source_name = "Transcript"
        else:  # dictation
            text = self.dictation_text.get("1.0", tk.END).strip()
            source_name = "Dictation"
        
        if not text:
            messagebox.showwarning("Empty Text", f"The {source_name} tab is empty. Please add content before creating a letter.")
            return
        
        # Show progress
        self.status_manager.progress(f"Generating letter from {source_name} text...")
        self.progress_bar.pack(side=RIGHT, padx=10)
        self.progress_bar.start()
        self.letter_button.config(state=DISABLED)
        
        def task() -> None:
            try:
                # Generate letter using the imported AI function
                letter = create_letter_with_ai(text, specs)
                
                # Update UI when done
                self.after(0, lambda: [
                    self._update_text_area(letter, f"Letter generated from {source_name}", self.letter_button, self.referral_text),
                    self.notebook.select(2)  # Show letter in Referral tab
                ])
            except Exception as e:
                error_msg = f"Error creating letter: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.after(0, lambda: [
                    self.update_status(error_msg, status_type="error"),
                    self.letter_button.config(state=NORMAL),
                    self.progress_bar.stop(),
                    self.progress_bar.pack_forget()
                ])
        
        # Execute in thread pool
        self.executor.submit(task)

    def show_elevenlabs_settings(self) -> None:
        # Call the refactored function from dialogs.py
        show_elevenlabs_settings_dialog(self)
        
        # Refresh the audio handler with potentially new settings
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self.audio_handler = AudioHandler(
            elevenlabs_api_key=self.elevenlabs_api_key,
            deepgram_api_key=self.deepgram_api_key,
            recognition_language=self.recognition_language
        )
        self.status_manager.success("ElevenLabs settings saved successfully")

    def _on_provider_change(self, event):
        from settings import SETTINGS, save_settings  # Import locally if preferred
        
        selected_index = self.provider_combobox.current()
        providers = ["openai", "perplexity", "grok", "ollama"]
        provider_display = ["OpenAI", "Perplexity", "Grok", "Ollama"]
        
        if 0 <= selected_index < len(providers):
            selected_provider = providers[selected_index]
            SETTINGS["ai_provider"] = selected_provider
            save_settings(SETTINGS)
            self.update_status(f"AI Provider set to {provider_display[selected_index]}")

    def _on_stt_change(self, event):
        """Update STT provider when dropdown selection changes."""
        selected_index = self.stt_combobox.current()
        if selected_index >= 0:
            # Map display values to actual provider values
            stt_providers = ["elevenlabs", "deepgram"]
            stt_display = ["ElevenLabs", "Deepgram"]
            
            # Update settings
            provider = stt_providers[selected_index]
            from settings import SETTINGS, save_settings
            SETTINGS["stt_provider"] = provider
            save_settings(SETTINGS)
            
            # Update status with the new provider info
            self.status_manager.update_provider_info()
            self.update_status(f"Speech-to-Text provider set to {stt_display[selected_index]}")

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
            "google": "Google"
        }
        
        primary_display = provider_names.get(primary_provider, primary_provider)
        fallback_display = provider_names.get(fallback_provider, fallback_provider)
        
        # Update status with warning about fallback
        message = f"{primary_display} transcription failed. Falling back to {fallback_display}."
        self.after(0, lambda: self.status_manager.warning(message))
        
        # Update STT provider dropdown to reflect actual service being used
        try:
            stt_providers = ["elevenlabs", "deepgram"]
            fallback_index = stt_providers.index(fallback_provider)
            self.after(0, lambda: self.stt_combobox.current(fallback_index))
        except (ValueError, IndexError):
            pass

    def toggle_theme(self):
        """Toggle between light and dark themes"""
        # Define light and dark theme pairs
        theme_pairs = {
            # Light themes
            "flatly": "darkly",
            "cosmo": "solar",
            "yeti": "cyborg",
            "minty": "superhero",
            # Dark themes
            "darkly": "flatly",
            "solar": "cosmo",
            "cyborg": "yeti",
            "superhero": "minty"
        }
        
        # Get the paired theme for the current theme
        new_theme = theme_pairs.get(self.current_theme, "flatly")
        
        # Apply the new theme - need to recreate the window to fully apply the theme
        self.style.theme_use(new_theme)
        self.current_theme = new_theme
        
        # Update settings
        SETTINGS["theme"] = new_theme
        save_settings(SETTINGS)
        
        # Define dark themes list
        dark_themes = ["darkly", "solar", "cyborg", "superhero"]
        
        # Check if the NEW theme is dark (not the current theme which has just been switched)
        is_dark = new_theme in dark_themes
        mode_name = "Dark" if is_dark else "Light"
        self.status_manager.info(f"Switched to {mode_name} Mode ({new_theme})")
        
        # Update text widgets background and foreground colors based on theme
        text_bg = "#212529" if is_dark else "#ffffff"
        text_fg = "#f8f9fa" if is_dark else "#212529"
        
        # Update all text widgets with new colors
        text_widgets = [self.transcript_text, self.soap_text, self.referral_text, self.dictation_text]
        for widget in text_widgets:
            widget.config(bg=text_bg, fg=text_fg, insertbackground=text_fg)
            
        # For better visibility in dark mode, update styles for buttons and other elements
        control_bg = "#212529" if is_dark else "#f8f9fa"
        control_fg = "#f8f9fa" if is_dark else "#212529"
        
        # Update control panel backgrounds - handle tk vs ttk frames differently
        for frame in self.winfo_children():
            if isinstance(frame, tk.Frame):  # Only standard tk frames support 'background'
                frame.configure(background=control_bg)
                
        # Update all button frames specifically - handle tk vs ttk frames differently
        for btn_name, btn in self.buttons.items():
            btn_frame = btn.master
            if isinstance(btn_frame, tk.Frame):  # Only standard tk frames support 'background'
                btn_frame.configure(background=control_bg)
                
        # Update notebook style
        if is_dark:
            # Dark mode styling
            self.style.configure("Green.TNotebook", background=control_bg)
            self.style.configure("Green.TNotebook.Tab", background="#343a40", foreground=control_fg)
            self.style.configure("TButton", foreground=control_fg)
            self.style.configure("TFrame", background=control_bg)  # Use style system for ttk frames
            self.style.configure("TLabel", foreground=control_fg)
            
            # Set specific components that need explicit styling
            if hasattr(self, 'control_frame') and isinstance(self.control_frame, tk.Frame):
                self.control_frame.configure(background=control_bg)
        else:
            # Light mode styling - reset to defaults
            self.style.configure("Green.TNotebook", background="#ffffff")
            self.style.configure("Green.TNotebook.Tab", background="#e9ecef", foreground="#212529")
            self.style.configure("TButton", foreground="#212529")
            self.style.configure("TFrame", background="#f8f9fa")  # Use style system for ttk frames
            self.style.configure("TLabel", foreground="#212529")
            
            # Set specific components that need explicit styling
            if hasattr(self, 'control_frame') and isinstance(self.control_frame, tk.Frame):
                self.control_frame.configure(background="#f8f9fa")
            
            # Do not try to style menu bar directly as it's not stored as an instance variable
        
        # Update theme button icon and tooltip if available
        if hasattr(self, 'theme_btn') and self.theme_btn:
            # Log the current state for debugging
            print(f"Updating theme button - is_dark: {is_dark}, theme: {new_theme}")
            
            # Update icon and text based on new theme
            icon = "🌙" if not is_dark else "☀️"
            self.theme_btn.config(text=f"{icon} Theme")
            
            # Also update bootstyle based on theme for better visibility
            button_style = "info" if not is_dark else "warning"
            self.theme_btn.configure(bootstyle=button_style)
            
            # Update tooltip - create new tooltip and destroy old one
            tooltip_text = "Switch to Dark Mode" if not is_dark else "Switch to Light Mode"
            if hasattr(self.theme_btn, '_tooltip'):
                if hasattr(self.theme_btn._tooltip, 'hidetip'):
                    self.theme_btn._tooltip.hidetip()  # Hide current tooltip if visible
                
                # Update tooltip text
                self.theme_btn._tooltip.text = tooltip_text
                print(f"Updated tooltip text to: {tooltip_text}")
        
        # Update the theme label if available
        if hasattr(self, 'theme_label') and self.theme_label:
            mode_text = "Light Mode" if not is_dark else "Dark Mode"
            self.theme_label.config(text=f"({mode_text})")
            print(f"Updated theme label to: ({mode_text})")
            
        # Update shortcut label in status bar to show theme toggle shortcut
        self.status_manager.info("Theme toggle shortcut: Alt+T")

    def create_referral(self) -> None:
        """Create a referral from transcript with improved concurrency."""
        # Check if the transcript is empty before proceeding
        text = self.transcript_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Empty Transcript", "The transcript is empty. Please add content before creating a referral.")
            return
            
        # Update status and display progress bar on referral click
        self.status_manager.progress("Analyzing transcript for possible conditions...")
        self.progress_bar.pack(side=RIGHT, padx=10)
        self.progress_bar.start()
        
        # Get suggested conditions asynchronously using CPU executor
        def get_conditions_task() -> str:
            try:
                # Use CPU executor for the condition analysis which is CPU-intensive
                future = self.cpu_executor.submit(get_possible_conditions, text)
                # Get result with timeout to prevent hanging
                return future.result(timeout=60) or ""
            except concurrent.futures.TimeoutError:
                logging.error("Condition analysis timed out")
                return ""
            except Exception as e:
                logging.error(f"Error analyzing conditions: {str(e)}", exc_info=True)
                return ""

        # Use I/O executor for the overall task management
        future = self.io_executor.submit(get_conditions_task)
        
        def on_conditions_done(future_result):
            try:
                suggestions = future_result.result()
                # Continue on the main thread
                self.after(0, lambda: self._create_referral_continued(suggestions))
            except Exception as e:
                error_msg = f"Failed to analyze conditions: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.after(0, lambda: [
                    self.status_manager.error(error_msg),
                    self.progress_bar.stop(),
                    self.progress_bar.pack_forget()
                ])
                
        future.add_done_callback(on_conditions_done)

    def _create_referral_continued(self, suggestions: str) -> None:
        """Continue referral creation process after condition analysis."""
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        
        conditions_list = [cond.strip() for cond in suggestions.split(",") if cond.strip()]
        
        # Use ask_conditions_dialog as an imported function
        from dialogs import ask_conditions_dialog
        focus = ask_conditions_dialog(self, "Select Conditions", "Select conditions to focus on:", conditions_list)
        
        if not focus:
            self.update_status("Referral cancelled or no conditions selected.", status_type="warning")
            return
        
        # Use "progress" status type to prevent auto-clearing for long-running operations
        self.status_manager.progress(f"Creating referral for conditions: {focus}...")
        self.progress_bar.pack(side=RIGHT, padx=10)
        self.progress_bar.start()
        self.referral_button.config(state=DISABLED)  # Disable button while processing
        
        def task() -> None:
            try:
                transcript = self.transcript_text.get("1.0", tk.END).strip()
                
                # Import locally to avoid potential circular import
                from ai import create_referral_with_openai
                
                # Use our custom scheduler for status updates
                self.schedule_status_update(3000, f"Still generating referral for: {focus}...", "progress")
                self.schedule_status_update(10000, f"Processing referral (this may take a moment)...", "progress")
                
                # Use CPU executor for the AI processing which is CPU-intensive
                future = self.cpu_executor.submit(create_referral_with_openai, transcript, focus)
                
                # Get result with timeout to prevent hanging
                result = future.result(timeout=120)
                
                # Update UI when done
                self.after(0, lambda: [
                    self._update_text_area(result, f"Referral created for: {focus}", self.referral_button, self.referral_text),
                    self.notebook.select(2)  # Switch focus to Referral tab
                ])
            except concurrent.futures.TimeoutError:
                self.after(0, lambda: [
                    self.status_manager.error("Referral creation timed out. Please try again."),
                    self.referral_button.config(state=NORMAL),
                    self.progress_bar.stop(),
                    self.progress_bar.pack_forget()
                ])
            except Exception as e:
                error_msg = f"Error creating referral: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.after(0, lambda: [
                    self.status_manager.error(error_msg),
                    self.referral_button.config(state=NORMAL),
                    self.progress_bar.stop(),
                    self.progress_bar.pack_forget()
                ])

        # Use I/O executor for task management since it involves UI coordination
        self.io_executor.submit(task)

    def load_audio_file(self) -> None:
        """Load and transcribe audio from a file using AudioHandler with improved concurrency."""
        file_path = filedialog.askopenfilename(
            initialdir=os.path.expanduser("~"),
            title="Select Audio File",
            filetypes=(
                ("Audio Files", "*.wav;*.mp3;*.ogg;*.flac;*.m4a"),
                ("All Files", "*.*")
            )
        )
        if not file_path:
            return
        
        self.status_manager.progress(f"Processing audio file: {os.path.basename(file_path)}...")
        self.progress_bar.pack(side=RIGHT, padx=10)
        self.progress_bar.start()
        
        def task() -> None:
            try:
                # Use I/O executor for file loading which is I/O-bound
                segment, transcript = self.audio_handler.load_audio_file(file_path)
                
                if segment and transcript:
                    # Store segment for future use (was missing in the updated code)
                    self.audio_segments = [segment]
                    
                    # Schedule UI update on the main thread
                    self.after(0, lambda: [
                        self.append_text(transcript),
                        self.status_manager.success(f"Audio transcribed: {os.path.basename(file_path)}"),
                        self.progress_bar.stop(),
                        self.progress_bar.pack_forget(),
                        self.notebook.select(0)  # Switch to Transcript tab (index 0)
                    ])
                else:
                    self.after(0, lambda: [
                        self.status_manager.error("Failed to process audio file"),
                        self.progress_bar.stop(),
                        self.progress_bar.pack_forget()
                    ])
            except Exception as e:
                error_msg = f"Error processing audio file: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.after(0, lambda: [
                    self.status_manager.error(error_msg),
                    self.progress_bar.stop(),
                    self.progress_bar.pack_forget()
                ])
                
        # Use I/O executor for the task since it primarily involves file I/O
        self.io_executor.submit(task)

    def append_text_to_widget(self, text: str, widget: tk.Widget) -> None:
        current = widget.get("1.0", "end-1c")
        if (self.capitalize_next or not current or current[-1] in ".!?") and text:
            text = text[0].upper() + text[1:]
            self.capitalize_next = False
        widget.insert(tk.END, (" " if current and current[-1] != "\n" else "") + text)
        widget.see(tk.END)

if __name__ == "__main__":
    main()
