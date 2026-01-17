"""
Translation Responses Module

Provides canned responses management functionality.
"""

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import X, LEFT, RIGHT
from typing import TYPE_CHECKING, Optional, Dict, List, Callable
from utils.structured_logging import get_logger, Logger

from ui.tooltip import ToolTip
from settings.settings_manager import settings_manager

if TYPE_CHECKING:
    pass


logger = get_logger(__name__)


class ResponsesMixin:
    """Mixin for canned responses management."""

    dialog: Optional[tk.Toplevel]
    favorite_responses: List[str]

    # UI components
    canned_canvas: tk.Canvas
    canned_canvas_window: int
    canned_responses_frame: ttk.Frame
    canned_category_var: tk.StringVar
    canned_category_combo: ttk.Combobox
    canned_search_var: tk.StringVar
    canned_search_entry: ttk.Entry
    canned_frame: ttk.Frame
    _quick_responses_visible: tk.BooleanVar
    _quick_toggle_btn: ttk.Button
    doctor_input_text: tk.Text
    recording_status: ttk.Label

    # Methods from other mixins
    def _on_doctor_text_change(self, event=None): ...

    def _create_canned_responses(self, parent):
        """Create canned response buttons for common medical phrases.

        Args:
            parent: Parent widget
        """
        # Container for responses and manage button
        container = ttk.Frame(parent)
        container.pack(fill=X)

        # Header with category filter, search, and manage button
        header_frame = ttk.Frame(container)
        header_frame.pack(fill=X, pady=(0, 5))

        # Category filter
        ttk.Label(header_frame, text="Category:").pack(side=LEFT, padx=(0, 3))

        self.canned_category_var = tk.StringVar(value="All")
        categories = ["All", "★ Favorites", "greeting", "symptom", "history", "instruction", "clarify", "general"]
        self.canned_category_combo = ttk.Combobox(
            header_frame,
            textvariable=self.canned_category_var,
            values=categories,
            state="readonly",
            width=12
        )
        self.canned_category_combo.pack(side=LEFT, padx=(0, 8))
        self.canned_category_combo.bind("<<ComboboxSelected>>", lambda e: self._populate_canned_responses())

        # Search filter
        ttk.Label(header_frame, text="Search:").pack(side=LEFT, padx=(0, 3))
        self.canned_search_var = tk.StringVar()
        self.canned_search_entry = ttk.Entry(
            header_frame,
            textvariable=self.canned_search_var,
            width=15
        )
        self.canned_search_entry.pack(side=LEFT, padx=(0, 5))
        self.canned_search_var.trace_add("write", lambda *args: self._populate_canned_responses())
        ToolTip(self.canned_search_entry, "Filter responses by text")

        # Clear search button
        clear_search_btn = ttk.Button(
            header_frame,
            text="✕",
            command=lambda: self.canned_search_var.set(""),
            bootstyle="secondary",
            width=2
        )
        clear_search_btn.pack(side=LEFT, padx=(0, 10))

        # Manage button on the right
        manage_btn = ttk.Button(
            header_frame,
            text="⚙ Manage",
            command=self._manage_canned_responses,
            bootstyle="secondary",
            width=10
        )
        manage_btn.pack(side=RIGHT)
        ToolTip(manage_btn, "Add, edit, or delete quick responses")

        # Create scrollable container for responses with fixed max height
        scroll_container = ttk.Frame(container, height=120)
        scroll_container.pack(fill=X)
        scroll_container.pack_propagate(False)

        # Canvas for scrolling
        self.canned_canvas = tk.Canvas(scroll_container, highlightthickness=0)
        self.canned_canvas.pack(side=LEFT, fill=tk.BOTH, expand=True)

        # Scrollbar
        scrollbar = ttk.Scrollbar(scroll_container, orient="vertical", command=self.canned_canvas.yview)
        scrollbar.pack(side=RIGHT, fill=tk.Y)
        self.canned_canvas.configure(yscrollcommand=scrollbar.set)

        # Responses frame inside canvas
        responses_frame = ttk.Frame(self.canned_canvas)
        self.canned_canvas_window = self.canned_canvas.create_window((0, 0), window=responses_frame, anchor="nw")

        # Store reference for refresh
        self.canned_responses_frame = responses_frame

        # Bind canvas resize to update scroll region
        def on_frame_configure(event):
            self.canned_canvas.configure(scrollregion=self.canned_canvas.bbox("all"))

        def on_canvas_configure(event):
            self.canned_canvas.itemconfig(self.canned_canvas_window, width=event.width)

        responses_frame.bind("<Configure>", on_frame_configure)
        self.canned_canvas.bind("<Configure>", on_canvas_configure)

        # Enable mouse wheel scrolling
        def on_mousewheel(event):
            self.canned_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def on_mousewheel_linux(event):
            if event.num == 4:
                self.canned_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.canned_canvas.yview_scroll(1, "units")

        self.canned_canvas.bind("<MouseWheel>", on_mousewheel)
        self.canned_canvas.bind("<Button-4>", on_mousewheel_linux)
        self.canned_canvas.bind("<Button-5>", on_mousewheel_linux)

        # Populate responses
        self._populate_canned_responses()

    def _populate_canned_responses(self):
        """Populate the canned responses from settings."""
        # Clear existing buttons
        for widget in self.canned_responses_frame.winfo_children():
            widget.destroy()

        # Get responses from settings
        canned_settings = settings_manager.get("translation_canned_responses", {})
        responses = canned_settings.get("responses", {})

        if not responses:
            ttk.Label(
                self.canned_responses_frame,
                text="No quick responses configured. Click 'Manage' to add some.",
                foreground="gray"
            ).pack(pady=20)
            return

        # Get selected category filter
        selected_category = self.canned_category_var.get() if hasattr(self, 'canned_category_var') else "All"

        # Get search text
        search_text = self.canned_search_var.get().lower() if hasattr(self, 'canned_search_var') else ""

        # Filter responses by category and search
        filtered_responses = {}
        for response_text, category in responses.items():
            # Check category
            if selected_category == "★ Favorites":
                if response_text not in self.favorite_responses:
                    continue
            elif selected_category != "All" and category != selected_category:
                continue

            # Check search filter
            if search_text and search_text not in response_text.lower():
                continue

            filtered_responses[response_text] = category

        if not filtered_responses:
            msg = "No matching responses found." if search_text else f"No responses in '{selected_category}' category."
            ttk.Label(
                self.canned_responses_frame,
                text=msg,
                foreground="gray"
            ).pack(pady=20)
            return

        # Category colors
        category_styles = {
            "greeting": "outline-success",
            "symptom": "outline-warning",
            "history": "outline-info",
            "instruction": "outline-primary",
            "clarify": "outline-danger",
            "general": "outline-secondary"
        }

        # Create buttons in rows
        current_row = None
        button_count = 0
        max_per_row = 4

        for response_text, category in filtered_responses.items():
            if button_count % max_per_row == 0:
                current_row = ttk.Frame(self.canned_responses_frame)
                current_row.pack(fill=X, pady=2)

            style = category_styles.get(category, "outline-secondary")

            # Check if favorite
            is_favorite = response_text in self.favorite_responses
            btn_text = f"★ {response_text[:30]}" if is_favorite else response_text[:35]

            btn = ttk.Button(
                current_row,
                text=btn_text,
                command=lambda t=response_text: self._insert_canned_response(t),
                bootstyle=style,
                width=25
            )
            btn.pack(side=LEFT, padx=2, pady=1)

            # Right-click to toggle favorite
            btn.bind("<Button-3>", lambda e, t=response_text: self._toggle_favorite_response(t))
            ToolTip(btn, f"[{category}] Right-click to toggle favorite")

            button_count += 1

    def _manage_canned_responses(self):
        """Open the canned responses management dialog."""
        from ui.dialogs.canned_responses_dialog import CannedResponsesDialog
        dlg = CannedResponsesDialog(self.dialog)
        dlg.show()
        # Refresh after dialog closes
        self._populate_canned_responses()

    def _insert_canned_response(self, text):
        """Insert a canned response into the doctor input.

        Args:
            text: Response text to insert
        """
        # Get current text
        current = self.doctor_input_text.get("1.0", tk.END).strip()

        # Insert response
        if current:
            new_text = f"{current} {text}"
        else:
            new_text = text

        self.doctor_input_text.delete("1.0", tk.END)
        self.doctor_input_text.insert("1.0", new_text)

        # Trigger translation
        self._on_doctor_text_change()

        self.recording_status.config(text="Response inserted", foreground="green")

    def _toggle_quick_responses(self):
        """Toggle visibility of Quick Responses section."""
        if self._quick_responses_visible.get():
            self.canned_frame.pack(fill=X)
            self._quick_toggle_btn.config(text="▼ Quick Responses")
        else:
            self.canned_frame.pack_forget()
            self._quick_toggle_btn.config(text="▶ Quick Responses")

    def _toggle_favorite_response(self, response_text: str):
        """Toggle a canned response as favorite.

        Args:
            response_text: Response text to toggle
        """
        if response_text in self.favorite_responses:
            self.favorite_responses.remove(response_text)
        else:
            self.favorite_responses.append(response_text)

        # Save to settings
        settings_manager.set_nested("translation.favorite_responses", self.favorite_responses)

        # Refresh display
        self._populate_canned_responses()


__all__ = ["ResponsesMixin"]
