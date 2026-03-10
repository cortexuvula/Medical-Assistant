"""
Storage tab mixin for UnifiedSettingsDialog.

Provides the _create_storage_tab method.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog
import ttkbootstrap as ttk

from ui.tooltip import ToolTip
from settings.settings_manager import settings_manager
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class StorageTabMixin:
    """Mixin providing the Storage tab for UnifiedSettingsDialog.

    Expects the host class to provide:
        - self.notebook: ttk.Notebook
        - self.widgets: Dict[str, Dict]
        - self.dialog: tk.Toplevel
        - self.parent: Parent window
    """

    def _create_storage_tab(self):
        """Create Storage tab content."""
        tab = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(tab, text=self.TAB_STORAGE)

        self.widgets['storage'] = {}
        row = 0

        # Storage folder
        ttk.Label(tab, text="Storage Settings",
                 font=("Segoe UI", 12, "bold")).grid(row=row, column=0, columnspan=3,
                                                      sticky="w", pady=(0, 15))
        row += 1

        folder_label = ttk.Label(tab, text="Default Storage Folder:")
        folder_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(folder_label, "Default folder for saving documents")
        # Read storage_folder (used by audio save), fall back to default_folder for compat
        _storage_path = settings_manager.get("storage_folder", "") or settings_manager.get("default_folder", "")
        folder_var = tk.StringVar(value=_storage_path)
        self.widgets['storage']['default_folder'] = folder_var
        folder_entry = ttk.Entry(tab, textvariable=folder_var, width=50)
        folder_entry.grid(row=row, column=1, sticky="ew", padx=(10, 5), pady=10)
        ToolTip(folder_entry, "Path where documents will be saved by default")

        def browse_folder():
            folder = filedialog.askdirectory(initialdir=folder_var.get())
            if folder:
                folder_var.set(folder)

        browse_btn = ttk.Button(tab, text="Browse...", command=browse_folder)
        browse_btn.grid(row=row, column=2, padx=5, pady=10)
        ToolTip(browse_btn, "Browse to select a folder")
        row += 1

        # Separator
        ttk.Separator(tab, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=20)
        row += 1

        # Quick links section
        ttk.Label(tab, text="Quick Links",
                 font=("Segoe UI", 12, "bold")).grid(row=row, column=0, columnspan=3,
                                                      sticky="w", pady=(0, 15))
        row += 1

        links = [
            ("Custom Vocabulary...", "show_vocabulary_settings", "Manage custom word corrections and medical terminology"),
            ("Manage Address Book...", "manage_address_book", "Manage provider and facility contact information"),
            ("Record Prefix Audio...", "record_prefix_audio", "Record an audio prefix to be added to all recordings"),
        ]

        for label, method_name, tooltip_text in links:
            def make_callback(m=method_name):
                def callback():
                    if hasattr(self.parent, m):
                        self.dialog.destroy()
                        getattr(self.parent, m)()
                return callback

            btn = ttk.Button(tab, text=label, width=30, command=make_callback())
            btn.grid(row=row, column=0, columnspan=2, sticky="w", pady=5)
            ToolTip(btn, tooltip_text)
            row += 1

        tab.columnconfigure(1, weight=1)
