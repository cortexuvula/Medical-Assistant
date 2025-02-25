import os
import logging
import requests
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
import re

# Function to get OpenAI models
def get_openai_models() -> list:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        api_key = prompt_for_api_key("OpenAI")
        if not api_key:
            return get_fallback_openai_models()
    
    try:
        logging.info("Fetching OpenAI models...")
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get("https://api.openai.com/v1/models", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            # Filter models to include only GPT models
            models = [item["id"] for item in data.get("data", []) 
                     if any(model_name in item["id"] for model_name in ["gpt", "GPT"])]
            logging.info(f"Fetched {len(models)} OpenAI models")
            return sorted(models)
        else:
            logging.error(f"Failed to fetch OpenAI models: {response.status_code}, {response.text}")
            return get_fallback_openai_models()
    except Exception as e:
        logging.error(f"Error fetching OpenAI models: {str(e)}")
        return get_fallback_openai_models()

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

def get_grok_models() -> list:
    # Get the Grok API key from the environment
    api_key = os.getenv("GROK_API_KEY")
    if not api_key:
        # Show dialog to input API key if not found in environment variables
        api_key = prompt_for_api_key()
        if not api_key:
            logging.warning("Grok API key not provided by user")
            return get_fallback_models()
    
    # Log partial key for debugging (showing only first 4 chars)
    key_prefix = api_key[:4] + "..." if api_key else "None"
    logging.info(f"Using Grok API key starting with: {key_prefix}")
    
    try:
        logging.info("Fetching Grok (X.AI) models...")
        # Use the correct API endpoint and headers for X.AI (Grok)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get("https://api.x.ai/v1/models", headers=headers)
            if response.status_code == 200:
                data = response.json()
                models = [item["id"] for item in data.get("data", [])]
                logging.info(f"Fetched {len(models)} models from Grok API")
                return models
            else:
                logging.error(f"Failed to fetch Grok models: {response.status_code}, {response.text}")
                return get_fallback_models()
        except Exception as e:
            logging.error(f"Error fetching Grok models: {str(e)}")
            return get_fallback_models()
    except Exception as e:
        logging.error(f"Error in get_grok_models: {str(e)}")
    return get_fallback_models()

def get_fallback_models() -> list:
    """Return a list of common Grok models as fallback"""
    logging.info("Using fallback set of common Grok models")
    return ["grok-1", "grok-1-mini", "grok-2", "grok-2-mini"]

def prompt_for_api_key(provider: str = "Grok") -> str:
    """Prompt the user for their API key."""
    dialog = tk.Toplevel()
    dialog.title(f"{provider} API Key Required")
    dialog.geometry("450x200")
    dialog.grab_set()
    
    env_var_name = {
        "Grok": "GROK_API_KEY",
        "OpenAI": "OPENAI_API_KEY",
        "Perplexity": "PERPLEXITY_API_KEY"
    }.get(provider, "API_KEY")
    
    provider_url = {
        "Grok": "X.AI account",
        "OpenAI": "https://platform.openai.com/account/api-keys",
        "Perplexity": "https://www.perplexity.ai/settings/api"
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

def create_toplevel_dialog(parent: tk.Tk, title: str, geometry: str = "400x300") -> tk.Toplevel:
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.geometry(geometry)
    dialog.transient(parent)
    dialog.grab_set()
    return dialog

def show_settings_dialog(parent: tk.Tk, title: str, config: dict, default: dict, 
                         current_prompt: str, current_model: str, current_perplexity: str, current_grok: str,
                         save_callback: callable) -> None:
    dialog = create_toplevel_dialog(parent, title, "800x600")
    frame = ttk.LabelFrame(dialog, text=title, padding=10)
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    ttk.Label(frame, text="Prompt:").grid(row=0, column=0, sticky="nw")
    import tkinter.scrolledtext as scrolledtext
    prompt_text = scrolledtext.ScrolledText(frame, width=60, height=10)
    prompt_text.grid(row=0, column=1, padx=5, pady=5)
    prompt_text.insert("1.0", current_prompt)
    
    # OpenAI Model
    ttk.Label(frame, text="OpenAI Model:").grid(row=1, column=0, sticky="nw")
    openai_frame = ttk.Frame(frame)
    openai_frame.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
    openai_combobox = ttk.Combobox(openai_frame, width=48)
    openai_combobox.pack(side=tk.LEFT, fill=tk.X, expand=True)
    if current_model:
        openai_combobox.set(current_model)
    # Add fetch button
    def fetch_openai_models():
        models = get_openai_models()
        if models:
            openai_combobox['values'] = models
            openai_combobox.config(state="readonly")
            parent.bell()
        else:
            openai_combobox['values'] = ["No models found - check API key"]
    openai_fetch_button = ttk.Button(openai_frame, text="Fetch Models", command=fetch_openai_models)
    openai_fetch_button.pack(side=tk.RIGHT, padx=(5, 0))
    
    # Perplexity Model
    ttk.Label(frame, text="Perplexity Model:").grid(row=2, column=0, sticky="nw")
    perplexity_frame = ttk.Frame(frame)
    perplexity_frame.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
    perplexity_combobox = ttk.Combobox(perplexity_frame, width=48)
    perplexity_combobox.pack(side=tk.LEFT, fill=tk.X, expand=True)
    if current_perplexity:
        perplexity_combobox.set(current_perplexity)
    # Add fetch button
    def fetch_perplexity_models():
        models = get_perplexity_models()
        if models:
            perplexity_combobox['values'] = models
            perplexity_combobox.config(state="readonly")
            parent.bell()
        else:
            perplexity_combobox['values'] = ["No models found - check API key"]
    perplexity_fetch_button = ttk.Button(perplexity_frame, text="Fetch Models", command=fetch_perplexity_models)
    perplexity_fetch_button.pack(side=tk.RIGHT, padx=(5, 0))
    
    # Grok Model - keep existing implementation
    ttk.Label(frame, text="Grok Model:").grid(row=3, column=0, sticky="nw")
    grok_frame = ttk.Frame(frame)
    grok_frame.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
    grok_combobox = ttk.Combobox(grok_frame, width=48)
    grok_combobox.pack(side=tk.LEFT, fill=tk.X, expand=True)
    if current_grok:
        grok_combobox.set(current_grok)
    # Add fetch button
    def fetch_grok_models():
        models = get_grok_models()
        if models:
            grok_combobox['values'] = models
            grok_combobox.config(state="readonly")
            parent.bell()
        else:
            grok_combobox['values'] = ["No models found - check API key"]
    grok_fetch_button = ttk.Button(grok_frame, text="Fetch Models", command=fetch_grok_models)
    grok_fetch_button.pack(side=tk.RIGHT, padx=(5, 0))
    
    # Try to pre-populate all models
    openai_models = get_openai_models()
    if openai_models:
        openai_combobox['values'] = openai_models
        openai_combobox.config(state="readonly")
    
    perplexity_models = get_perplexity_models()
    if perplexity_models:
        perplexity_combobox['values'] = perplexity_models
        perplexity_combobox.config(state="readonly")
    
    grok_models = get_grok_models()
    if grok_models:
        grok_combobox['values'] = grok_models
        grok_combobox.config(state="readonly")
    
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill=tk.X, padx=10, pady=10)
    def reset_fields():
        prompt_text.delete("1.0", tk.END)
        insertion_text = default.get("system_message", default.get("prompt", "Default prompt not set"))
        prompt_text.insert("1.0", insertion_text)
        openai_combobox.set(default.get("model", ""))
        perplexity_combobox.set(default.get("perplexity_model", ""))
        grok_combobox.set(default.get("grok_model", ""))
        prompt_text.focus()
    ttk.Button(btn_frame, text="Reset", command=reset_fields).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Save", command=lambda: [save_callback(
        prompt_text.get("1.0", tk.END).strip(),
        openai_combobox.get().strip(),
        perplexity_combobox.get().strip(),
        grok_combobox.get().strip()
    ), dialog.destroy()]).pack(side=tk.RIGHT, padx=5)
    ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

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
    tk.Label(dialog, text=prompt, wraplength=380).pack(padx=20, pady=10)
    style = ttk.Style()
    style.configure("Green.TCheckbutton", background="white", foreground="grey20", indicatorcolor="blue")
    style.map("Green.TCheckbutton", background=[("active", "lightgrey"), ("selected", "green")],
              foreground=[("selected", "white")], indicatorcolor=[("selected", "blue"), ("pressed", "darkblue")])
    checkbox_frame = tk.Frame(dialog)
    checkbox_frame.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)
    vars_list = []
    for cond in conditions:
        var = tk.BooleanVar()
        ttk.Checkbutton(checkbox_frame, text=cond, variable=var, style="Green.TCheckbutton").pack(anchor="w")
        vars_list.append((cond, var))
    tk.Label(dialog, text="Additional conditions (optional):", wraplength=380).pack(padx=20, pady=(10,0))
    optional_text = tk.Text(dialog, width=50, height=3)
    optional_text.pack(padx=20, pady=(0,10))
    selected = []
    def on_ok():
        for cond, var in vars_list:
            if var.get():
                selected.append(cond)
        extra = optional_text.get("1.0", tk.END).strip()
        if extra:
            selected.extend([item.strip() for item in extra.split(",") if item.strip()])
        dialog.destroy()
    btn_frame = tk.Frame(dialog)
    btn_frame.pack(pady=10)
    tk.Button(btn_frame, text="OK", command=on_ok).pack(side=tk.LEFT, padx=5)
    dialog.wait_window()
    return ", ".join(selected) if selected else ""

