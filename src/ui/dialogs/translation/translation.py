"""
Translation Processing Module

Provides translation API calls and text processing functionality.
"""

import tkinter as tk
import ttkbootstrap as ttk
import threading
import time
from typing import TYPE_CHECKING, Optional, Callable
from utils.structured_logging import get_logger

if TYPE_CHECKING:
    from managers.translation_manager import TranslationManager
    from managers.translation_session_manager import TranslationSessionManager


logger = get_logger(__name__)


class TranslationMixin:
    """Mixin for translation processing."""

    dialog: Optional[tk.Toplevel]
    translation_manager: "TranslationManager"
    session_manager: "TranslationSessionManager"
    patient_language: str
    doctor_language: str

    # Rate limiting
    _last_translation_time: float
    _min_translation_interval: float

    # UI components
    patient_original_text: tk.Text
    patient_translated_text: tk.Text
    patient_translation_indicator: ttk.Label
    doctor_input_text: tk.Text
    doctor_translated_text: tk.Text
    doctor_translation_indicator: ttk.Label
    recording_status: ttk.Label
    patient_lang_var: tk.StringVar
    auto_detect_var: tk.BooleanVar
    llm_refinement_var: tk.BooleanVar

    # Methods from other mixins
    def _dialog_exists(self) -> bool: ...
    def _safe_after(self, delay: int, callback: Callable, *args): ...
    def _safe_ui_update(self, callback: Callable): ...
    def _add_history_entry(self, entry): ...
    def _update_send_play_buttons(self): ...

    def _process_patient_speech(self, transcript: str):
        """Process transcribed patient speech.

        Args:
            transcript: Transcribed text
        """
        # Insert original text
        self.patient_original_text.delete("1.0", tk.END)
        self.patient_original_text.insert("1.0", transcript)

        # Detect or use configured language
        if self.auto_detect_var.get():
            detected_lang = self.translation_manager.detect_language(transcript)
            if detected_lang:
                self.patient_language = detected_lang
                # Update combo box to show detected language
                languages = self.translation_manager.get_supported_languages()
                for lang_code, lang_name in languages:
                    if lang_code == detected_lang:
                        self.patient_lang_var.set(f"{lang_name} ({lang_code})")
                        break

        # Translate to doctor's language
        self.recording_status.config(text="Translating...", foreground="blue")
        self.patient_translation_indicator.pack(side=tk.LEFT, padx=(10, 0))

        def translate():
            try:
                logger.debug(f"Translating from {self.patient_language} to {self.doctor_language}")
                # Use LLM refinement if enabled
                refine_medical = self.llm_refinement_var.get() if hasattr(self, 'llm_refinement_var') else None
                translated = self.translation_manager.translate(
                    transcript,
                    source_lang=self.patient_language,
                    target_lang=self.doctor_language,
                    refine_medical=refine_medical
                )

                # Add entry to session history
                def update_ui():
                    self.patient_translation_indicator.pack_forget()
                    self.patient_translated_text.delete("1.0", tk.END)
                    self.patient_translated_text.insert("1.0", translated)
                    self.recording_status.config(text="Ready", foreground="green")

                    # Add to history
                    try:
                        entry = self.session_manager.add_patient_entry(
                            original_text=transcript,
                            original_language=self.patient_language,
                            translated_text=translated,
                            target_language=self.doctor_language
                        )
                        self._add_history_entry(entry)
                    except Exception as he:
                        logger.error(f"Failed to add history entry: {he}")

                # Update UI on main thread
                self._safe_after(0, update_ui)

            except Exception as e:
                logger.error(f"Translation failed: {e}", exc_info=True)
                error_msg = str(e)[:40]  # Capture error message before callback

                def show_translation_error():
                    if not self._dialog_exists():
                        return
                    self.patient_translation_indicator.pack_forget()
                    self.recording_status.config(text=f"Translation error: {error_msg}", foreground="red")

                self._safe_after(0, show_translation_error)

        threading.Thread(target=translate, daemon=True).start()

    def _on_doctor_text_change(self, event=None):
        """Handle changes to doctor input text."""
        if not self._dialog_exists():
            return

        text = self.doctor_input_text.get("1.0", tk.END).strip()
        if not text:
            # Clear translated text when input is empty
            self.doctor_translated_text.delete("1.0", tk.END)
            self._update_send_play_buttons()
            return

        # Rate limiting - don't translate too frequently
        current_time = time.time()
        if current_time - self._last_translation_time < self._min_translation_interval:
            # Schedule translation after delay
            if hasattr(self, '_doctor_translate_timer'):
                try:
                    self.dialog.after_cancel(self._doctor_translate_timer)
                except Exception:
                    pass
            self._doctor_translate_timer = self.dialog.after(
                int(self._min_translation_interval * 1000),
                lambda: self._translate_doctor_text(text)
            )
            return

        self._translate_doctor_text(text)

    def _translate_doctor_text(self, text: str):
        """Translate doctor text to patient language.

        Args:
            text: Text to translate
        """
        if not text.strip():
            return

        self._last_translation_time = time.time()

        # Show translation indicator
        self.doctor_translation_indicator.pack(side=tk.LEFT, padx=(10, 0))

        def translate():
            try:
                # Use LLM refinement if enabled
                refine_medical = self.llm_refinement_var.get() if hasattr(self, 'llm_refinement_var') else None
                translated = self.translation_manager.translate(
                    text,
                    source_lang=self.doctor_language,
                    target_lang=self.patient_language,
                    refine_medical=refine_medical
                )

                def update_ui():
                    if not self._dialog_exists():
                        return
                    self.doctor_translation_indicator.pack_forget()
                    self.doctor_translated_text.delete("1.0", tk.END)
                    self.doctor_translated_text.insert("1.0", translated)
                    self._update_send_play_buttons()

                self._safe_after(0, update_ui)

            except Exception as e:
                logger.error(f"Doctor translation failed: {e}", exc_info=True)
                error_msg = str(e)[:30]  # Capture error message before lambda

                def show_error():
                    if not self._dialog_exists():
                        return
                    self.doctor_translation_indicator.pack_forget()
                    self.recording_status.config(text=f"Translation error: {error_msg}", foreground="red")

                self._safe_after(0, show_error)

        threading.Thread(target=translate, daemon=True).start()


__all__ = ["TranslationMixin"]
