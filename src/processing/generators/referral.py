"""
Referral Generator Module

Handles referral generation using the referral agent.
"""

import logging
from tkinter import messagebox
from tkinter.constants import RIGHT
from typing import TYPE_CHECKING, Dict, Any

from ai.ai import get_possible_conditions
from managers.agent_manager import agent_manager
from managers.recipient_manager import get_recipient_manager
from ai.agents import AgentTask, AgentType
from ui.dialogs.referral_options_dialog import ReferralOptionsDialog
from utils.error_handling import AsyncUIErrorHandler

if TYPE_CHECKING:
    from core.app import MedicalAssistantApp


class ReferralGeneratorMixin:
    """Mixin for referral generation functionality."""

    app: "MedicalAssistantApp"

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

                logging.debug(f"Referral input_data keys: {list(input_data.keys())}")
                logging.debug(f"source_text length: {len(source_text)}, is_soap: {is_soap}")

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


__all__ = ["ReferralGeneratorMixin"]
