"""
Dialog Utilities Module

Common utility functions for creating and managing dialogs.
"""

import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from typing import List, Optional, Callable

from ui.scaling_utils import ui_scaler
from ui.dialogs.model_providers import clear_model_cache


def create_toplevel_dialog(parent: tk.Tk, title: str, geometry: str = "700x500") -> tk.Toplevel:
    """Create a top-level dialog with standard properties.

    Args:
        parent: Parent window
        title: Dialog title
        geometry: Window geometry string (width x height)

    Returns:
        The created top-level window
    """
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.geometry(geometry)
    dialog.transient(parent)

    # Center the dialog on the screen
    dialog.update_idletasks()
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    size = tuple(map(int, geometry.split('x')))
    x = (screen_width // 2) - (size[0] // 2)
    y = (screen_height // 2) - (size[1] // 2)
    dialog.geometry(f"{size[0]}x{size[1]}+{x}+{y}")

    # Grab focus after window is visible
    dialog.deiconify()
    try:
        dialog.grab_set()
    except tk.TclError:
        pass  # Window not viewable yet

    return dialog


def create_model_selector(parent, frame, model_var, provider_name: str,
                          get_models_func: Callable, row: int, column: int = 1):
    """Create a model selection widget with a select button.

    Args:
        parent: Parent window
        frame: Frame to place the widget in
        model_var: tkinter variable to store selected model
        provider_name: Name of the provider (e.g., "OpenAI", "Anthropic")
        get_models_func: Function to call to get available models
        row: Grid row position
        column: Grid column position

    Returns:
        The frame containing the entry and button
    """
    # Create container frame
    container_frame = ttk.Frame(frame)
    container_frame.grid(row=row, column=column, sticky="ew", padx=(10, 0))

    # Create entry field
    entry = ttk.Entry(container_frame, textvariable=model_var)
    entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def select_model():
        # Create progress dialog
        progress_dialog = create_toplevel_dialog(parent, "Fetching Models", "300x100")
        progress_frame = ttk.Frame(progress_dialog, padding=20)
        progress_frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(progress_frame, text=f"Fetching {provider_name} models...").pack(pady=(0, 10))
        progress = ttk.Progressbar(progress_frame, mode="indeterminate")
        progress.pack(fill=tk.X)
        progress.start()
        progress_dialog.update()

        # Fetch models
        models = get_models_func()

        # Close progress dialog
        progress_dialog.destroy()

        if not models:
            messagebox.showerror("Error",
                f"Failed to fetch {provider_name} models. Check your API key and internet connection.")
            return

        # Open model selection dialog with refresh capability
        model_selection = create_model_selection_dialog(parent,
            f"Select {provider_name} Model", models, model_var.get(),
            get_models_func=get_models_func, provider_name=provider_name)
        if model_selection:
            model_var.set(model_selection)

    # Add select button
    select_button = ttk.Button(container_frame, text="Select Model", command=select_model)
    select_button.pack(side=tk.RIGHT, padx=(5, 0))

    return container_frame


def create_model_selection_dialog(parent, title: str, models_list: List[str],
                                   current_selection: str,
                                   get_models_func: Callable = None,
                                   provider_name: str = None) -> Optional[str]:
    """Create a dialog with a scrollable listbox for selecting models.

    Args:
        parent: Parent window
        title: Dialog title
        models_list: List of models to display
        current_selection: Currently selected model
        get_models_func: Optional function to refresh models
        provider_name: Optional provider name for cache clearing

    Returns:
        Selected model or None if cancelled
    """
    dialog = create_toplevel_dialog(parent, title, "700x450")

    # Create a frame for the dialog
    frame = ttk.Frame(dialog, padding=10)
    frame.pack(fill=tk.BOTH, expand=True)

    # Create header frame with label and refresh button
    header_frame = ttk.Frame(frame)
    header_frame.pack(fill=tk.X, pady=(0, 5))

    ttk.Label(header_frame, text="Select a model:").pack(side=tk.LEFT)

    # Add refresh button if get_models_func is provided
    if get_models_func:
        def refresh_models():
            # Clear cache if provider_name is provided
            if provider_name:
                clear_model_cache(provider_name.lower())

            # Show progress
            refresh_btn.config(state="disabled", text="Refreshing...")
            dialog.update()

            # Fetch new models
            new_models = get_models_func()

            # Update listbox
            listbox.delete(0, tk.END)
            for model in new_models:
                listbox.insert(tk.END, model)
                if model == current_selection:
                    listbox.selection_set(listbox.size() - 1)
                    listbox.see(listbox.size() - 1)

            # Update models_list reference
            models_list[:] = new_models

            # Re-enable button
            refresh_btn.config(state="normal", text="Refresh")
            messagebox.showinfo("Refresh Complete", f"Fetched {len(new_models)} models")

        refresh_btn = ttk.Button(header_frame, text="Refresh", command=refresh_models)
        refresh_btn.pack(side=tk.RIGHT, padx=(10, 0))

    # Create a frame for the listbox and scrollbar
    list_frame = ttk.Frame(frame)
    list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

    # Create scrollbar
    scrollbar = ttk.Scrollbar(list_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Create listbox
    listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, exportselection=0)
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Configure scrollbar
    scrollbar.config(command=listbox.yview)

    # Insert models into listbox
    for model in models_list:
        listbox.insert(tk.END, model)
        if model == current_selection:
            listbox.selection_set(listbox.size() - 1)
            listbox.see(listbox.size() - 1)

    # Create a frame for buttons
    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X, pady=(10, 0))

    # Variable to store the result
    result = [None]

    # Define OK function
    def ok_function():
        selection = listbox.curselection()
        if selection:
            result[0] = listbox.get(selection[0])
        dialog.destroy()

    # Define Cancel function
    def cancel_function():
        dialog.destroy()

    # Create OK and Cancel buttons
    ttk.Button(button_frame, text="OK", command=ok_function).pack(side=tk.RIGHT, padx=5)
    ttk.Button(button_frame, text="Cancel", command=cancel_function).pack(side=tk.RIGHT)

    # Make dialog modal
    dialog.transient(parent)
    dialog.deiconify()
    try:
        dialog.grab_set()
    except tk.TclError:
        pass  # Window not viewable yet
    parent.wait_window(dialog)

    return result[0]


def askstring_min(parent: tk.Tk, title: str, prompt: str, initialvalue: str = "") -> Optional[str]:
    """Show a simple string input dialog.

    Args:
        parent: Parent window
        title: Dialog title
        prompt: Prompt text
        initialvalue: Initial value for the entry field

    Returns:
        The entered string or None if cancelled
    """
    dialog = create_toplevel_dialog(parent, title, "400x150")

    # Create widgets
    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=prompt).pack(anchor=tk.W)

    entry_var = tk.StringVar(value=initialvalue)
    entry = ttk.Entry(frame, textvariable=entry_var, width=50)
    entry.pack(fill=tk.X, pady=10)
    entry.focus_set()
    entry.select_range(0, tk.END)

    result = [None]

    def ok():
        result[0] = entry_var.get()
        dialog.destroy()

    def cancel():
        dialog.destroy()

    # Button frame
    btn_frame = ttk.Frame(frame)
    btn_frame.pack(fill=tk.X)
    ttk.Button(btn_frame, text="OK", command=ok).pack(side=tk.RIGHT, padx=5)
    ttk.Button(btn_frame, text="Cancel", command=cancel).pack(side=tk.RIGHT)

    # Bind Enter key
    entry.bind("<Return>", lambda e: ok())
    dialog.bind("<Escape>", lambda e: cancel())

    parent.wait_window(dialog)
    return result[0]


def ask_conditions_dialog(parent: tk.Tk, title: str, prompt: str,
                          conditions: List[str]) -> Optional[str]:
    """Show a dialog for selecting conditions from a list.

    Args:
        parent: Parent window
        title: Dialog title
        prompt: Prompt text
        conditions: List of conditions to choose from

    Returns:
        Selected conditions as comma-separated string, or None if cancelled
    """
    dialog = create_toplevel_dialog(parent, title, "500x400")

    frame = ttk.Frame(dialog, padding=10)
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=prompt).pack(anchor=tk.W, pady=(0, 10))

    # Listbox with multiple selection
    list_frame = ttk.Frame(frame)
    list_frame.pack(fill=tk.BOTH, expand=True)

    scrollbar = ttk.Scrollbar(list_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE,
                         yscrollcommand=scrollbar.set, exportselection=0)
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=listbox.yview)

    for condition in conditions:
        listbox.insert(tk.END, condition)

    # Custom entry for additional conditions
    ttk.Label(frame, text="Or enter custom conditions (comma-separated):").pack(
        anchor=tk.W, pady=(10, 5))
    custom_var = tk.StringVar()
    custom_entry = ttk.Entry(frame, textvariable=custom_var)
    custom_entry.pack(fill=tk.X)

    result = [None]

    def ok():
        selected = [listbox.get(i) for i in listbox.curselection()]
        custom = custom_var.get().strip()
        if custom:
            selected.extend([c.strip() for c in custom.split(",") if c.strip()])
        if selected:
            result[0] = ", ".join(selected)
        dialog.destroy()

    def cancel():
        dialog.destroy()

    btn_frame = ttk.Frame(frame)
    btn_frame.pack(fill=tk.X, pady=(10, 0))
    ttk.Button(btn_frame, text="OK", command=ok).pack(side=tk.RIGHT, padx=5)
    ttk.Button(btn_frame, text="Cancel", command=cancel).pack(side=tk.RIGHT)

    parent.wait_window(dialog)
    return result[0]
