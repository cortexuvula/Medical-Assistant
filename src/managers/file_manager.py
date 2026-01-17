"""
File Manager Module

Handles all file operations including saving/loading text files,
audio files, prompt exports/imports, and storage management.
"""

import os
import json
from datetime import datetime as dt
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
from tkinter import filedialog, messagebox
from pydub import AudioSegment

from settings.settings_manager import settings_manager
from utils.structured_logging import get_logger
from utils.error_handling import ErrorContext

logger = get_logger(__name__)


class FileManager:
    """Manages file operations for the application."""
    
    def __init__(self, default_folder: Optional[str] = None):
        """Initialize file manager.
        
        Args:
            default_folder: Default storage folder path
        """
        self.default_folder = default_folder or settings_manager.get("default_folder", "")
        
    def save_text_file(self, text: str, title: str = "Save Text File", 
                      default_extension: str = ".txt") -> Optional[str]:
        """Save text to a file.
        
        Args:
            text: Text content to save
            title: Dialog title
            default_extension: Default file extension
            
        Returns:
            Optional[str]: Saved file path or None if cancelled
        """
        try:
            # Generate default filename
            timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"transcription_{timestamp}{default_extension}"
            
            # Set initial directory
            initial_dir = self.default_folder if self.default_folder else os.getcwd()
            
            # Show save dialog
            file_path = filedialog.asksaveasfilename(
                title=title,
                initialdir=initial_dir,
                initialfile=default_filename,
                defaultextension=default_extension,
                filetypes=[
                    ("Text files", "*.txt"),
                    ("Markdown files", "*.md"),
                    ("All files", "*.*")
                ]
            )
            
            if file_path:
                # Save the file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(text)
                    
                logger.info(f"Text saved to: {file_path}")
                return file_path
                
        except Exception as e:
            logger.error(f"Failed to save text file: {e}")
            messagebox.showerror("Save Error", f"Failed to save file: {str(e)}")
            
        return None
    
    def load_audio_file(self, title: str = "Select Audio File") -> Optional[str]:
        """Load an audio file.
        
        Args:
            title: Dialog title
            
        Returns:
            Optional[str]: Selected file path or None if cancelled
        """
        try:
            # Set initial directory
            initial_dir = self.default_folder if self.default_folder else os.getcwd()
            
            # Show open dialog
            file_path = filedialog.askopenfilename(
                title=title,
                initialdir=initial_dir,
                filetypes=[
                    ("Audio files", "*.mp3 *.wav *.m4a *.flac *.ogg"),
                    ("MP3 files", "*.mp3"),
                    ("WAV files", "*.wav"),
                    ("All files", "*.*")
                ]
            )
            
            if file_path and os.path.exists(file_path):
                logger.info(f"Audio file loaded: {file_path}")
                return file_path
                
        except Exception as e:
            logger.error(f"Failed to load audio file: {e}")
            messagebox.showerror("Load Error", f"Failed to load file: {str(e)}")
            
        return None
    
    def save_audio_file(self, audio_data: AudioSegment, 
                       title: str = "Save Audio File") -> Optional[str]:
        """Save audio data to a file.
        
        Args:
            audio_data: Audio data to save
            title: Dialog title
            
        Returns:
            Optional[str]: Saved file path or None if cancelled
        """
        try:
            # Generate default filename
            timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"recording_{timestamp}.mp3"
            
            # Set initial directory
            initial_dir = self.default_folder if self.default_folder else os.getcwd()
            
            # Show save dialog
            file_path = filedialog.asksaveasfilename(
                title=title,
                initialdir=initial_dir,
                initialfile=default_filename,
                defaultextension=".mp3",
                filetypes=[
                    ("MP3 files", "*.mp3"),
                    ("WAV files", "*.wav"),
                    ("All files", "*.*")
                ]
            )
            
            if file_path:
                # Determine format from extension
                ext = os.path.splitext(file_path)[1].lower()
                format_map = {
                    '.mp3': 'mp3',
                    '.wav': 'wav',
                    '.ogg': 'ogg',
                    '.flac': 'flac'
                }
                audio_format = format_map.get(ext, 'mp3')
                
                # Save the audio file
                audio_data.export(file_path, format=audio_format)
                
                logger.info(f"Audio saved to: {file_path}")
                return file_path
                
        except Exception as e:
            logger.error(f"Failed to save audio file: {e}")
            messagebox.showerror("Save Error", f"Failed to save audio: {str(e)}")
            
        return None
    
    def export_prompts(self, title: str = "Export Prompts") -> bool:
        """Export prompts to a JSON file.
        
        Args:
            title: Dialog title
            
        Returns:
            bool: True if exported successfully
        """
        try:
            # Prepare prompts data from settings
            prompts_data = {}

            # Get refine settings
            refine_config = settings_manager.get_model_config("refine_text")
            prompts_data["refine"] = {
                "prompt": refine_config.get("prompt", ""),
                "temperature": refine_config.get("temperature", 0.1)
            }

            # Get improve settings
            improve_config = settings_manager.get_model_config("improve_text")
            prompts_data["improve"] = {
                "prompt": improve_config.get("prompt", ""),
                "temperature": improve_config.get("temperature", 0.3)
            }

            # Get SOAP settings
            soap_config = settings_manager.get_soap_config()
            prompts_data["soap"] = {
                "prompt": soap_config.get("system_message", ""),
                "temperature": soap_config.get("temperature", 0.2)
            }

            # Get referral settings
            referral_config = settings_manager.get_model_config("referral")
            prompts_data["referral"] = {
                "prompt": referral_config.get("prompt", ""),
                "temperature": referral_config.get("temperature", 0.3)
            }
            
            # Show save dialog
            file_path = filedialog.asksaveasfilename(
                title=title,
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            
            if file_path:
                # Save prompts
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(prompts_data, f, indent=2)
                    
                logger.info(f"Prompts exported to: {file_path}")
                messagebox.showinfo("Export Successful", "Prompts exported successfully!")
                return True
                
        except Exception as e:
            logger.error(f"Failed to export prompts: {e}")
            messagebox.showerror("Export Error", f"Failed to export prompts: {str(e)}")
            
        return False
    
    def import_prompts(self, title: str = "Import Prompts") -> bool:
        """Import prompts from a JSON file.
        
        Args:
            title: Dialog title
            
        Returns:
            bool: True if imported successfully
        """
        try:
            # Show open dialog
            file_path = filedialog.askopenfilename(
                title=title,
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            
            if file_path and os.path.exists(file_path):
                # Load prompts
                with open(file_path, 'r', encoding='utf-8') as f:
                    prompts_data = json.load(f)
                
                # Update settings
                for category, data in prompts_data.items():
                    if isinstance(data, dict):
                        if "prompt" in data:
                            settings_manager.set(f"{category}_prompt", data["prompt"], auto_save=False)
                        if "temperature" in data:
                            settings_manager.set(f"{category}_temperature", data["temperature"], auto_save=False)

                # Save settings
                settings_manager.save()
                
                logger.info(f"Prompts imported from: {file_path}")
                messagebox.showinfo("Import Successful", "Prompts imported successfully!")
                return True
                
        except Exception as e:
            logger.error(f"Failed to import prompts: {e}")
            messagebox.showerror("Import Error", f"Failed to import prompts: {str(e)}")
            
        return False
    
    def set_default_folder(self) -> Optional[str]:
        """Set the default storage folder.
        
        Returns:
            Optional[str]: Selected folder path or None if cancelled
        """
        try:
            # Show folder selection dialog
            folder_path = filedialog.askdirectory(
                title="Select Default Storage Folder",
                initialdir=self.default_folder if self.default_folder else os.getcwd()
            )
            
            if folder_path:
                # Update settings
                self.default_folder = folder_path
                settings_manager.set("default_folder", folder_path)
                
                logger.info(f"Default folder set to: {folder_path}")
                return folder_path
                
        except Exception as e:
            logger.error(f"Failed to set default folder: {e}")
            messagebox.showerror("Error", f"Failed to set folder: {str(e)}")
            
        return None
    
    def ensure_directories(self) -> None:
        """Ensure required directories exist."""
        directories = [
            "logs",
            "recordings",
            "exports"
        ]
        
        for directory in directories:
            dir_path = Path(directory)
            if not dir_path.exists():
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created directory: {directory}")
                except Exception as e:
                    logger.error(f"Failed to create directory {directory}: {e}")
    
    def get_recording_path(self, recording_type: str = "soap") -> str:
        """Get path for saving a recording.
        
        Args:
            recording_type: Type of recording (soap, audio, etc.)
            
        Returns:
            str: Full file path for the recording
        """
        # Ensure recordings directory exists
        recordings_dir = Path("recordings")
        recordings_dir.mkdir(exist_ok=True)
        
        # Generate filename
        timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{recording_type}_recording_{timestamp}.mp3"
        
        return str(recordings_dir / filename)