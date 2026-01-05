"""
Shared Panel Manager for Medical Assistant

Manages switching between Analysis and Recordings panels in a single shared area.
"""

import tkinter as tk
import ttkbootstrap as ttk
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class SharedPanelManager:
    """Manages switching between Analysis and Recordings panels.

    This class handles:
    - Creating a container frame for panel switching
    - Registering panels that can be shown in the container
    - Switching between panels with pack_forget/pack
    - Tracking the current visible panel
    """

    PANEL_ANALYSIS = "analysis"
    PANEL_RECORDINGS = "recordings"

    def __init__(self, parent_ui):
        """Initialize the SharedPanelManager.

        Args:
            parent_ui: Reference to the parent WorkflowUI instance
        """
        self.parent_ui = parent_ui
        self.container: Optional[ttk.Frame] = None
        self.panels: Dict[str, ttk.Frame] = {}
        self.current_panel: Optional[str] = None

    def create_container(self, parent) -> ttk.Frame:
        """Create the container frame for panels.

        Args:
            parent: Parent widget for the container

        Returns:
            ttk.Frame: The container frame
        """
        self.container = ttk.Frame(parent)
        return self.container

    def register_panel(self, panel_id: str, frame: ttk.Frame) -> None:
        """Register a panel to be managed.

        Args:
            panel_id: Unique identifier for the panel
            frame: The panel frame widget
        """
        self.panels[panel_id] = frame
        # Initially hide all panels
        frame.pack_forget()
        logger.debug(f"Registered panel: {panel_id}")

    def show_panel(self, panel_id: str) -> None:
        """Show the specified panel, hiding others.

        Args:
            panel_id: ID of the panel to show
        """
        if panel_id not in self.panels:
            logger.warning(f"Panel not found: {panel_id}")
            return

        # Skip if already showing this panel
        if self.current_panel == panel_id:
            return

        # Hide current panel
        if self.current_panel and self.current_panel in self.panels:
            self.panels[self.current_panel].pack_forget()

        # Show new panel
        self.panels[panel_id].pack(fill=tk.BOTH, expand=True)
        self.current_panel = panel_id
        logger.debug(f"Showing panel: {panel_id}")

        # Trigger any panel-specific refresh
        self._on_panel_shown(panel_id)

    def _on_panel_shown(self, panel_id: str) -> None:
        """Handle panel-specific actions when shown.

        Args:
            panel_id: ID of the panel that was shown
        """
        if panel_id == self.PANEL_RECORDINGS:
            # Refresh recordings list when shown
            if hasattr(self.parent_ui, 'recordings_tab'):
                try:
                    self.parent_ui.recordings_tab._refresh_recordings_list()
                except Exception as e:
                    logger.debug(f"Could not refresh recordings: {e}")

    def get_current_panel(self) -> Optional[str]:
        """Get the ID of the currently visible panel.

        Returns:
            Panel ID or None if no panel is visible
        """
        return self.current_panel

    def is_panel_visible(self, panel_id: str) -> bool:
        """Check if a specific panel is currently visible.

        Args:
            panel_id: ID of the panel to check

        Returns:
            True if the panel is currently visible
        """
        return self.current_panel == panel_id
