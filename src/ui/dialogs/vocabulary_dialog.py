"""
Vocabulary Settings Dialog for managing custom vocabulary corrections.

Allows users to add, edit, and delete vocabulary correction entries
for improving transcription accuracy of medical terms, doctor names,
medications, and abbreviations.
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import logging
from typing import Optional

from managers.vocabulary_manager import vocabulary_manager
from settings.settings import SETTINGS


class VocabularyDialog:
    """Dialog for managing custom vocabulary corrections."""

    # Category options
    CATEGORIES = ["doctors", "medications", "terminology", "abbreviations", "general"]

    # Specialty options
    SPECIALTIES = [
        "general", "cardiology", "dermatology", "endocrinology",
        "gastroenterology", "neurology", "oncology", "orthopedics",
        "pediatrics", "psychiatry", "pulmonology", "rheumatology"
    ]

    def __init__(self, parent):
        """Initialize the vocabulary dialog.

        Args:
            parent: Parent window
        """
        self.parent = parent
        self.dialog = None
        self.logger = logging.getLogger(__name__)

        # Load current corrections from manager
        self._load_from_manager()

    def _load_from_manager(self):
        """Load corrections from the vocabulary manager."""
        self.working_corrections = vocabulary_manager._corrections.copy()
        self.enabled = vocabulary_manager._enabled
        self.default_specialty = vocabulary_manager._default_specialty

    def show(self) -> bool:
        """Show the dialog and return True if changes were saved.

        Returns:
            bool: True if user saved changes, False if cancelled
        """
        # Create dialog window
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Custom Vocabulary Settings")
        self.dialog.geometry("1100x700")
        self.dialog.minsize(900, 600)
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - 1100) // 2
        y = (self.dialog.winfo_screenheight() - 700) // 2
        self.dialog.geometry(f"1100x700+{x}+{y}")

        # Grab focus after window is visible
        self.dialog.deiconify()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass  # Window not viewable yet

        # Create main container
        main_container = ttk.Frame(self.dialog)
        main_container.pack(fill=BOTH, expand=True, padx=10, pady=10)

        # Create enable toggle at top
        self._create_enable_section(main_container)

        # Create toolbar
        self._create_toolbar(main_container)

        # Create corrections list
        self._create_corrections_list(main_container)

        # Create button bar
        result = self._create_button_bar(main_container)

        # Handle dialog close
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)

        # Focus on dialog
        self.dialog.focus_set()

        # Wait for dialog to close
        self.dialog.wait_window()

        return result.get("saved", False)

    def _create_enable_section(self, parent):
        """Create the enable/disable toggle section.

        Args:
            parent: Parent widget
        """
        enable_frame = ttk.Frame(parent)
        enable_frame.pack(fill=X, pady=(0, 10))

        # Enable checkbox
        self.enabled_var = tk.BooleanVar(value=self.enabled)
        enable_check = ttk.Checkbutton(
            enable_frame,
            text="Enable vocabulary corrections",
            variable=self.enabled_var,
            bootstyle="success-round-toggle"
        )
        enable_check.pack(side=LEFT)

        # Default specialty
        ttk.Label(enable_frame, text="Default specialty:").pack(side=LEFT, padx=(30, 5))

        self.specialty_var = tk.StringVar(value=self.default_specialty)
        specialty_combo = ttk.Combobox(
            enable_frame,
            textvariable=self.specialty_var,
            values=self.SPECIALTIES,
            state="readonly",
            width=15
        )
        specialty_combo.pack(side=LEFT)

        # Help text
        ttk.Label(
            enable_frame,
            text="(Corrections are applied after transcription)",
            foreground="gray"
        ).pack(side=RIGHT)

    def _create_toolbar(self, parent):
        """Create toolbar with action buttons.

        Args:
            parent: Parent widget
        """
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=X, pady=(0, 10))

        # Add button
        ttk.Button(
            toolbar,
            text="+ Add",
            command=self._add_entry,
            bootstyle="success"
        ).pack(side=LEFT, padx=(0, 5))

        # Edit button
        ttk.Button(
            toolbar,
            text="Edit",
            command=self._edit_selected,
            bootstyle="info"
        ).pack(side=LEFT, padx=(0, 5))

        # Delete button
        ttk.Button(
            toolbar,
            text="Delete",
            command=self._delete_selected,
            bootstyle="danger"
        ).pack(side=LEFT, padx=(0, 15))

        # Separator
        ttk.Separator(toolbar, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=5)

        # Import button
        ttk.Button(
            toolbar,
            text="Import CSV",
            command=self._import_csv,
            bootstyle="secondary"
        ).pack(side=LEFT, padx=(10, 5))

        # Export button
        ttk.Button(
            toolbar,
            text="Export CSV",
            command=self._export_csv,
            bootstyle="secondary"
        ).pack(side=LEFT, padx=(0, 15))

        # Separator
        ttk.Separator(toolbar, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=5)

        # Category filter
        ttk.Label(toolbar, text="Category:").pack(side=LEFT, padx=(10, 5))

        self.filter_category_var = tk.StringVar(value="All")
        category_filter = ttk.Combobox(
            toolbar,
            textvariable=self.filter_category_var,
            values=["All"] + self.CATEGORIES,
            state="readonly",
            width=12
        )
        category_filter.pack(side=LEFT)
        category_filter.bind("<<ComboboxSelected>>", self._on_filter_change)

        # Specialty filter
        ttk.Label(toolbar, text="Specialty:").pack(side=LEFT, padx=(15, 5))

        self.filter_specialty_var = tk.StringVar(value="All")
        specialty_filter = ttk.Combobox(
            toolbar,
            textvariable=self.filter_specialty_var,
            values=["All"] + self.SPECIALTIES,
            state="readonly",
            width=12
        )
        specialty_filter.pack(side=LEFT)
        specialty_filter.bind("<<ComboboxSelected>>", self._on_filter_change)

        # Clear all button (far right)
        ttk.Button(
            toolbar,
            text="Clear All",
            command=self._clear_all,
            bootstyle="warning"
        ).pack(side=RIGHT)

    def _create_corrections_list(self, parent):
        """Create the list of corrections.

        Args:
            parent: Parent widget
        """
        # Create frame with scrollbar
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=BOTH, expand=True, pady=(0, 10))

        # Create treeview
        columns = ("replacement", "category", "specialty", "enabled", "priority")
        self.tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            height=20
        )

        # Configure columns
        self.tree.heading("replacement", text="Find Text", anchor=W)
        self.tree.heading("category", text="Category", anchor=W)
        self.tree.heading("specialty", text="Specialty", anchor=W)
        self.tree.heading("enabled", text="Enabled", anchor=CENTER)
        self.tree.heading("priority", text="Priority", anchor=CENTER)

        self.tree.column("replacement", width=400, minwidth=200)
        self.tree.column("category", width=120, minwidth=100)
        self.tree.column("specialty", width=120, minwidth=100)
        self.tree.column("enabled", width=80, minwidth=60)
        self.tree.column("priority", width=80, minwidth=60)

        # Add scrollbars
        y_scrollbar = ttk.Scrollbar(list_frame, orient=VERTICAL, command=self.tree.yview)
        x_scrollbar = ttk.Scrollbar(list_frame, orient=HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)

        # Grid layout for scrollbars
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")

        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)

        # Populate tree
        self._populate_tree()

        # Bind double-click to edit
        self.tree.bind("<Double-Button-1>", lambda e: self._edit_selected())

        # Create context menu
        self._create_context_menu()

    def _create_context_menu(self):
        """Create right-click context menu."""
        self.context_menu = tk.Menu(self.tree, tearoff=0)
        self.context_menu.add_command(label="Edit", command=self._edit_selected)
        self.context_menu.add_command(label="Delete", command=self._delete_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Toggle Enabled", command=self._toggle_enabled)

        # Bind right-click
        self.tree.bind("<Button-3>", self._show_context_menu)

    def _show_context_menu(self, event):
        """Show context menu on right-click."""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def _populate_tree(self):
        """Populate the tree with corrections."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Get filters
        filter_category = self.filter_category_var.get() if hasattr(self, 'filter_category_var') else "All"
        filter_specialty = self.filter_specialty_var.get() if hasattr(self, 'filter_specialty_var') else "All"

        # Add corrections
        for find_text, rule in sorted(self.working_corrections.items()):
            category = rule.get("category", "general")
            specialty = rule.get("specialty", "general") or "general"
            enabled = rule.get("enabled", True)
            priority = rule.get("priority", 0)

            # Apply filters
            if filter_category != "All" and category != filter_category:
                continue
            if filter_specialty != "All" and specialty != filter_specialty:
                continue

            replacement = rule.get("replacement", "")

            # Format display
            display_text = f"{find_text} → {replacement}"
            enabled_text = "Yes" if enabled else "No"

            self.tree.insert(
                "", "end",
                iid=find_text,  # Use find_text as item ID
                values=(display_text, category, specialty, enabled_text, priority)
            )

    def _on_filter_change(self, event=None):
        """Handle filter change."""
        self._populate_tree()

    def _add_entry(self):
        """Add a new vocabulary entry."""
        dialog = VocabularyEntryDialog(self.dialog, self.CATEGORIES, self.SPECIALTIES)
        result = dialog.show()

        if result:
            find_text = result["find_text"]

            # Check for duplicates
            if find_text in self.working_corrections:
                messagebox.showwarning(
                    "Duplicate Entry",
                    f"An entry for '{find_text}' already exists.",
                    parent=self.dialog
                )
                return

            # Add to working copy
            self.working_corrections[find_text] = {
                "replacement": result["replacement"],
                "category": result["category"],
                "specialty": result["specialty"],
                "case_sensitive": result["case_sensitive"],
                "enabled": result["enabled"],
                "priority": result["priority"]
            }

            # Refresh tree
            self._populate_tree()
            self._update_count_label()

    def _edit_selected(self):
        """Edit the selected entry."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo(
                "No Selection",
                "Please select an entry to edit.",
                parent=self.dialog
            )
            return

        find_text = selection[0]  # Item ID is the find_text
        rule = self.working_corrections.get(find_text, {})

        dialog = VocabularyEntryDialog(
            self.dialog,
            self.CATEGORIES,
            self.SPECIALTIES,
            find_text=find_text,
            replacement=rule.get("replacement", ""),
            category=rule.get("category", "general"),
            specialty=rule.get("specialty", "general"),
            case_sensitive=rule.get("case_sensitive", False),
            enabled=rule.get("enabled", True),
            priority=rule.get("priority", 0)
        )
        result = dialog.show()

        if result:
            new_find_text = result["find_text"]

            # If find text changed, check for duplicates and remove old
            if new_find_text != find_text:
                if new_find_text in self.working_corrections:
                    messagebox.showwarning(
                        "Duplicate Entry",
                        f"An entry for '{new_find_text}' already exists.",
                        parent=self.dialog
                    )
                    return
                del self.working_corrections[find_text]

            # Update/add entry
            self.working_corrections[new_find_text] = {
                "replacement": result["replacement"],
                "category": result["category"],
                "specialty": result["specialty"],
                "case_sensitive": result["case_sensitive"],
                "enabled": result["enabled"],
                "priority": result["priority"]
            }

            # Refresh tree
            self._populate_tree()

    def _delete_selected(self):
        """Delete the selected entry."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo(
                "No Selection",
                "Please select an entry to delete.",
                parent=self.dialog
            )
            return

        find_text = selection[0]

        if messagebox.askyesno(
            "Delete Entry",
            f"Are you sure you want to delete the entry for:\n\n'{find_text}'?",
            parent=self.dialog
        ):
            del self.working_corrections[find_text]
            self._populate_tree()
            self._update_count_label()

    def _toggle_enabled(self):
        """Toggle the enabled state of selected entry."""
        selection = self.tree.selection()
        if not selection:
            return

        find_text = selection[0]
        if find_text in self.working_corrections:
            current = self.working_corrections[find_text].get("enabled", True)
            self.working_corrections[find_text]["enabled"] = not current
            self._populate_tree()

    def _clear_all(self):
        """Clear all corrections."""
        if not self.working_corrections:
            return

        if messagebox.askyesno(
            "Clear All",
            f"Are you sure you want to delete all {len(self.working_corrections)} entries?\n\n"
            "This cannot be undone.",
            parent=self.dialog
        ):
            self.working_corrections.clear()
            self._populate_tree()
            self._update_count_label()

    def _import_csv(self):
        """Import corrections from CSV file."""
        file_path = filedialog.askopenfilename(
            parent=self.dialog,
            title="Import Vocabulary from CSV",
            filetypes=[
                ("CSV files", "*.csv"),
                ("All files", "*.*")
            ]
        )

        if not file_path:
            return

        try:
            # Use manager's import method to get corrections
            import csv
            imported = {}
            errors = []

            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row_num, row in enumerate(reader, start=2):
                    try:
                        find_text = row.get('find_text', '').strip()
                        replacement = row.get('replacement', '').strip()

                        if not find_text or not replacement:
                            errors.append(f"Row {row_num}: Missing find_text or replacement")
                            continue

                        imported[find_text] = {
                            "replacement": replacement,
                            "category": row.get('category', 'general').strip() or 'general',
                            "specialty": row.get('specialty', '').strip() or None,
                            "case_sensitive": row.get('case_sensitive', '').lower() == 'true',
                            "enabled": row.get('enabled', 'true').lower() != 'false',
                            "priority": int(row.get('priority', 0) or 0)
                        }
                    except Exception as e:
                        errors.append(f"Row {row_num}: {str(e)}")

            if imported:
                # Merge with existing
                self.working_corrections.update(imported)
                self._populate_tree()
                self._update_count_label()

                msg = f"Imported {len(imported)} entries."
                if errors:
                    msg += f"\n\n{len(errors)} errors:\n" + "\n".join(errors[:5])
                    if len(errors) > 5:
                        msg += f"\n... and {len(errors) - 5} more"

                messagebox.showinfo("Import Complete", msg, parent=self.dialog)
            else:
                messagebox.showwarning(
                    "Import Failed",
                    "No valid entries found in the CSV file.",
                    parent=self.dialog
                )

        except Exception as e:
            messagebox.showerror(
                "Import Error",
                f"Failed to import CSV file:\n\n{str(e)}",
                parent=self.dialog
            )

    def _export_csv(self):
        """Export corrections to CSV file."""
        if not self.working_corrections:
            messagebox.showinfo(
                "Nothing to Export",
                "There are no vocabulary entries to export.",
                parent=self.dialog
            )
            return

        file_path = filedialog.asksaveasfilename(
            parent=self.dialog,
            title="Export Vocabulary to CSV",
            defaultextension=".csv",
            filetypes=[
                ("CSV files", "*.csv"),
                ("All files", "*.*")
            ]
        )

        if not file_path:
            return

        try:
            import csv

            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['find_text', 'replacement', 'category', 'specialty',
                              'case_sensitive', 'enabled', 'priority']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for find_text, rule in sorted(self.working_corrections.items()):
                    writer.writerow({
                        'find_text': find_text,
                        'replacement': rule.get('replacement', ''),
                        'category': rule.get('category', 'general'),
                        'specialty': rule.get('specialty', ''),
                        'case_sensitive': str(rule.get('case_sensitive', False)).lower(),
                        'enabled': str(rule.get('enabled', True)).lower(),
                        'priority': rule.get('priority', 0)
                    })

            messagebox.showinfo(
                "Export Complete",
                f"Exported {len(self.working_corrections)} entries to:\n\n{file_path}",
                parent=self.dialog
            )

        except Exception as e:
            messagebox.showerror(
                "Export Error",
                f"Failed to export CSV file:\n\n{str(e)}",
                parent=self.dialog
            )

    def _update_count_label(self):
        """Update the entry count label."""
        if hasattr(self, 'count_label'):
            self.count_label.configure(text=f"{len(self.working_corrections)} entries")

    def _create_button_bar(self, parent) -> dict:
        """Create bottom button bar.

        Args:
            parent: Parent widget

        Returns:
            dict: Result dictionary with 'saved' key
        """
        result = {"saved": False}

        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=X, pady=(10, 0))

        # Save button
        def save_changes():
            # Update manager with all changes
            vocabulary_manager._corrections = self.working_corrections.copy()
            vocabulary_manager._enabled = self.enabled_var.get()
            vocabulary_manager._default_specialty = self.specialty_var.get()

            # Clear pattern cache
            vocabulary_manager.corrector.clear_cache()

            # Save to settings
            vocabulary_manager.save_settings()

            result["saved"] = True
            self.dialog.destroy()

        ttk.Button(
            button_frame,
            text="Save",
            command=save_changes,
            bootstyle="success"
        ).pack(side=RIGHT, padx=(5, 0))

        # Cancel button
        ttk.Button(
            button_frame,
            text="Cancel",
            command=self._on_cancel,
            bootstyle="secondary"
        ).pack(side=RIGHT)

        # Info label
        self.count_label = ttk.Label(
            button_frame,
            text=f"{len(self.working_corrections)} entries",
            foreground="gray"
        )
        self.count_label.pack(side=LEFT)

        return result

    def _on_cancel(self):
        """Handle cancel/close."""
        self.dialog.destroy()


class VocabularyEntryDialog:
    """Dialog for editing a single vocabulary entry."""

    def __init__(
        self,
        parent,
        categories: list,
        specialties: list,
        find_text: str = "",
        replacement: str = "",
        category: str = "general",
        specialty: str = "general",
        case_sensitive: bool = False,
        enabled: bool = True,
        priority: int = 0
    ):
        """Initialize the entry edit dialog.

        Args:
            parent: Parent window
            categories: List of available categories
            specialties: List of available specialties
            find_text: Current find text (for editing)
            replacement: Current replacement text
            category: Current category
            specialty: Current specialty
            case_sensitive: Current case sensitivity setting
            enabled: Current enabled state
            priority: Current priority value
        """
        self.parent = parent
        self.categories = categories
        self.specialties = specialties
        self.find_text = find_text
        self.replacement = replacement
        self.category = category
        self.specialty = specialty or "general"
        self.case_sensitive = case_sensitive
        self.enabled = enabled
        self.priority = priority
        self.is_edit = bool(find_text)

    def show(self) -> Optional[dict]:
        """Show the dialog and return the result.

        Returns:
            dict with entry data or None if cancelled
        """
        # Create dialog
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Edit Vocabulary Entry" if self.is_edit else "Add Vocabulary Entry")
        self.dialog.geometry("500x450")
        self.dialog.resizable(True, True)
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - 500) // 2
        y = (self.dialog.winfo_screenheight() - 450) // 2
        self.dialog.geometry(f"500x450+{x}+{y}")

        # Grab focus after window is visible
        self.dialog.deiconify()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass  # Window not viewable yet

        # Create form
        form_frame = ttk.Frame(self.dialog, padding=20)
        form_frame.pack(fill=BOTH, expand=True)

        # Find text
        ttk.Label(form_frame, text="Find Text:", font=("", 10, "bold")).pack(anchor=W)
        ttk.Label(
            form_frame,
            text="The text to search for (e.g., 'lipidor', 'dr smith')",
            foreground="gray"
        ).pack(anchor=W)

        self.find_entry = ttk.Entry(form_frame, width=50)
        self.find_entry.pack(fill=X, pady=(5, 15))
        if self.find_text:
            self.find_entry.insert(0, self.find_text)

        # Replacement text
        ttk.Label(form_frame, text="Replace With:", font=("", 10, "bold")).pack(anchor=W)
        ttk.Label(
            form_frame,
            text="The correct text to replace with (e.g., 'Lipitor', 'Dr. Smith')",
            foreground="gray"
        ).pack(anchor=W)

        self.replace_entry = ttk.Entry(form_frame, width=50)
        self.replace_entry.pack(fill=X, pady=(5, 15))
        if self.replacement:
            self.replace_entry.insert(0, self.replacement)

        # Category and Specialty row
        row_frame = ttk.Frame(form_frame)
        row_frame.pack(fill=X, pady=(0, 15))

        # Category
        cat_frame = ttk.Frame(row_frame)
        cat_frame.pack(side=LEFT, fill=X, expand=True)

        ttk.Label(cat_frame, text="Category:", font=("", 10, "bold")).pack(anchor=W)
        self.category_var = tk.StringVar(value=self.category)
        category_combo = ttk.Combobox(
            cat_frame,
            textvariable=self.category_var,
            values=self.categories,
            state="readonly",
            width=15
        )
        category_combo.pack(anchor=W, pady=(5, 0))

        # Specialty
        spec_frame = ttk.Frame(row_frame)
        spec_frame.pack(side=LEFT, fill=X, expand=True, padx=(20, 0))

        ttk.Label(spec_frame, text="Specialty:", font=("", 10, "bold")).pack(anchor=W)
        self.specialty_var = tk.StringVar(value=self.specialty)
        specialty_combo = ttk.Combobox(
            spec_frame,
            textvariable=self.specialty_var,
            values=self.specialties,
            state="readonly",
            width=15
        )
        specialty_combo.pack(anchor=W, pady=(5, 0))

        # Priority
        pri_frame = ttk.Frame(row_frame)
        pri_frame.pack(side=LEFT, fill=X, padx=(20, 0))

        ttk.Label(pri_frame, text="Priority:", font=("", 10, "bold")).pack(anchor=W)
        self.priority_var = tk.IntVar(value=self.priority)
        priority_spin = ttk.Spinbox(
            pri_frame,
            from_=0,
            to=100,
            textvariable=self.priority_var,
            width=8
        )
        priority_spin.pack(anchor=W, pady=(5, 0))

        # Options row
        options_frame = ttk.Frame(form_frame)
        options_frame.pack(fill=X, pady=(0, 15))

        # Case sensitive
        self.case_var = tk.BooleanVar(value=self.case_sensitive)
        ttk.Checkbutton(
            options_frame,
            text="Case sensitive matching",
            variable=self.case_var
        ).pack(side=LEFT)

        # Enabled
        self.enabled_var = tk.BooleanVar(value=self.enabled)
        ttk.Checkbutton(
            options_frame,
            text="Enabled",
            variable=self.enabled_var
        ).pack(side=LEFT, padx=(30, 0))

        # Result
        result = {}

        # Buttons
        button_frame = ttk.Frame(form_frame)
        button_frame.pack(fill=X, pady=(20, 0))

        def save():
            find = self.find_entry.get().strip()
            replace = self.replace_entry.get().strip()

            if not find:
                messagebox.showwarning(
                    "Invalid Input",
                    "Please enter the text to find.",
                    parent=self.dialog
                )
                return

            if not replace:
                messagebox.showwarning(
                    "Invalid Input",
                    "Please enter the replacement text.",
                    parent=self.dialog
                )
                return

            result["find_text"] = find
            result["replacement"] = replace
            result["category"] = self.category_var.get()
            result["specialty"] = self.specialty_var.get()
            result["case_sensitive"] = self.case_var.get()
            result["enabled"] = self.enabled_var.get()
            result["priority"] = self.priority_var.get()

            self.dialog.destroy()

        ttk.Button(
            button_frame,
            text="Save",
            command=save,
            bootstyle="success"
        ).pack(side=RIGHT, padx=(5, 0))

        ttk.Button(
            button_frame,
            text="Cancel",
            command=self.dialog.destroy,
            bootstyle="secondary"
        ).pack(side=RIGHT)

        # Focus on find entry
        self.find_entry.focus_set()

        # Wait for dialog
        self.dialog.wait_window()

        return result if result else None
