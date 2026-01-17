import tkinter as tk
from tkinter import messagebox
from ui.scaling_utils import ui_scaler
import ttkbootstrap as ttk
from settings.settings_manager import settings_manager

def show_temperature_settings_dialog(parent):
    """
    Show dialog to configure temperature settings for each AI provider and task.
    
    Args:
        parent: Parent window
    """
    # Load fresh settings directly from settings_manager
    current_settings = settings_manager.get_all()
    
    dialog = tk.Toplevel(parent)
    dialog.title("Temperature Settings")
    dialog_width, dialog_height = ui_scaler.get_dialog_size(800, 600)
    dialog.geometry(f"{dialog_width}x{dialog_height}")
    dialog.minsize(700, 500)
    
    # Make it modal
    dialog.transient(parent)

    # Configure the grid
    dialog.rowconfigure(0, weight=1)
    dialog.columnconfigure(0, weight=1)
    
    # Create notebook for provider tabs
    notebook = ttk.Notebook(dialog)
    notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
    
    # Create a frame for each provider
    provider_frames = {}
    sliders = []  # Move sliders list outside the loop
    
    for provider in ["openai", "ollama", "anthropic", "gemini"]:
        provider_display = provider.capitalize()
        provider_frames[provider] = ttk.Frame(notebook, padding=10)
        notebook.add(provider_frames[provider], text=provider_display)
        
        # Configure grid for the frame
        provider_frames[provider].columnconfigure(1, weight=1)
        
        # Add a label at the top
        ttk.Label(provider_frames[provider], 
                 text=f"Adjust temperature settings for {provider_display}",
                 font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=3, pady=(0, 15), sticky="w")
        
        # Add a description
        ttk.Label(provider_frames[provider], 
                 text="Temperature controls randomness in AI responses. Lower values (0.0) make responses more focused and deterministic,\nwhile higher values (1.0) make responses more creative and varied.",
                 wraplength=700).grid(row=1, column=0, columnspan=3, pady=(0, 20), sticky="w")
        
        # Add sliders for each task type
        row = 2
        
        for task in ["refine_text", "improve_text", "soap_note", "referral"]:
            task_display = task.replace("_", " ").title()
            
            # Task label
            ttk.Label(provider_frames[provider], 
                     text=f"{task_display}:", 
                     width=15).grid(row=row, column=0, padx=(0, 10), pady=10, sticky="w")
            
            # Temperature value variable
            temp_var = tk.DoubleVar()
            temp_key = f"{provider}_temperature"
            
            # Get temperature value from settings with proper fallback chain
            default_settings = settings_manager.get_default(task, {})
            if task in current_settings and temp_key in current_settings[task]:
                temp_value = current_settings[task][temp_key]
            elif temp_key in default_settings:
                temp_value = default_settings[temp_key]
            else:
                temp_value = 0.7  # Ultimate fallback
                
            temp_var.set(temp_value)
            
            # Slider for temperature
            slider = ttk.Scale(provider_frames[provider], from_=0.0, to=1.0, 
                              orient=tk.HORIZONTAL, variable=temp_var, length=350)
            slider.grid(row=row, column=1, padx=10, pady=10, sticky="ew")
            
            # Value label
            value_label = ttk.Label(provider_frames[provider], width=5, text=f"{temp_value:.2f}")
            value_label.grid(row=row, column=2, padx=(10, 0), pady=10, sticky="w")
            
            # Update function to show current value
            def update_label(event, lbl=value_label, var=temp_var):
                lbl.config(text=f"{var.get():.2f}")
            
            # Bind slider movement to update label
            slider.bind("<B1-Motion>", update_label)
            slider.bind("<ButtonRelease-1>", update_label)
            
            # Store metadata for saving
            slider_data = {
                "slider": slider,
                "task": task,
                "provider": provider,
                "temp_var": temp_var,
                "label": value_label
            }
            sliders.append(slider_data)
            
            row += 1
    
    # Create frame for buttons
    button_frame = ttk.Frame(dialog)
    button_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
    
    # Save button
    def save_temperature_settings():
        # Collect all temperature values from sliders
        for slider_data in sliders:
            task = slider_data["task"]
            provider_name = slider_data["provider"]
            temp_var = slider_data["temp_var"]
            
            temp_key = f"{provider_name}_temperature"
            
            # Ensure task exists in settings
            if task not in current_settings:
                current_settings[task] = {}
            
            # Update temperature value
            current_settings[task][temp_key] = round(temp_var.get(), 2)
        
        # Save settings to file using settings_manager
        for task, values in current_settings.items():
            if isinstance(values, dict) and task in ["refine_text", "improve_text", "soap_note", "referral"]:
                settings_manager.set(task, values, auto_save=False)
        settings_manager.save()
        messagebox.showinfo("Settings Saved", "Temperature settings have been saved.")
        dialog.destroy()
    
    # Reset button
    def reset_to_defaults():
        for slider_data in sliders:
            task = slider_data["task"]
            provider_name = slider_data["provider"]
            temp_var = slider_data["temp_var"]
            temp_key = f"{provider_name}_temperature"

            # Get default value from settings_manager
            default_task_settings = settings_manager.get_default(task, {})
            if temp_key in default_task_settings:
                default_temp = default_task_settings[temp_key]
            else:
                default_temp = 0.7

            # Set slider to default
            temp_var.set(default_temp)
            slider_data["label"].config(text=f"{default_temp:.2f}")
    
    # Add reset button
    reset_button = ttk.Button(button_frame, text="Reset to Defaults", command=reset_to_defaults)
    reset_button.pack(side=tk.LEFT, padx=5)
    
    save_button = ttk.Button(button_frame, text="Save Settings", command=save_temperature_settings)
    save_button.pack(side=tk.RIGHT, padx=5)
    
    # Center the dialog on the parent window
    dialog.update_idletasks()
    width = dialog.winfo_width()
    height = dialog.winfo_height()
    x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
    dialog.geometry(f"{width}x{height}+{x}+{y}")

    # Grab focus after window is visible
    dialog.deiconify()
    try:
        dialog.grab_set()
    except tk.TclError:
        pass  # Window not viewable yet

    # Wait for the dialog to be closed
    dialog.wait_window()
