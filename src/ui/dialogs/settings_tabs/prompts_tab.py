"""
Prompts tab mixin for UnifiedSettingsDialog.

Provides the _create_prompts_tab method.
"""

from __future__ import annotations

import ttkbootstrap as ttk

from ui.tooltip import ToolTip
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class PromptsTabMixin:
    """Mixin providing the Prompts tab for UnifiedSettingsDialog.

    Expects the host class to provide:
        - self.notebook: ttk.Notebook
        - self.dialog: tk.Toplevel
        - self.parent: Parent window
    """

    def _create_prompts_tab(self):
        """Create Prompts tab with edit buttons."""
        tab = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(tab, text=self.TAB_PROMPTS)

        ttk.Label(tab, text="Prompt Configuration",
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 15))

        ttk.Label(tab, text="Click 'Edit' to open the full prompt editor for each category:",
                 foreground="gray").pack(anchor="w", pady=(0, 15))

        # Create list of prompts with edit buttons
        prompts_config = [
            ("Refine Text Prompt", "show_refine_settings", "Edit prompt for refining/cleaning transcribed text"),
            ("Improve Text Prompt", "show_improve_settings", "Edit prompt for improving text quality and clarity"),
            ("SOAP Note Prompt", "show_soap_settings", "Edit prompt for generating SOAP clinical notes"),
            ("Referral Prompt", "show_referral_settings", "Edit prompt for generating referral letters"),
            ("Advanced Analysis Prompt", "show_advanced_analysis_settings", "Edit prompt for periodic differential diagnosis"),
        ]

        for label, method_name, tooltip_text in prompts_config:
            row_frame = ttk.Frame(tab)
            row_frame.pack(fill="x", pady=5)

            prompt_label = ttk.Label(row_frame, text=label, width=30)
            prompt_label.pack(side="left")
            ToolTip(prompt_label, tooltip_text)

            # Create edit button that calls parent method
            def make_callback(m=method_name):
                def callback():
                    if hasattr(self.parent, m):
                        self.dialog.destroy()
                        getattr(self.parent, m)()
                return callback

            edit_btn = ttk.Button(row_frame, text="Edit...", width=10, command=make_callback())
            edit_btn.pack(side="right", padx=5)
            ToolTip(edit_btn, f"Open {label.lower()} editor")
