"""
Theme Manager Module

Handles theme switching and UI styling management including light/dark mode
toggles, color updates, and component styling.
"""

import tkinter as tk
import ttkbootstrap as ttk
from utils.structured_logging import get_logger
from settings.settings import SETTINGS, save_settings
from ui.ui_constants import Colors, Icons
from ui.theme_observer import notify_theme_change

logger = get_logger(__name__)


class ThemeManager:
    """Manages application theme switching and styling."""
    
    def __init__(self, parent_app):
        """Initialize the theme manager.
        
        Args:
            parent_app: The main application instance
        """
        self.app = parent_app
        
        # Define light and dark theme pairs
        self.theme_pairs = {
            # Light themes
            "flatly": "darkly",
            "cosmo": "solar",
            "yeti": "cyborg",
            "minty": "superhero",
            # Dark themes
            "darkly": "flatly",
            "solar": "cosmo",
            "cyborg": "yeti",
            "superhero": "minty"
        }
        
        # Define dark themes list
        self.dark_themes = ["darkly", "solar", "cyborg", "superhero"]
        
    def toggle_theme(self):
        """Toggle between light and dark themes."""
        # Get the paired theme for the current theme
        new_theme = self.theme_pairs.get(self.app.current_theme, "flatly")
        
        # Apply the new theme - need to recreate the window to fully apply the theme
        try:
            self.app.style.theme_use(new_theme)
        except tk.TclError as e:
            # Catch and log the error instead of crashing
            if "Duplicate element" in str(e):
                logger.info(f"Ignoring harmless duplicate element error during theme change: {e}")
            else:
                # Re-raise if it's not the specific error we're handling
                raise
        
        self.app.current_theme = new_theme
        
        # Update settings
        SETTINGS["theme"] = new_theme
        save_settings(SETTINGS)
        
        # Check if the NEW theme is dark (not the current theme which has just been switched)
        is_dark = new_theme in self.dark_themes
        mode_name = "Dark" if is_dark else "Light"
        self.app.status_manager.info(f"Switched to {mode_name} Mode ({new_theme})")
        
        # Update all UI components for the new theme
        self._update_text_widgets(is_dark)
        self._update_frames_and_controls(is_dark)
        self._update_notebook_style(is_dark)
        self._update_theme_button(is_dark, new_theme)
        self._update_refresh_buttons(is_dark)
        self._update_chat_ui(is_dark)
        self._update_sidebar(is_dark)

        # Update menu styling for new theme
        if hasattr(self.app, 'menu_manager') and self.app.menu_manager:
            self.app.menu_manager.update_menu_theme()

        # Broadcast theme change to all registered observers
        notify_theme_change(is_dark)

        # Update shortcut label in status bar to show theme toggle shortcut
        self.app.status_manager.info("Theme toggle shortcut: Alt+T")
        
    def _update_text_widgets(self, is_dark: bool):
        """Update text widgets background and foreground colors based on theme."""
        colors = Colors.get_theme_colors(is_dark)
        text_bg = colors["bg"]
        text_fg = colors["fg"]
        
        # Update all main text widgets with new colors
        text_widgets = [self.app.transcript_text, self.app.soap_text, self.app.referral_text]
        
        # Add letter text widget if it exists
        if hasattr(self.app, 'letter_text') and self.app.letter_text:
            text_widgets.append(self.app.letter_text)
            
        # Add context text widget if it exists
        if hasattr(self.app, 'context_text') and self.app.context_text:
            text_widgets.append(self.app.context_text)
        
        for widget in text_widgets:
            if widget:  # Check widget exists
                widget.config(bg=text_bg, fg=text_fg, insertbackground=text_fg)
    
    def _update_frames_and_controls(self, is_dark: bool):
        """Update control panel backgrounds and button frames."""
        colors = Colors.get_theme_colors(is_dark)
        control_bg = colors["bg_secondary"]
        
        # Update control panel backgrounds - handle tk vs ttk frames differently
        for frame in self.app.winfo_children():
            if isinstance(frame, tk.Frame):  # Only standard tk frames support 'background'
                frame.configure(background=control_bg)
                
        # Update all button frames specifically - handle tk vs ttk frames differently
        for _, btn in self.app.buttons.items():
            if btn is None:
                continue
            btn_frame = btn.master
            if isinstance(btn_frame, tk.Frame):  # Only standard tk frames support 'background'
                btn_frame.configure(background=control_bg)
        
        # Set specific components that need explicit styling
        if hasattr(self.app, 'control_frame') and isinstance(self.app.control_frame, tk.Frame):
            self.app.control_frame.configure(background=control_bg)

        # Update context panel search entry for theme
        if hasattr(self.app, 'ui') and hasattr(self.app.ui, 'components'):
            search_entry = self.app.ui.components.get('context_search_entry')
            if search_entry:
                entry_bg = colors["bg"] if is_dark else "#ffffff"
                entry_fg = colors["fg"]
                entry_muted = colors["fg_muted"] if "fg_muted" in colors else "#6c757d"
                search_entry.configure(bg=entry_bg, fg=entry_fg, insertbackground=entry_fg)

            # Update templates canvas background for theme
            context_panel = self.app.ui.context_panel
            if hasattr(context_panel, '_templates_canvas'):
                canvas_bg = colors["bg"]
                context_panel._templates_canvas.configure(bg=canvas_bg)
                # Also update the inner frame background
                if hasattr(context_panel, 'templates_frame'):
                    context_panel.templates_frame.configure(bg=canvas_bg)
                # Update two-column layout backgrounds
                if hasattr(context_panel, '_left_column'):
                    context_panel._left_column.configure(bg=canvas_bg)
                if hasattr(context_panel, '_right_column'):
                    context_panel._right_column.configure(bg=canvas_bg)

    def _update_notebook_style(self, is_dark: bool):
        """Update notebook and general component styling."""
        colors = Colors.get_theme_colors(is_dark)

        if is_dark:
            # Dark mode styling
            self.app.style.configure("Green.TNotebook", background=colors["bg"])
            self.app.style.configure("Green.TNotebook.Tab", background=colors["bg_secondary"], foreground=colors["fg"])
            self.app.style.configure("TButton", foreground=colors["fg"])
            self.app.style.configure("TFrame", background=colors["bg"])
            self.app.style.configure("TLabel", foreground=colors["fg"])
        else:
            # Light mode styling - reset to defaults
            self.app.style.configure("Green.TNotebook", background=colors["bg"])
            self.app.style.configure("Green.TNotebook.Tab", background=colors["bg_tertiary"], foreground=colors["fg"])
            self.app.style.configure("TButton", foreground=colors["fg"])
            self.app.style.configure("TFrame", background=colors["bg_secondary"])
            self.app.style.configure("TLabel", foreground=colors["fg"])
    
    def _update_theme_button(self, is_dark: bool, new_theme: str):
        """Update theme button icon and tooltip if available."""
        if hasattr(self.app, 'theme_btn') and self.app.theme_btn:
            # Log the current state for debugging
            logging.debug(f"Updating theme button - is_dark: {is_dark}, theme: {new_theme}")

            # Update icon and text based on new theme
            icon = Icons.MOON if not is_dark else Icons.SUN
            self.app.theme_btn.config(text=f"{icon} Theme")
            
            # Also update bootstyle based on theme for better visibility
            button_style = "info" if not is_dark else "warning"
            self.app.theme_btn.configure(bootstyle=button_style)
            
            # Update tooltip - create new tooltip and destroy old one
            tooltip_text = "Switch to Dark Mode" if not is_dark else "Switch to Light Mode"
            if hasattr(self.app.theme_btn, '_tooltip'):
                if hasattr(self.app.theme_btn._tooltip, 'hidetip'):
                    self.app.theme_btn._tooltip.hidetip()  # Hide current tooltip if visible
                
                # Update tooltip text
                self.app.theme_btn._tooltip.text = tooltip_text
                logging.debug(f"Updated tooltip text to: {tooltip_text}")
        
        # Update the theme label if available
        if hasattr(self.app, 'theme_label') and self.app.theme_label:
            mode_text = "Light Mode" if not is_dark else "Dark Mode"
            self.app.theme_label.config(text=f"({mode_text})")
            logging.debug(f"Updated theme label to: ({mode_text})")
    
    def _update_refresh_buttons(self, is_dark: bool):
        """Configure refresh button style based on theme."""
        colors = Colors.get_theme_colors(is_dark)

        if is_dark:
            # Dark mode - button is already visible against dark background
            self.app.style.configure("Refresh.TButton", foreground=colors["fg"])
            self.app.style.map("Refresh.TButton",
                foreground=[("pressed", colors["fg"]), ("active", colors["fg"])],
                background=[("pressed", Colors.PRIMARY), ("active", Colors.PRIMARY)])

            # Find and update refresh button if it exists
            for widget in self.app.winfo_children():
                self._update_refresh_button_bootstyle(widget, "dark")
        else:
            # Light mode - make button text white for visibility
            self.app.style.configure("Refresh.TButton", foreground="white")
            self.app.style.map("Refresh.TButton",
                foreground=[("pressed", "white"), ("active", "white")],
                background=[("pressed", Colors.PRIMARY), ("active", Colors.PRIMARY)])

            # Find and update refresh button if it exists
            for widget in self.app.winfo_children():
                self._update_refresh_button_bootstyle(widget, "info")

    def _update_refresh_button_bootstyle(self, widget, style):
        """Update the bootstyle of a refresh button if found."""
        # Check if this is a ttk Button with our custom style
        if isinstance(widget, ttk.Button) and hasattr(widget, 'configure'):
            try:
                # Try to get the current widget style
                current_style = widget.cget('style')
                if current_style == "Refresh.TButton":
                    widget.configure(bootstyle=style)
            except (tk.TclError, AttributeError):
                pass  # Ignore errors if widget doesn't support style attribute
        
        # Search children for ttk widgets
        for child in widget.winfo_children():
            self._update_refresh_button_bootstyle(child, style)
            
    def _update_chat_ui(self, is_dark: bool):
        """Update chat UI components for theme changes."""
        if hasattr(self.app, 'chat_ui') and self.app.chat_ui:
            try:
                self.app.chat_ui.update_theme()
                logging.debug(f"Updated chat UI for {'dark' if is_dark else 'light'} theme")
            except Exception as e:
                logging.error(f"Error updating chat UI theme: {e}")

    def _update_sidebar(self, is_dark: bool):
        """Update sidebar colors for theme changes."""
        if hasattr(self.app, 'ui') and hasattr(self.app.ui, 'sidebar_navigation'):
            try:
                self.app.ui.sidebar_navigation.update_theme(is_dark)
                logging.debug(f"Updated sidebar for {'dark' if is_dark else 'light'} theme")
            except Exception as e:
                logging.error(f"Error updating sidebar theme: {e}")