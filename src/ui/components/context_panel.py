"""
Context Panel Component for Medical Assistant
Handles persistent context information and templates with accordion-style UI
"""

import tkinter as tk
import tkinter.messagebox
import ttkbootstrap as ttk
from typing import Dict, Callable, List
import logging
from ui.tooltip import ToolTip
from ui.scaling_utils import ui_scaler
from settings.settings import SETTINGS
from ui.ui_constants import Icons


class ContextPanel:
    """Manages the context side panel UI components with expandable templates."""

    # Colors for the context panel (light theme)
    COLORS = {
        "bg": "#f8f9fa",              # Light gray background
        "header_bg": "#ffffff",        # White header
        "border": "#e9ecef",          # Light border
        "text": "#212529",            # Dark text
        "text_muted": "#6c757d",      # Muted text
        "item_hover": "#e3f2fd",      # Light blue hover
        "item_active": "#bbdefb",     # Blue active
        "expand_icon": "#6c757d",     # Gray expand icon
    }

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
        self._expanded_templates: Dict[str, bool] = {}  # Track expanded state
        self._template_content_frames: Dict[str, tk.Frame] = {}  # Store content frames

    def create_context_panel(self) -> ttk.Frame:
        """Create the persistent context side panel.

        Returns:
            ttk.Frame: The context panel frame
        """
        # Create a collapsible side panel with light background
        context_panel = tk.Frame(self.parent, bg=self.COLORS["bg"])

        # Header with "Context & Templates" title and collapse button
        header_frame = tk.Frame(context_panel, bg=self.COLORS["header_bg"])
        header_frame.pack(fill=tk.X)

        # Header content
        header_content = tk.Frame(header_frame, bg=self.COLORS["header_bg"])
        header_content.pack(fill=tk.X, padx=10, pady=8)

        # Collapse button
        self._collapse_btn = tk.Button(
            header_content,
            text=Icons.SIDEBAR_COLLAPSE,
            font=("Segoe UI", 10),
            bg=self.COLORS["header_bg"],
            fg=self.COLORS["text_muted"],
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            command=self._toggle_context_panel
        )
        self._collapse_btn.pack(side=tk.LEFT)
        self.components['context_collapse_btn'] = self._collapse_btn

        # Title
        tk.Label(
            header_content,
            text="Context & Templates",
            font=("Segoe UI", 11, "bold"),
            bg=self.COLORS["header_bg"],
            fg=self.COLORS["text"]
        ).pack(side=tk.LEFT, padx=8)

        # Header border
        tk.Frame(header_frame, height=1, bg=self.COLORS["border"]).pack(fill=tk.X)

        # Search box
        search_frame = tk.Frame(context_panel, bg=self.COLORS["bg"])
        search_frame.pack(fill=tk.X, padx=10, pady=8)

        # Get theme-aware colors for search entry
        from ui.ui_constants import Colors
        from settings.settings import SETTINGS
        current_theme = SETTINGS.get("theme", "flatly")
        is_dark = current_theme in ["darkly", "cyborg", "vapor", "solar", "superhero"]
        theme_colors = Colors.get_theme_colors(is_dark)
        entry_bg = theme_colors["bg"] if is_dark else "#ffffff"
        entry_fg = theme_colors["fg"]
        entry_fg_muted = theme_colors["fg_muted"]

        self._search_var = tk.StringVar()
        self._search_entry = tk.Entry(
            search_frame,
            textvariable=self._search_var,
            font=("Segoe UI", 10),
            relief=tk.FLAT,
            bg=entry_bg,
            fg=entry_fg,
            insertbackground=entry_fg
        )
        self._search_entry.pack(fill=tk.X, ipady=6, ipadx=8)
        self._search_entry.insert(0, "Search templates...")
        self._search_entry.bind("<FocusIn>", self._on_search_focus_in)
        self._search_entry.bind("<FocusOut>", self._on_search_focus_out)
        self._search_entry.bind("<KeyRelease>", self._on_search_change)
        self._search_entry.config(fg=entry_fg_muted)
        self.components['context_search_entry'] = self._search_entry

        # Content frame
        content_frame = tk.Frame(context_panel, bg=self.COLORS["bg"])
        content_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        self.components['context_content_frame'] = content_frame

        # Quick Templates section with accordion
        templates_section = tk.Frame(content_frame, bg=self.COLORS["bg"])
        templates_section.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Section header
        section_header = tk.Frame(templates_section, bg=self.COLORS["bg"])
        section_header.pack(fill=tk.X)

        tk.Label(
            section_header,
            text="Quick Templates",
            font=("Segoe UI", 10, "bold"),
            bg=self.COLORS["bg"],
            fg=self.COLORS["text"]
        ).pack(side=tk.LEFT, pady=5)

        # Scrollable templates container with fixed height
        templates_container = tk.Frame(templates_section, bg=self.COLORS["bg"])
        templates_container.pack(fill=tk.X)

        # Create canvas for scrolling
        self._templates_canvas = tk.Canvas(
            templates_container,
            bg=self.COLORS["bg"],
            highlightthickness=0,
            height=200  # Fixed height - shows ~5-6 collapsed templates
        )

        # Scrollbar (only visible when needed)
        self._templates_scrollbar = ttk.Scrollbar(
            templates_container,
            orient="vertical",
            command=self._templates_canvas.yview
        )

        # Inner frame that holds the actual template items
        self.templates_frame = tk.Frame(self._templates_canvas, bg=self.COLORS["bg"])

        # Create window in canvas for the frame
        self._templates_canvas_window = self._templates_canvas.create_window(
            (0, 0),
            window=self.templates_frame,
            anchor="nw"
        )

        # Configure scrolling
        self._templates_canvas.configure(yscrollcommand=self._templates_scrollbar.set)

        # Pack canvas and scrollbar
        self._templates_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._templates_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind events for proper scrolling behavior
        self.templates_frame.bind("<Configure>", self._on_templates_frame_configure)
        self._templates_canvas.bind("<Configure>", self._on_templates_canvas_configure)

        # Enable mousewheel scrolling when mouse is over templates area
        self._templates_canvas.bind("<Enter>", self._bind_mousewheel)
        self._templates_canvas.bind("<Leave>", self._unbind_mousewheel)

        # Create accordion-style template items
        self._create_accordion_templates()

        # Context Information section
        context_section = tk.Frame(content_frame, bg=self.COLORS["bg"])
        context_section.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Section header
        tk.Label(
            context_section,
            text="Context Information",
            font=("Segoe UI", 10, "bold"),
            bg=self.COLORS["bg"],
            fg=self.COLORS["text"]
        ).pack(anchor=tk.W, pady=(0, 5))

        # Text area with border
        text_container = tk.Frame(context_section, bg=self.COLORS["border"])
        text_container.pack(fill=tk.BOTH, expand=True)

        text_inner = tk.Frame(text_container, bg="#ffffff")
        text_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Create text widget with scrollbar
        text_scroll = ttk.Scrollbar(text_inner)
        text_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.components['context_text'] = tk.Text(
            text_inner,
            wrap=tk.WORD,
            yscrollcommand=text_scroll.set,
            height=8,
            width=25,
            font=("Segoe UI", 10),
            relief=tk.FLAT,
            bg="#ffffff",
            fg=self.COLORS["text"]
        )
        self.components['context_text'].pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        text_scroll.config(command=self.components['context_text'].yview)

        # Context actions
        actions_frame = tk.Frame(content_frame, bg=self.COLORS["bg"])
        actions_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(
            actions_frame,
            text="Save Template",
            bootstyle="info-outline",
            command=self._save_context_template
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            actions_frame,
            text="Clear",
            bootstyle="secondary-outline",
            command=self._clear_context
        ).pack(side=tk.LEFT)

        self.components['context_panel'] = context_panel

        return context_panel

    def _on_search_focus_in(self, event):
        """Handle search field focus in."""
        if self._search_entry.get() == "Search templates...":
            self._search_entry.delete(0, tk.END)
            # Use theme-aware colors
            from ui.ui_constants import Colors
            from settings.settings import SETTINGS
            current_theme = SETTINGS.get("theme", "flatly")
            is_dark = current_theme in ["darkly", "cyborg", "vapor", "solar", "superhero"]
            theme_colors = Colors.get_theme_colors(is_dark)
            self._search_entry.config(fg=theme_colors["fg"])

    def _on_search_focus_out(self, event):
        """Handle search field focus out."""
        if not self._search_entry.get():
            self._search_entry.insert(0, "Search templates...")
            # Use theme-aware colors
            from ui.ui_constants import Colors
            from settings.settings import SETTINGS
            current_theme = SETTINGS.get("theme", "flatly")
            is_dark = current_theme in ["darkly", "cyborg", "vapor", "solar", "superhero"]
            theme_colors = Colors.get_theme_colors(is_dark)
            self._search_entry.config(fg=theme_colors["fg_muted"])

    def _on_templates_frame_configure(self, event):
        """Update scroll region when templates frame changes size."""
        self._templates_canvas.configure(scrollregion=self._templates_canvas.bbox("all"))
        # Show/hide scrollbar based on content height
        if self.templates_frame.winfo_reqheight() > self._templates_canvas.winfo_height():
            self._templates_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        else:
            self._templates_scrollbar.pack_forget()

    def _on_templates_canvas_configure(self, event):
        """Adjust inner frame width to match canvas."""
        self._templates_canvas.itemconfig(self._templates_canvas_window, width=event.width)

    def _bind_mousewheel(self, event):
        """Bind mousewheel when mouse enters templates area."""
        self._templates_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self._templates_canvas.bind_all("<Button-4>", self._on_mousewheel)  # Linux scroll up
        self._templates_canvas.bind_all("<Button-5>", self._on_mousewheel)  # Linux scroll down

    def _unbind_mousewheel(self, event):
        """Unbind mousewheel when mouse leaves templates area."""
        self._templates_canvas.unbind_all("<MouseWheel>")
        self._templates_canvas.unbind_all("<Button-4>")
        self._templates_canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        """Handle mousewheel scrolling."""
        if event.num == 4:  # Linux scroll up
            self._templates_canvas.yview_scroll(-1, "units")
        elif event.num == 5:  # Linux scroll down
            self._templates_canvas.yview_scroll(1, "units")
        else:  # Windows/Mac
            self._templates_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_search_change(self, event):
        """Handle search text change."""
        search_text = self._search_var.get().lower()
        if search_text == "search templates...":
            search_text = ""
        self._filter_templates(search_text)

    def _filter_templates(self, search_text: str):
        """Filter templates based on search text."""
        for template_name, content_frame in self._template_content_frames.items():
            parent_frame = content_frame.master
            if search_text and search_text not in template_name.lower():
                parent_frame.pack_forget()
            else:
                parent_frame.pack(fill=tk.X, pady=1)

    def _create_accordion_templates(self):
        """Create accordion-style template items."""
        # Built-in templates
        builtin_templates = [
            ("Follow Up", "Follow-up visit for ongoing condition."),
            ("New Patient", "New patient consultation. No previous medical history available."),
            ("Telehealth", "Telehealth consultation via video call."),
            ("Annual Check-up", "Annual health checkup and preventive care visit."),
            ("Urgent Care", "Urgent care visit for acute symptoms.")
        ]

        # Clear existing
        for widget in self.templates_frame.winfo_children():
            widget.destroy()

        self._expanded_templates.clear()
        self._template_content_frames.clear()

        # Get favorite template names from settings
        favorite_templates = set(SETTINGS.get("context_template_favorites", []))

        # Collect all templates with favorite status
        all_templates = []

        # Add built-in templates
        for name, text in builtin_templates:
            is_favorite = name in favorite_templates
            all_templates.append((name, text, True, is_favorite))  # (name, text, is_builtin, is_favorite)

        # Add custom templates
        custom_templates = SETTINGS.get("custom_context_templates", {})
        if custom_templates:
            for template_name, template_text in custom_templates.items():
                is_favorite = template_name in favorite_templates
                all_templates.append((template_name, template_text, False, is_favorite))

        # Sort: favorites first (alphabetically), then non-favorites (alphabetically)
        favorites = sorted([t for t in all_templates if t[3]], key=lambda x: x[0].lower())
        non_favorites = sorted([t for t in all_templates if not t[3]], key=lambda x: x[0].lower())
        sorted_templates = favorites + non_favorites

        # Create accordion items
        for name, text, is_builtin, is_favorite in sorted_templates:
            self._create_accordion_item(name, text, is_builtin=is_builtin, is_favorite=is_favorite)

    def _create_accordion_item(self, name: str, text: str, is_builtin: bool = True, is_favorite: bool = False):
        """Create a single accordion item.

        Args:
            name: Template name
            text: Template content
            is_builtin: Whether this is a built-in template
            is_favorite: Whether this template is marked as favorite
        """
        # Initialize as collapsed
        self._expanded_templates[name] = False

        # Item container
        item_frame = tk.Frame(self.templates_frame, bg=self.COLORS["bg"])
        item_frame.pack(fill=tk.X, pady=1)

        # Header row (clickable)
        header = tk.Frame(item_frame, bg="#ffffff", cursor="hand2")
        header.pack(fill=tk.X)

        # Favorite star button
        star_label = tk.Label(
            header,
            text="★" if is_favorite else "☆",
            font=("Segoe UI", 10),
            bg="#ffffff",
            fg="#f0ad4e" if is_favorite else self.COLORS["text_muted"],
            cursor="hand2"
        )
        star_label.pack(side=tk.LEFT, padx=(8, 2), pady=8)

        def toggle_favorite(e=None):
            """Toggle favorite status for this template."""
            favorite_templates = set(SETTINGS.get("context_template_favorites", []))
            if name in favorite_templates:
                favorite_templates.discard(name)
                star_label.config(text="☆", fg=self.COLORS["text_muted"])
            else:
                favorite_templates.add(name)
                star_label.config(text="★", fg="#f0ad4e")

            # Save to settings
            SETTINGS["context_template_favorites"] = list(favorite_templates)
            from settings.settings import save_settings
            save_settings(SETTINGS)

            # Refresh to re-sort templates
            self._create_accordion_templates()

        star_label.bind("<Button-1>", toggle_favorite)

        # Expand indicator
        expand_label = tk.Label(
            header,
            text=Icons.SECTION_CLOSED,
            font=("Segoe UI", 9),
            bg="#ffffff",
            fg=self.COLORS["expand_icon"]
        )
        expand_label.pack(side=tk.LEFT, padx=(2, 5), pady=8)

        # Template name
        name_label = tk.Label(
            header,
            text=name,
            font=("Segoe UI", 10),
            bg="#ffffff",
            fg=self.COLORS["text"],
            anchor=tk.W
        )
        name_label.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=8)

        # Content frame (initially hidden)
        content_frame = tk.Frame(item_frame, bg="#f8f9fa")
        self._template_content_frames[name] = content_frame

        # Content inner
        content_inner = tk.Frame(content_frame, bg="#f8f9fa")
        content_inner.pack(fill=tk.X, padx=25, pady=(0, 10))

        # Preview text
        preview_text = text[:80] + "..." if len(text) > 80 else text
        tk.Label(
            content_inner,
            text=preview_text,
            font=("Segoe UI", 9),
            bg="#f8f9fa",
            fg=self.COLORS["text_muted"],
            wraplength=180,
            justify=tk.LEFT
        ).pack(anchor=tk.W, pady=(5, 8))

        # Action buttons
        actions = tk.Frame(content_inner, bg="#f8f9fa")
        actions.pack(anchor=tk.W)

        ttk.Button(
            actions,
            text="Use",
            bootstyle="primary-outline",
            command=lambda t=text: self._apply_template(t)
        ).pack(side=tk.LEFT, padx=(0, 5))

        if not is_builtin:
            ttk.Button(
                actions,
                text="Delete",
                bootstyle="danger-outline",
                command=lambda n=name: self._delete_custom_template(n)
            ).pack(side=tk.LEFT)

        # Click handlers
        def toggle_expand(e=None):
            is_expanded = self._expanded_templates.get(name, False)
            if is_expanded:
                content_frame.pack_forget()
                expand_label.config(text=Icons.SECTION_CLOSED)
                self._expanded_templates[name] = False
            else:
                content_frame.pack(fill=tk.X)
                expand_label.config(text=Icons.SECTION_OPEN)
                self._expanded_templates[name] = True

        header.bind("<Button-1>", toggle_expand)
        expand_label.bind("<Button-1>", toggle_expand)
        name_label.bind("<Button-1>", toggle_expand)

    def _apply_template(self, text: str):
        """Apply a template to the context text area."""
        self.components['context_text'].delete("1.0", tk.END)
        self.components['context_text'].insert("1.0", text)
    
    def _toggle_context_panel(self):
        """Toggle the context panel visibility."""
        if self._context_collapsed:
            # Expand
            self.components['context_content_frame'].pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
            self._collapse_btn.config(text=Icons.SIDEBAR_COLLAPSE)
            self._context_collapsed = False
        else:
            # Collapse
            self.components['context_content_frame'].pack_forget()
            self._collapse_btn.config(text=Icons.SIDEBAR_EXPAND)
            self._context_collapsed = True
    
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
        width, height = ui_scaler.get_dialog_size(400, 280, min_width=350, min_height=250)
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
        """Create template buttons - redirects to accordion style."""
        self._create_accordion_templates()
    
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