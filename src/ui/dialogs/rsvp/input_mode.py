"""
RSVP Input Mode Panel

Handles the input mode UI for the RSVP reader including:
- Text area for pasting text
- PDF file upload with OCR support
- Text file upload (.txt, .md, .rtf)
- Word count display
"""

import tkinter as tk
import ttkbootstrap as ttk
from tkinter import filedialog, messagebox
from typing import Callable, Optional
import threading
import os

from utils.structured_logging import get_logger

from .core import RSVPTheme

logger = get_logger(__name__)


class InputModePanel:
    """Panel for RSVP input mode - text entry and file loading."""

    def __init__(
        self,
        parent_frame: tk.Frame,
        colors: dict,
        on_start_reading: Callable[[str], None],
        on_theme_toggle: Callable[[], None],
        last_directory: str = ""
    ):
        """Initialize the input mode panel.

        Args:
            parent_frame: Parent frame to build UI in
            colors: Color dictionary from RSVPTheme
            on_start_reading: Callback when user clicks "Start Reading"
            on_theme_toggle: Callback for theme toggle button
            last_directory: Last used directory for file dialogs
        """
        self.parent = parent_frame
        self.colors = colors
        self.on_start_reading = on_start_reading
        self.on_theme_toggle = on_theme_toggle
        self.last_directory = last_directory

        self.input_text: Optional[tk.Text] = None
        self.word_count_label: Optional[tk.Label] = None
        self.theme_btn: Optional[ttk.Button] = None
        self._progress_label: Optional[tk.Label] = None

        self._create_ui()

    def _create_ui(self) -> None:
        """Create the input mode UI."""
        # Header
        header_frame = tk.Frame(self.parent, bg=self.colors['control_bg'])
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        title_label = tk.Label(
            header_frame,
            text="RSVP Reader - Load Text",
            font=("Helvetica", 16, "bold"),
            bg=self.colors['control_bg'],
            fg=self.colors['text']
        )
        title_label.pack(side=tk.LEFT, padx=15, pady=10)

        # Theme toggle button
        self.theme_btn = ttk.Button(
            header_frame,
            text="Light",  # Will be updated by parent
            command=self.on_theme_toggle,
            width=6,
            bootstyle="secondary"
        )
        self.theme_btn.pack(side=tk.RIGHT, padx=15, pady=10)

        # Button row
        button_frame = tk.Frame(self.parent, bg=self.colors['bg'])
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
            self.parent,
            text="Paste text below, or use buttons above to load from file:",
            font=("Helvetica", 10),
            bg=self.colors['bg'],
            fg=self.colors['context']
        )
        instructions.pack(anchor=tk.W, padx=25, pady=(10, 5))

        # Text area frame
        text_frame = tk.Frame(self.parent, bg=self.colors['bg'])
        text_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        # Text area with scrollbar
        self.input_text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=("Helvetica", 11),
            bg=self.colors['input_bg'],
            fg=self.colors['text'],
            insertbackground=self.colors['text'],
            relief=tk.FLAT,
            padx=10,
            pady=10
        )

        scrollbar = ttk.Scrollbar(
            text_frame,
            orient=tk.VERTICAL,
            command=self.input_text.yview
        )
        self.input_text.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.input_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Bind text changes to update word count
        self.input_text.bind('<KeyRelease>', self._update_word_count)

        # Word count label
        self.word_count_label = tk.Label(
            self.parent,
            text="Word count: 0",
            font=("Helvetica", 10),
            bg=self.colors['bg'],
            fg=self.colors['context']
        )
        self.word_count_label.pack(anchor=tk.W, padx=25, pady=5)

        # Start Reading button
        button_bottom_frame = tk.Frame(self.parent, bg=self.colors['bg'])
        button_bottom_frame.pack(fill=tk.X, padx=20, pady=15)

        self.start_reading_btn = ttk.Button(
            button_bottom_frame,
            text="Start Reading >>",
            command=self._on_start_reading,
            width=20,
            bootstyle="success"
        )
        self.start_reading_btn.pack(side=tk.RIGHT, padx=5)

        # Focus on text area
        self.input_text.focus_set()

    def _update_word_count(self, event=None) -> None:
        """Update the word count display."""
        text = self.get_text()
        word_count = len(text.split()) if text else 0
        self.word_count_label.config(text=f"Word count: {word_count}")

    def _clear_text(self) -> None:
        """Clear the input text area."""
        self.input_text.delete("1.0", tk.END)
        self._update_word_count()

    def get_text(self) -> str:
        """Get the current text content."""
        return self.input_text.get("1.0", "end-1c").strip()

    def set_text(self, text: str) -> None:
        """Set the text content."""
        self.input_text.delete("1.0", tk.END)
        self.input_text.insert("1.0", text)
        self._update_word_count()

    def _on_start_reading(self) -> None:
        """Handle Start Reading button click."""
        text = self.get_text()
        if not text:
            messagebox.showwarning(
                "No Text",
                "Please enter or load some text first.",
                parent=self.parent
            )
            return
        self.on_start_reading(text)

    def _upload_pdf(self) -> None:
        """Handle PDF file upload."""
        initial_dir = self.last_directory if self.last_directory else None

        file_path = filedialog.askopenfilename(
            parent=self.parent,
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
        self.last_directory = os.path.dirname(file_path)

        # Show progress
        self._show_progress("Extracting text from PDF...")

        def extract_pdf():
            try:
                from processing.pdf_processor import get_pdf_processor

                processor = get_pdf_processor()

                def progress_callback(message: str):
                    self.parent.after(0, lambda: self._show_progress(message))

                text, used_ocr = processor.extract_text(file_path, progress_callback)

                if text.strip():
                    msg = f"PDF loaded {'(via OCR)' if used_ocr else ''}"
                    self.parent.after(0, lambda: self._load_text(text, msg))
                else:
                    self.parent.after(
                        0,
                        lambda: self._show_error("No text could be extracted from the PDF.")
                    )

            except ImportError as e:
                self.parent.after(0, lambda: self._show_error(str(e)))
            except RuntimeError as e:
                self.parent.after(0, lambda: self._show_error(str(e)))
            except Exception as e:
                logger.error(f"PDF extraction error: {e}")
                self.parent.after(0, lambda: self._show_error(f"Failed to extract PDF: {e}"))

        # Run extraction in thread
        thread = threading.Thread(target=extract_pdf, daemon=True)
        thread.start()

    def _upload_text_file(self) -> None:
        """Handle text file upload."""
        initial_dir = self.last_directory if self.last_directory else None

        file_path = filedialog.askopenfilename(
            parent=self.parent,
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
        self.last_directory = os.path.dirname(file_path)

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
        self.set_text(text)

        if message:
            # Show brief status message
            status_label = tk.Label(
                self.parent,
                text=message,
                font=("Helvetica", 10),
                bg=self.colors['bg'],
                fg="#4CAF50"
            )
            status_label.pack(anchor=tk.W, padx=25)
            self.parent.after(3000, status_label.destroy)

    def _show_progress(self, message: str) -> None:
        """Show progress indicator."""
        if self._progress_label and self._progress_label.winfo_exists():
            self._progress_label.config(text=message)
        else:
            self._progress_label = tk.Label(
                self.parent,
                text=message,
                font=("Helvetica", 10),
                bg=self.colors['bg'],
                fg=self.colors['text']
            )
            self._progress_label.pack(anchor=tk.W, padx=25, pady=5)

    def _hide_progress(self) -> None:
        """Hide progress indicator."""
        if self._progress_label and self._progress_label.winfo_exists():
            self._progress_label.destroy()
            self._progress_label = None

    def _show_error(self, message: str) -> None:
        """Show error message."""
        self._hide_progress()
        messagebox.showerror("Error", message, parent=self.parent)

    def update_colors(self, colors: dict) -> None:
        """Update colors for theme change."""
        self.colors = colors
        # Note: Full color update would require recreating widgets
        # For simplicity, theme changes trigger a mode rebuild in the main dialog

    def update_theme_button(self, is_dark: bool) -> None:
        """Update theme button text."""
        if self.theme_btn:
            self.theme_btn.configure(text="Light" if is_dark else "Dark")


__all__ = ['InputModePanel']
