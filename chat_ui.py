"""
Chat UI Components for Medical Assistant
Provides a ChatGPT-style interface for interacting with document content
"""

import tkinter as tk
from tkinter import ttk
import ttkbootstrap as ttk
from typing import Callable, Optional, Dict, Any
import logging

from tooltip import ToolTip


class ChatUI:
    """Manages the chat interface components for LLM interaction"""
    
    def __init__(self, parent_frame: ttk.Frame, app):
        """
        Initialize the chat UI components.
        
        Args:
            parent_frame: The parent frame to contain the chat UI
            app: Reference to the main application
        """
        self.parent_frame = parent_frame
        self.app = app
        self.chat_frame = None
        self.input_text = None
        self.send_button = None
        self.clear_button = None
        self.char_counter = None
        self.context_indicator = None
        self.is_processing = False
        
        # Callbacks
        self.on_send_callback = None
        
        # Configuration from settings
        from settings import SETTINGS
        chat_config = SETTINGS.get("chat_interface", {})
        self.max_input_length = chat_config.get("max_input_length", 2000)
        self.min_input_lines = 2
        self.max_input_lines = 5
        
        # Collapse state
        self._collapsed = False
        self.content_frame = None
        self.collapse_btn = None
        
        # Create the UI
        self.create_chat_interface()
        
    def create_chat_interface(self):
        """Create the main chat interface components"""
        # Main chat frame with border
        self.chat_frame = ttk.LabelFrame(
            self.parent_frame, 
            text="AI Assistant Chat", 
            padding=(10, 5)
        )
        self.chat_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=(0, 5))
        
        # Header frame with title and collapse button
        header_frame = ttk.Frame(self.chat_frame)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Collapse/expand button
        self.collapse_btn = ttk.Button(
            header_frame,
            text="^",
            width=3,
            command=self._toggle_collapse
        )
        self.collapse_btn.pack(side=tk.RIGHT)
        ToolTip(self.collapse_btn, "Hide/Show chat interface")
        
        # Content frame that can be hidden
        self.content_frame = ttk.Frame(self.chat_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top row - context indicator and controls
        top_row = ttk.Frame(self.content_frame)
        top_row.pack(fill=tk.X, pady=(0, 5))
        
        # Context indicator (shows which tab is active)
        self.context_indicator = ttk.Label(
            top_row,
            text="Context: Transcript",
            font=("Arial", 9),
            foreground="gray"
        )
        self.context_indicator.pack(side=tk.LEFT, padx=(0, 10))
        
        # Character counter
        self.char_counter = ttk.Label(
            top_row,
            text=f"0/{self.max_input_length}",
            font=("Arial", 9),
            foreground="gray"
        )
        self.char_counter.pack(side=tk.RIGHT, padx=(10, 0))
        
        # Middle section - input area with scrollbar
        input_frame = ttk.Frame(self.content_frame)
        input_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        # Create text widget with scrollbar
        self.input_text = tk.Text(
            input_frame,
            height=self.min_input_lines,
            wrap=tk.WORD,
            font=("Arial", 11),
            relief=tk.FLAT,
            borderwidth=1
        )
        
        # Scrollbar for input text
        scrollbar = ttk.Scrollbar(input_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.input_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.input_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.input_text.yview)
        
        # Apply theme-aware styling
        self._apply_text_styling()
        
        # Bottom row - buttons and suggestions
        bottom_row = ttk.Frame(self.content_frame)
        bottom_row.pack(fill=tk.X)
        
        # Button frame (right side)
        button_frame = ttk.Frame(bottom_row)
        button_frame.pack(side=tk.RIGHT)
        
        # Clear button
        self.clear_button = ttk.Button(
            button_frame,
            text="Clear",
            command=self.clear_input,
            width=8,
            bootstyle="secondary"
        )
        self.clear_button.pack(side=tk.LEFT, padx=(0, 5))
        ToolTip(self.clear_button, "Clear input (Esc)")
        
        # Send button
        self.send_button = ttk.Button(
            button_frame,
            text="Send",
            command=self.send_message,
            width=10,
            bootstyle="primary"
        )
        self.send_button.pack(side=tk.LEFT)
        ToolTip(self.send_button, "Send message (Ctrl+Enter)")
        
        # Suggestions frame (left side)
        self.suggestions_frame = ttk.Frame(bottom_row)
        self.suggestions_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Manage suggestions button
        self.manage_btn = ttk.Button(
            bottom_row,
            text="Settings",
            command=self._show_suggestions_manager,
            width=3,
            bootstyle="secondary-outline"
        )
        self.manage_btn.pack(side=tk.LEFT, padx=(5, 0))
        ToolTip(self.manage_btn, "Manage custom suggestions")
        
        # Bind events
        self._bind_events()
        
        # Initial setup
        self.update_context_indicator()
        
    def _apply_text_styling(self):
        """Apply theme-aware styling to the text widget"""
        # Check if we have access to the theme manager
        is_dark = self._is_dark_theme()
        
        if is_dark:
            # Dark theme colors
            bg_color = "#212529"
            fg_color = "#f8f9fa"
            insert_color = "#f8f9fa"
            select_bg = "#495057"
            select_fg = "#ffffff"
            border_color = "#495057"
        else:
            # Light theme colors
            bg_color = "#ffffff"
            fg_color = "#212529"
            insert_color = "#212529"
            select_bg = "#0d6efd"
            select_fg = "#ffffff"
            border_color = "#dee2e6"
            
        self.input_text.config(
            bg=bg_color,
            fg=fg_color,
            insertbackground=insert_color,
            selectbackground=select_bg,
            selectforeground=select_fg,
            highlightbackground=border_color,
            highlightcolor=border_color
        )
        
        # Update context indicator and character counter colors
        self._update_label_colors(is_dark)
        
    def _is_dark_theme(self) -> bool:
        """Check if current theme is a dark theme"""
        # First try to get from app's current_theme attribute
        if hasattr(self.app, 'current_theme'):
            current_theme = self.app.current_theme
        else:
            # Fallback to settings
            from settings import SETTINGS
            current_theme = SETTINGS.get("theme", "flatly")
        
        # Define dark themes list
        dark_themes = ["darkly", "solar", "cyborg", "superhero"]
        return current_theme in dark_themes
        
    def _update_label_colors(self, is_dark: bool):
        """Update label colors based on theme"""
        if is_dark:
            label_fg = "#6c757d"  # Muted color for dark theme
        else:
            label_fg = "#6c757d"  # Same muted color works for light theme
            
        # Update context indicator
        if self.context_indicator:
            self.context_indicator.config(foreground=label_fg)
            
        # Update character counter (unless it's showing a warning color)
        if self.char_counter:
            current_color = self.char_counter.cget('foreground')
            if current_color not in ['orange', 'red']:  # Don't override warning colors
                self.char_counter.config(foreground=label_fg)
        
    def _bind_events(self):
        """Bind keyboard and other events"""
        # Input text events
        self.input_text.bind("<KeyRelease>", self._on_key_release)
        self.input_text.bind("<Control-Return>", lambda e: self.send_message())
        self.input_text.bind("<Escape>", lambda e: self.clear_input())
        
        # Auto-resize as user types
        self.input_text.bind("<KeyPress>", self._auto_resize_input)
        
        # Update char counter
        self.input_text.bind("<<Modified>>", self._update_char_counter)
        
    def _on_key_release(self, event):
        """Handle key release events"""
        # Update character counter
        self._update_char_counter()
        
    def _auto_resize_input(self, event=None):
        """Auto-resize input text widget based on content"""
        # Count lines
        content = self.input_text.get("1.0", tk.END)
        lines = content.count('\n') + 1
        
        # Adjust height within limits
        new_height = max(self.min_input_lines, min(lines, self.max_input_lines))
        current_height = int(self.input_text.cget("height"))
        
        if new_height != current_height:
            self.input_text.config(height=new_height)
            
    def _update_char_counter(self, event=None):
        """Update the character counter"""
        content = self.input_text.get("1.0", tk.END).strip()
        char_count = len(content)
        
        # Update counter text
        self.char_counter.config(text=f"{char_count}/{self.max_input_length}")
        
        # Change color if approaching limit
        if char_count > self.max_input_length * 0.9:
            self.char_counter.config(foreground="orange")
        elif char_count > self.max_input_length:
            self.char_counter.config(foreground="red")
        else:
            # Use theme-appropriate color for normal state
            is_dark = self._is_dark_theme()
            normal_color = "#6c757d" if not is_dark else "#6c757d"
            self.char_counter.config(foreground=normal_color)
            
        # Reset modified flag
        self.input_text.edit_modified(False)
        
    def update_context_indicator(self):
        """Update the context indicator based on active tab"""
        if hasattr(self.app, 'notebook') and self.app.notebook:
            tab_index = self.app.notebook.index("current")
            tab_names = ["Transcript", "SOAP Note", "Referral", "Letter"]
            
            if 0 <= tab_index < len(tab_names):
                self.context_indicator.config(text=f"Context: {tab_names[tab_index]}")
            else:
                self.context_indicator.config(text="Context: Unknown")
                
    def set_suggestions(self, suggestions: list):
        """Set quick action suggestions based on context"""
        # Clear existing suggestions
        for widget in self.suggestions_frame.winfo_children():
            widget.destroy()
            
        if not suggestions:
            return
            
        # Create scrollable frame if we have many suggestions
        if len(suggestions) > 6:
            # Create canvas and scrollbar for horizontal scrolling
            canvas = tk.Canvas(self.suggestions_frame, height=35, highlightthickness=0)
            scrollbar = ttk.Scrollbar(self.suggestions_frame, orient="horizontal", command=canvas.xview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(xscrollcommand=scrollbar.set)
            
            canvas.pack(side="top", fill="x", expand=True)
            scrollbar.pack(side="bottom", fill="x")
            
            parent_frame = scrollable_frame
        else:
            parent_frame = self.suggestions_frame
            
        # Add suggestion buttons (limit to 6 to avoid UI clutter)
        for i, suggestion in enumerate(suggestions[:6]):
            # Truncate long suggestions for button display
            display_text = suggestion[:30] + "..." if len(suggestion) > 30 else suggestion
            
            btn = ttk.Button(
                parent_frame,
                text=display_text,
                command=lambda s=suggestion: self.use_suggestion(s),
                bootstyle="info-link"
            )
            btn.pack(side=tk.LEFT, padx=(0, 5))
            
            # Add tooltip for full text if truncated
            if len(suggestion) > 30:
                ToolTip(btn, suggestion)
            
    def use_suggestion(self, suggestion: str):
        """Use a suggestion as input"""
        self.input_text.delete("1.0", tk.END)
        self.input_text.insert("1.0", suggestion)
        self.input_text.focus_set()
        
    def _show_suggestions_manager(self):
        """Show the custom suggestions management dialog"""
        try:
            from dialogs import show_custom_suggestions_dialog
            # Get the top-level window
            top_level = self.parent_frame.winfo_toplevel()
            show_custom_suggestions_dialog(top_level)
            
            # Refresh suggestions after dialog closes
            if hasattr(self.app, '_update_chat_suggestions'):
                self.app._update_chat_suggestions()
        except Exception as e:
            import logging
            logging.error(f"Error showing suggestions manager: {e}")
            import tkinter.messagebox
            tkinter.messagebox.showerror("Error", f"Failed to open suggestions manager: {str(e)}")
        
    def send_message(self):
        """Send the current message"""
        if self.is_processing:
            return
            
        content = self.input_text.get("1.0", tk.END).strip()
        
        if not content:
            return
            
        # Check length
        if len(content) > self.max_input_length:
            self.app.status_manager.warning(
                f"Message too long. Maximum {self.max_input_length} characters."
            )
            return
            
        # Call the callback if set
        if self.on_send_callback:
            self.set_processing(True)
            self.on_send_callback(content)
            
    def clear_input(self):
        """Clear the input field"""
        self.input_text.delete("1.0", tk.END)
        self._update_char_counter()
        self.input_text.focus_set()
        
    def set_processing(self, processing: bool):
        """Set the processing state"""
        self.is_processing = processing
        
        if processing:
            self.send_button.config(state=tk.DISABLED, text="Processing...")
            self.clear_button.config(state=tk.DISABLED)
            self.input_text.config(state=tk.DISABLED)
        else:
            self.send_button.config(state=tk.NORMAL, text="Send")
            self.clear_button.config(state=tk.NORMAL)
            self.input_text.config(state=tk.NORMAL)
            # Clear input after successful send
            self.clear_input()
            
    def set_send_callback(self, callback: Callable[[str], None]):
        """Set the callback for when send is clicked"""
        self.on_send_callback = callback
        
    def focus_input(self):
        """Focus the input text widget"""
        self.input_text.focus_set()
        
    def update_theme(self):
        """Update styling when theme changes"""
        self._apply_text_styling()
        
        # Update the chat frame border color based on theme
        is_dark = self._is_dark_theme()
        
        # Update the LabelFrame styling
        if self.chat_frame:
            if is_dark:
                # Dark theme styling for the frame
                self.chat_frame.configure(style="Dark.TLabelframe")
                # Try to configure the dark style if it doesn't exist
                try:
                    style = ttk.Style()
                    style.configure("Dark.TLabelframe", 
                                  background="#212529",
                                  foreground="#f8f9fa",
                                  bordercolor="#495057")
                    style.configure("Dark.TLabelframe.Label",
                                  background="#212529", 
                                  foreground="#f8f9fa")
                except:
                    pass
            else:
                # Light theme styling
                self.chat_frame.configure(style="TLabelframe")
                
        # Update scrollbar styling
        if hasattr(self, 'input_text') and self.input_text:
            # Find the scrollbar
            for widget in self.input_text.master.winfo_children():
                if isinstance(widget, ttk.Scrollbar):
                    # Scrollbar will automatically inherit theme colors
                    widget.update()
                    break
    
    def _toggle_collapse(self):
        """Toggle the collapse state of the chat interface"""
        if self._collapsed:
            # Expand
            self.content_frame.pack(fill=tk.BOTH, expand=True)
            self.collapse_btn.config(text="^")
            self._collapsed = False
        else:
            # Collapse
            self.content_frame.pack_forget()
            self.collapse_btn.config(text="v")
            self._collapsed = True