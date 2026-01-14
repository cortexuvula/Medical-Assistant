"""
Window Controller Module

Consolidated controller for window state, navigation, and log viewing.

This controller merges:
- NavigationController: Navigation state and view switching
- WindowStateController: Window dimensions, tab changes, application closing
- LogsViewerController: Log file viewing and folder access

Extracted from the main App class to improve maintainability and separation of concerns.
"""

import os
import logging
import time
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from typing import TYPE_CHECKING, Optional, Callable, Dict, List

from settings import settings_manager

if TYPE_CHECKING:
    from core.app import MedicalDictationApp

logger = logging.getLogger(__name__)


class WindowController:
    """Controller for managing window state, navigation, and log viewing.

    This class coordinates:
    - Navigation state and view switching
    - Sidebar navigation items
    - Document tabs (Transcript, SOAP, Referral, Letter, Chat, RAG)
    - Window configuration changes (resize handling)
    - Window dimension persistence
    - Tab change handling
    - Application closing and cleanup
    - Viewing logs via popup menu
    - Displaying log contents in a window
    - Opening the logs folder in file explorer
    """

    # Mapping of navigation items to notebook tab indices
    TAB_MAPPING = {
        "record": 0,      # Transcript tab (default when recording)
        "soap": 1,        # SOAP Note tab
        "referral": 2,    # Referral tab
        "letter": 3,      # Letter tab
        "chat": 4,        # Chat tab
        "rag": 5,         # RAG tab
    }

    # Special views that need custom handling
    SPECIAL_VIEWS = ["record", "recordings", "advanced_analysis"]

    def __init__(self, app: 'MedicalDictationApp'):
        """Initialize the window controller.

        Args:
            app: Reference to the main application instance
        """
        self.app = app
        # Navigation state
        self._current_view = "record"
        self._view_history: List[str] = []
        self._callbacks: Dict[str, List[Callable]] = {}

        logging.debug("WindowController initialized")

    # =========================================================================
    # Navigation Methods (from NavigationController)
    # =========================================================================

    @property
    def current_view(self) -> str:
        """Get the currently active view ID."""
        return self._current_view

    def navigate_to(self, view_id: str) -> bool:
        """Navigate to a specific view.

        Args:
            view_id: The ID of the view to navigate to

        Returns:
            bool: True if navigation was successful
        """
        if view_id == self._current_view:
            logging.debug(f"Already on view: {view_id}")
            return True

        logging.debug(f"Navigating from {self._current_view} to {view_id}")

        # Store in history
        self._view_history.append(self._current_view)
        if len(self._view_history) > 50:  # Limit history size
            self._view_history.pop(0)

        # Update current view
        old_view = self._current_view
        self._current_view = view_id

        # Update sidebar highlighting
        self._update_sidebar(view_id)

        # Show appropriate content
        success = self._show_view(view_id)

        if success:
            # Fire callbacks
            self._fire_callbacks("navigation_changed", old_view, view_id)

        return success

    def _update_sidebar(self, view_id: str):
        """Update sidebar to highlight the active item."""
        try:
            if hasattr(self.app, 'ui') and hasattr(self.app.ui, 'sidebar_navigation'):
                self.app.ui.sidebar_navigation.set_active_item(view_id)
        except Exception as e:
            logging.error(f"Error updating sidebar: {e}")

    def _show_view(self, view_id: str) -> bool:
        """Show the content for a specific view.

        Args:
            view_id: The ID of the view to show

        Returns:
            bool: True if the view was shown successfully
        """
        try:
            if view_id == "record":
                return self._show_record_view()
            elif view_id == "recordings":
                return self._show_recordings_view()
            elif view_id == "advanced_analysis":
                return self._show_advanced_analysis_view()
            elif view_id in self.TAB_MAPPING:
                return self._show_document_view(view_id)
            else:
                logging.warning(f"Unknown view ID: {view_id}")
                return False
        except Exception as e:
            logging.error(f"Error showing view {view_id}: {e}")
            return False

    def _show_record_view(self) -> bool:
        """Show the recording view with controls visible."""
        logging.debug("Showing record view")

        try:
            # Show analysis panel in shared panel area
            if hasattr(self.app, 'ui') and hasattr(self.app.ui, 'shared_panel_manager'):
                from ui.components.shared_panel_manager import SharedPanelManager
                self.app.ui.shared_panel_manager.show_panel(SharedPanelManager.PANEL_ANALYSIS)
            elif hasattr(self.app, 'workflow_notebook'):
                # Fallback for backwards compatibility
                self.app.workflow_notebook.select(0)  # Record tab

            # Select Transcript tab in document notebook
            if hasattr(self.app, 'notebook'):
                self.app.notebook.select(0)  # Transcript tab

            return True
        except Exception as e:
            logging.error(f"Error showing record view: {e}")
            return False

    def _show_recordings_view(self) -> bool:
        """Show the recordings history view."""
        logging.debug("Showing recordings view")

        try:
            # Show recordings panel in shared panel area
            if hasattr(self.app, 'ui') and hasattr(self.app.ui, 'shared_panel_manager'):
                from ui.components.shared_panel_manager import SharedPanelManager
                self.app.ui.shared_panel_manager.show_panel(SharedPanelManager.PANEL_RECORDINGS)
            elif hasattr(self.app, 'workflow_notebook'):
                # Fallback for backwards compatibility
                self.app.workflow_notebook.select(3)  # Recordings tab

            return True
        except Exception as e:
            logging.error(f"Error showing recordings view: {e}")
            return False

    def _show_advanced_analysis_view(self) -> bool:
        """Show the advanced analysis panel directly.

        Unlike the record view, this only shows the analysis panel
        without changing the document notebook tab.
        """
        logging.debug("Showing advanced analysis view")

        try:
            # Show analysis panel in shared panel area
            if hasattr(self.app, 'ui') and hasattr(self.app.ui, 'shared_panel_manager'):
                from ui.components.shared_panel_manager import SharedPanelManager
                self.app.ui.shared_panel_manager.show_panel(SharedPanelManager.PANEL_ANALYSIS)
            elif hasattr(self.app, 'workflow_notebook'):
                # Fallback for backwards compatibility
                self.app.workflow_notebook.select(0)  # Record tab

            return True
        except Exception as e:
            logging.error(f"Error showing advanced analysis view: {e}")
            return False

    def _show_document_view(self, view_id: str) -> bool:
        """Show a document view (SOAP, Referral, Letter, Chat, RAG).

        Args:
            view_id: The document view ID

        Returns:
            bool: True if successful
        """
        logging.debug(f"Showing document view: {view_id}")

        try:
            tab_index = self.TAB_MAPPING.get(view_id)
            if tab_index is None:
                logging.warning(f"No tab mapping for view: {view_id}")
                return False

            # Select the appropriate tab in the document notebook
            if hasattr(self.app, 'notebook'):
                self.app.notebook.select(tab_index)

            # If not on Record view, we may want to hide record controls
            # or switch workflow notebook away from Record tab
            if view_id != "record" and hasattr(self.app, 'workflow_notebook'):
                # Keep workflow notebook on a neutral state or Process tab
                # For now, leave it as is since document tabs are independent
                pass

            return True
        except Exception as e:
            logging.error(f"Error showing document view {view_id}: {e}")
            return False

    def go_back(self) -> bool:
        """Navigate to the previous view in history.

        Returns:
            bool: True if there was a previous view to go to
        """
        if not self._view_history:
            logging.debug("No navigation history available")
            return False

        previous_view = self._view_history.pop()
        logging.debug(f"Going back to: {previous_view}")

        # Don't add to history when going back
        self._current_view = previous_view
        self._update_sidebar(previous_view)
        return self._show_view(previous_view)

    def sync_with_notebook(self, tab_index: int):
        """Sync navigation state when notebook tab changes directly.

        Called when user clicks on document tabs directly (not via sidebar).

        Args:
            tab_index: The index of the newly selected tab
        """
        # Find the view ID for this tab index
        view_id = None
        for vid, idx in self.TAB_MAPPING.items():
            if idx == tab_index:
                view_id = vid
                break

        if view_id and view_id != self._current_view:
            logging.debug(f"Syncing sidebar with notebook tab: {view_id}")
            self._current_view = view_id
            self._update_sidebar(view_id)

    def register_callback(self, event: str, callback: Callable):
        """Register a callback for navigation events.

        Args:
            event: Event name (e.g., "navigation_changed")
            callback: Callable to invoke when event occurs
        """
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)

    def unregister_callback(self, event: str, callback: Callable):
        """Unregister a callback.

        Args:
            event: Event name
            callback: Callable to remove
        """
        if event in self._callbacks and callback in self._callbacks[event]:
            self._callbacks[event].remove(callback)

    def _fire_callbacks(self, event: str, *args):
        """Fire all callbacks for an event.

        Args:
            event: Event name
            *args: Arguments to pass to callbacks
        """
        if event in self._callbacks:
            for callback in self._callbacks[event]:
                try:
                    callback(*args)
                except Exception as e:
                    logging.error(f"Error in navigation callback: {e}")

    def get_history(self) -> List[str]:
        """Get the navigation history.

        Returns:
            List of view IDs in navigation order
        """
        return self._view_history.copy()

    # =========================================================================
    # Window State Methods (from WindowStateController)
    # =========================================================================

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
        settings_manager.set_window_dimensions(self.app.last_width, self.app.last_height)
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

    # =========================================================================
    # Logs Viewer Methods (from LogsViewerController)
    # =========================================================================

    def view_logs(self) -> None:
        """Open the logs directory in file explorer or view log contents."""
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
        log_file = os.path.join(log_dir, "medical_dictation.log")

        if not os.path.exists(log_dir):
            messagebox.showinfo(
                "Logs",
                "The logs directory does not exist yet. It will be created when logs are generated."
            )
            return

        # Log that logs are being viewed
        logging.info("User accessed logs directory")

        # Create a dropdown menu for log actions
        log_menu = tk.Menu(self.app, tearoff=0)
        log_menu.add_command(label="Open Logs Folder", command=lambda: self.open_logs_folder(log_dir))
        log_menu.add_command(label="View Log Contents", command=lambda: self.show_log_contents(log_file))

        # Get the position of the mouse
        try:
            x = self.app.winfo_pointerx()
            y = self.app.winfo_pointery()
            log_menu.tk_popup(x, y)
        finally:
            # Make sure to release the grab
            log_menu.grab_release()

    def show_log_contents(self, log_file: str) -> None:
        """Show the contents of the log file in a new window.

        Args:
            log_file: Path to the log file to display
        """
        try:
            if os.path.exists(log_file):
                # Create a new top-level window
                log_window = tk.Toplevel(self.app)
                log_window.title("Log Contents")
                log_window.geometry("800x600")

                # Create text widget with scrollbar
                frame = ttk.Frame(log_window)
                frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

                text_widget = tk.Text(frame, wrap=tk.WORD)
                scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text_widget.yview)
                text_widget.configure(yscrollcommand=scrollbar.set)

                text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                # Read and display log contents
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    text_widget.insert('1.0', content)
                    text_widget.config(state=tk.DISABLED)  # Make read-only

                # Add close button
                close_btn = ttk.Button(log_window, text="Close", command=log_window.destroy)
                close_btn.pack(pady=5)
            else:
                messagebox.showwarning("File Not Found", "Log file not found.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open log file: {str(e)}")

    def open_logs_folder(self, log_dir: str) -> None:
        """Open the logs directory using file explorer.

        Args:
            log_dir: Path to the logs directory
        """
        try:
            from utils.validation import open_file_or_folder_safely
            success, error = open_file_or_folder_safely(log_dir, operation="open")
            if not success:
                messagebox.showerror("Error", f"Could not open logs directory: {error}")
                logging.error(f"Error opening logs directory: {error}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open logs directory: {str(e)}")
            logging.error(f"Error opening logs directory: {str(e)}")

    def open_logs_folder_menu(self) -> None:
        """Wrapper method for menu to open logs folder."""
        from managers.data_folder_manager import data_folder_manager
        log_dir = str(data_folder_manager.logs_folder)
        if not os.path.exists(log_dir):
            messagebox.showinfo(
                "Logs",
                "The logs directory does not exist yet. It will be created when logs are generated."
            )
            return
        logging.info("User accessed logs directory from menu")
        self.open_logs_folder(log_dir)

    def show_log_contents_menu(self) -> None:
        """Wrapper method for menu to show log contents."""
        from managers.data_folder_manager import data_folder_manager
        log_dir = str(data_folder_manager.logs_folder)
        log_file = os.path.join(log_dir, "medical_dictation.log")
        if not os.path.exists(log_dir):
            messagebox.showinfo(
                "Logs",
                "The logs directory does not exist yet. It will be created when logs are generated."
            )
            return
        logging.info("User viewed log contents from menu")
        self.show_log_contents(log_file)
