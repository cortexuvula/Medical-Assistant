"""
Context Panel Component for Medical Assistant
Handles persistent context information and templates
"""

import tkinter as tk
import tkinter.messagebox
import ttkbootstrap as ttk
from typing import Dict, Callable
import logging
from ui.tooltip import ToolTip
from ui.scaling_utils import ui_scaler
from settings.settings import SETTINGS


class ContextPanel:
    """Manages the context side panel UI components."""
    
    def __init__(self, parent_ui):
        """Initialize the ContextPanel component.
        
        Args:
            parent_ui: Reference to the parent WorkflowUI instance
        """
        self.parent_ui = parent_ui
        self.parent = parent_ui.parent
        self.components = parent_ui.components
        
        self._context_collapsed = False
        self.templates_frame = None
        
    def create_context_panel(self) -> ttk.Frame:
        """Create the persistent context side panel.
        
        Returns:
            ttk.Frame: The context panel frame
        """
        # Create a collapsible side panel
        context_panel = ttk.Frame(self.parent)
        
        # Header with collapse button
        header_frame = ttk.Frame(context_panel)
        header_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.components['context_collapse_btn'] = ttk.Button(
            header_frame,
            text="<",
            width=3,
            command=self._toggle_context_panel
        )
        self.components['context_collapse_btn'].pack(side=tk.LEFT)
        
        ttk.Label(
            header_frame, 
            text="Context", 
            font=("Segoe UI", 12, "bold")
        ).pack(side=tk.LEFT, padx=10)
        
        # Context content frame
        content_frame = ttk.Frame(context_panel)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.components['context_content_frame'] = content_frame
        
        # Quick templates
        self.templates_frame = ttk.LabelFrame(content_frame, text="Quick Templates", padding=10)
        self.templates_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Create initial templates
        self._create_template_buttons()
        
        # Context text area
        text_frame = ttk.LabelFrame(content_frame, text="Context Information", padding=10)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create text widget with scrollbar
        text_scroll = ttk.Scrollbar(text_frame)
        text_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.components['context_text'] = tk.Text(
            text_frame,
            wrap=tk.WORD,
            yscrollcommand=text_scroll.set,
            height=10,
            width=30
        )
        self.components['context_text'].pack(fill=tk.BOTH, expand=True)
        text_scroll.config(command=self.components['context_text'].yview)
        
        # Context actions
        actions_frame = ttk.Frame(content_frame)
        actions_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(
            actions_frame,
            text="Save Template",
            bootstyle="info",
            command=self._save_context_template
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            actions_frame,
            text="Clear",
            bootstyle="secondary",
            command=self._clear_context
        ).pack(side=tk.LEFT, padx=2)
        
        self.components['context_panel'] = context_panel
        
        return context_panel
    
    def _toggle_context_panel(self):
        """Toggle the context panel visibility."""
        if self._context_collapsed:
            # Expand
            self.components['context_content_frame'].pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            self.components['context_collapse_btn'].config(text="<")
            self._context_collapsed = False
        else:
            # Collapse
            self.components['context_content_frame'].pack_forget()
            self.components['context_collapse_btn'].config(text=">")
            self._context_collapsed = True
    
    def _apply_context_template(self, template: str):
        """Apply a context template."""
        template_texts = {
            "Follow-up visit": "Follow-up visit for ongoing condition.",
            "New patient": "New patient consultation. No previous medical history available.",
            "Telehealth consultation": "Telehealth consultation via video call.",
            "Annual checkup": "Annual health checkup and preventive care visit.",
            "Urgent care visit": "Urgent care visit for acute symptoms."
        }
        
        if template in template_texts:
            self.components['context_text'].delete("1.0", tk.END)
            self.components['context_text'].insert("1.0", template_texts[template])
    
    def _save_context_template(self):
        """Save current context as a template."""
        # Get current context text
        context_text = self.components['context_text'].get("1.0", tk.END).strip()
        
        if not context_text:
            tkinter.messagebox.showwarning("No Content", "Please enter some context text before saving as a template.")
            return
        
        # Create dialog to get template name
        dialog = tk.Toplevel(self.parent)
        dialog.title("Save Context Template")
        # Get responsive dialog size
        width, height = ui_scaler.get_dialog_size(400, 200, min_width=350, min_height=150)
        dialog.geometry(f"{width}x{height}")
        dialog.resizable(False, False)
        dialog.transient(self.parent)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (dialog.winfo_screenheight() // 2) - (height // 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")
        
        # Dialog content
        ttk.Label(dialog, text="Template Name:", font=("Segoe UI", ui_scaler.scale_font_size(11))).pack(pady=ui_scaler.get_padding(10))
        
        name_var = tk.StringVar()
        name_entry = ttk.Entry(dialog, textvariable=name_var, width=ui_scaler.scale_dimension(40), font=("Segoe UI", ui_scaler.scale_font_size(10)))
        name_entry.pack(pady=ui_scaler.get_padding(5))
        name_entry.focus()
        
        # Preview of content
        ttk.Label(dialog, text="Content Preview:", font=("Segoe UI", ui_scaler.scale_font_size(10))).pack(pady=(ui_scaler.get_padding(15), ui_scaler.get_padding(5)))
        preview_text = context_text[:100] + "..." if len(context_text) > 100 else context_text
        preview_label = ttk.Label(dialog, text=preview_text, font=("Segoe UI", ui_scaler.scale_font_size(9)), foreground="gray")
        preview_label.pack(pady=ui_scaler.get_padding(5), padx=ui_scaler.get_padding(20))
        
        result = {"saved": False}
        
        def save_template():
            template_name = name_var.get().strip()
            if not template_name:
                tkinter.messagebox.showwarning("Invalid Name", "Please enter a template name.")
                return
            
            # Save to settings
            try:
                custom_templates = SETTINGS.get("custom_context_templates", {})
                custom_templates[template_name] = context_text
                SETTINGS["custom_context_templates"] = custom_templates
                
                # Save settings
                from settings.settings import save_settings
                save_settings(SETTINGS)
                
                # Refresh template buttons
                self._refresh_template_buttons()
                
                result["saved"] = True
                dialog.destroy()
                
                tkinter.messagebox.showinfo("Template Saved", f"Template '{template_name}' has been saved successfully!")
                
            except Exception as e:
                logging.error(f"Error saving context template: {e}")
                tkinter.messagebox.showerror("Error", f"Failed to save template: {str(e)}")
        
        def cancel():
            dialog.destroy()
        
        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="Save", command=save_template, bootstyle="success").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=cancel, bootstyle="secondary").pack(side=tk.LEFT, padx=5)
        
        # Bind Enter key to save
        name_entry.bind("<Return>", lambda e: save_template())
        dialog.bind("<Escape>", lambda e: cancel())
        
        # Wait for dialog to close
        dialog.wait_window()
    
    def _create_template_buttons(self):
        """Create template buttons including built-in and custom templates."""
        # Built-in templates
        builtin_templates = [
            "Follow-up visit",
            "New patient", 
            "Telehealth consultation",
            "Annual checkup",
            "Urgent care visit"
        ]
        
        # Clear existing buttons
        for widget in self.templates_frame.winfo_children():
            widget.destroy()
        
        # Add built-in templates
        for template in builtin_templates:
            btn = ttk.Button(
                self.templates_frame,
                text=template,
                bootstyle="outline",
                command=lambda t=template: self._apply_context_template(t)
            )
            btn.pack(pady=3, padx=5, fill=tk.X)
        
        # Add custom templates
        custom_templates = SETTINGS.get("custom_context_templates", {})
        if custom_templates:
            # Add separator
            separator = ttk.Separator(self.templates_frame, orient="horizontal")
            separator.pack(fill=tk.X, pady=5)
            
            # Add custom template buttons
            for template_name, template_text in custom_templates.items():
                btn_frame = ttk.Frame(self.templates_frame)
                btn_frame.pack(fill=tk.X, pady=3, padx=5)
                
                # Template button
                btn = ttk.Button(
                    btn_frame,
                    text=template_name,
                    bootstyle="info-outline",
                    command=lambda t=template_text: self._apply_custom_template(t)
                )
                btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
                
                # Delete button
                del_btn = ttk.Button(
                    btn_frame,
                    text="X",
                    bootstyle="danger-outline",
                    width=3,
                    command=lambda name=template_name: self._delete_custom_template(name)
                )
                del_btn.pack(side=tk.RIGHT, padx=(2, 0))
                ToolTip(del_btn, f"Delete template '{template_name}'")
    
    def _refresh_template_buttons(self):
        """Refresh the template buttons to show updated custom templates."""
        self._create_template_buttons()
    
    def _apply_custom_template(self, template_text: str):
        """Apply a custom template."""
        self.components['context_text'].delete("1.0", tk.END)
        self.components['context_text'].insert("1.0", template_text)
    
    def _delete_custom_template(self, template_name: str):
        """Delete a custom template."""
        result = tkinter.messagebox.askyesno(
            "Delete Template",
            f"Are you sure you want to delete the template '{template_name}'?",
            icon="warning"
        )
        
        if result:
            try:
                custom_templates = SETTINGS.get("custom_context_templates", {})
                if template_name in custom_templates:
                    del custom_templates[template_name]
                    SETTINGS["custom_context_templates"] = custom_templates
                    
                    # Save settings
                    from settings.settings import save_settings
                    save_settings(SETTINGS)
                    
                    # Refresh template buttons
                    self._refresh_template_buttons()
                    
                    tkinter.messagebox.showinfo("Template Deleted", f"Template '{template_name}' has been deleted.")
                    
            except Exception as e:
                logging.error(f"Error deleting custom template: {e}")
                tkinter.messagebox.showerror("Error", f"Failed to delete template: {str(e)}")
    
    def _clear_context(self):
        """Clear the context text."""
        self.components['context_text'].delete("1.0", tk.END)