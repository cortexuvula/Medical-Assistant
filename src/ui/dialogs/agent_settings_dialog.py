"""
Agent Settings Dialog

Provides a UI for configuring AI agent parameters including model selection,
temperature, max tokens, and system prompts for each agent type.
"""

import tkinter as tk
from tkinter import messagebox, scrolledtext
import ttkbootstrap as ttk
from typing import Dict, Any, Optional
import logging

from settings.settings import load_settings, save_settings, _DEFAULT_SETTINGS
from ai.agents.models import AgentType
from ai.agents.synopsis import SynopsisAgent

logger = logging.getLogger(__name__)


class AgentSettingsDialog:
    """Dialog for configuring agent settings."""
    
    # Default configurations for each agent type
    DEFAULT_AGENT_CONFIGS = {
        AgentType.SYNOPSIS: {
            "enabled": True,
            "model": "gpt-4",
            "temperature": 0.3,
            "max_tokens": 300,
            "system_prompt": SynopsisAgent.DEFAULT_CONFIG.system_prompt
        },
        AgentType.DIAGNOSTIC: {
            "enabled": False,
            "model": "gpt-4",
            "temperature": 0.1,
            "max_tokens": 500,
            "system_prompt": """You are a medical diagnostic assistant. Analyze symptoms and clinical findings to suggest potential diagnoses. 
Always include differential diagnoses and recommend appropriate investigations. 
Never provide definitive diagnoses - only suggestions for clinical consideration."""
        },
        AgentType.MEDICATION: {
            "enabled": False,
            "model": "gpt-4",
            "temperature": 0.2,
            "max_tokens": 400,
            "system_prompt": """You are a medication management assistant. Help with medication selection, dosing, and interaction checking.
Always emphasize the importance of clinical judgment and patient-specific factors.
Include warnings about contraindications and potential side effects."""
        },
        AgentType.REFERRAL: {
            "enabled": False,
            "model": "gpt-4",
            "temperature": 0.3,
            "max_tokens": 350,
            "system_prompt": """You are a referral letter specialist. Generate professional, concise referral letters that include:
1. Clear reason for referral
2. Relevant clinical history
3. Current medications
4. Specific questions or requests
5. Urgency level
Format letters professionally and appropriately for the specialty."""
        },
        AgentType.DATA_EXTRACTION: {
            "enabled": False,
            "model": "gpt-3.5-turbo",
            "temperature": 0.0,
            "max_tokens": 300,
            "system_prompt": """You are a clinical data extraction specialist. Extract structured data from clinical text including:
- Vital signs
- Laboratory values
- Medications with dosages
- Diagnoses with ICD codes
- Procedures
Return data in a structured, consistent format."""
        },
        AgentType.WORKFLOW: {
            "enabled": False,
            "model": "gpt-4",
            "temperature": 0.3,
            "max_tokens": 500,
            "system_prompt": """You are a clinical workflow coordinator. Help manage multi-step medical processes including:
- Patient intake workflows
- Diagnostic workup planning
- Treatment protocols
- Follow-up scheduling
Provide clear, step-by-step guidance while maintaining flexibility for clinical judgment."""
        }
    }
    
    # Available models for each provider
    PROVIDER_MODELS = {
        "openai": ["gpt-4-turbo-preview", "gpt-4", "gpt-3.5-turbo"],
        "anthropic": ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"],
        "ollama": ["llama3", "mistral", "codellama"],
        "perplexity": ["sonar-medium-chat", "sonar-small-chat"],
        "grok": ["grok-1"]
    }
    
    def __init__(self, parent):
        """Initialize the agent settings dialog.
        
        Args:
            parent: Parent window
        """
        self.parent = parent
        self.dialog = None
        self.settings = load_settings()
        self.widgets = {}
        self.test_results = {}
        
        # Ensure agent_config exists in settings
        if "agent_config" not in self.settings:
            self.settings["agent_config"] = {}
            
    def show(self):
        """Show the agent settings dialog."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Agent Settings")
        self.dialog.geometry("900x700")
        self.dialog.minsize(800, 600)
        
        # Make it modal
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Configure grid
        self.dialog.rowconfigure(0, weight=1)
        self.dialog.columnconfigure(0, weight=1)
        
        # Create main container
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        
        # Create notebook for agent tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        
        # Create tabs for each agent type
        for agent_type in AgentType:
            self._create_agent_tab(agent_type)
            
        # Create button frame
        self._create_buttons(main_frame)
        
        # Center the dialog
        self.dialog.update_idletasks()
        width = self.dialog.winfo_width()
        height = self.dialog.winfo_height()
        x = self.parent.winfo_rootx() + (self.parent.winfo_width() - width) // 2
        y = self.parent.winfo_rooty() + (self.parent.winfo_height() - height) // 2
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")
        
        # Wait for dialog to close
        self.dialog.wait_window()
        
    def _create_agent_tab(self, agent_type: AgentType):
        """Create a tab for an agent type.
        
        Args:
            agent_type: The agent type enum
        """
        # Create frame for the tab
        tab_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab_frame, text=agent_type.value.replace("_", " ").title())
        
        # Configure grid
        tab_frame.columnconfigure(1, weight=1)
        
        # Get current config or use defaults
        agent_key = agent_type.value
        if agent_key not in self.settings["agent_config"]:
            self.settings["agent_config"][agent_key] = self.DEFAULT_AGENT_CONFIGS[agent_type].copy()
        
        current_config = self.settings["agent_config"][agent_key]
        
        # Store widgets for this agent
        self.widgets[agent_key] = {}
        
        row = 0
        
        # Enable/Disable checkbox
        enabled_var = tk.BooleanVar(value=current_config.get("enabled", False))
        self.widgets[agent_key]["enabled"] = enabled_var
        
        enabled_check = ttk.Checkbutton(
            tab_frame, 
            text="Enable this agent",
            variable=enabled_var,
            command=lambda: self._toggle_agent_controls(agent_key)
        )
        enabled_check.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 10))
        row += 1
        
        # AI Provider selection
        ttk.Label(tab_frame, text="AI Provider:").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=5)
        
        # Get current provider from settings or default to openai
        current_provider = self.settings.get("ai_provider", "openai")
        provider_var = tk.StringVar(value=current_provider)
        self.widgets[agent_key]["provider"] = provider_var
        
        provider_combo = ttk.Combobox(
            tab_frame,
            textvariable=provider_var,
            values=list(self.PROVIDER_MODELS.keys()),
            state="readonly",
            width=20
        )
        provider_combo.grid(row=row, column=1, sticky="w", pady=5)
        provider_combo.bind("<<ComboboxSelected>>", lambda e: self._update_model_list(agent_key))
        row += 1
        
        # Model selection
        ttk.Label(tab_frame, text="Model:").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=5)
        
        model_var = tk.StringVar(value=current_config.get("model", "gpt-4"))
        self.widgets[agent_key]["model"] = model_var
        
        model_combo = ttk.Combobox(
            tab_frame,
            textvariable=model_var,
            values=self.PROVIDER_MODELS.get(current_provider, []),
            state="readonly",
            width=30
        )
        model_combo.grid(row=row, column=1, sticky="w", pady=5)
        self.widgets[agent_key]["model_combo"] = model_combo
        row += 1
        
        # Temperature slider
        ttk.Label(tab_frame, text="Temperature:").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=5)
        
        temp_frame = ttk.Frame(tab_frame)
        temp_frame.grid(row=row, column=1, sticky="ew", pady=5)
        temp_frame.columnconfigure(0, weight=1)
        
        temp_var = tk.DoubleVar(value=current_config.get("temperature", 0.7))
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
        
        # Update temperature label
        def update_temp_label(*args):
            temp_label.config(text=f"{temp_var.get():.2f}")
        
        temp_slider.bind("<Motion>", update_temp_label)
        temp_slider.bind("<ButtonRelease-1>", update_temp_label)
        row += 1
        
        # Max tokens
        ttk.Label(tab_frame, text="Max Tokens:").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=5)
        
        tokens_var = tk.IntVar(value=current_config.get("max_tokens", 300))
        self.widgets[agent_key]["max_tokens"] = tokens_var
        
        tokens_spin = ttk.Spinbox(
            tab_frame,
            from_=50,
            to=4000,
            increment=50,
            textvariable=tokens_var,
            width=10
        )
        tokens_spin.grid(row=row, column=1, sticky="w", pady=5)
        row += 1
        
        # System prompt
        ttk.Label(tab_frame, text="System Prompt:").grid(row=row, column=0, sticky="nw", padx=(0, 10), pady=5)
        
        prompt_text = scrolledtext.ScrolledText(
            tab_frame,
            height=10,
            width=60,
            wrap=tk.WORD
        )
        prompt_text.grid(row=row, column=1, sticky="ew", pady=5)
        prompt_text.insert("1.0", current_config.get("system_prompt", ""))
        self.widgets[agent_key]["system_prompt"] = prompt_text
        tab_frame.rowconfigure(row, weight=1)
        row += 1
        
        # Test button
        test_button = ttk.Button(
            tab_frame,
            text="Test Agent Configuration",
            command=lambda: self._test_agent(agent_key)
        )
        test_button.grid(row=row, column=1, sticky="w", pady=(10, 0))
        self.widgets[agent_key]["test_button"] = test_button
        
        # Test result label
        test_label = ttk.Label(tab_frame, text="", foreground="gray")
        test_label.grid(row=row+1, column=1, sticky="w", pady=(5, 0))
        self.widgets[agent_key]["test_label"] = test_label
        
        # Set initial control states
        self._toggle_agent_controls(agent_key)
        
    def _toggle_agent_controls(self, agent_key: str):
        """Enable/disable controls based on agent enabled state.
        
        Args:
            agent_key: The agent identifier
        """
        enabled = self.widgets[agent_key]["enabled"].get()
        state = "normal" if enabled else "disabled"
        
        # Enable/disable all controls except the enabled checkbox
        if "model_combo" in self.widgets[agent_key]:
            self.widgets[agent_key]["model_combo"].config(state="readonly" if enabled else "disabled")
        
        for widget_key in ["system_prompt", "test_button"]:
            if widget_key in self.widgets[agent_key]:
                widget = self.widgets[agent_key][widget_key]
                if hasattr(widget, 'config'):
                    if widget_key == "system_prompt":
                        widget.config(state=state)
                    else:
                        widget.config(state=state)
                        
    def _update_model_list(self, agent_key: str):
        """Update model list based on selected provider.
        
        Args:
            agent_key: The agent identifier
        """
        provider = self.widgets[agent_key]["provider"].get()
        models = self.PROVIDER_MODELS.get(provider, [])
        
        model_combo = self.widgets[agent_key]["model_combo"]
        model_combo["values"] = models
        
        # Set to first model if current model not in list
        current_model = self.widgets[agent_key]["model"].get()
        if current_model not in models and models:
            self.widgets[agent_key]["model"].set(models[0])
            
    def _test_agent(self, agent_key: str):
        """Test agent configuration.
        
        Args:
            agent_key: The agent identifier
        """
        # Update test label
        test_label = self.widgets[agent_key]["test_label"]
        test_label.config(text="Testing configuration...", foreground="blue")
        self.dialog.update()
        
        try:
            # Get current configuration
            config = self._get_agent_config(agent_key)
            
            # For now, just validate the configuration
            # In the future, this could make a test API call
            if not config["system_prompt"].strip():
                raise ValueError("System prompt cannot be empty")
                
            if config["temperature"] < 0 or config["temperature"] > 2:
                raise ValueError("Temperature must be between 0 and 2")
                
            if config["max_tokens"] < 50 or config["max_tokens"] > 4000:
                raise ValueError("Max tokens must be between 50 and 4000")
                
            # Mark as successful
            test_label.config(text="✓ Configuration valid", foreground="green")
            self.test_results[agent_key] = True
            
        except Exception as e:
            test_label.config(text=f"✗ Error: {str(e)}", foreground="red")
            self.test_results[agent_key] = False
            
    def _get_agent_config(self, agent_key: str) -> Dict[str, Any]:
        """Get current configuration for an agent.
        
        Args:
            agent_key: The agent identifier
            
        Returns:
            Dictionary with agent configuration
        """
        widgets = self.widgets[agent_key]
        
        return {
            "enabled": widgets["enabled"].get(),
            "provider": widgets["provider"].get(),
            "model": widgets["model"].get(),
            "temperature": round(widgets["temperature"].get(), 2),
            "max_tokens": widgets["max_tokens"].get(),
            "system_prompt": widgets["system_prompt"].get("1.0", "end-1c")
        }
        
    def _create_buttons(self, parent):
        """Create dialog buttons.
        
        Args:
            parent: Parent frame
        """
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=1, column=0, sticky="ew")
        
        # Reset button
        reset_button = ttk.Button(
            button_frame,
            text="Reset to Defaults",
            command=self._reset_to_defaults
        )
        reset_button.pack(side=tk.LEFT, padx=5)
        
        # Test all button
        test_all_button = ttk.Button(
            button_frame,
            text="Test All Agents",
            command=self._test_all_agents
        )
        test_all_button.pack(side=tk.LEFT, padx=5)
        
        # Save button
        save_button = ttk.Button(
            button_frame,
            text="Save Settings",
            command=self._save_settings
        )
        save_button.pack(side=tk.RIGHT, padx=5)
        
        # Cancel button
        cancel_button = ttk.Button(
            button_frame,
            text="Cancel",
            command=self.dialog.destroy
        )
        cancel_button.pack(side=tk.RIGHT, padx=5)
        
    def _reset_to_defaults(self):
        """Reset all settings to defaults."""
        response = messagebox.askyesno(
            "Reset to Defaults",
            "Are you sure you want to reset all agent settings to defaults?",
            parent=self.dialog
        )
        
        if response:
            # Reset each agent to defaults
            for agent_type in AgentType:
                agent_key = agent_type.value
                default_config = self.DEFAULT_AGENT_CONFIGS[agent_type]
                
                widgets = self.widgets[agent_key]
                widgets["enabled"].set(default_config["enabled"])
                widgets["model"].set(default_config["model"])
                widgets["temperature"].set(default_config["temperature"])
                widgets["max_tokens"].set(default_config["max_tokens"])
                widgets["system_prompt"].delete("1.0", tk.END)
                widgets["system_prompt"].insert("1.0", default_config["system_prompt"])
                widgets["temp_label"].config(text=f"{default_config['temperature']:.2f}")
                
                # Update control states
                self._toggle_agent_controls(agent_key)
                
    def _test_all_agents(self):
        """Test all enabled agents."""
        for agent_type in AgentType:
            agent_key = agent_type.value
            if self.widgets[agent_key]["enabled"].get():
                self._test_agent(agent_key)
                
    def _save_settings(self):
        """Save all agent settings."""
        try:
            # Update settings with current values
            for agent_type in AgentType:
                agent_key = agent_type.value
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


def show_agent_settings_dialog(parent):
    """Show the agent settings dialog.
    
    Args:
        parent: Parent window
    """
    dialog = AgentSettingsDialog(parent)
    dialog.show()