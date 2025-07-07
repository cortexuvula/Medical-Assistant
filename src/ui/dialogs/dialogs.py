import os
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

# Cache for model lists with TTL
_model_cache = {}
_cache_ttl = 3600  # 1 hour cache TTL

def clear_model_cache(provider: str = None):
    """Clear the model cache for a specific provider or all providers.
    
    Args:
        provider: Specific provider to clear cache for, or None to clear all
    """
    global _model_cache
    if provider:
        cache_key = f"{provider}_models"
        if cache_key in _model_cache:
            del _model_cache[cache_key]
            logging.info(f"Cleared model cache for {provider}")
    else:
        _model_cache.clear()
        logging.info("Cleared all model caches")

def create_model_selector(parent, frame, model_var, provider_name, get_models_func, row, column=1):
    """Create a model selection widget with a select button.
    
    Args:
        parent: Parent window
        frame: Frame to place the widget in
        model_var: tkinter variable to store selected model
        provider_name: Name of the provider (e.g., "OpenAI", "Perplexity")
        get_models_func: Function to call to get available models
        row: Grid row position
        column: Grid column position
    
    Returns:
        The frame containing the entry and button
    """
    # Create container frame
    container_frame = ttk.Frame(frame)
    container_frame.grid(row=row, column=column, sticky="ew", padx=(10, 0))
    
    # Create entry field
    entry = ttk.Entry(container_frame, textvariable=model_var)
    entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
    
    def select_model():
        # Create progress dialog
        progress_dialog = create_toplevel_dialog(parent, "Fetching Models", "300x100")
        progress_frame = ttk.Frame(progress_dialog, padding=20)
        progress_frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(progress_frame, text=f"Fetching {provider_name} models...").pack(pady=(0, 10))
        progress = ttk.Progressbar(progress_frame, mode="indeterminate")
        progress.pack(fill=tk.X)
        progress.start()
        progress_dialog.update()
        
        # Fetch models
        models = get_models_func()
        
        # Close progress dialog
        progress_dialog.destroy()
        
        if not models:
            messagebox.showerror("Error", 
                f"Failed to fetch {provider_name} models. Check your API key and internet connection.")
            return
        
        # Open model selection dialog with refresh capability
        model_selection = create_model_selection_dialog(parent, 
            f"Select {provider_name} Model", models, model_var.get(), 
            get_models_func=get_models_func, provider_name=provider_name)
        if model_selection:
            model_var.set(model_selection)
    
    # Add select button
    select_button = ttk.Button(container_frame, text="Select Model", command=select_model)
    select_button.pack(side=tk.RIGHT, padx=(5, 0))
    
    return container_frame

# Function to get OpenAI models
def get_openai_models() -> list:
    """Fetch available models from OpenAI API."""
    import openai
    try:
        # Create OpenAI client
        client = openai.OpenAI()
        
        # Make API call to list models
        response = client.models.list()
        
        # Extract GPT models from response
        models = []
        for model in response.data:
            if "gpt" in model.id.lower():
                models.append(model.id)
        
        # Add common models in case they're not in the API response
        common_models = [
            "gpt-3.5-turbo", 
            "gpt-3.5-turbo-16k", 
            "gpt-3.5-turbo-1106", 
            "gpt-3.5-turbo-0125",
            "gpt-4", 
            "gpt-4-turbo", 
            "gpt-4-turbo-preview",
            "gpt-4-0125-preview",
            "gpt-4-1106-preview", 
            "gpt-4-vision-preview",
            "gpt-4-32k"
        ]
        
        # Add any missing common models
        for model in common_models:
            if model not in models:
                models.append(model)
        
        # Return sorted list
        return sorted(models)
    except Exception as e:
        logging.error(f"Error fetching OpenAI models: {str(e)}")
        
        # Return fallback list of common models
        return [
            "gpt-3.5-turbo", 
            "gpt-3.5-turbo-16k", 
            "gpt-3.5-turbo-1106", 
            "gpt-3.5-turbo-0125",
            "gpt-4", 
            "gpt-4-turbo", 
            "gpt-4-turbo-preview",
            "gpt-4-0125-preview",
            "gpt-4-1106-preview", 
            "gpt-4-vision-preview",
            "gpt-4-32k"
        ]


def get_grok_models() -> list:
    """Fetch available models from Grok API."""
    try:
        
        # Get API key from environment
        api_key = os.getenv("GROK_API_KEY")
        if not api_key:
            logging.error("Grok API key not found in environment variables")
            return get_fallback_grok_models()
            
        # Make API call to get models using the OpenAI client with x.ai base URL
        try:
            # Initialize client with X.AI base URL
            client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
            
            # Make API call to get models
            response = client.models.list()
            
            # Extract model IDs
            models = []
            for model in response.data:
                if hasattr(model, 'id'):
                    models.append(model.id)
            
            # Add common models that might be missing
            common_models = ["grok-1", "grok-1.5", "grok-mini"]
            for model in common_models:
                if model not in models:
                    models.append(model)
                    
            return sorted(models)
        
        except Exception as api_error:
            # Fall back to direct request if OpenAI client approach fails
            logging.warning(f"OpenAI client approach failed, trying direct request: {str(api_error)}")
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                "https://api.x.ai/v1/models",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                # Extract model IDs - adjust according to actual response structure
                if "data" in data:
                    models = [model.get("id") for model in data.get("data", []) if model.get("id")]
                else:
                    models = [model.get("id") for model in data if model.get("id")]
                
                # Add common models that might be missing
                common_models = ["grok-1", "grok-1.5", "grok-mini"]
                for model in common_models:
                    if model not in models:
                        models.append(model)
                return sorted(models)
            else:
                logging.error(f"Error fetching Grok models: {response.status_code}")
                return get_fallback_grok_models()
    
    except Exception as e:
        logging.error(f"Error fetching Grok models: {str(e)}")
        return get_fallback_grok_models()

def get_fallback_grok_models() -> list:
    """Return fallback list of common Grok models."""
    return ["grok-1", "grok-1.5", "grok-mini"]

def get_ollama_models() -> list:
    """Fetch available models from Ollama API."""
    import requests
    
    try:
        # Make a request to the Ollama API to list models
        response = requests.get("http://localhost:11434/api/tags")
        
        if response.status_code == 200:
            # Parse the response as JSON
            data = response.json()
            
            # Extract model names from the response
            models = [model["name"] for model in data["models"]]
            
            # Sort models alphabetically
            models.sort()
            
            return models
        else:
            logging.error(f"Error fetching Ollama models: {response.status_code}")
            return []
    except Exception as e:
        logging.error(f"Error fetching Ollama models: {str(e)}")
        return []

def get_fallback_openai_models() -> list:
    """Return a list of common OpenAI models as fallback"""
    logging.info("Using fallback set of common OpenAI models")
    return ["gpt-4o", "gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"]

# Function to get Perplexity models
def get_perplexity_models() -> list:
    # For Perplexity, we'll use a curated list of models rather than trying to 
    # query them dynamically, since there's no direct API endpoint for listing models
    logging.info("Using curated list of Perplexity models")
    return [
        # Latest curated Perplexity models with context windows
        "sonar-reasoning-pro",    # 128k context
        "sonar-reasoning",        # 128k context
        "sonar-pro",              # 200k context
        "sonar",                  # 128k context
        "r1-1776"                # 128k context
        
    ]

def get_fallback_perplexity_models() -> list:
    """Return a list of Perplexity models"""
    logging.info("Using standard list of Perplexity models")
    return [
        "sonar-reasoning-pro",    # 128k context
        "sonar-reasoning",        # 128k context
        "sonar-pro",              # 200k context
        "sonar",                  # 128k context
        "r1-1776"                # 128k context
    ]

def get_anthropic_models() -> list:
    """Return a list of Anthropic models, fetched dynamically if possible"""
    # Check cache first
    cache_key = "anthropic_models"
    if cache_key in _model_cache:
        cached_time, cached_models = _model_cache[cache_key]
        if time.time() - cached_time < _cache_ttl:
            logging.info("Using cached Anthropic models")
            return cached_models
    
    try:
        # Try to fetch models dynamically from Anthropic API
        from anthropic import Anthropic
        from utils.security import get_security_manager
        
        security_manager = get_security_manager()
        api_key = security_manager.get_api_key("anthropic")
        
        if api_key:
            logging.info("Attempting to fetch Anthropic models from API")
            client = Anthropic(api_key=api_key)
            
            # Fetch models list from API
            models_response = client.models.list()
            
            # Extract model IDs from the response
            model_ids = []
            if hasattr(models_response, 'data'):
                for model in models_response.data:
                    if hasattr(model, 'id'):
                        model_ids.append(model.id)
            elif isinstance(models_response, list):
                model_ids = [model.id if hasattr(model, 'id') else str(model) for model in models_response]
            
            if model_ids:
                logging.info(f"Successfully fetched {len(model_ids)} Anthropic models from API")
                # Sort models with Claude 3 models first, then by version
                model_ids.sort(key=lambda x: (
                    0 if 'claude-3-opus' in x else
                    1 if 'claude-3-sonnet' in x else
                    2 if 'claude-3-haiku' in x else
                    3 if 'claude-2.1' in x else
                    4 if 'claude-2.0' in x else
                    5 if 'claude-instant' in x else
                    6
                ))
                # Cache the results
                _model_cache[cache_key] = (time.time(), model_ids)
                return model_ids
            else:
                logging.warning("No models found in API response, using fallback list")
                return get_fallback_anthropic_models()
        else:
            logging.info("No Anthropic API key available, using fallback list")
            return get_fallback_anthropic_models()
            
    except ImportError:
        logging.warning("Anthropic library not installed, using fallback list")
        return get_fallback_anthropic_models()
    except Exception as e:
        logging.error(f"Error fetching Anthropic models from API: {e}")
        return get_fallback_anthropic_models()

def get_fallback_anthropic_models() -> list:
    """Return a fallback list of Anthropic models"""
    logging.info("Using fallback list of Anthropic models")
    return [
        "claude-3-opus-20240229",      # Most capable model
        "claude-3-sonnet-20240229",    # Balanced performance
        "claude-3-haiku-20240307",     # Fastest model
        "claude-2.1",                  # Previous generation
        "claude-2.0",                  # Legacy model
        "claude-instant-1.2"           # Fast, lightweight model
    ]

def prompt_for_api_key(provider: str = "Grok") -> str:
    """Prompt the user for their API key."""
    dialog = tk.Toplevel()
    dialog.title(f"{provider} API Key Required")
    dialog.geometry("450x200")
    dialog.grab_set()
    
    env_var_name = {
        "Grok": "GROK_API_KEY",
        "OpenAI": "OPENAI_API_KEY",
        "Perplexity": "PERPLEXITY_API_KEY",
        "Anthropic": "ANTHROPIC_API_KEY"
    }.get(provider, "API_KEY")
    
    provider_url = {
        "Grok": "X.AI account",
        "OpenAI": "https://platform.openai.com/account/api-keys",
        "Perplexity": "https://www.perplexity.ai/settings/api",
        "Anthropic": "https://console.anthropic.com/account/keys"
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

def create_toplevel_dialog(parent: tk.Tk, title: str, geometry: str = "700x500") -> tk.Toplevel:
    """Create a top-level dialog with standard properties.
    
    Args:
        parent: Parent window
        title: Dialog title
        geometry: Window geometry string (width x height)
        
    Returns:
        The created top-level window
    """
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.geometry(geometry)
    dialog.transient(parent)
    dialog.grab_set()
    
    # Center the dialog on the screen
    dialog.update_idletasks()
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    size = tuple(map(int, geometry.split('x')))
    x = (screen_width // 2) - (size[0] // 2)
    y = (screen_height // 2) - (size[1] // 2)
    dialog.geometry(f"{size[0]}x{size[1]}+{x}+{y}")
    
    return dialog

def create_model_selection_dialog(parent, title, models_list, current_selection, get_models_func=None, provider_name=None):
    """
    Create a dialog with a scrollable listbox for selecting models.
    
    Args:
        parent: Parent window
        title: Dialog title
        models_list: List of models to display
        current_selection: Currently selected model
        get_models_func: Optional function to refresh models
        provider_name: Optional provider name for cache clearing
    
    Returns:
        Selected model or None if cancelled
    """
    dialog = create_toplevel_dialog(parent, title, "700x450")  # Increased size for better model selection
    
    # Create a frame for the dialog
    frame = ttk.Frame(dialog, padding=10)
    frame.pack(fill=tk.BOTH, expand=True)
    
    # Create header frame with label and refresh button
    header_frame = ttk.Frame(frame)
    header_frame.pack(fill=tk.X, pady=(0, 5))
    
    ttk.Label(header_frame, text="Select a model:").pack(side=tk.LEFT)
    
    # Add refresh button if get_models_func is provided
    if get_models_func:
        def refresh_models():
            # Clear cache if provider_name is provided
            if provider_name:
                clear_model_cache(provider_name.lower())
            
            # Show progress
            refresh_btn.config(state="disabled", text="Refreshing...")
            dialog.update()
            
            # Fetch new models
            new_models = get_models_func()
            
            # Update listbox
            listbox.delete(0, tk.END)
            for model in new_models:
                listbox.insert(tk.END, model)
                if model == current_selection:
                    listbox.selection_set(listbox.size() - 1)
                    listbox.see(listbox.size() - 1)
            
            # Update models_list reference
            models_list[:] = new_models
            
            # Re-enable button
            refresh_btn.config(state="normal", text="↻ Refresh")
            messagebox.showinfo("Refresh Complete", f"Fetched {len(new_models)} models")
        
        refresh_btn = ttk.Button(header_frame, text="↻ Refresh", command=refresh_models)
        refresh_btn.pack(side=tk.RIGHT, padx=(10, 0))
    
    # Create a frame for the listbox and scrollbar
    list_frame = ttk.Frame(frame)
    list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
    
    # Create scrollbar
    scrollbar = ttk.Scrollbar(list_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    # Create listbox
    listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, exportselection=0)
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    # Configure scrollbar
    scrollbar.config(command=listbox.yview)
    
    # Insert models into listbox
    for model in models_list:
        listbox.insert(tk.END, model)
        if model == current_selection:
            listbox.selection_set(listbox.size() - 1)
            listbox.see(listbox.size() - 1)
    
    # Create a frame for buttons
    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X, pady=(10, 0))
    
    # Variable to store the result
    result = [None]
    
    # Define OK function
    def ok_function():
        selection = listbox.curselection()
        if selection:
            result[0] = listbox.get(selection[0])
        dialog.destroy()
    
    # Define Cancel function
    def cancel_function():
        dialog.destroy()
    
    # Create OK and Cancel buttons
    ttk.Button(button_frame, text="OK", command=ok_function).pack(side=tk.RIGHT, padx=5)
    ttk.Button(button_frame, text="Cancel", command=cancel_function).pack(side=tk.RIGHT)
    
    # Make dialog modal
    dialog.transient(parent)
    dialog.grab_set()
    parent.wait_window(dialog)
    
    return result[0]

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

def _create_models_tab(parent: ttk.Frame, current_model: str, current_perplexity: str, 
                      current_grok: str, current_ollama: str, current_anthropic: str) -> Dict[str, tk.StringVar]:
    """Create the models tab content.
    
    Args:
        parent: Parent frame for the tab
        current_model: Current OpenAI model
        current_perplexity: Current Perplexity model
        current_grok: Current Grok model
        current_ollama: Current Ollama model
        current_anthropic: Current Anthropic model
        
    Returns:
        Dictionary of model StringVars
    """
    model_vars = {}
    
    # OpenAI Model
    ttk.Label(parent, text="OpenAI Model:").grid(row=0, column=0, sticky="nw", pady=(10, 5))
    openai_model_var = tk.StringVar(value=current_model)
    model_vars['openai'] = openai_model_var
    create_model_selector(parent, parent, openai_model_var, "OpenAI", get_openai_models, row=0)
    
    # Perplexity Model
    ttk.Label(parent, text="Perplexity Model:").grid(row=1, column=0, sticky="nw", pady=(5, 5))
    perplexity_model_var = tk.StringVar(value=current_perplexity)
    model_vars['perplexity'] = perplexity_model_var
    create_model_selector(parent, parent, perplexity_model_var, "Perplexity", get_perplexity_models, row=1)
    
    # Grok Model
    ttk.Label(parent, text="Grok Model:").grid(row=2, column=0, sticky="nw", pady=(5, 5))
    grok_model_var = tk.StringVar(value=current_grok)
    model_vars['grok'] = grok_model_var
    grok_entry = ttk.Entry(parent, textvariable=grok_model_var, width=50)
    grok_entry.grid(row=2, column=1, sticky="ew", padx=(10, 0), pady=(5, 5))
    
    # Ollama Model
    ttk.Label(parent, text="Ollama Model:").grid(row=3, column=0, sticky="nw", pady=(5, 5))
    ollama_model_var = tk.StringVar(value=current_ollama)
    model_vars['ollama'] = ollama_model_var
    create_model_selector(parent, parent, ollama_model_var, "Ollama", get_ollama_models, row=3)
    
    # Anthropic Model
    ttk.Label(parent, text="Anthropic Model:").grid(row=4, column=0, sticky="nw", pady=(5, 10))
    anthropic_model_var = tk.StringVar(value=current_anthropic)
    model_vars['anthropic'] = anthropic_model_var
    create_model_selector(parent, parent, anthropic_model_var, "Anthropic", get_anthropic_models, row=4)
    
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
                         current_prompt: str, current_model: str, current_perplexity: str, current_grok: str,
                         save_callback: callable, current_ollama: str = "", current_system_prompt: str = "", 
                         current_anthropic: str = "") -> None:
    """Show settings dialog for configuring prompt and model.
    
    Args:
        parent: Parent window
        title: Dialog title
        config: Current configuration
        default: Default configuration
        current_prompt: Current prompt text
        current_model: Current OpenAI model
        current_perplexity: Current Perplexity model
        current_grok: Current Grok model
        save_callback: Callback for saving settings
        current_ollama: Current Ollama model
        current_system_prompt: Current system prompt text
        current_anthropic: Current Anthropic model
    """
    # Create dialog
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.geometry("950x700")
    dialog.transient(parent)
    dialog.grab_set()
    
    # Center the dialog on the screen
    dialog.update_idletasks()
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    x = (screen_width // 2) - (950 // 2)
    y = (screen_height // 2) - (700 // 2)
    dialog.geometry(f"950x700+{x}+{y}")
    
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
    
    # Populate tabs
    prompt_text, system_prompt_text = _create_prompt_tab(prompts_tab, current_prompt, current_system_prompt)
    model_vars = _create_models_tab(models_tab, current_model, current_perplexity, current_grok, current_ollama, current_anthropic)
    
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
        
        # Clear text areas
        prompt_text.delete("1.0", tk.END)
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
        elif "SOAP Note" in title:
            default_prompt = SOAP_PROMPT_TEMPLATE
            default_system = SOAP_SYSTEM_MESSAGE
        elif "Referral" in title:
            # For referral, use defaults from the default dictionary
            default_prompt = default.get("prompt", "Write a referral paragraph using the SOAP Note given to you")
            default_system = default.get("system_message", "")
        
        # Insert defaults
        prompt_text.insert("1.0", default_prompt)
        system_prompt_text.insert("1.0", default_system)
        
        # Reset model fields to defaults
        model_vars['openai'].set(config.get("model", default.get("model", "gpt-3.5-turbo")))
        model_vars['perplexity'].set(config.get("perplexity_model", default.get("perplexity_model", "sonar-reasoning-pro")))
        model_vars['grok'].set(config.get("grok_model", default.get("grok_model", "grok-1")))
        model_vars['ollama'].set(config.get("ollama_model", default.get("ollama_model", "llama3")))
        model_vars['anthropic'].set(config.get("anthropic_model", default.get("anthropic_model", "claude-3-sonnet-20240229")))
        
        # Reset temperature
        temp_scale.set(default_temp)
        temp_value_var.set(f"{default_temp:.1f}")
        
        # Set focus
        prompt_text.focus_set()
    
    # Define save function
    def save_fields():
        # Add temperature to config
        config["temperature"] = temp_scale.get()
        
        save_callback(
            prompt_text.get("1.0", tk.END).strip(),
            model_vars['openai'].get().strip(),
            model_vars['perplexity'].get().strip(),
            model_vars['grok'].get().strip(),
            model_vars['ollama'].get().strip(),
            system_prompt_text.get("1.0", tk.END).strip(),
            model_vars['anthropic'].get().strip()
        )
        dialog.destroy()
    
    # Create buttons
    reset_button = ttk.Button(btn_frame, text="Reset", command=reset_fields)
    reset_button.pack(side=tk.LEFT, padx=5)
    
    save_button = ttk.Button(btn_frame, text="Save", command=save_fields)
    save_button.pack(side=tk.RIGHT, padx=5)
    
    cancel_button = ttk.Button(btn_frame, text="Cancel", command=dialog.destroy)
    cancel_button.pack(side=tk.RIGHT, padx=5)

def askstring_min(parent: tk.Tk, title: str, prompt: str, initialvalue: str = "") -> str:
    dialog = create_toplevel_dialog(parent, title, "400x300")
    tk.Label(dialog, text=prompt, wraplength=380).pack(padx=20, pady=20)
    entry = tk.Entry(dialog, width=50)
    entry.insert(0, initialvalue)
    entry.pack(padx=20)
    result = [None]
    def on_ok():
        result[0] = entry.get()
        dialog.destroy()
    btn_frame = tk.Frame(dialog)
    btn_frame.pack(pady=20)
    tk.Button(btn_frame, text="OK", command=on_ok).pack(side=tk.LEFT, padx=5)
    dialog.wait_window()
    return result[0]

def ask_conditions_dialog(parent: tk.Tk, title: str, prompt: str, conditions: list) -> str:
    dialog = create_toplevel_dialog(parent, title, "500x500")
    
    # Create a frame to hold all content
    main_frame = ttk.Frame(dialog, padding=10)
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    ttk.Label(main_frame, text=prompt, wraplength=450).pack(padx=20, pady=10)
    
    # Configure styles that work well in both light and dark modes
    style = ttk.Style()
    
    # Define a custom style for our checkbuttons that adapts to the theme
    style.configure("Conditions.TCheckbutton", font=("Segoe UI", 10))
    
    # Create a frame for checkboxes with a slight border for visual separation
    checkbox_frame = ttk.LabelFrame(main_frame, text="", padding=10)
    checkbox_frame.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)
    
    vars_list = []
    for cond in conditions:
        var = tk.BooleanVar()
        cb = ttk.Checkbutton(checkbox_frame, text=cond, variable=var, style="Conditions.TCheckbutton")
        cb.pack(anchor="w", pady=2)
        vars_list.append((cond, var))
    
    # Additional conditions section
    ttk.Label(main_frame, text="Additional conditions (optional):", wraplength=450).pack(padx=20, pady=(10,0))
    
    # Add a frame for the Text widget to visually separate it
    text_frame = ttk.Frame(main_frame, borderwidth=1, relief="solid")
    text_frame.pack(padx=20, pady=(5,10), fill="x")
    
    optional_text = tk.Text(text_frame, width=50, height=3, borderwidth=2)
    optional_text.pack(padx=2, pady=2, fill="x")
    
    selected = []
    def on_ok():
        for cond, var in vars_list:
            if var.get():
                selected.append(cond)
        extra = optional_text.get("1.0", tk.END).strip()
        if extra:
            selected.extend([item.strip() for item in extra.split(",") if item.strip()])
        dialog.destroy()
    
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(pady=10)
    
    ok_button = ttk.Button(btn_frame, text="OK", command=on_ok, width=10)
    ok_button.pack(side=tk.LEFT, padx=5)
    
    dialog.wait_window()
    return ", ".join(selected) if selected else ""

def show_api_keys_dialog(parent: tk.Tk) -> dict:
    """Shows a dialog to update API keys and updates the .env file.
    
    Returns:
        dict: Updated API keys or None if cancelled
    """
    dialog = create_toplevel_dialog(parent, "Update API Keys", "900x1000")
    result = {"keys": None}  # Store result in mutable object
    
    # Increase main frame padding for more spacing around all content
    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    
    # Add a header section with explanation
    header_frame = ttk.Frame(frame)
    header_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 30))
    
    ttk.Label(header_frame, text="API Key Configuration", 
             font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 15))

    # Get current API keys from environment
    openai_key = os.getenv("OPENAI_API_KEY", "")
    deepgram_key = os.getenv("DEEPGRAM_API_KEY", "")
    grok_key = os.getenv("GROK_API_KEY", "")
    perplexity_key = os.getenv("PERPLEXITY_API_KEY", "")
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY", "")  # NEW: Get ElevenLabs key
    ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")  # Default Ollama URL
    groq_key = os.getenv("GROQ_API_KEY", "")  # NEW: Get GROQ key
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")  # NEW: Get Anthropic key
    
    # Create entry fields with password masking - add more vertical spacing
    row_offset = 1  # Start at row 1 since header is at row 0
    
    ttk.Label(frame, text="OpenAI API Key:").grid(row=row_offset, column=0, sticky="w", pady=15)
    openai_entry = ttk.Entry(frame, width=50, show="•")
    openai_entry.grid(row=row_offset, column=1, sticky="ew", padx=(10, 5), pady=15)
    openai_entry.insert(0, openai_key)
    row_offset += 1

    ttk.Label(frame, text="Grok API Key:").grid(row=row_offset, column=0, sticky="w", pady=15)
    grok_entry = ttk.Entry(frame, width=50, show="•")
    grok_entry.grid(row=row_offset, column=1, sticky="ew", padx=(10, 5), pady=15)
    grok_entry.insert(0, grok_key)
    row_offset += 1

    ttk.Label(frame, text="Perplexity API Key:").grid(row=row_offset, column=0, sticky="w", pady=15)
    perplexity_entry = ttk.Entry(frame, width=50, show="•")
    perplexity_entry.grid(row=row_offset, column=1, sticky="ew", padx=(10, 5), pady=15)
    perplexity_entry.insert(0, perplexity_key)
    row_offset += 1
    
    ttk.Label(frame, text="Anthropic API Key:").grid(row=row_offset, column=0, sticky="w", pady=15)
    anthropic_entry = ttk.Entry(frame, width=50, show="•")
    anthropic_entry.grid(row=row_offset, column=1, sticky="ew", padx=(10, 5), pady=15)
    anthropic_entry.insert(0, anthropic_key)
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
    create_toggle_button(frame, grok_entry, row=2)
    create_toggle_button(frame, perplexity_entry, row=3)
    create_toggle_button(frame, anthropic_entry, row=4)
    # Ollama URL doesn't need a show/hide button as it's not a key
    
    # Calculate eye button positions for STT API keys based on deepgram's row
    deepgram_row = 9  # Based on the row_offset after separator and STT label (updated for Anthropic)
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
        new_grok = grok_entry.get().strip()
        new_perplexity = perplexity_entry.get().strip()
        new_elevenlabs = elevenlabs_entry.get().strip()  # NEW: Get ElevenLabs key
        new_ollama_url = ollama_entry.get().strip()  # Get Ollama URL
        new_groq = groq_entry.get().strip()  # NEW: Get GROQ key
        new_anthropic = anthropic_entry.get().strip()  # NEW: Get Anthropic key
        
        from utils.validation import validate_api_key
        
        # Validate API keys if provided
        validation_errors = []
        
        if new_openai:
            is_valid, error = validate_api_key("openai", new_openai)
            if not is_valid:
                validation_errors.append(f"OpenAI: {error}")
        
        if new_grok:
            is_valid, error = validate_api_key("grok", new_grok)
            if not is_valid:
                validation_errors.append(f"Grok: {error}")
        
        if new_perplexity:
            is_valid, error = validate_api_key("perplexity", new_perplexity)
            if not is_valid:
                validation_errors.append(f"Perplexity: {error}")
        
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
        
        if validation_errors:
            error_var.set("Validation errors:\n" + "\n".join(validation_errors))
            return
        
        # Check if at least one LLM provider (OpenAI, Grok, Perplexity, Anthropic, or Ollama) is provided
        if not (new_openai or new_grok or new_perplexity or new_anthropic or new_ollama_url):
            error_var.set("Error: At least one LLM provider API key is required (OpenAI, Grok, Perplexity, Anthropic, or Ollama).")
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
                elif "GROK_API_KEY=" in line:
                    updated_lines.append(f"GROK_API_KEY={new_grok}")
                    keys_updated.add("GROK_API_KEY")
                elif "PERPLEXITY_API_KEY=" in line:
                    updated_lines.append(f"PERPLEXITY_API_KEY={new_perplexity}")
                    keys_updated.add("PERPLEXITY_API_KEY")
                elif "ELEVENLABS_API_KEY=" in line:  # NEW: Update ElevenLabs key
                    updated_lines.append(f"ELEVENLABS_API_KEY={new_elevenlabs}")
                    keys_updated.add("ELEVENLABS_API_KEY")
                elif "OLLAMA_API_URL=" in line:
                    updated_lines.append(f"OLLAMA_API_URL={new_ollama_url}")
                    keys_updated.add("OLLAMA_API_URL")
                elif "ANTHROPIC_API_KEY=" in line:  # NEW: Update Anthropic key
                    updated_lines.append(f"ANTHROPIC_API_KEY={new_anthropic}")
                    keys_updated.add("ANTHROPIC_API_KEY")
                else:
                    updated_lines.append(line)
            
            # Add keys that weren't in the file
            if "OPENAI_API_KEY" not in keys_updated and new_openai:
                updated_lines.append(f"OPENAI_API_KEY={new_openai}")
            if "DEEPGRAM_API_KEY" not in keys_updated and new_deepgram:
                updated_lines.append(f"DEEPGRAM_API_KEY={new_deepgram}")
            if "GROK_API_KEY" not in keys_updated and new_grok:
                updated_lines.append(f"GROK_API_KEY={new_grok}")
            if "PERPLEXITY_API_KEY" not in keys_updated and new_perplexity:
                updated_lines.append(f"PERPLEXITY_API_KEY={new_perplexity}")
            if "ELEVENLABS_API_KEY" not in keys_updated and new_elevenlabs:
                updated_lines.append(f"ELEVENLABS_API_KEY={new_elevenlabs}")
            if "OLLAMA_API_URL" not in keys_updated and new_ollama_url:
                updated_lines.append(f"OLLAMA_API_URL={new_ollama_url}")
            if "GROQ_API_KEY" not in keys_updated and new_groq:
                updated_lines.append(f"GROQ_API_KEY={new_groq}")
            if "ANTHROPIC_API_KEY" not in keys_updated and new_anthropic:
                updated_lines.append(f"ANTHROPIC_API_KEY={new_anthropic}")
            
            # Make sure we have the RECOGNITION_LANGUAGE line
            if not any("RECOGNITION_LANGUAGE=" in line for line in updated_lines):
                updated_lines.append("RECOGNITION_LANGUAGE=en-US")
            
            # Write back to file
            with open(env_path, "w") as f:
                f.write("\n".join(updated_lines))
            
            # Update environment variables in memory
            if new_openai:
                os.environ["OPENAI_API_KEY"] = new_openai
                import openai
                openai.api_key = new_openai
            if new_deepgram:
                os.environ["DEEPGRAM_API_KEY"] = new_deepgram
            if new_grok:
                os.environ["GROK_API_KEY"] = new_grok
            if new_perplexity:
                os.environ["PERPLEXITY_API_KEY"] = new_perplexity
            if new_elevenlabs:
                os.environ["ELEVENLABS_API_KEY"] = new_elevenlabs
            if new_ollama_url:
                os.environ["OLLAMA_API_URL"] = new_ollama_url
            if new_groq:
                os.environ["GROQ_API_KEY"] = new_groq
            if new_anthropic:
                os.environ["ANTHROPIC_API_KEY"] = new_anthropic
            
            # Store results before showing message
            result["keys"] = {
                "openai": new_openai,
                "deepgram": new_deepgram,
                "grok": new_grok,
                "perplexity": new_perplexity,
                "elevenlabs": new_elevenlabs,
                "ollama_url": new_ollama_url,
                "groq": new_groq,
                "anthropic": new_anthropic
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
            ("F1", "Show this help dialog")
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
    except:
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
    dialog.grab_set()
    
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
    info_frame = ttk.LabelFrame(main_frame, text="System Information", padding=15)
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
    credits_frame = ttk.LabelFrame(main_frame, text="Credits", padding=10)
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
    dialog.grab_set()
    
    # Bind ESC key to close dialog
    dialog.bind('<Escape>', lambda e: dialog.destroy())
    
    # Focus on close button
    close_btn.focus_set()
    
    parent.wait_window(dialog)

def show_letter_options_dialog(parent: tk.Tk) -> tuple:
    """Show dialog to get letter source and specifications from user.
    
    Returns:
        tuple: (source, specifications) where source is 'transcript' or 'soap'
    """
    # Increase dialog size from 600x400 to 700x550 for better fit
    dialog = create_toplevel_dialog(parent, "Letter Options", "700x700")
    
    # Add a main frame with padding for better spacing
    main_frame = ttk.Frame(dialog, padding=(20, 20, 20, 20))
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    ttk.Label(main_frame, text="Select text source for the letter:", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 10))
    
    # Improve radio button section with a frame
    source_frame = ttk.Frame(main_frame)
    source_frame.pack(fill="x", pady=(0, 15), anchor="w")
    
    source_var = tk.StringVar(value="transcript")
    ttk.Radiobutton(source_frame, text="Use text from Transcript tab", variable=source_var, value="transcript").pack(anchor="w", padx=20, pady=5)
    ttk.Radiobutton(source_frame, text="Use text from SOAP tab", variable=source_var, value="soap").pack(anchor="w", padx=20, pady=5)
    
    ttk.Label(main_frame, text="Letter specifications:", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(10, 5))
    ttk.Label(main_frame, text="Enter any specific requirements for the letter (tone, style, formality, purpose, etc.)", 
            wraplength=650, font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 10))
    
    # Make the text area larger and ensure it fills available width
    specs_text = scrolledtext.ScrolledText(main_frame, height=8, width=80, font=("Segoe UI", 10))
    specs_text.pack(fill="both", expand=True, pady=(0, 20))
    
    # Add some example text to help users
    example_text = "Examples:\n- Formal letter to a specialist for patient referral\n- Patient instruction letter\n- Response to insurance company\n- Follow-up appointment instructions"
    specs_text.insert("1.0", example_text)
    specs_text.tag_add("gray", "1.0", "end")
    specs_text.tag_config("gray", foreground="gray")
    
    # Clear example text when user clicks in the field
    def clear_example(_):
        if specs_text.get("1.0", "end-1c").strip() == example_text.strip():
            specs_text.delete("1.0", "end")
            specs_text.tag_remove("gray", "1.0", "end")
        specs_text.unbind("<FocusIn>")  # Only clear once
    
    specs_text.bind("<FocusIn>", clear_example)
    
    result = [None, None]
    
    def on_submit():
        result[0] = source_var.get()
        result[1] = specs_text.get("1.0", "end-1c")
        # If user didn't change example text, provide empty specs
        if result[1].strip() == example_text.strip():
            result[1] = ""
        dialog.destroy()
    
    def on_cancel():
        dialog.destroy()
    
    # Improve button layout
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
    return result[0], result[1]

def show_elevenlabs_settings_dialog(parent: tk.Tk) -> None:
    """Show dialog to configure ElevenLabs speech-to-text settings."""
    from settings.settings import SETTINGS, _DEFAULT_SETTINGS, save_settings
    
    # Get current ElevenLabs settings with fallback to defaults
    elevenlabs_settings = SETTINGS.get("elevenlabs", {})
    default_settings = _DEFAULT_SETTINGS.get("elevenlabs", {})
    
    dialog = create_toplevel_dialog(parent, "ElevenLabs Settings", "700x800")
    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)
    
    # Create form with current settings
    ttk.Label(frame, text="ElevenLabs Speech-to-Text Settings", 
              font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky="w")
    
    # Model ID
    ttk.Label(frame, text="Model ID:").grid(row=1, column=0, sticky="w", pady=10)
    model_var = tk.StringVar(value=elevenlabs_settings.get("model_id", default_settings.get("model_id", "scribe_v1")))
    model_combo = ttk.Combobox(frame, textvariable=model_var, width=30)
    model_combo['values'] = ["scribe_v1", "scribe_v1_base"]  # Updated to supported models only
    model_combo.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="The AI model to use for transcription.", 
              wraplength=400, foreground="gray").grid(row=2, column=0, columnspan=2, sticky="w", padx=(20, 0))
    
    # Language Code
    ttk.Label(frame, text="Language Code:").grid(row=3, column=0, sticky="w", pady=10)
    lang_var = tk.StringVar(value=elevenlabs_settings.get("language_code", default_settings.get("language_code", "")))
    lang_entry = ttk.Entry(frame, textvariable=lang_var, width=30)
    lang_entry.grid(row=3, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Optional ISO language code (e.g., 'en-US'). Leave empty for auto-detection.", 
              wraplength=400, foreground="gray").grid(row=4, column=0, columnspan=2, sticky="w", padx=(20, 0))
    
    # Tag Audio Events
    ttk.Label(frame, text="Tag Audio Events:").grid(row=5, column=0, sticky="w", pady=10)
    tag_events_var = tk.BooleanVar(value=elevenlabs_settings.get("tag_audio_events", default_settings.get("tag_audio_events", True)))
    tag_events_check = ttk.Checkbutton(frame, variable=tag_events_var)
    tag_events_check.grid(row=5, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Add timestamps and labels for audio events like silence, music, etc.", 
              wraplength=400, foreground="gray").grid(row=6, column=0, columnspan=2, sticky="w", padx=(20, 0))
    
    # Number of Speakers
    ttk.Label(frame, text="Number of Speakers:").grid(row=7, column=0, sticky="w", pady=10)
    
    # Create a custom variable handler for the special "None" case
    speakers_value = elevenlabs_settings.get("num_speakers", default_settings.get("num_speakers", None))
    speakers_str = "" if speakers_value is None else str(speakers_value)
    speakers_entry = ttk.Entry(frame, width=30)
    speakers_entry.insert(0, speakers_str)
    speakers_entry.grid(row=7, column=1, sticky="w", padx=(10, 0), pady=10)
    
    ttk.Label(frame, text="Optional number of speakers. Leave empty for auto-detection.", 
              wraplength=400, foreground="gray").grid(row=8, column=0, columnspan=2, sticky="w", padx=(20, 0))
    
    # Timestamps Granularity
    ttk.Label(frame, text="Timestamps Granularity:").grid(row=9, column=0, sticky="w", pady=10)
    granularity_var = tk.StringVar(value=elevenlabs_settings.get("timestamps_granularity", default_settings.get("timestamps_granularity", "word")))
    granularity_combo = ttk.Combobox(frame, textvariable=granularity_var, width=30)
    granularity_combo['values'] = ["word", "segment", "sentence"]
    granularity_combo.grid(row=9, column=1, sticky="w", padx=(10, 0), pady=10)
    
    # Diarize
    ttk.Label(frame, text="Diarize:").grid(row=10, column=0, sticky="w", pady=10)
    diarize_var = tk.BooleanVar(value=elevenlabs_settings.get("diarize", default_settings.get("diarize", True)))
    diarize_check = ttk.Checkbutton(frame, variable=diarize_var)
    diarize_check.grid(row=10, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Identify different speakers in the audio.", 
              wraplength=400, foreground="gray").grid(row=11, column=0, columnspan=2, sticky="w", padx=(20, 0))
    
    # Create the buttons frame
    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=12, column=0, columnspan=2, pady=(20, 0), sticky="e")
    
    # Save handler - renamed to avoid conflict with imported save_settings
    def save_elevenlabs_settings():
        # Parse the number of speakers value (None or int)
        try:
            num_speakers = None if not speakers_entry.get().strip() else int(speakers_entry.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Number of speakers must be a valid integer or empty.")
            return
            
        # Build the new settings
        new_settings = {
            "model_id": model_var.get(),
            "language_code": lang_var.get(),
            "tag_audio_events": tag_events_var.get(),
            "num_speakers": num_speakers,
            "timestamps_granularity": granularity_var.get(),
            "diarize": diarize_var.get()
        }
        
        # Update the settings
        SETTINGS["elevenlabs"] = new_settings
        save_settings(SETTINGS)  # This now refers to the imported save_settings function
        messagebox.showinfo("Settings Saved", "ElevenLabs settings saved successfully")
        dialog.destroy()
    
    # Cancel handler
    def cancel():
        dialog.destroy()
    
    ttk.Button(btn_frame, text="Cancel", command=cancel, width=10).pack(side="left", padx=5)
    ttk.Button(btn_frame, text="Save", command=save_elevenlabs_settings, bootstyle="success", width=10).pack(side="left", padx=5)

def show_deepgram_settings_dialog(parent: tk.Tk) -> None:
    """Show dialog to configure Deepgram speech-to-text settings."""
    from settings.settings import SETTINGS, _DEFAULT_SETTINGS, save_settings
    
    # Get current Deepgram settings with fallback to defaults
    deepgram_settings = SETTINGS.get("deepgram", {})
    default_settings = _DEFAULT_SETTINGS.get("deepgram", {})
    
    # Increase height from 800 to 900 to provide more space for all settings
    dialog = create_toplevel_dialog(parent, "Deepgram Settings", "700x900")
    
    # Use scrollable canvas to ensure all content is accessible regardless of screen size
    canvas = tk.Canvas(dialog)
    scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)
    
    # Configure scrolling
    scrollable_frame.bind(
        "<Configure>",
        lambda _: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    # Pack the canvas and scrollbar
    canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
    scrollbar.pack(side="right", fill="y", pady=10)
    
    # Create the main frame with padding inside the scrollable frame
    frame = ttk.Frame(scrollable_frame, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)
    
    # Create form with current settings
    ttk.Label(frame, text="Deepgram Speech-to-Text Settings", 
              font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky="w")
    
    # Model selection
    ttk.Label(frame, text="Model:").grid(row=1, column=0, sticky="w", pady=10)
    model_var = tk.StringVar(value=deepgram_settings.get("model", default_settings.get("model", "nova-2-medical")))
    model_combo = ttk.Combobox(frame, textvariable=model_var, width=30)
    model_combo['values'] = [
        "nova-2-medical", 
        "nova-2", 
        "enhanced",
        "base"
    ]
    model_combo.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="The AI model to use for transcription. 'nova-2-medical' is optimized for medical terminology.", 
              wraplength=400, foreground="gray").grid(row=2, column=0, columnspan=2, sticky="w", padx=(20, 0))
    
    # Language
    ttk.Label(frame, text="Language:").grid(row=3, column=0, sticky="w", pady=10)
    language_var = tk.StringVar(value=deepgram_settings.get("language", default_settings.get("language", "en-US")))
    language_entry = ttk.Combobox(frame, textvariable=language_var, width=30)
    language_entry['values'] = [
        "en-US", "en-GB", "en-AU", "en-NZ", "en-IN", 
        "fr-FR", "de-DE", "es-ES", "it-IT", "ja-JP",
        "ko-KR", "pt-BR", "zh-CN"
    ]
    language_entry.grid(row=3, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Language code for speech recognition.", 
              wraplength=400, foreground="gray").grid(row=4, column=0, columnspan=2, sticky="w", padx=(20, 0))
    
    # Smart formatting toggle
    ttk.Label(frame, text="Smart Formatting:").grid(row=5, column=0, sticky="w", pady=10)
    smart_format_var = tk.BooleanVar(value=deepgram_settings.get("smart_format", default_settings.get("smart_format", True)))
    smart_format_check = ttk.Checkbutton(frame, variable=smart_format_var)
    smart_format_check.grid(row=5, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Adds punctuation and capitalization to transcriptions.", 
              wraplength=400, foreground="gray").grid(row=6, column=0, columnspan=2, sticky="w", padx=(20, 0))
    
    # Diarization toggle
    ttk.Label(frame, text="Speaker Diarization:").grid(row=7, column=0, sticky="w", pady=10)
    diarize_var = tk.BooleanVar(value=deepgram_settings.get("diarize", default_settings.get("diarize", False)))
    diarize_check = ttk.Checkbutton(frame, variable=diarize_var)
    diarize_check.grid(row=7, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Identify and label different speakers in the audio.", 
              wraplength=400, foreground="gray").grid(row=8, column=0, columnspan=2, sticky="w", padx=(20, 0))
    
    # Profanity filter
    ttk.Label(frame, text="Filter Profanity:").grid(row=9, column=0, sticky="w", pady=10)
    profanity_var = tk.BooleanVar(value=deepgram_settings.get("profanity_filter", default_settings.get("profanity_filter", False)))
    profanity_check = ttk.Checkbutton(frame, variable=profanity_var)
    profanity_check.grid(row=9, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Replaces profanity with asterisks.", 
              wraplength=400, foreground="gray").grid(row=10, column=0, columnspan=2, sticky="w", padx=(20, 0))
              
    # Redact PII
    ttk.Label(frame, text="Redact PII:").grid(row=11, column=0, sticky="w", pady=10)
    redact_var = tk.BooleanVar(value=deepgram_settings.get("redact", default_settings.get("redact", False)))
    redact_check = ttk.Checkbutton(frame, variable=redact_var)
    redact_check.grid(row=11, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Redact personally identifiable information like names, addresses, etc.", 
              wraplength=400, foreground="gray").grid(row=12, column=0, columnspan=2, sticky="w", padx=(20, 0))
              
    # Number of alternatives
    ttk.Label(frame, text="Alternatives:").grid(row=13, column=0, sticky="w", pady=10)
    alternatives_var = tk.StringVar(value=str(deepgram_settings.get("alternatives", default_settings.get("alternatives", 1))))
    alternatives_spin = ttk.Spinbox(frame, from_=1, to=5, width=5, textvariable=alternatives_var)
    alternatives_spin.grid(row=13, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Number of alternative transcriptions to generate.", 
              wraplength=400, foreground="gray").grid(row=14, column=0, columnspan=2, sticky="w", padx=(20, 0))
    
    # Create the buttons frame
    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=15, column=0, columnspan=2, pady=(20, 0), sticky="e")
    
    # Save handler
    def save_deepgram_settings():
        try:
            alternatives = int(alternatives_var.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Number of alternatives must be a valid integer.")
            return
            
        # Build the new settings
        new_settings = {
            "model": model_var.get(),
            "language": language_var.get(),
            "smart_format": smart_format_var.get(),
            "diarize": diarize_var.get(),
            "profanity_filter": profanity_var.get(),
            "redact": redact_var.get(),
            "alternatives": alternatives
        }
        
        # Update the settings
        SETTINGS["deepgram"] = new_settings
        save_settings(SETTINGS)
        messagebox.showinfo("Settings Saved", "Deepgram settings saved successfully")
        dialog.destroy()
    
    # Cancel handler
    def cancel():
        dialog.destroy()
    
    ttk.Button(btn_frame, text="Cancel", command=cancel, width=10).pack(side="left", padx=5)
    ttk.Button(btn_frame, text="Save", command=save_deepgram_settings, bootstyle="success", width=10).pack(side="left", padx=5)
    
    # Bind mousewheel for scrolling
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    canvas.bind_all("<MouseWheel>", _on_mousewheel)
    
    # Ensure dialog is closed properly
    def on_close():
        canvas.unbind_all("<MouseWheel>")
        dialog.destroy()
        
    dialog.protocol("WM_DELETE_WINDOW", on_close)

def show_custom_suggestions_dialog(parent: tk.Tk) -> None:
    """Show dialog to manage custom chat suggestions."""
    from settings.settings import SETTINGS, save_settings
    
    # Create dialog
    dialog = tk.Toplevel(parent)
    dialog.title("Manage Custom Chat Suggestions")
    dialog.geometry("700x600")
    dialog.resizable(True, True)
    dialog.transient(parent)
    dialog.grab_set()
    
    # Center the dialog
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
    y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
    dialog.geometry(f"+{x}+{y}")
    
    # Main frame with padding
    main_frame = ttk.Frame(dialog, padding=15)
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Title and description
    title_frame = ttk.Frame(main_frame)
    title_frame.pack(fill=tk.X, pady=(0, 15))
    
    ttk.Label(title_frame, text="Custom Chat Suggestions", font=("Arial", 14, "bold")).pack(anchor="w")
    ttk.Label(title_frame, text="Create custom suggestions for different contexts. These will appear alongside built-in suggestions.", 
              font=("Arial", 10), foreground="gray").pack(anchor="w", pady=(5, 0))
    
    # Create notebook for different contexts
    notebook = ttk.Notebook(main_frame)
    notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
    
    # Store references to suggestion lists
    suggestion_vars = {}
    
    def create_suggestion_tab(tab_name: str, context_key: str):
        """Create a tab for managing suggestions in a specific context."""
        tab_frame = ttk.Frame(notebook)
        notebook.add(tab_frame, text=tab_name)
        
        # Context-specific suggestions (with_content vs without_content)
        if context_key != "global":
            # With content section
            with_frame = ttk.LabelFrame(tab_frame, text="When content exists", padding=10)
            with_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            with_vars = create_suggestion_manager(with_frame, context_key, "with_content")
            suggestion_vars[f"{context_key}_with_content"] = with_vars
            
            # Without content section
            without_frame = ttk.LabelFrame(tab_frame, text="When no content exists", padding=10)
            without_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            without_vars = create_suggestion_manager(without_frame, context_key, "without_content")
            suggestion_vars[f"{context_key}_without_content"] = without_vars
        else:
            # Global suggestions (always shown)
            global_vars = create_suggestion_manager(tab_frame, context_key, None)
            suggestion_vars["global"] = global_vars
    
    def create_suggestion_manager(parent_frame: ttk.Frame, context: str, content_state: str):
        """Create suggestion management interface for a specific context."""
        # Get current suggestions
        if context == "global":
            current_suggestions = SETTINGS.get("custom_chat_suggestions", {}).get("global", [])
        else:
            current_suggestions = SETTINGS.get("custom_chat_suggestions", {}).get(context, {}).get(content_state, [])
        
        # Variables to track suggestions
        suggestion_vars = []
        
        # Scrollable frame for suggestions
        canvas = tk.Canvas(parent_frame, height=150)
        scrollbar = ttk.Scrollbar(parent_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Function to add a suggestion entry
        def add_suggestion_entry(text=""):
            frame = ttk.Frame(scrollable_frame)
            frame.pack(fill=tk.X, pady=2)
            
            var = tk.StringVar(value=text)
            entry = ttk.Entry(frame, textvariable=var, width=50)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
            
            def remove_entry():
                suggestion_vars.remove((frame, var))
                frame.destroy()
                canvas.configure(scrollregion=canvas.bbox("all"))
            
            remove_btn = ttk.Button(frame, text="×", width=3, command=remove_entry)
            remove_btn.pack(side=tk.RIGHT)
            
            suggestion_vars.append((frame, var))
            
            # Update scroll region
            canvas.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
            
            return var
        
        # Add existing suggestions
        for suggestion in current_suggestions:
            add_suggestion_entry(suggestion)
        
        # Add button frame
        button_frame = ttk.Frame(parent_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        def add_new_suggestion():
            var = add_suggestion_entry()
            # Focus the new entry
            for frame, entry_var in suggestion_vars:
                if entry_var == var:
                    for widget in frame.winfo_children():
                        if isinstance(widget, ttk.Entry):
                            widget.focus_set()
                            break
                    break
        
        ttk.Button(button_frame, text="+ Add Suggestion", command=add_new_suggestion).pack(side=tk.LEFT)
        
        def clear_all():
            if messagebox.askyesno("Clear All", "Are you sure you want to remove all suggestions?", parent=dialog):
                for frame, _ in suggestion_vars.copy():
                    frame.destroy()
                suggestion_vars.clear()
                canvas.configure(scrollregion=canvas.bbox("all"))
        
        ttk.Button(button_frame, text="Clear All", command=clear_all).pack(side=tk.LEFT, padx=(10, 0))
        
        return suggestion_vars
    
    # Create tabs
    create_suggestion_tab("Global", "global")
    create_suggestion_tab("Transcript", "transcript")
    create_suggestion_tab("SOAP Note", "soap")
    create_suggestion_tab("Referral", "referral")
    create_suggestion_tab("Letter", "letter")
    
    # Bottom buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, pady=(10, 0))
    
    def save_suggestions():
        """Save all custom suggestions to settings."""
        try:
            custom_suggestions = SETTINGS.get("custom_chat_suggestions", {})
            
            # Update global suggestions
            if "global" in suggestion_vars:
                global_suggestions = []
                for _, var in suggestion_vars["global"]:
                    text = var.get().strip()
                    if text:
                        global_suggestions.append(text)
                custom_suggestions["global"] = global_suggestions
            
            # Update context-specific suggestions
            for context in ["transcript", "soap", "referral", "letter"]:
                if context not in custom_suggestions:
                    custom_suggestions[context] = {"with_content": [], "without_content": []}
                
                # With content
                key = f"{context}_with_content"
                if key in suggestion_vars:
                    with_suggestions = []
                    for _, var in suggestion_vars[key]:
                        text = var.get().strip()
                        if text:
                            with_suggestions.append(text)
                    custom_suggestions[context]["with_content"] = with_suggestions
                
                # Without content
                key = f"{context}_without_content"
                if key in suggestion_vars:
                    without_suggestions = []
                    for _, var in suggestion_vars[key]:
                        text = var.get().strip()
                        if text:
                            without_suggestions.append(text)
                    custom_suggestions[context]["without_content"] = without_suggestions
            
            # Save to settings
            SETTINGS["custom_chat_suggestions"] = custom_suggestions
            save_settings(SETTINGS)
            
            messagebox.showinfo("Success", "Custom suggestions saved successfully!", parent=dialog)
            dialog.destroy()
            
        except Exception as e:
            logging.error(f"Error saving custom suggestions: {e}")
            messagebox.showerror("Error", f"Failed to save suggestions: {str(e)}", parent=dialog)
    
    def cancel():
        dialog.destroy()
    
    # Buttons
    ttk.Button(button_frame, text="Save", command=save_suggestions, bootstyle="success").pack(side=tk.RIGHT, padx=(5, 0))
    ttk.Button(button_frame, text="Cancel", command=cancel).pack(side=tk.RIGHT)
    
    # Handle window close
    dialog.protocol("WM_DELETE_WINDOW", cancel)
    
    # Wait for dialog
    dialog.wait_window()

def test_ollama_connection(_: tk.Tk, ollama_url: str = None) -> bool:
    """
    Test the connection to Ollama server and show a message with the results.
    
    Args:
        parent: Parent window
        ollama_url: The Ollama API URL to test, if None, will use environment variable or default
        
    Returns:
        bool: True if connection was successful, False otherwise
    """
    import requests
    import os
    import logging
    
    if ollama_url is None:
        ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
    
    base_url = ollama_url.rstrip("/")  # Remove trailing slash if present
    
    try:
        # Get available models as a connection test
        response = requests.get(
            f"{base_url}/api/tags",
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            if "models" in data and len(data["models"]) > 0:
                # Get the list of available models
                models = [model["name"] for model in data["models"]]
                model_list = "\n".join(models[:10])  # Show first 10 models
                if len(models) > 10:
                    model_list += f"\n...and {len(models)-10} more"
                
                messagebox.showinfo(
                    "Ollama Connection Successful", 
                    f"Successfully connected to Ollama server at {ollama_url}.\n\n"
                    f"Available models:\n{model_list}"
                )
                return True
            else:
                messagebox.showwarning(
                    "Ollama Connection Warning", 
                    f"Connected to Ollama server at {ollama_url}, but no models were found.\n\n"
                    "Please pull at least one model using 'ollama pull <model_name>'"
                )
                return False
        else:
            messagebox.showerror(
                "Ollama Connection Failed", 
                f"Could not connect to Ollama server at {ollama_url}.\n\n"
                f"Status code: {response.status_code}\n"
                "Please make sure Ollama is running and the URL is correct."
            )
            return False
    except Exception as e:
        messagebox.showerror(
            "Ollama Connection Error", 
            f"Error connecting to Ollama server at {ollama_url}:\n\n{str(e)}\n\n"
            "Please make sure Ollama is running and the URL is correct."
        )
        logging.error(f"Ollama connection test error: {str(e)}")
        return False

def _fetch_tts_voices(provider: str) -> List[Dict[str, str]]:
    """Fetch available voices for a TTS provider.
    
    Args:
        provider: TTS provider name ('openai' or 'elevenlabs')
        
    Returns:
        List of voice dictionaries with 'id' and 'name' keys
    """
    try:
        # Import here to avoid circular imports
        from voice.tts_providers import OpenAITTSProvider, ElevenLabsTTSProvider
        
        if provider == "openai":
            # Get OpenAI API key
            api_key = os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                return []
            
            # Create provider and get voices
            tts_provider = OpenAITTSProvider(api_key)
            voices = tts_provider.get_voices()
            
        elif provider == "elevenlabs":
            # Get ElevenLabs API key
            api_key = os.getenv("ELEVENLABS_API_KEY", "")
            if not api_key:
                return []
            
            # Create provider and get voices
            tts_provider = ElevenLabsTTSProvider(api_key)
            voices = tts_provider.get_voices()
            
        else:
            return []
            
        return voices
        
    except Exception as e:
        logging.error(f"Error fetching TTS voices for {provider}: {e}")
        return []


def show_translation_settings_dialog(parent: tk.Tk) -> None:
    """Show dialog to configure translation settings."""
    from settings.settings import SETTINGS, _DEFAULT_SETTINGS, save_settings
    
    # Get current translation settings with fallback to defaults
    translation_settings = SETTINGS.get("translation", {})
    default_settings = _DEFAULT_SETTINGS.get("translation", {})
    
    dialog = create_toplevel_dialog(parent, "Translation Settings", "600x500")
    
    # Create the main frame with padding
    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)
    
    # Title
    ttk.Label(frame, text="Translation Settings", 
              font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky="w")
    
    # Provider selection
    ttk.Label(frame, text="Translation Provider:").grid(row=1, column=0, sticky="w", pady=10)
    provider_var = tk.StringVar(value=translation_settings.get("provider", default_settings.get("provider", "deep_translator")))
    provider_combo = ttk.Combobox(frame, textvariable=provider_var, width=30, state="readonly")
    provider_combo['values'] = ["deep_translator"]
    provider_combo.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=10)
    
    # Sub-provider selection (for deep_translator)
    ttk.Label(frame, text="Translation Service:").grid(row=2, column=0, sticky="w", pady=10)
    sub_provider_var = tk.StringVar(value=translation_settings.get("sub_provider", default_settings.get("sub_provider", "google")))
    sub_provider_combo = ttk.Combobox(frame, textvariable=sub_provider_var, width=30, state="readonly")
    sub_provider_combo['values'] = ["google", "deepl", "microsoft"]
    sub_provider_combo.grid(row=2, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Google is free, DeepL and Microsoft require API keys", 
              wraplength=400, foreground="gray").grid(row=3, column=0, columnspan=2, sticky="w", padx=(20, 0))
    
    # Default patient language
    ttk.Label(frame, text="Default Patient Language:").grid(row=4, column=0, sticky="w", pady=10)
    patient_lang_var = tk.StringVar(value=translation_settings.get("patient_language", default_settings.get("patient_language", "es")))
    patient_lang_entry = ttk.Entry(frame, textvariable=patient_lang_var, width=32)
    patient_lang_entry.grid(row=4, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Language code (e.g., es, fr, de, zh)", 
              wraplength=400, foreground="gray").grid(row=5, column=0, columnspan=2, sticky="w", padx=(20, 0))
    
    # Default doctor language
    ttk.Label(frame, text="Default Doctor Language:").grid(row=6, column=0, sticky="w", pady=10)
    doctor_lang_var = tk.StringVar(value=translation_settings.get("doctor_language", default_settings.get("doctor_language", "en")))
    doctor_lang_entry = ttk.Entry(frame, textvariable=doctor_lang_var, width=32)
    doctor_lang_entry.grid(row=6, column=1, sticky="w", padx=(10, 0), pady=10)
    
    # Auto-detect checkbox
    auto_detect_var = tk.BooleanVar(value=translation_settings.get("auto_detect", default_settings.get("auto_detect", True)))
    ttk.Checkbutton(frame, text="Auto-detect patient language", 
                    variable=auto_detect_var).grid(row=7, column=0, columnspan=2, sticky="w", pady=(20, 10))
    
    # Button frame
    button_frame = ttk.Frame(dialog)
    button_frame.pack(fill=tk.X, pady=(0, 20))
    
    def save_translation_settings():
        """Save the translation settings."""
        SETTINGS["translation"] = {
            "provider": provider_var.get(),
            "sub_provider": sub_provider_var.get(),
            "patient_language": patient_lang_var.get(),
            "doctor_language": doctor_lang_var.get(),
            "auto_detect": auto_detect_var.get()
        }
        save_settings(SETTINGS)
        dialog.destroy()
    
    ttk.Button(button_frame, text="Save", command=save_translation_settings).pack(side=tk.RIGHT, padx=(0, 20))
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)


def show_tts_settings_dialog(parent: tk.Tk) -> None:
    """Show dialog to configure TTS (Text-to-Speech) settings."""
    from settings.settings import SETTINGS, _DEFAULT_SETTINGS, save_settings
    
    # Get current TTS settings with fallback to defaults
    tts_settings = SETTINGS.get("tts", {})
    default_settings = _DEFAULT_SETTINGS.get("tts", {})
    
    dialog = create_toplevel_dialog(parent, "TTS Settings", "600x550")
    
    # Create the main frame with padding
    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)
    
    # Title
    ttk.Label(frame, text="Text-to-Speech Settings", 
              font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky="w")
    
    # Provider selection
    ttk.Label(frame, text="TTS Provider:").grid(row=1, column=0, sticky="w", pady=10)
    provider_var = tk.StringVar(value=tts_settings.get("provider", default_settings.get("provider", "pyttsx3")))
    provider_combo = ttk.Combobox(frame, textvariable=provider_var, width=30, state="readonly")
    provider_combo['values'] = ["pyttsx3", "elevenlabs", "google"]
    provider_combo.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="pyttsx3 is offline, ElevenLabs requires API key, Google is free online", 
              wraplength=400, foreground="gray").grid(row=2, column=0, columnspan=2, sticky="w", padx=(20, 0))
    
    # Voice selection (will be populated based on provider)
    ttk.Label(frame, text="Voice:").grid(row=3, column=0, sticky="w", pady=10)
    voice_var = tk.StringVar(value=tts_settings.get("voice", default_settings.get("voice", "default")))
    
    # Create frame for voice selection
    voice_frame = ttk.Frame(frame)
    voice_frame.grid(row=3, column=1, sticky="w", padx=(10, 0), pady=10)
    
    # Voice combo box (hidden by default, shown for ElevenLabs)
    voice_combo = ttk.Combobox(voice_frame, textvariable=voice_var, width=40, state="readonly")
    
    # Voice entry (shown by default)
    voice_entry = ttk.Entry(voice_frame, textvariable=voice_var, width=32)
    voice_entry.pack(side=tk.LEFT)
    
    # Fetch voices button (hidden by default)
    fetch_button = ttk.Button(voice_frame, text="Fetch Voices", width=12)
    
    # Loading label
    loading_label = ttk.Label(voice_frame, text="Loading...", foreground="blue")
    
    # Voice description label
    voice_desc_label = ttk.Label(frame, text="Voice ID or name (provider-specific, 'default' for system default)", 
                                 wraplength=400, foreground="gray")
    voice_desc_label.grid(row=4, column=0, columnspan=2, sticky="w", padx=(20, 0))
    
    # Store voice data
    voices_data = {}
    
    # Speech rate
    ttk.Label(frame, text="Speech Rate:").grid(row=5, column=0, sticky="w", pady=10)
    rate_var = tk.IntVar(value=tts_settings.get("rate", default_settings.get("rate", 150)))
    rate_scale = ttk.Scale(frame, from_=50, to=300, variable=rate_var, orient="horizontal", length=200)
    rate_scale.grid(row=5, column=1, sticky="w", padx=(10, 0), pady=10)
    rate_label = ttk.Label(frame, text=f"{rate_var.get()} words/min")
    rate_label.grid(row=5, column=1, sticky="e", padx=(0, 10), pady=10)
    
    def update_rate_label(value):
        rate_label.config(text=f"{int(float(value))} words/min")
    
    rate_scale.config(command=update_rate_label)
    
    # Volume
    ttk.Label(frame, text="Volume:").grid(row=6, column=0, sticky="w", pady=10)
    volume_var = tk.DoubleVar(value=tts_settings.get("volume", default_settings.get("volume", 1.0)))
    volume_scale = ttk.Scale(frame, from_=0.0, to=1.0, variable=volume_var, orient="horizontal", length=200)
    volume_scale.grid(row=6, column=1, sticky="w", padx=(10, 0), pady=10)
    volume_label = ttk.Label(frame, text=f"{int(volume_var.get() * 100)}%")
    volume_label.grid(row=6, column=1, sticky="e", padx=(0, 10), pady=10)
    
    def update_volume_label(value):
        volume_label.config(text=f"{int(float(value) * 100)}%")
    
    volume_scale.config(command=update_volume_label)
    
    # Function to fetch ElevenLabs voices
    def fetch_elevenlabs_voices():
        """Fetch available voices from ElevenLabs API."""
        import threading
        import os
        
        # Show loading
        fetch_button.pack_forget()
        loading_label.pack(side=tk.LEFT, padx=(10, 0))
        
        def fetch_voices_thread():
            try:
                # Import and create TTS manager
                from managers.tts_manager import get_tts_manager
                from utils.security import get_security_manager
                
                # Check if API key exists
                security_manager = get_security_manager()
                api_key = security_manager.get_api_key("elevenlabs")
                
                if not api_key:
                    dialog.after(0, lambda: [
                        loading_label.pack_forget(),
                        fetch_button.pack(side=tk.LEFT, padx=(10, 0)),
                        messagebox.showwarning("API Key Missing", 
                                             "Please set your ElevenLabs API key first.", 
                                             parent=dialog)
                    ])
                    return
                
                # Get TTS manager and set to ElevenLabs
                tts_manager = get_tts_manager()
                tts_manager.set_provider("elevenlabs")
                
                # Fetch voices
                voices = tts_manager.get_available_voices()
                
                if voices:
                    # Format voices for display
                    voice_display_list = []
                    voices_data.clear()
                    
                    for voice in voices:
                        # Format: "Voice Name (Category)"
                        name = voice.get("name", "Unknown")
                        desc = voice.get("description", "")
                        category = desc.split(" - ")[0] if " - " in desc else ""
                        
                        if category:
                            display_name = f"{name} ({category})"
                        else:
                            display_name = name
                        
                        voice_display_list.append(display_name)
                        voices_data[display_name] = voice.get("id", "")
                    
                    # Update UI on main thread
                    def update_ui():
                        loading_label.pack_forget()
                        voice_combo['values'] = sorted(voice_display_list)
                        voice_desc_label.config(text="Select a voice from the dropdown")
                        
                        # Try to select the saved voice
                        current_voice_id = voice_var.get()
                        selected = False
                        
                        # Look for matching voice ID
                        for display_name, voice_id in voices_data.items():
                            if voice_id == current_voice_id:
                                voice_combo.set(display_name)
                                selected = True
                                break
                        
                        # If not found, select first voice
                        if not selected and voice_display_list:
                            voice_combo.set(voice_display_list[0])
                    
                    dialog.after(0, update_ui)
                else:
                    dialog.after(0, lambda: [
                        loading_label.pack_forget(),
                        fetch_button.pack(side=tk.LEFT, padx=(10, 0)),
                        messagebox.showwarning("No Voices Found", 
                                             "Could not fetch voices from ElevenLabs.", 
                                             parent=dialog)
                    ])
                    
            except Exception as e:
                error_msg = str(e)
                dialog.after(0, lambda: [
                    loading_label.pack_forget(),
                    fetch_button.pack(side=tk.LEFT, padx=(10, 0)),
                    messagebox.showerror("Error", 
                                       f"Failed to fetch voices: {error_msg}", 
                                       parent=dialog)
                ])
        
        # Start fetch in background thread
        thread = threading.Thread(target=fetch_voices_thread, daemon=True)
        thread.start()
    
    # Configure fetch button
    fetch_button.config(command=fetch_elevenlabs_voices)
    
    # Function to handle provider change
    def on_provider_change(*args):
        """Handle TTS provider change."""
        provider = provider_var.get()
        
        if provider == "elevenlabs":
            # Show combo box and fetch button
            voice_entry.pack_forget()
            voice_combo.pack(side=tk.LEFT)
            fetch_button.pack(side=tk.LEFT, padx=(10, 0))
            voice_desc_label.config(text="Click 'Fetch Voices' to load available voices")
            
            # If we already have voices data, show them
            if voices_data:
                voice_combo['values'] = sorted(voices_data.keys())
        else:
            # Show entry field
            voice_combo.pack_forget()
            fetch_button.pack_forget()
            loading_label.pack_forget()
            voice_entry.pack(side=tk.LEFT)
            voice_desc_label.config(text="Voice ID or name (provider-specific, 'default' for system default)")
    
    # Bind provider change
    provider_combo.bind("<<ComboboxSelected>>", on_provider_change)
    
    # Initialize UI based on current provider
    on_provider_change()
    
    # If ElevenLabs and we have a saved voice ID, try to fetch voices
    if provider_var.get() == "elevenlabs" and voice_var.get() and voice_var.get() != "default":
        # Auto-fetch voices on dialog open for ElevenLabs
        dialog.after(100, fetch_elevenlabs_voices)
    
    # Default language
    ttk.Label(frame, text="Default Language:").grid(row=7, column=0, sticky="w", pady=10)
    language_var = tk.StringVar(value=tts_settings.get("language", default_settings.get("language", "en")))
    language_entry = ttk.Entry(frame, textvariable=language_var, width=32)
    language_entry.grid(row=7, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Language code (e.g., en, es, fr)", 
              wraplength=400, foreground="gray").grid(row=8, column=0, columnspan=2, sticky="w", padx=(20, 0))
    
    # Button frame
    button_frame = ttk.Frame(dialog)
    button_frame.pack(fill=tk.X, pady=(0, 20))
    
    def save_tts_settings():
        """Save the TTS settings."""
        provider = provider_var.get()
        voice_value = voice_var.get()
        
        # For ElevenLabs, convert display name to voice ID
        if provider == "elevenlabs" and voice_value in voices_data:
            voice_value = voices_data[voice_value]
        
        SETTINGS["tts"] = {
            "provider": provider,
            "voice": voice_value,
            "rate": rate_var.get(),
            "volume": volume_var.get(),
            "language": language_var.get()
        }
        save_settings(SETTINGS)
        dialog.destroy()
    
    ttk.Button(button_frame, text="Save", command=save_tts_settings).pack(side=tk.RIGHT, padx=(0, 20))
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)

