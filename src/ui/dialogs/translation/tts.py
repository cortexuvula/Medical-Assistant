"""
Translation TTS Module

Provides text-to-speech playback functionality.
"""

import tkinter as tk
import ttkbootstrap as ttk

import threading
import logging
from typing import TYPE_CHECKING, Optional, Callable

if TYPE_CHECKING:
    from managers.tts_manager import TTSManager


class TTSMixin:
    """Mixin for text-to-speech functionality."""

    dialog: Optional[tk.Toplevel]
    tts_manager: "TTSManager"
    patient_language: str
    logger: logging.Logger

    # UI components
    doctor_translated_text: tk.Text
    play_button: ttk.Button
    preview_button: ttk.Button
    stop_button: ttk.Button
    recording_status: ttk.Label
    selected_output: tk.StringVar

    # Methods from other mixins
    def _dialog_exists(self) -> bool: ...
    def _safe_after(self, delay: int, callback: Callable, *args): ...
    def _safe_ui_update(self, callback: Callable): ...

    def _play_doctor_response(self):
        """Play the translated doctor response via TTS."""
        translated_text = self.doctor_translated_text.get("1.0", tk.END).strip()
        if not translated_text:
            return

        # Update button states
        self.play_button.config(state=tk.DISABLED, text="🔊 Playing...")
        self.stop_button.config(state=tk.NORMAL)
        self.recording_status.config(text="Playing response...", foreground="blue")

        def synthesize_and_play():
            try:
                self.tts_manager.synthesize_and_play(
                    translated_text,
                    language=self.patient_language,
                    blocking=True,
                    output_device=self.selected_output.get()
                )
                self._safe_after(0, lambda: self._safe_ui_update(
                    lambda: self._on_playback_complete()
                ))
            except Exception as e:
                self.logger.error(f"TTS playback failed: {e}", exc_info=True)
                self._safe_after(0, lambda err=str(e): self._safe_ui_update(
                    lambda: self._on_playback_error(err)
                ))

        threading.Thread(target=synthesize_and_play, daemon=True).start()

    def _on_playback_complete(self):
        """Handle TTS playback completion."""
        self.play_button.config(state=tk.NORMAL, text="🔊 Play")
        self.stop_button.config(state=tk.DISABLED)
        self.recording_status.config(text="Playback complete", foreground="green")

    def _on_playback_error(self, error: str):
        """Handle TTS playback error.

        Args:
            error: Error message
        """
        self.play_button.config(state=tk.NORMAL, text="🔊 Play")
        self.stop_button.config(state=tk.DISABLED)
        self.recording_status.config(text=f"Playback error: {error[:40]}", foreground="red")

    def _stop_playback(self):
        """Stop current TTS playback."""
        try:
            self.tts_manager.stop_playback()
            self.play_button.config(state=tk.NORMAL, text="🔊 Play")
            self.stop_button.config(state=tk.DISABLED)
            self.recording_status.config(text="Playback stopped", foreground="orange")
        except Exception as e:
            self.logger.error(f"Failed to stop playback: {e}")

    def _preview_translation(self):
        """Preview the translation audio for the doctor (at lower volume)."""
        translated_text = self.doctor_translated_text.get("1.0", tk.END).strip()
        if not translated_text:
            return

        self.preview_button.config(state=tk.DISABLED, text="👂 Previewing...")
        self.stop_button.config(state=tk.NORMAL)
        self.recording_status.config(text="Previewing translation...", foreground="blue")

        def preview_audio():
            try:
                self.tts_manager.synthesize_and_play(
                    translated_text,
                    language=self.patient_language,
                    blocking=True,
                    output_device=self.selected_output.get()
                )
                self._safe_after(0, lambda: self._safe_ui_update(
                    lambda: self._on_preview_complete()
                ))
            except Exception as e:
                self.logger.error(f"Preview failed: {e}", exc_info=True)
                self._safe_after(0, lambda: self._safe_ui_update(
                    lambda: self._on_preview_error(str(e))
                ))

        threading.Thread(target=preview_audio, daemon=True).start()

    def _on_preview_complete(self):
        """Handle preview completion."""
        self.preview_button.config(state=tk.NORMAL, text="👂 Preview")
        self.stop_button.config(state=tk.DISABLED)
        self.recording_status.config(text="Preview complete", foreground="green")

    def _on_preview_error(self, error: str):
        """Handle preview error.

        Args:
            error: Error message
        """
        self.preview_button.config(state=tk.NORMAL, text="👂 Preview")
        self.stop_button.config(state=tk.DISABLED)
        self.recording_status.config(text=f"Preview error: {error[:40]}", foreground="red")


__all__ = ["TTSMixin"]
