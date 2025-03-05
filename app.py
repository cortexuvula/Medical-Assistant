import os
import json
import string
import logging
import concurrent.futures
from io import BytesIO
import tkinter as tk
from tkinter import messagebox, filedialog, scrolledtext
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
        
        tk.Label(api_root, text="OpenAI, Grok, or Perplexity API key is required. Deepgram is optional but recommended.",
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
        tk.Label(keys_frame, text="Deepgram API Key (Optional):").grid(row=3, column=0, sticky="w", pady=5)
        deepgram_entry = tk.Entry(keys_frame, width=40)
        deepgram_entry.grid(row=3, column=1, sticky="ew", pady=5)
        
        # NEW: Add ElevenLabs API Key field
        tk.Label(keys_frame, text="ElevenLabs API Key (Optional):").grid(row=4, column=0, sticky="w", pady=5)
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
        # Initialize the executor first, before any potential failures
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        
        super().__init__(themename="flatly")
        self.title("Medical Assistant")
        self.geometry("1400x950")
        self.minsize(700, 500)
        self.config(bg="#f0f0f0")
        
        # Center the window on the screen
        self.update_idletasks()  # Ensure window dimensions are calculated
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = 1400
        window_height = 950
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # Initialize API keys and handlers
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.deepgram_api_key = os.getenv("DEEPGRAM_API_KEY", "")
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self.recognition_language = os.getenv("RECOGNITION_LANGUAGE", "en-US")
        
        # Initialize audio handler
        self.audio_handler = AudioHandler(
            elevenlabs_api_key=self.elevenlabs_api_key,
            deepgram_api_key=self.deepgram_api_key,
            recognition_language=self.recognition_language
        )

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
            "toggle_soap_pause": self.toggle_soap_pause
        }
        
        # Create microphone frame
        mic_frame, self.mic_combobox, self.provider_combobox, self.stt_combobox = self.ui.create_microphone_frame(
            on_provider_change=self._on_provider_change,
            on_stt_change=self._on_stt_change,
            refresh_microphones=self.refresh_microphones
        )
        mic_frame.pack(side=TOP, fill=tk.X, padx=20, pady=(20, 10))
        
        # Create notebook with text areas
        self.notebook, self.transcript_text, self.soap_text, self.referral_text, self.dictation_text = self.ui.create_notebook()
        self.notebook.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)
        
        # Set initial active text widget and bind tab change event
        self.active_text_widget = self.transcript_text
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
        # Create control panel with buttons
        control_frame, self.buttons = self.ui.create_control_panel(command_map)
        control_frame.pack(side=TOP, fill=tk.X, padx=20, pady=10)
        
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
        
        # Create status bar
        status_frame, self.status_icon_label, self.status_label, self.provider_indicator, self.progress_bar = self.ui.create_status_bar()
        status_frame.pack(side=BOTTOM, fill=tk.X)

    def bind_shortcuts(self) -> None:
        self.bind("<Control-n>", lambda event: self.new_session())
        self.bind("<Control-s>", lambda event: self.save_text())
        self.bind("<Control-c>", lambda event: self.copy_text())
        self.bind("<Control-l>", lambda event: self.load_audio_file())

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
            save_callback=self.save_refine_settings
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
            save_callback=self.save_improve_settings
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
            save_callback=self.save_soap_settings
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
            save_callback=self.save_referral_settings
        )

    def save_refine_settings(self, prompt: str, openai_model: str, perplexity_model: str, grok_model: str) -> None:
        from settings import save_settings, SETTINGS
        SETTINGS["refine_text"] = {
            "prompt": prompt,
            "model": openai_model,
            "perplexity_model": perplexity_model,
            "grok_model": grok_model
        }
        save_settings(SETTINGS)
        self.update_status("Refine settings saved.")

    def save_improve_settings(self, prompt: str, openai_model: str, perplexity_model: str, grok_model: str) -> None:
        from settings import save_settings, SETTINGS
        SETTINGS["improve_text"] = {
            "prompt": prompt,
            "model": openai_model,
            "perplexity_model": perplexity_model,
            "grok_model": grok_model
        }
        save_settings(SETTINGS)
        self.update_status("Improve settings saved.")

    def save_soap_settings(self, prompt: str, openai_model: str, perplexity_model: str, grok_model: str) -> None:
        from settings import save_settings, SETTINGS
        SETTINGS["soap_note"] = {
            "system_message": prompt,
            "model": openai_model,
            "perplexity_model": perplexity_model,
            "grok_model": grok_model
        }
        save_settings(SETTINGS)
        self.update_status("SOAP note settings saved.")

    def save_referral_settings(self, prompt: str, openai_model: str, perplexity_model: str, grok_model: str) -> None:
        from settings import SETTINGS, save_settings
        SETTINGS["referral"] = {
            "prompt": prompt,
            "model": openai_model,
            "perplexity_model": perplexity_model,
            "grok_model": grok_model
        }
        save_settings(SETTINGS)
        self.update_status("Referral settings saved.")

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
        self.executor.submit(self.process_audio, recognizer, audio)

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
        """Process SOAP recording using AudioHandler."""
        def task() -> None:
            try:
                # Use audio handler to combine segments and get transcript
                combined = self.audio_handler.combine_audio_segments(self.soap_audio_segments)
                transcript = self.audio_handler.transcribe_audio(combined) if combined else ""
                soap_note = create_soap_note_with_openai(transcript)
            except Exception as e:
                soap_note = f"Error processing SOAP note: {e}"
                transcript = ""
                
            def update_ui():
                # Update Transcript tab with the obtained transcript
                self.transcript_text.delete("1.0", tk.END)
                self.transcript_text.insert(tk.END, transcript)
                # Update SOAP Note tab with the generated SOAP note
                self._update_text_area(soap_note, "SOAP note created from recording.", self.record_soap_button, self.soap_text)
                # Switch focus to the SOAP Note tab (index 1)
                self.notebook.select(1)
                
            self.after(0, update_ui)
            
        self.executor.submit(task)

    def load_audio_file(self) -> None:
        """Load and transcribe audio from a file using AudioHandler."""
        file_path = filedialog.askopenfilename(
            title="Select Audio File",
            filetypes=[("Audio Files", "*.wav *.mp3"), ("All Files", "*.*")]
        )
        if not file_path:
            return
        self.status_manager.progress("Transcribing audio...")
        self.buttons["load"].config(state=DISABLED)
        
        self.progress_bar.pack(side=RIGHT, padx=10)
        self.progress_bar.start()
        
        def task() -> None:
            segment, transcript = self.audio_handler.load_audio_file(file_path)
            
            if segment:
                # Store segment for future use
                self.audio_segments = [segment]
            
            if transcript:
                self.after(0, lambda: [
                    self.transcript_text.delete("1.0", tk.END),
                    self._update_text_area(transcript, "Audio transcribed successfully.", self.buttons["load"], self.transcript_text),
                    self.notebook.select(0)
                ])
            else:
                self.after(0, lambda: messagebox.showerror("Transcription Error", "Failed to transcribe audio."))
                
            # Always re-enable button and hide progress bar
            self.after(0, lambda: self.buttons["load"].config(state=NORMAL))
            self.after(0, self.progress_bar.stop)
            self.after(0, self.progress_bar.pack_forget)
            
        self.executor.submit(task)

    def append_text_to_widget(self, text: str, widget: tk.Widget) -> None:
        current = widget.get("1.0", "end-1c")
        if (self.capitalize_next or not current or current[-1] in ".!?") and text:
            text = text[0].upper() + text[1:]
            self.capitalize_next = False
        widget.insert(tk.END, (" " if current and current[-1] != "\n" else "") + text)
        widget.see(tk.END)

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
            result = api_func(text)
            self.after(0, lambda: self._update_text_area(result, success_message, button, target_widget))
        self.executor.submit(task)

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
        transcript = self.transcript_text.get("1.0", tk.END).strip()
        if not transcript:
            messagebox.showwarning("Process Text", "There is no text to process.")
            return
        self.status_manager.progress("Processing SOAP note...")
        self.soap_button.config(state=DISABLED)
        self.progress_bar.pack(side=RIGHT, padx=10)
        self.progress_bar.start()
        def task() -> None:
            result = create_soap_note_with_openai(transcript)
            self.after(0, lambda: [
                self._update_text_area(result, "SOAP note created.", self.soap_button, self.soap_text),
                self.notebook.select(1)  # Switch focus to SOAP Note tab (index 1)
            ])
        self.executor.submit(task)

    def create_referral(self) -> None:
        # Check if the transcript is empty before proceeding
        text = self.transcript_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Empty Transcript", "The transcript is empty. Please add content before creating a referral.")
            return
            
        # New: Immediately update status and display progress bar on referral click
        self.status_manager.progress("Referral button clicked - preparing referral...")
        self.progress_bar.pack(side=RIGHT, padx=10)
        self.progress_bar.start()
        
        # New: Get suggested conditions asynchronously using imported function
        def get_conditions() -> str:
            return get_possible_conditions(text)  # Use the imported function
        future = self.executor.submit(get_conditions)
        def on_conditions_done(future_result):
            try:
                suggestions = future_result.result() or ""
            except Exception as e:
                suggestions = ""
            # Continue on the main thread
            self.after(0, lambda: self._create_referral_continued(suggestions))
        future.add_done_callback(on_conditions_done)

    def _create_referral_continued(self, suggestions: str) -> None:
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        conditions_list = [cond.strip() for cond in suggestions.split(",") if cond.strip()]
        # Fix: Use ask_conditions_dialog as an imported function, not as a method
        from dialogs import ask_conditions_dialog
        focus = ask_conditions_dialog(self, "Select Conditions", "Select conditions to focus on:", conditions_list)
        if not focus:
            self.update_status("Referral cancelled or no conditions selected.", status_type="warning")
            return
        
        # Use "progress" status type to prevent auto-clearing for long-running operations
        self.status_manager.progress(f"Processing referral for conditions: {focus}...")
        self.progress_bar.pack(side=RIGHT, padx=10)
        self.progress_bar.start()
        self.referral_button.config(state=DISABLED)  # Disable button while processing
        
        def task() -> None:
            try:
                transcript = self.transcript_text.get("1.0", tk.END).strip()
                # Import locally to avoid potential circular import
                from ai import create_referral_with_openai
                # Use our custom scheduler instead of direct after() calls
                self.schedule_status_update(3000, f"Still generating referral for: {focus}...", "progress")
                self.schedule_status_update(10000, f"Processing referral (this may take a moment)...", "progress")
                # Execute the referral creation with conditions
                result = create_referral_with_openai(transcript, focus)
                # Update UI when done
                self.after(0, lambda: [
                    self._update_text_area(result, f"Referral created for: {focus}", self.referral_button, self.referral_text),
                    self.notebook.select(2)  # Switch focus to Referral tab (index 2)
                ])
            except Exception as e:
                error_msg = f"Error creating referral: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.after(0, lambda: [
                    self.update_status(error_msg, status_type="error"),
                    self.referral_button.config(state=NORMAL),
                    self.progress_bar.stop(),
                    self.progress_bar.pack_forget()
                ])
        # Execute in thread pool
        self.executor.submit(task)

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
        # ... existing code for starting recording ...
        
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
            if self.soap_stop_listening_function:
                self.soap_stop_listening_function(wait_for_stop=False)
            self.soap_recording = False
            self.soap_paused = False
            # Disable the record SOAP note button for 5 seconds to prevent double click
            self.record_soap_button.config(text="Record SOAP Note", bootstyle="SECONDARY", state=tk.DISABLED)
            self.pause_soap_button.config(state=tk.DISABLED, text="Pause")
            self.update_status("Transcribing SOAP note...")
            
            import datetime
            folder = SETTINGS.get("default_storage_folder")
            if folder and not os.path.exists(folder):
                os.makedirs(folder)
                
            now_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
            audio_file_path = os.path.join(folder, f"{now_str}.wav") if folder else f"{now_str}.wav"
            
            # Use audio handler to save the combined audio
            if self.soap_audio_segments:
                self.audio_handler.save_audio(self.soap_audio_segments, audio_file_path)
                self.update_status(f"SOAP audio saved to: {audio_file_path}")
                
            self.progress_bar.pack(side=RIGHT, padx=10)
            self.progress_bar.start()
            self.process_soap_recording()
            # Re-enable the record button after 5 seconds and restore green colors
            self.after(5000, lambda: self.record_soap_button.config(state=NORMAL, bootstyle="success"))

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
        if self.soap_recording and self.soap_paused:
            try:
                mic = sr.Microphone()  # Adjust as needed for selected mic
            except Exception as e:
                self.update_status(f"Error accessing microphone: {e}")
                return
            self.soap_stop_listening_function = self.recognizer.listen_in_background(mic, self.soap_callback, phrase_time_limit=10)
            self.soap_paused = False
            self.pause_soap_button.config(text="Pause")
            self.update_status("SOAP note recording resumed.")

    def soap_callback(self, recognizer: sr.Recognizer, audio: sr.AudioData) -> None:
        """Callback for SOAP note recording using AudioHandler."""
        try:
            # Extract audio segment using AudioHandler
            segment, _ = self.audio_handler.process_audio_data(audio)
            if segment:
                self.soap_audio_segments.append(segment)
        except Exception as e:
            logging.error(f"Error recording SOAP note chunk: {str(e)}", exc_info=True)

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
            # Check if executor exists and is not None before trying to shut it down
            if hasattr(self, 'executor') and self.executor is not None:
                self.executor.shutdown(wait=False)
        except Exception as e:
            logging.error(f"Error shutting down executor: {str(e)}", exc_info=True)
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
        providers = ["openai", "perplexity", "grok"]
        provider_display = ["OpenAI", "Perplexity", "Grok"]
        
        if 0 <= selected_index < len(providers):
            selected_provider = providers[selected_index]
            SETTINGS["ai_provider"] = selected_provider
            save_settings(SETTINGS)
            self.update_status(f"AI Provider set to {provider_display[selected_index]}")

    def _on_stt_change(self, event):
        from settings import SETTINGS, save_settings  # Import locally if preferred
        
        selected_index = self.stt_combobox.current()
        stt_providers = ["elevenlabs", "deepgram", "google"]
        stt_display = ["ElevenLabs", "Deepgram", "Google"]
        
        if 0 <= selected_index < len(stt_providers):
            selected_stt = stt_providers[selected_index]
            SETTINGS["stt_provider"] = selected_stt
            save_settings(SETTINGS)
            self.update_status(f"Speech-to-Text provider set to {stt_display[selected_index]}")


