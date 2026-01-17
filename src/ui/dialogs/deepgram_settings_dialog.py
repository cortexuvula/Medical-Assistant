"""
Deepgram Settings Dialog

Dialog for configuring Deepgram speech-to-text settings.
"""

import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk

from settings import settings_manager
from ui.dialogs.dialog_utils import create_toplevel_dialog


def show_deepgram_settings_dialog(parent: tk.Tk) -> None:
    """Show dialog to configure Deepgram speech-to-text settings."""
    # Get current Deepgram settings with fallback to defaults
    deepgram_settings = settings_manager.get_deepgram_settings()
    default_settings = settings_manager.get_default("deepgram", {})

    dialog = create_toplevel_dialog(parent, "Deepgram Settings", "700x900")

    # Use scrollable canvas
    canvas = tk.Canvas(dialog)
    scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda _: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
    scrollbar.pack(side="right", fill="y", pady=10)

    frame = ttk.Frame(scrollable_frame, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text="Deepgram Speech-to-Text Settings",
              font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky="w")

    # Model selection
    ttk.Label(frame, text="Model:").grid(row=1, column=0, sticky="w", pady=10)
    model_var = tk.StringVar(value=deepgram_settings.get("model", default_settings.get("model", "nova-2-medical")))
    model_combo = ttk.Combobox(frame, textvariable=model_var, width=30)
    model_combo['values'] = ["nova-2-medical", "nova-2", "enhanced", "base"]
    model_combo.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="The AI model to use for transcription. 'nova-2-medical' is optimized for medical terminology.",
              wraplength=400, foreground="gray").grid(row=2, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Language
    ttk.Label(frame, text="Language:").grid(row=3, column=0, sticky="w", pady=10)
    language_var = tk.StringVar(value=deepgram_settings.get("language", default_settings.get("language", "en-US")))
    language_entry = ttk.Combobox(frame, textvariable=language_var, width=30)
    language_entry['values'] = [
        "en-US", "en-GB", "en-AU", "en-NZ", "en-IN",
        "fr-FR", "de-DE", "es-ES", "it-IT", "ja-JP",
        "ko-KR", "pt-BR", "zh-CN"
    ]
    language_entry.grid(row=3, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Language code for speech recognition.",
              wraplength=400, foreground="gray").grid(row=4, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Smart formatting
    ttk.Label(frame, text="Smart Formatting:").grid(row=5, column=0, sticky="w", pady=10)
    smart_format_var = tk.BooleanVar(value=deepgram_settings.get("smart_format", default_settings.get("smart_format", True)))
    smart_format_check = ttk.Checkbutton(frame, variable=smart_format_var)
    smart_format_check.grid(row=5, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Adds punctuation and capitalization to transcriptions.",
              wraplength=400, foreground="gray").grid(row=6, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Diarization
    ttk.Label(frame, text="Speaker Diarization:").grid(row=7, column=0, sticky="w", pady=10)
    diarize_var = tk.BooleanVar(value=deepgram_settings.get("diarize", default_settings.get("diarize", False)))
    diarize_check = ttk.Checkbutton(frame, variable=diarize_var)
    diarize_check.grid(row=7, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Identify and label different speakers in the audio.",
              wraplength=400, foreground="gray").grid(row=8, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Profanity filter
    ttk.Label(frame, text="Filter Profanity:").grid(row=9, column=0, sticky="w", pady=10)
    profanity_var = tk.BooleanVar(value=deepgram_settings.get("profanity_filter", default_settings.get("profanity_filter", False)))
    profanity_check = ttk.Checkbutton(frame, variable=profanity_var)
    profanity_check.grid(row=9, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Replaces profanity with asterisks.",
              wraplength=400, foreground="gray").grid(row=10, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Redact PII
    ttk.Label(frame, text="Redact PII:").grid(row=11, column=0, sticky="w", pady=10)
    redact_var = tk.BooleanVar(value=deepgram_settings.get("redact", default_settings.get("redact", False)))
    redact_check = ttk.Checkbutton(frame, variable=redact_var)
    redact_check.grid(row=11, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Redact personally identifiable information like names, addresses, etc.",
              wraplength=400, foreground="gray").grid(row=12, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Alternatives
    ttk.Label(frame, text="Alternatives:").grid(row=13, column=0, sticky="w", pady=10)
    alternatives_var = tk.StringVar(value=str(deepgram_settings.get("alternatives", default_settings.get("alternatives", 1))))
    alternatives_spin = ttk.Spinbox(frame, from_=1, to=5, width=5, textvariable=alternatives_var)
    alternatives_spin.grid(row=13, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Number of alternative transcriptions to generate.",
              wraplength=400, foreground="gray").grid(row=14, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Buttons
    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=15, column=0, columnspan=2, pady=(20, 0), sticky="e")

    def save_deepgram_settings():
        try:
            alternatives = int(alternatives_var.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Number of alternatives must be a valid integer.")
            return

        new_settings = {
            "model": model_var.get(),
            "language": language_var.get(),
            "smart_format": smart_format_var.get(),
            "diarize": diarize_var.get(),
            "profanity_filter": profanity_var.get(),
            "redact": redact_var.get(),
            "alternatives": alternatives
        }

        settings_manager.set_deepgram_settings(new_settings)
        messagebox.showinfo("Settings Saved", "Deepgram settings saved successfully")
        dialog.destroy()

    def cancel():
        dialog.destroy()

    ttk.Button(btn_frame, text="Cancel", command=cancel, width=10).pack(side="left", padx=5)
    ttk.Button(btn_frame, text="Save", command=save_deepgram_settings, bootstyle="success", width=10).pack(side="left", padx=5)

    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def on_close():
        canvas.unbind_all("<MouseWheel>")
        dialog.destroy()

    dialog.protocol("WM_DELETE_WINDOW", on_close)


__all__ = ["show_deepgram_settings_dialog"]
