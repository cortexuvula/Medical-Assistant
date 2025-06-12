"""
Advanced Agent Settings Dialog

Enhanced version of agent settings with support for advanced parameters,
sub-agents, and agent chains.
"""

import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog, ttk as tk_ttk
import ttkbootstrap as ttk
from typing import Dict, Any, Optional, List
import logging
import json
from datetime import datetime
import os

from settings.settings import load_settings, save_settings
from ai.agents.models import (
    AgentType, ResponseFormat, RetryStrategy, RetryConfig, 
    AdvancedConfig, SubAgentConfig, AgentConfig, AgentTemplate
)
from ai.agents.synopsis import SynopsisAgent
from ui.dialogs.agent_settings_dialog import AgentSettingsDialog

logger = logging.getLogger(__name__)


class AdvancedAgentSettingsDialog(AgentSettingsDialog):
    """Enhanced dialog for configuring agent settings with advanced features."""
    
    def __init__(self, parent):
        """Initialize the advanced agent settings dialog."""
        super().__init__(parent)
        self.templates = []
        self.load_templates()
        
    def _create_agent_tab(self, agent_type: AgentType):
        """Create an enhanced tab for an agent type with sub-tabs."""
        # Create main frame for the tab
        tab_frame = ttk.Frame(self.notebook, padding=5)
        self.notebook.add(tab_frame, text=agent_type.value.replace("_", " ").title())
        
        # Create sub-notebook for basic/advanced/sub-agents tabs
        sub_notebook = ttk.Notebook(tab_frame)
        sub_notebook.pack(fill="both", expand=True)
        
        # Create sub-tabs
        basic_frame = ttk.Frame(sub_notebook, padding=10)
        sub_notebook.add(basic_frame, text="Basic Settings")
        
        advanced_frame = ttk.Frame(sub_notebook, padding=10)
        sub_notebook.add(advanced_frame, text="Advanced Settings")
        
        subagents_frame = ttk.Frame(sub_notebook, padding=10)
        sub_notebook.add(subagents_frame, text="Sub-Agents")
        
        # Get current config
        agent_key = agent_type.value
        if agent_key not in self.settings["agent_config"]:
            self.settings["agent_config"][agent_key] = self.DEFAULT_AGENT_CONFIGS.get(
                agent_type, self._get_default_config(agent_type)
            )
        
        current_config = self.settings["agent_config"][agent_key]
        
        # Store widgets for this agent
        self.widgets[agent_key] = {}
        
        # Create basic settings
        self._create_basic_settings(basic_frame, agent_key, current_config)
        
        # Create advanced settings
        self._create_advanced_settings(advanced_frame, agent_key, current_config)
        
        # Create sub-agents settings
        self._create_subagents_settings(subagents_frame, agent_key, current_config)
        
    def _create_basic_settings(self, parent, agent_key: str, config: dict):
        """Create basic settings UI."""
        parent.columnconfigure(1, weight=1)
        row = 0
        
        # Enable/Disable checkbox
        enabled_var = tk.BooleanVar(value=config.get("enabled", False))
        self.widgets[agent_key]["enabled"] = enabled_var
        
        enabled_check = ttk.Checkbutton(
            parent, 
            text="Enable this agent",
            variable=enabled_var,
            command=lambda: self._toggle_agent_controls(agent_key)
        )
        enabled_check.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 10))
        row += 1
        
        # AI Provider selection
        ttk.Label(parent, text="AI Provider:").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=5)
        
        current_provider = config.get("provider", self.settings.get("ai_provider", "openai"))
        provider_var = tk.StringVar(value=current_provider)
        self.widgets[agent_key]["provider"] = provider_var
        
        provider_combo = ttk.Combobox(
            parent,
            textvariable=provider_var,
            values=list(self.PROVIDER_MODELS.keys()),
            state="readonly",
            width=20
        )
        provider_combo.grid(row=row, column=1, sticky="w", pady=5)
        provider_combo.bind("<<ComboboxSelected>>", lambda e: self._update_model_list(agent_key))
        row += 1
        
        # Model selection
        ttk.Label(parent, text="Model:").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=5)
        
        model_var = tk.StringVar(value=config.get("model", "gpt-4"))
        self.widgets[agent_key]["model"] = model_var
        
        model_combo = ttk.Combobox(
            parent,
            textvariable=model_var,
            values=self.PROVIDER_MODELS.get(current_provider, []),
            state="readonly",
            width=30
        )
        model_combo.grid(row=row, column=1, sticky="w", pady=5)
        self.widgets[agent_key]["model_combo"] = model_combo
        row += 1
        
        # Temperature slider
        ttk.Label(parent, text="Temperature:").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=5)
        
        temp_frame = ttk.Frame(parent)
        temp_frame.grid(row=row, column=1, sticky="ew", pady=5)
        temp_frame.columnconfigure(0, weight=1)
        
        temp_var = tk.DoubleVar(value=config.get("temperature", 0.7))
        self.widgets[agent_key]["temperature"] = temp_var
        
        temp_slider = ttk.Scale(
            temp_frame,
            from_=0.0,
            to=2.0,
            orient=tk.HORIZONTAL,
            variable=temp_var
        )
        temp_slider.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        
        temp_label = ttk.Label(temp_frame, text=f"{temp_var.get():.2f}", width=5)
        temp_label.grid(row=0, column=1, sticky="w")
        self.widgets[agent_key]["temp_label"] = temp_label
        
        def update_temp_label(*args):
            temp_label.config(text=f"{temp_var.get():.2f}")
        
        temp_slider.bind("<Motion>", update_temp_label)
        temp_slider.bind("<ButtonRelease-1>", update_temp_label)
        row += 1
        
        # Max tokens
        ttk.Label(parent, text="Max Tokens:").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=5)
        
        tokens_var = tk.IntVar(value=config.get("max_tokens", 300))
        self.widgets[agent_key]["max_tokens"] = tokens_var
        
        tokens_spin = ttk.Spinbox(
            parent,
            from_=50,
            to=4000,
            increment=50,
            textvariable=tokens_var,
            width=10
        )
        tokens_spin.grid(row=row, column=1, sticky="w", pady=5)
        row += 1
        
        # System prompt
        ttk.Label(parent, text="System Prompt:").grid(row=row, column=0, sticky="nw", padx=(0, 10), pady=5)
        
        prompt_text = scrolledtext.ScrolledText(
            parent,
            height=10,
            width=60,
            wrap=tk.WORD
        )
        prompt_text.grid(row=row, column=1, sticky="ew", pady=5)
        prompt_text.insert("1.0", config.get("system_prompt", ""))
        self.widgets[agent_key]["system_prompt"] = prompt_text
        parent.rowconfigure(row, weight=1)
        row += 1
        
        # Test button
        test_button = ttk.Button(
            parent,
            text="Test Agent Configuration",
            command=lambda: self._test_agent(agent_key)
        )
        test_button.grid(row=row, column=1, sticky="w", pady=(10, 0))
        self.widgets[agent_key]["test_button"] = test_button
        
        # Test result label
        test_label = ttk.Label(parent, text="", foreground="gray")
        test_label.grid(row=row+1, column=1, sticky="w", pady=(5, 0))
        self.widgets[agent_key]["test_label"] = test_label
        
        # Set initial control states
        self._toggle_agent_controls(agent_key)
        
    def _create_advanced_settings(self, parent, agent_key: str, config: dict):
        """Create advanced settings UI."""
        parent.columnconfigure(1, weight=1)
        
        # Get advanced config or create default
        advanced = config.get("advanced", {})
        
        row = 0
        
        # Response Format
        ttk.Label(parent, text="Response Format:").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=5)
        
        format_var = tk.StringVar(value=advanced.get("response_format", ResponseFormat.PLAIN_TEXT.value))
        self.widgets[agent_key]["response_format"] = format_var
        
        format_combo = ttk.Combobox(
            parent,
            textvariable=format_var,
            values=[fmt.value for fmt in ResponseFormat],
            state="readonly",
            width=20
        )
        format_combo.grid(row=row, column=1, sticky="w", pady=5)
        row += 1
        
        # Context Window Size
        ttk.Label(parent, text="Context Window:").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=5)
        
        context_var = tk.IntVar(value=advanced.get("context_window_size", 5))
        self.widgets[agent_key]["context_window_size"] = context_var
        
        context_spin = ttk.Spinbox(
            parent,
            from_=0,
            to=20,
            increment=1,
            textvariable=context_var,
            width=10
        )
        context_spin.grid(row=row, column=1, sticky="w", pady=5)
        row += 1
        
        # Timeout
        ttk.Label(parent, text="Timeout (seconds):").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=5)
        
        timeout_var = tk.DoubleVar(value=advanced.get("timeout_seconds", 30.0))
        self.widgets[agent_key]["timeout_seconds"] = timeout_var
        
        timeout_spin = ttk.Spinbox(
            parent,
            from_=5.0,
            to=300.0,
            increment=5.0,
            textvariable=timeout_var,
            width=10
        )
        timeout_spin.grid(row=row, column=1, sticky="w", pady=5)
        row += 1
        
        # Retry Strategy
        retry_config = advanced.get("retry_config", {})
        
        ttk.Label(parent, text="Retry Strategy:").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=5)
        
        retry_var = tk.StringVar(value=retry_config.get("strategy", RetryStrategy.EXPONENTIAL_BACKOFF.value))
        self.widgets[agent_key]["retry_strategy"] = retry_var
        
        retry_combo = ttk.Combobox(
            parent,
            textvariable=retry_var,
            values=[strategy.value for strategy in RetryStrategy],
            state="readonly",
            width=25
        )
        retry_combo.grid(row=row, column=1, sticky="w", pady=5)
        row += 1
        
        # Max Retries
        ttk.Label(parent, text="Max Retries:").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=5)
        
        max_retries_var = tk.IntVar(value=retry_config.get("max_retries", 3))
        self.widgets[agent_key]["max_retries"] = max_retries_var
        
        max_retries_spin = ttk.Spinbox(
            parent,
            from_=0,
            to=10,
            increment=1,
            textvariable=max_retries_var,
            width=10
        )
        max_retries_spin.grid(row=row, column=1, sticky="w", pady=5)
        row += 1
        
        # Checkboxes frame
        checks_frame = ttk.Frame(parent)
        checks_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)
        
        # Enable Caching
        cache_var = tk.BooleanVar(value=advanced.get("enable_caching", True))
        self.widgets[agent_key]["enable_caching"] = cache_var
        ttk.Checkbutton(
            checks_frame,
            text="Enable Response Caching",
            variable=cache_var
        ).pack(side="left", padx=(0, 20))
        
        # Enable Logging
        logging_var = tk.BooleanVar(value=advanced.get("enable_logging", True))
        self.widgets[agent_key]["enable_logging"] = logging_var
        ttk.Checkbutton(
            checks_frame,
            text="Enable Detailed Logging",
            variable=logging_var
        ).pack(side="left", padx=(0, 20))
        
        # Enable Metrics
        metrics_var = tk.BooleanVar(value=advanced.get("enable_metrics", True))
        self.widgets[agent_key]["enable_metrics"] = metrics_var
        ttk.Checkbutton(
            checks_frame,
            text="Collect Performance Metrics",
            variable=metrics_var
        ).pack(side="left")
        row += 1
        
        # Performance metrics display
        metrics_frame = ttk.LabelFrame(parent, text="Performance Metrics", padding=10)
        metrics_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)
        
        metrics_text = tk.Text(metrics_frame, height=6, width=60, state="disabled")
        metrics_text.pack(fill="both", expand=True)
        self.widgets[agent_key]["metrics_display"] = metrics_text
        
        # Load existing metrics if available
        self._update_metrics_display(agent_key)
        
    def _create_subagents_settings(self, parent, agent_key: str, config: dict):
        """Create sub-agents configuration UI."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        
        # Instructions
        ttk.Label(
            parent,
            text="Configure sub-agents that this agent can call:",
            font=("", 10, "bold")
        ).grid(row=0, column=0, sticky="w", pady=(0, 10))
        
        # Create treeview for sub-agents
        columns = ("agent_type", "enabled", "priority", "required", "condition")
        tree = tk_ttk.Treeview(parent, columns=columns, show="tree headings", height=8)
        
        # Configure columns
        tree.heading("#0", text="")
        tree.column("#0", width=30)
        tree.heading("agent_type", text="Agent Type")
        tree.column("agent_type", width=150)
        tree.heading("enabled", text="Enabled")
        tree.column("enabled", width=70)
        tree.heading("priority", text="Priority")
        tree.column("priority", width=70)
        tree.heading("required", text="Required")
        tree.column("required", width=70)
        tree.heading("condition", text="Condition")
        tree.column("condition", width=200)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.grid(row=1, column=0, sticky="nsew", padx=(0, 5))
        scrollbar.grid(row=1, column=1, sticky="ns")
        
        self.widgets[agent_key]["subagents_tree"] = tree
        
        # Button frame
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        
        ttk.Button(
            button_frame,
            text="Add Sub-Agent",
            command=lambda: self._add_subagent(agent_key)
        ).pack(side="left", padx=(0, 5))
        
        ttk.Button(
            button_frame,
            text="Edit",
            command=lambda: self._edit_subagent(agent_key)
        ).pack(side="left", padx=(0, 5))
        
        ttk.Button(
            button_frame,
            text="Remove",
            command=lambda: self._remove_subagent(agent_key)
        ).pack(side="left")
        
        # Load existing sub-agents
        sub_agents = config.get("sub_agents", [])
        for sub_agent in sub_agents:
            self._add_subagent_to_tree(tree, sub_agent)
            
    def _add_subagent_to_tree(self, tree, sub_agent: dict):
        """Add a sub-agent to the tree view."""
        values = (
            sub_agent.get("agent_type", ""),
            "✓" if sub_agent.get("enabled", True) else "✗",
            sub_agent.get("priority", 0),
            "✓" if sub_agent.get("required", False) else "✗",
            sub_agent.get("condition", "")
        )
        tree.insert("", "end", values=values, tags=(json.dumps(sub_agent),))
        
    def _add_subagent(self, agent_key: str):
        """Add a new sub-agent configuration."""
        dialog = SubAgentDialog(self.dialog, None)
        result = dialog.show()
        
        if result:
            tree = self.widgets[agent_key]["subagents_tree"]
            self._add_subagent_to_tree(tree, result)
            
    def _edit_subagent(self, agent_key: str):
        """Edit selected sub-agent configuration."""
        tree = self.widgets[agent_key]["subagents_tree"]
        selection = tree.selection()
        
        if not selection:
            messagebox.showwarning("No Selection", "Please select a sub-agent to edit.")
            return
            
        item = selection[0]
        tags = tree.item(item, "tags")
        if tags:
            sub_agent = json.loads(tags[0])
            
            dialog = SubAgentDialog(self.dialog, sub_agent)
            result = dialog.show()
            
            if result:
                # Update tree item
                tree.delete(item)
                self._add_subagent_to_tree(tree, result)
                
    def _remove_subagent(self, agent_key: str):
        """Remove selected sub-agent."""
        tree = self.widgets[agent_key]["subagents_tree"]
        selection = tree.selection()
        
        if selection:
            tree.delete(selection)
            
    def _update_metrics_display(self, agent_key: str):
        """Update the metrics display with latest data."""
        metrics_text = self.widgets[agent_key].get("metrics_display")
        if not metrics_text:
            return
            
        # This would load actual metrics from a metrics store
        # For now, show placeholder
        metrics_text.config(state="normal")
        metrics_text.delete("1.0", tk.END)
        metrics_text.insert("1.0", "No metrics available yet.\n\n")
        metrics_text.insert("end", "Metrics will appear here after agent execution.")
        metrics_text.config(state="disabled")
        
    def _create_buttons(self, parent):
        """Create enhanced dialog buttons."""
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=1, column=0, sticky="ew")
        
        # Left side buttons
        left_frame = ttk.Frame(button_frame)
        left_frame.pack(side=tk.LEFT)
        
        # Reset button
        reset_button = ttk.Button(
            left_frame,
            text="Reset to Defaults",
            command=self._reset_to_defaults
        )
        reset_button.pack(side=tk.LEFT, padx=5)
        
        # Import/Export menu
        import_export_btn = ttk.Menubutton(
            left_frame,
            text="Import/Export"
        )
        import_export_btn.pack(side=tk.LEFT, padx=5)
        
        import_export_menu = tk.Menu(import_export_btn, tearoff=0)
        import_export_btn.configure(menu=import_export_menu)
        
        import_export_menu.add_command(
            label="Import Configuration...",
            command=self._import_configuration
        )
        import_export_menu.add_command(
            label="Export Configuration...",
            command=self._export_configuration
        )
        import_export_menu.add_separator()
        import_export_menu.add_command(
            label="Load Template...",
            command=self._load_template
        )
        import_export_menu.add_command(
            label="Save as Template...",
            command=self._save_as_template
        )
        
        # Test buttons
        test_all_button = ttk.Button(
            left_frame,
            text="Test All Agents",
            command=self._test_all_agents
        )
        test_all_button.pack(side=tk.LEFT, padx=5)
        
        # Right side buttons
        right_frame = ttk.Frame(button_frame)
        right_frame.pack(side=tk.RIGHT)
        
        # Save button
        save_button = ttk.Button(
            right_frame,
            text="Save Settings",
            command=self._save_settings
        )
        save_button.pack(side=tk.RIGHT, padx=5)
        
        # Cancel button
        cancel_button = ttk.Button(
            right_frame,
            text="Cancel",
            command=self.dialog.destroy
        )
        cancel_button.pack(side=tk.RIGHT, padx=5)
        
    def _get_agent_config(self, agent_key: str) -> Dict[str, Any]:
        """Get current configuration for an agent including advanced settings."""
        widgets = self.widgets.get(agent_key, {})
        
        # Get sub-agents from tree
        sub_agents = []
        tree = widgets.get("subagents_tree")
        if tree:
            for item in tree.get_children():
                tags = tree.item(item, "tags")
                if tags:
                    sub_agents.append(json.loads(tags[0]))
        
        # Get basic config with safe defaults
        config = {
            "enabled": widgets.get("enabled", tk.BooleanVar(value=False)).get() if "enabled" in widgets else False,
            "provider": widgets.get("provider", tk.StringVar(value="openai")).get() if "provider" in widgets else "openai",
            "model": widgets.get("model", tk.StringVar(value="gpt-4")).get() if "model" in widgets else "gpt-4",
            "temperature": round(widgets.get("temperature", tk.DoubleVar(value=0.7)).get(), 2) if "temperature" in widgets else 0.7,
            "max_tokens": widgets.get("max_tokens", tk.IntVar(value=300)).get() if "max_tokens" in widgets else 300,
            "system_prompt": widgets["system_prompt"].get("1.0", "end-1c") if "system_prompt" in widgets else "",
            "advanced": {
                "response_format": widgets.get("response_format", tk.StringVar(value="plain_text")).get() if "response_format" in widgets else "plain_text",
                "context_window_size": widgets.get("context_window_size", tk.IntVar(value=5)).get() if "context_window_size" in widgets else 5,
                "timeout_seconds": widgets.get("timeout_seconds", tk.DoubleVar(value=30.0)).get() if "timeout_seconds" in widgets else 30.0,
                "retry_config": {
                    "strategy": widgets.get("retry_strategy", tk.StringVar(value="exponential_backoff")).get() if "retry_strategy" in widgets else "exponential_backoff",
                    "max_retries": widgets.get("max_retries", tk.IntVar(value=3)).get() if "max_retries" in widgets else 3,
                },
                "enable_caching": widgets.get("enable_caching", tk.BooleanVar(value=True)).get() if "enable_caching" in widgets else True,
                "enable_logging": widgets.get("enable_logging", tk.BooleanVar(value=True)).get() if "enable_logging" in widgets else True,
                "enable_metrics": widgets.get("enable_metrics", tk.BooleanVar(value=True)).get() if "enable_metrics" in widgets else True,
            },
            "sub_agents": sub_agents
        }
        
        return config
        
    def _test_all_agents(self):
        """Test all enabled agents with error handling."""
        for agent_type in AgentType:
            agent_key = agent_type.value
            # Check if widgets exist for this agent type
            if agent_key in self.widgets and "enabled" in self.widgets[agent_key]:
                if self.widgets[agent_key]["enabled"].get():
                    self._test_agent(agent_key)
                    
    def _test_agent(self, agent_key: str):
        """Test agent configuration with better error handling."""
        # Check if widgets exist
        if agent_key not in self.widgets:
            logger.warning(f"No widgets found for agent {agent_key}")
            return
            
        widgets = self.widgets[agent_key]
        
        # Update test label if it exists
        test_label = widgets.get("test_label")
        if test_label:
            test_label.config(text="Testing configuration...", foreground="blue")
            self.dialog.update()
        
        try:
            # Get current configuration
            config = self._get_agent_config(agent_key)
            
            # Validate the configuration
            if not config.get("system_prompt", "").strip():
                raise ValueError("System prompt cannot be empty")
                
            temp = config.get("temperature", 0.7)
            if temp < 0 or temp > 2:
                raise ValueError("Temperature must be between 0 and 2")
                
            tokens = config.get("max_tokens", 300)
            if tokens < 50 or tokens > 4000:
                raise ValueError("Max tokens must be between 50 and 4000")
                
            # Mark as successful
            if test_label:
                test_label.config(text="✓ Configuration valid", foreground="green")
            self.test_results[agent_key] = True
            
        except Exception as e:
            if test_label:
                test_label.config(text=f"✗ Error: {str(e)}", foreground="red")
            self.test_results[agent_key] = False
            logger.error(f"Error testing agent {agent_key}: {e}")
        
    def _get_default_config(self, agent_type: AgentType) -> dict:
        """Get default configuration for an agent type."""
        base_config = self.DEFAULT_AGENT_CONFIGS.get(agent_type, {
            "enabled": False,
            "model": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 300,
            "system_prompt": f"You are a {agent_type.value.replace('_', ' ')} assistant."
        })
        
        # Add advanced defaults
        base_config["advanced"] = {
            "response_format": ResponseFormat.PLAIN_TEXT.value,
            "context_window_size": 5,
            "timeout_seconds": 30.0,
            "retry_config": {
                "strategy": RetryStrategy.EXPONENTIAL_BACKOFF.value,
                "max_retries": 3,
                "initial_delay": 1.0,
                "max_delay": 60.0,
                "backoff_factor": 2.0
            },
            "enable_caching": True,
            "cache_ttl_seconds": 3600,
            "enable_logging": True,
            "enable_metrics": True
        }
        
        base_config["sub_agents"] = []
        
        return base_config
        
    def _import_configuration(self):
        """Import agent configuration from file."""
        filename = filedialog.askopenfilename(
            title="Import Agent Configuration",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            parent=self.dialog
        )
        
        if filename:
            try:
                with open(filename, 'r') as f:
                    config = json.load(f)
                    
                # Validate and apply configuration
                if "agent_config" in config:
                    self.settings["agent_config"] = config["agent_config"]
                    messagebox.showinfo(
                        "Import Successful",
                        "Configuration imported successfully. Please review the settings.",
                        parent=self.dialog
                    )
                    # Refresh UI
                    self.dialog.destroy()
                    self.show()
                else:
                    messagebox.showerror(
                        "Invalid Configuration",
                        "The selected file does not contain valid agent configuration.",
                        parent=self.dialog
                    )
                    
            except Exception as e:
                messagebox.showerror(
                    "Import Error",
                    f"Failed to import configuration: {str(e)}",
                    parent=self.dialog
                )
                
    def _export_configuration(self):
        """Export current agent configuration to file."""
        filename = filedialog.asksaveasfilename(
            title="Export Agent Configuration",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            parent=self.dialog
        )
        
        if filename:
            try:
                # Get current configuration
                export_config = {"agent_config": {}}
                
                for agent_type in AgentType:
                    agent_key = agent_type.value
                    export_config["agent_config"][agent_key] = self._get_agent_config(agent_key)
                    
                # Write to file
                with open(filename, 'w') as f:
                    json.dump(export_config, f, indent=2)
                    
                messagebox.showinfo(
                    "Export Successful",
                    f"Configuration exported to {os.path.basename(filename)}",
                    parent=self.dialog
                )
                
            except Exception as e:
                messagebox.showerror(
                    "Export Error",
                    f"Failed to export configuration: {str(e)}",
                    parent=self.dialog
                )
                
    def load_templates(self):
        """Load available agent templates."""
        # This would load from a templates directory or database
        # For now, create some example templates
        self.templates = [
            AgentTemplate(
                id="clinical-workflow",
                name="Clinical Workflow",
                description="Complete clinical documentation workflow",
                category="Medical",
                agent_configs={},  # Would contain full configs
                tags=["medical", "documentation", "workflow"],
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            ),
            AgentTemplate(
                id="diagnostic-assistant",
                name="Diagnostic Assistant",
                description="Enhanced diagnostic support with sub-agents",
                category="Medical",
                agent_configs={},
                tags=["medical", "diagnostic", "analysis"],
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
        ]
        
    def _load_template(self):
        """Load a pre-configured template."""
        dialog = TemplateSelectionDialog(self.dialog, self.templates)
        template = dialog.show()
        
        if template:
            # Apply template configuration
            messagebox.showinfo(
                "Template Loaded",
                f"Template '{template.name}' has been loaded.",
                parent=self.dialog
            )
            
    def _save_as_template(self):
        """Save current configuration as a template."""
        dialog = SaveTemplateDialog(self.dialog)
        result = dialog.show()
        
        if result:
            # Create template from current configuration
            template = AgentTemplate(
                id=result["id"],
                name=result["name"],
                description=result["description"],
                category=result["category"],
                agent_configs={},  # Would be populated from current config
                tags=result["tags"],
                author=os.getenv("USER", "user"),
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
            
            # Save template (would save to file/database)
            messagebox.showinfo(
                "Template Saved",
                f"Template '{template.name}' has been saved.",
                parent=self.dialog
            )


class SubAgentDialog:
    """Dialog for configuring a sub-agent."""
    
    def __init__(self, parent, sub_agent: Optional[dict] = None):
        self.parent = parent
        self.sub_agent = sub_agent
        self.result = None
        
    def show(self) -> Optional[dict]:
        """Show the dialog and return the result."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Configure Sub-Agent")
        self.dialog.geometry("400x350")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Create UI
        frame = ttk.Frame(self.dialog, padding=20)
        frame.pack(fill="both", expand=True)
        
        # Agent Type
        ttk.Label(frame, text="Agent Type:").grid(row=0, column=0, sticky="w", pady=5)
        
        self.agent_type_var = tk.StringVar(
            value=self.sub_agent.get("agent_type", "") if self.sub_agent else ""
        )
        agent_type_combo = ttk.Combobox(
            frame,
            textvariable=self.agent_type_var,
            values=[t.value for t in AgentType],
            state="readonly",
            width=25
        )
        agent_type_combo.grid(row=0, column=1, sticky="w", pady=5)
        
        # Output Key
        ttk.Label(frame, text="Output Key:").grid(row=1, column=0, sticky="w", pady=5)
        
        self.output_key_var = tk.StringVar(
            value=self.sub_agent.get("output_key", "") if self.sub_agent else ""
        )
        output_entry = ttk.Entry(frame, textvariable=self.output_key_var, width=27)
        output_entry.grid(row=1, column=1, sticky="w", pady=5)
        
        # Priority
        ttk.Label(frame, text="Priority:").grid(row=2, column=0, sticky="w", pady=5)
        
        self.priority_var = tk.IntVar(
            value=self.sub_agent.get("priority", 0) if self.sub_agent else 0
        )
        priority_spin = ttk.Spinbox(
            frame, 
            from_=0, 
            to=100, 
            textvariable=self.priority_var,
            width=10
        )
        priority_spin.grid(row=2, column=1, sticky="w", pady=5)
        
        # Checkboxes
        self.enabled_var = tk.BooleanVar(
            value=self.sub_agent.get("enabled", True) if self.sub_agent else True
        )
        ttk.Checkbutton(
            frame, 
            text="Enabled", 
            variable=self.enabled_var
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=5)
        
        self.required_var = tk.BooleanVar(
            value=self.sub_agent.get("required", False) if self.sub_agent else False
        )
        ttk.Checkbutton(
            frame, 
            text="Required (must succeed)", 
            variable=self.required_var
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=5)
        
        self.pass_context_var = tk.BooleanVar(
            value=self.sub_agent.get("pass_context", True) if self.sub_agent else True
        )
        ttk.Checkbutton(
            frame, 
            text="Pass parent context", 
            variable=self.pass_context_var
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=5)
        
        # Condition
        ttk.Label(frame, text="Condition (optional):").grid(row=6, column=0, sticky="nw", pady=5)
        
        self.condition_text = tk.Text(frame, height=3, width=30)
        self.condition_text.grid(row=6, column=1, sticky="w", pady=5)
        if self.sub_agent and self.sub_agent.get("condition"):
            self.condition_text.insert("1.0", self.sub_agent["condition"])
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=7, column=0, columnspan=2, pady=20)
        
        ttk.Button(
            button_frame,
            text="OK",
            command=self._ok_clicked
        ).pack(side="left", padx=5)
        
        ttk.Button(
            button_frame,
            text="Cancel",
            command=self.dialog.destroy
        ).pack(side="left", padx=5)
        
        # Center dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - self.dialog.winfo_width()) // 2
        y = (self.dialog.winfo_screenheight() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")
        
        self.dialog.wait_window()
        return self.result
        
    def _ok_clicked(self):
        """Handle OK button click."""
        if not self.agent_type_var.get():
            messagebox.showerror("Error", "Please select an agent type.")
            return
            
        if not self.output_key_var.get():
            messagebox.showerror("Error", "Please enter an output key.")
            return
            
        self.result = {
            "agent_type": self.agent_type_var.get(),
            "output_key": self.output_key_var.get(),
            "priority": self.priority_var.get(),
            "enabled": self.enabled_var.get(),
            "required": self.required_var.get(),
            "pass_context": self.pass_context_var.get(),
            "condition": self.condition_text.get("1.0", "end-1c").strip() or None
        }
        
        self.dialog.destroy()


class TemplateSelectionDialog:
    """Dialog for selecting an agent template."""
    
    def __init__(self, parent, templates: List[AgentTemplate]):
        self.parent = parent
        self.templates = templates
        self.selected_template = None
        
    def show(self) -> Optional[AgentTemplate]:
        """Show the dialog and return selected template."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Select Template")
        self.dialog.geometry("600x400")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Create UI
        frame = ttk.Frame(self.dialog, padding=10)
        frame.pack(fill="both", expand=True)
        
        # Template list
        columns = ("name", "category", "description")
        self.tree = tk_ttk.Treeview(frame, columns=columns, show="tree headings", height=12)
        
        self.tree.heading("name", text="Name")
        self.tree.column("name", width=150)
        self.tree.heading("category", text="Category")
        self.tree.column("category", width=100)
        self.tree.heading("description", text="Description")
        self.tree.column("description", width=300)
        
        # Add templates
        for template in self.templates:
            self.tree.insert("", "end", values=(
                template.name,
                template.category,
                template.description
            ), tags=(template,))
            
        self.tree.pack(fill="both", expand=True)
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill="x", pady=(10, 0))
        
        ttk.Button(
            button_frame,
            text="Load Template",
            command=self._load_clicked
        ).pack(side="right", padx=(5, 0))
        
        ttk.Button(
            button_frame,
            text="Cancel",
            command=self.dialog.destroy
        ).pack(side="right")
        
        self.dialog.wait_window()
        return self.selected_template
        
    def _load_clicked(self):
        """Handle load button click."""
        selection = self.tree.selection()
        if selection:
            tags = self.tree.item(selection[0], "tags")
            if tags:
                self.selected_template = tags[0]
                self.dialog.destroy()
        else:
            messagebox.showwarning("No Selection", "Please select a template.")


class SaveTemplateDialog:
    """Dialog for saving configuration as template."""
    
    def __init__(self, parent):
        self.parent = parent
        self.result = None
        
    def show(self) -> Optional[dict]:
        """Show the dialog and return template info."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Save as Template")
        self.dialog.geometry("400x300")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Create UI
        frame = ttk.Frame(self.dialog, padding=20)
        frame.pack(fill="both", expand=True)
        
        # Template ID
        ttk.Label(frame, text="Template ID:").grid(row=0, column=0, sticky="w", pady=5)
        self.id_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.id_var, width=30).grid(row=0, column=1, pady=5)
        
        # Name
        ttk.Label(frame, text="Name:").grid(row=1, column=0, sticky="w", pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.name_var, width=30).grid(row=1, column=1, pady=5)
        
        # Category
        ttk.Label(frame, text="Category:").grid(row=2, column=0, sticky="w", pady=5)
        self.category_var = tk.StringVar()
        category_combo = ttk.Combobox(
            frame,
            textvariable=self.category_var,
            values=["Medical", "General", "Custom"],
            width=27
        )
        category_combo.grid(row=2, column=1, pady=5)
        
        # Description
        ttk.Label(frame, text="Description:").grid(row=3, column=0, sticky="nw", pady=5)
        self.desc_text = tk.Text(frame, height=4, width=30)
        self.desc_text.grid(row=3, column=1, pady=5)
        
        # Tags
        ttk.Label(frame, text="Tags (comma-separated):").grid(row=4, column=0, sticky="w", pady=5)
        self.tags_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.tags_var, width=30).grid(row=4, column=1, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)
        
        ttk.Button(
            button_frame,
            text="Save",
            command=self._save_clicked
        ).pack(side="left", padx=5)
        
        ttk.Button(
            button_frame,
            text="Cancel",
            command=self.dialog.destroy
        ).pack(side="left", padx=5)
        
        self.dialog.wait_window()
        return self.result
        
    def _save_clicked(self):
        """Handle save button click."""
        if not all([self.id_var.get(), self.name_var.get(), self.category_var.get()]):
            messagebox.showerror("Error", "Please fill in all required fields.")
            return
            
        self.result = {
            "id": self.id_var.get(),
            "name": self.name_var.get(),
            "category": self.category_var.get(),
            "description": self.desc_text.get("1.0", "end-1c"),
            "tags": [t.strip() for t in self.tags_var.get().split(",") if t.strip()]
        }
        
        self.dialog.destroy()
    
    def _save_settings(self):
        """Save all agent settings."""
        try:
            # Update settings with current values
            for agent_type in AgentType:
                agent_key = agent_type.value
                if agent_key in self.widgets:
                    self.settings["agent_config"][agent_key] = self._get_agent_config(agent_key)
                    
            # Save to file
            save_settings(self.settings)
            
            # Reload agents to apply new settings
            from managers.agent_manager import agent_manager
            agent_manager.reload_agents()
            
            messagebox.showinfo(
                "Settings Saved",
                "Agent settings have been saved successfully.",
                parent=self.dialog
            )
            
            self.dialog.destroy()
            
        except Exception as e:
            logger.error(f"Error saving agent settings: {e}")
            messagebox.showerror(
                "Save Error",
                f"Failed to save settings: {str(e)}",
                parent=self.dialog
            )


def show_advanced_agent_settings_dialog(parent):
    """Show the advanced agent settings dialog.
    
    Args:
        parent: Parent window
    """
    dialog = AdvancedAgentSettingsDialog(parent)
    dialog.show()