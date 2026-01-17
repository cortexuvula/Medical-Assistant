"""
Manage Recipients Dialog for address book management.

Allows users to view, add, edit, and delete saved recipients/contacts
for use in referral generation.
"""

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, X, Y, HORIZONTAL, VERTICAL, LEFT, RIGHT, CENTER, W
from typing import Dict, List, Optional, Any
from tkinter import messagebox

from managers.recipient_manager import get_recipient_manager
from utils.structured_logging import get_logger

logger = get_logger(__name__)


# Constants
RECIPIENT_TYPES = [
    ("All", None),
    ("Specialist", "specialist"),
    ("GP Back-referral", "gp_backreferral"),
    ("Hospital/ER", "hospital"),
    ("Diagnostic", "diagnostic")
]

TITLE_OPTIONS = ["", "Dr.", "Prof.", "Mr.", "Mrs.", "Ms."]

COMMON_SPECIALTIES = [
    "Cardiology", "Dermatology", "Endocrinology", "Gastroenterology",
    "General Practice", "Hematology", "Infectious Disease", "Internal Medicine",
    "Nephrology", "Neurology", "Oncology", "Ophthalmology", "Orthopedics",
    "Otolaryngology", "Pathology", "Pediatrics", "Physical Medicine",
    "Psychiatry", "Pulmonology", "Radiology", "Rheumatology", "Surgery", "Urology"
]


class ManageRecipientsDialog:
    """Dialog for managing saved recipients in the address book."""

    def __init__(self, parent):
        """Initialize the manage recipients dialog.

        Args:
            parent: Parent window
        """
        self.parent = parent
        self.dialog = None
        self.recipient_manager = get_recipient_manager()
        self.all_recipients = []

    def show(self) -> None:
        """Show the dialog."""
        # Create dialog window
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Manage Address Book")

        # Get screen dimensions
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()

        # Set dialog size
        dialog_width = min(1000, int(screen_width * 0.8))
        dialog_height = min(700, int(screen_height * 0.8))

        self.dialog.geometry(f"{dialog_width}x{dialog_height}")
        self.dialog.minsize(800, 500)
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.update_idletasks()
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

        # Grab focus after window is visible
        self.dialog.deiconify()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass  # Window not viewable yet

        # Create main container
        main_container = ttk.Frame(self.dialog)
        main_container.pack(fill=BOTH, expand=True, padx=15, pady=15)

        # Title
        title_label = ttk.Label(
            main_container,
            text="Address Book",
            font=("Segoe UI", 14, "bold")
        )
        title_label.pack(pady=(0, 10))

        # Create toolbar
        self._create_toolbar(main_container)

        # Create recipients list
        self._create_recipients_list(main_container)

        # Create selection info and action buttons
        self._create_button_bar(main_container)

        # Handle dialog close
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

        # Focus on dialog
        self.dialog.focus_set()

        # Load initial data
        self._load_recipients()

        # Wait for dialog to close
        self.dialog.wait_window()

    def _create_toolbar(self, parent):
        """Create toolbar with search, filter, and add button.

        Args:
            parent: Parent widget
        """
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=X, pady=(0, 10))

        # Add button
        ttk.Button(
            toolbar,
            text="+ Add Contact",
            command=self._add_recipient,
            bootstyle="success"
        ).pack(side=LEFT, padx=(0, 15))

        # Search
        ttk.Label(toolbar, text="Search:").pack(side=LEFT, padx=(0, 5))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search)
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=25)
        search_entry.pack(side=LEFT, padx=(0, 15))

        # Type filter
        ttk.Label(toolbar, text="Type:").pack(side=LEFT, padx=(0, 5))

        self.type_filter_var = tk.StringVar(value="All")
        type_combo = ttk.Combobox(
            toolbar,
            textvariable=self.type_filter_var,
            values=[t[0] for t in RECIPIENT_TYPES],
            state="readonly",
            width=15
        )
        type_combo.pack(side=LEFT)
        type_combo.bind("<<ComboboxSelected>>", self._on_filter_change)

        # Count label
        self.count_var = tk.StringVar(value="0 contacts")
        ttk.Label(
            toolbar,
            textvariable=self.count_var,
            foreground="gray"
        ).pack(side=RIGHT)

    def _create_recipients_list(self, parent):
        """Create the treeview list of recipients.

        Args:
            parent: Parent widget
        """
        # Create frame with scrollbar
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=BOTH, expand=True, pady=(0, 10))

        # Create treeview
        columns = ("specialty", "facility", "phone", "fax", "type", "favorite")
        self.tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="tree headings",
            height=15
        )

        # Configure columns
        self.tree.heading("#0", text="Name", anchor=W)
        self.tree.heading("specialty", text="Specialty", anchor=W)
        self.tree.heading("facility", text="Facility", anchor=W)
        self.tree.heading("phone", text="Phone", anchor=W)
        self.tree.heading("fax", text="Fax", anchor=W)
        self.tree.heading("type", text="Type", anchor=W)
        self.tree.heading("favorite", text="Fav", anchor=CENTER)

        self.tree.column("#0", width=180, minwidth=150)
        self.tree.column("specialty", width=150, minwidth=100)
        self.tree.column("facility", width=180, minwidth=120)
        self.tree.column("phone", width=110, minwidth=90)
        self.tree.column("fax", width=110, minwidth=90)
        self.tree.column("type", width=100, minwidth=80)
        self.tree.column("favorite", width=50, minwidth=40)

        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(list_frame, orient=VERTICAL, command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(list_frame, orient=HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Pack widgets using grid for better scrollbar placement
        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")

        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        # Bind events
        self.tree.bind("<Double-Button-1>", lambda e: self._edit_selected())
        self.tree.bind("<<TreeviewSelect>>", self._on_selection_change)
        self.tree.bind("<Button-3>", self._show_context_menu)

        # Create context menu
        self.context_menu = tk.Menu(self.tree, tearoff=0)
        self.context_menu.add_command(label="Edit", command=self._edit_selected)
        self.context_menu.add_command(label="Delete", command=self._delete_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Toggle Favorite", command=self._toggle_favorite)

    def _create_button_bar(self, parent):
        """Create bottom button bar with actions.

        Args:
            parent: Parent widget
        """
        # Selection info frame
        info_frame = ttk.Frame(parent)
        info_frame.pack(fill=X, pady=(0, 10))

        self.selection_var = tk.StringVar(value="No contact selected")
        ttk.Label(
            info_frame,
            textvariable=self.selection_var,
            foreground="gray"
        ).pack(side=LEFT)

        # Button frame
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=X)

        # Left side - action buttons
        action_frame = ttk.Frame(button_frame)
        action_frame.pack(side=LEFT)

        self.edit_btn = ttk.Button(
            action_frame,
            text="Edit",
            command=self._edit_selected,
            state=tk.DISABLED
        )
        self.edit_btn.pack(side=LEFT, padx=(0, 5))

        self.delete_btn = ttk.Button(
            action_frame,
            text="Delete",
            command=self._delete_selected,
            bootstyle="danger",
            state=tk.DISABLED
        )
        self.delete_btn.pack(side=LEFT, padx=(0, 5))

        self.favorite_btn = ttk.Button(
            action_frame,
            text="Toggle Favorite",
            command=self._toggle_favorite,
            bootstyle="warning",
            state=tk.DISABLED
        )
        self.favorite_btn.pack(side=LEFT)

        # Right side - close button
        ttk.Button(
            button_frame,
            text="Close",
            command=self._on_close,
            bootstyle="secondary"
        ).pack(side=RIGHT)

    def _load_recipients(self):
        """Load all recipients from database."""
        self.all_recipients = self.recipient_manager.get_all_recipients()
        self._populate_tree()

    def _populate_tree(self):
        """Populate the tree with filtered recipients.

        Uses FTS (full-text search) when a search term is present,
        falls back to loading all recipients when no search.
        """
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Get filter values
        search_term = self.search_var.get().strip()
        type_filter = self.type_filter_var.get()

        # Get type value from display name
        type_value = None
        for display, value in RECIPIENT_TYPES:
            if display == type_filter:
                type_value = value
                break

        # Get recipients - use FTS search when there's a search term
        if search_term:
            # Use database FTS search for better performance
            recipients = self.recipient_manager.search_recipients(search_term)
        else:
            # No search - use cached all_recipients or fetch by type
            if type_value:
                recipients = [r for r in self.all_recipients if r.get("recipient_type") == type_value]
            else:
                recipients = self.all_recipients

        # Filter and add recipients
        count = 0
        for recipient in recipients:
            # Apply type filter to search results as well
            if type_value and recipient.get("recipient_type") != type_value:
                continue

            # Get display values
            name = recipient.get("name", "Unknown")
            specialty = recipient.get("specialty", "")
            facility = recipient.get("facility", "")
            phone = recipient.get("phone", "")
            fax = recipient.get("fax", "")
            rtype = recipient.get("recipient_type", "specialist")
            is_favorite = recipient.get("is_favorite", False)

            # Format type for display
            type_display = rtype.replace("_", " ").title() if rtype else ""

            # Insert into tree
            self.tree.insert(
                "", END,
                text=name,
                values=(specialty, facility, phone, fax, type_display, "★" if is_favorite else ""),
                tags=(str(recipient.get("id")),)
            )
            count += 1

        # Update count
        self.count_var.set(f"{count} contact{'s' if count != 1 else ''}")

    def _on_search(self, *args):
        """Handle search input change."""
        self._populate_tree()

    def _on_filter_change(self, event=None):
        """Handle type filter change."""
        self._populate_tree()

    def _on_selection_change(self, event=None):
        """Handle selection change in tree."""
        selection = self.tree.selection()
        if selection:
            item = selection[0]
            name = self.tree.item(item, "text")
            values = self.tree.item(item, "values")
            specialty = values[0] if values else ""
            self.selection_var.set(f"Selected: {name}" + (f" - {specialty}" if specialty else ""))

            # Enable buttons
            self.edit_btn.config(state=tk.NORMAL)
            self.delete_btn.config(state=tk.NORMAL)
            self.favorite_btn.config(state=tk.NORMAL)
        else:
            self.selection_var.set("No contact selected")
            self.edit_btn.config(state=tk.DISABLED)
            self.delete_btn.config(state=tk.DISABLED)
            self.favorite_btn.config(state=tk.DISABLED)

    def _show_context_menu(self, event):
        """Show context menu on right-click."""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def _get_selected_recipient_id(self) -> Optional[int]:
        """Get the ID of the currently selected recipient."""
        selection = self.tree.selection()
        if not selection:
            return None

        item = selection[0]
        tags = self.tree.item(item, "tags")
        if tags:
            try:
                return int(tags[0])
            except (ValueError, IndexError):
                pass
        return None

    def _get_selected_recipient(self) -> Optional[Dict[str, Any]]:
        """Get the full recipient data for the selected item."""
        recipient_id = self._get_selected_recipient_id()
        if recipient_id:
            return self.recipient_manager.get_recipient(recipient_id)
        return None

    def _add_recipient(self):
        """Add a new recipient."""
        dialog = RecipientEditDialog(self.dialog)
        result = dialog.show()

        if result:
            # Save to database
            recipient_id = self.recipient_manager.save_recipient(result)
            if recipient_id:
                # Reload and refresh
                self._load_recipients()
                messagebox.showinfo(
                    "Contact Added",
                    f"Contact '{result.get('name', 'Unknown')}' has been added.",
                    parent=self.dialog
                )
            else:
                messagebox.showerror(
                    "Error",
                    "Failed to save contact. Please try again.",
                    parent=self.dialog
                )

    def _edit_selected(self):
        """Edit the selected recipient."""
        recipient = self._get_selected_recipient()
        if not recipient:
            return

        dialog = RecipientEditDialog(self.dialog, recipient)
        result = dialog.show()

        if result:
            # Update in database
            success = self.recipient_manager.update_recipient(recipient["id"], result)
            if success:
                # Reload and refresh
                self._load_recipients()
                messagebox.showinfo(
                    "Contact Updated",
                    f"Contact '{result.get('name', 'Unknown')}' has been updated.",
                    parent=self.dialog
                )
            else:
                messagebox.showerror(
                    "Error",
                    "Failed to update contact. Please try again.",
                    parent=self.dialog
                )

    def _delete_selected(self):
        """Delete the selected recipient."""
        recipient = self._get_selected_recipient()
        if not recipient:
            return

        name = recipient.get("name", "Unknown")

        if messagebox.askyesno(
            "Delete Contact",
            f"Are you sure you want to delete:\n\n'{name}'?\n\nThis cannot be undone.",
            parent=self.dialog
        ):
            success = self.recipient_manager.delete_recipient(recipient["id"])
            if success:
                self._load_recipients()
                messagebox.showinfo(
                    "Contact Deleted",
                    f"Contact '{name}' has been deleted.",
                    parent=self.dialog
                )
            else:
                messagebox.showerror(
                    "Error",
                    "Failed to delete contact. Please try again.",
                    parent=self.dialog
                )

    def _toggle_favorite(self):
        """Toggle favorite status of selected recipient."""
        recipient_id = self._get_selected_recipient_id()
        if not recipient_id:
            return

        success = self.recipient_manager.toggle_favorite(recipient_id)
        if success:
            self._load_recipients()

    def _on_close(self):
        """Handle dialog close."""
        self.dialog.destroy()


class RecipientEditDialog:
    """Dialog for adding or editing a recipient."""

    def __init__(self, parent, recipient: Optional[Dict[str, Any]] = None):
        """Initialize the recipient edit dialog.

        Args:
            parent: Parent window
            recipient: Existing recipient data (for editing), or None for new
        """
        self.parent = parent
        self.recipient = recipient or {}
        self.is_edit = bool(recipient)
        self.result = None

    def show(self) -> Optional[Dict[str, Any]]:
        """Show the dialog and return the result.

        Returns:
            dict: Recipient data if saved, or None if cancelled
        """
        # Create dialog
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Edit Contact" if self.is_edit else "Add Contact")

        # Get screen dimensions
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()

        # Set dialog size
        dialog_width = min(550, int(screen_width * 0.5))
        dialog_height = min(650, int(screen_height * 0.8))

        self.dialog.geometry(f"{dialog_width}x{dialog_height}")
        self.dialog.minsize(450, 550)
        self.dialog.resizable(True, True)
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.update_idletasks()
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

        # Grab focus after window is visible
        self.dialog.deiconify()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass  # Window not viewable yet

        # Create scrollable frame
        canvas = tk.Canvas(self.dialog, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.dialog, orient=VERTICAL, command=canvas.yview)
        self.form_frame = ttk.Frame(canvas, padding=20)

        self.form_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.form_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack canvas and scrollbar
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        # Bind mousewheel
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Create form sections
        self._create_basic_info_section()
        self._create_contact_section()
        self._create_location_section()
        self._create_professional_section()
        self._create_notes_section()
        self._create_buttons()

        # Handle dialog close
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)

        # Unbind mousewheel when dialog closes
        def cleanup():
            canvas.unbind_all("<MouseWheel>")
        self.dialog.bind("<Destroy>", lambda e: cleanup())

        # Wait for dialog
        self.dialog.wait_window()

        return self.result

    def _create_section_label(self, text: str):
        """Create a section header label."""
        ttk.Label(
            self.form_frame,
            text=text,
            font=("Segoe UI", 10, "bold")
        ).pack(anchor=W, pady=(15, 5))

        ttk.Separator(self.form_frame, orient=HORIZONTAL).pack(fill=X, pady=(0, 10))

    def _create_field(self, label: str, field_name: str, width: int = 40,
                      options: List[str] = None, readonly: bool = False) -> tk.StringVar:
        """Create a labeled input field.

        Args:
            label: Field label text
            field_name: Key in recipient dict
            width: Entry width
            options: List of options for combobox (None for entry)
            readonly: Whether combobox is readonly

        Returns:
            StringVar for the field
        """
        frame = ttk.Frame(self.form_frame)
        frame.pack(fill=X, pady=2)

        ttk.Label(frame, text=label, width=15, anchor=W).pack(side=LEFT)

        var = tk.StringVar(value=str(self.recipient.get(field_name, "") or ""))

        if options:
            widget = ttk.Combobox(
                frame,
                textvariable=var,
                values=options,
                width=width,
                state="readonly" if readonly else "normal"
            )
        else:
            widget = ttk.Entry(frame, textvariable=var, width=width)

        widget.pack(side=LEFT, fill=X, expand=True)

        return var

    def _create_basic_info_section(self):
        """Create basic information section."""
        self._create_section_label("Basic Information")

        self.title_var = self._create_field("Title:", "title", options=TITLE_OPTIONS)
        self.first_name_var = self._create_field("First Name:", "first_name")
        self.last_name_var = self._create_field("Last Name:", "last_name")
        self.specialty_var = self._create_field("Specialty:", "specialty", options=COMMON_SPECIALTIES)

        # Type dropdown
        frame = ttk.Frame(self.form_frame)
        frame.pack(fill=X, pady=2)
        ttk.Label(frame, text="Type:", width=15, anchor=W).pack(side=LEFT)

        current_type = self.recipient.get("recipient_type", "specialist")
        type_display = "Specialist"
        for display, value in RECIPIENT_TYPES[1:]:  # Skip "All"
            if value == current_type:
                type_display = display
                break

        self.type_var = tk.StringVar(value=type_display)
        type_combo = ttk.Combobox(
            frame,
            textvariable=self.type_var,
            values=[t[0] for t in RECIPIENT_TYPES[1:]],  # Skip "All"
            state="readonly",
            width=40
        )
        type_combo.pack(side=LEFT, fill=X, expand=True)

    def _create_contact_section(self):
        """Create contact information section."""
        self._create_section_label("Contact Information")

        self.phone_var = self._create_field("Phone:", "phone")
        self.fax_var = self._create_field("Fax:", "fax")
        self.email_var = self._create_field("Email:", "email")

    def _create_location_section(self):
        """Create location section."""
        self._create_section_label("Location")

        self.facility_var = self._create_field("Facility:", "facility")
        self.address_var = self._create_field("Address:", "office_address")
        self.city_var = self._create_field("City:", "city")
        self.province_var = self._create_field("Province:", "province")
        self.postal_var = self._create_field("Postal Code:", "postal_code")

    def _create_professional_section(self):
        """Create professional IDs section."""
        self._create_section_label("Professional IDs")

        self.practitioner_var = self._create_field("Practitioner #:", "practitioner_number")
        self.payee_var = self._create_field("Payee #:", "payee_number")

    def _create_notes_section(self):
        """Create notes section."""
        self._create_section_label("Notes")

        self.notes_text = tk.Text(self.form_frame, height=4, wrap=tk.WORD)
        self.notes_text.pack(fill=X, pady=(0, 10))

        if self.recipient.get("notes"):
            self.notes_text.insert("1.0", self.recipient["notes"])

    def _create_buttons(self):
        """Create button bar."""
        button_frame = ttk.Frame(self.form_frame)
        button_frame.pack(fill=X, pady=(20, 0))

        ttk.Button(
            button_frame,
            text="Save",
            command=self._on_save,
            bootstyle="success"
        ).pack(side=RIGHT, padx=(5, 0))

        ttk.Button(
            button_frame,
            text="Cancel",
            command=self._on_cancel,
            bootstyle="secondary"
        ).pack(side=RIGHT)

    def _on_save(self):
        """Handle save button click."""
        # Validate
        first_name = self.first_name_var.get().strip()
        last_name = self.last_name_var.get().strip()
        specialty = self.specialty_var.get().strip()

        if not first_name and not last_name:
            messagebox.showwarning(
                "Validation Error",
                "Please enter at least a first name or last name.",
                parent=self.dialog
            )
            return

        # Build name from components
        name_parts = []
        title = self.title_var.get().strip()
        if title:
            name_parts.append(title)
        if first_name:
            name_parts.append(first_name)
        if last_name:
            name_parts.append(last_name)
        name = " ".join(name_parts)

        # Get type value from display
        type_display = self.type_var.get()
        type_value = "specialist"
        for display, value in RECIPIENT_TYPES[1:]:
            if display == type_display:
                type_value = value
                break

        # Build address from components
        address_parts = []
        office_address = self.address_var.get().strip()
        city = self.city_var.get().strip()
        province = self.province_var.get().strip()
        postal = self.postal_var.get().strip()

        if office_address:
            address_parts.append(office_address)
        if city:
            address_parts.append(city)
        if province:
            address_parts.append(province)
        if postal:
            address_parts.append(postal)
        address = ", ".join(address_parts) if address_parts else ""

        # Build result
        self.result = {
            "name": name,
            "first_name": first_name,
            "last_name": last_name,
            "title": title,
            "specialty": specialty,
            "recipient_type": type_value,
            "phone": self.phone_var.get().strip(),
            "fax": self.fax_var.get().strip(),
            "email": self.email_var.get().strip(),
            "facility": self.facility_var.get().strip(),
            "office_address": office_address,
            "city": city,
            "province": province,
            "postal_code": postal,
            "address": address,
            "practitioner_number": self.practitioner_var.get().strip(),
            "payee_number": self.payee_var.get().strip(),
            "notes": self.notes_text.get("1.0", "end-1c").strip()
        }

        self.dialog.destroy()

    def _on_cancel(self):
        """Handle cancel button click."""
        self.result = None
        self.dialog.destroy()
