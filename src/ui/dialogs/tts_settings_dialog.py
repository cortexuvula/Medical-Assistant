"""
TTS Settings Dialog

Dialog for configuring Text-to-Speech settings.
"""

import os
import threading
from utils.structured_logging import get_logger

logger = get_logger(__name__)
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from typing import Dict, List

from settings import settings_manager
from ui.dialogs.dialog_utils import create_toplevel_dialog


def _fetch_tts_voices(provider: str) -> List[Dict[str, str]]:
    """Fetch available voices for a TTS provider.

    Args:
        provider: TTS provider name ('openai' or 'elevenlabs')

    Returns:
        List of voice dictionaries with 'id' and 'name' keys
    """
    try:
        from voice.tts_providers import OpenAITTSProvider, ElevenLabsTTSProvider

        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                return []
            tts_provider = OpenAITTSProvider(api_key)
            voices = tts_provider.get_voices()

        elif provider == "elevenlabs":
            api_key = os.getenv("ELEVENLABS_API_KEY", "")
            if not api_key:
                return []
            tts_provider = ElevenLabsTTSProvider(api_key)
            voices = tts_provider.get_voices()

        else:
            return []

        return voices

    except Exception as e:
        logger.error(f"Error fetching TTS voices for {provider}: {e}")
        return []


def show_tts_settings_dialog(parent: tk.Tk) -> None:
    """Show dialog to configure TTS (Text-to-Speech) settings."""
    tts_settings = settings_manager.get_tts_settings()
    default_settings = settings_manager.get_default("tts", {})

    dialog = create_toplevel_dialog(parent, "TTS Settings", "600x550")

    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)

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

    # Voice selection
    ttk.Label(frame, text="Voice:").grid(row=3, column=0, sticky="w", pady=10)
    voice_var = tk.StringVar(value=tts_settings.get("voice", default_settings.get("voice", "default")))

    voice_frame = ttk.Frame(frame)
    voice_frame.grid(row=3, column=1, sticky="w", padx=(10, 0), pady=10)

    voice_combo = ttk.Combobox(voice_frame, textvariable=voice_var, width=40, state="readonly")
    voice_entry = ttk.Entry(voice_frame, textvariable=voice_var, width=32)
    voice_entry.pack(side=tk.LEFT)

    fetch_button = ttk.Button(voice_frame, text="Fetch Voices", width=12)
    loading_label = ttk.Label(voice_frame, text="Loading...", foreground="blue")

    voice_desc_label = ttk.Label(frame, text="Voice ID or name (provider-specific, 'default' for system default)",
                                 wraplength=400, foreground="gray")
    voice_desc_label.grid(row=4, column=0, columnspan=2, sticky="w", padx=(20, 0))

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

    # ElevenLabs Model Selection widgets
    model_label = ttk.Label(frame, text="ElevenLabs Model:")
    elevenlabs_model_var = tk.StringVar(value=tts_settings.get("elevenlabs_model", default_settings.get("elevenlabs_model", "eleven_turbo_v2_5")))
    model_combo = ttk.Combobox(frame, textvariable=elevenlabs_model_var, width=30, state="readonly")
    model_combo['values'] = [
        "eleven_turbo_v2_5",
        "eleven_multilingual_v2",
        "eleven_flash_v2_5"
    ]
    model_desc_label = ttk.Label(frame, text="Flash v2.5: fastest/cheapest, Turbo v2.5: balanced, Multilingual v2: best quality",
                                 wraplength=400, foreground="gray")

    def fetch_elevenlabs_voices():
        fetch_button.pack_forget()
        loading_label.pack(side=tk.LEFT, padx=(10, 0))

        def fetch_voices_thread():
            try:
                from managers.tts_manager import get_tts_manager
                from utils.security import get_security_manager

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

                tts_manager = get_tts_manager()
                original_provider = settings_manager.get_nested("tts.provider", "pyttsx3")
                settings_manager.set_nested("tts.provider", "elevenlabs", auto_save=False)
                tts_manager._current_provider = None
                voices = tts_manager.get_available_voices()
                settings_manager.set_nested("tts.provider", original_provider, auto_save=False)

                if voices:
                    voice_display_list = []
                    voices_data.clear()

                    for voice in voices:
                        name = voice.get("name", "Unknown")
                        desc = voice.get("description", "")
                        category = desc.split(" - ")[0] if " - " in desc else ""

                        if category:
                            display_name = f"{name} ({category})"
                        else:
                            display_name = name

                        voice_display_list.append(display_name)
                        voices_data[display_name] = voice.get("id", "")

                    def update_ui():
                        loading_label.pack_forget()
                        voice_combo['values'] = sorted(voice_display_list)
                        voice_desc_label.config(text="Select a voice from the dropdown")

                        current_voice_id = voice_var.get()
                        selected = False

                        for display_name, voice_id in voices_data.items():
                            if voice_id == current_voice_id:
                                voice_combo.set(display_name)
                                selected = True
                                break

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

        thread = threading.Thread(target=fetch_voices_thread, daemon=True)
        thread.start()

    fetch_button.config(command=fetch_elevenlabs_voices)

    def on_provider_change(*args):
        provider = provider_var.get()

        if provider == "elevenlabs":
            voice_entry.pack_forget()
            voice_combo.pack(side=tk.LEFT)
            fetch_button.pack(side=tk.LEFT, padx=(10, 0))
            voice_desc_label.config(text="Click 'Fetch Voices' to load available voices")

            model_label.grid()
            model_combo.grid()
            model_desc_label.grid()

            if voices_data:
                voice_combo['values'] = sorted(voices_data.keys())
        else:
            voice_combo.pack_forget()
            fetch_button.pack_forget()
            loading_label.pack_forget()
            voice_entry.pack(side=tk.LEFT)
            voice_desc_label.config(text="Voice ID or name (provider-specific, 'default' for system default)")

            model_label.grid_remove()
            model_combo.grid_remove()
            model_desc_label.grid_remove()

    provider_combo.bind("<<ComboboxSelected>>", on_provider_change)
    on_provider_change()

    if provider_var.get() == "elevenlabs" and voice_var.get() and voice_var.get() != "default":
        dialog.after(100, fetch_elevenlabs_voices)

    # Default language
    ttk.Label(frame, text="Default Language:").grid(row=7, column=0, sticky="w", pady=10)
    language_var = tk.StringVar(value=tts_settings.get("language", default_settings.get("language", "en")))
    language_entry = ttk.Entry(frame, textvariable=language_var, width=32)
    language_entry.grid(row=7, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Language code (e.g., en, es, fr)",
              wraplength=400, foreground="gray").grid(row=8, column=0, columnspan=2, sticky="w", padx=(20, 0))

    # Position ElevenLabs Model Selection widgets
    model_label.grid(row=9, column=0, sticky="w", pady=10)
    model_combo.grid(row=9, column=1, sticky="w", padx=(10, 0), pady=10)
    model_desc_label.grid(row=10, column=0, columnspan=2, sticky="w", padx=(20, 0))

    if provider_var.get() != "elevenlabs":
        model_label.grid_remove()
        model_combo.grid_remove()
        model_desc_label.grid_remove()

    # Button frame
    button_frame = ttk.Frame(dialog)
    button_frame.pack(fill=tk.X, pady=(0, 20))

    def save_tts_settings():
        provider = provider_var.get()
        voice_value = voice_var.get()

        if provider == "elevenlabs" and voice_value in voices_data:
            voice_value = voices_data[voice_value]

        settings_manager.set_tts_settings({
            "provider": provider,
            "voice": voice_value,
            "rate": rate_var.get(),
            "volume": volume_var.get(),
            "language": language_var.get(),
            "elevenlabs_model": elevenlabs_model_var.get()
        })
        dialog.destroy()

    ttk.Button(button_frame, text="Save", command=save_tts_settings).pack(side=tk.RIGHT, padx=(0, 20))
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)


__all__ = ["show_tts_settings_dialog", "_fetch_tts_voices"]
