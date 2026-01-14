"""
Template Selection Dialog

Dialog for selecting an agent template from available templates.
"""

import tkinter as tk
from tkinter import messagebox, ttk as tk_ttk
from ui.scaling_utils import ui_scaler
import ttkbootstrap as ttk
from typing import Optional, List

from ai.agents.models import AgentTemplate


class TemplateSelectionDialog:
    """Dialog for selecting an agent template."""

    def __init__(self, parent, templates: List[AgentTemplate]):
        self.parent = parent
        self.templates = templates
        self.selected_template = None

    def show(self) -> Optional[AgentTemplate]:
        """Show the dialog and return selected template."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Select Template")
        dialog_width, dialog_height = ui_scaler.get_dialog_size(600, 400)
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
        frame = ttk.Frame(self.dialog, padding=10)
        frame.pack(fill="both", expand=True)

        # Template list
        columns = ("name", "category", "description")
        self.tree = tk_ttk.Treeview(frame, columns=columns, show="tree headings", height=12)

        self.tree.heading("name", text="Name")
        self.tree.column("name", width=150)
        self.tree.heading("category", text="Category")
        self.tree.column("category", width=100)
        self.tree.heading("description", text="Description")
        self.tree.column("description", width=300)

        # Add templates
        for template in self.templates:
            self.tree.insert("", "end", values=(
                template.name,
                template.category,
                template.description
            ), tags=(template,))

        self.tree.pack(fill="both", expand=True)

        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill="x", pady=(10, 0))

        ttk.Button(
            button_frame,
            text="Load Template",
            command=self._load_clicked
        ).pack(side="right", padx=(5, 0))

        ttk.Button(
            button_frame,
            text="Cancel",
            command=self.dialog.destroy
        ).pack(side="right")

        self.dialog.wait_window()
        return self.selected_template

    def _load_clicked(self):
        """Handle load button click."""
        selection = self.tree.selection()
        if selection:
            tags = self.tree.item(selection[0], "tags")
            if tags:
                self.selected_template = tags[0]
                self.dialog.destroy()
        else:
            messagebox.showwarning("No Selection", "Please select a template.")


__all__ = ["TemplateSelectionDialog"]
