"""
Translation Languages Module

Provides language selection, presets, and swapping functionality.
"""

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import X, LEFT
import logging
from typing import TYPE_CHECKING, Dict, List, Tuple, Optional

from ui.tooltip import ToolTip
from settings.settings import SETTINGS

if TYPE_CHECKING:
    from managers.translation_manager import TranslationManager


class LanguagesMixin:
    """Mixin for language selection and management."""

    patient_language: str
    doctor_language: str
    translation_manager: "TranslationManager"
    patient_lang_var: tk.StringVar
    doctor_lang_var: tk.StringVar
    patient_combo: ttk.Combobox
    doctor_combo: ttk.Combobox
    llm_refinement_var: tk.BooleanVar
    logger: logging.Logger
    _preset_buttons: Dict[Tuple[str, str], ttk.Button]
    _language_presets: List[Tuple[str, str, str, str]]

    def _create_language_bar(self, parent):
        """Create language selection controls.

        Args:
            parent: Parent widget
        """
        lang_frame = ttk.Frame(parent)
        lang_frame.pack(fill=X)

        # Patient language selection
        ttk.Label(lang_frame, text="Patient Language:", font=("", 10, "bold")).pack(side=LEFT, padx=(0, 5))

        # Get supported languages and sort alphabetically by name
        languages = self.translation_manager.get_supported_languages()
        languages = sorted(languages, key=lambda x: x[1].lower())
        lang_names = [f"{lang[1]} ({lang[0]})" for lang in languages]
        lang_codes = [lang[0] for lang in languages]

        self.patient_lang_var = tk.StringVar(value=self.patient_language)
        self.patient_combo = ttk.Combobox(
            lang_frame,
            textvariable=self.patient_lang_var,
            values=lang_names,
            state="readonly",
            width=20
        )
        self.patient_combo.pack(side=LEFT, padx=(0, 20))

        # Set display value
        try:
            idx = lang_codes.index(self.patient_language)
            self.patient_combo.set(lang_names[idx])
        except (ValueError, IndexError):
            self.patient_combo.set(self.patient_language)

        self.patient_combo.bind("<<ComboboxSelected>>", self._on_patient_language_change)

        # Language swap button
        swap_btn = ttk.Button(
            lang_frame,
            text="⇄ Swap",
            command=self._swap_languages,
            bootstyle="info-outline",
            width=8
        )
        swap_btn.pack(side=LEFT, padx=10)
        ToolTip(swap_btn, "Swap patient and doctor languages (exchanges the two languages)")

        # Doctor language selection
        ttk.Label(lang_frame, text="Doctor Language:", font=("", 10, "bold")).pack(side=LEFT, padx=(0, 5))

        self.doctor_lang_var = tk.StringVar(value=self.doctor_language)
        self.doctor_combo = ttk.Combobox(
            lang_frame,
            textvariable=self.doctor_lang_var,
            values=lang_names,
            state="readonly",
            width=20
        )
        self.doctor_combo.pack(side=LEFT)

        # Set display value
        try:
            idx = lang_codes.index(self.doctor_language)
            self.doctor_combo.set(lang_names[idx])
        except (ValueError, IndexError):
            self.doctor_combo.set(self.doctor_language)

        self.doctor_combo.bind("<<ComboboxSelected>>", self._on_doctor_language_change)

        # Auto-detect checkbox
        self.auto_detect_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            lang_frame,
            text="Auto-detect patient language",
            variable=self.auto_detect_var
        ).pack(side=LEFT, padx=(30, 0))

        # LLM refinement toggle
        translation_settings = SETTINGS.get("translation", {})
        self.llm_refinement_var = tk.BooleanVar(
            value=translation_settings.get("llm_refinement_enabled", False)
        )
        llm_cb = ttk.Checkbutton(
            lang_frame,
            text="Medical term refinement",
            variable=self.llm_refinement_var,
            command=self._on_llm_refinement_toggle
        )
        llm_cb.pack(side=LEFT, padx=(20, 0))
        ToolTip(llm_cb, "Use AI to refine medical terminology in translations")

        # Quick language pair presets
        presets_frame = ttk.Frame(parent)
        presets_frame.pack(fill=X, pady=(5, 0))

        ttk.Label(presets_frame, text="Quick pairs:", font=("", 9)).pack(side=LEFT, padx=(0, 10))

        # Common language pairs for medical settings
        self._language_presets = [
            ("ES", "es", "en", "Spanish ↔ English"),
            ("CN", "zh", "en", "Chinese ↔ English"),
            ("VN", "vi", "en", "Vietnamese ↔ English"),
            ("KR", "ko", "en", "Korean ↔ English"),
            ("FR", "fr", "en", "French ↔ English"),
            ("RU", "ru", "en", "Russian ↔ English"),
        ]

        # Store button references for highlighting
        self._preset_buttons = {}

        for label, patient_code, doctor_code, tooltip in self._language_presets:
            btn = ttk.Button(
                presets_frame,
                text=f"{label}↔EN",
                command=lambda p=patient_code, d=doctor_code: self._apply_language_preset(p, d),
                bootstyle="outline-secondary",
                width=8
            )
            btn.pack(side=LEFT, padx=2)
            ToolTip(btn, tooltip)
            self._preset_buttons[(patient_code, doctor_code)] = btn

    def _apply_language_preset(self, patient_code: str, doctor_code: str):
        """Apply a language pair preset.

        Args:
            patient_code: Language code for patient
            doctor_code: Language code for doctor
        """
        # Update internal values
        self.patient_language = patient_code
        self.doctor_language = doctor_code

        # Get language names for display
        languages = self.translation_manager.get_supported_languages()
        lang_dict = {lang[0]: f"{lang[1]} ({lang[0]})" for lang in languages}

        # Update comboboxes
        if patient_code in lang_dict:
            self.patient_combo.set(lang_dict[patient_code])
        else:
            self.patient_combo.set(patient_code)

        if doctor_code in lang_dict:
            self.doctor_combo.set(lang_dict[doctor_code])
        else:
            self.doctor_combo.set(doctor_code)

        # Update preset button highlighting
        self._update_preset_highlighting()

        self.logger.info(f"Applied language preset: patient={patient_code}, doctor={doctor_code}")

    def _update_preset_highlighting(self):
        """Update the visual highlighting of preset buttons based on current language selection."""
        if not hasattr(self, '_preset_buttons'):
            return

        current_pair = (self.patient_language, self.doctor_language)

        for pair, btn in self._preset_buttons.items():
            try:
                if pair == current_pair:
                    btn.configure(bootstyle="info")  # Highlighted
                else:
                    btn.configure(bootstyle="outline-secondary")  # Normal
            except tk.TclError:
                pass

    def _on_patient_language_change(self, event=None):
        """Handle patient language selection change."""
        selected = self.patient_lang_var.get()

        # Get the language code from the formatted string "Language Name (code)"
        # Handle special cases like "Chinese (Simplified) (zh-CN)"
        if selected.endswith(')'):
            last_paren = selected.rfind('(')
            if last_paren != -1:
                self.patient_language = selected[last_paren+1:-1]
            else:
                self.patient_language = selected
        else:
            self.patient_language = selected

        self.logger.debug(f"Patient language changed to: {self.patient_language} (from: {selected})")
        self._update_preset_highlighting()

    def _on_doctor_language_change(self, event=None):
        """Handle doctor language selection change."""
        selected = self.doctor_lang_var.get()

        # Get the language code from the formatted string "Language Name (code)"
        # Handle special cases like "Chinese (Simplified) (zh-CN)"
        if selected.endswith(')'):
            last_paren = selected.rfind('(')
            if last_paren != -1:
                self.doctor_language = selected[last_paren+1:-1]
            else:
                self.doctor_language = selected
        else:
            self.doctor_language = selected

        self.logger.debug(f"Doctor language changed to: {self.doctor_language} (from: {selected})")
        self._update_preset_highlighting()

    def _swap_languages(self):
        """Swap patient and doctor languages."""
        # Store current values
        current_patient = self.patient_lang_var.get()
        current_doctor = self.doctor_lang_var.get()
        temp_patient_code = self.patient_language
        temp_doctor_code = self.doctor_language

        # Swap display values
        self.patient_combo.set(current_doctor)
        self.doctor_combo.set(current_patient)

        # Swap language codes
        self.patient_language = temp_doctor_code
        self.doctor_language = temp_patient_code

        # Update preset highlighting
        self._update_preset_highlighting()

        self.logger.debug(f"Languages swapped: patient={self.patient_language}, doctor={self.doctor_language}")

    def _on_llm_refinement_toggle(self):
        """Handle LLM refinement checkbox toggle."""
        enabled = self.llm_refinement_var.get()
        SETTINGS.setdefault("translation", {})["llm_refinement_enabled"] = enabled


__all__ = ["LanguagesMixin"]
