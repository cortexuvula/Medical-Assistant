# Import console suppression patch first (Windows only)
try:
    import suppress_console
except ImportError:
    pass  # Not critical if it fails

import json
import string
import logging
import os
import sys
from concurrent_log_handler import ConcurrentRotatingFileHandler
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import multiprocessing
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
# Import tkinter constants for compatibility
from tkinter import TOP, BOTTOM, LEFT, RIGHT, NORMAL, DISABLED
from dotenv import load_dotenv
import openai
from typing import Callable
import threading
import numpy as np
from pydub import AudioSegment
from datetime import datetime as dt
import tempfile
from cleanup_utils import clear_all_content
from database import Database

# Set up logging configuration
def setup_logging():
    """Set up logging with rotation to keep file size manageable"""
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # Path to the log file
    log_file = os.path.join(log_dir, "medical_dictation.log")
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Create and configure rotating file handler
    # Set maxBytes to a reasonable size that will hold approximately 1000 entries
    # Each log entry is roughly 100-200 bytes, so 200KB should hold ~1000 entries
    file_handler = ConcurrentRotatingFileHandler(
        log_file, 
        maxBytes=200*1024,  # 200 KB
        backupCount=2  # Keep 2 backup files in addition to the current one
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Also add console handler for stdout output
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    logging.info("Logging initialized")
    logging.info(f"Log file path: {log_file}")

setup_logging()

# Add this import for creating .env file
from pathlib import Path

# Requests is imported later if needed

from utils import get_valid_microphones
from ai import adjust_text_with_openai, improve_text_with_openai, create_soap_note_with_openai, get_possible_conditions
from settings import SETTINGS, save_settings  # Add save_settings here
from dialogs import create_toplevel_dialog, show_settings_dialog, show_api_keys_dialog, show_shortcuts_dialog, show_about_dialog, show_letter_options_dialog, show_elevenlabs_settings_dialog, show_deepgram_settings_dialog  # Add this import

# Add near the top of the file
import time

# Add to imports section
from audio import AudioHandler

# Add these imports:
from ui_components import UIComponents
from text_processor import TextProcessor

# Add this import at the top with other imports
from status_manager import StatusManager
from ffmpeg_utils import configure_pydub

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
        
        # NEW: Add GROQ API Key field
        tk.Label(keys_frame, text="GROQ API Key:").grid(row=5, column=0, sticky="w", pady=5)
        groq_entry = tk.Entry(keys_frame, width=40)
        groq_entry.grid(row=5, column=1, sticky="ew", pady=5)
        
        # Add info about where to find the keys
        info_text = ("Get your API keys at:\n"
                    "• OpenAI: https://platform.openai.com/account/api-keys\n"
                    "• Grok (X.AI): https://x.ai\n"
                    "• Perplexity: https://docs.perplexity.ai/\n"
                    "• Deepgram: https://console.deepgram.com/signup\n"
                    "• ElevenLabs: https://elevenlabs.io/app/speech-to-text\n"
                    "• GROQ: https://groq.com/")
        tk.Label(keys_frame, text=info_text, justify="left", wraplength=450).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=10)
        
        error_var = tk.StringVar()
        error_label = tk.Label(api_root, textvariable=error_var, foreground="red", wraplength=450)
        error_label.pack(pady=5)
        
        def validate_and_save():
            openai_key = openai_entry.get().strip()
            deepgram_key = deepgram_entry.get().strip()
            grok_key = grok_entry.get().strip()
            perplexity_key = perplexity_entry.get().strip()
            elevenlabs_key = elevenlabs_entry.get().strip()  # NEW: Get ElevenLabs key
            groq_key = groq_entry.get().strip()  # NEW: Get GROQ key
            
            # Check if at least one of OpenAI, Grok, or Perplexity keys is provided
            if not (openai_key or grok_key or perplexity_key):
                error_var.set("Error: At least one of OpenAI, Grok, or Perplexity API keys is required.")
                return
                
            # Check if at least one speech-to-text API key is provided
            if not (deepgram_key or elevenlabs_key or groq_key):
                error_var.set("Error: Either Deepgram, ElevenLabs, or GROQ API key is mandatory for speech recognition.")
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
                # NEW: Add GROQ key if provided
                if groq_key:
                    f.write(f"GROQ_API_KEY={groq_key}\n")
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
    """Main function to start the application."""
    # Configure FFmpeg paths before anything else
    configure_pydub()
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Log application startup
    logging.info("Medical Dictation application starting")
    
    # Check for .env file
    # Commented out to skip API key dialog
    # if not check_env_file():
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
            import sys
            logging.debug(f"Error: {exc_type.__name__}: {exc_value}", file=sys.stderr)
        
        # Don't show popup for TclErrors - these are usually harmless UI timing issues
        if exc_type.__name__ != "TclError":
            # Show error message to user for other types of errors
            try:
                messagebox.showerror("Error", f"An unexpected error occurred: {exc_value}")
            except:
                pass
    
    # Set exception handler for uncaught exceptions - bind to the app instance
    app.report_callback_exception = lambda exc, val, tb: handle_exception(exc.__class__, exc, tb)
    
    # Start the app
    app.mainloop()
    
    # Log application shutdown
    logging.info("Medical Dictation application shutting down")

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
        
        # Set window icon
        try:
            # Determine if we're running as a PyInstaller bundle
            if getattr(sys, 'frozen', False):
                # Running as compiled executable
                # PyInstaller sets sys._MEIPASS to the temp folder where files are extracted
                bundle_dir = sys._MEIPASS
            else:
                # Running as script
                bundle_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Try to load the icon file
            icon_path = os.path.join(bundle_dir, 'icon.ico')
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
                logging.debug(f"Window icon set from: {icon_path}")
            else:
                # Try alternate icon in case of different resolutions
                alt_icon_path = os.path.join(bundle_dir, 'icon256x256.ico')
                if os.path.exists(alt_icon_path):
                    self.iconbitmap(alt_icon_path)
                    logging.debug(f"Window icon set from alternate: {alt_icon_path}")
                else:
                    logging.warning(f"Icon file not found at: {icon_path} or {alt_icon_path}")
        except Exception as e:
            logging.warning(f"Could not set window icon: {e}")
        
        # Get screen dimensions and calculate appropriate window size
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Check if we have saved window dimensions in settings
        saved_width = SETTINGS.get("window_width", 0)
        saved_height = SETTINGS.get("window_height", 0)
        
        if saved_width > 0 and saved_height > 0:
            # Use saved dimensions if they exist and are valid
            window_width = saved_width
            window_height = saved_height
        else:
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
        
        # Add binding for window resize to save dimensions
        self.bind("<Configure>", self.on_window_configure)
        
        # Variables to optimize resize event handling
        self.resize_timer = None
        self.last_width = window_width
        self.last_height = window_height
        
        # Initialize API keys and handlers
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.deepgram_api_key = os.getenv("DEEPGRAM_API_KEY", "")
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        self.recognition_language = os.getenv("RECOGNITION_LANGUAGE", "en-US")
        
        # Check for necessary API keys
        elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
        deepgram_key = os.getenv("DEEPGRAM_API_KEY")
        groq_key = os.getenv("GROQ_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")
        grok_key = os.getenv("GROK_API_KEY")
        perplexity_key = os.getenv("PERPLEXITY_API_KEY")
        ollama_url = os.getenv("OLLAMA_API_URL")
        
        # Check if we have at least one LLM and one STT provider
        has_llm = bool(openai_key or grok_key or perplexity_key or ollama_url)
        has_stt = bool(elevenlabs_key or deepgram_key or groq_key)
        
        if not has_llm or not has_stt:
            messagebox.showinfo(
                "API Keys Required", 
                "Welcome to Medical Assistant!\n\n" +
                "To use this application, you need:\n" +
                "• At least one LLM provider (OpenAI, Grok, Perplexity, or Ollama)\n" +
                "• At least one STT provider (Groq, Deepgram, or ElevenLabs)\n\n" +
                "Please configure your API keys."
            )
            # Open the API key dialog
            result = show_api_keys_dialog(self)
            if result:
                # Update the keys after dialog closes
                self.deepgram_api_key = os.getenv("DEEPGRAM_API_KEY", "")
                self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "")
                self.groq_api_key = os.getenv("GROQ_API_KEY", "")
                openai.api_key = os.getenv("OPENAI_API_KEY")
        
        # Initialize audio handler
        self.audio_handler = AudioHandler(
            elevenlabs_api_key=self.elevenlabs_api_key,
            deepgram_api_key=self.deepgram_api_key,
            groq_api_key=self.groq_api_key,
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
        # self.soap_audio_segments = [] # Replaced by pending_soap_segments and combined_soap_chunks
        self.pending_soap_segments = [] # Segments collected since last combination
        self.combined_soap_chunks = [] # List of larger, combined audio chunks
        self.soap_combine_threshold = 100 # Combine every N pending segments
        self.soap_stop_listening_function = None
        self.listening = False  # Initialize listening flag for recording state
        self.current_recording_id = None  # Track the ID of the currently loaded recording

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

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Add a list to track all scheduled status updates
        self.status_timers = []
        self.status_timer = None
        
        # Initialize database
        self.db = Database()
        self.db.create_tables()

    def create_menu(self) -> None:
        menubar = tk.Menu(self)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="New", command=self.new_session, accelerator="Ctrl+N")
        filemenu.add_command(label="Save", command=self.save_text, accelerator="Ctrl+S")
        filemenu.add_command(label="View Recordings", command=self.show_recordings_dialog)
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
        settings_menu.add_command(label="Temperature Settings", command=self.show_temperature_settings)
        
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
        settings_menu.add_command(label="Record Prefix Audio", command=self.record_prefix_audio)
        settings_menu.add_command(label="Toggle Theme", command=self.toggle_theme)  # NEW: Add toggle theme option
        menubar.add_cascade(label="Settings", menu=settings_menu)

        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="About", command=self.show_about)
        helpmenu.add_command(label="Keyboard Shortcuts", command=self.show_shortcuts)
        helpmenu.add_command(label="View Logs", command=self.view_logs)
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
        # Create a toplevel dialog for prefix audio recording
        prefix_dialog = create_toplevel_dialog(self, "Record Prefix Audio", "600x400")
        
        # Create instruction label
        instruction_text = "This audio will be prepended to all recordings before sending to the STT provider.\n"
        instruction_text += "Record a short introduction or context that you want to include at the beginning of all your dictations."
        ttk.Label(prefix_dialog, text=instruction_text, wraplength=550).pack(pady=(20, 10))
        
        # Status variable and label
        status_var = tk.StringVar(value="Ready to record")
        status_label = ttk.Label(prefix_dialog, textvariable=status_var)
        status_label.pack(pady=10)
        
        # Create microphone selection dropdown
        mic_frame = ttk.Frame(prefix_dialog)
        mic_frame.pack(pady=5, fill="x", padx=20)
        
        ttk.Label(mic_frame, text="Select Microphone:").pack(side="left", padx=(0, 10))
        
        # Get available microphones
        available_mics = get_valid_microphones()
        
        # Create microphone selection variable
        mic_var = tk.StringVar(prefix_dialog)
        
        # Get the currently selected microphone from settings
        selected_mic = SETTINGS.get("selected_microphone", "")
        
        # Set the dropdown to the currently selected microphone if available
        if selected_mic and selected_mic in available_mics:
            mic_var.set(selected_mic)
        elif available_mics:
            mic_var.set(available_mics[0])
        
        # Create dropdown menu
        mic_dropdown = ttk.Combobox(mic_frame, textvariable=mic_var, width=40)
        mic_dropdown["values"] = available_mics
        mic_dropdown.pack(side="left", fill="x", expand=True)
        
        # Create frame for buttons
        button_frame = ttk.Frame(prefix_dialog)
        button_frame.pack(pady=10)
        
        # Recording state variables
        recording_active = False
        stop_recording_func = None
        preview_segment = None
        audio_segments = []  # Accumulate segments
        original_soap_mode = False  # Store original SOAP mode
        
        # Path to the prefix audio file
        prefix_audio_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prefix_audio.mp3")
        
        # Function to handle audio data from recording
        def on_audio_data(audio_data):
            nonlocal audio_segments
            try:
                # Process the audio data into a segment
                segment, _ = self.audio_handler.process_audio_data(audio_data)
                if segment:
                    audio_segments.append(segment)
                    duration = sum(seg.duration_seconds for seg in audio_segments)
                    status_var.set(f"Recording... {duration:.1f} seconds captured")
            except Exception as e:
                logging.error(f"Error processing prefix audio: {e}", exc_info=True)
                status_var.set(f"Error: {str(e)}")
        
        # Function to start recording
        def start_recording():
            nonlocal recording_active, stop_recording_func, audio_segments, original_soap_mode
            if recording_active:
                return
                
            # Get the selected microphone
            mic_name = mic_var.get()
            if not mic_name:
                status_var.set("Error: No microphone selected")
                return
                
            try:
                # Clear previous segments
                audio_segments = []
                
                # Make sure SOAP mode is disabled for prefix recording
                original_soap_mode = self.audio_handler.soap_mode
                self.audio_handler.soap_mode = False
                
                # Play start sound
                self.play_recording_sound(start=True)
                
                # Start recording
                recording_active = True
                status_var.set("Recording... speak now")
                record_button.config(state=DISABLED)
                stop_button.config(state=NORMAL)
                preview_button.config(state=DISABLED)
                save_button.config(state=DISABLED)
                
                # Use the audio handler to start listening
                stop_recording_func = self.audio_handler.listen_in_background(
                    mic_name, 
                    on_audio_data,
                    phrase_time_limit=10  # Use 10 seconds to prevent cutoffs
                )
            except Exception as e:
                recording_active = False
                logging.error(f"Error starting prefix recording: {e}", exc_info=True)
                status_var.set(f"Error: {str(e)}")
                record_button.config(state=NORMAL)
                stop_button.config(state=DISABLED)
        
        # Function to stop recording
        def stop_recording():
            nonlocal recording_active, stop_recording_func
            if not recording_active or not stop_recording_func:
                return
            
            # Disable buttons immediately
            stop_button.config(state=DISABLED)
            status_var.set("Processing recording...")
            
            # Run the actual stop process in a thread to avoid blocking UI
            def stop_recording_thread():
                nonlocal preview_segment, audio_segments, recording_active, stop_recording_func
                try:
                    # Play stop sound
                    self.play_recording_sound(start=False)
                    
                    # Stop the recording
                    stop_recording_func()
                    recording_active = False
                    stop_recording_func = None
                    
                    # Restore original SOAP mode
                    self.audio_handler.soap_mode = original_soap_mode
                    
                    # Combine all segments if we have any
                    if audio_segments:
                        # Combine all segments into one
                        preview_segment = self.audio_handler.combine_audio_segments(audio_segments)
                        if preview_segment:
                            duration = preview_segment.duration_seconds
                            # Update UI on main thread
                            prefix_dialog.after(0, lambda: [
                                status_var.set(f"Recording stopped - {duration:.1f} seconds captured"),
                                preview_button.config(state=NORMAL),
                                save_button.config(state=NORMAL),
                                record_button.config(state=NORMAL)
                            ])
                        else:
                            prefix_dialog.after(0, lambda: [
                                status_var.set("Recording stopped - no audio captured"),
                                record_button.config(state=NORMAL)
                            ])
                    else:
                        prefix_dialog.after(0, lambda: [
                            status_var.set("Recording stopped - no audio captured"),
                            record_button.config(state=NORMAL)
                        ])
                except Exception as e:
                    logging.error(f"Error stopping prefix recording: {e}", exc_info=True)
                    prefix_dialog.after(0, lambda: [
                        status_var.set(f"Error: {str(e)}"),
                        record_button.config(state=NORMAL)
                    ])
            
            # Start the thread
            threading.Thread(target=stop_recording_thread, daemon=True).start()
        
        # Function to preview the recorded audio
        def preview_audio():
            nonlocal preview_segment
            if not preview_segment:
                status_var.set("No recording to preview")
                return
                
            try:
                # Create a temporary file for preview
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                    preview_segment.export(temp_file.name, format="mp3", bitrate="192k")
                    # Open the file with the default audio player
                    if os.name == 'nt':  # Windows
                        os.startfile(temp_file.name)
                    else:  # macOS or Linux
                        import subprocess
                        subprocess.Popen(['open', temp_file.name] if sys.platform == 'darwin' else ['xdg-open', temp_file.name])
                status_var.set("Playing preview")
            except Exception as e:
                logging.error(f"Error previewing audio: {e}", exc_info=True)
                status_var.set(f"Error previewing: {str(e)}")
        
        # Function to save the recorded audio
        def save_audio():
            nonlocal preview_segment
            if not preview_segment:
                status_var.set("No recording to save")
                return
                
            try:
                # Export the audio segment to the application directory
                preview_segment.export(prefix_audio_path, format="mp3", bitrate="192k")
                status_var.set(f"Prefix audio saved successfully to {prefix_audio_path}")
                self.status_manager.success("Prefix audio saved successfully")
                prefix_dialog.destroy()
            except Exception as e:
                logging.error(f"Error saving prefix audio: {e}", exc_info=True)
                status_var.set(f"Error saving: {str(e)}")
        
        # Add buttons
        record_button = ttk.Button(button_frame, text="Record", command=start_recording)
        record_button.pack(side=tk.LEFT, padx=5)
        
        stop_button = ttk.Button(button_frame, text="Stop", command=stop_recording, state=DISABLED)
        stop_button.pack(side=tk.LEFT, padx=5)
        
        preview_button = ttk.Button(button_frame, text="Preview", command=preview_audio, state=DISABLED)
        preview_button.pack(side=tk.LEFT, padx=5)
        
        save_button = ttk.Button(button_frame, text="Save", command=save_audio, state=DISABLED)
        save_button.pack(side=tk.LEFT, padx=5)
        
        # Add cancel button
        ttk.Button(prefix_dialog, text="Cancel", command=prefix_dialog.destroy).pack(pady=20)
        
        # Check if prefix audio already exists and show info
        if os.path.exists(prefix_audio_path):
            file_info = f"Existing prefix audio found. Recording will replace the current file."
            ttk.Label(prefix_dialog, text=file_info, foreground="blue").pack(pady=10)
            
            # Add button to delete existing prefix
            def delete_prefix():
                try:
                    os.remove(prefix_audio_path)
                    status_var.set("Existing prefix audio deleted")
                    delete_button.config(state=DISABLED)
                except Exception as e:
                    logging.error(f"Error deleting prefix audio: {e}", exc_info=True)
                    status_var.set(f"Error deleting: {str(e)}")
            
            delete_button = ttk.Button(prefix_dialog, text="Delete Existing Prefix", command=delete_prefix)
            delete_button.pack(pady=5)

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
        """
        Set the default storage folder for the application using a custom folder selector
        that avoids native file dialogs entirely to prevent UI freezing.
        """
        logging.info("STORAGE: Opening custom folder selection dialog")
        
        # Create a custom folder selection dialog
        dialog = tk.Toplevel(self)
        dialog.title("Select Storage Folder")
        dialog.geometry("600x500")
        dialog.transient(self)
        dialog.grab_set()
        
        # Center the dialog on the parent window
        x = self.winfo_x() + (self.winfo_width() // 2) - (600 // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (500 // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Create main frame with padding
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Add explanation label
        ttk.Label(main_frame, text="Select a folder for storing recordings and exports", 
                 wraplength=580).pack(pady=(0, 10))
        
        # Create a frame for the path entry and navigation
        path_frame = ttk.Frame(main_frame)
        path_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Current path display
        path_var = tk.StringVar(value=os.path.expanduser("~"))
        path_entry = ttk.Entry(path_frame, textvariable=path_var, width=50)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # Use a simple default rather than dealing with file dialogs
        def use_default_location():
            # Use the 'exports' directory in the application folder
            app_dir = os.path.dirname(os.path.abspath(__file__))
            default_storage = os.path.join(app_dir, "storage")
            
            # Create the directory if it doesn't exist
            try:
                os.makedirs(default_storage, exist_ok=True)
                path_var.set(default_storage)
                refresh_file_list()
                logging.info(f"STORAGE: Using default location: {default_storage}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not create default storage folder: {e}")
                logging.error(f"STORAGE: Error creating default folder: {str(e)}", exc_info=True)
        
        # Button for default location
        default_btn = ttk.Button(path_frame, text="Use Default", command=use_default_location)
        default_btn.pack(side=tk.RIGHT)
        
        # Frame for directory listing with scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Create scrollbar and listbox for directories
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        dir_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=("Segoe UI", 10))
        dir_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=dir_listbox.yview)
        
        # Function to refresh the directory listing
        def refresh_file_list():
            current_path = path_var.get()
            if not os.path.exists(current_path):
                # If path doesn't exist, try to fall back to user's home directory
                current_path = os.path.expanduser("~")
                path_var.set(current_path)
            
            # Clear the listbox
            dir_listbox.delete(0, tk.END)
            
            # Add parent directory option if not at root
            if os.path.abspath(current_path) != os.path.abspath(os.path.dirname(current_path)):
                dir_listbox.insert(tk.END, "..")
            
            try:
                # List directories only
                dirs = [d for d in os.listdir(current_path) 
                       if os.path.isdir(os.path.join(current_path, d))]
                dirs.sort()
                
                for d in dirs:
                    dir_listbox.insert(tk.END, d)
                    
                status_var.set(f"Found {len(dirs)} directories")
            except Exception as e:
                status_var.set(f"Error: {str(e)}")
                logging.error(f"STORAGE: Error listing directories: {str(e)}", exc_info=True)
        
        # Handle double-click on directory
        def on_dir_double_click(_):
            selection = dir_listbox.curselection()
            if selection:
                item = dir_listbox.get(selection[0])
                current_path = path_var.get()
                
                if item == "..":
                    # Go up one directory
                    new_path = os.path.dirname(current_path)
                else:
                    # Enter selected directory
                    new_path = os.path.join(current_path, item)
                
                path_var.set(new_path)
                refresh_file_list()
        
        # Bind double-click event
        dir_listbox.bind("<Double-1>", on_dir_double_click)
        
        # Status bar
        status_var = tk.StringVar()
        status_bar = ttk.Label(main_frame, textvariable=status_var, anchor="w")
        status_bar.pack(fill=tk.X, pady=(5, 10))
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        # Function to set the selected folder
        def set_selected_folder():
            selected_path = path_var.get()
            if os.path.exists(selected_path) and os.path.isdir(selected_path):
                try:
                    from settings import SETTINGS, save_settings
                    
                    # Set both keys for backwards compatibility
                    SETTINGS["storage_folder"] = selected_path
                    SETTINGS["default_storage_folder"] = selected_path
                    save_settings(SETTINGS)
                    
                    self.status_manager.success(f"Storage folder set to: {selected_path}")
                    logging.info(f"STORAGE: Folder set to {selected_path}")
                    dialog.destroy()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to set folder: {e}")
                    logging.error(f"STORAGE: Error setting folder: {str(e)}", exc_info=True)
            else:
                messagebox.showerror("Invalid Directory", "The selected path is not a valid directory.")
        
        # Add Select and Cancel buttons
        select_btn = ttk.Button(button_frame, text="Select This Folder", command=set_selected_folder, style="primary.TButton")
        select_btn.pack(side=tk.LEFT, padx=(0, 5), fill=tk.X, expand=True)
        
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=dialog.destroy)
        cancel_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        
        # Initial directory listing
        refresh_file_list()

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
        
        # Add binding for window resize to save dimensions
        self.mic_combobox.bind("<<ComboboxSelected>>", self._on_microphone_change)
        
        # Create control panel with buttons - inside main_content
        self.control_frame, self.buttons = self.ui.create_control_panel(command_map)
        self.control_frame.pack(side=TOP, fill=tk.X, padx=10, pady=5)
        
        # Create notebook with text areas - inside main_content with expand=True
        self.notebook, self.transcript_text, self.soap_text, self.referral_text, self.letter_text = self.ui.create_notebook()
        self.notebook.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
        
        # Set initial active text widget and bind tab change event
        self.active_text_widget = self.transcript_text
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
        # Access common buttons from self.buttons
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
        self.bind("<Control-n>", lambda _: self.new_session())
        self.bind("<Control-s>", lambda _: self.save_text())
        self.bind("<Control-c>", lambda _: self.copy_text())
        self.bind("<Control-l>", lambda _: self.load_audio_file())
        self.bind("<Control-z>", lambda _: self.undo_text())
        self.bind("<Control-y>", lambda _: self.redo_text())
        self.bind("<F5>", lambda _: self.toggle_recording())
        self.bind("<Control-Shift-S>", lambda _: self.toggle_soap_recording())
        self.bind("<Alt-t>", lambda _: self.toggle_theme())

    def show_about(self) -> None:
        # Call the refactored function from dialogs.py
        show_about_dialog(self)

    def show_shortcuts(self) -> None:
        # Call the refactored function from dialogs.py
        show_shortcuts_dialog(self)

    def show_refine_settings_dialog(self) -> None:
        from settings import SETTINGS, _DEFAULT_SETTINGS
        from prompts import REFINE_PROMPT, REFINE_SYSTEM_MESSAGE
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
            current_system_prompt=cfg.get("system_message", REFINE_SYSTEM_MESSAGE)
        )

    def show_improve_settings_dialog(self) -> None:
        from settings import SETTINGS, _DEFAULT_SETTINGS
        from prompts import IMPROVE_PROMPT, IMPROVE_SYSTEM_MESSAGE
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
            current_system_prompt=cfg.get("system_message", IMPROVE_SYSTEM_MESSAGE)
        )

    def show_soap_settings_dialog(self) -> None:
        from settings import SETTINGS, _DEFAULT_SETTINGS
        from prompts import SOAP_PROMPT_TEMPLATE, SOAP_SYSTEM_MESSAGE
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
            current_system_prompt=cfg.get("system_message", default_system_prompt)
        )

    def show_referral_settings_dialog(self) -> None:
        from settings import SETTINGS, _DEFAULT_SETTINGS
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
            current_system_prompt=cfg.get("system_message", default_system_prompt)
        )

    def show_temperature_settings(self) -> None:
        """Show dialog to configure temperature settings for each AI provider."""
        from temperature_dialog import show_temperature_settings_dialog
        show_temperature_settings_dialog(self)
        self.status_manager.success("Temperature settings saved successfully")

    def save_refine_settings(self, prompt: str, openai_model: str, perplexity_model: str, grok_model: str, ollama_model: str, system_prompt: str) -> None:
        from settings import save_settings, SETTINGS
        SETTINGS["refine_text"] = {
            "prompt": prompt,
            "system_message": system_prompt,
            "model": openai_model,
            "perplexity_model": perplexity_model,
            "grok_model": grok_model,
            "ollama_model": ollama_model
        }
        save_settings(SETTINGS)
        self.status_manager.success("Refine text settings saved successfully")

    def save_improve_settings(self, prompt: str, openai_model: str, perplexity_model: str, grok_model: str, ollama_model: str, system_prompt: str) -> None:
        from settings import save_settings, SETTINGS
        SETTINGS["improve_text"] = {
            "prompt": prompt,
            "system_message": system_prompt,
            "model": openai_model,
            "perplexity_model": perplexity_model,
            "grok_model": grok_model,
            "ollama_model": ollama_model
        }
        save_settings(SETTINGS)
        self.status_manager.success("Improve text settings saved successfully")

    def save_soap_settings(self, prompt: str, openai_model: str, perplexity_model: str, grok_model: str, ollama_model: str, system_prompt: str) -> None:
        from settings import save_settings, SETTINGS
        SETTINGS["soap_note"] = {
            "prompt": prompt,
            "system_message": system_prompt,
            "model": openai_model,
            "perplexity_model": perplexity_model,
            "grok_model": grok_model,
            "ollama_model": ollama_model
        }
        save_settings(SETTINGS)
        self.status_manager.success("SOAP note settings saved successfully")

    def save_referral_settings(self, prompt: str, openai_model: str, perplexity_model: str, grok_model: str, ollama_model: str, system_prompt: str) -> None:
        from settings import save_settings, SETTINGS
        SETTINGS["referral"] = {
            "prompt": prompt,
            "system_message": system_prompt,
            "model": openai_model,
            "perplexity_model": perplexity_model,
            "grok_model": grok_model,
            "ollama_model": ollama_model
        }
        save_settings(SETTINGS)
        self.status_manager.success("Referral settings saved successfully")

    def new_session(self) -> None:
        if messagebox.askyesno("New Dictation", "Start a new session? Unsaved changes will be lost."):
            clear_all_content(self)

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
            from validation import validate_file_path
            
            # Validate file path before saving
            is_valid, error = validate_file_path(file_path, must_be_writable=True)
            if not is_valid:
                from error_codes import show_error_dialog
                show_error_dialog(self, "SYS_FILE_ACCESS", error)
                return
            
            try:
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(text)
                
                # Save audio if available using the AudioHandler
                if self.audio_segments:
                    base, _ = os.path.splitext(file_path)
                    audio_path = f"{base}.mp3"
                    if self.audio_handler.save_audio(self.audio_segments, audio_path):
                        messagebox.showinfo("Save Audio", f"Audio saved as: {audio_path}")
                
                messagebox.showinfo("Save Text", "Text saved successfully.")
            except Exception as e:
                from error_codes import show_error_dialog
                show_error_dialog(self, "SYS_FILE_ACCESS", f"Could not save file: {str(e)}")

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

    def process_soap_recording(self) -> None:
        """Process SOAP recording using AudioHandler with improved concurrency."""
        def task():
            try:
                # Reset the audio handler silence threshold to normal
                self.audio_handler.silence_threshold = 0.01
                
                # Turn off SOAP debug mode
                self.audio_handler.soap_mode = False
                
                # Combine any remaining pending segments
                if self.pending_soap_segments:
                    remaining_chunk = self.audio_handler.combine_audio_segments(self.pending_soap_segments)
                    if remaining_chunk:
                        self.combined_soap_chunks.append(remaining_chunk)
                    self.pending_soap_segments = [] # Clear pending list
                        
                # Check if we have any combined chunks to process
                if not self.combined_soap_chunks:
                    logging.warning("No SOAP audio chunks were recorded or combined.")
                    # Update UI to indicate no audio
                    self.after(0, lambda: [
                        self.status_manager.warning("No audio recorded for SOAP note."),
                        self.progress_bar.stop(),
                        self.progress_bar.pack_forget(),
                        self.soap_button.config(state=NORMAL), # Re-enable button
                        self.cancel_soap_button.config(state=DISABLED)
                    ])
                    return # Exit task early

                # Log info about the combined chunks before final combination
                num_chunks = len(self.combined_soap_chunks)
                approx_total_duration = sum(len(chunk) for chunk in self.combined_soap_chunks)
                logging.info(f"Processing {num_chunks} combined SOAP audio chunks, approx duration: {approx_total_duration}ms")
                
                # Update status on UI thread
                self.after(0, lambda: [
                    self.status_manager.progress("Finalizing SOAP audio..."),
                    self.progress_bar.pack(side=LEFT, padx=(5, 0))
                ])
                
                # Combine all the combined chunks into the final AudioSegment
                audio_segment = self.audio_handler.combine_audio_segments(self.combined_soap_chunks)
                
                # Clear the list of combined chunks now that we have the final segment
                self.combined_soap_chunks = []
                
                if not audio_segment:
                     # This case should be rare if checks above are done, but handle defensively
                    raise ValueError("Failed to create final audio segment from combined chunks")

                # --- Rest of the processing (saving, transcription) remains largely the same ---                   
                # Save the SOAP audio to the user's default storage folder
                from settings import SETTINGS
                
                # Try to get storage folder from both possible keys for backward compatibility
                storage_folder = SETTINGS.get("storage_folder")
                if not storage_folder:
                    storage_folder = SETTINGS.get("default_storage_folder")
                
                # If no storage folder is set, create default one
                if not storage_folder or not os.path.exists(storage_folder):
                    storage_folder = os.path.join(os.path.expanduser("~"), "Documents", "Medical-Dictation", "Storage")
                    os.makedirs(storage_folder, exist_ok=True)
                    
                # Create a user-friendly timestamp format: DD-MM-YY_HH-MM as requested
                date_formatted = dt.now().strftime("%d-%m-%y")
                time_formatted = dt.now().strftime("%H-%M")
                
                # Combine into a user-friendly filename
                # Format: recording_DD-MM-YY_HH-MM.mp3
                audio_path = os.path.join(storage_folder, f"recording_{date_formatted}_{time_formatted}.mp3")
                
                # Save the audio file
                if audio_segment:
                    segment_length_ms = len(audio_segment)
                    segment_frame_rate = audio_segment.frame_rate
                    segment_channels = audio_segment.channels
                    segment_sample_width = audio_segment.sample_width
                    segment_max_volume = float(getattr(audio_segment, "max", -1))
                    
                    logging.info(f"SOAP audio segment stats: length={segment_length_ms}ms, "
                                f"rate={segment_frame_rate}Hz, channels={segment_channels}, "
                                f"width={segment_sample_width}bytes, max_volume={segment_max_volume}")
                    
                    # Check if the audio segment has meaningful content
                    if segment_length_ms < 100:  # Less than 100ms is probably empty
                        logging.warning(f"SOAP audio segment is too short ({segment_length_ms}ms), might be empty")
                    
                if self.audio_handler.save_audio([audio_segment], audio_path):
                    logging.info(f"SOAP audio saved to: {audio_path}")
                    self.after(0, lambda: self.status_manager.progress(f"SOAP audio saved to: {audio_path}"))
                
                # Update status on UI thread
                self.after(0, lambda: [
                    self.status_manager.progress("Transcribing SOAP audio..."),
                    self.progress_bar.pack(side=LEFT, padx=(5, 0))
                ])
                
                # Try transcription with the unified transcribe_audio method that handles prefix audio
                self.after(0, lambda: self.status_manager.progress("Transcribing SOAP audio with prefix..."))
                
                # Use the transcribe_audio method which already handles prefix audio and fallbacks
                transcript = self.audio_handler.transcribe_audio(audio_segment)
                
                # Log the result
                if transcript:
                    logging.info("Successfully transcribed SOAP audio with prefix")
                else:
                    logging.warning("Failed to transcribe SOAP audio with any provider")
                # If all transcription methods failed
                if not transcript:
                    raise ValueError("All transcription methods failed - no text recognized")
                
                # Log success and progress
                logging.info(f"Successfully transcribed audio, length: {len(transcript)} chars")
                
                # Update transcript tab with the raw transcript
                self.after(0, lambda: [
                    self.transcript_text.delete("1.0", tk.END),
                    self.transcript_text.insert(tk.END, transcript),
                    self.status_manager.progress("Creating SOAP note from transcript...")
                ])
                
                # Use IO executor for the AI API call (I/O-bound operation)
                future = self.io_executor.submit(
                    create_soap_note_with_openai,
                    transcript
                )
                
                # Get result with timeout to prevent hanging
                result = future.result(timeout=120)
                
                # Store the values we need for database operations
                soap_note = result
                filename = "Transcript"
                
                # Schedule UI update on the main thread and save to database
                self.after(0, lambda: [
                    self._update_text_area(soap_note, "SOAP note created", self.soap_button, self.soap_text),
                    self.notebook.select(1),  # Switch to SOAP tab
                    # Save to database on the main thread
                    self._save_soap_recording_to_database(filename, transcript, soap_note)
                ])
            except concurrent.futures.TimeoutError:
                self.after(0, lambda: [
                    self.status_manager.error("SOAP note creation timed out. Please try again."),
                    self.soap_button.config(state=NORMAL),
                    self.progress_bar.stop(),
                    self.progress_bar.pack_forget()
                ])
            except Exception as e:
                error_msg = f"Error processing SOAP note: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.after(0, lambda: [
                    self.status_manager.error(error_msg),
                    self.soap_button.config(state=NORMAL),
                    self.progress_bar.stop(),
                    self.progress_bar.pack_forget()
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
                # Use IO executor for the AI API call (I/O-bound operation)
                future = self.io_executor.submit(
                    create_soap_note_with_openai,
                    transcript
                )
                
                # Get result with timeout to prevent hanging
                result = future.result(timeout=120)
                
                # Store the values we need for database operations
                soap_note = result
                filename = "Transcript"
                
                # Schedule UI update on the main thread and save to database
                self.after(0, lambda: [
                    self._update_text_area(soap_note, "SOAP note created", self.soap_button, self.soap_text),
                    self.notebook.select(1),  # Switch to SOAP tab
                    # Save to database on the main thread
                    self._save_soap_recording_to_database(filename, transcript, soap_note)
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
                do_refresh()
                
        def do_refresh():
            """Perform the actual microphone refresh."""
            try:
                # Get available microphones using common method
                from utils import get_valid_microphones
                from settings import SETTINGS, save_settings
                
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
                
                # Reset button state and cursor
                if refresh_btn:
                    refresh_btn.config(text="⟳", state=tk.NORMAL)
                
                # Reset cursor
                try:
                    self.config(cursor="")
                except:
                    pass

    def toggle_soap_recording(self) -> None:
        """Toggle SOAP note recording using AudioHandler."""
        if not self.soap_recording:
            # Switch focus to the SOAP tab
            self.notebook.select(1)
            
            # Clear all text fields and audio segments before starting a new recording
            clear_all_content(self)
            
            # Start SOAP recording
            try:
                selected_device = self.mic_combobox.get()
                
                # Play recording start sound
                self.play_recording_sound(start=True)
                
                self.update_status("Recording SOAP note...", "info")
                
                # Get the actual device index if using the new naming format
                from utils import get_device_index_from_name
                device_index = get_device_index_from_name(selected_device)
                
                # Log the selected device information
                logging.info(f"Starting SOAP recording with device: {selected_device} (index {device_index})")
                
                # Initialize empty audio segments list
                self.pending_soap_segments = [] # Segments collected since last combination
                self.combined_soap_chunks = [] # List of larger, combined audio chunks
                
                # Set debug flag for SOAP recording to help with troubleshooting
                self.audio_handler.soap_mode = True
                
                # Use a much lower silence threshold for SOAP recording
                self.audio_handler.silence_threshold = 0.0001  # Much lower for SOAP recording
                
                # Start recording using AudioHandler
                # Use shorter phrase time limit for SOAP to get more frequent callbacks
                self.soap_stop_listening_function = self.audio_handler.listen_in_background(
                    mic_name=selected_device,
                    callback=self.soap_callback,
                    phrase_time_limit=3  # Use 3 seconds for more frequent processing
                )
                
                # Update state and UI
                self.soap_recording = True
                self.record_soap_button.config(text="Stop Recording", bootstyle="danger")
                self.pause_soap_button.config(state=tk.NORMAL)
                self.cancel_soap_button.config(state=tk.NORMAL)
                
                # Disable other buttons during recording
                #self.record_button.config(state=tk.DISABLED)
                
            except Exception as e:
                logging.error("Error starting SOAP recording", exc_info=True)
                self.update_status(f"Error starting SOAP recording: {str(e)}", "error")
        else:
            # Stop SOAP recording
            def stop_recording_task():
                try:
                    if self.soap_stop_listening_function:
                        self.soap_stop_listening_function()
                        self.soap_stop_listening_function = None
                    
                    # Reset SOAP mode
                    self.audio_handler.soap_mode = False
                    self.audio_handler.silence_threshold = 0.001  # Reset to normal
                    
                    # Reset state
                    self.soap_recording = False
                    
                    # Update UI on main thread
                    self.after(0, lambda: [
                        self._finalize_soap_recording()
                    ])
                    
                except Exception as e:
                    logging.error("Error stopping SOAP recording", exc_info=True)
                    error_msg = str(e)
                    self.after(0, lambda: self.update_status(f"Error stopping SOAP recording: {error_msg}", "error"))
            
            # Run the cancellation process in a separate thread to avoid freezing the UI
            threading.Thread(target=stop_recording_task, daemon=True).start()
            
            # Update status immediately
            self.update_status("Finalizing SOAP recording...", "info")
            self.record_soap_button.config(state=tk.DISABLED)

    def _finalize_soap_recording(self):
        """Complete the SOAP recording process after ensuring all audio is captured."""
        # Play recording stop sound
        self.play_recording_sound(start=False)
        
        # Process the recorded audio segments
        self.process_soap_recording()
        
        # Reset all button states after processing is complete
        self.after(0, lambda: [
            self.record_soap_button.config(text="Record SOAP Note", state=tk.NORMAL, bootstyle="success"),
            self.pause_soap_button.config(text="Pause", state=tk.DISABLED, bootstyle="warning"),
            self.cancel_soap_button.config(state=tk.DISABLED),
            #self.record_button.config(state=tk.NORMAL)
        ])

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
            
            # Stop the current recording
            self.soap_stop_listening_function()
            self.soap_stop_listening_function = None
            
            # Update UI
            self.pause_soap_button.config(text="Resume", bootstyle="success")
            self.update_status("SOAP recording paused. Press Resume to continue.", "info")

    def resume_soap_recording(self) -> None:
        """Resume SOAP recording after pause using the selected microphone."""
        try:
            # Play resume sound
            self.play_recording_sound(start=True)
            
            # Get selected microphone name
            selected_device = self.mic_combobox.get()
            
            # Get the actual device index if using the new naming format
            from utils import get_device_index_from_name
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
            self.pause_soap_button.config(text="Pause", bootstyle="warning")
            self.update_status("SOAP recording resumed.", "info")
            
        except Exception as e:
            logging.error("Error resuming SOAP recording", exc_info=True)
            self.update_status(f"Error resuming SOAP recording: {str(e)}", "error")

    def soap_callback(self, audio_data) -> None:
        """Callback for SOAP note recording using AudioHandler."""
        try:
            # Directly handle numpy array data for potential efficiency
            if isinstance(audio_data, np.ndarray):
                max_amp = np.abs(audio_data).max()
                # logging.debug(f"SOAP callback processing np.ndarray, max_amp: {max_amp:.8f}")
                
                # Basic silence detection - adjust threshold as needed
                if self.audio_handler.soap_mode or max_amp > 0.0001: # Avoid processing completely silent chunks unless in SOAP mode
                    try:
                        # Ensure data is in the correct format (int16)
                        if audio_data.dtype != np.int16:
                            # Scale float32/64 [-1.0, 1.0] to int16 [-32768, 32767]
                            if audio_data.dtype in [np.float32, np.float64]:
                                audio_data = (audio_data * 32767).astype(np.int16)
                            else:
                                # Attempt conversion for other types, log warning
                                logging.warning(f"Unexpected audio data type {audio_data.dtype}, attempting conversion to int16")
                                audio_data = audio_data.astype(np.int16)
                        
                        new_segment = AudioSegment(
                            data=audio_data.tobytes(), 
                            sample_width=self.audio_handler.sample_width, 
                            frame_rate=self.audio_handler.sample_rate,
                            channels=self.audio_handler.channels
                        )
                        # logging.debug("SOAP callback: Successfully created AudioSegment from np.ndarray.")
                        # Add to segments list for later processing
                        self.pending_soap_segments.append(new_segment)
                        #logging.info(f"SOAP segment appended (from np.ndarray). Total segments: {len(self.pending_soap_segments)}")
                        
                        # Visual feedback that audio is being recorded
                        self.after(0, lambda: self.update_status("Recording SOAP note...", "info"))
                        return # Successfully processed, exit callback
                    except Exception as e:
                        logging.error(f"Error processing direct SOAP audio data (np.ndarray): {str(e)}", exc_info=True)
                        # Fall through to standard processing if direct fails
                        logging.warning("Falling back to standard audio processing for np.ndarray.")
                else:
                    logging.debug(f"SOAP audio segment skipped (np.ndarray) - amplitude too low ({max_amp:.8f})")
                    # Do not return here, let it potentially fall through if needed, although unlikely for low amplitude
            
            # Fall back to standard processing for non-ndarray types or if direct processing failed
            # logging.debug("SOAP callback using standard process_audio_data.")
            new_segment, _ = self.audio_handler.process_audio_data(audio_data)
            
            if new_segment:
                # logging.debug("SOAP callback: Successfully created AudioSegment via standard process.")
                # Add to segments list for later processing
                self.pending_soap_segments.append(new_segment)
                # logging.info(f"SOAP segment appended (from standard process). Total segments: {len(self.pending_soap_segments)}")
                
                # Visual feedback that audio is being recorded
                self.after(0, lambda: self.update_status("Recording SOAP note...", "info"))
            else:
                # Log the issue with audio data
                logging.warning(f"SOAP recording: No audio segment created via standard process from data of type {type(audio_data)}")
                max_amp_fallback = 0
                if isinstance(audio_data, np.ndarray):
                    max_amp_fallback = np.abs(audio_data).max()
                elif hasattr(audio_data, 'max_dBFS'): # Check for AudioData attribute
                    # Note: max_dBFS is logarithmic, not directly comparable to amplitude
                    max_amp_fallback = audio_data.max_dBFS 
                    logging.warning(f"SOAP recording: AudioData max_dBFS was {max_amp_fallback}")
                else:
                     logging.warning("SOAP recording: Could not determine max amplitude/dBFS for this data type.")
                     
                
                if isinstance(audio_data, np.ndarray):
                     logging.warning(f"SOAP recording (standard process): Max amplitude was {max_amp_fallback}")
                
                # Visual feedback for user if likely low volume
                if isinstance(audio_data, np.ndarray) and max_amp_fallback < 0.005:
                    self.after(0, lambda: self.update_status("Audio level too low - check microphone settings", "warning"))
                elif hasattr(audio_data, 'max_dBFS') and audio_data.max_dBFS < -40: # Heuristic for low dBFS
                     self.after(0, lambda: self.update_status("Audio level might be low - check microphone settings", "warning"))
                    
        except Exception as e:
            logging.error(f"Critical Error in SOAP callback: {str(e)}", exc_info=True)

        # --- Incremental Combination Logic ---            
        if new_segment:
            # Add the newly created segment to the pending list
            self.pending_soap_segments.append(new_segment)
            
            # Check if we reached the threshold to combine pending segments
            if len(self.pending_soap_segments) >= self.soap_combine_threshold:
                logging.debug(f"SOAP callback: Reached threshold ({self.soap_combine_threshold}), combining {len(self.pending_soap_segments)} pending segments.")
                # Combine the pending segments
                chunk_to_add = self.audio_handler.combine_audio_segments(self.pending_soap_segments)
                
                if chunk_to_add:
                    # Add the newly combined chunk to our list of larger chunks
                    self.combined_soap_chunks.append(chunk_to_add)
                    # logging.info(f"SOAP chunk combined and added. Total chunks: {len(self.combined_soap_chunks)}")
                else:
                    logging.warning("SOAP callback: Combining pending segments resulted in None.")
                    
                # Clear the pending list
                self.pending_soap_segments = []

            # Visual feedback (can be less frequent if needed)
            # Update status less frequently to avoid flooding UI updates
            if len(self.pending_soap_segments) % 10 == 1: # Update status every 10 segments added
                 self.after(0, lambda: self.update_status("Recording SOAP note...", "info"))
        # else: # Removed logging for no segment created to reduce noise
            # logging.warning(f"SOAP recording: No audio segment created from data of type {type(audio_data)}")
                
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
        self.record_soap_button.config(state=tk.DISABLED)

    def _cancel_soap_recording_finalize(self):
        """Finalize the cancellation of SOAP recording."""
        # Use the centralized cleanup function to clear all content
        clear_all_content(self)
        
        # Reset state variables
        self.soap_recording = False
        
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
                    
            # Stop any active listening in the audio handler
            if hasattr(self, 'audio_handler'):
                logging.info("Ensuring audio handler is properly closed...")
                try:
                    self.audio_handler.cleanup_resources()
                except Exception as e:
                    logging.error(f"Error cleaning up audio handler: {str(e)}", exc_info=True)
            
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
        else:
            self.active_text_widget = self.transcript_text

    def schedule_status_update(self, delay_ms: int, message: str, status_type: str = "info") -> None:
        """Schedule a status update that won't be automatically cleared after timeout"""
        return self.status_manager.schedule_status_update(delay_ms, message, status_type)

    def show_letter_options_dialog(self) -> tuple:
        # Call the refactored function from dialogs.py
        return show_letter_options_dialog(self)

    def create_letter(self) -> None:
        """Create a letter from transcript with improved concurrency."""
        # Get source and specifications
        source, specs = self.show_letter_options_dialog()
        
        if source is None:  # User cancelled
            return
            
        # Get the text based on selected source
        if source == "transcript":
            text = self.transcript_text.get("1.0", tk.END).strip()
            source_name = "Transcript"
        else:  # soap
            text = self.soap_text.get("1.0", tk.END).strip()
            source_name = "SOAP"
        
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
                # Use our custom scheduler for status updates
                self.schedule_status_update(3000, f"Still generating letter from {source_name}...", "progress")
                self.schedule_status_update(10000, f"Processing letter (this may take a moment)...", "progress")
                
                # Log that we're starting letter generation
                logging.info(f"Starting letter generation from {source_name} with specs: {specs}")
                
                # Import locally to avoid potential circular import
                from ai import create_letter_with_ai
                
                # Use CPU executor for the AI processing which is CPU-intensive
                future = self.io_executor.submit(create_letter_with_ai, text, specs)
                
                # Get result with a longer timeout to prevent hanging (5 minutes)
                result = future.result(timeout=300)
                
                # Log the successful completion
                logging.info("Successfully generated letter")
                
                # Check if result contains error message
                if result.startswith("Error creating letter:"):
                    raise Exception(result)
                
                # Schedule UI update on the main thread
                self.after(0, lambda: [
                    self._update_text_area(result, f"Letter generated from {source_name}", self.letter_button, self.letter_text),
                    self.notebook.select(3)  # Show letter in Letter tab (index 3)
                ])
                
                # Store the generated letter and recording ID for database update
                # We'll pass these to the main thread for database update
                generated_letter = result
                recording_id = self.current_recording_id
                
                # For database operations, schedule them on the main thread
                if recording_id:
                    # Schedule database update on main thread to avoid threading issues
                    self.after(0, lambda: self._save_letter_to_database(recording_id, generated_letter))
                        
            except concurrent.futures.TimeoutError:
                self.after(0, lambda: [
                    self.status_manager.error("Letter creation timed out. Please try again."),
                    self.letter_button.config(state=NORMAL),
                    self.progress_bar.stop(),
                    self.progress_bar.pack_forget()
                ])
            except Exception as e:
                error_msg = f"Error creating letter: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.after(0, lambda: [
                    self.status_manager.error(error_msg),
                    self.letter_button.config(state=NORMAL),
                    self.progress_bar.stop(),
                    self.progress_bar.pack_forget()
                ])

        # Actually submit the task to be executed
        self.io_executor.submit(task)

    def _save_letter_to_database(self, recording_id: int, letter_text: str) -> None:
        """Safely save letter to database from the main thread.
        
        Args:
            recording_id: ID of the recording to update
            letter_text: The generated letter text to save
        """
        try:
            # This runs on the main thread, so it's safe to use the database connection
            if self.db.update_recording(recording_id, letter=letter_text):
                logging.info(f"Saved letter to database for recording ID {recording_id}")
            else:
                logging.warning(f"Failed to save letter to database - no rows updated for ID {recording_id}")
        except Exception as db_error:
            error_msg = f"Error updating database: {str(db_error)}"
            logging.error(error_msg, exc_info=True)
            # Show error in the status bar
            self.status_manager.error(error_msg)
    
    def _save_soap_recording_to_database(self, filename: str, transcript: str, soap_note: str) -> None:
        """Save a SOAP recording to the database.
        
        Args:
            filename: The filename of the recorded audio
            transcript: The transcript from the recording
            soap_note: The generated SOAP note content
        """
        try:
            # Add a new recording to the database
            new_id = self.db.add_recording(filename=filename, transcript=transcript, soap_note=soap_note)
            
            if new_id:
                # Update the current recording ID to the newly created record
                self.current_recording_id = new_id
                logging.info(f"Saved SOAP recording to database with ID {new_id}")
                self.status_manager.success(f"Recording saved to database")
            else:
                logging.warning("Failed to save SOAP recording to database")
                self.status_manager.warning("Failed to save recording to database")
        except Exception as db_error:
            error_msg = f"Error saving to database: {str(db_error)}"
            logging.error(error_msg, exc_info=True)
            self.status_manager.error(error_msg)

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

    def _on_provider_change(self, _):
        from settings import SETTINGS, save_settings  # Import locally if preferred
        
        selected_index = self.provider_combobox.current()
        providers = ["openai", "grok", "perplexity"]
        provider_display = ["OpenAI", "Grok", "Perplexity"]
        
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
            from settings import SETTINGS, save_settings
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
            from settings import SETTINGS, save_settings
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
        try:
            self.style.theme_use(new_theme)
        except tk.TclError as e:
            # Catch and log the error instead of crashing
            if "Duplicate element" in str(e):
                logging.info(f"Ignoring harmless duplicate element error during theme change: {e}")
            else:
                # Re-raise if it's not the specific error we're handling
                raise
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
        text_widgets = [self.transcript_text, self.soap_text, self.referral_text]
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
        for _, btn in self.buttons.items():
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
            logging.debug(f"Updating theme button - is_dark: {is_dark}, theme: {new_theme}")
            
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
                logging.debug(f"Updated tooltip text to: {tooltip_text}")
        
        # Update the theme label if available
        if hasattr(self, 'theme_label') and self.theme_label:
            mode_text = "Light Mode" if not is_dark else "Dark Mode"
            self.theme_label.config(text=f"({mode_text})")
            logging.debug(f"Updated theme label to: ({mode_text})")
            
        # Update shortcut label in status bar to show theme toggle shortcut
        self.status_manager.info("Theme toggle shortcut: Alt+T")
        
        # Configure refresh button style based on theme
        if is_dark:
            # Dark mode - button is already visible against dark background
            self.style.configure("Refresh.TButton", foreground="#f8f9fa")  # Light text on dark background
            self.style.map("Refresh.TButton", 
                foreground=[("pressed", "#f8f9fa"), ("active", "#f8f9fa")],
                background=[("pressed", "#0d6efd"), ("active", "#0d6efd")])
                
            # Find and update refresh button if it exists
            for widget in self.winfo_children():
                self._update_refresh_button_bootstyle(widget, "dark")
        else:
            # Light mode - make button text white for visibility
            self.style.configure("Refresh.TButton", foreground="white")  # White text for better visibility
            self.style.map("Refresh.TButton", 
                foreground=[("pressed", "white"), ("active", "white")],
                background=[("pressed", "#0d6efd"), ("active", "#0d6efd")])
                
            # Find and update refresh button if it exists
            for widget in self.winfo_children():
                self._update_refresh_button_bootstyle(widget, "info")

    def _update_refresh_button_bootstyle(self, widget, style):
        """Update the bootstyle of a refresh button if found"""
        # Check if this is a ttk Button with our custom style
        if isinstance(widget, ttk.Button) and hasattr(widget, 'configure'):
            try:
                # Try to get the current widget style
                current_style = widget.cget('style')
                if current_style == "Refresh.TButton":
                    widget.configure(bootstyle=style)
            except (tk.TclError, AttributeError):
                pass  # Ignore errors if widget doesn't support style attribute
        
        # Search children for ttk widgets
        for child in widget.winfo_children():
            self._update_refresh_button_bootstyle(child, style)

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
                future = self.io_executor.submit(get_possible_conditions, text)
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
                
                # Log that we're waiting for result
                logging.info(f"Starting referral generation for conditions: {focus}")
                
                # Use CPU executor for the AI processing which is CPU-intensive
                future = self.io_executor.submit(create_referral_with_openai, transcript, focus)
                
                # Get result with a longer timeout to prevent hanging (5 minutes instead of 2)
                result = future.result(timeout=300)
                
                # Log the successful completion
                logging.info(f"Successfully generated referral for conditions: {focus}")
                
                # Check if result contains error message
                if result.startswith("Error creating referral:"):
                    raise Exception(result)
                    
                # Schedule UI update on the main thread
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
        
        # Actually submit the task to be executed
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
        
        from validation import validate_audio_file
        
        # Validate audio file before processing
        is_valid, error = validate_audio_file(file_path)
        if not is_valid:
            from error_codes import show_error_dialog
            show_error_dialog(self, "SYS_FILE_ACCESS", error)
            return
        
        # Clear audio chunks and text widgets
        clear_all_content(self)
        
        self.status_manager.progress(f"Processing audio file: {os.path.basename(file_path)}...")
        self.progress_bar.pack(side=RIGHT, padx=10)
        self.progress_bar.start()

        def task() -> None:
            try:
                # Use I/O executor for file loading which is I/O-bound
                segment, transcript = self.audio_handler.load_audio_file(file_path)
                
                if segment and transcript:
                    # Store segment
                    self.audio_segments = [segment]
                    
                    # Handle transcript result
                    if transcript:
                        # Add to database
                        filename = os.path.basename(file_path)
                        try:
                            recording_id = self.db.add_recording(filename=filename, transcript=transcript)
                            self.current_recording_id = recording_id  # Track the current recording ID
                            logging.info(f"Added recording to database with ID: {recording_id}")
                        except Exception as db_err:
                            logging.error(f"Failed to add to database: {str(db_err)}", exc_info=True)
                        
                        # Always append to transcript_text widget and switch to transcript tab
                        self.after(0, lambda: [
                            self.append_text_to_widget(transcript, self.transcript_text),
                            self.notebook.select(0),  # Switch to transcript tab (index 0)
                            self.status_manager.success(f"Audio file processed and saved to database: {filename}"),
                            self.progress_bar.stop(),
                            self.progress_bar.pack_forget()
                        ])
                    else:
                        self.after(0, lambda: self.update_status("No transcript was produced", "warning"))
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
        if self.capitalize_next and text:
            text = text[0].upper() + text[1:]
            self.capitalize_next = False
        widget.insert(tk.END, (" " if current and current[-1] != "\n" else "") + text)
        widget.see(tk.END)
        
    def show_recordings_dialog(self) -> None:
        """Show a dialog with all recordings from the database"""
        dialog = create_toplevel_dialog(self, "Recordings Database", "1000x600")
        
        # Create a frame for the top controls
        controls_frame = ttk.Frame(dialog)
        controls_frame.pack(fill="x", padx=10, pady=5)
        
        # Add a search entry
        ttk.Label(controls_frame, text="Search:").pack(side="left", padx=(0, 5))
        search_var = tk.StringVar()
        search_entry = ttk.Entry(controls_frame, textvariable=search_var, width=30)
        search_entry.pack(side="left", padx=(0, 10))
        
        # Add a refresh button
        refresh_button = ttk.Button(controls_frame, text="🔄 Refresh", bootstyle="outline")
        refresh_button.pack(side="right", padx=5)
        
        # Create a frame for the Treeview
        tree_frame = ttk.Frame(dialog)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Create scrollbars
        y_scrollbar = ttk.Scrollbar(tree_frame)
        y_scrollbar.pack(side="right", fill="y")
        
        x_scrollbar = ttk.Scrollbar(tree_frame, orient="horizontal")
        x_scrollbar.pack(side="bottom", fill="x")
        
        # Create the Treeview
        columns = ("id", "filename", "timestamp", "has_transcript", "has_soap", "has_referral", "has_letter")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", 
                           yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        
        # Configure scrollbars
        y_scrollbar.config(command=tree.yview)
        x_scrollbar.config(command=tree.xview)
        
        # Define column headings and widths
        tree.heading("id", text="ID", anchor="center")
        tree.heading("filename", text="Filename", anchor="center")
        tree.heading("timestamp", text="Date/Time", anchor="center")
        tree.heading("has_transcript", text="Transcript", anchor="center")
        tree.heading("has_soap", text="SOAP Note", anchor="center")
        tree.heading("has_referral", text="Referral", anchor="center")
        tree.heading("has_letter", text="Letter", anchor="center")
        
        # Set column widths and alignment
        tree.column("id", width=60, minwidth=60, anchor="center")
        tree.column("filename", width=300, minwidth=200, anchor="center")
        tree.column("timestamp", width=180, minwidth=150, anchor="center")
        tree.column("has_transcript", width=100, minwidth=80, anchor="center")
        tree.column("has_soap", width=100, minwidth=80, anchor="center")
        tree.column("has_referral", width=100, minwidth=80, anchor="center")
        tree.column("has_letter", width=100, minwidth=80, anchor="center")
        
        tree.pack(fill="both", expand=True)
        
        # Create a frame for the buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        # Add buttons
        load_button = ttk.Button(button_frame, text="Load Selected", bootstyle="primary")
        load_button.pack(side="left", padx=5)
        
        delete_button = ttk.Button(button_frame, text="Delete Selected", bootstyle="danger")
        delete_button.pack(side="left", padx=5)
        
        export_button = ttk.Button(button_frame, text="Export Selected", bootstyle="success")
        export_button.pack(side="left", padx=5)
        
        close_button = ttk.Button(button_frame, text="Close", command=dialog.destroy)
        close_button.pack(side="right", padx=5)
        
        # Create a function to load records from the database
        def load_recordings(search_term=None):
            # Clear existing items
            for item in tree.get_children():
                tree.delete(item)
            
            try:
                # Get recordings from database
                if search_term:
                    recordings = self.db.search_recordings(search_term)
                else:
                    recordings = self.db.get_all_recordings()
                
                # Insert records into the treeview
                for rec in recordings:
                    # Check if each field has content
                    has_transcript = "✓" if rec["transcript"] else "-"
                    has_soap = "✓" if rec["soap_note"] else "-"
                    has_referral = "✓" if rec["referral"] else "-"
                    has_letter = "✓" if rec["letter"] else "-"
                    
                    # Format timestamp
                    timestamp = rec["timestamp"]
                    if timestamp:
                        # Try to convert string timestamp to datetime if needed
                        if isinstance(timestamp, str):
                            try:
                                dt_obj = dt.fromisoformat(timestamp.replace('Z', '+00:00'))
                                formatted_time = dt_obj.strftime("%Y-%m-%d %H:%M")
                            except ValueError:
                                formatted_time = timestamp
                        else:
                            formatted_time = timestamp.strftime("%Y-%m-%d %H:%M")
                    else:
                        formatted_time = "-"
                    
                    tree.insert("", tk.END, values=(rec["id"], rec["filename"], formatted_time, 
                                              has_transcript, has_soap, has_referral, has_letter))
            except Exception as e:
                from error_codes import show_error_dialog
                show_error_dialog(self, "SYS_FILE_ACCESS", f"Database error: {str(e)}")
        
        # Function to handle search
        def on_search(*_):
            search_term = search_var.get().strip()
            if search_term:
                load_recordings(search_term)
            else:
                load_recordings()
        
        # Bind search entry to search function
        search_var.trace_add("write", on_search)
        
        # Function to refresh the list
        def refresh_recordings():
            search_var.set("")  # Clear search
            load_recordings()
        
        # Bind refresh button
        refresh_button.config(command=refresh_recordings)
        
        # Function to load a selected recording
        def load_selected_recording():
            selected_items = tree.selection()
            if not selected_items:
                messagebox.showinfo("Selection", "Please select a recording to load")
                return
            
            # Get the first selected item's ID
            item = tree.item(selected_items[0])
            recording_id = item["values"][0]
            
            try:
                # Get the recording from the database
                recording = self.db.get_recording(recording_id)
                if recording:
                    # Clear current content
                    clear_all_content(self)
                    
                    # Set the current recording ID
                    self.current_recording_id = recording_id
                    
                    # Load transcript if available
                    if recording["transcript"]:
                        self.append_text_to_widget(recording["transcript"], self.transcript_text)
                        
                    # Load SOAP note if available
                    if recording["soap_note"]:
                        self.append_text_to_widget(recording["soap_note"], self.soap_text)
                    
                    # Load referral if available
                    if recording["referral"]:
                        self.append_text_to_widget(recording["referral"], self.referral_text)
                    
                    # Load letter if available
                    if recording["letter"]:
                        self.append_text_to_widget(recording["letter"], self.letter_text)
                    
                    # Close the dialog
                    dialog.destroy()
                    
                    # Show success message
                    self.status_manager.success(f"Loaded recording: {recording['filename']}")
                else:
                    messagebox.showerror("Error", f"Recording ID {recording_id} not found")
            except Exception as e:
                messagebox.showerror("Error", f"Error loading recording: {str(e)}")
        
        # Bind load button
        load_button.config(command=load_selected_recording)
        
        # Function to delete selected recordings
        def delete_selected_recordings():
            selected_items = tree.selection()
            if not selected_items:
                messagebox.showinfo("Selection", "Please select recordings to delete")
                return
            
            # Confirm deletion
            count = len(selected_items)
            if not messagebox.askyesno("Confirm Deletion", 
                                    f"Are you sure you want to delete {count} recording(s)?"):
                return
            
            # Delete each selected item
            success_count = 0
            for item_id in selected_items:
                item = tree.item(item_id)
                recording_id = item["values"][0]
                
                try:
                    if self.db.delete_recording(recording_id):
                        success_count += 1
                    else:
                        logging.warning(f"Failed to delete recording ID {recording_id}")
                except Exception as e:
                    logging.error(f"Error deleting recording ID {recording_id}: {str(e)}")
            
            # Refresh the list
            refresh_recordings()
            
            # Show success message
            if success_count > 0:
                messagebox.showinfo("Deletion Complete", 
                                f"Successfully deleted {success_count} recording(s)")
        
        # Bind delete button
        delete_button.config(command=delete_selected_recordings)
        
        # Function to export selected recordings - simplified version
        def export_selected_recordings():
            logging.info("Export Selected clicked - starting export process")
            
            # Get selected items
            selected_items = tree.selection()
            if not selected_items:
                logging.info("No items selected for export")
                messagebox.showinfo("Selection", "Please select recordings to export")
                return
            
            logging.info(f"Selected {len(selected_items)} items for export")
            
            # Create a list of recording IDs
            recording_ids = []
            try:
                for item_id in selected_items:
                    item = tree.item(item_id)
                    recording_id = item['values'][0]
                    recording_ids.append(recording_id)
            except Exception as e:
                logging.error(f"Error getting recording IDs: {str(e)}", exc_info=True)
                messagebox.showerror("Export Error", f"Error preparing export: {str(e)}")
                return
            
            # Get storage folder from settings, or use a default if not set
            from settings import SETTINGS
            
            # Check for storage_folder in settings
            storage_folder = SETTINGS.get("storage_folder", None) or SETTINGS.get("default_storage_folder", None)
            
            # If no storage folder is configured, create a default directory in the application folder
            if not storage_folder or not os.path.exists(storage_folder):
                export_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")
                logging.info(f"No valid storage folder found in settings, using default: {export_dir}")
            else:
                # Use the configured storage folder
                export_dir = storage_folder
                logging.info(f"Using configured storage folder from settings: {export_dir}")
            
            # Create the directory if it doesn't exist
            try:
                if not os.path.exists(export_dir):
                    os.makedirs(export_dir)
                    logging.info(f"Created export directory: {export_dir}")
                
                logging.info(f"Using export directory: {export_dir}")
            except Exception as e:
                logging.error(f"Error creating exports directory: {str(e)}", exc_info=True)
                messagebox.showerror("Export Error", f"Error creating exports directory: {str(e)}")
                return
            
            # Show a processing message
            processing_dialog = tk.Toplevel(dialog)
            processing_dialog.title("Exporting Records")
            processing_dialog.geometry("300x100")
            processing_dialog.transient(dialog)
            processing_dialog.resizable(False, False)
            processing_dialog.grab_set()
            
            # Center the dialog
            processing_dialog.geometry("+%d+%d" % (
                dialog.winfo_rootx() + (dialog.winfo_width() // 2) - 150,
                dialog.winfo_rooty() + (dialog.winfo_height() // 2) - 50))
            
            # Add a label
            progress_label = ttk.Label(processing_dialog, text="Exporting records...")
            progress_label.pack(pady=20)
            
            # Update the UI
            processing_dialog.update()
            
            # Perform the export in a background thread
            def export_task():
                # Get reference to the progress dialog label
                progress_label_ref = progress_label
                
                # Log the export directory selection
                logging.info(f"EXPORT: Starting export task for {len(recording_ids)} recordings to {export_dir}")
                logging.info(f"EXPORT: Thread ID: {threading.get_ident()}")
                
                success_count = 0
                error_messages = []
                total_count = len(recording_ids)
                
                # Update the progress dialog from the main thread
                def update_progress(message):
                    try:
                        self.after(0, lambda: progress_label_ref.config(text=message))
                    except Exception as ui_err:
                        logging.error(f"EXPORT: Progress update error: {str(ui_err)}")
                
                # Export each selected item
                for idx, recording_id in enumerate(recording_ids):
                    current_count = idx + 1
                    
                    # Update progress
                    progress_message = f"Exporting recording {current_count} of {total_count} (ID: {recording_id})"
                    logging.info(f"EXPORT: {progress_message}")
                    update_progress(progress_message)
                    
                    try:
                        # Create a separate database connection for the export thread
                        logging.info(f"EXPORT: Creating database connection for export")
                        from database import Database
                        db_thread = Database()
                        
                        # Get the recording
                        logging.info(f"EXPORT: Getting recording ID {recording_id}")
                        recording = db_thread.get_recording(recording_id)
                        
                        if recording:
                            # Create a more user-friendly filename
                            # Extract original recording date from the database timestamp
                            try:
                                # Parse the recording timestamp from the database
                                db_timestamp = recording["timestamp"]
                                if db_timestamp:
                                    # Try to parse the timestamp in ISO format
                                    try:
                                        # First try direct parsing
                                        recording_date = dt.fromisoformat(db_timestamp)
                                    except (ValueError, TypeError):
                                        # Fallback if the format is different
                                        try:
                                            # Try parsing with different formats
                                            formats_to_try = [
                                                "%Y-%m-%d %H:%M:%S",  # Standard format
                                                "%Y-%m-%d %H:%M:%S.%f",  # With microseconds
                                                "%Y-%m-%dT%H:%M:%S",  # ISO-like format
                                                "%Y-%m-%dT%H:%M:%S.%f"  # ISO with microseconds
                                            ]
                                            
                                            for fmt in formats_to_try:
                                                try:
                                                    recording_date = dt.strptime(db_timestamp, fmt)
                                                    break
                                                except (ValueError, TypeError):
                                                    continue
                                            else:
                                                # If loop completed without breaks, use current time
                                                recording_date = dt.now()
                                        except:
                                            recording_date = dt.now()
                                else:
                                    recording_date = dt.now()
                            except:
                                # If any error occurs, use current time
                                recording_date = dt.now()
                                
                            # Format the date in a readable way (YYYY-MM-DD)
                            date_str = recording_date.strftime("%Y-%m-%d")
                            
                            # Extract original filename and clean it to use as part of the new filename
                            original_filename = recording.get("filename", "").replace(".wav", "")
                            # If the original filename is empty or None, use a generic name
                            if not original_filename:
                                original_filename = f"recording_{recording_id}"
                            
                            # Remove any problematic characters from the filename
                            import re
                            cleaned_filename = re.sub(r'[^\w\s-]', '', original_filename)[:40]
                            cleaned_filename = cleaned_filename.strip().replace(' ', '_')
                            
                            # Create the base filename with date and cleaned original name
                            # Format: YYYY-MM-DD_OriginalName_ID
                            base_filename = f"{date_str}_{cleaned_filename}_{recording_id}"
                            
                            # Log each export operation
                            logging.info(f"Exporting recording ID {recording_id} to {export_dir}")
                            
                            # Export each component that exists
                            if recording["transcript"]:
                                transcript_file = os.path.join(export_dir, f"{base_filename}_transcript.txt")
                                try:
                                    logging.info(f"EXPORT: Writing transcript file at {transcript_file}")
                                    logging.debug(f"EXPORT: Transcript size: {len(recording['transcript'])} characters")
                                    
                                    with open(transcript_file, "w", encoding="utf-8") as f:
                                        f.write(recording["transcript"])
                                    
                                    logging.info(f"EXPORT: Successfully saved transcript to {transcript_file}")
                                except Exception as file_err:
                                    error_msg = f"Error saving transcript file: {str(file_err)}"
                                    logging.error(f"EXPORT: {error_msg}", exc_info=True)
                                    error_messages.append(f"Error saving transcript for recording ID {recording_id}: {str(file_err)}")
                            
                            if recording["soap_note"]:
                                soap_file = os.path.join(export_dir, f"{base_filename}_soap.txt")
                                try:
                                    logging.info(f"EXPORT: Writing SOAP note file at {soap_file}")
                                    logging.debug(f"EXPORT: SOAP note size: {len(recording['soap_note'])} characters")
                                    
                                    with open(soap_file, "w", encoding="utf-8") as f:
                                        f.write(recording["soap_note"])
                                    
                                    logging.info(f"EXPORT: Successfully saved SOAP note to {soap_file}")
                                except Exception as file_err:
                                    error_msg = f"Error saving SOAP note file: {str(file_err)}"
                                    logging.error(f"EXPORT: {error_msg}", exc_info=True)
                                    error_messages.append(f"Error saving SOAP note for recording ID {recording_id}: {str(file_err)}")
                            
                            if recording["referral"]:
                                referral_file = os.path.join(export_dir, f"{base_filename}_referral.txt")
                                try:
                                    logging.info(f"EXPORT: Writing referral file at {referral_file}")
                                    logging.debug(f"EXPORT: Referral size: {len(recording['referral'])} characters")
                                    
                                    with open(referral_file, "w", encoding="utf-8") as f:
                                        f.write(recording["referral"])
                                    
                                    logging.info(f"EXPORT: Successfully saved referral to {referral_file}")
                                except Exception as file_err:
                                    error_msg = f"Error saving referral file: {str(file_err)}"
                                    logging.error(f"EXPORT: {error_msg}", exc_info=True)
                                    error_messages.append(f"Error saving referral for recording ID {recording_id}: {str(file_err)}")
                            
                            if recording["letter"]:
                                letter_file = os.path.join(export_dir, f"{base_filename}_letter.txt")
                                try:
                                    logging.info(f"EXPORT: Writing letter file at {letter_file}")
                                    logging.debug(f"EXPORT: Letter size: {len(recording['letter'])} characters")
                                    
                                    with open(letter_file, "w", encoding="utf-8") as f:
                                        f.write(recording["letter"])
                                    
                                    logging.info(f"EXPORT: Successfully saved letter to {letter_file}")
                                except Exception as file_err:
                                    error_msg = f"Error saving letter file: {str(file_err)}"
                                    logging.error(f"EXPORT: {error_msg}", exc_info=True)
                                    error_messages.append(f"Error saving letter for recording ID {recording_id}: {str(file_err)}")
                            
                            success_count += 1
                    except Exception as e:
                        error_msg = f"Error exporting recording ID {recording_id}: {str(e)}"
                        logging.error(error_msg)
                        error_messages.append(error_msg)
                
                # Update UI with completion message
                update_progress("Export complete!")
                
                # Final report
                report_message = f"Export complete! Successfully exported {success_count} recording(s) to {export_dir}"
                logging.info(f"EXPORT: {report_message}")
                
                # Close the progress dialog and show completion message after a short delay
                self.after(500, lambda: complete_export(success_count, error_messages))
            
            # Function to show completion message and clean up
            def complete_export(success_count, error_messages):
                try:
                    # Close the progress dialog
                    if processing_dialog.winfo_exists():
                        processing_dialog.destroy()
                        
                    # Show success message
                    if success_count > 0:
                        # Open the exports folder automatically (as a convenience)
                        try:
                            if os.name == 'nt':  # Windows
                                os.startfile(export_dir)
                            else:  # macOS or Linux
                                import subprocess
                                subprocess.Popen(['open', export_dir] if sys.platform == 'darwin' else ['xdg-open', export_dir])
                        except Exception as folder_err:
                            logging.error(f"EXPORT: Error opening export folder: {str(folder_err)}", exc_info=True)
                        
                        # Show success message
                        messagebox.showinfo("Export Complete", 
                                        f"Successfully exported {success_count} recording(s) to:\n{export_dir}")
                    
                    # Show error message if there were any errors
                    if error_messages:
                        combined_errors = "\n".join(error_messages[:5])  # Show first 5 errors
                        if len(error_messages) > 5:
                            combined_errors += f"\n...and {len(error_messages) - 5} more errors."
                        messagebox.showwarning("Export Warning", 
                                            f"There were {len(error_messages)} errors during export:\n{combined_errors}")
                    elif success_count == 0:
                        messagebox.showwarning("Export Warning", "No recordings were exported. Check the logs for details.")
                except Exception as ui_error:
                    logging.error(f"EXPORT: Error showing completion message: {str(ui_error)}", exc_info=True)
                    try:
                        messagebox.showerror("Export Error", f"Error completing export: {str(ui_error)}")
                    except:
                        pass
            
            # Start the export task in a background thread
            try:
                logging.info("EXPORT: Creating export thread")
                export_thread = threading.Thread(target=export_task)
                export_thread.daemon = True  # Allow app to exit if thread is still running
                
                logging.info("EXPORT: Starting export thread")
                export_thread.start()
                logging.info("EXPORT: Export thread started successfully")
            except Exception as e:
                logging.error(f"EXPORT: Error starting export thread: {str(e)}", exc_info=True)
                messagebox.showerror("Export Error", f"Error starting export: {str(e)}")
                if processing_dialog.winfo_exists():
                    processing_dialog.destroy()
        
        # Bind export button
        export_button.config(command=export_selected_recordings)
        
        # Double-click on item to load it
        tree.bind("<Double-1>", lambda _: load_selected_recording())
        
        # Initial load of recordings
        load_recordings()
        
        # Set focus to search entry
        search_entry.focus_set()

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
        from settings import SETTINGS, save_settings
        SETTINGS["window_width"] = self.last_width
        SETTINGS["window_height"] = self.last_height
        save_settings(SETTINGS)
        # No status message needed for this automatic action
        self.resize_timer = None  # Clear the timer reference
    
    def play_recording_sound(self, start=True):
        """Play a sound to indicate recording start/stop."""
        # Sound disabled - just log the event
        logging.debug(f"Recording {'started' if start else 'stopped'}")

if __name__ == "__main__":
    main()
