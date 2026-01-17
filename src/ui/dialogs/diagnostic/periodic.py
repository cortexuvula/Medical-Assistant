"""
Diagnostic Results Periodic Analysis Module

Provides periodic analysis panel and evolution display functionality.
"""

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import X, BOTH, Y, VERTICAL, LEFT, RIGHT, W
import json
from tkinter import messagebox
import pyperclip
from typing import Dict, Optional, TYPE_CHECKING
from utils.structured_logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from database.database import Database


class PeriodicMixin:
    """Mixin for periodic analysis functionality."""

    parent: tk.Tk
    dialog: Optional[tk.Toplevel]
    _db: Optional["Database"]

    def _has_periodic_analyses(self, recording_id: int) -> bool:
        """Check if there are periodic analyses linked to a recording.

        Args:
            recording_id: The recording ID to check

        Returns:
            True if periodic analyses exist
        """
        try:
            db = self._get_database()
            analyses = db.get_recent_analysis_results(
                analysis_type="periodic",
                limit=100
            )

            return any(a.get('recording_id') == recording_id for a in analyses)
        except Exception:
            return False

    def _create_periodic_analysis_panel(
        self,
        parent: ttk.Frame,
        recording_id: Optional[int],
        session_id: Optional[int]
    ) -> None:
        """Create a panel showing linked periodic analysis evolution.

        Args:
            parent: Parent frame
            recording_id: Recording ID to find linked analyses
            session_id: Specific session ID if known
        """
        # Create collapsible panel
        periodic_frame = ttk.Labelframe(
            parent,
            text="📊 Differential Evolution (Periodic Analysis)",
            padding=10
        )
        periodic_frame.pack(fill=X, pady=(0, 10))

        # Get periodic analyses
        db = self._get_database()
        periodic_analyses = []

        try:
            all_periodic = db.get_recent_analysis_results(
                analysis_type="periodic",
                limit=200
            )

            if recording_id:
                periodic_analyses = [
                    a for a in all_periodic
                    if a.get('recording_id') == recording_id
                    and a.get('analysis_subtype') == 'differential_evolution'
                ]
            elif session_id:
                periodic_analyses = [
                    a for a in all_periodic
                    if a.get('id') == session_id
                ]
        except Exception as e:
            logger.error(f"Error loading periodic analyses: {e}")

        if not periodic_analyses:
            ttk.Label(
                periodic_frame,
                text="No periodic analysis data available for this recording.",
                font=("Segoe UI", 9, "italic"),
                foreground="gray"
            ).pack(anchor=W)
            return

        # Get the most recent session
        session = periodic_analyses[0]
        metadata = {}
        metadata_raw = session.get('metadata_json')
        if metadata_raw:
            if isinstance(metadata_raw, dict):
                metadata = metadata_raw
            elif isinstance(metadata_raw, str):
                try:
                    metadata = json.loads(metadata_raw)
                except (json.JSONDecodeError, TypeError):
                    pass

        # Summary info
        info_frame = ttk.Frame(periodic_frame)
        info_frame.pack(fill=X, pady=(0, 5))

        total_analyses = metadata.get('total_analyses', 0)
        duration = metadata.get('total_duration_seconds', 0)
        duration_str = f"{int(duration // 60)}:{int(duration % 60):02d}"

        ttk.Label(
            info_frame,
            text=f"📈 {total_analyses} periodic analyses over {duration_str}",
            font=("Segoe UI", 10, "bold")
        ).pack(side=LEFT)

        # View full evolution button
        ttk.Button(
            info_frame,
            text="View Full Evolution",
            command=lambda: self._show_periodic_evolution(session),
            bootstyle="info-outline",
            width=18
        ).pack(side=RIGHT)

        # Individual analysis timeline (condensed)
        individual = metadata.get('individual_analyses', [])
        if individual:
            timeline_frame = ttk.Frame(periodic_frame)
            timeline_frame.pack(fill=X, pady=(5, 0))

            for i, analysis in enumerate(individual[:5]):
                elapsed = analysis.get('elapsed_seconds', 0)
                time_str = f"{int(elapsed // 60)}:{int(elapsed % 60):02d}"
                diff_count = analysis.get('differential_count', 0)

                ttk.Label(
                    timeline_frame,
                    text=f"#{analysis.get('analysis_number', i+1)} ({time_str}): {diff_count} differentials",
                    font=("Segoe UI", 9)
                ).pack(anchor=W)

            if len(individual) > 5:
                ttk.Label(
                    timeline_frame,
                    text=f"... and {len(individual) - 5} more snapshots",
                    font=("Segoe UI", 8, "italic"),
                    foreground="gray"
                ).pack(anchor=W)

    def _show_periodic_evolution(self, session: Dict) -> None:
        """Show full periodic analysis evolution in a dialog.

        Args:
            session: The periodic session data
        """
        evolution_dialog = tk.Toplevel(self.dialog or self.parent)
        evolution_dialog.title("Differential Evolution Timeline")
        evolution_dialog.geometry("800x600")
        evolution_dialog.transient(self.dialog or self.parent)

        # Main frame
        main = ttk.Frame(evolution_dialog, padding=15)
        main.pack(fill=BOTH, expand=True)

        # Header
        ttk.Label(
            main,
            text="Differential Diagnosis Evolution Over Time",
            font=("Segoe UI", 14, "bold")
        ).pack(anchor=W, pady=(0, 10))

        # Metadata
        metadata = {}
        metadata_raw = session.get('metadata_json')
        if metadata_raw:
            if isinstance(metadata_raw, dict):
                metadata = metadata_raw
            elif isinstance(metadata_raw, str):
                try:
                    metadata = json.loads(metadata_raw)
                except (json.JSONDecodeError, TypeError):
                    pass

        info_frame = ttk.Frame(main)
        info_frame.pack(fill=X, pady=(0, 10))

        total = metadata.get('total_analyses', 0)
        start = metadata.get('session_start', 'Unknown')[:19] if metadata.get('session_start') else 'Unknown'
        end = metadata.get('session_end', 'Unknown')[:19] if metadata.get('session_end') else 'Unknown'

        ttk.Label(info_frame, text=f"Total Snapshots: {total}").pack(side=LEFT, padx=(0, 20))
        ttk.Label(info_frame, text=f"Start: {start}").pack(side=LEFT, padx=(0, 20))
        ttk.Label(info_frame, text=f"End: {end}").pack(side=LEFT)

        # Content - full evolution text
        text_frame = ttk.Frame(main)
        text_frame.pack(fill=BOTH, expand=True, pady=(0, 10))

        text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            padx=10,
            pady=10
        )
        text.pack(side=LEFT, fill=BOTH, expand=True)

        scrollbar = ttk.Scrollbar(text_frame, orient=VERTICAL, command=text.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        text.config(yscrollcommand=scrollbar.set)

        # Insert the evolution text with formatting
        result_text = session.get('result_text', 'No evolution data available.')

        # Configure tags for formatting
        text.tag_configure("header", font=("Segoe UI", 11, "bold"), foreground="#0d6efd")
        text.tag_configure("new", foreground="green", font=("Segoe UI", 10, "bold"))
        text.tag_configure("removed", foreground="red", font=("Segoe UI", 10))
        text.tag_configure("separator", foreground="gray")

        # Parse and format the text
        for line in result_text.split('\n'):
            if line.startswith('Analysis #') or 'recording time:' in line:
                text.insert(tk.END, line + '\n', "header")
            elif '📈 NEW' in line or '✨ NEW' in line or '🆕' in line:
                text.insert(tk.END, line + '\n', "new")
            elif '❌ REMOVED' in line or '🔻' in line:
                text.insert(tk.END, line + '\n', "removed")
            elif line.strip().startswith('─'):
                text.insert(tk.END, line + '\n', "separator")
            else:
                text.insert(tk.END, line + '\n')

        text.config(state=tk.DISABLED)

        # Buttons
        button_frame = ttk.Frame(main)
        button_frame.pack(fill=X)

        ttk.Button(
            button_frame,
            text="Copy to Clipboard",
            command=lambda: self._copy_evolution_text(result_text),
            bootstyle="info-outline",
            width=18
        ).pack(side=LEFT, padx=(0, 5))

        ttk.Button(
            button_frame,
            text="Close",
            command=evolution_dialog.destroy,
            width=15
        ).pack(side=RIGHT)

    def _copy_evolution_text(self, text: str) -> None:
        """Copy evolution text to clipboard.

        Args:
            text: Text to copy
        """
        try:
            pyperclip.copy(text)
            messagebox.showinfo(
                "Copied",
                "Evolution text copied to clipboard.",
                parent=self.dialog if self.dialog else self.parent
            )
        except Exception as e:
            logger.error(f"Error copying evolution text: {e}")
            messagebox.showerror(
                "Error",
                f"Failed to copy: {e}",
                parent=self.dialog if self.dialog else self.parent
            )


__all__ = ["PeriodicMixin"]
