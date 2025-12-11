"""
Microphone Controller Module

Handles microphone detection, listing, refresh, and selection functionality.

This controller extracts microphone management logic from the main App class
to improve maintainability and separation of concerns.
"""

import logging
import tkinter as tk
from typing import TYPE_CHECKING

from settings.settings import SETTINGS, save_settings
from utils.utils import get_valid_microphones

if TYPE_CHECKING:
    from core.app import MedicalDictationApp

logger = logging.getLogger(__name__)


class MicrophoneController:
    """Controller for managing microphone functionality.

    This class coordinates:
    - Detecting available microphones
    - Refreshing the microphone list with animation
    - Managing microphone selection
    - Cursor state management during refresh
    """

    def __init__(self, app: 'MedicalDictationApp'):
        """Initialize the microphone controller.

        Args:
            app: Reference to the main application instance
        """
        self.app = app
        self._refreshing = False

    def refresh_microphones(self) -> None:
        """Refresh the list of available microphones with simple animation."""
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
                    saved_mic = SETTINGS.get("selected_microphone", "")
                    if saved_mic and saved_mic in mic_names:
                        self.app.mic_combobox.set(saved_mic)
                    else:
                        # Select first device and save it
                        self.app.mic_combobox.current(0)
                        SETTINGS["selected_microphone"] = self.app.mic_combobox.get()
                        save_settings(SETTINGS)
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
