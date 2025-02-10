import os
import json
import string
import logging
import concurrent.futures
from io import BytesIO
import tkinter as tk
from tkinter import messagebox, filedialog, scrolledtext
import speech_recognition as sr
from pydub import AudioSegment
from deepgram import DeepgramClient, PrerecordedOptions
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from dotenv import load_dotenv

load_dotenv()
import openai
from typing import Callable, Optional

# --------------- Settings management -----------------
SETTINGS_FILE = "settings.json"

DEFAULT_SETTINGS = {
    "refine_text": {
        "prompt": (
            "Refine the punctuation and capitalization of the following text so that any voice command cues "
            "like 'full stop' are replaced with the appropriate punctuation and sentences start with a capital letter."
        ),
        "model": "gpt-3.5-turbo"
    },
    "improve_text": {
        "prompt": (
            "Improve the clarity, readability, and overall quality of the following transcript text."
        ),
        "model": "gpt-3.5-turbo"
    }
}

def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading settings: {e}", exc_info=True)
    return DEFAULT_SETTINGS.copy()

def save_settings(settings: dict) -> None:
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving settings: {e}", exc_info=True)

# Global settings variable
SETTINGS = load_settings()

# -------------------------
# Configuration Constants
# -------------------------
OPENAI_TEMPERATURE_REFINEMENT: float = 0.0
OPENAI_MAX_TOKENS_REFINEMENT: int = 4000
OPENAI_TEMPERATURE_IMPROVEMENT: float = 1.0
OPENAI_MAX_TOKENS_IMPROVEMENT: int = 4000

# Tooltip delay in milliseconds.
TOOLTIP_DELAY_MS: int = 500

# -------------------------
# API Keys and Logging
# -------------------------
openai.api_key = os.getenv("OPENAI_API_KEY")
deepgram_api_key: str = os.getenv("DEEPGRAM_API_KEY", "")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# -------------------------
# Main Application Class
# -------------------------
class MedicalDictationApp(ttk.Window):
    """
    Main application window for the Medical Dictation App.
    Supports voice-activated transcription, audio processing (via Deepgram or Google),
    and text refinement/improvement using OpenAI.
    """

    def __init__(self) -> None:
        super().__init__(themename="flatly")
        self.title("Medical Dictation App")
        self.geometry("1200x800")
        self.minsize(1200, 800)
        self.config(bg="#f0f0f0")

        # Load configuration from environment variables.
        self.recognition_language: str = os.getenv("RECOGNITION_LANGUAGE", "en-US")
        self.deepgram_api_key: str = deepgram_api_key

        # Thread pool for background tasks.
        self.executor: concurrent.futures.ThreadPoolExecutor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

        # Initialize Deepgram client if API key is provided.
        self.deepgram_client: Optional[DeepgramClient] = (
            DeepgramClient(api_key=self.deepgram_api_key) if self.deepgram_api_key else None
        )

        # For managing appended text chunks and capitalization.
        self.appended_chunks: list[str] = []
        self.capitalize_next: bool = False

        self.create_menu()
        self.create_widgets()
        self.bind_shortcuts()

        # Warn if OpenAI API key is missing.
        if not openai.api_key:
            self.refine_button.config(state=DISABLED)
            self.improve_button.config(state=DISABLED)
            self.update_status("Warning: OpenAI API key not provided. AI features disabled.")

        # Setup Speech Recognizer.
        self.recognizer: sr.Recognizer = sr.Recognizer()
        self.listening: bool = False
        self.stop_listening_function = None

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    # -------------------------
    # UI Creation Methods
    # -------------------------
    def create_menu(self) -> None:
        """Creates the application menu."""
        menubar = tk.Menu(self)
        
        # File Menu
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="New", command=self.new_session, accelerator="Ctrl+N")
        filemenu.add_command(label="Save", command=self.save_text, accelerator="Ctrl+S")
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.on_closing)
        menubar.add_cascade(label="File", menu=filemenu)

        # Settings Menu with a sub-menu for Text Settings
        settings_menu = tk.Menu(menubar, tearoff=0)
        text_settings_menu = tk.Menu(settings_menu, tearoff=0)
        text_settings_menu.add_command(label="Refine Text Settings", command=self.show_refine_settings_dialog)
        text_settings_menu.add_command(label="Improve Text Settings", command=self.show_improve_settings_dialog)
        settings_menu.add_cascade(label="Text Settings", menu=text_settings_menu)
        menubar.add_cascade(label="Settings", menu=settings_menu)

        # Help Menu
        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="About", command=self.show_about)
        helpmenu.add_command(label="Shortcuts & Voice Commands", command=self.show_shortcuts)
        menubar.add_cascade(label="Help", menu=helpmenu)

        self.config(menu=menubar)

    def create_widgets(self) -> None:
        """Creates the UI widgets."""
        # Microphone Selection Frame
        mic_frame = ttk.Frame(self, padding=10)
        mic_frame.pack(side=TOP, fill=tk.X, padx=20, pady=(20, 10))
        mic_label = ttk.Label(mic_frame, text="Select Microphone:")
        mic_label.pack(side=LEFT, padx=(0, 10))
        self.mic_names = sr.Microphone.list_microphone_names()
        self.mic_combobox = ttk.Combobox(mic_frame, values=self.mic_names, state="readonly", width=50)
        self.mic_combobox.pack(side=LEFT)
        if self.mic_names:
            self.mic_combobox.current(0)
        else:
            self.mic_combobox.set("No microphone found")
        refresh_btn = ttk.Button(mic_frame, text="Refresh", command=self.refresh_microphones, bootstyle="info")
        refresh_btn.pack(side=LEFT, padx=10)
        ToolTip(refresh_btn, "Refresh the list of available microphones.")

        # Transcription Text Area
        self.text_area = scrolledtext.ScrolledText(self, wrap=tk.WORD, width=80, height=12, font=("Segoe UI", 11))
        self.text_area.pack(padx=20, pady=10, fill=tk.X)

        # Control Buttons Frame
        control_frame = ttk.Frame(self, padding=10)
        control_frame.pack(side=TOP, fill=tk.X, padx=20, pady=10)

        # "Controls" Heading for main controls
        controls_label = ttk.Label(control_frame, text="Controls", font=("Segoe UI", 11, "bold"))
        controls_label.grid(row=0, column=0, sticky="w", padx=5, pady=(0, 5))

        # Main Controls Frame
        main_controls = ttk.Frame(control_frame)
        main_controls.grid(row=1, column=0, sticky="w")
        self.record_button = ttk.Button(main_controls, text="Record", width=10, command=self.start_recording, bootstyle="success")
        self.record_button.grid(row=0, column=0, padx=5, pady=5)
        ToolTip(self.record_button, "Start recording audio.")
        self.stop_button = ttk.Button(main_controls, text="Stop", width=10, command=self.stop_recording, state=DISABLED, bootstyle="danger")
        self.stop_button.grid(row=0, column=1, padx=5, pady=5)
        ToolTip(self.stop_button, "Stop recording audio.")
        self.new_session_button = ttk.Button(main_controls, text="New Dictation", width=12, command=self.new_session)
        self.new_session_button.grid(row=0, column=2, padx=5, pady=5)
        ToolTip(self.new_session_button, "Start a new dictation session.")
        self.clear_button = ttk.Button(main_controls, text="Clear Text", width=10, command=self.clear_text)
        self.clear_button.grid(row=0, column=3, padx=5, pady=5)
        ToolTip(self.clear_button, "Clear the transcription text.")
        self.copy_button = ttk.Button(main_controls, text="Copy Text", width=10, command=self.copy_text)
        self.copy_button.grid(row=0, column=4, padx=5, pady=5)
        ToolTip(self.copy_button, "Copy the transcription to the clipboard.")
        self.save_button = ttk.Button(main_controls, text="Save Text", width=10, command=self.save_text)
        self.save_button.grid(row=0, column=5, padx=5, pady=5)
        ToolTip(self.save_button, "Save the transcription to a file.")

        # AI Assist Section:
        ai_assist_label = ttk.Label(control_frame, text="AI Assist", font=("Segoe UI", 11, "bold"))
        ai_assist_label.grid(row=2, column=0, sticky="w", padx=5, pady=(10, 5))
        ai_buttons = ttk.Frame(control_frame)
        ai_buttons.grid(row=3, column=0, sticky="w")
        self.refine_button = ttk.Button(ai_buttons, text="Refine Text", width=15, command=self.refine_text)
        self.refine_button.grid(row=0, column=0, padx=5, pady=5)
        ToolTip(self.refine_button, "Refine text punctuation and capitalization using OpenAI API.")
        self.improve_button = ttk.Button(ai_buttons, text="Improve Text", width=15, command=self.improve_text)
        self.improve_button.grid(row=0, column=1, padx=5, pady=5)
        ToolTip(self.improve_button, "Improve text clarity using OpenAI API.")

        # Status Bar with Progress Bar
        status_frame = ttk.Frame(self, padding=(10, 5))
        status_frame.pack(side=BOTTOM, fill=tk.X)
        self.status_label = ttk.Label(status_frame, text="Status: Idle", anchor="w")
        self.status_label.pack(side=LEFT, fill=tk.X, expand=True)
        self.progress_bar = ttk.Progressbar(status_frame, mode="indeterminate")
        self.progress_bar.pack(side=RIGHT, padx=10)
        self.progress_bar.stop()
        self.progress_bar.pack_forget()  # Hide progress bar initially

    def bind_shortcuts(self) -> None:
        """Binds keyboard shortcuts to application commands."""
        self.bind("<Control-n>", lambda event: self.new_session())
        self.bind("<Control-s>", lambda event: self.save_text())
        self.bind("<Control-c>", lambda event: self.copy_text())

    def show_about(self) -> None:
        """Displays the About dialog."""
        messagebox.showinfo("About", "Medical Dictation App\n\nVersion 0.1\n\nDeveloped with Python and Tkinter (ttkbootstrap).")

    def show_shortcuts(self) -> None:
        """Displays a dialog with keyboard shortcuts and voice commands."""
        dialog = tk.Toplevel(self)
        dialog.title("Shortcuts & Voice Commands")
        dialog.geometry("700x500")
        dialog.transient(self)
        dialog.grab_set()

        notebook = ttk.Notebook(dialog)
        notebook.pack(expand=True, fill="both", padx=10, pady=10)

        # Keyboard Shortcuts Tab
        kb_frame = ttk.Frame(notebook)
        notebook.add(kb_frame, text="Keyboard Shortcuts")
        kb_tree = ttk.Treeview(kb_frame, columns=("Command", "Description"), show="headings")
        kb_tree.heading("Command", text="Command")
        kb_tree.heading("Description", text="Description")
        kb_tree.column("Command", width=150, anchor="w")
        kb_tree.column("Description", width=500, anchor="w")
        kb_tree.pack(expand=True, fill="both", padx=10, pady=10)
        keyboard_shortcuts = {
            "Ctrl+N": "Start a new dictation",
            "Ctrl+S": "Save the transcribed text",
            "Ctrl+C": "Copy the text to clipboard",
        }
        for cmd, desc in keyboard_shortcuts.items():
            kb_tree.insert("", tk.END, values=(cmd, desc))

        # Voice Commands Tab
        vc_frame = ttk.Frame(notebook)
        notebook.add(vc_frame, text="Voice Commands")
        vc_tree = ttk.Treeview(vc_frame, columns=("Command", "Action"), show="headings")
        vc_tree.heading("Command", text="Voice Command")
        vc_tree.heading("Action", text="Action")
        vc_tree.column("Command", width=200, anchor="w")
        vc_tree.column("Action", width=450, anchor="w")
        vc_tree.pack(expand=True, fill="both", padx=10, pady=10)
        voice_commands = {
            "new paragraph": "Inserts a new paragraph (two newlines)",
            "new line": "Inserts a new line",
            "full stop": "Inserts a period and capitalizes next word",
            "comma": "Inserts a comma and a space",
            "question mark": "Inserts a question mark and capitalizes next word",
            "question point": "(Same as 'question mark')",
            "exclamation point": "Inserts an exclamation mark and capitalizes next word",
            "exclamation mark": "(Same as 'exclamation point')",
            "semicolon": "Inserts a semicolon and a space",
            "colon": "Inserts a colon and a space",
            "open quote": "Inserts an opening quote",
            "close quote": "Inserts a closing quote",
            "open parenthesis": "Inserts an opening parenthesis",
            "close parenthesis": "Inserts a closing parenthesis",
            "delete last word": "Deletes the last word from the text",
            "scratch that": "Removes the last appended text chunk",
            "new dictation": "Clears the current dictation (new session)",
            "clear text": "Clears all text",
            "copy text": "Copies the text to the clipboard",
            "save text": "Saves the text to a file"
        }
        for cmd, action in voice_commands.items():
            vc_tree.insert("", tk.END, values=(cmd, action))

        close_btn = ttk.Button(dialog, text="Close", command=dialog.destroy)
        close_btn.pack(pady=10)

    # -------------------------
    # Settings Dialogs (Split into Sub-menus)
    # -------------------------
    def show_refine_settings_dialog(self) -> None:
        """Displays the Refine Text Settings dialog."""
        dialog = tk.Toplevel(self)
        dialog.title("Refine Text Settings")
        dialog.geometry("800x500")
        dialog.transient(self)
        dialog.grab_set()

        refine_frame = ttk.LabelFrame(dialog, text="Refine Text Settings", padding=10)
        refine_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        refine_prompt_label = ttk.Label(refine_frame, text="Prompt:")
        refine_prompt_label.grid(row=0, column=0, sticky="nw")
        refine_prompt_text = tk.Text(refine_frame, width=60, height=5)
        refine_prompt_text.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        refine_prompt_text.insert(tk.END, SETTINGS.get("refine_text", {}).get("prompt", DEFAULT_SETTINGS["refine_text"]["prompt"]))

        refine_model_label = ttk.Label(refine_frame, text="Model:")
        refine_model_label.grid(row=1, column=0, sticky="nw")
        refine_model_entry = ttk.Entry(refine_frame, width=60)
        refine_model_entry.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        refine_model_entry.insert(0, SETTINGS.get("refine_text", {}).get("model", DEFAULT_SETTINGS["refine_text"]["model"]))

        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        def save_and_close():
            SETTINGS["refine_text"]["prompt"] = refine_prompt_text.get("1.0", tk.END).strip()
            SETTINGS["refine_text"]["model"] = refine_model_entry.get().strip()
            save_settings(SETTINGS)
            self.update_status("Refine text settings saved.")
            dialog.destroy()

        save_btn = ttk.Button(button_frame, text="Save", command=save_and_close, bootstyle="primary")
        save_btn.pack(side=tk.RIGHT, padx=5)
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=dialog.destroy, bootstyle="secondary")
        cancel_btn.pack(side=tk.RIGHT, padx=5)

    def show_improve_settings_dialog(self) -> None:
        """Displays the Improve Text Settings dialog."""
        dialog = tk.Toplevel(self)
        dialog.title("Improve Text Settings")
        dialog.geometry("800x500")
        dialog.transient(self)
        dialog.grab_set()

        improve_frame = ttk.LabelFrame(dialog, text="Improve Text Settings", padding=10)
        improve_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        improve_prompt_label = ttk.Label(improve_frame, text="Prompt:")
        improve_prompt_label.grid(row=0, column=0, sticky="nw")
        improve_prompt_text = tk.Text(improve_frame, width=60, height=5)
        improve_prompt_text.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        improve_prompt_text.insert(tk.END, SETTINGS.get("improve_text", {}).get("prompt", DEFAULT_SETTINGS["improve_text"]["prompt"]))

        improve_model_label = ttk.Label(improve_frame, text="Model:")
        improve_model_label.grid(row=1, column=0, sticky="nw")
        improve_model_entry = ttk.Entry(improve_frame, width=60)
        improve_model_entry.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        improve_model_entry.insert(0, SETTINGS.get("improve_text", {}).get("model", DEFAULT_SETTINGS["improve_text"]["model"]))

        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        def save_and_close():
            SETTINGS["improve_text"]["prompt"] = improve_prompt_text.get("1.0", tk.END).strip()
            SETTINGS["improve_text"]["model"] = improve_model_entry.get().strip()
            save_settings(SETTINGS)
            self.update_status("Improve text settings saved.")
            dialog.destroy()

        save_btn = ttk.Button(button_frame, text="Save", command=save_and_close, bootstyle="primary")
        save_btn.pack(side=tk.RIGHT, padx=5)
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=dialog.destroy, bootstyle="secondary")
        cancel_btn.pack(side=tk.RIGHT, padx=5)

    # -------------------------
    # Text Management Methods
    # -------------------------
    def new_session(self) -> None:
        """Starts a new dictation session, clearing unsaved text."""
        if messagebox.askyesno("New Dictation", "Start a new dictation? Unsaved changes will be lost."):
            self.text_area.delete("1.0", tk.END)
            self.appended_chunks.clear()

    def save_text(self) -> None:
        """Saves the transcribed text to a file."""
        text: str = self.text_area.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Save Text", "No text to save.")
            return
        file_path: str = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(text)
                messagebox.showinfo("Save Text", "Text saved successfully.")
            except Exception as e:
                messagebox.showerror("Save Text", f"Error saving file: {e}")

    def copy_text(self) -> None:
        """Copies the transcribed text to the clipboard."""
        text: str = self.text_area.get("1.0", tk.END)
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update_status("Text copied to clipboard.")

    def clear_text(self) -> None:
        """Clears the transcribed text."""
        if messagebox.askyesno("Clear Text", "Are you sure you want to clear the text?"):
            self.text_area.delete("1.0", tk.END)
            self.appended_chunks.clear()

    def append_text(self, text: str) -> None:
        """
        Appends recognized text to the text area, handling punctuation and capitalization.
        """
        current_content: str = self.text_area.get("1.0", "end-1c")
        if (self.capitalize_next or not current_content or current_content[-1] in ".!?") and text:
            text = text[0].upper() + text[1:]
            self.capitalize_next = False
        text_to_insert: str = (" " if current_content and current_content[-1] != "\n" else "") + text
        tag_name: str = f"chunk_{len(self.appended_chunks)}"
        self.text_area.insert(tk.END, text_to_insert, tag_name)
        self.appended_chunks.append(tag_name)
        self.text_area.see(tk.END)

    def scratch_that(self) -> None:
        """Removes the last appended text chunk."""
        if not self.appended_chunks:
            self.update_status("Nothing to scratch.")
            return
        tag_name: str = self.appended_chunks.pop()
        ranges = self.text_area.tag_ranges(tag_name)
        if ranges:
            self.text_area.delete(ranges[0], ranges[1])
            self.text_area.tag_delete(tag_name)
            self.update_status("Last added text removed.")
        else:
            self.update_status("No tagged text found.")

    def delete_last_word(self) -> None:
        """Deletes the last word from the transcribed text."""
        current_content: str = self.text_area.get("1.0", "end-1c")
        if current_content:
            words = current_content.split()
            new_text = " ".join(words[:-1])
            self.text_area.delete("1.0", tk.END)
            self.text_area.insert(tk.END, new_text)
            self.text_area.see(tk.END)

    def update_status(self, message: str) -> None:
        """Updates the status bar with a given message."""
        self.status_label.config(text=f"Status: {message}")

    # -------------------------
    # Audio Processing Methods
    # -------------------------
    def start_recording(self) -> None:
        """Starts recording audio using the selected microphone."""
        if not self.listening:
            self.update_status("Listening...")
            mic_index = self.mic_combobox.current()
            try:
                mic = sr.Microphone(device_index=mic_index)
            except Exception as e:
                messagebox.showerror("Microphone Error", f"Error accessing microphone: {e}")
                logging.error("Microphone access error", exc_info=True)
                return
            self.stop_listening_function = self.recognizer.listen_in_background(mic, self.callback, phrase_time_limit=10)
            self.listening = True
            self.record_button.config(state=DISABLED)
            self.stop_button.config(state=NORMAL)

    def stop_recording(self) -> None:
        """Stops the audio recording."""
        if self.listening and self.stop_listening_function:
            self.stop_listening_function(wait_for_stop=False)
            self.listening = False
            self.update_status("Idle")
            self.record_button.config(state=NORMAL)
            self.stop_button.config(state=DISABLED)

    def callback(self, recognizer: sr.Recognizer, audio: sr.AudioData) -> None:
        """Callback for processing audio in the background."""
        self.executor.submit(self.process_audio, recognizer, audio)

    def process_audio(self, recognizer: sr.Recognizer, audio: sr.AudioData) -> None:
        """
        Processes the recorded audio using Deepgram (if available) or Google Speech Recognition.
        Dynamically determines the number of channels for the audio segment.
        """
        try:
            if self.deepgram_client:
                channels = getattr(audio, "channels", 1)  # Use dynamic channel count if available
                audio_segment = AudioSegment(
                    data=audio.get_raw_data(),
                    sample_width=audio.sample_width,
                    frame_rate=audio.sample_rate,
                    channels=channels
                )
                audio_buffer = BytesIO()
                audio_segment.export(audio_buffer, format="wav")
                audio_buffer.seek(0)
                payload = {"buffer": audio_buffer}
                options = PrerecordedOptions(model="nova-2-medical", language="en-US")
                response = self.deepgram_client.listen.rest.v("1").transcribe_file(payload, options)
                result_data = json.loads(response.to_json(indent=4))
                text: str = result_data["results"]["channels"][0]["alternatives"][0]["transcript"]
            else:
                text = recognizer.recognize_google(audio, language=self.recognition_language)
            self.after(0, self.handle_recognized_text, text)
        except sr.UnknownValueError:
            logging.info("Audio not understood.")
            self.after(0, self.update_status, "Audio not understood")
        except sr.RequestError as e:
            logging.error(f"Request error: {e}", exc_info=True)
            self.after(0, self.update_status, f"Request error: {e}")
        except Exception as e:
            logging.error(f"Processing error: {e}", exc_info=True)
            self.after(0, self.update_status, f"Error: {e}")

    def handle_recognized_text(self, text: str) -> None:
        """
        Handles the recognized text from speech recognition.
        Checks for voice command cues and either executes a command or appends the text.
        """
        if not text.strip():
            return

        def insert_punctuation(symbol: str, capitalize: bool = False) -> None:
            self.text_area.insert(tk.END, symbol + " ")
            if capitalize:
                self.capitalize_next = True

        commands = {
            "new paragraph": lambda: self.text_area.insert(tk.END, "\n\n"),
            "new line": lambda: self.text_area.insert(tk.END, "\n"),
            "full stop": lambda: insert_punctuation(".", capitalize=True),
            "comma": lambda: self.text_area.insert(tk.END, ", "),
            "question mark": lambda: insert_punctuation("?", capitalize=True),
            "question point": lambda: insert_punctuation("?", capitalize=True),
            "exclamation point": lambda: insert_punctuation("!", capitalize=True),
            "exclamation mark": lambda: insert_punctuation("!", capitalize=True),
            "semicolon": lambda: self.text_area.insert(tk.END, "; "),
            "colon": lambda: self.text_area.insert(tk.END, ": "),
            "open quote": lambda: self.text_area.insert(tk.END, "\""),
            "close quote": lambda: self.text_area.insert(tk.END, "\""),
            "open parenthesis": lambda: self.text_area.insert(tk.END, "("),
            "close parenthesis": lambda: self.text_area.insert(tk.END, ")"),
            "delete last word": self.delete_last_word,
            "scratch that": self.scratch_that,
            "new dictation": self.new_session,
            "clear text": self.clear_text,
            "copy text": self.copy_text,
            "save text": self.save_text,
        }
        cleaned = text.lower().strip().translate(str.maketrans('', '', string.punctuation))
        if cleaned in commands:
            commands[cleaned]()
        else:
            self.append_text(text)

    # -------------------------
    # Refine/Improve Text Methods Using OpenAI
    # -------------------------
    def _process_text_with_ai(self, api_func: Callable[[str], str], success_message: str, button: ttk.Button) -> None:
        """
        Generic helper to process text with an AI API call.
        
        :param api_func: Function that processes text using OpenAI.
        :param success_message: Message to display upon successful processing.
        :param button: The button widget to disable/enable during processing.
        """
        text: str = self.text_area.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Process Text", "There is no text to process.")
            return
        
        self.update_status("Processing text...")
        button.config(state=DISABLED)
        self.progress_bar.pack(side=RIGHT, padx=10)
        self.progress_bar.start()

        def task() -> None:
            result = api_func(text)
            self.after(0, lambda: self._update_text_area(result, success_message, button))
        self.executor.submit(task)

    def _update_text_area(self, new_text: str, success_message: str, button: ttk.Button) -> None:
        """Updates the text area with new text and resets UI elements after an AI task."""
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert(tk.END, new_text)
        self.update_status(success_message)
        button.config(state=NORMAL)
        self.progress_bar.stop()
        self.progress_bar.pack_forget()

    def refine_text(self) -> None:
        """Refines the transcribed text using OpenAI to adjust punctuation and capitalization."""
        self._process_text_with_ai(adjust_text_with_openai, "Text refined.", self.refine_button)

    def improve_text(self) -> None:
        """Improves the clarity and readability of the transcribed text using OpenAI."""
        self._process_text_with_ai(improve_text_with_openai, "Text improved.", self.improve_button)

    # -------------------------
    # Utility Methods
    # -------------------------
    def refresh_microphones(self) -> None:
        """Refreshes the list of available microphones."""
        self.mic_names = sr.Microphone.list_microphone_names()
        self.mic_combobox['values'] = self.mic_names
        if self.mic_names:
            self.mic_combobox.current(0)
        else:
            self.mic_combobox.set("No microphone found")
        self.update_status("Microphone list refreshed.")

    def on_closing(self) -> None:
        """Handles application shutdown and cleans up background tasks."""
        try:
            self.executor.shutdown(wait=False)
            logging.info("Thread pool shutdown.")
        except Exception as e:
            logging.error(f"Error shutting down thread pool: {e}", exc_info=True)
        self.destroy()

# -------------------------
# Tooltip Implementation
# -------------------------
class ToolTip:
    """
    Creates a tooltip for a given widget.
    The tooltip appears after a short delay when the mouse hovers over the widget.
    """
    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tipwindow: Optional[tk.Toplevel] = None
        self.after_id: Optional[str] = None
        self.widget.bind("<Enter>", self.schedule_showtip)
        self.widget.bind("<Leave>", self.cancel_showtip)

    def schedule_showtip(self, event: Optional[tk.Event] = None) -> None:
        self.after_id = self.widget.after(TOOLTIP_DELAY_MS, self.showtip)

    def cancel_showtip(self, event: Optional[tk.Event] = None) -> None:
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None
        self.hidetip()

    def showtip(self) -> None:
        """Displays the tooltip."""
        if self.tipwindow or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 10
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self.text,
            justify='left',
            background="#ffffe0",
            relief='solid',
            borderwidth=1,
            font=("tahoma", "8", "normal")
        )
        label.pack(ipadx=1)

    def hidetip(self) -> None:
        """Hides the tooltip."""
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None

# -------------------------
# OpenAI API Helper Functions
# -------------------------
def call_openai(model: str, system_message: str, prompt: str, temperature: float, max_tokens: int) -> str:
    """
    Calls the OpenAI API with the given parameters.
    
    :param model: OpenAI model to use.
    :param system_message: System prompt message.
    :param prompt: User prompt.
    :param temperature: Temperature setting for the API call.
    :param max_tokens: Maximum tokens for the response.
    :return: The AI-generated text.
    """
    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI API error: {e}", exc_info=True)
        return prompt  # Return original prompt as fallback

def adjust_text_with_openai(text: str) -> str:
    """
    Refines text punctuation and capitalization using OpenAI.
    
    :param text: The original text.
    :return: The refined text.
    """
    prompt_base = SETTINGS.get("refine_text", {}).get("prompt", DEFAULT_SETTINGS["refine_text"]["prompt"])
    model = SETTINGS.get("refine_text", {}).get("model", DEFAULT_SETTINGS["refine_text"]["model"])
    full_prompt = f"{prompt_base}\n\nOriginal: {text}\n\nCorrected:"
    system_message = "You are an assistant that corrects punctuation and capitalization."
    return call_openai(model, system_message, full_prompt, OPENAI_TEMPERATURE_REFINEMENT, OPENAI_MAX_TOKENS_REFINEMENT)

def improve_text_with_openai(text: str) -> str:
    """
    Improves text clarity and readability using OpenAI.
    
    :param text: The original text.
    :return: The improved text.
    """
    prompt_base = SETTINGS.get("improve_text", {}).get("prompt", DEFAULT_SETTINGS["improve_text"]["prompt"])
    model = SETTINGS.get("improve_text", {}).get("model", DEFAULT_SETTINGS["improve_text"]["model"])
    full_prompt = f"{prompt_base}\n\nOriginal: {text}\n\nImproved:"
    system_message = "You are an assistant that enhances the clarity and readability of text."
    return call_openai(model, system_message, full_prompt, OPENAI_TEMPERATURE_IMPROVEMENT, OPENAI_MAX_TOKENS_IMPROVEMENT)

# -------------------------
# Application Entry Point
# -------------------------
def main() -> None:
    """Application entry point."""
    app = MedicalDictationApp()
    app.mainloop()

if __name__ == "__main__":
    main()
