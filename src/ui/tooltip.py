import tkinter as tk
from typing import Optional

from ui.ui_constants import Colors, Fonts, Animation


class ToolTip:
    """Tooltip widget that shows helpful text on hover."""

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tipwindow: Optional[tk.Toplevel] = None
        self.after_id: Optional[str] = None
        self.widget.bind("<Enter>", self.schedule_showtip)
        self.widget.bind("<Leave>", self.cancel_showtip)

    def schedule_showtip(self, event: Optional[tk.Event] = None) -> None:
        self.after_id = self.widget.after(Animation.TOOLTIP_DELAY, self.showtip)

    def cancel_showtip(self, event: Optional[tk.Event] = None) -> None:
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None
        self.hidetip()

    def showtip(self) -> None:
        if self.tipwindow or not self.text:
            return
        x = self.widget.winfo_rootx() + 40
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 20
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(
            tw,
            text=self.text,
            justify='left',
            background=Colors.TOOLTIP_BG,
            foreground=Colors.TOOLTIP_FG,
            relief='solid',
            borderwidth=1,
            font=Fonts.get_font(Fonts.SIZE_XS)
        ).pack(ipadx=1)

    def hidetip(self) -> None:
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None
