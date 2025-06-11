"""
SOAP Processor Module

Handles SOAP recording processing including audio combination,
transcription, and SOAP note generation.
"""

import os
import logging
import concurrent.futures
import tkinter as tk
from tkinter import NORMAL, DISABLED
from ttkbootstrap.constants import LEFT
from datetime import datetime as dt
from typing import List, Any, Dict, Optional

from ai.ai import create_soap_note_with_openai
from settings.settings import SETTINGS


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
                    logging.warning("No SOAP audio was recorded.")
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
                logging.info(f"Processing SOAP audio, duration: {duration_ms}ms")
                
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
                from settings.settings import SETTINGS
                
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
                    self.app.after(0, lambda: self.status_manager.progress(f"SOAP audio saved to: {audio_path}"))
                
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
                    logging.info("Successfully transcribed SOAP audio with prefix")
                else:
                    logging.warning("Failed to transcribe SOAP audio with any provider")
                # If all transcription methods failed
                if not transcript:
                    raise ValueError("All transcription methods failed - no text recognized")
                
                # Log success and progress
                logging.info(f"Successfully transcribed audio, length: {len(transcript)} chars")
                
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
                self.app.after(0, lambda: [
                    self.app._update_text_area(soap_note, "SOAP note created", self.app.soap_button, self.app.soap_text),
                    self.app.notebook.select(1),  # Switch to SOAP tab
                    # Save to database on the main thread
                    self.app._save_soap_recording_to_database(filename, transcript, soap_note)
                ])
            except concurrent.futures.TimeoutError:
                self.app.after(0, lambda: [
                    self.status_manager.error("SOAP note creation timed out. Please try again."),
                    self.app.soap_button.config(state=NORMAL),
                    self.app.progress_bar.stop(),
                    self.app.progress_bar.pack_forget()
                ])
            except Exception as e:
                error_msg = f"Error processing SOAP note: {str(e)}"
                logging.error(error_msg, exc_info=True)
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
            logging.info(f"Starting async processing for recording {recording_data.get('recording_id')}")
            
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
            storage_folder = SETTINGS.get("storage_folder") or SETTINGS.get("default_storage_folder")
            if not storage_folder or not os.path.exists(storage_folder):
                storage_folder = os.path.join(os.path.expanduser("~"), "Documents", "Medical-Dictation", "Storage")
                os.makedirs(storage_folder, exist_ok=True)
            
            # Create filename with patient name if available
            patient_name = recording_data.get('patient_name', 'Unknown')
            safe_patient_name = "".join(c for c in patient_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            date_formatted = dt.now().strftime("%d-%m-%y")
            time_formatted = dt.now().strftime("%H-%M")
            
            audio_path = os.path.join(storage_folder, f"recording_{safe_patient_name}_{date_formatted}_{time_formatted}.mp3")
            
            # Save audio
            if not self.audio_handler.save_audio([audio_segment], audio_path):
                raise ValueError("Failed to save audio file")
            
            logging.info(f"Audio saved to: {audio_path}")
            
            # Transcribe audio
            transcript = self.audio_handler.transcribe_audio(audio_segment)
            if not transcript:
                raise ValueError("Transcription failed - no text recognized")
            
            logging.info(f"Transcription complete: {len(transcript)} characters")
            
            # Generate SOAP note
            context_text = recording_data.get('context', '')
            soap_note = create_soap_note_with_openai(transcript, context_text)
            
            if not soap_note:
                raise ValueError("Failed to generate SOAP note")
            
            logging.info(f"SOAP note generated successfully for recording {recording_data.get('recording_id')}")
            
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
            logging.error(f"Error in async processing: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'transcript': '',
                'soap_note': '',
                'audio_path': '',
                'duration': 0
            }