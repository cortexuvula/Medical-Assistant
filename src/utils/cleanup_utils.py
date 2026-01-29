"""
Cleanup utilities for the Medical Dictation application.

This module provides centralized functions for cleaning up application state,
including text widgets, audio segments, and other application data.
"""

import tkinter as tk
from typing import Any, TYPE_CHECKING

from utils.structured_logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from core.app import MedicalDictationApp


def clear_all_content(app_instance: "MedicalDictationApp") -> None:
    """
    Clear all content in the application, including text widgets and audio segments.

    This function provides a centralized way to clear all application content
    when starting a new session, loading a new file, or recording a new SOAP note.

    Args:
        app_instance: The main application instance with references to text widgets and audio segments
    """
    logger.info("Clearing all application content")

    # Clear all text widgets
    widgets_to_clear = [app_instance.transcript_text, app_instance.soap_text, app_instance.referral_text, app_instance.letter_text, app_instance.context_text]

    # Add chat_text if it exists
    if hasattr(app_instance, 'chat_text'):
        widgets_to_clear.append(app_instance.chat_text)

    for widget in widgets_to_clear:
        if widget:
            widget.delete("1.0", tk.END)
            widget.edit_reset()  # Clear undo/redo history

    # Clear analysis tabs (Medication Analysis and Differential Diagnosis)
    # These are disabled by default, so we need to enable them first
    if hasattr(app_instance, 'ui') and hasattr(app_instance.ui, 'components'):
        analysis_widgets = [
            app_instance.ui.components.get('medication_analysis_text'),
            app_instance.ui.components.get('differential_analysis_text')
        ]
        for widget in analysis_widgets:
            if widget:
                try:
                    widget.config(state='normal')
                    widget.delete("1.0", tk.END)
                    widget.config(state='disabled')
                except tk.TclError:
                    pass  # Widget may not exist or be destroyed

    # Clear audio state via AudioStateManager
    if hasattr(app_instance, "audio_state_manager") and app_instance.audio_state_manager:
        app_instance.audio_state_manager.clear_all()
        logger.info("Cleared all audio via AudioStateManager")
    
    
    # Reset the current recording ID - this ensures we don't update the wrong database record
    if hasattr(app_instance, "current_recording_id"):
        app_instance.current_recording_id = None
        logger.info("Reset current recording ID")

    # Clear pending analyses (deferred save pattern)
    if hasattr(app_instance, '_pending_medication_analysis'):
        app_instance._pending_medication_analysis = None
    if hasattr(app_instance, '_pending_differential_analysis'):
        app_instance._pending_differential_analysis = None
    logger.debug("Cleared pending analyses")

    # Update status to inform the user
    if hasattr(app_instance, "update_status"):
        app_instance.update_status("All content cleared", "info")


def clear_content_except_context(app_instance: "MedicalDictationApp") -> None:
    """
    Clear all content except the context tab text.

    This function is used when starting SOAP recording to preserve context information
    while clearing other content.

    Args:
        app_instance: The main application instance with references to text widgets and audio segments
    """
    logger.info("Clearing all application content except context")
    
    # Clear all text widgets EXCEPT context
    widgets_to_clear = [app_instance.transcript_text, app_instance.soap_text, app_instance.referral_text, app_instance.letter_text]
    
    # Add chat_text if it exists
    if hasattr(app_instance, 'chat_text'):
        widgets_to_clear.append(app_instance.chat_text)
    
    for widget in widgets_to_clear:
        if widget:
            widget.delete("1.0", tk.END)
            widget.edit_reset()  # Clear undo/redo history
    
    # Clear audio state via AudioStateManager
    if hasattr(app_instance, "audio_state_manager") and app_instance.audio_state_manager:
        app_instance.audio_state_manager.clear_all()
        logger.info("Cleared all audio via AudioStateManager")
    
    
    # Reset the current recording ID - this ensures we don't update the wrong database record
    if hasattr(app_instance, "current_recording_id"):
        app_instance.current_recording_id = None
        logger.info("Reset current recording ID")

    # Clear pending analyses (deferred save pattern)
    if hasattr(app_instance, '_pending_medication_analysis'):
        app_instance._pending_medication_analysis = None
    if hasattr(app_instance, '_pending_differential_analysis'):
        app_instance._pending_differential_analysis = None
    logger.debug("Cleared pending analyses")

    # Update status to inform the user
    if hasattr(app_instance, "update_status"):
        app_instance.update_status("Content cleared (context preserved)", "info")
