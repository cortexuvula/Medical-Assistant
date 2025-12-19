"""
Dialog Factory Module

Provides a factory for creating consistent dialogs with proper modal behavior,
centering, theming, and standard button layouts.
"""

import tkinter as tk
import ttkbootstrap as ttk
from typing import Optional, Callable, Dict, List, Any, Tuple
from enum import Enum

from ui.ui_constants import Colors, Fonts, Spacing, DialogConfig, ButtonStyle
from ui.scrollable_frame import ScrollableFrame


class DialogResult(Enum):
    """Dialog result types."""
    OK = "ok"
    CANCEL = "cancel"
    YES = "yes"
    NO = "no"
    CUSTOM = "custom"


class DialogButton:
    """Configuration for a dialog button."""

    def __init__(
        self,
        text: str,
        result: DialogResult = DialogResult.CUSTOM,
        style: str = "primary",
        callback: Optional[Callable] = None,
        is_default: bool = False,
        is_cancel: bool = False
    ):
        """Initialize button configuration.

        Args:
            text: Button text
            result: Result to return when clicked
            style: ttkbootstrap style
            callback: Optional callback before closing
            is_default: Whether this is the default button (Enter key)
            is_cancel: Whether this is the cancel button (Escape key)
        """
        self.text = text
        self.result = result
        self.style = style
        self.callback = callback
        self.is_default = is_default
        self.is_cancel = is_cancel


class BaseDialog:
    """Base class for all dialogs with consistent behavior."""

    def __init__(
        self,
        parent: tk.Widget,
        title: str = "Dialog",
        width: int = 400,
        height: int = 300,
        resizable: Tuple[bool, bool] = (True, True),
        modal: bool = True,
        show_close_button: bool = True
    ):
        """Initialize the base dialog.

        Args:
            parent: Parent widget
            title: Dialog title
            width: Dialog width
            height: Dialog height
            resizable: Tuple of (width_resizable, height_resizable)
            modal: Whether dialog is modal (blocks parent)
            show_close_button: Whether to show the X close button
        """
        self.parent = parent
        self.title = title
        self.width = width
        self.height = height
        self.resizable = resizable
        self.modal = modal
        self.show_close_button = show_close_button

        self.dialog: Optional[tk.Toplevel] = None
        self.result: Optional[DialogResult] = None
        self.result_data: Optional[Any] = None

        # Detect theme
        self._is_dark = self._detect_dark_theme()

    def _detect_dark_theme(self) -> bool:
        """Detect if dark theme is active."""
        try:
            from settings.settings import SETTINGS
            theme = SETTINGS.get("theme", "flatly")
            return theme in ["darkly", "solar", "cyborg", "superhero"]
        except Exception:
            return False

    def _create_dialog(self) -> tk.Toplevel:
        """Create the dialog window."""
        dialog = tk.Toplevel(self.parent)
        dialog.title(self.title)

        # Get screen dimensions
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()

        # Calculate centered geometry
        geometry = DialogConfig.get_centered_geometry(
            screen_width, screen_height,
            self.width, self.height
        )
        dialog.geometry(geometry)

        # Set resizable
        dialog.resizable(*self.resizable)

        # Set minimum size
        dialog.minsize(min(300, self.width), min(200, self.height))

        # Handle close button
        if not self.show_close_button:
            dialog.protocol("WM_DELETE_WINDOW", lambda: None)
        else:
            dialog.protocol("WM_DELETE_WINDOW", self._on_close)

        # Make modal if requested
        if self.modal:
            dialog.transient(self.parent)
            dialog.grab_set()

        # Apply theme colors
        colors = Colors.get_theme_colors(self._is_dark)
        dialog.configure(bg=colors["bg"])

        return dialog

    def _on_close(self) -> None:
        """Handle dialog close."""
        self.result = DialogResult.CANCEL
        self._close()

    def _close(self) -> None:
        """Close the dialog."""
        if self.dialog:
            self.dialog.grab_release()
            self.dialog.destroy()
            self.dialog = None

    def _bind_keys(self) -> None:
        """Bind keyboard shortcuts."""
        self.dialog.bind("<Escape>", lambda e: self._on_escape())

    def _on_escape(self) -> None:
        """Handle Escape key."""
        self.result = DialogResult.CANCEL
        self._close()

    def show(self) -> Optional[DialogResult]:
        """Show the dialog and wait for result.

        Returns:
            DialogResult or None if closed
        """
        self.dialog = self._create_dialog()
        self._bind_keys()
        self._build_content()

        # Wait for dialog to close
        self.dialog.wait_window()

        return self.result

    def _build_content(self) -> None:
        """Build dialog content. Override in subclasses."""
        pass


class MessageDialog(BaseDialog):
    """Simple message dialog with customizable buttons."""

    def __init__(
        self,
        parent: tk.Widget,
        title: str = "Message",
        message: str = "",
        detail: str = "",
        icon: str = "info",
        buttons: Optional[List[DialogButton]] = None,
        **kwargs
    ):
        """Initialize message dialog.

        Args:
            parent: Parent widget
            title: Dialog title
            message: Main message text
            detail: Additional detail text
            icon: Icon type ("info", "warning", "error", "question")
            buttons: List of DialogButton configurations
            **kwargs: Additional BaseDialog arguments
        """
        super().__init__(parent, title, width=400, height=200, **kwargs)

        self.message = message
        self.detail = detail
        self.icon = icon
        self.buttons = buttons or [
            DialogButton("OK", DialogResult.OK, "primary", is_default=True)
        ]

    def _get_icon_text(self) -> str:
        """Get icon character based on type."""
        icons = {
            "info": "ℹ",
            "warning": "⚠",
            "error": "✖",
            "question": "?",
            "success": "✓"
        }
        return icons.get(self.icon, "ℹ")

    def _get_icon_color(self) -> str:
        """Get icon color based on type."""
        colors_map = {
            "info": Colors.STATUS_INFO,
            "warning": Colors.STATUS_WARNING,
            "error": Colors.STATUS_ERROR,
            "question": Colors.STATUS_INFO,
            "success": Colors.STATUS_SUCCESS
        }
        return colors_map.get(self.icon, Colors.STATUS_INFO)

    def _build_content(self) -> None:
        """Build the message dialog content."""
        colors = Colors.get_theme_colors(self._is_dark)

        # Main container
        main_frame = ttk.Frame(self.dialog, padding=Spacing.XL)
        main_frame.pack(fill="both", expand=True)

        # Content frame (icon + text)
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill="both", expand=True)

        # Icon
        icon_label = ttk.Label(
            content_frame,
            text=self._get_icon_text(),
            font=Fonts.get_font(32),
            foreground=self._get_icon_color()
        )
        icon_label.pack(side="left", padx=(0, Spacing.LG))

        # Text container
        text_frame = ttk.Frame(content_frame)
        text_frame.pack(side="left", fill="both", expand=True)

        # Message
        if self.message:
            msg_label = ttk.Label(
                text_frame,
                text=self.message,
                font=Fonts.get_font(Fonts.SIZE_LG, Fonts.WEIGHT_BOLD),
                wraplength=300
            )
            msg_label.pack(anchor="w")

        # Detail
        if self.detail:
            detail_label = ttk.Label(
                text_frame,
                text=self.detail,
                font=Fonts.get_font(Fonts.SIZE_MD),
                foreground=colors["fg_muted"],
                wraplength=300
            )
            detail_label.pack(anchor="w", pady=(Spacing.SM, 0))

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(Spacing.XL, 0))

        # Create buttons (right-aligned)
        for btn_config in reversed(self.buttons):
            btn = ttk.Button(
                button_frame,
                text=btn_config.text,
                bootstyle=btn_config.style,
                command=lambda b=btn_config: self._on_button_click(b)
            )
            btn.pack(side="right", padx=(Spacing.SM, 0))

            # Bind Enter key to default button
            if btn_config.is_default:
                self.dialog.bind("<Return>", lambda e, b=btn_config: self._on_button_click(b))

            # Bind Escape key to cancel button
            if btn_config.is_cancel:
                self.dialog.bind("<Escape>", lambda e, b=btn_config: self._on_button_click(b))

    def _on_button_click(self, btn_config: DialogButton) -> None:
        """Handle button click."""
        if btn_config.callback:
            btn_config.callback()

        self.result = btn_config.result
        self._close()


class InputDialog(BaseDialog):
    """Dialog for getting user input."""

    def __init__(
        self,
        parent: tk.Widget,
        title: str = "Input",
        prompt: str = "",
        default_value: str = "",
        multiline: bool = False,
        password: bool = False,
        **kwargs
    ):
        """Initialize input dialog.

        Args:
            parent: Parent widget
            title: Dialog title
            prompt: Prompt text
            default_value: Default input value
            multiline: Whether to use multiline text widget
            password: Whether to mask input (for passwords)
            **kwargs: Additional BaseDialog arguments
        """
        height = 250 if multiline else 150
        super().__init__(parent, title, width=400, height=height, **kwargs)

        self.prompt = prompt
        self.default_value = default_value
        self.multiline = multiline
        self.password = password
        self.input_widget: Optional[tk.Widget] = None

    def _build_content(self) -> None:
        """Build the input dialog content."""
        # Main container
        main_frame = ttk.Frame(self.dialog, padding=Spacing.XL)
        main_frame.pack(fill="both", expand=True)

        # Prompt
        if self.prompt:
            prompt_label = ttk.Label(
                main_frame,
                text=self.prompt,
                font=Fonts.get_font(Fonts.SIZE_MD)
            )
            prompt_label.pack(anchor="w", pady=(0, Spacing.SM))

        # Input widget
        if self.multiline:
            from ui.scrollable_frame import ScrollableText
            self.input_widget = ScrollableText(
                main_frame,
                undo=True,
                autoseparators=True
            )
            self.input_widget.pack(fill="both", expand=True)
            if self.default_value:
                self.input_widget.insert("1.0", self.default_value)
        else:
            self.input_widget = ttk.Entry(
                main_frame,
                show="*" if self.password else "",
                font=Fonts.get_font(Fonts.SIZE_MD)
            )
            self.input_widget.pack(fill="x")
            if self.default_value:
                self.input_widget.insert(0, self.default_value)
            self.input_widget.select_range(0, "end")
            self.input_widget.focus_set()

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(Spacing.LG, 0))

        # Cancel button
        cancel_btn = ttk.Button(
            button_frame,
            text="Cancel",
            bootstyle="secondary",
            command=self._on_cancel
        )
        cancel_btn.pack(side="right")

        # OK button
        ok_btn = ttk.Button(
            button_frame,
            text="OK",
            bootstyle="primary",
            command=self._on_ok
        )
        ok_btn.pack(side="right", padx=(0, Spacing.SM))

        # Key bindings
        self.dialog.bind("<Return>", lambda e: self._on_ok())
        self.dialog.bind("<Escape>", lambda e: self._on_cancel())

    def _on_ok(self) -> None:
        """Handle OK button."""
        if self.multiline:
            self.result_data = self.input_widget.get("1.0", "end-1c")
        else:
            self.result_data = self.input_widget.get()

        self.result = DialogResult.OK
        self._close()

    def _on_cancel(self) -> None:
        """Handle Cancel button."""
        self.result = DialogResult.CANCEL
        self._close()

    def show(self) -> Optional[str]:
        """Show dialog and return input value.

        Returns:
            Input string or None if cancelled
        """
        super().show()
        if self.result == DialogResult.OK:
            return self.result_data
        return None


class FormDialog(BaseDialog):
    """Dialog with a form layout for multiple inputs."""

    def __init__(
        self,
        parent: tk.Widget,
        title: str = "Form",
        fields: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ):
        """Initialize form dialog.

        Args:
            parent: Parent widget
            title: Dialog title
            fields: List of field configurations
                Each field: {
                    "name": str,
                    "label": str,
                    "type": "text" | "password" | "select" | "checkbox" | "textarea",
                    "default": any,
                    "options": list (for select),
                    "required": bool
                }
            **kwargs: Additional BaseDialog arguments
        """
        height = max(300, 150 + len(fields or []) * 50)
        super().__init__(parent, title, width=500, height=height, **kwargs)

        self.fields = fields or []
        self.field_widgets: Dict[str, tk.Widget] = {}

    def _build_content(self) -> None:
        """Build the form dialog content."""
        # Main container with scrolling
        main_frame = ttk.Frame(self.dialog, padding=Spacing.XL)
        main_frame.pack(fill="both", expand=True)

        # Scrollable form area
        scroll_frame = ScrollableFrame(main_frame)
        scroll_frame.pack(fill="both", expand=True)

        # Create fields
        for i, field in enumerate(self.fields):
            self._create_field(scroll_frame.interior, field, i)

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(Spacing.LG, 0))

        # Cancel button
        cancel_btn = ttk.Button(
            button_frame,
            text="Cancel",
            bootstyle="secondary",
            command=self._on_cancel
        )
        cancel_btn.pack(side="right")

        # OK button
        ok_btn = ttk.Button(
            button_frame,
            text="OK",
            bootstyle="primary",
            command=self._on_ok
        )
        ok_btn.pack(side="right", padx=(0, Spacing.SM))

    def _create_field(
        self,
        parent: tk.Widget,
        field: Dict[str, Any],
        row: int
    ) -> None:
        """Create a form field."""
        name = field.get("name", f"field_{row}")
        label = field.get("label", name)
        field_type = field.get("type", "text")
        default = field.get("default", "")
        options = field.get("options", [])
        required = field.get("required", False)

        # Field container
        field_frame = ttk.Frame(parent)
        field_frame.pack(fill="x", pady=Spacing.SM)

        # Label
        label_text = f"{label}{'*' if required else ''}"
        label_widget = ttk.Label(
            field_frame,
            text=label_text,
            font=Fonts.get_font(Fonts.SIZE_MD),
            width=20,
            anchor="e"
        )
        label_widget.pack(side="left", padx=(0, Spacing.MD))

        # Input widget based on type
        if field_type == "text":
            widget = ttk.Entry(field_frame, font=Fonts.get_font(Fonts.SIZE_MD))
            widget.insert(0, str(default))
            widget.pack(side="left", fill="x", expand=True)

        elif field_type == "password":
            widget = ttk.Entry(
                field_frame,
                font=Fonts.get_font(Fonts.SIZE_MD),
                show="*"
            )
            widget.insert(0, str(default))
            widget.pack(side="left", fill="x", expand=True)

        elif field_type == "select":
            widget = ttk.Combobox(
                field_frame,
                values=options,
                font=Fonts.get_font(Fonts.SIZE_MD),
                state="readonly"
            )
            if default in options:
                widget.set(default)
            elif options:
                widget.set(options[0])
            widget.pack(side="left", fill="x", expand=True)

        elif field_type == "checkbox":
            var = tk.BooleanVar(value=bool(default))
            widget = ttk.Checkbutton(field_frame, variable=var)
            widget.var = var
            widget.pack(side="left")

        elif field_type == "textarea":
            widget = tk.Text(
                field_frame,
                height=3,
                font=Fonts.get_font(Fonts.SIZE_MD)
            )
            widget.insert("1.0", str(default))
            widget.pack(side="left", fill="x", expand=True)

        else:
            widget = ttk.Entry(field_frame, font=Fonts.get_font(Fonts.SIZE_MD))
            widget.insert(0, str(default))
            widget.pack(side="left", fill="x", expand=True)

        self.field_widgets[name] = widget

    def _get_field_values(self) -> Dict[str, Any]:
        """Get all field values."""
        values = {}
        for name, widget in self.field_widgets.items():
            if isinstance(widget, ttk.Combobox):
                values[name] = widget.get()
            elif isinstance(widget, ttk.Checkbutton):
                values[name] = widget.var.get()
            elif isinstance(widget, tk.Text):
                values[name] = widget.get("1.0", "end-1c")
            else:
                values[name] = widget.get()
        return values

    def _on_ok(self) -> None:
        """Handle OK button."""
        self.result_data = self._get_field_values()
        self.result = DialogResult.OK
        self._close()

    def _on_cancel(self) -> None:
        """Handle Cancel button."""
        self.result = DialogResult.CANCEL
        self._close()

    def show(self) -> Optional[Dict[str, Any]]:
        """Show dialog and return form values.

        Returns:
            Dict of field values or None if cancelled
        """
        super().show()
        if self.result == DialogResult.OK:
            return self.result_data
        return None


# Convenience functions

def show_info(
    parent: tk.Widget,
    title: str = "Information",
    message: str = "",
    detail: str = ""
) -> None:
    """Show an information message dialog."""
    dialog = MessageDialog(
        parent, title, message, detail, icon="info",
        buttons=[DialogButton("OK", DialogResult.OK, "primary", is_default=True)]
    )
    dialog.show()


def show_warning(
    parent: tk.Widget,
    title: str = "Warning",
    message: str = "",
    detail: str = ""
) -> None:
    """Show a warning message dialog."""
    dialog = MessageDialog(
        parent, title, message, detail, icon="warning",
        buttons=[DialogButton("OK", DialogResult.OK, "warning", is_default=True)]
    )
    dialog.show()


def show_error(
    parent: tk.Widget,
    title: str = "Error",
    message: str = "",
    detail: str = ""
) -> None:
    """Show an error message dialog."""
    dialog = MessageDialog(
        parent, title, message, detail, icon="error",
        buttons=[DialogButton("OK", DialogResult.OK, "danger", is_default=True)]
    )
    dialog.show()


def ask_yes_no(
    parent: tk.Widget,
    title: str = "Confirm",
    message: str = "",
    detail: str = ""
) -> bool:
    """Show a yes/no confirmation dialog.

    Returns:
        True if Yes was clicked, False otherwise
    """
    dialog = MessageDialog(
        parent, title, message, detail, icon="question",
        buttons=[
            DialogButton("No", DialogResult.NO, "secondary", is_cancel=True),
            DialogButton("Yes", DialogResult.YES, "primary", is_default=True)
        ]
    )
    result = dialog.show()
    return result == DialogResult.YES


def ask_ok_cancel(
    parent: tk.Widget,
    title: str = "Confirm",
    message: str = "",
    detail: str = ""
) -> bool:
    """Show an OK/Cancel confirmation dialog.

    Returns:
        True if OK was clicked, False otherwise
    """
    dialog = MessageDialog(
        parent, title, message, detail, icon="question",
        buttons=[
            DialogButton("Cancel", DialogResult.CANCEL, "secondary", is_cancel=True),
            DialogButton("OK", DialogResult.OK, "primary", is_default=True)
        ]
    )
    result = dialog.show()
    return result == DialogResult.OK


def ask_input(
    parent: tk.Widget,
    title: str = "Input",
    prompt: str = "",
    default_value: str = ""
) -> Optional[str]:
    """Show an input dialog.

    Returns:
        Input string or None if cancelled
    """
    dialog = InputDialog(parent, title, prompt, default_value)
    return dialog.show()
