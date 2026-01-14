"""
Save Template Dialog

Dialog for saving agent configuration as a template.
"""

import tkinter as tk
from tkinter import messagebox
from ui.scaling_utils import ui_scaler
import ttkbootstrap as ttk
from typing import Optional


class SaveTemplateDialog:
    """Dialog for saving configuration as template."""

    def __init__(self, parent):
        self.parent = parent
        self.result = None

    def show(self) -> Optional[dict]:
        """Show the dialog and return template info."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Save as Template")
        dialog_width, dialog_height = ui_scaler.get_dialog_size(400, 300)
        self.dialog.geometry(f"{dialog_width}x{dialog_height}")
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - dialog_width) // 2
        y = (self.dialog.winfo_screenheight() - dialog_height) // 2
        self.dialog.geometry(f"+{x}+{y}")

        # Grab focus after window is visible
        self.dialog.deiconify()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass  # Window not viewable yet

        # Create UI
        frame = ttk.Frame(self.dialog, padding=20)
        frame.pack(fill="both", expand=True)

        # Template ID
        ttk.Label(frame, text="Template ID:").grid(row=0, column=0, sticky="w", pady=5)
        self.id_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.id_var, width=30).grid(row=0, column=1, pady=5)

        # Name
        ttk.Label(frame, text="Name:").grid(row=1, column=0, sticky="w", pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.name_var, width=30).grid(row=1, column=1, pady=5)

        # Category
        ttk.Label(frame, text="Category:").grid(row=2, column=0, sticky="w", pady=5)
        self.category_var = tk.StringVar()
        category_combo = ttk.Combobox(
            frame,
            textvariable=self.category_var,
            values=["Medical", "General", "Custom"],
            width=27
        )
        category_combo.grid(row=2, column=1, pady=5)

        # Description
        ttk.Label(frame, text="Description:").grid(row=3, column=0, sticky="nw", pady=5)
        self.desc_text = tk.Text(frame, height=4, width=30)
        self.desc_text.grid(row=3, column=1, pady=5)

        # Tags
        ttk.Label(frame, text="Tags (comma-separated):").grid(row=4, column=0, sticky="w", pady=5)
        self.tags_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.tags_var, width=30).grid(row=4, column=1, pady=5)

        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)

        ttk.Button(
            button_frame,
            text="Save",
            command=self._save_clicked
        ).pack(side="left", padx=5)

        ttk.Button(
            button_frame,
            text="Cancel",
            command=self.dialog.destroy
        ).pack(side="left", padx=5)

        self.dialog.wait_window()
        return self.result

    def _save_clicked(self):
        """Handle save button click."""
        if not all([self.id_var.get(), self.name_var.get(), self.category_var.get()]):
            messagebox.showerror("Error", "Please fill in all required fields.")
            return

        self.result = {
            "id": self.id_var.get(),
            "name": self.name_var.get(),
            "category": self.category_var.get(),
            "description": self.desc_text.get("1.0", "end-1c"),
            "tags": [t.strip() for t in self.tags_var.get().split(",") if t.strip()]
        }

        self.dialog.destroy()


__all__ = ["SaveTemplateDialog"]
