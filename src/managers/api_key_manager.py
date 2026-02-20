"""
API Key Manager Module

Handles API key collection and validation through a GUI dialog.
Manages secure storage of API keys using encryption.
"""

import sys
import tkinter as tk
from typing import Dict, Optional
from managers.data_folder_manager import data_folder_manager
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class APIKeyManager:
    """Manages API key collection and validation with secure storage."""

    # Provider name mappings for secure storage
    PROVIDER_KEYS = {
        'openai': 'OPENAI_API_KEY',
        'deepgram': 'DEEPGRAM_API_KEY',
        'anthropic': 'ANTHROPIC_API_KEY',
        'elevenlabs': 'ELEVENLABS_API_KEY',
        'groq': 'GROQ_API_KEY',
        'gemini': 'GEMINI_API_KEY',
        'cerebras': 'CEREBRAS_API_KEY',
    }

    def __init__(self):
        """Initialize the API key manager."""
        self.env_path = data_folder_manager.env_file_path
        self._security_manager = None

    def _get_security_manager(self):
        """Lazy load security manager to avoid circular imports."""
        if self._security_manager is None:
            from utils.security import get_security_manager
            self._security_manager = get_security_manager()
        return self._security_manager

    def _has_stored_keys(self) -> bool:
        """Check if we have any API keys stored (encrypted or in .env).

        Returns:
            bool: True if at least one AI and one STT key exists
        """
        security_mgr = self._get_security_manager()

        # Check for AI provider keys
        ai_providers = ['openai', 'anthropic', 'gemini', 'groq', 'cerebras']
        has_ai_key = any(security_mgr.get_api_key(p) for p in ai_providers)

        # Check for STT provider keys
        stt_providers = ['deepgram', 'elevenlabs', 'groq']
        has_stt_key = any(security_mgr.get_api_key(p) for p in stt_providers)

        return has_ai_key and has_stt_key

    def _store_key_securely(self, provider: str, api_key: str) -> bool:
        """Store an API key securely using encryption.

        Args:
            provider: Provider name (e.g., 'openai', 'deepgram')
            api_key: The API key to store

        Returns:
            bool: True if stored successfully
        """
        if not api_key:
            return False

        try:
            security_mgr = self._get_security_manager()
            success, error = security_mgr.store_api_key(provider, api_key)
            if not success:
                logger.warning(f"Failed to store {provider} key securely: {error}")
                return False
            logger.info(f"Securely stored API key for {provider}")
            return True
        except Exception as e:
            logger.error(f"Error storing {provider} key: {e}")
            return False

    def check_env_file(self) -> bool:
        """Check if API keys exist (encrypted or in .env) and collect if needed.

        Returns:
            bool: True if the app should continue, False if it should exit
        """
        # Check if we have keys in secure storage or .env file
        if self.env_path.exists() or self._has_stored_keys():
            return True

        # Setup API key collection using standard Tk approach (not Toplevel)
        # This avoids window destruction issues
        return self._collect_api_keys_flow()
    
    def _collect_api_keys_flow(self) -> bool:
        """Handle the API key collection flow.
        
        Returns:
            bool: True if keys were collected successfully, False if cancelled
        """
        # Collect API keys and determine whether to continue
        should_continue = self._collect_api_keys()
        
        # If user cancelled or closed the window without saving, exit the program
        if not should_continue:
            sys.exit(0)
        
        return True
    
    def _collect_api_keys(self) -> bool:
        """Show API key collection dialog.
        
        Returns:
            bool: True if keys were saved successfully, False if cancelled
        """
        # Create a new root window specifically for API key collection
        api_root = tk.Tk()
        api_root.title("Medical Dictation App - API Keys Setup")
        api_root.geometry("500x680")
        should_continue = [False]  # Use list for mutable reference
        
        # Headers
        tk.Label(api_root, text="Welcome to Medical Dictation App!", 
                font=("Segoe UI", 14, "bold")).pack(pady=(20, 5))
        
        tk.Label(api_root, text="Please enter at least one of the following API keys to continue:",
                font=("Segoe UI", 11)).pack(pady=(0, 5))
        
        tk.Label(api_root, text="OpenAI, Anthropic, or Gemini API key is required. Either Deepgram, ElevenLabs, or GROQ API key is mandatory for speech recognition.",
                wraplength=450).pack(pady=(0, 20))
        
        # Create frame for keys
        keys_frame = tk.Frame(api_root)
        keys_frame.pack(fill="both", expand=True, padx=20)
        
        # Create entries for mandatory API keys first
        tk.Label(keys_frame, text="OpenAI API Key:").grid(row=0, column=0, sticky="w", pady=5)
        openai_entry = tk.Entry(keys_frame, width=40)
        openai_entry.grid(row=0, column=1, sticky="ew", pady=5)

        tk.Label(keys_frame, text="Anthropic API Key:").grid(row=1, column=0, sticky="w", pady=5)
        anthropic_entry = tk.Entry(keys_frame, width=40)
        anthropic_entry.grid(row=1, column=1, sticky="ew", pady=5)

        tk.Label(keys_frame, text="Google Gemini API Key:").grid(row=2, column=0, sticky="w", pady=5)
        gemini_entry = tk.Entry(keys_frame, width=40)
        gemini_entry.grid(row=2, column=1, sticky="ew", pady=5)

        # Create entry for optional API key last
        tk.Label(keys_frame, text="Deepgram API Key:").grid(row=3, column=0, sticky="w", pady=5)
        deepgram_entry = tk.Entry(keys_frame, width=40)
        deepgram_entry.grid(row=3, column=1, sticky="ew", pady=5)

        # ElevenLabs API Key field
        tk.Label(keys_frame, text="ElevenLabs API Key:").grid(row=4, column=0, sticky="w", pady=5)
        elevenlabs_entry = tk.Entry(keys_frame, width=40)
        elevenlabs_entry.grid(row=4, column=1, sticky="ew", pady=5)

        # GROQ API Key field
        tk.Label(keys_frame, text="GROQ API Key:").grid(row=5, column=0, sticky="w", pady=5)
        groq_entry = tk.Entry(keys_frame, width=40)
        groq_entry.grid(row=5, column=1, sticky="ew", pady=5)

        # Cerebras API Key field
        tk.Label(keys_frame, text="Cerebras API Key:").grid(row=6, column=0, sticky="w", pady=5)
        cerebras_entry = tk.Entry(keys_frame, width=40)
        cerebras_entry.grid(row=6, column=1, sticky="ew", pady=5)

        # Add info about where to find the keys
        info_text = ("Get your API keys at:\n"
                    "• OpenAI: https://platform.openai.com/account/api-keys\n"
                    "• Anthropic: https://console.anthropic.com/account/keys\n"
                    "• Gemini: https://aistudio.google.com/app/apikey\n"
                    "• Deepgram: https://console.deepgram.com/signup\n"
                    "• ElevenLabs: https://elevenlabs.io/app/speech-to-text\n"
                    "• GROQ: https://groq.com/\n"
                    "• Cerebras: https://cloud.cerebras.ai/")
        tk.Label(keys_frame, text=info_text, justify="left", wraplength=450).grid(
            row=7, column=0, columnspan=2, sticky="w", pady=10)
        
        error_var = tk.StringVar()
        error_label = tk.Label(api_root, textvariable=error_var, foreground="red", wraplength=450)
        error_label.pack(pady=5)
        
        def validate_and_save():
            """Validate API keys and store securely using encryption."""
            openai_key = openai_entry.get().strip()
            deepgram_key = deepgram_entry.get().strip()
            anthropic_key = anthropic_entry.get().strip()
            gemini_key = gemini_entry.get().strip()
            elevenlabs_key = elevenlabs_entry.get().strip()
            groq_key = groq_entry.get().strip()
            cerebras_key = cerebras_entry.get().strip()

            # Check if at least one AI provider key is provided
            if not (openai_key or anthropic_key or gemini_key or groq_key or cerebras_key):
                error_var.set("Error: At least one of OpenAI, Anthropic, or Gemini API keys is required.")
                return

            # Check if at least one speech-to-text API key is provided
            if not (deepgram_key or elevenlabs_key or groq_key):
                error_var.set("Error: Either Deepgram, ElevenLabs, or GROQ API key is mandatory for speech recognition.")
                return

            # Store keys securely using encryption
            keys_to_store = {
                'openai': openai_key,
                'deepgram': deepgram_key,
                'anthropic': anthropic_key,
                'gemini': gemini_key,
                'elevenlabs': elevenlabs_key,
                'groq': groq_key,
                'cerebras': cerebras_key,
            }

            stored_count = 0
            for provider, key in keys_to_store.items():
                if key:
                    if self._store_key_securely(provider, key):
                        stored_count += 1
                    else:
                        error_var.set(f"Error: Failed to securely store {provider} API key.")
                        return

            if stored_count == 0:
                error_var.set("Error: No API keys were stored.")
                return

            # Create minimal .env file with non-sensitive settings only
            with open(self.env_path, "w") as f:
                f.write("# API keys are stored securely in encrypted storage\n")
                f.write("# This file contains only non-sensitive configuration\n")
                f.write("RECOGNITION_LANGUAGE=en-US\n")

            logger.info(f"Securely stored {stored_count} API key(s)")
            should_continue[0] = True
            api_root.quit()
        
        def on_cancel():
            """Handle cancel button."""
            api_root.quit()
        
        # Create a button frame
        button_frame = tk.Frame(api_root)
        button_frame.pack(pady=(0, 20))
        
        # Add Cancel and Save buttons
        tk.Button(button_frame, text="Cancel", command=on_cancel).pack(side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="Save and Continue", command=validate_and_save).pack(side=tk.LEFT, padx=10)
        
        # Center the window
        api_root.update_idletasks()
        width = api_root.winfo_width()
        height = api_root.winfo_height()
        x = (api_root.winfo_screenwidth() // 2) - (width // 2)
        y = (api_root.winfo_screenheight() // 2) - (height // 2)
        api_root.geometry(f'{width}x{height}+{x}+{y}')
        
        api_root.protocol("WM_DELETE_WINDOW", on_cancel)
        api_root.mainloop()
        
        # Important: destroy the window only after mainloop exits
        api_root.destroy()
        return should_continue[0]


def check_api_keys() -> bool:
    """Convenience function to check and collect API keys.
    
    Returns:
        bool: True if the app should continue, False if it should exit
    """
    api_manager = APIKeyManager()
    return api_manager.check_env_file()