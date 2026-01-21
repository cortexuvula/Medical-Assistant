"""
App Initializer Module

Handles the complex initialization process of the Medical Dictation App including
executors setup, window configuration, API key validation, UI creation, and
manager initialization.
"""

import os
import multiprocessing

from utils.structured_logging import get_logger

logger = get_logger(__name__)
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import tkinter as tk
from tkinter import messagebox
from tkinter.constants import DISABLED
import ttkbootstrap as ttk

from settings.settings import SETTINGS
from ui.dialogs.dialogs import show_api_keys_dialog
from audio.audio import AudioHandler
from processing.text_processor import TextProcessor
from ui.workflow_ui import WorkflowUI
from ui.chat_ui import ChatUI
from ai.chat_processor import ChatProcessor
from ai.rag_processor import RagProcessor
from managers.rag_document_manager import get_rag_document_manager
from ui.status_manager import StatusManager
from audio.recording_manager import RecordingManager
from audio.audio_state_manager import AudioStateManager
from ai.ai_processor import AIProcessor
from managers.file_manager import FileManager
from database.db_manager import DatabaseManager
from ui.dialogs.recordings_dialog_manager import RecordingsDialogManager
from ui.dialogs.audio_dialogs import AudioDialogManager
from ui.dialogs.folder_dialogs import FolderDialogManager
from ui.theme_manager import ThemeManager
from processing.document_generators import DocumentGenerators
from ai.soap_processor import SOAPProcessor
from audio.soap_audio_processor import SOAPAudioProcessor
from processing.file_processor import FileProcessor
from database.database import Database
from processing.processing_queue import ProcessingQueue
from managers.notification_manager import NotificationManager
from audio.periodic_analysis import PeriodicAnalyzer
from ui.scaling_utils import ui_scaler
from core.ui_state_manager import UIStateManager
from core.controllers.config_controller import ConfigController
from core.controllers.window_controller import WindowController
from core.controllers.persistence_controller import PersistenceController
from core.controllers.processing_controller import ProcessingController
from core.controllers.recording_controller import RecordingController
from utils.security import get_security_manager


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
        self._finalize_ui()  # Phase 2: UI setup that requires controllers
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
        
        # Initialize UI scaler with the root window
        ui_scaler.initialize(self.app)
        
        # Check if we have saved window dimensions in settings
        saved_width = SETTINGS.get("window_width", 0)
        saved_height = SETTINGS.get("window_height", 0)
        
        if saved_width > 0 and saved_height > 0:
            # Use saved dimensions if they exist and are valid
            # But ensure they fit on current screen
            screen_width = ui_scaler.screen_width or self.app.winfo_screenwidth()
            screen_height = ui_scaler.screen_height or self.app.winfo_screenheight()
            
            # Clamp saved dimensions to current screen size
            window_width = min(saved_width, int(screen_width * 0.95))
            window_height = min(saved_height, int(screen_height * 0.95))
        else:
            # Calculate responsive window size based on screen category
            if ui_scaler.screen_category == ui_scaler.ULTRAWIDE:
                # For ultrawide, use less width percentage
                window_width, window_height = ui_scaler.get_window_size(0.6, 0.85)
            elif ui_scaler.screen_category == ui_scaler.SMALL:
                # For small screens, use more of available space
                window_width, window_height = ui_scaler.get_window_size(0.9, 0.9)
            else:
                # Standard sizing
                window_width, window_height = ui_scaler.get_window_size(0.8, 0.85)
        
        # Apply the calculated window size
        self.app.geometry(f"{window_width}x{window_height}")
        
        # Set responsive minimum size based on screen dimensions
        min_width, min_height = ui_scaler.get_minimum_window_size()
        self.app.minsize(min_width, min_height)
        
        # Center the window on the screen
        self.app.update_idletasks()  # Ensure window dimensions are calculated
        screen_width = ui_scaler.screen_width or self.app.winfo_screenwidth()
        screen_height = ui_scaler.screen_height or self.app.winfo_screenheight()
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)
        self.app.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Add binding for window resize to save dimensions
        self.app.bind("<Configure>", self.app.on_window_configure)
        
        # Variables to optimize resize event handling
        self.app.resize_timer = None
        self.app.last_width = window_width
        self.app.last_height = window_height
        
        # Store scaler reference in app for access by other components
        self.app.ui_scaler = ui_scaler
        
    def _setup_api_keys(self):
        """Initialize and validate API keys."""
        # Get security manager for API key access
        security_manager = get_security_manager()

        # Initialize API keys from environment/secure storage
        self.app.deepgram_api_key = os.getenv("DEEPGRAM_API_KEY", "")
        self.app.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self.app.groq_api_key = os.getenv("GROQ_API_KEY", "")
        self.app.recognition_language = os.getenv("RECOGNITION_LANGUAGE", "en-US")

        # Check for necessary API keys using security manager
        openai_key = security_manager.get_api_key("openai")
        anthropic_key = security_manager.get_api_key("anthropic")
        gemini_key = security_manager.get_api_key("gemini")
        elevenlabs_key = security_manager.get_api_key("elevenlabs")
        deepgram_key = security_manager.get_api_key("deepgram")
        groq_key = security_manager.get_api_key("groq")
        ollama_url = os.getenv("OLLAMA_API_URL")

        # Check if we have at least one LLM and one STT provider
        has_llm = bool(openai_key or anthropic_key or gemini_key or ollama_url)
        has_stt = bool(elevenlabs_key or deepgram_key or groq_key)

        if not has_llm or not has_stt:
            messagebox.showinfo(
                "API Keys Required",
                "Welcome to Medical Assistant!\n\n" +
                "To use this application, you need:\n" +
                "• At least one LLM provider (OpenAI, Anthropic, Gemini, or Ollama)\n" +
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
            logger.warning("Audio handler doesn't support fallback callback - update your audio.py file")
            
        # Initialize text processor
        self.app.text_processor = TextProcessor()
        
    def _initialize_variables(self):
        """Initialize application state variables."""
        self.app.capitalize_next = False
        self.app.soap_recording = False
        # Audio-related variables
        self.app.audio_segments = []  # For loaded audio files
        self.app.text_chunks = []  # For scratch-that functionality
        self.app.soap_combine_threshold = 100 # Used by AudioStateManager
        self.app.soap_stop_listening_function = None
        self.app.listening = False  # Initialize listening flag for recording state
        self.app.current_recording_id = None  # Track the ID of the currently loaded recording
        
        # Initialize auto-save state
        self.app.has_available_autosave = False
        self.app.last_autosave_timestamp = None
        
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
        """Create the user interface components (Phase 1 - widgets only).

        Note: This creates widgets but does NOT call initialization methods
        that require controllers. Those are called in _finalize_ui().
        """
        # Initialize window controller early (needed by create_widgets for navigation)
        self.app.window_controller = WindowController(self.app)
        # Backward-compatible aliases
        self.app.navigation_controller = self.app.window_controller
        self.app.window_state_controller = self.app.window_controller
        self.app.logs_viewer_controller = self.app.window_controller

        # Create workflow-oriented UI (only UI mode supported)
        self.app.ui = WorkflowUI(self.app)
        self.app.create_menu()
        self.app.create_widgets()
        # Note: bind_shortcuts() moved to _finalize_ui() - needs KeyboardShortcutsController

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

    def _finalize_ui(self):
        """Complete UI setup after controllers are initialized (Phase 2).

        This method is called after _initialize_managers() so that
        these methods can safely delegate to their controllers.
        """
        # Initialize provider selections (delegates to ProviderConfigController)
        self.app._initialize_provider_selections()

        # Initialize autosave (delegates to AutoSaveController)
        self.app._initialize_autosave()

        # Bind keyboard shortcuts (delegates to KeyboardShortcutsController)
        self.app.bind_shortcuts()
        
    def _initialize_managers(self):
        """Initialize all the manager classes."""
        # Initialize audio state manager first
        self.app.audio_state_manager = AudioStateManager(
            combine_threshold=self.app.soap_combine_threshold
        )

        # Initialize recording manager with audio state manager
        self.app.recording_manager = RecordingManager(
            self.app.audio_handler,
            self.app.status_manager,
            self.app.audio_state_manager
        )
        self.app.recording_manager.on_text_recognized = self.app.handle_recognized_text
        self.app.recording_manager.on_transcription_fallback = self.app.on_transcription_fallback

        # Initialize UI state manager (before recording controller which uses it)
        self.app.ui_state_manager = UIStateManager(self.app)

        # Initialize recording controller (consolidated recording + periodic analysis + recovery)
        self.app.recording_controller = RecordingController(self.app)
        # Backward-compatible aliases
        self.app.periodic_analysis_controller = self.app.recording_controller
        self.app.recording_recovery_controller = self.app.recording_controller

        # Initialize processing controller (consolidated queue + text + document export)
        self.app.processing_controller = ProcessingController(self.app)
        # Backward-compatible aliases
        self.app.text_processing_controller = self.app.processing_controller
        self.app.document_export_controller = self.app.processing_controller
        self.app.queue_processing_controller = self.app.processing_controller

        # Initialize config controller (consolidated provider + microphone)
        self.app.config_controller = ConfigController(self.app)
        # Backward-compatible aliases
        self.app.provider_config_controller = self.app.config_controller
        self.app.microphone_controller = self.app.config_controller

        # Initialize persistence controller (consolidated autosave + keyboard shortcuts)
        self.app.persistence_controller = PersistenceController(self.app)
        # Backward-compatible aliases
        self.app.autosave_controller = self.app.persistence_controller
        self.app.keyboard_shortcuts_controller = self.app.persistence_controller

        # Note: window_controller (and aliases: navigation_controller, window_state_controller,
        # logs_viewer_controller) is initialized in _create_ui() before create_widgets()
        # Note: queue_processing_controller is an alias for processing_controller

        self.app.ai_processor = AIProcessor()  # Uses security manager internally
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
        self.app.rag_processor = RagProcessor(self.app)

        # Initialize RAG document manager (lazy initialization)
        self._initialize_rag_system()

        # Initialize processing queue
        self.app.processing_queue = ProcessingQueue(self.app)
        self.app.processing_queue.status_callback = self._on_queue_status_update
        self.app.processing_queue.completion_callback = self._on_queue_completion
        self.app.processing_queue.error_callback = self._on_queue_error

        # Initialize notification manager
        self.app.notification_manager = NotificationManager(self.app)

        # Initialize periodic analyzer
        self.app.periodic_analyzer = None  # Will be created when needed

    def _initialize_rag_system(self):
        """Initialize the RAG document management system.

        This sets up the RAG document manager and logs system status.
        The actual connections (Neon, embeddings) are lazily initialized
        when first needed to avoid slowing down app startup.
        """
        try:
            # Get the RAG document manager singleton
            self.app.rag_document_manager = get_rag_document_manager()

            # Check RAG mode (local vs N8N webhook)
            rag_mode = self.app.rag_processor.get_rag_mode()
            if rag_mode == "local":
                logger.info("RAG system initialized in local mode (Neon pgvector)")
                # Get document count for status
                try:
                    doc_count = self.app.rag_document_manager.get_document_count()
                    logger.info(f"RAG document library contains {doc_count} documents")
                except Exception as e:
                    logger.debug(f"Could not get document count: {e}")
            elif rag_mode == "n8n":
                logger.info("RAG system initialized in N8N webhook mode")
            else:
                logger.info("RAG system not configured (no Neon or N8N connection)")

        except Exception as e:
            logger.warning(f"RAG system initialization warning: {e}")
            self.app.rag_document_manager = None

    def _setup_api_dependent_features(self):
        """Configure features that depend on API availability."""
        # Check if any LLM provider is configured
        security_manager = get_security_manager()
        has_any_llm = any([
            security_manager.get_api_key("openai"),
            security_manager.get_api_key("anthropic"),
            security_manager.get_api_key("gemini"),
            os.getenv("OLLAMA_API_URL")
        ])
        if not has_any_llm:
            self.app.buttons["refine"].config(state=DISABLED)
            self.app.buttons["improve"].config(state=DISABLED)
            self.app.status_manager.warning("Warning: No LLM API keys configured. AI features disabled.")
            
    def _finalize_setup(self):
        """Complete the application setup."""
        self.app.protocol("WM_DELETE_WINDOW", self.app.on_closing)

        # Add a list to track all scheduled status updates
        self.app.status_timers = []
        self.app.status_timer = None

        # Check for incomplete recording after UI is fully ready
        self.app.after(1000, self.app.recording_recovery_controller.check_for_incomplete_recording)
    
    def _on_queue_status_update(self, task_id: str, status: str, queue_size: int):
        """Handle queue status updates.

        Note: This callback is called from background threads, so all UI updates
        must be scheduled on the main thread using app.after().
        """
        logger.debug(f"Queue status update: task={task_id}, status={status}, size={queue_size}")

        # Get stats synchronously (thread-safe operation)
        stats = self.app.processing_queue.get_status()

        # Schedule UI update on main thread (Tkinter is not thread-safe)
        self.app.after(0, lambda: self.app.status_manager.update_queue_status(
            active=stats["active_tasks"],
            completed=stats["completed_tasks"],
            failed=stats["failed_tasks"]
        ))
    
    def _on_queue_completion(self, task_id: str, recording_data: dict, result: dict):
        """Handle queue processing completion."""
        logger.info(f"Processing completed for task {task_id}")
        
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
        
        # Update queue status - MUST be scheduled on main thread (Tkinter not thread-safe)
        self.app.after(0, self.app.status_manager.increment_queue_completed)

    def _on_queue_error(self, task_id: str, recording_data: dict, error_msg: str):
        """Handle queue processing errors."""
        logger.error(f"Processing failed for task {task_id}: {error_msg}")

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

        # Update queue status - MUST be scheduled on main thread (Tkinter not thread-safe)
        self.app.after(0, self.app.status_manager.increment_queue_failed)
    
    def _update_ui_with_results(self, recording_id: int, transcript: str, soap_note: str, patient_name: str):
        """Update UI tabs with processed results from background queue.

        This method checks for user modifications before overwriting content,
        protecting user edits from being lost to background updates.
        """
        try:
            # Check if UI should be updated based on settings
            if not SETTINGS.get('auto_update_ui_on_completion', True):
                return

            # Only update if the UI is not currently busy with another recording
            if hasattr(self.app, 'soap_recording') and self.app.soap_recording:
                logger.info("Skipping UI update - currently recording")
                return

            # Use the app's protection mechanism to check if updates are safe
            can_update_transcript = self.app.can_update_tab_from_background('transcript', recording_id)
            can_update_soap = self.app.can_update_tab_from_background('soap', recording_id)

            # Track if we skipped any updates due to user modifications
            skipped_updates = []

            # Update transcript tab if safe
            if transcript:
                if can_update_transcript:
                    self.app.transcript_text.delete("1.0", "end")
                    self.app.transcript_text.insert("1.0", transcript)
                    self.app.transcript_text.edit_separator()  # Add to undo history
                    self.app.reset_content_modified('transcript')  # Reset modified flag
                    logger.info(f"Updated transcript tab with results from recording {recording_id}")
                else:
                    skipped_updates.append('transcript')
                    logger.info(f"Skipped transcript update - user has modified content")

            # Update SOAP tab if safe
            if soap_note:
                if can_update_soap:
                    self.app.soap_text.delete("1.0", "end")
                    self.app.soap_text.insert("1.0", soap_note)
                    self.app.soap_text.edit_separator()  # Add to undo history
                    self.app.reset_content_modified('soap')  # Reset modified flag
                    logger.info(f"Updated SOAP tab with results from recording {recording_id}")

                    # Switch to SOAP tab to show the results and give focus
                    self.app.notebook.select(1)
                    self.app.soap_text.focus_set()

                    # Auto-run analyses to the side panels
                    logger.info(f"Scheduling auto-analysis for queued SOAP note ({len(soap_note)} chars)")
                    if hasattr(self.app, 'document_generators'):
                        self.app.after(100, lambda sn=soap_note: self.app.document_generators._run_medication_to_panel(sn))
                        self.app.after(200, lambda sn=soap_note: self.app.document_generators._run_diagnostic_to_panel(sn))
                else:
                    skipped_updates.append('soap')
                    logger.info(f"Skipped SOAP update - user has modified content")

            # Update current recording ID
            self.app._current_recording_id = recording_id

            # Update status with info about skipped updates
            if skipped_updates:
                self.app.status_manager.info(
                    f"Results for {patient_name} ready (view in Recordings tab - "
                    f"skipped {', '.join(skipped_updates)} to preserve your edits)"
                )
            else:
                self.app.status_manager.info(f"Loaded results for {patient_name}")

        except Exception as e:
            logger.error(f"Error updating UI with results: {str(e)}", exc_info=True)