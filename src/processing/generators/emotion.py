"""
Emotion Generator Module

Handles emotional assessment display in the analysis panel.
This mixin does NOT use AI agents - it formats and displays
pre-computed emotion data from Modulate.ai transcriptions.
"""

from typing import TYPE_CHECKING

from utils.structured_logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from core.app import MedicalAssistantApp


class EmotionGeneratorMixin:
    """Mixin for emotional assessment display functionality."""

    app: "MedicalAssistantApp"

    def _get_emotion_widget(self):
        """Get the emotion analysis text widget from UI components."""
        widget = getattr(self.app, 'emotion_analysis_text', None)
        if not widget and hasattr(self.app, 'ui'):
            widget = self.app.ui.components.get('emotion_analysis_text')
        return widget

    def _run_emotion_to_panel(self, emotion_data: dict) -> None:
        """Display emotion analysis results in the analysis panel.

        Formats pre-computed emotion data and updates the emotion
        analysis panel widget. No AI agent is invoked.

        Args:
            emotion_data: Pre-computed emotion data from Modulate.ai
        """
        logger.info("_run_emotion_to_panel called")
        self.app.status_manager.info("Displaying emotional assessment...")

        widget = self._get_emotion_widget()
        if not widget:
            logger.warning("Emotion analysis panel not available")
            self.app.status_manager.warning("Emotion panel not available")
            return

        if not emotion_data:
            self._update_analysis_panel(
                widget,
                "No emotion data available.\n\n"
                "Emotion analysis requires a Modulate.ai transcription."
            )
            return

        # Show loading indicator
        self._update_analysis_panel(
            widget,
            "Formatting emotional assessment..."
        )

        try:
            # Update panel with formatted results on the main thread
            self.app.after(0, lambda: self._update_emotion_panel_formatted(emotion_data))
        except Exception as e:
            logger.error(f"Emotion panel display failed: {e}")
            error_msg = str(e)
            self.app.after(0, lambda: self._update_analysis_panel(
                widget,
                f"Error: {error_msg}\n\n"
                "Failed to display emotion data."
            ))

    def _update_emotion_panel_formatted(self, emotion_data: dict) -> None:
        """Update emotion panel with formatted content.

        Uses format_emotion_for_panel from ai.emotion_processor to
        render emotion data into the analysis panel widget.

        Args:
            emotion_data: Pre-computed emotion data to format and display
        """
        try:
            from ai.emotion_processor import format_emotion_for_panel

            widget = self._get_emotion_widget()
            if not widget:
                logger.warning("Emotion widget not found during panel update")
                return

            # format_emotion_for_panel returns a formatted string
            formatted_text = format_emotion_for_panel(emotion_data)

            # Update the widget
            widget.config(state='normal')
            widget.delete('1.0', 'end')
            widget.insert('end', formatted_text)
            widget.config(state='disabled')

            # Enable View Details button if available
            if hasattr(self.app, 'ui') and hasattr(self.app.ui, 'components'):
                view_btn = self.app.ui.components.get('emotion_view_details_btn')
                if view_btn:
                    view_btn.config(state='normal')

            # Store for later access (View Details dialog, saved recordings)
            stored = {'result': formatted_text, 'metadata': emotion_data}
            self.app._last_emotion_analysis = stored
            if hasattr(self.app, 'ui'):
                self.app.ui._last_emotion_analysis = stored

            self.app.status_manager.success("Emotional assessment displayed")

        except Exception as e:
            logger.error(f"Failed to format emotion panel: {e}")
            fallback = str(emotion_data) if emotion_data else "No emotion data."
            w = self._get_emotion_widget()
            if w:
                self._update_analysis_panel(w, fallback)


__all__ = ["EmotionGeneratorMixin"]
