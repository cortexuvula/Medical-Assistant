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
from ai import adjust_text_with_openai, improve_text_with_openai, create_soap_note_with_openai
from tooltip import ToolTip
from settings import SETTINGS
from dialogs import create_toplevel_dialog, show_settings_dialog, askstring_min, ask_conditions_dialog

# Add near the top of the file
import time
import uuid
from requests.exceptions import RequestException, Timeout, ConnectionError

# Add to imports section
from audio import AudioHandler

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

        # Move these here from the module level
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.deepgram_api_key = os.getenv("DEEPGRAM_API_KEY", "")
        # NEW: Add ElevenLabs API key
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self.recognition_language = os.getenv("RECOGNITION_LANGUAGE", "en-US")
        
        # Initialize audio handler instead of Deepgram client
        self.audio_handler = AudioHandler(
            elevenlabs_api_key=self.elevenlabs_api_key,
            deepgram_api_key=self.deepgram_api_key,
            recognition_language=self.recognition_language
        )

        self.appended_chunks = []
        self.capitalize_next = False
        self.audio_segments = []
        self.soap_recording = False
        self.soap_audio_segments = []
        self.soap_stop_listening_function = None

        self.create_menu()
        self.create_widgets()
        self.bind_shortcuts()

        if not openai.api_key:
            self.refine_button.config(state=DISABLED)
            self.improve_button.config(state=DISABLED)
            self.update_status("Warning: OpenAI API key not provided. AI features disabled.")

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
        
        # Add ElevenLabs settings menu option
        settings_menu.add_command(label="ElevenLabs Settings", command=self.show_elevenlabs_settings)
        
        text_settings_menu = tk.Menu(settings_menu, tearoff=0)
        text_settings_menu.add_command(label="Refine Prompt Settings", command=self.show_refine_settings_dialog)
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
        dialog = create_toplevel_dialog(self, "Update API Keys", "800x700")
        
        # Increase main frame padding for more spacing around all content
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Get current API keys from environment
        openai_key = os.getenv("OPENAI_API_KEY", "")
        deepgram_key = os.getenv("DEEPGRAM_API_KEY", "")
        grok_key = os.getenv("GROK_API_KEY", "")
        perplexity_key = os.getenv("PERPLEXITY_API_KEY", "")
        elevenlabs_key = os.getenv("ELEVENLABS_API_KEY", "")  # NEW: Get ElevenLabs key

        # Create entry fields with password masking - add more vertical spacing
        ttk.Label(frame, text="OpenAI API Key:").grid(row=0, column=0, sticky="w", pady=10)
        openai_entry = ttk.Entry(frame, width=50, show="•")
        openai_entry.grid(row=0, column=1, sticky="ew", padx=(10, 5), pady=10)
        openai_entry.insert(0, openai_key)

        ttk.Label(frame, text="Grok API Key:").grid(row=1, column=0, sticky="w", pady=10)
        grok_entry = ttk.Entry(frame, width=50, show="•")
        grok_entry.grid(row=1, column=1, sticky="ew", padx=(10, 5), pady=10)
        grok_entry.insert(0, grok_key)

        ttk.Label(frame, text="Perplexity API Key:").grid(row=2, column=0, sticky="w", pady=10)
        perplexity_entry = ttk.Entry(frame, width=50, show="•")
        perplexity_entry.grid(row=2, column=1, sticky="ew", padx=(10, 5), pady=10)
        perplexity_entry.insert(0, perplexity_key)

        ttk.Label(frame, text="Deepgram API Key:").grid(row=3, column=0, sticky="w", pady=10)
        deepgram_entry = ttk.Entry(frame, width=50, show="•")
        deepgram_entry.grid(row=3, column=1, sticky="ew", padx=(10, 5), pady=10)
        deepgram_entry.insert(0, deepgram_key)

        # NEW: Add ElevenLabs API Key field
        ttk.Label(frame, text="ElevenLabs API Key:").grid(row=4, column=0, sticky="w", pady=10)
        elevenlabs_entry = ttk.Entry(frame, width=50, show="•")
        elevenlabs_entry.grid(row=4, column=1, sticky="ew", padx=(10, 5), pady=10)
        elevenlabs_entry.insert(0, elevenlabs_key)

        # Add toggle buttons to show/hide keys
        def toggle_show_hide(entry):
            current = entry['show']
            entry['show'] = '' if current else '•'
        
        ttk.Button(frame, text="👁", width=3, command=lambda: toggle_show_hide(openai_entry)).grid(row=0, column=2, padx=5)
        ttk.Button(frame, text="👁", width=3, command=lambda: toggle_show_hide(grok_entry)).grid(row=1, column=2, padx=5)
        ttk.Button(frame, text="👁", width=3, command=lambda: toggle_show_hide(perplexity_entry)).grid(row=2, column=2, padx=5)
        ttk.Button(frame, text="👁", width=3, command=lambda: toggle_show_hide(deepgram_entry)).grid(row=3, column=2, padx=5)
        ttk.Button(frame, text="👁", width=3, command=lambda: toggle_show_hide(elevenlabs_entry)).grid(row=4, column=2, padx=5)

        # Provide info about where to get API keys - add more vertical spacing
        info_text = ("Get your API keys at:\n"
                    "• OpenAI: https://platform.openai.com/account/api-keys\n"
                    "• Grok (X.AI): https://x.ai\n"
                    "• Perplexity: https://docs.perplexity.ai/\n"
                    "• Deepgram: https://console.deepgram.com/signup\n"
                    "• ElevenLabs: https://elevenlabs.io/app/speech-to-text")
        ttk.Label(frame, text=info_text, justify="left", wraplength=450).grid(
            row=5, column=0, columnspan=3, sticky="w", pady=20)

        def update_api_keys():
            new_openai = openai_entry.get().strip()
            new_deepgram = deepgram_entry.get().strip()
            new_grok = grok_entry.get().strip()
            new_perplexity = perplexity_entry.get().strip()
            new_elevenlabs = elevenlabs_entry.get().strip()  # NEW: Get ElevenLabs key

            # Update .env file
            try:
                # Read existing content
                env_content = ""
                if os.path.exists(".env"):
                    with open(".env", "r") as f:
                        env_content = f.read()
                
                # Update or add each key
                env_lines = env_content.split("\n")
                updated_lines = []
                keys_updated = set()
                
                for line in env_lines:
                    # Fix: Change startsWith to startswith (Python string method is lowercase)
                    if line.strip() == "" or line.strip().startswith("#"):
                        updated_lines.append(line)
                        continue
                        
                    if "OPENAI_API_KEY=" in line:
                        updated_lines.append(f"OPENAI_API_KEY={new_openai}")
                        keys_updated.add("OPENAI_API_KEY")
                    elif "DEEPGRAM_API_KEY=" in line:
                        updated_lines.append(f"DEEPGRAM_API_KEY={new_deepgram}")
                        keys_updated.add("DEEPGRAM_API_KEY")
                    elif "GROK_API_KEY=" in line:
                        updated_lines.append(f"GROK_API_KEY={new_grok}")
                        keys_updated.add("GROK_API_KEY")
                    elif "PERPLEXITY_API_KEY=" in line:
                        updated_lines.append(f"PERPLEXITY_API_KEY={new_perplexity}")
                        keys_updated.add("PERPLEXITY_API_KEY")
                    elif "ELEVENLABS_API_KEY=" in line:  # NEW: Update ElevenLabs key
                        updated_lines.append(f"ELEVENLABS_API_KEY={new_elevenlabs}")
                        keys_updated.add("ELEVENLABS_API_KEY")
                    else:
                        updated_lines.append(line)
                
                # Add keys that weren't in the file
                if "OPENAI_API_KEY" not in keys_updated and new_openai:
                    updated_lines.append(f"OPENAI_API_KEY={new_openai}")
                if "DEEPGRAM_API_KEY" not in keys_updated and new_deepgram:
                    updated_lines.append(f"DEEPGRAM_API_KEY={new_deepgram}")
                if "GROK_API_KEY" not in keys_updated and new_grok:
                    updated_lines.append(f"GROK_API_KEY={new_grok}")
                if "PERPLEXITY_API_KEY" not in keys_updated and new_perplexity:
                    updated_lines.append(f"PERPLEXITY_API_KEY={new_perplexity}")
                if "ELEVENLABS_API_KEY" not in keys_updated and new_elevenlabs:
                    updated_lines.append(f"ELEVENLABS_API_KEY={new_elevenlabs}")
                
                # Make sure we have the RECOGNITION_LANGUAGE line
                if not any("RECOGNITION_LANGUAGE=" in line for line in updated_lines):
                    updated_lines.append("RECOGNITION_LANGUAGE=en-US")
                
                # Write back to file
                with open(".env", "w") as f:
                    f.write("\n".join(updated_lines))
                
                # Update environment variables in memory
                if new_openai:
                    os.environ["OPENAI_API_KEY"] = new_openai
                    openai.api_key = new_openai 
                if new_deepgram:
                    os.environ["DEEPGRAM_API_KEY"] = new_deepgram
                    # Update the client if needed
                    self.deepgram_api_key = new_deepgram
                    self.deepgram_client = DeepgramClient(api_key=self.deepgram_api_key) if self.deepgram_api_key else None
                if new_grok:
                    os.environ["GROK_API_KEY"] = new_grok
                if new_perplexity:
                    os.environ["PERPLEXITY_API_KEY"] = new_perplexity
                if new_elevenlabs:
                    os.environ["ELEVENLABS_API_KEY"] = new_elevenlabs
                    self.elevenlabs_api_key = new_elevenlabs
                
                # Update buttons if needed (enable or disable based on API keys)
                if new_openai:
                    self.refine_button.config(state=NORMAL)
                    self.improve_button.config(state=NORMAL)
                    self.soap_button.config(state=NORMAL)
                else:
                    self.refine_button.config(state=DISABLED)
                    self.improve_button.config(state=DISABLED)
                
                self.update_status("API keys updated successfully", status_type="success")
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update API keys: {str(e)}")

        # Add more padding to the button frame
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20, padx=20)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=15).pack(side=tk.LEFT, padx=20)
        ttk.Button(btn_frame, text="Update Keys", command=update_api_keys, bootstyle="success", width=15).pack(side=tk.LEFT, padx=20)

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
        mic_frame = ttk.Frame(self, padding=10)
        mic_frame.pack(side=TOP, fill=tk.X, padx=20, pady=(20, 10))
        ttk.Label(mic_frame, text="Select Microphone:").pack(side=LEFT, padx=(0, 10))
        self.mic_names = get_valid_microphones() or sr.Microphone.list_microphone_names()
        self.mic_combobox = ttk.Combobox(mic_frame, values=self.mic_names, state="readonly", width=50)
        self.mic_combobox.pack(side=LEFT)
        if self.mic_names:
            self.mic_combobox.current(0)
        else:
            self.mic_combobox.set("No microphone found")
        refresh_btn = ttk.Button(mic_frame, text="Refresh", command=self.refresh_microphones, bootstyle="PRIMARY")
        refresh_btn.pack(side=LEFT, padx=10)
        ToolTip(refresh_btn, "Refresh the list of available microphones.")
        
        # Create a frame for the provider selection
        provider_frame = ttk.Frame(mic_frame)
        provider_frame.pack(side=LEFT, padx=10)
        
        # Add a label for the provider dropdown
        ttk.Label(provider_frame, text="Provider:").pack(side=LEFT, padx=(0, 5))
        
        # Create a dropdown for provider selection instead of a button
        from settings import SETTINGS, save_settings
        provider = SETTINGS.get("ai_provider", "openai")
        
        # Available provider options
        providers = ["openai", "perplexity", "grok"]
        provider_display = ["OpenAI", "Perplexity", "Grok"]  # Capitalized display names
        
        # Create the provider selection combobox
        self.provider_combobox = ttk.Combobox(
            provider_frame, 
            values=provider_display,
            state="readonly",
            width=12
        )
        self.provider_combobox.pack(side=LEFT)
        
        # Set the current value
        try:
            current_index = providers.index(provider.lower())
            self.provider_combobox.current(current_index)
        except (ValueError, IndexError):
            # Default to OpenAI if provider not found in list
            self.provider_combobox.current(0)
        
        # Add callback for when selection changes
        def on_provider_change(event):
            selected_index = self.provider_combobox.current()
            if 0 <= selected_index < len(providers):
                selected_provider = providers[selected_index]
                SETTINGS["ai_provider"] = selected_provider
                save_settings(SETTINGS)
                self.update_status(f"AI Provider set to {provider_display[selected_index]}")
        
        self.provider_combobox.bind("<<ComboboxSelected>>", on_provider_change)
        ToolTip(self.provider_combobox, "Select which AI provider to use")
        
        # NEW: Add Speech-to-Text provider selection with ElevenLabs
        stt_frame = ttk.Frame(mic_frame)
        stt_frame.pack(side=LEFT, padx=10)
        
        # Add label for STT provider dropdown
        ttk.Label(stt_frame, text="Speech To Text:").pack(side=LEFT, padx=(0, 5))
        
        # Available STT provider options - add ElevenLabs
        stt_providers = ["elevenlabs", "deepgram", "google"]
        stt_display = ["ElevenLabs", "Deepgram", "Google"]
        
        # Get current STT provider from settings
        stt_provider = SETTINGS.get("stt_provider", "deepgram")
        
        # Create the STT provider selection combobox
        self.stt_combobox = ttk.Combobox(
            stt_frame,
            values=stt_display,
            state="readonly",
            width=12
        )
        self.stt_combobox.pack(side=LEFT)
        
        # Set the current value
        try:
            stt_index = stt_providers.index(stt_provider.lower())
            self.stt_combobox.current(stt_index)
        except (ValueError, IndexError):
            # Default to Deepgram if provider not found in list
            self.stt_combobox.current(0)
        
        # Add callback for when STT selection changes
        def on_stt_change(event):
            selected_index = self.stt_combobox.current()
            if 0 <= selected_index < len(stt_providers):
                selected_stt = stt_providers[selected_index]
                SETTINGS["stt_provider"] = selected_stt
                save_settings(SETTINGS)
                self.update_status(f"Speech-to-Text provider set to {stt_display[selected_index]}")
        
        self.stt_combobox.bind("<<ComboboxSelected>>", on_stt_change)
        ToolTip(self.stt_combobox, "Select which Speech-to-Text provider to use")

        # NEW: Force use of "clam" theme and configure custom Notebook style
        style = ttk.Style()
        # Removed theme_use("clam") to prevent conflict with ttkbootstrap's theme
        # style.theme_use("clam")
        style.configure("Green.TNotebook", background="white", borderwidth=0)
        style.configure("Green.TNotebook.Tab", padding=[10, 5], background="lightgrey", foreground="black")
        
        # Map the foreground (text color) based on tab state
        style.map("Green.TNotebook.Tab",
            background=[("selected", "teal"), ("active", "teal"), ("!selected", "lightgrey")],
            foreground=[("selected", "white"), ("!selected", "black")]  # White text when selected, black otherwise
        )
        
        # Get success color from ttkbootstrap theme
        success_color = style.colors.success
        
        # Configure notebook with success color for active tabs
        style.configure("Green.TNotebook", background="white", borderwidth=0)
        style.configure("Green.TNotebook.Tab", padding=[10, 5], background="lightgrey", foreground="black")
        
        # Map the foreground (text color) and background based on tab state
        style.map("Green.TNotebook.Tab",
            background=[("selected", success_color), ("active", success_color), ("!selected", "lightgrey")],
            foreground=[("selected", "white"), ("!selected", "black")]
        )
        
        # Create the Notebook using the custom style
        self.notebook = ttk.Notebook(self, style="Green.TNotebook")

        # NEW: Create notebook with four tabs
        self.notebook.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)
        transcript_frame = ttk.Frame(self.notebook)
        soap_frame = ttk.Frame(self.notebook)
        referral_frame = ttk.Frame(self.notebook)
        dictation_frame = ttk.Frame(self.notebook)  # NEW: Dictation tab
        self.notebook.add(transcript_frame, text="Transcript")
        self.notebook.add(soap_frame, text="SOAP Note")
        self.notebook.add(referral_frame, text="Referral")
        self.notebook.add(dictation_frame, text="Dictation")  # NEW
        self.transcript_text = scrolledtext.ScrolledText(transcript_frame, wrap=tk.WORD, width=80, height=12, font=("Segoe UI", 11), undo=True, autoseparators=False)
        self.transcript_text.pack(fill=tk.BOTH, expand=True)
        self.soap_text = scrolledtext.ScrolledText(soap_frame, wrap=tk.WORD, width=80, height=12, font=("Segoe UI", 11), undo=True, autoseparators=False)
        self.soap_text.pack(fill=tk.BOTH, expand=True)
        self.referral_text = scrolledtext.ScrolledText(referral_frame, wrap=tk.WORD, width=80, height=12, font=("Segoe UI", 11), undo=True, autoseparators=False)
        self.referral_text.pack(fill=tk.BOTH, expand=True)
        self.dictation_text = scrolledtext.ScrolledText(dictation_frame, wrap=tk.WORD, width=80, height=12, font=("Segoe UI", 11), undo=True, autoseparators=False)  # NEW
        self.dictation_text.pack(fill=tk.BOTH, expand=True)
        # NEW: Set initial active text widget and bind tab change event
        self.active_text_widget = self.transcript_text
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        control_frame = ttk.Frame(self, padding=10)
        control_frame.pack(side=TOP, fill=tk.X, padx=20, pady=10)
        ttk.Label(control_frame, text="Individual Controls", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w", padx=5, pady=(0, 5))
        main_controls = ttk.Frame(control_frame)
        main_controls.grid(row=1, column=0, sticky="w")
        
        # Change the record button to be a toggle button that starts/stops recording
        self.record_button = ttk.Button(main_controls, text="Start Dictation", width=15, 
                                        command=self.toggle_recording, bootstyle="success")
        self.record_button.grid(row=0, column=0, padx=5, pady=5)
        ToolTip(self.record_button, "Start or stop recording audio.")
        
        # Hide the stop button as we'll use the record button for both functions
        # self.stop_button = ttk.Button(main_controls, text="Stop", width=10, command=self.stop_recording, state=DISABLED, bootstyle="danger")
        # self.stop_button.grid(row=0, column=1, padx=5, pady=5)
        # ToolTip(self.stop_button, "Stop recording audio.")
        
        # Change button text from "New Dictation" to "New Session"
        self.new_session_button = ttk.Button(main_controls, text="New Session", width=12, command=self.new_session, bootstyle="warning")
        self.new_session_button.grid(row=0, column=1, padx=5, pady=5)  # Adjust column to 1 since stop button is removed
        
        self.undo_button = ttk.Button(main_controls, text="Undo", width=10, command=self.undo_text, bootstyle="SECONDARY")
        self.undo_button.grid(row=0, column=3, padx=5, pady=5)
        ToolTip(self.undo_button, "Undo the last change.")
        # NEW: Add redo button next to undo button
        self.redo_button = ttk.Button(main_controls, text="Redo", width=10, command=self.redo_text, bootstyle="SECONDARY")
        self.redo_button.grid(row=0, column=4, padx=5, pady=5)
        ToolTip(self.redo_button, "Redo the last undone change.")
        # Move Copy Text button to column 5 (between Redo and Save)
        self.copy_button = ttk.Button(main_controls, text="Copy Text", width=10, command=self.copy_text, bootstyle="PRIMARY")
        self.copy_button.grid(row=0, column=5, padx=5, pady=5)
        ToolTip(self.copy_button, "Copy the text to the clipboard.")
        # Adjust Save and Load buttons to columns 6 and 7
        self.save_button = ttk.Button(main_controls, text="Save", width=10, command=self.save_text, bootstyle="PRIMARY")
        self.save_button.grid(row=0, column=6, padx=5, pady=5)
        ToolTip(self.save_button, "Save the transcription and audio to files.")
        self.load_button = ttk.Button(main_controls, text="Load", width=10, command=self.load_audio_file, bootstyle="PRIMARY")
        self.load_button.grid(row=0, column=7, padx=5, pady=5)
        ToolTip(self.load_button, "Load an audio file and transcribe.")

        ttk.Label(control_frame, text="AI Assist", font=("Segoe UI", 11, "bold")).grid(row=2, column=0, sticky="w", padx=5, pady=(10, 5))
        ttk.Label(control_frame, text="Individual Controls", font=("Segoe UI", 10, "italic")).grid(row=3, column=0, sticky="w", padx=5, pady=(0, 5))
        ai_buttons = ttk.Frame(control_frame)
        ai_buttons.grid(row=4, column=0, sticky="w")
        self.refine_button = ttk.Button(ai_buttons, text="Refine Text", width=15, command=self.refine_text, bootstyle="SECONDARY")
        self.refine_button.grid(row=0, column=0, padx=5, pady=5)
        ToolTip(self.refine_button, "Refine text using OpenAI.")
        self.improve_button = ttk.Button(ai_buttons, text="Improve Text", width=15, command=self.improve_text, bootstyle="SECONDARY")
        self.improve_button.grid(row=0, column=1, padx=5, pady=5)
        ToolTip(self.improve_button, "Improve text clarity using OpenAI.")
        self.soap_button = ttk.Button(ai_buttons, text="SOAP Note", width=15, command=self.create_soap_note, bootstyle="SECONDARY")
        self.soap_button.grid(row=0, column=2, padx=5, pady=5)
        ToolTip(self.soap_button, "Create a SOAP note using OpenAI.")
        self.referral_button = ttk.Button(ai_buttons, text="Referral", width=15, command=self.create_referral, bootstyle="SECONDARY")
        self.referral_button.grid(row=0, column=3, padx=5, pady=5)
        ToolTip(self.referral_button, "Generate a referral paragraph using OpenAI.")
        
        # ADD NEW BUTTON: Letter button
        self.letter_button = ttk.Button(ai_buttons, text="Letter", width=15, command=self.create_letter, bootstyle="SECONDARY")
        self.letter_button.grid(row=0, column=4, padx=5, pady=5)
        ToolTip(self.letter_button, "Generate a professional letter from text.")
        
        ttk.Label(control_frame, text="Automation Controls", font=("Segoe UI", 10, "italic")).grid(row=5, column=0, sticky="w", padx=5, pady=(0, 5))
        automation_frame = ttk.Frame(control_frame)
        automation_frame.grid(row=6, column=0, sticky="w")
        self.record_soap_button = ttk.Button(
            automation_frame, text="Record SOAP Note", width=25,
            command=self.toggle_soap_recording, bootstyle="success"
        )
        self.record_soap_button.grid(row=0, column=0, padx=5, pady=5)
        ToolTip(self.record_soap_button, "Record audio for SOAP note without live transcription.")
        # New pause/resume button for SOAP Note recording
        self.pause_soap_button = ttk.Button(
            automation_frame, text="Pause", width=15,
            command=self.toggle_soap_pause, bootstyle="SECONDARY", state=tk.DISABLED
        )
        self.pause_soap_button.grid(row=0, column=1, padx=5, pady=5)
        ToolTip(self.pause_soap_button, "Pause/Resume the SOAP note recording.")

        status_frame = ttk.Frame(self, padding=(10, 5))
        status_frame.pack(side=BOTTOM, fill=tk.X)
        
        # Enhanced status indicator with icon and color indicators
        self.status_icon_label = ttk.Label(status_frame, text="•", font=("Segoe UI", 16), foreground="gray")
        self.status_icon_label.pack(side=LEFT, padx=(5, 0))
        
        self.status_label = ttk.Label(
            status_frame, 
            text="Status: Idle", 
            anchor="w",
            font=("Segoe UI", 10)
        )
        self.status_label.pack(side=LEFT, fill=tk.X, expand=True, padx=(5, 0))
        
        # Add current AI provider indicator to status bar
        provider = SETTINGS.get("ai_provider", "openai").capitalize()
        self.provider_indicator = ttk.Label(
            status_frame, 
            text=f"Using: {provider}",
            anchor="e",
            font=("Segoe UI", 9),
            foreground="gray"
        )
        self.provider_indicator.pack(side=LEFT, padx=(0, 10))
        
        self.progress_bar = ttk.Progressbar(status_frame, mode="indeterminate")
        self.progress_bar.pack(side=RIGHT, padx=10)
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        
        # For automatic status clearing
        self.status_timer = None

    def bind_shortcuts(self) -> None:
        self.bind("<Control-n>", lambda event: self.new_session())
        self.bind("<Control-s>", lambda event: self.save_text())
        self.bind("<Control-c>", lambda event: self.copy_text())
        self.bind("<Control-l>", lambda event: self.load_audio_file())

    def show_about(self) -> None:
        messagebox.showinfo("About", "Medical Assistant App\nDeveloped using Vibe Coding.")

    def show_shortcuts(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Shortcuts & Voice Commands")
        dialog.geometry("700x500")
        dialog.transient(self)
        dialog.grab_set()
        notebook = ttk.Notebook(dialog)
        notebook.pack(expand=True, fill="both", padx=10, pady=10)
        kb_frame = ttk.Frame(notebook)
        notebook.add(kb_frame, text="Keyboard Shortcuts")
        kb_tree = ttk.Treeview(kb_frame, columns=("Command", "Description"), show="headings")
        kb_tree.heading("Command", text="Command")
        kb_tree.heading("Description", text="Description")
        kb_tree.column("Command", width=150, anchor="w")
        kb_tree.column("Description", width=500, anchor="w")
        kb_tree.pack(expand=True, fill="both", padx=10, pady=10)
        for cmd, desc in {"Ctrl+N": "New dictation", "Ctrl+S": "Save", "Ctrl+C": "Copy text", "Ctrl+L": "Load Audio File"}.items():
            kb_tree.insert("", tk.END, values=(cmd, desc))
        vc_frame = ttk.Frame(notebook)
        notebook.add(vc_frame, text="Voice Commands")
        vc_tree = ttk.Treeview(vc_frame, columns=("Command", "Action"), show="headings")
        vc_tree.heading("Command", text="Voice Command")
        vc_tree.heading("Action", text="Action")
        vc_tree.column("Command", width=200, anchor="w")
        vc_tree.column("Action", width=450, anchor="w")
        vc_tree.pack(expand=True, fill="both", padx=10, pady=10)
        for cmd, act in {
            "new paragraph": "Insert two newlines",
            "new line": "Insert a newline",
            "full stop": "Insert period & capitalize next",
            "delete last word": "Delete last word"
        }.items():
            vc_tree.insert("", tk.END, values=(cmd, act))
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

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
        # Cancel any pending status timer
        if self.status_timer:
            self.after_cancel(self.status_timer)
            self.status_timer = None
        
        # Cancel all scheduled status updates
        for timer_id in self.status_timers:
            if timer_id:
                try:
                    self.after_cancel(timer_id)
                except Exception:
                    pass
        self.status_timers = []
        
        # Update status text
        self.status_label.config(text=f"Status: {message}")
        
        # Color-code the status indicator based on status_type
        status_colors = {
            "success": "#28a745",  # Green
            "info": "#17a2b8",     # Blue
            "warning": "#ffc107",  # Yellow
            "error": "#dc3545",    # Red
            "idle": "gray"         # Gray for idle state
        }
        
        # Status icons - using circle symbol with different colors
        self.status_icon_label.config(
            foreground=status_colors.get(status_type, status_colors["info"])
        )
        
        # Make status message more prominent for important messages
        if status_type in ["error", "warning"]:
            self.status_label.config(font=("Segoe UI", 10, "bold"))
        else:
            self.status_label.config(font=("Segoe UI", 10))
        
        # Update AI provider indicator when it changes
        provider = SETTINGS.get("ai_provider", "openai").capitalize()
        stt_provider = SETTINGS.get("stt_provider", "deepgram").capitalize()
        self.provider_indicator.config(text=f"Using: {provider} | STT: {stt_provider}")
        
        # For non-error messages, set a timer to clear status after a delay
        if status_type != "error" and status_type != "progress":
            # Clear status after 8 seconds unless it's an error or progress indicator
            self.status_timer = self.after(8000, lambda: self.reset_status())

    def reset_status(self) -> None:
        """Reset status to idle state after timeout"""
        self.status_label.config(text="Status: Idle", font=("Segoe UI", 10))
        self.status_icon_label.config(foreground="gray")
        self.status_timer = None

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
        self.update_status("Transcribing audio...")
        self.load_button.config(state=DISABLED)
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
                    self._update_text_area(transcript, "Audio transcribed successfully.", self.load_button, self.transcript_text),
                    self.notebook.select(0)
                ])
            else:
                self.after(0, lambda: messagebox.showerror("Transcription Error", "Failed to transcribe audio."))
                
            # Always re-enable button and hide progress bar
            self.after(0, lambda: self.load_button.config(state=NORMAL))
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
        self.update_status("Processing text...")
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
        self.update_status(success_message, status_type="success")
        button.config(state=NORMAL)
        self.progress_bar.stop()
        self.progress_bar.pack_forget()

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
        self.update_status("Processing SOAP note...")
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

    def _get_possible_conditions(self, text: str) -> str:
        from ai import call_ai, remove_markdown, remove_citations
        prompt = ("Extract up to a maximun of 5 relevant medical conditions for a referral from the following text. Keep the condition names simple and specific and not longer that 3 words. "
                  "Return them as a comma-separated list. Text: " + text)
        result = call_ai("gpt-4", "You are a physician specialized in referrals.", prompt, 0.7, 100)
        conditions = remove_markdown(result).strip()
        conditions = remove_citations(conditions)
        return conditions

    def create_referral(self) -> None:
        # Check if the transcript is empty before proceeding
        text = self.transcript_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Empty Transcript", "The transcript is empty. Please add content before creating a referral.")
            return
            
        # New: Immediately update status and display progress bar on referral click
        self.update_status("Referral button clicked - preparing referral...")
        self.progress_bar.pack(side=RIGHT, padx=10)
        self.progress_bar.start()
        
        # New: Get suggested conditions asynchronously
        def get_conditions() -> str:
            return self._get_possible_conditions(text)
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
        self.update_status(f"Processing referral for conditions: {focus}...", status_type="progress")
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
        timer_id = self.after(delay_ms, lambda: self.update_status(message, status_type))
        self.status_timers.append(timer_id)
        return timer_id

    def show_letter_options_dialog(self) -> tuple:
        """Show dialog to get letter source and specifications from user"""
        # Increase dialog size from 600x400 to 700x550 for better fit
        dialog = create_toplevel_dialog(self, "Letter Options", "700x700")
        
        # Add a main frame with padding for better spacing
        main_frame = ttk.Frame(dialog, padding=(20, 20, 20, 20))
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Select text source for the letter:", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 10))
        
        # Improve radio button section with a frame
        source_frame = ttk.Frame(main_frame)
        source_frame.pack(fill="x", pady=(0, 15), anchor="w")
        
        source_var = tk.StringVar(value="transcript")
        ttk.Radiobutton(source_frame, text="Use text from Transcript tab", variable=source_var, value="transcript").pack(anchor="w", padx=20, pady=5)
        ttk.Radiobutton(source_frame, text="Use text from Dictation tab", variable=source_var, value="dictation").pack(anchor="w", padx=20, pady=5)
        
        ttk.Label(main_frame, text="Letter specifications:", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(10, 5))
        ttk.Label(main_frame, text="Enter any specific requirements for the letter (tone, style, formality, purpose, etc.)", 
                  wraplength=650, font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 10))
        
        # Make the text area larger and ensure it fills available width
        specs_text = scrolledtext.ScrolledText(main_frame, height=8, width=80, font=("Segoe UI", 10))
        specs_text.pack(fill="both", expand=True, pady=(0, 20))
        
        # Add some example text to help users
        example_text = "Examples:\n- Formal letter to a specialist for patient referral\n- Patient instruction letter\n- Response to insurance company\n- Follow-up appointment instructions"
        specs_text.insert("1.0", example_text)
        specs_text.tag_add("gray", "1.0", "end")
        specs_text.tag_config("gray", foreground="gray")
        
        # Clear example text when user clicks in the field
        def clear_example(event):
            if specs_text.get("1.0", "end-1c").strip() == example_text.strip():
                specs_text.delete("1.0", "end")
                specs_text.tag_remove("gray", "1.0", "end")
            specs_text.unbind("<FocusIn>")  # Only clear once
        
        specs_text.bind("<FocusIn>", clear_example)
        
        result = [None, None]
        
        def on_submit():
            result[0] = source_var.get()
            result[1] = specs_text.get("1.0", "end-1c")
            # If user didn't change example text, provide empty specs
            if result[1].strip() == example_text.strip():
                result[1] = ""
            dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        # Improve button layout
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        ttk.Button(btn_frame, text="Cancel", command=on_cancel, width=15).pack(side="left", padx=10, pady=10)
        ttk.Button(btn_frame, text="Generate Letter", command=on_submit, bootstyle="success", width=15).pack(side="right", padx=10, pady=10)
        
        # Center the dialog on the screen
        dialog.update_idletasks()
        dialog.geometry("+{}+{}".format(
            (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2),
            (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        ))
        
        dialog.wait_window()
        return result[0], result[1]

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
        self.update_status(f"Generating letter from {source_name} text...", status_type="progress")
        self.progress_bar.pack(side=RIGHT, padx=10)
        self.progress_bar.start()
        self.letter_button.config(state=DISABLED)
        
        def task() -> None:
            try:
                # Generate letter using AI
                letter = self._generate_letter_with_ai(text, specs)
                
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

    def _generate_letter_with_ai(self, text: str, specs: str) -> str:
        """Use the selected AI provider to generate a professional letter"""
        from ai import call_ai, remove_markdown, remove_citations
        
        # Create a prompt for the AI
        prompt = f"Create a professional letter based on the following text content:\n\n{text}\n\n"
        if specs.strip():
            prompt += f"Special instructions: {specs}\n\n"
        
        prompt += "Format the letter properly with date, recipient, greeting, body, closing, and signature."
        
        # Call the AI with the letter generation prompt
        system_message = "You are an expert medical professional specializing in writing professional medical letters. Create well-formatted correspondence that is clear, concise, and appropriate for medical communication."
        
        # Use the currently selected AI provider
        from settings import SETTINGS
        current_provider = SETTINGS.get("ai_provider", "openai")
        
        result = call_ai("gpt-4o", system_message, prompt, 0.7, 2000)
        
        # Clean up any markdown formatting from the result
        clean_result = remove_markdown(result)
        clean_result = remove_citations(clean_result)
        
        return clean_result

    def show_elevenlabs_settings(self) -> None:
        """Show dialog to configure ElevenLabs speech-to-text settings."""
        from settings import SETTINGS, _DEFAULT_SETTINGS, save_settings
        
        # Get current ElevenLabs settings with fallback to defaults
        elevenlabs_settings = SETTINGS.get("elevenlabs", {})
        default_settings = _DEFAULT_SETTINGS["elevenlabs"]
        
        dialog = create_toplevel_dialog(self, "ElevenLabs Settings", "650x750")
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Create form with current settings
        ttk.Label(frame, text="ElevenLabs Speech-to-Text Settings", 
                  font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky="w")
        
        # Model ID
        ttk.Label(frame, text="Model ID:").grid(row=1, column=0, sticky="w", pady=10)
        model_var = tk.StringVar(value=elevenlabs_settings.get("model_id", default_settings["model_id"]))
        model_combo = ttk.Combobox(frame, textvariable=model_var, width=30)
        model_combo['values'] = ["scribe_v1", "scribe_v1_base"]  # Updated to supported models only
        model_combo.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=10)
        ttk.Label(frame, text="The AI model to use for transcription.", 
                  wraplength=400, foreground="gray").grid(row=2, column=0, columnspan=2, sticky="w", padx=(20, 0))
        
        # Language Code
        ttk.Label(frame, text="Language Code:").grid(row=3, column=0, sticky="w", pady=10)
        lang_var = tk.StringVar(value=elevenlabs_settings.get("language_code", default_settings["language_code"]))
        lang_entry = ttk.Entry(frame, textvariable=lang_var, width=30)
        lang_entry.grid(row=3, column=1, sticky="w", padx=(10, 0), pady=10)
        ttk.Label(frame, text="Optional ISO language code (e.g., 'en-US'). Leave empty for auto-detection.", 
                  wraplength=400, foreground="gray").grid(row=4, column=0, columnspan=2, sticky="w", padx=(20, 0))
        
        # Tag Audio Events
        ttk.Label(frame, text="Tag Audio Events:").grid(row=5, column=0, sticky="w", pady=10)
        tag_events_var = tk.BooleanVar(value=elevenlabs_settings.get("tag_audio_events", default_settings["tag_audio_events"]))
        tag_events_check = ttk.Checkbutton(frame, variable=tag_events_var)
        tag_events_check.grid(row=5, column=1, sticky="w", padx=(10, 0), pady=10)
        ttk.Label(frame, text="Add timestamps and labels for audio events like silence, music, etc.", 
                  wraplength=400, foreground="gray").grid(row=6, column=0, columnspan=2, sticky="w", padx=(20, 0))
        
        # Number of Speakers
        ttk.Label(frame, text="Number of Speakers:").grid(row=7, column=0, sticky="w", pady=10)
        
        # Create a custom variable handler for the special "None" case
        speakers_value = elevenlabs_settings.get("num_speakers", default_settings["num_speakers"])
        speakers_str = "" if speakers_value is None else str(speakers_value)
        speakers_entry = ttk.Entry(frame, width=30)
        speakers_entry.insert(0, speakers_str)
        speakers_entry.grid(row=7, column=1, sticky="w", padx=(10, 0), pady=10)
        
        ttk.Label(frame, text="Optional number of speakers. Leave empty for auto-detection.", 
                  wraplength=400, foreground="gray").grid(row=8, column=0, columnspan=2, sticky="w", padx=(20, 0))
        
        # Timestamps Granularity
        ttk.Label(frame, text="Timestamps Granularity:").grid(row=9, column=0, sticky="w", pady=10)
        granularity_var = tk.StringVar(value=elevenlabs_settings.get("timestamps_granularity", default_settings["timestamps_granularity"]))
        granularity_combo = ttk.Combobox(frame, textvariable=granularity_var, width=30)
        granularity_combo['values'] = ["word", "segment", "sentence"]
        granularity_combo.grid(row=9, column=1, sticky="w", padx=(10, 0), pady=10)
        
        # Diarize
        ttk.Label(frame, text="Diarize:").grid(row=10, column=0, sticky="w", pady=10)
        diarize_var = tk.BooleanVar(value=elevenlabs_settings.get("diarize", default_settings["diarize"]))
        diarize_check = ttk.Checkbutton(frame, variable=diarize_var)
        diarize_check.grid(row=10, column=1, sticky="w", padx=(10, 0), pady=10)
        ttk.Label(frame, text="Identify different speakers in the audio.", 
                  wraplength=400, foreground="gray").grid(row=11, column=0, columnspan=2, sticky="w", padx=(20, 0))
        
        # Create the buttons frame
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=12, column=0, columnspan=2, pady=(20, 0), sticky="e")
        
        # Save handler - renamed to avoid conflict with imported save_settings
        def save_elevenlabs_settings():
            # Parse the number of speakers value (None or int)
            try:
                num_speakers = None if not speakers_entry.get().strip() else int(speakers_entry.get())
            except ValueError:
                messagebox.showerror("Invalid Input", "Number of speakers must be a valid integer or empty.")
                return
                
            # Build the new settings
            new_settings = {
                "model_id": model_var.get(),
                "language_code": lang_var.get(),
                "tag_audio_events": tag_events_var.get(),
                "num_speakers": num_speakers,
                "timestamps_granularity": granularity_var.get(),
                "diarize": diarize_var.get()
            }
            
            # Update the settings
            SETTINGS["elevenlabs"] = new_settings
            save_settings(SETTINGS)  # This now refers to the imported save_settings function
            self.update_status("ElevenLabs settings saved successfully", status_type="success")
            dialog.destroy()
        
        # Cancel handler
        def cancel():
            dialog.destroy()
        
        ttk.Button(btn_frame, text="Cancel", command=cancel, width=10).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Save", command=save_elevenlabs_settings, bootstyle="success", width=10).pack(side="left", padx=5)
