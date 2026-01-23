"""
SOAP Processor Module

Handles SOAP recording processing including audio combination,
transcription, and SOAP note generation.
"""

import os
import concurrent.futures

from utils.structured_logging import get_logger

logger = get_logger(__name__)
import tkinter as tk
from tkinter import NORMAL, DISABLED
from ttkbootstrap.constants import LEFT
from datetime import datetime as dt
from typing import List, Any, Dict, Optional

from ai.ai import create_soap_note_with_openai
from settings.settings_manager import settings_manager


class SOAPProcessor:
    """Handles SOAP recording processing operations."""
    
    def __init__(self, parent_app):
        """Initialize the SOAP processor.
        
        Args:
            parent_app: The main application instance
        """
        self.app = parent_app
        self.audio_handler = parent_app.audio_handler
        self.status_manager = parent_app.status_manager
        self.io_executor = parent_app.io_executor
        
    def process_soap_recording(self) -> None:
        """Process SOAP recording using AudioHandler with improved concurrency."""
        def task():
            try:
                # Reset the audio handler silence threshold to normal
                self.audio_handler.silence_threshold = 0.01
                
                # Turn off SOAP debug mode
                self.audio_handler.soap_mode = False
                
                # Get combined audio from AudioStateManager
                audio_segment = self.app.audio_state_manager.get_combined_audio()
                
                # Check if we have any audio to process
                if not audio_segment:
                    logger.warning("No SOAP audio was recorded.")
                    # Update UI to indicate no audio
                    self.app.after(0, lambda: [
                        self.status_manager.warning("No audio recorded for SOAP note."),
                        self.app.progress_bar.stop(),
                        self.app.progress_bar.pack_forget(),
                        self.app.soap_button.config(state=NORMAL), # Re-enable button
                        self.app.cancel_soap_button.config(state=DISABLED)
                    ])
                    return # Exit task early

                # Log info about the audio
                duration_ms = len(audio_segment)
                logger.info(f"Processing SOAP audio, duration: {duration_ms}ms")
                
                # Update status on UI thread
                self.app.after(0, lambda: [
                    self.status_manager.progress("Finalizing SOAP audio..."),
                    self.app.progress_bar.pack(side=LEFT, padx=(5, 0))
                ])
                
                if not audio_segment:
                     # This case should be rare if checks above are done, but handle defensively
                    raise ValueError("Failed to create final audio segment from combined chunks")

                # --- Rest of the processing (saving, transcription) remains largely the same ---
                # Save the SOAP audio to the user's default storage folder

                # Try to get storage folder from both possible keys for backward compatibility
                storage_folder = settings_manager.get("storage_folder")
                logger.info(f"Storage folder from settings: {storage_folder}")

                if not storage_folder:
                    storage_folder = settings_manager.get("default_storage_folder")
                    logger.info(f"Using default_storage_folder instead: {storage_folder}")
                
                # If no storage folder is set, create default one
                if not storage_folder or not os.path.exists(storage_folder):
                    logger.warning(f"Storage folder '{storage_folder}' not found or not set, using default")
                    storage_folder = os.path.join(os.path.expanduser("~"), "Documents", "Medical-Dictation", "Storage")
                    os.makedirs(storage_folder, exist_ok=True)
                    logger.info(f"Created/using default storage folder: {storage_folder}")
                else:
                    logger.info(f"Using configured storage folder: {storage_folder}")
                    
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
                    
                    logger.info(f"SOAP audio segment stats: length={segment_length_ms}ms, "
                                f"rate={segment_frame_rate}Hz, channels={segment_channels}, "
                                f"width={segment_sample_width}bytes, max_volume={segment_max_volume}")
                    
                    # Check if the audio segment has meaningful content
                    if segment_length_ms < 100:  # Less than 100ms is probably empty
                        logger.warning(f"SOAP audio segment is too short ({segment_length_ms}ms), might be empty")
                    
                logger.info(f"Attempting to save SOAP audio to: {audio_path}")
                save_result = self.audio_handler.save_audio([audio_segment], audio_path)
                logger.info(f"Audio save result: {save_result}")
                
                if save_result:
                    # Verify file was actually created
                    if os.path.exists(audio_path):
                        file_size = os.path.getsize(audio_path)
                        logger.info(f"SOAP audio saved successfully to: {audio_path} (size: {file_size} bytes)")
                        self.app.after(0, lambda: self.status_manager.progress(f"SOAP audio saved to: {audio_path}"))
                    else:
                        logger.error(f"Audio save reported success but file not found: {audio_path}")
                        self.app.after(0, lambda: self.status_manager.progress("Warning: Audio file may not have been saved"))
                else:
                    logger.error(f"Failed to save SOAP audio to: {audio_path}")
                    self.app.after(0, lambda: self.status_manager.progress("Failed to save audio file"))
                
                # Update status on UI thread
                self.app.after(0, lambda: [
                    self.status_manager.progress("Transcribing SOAP audio..."),
                    self.app.progress_bar.pack(side=LEFT, padx=(5, 0))
                ])
                
                # Try transcription with the unified transcribe_audio method that handles prefix audio
                self.app.after(0, lambda: self.status_manager.progress("Transcribing SOAP audio with prefix..."))
                
                # Use the transcribe_audio method which already handles prefix audio and fallbacks
                transcript = self.audio_handler.transcribe_audio(audio_segment)
                
                # Log the result
                if transcript:
                    logger.info("Successfully transcribed SOAP audio with prefix")
                else:
                    logger.warning("Failed to transcribe SOAP audio with any provider")
                # If all transcription methods failed
                if not transcript:
                    raise ValueError("All transcription methods failed - no text recognized")
                
                # Log success and progress
                logger.info(f"Successfully transcribed audio, length: {len(transcript)} chars")
                
                # Update transcript tab with the raw transcript
                self.app.after(0, lambda: [
                    self.app.transcript_text.delete("1.0", tk.END),
                    self.app.transcript_text.insert(tk.END, transcript),
                    self.status_manager.progress("Creating SOAP note from transcript...")
                ])
                
                # Get context text from the context tab
                context_text = self.app.context_text.get("1.0", tk.END).strip()
                
                # Use IO executor for the AI API call (I/O-bound operation)
                future = self.io_executor.submit(
                    create_soap_note_with_openai,
                    transcript,
                    context_text
                )
                
                # Get result with timeout to prevent hanging
                result = future.result(timeout=120)
                
                # Store the values we need for database operations
                soap_note = result
                filename = "Transcript"
                
                # Schedule UI update on the main thread and save to database
                def finalize_soap():
                    self.app._update_text_area(soap_note, "SOAP note created", self.app.soap_button, self.app.soap_text)
                    self.app.notebook.select(1)  # Switch to SOAP tab
                    self.app.soap_text.focus_set()  # Give focus to SOAP text widget
                    # Save to database - update if recording exists, else create new
                    if hasattr(self.app, 'current_recording_id') and self.app.current_recording_id:
                        logger.debug(f"Updating existing recording {self.app.current_recording_id} with SOAP note")
                        success = self.app.db.update_recording(
                            self.app.current_recording_id,
                            transcript=transcript,
                            soap_note=soap_note
                        )
                        if success:
                            logger.info(f"Updated existing recording {self.app.current_recording_id}")
                            # Set selected_recording_id so analyses can save correctly
                            self.app.selected_recording_id = self.app.current_recording_id
                            logger.debug(f"Set selected_recording_id to {self.app.selected_recording_id} for analysis save")
                        else:
                            logger.error(f"Failed to update recording {self.app.current_recording_id}")
                    else:
                        logger.debug("No current_recording_id, creating new database entry")
                        self.app._save_soap_recording_to_database(filename, transcript, soap_note)

                    # Auto-run analyses to the side panels
                    if hasattr(self.app, 'document_generators') and self.app.document_generators:
                        logger.info(f"Scheduling auto-analysis for SOAP note ({len(soap_note)} chars)")
                        # Run medication analysis to panel
                        self.app.after(100, lambda sn=soap_note:
                            self.app.document_generators._run_medication_to_panel(sn))
                        # Run differential diagnosis to panel
                        self.app.after(200, lambda sn=soap_note:
                            self.app.document_generators._run_diagnostic_to_panel(sn))

                self.app.after(0, finalize_soap)
            except concurrent.futures.TimeoutError:
                self.app.after(0, lambda: [
                    self.status_manager.error("SOAP note creation timed out. Please try again."),
                    self.app.soap_button.config(state=NORMAL),
                    self.app.progress_bar.stop(),
                    self.app.progress_bar.pack_forget()
                ])
            except Exception as e:
                error_msg = f"Error processing SOAP note: {str(e)}"
                logger.error(error_msg, exc_info=True)
                self.app.after(0, lambda: [
                    self.status_manager.error(error_msg),
                    self.app.soap_button.config(state=NORMAL),
                    self.app.progress_bar.stop(),
                    self.app.progress_bar.pack_forget()
                ])

        # Use IO executor for the CPU-intensive audio processing
        self.io_executor.submit(task)
    
    def process_recording_async(self, recording_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a recording asynchronously for background queue processing.
        
        This method is designed to be called from the ProcessingQueue without
        UI interactions. It returns results that can be saved to the database.
        
        Args:
            recording_data: Dictionary containing:
                - audio_data: Raw audio data or segments
                - recording_id: Database ID
                - patient_name: Patient name
                - context: Context information
                
        Returns:
            Dictionary with processing results:
                - transcript: The transcribed text
                - soap_note: The generated SOAP note
                - audio_path: Path to saved audio file
                - success: Boolean indicating success
                - error: Error message if failed
        """
        try:
            logger.info(f"Starting async processing for recording {recording_data.get('recording_id')}")
            
            # Process audio data
            audio_segments = recording_data.get('audio_data', [])
            if not audio_segments:
                raise ValueError("No audio data provided")
            
            # Combine audio segments if multiple
            if isinstance(audio_segments, list):
                audio_segment = self.audio_handler.combine_audio_segments(audio_segments)
            else:
                audio_segment = audio_segments
            
            if not audio_segment:
                raise ValueError("Failed to create audio segment")
            
            # Generate filename and save audio
            storage_folder = settings_manager.get("storage_folder")
            logger.info(f"[Async] Storage folder from settings: {storage_folder}")

            if not storage_folder:
                storage_folder = settings_manager.get("default_storage_folder")
                logger.info(f"[Async] Using default_storage_folder instead: {storage_folder}")
            
            if not storage_folder or not os.path.exists(storage_folder):
                logger.warning(f"[Async] Storage folder '{storage_folder}' not found or not set, using default")
                storage_folder = os.path.join(os.path.expanduser("~"), "Documents", "Medical-Dictation", "Storage")
                os.makedirs(storage_folder, exist_ok=True)
                logger.info(f"[Async] Created/using default storage folder: {storage_folder}")
            else:
                logger.info(f"[Async] Using configured storage folder: {storage_folder}")
            
            # Create filename with patient name if available
            patient_name = recording_data.get('patient_name', 'Unknown')
            safe_patient_name = "".join(c for c in patient_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            date_formatted = dt.now().strftime("%d-%m-%y")
            time_formatted = dt.now().strftime("%H-%M")
            
            audio_path = os.path.join(storage_folder, f"recording_{safe_patient_name}_{date_formatted}_{time_formatted}.mp3")
            
            # Save audio
            logger.info(f"[Async] Attempting to save audio to: {audio_path}")
            save_result = self.audio_handler.save_audio([audio_segment], audio_path)
            logger.info(f"[Async] Audio save result: {save_result}")
            
            if not save_result:
                raise ValueError("Failed to save audio file")
            
            # Verify file was actually created
            if os.path.exists(audio_path):
                file_size = os.path.getsize(audio_path)
                logger.info(f"[Async] Audio saved successfully to: {audio_path} (size: {file_size} bytes)")
            else:
                logger.error(f"[Async] Audio save reported success but file not found: {audio_path}")
                raise ValueError("Audio file not found after save")
            
            # Transcribe audio
            transcript = self.audio_handler.transcribe_audio(audio_segment)
            if not transcript:
                raise ValueError("Transcription failed - no text recognized")
            
            logger.info(f"Transcription complete: {len(transcript)} characters")
            
            # Generate SOAP note
            context_text = recording_data.get('context', '')
            soap_note = create_soap_note_with_openai(transcript, context_text)
            
            if not soap_note:
                raise ValueError("Failed to generate SOAP note")
            
            logger.info(f"SOAP note generated successfully for recording {recording_data.get('recording_id')}")
            
            # Return results
            return {
                'success': True,
                'transcript': transcript,
                'soap_note': soap_note,
                'audio_path': audio_path,
                'duration': len(audio_segment) / 1000.0,  # Convert to seconds
                'patient_name': patient_name
            }
            
        except Exception as e:
            logger.error(f"Error in async processing: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'transcript': '',
                'soap_note': '',
                'audio_path': '',
                'duration': 0
            }