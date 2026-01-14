"""
Groq Settings Dialog

Dialog for configuring Groq speech-to-text settings.
"""

import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk

from settings import settings_manager
from ui.dialogs.dialog_utils import create_toplevel_dialog


def show_groq_settings_dialog(parent: tk.Tk) -> None:
    """Show dialog to configure Groq speech-to-text settings."""
    from settings.settings import _DEFAULT_SETTINGS

    # Get current Groq settings with fallback to defaults
    groq_settings = settings_manager.get_groq_settings()
    default_settings = _DEFAULT_SETTINGS.get("groq", {
        "model": "whisper-large-v3-turbo",
        "language": "en",
        "prompt": ""
    })

    dialog = create_toplevel_dialog(parent, "Groq Settings", "550x580")

    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)
    frame.columnconfigure(1, weight=1)

    ttk.Label(frame, text="Groq Speech-to-Text Settings",
              font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky="w")

    # Model selection
    ttk.Label(frame, text="Model:").grid(row=1, column=0, sticky="w", pady=5)
    model_var = tk.StringVar(value=groq_settings.get("model", default_settings.get("model", "whisper-large-v3-turbo")))
    model_combo = ttk.Combobox(frame, textvariable=model_var, width=35, state="readonly")
    model_combo['values'] = [
        "whisper-large-v3-turbo",
        "whisper-large-v3",
        "distil-whisper-large-v3-en"
    ]
    model_combo.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=5)
    ttk.Label(frame, text="whisper-large-v3-turbo: fastest (216x real-time), whisper-large-v3: higher quality",
              wraplength=450, foreground="gray").grid(row=2, column=0, columnspan=2, sticky="w", padx=(20, 0), pady=(0, 10))

    # Language
    ttk.Label(frame, text="Language:").grid(row=3, column=0, sticky="w", pady=5)
    language_var = tk.StringVar(value=groq_settings.get("language", default_settings.get("language", "en")))
    language_combo = ttk.Combobox(frame, textvariable=language_var, width=35)
    language_combo['values'] = [
        "en", "es", "fr", "de", "it", "pt", "nl", "pl", "ru",
        "ja", "ko", "zh", "ar", "hi", "tr", "vi", "th"
    ]
    language_combo.grid(row=3, column=1, sticky="ew", padx=(10, 0), pady=5)
    ttk.Label(frame, text="ISO-639-1 language code. Setting this improves accuracy and latency.",
              wraplength=450, foreground="gray").grid(row=4, column=0, columnspan=2, sticky="w", padx=(20, 0), pady=(0, 10))

    # Prompt
    ttk.Label(frame, text="Prompt:").grid(row=5, column=0, sticky="nw", pady=5)
    prompt_text = tk.Text(frame, width=45, height=8, wrap=tk.WORD)
    prompt_text.insert("1.0", groq_settings.get("prompt", default_settings.get("prompt", "")))
    prompt_text.grid(row=5, column=1, sticky="ew", padx=(10, 0), pady=5)
    ttk.Label(frame, text="Optional context or spelling hints (max 224 tokens). Example: medical terminology, names.",
              wraplength=450, foreground="gray").grid(row=6, column=0, columnspan=2, sticky="w", padx=(20, 0), pady=(0, 10))

    # Buttons
    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=7, column=0, columnspan=2, pady=(20, 0), sticky="e")

    def save_groq_settings():
        prompt = prompt_text.get("1.0", tk.END).strip()

        new_settings = {
            "model": model_var.get(),
            "language": language_var.get(),
            "prompt": prompt
        }

        settings_manager.set_groq_settings(new_settings)
        messagebox.showinfo("Settings Saved", "Groq settings saved successfully")
        dialog.destroy()

    def cancel():
        dialog.destroy()

    ttk.Button(btn_frame, text="Cancel", command=cancel, width=10).pack(side="left", padx=5)
    ttk.Button(btn_frame, text="Save", command=save_groq_settings, bootstyle="success", width=10).pack(side="left", padx=5)


__all__ = ["show_groq_settings_dialog"]
