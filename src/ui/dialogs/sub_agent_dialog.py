"""
Sub-Agent Configuration Dialog

Dialog for configuring sub-agent settings within an agent chain.
"""

import tkinter as tk
from tkinter import messagebox
from ui.scaling_utils import ui_scaler
import ttkbootstrap as ttk
from typing import Optional

from ai.agents.models import AgentType


class SubAgentDialog:
    """Dialog for configuring a sub-agent."""

    def __init__(self, parent, sub_agent: Optional[dict] = None):
        self.parent = parent
        self.sub_agent = sub_agent
        self.result = None

    def show(self) -> Optional[dict]:
        """Show the dialog and return the result."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Configure Sub-Agent")
        dialog_width, dialog_height = ui_scaler.get_dialog_size(400, 350)
        self.dialog.geometry(f"{dialog_width}x{dialog_height}")
        self.dialog.transient(self.parent)

        # Create UI
        frame = ttk.Frame(self.dialog, padding=20)
        frame.pack(fill="both", expand=True)

        # Agent Type
        ttk.Label(frame, text="Agent Type:").grid(row=0, column=0, sticky="w", pady=5)

        self.agent_type_var = tk.StringVar(
            value=self.sub_agent.get("agent_type", "") if self.sub_agent else ""
        )
        agent_type_combo = ttk.Combobox(
            frame,
            textvariable=self.agent_type_var,
            values=[t.value for t in AgentType],
            state="readonly",
            width=25
        )
        agent_type_combo.grid(row=0, column=1, sticky="w", pady=5)

        # Output Key
        ttk.Label(frame, text="Output Key:").grid(row=1, column=0, sticky="w", pady=5)

        self.output_key_var = tk.StringVar(
            value=self.sub_agent.get("output_key", "") if self.sub_agent else ""
        )
        output_entry = ttk.Entry(frame, textvariable=self.output_key_var, width=27)
        output_entry.grid(row=1, column=1, sticky="w", pady=5)

        # Priority
        ttk.Label(frame, text="Priority:").grid(row=2, column=0, sticky="w", pady=5)

        self.priority_var = tk.IntVar(
            value=self.sub_agent.get("priority", 0) if self.sub_agent else 0
        )
        priority_spin = ttk.Spinbox(
            frame,
            from_=0,
            to=100,
            textvariable=self.priority_var,
            width=10
        )
        priority_spin.grid(row=2, column=1, sticky="w", pady=5)

        # Checkboxes
        self.enabled_var = tk.BooleanVar(
            value=self.sub_agent.get("enabled", True) if self.sub_agent else True
        )
        ttk.Checkbutton(
            frame,
            text="Enabled",
            variable=self.enabled_var
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=5)

        self.required_var = tk.BooleanVar(
            value=self.sub_agent.get("required", False) if self.sub_agent else False
        )
        ttk.Checkbutton(
            frame,
            text="Required (must succeed)",
            variable=self.required_var
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=5)

        self.pass_context_var = tk.BooleanVar(
            value=self.sub_agent.get("pass_context", True) if self.sub_agent else True
        )
        ttk.Checkbutton(
            frame,
            text="Pass parent context",
            variable=self.pass_context_var
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=5)

        # Condition
        ttk.Label(frame, text="Condition (optional):").grid(row=6, column=0, sticky="nw", pady=5)

        self.condition_text = tk.Text(frame, height=3, width=30)
        self.condition_text.grid(row=6, column=1, sticky="w", pady=5)
        if self.sub_agent and self.sub_agent.get("condition"):
            self.condition_text.insert("1.0", self.sub_agent["condition"])

        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=7, column=0, columnspan=2, pady=20)

        ttk.Button(
            button_frame,
            text="OK",
            command=self._ok_clicked
        ).pack(side="left", padx=5)

        ttk.Button(
            button_frame,
            text="Cancel",
            command=self.dialog.destroy
        ).pack(side="left", padx=5)

        # Center dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - self.dialog.winfo_width()) // 2
        y = (self.dialog.winfo_screenheight() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")

        # Grab focus after window is visible
        self.dialog.deiconify()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass  # Window not viewable yet

        self.dialog.wait_window()
        return self.result

    def _ok_clicked(self):
        """Handle OK button click."""
        if not self.agent_type_var.get():
            messagebox.showerror("Error", "Please select an agent type.")
            return

        if not self.output_key_var.get():
            messagebox.showerror("Error", "Please enter an output key.")
            return

        self.result = {
            "agent_type": self.agent_type_var.get(),
            "output_key": self.output_key_var.get(),
            "priority": self.priority_var.get(),
            "enabled": self.enabled_var.get(),
            "required": self.required_var.get(),
            "pass_context": self.pass_context_var.get(),
            "condition": self.condition_text.get("1.0", "end-1c").strip() or None
        }

        self.dialog.destroy()


__all__ = ["SubAgentDialog"]
