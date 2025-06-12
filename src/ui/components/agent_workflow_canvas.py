"""
Agent Workflow Canvas Component

Provides a visual canvas for building and editing agent chains
with drag-and-drop functionality.
"""

import tkinter as tk
from tkinter import Canvas, messagebox
import ttkbootstrap as ttk
from typing import Dict, List, Optional, Tuple, Any
import math
import json
import uuid

from ai.agents.models import (
    ChainNode, ChainNodeType, AgentType, AgentChain
)
from ai.agents.chain_builder import ChainBuilder, ChainExecutor


class WorkflowNode:
    """Visual representation of a chain node."""
    
    def __init__(self, canvas: Canvas, node: ChainNode, x: float = 100, y: float = 100):
        self.canvas = canvas
        self.node = node
        self.x = x
        self.y = y
        self.width = 120
        self.height = 60
        self.selected = False
        self.connections: List['Connection'] = []
        
        # Colors based on node type
        self.colors = {
            ChainNodeType.AGENT: "#3498db",
            ChainNodeType.CONDITION: "#e74c3c",
            ChainNodeType.TRANSFORMER: "#2ecc71",
            ChainNodeType.AGGREGATOR: "#9b59b6",
            ChainNodeType.PARALLEL: "#f39c12",
            ChainNodeType.LOOP: "#1abc9c"
        }
        
        self._create_visual()
        
    def _create_visual(self):
        """Create visual elements for the node."""
        color = self.colors.get(self.node.type, "#95a5a6")
        
        # Create rectangle
        self.rect = self.canvas.create_rectangle(
            self.x - self.width/2, self.y - self.height/2,
            self.x + self.width/2, self.y + self.height/2,
            fill=color, outline="white", width=2,
            tags=("node", self.node.id)
        )
        
        # Create text labels
        self.name_text = self.canvas.create_text(
            self.x, self.y - 10,
            text=self.node.name[:15],
            fill="white", font=("Arial", 10, "bold"),
            tags=("node", self.node.id)
        )
        
        type_text = self.node.type.value.replace("_", " ").title()
        if self.node.type == ChainNodeType.AGENT and self.node.agent_type:
            type_text = self.node.agent_type.value.replace("_", " ").title()
            
        self.type_text = self.canvas.create_text(
            self.x, self.y + 10,
            text=type_text,
            fill="white", font=("Arial", 8),
            tags=("node", self.node.id)
        )
        
        # Input/output ports
        self.input_port = self.canvas.create_oval(
            self.x - self.width/2 - 5, self.y - 5,
            self.x - self.width/2 + 5, self.y + 5,
            fill="white", outline=color,
            tags=("port", "input", self.node.id)
        )
        
        self.output_port = self.canvas.create_oval(
            self.x + self.width/2 - 5, self.y - 5,
            self.x + self.width/2 + 5, self.y + 5,
            fill="white", outline=color,
            tags=("port", "output", self.node.id)
        )
        
    def move(self, dx: float, dy: float):
        """Move the node by delta x, y."""
        self.x += dx
        self.y += dy
        
        # Move all visual elements
        for item in [self.rect, self.name_text, self.type_text, 
                     self.input_port, self.output_port]:
            self.canvas.move(item, dx, dy)
            
        # Update connections
        for connection in self.connections:
            connection.update()
            
    def set_selected(self, selected: bool):
        """Set selection state."""
        self.selected = selected
        outline_width = 3 if selected else 2
        outline_color = "yellow" if selected else "white"
        self.canvas.itemconfig(self.rect, width=outline_width, outline=outline_color)
        
    def get_input_port_pos(self) -> Tuple[float, float]:
        """Get input port position."""
        return (self.x - self.width/2, self.y)
        
    def get_output_port_pos(self) -> Tuple[float, float]:
        """Get output port position."""
        return (self.x + self.width/2, self.y)
        
    def contains_point(self, x: float, y: float) -> bool:
        """Check if point is inside node."""
        return (self.x - self.width/2 <= x <= self.x + self.width/2 and
                self.y - self.height/2 <= y <= self.y + self.height/2)


class Connection:
    """Visual representation of a connection between nodes."""
    
    def __init__(self, canvas: Canvas, from_node: WorkflowNode, to_node: WorkflowNode):
        self.canvas = canvas
        self.from_node = from_node
        self.to_node = to_node
        
        # Register with nodes
        from_node.connections.append(self)
        to_node.connections.append(self)
        
        self._create_visual()
        
    def _create_visual(self):
        """Create visual line for connection."""
        self.update()
        
    def update(self):
        """Update connection visual."""
        # Get port positions
        x1, y1 = self.from_node.get_output_port_pos()
        x2, y2 = self.to_node.get_input_port_pos()
        
        # Calculate control points for bezier curve
        dx = abs(x2 - x1)
        control_offset = min(dx / 2, 50)
        
        # Delete old line if exists
        if hasattr(self, 'line'):
            self.canvas.delete(self.line)
            
        # Create smooth curve
        points = self._calculate_bezier_points(
            x1, y1, x1 + control_offset, y1,
            x2 - control_offset, y2, x2, y2
        )
        
        self.line = self.canvas.create_line(
            points, 
            fill="#ecf0f1", 
            width=2, 
            smooth=True,
            arrow=tk.LAST,
            tags=("connection",)
        )
        
        # Send to back
        self.canvas.tag_lower(self.line)
        
    def _calculate_bezier_points(self, x1, y1, cx1, cy1, cx2, cy2, x2, y2, steps=20):
        """Calculate points along a bezier curve."""
        points = []
        for i in range(steps + 1):
            t = i / steps
            t2 = t * t
            t3 = t2 * t
            mt = 1 - t
            mt2 = mt * mt
            mt3 = mt2 * mt
            
            x = mt3 * x1 + 3 * mt2 * t * cx1 + 3 * mt * t2 * cx2 + t3 * x2
            y = mt3 * y1 + 3 * mt2 * t * cy1 + 3 * mt * t2 * cy2 + t3 * y2
            
            points.extend([x, y])
            
        return points
        
    def delete(self):
        """Delete the connection."""
        self.canvas.delete(self.line)
        self.from_node.connections.remove(self)
        self.to_node.connections.remove(self)


class AgentWorkflowCanvas(ttk.Frame):
    """Visual canvas for building agent workflows."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.nodes: Dict[str, WorkflowNode] = {}
        self.connections: List[Connection] = []
        self.selected_node: Optional[WorkflowNode] = None
        self.drag_data = {"x": 0, "y": 0, "node": None}
        self.connecting = False
        self.connect_start_node: Optional[WorkflowNode] = None
        
        self._create_ui()
        self._bind_events()
        
    def _create_ui(self):
        """Create the canvas UI."""
        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(side="top", fill="x", padx=5, pady=5)
        
        # Node type buttons
        ttk.Label(toolbar, text="Add Node:").pack(side="left", padx=(0, 10))
        
        for node_type in ChainNodeType:
            btn = ttk.Button(
                toolbar,
                text=node_type.value.replace("_", " ").title(),
                command=lambda t=node_type: self.add_node(t)
            )
            btn.pack(side="left", padx=2)
            
        # Tools
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=10)
        
        self.connect_btn = ttk.Button(
            toolbar,
            text="Connect",
            command=self.toggle_connect_mode
        )
        self.connect_btn.pack(side="left", padx=2)
        
        ttk.Button(
            toolbar,
            text="Delete",
            command=self.delete_selected
        ).pack(side="left", padx=2)
        
        ttk.Button(
            toolbar,
            text="Clear All",
            command=self.clear_all
        ).pack(side="left", padx=2)
        
        # Canvas
        self.canvas = Canvas(
            self,
            bg="#2c3e50",
            highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)
        
        # Grid
        self._draw_grid()
        
    def _draw_grid(self):
        """Draw background grid."""
        width = 2000
        height = 2000
        grid_size = 20
        
        # Draw grid lines
        for x in range(0, width, grid_size):
            self.canvas.create_line(
                x, 0, x, height,
                fill="#34495e", width=1,
                tags=("grid",)
            )
            
        for y in range(0, height, grid_size):
            self.canvas.create_line(
                0, y, width, y,
                fill="#34495e", width=1,
                tags=("grid",)
            )
            
        # Send grid to back
        self.canvas.tag_lower("grid")
        
    def _bind_events(self):
        """Bind canvas events."""
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<Button-3>", self._on_right_click)  # Right click
        
    def add_node(self, node_type: ChainNodeType, x: Optional[float] = None, y: Optional[float] = None):
        """Add a new node to the canvas."""
        if x is None:
            x = 200 + len(self.nodes) * 150
        if y is None:
            y = 200
            
        # Create chain node
        node_id = str(uuid.uuid4())
        node = ChainNode(
            id=node_id,
            type=node_type,
            name=f"{node_type.value}_{len(self.nodes) + 1}",
            config={}
        )
        
        # Create visual node
        visual_node = WorkflowNode(self.canvas, node, x, y)
        self.nodes[node_id] = visual_node
        
        return visual_node
        
    def toggle_connect_mode(self):
        """Toggle connection mode."""
        self.connecting = not self.connecting
        
        if self.connecting:
            self.connect_btn.configure(style="warning.TButton")
            self.canvas.configure(cursor="cross")
        else:
            self.connect_btn.configure(style="TButton")
            self.canvas.configure(cursor="")
            self.connect_start_node = None
            
    def _on_click(self, event):
        """Handle canvas click."""
        # Find clicked node
        clicked_node = self._find_node_at(event.x, event.y)
        
        if self.connecting:
            # Connection mode
            if clicked_node:
                if not self.connect_start_node:
                    # Start connection
                    self.connect_start_node = clicked_node
                    clicked_node.set_selected(True)
                else:
                    # Complete connection
                    if clicked_node != self.connect_start_node:
                        self._create_connection(self.connect_start_node, clicked_node)
                    self.connect_start_node.set_selected(False)
                    self.connect_start_node = None
        else:
            # Selection mode
            # Deselect previous
            if self.selected_node:
                self.selected_node.set_selected(False)
                
            # Select new
            if clicked_node:
                clicked_node.set_selected(True)
                self.selected_node = clicked_node
                
                # Start drag
                self.drag_data["x"] = event.x
                self.drag_data["y"] = event.y
                self.drag_data["node"] = clicked_node
            else:
                self.selected_node = None
                
    def _on_drag(self, event):
        """Handle drag motion."""
        if self.drag_data["node"] and not self.connecting:
            # Calculate delta
            dx = event.x - self.drag_data["x"]
            dy = event.y - self.drag_data["y"]
            
            # Move node
            self.drag_data["node"].move(dx, dy)
            
            # Update drag data
            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y
            
    def _on_release(self, event):
        """Handle mouse release."""
        self.drag_data["node"] = None
        
    def _on_double_click(self, event):
        """Handle double click - edit node."""
        node = self._find_node_at(event.x, event.y)
        if node:
            self._edit_node(node)
            
    def _on_right_click(self, event):
        """Handle right click - context menu."""
        node = self._find_node_at(event.x, event.y)
        if node:
            self._show_node_menu(event, node)
            
    def _find_node_at(self, x: float, y: float) -> Optional[WorkflowNode]:
        """Find node at coordinates."""
        for node in self.nodes.values():
            if node.contains_point(x, y):
                return node
        return None
        
    def _create_connection(self, from_node: WorkflowNode, to_node: WorkflowNode):
        """Create connection between nodes."""
        # Update chain node data
        if to_node.node.id not in from_node.node.outputs:
            from_node.node.outputs.append(to_node.node.id)
        if from_node.node.id not in to_node.node.inputs:
            to_node.node.inputs.append(from_node.node.id)
            
        # Create visual connection
        connection = Connection(self.canvas, from_node, to_node)
        self.connections.append(connection)
        
    def _edit_node(self, node: WorkflowNode):
        """Edit node properties."""
        dialog = NodeEditDialog(self, node.node)
        self.wait_window(dialog.dialog)
        
        # Update visual
        node.canvas.itemconfig(node.name_text, text=node.node.name[:15])
        
    def _show_node_menu(self, event, node: WorkflowNode):
        """Show context menu for node."""
        menu = tk.Menu(self, tearoff=0)
        
        menu.add_command(label="Edit", command=lambda: self._edit_node(node))
        menu.add_command(label="Delete", command=lambda: self._delete_node(node))
        menu.add_separator()
        menu.add_command(label="Set as Start", command=lambda: self._set_start_node(node))
        
        menu.post(event.x_root, event.y_root)
        
    def _delete_node(self, node: WorkflowNode):
        """Delete a node."""
        # Delete connections
        for conn in node.connections[:]:
            conn.delete()
            self.connections.remove(conn)
            
        # Delete visual elements
        self.canvas.delete(node.rect)
        self.canvas.delete(node.name_text)
        self.canvas.delete(node.type_text)
        self.canvas.delete(node.input_port)
        self.canvas.delete(node.output_port)
        
        # Remove from dict
        del self.nodes[node.node.id]
        
        # Deselect if selected
        if self.selected_node == node:
            self.selected_node = None
            
    def _set_start_node(self, node: WorkflowNode):
        """Set node as start node."""
        # Visual indicator - make border green
        for n in self.nodes.values():
            color = self.colors.get(n.node.type, "#95a5a6")
            self.canvas.itemconfig(n.rect, outline="white" if n != node else "#27ae60")
            
    def delete_selected(self):
        """Delete selected node."""
        if self.selected_node:
            self._delete_node(self.selected_node)
            
    def clear_all(self):
        """Clear all nodes and connections."""
        response = messagebox.askyesno(
            "Clear All",
            "Are you sure you want to clear all nodes?"
        )
        
        if response:
            self.canvas.delete("all")
            self.nodes.clear()
            self.connections.clear()
            self.selected_node = None
            self._draw_grid()
            
    def get_chain(self) -> Optional[AgentChain]:
        """Get the current chain configuration."""
        if not self.nodes:
            return None
            
        # Find start node (first node or marked start)
        start_node = None
        for node in self.nodes.values():
            outline = self.canvas.itemcget(node.rect, "outline")
            if outline == "#27ae60":  # Green = start
                start_node = node
                break
                
        if not start_node and self.nodes:
            start_node = list(self.nodes.values())[0]
            
        # Build chain
        chain = AgentChain(
            id=str(uuid.uuid4()),
            name="Visual Workflow",
            description="Created with visual editor",
            nodes=[node.node for node in self.nodes.values()],
            start_node_id=start_node.node.id if start_node else "",
            metadata={}
        )
        
        return chain
        
    def load_chain(self, chain: AgentChain):
        """Load a chain into the canvas."""
        self.clear_all()
        
        # Create nodes
        for i, node in enumerate(chain.nodes):
            x = 200 + (i % 4) * 200
            y = 200 + (i // 4) * 150
            
            if node.position:
                x = node.position.get("x", x)
                y = node.position.get("y", y)
                
            visual_node = WorkflowNode(self.canvas, node, x, y)
            self.nodes[node.id] = visual_node
            
        # Create connections
        for node in chain.nodes:
            if node.id in self.nodes:
                from_visual = self.nodes[node.id]
                for output_id in node.outputs:
                    if output_id in self.nodes:
                        to_visual = self.nodes[output_id]
                        connection = Connection(self.canvas, from_visual, to_visual)
                        self.connections.append(connection)
                        
        # Mark start node
        if chain.start_node_id in self.nodes:
            start_visual = self.nodes[chain.start_node_id]
            self.canvas.itemconfig(start_visual.rect, outline="#27ae60")


class NodeEditDialog:
    """Dialog for editing node properties."""
    
    def __init__(self, parent, node: ChainNode):
        self.parent = parent
        self.node = node
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Edit {node.type.value} Node")
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self._create_ui()
        
    def _create_ui(self):
        """Create the edit dialog UI."""
        frame = ttk.Frame(self.dialog, padding=20)
        frame.pack(fill="both", expand=True)
        
        # Name
        ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky="w", pady=5)
        self.name_var = tk.StringVar(value=self.node.name)
        ttk.Entry(frame, textvariable=self.name_var, width=40).grid(row=0, column=1, pady=5)
        
        # Type-specific fields
        row = 1
        
        if self.node.type == ChainNodeType.AGENT:
            # Agent type
            ttk.Label(frame, text="Agent Type:").grid(row=row, column=0, sticky="w", pady=5)
            self.agent_type_var = tk.StringVar(
                value=self.node.agent_type.value if self.node.agent_type else ""
            )
            agent_combo = ttk.Combobox(
                frame,
                textvariable=self.agent_type_var,
                values=[t.value for t in AgentType],
                state="readonly",
                width=37
            )
            agent_combo.grid(row=row, column=1, pady=5)
            row += 1
            
            # Task description
            ttk.Label(frame, text="Task:").grid(row=row, column=0, sticky="nw", pady=5)
            self.task_text = tk.Text(frame, height=3, width=40)
            self.task_text.grid(row=row, column=1, pady=5)
            self.task_text.insert("1.0", self.node.config.get("task_description", ""))
            row += 1
            
            # Context template
            ttk.Label(frame, text="Context:").grid(row=row, column=0, sticky="nw", pady=5)
            self.context_text = tk.Text(frame, height=3, width=40)
            self.context_text.grid(row=row, column=1, pady=5)
            self.context_text.insert("1.0", self.node.config.get("context_template", ""))
            row += 1
            
        elif self.node.type == ChainNodeType.CONDITION:
            # Condition
            ttk.Label(frame, text="Condition:").grid(row=row, column=0, sticky="nw", pady=5)
            self.condition_text = tk.Text(frame, height=3, width=40)
            self.condition_text.grid(row=row, column=1, pady=5)
            self.condition_text.insert("1.0", self.node.config.get("condition", ""))
            row += 1
            
        # Config JSON
        ttk.Label(frame, text="Configuration:").grid(row=row, column=0, sticky="nw", pady=5)
        self.config_text = tk.Text(frame, height=10, width=40)
        self.config_text.grid(row=row, column=1, pady=5)
        self.config_text.insert("1.0", json.dumps(self.node.config, indent=2))
        row += 1
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=row, column=0, columnspan=2, pady=20)
        
        ttk.Button(
            button_frame,
            text="Save",
            command=self._save
        ).pack(side="left", padx=5)
        
        ttk.Button(
            button_frame,
            text="Cancel",
            command=self.dialog.destroy
        ).pack(side="left", padx=5)
        
    def _save(self):
        """Save node changes."""
        self.node.name = self.name_var.get()
        
        # Save type-specific fields
        if self.node.type == ChainNodeType.AGENT:
            agent_type = self.agent_type_var.get()
            if agent_type:
                self.node.agent_type = AgentType(agent_type)
                
            self.node.config["task_description"] = self.task_text.get("1.0", "end-1c")
            self.node.config["context_template"] = self.context_text.get("1.0", "end-1c")
            
        elif self.node.type == ChainNodeType.CONDITION:
            self.node.config["condition"] = self.condition_text.get("1.0", "end-1c")
            
        # Parse config JSON
        try:
            config_str = self.config_text.get("1.0", "end-1c")
            if config_str:
                self.node.config = json.loads(config_str)
        except json.JSONDecodeError:
            messagebox.showerror("Invalid JSON", "Configuration must be valid JSON")
            return
            
        self.dialog.destroy()