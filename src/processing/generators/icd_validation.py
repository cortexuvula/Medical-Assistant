"""
ICD Validation Generator Module

Handles ICD code validation warning display in the analysis panel.
This mixin does NOT use AI agents - it formats and displays
pre-computed ICD validation warnings from SOAP note generation.
"""

from typing import List, TYPE_CHECKING

from utils.structured_logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from core.app import MedicalAssistantApp


class ICDValidationGeneratorMixin:
    """Mixin for ICD code validation warning display functionality."""

    app: "MedicalAssistantApp"

    def _get_icd_validation_widget(self):
        """Get the ICD validation text widget from UI components."""
        widget = None
        if hasattr(self.app, 'ui'):
            widget = self.app.ui.components.get('icd_validation_text')
        return widget

    def _run_icd_validation_to_panel(self, warnings: List[str]) -> None:
        """Display ICD validation warnings in the analysis panel.

        Formats validation warnings and updates the ICD validation
        panel widget. No AI agent is invoked.

        Args:
            warnings: List of ICD validation warning strings
        """
        logger.info(f"_run_icd_validation_to_panel called with {len(warnings)} warning(s)")

        widget = self._get_icd_validation_widget()
        if not widget:
            logger.warning("ICD validation panel not available")
            return

        if not warnings:
            self._update_analysis_panel(
                widget,
                "No ICD code validation issues found."
            )
            return

        # Format warnings for display
        lines = [f"ICD Code Validation ({len(warnings)} warning(s))\n"]
        for i, warning in enumerate(warnings, 1):
            lines.append(f"  {i}. {warning}")
        lines.append("")
        lines.append("Please verify flagged codes before finalizing the SOAP note.")

        formatted = "\n".join(lines)
        self._update_analysis_panel(widget, formatted)

        # Flash status bar to draw attention
        self.app.status_manager.warning(
            f"ICD validation: {len(warnings)} warning(s) — see ICD Validation tab"
        )

        logger.info(f"ICD validation warnings displayed in panel")


__all__ = ["ICDValidationGeneratorMixin"]
