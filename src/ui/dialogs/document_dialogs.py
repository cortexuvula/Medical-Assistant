"""
Document Dialogs Module

Dialogs for letter generation options and letterhead configuration.
"""

import logging
import tkinter as tk
from tkinter import messagebox, scrolledtext
import ttkbootstrap as ttk

from ui.dialogs.dialog_utils import create_toplevel_dialog


def show_letter_options_dialog(parent: tk.Tk) -> tuple:
    """Show dialog to get letter source, recipient type, and specifications from user.

    Returns:
        tuple: (source, recipient_type, specifications) where source is 'transcript' or 'soap'
    """
    dialog = create_toplevel_dialog(parent, "Letter Options", "700x750")

    # Add a main frame with padding for better spacing
    main_frame = ttk.Frame(dialog, padding=(20, 20, 20, 20))
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Source selection
    ttk.Label(main_frame, text="Select text source for the letter:", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 10))

    source_frame = ttk.Frame(main_frame)
    source_frame.pack(fill="x", pady=(0, 15), anchor="w")

    source_var = tk.StringVar(value="transcript")
    ttk.Radiobutton(source_frame, text="Use text from Transcript tab", variable=source_var, value="transcript").pack(anchor="w", padx=20, pady=5)
    ttk.Radiobutton(source_frame, text="Use text from SOAP tab", variable=source_var, value="soap").pack(anchor="w", padx=20, pady=5)

    # Recipient type selection (NEW)
    ttk.Label(main_frame, text="Letter recipient type:", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(10, 5))
    ttk.Label(main_frame, text="Select the type of recipient to focus the letter content appropriately",
              wraplength=650, font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 10))

    recipient_frame = ttk.Frame(main_frame)
    recipient_frame.pack(fill="x", pady=(0, 15), anchor="w")

    # Recipient type options
    recipient_types = [
        ("Insurance Company", "insurance"),
        ("Employer / Workplace", "employer"),
        ("Specialist / Colleague", "specialist"),
        ("Patient", "patient"),
        ("School / Educational Institution", "school"),
        ("Legal / Attorney", "legal"),
        ("Government Agency (Disability, etc.)", "government"),
        ("Other (specify in instructions below)", "other")
    ]

    recipient_var = tk.StringVar(value="insurance")
    for label, value in recipient_types:
        ttk.Radiobutton(recipient_frame, text=label, variable=recipient_var, value=value).pack(anchor="w", padx=20, pady=2)

    # Additional specifications
    ttk.Label(main_frame, text="Additional instructions (optional):", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(10, 5))
    ttk.Label(main_frame, text="Enter any specific requirements (purpose, specific conditions to focus on, tone, etc.)",
              wraplength=650, font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 10))

    specs_text = scrolledtext.ScrolledText(main_frame, height=6, width=80, font=("Segoe UI", 10))
    specs_text.pack(fill="both", expand=True, pady=(0, 20))

    # Add placeholder text
    placeholder_text = "Examples:\n- Focus only on back injury for workers comp claim\n- Request prior authorization for MRI\n- Fitness to return to work assessment\n- Medical clearance for surgery"
    specs_text.insert("1.0", placeholder_text)
    specs_text.tag_add("gray", "1.0", "end")
    specs_text.tag_config("gray", foreground="gray")

    def clear_placeholder(_):
        if specs_text.get("1.0", "end-1c").strip() == placeholder_text.strip():
            specs_text.delete("1.0", "end")
            specs_text.tag_remove("gray", "1.0", "end")
        specs_text.unbind("<FocusIn>")

    specs_text.bind("<FocusIn>", clear_placeholder)

    result = [None, None, None]

    def on_submit():
        result[0] = source_var.get()
        result[1] = recipient_var.get()
        result[2] = specs_text.get("1.0", "end-1c")
        # If user didn't change placeholder text, provide empty specs
        if result[2].strip() == placeholder_text.strip():
            result[2] = ""
        dialog.destroy()

    def on_cancel():
        dialog.destroy()

    # Button layout
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill="x", padx=20, pady=(0, 20))

    ttk.Button(btn_frame, text="Cancel", command=on_cancel, width=15).pack(side="left", padx=10, pady=10)
    ttk.Button(btn_frame, text="Generate Letter", command=on_submit, bootstyle="success", width=15).pack(side="right", padx=10, pady=10)

    # Center the dialog on the screen
    dialog.update_idletasks()
    dialog.geometry("+{}+{}".format(
        (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2),
        (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
    ))

    dialog.wait_window()
    return result[0], result[1], result[2]


def show_letterhead_dialog(parent: tk.Tk, clinic_name: str = "", doctor_name: str = "") -> tuple:
    """Show dialog to get letterhead information (clinic name and doctor name).

    Args:
        parent: Parent window
        clinic_name: Pre-filled clinic name
        doctor_name: Pre-filled doctor name

    Returns:
        tuple: (clinic_name, doctor_name) or None if cancelled
    """
    dialog = create_toplevel_dialog(parent, "Letterhead Information", "450x280")

    # Main frame
    main_frame = ttk.Frame(dialog, padding=(20, 20, 20, 20))
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Heading
    ttk.Label(
        main_frame,
        text="Enter letterhead information:",
        font=("Segoe UI", 11, "bold")
    ).pack(anchor="w", pady=(0, 15))

    ttk.Label(
        main_frame,
        text="This information will appear at the top of your PDF documents.",
        font=("Segoe UI", 10),
        wraplength=400
    ).pack(anchor="w", pady=(0, 15))

    # Clinic name
    clinic_frame = ttk.Frame(main_frame)
    clinic_frame.pack(fill="x", pady=5)
    ttk.Label(clinic_frame, text="Clinic Name:", width=12).pack(side="left")
    clinic_var = tk.StringVar(value=clinic_name)
    clinic_entry = ttk.Entry(clinic_frame, textvariable=clinic_var, width=40)
    clinic_entry.pack(side="left", padx=(10, 0), fill="x", expand=True)

    # Doctor name
    doctor_frame = ttk.Frame(main_frame)
    doctor_frame.pack(fill="x", pady=5)
    ttk.Label(doctor_frame, text="Doctor Name:", width=12).pack(side="left")
    doctor_var = tk.StringVar(value=doctor_name)
    doctor_entry = ttk.Entry(doctor_frame, textvariable=doctor_var, width=40)
    doctor_entry.pack(side="left", padx=(10, 0), fill="x", expand=True)

    # Save checkbox
    save_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(
        main_frame,
        text="Save for future use",
        variable=save_var
    ).pack(anchor="w", pady=(15, 0))

    result = [None]

    def on_submit():
        clinic = clinic_var.get().strip()
        doctor = doctor_var.get().strip()

        if not clinic and not doctor:
            messagebox.showwarning("Input Required", "Please enter at least a clinic name or doctor name.")
            return

        # Save to settings if requested
        if save_var.get():
            try:
                from settings.settings_manager import SETTINGS, save_settings
                SETTINGS["clinic_name"] = clinic
                SETTINGS["doctor_name"] = doctor
                save_settings()
            except Exception as e:
                logging.warning(f"Could not save letterhead settings: {e}")

        result[0] = (clinic, doctor)
        dialog.destroy()

    def on_cancel():
        dialog.destroy()

    # Buttons
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill="x", padx=20, pady=(0, 20))

    ttk.Button(btn_frame, text="Cancel", command=on_cancel, width=12).pack(side="left", padx=5)
    ttk.Button(btn_frame, text="Continue", command=on_submit, bootstyle="success", width=12).pack(side="right", padx=5)

    # Focus on first empty field
    if not clinic_name:
        clinic_entry.focus_set()
    elif not doctor_name:
        doctor_entry.focus_set()
    else:
        clinic_entry.focus_set()

    # Center dialog
    dialog.update_idletasks()
    dialog.geometry("+{}+{}".format(
        (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2),
        (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
    ))

    dialog.wait_window()
    return result[0]


__all__ = ["show_letter_options_dialog", "show_letterhead_dialog"]
