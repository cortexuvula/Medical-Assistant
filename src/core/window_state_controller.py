"""
Window State Controller Module

Handles window configuration, dimensions, tab changes, and application closing
lifecycle management.

This controller extracts window state logic from the main App class
to improve maintainability and separation of concerns.
"""

import logging
import time
from typing import TYPE_CHECKING

from settings.settings import SETTINGS, save_settings

if TYPE_CHECKING:
    from core.app import MedicalDictationApp

logger = logging.getLogger(__name__)


class WindowStateController:
    """Controller for managing window state and lifecycle.

    This class coordinates:
    - Window configuration changes (resize handling)
    - Window dimension persistence
    - Tab change handling
    - Application closing and cleanup
    """

    def __init__(self, app: 'MedicalDictationApp'):
        """Initialize the window state controller.

        Args:
            app: Reference to the main application instance
        """
        self.app = app

    def on_window_configure(self, event) -> None:
        """Handle window configuration events.

        Only save dimensions when the window size actually changes and after
        resizing stops.

        Args:
            event: The configure event from tkinter
        """
        # Skip if this is not the main window configure event or if size hasn't changed
        if event.widget != self.app or (
            self.app.last_width == self.app.winfo_width() and
            self.app.last_height == self.app.winfo_height()
        ):
            return

        # Update last known dimensions
        self.app.last_width = self.app.winfo_width()
        self.app.last_height = self.app.winfo_height()

        # Cancel previous timer if it exists
        if self.app.resize_timer is not None:
            self.app.after_cancel(self.app.resize_timer)

        # Set a new timer to save settings after resizing stops (500ms delay)
        self.app.resize_timer = self.app.after(500, self.save_window_dimensions)

    def save_window_dimensions(self) -> None:
        """Save the current window dimensions to settings."""
        SETTINGS["window_width"] = self.app.last_width
        SETTINGS["window_height"] = self.app.last_height
        save_settings(SETTINGS)
        # Clear the timer reference
        self.app.resize_timer = None

    def on_tab_changed(self, event=None) -> None:
        """Handle tab change events in the notebook.

        Updates the active_text_widget based on the selected tab.

        Args:
            event: The tab change event (unused but required for binding)
        """
        current = self.app.notebook.index(self.app.notebook.select())
        if current == 0:
            self.app.active_text_widget = self.app.transcript_text
        elif current == 1:
            self.app.active_text_widget = self.app.soap_text
        elif current == 2:
            self.app.active_text_widget = self.app.referral_text
        elif current == 3:
            self.app.active_text_widget = self.app.letter_text
        elif current == 4:
            self.app.active_text_widget = self.app.chat_text
        elif current == 5:
            self.app.active_text_widget = self.app.context_text
        else:
            self.app.active_text_widget = self.app.transcript_text

    def on_closing(self) -> None:
        """Clean up resources and save settings before closing the application."""
        # Save window dimensions before closing
        self.save_window_dimensions()

        try:
            # Explicitly stop the background listener if it's running (e.g., SOAP recording)
            if hasattr(self.app, 'soap_stop_listening_function') and self.app.soap_stop_listening_function:
                logging.info("Stopping SOAP recording before exit...")
                try:
                    self.app.soap_stop_listening_function(True)
                    self.app.soap_stop_listening_function = None  # Prevent double calls
                    # Give the audio thread a moment to release resources
                    time.sleep(0.2)
                except Exception as e:
                    logging.error(f"Error stopping SOAP recording: {str(e)}", exc_info=True)

            # Stop periodic analysis if running
            if hasattr(self.app, 'periodic_analyzer') and self.app.periodic_analyzer:
                logging.info("Stopping periodic analyzer...")
                try:
                    self.app._stop_periodic_analysis()
                except Exception as e:
                    logging.error(f"Error stopping periodic analyzer: {str(e)}", exc_info=True)

            # Stop any active listening in the audio handler
            if hasattr(self.app, 'audio_handler'):
                logging.info("Ensuring audio handler is properly closed...")
                try:
                    self.app.audio_handler.cleanup_resources()
                except Exception as e:
                    logging.error(f"Error cleaning up audio handler: {str(e)}", exc_info=True)

            # Shutdown processing queue if it exists
            if hasattr(self.app, 'processing_queue') and self.app.processing_queue:
                logging.info("Shutting down processing queue...")
                try:
                    self.app.processing_queue.shutdown(wait=True)
                except Exception as e:
                    logging.error(f"Error shutting down processing queue: {str(e)}", exc_info=True)

            # Cleanup notification manager if it exists
            if hasattr(self.app, 'notification_manager') and self.app.notification_manager:
                logging.info("Cleaning up notification manager...")
                try:
                    self.app.notification_manager.cleanup()
                except Exception as e:
                    logging.error(f"Error cleaning up notification manager: {str(e)}", exc_info=True)

            # Shutdown MCP servers
            from ai.mcp.mcp_manager import mcp_manager
            logging.info("Shutting down MCP servers...")
            try:
                mcp_manager.stop_all()
            except Exception as e:
                logging.error(f"Error shutting down MCP servers: {str(e)}", exc_info=True)

            # Shutdown all executor pools properly - wait for tasks to complete
            logging.info("Shutting down executor pools...")
            for executor_name in ['io_executor', 'cpu_executor', 'executor']:
                if hasattr(self.app, executor_name) and getattr(self.app, executor_name) is not None:
                    try:
                        executor = getattr(self.app, executor_name)
                        logging.info(f"Shutting down {executor_name}")
                        # Use wait=True to ensure all tasks complete before closing
                        executor.shutdown(wait=True, cancel_futures=True)
                    except TypeError:
                        # Handle older Python versions without cancel_futures parameter
                        executor.shutdown(wait=True)
                    except Exception as e:
                        logging.error(f"Error shutting down {executor_name}: {str(e)}", exc_info=True)

            # Final logging message before closing
            logging.info("Application shutdown complete")

        except Exception as e:
            logging.error(f"Error during application cleanup: {str(e)}", exc_info=True)

        # Destroy the window
        self.app.destroy()
