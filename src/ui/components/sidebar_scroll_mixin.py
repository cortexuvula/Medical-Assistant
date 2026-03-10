"""
Scroll-related mixin for SidebarNavigation.

This mixin provides all scrollable section related methods for the
SidebarNavigation class, including custom scrollbar drawing, mousewheel
handling, scroll indicators, and fade effects.
"""

from __future__ import annotations

import platform
import tkinter as tk

from utils.structured_logging import get_logger

logger = get_logger(__name__)


class SidebarScrollMixin:
    """Mixin providing scroll-related methods for SidebarNavigation.

    Expects the host class to provide:
        - self._content_frame: Frame containing sidebar content
        - self._collapsed: bool indicating sidebar collapsed state
        - self._scroll_canvas: Canvas for scrolling
        - self._scrollbar: Canvas for custom scrollbar
        - self._scrollable_frame: Frame inside scroll canvas
        - self._scroll_fade_overlay: Canvas for fade effect
        - self._scroll_window_id: Canvas window id
        - self._scrollbar_colors: Dict of scrollbar colors
        - self._scrollbar_dragging: bool
        - self._scrollbar_hover: bool
        - self._colors: Dict of color scheme
    """

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
