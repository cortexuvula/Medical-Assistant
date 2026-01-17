"""
API Keys Dialog Module

Dialog for viewing and updating API keys for all providers.
"""

import os
import tkinter as tk
from utils.structured_logging import get_logger

logger = get_logger(__name__)
from tkinter import messagebox
import ttkbootstrap as ttk

from ui.dialogs.dialog_utils import create_toplevel_dialog
from ui.dialogs.audio_settings import test_ollama_connection


def show_api_keys_dialog(parent: tk.Tk) -> dict:
    """Shows a dialog to update API keys and updates the .env file.

    Returns:
        dict: Updated API keys or None if cancelled
    """
    dialog = create_toplevel_dialog(parent, "Update API Keys", "900x1100")
    result = {"keys": None}  # Store result in mutable object

    # Increase main frame padding for more spacing around all content
    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

    # Add a header section with explanation
    header_frame = ttk.Frame(frame)
    header_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 30))

    ttk.Label(header_frame, text="API Key Configuration",
             font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 15))

    # Get current API keys from secure storage first, then fall back to environment
    from utils.security import get_security_manager
    security_mgr = get_security_manager()

    openai_key = security_mgr.get_api_key("openai") or os.getenv("OPENAI_API_KEY", "")
    deepgram_key = security_mgr.get_api_key("deepgram") or os.getenv("DEEPGRAM_API_KEY", "")
    elevenlabs_key = security_mgr.get_api_key("elevenlabs") or os.getenv("ELEVENLABS_API_KEY", "")
    ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")  # Default Ollama URL
    groq_key = security_mgr.get_api_key("groq") or os.getenv("GROQ_API_KEY", "")
    anthropic_key = security_mgr.get_api_key("anthropic") or os.getenv("ANTHROPIC_API_KEY", "")
    gemini_key = security_mgr.get_api_key("gemini") or os.getenv("GEMINI_API_KEY", "")

    # Create entry fields with password masking - add more vertical spacing
    row_offset = 1  # Start at row 1 since header is at row 0

    ttk.Label(frame, text="OpenAI API Key:").grid(row=row_offset, column=0, sticky="w", pady=15)
    openai_entry = ttk.Entry(frame, width=50, show="•")
    openai_entry.grid(row=row_offset, column=1, sticky="ew", padx=(10, 5), pady=15)
    openai_entry.insert(0, openai_key)
    row_offset += 1

    ttk.Label(frame, text="Anthropic API Key:").grid(row=row_offset, column=0, sticky="w", pady=15)
    anthropic_entry = ttk.Entry(frame, width=50, show="•")
    anthropic_entry.grid(row=row_offset, column=1, sticky="ew", padx=(10, 5), pady=15)
    anthropic_entry.insert(0, anthropic_key)
    row_offset += 1

    ttk.Label(frame, text="Google Gemini API Key:").grid(row=row_offset, column=0, sticky="w", pady=15)
    gemini_entry = ttk.Entry(frame, width=50, show="•")
    gemini_entry.grid(row=row_offset, column=1, sticky="ew", padx=(10, 5), pady=15)
    gemini_entry.insert(0, gemini_key)
    row_offset += 1

    ttk.Label(frame, text="Ollama API URL:").grid(row=row_offset, column=0, sticky="w", pady=15)
    ollama_entry = ttk.Entry(frame, width=50)
    ollama_entry.grid(row=row_offset, column=1, sticky="ew", padx=(10, 5), pady=15)
    ollama_entry.insert(0, ollama_url)
    row_offset += 1

    # Add a "Test Connection" button for Ollama
    test_ollama_btn = ttk.Button(
        frame,
        text="Test Ollama Connection",
        command=lambda: test_ollama_connection(parent, ollama_entry.get())
    )
    test_ollama_btn.grid(row=row_offset, column=1, sticky="e", padx=(10, 5), pady=15)
    row_offset += 1

    # Add a separator and section title for STT APIs
    ttk.Separator(frame, orient="horizontal").grid(row=row_offset, column=0, columnspan=3, sticky="ew", pady=25)
    row_offset += 1

    stt_label = ttk.Label(frame, text="Speech-to-Text APIs (at least one required)", font=("Segoe UI", 12, "bold"))
    stt_label.grid(row=row_offset, column=0, columnspan=3, sticky="w", pady=(0, 15))
    row_offset += 1

    # Add Deepgram API Key field with special styling
    deepgram_label = ttk.Label(frame, text="Deepgram API Key:", bootstyle="warning")
    deepgram_label.grid(row=row_offset, column=0, sticky="w", pady=15)
    deepgram_entry = ttk.Entry(frame, width=50, show="•", bootstyle="warning")
    deepgram_entry.grid(row=row_offset, column=1, sticky="ew", padx=(10, 5), pady=15)
    deepgram_entry.insert(0, deepgram_key)
    row_offset += 1

    # Add ElevenLabs API Key field with special styling
    elevenlabs_label = ttk.Label(frame, text="ElevenLabs API Key:", bootstyle="warning")
    elevenlabs_label.grid(row=row_offset, column=0, sticky="w", pady=15)
    elevenlabs_entry = ttk.Entry(frame, width=50, show="•", bootstyle="warning")
    elevenlabs_entry.grid(row=row_offset, column=1, sticky="ew", padx=(10, 5), pady=15)
    elevenlabs_entry.insert(0, elevenlabs_key)
    row_offset += 1

    # Add GROQ API Key field
    groq_label = ttk.Label(frame, text="GROQ API Key:", bootstyle="danger")
    groq_label.grid(row=row_offset, column=0, sticky="w", pady=15)
    groq_entry = ttk.Entry(frame, width=50, show="•", bootstyle="danger")
    groq_entry.grid(row=row_offset, column=1, sticky="ew", padx=(10, 5), pady=15)
    groq_entry.insert(0, groq_key)
    row_offset += 1

    # Add toggle buttons to show/hide keys with dynamic row positioning
    def create_toggle_button(parent, entry, row, column=2, padx=5, pady=15):
        """Create a toggle button to show/hide password entries."""
        def toggle():
            current = entry['show']
            entry['show'] = '' if current else '•'

        return ttk.Button(parent, text="👁", width=3, command=toggle).grid(
            row=row, column=column, padx=padx, pady=pady
        )

    # Fixed eye button positions for LLM API keys
    create_toggle_button(frame, openai_entry, row=1)
    create_toggle_button(frame, anthropic_entry, row=2)
    create_toggle_button(frame, gemini_entry, row=3)
    # Ollama URL doesn't need a show/hide button as it's not a key

    # Calculate eye button positions for STT API keys based on deepgram's row
    deepgram_row = 8  # Based on the row_offset after separator and STT label
    create_toggle_button(frame, deepgram_entry, row=deepgram_row)
    create_toggle_button(frame, elevenlabs_entry, row=deepgram_row+1)
    create_toggle_button(frame, groq_entry, row=deepgram_row+2)

    # Error variable for validation messages
    error_var = tk.StringVar()
    error_label = ttk.Label(frame, textvariable=error_var, bootstyle="danger")
    error_label.grid(row=row_offset, column=0, columnspan=3, sticky="w", pady=15)
    row_offset += 1



    def update_api_keys():
        new_openai = openai_entry.get().strip()
        new_deepgram = deepgram_entry.get().strip()
        new_elevenlabs = elevenlabs_entry.get().strip()
        new_ollama_url = ollama_entry.get().strip()
        new_groq = groq_entry.get().strip()
        new_anthropic = anthropic_entry.get().strip()
        new_gemini = gemini_entry.get().strip()

        from utils.validation import validate_api_key

        # Validate API keys if provided
        validation_errors = []

        if new_openai:
            is_valid, error = validate_api_key("openai", new_openai)
            if not is_valid:
                validation_errors.append(f"OpenAI: {error}")

        if new_deepgram:
            is_valid, error = validate_api_key("deepgram", new_deepgram)
            if not is_valid:
                validation_errors.append(f"Deepgram: {error}")

        if new_elevenlabs:
            is_valid, error = validate_api_key("elevenlabs", new_elevenlabs)
            if not is_valid:
                validation_errors.append(f"ElevenLabs: {error}")

        if new_groq:
            is_valid, error = validate_api_key("groq", new_groq)
            if not is_valid:
                validation_errors.append(f"GROQ: {error}")

        if new_anthropic:
            is_valid, error = validate_api_key("anthropic", new_anthropic)
            if not is_valid:
                validation_errors.append(f"Anthropic: {error}")

        if new_gemini:
            is_valid, error = validate_api_key("gemini", new_gemini)
            if not is_valid:
                validation_errors.append(f"Gemini: {error}")

        if validation_errors:
            error_var.set("Validation errors:\n" + "\n".join(validation_errors))
            return

        # Check if at least one LLM provider is provided
        if not (new_openai or new_anthropic or new_gemini or new_ollama_url):
            error_var.set("Error: At least one LLM provider API key is required (OpenAI, Anthropic, Gemini, or Ollama).")
            return

        # Check if at least one STT provider (Groq, Deepgram, or ElevenLabs) is provided
        if not (new_groq or new_deepgram or new_elevenlabs):
            error_var.set("Error: At least one STT provider API key is required (Groq, Deepgram, or ElevenLabs).")
            return

        # Clear any error messages
        error_var.set("")

        # Update .env file
        try:
            # Use data_folder_manager to get the correct .env path
            from managers.data_folder_manager import data_folder_manager
            env_path = str(data_folder_manager.env_file_path)

            # Read existing content
            env_content = ""
            if os.path.exists(env_path):
                with open(env_path, "r") as f:
                    env_content = f.read()

            # Update or add each key
            env_lines = env_content.split("\n")
            updated_lines = []
            keys_updated = set()

            for line in env_lines:
                # Fix: Change startsWith to startswith (Python string method is lowercase)
                if line.strip() == "" or line.strip().startswith("#"):
                    updated_lines.append(line)
                    continue

                if "OPENAI_API_KEY=" in line:
                    updated_lines.append(f"OPENAI_API_KEY={new_openai}")
                    keys_updated.add("OPENAI_API_KEY")
                elif "DEEPGRAM_API_KEY=" in line:
                    updated_lines.append(f"DEEPGRAM_API_KEY={new_deepgram}")
                    keys_updated.add("DEEPGRAM_API_KEY")
                elif "ELEVENLABS_API_KEY=" in line:
                    updated_lines.append(f"ELEVENLABS_API_KEY={new_elevenlabs}")
                    keys_updated.add("ELEVENLABS_API_KEY")
                elif "OLLAMA_API_URL=" in line:
                    updated_lines.append(f"OLLAMA_API_URL={new_ollama_url}")
                    keys_updated.add("OLLAMA_API_URL")
                elif "ANTHROPIC_API_KEY=" in line:
                    updated_lines.append(f"ANTHROPIC_API_KEY={new_anthropic}")
                    keys_updated.add("ANTHROPIC_API_KEY")
                elif "GEMINI_API_KEY=" in line:
                    updated_lines.append(f"GEMINI_API_KEY={new_gemini}")
                    keys_updated.add("GEMINI_API_KEY")
                else:
                    updated_lines.append(line)

            # Add keys that weren't in the file
            if "OPENAI_API_KEY" not in keys_updated and new_openai:
                updated_lines.append(f"OPENAI_API_KEY={new_openai}")
            if "DEEPGRAM_API_KEY" not in keys_updated and new_deepgram:
                updated_lines.append(f"DEEPGRAM_API_KEY={new_deepgram}")
            if "ELEVENLABS_API_KEY" not in keys_updated and new_elevenlabs:
                updated_lines.append(f"ELEVENLABS_API_KEY={new_elevenlabs}")
            if "OLLAMA_API_URL" not in keys_updated and new_ollama_url:
                updated_lines.append(f"OLLAMA_API_URL={new_ollama_url}")
            if "GROQ_API_KEY" not in keys_updated and new_groq:
                updated_lines.append(f"GROQ_API_KEY={new_groq}")
            if "ANTHROPIC_API_KEY" not in keys_updated and new_anthropic:
                updated_lines.append(f"ANTHROPIC_API_KEY={new_anthropic}")
            if "GEMINI_API_KEY" not in keys_updated and new_gemini:
                updated_lines.append(f"GEMINI_API_KEY={new_gemini}")

            # Make sure we have the RECOGNITION_LANGUAGE line
            if not any("RECOGNITION_LANGUAGE=" in line for line in updated_lines):
                updated_lines.append("RECOGNITION_LANGUAGE=en-US")

            # Write back to file
            with open(env_path, "w") as f:
                f.write("\n".join(updated_lines))

            # Store keys securely using encryption
            from utils.security import get_security_manager
            security_mgr = get_security_manager()

            # Store each key securely (this is the primary storage method)
            keys_to_store = {
                'openai': new_openai,
                'deepgram': new_deepgram,
                'elevenlabs': new_elevenlabs,
                'groq': new_groq,
                'anthropic': new_anthropic,
                'gemini': new_gemini,
            }

            for provider, key in keys_to_store.items():
                if key:
                    success, error = security_mgr.store_api_key(provider, key)
                    if not success:
                        logger.warning(f"Failed to store {provider} key securely: {error}")

            # Update environment variables in memory
            if new_openai:
                os.environ["OPENAI_API_KEY"] = new_openai
                # Note: Modern OpenAI provider uses client pattern that reads from env/security manager
            if new_deepgram:
                os.environ["DEEPGRAM_API_KEY"] = new_deepgram
            if new_elevenlabs:
                os.environ["ELEVENLABS_API_KEY"] = new_elevenlabs
            if new_ollama_url:
                os.environ["OLLAMA_API_URL"] = new_ollama_url
            if new_groq:
                os.environ["GROQ_API_KEY"] = new_groq
            if new_anthropic:
                os.environ["ANTHROPIC_API_KEY"] = new_anthropic
            if new_gemini:
                os.environ["GEMINI_API_KEY"] = new_gemini

            # Store results before showing message
            result["keys"] = {
                "openai": new_openai,
                "deepgram": new_deepgram,
                "elevenlabs": new_elevenlabs,
                "ollama_url": new_ollama_url,
                "groq": new_groq,
                "anthropic": new_anthropic,
                "gemini": new_gemini
            }

            # Success message and close dialog
            messagebox.showinfo("API Keys", "API keys updated successfully")
            dialog.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update API keys: {str(e)}")
            return None

    # Add more padding to the button frame
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(pady=30, padx=20)
    ttk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=15).pack(side="left", padx=20)
    ttk.Button(btn_frame, text="Update Keys", command=update_api_keys, bootstyle="success", width=15).pack(side="left", padx=20)

    # Wait for dialog to close
    dialog.wait_window()

    # Return the result
    return result.get("keys")


__all__ = ["show_api_keys_dialog"]
