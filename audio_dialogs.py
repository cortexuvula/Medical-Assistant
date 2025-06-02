"""
Audio Dialogs Module

Handles dialogs related to audio recording functionality including
prefix audio recording and other audio-related UI components.
"""

import os
import sys
import logging
import tempfile
import threading
import tkinter as tk
from tkinter import NORMAL, DISABLED
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from dialogs import create_toplevel_dialog
from utils import get_valid_microphones
from settings import SETTINGS


class AudioDialogManager:
    """Manages audio-related dialogs."""
    
    def __init__(self, parent_app):
        """Initialize the audio dialog manager.
        
        Args:
            parent_app: The main application instance
        """
        self.app = parent_app
        self.audio_handler = parent_app.audio_handler
        self.status_manager = parent_app.status_manager
        
    def show_prefix_recording_dialog(self) -> None:
        """Shows a dialog to record and save a prefix audio file."""
        # Create a toplevel dialog for prefix audio recording
        prefix_dialog = create_toplevel_dialog(self.app, "Record Prefix Audio", "600x400")
        
        # Create instruction label
        instruction_text = "This audio will be prepended to all recordings before sending to the STT provider.\n"
        instruction_text += "Record a short introduction or context that you want to include at the beginning of all your dictations."
        ttk.Label(prefix_dialog, text=instruction_text, wraplength=550).pack(pady=(20, 10))
        
        # Status variable and label
        status_var = tk.StringVar(value="Ready to record")
        status_label = ttk.Label(prefix_dialog, textvariable=status_var)
        status_label.pack(pady=10)
        
        # Create microphone selection dropdown
        mic_frame = ttk.Frame(prefix_dialog)
        mic_frame.pack(pady=5, fill="x", padx=20)
        
        ttk.Label(mic_frame, text="Select Microphone:").pack(side="left", padx=(0, 10))
        
        # Get available microphones
        available_mics = get_valid_microphones()
        
        # Create microphone selection variable
        mic_var = tk.StringVar(prefix_dialog)
        
        # Get the currently selected microphone from settings
        selected_mic = SETTINGS.get("selected_microphone", "")
        
        # Set the dropdown to the currently selected microphone if available
        if selected_mic and selected_mic in available_mics:
            mic_var.set(selected_mic)
        elif available_mics:
            mic_var.set(available_mics[0])
        
        # Create dropdown menu
        mic_dropdown = ttk.Combobox(mic_frame, textvariable=mic_var, width=40)
        mic_dropdown["values"] = available_mics
        mic_dropdown.pack(side="left", fill="x", expand=True)
        
        # Create frame for buttons
        button_frame = ttk.Frame(prefix_dialog)
        button_frame.pack(pady=10)
        
        # Recording state variables
        recording_active = False
        stop_recording_func = None
        preview_segment = None
        audio_segments = []  # Accumulate segments
        original_soap_mode = False  # Store original SOAP mode
        
        # Path to the prefix audio file
        prefix_audio_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prefix_audio.mp3")
        
        # Function to handle audio data from recording
        def on_audio_data(audio_data):
            nonlocal audio_segments
            try:
                # Process the audio data into a segment
                segment, _ = self.audio_handler.process_audio_data(audio_data)
                if segment:
                    audio_segments.append(segment)
                    duration = sum(seg.duration_seconds for seg in audio_segments)
                    status_var.set(f"Recording... {duration:.1f} seconds captured")
            except Exception as e:
                logging.error(f"Error processing prefix audio: {e}", exc_info=True)
                status_var.set(f"Error: {str(e)}")
        
        # Function to start recording
        def start_recording():
            nonlocal recording_active, stop_recording_func, audio_segments, original_soap_mode
            if recording_active:
                return
                
            # Get the selected microphone
            mic_name = mic_var.get()
            if not mic_name:
                status_var.set("Error: No microphone selected")
                return
                
            try:
                # Clear previous segments
                audio_segments = []
                
                # Make sure SOAP mode is disabled for prefix recording
                original_soap_mode = self.audio_handler.soap_mode
                self.audio_handler.soap_mode = False
                
                # Play start sound
                self.app.play_recording_sound(start=True)
                
                # Start recording
                recording_active = True
                status_var.set("Recording... speak now")
                record_button.config(state=DISABLED)
                stop_button.config(state=NORMAL)
                preview_button.config(state=DISABLED)
                save_button.config(state=DISABLED)
                
                # Use the audio handler to start listening
                stop_recording_func = self.audio_handler.listen_in_background(
                    mic_name, 
                    on_audio_data,
                    phrase_time_limit=10  # Use 10 seconds to prevent cutoffs
                )
            except Exception as e:
                recording_active = False
                logging.error(f"Error starting prefix recording: {e}", exc_info=True)
                status_var.set(f"Error: {str(e)}")
                record_button.config(state=NORMAL)
                stop_button.config(state=DISABLED)
        
        # Function to stop recording
        def stop_recording():
            nonlocal recording_active, stop_recording_func
            if not recording_active or not stop_recording_func:
                return
            
            # Disable buttons immediately
            stop_button.config(state=DISABLED)
            status_var.set("Processing recording...")
            
            # Run the actual stop process in a thread to avoid blocking UI
            def stop_recording_thread():
                nonlocal preview_segment, audio_segments, recording_active, stop_recording_func
                try:
                    # Play stop sound
                    self.app.play_recording_sound(start=False)
                    
                    # Stop the recording
                    stop_recording_func()
                    recording_active = False
                    stop_recording_func = None
                    
                    # Restore original SOAP mode
                    self.audio_handler.soap_mode = original_soap_mode
                    
                    # Combine all segments if we have any
                    if audio_segments:
                        # Combine all segments into one
                        preview_segment = self.audio_handler.combine_audio_segments(audio_segments)
                        if preview_segment:
                            duration = preview_segment.duration_seconds
                            # Update UI on main thread
                            prefix_dialog.after(0, lambda: [
                                status_var.set(f"Recording stopped - {duration:.1f} seconds captured"),
                                preview_button.config(state=NORMAL),
                                save_button.config(state=NORMAL),
                                record_button.config(state=NORMAL)
                            ])
                        else:
                            prefix_dialog.after(0, lambda: [
                                status_var.set("Recording stopped - no audio captured"),
                                record_button.config(state=NORMAL)
                            ])
                    else:
                        prefix_dialog.after(0, lambda: [
                            status_var.set("Recording stopped - no audio captured"),
                            record_button.config(state=NORMAL)
                        ])
                except Exception as e:
                    logging.error(f"Error stopping prefix recording: {e}", exc_info=True)
                    prefix_dialog.after(0, lambda: [
                        status_var.set(f"Error: {str(e)}"),
                        record_button.config(state=NORMAL)
                    ])
            
            # Start the thread
            threading.Thread(target=stop_recording_thread, daemon=True).start()
        
        # Function to preview the recorded audio
        def preview_audio():
            nonlocal preview_segment
            if not preview_segment:
                status_var.set("No recording to preview")
                return
                
            try:
                # Create a temporary file for preview
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                    preview_segment.export(temp_file.name, format="mp3", bitrate="192k")
                    # Open the file with the default audio player
                    if os.name == 'nt':  # Windows
                        os.startfile(temp_file.name)
                    else:  # macOS or Linux
                        import subprocess
                        subprocess.Popen(['open', temp_file.name] if sys.platform == 'darwin' else ['xdg-open', temp_file.name])
                status_var.set("Playing preview")
            except Exception as e:
                logging.error(f"Error previewing audio: {e}", exc_info=True)
                status_var.set(f"Error previewing: {str(e)}")
        
        # Function to save the recorded audio
        def save_audio():
            nonlocal preview_segment
            if not preview_segment:
                status_var.set("No recording to save")
                return
                
            try:
                # Export the audio segment to the application directory
                preview_segment.export(prefix_audio_path, format="mp3", bitrate="192k")
                status_var.set(f"Prefix audio saved successfully to {prefix_audio_path}")
                self.status_manager.success("Prefix audio saved successfully")
                prefix_dialog.destroy()
            except Exception as e:
                logging.error(f"Error saving prefix audio: {e}", exc_info=True)
                status_var.set(f"Error saving: {str(e)}")
        
        # Add buttons
        record_button = ttk.Button(button_frame, text="Record", command=start_recording)
        record_button.pack(side=tk.LEFT, padx=5)
        
        stop_button = ttk.Button(button_frame, text="Stop", command=stop_recording, state=DISABLED)
        stop_button.pack(side=tk.LEFT, padx=5)
        
        preview_button = ttk.Button(button_frame, text="Preview", command=preview_audio, state=DISABLED)
        preview_button.pack(side=tk.LEFT, padx=5)
        
        save_button = ttk.Button(button_frame, text="Save", command=save_audio, state=DISABLED)
        save_button.pack(side=tk.LEFT, padx=5)
        
        # Add cancel button
        ttk.Button(prefix_dialog, text="Cancel", command=prefix_dialog.destroy).pack(pady=20)
        
        # Check if prefix audio already exists and show info
        if os.path.exists(prefix_audio_path):
            file_info = f"Existing prefix audio found. Recording will replace the current file."
            ttk.Label(prefix_dialog, text=file_info, foreground="blue").pack(pady=10)
            
            # Add button to delete existing prefix
            def delete_prefix():
                try:
                    os.remove(prefix_audio_path)
                    status_var.set("Existing prefix audio deleted")
                    delete_button.config(state=DISABLED)
                except Exception as e:
                    logging.error(f"Error deleting prefix audio: {e}", exc_info=True)
                    status_var.set(f"Error deleting: {str(e)}")
            
            delete_button = ttk.Button(prefix_dialog, text="Delete Existing Prefix", command=delete_prefix)
            delete_button.pack(pady=5)