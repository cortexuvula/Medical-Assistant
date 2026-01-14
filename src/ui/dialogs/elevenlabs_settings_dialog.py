"""
ElevenLabs Settings Dialog

Dialog for configuring ElevenLabs speech-to-text settings.
"""

import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk

from settings import settings_manager
from ui.dialogs.dialog_utils import create_toplevel_dialog


def show_elevenlabs_settings_dialog(parent: tk.Tk) -> None:
    """Show dialog to configure ElevenLabs speech-to-text settings."""
    from settings.settings import _DEFAULT_SETTINGS

    # Get current ElevenLabs settings with fallback to defaults
    elevenlabs_settings = settings_manager.get_elevenlabs_settings()
    default_settings = _DEFAULT_SETTINGS.get("elevenlabs", {})

    dialog = create_toplevel_dialog(parent, "ElevenLabs Settings", "700x700")

    # Use scrollable canvas to ensure all content is accessible regardless of screen size
    canvas = tk.Canvas(dialog)
    scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    # Configure scrolling
    scrollable_frame.bind(
        "<Configure>",
        lambda _: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    # Pack the canvas and scrollbar
    canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
    scrollbar.pack(side="right", fill="y", pady=10)

    # Create the main frame with padding inside the scrollable frame
    frame = ttk.Frame(scrollable_frame, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)

    # Create form with current settings
    ttk.Label(frame, text="ElevenLabs Speech-to-Text Settings",
              font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky="w")

    # Model ID
    ttk.Label(frame, text="Model ID:").grid(row=1, column=0, sticky="w", pady=10)
    model_var = tk.StringVar(value=elevenlabs_settings.get("model_id", default_settings.get("model_id", "scribe_v2")))
    model_combo = ttk.Combobox(frame, textvariable=model_var, width=30)
    model_combo['values'] = ["scribe_v2", "scribe_v1", "scribe_v1_experimental"]
    model_combo.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="scribe_v2: 90+ languages, up to 48 speakers, entity detection, keyterm prompting",
              wraplength=400, foreground="gray").grid(row=2, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Language Code
    ttk.Label(frame, text="Language Code:").grid(row=3, column=0, sticky="w", pady=10)
    lang_var = tk.StringVar(value=elevenlabs_settings.get("language_code", default_settings.get("language_code", "")))
    lang_entry = ttk.Entry(frame, textvariable=lang_var, width=30)
    lang_entry.grid(row=3, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Optional ISO language code (e.g., 'en-US'). Leave empty for auto-detection.",
              wraplength=400, foreground="gray").grid(row=4, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Tag Audio Events
    ttk.Label(frame, text="Tag Audio Events:").grid(row=5, column=0, sticky="w", pady=10)
    tag_events_var = tk.BooleanVar(value=elevenlabs_settings.get("tag_audio_events", default_settings.get("tag_audio_events", True)))
    tag_events_check = ttk.Checkbutton(frame, variable=tag_events_var)
    tag_events_check.grid(row=5, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Add timestamps and labels for audio events like silence, music, etc.",
              wraplength=400, foreground="gray").grid(row=6, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Number of Speakers
    ttk.Label(frame, text="Number of Speakers:").grid(row=7, column=0, sticky="w", pady=10)

    speakers_value = elevenlabs_settings.get("num_speakers", default_settings.get("num_speakers", None))
    speakers_str = "" if speakers_value is None else str(speakers_value)
    speakers_entry = ttk.Entry(frame, width=30)
    speakers_entry.insert(0, speakers_str)
    speakers_entry.grid(row=7, column=1, sticky="w", padx=(10, 0), pady=10)

    ttk.Label(frame, text="Optional number of speakers (up to 48). Leave empty for auto-detection.",
              wraplength=400, foreground="gray").grid(row=8, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Timestamps Granularity
    ttk.Label(frame, text="Timestamps Granularity:").grid(row=9, column=0, sticky="w", pady=10)
    granularity_var = tk.StringVar(value=elevenlabs_settings.get("timestamps_granularity", default_settings.get("timestamps_granularity", "word")))
    granularity_combo = ttk.Combobox(frame, textvariable=granularity_var, width=30)
    granularity_combo['values'] = ["none", "word", "character"]
    granularity_combo.grid(row=9, column=1, sticky="w", padx=(10, 0), pady=10)

    # Diarize
    ttk.Label(frame, text="Diarize:").grid(row=10, column=0, sticky="w", pady=10)
    diarize_var = tk.BooleanVar(value=elevenlabs_settings.get("diarize", default_settings.get("diarize", True)))
    diarize_check = ttk.Checkbutton(frame, variable=diarize_var)
    diarize_check.grid(row=10, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Identify different speakers in the audio.",
              wraplength=400, foreground="gray").grid(row=11, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Temperature
    ttk.Label(frame, text="Temperature:").grid(row=12, column=0, sticky="w", pady=10)
    temp_value = elevenlabs_settings.get("temperature", default_settings.get("temperature", None))
    temp_str = "" if temp_value is None else str(temp_value)
    temp_entry = ttk.Entry(frame, width=30)
    temp_entry.insert(0, temp_str)
    temp_entry.grid(row=12, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Optional. 0.0=deterministic, 2.0=creative. Leave empty for default.",
              wraplength=400, foreground="gray").grid(row=13, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Diarization Threshold
    ttk.Label(frame, text="Diarization Threshold:").grid(row=14, column=0, sticky="w", pady=10)
    diar_thresh_value = elevenlabs_settings.get("diarization_threshold", default_settings.get("diarization_threshold", None))
    diar_thresh_str = "" if diar_thresh_value is None else str(diar_thresh_value)
    diar_thresh_entry = ttk.Entry(frame, width=30)
    diar_thresh_entry.insert(0, diar_thresh_str)
    diar_thresh_entry.grid(row=14, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Optional. Confidence threshold for speaker detection (0.0-2.0).",
              wraplength=400, foreground="gray").grid(row=15, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Entity Detection
    ttk.Label(frame, text="Entity Detection:", font=("Segoe UI", 10, "bold")).grid(
        row=16, column=0, columnspan=2, sticky="w", pady=(15, 5))
    ttk.Label(frame, text="Detect sensitive entities in transcription (scribe_v2 only)",
              wraplength=400, foreground="gray").grid(row=17, column=0, columnspan=2, sticky="w", padx=(20, 0))

    current_entities = elevenlabs_settings.get("entity_detection", default_settings.get("entity_detection", []))

    entity_frame = ttk.Frame(frame)
    entity_frame.grid(row=18, column=0, columnspan=2, sticky="w", pady=5, padx=(20, 0))

    phi_var = tk.BooleanVar(value="phi" in current_entities)
    pii_var = tk.BooleanVar(value="pii" in current_entities)
    pci_var = tk.BooleanVar(value="pci" in current_entities)
    offensive_var = tk.BooleanVar(value="offensive" in current_entities)

    ttk.Checkbutton(entity_frame, text="PHI (Protected Health Info)", variable=phi_var).grid(row=0, column=0, sticky="w", padx=(0, 15))
    ttk.Checkbutton(entity_frame, text="PII (Personal Info)", variable=pii_var).grid(row=0, column=1, sticky="w", padx=(0, 15))
    ttk.Checkbutton(entity_frame, text="PCI (Payment Info)", variable=pci_var).grid(row=1, column=0, sticky="w", padx=(0, 15), pady=(5, 0))
    ttk.Checkbutton(entity_frame, text="Offensive Language", variable=offensive_var).grid(row=1, column=1, sticky="w", pady=(5, 0))

    # Keyterms
    ttk.Label(frame, text="Keyterms:", font=("Segoe UI", 10, "bold")).grid(
        row=19, column=0, columnspan=2, sticky="w", pady=(15, 5))
    ttk.Label(frame, text="Medical terms to bias recognition (comma-separated, up to 100 terms)",
              wraplength=400, foreground="gray").grid(row=20, column=0, columnspan=2, sticky="w", padx=(20, 0))

    current_keyterms = elevenlabs_settings.get("keyterms", default_settings.get("keyterms", []))
    keyterms_text = tk.Text(frame, width=50, height=3, wrap=tk.WORD)
    keyterms_text.insert("1.0", ", ".join(current_keyterms))
    keyterms_text.grid(row=21, column=0, columnspan=2, sticky="w", padx=(20, 0), pady=5)

    # Buttons
    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=22, column=0, columnspan=2, pady=(20, 0), sticky="e")

    def save_elevenlabs_settings():
        try:
            num_speakers = None if not speakers_entry.get().strip() else int(speakers_entry.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Number of speakers must be a valid integer or empty.")
            return

        try:
            temperature = None if not temp_entry.get().strip() else float(temp_entry.get())
            if temperature is not None and (temperature < 0.0 or temperature > 2.0):
                messagebox.showerror("Invalid Input", "Temperature must be between 0.0 and 2.0.")
                return
        except ValueError:
            messagebox.showerror("Invalid Input", "Temperature must be a valid number or empty.")
            return

        try:
            diarization_threshold = None if not diar_thresh_entry.get().strip() else float(diar_thresh_entry.get())
            if diarization_threshold is not None and (diarization_threshold < 0.0 or diarization_threshold > 2.0):
                messagebox.showerror("Invalid Input", "Diarization threshold must be between 0.0 and 2.0.")
                return
        except ValueError:
            messagebox.showerror("Invalid Input", "Diarization threshold must be a valid number or empty.")
            return

        entity_detection = []
        if phi_var.get():
            entity_detection.append("phi")
        if pii_var.get():
            entity_detection.append("pii")
        if pci_var.get():
            entity_detection.append("pci")
        if offensive_var.get():
            entity_detection.append("offensive")

        keyterms_raw = keyterms_text.get("1.0", tk.END).strip()
        keyterms = [term.strip() for term in keyterms_raw.split(",") if term.strip()]
        if len(keyterms) > 100:
            messagebox.showwarning("Keyterms Limit", "Only the first 100 keyterms will be used.")
            keyterms = keyterms[:100]

        new_settings = {
            "model_id": model_var.get(),
            "language_code": lang_var.get(),
            "tag_audio_events": tag_events_var.get(),
            "num_speakers": num_speakers,
            "timestamps_granularity": granularity_var.get(),
            "diarize": diarize_var.get(),
            "temperature": temperature,
            "diarization_threshold": diarization_threshold,
            "entity_detection": entity_detection,
            "keyterms": keyterms
        }

        settings_manager.set_elevenlabs_settings(new_settings)
        messagebox.showinfo("Settings Saved", "ElevenLabs settings saved successfully")
        close_dialog()

    def cancel():
        close_dialog()

    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def _on_mousewheel_linux(event):
        if event.num == 4:
            canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            canvas.yview_scroll(1, "units")

    canvas.bind_all("<MouseWheel>", _on_mousewheel)
    canvas.bind_all("<Button-4>", _on_mousewheel_linux)
    canvas.bind_all("<Button-5>", _on_mousewheel_linux)

    def close_dialog():
        canvas.unbind_all("<MouseWheel>")
        canvas.unbind_all("<Button-4>")
        canvas.unbind_all("<Button-5>")
        dialog.destroy()

    dialog.protocol("WM_DELETE_WINDOW", close_dialog)

    ttk.Button(btn_frame, text="Cancel", command=cancel, width=10).pack(side="left", padx=5)
    ttk.Button(btn_frame, text="Save", command=save_elevenlabs_settings, bootstyle="success", width=10).pack(side="left", padx=5)


__all__ = ["show_elevenlabs_settings_dialog"]
