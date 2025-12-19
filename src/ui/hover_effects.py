"""
Hover Effects Module

Provides hover effects for UI elements to improve visual feedback.
"""

import tkinter as tk
import ttkbootstrap as ttk
from typing import Optional, Callable

from ui.ui_constants import Colors


class HoverEffect:
    """Adds hover effects to widgets for better visual feedback."""

    # Default hover scale factors
    HOVER_SCALE = 1.02
    PRESS_SCALE = 0.98

    def __init__(
        self,
        widget: tk.Widget,
        on_enter: Optional[Callable] = None,
        on_leave: Optional[Callable] = None,
        cursor: str = "hand2"
    ) -> None:
        """Initialize hover effect for a widget.

        Args:
            widget: The widget to add hover effects to
            on_enter: Optional callback when mouse enters
            on_leave: Optional callback when mouse leaves
            cursor: Cursor to show on hover (default: hand2/pointer)
        """
        self.widget = widget
        self.on_enter_callback = on_enter
        self.on_leave_callback = on_leave
        self.original_cursor = widget.cget("cursor") if hasattr(widget, "cget") else ""
        self.cursor = cursor

        # Bind events
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")

    def _on_enter(self, event: Optional[tk.Event] = None) -> None:
        """Handle mouse enter event."""
        try:
            self.widget.config(cursor=self.cursor)
            if self.on_enter_callback:
                self.on_enter_callback()
        except tk.TclError:
            pass  # Widget might be destroyed

    def _on_leave(self, event: Optional[tk.Event] = None) -> None:
        """Handle mouse leave event."""
        try:
            self.widget.config(cursor=self.original_cursor)
            if self.on_leave_callback:
                self.on_leave_callback()
        except tk.TclError:
            pass  # Widget might be destroyed


class ButtonHoverEffect(HoverEffect):
    """Adds hover effects specifically for buttons with visual feedback."""

    def __init__(
        self,
        button: ttk.Button,
        hover_bootstyle: Optional[str] = None,
        press_bootstyle: Optional[str] = None
    ) -> None:
        """Initialize button hover effect.

        Args:
            button: The button widget
            hover_bootstyle: Optional bootstyle to apply on hover
            press_bootstyle: Optional bootstyle to apply on press
        """
        self.button = button
        self.hover_bootstyle = hover_bootstyle
        self.press_bootstyle = press_bootstyle

        # Store original style
        try:
            self.original_bootstyle = button.cget("bootstyle")
        except (tk.TclError, AttributeError):
            self.original_bootstyle = None

        super().__init__(button)

        # Add press/release bindings
        button.bind("<ButtonPress-1>", self._on_press, add="+")
        button.bind("<ButtonRelease-1>", self._on_release, add="+")

    def _on_enter(self, event: Optional[tk.Event] = None) -> None:
        """Handle mouse enter with bootstyle change."""
        super()._on_enter(event)
        if self.hover_bootstyle and self.original_bootstyle:
            try:
                # Add solid style on hover (remove outline)
                if "-outline" in str(self.original_bootstyle):
                    solid_style = self.original_bootstyle.replace("-outline", "")
                    self.button.configure(bootstyle=solid_style)
            except (tk.TclError, AttributeError):
                pass

    def _on_leave(self, event: Optional[tk.Event] = None) -> None:
        """Handle mouse leave, restore original bootstyle."""
        super()._on_leave(event)
        if self.original_bootstyle:
            try:
                self.button.configure(bootstyle=self.original_bootstyle)
            except (tk.TclError, AttributeError):
                pass

    def _on_press(self, event: Optional[tk.Event] = None) -> None:
        """Handle button press."""
        if self.press_bootstyle:
            try:
                self.button.configure(bootstyle=self.press_bootstyle)
            except (tk.TclError, AttributeError):
                pass

    def _on_release(self, event: Optional[tk.Event] = None) -> None:
        """Handle button release, restore to hover state if still hovered."""
        # Restore to hover style or original
        try:
            if self.button.winfo_containing(
                self.button.winfo_pointerx(),
                self.button.winfo_pointery()
            ) == self.button:
                # Still hovering, show hover style
                if self.hover_bootstyle and "-outline" in str(self.original_bootstyle):
                    solid_style = self.original_bootstyle.replace("-outline", "")
                    self.button.configure(bootstyle=solid_style)
            else:
                # Not hovering, restore original
                if self.original_bootstyle:
                    self.button.configure(bootstyle=self.original_bootstyle)
        except (tk.TclError, AttributeError):
            pass


class TreeviewHoverEffect:
    """Adds hover effects for Treeview rows."""

    def __init__(
        self,
        treeview: ttk.Treeview,
        hover_bg: str = None,
        hover_fg: Optional[str] = None
    ) -> None:
        """Initialize treeview hover effect.

        Args:
            treeview: The treeview widget
            hover_bg: Background color on hover (default: Colors.HOVER_LIGHT)
            hover_fg: Optional foreground color on hover
        """
        self.treeview = treeview
        self.hover_bg = hover_bg or Colors.HOVER_LIGHT
        self.hover_fg = hover_fg
        self.hovered_item = None

        # Configure hover tag
        treeview.tag_configure("hover", background=self.hover_bg)
        if hover_fg:
            treeview.tag_configure("hover", foreground=hover_fg)

        # Bind events
        treeview.bind("<Motion>", self._on_motion)
        treeview.bind("<Leave>", self._on_leave)

    def _on_motion(self, event: tk.Event) -> None:
        """Handle mouse motion over treeview."""
        item = self.treeview.identify_row(event.y)

        if item != self.hovered_item:
            # Remove hover from previous item
            if self.hovered_item:
                try:
                    tags = list(self.treeview.item(self.hovered_item, "tags"))
                    if "hover" in tags:
                        tags.remove("hover")
                        self.treeview.item(self.hovered_item, tags=tags)
                except tk.TclError:
                    pass  # Item might not exist

            # Add hover to new item
            if item:
                try:
                    tags = list(self.treeview.item(item, "tags"))
                    if "hover" not in tags:
                        tags.append("hover")
                        self.treeview.item(item, tags=tags)
                except tk.TclError:
                    pass

            self.hovered_item = item

    def _on_leave(self, event: Optional[tk.Event] = None) -> None:
        """Handle mouse leaving treeview."""
        if self.hovered_item:
            try:
                tags = list(self.treeview.item(self.hovered_item, "tags"))
                if "hover" in tags:
                    tags.remove("hover")
                    self.treeview.item(self.hovered_item, tags=tags)
            except tk.TclError:
                pass
            self.hovered_item = None


def add_hover_to_button(button: ttk.Button, enable_style_change: bool = True) -> ButtonHoverEffect:
    """Convenience function to add hover effects to a button.

    Args:
        button: The button to add hover effects to
        enable_style_change: Whether to change bootstyle on hover

    Returns:
        ButtonHoverEffect instance
    """
    return ButtonHoverEffect(
        button,
        hover_bootstyle="solid" if enable_style_change else None
    )


def add_hover_to_label(label: ttk.Label, cursor: str = "hand2") -> HoverEffect:
    """Add hover effect to a clickable label.

    Args:
        label: The label widget
        cursor: Cursor to show on hover

    Returns:
        HoverEffect instance
    """
    return HoverEffect(label, cursor=cursor)


def add_hover_to_treeview(
    treeview: ttk.Treeview,
    is_dark: bool = False
) -> TreeviewHoverEffect:
    """Add hover effects to a treeview.

    Args:
        treeview: The treeview widget
        is_dark: Whether dark mode is active

    Returns:
        TreeviewHoverEffect instance
    """
    hover_bg = Colors.HOVER_DARK if is_dark else Colors.HOVER_LIGHT
    return TreeviewHoverEffect(treeview, hover_bg=hover_bg)
