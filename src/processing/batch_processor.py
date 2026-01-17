"""
Batch Processor Module

Handles batch processing of recordings and audio files.
This module is extracted from document_generators.py for better code organization.
"""

import logging
import os
from typing import Dict, Any, List, Callable, Optional
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class BatchProcessor:
    """Manages batch processing of recordings and audio files."""

    def __init__(self, app):
        """Initialize the batch processor.

        Args:
            app: The main application instance
        """
        self.app = app

    def process_batch_recordings(self, recording_ids: List[int], options: Dict[str, Any],
                                 on_complete: Callable = None, on_progress: Callable = None) -> None:
        """Process multiple recordings in batch.

        Args:
            recording_ids: List of recording IDs to process
            options: Processing options dictionary containing:
                - process_soap: Whether to generate SOAP notes
                - process_referral: Whether to generate referrals
                - process_letter: Whether to generate letters
                - priority: Processing priority
                - skip_existing: Skip if content already exists
                - continue_on_error: Continue processing on errors
            on_complete: Callback when batch processing is complete
            on_progress: Callback for progress updates (message, completed, total)
        """
        # Get recordings from database
        recordings = self.app.db.get_recordings_by_ids(recording_ids)
        if not recordings:
            self.app.status_manager.error("No recordings found for batch processing")
            if on_complete:
                on_complete()
            return

        # Map priority strings to numeric values
        priority_map = {"low": 3, "normal": 5, "high": 7}
        numeric_priority = priority_map.get(options.get("priority", "normal"), 5)

        # Initialize processing queue if not available
        if not hasattr(self.app, 'processing_queue') or not self.app.processing_queue:
            from processing.processing_queue import ProcessingQueue
            self.app.processing_queue = ProcessingQueue(self.app)

        # Set up batch callback
        batch_id = None
        completed_count = 0
        total_count = len(recordings)

        def batch_callback(event: str, bid: str, current: int, total: int, **kwargs):
            nonlocal batch_id, completed_count
            batch_id = bid

            if event == "progress":
                completed_count = current
                if on_progress:
                    msg = f"Processing recordings"
                    on_progress(msg, current, total)
            elif event == "completed":
                # Batch complete
                if on_complete:
                    on_complete()

                # Show summary
                failed = kwargs.get("failed", 0)
                if failed > 0:
                    self.app.status_manager.warning(
                        f"Batch processing completed: {current - failed} successful, {failed} failed"
                    )
                else:
                    self.app.status_manager.success(
                        f"Batch processing completed: {current} recordings processed successfully"
                    )

        self.app.processing_queue.set_batch_callback(batch_callback)

        # Build batch recordings data
        batch_recordings = []

        for recording in recordings:
            rec_id = recording['id']

            # Check if we should skip based on existing content
            if options.get("skip_existing", True):
                skip = False
                if options.get("process_soap") and recording.get("soap_note"):
                    skip = True
                elif options.get("process_referral") and recording.get("referral"):
                    skip = True
                elif options.get("process_letter") and recording.get("letter"):
                    skip = True

                if skip:
                    logging.info(f"Skipping recording {rec_id} - already has requested content")
                    total_count -= 1
                    continue

            # Build recording data for processing
            recording_data = {
                "recording_id": rec_id,
                "filename": recording.get("filename", ""),
                "transcript": recording.get("transcript", ""),
                "patient_name": recording.get("patient_name", "Unknown"),
                "process_options": {
                    "generate_soap": options.get("process_soap", False),
                    "generate_referral": options.get("process_referral", False),
                    "generate_letter": options.get("process_letter", False)
                },
                "continue_on_error": options.get("continue_on_error", True)
            }

            batch_recordings.append(recording_data)

        if not batch_recordings:
            self.app.status_manager.info("All selected recordings already have the requested content")
            if on_complete:
                on_complete()
            return

        # Update progress callback with actual count
        if on_progress:
            on_progress("Starting batch processing", 0, len(batch_recordings))

        # Submit batch to processing queue
        batch_options = {
            "priority": numeric_priority,
            "continue_on_error": options.get("continue_on_error", True)
        }

        batch_id = self.app.processing_queue.add_batch_recordings(batch_recordings, batch_options)

        logging.info(f"Started batch processing with ID {batch_id} for {len(batch_recordings)} recordings")

    def process_batch_files(self, file_paths: List[str], options: Dict[str, Any],
                            on_complete: Callable = None, on_progress: Callable = None) -> None:
        """Process multiple audio files in batch.

        Args:
            file_paths: List of audio file paths to process
            options: Processing options dictionary
            on_complete: Callback when batch processing is complete
            on_progress: Callback for progress updates (message, completed, total)
        """
        # Map priority strings to numeric values
        priority_map = {"low": 3, "normal": 5, "high": 7}
        numeric_priority = priority_map.get(options.get("priority", "normal"), 5)

        # Initialize processing queue if not available
        if not hasattr(self.app, 'processing_queue') or not self.app.processing_queue:
            from processing.processing_queue import ProcessingQueue
            self.app.processing_queue = ProcessingQueue(self.app)

        # Validate and prepare files
        valid_files = []
        for file_path in file_paths:
            if os.path.exists(file_path) and os.path.isfile(file_path):
                valid_files.append(file_path)
            else:
                logging.warning(f"Invalid file path: {file_path}")

        if not valid_files:
            self.app.status_manager.error("No valid audio files found for batch processing")
            if on_complete:
                on_complete()
            return

        total_count = len(valid_files)
        completed_count = 0

        def process_single_file(file_path: str, index: int):
            """Process a single audio file."""
            nonlocal completed_count

            try:
                if on_progress:
                    on_progress(f"Processing {os.path.basename(file_path)}", index, total_count)

                # Step 1: Transcribe the audio file
                # Get selected STT provider from settings
                from settings.settings import SETTINGS
                from pydub import AudioSegment
                stt_provider = SETTINGS.get("stt_provider", "groq")

                # Use the app's existing audio handler which has initialized STT providers
                audio_handler = self.app.audio_handler

                # Transcribe the file
                transcript = None
                error_msg = None

                try:
                    # Load the audio file as AudioSegment
                    audio_segment = AudioSegment.from_file(file_path)

                    # Use the appropriate STT provider (handle case variations)
                    stt_provider_lower = stt_provider.lower()
                    if stt_provider_lower == "deepgram":
                        transcript = audio_handler.deepgram_provider.transcribe(audio_segment)
                    elif stt_provider_lower == "elevenlabs":
                        transcript = audio_handler.elevenlabs_provider.transcribe(audio_segment)
                    elif stt_provider_lower == "groq":
                        transcript = audio_handler.groq_provider.transcribe(audio_segment)
                    elif stt_provider_lower in ["local whisper", "whisper"]:
                        transcript = audio_handler.whisper_provider.transcribe(audio_segment)
                    else:
                        error_msg = f"Unknown STT provider: {stt_provider}"

                except Exception as e:
                    error_msg = f"Transcription failed: {str(e)}"
                    logging.error(f"Failed to transcribe {file_path}: {e}")

                if error_msg:
                    if options.get("continue_on_error", True):
                        if on_progress:
                            on_progress(f"Failed: {os.path.basename(file_path)} - {error_msg}",
                                        index + 1, total_count)
                        return
                    else:
                        raise Exception(error_msg)

                if not transcript:
                    if on_progress:
                        on_progress(f"No transcript for {os.path.basename(file_path)}",
                                    index + 1, total_count)
                    return

                # Step 2: Save recording to database
                filename = os.path.basename(file_path)
                rec_id = self.app.db.add_recording(
                    filename=filename,
                    transcript=transcript,
                    audio_path=file_path
                )

                if not rec_id:
                    raise Exception("Failed to save recording to database")

                # Step 3: Create recording data for processing
                recording_data = {
                    "recording_id": rec_id,
                    "filename": filename,
                    "transcript": transcript,
                    "patient_name": f"Patient from {filename}",
                    "audio_path": file_path,
                    "process_options": {
                        "generate_soap": options.get("process_soap", False),
                        "generate_referral": options.get("process_referral", False),
                        "generate_letter": options.get("process_letter", False)
                    },
                    "priority": numeric_priority
                }

                # Step 4: Add to processing queue
                task_id = self.app.processing_queue.add_recording(recording_data)

                completed_count += 1

                if on_progress:
                    on_progress(f"Queued: {os.path.basename(file_path)}",
                                completed_count, total_count)

            except Exception as e:
                logging.error(f"Error processing file {file_path}: {e}")
                if not options.get("continue_on_error", True):
                    raise
                if on_progress:
                    on_progress(f"Error: {os.path.basename(file_path)} - {str(e)}",
                                index + 1, total_count)

        # Process files sequentially (could be parallelized if needed)
        try:
            for i, file_path in enumerate(valid_files):
                process_single_file(file_path, i)

            # Notify completion
            if on_complete:
                on_complete()

            self.app.status_manager.success(
                f"Batch file processing completed: {completed_count} files queued for processing"
            )

        except Exception as e:
            logging.error(f"Batch file processing failed: {e}")
            if on_complete:
                on_complete()
            raise
