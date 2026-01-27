"""
Translation Dialog Package

Provides a bidirectional translation interface for medical translation
between doctor and patient with STT/TTS support.
"""

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, X, HORIZONTAL, NORMAL, DISABLED
from datetime import datetime
from typing import Optional, Callable, List, Dict, TYPE_CHECKING

from managers.translation_manager import get_translation_manager
from managers.tts_manager import get_tts_manager
from managers.translation_session_manager import get_translation_session_manager
from audio.audio import AudioHandler
from settings.settings_manager import settings_manager
from utils.structured_logging import get_logger
from utils.error_handling import ErrorContext

logger = get_logger(__name__)

from .languages import LanguagesMixin
from .recording import RecordingMixin
from .translation import TranslationMixin
from .tts import TTSMixin
from .responses import ResponsesMixin
from .history import HistoryMixin
from .ui_builder import UIBuilderMixin

if TYPE_CHECKING:
    pass


class TranslationDialog(
    LanguagesMixin,
    RecordingMixin,
    TranslationMixin,
    TTSMixin,
    ResponsesMixin,
    HistoryMixin,
    UIBuilderMixin
):
    """Dialog for bidirectional translation with STT/TTS support.

    This class combines multiple mixins to provide:
    - Language selection and presets (LanguagesMixin)
    - Audio recording for patient and doctor (RecordingMixin)
    - Translation processing (TranslationMixin)
    - Text-to-speech playback (TTSMixin)
    - Canned responses management (ResponsesMixin)
    - Conversation history (HistoryMixin)
    - UI component creation (UIBuilderMixin)
    """

    def __init__(self, parent, audio_handler: AudioHandler):
        """Initialize the translation dialog.

        Args:
            parent: Parent window
            audio_handler: Audio handler for recording (reference for API keys)
        """
        self.parent = parent
        # Create a separate audio handler instance for translation
        logger.info(f"Creating AudioHandler for translation with keys: elevenlabs={bool(audio_handler.elevenlabs_api_key)}, deepgram={bool(audio_handler.deepgram_api_key)}, groq={bool(audio_handler.groq_api_key)}")
        self.audio_handler = AudioHandler(
            elevenlabs_api_key=audio_handler.elevenlabs_api_key,
            deepgram_api_key=audio_handler.deepgram_api_key,
            recognition_language=audio_handler.recognition_language,
            groq_api_key=audio_handler.groq_api_key
        )
        logger.info(f"AudioHandler created for translation dialog")
        self.translation_manager = get_translation_manager()
        self.tts_manager = get_tts_manager()
        self.session_manager = get_translation_session_manager()

        self.dialog: Optional[tk.Toplevel] = None
        self.is_recording = False
        self.stop_recording_func = None
        self.audio_segments: List = []
        self.recording_start_time: Optional[datetime] = None
        self.recording_timer_id: Optional[str] = None

        # Doctor dictation state
        self.is_doctor_recording = False
        self.doctor_audio_segments: List = []
        self.stop_doctor_recording_func = None

        # Get language and device settings
        translation_settings = settings_manager.get("translation", {})
        self.patient_language = translation_settings.get("patient_language", "es")
        self.doctor_language = translation_settings.get("doctor_language", "en")
        self.input_device = translation_settings.get("input_device", "")
        self.output_device = translation_settings.get("output_device", "")
        self.stt_provider = translation_settings.get("stt_provider", "")

        # New settings
        self.auto_clear_after_send = translation_settings.get("auto_clear_after_send", False)
        self.tts_speed = translation_settings.get("tts_speed", 1.0)
        self.font_size = translation_settings.get("font_size", 11)
        self.recent_languages = translation_settings.get("recent_languages", [])
        self.favorite_responses = translation_settings.get("favorite_responses", [])

        self.logger = get_logger(__name__)

        # Theme-aware colors
        self._init_theme_colors()

        # Rate limiting for API calls
        self._last_translation_time = 0
        self._min_translation_interval = 0.5

        # Undo history
        self._undo_stack: List[Dict] = []

        # Service status
        self._translation_service_online = True
        self._tts_service_online = True

        # Audio level visibility flag
        self._audio_level_visible = False

    def _dialog_exists(self) -> bool:
        """Check if dialog still exists and is valid.

        Returns:
            True if dialog exists and can be updated, False otherwise
        """
        try:
            return self.dialog is not None and self.dialog.winfo_exists()
        except tk.TclError:
            return False

    def _safe_after(self, delay: int, callback: Callable, *args):
        """Schedule a callback only if dialog still exists.

        Args:
            delay: Delay in milliseconds
            callback: Function to call
            *args: Arguments to pass to callback
        """
        logger.info(f"_safe_after called: delay={delay}, callback={callback.__name__ if hasattr(callback, '__name__') else 'lambda'}, dialog_exists={self._dialog_exists()}")

        def wrapped_callback():
            """Wrapper to catch and log any exceptions in the callback."""
            try:
                logger.info(f"_safe_after: executing callback")
                callback(*args)
                logger.info(f"_safe_after: callback completed successfully")
            except Exception as e:
                logger.error(f"_safe_after: Exception in callback: {e}", exc_info=True)

        if self._dialog_exists():
            try:
                self.dialog.after(delay, wrapped_callback)
                logger.info("_safe_after: callback scheduled successfully")
            except tk.TclError as e:
                logger.error(f"_safe_after: TclError when scheduling callback: {e}")
        else:
            logger.warning("_safe_after: dialog does not exist, skipping callback")

    def _safe_ui_update(self, callback: Callable):
        """Execute UI update only if dialog still exists.

        Args:
            callback: Function that updates UI
        """
        if self._dialog_exists():
            try:
                callback()
            except tk.TclError:
                pass

    def _update_send_play_buttons(self):
        """Update Send, Play, and Preview button states based on translated text availability."""
        if not self._dialog_exists():
            return

        try:
            translated_text = self.doctor_translated_text.get("1.0", tk.END).strip()
            state = NORMAL if translated_text else DISABLED

            if hasattr(self, 'send_button'):
                self.send_button.config(state=state)
            if hasattr(self, 'play_button'):
                self.play_button.config(state=state)
            if hasattr(self, 'preview_button'):
                self.preview_button.config(state=state)

            self._update_char_counts()
        except tk.TclError:
            pass

    def _init_theme_colors(self):
        """Initialize colors based on current theme."""
        try:
            style = ttk.Style()
            theme = style.theme_use()
            is_dark = 'dark' in theme.lower() or theme in ['darkly', 'cyborg', 'vapor', 'solar']
        except Exception:
            is_dark = False

        if is_dark:
            self.colors = {
                'patient_original_bg': '#2b3e50',
                'patient_translated_bg': '#1e3a5f',
                'doctor_input_bg': '#2e4a3f',
                'doctor_translated_bg': '#3d2e4a',
                'text_fg': '#e0e0e0',
                'highlight_fg': '#a0d0ff',
            }
        else:
            self.colors = {
                'patient_original_bg': '#ffffff',
                'patient_translated_bg': '#f0f8ff',
                'doctor_input_bg': '#f0fff0',
                'doctor_translated_bg': '#fff0f5',
                'text_fg': '#000000',
                'highlight_fg': '#0066cc',
            }

    def _hide_all_tooltips(self):
        """Hide all active tooltips in the application."""
        try:
            widget_under_mouse = self.parent.winfo_containing(
                self.parent.winfo_pointerx(),
                self.parent.winfo_pointery()
            )

            if widget_under_mouse:
                widget_under_mouse.event_generate("<Leave>")

            root = self.parent.winfo_toplevel()
            for child in root.children.values():
                if isinstance(child, tk.Toplevel):
                    try:
                        if child.wm_overrideredirect():
                            child.destroy()
                    except tk.TclError:
                        pass
        except Exception as e:
            self.logger.info(f"Error hiding tooltips: {e}")

    def show(self):
        """Show the translation dialog."""
        self._hide_all_tooltips()

        # Create dialog window
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Bidirectional Translation Assistant")

        # Get screen dimensions
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()

        # Set dialog size
        dialog_width = int(screen_width * 0.85)
        dialog_height = int(screen_height * 0.80)

        self.dialog.geometry(f"{dialog_width}x{dialog_height}")
        self.dialog.minsize(1200, 850)
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.update_idletasks()
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

        # Grab focus
        self.dialog.deiconify()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        # Create main container
        main_container = ttk.Frame(self.dialog)
        main_container.pack(fill=BOTH, expand=True, padx=10, pady=10)

        # Create language selection bar at top
        self._create_language_bar(main_container)

        # Create separator
        ttk.Separator(main_container, orient=HORIZONTAL).pack(fill=X, pady=(10, 15))

        # Create horizontal paned window for translation and history panels
        self.main_paned = ttk.Panedwindow(main_container, orient=HORIZONTAL)
        self.main_paned.pack(fill=BOTH, expand=True, pady=(0, 10))

        # Left pane: Current translation exchange
        left_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(left_frame, weight=3)

        # Patient section
        patient_frame = ttk.Labelframe(left_frame, text="Patient", padding=10)
        patient_frame.pack(fill=BOTH, expand=True, pady=(0, 10))
        self._create_patient_section(patient_frame)

        # Doctor section
        doctor_frame = ttk.Labelframe(left_frame, text="Doctor", padding=10)
        doctor_frame.pack(fill=BOTH, expand=True)
        self._create_doctor_section(doctor_frame)

        # Right pane: Conversation history
        right_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(right_frame, weight=1)
        self._create_history_panel(right_frame)

        # Create button bar at bottom
        self._create_button_bar(main_container)

        # Start a new session
        self._start_new_session()

        # Bind keyboard shortcuts
        self._bind_keyboard_shortcuts()

        # Handle dialog close
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

        # Focus on dialog
        self.dialog.focus_set()

    def _bind_keyboard_shortcuts(self):
        """Bind keyboard shortcuts for accessibility."""
        self.dialog.bind('<Control-r>', lambda e: self._toggle_recording())
        self.dialog.bind('<Control-R>', lambda e: self._toggle_recording())
        self.dialog.bind('<Escape>', lambda e: self._stop_recording() if self.is_recording else None)
        self.dialog.bind('<Control-p>', lambda e: self._play_doctor_response())
        self.dialog.bind('<Control-P>', lambda e: self._play_doctor_response())
        self.dialog.bind('<Control-Return>', lambda e: self._send_doctor_response())
        self.dialog.bind('<Control-e>', lambda e: self._export_session())
        self.dialog.bind('<Control-E>', lambda e: self._export_session())
        self.dialog.bind('<Control-n>', lambda e: self._start_new_session())
        self.dialog.bind('<Control-N>', lambda e: self._start_new_session())
        self.dialog.bind('<Control-z>', lambda e: self._undo_last_entry())
        self.dialog.bind('<Control-Z>', lambda e: self._undo_last_entry())

    def _send_doctor_response(self):
        """Send doctor response to history without TTS playback."""
        original_text = self.doctor_input_text.get("1.0", tk.END).strip()
        translated_text = self.doctor_translated_text.get("1.0", tk.END).strip()

        if not translated_text:
            self.recording_status.config(text="No translation to send", foreground="orange")
            return

        try:
            entry = self.session_manager.add_doctor_entry(
                original_text=original_text,
                original_language=self.doctor_language,
                translated_text=translated_text,
                target_language=self.patient_language
            )
            self._add_history_entry(entry)

            if self.auto_clear_var.get():
                self.doctor_input_text.delete("1.0", tk.END)
                self.doctor_translated_text.delete("1.0", tk.END)
                self._update_send_play_buttons()

            self.recording_status.config(text="Response sent", foreground="green")
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Adding doctor entry to history",
                exception=e
            )
            self.logger.error(ctx.to_log_string())
            self.recording_status.config(text=f"Error: {ctx.user_message}", foreground="red")

    def _clear_all(self):
        """Clear all text fields."""
        self.patient_original_text.delete("1.0", tk.END)
        self.patient_translated_text.delete("1.0", tk.END)
        self.doctor_input_text.delete("1.0", tk.END)
        self.doctor_translated_text.delete("1.0", tk.END)
        self.recording_status.config(text="")

    def _copy_text(self, text_widget):
        """Copy text from widget to clipboard.

        Args:
            text_widget: Text widget to copy from
        """
        try:
            text = text_widget.get("1.0", tk.END).strip()
            if text:
                self.dialog.clipboard_clear()
                self.dialog.clipboard_append(text)
                self.dialog.update()  # Flush clipboard to macOS pasteboard
                self.recording_status.config(text="Copied to clipboard", foreground="green")
            else:
                self.recording_status.config(text="Nothing to copy", foreground="orange")
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Copying text to clipboard",
                exception=e
            )
            self.logger.error(ctx.to_log_string())
            self.recording_status.config(text=f"Copy failed: {ctx.user_message[:30]}", foreground="red")

    def _export_conversation(self):
        """Export the conversation to a file."""
        from tkinter import filedialog

        filename = filedialog.asksaveasfilename(
            parent=self.dialog,
            title="Export Conversation",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )

        if not filename:
            return

        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            content = f"Translation Conversation Export\n"
            content += f"Generated: {timestamp}\n"
            content += f"Patient Language: {self.patient_language}\n"
            content += f"Doctor Language: {self.doctor_language}\n"
            content += "=" * 60 + "\n\n"

            patient_original = self.patient_original_text.get("1.0", tk.END).strip()
            patient_translated = self.patient_translated_text.get("1.0", tk.END).strip()

            if patient_original:
                content += f"PATIENT (Original - {self.patient_language}):\n"
                content += patient_original + "\n\n"
                content += f"PATIENT (Translated - {self.doctor_language}):\n"
                content += patient_translated + "\n\n"

            doctor_original = self.doctor_input_text.get("1.0", tk.END).strip()
            doctor_translated = self.doctor_translated_text.get("1.0", tk.END).strip()

            if doctor_original:
                content += f"DOCTOR (Original - {self.doctor_language}):\n"
                content += doctor_original + "\n\n"
                content += f"DOCTOR (Translated - {self.patient_language}):\n"
                content += doctor_translated + "\n\n"

            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)

            self.recording_status.config(text="Conversation exported", foreground="green")

        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Exporting conversation",
                exception=e,
                input_summary=f"filename={filename if 'filename' in dir() else 'unknown'}"
            )
            self.logger.error(ctx.to_log_string())
            self.recording_status.config(text=f"Export error: {ctx.user_message}", foreground="red")

    def _on_auto_clear_toggle(self):
        """Handle auto-clear checkbox toggle."""
        self.auto_clear_after_send = self.auto_clear_var.get()
        settings_manager.set_nested("translation.auto_clear_after_send", self.auto_clear_after_send)

    def _on_speed_change(self, value):
        """Handle TTS speed change."""
        speed = float(value)
        self.tts_speed = speed
        self.speed_label.config(text=f"{speed:.1f}x")
        settings_manager.set_nested("translation.tts_speed", speed)

    def _on_font_size_change(self):
        """Handle font size change."""
        size = self.font_size_var.get()
        self.font_size = size
        settings_manager.set_nested("translation.font_size", size)

        font = ("Consolas", size)
        for widget in [self.patient_original_text, self.patient_translated_text,
                       self.doctor_input_text, self.doctor_translated_text]:
            try:
                widget.config(font=font)
            except tk.TclError:
                pass

    def _update_char_counts(self):
        """Update character count displays."""
        if not self._dialog_exists():
            return

        try:
            doctor_text = self.doctor_input_text.get("1.0", tk.END).strip()
            self.doctor_char_count.config(text=f"{len(doctor_text)} chars")

            trans_text = self.doctor_translated_text.get("1.0", tk.END).strip()
            self.trans_char_count.config(text=f"{len(trans_text)} chars")
        except tk.TclError:
            pass

    def _copy_both_languages(self):
        """Copy both original and translated text to clipboard."""
        try:
            doctor_text = self.doctor_input_text.get("1.0", tk.END).strip()
            trans_text = self.doctor_translated_text.get("1.0", tk.END).strip()

            combined = f"[{self.doctor_language}] {doctor_text}\n[{self.patient_language}] {trans_text}"
            self.dialog.clipboard_clear()
            self.dialog.clipboard_append(combined)
            self.dialog.update()  # Flush clipboard to macOS pasteboard
            self.recording_status.config(text="Both languages copied!", foreground="green")
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Copying both languages to clipboard",
                exception=e
            )
            self.logger.error(ctx.to_log_string())

    def _add_to_context(self):
        """Add conversation to Context Information on main screen."""
        try:
            if not hasattr(self.parent, 'context_text') or self.parent.context_text is None:
                self.recording_status.config(text="Context panel not available", foreground="orange")
                return

            lines = []
            notes = self.session_notes_var.get().strip() if hasattr(self, 'session_notes_var') else ""

            lines.append("--- Translation Session ---")
            if notes:
                lines.append(f"Notes: {notes}")
            lines.append(f"Languages: Patient ({self.patient_language}) ↔ Doctor ({self.doctor_language})")
            lines.append("")

            patient_original = self.patient_original_text.get("1.0", tk.END).strip()
            patient_translated = self.patient_translated_text.get("1.0", tk.END).strip()
            doctor_input = self.doctor_input_text.get("1.0", tk.END).strip()
            doctor_translated = self.doctor_translated_text.get("1.0", tk.END).strip()

            if patient_original:
                lines.append(f"Patient [{self.patient_language}]: {patient_original}")
                if patient_translated:
                    lines.append(f"  → [{self.doctor_language}]: {patient_translated}")
                lines.append("")

            if doctor_input:
                lines.append(f"Doctor [{self.doctor_language}]: {doctor_input}")
                if doctor_translated:
                    lines.append(f"  → [{self.patient_language}]: {doctor_translated}")
                lines.append("")

            if self.session_manager.current_session and self.session_manager.current_session.entries:
                lines.append("Conversation History:")
                for entry in self.session_manager.current_session.entries:
                    speaker = entry.speaker.value.title()
                    lines.append(f"  {speaker}: {entry.original_text}")
                    display_trans = entry.llm_refined_text or entry.translated_text
                    lines.append(f"    → {display_trans}")
                lines.append("")

            lines.append("--- End Translation ---")

            existing = self.parent.context_text.get("1.0", tk.END).strip()
            new_content = "\n".join(lines)

            if existing:
                combined = f"{existing}\n\n{new_content}"
            else:
                combined = new_content

            self.parent.context_text.delete("1.0", tk.END)
            self.parent.context_text.insert("1.0", combined)

            self.recording_status.config(text="Added to Context!", foreground="green")
            self.logger.info("Translation conversation added to context")

        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Adding translation to context",
                exception=e
            )
            self.logger.error(ctx.to_log_string())
            self.recording_status.config(text=f"Error: {ctx.user_message[:30]}", foreground="red")

    def _update_service_status(self, translation_ok: bool = None, tts_ok: bool = None):
        """Update service status indicators."""
        if not self._dialog_exists():
            return

        try:
            if translation_ok is not None:
                self._translation_service_online = translation_ok
                color = "green" if translation_ok else "red"
                self.translation_status.config(foreground=color)

            if tts_ok is not None:
                self._tts_service_online = tts_ok
                color = "green" if tts_ok else "red"
                self.tts_status.config(foreground=color)
        except tk.TclError:
            pass

    def _on_close(self):
        """Handle dialog close."""
        if self.is_recording:
            self._stop_recording()

        if hasattr(self, 'is_dictating') and self.is_dictating:
            self._stop_doctor_dictation()

        self._stop_playback()

        if self.session_manager.current_session and hasattr(self, 'session_notes_var'):
            notes = self.session_notes_var.get().strip()
            if notes:
                self.session_manager.current_session.notes = notes

        try:
            self.session_manager.end_session()
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Ending translation session",
                exception=e
            )
            self.logger.error(ctx.to_log_string())

        try:
            self.audio_handler.cleanup_resources()
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Cleaning up audio handler",
                exception=e
            )
            self.logger.error(ctx.to_log_string())

        # Save settings
        selected_stt_display = self.selected_stt_provider.get()
        translation_config = settings_manager.get("translation", {})
        translation_config.update({
            "patient_language": self.patient_language,
            "doctor_language": self.doctor_language,
            "input_device": self.selected_microphone.get(),
            "output_device": self.selected_output.get(),
            "stt_provider": self._stt_provider_map.get(selected_stt_display, ""),
        })
        settings_manager.set("translation", translation_config)
        self.logger.info("Translation settings saved")

        self.dialog.destroy()


__all__ = ["TranslationDialog"]
