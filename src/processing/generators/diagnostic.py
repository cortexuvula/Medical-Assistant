"""
Diagnostic Generator Module

Handles diagnostic analysis generation using the diagnostic agent.
"""

import logging
from tkinter import messagebox
from typing import TYPE_CHECKING

from managers.agent_manager import agent_manager
from ai.agents import AgentTask, AgentType
from ui.dialogs.diagnostic_dialog import DiagnosticAnalysisDialog
from ui.dialogs.diagnostic_results_dialog import DiagnosticResultsDialog
from utils.error_handling import AsyncUIErrorHandler, ErrorContext

if TYPE_CHECKING:
    from core.app import MedicalAssistantApp


class DiagnosticGeneratorMixin:
    """Mixin for diagnostic analysis functionality."""

    app: "MedicalAssistantApp"

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
        patient_context = result.get("patient_context")
        specialty = result.get("specialty", "general")

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
                # Build input data with patient context and specialty
                task_input_data = {}

                if clinical_findings:
                    task_input_data["clinical_findings"] = clinical_findings
                elif source == "soap":
                    task_input_data["soap_note"] = soap_note

                # Add patient context if provided
                if patient_context:
                    task_input_data["patient_context"] = patient_context

                # Add specialty focus
                task_input_data["specialty"] = specialty

                # Create agent task with enhanced input
                task_data = AgentTask(
                    task_description=f"Analyze clinical findings from {source_name} with {specialty} focus",
                    input_data=task_input_data,
                    context=self._build_context_string(patient_context, specialty) if patient_context else None
                )

                # Execute diagnostic analysis
                response = agent_manager.execute_agent_task(AgentType.DIAGNOSTIC, task_data)

                if response and response.success:
                    # Capture values for closure
                    _source_text = clinical_findings if clinical_findings else soap_note
                    # Schedule UI update on main thread
                    error_handler.complete(
                        callback=lambda: self._update_diagnostic_display(
                            response.result,
                            source_name,
                            response.metadata,
                            source_text=_source_text
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

    def _build_context_string(self, patient_context: dict, specialty: str) -> str:
        """Build a context string from patient context and specialty for the agent.

        Args:
            patient_context: Dictionary with patient demographics and history
            specialty: The specialty focus for the analysis

        Returns:
            Formatted context string for the agent
        """
        parts = []

        # Specialty context mapping
        specialty_contexts = {
            "general": "Apply a broad primary care perspective, considering common conditions first.",
            "emergency": "Prioritize life-threatening and time-sensitive conditions. Focus on red flags.",
            "internal": "Consider multisystem involvement and complex medical conditions.",
            "pediatric": "Apply age-appropriate differentials and developmental considerations.",
            "cardiology": "Focus on cardiovascular causes and risk stratification.",
            "pulmonology": "Focus on respiratory and pulmonary conditions.",
            "gi": "Focus on gastrointestinal and hepatobiliary conditions.",
            "neurology": "Focus on neurological causes including structural, vascular, and functional.",
            "psychiatry": "Consider psychiatric and biopsychosocial factors.",
            "orthopedic": "Focus on musculoskeletal and orthopedic conditions.",
            "oncology": "Consider malignancy in the differential and paraneoplastic syndromes.",
            "geriatric": "Consider age-related conditions, polypharmacy, and atypical presentations.",
        }

        parts.append(f"SPECIALTY FOCUS: {specialty_contexts.get(specialty, specialty_contexts['general'])}")

        if patient_context:
            patient_parts = []

            if 'age' in patient_context:
                patient_parts.append(f"Age: {patient_context['age']} years")

            if 'sex' in patient_context:
                patient_parts.append(f"Sex: {patient_context['sex']}")
                if patient_context.get('pregnant'):
                    patient_parts.append("Pregnancy: Currently pregnant")

            if 'past_medical_history' in patient_context:
                patient_parts.append(f"Past Medical History: {patient_context['past_medical_history']}")

            if 'current_medications' in patient_context:
                patient_parts.append(f"Current Medications: {patient_context['current_medications']}")

            if 'allergies' in patient_context:
                patient_parts.append(f"Allergies: {patient_context['allergies']}")

            if patient_parts:
                parts.append("PATIENT CONTEXT:\n" + "\n".join(patient_parts))

        return "\n\n".join(parts)

    def _update_diagnostic_display(
        self,
        analysis: str,
        source: str,
        metadata: dict,
        source_text: str = ""
    ) -> None:
        """Update the UI with diagnostic analysis results.

        Note: Progress bar and button state are handled by AsyncUIErrorHandler.
        """
        # Try to get recording_id from current selection if available
        recording_id = None
        if hasattr(self.app, 'selected_recording_id'):
            recording_id = self.app.selected_recording_id

        # Show results in a dialog
        dialog = DiagnosticResultsDialog(self.app)
        dialog.show_results(
            analysis,
            source,
            metadata,
            recording_id=recording_id,
            source_text=source_text
        )

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

    def _run_diagnostic_to_panel(self, soap_note: str) -> None:
        """Run differential diagnosis and display results in the analysis panel.

        Args:
            soap_note: The SOAP note text to analyze for diagnoses
        """
        logging.info("_run_diagnostic_to_panel called")
        self.app.status_manager.info("Starting differential diagnosis...")

        # Check if the analysis panel exists
        if not hasattr(self.app, 'differential_analysis_text') or self.app.differential_analysis_text is None:
            logging.warning("Differential analysis panel not available")
            self.app.status_manager.warning("Differential panel not available")
            return

        # Check if diagnostic agent is enabled
        if not agent_manager.is_agent_enabled(AgentType.DIAGNOSTIC):
            self._update_analysis_panel(
                self.app.differential_analysis_text,
                "Diagnostic agent is disabled.\n\n"
                "Enable it in Settings → AI & Models → Agent Settings"
            )
            return

        # Show loading indicator
        self._update_analysis_panel(
            self.app.differential_analysis_text,
            "Analyzing differential diagnoses..."
        )

        def task() -> None:
            try:
                # Create agent task for diagnostic analysis
                task_data = AgentTask(
                    task_description="Generate differential diagnosis from SOAP note",
                    input_data={"soap_note": soap_note}
                )

                # Execute diagnostic analysis
                response = agent_manager.execute_agent_task(AgentType.DIAGNOSTIC, task_data)

                if response and response.success:
                    # Store analysis for View Details functionality
                    self.app._last_diagnostic_analysis = {
                        'result': response.result,
                        'metadata': response.metadata or {}
                    }
                    logging.debug(f"Stored diagnostic analysis on app (result length: {len(response.result)})")

                    # Update panel with formatted results
                    self.app.after(0, lambda: self._update_diagnostic_panel_formatted(
                        response.result,
                        response.metadata or {}
                    ))
                else:
                    error_msg = response.error if response else "Unknown error"
                    self.app.after(0, lambda: self._update_analysis_panel(
                        self.app.differential_analysis_text,
                        f"Analysis failed: {error_msg}\n\n"
                        "Unable to generate differential diagnosis."
                    ))

            except Exception as e:
                logging.error(f"Diagnostic panel analysis failed: {e}")
                self.app.after(0, lambda: self._update_analysis_panel(
                    self.app.differential_analysis_text,
                    f"Error: {str(e)}\n\n"
                    "Check your API key and network connection."
                ))

        # Submit task for execution
        self.app.io_executor.submit(task)

    def _update_diagnostic_panel_formatted(self, result: str, metadata: dict) -> None:
        """Update diagnostic panel with formatted content.

        Args:
            result: The analysis result text
            metadata: Analysis metadata for summary
        """
        try:
            from ui.components.analysis_panel_formatter import AnalysisPanelFormatter

            widget = self.app.differential_analysis_text
            formatter = AnalysisPanelFormatter(widget)
            formatter.format_diagnostic_panel(result, metadata)

            # Enable View Details button
            if hasattr(self.app, 'ui') and hasattr(self.app.ui, 'components'):
                view_btn = self.app.ui.components.get('differential_view_details_btn')
                if view_btn:
                    view_btn.config(state='normal')
                    logging.debug("Diagnostic View Details button enabled")
                else:
                    logging.warning("differential_view_details_btn not found in components")
            else:
                logging.warning("Cannot access app.ui.components to enable View Details button")

            self.app.status_manager.success("Differential diagnosis complete")

        except Exception as e:
            logging.error(f"Failed to format diagnostic panel: {e}")
            # Fall back to plain text update
            self._update_analysis_panel(self.app.differential_analysis_text, str(result))


__all__ = ["DiagnosticGeneratorMixin"]
