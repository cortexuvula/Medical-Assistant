"""
Sidebar Navigation Component for Medical Assistant
Provides left sidebar navigation with collapsible sections
"""

import tkinter as tk
import ttkbootstrap as ttk
from typing import Dict, Callable, Optional, List
import logging

from ui.tooltip import ToolTip
from ui.scaling_utils import ui_scaler
from ui.ui_constants import Icons, SidebarConfig, Fonts
from settings.settings import SETTINGS


class SidebarNavigation:
    """Manages the left sidebar navigation UI components."""

    # Navigation items configuration
    NAV_ITEMS = [
        {"id": "record", "label": "Record", "icon": Icons.NAV_RECORD},
        {"id": "soap", "label": "SOAP Note", "icon": Icons.NAV_SOAP},
        {"id": "referral", "label": "Referral", "icon": Icons.NAV_REFERRAL},
        {"id": "letter", "label": "Letter", "icon": Icons.NAV_LETTER},
        {"id": "chat", "label": "Chat", "icon": Icons.NAV_CHAT},
        {"id": "rag", "label": "RAG", "icon": Icons.NAV_RAG},
        {"id": "recordings", "label": "Recordings", "icon": Icons.NAV_RECORDINGS},
    ]

    # File operation items
    FILE_ITEMS = [
        {"id": "new_session", "label": "New Session", "icon": Icons.FILE_NEW},
        {"id": "save", "label": "Save", "icon": Icons.FILE_SAVE},
        {"id": "load_audio", "label": "Load Audio", "icon": Icons.FILE_LOAD},
        {"id": "export_pdf", "label": "Export PDF", "icon": Icons.FILE_EXPORT},
    ]

    # Generate items - for creating documents
    GENERATE_ITEMS = [
        {"id": "gen_soap", "label": "Generate SOAP", "icon": Icons.NAV_SOAP},
        {"id": "gen_referral", "label": "Generate Referral", "icon": Icons.NAV_REFERRAL},
        {"id": "gen_letter", "label": "Generate Letter", "icon": Icons.NAV_LETTER},
    ]

    # Tool items configuration - labels match actual functionality
    TOOL_ITEMS = [
        {"id": "refine", "label": "Refine Text", "icon": Icons.TOOL_REFINE},
        {"id": "improve", "label": "Improve Text", "icon": Icons.TOOL_IMPROVE},
        {"id": "medication", "label": "Medication", "icon": Icons.TOOL_MEDICATION},
        {"id": "diagnostic", "label": "Diagnostic", "icon": Icons.TOOL_DIAGNOSTIC},
        {"id": "workflow", "label": "Workflow", "icon": Icons.TOOL_WORKFLOW},
        {"id": "translation", "label": "Translation", "icon": Icons.TOOL_TRANSLATION},
        {"id": "data_extraction", "label": "Data Extract", "icon": Icons.TOOL_DATA},
    ]

    def __init__(self, parent_ui):
        """Initialize the SidebarNavigation component.

        Args:
            parent_ui: Reference to the parent WorkflowUI instance
        """
        self.parent_ui = parent_ui
        self.parent = parent_ui.parent
        self.components = parent_ui.components

        self._collapsed = SETTINGS.get("sidebar_collapsed", False)
        self._tools_expanded = SETTINGS.get("sidebar_tools_expanded", True)
        self._generate_expanded = SETTINGS.get("sidebar_generate_expanded", True)
        self._file_expanded = SETTINGS.get("sidebar_file_expanded", True)
        self._active_item = "record"
        self._is_dark = False

        # Widget references
        self._nav_items: Dict[str, tk.Frame] = {}
        self._tool_items: Dict[str, tk.Frame] = {}
        self._generate_items: Dict[str, tk.Frame] = {}
        self._file_items: Dict[str, tk.Frame] = {}
        self._sidebar_frame: Optional[ttk.Frame] = None
        self._content_frame: Optional[tk.Frame] = None
        self._toggle_btn: Optional[ttk.Button] = None
        self._tools_header: Optional[tk.Frame] = None
        self._tools_container: Optional[tk.Frame] = None
        self._generate_header: Optional[tk.Frame] = None
        self._generate_container: Optional[tk.Frame] = None
        self._file_header: Optional[tk.Frame] = None
        self._file_container: Optional[tk.Frame] = None

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

        # Create header with toggle button
        self._create_header(colors)

        # Create separator
        self._create_separator(colors)

        # Create navigation section
        self._create_nav_section(colors)

        # Create separator
        self._create_separator(colors)

        # Create file section
        self._create_file_section(colors)

        # Create separator
        self._create_separator(colors)

        # Create generate section
        self._create_generate_section(colors)

        # Create separator
        self._create_separator(colors)

        # Create tools section
        self._create_tools_section(colors)

        # Create separator
        self._create_separator(colors)

        # Create settings footer
        self._create_settings_footer(colors)

        # Store reference
        self.components['sidebar'] = self._sidebar_frame
        self.components['sidebar_navigation'] = self

        # Apply initial collapsed state
        if self._collapsed:
            self._apply_collapsed_state()

        return self._sidebar_frame

    def _detect_dark_theme(self) -> bool:
        """Detect if dark theme is currently active."""
        current_theme = SETTINGS.get("theme", "darkly")
        dark_themes = ["darkly", "solar", "cyborg", "superhero", "vapor"]
        return current_theme.lower() in dark_themes

    def _create_header(self, colors: dict):
        """Create the sidebar header with toggle button."""
        header = tk.Frame(self._content_frame, bg=colors["bg"])
        header.pack(fill=tk.X, padx=5, pady=8)

        # Toggle button (collapse/expand sidebar)
        toggle_icon = Icons.SIDEBAR_COLLAPSE if not self._collapsed else Icons.SIDEBAR_EXPAND
        self._toggle_btn = tk.Button(
            header,
            text=toggle_icon,
            font=(Fonts.FAMILY[0], 14),
            bg=colors["bg"],
            fg=colors["fg"],
            activebackground=colors["bg_hover"],
            activeforeground=colors["fg"],
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            command=self._toggle_sidebar
        )
        self._toggle_btn.pack(side=tk.LEFT, padx=5)
        ToolTip(self._toggle_btn, "Collapse sidebar" if not self._collapsed else "Expand sidebar")

        # Title label removed - window title already shows app name
        self._title_label = None

    def _create_separator(self, colors: dict):
        """Create a horizontal separator line."""
        sep = tk.Frame(self._content_frame, bg=colors["border"], height=1)
        sep.pack(fill=tk.X, padx=10, pady=5)

    def _create_nav_section(self, colors: dict):
        """Create the main navigation items section."""
        # Section header
        if not self._collapsed:
            section_header = tk.Label(
                self._content_frame,
                text="NAVIGATE",
                font=(Fonts.FAMILY[0], 9),
                bg=colors["bg"],
                fg=colors["fg_muted"]
            )
            section_header.pack(anchor=tk.W, padx=15, pady=(5, 2))

        # Create navigation items
        for item in self.NAV_ITEMS:
            nav_frame = self._create_nav_item(
                item["id"],
                item["label"],
                item["icon"],
                colors,
                is_active=(item["id"] == self._active_item)
            )
            self._nav_items[item["id"]] = nav_frame

    def _create_file_section(self, colors: dict):
        """Create the collapsible file operations section."""
        # File header (clickable to expand/collapse)
        self._file_header = tk.Frame(self._content_frame, bg=colors["bg"], cursor="hand2")
        self._file_header.pack(fill=tk.X, padx=10, pady=2)

        # Toggle icon
        toggle_icon = Icons.SECTION_OPEN if self._file_expanded else Icons.SECTION_CLOSED
        self._file_toggle_label = tk.Label(
            self._file_header,
            text=toggle_icon if not self._collapsed else Icons.FILE_NEW,
            font=(Fonts.FAMILY[0], 10),
            bg=colors["bg"],
            fg=colors["fg_muted"]
        )
        self._file_toggle_label.pack(side=tk.LEFT, padx=5)

        self._file_title_label = None
        if not self._collapsed:
            self._file_title_label = tk.Label(
                self._file_header,
                text="FILE",
                font=(Fonts.FAMILY[0], 9),
                bg=colors["bg"],
                fg=colors["fg_muted"]
            )
            self._file_title_label.pack(side=tk.LEFT, padx=5)

        # Bind click events
        self._file_header.bind("<Button-1>", lambda e: self._toggle_file_section())
        self._file_toggle_label.bind("<Button-1>", lambda e: self._toggle_file_section())
        if self._file_title_label:
            self._file_title_label.bind("<Button-1>", lambda e: self._toggle_file_section())

        # File container
        self._file_container = tk.Frame(self._content_frame, bg=colors["bg"])
        if self._file_expanded and not self._collapsed:
            self._file_container.pack(fill=tk.X)

        # Create file items
        for item in self.FILE_ITEMS:
            file_frame = self._create_tool_item(
                item["id"],
                item["label"],
                item["icon"],
                colors,
                container=self._file_container
            )
            self._file_items[item["id"]] = file_frame

    def _toggle_file_section(self):
        """Toggle the file section expanded/collapsed state."""
        self._file_expanded = not self._file_expanded

        # Save preference
        SETTINGS["sidebar_file_expanded"] = self._file_expanded
        try:
            from settings.settings import save_settings
            save_settings(SETTINGS)
        except Exception:
            pass

        colors = SidebarConfig.get_sidebar_colors(self._is_dark)

        # Update toggle icon
        toggle_icon = Icons.SECTION_OPEN if self._file_expanded else Icons.SECTION_CLOSED
        self._file_toggle_label.config(text=toggle_icon)

        # Show/hide container - pack after header to maintain position
        if self._file_expanded:
            self._file_container.pack(fill=tk.X, after=self._file_header)
        else:
            self._file_container.pack_forget()

    def _create_generate_section(self, colors: dict):
        """Create the collapsible generate documents section."""
        # Generate header (clickable to expand/collapse)
        self._generate_header = tk.Frame(self._content_frame, bg=colors["bg"], cursor="hand2")
        self._generate_header.pack(fill=tk.X, padx=10, pady=2)

        # Toggle icon
        toggle_icon = Icons.SECTION_OPEN if self._generate_expanded else Icons.SECTION_CLOSED
        self._generate_toggle_label = tk.Label(
            self._generate_header,
            text=toggle_icon if not self._collapsed else Icons.NAV_SOAP,
            font=(Fonts.FAMILY[0], 10),
            bg=colors["bg"],
            fg=colors["fg_muted"]
        )
        self._generate_toggle_label.pack(side=tk.LEFT, padx=5)

        self._generate_title_label = None
        if not self._collapsed:
            self._generate_title_label = tk.Label(
                self._generate_header,
                text="GENERATE",
                font=(Fonts.FAMILY[0], 9),
                bg=colors["bg"],
                fg=colors["fg_muted"]
            )
            self._generate_title_label.pack(side=tk.LEFT, padx=5)

        # Bind click events
        self._generate_header.bind("<Button-1>", lambda e: self._toggle_generate_section())
        self._generate_toggle_label.bind("<Button-1>", lambda e: self._toggle_generate_section())
        if self._generate_title_label:
            self._generate_title_label.bind("<Button-1>", lambda e: self._toggle_generate_section())

        # Generate container
        self._generate_container = tk.Frame(self._content_frame, bg=colors["bg"])
        if self._generate_expanded and not self._collapsed:
            self._generate_container.pack(fill=tk.X)

        # Create generate items
        for item in self.GENERATE_ITEMS:
            gen_frame = self._create_tool_item(
                item["id"],
                item["label"],
                item["icon"],
                colors,
                container=self._generate_container
            )
            self._generate_items[item["id"]] = gen_frame

    def _toggle_generate_section(self):
        """Toggle the generate section expanded/collapsed state."""
        self._generate_expanded = not self._generate_expanded

        # Save preference
        SETTINGS["sidebar_generate_expanded"] = self._generate_expanded
        try:
            from settings.settings import save_settings
            save_settings(SETTINGS)
        except Exception:
            pass

        colors = SidebarConfig.get_sidebar_colors(self._is_dark)

        # Update toggle icon
        toggle_icon = Icons.SECTION_OPEN if self._generate_expanded else Icons.SECTION_CLOSED
        self._generate_toggle_label.config(text=toggle_icon)

        # Show/hide container - pack after header to maintain position
        if self._generate_expanded:
            self._generate_container.pack(fill=tk.X, after=self._generate_header)
        else:
            self._generate_container.pack_forget()

    def _create_tools_section(self, colors: dict):
        """Create the collapsible tools section."""
        # Tools header (clickable to expand/collapse)
        self._tools_header = tk.Frame(self._content_frame, bg=colors["bg"], cursor="hand2")
        self._tools_header.pack(fill=tk.X, padx=10, pady=2)

        # Toggle icon
        toggle_icon = Icons.SECTION_OPEN if self._tools_expanded else Icons.SECTION_CLOSED
        self._tools_toggle_label = tk.Label(
            self._tools_header,
            text=toggle_icon if not self._collapsed else Icons.TOOL_WORKFLOW,
            font=(Fonts.FAMILY[0], 10),
            bg=colors["bg"],
            fg=colors["fg_muted"]
        )
        self._tools_toggle_label.pack(side=tk.LEFT, padx=5)

        self._tools_title_label = None
        if not self._collapsed:
            self._tools_title_label = tk.Label(
                self._tools_header,
                text="TOOLS",
                font=(Fonts.FAMILY[0], 9),
                bg=colors["bg"],
                fg=colors["fg_muted"]
            )
            self._tools_title_label.pack(side=tk.LEFT, padx=5)

        # Bind click events
        self._tools_header.bind("<Button-1>", lambda e: self._toggle_tools_section())
        self._tools_toggle_label.bind("<Button-1>", lambda e: self._toggle_tools_section())
        if self._tools_title_label:
            self._tools_title_label.bind("<Button-1>", lambda e: self._toggle_tools_section())

        # Tools container
        self._tools_container = tk.Frame(self._content_frame, bg=colors["bg"])
        if self._tools_expanded and not self._collapsed:
            self._tools_container.pack(fill=tk.X)

        # Create tool items
        for item in self.TOOL_ITEMS:
            tool_frame = self._create_tool_item(
                item["id"],
                item["label"],
                item["icon"],
                colors
            )
            self._tool_items[item["id"]] = tool_frame

    def _create_nav_item(self, item_id: str, label: str, icon: str, colors: dict, is_active: bool = False) -> tk.Frame:
        """Create a navigation item with icon and label.

        Args:
            item_id: Unique identifier for the item
            label: Display label
            icon: Icon character
            colors: Color scheme dict
            is_active: Whether this item is currently active

        Returns:
            tk.Frame: The navigation item frame
        """
        bg_color = colors["bg_active"] if is_active else colors["bg"]
        fg_color = colors["fg_active"] if is_active else colors["fg"]

        item_frame = tk.Frame(
            self._content_frame,
            bg=bg_color,
            cursor="hand2"
        )
        item_frame.pack(fill=tk.X, padx=5, pady=1)

        # Icon
        icon_label = tk.Label(
            item_frame,
            text=icon,
            font=(Fonts.FAMILY[0], 14),
            bg=bg_color,
            fg=fg_color,
            width=2
        )
        icon_label.pack(side=tk.LEFT, padx=(10, 5), pady=8)

        # Label (hidden when collapsed)
        if not self._collapsed:
            text_label = tk.Label(
                item_frame,
                text=label,
                font=(Fonts.FAMILY[0], 10),
                bg=bg_color,
                fg=fg_color,
                anchor=tk.W
            )
            text_label.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=8)
            text_label.bind("<Button-1>", lambda e, id=item_id: self._on_nav_click(id))

        # Store references for theme updates
        item_frame._icon_label = icon_label
        item_frame._text_label = text_label if not self._collapsed else None
        item_frame._item_id = item_id

        # Bind click events
        item_frame.bind("<Button-1>", lambda e, id=item_id: self._on_nav_click(id))
        icon_label.bind("<Button-1>", lambda e, id=item_id: self._on_nav_click(id))

        # Add tooltip when collapsed
        if self._collapsed:
            ToolTip(item_frame, label)
            ToolTip(icon_label, label)

        return item_frame

    def _create_tool_item(self, item_id: str, label: str, icon: str, colors: dict, container=None) -> tk.Frame:
        """Create a tool item with icon and label.

        Args:
            item_id: Unique identifier for the tool
            label: Display label
            icon: Icon character
            colors: Color scheme dict
            container: Optional container frame (defaults to tools container)

        Returns:
            tk.Frame: The tool item frame
        """
        parent_container = container if container else self._tools_container
        item_frame = tk.Frame(
            parent_container,
            bg=colors["bg"],
            cursor="hand2"
        )
        item_frame.pack(fill=tk.X, padx=5, pady=1)

        # Icon
        icon_label = tk.Label(
            item_frame,
            text=icon,
            font=(Fonts.FAMILY[0], 12),
            bg=colors["bg"],
            fg=colors["fg"],
            width=2
        )
        icon_label.pack(side=tk.LEFT, padx=(15, 5), pady=6)

        # Label (hidden when collapsed)
        text_label = None
        if not self._collapsed:
            text_label = tk.Label(
                item_frame,
                text=label,
                font=(Fonts.FAMILY[0], 9),
                bg=colors["bg"],
                fg=colors["fg"],
                anchor=tk.W
            )
            text_label.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=6)
            text_label.bind("<Button-1>", lambda e, id=item_id: self._on_tool_click(id))

        # Store references
        item_frame._icon_label = icon_label
        item_frame._text_label = text_label
        item_frame._item_id = item_id

        # Bind click events
        item_frame.bind("<Button-1>", lambda e, id=item_id: self._on_tool_click(id))
        icon_label.bind("<Button-1>", lambda e, id=item_id: self._on_tool_click(id))

        # Add tooltip
        ToolTip(item_frame, label)
        ToolTip(icon_label, label)

        return item_frame

    def _create_settings_footer(self, colors: dict):
        """Create the settings shortcut at the bottom."""
        # Spacer to push settings to bottom
        spacer = tk.Frame(self._content_frame, bg=colors["bg"])
        spacer.pack(fill=tk.BOTH, expand=True)

        # Credentials item
        credentials_frame = tk.Frame(self._content_frame, bg=colors["bg"], cursor="hand2")
        credentials_frame.pack(fill=tk.X, padx=5, pady=10, side=tk.BOTTOM)

        icon_label = tk.Label(
            credentials_frame,
            text=Icons.NAV_SETTINGS,
            font=(Fonts.FAMILY[0], 14),
            bg=colors["bg"],
            fg=colors["fg_muted"],
            width=2
        )
        icon_label.pack(side=tk.LEFT, padx=(10, 5), pady=8)

        if not self._collapsed:
            text_label = tk.Label(
                credentials_frame,
                text="Credentials",
                font=(Fonts.FAMILY[0], 10),
                bg=colors["bg"],
                fg=colors["fg_muted"],
                anchor=tk.W
            )
            text_label.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=8)
            text_label.bind("<Button-1>", lambda e: self._open_settings())

        credentials_frame._icon_label = icon_label
        credentials_frame.bind("<Button-1>", lambda e: self._open_settings())
        icon_label.bind("<Button-1>", lambda e: self._open_settings())

        ToolTip(credentials_frame, "Manage API Credentials")
        ToolTip(icon_label, "Manage API Credentials")

    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================

    def _on_nav_click(self, item_id: str):
        """Handle click on navigation item."""
        logging.debug(f"Navigation clicked: {item_id}")
        self.set_active_item(item_id)

        # Notify navigation controller
        if hasattr(self.parent, 'navigation_controller'):
            self.parent.navigation_controller.navigate_to(item_id)

    def _on_tool_click(self, tool_id: str):
        """Handle click on tool item or generate item."""
        logging.debug(f"Tool/Generate clicked: {tool_id}")

        # Map tool IDs to command map keys or methods
        tool_commands = {
            # File items
            "new_session": "new_session",
            "save": "save_text",
            "load_audio": "load_audio_file",
            "export_pdf": "export_as_pdf",
            # Generate items
            "gen_soap": "create_soap_note",
            "gen_referral": "create_referral",
            "gen_letter": "create_letter",
            # Tool items
            "refine": "refine_text",
            "improve": "improve_text",
            "translation": "open_translation",
            "medication": "analyze_medications",
            "diagnostic": "create_diagnostic_analysis",
            "workflow": "manage_workflow",
            "data_extraction": "extract_clinical_data",
        }

        command_key = tool_commands.get(tool_id)
        if command_key:
            # Try command map first
            if command_key in self._command_map:
                try:
                    self._command_map[command_key]()
                except Exception as e:
                    logging.error(f"Error executing tool command {command_key}: {e}")
            # Try parent method
            elif hasattr(self.parent, command_key):
                try:
                    getattr(self.parent, command_key)()
                except Exception as e:
                    logging.error(f"Error executing tool method {command_key}: {e}")
            else:
                logging.warning(f"No handler found for tool: {tool_id}")

    def _open_settings(self):
        """Open the settings menu/dialog."""
        from ui.dialogs.dialogs import show_api_keys_dialog
        show_api_keys_dialog(self.parent)

    def _toggle_sidebar(self):
        """Toggle sidebar between expanded and collapsed states."""
        self._collapsed = not self._collapsed

        # Save preference
        SETTINGS["sidebar_collapsed"] = self._collapsed
        try:
            from settings.settings import save_settings
            save_settings(SETTINGS)
        except Exception as e:
            logging.error(f"Error saving sidebar state: {e}")

        # Rebuild sidebar
        self._rebuild_sidebar()

    def _toggle_tools_section(self):
        """Toggle the tools section expanded/collapsed state."""
        if self._collapsed:
            return  # Don't toggle when sidebar is collapsed

        self._tools_expanded = not self._tools_expanded

        # Save preference
        SETTINGS["sidebar_tools_expanded"] = self._tools_expanded
        try:
            from settings.settings import save_settings
            save_settings(SETTINGS)
        except Exception as e:
            logging.error(f"Error saving tools expanded state: {e}")

        colors = SidebarConfig.get_sidebar_colors(self._is_dark)

        # Show/hide container - pack after header to maintain position
        if self._tools_expanded:
            self._tools_container.pack(fill=tk.X, after=self._tools_header)
            self._tools_toggle_label.config(text=Icons.SECTION_OPEN)
        else:
            self._tools_container.pack_forget()
            self._tools_toggle_label.config(text=Icons.SECTION_CLOSED)

    def _apply_collapsed_state(self):
        """Apply the collapsed visual state."""
        self._content_frame.config(width=SidebarConfig.WIDTH_COLLAPSED)

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

        # Get colors
        colors = SidebarConfig.get_sidebar_colors(self._is_dark)

        # Update frame width
        new_width = SidebarConfig.WIDTH_COLLAPSED if self._collapsed else SidebarConfig.WIDTH_EXPANDED
        self._content_frame.config(width=new_width, bg=colors["bg"])

        # Recreate all sections
        self._create_header(colors)
        self._create_separator(colors)
        self._create_nav_section(colors)
        self._create_separator(colors)
        self._create_file_section(colors)
        self._create_separator(colors)
        self._create_generate_section(colors)
        self._create_separator(colors)
        self._create_tools_section(colors)
        self._create_separator(colors)
        self._create_settings_footer(colors)

        # Restore active item
        self._active_item = current_active
        self._update_active_visual()

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
