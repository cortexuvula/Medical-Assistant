"""
SOAP QA Generator Module

Handles medication QA comparison warning display in the analysis panel.
This mixin does NOT use AI agents - it formats and displays
pre-computed medication comparison warnings from SOAP note generation.
"""

from typing import List, TYPE_CHECKING

from utils.structured_logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from core.app import MedicalAssistantApp


class SOAPQAGeneratorMixin:
    """Mixin for SOAP QA medication comparison warning display."""

    app: "MedicalAssistantApp"

    def _get_soap_qa_widget(self):
        """Get the SOAP QA text widget from UI components."""
        widget = None
        if hasattr(self.app, 'ui'):
            widget = self.app.ui.components.get('soap_qa_text')
        return widget

    def _run_soap_qa_to_panel(self, warnings: List[str]) -> None:
        """Display medication QA warnings in the analysis panel.

        Formats medication comparison warnings and updates the SOAP QA
        panel widget. No AI agent is invoked.

        Args:
            warnings: List of medication omission warning strings
        """
        logger.info(f"_run_soap_qa_to_panel called with {len(warnings)} warning(s)")

        widget = self._get_soap_qa_widget()
        if not widget:
            logger.warning("SOAP QA panel not available")
            return

        if not warnings:
            self._update_analysis_panel(
                widget,
                "No medication omissions detected.\n\n"
                "All medications mentioned in the transcript "
                "appear in the SOAP note."
            )
            return

        # Format warnings for display
        lines = [f"Medication QA ({len(warnings)} potential omission(s))\n"]
        for i, warning in enumerate(warnings, 1):
            lines.append(f"  {i}. {warning}")
        lines.append("")
        lines.append(
            "Please verify these medications are appropriately "
            "addressed in the SOAP note."
        )

        formatted = "\n".join(lines)
        self._update_analysis_panel(widget, formatted)

        # Flash status bar to draw attention
        self.app.status_manager.warning(
            f"Medication QA: {len(warnings)} potential omission(s) "
            f"— see Medication QA tab"
        )

        logger.info("SOAP QA warnings displayed in panel")


__all__ = ["SOAPQAGeneratorMixin"]
