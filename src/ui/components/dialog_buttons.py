"""
Standardized Dialog Button Component

Provides consistent button layout and styling for all dialogs in the application.
Follows the standard layout: [Secondary buttons...] [Cancel] [Primary]
"""

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import X, LEFT, RIGHT
from typing import Callable, Optional, List, Tuple
from utils.structured_logging import get_logger

from ui.tooltip import ToolTip

logger = get_logger(__name__)


class DialogButtonRow(ttk.Frame):
    """Standardized dialog button row with consistent layout.

    Layout follows platform conventions:
    [Secondary buttons...] [spacer] [Cancel] [Primary]

    This ensures all dialogs have consistent button ordering and styling.

    Example:
        # Basic usage with OK/Cancel
        buttons = DialogButtonRow(
            parent=dialog_frame,
            on_cancel=self.cancel,
            on_primary=self.save,
            primary_text="Save"
        )
        buttons.pack(fill=X, padx=10, pady=10)

        # With secondary buttons
        buttons = DialogButtonRow(
            parent=dialog_frame,
            on_cancel=self.cancel,
            on_primary=self.save,
            primary_text="Save",
            secondary_buttons=[
                ("Delete", self.delete, "danger", "Delete this item"),
                ("Reset", self.reset, "secondary", "Reset to defaults")
            ]
        )
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_cancel: Callable,
        on_primary: Callable,
        primary_text: str = "OK",
        cancel_text: str = "Cancel",
        primary_style: str = "primary",
        secondary_buttons: Optional[List[Tuple]] = None,
        primary_tooltip: Optional[str] = None,
        cancel_tooltip: Optional[str] = None,
        show_cancel: bool = True,
        **kwargs
    ):
        """Initialize the dialog button row.

        Args:
            parent: Parent widget
            on_cancel: Callback for Cancel button
            on_primary: Callback for Primary button
            primary_text: Text for primary button (default: "OK")
            cancel_text: Text for cancel button (default: "Cancel")
            primary_style: ttkbootstrap style for primary button (default: "primary")
            secondary_buttons: Optional list of secondary button specs.
                Each spec is a tuple: (text, command, style, tooltip)
                Style and tooltip are optional.
            primary_tooltip: Optional tooltip for primary button
            cancel_tooltip: Optional tooltip for cancel button
            show_cancel: Whether to show cancel button (default: True)
            **kwargs: Additional Frame arguments
        """
        super().__init__(parent, **kwargs)

        self._on_cancel = on_cancel
        self._on_primary = on_primary
        self._primary_btn = None
        self._cancel_btn = None
        self._secondary_btns = []

        # Secondary buttons on the left
        if secondary_buttons:
            for btn_spec in secondary_buttons:
                text = btn_spec[0]
                command = btn_spec[1]
                style = btn_spec[2] if len(btn_spec) > 2 else "secondary"
                tooltip = btn_spec[3] if len(btn_spec) > 3 else None

                btn = ttk.Button(
                    self,
                    text=text,
                    command=command,
                    bootstyle=style
                )
                btn.pack(side=LEFT, padx=(0, 5))
                self._secondary_btns.append(btn)

                if tooltip:
                    ToolTip(btn, tooltip)

        # Spacer to push primary/cancel to the right
        spacer = ttk.Frame(self)
        spacer.pack(side=LEFT, fill=X, expand=True)

        # Primary button (rightmost)
        self._primary_btn = ttk.Button(
            self,
            text=primary_text,
            command=self._handle_primary,
            bootstyle=primary_style
        )
        self._primary_btn.pack(side=RIGHT, padx=(5, 0))

        if primary_tooltip:
            ToolTip(self._primary_btn, primary_tooltip)

        # Cancel button (to the left of primary)
        if show_cancel:
            self._cancel_btn = ttk.Button(
                self,
                text=cancel_text,
                command=self._handle_cancel,
                bootstyle="secondary"
            )
            self._cancel_btn.pack(side=RIGHT, padx=(5, 0))

            if cancel_tooltip:
                ToolTip(self._cancel_btn, cancel_tooltip)

    def _handle_primary(self):
        """Handle primary button click."""
        try:
            self._on_primary()
        except Exception as e:
            logger.error(f"Error in primary button callback: {e}")

    def _handle_cancel(self):
        """Handle cancel button click."""
        try:
            self._on_cancel()
        except Exception as e:
            logger.error(f"Error in cancel button callback: {e}")

    def set_primary_enabled(self, enabled: bool):
        """Enable or disable the primary button.

        Args:
            enabled: Whether the button should be enabled
        """
        state = NORMAL if enabled else DISABLED
        if self._primary_btn:
            self._primary_btn.config(state=state)

    def set_cancel_enabled(self, enabled: bool):
        """Enable or disable the cancel button.

        Args:
            enabled: Whether the button should be enabled
        """
        state = NORMAL if enabled else DISABLED
        if self._cancel_btn:
            self._cancel_btn.config(state=state)

    def set_primary_text(self, text: str):
        """Update the primary button text.

        Args:
            text: New button text
        """
        if self._primary_btn:
            self._primary_btn.config(text=text)

    def get_primary_button(self) -> Optional[ttk.Button]:
        """Get reference to the primary button widget."""
        return self._primary_btn

    def get_cancel_button(self) -> Optional[ttk.Button]:
        """Get reference to the cancel button widget."""
        return self._cancel_btn


class DialogButtonFactory:
    """Factory for creating common dialog button configurations."""

    @staticmethod
    def create_ok_cancel(
        parent: tk.Widget,
        on_ok: Callable,
        on_cancel: Callable,
        ok_text: str = "OK",
        **kwargs
    ) -> DialogButtonRow:
        """Create a standard OK/Cancel button row.

        Args:
            parent: Parent widget
            on_ok: Callback for OK button
            on_cancel: Callback for Cancel button
            ok_text: Text for OK button (default: "OK")
            **kwargs: Additional arguments for DialogButtonRow

        Returns:
            Configured DialogButtonRow
        """
        return DialogButtonRow(
            parent=parent,
            on_cancel=on_cancel,
            on_primary=on_ok,
            primary_text=ok_text,
            **kwargs
        )

    @staticmethod
    def create_save_cancel(
        parent: tk.Widget,
        on_save: Callable,
        on_cancel: Callable,
        **kwargs
    ) -> DialogButtonRow:
        """Create a Save/Cancel button row.

        Args:
            parent: Parent widget
            on_save: Callback for Save button
            on_cancel: Callback for Cancel button
            **kwargs: Additional arguments for DialogButtonRow

        Returns:
            Configured DialogButtonRow
        """
        return DialogButtonRow(
            parent=parent,
            on_cancel=on_cancel,
            on_primary=on_save,
            primary_text="Save",
            primary_style="success",
            primary_tooltip="Save changes",
            cancel_tooltip="Discard changes",
            **kwargs
        )

    @staticmethod
    def create_close_only(
        parent: tk.Widget,
        on_close: Callable,
        close_text: str = "Close",
        **kwargs
    ) -> DialogButtonRow:
        """Create a dialog with only a Close button.

        Args:
            parent: Parent widget
            on_close: Callback for Close button
            close_text: Text for Close button (default: "Close")
            **kwargs: Additional arguments for DialogButtonRow

        Returns:
            Configured DialogButtonRow
        """
        return DialogButtonRow(
            parent=parent,
            on_cancel=on_close,
            on_primary=on_close,
            primary_text=close_text,
            show_cancel=False,
            **kwargs
        )

    @staticmethod
    def create_yes_no(
        parent: tk.Widget,
        on_yes: Callable,
        on_no: Callable,
        **kwargs
    ) -> DialogButtonRow:
        """Create a Yes/No button row.

        Args:
            parent: Parent widget
            on_yes: Callback for Yes button
            on_no: Callback for No button
            **kwargs: Additional arguments for DialogButtonRow

        Returns:
            Configured DialogButtonRow
        """
        return DialogButtonRow(
            parent=parent,
            on_cancel=on_no,
            on_primary=on_yes,
            primary_text="Yes",
            cancel_text="No",
            primary_style="success",
            **kwargs
        )

    @staticmethod
    def create_with_delete(
        parent: tk.Widget,
        on_save: Callable,
        on_cancel: Callable,
        on_delete: Callable,
        **kwargs
    ) -> DialogButtonRow:
        """Create a dialog with Delete, Cancel, and Save buttons.

        Args:
            parent: Parent widget
            on_save: Callback for Save button
            on_cancel: Callback for Cancel button
            on_delete: Callback for Delete button
            **kwargs: Additional arguments for DialogButtonRow

        Returns:
            Configured DialogButtonRow
        """
        return DialogButtonRow(
            parent=parent,
            on_cancel=on_cancel,
            on_primary=on_save,
            primary_text="Save",
            primary_style="success",
            secondary_buttons=[
                ("Delete", on_delete, "danger", "Delete this item")
            ],
            **kwargs
        )


# Module-level factory instance for convenience
button_factory = DialogButtonFactory()
