import tkinter as tk
from typing import Optional

TOOLTIP_DELAY_MS = 500

class ToolTip:
    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tipwindow: Optional[tk.Toplevel] = None
        self.after_id: Optional[str] = None
        self.widget.bind("<Enter>", self.schedule_showtip)
        self.widget.bind("<Leave>", self.cancel_showtip)

    def schedule_showtip(self, event: Optional[tk.Event] = None) -> None:
        self.after_id = self.widget.after(TOOLTIP_DELAY_MS, self.showtip)

    def cancel_showtip(self, event: Optional[tk.Event] = None) -> None:
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None
        self.hidetip()

    def showtip(self) -> None:
        if self.tipwindow or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 10
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(
            tw,
            text=self.text,
            justify='left',
            background="#ffffe0",
            relief='solid',
            borderwidth=1,
            font=("tahoma", "8", "normal")
        ).pack(ipadx=1)

    def hidetip(self) -> None:
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None
