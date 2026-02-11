"""
Guidelines Library Dialog.

Provides an interface to view and manage uploaded clinical guidelines
stored in the remote Neon PostgreSQL database:
- List all guidelines with metadata
- Delete guidelines
- Refresh list
"""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

from utils.structured_logging import get_logger

logger = get_logger(__name__)


class GuidelinesLibraryDialog(tk.Toplevel):
    """Dialog for viewing and managing clinical guidelines."""

    def __init__(
        self,
        parent: tk.Widget,
        on_delete: Optional[Callable[[str], bool]] = None,
        on_refresh: Optional[Callable[[], list]] = None,
    ):
        """Initialize the guidelines library dialog.

        Args:
            parent: Parent widget
            on_delete: Callback for deleting a guideline (returns success)
            on_refresh: Callback to refresh guideline list
        """
        super().__init__(parent)
        self.title("Clinical Guidelines Library")
        self.geometry("950x550")
        self.minsize(700, 400)

        self.on_delete = on_delete
        self.on_refresh = on_refresh
        self.guidelines = []
        self.filtered_guidelines = []

        self._create_widgets()
        self._center_window()
        self._load_guidelines()

        # Non-modal - allow interaction with main app
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
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header with stats
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            header_frame,
            text="Clinical Guidelines Library",
            font=("TkDefaultFont", 14, "bold"),
        ).pack(side=tk.LEFT)

        self.stats_label = ttk.Label(
            header_frame,
            text="",
            foreground="gray",
        )
        self.stats_label.pack(side=tk.RIGHT)

        # Search and filter bar
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(filter_frame, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search)
        search_entry = ttk.Entry(
            filter_frame,
            textvariable=self.search_var,
            width=30,
        )
        search_entry.pack(side=tk.LEFT, padx=(5, 20))

        ttk.Label(filter_frame, text="Specialty:").pack(side=tk.LEFT)
        self.specialty_filter_var = tk.StringVar(value="All")
        specialty_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.specialty_filter_var,
            values=["All"],
            state="readonly",
            width=15,
        )
        specialty_combo.pack(side=tk.LEFT, padx=(5, 20))
        specialty_combo.bind("<<ComboboxSelected>>", self._on_filter_change)
        self._specialty_combo = specialty_combo

        ttk.Label(filter_frame, text="Source:").pack(side=tk.LEFT)
        self.source_filter_var = tk.StringVar(value="All")
        source_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.source_filter_var,
            values=["All"],
            state="readonly",
            width=12,
        )
        source_combo.pack(side=tk.LEFT, padx=(5, 0))
        source_combo.bind("<<ComboboxSelected>>", self._on_filter_change)
        self._source_combo = source_combo

        # Treeview for guidelines
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("title", "specialty", "source", "version", "chunks", "date")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="extended",
        )

        # Define columns
        self.tree.heading("title", text="Title / Filename", command=lambda: self._sort_by("title"))
        self.tree.heading("specialty", text="Specialty", command=lambda: self._sort_by("specialty"))
        self.tree.heading("source", text="Source", command=lambda: self._sort_by("source"))
        self.tree.heading("version", text="Version", command=lambda: self._sort_by("version"))
        self.tree.heading("chunks", text="Chunks", command=lambda: self._sort_by("chunks"))
        self.tree.heading("date", text="Created", command=lambda: self._sort_by("date"))

        self.tree.column("title", width=280, minwidth=150)
        self.tree.column("specialty", width=120, minwidth=80)
        self.tree.column("source", width=90, minwidth=60)
        self.tree.column("version", width=80, minwidth=50)
        self.tree.column("chunks", width=70, minwidth=50)
        self.tree.column("date", width=150, minwidth=100)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Bind selection and double-click for chunk browser (Issue 13)
        self.tree.bind("<<TreeviewSelect>>", self._on_selection_change)
        self.tree.bind("<Double-1>", self._on_double_click)

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        self.delete_button = ttk.Button(
            button_frame,
            text="Delete Selected",
            command=self._delete_selected,
            state=tk.DISABLED,
        )
        self.delete_button.pack(side=tk.LEFT)

        ttk.Button(
            button_frame,
            text="Refresh",
            command=self._refresh_list,
        ).pack(side=tk.LEFT, padx=(10, 0))

        ttk.Button(
            button_frame,
            text="Close",
            command=self.destroy,
        ).pack(side=tk.RIGHT)

        # Loading label
        self.loading_label = ttk.Label(
            main_frame,
            text="Loading guidelines...",
            foreground="gray",
        )

    def _load_guidelines(self):
        """Load guidelines from the remote database.

        Uses cached data from background startup refresh if available,
        providing instant display without a loading spinner.
        """
        # Check for cached guidelines from background startup refresh
        app = self.master
        # Walk up to the root app if needed
        while app and not hasattr(app, 'guidelines_cache'):
            app = getattr(app, 'master', None)
        cached = getattr(app, 'guidelines_cache', None) if app else None

        if cached is not None and isinstance(cached, list):
            # Use cached data — instant display, no spinner
            if app:
                app.guidelines_cache = None  # Clear so Refresh button fetches fresh
            self._on_guidelines_loaded(cached)
            return

        import threading

        self.loading_label.pack(fill=tk.X, pady=5)

        def _fetch():
            try:
                if self.on_refresh:
                    guidelines = self.on_refresh()
                else:
                    from rag.guidelines_vector_store import get_guidelines_vector_store
                    store = get_guidelines_vector_store()
                    guidelines = store.list_guidelines()

                self.after(0, lambda g=guidelines: self._on_guidelines_loaded(g))
            except Exception as e:
                logger.error(f"Failed to load guidelines: {e}")
                error_msg = str(e)
                self.after(0, lambda msg=error_msg: self._on_load_error(msg))

        thread = threading.Thread(target=_fetch, daemon=True)
        thread.start()

    def _on_guidelines_loaded(self, guidelines):
        """Handle loaded guidelines on the main thread."""
        self.loading_label.pack_forget()
        self.guidelines = guidelines
        self.filtered_guidelines = guidelines.copy()
        self._update_filter_options()
        self._populate_tree()
        self._update_stats()

    def _on_load_error(self, error_msg: str):
        """Handle load error."""
        self.loading_label.config(
            text=f"Failed to load guidelines: {error_msg}",
            foreground="red",
        )

    def _update_filter_options(self):
        """Update filter dropdown options based on loaded data."""
        specialties = sorted(set(
            g.specialty for g in self.guidelines if g.specialty
        ))
        self._specialty_combo['values'] = ["All"] + specialties

        sources = sorted(set(
            g.source for g in self.guidelines if g.source
        ))
        self._source_combo['values'] = ["All"] + sources

    def _populate_tree(self):
        """Populate the treeview with guidelines."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        for g in self.filtered_guidelines:
            display_title = g.title or g.filename
            created_str = ""
            if g.created_at:
                try:
                    created_str = g.created_at.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    created_str = str(g.created_at)[:16]

            self.tree.insert(
                "",
                tk.END,
                iid=g.guideline_id,
                values=(
                    display_title,
                    (g.specialty or "").replace("_", " ").title(),
                    g.source or "",
                    g.version or "",
                    g.chunk_count,
                    created_str,
                ),
            )

    def _update_stats(self):
        """Update statistics label."""
        total = len(self.guidelines)
        total_chunks = sum(g.chunk_count for g in self.guidelines)
        specialties = len(set(g.specialty for g in self.guidelines if g.specialty))

        self.stats_label.config(
            text=f"{total} guidelines  |  {specialties} specialties  |  {total_chunks} chunks"
        )

    def _on_search(self, *args):
        """Handle search input."""
        self._apply_filters()

    def _on_filter_change(self, event=None):
        """Handle filter change."""
        self._apply_filters()

    def _apply_filters(self):
        """Apply search and filter criteria."""
        search_text = self.search_var.get().lower()
        specialty_filter = self.specialty_filter_var.get()
        source_filter = self.source_filter_var.get()

        self.filtered_guidelines = []

        for g in self.guidelines:
            # Search filter
            searchable = f"{g.title or ''} {g.filename}".lower()
            if search_text and search_text not in searchable:
                continue

            # Specialty filter
            if specialty_filter != "All":
                if (g.specialty or "") != specialty_filter:
                    continue

            # Source filter
            if source_filter != "All":
                if (g.source or "") != source_filter:
                    continue

            self.filtered_guidelines.append(g)

        self._populate_tree()

    def _sort_by(self, column: str):
        """Sort treeview by column."""
        data = [(self.tree.item(child)["values"], child) for child in self.tree.get_children()]
        col_idx = {"title": 0, "specialty": 1, "source": 2, "version": 3, "chunks": 4, "date": 5}[column]
        data.sort(key=lambda x: str(x[0][col_idx]).lower())

        for idx, (values, item) in enumerate(data):
            self.tree.move(item, "", idx)

    def _on_selection_change(self, event=None):
        """Handle selection change."""
        selection = self.tree.selection()
        has_selection = len(selection) > 0
        self.delete_button.config(state=tk.NORMAL if has_selection else tk.DISABLED)

    def _delete_selected(self):
        """Delete selected guidelines."""
        selection = self.tree.selection()
        if not selection:
            return

        count = len(selection)
        if not messagebox.askyesno(
            "Confirm Delete",
            f"Delete {count} guideline(s)?\n\n"
            "This will remove the guidelines and their embeddings from the remote database.",
            parent=self,
        ):
            return

        deleted = 0
        for gid in selection:
            if self.on_delete:
                if self.on_delete(gid):
                    deleted += 1
                    self.guidelines = [g for g in self.guidelines if g.guideline_id != gid]
            else:
                # Default: use vector store directly
                try:
                    from rag.guidelines_vector_store import get_guidelines_vector_store
                    store = get_guidelines_vector_store()
                    if store.delete_guideline_complete(gid):
                        deleted += 1
                        self.guidelines = [g for g in self.guidelines if g.guideline_id != gid]
                except Exception as e:
                    logger.error(f"Failed to delete guideline {gid}: {e}")

        self._apply_filters()
        self._update_stats()

        messagebox.showinfo(
            "Delete Complete",
            f"Deleted {deleted} of {count} guideline(s).",
            parent=self,
        )

    def _on_double_click(self, event=None):
        """Handle double-click on a guideline to show chunk browser (Issue 13)."""
        selection = self.tree.selection()
        if not selection:
            return

        guideline_id = selection[0]

        # Find the guideline title for the dialog title
        guideline_title = "Guideline Chunks"
        for g in self.guidelines:
            if g.guideline_id == guideline_id:
                guideline_title = g.title or g.filename or "Guideline"
                break

        # Load chunks in background thread
        import threading

        def _fetch_chunks():
            try:
                from rag.guidelines_vector_store import get_guidelines_vector_store
                store = get_guidelines_vector_store()
                chunks = store.get_guideline_chunks(guideline_id)
                self.after(0, lambda c=chunks: self._show_chunk_browser(
                    guideline_title, c
                ))
            except Exception as e:
                logger.error(f"Failed to load chunks for {guideline_id}: {e}")
                error_msg = str(e)
                self.after(0, lambda msg=error_msg: messagebox.showerror(
                    "Error", f"Failed to load chunks: {msg}", parent=self
                ))

        thread = threading.Thread(target=_fetch_chunks, daemon=True)
        thread.start()

    def _show_chunk_browser(self, title: str, chunks: list):
        """Show chunk browser dialog for a guideline."""
        if not chunks:
            messagebox.showinfo(
                "No Chunks",
                "No chunks found for this guideline.",
                parent=self,
            )
            return

        _GuidelineChunkBrowserDialog(self, title, chunks)

    def _refresh_list(self):
        """Refresh the guideline list."""
        self._load_guidelines()


class _GuidelineChunkBrowserDialog(tk.Toplevel):
    """Dialog for browsing chunks of a guideline (Issue 13)."""

    def __init__(self, parent: tk.Widget, title: str, chunks: list):
        super().__init__(parent)
        self.title(f"Chunks: {title}")
        self.geometry("800x600")
        self.minsize(600, 400)

        self.chunks = chunks
        self._create_widgets()
        self._center_window()
        self.transient(parent)

    def _center_window(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Chunk list
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("index", "section_type", "rec_class", "evidence", "preview")
        self.tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )

        self.tree.heading("index", text="#")
        self.tree.heading("section_type", text="Section Type")
        self.tree.heading("rec_class", text="Rec. Class")
        self.tree.heading("evidence", text="Evidence")
        self.tree.heading("preview", text="Text Preview")

        self.tree.column("index", width=40, minwidth=30)
        self.tree.column("section_type", width=120, minwidth=80)
        self.tree.column("rec_class", width=80, minwidth=60)
        self.tree.column("evidence", width=80, minwidth=60)
        self.tree.column("preview", width=400, minwidth=200)

        vsb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        # Bind selection for full text display
        self.tree.bind("<<TreeviewSelect>>", self._on_chunk_select)

        # Full text display
        ttk.Label(main_frame, text="Full Chunk Text:", font=("TkDefaultFont", 10, "bold")).pack(
            anchor=tk.W, pady=(10, 5)
        )
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)

        self.text_widget = tk.Text(
            text_frame,
            wrap=tk.WORD,
            height=8,
            state=tk.DISABLED,
            font=("TkDefaultFont", 9),
        )
        text_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text_widget.yview)
        self.text_widget.configure(yscrollcommand=text_scrollbar.set)
        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Populate
        self._populate_chunks()

        # Close button
        ttk.Button(main_frame, text="Close", command=self.destroy).pack(
            pady=(10, 0), anchor=tk.E
        )

    def _populate_chunks(self):
        for chunk in self.chunks:
            idx = chunk.get("chunk_index", 0)
            section_type = chunk.get("section_type", "recommendation") or ""
            rec_class = chunk.get("recommendation_class", "") or ""
            evidence = chunk.get("evidence_level", "") or ""
            text = chunk.get("chunk_text", "")
            preview = text[:80].replace("\n", " ") + ("..." if len(text) > 80 else "")

            self.tree.insert(
                "",
                tk.END,
                iid=str(idx),
                values=(idx, section_type, rec_class, evidence, preview),
            )

    def _on_chunk_select(self, event=None):
        selection = self.tree.selection()
        if not selection:
            return

        chunk_idx = int(selection[0])
        for chunk in self.chunks:
            if chunk.get("chunk_index") == chunk_idx:
                self.text_widget.config(state=tk.NORMAL)
                self.text_widget.delete("1.0", tk.END)
                self.text_widget.insert("1.0", chunk.get("chunk_text", ""))
                self.text_widget.config(state=tk.DISABLED)
                break
