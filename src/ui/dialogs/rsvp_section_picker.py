"""
RSVP Section Picker Dialog

Allows users to select which SOAP sections to read before launching the RSVP reader.
Detects sections in the SOAP text and shows checkboxes with word counts.
"""

import tkinter as tk
import ttkbootstrap as ttk
from typing import Optional, List, Tuple

from settings.settings_manager import settings_manager
from utils.structured_logging import get_logger

logger = get_logger(__name__)

# Section headers to detect (lowercase key, display name)
SECTION_HEADERS = [
    ("subjective", "Subjective"),
    ("objective", "Objective"),
    ("assessment", "Assessment"),
    ("differential diagnosis", "Differential Diagnosis"),
    ("plan", "Plan"),
    ("follow up", "Follow Up"),
    ("follow-up", "Follow Up"),
    ("clinical synopsis", "Clinical Synopsis"),
]


class RSVPSectionPicker:
    """Dialog for selecting which SOAP sections to include in RSVP reading."""

    def __init__(self, parent, soap_text: str):
        self.parent = parent
        self.result: Optional[str] = None
        self.soap_text = soap_text

        # Parse sections from text
        self.sections = self._detect_sections(soap_text)

        if not self.sections:
            # No sections detected — pass through full text
            self.result = soap_text
            return

        # Load saved preferences
        rsvp_settings = settings_manager.get("rsvp", {})
        self.remember = rsvp_settings.get("remember_section_selection", False)
        saved_mode = rsvp_settings.get("section_mode", "all")
        saved_selected = set(rsvp_settings.get("selected_sections", []))

        # Build dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Select Sections to Read")
        self.dialog.geometry("420x480")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)

        # Center on screen
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - 420) // 2
        y = (self.dialog.winfo_screenheight() - 480) // 2
        self.dialog.geometry(f"+{x}+{y}")

        self.dialog.deiconify()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        # Variables
        self.read_all_var = tk.BooleanVar(value=(not self.remember or saved_mode == "all"))
        self.remember_var = tk.BooleanVar(value=self.remember)
        self.section_vars: dict[str, tk.BooleanVar] = {}

        self._create_widgets(saved_selected)

        # Apply saved selection state
        if self.remember and saved_mode == "selected":
            self.read_all_var.set(False)
            self._on_read_all_toggle()

        self.dialog.bind('<Escape>', lambda e: self._cancel())
        self.dialog.protocol("WM_DELETE_WINDOW", self._cancel)

        self.dialog.wait_window()

    def _detect_sections(self, text: str) -> List[Tuple[str, str, int]]:
        """Detect SOAP sections in text.

        Returns list of (canonical_name, header_line, word_count) in document order.
        """
        lines = text.split('\n')
        sections: List[Tuple[str, int]] = []  # (canonical_name, start_line_idx)
        seen_names = set()

        for i, line in enumerate(lines):
            stripped = line.strip().lstrip('-').lstrip('\u2022').lstrip('*').strip()
            stripped_lower = stripped.lower()

            for header_key, display_name in SECTION_HEADERS:
                if stripped_lower.startswith(header_key):
                    rest = stripped_lower[len(header_key):]
                    if not rest or rest[0] in (':', ' ', '\t'):
                        if display_name not in seen_names:
                            seen_names.add(display_name)
                            sections.append((display_name, i))
                        break

        if not sections:
            return []

        # Calculate word counts per section
        result = []
        for idx, (name, start) in enumerate(sections):
            if idx + 1 < len(sections):
                end = sections[idx + 1][1]
            else:
                end = len(lines)
            section_text = '\n'.join(lines[start:end])
            word_count = len(section_text.split())
            result.append((name, section_text, word_count))

        return result

    def _create_widgets(self, saved_selected: set):
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(
            main_frame,
            text="Choose Sections to Read",
            font=("Segoe UI", 14, "bold")
        ).pack(pady=(0, 15))

        # Total word count
        total_words = sum(wc for _, _, wc in self.sections)
        ttk.Label(
            main_frame,
            text=f"Total: {total_words} words",
            font=("Segoe UI", 10)
        ).pack(pady=(0, 10))

        # "Read All Sections" checkbox
        read_all_cb = ttk.Checkbutton(
            main_frame,
            text="Read All Sections",
            variable=self.read_all_var,
            command=self._on_read_all_toggle,
            bootstyle="primary"
        )
        read_all_cb.pack(anchor=tk.W, pady=(0, 10))

        ttk.Separator(main_frame).pack(fill=tk.X, pady=5)

        # Section checkboxes
        self.section_frame = ttk.Frame(main_frame)
        self.section_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        for name, _, word_count in self.sections:
            var = tk.BooleanVar(value=(name in saved_selected) if saved_selected else True)
            self.section_vars[name] = var
            cb = ttk.Checkbutton(
                self.section_frame,
                text=f"{name}  (~{word_count} words)",
                variable=var,
                bootstyle="default"
            )
            cb.pack(anchor=tk.W, pady=3, padx=10)

        # Initially disable section checkboxes if "Read All" is checked
        self._on_read_all_toggle()

        ttk.Separator(main_frame).pack(fill=tk.X, pady=5)

        # Remember checkbox
        ttk.Checkbutton(
            main_frame,
            text="Remember my selection",
            variable=self.remember_var,
            bootstyle="secondary"
        ).pack(anchor=tk.W, pady=(5, 10))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(
            btn_frame,
            text="Cancel",
            command=self._cancel,
            width=12,
            bootstyle="secondary"
        ).pack(side=tk.RIGHT, padx=(5, 0))

        ttk.Button(
            btn_frame,
            text="Start Reading",
            command=self._start,
            width=14,
            bootstyle="success"
        ).pack(side=tk.RIGHT)

    def _on_read_all_toggle(self):
        """Enable/disable individual section checkboxes based on 'Read All' state."""
        read_all = self.read_all_var.get()
        state = "disabled" if read_all else "normal"
        for widget in self.section_frame.winfo_children():
            widget.configure(state=state)

    def _start(self):
        """Assemble selected text and close dialog."""
        if self.read_all_var.get():
            self.result = self.soap_text
            mode = "all"
            selected = []
        else:
            selected_sections = []
            selected = []
            for name, text, _ in self.sections:
                if self.section_vars.get(name, tk.BooleanVar(value=False)).get():
                    selected_sections.append(text)
                    selected.append(name)

            if not selected_sections:
                from tkinter import messagebox
                messagebox.showwarning(
                    "No Sections Selected",
                    "Please select at least one section or choose 'Read All Sections'.",
                    parent=self.dialog
                )
                return

            self.result = '\n\n'.join(selected_sections)
            mode = "selected"

        # Save preferences
        self._save_preferences(mode, selected)
        self.dialog.destroy()

    def _cancel(self):
        """Cancel without opening RSVP reader."""
        self.result = None
        self.dialog.destroy()

    def _save_preferences(self, mode: str, selected: list):
        """Persist section selection preferences if 'remember' is checked."""
        rsvp_settings = settings_manager.get("rsvp", {})
        rsvp_settings["remember_section_selection"] = self.remember_var.get()
        if self.remember_var.get():
            rsvp_settings["section_mode"] = mode
            rsvp_settings["selected_sections"] = selected
        else:
            # Clear saved selection when remember is unchecked
            rsvp_settings["section_mode"] = "all"
            rsvp_settings["selected_sections"] = []
        settings_manager.set("rsvp", rsvp_settings)
