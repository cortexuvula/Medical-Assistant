"""
Canned Responses Dialog for managing translation quick responses.

Allows users to add, edit, and delete canned responses for the translation dialog.
"""

import tkinter as tk
from ui.scaling_utils import ui_scaler
import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, X, Y, LEFT, RIGHT, CENTER, W
from typing import Dict, List, Tuple
from utils.structured_logging import get_logger

logger = get_logger(__name__)
from tkinter import messagebox

from settings.settings_manager import settings_manager
from ui.tooltip import ToolTip


class CannedResponsesDialog:
    """Dialog for managing canned responses in the translation assistant."""
    
    def __init__(self, parent):
        """Initialize the canned responses dialog.
        
        Args:
            parent: Parent window
        """
        self.parent = parent
        self.dialog = None
        # Using module-level logger
        
        # Load current settings
        self.canned_settings = settings_manager.get("translation_canned_responses", {})
        self.categories = self.canned_settings.get("categories", [])
        self.responses = self.canned_settings.get("responses", {})
        
        # Make a working copy
        self.working_categories = self.categories.copy()
        self.working_responses = self.responses.copy()
        
    def show(self) -> bool:
        """Show the dialog and return True if changes were saved.
        
        Returns:
            bool: True if user saved changes, False if cancelled
        """
        # Create dialog window
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Manage Quick Responses")
        self.dialog_width, dialog_height = ui_scaler.get_dialog_size(1000, 700)
        self.dialog.geometry(f"{self.dialog_width}x{dialog_height}")
        self.dialog.minsize(900, 600)
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - 1000) // 2
        y = (self.dialog.winfo_screenheight() - 700) // 2
        self.dialog.geometry(f"1000x700+{x}+{y}")

        # Grab focus after window is visible
        self.dialog.deiconify()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass  # Window not viewable yet
        
        # Create main container
        main_container = ttk.Frame(self.dialog)
        main_container.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        # Create toolbar
        self._create_toolbar(main_container)
        
        # Create responses list
        self._create_responses_list(main_container)
        
        # Create button bar
        result = self._create_button_bar(main_container)
        
        # Handle dialog close
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
        # Focus on dialog
        self.dialog.focus_set()
        
        # Wait for dialog to close
        self.dialog.wait_window()
        
        return result.get("saved", False)
    
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
            text="➕ Add Response",
            command=self._add_response,
            bootstyle="success"
        ).pack(side=LEFT, padx=(0, 5))
        
        # Category filter
        ttk.Label(toolbar, text="Filter by category:").pack(side=LEFT, padx=(20, 5))
        
        self.filter_var = tk.StringVar(value="All")
        filter_combo = ttk.Combobox(
            toolbar,
            textvariable=self.filter_var,
            values=["All"] + self.working_categories,
            state="readonly",
            width=15
        )
        filter_combo.pack(side=LEFT)
        filter_combo.bind("<<ComboboxSelected>>", self._on_filter_change)
        
        # Reset button
        ttk.Button(
            toolbar,
            text="Reset to Defaults",
            command=self._reset_to_defaults,
            bootstyle="warning"
        ).pack(side=RIGHT)
    
    def _create_responses_list(self, parent):
        """Create the list of responses.
        
        Args:
            parent: Parent widget
        """
        # Create frame with scrollbar
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=BOTH, expand=True, pady=(0, 10))
        
        # Create treeview
        columns = ("category", "actions")
        self.tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="tree headings",
            height=15
        )
        
        # Configure columns
        self.tree.heading("#0", text="Response Text", anchor=W)
        self.tree.heading("category", text="Category", anchor=W)
        self.tree.heading("actions", text="Actions", anchor=CENTER)
        
        self.tree.column("#0", width=500, minwidth=400)
        self.tree.column("category", width=200, minwidth=150)
        self.tree.column("actions", width=250, minwidth=200)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack widgets
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        # Populate tree
        self._populate_tree()
        
        # Bind double-click to edit
        self.tree.bind("<Double-Button-1>", lambda e: self._edit_selected())
        
        # Bind selection change
        self.tree.bind("<<TreeviewSelect>>", self._on_selection_change)
    
    def _populate_tree(self):
        """Populate the tree with responses."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Get filter
        filter_category = self.filter_var.get() if hasattr(self, 'filter_var') else "All"
        
        # Add responses
        for response_text, category in sorted(self.working_responses.items()):
            if filter_category == "All" or category == filter_category:
                item = self.tree.insert(
                    "", "end",
                    text=response_text,
                    values=(category, "")
                )
                
                # Create action buttons frame
                self._create_action_buttons(item, response_text)
    
    def _create_action_buttons(self, item, response_text):
        """Create action buttons for a tree item.
        
        Note: Treeview doesn't support embedded widgets well,
        so we'll use context menu instead.
        """
        # Tag items as editable
        self.tree.item(item, tags=("editable",))
        
        # Create context menu
        if not hasattr(self, 'context_menu'):
            self.context_menu = tk.Menu(self.tree, tearoff=0)
            self.context_menu.add_command(label="Edit", command=self._edit_selected)
            self.context_menu.add_command(label="Delete", command=self._delete_selected)
            
            # Bind right-click
            self.tree.bind("<Button-3>", self._show_context_menu)
    
    def _show_context_menu(self, event):
        """Show context menu on right-click."""
        # Select item under cursor
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
    
    def _on_filter_change(self, event=None):
        """Handle filter change."""
        self._populate_tree()
    
    def _on_selection_change(self, event=None):
        """Handle selection change in tree."""
        # Could be used to enable/disable buttons
        pass
    
    def _add_response(self):
        """Add a new response."""
        dialog = ResponseEditDialog(self.dialog, self.working_categories)
        result = dialog.show()
        
        if result:
            response_text = result["text"]
            category = result["category"]
            
            # Add to working copy
            self.working_responses[response_text] = category
            
            # Refresh tree
            self._populate_tree()
    
    def _edit_selected(self):
        """Edit the selected response."""
        selection = self.tree.selection()
        if not selection:
            return
        
        item = selection[0]
        response_text = self.tree.item(item, "text")
        category = self.working_responses.get(response_text, "")
        
        dialog = ResponseEditDialog(
            self.dialog,
            self.working_categories,
            response_text,
            category
        )
        result = dialog.show()
        
        if result:
            # Remove old entry if text changed
            if response_text != result["text"]:
                del self.working_responses[response_text]
            
            # Add new/updated entry
            self.working_responses[result["text"]] = result["category"]
            
            # Refresh tree
            self._populate_tree()
    
    def _delete_selected(self):
        """Delete the selected response."""
        selection = self.tree.selection()
        if not selection:
            return
        
        item = selection[0]
        response_text = self.tree.item(item, "text")
        
        # Confirm deletion
        if messagebox.askyesno(
            "Delete Response",
            f"Are you sure you want to delete:\n\n'{response_text}'?",
            parent=self.dialog
        ):
            # Remove from working copy
            del self.working_responses[response_text]
            
            # Refresh tree
            self._populate_tree()
    
    def _reset_to_defaults(self):
        """Reset responses to defaults."""
        if messagebox.askyesno(
            "Reset to Defaults",
            "This will remove all custom responses and restore the default set.\n\n"
            "Are you sure you want to continue?",
            parent=self.dialog
        ):
            # Get defaults from settings
            default_responses = settings_manager.get_default("translation_canned_responses", {})
            
            self.working_categories = default_responses.get("categories", []).copy()
            self.working_responses = default_responses.get("responses", {}).copy()
            
            # Update filter combo if it exists
            if hasattr(self, 'filter_var'):
                self.filter_var.set("All")
            
            # Refresh tree
            self._populate_tree()
            
            messagebox.showinfo(
                "Reset Complete",
                "Responses have been reset to defaults.",
                parent=self.dialog
            )
    
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
            # Update settings
            self.canned_settings["categories"] = self.working_categories
            self.canned_settings["responses"] = self.working_responses
            settings_manager.set("translation_canned_responses", self.canned_settings)

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
        ttk.Label(
            button_frame,
            text=f"{len(self.working_responses)} responses",
            foreground="gray"
        ).pack(side=LEFT)
        
        return result
    
    def _on_cancel(self):
        """Handle cancel/close."""
        self.dialog.destroy()


class ResponseEditDialog:
    """Dialog for editing a single response."""
    
    def __init__(self, parent, categories: List[str], 
                 response_text: str = "", category: str = ""):
        """Initialize the response edit dialog.
        
        Args:
            parent: Parent window
            categories: List of available categories
            response_text: Current response text (for editing)
            category: Current category (for editing)
        """
        self.parent = parent
        self.categories = categories
        self.response_text = response_text
        self.category = category
        self.is_edit = bool(response_text)
        
    def show(self) -> dict:
        """Show the dialog and return the result.
        
        Returns:
            dict: {"text": str, "category": str} or None if cancelled
        """
        # Create dialog
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Edit Response" if self.is_edit else "Add Response")
        self.dialog_width, dialog_height = ui_scaler.get_dialog_size(600, 400)
        self.dialog.geometry(f"{self.dialog_width}x{dialog_height}")
        self.dialog.resizable(True, True)
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - 600) // 2
        y = (self.dialog.winfo_screenheight() - 400) // 2
        self.dialog.geometry(f"600x400+{x}+{y}")

        # Grab focus after window is visible
        self.dialog.deiconify()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass  # Window not viewable yet
        
        # Create form
        form_frame = ttk.Frame(self.dialog, padding=20)
        form_frame.pack(fill=BOTH, expand=True)
        
        # Response text
        ttk.Label(form_frame, text="Response Text:", font=("", 10, "bold")).pack(anchor=W)
        
        text_frame = ttk.Frame(form_frame)
        text_frame.pack(fill=BOTH, expand=True, pady=(5, 15))
        
        text_scroll = ttk.Scrollbar(text_frame)
        text_scroll.pack(side=RIGHT, fill=Y)
        
        self.text_widget = tk.Text(
            text_frame,
            wrap=WORD,
            height=6,
            yscrollcommand=text_scroll.set
        )
        self.text_widget.pack(fill=BOTH, expand=True)
        text_scroll.config(command=self.text_widget.yview)
        
        # Insert existing text
        if self.response_text:
            self.text_widget.insert("1.0", self.response_text)
        
        # Category selection
        ttk.Label(form_frame, text="Category:", font=("", 10, "bold")).pack(anchor=W)
        
        self.category_var = tk.StringVar(value=self.category or self.categories[0])
        category_combo = ttk.Combobox(
            form_frame,
            textvariable=self.category_var,
            values=self.categories,
            state="readonly",
            width=30
        )
        category_combo.pack(fill=X, pady=(5, 0))
        
        # Result
        result = {"text": None, "category": None}
        
        # Buttons
        button_frame = ttk.Frame(form_frame)
        button_frame.pack(fill=X, pady=(20, 0))
        
        def save():
            text = self.text_widget.get("1.0", "end-1c").strip()
            if not text:
                messagebox.showwarning(
                    "Invalid Input",
                    "Please enter response text.",
                    parent=self.dialog
                )
                return
            
            result["text"] = text
            result["category"] = self.category_var.get()
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
        
        # Focus on text widget
        self.text_widget.focus_set()
        
        # Wait for dialog
        self.dialog.wait_window()
        
        return result if result["text"] else None