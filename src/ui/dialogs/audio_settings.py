"""
Audio Settings Dialogs - Re-export Facade

This module provides backward compatibility by re-exporting audio settings
dialogs from their refactored individual modules.

DEPRECATED: Import directly from individual dialog modules instead.
"""

import os
import tkinter as tk
from utils.structured_logging import get_logger

logger = get_logger(__name__)
from tkinter import messagebox

from ui.dialogs.elevenlabs_settings_dialog import show_elevenlabs_settings_dialog
from ui.dialogs.deepgram_settings_dialog import show_deepgram_settings_dialog
from ui.dialogs.groq_settings_dialog import show_groq_settings_dialog
from ui.dialogs.translation_settings_dialog import show_translation_settings_dialog
from ui.dialogs.tts_settings_dialog import show_tts_settings_dialog, _fetch_tts_voices
from ui.dialogs.custom_suggestions_dialog import show_custom_suggestions_dialog


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

    base_url = ollama_url.rstrip("/")

    try:
        response = requests.get(
            f"{base_url}/api/tags",
            headers={"Content-Type": "application/json"},
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            if "models" in data and len(data["models"]) > 0:
                models = [model["name"] for model in data["models"]]
                model_list = "\n".join(models[:10])
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
        logger.error(f"Ollama connection test error: {str(e)}")
        return False


__all__ = [
    "show_elevenlabs_settings_dialog",
    "show_deepgram_settings_dialog",
    "show_groq_settings_dialog",
    "show_translation_settings_dialog",
    "show_tts_settings_dialog",
    "show_custom_suggestions_dialog",
    "test_ollama_connection",
    "_fetch_tts_voices",
]
