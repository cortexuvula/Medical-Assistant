"""
Translation Recording Module

Provides audio recording functionality for patient and doctor speech.
"""

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import LEFT
import threading
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Callable, List

from settings.settings_manager import settings_manager
from utils.structured_logging import get_logger
from utils.error_handling import ErrorContext

if TYPE_CHECKING:
    from audio.audio import AudioHandler


class RecordingMixin:
    """Mixin for audio recording functionality."""

    parent: tk.Tk
    dialog: Optional[tk.Toplevel]
    audio_handler: "AudioHandler"
    is_recording: bool
    stop_recording_func: Optional[Callable]
    audio_segments: List
    recording_start_time: Optional[datetime]
    recording_timer_id: Optional[str]
    _audio_level_visible: bool

    # UI components
    record_button: ttk.Button
    recording_status: ttk.Label
    recording_timer_label: ttk.Label
    audio_level_bar: ttk.Progressbar
    selected_microphone: tk.StringVar
    selected_stt_provider: tk.StringVar
    _stt_provider_map: dict

    # Doctor dictation
    is_doctor_recording: bool
    dictate_button: ttk.Button
    doctor_audio_segments: List
    stop_doctor_recording_func: Optional[Callable]

    logger: "get_logger"  # Uses structured logger

    # Methods from other mixins (declared for type checking)
    def _dialog_exists(self) -> bool: ...
    def _safe_after(self, delay: int, callback: Callable, *args): ...
    def _safe_ui_update(self, callback: Callable): ...
    def _process_patient_speech(self, transcript: str): ...
    def _update_doctor_dictation_text(self, transcript: str): ...

    def _toggle_recording(self):
        """Toggle patient speech recording."""
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        """Start recording patient speech."""
        if self.is_recording:
            return

        try:
            # Update UI
            self.is_recording = True
            self.record_button.config(text="⏹ Stop Recording", bootstyle="secondary")
            self.recording_status.config(text="Recording...", foreground="red")

            # Start recording timer
            self.recording_start_time = datetime.now()
            self.recording_timer_label.config(text="00:00")
            self.recording_timer_label.pack(side=LEFT, padx=(10, 0))
            self._update_recording_timer()

            # Show audio level indicator
            self.audio_level_bar.pack(side=LEFT, padx=(5, 0))
            self.audio_level_bar['value'] = 0
            self._audio_level_visible = True

            # Get selected microphone from dropdown
            mic_name = self.selected_microphone.get()
            if not mic_name:
                raise ValueError("No microphone selected")

            # Clear audio segments
            self.audio_segments = []

            # Start recording with shorter phrase time limit for conversational speech
            self.stop_recording_func = self.audio_handler.listen_in_background(
                mic_name,
                self._on_audio_data,
                phrase_time_limit=3,
                stream_purpose="translation"
            )

            # Play start sound
            if hasattr(self.parent, 'play_recording_sound'):
                self.parent.play_recording_sound(start=True)

        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Starting patient recording",
                exception=e,
                input_summary=f"mic={mic_name if 'mic_name' in dir() else 'unknown'}"
            )
            self.logger.error(ctx.to_log_string())
            self.is_recording = False
            self.recording_status.config(text=f"Error: {ctx.user_message}", foreground="red")
            self.record_button.config(text="🎤 Record Patient", bootstyle="danger")

    def _stop_recording(self):
        """Stop recording and process the audio."""
        if not self.is_recording or not self.stop_recording_func:
            return

        # Stop recording timer
        if self.recording_timer_id:
            self.dialog.after_cancel(self.recording_timer_id)
            self.recording_timer_id = None
        self.recording_timer_label.pack_forget()

        # Hide audio level indicator
        if self._audio_level_visible:
            self.audio_level_bar.pack_forget()
            self._audio_level_visible = False

        # Update UI immediately but keep is_recording=True until flush completes
        self.record_button.config(text="🎤 Record Patient", bootstyle="danger")
        self.recording_status.config(text="Processing...", foreground="blue")

        # Stop recording in thread
        def stop_and_process():
            try:
                # Stop recording - this will flush accumulated audio via callback
                self.stop_recording_func()
                self.stop_recording_func = None

                # NOW set is_recording to False after flush completes
                self.is_recording = False

                # Play stop sound
                if hasattr(self.parent, 'play_recording_sound'):
                    self.parent.play_recording_sound(start=False)

                # Process accumulated audio segments
                if self.audio_segments:
                    # Combine all segments
                    combined = self.audio_handler.combine_audio_segments(self.audio_segments)

                    if combined:
                        # Update status
                        self._safe_after(0, lambda: self._safe_ui_update(
                            lambda: self.recording_status.config(text="Transcribing...", foreground="blue")
                        ))

                        # Use selected STT provider for transcription
                        selected_stt_display = self.selected_stt_provider.get()
                        selected_provider = self._stt_provider_map.get(selected_stt_display, "")

                        # Save current provider and switch if needed
                        original_provider = settings_manager.get("stt_provider", "groq")
                        if selected_provider:
                            settings_manager.set("stt_provider", selected_provider, auto_save=False)
                            self.logger.info(f"Using STT provider: {selected_provider}")

                        # Disable diarization for Translation Assistant
                        original_deepgram_diarize = settings_manager.get_nested("deepgram.diarize", False)
                        original_elevenlabs_diarize = settings_manager.get_nested("elevenlabs.diarize", True)
                        settings_manager.set_nested("deepgram.diarize", False)
                        settings_manager.set_nested("elevenlabs.diarize", False)

                        # Disable audio event tagging
                        original_tag_audio_events = settings_manager.get_nested("elevenlabs.tag_audio_events", True)
                        settings_manager.set_nested("elevenlabs.tag_audio_events", False)

                        try:
                            # Transcribe without prefix
                            transcript = self.audio_handler.transcribe_audio_without_prefix(combined)
                        finally:
                            # Restore original provider
                            if selected_provider:
                                settings_manager.set("stt_provider", original_provider, auto_save=False)
                            # Restore original diarization settings
                            settings_manager.set_nested("deepgram.diarize", original_deepgram_diarize)
                            settings_manager.set_nested("elevenlabs.diarize", original_elevenlabs_diarize)
                            # Restore audio event tagging setting
                            settings_manager.set_nested("elevenlabs.tag_audio_events", original_tag_audio_events)

                        if transcript:
                            # Process the complete transcript
                            self._safe_after(0, lambda t=transcript: self._process_patient_speech(t))
                        else:
                            self._safe_after(0, lambda: self._safe_ui_update(
                                lambda: self.recording_status.config(text="No speech detected", foreground="orange")
                            ))
                    else:
                        self._safe_after(0, lambda: self._safe_ui_update(
                            lambda: self.recording_status.config(text="No audio captured", foreground="orange")
                        ))
                else:
                    self._safe_after(0, lambda: self._safe_ui_update(
                        lambda: self.recording_status.config(text="No audio captured", foreground="orange")
                    ))

            except Exception as e:
                ctx = ErrorContext.capture(
                    operation="Processing recording",
                    exception=e
                )
                self.logger.error(ctx.to_log_string(), exc_info=True)
                self._safe_after(0, lambda msg=ctx.user_message: self._safe_ui_update(
                    lambda: self.recording_status.config(text=f"Recording error: {msg[:50]}", foreground="red")
                ))

        # Start processing thread
        threading.Thread(target=stop_and_process, daemon=True).start()

    def _on_audio_data(self, audio_data):
        """Handle incoming audio data during recording.

        Args:
            audio_data: Complete audio segment (AudioData object)
        """
        if not self.is_recording:
            return

        try:
            # Process the audio data into a segment
            segment, _ = self.audio_handler.process_audio_data(audio_data)
            if segment:
                # Add to segments list
                self.audio_segments.append(segment)

                # Update audio level indicator
                try:
                    dbfs = segment.dBFS
                    # Map -40 dBFS to 0 and -5 dBFS to 100
                    level = max(0, min(100, (dbfs + 40) * (100 / 35)))
                    self._safe_after(0, lambda l=level: self._update_audio_level(l))
                except Exception:
                    pass  # Ignore level calculation errors

                # Update recording duration
                total_duration = sum(seg.duration_seconds for seg in self.audio_segments)
                self._safe_after(0, lambda d=total_duration: self._safe_ui_update(
                    lambda: self.recording_status.config(text=f"Recording... {d:.1f}s", foreground="red")
                ))

        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Processing audio data",
                exception=e
            )
            self.logger.error(ctx.to_log_string())

    def _update_audio_level(self, level: float):
        """Update the audio level indicator.

        Args:
            level: Audio level from 0-100
        """
        if not self._dialog_exists() or not self._audio_level_visible:
            return
        try:
            self.audio_level_bar['value'] = level
            # Change color based on level
            if level > 80:
                self.audio_level_bar.configure(bootstyle="danger-striped")
            elif level > 50:
                self.audio_level_bar.configure(bootstyle="warning-striped")
            else:
                self.audio_level_bar.configure(bootstyle="success-striped")
        except tk.TclError:
            pass

    def _update_recording_timer(self):
        """Update the recording timer display."""
        if not self.is_recording or not self.recording_start_time:
            return

        # Calculate elapsed time
        elapsed = datetime.now() - self.recording_start_time
        minutes = int(elapsed.total_seconds() // 60)
        seconds = int(elapsed.total_seconds() % 60)

        # Update timer label
        self.recording_timer_label.config(text=f"{minutes:02d}:{seconds:02d}")

        # Schedule next update
        self.recording_timer_id = self.dialog.after(1000, self._update_recording_timer)

    def _toggle_doctor_dictation(self):
        """Toggle doctor speech dictation."""
        if self.is_doctor_recording:
            self._stop_doctor_dictation()
        else:
            self._start_doctor_dictation()

    def _start_doctor_dictation(self):
        """Start recording doctor dictation."""
        if self.is_doctor_recording:
            return

        try:
            self.is_doctor_recording = True
            self.dictate_button.config(text="⏹ Stop", bootstyle="secondary")
            self.recording_status.config(text="Dictating...", foreground="blue")

            # Get selected microphone
            mic_name = self.selected_microphone.get()
            if not mic_name:
                raise ValueError("No microphone selected")

            # Clear audio segments
            self.doctor_audio_segments = []

            # Start recording
            self.stop_doctor_recording_func = self.audio_handler.listen_in_background(
                mic_name,
                self._on_doctor_audio_data,
                phrase_time_limit=5,
                stream_purpose="doctor_dictation"
            )

        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Starting doctor dictation",
                exception=e,
                input_summary=f"mic={mic_name if 'mic_name' in dir() else 'unknown'}"
            )
            self.logger.error(ctx.to_log_string())
            self.is_doctor_recording = False
            self.recording_status.config(text=f"Error: {ctx.user_message}", foreground="red")
            self.dictate_button.config(text="🎤 Dictate", bootstyle="outline-info")

    def _stop_doctor_dictation(self):
        """Stop doctor dictation and transcribe."""
        if not self.is_doctor_recording or not self.stop_doctor_recording_func:
            return

        # Update UI
        self.dictate_button.config(text="🎤 Dictate", bootstyle="outline-info")
        self.recording_status.config(text="Processing...", foreground="blue")

        def stop_and_transcribe():
            try:
                # Stop recording
                self.stop_doctor_recording_func()
                self.stop_doctor_recording_func = None
                self.is_doctor_recording = False

                # Process audio
                if self.doctor_audio_segments:
                    combined = self.audio_handler.combine_audio_segments(self.doctor_audio_segments)

                    if combined:
                        # Use selected STT provider
                        selected_stt_display = self.selected_stt_provider.get()
                        selected_provider = self._stt_provider_map.get(selected_stt_display, "")

                        original_provider = settings_manager.get("stt_provider", "groq")
                        if selected_provider:
                            settings_manager.set("stt_provider", selected_provider, auto_save=False)

                        # Disable diarization
                        original_deepgram_diarize = settings_manager.get_nested("deepgram.diarize", False)
                        original_elevenlabs_diarize = settings_manager.get_nested("elevenlabs.diarize", True)
                        settings_manager.set_nested("deepgram.diarize", False)
                        settings_manager.set_nested("elevenlabs.diarize", False)

                        try:
                            transcript = self.audio_handler.transcribe_audio_without_prefix(combined)
                        finally:
                            if selected_provider:
                                settings_manager.set("stt_provider", original_provider, auto_save=False)
                            settings_manager.set_nested("deepgram.diarize", original_deepgram_diarize)
                            settings_manager.set_nested("elevenlabs.diarize", original_elevenlabs_diarize)

                        if transcript:
                            def update_ui():
                                # Get current text and append
                                current = self.doctor_input_text.get("1.0", tk.END).strip()
                                if current:
                                    new_text = f"{current} {transcript}"
                                else:
                                    new_text = transcript
                                self.doctor_input_text.delete("1.0", tk.END)
                                self.doctor_input_text.insert("1.0", new_text)
                                self.recording_status.config(text="Dictation complete", foreground="green")
                                # Trigger translation
                                self._on_doctor_text_change()

                            self._safe_after(0, update_ui)
                        else:
                            self._safe_after(0, lambda: self._safe_ui_update(
                                lambda: self.recording_status.config(text="No speech detected", foreground="orange")
                            ))
                    else:
                        self._safe_after(0, lambda: self._safe_ui_update(
                            lambda: self.recording_status.config(text="No audio captured", foreground="orange")
                        ))
                else:
                    self._safe_after(0, lambda: self._safe_ui_update(
                        lambda: self.recording_status.config(text="No audio captured", foreground="orange")
                    ))

            except Exception as e:
                ctx = ErrorContext.capture(
                    operation="Doctor dictation transcription",
                    exception=e
                )
                self.logger.error(ctx.to_log_string(), exc_info=True)
                self._safe_after(0, lambda msg=ctx.user_message: self._safe_ui_update(
                    lambda: self.recording_status.config(text=f"Error: {msg[:40]}", foreground="red")
                ))

        threading.Thread(target=stop_and_transcribe, daemon=True).start()

    def _on_doctor_audio_data(self, audio_data):
        """Handle incoming audio data during doctor dictation.

        Args:
            audio_data: Complete audio segment
        """
        if not self.is_doctor_recording:
            return

        try:
            segment, _ = self.audio_handler.process_audio_data(audio_data)
            if segment:
                self.doctor_audio_segments.append(segment)
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Processing doctor audio data",
                exception=e
            )
            self.logger.error(ctx.to_log_string())


__all__ = ["RecordingMixin"]
