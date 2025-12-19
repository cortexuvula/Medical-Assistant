"""
Accessibility Module

Provides accessibility features including keyboard navigation, focus management,
screen reader hints, and high contrast support.
"""

import tkinter as tk
import ttkbootstrap as ttk
from typing import Optional, Callable, Dict, List, Tuple
import logging
import platform

from ui.ui_constants import Colors


class KeyboardShortcut:
    """Represents a keyboard shortcut binding."""

    def __init__(
        self,
        key: str,
        callback: Callable,
        description: str,
        modifiers: Optional[List[str]] = None
    ):
        """Initialize a keyboard shortcut.

        Args:
            key: The key (e.g., 'r', 'F1', 'Return')
            callback: Function to call when triggered
            description: Human-readable description
            modifiers: List of modifiers ('Control', 'Alt', 'Shift')
        """
        self.key = key
        self.callback = callback
        self.description = description
        self.modifiers = modifiers or []

    def get_binding_string(self) -> str:
        """Get the tkinter binding string.

        Returns:
            Binding string like '<Control-s>'
        """
        parts = []
        for mod in self.modifiers:
            parts.append(mod)
        parts.append(self.key)
        return f"<{'-'.join(parts)}>"

    def get_display_string(self) -> str:
        """Get the human-readable shortcut string.

        Returns:
            Display string like 'Ctrl+S'
        """
        parts = []
        for mod in self.modifiers:
            if mod == "Control":
                parts.append("Ctrl" if platform.system() != "Darwin" else "Cmd")
            elif mod == "Alt":
                parts.append("Alt" if platform.system() != "Darwin" else "Option")
            else:
                parts.append(mod)
        parts.append(self.key.upper() if len(self.key) == 1 else self.key)
        return "+".join(parts)


class ShortcutManager:
    """Manages keyboard shortcuts for the application."""

    def __init__(self, root: tk.Tk):
        """Initialize the shortcut manager.

        Args:
            root: The root window to bind shortcuts to
        """
        self.root = root
        self.shortcuts: Dict[str, KeyboardShortcut] = {}
        self._enabled = True

    def register(
        self,
        key: str,
        callback: Callable,
        description: str,
        modifiers: Optional[List[str]] = None
    ) -> None:
        """Register a keyboard shortcut.

        Args:
            key: The key to bind
            callback: Callback function
            description: Description for help text
            modifiers: Key modifiers
        """
        shortcut = KeyboardShortcut(key, callback, description, modifiers)
        binding = shortcut.get_binding_string()

        # Store shortcut
        self.shortcuts[binding] = shortcut

        # Bind to root window
        self.root.bind(binding, lambda e: self._handle_shortcut(binding, e))

        logging.debug(f"Registered shortcut: {shortcut.get_display_string()} - {description}")

    def unregister(self, key: str, modifiers: Optional[List[str]] = None) -> None:
        """Unregister a keyboard shortcut.

        Args:
            key: The key to unbind
            modifiers: Key modifiers
        """
        shortcut = KeyboardShortcut(key, lambda: None, "", modifiers)
        binding = shortcut.get_binding_string()

        if binding in self.shortcuts:
            del self.shortcuts[binding]
            self.root.unbind(binding)

    def _handle_shortcut(self, binding: str, event: tk.Event) -> Optional[str]:
        """Handle a shortcut event.

        Args:
            binding: The binding string
            event: The key event

        Returns:
            "break" to prevent further handling
        """
        if not self._enabled:
            return None

        if binding in self.shortcuts:
            try:
                self.shortcuts[binding].callback()
            except Exception as e:
                logging.error(f"Error in shortcut handler: {e}")
            return "break"
        return None

    def enable(self) -> None:
        """Enable shortcut handling."""
        self._enabled = True

    def disable(self) -> None:
        """Disable shortcut handling temporarily."""
        self._enabled = False

    def get_shortcuts_help(self) -> str:
        """Get a formatted help string with all shortcuts.

        Returns:
            Formatted help text
        """
        lines = ["Keyboard Shortcuts:", ""]
        for shortcut in self.shortcuts.values():
            lines.append(f"  {shortcut.get_display_string():20} {shortcut.description}")
        return "\n".join(lines)

    def get_shortcuts_list(self) -> List[Tuple[str, str]]:
        """Get list of shortcuts as (key, description) tuples.

        Returns:
            List of (shortcut_display, description) tuples
        """
        return [
            (s.get_display_string(), s.description)
            for s in self.shortcuts.values()
        ]


class FocusManager:
    """Manages focus traversal and focus indicators."""

    def __init__(self, root: tk.Tk):
        """Initialize the focus manager.

        Args:
            root: The root window
        """
        self.root = root
        self._focus_ring_color = Colors.PRIMARY
        self._focus_widgets: List[tk.Widget] = []
        self._current_focus_index = 0

    def set_focus_order(self, widgets: List[tk.Widget]) -> None:
        """Set the tab focus order for widgets.

        Args:
            widgets: List of widgets in focus order
        """
        self._focus_widgets = widgets

        for i, widget in enumerate(widgets):
            # Set tab traversal
            widget.lift()

            # Bind focus events
            widget.bind("<FocusIn>", lambda e, w=widget: self._on_focus_in(w))
            widget.bind("<FocusOut>", lambda e, w=widget: self._on_focus_out(w))

    def _on_focus_in(self, widget: tk.Widget) -> None:
        """Handle focus in event."""
        if widget in self._focus_widgets:
            self._current_focus_index = self._focus_widgets.index(widget)

        # Add focus indicator
        self._add_focus_indicator(widget)

    def _on_focus_out(self, widget: tk.Widget) -> None:
        """Handle focus out event."""
        self._remove_focus_indicator(widget)

    def _add_focus_indicator(self, widget: tk.Widget) -> None:
        """Add a visual focus indicator to a widget."""
        try:
            # For ttk widgets, we can use a style
            if isinstance(widget, (ttk.Button, ttk.Entry, ttk.Combobox)):
                # Store original style and apply focused style
                pass  # ttkbootstrap handles this automatically
            elif isinstance(widget, tk.Text):
                widget.configure(highlightcolor=self._focus_ring_color, highlightthickness=2)
        except tk.TclError:
            pass

    def _remove_focus_indicator(self, widget: tk.Widget) -> None:
        """Remove the focus indicator from a widget."""
        try:
            if isinstance(widget, tk.Text):
                widget.configure(highlightthickness=0)
        except tk.TclError:
            pass

    def focus_next(self) -> None:
        """Move focus to the next widget in the focus order."""
        if not self._focus_widgets:
            return

        self._current_focus_index = (self._current_focus_index + 1) % len(self._focus_widgets)
        self._focus_widgets[self._current_focus_index].focus_set()

    def focus_previous(self) -> None:
        """Move focus to the previous widget in the focus order."""
        if not self._focus_widgets:
            return

        self._current_focus_index = (self._current_focus_index - 1) % len(self._focus_widgets)
        self._focus_widgets[self._current_focus_index].focus_set()

    def focus_first(self) -> None:
        """Focus the first widget in the focus order."""
        if self._focus_widgets:
            self._current_focus_index = 0
            self._focus_widgets[0].focus_set()

    def focus_last(self) -> None:
        """Focus the last widget in the focus order."""
        if self._focus_widgets:
            self._current_focus_index = len(self._focus_widgets) - 1
            self._focus_widgets[-1].focus_set()


class AccessibleWidget:
    """Mixin class to add accessibility features to widgets."""

    def set_accessible_name(self, name: str) -> None:
        """Set the accessible name for screen readers.

        Args:
            name: The accessible name
        """
        # Store for potential screen reader access
        self._accessible_name = name

    def set_accessible_description(self, description: str) -> None:
        """Set the accessible description for screen readers.

        Args:
            description: The accessible description
        """
        self._accessible_description = description

    def set_accessible_role(self, role: str) -> None:
        """Set the accessible role (button, textbox, etc.).

        Args:
            role: The accessible role
        """
        self._accessible_role = role


def make_accessible(widget: tk.Widget, name: str, description: str = "") -> None:
    """Add accessibility attributes to a widget.

    Args:
        widget: The widget to make accessible
        name: Accessible name
        description: Accessible description
    """
    widget._accessible_name = name
    widget._accessible_description = description

    # Add to widget help text if it's a ttk widget with tooltip support
    if hasattr(widget, 'configure'):
        try:
            # Some widgets support help text
            pass
        except tk.TclError:
            pass


def add_keyboard_hint(widget: tk.Widget, shortcut: str) -> None:
    """Add a keyboard shortcut hint to a widget's tooltip.

    Args:
        widget: The widget
        shortcut: The shortcut string (e.g., "Ctrl+S")
    """
    if hasattr(widget, '_tooltip'):
        current_text = widget._tooltip.text if hasattr(widget._tooltip, 'text') else ""
        widget._tooltip.text = f"{current_text}\n({shortcut})" if current_text else f"({shortcut})"


class HighContrastMode:
    """Manages high contrast mode for accessibility."""

    def __init__(self, root: tk.Tk):
        """Initialize high contrast mode manager.

        Args:
            root: The root window
        """
        self.root = root
        self._enabled = False
        self._original_colors: Dict[str, Dict[str, str]] = {}

    @property
    def enabled(self) -> bool:
        """Check if high contrast mode is enabled."""
        return self._enabled

    def toggle(self) -> None:
        """Toggle high contrast mode."""
        if self._enabled:
            self.disable()
        else:
            self.enable()

    def enable(self) -> None:
        """Enable high contrast mode."""
        if self._enabled:
            return

        self._enabled = True

        # Apply high contrast colors
        self._apply_high_contrast(self.root)

        logging.info("High contrast mode enabled")

    def disable(self) -> None:
        """Disable high contrast mode."""
        if not self._enabled:
            return

        self._enabled = False

        # Restore original colors
        self._restore_colors(self.root)

        logging.info("High contrast mode disabled")

    def _apply_high_contrast(self, widget: tk.Widget) -> None:
        """Apply high contrast colors to a widget and its children."""
        # High contrast color scheme
        hc_bg = "#000000"
        hc_fg = "#FFFFFF"
        hc_highlight = "#FFFF00"

        try:
            # Store original colors
            widget_id = str(id(widget))
            self._original_colors[widget_id] = {}

            if hasattr(widget, 'cget'):
                for option in ['background', 'foreground', 'highlightcolor']:
                    try:
                        self._original_colors[widget_id][option] = widget.cget(option)
                    except tk.TclError:
                        pass

            # Apply high contrast colors
            if isinstance(widget, (tk.Frame, ttk.Frame)):
                try:
                    widget.configure(background=hc_bg)
                except tk.TclError:
                    pass
            elif isinstance(widget, (tk.Label, ttk.Label)):
                try:
                    widget.configure(background=hc_bg, foreground=hc_fg)
                except tk.TclError:
                    pass
            elif isinstance(widget, (tk.Button, ttk.Button)):
                try:
                    widget.configure(background=hc_bg, foreground=hc_fg)
                except tk.TclError:
                    pass
            elif isinstance(widget, tk.Text):
                widget.configure(
                    background=hc_bg,
                    foreground=hc_fg,
                    insertbackground=hc_fg,
                    highlightcolor=hc_highlight
                )

        except Exception as e:
            logging.debug(f"Could not apply high contrast to widget: {e}")

        # Apply to children
        for child in widget.winfo_children():
            self._apply_high_contrast(child)

    def _restore_colors(self, widget: tk.Widget) -> None:
        """Restore original colors for a widget and its children."""
        widget_id = str(id(widget))

        if widget_id in self._original_colors:
            for option, value in self._original_colors[widget_id].items():
                try:
                    widget.configure(**{option: value})
                except tk.TclError:
                    pass

        # Restore children
        for child in widget.winfo_children():
            self._restore_colors(child)


# Convenience functions

def setup_common_shortcuts(
    manager: ShortcutManager,
    callbacks: Dict[str, Callable]
) -> None:
    """Set up common application shortcuts.

    Args:
        manager: The shortcut manager
        callbacks: Dict of callback names to functions
    """
    common_shortcuts = [
        ("s", ["Control"], "save", "Save current work"),
        ("n", ["Control"], "new", "New recording"),
        ("o", ["Control"], "open", "Open recording"),
        ("q", ["Control"], "quit", "Quit application"),
        ("z", ["Control"], "undo", "Undo"),
        ("y", ["Control"], "redo", "Redo"),
        ("F1", [], "help", "Show help"),
        ("t", ["Alt"], "toggle_theme", "Toggle theme"),
        ("r", ["Control"], "record", "Start/stop recording"),
    ]

    for key, mods, name, desc in common_shortcuts:
        if name in callbacks:
            manager.register(key, callbacks[name], desc, mods)


def announce_for_screen_reader(widget: tk.Widget, message: str) -> None:
    """Announce a message for screen readers.

    Note: This is a placeholder. Full screen reader support requires
    platform-specific accessibility APIs.

    Args:
        widget: A widget in the application
        message: Message to announce
    """
    # For now, we log the message. Full implementation would use
    # platform-specific APIs like MSAA/UIA on Windows or ATK on Linux
    logging.debug(f"Screen reader announcement: {message}")
