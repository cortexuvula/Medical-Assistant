"""
Voice Mode UI Components for Advanced Voice Interaction

Provides the UI interface for voice mode functionality in the Medical Assistant.
"""

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from typing import Optional, Callable, Dict, Any
import logging
from datetime import datetime
import threading
import time

from ui.tooltip import ToolTip
from voice.voice_interaction_manager import ConversationState


class VoiceModeUI:
    """Manages the Voice Mode UI components."""
    
    def __init__(self, parent_frame: ttk.Frame, app):
        """Initialize Voice Mode UI.
        
        Args:
            parent_frame: Parent frame for the UI
            app: Reference to main application
        """
        self.parent_frame = parent_frame
        self.app = app
        
        # UI Components
        self.voice_button = None
        self.status_label = None
        self.conversation_text = None
        self.settings_frame = None
        self.volume_slider = None
        self.volume_label = None
        self.interrupt_button = None
        
        # State
        self.is_active = False
        self.current_state = ConversationState.IDLE
        
        # Animation
        self.pulse_animation_id = None
        self.pulse_state = 0
        
        # Create UI
        self.create_voice_interface()
        
    def create_voice_interface(self):
        """Create the voice mode interface."""
        # Main container with padding
        main_container = ttk.Frame(self.parent_frame)
        main_container.pack(fill=BOTH, expand=True, padx=20, pady=10)
        
        # Top section - Controls
        self._create_control_section(main_container)
        
        # Middle section - Conversation display
        self._create_conversation_section(main_container)
        
        # Bottom section - Settings
        self._create_settings_section(main_container)
        
    def _create_control_section(self, parent):
        """Create the control section with voice button and status.
        
        Args:
            parent: Parent widget
        """
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=X, pady=(0, 20))
        
        # Center container for controls
        center_container = ttk.Frame(control_frame)
        center_container.pack(expand=True)
        
        # Large voice activation button
        button_frame = ttk.Frame(center_container)
        button_frame.pack(pady=10)
        
        self.voice_button = ttk.Button(
            button_frame,
            text="🎤 Start Voice Mode",
            command=self._toggle_voice_mode,
            style="Voice.TButton",
            width=20
        )
        self.voice_button.pack()
        
        # Add custom style for the voice button
        style = ttk.Style()
        style.configure(
            "Voice.TButton",
            font=("Arial", 16, "bold"),
            padding=(20, 15)
        )
        
        # Status label
        self.status_label = ttk.Label(
            center_container,
            text="Ready to start voice conversation",
            font=("Arial", 12)
        )
        self.status_label.pack(pady=(10, 0))
        
        # Visual indicator frame
        indicator_frame = ttk.Frame(center_container)
        indicator_frame.pack(pady=10)
        
        # Create animated status indicator
        self.status_indicator = tk.Canvas(
            indicator_frame,
            width=20,
            height=20,
            highlightthickness=0
        )
        self.status_indicator.pack()
        self._update_status_indicator()
        
        # Interrupt button (hidden by default)
        self.interrupt_button = ttk.Button(
            center_container,
            text="⏸ Interrupt",
            command=self._interrupt_voice,
            style="Danger.TButton",
            state=DISABLED
        )
        self.interrupt_button.pack(pady=5)
        self.interrupt_button.pack_forget()  # Hide initially
        
    def _create_conversation_section(self, parent):
        """Create the conversation display section.
        
        Args:
            parent: Parent widget
        """
        # Conversation frame with border
        conv_frame = ttk.LabelFrame(
            parent,
            text="Conversation",
            padding=15
        )
        conv_frame.pack(fill=BOTH, expand=True, pady=(0, 20))
        
        # Scrolled text for conversation history
        text_frame = ttk.Frame(conv_frame)
        text_frame.pack(fill=BOTH, expand=True)
        
        # Create text widget with scrollbar
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        self.conversation_text = tk.Text(
            text_frame,
            wrap=WORD,
            height=20,
            font=("Arial", 11),
            yscrollcommand=scrollbar.set
        )
        self.conversation_text.pack(side=LEFT, fill=BOTH, expand=True)
        
        scrollbar.config(command=self.conversation_text.yview)
        
        # Configure text tags for different speakers
        self.conversation_text.tag_configure(
            "user",
            foreground="#0066cc",
            font=("Arial", 11, "bold")
        )
        self.conversation_text.tag_configure(
            "assistant",
            foreground="#006600",
            font=("Arial", 11, "bold")
        )
        self.conversation_text.tag_configure(
            "system",
            foreground="#666666",
            font=("Arial", 10, "italic")
        )
        self.conversation_text.tag_configure(
            "timestamp",
            foreground="#999999",
            font=("Arial", 9)
        )
        
        # Initially read-only
        self.conversation_text.config(state=DISABLED)
        
        # Action buttons below conversation
        action_frame = ttk.Frame(conv_frame)
        action_frame.pack(fill=X, pady=(10, 0))
        
        ttk.Button(
            action_frame,
            text="Clear Conversation",
            command=self._clear_conversation,
            style="Secondary.TButton"
        ).pack(side=LEFT, padx=(0, 10))
        
        ttk.Button(
            action_frame,
            text="Export Transcript",
            command=self._export_transcript,
            style="Secondary.TButton"
        ).pack(side=LEFT, padx=(0, 10))
        
        ttk.Button(
            action_frame,
            text="Copy to Context",
            command=self._copy_to_context,
            style="Secondary.TButton"
        ).pack(side=LEFT)
        
    def _create_settings_section(self, parent):
        """Create the settings section.
        
        Args:
            parent: Parent widget
        """
        settings_frame = ttk.LabelFrame(
            parent,
            text="Voice Settings",
            padding=15
        )
        settings_frame.pack(fill=X)
        
        # Create two columns
        left_col = ttk.Frame(settings_frame)
        left_col.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 20))
        
        right_col = ttk.Frame(settings_frame)
        right_col.pack(side=LEFT, fill=BOTH, expand=True)
        
        # Left column - Audio settings
        ttk.Label(left_col, text="Audio Settings", font=("Arial", 10, "bold")).pack(anchor=W)
        
        # Volume control
        volume_frame = ttk.Frame(left_col)
        volume_frame.pack(fill=X, pady=(10, 0))
        
        ttk.Label(volume_frame, text="Volume:").pack(side=LEFT, padx=(0, 10))
        
        self.volume_slider = ttk.Scale(
            volume_frame,
            from_=0,
            to=100,
            orient=HORIZONTAL,
            command=self._on_volume_change
        )
        self.volume_slider.set(80)  # Default 80%
        self.volume_slider.pack(side=LEFT, fill=X, expand=True)
        
        self.volume_label = ttk.Label(volume_frame, text="80%", width=4)
        self.volume_label.pack(side=LEFT, padx=(10, 0))
        
        # Input device selection
        device_frame = ttk.Frame(left_col)
        device_frame.pack(fill=X, pady=(10, 0))
        
        ttk.Label(device_frame, text="Microphone:").pack(side=LEFT, padx=(0, 10))
        
        self.mic_combo = ttk.Combobox(
            device_frame,
            state="readonly",
            width=30
        )
        self.mic_combo.pack(side=LEFT, fill=X, expand=True)
        
        # Right column - Voice settings
        ttk.Label(right_col, text="Voice Settings", font=("Arial", 10, "bold")).pack(anchor=W)
        
        # Voice selection
        voice_frame = ttk.Frame(right_col)
        voice_frame.pack(fill=X, pady=(10, 0))
        
        ttk.Label(voice_frame, text="AI Voice:").pack(side=LEFT, padx=(0, 10))
        
        self.voice_combo = ttk.Combobox(
            voice_frame,
            state="readonly",
            values=["Nova", "Alloy", "Echo", "Fable", "Onyx", "Shimmer"],
            width=20
        )
        self.voice_combo.set("Nova")  # Default
        self.voice_combo.pack(side=LEFT)
        
        # Options
        options_frame = ttk.Frame(right_col)
        options_frame.pack(fill=X, pady=(10, 0))
        
        self.interrupt_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame,
            text="Allow interruptions",
            variable=self.interrupt_var,
            command=self._on_interrupt_toggle
        ).pack(anchor=W)
        
        self.medical_context_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame,
            text="Include medical context",
            variable=self.medical_context_var
        ).pack(anchor=W, pady=(5, 0))
        
    def _toggle_voice_mode(self):
        """Toggle voice mode on/off."""
        if not self.is_active:
            self._start_voice_mode()
        else:
            self._stop_voice_mode()
            
    def _start_voice_mode(self):
        """Start voice mode."""
        self.is_active = True
        
        # Update UI
        self.voice_button.configure(
            text="🔴 Stop Voice Mode",
            style="Danger.TButton"
        )
        self.status_label.configure(text="Initializing voice mode...")
        
        # Show interrupt button if enabled
        if self.interrupt_var.get():
            self.interrupt_button.pack(pady=5)
            
        # Start animation
        self._start_pulse_animation()
        
        # Add system message
        self._add_system_message("Voice mode started")
        
        # Notify app to start voice mode
        if hasattr(self.app, 'start_voice_mode'):
            self.app.start_voice_mode()
            
    def _stop_voice_mode(self):
        """Stop voice mode."""
        self.is_active = False
        
        # Update UI
        self.voice_button.configure(
            text="🎤 Start Voice Mode",
            style="Voice.TButton"
        )
        self.status_label.configure(text="Voice mode stopped")
        
        # Hide interrupt button
        self.interrupt_button.pack_forget()
        
        # Stop animation
        self._stop_pulse_animation()
        
        # Add system message
        self._add_system_message("Voice mode stopped")
        
        # Notify app to stop voice mode
        if hasattr(self.app, 'stop_voice_mode'):
            self.app.stop_voice_mode()
            
    def _interrupt_voice(self):
        """Interrupt current voice interaction."""
        if hasattr(self.app, 'interrupt_voice'):
            self.app.interrupt_voice()
            
        self._add_system_message("Interrupted")
        
    def _clear_conversation(self):
        """Clear the conversation history."""
        self.conversation_text.config(state=NORMAL)
        self.conversation_text.delete(1.0, END)
        self.conversation_text.config(state=DISABLED)
        
    def _export_transcript(self):
        """Export conversation transcript."""
        content = self.conversation_text.get(1.0, END)
        
        if hasattr(self.app, 'export_voice_transcript'):
            self.app.export_voice_transcript(content)
        else:
            # Fallback - copy to clipboard
            self.parent_frame.clipboard_clear()
            self.parent_frame.clipboard_append(content)
            self._add_system_message("Transcript copied to clipboard")
            
    def _copy_to_context(self):
        """Copy conversation to context tab."""
        content = self.conversation_text.get(1.0, END)
        
        if hasattr(self.app, 'add_to_context'):
            self.app.add_to_context(content, "Voice Conversation")
            self._add_system_message("Conversation copied to context")
            
    def _on_volume_change(self, value):
        """Handle volume slider change.
        
        Args:
            value: Slider value
        """
        volume = int(float(value))
        if self.volume_label:
            self.volume_label.configure(text=f"{volume}%")
        
        # Update voice manager volume
        if hasattr(self.app, 'set_voice_volume'):
            self.app.set_voice_volume(volume / 100.0)
            
    def _on_interrupt_toggle(self):
        """Handle interrupt checkbox toggle."""
        if hasattr(self.app, 'set_voice_interruptions'):
            self.app.set_voice_interruptions(self.interrupt_var.get())
            
    def update_state(self, state: str):
        """Update UI based on voice state.
        
        Args:
            state: Current voice state
        """
        state_messages = {
            ConversationState.IDLE.value: "Ready to start",
            ConversationState.LISTENING.value: "Listening...",
            ConversationState.PROCESSING.value: "Processing...",
            ConversationState.SPEAKING.value: "Speaking...",
            ConversationState.INTERRUPTED.value: "Interrupted"
        }
        
        message = state_messages.get(state, state)
        self.status_label.configure(text=message)
        
        # Update status indicator color
        self._update_status_indicator(state)
        
        # Enable/disable interrupt button
        if state == ConversationState.SPEAKING.value:
            self.interrupt_button.configure(state=NORMAL)
        else:
            self.interrupt_button.configure(state=DISABLED)
            
    def add_user_message(self, text: str, timestamp: Optional[datetime] = None):
        """Add user message to conversation.
        
        Args:
            text: Message text
            timestamp: Message timestamp
        """
        self._add_message("You", text, "user", timestamp)
        
    def add_assistant_message(self, text: str, timestamp: Optional[datetime] = None):
        """Add assistant message to conversation.
        
        Args:
            text: Message text
            timestamp: Message timestamp
        """
        self._add_message("Assistant", text, "assistant", timestamp)
        
    def _add_system_message(self, text: str):
        """Add system message to conversation.
        
        Args:
            text: Message text
        """
        self._add_message("System", text, "system")
        
    def _add_message(self, speaker: str, text: str, tag: str, 
                    timestamp: Optional[datetime] = None):
        """Add message to conversation display.
        
        Args:
            speaker: Speaker name
            text: Message text
            tag: Text tag for styling
            timestamp: Message timestamp
        """
        self.conversation_text.config(state=NORMAL)
        
        # Add timestamp if provided
        if timestamp:
            time_str = timestamp.strftime("%H:%M:%S")
            self.conversation_text.insert(END, f"[{time_str}] ", "timestamp")
            
        # Add speaker
        self.conversation_text.insert(END, f"{speaker}: ", tag)
        
        # Add message
        self.conversation_text.insert(END, f"{text}\n\n")
        
        # Auto-scroll to bottom
        self.conversation_text.see(END)
        
        self.conversation_text.config(state=DISABLED)
        
    def _update_status_indicator(self, state: Optional[str] = None):
        """Update status indicator color.
        
        Args:
            state: Current state
        """
        colors = {
            ConversationState.IDLE.value: "#cccccc",
            ConversationState.LISTENING.value: "#00cc00",
            ConversationState.PROCESSING.value: "#ffcc00",
            ConversationState.SPEAKING.value: "#0099ff",
            ConversationState.INTERRUPTED.value: "#ff6600"
        }
        
        color = colors.get(state, "#cccccc")
        
        self.status_indicator.delete("all")
        self.status_indicator.create_oval(
            2, 2, 18, 18,
            fill=color,
            outline=color
        )
        
    def _start_pulse_animation(self):
        """Start pulsing animation for active state."""
        def pulse():
            if not self.is_active:
                return
                
            # Calculate pulse alpha
            self.pulse_state = (self.pulse_state + 1) % 20
            alpha = abs(10 - self.pulse_state) / 10.0
            
            # Update indicator with pulse effect
            if self.current_state == ConversationState.LISTENING.value:
                # Pulse green for listening
                intensity = int(204 + (255 - 204) * alpha)
                color = f"#{intensity:02x}ff{intensity:02x}"
            elif self.current_state == ConversationState.SPEAKING.value:
                # Pulse blue for speaking
                intensity = int(153 + (255 - 153) * alpha)
                color = f"#{intensity:02x}{intensity:02x}ff"
            else:
                return
                
            self.status_indicator.delete("all")
            self.status_indicator.create_oval(
                2, 2, 18, 18,
                fill=color,
                outline=color
            )
            
            # Schedule next frame
            self.pulse_animation_id = self.parent_frame.after(50, pulse)
            
        pulse()
        
    def _stop_pulse_animation(self):
        """Stop pulsing animation."""
        if self.pulse_animation_id:
            self.parent_frame.after_cancel(self.pulse_animation_id)
            self.pulse_animation_id = None
            
        self._update_status_indicator()
        
    def populate_microphones(self, microphones: list):
        """Populate microphone dropdown.
        
        Args:
            microphones: List of microphone names
        """
        self.mic_combo['values'] = microphones
        if microphones:
            self.mic_combo.current(0)