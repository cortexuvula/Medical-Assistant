"""
Audio & STT tab mixin for UnifiedSettingsDialog.

Provides the _create_audio_stt_tab and its sub-tab methods.
"""

from __future__ import annotations

import tkinter as tk
import ttkbootstrap as ttk

from ui.tooltip import ToolTip
from settings.settings_manager import settings_manager
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class AudioSttTabMixin:
    """Mixin providing the Audio & STT tab for UnifiedSettingsDialog.

    Expects the host class to provide:
        - self.notebook: ttk.Notebook
        - self.widgets: Dict[str, Dict]
    """

    def _create_audio_stt_tab(self):
        """Create Audio & STT tab with nested notebook."""
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text=self.TAB_AUDIO_STT)

        # Create nested notebook for sub-sections
        sub_notebook = ttk.Notebook(tab)
        sub_notebook.pack(fill="both", expand=True)
        self._audio_stt_notebook = sub_notebook

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

        elevenlabs_settings = settings_manager.get("elevenlabs", {})
        defaults = settings_manager.get_default("elevenlabs", {})

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
        row += 1

        # --- Diarization section separator ---
        sep_label = ttk.Label(frame, text="Diarization (Speaker Detection)", font=("", 10, "bold"))
        sep_label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(15, 5))
        row += 1

        # Diarize checkbox
        diarize_label = ttk.Label(frame, text="Enable Diarization:")
        diarize_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(diarize_label, "Detect and label different speakers in the transcript")
        diarize_var = tk.BooleanVar(value=elevenlabs_settings.get("diarize", defaults.get("diarize", True)))
        self.widgets['audio_stt']['elevenlabs']['diarize'] = diarize_var
        diarize_check = ttk.Checkbutton(frame, variable=diarize_var)
        diarize_check.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)
        ToolTip(diarize_check, "When enabled, the transcript will include Speaker 1, Speaker 2, etc.")
        row += 1

        # Number of Speakers
        num_speakers_label = ttk.Label(frame, text="Number of Speakers:")
        num_speakers_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(num_speakers_label, "Expected number of speakers (leave empty for auto-detection)")
        current_num_speakers = elevenlabs_settings.get("num_speakers", defaults.get("num_speakers", None))
        num_speakers_var = tk.StringVar(value=str(current_num_speakers) if current_num_speakers is not None else "")
        self.widgets['audio_stt']['elevenlabs']['num_speakers'] = num_speakers_var
        num_speakers_entry = ttk.Entry(frame, textvariable=num_speakers_var, width=10)
        num_speakers_entry.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)
        ToolTip(num_speakers_entry, "Leave empty for auto-detection (recommended). Set 2 for doctor-patient consultations.")
        row += 1

        # Diarization Threshold
        threshold_label = ttk.Label(frame, text="Diarization Threshold:")
        threshold_label.grid(row=row, column=0, sticky="w", pady=10)
        ToolTip(threshold_label, "Sensitivity for speaker separation (0.0-1.0, lower = more sensitive)")
        current_threshold = elevenlabs_settings.get("diarization_threshold", defaults.get("diarization_threshold", None))
        threshold_var = tk.StringVar(value=str(current_threshold) if current_threshold is not None else "")
        self.widgets['audio_stt']['elevenlabs']['diarization_threshold'] = threshold_var
        threshold_entry = ttk.Entry(frame, textvariable=threshold_var, width=10)
        threshold_entry.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=10)
        ToolTip(threshold_entry, "0.0-1.0. Lower values detect more speakers. Leave empty to use API default. Try 0.3 for medical consultations.")

        frame.columnconfigure(1, weight=1)

    def _create_deepgram_subtab(self, parent_notebook: ttk.Notebook):
        """Create Deepgram settings sub-tab."""
        frame = ttk.Frame(parent_notebook, padding=15)
        parent_notebook.add(frame, text="Deepgram")

        deepgram_settings = settings_manager.get("deepgram", {})
        defaults = settings_manager.get_default("deepgram", {})

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

        groq_settings = settings_manager.get("groq", {})
        defaults = settings_manager.get_default("groq", {})

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

        tts_settings = settings_manager.get("tts", {})
        defaults = settings_manager.get_default("tts", {})

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
