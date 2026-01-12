"""
Unified Settings Dialog

A comprehensive tabbed settings dialog that consolidates all application
settings into a single, organized interface.
"""

import os
import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog
import ttkbootstrap as ttk
from typing import Dict, Optional, Callable

from ui.scaling_utils import ui_scaler
from ui.dialogs.dialog_utils import create_toplevel_dialog
from ui.tooltip import ToolTip
from settings.settings import SETTINGS, save_settings, _DEFAULT_SETTINGS


class UnifiedSettingsDialog:
    """Main unified settings dialog with tabbed interface."""

    TAB_API_KEYS = "API Keys"
    TAB_AUDIO_STT = "Audio & STT"
    TAB_AI_MODELS = "AI Models"
    TAB_PROMPTS = "Prompts"
    TAB_STORAGE = "Storage"
    TAB_GENERAL = "General"

    def __init__(self, parent):
        """Initialize the unified settings dialog.

        Args:
            parent: Parent window
        """
        self.parent = parent
        self.dialog: Optional[tk.Toplevel] = None
        self.notebook: Optional[ttk.Notebook] = None
        self.widgets: Dict[str, Dict] = {}
        self._modified = False

    def show(self, initial_tab: str = None):
        """Show the dialog, optionally selecting a specific tab.

        Args:
            initial_tab: Optional tab name to select initially
        """
        # Create dialog
        dialog_width, dialog_height = ui_scaler.get_dialog_size(900, 700)
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Preferences")
        self.dialog.geometry(f"{dialog_width}x{dialog_height}")
        self.dialog.minsize(800, 600)
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.update_idletasks()
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        x = (screen_width // 2) - (dialog_width // 2)
        y = (screen_height // 2) - (dialog_height // 2)
        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

        # Configure grid
        self.dialog.rowconfigure(0, weight=1)
        self.dialog.columnconfigure(0, weight=1)

        # Create main frame
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)

        # Create notebook
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew", pady=(0, 10))

        # Create tabs
        self._create_api_keys_tab()
        self._create_audio_stt_tab()
        self._create_ai_models_tab()
        self._create_prompts_tab()
        self._create_storage_tab()
        self._create_general_tab()

        # Create button frame
        self._create_buttons(main_frame)

        # Select initial tab if specified
        if initial_tab:
            tab_names = [self.TAB_API_KEYS, self.TAB_AUDIO_STT, self.TAB_AI_MODELS,
                        self.TAB_PROMPTS, self.TAB_STORAGE, self.TAB_GENERAL]
            if initial_tab in tab_names:
                self.notebook.select(tab_names.index(initial_tab))

        # Grab focus
        self.dialog.deiconify()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        self.parent.wait_window(self.dialog)

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
            ("grok", "Grok API Key:", "GROK_API_KEY", "API key from X.AI/Grok"),
            ("perplexity", "Perplexity API Key:", "PERPLEXITY_API_KEY", "API key from perplexity.ai"),
            ("anthropic", "Anthropic API Key:", "ANTHROPIC_API_KEY", "API key from console.anthropic.com"),
            ("gemini", "Google Gemini API Key:", "GEMINI_API_KEY", "API key from Google AI Studio"),
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

        entry = ttk.Entry(parent, textvariable=key_var, width=50, show="•")
        entry.grid(row=row, column=1, sticky="ew", padx=(10, 5), pady=10)
        if tooltip:
            ToolTip(entry, tooltip)

        # Toggle visibility button
        def toggle_visibility(e=entry):
            current = e['show']
            e['show'] = '' if current else '•'

        toggle_btn = ttk.Button(parent, text="👁", width=3, command=toggle_visibility)
        toggle_btn.grid(row=row, column=2, padx=5, pady=10)
        ToolTip(toggle_btn, "Show/hide API key")

        return row + 1

    def _create_audio_stt_tab(self):
        """Create Audio & STT tab with nested notebook."""
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text=self.TAB_AUDIO_STT)

        # Create nested notebook for sub-sections
        sub_notebook = ttk.Notebook(tab)
        sub_notebook.pack(fill="both", expand=True)

        self.widgets['audio_stt'] = {}

        # ElevenLabs sub-tab
        self._create_elevenlabs_subtab(sub_notebook)

        # Deepgram sub-tab
        self._create_deepgram_subtab(sub_notebook)

        # Groq sub-tab
        self._create_groq_subtab(sub_notebook)

        # TTS sub-tab
        self._create_tts_subtab(sub_notebook)

    def _create_elevenlabs_subtab(self, parent_notebook: ttk.Notebook):
        """Create ElevenLabs settings sub-tab."""
        frame = ttk.Frame(parent_notebook, padding=15)
        parent_notebook.add(frame, text="ElevenLabs")

        elevenlabs_settings = SETTINGS.get("elevenlabs", {})
        defaults = _DEFAULT_SETTINGS.get("elevenlabs", {})

        self.widgets['audio_stt']['elevenlabs'] = {}
        row = 0

        # Model
        model_label = ttk.Label(frame, text="Model:")
        model_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(model_label, "ElevenLabs speech-to-text model")
        model_var = tk.StringVar(value=elevenlabs_settings.get("model_id", defaults.get("model_id", "scribe_v2")))
        self.widgets['audio_stt']['elevenlabs']['model_id'] = model_var
        model_combo = ttk.Combobox(frame, textvariable=model_var, width=30,
                                   values=["scribe_v2", "scribe_v1", "scribe_v1_experimental"])
        model_combo.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)
        ToolTip(model_combo, "scribe_v2: 90+ languages, entity detection, keyterms")
        row += 1

        # Language
        lang_label = ttk.Label(frame, text="Language:")
        lang_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(lang_label, "ISO language code for transcription")
        lang_var = tk.StringVar(value=elevenlabs_settings.get("language_code", defaults.get("language_code", "en")))
        self.widgets['audio_stt']['elevenlabs']['language_code'] = lang_var
        lang_entry = ttk.Entry(frame, textvariable=lang_var, width=30)
        lang_entry.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)
        ToolTip(lang_entry, "ISO language code (e.g., 'en', 'es', 'fr')")
        row += 1

        # Tag Audio Events
        tag_label = ttk.Label(frame, text="Tag Audio Events:")
        tag_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(tag_label, "Detect and tag audio events like laughter, music, applause")
        tag_var = tk.BooleanVar(value=elevenlabs_settings.get("tag_audio_events", defaults.get("tag_audio_events", True)))
        self.widgets['audio_stt']['elevenlabs']['tag_audio_events'] = tag_var
        tag_check = ttk.Checkbutton(frame, variable=tag_var)
        tag_check.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)
        ToolTip(tag_check, "Enable to include audio event markers in transcript")
        row += 1

        # Entity Detection (scribe_v2 feature)
        entity_label = ttk.Label(frame, text="Entity Detection:")
        entity_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(entity_label, "Detect sensitive entities (scribe_v2 only)")

        entity_frame = ttk.Frame(frame)
        entity_frame.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)

        current_entities = elevenlabs_settings.get("entity_detection", defaults.get("entity_detection", []))
        phi_var = tk.BooleanVar(value="phi" in current_entities)
        pii_var = tk.BooleanVar(value="pii" in current_entities)
        pci_var = tk.BooleanVar(value="pci" in current_entities)
        offensive_var = tk.BooleanVar(value="offensive" in current_entities)

        self.widgets['audio_stt']['elevenlabs']['entity_phi'] = phi_var
        self.widgets['audio_stt']['elevenlabs']['entity_pii'] = pii_var
        self.widgets['audio_stt']['elevenlabs']['entity_pci'] = pci_var
        self.widgets['audio_stt']['elevenlabs']['entity_offensive'] = offensive_var

        ttk.Checkbutton(entity_frame, text="PHI", variable=phi_var).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(entity_frame, text="PII", variable=pii_var).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(entity_frame, text="PCI", variable=pci_var).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(entity_frame, text="Offensive", variable=offensive_var).pack(side=tk.LEFT)
        row += 1

        # Keyterms (scribe_v2 feature)
        keyterms_label = ttk.Label(frame, text="Keyterms:")
        keyterms_label.grid(row=row, column=0, sticky="nw", pady=10)
        ToolTip(keyterms_label, "Medical terms to bias recognition (comma-separated, up to 100)")
        current_keyterms = elevenlabs_settings.get("keyterms", defaults.get("keyterms", []))
        keyterms_var = tk.StringVar(value=", ".join(current_keyterms))
        self.widgets['audio_stt']['elevenlabs']['keyterms'] = keyterms_var
        keyterms_entry = ttk.Entry(frame, textvariable=keyterms_var, width=40)
        keyterms_entry.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)
        ToolTip(keyterms_entry, "Comma-separated medical terms (e.g., 'hypertension, metformin, COPD')")

        frame.columnconfigure(1, weight=1)

    def _create_deepgram_subtab(self, parent_notebook: ttk.Notebook):
        """Create Deepgram settings sub-tab."""
        frame = ttk.Frame(parent_notebook, padding=15)
        parent_notebook.add(frame, text="Deepgram")

        deepgram_settings = SETTINGS.get("deepgram", {})
        defaults = _DEFAULT_SETTINGS.get("deepgram", {})

        self.widgets['audio_stt']['deepgram'] = {}
        row = 0

        # Model
        model_label = ttk.Label(frame, text="Model:")
        model_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(model_label, "Deepgram speech recognition model")
        model_var = tk.StringVar(value=deepgram_settings.get("model", defaults.get("model", "nova-2-medical")))
        self.widgets['audio_stt']['deepgram']['model'] = model_var
        model_combo = ttk.Combobox(frame, textvariable=model_var, width=30,
                                   values=["nova-2-medical", "nova-2", "nova", "enhanced", "base"])
        model_combo.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)
        ToolTip(model_combo, "nova-2-medical is optimized for medical terminology")
        row += 1

        # Language
        lang_label = ttk.Label(frame, text="Language:")
        lang_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(lang_label, "Language code for transcription")
        lang_var = tk.StringVar(value=deepgram_settings.get("language", defaults.get("language", "en-US")))
        self.widgets['audio_stt']['deepgram']['language'] = lang_var
        lang_entry = ttk.Entry(frame, textvariable=lang_var, width=30)
        lang_entry.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)
        ToolTip(lang_entry, "Language code (e.g., 'en-US', 'es', 'fr')")
        row += 1

        # Smart Format
        smart_label = ttk.Label(frame, text="Smart Format:")
        smart_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(smart_label, "Auto-format numbers, dates, and punctuation")
        smart_var = tk.BooleanVar(value=deepgram_settings.get("smart_format", defaults.get("smart_format", True)))
        self.widgets['audio_stt']['deepgram']['smart_format'] = smart_var
        smart_check = ttk.Checkbutton(frame, variable=smart_var)
        smart_check.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)
        ToolTip(smart_check, "Automatically formats dates, times, numbers, and adds punctuation")
        row += 1

        # Diarize
        diarize_label = ttk.Label(frame, text="Speaker Diarization:")
        diarize_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(diarize_label, "Identify different speakers in audio")
        diarize_var = tk.BooleanVar(value=deepgram_settings.get("diarize", defaults.get("diarize", True)))
        self.widgets['audio_stt']['deepgram']['diarize'] = diarize_var
        diarize_check = ttk.Checkbutton(frame, variable=diarize_var)
        diarize_check.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)
        ToolTip(diarize_check, "Labels speakers as 'Speaker 0', 'Speaker 1', etc.")

        frame.columnconfigure(1, weight=1)

    def _create_groq_subtab(self, parent_notebook: ttk.Notebook):
        """Create Groq settings sub-tab."""
        frame = ttk.Frame(parent_notebook, padding=15)
        parent_notebook.add(frame, text="Groq")

        groq_settings = SETTINGS.get("groq", {})
        defaults = _DEFAULT_SETTINGS.get("groq", {})

        self.widgets['audio_stt']['groq'] = {}
        row = 0

        # Model
        model_label = ttk.Label(frame, text="Model:")
        model_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(model_label, "Groq Whisper model for ultra-fast transcription")
        model_var = tk.StringVar(value=groq_settings.get("model", defaults.get("model", "whisper-large-v3-turbo")))
        self.widgets['audio_stt']['groq']['model'] = model_var
        model_combo = ttk.Combobox(frame, textvariable=model_var, width=30,
                                   values=["whisper-large-v3-turbo", "whisper-large-v3", "distil-whisper-large-v3-en"])
        model_combo.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)
        ToolTip(model_combo, "turbo: fastest (216x real-time); v3: highest quality; distil-en: English-only")
        row += 1

        # Language
        lang_label = ttk.Label(frame, text="Language:")
        lang_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(lang_label, "Language code for transcription")
        lang_var = tk.StringVar(value=groq_settings.get("language", defaults.get("language", "en")))
        self.widgets['audio_stt']['groq']['language'] = lang_var
        lang_entry = ttk.Entry(frame, textvariable=lang_var, width=30)
        lang_entry.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)
        ToolTip(lang_entry, "ISO language code (e.g., 'en', 'es', 'fr')")

        frame.columnconfigure(1, weight=1)

    def _create_tts_subtab(self, parent_notebook: ttk.Notebook):
        """Create TTS settings sub-tab."""
        frame = ttk.Frame(parent_notebook, padding=15)
        parent_notebook.add(frame, text="TTS")

        tts_settings = SETTINGS.get("tts", {})
        defaults = _DEFAULT_SETTINGS.get("tts", {})

        self.widgets['audio_stt']['tts'] = {}
        row = 0

        # Provider
        provider_label = ttk.Label(frame, text="TTS Provider:")
        provider_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(provider_label, "Text-to-speech service provider")
        provider_var = tk.StringVar(value=tts_settings.get("provider", defaults.get("provider", "elevenlabs")))
        self.widgets['audio_stt']['tts']['provider'] = provider_var
        provider_combo = ttk.Combobox(frame, textvariable=provider_var, width=30,
                                      values=["elevenlabs", "system"])
        provider_combo.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)
        ToolTip(provider_combo, "elevenlabs: high-quality AI voices; system: OS built-in voices")
        row += 1

        # Model
        model_label = ttk.Label(frame, text="Model:")
        model_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(model_label, "ElevenLabs TTS model")
        model_var = tk.StringVar(value=tts_settings.get("model", defaults.get("model", "eleven_multilingual_v2")))
        self.widgets['audio_stt']['tts']['model'] = model_var
        model_combo = ttk.Combobox(frame, textvariable=model_var, width=30,
                                   values=["eleven_flash_v2_5", "eleven_turbo_v2_5", "eleven_multilingual_v2"])
        model_combo.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)
        ToolTip(model_combo, "flash: ultra-low latency; turbo: fast; multilingual: highest quality")
        row += 1

        # Voice ID
        voice_label = ttk.Label(frame, text="Voice ID:")
        voice_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(voice_label, "ElevenLabs voice identifier")
        voice_var = tk.StringVar(value=tts_settings.get("voice_id", defaults.get("voice_id", "")))
        self.widgets['audio_stt']['tts']['voice_id'] = voice_var
        voice_entry = ttk.Entry(frame, textvariable=voice_var, width=30)
        voice_entry.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)
        ToolTip(voice_entry, "ElevenLabs voice ID - use TTS Settings for voice browser")

        # Note about selecting voices
        ttk.Label(frame, text="Use TTS Settings from menu for voice selection dialog",
                 foreground="gray").grid(row=row+1, column=0, columnspan=2, sticky="w", pady=(0, 10))

        frame.columnconfigure(1, weight=1)

    def _create_ai_models_tab(self):
        """Create AI Models tab with nested notebook."""
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text=self.TAB_AI_MODELS)

        # Create nested notebook
        sub_notebook = ttk.Notebook(tab)
        sub_notebook.pack(fill="both", expand=True)

        self.widgets['ai_models'] = {}

        # Temperature sub-tab
        self._create_temperature_subtab(sub_notebook)

        # Translation sub-tab
        self._create_translation_subtab(sub_notebook)

        # Note about agent settings
        note_frame = ttk.Frame(tab)
        note_frame.pack(fill="x", pady=(10, 0))
        ttk.Label(note_frame,
                 text="For detailed Agent Settings, use Settings → AI & Models → Agent Settings",
                 foreground="gray").pack(anchor="w")

    def _create_temperature_subtab(self, parent_notebook: ttk.Notebook):
        """Create Temperature settings sub-tab."""
        frame = ttk.Frame(parent_notebook, padding=15)
        parent_notebook.add(frame, text="Temperature")

        self.widgets['ai_models']['temperature'] = {}

        header_label = ttk.Label(frame, text="Default AI Temperature:", font=("Segoe UI", 11, "bold"))
        header_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 15))
        ToolTip(header_label, "Controls randomness/creativity of AI responses")

        # Global temperature
        current_temp = SETTINGS.get("temperature", 0.7)

        temp_frame = ttk.Frame(frame)
        temp_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=10)

        temp_var = tk.DoubleVar(value=current_temp)
        self.widgets['ai_models']['temperature']['global'] = temp_var

        temp_label = ttk.Label(temp_frame, text=f"{current_temp:.1f}", width=5)
        temp_label.pack(side="right", padx=(10, 0))
        ToolTip(temp_label, "Current temperature value")

        def update_label(*args):
            temp_label.config(text=f"{temp_var.get():.1f}")

        temp_slider = ttk.Scale(temp_frame, from_=0.0, to=2.0,
                               orient=tk.HORIZONTAL, variable=temp_var,
                               command=lambda v: update_label())
        temp_slider.pack(side="left", fill="x", expand=True)
        ToolTip(temp_slider, "Drag to adjust temperature (0=deterministic, 2=maximum randomness)")

        # Explanation
        explanation = ttk.Label(frame, text=
            "Temperature controls the randomness of AI responses:\n"
            "• 0.0 = Most focused and deterministic\n"
            "• 0.7 = Balanced creativity and consistency (recommended)\n"
            "• 1.0 = More creative and varied\n"
            "• 2.0 = Maximum randomness",
            justify=tk.LEFT, foreground="gray")
        explanation.grid(row=2, column=0, columnspan=2, sticky="w", pady=(15, 10))

        frame.columnconfigure(0, weight=1)

    def _create_translation_subtab(self, parent_notebook: ttk.Notebook):
        """Create Translation settings sub-tab."""
        frame = ttk.Frame(parent_notebook, padding=15)
        parent_notebook.add(frame, text="Translation")

        translation_settings = SETTINGS.get("translation", {})
        defaults = _DEFAULT_SETTINGS.get("translation", {})

        self.widgets['ai_models']['translation'] = {}
        row = 0

        # Provider
        provider_label = ttk.Label(frame, text="Translation Provider:")
        provider_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(provider_label, "Service used for translations")
        provider_var = tk.StringVar(value=translation_settings.get("provider", defaults.get("provider", "google")))
        self.widgets['ai_models']['translation']['provider'] = provider_var
        provider_combo = ttk.Combobox(frame, textvariable=provider_var, width=30,
                                      values=["google", "deepl", "microsoft"])
        provider_combo.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)
        ToolTip(provider_combo, "google: free; deepl: higher quality; microsoft: enterprise")
        row += 1

        # Default patient language
        patient_label = ttk.Label(frame, text="Default Patient Language:")
        patient_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(patient_label, "Default language for patient communication")
        patient_lang_var = tk.StringVar(value=translation_settings.get("default_patient_language", "es"))
        self.widgets['ai_models']['translation']['default_patient_language'] = patient_lang_var
        patient_entry = ttk.Entry(frame, textvariable=patient_lang_var, width=30)
        patient_entry.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)
        ToolTip(patient_entry, "ISO language code (e.g., 'es' for Spanish, 'zh' for Chinese)")
        row += 1

        # Default doctor language
        doctor_label = ttk.Label(frame, text="Default Doctor Language:")
        doctor_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(doctor_label, "Default language for provider/doctor communication")
        doctor_lang_var = tk.StringVar(value=translation_settings.get("default_doctor_language", "en"))
        self.widgets['ai_models']['translation']['default_doctor_language'] = doctor_lang_var
        doctor_entry = ttk.Entry(frame, textvariable=doctor_lang_var, width=30)
        doctor_entry.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)
        ToolTip(doctor_entry, "ISO language code (e.g., 'en' for English)")

        frame.columnconfigure(1, weight=1)

    def _create_prompts_tab(self):
        """Create Prompts tab with edit buttons."""
        tab = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(tab, text=self.TAB_PROMPTS)

        ttk.Label(tab, text="Prompt Configuration",
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 15))

        ttk.Label(tab, text="Click 'Edit' to open the full prompt editor for each category:",
                 foreground="gray").pack(anchor="w", pady=(0, 15))

        # Create list of prompts with edit buttons
        prompts_config = [
            ("Refine Text Prompt", "show_refine_settings", "Edit prompt for refining/cleaning transcribed text"),
            ("Improve Text Prompt", "show_improve_settings", "Edit prompt for improving text quality and clarity"),
            ("SOAP Note Prompt", "show_soap_settings", "Edit prompt for generating SOAP clinical notes"),
            ("Referral Prompt", "show_referral_settings", "Edit prompt for generating referral letters"),
            ("Advanced Analysis Prompt", "show_advanced_analysis_settings", "Edit prompt for periodic differential diagnosis"),
        ]

        for label, method_name, tooltip_text in prompts_config:
            row_frame = ttk.Frame(tab)
            row_frame.pack(fill="x", pady=5)

            prompt_label = ttk.Label(row_frame, text=label, width=30)
            prompt_label.pack(side="left")
            ToolTip(prompt_label, tooltip_text)

            # Create edit button that calls parent method
            def make_callback(m=method_name):
                def callback():
                    if hasattr(self.parent, m):
                        self.dialog.destroy()
                        getattr(self.parent, m)()
                return callback

            edit_btn = ttk.Button(row_frame, text="Edit...", width=10, command=make_callback())
            edit_btn.pack(side="right", padx=5)
            ToolTip(edit_btn, f"Open {label.lower()} editor")

    def _create_storage_tab(self):
        """Create Storage tab content."""
        tab = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(tab, text=self.TAB_STORAGE)

        self.widgets['storage'] = {}
        row = 0

        # Storage folder
        ttk.Label(tab, text="Storage Settings",
                 font=("Segoe UI", 12, "bold")).grid(row=row, column=0, columnspan=3,
                                                      sticky="w", pady=(0, 15))
        row += 1

        folder_label = ttk.Label(tab, text="Default Storage Folder:")
        folder_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(folder_label, "Default folder for saving documents")
        folder_var = tk.StringVar(value=SETTINGS.get("default_folder", ""))
        self.widgets['storage']['default_folder'] = folder_var
        folder_entry = ttk.Entry(tab, textvariable=folder_var, width=50)
        folder_entry.grid(row=row, column=1, sticky="ew", padx=(10, 5), pady=10)
        ToolTip(folder_entry, "Path where documents will be saved by default")

        def browse_folder():
            folder = filedialog.askdirectory(initialdir=folder_var.get())
            if folder:
                folder_var.set(folder)

        browse_btn = ttk.Button(tab, text="Browse...", command=browse_folder)
        browse_btn.grid(row=row, column=2, padx=5, pady=10)
        ToolTip(browse_btn, "Browse to select a folder")
        row += 1

        # Separator
        ttk.Separator(tab, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=20)
        row += 1

        # Quick links section
        ttk.Label(tab, text="Quick Links",
                 font=("Segoe UI", 12, "bold")).grid(row=row, column=0, columnspan=3,
                                                      sticky="w", pady=(0, 15))
        row += 1

        links = [
            ("Custom Vocabulary...", "show_vocabulary_settings", "Manage custom word corrections and medical terminology"),
            ("Manage Address Book...", "manage_address_book", "Manage provider and facility contact information"),
            ("Record Prefix Audio...", "record_prefix_audio", "Record an audio prefix to be added to all recordings"),
        ]

        for label, method_name, tooltip_text in links:
            def make_callback(m=method_name):
                def callback():
                    if hasattr(self.parent, m):
                        self.dialog.destroy()
                        getattr(self.parent, m)()
                return callback

            btn = ttk.Button(tab, text=label, width=30, command=make_callback())
            btn.grid(row=row, column=0, columnspan=2, sticky="w", pady=5)
            ToolTip(btn, tooltip_text)
            row += 1

        tab.columnconfigure(1, weight=1)

    def _create_general_tab(self):
        """Create General tab content."""
        tab = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(tab, text=self.TAB_GENERAL)

        self.widgets['general'] = {}
        row = 0

        # General Settings header
        ttk.Label(tab, text="General Settings",
                 font=("Segoe UI", 12, "bold")).grid(row=row, column=0, columnspan=2,
                                                      sticky="w", pady=(0, 15))
        row += 1

        # Quick Continue Mode
        qc_label = ttk.Label(tab, text="Quick Continue Mode:")
        qc_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(qc_label, "Enable to start new recordings while previous ones process")
        quick_continue_var = tk.BooleanVar(value=SETTINGS.get("quick_continue_mode", False))
        self.widgets['general']['quick_continue_mode'] = quick_continue_var
        qc_check = ttk.Checkbutton(tab, variable=quick_continue_var)
        qc_check.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)
        ToolTip(qc_check, "Queue recordings for background processing while starting new ones")
        ttk.Label(tab, text="Queue recordings for background processing while starting new ones",
                 foreground="gray").grid(row=row+1, column=0, columnspan=2, sticky="w", padx=(20, 0))
        row += 2

        # Theme
        theme_label = ttk.Label(tab, text="Theme:")
        theme_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(theme_label, "Application color theme")
        theme_var = tk.StringVar(value=SETTINGS.get("theme", "darkly"))
        self.widgets['general']['theme'] = theme_var
        theme_combo = ttk.Combobox(tab, textvariable=theme_var, width=20,
                                   values=["darkly", "solar", "cyborg", "superhero", "vapor",
                                          "flatly", "litera", "minty", "pulse", "sandstone"])
        theme_combo.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)
        ToolTip(theme_combo, "Dark themes: darkly, solar, cyborg, superhero; Light themes: flatly, litera, minty, pulse")
        row += 1

        # Sidebar collapsed
        sidebar_label = ttk.Label(tab, text="Sidebar Collapsed:")
        sidebar_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(sidebar_label, "Start with sidebar collapsed")
        sidebar_var = tk.BooleanVar(value=SETTINGS.get("sidebar_collapsed", False))
        self.widgets['general']['sidebar_collapsed'] = sidebar_var
        sidebar_check = ttk.Checkbutton(tab, variable=sidebar_var)
        sidebar_check.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)
        ToolTip(sidebar_check, "Start with navigation sidebar collapsed (can toggle with button)")
        row += 1

        # Separator
        ttk.Separator(tab, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=20)
        row += 1

        # Keyboard shortcuts info
        ttk.Label(tab, text="Keyboard Shortcuts",
                 font=("Segoe UI", 12, "bold")).grid(row=row, column=0, columnspan=2,
                                                      sticky="w", pady=(0, 10))
        row += 1

        shortcuts = [
            ("Ctrl+,", "Open Preferences"),
            ("Alt+T", "Toggle Theme"),
            ("Ctrl+N", "New Session"),
            ("Ctrl+S", "Save"),
            ("F5", "Start/Stop Recording"),
            ("Ctrl+/", "Focus Chat Input"),
        ]

        for key, desc in shortcuts:
            shortcut_frame = ttk.Frame(tab)
            shortcut_frame.grid(row=row, column=0, columnspan=2, sticky="w", pady=2)
            ttk.Label(shortcut_frame, text=key, font=("Consolas", 10), width=10).pack(side="left")
            ttk.Label(shortcut_frame, text=desc, foreground="gray").pack(side="left", padx=(10, 0))
            row += 1

        tab.columnconfigure(1, weight=1)

    def _create_buttons(self, parent):
        """Create save/cancel/reset buttons."""
        btn_frame = ttk.Frame(parent)
        btn_frame.grid(row=1, column=0, sticky="e", pady=(10, 0))

        reset_btn = ttk.Button(btn_frame, text="Reset Defaults", command=self._reset_to_defaults)
        reset_btn.pack(side=tk.LEFT, padx=5)
        ToolTip(reset_btn, "Reset all settings to their default values")

        cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy)
        cancel_btn.pack(side=tk.RIGHT, padx=5)
        ToolTip(cancel_btn, "Discard changes and close")

        save_btn = ttk.Button(btn_frame, text="Save", command=self._save_all_settings, bootstyle="success")
        save_btn.pack(side=tk.RIGHT, padx=5)
        ToolTip(save_btn, "Save all settings and close")

    def _save_all_settings(self):
        """Save all settings from all tabs."""
        try:
            # Save API Keys
            from utils.security import get_security_manager
            security_mgr = get_security_manager()

            api_keys = self.widgets.get('api_keys', {})
            for key_id in ['openai', 'grok', 'perplexity', 'anthropic', 'gemini',
                          'deepgram', 'elevenlabs', 'groq']:
                if key_id in api_keys:
                    value = api_keys[key_id].get().strip()
                    if value:
                        security_mgr.store_api_key(key_id, value)

            # Save Ollama URL to environment
            if 'ollama_url' in api_keys:
                os.environ["OLLAMA_API_URL"] = api_keys['ollama_url'].get().strip()

            # Save Audio/STT settings
            audio_stt = self.widgets.get('audio_stt', {})

            if 'elevenlabs' in audio_stt:
                SETTINGS.setdefault('elevenlabs', {})
                el_widgets = audio_stt['elevenlabs']

                # Handle entity detection checkboxes -> array
                entity_detection = []
                if el_widgets.get('entity_phi', tk.BooleanVar()).get():
                    entity_detection.append('phi')
                if el_widgets.get('entity_pii', tk.BooleanVar()).get():
                    entity_detection.append('pii')
                if el_widgets.get('entity_pci', tk.BooleanVar()).get():
                    entity_detection.append('pci')
                if el_widgets.get('entity_offensive', tk.BooleanVar()).get():
                    entity_detection.append('offensive')
                SETTINGS['elevenlabs']['entity_detection'] = entity_detection

                # Handle keyterms string -> array
                keyterms_str = el_widgets.get('keyterms', tk.StringVar()).get()
                keyterms = [t.strip() for t in keyterms_str.split(',') if t.strip()]
                SETTINGS['elevenlabs']['keyterms'] = keyterms[:100]  # Limit to 100

                # Handle regular settings
                for key, var in el_widgets.items():
                    if key.startswith('entity_') or key == 'keyterms':
                        continue  # Already handled above
                    SETTINGS['elevenlabs'][key] = var.get()

            if 'deepgram' in audio_stt:
                SETTINGS.setdefault('deepgram', {})
                for key, var in audio_stt['deepgram'].items():
                    SETTINGS['deepgram'][key] = var.get()

            if 'groq' in audio_stt:
                SETTINGS.setdefault('groq', {})
                for key, var in audio_stt['groq'].items():
                    SETTINGS['groq'][key] = var.get()

            if 'tts' in audio_stt:
                SETTINGS.setdefault('tts', {})
                for key, var in audio_stt['tts'].items():
                    SETTINGS['tts'][key] = var.get()

            # Save AI Models settings
            ai_models = self.widgets.get('ai_models', {})

            if 'temperature' in ai_models and 'global' in ai_models['temperature']:
                SETTINGS['temperature'] = ai_models['temperature']['global'].get()

            if 'translation' in ai_models:
                SETTINGS.setdefault('translation', {})
                for key, var in ai_models['translation'].items():
                    SETTINGS['translation'][key] = var.get()

            # Save Storage settings
            storage = self.widgets.get('storage', {})
            if 'default_folder' in storage:
                SETTINGS['default_folder'] = storage['default_folder'].get()

            # Save General settings
            general = self.widgets.get('general', {})
            if 'quick_continue_mode' in general:
                SETTINGS['quick_continue_mode'] = general['quick_continue_mode'].get()
            if 'theme' in general:
                SETTINGS['theme'] = general['theme'].get()
            if 'sidebar_collapsed' in general:
                SETTINGS['sidebar_collapsed'] = general['sidebar_collapsed'].get()

            # Persist settings
            save_settings(SETTINGS)

            messagebox.showinfo("Settings Saved", "All settings have been saved successfully.")
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {str(e)}")

    def _reset_to_defaults(self):
        """Reset all settings to defaults."""
        if not messagebox.askyesno("Reset Settings",
                                   "Are you sure you want to reset all settings to defaults?"):
            return

        # Reset Audio/STT
        audio_stt = self.widgets.get('audio_stt', {})

        if 'elevenlabs' in audio_stt:
            defaults = _DEFAULT_SETTINGS.get('elevenlabs', {})
            el_widgets = audio_stt['elevenlabs']

            # Reset entity detection checkboxes
            default_entities = defaults.get('entity_detection', [])
            if 'entity_phi' in el_widgets:
                el_widgets['entity_phi'].set('phi' in default_entities)
            if 'entity_pii' in el_widgets:
                el_widgets['entity_pii'].set('pii' in default_entities)
            if 'entity_pci' in el_widgets:
                el_widgets['entity_pci'].set('pci' in default_entities)
            if 'entity_offensive' in el_widgets:
                el_widgets['entity_offensive'].set('offensive' in default_entities)

            # Reset keyterms
            if 'keyterms' in el_widgets:
                default_keyterms = defaults.get('keyterms', [])
                el_widgets['keyterms'].set(', '.join(default_keyterms))

            # Reset regular settings
            for key, var in el_widgets.items():
                if key.startswith('entity_') or key == 'keyterms':
                    continue  # Already handled above
                if key in defaults:
                    var.set(defaults[key])

        if 'deepgram' in audio_stt:
            defaults = _DEFAULT_SETTINGS.get('deepgram', {})
            for key, var in audio_stt['deepgram'].items():
                if key in defaults:
                    var.set(defaults[key])

        if 'groq' in audio_stt:
            defaults = _DEFAULT_SETTINGS.get('groq', {})
            for key, var in audio_stt['groq'].items():
                if key in defaults:
                    var.set(defaults[key])

        if 'tts' in audio_stt:
            defaults = _DEFAULT_SETTINGS.get('tts', {})
            for key, var in audio_stt['tts'].items():
                if key in defaults:
                    var.set(defaults[key])

        # Reset AI Models
        ai_models = self.widgets.get('ai_models', {})
        if 'temperature' in ai_models and 'global' in ai_models['temperature']:
            ai_models['temperature']['global'].set(0.7)

        if 'translation' in ai_models:
            defaults = _DEFAULT_SETTINGS.get('translation', {})
            for key, var in ai_models['translation'].items():
                if key in defaults:
                    var.set(defaults[key])

        # Reset General
        general = self.widgets.get('general', {})
        if 'quick_continue_mode' in general:
            general['quick_continue_mode'].set(False)
        if 'theme' in general:
            general['theme'].set('darkly')
        if 'sidebar_collapsed' in general:
            general['sidebar_collapsed'].set(False)

        messagebox.showinfo("Reset Complete", "Settings have been reset to defaults.\n"
                           "Click Save to apply changes.")


def show_unified_settings_dialog(parent, initial_tab: str = None):
    """Show the unified settings dialog.

    Args:
        parent: Parent window
        initial_tab: Optional tab name to select initially
            (use UnifiedSettingsDialog.TAB_* constants)
    """
    dialog = UnifiedSettingsDialog(parent)
    dialog.show(initial_tab)
