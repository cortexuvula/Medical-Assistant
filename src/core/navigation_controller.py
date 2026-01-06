"""
Navigation Controller for Medical Assistant
Manages navigation state and view switching between sidebar items
"""

import logging
from typing import Optional, Callable, Dict, List


class NavigationController:
    """Manages navigation state and coordinates view switching.

    This controller handles the relationship between:
    - Sidebar navigation items
    - Document tabs (Transcript, SOAP, Referral, Letter, Chat, RAG)
    - Special views (Record, Recordings)
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

    def __init__(self, app):
        """Initialize the NavigationController.

        Args:
            app: Reference to the main application instance
        """
        self.app = app
        self._current_view = "record"
        self._view_history: List[str] = []
        self._callbacks: Dict[str, List[Callable]] = {}

        logging.debug("NavigationController initialized")

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
