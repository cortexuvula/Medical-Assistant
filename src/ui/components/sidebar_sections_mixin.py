"""
Sidebar Sections Mixin

Provides section creation and toggle methods for the sidebar:
- Navigation section with SOAP collapsible sub-items
- File operations section
- Generate documents section
- Tools section

Each section is a collapsible group of items with a header and container.
Extracted from SidebarNavigation to reduce file size.
"""

import tkinter as tk
from utils.structured_logging import get_logger
from ui.tooltip import ToolTip
from ui.ui_constants import Icons, SidebarConfig, Fonts
from settings.settings_manager import settings_manager

logger = get_logger(__name__)


class SidebarSectionsMixin:
    """Section creation and management methods for SidebarNavigation."""

    # ------------------------------------------------------------------
    # Navigation Section (with SOAP collapsible sub-items)
    # ------------------------------------------------------------------

    def _create_nav_section(self, colors: dict):
        """Create the main navigation items section."""
        if not self._collapsed:
            section_header = tk.Label(
                self._scrollable_frame,
                text="NAVIGATE",
                font=(Fonts.FAMILY[0], 9),
                bg=colors["bg"],
                fg=colors["fg_muted"]
            )
            section_header.pack(anchor=tk.W, padx=15, pady=(5, 2))

        for item in SidebarConfig.get_nav_items():
            if item["id"] == "soap":
                self._create_soap_collapsible_nav_item(item, colors)
            else:
                nav_frame = self._create_nav_item(
                    item["id"], item["label"], item["icon"], colors,
                    is_active=(item["id"] == self._active_item)
                )
                self._nav_items[item["id"]] = nav_frame

    def _create_soap_collapsible_nav_item(self, item: dict, colors: dict) -> None:
        """Create the SOAP Note navigation item with collapsible sub-items."""
        is_active = item["id"] == self._active_item or self._active_item.startswith("soap_")
        bg_color = colors["bg_active"] if is_active else colors["bg"]
        fg_color = colors["fg_active"] if is_active else colors["fg"]

        item_frame = tk.Frame(self._scrollable_frame, bg=bg_color, cursor="hand2")
        item_frame.pack(fill=tk.X, padx=5, pady=1)

        icon_label = tk.Label(
            item_frame, text=item["icon"], font=(Fonts.FAMILY[0], 14),
            bg=bg_color, fg=fg_color, width=2
        )
        icon_label.pack(side=tk.LEFT, padx=(10, 5), pady=8)

        if not self._collapsed:
            text_label = tk.Label(
                item_frame, text=item["label"], font=(Fonts.FAMILY[0], 10),
                bg=bg_color, fg=fg_color, anchor=tk.W
            )
            text_label.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=8)
            text_label.bind("<Button-1>", lambda e: self._on_nav_click("soap"))

            toggle_icon = Icons.SECTION_OPEN if self._soap_expanded else Icons.SECTION_CLOSED
            self._soap_toggle_label = tk.Label(
                item_frame, text=toggle_icon, font=(Fonts.FAMILY[0], 9),
                bg=bg_color, fg=colors["fg_muted"], cursor="hand2"
            )
            self._soap_toggle_label.pack(side=tk.RIGHT, padx=(0, 8), pady=8)
            self._soap_toggle_label.bind("<Button-1>", lambda e: self._toggle_soap_section())
            item_frame._text_label = text_label
        else:
            item_frame._text_label = None

        item_frame._icon_label = icon_label
        item_frame._item_id = "soap"

        item_frame.bind("<Button-1>", lambda e: self._on_nav_click("soap"))
        icon_label.bind("<Button-1>", lambda e: self._on_nav_click("soap"))

        if self._collapsed:
            ToolTip(item_frame, item["label"])
            ToolTip(icon_label, item["label"])

        self._nav_items["soap"] = item_frame

        self._soap_container = tk.Frame(self._scrollable_frame, bg=colors["bg"])
        if self._soap_expanded and not self._collapsed:
            self._soap_container.pack(fill=tk.X)

        for subitem in SidebarConfig.get_soap_subitems():
            sub_frame = self._create_soap_subitem(
                subitem["id"], subitem["label"], subitem["icon"], colors
            )
            self._soap_items[subitem["id"]] = sub_frame

    def _create_soap_subitem(
        self, item_id: str, label: str, icon: str, colors: dict
    ) -> tk.Frame:
        """Create a SOAP sub-item with icon, label, and optional indicator."""
        is_active = item_id == self._active_item
        bg_color = colors["bg_active"] if is_active else colors["bg"]
        fg_color = colors["fg_active"] if is_active else colors["fg"]

        item_frame = tk.Frame(self._soap_container, bg=bg_color, cursor="hand2")
        item_frame.pack(fill=tk.X, padx=5, pady=1)

        spacer = tk.Label(item_frame, text="", bg=bg_color, width=1)
        spacer.pack(side=tk.LEFT, padx=(5, 0))

        icon_label = tk.Label(
            item_frame, text=icon, font=(Fonts.FAMILY[0], 11),
            bg=bg_color, fg=fg_color, width=2
        )
        icon_label.pack(side=tk.LEFT, padx=(5, 3), pady=6)

        text_label = None
        if not self._collapsed:
            text_label = tk.Label(
                item_frame, text=label, font=(Fonts.FAMILY[0], 9),
                bg=bg_color, fg=fg_color, anchor=tk.W
            )
            text_label.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=6)
            text_label.bind("<Button-1>", lambda e, id=item_id: self._on_soap_subitem_click(id))

            indicator = tk.Label(
                item_frame, text="", font=(Fonts.FAMILY[0], 8),
                bg=bg_color, fg=colors["fg_muted"],
            )
            indicator.pack(side=tk.RIGHT, padx=(0, 8), pady=6)

            if item_id == "soap_medication":
                self._soap_medication_indicator = indicator
            elif item_id == "soap_differential":
                self._soap_differential_indicator = indicator

        item_frame._icon_label = icon_label
        item_frame._text_label = text_label
        item_frame._item_id = item_id

        item_frame.bind("<Button-1>", lambda e, id=item_id: self._on_soap_subitem_click(id))
        icon_label.bind("<Button-1>", lambda e, id=item_id: self._on_soap_subitem_click(id))

        ToolTip(item_frame, label)
        ToolTip(icon_label, label)

        return item_frame

    def _toggle_soap_section(self):
        """Toggle the SOAP sub-items expanded/collapsed state."""
        if self._collapsed:
            return

        self._soap_expanded = not self._soap_expanded
        settings_manager.set("sidebar_soap_expanded", self._soap_expanded)

        if self._soap_toggle_label:
            toggle_icon = Icons.SECTION_OPEN if self._soap_expanded else Icons.SECTION_CLOSED
            self._soap_toggle_label.config(text=toggle_icon)

        if self._soap_expanded:
            soap_frame = self._nav_items.get("soap")
            if soap_frame and self._soap_container:
                self._soap_container.pack(fill=tk.X, after=soap_frame)
        else:
            if self._soap_container:
                self._soap_container.pack_forget()

    def _on_soap_subitem_click(self, item_id: str):
        """Handle click on SOAP sub-item."""
        logger.debug(f"SOAP sub-item clicked: {item_id}")
        if hasattr(self.parent, 'navigation_controller'):
            self.parent.navigation_controller.navigate_to("soap")

        if item_id == "soap_medication":
            self._show_medication_analysis_tab()
        elif item_id == "soap_differential":
            self._show_differential_analysis_tab()

    def _show_medication_analysis_tab(self):
        """Switch to the Medication Analysis tab within the SOAP panel."""
        try:
            notebook_tabs = getattr(self.parent_ui, 'notebook_tabs', None)
            if notebook_tabs and hasattr(notebook_tabs, 'show_medication_analysis_tab'):
                notebook_tabs.show_medication_analysis_tab()
            else:
                self._fallback_show_analysis_tab(0)
        except Exception as e:
            logger.debug(f"Could not switch to medication tab: {e}")

    def _show_differential_analysis_tab(self):
        """Switch to the Differential Diagnosis tab within the SOAP panel."""
        try:
            notebook_tabs = getattr(self.parent_ui, 'notebook_tabs', None)
            if notebook_tabs and hasattr(notebook_tabs, 'show_differential_analysis_tab'):
                notebook_tabs.show_differential_analysis_tab()
            else:
                self._fallback_show_analysis_tab(1)
        except Exception as e:
            logger.debug(f"Could not switch to differential tab: {e}")

    def _fallback_show_analysis_tab(self, tab_index: int):
        """Fallback method to show analysis tab."""
        try:
            if hasattr(self.parent_ui, 'components'):
                analysis_content = self.parent_ui.components.get('analysis_content')
                if analysis_content:
                    for child in analysis_content.winfo_children():
                        if hasattr(child, 'select') and hasattr(child, 'tabs'):
                            tabs = child.tabs()
                            if len(tabs) > tab_index:
                                child.select(tabs[tab_index])
                            break
        except Exception as e:
            logger.debug(f"Fallback show analysis tab failed: {e}")

    def update_soap_indicators(self, has_medication: bool = False, has_differential: bool = False):
        """Update the SOAP sub-item indicators to show data availability."""
        try:
            if self._soap_medication_indicator:
                if has_medication:
                    self._soap_medication_indicator.config(text="\u25cf")
                    colors = SidebarConfig.get_sidebar_colors(self._is_dark)
                    self._soap_medication_indicator.config(fg=colors.get("fg_muted", "#888"))
                else:
                    self._soap_medication_indicator.config(text="")

            if self._soap_differential_indicator:
                if has_differential:
                    self._soap_differential_indicator.config(text="\u25cf")
                    colors = SidebarConfig.get_sidebar_colors(self._is_dark)
                    self._soap_differential_indicator.config(fg=colors.get("fg_muted", "#888"))
                else:
                    self._soap_differential_indicator.config(text="")
        except Exception as e:
            logger.debug(f"Could not update SOAP indicators: {e}")

    # ------------------------------------------------------------------
    # File Section
    # ------------------------------------------------------------------

    def _create_file_section(self, colors: dict):
        """Create the collapsible file operations section."""
        self._file_header = tk.Frame(self._scrollable_frame, bg=colors["bg"], cursor="hand2")
        self._file_header.pack(fill=tk.X, padx=10, pady=2)

        toggle_icon = Icons.SECTION_OPEN if self._file_expanded else Icons.SECTION_CLOSED
        self._file_toggle_label = tk.Label(
            self._file_header,
            text=toggle_icon if not self._collapsed else Icons.FILE_NEW,
            font=(Fonts.FAMILY[0], 10), bg=colors["bg"], fg=colors["fg_muted"]
        )
        self._file_toggle_label.pack(side=tk.LEFT, padx=5)

        self._file_title_label = None
        if not self._collapsed:
            self._file_title_label = tk.Label(
                self._file_header, text="FILE", font=(Fonts.FAMILY[0], 9),
                bg=colors["bg"], fg=colors["fg_muted"]
            )
            self._file_title_label.pack(side=tk.LEFT, padx=5)

        self._file_header.bind("<Button-1>", lambda e: self._toggle_file_section())
        self._file_toggle_label.bind("<Button-1>", lambda e: self._toggle_file_section())
        if self._file_title_label:
            self._file_title_label.bind("<Button-1>", lambda e: self._toggle_file_section())

        self._file_container = tk.Frame(self._scrollable_frame, bg=colors["bg"])
        if self._file_expanded and not self._collapsed:
            self._file_container.pack(fill=tk.X)

        for item in SidebarConfig.get_file_items():
            file_frame = self._create_tool_item(
                item["id"], item["label"], item["icon"], colors,
                container=self._file_container
            )
            self._file_items[item["id"]] = file_frame

    def _toggle_file_section(self):
        """Toggle the file section expanded/collapsed state."""
        self._file_expanded = not self._file_expanded
        settings_manager.set("sidebar_file_expanded", self._file_expanded)

        toggle_icon = Icons.SECTION_OPEN if self._file_expanded else Icons.SECTION_CLOSED
        self._file_toggle_label.config(text=toggle_icon)

        if self._file_expanded:
            self._file_container.pack(fill=tk.X, after=self._file_header)
        else:
            self._file_container.pack_forget()

    # ------------------------------------------------------------------
    # Generate Section
    # ------------------------------------------------------------------

    def _create_generate_section(self, colors: dict):
        """Create the collapsible generate documents section."""
        self._generate_header = tk.Frame(self._scrollable_frame, bg=colors["bg"], cursor="hand2")
        self._generate_header.pack(fill=tk.X, padx=10, pady=2)

        toggle_icon = Icons.SECTION_OPEN if self._generate_expanded else Icons.SECTION_CLOSED
        self._generate_toggle_label = tk.Label(
            self._generate_header,
            text=toggle_icon if not self._collapsed else Icons.NAV_SOAP,
            font=(Fonts.FAMILY[0], 10), bg=colors["bg"], fg=colors["fg_muted"]
        )
        self._generate_toggle_label.pack(side=tk.LEFT, padx=5)

        self._generate_title_label = None
        if not self._collapsed:
            self._generate_title_label = tk.Label(
                self._generate_header, text="GENERATE", font=(Fonts.FAMILY[0], 9),
                bg=colors["bg"], fg=colors["fg_muted"]
            )
            self._generate_title_label.pack(side=tk.LEFT, padx=5)

        self._generate_header.bind("<Button-1>", lambda e: self._toggle_generate_section())
        self._generate_toggle_label.bind("<Button-1>", lambda e: self._toggle_generate_section())
        if self._generate_title_label:
            self._generate_title_label.bind("<Button-1>", lambda e: self._toggle_generate_section())

        self._generate_container = tk.Frame(self._scrollable_frame, bg=colors["bg"])
        if self._generate_expanded and not self._collapsed:
            self._generate_container.pack(fill=tk.X)

        for item in SidebarConfig.get_generate_items():
            gen_frame = self._create_tool_item(
                item["id"], item["label"], item["icon"], colors,
                container=self._generate_container
            )
            self._generate_items[item["id"]] = gen_frame

    def _toggle_generate_section(self):
        """Toggle the generate section expanded/collapsed state."""
        self._generate_expanded = not self._generate_expanded
        settings_manager.set("sidebar_generate_expanded", self._generate_expanded)

        toggle_icon = Icons.SECTION_OPEN if self._generate_expanded else Icons.SECTION_CLOSED
        self._generate_toggle_label.config(text=toggle_icon)

        if self._generate_expanded:
            self._generate_container.pack(fill=tk.X, after=self._generate_header)
        else:
            self._generate_container.pack_forget()

    # ------------------------------------------------------------------
    # Tools Section
    # ------------------------------------------------------------------

    def _create_tools_section(self, colors: dict):
        """Create the collapsible tools section."""
        self._tools_header = tk.Frame(self._scrollable_frame, bg=colors["bg"], cursor="hand2")
        self._tools_header.pack(fill=tk.X, padx=10, pady=2)

        toggle_icon = Icons.SECTION_OPEN if self._tools_expanded else Icons.SECTION_CLOSED
        self._tools_toggle_label = tk.Label(
            self._tools_header,
            text=toggle_icon if not self._collapsed else Icons.TOOL_WORKFLOW,
            font=(Fonts.FAMILY[0], 10), bg=colors["bg"], fg=colors["fg_muted"]
        )
        self._tools_toggle_label.pack(side=tk.LEFT, padx=5)

        self._tools_title_label = None
        if not self._collapsed:
            self._tools_title_label = tk.Label(
                self._tools_header, text="TOOLS", font=(Fonts.FAMILY[0], 9),
                bg=colors["bg"], fg=colors["fg_muted"]
            )
            self._tools_title_label.pack(side=tk.LEFT, padx=5)

        self._tools_header.bind("<Button-1>", lambda e: self._toggle_tools_section())
        self._tools_toggle_label.bind("<Button-1>", lambda e: self._toggle_tools_section())
        if self._tools_title_label:
            self._tools_title_label.bind("<Button-1>", lambda e: self._toggle_tools_section())

        self._tools_container = tk.Frame(self._scrollable_frame, bg=colors["bg"])
        if self._tools_expanded and not self._collapsed:
            self._tools_container.pack(fill=tk.X)

        for item in SidebarConfig.get_tool_items():
            tool_frame = self._create_tool_item(
                item["id"], item["label"], item["icon"], colors
            )
            self._tool_items[item["id"]] = tool_frame

    def _toggle_tools_section(self):
        """Toggle the tools section expanded/collapsed state."""
        if self._collapsed:
            return

        self._tools_expanded = not self._tools_expanded
        settings_manager.set("sidebar_tools_expanded", self._tools_expanded)

        if self._tools_expanded:
            self._tools_container.pack(fill=tk.X, after=self._tools_header)
            self._tools_toggle_label.config(text=Icons.SECTION_OPEN)
        else:
            self._tools_container.pack_forget()
            self._tools_toggle_label.config(text=Icons.SECTION_CLOSED)
