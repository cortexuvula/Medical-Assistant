"""
Settings Dialogs Module

Functions for creating and showing settings dialogs with prompt and model configuration.
"""

import tkinter as tk
from tkinter import scrolledtext
import ttkbootstrap as ttk
from typing import Dict, Tuple
from ui.scaling_utils import ui_scaler

from ui.dialogs.dialog_utils import create_model_selector
from ui.dialogs.model_providers import (
    get_openai_models,
    get_ollama_models,
    get_anthropic_models,
    get_gemini_models,
)


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


__all__ = [
    "_create_prompt_tab",
    "_create_soap_prompts_tab",
    "_create_models_tab",
    "_create_temperature_tab",
    "show_settings_dialog",
]
