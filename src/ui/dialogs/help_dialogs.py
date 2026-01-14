"""
Help Dialogs Module

Dialogs for showing keyboard shortcuts and about information.
"""

import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk

from ui.dialogs.dialog_utils import create_toplevel_dialog


def show_shortcuts_dialog(parent: tk.Tk) -> None:
    """Show keyboard shortcuts dialog."""
    dialog = tk.Toplevel(parent)
    dialog.title("Keyboard Shortcuts")
    dialog.transient(parent)
    dialog.resizable(True, True)  # Allow resizing
    dialog.minsize(700, 400)  # Set minimum size

    # Set initial size and position BEFORE creating content
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    dialog_width = 900
    dialog_height = 600  # Increased height even more

    # Calculate center position
    x = (screen_width // 2) - (dialog_width // 2)
    y = (screen_height // 2) - (dialog_height // 2)

    # Ensure dialog is not positioned off screen
    x = max(50, min(x, screen_width - dialog_width - 50))
    y = max(50, min(y, screen_height - dialog_height - 50))

    dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

    # Configure dialog to be on top initially
    dialog.attributes('-topmost', True)
    dialog.focus_force()

    # Allow window manager to handle the dialog properly
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)

    # Create frame for keyboard shortcuts
    kb_frame = ttk.Frame(dialog)
    kb_frame.pack(expand=True, fill="both", padx=10, pady=(10, 5))

    # Create treeview with scrollbar
    tree_frame = ttk.Frame(kb_frame)
    tree_frame.pack(expand=True, fill="both")

    kb_tree = ttk.Treeview(tree_frame, columns=("Command", "Description"), show="headings", height=20)
    kb_tree.heading("Command", text="Command")
    kb_tree.heading("Description", text="Description")
    kb_tree.column("Command", width=200, anchor="w")
    kb_tree.column("Description", width=650, anchor="w")

    # Add scrollbar
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=kb_tree.yview)
    kb_tree.configure(yscrollcommand=scrollbar.set)

    # Pack treeview and scrollbar
    kb_tree.pack(side="left", expand=True, fill="both")
    scrollbar.pack(side="right", fill="y")

    # Organized shortcuts by category
    shortcuts_categories = [
        ("File Operations", [
            ("Ctrl+N", "New session"),
            ("Ctrl+S", "Save text and audio"),
            ("Ctrl+L", "Load audio file"),
            ("Ctrl+C", "Copy text to clipboard")
        ]),
        ("Text Editing", [
            ("Ctrl+Z", "Undo text changes"),
            ("Ctrl+Y", "Redo text changes")
        ]),
        ("Recording Controls", [
            ("F5", "Start/Stop recording"),
            ("Ctrl+Shift+S", "Start/Stop recording"),
            ("Space", "Pause/Resume recording (when recording)"),
            ("Esc", "Cancel recording")
        ]),
        ("Chat & Interface", [
            ("Ctrl+/", "Focus chat input"),
            ("Alt+T", "Toggle theme (Light/Dark)"),
            ("Ctrl+,", "Open Preferences"),
            ("F1", "Show this help dialog")
        ]),
        ("AI Analysis", [
            ("Ctrl+D", "Run diagnostic analysis"),
        ]),
        ("Export", [
            ("Ctrl+E", "Export to PDF"),
            ("Ctrl+Shift+W", "Export to Word"),
            ("Ctrl+Shift+F", "Export to FHIR"),
            ("Ctrl+P", "Print document")
        ])
    ]

    # Add shortcuts with categories
    for category, shortcuts in shortcuts_categories:
        # Add category header
        kb_tree.insert("", tk.END, values=(f"━━ {category} ━━", ""), tags=("category",))

        # Add shortcuts in category
        for cmd, desc in shortcuts:
            kb_tree.insert("", tk.END, values=(cmd, desc))

        # Add empty line for spacing
        kb_tree.insert("", tk.END, values=("", ""))

    # Configure category styling (theme-aware)
    try:
        # Try to detect if parent is using a dark theme
        if hasattr(parent, 'current_theme'):
            is_dark = parent.current_theme in ["darkly", "solar", "cyborg", "superhero"]
            category_color = "#6ea8fe" if is_dark else "#0d6efd"
        else:
            category_color = "#0d6efd"
        kb_tree.tag_configure("category", foreground=category_color, font=("Arial", 10, "bold"))
    except (tk.TclError, AttributeError):
        # Fallback to default blue color
        kb_tree.tag_configure("category", foreground="#0d6efd", font=("Arial", 10, "bold"))

    # Button frame at bottom
    button_frame = ttk.Frame(dialog)
    button_frame.pack(fill="x", padx=10, pady=10)

    ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side="right")

    # Update and focus on the dialog
    dialog.update_idletasks()
    dialog.focus_set()

    # Set modal behavior after dialog is fully created
    dialog.deiconify()
    try:
        dialog.grab_set()
    except tk.TclError:
        pass  # Window not viewable yet

    # Bring dialog to front and then allow normal window behavior
    dialog.lift()
    dialog.after(500, lambda: dialog.attributes('-topmost', False))  # Remove topmost after the dialog is established


def show_about_dialog(parent: tk.Tk) -> None:
    """Show about dialog with app information."""
    import platform
    import sys
    import os
    from datetime import datetime
    import webbrowser

    # Create custom dialog window
    dialog = create_toplevel_dialog(parent, "About Medical Assistant", "600x780")
    dialog.resizable(False, False)

    # Get current theme
    is_dark = hasattr(parent, 'current_theme') and parent.current_theme in ["darkly", "solar", "cyborg", "superhero"]

    # Main container with scrollable support
    main_frame = ttk.Frame(dialog, padding=15)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Header section with app icon and title
    header_frame = ttk.Frame(main_frame)
    header_frame.pack(fill=tk.X, pady=(0, 20))

    # App icon - load from file
    try:
        # Try to load the icon file
        from PIL import Image, ImageTk

        # Get the icon path
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon128x128.ico")

        if os.path.exists(icon_path):
            # Load and resize icon
            icon_image = Image.open(icon_path)
            icon_image = icon_image.resize((80, 80), Image.Resampling.LANCZOS)
            icon_photo = ImageTk.PhotoImage(icon_image)

            icon_label = ttk.Label(header_frame, image=icon_photo)
            icon_label.image = icon_photo  # Keep a reference to prevent garbage collection
            icon_label.pack()
        else:
            # Fallback to emoji if icon not found
            icon_label = ttk.Label(header_frame, text="🏥", font=("Segoe UI", 48))
            icon_label.pack()
    except Exception as e:
        # Fallback to emoji if any error occurs
        icon_label = ttk.Label(header_frame, text="🏥", font=("Segoe UI", 48))
        icon_label.pack()

    # App title
    title_label = ttk.Label(header_frame, text="Medical Assistant",
                           font=("Segoe UI", 24, "bold"))
    title_label.pack(pady=(10, 5))

    # Version info
    version_label = ttk.Label(header_frame, text="Version 2.0.0",
                             font=("Segoe UI", 12))
    version_label.pack()

    # Separator
    ttk.Separator(main_frame, orient="horizontal").pack(fill=tk.X, pady=20)

    # Description section
    desc_frame = ttk.Frame(main_frame)
    desc_frame.pack(fill=tk.X, pady=(0, 20))

    description = """A powerful medical dictation and documentation assistant that helps healthcare professionals create accurate medical records efficiently.

Features advanced speech-to-text, AI-powered text processing, and SOAP note generation."""

    desc_label = ttk.Label(desc_frame, text=description,
                          wraplength=550, justify=tk.CENTER,
                          font=("Segoe UI", 10))
    desc_label.pack()

    # Info section
    info_frame = ttk.Labelframe(main_frame, text="System Information", padding=15)
    info_frame.pack(fill=tk.X, pady=(0, 20))

    # System details
    info_items = [
        ("Platform", platform.system()),
        ("Python Version", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"),
        ("Architecture", platform.machine()),
        ("Build Date", datetime.now().strftime("%B %Y"))
    ]

    for label, value in info_items:
        row_frame = ttk.Frame(info_frame)
        row_frame.pack(fill=tk.X, pady=2)
        ttk.Label(row_frame, text=f"{label}:", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        ttk.Label(row_frame, text=value, font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(10, 0))

    # Credits section
    credits_frame = ttk.Labelframe(main_frame, text="Credits", padding=10)
    credits_frame.pack(fill=tk.X, pady=(0, 15))

    credits_text = """Developed with ❤️ by:
• Original Developer: Andre Hugo
• Enhanced by: Claude (Anthropic AI Assistant)

Technologies: Python, Tkinter/ttkbootstrap, OpenAI GPT,
ElevenLabs, Deepgram, Groq APIs"""

    credits_label = ttk.Label(credits_frame, text=credits_text,
                             font=("Segoe UI", 9), justify=tk.LEFT,
                             wraplength=550)
    credits_label.pack(anchor="w", fill=tk.X)

    # Links section
    links_frame = ttk.Frame(main_frame)
    links_frame.pack(fill=tk.X)

    def open_link(url):
        webbrowser.open(url)

    # Support link (styled as a button)
    support_btn = ttk.Button(links_frame, text="💬 Get Support",
                           command=lambda: messagebox.showinfo("Support", "For support, please contact:\nsupport@medical-assistant.app"),
                           bootstyle="link")
    support_btn.pack(side=tk.LEFT, padx=(0, 10))

    # License link
    license_btn = ttk.Button(links_frame, text="📜 License",
                         command=lambda: messagebox.showinfo("License", "This software is licensed under the MIT License.\n\nYou are free to use, modify, and distribute\nthis software in accordance with the license terms."),
                         bootstyle="link")
    license_btn.pack(side=tk.LEFT)

    # Footer
    ttk.Separator(main_frame, orient="horizontal").pack(fill=tk.X, pady=(20, 10))

    # Dynamic copyright year
    current_year = datetime.now().year
    footer_label = ttk.Label(main_frame, text=f"© {current_year} Medical Assistant. All rights reserved.",
                            font=("Segoe UI", 8), foreground="gray")
    footer_label.pack()

    # Close button
    close_btn = ttk.Button(main_frame, text="Close", command=dialog.destroy,
                          bootstyle="primary")
    close_btn.pack(pady=(10, 0))

    # Center the dialog
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
    y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
    dialog.geometry(f"+{x}+{y}")

    # Add fade-in animation
    dialog.attributes('-alpha', 0.0)
    dialog.update()

    def fade_in(alpha=0.0):
        if alpha < 1.0:
            alpha += 0.1
            dialog.attributes('-alpha', alpha)
            dialog.after(20, lambda: fade_in(alpha))

    fade_in()

    # Make dialog modal
    dialog.transient(parent)
    dialog.deiconify()
    try:
        dialog.grab_set()
    except tk.TclError:
        pass  # Window not viewable yet

    # Bind ESC key to close dialog
    dialog.bind('<Escape>', lambda e: dialog.destroy())

    # Focus on close button
    close_btn.focus_set()

    parent.wait_window(dialog)


__all__ = ["show_shortcuts_dialog", "show_about_dialog"]
