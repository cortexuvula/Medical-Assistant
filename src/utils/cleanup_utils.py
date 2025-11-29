"""
Cleanup utilities for the Medical Dictation application.

This module provides centralized functions for cleaning up application state,
including text widgets, audio segments, and other application data.
"""

import tkinter as tk
import logging
from typing import Any, TYPE_CHECKING

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
    logging.info("Clearing all application content")
    
    # Clear all text widgets
    widgets_to_clear = [app_instance.transcript_text, app_instance.soap_text, app_instance.referral_text, app_instance.letter_text, app_instance.context_text]
    
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
        logging.info("Cleared all audio via AudioStateManager")
    
    
    # Reset the current recording ID - this ensures we don't update the wrong database record
    if hasattr(app_instance, "current_recording_id"):
        app_instance.current_recording_id = None
        logging.info("Reset current recording ID")
    
    # Update status to inform the user
    if hasattr(app_instance, "update_status"):
        app_instance.update_status("All content cleared", "info")


def clear_text_only(app_instance: "MedicalDictationApp") -> None:
    """
    Clear just the text widgets without affecting audio segments.

    Args:
        app_instance: The main application instance with references to text widgets
    """
    logging.info("Clearing all text content")
    
    # Clear all text widgets
    widgets_to_clear = [app_instance.transcript_text, app_instance.soap_text, app_instance.referral_text, app_instance.letter_text, app_instance.context_text]
    
    # Add chat_text if it exists
    if hasattr(app_instance, 'chat_text'):
        widgets_to_clear.append(app_instance.chat_text)
    
    for widget in widgets_to_clear:
        if widget:
            widget.delete("1.0", tk.END)
            widget.edit_reset()  # Clear undo/redo history
    
    # Update status to inform the user
    if hasattr(app_instance, "update_status"):
        app_instance.update_status("All text cleared", "info")


def clear_audio_only(app_instance: "MedicalDictationApp") -> None:
    """
    Clear just the audio segments without affecting text widgets.

    Args:
        app_instance: The main application instance with references to audio segments
    """
    logging.info("Clearing all audio content")
    
    # Clear audio state via AudioStateManager
    if hasattr(app_instance, "audio_state_manager") and app_instance.audio_state_manager:
        app_instance.audio_state_manager.clear_all()
        logging.info("Cleared all audio via AudioStateManager")
    
    # Clear legacy audio segments (for backward compatibility)
    # Clear file-loaded audio segments
    if hasattr(app_instance, "audio_segments"):
        app_instance.audio_segments = []
    
    # Clear text chunks (for scratch-that functionality)
    if hasattr(app_instance, "text_chunks"):
        app_instance.text_chunks = []
    
    # Update status to inform the user
    if hasattr(app_instance, "update_status"):
        app_instance.update_status("All audio cleared", "info")


def clear_content_except_context(app_instance: "MedicalDictationApp") -> None:
    """
    Clear all content except the context tab text.

    This function is used when starting SOAP recording to preserve context information
    while clearing other content.

    Args:
        app_instance: The main application instance with references to text widgets and audio segments
    """
    logging.info("Clearing all application content except context")
    
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
        logging.info("Cleared all audio via AudioStateManager")
    
    
    # Reset the current recording ID - this ensures we don't update the wrong database record
    if hasattr(app_instance, "current_recording_id"):
        app_instance.current_recording_id = None
        logging.info("Reset current recording ID")
    
    # Update status to inform the user
    if hasattr(app_instance, "update_status"):
        app_instance.update_status("Content cleared (context preserved)", "info")
