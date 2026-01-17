import tkinter as tk
import string
from typing import Optional, Dict, Callable, List
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class TextProcessor:
    """Handles text processing, manipulation, and command handling for voice recognition"""
    
    def __init__(self):
        self.capitalize_next = False
        self.text_chunks = []
        
    def append_text_to_widget(self, text: str, widget: tk.Widget) -> None:
        """Append text to a text widget with smart whitespace handling.
        
        Args:
            text: Text to append
            widget: Text widget to append to
        """
        if not text.strip():
            return
            
        current = widget.get("1.0", "end-1c")
        
        # Auto-capitalize if needed
        if (self.capitalize_next or not current or current[-1] in ".!?") and text:
            text = text[0].upper() + text[1:]
            self.capitalize_next = False
            
        # Add space if needed
        if current and current[-1] not in " \n":
            text = " " + text
            
        widget.insert(tk.END, text)
        widget.see(tk.END)
        
    def handle_text_command(self, command: str, active_widget: tk.Widget) -> bool:
        """Process text commands like 'new paragraph', 'full stop', etc.
        
        Args:
            command: Command to process
            active_widget: Current active text widget
            
        Returns:
            bool: True if command was handled, False otherwise
        """
        # Common voice commands
        commands = {
            "new paragraph": lambda: active_widget.insert(tk.END, "\n\n"),
            "new line": lambda: active_widget.insert(tk.END, "\n"),
            "full stop": lambda: self._insert_with_capitalize(active_widget, ". "),
            "comma": lambda: active_widget.insert(tk.END, ", "),
            "question mark": lambda: active_widget.insert(tk.END, "? "),
            "exclamation point": lambda: active_widget.insert(tk.END, "! "),
            "semicolon": lambda: active_widget.insert(tk.END, "; "),
            "colon": lambda: active_widget.insert(tk.END, ": "),
            "open quote": lambda: active_widget.insert(tk.END, "\""),
            "close quote": lambda: active_widget.insert(tk.END, "\""),
            "open parenthesis": lambda: active_widget.insert(tk.END, "("),
            "close parenthesis": lambda: active_widget.insert(tk.END, ")"),
        }
        
        if command in commands:
            commands[command]()
            return True
            
        return False
        
    def _insert_with_capitalize(self, widget: tk.Widget, text: str) -> None:
        """Insert text and mark that next character should be capitalized."""
        widget.insert(tk.END, text)
        self.capitalize_next = True
        
    def delete_last_word(self, widget: tk.Widget) -> None:
        """Delete the last word in the text widget.
        
        Args:
            widget: Text widget to modify
        """
        current = widget.get("1.0", "end-1c")
        if current:
            words = current.split()
            if words:
                widget.delete("1.0", tk.END)
                widget.insert(tk.END, " ".join(words[:-1]))
                widget.see(tk.END)
                
    def clean_command_text(self, text: str) -> str:
        """Clean up text to use as command detection.
        
        Args:
            text: Raw text to clean
            
        Returns:
            Cleaned text suitable for command detection
        """
        return text.lower().strip().translate(str.maketrans('', '', string.punctuation))
