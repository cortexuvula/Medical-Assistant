"""
App Dialog Mixin

Provides dialog-related methods for the MedicalDictationApp.
Extracted from app.py for better separation of concerns.
"""

import os
import logging
from typing import TYPE_CHECKING, Optional, Tuple
from tkinter import NORMAL, DISABLED

from ui.dialogs.dialogs import (
    show_about_dialog,
    show_shortcuts_dialog,
    show_letter_options_dialog,
    show_elevenlabs_settings_dialog,
    show_deepgram_settings_dialog,
    show_groq_settings_dialog
)

if TYPE_CHECKING:
    from audio.audio import AudioHandler

logger = logging.getLogger(__name__)


class AppDialogMixin:
    """Mixin providing dialog-related methods for MedicalDictationApp.

    This mixin expects the following attributes on the class:
    - menu_manager: MenuManager instance
    - audio_handler: AudioHandler instance
    - status_manager: StatusManager instance
    - refine_button, improve_button, soap_button: Button widgets
    - deepgram_api_key, elevenlabs_api_key, groq_api_key: API key strings
    - recognition_language: Language code string
    """

    def show_api_keys_dialog(self) -> None:
        """Shows a dialog to update API keys and updates the .env file."""
        self.menu_manager.show_api_keys_dialog()

        # Update local properties
        self.deepgram_api_key = os.getenv("DEEPGRAM_API_KEY", "")
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")

        # Update UI components based on API availability
        from utils.security import get_security_manager
        security_manager = get_security_manager()
        has_any_llm = any([
            security_manager.get_api_key("openai"),
            security_manager.get_api_key("anthropic"),
            security_manager.get_api_key("gemini"),
            os.getenv("OLLAMA_API_URL")
        ])

        if has_any_llm:
            if self.refine_button:
                self.refine_button.config(state=NORMAL)
            if self.improve_button:
                self.improve_button.config(state=NORMAL)
            if self.soap_button:
                self.soap_button.config(state=NORMAL)
        else:
            if self.refine_button:
                self.refine_button.config(state=DISABLED)
            if self.improve_button:
                self.improve_button.config(state=DISABLED)
            if self.soap_button:
                self.soap_button.config(state=DISABLED)

        # Reinitialize audio handler with new API keys
        from audio.audio import AudioHandler
        self.audio_handler = AudioHandler(
            elevenlabs_api_key=self.elevenlabs_api_key,
            deepgram_api_key=self.deepgram_api_key,
            groq_api_key=self.groq_api_key,
            recognition_language=self.recognition_language
        )

        self.status_manager.success("API keys updated successfully")

    def show_about(self) -> None:
        """Show the About dialog."""
        show_about_dialog(self)

    def show_shortcuts(self) -> None:
        """Show the keyboard shortcuts dialog."""
        show_shortcuts_dialog(self)

    def show_letter_options_dialog(self) -> Optional[Tuple]:
        """Show the letter options dialog."""
        return show_letter_options_dialog(self)

    def show_elevenlabs_settings(self) -> None:
        """Show ElevenLabs settings dialog."""
        show_elevenlabs_settings_dialog(self)

        # Refresh the audio handler with potentially new settings
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "")
        from audio.audio import AudioHandler
        self.audio_handler = AudioHandler(
            elevenlabs_api_key=self.elevenlabs_api_key,
            deepgram_api_key=self.deepgram_api_key,
            groq_api_key=self.groq_api_key,
            recognition_language=self.recognition_language
        )
        self.status_manager.success("ElevenLabs settings saved successfully")

    def show_deepgram_settings(self) -> None:
        """Show dialog to configure Deepgram settings."""
        show_deepgram_settings_dialog(self)

        # Refresh the audio handler with potentially new settings
        from audio.audio import AudioHandler
        self.audio_handler = AudioHandler(
            elevenlabs_api_key=self.elevenlabs_api_key,
            deepgram_api_key=self.deepgram_api_key,
            groq_api_key=self.groq_api_key,
            recognition_language=self.recognition_language
        )
        self.status_manager.success("Deepgram settings saved successfully")

    def show_groq_settings(self) -> None:
        """Show dialog to configure Groq settings."""
        show_groq_settings_dialog(self)

        # Refresh the audio handler with potentially new settings
        from audio.audio import AudioHandler
        self.audio_handler = AudioHandler(
            elevenlabs_api_key=self.elevenlabs_api_key,
            deepgram_api_key=self.deepgram_api_key,
            groq_api_key=self.groq_api_key,
            recognition_language=self.recognition_language
        )
        self.status_manager.success("Groq settings saved successfully")

    def show_translation_settings(self) -> None:
        """Show dialog to configure translation settings."""
        from ui.dialogs.dialogs import show_translation_settings_dialog
        show_translation_settings_dialog(self)
        self.status_manager.success("Translation settings saved successfully")

    def show_tts_settings(self) -> None:
        """Show dialog to configure TTS settings."""
        from ui.dialogs.dialogs import show_tts_settings_dialog
        show_tts_settings_dialog(self)
        self.status_manager.success("TTS settings saved successfully")

    def record_prefix_audio(self) -> None:
        """Shows a dialog to record and save a prefix audio file."""
        self.audio_dialog_manager.show_prefix_recording_dialog()


__all__ = ["AppDialogMixin"]
