"""
API Key Dialogs Module

Functions for prompting users for API keys and saving them.
"""

import os
import re
import tkinter as tk
from utils.structured_logging import get_logger

logger = get_logger(__name__)
import ttkbootstrap as ttk
from ui.scaling_utils import ui_scaler


def prompt_for_api_key(provider: str = "OpenAI") -> str:
    """Prompt the user for their API key."""
    dialog = tk.Toplevel()
    dialog.title(f"{provider} API Key Required")
    dialog_width, dialog_height = ui_scaler.get_dialog_size(450, 200)
    dialog.geometry(f"{dialog_width}x{dialog_height}")

    # Center the dialog
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - (dialog_width // 2)
    y = (dialog.winfo_screenheight() // 2) - (dialog_height // 2)
    dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

    # Grab focus after window is visible
    dialog.deiconify()
    try:
        dialog.grab_set()
    except tk.TclError:
        pass  # Window not viewable yet

    env_var_name = {
        "OpenAI": "OPENAI_API_KEY",
        "Anthropic": "ANTHROPIC_API_KEY",
        "Gemini": "GEMINI_API_KEY"
    }.get(provider, "API_KEY")

    provider_url = {
        "OpenAI": "https://platform.openai.com/account/api-keys",
        "Anthropic": "https://console.anthropic.com/account/keys",
        "Gemini": "https://aistudio.google.com/app/apikey"
    }.get(provider, "provider website")

    ttk.Label(dialog, text=f"Please enter your {provider} API Key:", wraplength=400).pack(pady=(20, 5))
    ttk.Label(dialog, text=f"You can get your key from your {provider_url}",
              font=("Segoe UI", 8), foreground="blue").pack()

    entry = ttk.Entry(dialog, width=50)
    entry.pack(pady=10, padx=20)

    # Add checkbox for saving the key
    save_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(dialog, text="Save key for future sessions", variable=save_var).pack()

    result = [None]

    def on_ok():
        key = entry.get().strip()
        if key:
            result[0] = key
            # Set environment variable
            os.environ[env_var_name] = key
            # Save to .env file if requested
            if save_var.get():
                save_api_key_to_env(key, env_var_name)
        dialog.destroy()

    def on_cancel():
        dialog.destroy()

    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(pady=20)
    ttk.Button(btn_frame, text="OK", command=on_ok).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side=tk.LEFT, padx=5)

    dialog.wait_window()
    return result[0]


def save_api_key_to_env(key: str, env_var_name: str) -> None:
    """Save the API key to the .env file."""
    try:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        env_content = ""
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                env_content = f.read()

        # Replace existing API key or add new one
        if f'{env_var_name}=' in env_content:
            env_content = re.sub(f'{env_var_name}=.*', f'{env_var_name}={key}', env_content)
        else:
            env_content += f'\n{env_var_name}={key}'

        with open(env_path, 'w') as f:
            f.write(env_content)

        logger.info(f"{env_var_name} saved to .env file")
    except Exception as e:
        logger.error(f"Failed to save {env_var_name}: {e}")


__all__ = ["prompt_for_api_key", "save_api_key_to_env"]
