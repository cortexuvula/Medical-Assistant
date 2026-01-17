"""
MCP Configuration Dialog - UI for managing MCP servers
"""

import tkinter as tk
from ui.scaling_utils import ui_scaler
import ttkbootstrap as ttk
from tkinter import messagebox, scrolledtext
import json
import shutil
import threading
from typing import Dict, Any, Optional, Tuple

from utils.structured_logging import get_logger
from utils.error_handling import ErrorContext

logger = get_logger(__name__)

# Popular MCP server presets
MCP_SERVER_PRESETS = {
    "Brave Search": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "env": {"BRAVE_API_KEY": "YOUR_API_KEY_HERE"},
        "enabled": True,
        "description": "Web search via Brave Search API"
    },
    "Filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/directory"],
        "env": {},
        "enabled": True,
        "description": "Read/write files in allowed directories"
    },
    "GitHub": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "YOUR_TOKEN_HERE"},
        "enabled": True,
        "description": "Access GitHub repos, issues, PRs"
    },
    "Google Maps": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-google-maps"],
        "env": {"GOOGLE_MAPS_API_KEY": "YOUR_API_KEY_HERE"},
        "enabled": True,
        "description": "Location search and directions"
    },
    "Memory": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"],
        "env": {},
        "enabled": True,
        "description": "Persistent memory across sessions"
    },
    "Puppeteer": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-puppeteer"],
        "env": {},
        "enabled": True,
        "description": "Browser automation and screenshots"
    },
    "SQLite": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sqlite", "/path/to/database.db"],
        "env": {},
        "enabled": True,
        "description": "Query SQLite databases"
    }
}


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
        dialog_width, dialog_height = ui_scaler.get_dialog_size(800, 600)
        self.dialog.geometry(f"{dialog_width}x{dialog_height}")
        self.dialog.resizable(True, True)

        # Make dialog modal
        self.dialog.transient(self.parent)

        # Create UI
        self._create_ui()

        # Load current configuration
        self._load_config()

        # Center dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

        # Grab focus after window is visible
        self.dialog.deiconify()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass  # Window not viewable yet

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

        # Add preset button with dropdown
        preset_btn = ttk.Menubutton(
            toolbar,
            text="Add Preset",
            bootstyle="success-outline"
        )
        preset_btn.pack(side=tk.LEFT, padx=(10, 0))

        # Create preset menu
        preset_menu = tk.Menu(preset_btn, tearoff=0)
        for preset_name, preset_config in MCP_SERVER_PRESETS.items():
            preset_menu.add_command(
                label=f"{preset_name} - {preset_config['description']}",
                command=lambda n=preset_name, c=preset_config: self._add_preset(n, c)
            )
        preset_btn["menu"] = preset_menu

        # View Logs button
        ttk.Button(
            toolbar,
            text="View Logs",
            command=self._view_server_logs,
            bootstyle="info-outline"
        ).pack(side=tk.LEFT, padx=(5, 0))

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
        example_frame = ttk.Labelframe(parent, text="Example", padding=10)
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

    def _add_preset(self, preset_name: str, preset_config: Dict[str, Any]):
        """Add a server from preset configuration.

        Args:
            preset_name: Display name of the preset
            preset_config: Preset configuration dict
        """
        # Generate a unique server name
        base_name = preset_name.lower().replace(" ", "-")
        name = base_name
        counter = 1

        # Check for existing servers with same name
        existing_names = [item_data["name"] for item_data in self.server_items.values()]
        while name in existing_names:
            name = f"{base_name}-{counter}"
            counter += 1

        # Copy config without description
        config = {
            "command": preset_config["command"],
            "args": preset_config["args"].copy(),
            "env": preset_config["env"].copy(),
            "enabled": preset_config["enabled"]
        }

        # Open edit dialog so user can customize (especially API keys and paths)
        dialog = ServerEditDialog(self.dialog, name, config)
        if dialog.show():
            final_name = dialog.name_var.get()
            final_config = dialog.get_config()

            # Check for duplicate
            for item_data in self.server_items.values():
                if item_data["name"] == final_name:
                    messagebox.showerror("Error", f"Server '{final_name}' already exists")
                    return

            # Add to list
            self._add_server_to_list(final_name, final_config)
            messagebox.showinfo("Preset Added", f"Server '{final_name}' added from preset.\n\nRemember to update any placeholder values (API keys, paths, etc.)")

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

    def _view_server_logs(self):
        """View error logs for selected server."""
        selection = self.server_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a server to view logs", parent=self.dialog)
            return

        item = selection[0]
        item_data = self.server_items.get(item)
        if not item_data:
            return

        server_name = item_data["name"]
        server = self.mcp_manager.servers.get(server_name)

        # Create log viewer dialog
        log_dialog = tk.Toplevel(self.dialog)
        log_dialog.title(f"Server Logs - {server_name}")
        dialog_width, dialog_height = ui_scaler.get_dialog_size(600, 400)
        log_dialog.geometry(f"{dialog_width}x{dialog_height}")
        log_dialog.transient(self.dialog)

        # Content frame
        content = ttk.Frame(log_dialog, padding=10)
        content.pack(fill=tk.BOTH, expand=True)

        # Status info
        if server and server.process:
            status = "Running" if server.process.poll() is None else f"Stopped (exit code: {server.process.returncode})"
        else:
            status = "Not started"

        ttk.Label(
            content,
            text=f"Status: {status}",
            font=("", 10, "bold")
        ).pack(anchor=tk.W, pady=(0, 5))

        # Log text area
        log_frame = ttk.Frame(content)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=("Courier", 9),
            state=tk.NORMAL
        )
        log_text.pack(fill=tk.BOTH, expand=True)

        # Get and display logs
        if server:
            log_content = server.get_error_log()
        else:
            log_content = "Server not active. Start the server to collect logs."

        log_text.insert("1.0", log_content)
        log_text.config(state=tk.DISABLED)

        # Scroll to bottom
        log_text.see(tk.END)

        # Button frame
        btn_frame = ttk.Frame(content)
        btn_frame.pack(fill=tk.X)

        def refresh_logs():
            log_text.config(state=tk.NORMAL)
            log_text.delete("1.0", tk.END)
            if server:
                log_text.insert("1.0", server.get_error_log())
            log_text.config(state=tk.DISABLED)
            log_text.see(tk.END)

        def clear_logs():
            if server:
                server.clear_error_log()
                refresh_logs()

        ttk.Button(
            btn_frame,
            text="Refresh",
            command=refresh_logs,
            bootstyle="info"
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            btn_frame,
            text="Clear Logs",
            command=clear_logs,
            bootstyle="warning"
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            btn_frame,
            text="Close",
            command=log_dialog.destroy,
            bootstyle="secondary"
        ).pack(side=tk.RIGHT)

        # Center dialog
        log_dialog.update_idletasks()
        x = (log_dialog.winfo_screenwidth() // 2) - (log_dialog.winfo_width() // 2)
        y = (log_dialog.winfo_screenheight() // 2) - (log_dialog.winfo_height() // 2)
        log_dialog.geometry(f"+{x}+{y}")

    def _test_server(self):
        """Test selected server connection (async with cancel option)"""
        selection = self.server_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a server to test")
            return

        item = selection[0]
        item_data = self.server_items.get(item)
        if not item_data:
            return

        # Show progress dialog
        progress = ttk.Toplevel(self.dialog)
        progress.title("Testing Connection")
        progress_width, progress_height = ui_scaler.get_dialog_size(350, 150)
        progress.geometry(f"{progress_width}x{progress_height}")
        progress.transient(self.dialog)
        progress.resizable(False, False)

        # Track if cancelled
        cancelled = [False]

        # Content frame
        content = ttk.Frame(progress, padding=15)
        content.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            content,
            text=f"Testing '{item_data['name']}'...",
            font=("", 11)
        ).pack(pady=(0, 10))

        progress_bar = ttk.Progressbar(content, mode="indeterminate", length=280)
        progress_bar.pack(pady=(0, 15))
        progress_bar.start(10)

        def cancel_test():
            cancelled[0] = True
            progress.destroy()

        cancel_btn = ttk.Button(
            content,
            text="Cancel",
            command=cancel_test,
            bootstyle="secondary",
            width=10
        )
        cancel_btn.pack()

        # Center progress dialog
        progress.update_idletasks()
        x = (progress.winfo_screenwidth() // 2) - (progress.winfo_width() // 2)
        y = (progress.winfo_screenheight() // 2) - (progress.winfo_height() // 2)
        progress.geometry(f"+{x}+{y}")

        # Handle window close
        progress.protocol("WM_DELETE_WINDOW", cancel_test)

        def show_result(success: bool, message: str):
            """Show test result on main thread"""
            if cancelled[0]:
                return

            try:
                progress.destroy()
            except tk.TclError:
                pass  # Dialog already closed

            if success:
                messagebox.showinfo("Test Successful", message, parent=self.dialog)
            else:
                messagebox.showerror("Test Failed", message, parent=self.dialog)

        def run_test():
            """Run test in background thread"""
            try:
                success, message = self.mcp_manager.test_server(item_data["config"])
                if not cancelled[0]:
                    # Schedule result display on main thread
                    self.dialog.after(0, lambda: show_result(success, message))
            except Exception as e:
                ctx = ErrorContext.capture(
                    operation="Testing MCP server",
                    exception=e,
                    input_summary=f"server={item_data['name']}"
                )
                logger.error(ctx.to_log_string())
                if not cancelled[0]:
                    self.dialog.after(0, lambda: show_result(False, ctx.user_message))

        # Start test in background thread
        test_thread = threading.Thread(target=run_test, daemon=True)
        test_thread.start()
    
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
            ctx = ErrorContext.capture(
                operation="Parsing MCP JSON",
                exception=e,
                input_summary=f"json_length={len(json_str)}"
            )
            logger.error(ctx.to_log_string())
            messagebox.showerror("Invalid JSON", f"Failed to parse JSON: {e.msg} at line {e.lineno}")
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Importing MCP configuration",
                exception=e,
                input_summary=f"json_length={len(json_str)}"
            )
            logger.error(ctx.to_log_string())
            messagebox.showerror("Import Error", ctx.user_message)
    
    def _validate_config(self) -> Tuple[bool, str]:
        """Validate all server configurations before saving.

        Returns:
            Tuple of (is_valid, error_message)
        """
        warnings = []

        for item, item_data in self.server_items.items():
            config = item_data["config"]
            name = item_data["name"]

            # Check command exists
            command = config.get("command", "")
            if not command:
                return False, f"Server '{name}': command is required"

            # Check for npx availability if using npx
            if command in ("npx", "npx.cmd"):
                if not shutil.which("npx") and not shutil.which("npx.cmd"):
                    return False, f"Server '{name}': npx not found.\n\nPlease install Node.js from https://nodejs.org"

            # Check for python availability if using python
            if command in ("python", "python3"):
                if not shutil.which("python") and not shutil.which("python3"):
                    return False, f"Server '{name}': Python not found in PATH"

            # Warn about empty API keys (but don't block)
            env = config.get("env", {})
            for key, value in env.items():
                if "API_KEY" in key or "TOKEN" in key or "SECRET" in key:
                    if not value or value in ("YOUR_API_KEY_HERE", "YOUR_TOKEN_HERE"):
                        warnings.append(f"Server '{name}': {key} appears to be a placeholder")

            # Warn about placeholder paths
            args = config.get("args", [])
            for arg in args:
                if "/path/to/" in arg or "YOUR_" in arg:
                    warnings.append(f"Server '{name}': argument '{arg}' appears to be a placeholder")

        # Show warnings but allow save
        if warnings:
            warning_msg = "Configuration has potential issues:\n\n" + "\n".join(f"• {w}" for w in warnings[:5])
            if len(warnings) > 5:
                warning_msg += f"\n\n...and {len(warnings) - 5} more"
            warning_msg += "\n\nDo you want to save anyway?"

            if not messagebox.askyesno("Configuration Warnings", warning_msg, parent=self.dialog):
                return False, ""  # User cancelled, no error message

        return True, ""

    def _save_config(self):
        """Save the configuration"""
        # Validate configuration first
        is_valid, error_msg = self._validate_config()
        if not is_valid:
            if error_msg:  # Only show error if there's a message (not cancelled)
                messagebox.showerror("Validation Error", error_msg, parent=self.dialog)
            return

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
        
        # Save settings using settings_manager
        from settings.settings_manager import settings_manager
        settings_manager.set("mcp_config", mcp_config)
        
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
        dialog_width, dialog_height = ui_scaler.get_dialog_size(600, 500)
        self.dialog.geometry(f"{dialog_width}x{dialog_height}")

        # Make modal
        self.dialog.transient(self.parent)

        # Create UI
        self._create_ui()

        # Load environment variables
        self._load_env()

        # Center dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

        # Grab focus after window is visible
        self.dialog.deiconify()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass  # Window not viewable yet

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