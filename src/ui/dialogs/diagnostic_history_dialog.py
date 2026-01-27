"""
Diagnostic History Dialog

Displays saved diagnostic analyses with the ability to view, re-open, or delete them.
"""

import tkinter as tk
from ui.scaling_utils import ui_scaler
import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, X, Y, VERTICAL, LEFT, RIGHT, CENTER, W, END
from tkinter import messagebox
import re
from typing import Dict, List, Optional, Any
import json
from datetime import datetime
from database.database import Database
from utils.structured_logging import get_logger
from utils.error_handling import ErrorContext

logger = get_logger(__name__)


class DiagnosticHistoryDialog:
    """Dialog for viewing saved diagnostic analysis history."""

    def __init__(self, parent, on_view_callback=None):
        """Initialize the diagnostic history dialog.

        Args:
            parent: Parent window
            on_view_callback: Optional callback when viewing an analysis (receives analysis dict)
        """
        self.parent = parent
        self.on_view_callback = on_view_callback
        self.dialog: Optional[tk.Toplevel] = None
        self._db: Optional[Database] = None
        self.analyses: List[Dict] = []

    def _get_database(self) -> Database:
        """Get or create database connection."""
        if self._db is None:
            self._db = Database()
        return self._db

    def show(self):
        """Show the diagnostic history dialog."""
        # Create dialog window
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Diagnostic Analysis History")
        dialog_width, dialog_height = ui_scaler.get_dialog_size(1000, 750)
        self.dialog.geometry(f"{dialog_width}x{dialog_height}")
        self.dialog.minsize(900, 650)
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - self.dialog.winfo_width()) // 2
        y = (self.dialog.winfo_screenheight() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")

        # Grab focus
        self.dialog.deiconify()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        # Main container
        main_frame = ttk.Frame(self.dialog, padding=15)
        main_frame.pack(fill=BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=X, pady=(0, 10))

        ttk.Label(
            header_frame,
            text="Saved Diagnostic Analyses",
            font=("Segoe UI", 14, "bold")
        ).pack(side=LEFT)

        # Refresh button
        ttk.Button(
            header_frame,
            text="Refresh",
            command=self._load_analyses,
            bootstyle="info-outline",
            width=10
        ).pack(side=RIGHT)

        # Search frame
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=X, pady=(0, 10))

        ttk.Label(search_frame, text="Search:").pack(side=LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        self.search_entry.pack(side=LEFT, padx=(0, 5))
        self.search_entry.bind("<Return>", lambda e: self._search_analyses())
        self.search_entry.bind("<KeyRelease>", self._on_search_key)

        ttk.Button(
            search_frame,
            text="Search",
            command=self._search_analyses,
            bootstyle="primary",
            width=10
        ).pack(side=LEFT, padx=(0, 5))

        ttk.Button(
            search_frame,
            text="Clear",
            command=self._clear_search,
            bootstyle="secondary-outline",
            width=8
        ).pack(side=LEFT)

        # Search type options
        self.search_type_var = tk.StringVar(value="all")
        ttk.Label(search_frame, text="  In:").pack(side=LEFT, padx=(10, 5))
        ttk.Radiobutton(
            search_frame, text="All", variable=self.search_type_var, value="all"
        ).pack(side=LEFT, padx=2)
        ttk.Radiobutton(
            search_frame, text="Diagnoses", variable=self.search_type_var, value="diagnosis"
        ).pack(side=LEFT, padx=2)
        ttk.Radiobutton(
            search_frame, text="ICD Codes", variable=self.search_type_var, value="icd"
        ).pack(side=LEFT, padx=2)

        # Filter frame
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill=X, pady=(0, 10))

        ttk.Label(filter_frame, text="Show:").pack(side=LEFT, padx=(0, 5))

        self.filter_var = tk.StringVar(value="all")
        filter_options = [
            ("All", "all"),
            ("Last 7 Days", "7days"),
            ("Last 30 Days", "30days"),
            ("Linked to Recordings", "linked")
        ]
        for label, value in filter_options:
            ttk.Radiobutton(
                filter_frame,
                text=label,
                variable=self.filter_var,
                value=value,
                command=self._load_analyses
            ).pack(side=LEFT, padx=5)

        # Treeview for analyses list
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=BOTH, expand=True, pady=(0, 10))

        columns = ("date", "specialty", "differentials", "red_flags", "source", "recording")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

        # Define column headings
        self.tree.heading("date", text="Date/Time")
        self.tree.heading("specialty", text="Specialty")
        self.tree.heading("differentials", text="# Differentials")
        self.tree.heading("red_flags", text="Red Flags")
        self.tree.heading("source", text="Source")
        self.tree.heading("recording", text="Recording ID")

        # Define column widths
        self.tree.column("date", width=150, anchor=W)
        self.tree.column("specialty", width=120, anchor=W)
        self.tree.column("differentials", width=100, anchor=CENTER)
        self.tree.column("red_flags", width=80, anchor=CENTER)
        self.tree.column("source", width=100, anchor=W)
        self.tree.column("recording", width=100, anchor=CENTER)

        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        # Bind double-click to view
        self.tree.bind("<Double-1>", lambda e: self._view_selected())

        # Preview frame
        preview_frame = ttk.Labelframe(main_frame, text="Preview", padding=10)
        preview_frame.pack(fill=X, pady=(0, 10))

        self.preview_text = tk.Text(
            preview_frame,
            wrap=tk.WORD,
            height=6,
            font=("Segoe UI", 10),
            state=tk.DISABLED
        )
        self.preview_text.pack(fill=X)

        # Bind selection to preview
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=X)

        ttk.Button(
            button_frame,
            text="View Full Analysis",
            command=self._view_selected,
            bootstyle="primary",
            width=18
        ).pack(side=LEFT, padx=(0, 5))

        ttk.Button(
            button_frame,
            text="Copy to Clipboard",
            command=self._copy_selected,
            bootstyle="info",
            width=18
        ).pack(side=LEFT, padx=(0, 5))

        ttk.Button(
            button_frame,
            text="Delete",
            command=self._delete_selected,
            bootstyle="danger-outline",
            width=12
        ).pack(side=LEFT)

        ttk.Button(
            button_frame,
            text="Close",
            command=self.dialog.destroy,
            width=12
        ).pack(side=RIGHT)

        # Load analyses
        self._load_analyses()

        # Bind keyboard shortcuts
        self.dialog.bind("<Escape>", lambda e: self.dialog.destroy())
        self.dialog.bind("<Delete>", lambda e: self._delete_selected())
        self.dialog.bind("<Return>", lambda e: self._view_selected())

    def _load_analyses(self):
        """Load analyses from database based on filter."""
        try:
            db = self._get_database()
            filter_val = self.filter_var.get()

            # Get analyses
            if filter_val == "linked":
                # Only get analyses linked to recordings
                all_analyses = db.get_recent_analysis_results(
                    analysis_type="diagnostic",
                    limit=200
                )
                self.analyses = [a for a in all_analyses if a.get('recording_id')]
            else:
                self.analyses = db.get_recent_analysis_results(
                    analysis_type="diagnostic",
                    limit=200
                )

            # Filter by date if needed
            if filter_val in ("7days", "30days"):
                days = 7 if filter_val == "7days" else 30
                cutoff = datetime.now().timestamp() - (days * 24 * 60 * 60)
                filtered = []
                for a in self.analyses:
                    try:
                        created = a.get('created_at', '')
                        if isinstance(created, str):
                            dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                            if dt.timestamp() >= cutoff:
                                filtered.append(a)
                        else:
                            filtered.append(a)  # Keep if can't parse
                    except (ValueError, TypeError):
                        filtered.append(a)
                self.analyses = filtered

            # Clear tree
            for item in self.tree.get_children():
                self.tree.delete(item)

            # Populate tree
            for analysis in self.analyses:
                # Parse metadata - may already be a dict from _parse_analysis_row
                metadata = {}
                metadata_raw = analysis.get('metadata_json')
                if metadata_raw:
                    if isinstance(metadata_raw, dict):
                        metadata = metadata_raw
                    elif isinstance(metadata_raw, str):
                        try:
                            metadata = json.loads(metadata_raw)
                        except (json.JSONDecodeError, TypeError):
                            pass

                # Format date
                created = analysis.get('created_at', '')
                if isinstance(created, str):
                    try:
                        dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                        date_str = dt.strftime("%Y-%m-%d %H:%M")
                    except ValueError:
                        date_str = created[:16] if len(created) > 16 else created
                else:
                    date_str = str(created)

                # Get values
                specialty = metadata.get('specialty', 'general').title()
                diff_count = metadata.get('differential_count')

                # Fallback: count differentials from result text if not in metadata
                if diff_count is None or diff_count == '?':
                    result_text = analysis.get('result_text', '')
                    if 'DIFFERENTIAL DIAGNOSES:' in result_text:
                        diff_section = result_text.split('DIFFERENTIAL DIAGNOSES:')[1]
                        # Find the end of the section
                        for end_marker in ['RED FLAGS:', 'RECOMMENDED INVESTIGATIONS:', 'CLINICAL PEARLS:', 'MEDICATION CONSIDERATIONS:']:
                            if end_marker in diff_section:
                                diff_section = diff_section.split(end_marker)[0]
                                break
                        # Count numbered or bulleted items
                        numbered = re.findall(r'^\s*\d+\.', diff_section, re.MULTILINE)
                        bulleted = re.findall(r'^\s*[-•]', diff_section, re.MULTILINE)
                        diff_count = len(numbered) or len(bulleted) or '?'
                    else:
                        diff_count = '?'

                has_red_flags = "Yes" if metadata.get('has_red_flags') else "No"
                # Also check result text for red flags
                if has_red_flags == "No" and analysis.get('result_text'):
                    result_text = analysis.get('result_text', '')
                    if 'RED FLAGS:' in result_text:
                        red_section = result_text.split('RED FLAGS:')[1].split('\n')[0:5]
                        if any(line.strip() and line.strip() not in ['None', '-', 'N/A'] for line in red_section):
                            has_red_flags = "Yes"

                source = analysis.get('source_type', 'Unknown')
                recording_id = analysis.get('recording_id', '-')

                self.tree.insert("", END, values=(
                    date_str,
                    specialty,
                    diff_count,
                    has_red_flags,
                    source,
                    recording_id if recording_id else "-"
                ), tags=(str(analysis.get('id', '')),))

            # Update count in header
            logger.info("Loaded diagnostic analyses", count=len(self.analyses))

        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Loading diagnostic analyses",
                exception=e,
                input_summary=f"filter={filter_val}"
            )
            logger.error(ctx.to_log_string())
            messagebox.showerror(
                "Error",
                ctx.user_message,
                parent=self.dialog
            )

    def _on_select(self, event=None):
        """Handle selection change to update preview."""
        selection = self.tree.selection()
        if not selection:
            return

        # Get the selected item's index
        item = selection[0]
        idx = self.tree.index(item)

        if 0 <= idx < len(self.analyses):
            analysis = self.analyses[idx]
            result_text = analysis.get('result_text', '')

            # Update preview (first 500 chars)
            preview = result_text[:500] + "..." if len(result_text) > 500 else result_text

            self.preview_text.config(state=tk.NORMAL)
            self.preview_text.delete("1.0", tk.END)
            self.preview_text.insert("1.0", preview)
            self.preview_text.config(state=tk.DISABLED)

    def _view_selected(self):
        """View the full selected analysis."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo(
                "No Selection",
                "Please select an analysis to view.",
                parent=self.dialog
            )
            return

        item = selection[0]
        idx = self.tree.index(item)

        if 0 <= idx < len(self.analyses):
            analysis = self.analyses[idx]

            # If callback provided, use it
            if self.on_view_callback:
                self.on_view_callback(analysis)
                return

            # Otherwise show in a simple dialog
            self._show_analysis_detail(analysis)

    def _show_analysis_detail(self, analysis: Dict):
        """Show analysis in a detail dialog."""
        detail_dialog = tk.Toplevel(self.dialog)
        detail_dialog.title("Diagnostic Analysis Detail")
        detail_dialog.geometry("800x600")
        detail_dialog.transient(self.dialog)

        # Main frame
        main = ttk.Frame(detail_dialog, padding=15)
        main.pack(fill=BOTH, expand=True)

        # Header info
        header = ttk.Frame(main)
        header.pack(fill=X, pady=(0, 10))

        # Parse metadata - may already be a dict
        metadata = {}
        metadata_raw = analysis.get('metadata_json')
        if metadata_raw:
            if isinstance(metadata_raw, dict):
                metadata = metadata_raw
            elif isinstance(metadata_raw, str):
                try:
                    metadata = json.loads(metadata_raw)
                except (json.JSONDecodeError, TypeError):
                    pass

        ttk.Label(
            header,
            text=f"Created: {analysis.get('created_at', 'Unknown')}",
            font=("Segoe UI", 10)
        ).pack(side=LEFT, padx=(0, 20))

        ttk.Label(
            header,
            text=f"Specialty: {metadata.get('specialty', 'general').title()}",
            font=("Segoe UI", 10)
        ).pack(side=LEFT, padx=(0, 20))

        ttk.Label(
            header,
            text=f"Differentials: {metadata.get('differential_count', '?')}",
            font=("Segoe UI", 10)
        ).pack(side=LEFT)

        # Text area
        text_frame = ttk.Frame(main)
        text_frame.pack(fill=BOTH, expand=True, pady=(0, 10))

        text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=("Segoe UI", 11),
            padx=10,
            pady=10
        )
        text.pack(side=LEFT, fill=BOTH, expand=True)

        scrollbar = ttk.Scrollbar(text_frame, orient=VERTICAL, command=text.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        text.config(yscrollcommand=scrollbar.set)

        text.insert("1.0", analysis.get('result_text', ''))
        text.config(state=tk.DISABLED)

        # Close button
        ttk.Button(
            main,
            text="Close",
            command=detail_dialog.destroy,
            width=15
        ).pack(side=RIGHT)

    def _copy_selected(self):
        """Copy selected analysis to clipboard."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo(
                "No Selection",
                "Please select an analysis to copy.",
                parent=self.dialog
            )
            return

        item = selection[0]
        idx = self.tree.index(item)

        if 0 <= idx < len(self.analyses):
            analysis = self.analyses[idx]
            try:
                import pyperclip
                pyperclip.copy(analysis.get('result_text', ''))
                messagebox.showinfo(
                    "Copied",
                    "Analysis copied to clipboard.",
                    parent=self.dialog
                )
            except ImportError:
                # pyperclip not available, try tkinter clipboard
                try:
                    self.dialog.clipboard_clear()
                    self.dialog.clipboard_append(analysis.get('result_text', ''))
                    self.dialog.update()  # Flush clipboard to macOS pasteboard
                    messagebox.showinfo(
                        "Copied",
                        "Analysis copied to clipboard.",
                        parent=self.dialog
                    )
                except tk.TclError as e:
                    ctx = ErrorContext.capture(
                        operation="Copying to clipboard",
                        exception=e,
                        input_summary=f"analysis_id={analysis.get('id')}"
                    )
                    logger.error(ctx.to_log_string())
                    messagebox.showerror("Error", ctx.user_message, parent=self.dialog)
            except Exception as e:
                ctx = ErrorContext.capture(
                    operation="Copying to clipboard",
                    exception=e,
                    input_summary=f"analysis_id={analysis.get('id')}"
                )
                logger.error(ctx.to_log_string())
                messagebox.showerror("Error", ctx.user_message, parent=self.dialog)

    def _delete_selected(self):
        """Delete selected analysis."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo(
                "No Selection",
                "Please select an analysis to delete.",
                parent=self.dialog
            )
            return

        if not messagebox.askyesno(
            "Confirm Delete",
            "Are you sure you want to delete this analysis?",
            parent=self.dialog
        ):
            return

        item = selection[0]
        idx = self.tree.index(item)

        if 0 <= idx < len(self.analyses):
            analysis = self.analyses[idx]
            analysis_id = analysis.get('id')
            try:
                db = self._get_database()
                db.delete_analysis_result(analysis_id)
                self._load_analyses()
                messagebox.showinfo(
                    "Deleted",
                    "Analysis deleted successfully.",
                    parent=self.dialog
                )
            except Exception as e:
                ctx = ErrorContext.capture(
                    operation="Deleting analysis",
                    exception=e,
                    input_summary=f"analysis_id={analysis_id}"
                )
                logger.error(ctx.to_log_string())
                messagebox.showerror(
                    "Error",
                    ctx.user_message,
                    parent=self.dialog
                )

    def _on_search_key(self, event=None):
        """Handle search key release for live search."""
        # Debounce: only search after a brief pause
        if hasattr(self, '_search_after_id'):
            self.dialog.after_cancel(self._search_after_id)
        self._search_after_id = self.dialog.after(300, self._search_analyses)

    def _search_analyses(self):
        """Search analyses using full-text search."""
        query = self.search_var.get().strip()
        if not query:
            self._load_analyses()
            return

        try:
            db = self._get_database()
            search_type = self.search_type_var.get()

            # Clear current results
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.analyses = []

            # Perform appropriate search based on search type
            if search_type == "diagnosis":
                results = self._search_diagnoses(db, query)
            elif search_type == "icd":
                results = self._search_icd_codes(db, query)
            else:
                results = self._search_full_text(db, query)

            self.analyses = results

            # Populate tree
            for analysis in results:
                self._add_analysis_to_tree(analysis)

            # Update status
            logger.info("Search completed", query=query, result_count=len(results))

        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Searching analyses",
                exception=e,
                input_summary=f"query='{query}', type={search_type}"
            )
            logger.error(ctx.to_log_string())
            messagebox.showerror(
                "Search Error",
                ctx.user_message,
                parent=self.dialog
            )

    def _search_full_text(self, db, query: str) -> List[Dict]:
        """Search using FTS5 full-text search.

        Args:
            db: Database connection
            query: Search query

        Returns:
            List of matching analysis records
        """
        try:
            conn = db._get_connection()

            # Try FTS5 search first
            try:
                cursor = conn.execute(
                    """
                    SELECT ar.*
                    FROM analysis_results ar
                    JOIN analysis_results_fts fts ON ar.id = fts.rowid
                    WHERE analysis_results_fts MATCH ?
                    AND ar.analysis_type = 'diagnostic'
                    ORDER BY ar.created_at DESC
                    LIMIT 100
                    """,
                    (query,)
                )
                results = []
                for row in cursor.fetchall():
                    results.append(db._parse_analysis_row(row))
                return results
            except Exception as e:
                # Fallback to LIKE search if FTS not available
                logger.debug("FTS search failed, falling back to LIKE search", error=str(e))

            # Fallback: LIKE search
            cursor = conn.execute(
                """
                SELECT * FROM analysis_results
                WHERE analysis_type = 'diagnostic'
                AND (result_text LIKE ? OR source_text LIKE ?)
                ORDER BY created_at DESC
                LIMIT 100
                """,
                (f'%{query}%', f'%{query}%')
            )
            results = []
            for row in cursor.fetchall():
                results.append(db._parse_analysis_row(row))
            return results

        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Full-text search",
                exception=e,
                input_summary=f"query='{query}'"
            )
            logger.error(ctx.to_log_string())
            return []

    def _search_diagnoses(self, db, query: str) -> List[Dict]:
        """Search in differential diagnoses table.

        Args:
            db: Database connection
            query: Search query

        Returns:
            List of matching analysis records
        """
        try:
            conn = db._get_connection()

            # Try FTS5 search on differential_diagnoses first
            try:
                cursor = conn.execute(
                    """
                    SELECT DISTINCT ar.*
                    FROM analysis_results ar
                    JOIN differential_diagnoses dd ON ar.id = dd.analysis_id
                    JOIN differential_diagnoses_fts fts ON dd.id = fts.rowid
                    WHERE differential_diagnoses_fts MATCH ?
                    ORDER BY ar.created_at DESC
                    LIMIT 100
                    """,
                    (query,)
                )
                results = []
                for row in cursor.fetchall():
                    results.append(db._parse_analysis_row(row))
                return results
            except Exception as e:
                logger.debug("Diagnosis FTS search failed, falling back to LIKE", error=str(e))

            # Fallback: LIKE search on differential_diagnoses
            cursor = conn.execute(
                """
                SELECT DISTINCT ar.*
                FROM analysis_results ar
                JOIN differential_diagnoses dd ON ar.id = dd.analysis_id
                WHERE dd.diagnosis_name LIKE ?
                ORDER BY ar.created_at DESC
                LIMIT 100
                """,
                (f'%{query}%',)
            )
            results = []
            for row in cursor.fetchall():
                results.append(db._parse_analysis_row(row))
            return results

        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Diagnosis search",
                exception=e,
                input_summary=f"query='{query}'"
            )
            logger.error(ctx.to_log_string())
            # Fallback: search in result_text
            return self._search_full_text(db, query)

    def _search_icd_codes(self, db, query: str) -> List[Dict]:
        """Search by ICD code.

        Args:
            db: Database connection
            query: ICD code to search

        Returns:
            List of matching analysis records
        """
        try:
            conn = db._get_connection()

            # Search in differential_diagnoses table for ICD codes
            cursor = conn.execute(
                """
                SELECT DISTINCT ar.*
                FROM analysis_results ar
                JOIN differential_diagnoses dd ON ar.id = dd.analysis_id
                WHERE dd.icd10_code LIKE ? OR dd.icd9_code LIKE ?
                ORDER BY ar.created_at DESC
                LIMIT 100
                """,
                (f'%{query}%', f'%{query}%')
            )
            results = []
            for row in cursor.fetchall():
                results.append(db._parse_analysis_row(row))

            if results:
                return results

            # Fallback: search in result_text for ICD pattern
            return self._search_full_text(db, query)

        except Exception as e:
            ctx = ErrorContext.capture(
                operation="ICD code search",
                exception=e,
                input_summary=f"query='{query}'"
            )
            logger.error(ctx.to_log_string())
            return self._search_full_text(db, query)

    def _clear_search(self):
        """Clear search and reload all analyses."""
        self.search_var.set("")
        self._load_analyses()

    def _add_analysis_to_tree(self, analysis: Dict):
        """Add an analysis to the treeview.

        Args:
            analysis: Analysis dictionary to add
        """
        # Parse metadata - may already be a dict from _parse_analysis_row
        metadata = {}
        metadata_raw = analysis.get('metadata_json')
        if metadata_raw:
            if isinstance(metadata_raw, dict):
                metadata = metadata_raw
            elif isinstance(metadata_raw, str):
                try:
                    metadata = json.loads(metadata_raw)
                except (json.JSONDecodeError, TypeError):
                    pass

        # Format date
        created = analysis.get('created_at', '')
        if isinstance(created, str):
            try:
                dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                date_str = dt.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                date_str = created[:16] if len(created) > 16 else created
        else:
            date_str = str(created)

        # Get values
        specialty = metadata.get('specialty', 'general').title()
        diff_count = metadata.get('differential_count')

        # Fallback: count differentials from result text if not in metadata
        if diff_count is None or diff_count == '?':
            result_text = analysis.get('result_text', '')
            if 'DIFFERENTIAL DIAGNOSES:' in result_text:
                diff_section = result_text.split('DIFFERENTIAL DIAGNOSES:')[1]
                for end_marker in ['RED FLAGS:', 'RECOMMENDED INVESTIGATIONS:', 'CLINICAL PEARLS:', 'MEDICATION CONSIDERATIONS:']:
                    if end_marker in diff_section:
                        diff_section = diff_section.split(end_marker)[0]
                        break
                numbered = re.findall(r'^\s*\d+\.', diff_section, re.MULTILINE)
                bulleted = re.findall(r'^\s*[-•]', diff_section, re.MULTILINE)
                diff_count = len(numbered) or len(bulleted) or '?'
            else:
                diff_count = '?'

        has_red_flags = "Yes" if metadata.get('has_red_flags') else "No"
        if has_red_flags == "No" and analysis.get('result_text'):
            result_text = analysis.get('result_text', '')
            if 'RED FLAGS:' in result_text:
                red_section = result_text.split('RED FLAGS:')[1].split('\n')[0:5]
                if any(line.strip() and line.strip() not in ['None', '-', 'N/A'] for line in red_section):
                    has_red_flags = "Yes"

        source = analysis.get('source_type', 'Unknown')
        recording_id = analysis.get('recording_id', '-')

        self.tree.insert("", END, values=(
            date_str,
            specialty,
            diff_count,
            has_red_flags,
            source,
            recording_id if recording_id else "-"
        ), tags=(str(analysis.get('id', '')),))
