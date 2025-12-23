"""
Import Contacts Dialog

Provides a dialog for importing contacts from a CSV file into the
saved recipients database for use in referral generation.
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from typing import Optional, Dict, List, Any

from managers.recipient_manager import get_recipient_manager


class ImportContactsDialog:
    """Dialog for importing contacts from CSV files."""

    def __init__(self, parent):
        """Initialize the import contacts dialog.

        Args:
            parent: Parent window
        """
        self.parent = parent
        self.result = None
        self.file_path = None
        self.preview_data = []
        self.total_count = 0

    def show(self) -> Optional[Dict[str, Any]]:
        """Show the dialog and return import results.

        Returns:
            Dictionary with import results, or None if cancelled
        """
        # Create dialog window
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Import Contacts from CSV")

        # Get screen dimensions
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()

        # Set dialog size
        dialog_width = min(800, int(screen_width * 0.7))
        dialog_height = min(600, int(screen_height * 0.7))

        self.dialog.geometry(f"{dialog_width}x{dialog_height}")
        self.dialog.minsize(600, 400)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Center the dialog
        self.dialog.update_idletasks()
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

        # Create main container
        main_container = ttk.Frame(self.dialog)
        main_container.pack(fill=BOTH, expand=True, padx=15, pady=15)

        # Title
        title_label = ttk.Label(
            main_container,
            text="Import Contacts from CSV",
            font=("Segoe UI", 14, "bold")
        )
        title_label.pack(pady=(0, 15))

        # File selection frame
        file_frame = ttk.LabelFrame(main_container, text="Select CSV File", padding=10)
        file_frame.pack(fill=X, pady=(0, 10))

        file_row = ttk.Frame(file_frame)
        file_row.pack(fill=X)

        self.file_path_var = tk.StringVar()
        file_entry = ttk.Entry(file_row, textvariable=self.file_path_var, state="readonly")
        file_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 10))

        browse_btn = ttk.Button(
            file_row,
            text="Browse...",
            command=self._browse_file,
            style="secondary.TButton"
        )
        browse_btn.pack(side=LEFT)

        # Expected format info
        format_label = ttk.Label(
            file_frame,
            text="Expected columns: Last Name, First Name, Title, Specialty, Phone Number, Fax Number, Office Name, etc.",
            foreground="gray",
            font=("Segoe UI", 9)
        )
        format_label.pack(anchor=W, pady=(10, 0))

        # Preview frame
        preview_frame = ttk.LabelFrame(main_container, text="Preview (first 5 rows)", padding=10)
        preview_frame.pack(fill=BOTH, expand=True, pady=(0, 10))

        # Create treeview for preview
        columns = ("name", "specialty", "phone", "fax", "facility")
        self.preview_tree = ttk.Treeview(preview_frame, columns=columns, show="headings", height=5)

        self.preview_tree.heading("name", text="Name")
        self.preview_tree.heading("specialty", text="Specialty")
        self.preview_tree.heading("phone", text="Phone")
        self.preview_tree.heading("fax", text="Fax")
        self.preview_tree.heading("facility", text="Office/Facility")

        self.preview_tree.column("name", width=150)
        self.preview_tree.column("specialty", width=120)
        self.preview_tree.column("phone", width=100)
        self.preview_tree.column("fax", width=100)
        self.preview_tree.column("facility", width=150)

        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(preview_frame, orient=VERTICAL, command=self.preview_tree.yview)
        self.preview_tree.configure(yscrollcommand=scrollbar.set)

        self.preview_tree.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        # Status label
        self.status_var = tk.StringVar(value="Select a CSV file to preview")
        status_label = ttk.Label(
            main_container,
            textvariable=self.status_var,
            foreground="gray"
        )
        status_label.pack(anchor=W, pady=(0, 10))

        # Info about import behavior
        info_frame = ttk.Frame(main_container)
        info_frame.pack(fill=X, pady=(0, 10))

        ttk.Label(
            info_frame,
            text="Import behavior:",
            font=("Segoe UI", 9, "bold")
        ).pack(anchor=W)

        ttk.Label(
            info_frame,
            text="  - Duplicates (same name + specialty) will be skipped",
            foreground="gray",
            font=("Segoe UI", 9)
        ).pack(anchor=W)

        ttk.Label(
            info_frame,
            text="  - All contacts imported as 'Specialist' type",
            foreground="gray",
            font=("Segoe UI", 9)
        ).pack(anchor=W)

        # Button frame
        button_frame = ttk.Frame(main_container)
        button_frame.pack(fill=X)

        ttk.Button(
            button_frame,
            text="Cancel",
            command=self._cancel,
            style="secondary.TButton"
        ).pack(side=RIGHT, padx=(5, 0))

        self.import_btn = ttk.Button(
            button_frame,
            text="Import Contacts",
            command=self._import,
            style="primary.TButton",
            state=DISABLED
        )
        self.import_btn.pack(side=RIGHT)

        # Wait for dialog to close
        self.dialog.wait_window()

        return self.result

    def _browse_file(self):
        """Open file browser to select CSV file."""
        file_path = filedialog.askopenfilename(
            parent=self.dialog,
            title="Select CSV File",
            filetypes=[
                ("CSV files", "*.csv"),
                ("All files", "*.*")
            ]
        )

        if file_path:
            self.file_path = file_path
            self.file_path_var.set(file_path)
            self._load_preview()

    def _load_preview(self):
        """Load and display preview of CSV file."""
        if not self.file_path:
            return

        # Clear existing preview
        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)

        recipient_manager = get_recipient_manager()

        try:
            preview_rows, total_count, columns = recipient_manager.preview_csv(self.file_path, limit=5)

            self.preview_data = preview_rows
            self.total_count = total_count

            # Check for expected columns
            expected = {"Last Name", "First Name", "Specialty"}
            found = set(columns)
            if not expected.issubset(found):
                missing = expected - found
                self.status_var.set(f"Warning: Missing columns: {', '.join(missing)}")
            else:
                self.status_var.set(f"Found {total_count} contacts in file")

            # Populate preview
            for row in preview_rows:
                # Build name from parts
                name_parts = []
                if row.get("Title"):
                    name_parts.append(row["Title"])
                if row.get("First Name"):
                    name_parts.append(row["First Name"])
                if row.get("Last Name"):
                    name_parts.append(row["Last Name"])
                name = " ".join(name_parts) if name_parts else "Unknown"

                self.preview_tree.insert("", END, values=(
                    name,
                    row.get("Specialty", ""),
                    row.get("Phone Number", ""),
                    row.get("Fax Number", ""),
                    row.get("Office Name", "")
                ))

            # Enable import button
            self.import_btn.config(state=NORMAL)

        except Exception as e:
            self.status_var.set(f"Error reading file: {str(e)}")
            self.import_btn.config(state=DISABLED)

    def _import(self):
        """Perform the import."""
        if not self.file_path:
            return

        # Confirm import
        if self.total_count > 100:
            if not messagebox.askyesno(
                "Confirm Import",
                f"You are about to import {self.total_count} contacts.\n\nThis may take a moment. Continue?",
                parent=self.dialog
            ):
                return

        # Show progress
        self.status_var.set("Importing contacts...")
        self.import_btn.config(state=DISABLED)
        self.dialog.update()

        # Perform import
        recipient_manager = get_recipient_manager()
        imported, skipped, errors = recipient_manager.import_from_csv(self.file_path)

        # Show results
        self.result = {
            "imported": imported,
            "skipped": skipped,
            "errors": errors
        }

        # Build result message
        msg_parts = [f"Imported: {imported} contacts"]
        if skipped > 0:
            msg_parts.append(f"Skipped: {skipped} duplicates")
        if errors:
            msg_parts.append(f"Errors: {len(errors)}")

        result_msg = "\n".join(msg_parts)

        if errors and len(errors) <= 5:
            result_msg += "\n\nErrors:\n" + "\n".join(errors[:5])
        elif errors:
            result_msg += f"\n\nFirst 5 errors:\n" + "\n".join(errors[:5])

        if imported > 0:
            messagebox.showinfo("Import Complete", result_msg, parent=self.dialog)
        else:
            messagebox.showwarning("Import Complete", result_msg, parent=self.dialog)

        self.dialog.destroy()

    def _cancel(self):
        """Handle cancel button click."""
        self.result = None
        self.dialog.destroy()
