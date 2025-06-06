"""
App Initializer Module

Handles the complex initialization process of the Medical Dictation App including
executors setup, window configuration, API key validation, UI creation, and
manager initialization.
"""

import os
import logging
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import tkinter as tk
from tkinter import messagebox
from tkinter.constants import DISABLED
import ttkbootstrap as ttk
import openai

from settings import SETTINGS
from dialogs import show_api_keys_dialog
from audio import AudioHandler
from text_processor import TextProcessor
from workflow_ui import WorkflowUI
from chat_ui import ChatUI
from chat_processor import ChatProcessor
from status_manager import StatusManager
from recording_manager import RecordingManager
from ai_processor import AIProcessor
from file_manager import FileManager
from db_manager import DatabaseManager
from recordings_dialog_manager import RecordingsDialogManager
from audio_dialogs import AudioDialogManager
from folder_dialogs import FolderDialogManager
from theme_manager import ThemeManager
from document_generators import DocumentGenerators
from soap_processor import SOAPProcessor
from soap_audio_processor import SOAPAudioProcessor
from file_processor import FileProcessor
from database import Database
from processing_queue import ProcessingQueue
from notification_manager import NotificationManager


class AppInitializer:
    """Manages the application initialization process."""
    
    def __init__(self, app_instance):
        """Initialize the app initializer.
        
        Args:
            app_instance: The main application instance to initialize
        """
        self.app = app_instance
        
    def initialize_application(self):
        """Initialize the complete application."""
        self._setup_executors()
        self._configure_window()
        self._setup_api_keys()
        self._initialize_audio_handler()
        self._initialize_variables()
        self._initialize_database()
        self._create_ui()
        self._initialize_managers()
        self._setup_api_dependent_features()
        self._finalize_setup()
        
    def _setup_executors(self):
        """Set up thread and process executors for concurrent operations."""
        # Determine number of CPU cores available for optimal threading configuration
        cpu_count = multiprocessing.cpu_count()
        
        # Initialize ThreadPoolExecutor for I/O-bound tasks (network calls, file operations)
        # Use more threads for I/O operations since they spend most of their time waiting
        self.app.io_executor = ThreadPoolExecutor(max_workers=min(32, cpu_count * 4))
        
        # Initialize ProcessPoolExecutor for CPU-bound tasks (text processing, analysis)
        # Use number of physical cores for CPU-intensive tasks to avoid context switching overhead
        self.app.cpu_executor = ProcessPoolExecutor(max_workers=max(2, cpu_count - 1))
        
        # Maintain the original executor for backwards compatibility
        self.app.executor = self.app.io_executor
        
    def _configure_window(self):
        """Configure window appearance, size, and positioning."""
        # Get theme from settings or use default
        self.app.current_theme = SETTINGS.get("theme", "flatly")
        
        # Initialize the ttk.Window with theme
        ttk.Window.__init__(self.app, themename=self.app.current_theme)
        self.app.title("Medical Assistant")
        
        # Get screen dimensions and calculate appropriate window size
        screen_width = self.app.winfo_screenwidth()
        screen_height = self.app.winfo_screenheight()
        
        # Check if we have saved window dimensions in settings
        saved_width = SETTINGS.get("window_width", 0)
        saved_height = SETTINGS.get("window_height", 0)
        
        if saved_width > 0 and saved_height > 0:
            # Use saved dimensions if they exist and are valid
            window_width = saved_width
            window_height = saved_height
        else:
            # Calculate responsive window size (80% of screen size, but not larger than 1700x1100)
            # Increased default height to better accommodate workflow UI and recordings panel
            window_width = min(int(screen_width * 0.8), 1700)
            window_height = min(int(screen_height * 0.85), 1100)
        
        # Apply the calculated window size
        self.app.geometry(f"{window_width}x{window_height}")
        
        # Set a reasonable minimum size that ensures all UI elements are visible
        # Increased minimum height to accommodate workflow UI recording controls and recordings panel
        self.app.minsize(1200, 950)
        
        # Center the window on the screen
        self.app.update_idletasks()  # Ensure window dimensions are calculated
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)
        self.app.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Add binding for window resize to save dimensions
        self.app.bind("<Configure>", self.app.on_window_configure)
        
        # Variables to optimize resize event handling
        self.app.resize_timer = None
        self.app.last_width = window_width
        self.app.last_height = window_height
        
    def _setup_api_keys(self):
        """Initialize and validate API keys."""
        # Initialize API keys and handlers
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.app.deepgram_api_key = os.getenv("DEEPGRAM_API_KEY", "")
        self.app.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self.app.groq_api_key = os.getenv("GROQ_API_KEY", "")
        self.app.recognition_language = os.getenv("RECOGNITION_LANGUAGE", "en-US")
        
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
            result = show_api_keys_dialog(self.app)
            if result:
                # Update the keys after dialog closes
                self.app.deepgram_api_key = os.getenv("DEEPGRAM_API_KEY", "")
                self.app.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "")
                self.app.groq_api_key = os.getenv("GROQ_API_KEY", "")
                openai.api_key = os.getenv("OPENAI_API_KEY")
                
    def _initialize_audio_handler(self):
        """Initialize the audio handler and text processor."""
        # Initialize audio handler
        self.app.audio_handler = AudioHandler(
            elevenlabs_api_key=self.app.elevenlabs_api_key,
            deepgram_api_key=self.app.deepgram_api_key,
            groq_api_key=self.app.groq_api_key,
            recognition_language=self.app.recognition_language
        )
        
        # Register fallback notification callback with error handling
        try:
            self.app.audio_handler.set_fallback_callback(self.app.on_transcription_fallback)
        except AttributeError:
            logging.warning("Audio handler doesn't support fallback callback - update your audio.py file")
            
        # Initialize text processor
        self.app.text_processor = TextProcessor()
        
    def _initialize_variables(self):
        """Initialize application state variables."""
        self.app.appended_chunks = []
        self.app.capitalize_next = False
        self.app.audio_segments = []
        self.app.soap_recording = False
        # self.app.soap_audio_segments = [] # Replaced by pending_soap_segments and combined_soap_chunks
        self.app.pending_soap_segments = [] # Segments collected since last combination
        self.app.combined_soap_chunks = [] # List of larger, combined audio chunks
        self.app.soap_combine_threshold = 100 # Combine every N pending segments
        self.app.soap_stop_listening_function = None
        self.app.listening = False  # Initialize listening flag for recording state
        self.app.current_recording_id = None  # Track the ID of the currently loaded recording
        
        # Quick continue mode variable for menu checkbox
        self.app.quick_continue_var = tk.BooleanVar()
        self.app.quick_continue_var.set(SETTINGS.get("quick_continue_mode", True))
        
    def _initialize_database(self):
        """Initialize database instance."""
        self.app.db = Database()
        self.app.db.create_tables()
        # Ensure queue tables exist
        self.app.db.create_queue_tables()
        
    def _create_ui(self):
        """Create the user interface components."""
        # Create workflow-oriented UI (only UI mode supported)
        self.app.ui = WorkflowUI(self.app)
        self.app.create_menu()
        self.app.create_widgets()
        self.app.bind_shortcuts()

        # Initialize status manager
        self.app.status_manager = StatusManager(
            self.app,
            self.app.status_icon_label,
            self.app.status_label,
            self.app.provider_indicator,
            self.app.progress_bar
        )
        
        # Set queue status label if available
        queue_label = self.app.ui.components.get('queue_status_label')
        if queue_label:
            self.app.status_manager.set_queue_status_label(queue_label)
        
    def _initialize_managers(self):
        """Initialize all the manager classes."""
        # Initialize our new managers
        self.app.recording_manager = RecordingManager(self.app.audio_handler, self.app.status_manager)
        self.app.recording_manager.on_text_recognized = self.app.handle_recognized_text
        self.app.recording_manager.on_transcription_fallback = self.app.on_transcription_fallback
        
        self.app.ai_processor = AIProcessor(openai.api_key)
        self.app.file_manager = FileManager(SETTINGS.get("default_folder", ""))
        self.app.db_manager = DatabaseManager()
        self.app.recordings_dialog_manager = RecordingsDialogManager(self.app)
        self.app.audio_dialog_manager = AudioDialogManager(self.app)
        self.app.folder_dialog_manager = FolderDialogManager(self.app)
        self.app.theme_manager = ThemeManager(self.app)
        self.app.document_generators = DocumentGenerators(self.app)
        self.app.soap_processor = SOAPProcessor(self.app)
        self.app.soap_audio_processor = SOAPAudioProcessor(self.app)
        self.app.file_processor = FileProcessor(self.app)
        self.app.chat_processor = ChatProcessor(self.app)
        
        # Initialize processing queue
        self.app.processing_queue = ProcessingQueue(self.app)
        self.app.processing_queue.status_callback = self._on_queue_status_update
        self.app.processing_queue.completion_callback = self._on_queue_completion
        self.app.processing_queue.error_callback = self._on_queue_error
        
        # Initialize notification manager
        self.app.notification_manager = NotificationManager(self.app)
        
    def _setup_api_dependent_features(self):
        """Configure features that depend on API availability."""
        if not openai.api_key:
            self.app.buttons["refine"].config(state=DISABLED)
            self.app.buttons["improve"].config(state=DISABLED)
            self.app.status_manager.warning("Warning: OpenAI API key not provided. AI features disabled.")
            
    def _finalize_setup(self):
        """Complete the application setup."""
        self.app.protocol("WM_DELETE_WINDOW", self.app.on_closing)
        
        # Add a list to track all scheduled status updates
        self.app.status_timers = []
        self.app.status_timer = None
    
    def _on_queue_status_update(self, task_id: str, status: str, queue_size: int):
        """Handle queue status updates."""
        logging.debug(f"Queue status update: task={task_id}, status={status}, size={queue_size}")
        
        # Update queue status display
        stats = self.app.processing_queue.get_status()
        self.app.status_manager.update_queue_status(
            active=stats["active_tasks"],
            completed=stats["completed_tasks"],
            failed=stats["failed_tasks"]
        )
    
    def _on_queue_completion(self, task_id: str, recording_data: dict, result: dict):
        """Handle queue processing completion."""
        logging.info(f"Processing completed for task {task_id}")
        
        # Update database with results
        if result.get('success'):
            self.app.db.update_recording(
                recording_data['recording_id'],
                transcript=result.get('transcript', ''),
                soap_note=result.get('soap_note', ''),
                audio_path=result.get('audio_path', ''),
                processing_status='completed',
                processing_completed_at=result.get('completed_at')
            )
            
            # Update UI with the processed results
            transcript = result.get('transcript', '')
            soap_note = result.get('soap_note', '')
            
            # Schedule UI update on main thread
            self.app.after(0, lambda: self._update_ui_with_results(
                recording_data['recording_id'],
                transcript,
                soap_note,
                recording_data.get('patient_name', 'Unknown')
            ))
            
            # Show notification
            self.app.notification_manager.show_completion(
                patient_name=recording_data.get('patient_name', 'Unknown'),
                recording_id=recording_data['recording_id'],
                task_id=task_id,
                processing_time=result.get('processing_time', 0)
            )
        
        # Update queue status
        self.app.status_manager.increment_queue_completed()
    
    def _on_queue_error(self, task_id: str, recording_data: dict, error_msg: str):
        """Handle queue processing errors."""
        logging.error(f"Processing failed for task {task_id}: {error_msg}")
        
        # Update database
        self.app.db.update_recording(
            recording_data['recording_id'],
            processing_status='failed',
            error_message=error_msg
        )
        
        # Show notification
        self.app.notification_manager.show_error(
            patient_name=recording_data.get('patient_name', 'Unknown'),
            error_message=error_msg,
            recording_id=recording_data['recording_id'],
            task_id=task_id
        )
        
        # Update queue status
        self.app.status_manager.increment_queue_failed()
    
    def _update_ui_with_results(self, recording_id: int, transcript: str, soap_note: str, patient_name: str):
        """Update UI tabs with processed results from background queue."""
        try:
            # Check if UI should be updated based on settings
            if not SETTINGS.get('auto_update_ui_on_completion', True):
                return
                
            # Only update if the UI is not currently busy with another recording
            if hasattr(self.app, 'soap_recording') and self.app.soap_recording:
                logging.info("Skipping UI update - currently recording")
                return
            
            # Check if tabs are empty or user wants to see the latest results
            transcript_empty = not self.app.transcript_text.get("1.0", "end-1c").strip()
            soap_empty = not self.app.soap_text.get("1.0", "end-1c").strip()
            
            # Update transcript tab if empty
            if transcript_empty and transcript:
                self.app.transcript_text.delete("1.0", "end")
                self.app.transcript_text.insert("1.0", transcript)
                self.app.transcript_text.edit_separator()  # Add to undo history
                logging.info(f"Updated transcript tab with results from recording {recording_id}")
            
            # Update SOAP tab if empty
            if soap_empty and soap_note:
                self.app.soap_text.delete("1.0", "end")
                self.app.soap_text.insert("1.0", soap_note)
                self.app.soap_text.edit_separator()  # Add to undo history
                logging.info(f"Updated SOAP tab with results from recording {recording_id}")
                
                # Switch to SOAP tab to show the results
                self.app.notebook.select(1)
            
            # Update current recording ID
            self.app.current_recording_id = recording_id
            
            # Update status
            self.app.status_manager.info(f"Loaded results for {patient_name}")
            
        except Exception as e:
            logging.error(f"Error updating UI with results: {str(e)}", exc_info=True)