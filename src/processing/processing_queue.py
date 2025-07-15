"""
Background Processing Queue Module

Manages asynchronous processing of recordings to allow immediate
continuation with next patient consultation.
"""

import logging
import uuid
import time
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, Future
from threading import Thread, Lock, Event
from typing import Dict, Optional, Callable, Any, List
from datetime import datetime
import traceback

from database.database import Database
from settings.settings import SETTINGS


class ProcessingQueue:
    """Manages background processing of medical recordings."""
    
    def __init__(self, app=None, max_workers: int = None):
        """Initialize the processing queue.
        
        Args:
            app: The main application instance
            max_workers: Maximum number of concurrent processing threads
        """
        self.app = app
        self.max_workers = max_workers or SETTINGS.get("max_background_workers", 2)
        
        # Core components
        self.queue = Queue()
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.active_tasks: Dict[str, Dict] = {}
        self.completed_tasks: Dict[str, Dict] = {}
        self.failed_tasks: Dict[str, Dict] = {}
        self.batch_tasks: Dict[str, Dict] = {}  # Track batch processing
        
        # Thread safety
        self.lock = Lock()
        self.shutdown_event = Event()
        
        # Callbacks
        self.status_callback: Optional[Callable] = None
        self.completion_callback: Optional[Callable] = None
        self.error_callback: Optional[Callable] = None
        self.batch_callback: Optional[Callable] = None  # For batch progress updates
        
        # Statistics
        self.stats = {
            "total_queued": 0,
            "total_processed": 0,
            "total_failed": 0,
            "total_retried": 0,
            "processing_time_avg": 0
        }
        
        # Start the queue processor
        self.processor_thread = Thread(target=self._process_queue, daemon=True)
        self.processor_thread.start()
        
        logging.info(f"ProcessingQueue initialized with {self.max_workers} workers")
    
    def add_recording(self, recording_data: Dict[str, Any]) -> str:
        """Add a recording to the processing queue.
        
        Args:
            recording_data: Dictionary containing:
                - recording_id: Database ID of the recording
                - audio_data: Raw audio data
                - patient_name: Patient name for notifications
                - context: Any context information
                - priority: Processing priority (0-10, default 5)
                - batch_id: Optional batch identifier
        
        Returns:
            task_id: Unique identifier for tracking this task
        """
        task_id = str(uuid.uuid4())
        
        # Add timestamp and task ID
        recording_data["task_id"] = task_id
        recording_data["queued_at"] = datetime.now()
        recording_data["priority"] = recording_data.get("priority", 5)
        recording_data["retry_count"] = 0
        recording_data["status"] = "queued"
        
        # Add to queue
        self.queue.put((recording_data["priority"], task_id, recording_data))
        
        # Track in active tasks
        with self.lock:
            self.active_tasks[task_id] = recording_data
            self.stats["total_queued"] += 1
            
            # Track batch if provided
            batch_id = recording_data.get("batch_id")
            if batch_id:
                if batch_id not in self.batch_tasks:
                    self.batch_tasks[batch_id] = {
                        "total": 0,
                        "completed": 0,
                        "failed": 0,
                        "task_ids": []
                    }
                self.batch_tasks[batch_id]["total"] += 1
                self.batch_tasks[batch_id]["task_ids"].append(task_id)
        
        # Notify status update
        self._notify_status_update(task_id, "queued", len(self.active_tasks))
        
        logging.info(f"Recording {recording_data.get('recording_id')} added to queue as task {task_id}")
        
        return task_id
    
    def add_batch_recordings(self, recordings: List[Dict[str, Any]], batch_options: Dict[str, Any] = None) -> str:
        """Add multiple recordings to the processing queue as a batch.
        
        Args:
            recordings: List of recording data dictionaries
            batch_options: Optional batch-wide options (priority, etc.)
            
        Returns:
            batch_id: Unique identifier for the batch
        """
        batch_id = str(uuid.uuid4())
        batch_priority = batch_options.get("priority", 5) if batch_options else 5
        
        logging.info(f"Adding batch {batch_id} with {len(recordings)} recordings")
        
        # Initialize batch tracking
        with self.lock:
            self.batch_tasks[batch_id] = {
                "total": len(recordings),
                "completed": 0,
                "failed": 0,
                "task_ids": [],
                "started_at": datetime.now(),
                "options": batch_options or {}
            }
        
        # Add each recording with batch info
        task_ids = []
        for recording_data in recordings:
            # Add batch info to recording data
            recording_data["batch_id"] = batch_id
            recording_data["priority"] = recording_data.get("priority", batch_priority)
            
            # Add batch options
            if batch_options:
                recording_data["batch_options"] = batch_options
            
            task_id = self.add_recording(recording_data)
            task_ids.append(task_id)
        
        # Notify batch start
        if self.batch_callback:
            try:
                self.batch_callback("started", batch_id, 0, len(recordings))
            except Exception as e:
                logging.error(f"Error in batch callback: {str(e)}")
        
        return batch_id
    
    def _process_queue(self):
        """Main queue processing loop - runs in separate thread."""
        logging.info("Processing queue started")
        
        while not self.shutdown_event.is_set():
            try:
                # Wait for items with timeout
                priority, task_id, recording_data = self.queue.get(timeout=1.0)
                
                # Submit to executor
                future = self.executor.submit(self._process_recording, task_id, recording_data)
                
                # Track the future
                with self.lock:
                    if task_id in self.active_tasks:
                        self.active_tasks[task_id]["future"] = future
                        self.active_tasks[task_id]["status"] = "processing"
                
                # Mark queue task as done
                self.queue.task_done()
                
            except Empty:
                # No items in queue, continue waiting
                continue
            except Exception as e:
                logging.error(f"Error in queue processor: {str(e)}", exc_info=True)
    
    def _process_recording(self, task_id: str, recording_data: Dict[str, Any]):
        """Process a single recording - runs in thread pool."""
        start_time = time.time()
        recording_id = recording_data.get("recording_id")
        
        try:
            logging.info(f"Starting processing for task {task_id}, recording {recording_id}")
            
            # Update status
            recording_data["status"] = "processing"
            recording_data["started_at"] = datetime.now()
            self._notify_status_update(task_id, "processing", len(self.active_tasks))
            
            # Update database status
            if self.app and hasattr(self.app, 'db'):
                self.app.db.update_recording(
                    recording_id,
                    processing_status="processing",
                    processing_started_at=datetime.now()
                )
            
            # Get the processing function from the app
            if self.app:
                # Process based on options
                process_options = recording_data.get("process_options", {})
                results = {}
                
                # First, check if we need to transcribe audio
                transcript = recording_data.get("transcript", "")
                if not transcript and recording_data.get("audio_data"):
                    # Transcribe the audio
                    logging.info(f"Transcribing audio for recording {recording_id}")
                    audio_data = recording_data.get("audio_data")
                    
                    # Save audio file before transcription
                    try:
                        from settings.settings import SETTINGS
                        from datetime import datetime as dt
                        import os
                        
                        # Get storage folder
                        storage_folder = SETTINGS.get("storage_folder")
                        logging.info(f"[Queue] Storage folder from settings: {storage_folder}")
                        
                        if not storage_folder:
                            storage_folder = SETTINGS.get("default_storage_folder")
                            logging.info(f"[Queue] Using default_storage_folder instead: {storage_folder}")
                        
                        if not storage_folder or not os.path.exists(storage_folder):
                            logging.warning(f"[Queue] Storage folder '{storage_folder}' not found or not set, using default")
                            storage_folder = os.path.join(os.path.expanduser("~"), "Documents", "Medical-Dictation", "Storage")
                            os.makedirs(storage_folder, exist_ok=True)
                            logging.info(f"[Queue] Created/using default storage folder: {storage_folder}")
                        else:
                            logging.info(f"[Queue] Using configured storage folder: {storage_folder}")
                        
                        # Create filename with patient name
                        patient_name = recording_data.get('patient_name', 'Patient')
                        safe_patient_name = "".join(c for c in patient_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        date_formatted = dt.now().strftime("%d-%m-%y")
                        time_formatted = dt.now().strftime("%H-%M")
                        audio_path = os.path.join(storage_folder, f"recording_{safe_patient_name}_{date_formatted}_{time_formatted}.mp3")
                        
                        # Save audio using audio handler
                        logging.info(f"[Queue] Attempting to save audio to: {audio_path}")
                        if hasattr(self.app, 'audio_handler'):
                            # Convert audio_data to list if needed
                            audio_segments = [audio_data] if not isinstance(audio_data, list) else audio_data
                            save_result = self.app.audio_handler.save_audio(audio_segments, audio_path)
                            logging.info(f"[Queue] Audio save result: {save_result}")
                            
                            if save_result:
                                # Verify file was actually created
                                if os.path.exists(audio_path):
                                    file_size = os.path.getsize(audio_path)
                                    logging.info(f"[Queue] Audio saved successfully to: {audio_path} (size: {file_size} bytes)")
                                else:
                                    logging.error(f"[Queue] Audio save reported success but file not found: {audio_path}")
                            else:
                                logging.error(f"[Queue] Failed to save audio to: {audio_path}")
                    except Exception as e:
                        logging.error(f"[Queue] Error saving audio file: {str(e)}", exc_info=True)
                        # Continue with transcription even if audio save fails
                    
                    # Log audio data info
                    if hasattr(audio_data, 'duration_seconds'):
                        logging.info(f"Audio duration: {audio_data.duration_seconds} seconds")
                    
                    # Use the app's audio handler to transcribe
                    if hasattr(self.app, 'audio_handler'):
                        try:
                            transcript = self.app.audio_handler.transcribe_audio(audio_data)
                            if transcript:
                                # Update the recording data and database
                                recording_data["transcript"] = transcript
                                self.app.db.update_recording(recording_id, transcript=transcript)
                                logging.info(f"Transcription completed for recording {recording_id}: {len(transcript)} characters")
                            else:
                                raise Exception("Transcription returned empty result")
                        except Exception as e:
                            logging.error(f"Transcription failed: {str(e)}", exc_info=True)
                            raise Exception(f"Failed to transcribe audio: {str(e)}")
                    else:
                        logging.error("Audio handler not available for transcription")
                        raise Exception("Audio handler not available for transcription")
                else:
                    if transcript:
                        logging.info(f"Using existing transcript for recording {recording_id}: {len(transcript)} characters")
                    else:
                        logging.warning(f"No transcript or audio data for recording {recording_id}")
                
                # Generate SOAP note if requested
                if process_options.get("generate_soap", True):
                    if transcript:
                        logging.info(f"Generating SOAP note for recording {recording_id}")
                        soap_result = self._generate_soap_note(transcript)
                        if soap_result:
                            results["soap_note"] = soap_result
                            # Update database
                            self.app.db.update_recording(recording_id, soap_note=soap_result)
                            logging.info(f"SOAP note generated for recording {recording_id}: {len(soap_result)} characters")
                        else:
                            logging.warning(f"SOAP generation returned empty result for recording {recording_id}")
                    else:
                        logging.warning(f"No transcript available for SOAP generation for recording {recording_id}")
                
                # Generate referral if requested
                if process_options.get("generate_referral") and results.get("soap_note"):
                    referral_result = self._generate_referral(results["soap_note"])
                    if referral_result:
                        results["referral"] = referral_result
                        # Update database
                        self.app.db.update_recording(recording_id, referral=referral_result)
                
                # Generate letter if requested
                if process_options.get("generate_letter"):
                    content = results.get("soap_note") or recording_data.get("transcript", "")
                    if content:
                        letter_result = self._generate_letter(content)
                        if letter_result:
                            results["letter"] = letter_result
                            # Update database
                            self.app.db.update_recording(recording_id, letter=letter_result)
                
                # Log final results
                logging.info(f"Processing results for recording {recording_id}: {list(results.keys())}")
                
                # Format results for callback with expected structure
                callback_result = {
                    'success': True,
                    'transcript': recording_data.get("transcript", ""),
                    'soap_note': results.get("soap_note", ""),
                    'referral': results.get("referral", ""),
                    'letter': results.get("letter", ""),
                    'completed_at': datetime.now()
                }
                
                # Mark as completed
                self._mark_completed(task_id, recording_data, callback_result, time.time() - start_time)
                
            else:
                logging.error("No app context available for processing")
                raise Exception("No app context available")
                
        except Exception as e:
            # Handle processing error
            error_msg = f"Processing failed: {str(e)}"
            logging.error(f"Task {task_id} failed: {error_msg}", exc_info=True)
            
            # Check retry logic
            if self._should_retry(recording_data):
                self._retry_task(task_id, recording_data, error_msg)
            else:
                self._mark_failed(task_id, recording_data, error_msg)
    
    def _mark_completed(self, task_id: str, recording_data: Dict, result: Dict, processing_time: float):
        """Mark a task as completed successfully."""
        with self.lock:
            # Update task data
            recording_data["status"] = "completed"
            recording_data["completed_at"] = datetime.now()
            recording_data["processing_time"] = processing_time
            recording_data["result"] = result
            
            # Move to completed
            if task_id in self.active_tasks:
                self.completed_tasks[task_id] = self.active_tasks.pop(task_id)
            
            # Update stats
            self.stats["total_processed"] += 1
            self._update_avg_processing_time(processing_time)
            
            # Update batch tracking if part of a batch
            batch_id = recording_data.get("batch_id")
            if batch_id and batch_id in self.batch_tasks:
                self.batch_tasks[batch_id]["completed"] += 1
                self._check_batch_completion(batch_id)
        
        # Update database
        if self.app and hasattr(self.app, 'db'):
            self.app.db.update_recording(
                recording_data["recording_id"],
                processing_status="completed",
                processing_completed_at=datetime.now()
            )
        
        # Add processing time to result for notification
        if isinstance(result, dict):
            result['processing_time'] = processing_time
        
        # Notify completion
        self._notify_completion(task_id, recording_data, result)
        self._notify_status_update(task_id, "completed", len(self.active_tasks))
        
        logging.info(f"Task {task_id} completed in {processing_time:.2f} seconds")
    
    def _mark_failed(self, task_id: str, recording_data: Dict, error_msg: str):
        """Mark a task as failed."""
        with self.lock:
            # Update task data
            recording_data["status"] = "failed"
            recording_data["failed_at"] = datetime.now()
            recording_data["error_message"] = error_msg
            
            # Move to failed
            if task_id in self.active_tasks:
                self.failed_tasks[task_id] = self.active_tasks.pop(task_id)
            
            # Update stats
            self.stats["total_failed"] += 1
            
            # Update batch tracking if part of a batch
            batch_id = recording_data.get("batch_id")
            if batch_id and batch_id in self.batch_tasks:
                self.batch_tasks[batch_id]["failed"] += 1
                self._check_batch_completion(batch_id)
        
        # Update database
        if self.app and hasattr(self.app, 'db'):
            self.app.db.update_recording(
                recording_data["recording_id"],
                processing_status="failed",
                error_message=error_msg
            )
        
        # Notify failure
        self._notify_error(task_id, recording_data, error_msg)
        self._notify_status_update(task_id, "failed", len(self.active_tasks))
        
        logging.error(f"Task {task_id} failed: {error_msg}")
    
    def _should_retry(self, recording_data: Dict) -> bool:
        """Check if a task should be retried."""
        if not SETTINGS.get("auto_retry_failed", True):
            return False
        
        max_retries = SETTINGS.get("max_retry_attempts", 3)
        return recording_data.get("retry_count", 0) < max_retries
    
    def _retry_task(self, task_id: str, recording_data: Dict, error_msg: str):
        """Retry a failed task with exponential backoff."""
        retry_count = recording_data.get("retry_count", 0) + 1
        recording_data["retry_count"] = retry_count
        recording_data["last_error"] = error_msg
        
        # Calculate backoff delay
        delay = min(300, 2 ** retry_count)  # Max 5 minutes
        
        with self.lock:
            self.stats["total_retried"] += 1
        
        logging.info(f"Retrying task {task_id} (attempt {retry_count}) after {delay} seconds")
        
        # Schedule retry
        def delayed_retry():
            time.sleep(delay)
            if not self.shutdown_event.is_set():
                self.queue.put((recording_data["priority"] - 1, task_id, recording_data))
        
        Thread(target=delayed_retry, daemon=True).start()
    
    def _update_avg_processing_time(self, new_time: float):
        """Update average processing time statistic."""
        total = self.stats["total_processed"]
        if total == 1:
            self.stats["processing_time_avg"] = new_time
        else:
            # Running average
            current_avg = self.stats["processing_time_avg"]
            self.stats["processing_time_avg"] = ((current_avg * (total - 1)) + new_time) / total
    
    def _notify_status_update(self, task_id: str, status: str, queue_size: int):
        """Notify status callback of queue status change."""
        if self.status_callback:
            try:
                self.status_callback(task_id, status, queue_size)
            except Exception as e:
                logging.error(f"Error in status callback: {str(e)}")
    
    def _notify_completion(self, task_id: str, recording_data: Dict, result: Dict):
        """Notify completion callback."""
        if self.completion_callback:
            try:
                self.completion_callback(task_id, recording_data, result)
            except Exception as e:
                logging.error(f"Error in completion callback: {str(e)}")
    
    def _notify_error(self, task_id: str, recording_data: Dict, error_msg: str):
        """Notify error callback."""
        if self.error_callback:
            try:
                self.error_callback(task_id, recording_data, error_msg)
            except Exception as e:
                logging.error(f"Error in error callback: {str(e)}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current queue status and statistics."""
        with self.lock:
            return {
                "queue_size": self.queue.qsize(),
                "active_tasks": len(self.active_tasks),
                "completed_tasks": len(self.completed_tasks),
                "failed_tasks": len(self.failed_tasks),
                "stats": self.stats.copy(),
                "workers": self.max_workers
            }
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get status of a specific task."""
        with self.lock:
            if task_id in self.active_tasks:
                return self.active_tasks[task_id].copy()
            elif task_id in self.completed_tasks:
                return self.completed_tasks[task_id].copy()
            elif task_id in self.failed_tasks:
                return self.failed_tasks[task_id].copy()
        return None
    
    def cancel_task(self, task_id: str) -> bool:
        """Attempt to cancel a queued or processing task."""
        with self.lock:
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                if task["status"] == "queued":
                    # Remove from queue if still queued
                    task["status"] = "cancelled"
                    self.active_tasks.pop(task_id)
                    logging.info(f"Task {task_id} cancelled")
                    return True
                elif "future" in task:
                    # Try to cancel running task
                    future: Future = task["future"]
                    if future.cancel():
                        self.active_tasks.pop(task_id)
                        logging.info(f"Task {task_id} cancelled")
                        return True
        return False
    
    def shutdown(self, wait: bool = True):
        """Shutdown the processing queue gracefully."""
        logging.info("Shutting down processing queue...")
        
        # Signal shutdown
        self.shutdown_event.set()
        
        # Wait for processor thread
        if wait:
            self.processor_thread.join(timeout=5)
        
        # Shutdown executor
        self.executor.shutdown(wait=wait)
        
        logging.info("Processing queue shutdown complete")
    
    def _check_batch_completion(self, batch_id: str):
        """Check if a batch is complete and notify if so."""
        batch = self.batch_tasks.get(batch_id)
        if not batch:
            return
            
        total = batch["total"]
        completed = batch["completed"]
        failed = batch["failed"]
        
        # Notify progress
        if self.batch_callback:
            try:
                self.batch_callback("progress", batch_id, completed + failed, total)
            except Exception as e:
                logging.error(f"Error in batch callback: {str(e)}")
        
        # Check if batch is complete
        if completed + failed >= total:
            batch["completed_at"] = datetime.now()
            
            # Calculate duration
            duration = (batch["completed_at"] - batch["started_at"]).total_seconds()
            batch["duration"] = duration
            
            # Notify completion
            if self.batch_callback:
                try:
                    self.batch_callback("completed", batch_id, completed, total, failed=failed)
                except Exception as e:
                    logging.error(f"Error in batch callback: {str(e)}")
            
            logging.info(f"Batch {batch_id} completed: {completed} successful, {failed} failed, {duration:.2f}s")
    
    def get_batch_status(self, batch_id: str) -> Optional[Dict]:
        """Get the status of a batch.
        
        Args:
            batch_id: Batch identifier
            
        Returns:
            Batch status dictionary or None if not found
        """
        with self.lock:
            batch = self.batch_tasks.get(batch_id)
            if batch:
                return {
                    "batch_id": batch_id,
                    "total": batch["total"],
                    "completed": batch["completed"],
                    "failed": batch["failed"],
                    "in_progress": batch["total"] - batch["completed"] - batch["failed"],
                    "started_at": batch.get("started_at"),
                    "completed_at": batch.get("completed_at"),
                    "duration": batch.get("duration"),
                    "options": batch.get("options", {})
                }
        return None
    
    def set_batch_callback(self, callback: Callable):
        """Set the batch progress callback.
        
        Args:
            callback: Function to call with (event, batch_id, current, total, **kwargs)
        """
        self.batch_callback = callback
    
    def _generate_soap_note(self, transcript: str) -> Optional[str]:
        """Generate SOAP note from transcript.
        
        Args:
            transcript: The transcript text
            
        Returns:
            Generated SOAP note or None if failed
        """
        try:
            from ai.ai import create_soap_note_with_openai
            from settings.settings import SETTINGS
            
            provider = SETTINGS.get("ai_provider", "openai")
            model = SETTINGS.get(f"{provider}_model", "gpt-4")
            
            # Generate SOAP note
            soap_note = create_soap_note_with_openai(transcript)
            return soap_note
        except Exception as e:
            logging.error(f"Error generating SOAP note: {str(e)}")
            return None
    
    def _generate_referral(self, soap_note: str) -> Optional[str]:
        """Generate referral from SOAP note.
        
        Args:
            soap_note: The SOAP note text
            
        Returns:
            Generated referral or None if failed
        """
        try:
            from ai.ai import create_referral_with_openai
            from settings.settings import SETTINGS
            
            provider = SETTINGS.get("ai_provider", "openai")
            model = SETTINGS.get(f"{provider}_model", "gpt-4")
            
            # For batch processing, use a default condition
            conditions = "Based on the clinical findings in the SOAP note"
            
            # Generate referral
            referral = create_referral_with_openai(soap_note, conditions)
            return referral
        except Exception as e:
            logging.error(f"Error generating referral: {str(e)}")
            return None
    
    def _generate_letter(self, content: str) -> Optional[str]:
        """Generate letter from content.
        
        Args:
            content: The source content (SOAP note or transcript)
            
        Returns:
            Generated letter or None if failed
        """
        try:
            from ai.ai import create_letter_with_ai
            from settings.settings import SETTINGS
            
            provider = SETTINGS.get("ai_provider", "openai")
            model = SETTINGS.get(f"{provider}_model", "gpt-4")
            
            # Generate letter
            letter = create_letter_with_ai(content)
            return letter
        except Exception as e:
            logging.error(f"Error generating letter: {str(e)}")
            return None