"""
Undo History Dialog Module

Displays the undo history for text widgets and allows
undoing to a specific point in history.
"""

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from typing import TYPE_CHECKING, Optional, Callable

from ui.dialogs.dialog_utils import create_toplevel_dialog
from ui.undo_history_manager import get_undo_history_manager, UndoHistoryEntry

if TYPE_CHECKING:
    from core.app import MedicalDictationApp


def show_undo_history_dialog(
    parent: 'MedicalDictationApp',
    active_widget_name: str,
    undo_callback: Callable[[], bool]
) -> None:
    """Show the undo history dialog.

    Args:
        parent: Parent application window
        active_widget_name: Name of the currently active text widget
        undo_callback: Callback to perform a single undo operation
                      Returns True if undo was successful, False otherwise
    """
    history_manager = get_undo_history_manager()
    history = history_manager.get_history(active_widget_name)

    # Create dialog
    dialog = create_toplevel_dialog(parent, "Undo History", "500x400")

    # Main content frame
    main_frame = ttk.Frame(dialog, padding=15)
    main_frame.pack(fill=BOTH, expand=True)

    # Header
    header_frame = ttk.Frame(main_frame)
    header_frame.pack(fill=X, pady=(0, 10))

    widget_display_names = {
        "transcript": "Transcript",
        "soap": "SOAP Note",
        "referral": "Referral",
        "letter": "Letter",
        "context": "Context",
    }
    display_name = widget_display_names.get(active_widget_name, active_widget_name.title())

    ttk.Label(
        header_frame,
        text=f"Undo History - {display_name}",
        font=("Segoe UI", 12, "bold")
    ).pack(side=LEFT)

    entry_count = len(history)
    ttk.Label(
        header_frame,
        text=f"({entry_count} {'entry' if entry_count == 1 else 'entries'})",
        foreground="gray"
    ).pack(side=LEFT, padx=(10, 0))

    # History listbox with scrollbar
    list_frame = ttk.Frame(main_frame)
    list_frame.pack(fill=BOTH, expand=True, pady=(0, 10))

    scrollbar = ttk.Scrollbar(list_frame)
    scrollbar.pack(side=RIGHT, fill=Y)

    listbox = tk.Listbox(
        list_frame,
        yscrollcommand=scrollbar.set,
        font=("Consolas", 10),
        selectmode=SINGLE,
        activestyle="dotbox"
    )
    listbox.pack(side=LEFT, fill=BOTH, expand=True)
    scrollbar.config(command=listbox.yview)

    # Populate listbox
    if history:
        for i, entry in enumerate(history):
            display_text = entry.get_display_text()
            listbox.insert(END, f"  {i + 1}. {display_text}")
    else:
        listbox.insert(END, "  No undo history available")
        listbox.config(state=DISABLED)

    # Info label
    info_label = ttk.Label(
        main_frame,
        text="Select an entry and click 'Undo to Here' to undo all changes up to that point.",
        foreground="gray",
        wraplength=450
    )
    info_label.pack(fill=X, pady=(0, 10))

    # Button frame
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=X)

    def on_undo_to_here():
        """Undo all changes up to the selected entry."""
        selection = listbox.curselection()
        if not selection:
            return

        selected_index = selection[0]
        # Number of undos needed (selected_index + 1 because index 0 = 1 undo)
        undo_count = selected_index + 1

        success_count = 0
        for _ in range(undo_count):
            try:
                if undo_callback():
                    success_count += 1
                else:
                    break
            except Exception:
                break

        # Update status
        if success_count > 0:
            if hasattr(parent, 'status_manager'):
                parent.status_manager.info(f"Undone {success_count} operation(s)")

        dialog.destroy()

    def on_clear_history():
        """Clear all history for this widget."""
        history_manager.clear_history(active_widget_name)
        listbox.delete(0, END)
        listbox.insert(END, "  History cleared")
        listbox.config(state=DISABLED)
        undo_to_btn.config(state=DISABLED)
        clear_btn.config(state=DISABLED)

    # Undo to Here button
    undo_to_btn = ttk.Button(
        button_frame,
        text="Undo to Here",
        command=on_undo_to_here,
        bootstyle="primary",
        width=15
    )
    undo_to_btn.pack(side=LEFT)

    # Clear History button
    clear_btn = ttk.Button(
        button_frame,
        text="Clear History",
        command=on_clear_history,
        bootstyle="secondary",
        width=15
    )
    clear_btn.pack(side=LEFT, padx=(10, 0))

    # Close button
    close_btn = ttk.Button(
        button_frame,
        text="Close",
        command=dialog.destroy,
        bootstyle="secondary",
        width=10
    )
    close_btn.pack(side=RIGHT)

    # Disable buttons if no history
    if not history:
        undo_to_btn.config(state=DISABLED)
        clear_btn.config(state=DISABLED)

    # Select first item by default
    if history:
        listbox.selection_set(0)

    # Handle double-click to undo
    def on_double_click(event):
        if history:
            on_undo_to_here()

    listbox.bind("<Double-1>", on_double_click)

    # Handle Escape to close
    dialog.bind("<Escape>", lambda e: dialog.destroy())

    # Focus the listbox
    listbox.focus_set()
