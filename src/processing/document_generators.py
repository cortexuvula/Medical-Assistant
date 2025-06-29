"""
Document Generators Module

Handles the generation of medical documents including SOAP notes, referrals, 
letters, and diagnostic analyses from transcripts using AI processing.
"""

import logging
import concurrent.futures
from tkinter import messagebox
from tkinter.constants import DISABLED, NORMAL, RIGHT
from typing import Dict, Any, List, Callable, Optional

from ai.ai import create_soap_note_with_openai, create_referral_with_openai, get_possible_conditions, create_letter_with_ai
from ui.dialogs.dialogs import ask_conditions_dialog
from managers.agent_manager import agent_manager
from ai.agents import AgentTask, AgentType
from ui.dialogs.diagnostic_dialog import DiagnosticAnalysisDialog
from ui.dialogs.diagnostic_results_dialog import DiagnosticResultsDialog
from utils.progress_tracker import DocumentGenerationProgress, create_progress_callback


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
                # Create progress tracker
                progress_callback = create_progress_callback(self.app.status_manager)
                tracker = DocumentGenerationProgress.create_soap_tracker(progress_callback)
                
                # Step 1: Prepare transcript
                tracker.update("Preparing transcript...")
                context_text = self.app.context_text.get("1.0", "end").strip()
                
                # Step 2: Extract context
                tracker.update("Extracting context...")
                
                # Step 3: Generate SOAP sections
                tracker.update("Generating SOAP sections...")
                
                # Use IO executor for the AI API call (I/O-bound operation)
                future = self.app.io_executor.submit(
                    create_soap_note_with_openai,
                    transcript,
                    context_text
                )
                
                # Get result with timeout to prevent hanging
                result = future.result(timeout=120)
                
                # Step 4: Format output
                tracker.update("Formatting output...")
                
                # Step 5: Finalize
                tracker.update("Finalizing document...")
                
                # Store the values we need for database operations
                soap_note = result
                filename = "Transcript"
                
                # Schedule UI update on the main thread and save to database
                def update_ui_and_save():
                    self.app._update_text_area(soap_note, "SOAP note created", self.app.soap_button, self.app.soap_text)
                    self.app.notebook.select(1)  # Switch to SOAP tab
                    
                    # Check if we have an existing recording from file upload
                    if hasattr(self.app, 'current_recording_id') and self.app.current_recording_id:
                        # Update existing recording with SOAP note
                        success = self.app.db.update_recording(
                            self.app.current_recording_id,
                            soap_note=soap_note
                        )
                        if success:
                            logging.info(f"Updated existing recording {self.app.current_recording_id} with SOAP note")
                        else:
                            logging.error(f"Failed to update recording {self.app.current_recording_id} with SOAP note")
                    else:
                        # No existing recording, create a new one
                        self.app._save_soap_recording_to_database(filename, transcript, soap_note)
                    
                    # Check if diagnostic agent is enabled and offer to run analysis
                    if agent_manager.is_agent_enabled(AgentType.DIAGNOSTIC):
                        # Ask user if they want to run diagnostic analysis
                        if messagebox.askyesno(
                            "Run Diagnostic Analysis?",
                            "SOAP note created successfully.\n\n"
                            "Would you like to run diagnostic analysis on this SOAP note?",
                            parent=self.app
                        ):
                            # Run diagnostic analysis on the SOAP note
                            self.app.after(100, lambda: self._run_diagnostic_on_soap(soap_note))
                
                # Mark progress as complete
                tracker.complete("SOAP note created successfully")
                
                self.app.after(0, update_ui_and_save)
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
        # Reload settings to ensure we have the latest configuration
        from settings.settings import load_settings, SETTINGS
        latest_settings = load_settings()
        SETTINGS.update(latest_settings)
        
        # Reload agent manager to pick up latest settings
        agent_manager.reload_agents()
        
        # Check if referral agent is enabled
        if agent_manager.is_agent_enabled(AgentType.REFERRAL):
            # Use agent-based referral generation
            self._create_referral_with_agent()
            return
        
        # Otherwise, use the traditional method
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
                # Note: _update_text_area already handles database updates for letters
                self.app.after(0, lambda: [
                    self.app._update_text_area(result, f"Letter generated from {source_name}", self.app.letter_button, self.app.letter_text),
                    self.app.notebook.select(3)  # Show letter in Letter tab (index 3)
                ])
                        
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

    def create_diagnostic_analysis(self) -> None:
        """Create a diagnostic analysis from clinical findings."""
        # Reload settings to ensure we have the latest configuration
        from settings.settings import load_settings, SETTINGS
        latest_settings = load_settings()
        SETTINGS.update(latest_settings)
        
        # Reload agent manager to pick up latest settings
        agent_manager.reload_agents()
        
        # Check if diagnostic agent is enabled
        if not agent_manager.is_agent_enabled(AgentType.DIAGNOSTIC):
            messagebox.showwarning(
                "Diagnostic Agent Disabled", 
                "The Diagnostic Agent is currently disabled.\n\n"
                "Please enable it in Settings > Agent Settings to use diagnostic analysis."
            )
            return
        
        # Check for existing content to analyze
        transcript = self.app.transcript_text.get("1.0", "end").strip()
        soap_note = self.app.soap_text.get("1.0", "end").strip()
        
        if not transcript and not soap_note:
            messagebox.showwarning(
                "No Content", 
                "Please provide either a transcript or SOAP note for diagnostic analysis."
            )
            return
        
        # Show diagnostic analysis dialog
        dialog = DiagnosticAnalysisDialog(self.app)
        dialog.set_available_content(
            has_transcript=bool(transcript),
            has_soap=bool(soap_note)
        )
        
        result = dialog.show()
        if not result:
            return  # User cancelled
        
        source = result.get("source")
        custom_findings = result.get("custom_findings", "")
        
        # Determine what content to analyze
        if source == "custom" and custom_findings:
            clinical_findings = custom_findings
            source_name = "Custom Input"
        elif source == "soap":
            clinical_findings = None  # Will be extracted from SOAP
            input_data = {"soap_note": soap_note}
            source_name = "SOAP Note"
        else:  # transcript
            clinical_findings = transcript
            source_name = "Transcript"
        
        # Update status and show progress
        self.app.status_manager.progress("Analyzing clinical findings...")
        self.app.progress_bar.pack(side=RIGHT, padx=10)
        self.app.progress_bar.start()
        
        # Disable the diagnostic button during processing
        diagnostic_button = self.app.ui.components.get('generate_diagnostic_button')
        if diagnostic_button:
            diagnostic_button.config(state=DISABLED)
        
        def task() -> None:
            try:
                # Create agent task
                if clinical_findings:
                    task_data = AgentTask(
                        task_description=f"Analyze clinical findings from {source_name}",
                        input_data={"clinical_findings": clinical_findings}
                    )
                else:
                    task_data = AgentTask(
                        task_description=f"Analyze SOAP note for diagnostic insights",
                        input_data=input_data
                    )
                
                # Execute diagnostic analysis
                response = agent_manager.execute_agent_task(AgentType.DIAGNOSTIC, task_data)
                
                if response and response.success:
                    # Schedule UI update on main thread
                    self.app.after(0, lambda: self._update_diagnostic_display(
                        response.result, 
                        source_name,
                        response.metadata
                    ))
                else:
                    error_msg = response.error if response else "Unknown error"
                    raise Exception(error_msg)
                    
            except Exception as e:
                error_msg = f"Error creating diagnostic analysis: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.app.after(0, lambda: [
                    self.app.status_manager.error(error_msg),
                    diagnostic_button.config(state=NORMAL) if diagnostic_button else None,
                    self.app.progress_bar.stop(),
                    self.app.progress_bar.pack_forget()
                ])
        
        # Submit task for execution
        self.app.io_executor.submit(task)
    
    def _update_diagnostic_display(self, analysis: str, source: str, metadata: dict) -> None:
        """Update the UI with diagnostic analysis results."""
        # Stop progress bar
        self.app.progress_bar.stop()
        self.app.progress_bar.pack_forget()
        
        # Re-enable diagnostic button
        diagnostic_button = self.app.ui.components.get('generate_diagnostic_button')
        if diagnostic_button:
            diagnostic_button.config(state=NORMAL)
        
        # Show results in a dialog
        dialog = DiagnosticResultsDialog(self.app)
        dialog.show_results(analysis, source, metadata)
        
        # Update status
        diff_count = metadata.get('differential_count', 0)
        has_red_flags = metadata.get('has_red_flags', False)
        status_msg = f"Diagnostic analysis completed: {diff_count} differentials"
        if has_red_flags:
            status_msg += " (RED FLAGS identified)"
        
        self.app.status_manager.success(status_msg)
    
    def _run_diagnostic_on_soap(self, soap_note: str) -> None:
        """Run diagnostic analysis on a SOAP note.
        
        Args:
            soap_note: The SOAP note text to analyze
        """
        # Update status and show progress
        self.app.status_manager.progress("Running diagnostic analysis on SOAP note...")
        self.app.progress_bar.pack(side=RIGHT, padx=10)
        self.app.progress_bar.start()
        
        def task() -> None:
            try:
                # Create agent task for SOAP analysis
                task_data = AgentTask(
                    task_description="Analyze SOAP note for diagnostic insights",
                    input_data={"soap_note": soap_note}
                )
                
                # Execute diagnostic analysis
                response = agent_manager.execute_agent_task(AgentType.DIAGNOSTIC, task_data)
                
                if response and response.success:
                    # Schedule UI update on main thread
                    self.app.after(0, lambda: self._update_diagnostic_display(
                        response.result, 
                        "SOAP Note (Auto-Analysis)",
                        response.metadata
                    ))
                else:
                    error_msg = response.error if response else "Unknown error"
                    raise Exception(error_msg)
                    
            except Exception as e:
                error_msg = f"Error running diagnostic analysis: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.app.after(0, lambda: [
                    self.app.status_manager.error(error_msg),
                    self.app.progress_bar.stop(),
                    self.app.progress_bar.pack_forget()
                ])
        
        # Submit task for execution
        self.app.io_executor.submit(task)

    
    def analyze_medications(self) -> None:
        """Analyze medications from clinical content."""
        # Reload settings to ensure we have the latest configuration
        from settings.settings import load_settings, SETTINGS
        latest_settings = load_settings()
        SETTINGS.update(latest_settings)
        
        # Reload agent manager to pick up latest settings
        agent_manager.reload_agents()
        
        # Check if medication agent is enabled
        if not agent_manager.is_agent_enabled(AgentType.MEDICATION):
            messagebox.showwarning(
                "Medication Agent Disabled", 
                "The Medication Agent is currently disabled.\n\n"
                "Please enable it in Settings > Agent Settings to use medication analysis."
            )
            return
        
        # Check for existing content to analyze
        transcript = self.app.transcript_text.get("1.0", "end").strip()
        soap_note = self.app.soap_text.get("1.0", "end").strip()
        context_text = self.app.context_text.get("1.0", "end").strip()
        
        if not transcript and not soap_note and not context_text:
            messagebox.showwarning(
                "No Content", 
                "Please provide either a transcript, SOAP note, or context information for medication analysis."
            )
            return
        
        # Import dialogs here to avoid circular imports
        from ui.dialogs.medication_analysis_dialog import MedicationAnalysisDialog
        from ui.dialogs.medication_results_dialog import MedicationResultsDialog
        
        # Show medication analysis dialog
        dialog = MedicationAnalysisDialog(self.app)
        dialog.set_available_content(
            has_transcript=bool(transcript),
            has_soap=bool(soap_note),
            has_context=bool(context_text)
        )
        
        result = dialog.show()
        if not result:
            return  # User cancelled
        
        analysis_type = result.get("analysis_type")
        source = result.get("source")
        custom_medications = result.get("custom_medications", "")
        
        # Determine content based on source
        if source == "custom" and custom_medications:
            content = custom_medications
            source_name = "Custom Input"
        elif source == "soap":
            content = soap_note
            source_name = "SOAP Note"
        elif source == "context":
            content = context_text
            source_name = "Context Information"
        else:  # transcript
            content = transcript
            source_name = "Transcript"
        
        # Update status and show progress
        self.app.status_manager.progress(f"Analyzing medications from {source_name}...")
        self.app.progress_bar.pack(side=RIGHT, padx=10)
        self.app.progress_bar.start()
        
        # Disable the medication button during processing
        medication_button = self.app.ui.components.get('generate_medication_button')
        if medication_button:
            medication_button.config(state=DISABLED)
        
        def task() -> None:
            try:
                # Build task description based on analysis type
                task_descriptions = {
                    "extract": "Extract medications from text",
                    "interactions": "Check medication interactions",
                    "dosing": "Validate medication dosing",
                    "alternatives": "Suggest medication alternatives",
                    "prescription": "Generate prescription",
                    "comprehensive": "Comprehensive medication analysis"
                }
                
                task_description = task_descriptions.get(analysis_type, "Analyze medications")
                
                # Create agent task with properly mapped input data
                input_data = {
                    "clinical_text": content,  # Medication agent expects clinical_text
                    "source": source_name,
                    "analysis_type": analysis_type
                }
                
                # For comprehensive analysis, try to parse medications if they look like a list
                if analysis_type == "comprehensive" and "\n" in content:
                    lines = content.strip().split("\n")
                    medication_lines = [line.strip() for line in lines if line.strip()]
                    # If it looks like a medication list, add as current_medications
                    if medication_lines and any(mg in content.lower() for mg in ["mg", "ml", "tablet", "daily"]):
                        input_data["current_medications"] = medication_lines
                
                task_data = AgentTask(
                    task_description=task_description,
                    input_data=input_data
                )
                
                # Execute medication analysis
                response = agent_manager.execute_agent_task(AgentType.MEDICATION, task_data)
                
                if response and response.success:
                    # Schedule UI update on main thread
                    self.app.after(0, lambda: self._update_medication_display(
                        response.result,
                        analysis_type,
                        source_name,
                        response.metadata
                    ))
                else:
                    error_msg = response.error if response else "Unknown error"
                    raise Exception(error_msg)
                    
            except Exception as e:
                error_msg = f"Error analyzing medications: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.app.after(0, lambda: [
                    self.app.status_manager.error(error_msg),
                    self.app.progress_bar.stop(),
                    self.app.progress_bar.pack_forget(),
                    medication_button.config(state=NORMAL) if medication_button else None
                ])
        
        # Submit task for execution
        self.app.io_executor.submit(task)
    
    def _update_medication_display(self, analysis: dict, analysis_type: str, source: str, metadata: dict) -> None:
        """Update UI with medication analysis results."""
        # Hide progress
        self.app.progress_bar.stop()
        self.app.progress_bar.pack_forget()
        
        # Re-enable medication button
        medication_button = self.app.ui.components.get('generate_medication_button')
        if medication_button:
            medication_button.config(state=NORMAL)
        
        # Import here to avoid circular imports
        from ui.dialogs.medication_results_dialog import MedicationResultsDialog
        
        # Show results in a dialog
        dialog = MedicationResultsDialog(self.app)
        dialog.show_results(analysis, analysis_type, source, metadata)
        
        # Update status
        med_count = metadata.get('medication_count', 0)
        interaction_count = metadata.get('interaction_count', 0)
        
        status_msg = f"Medication analysis completed: {med_count} medications"
        if interaction_count > 0:
            status_msg += f", {interaction_count} interactions found"
        
        self.app.status_manager.success(status_msg)
    
    def _create_referral_with_agent(self) -> None:
        """Create a referral using the referral agent."""
        # Check for existing content to analyze
        transcript = self.app.transcript_text.get("1.0", "end").strip()
        soap_note = self.app.soap_text.get("1.0", "end").strip()
        
        if not transcript and not soap_note:
            messagebox.showwarning(
                "No Content", 
                "Please provide either a transcript or SOAP note for referral generation."
            )
            return
        
        # Get suggested conditions for the referral
        self.app.status_manager.progress("Analyzing content for referral conditions...")
        self.app.progress_bar.pack(side=RIGHT, padx=10)
        self.app.progress_bar.start()
        
        # Prefer SOAP note if available
        source_text = soap_note if soap_note else transcript
        source_name = "SOAP Note" if soap_note else "Transcript"
        
        def get_conditions_task() -> str:
            try:
                # Use existing function to get possible conditions
                future = self.app.io_executor.submit(get_possible_conditions, source_text)
                return future.result(timeout=60) or ""
            except Exception as e:
                logging.error(f"Error analyzing conditions: {str(e)}")
                return ""
        
        future = self.app.io_executor.submit(get_conditions_task)
        
        def on_conditions_done(future_result):
            try:
                suggestions = future_result.result()
                self.app.after(0, lambda: self._create_referral_with_agent_continued(
                    source_text, source_name, suggestions, soap_note is not None
                ))
            except Exception as e:
                error_msg = f"Failed to analyze conditions: {str(e)}"
                logging.error(error_msg)
                self.app.after(0, lambda: [
                    self.app.status_manager.error(error_msg),
                    self.app.progress_bar.stop(),
                    self.app.progress_bar.pack_forget()
                ])
        
        future.add_done_callback(on_conditions_done)
    
    def _create_referral_with_agent_continued(self, source_text: str, source_name: str, 
                                              suggestions: str, is_soap: bool) -> None:
        """Continue referral creation with agent after condition analysis."""
        self.app.progress_bar.stop()
        self.app.progress_bar.pack_forget()
        
        conditions_list = [cond.strip() for cond in suggestions.split(",") if cond.strip()]
        
        # Use ask_conditions_dialog to select conditions
        focus = ask_conditions_dialog(self.app, "Select Conditions", 
                                       "Select conditions to focus on:", conditions_list)
        
        if not focus:
            self.app.update_status("Referral cancelled or no conditions selected.", 
                                   status_type="warning")
            return
        
        # Update status
        self.app.status_manager.progress(f"Generating referral for: {focus}...")
        self.app.progress_bar.pack(side=RIGHT, padx=10)
        self.app.progress_bar.start()
        
        # Disable referral button
        self.app.referral_button.config(state=DISABLED)
        
        def task() -> None:
            try:
                # Create agent task
                input_data = {
                    "conditions": focus
                }
                
                if is_soap:
                    input_data["soap_note"] = source_text
                else:
                    input_data["transcript"] = source_text
                
                task_data = AgentTask(
                    task_description=f"Generate referral letter from {source_name} for conditions: {focus}",
                    input_data=input_data
                )
                
                # Execute referral generation
                response = agent_manager.execute_agent_task(AgentType.REFERRAL, task_data)
                
                if response and response.success:
                    # Schedule UI update on main thread
                    self.app.after(0, lambda: self._update_referral_display(
                        response.result,
                        focus,
                        source_name,
                        response.metadata
                    ))
                else:
                    error_msg = response.error if response else "Unknown error"
                    raise Exception(error_msg)
                    
            except Exception as e:
                error_msg = f"Error creating referral: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.app.after(0, lambda: [
                    self.app.status_manager.error(error_msg),
                    self.app.referral_button.config(state=NORMAL),
                    self.app.progress_bar.stop(),
                    self.app.progress_bar.pack_forget()
                ])
        
        # Submit task for execution
        self.app.io_executor.submit(task)
    
    def _update_referral_display(self, referral_text: str, conditions: str, 
                                 source: str, metadata: dict) -> None:
        """Update UI with referral agent results."""
        # Stop progress bar
        self.app.progress_bar.stop()
        self.app.progress_bar.pack_forget()
        
        # Re-enable referral button
        self.app.referral_button.config(state=NORMAL)
        
        # Update text area
        self.app._update_text_area(
            referral_text, 
            f"Referral created for: {conditions}", 
            self.app.referral_button, 
            self.app.referral_text
        )
        
        # Switch to referral tab
        self.app.notebook.select(2)
        
        # Update status with metadata
        urgency = metadata.get('urgency_level', 'standard')
        specialty = metadata.get('specialty', 'N/A')
        status_msg = f"Referral generated from {source}"
        if urgency != 'standard':
            status_msg += f" (Urgency: {urgency.upper()})"
        if specialty != 'N/A':
            status_msg += f" - {specialty}"
        
        self.app.status_manager.success(status_msg)
    
    def extract_clinical_data(self) -> None:
        """Extract structured clinical data using the data extraction agent."""
        # Reload settings to ensure we have the latest configuration
        from settings.settings import load_settings, SETTINGS
        latest_settings = load_settings()
        SETTINGS.update(latest_settings)
        
        # Reload agent manager to pick up latest settings
        agent_manager.reload_agents()
        
        # Check if data extraction agent is enabled
        if not agent_manager.is_agent_enabled(AgentType.DATA_EXTRACTION):
            messagebox.showwarning(
                "Data Extraction Agent Disabled", 
                "The Data Extraction Agent is currently disabled.\n\n"
                "Please enable it in Settings > Agent Settings to use data extraction."
            )
            return
        
        # Check for existing content to analyze
        transcript = self.app.transcript_text.get("1.0", "end").strip()
        soap_note = self.app.soap_text.get("1.0", "end").strip()
        context_text = self.app.context_text.get("1.0", "end").strip()
        
        if not transcript and not soap_note and not context_text:
            messagebox.showwarning(
                "No Content", 
                "Please provide either a transcript, SOAP note, or context information for data extraction."
            )
            return
        
        # Import dialogs here to avoid circular imports
        from ui.dialogs.data_extraction_dialog import DataExtractionDialog
        from ui.dialogs.data_extraction_results_dialog import DataExtractionResultsDialog
        
        # Show data extraction dialog
        dialog = DataExtractionDialog(self.app)
        dialog.set_available_content(
            has_transcript=bool(transcript),
            has_soap=bool(soap_note),
            has_context=bool(context_text)
        )
        
        result = dialog.show()
        if not result:
            return  # User cancelled
        
        extraction_type = result.get("extraction_type", "comprehensive")
        source = result.get("source")
        output_format = result.get("output_format", "structured_text")
        
        # Determine content based on source
        if source == "soap":
            content = soap_note
            source_name = "SOAP Note"
        elif source == "context":
            content = context_text
            source_name = "Context Information"
        else:  # transcript
            content = transcript
            source_name = "Transcript"
        
        # Update status and show progress
        self.app.status_manager.progress(f"Extracting clinical data from {source_name}...")
        self.app.progress_bar.pack(side=RIGHT, padx=10)
        self.app.progress_bar.start()
        
        # Disable the data extraction button during processing
        data_extraction_button = self.app.ui.components.get('generate_data_extraction_button')
        if data_extraction_button:
            data_extraction_button.config(state=DISABLED)
        
        def task() -> None:
            try:
                # Build task description based on extraction type
                task_descriptions = {
                    "comprehensive": "Extract all clinical data",
                    "vitals": "Extract vital signs",
                    "labs": "Extract laboratory values",
                    "medications": "Extract medications",
                    "diagnoses": "Extract diagnoses with ICD codes",
                    "procedures": "Extract procedures and interventions"
                }
                
                task_description = task_descriptions.get(extraction_type, "Extract clinical data")
                
                # Create agent task
                input_data = {
                    "clinical_text": content,
                    "source": source_name,
                    "extraction_type": extraction_type,
                    "output_format": output_format
                }
                
                task_data = AgentTask(
                    task_description=task_description,
                    input_data=input_data
                )
                
                # Execute data extraction
                response = agent_manager.execute_agent_task(AgentType.DATA_EXTRACTION, task_data)
                
                if response and response.success:
                    # Schedule UI update on main thread
                    self.app.after(0, lambda: self._update_data_extraction_display(
                        response.result,
                        extraction_type,
                        source_name,
                        output_format,
                        response.metadata
                    ))
                else:
                    error_msg = response.error if response else "Unknown error"
                    raise Exception(error_msg)
                    
            except Exception as e:
                error_msg = f"Error extracting clinical data: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.app.after(0, lambda: [
                    self.app.status_manager.error(error_msg),
                    self.app.progress_bar.stop(),
                    self.app.progress_bar.pack_forget(),
                    data_extraction_button.config(state=NORMAL) if data_extraction_button else None
                ])
        
        # Submit task for execution
        self.app.io_executor.submit(task)
    
    def _update_data_extraction_display(self, extracted_data: str, extraction_type: str, 
                                        source: str, output_format: str, metadata: dict) -> None:
        """Update UI with data extraction results."""
        # Hide progress
        self.app.progress_bar.stop()
        self.app.progress_bar.pack_forget()
        
        # Re-enable data extraction button
        data_extraction_button = self.app.ui.components.get('generate_data_extraction_button')
        if data_extraction_button:
            data_extraction_button.config(state=NORMAL)
        
        # Import here to avoid circular imports
        from ui.dialogs.data_extraction_results_dialog import DataExtractionResultsDialog
        
        # Show results in a dialog
        dialog = DataExtractionResultsDialog(self.app)
        dialog.show_results(extracted_data, extraction_type, source, output_format, metadata)
        
        # Update status
        counts = metadata.get('counts', {})
        total_count = counts.get('total', 0)
        
        status_msg = f"Data extraction completed: {total_count} items extracted"
        if extraction_type != 'comprehensive':
            specific_count = counts.get(extraction_type, 0)
            status_msg = f"Extracted {specific_count} {extraction_type.replace('_', ' ')}"
        
        self.app.status_manager.success(status_msg)
    
    def manage_workflow(self) -> None:
        """Manage clinical workflows using the workflow agent."""
        # Reload settings to ensure we have the latest configuration
        from settings.settings import load_settings, SETTINGS
        latest_settings = load_settings()
        SETTINGS.update(latest_settings)
        
        # Reload agent manager to pick up latest settings
        agent_manager.reload_agents()
        
        # Check if workflow agent is enabled
        if not agent_manager.is_agent_enabled(AgentType.WORKFLOW):
            messagebox.showwarning(
                "Workflow Agent Disabled", 
                "The Workflow Agent is currently disabled.\n\n"
                "Please enable it in Settings > Agent Settings to use clinical workflows."
            )
            return
        
        # Import dialogs here to avoid circular imports
        from ui.dialogs.workflow_dialog import WorkflowDialog
        from ui.dialogs.workflow_results_dialog import WorkflowResultsDialog
        
        # Show workflow configuration dialog
        dialog = WorkflowDialog(self.app)
        result = dialog.show()
        
        if not result:
            return  # User cancelled
        
        # Extract configuration
        workflow_type = result.get("workflow_type", "general")
        patient_info = result.get("patient_info", {})
        clinical_context = result.get("clinical_context", "")
        options = result.get("options", {})
        
        # Update status and show progress
        workflow_name = workflow_type.replace('_', ' ').title()
        self.app.status_manager.progress(f"Generating {workflow_name} workflow...")
        self.app.progress_bar.pack(side=RIGHT, padx=10)
        self.app.progress_bar.start()
        
        # Disable the workflow button during processing
        workflow_button = self.app.ui.components.get('generate_workflow_button')
        if workflow_button:
            workflow_button.config(state=DISABLED)
        
        def task() -> None:
            try:
                # Prepare context including any existing content
                context_parts = []
                
                # Add clinical context from dialog
                if clinical_context:
                    context_parts.append(f"Clinical Details: {clinical_context}")
                
                # Add patient concern if specified
                if patient_info.get('primary_concern'):
                    context_parts.append(f"Primary Concern: {patient_info['primary_concern']}")
                
                # Check for existing SOAP note or transcript
                soap_note = self.app.soap_text.get("1.0", "end").strip()
                transcript = self.app.transcript_text.get("1.0", "end").strip()
                
                if soap_note:
                    context_parts.append(f"SOAP Note Available: Yes")
                if transcript:
                    context_parts.append(f"Transcript Available: Yes")
                
                full_context = "\n".join(context_parts) if context_parts else None
                
                # Create agent task
                task_data = AgentTask(
                    task_description=f"Create {workflow_name} workflow",
                    context=full_context,
                    input_data={
                        "workflow_type": workflow_type,
                        "clinical_context": clinical_context,
                        "patient_info": patient_info,
                        "workflow_state": {},
                        "options": options
                    }
                )
                
                # Execute workflow generation
                response = agent_manager.execute_agent_task(AgentType.WORKFLOW, task_data)
                
                if response and response.success:
                    # Schedule UI update on main thread
                    self.app.after(0, lambda: self._update_workflow_display(
                        response.result,
                        workflow_type,
                        patient_info,
                        response.metadata
                    ))
                else:
                    error_msg = response.error if response else "Unknown error"
                    raise Exception(error_msg)
                    
            except Exception as e:
                error_msg = f"Error creating workflow: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.app.after(0, lambda: [
                    self.app.status_manager.error(error_msg),
                    self.app.progress_bar.stop(),
                    self.app.progress_bar.pack_forget(),
                    workflow_button.config(state=NORMAL) if workflow_button else None
                ])
        
        # Submit task for execution
        self.app.io_executor.submit(task)
    
    def _update_workflow_display(self, workflow_text: str, workflow_type: str,
                                 patient_info: Dict[str, Any], metadata: dict) -> None:
        """Update UI with workflow results."""
        # Hide progress
        self.app.progress_bar.stop()
        self.app.progress_bar.pack_forget()
        
        # Re-enable workflow button
        workflow_button = self.app.ui.components.get('generate_workflow_button')
        if workflow_button:
            workflow_button.config(state=NORMAL)
        
        # Import here to avoid circular imports
        from ui.dialogs.workflow_results_dialog import WorkflowResultsDialog
        
        # Show results in dialog
        dialog = WorkflowResultsDialog(self.app)
        dialog.show_results(workflow_text, workflow_type, patient_info, metadata)
        
        # Update status
        workflow_name = workflow_type.replace('_', ' ').title()
        total_steps = metadata.get('total_steps', 0)
        duration = metadata.get('estimated_duration', 'Unknown')
        
        status_msg = f"{workflow_name} workflow generated: {total_steps} steps"
        if duration != 'Unknown':
            status_msg += f" (~{duration})"
        
        self.app.status_manager.success(status_msg)
    
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