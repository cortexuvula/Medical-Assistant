"""
Scrollable Frame Module

Provides a reusable scrollable frame component for consistent scrolling behavior
across the application.
"""

import tkinter as tk
import ttkbootstrap as ttk
from typing import Optional, Callable
import platform

from ui.ui_constants import Colors


class ScrollableFrame(ttk.Frame):
    """A frame with built-in scrollbar support.

    This component provides a consistent scrollable container that can be used
    throughout the application. It handles mouse wheel scrolling on all platforms.

    Usage:
        scrollable = ScrollableFrame(parent)
        scrollable.pack(fill="both", expand=True)

        # Add widgets to scrollable.interior
        ttk.Label(scrollable.interior, text="Content here").pack()
    """

    def __init__(
        self,
        parent: tk.Widget,
        scrollbar_side: str = "right",
        scroll_speed: int = 3,
        autohide_scrollbar: bool = False,
        **kwargs
    ) -> None:
        """Initialize the scrollable frame.

        Args:
            parent: Parent widget
            scrollbar_side: Side for scrollbar ("right" or "left")
            scroll_speed: Mouse wheel scroll speed (units per scroll)
            autohide_scrollbar: Whether to hide scrollbar when not needed
            **kwargs: Additional frame arguments
        """
        super().__init__(parent, **kwargs)

        self.scroll_speed = scroll_speed
        self.autohide_scrollbar = autohide_scrollbar
        self._scrollbar_visible = True

        # Create canvas
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)

        # Create scrollbar
        self.scrollbar = ttk.Scrollbar(
            self,
            orient="vertical",
            command=self.canvas.yview
        )

        # Configure canvas
        self.canvas.configure(yscrollcommand=self._on_scroll)

        # Create interior frame
        self.interior = ttk.Frame(self.canvas)
        self.interior_id = self.canvas.create_window(
            (0, 0),
            window=self.interior,
            anchor="nw"
        )

        # Pack widgets
        if scrollbar_side == "left":
            self.scrollbar.pack(side="left", fill="y")
            self.canvas.pack(side="right", fill="both", expand=True)
        else:
            self.canvas.pack(side="left", fill="both", expand=True)
            self.scrollbar.pack(side="right", fill="y")

        # Bind events
        self.interior.bind("<Configure>", self._on_interior_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Bind mouse wheel
        self._bind_mousewheel()

    def _on_scroll(self, *args) -> None:
        """Handle scrollbar updates and autohide."""
        self.scrollbar.set(*args)

        if self.autohide_scrollbar:
            # Check if scrolling is needed
            if float(args[0]) <= 0 and float(args[1]) >= 1:
                # Content fits, hide scrollbar
                if self._scrollbar_visible:
                    self.scrollbar.pack_forget()
                    self._scrollbar_visible = False
            else:
                # Content overflows, show scrollbar
                if not self._scrollbar_visible:
                    self.scrollbar.pack(side="right", fill="y")
                    self._scrollbar_visible = True

    def _on_interior_configure(self, event: tk.Event) -> None:
        """Update scroll region when interior frame is resized."""
        # Update the scroll region to encompass the interior frame
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        """Update interior frame width when canvas is resized."""
        # Make interior frame fill the canvas width
        self.canvas.itemconfig(self.interior_id, width=event.width)

    def _bind_mousewheel(self) -> None:
        """Bind mouse wheel events for scrolling."""
        # Bind to canvas and interior
        self.canvas.bind("<Enter>", self._on_enter)
        self.canvas.bind("<Leave>", self._on_leave)

    def _on_enter(self, event: tk.Event) -> None:
        """Bind mousewheel when entering the frame."""
        system = platform.system()

        if system == "Linux":
            self.canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
            self.canvas.bind_all("<Button-5>", self._on_mousewheel_linux)
        else:
            self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_leave(self, event: tk.Event) -> None:
        """Unbind mousewheel when leaving the frame."""
        system = platform.system()

        if system == "Linux":
            self.canvas.unbind_all("<Button-4>")
            self.canvas.unbind_all("<Button-5>")
        else:
            self.canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event: tk.Event) -> None:
        """Handle mouse wheel scrolling (Windows/macOS)."""
        # Windows uses event.delta (positive = up, negative = down)
        # macOS also uses event.delta but with different scale
        if platform.system() == "Darwin":
            delta = -event.delta
        else:
            delta = -event.delta // 120

        self.canvas.yview_scroll(delta * self.scroll_speed, "units")

    def _on_mousewheel_linux(self, event: tk.Event) -> None:
        """Handle mouse wheel scrolling (Linux)."""
        if event.num == 4:
            self.canvas.yview_scroll(-self.scroll_speed, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(self.scroll_speed, "units")

    def scroll_to_top(self) -> None:
        """Scroll to the top of the content."""
        self.canvas.yview_moveto(0)

    def scroll_to_bottom(self) -> None:
        """Scroll to the bottom of the content."""
        self.canvas.yview_moveto(1)

    def scroll_to_widget(self, widget: tk.Widget) -> None:
        """Scroll to make a widget visible.

        Args:
            widget: The widget to scroll to
        """
        self.canvas.update_idletasks()

        # Get widget position relative to interior
        widget_y = widget.winfo_y()
        interior_height = self.interior.winfo_height()
        canvas_height = self.canvas.winfo_height()

        if interior_height > canvas_height:
            # Calculate scroll position
            scroll_pos = widget_y / interior_height
            self.canvas.yview_moveto(scroll_pos)

    def update_theme(self, is_dark: bool) -> None:
        """Update colors for theme change.

        Args:
            is_dark: Whether dark mode is active
        """
        colors = Colors.get_theme_colors(is_dark)
        self.canvas.configure(bg=colors["bg"])


class HorizontalScrollableFrame(ttk.Frame):
    """A frame with horizontal scrollbar support."""

    def __init__(
        self,
        parent: tk.Widget,
        scrollbar_side: str = "bottom",
        scroll_speed: int = 3,
        **kwargs
    ) -> None:
        """Initialize the horizontal scrollable frame.

        Args:
            parent: Parent widget
            scrollbar_side: Side for scrollbar ("top" or "bottom")
            scroll_speed: Mouse wheel scroll speed
            **kwargs: Additional frame arguments
        """
        super().__init__(parent, **kwargs)

        self.scroll_speed = scroll_speed

        # Create canvas
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)

        # Create scrollbar
        self.scrollbar = ttk.Scrollbar(
            self,
            orient="horizontal",
            command=self.canvas.xview
        )

        # Configure canvas
        self.canvas.configure(xscrollcommand=self.scrollbar.set)

        # Create interior frame
        self.interior = ttk.Frame(self.canvas)
        self.interior_id = self.canvas.create_window(
            (0, 0),
            window=self.interior,
            anchor="nw"
        )

        # Pack widgets
        if scrollbar_side == "top":
            self.scrollbar.pack(side="top", fill="x")
            self.canvas.pack(side="bottom", fill="both", expand=True)
        else:
            self.canvas.pack(side="top", fill="both", expand=True)
            self.scrollbar.pack(side="bottom", fill="x")

        # Bind events
        self.interior.bind("<Configure>", self._on_interior_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_interior_configure(self, event: tk.Event) -> None:
        """Update scroll region when interior frame is resized."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        """Update interior frame height when canvas is resized."""
        self.canvas.itemconfig(self.interior_id, height=event.height)

    def scroll_to_start(self) -> None:
        """Scroll to the start (left) of the content."""
        self.canvas.xview_moveto(0)

    def scroll_to_end(self) -> None:
        """Scroll to the end (right) of the content."""
        self.canvas.xview_moveto(1)


class ScrollableText(ttk.Frame):
    """A text widget with integrated scrollbar."""

    def __init__(
        self,
        parent: tk.Widget,
        scrollbar_side: str = "right",
        wrap: str = "word",
        **text_kwargs
    ) -> None:
        """Initialize the scrollable text widget.

        Args:
            parent: Parent widget
            scrollbar_side: Side for scrollbar
            wrap: Text wrapping mode ("word", "char", "none")
            **text_kwargs: Additional Text widget arguments
        """
        super().__init__(parent)

        # Create scrollbar
        self.scrollbar = ttk.Scrollbar(self, orient="vertical")

        # Create text widget
        self.text = tk.Text(
            self,
            wrap=wrap,
            yscrollcommand=self.scrollbar.set,
            **text_kwargs
        )

        # Configure scrollbar
        self.scrollbar.configure(command=self.text.yview)

        # Pack widgets
        if scrollbar_side == "left":
            self.scrollbar.pack(side="left", fill="y")
            self.text.pack(side="right", fill="both", expand=True)
        else:
            self.text.pack(side="left", fill="both", expand=True)
            self.scrollbar.pack(side="right", fill="y")

    def get(self, *args, **kwargs):
        """Get text content."""
        return self.text.get(*args, **kwargs)

    def insert(self, *args, **kwargs):
        """Insert text."""
        return self.text.insert(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Delete text."""
        return self.text.delete(*args, **kwargs)

    def configure(self, **kwargs):
        """Configure the text widget."""
        return self.text.configure(**kwargs)

    config = configure

    def update_theme(self, is_dark: bool) -> None:
        """Update colors for theme change."""
        colors = Colors.get_theme_colors(is_dark)
        self.text.configure(
            bg=colors["bg"],
            fg=colors["fg"],
            insertbackground=colors["fg"]
        )
