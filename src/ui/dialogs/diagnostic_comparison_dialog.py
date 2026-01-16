"""
Diagnostic Comparison Dialog

Provides side-by-side comparison of multiple diagnostic analyses to track
differential evolution and compare findings across time or specialties.
"""

import tkinter as tk
from ui.scaling_utils import ui_scaler
import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, X, Y, HORIZONTAL, VERTICAL, LEFT, RIGHT, BOTTOM, CENTER, N, S, W, EW
from tkinter import messagebox
import logging
import re
from typing import Dict, List, Optional, Any
import json
from datetime import datetime
from database.database import Database


class DiagnosticComparisonDialog:
    """Dialog for comparing multiple diagnostic analyses side by side."""

    def __init__(self, parent, on_select_callback=None):
        """Initialize the diagnostic comparison dialog.

        Args:
            parent: Parent window
            on_select_callback: Optional callback when selecting analyses to compare
        """
        self.parent = parent
        self.on_select_callback = on_select_callback
        self.dialog: Optional[tk.Toplevel] = None
        self._db: Optional[Database] = None
        self.analyses: List[Dict] = []
        self.selected_analyses: List[Dict] = []

    def _get_database(self) -> Database:
        """Get or create database connection."""
        if self._db is None:
            self._db = Database()
        return self._db

    def show(self):
        """Show the comparison dialog."""
        # Create dialog window
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Compare Diagnostic Analyses")
        dialog_width, dialog_height = ui_scaler.get_dialog_size(1200, 800)
        self.dialog.geometry(f"{dialog_width}x{dialog_height}")
        self.dialog.minsize(1100, 700)
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

        # Main container with paned window
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=X, pady=(0, 10))

        ttk.Label(
            header_frame,
            text="Compare Diagnostic Analyses",
            font=("Segoe UI", 14, "bold")
        ).pack(side=LEFT)

        ttk.Label(
            header_frame,
            text="Select 2-4 analyses to compare side by side",
            font=("Segoe UI", 10),
            foreground="gray"
        ).pack(side=LEFT, padx=(20, 0))

        # Paned window for selection and comparison
        paned = ttk.Panedwindow(main_frame, orient=HORIZONTAL)
        paned.pack(fill=BOTH, expand=True)

        # Left panel - Selection
        self._create_selection_panel(paned)

        # Right panel - Comparison view
        self._create_comparison_panel(paned)

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=X, pady=(10, 0))

        ttk.Button(
            button_frame,
            text="Compare Selected",
            command=self._compare_selected,
            bootstyle="primary",
            width=18
        ).pack(side=LEFT, padx=(0, 5))

        ttk.Button(
            button_frame,
            text="Clear Selection",
            command=self._clear_selection,
            bootstyle="secondary-outline",
            width=15
        ).pack(side=LEFT, padx=(0, 5))

        ttk.Button(
            button_frame,
            text="Export Comparison",
            command=self._export_comparison,
            bootstyle="info-outline",
            width=18
        ).pack(side=LEFT)

        ttk.Button(
            button_frame,
            text="Close",
            command=self.dialog.destroy,
            width=12
        ).pack(side=RIGHT)

        # Load analyses
        self._load_analyses()

        # Keyboard shortcuts
        self.dialog.bind("<Escape>", lambda e: self.dialog.destroy())

    def _create_selection_panel(self, paned: ttk.Panedwindow) -> None:
        """Create the left panel for analysis selection.

        Args:
            paned: Parent paned window
        """
        selection_frame = ttk.Frame(paned, padding=5)
        paned.add(selection_frame, weight=1)

        # Filter row
        filter_frame = ttk.Frame(selection_frame)
        filter_frame.pack(fill=X, pady=(0, 5))

        ttk.Label(filter_frame, text="Filter:").pack(side=LEFT, padx=(0, 5))

        self.filter_var = tk.StringVar(value="all")
        filter_options = [("All", "all"), ("7 Days", "7days"), ("30 Days", "30days")]
        for label, value in filter_options:
            ttk.Radiobutton(
                filter_frame,
                text=label,
                variable=self.filter_var,
                value=value,
                command=self._load_analyses
            ).pack(side=LEFT, padx=3)

        # Search
        ttk.Label(filter_frame, text="Search:").pack(side=LEFT, padx=(15, 5))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(filter_frame, textvariable=self.search_var, width=20)
        search_entry.pack(side=LEFT)
        search_entry.bind("<Return>", lambda e: self._filter_analyses())

        # Treeview for selection (with checkboxes simulated)
        tree_frame = ttk.Frame(selection_frame)
        tree_frame.pack(fill=BOTH, expand=True)

        columns = ("select", "date", "specialty", "diffs", "source")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="extended",
            height=20
        )

        self.tree.heading("select", text="✓")
        self.tree.heading("date", text="Date")
        self.tree.heading("specialty", text="Specialty")
        self.tree.heading("diffs", text="# Diffs")
        self.tree.heading("source", text="Source")

        self.tree.column("select", width=30, anchor=CENTER)
        self.tree.column("date", width=120, anchor=W)
        self.tree.column("specialty", width=100, anchor=W)
        self.tree.column("diffs", width=60, anchor=CENTER)
        self.tree.column("source", width=80, anchor=W)

        scrollbar = ttk.Scrollbar(tree_frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        # Bind click to toggle selection
        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<Double-1>", self._on_tree_double_click)

        # Selection counter
        self.selection_label = ttk.Label(
            selection_frame,
            text="0 analyses selected",
            font=("Segoe UI", 9)
        )
        self.selection_label.pack(anchor=W, pady=(5, 0))

    def _create_comparison_panel(self, paned: ttk.Panedwindow) -> None:
        """Create the right panel for comparison view.

        Args:
            paned: Parent paned window
        """
        comparison_frame = ttk.Frame(paned, padding=5)
        paned.add(comparison_frame, weight=3)

        ttk.Label(
            comparison_frame,
            text="Comparison View",
            font=("Segoe UI", 12, "bold")
        ).pack(anchor=W, pady=(0, 5))

        # Notebook for different comparison views
        self.comparison_notebook = ttk.Notebook(comparison_frame)
        self.comparison_notebook.pack(fill=BOTH, expand=True)

        # Tab 1: Side by Side
        self.side_by_side_frame = ttk.Frame(self.comparison_notebook)
        self.comparison_notebook.add(self.side_by_side_frame, text="Side by Side")

        # Tab 2: Differential Matrix
        self.matrix_frame = ttk.Frame(self.comparison_notebook)
        self.comparison_notebook.add(self.matrix_frame, text="Differential Matrix")

        # Tab 3: Timeline
        self.timeline_frame = ttk.Frame(self.comparison_notebook)
        self.comparison_notebook.add(self.timeline_frame, text="Timeline")

        # Initial placeholder
        ttk.Label(
            self.side_by_side_frame,
            text="Select 2-4 analyses and click 'Compare Selected' to view comparison",
            font=("Segoe UI", 11),
            foreground="gray"
        ).pack(expand=True)

    def _load_analyses(self) -> None:
        """Load analyses from database."""
        try:
            db = self._get_database()
            filter_val = self.filter_var.get()

            # Get analyses
            self.analyses = db.get_recent_analysis_results(
                analysis_type="diagnostic",
                limit=100
            )

            # Filter by date
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
                            filtered.append(a)
                    except (ValueError, TypeError):
                        filtered.append(a)
                self.analyses = filtered

            # Clear tree
            for item in self.tree.get_children():
                self.tree.delete(item)

            # Populate tree
            for analysis in self.analyses:
                self._add_analysis_to_tree(analysis)

        except Exception as e:
            logging.error(f"Error loading analyses: {e}")

    def _add_analysis_to_tree(self, analysis: Dict) -> None:
        """Add an analysis to the selection tree.

        Args:
            analysis: Analysis dictionary
        """
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

        specialty = metadata.get('specialty', 'general').title()
        diff_count = metadata.get('differential_count', '?')
        source = analysis.get('source_type', 'Unknown')

        # Check mark based on selection
        is_selected = analysis.get('id') in [a.get('id') for a in self.selected_analyses]
        check = "✓" if is_selected else ""

        self.tree.insert("", END, values=(
            check,
            date_str,
            specialty,
            diff_count,
            source
        ), tags=(str(analysis.get('id', '')),))

    def _on_tree_click(self, event) -> None:
        """Handle tree click for selection toggle.

        Args:
            event: Click event
        """
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        column = self.tree.identify_column(event.x)
        item = self.tree.identify_row(event.y)

        if not item:
            return

        # Get analysis ID from tags
        tags = self.tree.item(item, "tags")
        if not tags:
            return

        analysis_id = int(tags[0])

        # Find analysis
        analysis = None
        for a in self.analyses:
            if a.get('id') == analysis_id:
                analysis = a
                break

        if not analysis:
            return

        # Toggle selection
        is_selected = analysis in self.selected_analyses
        if is_selected:
            self.selected_analyses.remove(analysis)
        else:
            if len(self.selected_analyses) >= 4:
                messagebox.showinfo(
                    "Limit Reached",
                    "You can compare up to 4 analyses at a time.",
                    parent=self.dialog
                )
                return
            self.selected_analyses.append(analysis)

        # Update tree display
        new_check = "✓" if not is_selected else ""
        values = list(self.tree.item(item, "values"))
        values[0] = new_check
        self.tree.item(item, values=values)

        # Update counter
        self.selection_label.config(
            text=f"{len(self.selected_analyses)} analyses selected"
        )

    def _on_tree_double_click(self, event) -> None:
        """Handle double-click to preview analysis.

        Args:
            event: Click event
        """
        item = self.tree.identify_row(event.y)
        if not item:
            return

        tags = self.tree.item(item, "tags")
        if not tags:
            return

        analysis_id = int(tags[0])

        for a in self.analyses:
            if a.get('id') == analysis_id:
                self._show_preview(a)
                break

    def _show_preview(self, analysis: Dict) -> None:
        """Show a preview of an analysis.

        Args:
            analysis: Analysis to preview
        """
        preview = tk.Toplevel(self.dialog)
        preview.title("Analysis Preview")
        preview.geometry("600x400")
        preview.transient(self.dialog)

        text = tk.Text(preview, wrap=tk.WORD, font=("Segoe UI", 10), padx=10, pady=10)
        text.pack(fill=BOTH, expand=True, padx=10, pady=10)

        scrollbar = ttk.Scrollbar(text, orient=VERTICAL, command=text.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        text.config(yscrollcommand=scrollbar.set)

        text.insert("1.0", analysis.get('result_text', 'No content'))
        text.config(state=tk.DISABLED)

        ttk.Button(
            preview,
            text="Close",
            command=preview.destroy,
            width=15
        ).pack(pady=10)

    def _clear_selection(self) -> None:
        """Clear all selections."""
        self.selected_analyses = []
        self._load_analyses()
        self.selection_label.config(text="0 analyses selected")

    def _compare_selected(self) -> None:
        """Compare the selected analyses."""
        if len(self.selected_analyses) < 2:
            messagebox.showinfo(
                "Not Enough",
                "Please select at least 2 analyses to compare.",
                parent=self.dialog
            )
            return

        # Clear existing comparison
        for widget in self.side_by_side_frame.winfo_children():
            widget.destroy()
        for widget in self.matrix_frame.winfo_children():
            widget.destroy()
        for widget in self.timeline_frame.winfo_children():
            widget.destroy()

        # Create side-by-side comparison
        self._create_side_by_side_view()

        # Create differential matrix
        self._create_differential_matrix()

        # Create timeline view
        self._create_timeline_view()

    def _create_side_by_side_view(self) -> None:
        """Create side-by-side comparison view."""
        # Container for columns
        container = ttk.Frame(self.side_by_side_frame)
        container.pack(fill=BOTH, expand=True, padx=5, pady=5)

        num_analyses = len(self.selected_analyses)
        for i, analysis in enumerate(self.selected_analyses):
            # Column frame
            col_frame = ttk.Labelframe(
                container,
                text=f"Analysis {i+1}",
                padding=5
            )
            col_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=2)

            # Metadata
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

            # Header info
            created = analysis.get('created_at', '')[:16]
            specialty = metadata.get('specialty', 'general').title()
            diff_count = metadata.get('differential_count', '?')

            ttk.Label(
                col_frame,
                text=f"Date: {created}",
                font=("Segoe UI", 9)
            ).pack(anchor=W)

            ttk.Label(
                col_frame,
                text=f"Specialty: {specialty}",
                font=("Segoe UI", 9)
            ).pack(anchor=W)

            ttk.Label(
                col_frame,
                text=f"Differentials: {diff_count}",
                font=("Segoe UI", 9, "bold")
            ).pack(anchor=W)

            # Separator
            ttk.Separator(col_frame, orient=HORIZONTAL).pack(fill=X, pady=5)

            # Content
            text_frame = ttk.Frame(col_frame)
            text_frame.pack(fill=BOTH, expand=True)

            text = tk.Text(
                text_frame,
                wrap=tk.WORD,
                font=("Segoe UI", 9),
                padx=5,
                pady=5,
                width=30
            )
            text.pack(side=LEFT, fill=BOTH, expand=True)

            scrollbar = ttk.Scrollbar(text_frame, orient=VERTICAL, command=text.yview)
            scrollbar.pack(side=RIGHT, fill=Y)
            text.config(yscrollcommand=scrollbar.set)

            # Insert differentials section only
            result_text = analysis.get('result_text', '')
            diff_section = self._extract_section(result_text, 'DIFFERENTIAL DIAGNOSES:')
            text.insert("1.0", diff_section or "No differentials found")
            text.config(state=tk.DISABLED)

    def _extract_section(self, text: str, section_name: str) -> str:
        """Extract a section from analysis text.

        Args:
            text: Full analysis text
            section_name: Section header to extract

        Returns:
            Section content
        """
        if section_name not in text:
            return ""

        content = text.split(section_name)[1]
        end_markers = ['RED FLAGS:', 'RECOMMENDED INVESTIGATIONS:',
                      'CLINICAL PEARLS:', 'MEDICATION CONSIDERATIONS:']

        for marker in end_markers:
            if marker in content:
                content = content.split(marker)[0]
                break

        return content.strip()

    def _create_differential_matrix(self) -> None:
        """Create a matrix showing common/unique differentials across analyses."""
        # Extract all differentials from each analysis
        all_diagnoses = {}  # diagnosis -> list of analysis indices
        analysis_diagnoses = []  # List of diagnosis sets per analysis

        for i, analysis in enumerate(self.selected_analyses):
            result_text = analysis.get('result_text', '')
            diff_section = self._extract_section(result_text, 'DIFFERENTIAL DIAGNOSES:')

            diagnoses = set()
            for line in diff_section.split('\n'):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-')):
                    # Extract diagnosis name
                    cleaned = re.sub(r'^[\d\.\-\•\*]+\s*', '', line)
                    cleaned = re.sub(r'\([^)]+\)', '', cleaned)  # Remove ICD codes
                    cleaned = re.sub(r'\[(HIGH|MEDIUM|LOW)\]', '', cleaned, flags=re.IGNORECASE)
                    cleaned = cleaned.strip(' :-')
                    if cleaned and len(cleaned) > 3:
                        diagnoses.add(cleaned)
                        if cleaned not in all_diagnoses:
                            all_diagnoses[cleaned] = []
                        all_diagnoses[cleaned].append(i)

            analysis_diagnoses.append(diagnoses)

        # Create matrix view
        canvas = tk.Canvas(self.matrix_frame)
        scrollbar_y = ttk.Scrollbar(self.matrix_frame, orient=VERTICAL, command=canvas.yview)
        scrollbar_x = ttk.Scrollbar(self.matrix_frame, orient=HORIZONTAL, command=canvas.xview)
        matrix_content = ttk.Frame(canvas)

        matrix_content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=matrix_content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        scrollbar_y.pack(side=RIGHT, fill=Y)
        scrollbar_x.pack(side=BOTTOM, fill=X)
        canvas.pack(fill=BOTH, expand=True)

        # Header row
        ttk.Label(
            matrix_content,
            text="Diagnosis",
            font=("Segoe UI", 10, "bold"),
            width=30
        ).grid(row=0, column=0, sticky=W, padx=5, pady=2)

        for i in range(len(self.selected_analyses)):
            ttk.Label(
                matrix_content,
                text=f"Analysis {i+1}",
                font=("Segoe UI", 10, "bold"),
                width=10
            ).grid(row=0, column=i+1, padx=5, pady=2)

        # Separator
        ttk.Separator(matrix_content, orient=HORIZONTAL).grid(
            row=1, column=0, columnspan=len(self.selected_analyses)+1, sticky=EW, pady=5
        )

        # Sort diagnoses by frequency (common ones first)
        sorted_diagnoses = sorted(
            all_diagnoses.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )

        # Data rows
        for row_idx, (diagnosis, indices) in enumerate(sorted_diagnoses[:30], start=2):
            # Diagnosis name
            is_common = len(indices) > 1
            ttk.Label(
                matrix_content,
                text=diagnosis[:40] + "..." if len(diagnosis) > 40 else diagnosis,
                font=("Segoe UI", 9, "bold" if is_common else "normal"),
                foreground="green" if is_common else "black"
            ).grid(row=row_idx, column=0, sticky=W, padx=5, pady=1)

            # Check marks for each analysis
            for i in range(len(self.selected_analyses)):
                marker = "✓" if i in indices else ""
                color = "green" if marker else "gray"
                ttk.Label(
                    matrix_content,
                    text=marker,
                    font=("Segoe UI", 12),
                    foreground=color
                ).grid(row=row_idx, column=i+1, padx=5, pady=1)

        # Legend
        legend_frame = ttk.Frame(matrix_content)
        legend_frame.grid(
            row=len(sorted_diagnoses)+3, column=0,
            columnspan=len(self.selected_analyses)+1,
            sticky=W, pady=(10, 0)
        )

        ttk.Label(
            legend_frame,
            text="Legend: ",
            font=("Segoe UI", 9, "bold")
        ).pack(side=LEFT)

        ttk.Label(
            legend_frame,
            text="Green = Common across analyses",
            font=("Segoe UI", 9),
            foreground="green"
        ).pack(side=LEFT, padx=10)

    def _create_timeline_view(self) -> None:
        """Create a timeline view showing differential evolution."""
        # Sort analyses by date
        sorted_analyses = sorted(
            self.selected_analyses,
            key=lambda a: a.get('created_at', ''),
            reverse=False
        )

        # Create timeline canvas
        canvas_frame = ttk.Frame(self.timeline_frame)
        canvas_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)

        canvas = tk.Canvas(canvas_frame, height=400)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=HORIZONTAL, command=canvas.xview)

        canvas.pack(fill=BOTH, expand=True)
        scrollbar.pack(fill=X)
        canvas.configure(xscrollcommand=scrollbar.set)

        # Draw timeline
        y_center = 200
        x_start = 50
        x_spacing = 250

        for i, analysis in enumerate(sorted_analyses):
            x = x_start + i * x_spacing

            # Draw timeline node
            canvas.create_oval(x-10, y_center-10, x+10, y_center+10, fill="#0d6efd")

            # Draw connecting line
            if i < len(sorted_analyses) - 1:
                canvas.create_line(
                    x+10, y_center, x+x_spacing-10, y_center,
                    fill="#0d6efd", width=2, arrow=tk.LAST
                )

            # Metadata
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

            # Date label
            created = analysis.get('created_at', '')[:16]
            canvas.create_text(
                x, y_center-30,
                text=created,
                font=("Segoe UI", 9),
                anchor=S
            )

            # Specialty label
            specialty = metadata.get('specialty', 'general').title()
            canvas.create_text(
                x, y_center+30,
                text=specialty,
                font=("Segoe UI", 10, "bold"),
                anchor=N
            )

            # Top differentials
            result_text = analysis.get('result_text', '')
            diff_section = self._extract_section(result_text, 'DIFFERENTIAL DIAGNOSES:')
            top_diffs = []
            for line in diff_section.split('\n')[:3]:
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-')):
                    cleaned = re.sub(r'^[\d\.\-\•\*]+\s*', '', line)
                    cleaned = re.sub(r'\([^)]+\)', '', cleaned)
                    cleaned = cleaned.strip()[:30]
                    if cleaned:
                        top_diffs.append(cleaned)

            y_diff = y_center + 50
            for diff in top_diffs:
                canvas.create_text(
                    x, y_diff,
                    text=f"• {diff}",
                    font=("Segoe UI", 8),
                    anchor=N
                )
                y_diff += 15

        # Update scroll region
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _filter_analyses(self) -> None:
        """Filter analyses based on search term."""
        query = self.search_var.get().strip().lower()
        if not query:
            self._load_analyses()
            return

        # Clear tree
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Filter and display
        for analysis in self.analyses:
            result_text = analysis.get('result_text', '').lower()
            if query in result_text:
                self._add_analysis_to_tree(analysis)

    def _export_comparison(self) -> None:
        """Export the comparison to a file."""
        if len(self.selected_analyses) < 2:
            messagebox.showinfo(
                "No Comparison",
                "Please compare at least 2 analyses first.",
                parent=self.dialog
            )
            return

        from tkinter import filedialog
        file_path = filedialog.asksaveasfilename(
            parent=self.dialog,
            defaultextension=".txt",
            filetypes=[
                ("Text files", "*.txt"),
                ("JSON files", "*.json"),
                ("All files", "*.*")
            ],
            initialfile="diagnostic_comparison.txt",
            title="Export Comparison"
        )

        if not file_path:
            return

        try:
            if file_path.endswith('.json'):
                # Export as JSON
                export_data = {
                    'comparison_date': datetime.now().isoformat(),
                    'analyses': []
                }
                for analysis in self.selected_analyses:
                    metadata = {}
                    metadata_raw = analysis.get('metadata_json')
                    if isinstance(metadata_raw, dict):
                        metadata = metadata_raw
                    elif isinstance(metadata_raw, str):
                        try:
                            metadata = json.loads(metadata_raw)
                        except (json.JSONDecodeError, ValueError, TypeError) as e:
                            logging.debug(f"Failed to parse metadata JSON: {e}")

                    export_data['analyses'].append({
                        'id': analysis.get('id'),
                        'created_at': analysis.get('created_at'),
                        'specialty': metadata.get('specialty'),
                        'result_text': analysis.get('result_text')
                    })

                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2)
            else:
                # Export as text
                lines = ["=" * 60, "DIAGNOSTIC ANALYSIS COMPARISON", "=" * 60, ""]

                for i, analysis in enumerate(self.selected_analyses, 1):
                    metadata = {}
                    metadata_raw = analysis.get('metadata_json')
                    if isinstance(metadata_raw, dict):
                        metadata = metadata_raw
                    elif isinstance(metadata_raw, str):
                        try:
                            metadata = json.loads(metadata_raw)
                        except (json.JSONDecodeError, ValueError, TypeError) as e:
                            logging.debug(f"Failed to parse metadata JSON: {e}")

                    lines.append(f"--- Analysis {i} ---")
                    lines.append(f"Date: {analysis.get('created_at', 'Unknown')}")
                    lines.append(f"Specialty: {metadata.get('specialty', 'general').title()}")
                    lines.append("")
                    lines.append(analysis.get('result_text', 'No content'))
                    lines.append("")
                    lines.append("-" * 40)
                    lines.append("")

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines))

            messagebox.showinfo(
                "Exported",
                f"Comparison exported to:\n{file_path}",
                parent=self.dialog
            )

        except Exception as e:
            logging.error(f"Error exporting comparison: {e}")
            messagebox.showerror(
                "Error",
                f"Failed to export: {e}",
                parent=self.dialog
            )
