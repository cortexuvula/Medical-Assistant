"""
API Keys tab mixin for UnifiedSettingsDialog.

Provides the _create_api_keys_tab and _create_api_key_row methods.
"""

from __future__ import annotations

import os
import tkinter as tk
import ttkbootstrap as ttk

from ui.tooltip import ToolTip
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class ApiKeysTabMixin:
    """Mixin providing the API Keys tab for UnifiedSettingsDialog.

    Expects the host class to provide:
        - self.notebook: ttk.Notebook
        - self.widgets: Dict[str, Dict]
        - self.parent: Parent window
    """

    def _create_api_keys_tab(self):
        """Create API Keys tab content."""
        tab = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(tab, text=self.TAB_API_KEYS)

        # Create scrollable canvas for many fields
        canvas = tk.Canvas(tab, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind mousewheel
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self.widgets['api_keys'] = {}

        # Get current keys from secure storage
        from utils.security import get_security_manager
        security_mgr = get_security_manager()

        # LLM API Keys section
        ttk.Label(scrollable_frame, text="LLM Provider API Keys",
                 font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=3,
                                                      sticky="w", pady=(0, 15))

        row = 1
        api_keys_config = [
            ("openai", "OpenAI API Key:", "OPENAI_API_KEY", "API key from platform.openai.com"),
            ("anthropic", "Anthropic API Key:", "ANTHROPIC_API_KEY", "API key from console.anthropic.com"),
            ("gemini", "Google Gemini API Key:", "GEMINI_API_KEY", "API key from Google AI Studio"),
            ("cerebras", "Cerebras API Key:", "CEREBRAS_API_KEY", "API key from cloud.cerebras.ai - Ultra-fast inference (no HIPAA BAA)"),
        ]

        for key_id, label, env_var, tooltip in api_keys_config:
            current_value = security_mgr.get_api_key(key_id) or os.getenv(env_var, "")
            row = self._create_api_key_row(scrollable_frame, row, key_id, label, current_value, tooltip)

        # Ollama URL (not a secret)
        ollama_label = ttk.Label(scrollable_frame, text="Ollama API URL:")
        ollama_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(ollama_label, "URL for local Ollama server (default: http://localhost:11434)")

        ollama_var = tk.StringVar(value=os.getenv("OLLAMA_API_URL", "http://localhost:11434"))
        self.widgets['api_keys']['ollama_url'] = ollama_var
        ollama_entry = ttk.Entry(scrollable_frame, textvariable=ollama_var, width=50)
        ollama_entry.grid(row=row, column=1, sticky="ew", padx=(10, 5), pady=10)
        ToolTip(ollama_entry, "URL for local Ollama server (default: http://localhost:11434)")

        # Test Ollama button
        from ui.dialogs.audio_settings import test_ollama_connection
        test_btn = ttk.Button(scrollable_frame, text="Test", width=6,
                             command=lambda: test_ollama_connection(self.parent, ollama_var.get()))
        test_btn.grid(row=row, column=2, padx=5, pady=10)
        ToolTip(test_btn, "Test connection to Ollama server")
        row += 1

        # Separator
        ttk.Separator(scrollable_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=20)
        row += 1

        # STT API Keys section
        ttk.Label(scrollable_frame, text="Speech-to-Text API Keys",
                 font=("Segoe UI", 12, "bold")).grid(row=row, column=0, columnspan=3,
                                                      sticky="w", pady=(0, 15))
        row += 1

        stt_keys_config = [
            ("deepgram", "Deepgram API Key:", "DEEPGRAM_API_KEY", "API key for Deepgram speech-to-text (nova-2-medical model)"),
            ("elevenlabs", "ElevenLabs API Key:", "ELEVENLABS_API_KEY", "API key for ElevenLabs STT and TTS"),
            ("groq", "Groq API Key:", "GROQ_API_KEY", "API key for Groq ultra-fast Whisper transcription"),
        ]

        for key_id, label, env_var, tooltip in stt_keys_config:
            current_value = security_mgr.get_api_key(key_id) or os.getenv(env_var, "")
            row = self._create_api_key_row(scrollable_frame, row, key_id, label, current_value, tooltip)

        # Configure column weights
        scrollable_frame.columnconfigure(1, weight=1)

    def _create_api_key_row(self, parent, row: int, key_id: str, label: str,
                           current_value: str, tooltip: str = "") -> int:
        """Create a row for an API key with show/hide toggle.

        Args:
            parent: Parent frame
            row: Row number in grid
            key_id: Key identifier for widget storage
            label: Display label
            current_value: Current API key value
            tooltip: Optional tooltip text for the field

        Returns:
            Next row number
        """
        label_widget = ttk.Label(parent, text=label)
        label_widget.grid(row=row, column=0, sticky="w", pady=10)
        if tooltip:
            ToolTip(label_widget, tooltip)

        key_var = tk.StringVar(value=current_value)
        self.widgets['api_keys'][key_id] = key_var

        entry = ttk.Entry(parent, textvariable=key_var, width=50, show="\u2022")
        entry.grid(row=row, column=1, sticky="ew", padx=(10, 5), pady=10)
        if tooltip:
            ToolTip(entry, tooltip)

        # Toggle visibility button
        def toggle_visibility(e=entry):
            current = e['show']
            e['show'] = '' if current else '\u2022'

        toggle_btn = ttk.Button(parent, text="\U0001f441", width=3, command=toggle_visibility)
        toggle_btn.grid(row=row, column=2, padx=5, pady=10)
        ToolTip(toggle_btn, "Show/hide API key")

        return row + 1
