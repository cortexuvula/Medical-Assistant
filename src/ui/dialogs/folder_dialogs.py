"""
Folder Dialog Manager Module

Handles storage folder selection through a custom dialog that avoids
native file dialogs to prevent UI freezing issues.
"""

import os
from ui.scaling_utils import ui_scaler
import logging
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk


class FolderDialogManager:
    """Manages custom folder selection dialogs."""
    
    def __init__(self, parent_app):
        """Initialize the folder dialog manager.
        
        Args:
            parent_app: The main application instance
        """
        self.app = parent_app
        
    def show_storage_folder_dialog(self) -> None:
        """
        Show a custom folder selection dialog for setting the storage folder.
        Avoids native file dialogs entirely to prevent UI freezing.
        """
        logging.info("STORAGE: Opening custom folder selection dialog")
        
        # Create a custom folder selection dialog
        dialog = tk.Toplevel(self.app)
        dialog.title("Select Storage Folder")
        dialog_width, dialog_height = ui_scaler.get_dialog_size(600, 500)
        dialog.geometry(f"{dialog_width}x{dialog_height}")
        dialog.transient(self.app)
        dialog.grab_set()
        
        # Center the dialog on the parent window
        x = self.app.winfo_x() + (self.app.winfo_width() // 2) - (600 // 2)
        y = self.app.winfo_y() + (self.app.winfo_height() // 2) - (500 // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Create main frame with padding
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Get current storage folder from settings
        from settings.settings import SETTINGS
        current_storage = SETTINGS.get("storage_folder", "") or SETTINGS.get("default_storage_folder", "")
        
        # Add current folder display
        if current_storage and os.path.exists(current_storage):
            current_frame = ttk.LabelFrame(main_frame, text="Current Storage Folder", padding="10")
            current_frame.pack(fill=tk.X, pady=(0, 10))
            
            current_label = ttk.Label(current_frame, text=current_storage, 
                                    font=("Segoe UI", 10, "bold"), 
                                    foreground="green")
            current_label.pack(anchor="w")
        else:
            # Show warning if no valid folder is set
            warning_frame = ttk.LabelFrame(main_frame, text="Current Storage Folder", padding="10")
            warning_frame.pack(fill=tk.X, pady=(0, 10))
            
            warning_label = ttk.Label(warning_frame, 
                                    text="No storage folder currently set" if not current_storage 
                                    else f"Invalid folder: {current_storage}",
                                    font=("Segoe UI", 10), 
                                    foreground="red")
            warning_label.pack(anchor="w")
        
        # Add explanation label
        ttk.Label(main_frame, text="Select a new folder for storing recordings and exports", 
                 wraplength=580).pack(pady=(0, 10))
        
        # Create a frame for the path entry and navigation
        path_frame = ttk.Frame(main_frame)
        path_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Current path display - start with current storage folder if valid, otherwise home directory
        initial_path = current_storage if current_storage and os.path.exists(current_storage) else os.path.expanduser("~")
        path_var = tk.StringVar(value=initial_path)
        path_entry = ttk.Entry(path_frame, textvariable=path_var, width=50)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # Use a simple default rather than dealing with file dialogs
        def use_default_location():
            """Set the path to the default storage location."""
            # Use the 'storage' directory in the application folder
            app_dir = os.path.dirname(os.path.abspath(__file__))
            default_storage = os.path.join(app_dir, "storage")
            
            # Create the directory if it doesn't exist
            try:
                os.makedirs(default_storage, exist_ok=True)
                path_var.set(default_storage)
                refresh_file_list()
                logging.info(f"STORAGE: Using default location: {default_storage}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not create default storage folder: {e}")
                logging.error(f"STORAGE: Error creating default folder: {str(e)}", exc_info=True)
        
        # Button for default location
        default_btn = ttk.Button(path_frame, text="Use Default", command=use_default_location)
        default_btn.pack(side=tk.RIGHT)
        
        # Frame for directory listing with scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Create scrollbar and listbox for directories
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        dir_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=("Segoe UI", 10))
        dir_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=dir_listbox.yview)
        
        # Status bar variable
        status_var = tk.StringVar()
        
        # Function to refresh the directory listing
        def refresh_file_list():
            """Refresh the directory listing in the listbox."""
            current_path = path_var.get()
            if not os.path.exists(current_path):
                # If path doesn't exist, try to fall back to user's home directory
                current_path = os.path.expanduser("~")
                path_var.set(current_path)
            
            # Clear the listbox
            dir_listbox.delete(0, tk.END)
            
            # Add parent directory option if not at root
            if os.path.abspath(current_path) != os.path.abspath(os.path.dirname(current_path)):
                dir_listbox.insert(tk.END, "..")
            
            try:
                # List directories only
                dirs = [d for d in os.listdir(current_path) 
                       if os.path.isdir(os.path.join(current_path, d))]
                dirs.sort()
                
                for d in dirs:
                    dir_listbox.insert(tk.END, d)
                    
                status_var.set(f"Found {len(dirs)} directories")
            except Exception as e:
                status_var.set(f"Error: {str(e)}")
                logging.error(f"STORAGE: Error listing directories: {str(e)}", exc_info=True)
        
        # Handle double-click on directory
        def on_dir_double_click(_):
            """Handle double-click on directory entry."""
            selection = dir_listbox.curselection()
            if selection:
                item = dir_listbox.get(selection[0])
                current_path = path_var.get()
                
                if item == "..":
                    # Go up one directory
                    new_path = os.path.dirname(current_path)
                else:
                    # Enter selected directory
                    new_path = os.path.join(current_path, item)
                
                path_var.set(new_path)
                refresh_file_list()
        
        # Bind double-click event
        dir_listbox.bind("<Double-1>", on_dir_double_click)
        
        # Status bar
        status_bar = ttk.Label(main_frame, textvariable=status_var, anchor="w")
        status_bar.pack(fill=tk.X, pady=(5, 10))
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        # Function to set the selected folder
        def set_selected_folder():
            """Set the selected folder as the storage location."""
            selected_path = path_var.get()
            if os.path.exists(selected_path) and os.path.isdir(selected_path):
                try:
                    from settings.settings import SETTINGS, save_settings
                    
                    # Set both keys for backwards compatibility
                    SETTINGS["storage_folder"] = selected_path
                    SETTINGS["default_storage_folder"] = selected_path
                    save_settings(SETTINGS)
                    
                    self.app.status_manager.success(f"Storage folder set to: {selected_path}")
                    logging.info(f"STORAGE: Folder set to {selected_path}")
                    dialog.destroy()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to set folder: {e}")
                    logging.error(f"STORAGE: Error setting folder: {str(e)}", exc_info=True)
            else:
                messagebox.showerror("Invalid Directory", "The selected path is not a valid directory.")
        
        # Add Select and Cancel buttons
        select_btn = ttk.Button(button_frame, text="Select This Folder", command=set_selected_folder, style="primary.TButton")
        select_btn.pack(side=tk.LEFT, padx=(0, 5), fill=tk.X, expand=True)
        
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=dialog.destroy)
        cancel_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        
        # Initial directory listing
        refresh_file_list()