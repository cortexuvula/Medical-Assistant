"""
Provider Configuration Controller Module

Handles AI and STT provider configuration including provider availability,
dropdown management, selection changes, and transcription fallback handling.

This controller extracts provider configuration logic from the main App class
to improve maintainability and separation of concerns.
"""

import logging
from typing import TYPE_CHECKING, Tuple, List

from settings.settings import SETTINGS, save_settings

if TYPE_CHECKING:
    from core.app import MedicalDictationApp

logger = logging.getLogger(__name__)


class ProviderConfigController:
    """Controller for managing provider configuration.

    This class coordinates:
    - AI provider availability checking
    - STT provider availability checking
    - Provider dropdown population and selection
    - Provider change event handling
    - Microphone selection
    - Transcription fallback notifications
    """

    def __init__(self, app: 'MedicalDictationApp'):
        """Initialize the provider configuration controller.

        Args:
            app: Reference to the main application instance
        """
        self.app = app

    def get_available_ai_providers(self) -> Tuple[List[str], List[str]]:
        """Get list of AI providers that have API keys configured.

        Returns:
            tuple: (list of provider keys, list of display names)
        """
        from utils.security import get_security_manager
        security_mgr = get_security_manager()

        # All possible AI providers with their display names
        all_providers = [
            ("openai", "OpenAI"),
            ("grok", "Grok"),
            ("perplexity", "Perplexity"),
            ("anthropic", "Anthropic"),
            ("gemini", "Gemini"),
        ]

        available = []
        display_names = []

        for provider_key, display_name in all_providers:
            api_key = security_mgr.get_api_key(provider_key)
            if api_key:
                available.append(provider_key)
                display_names.append(display_name)

        # If no providers have keys, show all (fallback)
        if not available:
            logging.warning("No AI providers have API keys configured, showing all options")
            available = [p[0] for p in all_providers]
            display_names = [p[1] for p in all_providers]

        return available, display_names

    def get_available_stt_providers(self) -> Tuple[List[str], List[str]]:
        """Get list of STT providers that have API keys configured.

        Returns:
            tuple: (list of provider keys, list of display names)
        """
        from utils.security import get_security_manager
        security_mgr = get_security_manager()

        # All possible STT providers with their display names
        all_providers = [
            ("groq", "GROQ"),
            ("elevenlabs", "ElevenLabs"),
            ("deepgram", "Deepgram"),
        ]

        available = []
        display_names = []

        for provider_key, display_name in all_providers:
            api_key = security_mgr.get_api_key(provider_key)
            if api_key:
                available.append(provider_key)
                display_names.append(display_name)

        # If no providers have keys, show all (fallback)
        if not available:
            logging.warning("No STT providers have API keys configured, showing all options")
            available = [p[0] for p in all_providers]
            display_names = [p[1] for p in all_providers]

        return available, display_names

    def initialize_provider_selections(self) -> None:
        """Initialize provider dropdown selections based on available providers."""
        # Set AI provider - find index in available providers list
        ai_provider = SETTINGS.get("ai_provider", "openai")
        if ai_provider in self.app._available_ai_providers:
            index = self.app._available_ai_providers.index(ai_provider)
            self.app.provider_combobox.current(index)
        elif self.app._available_ai_providers:
            # Fall back to first available provider
            self.app.provider_combobox.current(0)
            # Update settings to match
            SETTINGS["ai_provider"] = self.app._available_ai_providers[0]
            save_settings(SETTINGS)

        # Set STT provider - find index in available providers list
        stt_provider = SETTINGS.get("stt_provider", "groq")
        if stt_provider in self.app._available_stt_providers:
            index = self.app._available_stt_providers.index(stt_provider)
            self.app.stt_combobox.current(index)
        elif self.app._available_stt_providers:
            # Fall back to first available provider
            self.app.stt_combobox.current(0)
            # Update settings to match
            SETTINGS["stt_provider"] = self.app._available_stt_providers[0]
            save_settings(SETTINGS)

    def on_provider_change(self, event=None) -> None:
        """Handle AI provider dropdown selection change.

        Args:
            event: Tkinter event (unused but required for binding)
        """
        selected_index = self.app.provider_combobox.current()

        # Use the dynamic available providers list
        if 0 <= selected_index < len(self.app._available_ai_providers):
            selected_provider = self.app._available_ai_providers[selected_index]
            display_name = self.app._ai_display_names[selected_index]
            SETTINGS["ai_provider"] = selected_provider
            save_settings(SETTINGS)
            self.app.update_status(f"AI Provider set to {display_name}")

    def on_stt_change(self, event=None) -> None:
        """Handle STT provider dropdown selection change.

        Args:
            event: Tkinter event (unused but required for binding)
        """
        selected_index = self.app.stt_combobox.current()

        # Use the dynamic available providers list
        if 0 <= selected_index < len(self.app._available_stt_providers):
            provider = self.app._available_stt_providers[selected_index]
            display_name = self.app._stt_display_names[selected_index]

            # Update settings
            SETTINGS["stt_provider"] = provider
            save_settings(SETTINGS)

            # Update the audio handler with the new provider
            self.app.audio_handler.set_stt_provider(provider)

            # Update status with the new provider info
            self.app.status_manager.update_provider_info()
            self.app.update_status(f"Speech-to-Text provider set to {display_name}")

    def on_microphone_change(self, event=None) -> None:
        """Handle microphone dropdown selection change.

        Args:
            event: Tkinter event (unused but required for binding)
        """
        selected_mic = self.app.mic_combobox.get()
        if selected_mic and selected_mic != "No microphones found":
            # Update the settings with the selected microphone
            SETTINGS["selected_microphone"] = selected_mic
            save_settings(SETTINGS)
            logging.info(f"Saved selected microphone: {selected_mic}")

    def refresh_provider_dropdowns(self) -> None:
        """Refresh the provider dropdowns after API keys have been updated.

        This should be called after the API keys dialog is closed to update
        the available providers in the dropdowns.
        """
        # Get current selections
        current_ai = SETTINGS.get("ai_provider", "openai")
        current_stt = SETTINGS.get("stt_provider", "groq")

        # Refresh available providers
        self.app._available_ai_providers, self.app._ai_display_names = self.get_available_ai_providers()
        self.app._available_stt_providers, self.app._stt_display_names = self.get_available_stt_providers()

        # Update combobox values
        self.app.provider_combobox['values'] = self.app._ai_display_names
        self.app.stt_combobox['values'] = self.app._stt_display_names

        # Re-select current provider if still available, otherwise select first
        if current_ai in self.app._available_ai_providers:
            index = self.app._available_ai_providers.index(current_ai)
            self.app.provider_combobox.current(index)
        elif self.app._available_ai_providers:
            self.app.provider_combobox.current(0)
            SETTINGS["ai_provider"] = self.app._available_ai_providers[0]
            save_settings(SETTINGS)

        if current_stt in self.app._available_stt_providers:
            index = self.app._available_stt_providers.index(current_stt)
            self.app.stt_combobox.current(index)
        elif self.app._available_stt_providers:
            self.app.stt_combobox.current(0)
            SETTINGS["stt_provider"] = self.app._available_stt_providers[0]
            save_settings(SETTINGS)
            # Update audio handler
            self.app.audio_handler.set_stt_provider(self.app._available_stt_providers[0])

        logging.info(f"Provider dropdowns refreshed. AI: {self.app._ai_display_names}, STT: {self.app._stt_display_names}")

    def on_transcription_fallback(self, primary_provider: str, fallback_provider: str) -> None:
        """Handle notification of transcription service fallback.

        Args:
            primary_provider: Name of the primary provider that failed
            fallback_provider: Name of the fallback provider being used
        """
        # Create readable provider names for display
        provider_names = {
            "elevenlabs": "ElevenLabs",
            "deepgram": "Deepgram",
            "groq": "GROQ",
            "google": "Google"
        }

        primary_display = provider_names.get(primary_provider, primary_provider)
        fallback_display = provider_names.get(fallback_provider, fallback_provider)

        # Update status with warning about fallback
        message = f"{primary_display} transcription failed. Falling back to {fallback_display}."

        # Update STT provider dropdown to reflect actual service being used
        try:
            stt_providers = ["groq", "elevenlabs", "deepgram"]
            fallback_index = stt_providers.index(fallback_provider)
            self.app.after(0, lambda: [
                self.app.status_manager.warning(message),
                self.app.stt_combobox.current(fallback_index)
            ])
        except (ValueError, IndexError):
            # Just show the warning if we can't update the dropdown
            self.app.after(0, lambda: self.app.status_manager.warning(message))
