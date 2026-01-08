"""
Sidebar Navigation Component for Medical Assistant
Provides left sidebar navigation with collapsible sections
"""

import tkinter as tk
import ttkbootstrap as ttk
from typing import Dict, Callable, Optional, List
import logging
import platform

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
        {"id": "advanced_analysis", "label": "Analysis", "icon": Icons.NAV_ADVANCED_ANALYSIS},
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

    def _create_scrollable_section(self, colors: dict):
        """Create the scrollable middle section of the sidebar."""
        # Create container frame for canvas and scrollbar
        scroll_container = tk.Frame(self._content_frame, bg=colors["bg"])
        scroll_container.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        self._scroll_container = scroll_container

        # Create canvas for scrolling
        self._scroll_canvas = tk.Canvas(
            scroll_container,
            bg=colors["bg"],
            highlightthickness=0,
            borderwidth=0
        )
        self._scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Create fade overlay for scroll indicator (placed on top)
        self._scroll_fade_overlay = tk.Canvas(
            scroll_container,
            height=24,
            bg=colors["bg"],
            highlightthickness=0,
            borderwidth=0
        )
        # Use place geometry manager to overlay at bottom
        # place() naturally stacks later widgets on top
        self._scroll_fade_overlay.place(relx=0, rely=1.0, relwidth=1.0, anchor="sw")

        # Create custom scrollbar - a thin canvas-based scrollbar for better theming
        scrollbar_width = 6 if not self._collapsed else 4
        self._scrollbar = tk.Canvas(
            scroll_container,
            width=scrollbar_width,
            bg=colors["bg"],
            highlightthickness=0,
            borderwidth=0
        )
        # Don't pack scrollbar initially - will be shown when needed

        # Scrollbar colors
        self._scrollbar_colors = {
            "track": colors["bg"],
            "thumb": colors["fg_muted"],
            "thumb_hover": colors["fg"]
        }
        self._scrollbar_dragging = False
        self._scrollbar_hover = False

        # Bind scrollbar events
        self._scrollbar.bind("<Button-1>", self._on_scrollbar_click)
        self._scrollbar.bind("<B1-Motion>", self._on_scrollbar_drag)
        self._scrollbar.bind("<ButtonRelease-1>", self._on_scrollbar_release)
        self._scrollbar.bind("<Enter>", self._on_scrollbar_enter)
        self._scrollbar.bind("<Leave>", self._on_scrollbar_leave)

        # Create interior frame for scrollable content
        self._scrollable_frame = tk.Frame(self._scroll_canvas, bg=colors["bg"])
        self._scroll_window_id = self._scroll_canvas.create_window(
            (0, 0),
            window=self._scrollable_frame,
            anchor="nw"
        )

        # Bind events for scroll region
        self._scrollable_frame.bind("<Configure>", self._on_scrollable_configure)
        self._scroll_canvas.bind("<Configure>", self._on_canvas_configure)

        # Bind mouse wheel for scrolling
        self._bind_mousewheel()

    def _on_scrollable_configure(self, event: tk.Event):
        """Update scroll region when scrollable frame is resized."""
        self._scroll_canvas.configure(scrollregion=self._scroll_canvas.bbox("all"))
        self._update_scrollbar_visibility()
        self._draw_scrollbar()
        self._update_scroll_indicator()

    def _on_canvas_configure(self, event: tk.Event):
        """Update scrollable frame width when canvas is resized."""
        self._scroll_canvas.itemconfig(self._scroll_window_id, width=event.width)
        self._update_scrollbar_visibility()
        self._draw_scrollbar()
        self._update_scroll_indicator()

    def _update_scrollbar_visibility(self):
        """Show or hide scrollbar based on content size."""
        if not self._scrollbar or not self._scroll_canvas:
            return

        try:
            canvas_height = self._scroll_canvas.winfo_height()
            bbox = self._scroll_canvas.bbox("all")
            if bbox:
                content_height = bbox[3] - bbox[1]
            else:
                content_height = 0

            # Show scrollbar only if content exceeds canvas height
            needs_scrollbar = content_height > canvas_height + 5  # 5px tolerance

            if needs_scrollbar:
                if not self._scrollbar.winfo_ismapped():
                    self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 2), pady=2)
            else:
                if self._scrollbar.winfo_ismapped():
                    self._scrollbar.pack_forget()
        except tk.TclError:
            pass  # Widget destroyed

    def _draw_scrollbar(self):
        """Draw the scrollbar thumb on the scrollbar canvas."""
        if not self._scrollbar or not self._scroll_canvas:
            return

        try:
            if not self._scrollbar.winfo_ismapped():
                return

            # Clear previous drawings
            self._scrollbar.delete("all")

            canvas_height = self._scroll_canvas.winfo_height()
            bbox = self._scroll_canvas.bbox("all")
            if not bbox:
                return

            content_height = bbox[3] - bbox[1]
            if content_height <= canvas_height:
                return

            scrollbar_height = self._scrollbar.winfo_height()
            scrollbar_width = self._scrollbar.winfo_width()

            # Calculate thumb size and position
            thumb_height = max(30, (canvas_height / content_height) * scrollbar_height)

            # Get current scroll position
            yview = self._scroll_canvas.yview()
            thumb_top = yview[0] * (scrollbar_height - thumb_height)

            # Choose thumb color based on state
            if self._scrollbar_dragging or self._scrollbar_hover:
                thumb_color = self._scrollbar_colors["thumb_hover"]
            else:
                thumb_color = self._scrollbar_colors["thumb"]

            # Draw rounded rectangle thumb
            padding = 1
            self._scrollbar.create_oval(
                padding, thumb_top + padding,
                scrollbar_width - padding, thumb_top + 4 + padding,
                fill=thumb_color, outline=thumb_color
            )
            self._scrollbar.create_rectangle(
                padding, thumb_top + 2 + padding,
                scrollbar_width - padding, thumb_top + thumb_height - 2 - padding,
                fill=thumb_color, outline=thumb_color
            )
            self._scrollbar.create_oval(
                padding, thumb_top + thumb_height - 4 - padding,
                scrollbar_width - padding, thumb_top + thumb_height - padding,
                fill=thumb_color, outline=thumb_color
            )
        except tk.TclError:
            pass  # Widget destroyed

    def _update_scroll_indicator(self):
        """Update the scroll fade indicator based on scroll position."""
        if not self._scroll_fade_overlay or not self._scroll_canvas:
            return

        try:
            canvas_height = self._scroll_canvas.winfo_height()
            bbox = self._scroll_canvas.bbox("all")
            if not bbox:
                self._scroll_fade_overlay.place_forget()
                return

            content_height = bbox[3] - bbox[1]

            # Check if content is scrollable and not at bottom
            if content_height <= canvas_height + 5:
                # No scrolling needed - hide indicator
                self._scroll_fade_overlay.place_forget()
                return

            # Get current scroll position
            yview = self._scroll_canvas.yview()
            at_bottom = yview[1] >= 0.99  # Allow small tolerance

            if at_bottom:
                # At bottom - hide indicator
                self._scroll_fade_overlay.place_forget()
            else:
                # Show fade indicator
                if not self._scroll_fade_overlay.winfo_ismapped():
                    self._scroll_fade_overlay.place(relx=0, rely=1.0, relwidth=1.0, anchor="sw")

                # Draw gradient fade effect
                self._draw_scroll_fade()

        except tk.TclError:
            pass  # Widget destroyed

    def _draw_scroll_fade(self):
        """Draw the gradient fade effect on the scroll indicator."""
        if not self._scroll_fade_overlay or not self._colors:
            return

        try:
            self._scroll_fade_overlay.delete("all")

            width = self._scroll_fade_overlay.winfo_width()
            height = self._scroll_fade_overlay.winfo_height()

            if width <= 1 or height <= 1:
                return

            bg_color = self._colors["bg"]
            # Create gradient effect with multiple rectangles
            # From transparent (top) to solid bg color (bottom)
            steps = 8
            for i in range(steps):
                # Calculate alpha-like effect by blending with bg
                y1 = int(height * i / steps)
                y2 = int(height * (i + 1) / steps)

                # Use stipple pattern for transparency effect on older displays
                # or just draw gradient bars
                alpha = i / (steps - 1) if steps > 1 else 1
                self._scroll_fade_overlay.create_rectangle(
                    0, y1, width, y2,
                    fill=bg_color,
                    outline=bg_color,
                    stipple="" if alpha > 0.5 else "gray50"
                )

            # Draw a subtle indicator arrow/chevron at bottom center
            center_x = width // 2
            arrow_y = height - 6
            arrow_size = 4
            indicator_color = self._colors.get("fg_muted", "#888888")

            # Draw down chevron
            self._scroll_fade_overlay.create_line(
                center_x - arrow_size, arrow_y - arrow_size // 2,
                center_x, arrow_y + arrow_size // 2,
                center_x + arrow_size, arrow_y - arrow_size // 2,
                fill=indicator_color,
                width=1.5,
                capstyle=tk.ROUND,
                joinstyle=tk.ROUND
            )

        except tk.TclError:
            pass  # Widget destroyed

    def _on_scrollbar_click(self, event: tk.Event):
        """Handle click on scrollbar."""
        self._scrollbar_dragging = True
        self._scrollbar_drag_start_y = event.y
        self._scroll_to_position(event.y)

    def _on_scrollbar_drag(self, event: tk.Event):
        """Handle drag on scrollbar."""
        if self._scrollbar_dragging:
            self._scroll_to_position(event.y)

    def _on_scrollbar_release(self, event: tk.Event):
        """Handle release of scrollbar."""
        self._scrollbar_dragging = False
        self._draw_scrollbar()

    def _on_scrollbar_enter(self, event: tk.Event):
        """Handle mouse entering scrollbar."""
        self._scrollbar_hover = True
        self._draw_scrollbar()

    def _on_scrollbar_leave(self, event: tk.Event):
        """Handle mouse leaving scrollbar."""
        self._scrollbar_hover = False
        if not self._scrollbar_dragging:
            self._draw_scrollbar()

    def _scroll_to_position(self, y: int):
        """Scroll content to match scrollbar position."""
        if not self._scrollbar:
            return

        try:
            scrollbar_height = self._scrollbar.winfo_height()
            canvas_height = self._scroll_canvas.winfo_height()
            bbox = self._scroll_canvas.bbox("all")

            if not bbox:
                return

            content_height = bbox[3] - bbox[1]
            if content_height <= canvas_height:
                return

            thumb_height = max(30, (canvas_height / content_height) * scrollbar_height)

            # Calculate scroll fraction
            scroll_range = scrollbar_height - thumb_height
            if scroll_range <= 0:
                return

            fraction = max(0, min(1, (y - thumb_height / 2) / scroll_range))
            self._scroll_canvas.yview_moveto(fraction)
            self._draw_scrollbar()
            self._update_scroll_indicator()
        except tk.TclError:
            pass  # Widget destroyed

    def _bind_mousewheel(self):
        """Bind mouse wheel events for scrolling."""
        self._scroll_canvas.bind("<Enter>", self._on_scroll_enter)
        self._scroll_canvas.bind("<Leave>", self._on_scroll_leave)

    def _on_scroll_enter(self, event: tk.Event):
        """Bind mousewheel when entering the scrollable area."""
        system = platform.system()
        if system == "Linux":
            self._scroll_canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
            self._scroll_canvas.bind_all("<Button-5>", self._on_mousewheel_linux)
        else:
            self._scroll_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_scroll_leave(self, event: tk.Event):
        """Unbind mousewheel when leaving the scrollable area."""
        system = platform.system()
        if system == "Linux":
            self._scroll_canvas.unbind_all("<Button-4>")
            self._scroll_canvas.unbind_all("<Button-5>")
        else:
            self._scroll_canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event: tk.Event):
        """Handle mouse wheel scrolling (Windows/macOS)."""
        if platform.system() == "Darwin":
            delta = -event.delta
        else:
            delta = -event.delta // 120
        self._scroll_canvas.yview_scroll(delta * 3, "units")
        self._draw_scrollbar()
        self._update_scroll_indicator()

    def _on_mousewheel_linux(self, event: tk.Event):
        """Handle mouse wheel scrolling (Linux)."""
        if event.num == 4:
            self._scroll_canvas.yview_scroll(-3, "units")
        elif event.num == 5:
            self._scroll_canvas.yview_scroll(3, "units")
        self._draw_scrollbar()
        self._update_scroll_indicator()

    def _detect_dark_theme(self) -> bool:
        """Detect if dark theme is currently active."""
        current_theme = SETTINGS.get("theme", "darkly")
        dark_themes = ["darkly", "solar", "cyborg", "superhero", "vapor"]
        return current_theme.lower() in dark_themes

    def _create_header(self, colors: dict):
        """Create the sidebar header with toggle button."""
        header = tk.Frame(self._header_frame, bg=colors["bg"])
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

    def _create_separator(self, colors: dict, parent=None):
        """Create a horizontal separator line.

        Args:
            colors: Color scheme dict
            parent: Optional parent frame (defaults to scrollable frame)
        """
        container = parent if parent else self._scrollable_frame
        sep = tk.Frame(container, bg=colors["border"], height=1)
        sep.pack(fill=tk.X, padx=10, pady=5)

    def _create_nav_section(self, colors: dict):
        """Create the main navigation items section."""
        # Section header
        if not self._collapsed:
            section_header = tk.Label(
                self._scrollable_frame,
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
        self._file_header = tk.Frame(self._scrollable_frame, bg=colors["bg"], cursor="hand2")
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
        self._file_container = tk.Frame(self._scrollable_frame, bg=colors["bg"])
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
        self._generate_header = tk.Frame(self._scrollable_frame, bg=colors["bg"], cursor="hand2")
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
        self._generate_container = tk.Frame(self._scrollable_frame, bg=colors["bg"])
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
        self._tools_header = tk.Frame(self._scrollable_frame, bg=colors["bg"], cursor="hand2")
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
        self._tools_container = tk.Frame(self._scrollable_frame, bg=colors["bg"])
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
            self._scrollable_frame,
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
        """Create the footer section (placeholder for future items)."""
        # Footer is now empty - credentials removed
        # Keep this method for future footer items if needed
        pass

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
        self._header_frame = None
        self._footer_frame = None
        self._scroll_canvas = None
        self._scrollable_frame = None
        self._scroll_fade_overlay = None
        self._scroll_container = None

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
            logging.debug(f"Could not update parent geometry: {e}")

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
