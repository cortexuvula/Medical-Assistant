"""
App Dialog Mixin

Provides dialog-related methods for the MedicalDictationApp.
Extracted from app.py for better separation of concerns.
"""

import os
from typing import TYPE_CHECKING, Optional, Tuple
from tkinter import NORMAL, DISABLED

from ui.dialogs.dialogs import (
    show_about_dialog,
    show_shortcuts_dialog,
    show_letter_options_dialog,
)
from ui.dialogs.unified_settings_dialog import (
    show_unified_settings_dialog,
    UnifiedSettingsDialog,
)
from utils.constants import (
    PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_GEMINI,
    STT_ELEVENLABS, STT_DEEPGRAM, STT_GROQ, STT_MODULATE
)
from utils.structured_logging import get_logger

if TYPE_CHECKING:
    from audio.audio import AudioHandler

logger = get_logger(__name__)


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

        # Update UI components based on API availability
        from utils.security import get_security_manager
        security_manager = get_security_manager()
        has_any_llm = any([
            security_manager.get_api_key(PROVIDER_OPENAI),
            security_manager.get_api_key(PROVIDER_ANTHROPIC),
            security_manager.get_api_key(PROVIDER_GEMINI),
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

        self._refresh_audio_handler()
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
        """Show ElevenLabs settings in Preferences dialog."""
        show_unified_settings_dialog(
            self, initial_tab=UnifiedSettingsDialog.TAB_AUDIO_STT,
            initial_subtab=UnifiedSettingsDialog.SUBTAB_ELEVENLABS
        )
        self._refresh_audio_handler()

    def show_deepgram_settings(self) -> None:
        """Show Deepgram settings in Preferences dialog."""
        show_unified_settings_dialog(
            self, initial_tab=UnifiedSettingsDialog.TAB_AUDIO_STT,
            initial_subtab=UnifiedSettingsDialog.SUBTAB_DEEPGRAM
        )
        self._refresh_audio_handler()

    def show_groq_settings(self) -> None:
        """Show Groq settings in Preferences dialog."""
        show_unified_settings_dialog(
            self, initial_tab=UnifiedSettingsDialog.TAB_AUDIO_STT,
            initial_subtab=UnifiedSettingsDialog.SUBTAB_GROQ
        )
        self._refresh_audio_handler()

    def show_translation_settings(self) -> None:
        """Show Translation settings in Preferences dialog."""
        show_unified_settings_dialog(
            self, initial_tab=UnifiedSettingsDialog.TAB_AI_MODELS,
            initial_subtab=UnifiedSettingsDialog.SUBTAB_TRANSLATION
        )

    def show_tts_settings(self) -> None:
        """Show TTS settings in Preferences dialog."""
        show_unified_settings_dialog(
            self, initial_tab=UnifiedSettingsDialog.TAB_AUDIO_STT,
            initial_subtab=UnifiedSettingsDialog.SUBTAB_TTS
        )
        self._refresh_audio_handler()

    def _refresh_audio_handler(self) -> None:
        """Refresh the audio handler after settings changes."""
        from utils.security import get_security_manager
        security_manager = get_security_manager()
        self.elevenlabs_api_key = security_manager.get_api_key(STT_ELEVENLABS) or ""
        self.deepgram_api_key = security_manager.get_api_key(STT_DEEPGRAM) or ""
        self.groq_api_key = security_manager.get_api_key(STT_GROQ) or ""
        self.modulate_api_key = security_manager.get_api_key(STT_MODULATE) or ""
        from audio.audio import AudioHandler
        self.audio_handler = AudioHandler(
            elevenlabs_api_key=self.elevenlabs_api_key,
            deepgram_api_key=self.deepgram_api_key,
            groq_api_key=self.groq_api_key,
            modulate_api_key=self.modulate_api_key,
            recognition_language=self.recognition_language
        )

    def record_prefix_audio(self) -> None:
        """Shows a dialog to record and save a prefix audio file."""
        self.audio_dialog_manager.show_prefix_recording_dialog()


__all__ = ["AppDialogMixin"]
