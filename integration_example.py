"""
Integration Example: How to refactor app.py to use the new modules

This file demonstrates how to integrate the extracted modules into the existing app.py
without completely rewriting it. Each section shows before/after examples.
"""

# ========================================================================
# STEP 1: Add imports at the top of app.py
# ========================================================================

# Add these imports after the existing imports in app.py:
from recording_manager import RecordingManager
from ai_processor import AIProcessor
from file_manager import FileManager
from db_manager import DatabaseManager


# ========================================================================
# STEP 2: Initialize managers in __init__ method
# ========================================================================

# In MedicalDictationApp.__init__, after initializing audio_handler, add:
"""
# Initialize our new managers
self.recording_manager = RecordingManager(self.audio_handler, self.status_manager)
self.recording_manager.on_text_recognized = self.handle_recognized_text
self.recording_manager.on_transcription_fallback = self.on_transcription_fallback

self.ai_processor = AIProcessor(openai.api_key)
self.file_manager = FileManager(SETTINGS.get("default_folder", ""))
self.db_manager = DatabaseManager()
"""


# ========================================================================
# STEP 3: Replace SOAP Recording Methods
# ========================================================================

# BEFORE (old toggle_soap_recording method):
"""
def toggle_soap_recording(self) -> None:
    if not self.soap_recording:
        # Start recording logic...
        self.soap_recording = True
        # ... lots of code ...
    else:
        # Stop recording logic...
        self.soap_recording = False
        # ... lots of code ...
"""

# AFTER (using RecordingManager):
def toggle_soap_recording(self) -> None:
    """Toggle SOAP recording using RecordingManager."""
    if not self.recording_manager.is_recording:
        # Start recording
        self.status_manager.info("Starting SOAP recording...")
        self.record_soap_button.config(text="Stop Recording", bootstyle="danger")
        self.pause_soap_button.config(state=NORMAL)
        self.cancel_soap_button.config(state=NORMAL)
        
        # Start recording with callback
        if self.recording_manager.start_recording(self.soap_callback):
            self.play_recording_sound("start")
        else:
            self.status_manager.error("Failed to start recording")
            self.record_soap_button.config(text="Record SOAP Note", bootstyle="success")
    else:
        # Stop recording
        self.status_manager.info("Stopping SOAP recording...")
        self.record_soap_button.config(state=DISABLED)
        
        # Stop and get recording data
        recording_data = self.recording_manager.stop_recording()
        if recording_data:
            self.play_recording_sound("stop")
            self._finalize_soap_recording(recording_data)
        else:
            self.status_manager.error("No recording data available")
            self.record_soap_button.config(text="Record SOAP Note", bootstyle="success", state=NORMAL)


# ========================================================================
# STEP 4: Replace AI Processing Methods
# ========================================================================

# BEFORE (old refine_text method):
"""
def refine_text(self) -> None:
    text = self.get_active_text_widget().get("1.0", tk.END).strip()
    if not text:
        messagebox.showwarning("Empty Text", "Please add text before refining.")
        return
    # ... lots of OpenAI API code ...
"""

# AFTER (using AIProcessor):
def refine_text(self) -> None:
    """Refine text using AI processor."""
    text = self.get_active_text_widget().get("1.0", tk.END).strip()
    if not text:
        messagebox.showwarning("Empty Text", "Please add text before refining.")
        return
    
    # Show progress
    self.status_manager.progress("Refining text...")
    self.refine_button.config(state=DISABLED)
    
    def task():
        # Use AI processor
        result = self.ai_processor.refine_text(text)
        
        # Update UI on main thread
        self.after(0, lambda: self._handle_ai_result(result, "refine"))
    
    # Run in background
    self.io_executor.submit(task)


def _handle_ai_result(self, result: dict, operation: str):
    """Handle AI processing result."""
    if result["success"]:
        # Update text widget
        widget = self.get_active_text_widget()
        widget.delete("1.0", tk.END)
        widget.insert("1.0", result["text"])
        self.status_manager.success(f"Text {operation}d successfully")
    else:
        self.status_manager.error(f"Failed to {operation} text: {result['error']}")
    
    # Re-enable button
    if operation == "refine":
        self.refine_button.config(state=NORMAL)
    elif operation == "improve":
        self.improve_button.config(state=NORMAL)


# ========================================================================
# STEP 5: Replace File Operations
# ========================================================================

# BEFORE (old save_text method):
"""
def save_text(self) -> None:
    text = self.transcript_text.get("1.0", tk.END).strip()
    if not text:
        messagebox.showwarning("Save Text", "No text to save.")
        return
    file_path = filedialog.asksaveasfilename(...)
    # ... file saving code ...
"""

# AFTER (using FileManager):
def save_text(self) -> None:
    """Save text using FileManager."""
    text = self.transcript_text.get("1.0", tk.END).strip()
    if not text:
        messagebox.showwarning("Save Text", "No text to save.")
        return
    
    # Save text file
    file_path = self.file_manager.save_text_file(text, "Save Transcript")
    
    if file_path and self.audio_segments:
        # Also save audio if available
        audio_data = self.audio_handler.combine_audio_segments(self.audio_segments)
        if audio_data:
            audio_path = file_path.replace('.txt', '.mp3')
            if self.file_manager.save_audio_file(audio_data, "Save Audio"):
                self.status_manager.success("Text and audio saved successfully")
            else:
                self.status_manager.warning("Text saved, but audio save failed")


# BEFORE (old export_prompts method):
"""
def export_prompts(self) -> None:
    # ... lots of prompt export code ...
"""

# AFTER (using FileManager):
def export_prompts(self) -> None:
    """Export prompts using FileManager."""
    self.file_manager.export_prompts()


# ========================================================================
# STEP 6: Replace Database Operations
# ========================================================================

# BEFORE (old _save_soap_recording_to_database method):
"""
def _save_soap_recording_to_database(self, transcript: str, audio_path: str, 
                                   duration: float, soap_note: str = "") -> Optional[int]:
    try:
        recording_id = self.db.add_recording(
            transcript=transcript,
            audio_path=audio_path,
            duration=duration,
            soap_note=soap_note
        )
        # ... more code ...
"""

# AFTER (using DatabaseManager):
def _save_soap_recording_to_database(self, transcript: str, audio_path: str, 
                                   duration: float, soap_note: str = "") -> Optional[int]:
    """Save SOAP recording using DatabaseManager."""
    recording_data = {
        "transcript": transcript,
        "audio_path": audio_path,
        "duration": duration,
        "soap_note": soap_note,
        "metadata": {
            "provider": SETTINGS.get("selected_stt_provider", "unknown"),
            "language": self.recognition_language
        }
    }
    
    recording_id = self.db_manager.save_soap_recording(recording_data)
    if recording_id:
        self.status_manager.success(f"Recording saved to database (ID: {recording_id})")
    else:
        self.status_manager.error("Failed to save recording to database")
    
    return recording_id


# ========================================================================
# STEP 7: Update show_recordings_dialog to use DatabaseManager
# ========================================================================

# In the show_recordings_dialog method, replace database queries:
"""
# BEFORE:
recordings = self.db.get_recordings()

# AFTER:
recordings = self.db_manager.get_recordings(limit=100)
"""


# ========================================================================
# STEP 8: Gradual Migration Strategy
# ========================================================================

"""
1. Start by adding the imports and initializing the managers
2. Replace one method at a time, testing after each change
3. Keep the old methods temporarily by renaming them (e.g., toggle_soap_recording_old)
4. Once a module is fully integrated and tested, remove the old methods
5. Run the application and test thoroughly after each major change

Benefits of this approach:
- Incremental changes reduce risk
- Easy to rollback if issues arise
- Can test integration piece by piece
- Maintains working application throughout refactoring
"""


# ========================================================================
# EXAMPLE: Complete Integration for create_soap_note
# ========================================================================

def create_soap_note(self) -> None:
    """Create SOAP note using AIProcessor with context support."""
    # Get transcript text
    transcript = self.transcript_text.get("1.0", tk.END).strip()
    if not transcript:
        messagebox.showwarning("Empty Transcript", 
                             "Please add transcript text before creating SOAP note.")
        return
    
    # Get context if available (from future Context tab)
    context = getattr(self, 'context_text', tk.Text()).get("1.0", tk.END).strip()
    
    # Show progress
    self.status_manager.progress("Creating SOAP note...")
    self.soap_button.config(state=DISABLED)
    self.progress_bar.pack(side=RIGHT, padx=10)
    self.progress_bar.start()
    
    def task():
        try:
            # Use AI processor
            result = self.ai_processor.create_soap_note(transcript, context)
            
            # Update UI on main thread
            self.after(0, lambda: self._handle_soap_result(result))
            
        except Exception as e:
            logging.error(f"Error creating SOAP note: {e}")
            self.after(0, lambda: [
                self.status_manager.error(f"Error: {str(e)}"),
                self.soap_button.config(state=NORMAL),
                self.progress_bar.stop(),
                self.progress_bar.pack_forget()
            ])
    
    # Run in background
    self.io_executor.submit(task)


def _handle_soap_result(self, result: dict):
    """Handle SOAP note generation result."""
    self.progress_bar.stop()
    self.progress_bar.pack_forget()
    
    if result["success"]:
        # Update SOAP text
        self.soap_text.delete("1.0", tk.END)
        self.soap_text.insert("1.0", result["text"])
        
        # Switch to SOAP tab
        self.notebook.select(1)
        
        # Save to database if enabled
        if SETTINGS.get("auto_save_soap", True):
            self.db_manager.save_soap_recording({
                "transcript": self.transcript_text.get("1.0", tk.END).strip(),
                "audio_path": "",  # Will be set if we have audio
                "duration": 0,
                "soap_note": result["text"]
            })
        
        self.status_manager.success("SOAP note created successfully")
    else:
        self.status_manager.error(f"Failed to create SOAP note: {result['error']}")
        
    self.soap_button.config(state=NORMAL)