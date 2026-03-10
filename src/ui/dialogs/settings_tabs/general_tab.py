"""
General tab mixin for UnifiedSettingsDialog.

Provides the _create_general_tab method.
"""

from __future__ import annotations

import tkinter as tk
import ttkbootstrap as ttk

from ui.tooltip import ToolTip
from settings.settings_manager import settings_manager
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class GeneralTabMixin:
    """Mixin providing the General tab for UnifiedSettingsDialog.

    Expects the host class to provide:
        - self.notebook: ttk.Notebook
        - self.widgets: Dict[str, Dict]
    """

    def _create_general_tab(self):
        """Create General tab content."""
        tab = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(tab, text=self.TAB_GENERAL)

        self.widgets['general'] = {}
        row = 0

        # General Settings header
        ttk.Label(tab, text="General Settings",
                 font=("Segoe UI", 12, "bold")).grid(row=row, column=0, columnspan=2,
                                                      sticky="w", pady=(0, 15))
        row += 1

        # Quick Continue Mode
        qc_label = ttk.Label(tab, text="Quick Continue Mode:")
        qc_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(qc_label, "Enable to start new recordings while previous ones process")
        quick_continue_var = tk.BooleanVar(value=settings_manager.get("quick_continue_mode", False))
        self.widgets['general']['quick_continue_mode'] = quick_continue_var
        qc_check = ttk.Checkbutton(tab, variable=quick_continue_var)
        qc_check.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)
        ToolTip(qc_check, "Queue recordings for background processing while starting new ones")
        ttk.Label(tab, text="Queue recordings for background processing while starting new ones",
                 foreground="gray").grid(row=row+1, column=0, columnspan=2, sticky="w", padx=(20, 0))
        row += 2

        # Theme
        theme_label = ttk.Label(tab, text="Theme:")
        theme_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(theme_label, "Application color theme")
        theme_var = tk.StringVar(value=settings_manager.get("theme", "darkly"))
        self.widgets['general']['theme'] = theme_var
        theme_combo = ttk.Combobox(tab, textvariable=theme_var, width=20,
                                   values=["darkly", "solar", "cyborg", "superhero", "vapor",
                                          "flatly", "litera", "minty", "pulse", "sandstone"])
        theme_combo.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)
        ToolTip(theme_combo, "Dark themes: darkly, solar, cyborg, superhero; Light themes: flatly, litera, minty, pulse")
        row += 1

        # Sidebar collapsed
        sidebar_label = ttk.Label(tab, text="Sidebar Collapsed:")
        sidebar_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(sidebar_label, "Start with sidebar collapsed")
        sidebar_var = tk.BooleanVar(value=settings_manager.get("sidebar_collapsed", False))
        self.widgets['general']['sidebar_collapsed'] = sidebar_var
        sidebar_check = ttk.Checkbutton(tab, variable=sidebar_var)
        sidebar_check.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)
        ToolTip(sidebar_check, "Start with navigation sidebar collapsed (can toggle with button)")
        row += 1

        # Separator
        ttk.Separator(tab, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=20)
        row += 1

        # Keyboard shortcuts info
        ttk.Label(tab, text="Keyboard Shortcuts",
                 font=("Segoe UI", 12, "bold")).grid(row=row, column=0, columnspan=2,
                                                      sticky="w", pady=(0, 10))
        row += 1

        shortcuts = [
            ("Ctrl+,", "Open Preferences"),
            ("Alt+T", "Toggle Theme"),
            ("Ctrl+N", "New Session"),
            ("Ctrl+S", "Save"),
            ("F5", "Start/Stop Recording"),
            ("Ctrl+/", "Focus Chat Input"),
        ]

        for key, desc in shortcuts:
            shortcut_frame = ttk.Frame(tab)
            shortcut_frame.grid(row=row, column=0, columnspan=2, sticky="w", pady=2)
            ttk.Label(shortcut_frame, text=key, font=("Consolas", 10), width=10).pack(side="left")
            ttk.Label(shortcut_frame, text=desc, foreground="gray").pack(side="left", padx=(10, 0))
            row += 1

        tab.columnconfigure(1, weight=1)
