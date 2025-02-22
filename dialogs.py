import tkinter as tk
import ttkbootstrap as ttk

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
    ttk.Label(frame, text="OpenAI Model:").grid(row=1, column=0, sticky="nw")
    model_entry = ttk.Entry(frame, width=60)
    model_entry.grid(row=1, column=1, padx=5, pady=5)
    model_entry.insert(0, current_model)
    ttk.Label(frame, text="Perplexity Model:").grid(row=2, column=0, sticky="nw")
    perplexity_entry = ttk.Entry(frame, width=60)
    perplexity_entry.grid(row=2, column=1, padx=5, pady=5)
    perplexity_entry.insert(0, current_perplexity)
    ttk.Label(frame, text="Grok Model:").grid(row=3, column=0, sticky="nw")
    grok_entry = ttk.Entry(frame, width=60)
    grok_entry.grid(row=3, column=1, padx=5, pady=5)
    grok_entry.insert(0, current_grok)
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill=tk.X, padx=10, pady=10)
    def reset_fields():
        prompt_text.delete("1.0", tk.END)
        insertion_text = default.get("system_message", default.get("prompt", "Default prompt not set"))
        prompt_text.insert("1.0", insertion_text)
        model_entry.delete(0, tk.END)
        model_entry.insert(0, default.get("model", ""))
        perplexity_entry.delete(0, tk.END)
        perplexity_entry.insert(0, default.get("perplexity_model", ""))
        grok_entry.delete(0, tk.END)
        grok_entry.insert(0, default.get("grok_model", ""))
        prompt_text.focus()
    ttk.Button(btn_frame, text="Reset", command=reset_fields).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Save", command=lambda: [save_callback(
        prompt_text.get("1.0", tk.END).strip(),
        model_entry.get().strip(),
        perplexity_entry.get().strip(),
        grok_entry.get().strip()
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
