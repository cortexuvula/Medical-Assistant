"""
Save Template Dialog

Dialog for saving agent configuration as a template.
"""

import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from typing import Optional

from ui.dialogs.base_dialog import BaseDialog


class SaveTemplateDialog(BaseDialog):
    """Dialog for saving configuration as template."""

    def __init__(self, parent):
        super().__init__(parent, modal=True)

    def _get_title(self):
        return "Save as Template"

    def _get_size(self):
        return (400, 300)

    def _get_padding(self):
        return 20

    def _create_content(self, parent_frame):
        """Build the template form."""
        frame = parent_frame

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
            command=self.close
        ).pack(side="left", padx=5)

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

        self.close()


__all__ = ["SaveTemplateDialog"]
