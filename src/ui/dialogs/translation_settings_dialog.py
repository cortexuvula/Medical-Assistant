"""
Translation Settings Dialog

Dialog for configuring translation provider settings.
"""

import tkinter as tk
import ttkbootstrap as ttk

from settings import settings_manager
from ui.dialogs.dialog_utils import create_toplevel_dialog


def show_translation_settings_dialog(parent: tk.Tk) -> None:
    """Show dialog to configure translation settings."""
    from settings.settings import _DEFAULT_SETTINGS

    # Get current translation settings with fallback to defaults
    translation_settings = settings_manager.get_translation_settings()
    default_settings = _DEFAULT_SETTINGS.get("translation", {})

    dialog = create_toplevel_dialog(parent, "Translation Settings", "600x500")

    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text="Translation Settings",
              font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky="w")

    # Provider selection
    ttk.Label(frame, text="Translation Provider:").grid(row=1, column=0, sticky="w", pady=10)
    provider_var = tk.StringVar(value=translation_settings.get("provider", default_settings.get("provider", "deep_translator")))
    provider_combo = ttk.Combobox(frame, textvariable=provider_var, width=30, state="readonly")
    provider_combo['values'] = ["deep_translator"]
    provider_combo.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=10)

    # Sub-provider selection
    ttk.Label(frame, text="Translation Service:").grid(row=2, column=0, sticky="w", pady=10)
    sub_provider_var = tk.StringVar(value=translation_settings.get("sub_provider", default_settings.get("sub_provider", "google")))
    sub_provider_combo = ttk.Combobox(frame, textvariable=sub_provider_var, width=30, state="readonly")
    sub_provider_combo['values'] = ["google", "deepl", "microsoft"]
    sub_provider_combo.grid(row=2, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Google is free, DeepL and Microsoft require API keys",
              wraplength=400, foreground="gray").grid(row=3, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Default patient language
    ttk.Label(frame, text="Default Patient Language:").grid(row=4, column=0, sticky="w", pady=10)
    patient_lang_var = tk.StringVar(value=translation_settings.get("patient_language", default_settings.get("patient_language", "es")))
    patient_lang_entry = ttk.Entry(frame, textvariable=patient_lang_var, width=32)
    patient_lang_entry.grid(row=4, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Language code (e.g., es, fr, de, zh)",
              wraplength=400, foreground="gray").grid(row=5, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Default doctor language
    ttk.Label(frame, text="Default Doctor Language:").grid(row=6, column=0, sticky="w", pady=10)
    doctor_lang_var = tk.StringVar(value=translation_settings.get("doctor_language", default_settings.get("doctor_language", "en")))
    doctor_lang_entry = ttk.Entry(frame, textvariable=doctor_lang_var, width=32)
    doctor_lang_entry.grid(row=6, column=1, sticky="w", padx=(10, 0), pady=10)

    # Auto-detect checkbox
    auto_detect_var = tk.BooleanVar(value=translation_settings.get("auto_detect", default_settings.get("auto_detect", True)))
    ttk.Checkbutton(frame, text="Auto-detect patient language",
                    variable=auto_detect_var).grid(row=7, column=0, columnspan=2, sticky="w", pady=(20, 10))

    # Button frame
    button_frame = ttk.Frame(dialog)
    button_frame.pack(fill=tk.X, pady=(0, 20))

    def save_translation_settings():
        settings_manager.set_translation_settings({
            "provider": provider_var.get(),
            "sub_provider": sub_provider_var.get(),
            "patient_language": patient_lang_var.get(),
            "doctor_language": doctor_lang_var.get(),
            "auto_detect": auto_detect_var.get()
        })
        dialog.destroy()

    ttk.Button(button_frame, text="Save", command=save_translation_settings).pack(side=tk.RIGHT, padx=(0, 20))
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)


__all__ = ["show_translation_settings_dialog"]
