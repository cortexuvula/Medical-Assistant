"""
Config Controller Module

Consolidated controller for provider configuration and microphone management.

This controller merges:
- ProviderConfigController: AI/STT provider availability, dropdowns, selection
- MicrophoneController: Microphone detection, listing, refresh, selection

Extracted from the main App class to improve maintainability and separation of concerns.
"""

import logging
import tkinter as tk
from typing import TYPE_CHECKING, Tuple, List

from settings import settings_manager

if TYPE_CHECKING:
    from core.app import MedicalDictationApp

logger = logging.getLogger(__name__)


class ConfigController:
    """Controller for managing provider configuration and microphone functionality.

    This class coordinates:
    - AI provider availability checking
    - STT provider availability checking
    - Provider dropdown population and selection
    - Provider change event handling
    - Microphone detection and listing
    - Microphone refresh with animation
    - Microphone selection management
    - Transcription fallback notifications
    """

    def __init__(self, app: 'MedicalDictationApp'):
        """Initialize the config controller.

        Args:
            app: Reference to the main application instance
        """
        self.app = app
        self._refreshing = False  # For microphone refresh animation

    # =========================================================================
    # AI Provider Methods
    # =========================================================================

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

    # =========================================================================
    # STT Provider Methods
    # =========================================================================

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

    # =========================================================================
    # Provider Selection Initialization
    # =========================================================================

    def initialize_provider_selections(self) -> None:
        """Initialize provider dropdown selections based on available providers."""
        # Set AI provider - find index in available providers list
        ai_provider = settings_manager.get_ai_provider()
        if ai_provider in self.app._available_ai_providers:
            index = self.app._available_ai_providers.index(ai_provider)
            self.app.provider_combobox.current(index)
        elif self.app._available_ai_providers:
            # Fall back to first available provider
            self.app.provider_combobox.current(0)
            # Update settings to match
            settings_manager.set_ai_provider(self.app._available_ai_providers[0])

        # Set STT provider - find index in available providers list
        stt_provider = settings_manager.get_stt_provider()
        if stt_provider in self.app._available_stt_providers:
            index = self.app._available_stt_providers.index(stt_provider)
            self.app.stt_combobox.current(index)
        elif self.app._available_stt_providers:
            # Fall back to first available provider
            self.app.stt_combobox.current(0)
            # Update settings to match
            settings_manager.set_stt_provider(self.app._available_stt_providers[0])

    # =========================================================================
    # Provider Change Handlers
    # =========================================================================

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
            settings_manager.set_ai_provider(selected_provider)
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
            settings_manager.set_stt_provider(provider)

            # Update the audio handler with the new provider
            self.app.audio_handler.set_stt_provider(provider)

            # Update status with the new provider info
            self.app.status_manager.update_provider_info()
            self.app.update_status(f"Speech-to-Text provider set to {display_name}")

    # =========================================================================
    # Provider Dropdown Refresh
    # =========================================================================

    def refresh_provider_dropdowns(self) -> None:
        """Refresh the provider dropdowns after API keys have been updated.

        This should be called after the API keys dialog is closed to update
        the available providers in the dropdowns.
        """
        # Get current selections
        current_ai = settings_manager.get_ai_provider()
        current_stt = settings_manager.get_stt_provider()

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
            settings_manager.set_ai_provider(self.app._available_ai_providers[0])

        if current_stt in self.app._available_stt_providers:
            index = self.app._available_stt_providers.index(current_stt)
            self.app.stt_combobox.current(index)
        elif self.app._available_stt_providers:
            self.app.stt_combobox.current(0)
            settings_manager.set_stt_provider(self.app._available_stt_providers[0])
            # Update audio handler
            self.app.audio_handler.set_stt_provider(self.app._available_stt_providers[0])

        logging.info(f"Provider dropdowns refreshed. AI: {self.app._ai_display_names}, STT: {self.app._stt_display_names}")

    # =========================================================================
    # Transcription Fallback Handler
    # =========================================================================

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

    # =========================================================================
    # Microphone Selection Handler
    # =========================================================================

    def on_microphone_change(self, event=None) -> None:
        """Handle microphone dropdown selection change.

        Args:
            event: Tkinter event (unused but required for binding)
        """
        selected_mic = self.app.mic_combobox.get()
        if selected_mic and selected_mic != "No microphones found":
            # Update the settings with the selected microphone
            settings_manager.set("selected_microphone", selected_mic)
            logging.info(f"Saved selected microphone: {selected_mic}")

    # =========================================================================
    # Microphone Refresh Methods
    # =========================================================================

    def refresh_microphones(self) -> None:
        """Refresh the list of available microphones with simple animation."""
        from utils.utils import get_valid_microphones

        # Find the refresh button
        refresh_btn = self.app.ui.components.get('refresh_btn')

        # If animation is already in progress, return
        if self._refreshing:
            return

        # Mark as refreshing
        self._refreshing = True

        # Disable the button during refresh
        if refresh_btn:
            refresh_btn.config(state=tk.DISABLED)

        # Set wait cursor (use watch which is cross-platform)
        try:
            self.app.config(cursor="watch")
        except tk.TclError:
            # Some platforms may not support cursor changes
            pass

        # Define the animation frames
        animation_chars = ["⟳", "⟲", "↻", "↺", "⟳"]

        def animate_refresh(frame=0):
            """Simple animation function to rotate the refresh button text."""
            if frame < len(animation_chars) * 2:  # Repeat animation twice
                if refresh_btn:
                    refresh_btn.config(text=animation_chars[frame % len(animation_chars)])
                self.app.after(100, lambda: animate_refresh(frame + 1))
            else:
                # Animation complete, perform actual refresh
                logging.debug("Microphone refresh animation complete, starting refresh")
                do_refresh()

        def do_refresh():
            """Perform the actual microphone refresh."""
            try:
                mic_names = get_valid_microphones()

                # Clear existing items
                self.app.mic_combobox['values'] = []

                # Add device names to dropdown
                if mic_names:
                    self.app.mic_combobox['values'] = mic_names

                    # Try to select previously saved microphone or select first one
                    saved_mic = settings_manager.get("selected_microphone", "")
                    if saved_mic and saved_mic in mic_names:
                        self.app.mic_combobox.set(saved_mic)
                    else:
                        # Select first device and save it
                        self.app.mic_combobox.current(0)
                        settings_manager.set("selected_microphone", self.app.mic_combobox.get())
                else:
                    self.app.mic_combobox['values'] = ["No microphones found"]
                    self.app.mic_combobox.current(0)
                    self.app.update_status("No microphones detected", "warning")

            except (OSError, RuntimeError, tk.TclError) as e:
                logging.error(f"Error refreshing microphones: {e}", exc_info=True)
                self.app.update_status("Error detecting microphones", "error")
            finally:
                # Reset animation state
                self._refreshing = False
                logging.debug("Resetting microphone refresh state and cursor")

                # Reset button state and cursor
                if refresh_btn:
                    refresh_btn.config(text="⟳", state=tk.NORMAL)

                # Reset cursor - try multiple approaches
                self._reset_cursor()

                # Force cursor update by updating the window
                try:
                    self.app.update_idletasks()
                except tk.TclError:
                    pass  # Window may be closing

        # Start the animation
        animate_refresh()

        # Add a fallback cursor reset in case something goes wrong
        self.app.after(3000, self.reset_cursor_fallback)

    def _reset_cursor(self) -> None:
        """Reset the cursor to default state."""
        cursor_reset = False
        try:
            self.app.config(cursor="")
            cursor_reset = True
            logging.debug("Cursor reset to default successfully")
        except Exception as e:
            logging.debug(f"Failed to reset cursor to default: {e}")
            try:
                self.app.config(cursor="arrow")
                cursor_reset = True
                logging.debug("Cursor reset to arrow successfully")
            except Exception as e2:
                logging.debug(f"Failed to reset cursor to arrow: {e2}")
                try:
                    self.app.config(cursor="left_ptr")
                    cursor_reset = True
                    logging.debug("Cursor reset to left_ptr successfully")
                except Exception as e3:
                    logging.debug(f"Failed to reset cursor to left_ptr: {e3}")

        if not cursor_reset:
            logging.warning("Could not reset cursor after microphone refresh")

    def reset_cursor_fallback(self) -> None:
        """Fallback method to reset cursor if it gets stuck."""
        try:
            if self._refreshing:
                logging.warning("Cursor reset fallback triggered - microphone refresh may have failed")
                self._refreshing = False
                # Try to reset cursor
                try:
                    self.app.config(cursor="")
                except tk.TclError:
                    try:
                        self.app.config(cursor="arrow")
                    except tk.TclError:
                        pass  # Cursor change not supported
                # Re-enable refresh button
                refresh_btn = self.app.ui.components.get('refresh_btn')
                if refresh_btn:
                    refresh_btn.config(text="⟳", state=tk.NORMAL)
        except Exception as e:
            logging.error(f"Error in cursor reset fallback: {e}")
