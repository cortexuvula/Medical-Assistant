"""
Compliance Generator Module

Handles clinical guidelines compliance analysis using the compliance agent.
Analyzes SOAP notes against clinical guidelines for adherence checking.

Architecture Note:
    This generator uses the ComplianceAgent which queries the SEPARATE
    guidelines database, NOT the main patient RAG system.
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


class ComplianceGeneratorMixin:
    """Mixin for clinical guidelines compliance analysis functionality."""

    app: "MedicalAssistantApp"

    def create_compliance_analysis(self) -> None:
        """Create a compliance analysis from SOAP note content."""
        # Reload settings to ensure we have the latest configuration
        from settings.settings import load_settings, SETTINGS
        latest_settings = load_settings()
        SETTINGS.update(latest_settings)

        # Reload agent manager to pick up latest settings
        agent_manager.reload_agents()

        # Check if compliance agent is enabled
        if not agent_manager.is_agent_enabled(AgentType.COMPLIANCE):
            messagebox.showwarning(
                "Compliance Agent Disabled",
                "The Compliance Agent is currently disabled.\n\n"
                "Please enable it in Settings > Agent Settings to use compliance analysis."
            )
            return

        # Check for existing SOAP note content
        soap_note = self.app.soap_text.get("1.0", "end").strip()

        if not soap_note:
            messagebox.showwarning(
                "No SOAP Note",
                "Please generate or enter a SOAP note before running compliance analysis."
            )
            return

        # Get the compliance button if available
        compliance_button = self.app.ui.components.get('compliance_view_details_btn')

        # Create error handler for this operation
        error_handler = AsyncUIErrorHandler(
            self.app,
            button=compliance_button,
            progress_bar=self.app.progress_bar,
            operation_name="Checking clinical guidelines compliance"
        )
        error_handler.start()

        def task() -> None:
            try:
                # Create agent task for compliance analysis
                task_data = AgentTask(
                    task_description="Check SOAP note compliance with clinical guidelines",
                    input_data={"soap_note": soap_note}
                )

                # Execute compliance analysis
                response = agent_manager.execute_agent_task(AgentType.COMPLIANCE, task_data)

                if response and response.success:
                    # Schedule UI update on main thread
                    error_handler.complete(
                        callback=lambda: self._update_compliance_display(
                            response.result,
                            "SOAP Note",
                            response.metadata
                        )
                    )
                else:
                    error_msg = response.error if response else "Unknown error"
                    ctx = ErrorContext.capture(
                        operation="Compliance analysis",
                        error_message=error_msg,
                        error_code="COMPLIANCE_FAILED",
                        input_summary=f"SOAP note length: {len(soap_note)}",
                        agent_type="COMPLIANCE",
                        response_metadata=response.metadata if response else None
                    )
                    ctx.log()
                    raise Exception(ctx.user_message)

            except Exception as e:
                if not isinstance(e.args[0], str) or "failed:" not in str(e):
                    ctx = ErrorContext.capture(
                        operation="Compliance analysis",
                        exception=e,
                        error_code="COMPLIANCE_ERROR",
                        input_summary="SOAP Note"
                    )
                    ctx.log()
                    error_handler.fail(ctx.user_message)
                else:
                    error_handler.fail(e)

        # Submit task for execution
        self.app.io_executor.submit(task)

    def _update_compliance_display(
        self,
        analysis: str,
        source: str,
        metadata: dict
    ) -> None:
        """Update the UI with compliance analysis results.

        Args:
            analysis: The compliance analysis text
            source: Source of the SOAP note
            metadata: Analysis metadata
        """
        recording_id = getattr(self.app, 'selected_recording_id', None)

        # Try to show in a dialog if available
        try:
            from ui.dialogs.compliance_results_dialog import ComplianceResultsDialog
            dialog = ComplianceResultsDialog(self.app)
            dialog.show_results(analysis, metadata, recording_id=recording_id)
        except ImportError:
            # Fallback - just update status
            pass

        # Build status message from metadata
        guidelines_checked = metadata.get('guidelines_checked', 0)
        compliant_count = metadata.get('compliant_count', 0)
        gap_count = metadata.get('gap_count', 0)
        warning_count = metadata.get('warning_count', 0)
        overall_score = metadata.get('overall_score', 0.0)

        status_msg = f"Compliance check complete: {int(overall_score * 100)}% score"
        if gap_count > 0:
            status_msg += f", {gap_count} gaps identified"
        if warning_count > 0:
            status_msg += f", {warning_count} warnings"

        self.app.status_manager.success(status_msg)

    def _run_compliance_to_panel(self, soap_note: str) -> None:
        """Run compliance analysis and display results in the analysis panel.

        This is called automatically after SOAP note generation to provide
        immediate guideline compliance feedback.

        Args:
            soap_note: The SOAP note text to analyze for compliance
        """
        logger.info("_run_compliance_to_panel called")
        self.app.status_manager.info("Checking clinical guidelines compliance...")

        # Check if the analysis panel exists
        compliance_text = getattr(self.app, 'compliance_analysis_text', None)
        if compliance_text is None:
            # Try to get from UI components
            if hasattr(self.app, 'ui') and hasattr(self.app.ui, 'components'):
                compliance_text = self.app.ui.components.get('compliance_analysis_text')

        if compliance_text is None:
            logger.warning("Compliance analysis panel not available")
            self.app.status_manager.warning("Compliance panel not available")
            return

        # Check if compliance agent is enabled
        if not agent_manager.is_agent_enabled(AgentType.COMPLIANCE):
            self._update_analysis_panel(
                compliance_text,
                "Compliance agent is disabled.\n\n"
                "Enable it in Settings → AI & Models → Agent Settings\n\n"
                "To check compliance, you also need to upload clinical guidelines "
                "using the 'Upload Guidelines' button above."
            )
            return

        # Show loading indicator
        self._update_analysis_panel(
            compliance_text,
            "Checking clinical guidelines compliance..."
        )

        def task() -> None:
            try:
                # Create agent task for compliance analysis
                task_data = AgentTask(
                    task_description="Check SOAP note compliance with clinical guidelines",
                    input_data={"soap_note": soap_note}
                )

                # Execute compliance analysis
                response = agent_manager.execute_agent_task(AgentType.COMPLIANCE, task_data)

                if response and response.success:
                    # Store analysis for View Details functionality
                    self.app._last_compliance_analysis = {
                        'result': response.result,
                        'metadata': response.metadata or {}
                    }
                    logger.debug(f"Stored compliance analysis on app (result length: {len(response.result)})")

                    # Update panel with formatted results
                    self.app.after(0, lambda: self._update_compliance_panel_formatted(
                        response.result,
                        response.metadata or {}
                    ))
                else:
                    error_msg = response.error if response else "Unknown error"

                    # Check if it's a "no guidelines" error
                    if "no guidelines" in error_msg.lower() or "guidelines not" in error_msg.lower():
                        self.app.after(0, lambda: self._update_analysis_panel(
                            compliance_text,
                            "No clinical guidelines available for compliance checking.\n\n"
                            "To enable compliance checking:\n"
                            "1. Click 'Upload Guidelines' above\n"
                            "2. Upload clinical guidelines (PDF, DOCX, TXT)\n"
                            "3. Specify specialty and source\n"
                            "4. Generate a new SOAP note"
                        ))
                    else:
                        self.app.after(0, lambda: self._update_analysis_panel(
                            compliance_text,
                            f"Analysis failed: {error_msg}\n\n"
                            "Unable to check compliance."
                        ))

            except Exception as e:
                logger.error(f"Compliance panel analysis failed: {e}")
                error_msg = str(e)
                self.app.after(0, lambda: self._update_analysis_panel(
                    compliance_text,
                    f"Error: {error_msg}\n\n"
                    "Check your API key and network connection."
                ))

        # Submit task for execution
        self.app.io_executor.submit(task)

    def _update_compliance_panel_formatted(self, result: str, metadata: dict) -> None:
        """Update compliance panel with formatted content.

        Args:
            result: The compliance analysis result text
            metadata: Analysis metadata for summary
        """
        try:
            # Get compliance text widget
            compliance_text = getattr(self.app, 'compliance_analysis_text', None)
            if compliance_text is None and hasattr(self.app, 'ui'):
                compliance_text = self.app.ui.components.get('compliance_analysis_text')

            if not compliance_text:
                logger.warning("Compliance text widget not found")
                return

            try:
                from ui.components.analysis_panel_formatter import AnalysisPanelFormatter
                formatter = AnalysisPanelFormatter(compliance_text)
                formatter.format_compliance_panel(result, metadata)
            except (ImportError, AttributeError):
                # Fallback to plain text
                self._update_analysis_panel(compliance_text, result)

            # Enable View Details button
            if hasattr(self.app, 'ui') and hasattr(self.app.ui, 'components'):
                view_btn = self.app.ui.components.get('compliance_view_details_btn')
                if view_btn:
                    view_btn.config(state='normal')
                    logger.debug("Compliance View Details button enabled")

            # Save to database if recording_id is available
            self._save_compliance_to_db(result, metadata)

            # Build and show status
            overall_score = metadata.get('overall_score', 0.0)
            gap_count = metadata.get('gap_count', 0)
            warning_count = metadata.get('warning_count', 0)

            status_parts = [f"Compliance: {int(overall_score * 100)}%"]
            if gap_count > 0:
                status_parts.append(f"{gap_count} gaps")
            if warning_count > 0:
                status_parts.append(f"{warning_count} warnings")

            self.app.status_manager.success(" | ".join(status_parts))

        except Exception as e:
            logger.error(f"Failed to format compliance panel: {e}")
            # Fall back to plain text update
            compliance_text = getattr(self.app, 'compliance_analysis_text', None)
            if compliance_text:
                self._update_analysis_panel(compliance_text, str(result))

    def _save_compliance_to_db(self, result: str, metadata: dict) -> None:
        """Save compliance analysis to database if recording_id is available.

        Args:
            result: The analysis result text
            metadata: Analysis metadata
        """
        try:
            from processing.analysis_storage import get_analysis_storage

            recording_id = getattr(self.app, 'selected_recording_id', None)

            # Get SOAP note as source text
            source_text = ""
            if hasattr(self.app, 'soap_text'):
                source_text = self.app.soap_text.get("1.0", "end").strip()

            if not recording_id:
                # Store as pending - will be saved when recording is saved
                self.app._pending_compliance_analysis = {
                    'result_text': result,
                    'metadata': metadata,
                    'source_text': source_text[:5000] if source_text else None,
                    'analysis_subtype': 'guidelines'
                }
                logger.info("Compliance analysis stored as pending - will save with recording")
                return

            storage = get_analysis_storage()
            analysis_id = storage.save_compliance_analysis(
                result_text=result,
                recording_id=recording_id,
                metadata=metadata,
                source_type="soap",
                source_text=source_text[:5000] if source_text else None,
                analysis_subtype="guidelines"
            )

            if analysis_id:
                logger.info(f"Saved compliance analysis (id={analysis_id}) for recording {recording_id}")

                # Update sidebar indicators
                self._update_compliance_indicators()

        except Exception as e:
            logger.error(f"Failed to save compliance analysis to database: {e}")

    def _update_compliance_indicators(self) -> None:
        """Update sidebar SOAP sub-item indicators for compliance."""
        try:
            from processing.analysis_storage import get_analysis_storage

            recording_id = getattr(self.app, 'selected_recording_id', None)
            if not recording_id:
                return

            storage = get_analysis_storage()
            has_medication = storage.has_medication_analysis(recording_id)
            has_differential = storage.has_differential_diagnosis(recording_id)
            has_compliance = storage.has_compliance_analysis(recording_id)

            # Update sidebar indicators if available
            if hasattr(self.app, 'ui') and hasattr(self.app.ui, 'components'):
                sidebar_nav = self.app.ui.components.get('sidebar_navigation')
                if sidebar_nav and hasattr(sidebar_nav, 'update_soap_indicators'):
                    sidebar_nav.update_soap_indicators(
                        has_medication=has_medication,
                        has_differential=has_differential,
                        has_compliance=has_compliance
                    )
        except Exception as e:
            logger.debug(f"Could not update compliance indicators: {e}")

    def _update_analysis_panel(self, text_widget, content: str) -> None:
        """Update an analysis panel with plain text content.

        Args:
            text_widget: The tk.Text widget to update
            content: Text content to display
        """
        try:
            text_widget.config(state='normal')
            text_widget.delete('1.0', 'end')
            text_widget.insert('1.0', content)
            text_widget.config(state='disabled')
        except Exception as e:
            logger.debug(f"Failed to update analysis panel: {e}")


__all__ = ["ComplianceGeneratorMixin"]
