"""
Translation UI Builder Module

Provides UI creation for patient section, doctor section, and button bar.
"""

import tkinter as tk
from tkinter.constants import WORD
import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, X, Y, LEFT, RIGHT, W
from typing import TYPE_CHECKING, Optional, Dict

from ui.tooltip import ToolTip
from utils.structured_logging import get_logger, StructuredLogger

if TYPE_CHECKING:
    pass


class UIBuilderMixin:
    """Mixin for building translation dialog UI components."""

    dialog: Optional[tk.Toplevel]
    logger: StructuredLogger
    colors: Dict[str, str]

    # Settings
    auto_clear_after_send: bool
    tts_speed: float
    font_size: int
    input_device: str
    output_device: str

    # UI components (will be created)
    patient_original_text: tk.Text
    patient_translated_text: tk.Text
    patient_translation_indicator: ttk.Label
    doctor_input_text: tk.Text
    doctor_translated_text: tk.Text
    doctor_translation_indicator: ttk.Label
    doctor_char_count: ttk.Label
    trans_char_count: ttk.Label
    record_button: ttk.Button
    recording_status: ttk.Label
    recording_timer_label: ttk.Label
    audio_level_bar: ttk.Progressbar
    selected_microphone: tk.StringVar
    selected_stt_provider: tk.StringVar
    mic_combo: ttk.Combobox
    stt_combo: ttk.Combobox
    _stt_provider_map: Dict
    _stt_provider_reverse_map: Dict
    stt_provider: str
    _audio_level_visible: bool
    canned_frame: ttk.Frame
    _quick_container: ttk.Frame
    _quick_responses_visible: tk.BooleanVar
    _quick_toggle_btn: ttk.Checkbutton
    dictate_button: ttk.Button
    is_dictating: bool
    dictate_stop_func: Optional
    realtime_var: tk.BooleanVar
    auto_clear_var: tk.BooleanVar
    send_button: ttk.Button
    preview_button: ttk.Button
    play_button: ttk.Button
    stop_button: ttk.Button
    selected_output: tk.StringVar
    output_combo: ttk.Combobox
    speed_var: tk.DoubleVar
    speed_scale: ttk.Scale
    speed_label: ttk.Label
    font_size_var: tk.IntVar
    service_status_frame: ttk.Frame
    translation_status: ttk.Label
    tts_status: ttk.Label
    undo_button: ttk.Button
    session_notes_var: tk.StringVar
    session_notes_entry: ttk.Entry

    # Methods from other mixins
    def _toggle_recording(self): ...
    def _toggle_doctor_dictation(self): ...
    def _on_doctor_text_change(self, event=None): ...
    def _toggle_quick_responses(self): ...
    def _create_canned_responses(self, parent): ...
    def _send_doctor_response(self): ...
    def _preview_translation(self): ...
    def _play_doctor_response(self): ...
    def _stop_playback(self): ...
    def _on_auto_clear_toggle(self): ...
    def _on_speed_change(self, value): ...
    def _on_font_size_change(self): ...
    def _undo_last_entry(self): ...
    def _clear_all(self): ...
    def _copy_text(self, text_widget): ...
    def _copy_both_languages(self): ...
    def _export_conversation(self): ...
    def _add_to_context(self): ...
    def _on_close(self): ...

    def _create_patient_section(self, parent):
        """Create patient input/output section.

        Args:
            parent: Parent widget
        """
        # Recording controls
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=X, pady=(0, 10))

        # Microphone selection
        mic_frame = ttk.Frame(control_frame)
        mic_frame.pack(side=LEFT, padx=(0, 20))

        ttk.Label(mic_frame, text="Microphone:").pack(side=LEFT, padx=(0, 5))

        # Get available microphones
        from utils.utils import get_valid_microphones
        microphones = get_valid_microphones()

        self.selected_microphone = tk.StringVar()
        if self.input_device and self.input_device in microphones:
            self.selected_microphone.set(self.input_device)
        elif microphones:
            if self.input_device:
                self.logger.warning(f"Saved microphone '{self.input_device}' not found, using default")
            self.selected_microphone.set(microphones[0])

        self.mic_combo = ttk.Combobox(
            mic_frame,
            textvariable=self.selected_microphone,
            values=microphones,
            width=30,
            state="readonly"
        )
        self.mic_combo.pack(side=LEFT)

        # STT Provider selection
        stt_frame = ttk.Frame(control_frame)
        stt_frame.pack(side=LEFT, padx=(0, 20))

        ttk.Label(stt_frame, text="STT:").pack(side=LEFT, padx=(0, 5))

        # Available STT providers
        stt_providers = ["Use Main Setting", "Groq", "Deepgram", "ElevenLabs", "Whisper"]
        stt_provider_map = {"Use Main Setting": "", "Groq": "groq", "Deepgram": "deepgram",
                           "ElevenLabs": "elevenlabs", "Whisper": "whisper"}
        self._stt_provider_map = stt_provider_map
        self._stt_provider_reverse_map = {v: k for k, v in stt_provider_map.items()}

        self.selected_stt_provider = tk.StringVar()
        display_name = self._stt_provider_reverse_map.get(self.stt_provider, "Use Main Setting")
        self.selected_stt_provider.set(display_name)

        self.stt_combo = ttk.Combobox(
            stt_frame,
            textvariable=self.selected_stt_provider,
            values=stt_providers,
            width=15,
            state="readonly"
        )
        self.stt_combo.pack(side=LEFT)
        ToolTip(self.stt_combo, "Select STT provider for patient speech recognition")

        self.record_button = ttk.Button(
            control_frame,
            text="🎤 Record Patient",
            command=self._toggle_recording,
            bootstyle="danger",
            width=20
        )
        self.record_button.pack(side=LEFT, padx=(0, 10))

        # Audio level indicator (progress bar)
        self.audio_level_bar = ttk.Progressbar(
            control_frame,
            mode='determinate',
            length=80,
            bootstyle="success-striped"
        )
        # Initially hidden
        self._audio_level_visible = False

        # Recording timer display
        self.recording_timer_label = ttk.Label(
            control_frame,
            text="00:00",
            font=("", 11, "bold"),
            foreground="red"
        )
        # Hidden initially

        self.recording_status = ttk.Label(control_frame, text="")
        self.recording_status.pack(side=LEFT)

        # Translation indicator (initially hidden)
        self.patient_translation_indicator = ttk.Label(
            control_frame,
            text="Translating...",
            foreground="blue",
            font=("", 9, "italic")
        )

        # Create text areas side by side
        text_container = ttk.Frame(parent)
        text_container.pack(fill=BOTH, expand=True)

        # Patient speech (original language)
        left_frame = ttk.Frame(text_container)
        left_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 5))

        ttk.Label(left_frame, text="Patient Speech (Original):", font=("", 9)).pack(anchor=W)

        scroll1 = ttk.Scrollbar(left_frame)
        scroll1.pack(side=RIGHT, fill=Y)

        self.patient_original_text = tk.Text(
            left_frame,
            wrap=tk.WORD,
            height=10,
            yscrollcommand=scroll1.set,
            font=("Consolas", 11),
            background=self.colors['patient_original_bg'],
            foreground=self.colors['text_fg'],
            insertbackground=self.colors['text_fg']
        )
        self.patient_original_text.pack(fill=BOTH, expand=True)
        scroll1.config(command=self.patient_original_text.yview)

        # Translation (English for doctor)
        right_frame = ttk.Frame(text_container)
        right_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=(5, 0))

        ttk.Label(right_frame, text="Translation (for Doctor):", font=("", 9)).pack(anchor=W)

        scroll2 = ttk.Scrollbar(right_frame)
        scroll2.pack(side=RIGHT, fill=Y)

        self.patient_translated_text = tk.Text(
            right_frame,
            wrap=tk.WORD,
            height=10,
            yscrollcommand=scroll2.set,
            font=("Consolas", 11),
            background=self.colors['patient_translated_bg'],
            foreground=self.colors['text_fg'],
            insertbackground=self.colors['text_fg']
        )
        self.patient_translated_text.pack(fill=BOTH, expand=True)
        scroll2.config(command=self.patient_translated_text.yview)

        # Make translated text read-only
        self.patient_translated_text.bind("<Key>", lambda e: "break")

    def _create_doctor_section(self, parent):
        """Create doctor input/output section.

        Args:
            parent: Parent widget
        """
        # Collapsible Quick Responses section
        self._quick_container = ttk.Frame(parent)
        self._quick_container.pack(fill=X, pady=(0, 10))

        # Header with toggle button
        quick_header_frame = ttk.Frame(self._quick_container)
        quick_header_frame.pack(fill=X)

        self._quick_responses_visible = tk.BooleanVar(value=True)
        self._quick_toggle_btn = ttk.Checkbutton(
            quick_header_frame,
            text="▼ Quick Responses",
            variable=self._quick_responses_visible,
            command=self._toggle_quick_responses,
            bootstyle="toolbutton"
        )
        self._quick_toggle_btn.pack(side=LEFT)

        # Content frame inside container
        self.canned_frame = ttk.Frame(self._quick_container, padding=5)
        self.canned_frame.pack(fill=X)
        self._create_canned_responses(self.canned_frame)

        # Create text areas side by side
        text_container = ttk.Frame(parent)
        text_container.pack(fill=BOTH, expand=False, pady=(0, 10))

        # Doctor response (English)
        left_frame = ttk.Frame(text_container)
        left_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 5))

        # Header with label and dictate button
        header_frame = ttk.Frame(left_frame)
        header_frame.pack(fill=X)

        ttk.Label(header_frame, text="Doctor Response (Type or dictate):", font=("", 9)).pack(side=LEFT)

        # Character count for doctor input
        self.doctor_char_count = ttk.Label(header_frame, text="0 chars", font=("", 8), foreground="gray")
        self.doctor_char_count.pack(side=RIGHT, padx=(5, 0))

        # Dictate button for voice input
        self.dictate_button = ttk.Button(
            header_frame,
            text="🎙️ Dictate",
            command=self._toggle_doctor_dictation,
            bootstyle="outline-info",
            width=10
        )
        self.dictate_button.pack(side=RIGHT, padx=(5, 0))
        ToolTip(self.dictate_button, "Click to dictate your response")

        self.is_dictating = False
        self.dictate_stop_func = None

        scroll1 = ttk.Scrollbar(left_frame)
        scroll1.pack(side=RIGHT, fill=Y)

        self.doctor_input_text = tk.Text(
            left_frame,
            wrap=tk.WORD,
            height=8,
            yscrollcommand=scroll1.set,
            font=("Consolas", 11),
            background=self.colors['doctor_input_bg'],
            foreground=self.colors['text_fg'],
            insertbackground=self.colors['text_fg']
        )
        self.doctor_input_text.pack(fill=BOTH, expand=False)
        scroll1.config(command=self.doctor_input_text.yview)

        # Bind for real-time translation
        self.doctor_input_text.bind("<KeyRelease>", self._on_doctor_text_change)

        # Translation (Patient's language)
        right_frame = ttk.Frame(text_container)
        right_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=(5, 0))

        # Header with character count
        trans_header = ttk.Frame(right_frame)
        trans_header.pack(fill=X)
        ttk.Label(trans_header, text="Translation (for Patient):", font=("", 9)).pack(side=LEFT)
        self.trans_char_count = ttk.Label(trans_header, text="0 chars", font=("", 8), foreground="gray")
        self.trans_char_count.pack(side=RIGHT)

        scroll2 = ttk.Scrollbar(right_frame)
        scroll2.pack(side=RIGHT, fill=Y)

        self.doctor_translated_text = tk.Text(
            right_frame,
            wrap=tk.WORD,
            height=8,
            yscrollcommand=scroll2.set,
            font=("Consolas", 11),
            background=self.colors['doctor_translated_bg'],
            foreground=self.colors['text_fg'],
            insertbackground=self.colors['text_fg']
        )
        self.doctor_translated_text.pack(fill=BOTH, expand=False)
        scroll2.config(command=self.doctor_translated_text.yview)

        # Make translated text read-only
        self.doctor_translated_text.bind("<Key>", lambda e: "break")

        # TTS controls
        tts_frame = ttk.Frame(parent)
        tts_frame.pack(fill=X)

        # Send button
        self.send_button = ttk.Button(
            tts_frame,
            text="📤 Send",
            command=self._send_doctor_response,
            bootstyle="primary",
            width=8,
            state=tk.DISABLED
        )
        self.send_button.pack(side=LEFT, padx=(0, 3))
        ToolTip(self.send_button, "Add response to history without playing audio (Ctrl+Enter)")

        # Preview button
        self.preview_button = ttk.Button(
            tts_frame,
            text="👂 Preview",
            command=self._preview_translation,
            bootstyle="info",
            width=10,
            state=tk.DISABLED
        )
        self.preview_button.pack(side=LEFT, padx=(0, 3))
        ToolTip(self.preview_button, "Preview translation audio")

        self.play_button = ttk.Button(
            tts_frame,
            text="🔊 Play",
            command=self._play_doctor_response,
            bootstyle="success",
            width=8,
            state=tk.DISABLED
        )
        self.play_button.pack(side=LEFT, padx=(0, 3))
        ToolTip(self.play_button, "Play translation for patient (Ctrl+P)")

        self.stop_button = ttk.Button(
            tts_frame,
            text="🛑 Stop",
            command=self._stop_playback,
            bootstyle="secondary",
            width=6,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=LEFT, padx=(0, 5))
        ToolTip(self.stop_button, "Stop audio playback")

        # Checkboxes
        self.realtime_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            tts_frame,
            text="Real-time",
            variable=self.realtime_var
        ).pack(side=LEFT, padx=(10, 0))

        self.auto_clear_var = tk.BooleanVar(value=self.auto_clear_after_send)
        ttk.Checkbutton(
            tts_frame,
            text="Auto-clear",
            variable=self.auto_clear_var,
            command=self._on_auto_clear_toggle
        ).pack(side=LEFT, padx=(5, 0))

        # Doctor translation indicator (initially hidden)
        self.doctor_translation_indicator = ttk.Label(
            tts_frame,
            text="Translating...",
            foreground="blue",
            font=("", 9, "italic")
        )

        # Output device and settings row
        output_frame = ttk.Frame(parent)
        output_frame.pack(fill=X, pady=(10, 0))

        ttk.Label(output_frame, text="Output:").pack(side=LEFT, padx=(0, 3))

        # Get available output devices
        from utils.utils import get_valid_output_devices
        output_devices = get_valid_output_devices()

        self.selected_output = tk.StringVar()
        if self.output_device and self.output_device in output_devices:
            self.selected_output.set(self.output_device)
        elif output_devices:
            if self.output_device:
                self.logger.warning(f"Saved output device '{self.output_device}' not found, using default")
            self.selected_output.set(output_devices[0])

        self.output_combo = ttk.Combobox(
            output_frame,
            textvariable=self.selected_output,
            values=output_devices,
            width=25,
            state="readonly"
        )
        self.output_combo.pack(side=LEFT, padx=(0, 10))

        # TTS Speed control
        ttk.Label(output_frame, text="Speed:").pack(side=LEFT, padx=(0, 3))
        self.speed_var = tk.DoubleVar(value=self.tts_speed)
        self.speed_scale = ttk.Scale(
            output_frame,
            from_=0.5,
            to=1.5,
            variable=self.speed_var,
            length=80,
            command=self._on_speed_change
        )
        self.speed_scale.pack(side=LEFT, padx=(0, 3))
        self.speed_label = ttk.Label(output_frame, text=f"{self.tts_speed:.1f}x", width=4)
        self.speed_label.pack(side=LEFT, padx=(0, 10))
        ToolTip(self.speed_scale, "Adjust TTS speech speed")

        # Font size control
        ttk.Label(output_frame, text="Font:").pack(side=LEFT, padx=(0, 3))
        self.font_size_var = tk.IntVar(value=self.font_size)
        font_spin = ttk.Spinbox(
            output_frame,
            from_=9,
            to=18,
            width=3,
            textvariable=self.font_size_var,
            command=self._on_font_size_change
        )
        font_spin.pack(side=LEFT, padx=(0, 10))
        ToolTip(font_spin, "Adjust text size in all text areas")

        # Service status indicators
        self.service_status_frame = ttk.Frame(output_frame)
        self.service_status_frame.pack(side=RIGHT)

        # Undo button
        self.undo_button = ttk.Button(
            output_frame,
            text="↶ Undo",
            command=self._undo_last_entry,
            bootstyle="outline-warning",
            width=7,
            state=tk.DISABLED
        )
        self.undo_button.pack(side=RIGHT, padx=(0, 10))
        ToolTip(self.undo_button, "Undo last history entry (Ctrl+Z)")

        self.translation_status = ttk.Label(
            self.service_status_frame,
            text="●",
            foreground="green",
            font=("", 10)
        )
        self.translation_status.pack(side=LEFT, padx=(0, 2))
        ToolTip(self.translation_status, "Translation service status")

        self.tts_status = ttk.Label(
            self.service_status_frame,
            text="●",
            foreground="green",
            font=("", 10)
        )
        self.tts_status.pack(side=LEFT)
        ToolTip(self.tts_status, "TTS service status")

    def _create_button_bar(self, parent):
        """Create bottom button bar.

        Args:
            parent: Parent widget
        """
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=X, pady=(15, 0))

        # Clear button
        ttk.Button(
            button_frame,
            text="Clear All",
            command=self._clear_all,
            bootstyle="warning"
        ).pack(side=LEFT, padx=(0, 10))

        # Copy buttons
        ttk.Button(
            button_frame,
            text="Copy Patient",
            command=lambda: self._copy_text(self.patient_original_text)
        ).pack(side=LEFT, padx=(0, 3))

        ttk.Button(
            button_frame,
            text="Copy Doctor",
            command=lambda: self._copy_text(self.doctor_input_text)
        ).pack(side=LEFT, padx=(0, 3))

        # Copy Both button
        copy_both_btn = ttk.Button(
            button_frame,
            text="Copy Both",
            command=self._copy_both_languages,
            bootstyle="outline-primary"
        )
        copy_both_btn.pack(side=LEFT, padx=(0, 10))
        ToolTip(copy_both_btn, "Copy original + translation together")

        # Session notes
        ttk.Label(button_frame, text="Notes:").pack(side=LEFT, padx=(0, 3))
        self.session_notes_var = tk.StringVar()
        self.session_notes_entry = ttk.Entry(
            button_frame,
            textvariable=self.session_notes_var,
            width=20
        )
        self.session_notes_entry.pack(side=LEFT, padx=(0, 10))
        ToolTip(self.session_notes_entry, "Add notes about this session")

        # Export button
        ttk.Button(
            button_frame,
            text="Export",
            command=self._export_conversation,
            bootstyle="info"
        ).pack(side=LEFT, padx=(0, 3))

        # Add to Context button
        add_context_btn = ttk.Button(
            button_frame,
            text="→ Context",
            command=self._add_to_context,
            bootstyle="success"
        )
        add_context_btn.pack(side=LEFT)
        ToolTip(add_context_btn, "Add conversation to Context Information on main screen")

        # Close button
        ttk.Button(
            button_frame,
            text="Close",
            command=self._on_close,
            bootstyle="secondary"
        ).pack(side=RIGHT)


__all__ = ["UIBuilderMixin"]
