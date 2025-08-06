"""
Process Tab Component for Medical Assistant
Handles text processing and file operations UI
"""

import tkinter as tk
import ttkbootstrap as ttk
from typing import Dict, Callable
from ui.tooltip import ToolTip


class ProcessTab:
    """Manages the Process workflow tab UI components."""
    
    def __init__(self, parent_ui):
        """Initialize the ProcessTab component.
        
        Args:
            parent_ui: Reference to the parent WorkflowUI instance
        """
        self.parent_ui = parent_ui
        self.parent = parent_ui.parent
        self.components = parent_ui.components
        
    def create_process_tab(self, command_map: Dict[str, Callable]) -> ttk.Frame:
        """Create the Process workflow tab.
        
        Args:
            command_map: Dictionary of commands
            
        Returns:
            ttk.Frame: The process tab frame
        """
        process_frame = ttk.Frame(self.parent)
        
        # Text processing tools
        tools_frame = ttk.LabelFrame(process_frame, text="Text Processing Tools", padding=15)
        tools_frame.pack(fill=tk.X, padx=20, pady=20)
        
        # Create tool buttons in a grid
        tools = [
            {
                "name": "refine",
                "text": "Refine Text",
                "tooltip": "Clean up punctuation and capitalization",
                "command": command_map.get("refine_text"),
                "row": 0,
                "column": 0
            },
            {
                "name": "improve",
                "text": "Improve Text",
                "tooltip": "Enhance clarity and readability",
                "command": command_map.get("improve_text"),
                "row": 0,
                "column": 1
            },
            {
                "name": "undo",
                "text": "Undo",
                "tooltip": "Undo last change (Ctrl+Z)",
                "command": command_map.get("undo_text"),
                "row": 1,
                "column": 0
            },
            {
                "name": "redo",
                "text": "Redo",
                "tooltip": "Redo last change (Ctrl+Y)",
                "command": command_map.get("redo_text"),
                "row": 1,
                "column": 1
            }
        ]
        
        for tool in tools:
            btn = ttk.Button(
                tools_frame,
                text=tool["text"],
                command=tool["command"],
                bootstyle="info",
                width=20
            )
            btn.grid(row=tool["row"], column=tool["column"], padx=10, pady=10, sticky="ew")
            ToolTip(btn, tool["tooltip"])
            self.components[f"process_{tool['name']}_button"] = btn
        
        # Configure grid weights
        tools_frame.columnconfigure(0, weight=1)
        tools_frame.columnconfigure(1, weight=1)
        
        # File operations
        file_frame = ttk.LabelFrame(process_frame, text="File Operations", padding=15)
        file_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        file_ops = [
            {
                "name": "save",
                "text": "Save",
                "tooltip": "Save transcript and audio",
                "command": command_map.get("save_text"),
                "column": 0
            },
            {
                "name": "load",
                "text": "Load Audio",
                "tooltip": "Load and transcribe audio file",
                "command": command_map.get("load_audio_file"),
                "column": 1
            },
            {
                "name": "new_session",
                "text": "New Session",
                "tooltip": "Start a new session (Ctrl+N)",
                "command": command_map.get("new_session"),
                "column": 2
            }
        ]
        
        for op in file_ops:
            btn = ttk.Button(
                file_frame,
                text=op["text"],
                command=op["command"],
                bootstyle="primary",
                width=15
            )
            btn.grid(row=0, column=op["column"], padx=10, pady=10, sticky="ew")
            ToolTip(btn, op["tooltip"])
            self.components[f"file_{op['name']}_button"] = btn
        
        # Configure grid weights
        for i in range(3):
            file_frame.columnconfigure(i, weight=1)
        
        return process_frame