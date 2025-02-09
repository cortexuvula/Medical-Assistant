import os
import json
import string
import logging
import concurrent.futures
from io import BytesIO

import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog, scrolledtext

import speech_recognition as sr
from pydub import AudioSegment
from deepgram import DeepgramClient, PrerecordedOptions

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from dotenv import load_dotenv
load_dotenv()

import openai

# -------------------------
# Environment Variables
# -------------------------
openai.api_key = os.getenv("OPENAI_API_KEY")
# Fetch the Deepgram API key once and store it in a module-level variable.
deepgram_api_key = os.getenv("DEEPGRAM_API_KEY", "")

# -------------------------
# Logging Configuration
# -------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# -------------------------
# Main Application Class
# -------------------------
class MedicalDictationApp(ttk.Window):
    def __init__(self):
        super().__init__(themename="flatly")
        self.title("Medical Dictation App")
        self.geometry("1200x800")
        self.minsize(1200, 800)
        self.config(bg="#f0f0f0")

        # Load configuration from environment variables.
        self.recognition_language = os.getenv("RECOGNITION_LANGUAGE", "en-US")
        # Use the module-level deepgram_api_key instead of calling os.getenv() again.
        self.deepgram_api_key = deepgram_api_key

        # Thread pool for background tasks.
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

        # Initialize Deepgram client if API key is provided.
        self.deepgram_client = DeepgramClient(api_key=self.deepgram_api_key) if self.deepgram_api_key else None

        # For managing appended text chunks and capitalization.
        self.appended_chunks = []
        self.capitalize_next = False

        self.create_menu()
        self.create_widgets()

        # Disable the Refine and Improve Text buttons if no OpenAI API key is provided.
        if not openai.api_key:
            self.refine_button.config(state=DISABLED)
            self.improve_button.config(state=DISABLED)

        self.bind_shortcuts()

        # Setup Speech Recognizer.
        self.recognizer = sr.Recognizer()
        self.listening = False
        self.stop_listening_function = None

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    # -------------------------
    # UI Creation Methods
    # -------------------------
    def create_menu(self):
        menubar = tk.Menu(self)

        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="New", command=self.new_session, accelerator="Ctrl+N")
        filemenu.add_command(label="Save", command=self.save_text, accelerator="Ctrl+S")
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.on_closing)
        menubar.add_cascade(label="File", menu=filemenu)

        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="About", command=self.show_about)
        helpmenu.add_command(label="Shortcuts & Voice Commands", command=self.show_shortcuts)
        menubar.add_cascade(label="Help", menu=helpmenu)

        self.config(menu=menubar)

    def create_widgets(self):
        # Microphone Selection Frame
        mic_frame = ttk.Frame(self, padding=10)
        mic_frame.pack(side=TOP, fill=tk.X, padx=20, pady=(20, 10))
        mic_label = ttk.Label(mic_frame, text="Select Microphone:")
        mic_label.pack(side=LEFT, padx=(0, 10))

        self.mic_names = sr.Microphone.list_microphone_names()
        self.mic_combobox = ttk.Combobox(mic_frame, values=self.mic_names, state="readonly", width=50)
        self.mic_combobox.pack(side=LEFT)
        self.mic_combobox.current(0) if self.mic_names else self.mic_combobox.set("No microphone found")

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

        # Main Controls Frame (Record, Stop, New Dictation, Clear Text, Copy Text, Save Text)
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
        # Place the AI Assist label on its own row below the main controls and above the refine text button.
        ai_assist_label = ttk.Label(control_frame, text="AI Assist", font=("Segoe UI", 11, "bold"))
        ai_assist_label.grid(row=2, column=0, sticky="w", padx=5, pady=(10, 5))

        # AI Buttons Frame for Refine and Improve buttons
        ai_buttons = ttk.Frame(control_frame)
        ai_buttons.grid(row=3, column=0, sticky="w")

        self.refine_button = ttk.Button(ai_buttons, text="Refine Text", width=15, command=self.refine_text)
        self.refine_button.grid(row=0, column=0, padx=5, pady=5)
        ToolTip(self.refine_button, "Refine text punctuation and capitalization using OpenAI API.")

        self.improve_button = ttk.Button(ai_buttons, text="Improve Text", width=15, command=self.improve_text)
        self.improve_button.grid(row=0, column=1, padx=5, pady=5)
        ToolTip(self.improve_button, "Improve text clarity using OpenAI API.")

        # Status Bar
        status_frame = ttk.Frame(self, padding=(10, 5))
        status_frame.pack(side=BOTTOM, fill=tk.X)
        self.status_label = ttk.Label(status_frame, text="Status: Idle", anchor="w")
        self.status_label.pack(fill=tk.X)

    def bind_shortcuts(self):
        self.bind("<Control-n>", lambda event: self.new_session())
        self.bind("<Control-s>", lambda event: self.save_text())
        self.bind("<Control-c>", lambda event: self.copy_text())

    def show_about(self):
        messagebox.showinfo("About", "Medical Dictation App\nImproved version with additional features.\n\nDeveloped with Python and Tkinter (ttkbootstrap).")

    def show_shortcuts(self):
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
    # Text Management Methods
    # -------------------------
    def new_session(self):
        if messagebox.askyesno("New Dictation", "Start a new dictation? Unsaved changes will be lost."):
            self.text_area.delete("1.0", tk.END)
            self.appended_chunks.clear()

    def save_text(self):
        text = self.text_area.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Save Text", "No text to save.")
            return
        file_path = filedialog.asksaveasfilename(
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

    def copy_text(self):
        text = self.text_area.get("1.0", tk.END)
        self.clipboard_clear()
        self.clipboard_append(text)
        # Update the status bar instead of showing a pop-up.
        self.update_status("Text copied to clipboard.")

    def clear_text(self):
        if messagebox.askyesno("Clear Text", "Are you sure you want to clear the text?"):
            self.text_area.delete("1.0", tk.END)
            self.appended_chunks.clear()

    def append_text(self, text):
        current_content = self.text_area.get("1.0", "end-1c")
        # Capitalize first letter if required.
        if (self.capitalize_next or not current_content or current_content[-1] in ".!?") and text:
            text = text[0].upper() + text[1:]
            self.capitalize_next = False
        text_to_insert = (" " if current_content and current_content[-1] != "\n" else "") + text
        tag_name = f"chunk_{len(self.appended_chunks)}"
        self.text_area.insert(tk.END, text_to_insert, tag_name)
        self.appended_chunks.append(tag_name)
        self.text_area.see(tk.END)

    def scratch_that(self):
        if not self.appended_chunks:
            self.update_status("Nothing to scratch.")
            return
        tag_name = self.appended_chunks.pop()
        ranges = self.text_area.tag_ranges(tag_name)
        if ranges:
            self.text_area.delete(ranges[0], ranges[1])
            self.text_area.tag_delete(tag_name)
            self.update_status("Last added text removed.")
        else:
            self.update_status("No tagged text found.")

    def delete_last_word(self):
        current_content = self.text_area.get("1.0", "end-1c")
        if current_content:
            words = current_content.split()
            new_text = " ".join(words[:-1])
            self.text_area.delete("1.0", tk.END)
            self.text_area.insert(tk.END, new_text)
            self.text_area.see(tk.END)

    def update_status(self, message):
        self.status_label.config(text=f"Status: {message}")

    # -------------------------
    # Audio Processing Methods
    # -------------------------
    def start_recording(self):
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

    def stop_recording(self):
        if self.listening and self.stop_listening_function:
            self.stop_listening_function(wait_for_stop=False)
            self.listening = False
            self.update_status("Idle")
            self.record_button.config(state=NORMAL)
            self.stop_button.config(state=DISABLED)

    def callback(self, recognizer, audio):
        self.executor.submit(self.process_audio, recognizer, audio)

    def process_audio(self, recognizer, audio):
        try:
            if self.deepgram_client:
                # Create AudioSegment for Deepgram processing.
                audio_segment = AudioSegment(
                    data=audio.get_raw_data(),
                    sample_width=audio.sample_width,
                    frame_rate=audio.sample_rate,
                    channels=1
                )
                audio_buffer = BytesIO()
                audio_segment.export(audio_buffer, format="wav")
                audio_buffer.seek(0)
                payload = {"buffer": audio_buffer}
                options = PrerecordedOptions(model="nova-2-medical", language="en-US")
                response = self.deepgram_client.listen.rest.v("1").transcribe_file(payload, options)
                result_data = json.loads(response.to_json(indent=4))
                text = result_data["results"]["channels"][0]["alternatives"][0]["transcript"]
            else:
                # Use the original audio for Google recognition.
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

    def handle_recognized_text(self, text):
        # Ignore input that is only whitespace
        if not text.strip():
            return

        # Define a helper to insert punctuation with optional capitalization.
        def insert_punctuation(symbol, capitalize=False):
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
        # Normalize the recognized text.
        cleaned = text.lower().strip().translate(str.maketrans('', '', string.punctuation))
        if cleaned in commands:
            commands[cleaned]()
        else:
            self.append_text(text)

    # -------------------------
    # Refine Text Methods Using OpenAI
    # -------------------------
    def refine_text(self):
        text = self.text_area.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Refine Text", "There is no text to refine.")
            return

        self.update_status("Refining text...")
        self.refine_button.config(state=DISABLED)

        def task():
            refined = adjust_text_with_openai(text)
            self.after(0, self.set_refined_text, refined)

        self.executor.submit(task)

    def set_refined_text(self, refined_text):
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert(tk.END, refined_text)
        self.update_status("Text refined.")
        self.refine_button.config(state=NORMAL)

    def improve_text(self):
        text = self.text_area.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Improve Text", "There is no text to improve.")
            return

        self.update_status("Improving text...")
        self.improve_button.config(state=DISABLED)

        def task():
            improved = improve_text_with_openai(text)
            self.after(0, self.set_improved_text, improved)

        self.executor.submit(task)

    def set_improved_text(self, improved_text):
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert(tk.END, improved_text)
        self.update_status("Text improved.")
        self.improve_button.config(state=NORMAL)

    # -------------------------
    # Utility Methods
    # -------------------------
    def refresh_microphones(self):
        self.mic_names = sr.Microphone.list_microphone_names()
        self.mic_combobox['values'] = self.mic_names
        self.mic_combobox.current(0) if self.mic_names else self.mic_combobox.set("No microphone found")
        self.update_status("Microphone list refreshed.")

    def on_closing(self):
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
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind("<Enter>", self.showtip)
        widget.bind("<Leave>", self.hidetip)

    def showtip(self, event=None):
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

    def hidetip(self, event=None):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None

# -------------------------
# OpenAI Text Refinement Helper Function
# -------------------------
def adjust_text_with_openai(text: str) -> str:
    prompt = (
        "Refine the punctuation and capitalization of the following text so that any voice command cues "
        "like 'full stop' are replaced with the appropriate punctuation and sentences start with a capital letter. "
        "Return only the corrected text.\n\n"
        f"Original: {text}\n\nCorrected:"
    )
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an assistant that corrects punctuation and capitalization."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=500,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI API error: {e}", exc_info=True)
        return text

# -------------------------
# OpenAI Text Improvement Helper Function
# -------------------------
def improve_text_with_openai(text: str) -> str:
    prompt = (
        "Improve the clarity, readability, and overall quality of the following transcript text. "
        "Return only the improved text.\n\n"
        f"Original: {text}\n\nImproved:"
    )
    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an assistant that enhances the clarity and readability of text."},
                {"role": "user", "content": prompt}
            ],
            temperature=1,
            max_tokens=500,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI API error (improve): {e}", exc_info=True)
        return text

# -------------------------
# Application Entry Point
# -------------------------
def main():
    app = MedicalDictationApp()
    app.mainloop()

if __name__ == "__main__":
    main()
