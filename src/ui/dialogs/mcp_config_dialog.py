"""
MCP Configuration Dialog - UI for managing MCP servers
"""

import tkinter as tk
from ui.scaling_utils import ui_scaler
import ttkbootstrap as ttk
from tkinter import messagebox, scrolledtext
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class MCPConfigDialog:
    """Dialog for configuring MCP servers"""
    
    def __init__(self, parent, mcp_manager, settings):
        self.parent = parent
        self.mcp_manager = mcp_manager
        self.settings = settings
        self.dialog = None
        self.result = False
        
        # Track server list items
        self.server_items = {}
        
    def show(self):
        """Show the MCP configuration dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("MCP Tool Configuration")
        self.dialog_width, dialog_height = ui_scaler.get_dialog_size(800, 600)
        dialog.geometry(f"{dialog_width}x{dialog_height}")
        self.dialog.resizable(True, True)
        
        # Make dialog modal
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Create UI
        self._create_ui()
        
        # Load current configuration
        self._load_config()
        
        # Center dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
        
        # Wait for dialog to close
        self.dialog.wait_window()
        
        return self.result
    
    def _create_ui(self):
        """Create the dialog UI"""
        # Main container
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Enable MCP checkbox
        self.enable_var = tk.BooleanVar(value=True)
        enable_check = ttk.Checkbutton(
            main_frame,
            text="Enable MCP Tool Integration",
            variable=self.enable_var,
            command=self._toggle_mcp
        )
        enable_check.pack(anchor=tk.W, pady=(0, 10))
        
        # Create notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Server list tab
        list_frame = ttk.Frame(notebook)
        notebook.add(list_frame, text="MCP Servers")
        self._create_server_list(list_frame)
        
        # Import tab
        import_frame = ttk.Frame(notebook)
        notebook.add(import_frame, text="Import JSON")
        self._create_import_tab(import_frame)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        ttk.Button(
            button_frame,
            text="Save",
            command=self._save_config,
            bootstyle="success"
        ).pack(side=tk.RIGHT, padx=(5, 0))
        
        ttk.Button(
            button_frame,
            text="Cancel",
            command=self.dialog.destroy,
            bootstyle="secondary"
        ).pack(side=tk.RIGHT)
    
    def _create_server_list(self, parent):
        """Create the server list UI"""
        # Toolbar
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(
            toolbar,
            text="Add Server",
            command=self._add_server,
            bootstyle="primary"
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            toolbar,
            text="Edit",
            command=self._edit_server,
            bootstyle="info"
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            toolbar,
            text="Remove",
            command=self._remove_server,
            bootstyle="danger"
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            toolbar,
            text="Test Connection",
            command=self._test_server,
            bootstyle="warning"
        ).pack(side=tk.LEFT)
        
        # Server list
        list_container = ttk.Frame(parent)
        list_container.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Treeview for servers
        columns = ("status", "command", "enabled")
        self.server_tree = ttk.Treeview(
            list_container,
            columns=columns,
            show="tree headings",
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.server_tree.yview)
        self.server_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure columns
        self.server_tree.heading("#0", text="Server Name")
        self.server_tree.heading("status", text="Status")
        self.server_tree.heading("command", text="Command")
        self.server_tree.heading("enabled", text="Enabled")
        
        self.server_tree.column("#0", width=200)
        self.server_tree.column("status", width=100)
        self.server_tree.column("command", width=250)
        self.server_tree.column("enabled", width=80)
        
        # Bind double-click to edit
        self.server_tree.bind("<Double-Button-1>", lambda e: self._edit_server())
    
    def _create_import_tab(self, parent):
        """Create the JSON import tab"""
        # Instructions
        instructions = ttk.Label(
            parent,
            text="Paste MCP server configuration JSON below:",
            font=("", 11)
        )
        instructions.pack(anchor=tk.W, pady=(10, 5))
        
        # Example
        example_frame = ttk.LabelFrame(parent, text="Example", padding=10)
        example_frame.pack(fill=tk.X, pady=(0, 10))
        
        example_text = """{
  "mcpServers": {
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"],
      "env": {"BRAVE_API_KEY": "YOUR_API_KEY_HERE"}
    }
  }
}"""
        
        example_label = ttk.Label(
            example_frame,
            text=example_text,
            font=("Courier", 9),
            foreground="gray"
        )
        example_label.pack()
        
        # JSON input area
        self.json_text = scrolledtext.ScrolledText(
            parent,
            height=10,
            wrap=tk.WORD,
            font=("Courier", 10)
        )
        self.json_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Import button
        ttk.Button(
            parent,
            text="Import Configuration",
            command=self._import_json,
            bootstyle="primary"
        ).pack()
    
    def _load_config(self):
        """Load current MCP configuration"""
        mcp_config = self.settings.get("mcp_config", {})
        self.enable_var.set(mcp_config.get("enabled", True))
        
        # Clear existing items
        for item in self.server_tree.get_children():
            self.server_tree.delete(item)
        self.server_items.clear()
        
        # Load servers
        servers = mcp_config.get("servers", {})
        
        # Handle both dict and list formats
        if isinstance(servers, dict):
            for name, config in servers.items():
                self._add_server_to_list(name, config)
        elif isinstance(servers, list):
            # Convert list format to dict format
            for server in servers:
                if isinstance(server, dict) and "name" in server:
                    name = server["name"]
                    config = server.copy()
                    config.pop("name", None)
                    self._add_server_to_list(name, config)
    
    def _add_server_to_list(self, name: str, config: Dict[str, Any]):
        """Add a server to the list"""
        # Determine status
        server = self.mcp_manager.servers.get(name)
        if server and server.process and server.process.poll() is None:
            status = "Running"
            status_color = "green"
        else:
            status = "Stopped"
            status_color = "red"
        
        # Add to tree
        item = self.server_tree.insert(
            "",
            tk.END,
            text=name,
            values=(
                status,
                config.get("command", ""),
                "Yes" if config.get("enabled", True) else "No"
            ),
            tags=(status_color,)
        )
        
        # Store config
        self.server_items[item] = {
            "name": name,
            "config": config.copy()
        }
        
        # Configure tag colors
        self.server_tree.tag_configure("green", foreground="green")
        self.server_tree.tag_configure("red", foreground="red")
    
    def _toggle_mcp(self):
        """Toggle MCP enabled state"""
        enabled = self.enable_var.get()
        state = tk.NORMAL if enabled else tk.DISABLED
        
        # Enable/disable tree and buttons
        self.server_tree.config(state=state)
        for child in self.server_tree.master.master.winfo_children():
            if isinstance(child, ttk.Frame):  # toolbar
                for button in child.winfo_children():
                    if isinstance(button, ttk.Button):
                        button.config(state=state)
    
    def _add_server(self):
        """Add a new server"""
        dialog = ServerEditDialog(self.dialog, None, {})
        if dialog.show():
            name = dialog.name_var.get()
            config = dialog.get_config()
            
            # Check for duplicate
            for item_data in self.server_items.values():
                if item_data["name"] == name:
                    messagebox.showerror("Error", f"Server '{name}' already exists")
                    return
            
            # Add to list
            self._add_server_to_list(name, config)
    
    def _edit_server(self):
        """Edit selected server"""
        selection = self.server_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a server to edit")
            return
        
        item = selection[0]
        item_data = self.server_items.get(item)
        if not item_data:
            return
        
        dialog = ServerEditDialog(
            self.dialog,
            item_data["name"],
            item_data["config"]
        )
        
        if dialog.show():
            # Update tree item
            new_name = dialog.name_var.get()
            new_config = dialog.get_config()
            
            self.server_tree.item(item, text=new_name)
            self.server_tree.set(item, "command", new_config.get("command", ""))
            self.server_tree.set(item, "enabled", "Yes" if new_config.get("enabled", True) else "No")
            
            # Update stored data
            item_data["name"] = new_name
            item_data["config"] = new_config
    
    def _remove_server(self):
        """Remove selected server"""
        selection = self.server_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a server to remove")
            return
        
        item = selection[0]
        item_data = self.server_items.get(item)
        if not item_data:
            return
        
        if messagebox.askyesno("Confirm Remove", f"Remove server '{item_data['name']}'?"):
            self.server_tree.delete(item)
            del self.server_items[item]
    
    def _test_server(self):
        """Test selected server connection"""
        selection = self.server_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a server to test")
            return
        
        item = selection[0]
        item_data = self.server_items.get(item)
        if not item_data:
            return
        
        # Show progress
        progress = ttk.Toplevel(self.dialog)
        progress.title("Testing Connection")
        progress_width, progress_height = ui_scaler.get_dialog_size(300, 100)
        progress.geometry(f"{progress_width}x{progress_height}")
        progress.transient(self.dialog)
        
        ttk.Label(progress, text="Testing MCP server connection...").pack(pady=20)
        progress_bar = ttk.Progressbar(progress, mode="indeterminate")
        progress_bar.pack(padx=20, fill=tk.X)
        progress_bar.start()
        
        # Center progress dialog
        progress.update_idletasks()
        x = (progress.winfo_screenwidth() // 2) - (progress.winfo_width() // 2)
        y = (progress.winfo_screenheight() // 2) - (progress.winfo_height() // 2)
        progress.geometry(f"+{x}+{y}")
        
        # Test in background
        def test():
            success, message = self.mcp_manager.test_server(item_data["config"])
            progress.destroy()
            
            if success:
                messagebox.showinfo("Test Successful", message)
            else:
                messagebox.showerror("Test Failed", message)
        
        self.dialog.after(100, test)
    
    def _import_json(self):
        """Import JSON configuration"""
        json_str = self.json_text.get("1.0", tk.END).strip()
        if not json_str:
            messagebox.showwarning("No Input", "Please paste JSON configuration")
            return
        
        try:
            data = json.loads(json_str)
            
            # Handle different formats
            if "mcpServers" in data:
                servers = data["mcpServers"]
            elif "servers" in data:
                servers = data["servers"]
            else:
                servers = data  # Assume it's direct server config
            
            # Import each server
            imported = 0
            for name, config in servers.items():
                # Check for required fields
                if "command" not in config:
                    messagebox.showwarning("Invalid Config", f"Server '{name}' missing 'command' field")
                    continue
                
                # Add defaults
                if "args" not in config:
                    config["args"] = []
                if "env" not in config:
                    config["env"] = {}
                if "enabled" not in config:
                    config["enabled"] = True
                
                # Add to list
                self._add_server_to_list(name, config)
                imported += 1
            
            if imported > 0:
                messagebox.showinfo("Import Successful", f"Imported {imported} server(s)")
                self.json_text.delete("1.0", tk.END)
            
        except json.JSONDecodeError as e:
            messagebox.showerror("Invalid JSON", f"Failed to parse JSON: {str(e)}")
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import: {str(e)}")
    
    def _save_config(self):
        """Save the configuration"""
        # Build new config
        mcp_config = {
            "enabled": self.enable_var.get(),
            "servers": {}
        }
        
        # Get servers from list
        for item, item_data in self.server_items.items():
            name = item_data["name"]
            config = item_data["config"]
            mcp_config["servers"][name] = config
        
        # Update settings
        self.settings["mcp_config"] = mcp_config
        
        # Save settings
        from settings.settings import save_settings
        save_settings(self.settings)
        
        # Reload MCP manager
        self.mcp_manager.stop_all()
        self.mcp_manager.servers.clear()
        self.mcp_manager.load_config(mcp_config)
        
        self.result = True
        self.dialog.destroy()


class ServerEditDialog:
    """Dialog for editing a single MCP server"""
    
    def __init__(self, parent, name: Optional[str], config: Dict[str, Any]):
        self.parent = parent
        self.original_name = name
        self.config = config.copy()
        self.dialog = None
        self.result = False
        
        # Variables
        self.name_var = tk.StringVar(value=name or "")
        self.command_var = tk.StringVar(value=config.get("command", ""))
        self.args_var = tk.StringVar(value=" ".join(config.get("args", [])))
        self.enabled_var = tk.BooleanVar(value=config.get("enabled", True))
        self.env_text = None
    
    def show(self):
        """Show the edit dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Edit MCP Server" if self.original_name else "Add MCP Server")
        self.dialog_width, dialog_height = ui_scaler.get_dialog_size(600, 500)
        dialog.geometry(f"{dialog_width}x{dialog_height}")
        
        # Make modal
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Create UI
        self._create_ui()
        
        # Load environment variables
        self._load_env()
        
        # Center dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
        
        # Wait for dialog
        self.dialog.wait_window()
        
        return self.result
    
    def _create_ui(self):
        """Create the dialog UI"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Name
        ttk.Label(main_frame, text="Server Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        name_entry = ttk.Entry(main_frame, textvariable=self.name_var, width=40)
        name_entry.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        # Command
        ttk.Label(main_frame, text="Command:").grid(row=1, column=0, sticky=tk.W, pady=5)
        command_entry = ttk.Entry(main_frame, textvariable=self.command_var, width=40)
        command_entry.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # Arguments
        ttk.Label(main_frame, text="Arguments:").grid(row=2, column=0, sticky=tk.W, pady=5)
        args_entry = ttk.Entry(main_frame, textvariable=self.args_var, width=40)
        args_entry.grid(row=2, column=1, sticky=tk.W, pady=5)
        ttk.Label(
            main_frame,
            text="Space-separated arguments",
            font=("", 9),
            foreground="gray"
        ).grid(row=3, column=1, sticky=tk.W)
        
        # Enabled
        enabled_check = ttk.Checkbutton(
            main_frame,
            text="Enable this server",
            variable=self.enabled_var
        )
        enabled_check.grid(row=4, column=1, sticky=tk.W, pady=10)
        
        # Environment variables
        env_label = ttk.Label(main_frame, text="Environment Variables:")
        env_label.grid(row=5, column=0, sticky=tk.NW, pady=5)
        
        env_frame = ttk.Frame(main_frame)
        env_frame.grid(row=5, column=1, sticky=tk.W, pady=5)
        
        self.env_text = scrolledtext.ScrolledText(
            env_frame,
            width=40,
            height=8,
            font=("Courier", 9)
        )
        self.env_text.pack()
        
        ttk.Label(
            main_frame,
            text="Format: KEY=VALUE (one per line)",
            font=("", 9),
            foreground="gray"
        ).grid(row=6, column=1, sticky=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=7, column=0, columnspan=2, pady=20)
        
        ttk.Button(
            button_frame,
            text="Save",
            command=self._save,
            bootstyle="success"
        ).pack(side=tk.RIGHT, padx=(5, 0))
        
        ttk.Button(
            button_frame,
            text="Cancel",
            command=self.dialog.destroy,
            bootstyle="secondary"
        ).pack(side=tk.RIGHT)
        
        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
    
    def _load_env(self):
        """Load environment variables into text widget"""
        env = self.config.get("env", {})
        lines = []
        for key, value in env.items():
            lines.append(f"{key}={value}")
        
        if lines:
            self.env_text.insert("1.0", "\n".join(lines))
    
    def _save(self):
        """Save the configuration"""
        # Validate
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Validation Error", "Server name is required")
            return
        
        command = self.command_var.get().strip()
        if not command:
            messagebox.showerror("Validation Error", "Command is required")
            return
        
        # Parse arguments
        args_str = self.args_var.get().strip()
        args = args_str.split() if args_str else []
        
        # Parse environment variables
        env = {}
        env_text = self.env_text.get("1.0", tk.END).strip()
        if env_text:
            for line in env_text.split("\n"):
                line = line.strip()
                if line and "=" in line:
                    key, value = line.split("=", 1)
                    env[key.strip()] = value.strip()
        
        # Update config
        self.config = {
            "command": command,
            "args": args,
            "env": env,
            "enabled": self.enabled_var.get()
        }
        
        self.result = True
        self.dialog.destroy()
    
    def get_config(self) -> Dict[str, Any]:
        """Get the edited configuration"""
        return self.config


def show_mcp_config_dialog(parent, mcp_manager, settings):
    """Show the MCP configuration dialog
    
    Args:
        parent: Parent window
        mcp_manager: MCP manager instance
        settings: Application settings
        
    Returns:
        True if configuration was saved
    """
    dialog = MCPConfigDialog(parent, mcp_manager, settings)
    return dialog.show()