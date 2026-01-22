"""
Medication Generator Module

Handles medication analysis using the medication agent.
"""

from tkinter import messagebox
from typing import TYPE_CHECKING

from managers.agent_manager import agent_manager
from ai.agents import AgentTask, AgentType
from utils.error_handling import AsyncUIErrorHandler, ErrorContext
from utils.structured_logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from core.app import MedicalAssistantApp


class MedicationGeneratorMixin:
    """Mixin for medication analysis functionality."""

    app: "MedicalAssistantApp"

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
        patient_context = result.get("patient_context")  # New: patient context from dialog

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

                # Add patient context if provided
                if patient_context:
                    input_data["patient_context"] = patient_context

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
                    # Capture values for closure
                    _content = content
                    _patient_context = patient_context
                    # Schedule UI update on main thread
                    error_handler.complete(
                        callback=lambda: self._update_medication_display(
                            response.result,
                            analysis_type,
                            source_name,
                            response.metadata,
                            source_text=_content,
                            patient_context=_patient_context
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

    def _update_medication_display(
        self,
        analysis: dict,
        analysis_type: str,
        source: str,
        metadata: dict,
        source_text: str = "",
        patient_context: dict = None
    ) -> None:
        """Update UI with medication analysis results.

        Note: Progress bar and button state are handled by AsyncUIErrorHandler.
        """
        # Import here to avoid circular imports
        from ui.dialogs.medication_results_dialog import MedicationResultsDialog

        # Try to get recording_id from current selection if available
        recording_id = None
        if hasattr(self.app, 'selected_recording_id'):
            recording_id = self.app.selected_recording_id

        # Show results in a dialog
        dialog = MedicationResultsDialog(self.app)
        dialog.show_results(
            analysis,
            analysis_type,
            source,
            metadata,
            recording_id=recording_id,
            patient_context=patient_context,
            source_text=source_text
        )

        # Update status
        med_count = metadata.get('medication_count', 0)
        interaction_count = metadata.get('interaction_count', 0)

        status_msg = f"Medication analysis completed: {med_count} medications"
        if interaction_count > 0:
            status_msg += f", {interaction_count} interactions found"

        self.app.status_manager.success(status_msg)

    def _run_medication_to_panel(self, soap_note: str) -> None:
        """Run medication analysis and display results in the analysis panel.

        Args:
            soap_note: The SOAP note text to analyze for medications
        """
        logger.info("_run_medication_to_panel called")
        self.app.status_manager.info("Starting medication analysis...")

        # Check if the analysis panel exists
        if not hasattr(self.app, 'medication_analysis_text') or self.app.medication_analysis_text is None:
            logger.warning("Medication analysis panel not available")
            self.app.status_manager.warning("Medication panel not available")
            return

        # Check if medication agent is enabled
        if not agent_manager.is_agent_enabled(AgentType.MEDICATION):
            self._update_analysis_panel(
                self.app.medication_analysis_text,
                "Medication agent is disabled.\n\n"
                "Enable it in Settings → AI & Models → Agent Settings"
            )
            return

        # Show loading indicator
        self._update_analysis_panel(
            self.app.medication_analysis_text,
            "Analyzing medications..."
        )

        def task() -> None:
            try:
                # Create agent task for medication analysis
                task_data = AgentTask(
                    task_description="Extract and analyze medications from SOAP note",
                    input_data={
                        "soap_note": soap_note,
                        "analysis_type": "comprehensive"
                    }
                )

                # Execute medication analysis
                response = agent_manager.execute_agent_task(AgentType.MEDICATION, task_data)

                if response and response.success:
                    # Store analysis for View Details functionality
                    self.app._last_medication_analysis = {
                        'result': response.result,
                        'analysis_type': 'comprehensive',
                        'metadata': response.metadata or {}
                    }
                    logger.info(f"Stored medication analysis on app id={id(self.app)} (result length: {len(response.result)})")
                    logger.info(f"self.app type: {type(self.app)}")

                    # Update panel with formatted results
                    self.app.after(0, lambda: self._update_medication_panel_formatted(
                        response.result,
                        response.metadata or {}
                    ))
                else:
                    error_msg = response.error if response else "Unknown error"
                    self.app.after(0, lambda: self._update_analysis_panel(
                        self.app.medication_analysis_text,
                        f"Analysis failed: {error_msg}\n\n"
                        "No medications found or API error occurred."
                    ))

            except Exception as e:
                logger.error(f"Medication panel analysis failed: {e}")
                error_msg = str(e)  # Capture before closure
                self.app.after(0, lambda: self._update_analysis_panel(
                    self.app.medication_analysis_text,
                    f"Error: {error_msg}\n\n"
                    "Check your API key and network connection."
                ))

        # Submit task for execution
        self.app.io_executor.submit(task)

    def _update_medication_panel_formatted(self, result: str, metadata: dict) -> None:
        """Update medication panel with formatted content.

        Args:
            result: The analysis result text
            metadata: Analysis metadata for summary
        """
        try:
            from ui.components.analysis_panel_formatter import AnalysisPanelFormatter

            widget = self.app.medication_analysis_text
            formatter = AnalysisPanelFormatter(widget)
            formatter.format_medication_panel(result, metadata)

            # Enable View Details button
            if hasattr(self.app, 'ui') and hasattr(self.app.ui, 'components'):
                logger.info(f"Looking for medication_view_details_btn in app.ui.components")
                logger.info(f"Available component keys: {list(self.app.ui.components.keys())}")
                view_btn = self.app.ui.components.get('medication_view_details_btn')
                if view_btn:
                    view_btn.config(state='normal')
                    logger.info("Medication View Details button enabled (state='normal')")
                else:
                    logger.warning("medication_view_details_btn not found in components")
            else:
                logger.warning(f"Cannot access app.ui.components: has ui={hasattr(self.app, 'ui')}, has components={hasattr(self.app.ui, 'components') if hasattr(self.app, 'ui') else 'N/A'}")

            # Save to database if recording_id is available
            self._save_medication_analysis_to_db(result, metadata)

            self.app.status_manager.success("Medication analysis complete")

        except Exception as e:
            logger.error(f"Failed to format medication panel: {e}")
            # Fall back to plain text update
            self._update_analysis_panel(self.app.medication_analysis_text, str(result))

    def _save_medication_analysis_to_db(self, result: str, metadata: dict) -> None:
        """Save medication analysis to database if recording_id is available.

        If no recording_id is available, stores the analysis as pending to be
        saved when a recording is created/saved (deferred save pattern).

        Args:
            result: The analysis result text
            metadata: Analysis metadata
        """
        try:
            from processing.analysis_storage import get_analysis_storage

            # Get recording_id from current selection
            recording_id = getattr(self.app, 'selected_recording_id', None)

            # Get SOAP note as source text
            source_text = ""
            if hasattr(self.app, 'soap_text'):
                source_text = self.app.soap_text.get("1.0", "end").strip()

            if not recording_id:
                # Store as pending - will be saved when recording is saved
                self.app._pending_medication_analysis = {
                    'result_text': result,
                    'metadata': metadata,
                    'source_text': source_text[:5000] if source_text else None,
                    'analysis_subtype': 'comprehensive'
                }
                logger.info("Medication analysis stored as pending - will save with recording")
                return

            storage = get_analysis_storage()
            analysis_id = storage.save_medication_analysis(
                result_text=result,
                recording_id=recording_id,
                metadata=metadata,
                source_type="soap",
                source_text=source_text[:5000] if source_text else None,  # Limit length
                analysis_subtype="comprehensive"
            )

            if analysis_id:
                logger.info(f"Saved medication analysis (id={analysis_id}) for recording {recording_id}")

                # Update sidebar indicators
                self._update_soap_indicators()

        except Exception as e:
            logger.error(f"Failed to save medication analysis to database: {e}")

    def _update_soap_indicators(self) -> None:
        """Update sidebar SOAP sub-item indicators."""
        try:
            from processing.analysis_storage import get_analysis_storage

            recording_id = getattr(self.app, 'selected_recording_id', None)
            if not recording_id:
                return

            storage = get_analysis_storage()
            has_medication = storage.has_medication_analysis(recording_id)
            has_differential = storage.has_differential_diagnosis(recording_id)

            # Update sidebar indicators
            if hasattr(self.app, 'ui') and hasattr(self.app.ui, 'components'):
                sidebar_nav = self.app.ui.components.get('sidebar_navigation')
                if sidebar_nav and hasattr(sidebar_nav, 'update_soap_indicators'):
                    sidebar_nav.update_soap_indicators(
                        has_medication=has_medication,
                        has_differential=has_differential
                    )
        except Exception as e:
            logger.debug(f"Could not update SOAP indicators: {e}")


__all__ = ["MedicationGeneratorMixin"]
