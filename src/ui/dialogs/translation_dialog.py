"""
Translation Dialog for bidirectional medical translation.

Provides an interface for real-time translation between doctor and patient,
with STT input for patient speech and TTS output for doctor responses.
"""

import tkinter as tk
from ui.scaling_utils import ui_scaler
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import threading
import logging
from typing import Optional, Callable
from datetime import datetime

from managers.translation_manager import get_translation_manager
from managers.tts_manager import get_tts_manager
from managers.translation_session_manager import get_translation_session_manager
from audio.audio import AudioHandler
from ui.tooltip import ToolTip
from settings.settings import SETTINGS
from models.translation_session import TranslationEntry, Speaker


class TranslationDialog:
    """Dialog for bidirectional translation with STT/TTS support."""
    
    def __init__(self, parent, audio_handler: AudioHandler):
        """Initialize the translation dialog.
        
        Args:
            parent: Parent window
            audio_handler: Audio handler for recording (reference for API keys)
        """
        self.parent = parent
        # Create a separate audio handler instance for translation
        self.audio_handler = AudioHandler(
            elevenlabs_api_key=audio_handler.elevenlabs_api_key,
            deepgram_api_key=audio_handler.deepgram_api_key,
            recognition_language=audio_handler.recognition_language,
            groq_api_key=audio_handler.groq_api_key
        )
        self.translation_manager = get_translation_manager()
        self.tts_manager = get_tts_manager()
        self.session_manager = get_translation_session_manager()

        self.dialog = None
        self.is_recording = False
        self.stop_recording_func = None
        self.audio_segments = []  # Store audio segments like SOAP recording
        
        # Get language and device settings
        translation_settings = SETTINGS.get("translation", {})
        self.patient_language = translation_settings.get("patient_language", "es")
        self.doctor_language = translation_settings.get("doctor_language", "en")
        self.input_device = translation_settings.get("input_device", "")
        self.output_device = translation_settings.get("output_device", "")
        
        self.logger = logging.getLogger(__name__)
    
    def _hide_all_tooltips(self):
        """Hide all active tooltips in the application."""
        try:
            # Move mouse out of any widget to trigger tooltip hiding
            # First, get the widget under the mouse
            widget_under_mouse = self.parent.winfo_containing(
                self.parent.winfo_pointerx(),
                self.parent.winfo_pointery()
            )
            
            if widget_under_mouse:
                # Generate a Leave event on that widget
                widget_under_mouse.event_generate("<Leave>")
            
            # Additionally, destroy any tooltip windows
            # Tooltips are Toplevel windows with overrideredirect set to True
            root = self.parent.winfo_toplevel()
            for child in root.children.values():
                if isinstance(child, tk.Toplevel):
                    try:
                        # Tooltip windows have overrideredirect set to True
                        # and typically have a yellow background
                        if child.wm_overrideredirect():
                            child.destroy()
                    except tk.TclError:
                        # Window might already be destroyed
                        pass
        except Exception as e:
            self.logger.debug(f"Error hiding tooltips: {e}")
    
    def show(self):
        """Show the translation dialog."""
        # Hide any active tooltips
        self._hide_all_tooltips()
            
        # Create dialog window
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Bidirectional Translation Assistant")
        
        # Get screen dimensions
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        
        # Set dialog size - reduced now that doctor text areas are smaller
        dialog_width = int(screen_width * 0.85)  # Use 85% of screen width
        dialog_height = int(screen_height * 0.80)  # Use 80% of screen height
        
        self.dialog.geometry(f"{dialog_width}x{dialog_height}")
        self.dialog.minsize(1200, 700)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        
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

        # Patient section (top of left pane)
        patient_frame = ttk.Labelframe(left_frame, text="Patient", padding=10)
        patient_frame.pack(fill=BOTH, expand=True, pady=(0, 10))
        self._create_patient_section(patient_frame)

        # Doctor section (bottom of left pane)
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
        # Recording toggle (Ctrl+R)
        self.dialog.bind('<Control-r>', lambda e: self._toggle_recording())
        self.dialog.bind('<Control-R>', lambda e: self._toggle_recording())

        # Stop recording (Escape)
        self.dialog.bind('<Escape>', lambda e: self._stop_recording() if self.is_recording else None)

        # Play response (Ctrl+P)
        self.dialog.bind('<Control-p>', lambda e: self._play_doctor_response())
        self.dialog.bind('<Control-P>', lambda e: self._play_doctor_response())

        # Export session (Ctrl+E)
        self.dialog.bind('<Control-e>', lambda e: self._export_session())
        self.dialog.bind('<Control-E>', lambda e: self._export_session())

        # New session (Ctrl+N)
        self.dialog.bind('<Control-n>', lambda e: self._start_new_session())
        self.dialog.bind('<Control-N>', lambda e: self._start_new_session())
    
    def _create_language_bar(self, parent):
        """Create language selection controls.
        
        Args:
            parent: Parent widget
        """
        lang_frame = ttk.Frame(parent)
        lang_frame.pack(fill=X)
        
        # Patient language selection
        ttk.Label(lang_frame, text="Patient Language:", font=("", 10, "bold")).pack(side=LEFT, padx=(0, 5))
        
        # Get supported languages
        languages = self.translation_manager.get_supported_languages()
        lang_names = [f"{lang[1]} ({lang[0]})" for lang in languages]
        lang_codes = [lang[0] for lang in languages]
        
        self.patient_lang_var = tk.StringVar(value=self.patient_language)
        self.patient_combo = ttk.Combobox(
            lang_frame,
            textvariable=self.patient_lang_var,
            values=lang_names,  # Use lang_names instead of lang_codes
            state="readonly",
            width=20  # Increase width to accommodate language names
        )
        self.patient_combo.pack(side=LEFT, padx=(0, 20))
        
        # Set display value
        try:
            idx = lang_codes.index(self.patient_language)
            self.patient_combo.set(lang_names[idx])
        except (ValueError, IndexError):
            self.patient_combo.set(self.patient_language)

        self.patient_combo.bind("<<ComboboxSelected>>", self._on_patient_language_change)

        # Arrow indicator
        ttk.Label(lang_frame, text="⟷", font=("", 16)).pack(side=LEFT, padx=20)

        # Doctor language selection
        ttk.Label(lang_frame, text="Doctor Language:", font=("", 10, "bold")).pack(side=LEFT, padx=(0, 5))

        self.doctor_lang_var = tk.StringVar(value=self.doctor_language)
        self.doctor_combo = ttk.Combobox(
            lang_frame,
            textvariable=self.doctor_lang_var,
            values=lang_names,  # Use lang_names instead of lang_codes
            state="readonly",
            width=20  # Increase width to accommodate language names
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
            # Use saved preference if available
            self.selected_microphone.set(self.input_device)
        elif microphones:
            # Default to first available
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
        
        self.record_button = ttk.Button(
            control_frame,
            text="🎤 Record Patient",
            command=self._toggle_recording,
            bootstyle="danger",
            width=20
        )
        self.record_button.pack(side=LEFT, padx=(0, 10))
        
        self.recording_status = ttk.Label(control_frame, text="")
        self.recording_status.pack(side=LEFT)
        
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
            wrap=WORD,
            height=10,
            yscrollcommand=scroll1.set,
            font=("Consolas", 11)
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
            wrap=WORD,
            height=10,
            yscrollcommand=scroll2.set,
            font=("Consolas", 11),
            background="#f0f8ff"  # Light blue background
        )
        self.patient_translated_text.pack(fill=BOTH, expand=True)
        scroll2.config(command=self.patient_translated_text.yview)
        
        # Make translated text read-only
        self.patient_translated_text.bind("<Key>", lambda e: "break")
    
    def _create_canned_responses(self, parent):
        """Create canned response buttons for common medical phrases.
        
        Args:
            parent: Parent widget
        """
        # Container for responses and manage button
        container = ttk.Frame(parent)
        container.pack(fill=BOTH, expand=True)
        
        # Header with manage button
        header_frame = ttk.Frame(container)
        header_frame.pack(fill=X, pady=(0, 5))
        
        # Manage button on the right
        manage_btn = ttk.Button(
            header_frame,
            text="⚙ Manage",
            command=self._manage_canned_responses,
            bootstyle="secondary",
            width=10
        )
        manage_btn.pack(side=RIGHT)
        ToolTip(manage_btn, "Add, edit, or delete quick responses")
        
        # Responses frame
        responses_frame = ttk.Frame(container)
        responses_frame.pack(fill=BOTH, expand=True)
        
        # Store reference for refresh
        self.canned_responses_frame = responses_frame
        
        # Populate responses
        self._populate_canned_responses()
    
    def _populate_canned_responses(self):
        """Populate the canned responses from settings."""
        # Clear existing buttons
        for widget in self.canned_responses_frame.winfo_children():
            widget.destroy()
        
        # Get responses from settings
        canned_settings = SETTINGS.get("translation_canned_responses", {})
        responses = canned_settings.get("responses", {})
        
        if not responses:
            # No responses configured
            ttk.Label(
                self.canned_responses_frame,
                text="No quick responses configured. Click 'Manage' to add some.",
                foreground="gray"
            ).pack(pady=20)
            return
        
        # Create buttons in a grid layout
        row = 0
        col = 0
        max_cols = 3
        
        for response_text, category in sorted(responses.items()):
            btn = ttk.Button(
                self.canned_responses_frame,
                text=response_text[:25] + "..." if len(response_text) > 25 else response_text,
                command=lambda text=response_text: self._insert_canned_response(text),
                bootstyle="outline-primary",
                width=30
            )
            btn.grid(row=row, column=col, padx=2, pady=2, sticky="ew")
            
            # Add tooltip with full text
            ToolTip(btn, response_text)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        # Configure grid weights for responsive layout
        for i in range(max_cols):
            self.canned_responses_frame.columnconfigure(i, weight=1)
    
    def _manage_canned_responses(self):
        """Open the canned responses management dialog."""
        from ui.dialogs.canned_responses_dialog import CannedResponsesDialog
        
        dialog = CannedResponsesDialog(self.dialog)
        if dialog.show():
            # Responses were updated, refresh the display
            self._populate_canned_responses()
    
    def _insert_canned_response(self, text):
        """Insert a canned response into the doctor input field.
        
        Args:
            text: Text to insert
        """
        # Get current content
        current_text = self.doctor_input_text.get("1.0", tk.END).strip()
        
        # Add the canned response
        if current_text:
            # If there's existing text, add a space and the new text
            self.doctor_input_text.insert(tk.END, " " + text)
        else:
            # If empty, just insert the text
            self.doctor_input_text.insert("1.0", text)
        
        # Trigger translation update
        self._on_doctor_text_change()
        
        # Focus on the text field
        self.doctor_input_text.focus_set()
        # Move cursor to end
        self.doctor_input_text.mark_set(tk.INSERT, tk.END)
    
    def _create_doctor_section(self, parent):
        """Create doctor input/output section.
        
        Args:
            parent: Parent widget
        """
        # Create canned responses frame
        canned_frame = ttk.Labelframe(parent, text="Quick Responses", padding=5)
        canned_frame.pack(fill=X, pady=(0, 10))
        self._create_canned_responses(canned_frame)
        
        # Create text areas side by side
        text_container = ttk.Frame(parent)
        text_container.pack(fill=BOTH, expand=False, pady=(0, 10))
        
        # Doctor response (English)
        left_frame = ttk.Frame(text_container)
        left_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 5))
        
        ttk.Label(left_frame, text="Doctor Response (Type here):", font=("", 9)).pack(anchor=W)
        
        scroll1 = ttk.Scrollbar(left_frame)
        scroll1.pack(side=RIGHT, fill=Y)
        
        self.doctor_input_text = tk.Text(
            left_frame,
            wrap=WORD,
            height=8,
            yscrollcommand=scroll1.set,
            font=("Consolas", 11),
            background="#f0fff0"  # Light green background
        )
        self.doctor_input_text.pack(fill=BOTH, expand=False)
        scroll1.config(command=self.doctor_input_text.yview)
        
        # Bind for real-time translation
        self.doctor_input_text.bind("<KeyRelease>", self._on_doctor_text_change)
        
        # Translation (Patient's language)
        right_frame = ttk.Frame(text_container)
        right_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=(5, 0))
        
        ttk.Label(right_frame, text="Translation (for Patient):", font=("", 9)).pack(anchor=W)
        
        scroll2 = ttk.Scrollbar(right_frame)
        scroll2.pack(side=RIGHT, fill=Y)
        
        self.doctor_translated_text = tk.Text(
            right_frame,
            wrap=WORD,
            height=8,
            yscrollcommand=scroll2.set,
            font=("Consolas", 11),
            background="#fff0f5"  # Light pink background
        )
        self.doctor_translated_text.pack(fill=BOTH, expand=False)
        scroll2.config(command=self.doctor_translated_text.yview)
        
        # Make translated text read-only
        self.doctor_translated_text.bind("<Key>", lambda e: "break")
        
        # TTS controls
        tts_frame = ttk.Frame(parent)
        tts_frame.pack(fill=X)
        
        self.play_button = ttk.Button(
            tts_frame,
            text="🔊 Play for Patient",
            command=self._play_doctor_response,
            bootstyle="success",
            width=20
        )
        self.play_button.pack(side=LEFT, padx=(0, 10))
        
        ttk.Button(
            tts_frame,
            text="🛑 Stop",
            command=self._stop_playback,
            bootstyle="secondary",
            width=10
        ).pack(side=LEFT, padx=(0, 10))
        
        # Real-time translation checkbox
        self.realtime_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            tts_frame,
            text="Real-time translation",
            variable=self.realtime_var
        ).pack(side=LEFT, padx=(20, 0))
        
        # Output device selection
        output_frame = ttk.Frame(parent)
        output_frame.pack(fill=X, pady=(10, 0))
        
        ttk.Label(output_frame, text="Output Device:").pack(side=LEFT, padx=(0, 5))
        
        # Get available output devices
        from utils.utils import get_valid_output_devices
        output_devices = get_valid_output_devices()
        
        self.selected_output = tk.StringVar()
        if self.output_device and self.output_device in output_devices:
            # Use saved preference if available
            self.selected_output.set(self.output_device)
        elif output_devices:
            # Default to first available
            if self.output_device:
                self.logger.warning(f"Saved output device '{self.output_device}' not found, using default")
            self.selected_output.set(output_devices[0])
        
        self.output_combo = ttk.Combobox(
            output_frame,
            textvariable=self.selected_output,
            values=output_devices,
            width=30,
            state="readonly"
        )
        self.output_combo.pack(side=LEFT)
    
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
            text="Copy Patient Original",
            command=lambda: self._copy_text(self.patient_original_text)
        ).pack(side=LEFT, padx=(0, 5))
        
        ttk.Button(
            button_frame,
            text="Copy Doctor Response",
            command=lambda: self._copy_text(self.doctor_input_text)
        ).pack(side=LEFT, padx=(0, 20))
        
        # Export button
        ttk.Button(
            button_frame,
            text="Export Conversation",
            command=self._export_conversation,
            bootstyle="info"
        ).pack(side=LEFT)
        
        # Close button
        ttk.Button(
            button_frame,
            text="Close",
            command=self._on_close,
            bootstyle="secondary"
        ).pack(side=RIGHT)
    
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
                phrase_time_limit=3,  # Same as SOAP recording for consistent behavior
                stream_purpose="translation"  # Use dedicated stream purpose
            )
            
            # Play start sound
            if hasattr(self.parent, 'play_recording_sound'):
                self.parent.play_recording_sound(start=True)
                
        except Exception as e:
            self.logger.error(f"Failed to start recording: {e}")
            self.is_recording = False
            self.recording_status.config(text=f"Error: {str(e)}", foreground="red")
            self.record_button.config(text="🎤 Record Patient", bootstyle="danger")
    
    def _stop_recording(self):
        """Stop recording and process the audio."""
        if not self.is_recording or not self.stop_recording_func:
            return
        
        # Update UI immediately
        self.is_recording = False
        self.record_button.config(text="🎤 Record Patient", bootstyle="danger")
        self.recording_status.config(text="Processing...", foreground="blue")
        
        # Stop recording in thread
        def stop_and_process():
            try:
                # Stop recording first
                self.stop_recording_func()
                self.stop_recording_func = None
                
                # Play stop sound
                if hasattr(self.parent, 'play_recording_sound'):
                    self.parent.play_recording_sound(start=False)
                
                # Process accumulated audio segments
                if self.audio_segments:
                    # Combine all segments
                    combined = self.audio_handler.combine_audio_segments(self.audio_segments)
                    
                    if combined:
                        # Update status
                        self.dialog.after(0, lambda: self.recording_status.config(
                            text="Transcribing...", foreground="blue"
                        ))
                        
                        # Transcribe without prefix
                        transcript = self.audio_handler.transcribe_audio_without_prefix(combined)
                        
                        if transcript:
                            # Process the complete transcript
                            self.dialog.after(0, lambda: self._process_patient_speech(transcript))
                        else:
                            self.dialog.after(0, lambda: self.recording_status.config(
                                text="No speech detected", foreground="orange"
                            ))
                    else:
                        self.dialog.after(0, lambda: self.recording_status.config(
                            text="No audio captured", foreground="orange"
                        ))
                else:
                    self.dialog.after(0, lambda: self.recording_status.config(
                        text="No audio captured", foreground="orange"
                    ))
                    
            except Exception as e:
                self.logger.error(f"Error processing recording: {e}")
                self.dialog.after(0, lambda: self.recording_status.config(
                    text=f"Error: {str(e)}", foreground="red"
                ))
        
        # Start processing thread
        threading.Thread(target=stop_and_process, daemon=True).start()
    
    def _on_audio_data(self, audio_data):
        """Handle incoming audio data during recording.
        
        This callback receives complete audio segments when silence is detected
        or phrase_time_limit is reached, similar to SOAP recording.
        
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
                
                # Update recording duration
                total_duration = sum(seg.duration_seconds for seg in self.audio_segments)
                self.dialog.after(0, lambda: self.recording_status.config(
                    text=f"Recording... {total_duration:.1f}s", foreground="red"
                ))
                
        except Exception as e:
            self.logger.error(f"Error processing audio data: {e}")
    
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
        
        def translate():
            try:
                self.logger.debug(f"Translating from {self.patient_language} to {self.doctor_language}")
                translated = self.translation_manager.translate(
                    transcript,
                    source_lang=self.patient_language,
                    target_lang=self.doctor_language
                )

                # Add entry to session history
                def update_ui():
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
                        self.logger.error(f"Failed to add history entry: {he}")

                # Update UI on main thread
                self.dialog.after(0, update_ui)

            except Exception as e:
                self.logger.error(f"Translation failed: {e}")
                self.dialog.after(0, lambda: self.recording_status.config(
                    text=f"Translation error: {str(e)}", foreground="red"
                ))

        # Start translation thread
        threading.Thread(target=translate, daemon=True).start()
    
    def _on_doctor_text_change(self, event=None):
        """Handle doctor text input change for real-time translation."""
        if not self.realtime_var.get():
            return
        
        # Get current text
        text = self.doctor_input_text.get("1.0", tk.END).strip()
        
        if not text:
            self.doctor_translated_text.delete("1.0", tk.END)
            return
        
        # Cancel previous translation timer if exists
        if hasattr(self, '_translation_timer'):
            self.dialog.after_cancel(self._translation_timer)
        
        # Set new timer for translation (debounce - 300ms for responsive feel)
        self._translation_timer = self.dialog.after(300, lambda: self._translate_doctor_text(text))
    
    def _translate_doctor_text(self, text: str):
        """Translate doctor's text to patient's language.
        
        Args:
            text: Text to translate
        """
        def translate():
            try:
                self.logger.debug(f"Translating from {self.doctor_language} to {self.patient_language}")
                translated = self.translation_manager.translate(
                    text,
                    source_lang=self.doctor_language,
                    target_lang=self.patient_language
                )
                
                # Update UI on main thread
                self.dialog.after(0, lambda: [
                    self.doctor_translated_text.delete("1.0", tk.END),
                    self.doctor_translated_text.insert("1.0", translated)
                ])
                
            except Exception as e:
                self.logger.error(f"Translation failed: {e}")
        
        # Start translation thread
        threading.Thread(target=translate, daemon=True).start()
    
    def _play_doctor_response(self):
        """Play the translated doctor response using TTS."""
        # Get texts
        original_text = self.doctor_input_text.get("1.0", tk.END).strip()
        translated_text = self.doctor_translated_text.get("1.0", tk.END).strip()

        if not translated_text:
            return

        # Add doctor entry to history (when they send the response)
        try:
            entry = self.session_manager.add_doctor_entry(
                original_text=original_text,
                original_language=self.doctor_language,
                translated_text=translated_text,
                target_language=self.patient_language
            )
            self._add_history_entry(entry)
        except Exception as e:
            self.logger.error(f"Failed to add doctor entry to history: {e}")

        # Disable play button
        self.play_button.config(state=DISABLED, text="Playing...")
        
        def synthesize_and_play():
            try:
                # Synthesize and play with selected output device
                self.tts_manager.synthesize_and_play(
                    text,
                    language=self.patient_language,
                    blocking=True,  # Wait for completion
                    output_device=self.selected_output.get()  # Pass selected output device
                )
                
                # Re-enable button on main thread
                self.dialog.after(0, lambda: self.play_button.config(
                    state=NORMAL, text="🔊 Play for Patient"
                ))
                
            except Exception as e:
                self.logger.error(f"TTS playback failed: {e}")
                self.dialog.after(0, lambda: [
                    self.play_button.config(state=NORMAL, text="🔊 Play for Patient"),
                    self.recording_status.config(
                        text=f"Playback error: {str(e)}", foreground="red"
                    )
                ])
        
        # Start TTS thread
        threading.Thread(target=synthesize_and_play, daemon=True).start()
    
    def _stop_playback(self):
        """Stop any ongoing TTS playback."""
        try:
            self.tts_manager.stop_playback()
        except Exception as e:
            self.logger.error(f"Failed to stop playback: {e}")
    
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
                self.recording_status.config(text="Copied to clipboard", foreground="green")
        except Exception as e:
            self.logger.error(f"Copy failed: {e}")
    
    def _export_conversation(self):
        """Export the conversation to a file."""
        from tkinter import filedialog
        
        # Get save location
        filename = filedialog.asksaveasfilename(
            parent=self.dialog,
            title="Export Conversation",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if not filename:
            return
        
        try:
            # Build conversation text
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            content = f"Translation Conversation Export\n"
            content += f"Generated: {timestamp}\n"
            content += f"Patient Language: {self.patient_language}\n"
            content += f"Doctor Language: {self.doctor_language}\n"
            content += "=" * 60 + "\n\n"
            
            # Patient section
            patient_original = self.patient_original_text.get("1.0", tk.END).strip()
            patient_translated = self.patient_translated_text.get("1.0", tk.END).strip()
            
            if patient_original:
                content += f"PATIENT (Original - {self.patient_language}):\n"
                content += patient_original + "\n\n"
                content += f"PATIENT (Translated - {self.doctor_language}):\n"
                content += patient_translated + "\n\n"
            
            # Doctor section
            doctor_original = self.doctor_input_text.get("1.0", tk.END).strip()
            doctor_translated = self.doctor_translated_text.get("1.0", tk.END).strip()
            
            if doctor_original:
                content += f"DOCTOR (Original - {self.doctor_language}):\n"
                content += doctor_original + "\n\n"
                content += f"DOCTOR (Translated - {self.patient_language}):\n"
                content += doctor_translated + "\n\n"
            
            # Save to file
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.recording_status.config(text="Conversation exported", foreground="green")
            
        except Exception as e:
            self.logger.error(f"Export failed: {e}")
            self.recording_status.config(text=f"Export error: {str(e)}", foreground="red")
    
    def _on_patient_language_change(self, event=None):
        """Handle patient language selection change."""
        # Extract language code from display value
        selected = self.patient_lang_var.get()
        
        # Get the language code from the formatted string "Language Name (code)"
        # We need to handle special cases like "Chinese (Simplified) (zh-CN)"
        if selected.endswith(')'):
            # Find the last occurrence of '(' to get the language code
            last_paren = selected.rfind('(')
            if last_paren != -1:
                self.patient_language = selected[last_paren+1:-1]
            else:
                self.patient_language = selected
        else:
            self.patient_language = selected
        
        self.logger.debug(f"Patient language changed to: {self.patient_language} (from: {selected})")
    
    def _on_doctor_language_change(self, event=None):
        """Handle doctor language selection change."""
        # Extract language code from display value
        selected = self.doctor_lang_var.get()
        
        # Get the language code from the formatted string "Language Name (code)"
        # We need to handle special cases like "Chinese (Simplified) (zh-CN)"
        if selected.endswith(')'):
            # Find the last occurrence of '(' to get the language code
            last_paren = selected.rfind('(')
            if last_paren != -1:
                self.doctor_language = selected[last_paren+1:-1]
            else:
                self.doctor_language = selected
        else:
            self.doctor_language = selected
        
        self.logger.debug(f"Doctor language changed to: {self.doctor_language} (from: {selected})")
    
    def _on_close(self):
        """Handle dialog close."""
        # Stop any ongoing recording
        if self.is_recording:
            self._stop_recording()

        # Stop any TTS playback
        self._stop_playback()

        # End the current session
        try:
            self.session_manager.end_session()
        except Exception as e:
            self.logger.error(f"Error ending translation session: {e}")

        # Clean up audio handler
        try:
            self.audio_handler.cleanup()
        except Exception as e:
            self.logger.error(f"Error cleaning up audio handler: {e}")

        # Save language and device preferences
        SETTINGS["translation"]["patient_language"] = self.patient_language
        SETTINGS["translation"]["doctor_language"] = self.doctor_language
        SETTINGS["translation"]["input_device"] = self.selected_microphone.get()
        SETTINGS["translation"]["output_device"] = self.selected_output.get()

        # Destroy dialog
        self.dialog.destroy()

    def _create_history_panel(self, parent):
        """Create the conversation history panel.

        Args:
            parent: Parent widget for the history panel
        """
        # History frame with labelframe styling
        history_frame = ttk.Labelframe(parent, text="Conversation History", padding=10)
        history_frame.pack(fill=BOTH, expand=True)

        # Header with controls
        header_frame = ttk.Frame(history_frame)
        header_frame.pack(fill=X, pady=(0, 10))

        ttk.Button(
            header_frame,
            text="New Session",
            command=self._start_new_session,
            bootstyle="outline-primary",
            width=12
        ).pack(side=LEFT, padx=(0, 5))

        ttk.Button(
            header_frame,
            text="Export",
            command=self._export_session,
            bootstyle="outline-info",
            width=10
        ).pack(side=LEFT)

        # Create canvas for scrollable history
        canvas_frame = ttk.Frame(history_frame)
        canvas_frame.pack(fill=BOTH, expand=True)

        self.history_canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        history_scrollbar = ttk.Scrollbar(
            canvas_frame,
            orient=VERTICAL,
            command=self.history_canvas.yview
        )

        # Create frame inside canvas for entries
        self.history_entries_frame = ttk.Frame(self.history_canvas)

        # Configure canvas window
        self.history_window = self.history_canvas.create_window(
            (0, 0),
            window=self.history_entries_frame,
            anchor=NW
        )

        # Pack scrollbar and canvas
        history_scrollbar.pack(side=RIGHT, fill=Y)
        self.history_canvas.pack(side=LEFT, fill=BOTH, expand=True)

        # Configure scrolling
        self.history_canvas.configure(yscrollcommand=history_scrollbar.set)

        # Bind events for scrolling
        self.history_entries_frame.bind("<Configure>", self._on_history_frame_configure)
        self.history_canvas.bind("<Configure>", self._on_history_canvas_configure)

        # Bind mouse wheel scrolling
        self.history_canvas.bind_all("<MouseWheel>", self._on_history_mousewheel)
        self.history_canvas.bind_all("<Button-4>", self._on_history_mousewheel)
        self.history_canvas.bind_all("<Button-5>", self._on_history_mousewheel)

        # Welcome message
        self._add_history_welcome()

    def _on_history_frame_configure(self, event):
        """Update scroll region when history frame size changes."""
        self.history_canvas.configure(scrollregion=self.history_canvas.bbox("all"))

    def _on_history_canvas_configure(self, event):
        """Update window width when canvas size changes."""
        self.history_canvas.itemconfig(self.history_window, width=event.width)

    def _on_history_mousewheel(self, event):
        """Handle mouse wheel scrolling in history panel."""
        if event.num == 4 or event.delta > 0:
            self.history_canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.history_canvas.yview_scroll(1, "units")

    def _add_history_welcome(self):
        """Add welcome message to history panel."""
        welcome_frame = ttk.Frame(self.history_entries_frame, padding=10)
        welcome_frame.pack(fill=X, pady=5)

        ttk.Label(
            welcome_frame,
            text="Session started",
            font=("", 9, "italic"),
            foreground="gray"
        ).pack(anchor=W)

        ttk.Label(
            welcome_frame,
            text=f"Patient: {self.patient_language} | Doctor: {self.doctor_language}",
            font=("", 8),
            foreground="gray"
        ).pack(anchor=W)

    def _add_history_entry(self, entry: TranslationEntry):
        """Add a translation entry to the history panel.

        Args:
            entry: TranslationEntry to display
        """
        # Create entry frame
        entry_frame = ttk.Frame(self.history_entries_frame, padding=5)
        entry_frame.pack(fill=X, pady=2, padx=2)

        # Speaker color
        speaker_color = "#0066cc" if entry.speaker == Speaker.DOCTOR else "#cc6600"
        speaker_label = entry.speaker.value.title()

        # Header row with speaker and time
        header_frame = ttk.Frame(entry_frame)
        header_frame.pack(fill=X)

        ttk.Label(
            header_frame,
            text=speaker_label,
            foreground=speaker_color,
            font=("", 9, "bold")
        ).pack(side=LEFT)

        time_str = entry.timestamp.strftime("%H:%M:%S")
        ttk.Label(
            header_frame,
            text=time_str,
            foreground="gray",
            font=("", 8)
        ).pack(side=RIGHT)

        # Original text
        ttk.Label(
            entry_frame,
            text=f"[{entry.original_language}] {entry.original_text}",
            wraplength=250,
            font=("", 9),
            justify=LEFT
        ).pack(fill=X, anchor=W)

        # Translated text
        display_translation = entry.llm_refined_text or entry.translated_text
        ttk.Label(
            entry_frame,
            text=f"[{entry.target_language}] {display_translation}",
            wraplength=250,
            font=("", 9),
            foreground="gray",
            justify=LEFT
        ).pack(fill=X, anchor=W)

        # Separator
        ttk.Separator(entry_frame, orient=HORIZONTAL).pack(fill=X, pady=(5, 0))

        # Auto-scroll to bottom
        self.history_canvas.update_idletasks()
        self.history_canvas.yview_moveto(1.0)

    def _start_new_session(self):
        """Start a new translation session."""
        # End any existing session
        if self.session_manager.current_session:
            self.session_manager.end_session()

        # Clear history display
        for widget in self.history_entries_frame.winfo_children():
            widget.destroy()

        # Start new session
        self.session_manager.start_session(
            patient_language=self.patient_language,
            doctor_language=self.doctor_language
        )

        # Add welcome message
        self._add_history_welcome()

        # Clear current text areas
        self._clear_all()

        self.logger.info("Started new translation session")

    def _export_session(self):
        """Export the current session to a file."""
        if not self.session_manager.current_session:
            from tkinter import messagebox
            messagebox.showwarning(
                "No Session",
                "No active translation session to export.",
                parent=self.dialog
            )
            return

        from tkinter import filedialog

        # Get save location
        filename = filedialog.asksaveasfilename(
            parent=self.dialog,
            title="Export Session",
            defaultextension=".txt",
            filetypes=[
                ("Text files", "*.txt"),
                ("JSON files", "*.json"),
                ("All files", "*.*")
            ]
        )

        if not filename:
            return

        try:
            # Determine format from extension
            if filename.endswith('.json'):
                content = self.session_manager.export_session(
                    self.session_manager.current_session.session_id,
                    format="json"
                )
            else:
                content = self.session_manager.export_session(
                    self.session_manager.current_session.session_id,
                    format="txt"
                )

            if content:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)

                from tkinter import messagebox
                messagebox.showinfo(
                    "Export Complete",
                    f"Session exported to:\n{filename}",
                    parent=self.dialog
                )
            else:
                raise ValueError("Failed to generate export content")

        except Exception as e:
            self.logger.error(f"Export failed: {e}")
            from tkinter import messagebox
            messagebox.showerror(
                "Export Failed",
                f"Failed to export session:\n{str(e)}",
                parent=self.dialog
            )