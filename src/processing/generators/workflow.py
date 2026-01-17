"""
Workflow Generator Module

Handles clinical workflow management using the workflow agent.
"""

from tkinter import messagebox
from typing import TYPE_CHECKING, Dict, Any

from managers.agent_manager import agent_manager
from ai.agents import AgentTask, AgentType
from utils.error_handling import AsyncUIErrorHandler

if TYPE_CHECKING:
    from core.app import MedicalAssistantApp


class WorkflowGeneratorMixin:
    """Mixin for clinical workflow management functionality."""

    app: "MedicalAssistantApp"

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


__all__ = ["WorkflowGeneratorMixin"]
