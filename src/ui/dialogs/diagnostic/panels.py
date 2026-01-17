"""
Diagnostic Results Panels Module

Provides panel creation for red flags and investigations tracking.
"""

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import X, BOTH, Y, VERTICAL, LEFT, RIGHT, W
from tkinter import messagebox
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from utils.structured_logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from database.database import Database


class PanelsMixin:
    """Mixin for creating diagnostic result panels."""

    parent: tk.Tk
    dialog: Optional[tk.Toplevel]
    investigation_vars: Dict[int, Dict]
    inv_summary_label: ttk.Label
    _db: Optional["Database"]

    def _create_red_flags_panel(self, parent: ttk.Frame, red_flags: List[str]) -> None:
        """Create a prominent red flags panel with visual emphasis.

        Args:
            parent: Parent frame
            red_flags: List of red flag strings
        """
        # Create collapsible red flags panel
        red_frame = ttk.Frame(parent)
        red_frame.pack(fill=X, pady=(0, 10))

        # Header with warning icon and count
        header_frame = ttk.Frame(red_frame)
        header_frame.pack(fill=X)

        # Use a styled label for the header
        style = ttk.Style()
        try:
            style.configure('RedFlag.TLabel', foreground='white', background='#dc3545',
                          font=('Segoe UI', 11, 'bold'))
        except Exception:
            pass

        header_label = ttk.Label(
            header_frame,
            text=f"  ⚠️ RED FLAGS ({len(red_flags)}) - URGENT ATTENTION REQUIRED  ",
            font=("Segoe UI", 11, "bold"),
            foreground="white",
            background="#dc3545"
        )
        header_label.pack(side=LEFT, fill=X, expand=True, ipady=5)

        # Content frame with red border effect
        content_frame = ttk.Frame(red_frame, padding=10)
        content_frame.pack(fill=X)

        # Add each red flag with icon
        for i, flag in enumerate(red_flags[:10], 1):  # Limit to 10 flags
            flag_frame = ttk.Frame(content_frame)
            flag_frame.pack(fill=X, pady=2)

            # Warning icon and text
            ttk.Label(
                flag_frame,
                text="⚠️",
                font=("Segoe UI", 10)
            ).pack(side=LEFT, padx=(0, 5))

            ttk.Label(
                flag_frame,
                text=flag,
                font=("Segoe UI", 10, "bold"),
                foreground="#dc3545",
                wraplength=700
            ).pack(side=LEFT, fill=X, expand=True)

        if len(red_flags) > 10:
            ttk.Label(
                content_frame,
                text=f"... and {len(red_flags) - 10} more red flags",
                font=("Segoe UI", 9, "italic"),
                foreground="gray"
            ).pack(anchor=W, pady=(5, 0))

    def _create_investigations_panel(
        self, parent: ttk.Frame, investigations: List[Dict[str, Any]]
    ) -> None:
        """Create an interactive investigations tracking panel.

        Args:
            parent: Parent frame
            investigations: List of investigation dictionaries
        """
        # Store investigation vars for later access
        self.investigation_vars = {}

        # Create collapsible investigations panel
        inv_frame = ttk.Labelframe(
            parent,
            text=f"📋 Recommended Investigations ({len(investigations)})",
            padding=10
        )
        inv_frame.pack(fill=X, pady=(0, 10))

        # Instructions
        ttk.Label(
            inv_frame,
            text="Check off completed investigations:",
            font=("Segoe UI", 9, "italic"),
            foreground="gray"
        ).pack(anchor=W, pady=(0, 5))

        # Scrollable frame for many investigations
        inv_canvas = tk.Canvas(inv_frame, height=150)
        inv_scrollbar = ttk.Scrollbar(inv_frame, orient=VERTICAL, command=inv_canvas.yview)
        inv_content = ttk.Frame(inv_canvas)

        inv_content.bind(
            "<Configure>",
            lambda e: inv_canvas.configure(scrollregion=inv_canvas.bbox("all"))
        )

        inv_canvas.create_window((0, 0), window=inv_content, anchor="nw")
        inv_canvas.configure(yscrollcommand=inv_scrollbar.set)

        inv_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        inv_scrollbar.pack(side=RIGHT, fill=Y)

        # Priority colors
        priority_colors = {
            'urgent': '#dc3545',
            'high': '#fd7e14',
            'routine': '#6c757d'
        }

        priority_icons = {
            'urgent': '🔴',
            'high': '🟠',
            'routine': '⚪'
        }

        # Filter out investigations with empty or invalid names
        valid_investigations = [
            inv for inv in investigations
            if inv.get('investigation_name', '').strip() and len(inv.get('investigation_name', '').strip()) >= 5
        ]

        # Update the panel title with correct count
        inv_frame.config(text=f"📋 Recommended Investigations ({len(valid_investigations)})")

        # Add each investigation with checkbox
        for i, inv in enumerate(valid_investigations[:20]):  # Limit to 20
            inv_row = ttk.Frame(inv_content)
            inv_row.pack(fill=X, pady=2)

            # Checkbox variable
            var = tk.BooleanVar(value=inv.get('status') == 'completed')
            self.investigation_vars[i] = {
                'var': var,
                'investigation': inv
            }

            # Priority icon
            priority = inv.get('priority', 'routine')
            ttk.Label(
                inv_row,
                text=priority_icons.get(priority, '⚪'),
                font=("Segoe UI", 10)
            ).pack(side=LEFT, padx=(0, 5))

            # Checkbox with investigation name
            cb = ttk.Checkbutton(
                inv_row,
                text=inv.get('investigation_name', 'Unknown'),
                variable=var,
                command=lambda idx=i: self._on_investigation_toggle(idx)
            )
            cb.pack(side=LEFT, fill=X, expand=True)

            # Priority label
            ttk.Label(
                inv_row,
                text=f"[{priority.upper()}]",
                font=("Segoe UI", 8),
                foreground=priority_colors.get(priority, 'gray')
            ).pack(side=RIGHT, padx=5)

        if len(valid_investigations) > 20:
            ttk.Label(
                inv_content,
                text=f"... and {len(valid_investigations) - 20} more investigations",
                font=("Segoe UI", 9, "italic"),
                foreground="gray"
            ).pack(anchor=W, pady=(5, 0))

        # Summary bar
        summary_frame = ttk.Frame(inv_frame)
        summary_frame.pack(fill=X, pady=(10, 0))

        self.inv_summary_label = ttk.Label(
            summary_frame,
            text="0 of {} completed".format(len(valid_investigations)),
            font=("Segoe UI", 9)
        )
        self.inv_summary_label.pack(side=LEFT)

        ttk.Button(
            summary_frame,
            text="Update Status in Database",
            command=self._save_investigation_status,
            bootstyle="info-outline",
            width=25
        ).pack(side=RIGHT)

    def _on_investigation_toggle(self, idx: int) -> None:
        """Handle investigation checkbox toggle.

        Args:
            idx: Investigation index
        """
        # Update summary
        completed = sum(1 for v in self.investigation_vars.values() if v['var'].get())
        total = len(self.investigation_vars)
        self.inv_summary_label.config(text=f"{completed} of {total} completed")

    def _save_investigation_status(self) -> None:
        """Save investigation completion status to database."""
        try:
            db = self._get_database()
            updated = 0

            for idx, data in self.investigation_vars.items():
                inv = data['investigation']
                is_completed = data['var'].get()
                status = 'completed' if is_completed else 'pending'

                # Update if has database ID
                if inv.get('id'):
                    db.update_investigation_status(
                        inv['id'],
                        status=status,
                        result_summary=None
                    )
                    updated += 1

            messagebox.showinfo(
                "Updated",
                f"Investigation status updated for {updated} items.",
                parent=self.dialog if self.dialog else self.parent
            )
        except Exception as e:
            logger.error(f"Error saving investigation status: {e}")
            messagebox.showerror(
                "Error",
                f"Failed to save status: {e}",
                parent=self.dialog if self.dialog else self.parent
            )


__all__ = ["PanelsMixin"]
