"""
Loading Indicator Module

Provides loading indicators and skeleton screens for async operations.
"""

import tkinter as tk
import ttkbootstrap as ttk
from typing import Optional, Callable

from ui.ui_constants import Colors, Fonts, Animation


class LoadingIndicator:
    """A pulsing loading indicator for async operations."""

    def __init__(
        self,
        parent: tk.Widget,
        text: str = "Loading...",
        show_spinner: bool = True
    ) -> None:
        """Initialize loading indicator.

        Args:
            parent: Parent widget to place the indicator in
            text: Text to display while loading
            show_spinner: Whether to show a spinning indicator
        """
        self.parent = parent
        self.text = text
        self.show_spinner = show_spinner
        self.frame: Optional[ttk.Frame] = None
        self.label: Optional[ttk.Label] = None
        self.spinner_label: Optional[ttk.Label] = None
        self.animation_id: Optional[str] = None
        self.spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.current_frame = 0
        self.is_visible = False

    def show(self) -> None:
        """Show the loading indicator."""
        if self.is_visible:
            return

        self.frame = ttk.Frame(self.parent)
        self.frame.pack(expand=True, fill=tk.BOTH)

        # Center container
        center_frame = ttk.Frame(self.frame)
        center_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        if self.show_spinner:
            self.spinner_label = ttk.Label(
                center_frame,
                text=self.spinner_frames[0],
                font=Fonts.get_font(Fonts.SIZE_HEADER + 4),
                foreground=Colors.STATUS_INFO
            )
            self.spinner_label.pack()

        self.label = ttk.Label(
            center_frame,
            text=self.text,
            font=Fonts.get_font(Fonts.SIZE_LG),
            foreground=Colors.CONTENT_NONE
        )
        self.label.pack(pady=(5, 0))

        self.is_visible = True

        if self.show_spinner:
            self._animate_spinner()

    def hide(self) -> None:
        """Hide the loading indicator."""
        if not self.is_visible:
            return

        if self.animation_id:
            try:
                self.parent.after_cancel(self.animation_id)
            except (tk.TclError, ValueError):
                pass
            self.animation_id = None

        if self.frame:
            self.frame.destroy()
            self.frame = None

        self.is_visible = False

    def _animate_spinner(self) -> None:
        """Animate the spinner."""
        if not self.is_visible or not self.spinner_label:
            return

        try:
            self.current_frame = (self.current_frame + 1) % len(self.spinner_frames)
            self.spinner_label.config(text=self.spinner_frames[self.current_frame])
            self.animation_id = self.parent.after(Animation.SPINNER_INTERVAL, self._animate_spinner)
        except tk.TclError:
            # Widget destroyed
            pass

    def update_text(self, text: str) -> None:
        """Update the loading text.

        Args:
            text: New text to display
        """
        self.text = text
        if self.label:
            try:
                self.label.config(text=text)
            except tk.TclError:
                pass


class LoadingOverlay:
    """A semi-transparent loading overlay for containers."""

    def __init__(
        self,
        parent: tk.Widget,
        text: str = "Loading...",
        bg_color: str = "#ffffff",
        bg_alpha: float = 0.8
    ) -> None:
        """Initialize loading overlay.

        Args:
            parent: Parent widget to overlay
            text: Text to display
            bg_color: Background color
            bg_alpha: Background opacity (0-1)
        """
        self.parent = parent
        self.text = text
        self.bg_color = bg_color
        self.overlay: Optional[tk.Frame] = None
        self.indicator: Optional[LoadingIndicator] = None
        self.is_visible = False

    def show(self) -> None:
        """Show the loading overlay."""
        if self.is_visible:
            return

        # Create overlay frame
        self.overlay = tk.Frame(self.parent, bg=self.bg_color)
        self.overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Add loading indicator
        self.indicator = LoadingIndicator(self.overlay, self.text)
        self.indicator.show()

        self.is_visible = True

    def hide(self) -> None:
        """Hide the loading overlay."""
        if not self.is_visible:
            return

        if self.indicator:
            self.indicator.hide()

        if self.overlay:
            self.overlay.destroy()
            self.overlay = None

        self.is_visible = False

    def update_text(self, text: str) -> None:
        """Update the overlay text."""
        self.text = text
        if self.indicator:
            self.indicator.update_text(text)


class PulsingLabel(ttk.Label):
    """A label that pulses to indicate loading/activity."""

    def __init__(
        self,
        parent: tk.Widget,
        text: str = "Loading...",
        pulse_color: str = None,
        normal_color: str = None,
        **kwargs
    ) -> None:
        """Initialize pulsing label.

        Args:
            parent: Parent widget
            text: Label text
            pulse_color: Color when pulsing bright (default: Colors.STATUS_INFO)
            normal_color: Color when pulsing dim (default: Colors.CONTENT_NONE)
            **kwargs: Additional Label arguments
        """
        super().__init__(parent, text=text, **kwargs)
        self.pulse_color = pulse_color or Colors.STATUS_INFO
        self.normal_color = normal_color or Colors.CONTENT_NONE
        self.animation_id: Optional[str] = None
        self.is_pulsing = False
        self.pulse_step = 0
        self.pulse_direction = 1

    def start_pulse(self) -> None:
        """Start the pulsing animation."""
        if self.is_pulsing:
            return
        self.is_pulsing = True
        self._pulse()

    def stop_pulse(self) -> None:
        """Stop the pulsing animation."""
        self.is_pulsing = False
        if self.animation_id:
            try:
                self.after_cancel(self.animation_id)
            except (tk.TclError, ValueError):
                pass
            self.animation_id = None
        try:
            self.config(foreground=self.normal_color)
        except tk.TclError:
            pass

    def _pulse(self) -> None:
        """Perform one pulse step."""
        if not self.is_pulsing:
            return

        try:
            # Interpolate between colors based on pulse step
            factor = self.pulse_step / 10.0

            # Simple color interpolation
            if factor > 0.5:
                self.config(foreground=self.pulse_color)
            else:
                self.config(foreground=self.normal_color)

            # Update step
            self.pulse_step += self.pulse_direction
            if self.pulse_step >= 10:
                self.pulse_direction = -1
            elif self.pulse_step <= 0:
                self.pulse_direction = 1

            self.animation_id = self.after(Animation.PULSE_INTERVAL, self._pulse)
        except tk.TclError:
            # Widget destroyed
            self.is_pulsing = False


def with_loading(
    container: tk.Widget,
    async_func: Callable,
    loading_text: str = "Loading...",
    on_complete: Optional[Callable] = None
) -> None:
    """Execute an async function with loading indicator.

    Args:
        container: Container to show loading indicator in
        async_func: Function to execute (should accept callback)
        loading_text: Text to show while loading
        on_complete: Callback when complete
    """
    import threading

    indicator = LoadingIndicator(container, loading_text)
    indicator.show()

    def task():
        try:
            result = async_func()
            container.after(0, lambda r=result: _complete(r))
        except Exception as e:
            err = e  # Capture exception before lambda
            container.after(0, lambda error=err: _complete(None, error=error))

    def _complete(result, error=None):
        indicator.hide()
        if on_complete:
            on_complete(result, error)

    threading.Thread(target=task, daemon=True).start()
