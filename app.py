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
from dialogs import create_toplevel_dialog, show_settings_dialog, askstring_min, ask_conditions_dialog

load_dotenv()

# API Keys & Logging Setup
openai.api_key = os.getenv("OPENAI_API_KEY")
deepgram_api_key = os.getenv("DEEPGRAM_API_KEY", "")
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class MedicalDictationApp(ttk.Window):
    def __init__(self) -> None:
        super().__init__(themename="flatly")
        self.title("Medical Assistant")
        self.geometry("1200x900")
        self.minsize(1200, 900)
        self.config(bg="#f0f0f0")

        self.recognition_language = os.getenv("RECOGNITION_LANGUAGE", "en-US")
        self.deepgram_api_key = deepgram_api_key
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self.deepgram_client = DeepgramClient(api_key=self.deepgram_api_key) if self.deepgram_api_key else None

        self.appended_chunks = []
        self.capitalize_next = False
        self.audio_segments = []
        self.soap_recording = False
        self.soap_audio_segments = []
        self.soap_stop_listening_function = None

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
        text_settings_menu.add_command(label="SOAP Note Settings", command=self.show_soap_settings_dialog)
        text_settings_menu.add_command(label="Referral Prompt Settings", command=self.show_referral_settings_dialog)
        settings_menu.add_cascade(label="Prompt Settings", menu=text_settings_menu)
        settings_menu.add_command(label="Export Prompts", command=self.export_prompts)
        settings_menu.add_command(label="Import Prompts", command=self.import_prompts)
        settings_menu.add_command(label="Set Storage Folder", command=self.set_default_folder)
        settings_menu.add_command(label="Set AI Provider", command=self.set_ai_provider)
        menubar.add_cascade(label="Settings", menu=settings_menu)

        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="About", command=self.show_about)
        helpmenu.add_command(label="Shortcuts & Voice Commands", command=self.show_shortcuts)
        menubar.add_cascade(label="Help", menu=helpmenu)

        self.config(menu=menubar)

    def set_ai_provider(self) -> None:
        from settings import SETTINGS, save_settings
        dialog = tk.Toplevel(self)
        dialog.title("Select AI Provider")
        dialog.geometry("400x200")
        dialog.transient(self)
        dialog.grab_set()
        ai_var = tk.StringVar(value=SETTINGS.get("ai_provider", "openai"))
        ttk.Label(dialog, text="Select AI Provider:").pack(pady=10)
        # NEW: Added Grok option along with OpenAI and Perplexity
        for text, value in [("OpenAI", "openai"), ("Perplexity", "perplexity"), ("Grok", "grok")]:
            ttk.Radiobutton(dialog, text=text, variable=ai_var, value=value).pack(anchor="w", padx=20)
        def save():
            SETTINGS["ai_provider"] = ai_var.get()
            save_settings(SETTINGS)
            self.provider_label.config(text=f"Provider: {ai_var.get().capitalize()}")
            self.update_status(f"AI Provider set to {ai_var.get().capitalize()}.")
            dialog.destroy()
        ttk.Button(dialog, text="Save", command=save).pack(pady=10)

    def set_default_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select Storage Folder")
        if folder:
            try:
                from settings import SETTINGS, save_settings
                SETTINGS["default_storage_folder"] = folder
                save_settings(SETTINGS)
                self.update_status(f"Default storage folder set to: {folder}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to set folder: {e}")

    def export_prompts(self) -> None:
        from settings import SETTINGS, _DEFAULT_SETTINGS
        data = {}
        for key in ("refine_text", "improve_text", "soap_note"):
            default = _DEFAULT_SETTINGS.get(key, {})
            current = SETTINGS.get(key, {})
            entry = {}
            if key == "soap_note":
                entry["prompt"] = current.get("system_message", default.get("system_message", ""))
            else:
                entry["prompt"] = current.get("prompt", default.get("prompt", ""))
            entry["model"] = current.get("model", default.get("model", ""))
            data[key] = entry
        file_path = filedialog.asksaveasfilename(
            title="Export Prompts and Models",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                messagebox.showinfo("Export Prompts", f"Prompts and models exported to {file_path}")
            except Exception as e:
                messagebox.showerror("Export Prompts", f"Error exporting prompts: {e}")

    def import_prompts(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Import Prompts and Models",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                from settings import SETTINGS, save_settings
                for key in ("refine_text", "improve_text", "soap_note"):
                    if key in data:
                        SETTINGS[key] = data[key]
                save_settings(SETTINGS)
                messagebox.showinfo("Import Prompts", "Prompts and models updated successfully.")
            except Exception as e:
                messagebox.showerror("Import Prompts", f"Error importing prompts: {e}")

    def create_widgets(self) -> None:
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
        from settings import SETTINGS
        provider = SETTINGS.get("ai_provider", "openai")
        self.provider_label = ttk.Label(mic_frame, text=f"Provider: {provider.capitalize()}")
        self.provider_label.pack(side=LEFT, padx=10)

        # NEW: Force use of "clam" theme and configure custom Notebook style
        style = ttk.Style()
        # Removed theme_use("clam") to prevent conflict with ttkbootstrap's theme
        # style.theme_use("clam")
        style.configure("Green.TNotebook", background="white", borderwidth=0)
        style.configure("Green.TNotebook.Tab", padding=[10, 5], background="lightgrey")
        style.map("Green.TNotebook.Tab",
            background=[("selected", "green"), ("active", "green"), ("!selected", "lightgrey")])
        # Create the Notebook using the custom style
        self.notebook = ttk.Notebook(self, style="Green.TNotebook")

        # NEW: Create notebook with four tabs
        self.notebook.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)
        transcript_frame = ttk.Frame(self.notebook)
        soap_frame = ttk.Frame(self.notebook)
        referral_frame = ttk.Frame(self.notebook)
        dictation_frame = ttk.Frame(self.notebook)  # NEW: Dictation tab
        self.notebook.add(transcript_frame, text="Transcript")
        self.notebook.add(soap_frame, text="SOAP Note")
        self.notebook.add(referral_frame, text="Referral")
        self.notebook.add(dictation_frame, text="Dictation")  # NEW
        self.transcript_text = scrolledtext.ScrolledText(transcript_frame, wrap=tk.WORD, width=80, height=12, font=("Segoe UI", 11), undo=True, autoseparators=False)
        self.transcript_text.pack(fill=tk.BOTH, expand=True)
        self.soap_text = scrolledtext.ScrolledText(soap_frame, wrap=tk.WORD, width=80, height=12, font=("Segoe UI", 11), undo=True, autoseparators=False)
        self.soap_text.pack(fill=tk.BOTH, expand=True)
        self.referral_text = scrolledtext.ScrolledText(referral_frame, wrap=tk.WORD, width=80, height=12, font=("Segoe UI", 11), undo=True, autoseparators=False)
        self.referral_text.pack(fill=tk.BOTH, expand=True)
        self.dictation_text = scrolledtext.ScrolledText(dictation_frame, wrap=tk.WORD, width=80, height=12, font=("Segoe UI", 11), undo=True, autoseparators=False)  # NEW
        self.dictation_text.pack(fill=tk.BOTH, expand=True)
        # NEW: Set initial active text widget and bind tab change event
        self.active_text_widget = self.transcript_text
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        control_frame = ttk.Frame(self, padding=10)
        control_frame.pack(side=TOP, fill=tk.X, padx=20, pady=10)
        ttk.Label(control_frame, text="Individual Controls", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w", padx=5, pady=(0, 5))
        main_controls = ttk.Frame(control_frame)
        main_controls.grid(row=1, column=0, sticky="w")
        self.record_button = ttk.Button(main_controls, text="Record", width=10, command=self.start_recording, bootstyle="success")
        self.record_button.grid(row=0, column=0, padx=5, pady=5)
        ToolTip(self.record_button, "Start recording audio.")
        self.stop_button = ttk.Button(main_controls, text="Stop", width=10, command=self.stop_recording, state=DISABLED, bootstyle="danger")
        self.stop_button.grid(row=0, column=1, padx=5, pady=5)
        ToolTip(self.stop_button, "Stop recording audio.")
        # Change button text from "New Dictation" to "New Session"
        self.new_session_button = ttk.Button(main_controls, text="New Session", width=12, command=self.new_session, bootstyle="warning")
        self.new_session_button.grid(row=0, column=2, padx=5, pady=5)
        ToolTip(self.new_session_button, "Start a new session.")
        self.copy_button = ttk.Button(main_controls, text="Copy Text", width=10, command=self.copy_text, bootstyle="PRIMARY")
        self.copy_button.grid(row=0, column=3, padx=5, pady=5)
        ToolTip(self.copy_button, "Copy the text to the clipboard.")
        self.undo_button = ttk.Button(main_controls, text="Undo", width=10, command=self.undo_text, bootstyle="SECONDARY")
        self.undo_button.grid(row=0, column=4, padx=5, pady=5)
        ToolTip(self.undo_button, "Undo the last change.")
        # NEW: Add redo button next to undo button
        self.redo_button = ttk.Button(main_controls, text="Redo", width=10, command=self.redo_text, bootstyle="SECONDARY")
        self.redo_button.grid(row=0, column=5, padx=5, pady=5)
        ToolTip(self.redo_button, "Redo the last undone change.")
        # Adjust subsequent buttons' grid columns
        self.save_button = ttk.Button(main_controls, text="Save", width=10, command=self.save_text, bootstyle="PRIMARY")
        self.save_button.grid(row=0, column=6, padx=5, pady=5)
        ToolTip(self.save_button, "Save the transcription and audio to files.")
        self.load_button = ttk.Button(main_controls, text="Load", width=10, command=self.load_audio_file, bootstyle="PRIMARY")
        self.load_button.grid(row=0, column=7, padx=5, pady=5)
        ToolTip(self.load_button, "Load an audio file and transcribe.")

        ttk.Label(control_frame, text="AI Assist", font=("Segoe UI", 11, "bold")).grid(row=2, column=0, sticky="w", padx=5, pady=(10, 5))
        ttk.Label(control_frame, text="Individual Controls", font=("Segoe UI", 10, "italic")).grid(row=3, column=0, sticky="w", padx=5, pady=(0, 5))
        ai_buttons = ttk.Frame(control_frame)
        ai_buttons.grid(row=4, column=0, sticky="w")
        self.refine_button = ttk.Button(ai_buttons, text="Refine Text", width=15, command=self.refine_text, bootstyle="SECONDARY")
        self.refine_button.grid(row=0, column=0, padx=5, pady=5)
        ToolTip(self.refine_button, "Refine text using OpenAI.")
        self.improve_button = ttk.Button(ai_buttons, text="Improve Text", width=15, command=self.improve_text, bootstyle="SECONDARY")
        self.improve_button.grid(row=0, column=1, padx=5, pady=5)
        ToolTip(self.improve_button, "Improve text clarity using OpenAI.")
        self.soap_button = ttk.Button(ai_buttons, text="SOAP Note", width=15, command=self.create_soap_note, bootstyle="SECONDARY")
        self.soap_button.grid(row=0, column=2, padx=5, pady=5)
        ToolTip(self.soap_button, "Create a SOAP note using OpenAI.")
        self.referral_button = ttk.Button(ai_buttons, text="Referral", width=15, command=self.create_referral, bootstyle="SECONDARY")
        self.referral_button.grid(row=0, column=3, padx=5, pady=5)
        ToolTip(self.referral_button, "Generate a referral paragraph using OpenAI.")
        
        ttk.Label(control_frame, text="Automation Controls", font=("Segoe UI", 10, "italic")).grid(row=5, column=0, sticky="w", padx=5, pady=(0, 5))
        automation_frame = ttk.Frame(control_frame)
        automation_frame.grid(row=6, column=0, sticky="w")
        self.record_soap_button = ttk.Button(
            automation_frame, text="Record SOAP Note", width=25,
            command=self.toggle_soap_recording, bootstyle="SECONDARY"
        )
        self.record_soap_button.grid(row=0, column=0, padx=5, pady=5)
        ToolTip(self.record_soap_button, "Record audio for SOAP note without live transcription.")
        # New pause/resume button for SOAP Note recording
        self.pause_soap_button = ttk.Button(
            automation_frame, text="Pause", width=15,
            command=self.toggle_soap_pause, bootstyle="SECONDARY", state=tk.DISABLED
        )
        self.pause_soap_button.grid(row=0, column=1, padx=5, pady=5)
        ToolTip(self.pause_soap_button, "Pause/Resume the SOAP note recording.")

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
        self.bind("<Control-l>", lambda event: self.load_audio_file())

    def show_about(self) -> None:
        messagebox.showinfo("About", "Medical Assistant App\nDeveloped with Python and Tkinter (ttkbootstrap).")

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

    def show_refine_settings_dialog(self) -> None:
        from settings import SETTINGS, _DEFAULT_SETTINGS
        cfg = SETTINGS.get("refine_text", {})
        show_settings_dialog(
            parent=self,
            title="Refine Text Settings",
            config=cfg,
            default=_DEFAULT_SETTINGS["refine_text"],
            current_prompt=cfg.get("prompt", ""),
            current_model=cfg.get("model", ""),
            current_perplexity=cfg.get("perplexity_model", ""),
            current_grok=cfg.get("grok_model", ""),
            save_callback=self.save_refine_settings
        )

    def show_improve_settings_dialog(self) -> None:
        from settings import SETTINGS, _DEFAULT_SETTINGS
        cfg = SETTINGS.get("improve_text", {})
        show_settings_dialog(
            parent=self,
            title="Improve Text Settings",
            config=cfg,
            default=_DEFAULT_SETTINGS["improve_text"],
            current_prompt=cfg.get("prompt", ""),
            current_model=cfg.get("model", ""),
            current_perplexity=cfg.get("perplexity_model", ""),
            current_grok=cfg.get("grok_model", ""),
            save_callback=self.save_improve_settings
        )

    def show_soap_settings_dialog(self) -> None:
        from settings import SETTINGS, _DEFAULT_SETTINGS
        cfg = SETTINGS.get("soap_note", {})
        default_prompt = _DEFAULT_SETTINGS["soap_note"].get("system_message", "")
        default_model = _DEFAULT_SETTINGS["soap_note"].get("model", "")
        show_settings_dialog(
            parent=self,
            title="SOAP Note Settings",
            config=cfg,
            default=_DEFAULT_SETTINGS["soap_note"],
            current_prompt=cfg.get("system_message") or default_prompt,
            current_model=cfg.get("model") or default_model,
            current_perplexity=cfg.get("perplexity_model", ""),
            current_grok=cfg.get("grok_model", ""),
            save_callback=self.save_soap_settings
        )

    def show_referral_settings_dialog(self) -> None:
        from settings import SETTINGS, _DEFAULT_SETTINGS
        cfg = SETTINGS.get("referral", {})
        default_prompt = _DEFAULT_SETTINGS["referral"].get("prompt", "")
        default_model = _DEFAULT_SETTINGS["referral"].get("model", "")
        show_settings_dialog(
            parent=self,
            title="Referral Prompt Settings",
            config=cfg,
            default=_DEFAULT_SETTINGS["referral"],
            current_prompt=cfg.get("prompt", default_prompt),
            current_model=cfg.get("model", default_model),
            current_perplexity=cfg.get("perplexity_model", ""),
            current_grok=cfg.get("grok_model", ""),
            save_callback=self.save_referral_settings
        )

    def save_refine_settings(self, prompt: str, openai_model: str, perplexity_model: str, grok_model: str) -> None:
        from settings import save_settings, SETTINGS
        SETTINGS["refine_text"] = {
            "prompt": prompt,
            "model": openai_model,
            "perplexity_model": perplexity_model,
            "grok_model": grok_model
        }
        save_settings(SETTINGS)
        self.update_status("Refine settings saved.")

    def save_improve_settings(self, prompt: str, openai_model: str, perplexity_model: str, grok_model: str) -> None:
        from settings import save_settings, SETTINGS
        SETTINGS["improve_text"] = {
            "prompt": prompt,
            "model": openai_model,
            "perplexity_model": perplexity_model,
            "grok_model": grok_model
        }
        save_settings(SETTINGS)
        self.update_status("Improve settings saved.")

    def save_soap_settings(self, prompt: str, openai_model: str, perplexity_model: str, grok_model: str) -> None:
        from settings import save_settings, SETTINGS
        SETTINGS["soap_note"] = {
            "system_message": prompt,
            "model": openai_model,
            "perplexity_model": perplexity_model,
            "grok_model": grok_model
        }
        save_settings(SETTINGS)
        self.update_status("SOAP note settings saved.")

    def save_referral_settings(self, prompt: str, openai_model: str, perplexity_model: str, grok_model: str) -> None:
        from settings import SETTINGS, save_settings
        SETTINGS["referral"] = {
            "prompt": prompt,
            "model": openai_model,
            "perplexity_model": perplexity_model,
            "grok_model": grok_model
        }
        save_settings(SETTINGS)
        self.update_status("Referral settings saved.")

    def new_session(self) -> None:
        if messagebox.askyesno("New Dictation", "Start a new session? Unsaved changes will be lost."):
            # Clear text and reset undo/redo history for all tabs
            for widget in [self.transcript_text, self.soap_text, self.referral_text, self.dictation_text]:
                widget.delete("1.0", tk.END)
                widget.edit_reset()  # Clear undo/redo history
            # Clear audio segments and other stored data
            self.appended_chunks.clear()
            self.audio_segments.clear()
            self.soap_audio_segments.clear()

    def save_text(self) -> None:
        text = self.transcript_text.get("1.0", tk.END).strip()
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
        active_widget = self.get_active_text_widget()
        self.clipboard_clear()
        self.clipboard_append(active_widget.get("1.0", tk.END))
        self.update_status("Text copied to clipboard.")

    def clear_text(self) -> None:
        if messagebox.askyesno("Clear Text", "Clear the text?"):
            self.transcript_text.delete("1.0", tk.END)
            self.appended_chunks.clear()
            self.audio_segments.clear()

    def append_text(self, text: str) -> None:
        current = self.transcript_text.get("1.0", "end-1c")
        if (self.capitalize_next or not current or current[-1] in ".!?") and text:
            text = text[0].upper() + text[1:]
            self.capitalize_next = False
        self.transcript_text.insert(tk.END, (" " if current and current[-1] != "\n" else "") + text)
        self.appended_chunks.append(f"chunk_{len(self.appended_chunks)}")
        self.transcript_text.see(tk.END)

    def scratch_that(self) -> None:
        if not self.appended_chunks:
            self.update_status("Nothing to scratch.")
            return
        tag = self.appended_chunks.pop()
        ranges = self.transcript_text.tag_ranges(tag)
        if ranges:
            self.transcript_text.delete(ranges[0], ranges[1])
            self.transcript_text.tag_delete(tag)
            self.update_status("Last added text removed.")
        else:
            self.update_status("No tagged text found.")

    def delete_last_word(self) -> None:
        current = self.transcript_text.get("1.0", "end-1c")
        if current:
            words = current.split()
            self.transcript_text.delete("1.0", tk.END)
            self.transcript_text.insert(tk.END, " ".join(words[:-1]))
            self.transcript_text.see(tk.END)

    def update_status(self, message: str) -> None:
        self.status_label.config(text=f"Status: {message}")

    def start_recording(self) -> None:
        # Switch focus to the Dictation tab (index 3)
        self.notebook.select(3)
        if not self.listening:
            self.update_status("Listening...")
            try:
                import speech_recognition as sr
                selected_index = self.mic_combobox.current()
                mic = sr.Microphone(device_index=selected_index)
            except Exception as e:
                logging.error("Error creating microphone", exc_info=True)
                self.update_status("Error accessing microphone.")
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

    def _combine_audio_segments(self, segments: list) -> AudioSegment:
        # Combine list of audio segments into one
        if not segments:
            return None
        combined = segments[0]
        for seg in segments[1:]:
            combined += seg
        return combined

    def _transcribe_audio(self, segment: AudioSegment) -> str:
        try:
            if self.deepgram_client:
                buf = BytesIO()
                segment.export(buf, format="wav")
                buf.seek(0)
                options = PrerecordedOptions(model="nova-2-medical", language="en-US")
                try:
                    response = self.deepgram_client.listen.rest.v("1").transcribe_file({"buffer": buf}, options)
                    transcript = json.loads(response.to_json(indent=4))["results"]["channels"][0]["alternatives"][0]["transcript"]
                    return transcript
                except Exception as e:
                    logging.error("Deepgram API timeout, falling back to Google Speech Recognition", exc_info=True)
                    self.update_status(f"Deepgram API timeout: {str(e)}")
                    temp_file = "temp.wav"
                    segment.export(temp_file, format="wav")
                    with sr.AudioFile(temp_file) as source:
                        audio_data = self.recognizer.record(source)
                    transcript = self.recognizer.recognize_google(audio_data, language=self.recognition_language)
                    os.remove(temp_file)
                    return transcript
            else:
                temp_file = "temp.wav"
                segment.export(temp_file, format="wav")
                with sr.AudioFile(temp_file) as source:
                    audio_data = self.recognizer.record(source)
                transcript = self.recognizer.recognize_google(audio_data, language=self.recognition_language)
                os.remove(temp_file)
                return transcript
        except Exception as e:
            logging.error("Transcription error", exc_info=True)
            self.update_status(f"Transcription error: {str(e)}")
            return ""

    # Refactor process_audio using the new helper
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
            transcript = self._transcribe_audio(segment)
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

    # Refactor process_soap_recording to use helpers
    def process_soap_recording(self) -> None:
        def task() -> None:
            try:
                combined = self._combine_audio_segments(self.soap_audio_segments)
                transcript = self._transcribe_audio(combined) if combined else ""
                soap_note = create_soap_note_with_openai(transcript)
            except Exception as e:
                soap_note = f"Error processing SOAP note: {e}"
                transcript = ""
            def update_ui():
                self.transcript_text.delete("1.0", tk.END)
                self.transcript_text.insert(tk.END, transcript)
                self._update_text_area(soap_note, "SOAP note created from recording.", self.record_soap_button, self.soap_text)
                self.notebook.select(1)
            self.after(0, update_ui)
        self.executor.submit(task)

    # Refactor load_audio_file to use the transcription helper
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
                transcript = self._transcribe_audio(seg)
            except Exception as e:
                logging.error("Error transcribing audio", exc_info=True)
                self.after(0, lambda: messagebox.showerror("Transcription Error", f"Error: {e}"))
            else:
                self.after(0, lambda: [
                    self._update_text_area(transcript, "Audio transcribed successfully.", self.load_button, self.transcript_text),
                    self.notebook.select(0)
                ])
            finally:
                self.after(0, lambda: self.load_button.config(state=NORMAL))
                self.after(0, self.progress_bar.stop)
                self.after(0, self.progress_bar.pack_forget)
        self.executor.submit(task)

    def append_text_to_widget(self, text: str, widget: tk.Widget) -> None:
        current = widget.get("1.0", "end-1c")
        if (self.capitalize_next or not current or current[-1] in ".!?") and text:
            text = text[0].upper() + text[1:]
            self.capitalize_next = False
        widget.insert(tk.END, (" " if current and current[-1] != "\n" else "") + text)
        widget.see(tk.END)

    def handle_recognized_text(self, text: str) -> None:
        if not text.strip():
            return
        # Use the active text widget instead of transcript_text directly
        active_widget = self.get_active_text_widget()
        commands = {
            "new paragraph": lambda: active_widget.insert(tk.END, "\n\n"),
            "new line": lambda: active_widget.insert(tk.END, "\n"),
            "full stop": lambda: active_widget.insert(tk.END, ". "),
            "comma": lambda: active_widget.insert(tk.END, ", "),
            "question mark": lambda: active_widget.insert(tk.END, "? "),
            "exclamation point": lambda: active_widget.insert(tk.END, "! "),
            "semicolon": lambda: active_widget.insert(tk.END, "; "),
            "colon": lambda: active_widget.insert(tk.END, ": "),
            "open quote": lambda: active_widget.insert(tk.END, "\""),
            "close quote": lambda: active_widget.insert(tk.END, "\""),
            "open parenthesis": lambda: active_widget.insert(tk.END, "("),
            "close parenthesis": lambda: active_widget.insert(tk.END, ")"),
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
            self.append_text_to_widget(text, active_widget)

    def _process_text_with_ai(self, api_func: Callable[[str], str], success_message: str, button: ttk.Button, target_widget: tk.Widget) -> None:
        text = target_widget.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Process Text", "There is no text to process.")
            return
        self.update_status("Processing text...")
        button.config(state=DISABLED)
        self.progress_bar.pack(side=RIGHT, padx=10)
        self.progress_bar.start()

        def task() -> None:
            result = api_func(text)
            self.after(0, lambda: self._update_text_area(result, success_message, button, target_widget))
        self.executor.submit(task)

    def _update_text_area(self, new_text: str, success_message: str, button: ttk.Button, target_widget: tk.Widget) -> None:
        target_widget.edit_separator()
        target_widget.delete("1.0", tk.END)
        target_widget.insert(tk.END, new_text)
        target_widget.edit_separator()
        self.update_status(success_message)
        button.config(state=NORMAL)
        self.progress_bar.stop()
        self.progress_bar.pack_forget()

    def get_active_text_widget(self) -> tk.Widget:
        return self.active_text_widget

    def refine_text(self) -> None:
        active_widget = self.get_active_text_widget()
        self._process_text_with_ai(adjust_text_with_openai, "Text refined.", self.refine_button, active_widget)

    def improve_text(self) -> None:
        active_widget = self.get_active_text_widget()
        self._process_text_with_ai(improve_text_with_openai, "Text improved.", self.improve_button, active_widget)

    def create_soap_note(self) -> None:
        transcript = self.transcript_text.get("1.0", tk.END).strip()
        if not transcript:
            messagebox.showwarning("Process Text", "There is no text to process.")
            return
        self.update_status("Processing SOAP note...")
        self.soap_button.config(state=DISABLED)
        self.progress_bar.pack(side=RIGHT, padx=10)
        self.progress_bar.start()
        def task() -> None:
            result = create_soap_note_with_openai(transcript)
            self.after(0, lambda: [
                self._update_text_area(result, "SOAP note created.", self.soap_button, self.soap_text),
                self.notebook.select(1)  # Switch focus to SOAP Note tab (index 1)
            ])
        self.executor.submit(task)

    def _get_possible_conditions(self, text: str) -> str:
        from ai import call_ai, remove_markdown, remove_citations
        prompt = ("Extract up to a maximun of 5 relevant medical conditions for a referral from the following text. Keep the condition names simple and specific and not longer that 3 words. "
                  "Return them as a comma-separated list. Text: " + text)
        result = call_ai("gpt-4o", "You are a physician specialized in referrals.", prompt, 0.7, 100)
        conditions = remove_markdown(result).strip()
        conditions = remove_citations(conditions)
        return conditions

    def create_referral(self) -> None:
        # New: Immediately update status and display progress bar on referral click
        self.update_status("Referral button clicked - preparing referral...")
        self.progress_bar.pack(side=RIGHT, padx=10)
        self.progress_bar.start()
        
        text = self.transcript_text.get("1.0", tk.END).strip()
        # New: Get suggested conditions asynchronously
        def get_conditions() -> str:
            return self._get_possible_conditions(text)
        future = self.executor.submit(get_conditions)
        def on_conditions_done(future_result):
            try:
                suggestions = future_result.result() or ""
            except Exception as e:
                suggestions = ""
            # Continue on the main thread
            self.after(0, lambda: self._create_referral_continued(suggestions))
        future.add_done_callback(on_conditions_done)

    def _create_referral_continued(self, suggestions: str) -> None:
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        conditions_list = [cond.strip() for cond in suggestions.split(",") if cond.strip()]
        focus = self.ask_conditions_dialog("Select Conditions", "Select conditions to focus on:", conditions_list)
        if focus is None:
            self.update_status("Referral cancelled.")
            return
        self.update_status("Processing referral...")
        self.progress_bar.pack(side=RIGHT, padx=10)
        self.progress_bar.start()
        def task() -> None:
            transcript = self.transcript_text.get("1.0", tk.END).strip()
            result = __import__("ai").create_referral_with_openai(transcript, focus)
            self.after(0, lambda: [
                self._update_text_area(result, "Referral created.", self.referral_button, self.referral_text),
                self.notebook.select(2)  # Switch focus to Referral tab (index 2)
            ])
        self.executor.submit(task)

    def refresh_microphones(self) -> None:
        names = get_valid_microphones() or sr.Microphone.list_microphone_names()
        self.mic_combobox['values'] = names
        if names:
            self.mic_combobox.current(0)
        else:
            self.mic_combobox.set("No microphone found")
        self.update_status("Microphone list refreshed.")

    def toggle_soap_recording(self) -> None:
        if not self.soap_recording:
            # Clear all text areas and reset audio segments before starting a new SOAP recording session
            self.transcript_text.delete("1.0", tk.END)
            self.soap_text.delete("1.0", tk.END)
            self.referral_text.delete("1.0", tk.END)   # NEW: clear referral tab
            self.dictation_text.delete("1.0", tk.END)   # NEW: clear dictation tab
            self.appended_chunks.clear()
            self.soap_audio_segments.clear()
            self.soap_recording = True
            self.soap_paused = False  # NEW: reset pause state
            self.record_soap_button.config(text="Stop", bootstyle="danger")
            self.pause_soap_button.config(state=tk.NORMAL, text="Pause")  # enable pause button
            self.update_status("Recording SOAP note...")
            try:
                import speech_recognition as sr
                selected_index = self.mic_combobox.current()
                mic = sr.Microphone(device_index=selected_index)
            except Exception as e:
                logging.error("Error creating microphone for SOAP recording", exc_info=True)
                self.update_status("Error accessing microphone for SOAP note.")
                return
            self.soap_stop_listening_function = self.recognizer.listen_in_background(mic, self.soap_callback, phrase_time_limit=10)
        else:
            # Stopping SOAP recording
            if self.soap_stop_listening_function:
                self.soap_stop_listening_function(wait_for_stop=False)
            self.soap_recording = False
            self.soap_paused = False
            # Disable the record SOAP note button for 5 seconds to prevent double click
            self.record_soap_button.config(text="Record SOAP Note", bootstyle="SECONDARY", state=tk.DISABLED)
            self.pause_soap_button.config(state=tk.DISABLED, text="Pause")
            self.update_status("Transcribing SOAP note...")
            import datetime
            folder = SETTINGS.get("default_storage_folder")
            if folder and not os.path.exists(folder):
                os.makedirs(folder)
            now_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
            audio_file_path = os.path.join(folder, f"{now_str}.wav") if folder else f"{now_str}.wav"
            if self.soap_audio_segments:
                combined = self.soap_audio_segments[0]
                for seg in self.soap_audio_segments[1:]:
                    combined += seg
                combined.export(audio_file_path, format="wav")
                self.update_status(f"SOAP audio saved to: {audio_file_path}")
            self.progress_bar.pack(side=RIGHT, padx=10)
            self.progress_bar.start()
            self.process_soap_recording()
            # Re-enable the record button after 5 seconds
            self.after(5000, lambda: self.record_soap_button.config(state=NORMAL))

    def toggle_soap_pause(self) -> None:
        if self.soap_paused:
            self.resume_soap_recording()
        else:
            self.pause_soap_recording()

    def pause_soap_recording(self) -> None:
        if self.soap_recording and not self.soap_paused:
            if self.soap_stop_listening_function:
                self.soap_stop_listening_function(wait_for_stop=False)
            self.soap_paused = True
            self.pause_soap_button.config(text="Resume")
            self.update_status("SOAP note recording paused.")

    def resume_soap_recording(self) -> None:
        if self.soap_recording and self.soap_paused:
            try:
                mic = sr.Microphone()  # Adjust as needed for selected mic
            except Exception as e:
                self.update_status(f"Error accessing microphone: {e}")
                return
            self.soap_stop_listening_function = self.recognizer.listen_in_background(mic, self.soap_callback, phrase_time_limit=10)
            self.soap_paused = False
            self.pause_soap_button.config(text="Pause")
            self.update_status("SOAP note recording resumed.")

    def soap_callback(self, recognizer: sr.Recognizer, audio: sr.AudioData) -> None:
        try:
            channels = getattr(audio, "channels", 1)
            segment = AudioSegment(
                data=audio.get_raw_data(),
                sample_width=audio.sample_width,
                frame_rate=audio.sample_rate,
                channels=channels
            )
            self.soap_audio_segments.append(segment)
        except Exception as e:
            logging.error("Error recording SOAP note chunk", exc_info=True)

    def process_soap_recording(self) -> None:
        def task() -> None:
            try:
                if not self.soap_audio_segments:
                    transcript = ""
                else:
                    combined = self._combine_audio_segments(self.soap_audio_segments)
                    transcript = self._transcribe_audio(combined) if combined else ""
                soap_note = create_soap_note_with_openai(transcript)
            except Exception as e:
                soap_note = f"Error processing SOAP note: {e}"
                transcript = ""
            def update_ui():
                # Update Transcript tab with the obtained transcript
                self.transcript_text.delete("1.0", tk.END)
                self.transcript_text.insert(tk.END, transcript)
                # Update SOAP Note tab with the generated SOAP note
                self._update_text_area(soap_note, "SOAP note created from recording.", self.record_soap_button, self.soap_text)
                # Switch focus to the SOAP Note tab (index 1)
                self.notebook.select(1)
            self.after(0, update_ui)
        self.executor.submit(task)

    def undo_text(self) -> None:
        try:
            widget = self.get_active_text_widget()
            widget.edit_undo()
            self.update_status("Undo performed.")
        except Exception as e:
            self.update_status("Nothing to undo.")

    def redo_text(self) -> None:
        try:
            widget = self.get_active_text_widget()
            widget.edit_redo()
            self.update_status("Redo performed.")
        except Exception as e:
            self.update_status("Nothing to redo.")

    def on_closing(self) -> None:
        try:
            self.executor.shutdown(wait=False)
        except Exception as e:
            logging.error("Error shutting down executor", exc_info=True)
        self.destroy()

    def on_tab_changed(self, event: tk.Event) -> None:
        current = self.notebook.index(self.notebook.select())
        if current == 0:
            self.active_text_widget = self.transcript_text
        elif current == 1:
            self.active_text_widget = self.soap_text
        elif current == 2:
            self.active_text_widget = self.referral_text
        elif current == 3:  # NEW: Dictation tab
            self.active_text_widget = self.dictation_text
        else:
            self.active_text_widget = self.transcript_text

def main() -> None:
    app = MedicalDictationApp()
    app.mainloop()

