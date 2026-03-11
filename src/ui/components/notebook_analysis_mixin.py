"""
Analysis panel mixin for NotebookTabs.

This mixin provides all analysis panel related methods for the NotebookTabs
class, including medication analysis, differential diagnosis, compliance
analysis, panel toggle, and saved analysis loading.
"""

from __future__ import annotations

import tkinter as tk
from typing import Any, Dict

import ttkbootstrap as ttk
from utils.structured_logging import get_logger

from ui.ui_constants import Icons
from settings.settings import SETTINGS, save_settings

logger = get_logger(__name__)

# Analysis type configuration to eliminate per-type copy-paste
_ANALYSIS_TYPES = {
    "medication": {
        "attr": "_last_medication_analysis",
        "widget_key": "medication_analysis_text",
        "btn_key": "medication_view_details_btn",
        "label": "Medication",
        "empty_msg": "Medication analysis will appear here after SOAP note generation.",
        "formatter_method": "format_medication_panel",
    },
    "differential": {
        "attr": "_last_diagnostic_analysis",
        "widget_key": "differential_analysis_text",
        "btn_key": "differential_view_details_btn",
        "label": "Differential Diagnosis",
        "empty_msg": "Differential diagnosis will appear here after SOAP note generation.",
        "formatter_method": "format_diagnostic_panel",
    },
    "compliance": {
        "attr": "_last_compliance_analysis",
        "widget_key": "compliance_analysis_text",
        "btn_key": "compliance_view_details_btn",
        "label": "Clinical Guidelines Compliance",
        "empty_msg": ("Clinical guidelines compliance will appear here after SOAP note generation.\n\n"
                      "Use the 'Upload Guidelines' button to add clinical guidelines to the database."),
        "formatter_method": "format_compliance_panel",
    },
}


class NotebookAnalysisMixin:
    """Mixin providing analysis panel methods for NotebookTabs.

    Expects the host class to provide:
        - self.parent: The parent window (WorkflowUI)
        - self.components: Dict of UI component references
        - self._analysis_collapsed: bool
        - self._analysis_collapse_tooltip: ToolTip instance
    """

    def _toggle_analysis_panel(self) -> None:
        """Toggle collapse/expand state of the Analysis panel.

        When collapsed, the analysis content is hidden and only the header remains visible.
        The SOAP note editor expands to fill the available space by adjusting the PanedWindow sash.
        """
        self._analysis_collapsed = not self._analysis_collapsed

        # Save state to settings
        SETTINGS["analysis_panel_collapsed"] = self._analysis_collapsed
        try:
            save_settings(SETTINGS)
        except Exception as e:
            logger.warning(f"Failed to save analysis panel collapsed state: {e}")

        # Get references
        analysis_content = self.components.get('analysis_content')
        collapse_btn = self.components.get('analysis_collapse_btn')
        soap_paned = self.components.get('soap_paned')
        bottom_frame = self.components.get('analysis_bottom_frame')

        if not analysis_content or not collapse_btn or not soap_paned:
            return

        if self._analysis_collapsed:
            # Collapse: hide the analysis content and move sash to bottom
            analysis_content.pack_forget()
            # Show expand icon when collapsed - indicates "click to expand"
            collapse_btn.config(text=Icons.EXPAND)
            if hasattr(self, '_analysis_collapse_tooltip') and self._analysis_collapse_tooltip:
                self._analysis_collapse_tooltip.text = "Expand Analysis Panel"

            # Save current sash position before collapsing (for later restoration)
            soap_paned.update_idletasks()
            try:
                current_sash = soap_paned.sashpos(0)
                self._saved_sash_position = current_sash
            except tk.TclError:
                self._saved_sash_position = None

            # Move sash to nearly the bottom (leave room for header only ~30px)
            soap_paned.update_idletasks()
            try:
                total_height = soap_paned.winfo_height()
                # Leave just enough room for the header (approximately 30 pixels)
                collapsed_height = max(30, total_height - 30)
                soap_paned.sashpos(0, collapsed_height)
            except tk.TclError as e:
                logger.debug(f"Could not set sash position: {e}")
        else:
            # Expand: show the analysis content and restore sash position
            analysis_content.pack(fill=tk.BOTH, expand=True)
            # Show collapse icon when expanded - indicates "click to collapse"
            collapse_btn.config(text=Icons.COLLAPSE)
            if hasattr(self, '_analysis_collapse_tooltip') and self._analysis_collapse_tooltip:
                self._analysis_collapse_tooltip.text = "Collapse Analysis Panel"

            # Restore sash to previous position or default 70/30 split
            soap_paned.update_idletasks()
            try:
                total_height = soap_paned.winfo_height()
                if hasattr(self, '_saved_sash_position') and self._saved_sash_position:
                    # Restore saved position
                    soap_paned.sashpos(0, self._saved_sash_position)
                else:
                    # Default to 70% for SOAP note
                    default_sash = int(total_height * 0.7)
                    soap_paned.sashpos(0, default_sash)
            except tk.TclError as e:
                logger.debug(f"Could not restore sash position: {e}")

    def _get_stored_analysis(self, attr_name: str) -> dict | None:
        """Retrieve a stored analysis, checking WorkflowUI then main app.

        Args:
            attr_name: The attribute name (e.g. '_last_medication_analysis')

        Returns:
            The analysis dict, or None if not found
        """
        analysis = getattr(self.parent, attr_name, None)
        if not analysis:
            main_app = getattr(self.parent, 'parent', None)
            if main_app:
                analysis = getattr(main_app, attr_name, None)
        return analysis

    def _show_simple_analysis_dialog(self, title: str, result: str,
                                     width: int = 600, height: int = 500) -> None:
        """Show a simple read-only text dialog for analysis results.

        Args:
            title: Dialog title
            result: Text content to display
            width: Dialog width
            height: Dialog height
        """
        dialog = tk.Toplevel(self.parent)
        dialog.title(title)
        dialog.geometry(f"{width}x{height}")
        dialog.transient(self.parent)

        frame = ttk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text_widget = tk.Text(
            frame, wrap=tk.WORD, yscrollcommand=scrollbar.set,
            font=("Segoe UI", 10)
        )
        text_widget.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_widget.yview)

        text_widget.insert('1.0', result)
        text_widget.config(state='disabled')

        ttk.Button(
            dialog, text="Close", command=dialog.destroy, bootstyle="secondary"
        ).pack(pady=10)

        dialog.update_idletasks()
        x = self.parent.winfo_x() + (self.parent.winfo_width() - dialog.winfo_width()) // 2
        y = self.parent.winfo_y() + (self.parent.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

    def _open_medication_details(self) -> None:
        """Open full medication results dialog with current analysis."""
        try:
            analysis = self._get_stored_analysis('_last_medication_analysis')
            if not analysis:
                if hasattr(self.parent, 'status_manager'):
                    self.parent.status_manager.warning("No medication analysis available. Generate a SOAP note first.")
                return

            result = analysis.get('result', '')
            if not result:
                if hasattr(self.parent, 'status_manager'):
                    self.parent.status_manager.warning("Medication analysis is empty")
                return

            from ui.dialogs.medication_results_dialog import MedicationResultsDialog
            dialog = MedicationResultsDialog(self.parent)
            dialog.show_results(
                result,
                analysis.get('analysis_type', 'comprehensive'),
                'SOAP Note',
                analysis.get('metadata', {})
            )
        except Exception as e:
            logger.error(f"Error opening medication details: {e}", exc_info=True)
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error(f"Failed to open medication details: {str(e)}")

    def _open_diagnostic_details(self) -> None:
        """Open full diagnostic results dialog with current analysis."""
        try:
            analysis = self._get_stored_analysis('_last_diagnostic_analysis')
            if not analysis:
                if hasattr(self.parent, 'status_manager'):
                    self.parent.status_manager.warning("No diagnostic analysis available. Generate a SOAP note first.")
                return

            result = analysis.get('result', 'No analysis available')
            self._show_simple_analysis_dialog("Differential Diagnosis Details", result)

        except Exception as e:
            logger.error(f"Error opening diagnostic details: {e}")
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error("Failed to open diagnostic details")

    def _open_compliance_details(self) -> None:
        """Open full compliance results dialog with current analysis."""
        try:
            analysis = self._get_stored_analysis('_last_compliance_analysis')
            if not analysis:
                if hasattr(self.parent, 'status_manager'):
                    self.parent.status_manager.warning("No compliance analysis available. Generate a SOAP note first.")
                return

            result = analysis.get('result', '')
            if not result:
                if hasattr(self.parent, 'status_manager'):
                    self.parent.status_manager.warning("Compliance analysis is empty")
                return

            # Try dedicated dialog first
            try:
                from ui.dialogs.compliance_results_dialog import ComplianceResultsDialog
                dialog = ComplianceResultsDialog(self.parent)
                dialog.show_results(result, analysis.get('metadata', {}))
                return
            except ImportError:
                pass

            self._show_simple_analysis_dialog(
                "Clinical Guidelines Compliance Details", result, 700, 550
            )

        except Exception as e:
            logger.error(f"Error opening compliance details: {e}")
            if hasattr(self.parent, 'status_manager'):
                self.parent.status_manager.error("Failed to open compliance details")

    def show_medication_analysis_tab(self) -> None:
        """Switch to the Medication Analysis tab within the SOAP panel."""
        try:
            # Make sure analysis panel is expanded
            if hasattr(self, '_analysis_collapsed') and self._analysis_collapsed:
                self._toggle_analysis_panel()

            # Find the analysis notebook
            analysis_content = self.components.get('analysis_content')
            if analysis_content:
                for child in analysis_content.winfo_children():
                    if hasattr(child, 'select') and hasattr(child, 'tabs'):
                        tabs = child.tabs()
                        if tabs:
                            child.select(tabs[0])  # Medication is first tab
                        break
        except tk.TclError as e:
            logger.debug(f"Could not switch to medication tab: {e}")

    def show_differential_analysis_tab(self) -> None:
        """Switch to the Differential Diagnosis tab within the SOAP panel."""
        try:
            # Make sure analysis panel is expanded
            if hasattr(self, '_analysis_collapsed') and self._analysis_collapsed:
                self._toggle_analysis_panel()

            # Find the analysis notebook
            analysis_content = self.components.get('analysis_content')
            if analysis_content:
                for child in analysis_content.winfo_children():
                    if hasattr(child, 'select') and hasattr(child, 'tabs'):
                        tabs = child.tabs()
                        if len(tabs) > 1:
                            child.select(tabs[1])  # Differential is second tab
                        break
        except tk.TclError as e:
            logger.debug(f"Could not switch to differential tab: {e}")

    def show_compliance_analysis_tab(self) -> None:
        """Switch to the Clinical Guidelines tab within the SOAP panel."""
        try:
            # Make sure analysis panel is expanded
            if hasattr(self, '_analysis_collapsed') and self._analysis_collapsed:
                self._toggle_analysis_panel()

            # Find the analysis notebook
            analysis_content = self.components.get('analysis_content')
            if analysis_content:
                for child in analysis_content.winfo_children():
                    if hasattr(child, 'select') and hasattr(child, 'tabs'):
                        tabs = child.tabs()
                        if len(tabs) > 2:
                            child.select(tabs[2])  # Compliance is third tab
                        break
        except tk.TclError as e:
            logger.debug(f"Could not switch to compliance tab: {e}")

    def load_saved_analyses(self, recording_id: int) -> Dict[str, Any]:
        """Load saved medication, differential, and compliance analyses from database.

        Args:
            recording_id: The recording ID to load analyses for

        Returns:
            Dict with 'medication', 'differential', and 'compliance' keys,
            each containing the analysis result dict or None
        """
        try:
            from processing.analysis_storage import get_analysis_storage

            storage = get_analysis_storage()
            analyses = storage.get_analyses_for_recording(recording_id)

            # Update the analysis panels with saved data
            if analyses.get('medication'):
                self._update_medication_panel_from_saved(analyses['medication'])

            if analyses.get('differential'):
                self._update_differential_panel_from_saved(analyses['differential'])

            if analyses.get('compliance'):
                self._update_compliance_panel_from_saved(analyses['compliance'])

            return analyses

        except Exception as e:
            logger.error(f"Failed to load saved analyses for recording {recording_id}: {e}")
            return {"medication": None, "differential": None, "compliance": None}

    def _update_analysis_panel_from_saved(self, analysis_type: str, analysis: Dict[str, Any]) -> None:
        """Update an analysis panel with saved analysis data.

        Args:
            analysis_type: One of 'medication', 'differential', 'compliance'
            analysis: Saved analysis dict from database
        """
        config = _ANALYSIS_TYPES.get(analysis_type)
        if not config:
            logger.warning(f"Unknown analysis type: {analysis_type}")
            return

        try:
            widget = self.components.get(config["widget_key"])
            if not widget:
                return

            result_text = analysis.get('result_text', '')
            metadata = analysis.get('metadata_json', {}) or {}

            # Store for View Details button
            stored = {'result': result_text, 'metadata': metadata}
            if analysis_type == "medication":
                stored['analysis_type'] = analysis.get('analysis_subtype', 'comprehensive')
            setattr(self.parent, config["attr"], stored)

            # Format and display
            try:
                from ui.components.analysis_panel_formatter import AnalysisPanelFormatter
                formatter = AnalysisPanelFormatter(widget)
                getattr(formatter, config["formatter_method"])(result_text, metadata)
            except (ImportError, tk.TclError):
                widget.config(state='normal')
                widget.delete('1.0', 'end')
                widget.insert('1.0', result_text)
                widget.config(state='disabled')

            # Enable View Details button
            view_btn = self.components.get(config["btn_key"])
            if view_btn:
                view_btn.config(state='normal')

        except Exception as e:
            logger.error(f"Failed to update {analysis_type} panel from saved: {e}")

    def _update_medication_panel_from_saved(self, analysis: Dict[str, Any]) -> None:
        """Update medication analysis panel with saved analysis."""
        self._update_analysis_panel_from_saved("medication", analysis)

    def _update_differential_panel_from_saved(self, analysis: Dict[str, Any]) -> None:
        """Update differential analysis panel with saved analysis."""
        self._update_analysis_panel_from_saved("differential", analysis)

    def _update_compliance_panel_from_saved(self, analysis: Dict[str, Any]) -> None:
        """Update compliance analysis panel with saved analysis."""
        self._update_analysis_panel_from_saved("compliance", analysis)

    def clear_analysis_panels(self) -> None:
        """Clear the medication, differential, and compliance analysis panels."""
        try:
            for config in _ANALYSIS_TYPES.values():
                # Clear text widget
                widget = self.components.get(config["widget_key"])
                if widget:
                    widget.config(state='normal')
                    widget.delete('1.0', 'end')
                    widget.insert('1.0', config["empty_msg"])
                    widget.config(state='disabled')

                # Disable View Details button
                view_btn = self.components.get(config["btn_key"])
                if view_btn:
                    view_btn.config(state='disabled')

                # Clear stored analysis
                if hasattr(self.parent, config["attr"]):
                    setattr(self.parent, config["attr"], None)

        except tk.TclError as e:
            logger.debug(f"Error clearing analysis panels: {e}")
