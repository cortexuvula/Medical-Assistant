"""
Knowledge Graph Visualization Dialog.

Displays an interactive visualization of entities and relationships
from the Neo4j knowledge graph using a custom canvas widget.
"""

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from rag.graph_data_provider import EntityType, GraphData, GraphDataProvider, GraphNode
from ui.components.graph_canvas import GraphCanvas
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class KnowledgeGraphDialog(tk.Toplevel):
    """Dialog for visualizing the knowledge graph."""

    def __init__(
        self,
        parent: tk.Widget,
        graphiti_client=None,
    ):
        """Initialize the knowledge graph dialog.

        Args:
            parent: Parent widget
            graphiti_client: Optional GraphitiClient instance
        """
        super().__init__(parent)
        self.title("Knowledge Graph Visualization")
        self.geometry("1200x800")
        self.minsize(800, 600)

        self.graphiti_client = graphiti_client
        self._data_provider: Optional[GraphDataProvider] = None
        self._graph_data: Optional[GraphData] = None
        self._loading = False

        self._create_widgets()
        self._center_window()

        # Make modal
        self.transient(parent)
        self.grab_set()

        # Load data after dialog is shown
        self.after(100, self._load_graph_data)

    def _center_window(self) -> None:
        """Center the dialog on screen."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self) -> None:
        """Create dialog widgets."""
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Toolbar
        self._create_toolbar(main_frame)

        # Main content area with paned window
        content_paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        content_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left: Graph canvas
        canvas_frame = ttk.Frame(content_paned)
        content_paned.add(canvas_frame, weight=7)

        self.graph_canvas = GraphCanvas(
            canvas_frame,
            on_node_select=self._on_node_select,
            on_node_hover=self._on_node_hover,
        )
        self.graph_canvas.pack(fill=tk.BOTH, expand=True)

        # Right: Details panel
        details_frame = ttk.Frame(content_paned, width=300)
        content_paned.add(details_frame, weight=3)

        self._create_details_panel(details_frame)

        # Status bar
        self._create_status_bar(main_frame)

    def _create_toolbar(self, parent: ttk.Frame) -> None:
        """Create the toolbar."""
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, padx=5, pady=5)

        # Search
        ttk.Label(toolbar, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_change)
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=25)
        search_entry.pack(side=tk.LEFT, padx=(5, 0))

        search_btn = ttk.Button(
            toolbar,
            text="Search",
            command=self._do_search,
        )
        search_btn.pack(side=tk.LEFT, padx=(5, 15))

        # Filter
        ttk.Label(toolbar, text="Filter:").pack(side=tk.LEFT)
        self.filter_var = tk.StringVar(value="All")
        filter_values = ["All"] + [e.value.title() for e in EntityType if e != EntityType.UNKNOWN]
        filter_combo = ttk.Combobox(
            toolbar,
            textvariable=self.filter_var,
            values=filter_values,
            state="readonly",
            width=15,
        )
        filter_combo.pack(side=tk.LEFT, padx=(5, 15))
        filter_combo.bind("<<ComboboxSelected>>", self._on_filter_change)

        # Separator
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # Zoom controls
        zoom_in_btn = ttk.Button(
            toolbar,
            text="+",
            width=3,
            command=self._zoom_in,
        )
        zoom_in_btn.pack(side=tk.LEFT, padx=(0, 2))

        zoom_out_btn = ttk.Button(
            toolbar,
            text="-",
            width=3,
            command=self._zoom_out,
        )
        zoom_out_btn.pack(side=tk.LEFT, padx=(0, 2))

        fit_btn = ttk.Button(
            toolbar,
            text="Fit",
            command=self._fit_to_view,
        )
        fit_btn.pack(side=tk.LEFT, padx=(0, 2))

        # Refresh button
        refresh_btn = ttk.Button(
            toolbar,
            text="Refresh",
            command=self._refresh_data,
        )
        refresh_btn.pack(side=tk.LEFT, padx=(10, 0))

        # Close button on right
        close_btn = ttk.Button(
            toolbar,
            text="Close",
            command=self.destroy,
        )
        close_btn.pack(side=tk.RIGHT)

    def _create_details_panel(self, parent: ttk.Frame) -> None:
        """Create the details panel on the right side."""
        # Node details section
        details_label = ttk.Label(
            parent,
            text="Node Details",
            font=("TkDefaultFont", 11, "bold"),
        )
        details_label.pack(fill=tk.X, pady=(5, 10))

        # Details content frame
        self.details_frame = ttk.Frame(parent)
        self.details_frame.pack(fill=tk.BOTH, expand=True)

        # Placeholder text
        self.no_selection_label = ttk.Label(
            self.details_frame,
            text="Select a node to view details",
            foreground="gray",
        )
        self.no_selection_label.pack(pady=20)

        # Node info labels (hidden initially)
        self.node_info_frame = ttk.Frame(self.details_frame)

        # Name
        ttk.Label(
            self.node_info_frame,
            text="Name:",
            font=("TkDefaultFont", 9, "bold"),
        ).grid(row=0, column=0, sticky=tk.W, pady=2)
        self.node_name_label = ttk.Label(self.node_info_frame, text="", wraplength=250)
        self.node_name_label.grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=2)

        # Type
        ttk.Label(
            self.node_info_frame,
            text="Type:",
            font=("TkDefaultFont", 9, "bold"),
        ).grid(row=1, column=0, sticky=tk.W, pady=2)
        self.node_type_label = ttk.Label(self.node_info_frame, text="")
        self.node_type_label.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=2)

        # Connections
        ttk.Label(
            self.node_info_frame,
            text="Connections:",
            font=("TkDefaultFont", 9, "bold"),
        ).grid(row=2, column=0, sticky=tk.W, pady=2)
        self.node_connections_label = ttk.Label(self.node_info_frame, text="")
        self.node_connections_label.grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=2)

        # Related facts section
        ttk.Separator(self.node_info_frame, orient=tk.HORIZONTAL).grid(
            row=3, column=0, columnspan=2, sticky=tk.EW, pady=10
        )

        ttk.Label(
            self.node_info_frame,
            text="Related Facts",
            font=("TkDefaultFont", 10, "bold"),
        ).grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))

        # Facts list
        facts_frame = ttk.Frame(self.node_info_frame)
        facts_frame.grid(row=5, column=0, columnspan=2, sticky=tk.NSEW)
        self.node_info_frame.grid_rowconfigure(5, weight=1)
        self.node_info_frame.grid_columnconfigure(1, weight=1)

        facts_scroll = ttk.Scrollbar(facts_frame)
        facts_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.facts_text = tk.Text(
            facts_frame,
            wrap=tk.WORD,
            height=15,
            width=30,
            state=tk.DISABLED,
            font=("TkDefaultFont", 9),
        )
        self.facts_text.pack(fill=tk.BOTH, expand=True)
        facts_scroll.config(command=self.facts_text.yview)
        self.facts_text.config(yscrollcommand=facts_scroll.set)

    def _create_status_bar(self, parent: ttk.Frame) -> None:
        """Create the status bar at the bottom."""
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=5)

        # Legend
        legend_frame = ttk.Frame(status_frame)
        legend_frame.pack(side=tk.LEFT)

        ttk.Label(legend_frame, text="Legend:").pack(side=tk.LEFT, padx=(0, 10))

        # Add legend items for main entity types
        legend_types = [
            (EntityType.MEDICATION, "Medication"),
            (EntityType.CONDITION, "Condition"),
            (EntityType.SYMPTOM, "Symptom"),
            (EntityType.PROCEDURE, "Procedure"),
            (EntityType.DOCUMENT, "Document"),
        ]

        for entity_type, label in legend_types:
            color = GraphCanvas.ENTITY_COLORS.get(entity_type, "#CCCCCC")
            canvas = tk.Canvas(legend_frame, width=16, height=16, highlightthickness=0)
            canvas.create_oval(2, 2, 14, 14, fill=color, outline="#333333", width=1)
            canvas.pack(side=tk.LEFT, padx=(0, 3))
            ttk.Label(legend_frame, text=label, font=("TkDefaultFont", 9)).pack(side=tk.LEFT, padx=(0, 12))

        # Statistics
        self.stats_label = ttk.Label(status_frame, text="", foreground="gray")
        self.stats_label.pack(side=tk.RIGHT)

    def _load_graph_data(self) -> None:
        """Load graph data from Neo4j."""
        if self._loading:
            return

        self._loading = True
        self._show_loading()

        def load_thread():
            try:
                self._data_provider = GraphDataProvider(self.graphiti_client)

                # Check health first
                if not self._data_provider.health_check():
                    self.after(0, lambda: self._show_error(
                        "Knowledge Graph is not configured.\n\n"
                        "The Knowledge Graph requires a Neo4j database connection.\n"
                        "Click the button below to configure Neo4j settings.",
                        show_configure=True
                    ))
                    return

                # Load data
                self._graph_data = self._data_provider.get_full_graph_data(limit=500)

                # Check if we got any data
                if not self._graph_data or self._graph_data.node_count == 0:
                    self.after(0, lambda: self._show_error(
                        "Knowledge Graph is empty.\n\n"
                        "No entities have been indexed yet.\n"
                        "Upload documents in the RAG tab to populate the graph."
                    ))
                    return

                # Update UI on main thread
                self.after(0, self._on_data_loaded)

            except ValueError as e:
                # Configuration error (missing credentials)
                logger.warning(f"Neo4j not configured: {e}")
                self.after(0, lambda: self._show_error(
                    "Knowledge Graph is not configured.\n\n"
                    "Neo4j connection details are missing.\n"
                    "Click the button below to configure Neo4j settings.",
                    show_configure=True
                ))

            except Exception as e:
                logger.error(f"Failed to load graph data: {e}")
                error_msg = str(e)

                # Check if it's a connection refused error
                if "refused" in error_msg.lower() or "connect" in error_msg.lower():
                    self.after(0, lambda: self._show_error(
                        "Cannot connect to Neo4j.\n\n"
                        "Make sure Neo4j is running and accessible.\n"
                        "Check your connection settings.",
                        show_configure=True
                    ))
                else:
                    self.after(0, lambda msg=error_msg: self._show_error(
                        f"Failed to load graph data:\n\n{msg}"
                    ))

            finally:
                self._loading = False

        thread = threading.Thread(target=load_thread, daemon=True)
        thread.start()

    def _show_loading(self) -> None:
        """Show loading indicator."""
        self.graph_canvas.delete("all")
        width = self.graph_canvas.winfo_width() or 800
        height = self.graph_canvas.winfo_height() or 600

        self.graph_canvas.create_text(
            width / 2,
            height / 2,
            text="Loading knowledge graph...",
            fill="#AAAAAA",
            font=("TkDefaultFont", 12),
        )

        self.stats_label.config(text="Loading...")

    def _show_error(self, message: str, show_configure: bool = False) -> None:
        """Show error message in canvas with optional configure button.

        Args:
            message: Error message to display
            show_configure: If True, show a configure button for settings
        """
        self.graph_canvas.delete("all")
        width = self.graph_canvas.winfo_width() or 800
        height = self.graph_canvas.winfo_height() or 600

        # Clear any existing configure button
        if hasattr(self, '_configure_btn_window'):
            try:
                self.graph_canvas.delete(self._configure_btn_window)
            except Exception:
                pass

        self.graph_canvas.create_text(
            width / 2,
            height / 2 - 40,
            text=message,
            fill="#FF6666",
            font=("TkDefaultFont", 11),
            justify=tk.CENTER,
        )

        if show_configure:
            # Add configure button
            configure_btn = ttk.Button(
                self.graph_canvas,
                text="Open Settings",
                command=self._open_neo4j_settings,
            )
            self._configure_btn_window = self.graph_canvas.create_window(
                width / 2,
                height / 2 + 40,
                window=configure_btn,
            )

        self.stats_label.config(text="Not configured" if show_configure else "Error")

    def _open_neo4j_settings(self) -> None:
        """Open the settings dialog to configure Neo4j."""
        try:
            # Try to open unified settings dialog
            parent = self.master
            while parent and not hasattr(parent, 'show_preferences'):
                parent = getattr(parent, 'master', None)

            if parent and hasattr(parent, 'show_preferences'):
                parent.show_preferences()
                messagebox.showinfo(
                    "Configure Neo4j",
                    "To enable the Knowledge Graph:\n\n"
                    "1. Go to 'API Keys' tab\n"
                    "2. Scroll to find Neo4j settings\n"
                    "3. Enter your Neo4j URI and password\n\n"
                    "Or set environment variables:\n"
                    "  NEO4J_URI=bolt://localhost:7687\n"
                    "  NEO4J_PASSWORD=your_password",
                    parent=self
                )
            else:
                # Show manual instructions
                messagebox.showinfo(
                    "Configure Neo4j",
                    "To enable the Knowledge Graph, add these to your .env file:\n\n"
                    "NEO4J_URI=bolt://localhost:7687\n"
                    "NEO4J_USER=neo4j\n"
                    "NEO4J_PASSWORD=your_password\n\n"
                    "Then restart the application.",
                    parent=self
                )
        except Exception as e:
            logger.error(f"Failed to open settings: {e}")
            messagebox.showerror("Error", f"Could not open settings: {e}", parent=self)

    def _on_data_loaded(self) -> None:
        """Handle successful data load."""
        if self._graph_data:
            self.graph_canvas.set_graph_data(self._graph_data)
            self._update_stats()

    def _update_stats(self) -> None:
        """Update statistics label."""
        if self._graph_data:
            self.stats_label.config(
                text=f"Nodes: {self._graph_data.node_count}  |  Edges: {self._graph_data.edge_count}"
            )
        else:
            self.stats_label.config(text="No data")

    def _on_node_select(self, node: Optional[GraphNode]) -> None:
        """Handle node selection."""
        if node:
            self._show_node_details(node)
        else:
            self._hide_node_details()

    def _on_node_hover(self, node: Optional[GraphNode]) -> None:
        """Handle node hover."""
        # Could add tooltip or status bar update here
        pass

    def _show_node_details(self, node: GraphNode) -> None:
        """Show details for selected node."""
        self.no_selection_label.pack_forget()
        self.node_info_frame.pack(fill=tk.BOTH, expand=True)

        # Update labels
        self.node_name_label.config(text=node.name)
        self.node_type_label.config(text=node.entity_type.value.title())

        # Count connections
        if self._graph_data:
            edges = self._graph_data.get_edges_for_node(node.id)
            self.node_connections_label.config(text=str(len(edges)))

            # Show related facts
            self.facts_text.config(state=tk.NORMAL)
            self.facts_text.delete("1.0", tk.END)

            for edge in edges:
                if edge.fact:
                    self.facts_text.insert(tk.END, f"• {edge.fact}\n\n")
                else:
                    # Show relationship type if no fact
                    connected_node = None
                    if edge.source_id == node.id:
                        connected_node = self._graph_data.get_node(edge.target_id)
                    else:
                        connected_node = self._graph_data.get_node(edge.source_id)

                    if connected_node:
                        self.facts_text.insert(
                            tk.END,
                            f"• {edge.display_type} → {connected_node.display_name}\n\n"
                        )

            if not edges:
                self.facts_text.insert(tk.END, "(No relationships)")

            self.facts_text.config(state=tk.DISABLED)
        else:
            self.node_connections_label.config(text="0")

    def _hide_node_details(self) -> None:
        """Hide node details panel."""
        self.node_info_frame.pack_forget()
        self.no_selection_label.pack(pady=20)

    def _on_search_change(self, *args) -> None:
        """Handle search text change."""
        # Debounce search
        if hasattr(self, "_search_after_id"):
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(300, self._do_search)

    def _do_search(self) -> None:
        """Execute search."""
        query = self.search_var.get().strip()

        if not query:
            self.graph_canvas.clear_highlights()
            return

        if self._graph_data:
            matching_nodes = self._graph_data.search(query)
            matching_ids = {n.id for n in matching_nodes}
            self.graph_canvas.highlight_nodes(matching_ids)

            # Update stats
            self.stats_label.config(
                text=f"Found: {len(matching_ids)} of {self._graph_data.node_count} nodes"
            )

    def _on_filter_change(self, event=None) -> None:
        """Handle filter change."""
        filter_value = self.filter_var.get()

        if filter_value == "All":
            # Show all data
            if self._graph_data:
                self.graph_canvas.set_graph_data(self._graph_data)
                self._update_stats()
        else:
            # Filter by entity type
            if self._graph_data:
                entity_type = EntityType.from_string(filter_value.lower())
                filtered_data = self._graph_data.filter_by_type(entity_type)
                self.graph_canvas.set_graph_data(filtered_data)

                self.stats_label.config(
                    text=f"Filtered: {filtered_data.node_count} nodes  |  {filtered_data.edge_count} edges"
                )

    def _zoom_in(self) -> None:
        """Zoom in on the graph."""
        self.graph_canvas.zoom_in()

    def _zoom_out(self) -> None:
        """Zoom out from the graph."""
        self.graph_canvas.zoom_out()

    def _fit_to_view(self) -> None:
        """Fit the entire graph in view."""
        self.graph_canvas.fit_to_view()

    def _refresh_data(self) -> None:
        """Refresh graph data from Neo4j."""
        self._hide_node_details()
        self.graph_canvas.clear_highlights()
        self.search_var.set("")
        self.filter_var.set("All")
        self._load_graph_data()

    def destroy(self) -> None:
        """Clean up resources on close."""
        if self._data_provider:
            try:
                self._data_provider.close()
            except Exception:
                pass

        super().destroy()
