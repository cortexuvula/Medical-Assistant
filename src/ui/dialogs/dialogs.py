"""
Dialogs Module

This module provides dialog functions for the Medical Assistant application.
Functions are organized into submodules for better maintainability:

- model_providers: Functions for fetching AI model lists from providers
- dialog_utils: Common dialog utility functions
- audio_settings: Audio/TTS/STT settings dialogs

For backward compatibility, all functions are re-exported from this module.
"""

import os
from ui.scaling_utils import ui_scaler
import logging
import tkinter as tk
from tkinter import messagebox, scrolledtext
import ttkbootstrap as ttk
import re
from typing import Dict, Tuple, List
import requests
import json
from openai import OpenAI
import time
from functools import lru_cache

# Import from submodules for organization
from ui.dialogs.model_providers import (
    clear_model_cache,
    get_openai_models,
    get_fallback_openai_models,
    get_ollama_models,
    get_anthropic_models,
    get_fallback_anthropic_models,
    get_gemini_models,
    get_fallback_gemini_models,
    _model_cache,
    _cache_ttl,
)

from ui.dialogs.dialog_utils import (
    create_toplevel_dialog,
    create_model_selector,
    create_model_selection_dialog,
    askstring_min,
    ask_conditions_dialog,
)

from ui.dialogs.audio_settings import (
    show_elevenlabs_settings_dialog,
    show_deepgram_settings_dialog,
    show_groq_settings_dialog,
    show_translation_settings_dialog,
    show_tts_settings_dialog,
    show_custom_suggestions_dialog,
    test_ollama_connection,
    _fetch_tts_voices,
)


# ============================================================================
# API Key Dialogs
# ============================================================================

def prompt_for_api_key(provider: str = "OpenAI") -> str:
    """Prompt the user for their API key."""
    dialog = tk.Toplevel()
    dialog.title(f"{provider} API Key Required")
    dialog_width, dialog_height = ui_scaler.get_dialog_size(450, 200)
    dialog.geometry(f"{dialog_width}x{dialog_height}")

    # Center the dialog
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - (dialog_width // 2)
    y = (dialog.winfo_screenheight() // 2) - (dialog_height // 2)
    dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

    # Grab focus after window is visible
    dialog.deiconify()
    try:
        dialog.grab_set()
    except tk.TclError:
        pass  # Window not viewable yet

    env_var_name = {
        "OpenAI": "OPENAI_API_KEY",
        "Anthropic": "ANTHROPIC_API_KEY",
        "Gemini": "GEMINI_API_KEY"
    }.get(provider, "API_KEY")

    provider_url = {
        "OpenAI": "https://platform.openai.com/account/api-keys",
        "Anthropic": "https://console.anthropic.com/account/keys",
        "Gemini": "https://aistudio.google.com/app/apikey"
    }.get(provider, "provider website")
    
    ttk.Label(dialog, text=f"Please enter your {provider} API Key:", wraplength=400).pack(pady=(20, 5))
    ttk.Label(dialog, text=f"You can get your key from your {provider_url}", 
              font=("Segoe UI", 8), foreground="blue").pack()
    
    entry = ttk.Entry(dialog, width=50)
    entry.pack(pady=10, padx=20)
    
    # Add checkbox for saving the key
    save_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(dialog, text="Save key for future sessions", variable=save_var).pack()
    
    result = [None]
    
    def on_ok():
        key = entry.get().strip()
        if key:
            result[0] = key
            # Set environment variable
            os.environ[env_var_name] = key
            # Save to .env file if requested
            if save_var.get():
                save_api_key_to_env(key, env_var_name)
        dialog.destroy()
    
    def on_cancel():
        dialog.destroy()
    
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(pady=20)
    ttk.Button(btn_frame, text="OK", command=on_ok).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side=tk.LEFT, padx=5)
    
    dialog.wait_window()
    return result[0]

def save_api_key_to_env(key: str, env_var_name: str) -> None:
    """Save the API key to the .env file."""
    try:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        env_content = ""
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                env_content = f.read()
        
        # Replace existing API key or add new one
        if f'{env_var_name}=' in env_content:
            env_content = re.sub(f'{env_var_name}=.*', f'{env_var_name}={key}', env_content)
        else:
            env_content += f'\n{env_var_name}={key}'
        
        with open(env_path, 'w') as f:
            f.write(env_content)
        
        logging.info(f"{env_var_name} saved to .env file")
    except Exception as e:
        logging.error(f"Failed to save {env_var_name}: {e}")


# ============================================================================
# Settings Tab Helpers
# ============================================================================

def _create_prompt_tab(parent: ttk.Frame, current_prompt: str, current_system_prompt: str) -> Tuple[tk.Text, tk.Text]:
    """Create the prompts tab content.
    
    Args:
        parent: Parent frame for the tab
        current_prompt: Current user prompt
        current_system_prompt: Current system prompt
        
    Returns:
        Tuple of (user_prompt_text, system_prompt_text) widgets
    """
    # User Prompt
    ttk.Label(parent, text="User Prompt:").grid(row=0, column=0, sticky="nw", pady=(10, 5))
    prompt_text = scrolledtext.ScrolledText(parent, width=60, height=5)
    prompt_text.grid(row=0, column=1, padx=5, pady=(10, 5))
    prompt_text.insert("1.0", current_prompt)
    
    # System Prompt
    ttk.Label(parent, text="System Prompt:").grid(row=1, column=0, sticky="nw", pady=(5, 10))
    system_prompt_text = scrolledtext.ScrolledText(parent, width=60, height=15)
    system_prompt_text.grid(row=1, column=1, padx=5, pady=(5, 10))
    system_prompt_text.insert("1.0", current_system_prompt)
    
    return prompt_text, system_prompt_text


def _create_soap_prompts_tab(parent: ttk.Frame, current_prompt: str,
                              provider_messages: Dict[str, str],
                              current_icd_version: str = "ICD-9") -> Tuple[tk.Text, Dict[str, tk.Text]]:
    """Create the SOAP prompts tab with per-provider system message tabs.

    Args:
        parent: Parent frame for the tab
        current_prompt: Current user prompt (shared across all providers)
        provider_messages: Dict mapping provider names to their current system messages
        current_icd_version: Current ICD code version for showing defaults

    Returns:
        Tuple of (user_prompt_text, dict of provider_name -> system_prompt_text widgets)
    """
    from ai.prompts import SOAP_PROVIDERS, SOAP_PROVIDER_NAMES, get_soap_system_message

    # User Prompt (shared across all providers)
    prompt_frame = ttk.Labelframe(parent, text="User Prompt (shared)", padding=5)
    prompt_frame.pack(fill=tk.X, padx=5, pady=(5, 10))

    prompt_text = scrolledtext.ScrolledText(prompt_frame, width=80, height=3)
    prompt_text.pack(fill=tk.X, padx=5, pady=5)
    prompt_text.insert("1.0", current_prompt)

    # Info label
    info_label = ttk.Label(parent,
                          text="Each AI provider can have its own system prompt. Leave empty to use the optimized default.",
                          foreground="gray")
    info_label.pack(anchor="w", padx=10, pady=(0, 5))

    # Create nested notebook for provider-specific system prompts
    provider_notebook = ttk.Notebook(parent)
    provider_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    system_prompt_texts = {}

    for provider in SOAP_PROVIDERS:
        provider_tab = ttk.Frame(provider_notebook)
        provider_notebook.add(provider_tab, text=SOAP_PROVIDER_NAMES.get(provider, provider.title()))

        # Get current message for this provider
        current_msg = provider_messages.get(f"{provider}_system_message", "")

        # Create frame for system message
        msg_frame = ttk.Frame(provider_tab)
        msg_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Label with provider name
        header_frame = ttk.Frame(msg_frame)
        header_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(header_frame,
                 text=f"System Prompt for {SOAP_PROVIDER_NAMES.get(provider, provider.title())}:").pack(side=tk.LEFT)

        # Status indicator
        status_text = "Using custom prompt" if current_msg and current_msg.strip() else "Using optimized default"
        status_color = "blue" if current_msg and current_msg.strip() else "green"
        status_label = ttk.Label(header_frame, text=f"({status_text})", foreground=status_color)
        status_label.pack(side=tk.LEFT, padx=(10, 0))

        # Text area for system prompt
        system_text = scrolledtext.ScrolledText(msg_frame, width=80, height=12)
        system_text.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        system_text.insert("1.0", current_msg)
        system_prompt_texts[provider] = system_text

        # Button frame
        btn_frame = ttk.Frame(msg_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 5))

        # Show Default button
        def show_default(p=provider, text_widget=system_text, icd=current_icd_version):
            default_prompt = get_soap_system_message(icd, provider=p)
            # Show in a new window
            default_win = tk.Toplevel(parent)
            default_win.title(f"Default {SOAP_PROVIDER_NAMES.get(p, p.title())} Prompt")
            default_win.geometry("800x600")
            default_win.transient(parent.winfo_toplevel())

            default_text = scrolledtext.ScrolledText(default_win, width=90, height=30)
            default_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            default_text.insert("1.0", default_prompt)
            default_text.config(state=tk.DISABLED)

            ttk.Button(default_win, text="Close", command=default_win.destroy).pack(pady=10)

        def clear_to_default(text_widget=system_text, status_lbl=status_label):
            text_widget.delete("1.0", tk.END)
            status_lbl.config(text="(Using optimized default)", foreground="green")

        def update_status(event=None, text_widget=system_text, status_lbl=status_label):
            content = text_widget.get("1.0", tk.END).strip()
            if content:
                status_lbl.config(text="(Using custom prompt)", foreground="blue")
            else:
                status_lbl.config(text="(Using optimized default)", foreground="green")

        # Bind text change to update status
        system_text.bind("<KeyRelease>", update_status)

        ttk.Button(btn_frame, text="Show Default", command=show_default).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Clear (Use Default)", command=clear_to_default).pack(side=tk.LEFT, padx=(0, 5))

    return prompt_text, system_prompt_texts


def _create_models_tab(parent: ttk.Frame, current_model: str,
                      current_ollama: str, current_anthropic: str,
                      current_gemini: str = "") -> Dict[str, tk.StringVar]:
    """Create the models tab content.

    Args:
        parent: Parent frame for the tab
        current_model: Current OpenAI model
        current_ollama: Current Ollama model
        current_anthropic: Current Anthropic model
        current_gemini: Current Gemini model

    Returns:
        Dictionary of model StringVars
    """
    model_vars = {}

    # OpenAI Model
    ttk.Label(parent, text="OpenAI Model:").grid(row=0, column=0, sticky="nw", pady=(10, 5))
    openai_model_var = tk.StringVar(value=current_model)
    model_vars['openai'] = openai_model_var
    create_model_selector(parent, parent, openai_model_var, "OpenAI", get_openai_models, row=0)

    # Ollama Model
    ttk.Label(parent, text="Ollama Model:").grid(row=1, column=0, sticky="nw", pady=(5, 5))
    ollama_model_var = tk.StringVar(value=current_ollama)
    model_vars['ollama'] = ollama_model_var
    create_model_selector(parent, parent, ollama_model_var, "Ollama", get_ollama_models, row=1)

    # Anthropic Model
    ttk.Label(parent, text="Anthropic Model:").grid(row=2, column=0, sticky="nw", pady=(5, 5))
    anthropic_model_var = tk.StringVar(value=current_anthropic)
    model_vars['anthropic'] = anthropic_model_var
    create_model_selector(parent, parent, anthropic_model_var, "Anthropic", get_anthropic_models, row=2)

    # Gemini Model
    ttk.Label(parent, text="Gemini Model:").grid(row=3, column=0, sticky="nw", pady=(5, 10))
    gemini_model_var = tk.StringVar(value=current_gemini)
    model_vars['gemini'] = gemini_model_var
    create_model_selector(parent, parent, gemini_model_var, "Gemini", get_gemini_models, row=3)

    return model_vars

def _create_temperature_tab(parent: ttk.Frame, current_temp: float, default_temp: float) -> Tuple[tk.Scale, tk.StringVar]:
    """Create the temperature tab content.
    
    Args:
        parent: Parent frame for the tab
        current_temp: Current temperature value
        default_temp: Default temperature value
        
    Returns:
        Tuple of (temperature_scale, temp_value_var)
    """
    # Temperature setting
    ttk.Label(parent, text="Temperature:").grid(row=0, column=0, sticky="w", pady=(10, 5))
    
    temp_frame = ttk.Frame(parent)
    temp_frame.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=(10, 5))
    
    temp_value_var = tk.StringVar(value=f"{current_temp:.1f}")
    temp_scale = tk.Scale(temp_frame, from_=0.0, to=2.0, resolution=0.1, 
                         orient=tk.HORIZONTAL, length=400,
                         command=lambda v: temp_value_var.set(f"{float(v):.1f}"))
    temp_scale.set(current_temp)
    temp_scale.pack(side=tk.LEFT, padx=(0, 10))
    
    ttk.Label(temp_frame, textvariable=temp_value_var).pack(side=tk.LEFT)
    
    # Temperature explanation
    explanation = ttk.Label(parent, text=
        "Temperature controls the randomness of the AI's responses:\n"
        "• 0.0 = Most focused and deterministic\n"
        "• 0.7 = Balanced creativity and consistency (recommended)\n"
        "• 1.0 = More creative and varied\n"
        "• 2.0 = Maximum randomness (may produce unusual results)",
        justify=tk.LEFT, foreground="gray")
    explanation.grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 5), padx=(10, 0))
    
    # Reset to default button
    def reset_temperature():
        temp_scale.set(default_temp)
        temp_value_var.set(f"{default_temp:.1f}")
    
    ttk.Button(parent, text=f"Reset to Default ({default_temp})", 
               command=reset_temperature).grid(row=2, column=1, sticky="w", padx=(10, 0), pady=(5, 10))
    
    return temp_scale, temp_value_var

def show_settings_dialog(parent: tk.Tk, title: str, config: dict, default: dict,
                         current_prompt: str, current_model: str,
                         save_callback: callable, current_ollama: str = "", current_system_prompt: str = "",
                         current_anthropic: str = "", current_gemini: str = "",
                         current_icd_version: str = "ICD-9", is_soap_settings: bool = False,
                         current_provider: str = "", is_advanced_analysis: bool = False,
                         provider_messages: Dict[str, str] = None) -> None:
    """Show settings dialog for configuring prompt and model.

    Args:
        parent: Parent window
        title: Dialog title
        config: Current configuration
        default: Default configuration
        current_prompt: Current prompt text
        current_model: Current OpenAI model
        save_callback: Callback for saving settings
        current_ollama: Current Ollama model
        current_system_prompt: Current system prompt text
        current_anthropic: Current Anthropic model
        current_gemini: Current Gemini model
        current_icd_version: Current ICD code version (ICD-9, ICD-10, or both)
        is_soap_settings: Whether this is the SOAP settings dialog (shows ICD selector)
        current_provider: Current AI provider for Advanced Analysis (empty = use global)
        is_advanced_analysis: Whether this is the Advanced Analysis settings dialog
        provider_messages: Dict of per-provider system messages for SOAP settings
    """
    # Initialize provider_messages if not provided
    if provider_messages is None:
        provider_messages = {}
    # Create dialog
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog_width, dialog_height = ui_scaler.get_dialog_size(950, 700)
    dialog.geometry(f"{dialog_width}x{dialog_height}")
    dialog.transient(parent)

    # Center the dialog on the screen
    dialog.update_idletasks()
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    x = (screen_width // 2) - (dialog_width // 2)
    y = (screen_height // 2) - (dialog_height // 2)
    dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

    # Grab focus after window is visible
    dialog.deiconify()
    try:
        dialog.grab_set()
    except tk.TclError:
        pass  # Window not viewable yet

    # Add provider selector for Advanced Analysis settings
    provider_var = tk.StringVar(value=current_provider if current_provider else "")
    if is_advanced_analysis:
        provider_frame = ttk.Labelframe(dialog, text="AI Provider", padding=10)
        provider_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Label(provider_frame, text="Provider for Advanced Analysis:").grid(row=0, column=0, sticky="w", padx=(0, 10))

        provider_options = [
            ("", "Use Global Setting"),
            ("openai", "OpenAI"),
            ("anthropic", "Anthropic"),
            ("ollama", "Ollama"),
            ("gemini", "Gemini")
        ]

        # Create combobox with display names
        provider_display_names = [name for _, name in provider_options]
        provider_combo = ttk.Combobox(provider_frame, values=provider_display_names, state="readonly", width=25)
        provider_combo.grid(row=0, column=1, sticky="w", padx=(0, 10))

        # Set initial value based on current_provider
        provider_map = {value: name for value, name in provider_options}
        initial_display = provider_map.get(current_provider, "Use Global Setting")
        provider_combo.set(initial_display)

        # Reverse map for getting value from display name
        display_to_value = {name: value for value, name in provider_options}

        def on_provider_change(event=None):
            display_name = provider_combo.get()
            provider_var.set(display_to_value.get(display_name, ""))

        provider_combo.bind("<<ComboboxSelected>>", on_provider_change)

        # Set initial value in provider_var
        provider_var.set(current_provider if current_provider else "")

        ttk.Label(provider_frame,
                 text="Select a specific provider or use the global setting from the main app.",
                 foreground="gray").grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))

    # Create notebook for tabs
    notebook = ttk.Notebook(dialog)
    notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Create tabs
    prompts_tab = ttk.Frame(notebook)
    models_tab = ttk.Frame(notebook)
    temperature_tab = ttk.Frame(notebook)

    notebook.add(prompts_tab, text="Prompts")
    notebook.add(models_tab, text="Models")
    notebook.add(temperature_tab, text="Temperature")

    # Add Options tab for SOAP settings (ICD code version)
    icd_version_var = tk.StringVar(value=current_icd_version)
    if is_soap_settings:
        options_tab = ttk.Frame(notebook)
        notebook.add(options_tab, text="Options")

        # ICD Code Version selector
        icd_frame = ttk.Labelframe(options_tab, text="ICD Code Version", padding=15)
        icd_frame.pack(fill=tk.X, padx=20, pady=20)

        ttk.Label(icd_frame, text="Select which ICD code version to include in SOAP notes:",
                 wraplength=400).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 15))

        icd_options = [
            ("ICD-9", "ICD-9", "Use ICD-9 codes only (traditional format)"),
            ("ICD-10", "ICD-10", "Use ICD-10 codes only (newer standard)"),
            ("both", "Both ICD-9 and ICD-10", "Include both ICD-9 and ICD-10 codes")
        ]

        for i, (value, label, description) in enumerate(icd_options):
            rb = ttk.Radiobutton(icd_frame, text=label, value=value, variable=icd_version_var)
            rb.grid(row=i+1, column=0, sticky="w", pady=5)
            ttk.Label(icd_frame, text=description, foreground="gray").grid(
                row=i+1, column=1, sticky="w", padx=(20, 0), pady=5)

        # Temperature guidance note for SOAP
        temp_note_frame = ttk.Labelframe(options_tab, text="SOAP Note Quality Tips", padding=15)
        temp_note_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(temp_note_frame,
                 text="For consistent, accurate SOAP notes, a temperature of 0.3-0.5 is recommended.\n"
                      "Lower temperatures produce more focused, predictable output.\n"
                      "The default is now 0.4 for optimal clinical documentation.",
                 wraplength=500, justify="left").pack(anchor="w")

    # Populate tabs
    # For SOAP settings, use per-provider prompts tab; for others, use standard tab
    soap_provider_texts = None  # Will hold dict of provider -> text widget for SOAP
    if is_soap_settings:
        prompt_text, soap_provider_texts = _create_soap_prompts_tab(
            prompts_tab, current_prompt, provider_messages, current_icd_version
        )
        # Create a dummy system_prompt_text for compatibility (won't be used)
        system_prompt_text = None
    else:
        prompt_text, system_prompt_text = _create_prompt_tab(prompts_tab, current_prompt, current_system_prompt)

    model_vars = _create_models_tab(models_tab, current_model, current_ollama, current_anthropic, current_gemini)

    # Get temperature from config
    current_temp = config.get("temperature", default.get("temperature", 0.7))
    default_temp = default.get("temperature", 0.7)
    temp_scale, temp_value_var = _create_temperature_tab(temperature_tab, current_temp, default_temp)
    
    # Create button frame
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill=tk.X, padx=10, pady=10)
    # Define reset function
    def reset_fields():
        # Import default prompts directly from prompts.py
        from ai.prompts import REFINE_PROMPT, IMPROVE_PROMPT, SOAP_PROMPT_TEMPLATE, REFINE_SYSTEM_MESSAGE, IMPROVE_SYSTEM_MESSAGE, SOAP_SYSTEM_MESSAGE

        # Clear user prompt text area
        prompt_text.delete("1.0", tk.END)

        # Handle SOAP settings with per-provider prompts differently
        if is_soap_settings and soap_provider_texts:
            # Clear all per-provider system prompts (empty = use default)
            for provider, text_widget in soap_provider_texts.items():
                text_widget.delete("1.0", tk.END)
            # Reset user prompt to default
            prompt_text.insert("1.0", SOAP_PROMPT_TEMPLATE)
        else:
            # Standard behavior for non-SOAP dialogs
            if system_prompt_text:
                system_prompt_text.delete("1.0", tk.END)

            # Determine which default prompt to use based on the dialog title
            default_prompt = ""
            default_system = ""

            if "Refine Text" in title:
                default_prompt = REFINE_PROMPT
                default_system = REFINE_SYSTEM_MESSAGE
            elif "Improve Text" in title:
                default_prompt = IMPROVE_PROMPT
                default_system = IMPROVE_SYSTEM_MESSAGE
            elif "Referral" in title:
                # For referral, use defaults from the default dictionary
                default_prompt = default.get("prompt", "Write a referral paragraph using the SOAP Note given to you")
                default_system = default.get("system_message", "")
            elif "Advanced Analysis" in title:
                # For advanced analysis, use defaults from the default dictionary
                default_prompt = default.get("prompt", "")
                default_system = default.get("system_message", "")

            # Insert defaults
            prompt_text.insert("1.0", default_prompt)
            if system_prompt_text:
                system_prompt_text.insert("1.0", default_system)

        # Reset model fields to defaults
        model_vars['openai'].set(config.get("model", default.get("model", "gpt-3.5-turbo")))
        model_vars['ollama'].set(config.get("ollama_model", default.get("ollama_model", "llama3")))
        model_vars['anthropic'].set(config.get("anthropic_model", default.get("anthropic_model", "claude-sonnet-4-20250514")))
        model_vars['gemini'].set(config.get("gemini_model", default.get("gemini_model", "gemini-1.5-flash")))

        # Reset temperature
        temp_scale.set(default_temp)
        temp_value_var.set(f"{default_temp:.1f}")

        # Reset ICD version for SOAP settings
        if is_soap_settings:
            icd_version_var.set("ICD-9")

        # Reset provider for Advanced Analysis settings
        if is_advanced_analysis:
            provider_var.set("")
            provider_combo.set("Use Global Setting")

        # Set focus
        prompt_text.focus_set()
    
    # Define save function
    def save_fields():
        # Add temperature to config
        config["temperature"] = temp_scale.get()

        # Handle SOAP settings with per-provider prompts
        if is_soap_settings and soap_provider_texts:
            # Collect per-provider system messages
            provider_msgs = {}
            for provider, text_widget in soap_provider_texts.items():
                provider_msgs[f"{provider}_system_message"] = text_widget.get("1.0", tk.END).strip()

            # Build arguments for SOAP save callback (different signature)
            save_args = [
                prompt_text.get("1.0", tk.END).strip(),
                model_vars['openai'].get().strip(),
                model_vars['ollama'].get().strip(),
                model_vars['anthropic'].get().strip(),
                model_vars['gemini'].get().strip(),
                icd_version_var.get(),
                provider_msgs  # Dict of per-provider system messages
            ]
        else:
            # Standard save for non-SOAP dialogs
            save_args = [
                prompt_text.get("1.0", tk.END).strip(),
                model_vars['openai'].get().strip(),
                model_vars['ollama'].get().strip(),
                system_prompt_text.get("1.0", tk.END).strip() if system_prompt_text else "",
                model_vars['anthropic'].get().strip(),
                model_vars['gemini'].get().strip()
            ]

            # Add ICD version for SOAP settings (backward compat for non per-provider mode)
            if is_soap_settings:
                save_args.append(icd_version_var.get())

            # Add provider for Advanced Analysis settings
            if is_advanced_analysis:
                save_args.append(provider_var.get())

        save_callback(*save_args)
        dialog.destroy()
    
    # Create buttons
    reset_button = ttk.Button(btn_frame, text="Reset", command=reset_fields)
    reset_button.pack(side=tk.LEFT, padx=5)
    
    save_button = ttk.Button(btn_frame, text="Save", command=save_fields)
    save_button.pack(side=tk.RIGHT, padx=5)
    
    cancel_button = ttk.Button(btn_frame, text="Cancel", command=dialog.destroy)
    cancel_button.pack(side=tk.RIGHT, padx=5)


# ============================================================================
# API Keys Dialog
# ============================================================================

def show_api_keys_dialog(parent: tk.Tk) -> dict:
    """Shows a dialog to update API keys and updates the .env file.
    
    Returns:
        dict: Updated API keys or None if cancelled
    """
    dialog = create_toplevel_dialog(parent, "Update API Keys", "900x1100")
    result = {"keys": None}  # Store result in mutable object
    
    # Increase main frame padding for more spacing around all content
    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    
    # Add a header section with explanation
    header_frame = ttk.Frame(frame)
    header_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 30))
    
    ttk.Label(header_frame, text="API Key Configuration", 
             font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 15))

    # Get current API keys from secure storage first, then fall back to environment
    from utils.security import get_security_manager
    security_mgr = get_security_manager()

    openai_key = security_mgr.get_api_key("openai") or os.getenv("OPENAI_API_KEY", "")
    deepgram_key = security_mgr.get_api_key("deepgram") or os.getenv("DEEPGRAM_API_KEY", "")
    elevenlabs_key = security_mgr.get_api_key("elevenlabs") or os.getenv("ELEVENLABS_API_KEY", "")
    ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")  # Default Ollama URL
    groq_key = security_mgr.get_api_key("groq") or os.getenv("GROQ_API_KEY", "")
    anthropic_key = security_mgr.get_api_key("anthropic") or os.getenv("ANTHROPIC_API_KEY", "")
    gemini_key = security_mgr.get_api_key("gemini") or os.getenv("GEMINI_API_KEY", "")

    # Create entry fields with password masking - add more vertical spacing
    row_offset = 1  # Start at row 1 since header is at row 0

    ttk.Label(frame, text="OpenAI API Key:").grid(row=row_offset, column=0, sticky="w", pady=15)
    openai_entry = ttk.Entry(frame, width=50, show="•")
    openai_entry.grid(row=row_offset, column=1, sticky="ew", padx=(10, 5), pady=15)
    openai_entry.insert(0, openai_key)
    row_offset += 1

    ttk.Label(frame, text="Anthropic API Key:").grid(row=row_offset, column=0, sticky="w", pady=15)
    anthropic_entry = ttk.Entry(frame, width=50, show="•")
    anthropic_entry.grid(row=row_offset, column=1, sticky="ew", padx=(10, 5), pady=15)
    anthropic_entry.insert(0, anthropic_key)
    row_offset += 1

    ttk.Label(frame, text="Google Gemini API Key:").grid(row=row_offset, column=0, sticky="w", pady=15)
    gemini_entry = ttk.Entry(frame, width=50, show="•")
    gemini_entry.grid(row=row_offset, column=1, sticky="ew", padx=(10, 5), pady=15)
    gemini_entry.insert(0, gemini_key)
    row_offset += 1

    ttk.Label(frame, text="Ollama API URL:").grid(row=row_offset, column=0, sticky="w", pady=15)
    ollama_entry = ttk.Entry(frame, width=50)
    ollama_entry.grid(row=row_offset, column=1, sticky="ew", padx=(10, 5), pady=15)
    ollama_entry.insert(0, ollama_url)
    row_offset += 1
    
    # Add a "Test Connection" button for Ollama
    test_ollama_btn = ttk.Button(
        frame, 
        text="Test Ollama Connection", 
        command=lambda: test_ollama_connection(parent, ollama_entry.get())
    )
    test_ollama_btn.grid(row=row_offset, column=1, sticky="e", padx=(10, 5), pady=15)
    row_offset += 1
    
    # Add a separator and section title for STT APIs
    ttk.Separator(frame, orient="horizontal").grid(row=row_offset, column=0, columnspan=3, sticky="ew", pady=25)
    row_offset += 1
    
    stt_label = ttk.Label(frame, text="Speech-to-Text APIs (at least one required)", font=("Segoe UI", 12, "bold"))
    stt_label.grid(row=row_offset, column=0, columnspan=3, sticky="w", pady=(0, 15))
    row_offset += 1

    # Add Deepgram API Key field with special styling
    deepgram_label = ttk.Label(frame, text="Deepgram API Key:", bootstyle="warning")
    deepgram_label.grid(row=row_offset, column=0, sticky="w", pady=15)
    deepgram_entry = ttk.Entry(frame, width=50, show="•", bootstyle="warning")
    deepgram_entry.grid(row=row_offset, column=1, sticky="ew", padx=(10, 5), pady=15)
    deepgram_entry.insert(0, deepgram_key)
    row_offset += 1

    # Add ElevenLabs API Key field with special styling
    elevenlabs_label = ttk.Label(frame, text="ElevenLabs API Key:", bootstyle="warning")
    elevenlabs_label.grid(row=row_offset, column=0, sticky="w", pady=15)
    elevenlabs_entry = ttk.Entry(frame, width=50, show="•", bootstyle="warning")
    elevenlabs_entry.grid(row=row_offset, column=1, sticky="ew", padx=(10, 5), pady=15)
    elevenlabs_entry.insert(0, elevenlabs_key)
    row_offset += 1

    # Add GROQ API Key field
    groq_label = ttk.Label(frame, text="GROQ API Key:", bootstyle="danger")
    groq_label.grid(row=row_offset, column=0, sticky="w", pady=15)
    groq_entry = ttk.Entry(frame, width=50, show="•", bootstyle="danger")
    groq_entry.grid(row=row_offset, column=1, sticky="ew", padx=(10, 5), pady=15)
    groq_entry.insert(0, groq_key)
    row_offset += 1
    
    # Add toggle buttons to show/hide keys with dynamic row positioning
    def create_toggle_button(parent, entry, row, column=2, padx=5, pady=15):
        """Create a toggle button to show/hide password entries."""
        def toggle():
            current = entry['show']
            entry['show'] = '' if current else '•'
        
        return ttk.Button(parent, text="👁", width=3, command=toggle).grid(
            row=row, column=column, padx=padx, pady=pady
        )
    
    # Fixed eye button positions for LLM API keys
    create_toggle_button(frame, openai_entry, row=1)
    create_toggle_button(frame, anthropic_entry, row=2)
    create_toggle_button(frame, gemini_entry, row=3)
    # Ollama URL doesn't need a show/hide button as it's not a key

    # Calculate eye button positions for STT API keys based on deepgram's row
    deepgram_row = 8  # Based on the row_offset after separator and STT label
    create_toggle_button(frame, deepgram_entry, row=deepgram_row)
    create_toggle_button(frame, elevenlabs_entry, row=deepgram_row+1)
    create_toggle_button(frame, groq_entry, row=deepgram_row+2)

    # Error variable for validation messages
    error_var = tk.StringVar()
    error_label = ttk.Label(frame, textvariable=error_var, bootstyle="danger")
    error_label.grid(row=row_offset, column=0, columnspan=3, sticky="w", pady=15)
    row_offset += 1

    

    def update_api_keys():
        new_openai = openai_entry.get().strip()
        new_deepgram = deepgram_entry.get().strip()
        new_elevenlabs = elevenlabs_entry.get().strip()
        new_ollama_url = ollama_entry.get().strip()
        new_groq = groq_entry.get().strip()
        new_anthropic = anthropic_entry.get().strip()
        new_gemini = gemini_entry.get().strip()

        from utils.validation import validate_api_key

        # Validate API keys if provided
        validation_errors = []

        if new_openai:
            is_valid, error = validate_api_key("openai", new_openai)
            if not is_valid:
                validation_errors.append(f"OpenAI: {error}")

        if new_deepgram:
            is_valid, error = validate_api_key("deepgram", new_deepgram)
            if not is_valid:
                validation_errors.append(f"Deepgram: {error}")

        if new_elevenlabs:
            is_valid, error = validate_api_key("elevenlabs", new_elevenlabs)
            if not is_valid:
                validation_errors.append(f"ElevenLabs: {error}")

        if new_groq:
            is_valid, error = validate_api_key("groq", new_groq)
            if not is_valid:
                validation_errors.append(f"GROQ: {error}")

        if new_anthropic:
            is_valid, error = validate_api_key("anthropic", new_anthropic)
            if not is_valid:
                validation_errors.append(f"Anthropic: {error}")

        if new_gemini:
            is_valid, error = validate_api_key("gemini", new_gemini)
            if not is_valid:
                validation_errors.append(f"Gemini: {error}")

        if validation_errors:
            error_var.set("Validation errors:\n" + "\n".join(validation_errors))
            return

        # Check if at least one LLM provider is provided
        if not (new_openai or new_anthropic or new_gemini or new_ollama_url):
            error_var.set("Error: At least one LLM provider API key is required (OpenAI, Anthropic, Gemini, or Ollama).")
            return
            
        # Check if at least one STT provider (Groq, Deepgram, or ElevenLabs) is provided
        if not (new_groq or new_deepgram or new_elevenlabs):
            error_var.set("Error: At least one STT provider API key is required (Groq, Deepgram, or ElevenLabs).")
            return
            
        # Clear any error messages
        error_var.set("")

        # Update .env file
        try:
            # Use data_folder_manager to get the correct .env path
            from managers.data_folder_manager import data_folder_manager
            env_path = str(data_folder_manager.env_file_path)
            
            # Read existing content
            env_content = ""
            if os.path.exists(env_path):
                with open(env_path, "r") as f:
                    env_content = f.read()
            
            # Update or add each key
            env_lines = env_content.split("\n")
            updated_lines = []
            keys_updated = set()
            
            for line in env_lines:
                # Fix: Change startsWith to startswith (Python string method is lowercase)
                if line.strip() == "" or line.strip().startswith("#"):
                    updated_lines.append(line)
                    continue
                     
                if "OPENAI_API_KEY=" in line:
                    updated_lines.append(f"OPENAI_API_KEY={new_openai}")
                    keys_updated.add("OPENAI_API_KEY")
                elif "DEEPGRAM_API_KEY=" in line:
                    updated_lines.append(f"DEEPGRAM_API_KEY={new_deepgram}")
                    keys_updated.add("DEEPGRAM_API_KEY")
                elif "ELEVENLABS_API_KEY=" in line:
                    updated_lines.append(f"ELEVENLABS_API_KEY={new_elevenlabs}")
                    keys_updated.add("ELEVENLABS_API_KEY")
                elif "OLLAMA_API_URL=" in line:
                    updated_lines.append(f"OLLAMA_API_URL={new_ollama_url}")
                    keys_updated.add("OLLAMA_API_URL")
                elif "ANTHROPIC_API_KEY=" in line:
                    updated_lines.append(f"ANTHROPIC_API_KEY={new_anthropic}")
                    keys_updated.add("ANTHROPIC_API_KEY")
                elif "GEMINI_API_KEY=" in line:
                    updated_lines.append(f"GEMINI_API_KEY={new_gemini}")
                    keys_updated.add("GEMINI_API_KEY")
                else:
                    updated_lines.append(line)
            
            # Add keys that weren't in the file
            if "OPENAI_API_KEY" not in keys_updated and new_openai:
                updated_lines.append(f"OPENAI_API_KEY={new_openai}")
            if "DEEPGRAM_API_KEY" not in keys_updated and new_deepgram:
                updated_lines.append(f"DEEPGRAM_API_KEY={new_deepgram}")
            if "ELEVENLABS_API_KEY" not in keys_updated and new_elevenlabs:
                updated_lines.append(f"ELEVENLABS_API_KEY={new_elevenlabs}")
            if "OLLAMA_API_URL" not in keys_updated and new_ollama_url:
                updated_lines.append(f"OLLAMA_API_URL={new_ollama_url}")
            if "GROQ_API_KEY" not in keys_updated and new_groq:
                updated_lines.append(f"GROQ_API_KEY={new_groq}")
            if "ANTHROPIC_API_KEY" not in keys_updated and new_anthropic:
                updated_lines.append(f"ANTHROPIC_API_KEY={new_anthropic}")
            if "GEMINI_API_KEY" not in keys_updated and new_gemini:
                updated_lines.append(f"GEMINI_API_KEY={new_gemini}")

            # Make sure we have the RECOGNITION_LANGUAGE line
            if not any("RECOGNITION_LANGUAGE=" in line for line in updated_lines):
                updated_lines.append("RECOGNITION_LANGUAGE=en-US")
            
            # Write back to file
            with open(env_path, "w") as f:
                f.write("\n".join(updated_lines))

            # Store keys securely using encryption
            from utils.security import get_security_manager
            security_mgr = get_security_manager()

            # Store each key securely (this is the primary storage method)
            keys_to_store = {
                'openai': new_openai,
                'deepgram': new_deepgram,
                'elevenlabs': new_elevenlabs,
                'groq': new_groq,
                'anthropic': new_anthropic,
                'gemini': new_gemini,
            }

            for provider, key in keys_to_store.items():
                if key:
                    success, error = security_mgr.store_api_key(provider, key)
                    if not success:
                        logging.warning(f"Failed to store {provider} key securely: {error}")

            # Update environment variables in memory
            if new_openai:
                os.environ["OPENAI_API_KEY"] = new_openai
                # Note: Modern OpenAI provider uses client pattern that reads from env/security manager
            if new_deepgram:
                os.environ["DEEPGRAM_API_KEY"] = new_deepgram
            if new_elevenlabs:
                os.environ["ELEVENLABS_API_KEY"] = new_elevenlabs
            if new_ollama_url:
                os.environ["OLLAMA_API_URL"] = new_ollama_url
            if new_groq:
                os.environ["GROQ_API_KEY"] = new_groq
            if new_anthropic:
                os.environ["ANTHROPIC_API_KEY"] = new_anthropic
            if new_gemini:
                os.environ["GEMINI_API_KEY"] = new_gemini

            # Store results before showing message
            result["keys"] = {
                "openai": new_openai,
                "deepgram": new_deepgram,
                "elevenlabs": new_elevenlabs,
                "ollama_url": new_ollama_url,
                "groq": new_groq,
                "anthropic": new_anthropic,
                "gemini": new_gemini
            }
            
            # Success message and close dialog
            messagebox.showinfo("API Keys", "API keys updated successfully")
            dialog.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update API keys: {str(e)}")
            return None

    # Add more padding to the button frame
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(pady=30, padx=20)
    ttk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=15).pack(side="left", padx=20)
    ttk.Button(btn_frame, text="Update Keys", command=update_api_keys, bootstyle="success", width=15).pack(side="left", padx=20)
    
    # Wait for dialog to close
    dialog.wait_window()
    
    # Return the result
    return result.get("keys")

def show_shortcuts_dialog(parent: tk.Tk) -> None:
    """Show keyboard shortcuts dialog."""
    dialog = tk.Toplevel(parent)
    dialog.title("Keyboard Shortcuts")
    dialog.transient(parent)
    dialog.resizable(True, True)  # Allow resizing
    dialog.minsize(700, 400)  # Set minimum size
    
    # Set initial size and position BEFORE creating content
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    dialog_width = 900
    dialog_height = 600  # Increased height even more
    
    # Calculate center position
    x = (screen_width // 2) - (dialog_width // 2)
    y = (screen_height // 2) - (dialog_height // 2)
    
    # Ensure dialog is not positioned off screen
    x = max(50, min(x, screen_width - dialog_width - 50))
    y = max(50, min(y, screen_height - dialog_height - 50))
    
    dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
    
    # Configure dialog to be on top initially
    dialog.attributes('-topmost', True)
    dialog.focus_force()
    
    # Allow window manager to handle the dialog properly
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    
    # Create frame for keyboard shortcuts
    kb_frame = ttk.Frame(dialog)
    kb_frame.pack(expand=True, fill="both", padx=10, pady=(10, 5))
    
    # Create treeview with scrollbar
    tree_frame = ttk.Frame(kb_frame)
    tree_frame.pack(expand=True, fill="both")
    
    kb_tree = ttk.Treeview(tree_frame, columns=("Command", "Description"), show="headings", height=20)
    kb_tree.heading("Command", text="Command")
    kb_tree.heading("Description", text="Description")
    kb_tree.column("Command", width=200, anchor="w")
    kb_tree.column("Description", width=650, anchor="w")
    
    # Add scrollbar
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=kb_tree.yview)
    kb_tree.configure(yscrollcommand=scrollbar.set)
    
    # Pack treeview and scrollbar
    kb_tree.pack(side="left", expand=True, fill="both")
    scrollbar.pack(side="right", fill="y")
    
    # Organized shortcuts by category
    shortcuts_categories = [
        ("File Operations", [
            ("Ctrl+N", "New session"),
            ("Ctrl+S", "Save text and audio"),
            ("Ctrl+L", "Load audio file"),
            ("Ctrl+C", "Copy text to clipboard")
        ]),
        ("Text Editing", [
            ("Ctrl+Z", "Undo text changes"),
            ("Ctrl+Y", "Redo text changes")
        ]),
        ("Recording Controls", [
            ("F5", "Start/Stop recording"),
            ("Ctrl+Shift+S", "Start/Stop recording"),
            ("Space", "Pause/Resume recording (when recording)"),
            ("Esc", "Cancel recording")
        ]),
        ("Chat & Interface", [
            ("Ctrl+/", "Focus chat input"),
            ("Alt+T", "Toggle theme (Light/Dark)"),
            ("Ctrl+,", "Open Preferences"),
            ("F1", "Show this help dialog")
        ]),
        ("AI Analysis", [
            ("Ctrl+D", "Run diagnostic analysis"),
        ]),
        ("Export", [
            ("Ctrl+E", "Export to PDF"),
            ("Ctrl+Shift+W", "Export to Word"),
            ("Ctrl+Shift+F", "Export to FHIR"),
            ("Ctrl+P", "Print document")
        ])
    ]
    
    # Add shortcuts with categories
    for category, shortcuts in shortcuts_categories:
        # Add category header
        kb_tree.insert("", tk.END, values=(f"━━ {category} ━━", ""), tags=("category",))
        
        # Add shortcuts in category
        for cmd, desc in shortcuts:
            kb_tree.insert("", tk.END, values=(cmd, desc))
        
        # Add empty line for spacing
        kb_tree.insert("", tk.END, values=("", ""))
    
    # Configure category styling (theme-aware)
    try:
        # Try to detect if parent is using a dark theme
        if hasattr(parent, 'current_theme'):
            is_dark = parent.current_theme in ["darkly", "solar", "cyborg", "superhero"]
            category_color = "#6ea8fe" if is_dark else "#0d6efd"
        else:
            category_color = "#0d6efd"
        kb_tree.tag_configure("category", foreground=category_color, font=("Arial", 10, "bold"))
    except (tk.TclError, AttributeError):
        # Fallback to default blue color
        kb_tree.tag_configure("category", foreground="#0d6efd", font=("Arial", 10, "bold"))
    
    # Button frame at bottom
    button_frame = ttk.Frame(dialog)
    button_frame.pack(fill="x", padx=10, pady=10)
    
    ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side="right")
    
    # Update and focus on the dialog
    dialog.update_idletasks()
    dialog.focus_set()

    # Set modal behavior after dialog is fully created
    dialog.deiconify()
    try:
        dialog.grab_set()
    except tk.TclError:
        pass  # Window not viewable yet

    # Bring dialog to front and then allow normal window behavior
    dialog.lift()
    dialog.after(500, lambda: dialog.attributes('-topmost', False))  # Remove topmost after the dialog is established

def show_about_dialog(parent: tk.Tk) -> None:
    """Show about dialog with app information."""
    import platform
    import sys
    from datetime import datetime
    import webbrowser
    
    # Create custom dialog window
    dialog = create_toplevel_dialog(parent, "About Medical Assistant", "600x780")
    dialog.resizable(False, False)
    
    # Get current theme
    is_dark = hasattr(parent, 'current_theme') and parent.current_theme in ["darkly", "solar", "cyborg", "superhero"]
    
    # Main container with scrollable support
    main_frame = ttk.Frame(dialog, padding=15)
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Header section with app icon and title
    header_frame = ttk.Frame(main_frame)
    header_frame.pack(fill=tk.X, pady=(0, 20))
    
    # App icon - load from file
    try:
        # Try to load the icon file
        import os
        from PIL import Image, ImageTk
        
        # Get the icon path
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon128x128.ico")
        
        if os.path.exists(icon_path):
            # Load and resize icon
            icon_image = Image.open(icon_path)
            icon_image = icon_image.resize((80, 80), Image.Resampling.LANCZOS)
            icon_photo = ImageTk.PhotoImage(icon_image)
            
            icon_label = ttk.Label(header_frame, image=icon_photo)
            icon_label.image = icon_photo  # Keep a reference to prevent garbage collection
            icon_label.pack()
        else:
            # Fallback to emoji if icon not found
            icon_label = ttk.Label(header_frame, text="🏥", font=("Segoe UI", 48))
            icon_label.pack()
    except Exception as e:
        # Fallback to emoji if any error occurs
        icon_label = ttk.Label(header_frame, text="🏥", font=("Segoe UI", 48))
        icon_label.pack()
    
    # App title
    title_label = ttk.Label(header_frame, text="Medical Assistant", 
                           font=("Segoe UI", 24, "bold"))
    title_label.pack(pady=(10, 5))
    
    # Version info
    version_label = ttk.Label(header_frame, text="Version 2.0.0", 
                             font=("Segoe UI", 12))
    version_label.pack()
    
    # Separator
    ttk.Separator(main_frame, orient="horizontal").pack(fill=tk.X, pady=20)
    
    # Description section
    desc_frame = ttk.Frame(main_frame)
    desc_frame.pack(fill=tk.X, pady=(0, 20))
    
    description = """A powerful medical dictation and documentation assistant that helps healthcare professionals create accurate medical records efficiently.

Features advanced speech-to-text, AI-powered text processing, and SOAP note generation."""
    
    desc_label = ttk.Label(desc_frame, text=description, 
                          wraplength=550, justify=tk.CENTER,
                          font=("Segoe UI", 10))
    desc_label.pack()
    
    # Info section
    info_frame = ttk.Labelframe(main_frame, text="System Information", padding=15)
    info_frame.pack(fill=tk.X, pady=(0, 20))
    
    # System details
    info_items = [
        ("Platform", platform.system()),
        ("Python Version", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"),
        ("Architecture", platform.machine()),
        ("Build Date", datetime.now().strftime("%B %Y"))
    ]
    
    for label, value in info_items:
        row_frame = ttk.Frame(info_frame)
        row_frame.pack(fill=tk.X, pady=2)
        ttk.Label(row_frame, text=f"{label}:", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        ttk.Label(row_frame, text=value, font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(10, 0))
    
    # Credits section
    credits_frame = ttk.Labelframe(main_frame, text="Credits", padding=10)
    credits_frame.pack(fill=tk.X, pady=(0, 15))
    
    credits_text = """Developed with ❤️ by:
• Original Developer: Andre Hugo
• Enhanced by: Claude (Anthropic AI Assistant)

Technologies: Python, Tkinter/ttkbootstrap, OpenAI GPT, 
ElevenLabs, Deepgram, Groq APIs"""
    
    credits_label = ttk.Label(credits_frame, text=credits_text, 
                             font=("Segoe UI", 9), justify=tk.LEFT,
                             wraplength=550)
    credits_label.pack(anchor="w", fill=tk.X)
    
    # Links section
    links_frame = ttk.Frame(main_frame)
    links_frame.pack(fill=tk.X)
    
    def open_link(url):
        webbrowser.open(url)
    
    # Support link (styled as a button)
    support_btn = ttk.Button(links_frame, text="💬 Get Support", 
                           command=lambda: messagebox.showinfo("Support", "For support, please contact:\nsupport@medical-assistant.app"),
                           bootstyle="link")
    support_btn.pack(side=tk.LEFT, padx=(0, 10))
    
    # License link
    license_btn = ttk.Button(links_frame, text="📜 License", 
                         command=lambda: messagebox.showinfo("License", "This software is licensed under the MIT License.\n\nYou are free to use, modify, and distribute\nthis software in accordance with the license terms."),
                         bootstyle="link")
    license_btn.pack(side=tk.LEFT)
    
    # Footer
    ttk.Separator(main_frame, orient="horizontal").pack(fill=tk.X, pady=(20, 10))
    
    # Dynamic copyright year
    current_year = datetime.now().year
    footer_label = ttk.Label(main_frame, text=f"© {current_year} Medical Assistant. All rights reserved.",
                            font=("Segoe UI", 8), foreground="gray")
    footer_label.pack()
    
    # Close button
    close_btn = ttk.Button(main_frame, text="Close", command=dialog.destroy,
                          bootstyle="primary")
    close_btn.pack(pady=(10, 0))
    
    # Center the dialog
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
    y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
    dialog.geometry(f"+{x}+{y}")
    
    # Add fade-in animation
    dialog.attributes('-alpha', 0.0)
    dialog.update()
    
    def fade_in(alpha=0.0):
        if alpha < 1.0:
            alpha += 0.1
            dialog.attributes('-alpha', alpha)
            dialog.after(20, lambda: fade_in(alpha))
    
    fade_in()

    # Make dialog modal
    dialog.transient(parent)
    dialog.deiconify()
    try:
        dialog.grab_set()
    except tk.TclError:
        pass  # Window not viewable yet

    # Bind ESC key to close dialog
    dialog.bind('<Escape>', lambda e: dialog.destroy())
    
    # Focus on close button
    close_btn.focus_set()
    
    parent.wait_window(dialog)

def show_letter_options_dialog(parent: tk.Tk) -> tuple:
    """Show dialog to get letter source, recipient type, and specifications from user.

    Returns:
        tuple: (source, recipient_type, specifications) where source is 'transcript' or 'soap'
    """
    dialog = create_toplevel_dialog(parent, "Letter Options", "700x750")

    # Add a main frame with padding for better spacing
    main_frame = ttk.Frame(dialog, padding=(20, 20, 20, 20))
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Source selection
    ttk.Label(main_frame, text="Select text source for the letter:", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 10))

    source_frame = ttk.Frame(main_frame)
    source_frame.pack(fill="x", pady=(0, 15), anchor="w")

    source_var = tk.StringVar(value="transcript")
    ttk.Radiobutton(source_frame, text="Use text from Transcript tab", variable=source_var, value="transcript").pack(anchor="w", padx=20, pady=5)
    ttk.Radiobutton(source_frame, text="Use text from SOAP tab", variable=source_var, value="soap").pack(anchor="w", padx=20, pady=5)

    # Recipient type selection (NEW)
    ttk.Label(main_frame, text="Letter recipient type:", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(10, 5))
    ttk.Label(main_frame, text="Select the type of recipient to focus the letter content appropriately",
              wraplength=650, font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 10))

    recipient_frame = ttk.Frame(main_frame)
    recipient_frame.pack(fill="x", pady=(0, 15), anchor="w")

    # Recipient type options
    recipient_types = [
        ("Insurance Company", "insurance"),
        ("Employer / Workplace", "employer"),
        ("Specialist / Colleague", "specialist"),
        ("Patient", "patient"),
        ("School / Educational Institution", "school"),
        ("Legal / Attorney", "legal"),
        ("Government Agency (Disability, etc.)", "government"),
        ("Other (specify in instructions below)", "other")
    ]

    recipient_var = tk.StringVar(value="insurance")
    for label, value in recipient_types:
        ttk.Radiobutton(recipient_frame, text=label, variable=recipient_var, value=value).pack(anchor="w", padx=20, pady=2)

    # Additional specifications
    ttk.Label(main_frame, text="Additional instructions (optional):", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(10, 5))
    ttk.Label(main_frame, text="Enter any specific requirements (purpose, specific conditions to focus on, tone, etc.)",
              wraplength=650, font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 10))

    specs_text = scrolledtext.ScrolledText(main_frame, height=6, width=80, font=("Segoe UI", 10))
    specs_text.pack(fill="both", expand=True, pady=(0, 20))

    # Add placeholder text
    placeholder_text = "Examples:\n- Focus only on back injury for workers comp claim\n- Request prior authorization for MRI\n- Fitness to return to work assessment\n- Medical clearance for surgery"
    specs_text.insert("1.0", placeholder_text)
    specs_text.tag_add("gray", "1.0", "end")
    specs_text.tag_config("gray", foreground="gray")

    def clear_placeholder(_):
        if specs_text.get("1.0", "end-1c").strip() == placeholder_text.strip():
            specs_text.delete("1.0", "end")
            specs_text.tag_remove("gray", "1.0", "end")
        specs_text.unbind("<FocusIn>")

    specs_text.bind("<FocusIn>", clear_placeholder)

    result = [None, None, None]

    def on_submit():
        result[0] = source_var.get()
        result[1] = recipient_var.get()
        result[2] = specs_text.get("1.0", "end-1c")
        # If user didn't change placeholder text, provide empty specs
        if result[2].strip() == placeholder_text.strip():
            result[2] = ""
        dialog.destroy()

    def on_cancel():
        dialog.destroy()

    # Button layout
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill="x", padx=20, pady=(0, 20))

    ttk.Button(btn_frame, text="Cancel", command=on_cancel, width=15).pack(side="left", padx=10, pady=10)
    ttk.Button(btn_frame, text="Generate Letter", command=on_submit, bootstyle="success", width=15).pack(side="right", padx=10, pady=10)

    # Center the dialog on the screen
    dialog.update_idletasks()
    dialog.geometry("+{}+{}".format(
        (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2),
        (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
    ))

    dialog.wait_window()
    return result[0], result[1], result[2]


def show_letterhead_dialog(parent: tk.Tk, clinic_name: str = "", doctor_name: str = "") -> tuple:
    """Show dialog to get letterhead information (clinic name and doctor name).

    Args:
        parent: Parent window
        clinic_name: Pre-filled clinic name
        doctor_name: Pre-filled doctor name

    Returns:
        tuple: (clinic_name, doctor_name) or None if cancelled
    """
    dialog = create_toplevel_dialog(parent, "Letterhead Information", "450x280")

    # Main frame
    main_frame = ttk.Frame(dialog, padding=(20, 20, 20, 20))
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Heading
    ttk.Label(
        main_frame,
        text="Enter letterhead information:",
        font=("Segoe UI", 11, "bold")
    ).pack(anchor="w", pady=(0, 15))

    ttk.Label(
        main_frame,
        text="This information will appear at the top of your PDF documents.",
        font=("Segoe UI", 10),
        wraplength=400
    ).pack(anchor="w", pady=(0, 15))

    # Clinic name
    clinic_frame = ttk.Frame(main_frame)
    clinic_frame.pack(fill="x", pady=5)
    ttk.Label(clinic_frame, text="Clinic Name:", width=12).pack(side="left")
    clinic_var = tk.StringVar(value=clinic_name)
    clinic_entry = ttk.Entry(clinic_frame, textvariable=clinic_var, width=40)
    clinic_entry.pack(side="left", padx=(10, 0), fill="x", expand=True)

    # Doctor name
    doctor_frame = ttk.Frame(main_frame)
    doctor_frame.pack(fill="x", pady=5)
    ttk.Label(doctor_frame, text="Doctor Name:", width=12).pack(side="left")
    doctor_var = tk.StringVar(value=doctor_name)
    doctor_entry = ttk.Entry(doctor_frame, textvariable=doctor_var, width=40)
    doctor_entry.pack(side="left", padx=(10, 0), fill="x", expand=True)

    # Save checkbox
    save_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(
        main_frame,
        text="Save for future use",
        variable=save_var
    ).pack(anchor="w", pady=(15, 0))

    result = [None]

    def on_submit():
        clinic = clinic_var.get().strip()
        doctor = doctor_var.get().strip()

        if not clinic and not doctor:
            messagebox.showwarning("Input Required", "Please enter at least a clinic name or doctor name.")
            return

        # Save to settings if requested
        if save_var.get():
            try:
                from settings.settings_manager import SETTINGS, save_settings
                SETTINGS["clinic_name"] = clinic
                SETTINGS["doctor_name"] = doctor
                save_settings()
            except Exception as e:
                logging.warning(f"Could not save letterhead settings: {e}")

        result[0] = (clinic, doctor)
        dialog.destroy()

    def on_cancel():
        dialog.destroy()

    # Buttons
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill="x", padx=20, pady=(0, 20))

    ttk.Button(btn_frame, text="Cancel", command=on_cancel, width=12).pack(side="left", padx=5)
    ttk.Button(btn_frame, text="Continue", command=on_submit, bootstyle="success", width=12).pack(side="right", padx=5)

    # Focus on first empty field
    if not clinic_name:
        clinic_entry.focus_set()
    elif not doctor_name:
        doctor_entry.focus_set()
    else:
        clinic_entry.focus_set()

    # Center dialog
    dialog.update_idletasks()
    dialog.geometry("+{}+{}".format(
        (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2),
        (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
    ))

    dialog.wait_window()
    return result[0]
