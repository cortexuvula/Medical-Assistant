"""
Clinical Guidelines Upload Dialog.

Provides a multi-file upload interface for clinical guidelines with:
- File selection (PDF, DOCX, TXT)
- Specialty and source metadata
- Version and effective date
- Guideline type selection
- Progress tracking

Architecture Note:
    This uploads to the SEPARATE guidelines database, NOT the main RAG system.
"""

import os
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable, Optional, Dict

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import DatePickerDialog

from rag.guidelines_models import (
    GuidelineSpecialty,
    GuidelineSource,
    GuidelineType,
    GuidelineUploadStatus,
)


# Supported file types for guidelines
SUPPORTED_EXTENSIONS = [
    ("All Supported", "*.pdf *.docx *.doc *.txt *.md"),
    ("PDF Files", "*.pdf"),
    ("Word Documents", "*.docx *.doc"),
    ("Text Files", "*.txt *.md"),
    ("All Files", "*.*"),
]

# Large batch warning threshold (warn at old hard limit)
LARGE_BATCH_WARNING_THRESHOLD = 100


class GuidelinesUploadDialog(tk.Toplevel):
    """Dialog for uploading clinical guidelines to the guidelines system."""

    def __init__(
        self,
        parent: tk.Widget,
        on_upload: Optional[Callable[[list[str], dict], None]] = None,
    ):
        """Initialize the upload dialog.

        Args:
            parent: Parent widget
            on_upload: Callback when upload starts (files, options)
        """
        super().__init__(parent)
        self.title("Upload Clinical Guidelines")
        self.geometry("750x700")
        self.minsize(650, 600)

        self.on_upload = on_upload
        self.selected_files: list[str] = []
        self.is_uploading = False
        self.effective_date: Optional[date] = None
        self.expiration_date: Optional[date] = None

        self._create_widgets()
        self._center_window()

        # Non-modal - allow user to interact with main app
        self.transient(parent)
        # REMOVED: self.grab_set()  # Don't grab focus - keep UI responsive

    def _center_window(self):
        """Center the dialog on screen."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        """Create dialog widgets."""
        # Main container with padding
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(
            main_frame,
            text="Upload Clinical Guidelines",
            font=("TkDefaultFont", 14, "bold"),
        )
        title_label.pack(anchor=tk.W)

        description = ttk.Label(
            main_frame,
            text="Add clinical guidelines to your separate guidelines database. "
                 "These will be used for compliance checking against SOAP notes. "
                 "Supported formats: PDF, DOCX, TXT.",
            wraplength=700,
        )
        description.pack(anchor=tk.W, pady=(5, 15))

        # File selection area
        file_frame = ttk.Labelframe(main_frame, text="Selected Files", padding=10)
        file_frame.pack(fill=tk.BOTH, expand=True)

        # File listbox with scrollbar
        list_frame = ttk.Frame(file_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.file_listbox = tk.Listbox(
            list_frame,
            height=8,
            selectmode=tk.EXTENDED,
            font=("TkDefaultFont", 10),
        )
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.file_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.file_listbox.yview)

        # File buttons
        btn_frame = ttk.Frame(file_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(
            btn_frame,
            text="Add Files...",
            command=self._add_files,
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            btn_frame,
            text="Add Folder...",
            command=self._add_folder,
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            btn_frame,
            text="Remove Selected",
            command=self._remove_selected,
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            btn_frame,
            text="Clear All",
            command=self._clear_files,
        ).pack(side=tk.LEFT)

        self.file_count_label = ttk.Label(btn_frame, text="0 files selected")
        self.file_count_label.pack(side=tk.RIGHT)

        # Guideline Information frame
        info_frame = ttk.Labelframe(main_frame, text="Guideline Information", padding=10)
        info_frame.pack(fill=tk.X, pady=(15, 0))

        # Row 1: Specialty and Source
        row1 = ttk.Frame(info_frame)
        row1.pack(fill=tk.X, pady=(0, 10))

        # Specialty dropdown
        ttk.Label(row1, text="Specialty:").pack(side=tk.LEFT)
        self.specialty_var = tk.StringVar()
        specialty_values = [""] + [s.value for s in GuidelineSpecialty]
        specialty_combo = ttk.Combobox(
            row1,
            textvariable=self.specialty_var,
            values=specialty_values,
            state="readonly",
            width=25,
        )
        specialty_combo.pack(side=tk.LEFT, padx=(10, 30))

        # Source dropdown
        ttk.Label(row1, text="Source:").pack(side=tk.LEFT)
        self.source_var = tk.StringVar()
        source_values = [""] + [s.value for s in GuidelineSource]
        source_combo = ttk.Combobox(
            row1,
            textvariable=self.source_var,
            values=source_values,
            state="readonly",
            width=20,
        )
        source_combo.pack(side=tk.LEFT, padx=(10, 0))

        # Advanced options toggle (Fix 10)
        self._advanced_visible = tk.BooleanVar(value=False)
        advanced_toggle = ttk.Checkbutton(
            info_frame,
            text="Show Advanced Options",
            variable=self._advanced_visible,
            command=self._toggle_advanced_options,
        )
        advanced_toggle.pack(fill=tk.X, padx=5, pady=(10, 0))

        # Advanced options frame (initially hidden)
        self._advanced_frame = ttk.LabelFrame(info_frame, text="Advanced Options", padx=5, pady=5)

        # Row 2: Version and Effective Date
        row2 = ttk.Frame(self._advanced_frame)
        row2.pack(fill=tk.X, pady=(0, 10))

        # Version entry
        ttk.Label(row2, text="Version:").pack(side=tk.LEFT)
        self.version_var = tk.StringVar()
        version_entry = ttk.Entry(
            row2,
            textvariable=self.version_var,
            width=15,
        )
        version_entry.pack(side=tk.LEFT, padx=(10, 30))
        ttk.Label(
            row2,
            text="(e.g., 2024)",
            foreground="gray",
        ).pack(side=tk.LEFT, padx=(0, 30))

        # Effective date
        ttk.Label(row2, text="Effective Date:").pack(side=tk.LEFT)
        self.date_var = tk.StringVar()
        self.date_entry = ttk.Entry(
            row2,
            textvariable=self.date_var,
            width=12,
            state="readonly",
        )
        self.date_entry.pack(side=tk.LEFT, padx=(10, 5))

        ttk.Button(
            row2,
            text="...",
            command=self._pick_date,
            width=3,
        ).pack(side=tk.LEFT)

        ttk.Button(
            row2,
            text="Clear",
            command=self._clear_date,
            width=5,
        ).pack(side=tk.LEFT, padx=(5, 0))

        # Row 2b: Expiration Date (Issue 14)
        row2b = ttk.Frame(self._advanced_frame)
        row2b.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(row2b, text="Expiration Date:").pack(side=tk.LEFT)
        self.expiration_date_var = tk.StringVar()
        self.expiration_date_entry = ttk.Entry(
            row2b,
            textvariable=self.expiration_date_var,
            width=12,
            state="readonly",
        )
        self.expiration_date_entry.pack(side=tk.LEFT, padx=(10, 5))

        ttk.Button(
            row2b,
            text="...",
            command=self._pick_expiration_date,
            width=3,
        ).pack(side=tk.LEFT)

        ttk.Button(
            row2b,
            text="Clear",
            command=self._clear_expiration_date,
            width=5,
        ).pack(side=tk.LEFT, padx=(5, 0))

        ttk.Label(
            row2b,
            text="(optional - expired guidelines excluded from search)",
            foreground="gray",
        ).pack(side=tk.LEFT, padx=(10, 0))

        # Row 3: Guideline Type
        row3 = ttk.Frame(self._advanced_frame)
        row3.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(row3, text="Guideline Type:").pack(side=tk.LEFT)
        self.type_var = tk.StringVar()
        type_values = [""] + [t.value for t in GuidelineType]
        type_combo = ttk.Combobox(
            row3,
            textvariable=self.type_var,
            values=type_values,
            state="readonly",
            width=30,
        )
        type_combo.pack(side=tk.LEFT, padx=(10, 0))

        # Row 4: Custom Title (optional)
        row4 = ttk.Frame(self._advanced_frame)
        row4.pack(fill=tk.X)

        ttk.Label(row4, text="Title (optional):").pack(side=tk.LEFT)
        self.title_var = tk.StringVar()
        title_entry = ttk.Entry(
            row4,
            textvariable=self.title_var,
            width=50,
        )
        title_entry.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)

        # Processing Options frame
        options_frame = ttk.Labelframe(main_frame, text="Processing Options", padding=10)
        options_frame.pack(fill=tk.X, pady=(15, 0))

        # Checkboxes row
        check_frame = ttk.Frame(options_frame)
        check_frame.pack(fill=tk.X)

        self.extract_recommendations_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            check_frame,
            text="Extract recommendations with evidence levels",
            variable=self.extract_recommendations_var,
        ).pack(side=tk.LEFT, padx=(0, 20))

        self.graph_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            check_frame,
            text="Build knowledge graph relationships",
            variable=self.graph_var,
        ).pack(side=tk.LEFT)

        # OCR checkbox
        check_frame2 = ttk.Frame(options_frame)
        check_frame2.pack(fill=tk.X, pady=(10, 0))

        self.ocr_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            check_frame2,
            text="Enable OCR for scanned documents",
            variable=self.ocr_var,
        ).pack(side=tk.LEFT)

        # Duplicate handling checkbox
        check_frame3 = ttk.Frame(options_frame)
        check_frame3.pack(fill=tk.X, pady=(10, 0))

        self.skip_duplicates_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            check_frame3,
            text="Skip duplicate guidelines (same title/source/version)",
            variable=self.skip_duplicates_var,
        ).pack(side=tk.LEFT)

        # Progress section (initially hidden)
        self.progress_frame = ttk.Labelframe(main_frame, text="Upload Progress", padding=10)

        self.progress_label = ttk.Label(self.progress_frame, text="Ready")
        self.progress_label.pack(fill=tk.X)

        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            mode="determinate",
            length=400,
        )
        self.progress_bar.pack(fill=tk.X, pady=(5, 0))

        self.current_file_label = ttk.Label(
            self.progress_frame,
            text="",
            foreground="gray",
        )
        self.current_file_label.pack(fill=tk.X, pady=(5, 0))

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(15, 0))

        self.cancel_button = ttk.Button(
            button_frame,
            text="Cancel",
            command=self._on_cancel,
            bootstyle="secondary",
        )
        self.cancel_button.pack(side=tk.RIGHT, padx=(10, 0))

        self.upload_button = ttk.Button(
            button_frame,
            text="Upload Guideline",
            command=self._start_upload,
            bootstyle="success",
            state=tk.DISABLED,
        )
        self.upload_button.pack(side=tk.RIGHT)

        # Set up drag-and-drop file support (Fix 18)
        self._setup_drag_and_drop()

    def _add_files(self):
        """Open file dialog to add files."""
        files = filedialog.askopenfilenames(
            parent=self,
            title="Select Clinical Guidelines",
            filetypes=SUPPORTED_EXTENSIONS,
        )

        self._add_files_to_list(list(files))

    def _add_files_to_list(self, file_paths: list):
        """Add file paths to the selected files list, skipping duplicates.

        Args:
            file_paths: List of absolute file paths to add
        """
        for file_path in file_paths:
            if file_path and file_path not in self.selected_files:
                self.selected_files.append(file_path)

        self._update_file_list()

    def _add_folder(self):
        """Add all supported files from a folder."""
        folder = filedialog.askdirectory(
            parent=self,
            title="Select Folder",
        )

        if not folder:
            return

        # Get supported extensions
        extensions = {".pdf", ".docx", ".doc", ".txt", ".md"}

        # Walk folder and add files
        added = 0
        for root, _, files in os.walk(folder):
            for filename in files:
                ext = Path(filename).suffix.lower()
                if ext in extensions:
                    file_path = os.path.join(root, filename)
                    if file_path not in self.selected_files:
                        self.selected_files.append(file_path)
                        added += 1

        self._update_file_list()

        if added > 0:
            messagebox.showinfo(
                "Files Added",
                f"Added {added} files from folder.",
                parent=self,
            )

    def _remove_selected(self):
        """Remove selected files from list."""
        selection = self.file_listbox.curselection()
        if not selection:
            return

        for idx in reversed(selection):
            self.selected_files.pop(idx)

        self._update_file_list()

    def _clear_files(self):
        """Clear all files."""
        self.selected_files.clear()
        self._update_file_list()

    def _update_file_list(self):
        """Update the file listbox."""
        self.file_listbox.delete(0, tk.END)

        total_size = 0
        stale_files = []
        for file_path in self.selected_files:
            filename = os.path.basename(file_path)
            try:
                size = os.path.getsize(file_path)
                total_size += size
                size_str = self._format_size(size)

                # Infer metadata from filename (Issue 10)
                inferred = self._infer_metadata_from_filename(filename)
                suffix = ""
                if inferred:
                    parts = []
                    if "source" in inferred:
                        parts.append(inferred["source"])
                    if "version" in inferred:
                        parts.append(f"v{inferred['version']}")
                    if parts:
                        suffix = f"  [{', '.join(parts)}]"

                self.file_listbox.insert(tk.END, f"{filename}  ({size_str}){suffix}")
            except OSError:
                stale_files.append(file_path)

        # Remove files that no longer exist on disk
        for f in stale_files:
            self.selected_files.remove(f)

        count = len(self.selected_files)
        batch_note = ""
        if count > LARGE_BATCH_WARNING_THRESHOLD:
            batch_note = " ⚠️ Large batch"
        elif count >= LARGE_BATCH_WARNING_THRESHOLD // 2:  # >= 100 files
            batch_note = " (medium batch)"

        self.file_count_label.config(
            text=f"{count} file{'s' if count != 1 else ''} ({self._format_size(total_size)}){batch_note}"
        )

        if count > 0 and not self.is_uploading:
            self.upload_button.config(state=tk.NORMAL)
        else:
            self.upload_button.config(state=tk.DISABLED)

    def _format_size(self, size_bytes: int) -> str:
        """Format file size for display."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    def _pick_date(self):
        """Open date picker dialog."""
        try:
            dialog = DatePickerDialog(
                parent=self,
                title="Select Effective Date",
            )
            selected_date = dialog.date_selected
            if selected_date:
                self.effective_date = selected_date
                self.date_var.set(selected_date.strftime("%Y-%m-%d"))
        except Exception:
            # Fallback for older ttkbootstrap versions
            from tkinter import simpledialog
            date_str = simpledialog.askstring(
                "Effective Date",
                "Enter date (YYYY-MM-DD):",
                parent=self,
            )
            if date_str:
                try:
                    from datetime import datetime
                    self.effective_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    self.date_var.set(date_str)
                except ValueError:
                    messagebox.showerror(
                        "Invalid Date",
                        "Please enter date in YYYY-MM-DD format.",
                        parent=self,
                    )

    def _clear_date(self):
        """Clear the effective date."""
        self.effective_date = None
        self.date_var.set("")

    def _toggle_advanced_options(self):
        """Toggle visibility of advanced metadata fields (Fix 10)."""
        if self._advanced_visible.get():
            self._advanced_frame.pack(fill=tk.X, padx=5, pady=5)
        else:
            self._advanced_frame.pack_forget()

    def _pick_expiration_date(self):
        """Open date picker for expiration date."""
        try:
            dialog = DatePickerDialog(
                parent=self,
                title="Select Expiration Date",
            )
            selected_date = dialog.date_selected
            if selected_date:
                self.expiration_date = selected_date
                self.expiration_date_var.set(selected_date.strftime("%Y-%m-%d"))
        except Exception:
            from tkinter import simpledialog
            date_str = simpledialog.askstring(
                "Expiration Date",
                "Enter date (YYYY-MM-DD):",
                parent=self,
            )
            if date_str:
                try:
                    from datetime import datetime
                    self.expiration_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    self.expiration_date_var.set(date_str)
                except ValueError:
                    messagebox.showerror(
                        "Invalid Date",
                        "Please enter date in YYYY-MM-DD format.",
                        parent=self,
                    )

    def _clear_expiration_date(self):
        """Clear the expiration date."""
        self.expiration_date = None
        self.expiration_date_var.set("")

    @staticmethod
    def _infer_metadata_from_filename(filename: str) -> dict:
        """Infer guideline metadata from filename patterns (Issue 10).

        Recognizes patterns like:
        - AHA_Heart_Failure_2024_v2.1.pdf -> source=AHA, version=v2.1, year
        - NICE_CG181_Lipid_Modification.pdf -> source=NICE
        - ACC-AHA_Hypertension_2023.pdf -> source=AHA/ACC

        Args:
            filename: Original filename

        Returns:
            Dict with inferred metadata (source, version, year)
        """
        import re

        result = {}
        stem = Path(filename).stem

        # Try to detect source organization from known prefixes
        source_patterns = {
            r'^AHA[_/-]ACC|^ACC[_/-]AHA': 'AHA/ACC',
            r'^AHA': 'AHA',
            r'^ACC': 'ACC',
            r'^ADA': 'ADA',
            r'^GOLD': 'GOLD',
            r'^NICE': 'NICE',
            r'^HFSA': 'HFSA',
            r'^USPSTF': 'USPSTF',
            r'^IDSA': 'IDSA',
            r'^ACR': 'ACR',
            r'^ASCO': 'ASCO',
            r'^AAN': 'AAN',
            r'^APA': 'APA',
            r'^ACOG': 'ACOG',
            r'^AAP': 'AAP',
            r'^AGS': 'AGS',
        }

        for pattern, source in source_patterns.items():
            if re.search(pattern, stem, re.IGNORECASE):
                result['source'] = source
                break

        # Try to detect version (v1.0, v2.1, etc.)
        version_match = re.search(r'[_\s-]v?(\d+\.\d+)', stem)
        if version_match:
            result['version'] = version_match.group(1)

        # Try to detect year (4-digit year 2000-2099)
        year_match = re.search(r'[_\s-](20\d{2})[_\s.-]?', stem)
        if year_match:
            result['year'] = year_match.group(1)
            if 'version' not in result:
                result['version'] = year_match.group(1)

        return result

    def _start_upload(self):
        """Start the upload process."""
        if not self.selected_files:
            messagebox.showwarning(
                "No Files",
                "Please select guideline files to upload.",
                parent=self,
            )
            return

        # Validate file sizes
        max_size = 100 * 1024 * 1024  # 100 MB for guidelines
        for file_path in self.selected_files:
            try:
                if os.path.getsize(file_path) > max_size:
                    messagebox.showerror(
                        "File Too Large",
                        f"File exceeds maximum size (100 MB):\n{os.path.basename(file_path)}",
                        parent=self,
                    )
                    return
            except OSError:
                messagebox.showerror(
                    "File Not Found",
                    f"File no longer exists:\n{os.path.basename(file_path)}",
                    parent=self,
                )
                self._update_file_list()
                return

        # Check for large batch and show warning
        file_count = len(self.selected_files)
        if file_count > LARGE_BATCH_WARNING_THRESHOLD:
            # Calculate estimated time (rough estimate: 1-3 seconds per file average)
            estimated_min = file_count // 60  # Conservative: 1 file per second
            estimated_max = (file_count * 3) // 60  # Liberal: 3 seconds per file

            warning_message = (
                f"Large Batch Upload\n\n"
                f"You are about to upload {file_count} guideline documents.\n\n"
                f"Estimated processing time: {estimated_min}-{estimated_max} minutes\n"
                f"(varies based on file sizes and system resources)\n\n"
                f"The progress dialog can be minimized, and processing will\n"
                f"continue in the background.\n\n"
                f"Do you want to proceed?"
            )

            proceed = messagebox.askyesno(
                "Large Batch Upload",
                warning_message,
                parent=self,
                icon='warning'
            )

            if not proceed:
                return  # User cancelled, don't start upload

        # Prepare options with guideline metadata
        options = {
            "specialty": self.specialty_var.get() or None,
            "source": self.source_var.get() or None,
            "version": self.version_var.get() or None,
            "effective_date": self.effective_date,
            "expiration_date": self.expiration_date,
            "document_type": self.type_var.get() or None,
            "title": self.title_var.get() or None,
            "extract_recommendations": self.extract_recommendations_var.get(),
            "enable_graph": self.graph_var.get(),
            "enable_ocr": self.ocr_var.get(),
            "skip_duplicates": self.skip_duplicates_var.get(),
        }

        # Show progress
        self.progress_frame.pack(fill=tk.X, pady=(15, 0))
        self.upload_button.config(state=tk.DISABLED)
        self.is_uploading = True

        # Call upload callback
        if self.on_upload:
            self.on_upload(self.selected_files.copy(), options)

        # Auto-close dialog now that upload is queued
        # Progress dialog will show instead
        self.after(100, self.destroy)  # Small delay to ensure callback completes

    def update_progress(
        self,
        filename: str,
        status: GuidelineUploadStatus,
        progress_percent: float,
        error_message: Optional[str] = None,
    ):
        """Update progress display.

        Args:
            filename: Current file being processed
            status: Upload status
            progress_percent: Progress percentage (0-100)
            error_message: Optional error message
        """
        if not self.winfo_exists():
            return

        self.progress_bar["value"] = progress_percent

        status_text = {
            GuidelineUploadStatus.PENDING: "Queued",
            GuidelineUploadStatus.EXTRACTING: "Extracting text...",
            GuidelineUploadStatus.CHUNKING: "Splitting into sections...",
            GuidelineUploadStatus.EMBEDDING: "Generating embeddings...",
            GuidelineUploadStatus.SYNCING: "Syncing to database...",
            GuidelineUploadStatus.COMPLETED: "Completed",
            GuidelineUploadStatus.FAILED: f"Failed: {error_message or 'Unknown error'}",
        }.get(status, "Processing...")

        self.progress_label.config(text=status_text)
        self.current_file_label.config(text=filename)

        self.update_idletasks()

    def complete_upload(self, success_count: int, fail_count: int):
        """Called when upload is complete.

        Args:
            success_count: Number of successful uploads
            fail_count: Number of failed uploads
        """
        self.is_uploading = False
        self.progress_bar["value"] = 100
        self.progress_label.config(text="Upload Complete")

        if fail_count == 0:
            messagebox.showinfo(
                "Upload Complete",
                f"Successfully uploaded {success_count} guideline(s).",
                parent=self,
            )
            self.destroy()
        else:
            messagebox.showwarning(
                "Upload Complete",
                f"Uploaded {success_count} guideline(s).\n{fail_count} failed.",
                parent=self,
            )
            self.upload_button.config(state=tk.NORMAL)

    def _setup_drag_and_drop(self):
        """Set up drag-and-drop file support (Fix 18).

        Uses tkinterdnd2 if available, gracefully falls back if not installed.
        """
        try:
            import tkinterdnd2

            # Register the file listbox as a drop target
            self.file_listbox.drop_target_register(tkinterdnd2.DND_FILES)
            self.file_listbox.dnd_bind('<<Drop>>', self._on_drop)
        except ImportError:
            pass  # tkinterdnd2 not installed, drag-and-drop not available
        except Exception:
            pass  # Graceful fallback

    def _on_drop(self, event):
        """Handle dropped files (Fix 18)."""
        import re as _re

        # Parse dropped paths (handle brace-wrapped paths from tkinterdnd2)
        data = event.data
        files = []

        if '{' in data:
            # Brace-wrapped paths: {/path/with spaces/file.pdf} {/another/file.pdf}
            files = _re.findall(r'\{([^}]+)\}', data)
        else:
            # Space-separated paths
            files = data.split()

        # Filter for supported extensions
        supported = {'.pdf', '.docx', '.doc', '.txt', '.md'}
        valid_files = []
        for f in files:
            f = f.strip()
            if f:
                ext = os.path.splitext(f)[1].lower()
                if ext in supported:
                    valid_files.append(f)

        if valid_files:
            self._add_files_to_list(valid_files)

    def _on_cancel(self):
        """Handle cancel button."""
        if self.is_uploading:
            if messagebox.askyesno(
                "Cancel Upload",
                "Upload is in progress. Cancel anyway?",
                parent=self,
            ):
                self.destroy()
        else:
            self.destroy()


class GuidelinesUploadProgressDialog(tk.Toplevel):
    """Progress dialog for batch guideline uploads."""

    def __init__(
        self,
        parent: tk.Widget,
        batch_id: str,
        queue_manager,
    ):
        """Initialize progress dialog.

        Args:
            parent: Parent widget
            batch_id: Batch identifier from queue
            queue_manager: ProcessingQueue instance
        """
        super().__init__(parent)
        self.title("Uploading Clinical Guidelines")
        self.geometry("550x380")
        self.resizable(False, False)

        self.batch_id = batch_id
        self.queue_manager = queue_manager
        self.cancelled = False

        # ETA tracking (Fix 11)
        import time as _time
        self._start_time = _time.time()
        self._eta_timer_id = None

        # Get batch info
        batch_info = queue_manager.get_guideline_batch_status(batch_id)
        self.total_files = batch_info.get("total_files", 0) if batch_info else 0
        self.processed_files = batch_info.get("processed", 0) if batch_info else 0
        self.success_count = batch_info.get("successful", 0) if batch_info else 0
        self.fail_count = batch_info.get("failed", 0) if batch_info else 0

        self._create_widgets()
        self._center_window()

        # NON-MODAL: Don't grab focus, allow user to interact with main app
        self.transient(parent)
        # REMOVED: self.grab_set()  # This made it modal

        # Allow minimizing instead of closing
        self.protocol("WM_DELETE_WINDOW", self._on_minimize)

    def _center_window(self):
        """Center the dialog."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        """Create dialog widgets."""
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Status label
        self.status_label = ttk.Label(
            main_frame,
            text="Preparing guideline upload...",
            font=("TkDefaultFont", 11),
        )
        self.status_label.pack(pady=(0, 10))

        # Overall progress
        ttk.Label(main_frame, text="Overall Progress:").pack(anchor=tk.W)
        self.overall_progress = ttk.Progressbar(
            main_frame,
            mode="determinate",
            length=450,
        )
        self.overall_progress.pack(fill=tk.X, pady=(5, 15))

        self.overall_label = ttk.Label(
            main_frame,
            text=f"0 / {self.total_files} guidelines",
        )
        self.overall_label.pack(anchor=tk.W)

        # Current file progress
        ttk.Label(main_frame, text="Current Guideline:").pack(anchor=tk.W, pady=(10, 0))
        self.current_file_label = ttk.Label(
            main_frame,
            text="",
            foreground="gray",
        )
        self.current_file_label.pack(anchor=tk.W)

        self.file_progress = ttk.Progressbar(
            main_frame,
            mode="determinate",
            length=450,
        )
        self.file_progress.pack(fill=tk.X, pady=(5, 15))

        self.file_status_label = ttk.Label(main_frame, text="")
        self.file_status_label.pack(anchor=tk.W)

        # Stats
        self.stats_label = ttk.Label(
            main_frame,
            text="",
            foreground="gray",
        )
        self.stats_label.pack(anchor=tk.W, pady=(10, 0))

        # ETA display (Fix 11)
        self._eta_label = ttk.Label(
            main_frame,
            text="Elapsed: 0s | ETA: calculating...",
            foreground="gray",
        )
        self._eta_label.pack(anchor=tk.W, pady=(5, 0))
        self._start_eta_timer()

        # Cancel button
        self.cancel_button = ttk.Button(
            main_frame,
            text="Cancel",
            command=self._on_cancel,
        )
        self.cancel_button.pack(pady=(15, 0))

    def update_batch_progress(self, batch_id: str, batch_info: Dict):
        """Update overall batch progress from queue callback.

        Args:
            batch_id: Batch identifier
            batch_info: Batch information dictionary
        """
        if not self.winfo_exists() or batch_id != self.batch_id:
            return

        processed = batch_info.get("processed", 0)
        total = batch_info.get("total_files", 1)
        successful = batch_info.get("successful", 0)
        failed = batch_info.get("failed", 0)
        skipped = batch_info.get("skipped", 0)

        # Keep local state in sync for ETA timer (avoids lock re-acquisition)
        self.processed_files = processed
        self.total_files = total
        self.success_count = successful
        self.fail_count = failed

        # Update overall progress
        progress_pct = (processed / total * 100) if total > 0 else 0
        self.overall_progress["value"] = progress_pct
        self.overall_label.config(text=f"{processed} / {total} guidelines")

        # Update stats
        if skipped > 0:
            self.stats_label.config(
                text=f"Success: {successful}  |  Skipped: {skipped}  |  Failed: {failed}"
            )
        else:
            self.stats_label.config(
                text=f"Success: {successful}  |  Failed: {failed}"
            )

        # Update status
        status = batch_info.get("status", "processing")
        if status == "completed":
            self.status_label.config(text="Upload Complete")
            self.cancel_button.config(text="Close")
        elif status == "cancelled":
            self.status_label.config(text="Upload Cancelled")
            self.cancel_button.config(text="Close")
        else:
            self.status_label.config(text=f"Processing {processed}/{total}...")

        self.update_idletasks()

    def update_file_start(self, filename: str, file_index: int):
        """Called when starting a new file.

        Args:
            filename: Name of the file
            file_index: Index of the file (0-based)
        """
        if not self.winfo_exists():
            return

        self.current_file_label.config(text=filename)
        self.file_progress["value"] = 0
        self.file_status_label.config(text="Starting...")

        self.update_idletasks()

    def update_file_progress(
        self,
        status: GuidelineUploadStatus,
        progress_percent: float,
        error_message: Optional[str] = None,
    ):
        """Update current file progress.

        Args:
            status: Upload status
            progress_percent: Progress percentage (0-100)
            error_message: Optional error message
        """
        if not self.winfo_exists():
            return

        self.file_progress["value"] = progress_percent

        status_text = {
            GuidelineUploadStatus.EXTRACTING: "Extracting text...",
            GuidelineUploadStatus.CHUNKING: "Creating sections...",
            GuidelineUploadStatus.EMBEDDING: "Generating embeddings...",
            GuidelineUploadStatus.SYNCING: "Syncing to database...",
            GuidelineUploadStatus.COMPLETED: "Complete!",
            GuidelineUploadStatus.FAILED: f"Failed: {error_message or 'Error'}",
        }.get(status, "Processing...")

        self.file_status_label.config(text=status_text)
        self.update_idletasks()

    def update_file_complete(self, success: bool):
        """Called when a file completes.

        Args:
            success: Whether the upload succeeded
        """
        if not self.winfo_exists():
            return

        self.processed_files += 1
        if success:
            self.success_count += 1
        else:
            self.fail_count += 1

        # Update overall progress
        progress_pct = (self.processed_files / self.total_files) * 100
        self.overall_progress["value"] = progress_pct
        self.overall_label.config(text=f"{self.processed_files} / {self.total_files} guidelines")

        # Update stats
        self.stats_label.config(
            text=f"Success: {self.success_count}  |  Failed: {self.fail_count}"
        )

        self.update_idletasks()

    def complete(self):
        """Called when all uploads are complete."""
        if not self.winfo_exists():
            return

        # Cancel ETA timer (Fix 11)
        if self._eta_timer_id:
            self.after_cancel(self._eta_timer_id)
            self._eta_timer_id = None

        self.status_label.config(text="Upload Complete")
        self.file_status_label.config(text="")
        self.file_progress["value"] = 100
        self.cancel_button.config(text="Close")

        # Update ETA label to show final elapsed time (Fix 11)
        import time as _time
        elapsed = _time.time() - self._start_time
        self._eta_label.configure(text=f"Elapsed: {self._format_duration(elapsed)} | Complete")

        self.update_idletasks()

    def _start_eta_timer(self):
        """Start the ETA update timer (Fix 11)."""
        self._update_eta()

    def _update_eta(self):
        """Update elapsed time and ETA display (Fix 11).

        IMPORTANT: This runs on the main thread via after(). It must NOT
        call into the queue_manager (which acquires locks) to avoid deadlocks
        with worker threads that hold locks and schedule UI updates.
        Uses only local state updated by progress callbacks instead.
        """
        import time as _time

        if not self.winfo_exists():
            return

        elapsed = _time.time() - self._start_time
        elapsed_str = self._format_duration(elapsed)

        # Use local state (updated by callbacks) — no lock acquisition needed
        processed = self.processed_files
        total = self.total_files

        if processed > 0 and processed < total:
            rate = elapsed / processed
            remaining = rate * (total - processed)
            eta_str = self._format_duration(remaining)
            self._eta_label.configure(
                text=f"Elapsed: {elapsed_str} | ETA: ~{eta_str}"
            )
        elif processed >= total and total > 0:
            self._eta_label.configure(
                text=f"Elapsed: {elapsed_str} | Complete"
            )
            self._eta_timer_id = None
            return
        else:
            self._eta_label.configure(
                text=f"Elapsed: {elapsed_str} | ETA: calculating..."
            )

        self._eta_timer_id = self.after(1000, self._update_eta)

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format duration in seconds to human-readable string (Fix 11)."""
        seconds = int(seconds)
        if seconds < 60:
            return f"{seconds}s"
        minutes = seconds // 60
        secs = seconds % 60
        if minutes < 60:
            return f"{minutes}m {secs}s"
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h {mins}m"

    def _on_cancel(self):
        """Handle cancel button."""
        if self.cancel_button.cget("text") == "Close":
            if self._eta_timer_id:
                self.after_cancel(self._eta_timer_id)
                self._eta_timer_id = None
            self.destroy()
            return

        if messagebox.askyesno(
            "Cancel Upload",
            "Are you sure you want to cancel the upload?\n\n"
            "Note: Currently processing files will complete.",
            parent=self,
        ):
            if self._eta_timer_id:
                self.after_cancel(self._eta_timer_id)
                self._eta_timer_id = None
            count = self.queue_manager.cancel_guideline_batch(self.batch_id)
            self.status_label.config(text=f"Cancelling... ({count} tasks)")
            self.cancelled = True
            # Don't destroy - let user see final status
            self.cancel_button.config(text="Close")

    def _on_minimize(self):
        """Hide dialog instead of destroying it."""
        self.withdraw()

        # Show status in main app status bar if available
        try:
            batch = self.queue_manager.guideline_batches.get(self.batch_id)
            if batch and hasattr(self.queue_manager.app, 'status_manager'):
                self.queue_manager.app.status_manager.info(
                    f"Guidelines upload: {batch['processed']}/{batch['total_files']} "
                    f"(success: {batch['successful']}, failed: {batch['failed']})"
                )
        except Exception:
            pass  # Silently ignore status bar update errors

    def show(self):
        """Show the dialog (deiconify if minimized)."""
        self.deiconify()
        self.lift()
