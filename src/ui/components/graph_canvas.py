"""
Graph Canvas Widget for Knowledge Graph visualization.

Custom Tkinter Canvas widget that renders nodes and edges from
a knowledge graph using NetworkX for layout calculation.
"""

import math
import tkinter as tk
from typing import Callable, Optional

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

from rag.graph_data_provider import EntityType, GraphData, GraphEdge, GraphNode
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class GraphCanvas(tk.Canvas):
    """Interactive canvas for visualizing knowledge graphs."""

    # Entity type to color mapping - vibrant, saturated colors
    ENTITY_COLORS = {
        EntityType.MEDICATION: "#0066FF",   # Bright Blue
        EntityType.CONDITION: "#FF2D2D",    # Bright Red
        EntityType.SYMPTOM: "#FF9500",      # Bright Orange
        EntityType.PROCEDURE: "#AA00FF",    # Bright Purple
        EntityType.LAB_TEST: "#00D4AA",     # Bright Teal
        EntityType.ANATOMY: "#00CC44",      # Bright Green
        EntityType.DOCUMENT: "#6B7280",     # Medium Gray
        EntityType.EPISODE: "#00AAFF",      # Bright Cyan
        EntityType.ENTITY: "#8855FF",       # Bright Violet
        EntityType.UNKNOWN: "#888888",      # Gray
    }

    # Node sizing
    NODE_RADIUS = 24
    NODE_RADIUS_SELECTED = 30
    LABEL_OFFSET = 6

    # Edge styling - lighter for dark background
    EDGE_COLOR = "#555566"
    EDGE_COLOR_HIGHLIGHTED = "#8888AA"
    EDGE_WIDTH = 2
    EDGE_WIDTH_HIGHLIGHTED = 3

    def __init__(
        self,
        parent: tk.Widget,
        on_node_select: Optional[Callable[[Optional[GraphNode]], None]] = None,
        on_node_hover: Optional[Callable[[Optional[GraphNode]], None]] = None,
        **kwargs
    ):
        """Initialize the graph canvas.

        Args:
            parent: Parent widget
            on_node_select: Callback when a node is selected
            on_node_hover: Callback when hovering over a node
            **kwargs: Additional canvas arguments
        """
        # Set default background - dark for contrast with white labels
        kwargs.setdefault("bg", "#1a1a2e")
        kwargs.setdefault("highlightthickness", 0)

        super().__init__(parent, **kwargs)

        self.on_node_select = on_node_select
        self.on_node_hover = on_node_hover

        # Graph data
        self._graph_data: Optional[GraphData] = None
        self._node_items: dict[str, int] = {}  # node_id -> canvas item id
        self._label_items: dict[str, int] = {}  # node_id -> label item id
        self._edge_items: dict[str, int] = {}  # edge_id -> canvas item id

        # View state
        self._zoom_level = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0

        # Selection state
        self._selected_node_id: Optional[str] = None
        self._hovered_node_id: Optional[str] = None

        # Drag state
        self._drag_node_id: Optional[str] = None
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._pan_start_x = 0
        self._pan_start_y = 0
        self._is_panning = False

        # Search highlighting
        self._highlighted_nodes: set[str] = set()

        # Bind events
        self.bind("<Button-1>", self._on_click)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Motion>", self._on_motion)
        self.bind("<MouseWheel>", self._on_mousewheel)  # Windows/macOS
        self.bind("<Button-4>", self._on_mousewheel)    # Linux scroll up
        self.bind("<Button-5>", self._on_mousewheel)    # Linux scroll down
        self.bind("<Configure>", self._on_resize)

    def set_graph_data(self, data: GraphData) -> None:
        """Set the graph data and render.

        Args:
            data: GraphData containing nodes and edges
        """
        self._graph_data = data
        self._selected_node_id = None
        self._highlighted_nodes.clear()

        # Reset view
        self._zoom_level = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0

        self._calculate_layout()
        self._render()

    def _calculate_layout(self) -> None:
        """Calculate node positions using NetworkX spring layout."""
        if not self._graph_data or not self._graph_data.nodes:
            return

        if not HAS_NETWORKX:
            # Fallback to simple circular layout
            self._calculate_circular_layout()
            return

        # Build NetworkX graph
        G = nx.Graph()

        for node in self._graph_data.nodes:
            G.add_node(node.id)

        for edge in self._graph_data.edges:
            G.add_edge(edge.source_id, edge.target_id)

        # Calculate layout
        try:
            # Use spring layout with better parameters for visualization
            pos = nx.spring_layout(
                G,
                k=2.0 / math.sqrt(len(G.nodes())) if len(G.nodes()) > 0 else 1.0,
                iterations=50,
                seed=42,  # For reproducibility
            )
        except Exception as e:
            logger.warning(f"NetworkX layout failed: {e}, using circular layout")
            self._calculate_circular_layout()
            return

        # Get canvas dimensions
        width = self.winfo_width() or 800
        height = self.winfo_height() or 600

        # Scale positions to canvas with padding
        padding = 100
        scale_x = (width - 2 * padding) / 2
        scale_y = (height - 2 * padding) / 2
        center_x = width / 2
        center_y = height / 2

        # Update node positions
        for node in self._graph_data.nodes:
            if node.id in pos:
                x, y = pos[node.id]
                node.x = center_x + x * scale_x
                node.y = center_y + y * scale_y

    def _calculate_circular_layout(self) -> None:
        """Fallback circular layout when NetworkX is unavailable."""
        if not self._graph_data or not self._graph_data.nodes:
            return

        width = self.winfo_width() or 800
        height = self.winfo_height() or 600

        center_x = width / 2
        center_y = height / 2
        radius = min(width, height) / 3

        num_nodes = len(self._graph_data.nodes)
        for i, node in enumerate(self._graph_data.nodes):
            angle = 2 * math.pi * i / num_nodes
            node.x = center_x + radius * math.cos(angle)
            node.y = center_y + radius * math.sin(angle)

    def _render(self) -> None:
        """Render all nodes and edges."""
        self.delete("all")
        self._node_items.clear()
        self._label_items.clear()
        self._edge_items.clear()

        if not self._graph_data:
            self._render_empty_message()
            return

        if not self._graph_data.nodes:
            self._render_empty_message(
                "No data in knowledge graph.\n\n"
                "To populate the graph:\n"
                "1. Click 'Upload Documents' in the RAG tab\n"
                "2. Ensure 'Enable Knowledge Graph' is checked\n"
                "3. Upload PDF, DOCX, or TXT files\n\n"
                "The graph will show entities and relationships\n"
                "extracted from your documents."
            )
            return

        # Draw edges first (so nodes appear on top)
        self._render_edges()

        # Draw nodes
        self._render_nodes()

    def _render_empty_message(self, message: str = "No graph data") -> None:
        """Render an empty state message."""
        width = self.winfo_width() or 800
        height = self.winfo_height() or 600

        self.create_text(
            width / 2,
            height / 2,
            text=message,
            fill="#AAAAAA",
            font=("TkDefaultFont", 12),
            anchor="center",
            justify=tk.CENTER,
        )

    def _render_edges(self) -> None:
        """Render all edges."""
        if not self._graph_data:
            return

        for edge in self._graph_data.edges:
            source_node = self._graph_data.get_node(edge.source_id)
            target_node = self._graph_data.get_node(edge.target_id)

            if not source_node or not target_node:
                continue

            # Transform coordinates
            x1 = self._transform_x(source_node.x)
            y1 = self._transform_y(source_node.y)
            x2 = self._transform_x(target_node.x)
            y2 = self._transform_y(target_node.y)

            # Check if edge should be highlighted
            is_highlighted = (
                edge.source_id == self._selected_node_id or
                edge.target_id == self._selected_node_id
            )

            color = self.EDGE_COLOR_HIGHLIGHTED if is_highlighted else self.EDGE_COLOR
            width = self.EDGE_WIDTH_HIGHLIGHTED if is_highlighted else self.EDGE_WIDTH

            item_id = self.create_line(
                x1, y1, x2, y2,
                fill=color,
                width=width,
                tags=("edge", f"edge_{edge.id}"),
            )
            self._edge_items[edge.id] = item_id

    def _render_nodes(self) -> None:
        """Render all nodes."""
        if not self._graph_data:
            return

        for node in self._graph_data.nodes:
            self._render_node(node)

    def _render_node(self, node: GraphNode) -> None:
        """Render a single node."""
        x = self._transform_x(node.x)
        y = self._transform_y(node.y)

        # Determine node appearance
        is_selected = node.id == self._selected_node_id
        is_highlighted = node.id in self._highlighted_nodes
        is_hovered = node.id == self._hovered_node_id

        radius = self.NODE_RADIUS_SELECTED if is_selected else self.NODE_RADIUS
        radius *= self._zoom_level

        # Get color
        color = self.ENTITY_COLORS.get(node.entity_type, self.ENTITY_COLORS[EntityType.UNKNOWN])

        # Darken color if highlighted
        if is_highlighted:
            color = self._adjust_brightness(color, 0.8)

        # Border for selection/hover - always show dark border for contrast
        border_color = "#000000" if is_selected else ("#222222" if is_hovered else "#333333")
        border_width = 4 if is_selected else (3 if is_hovered else 2)

        # Draw node circle
        item_id = self.create_oval(
            x - radius, y - radius,
            x + radius, y + radius,
            fill=color,
            outline=border_color,
            width=border_width,
            tags=("node", f"node_{node.id}"),
        )
        self._node_items[node.id] = item_id

        # Draw label (only if zoomed in enough)
        if self._zoom_level >= 0.5:
            label_y = y + radius + self.LABEL_OFFSET * self._zoom_level
            font_size = max(9, int(11 * self._zoom_level))

            label_id = self.create_text(
                x, label_y,
                text=node.display_name,
                fill="#FFFFFF",
                font=("TkDefaultFont", font_size, "bold"),
                anchor="n",
                tags=("label", f"label_{node.id}"),
            )
            self._label_items[node.id] = label_id

    def _transform_x(self, x: float) -> float:
        """Transform world X coordinate to canvas coordinate."""
        return (x - self._pan_x) * self._zoom_level + self.winfo_width() / 2 * (1 - self._zoom_level)

    def _transform_y(self, y: float) -> float:
        """Transform world Y coordinate to canvas coordinate."""
        return (y - self._pan_y) * self._zoom_level + self.winfo_height() / 2 * (1 - self._zoom_level)

    def _inverse_transform_x(self, x: float) -> float:
        """Transform canvas X coordinate to world coordinate."""
        width = self.winfo_width()
        return (x - width / 2 * (1 - self._zoom_level)) / self._zoom_level + self._pan_x

    def _inverse_transform_y(self, y: float) -> float:
        """Transform canvas Y coordinate to world coordinate."""
        height = self.winfo_height()
        return (y - height / 2 * (1 - self._zoom_level)) / self._zoom_level + self._pan_y

    def _get_node_at(self, canvas_x: float, canvas_y: float) -> Optional[GraphNode]:
        """Get the node at canvas coordinates."""
        if not self._graph_data:
            return None

        # Check from top to bottom (reverse order)
        for node in reversed(self._graph_data.nodes):
            x = self._transform_x(node.x)
            y = self._transform_y(node.y)
            radius = self.NODE_RADIUS * self._zoom_level

            if (canvas_x - x) ** 2 + (canvas_y - y) ** 2 <= radius ** 2:
                return node

        return None

    def _on_click(self, event: tk.Event) -> None:
        """Handle mouse click."""
        node = self._get_node_at(event.x, event.y)

        if node:
            # Clicked on a node - start potential drag
            self._drag_node_id = node.id
            self._drag_start_x = event.x
            self._drag_start_y = event.y

            # Select the node
            self._selected_node_id = node.id
            self._render()

            if self.on_node_select:
                self.on_node_select(node)
        else:
            # Clicked on empty space - start pan
            self._is_panning = True
            self._pan_start_x = event.x
            self._pan_start_y = event.y

            # Deselect
            if self._selected_node_id:
                self._selected_node_id = None
                self._render()

                if self.on_node_select:
                    self.on_node_select(None)

    def _on_drag(self, event: tk.Event) -> None:
        """Handle mouse drag."""
        if self._drag_node_id and self._graph_data:
            # Dragging a node
            node = self._graph_data.get_node(self._drag_node_id)
            if node:
                # Update node position
                dx = (event.x - self._drag_start_x) / self._zoom_level
                dy = (event.y - self._drag_start_y) / self._zoom_level
                node.x += dx
                node.y += dy

                self._drag_start_x = event.x
                self._drag_start_y = event.y

                self._render()

        elif self._is_panning:
            # Panning the view
            dx = event.x - self._pan_start_x
            dy = event.y - self._pan_start_y

            self._pan_x -= dx / self._zoom_level
            self._pan_y -= dy / self._zoom_level

            self._pan_start_x = event.x
            self._pan_start_y = event.y

            self._render()

    def _on_release(self, event: tk.Event) -> None:
        """Handle mouse release."""
        self._drag_node_id = None
        self._is_panning = False

    def _on_motion(self, event: tk.Event) -> None:
        """Handle mouse motion for hover effects."""
        node = self._get_node_at(event.x, event.y)
        node_id = node.id if node else None

        if node_id != self._hovered_node_id:
            self._hovered_node_id = node_id
            self._render()

            if self.on_node_hover:
                self.on_node_hover(node)

            # Update cursor
            self.config(cursor="hand2" if node else "")

    def _on_mousewheel(self, event: tk.Event) -> None:
        """Handle mousewheel for zooming."""
        # Determine scroll direction
        if event.num == 5 or event.delta < 0:
            factor = 0.9  # Zoom out
        else:
            factor = 1.1  # Zoom in

        # Calculate new zoom level
        new_zoom = self._zoom_level * factor
        new_zoom = max(0.1, min(5.0, new_zoom))  # Clamp zoom

        if new_zoom != self._zoom_level:
            # Zoom towards mouse position
            mouse_world_x = self._inverse_transform_x(event.x)
            mouse_world_y = self._inverse_transform_y(event.y)

            self._zoom_level = new_zoom

            # Adjust pan to keep mouse position stable
            new_mouse_world_x = self._inverse_transform_x(event.x)
            new_mouse_world_y = self._inverse_transform_y(event.y)

            self._pan_x -= (new_mouse_world_x - mouse_world_x)
            self._pan_y -= (new_mouse_world_y - mouse_world_y)

            self._render()

    def _on_resize(self, event: tk.Event) -> None:
        """Handle canvas resize."""
        if self._graph_data and self._graph_data.nodes:
            # Recalculate layout on resize
            self._calculate_layout()
            self._render()

    def zoom_in(self) -> None:
        """Zoom in."""
        self._zoom_level = min(5.0, self._zoom_level * 1.2)
        self._render()

    def zoom_out(self) -> None:
        """Zoom out."""
        self._zoom_level = max(0.1, self._zoom_level / 1.2)
        self._render()

    def fit_to_view(self) -> None:
        """Fit all nodes in view."""
        if not self._graph_data or not self._graph_data.nodes:
            return

        # Find bounding box
        min_x = min(n.x for n in self._graph_data.nodes)
        max_x = max(n.x for n in self._graph_data.nodes)
        min_y = min(n.y for n in self._graph_data.nodes)
        max_y = max(n.y for n in self._graph_data.nodes)

        # Add padding
        padding = 50
        width = self.winfo_width() - 2 * padding
        height = self.winfo_height() - 2 * padding

        if width <= 0 or height <= 0:
            return

        graph_width = max_x - min_x
        graph_height = max_y - min_y

        if graph_width <= 0 or graph_height <= 0:
            self._zoom_level = 1.0
            self._pan_x = 0
            self._pan_y = 0
        else:
            # Calculate zoom to fit
            zoom_x = width / graph_width
            zoom_y = height / graph_height
            self._zoom_level = min(zoom_x, zoom_y, 2.0)  # Cap at 2x

            # Center the graph
            self._pan_x = (min_x + max_x) / 2 - self.winfo_width() / 2
            self._pan_y = (min_y + max_y) / 2 - self.winfo_height() / 2

        self._render()

    def highlight_nodes(self, node_ids: set[str]) -> None:
        """Highlight specific nodes.

        Args:
            node_ids: Set of node IDs to highlight
        """
        self._highlighted_nodes = node_ids
        self._render()

    def clear_highlights(self) -> None:
        """Clear all node highlights."""
        self._highlighted_nodes.clear()
        self._render()

    def select_node(self, node_id: str) -> None:
        """Programmatically select a node.

        Args:
            node_id: ID of node to select
        """
        if self._graph_data:
            node = self._graph_data.get_node(node_id)
            if node:
                self._selected_node_id = node_id
                self._render()

                if self.on_node_select:
                    self.on_node_select(node)

    def get_selected_node(self) -> Optional[GraphNode]:
        """Get the currently selected node."""
        if self._graph_data and self._selected_node_id:
            return self._graph_data.get_node(self._selected_node_id)
        return None

    @staticmethod
    def _adjust_brightness(hex_color: str, factor: float) -> str:
        """Adjust color brightness.

        Args:
            hex_color: Hex color string (e.g., "#FF0000")
            factor: Brightness factor (< 1 darkens, > 1 lightens)

        Returns:
            Adjusted hex color
        """
        # Parse hex color
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)

        # Adjust brightness
        r = max(0, min(255, int(r * factor)))
        g = max(0, min(255, int(g * factor)))
        b = max(0, min(255, int(b * factor)))

        return f"#{r:02x}{g:02x}{b:02x}"
