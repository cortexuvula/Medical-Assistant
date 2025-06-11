"""
Document Generators Module

Handles the generation of medical documents including SOAP notes, referrals, 
and letters from transcripts using AI processing.
"""

import logging
import concurrent.futures
from tkinter import messagebox
from tkinter.constants import DISABLED, NORMAL, RIGHT

from ai.ai import create_soap_note_with_openai, create_referral_with_openai, get_possible_conditions, create_letter_with_ai
from ui.dialogs.dialogs import ask_conditions_dialog


class DocumentGenerators:
    """Manages medical document generation functionality."""
    
    def __init__(self, parent_app):
        """Initialize the document generators.
        
        Args:
            parent_app: The main application instance
        """
        self.app = parent_app
        
    def create_soap_note(self) -> None:
        """Create a SOAP note from the selected text using AI with improved concurrency."""
        transcript = self.app.transcript_text.get("1.0", "end").strip()
        if not transcript:
            messagebox.showwarning("Create SOAP Note", "There is no transcript to process.")
            return

        self.app.status_manager.progress("Creating SOAP note (this may take a moment)...")
        self.app.soap_button.config(state=DISABLED)
        self.app.progress_bar.pack(side=RIGHT, padx=10)
        self.app.progress_bar.start()

        def task() -> None:
            try:
                # Get context text from the context tab
                context_text = self.app.context_text.get("1.0", "end").strip()
                
                # Use IO executor for the AI API call (I/O-bound operation)
                future = self.app.io_executor.submit(
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
                    self.app.status_manager.error("SOAP note creation timed out. Please try again."),
                    self.app.soap_button.config(state=NORMAL),
                    self.app.progress_bar.stop(),
                    self.app.progress_bar.pack_forget()
                ])
            except Exception as e:
                error_msg = f"Error creating SOAP note: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.app.after(0, lambda: [
                    self.app.status_manager.error(error_msg),
                    self.app.soap_button.config(state=NORMAL),
                    self.app.progress_bar.stop(),
                    self.app.progress_bar.pack_forget()
                ])

        # Use I/O executor for task management since it involves UI coordination
        self.app.io_executor.submit(task)

    def create_referral(self) -> None:
        """Create a referral from transcript with improved concurrency."""
        # Check if the transcript is empty before proceeding
        text = self.app.transcript_text.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("Empty Transcript", "The transcript is empty. Please add content before creating a referral.")
            return
            
        # Update status and display progress bar on referral click
        self.app.status_manager.progress("Analyzing transcript for possible conditions...")
        self.app.progress_bar.pack(side=RIGHT, padx=10)
        self.app.progress_bar.start()
        
        # Get suggested conditions asynchronously using CPU executor
        def get_conditions_task() -> str:
            try:
                # Use CPU executor for the condition analysis which is CPU-intensive
                future = self.app.io_executor.submit(get_possible_conditions, text)
                # Get result with timeout to prevent hanging
                return future.result(timeout=60) or ""
            except concurrent.futures.TimeoutError:
                logging.error("Condition analysis timed out")
                return ""
            except Exception as e:
                logging.error(f"Error analyzing conditions: {str(e)}", exc_info=True)
                return ""

        # Use I/O executor for the overall task management
        future = self.app.io_executor.submit(get_conditions_task)
        
        def on_conditions_done(future_result):
            try:
                suggestions = future_result.result()
                # Continue on the main thread
                self.app.after(0, lambda: self._create_referral_continued(suggestions))
            except Exception as e:
                error_msg = f"Failed to analyze conditions: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.app.after(0, lambda: [
                    self.app.status_manager.error(error_msg),
                    self.app.progress_bar.stop(),
                    self.app.progress_bar.pack_forget()
                ])

        future.add_done_callback(on_conditions_done)

    def _create_referral_continued(self, suggestions: str) -> None:
        """Continue referral creation process after condition analysis."""
        self.app.progress_bar.stop()
        self.app.progress_bar.pack_forget()
        
        conditions_list = [cond.strip() for cond in suggestions.split(",") if cond.strip()]
        
        # Use ask_conditions_dialog as an imported function
        focus = ask_conditions_dialog(self.app, "Select Conditions", "Select conditions to focus on:", conditions_list)
        
        if not focus:
            self.app.update_status("Referral cancelled or no conditions selected.", status_type="warning")
            return
        
        # Use "progress" status type to prevent auto-clearing for long-running operations
        self.app.status_manager.progress(f"Creating referral for conditions: {focus}...")
        self.app.progress_bar.pack(side=RIGHT, padx=10)
        self.app.progress_bar.start()
        self.app.referral_button.config(state=DISABLED)  # Disable button while processing
        
        def task() -> None:
            try:
                transcript = self.app.transcript_text.get("1.0", "end").strip()
                
                # Use our custom scheduler for status updates
                self.app.schedule_status_update(3000, f"Still generating referral for: {focus}...", "progress")
                self.app.schedule_status_update(10000, f"Processing referral (this may take a moment)...", "progress")
                
                # Log that we're waiting for result
                logging.info(f"Starting referral generation for conditions: {focus}")
                
                # Use CPU executor for the AI processing which is CPU-intensive
                future = self.app.io_executor.submit(create_referral_with_openai, transcript, focus)
                
                # Get result with a longer timeout to prevent hanging (5 minutes instead of 2)
                result = future.result(timeout=300)
                
                # Log the successful completion
                logging.info(f"Successfully generated referral for conditions: {focus}")
                
                # Check if result contains error message
                if result.startswith("Error creating referral:"):
                    raise Exception(result)
                    
                # Schedule UI update on the main thread
                self.app.after(0, lambda: [
                    self.app._update_text_area(result, f"Referral created for: {focus}", self.app.referral_button, self.app.referral_text),
                    self.app.notebook.select(2)  # Switch focus to Referral tab
                ])
            except concurrent.futures.TimeoutError:
                self.app.after(0, lambda: [
                    self.app.status_manager.error("Referral creation timed out. Please try again."),
                    self.app.referral_button.config(state=NORMAL),
                    self.app.progress_bar.stop(),
                    self.app.progress_bar.pack_forget()
                ])
            except Exception as e:
                error_msg = f"Error creating referral: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.app.after(0, lambda: [
                    self.app.status_manager.error(error_msg),
                    self.app.referral_button.config(state=NORMAL),
                    self.app.progress_bar.stop(),
                    self.app.progress_bar.pack_forget()
                ])
        
        # Actually submit the task to be executed
        self.app.io_executor.submit(task)

    def create_letter(self) -> None:
        """Create a letter from transcript with improved concurrency."""
        # Get source and specifications
        source, specs = self.app.show_letter_options_dialog()
        
        if source is None:  # User cancelled
            return
        
        # Get the appropriate text based on source
        if source == "transcript":
            text = self.app.transcript_text.get("1.0", "end").strip()
            source_name = "Transcript"
        else:  # source == "soap"
            text = self.app.soap_text.get("1.0", "end").strip()
            source_name = "SOAP"
        
        if not text:
            messagebox.showwarning("Empty Text", f"The {source_name} tab is empty. Please add content before creating a letter.")
            return
        
        # Show progress
        self.app.status_manager.progress(f"Generating letter from {source_name} text...")
        self.app.progress_bar.pack(side=RIGHT, padx=10)
        self.app.progress_bar.start()
        self.app.letter_button.config(state=DISABLED)
        
        def task() -> None:
            try:
                # Use our custom scheduler for status updates
                self.app.schedule_status_update(3000, f"Still generating letter from {source_name}...", "progress")
                self.app.schedule_status_update(10000, f"Processing letter (this may take a moment)...", "progress")
                
                # Log that we're starting letter generation
                logging.info(f"Starting letter generation from {source_name} with specs: {specs}")
                
                # Use CPU executor for the AI processing which is CPU-intensive
                future = self.app.io_executor.submit(create_letter_with_ai, text, specs)
                
                # Get result with a longer timeout to prevent hanging (5 minutes)
                result = future.result(timeout=300)
                
                # Log the successful completion
                logging.info("Successfully generated letter")
                
                # Check if result contains error message
                if result.startswith("Error creating letter:"):
                    raise Exception(result)
                
                # Schedule UI update on the main thread
                self.app.after(0, lambda: [
                    self.app._update_text_area(result, f"Letter generated from {source_name}", self.app.letter_button, self.app.letter_text),
                    self.app.notebook.select(3)  # Show letter in Letter tab (index 3)
                ])
                
                # Store the generated letter and recording ID for database update
                # We'll pass these to the main thread for database update
                generated_letter = result
                recording_id = self.app.current_recording_id
                
                # For database operations, schedule them on the main thread
                if recording_id:
                    # Schedule database update on main thread to avoid threading issues
                    self.app.after(0, lambda: self._save_letter_to_database(recording_id, generated_letter))
                        
            except concurrent.futures.TimeoutError:
                self.app.after(0, lambda: [
                    self.app.status_manager.error("Letter creation timed out. Please try again."),
                    self.app.letter_button.config(state=NORMAL),
                    self.app.progress_bar.stop(),
                    self.app.progress_bar.pack_forget()
                ])
            except Exception as e:
                error_msg = f"Error creating letter: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.app.after(0, lambda: [
                    self.app.status_manager.error(error_msg),
                    self.app.letter_button.config(state=NORMAL),
                    self.app.progress_bar.stop(),
                    self.app.progress_bar.pack_forget()
                ])
        
        # Actually submit the task to be executed
        self.app.io_executor.submit(task)

    def _save_letter_to_database(self, recording_id: int, letter_text: str) -> None:
        """Safely save letter to database from the main thread.
        
        Args:
            recording_id: ID of the recording to update
            letter_text: The generated letter text to save
        """
        try:
            # This runs on the main thread, so it's safe to use the database connection
            if self.app.db.update_recording(recording_id, letter=letter_text):
                logging.info(f"Saved letter to database for recording ID {recording_id}")
            else:
                logging.warning(f"Failed to save letter to database - no rows updated for ID {recording_id}")
        except Exception as db_error:
            error_msg = f"Error updating database: {str(db_error)}"
            logging.error(error_msg, exc_info=True)