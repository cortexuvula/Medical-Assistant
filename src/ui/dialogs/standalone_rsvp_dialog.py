"""
Standalone RSVP Reader Dialog

A comprehensive RSVP reader that accepts text input via:
- Paste text directly
- Upload PDF files (with OCR fallback for scanned documents)
- Upload text files (.txt, .md, .rtf)

Features:
- Two modes: Input Mode and Reading Mode
- Full RSVP display with ORP (Optimal Recognition Point) highlighting
- Keyboard shortcuts for efficient navigation
- Settings persistence between sessions
- Light/Dark theme support

Code Structure:
- Lines 30-80: Class constants and __init__
- Lines 80-180: Settings management and theme colors
- Lines 180-350: Dialog creation and input mode UI
- Lines 350-500: File handling (PDF, text files)
- Lines 500-700: Reading mode UI (reused from rsvp_dialog.py)
- Lines 700-900: RSVP display methods (ORP calculation, canvas drawing)
- Lines 900-1050: Playback control and navigation
- Lines 1050-1150: Keyboard shortcuts and event handlers
"""

import tkinter as tk
import ttkbootstrap as ttk
from tkinter import filedialog, messagebox
from typing import List, Tuple, Optional, Dict, Callable
import tkinter.font as tkfont
import time
import platform
import logging

from settings.settings import SETTINGS, save_settings

logger = logging.getLogger(__name__)


class StandaloneRSVPDialog:
    """Standalone RSVP reader dialog with input and reading modes."""

    # Speed constants
    MIN_WPM = 50
    MAX_WPM = 2000
    DEFAULT_WPM = 300
    WPM_STEP = 25

    # Font size constants
    MIN_FONT_SIZE = 24
    MAX_FONT_SIZE = 96
    DEFAULT_FONT_SIZE = 48

    # Dark theme colors
    DARK_BG = "#1E1E1E"
    DARK_TEXT = "#FFFFFF"
    DARK_ORP = "#FF6B6B"
    DARK_CONTROL_BG = "#2D2D2D"
    DARK_PROGRESS_BG = "#3D3D3D"
    DARK_CONTEXT_TEXT = "#666666"
    DARK_INPUT_BG = "#252525"

    # Light theme colors
    LIGHT_BG = "#F5F5F5"
    LIGHT_TEXT = "#1E1E1E"
    LIGHT_ORP = "#E53935"
    LIGHT_CONTROL_BG = "#E0E0E0"
    LIGHT_PROGRESS_BG = "#D0D0D0"
    LIGHT_CONTEXT_TEXT = "#999999"
    LIGHT_INPUT_BG = "#FFFFFF"

    def __init__(self, parent):
        """Initialize standalone RSVP dialog.

        Args:
            parent: Parent window
        """
        self.parent = parent
        self.text = ""
        self.words: List[Tuple[str, str]] = []
        self.sentences: List[Tuple[int, int, str]] = []
        self.current_index = 0
        self.is_playing = False
        self.is_fullscreen = False
        self.timer_id: Optional[str] = None
        self.mode = "input"  # "input" or "reading"

        # Load settings with validation
        rsvp_settings = SETTINGS.get("rsvp", {})
        rsvp_reader_settings = SETTINGS.get("rsvp_reader", {})

        # Reading settings from shared "rsvp" key
        self.wpm = self._validate_wpm(rsvp_settings.get("wpm", self.DEFAULT_WPM))
        self.font_size = self._validate_font_size(rsvp_settings.get("font_size", self.DEFAULT_FONT_SIZE))
        self.chunk_size = self._validate_chunk_size(rsvp_settings.get("chunk_size", 1))
        self.is_dark_theme = self._validate_bool(rsvp_settings.get("dark_theme", True), True)
        self.audio_cue_enabled = self._validate_bool(rsvp_settings.get("audio_cue", False), False)
        self.show_context = self._validate_bool(rsvp_settings.get("show_context", False), False)

        # Reader-specific settings
        self.last_directory = rsvp_reader_settings.get("last_directory", "")
        self.auto_start_after_load = self._validate_bool(
            rsvp_reader_settings.get("auto_start_after_load", False), False
        )

        # Statistics tracking
        self.start_time: Optional[float] = None
        self.wpm_history: List[int] = []

        # Set theme colors
        self._update_theme_colors()

        # Create and show dialog
        self._create_dialog()
        self._create_input_mode()

    def _update_theme_colors(self) -> None:
        """Update color variables based on current theme."""
        if self.is_dark_theme:
            self.BG_COLOR = self.DARK_BG
            self.TEXT_COLOR = self.DARK_TEXT
            self.ORP_COLOR = self.DARK_ORP
            self.CONTROL_BG = self.DARK_CONTROL_BG
            self.PROGRESS_BG = self.DARK_PROGRESS_BG
            self.CONTEXT_COLOR = self.DARK_CONTEXT_TEXT
            self.INPUT_BG = self.DARK_INPUT_BG
        else:
            self.BG_COLOR = self.LIGHT_BG
            self.TEXT_COLOR = self.LIGHT_TEXT
            self.ORP_COLOR = self.LIGHT_ORP
            self.CONTROL_BG = self.LIGHT_CONTROL_BG
            self.PROGRESS_BG = self.LIGHT_PROGRESS_BG
            self.CONTEXT_COLOR = self.LIGHT_CONTEXT_TEXT
            self.INPUT_BG = self.LIGHT_INPUT_BG

    def _validate_wpm(self, value) -> int:
        """Validate WPM setting with bounds checking."""
        try:
            wpm = int(value)
            return max(self.MIN_WPM, min(self.MAX_WPM, wpm))
        except (TypeError, ValueError):
            return self.DEFAULT_WPM

    def _validate_font_size(self, value) -> int:
        """Validate font size setting with bounds checking."""
        try:
            size = int(value)
            return max(self.MIN_FONT_SIZE, min(self.MAX_FONT_SIZE, size))
        except (TypeError, ValueError):
            return self.DEFAULT_FONT_SIZE

    def _validate_chunk_size(self, value) -> int:
        """Validate chunk size setting (1, 2, or 3)."""
        try:
            chunk = int(value)
            if chunk in (1, 2, 3):
                return chunk
            return 1
        except (TypeError, ValueError):
            return 1

    def _validate_bool(self, value, default: bool) -> bool:
        """Validate boolean setting."""
        if isinstance(value, bool):
            return value
        return default

    # =========================================================================
    # DIALOG CREATION
    # =========================================================================

    def _create_dialog(self) -> None:
        """Create the main dialog window."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("RSVP Reader")
        self.dialog.geometry("900x700")
        self.dialog.configure(bg=self.BG_COLOR)
        self.dialog.resizable(True, True)
        self.dialog.minsize(700, 500)

        # Center on screen
        self.dialog.update_idletasks()
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        x = (screen_width // 2) - (900 // 2)
        y = (screen_height // 2) - (700 // 2)
        self.dialog.geometry(f"900x700+{x}+{y}")

        # Make modal
        self.dialog.transient(self.parent)
        self.dialog.deiconify()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        # Handle window close
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

        # Main container
        self.main_frame = ttk.Frame(self.dialog)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

    # =========================================================================
    # INPUT MODE
    # =========================================================================

    def _create_input_mode(self) -> None:
        """Create the input mode UI."""
        self.mode = "input"

        # Clear main frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        # Header
        header_frame = tk.Frame(self.main_frame, bg=self.CONTROL_BG)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        title_label = tk.Label(
            header_frame,
            text="RSVP Reader - Load Text",
            font=("Helvetica", 16, "bold"),
            bg=self.CONTROL_BG,
            fg=self.TEXT_COLOR
        )
        title_label.pack(side=tk.LEFT, padx=15, pady=10)

        # Theme toggle button
        theme_btn = ttk.Button(
            header_frame,
            text="Light" if self.is_dark_theme else "Dark",
            command=self._toggle_theme,
            width=6,
            bootstyle="secondary"
        )
        theme_btn.pack(side=tk.RIGHT, padx=15, pady=10)
        self.theme_btn = theme_btn

        # Button row
        button_frame = tk.Frame(self.main_frame, bg=self.BG_COLOR)
        button_frame.pack(fill=tk.X, padx=20, pady=(10, 5))

        ttk.Button(
            button_frame,
            text="Upload PDF",
            command=self._upload_pdf,
            width=15,
            bootstyle="primary"
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="Upload Text File",
            command=self._upload_text_file,
            width=15,
            bootstyle="primary"
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="Clear",
            command=self._clear_text,
            width=10,
            bootstyle="secondary"
        ).pack(side=tk.LEFT, padx=5)

        # Instructions
        instructions = tk.Label(
            self.main_frame,
            text="Paste text below, or use buttons above to load from file:",
            font=("Helvetica", 10),
            bg=self.BG_COLOR,
            fg=self.CONTEXT_COLOR
        )
        instructions.pack(anchor=tk.W, padx=25, pady=(10, 5))

        # Text area frame
        text_frame = tk.Frame(self.main_frame, bg=self.BG_COLOR)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        # Text area with scrollbar
        self.input_text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=("Helvetica", 11),
            bg=self.INPUT_BG,
            fg=self.TEXT_COLOR,
            insertbackground=self.TEXT_COLOR,
            relief=tk.FLAT,
            padx=10,
            pady=10
        )

        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.input_text.yview)
        self.input_text.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.input_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Bind text changes to update word count
        self.input_text.bind('<KeyRelease>', self._update_word_count)

        # Word count label
        self.word_count_label = tk.Label(
            self.main_frame,
            text="Word count: 0",
            font=("Helvetica", 10),
            bg=self.BG_COLOR,
            fg=self.CONTEXT_COLOR
        )
        self.word_count_label.pack(anchor=tk.W, padx=25, pady=5)

        # Start Reading button
        button_bottom_frame = tk.Frame(self.main_frame, bg=self.BG_COLOR)
        button_bottom_frame.pack(fill=tk.X, padx=20, pady=15)

        self.start_reading_btn = ttk.Button(
            button_bottom_frame,
            text="Start Reading >>",
            command=self._start_reading,
            width=20,
            bootstyle="success"
        )
        self.start_reading_btn.pack(side=tk.RIGHT, padx=5)

        # Bind keyboard shortcuts for input mode
        self.dialog.bind('<Escape>', lambda e: self._on_close())
        self.dialog.bind('<Control-Return>', lambda e: self._start_reading())

        # Focus on text area
        self.input_text.focus_set()

    def _update_word_count(self, event=None) -> None:
        """Update the word count display."""
        text = self.input_text.get("1.0", "end-1c").strip()
        word_count = len(text.split()) if text else 0
        self.word_count_label.config(text=f"Word count: {word_count}")

    def _clear_text(self) -> None:
        """Clear the input text area."""
        self.input_text.delete("1.0", tk.END)
        self._update_word_count()

    # =========================================================================
    # FILE HANDLING
    # =========================================================================

    def _upload_pdf(self) -> None:
        """Handle PDF file upload."""
        initial_dir = self.last_directory if self.last_directory else None

        file_path = filedialog.askopenfilename(
            parent=self.dialog,
            title="Select PDF File",
            initialdir=initial_dir,
            filetypes=[
                ("PDF files", "*.pdf"),
                ("All files", "*.*")
            ]
        )

        if not file_path:
            return

        # Save directory for next time
        import os
        self.last_directory = os.path.dirname(file_path)
        self._save_reader_settings()

        # Show progress
        self._show_progress("Extracting text from PDF...")

        def extract_pdf():
            try:
                from processing.pdf_processor import get_pdf_processor

                processor = get_pdf_processor()

                def progress_callback(message: str):
                    self.dialog.after(0, lambda: self._show_progress(message))

                text, used_ocr = processor.extract_text(file_path, progress_callback)

                if text.strip():
                    self.dialog.after(0, lambda: self._load_text(text, f"PDF loaded {'(via OCR)' if used_ocr else ''}"))
                else:
                    self.dialog.after(0, lambda: self._show_error("No text could be extracted from the PDF."))

            except ImportError as e:
                self.dialog.after(0, lambda: self._show_error(str(e)))
            except RuntimeError as e:
                self.dialog.after(0, lambda: self._show_error(str(e)))
            except Exception as e:
                logger.error(f"PDF extraction error: {e}")
                self.dialog.after(0, lambda: self._show_error(f"Failed to extract PDF: {e}"))

        # Run extraction in thread
        import threading
        thread = threading.Thread(target=extract_pdf, daemon=True)
        thread.start()

    def _upload_text_file(self) -> None:
        """Handle text file upload."""
        initial_dir = self.last_directory if self.last_directory else None

        file_path = filedialog.askopenfilename(
            parent=self.dialog,
            title="Select Text File",
            initialdir=initial_dir,
            filetypes=[
                ("Text files", "*.txt"),
                ("Markdown files", "*.md"),
                ("Rich Text Format", "*.rtf"),
                ("All files", "*.*")
            ]
        )

        if not file_path:
            return

        # Save directory for next time
        import os
        self.last_directory = os.path.dirname(file_path)
        self._save_reader_settings()

        try:
            # Try different encodings
            encodings = ['utf-8', 'latin-1', 'cp1252']
            text = None

            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        text = f.read()
                    break
                except UnicodeDecodeError:
                    continue

            if text is None:
                self._show_error("Could not read file - unsupported encoding")
                return

            if text.strip():
                self._load_text(text, f"Loaded: {os.path.basename(file_path)}")
            else:
                self._show_error("The file appears to be empty.")

        except Exception as e:
            logger.error(f"Text file read error: {e}")
            self._show_error(f"Failed to read file: {e}")

    def _load_text(self, text: str, message: str = "") -> None:
        """Load text into the input area."""
        self._hide_progress()
        self.input_text.delete("1.0", tk.END)
        self.input_text.insert("1.0", text)
        self._update_word_count()

        if message:
            # Show brief status message
            status_label = tk.Label(
                self.main_frame,
                text=message,
                font=("Helvetica", 10),
                bg=self.BG_COLOR,
                fg="#4CAF50"
            )
            status_label.pack(anchor=tk.W, padx=25)
            self.dialog.after(3000, status_label.destroy)

    def _show_progress(self, message: str) -> None:
        """Show progress indicator."""
        if hasattr(self, '_progress_label') and self._progress_label.winfo_exists():
            self._progress_label.config(text=message)
        else:
            self._progress_label = tk.Label(
                self.main_frame,
                text=message,
                font=("Helvetica", 10),
                bg=self.BG_COLOR,
                fg=self.TEXT_COLOR
            )
            self._progress_label.pack(anchor=tk.W, padx=25, pady=5)

    def _hide_progress(self) -> None:
        """Hide progress indicator."""
        if hasattr(self, '_progress_label') and self._progress_label.winfo_exists():
            self._progress_label.destroy()

    def _show_error(self, message: str) -> None:
        """Show error message."""
        self._hide_progress()
        messagebox.showerror("Error", message, parent=self.dialog)

    # =========================================================================
    # READING MODE
    # =========================================================================

    def _start_reading(self) -> None:
        """Switch to reading mode with the current text."""
        text = self.input_text.get("1.0", "end-1c").strip()

        if not text:
            messagebox.showwarning(
                "No Text",
                "Please enter or load some text first.",
                parent=self.dialog
            )
            return

        self.text = text
        self._parse_text()

        if not self.words:
            messagebox.showwarning(
                "No Content",
                "No readable text found.",
                parent=self.dialog
            )
            return

        self._create_reading_mode()

    def _parse_text(self) -> None:
        """Parse text into words with punctuation type for smart pausing."""
        raw_words = self.text.split()
        self.words = []
        self.sentences = []

        # Track sentences for context display
        current_sentence_start = 0
        current_sentence_words = []

        for word in raw_words:
            if not word:
                continue

            word_index = len(self.words)

            # Determine punctuation type for timing
            if word[-1:] in '.!?':
                punct_type = 'sentence'
            elif word[-1:] in ',;:':
                punct_type = 'clause'
            else:
                punct_type = 'none'

            self.words.append((word, punct_type))
            current_sentence_words.append(word)

            # Track sentence boundaries
            if punct_type == 'sentence':
                sentence_text = ' '.join(current_sentence_words)
                self.sentences.append((current_sentence_start, word_index, sentence_text))
                current_sentence_start = word_index + 1
                current_sentence_words = []

        # Add final sentence if not terminated
        if current_sentence_words:
            sentence_text = ' '.join(current_sentence_words)
            self.sentences.append((current_sentence_start, len(self.words) - 1, sentence_text))

    def _create_reading_mode(self) -> None:
        """Create the reading mode UI."""
        self.mode = "reading"
        self.current_index = 0
        self.is_playing = False
        self.start_time = None
        self.wpm_history = []

        # Clear main frame
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        # Context display area
        self.context_frame = tk.Frame(self.main_frame, bg=self.BG_COLOR, height=80)
        self.context_frame.pack(fill=tk.X, padx=20, pady=(15, 0))
        self.context_frame.pack_propagate(False)

        self.context_label = tk.Label(
            self.context_frame,
            text="",
            bg=self.BG_COLOR,
            fg=self.CONTEXT_COLOR,
            font=("Helvetica", 10),
            wraplength=820,
            justify=tk.CENTER
        )
        self.context_label.pack(expand=True, fill=tk.BOTH, padx=15, pady=8)

        # Word display area
        self.display_frame = tk.Frame(self.main_frame, bg=self.BG_COLOR, height=250)
        self.display_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        self.display_frame.pack_propagate(False)

        self.canvas = tk.Canvas(
            self.display_frame,
            bg=self.BG_COLOR,
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind('<Configure>', self._on_resize)

        # Control panel
        self._create_control_panel()

        # Progress section
        self._create_progress_section()

        # Back button
        back_frame = tk.Frame(self.main_frame, bg=self.BG_COLOR)
        back_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(
            back_frame,
            text="<< Back to Input",
            command=self._back_to_input,
            width=15,
            bootstyle="secondary"
        ).pack(side=tk.LEFT, padx=10)

        # Bind keyboard shortcuts
        self._bind_reading_keys()

        # Display first word
        self._display_word()
        self._update_progress()

        # Focus dialog for keyboard input
        self.dialog.focus_set()

    def _create_control_panel(self) -> None:
        """Create the control panel for reading mode."""
        self.control_frame = tk.Frame(self.main_frame, bg=self.CONTROL_BG, height=100)
        self.control_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        self.control_frame.pack_propagate(False)

        # Row 1: Play, Speed, Navigation
        row1 = tk.Frame(self.control_frame, bg=self.CONTROL_BG)
        row1.pack(fill=tk.X, pady=(8, 4))
        self.row1 = row1

        row1_inner = tk.Frame(row1, bg=self.CONTROL_BG)
        row1_inner.pack(expand=True)

        # Play/Pause button
        self.play_btn = ttk.Button(
            row1_inner,
            text="Play",
            command=self._toggle_playback,
            width=10,
            bootstyle="success"
        )
        self.play_btn.pack(side=tk.LEFT, padx=8)

        # Speed control
        speed_frame = tk.Frame(row1_inner, bg=self.CONTROL_BG)
        speed_frame.pack(side=tk.LEFT, padx=8)
        self.speed_frame = speed_frame

        ttk.Label(
            speed_frame,
            text="Speed:",
            background=self.CONTROL_BG,
            foreground=self.TEXT_COLOR
        ).pack(side=tk.LEFT, padx=(0, 3))

        ttk.Button(
            speed_frame,
            text="-",
            command=self._speed_down,
            width=2,
            bootstyle="secondary"
        ).pack(side=tk.LEFT)

        self.speed_var = tk.IntVar(value=self.wpm)
        self.speed_slider = ttk.Scale(
            speed_frame,
            from_=self.MIN_WPM,
            to=self.MAX_WPM,
            orient=tk.HORIZONTAL,
            length=100,
            variable=self.speed_var,
            command=self._on_speed_change
        )
        self.speed_slider.pack(side=tk.LEFT, padx=2)

        ttk.Button(
            speed_frame,
            text="+",
            command=self._speed_up,
            width=2,
            bootstyle="secondary"
        ).pack(side=tk.LEFT)

        self.wpm_label = ttk.Label(
            speed_frame,
            text=f"{self.wpm} WPM",
            width=9,
            background=self.CONTROL_BG,
            foreground=self.TEXT_COLOR
        )
        self.wpm_label.pack(side=tk.LEFT, padx=(5, 0))

        # Navigation buttons
        nav_frame = tk.Frame(row1_inner, bg=self.CONTROL_BG)
        nav_frame.pack(side=tk.LEFT, padx=8)
        self.nav_frame = nav_frame

        for symbol, cmd in [("<<", self._go_to_start), ("<", self._prev_word),
                           (">", self._next_word), (">>", self._go_to_end)]:
            ttk.Button(
                nav_frame,
                text=symbol,
                command=cmd,
                width=3,
                bootstyle="secondary"
            ).pack(side=tk.LEFT, padx=1)

        # Row 2: Font, Chunk, Settings
        row2 = tk.Frame(self.control_frame, bg=self.CONTROL_BG)
        row2.pack(fill=tk.X, pady=(4, 8))
        self.row2 = row2

        row2_inner = tk.Frame(row2, bg=self.CONTROL_BG)
        row2_inner.pack(expand=True)

        # Font size control
        font_frame = tk.Frame(row2_inner, bg=self.CONTROL_BG)
        font_frame.pack(side=tk.LEFT, padx=8)
        self.font_frame = font_frame

        ttk.Label(
            font_frame,
            text="Font:",
            background=self.CONTROL_BG,
            foreground=self.TEXT_COLOR
        ).pack(side=tk.LEFT, padx=(0, 3))

        self.font_var = tk.IntVar(value=self.font_size)
        self.font_slider = ttk.Scale(
            font_frame,
            from_=self.MIN_FONT_SIZE,
            to=self.MAX_FONT_SIZE,
            orient=tk.HORIZONTAL,
            length=80,
            variable=self.font_var,
            command=self._on_font_change
        )
        self.font_slider.pack(side=tk.LEFT, padx=2)

        self.font_label = ttk.Label(
            font_frame,
            text=f"{self.font_size}pt",
            width=5,
            background=self.CONTROL_BG,
            foreground=self.TEXT_COLOR
        )
        self.font_label.pack(side=tk.LEFT, padx=(3, 0))

        # Chunk size control
        chunk_frame = tk.Frame(row2_inner, bg=self.CONTROL_BG)
        chunk_frame.pack(side=tk.LEFT, padx=8)
        self.chunk_frame = chunk_frame

        ttk.Label(
            chunk_frame,
            text="Words:",
            background=self.CONTROL_BG,
            foreground=self.TEXT_COLOR
        ).pack(side=tk.LEFT, padx=(0, 3))

        self.chunk_var = tk.IntVar(value=self.chunk_size)
        for i in [1, 2, 3]:
            rb = ttk.Radiobutton(
                chunk_frame,
                text=str(i),
                variable=self.chunk_var,
                value=i,
                command=self._on_chunk_change,
                bootstyle="info-toolbutton"
            )
            rb.pack(side=tk.LEFT, padx=1)

        # Settings buttons
        settings_frame = tk.Frame(row2_inner, bg=self.CONTROL_BG)
        settings_frame.pack(side=tk.LEFT, padx=8)
        self.settings_frame = settings_frame

        # Theme toggle
        self.theme_btn = ttk.Button(
            settings_frame,
            text="Light" if self.is_dark_theme else "Dark",
            command=self._toggle_theme,
            width=6,
            bootstyle="secondary"
        )
        self.theme_btn.pack(side=tk.LEFT, padx=2)

        # Fullscreen toggle
        ttk.Button(
            settings_frame,
            text="F11",
            command=self._toggle_fullscreen,
            width=4,
            bootstyle="secondary"
        ).pack(side=tk.LEFT, padx=2)

        # Context toggle
        self.context_btn = ttk.Button(
            settings_frame,
            text="Ctx*" if self.show_context else "Ctx",
            command=self._toggle_context,
            width=4,
            bootstyle="info" if self.show_context else "secondary"
        )
        self.context_btn.pack(side=tk.LEFT, padx=2)

        # Audio toggle
        self.audio_btn = ttk.Button(
            settings_frame,
            text="Snd*" if self.audio_cue_enabled else "Snd",
            command=self._toggle_audio_cue,
            width=4,
            bootstyle="info" if self.audio_cue_enabled else "secondary"
        )
        self.audio_btn.pack(side=tk.LEFT, padx=2)

        # Help button
        ttk.Button(
            settings_frame,
            text="?",
            command=self._show_shortcuts_help,
            width=2,
            bootstyle="secondary"
        ).pack(side=tk.LEFT, padx=2)

    def _create_progress_section(self) -> None:
        """Create the progress bar and info section."""
        progress_frame = tk.Frame(self.main_frame, bg=self.PROGRESS_BG, height=60)
        progress_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        progress_frame.pack_propagate(False)

        progress_inner = tk.Frame(progress_frame, bg=self.PROGRESS_BG)
        progress_inner.pack(fill=tk.X, padx=15, pady=10)

        # Progress bar
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            progress_inner,
            variable=self.progress_var,
            maximum=100,
            length=500,
            mode='determinate',
            bootstyle="info"
        )
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Info labels
        info_frame = tk.Frame(progress_inner, bg=self.PROGRESS_BG)
        info_frame.pack(side=tk.RIGHT, padx=(15, 0))

        self.word_count_display = tk.Label(
            info_frame,
            text=f"0 / {len(self.words)} words",
            bg=self.PROGRESS_BG,
            fg=self.TEXT_COLOR
        )
        self.word_count_display.pack(anchor=tk.E)

        self.time_label = tk.Label(
            info_frame,
            text="",
            bg=self.PROGRESS_BG,
            fg=self.TEXT_COLOR
        )
        self.time_label.pack(anchor=tk.E)

    def _bind_reading_keys(self) -> None:
        """Bind keyboard shortcuts for reading mode."""
        self.dialog.bind('<space>', lambda e: self._toggle_playback())
        self.dialog.bind('<Up>', lambda e: self._speed_up())
        self.dialog.bind('<Down>', lambda e: self._speed_down())
        self.dialog.bind('<Left>', lambda e: self._prev_word())
        self.dialog.bind('<Right>', lambda e: self._next_word())
        self.dialog.bind('<Home>', lambda e: self._go_to_start())
        self.dialog.bind('<End>', lambda e: self._go_to_end())
        self.dialog.bind('<Escape>', lambda e: self._handle_escape())
        self.dialog.bind('<F11>', lambda e: self._toggle_fullscreen())
        self.dialog.bind('<t>', lambda e: self._toggle_theme())
        self.dialog.bind('<T>', lambda e: self._toggle_theme())
        self.dialog.bind('<Key-1>', lambda e: self._set_chunk_size(1))
        self.dialog.bind('<Key-2>', lambda e: self._set_chunk_size(2))
        self.dialog.bind('<Key-3>', lambda e: self._set_chunk_size(3))

    def _back_to_input(self) -> None:
        """Switch back to input mode."""
        self.pause()
        self._create_input_mode()
        # Restore the text
        self.input_text.insert("1.0", self.text)
        self._update_word_count()

    # =========================================================================
    # WORD DISPLAY (ORP)
    # =========================================================================

    def _calculate_orp(self, word: str) -> int:
        """Calculate optimal recognition point index."""
        clean_word = word.rstrip('.,;:!?"\'-')
        length = len(clean_word)

        if length <= 1:
            return 0
        if length <= 3:
            return 0
        if length <= 5:
            return 1
        if length <= 9:
            return 2
        return 3

    def _display_word(self) -> None:
        """Display current word(s) with ORP highlighting."""
        self.canvas.delete("all")

        if self.current_index >= len(self.words):
            self._show_complete()
            return

        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if canvas_width < 10 or canvas_height < 10:
            self.dialog.after(50, self._display_word)
            return

        # Get chunk of words
        end_idx = min(self.current_index + self.chunk_size, len(self.words))
        chunk_words = [w[0] for w in self.words[self.current_index:end_idx]]

        if self.chunk_size == 1:
            self._display_single_word(chunk_words[0], canvas_width, canvas_height)
        else:
            self._display_chunk(chunk_words, canvas_width, canvas_height)

        self._update_context_display()

    def _display_single_word(self, word: str, canvas_width: int, canvas_height: int) -> None:
        """Display a single word with ORP highlighting."""
        orp_pos = self._calculate_orp(word)
        font = tkfont.Font(family="Helvetica", size=self.font_size, weight="bold")

        pre = word[:orp_pos]
        orp_char = word[orp_pos] if orp_pos < len(word) else ''
        post = word[orp_pos + 1:] if orp_pos + 1 < len(word) else ''

        orp_width = font.measure(orp_char)
        center_x = canvas_width // 2
        center_y = canvas_height // 2

        # Draw vertical ORP indicator line
        self.canvas.create_line(
            center_x, 10, center_x, canvas_height - 10,
            fill=self.ORP_COLOR, width=2, dash=(4, 4)
        )

        # Draw triangle marker
        self.canvas.create_polygon(
            center_x - 8, 5,
            center_x + 8, 5,
            center_x, 15,
            fill=self.ORP_COLOR
        )

        orp_left_edge = center_x - (orp_width // 2)
        orp_right_edge = center_x + (orp_width // 2)

        # Draw pre-ORP text
        if pre:
            self.canvas.create_text(
                orp_left_edge, center_y,
                text=pre, font=font, fill=self.TEXT_COLOR, anchor=tk.E
            )

        # Draw ORP character (highlighted)
        if orp_char:
            self.canvas.create_text(
                center_x, center_y,
                text=orp_char, font=font, fill=self.ORP_COLOR, anchor=tk.CENTER
            )

        # Draw post-ORP text
        if post:
            self.canvas.create_text(
                orp_right_edge, center_y,
                text=post, font=font, fill=self.TEXT_COLOR, anchor=tk.W
            )

    def _display_chunk(self, words: List[str], canvas_width: int, canvas_height: int) -> None:
        """Display multiple words with ORP on focus word."""
        font_size = max(self.MIN_FONT_SIZE, self.font_size - 8)
        font = tkfont.Font(family="Helvetica", size=font_size, weight="bold")

        center_x = canvas_width // 2
        center_y = canvas_height // 2

        focus_idx = len(words) // 2
        focus_word = words[focus_idx]
        orp_pos = self._calculate_orp(focus_word)

        spacing = "  "
        word_widths = [font.measure(w) for w in words]
        spacing_width = font.measure(spacing)

        focus_word_start = sum(word_widths[:focus_idx]) + spacing_width * focus_idx
        pre_orp = focus_word[:orp_pos]
        orp_char = focus_word[orp_pos] if orp_pos < len(focus_word) else ''
        orp_char_width = font.measure(orp_char)
        pre_orp_width = font.measure(pre_orp)
        orp_center_in_chunk = focus_word_start + pre_orp_width + orp_char_width // 2
        start_x = center_x - orp_center_in_chunk

        # Draw ORP indicator
        self.canvas.create_line(
            center_x, 10, center_x, canvas_height - 10,
            fill=self.ORP_COLOR, width=2, dash=(4, 4)
        )
        self.canvas.create_polygon(
            center_x - 8, 5,
            center_x + 8, 5,
            center_x, 15,
            fill=self.ORP_COLOR
        )

        current_x = start_x
        for i, word in enumerate(words):
            if i == focus_idx:
                pre = word[:orp_pos]
                orp = word[orp_pos] if orp_pos < len(word) else ''
                post = word[orp_pos + 1:] if orp_pos + 1 < len(word) else ''

                if pre:
                    self.canvas.create_text(current_x, center_y, text=pre, font=font, fill=self.TEXT_COLOR, anchor=tk.W)
                    current_x += font.measure(pre)
                if orp:
                    self.canvas.create_text(current_x, center_y, text=orp, font=font, fill=self.ORP_COLOR, anchor=tk.W)
                    current_x += font.measure(orp)
                if post:
                    self.canvas.create_text(current_x, center_y, text=post, font=font, fill=self.TEXT_COLOR, anchor=tk.W)
                    current_x += font.measure(post)
            else:
                self.canvas.create_text(current_x, center_y, text=word, font=font, fill=self.TEXT_COLOR, anchor=tk.W)
                current_x += word_widths[i]

            if i < len(words) - 1:
                current_x += spacing_width

    def _update_context_display(self) -> None:
        """Update the sentence context display."""
        if not self.show_context:
            self.context_label.config(text="")
            return

        sentence = self._get_current_sentence()
        max_length = 200
        if len(sentence) > max_length:
            words_before = self.current_index - self._get_sentence_start_index()
            approx_char_pos = words_before * 6
            half_window = max_length // 2
            start = max(0, approx_char_pos - half_window)
            end = min(len(sentence), start + max_length)
            if end == len(sentence):
                start = max(0, end - max_length)
            truncated = sentence[start:end]
            if start > 0:
                truncated = "..." + truncated.lstrip()
            if end < len(sentence):
                truncated = truncated.rstrip() + "..."
            sentence = truncated

        self.context_label.config(text=sentence)

    def _get_sentence_start_index(self) -> int:
        """Get word index where current sentence starts."""
        for start, end, _ in self.sentences:
            if start <= self.current_index <= end:
                return start
        return 0

    def _get_current_sentence(self) -> str:
        """Get the sentence containing the current word."""
        for start, end, text in self.sentences:
            if start <= self.current_index <= end:
                return text
        return ""

    def _show_complete(self) -> None:
        """Show completion message with statistics."""
        self.canvas.delete("all")
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        font = tkfont.Font(family="Helvetica", size=36, weight="bold")
        small_font = tkfont.Font(family="Helvetica", size=14)

        self.canvas.create_text(
            canvas_width // 2, canvas_height // 2 - 40,
            text="Complete!",
            font=font, fill=self.TEXT_COLOR
        )

        if self.start_time and self.wpm_history:
            elapsed = time.time() - self.start_time
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            avg_wpm = sum(self.wpm_history) // len(self.wpm_history)
            stats_text = f"Time: {minutes}:{seconds:02d} | Avg: {avg_wpm} WPM | {len(self.words)} words"
            self.canvas.create_text(
                canvas_width // 2, canvas_height // 2 + 10,
                text=stats_text, font=small_font, fill="#888888"
            )

        self.canvas.create_text(
            canvas_width // 2, canvas_height // 2 + 50,
            text="Press Home to restart or Escape to go back",
            font=small_font, fill="#666666"
        )

    # =========================================================================
    # PLAYBACK CONTROL
    # =========================================================================

    def _update_progress(self) -> None:
        """Update progress bar and info labels."""
        total = len(self.words)
        current = min(self.current_index + 1, total) if total > 0 else 0

        progress = (current / total) * 100 if total > 0 else 0
        self.progress_var.set(progress)
        self.word_count_display.config(text=f"{current} / {total} words")

        words_remaining = max(0, total - current)
        seconds_remaining = (words_remaining * 60) / self.wpm if self.wpm > 0 else 0

        if seconds_remaining < 60:
            time_str = f"~{int(seconds_remaining)} sec remaining"
        else:
            minutes = int(seconds_remaining // 60)
            seconds = int(seconds_remaining % 60)
            time_str = f"~{minutes}:{seconds:02d} remaining"

        self.time_label.config(text=time_str)

    def _get_delay_ms(self) -> int:
        """Calculate delay for current word based on WPM and punctuation."""
        if self.current_index >= len(self.words):
            return 200

        base_delay = int(60000 / self.wpm)
        _, punct_type = self.words[self.current_index]

        multipliers = {
            'sentence': 2.5,
            'clause': 1.5,
            'none': 1.0
        }

        return int(base_delay * multipliers.get(punct_type, 1.0))

    def _toggle_playback(self) -> None:
        """Toggle between play and pause."""
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def play(self) -> None:
        """Start or resume playback."""
        if self.current_index >= len(self.words):
            self.current_index = 0
            self._display_word()
            self._update_progress()

        if self.start_time is None:
            self.start_time = time.time()
            self.wpm_history = []

        self.is_playing = True
        self.play_btn.configure(text="Pause", bootstyle="warning")
        self._schedule_next_word()

    def pause(self) -> None:
        """Pause playback."""
        self.is_playing = False

        # Only update play button if it exists (reading mode) and dialog is valid
        if hasattr(self, 'play_btn') and self.play_btn:
            try:
                self.play_btn.configure(text="Play", bootstyle="success")
            except tk.TclError:
                pass  # Widget may have been destroyed

        if self.timer_id:
            try:
                self.dialog.after_cancel(self.timer_id)
            except tk.TclError:
                pass  # Dialog may have been destroyed
            self.timer_id = None

    def _schedule_next_word(self) -> None:
        """Schedule the next word display."""
        if not self.is_playing:
            return
        self.wpm_history.append(self.wpm)
        delay = self._get_delay_ms()
        self.timer_id = self.dialog.after(delay, self._advance_word)

    def _advance_word(self) -> None:
        """Move to next word(s)."""
        self.current_index += self.chunk_size

        if self.current_index >= len(self.words):
            self.pause()
            self._show_complete()
            self._update_progress()
            return

        self._display_word()
        self._update_progress()
        self._schedule_next_word()

    def _prev_word(self) -> None:
        """Go to previous word(s)."""
        if self.current_index > 0:
            self.current_index = max(0, self.current_index - self.chunk_size)
            self._display_word()
            self._update_progress()

    def _next_word(self) -> None:
        """Go to next word(s)."""
        if self.current_index < len(self.words) - 1:
            self.current_index = min(len(self.words) - 1, self.current_index + self.chunk_size)
            self._display_word()
            self._update_progress()

    def _go_to_start(self) -> None:
        """Go to the first word."""
        self.current_index = 0
        self.start_time = None
        self.wpm_history = []
        self._display_word()
        self._update_progress()

    def _go_to_end(self) -> None:
        """Go to the last word."""
        self.current_index = len(self.words) - 1
        self._display_word()
        self._update_progress()

    # =========================================================================
    # SETTINGS CONTROLS
    # =========================================================================

    def _speed_up(self) -> None:
        """Increase reading speed."""
        new_wpm = min(self.wpm + self.WPM_STEP, self.MAX_WPM)
        self._set_speed(new_wpm)

    def _speed_down(self) -> None:
        """Decrease reading speed."""
        new_wpm = max(self.wpm - self.WPM_STEP, self.MIN_WPM)
        self._set_speed(new_wpm)

    def _set_speed(self, wpm: int) -> None:
        """Set the reading speed."""
        self.wpm = wpm
        self.speed_var.set(wpm)
        self.wpm_label.config(text=f"{wpm} WPM")
        self._update_progress()
        self._save_rsvp_settings()

    def _on_speed_change(self, value: str) -> None:
        """Handle speed slider change."""
        try:
            wpm = int(float(value))
            wpm = round(wpm / self.WPM_STEP) * self.WPM_STEP
            wpm = max(self.MIN_WPM, min(self.MAX_WPM, wpm))
            self.wpm = wpm
            self.wpm_label.config(text=f"{wpm} WPM")
            self._update_progress()
            self._save_rsvp_settings()
        except ValueError:
            pass

    def _on_font_change(self, value: str) -> None:
        """Handle font size slider change."""
        try:
            size = int(float(value))
            self.font_size = max(self.MIN_FONT_SIZE, min(self.MAX_FONT_SIZE, size))
            self.font_label.config(text=f"{self.font_size}pt")
            if self.mode == "reading":
                self._display_word()
            self._save_rsvp_settings()
        except ValueError:
            pass

    def _on_chunk_change(self) -> None:
        """Handle chunk size change."""
        self.chunk_size = self.chunk_var.get()
        if self.mode == "reading":
            self._display_word()
        self._save_rsvp_settings()

    def _set_chunk_size(self, size: int) -> None:
        """Set chunk size from keyboard shortcut."""
        self.chunk_size = size
        self.chunk_var.set(size)
        if self.mode == "reading":
            self._display_word()
        self._save_rsvp_settings()

    def _toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode."""
        self.is_fullscreen = not self.is_fullscreen
        self.dialog.attributes('-fullscreen', self.is_fullscreen)

    def _toggle_theme(self) -> None:
        """Toggle between light and dark themes."""
        self.is_dark_theme = not self.is_dark_theme
        self._update_theme_colors()

        # Update UI elements
        self.dialog.configure(bg=self.BG_COLOR)

        if self.mode == "reading":
            self.canvas.configure(bg=self.BG_COLOR)
            self.display_frame.configure(bg=self.BG_COLOR)
            self.context_frame.configure(bg=self.BG_COLOR)
            self.context_label.configure(bg=self.BG_COLOR, fg=self.CONTEXT_COLOR)
            self.word_count_display.configure(bg=self.PROGRESS_BG, fg=self.TEXT_COLOR)
            self.time_label.configure(bg=self.PROGRESS_BG, fg=self.TEXT_COLOR)
            self.control_frame.configure(bg=self.CONTROL_BG)
            self.row1.configure(bg=self.CONTROL_BG)
            self.row2.configure(bg=self.CONTROL_BG)
            self.speed_frame.configure(bg=self.CONTROL_BG)
            self.nav_frame.configure(bg=self.CONTROL_BG)
            self.font_frame.configure(bg=self.CONTROL_BG)
            self.chunk_frame.configure(bg=self.CONTROL_BG)
            self.settings_frame.configure(bg=self.CONTROL_BG)

            for child in self.row1.winfo_children():
                if isinstance(child, tk.Frame):
                    child.configure(bg=self.CONTROL_BG)
            for child in self.row2.winfo_children():
                if isinstance(child, tk.Frame):
                    child.configure(bg=self.CONTROL_BG)

            self._display_word()

        self.theme_btn.configure(text="Light" if self.is_dark_theme else "Dark")
        self._save_rsvp_settings()

    def _toggle_context(self) -> None:
        """Toggle sentence context display."""
        self.show_context = not self.show_context
        self.context_btn.configure(
            text="Ctx*" if self.show_context else "Ctx",
            bootstyle="info" if self.show_context else "secondary"
        )
        if self.mode == "reading":
            self._update_context_display()
        self._save_rsvp_settings()

    def _toggle_audio_cue(self) -> None:
        """Toggle audio cue."""
        self.audio_cue_enabled = not self.audio_cue_enabled
        self.audio_btn.configure(
            text="Snd*" if self.audio_cue_enabled else "Snd",
            bootstyle="info" if self.audio_cue_enabled else "secondary"
        )
        self._save_rsvp_settings()

    def _show_shortcuts_help(self) -> None:
        """Show keyboard shortcuts help."""
        help_text = """RSVP Reader Keyboard Shortcuts

PLAYBACK
  Space          Play / Pause
  Up / Down      Increase / Decrease speed
  Left / Right   Previous / Next word
  Home / End     Jump to start / end

DISPLAY
  F11            Toggle fullscreen
  T              Toggle light/dark theme
  1 / 2 / 3      Set chunk size (words at once)

NAVIGATION
  Escape         Exit fullscreen (or go back)
  Ctrl+Enter     Start reading (input mode)

SETTINGS BUTTONS
  Light/Dark     Toggle theme
  F11            Fullscreen mode
  Ctx            Show sentence context
  Snd            Audio cue on sections"""

        help_popup = tk.Toplevel(self.dialog)
        help_popup.title("Keyboard Shortcuts")
        help_popup.geometry("380x420")
        help_popup.resizable(False, False)
        help_popup.transient(self.dialog)

        help_popup.update_idletasks()
        x = self.dialog.winfo_x() + (self.dialog.winfo_width() - 380) // 2
        y = self.dialog.winfo_y() + (self.dialog.winfo_height() - 420) // 2
        help_popup.geometry(f"+{x}+{y}")

        help_popup.configure(bg=self.BG_COLOR)

        text_widget = tk.Text(
            help_popup,
            wrap=tk.WORD,
            bg=self.BG_COLOR,
            fg=self.TEXT_COLOR,
            font=("Consolas", 10),
            relief=tk.FLAT,
            padx=15,
            pady=15,
            highlightthickness=0
        )
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))
        text_widget.insert("1.0", help_text)
        text_widget.config(state=tk.DISABLED)

        ttk.Button(
            help_popup,
            text="Close",
            command=help_popup.destroy,
            bootstyle="secondary"
        ).pack(pady=(5, 15))

        help_popup.bind('<Escape>', lambda e: help_popup.destroy())
        help_popup.focus_set()

    # =========================================================================
    # SETTINGS PERSISTENCE
    # =========================================================================

    def _save_rsvp_settings(self) -> None:
        """Save RSVP display settings."""
        if "rsvp" not in SETTINGS:
            SETTINGS["rsvp"] = {}

        SETTINGS["rsvp"]["wpm"] = self.wpm
        SETTINGS["rsvp"]["font_size"] = self.font_size
        SETTINGS["rsvp"]["chunk_size"] = self.chunk_size
        SETTINGS["rsvp"]["dark_theme"] = self.is_dark_theme
        SETTINGS["rsvp"]["audio_cue"] = self.audio_cue_enabled
        SETTINGS["rsvp"]["show_context"] = self.show_context

        save_settings(SETTINGS)

    def _save_reader_settings(self) -> None:
        """Save reader-specific settings."""
        if "rsvp_reader" not in SETTINGS:
            SETTINGS["rsvp_reader"] = {}

        SETTINGS["rsvp_reader"]["last_directory"] = self.last_directory
        SETTINGS["rsvp_reader"]["auto_start_after_load"] = self.auto_start_after_load

        save_settings(SETTINGS)

    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================

    def _handle_escape(self) -> None:
        """Handle Escape key."""
        if self.is_fullscreen:
            self._toggle_fullscreen()
        elif self.mode == "reading":
            self._back_to_input()
        else:
            self._on_close()

    def _on_resize(self, event) -> None:
        """Handle canvas resize."""
        if hasattr(self, 'canvas') and self.words and self.mode == "reading":
            self._display_word()

    def _on_close(self) -> None:
        """Handle dialog close."""
        self.pause()
        try:
            self.dialog.destroy()
        except tk.TclError:
            pass  # Dialog may already be destroyed


__all__ = ["StandaloneRSVPDialog"]
