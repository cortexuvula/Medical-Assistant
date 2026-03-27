"""
Sidebar Items Mixin

Provides item creation helpers and click handlers for the sidebar:
- Navigation item creation (icon + label)
- Tool item creation (icon + label)
- Settings footer
- Click event handlers for navigation and tools

Extracted from SidebarNavigation to reduce file size.
"""

import tkinter as tk
from utils.structured_logging import get_logger
from ui.tooltip import ToolTip
from ui.ui_constants import Fonts

logger = get_logger(__name__)


class SidebarItemsMixin:
    """Item creation and click handler methods for SidebarNavigation."""

    def _create_nav_item(self, item_id: str, label: str, icon: str, colors: dict, is_active: bool = False) -> tk.Frame:
        """Create a navigation item with icon and label."""
        bg_color = colors["bg_active"] if is_active else colors["bg"]
        fg_color = colors["fg_active"] if is_active else colors["fg"]

        item_frame = tk.Frame(self._scrollable_frame, bg=bg_color, cursor="hand2")
        item_frame.pack(fill=tk.X, padx=5, pady=1)

        icon_label = tk.Label(
            item_frame, text=icon, font=(Fonts.FAMILY[0], 14),
            bg=bg_color, fg=fg_color, width=2
        )
        icon_label.pack(side=tk.LEFT, padx=(10, 5), pady=8)

        text_label = None
        if not self._collapsed:
            text_label = tk.Label(
                item_frame, text=label, font=(Fonts.FAMILY[0], 10),
                bg=bg_color, fg=fg_color, anchor=tk.W
            )
            text_label.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=8)
            text_label.bind("<Button-1>", lambda e, id=item_id: self._on_nav_click(id))

        item_frame._icon_label = icon_label
        item_frame._text_label = text_label
        item_frame._item_id = item_id

        item_frame.bind("<Button-1>", lambda e, id=item_id: self._on_nav_click(id))
        icon_label.bind("<Button-1>", lambda e, id=item_id: self._on_nav_click(id))

        if self._collapsed:
            ToolTip(item_frame, label)
            ToolTip(icon_label, label)

        return item_frame

    def _create_tool_item(self, item_id: str, label: str, icon: str, colors: dict, container=None) -> tk.Frame:
        """Create a tool item with icon and label."""
        parent_container = container if container else self._tools_container
        item_frame = tk.Frame(parent_container, bg=colors["bg"], cursor="hand2")
        item_frame.pack(fill=tk.X, padx=5, pady=1)

        icon_label = tk.Label(
            item_frame, text=icon, font=(Fonts.FAMILY[0], 12),
            bg=colors["bg"], fg=colors["fg"], width=2
        )
        icon_label.pack(side=tk.LEFT, padx=(15, 5), pady=6)

        text_label = None
        if not self._collapsed:
            text_label = tk.Label(
                item_frame, text=label, font=(Fonts.FAMILY[0], 9),
                bg=colors["bg"], fg=colors["fg"], anchor=tk.W
            )
            text_label.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=6)
            text_label.bind("<Button-1>", lambda e, id=item_id: self._on_tool_click(id))

        item_frame._icon_label = icon_label
        item_frame._text_label = text_label
        item_frame._item_id = item_id

        item_frame.bind("<Button-1>", lambda e, id=item_id: self._on_tool_click(id))
        icon_label.bind("<Button-1>", lambda e, id=item_id: self._on_tool_click(id))

        ToolTip(item_frame, label)
        ToolTip(icon_label, label)

        return item_frame

    def _create_settings_footer(self, colors: dict):
        """Create the footer section (placeholder for future items)."""
        pass

    # ------------------------------------------------------------------
    # Event Handlers
    # ------------------------------------------------------------------

    def _on_nav_click(self, item_id: str):
        """Handle click on navigation item."""
        logger.debug(f"Navigation clicked: {item_id}")
        self.set_active_item(item_id)

        if hasattr(self.parent, 'navigation_controller'):
            self.parent.navigation_controller.navigate_to(item_id)

    def _on_tool_click(self, tool_id: str):
        """Handle click on tool item or generate item."""
        logger.debug(f"Tool/Generate clicked: {tool_id}")

        tool_commands = {
            "new_session": "new_session",
            "save": "save_text",
            "load_audio": "load_audio_file",
            "export_pdf": "export_as_pdf",
            "gen_soap": "create_soap_note",
            "gen_referral": "create_referral",
            "gen_letter": "create_letter",
            "refine": "refine_text",
            "improve": "improve_text",
            "translation": "open_translation",
            "medication": "analyze_medications",
            "diagnostic": "create_diagnostic_analysis",
            "workflow": "manage_workflow",
            "data_extraction": "extract_clinical_data",
            "rsvp_reader": "open_rsvp_reader",
        }

        command_key = tool_commands.get(tool_id)
        if command_key:
            if command_key in self._command_map:
                try:
                    self._command_map[command_key]()
                except Exception as e:
                    logger.error(f"Error executing tool command {command_key}: {e}")
            elif hasattr(self.parent, command_key):
                try:
                    getattr(self.parent, command_key)()
                except Exception as e:
                    logger.error(f"Error executing tool method {command_key}: {e}")
            else:
                logger.warning(f"No handler found for tool: {tool_id}")
