"""
Data Extraction Generator Module

Handles clinical data extraction using the data extraction agent.
"""

import logging
from tkinter import messagebox
from typing import TYPE_CHECKING

from managers.agent_manager import agent_manager
from ai.agents import AgentTask, AgentType
from utils.error_handling import AsyncUIErrorHandler

if TYPE_CHECKING:
    from core.app import MedicalAssistantApp


class DataExtractionGeneratorMixin:
    """Mixin for clinical data extraction functionality."""

    app: "MedicalAssistantApp"

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


__all__ = ["DataExtractionGeneratorMixin"]
