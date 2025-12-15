"""
Audio Settings Dialogs Module

Dialog functions for configuring audio-related settings including:
- ElevenLabs STT settings
- Deepgram STT settings
- TTS (Text-to-Speech) settings
- Translation settings
"""

import os
import logging
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from typing import Dict, List

from ui.scaling_utils import ui_scaler
from ui.dialogs.dialog_utils import create_toplevel_dialog


def show_elevenlabs_settings_dialog(parent: tk.Tk) -> None:
    """Show dialog to configure ElevenLabs speech-to-text settings."""
    from settings.settings import SETTINGS, _DEFAULT_SETTINGS, save_settings

    # Get current ElevenLabs settings with fallback to defaults
    elevenlabs_settings = SETTINGS.get("elevenlabs", {})
    default_settings = _DEFAULT_SETTINGS.get("elevenlabs", {})

    dialog = create_toplevel_dialog(parent, "ElevenLabs Settings", "700x800")
    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)

    # Create form with current settings
    ttk.Label(frame, text="ElevenLabs Speech-to-Text Settings",
              font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky="w")

    # Model ID
    ttk.Label(frame, text="Model ID:").grid(row=1, column=0, sticky="w", pady=10)
    model_var = tk.StringVar(value=elevenlabs_settings.get("model_id", default_settings.get("model_id", "scribe_v1")))
    model_combo = ttk.Combobox(frame, textvariable=model_var, width=30)
    model_combo['values'] = ["scribe_v1", "scribe_v1_experimental"]  # Updated Dec 2025
    model_combo.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="scribe_v1: stable, scribe_v1_experimental: improved multi-language, reduced hallucinations",
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

    # Create a custom variable handler for the special "None" case
    speakers_value = elevenlabs_settings.get("num_speakers", default_settings.get("num_speakers", None))
    speakers_str = "" if speakers_value is None else str(speakers_value)
    speakers_entry = ttk.Entry(frame, width=30)
    speakers_entry.insert(0, speakers_str)
    speakers_entry.grid(row=7, column=1, sticky="w", padx=(10, 0), pady=10)

    ttk.Label(frame, text="Optional number of speakers. Leave empty for auto-detection.",
              wraplength=400, foreground="gray").grid(row=8, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Timestamps Granularity
    ttk.Label(frame, text="Timestamps Granularity:").grid(row=9, column=0, sticky="w", pady=10)
    granularity_var = tk.StringVar(value=elevenlabs_settings.get("timestamps_granularity", default_settings.get("timestamps_granularity", "word")))
    granularity_combo = ttk.Combobox(frame, textvariable=granularity_var, width=30)
    granularity_combo['values'] = ["word", "segment", "sentence"]
    granularity_combo.grid(row=9, column=1, sticky="w", padx=(10, 0), pady=10)

    # Diarize
    ttk.Label(frame, text="Diarize:").grid(row=10, column=0, sticky="w", pady=10)
    diarize_var = tk.BooleanVar(value=elevenlabs_settings.get("diarize", default_settings.get("diarize", True)))
    diarize_check = ttk.Checkbutton(frame, variable=diarize_var)
    diarize_check.grid(row=10, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Identify different speakers in the audio.",
              wraplength=400, foreground="gray").grid(row=11, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Temperature (new in 2025 API)
    ttk.Label(frame, text="Temperature:").grid(row=12, column=0, sticky="w", pady=10)
    temp_value = elevenlabs_settings.get("temperature", default_settings.get("temperature", None))
    temp_str = "" if temp_value is None else str(temp_value)
    temp_entry = ttk.Entry(frame, width=30)
    temp_entry.insert(0, temp_str)
    temp_entry.grid(row=12, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Optional. 0.0=deterministic, 1.0=creative. Leave empty for default.",
              wraplength=400, foreground="gray").grid(row=13, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Diarization Threshold (new in 2025 API)
    ttk.Label(frame, text="Diarization Threshold:").grid(row=14, column=0, sticky="w", pady=10)
    diar_thresh_value = elevenlabs_settings.get("diarization_threshold", default_settings.get("diarization_threshold", None))
    diar_thresh_str = "" if diar_thresh_value is None else str(diar_thresh_value)
    diar_thresh_entry = ttk.Entry(frame, width=30)
    diar_thresh_entry.insert(0, diar_thresh_str)
    diar_thresh_entry.grid(row=14, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Optional. Confidence threshold for speaker detection (0.0-1.0).",
              wraplength=400, foreground="gray").grid(row=15, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Create the buttons frame
    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=16, column=0, columnspan=2, pady=(20, 0), sticky="e")

    # Save handler - renamed to avoid conflict with imported save_settings
    def save_elevenlabs_settings():
        # Parse the number of speakers value (None or int)
        try:
            num_speakers = None if not speakers_entry.get().strip() else int(speakers_entry.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Number of speakers must be a valid integer or empty.")
            return

        # Parse temperature (None or float)
        try:
            temperature = None if not temp_entry.get().strip() else float(temp_entry.get())
            if temperature is not None and (temperature < 0.0 or temperature > 1.0):
                messagebox.showerror("Invalid Input", "Temperature must be between 0.0 and 1.0.")
                return
        except ValueError:
            messagebox.showerror("Invalid Input", "Temperature must be a valid number or empty.")
            return

        # Parse diarization threshold (None or float)
        try:
            diarization_threshold = None if not diar_thresh_entry.get().strip() else float(diar_thresh_entry.get())
            if diarization_threshold is not None and (diarization_threshold < 0.0 or diarization_threshold > 1.0):
                messagebox.showerror("Invalid Input", "Diarization threshold must be between 0.0 and 1.0.")
                return
        except ValueError:
            messagebox.showerror("Invalid Input", "Diarization threshold must be a valid number or empty.")
            return

        # Build the new settings
        new_settings = {
            "model_id": model_var.get(),
            "language_code": lang_var.get(),
            "tag_audio_events": tag_events_var.get(),
            "num_speakers": num_speakers,
            "timestamps_granularity": granularity_var.get(),
            "diarize": diarize_var.get(),
            "temperature": temperature,
            "diarization_threshold": diarization_threshold
        }

        # Update the settings
        SETTINGS["elevenlabs"] = new_settings
        save_settings(SETTINGS)  # This now refers to the imported save_settings function
        messagebox.showinfo("Settings Saved", "ElevenLabs settings saved successfully")
        dialog.destroy()

    # Cancel handler
    def cancel():
        dialog.destroy()

    ttk.Button(btn_frame, text="Cancel", command=cancel, width=10).pack(side="left", padx=5)
    ttk.Button(btn_frame, text="Save", command=save_elevenlabs_settings, bootstyle="success", width=10).pack(side="left", padx=5)


def show_deepgram_settings_dialog(parent: tk.Tk) -> None:
    """Show dialog to configure Deepgram speech-to-text settings."""
    from settings.settings import SETTINGS, _DEFAULT_SETTINGS, save_settings

    # Get current Deepgram settings with fallback to defaults
    deepgram_settings = SETTINGS.get("deepgram", {})
    default_settings = _DEFAULT_SETTINGS.get("deepgram", {})

    # Increase height from 800 to 900 to provide more space for all settings
    dialog = create_toplevel_dialog(parent, "Deepgram Settings", "700x900")

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
    ttk.Label(frame, text="Deepgram Speech-to-Text Settings",
              font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky="w")

    # Model selection
    ttk.Label(frame, text="Model:").grid(row=1, column=0, sticky="w", pady=10)
    model_var = tk.StringVar(value=deepgram_settings.get("model", default_settings.get("model", "nova-2-medical")))
    model_combo = ttk.Combobox(frame, textvariable=model_var, width=30)
    model_combo['values'] = [
        "nova-2-medical",
        "nova-2",
        "enhanced",
        "base"
    ]
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

    # Smart formatting toggle
    ttk.Label(frame, text="Smart Formatting:").grid(row=5, column=0, sticky="w", pady=10)
    smart_format_var = tk.BooleanVar(value=deepgram_settings.get("smart_format", default_settings.get("smart_format", True)))
    smart_format_check = ttk.Checkbutton(frame, variable=smart_format_var)
    smart_format_check.grid(row=5, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Adds punctuation and capitalization to transcriptions.",
              wraplength=400, foreground="gray").grid(row=6, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Diarization toggle
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

    # Number of alternatives
    ttk.Label(frame, text="Alternatives:").grid(row=13, column=0, sticky="w", pady=10)
    alternatives_var = tk.StringVar(value=str(deepgram_settings.get("alternatives", default_settings.get("alternatives", 1))))
    alternatives_spin = ttk.Spinbox(frame, from_=1, to=5, width=5, textvariable=alternatives_var)
    alternatives_spin.grid(row=13, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Number of alternative transcriptions to generate.",
              wraplength=400, foreground="gray").grid(row=14, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Create the buttons frame
    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=15, column=0, columnspan=2, pady=(20, 0), sticky="e")

    # Save handler
    def save_deepgram_settings():
        try:
            alternatives = int(alternatives_var.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Number of alternatives must be a valid integer.")
            return

        # Build the new settings
        new_settings = {
            "model": model_var.get(),
            "language": language_var.get(),
            "smart_format": smart_format_var.get(),
            "diarize": diarize_var.get(),
            "profanity_filter": profanity_var.get(),
            "redact": redact_var.get(),
            "alternatives": alternatives
        }

        # Update the settings
        SETTINGS["deepgram"] = new_settings
        save_settings(SETTINGS)
        messagebox.showinfo("Settings Saved", "Deepgram settings saved successfully")
        dialog.destroy()

    # Cancel handler
    def cancel():
        dialog.destroy()

    ttk.Button(btn_frame, text="Cancel", command=cancel, width=10).pack(side="left", padx=5)
    ttk.Button(btn_frame, text="Save", command=save_deepgram_settings, bootstyle="success", width=10).pack(side="left", padx=5)

    # Bind mousewheel for scrolling
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    # Ensure dialog is closed properly
    def on_close():
        canvas.unbind_all("<MouseWheel>")
        dialog.destroy()

    dialog.protocol("WM_DELETE_WINDOW", on_close)


def show_groq_settings_dialog(parent: tk.Tk) -> None:
    """Show dialog to configure Groq speech-to-text settings."""
    from settings.settings import SETTINGS, _DEFAULT_SETTINGS, save_settings

    # Get current Groq settings with fallback to defaults
    groq_settings = SETTINGS.get("groq", {})
    default_settings = _DEFAULT_SETTINGS.get("groq", {
        "model": "whisper-large-v3-turbo",
        "language": "en",
        "prompt": ""
    })

    dialog = create_toplevel_dialog(parent, "Groq Settings", "600x450")

    # Create the main frame with padding
    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)

    # Create form with current settings
    ttk.Label(frame, text="Groq Speech-to-Text Settings",
              font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky="w")

    # Model selection
    ttk.Label(frame, text="Model:").grid(row=1, column=0, sticky="w", pady=10)
    model_var = tk.StringVar(value=groq_settings.get("model", default_settings.get("model", "whisper-large-v3-turbo")))
    model_combo = ttk.Combobox(frame, textvariable=model_var, width=30, state="readonly")
    model_combo['values'] = [
        "whisper-large-v3-turbo",   # Fastest, 216x real-time
        "whisper-large-v3",         # Higher quality
        "distil-whisper-large-v3-en"  # English-only, fast
    ]
    model_combo.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="whisper-large-v3-turbo: fastest (216x real-time), whisper-large-v3: higher quality",
              wraplength=400, foreground="gray").grid(row=2, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Language
    ttk.Label(frame, text="Language:").grid(row=3, column=0, sticky="w", pady=10)
    language_var = tk.StringVar(value=groq_settings.get("language", default_settings.get("language", "en")))
    language_combo = ttk.Combobox(frame, textvariable=language_var, width=30)
    language_combo['values'] = [
        "en", "es", "fr", "de", "it", "pt", "nl", "pl", "ru",
        "ja", "ko", "zh", "ar", "hi", "tr", "vi", "th"
    ]
    language_combo.grid(row=3, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="ISO-639-1 language code. Setting this improves accuracy and latency.",
              wraplength=400, foreground="gray").grid(row=4, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Prompt (context/spelling hints)
    ttk.Label(frame, text="Prompt:").grid(row=5, column=0, sticky="nw", pady=10)
    prompt_text = tk.Text(frame, width=35, height=4, wrap=tk.WORD)
    prompt_text.insert("1.0", groq_settings.get("prompt", default_settings.get("prompt", "")))
    prompt_text.grid(row=5, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Optional context or spelling hints (max 224 tokens). Example: medical terminology, names.",
              wraplength=400, foreground="gray").grid(row=6, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Create the buttons frame
    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=7, column=0, columnspan=2, pady=(20, 0), sticky="e")

    # Save handler
    def save_groq_settings():
        # Get prompt text
        prompt = prompt_text.get("1.0", tk.END).strip()

        # Build the new settings
        new_settings = {
            "model": model_var.get(),
            "language": language_var.get(),
            "prompt": prompt
        }

        # Update the settings
        SETTINGS["groq"] = new_settings
        save_settings(SETTINGS)
        messagebox.showinfo("Settings Saved", "Groq settings saved successfully")
        dialog.destroy()

    # Cancel handler
    def cancel():
        dialog.destroy()

    ttk.Button(btn_frame, text="Cancel", command=cancel, width=10).pack(side="left", padx=5)
    ttk.Button(btn_frame, text="Save", command=save_groq_settings, bootstyle="success", width=10).pack(side="left", padx=5)


def show_translation_settings_dialog(parent: tk.Tk) -> None:
    """Show dialog to configure translation settings."""
    from settings.settings import SETTINGS, _DEFAULT_SETTINGS, save_settings

    # Get current translation settings with fallback to defaults
    translation_settings = SETTINGS.get("translation", {})
    default_settings = _DEFAULT_SETTINGS.get("translation", {})

    dialog = create_toplevel_dialog(parent, "Translation Settings", "600x500")

    # Create the main frame with padding
    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)

    # Title
    ttk.Label(frame, text="Translation Settings",
              font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky="w")

    # Provider selection
    ttk.Label(frame, text="Translation Provider:").grid(row=1, column=0, sticky="w", pady=10)
    provider_var = tk.StringVar(value=translation_settings.get("provider", default_settings.get("provider", "deep_translator")))
    provider_combo = ttk.Combobox(frame, textvariable=provider_var, width=30, state="readonly")
    provider_combo['values'] = ["deep_translator"]
    provider_combo.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=10)

    # Sub-provider selection (for deep_translator)
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
        """Save the translation settings."""
        SETTINGS["translation"] = {
            "provider": provider_var.get(),
            "sub_provider": sub_provider_var.get(),
            "patient_language": patient_lang_var.get(),
            "doctor_language": doctor_lang_var.get(),
            "auto_detect": auto_detect_var.get()
        }
        save_settings(SETTINGS)
        dialog.destroy()

    ttk.Button(button_frame, text="Save", command=save_translation_settings).pack(side=tk.RIGHT, padx=(0, 20))
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)


def _fetch_tts_voices(provider: str) -> List[Dict[str, str]]:
    """Fetch available voices for a TTS provider.

    Args:
        provider: TTS provider name ('openai' or 'elevenlabs')

    Returns:
        List of voice dictionaries with 'id' and 'name' keys
    """
    try:
        # Import here to avoid circular imports
        from voice.tts_providers import OpenAITTSProvider, ElevenLabsTTSProvider

        if provider == "openai":
            # Get OpenAI API key
            api_key = os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                return []

            # Create provider and get voices
            tts_provider = OpenAITTSProvider(api_key)
            voices = tts_provider.get_voices()

        elif provider == "elevenlabs":
            # Get ElevenLabs API key
            api_key = os.getenv("ELEVENLABS_API_KEY", "")
            if not api_key:
                return []

            # Create provider and get voices
            tts_provider = ElevenLabsTTSProvider(api_key)
            voices = tts_provider.get_voices()

        else:
            return []

        return voices

    except Exception as e:
        logging.error(f"Error fetching TTS voices for {provider}: {e}")
        return []


def show_tts_settings_dialog(parent: tk.Tk) -> None:
    """Show dialog to configure TTS (Text-to-Speech) settings."""
    from settings.settings import SETTINGS, _DEFAULT_SETTINGS, save_settings

    # Get current TTS settings with fallback to defaults
    tts_settings = SETTINGS.get("tts", {})
    default_settings = _DEFAULT_SETTINGS.get("tts", {})

    dialog = create_toplevel_dialog(parent, "TTS Settings", "600x550")

    # Create the main frame with padding
    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)

    # Title
    ttk.Label(frame, text="Text-to-Speech Settings",
              font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky="w")

    # Provider selection
    ttk.Label(frame, text="TTS Provider:").grid(row=1, column=0, sticky="w", pady=10)
    provider_var = tk.StringVar(value=tts_settings.get("provider", default_settings.get("provider", "pyttsx3")))
    provider_combo = ttk.Combobox(frame, textvariable=provider_var, width=30, state="readonly")
    provider_combo['values'] = ["pyttsx3", "elevenlabs", "google"]
    provider_combo.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="pyttsx3 is offline, ElevenLabs requires API key, Google is free online",
              wraplength=400, foreground="gray").grid(row=2, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Voice selection (will be populated based on provider)
    ttk.Label(frame, text="Voice:").grid(row=3, column=0, sticky="w", pady=10)
    voice_var = tk.StringVar(value=tts_settings.get("voice", default_settings.get("voice", "default")))

    # Create frame for voice selection
    voice_frame = ttk.Frame(frame)
    voice_frame.grid(row=3, column=1, sticky="w", padx=(10, 0), pady=10)

    # Voice combo box (hidden by default, shown for ElevenLabs)
    voice_combo = ttk.Combobox(voice_frame, textvariable=voice_var, width=40, state="readonly")

    # Voice entry (shown by default)
    voice_entry = ttk.Entry(voice_frame, textvariable=voice_var, width=32)
    voice_entry.pack(side=tk.LEFT)

    # Fetch voices button (hidden by default)
    fetch_button = ttk.Button(voice_frame, text="Fetch Voices", width=12)

    # Loading label
    loading_label = ttk.Label(voice_frame, text="Loading...", foreground="blue")

    # Voice description label
    voice_desc_label = ttk.Label(frame, text="Voice ID or name (provider-specific, 'default' for system default)",
                                 wraplength=400, foreground="gray")
    voice_desc_label.grid(row=4, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Store voice data
    voices_data = {}

    # Speech rate
    ttk.Label(frame, text="Speech Rate:").grid(row=5, column=0, sticky="w", pady=10)
    rate_var = tk.IntVar(value=tts_settings.get("rate", default_settings.get("rate", 150)))
    rate_scale = ttk.Scale(frame, from_=50, to=300, variable=rate_var, orient="horizontal", length=200)
    rate_scale.grid(row=5, column=1, sticky="w", padx=(10, 0), pady=10)
    rate_label = ttk.Label(frame, text=f"{rate_var.get()} words/min")
    rate_label.grid(row=5, column=1, sticky="e", padx=(0, 10), pady=10)

    def update_rate_label(value):
        rate_label.config(text=f"{int(float(value))} words/min")

    rate_scale.config(command=update_rate_label)

    # Volume
    ttk.Label(frame, text="Volume:").grid(row=6, column=0, sticky="w", pady=10)
    volume_var = tk.DoubleVar(value=tts_settings.get("volume", default_settings.get("volume", 1.0)))
    volume_scale = ttk.Scale(frame, from_=0.0, to=1.0, variable=volume_var, orient="horizontal", length=200)
    volume_scale.grid(row=6, column=1, sticky="w", padx=(10, 0), pady=10)
    volume_label = ttk.Label(frame, text=f"{int(volume_var.get() * 100)}%")
    volume_label.grid(row=6, column=1, sticky="e", padx=(0, 10), pady=10)

    def update_volume_label(value):
        volume_label.config(text=f"{int(float(value) * 100)}%")

    volume_scale.config(command=update_volume_label)

    # Function to fetch ElevenLabs voices
    def fetch_elevenlabs_voices():
        """Fetch available voices from ElevenLabs API."""
        import threading

        # Show loading
        fetch_button.pack_forget()
        loading_label.pack(side=tk.LEFT, padx=(10, 0))

        def fetch_voices_thread():
            try:
                # Import and create TTS manager
                from managers.tts_manager import get_tts_manager
                from utils.security import get_security_manager
                from settings.settings import SETTINGS

                # Check if API key exists
                security_manager = get_security_manager()
                api_key = security_manager.get_api_key("elevenlabs")

                if not api_key:
                    dialog.after(0, lambda: [
                        loading_label.pack_forget(),
                        fetch_button.pack(side=tk.LEFT, padx=(10, 0)),
                        messagebox.showwarning("API Key Missing",
                                             "Please set your ElevenLabs API key first.",
                                             parent=dialog)
                    ])
                    return

                # Get TTS manager
                tts_manager = get_tts_manager()

                # Temporarily update settings to use ElevenLabs provider
                original_provider = SETTINGS.get("tts", {}).get("provider", "pyttsx3")
                SETTINGS["tts"]["provider"] = "elevenlabs"

                # Force provider recreation by setting current provider to None
                tts_manager._current_provider = None

                # Fetch voices
                voices = tts_manager.get_available_voices()

                # Restore original provider
                SETTINGS["tts"]["provider"] = original_provider

                if voices:
                    # Format voices for display
                    voice_display_list = []
                    voices_data.clear()

                    for voice in voices:
                        # Format: "Voice Name (Category)"
                        name = voice.get("name", "Unknown")
                        desc = voice.get("description", "")
                        category = desc.split(" - ")[0] if " - " in desc else ""

                        if category:
                            display_name = f"{name} ({category})"
                        else:
                            display_name = name

                        voice_display_list.append(display_name)
                        voices_data[display_name] = voice.get("id", "")

                    # Update UI on main thread
                    def update_ui():
                        loading_label.pack_forget()
                        voice_combo['values'] = sorted(voice_display_list)
                        voice_desc_label.config(text="Select a voice from the dropdown")

                        # Try to select the saved voice
                        current_voice_id = voice_var.get()
                        selected = False

                        # Look for matching voice ID
                        for display_name, voice_id in voices_data.items():
                            if voice_id == current_voice_id:
                                voice_combo.set(display_name)
                                selected = True
                                break

                        # If not found, select first voice
                        if not selected and voice_display_list:
                            voice_combo.set(voice_display_list[0])

                    dialog.after(0, update_ui)
                else:
                    dialog.after(0, lambda: [
                        loading_label.pack_forget(),
                        fetch_button.pack(side=tk.LEFT, padx=(10, 0)),
                        messagebox.showwarning("No Voices Found",
                                             "Could not fetch voices from ElevenLabs.",
                                             parent=dialog)
                    ])

            except Exception as e:
                error_msg = str(e)
                dialog.after(0, lambda: [
                    loading_label.pack_forget(),
                    fetch_button.pack(side=tk.LEFT, padx=(10, 0)),
                    messagebox.showerror("Error",
                                       f"Failed to fetch voices: {error_msg}",
                                       parent=dialog)
                ])

        # Start fetch in background thread
        thread = threading.Thread(target=fetch_voices_thread, daemon=True)
        thread.start()

    # Configure fetch button
    fetch_button.config(command=fetch_elevenlabs_voices)

    # Create ElevenLabs Model Selection widgets first (before on_provider_change)
    # They will be positioned later
    model_label = ttk.Label(frame, text="ElevenLabs Model:")
    elevenlabs_model_var = tk.StringVar(value=tts_settings.get("elevenlabs_model", default_settings.get("elevenlabs_model", "eleven_turbo_v2_5")))
    model_combo = ttk.Combobox(frame, textvariable=elevenlabs_model_var, width=30, state="readonly")
    model_combo['values'] = [
        "eleven_turbo_v2_5",  # Fast, good quality
        "eleven_multilingual_v2",  # High quality multilingual (default)
        "eleven_flash_v2_5"  # Ultra-low latency, 50% cheaper
    ]
    model_desc_label = ttk.Label(frame, text="Flash v2.5: fastest/cheapest, Turbo v2.5: balanced, Multilingual v2: best quality",
                                 wraplength=400, foreground="gray")

    # Function to handle provider change
    def on_provider_change(*args):
        """Handle TTS provider change."""
        provider = provider_var.get()

        if provider == "elevenlabs":
            # Show combo box and fetch button
            voice_entry.pack_forget()
            voice_combo.pack(side=tk.LEFT)
            fetch_button.pack(side=tk.LEFT, padx=(10, 0))
            voice_desc_label.config(text="Click 'Fetch Voices' to load available voices")

            # Show model selection
            model_label.grid()
            model_combo.grid()
            model_desc_label.grid()

            # If we already have voices data, show them
            if voices_data:
                voice_combo['values'] = sorted(voices_data.keys())
        else:
            # Show entry field
            voice_combo.pack_forget()
            fetch_button.pack_forget()
            loading_label.pack_forget()
            voice_entry.pack(side=tk.LEFT)
            voice_desc_label.config(text="Voice ID or name (provider-specific, 'default' for system default)")

            # Hide model selection
            model_label.grid_remove()
            model_combo.grid_remove()
            model_desc_label.grid_remove()

    # Bind provider change
    provider_combo.bind("<<ComboboxSelected>>", on_provider_change)

    # Initialize UI based on current provider
    on_provider_change()

    # If ElevenLabs and we have a saved voice ID, try to fetch voices
    if provider_var.get() == "elevenlabs" and voice_var.get() and voice_var.get() != "default":
        # Auto-fetch voices on dialog open for ElevenLabs
        dialog.after(100, fetch_elevenlabs_voices)

    # Default language
    ttk.Label(frame, text="Default Language:").grid(row=7, column=0, sticky="w", pady=10)
    language_var = tk.StringVar(value=tts_settings.get("language", default_settings.get("language", "en")))
    language_entry = ttk.Entry(frame, textvariable=language_var, width=32)
    language_entry.grid(row=7, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Language code (e.g., en, es, fr)",
              wraplength=400, foreground="gray").grid(row=8, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Position the ElevenLabs Model Selection widgets (already created above)
    model_label.grid(row=9, column=0, sticky="w", pady=10)
    model_combo.grid(row=9, column=1, sticky="w", padx=(10, 0), pady=10)
    model_desc_label.grid(row=10, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Hide model selection initially if not ElevenLabs
    if provider_var.get() != "elevenlabs":
        model_label.grid_remove()
        model_combo.grid_remove()
        model_desc_label.grid_remove()

    # Button frame
    button_frame = ttk.Frame(dialog)
    button_frame.pack(fill=tk.X, pady=(0, 20))

    def save_tts_settings():
        """Save the TTS settings."""
        provider = provider_var.get()
        voice_value = voice_var.get()

        # For ElevenLabs, convert display name to voice ID
        if provider == "elevenlabs" and voice_value in voices_data:
            voice_value = voices_data[voice_value]

        SETTINGS["tts"] = {
            "provider": provider,
            "voice": voice_value,
            "rate": rate_var.get(),
            "volume": volume_var.get(),
            "language": language_var.get(),
            "elevenlabs_model": elevenlabs_model_var.get()
        }
        save_settings(SETTINGS)
        dialog.destroy()

    ttk.Button(button_frame, text="Save", command=save_tts_settings).pack(side=tk.RIGHT, padx=(0, 20))
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)


def test_ollama_connection(_: tk.Tk, ollama_url: str = None) -> bool:
    """
    Test the connection to Ollama server and show a message with the results.

    Args:
        parent: Parent window
        ollama_url: The Ollama API URL to test, if None, will use environment variable or default

    Returns:
        bool: True if connection was successful, False otherwise
    """
    import requests

    if ollama_url is None:
        ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")

    base_url = ollama_url.rstrip("/")  # Remove trailing slash if present

    try:
        # Get available models as a connection test
        response = requests.get(
            f"{base_url}/api/tags",
            headers={"Content-Type": "application/json"},
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            if "models" in data and len(data["models"]) > 0:
                # Get the list of available models
                models = [model["name"] for model in data["models"]]
                model_list = "\n".join(models[:10])  # Show first 10 models
                if len(models) > 10:
                    model_list += f"\n...and {len(models)-10} more"

                messagebox.showinfo(
                    "Ollama Connection Successful",
                    f"Successfully connected to Ollama server at {ollama_url}.\n\n"
                    f"Available models:\n{model_list}"
                )
                return True
            else:
                messagebox.showwarning(
                    "Ollama Connection Warning",
                    f"Connected to Ollama server at {ollama_url}, but no models were found.\n\n"
                    "Please pull at least one model using 'ollama pull <model_name>'"
                )
                return False
        else:
            messagebox.showerror(
                "Ollama Connection Failed",
                f"Could not connect to Ollama server at {ollama_url}.\n\n"
                f"Status code: {response.status_code}\n"
                "Please make sure Ollama is running and the URL is correct."
            )
            return False
    except Exception as e:
        messagebox.showerror(
            "Ollama Connection Error",
            f"Error connecting to Ollama server at {ollama_url}:\n\n{str(e)}\n\n"
            "Please make sure Ollama is running and the URL is correct."
        )
        logging.error(f"Ollama connection test error: {str(e)}")
        return False


def show_custom_suggestions_dialog(parent: tk.Tk) -> None:
    """Show dialog to manage custom chat suggestions."""
    from settings.settings import SETTINGS, save_settings

    # Create dialog
    dialog = tk.Toplevel(parent)
    dialog.title("Manage Custom Chat Suggestions")
    dialog_width, dialog_height = ui_scaler.get_dialog_size(700, 600)
    dialog.geometry(f"{dialog_width}x{dialog_height}")
    dialog.resizable(True, True)
    dialog.transient(parent)
    dialog.grab_set()

    # Center the dialog
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - (dialog_width // 2)
    y = (dialog.winfo_screenheight() // 2) - (dialog_height // 2)
    dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

    # Main frame with padding
    main_frame = ttk.Frame(dialog, padding=15)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Title and description
    title_frame = ttk.Frame(main_frame)
    title_frame.pack(fill=tk.X, pady=(0, 15))

    ttk.Label(title_frame, text="Custom Chat Suggestions", font=("Arial", 14, "bold")).pack(anchor="w")
    ttk.Label(title_frame, text="Create custom suggestions for different contexts. These will appear alongside built-in suggestions.",
              font=("Arial", 10), foreground="gray").pack(anchor="w", pady=(5, 0))

    # Create notebook for different contexts
    notebook = ttk.Notebook(main_frame)
    notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

    # Store references to suggestion lists
    suggestion_vars = {}

    def create_suggestion_tab(tab_name: str, context_key: str):
        """Create a tab for managing suggestions in a specific context."""
        tab_frame = ttk.Frame(notebook)
        notebook.add(tab_frame, text=tab_name)

        # Context-specific suggestions (with_content vs without_content)
        if context_key != "global":
            # With content section
            with_frame = ttk.LabelFrame(tab_frame, text="When content exists", padding=10)
            with_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            with_vars = create_suggestion_manager(with_frame, context_key, "with_content")
            suggestion_vars[f"{context_key}_with_content"] = with_vars

            # Without content section
            without_frame = ttk.LabelFrame(tab_frame, text="When no content exists", padding=10)
            without_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            without_vars = create_suggestion_manager(without_frame, context_key, "without_content")
            suggestion_vars[f"{context_key}_without_content"] = without_vars
        else:
            # Global suggestions (always shown)
            global_vars = create_suggestion_manager(tab_frame, context_key, None)
            suggestion_vars["global"] = global_vars

    def create_suggestion_manager(parent_frame: ttk.Frame, context: str, content_state: str):
        """Create suggestion management interface for a specific context."""
        # Get current suggestions
        if context == "global":
            current_suggestions = SETTINGS.get("custom_chat_suggestions", {}).get("global", [])
        else:
            current_suggestions = SETTINGS.get("custom_chat_suggestions", {}).get(context, {}).get(content_state, [])

        # Variables to track suggestions
        suggestion_vars_list = []

        # Scrollable frame for suggestions
        canvas = tk.Canvas(parent_frame, height=150)
        scrollbar = ttk.Scrollbar(parent_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Function to add a suggestion entry
        def add_suggestion_entry(text=""):
            entry_frame = ttk.Frame(scrollable_frame)
            entry_frame.pack(fill=tk.X, pady=2)

            var = tk.StringVar(value=text)
            entry = ttk.Entry(entry_frame, textvariable=var, width=50)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

            def remove_entry():
                suggestion_vars_list.remove((entry_frame, var))
                entry_frame.destroy()
                canvas.configure(scrollregion=canvas.bbox("all"))

            remove_btn = ttk.Button(entry_frame, text="×", width=3, command=remove_entry)
            remove_btn.pack(side=tk.RIGHT)

            suggestion_vars_list.append((entry_frame, var))

            # Update scroll region
            canvas.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))

            return var

        # Add existing suggestions
        for suggestion in current_suggestions:
            add_suggestion_entry(suggestion)

        # Add button frame
        button_frame = ttk.Frame(parent_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        def add_new_suggestion():
            var = add_suggestion_entry()
            # Focus the new entry
            for entry_frame, entry_var in suggestion_vars_list:
                if entry_var == var:
                    for widget in entry_frame.winfo_children():
                        if isinstance(widget, ttk.Entry):
                            widget.focus_set()
                            break
                    break

        ttk.Button(button_frame, text="+ Add Suggestion", command=add_new_suggestion).pack(side=tk.LEFT)

        def clear_all():
            if messagebox.askyesno("Clear All", "Are you sure you want to remove all suggestions?", parent=dialog):
                for entry_frame, _ in suggestion_vars_list.copy():
                    entry_frame.destroy()
                suggestion_vars_list.clear()
                canvas.configure(scrollregion=canvas.bbox("all"))

        ttk.Button(button_frame, text="Clear All", command=clear_all).pack(side=tk.LEFT, padx=(10, 0))

        return suggestion_vars_list

    # Create tabs
    create_suggestion_tab("Global", "global")
    create_suggestion_tab("Transcript", "transcript")
    create_suggestion_tab("SOAP Note", "soap")
    create_suggestion_tab("Referral", "referral")
    create_suggestion_tab("Letter", "letter")

    # Bottom buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, pady=(10, 0))

    def save_suggestions():
        """Save all custom suggestions to settings."""
        try:
            custom_suggestions = SETTINGS.get("custom_chat_suggestions", {})

            # Update global suggestions
            if "global" in suggestion_vars:
                global_suggestions = []
                for _, var in suggestion_vars["global"]:
                    text = var.get().strip()
                    if text:
                        global_suggestions.append(text)
                custom_suggestions["global"] = global_suggestions

            # Update context-specific suggestions
            for context in ["transcript", "soap", "referral", "letter"]:
                if context not in custom_suggestions:
                    custom_suggestions[context] = {"with_content": [], "without_content": []}

                # With content
                key = f"{context}_with_content"
                if key in suggestion_vars:
                    with_suggestions = []
                    for _, var in suggestion_vars[key]:
                        text = var.get().strip()
                        if text:
                            with_suggestions.append(text)
                    custom_suggestions[context]["with_content"] = with_suggestions

                # Without content
                key = f"{context}_without_content"
                if key in suggestion_vars:
                    without_suggestions = []
                    for _, var in suggestion_vars[key]:
                        text = var.get().strip()
                        if text:
                            without_suggestions.append(text)
                    custom_suggestions[context]["without_content"] = without_suggestions

            # Save to settings
            SETTINGS["custom_chat_suggestions"] = custom_suggestions
            save_settings(SETTINGS)

            messagebox.showinfo("Success", "Custom suggestions saved successfully!", parent=dialog)
            dialog.destroy()

        except Exception as e:
            logging.error(f"Error saving custom suggestions: {e}")
            messagebox.showerror("Error", f"Failed to save suggestions: {str(e)}", parent=dialog)

    def cancel():
        dialog.destroy()

    # Buttons
    ttk.Button(button_frame, text="Save", command=save_suggestions, bootstyle="success").pack(side=tk.RIGHT, padx=(5, 0))
    ttk.Button(button_frame, text="Cancel", command=cancel).pack(side=tk.RIGHT)

    # Handle window close
    dialog.protocol("WM_DELETE_WINDOW", cancel)

    # Wait for dialog
    dialog.wait_window()
