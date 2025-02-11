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
import openai
import pyaudio
from typing import Callable, Optional

from utils import get_valid_microphones
from ai import adjust_text_with_openai, improve_text_with_openai, create_soap_note_with_openai
from tooltip import ToolTip
from settings import SETTINGS

load_dotenv()

# API Keys & Logging Setup
openai.api_key = os.getenv("OPENAI_API_KEY")
deepgram_api_key = os.getenv("DEEPGRAM_API_KEY", "")
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class MedicalDictationApp(ttk.Window):
    def __init__(self) -> None:
        super().__init__(themename="flatly")
        self.title("Medical Assistant")
        self.geometry("1200x800")
        self.minsize(1200, 800)
        self.config(bg="#f0f0f0")

        self.recognition_language = os.getenv("RECOGNITION_LANGUAGE", "en-US")
        self.deepgram_api_key = deepgram_api_key
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self.deepgram_client = DeepgramClient(api_key=self.deepgram_api_key) if self.deepgram_api_key else None

        self.appended_chunks = []
        self.capitalize_next = False
        self.audio_segments = []

        self.create_menu()
        self.create_widgets()
        self.bind_shortcuts()

        if not openai.api_key:
            self.refine_button.config(state=DISABLED)
            self.improve_button.config(state=DISABLED)
            self.update_status("Warning: OpenAI API key not provided. AI features disabled.")

        self.recognizer = sr.Recognizer()
        self.listening = False
        self.stop_listening_function = None

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_menu(self) -> None:
        menubar = tk.Menu(self)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="New", command=self.new_session, accelerator="Ctrl+N")
        filemenu.add_command(label="Save", command=self.save_text, accelerator="Ctrl+S")
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.on_closing)
        menubar.add_cascade(label="File", menu=filemenu)

        settings_menu = tk.Menu(menubar, tearoff=0)
        text_settings_menu = tk.Menu(settings_menu, tearoff=0)
        text_settings_menu.add_command(label="Refine Prompt Settings", command=self.show_refine_settings_dialog)
        text_settings_menu.add_command(label="Improve Prompt Settings", command=self.show_improve_settings_dialog)
        text_settings_menu.add_command(label="SOAP Note Settings", command=self.show_soap_settings_dialog)  # new submenu for SOAP note settings
        settings_menu.add_cascade(label="Prompt Settings", menu=text_settings_menu)
        menubar.add_cascade(label="Settings", menu=settings_menu)

        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="About", command=self.show_about)
        helpmenu.add_command(label="Shortcuts & Voice Commands", command=self.show_shortcuts)
        menubar.add_cascade(label="Help", menu=helpmenu)

        self.config(menu=menubar)

    def create_widgets(self) -> None:
        # Microphone Selection
        mic_frame = ttk.Frame(self, padding=10)
        mic_frame.pack(side=TOP, fill=tk.X, padx=20, pady=(20, 10))
        ttk.Label(mic_frame, text="Select Microphone:").pack(side=LEFT, padx=(0, 10))
        self.mic_names = get_valid_microphones() or sr.Microphone.list_microphone_names()
        self.mic_combobox = ttk.Combobox(mic_frame, values=self.mic_names, state="readonly", width=50)
        self.mic_combobox.pack(side=LEFT)
        if self.mic_names:
            self.mic_combobox.current(0)
        else:
            self.mic_combobox.set("No microphone found")
        refresh_btn = ttk.Button(mic_frame, text="Refresh", command=self.refresh_microphones, bootstyle="PRIMARY")
        refresh_btn.pack(side=LEFT, padx=10)
        ToolTip(refresh_btn, "Refresh the list of available microphones.")

        # Transcription Text Area
        self.text_area = scrolledtext.ScrolledText(self, wrap=tk.WORD, width=80, height=12, font=("Segoe UI", 11))
        self.text_area.pack(padx=20, pady=10, fill=tk.X)

        # Control Buttons
        control_frame = ttk.Frame(self, padding=10)
        control_frame.pack(side=TOP, fill=tk.X, padx=20, pady=10)
        ttk.Label(control_frame, text="Controls", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w", padx=5, pady=(0, 5))
        main_controls = ttk.Frame(control_frame)
        main_controls.grid(row=1, column=0, sticky="w")
        self.record_button = ttk.Button(main_controls, text="Record", width=10, command=self.start_recording, bootstyle="success")
        self.record_button.grid(row=0, column=0, padx=5, pady=5)
        ToolTip(self.record_button, "Start recording audio.")
        self.stop_button = ttk.Button(main_controls, text="Stop", width=10, command=self.stop_recording, state=DISABLED, bootstyle="danger")
        self.stop_button.grid(row=0, column=1, padx=5, pady=5)
        ToolTip(self.stop_button, "Stop recording audio.")
        self.new_session_button = ttk.Button(main_controls, text="New Dictation", width=12, command=self.new_session, bootstyle="warning")
        self.new_session_button.grid(row=0, column=2, padx=5, pady=5)
        ToolTip(self.new_session_button, "Start a new dictation session.")
        self.clear_button = ttk.Button(main_controls, text="Clear Text", width=10, command=self.clear_text, bootstyle="warning")
        self.clear_button.grid(row=0, column=3, padx=5, pady=5)
        ToolTip(self.clear_button, "Clear the transcription text.")
        self.copy_button = ttk.Button(main_controls, text="Copy Text", width=10, command=self.copy_text, bootstyle="PRIMARY")
        self.copy_button.grid(row=0, column=4, padx=5, pady=5)
        ToolTip(self.copy_button, "Copy the text to the clipboard.")
        self.save_button = ttk.Button(main_controls, text="Save", width=10, command=self.save_text, bootstyle="PRIMARY")
        self.save_button.grid(row=0, column=5, padx=5, pady=5)
        ToolTip(self.save_button, "Save the transcription and audio to files.")
        self.load_button = ttk.Button(main_controls, text="Load", width=10, command=self.load_audio_file, bootstyle="PRIMARY")
        self.load_button.grid(row=0, column=6, padx=5, pady=5)
        ToolTip(self.load_button, "Load an audio file and transcribe.")

        # AI Assist Section
        ttk.Label(control_frame, text="AI Assist", font=("Segoe UI", 11, "bold")).grid(row=2, column=0, sticky="w", padx=5, pady=(10, 5))
        ai_buttons = ttk.Frame(control_frame)
        ai_buttons.grid(row=3, column=0, sticky="w")
        self.refine_button = ttk.Button(ai_buttons, text="Refine Text", width=15, command=self.refine_text, bootstyle="SECONDARY")
        self.refine_button.grid(row=0, column=0, padx=5, pady=5)
        ToolTip(self.refine_button, "Refine text using OpenAI.")
        self.improve_button = ttk.Button(ai_buttons, text="Improve Text", width=15, command=self.improve_text, bootstyle="SECONDARY")
        self.improve_button.grid(row=0, column=1, padx=5, pady=5)
        ToolTip(self.improve_button, "Improve text clarity using OpenAI.")
        self.soap_button = ttk.Button(ai_buttons, text="SOAP Note", width=15, command=self.create_soap_note, bootstyle="SECONDARY")
        self.soap_button.grid(row=0, column=2, padx=5, pady=5)
        ToolTip(self.soap_button, "Create a SOAP note using OpenAI.")

        # Status Bar
        status_frame = ttk.Frame(self, padding=(10, 5))
        status_frame.pack(side=BOTTOM, fill=tk.X)
        self.status_label = ttk.Label(status_frame, text="Status: Idle", anchor="w")
        self.status_label.pack(side=LEFT, fill=tk.X, expand=True)
        self.progress_bar = ttk.Progressbar(status_frame, mode="indeterminate")
        self.progress_bar.pack(side=RIGHT, padx=10)
        self.progress_bar.stop()
        self.progress_bar.pack_forget()

    def bind_shortcuts(self) -> None:
        self.bind("<Control-n>", lambda event: self.new_session())
        self.bind("<Control-s>", lambda event: self.save_text())
        self.bind("<Control-c>", lambda event: self.copy_text())
        self.bind("<Control-l>", lambda event: self.load_audio_file())  # added shortcut for loading a file

    def show_about(self) -> None:
        messagebox.showinfo("About", "Medical Dictation App\nDeveloped with Python and Tkinter (ttkbootstrap).")

    def show_shortcuts(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Shortcuts & Voice Commands")
        dialog.geometry("700x500")
        dialog.transient(self)
        dialog.grab_set()
        notebook = ttk.Notebook(dialog)
        notebook.pack(expand=True, fill="both", padx=10, pady=10)
        kb_frame = ttk.Frame(notebook)
        notebook.add(kb_frame, text="Keyboard Shortcuts")
        kb_tree = ttk.Treeview(kb_frame, columns=("Command", "Description"), show="headings")
        kb_tree.heading("Command", text="Command")
        kb_tree.heading("Description", text="Description")
        kb_tree.column("Command", width=150, anchor="w")
        kb_tree.column("Description", width=500, anchor="w")
        kb_tree.pack(expand=True, fill="both", padx=10, pady=10)
        for cmd, desc in {"Ctrl+N": "New dictation", "Ctrl+S": "Save", "Ctrl+C": "Copy text", "Ctrl+L": "Load Audio File"}.items():
            kb_tree.insert("", tk.END, values=(cmd, desc))
        vc_frame = ttk.Frame(notebook)
        notebook.add(vc_frame, text="Voice Commands")
        vc_tree = ttk.Treeview(vc_frame, columns=("Command", "Action"), show="headings")
        vc_tree.heading("Command", text="Voice Command")
        vc_tree.heading("Action", text="Action")
        vc_tree.column("Command", width=200, anchor="w")
        vc_tree.column("Action", width=450, anchor="w")
        vc_tree.pack(expand=True, fill="both", padx=10, pady=10)
        for cmd, act in {
            "new paragraph": "Insert two newlines",
            "new line": "Insert a newline",
            "full stop": "Insert period & capitalize next",
            "delete last word": "Delete last word"
        }.items():
            vc_tree.insert("", tk.END, values=(cmd, act))
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

    def show_settings_dialog(self, title: str, config_key: str, current_prompt: str, current_model: str, save_callback: callable) -> None:
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.geometry("800x500")
        dialog.transient(self)
        dialog.grab_set()
        frame = ttk.LabelFrame(dialog, text=title, padding=10)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        ttk.Label(frame, text="Prompt:").grid(row=0, column=0, sticky="nw")
        if title in ("SOAP Note Settings", "Improve Text Settings", "Refine Text Settings"):
            import tkinter.scrolledtext as scrolledtext
            prompt_text = scrolledtext.ScrolledText(frame, width=60, height=10)
        else:
            prompt_text = tk.Text(frame, width=60, height=5)
        prompt_text.grid(row=0, column=1, padx=5, pady=5)
        prompt_text.insert(tk.END, current_prompt)
        ttk.Label(frame, text="Model:").grid(row=1, column=0, sticky="nw")
        model_entry = ttk.Entry(frame, width=60)
        model_entry.grid(row=1, column=1, padx=5, pady=5)
        model_entry.insert(0, current_model)
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Save", command=lambda: [save_callback(prompt_text.get("1.0", tk.END).strip(), model_entry.get().strip()), dialog.destroy()]).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def show_refine_settings_dialog(self) -> None:
        from settings import SETTINGS
        cfg = SETTINGS.get("refine_text", {})
        self.show_settings_dialog(
            title="Refine Text Settings",
            config_key="refine_text",
            current_prompt=cfg.get("prompt", ""),
            current_model=cfg.get("model", ""),
            save_callback=self.save_refine_settings
        )

    def show_improve_settings_dialog(self) -> None:
        from settings import SETTINGS
        cfg = SETTINGS.get("improve_text", {})
        self.show_settings_dialog(
            title="Improve Text Settings",
            config_key="improve_text",
            current_prompt=cfg.get("prompt", ""),
            current_model=cfg.get("model", ""),
            save_callback=self.save_improve_settings
        )

    def show_soap_settings_dialog(self) -> None:
        from settings import SETTINGS, _DEFAULT_SETTINGS
        cfg = SETTINGS.get("soap_note", {})
        default_prompt = _DEFAULT_SETTINGS["soap_note"]["system_message"]
        default_model = _DEFAULT_SETTINGS["soap_note"]["model"]
        self.show_settings_dialog(
            title="SOAP Note Settings",
            config_key="soap_note",
            current_prompt=cfg.get("system_message") or default_prompt,
            current_model=cfg.get("model") or default_model,  # fallback to default model if missing
            save_callback=self.save_soap_settings
        )

    def save_refine_settings(self, prompt: str, model: str) -> None:
        from settings import save_settings, SETTINGS
        SETTINGS["refine_text"] = {"prompt": prompt, "model": model}
        save_settings(SETTINGS)
        self.update_status("Refine settings saved.")

    def save_improve_settings(self, prompt: str, model: str) -> None:
        from settings import save_settings, SETTINGS
        SETTINGS["improve_text"] = {"prompt": prompt, "model": model}
        save_settings(SETTINGS)
        self.update_status("Improve settings saved.")

    def save_soap_settings(self, prompt: str, model: str) -> None:
        from settings import save_settings, SETTINGS
        SETTINGS["soap_note"] = {"system_message": prompt, "model": model}
        save_settings(SETTINGS)
        self.update_status("SOAP note settings saved.")

    def new_session(self) -> None:
        if messagebox.askyesno("New Dictation", "Start a new dictation? Unsaved changes will be lost."):
            self.text_area.delete("1.0", tk.END)
            self.appended_chunks.clear()
            self.audio_segments.clear()

    def save_text(self) -> None:
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
                if self.audio_segments:
                    combined = self.audio_segments[0]
                    for seg in self.audio_segments[1:]:
                        combined += seg
                    base, _ = os.path.splitext(file_path)
                    combined.export(f"{base}.wav", format="wav")
                    messagebox.showinfo("Save Audio", f"Audio saved as: {base}.wav")
                messagebox.showinfo("Save Text", "Text saved successfully.")
            except Exception as e:
                messagebox.showerror("Save Text", f"Error: {e}")

    def copy_text(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.text_area.get("1.0", tk.END))
        self.update_status("Text copied to clipboard.")

    def clear_text(self) -> None:
        if messagebox.askyesno("Clear Text", "Clear the text?"):
            self.text_area.delete("1.0", tk.END)
            self.appended_chunks.clear()
            self.audio_segments.clear()

    def append_text(self, text: str) -> None:
        current = self.text_area.get("1.0", "end-1c")
        if (self.capitalize_next or not current or current[-1] in ".!?") and text:
            text = text[0].upper() + text[1:]
            self.capitalize_next = False
        self.text_area.insert(tk.END, (" " if current and current[-1] != "\n" else "") + text)
        self.appended_chunks.append(f"chunk_{len(self.appended_chunks)}")
        self.text_area.see(tk.END)

    def scratch_that(self) -> None:
        if not self.appended_chunks:
            self.update_status("Nothing to scratch.")
            return
        tag = self.appended_chunks.pop()
        ranges = self.text_area.tag_ranges(tag)
        if ranges:
            self.text_area.delete(ranges[0], ranges[1])
            self.text_area.tag_delete(tag)
            self.update_status("Last added text removed.")
        else:
            self.update_status("No tagged text found.")

    def delete_last_word(self) -> None:
        current = self.text_area.get("1.0", "end-1c")
        if current:
            words = current.split()
            self.text_area.delete("1.0", tk.END)
            self.text_area.insert(tk.END, " ".join(words[:-1]))
            self.text_area.see(tk.END)

    def update_status(self, message: str) -> None:
        self.status_label.config(text=f"Status: {message}")

    def start_recording(self) -> None:
        if not self.listening:
            self.update_status("Listening...")
            try:
                mic = sr.Microphone(device_index=self.mic_combobox.current())
            except Exception as e:
                messagebox.showerror("Microphone Error", f"Error accessing microphone: {e}")
                logging.error("Microphone access error", exc_info=True)
                return
            self.stop_listening_function = self.recognizer.listen_in_background(mic, self.callback, phrase_time_limit=10)
            self.listening = True
            self.record_button.config(state=DISABLED)
            self.stop_button.config(state=NORMAL)

    def stop_recording(self) -> None:
        if self.listening and self.stop_listening_function:
            self.stop_listening_function(wait_for_stop=False)
            self.listening = False
            self.update_status("Idle")
            self.record_button.config(state=NORMAL)
            self.stop_button.config(state=DISABLED)

    def callback(self, recognizer: sr.Recognizer, audio: sr.AudioData) -> None:
        self.executor.submit(self.process_audio, recognizer, audio)

    def process_audio(self, recognizer: sr.Recognizer, audio: sr.AudioData) -> None:
        try:
            channels = getattr(audio, "channels", 1)
            segment = AudioSegment(
                data=audio.get_raw_data(),
                sample_width=audio.sample_width,
                frame_rate=audio.sample_rate,
                channels=channels
            )
            self.audio_segments.append(segment)
            if self.deepgram_client:
                buf = BytesIO()
                segment.export(buf, format="wav")
                buf.seek(0)
                options = PrerecordedOptions(model="nova-2-medical", language="en-US")
                response = self.deepgram_client.listen.rest.v("1").transcribe_file({"buffer": buf}, options)
                transcript = json.loads(response.to_json(indent=4))["results"]["channels"][0]["alternatives"][0]["transcript"]
            else:
                transcript = recognizer.recognize_google(audio, language=self.recognition_language)
            self.after(0, self.handle_recognized_text, transcript)
        except sr.UnknownValueError:
            logging.info("Audio not understood.")
            self.after(0, self.update_status, "Audio not understood")
        except sr.RequestError as e:
            logging.error("Request error", exc_info=True)
            self.after(0, self.update_status, f"Request error: {e}")
        except Exception as e:
            logging.error("Processing error", exc_info=True)
            self.after(0, self.update_status, f"Error: {e}")

    def handle_recognized_text(self, text: str) -> None:
        if not text.strip():
            return
        commands = {
            "new paragraph": lambda: self.text_area.insert(tk.END, "\n\n"),
            "new line": lambda: self.text_area.insert(tk.END, "\n"),
            "full stop": lambda: self.text_area.insert(tk.END, ". "),
            "comma": lambda: self.text_area.insert(tk.END, ", "),
            "question mark": lambda: self.text_area.insert(tk.END, "? "),
            "exclamation point": lambda: self.text_area.insert(tk.END, "! "),
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

    def _process_text_with_ai(self, api_func: Callable[[str], str], success_message: str, button: ttk.Button) -> None:
        text = self.text_area.get("1.0", tk.END).strip()
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
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert(tk.END, new_text)
        self.update_status(success_message)
        button.config(state=NORMAL)
        self.progress_bar.stop()
        self.progress_bar.pack_forget()

    def refine_text(self) -> None:
        self._process_text_with_ai(adjust_text_with_openai, "Text refined.", self.refine_button)

    def improve_text(self) -> None:
        self._process_text_with_ai(improve_text_with_openai, "Text improved.", self.improve_button)

    def create_soap_note(self) -> None:
        self._process_text_with_ai(create_soap_note_with_openai, "SOAP note created.", self.soap_button)

    def load_audio_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select Audio File",
            filetypes=[("Audio Files", "*.wav *.mp3"), ("All Files", "*.*")]
        )
        if not file_path:
            return
        self.update_status("Transcribing audio...")
        self.load_button.config(state=DISABLED)
        self.progress_bar.pack(side=RIGHT, padx=10)
        self.progress_bar.start()

        def task() -> None:
            transcript = ""
            try:
                if file_path.lower().endswith(".mp3"):
                    seg = AudioSegment.from_file(file_path, format="mp3")
                elif file_path.lower().endswith(".wav"):
                    seg = AudioSegment.from_file(file_path, format="wav")
                else:
                    raise ValueError("Unsupported audio format.")
                if self.deepgram_client:
                    buf = BytesIO()
                    seg.export(buf, format="wav")
                    buf.seek(0)
                    options = PrerecordedOptions(model="nova-2-medical", language="en-US")
                    response = self.deepgram_client.listen.rest.v("1").transcribe_file({"buffer": buf}, options)
                    transcript = json.loads(response.to_json(indent=4))["results"]["channels"][0]["alternatives"][0]["transcript"]
                else:
                    raise Exception("Deepgram API key not provided.")
            except Exception as e:
                logging.error("Error transcribing audio", exc_info=True)
                self.after(0, lambda: messagebox.showerror("Transcription Error", f"Error: {e}"))
            else:
                self.after(0, lambda: self._update_text_area(transcript, "Audio transcribed successfully.", self.load_button))
            finally:
                self.after(0, lambda: self.load_button.config(state=NORMAL))
                self.after(0, self.progress_bar.stop)
                self.after(0, self.progress_bar.pack_forget)
        self.executor.submit(task)

    def refresh_microphones(self) -> None:
        names = get_valid_microphones() or sr.Microphone.list_microphone_names()
        self.mic_combobox['values'] = names
        if names:
            self.mic_combobox.current(0)
        else:
            self.mic_combobox.set("No microphone found")
        self.update_status("Microphone list refreshed.")

    def on_closing(self) -> None:
        try:
            self.executor.shutdown(wait=False)
        except Exception as e:
            logging.error("Error shutting down executor", exc_info=True)
        self.destroy()

# If this module is run directly, start the app
def main() -> None:
    app = MedicalDictationApp()
    app.mainloop()



