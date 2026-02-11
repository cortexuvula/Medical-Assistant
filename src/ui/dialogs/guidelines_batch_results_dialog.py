"""
Guidelines Batch Results Dialog.

Shows detailed per-file results after a batch guideline upload completes.
Includes status icons, error messages, and a "Retry Failed" button.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from utils.structured_logging import get_logger

logger = get_logger(__name__)


class GuidelinesBatchResultsDialog(tk.Toplevel):
    """Dialog showing detailed per-file results from a batch upload."""

    def __init__(
        self,
        parent: tk.Widget,
        results: list[dict],
        on_retry: Optional[Callable[[list[str]], None]] = None,
    ):
        """Initialize the batch results dialog.

        Args:
            parent: Parent widget
            results: List of dicts with keys:
                - filename: str
                - file_path: str
                - status: str ('success', 'failed', 'skipped')
                - error: Optional[str]
                - guideline_id: Optional[str]
            on_retry: Callback to retry failed files (receives list of file paths)
        """
        super().__init__(parent)
        self.title("Batch Upload Results")
        self.geometry("700x500")
        self.minsize(550, 350)

        self.results = results
        self.on_retry = on_retry

        self._create_widgets()
        self._populate_results()
        self._center_window()

        self.transient(parent)

    def _center_window(self):
        """Center the dialog on screen."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        """Create dialog widgets."""
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Summary header
        success_count = sum(1 for r in self.results if r.get("status") == "success")
        failed_count = sum(1 for r in self.results if r.get("status") == "failed")
        skipped_count = sum(1 for r in self.results if r.get("status") == "skipped")
        total = len(self.results)

        summary_text = f"Processed {total} files"
        parts = []
        if success_count:
            parts.append(f"{success_count} succeeded")
        if skipped_count:
            parts.append(f"{skipped_count} skipped")
        if failed_count:
            parts.append(f"{failed_count} failed")
        if parts:
            summary_text += f": {', '.join(parts)}"

        ttk.Label(
            main_frame,
            text=summary_text,
            font=("TkDefaultFont", 12, "bold"),
        ).pack(anchor=tk.W, pady=(0, 10))

        # Treeview for results
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("status", "filename", "error")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="extended",
        )

        self.tree.heading("status", text="Status")
        self.tree.heading("filename", text="Filename")
        self.tree.heading("error", text="Details")

        self.tree.column("status", width=80, minwidth=60)
        self.tree.column("filename", width=250, minwidth=150)
        self.tree.column("error", width=300, minwidth=100)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        self.retry_button = ttk.Button(
            button_frame,
            text="Retry Failed",
            command=self._retry_failed,
            state=tk.DISABLED,
        )
        self.retry_button.pack(side=tk.LEFT)

        ttk.Button(
            button_frame,
            text="Close",
            command=self.destroy,
        ).pack(side=tk.RIGHT)

    def _populate_results(self):
        """Populate the treeview with results."""
        has_failures = False

        for result in self.results:
            status = result.get("status", "unknown")
            filename = result.get("filename", "Unknown")
            error = result.get("error", "")

            # Status display
            status_map = {
                "success": "OK",
                "failed": "FAILED",
                "skipped": "Skipped",
            }
            status_display = status_map.get(status, status)

            if status == "skipped" and not error:
                error = "Duplicate"

            self.tree.insert(
                "",
                tk.END,
                values=(status_display, filename, error),
                tags=(status,),
            )

            if status == "failed":
                has_failures = True

        # Color tags
        self.tree.tag_configure("success", foreground="green")
        self.tree.tag_configure("failed", foreground="red")
        self.tree.tag_configure("skipped", foreground="gray")

        # Enable retry button if there are failures
        if has_failures and self.on_retry:
            self.retry_button.config(state=tk.NORMAL)

    def _retry_failed(self):
        """Retry all failed uploads."""
        failed_paths = [
            r["file_path"] for r in self.results
            if r.get("status") == "failed" and r.get("file_path")
        ]

        if failed_paths and self.on_retry:
            self.on_retry(failed_paths)
            self.destroy()
