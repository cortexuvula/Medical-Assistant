"""
Custom Suggestions Dialog

Dialog for managing custom chat suggestions.
"""

import logging
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk

from settings import settings_manager
from ui.scaling_utils import ui_scaler


def show_custom_suggestions_dialog(parent: tk.Tk) -> None:
    """Show dialog to manage custom chat suggestions."""

    dialog = tk.Toplevel(parent)
    dialog.title("Manage Custom Chat Suggestions")
    dialog_width, dialog_height = ui_scaler.get_dialog_size(700, 600)
    dialog.geometry(f"{dialog_width}x{dialog_height}")
    dialog.resizable(True, True)
    dialog.transient(parent)

    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - (dialog_width // 2)
    y = (dialog.winfo_screenheight() // 2) - (dialog_height // 2)
    dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

    dialog.deiconify()
    try:
        dialog.grab_set()
    except tk.TclError:
        pass

    main_frame = ttk.Frame(dialog, padding=15)
    main_frame.pack(fill=tk.BOTH, expand=True)

    title_frame = ttk.Frame(main_frame)
    title_frame.pack(fill=tk.X, pady=(0, 15))

    ttk.Label(title_frame, text="Custom Chat Suggestions", font=("Arial", 14, "bold")).pack(anchor="w")
    ttk.Label(title_frame, text="Create custom suggestions for different contexts. These will appear alongside built-in suggestions.",
              font=("Arial", 10), foreground="gray").pack(anchor="w", pady=(5, 0))

    notebook = ttk.Notebook(main_frame)
    notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

    suggestion_vars = {}

    def create_suggestion_tab(tab_name: str, context_key: str):
        tab_frame = ttk.Frame(notebook)
        notebook.add(tab_frame, text=tab_name)

        if context_key != "global":
            with_frame = ttk.Labelframe(tab_frame, text="When content exists", padding=10)
            with_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            with_vars = create_suggestion_manager(with_frame, context_key, "with_content")
            suggestion_vars[f"{context_key}_with_content"] = with_vars

            without_frame = ttk.Labelframe(tab_frame, text="When no content exists", padding=10)
            without_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            without_vars = create_suggestion_manager(without_frame, context_key, "without_content")
            suggestion_vars[f"{context_key}_without_content"] = without_vars
        else:
            global_vars = create_suggestion_manager(tab_frame, context_key, None)
            suggestion_vars["global"] = global_vars

    def create_suggestion_manager(parent_frame: ttk.Frame, context: str, content_state: str):
        if context == "global":
            current_suggestions = settings_manager.get("custom_chat_suggestions", {}).get("global", [])
        else:
            current_suggestions = settings_manager.get("custom_chat_suggestions", {}).get(context, {}).get(content_state, [])

        suggestion_vars_list = []

        canvas = tk.Canvas(parent_frame, height=150)
        scrollbar = ttk.Scrollbar(parent_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def add_suggestion_entry(text="", is_favorite=False):
            entry_frame = ttk.Frame(scrollable_frame)
            entry_frame.pack(fill=tk.X, pady=2)

            favorite_var = tk.BooleanVar(value=is_favorite)
            star_btn = ttk.Button(entry_frame, text="★" if is_favorite else "☆", width=3)

            def toggle_favorite():
                new_state = not favorite_var.get()
                favorite_var.set(new_state)
                star_btn.configure(text="★" if new_state else "☆")

            star_btn.configure(command=toggle_favorite)
            star_btn.pack(side=tk.LEFT, padx=(0, 5))

            text_var = tk.StringVar(value=text)
            entry = ttk.Entry(entry_frame, textvariable=text_var, width=45)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

            def remove_entry():
                for i, (f, t, fav) in enumerate(suggestion_vars_list):
                    if f == entry_frame:
                        suggestion_vars_list.pop(i)
                        break
                entry_frame.destroy()
                canvas.configure(scrollregion=canvas.bbox("all"))

            remove_btn = ttk.Button(entry_frame, text="×", width=3, command=remove_entry)
            remove_btn.pack(side=tk.RIGHT)

            suggestion_vars_list.append((entry_frame, text_var, favorite_var))

            canvas.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))

            return text_var

        for suggestion in current_suggestions:
            if isinstance(suggestion, dict):
                text = suggestion.get("text", "")
                is_favorite = suggestion.get("favorite", False)
            else:
                text = str(suggestion)
                is_favorite = False
            if text:
                add_suggestion_entry(text, is_favorite)

        button_frame = ttk.Frame(parent_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        def add_new_suggestion():
            var = add_suggestion_entry()
            for entry_frame, text_var, _ in suggestion_vars_list:
                if text_var == var:
                    for widget in entry_frame.winfo_children():
                        if isinstance(widget, ttk.Entry):
                            widget.focus_set()
                            break
                    break

        ttk.Button(button_frame, text="+ Add Suggestion", command=add_new_suggestion).pack(side=tk.LEFT)

        def clear_all():
            if messagebox.askyesno("Clear All", "Are you sure you want to remove all suggestions?", parent=dialog):
                for entry_frame, _, _ in suggestion_vars_list.copy():
                    entry_frame.destroy()
                suggestion_vars_list.clear()
                canvas.configure(scrollregion=canvas.bbox("all"))

        ttk.Button(button_frame, text="Clear All", command=clear_all).pack(side=tk.LEFT, padx=(10, 0))

        return suggestion_vars_list

    create_suggestion_tab("Global", "global")
    create_suggestion_tab("Transcript", "transcript")
    create_suggestion_tab("SOAP Note", "soap")
    create_suggestion_tab("Referral", "referral")
    create_suggestion_tab("Letter", "letter")

    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, pady=(10, 0))

    def save_suggestions():
        try:
            custom_suggestions = settings_manager.get("custom_chat_suggestions", {})

            if "global" in suggestion_vars:
                global_suggestions = []
                for _, text_var, favorite_var in suggestion_vars["global"]:
                    text = text_var.get().strip()
                    if text:
                        global_suggestions.append({
                            "text": text,
                            "favorite": favorite_var.get()
                        })
                custom_suggestions["global"] = global_suggestions

            for context in ["transcript", "soap", "referral", "letter"]:
                if context not in custom_suggestions:
                    custom_suggestions[context] = {"with_content": [], "without_content": []}

                key = f"{context}_with_content"
                if key in suggestion_vars:
                    with_suggestions = []
                    for _, text_var, favorite_var in suggestion_vars[key]:
                        text = text_var.get().strip()
                        if text:
                            with_suggestions.append({
                                "text": text,
                                "favorite": favorite_var.get()
                            })
                    custom_suggestions[context]["with_content"] = with_suggestions

                key = f"{context}_without_content"
                if key in suggestion_vars:
                    without_suggestions = []
                    for _, text_var, favorite_var in suggestion_vars[key]:
                        text = text_var.get().strip()
                        if text:
                            without_suggestions.append({
                                "text": text,
                                "favorite": favorite_var.get()
                            })
                    custom_suggestions[context]["without_content"] = without_suggestions

            settings_manager.set("custom_chat_suggestions", custom_suggestions)

            messagebox.showinfo("Success", "Custom suggestions saved successfully!", parent=dialog)
            dialog.destroy()

        except Exception as e:
            logging.error(f"Error saving custom suggestions: {e}")
            messagebox.showerror("Error", f"Failed to save suggestions: {str(e)}", parent=dialog)

    def cancel():
        dialog.destroy()

    ttk.Button(button_frame, text="Save", command=save_suggestions, bootstyle="success").pack(side=tk.RIGHT, padx=(5, 0))
    ttk.Button(button_frame, text="Cancel", command=cancel).pack(side=tk.RIGHT)

    dialog.protocol("WM_DELETE_WINDOW", cancel)
    dialog.wait_window()


__all__ = ["show_custom_suggestions_dialog"]
