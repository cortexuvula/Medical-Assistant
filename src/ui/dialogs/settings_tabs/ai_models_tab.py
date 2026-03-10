"""
AI Models tab mixin for UnifiedSettingsDialog.

Provides the _create_ai_models_tab and its sub-tab methods.
"""

from __future__ import annotations

import tkinter as tk
import ttkbootstrap as ttk

from ui.tooltip import ToolTip
from settings.settings_manager import settings_manager
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class AiModelsTabMixin:
    """Mixin providing the AI Models tab for UnifiedSettingsDialog.

    Expects the host class to provide:
        - self.notebook: ttk.Notebook
        - self.widgets: Dict[str, Dict]
    """

    def _create_ai_models_tab(self):
        """Create AI Models tab with nested notebook."""
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text=self.TAB_AI_MODELS)

        # Create nested notebook
        sub_notebook = ttk.Notebook(tab)
        sub_notebook.pack(fill="both", expand=True)
        self._ai_models_notebook = sub_notebook

        self.widgets['ai_models'] = {}

        # Temperature sub-tab
        self._create_temperature_subtab(sub_notebook)

        # Translation sub-tab
        self._create_translation_subtab(sub_notebook)

        # Note about agent settings
        note_frame = ttk.Frame(tab)
        note_frame.pack(fill="x", pady=(10, 0))
        ttk.Label(note_frame,
                 text="For detailed Agent Settings, use Settings \u2192 AI & Models \u2192 Agent Settings",
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
        current_temp = settings_manager.get("temperature", 0.7)

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
            "\u2022 0.0 = Most focused and deterministic\n"
            "\u2022 0.7 = Balanced creativity and consistency (recommended)\n"
            "\u2022 1.0 = More creative and varied\n"
            "\u2022 2.0 = Maximum randomness",
            justify=tk.LEFT, foreground="gray")
        explanation.grid(row=2, column=0, columnspan=2, sticky="w", pady=(15, 10))

        frame.columnconfigure(0, weight=1)

    def _create_translation_subtab(self, parent_notebook: ttk.Notebook):
        """Create Translation settings sub-tab."""
        frame = ttk.Frame(parent_notebook, padding=15)
        parent_notebook.add(frame, text="Translation")

        translation_settings = settings_manager.get("translation", {})
        defaults = settings_manager.get_default("translation", {})

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
