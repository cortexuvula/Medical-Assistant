"""
Sidebar Navigation Component for Medical Assistant
Provides left sidebar navigation with collapsible sections
"""

import tkinter as tk
import ttkbootstrap as ttk
from typing import Dict, Callable, Optional, List
import platform
from utils.structured_logging import get_logger

from ui.tooltip import ToolTip
from ui.scaling_utils import ui_scaler
from ui.ui_constants import Icons, SidebarConfig, Fonts
from settings.settings_manager import settings_manager

from ui.components.sidebar_scroll_mixin import SidebarScrollMixin
from ui.components.sidebar_sections_mixin import SidebarSectionsMixin
from ui.components.sidebar_items_mixin import SidebarItemsMixin

logger = get_logger(__name__)


class SidebarNavigation(SidebarSectionsMixin, SidebarItemsMixin, SidebarScrollMixin):
    """Manages the left sidebar navigation UI components."""

    def __init__(self, parent_ui):
        """Initialize the SidebarNavigation component.

        Args:
            parent_ui: Reference to the parent WorkflowUI instance
        """
        self.parent_ui = parent_ui
        self.parent = parent_ui.parent
        self.components = parent_ui.components

        self._collapsed = settings_manager.get("sidebar_collapsed", False)
        self._tools_expanded = settings_manager.get("sidebar_tools_expanded", True)
        self._generate_expanded = settings_manager.get("sidebar_generate_expanded", True)
        self._file_expanded = settings_manager.get("sidebar_file_expanded", True)
        self._soap_expanded = settings_manager.get("sidebar_soap_expanded", True)
        self._active_item = "record"
        self._is_dark = False

        # Widget references
        self._nav_items: Dict[str, tk.Frame] = {}
        self._soap_items: Dict[str, tk.Frame] = {}
        self._tool_items: Dict[str, tk.Frame] = {}
        self._generate_items: Dict[str, tk.Frame] = {}
        self._file_items: Dict[str, tk.Frame] = {}
        self._sidebar_frame: Optional[ttk.Frame] = None
        self._content_frame: Optional[tk.Frame] = None
        self._scroll_canvas: Optional[tk.Canvas] = None
        self._scrollbar: Optional[tk.Canvas] = None
        self._scrollbar_colors: Dict[str, str] = {}
        self._scrollbar_dragging: bool = False
        self._scrollbar_hover: bool = False
        self._scrollbar_drag_start_y: int = 0
        self._scrollable_frame: Optional[tk.Frame] = None
        self._header_frame: Optional[tk.Frame] = None
        self._footer_frame: Optional[tk.Frame] = None
        self._toggle_btn: Optional[ttk.Button] = None
        self._tools_header: Optional[tk.Frame] = None
        self._tools_container: Optional[tk.Frame] = None
        self._generate_header: Optional[tk.Frame] = None
        self._generate_container: Optional[tk.Frame] = None
        self._file_header: Optional[tk.Frame] = None
        self._file_container: Optional[tk.Frame] = None
        self._soap_container: Optional[tk.Frame] = None
        self._soap_toggle_label: Optional[tk.Label] = None

        # Indicator labels for SOAP sub-items (to show data availability)
        self._soap_medication_indicator: Optional[tk.Label] = None
        self._soap_differential_indicator: Optional[tk.Label] = None

        # Scroll indicator
        self._scroll_fade_overlay: Optional[tk.Canvas] = None
        self._scroll_container: Optional[tk.Frame] = None
        self._colors: Optional[dict] = None

        # Command map for tool actions
        self._command_map: Dict[str, Callable] = {}

    def create_sidebar(self, command_map: Dict[str, Callable]) -> ttk.Frame:
        """Create the left sidebar navigation panel.

        Args:
            command_map: Dictionary mapping command names to callable functions

        Returns:
            ttk.Frame: The sidebar frame
        """
        self._command_map = command_map

        # Detect initial theme
        self._is_dark = self._detect_dark_theme()
        colors = SidebarConfig.get_sidebar_colors(self._is_dark)
        self._colors = colors  # Store for later use

        # Create main sidebar frame
        self._sidebar_frame = ttk.Frame(self.parent)

        # Create inner content frame with background color
        self._content_frame = tk.Frame(
            self._sidebar_frame,
            bg=colors["bg"],
            width=SidebarConfig.WIDTH_EXPANDED if not self._collapsed else SidebarConfig.WIDTH_COLLAPSED
        )
        self._content_frame.pack(fill=tk.BOTH, expand=True)
        self._content_frame.pack_propagate(False)

        # Create header with toggle button (fixed at top)
        self._header_frame = tk.Frame(self._content_frame, bg=colors["bg"])
        self._header_frame.pack(fill=tk.X, side=tk.TOP)
        self._create_header(colors)
        self._create_separator(colors, parent=self._header_frame)

        # Create footer (fixed at bottom)
        self._footer_frame = tk.Frame(self._content_frame, bg=colors["bg"])
        self._footer_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self._create_settings_footer(colors)

        # Create scrollable middle section
        self._create_scrollable_section(colors)

        # Create navigation section (in scrollable area)
        self._create_nav_section(colors)

        # Create separator
        self._create_separator(colors, parent=self._scrollable_frame)

        # Create file section
        self._create_file_section(colors)

        # Create separator
        self._create_separator(colors, parent=self._scrollable_frame)

        # Create generate section
        self._create_generate_section(colors)

        # Create separator
        self._create_separator(colors, parent=self._scrollable_frame)

        # Create tools section
        self._create_tools_section(colors)

        # Store reference
        self.components['sidebar'] = self._sidebar_frame
        self.components['sidebar_navigation'] = self

        # Apply initial collapsed state
        if self._collapsed:
            self._apply_collapsed_state()
            # Schedule deferred geometry update after widget is added to Panedwindow
            self._sidebar_frame.after(100, lambda: self._update_parent_geometry(SidebarConfig.WIDTH_COLLAPSED))

        return self._sidebar_frame

    def _detect_dark_theme(self) -> bool:
        """Detect if dark theme is currently active."""
        current_theme = settings_manager.get("theme", "darkly")
        dark_themes = ["darkly", "solar", "cyborg", "superhero", "vapor"]
        return current_theme.lower() in dark_themes

    def _create_header(self, colors: dict):
        """Create the sidebar header with toggle button."""
        header = tk.Frame(self._header_frame, bg=colors["bg"])
        header.pack(fill=tk.X, padx=5, pady=8)

        # Toggle button (collapse/expand sidebar)
        toggle_icon = Icons.SIDEBAR_COLLAPSE if not self._collapsed else Icons.SIDEBAR_EXPAND
        # Use Label instead of Button for macOS Aqua compatibility
        self._toggle_btn = tk.Label(
            header,
            text=toggle_icon,
            font=(Fonts.FAMILY[0], 14),
            bg=colors["bg"],
            fg=colors["fg"],
            cursor="hand2",
        )
        self._toggle_btn.pack(side=tk.LEFT, padx=5)
        self._toggle_btn.bind("<Button-1>", lambda e: self._toggle_sidebar())
        ToolTip(self._toggle_btn, "Collapse sidebar" if not self._collapsed else "Expand sidebar")

        # Title label removed - window title already shows app name
        self._title_label = None

    def _create_separator(self, colors: dict, parent=None):
        """Create a horizontal separator line.

        Args:
            colors: Color scheme dict
            parent: Optional parent frame (defaults to scrollable frame)
        """
        container = parent if parent else self._scrollable_frame
        sep = tk.Frame(container, bg=colors["border"], height=1)
        sep.pack(fill=tk.X, padx=10, pady=5)

    # Section creation, item creation, and click handlers are provided
    # by SidebarSectionsMixin and SidebarItemsMixin.

    def _toggle_sidebar(self):
        """Toggle sidebar between expanded and collapsed states."""
        self._collapsed = not self._collapsed
        settings_manager.set("sidebar_collapsed", self._collapsed)
        self._rebuild_sidebar()

    def _apply_collapsed_state(self):
        """Apply the collapsed visual state."""
        collapsed_width = SidebarConfig.WIDTH_COLLAPSED
        self._content_frame.config(width=collapsed_width)
        # Also update sidebar frame so Panedwindow gets correct initial size
        self._sidebar_frame.configure(width=collapsed_width)

    def _rebuild_sidebar(self):
        """Rebuild the sidebar with current collapsed state."""
        # Store current active item
        current_active = self._active_item

        # Destroy current content
        for widget in self._content_frame.winfo_children():
            widget.destroy()

        # Clear references
        self._nav_items.clear()
        self._tool_items.clear()
        self._generate_items.clear()
        self._file_items.clear()
        self._soap_items.clear()
        self._header_frame = None
        self._footer_frame = None
        self._scroll_canvas = None
        self._scrollable_frame = None
        self._scroll_fade_overlay = None
        self._scroll_container = None
        self._soap_container = None
        self._soap_toggle_label = None
        self._soap_medication_indicator = None
        self._soap_differential_indicator = None

        # Get colors
        colors = SidebarConfig.get_sidebar_colors(self._is_dark)
        self._colors = colors  # Update stored colors

        # Update frame width
        new_width = SidebarConfig.WIDTH_COLLAPSED if self._collapsed else SidebarConfig.WIDTH_EXPANDED
        self._content_frame.config(width=new_width, bg=colors["bg"])

        # Update sidebar frame minimum width to force Panedwindow to resize
        self._sidebar_frame.configure(width=new_width)

        # Create header with toggle button (fixed at top)
        self._header_frame = tk.Frame(self._content_frame, bg=colors["bg"])
        self._header_frame.pack(fill=tk.X, side=tk.TOP)
        self._create_header(colors)
        self._create_separator(colors, parent=self._header_frame)

        # Create footer (fixed at bottom)
        self._footer_frame = tk.Frame(self._content_frame, bg=colors["bg"])
        self._footer_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self._create_settings_footer(colors)

        # Create scrollable middle section
        self._create_scrollable_section(colors)

        # Create navigation section (in scrollable area)
        self._create_nav_section(colors)
        self._create_separator(colors, parent=self._scrollable_frame)
        self._create_file_section(colors)
        self._create_separator(colors, parent=self._scrollable_frame)
        self._create_generate_section(colors)
        self._create_separator(colors, parent=self._scrollable_frame)
        self._create_tools_section(colors)

        # Restore active item
        self._active_item = current_active
        self._update_active_visual()

        # Force geometry update and notify parent Panedwindow
        self._update_parent_geometry(new_width)

    def _update_parent_geometry(self, new_width: int):
        """Force parent Panedwindow to update sash position after sidebar resize.

        Args:
            new_width: The new sidebar width
        """
        try:
            # Process pending geometry requests
            self._sidebar_frame.update_idletasks()

            # Find the Panedwindow that manages this sidebar
            # The sidebar is added to a Panedwindow via .add(), which makes
            # the Panedwindow the geometry manager (not the parent/master)
            panedwindow = self._find_managing_panedwindow()
            if panedwindow:
                try:
                    # Update sash position to match new sidebar width
                    panedwindow.sashpos(0, new_width)
                except tk.TclError:
                    pass  # Sash position update not needed or failed
        except Exception as e:
            logger.debug(f"Could not update parent geometry: {e}")

    def _find_managing_panedwindow(self):
        """Find the Panedwindow that manages this sidebar.

        Returns:
            The Panedwindow widget or None if not found
        """
        # Walk up to find a Panedwindow that contains this sidebar
        # Check parent_ui.parent which is the app window
        if hasattr(self.parent, 'winfo_children'):
            for child in self.parent.winfo_children():
                # Check if this is a Panedwindow that contains our sidebar
                if hasattr(child, 'panes'):
                    try:
                        panes = child.panes()
                        # Check if our sidebar frame is one of the panes
                        sidebar_name = str(self._sidebar_frame)
                        if sidebar_name in panes or self._sidebar_frame in panes:
                            return child
                    except tk.TclError:
                        continue
        return None

    def set_active_item(self, item_id: str):
        """Set the active navigation item.

        Args:
            item_id: ID of the item to make active
        """
        if item_id == self._active_item:
            return

        old_active = self._active_item
        self._active_item = item_id

        self._update_active_visual()

    def _update_active_visual(self):
        """Update visual highlighting for active item."""
        colors = SidebarConfig.get_sidebar_colors(self._is_dark)

        for item_id, frame in self._nav_items.items():
            is_active = (item_id == self._active_item)
            bg_color = colors["bg_active"] if is_active else colors["bg"]
            fg_color = colors["fg_active"] if is_active else colors["fg"]

            frame.config(bg=bg_color)
            if hasattr(frame, '_icon_label'):
                frame._icon_label.config(bg=bg_color, fg=fg_color)
            if hasattr(frame, '_text_label') and frame._text_label:
                frame._text_label.config(bg=bg_color, fg=fg_color)

    def update_theme(self, is_dark: bool):
        """Update sidebar colors for theme change.

        Args:
            is_dark: Whether dark theme is active
        """
        self._is_dark = is_dark
        self._rebuild_sidebar()

    def get_active_item(self) -> str:
        """Get the currently active navigation item ID."""
        return self._active_item

    def is_collapsed(self) -> bool:
        """Check if sidebar is in collapsed state."""
        return self._collapsed
