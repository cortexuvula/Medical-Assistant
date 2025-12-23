"""
Document Generators Module

Handles the generation of medical documents including SOAP notes, referrals,
letters, and diagnostic analyses from transcripts using AI processing.

Batch processing functionality is in processing/batch_processor.py.
"""

import logging
import concurrent.futures
from tkinter import messagebox
from tkinter.constants import DISABLED, NORMAL, RIGHT
from typing import Dict, Any, List, Callable, Optional

from ai.ai import create_soap_note_with_openai, create_referral_with_openai, get_possible_conditions, create_letter_with_ai
from ui.dialogs.dialogs import ask_conditions_dialog
from ui.dialogs.referral_options_dialog import ReferralOptionsDialog
from managers.recipient_manager import get_recipient_manager
from managers.agent_manager import agent_manager
from ai.agents import AgentTask, AgentType
from ui.dialogs.diagnostic_dialog import DiagnosticAnalysisDialog
from ui.dialogs.diagnostic_results_dialog import DiagnosticResultsDialog
from utils.progress_tracker import DocumentGenerationProgress, create_progress_callback
from utils.error_handling import AsyncUIErrorHandler, ErrorContext
from processing.batch_processor import BatchProcessor


class DocumentGenerators:
    """Manages medical document generation functionality.

    Batch processing methods are delegated to BatchProcessor.
    """

    def __init__(self, parent_app):
        """Initialize the document generators.

        Args:
            parent_app: The main application instance
        """
        self.app = parent_app
        self._batch_processor = None

    @property
    def batch_processor(self) -> BatchProcessor:
        """Get or create the batch processor instance."""
        if self._batch_processor is None:
            self._batch_processor = BatchProcessor(self.app)
        return self._batch_processor

    def process_batch_recordings(self, recording_ids: List[int], options: Dict[str, Any],
                                 on_complete: Callable = None, on_progress: Callable = None) -> None:
        """Process multiple recordings in batch. Delegates to BatchProcessor."""
        self.batch_processor.process_batch_recordings(recording_ids, options, on_complete, on_progress)

    def process_batch_files(self, file_paths: List[str], options: Dict[str, Any],
                            on_complete: Callable = None, on_progress: Callable = None) -> None:
        """Process multiple audio files in batch. Delegates to BatchProcessor."""
        self.batch_processor.process_batch_files(file_paths, options, on_complete, on_progress)
        
    def create_soap_note(self) -> None:
        """Create a SOAP note from the selected text using AI with improved concurrency."""
        transcript = self.app.transcript_text.get("1.0", "end").strip()
        if not transcript:
            messagebox.showwarning("Create SOAP Note", "There is no transcript to process.")
            return

        # Create error handler for this operation
        error_handler = AsyncUIErrorHandler(
            self.app,
            button=self.app.soap_button,
            progress_bar=self.app.progress_bar,
            operation_name="Creating SOAP note"
        )
        error_handler.start()

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
                    self.app.soap_text.focus_set()  # Give focus to SOAP text widget

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

                error_handler.complete(callback=update_ui_and_save)
            except concurrent.futures.TimeoutError:
                error_handler.fail("SOAP note creation timed out. Please try again.")
            except Exception as e:
                error_handler.fail(e)

        # Use I/O executor for task management since it involves UI coordination
        self.app.io_executor.submit(task)

    def create_referral(self) -> None:
        """Create a referral from transcript or SOAP note using the referral agent.

        This method always uses the agent-based referral generation for consistent,
        high-quality output with specialty inference and condition filtering.
        """
        # Reload settings to ensure we have the latest configuration
        from settings.settings import load_settings, SETTINGS
        latest_settings = load_settings()
        SETTINGS.update(latest_settings)

        # Reload agent manager to pick up latest settings
        agent_manager.reload_agents()

        # Always use agent-based referral generation
        self._create_referral_with_agent()

    def create_letter(self) -> None:
        """Create a letter from transcript with improved concurrency."""
        # Get source, recipient type, and specifications
        source, recipient_type, specs = self.app.show_letter_options_dialog()

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

        # Get recipient type display name for status messages
        recipient_names = {
            "insurance": "Insurance Company",
            "employer": "Employer",
            "specialist": "Specialist",
            "patient": "Patient",
            "school": "School",
            "legal": "Legal/Attorney",
            "government": "Government Agency",
            "other": "Other"
        }
        recipient_display = recipient_names.get(recipient_type, "recipient")

        # Create error handler for this operation
        error_handler = AsyncUIErrorHandler(
            self.app,
            button=self.app.letter_button,
            progress_bar=self.app.progress_bar,
            operation_name=f"Generating letter to {recipient_display}"
        )
        error_handler.start()

        def task() -> None:
            try:
                # Use our custom scheduler for status updates
                self.app.schedule_status_update(3000, f"Still generating letter to {recipient_display}...", "progress")
                self.app.schedule_status_update(10000, f"Processing letter (this may take a moment)...", "progress")

                # Log that we're starting letter generation
                logging.info(f"Starting letter generation from {source_name} to {recipient_type} with specs: {specs}")

                # Use IO executor for the AI processing
                future = self.app.io_executor.submit(create_letter_with_ai, text, recipient_type, specs)

                # Get result with a longer timeout to prevent hanging (5 minutes)
                result = future.result(timeout=300)

                # Log the successful completion
                logging.info(f"Successfully generated letter to {recipient_type}")

                # Check if result contains error message
                if result.startswith("Error creating letter:"):
                    raise Exception(result)

                # Schedule UI update on the main thread
                def update_ui():
                    self.app._update_text_area(
                        result,
                        f"Letter to {recipient_display} generated from {source_name}",
                        self.app.letter_button,
                        self.app.letter_text
                    )
                    self.app.notebook.select(3)  # Show letter in Letter tab (index 3)

                error_handler.complete(callback=update_ui, success_message=f"Letter to {recipient_display} generated")

            except concurrent.futures.TimeoutError:
                error_handler.fail("Letter creation timed out. Please try again.")
            except Exception as e:
                error_handler.fail(e)

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
        
        # Get the diagnostic button for error handler
        diagnostic_button = self.app.ui.components.get('generate_diagnostic_button')

        # Create error handler for this operation
        error_handler = AsyncUIErrorHandler(
            self.app,
            button=diagnostic_button,
            progress_bar=self.app.progress_bar,
            operation_name="Analyzing clinical findings"
        )
        error_handler.start()

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
                    error_handler.complete(
                        callback=lambda: self._update_diagnostic_display(
                            response.result,
                            source_name,
                            response.metadata
                        )
                    )
                else:
                    error_msg = response.error if response else "Unknown error"
                    # Capture detailed error context
                    ctx = ErrorContext.capture(
                        operation="Diagnostic analysis",
                        error_message=error_msg,
                        error_code="DIAGNOSTIC_FAILED",
                        input_summary=f"Source: {source_name}, Input length: {len(clinical_findings) if clinical_findings else 'N/A'}",
                        agent_type="DIAGNOSTIC",
                        response_metadata=response.metadata if response else None
                    )
                    ctx.log()
                    raise Exception(ctx.user_message)

            except Exception as e:
                # Capture error context if not already captured
                if not isinstance(e.args[0], str) or "failed:" not in str(e):
                    ctx = ErrorContext.capture(
                        operation="Diagnostic analysis",
                        exception=e,
                        error_code="DIAGNOSTIC_ERROR",
                        input_summary=f"Source: {source_name}"
                    )
                    ctx.log()
                    error_handler.fail(ctx.user_message)
                else:
                    error_handler.fail(e)

        # Submit task for execution
        self.app.io_executor.submit(task)
    
    def _update_diagnostic_display(self, analysis: str, source: str, metadata: dict) -> None:
        """Update the UI with diagnostic analysis results.

        Note: Progress bar and button state are handled by AsyncUIErrorHandler.
        """
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
        # Create error handler for this operation
        error_handler = AsyncUIErrorHandler(
            self.app,
            button=None,  # No button to disable for auto-analysis
            progress_bar=self.app.progress_bar,
            operation_name="Running diagnostic analysis on SOAP note"
        )
        error_handler.start()

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
                    error_handler.complete(
                        callback=lambda: self._update_diagnostic_display(
                            response.result,
                            "SOAP Note (Auto-Analysis)",
                            response.metadata
                        )
                    )
                else:
                    error_msg = response.error if response else "Unknown error"
                    raise Exception(error_msg)

            except Exception as e:
                error_handler.fail(e)

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
        
        # Get the medication button for error handler
        medication_button = self.app.ui.components.get('generate_medication_button')

        # Create error handler for this operation
        error_handler = AsyncUIErrorHandler(
            self.app,
            button=medication_button,
            progress_bar=self.app.progress_bar,
            operation_name=f"Analyzing medications from {source_name}"
        )
        error_handler.start()

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
                    error_handler.complete(
                        callback=lambda: self._update_medication_display(
                            response.result,
                            analysis_type,
                            source_name,
                            response.metadata
                        )
                    )
                else:
                    error_msg = response.error if response else "Unknown error"
                    # Capture detailed error context
                    ctx = ErrorContext.capture(
                        operation="Medication analysis",
                        error_message=error_msg,
                        error_code="MEDICATION_FAILED",
                        input_summary=f"Source: {source_name}, Type: {analysis_type}, Input length: {len(content)}",
                        agent_type="MEDICATION",
                        analysis_type=analysis_type
                    )
                    ctx.log()
                    raise Exception(ctx.user_message)

            except Exception as e:
                # Capture error context if not already captured
                if not isinstance(e.args[0], str) or "failed:" not in str(e):
                    ctx = ErrorContext.capture(
                        operation="Medication analysis",
                        exception=e,
                        error_code="MEDICATION_ERROR",
                        input_summary=f"Source: {source_name}, Type: {analysis_type}"
                    )
                    ctx.log()
                    error_handler.fail(ctx.user_message)
                else:
                    error_handler.fail(e)

        # Submit task for execution
        self.app.io_executor.submit(task)

    def _update_medication_display(self, analysis: dict, analysis_type: str, source: str, metadata: dict) -> None:
        """Update UI with medication analysis results.

        Note: Progress bar and button state are handled by AsyncUIErrorHandler.
        """
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
        """Create a referral using the referral agent with options dialog."""
        # Check for existing content to analyze
        transcript = self.app.transcript_text.get("1.0", "end").strip()
        soap_note = self.app.soap_text.get("1.0", "end").strip()
        context_text = self.app.context_text.get("1.0", "end").strip() if hasattr(self.app, 'context_text') else ""

        if not transcript and not soap_note and not context_text:
            messagebox.showwarning(
                "No Content",
                "Please provide a transcript, SOAP note, or context for referral generation."
            )
            return

        # Get suggested conditions for the referral
        self.app.status_manager.progress("Analyzing content for referral conditions...")
        self.app.progress_bar.pack(side=RIGHT, padx=10)
        self.app.progress_bar.start()

        # Prefer SOAP note if available, then transcript, then context
        if soap_note:
            source_text = soap_note
        elif transcript:
            source_text = transcript
        else:
            source_text = context_text

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
                self.app.after(0, lambda: self._show_referral_options_dialog(
                    suggestions,
                    has_transcript=bool(transcript),
                    has_soap=bool(soap_note),
                    has_context=bool(context_text)
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

    def _show_referral_options_dialog(self, suggestions: str, has_transcript: bool,
                                       has_soap: bool, has_context: bool) -> None:
        """Show the referral options dialog with extracted conditions."""
        self.app.progress_bar.stop()
        self.app.progress_bar.pack_forget()

        conditions_list = [cond.strip() for cond in suggestions.split(",") if cond.strip()]

        # Infer specialty from conditions
        from ai.agents.referral import ReferralAgent
        temp_agent = ReferralAgent()
        inferred_specialty = temp_agent._infer_specialty_from_conditions(suggestions) or ""

        # Get saved recipients
        recipient_manager = get_recipient_manager()
        saved_recipients = recipient_manager.get_all_recipients()

        # Create and show the options dialog
        dialog = ReferralOptionsDialog(self.app)
        dialog.set_available_content(has_transcript, has_soap, has_context)
        dialog.set_conditions(conditions_list, inferred_specialty)
        dialog.set_saved_recipients(saved_recipients)

        result = dialog.show()

        if not result:
            self.app.update_status("Referral generation cancelled.", status_type="warning")
            return

        # Process the dialog result
        self._generate_referral_from_options(result)

    def _generate_referral_from_options(self, options: Dict[str, Any]) -> None:
        """Generate referral based on dialog options."""
        # Get source text based on selection
        source = options.get("source", "soap")
        if source == "soap":
            source_text = self.app.soap_text.get("1.0", "end").strip()
            source_name = "SOAP Note"
            is_soap = True
        elif source == "transcript":
            source_text = self.app.transcript_text.get("1.0", "end").strip()
            source_name = "Transcript"
            is_soap = False
        else:  # context
            source_text = self.app.context_text.get("1.0", "end").strip() if hasattr(self.app, 'context_text') else ""
            source_name = "Context"
            is_soap = False

        if not source_text:
            messagebox.showwarning("No Content", f"The selected source ({source_name}) is empty.")
            return

        conditions_text = options.get("conditions_text", "")
        recipient_type = options.get("recipient_type", "specialist")
        urgency = options.get("urgency", "routine")
        specialty = options.get("specialty", "")
        recipient_details = options.get("recipient_details", {})
        save_recipient = options.get("save_recipient", False)

        # Save recipient if requested
        if save_recipient and recipient_details.get("name"):
            recipient_manager = get_recipient_manager()
            recipient_manager.save_recipient({
                "name": recipient_details.get("name", ""),
                "recipient_type": recipient_type,
                "specialty": specialty,
                "facility": recipient_details.get("facility", ""),
                "fax": recipient_details.get("fax", "")
            })
            logging.info(f"Saved new recipient: {recipient_details.get('name')}")

        # Create error handler for this operation
        error_handler = AsyncUIErrorHandler(
            self.app,
            button=self.app.referral_button,
            progress_bar=self.app.progress_bar,
            operation_name=f"Generating {recipient_type} referral"
        )
        error_handler.start()

        def task() -> None:
            try:
                # Build input data with all options
                input_data = {
                    "conditions": conditions_text,
                    "recipient_type": recipient_type,
                    "urgency": urgency,
                    "specialty": specialty,
                    "recipient_details": recipient_details
                }

                if is_soap:
                    input_data["soap_note"] = source_text
                else:
                    input_data["transcript"] = source_text

                # Determine task description based on recipient type
                recipient_type_labels = {
                    "specialist": "specialist consultation",
                    "gp_backreferral": "GP back-referral",
                    "hospital": "hospital admission",
                    "diagnostic": "diagnostic services"
                }
                type_label = recipient_type_labels.get(recipient_type, "referral")

                task_data = AgentTask(
                    task_description=f"Generate {type_label} from {source_name}",
                    input_data=input_data
                )

                # Execute referral generation
                response = agent_manager.execute_agent_task(AgentType.REFERRAL, task_data)

                if response and response.success:
                    # Schedule UI update on main thread
                    error_handler.complete(
                        callback=lambda: self._update_referral_display(
                            response.result,
                            conditions_text or "all conditions",
                            source_name,
                            response.metadata
                        )
                    )
                else:
                    error_msg = response.error if response else "Unknown error"
                    raise Exception(error_msg)

            except Exception as e:
                error_handler.fail(e)

        # Submit task for execution
        self.app.io_executor.submit(task)
    
    def _update_referral_display(self, referral_text: str, conditions: str,
                                 source: str, metadata: dict) -> None:
        """Update UI with referral agent results.

        Note: Progress bar and button state are handled by AsyncUIErrorHandler.
        """
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
        recipient_type = metadata.get('recipient_type', 'specialist')
        urgency = metadata.get('urgency_level', 'standard')
        specialty = metadata.get('specialty', '')
        recipient_name = metadata.get('recipient_name', '')

        # Build descriptive status message
        recipient_type_labels = {
            'specialist': 'Specialist referral',
            'gp_backreferral': 'GP back-referral',
            'hospital': 'Hospital admission request',
            'diagnostic': 'Diagnostic request'
        }
        type_label = recipient_type_labels.get(recipient_type, 'Referral')

        status_msg = f"{type_label} generated from {source}"

        if specialty:
            status_msg += f" to {specialty}"

        if recipient_name:
            status_msg += f" ({recipient_name})"

        if urgency and urgency not in ('standard', 'routine'):
            status_msg += f" - {urgency.upper()}"

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
        
        # Get the data extraction button for error handler
        data_extraction_button = self.app.ui.components.get('generate_data_extraction_button')

        # Create error handler for this operation
        error_handler = AsyncUIErrorHandler(
            self.app,
            button=data_extraction_button,
            progress_bar=self.app.progress_bar,
            operation_name=f"Extracting clinical data from {source_name}"
        )
        error_handler.start()

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
                    error_handler.complete(
                        callback=lambda: self._update_data_extraction_display(
                            response.result,
                            extraction_type,
                            source_name,
                            output_format,
                            response.metadata
                        )
                    )
                else:
                    error_msg = response.error if response else "Unknown error"
                    raise Exception(error_msg)

            except Exception as e:
                error_handler.fail(e)

        # Submit task for execution
        self.app.io_executor.submit(task)
    
    def _update_data_extraction_display(self, extracted_data: str, extraction_type: str, 
                                        source: str, output_format: str, metadata: dict) -> None:
        """Update UI with data extraction results."""
        # Note: Progress bar and button state are handled by AsyncUIErrorHandler.

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
        
        # Get the workflow button and build workflow name for error handler
        workflow_name = workflow_type.replace('_', ' ').title()
        workflow_button = self.app.ui.components.get('generate_workflow_button')

        # Create error handler for this operation
        error_handler = AsyncUIErrorHandler(
            self.app,
            button=workflow_button,
            progress_bar=self.app.progress_bar,
            operation_name=f"Generating {workflow_name} workflow"
        )
        error_handler.start()

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
                    error_handler.complete(
                        callback=lambda: self._update_workflow_display(
                            response.result,
                            workflow_type,
                            patient_info,
                            response.metadata
                        )
                    )
                else:
                    error_msg = response.error if response else "Unknown error"
                    raise Exception(error_msg)

            except Exception as e:
                error_handler.fail(e)

        # Submit task for execution
        self.app.io_executor.submit(task)
    
    def _update_workflow_display(self, workflow_text: str, workflow_type: str,
                                 patient_info: Dict[str, Any], metadata: dict) -> None:
        """Update UI with workflow results.

        Note: Progress bar and button state are handled by AsyncUIErrorHandler.
        """
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
