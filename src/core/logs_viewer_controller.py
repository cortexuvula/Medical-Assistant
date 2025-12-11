"""
Logs Viewer Controller Module

Handles log viewing, log directory access, and log file display functionality.

This controller extracts logs viewer logic from the main App class
to improve maintainability and separation of concerns.
"""

import os
import logging
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.app import MedicalDictationApp

logger = logging.getLogger(__name__)


class LogsViewerController:
    """Controller for managing log viewing functionality.

    This class coordinates:
    - Viewing logs via popup menu
    - Displaying log contents in a window
    - Opening the logs folder in file explorer
    """

    def __init__(self, app: 'MedicalDictationApp'):
        """Initialize the logs viewer controller.

        Args:
            app: Reference to the main application instance
        """
        self.app = app

    def view_logs(self) -> None:
        """Open the logs directory in file explorer or view log contents."""
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        log_file = os.path.join(log_dir, "medical_dictation.log")

        if not os.path.exists(log_dir):
            messagebox.showinfo(
                "Logs",
                "The logs directory does not exist yet. It will be created when logs are generated."
            )
            return

        # Log that logs are being viewed
        logging.info("User accessed logs directory")

        # Create a dropdown menu for log actions
        log_menu = tk.Menu(self.app, tearoff=0)
        log_menu.add_command(label="Open Logs Folder", command=lambda: self.open_logs_folder(log_dir))
        log_menu.add_command(label="View Log Contents", command=lambda: self.show_log_contents(log_file))

        # Get the position of the mouse
        try:
            x = self.app.winfo_pointerx()
            y = self.app.winfo_pointery()
            log_menu.tk_popup(x, y)
        finally:
            # Make sure to release the grab
            log_menu.grab_release()

    def show_log_contents(self, log_file: str) -> None:
        """Show the contents of the log file in a new window.

        Args:
            log_file: Path to the log file to display
        """
        try:
            if os.path.exists(log_file):
                # Create a new top-level window
                log_window = tk.Toplevel(self.app)
                log_window.title("Log Contents")
                log_window.geometry("800x600")

                # Create text widget with scrollbar
                frame = ttk.Frame(log_window)
                frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

                text_widget = tk.Text(frame, wrap=tk.WORD)
                scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text_widget.yview)
                text_widget.configure(yscrollcommand=scrollbar.set)

                text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                # Read and display log contents
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    text_widget.insert('1.0', content)
                    text_widget.config(state=tk.DISABLED)  # Make read-only

                # Add close button
                close_btn = ttk.Button(log_window, text="Close", command=log_window.destroy)
                close_btn.pack(pady=5)
            else:
                messagebox.showwarning("File Not Found", "Log file not found.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open log file: {str(e)}")

    def open_logs_folder(self, log_dir: str) -> None:
        """Open the logs directory using file explorer.

        Args:
            log_dir: Path to the logs directory
        """
        try:
            from utils.validation import open_file_or_folder_safely
            success, error = open_file_or_folder_safely(log_dir, operation="open")
            if not success:
                messagebox.showerror("Error", f"Could not open logs directory: {error}")
                logging.error(f"Error opening logs directory: {error}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open logs directory: {str(e)}")
            logging.error(f"Error opening logs directory: {str(e)}")

    def open_logs_folder_menu(self) -> None:
        """Wrapper method for menu to open logs folder."""
        from managers.data_folder_manager import data_folder_manager
        log_dir = str(data_folder_manager.logs_folder)
        if not os.path.exists(log_dir):
            messagebox.showinfo(
                "Logs",
                "The logs directory does not exist yet. It will be created when logs are generated."
            )
            return
        logging.info("User accessed logs directory from menu")
        self.open_logs_folder(log_dir)

    def show_log_contents_menu(self) -> None:
        """Wrapper method for menu to show log contents."""
        from managers.data_folder_manager import data_folder_manager
        log_dir = str(data_folder_manager.logs_folder)
        log_file = os.path.join(log_dir, "medical_dictation.log")
        if not os.path.exists(log_dir):
            messagebox.showinfo(
                "Logs",
                "The logs directory does not exist yet. It will be created when logs are generated."
            )
            return
        logging.info("User viewed log contents from menu")
        self.show_log_contents(log_file)
