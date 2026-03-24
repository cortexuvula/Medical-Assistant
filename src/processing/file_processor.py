"""
File Processor Module

Handles file loading, validation, audio processing, and database storage
with proper concurrency handling for the Medical Dictation App.
"""

import os
from tkinter import filedialog
from tkinter.constants import RIGHT
from utils.structured_logging import get_logger

from utils.validation import validate_audio_file

logger = get_logger(__name__)
from utils.error_codes import show_error_dialog
from utils.cleanup_utils import clear_all_content


class FileProcessor:
    """Manages file processing functionality."""
    
    def __init__(self, parent_app):
        """Initialize the file processor.
        
        Args:
            parent_app: The main application instance
        """
        self.app = parent_app
        
    def load_audio_file(self) -> None:
        """Load and transcribe audio from a file using AudioHandler with improved concurrency."""
        file_path = filedialog.askopenfilename(
            initialdir=os.path.expanduser("~"),
            title="Select Audio File",
            filetypes=[
                ("Audio Files", "*.wav *.mp3 *.ogg *.flac *.m4a"),
                ("All Files", "*.*")
            ]
        )
        if not file_path:
            return
        
        # Validate audio file before processing
        is_valid, error = validate_audio_file(file_path)
        if not is_valid:
            show_error_dialog(self.app, "SYS_FILE_ACCESS", error)
            return
        
        # Clear audio chunks and text widgets
        clear_all_content(self.app)
        
        self.app.status_manager.progress(f"Processing audio file: {os.path.basename(file_path)}...")
        self.app.progress_bar.pack(side=RIGHT, padx=10)
        self.app.progress_bar.start()

        def task() -> None:
            try:
                # Use metadata-aware loading to capture emotion data from Modulate
                segment, transcript, metadata = self.app.audio_handler.load_audio_file_with_metadata(file_path)

                if segment and transcript:
                    # Store segment
                    self.app.audio_segments = [segment]

                    # Extract emotion data if available (Modulate provider)
                    emotion_data = None
                    if metadata and metadata.get("emotion_data"):
                        emotion_data = metadata["emotion_data"]
                        logger.info(f"Captured emotion data from file transcription")

                    # Handle transcript result
                    if transcript:
                        # Add to database
                        filename = os.path.basename(file_path)
                        try:
                            recording_id = self.app.db.add_recording(filename=filename, transcript=transcript)
                            self.app.current_recording_id = recording_id  # Track the current recording ID
                            logger.info(f"Added recording to database with ID: {recording_id}")

                            # Save emotion data to recording metadata
                            if emotion_data and recording_id:
                                import json
                                self.app.db.update_recording(recording_id, metadata=json.dumps({"emotion_data": emotion_data}))
                                logger.info(f"Saved emotion data to recording {recording_id}")
                        except Exception as db_err:
                            logger.error(f"Failed to add to database: {str(db_err)}", exc_info=True)

                        # Always append to transcript_text widget and switch to transcript tab
                        def _on_success(fn=filename, ed=emotion_data):
                            try:
                                if not self.app.winfo_exists():
                                    return
                                self.app.append_text_to_widget(transcript, self.app.transcript_text)
                                self.app.notebook.select(0)
                                self.app.status_manager.success(f"Audio file processed and saved to database: {fn}")
                                self.app.progress_bar.stop()
                                self.app.progress_bar.pack_forget()

                                # Display emotion data in panel if available
                                if ed and hasattr(self.app, 'document_generators') and self.app.document_generators:
                                    self.app.document_generators._run_emotion_to_panel(ed)
                            except Exception:
                                pass
                        self.app.after(0, _on_success)
                    else:
                        self.app.after(0, lambda: self.app.update_status("No transcript was produced", "warning") if self.app.winfo_exists() else None)
                else:
                    def _on_fail():
                        try:
                            if not self.app.winfo_exists():
                                return
                            self.app.status_manager.error("Failed to process audio file")
                            self.app.progress_bar.stop()
                            self.app.progress_bar.pack_forget()
                        except Exception:
                            pass
                    self.app.after(0, _on_fail)
            except Exception as e:
                error_msg = f"Error processing audio file: {str(e)}"
                logger.error(error_msg, exc_info=True)
                def _on_error(msg=error_msg):
                    try:
                        if not self.app.winfo_exists():
                            return
                        self.app.status_manager.error(msg)
                        self.app.progress_bar.stop()
                        self.app.progress_bar.pack_forget()
                    except Exception:
                        pass
                self.app.after(0, _on_error)
                
        # Use I/O executor for the task since it primarily involves file I/O
        self.app.io_executor.submit(task)