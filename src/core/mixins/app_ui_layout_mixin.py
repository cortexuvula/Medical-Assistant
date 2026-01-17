"""
App UI Layout Mixin

Provides UI layout methods for the MedicalDictationApp.
Handles collapsible sections, sash positioning, and layout adjustments.
Extracted from app.py for better separation of concerns.
"""

import tkinter as tk
from typing import TYPE_CHECKING

from settings.settings import SETTINGS, save_settings
from utils.structured_logging import get_logger

if TYPE_CHECKING:
    from ui.workflow_ui import WorkflowUI

logger = get_logger(__name__)


class AppUiLayoutMixin:
    """Mixin providing UI layout methods for MedicalDictationApp.

    This mixin expects the following attributes on the class:
    - ui: WorkflowUI instance
    - _bottom_collapsed: Boolean for collapse state
    - _bottom_content: Paned window widget
    - _bottom_collapse_btn: Collapse button widget
    - _last_height: Integer for height tracking
    - content_paned: PanedWindow widget
    - notebook: Notebook widget
    """

    def _toggle_bottom_section(self) -> None:
        """Toggle collapse/expand of the entire bottom section (Chat + Analysis)."""
        self._bottom_collapsed = not self._bottom_collapsed

        # Save state to settings
        SETTINGS["bottom_section_collapsed"] = self._bottom_collapsed
        save_settings(SETTINGS)

        if self._bottom_collapsed:
            # Collapse: hide the content
            self._bottom_content.pack_forget()
            self._bottom_collapse_btn.config(text="▶")
        else:
            # Expand: show the content
            self._bottom_content.pack(fill=tk.BOTH, expand=True)
            self._bottom_collapse_btn.config(text="▼")

        # Adjust the sash position
        self._adjust_bottom_sash()

    def _on_content_paned_configure(self, event=None) -> None:
        """Handle resize events on content_paned to maintain sash proportions."""
        try:
            content_paned = self.ui.components.get('content_paned')
            if not content_paned:
                return

            new_height = content_paned.winfo_height()
            # Only adjust if height changed significantly (avoid jitter)
            if abs(new_height - self._last_height) > 20:
                self._last_height = new_height
                # Use after to debounce rapid resize events
                if hasattr(self, '_resize_after_id'):
                    self.after_cancel(self._resize_after_id)
                self._resize_after_id = self.after(50, self._adjust_bottom_sash)
        except Exception:
            pass

    def _adjust_bottom_sash(self) -> None:
        """Adjust the content_paned sash based on bottom section collapse state."""
        try:
            content_paned = self.ui.components.get('content_paned')
            if not content_paned:
                return

            content_paned.update_idletasks()
            total_height = content_paned.winfo_height()

            if total_height <= 1:
                # Window not fully rendered yet, retry later
                self.after(200, self._adjust_bottom_sash)
                return

            if self._bottom_collapsed:
                # Collapsed - just header visible (~50px for header + padding)
                new_sash_pos = total_height - 50
            else:
                # Expanded - 55% for notebook, 45% for bottom (more space for bottom panels)
                new_sash_pos = int(total_height * 0.55)

            content_paned.sashpos(0, new_sash_pos)
            self._last_height = total_height
            logger.debug(f"Set sash position: {new_sash_pos} of {total_height} (collapsed={self._bottom_collapsed})")

        except Exception as e:
            logger.debug(f"Could not adjust bottom sash: {e}")

    def _adjust_horizontal_sash(self) -> None:
        """Adjust the horizontal sash for Chat (25%) vs Analysis (75%) split."""
        try:
            bottom_paned = self.ui.components.get('bottom_paned')
            if not bottom_paned:
                return

            bottom_paned.update_idletasks()
            total_width = bottom_paned.winfo_width()

            if total_width <= 1:
                # Not rendered yet, retry
                self.after(200, self._adjust_horizontal_sash)
                return

            # Chat gets 25%, Analysis gets 75%
            sash_pos = int(total_width * 0.25)
            bottom_paned.sashpos(0, sash_pos)
            logger.debug(f"Set horizontal sash: {sash_pos} of {total_width}")

        except Exception as e:
            logger.debug(f"Could not adjust horizontal sash: {e}")

    def on_workflow_changed(self, workflow: str) -> None:
        """Handle workflow tab changes.

        Args:
            workflow: The current workflow tab ("record", "process", "generate", or "recordings")
        """
        logger.info(f"Workflow changed to: {workflow}")

        # Update UI based on workflow
        if workflow == "record":
            # Focus on transcript tab
            self.notebook.select(0)
        elif workflow == "process":
            # Ensure there's text to process
            if not self.transcript_text.get("1.0", tk.END).strip():
                self.status_manager.info("Load audio or paste text to process")
        elif workflow == "generate":
            # Check if we have content to generate from
            if not self.transcript_text.get("1.0", tk.END).strip():
                self.status_manager.info("No transcript available for document generation")
            else:
                # Show suggestions based on available content
                self._show_generation_suggestions()
        elif workflow == "recordings":
            # Show status when refreshing recordings
            self.status_manager.info("Refreshing recordings list...")

    def _show_generation_suggestions(self) -> None:
        """Show smart suggestions for document generation."""
        suggestions = []

        # Check what content is available
        has_transcript = bool(self.transcript_text.get("1.0", tk.END).strip())
        has_soap = bool(self.soap_text.get("1.0", tk.END).strip())
        has_referral = bool(self.referral_text.get("1.0", tk.END).strip())

        if has_transcript and not has_soap:
            suggestions.append("Create SOAP Note from transcript")

        if has_soap and not has_referral:
            suggestions.append("Generate Referral from SOAP note")

        if has_transcript or has_soap:
            suggestions.append("Create Letter from available content")

        # Update suggestions in UI if available
        if hasattr(self.ui, 'show_suggestions'):
            self.ui.show_suggestions(suggestions)


__all__ = ["AppUiLayoutMixin"]
