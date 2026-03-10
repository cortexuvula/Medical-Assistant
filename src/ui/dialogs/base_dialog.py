"""
Base Dialog Framework

Provides a base class that encapsulates common dialog boilerplate:
- Toplevel window creation with geometry and centering
- Modal/non-modal support with grab_set
- Escape key binding and WM_DELETE_WINDOW protocol
- Main frame with padding

Usage:
    class MyDialog(BaseDialog):
        def _get_title(self): return "My Dialog"
        def _get_size(self): return (600, 400)
        def _create_content(self, parent_frame):
            ttk.Label(parent_frame, text="Hello").pack()

        # Call self.close() to dismiss, or set self.result before closing.

    dialog = MyDialog(parent)
    result = dialog.show()
"""

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH
from typing import Any, Optional, Tuple

from ui.scaling_utils import ui_scaler


class BaseDialog:
    """Base class for application dialogs.

    Subclasses override the hook methods to customize title, size,
    and content.  Call ``show()`` to display and (for modal dialogs)
    block until the dialog is closed.  The return value of ``show()``
    is ``self.result``.
    """

    def __init__(self, parent, modal: bool = True):
        self.parent = parent
        self.dialog: Optional[tk.Toplevel] = None
        self.main_frame: Optional[ttk.Frame] = None
        self.result: Any = None
        self._modal = modal

    # ------------------------------------------------------------------
    # Override points
    # ------------------------------------------------------------------

    def _get_title(self) -> str:
        """Return the dialog window title."""
        return "Dialog"

    def _get_size(self) -> Tuple[int, int]:
        """Return (width, height) in logical pixels.

        The values are passed through ``ui_scaler.get_dialog_size``
        before being applied.
        """
        return (700, 500)

    def _get_min_size(self) -> Optional[Tuple[int, int]]:
        """Return (min_width, min_height) or None for no minimum."""
        return None

    def _get_padding(self) -> int:
        """Return padding for the main frame."""
        return 15

    def _create_content(self, parent_frame: ttk.Frame) -> None:
        """Build the dialog content inside *parent_frame*.

        This is the main hook subclasses must implement.
        """
        raise NotImplementedError

    def _on_close(self) -> None:
        """Called just before the dialog window is destroyed.

        Override to run cleanup logic.
        """
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show(self) -> Any:
        """Build the dialog, show it, and return ``self.result``.

        For modal dialogs this blocks until the window is closed.
        """
        self._build_dialog()
        self._create_content(self.main_frame)
        self.dialog.focus_set()
        if self._modal:
            self.parent.wait_window(self.dialog)
        return self.result

    def close(self) -> None:
        """Dismiss the dialog, running ``_on_close`` first."""
        self._on_close()
        if self.dialog and self.dialog.winfo_exists():
            self.dialog.destroy()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_dialog(self) -> None:
        """Create the Toplevel, configure geometry, and build main_frame."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(self._get_title())

        # Size --------------------------------------------------------
        raw_w, raw_h = self._get_size()
        dialog_w, dialog_h = ui_scaler.get_dialog_size(raw_w, raw_h)
        self.dialog.geometry(f"{dialog_w}x{dialog_h}")

        min_size = self._get_min_size()
        if min_size is not None:
            self.dialog.minsize(*min_size)

        # Transient / modal ------------------------------------------
        self.dialog.transient(self.parent)

        # Center on screen --------------------------------------------
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - dialog_w) // 2
        y = (self.dialog.winfo_screenheight() - dialog_h) // 2
        self.dialog.geometry(f"+{x}+{y}")

        # Grab (modal) -----------------------------------------------
        self.dialog.deiconify()
        if self._modal:
            try:
                self.dialog.grab_set()
            except tk.TclError:
                pass  # Window not viewable yet

        # Close bindings ----------------------------------------------
        self.dialog.bind("<Escape>", lambda _e: self.close())
        self.dialog.protocol("WM_DELETE_WINDOW", self.close)

        # Main frame --------------------------------------------------
        self.main_frame = ttk.Frame(self.dialog, padding=self._get_padding())
        self.main_frame.pack(fill=BOTH, expand=True)
