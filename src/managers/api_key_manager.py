"""
API Key Manager Module

Handles API key collection and validation through a GUI dialog.
Manages the creation of .env files with user-provided API keys.
"""

import sys
import tkinter as tk
from pathlib import Path
from managers.data_folder_manager import data_folder_manager


class APIKeyManager:
    """Manages API key collection and validation."""
    
    def __init__(self):
        """Initialize the API key manager."""
        self.env_path = data_folder_manager.env_file_path
    
    def check_env_file(self) -> bool:
        """Check if .env file exists and create it if needed.
        
        Returns:
            bool: True if the app should continue, False if it should exit
        """
        # If .env file exists, just return True to continue
        if self.env_path.exists():
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
        api_root.geometry("500x600")
        should_continue = [False]  # Use list for mutable reference
        
        # Headers
        tk.Label(api_root, text="Welcome to Medical Dictation App!", 
                font=("Segoe UI", 14, "bold")).pack(pady=(20, 5))
        
        tk.Label(api_root, text="Please enter at least one of the following API keys to continue:",
                font=("Segoe UI", 11)).pack(pady=(0, 5))
        
        tk.Label(api_root, text="OpenAI, Grok, Perplexity, or Anthropic API key is required. Either Deepgram, ElevenLabs, or GROQ API key is mandatory for speech recognition.",
                wraplength=450).pack(pady=(0, 20))
        
        # Create frame for keys
        keys_frame = tk.Frame(api_root)
        keys_frame.pack(fill="both", expand=True, padx=20)
        
        # Create entries for mandatory API keys first
        tk.Label(keys_frame, text="OpenAI API Key:").grid(row=0, column=0, sticky="w", pady=5)
        openai_entry = tk.Entry(keys_frame, width=40)
        openai_entry.grid(row=0, column=1, sticky="ew", pady=5)
        
        tk.Label(keys_frame, text="Grok API Key:").grid(row=1, column=0, sticky="w", pady=5)
        grok_entry = tk.Entry(keys_frame, width=40)
        grok_entry.grid(row=1, column=1, sticky="ew", pady=5)
        
        tk.Label(keys_frame, text="Perplexity API Key:").grid(row=2, column=0, sticky="w", pady=5)
        perplexity_entry = tk.Entry(keys_frame, width=40)
        perplexity_entry.grid(row=2, column=1, sticky="ew", pady=5)
        
        tk.Label(keys_frame, text="Anthropic API Key:").grid(row=3, column=0, sticky="w", pady=5)
        anthropic_entry = tk.Entry(keys_frame, width=40)
        anthropic_entry.grid(row=3, column=1, sticky="ew", pady=5)
        
        # Create entry for optional API key last
        tk.Label(keys_frame, text="Deepgram API Key:").grid(row=4, column=0, sticky="w", pady=5)
        deepgram_entry = tk.Entry(keys_frame, width=40)
        deepgram_entry.grid(row=4, column=1, sticky="ew", pady=5)
        
        # NEW: Add ElevenLabs API Key field
        tk.Label(keys_frame, text="ElevenLabs API Key:").grid(row=5, column=0, sticky="w", pady=5)
        elevenlabs_entry = tk.Entry(keys_frame, width=40)
        elevenlabs_entry.grid(row=5, column=1, sticky="ew", pady=5)
        
        # NEW: Add GROQ API Key field
        tk.Label(keys_frame, text="GROQ API Key:").grid(row=6, column=0, sticky="w", pady=5)
        groq_entry = tk.Entry(keys_frame, width=40)
        groq_entry.grid(row=6, column=1, sticky="ew", pady=5)
        
        # Add info about where to find the keys
        info_text = ("Get your API keys at:\n"
                    "• OpenAI: https://platform.openai.com/account/api-keys\n"
                    "• Grok (X.AI): https://x.ai\n"
                    "• Perplexity: https://docs.perplexity.ai/\n"
                    "• Anthropic: https://console.anthropic.com/account/keys\n"
                    "• Deepgram: https://console.deepgram.com/signup\n"
                    "• ElevenLabs: https://elevenlabs.io/app/speech-to-text\n"
                    "• GROQ: https://groq.com/")
        tk.Label(keys_frame, text=info_text, justify="left", wraplength=450).grid(
            row=7, column=0, columnspan=2, sticky="w", pady=10)
        
        error_var = tk.StringVar()
        error_label = tk.Label(api_root, textvariable=error_var, foreground="red", wraplength=450)
        error_label.pack(pady=5)
        
        def validate_and_save():
            """Validate API keys and save to .env file."""
            openai_key = openai_entry.get().strip()
            deepgram_key = deepgram_entry.get().strip()
            grok_key = grok_entry.get().strip()
            perplexity_key = perplexity_entry.get().strip()
            anthropic_key = anthropic_entry.get().strip()  # NEW: Get Anthropic key
            elevenlabs_key = elevenlabs_entry.get().strip()  # NEW: Get ElevenLabs key
            groq_key = groq_entry.get().strip()  # NEW: Get GROQ key
            
            # Check if at least one of OpenAI, Grok, Perplexity, or Anthropic keys is provided
            if not (openai_key or grok_key or perplexity_key or anthropic_key):
                error_var.set("Error: At least one of OpenAI, Grok, Perplexity, or Anthropic API keys is required.")
                return
                
            # Check if at least one speech-to-text API key is provided
            if not (deepgram_key or elevenlabs_key or groq_key):
                error_var.set("Error: Either Deepgram, ElevenLabs, or GROQ API key is mandatory for speech recognition.")
                return
            
            # Create the .env file with the provided keys
            with open(".env", "w") as f:
                if openai_key:
                    f.write(f"OPENAI_API_KEY={openai_key}\n")
                if deepgram_key:
                    f.write(f"DEEPGRAM_API_KEY={deepgram_key}\n")
                if grok_key:
                    f.write(f"GROK_API_KEY={grok_key}\n")
                if perplexity_key:
                    f.write(f"PERPLEXITY_API_KEY={perplexity_key}\n")
                if anthropic_key:
                    f.write(f"ANTHROPIC_API_KEY={anthropic_key}\n")
                # NEW: Add ElevenLabs key if provided
                if elevenlabs_key:
                    f.write(f"ELEVENLABS_API_KEY={elevenlabs_key}\n")
                # NEW: Add GROQ key if provided
                if groq_key:
                    f.write(f"GROQ_API_KEY={groq_key}\n")
                f.write(f"RECOGNITION_LANGUAGE=en-US\n")
            
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