"""
API Keys Dialog Module

Deprecated: This module now delegates to the unified settings dialog.
Use show_unified_settings_dialog(parent, initial_tab="API Keys") directly instead.
"""

import tkinter as tk

from ui.dialogs.unified_settings_dialog import show_unified_settings_dialog


def show_api_keys_dialog(parent: tk.Tk) -> dict:
    """Shows a dialog to update API keys via the unified settings dialog.

    This function is a backward-compatible wrapper. It opens the unified
    settings dialog focused on the API Keys tab.

    Returns:
        dict: A truthy dict {"saved": True} if saved, or None if cancelled
    """
    saved = show_unified_settings_dialog(parent, initial_tab="API Keys")
    if saved:
        return {"saved": True}
    return None


__all__ = ["show_api_keys_dialog"]
