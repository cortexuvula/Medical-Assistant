import os
import logging
import requests
import tkinter as tk
from tkinter import messagebox, scrolledtext  # Add scrolledtext here
import ttkbootstrap as ttk
import re

# Function to get OpenAI models
def get_openai_models() -> list:
    import openai
    try:
        models = []
        for model_name in ["gpt-3.5-turbo", "gpt-3.5-turbo-16k", "gpt-4", "gpt-4-turbo", "gpt-4-1106-preview", "gpt-4-32k"]:
            models.append(model_name)
        return models
    except Exception as e:
        logging.error(f"Error fetching OpenAI models: {str(e)}")
        return []

def get_perplexity_models() -> list:
    try:
        return ["sonar-small-chat", "sonar-medium-chat", "sonar-large-chat", "sonar-small-online", "sonar-medium-online", "codellama-70b-instruct", "mixtral-8x7b-instruct", "llama-2-70b-chat", "llama-3-8b-instruct"]
    except Exception as e:
        logging.error(f"Error fetching Perplexity models: {str(e)}")
        return []

def get_grok_models() -> list:
    try:
        return ["grok-1", "grok-0"]
    except Exception as e:
        logging.error(f"Error fetching Grok models: {str(e)}")
        return []

def get_ollama_models() -> list:
    """Fetch available models from Ollama API."""
    import requests
    import json
    import os
    
    try:
        # Get Ollama API URL from environment or use default
        ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
        base_url = ollama_url.rstrip("/")  # Remove trailing slash if present
        
        response = requests.get(
            f"{base_url}/api/tags",
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            if "models" in data:
                # Extract model names from the response
                return [model["name"] for model in data["models"]]
            else:
                logging.warning("Unexpected Ollama API response format")
                # Return common models as fallback
                return ["llama3", "llama3:70b", "llama3:8b", "mistral", "mixtral", "phi3", "codellama", "gemma", "gemma:7b"]
        else:
            logging.warning(f"Failed to fetch Ollama models: {response.status_code}")
            # Return common models as fallback
            return ["llama3", "llama3:70b", "llama3:8b", "mistral", "mixtral", "phi3", "codellama", "gemma", "gemma:7b"]
    except Exception as e:
        logging.error(f"Error fetching Ollama models: {str(e)}")
        # Return common models as fallback
        return ["llama3", "llama3:70b", "llama3:8b", "mistral", "mixtral", "phi3", "codellama", "gemma", "gemma:7b"]

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

def create_toplevel_dialog(parent: tk.Tk, title: str, geometry: str = "600x500") -> tk.Toplevel:
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

def show_settings_dialog(parent: tk.Tk, title: str, config: dict, default: dict, 
                         current_prompt: str, current_model: str, current_perplexity: str, current_grok: str,
                         save_callback: callable, current_ollama: str = "") -> None:
    dialog = create_toplevel_dialog(parent, title, "900x750")
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
    
    # Ollama Model
    ttk.Label(frame, text="Ollama Model:").grid(row=4, column=0, sticky="nw")
    ollama_frame = ttk.Frame(frame)
    ollama_frame.grid(row=4, column=1, padx=5, pady=5, sticky="ew")
    ollama_combobox = ttk.Combobox(ollama_frame, width=48)
    ollama_combobox.pack(side=tk.LEFT, fill=tk.X, expand=True)
    
    # Populate with common Ollama models
    ollama_models = ["llama3", "llama3:70b", "llama3:8b", "mistral", "mixtral", "phi3", "codellama", "gemma", "gemma:7b"]
    ollama_combobox['values'] = ollama_models
    
    if current_ollama:
        ollama_combobox.set(current_ollama)
    else:
        ollama_combobox.set("llama3")  # Default value
    
    # Add fetch button for Ollama models
    def fetch_ollama_models():
        models = get_ollama_models()
        if models:
            ollama_combobox['values'] = models
            ollama_combobox.config(state="readonly")
            parent.bell()
        else:
            ollama_combobox['values'] = ["No models found - check Ollama API URL"]
    ollama_fetch_button = ttk.Button(ollama_frame, text="Fetch Models", command=fetch_ollama_models)
    ollama_fetch_button.pack(side=tk.RIGHT, padx=(5, 0))
    
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
    
    # Try to get Ollama models
    fetch_ollama_models()
    
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill=tk.X, padx=10, pady=10)
    def reset_fields():
        prompt_text.delete("1.0", tk.END)
        insertion_text = default.get("system_message", default.get("prompt", "Default prompt not set"))
        prompt_text.insert("1.0", insertion_text)
        openai_combobox.set(default.get("model", ""))
        perplexity_combobox.set(default.get("perplexity_model", ""))
        grok_combobox.set(default.get("grok_model", ""))
        ollama_combobox.set(default.get("ollama_model", "llama3"))
        prompt_text.focus()
    ttk.Button(btn_frame, text="Reset", command=reset_fields).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Save", command=lambda: [save_callback(
        prompt_text.get("1.0", tk.END).strip(),
        openai_combobox.get().strip(),
        perplexity_combobox.get().strip(),
        grok_combobox.get().strip(),
        ollama_combobox.get().strip()
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
    style.map("Green.TCheckbutton", background=[("active", "teal"), ("selected", "teal")],
              foreground=[("selected", "white")], indicatorcolor=[("selected", "blue"), ("pressed", "teal")])
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

def show_api_keys_dialog(parent: tk.Tk) -> None:
    """Shows a dialog to update API keys and updates the .env file."""
    dialog = create_toplevel_dialog(parent, "Update API Keys", "900x950")
    
    # Increase main frame padding for more spacing around all content
    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    
    # Add a header section with explanation
    header_frame = ttk.Frame(frame)
    header_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 30))
    
    ttk.Label(header_frame, text="API Key Configuration", 
             font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 15))
    
    ttk.Label(header_frame, text="• At least one LLM provider API key (OpenAI, Grok, or Perplexity) is required.",
             wraplength=700, font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=3)
    
    ttk.Label(header_frame, text="• At least one Speech-to-Text API key (Deepgram or ElevenLabs) is REQUIRED for dictation.",
             wraplength=700, font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=3)

    # Get current API keys from environment
    openai_key = os.getenv("OPENAI_API_KEY", "")
    deepgram_key = os.getenv("DEEPGRAM_API_KEY", "")
    grok_key = os.getenv("GROK_API_KEY", "")
    perplexity_key = os.getenv("PERPLEXITY_API_KEY", "")
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY", "")  # NEW: Get ElevenLabs key
    ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")  # Default Ollama URL

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

    # Add toggle buttons to show/hide keys
    def toggle_show_hide(entry):
        current = entry['show']
        entry['show'] = '' if current else '•'
    
    ttk.Button(frame, text="👁", width=3, command=lambda: toggle_show_hide(openai_entry)).grid(row=1, column=2, padx=5)
    ttk.Button(frame, text="👁", width=3, command=lambda: toggle_show_hide(grok_entry)).grid(row=2, column=2, padx=5)
    ttk.Button(frame, text="👁", width=3, command=lambda: toggle_show_hide(perplexity_entry)).grid(row=3, column=2, padx=5)
    # Ollama URL doesn't need a show/hide button as it's not a key
    ttk.Button(frame, text="👁", width=3, command=lambda: toggle_show_hide(deepgram_entry)).grid(row=6, column=2, padx=5)
    ttk.Button(frame, text="👁", width=3, command=lambda: toggle_show_hide(elevenlabs_entry)).grid(row=7, column=2, padx=5)

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

        # Check if at least one of OpenAI, Grok, or Perplexity keys is provided
        if not (new_openai or new_grok or new_perplexity or new_ollama_url):
            error_var.set("Error: At least one of OpenAI, Grok, Perplexity, or Ollama API key/URL is required.")
            return
            
        # Check if at least one speech-to-text API key is provided
        if not (new_deepgram or new_elevenlabs):
            error_var.set("Error: Either Deepgram or ElevenLabs API key is required for speech recognition.")
            return
            
        # Clear any error messages
        error_var.set("")

        # Update .env file
        try:
            # Read existing content
            env_content = ""
            if os.path.exists(".env"):
                with open(".env", "r") as f:
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
            
            # Make sure we have the RECOGNITION_LANGUAGE line
            if not any("RECOGNITION_LANGUAGE=" in line for line in updated_lines):
                updated_lines.append("RECOGNITION_LANGUAGE=en-US")
            
            # Write back to file
            with open(".env", "w") as f:
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
            
            # Success message and close dialog
            messagebox.showinfo("API Keys", "API keys updated successfully")
            dialog.destroy()
            
            # Return results for app to handle UI updates
            return {
                "openai": new_openai,
                "deepgram": new_deepgram,
                "grok": new_grok,
                "perplexity": new_perplexity,
                "elevenlabs": new_elevenlabs,
                "ollama_url": new_ollama_url
            }
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update API keys: {str(e)}")
            return None

    # Add more padding to the button frame
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(pady=30, padx=20)
    ttk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=15).pack(side=tk.LEFT, padx=20)
    ttk.Button(btn_frame, text="Update Keys", command=update_api_keys, bootstyle="success", width=15).pack(side=tk.LEFT, padx=20)
    
    # Wait for dialog to close
    dialog.wait_window()

def show_shortcuts_dialog(parent: tk.Tk) -> None:
    """Show keyboard shortcuts and voice commands dialog."""
    dialog = tk.Toplevel(parent)
    dialog.title("Shortcuts & Voice Commands")
    dialog.geometry("800x600")
    dialog.transient(parent)
    dialog.grab_set()
    notebook = ttk.Notebook(dialog)
    notebook.pack(expand=True, fill="both", padx=10, pady=10)
    kb_frame = ttk.Frame(notebook)
    notebook.add(kb_frame, text="Keyboard Shortcuts")
    kb_tree = ttk.Treeview(kb_frame, columns=("Command", "Description"), show="headings")
    kb_tree.heading("Command", text="Command")
    kb_tree.heading("Description", text="Description")
    kb_tree.column("Command", width=150, anchor="w")
    kb_tree.column("Description", width=500, anchor="w")
    kb_tree.pack(expand=True, fill="both", padx=10, pady=10)
    for cmd, desc in {"Ctrl+N": "New dictation", "Ctrl+S": "Save", "Ctrl+C": "Copy text", "Ctrl+L": "Load Audio File"}.items():
        kb_tree.insert("", tk.END, values=(cmd, desc))
    vc_frame = ttk.Frame(notebook)
    notebook.add(vc_frame, text="Voice Commands")
    vc_tree = ttk.Treeview(vc_frame, columns=("Command", "Action"), show="headings")
    vc_tree.heading("Command", text="Voice Command")
    vc_tree.heading("Action", text="Action")
    vc_tree.column("Command", width=200, anchor="w")
    vc_tree.column("Action", width=450, anchor="w")
    vc_tree.pack(expand=True, fill="both", padx=10, pady=10)
    for cmd, act in {
        "new paragraph": "Insert two newlines",
        "new line": "Insert a newline",
        "full stop": "Insert period & capitalize next",
        "delete last word": "Delete last word"
    }.items():
        vc_tree.insert("", tk.END, values=(cmd, act))
    ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
    
    # Center the dialog on screen
    dialog.update_idletasks()
    width = dialog.winfo_width()
    height = dialog.winfo_height()
    x = (dialog.winfo_screenwidth() // 2) - (width // 2)
    y = (dialog.winfo_screenheight() // 2) - (height // 2)
    dialog.geometry(f'{width}x{height}+{x}+{y}')

def show_about_dialog(parent: tk.Tk) -> None:
    """Show about dialog with app information."""
    messagebox.showinfo("About", "Medical Assistant App\nDeveloped using Vibe Coding.")

def show_letter_options_dialog(parent: tk.Tk) -> tuple:
    """Show dialog to get letter source and specifications from user.
    
    Returns:
        tuple: (source, specifications) where source is 'transcript' or 'dictation'
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
    ttk.Radiobutton(source_frame, text="Use text from Dictation tab", variable=source_var, value="dictation").pack(anchor="w", padx=20, pady=5)
    
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
    def clear_example(event):
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
    from settings import SETTINGS, _DEFAULT_SETTINGS, save_settings
    
    # Get current ElevenLabs settings with fallback to defaults
    elevenlabs_settings = SETTINGS.get("elevenlabs", {})
    default_settings = _DEFAULT_SETTINGS["elevenlabs"]
    
    dialog = create_toplevel_dialog(parent, "ElevenLabs Settings", "700x800")
    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)
    
    # Create form with current settings
    ttk.Label(frame, text="ElevenLabs Speech-to-Text Settings", 
              font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky="w")
    
    # Model ID
    ttk.Label(frame, text="Model ID:").grid(row=1, column=0, sticky="w", pady=10)
    model_var = tk.StringVar(value=elevenlabs_settings.get("model_id", default_settings["model_id"]))
    model_combo = ttk.Combobox(frame, textvariable=model_var, width=30)
    model_combo['values'] = ["scribe_v1", "scribe_v1_base"]  # Updated to supported models only
    model_combo.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="The AI model to use for transcription.", 
              wraplength=400, foreground="gray").grid(row=2, column=0, columnspan=2, sticky="w", padx=(20, 0))
    
    # Language Code
    ttk.Label(frame, text="Language Code:").grid(row=3, column=0, sticky="w", pady=10)
    lang_var = tk.StringVar(value=elevenlabs_settings.get("language_code", default_settings["language_code"]))
    lang_entry = ttk.Entry(frame, textvariable=lang_var, width=30)
    lang_entry.grid(row=3, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Optional ISO language code (e.g., 'en-US'). Leave empty for auto-detection.", 
              wraplength=400, foreground="gray").grid(row=4, column=0, columnspan=2, sticky="w", padx=(20, 0))
    
    # Tag Audio Events
    ttk.Label(frame, text="Tag Audio Events:").grid(row=5, column=0, sticky="w", pady=10)
    tag_events_var = tk.BooleanVar(value=elevenlabs_settings.get("tag_audio_events", default_settings["tag_audio_events"]))
    tag_events_check = ttk.Checkbutton(frame, variable=tag_events_var)
    tag_events_check.grid(row=5, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Add timestamps and labels for audio events like silence, music, etc.", 
              wraplength=400, foreground="gray").grid(row=6, column=0, columnspan=2, sticky="w", padx=(20, 0))
    
    # Number of Speakers
    ttk.Label(frame, text="Number of Speakers:").grid(row=7, column=0, sticky="w", pady=10)
    
    # Create a custom variable handler for the special "None" case
    speakers_value = elevenlabs_settings.get("num_speakers", default_settings["num_speakers"])
    speakers_str = "" if speakers_value is None else str(speakers_value)
    speakers_entry = ttk.Entry(frame, width=30)
    speakers_entry.insert(0, speakers_str)
    speakers_entry.grid(row=7, column=1, sticky="w", padx=(10, 0), pady=10)
    
    ttk.Label(frame, text="Optional number of speakers. Leave empty for auto-detection.", 
              wraplength=400, foreground="gray").grid(row=8, column=0, columnspan=2, sticky="w", padx=(20, 0))
    
    # Timestamps Granularity
    ttk.Label(frame, text="Timestamps Granularity:").grid(row=9, column=0, sticky="w", pady=10)
    granularity_var = tk.StringVar(value=elevenlabs_settings.get("timestamps_granularity", default_settings["timestamps_granularity"]))
    granularity_combo = ttk.Combobox(frame, textvariable=granularity_var, width=30)
    granularity_combo['values'] = ["word", "segment", "sentence"]
    granularity_combo.grid(row=9, column=1, sticky="w", padx=(10, 0), pady=10)
    
    # Diarize
    ttk.Label(frame, text="Diarize:").grid(row=10, column=0, sticky="w", pady=10)
    diarize_var = tk.BooleanVar(value=elevenlabs_settings.get("diarize", default_settings["diarize"]))
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
    from settings import SETTINGS, _DEFAULT_SETTINGS, save_settings
    
    # Get current Deepgram settings with fallback to defaults
    deepgram_settings = SETTINGS.get("deepgram", {})
    default_settings = _DEFAULT_SETTINGS["deepgram"]
    
    # Increase height from 800 to 900 to provide more space for all settings
    dialog = create_toplevel_dialog(parent, "Deepgram Settings", "700x900")
    
    # Use scrollable canvas to ensure all content is accessible regardless of screen size
    canvas = tk.Canvas(dialog)
    scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)
    
    # Configure scrolling
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
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
    model_var = tk.StringVar(value=deepgram_settings.get("model", default_settings["model"]))
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
    language_var = tk.StringVar(value=deepgram_settings.get("language", default_settings["language"]))
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
    smart_format_var = tk.BooleanVar(value=deepgram_settings.get("smart_format", default_settings["smart_format"]))
    smart_format_check = ttk.Checkbutton(frame, variable=smart_format_var)
    smart_format_check.grid(row=5, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Adds punctuation and capitalization to transcriptions.", 
              wraplength=400, foreground="gray").grid(row=6, column=0, columnspan=2, sticky="w", padx=(20, 0))
    
    # Diarization toggle
    ttk.Label(frame, text="Speaker Diarization:").grid(row=7, column=0, sticky="w", pady=10)
    diarize_var = tk.BooleanVar(value=deepgram_settings.get("diarize", default_settings["diarize"]))
    diarize_check = ttk.Checkbutton(frame, variable=diarize_var)
    diarize_check.grid(row=7, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Identify and label different speakers in the audio.", 
              wraplength=400, foreground="gray").grid(row=8, column=0, columnspan=2, sticky="w", padx=(20, 0))
    
    # Profanity filter
    ttk.Label(frame, text="Filter Profanity:").grid(row=9, column=0, sticky="w", pady=10)
    profanity_var = tk.BooleanVar(value=deepgram_settings.get("profanity_filter", default_settings["profanity_filter"]))
    profanity_check = ttk.Checkbutton(frame, variable=profanity_var)
    profanity_check.grid(row=9, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Replaces profanity with asterisks.", 
              wraplength=400, foreground="gray").grid(row=10, column=0, columnspan=2, sticky="w", padx=(20, 0))
              
    # Redact PII
    ttk.Label(frame, text="Redact PII:").grid(row=11, column=0, sticky="w", pady=10)
    redact_var = tk.BooleanVar(value=deepgram_settings.get("redact", default_settings["redact"]))
    redact_check = ttk.Checkbutton(frame, variable=redact_var)
    redact_check.grid(row=11, column=1, sticky="w", padx=(10, 0), pady=10)
    ttk.Label(frame, text="Redact personally identifiable information like names, addresses, etc.", 
              wraplength=400, foreground="gray").grid(row=12, column=0, columnspan=2, sticky="w", padx=(20, 0))
              
    # Number of alternatives
    ttk.Label(frame, text="Alternatives:").grid(row=13, column=0, sticky="w", pady=10)
    alternatives_var = tk.StringVar(value=str(deepgram_settings.get("alternatives", default_settings["alternatives"])))
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

def test_ollama_connection(parent: tk.Tk, ollama_url: str = None) -> bool:
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
