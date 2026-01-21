"""
RAG Document Library Dialog.

Provides an interface to view and manage uploaded documents:
- List all documents with status
- Search and filter
- Delete documents
- View document details
"""

import json
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Callable, Optional

from src.rag.models import DocumentListItem, DocumentType, UploadStatus


class RAGDocumentLibraryDialog(tk.Toplevel):
    """Dialog for viewing and managing RAG documents."""

    def __init__(
        self,
        parent: tk.Widget,
        documents: list[DocumentListItem],
        on_delete: Optional[Callable[[str], bool]] = None,
        on_refresh: Optional[Callable[[], list[DocumentListItem]]] = None,
        on_reprocess: Optional[Callable[[str], None]] = None,
    ):
        """Initialize the document library dialog.

        Args:
            parent: Parent widget
            documents: List of documents to display
            on_delete: Callback for deleting a document (returns success)
            on_refresh: Callback to refresh document list
            on_reprocess: Callback to reprocess a failed document
        """
        super().__init__(parent)
        self.title("RAG Document Library")
        self.geometry("900x600")
        self.minsize(700, 400)

        self.documents = documents
        self.on_delete = on_delete
        self.on_refresh = on_refresh
        self.on_reprocess = on_reprocess
        self.filtered_documents = documents.copy()

        self._create_widgets()
        self._populate_tree()
        self._center_window()

        # Make modal
        self.transient(parent)
        self.grab_set()

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
            text="Document Library",
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

        ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT)
        self.status_filter_var = tk.StringVar(value="All")
        status_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.status_filter_var,
            values=["All", "Completed", "Processing", "Failed"],
            state="readonly",
            width=12,
        )
        status_combo.pack(side=tk.LEFT, padx=(5, 20))
        status_combo.bind("<<ComboboxSelected>>", self._on_filter_change)

        ttk.Label(filter_frame, text="Type:").pack(side=tk.LEFT)
        self.type_filter_var = tk.StringVar(value="All")
        type_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.type_filter_var,
            values=["All", "PDF", "DOCX", "TXT", "Image"],
            state="readonly",
            width=10,
        )
        type_combo.pack(side=tk.LEFT, padx=(5, 0))
        type_combo.bind("<<ComboboxSelected>>", self._on_filter_change)

        # Treeview for documents
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("filename", "type", "size", "chunks", "status", "created")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="extended",
        )

        # Define columns
        self.tree.heading("filename", text="Filename", command=lambda: self._sort_by("filename"))
        self.tree.heading("type", text="Type", command=lambda: self._sort_by("type"))
        self.tree.heading("size", text="Size", command=lambda: self._sort_by("size"))
        self.tree.heading("chunks", text="Chunks", command=lambda: self._sort_by("chunks"))
        self.tree.heading("status", text="Status", command=lambda: self._sort_by("status"))
        self.tree.heading("created", text="Created", command=lambda: self._sort_by("created"))

        self.tree.column("filename", width=250, minwidth=150)
        self.tree.column("type", width=70, minwidth=50)
        self.tree.column("size", width=80, minwidth=60)
        self.tree.column("chunks", width=70, minwidth=50)
        self.tree.column("status", width=100, minwidth=80)
        self.tree.column("created", width=150, minwidth=100)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Bind double-click for details
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<<TreeviewSelect>>", self._on_selection_change)

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

        self.reprocess_button = ttk.Button(
            button_frame,
            text="Reprocess",
            command=self._reprocess_selected,
            state=tk.DISABLED,
        )
        self.reprocess_button.pack(side=tk.LEFT, padx=(10, 0))

        self.details_button = ttk.Button(
            button_frame,
            text="View Details",
            command=self._view_details,
            state=tk.DISABLED,
        )
        self.details_button.pack(side=tk.LEFT, padx=(10, 0))

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

        # Update stats
        self._update_stats()

    def _populate_tree(self):
        """Populate the treeview with documents."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Add documents
        for doc in self.filtered_documents:
            status_icon = self._get_status_icon(doc.upload_status)
            created_str = doc.created_at.strftime("%Y-%m-%d %H:%M")

            self.tree.insert(
                "",
                tk.END,
                iid=doc.document_id,
                values=(
                    doc.filename,
                    doc.file_type.upper() if isinstance(doc.file_type, str) else doc.file_type.value.upper(),
                    self._format_size(doc.file_size_bytes),
                    doc.chunk_count,
                    f"{status_icon} {self._get_status_text(doc.upload_status)}",
                    created_str,
                ),
                tags=(doc.upload_status,),
            )

        # Configure tags for status colors
        self.tree.tag_configure(UploadStatus.COMPLETED, foreground="green")
        self.tree.tag_configure(UploadStatus.FAILED, foreground="red")
        self.tree.tag_configure(UploadStatus.EMBEDDING, foreground="blue")
        self.tree.tag_configure(UploadStatus.SYNCING, foreground="blue")

    def _get_status_icon(self, status) -> str:
        """Get icon for status."""
        if isinstance(status, str):
            status = UploadStatus(status)

        icons = {
            UploadStatus.COMPLETED: "✓",
            UploadStatus.FAILED: "✗",
            UploadStatus.PENDING: "○",
            UploadStatus.EXTRACTING: "⟳",
            UploadStatus.CHUNKING: "⟳",
            UploadStatus.EMBEDDING: "⟳",
            UploadStatus.SYNCING: "⟳",
        }
        return icons.get(status, "○")

    def _get_status_text(self, status) -> str:
        """Get display text for status."""
        if isinstance(status, str):
            status = UploadStatus(status)

        texts = {
            UploadStatus.COMPLETED: "Complete",
            UploadStatus.FAILED: "Failed",
            UploadStatus.PENDING: "Pending",
            UploadStatus.EXTRACTING: "Extracting",
            UploadStatus.CHUNKING: "Chunking",
            UploadStatus.EMBEDDING: "Embedding",
            UploadStatus.SYNCING: "Syncing",
        }
        return texts.get(status, str(status))

    def _format_size(self, size_bytes: int) -> str:
        """Format file size."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    def _update_stats(self):
        """Update statistics label."""
        total = len(self.documents)
        completed = sum(1 for d in self.documents if d.upload_status == UploadStatus.COMPLETED)
        failed = sum(1 for d in self.documents if d.upload_status == UploadStatus.FAILED)
        total_chunks = sum(d.chunk_count for d in self.documents)

        self.stats_label.config(
            text=f"{total} documents  |  {completed} completed  |  {failed} failed  |  {total_chunks} chunks"
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
        status_filter = self.status_filter_var.get()
        type_filter = self.type_filter_var.get()

        self.filtered_documents = []

        for doc in self.documents:
            # Search filter
            if search_text and search_text not in doc.filename.lower():
                continue

            # Status filter
            if status_filter != "All":
                if status_filter == "Completed" and doc.upload_status != UploadStatus.COMPLETED:
                    continue
                if status_filter == "Failed" and doc.upload_status != UploadStatus.FAILED:
                    continue
                if status_filter == "Processing" and doc.upload_status in [UploadStatus.COMPLETED, UploadStatus.FAILED]:
                    continue

            # Type filter
            if type_filter != "All":
                doc_type = doc.file_type if isinstance(doc.file_type, str) else doc.file_type.value
                if type_filter.lower() != doc_type.lower():
                    continue

            self.filtered_documents.append(doc)

        self._populate_tree()

    def _sort_by(self, column: str):
        """Sort treeview by column."""
        # Get current data
        data = [(self.tree.item(child)["values"], child) for child in self.tree.get_children()]

        # Determine sort key
        col_idx = {"filename": 0, "type": 1, "size": 2, "chunks": 3, "status": 4, "created": 5}[column]

        # Sort
        data.sort(key=lambda x: x[0][col_idx])

        # Rearrange items
        for idx, (values, item) in enumerate(data):
            self.tree.move(item, "", idx)

    def _on_selection_change(self, event=None):
        """Handle selection change."""
        selection = self.tree.selection()
        has_selection = len(selection) > 0

        self.delete_button.config(state=tk.NORMAL if has_selection else tk.DISABLED)
        self.details_button.config(state=tk.NORMAL if len(selection) == 1 else tk.DISABLED)

        # Enable reprocess for failed documents
        if selection:
            doc_id = selection[0]
            doc = next((d for d in self.documents if d.document_id == doc_id), None)
            can_reprocess = doc and doc.upload_status == UploadStatus.FAILED
            self.reprocess_button.config(state=tk.NORMAL if can_reprocess else tk.DISABLED)
        else:
            self.reprocess_button.config(state=tk.DISABLED)

    def _on_double_click(self, event):
        """Handle double-click on item."""
        self._view_details()

    def _view_details(self):
        """View details of selected document."""
        selection = self.tree.selection()
        if not selection:
            return

        doc_id = selection[0]
        doc = next((d for d in self.documents if d.document_id == doc_id), None)
        if not doc:
            return

        # Show details dialog
        DocumentDetailsDialog(self, doc)

    def _delete_selected(self):
        """Delete selected documents."""
        selection = self.tree.selection()
        if not selection:
            return

        count = len(selection)
        if not messagebox.askyesno(
            "Confirm Delete",
            f"Delete {count} document(s)?\n\n"
            "This will remove the documents from both the local database and Neon vector store.",
            parent=self,
        ):
            return

        deleted = 0
        for doc_id in selection:
            if self.on_delete and self.on_delete(doc_id):
                deleted += 1
                self.documents = [d for d in self.documents if d.document_id != doc_id]

        self._apply_filters()
        self._update_stats()

        messagebox.showinfo(
            "Delete Complete",
            f"Deleted {deleted} of {count} document(s).",
            parent=self,
        )

    def _reprocess_selected(self):
        """Reprocess selected failed document."""
        selection = self.tree.selection()
        if not selection:
            return

        doc_id = selection[0]
        if self.on_reprocess:
            self.on_reprocess(doc_id)
            messagebox.showinfo(
                "Reprocessing",
                "Document has been queued for reprocessing.",
                parent=self,
            )

    def _refresh_list(self):
        """Refresh the document list."""
        if self.on_refresh:
            self.documents = self.on_refresh()
            self._apply_filters()
            self._update_stats()


class DocumentDetailsDialog(tk.Toplevel):
    """Dialog showing document details."""

    def __init__(self, parent: tk.Widget, document: DocumentListItem):
        """Initialize details dialog.

        Args:
            parent: Parent widget
            document: Document to show details for
        """
        super().__init__(parent)
        self.title(f"Document Details - {document.filename}")
        self.geometry("500x400")
        self.resizable(False, False)

        self.document = document
        self._create_widgets()
        self._center_window()

        self.transient(parent)
        self.grab_set()

    def _center_window(self):
        """Center the dialog."""
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

        doc = self.document

        # Details grid
        details = [
            ("Document ID:", doc.document_id[:8] + "..."),
            ("Filename:", doc.filename),
            ("Type:", doc.file_type.upper() if isinstance(doc.file_type, str) else doc.file_type.value.upper()),
            ("Size:", self._format_size(doc.file_size_bytes)),
            ("Pages:", str(doc.page_count)),
            ("Chunks:", str(doc.chunk_count)),
            ("Status:", self._get_status_text(doc.upload_status)),
            ("Neon Synced:", "Yes" if doc.neon_synced else "No"),
            ("Graphiti Synced:", "Yes" if doc.graphiti_synced else "No"),
            ("Created:", doc.created_at.strftime("%Y-%m-%d %H:%M:%S")),
        ]

        if doc.category:
            details.append(("Category:", doc.category))

        if doc.tags:
            details.append(("Tags:", ", ".join(doc.tags)))

        for row, (label, value) in enumerate(details):
            ttk.Label(
                main_frame,
                text=label,
                font=("TkDefaultFont", 10, "bold"),
            ).grid(row=row, column=0, sticky=tk.W, pady=2)

            ttk.Label(
                main_frame,
                text=value,
            ).grid(row=row, column=1, sticky=tk.W, padx=(10, 0), pady=2)

        # Close button
        ttk.Button(
            main_frame,
            text="Close",
            command=self.destroy,
        ).grid(row=len(details) + 1, column=0, columnspan=2, pady=(20, 0))

    def _format_size(self, size_bytes: int) -> str:
        """Format file size."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    def _get_status_text(self, status) -> str:
        """Get display text for status."""
        if isinstance(status, str):
            status = UploadStatus(status)

        texts = {
            UploadStatus.COMPLETED: "Complete",
            UploadStatus.FAILED: "Failed",
            UploadStatus.PENDING: "Pending",
            UploadStatus.EXTRACTING: "Extracting",
            UploadStatus.CHUNKING: "Chunking",
            UploadStatus.EMBEDDING: "Embedding",
            UploadStatus.SYNCING: "Syncing",
        }
        return texts.get(status, str(status))
