"""
Recording Recovery Dialog Module

Prompts the user to recover an incomplete recording on application startup.
"""

import tkinter as tk
import ttkbootstrap as ttk
from datetime import datetime
from typing import Dict, Any, Optional

from ui.dialogs.dialog_utils import create_toplevel_dialog


def show_recording_recovery_dialog(parent: tk.Tk, recovery_info: Dict[str, Any]) -> bool:
    """Show dialog prompting user to recover an incomplete recording.

    Args:
        parent: Parent window
        recovery_info: Dictionary with session info from RecordingAutoSaveManager
            - session_id: Session identifier
            - start_time: Recording start time (ISO format)
            - last_save_time: Last auto-save time (ISO format)
            - patient_context: Optional patient context text
            - estimated_duration_seconds: Estimated recording duration
            - chunk_count: Number of saved audio chunks

    Returns:
        True if user wants to recover, False to discard
    """
    result = {"recover": False}

    # Create dialog - increased height to ensure all content fits
    dialog = create_toplevel_dialog(parent, "Recover Incomplete Recording?", "450x350")

    # Create button frame FIRST at the bottom so it always appears
    button_frame = ttk.Frame(dialog, padding=(20, 10, 20, 20))
    button_frame.pack(side=tk.BOTTOM, fill=tk.X)

    def on_recover():
        result["recover"] = True
        dialog.destroy()

    def on_discard():
        result["recover"] = False
        dialog.destroy()

    # Discard button (secondary)
    discard_btn = ttk.Button(
        button_frame,
        text="Discard",
        command=on_discard,
        bootstyle="secondary",
        width=12
    )
    discard_btn.pack(side=tk.RIGHT, padx=(5, 0))

    # Recover button (primary)
    recover_btn = ttk.Button(
        button_frame,
        text="Recover",
        command=on_recover,
        bootstyle="success",
        width=12
    )
    recover_btn.pack(side=tk.RIGHT)

    # Main content frame
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Warning icon and title
    title_frame = ttk.Frame(main_frame)
    title_frame.pack(fill=tk.X, pady=(0, 15))

    # Warning icon (using Unicode warning symbol)
    warning_label = ttk.Label(
        title_frame,
        text="\u26A0",  # Warning symbol
        font=("Segoe UI", 32),
        foreground="#FFA500"  # Orange color
    )
    warning_label.pack(side=tk.LEFT, padx=(0, 15))

    # Title text
    title_text = ttk.Label(
        title_frame,
        text="Incomplete Recording Found",
        font=("Segoe UI", 14, "bold")
    )
    title_text.pack(side=tk.LEFT, anchor=tk.W)

    # Description
    description = ttk.Label(
        main_frame,
        text="An incomplete recording was found from a previous session.\n"
             "Would you like to recover it?",
        wraplength=400,
        justify=tk.LEFT
    )
    description.pack(fill=tk.X, pady=(0, 15))

    # Info frame - use regular Frame with manual label for better compatibility
    info_outer = ttk.Frame(main_frame)
    info_outer.pack(fill=tk.X, pady=(0, 15))

    ttk.Label(info_outer, text="Recording Details:", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)

    info_frame = ttk.Frame(info_outer, padding=(10, 5, 10, 5))
    info_frame.pack(fill=tk.X)

    # Format duration
    duration_seconds = recovery_info.get("estimated_duration_seconds", 0)
    if duration_seconds >= 60:
        duration_str = f"{duration_seconds / 60:.1f} minutes"
    else:
        duration_str = f"{duration_seconds:.0f} seconds"

    # Format times
    start_time = recovery_info.get("start_time", "Unknown")
    last_save = recovery_info.get("last_save_time", "Unknown")

    try:
        if start_time != "Unknown":
            start_dt = datetime.fromisoformat(start_time)
            start_time = start_dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        pass

    try:
        if last_save != "Unknown":
            save_dt = datetime.fromisoformat(last_save)
            last_save = save_dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        pass

    # Info rows
    info_items = [
        ("Estimated Duration:", duration_str),
        ("Started:", start_time),
        ("Last Saved:", last_save),
    ]

    # Add patient context if available
    patient_context = recovery_info.get("patient_context", "")
    if patient_context and len(patient_context) > 0:
        # Truncate if too long
        if len(patient_context) > 50:
            patient_context = patient_context[:47] + "..."
        info_items.append(("Patient Context:", patient_context))

    for i, (label_text, value_text) in enumerate(info_items):
        row_frame = ttk.Frame(info_frame)
        row_frame.pack(fill=tk.X, pady=2)

        label = ttk.Label(row_frame, text=label_text, width=18, anchor=tk.W)
        label.pack(side=tk.LEFT)

        value = ttk.Label(row_frame, text=value_text, anchor=tk.W)
        value.pack(side=tk.LEFT, fill=tk.X, expand=True)

    # Handle window close
    def on_close():
        result["recover"] = False
        dialog.destroy()

    dialog.protocol("WM_DELETE_WINDOW", on_close)

    # Focus on recover button
    recover_btn.focus_set()

    # Bind Enter to recover and Escape to discard
    dialog.bind("<Return>", lambda e: on_recover())
    dialog.bind("<Escape>", lambda e: on_discard())

    # Wait for dialog to close
    dialog.wait_window()

    return result["recover"]
