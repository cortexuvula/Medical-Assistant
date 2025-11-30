"""
Auto-save Manager for Medical Assistant

Handles automatic saving of work to prevent data loss, including transcripts,
generated documents, and application state.
"""

import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Callable
import hashlib
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import io


class AutoSaveManager:
    """Manages automatic saving of application data.

    Thread Safety:
        This class is designed to be thread-safe. The data_providers dict
        is protected by _providers_lock, and the save state is protected
        by _state_lock. Both can be held simultaneously but must be acquired
        in the order: _providers_lock first, then _state_lock.
    """

    def __init__(self,
                 save_directory: Optional[Path] = None,
                 interval_seconds: int = 300,  # 5 minutes default
                 max_backups: int = 3):
        """
        Initialize the auto-save manager.

        Args:
            save_directory: Directory to store auto-save files
            interval_seconds: Time between auto-saves in seconds
            max_backups: Maximum number of backup files to keep
        """
        # Set up save directory
        if save_directory is None:
            from managers.data_folder_manager import data_folder_manager
            self.save_directory = data_folder_manager.app_data_folder / "autosave"
        else:
            self.save_directory = Path(save_directory)

        self.save_directory.mkdir(parents=True, exist_ok=True)

        self.interval_seconds = interval_seconds
        self.max_backups = max_backups

        # Thread synchronization - use RLock to allow recursive acquisition
        self._providers_lock = threading.RLock()  # Protects data_providers dict
        self._state_lock = threading.RLock()  # Protects save state
        self._stop_event = threading.Event()  # For clean shutdown

        # Protected by _state_lock
        self._is_running = False
        self.save_thread: Optional[threading.Thread] = None
        self.last_save_time: Optional[datetime] = None
        self.last_data_hash: Optional[str] = None

        # Protected by _providers_lock
        self._data_providers: Dict[str, Callable[[], Dict[str, Any]]] = {}

        # Callbacks (set from main thread, called from background thread)
        self.on_save_start: Optional[Callable] = None
        self.on_save_complete: Optional[Callable] = None
        self.on_save_error: Optional[Callable[[Exception], None]] = None

        logging.info(f"AutoSaveManager initialized with {interval_seconds}s interval")

    @property
    def is_running(self) -> bool:
        """Thread-safe check if autosave is running."""
        with self._state_lock:
            return self._is_running

    @is_running.setter
    def is_running(self, value: bool):
        """Thread-safe setter for running state."""
        with self._state_lock:
            self._is_running = value

    @property
    def data_providers(self) -> Dict[str, Callable[[], Dict[str, Any]]]:
        """Thread-safe access to data providers (returns a copy)."""
        with self._providers_lock:
            return dict(self._data_providers)
    
    def register_data_provider(self, name: str, provider: Callable[[], Dict[str, Any]]):
        """
        Register a data provider function.

        Thread-safe: Can be called from any thread.

        Args:
            name: Name of the data provider
            provider: Function that returns data to save
        """
        with self._providers_lock:
            self._data_providers[name] = provider
        logging.debug(f"Registered data provider: {name}")

    def unregister_data_provider(self, name: str) -> bool:
        """
        Unregister a data provider function.

        Thread-safe: Can be called from any thread.

        Args:
            name: Name of the data provider to remove

        Returns:
            True if provider was removed, False if not found
        """
        with self._providers_lock:
            if name in self._data_providers:
                del self._data_providers[name]
                logging.debug(f"Unregistered data provider: {name}")
                return True
            return False

    def start(self):
        """Start the auto-save timer."""
        with self._state_lock:
            if self._is_running:
                logging.warning("AutoSave is already running")
                return

            self._is_running = True
            self._stop_event.clear()
            self.save_thread = threading.Thread(target=self._save_loop, daemon=True, name="AutoSaveThread")
            self.save_thread.start()
        logging.info("AutoSave started")

    def stop(self):
        """Stop the auto-save timer gracefully."""
        with self._state_lock:
            if not self._is_running:
                return
            self._is_running = False
            self._stop_event.set()  # Signal thread to wake up and exit

        # Wait outside lock to avoid deadlock
        if self.save_thread and self.save_thread.is_alive():
            self.save_thread.join(timeout=5)
            if self.save_thread.is_alive():
                logging.warning("AutoSave thread did not terminate cleanly")

        logging.info("AutoSave stopped")

    def _save_loop(self):
        """Main auto-save loop running in background thread."""
        while not self._stop_event.is_set():
            try:
                # Wait for the interval or until stop is signaled
                # Using Event.wait() instead of time.sleep() allows faster shutdown
                if self._stop_event.wait(timeout=self.interval_seconds):
                    # Stop event was set, exit loop
                    break

                if self.is_running:  # Check again after wait
                    self.perform_save()

            except Exception as e:
                logging.error(f"Error in auto-save loop: {e}", exc_info=True)
                if self.on_save_error:
                    try:
                        self.on_save_error(e)
                    except Exception as callback_error:
                        logging.error(f"Error in save error callback: {callback_error}")
    
    def perform_save(self, force: bool = False) -> bool:
        """
        Perform an auto-save.

        Thread-safe: Can be called from any thread.

        Args:
            force: Force save even if data hasn't changed

        Returns:
            True if save was performed, False if skipped
        """
        try:
            # Collect data from all providers (thread-safe copy)
            save_data = {
                "timestamp": datetime.now().isoformat(),
                "version": "1.0",
                "data": {}
            }

            # Get a thread-safe snapshot of providers
            with self._providers_lock:
                providers_snapshot = dict(self._data_providers)

            # Call providers outside lock to avoid holding lock during callbacks
            for name, provider in providers_snapshot.items():
                try:
                    save_data["data"][name] = provider()
                except Exception as e:
                    logging.error(f"Error getting data from provider {name}: {e}")
                    save_data["data"][name] = None

            # Calculate hash to detect changes
            data_str = json.dumps(save_data["data"], sort_keys=True, default=str)
            current_hash = hashlib.md5(data_str.encode()).hexdigest()

            # Check last hash (thread-safe)
            with self._state_lock:
                if not force and current_hash == self.last_data_hash:
                    logging.debug("No changes detected, skipping auto-save")
                    return False

            # Notify save start (outside lock)
            if self.on_save_start:
                try:
                    self.on_save_start()
                except Exception as e:
                    logging.error(f"Error in save start callback: {e}")

            # Rotate existing backups
            self._rotate_backups()

            # Save to file using buffered I/O for better performance
            # First serialize to memory buffer, then write in one operation
            save_path = self.save_directory / "autosave_current.json"
            temp_path = save_path.with_suffix(".tmp")

            # Serialize JSON to memory first (reduces file handle time)
            json_bytes = json.dumps(save_data, indent=2, default=str).encode('utf-8')

            # Write using a single buffered operation
            with open(temp_path, 'wb', buffering=65536) as f:  # 64KB buffer
                f.write(json_bytes)
                f.flush()
                os.fsync(f.fileno())  # Ensure data is on disk before rename

            # Atomic rename
            temp_path.replace(save_path)

            # Update state (thread-safe)
            with self._state_lock:
                self.last_save_time = datetime.now()
                self.last_data_hash = current_hash

            # Notify save complete (outside lock)
            if self.on_save_complete:
                try:
                    self.on_save_complete()
                except Exception as e:
                    logging.error(f"Error in save complete callback: {e}")

            logging.info("Auto-save completed successfully")
            return True

        except Exception as e:
            logging.error(f"Failed to perform auto-save: {e}", exc_info=True)
            if self.on_save_error:
                try:
                    self.on_save_error(e)
                except Exception as callback_error:
                    logging.error(f"Error in save error callback: {callback_error}")
            return False
    
    def _rotate_backups(self):
        """Rotate backup files to maintain max_backups limit."""
        current_file = self.save_directory / "autosave_current.json"
        
        if not current_file.exists():
            return
        
        # Rotate existing backups
        for i in range(self.max_backups - 1, 0, -1):
            old_backup = self.save_directory / f"autosave_backup_{i}.json"
            new_backup = self.save_directory / f"autosave_backup_{i + 1}.json"
            
            if old_backup.exists():
                if i + 1 <= self.max_backups:
                    # On Windows, rename fails if destination exists, so remove it first
                    if new_backup.exists():
                        new_backup.unlink()
                    old_backup.rename(new_backup)
                else:
                    old_backup.unlink()  # Delete oldest backup
        
        # Move current to backup_1
        backup_1 = self.save_directory / "autosave_backup_1.json"
        # On Windows, rename fails if destination exists, so remove it first
        if backup_1.exists():
            backup_1.unlink()
        current_file.rename(backup_1)
    
    def load_latest(self) -> Optional[Dict[str, Any]]:
        """
        Load the most recent auto-save data.
        
        Returns:
            Saved data dictionary or None if no saves exist
        """
        save_files = [
            "autosave_current.json",
            "autosave_backup_1.json",
            "autosave_backup_2.json",
            "autosave_backup_3.json"
        ]
        
        for filename in save_files:
            save_path = self.save_directory / filename
            if save_path.exists():
                try:
                    with open(save_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    logging.info(f"Loaded auto-save from {filename}")
                    return data
                except Exception as e:
                    logging.error(f"Failed to load {filename}: {e}")
                    continue
        
        return None
    
    def has_unsaved_data(self) -> bool:
        """Check if there is auto-saved data available."""
        current_file = self.save_directory / "autosave_current.json"
        return current_file.exists()
    
    def clear_saves(self):
        """Clear all auto-save files."""
        for file in self.save_directory.glob("autosave_*.json"):
            try:
                file.unlink()
            except Exception as e:
                logging.error(f"Failed to delete {file}: {e}")
        
        self.last_data_hash = None
        logging.info("Cleared all auto-save files")
    
    def get_save_info(self) -> Dict[str, Any]:
        """Get information about current auto-saves."""
        info = {
            "last_save_time": self.last_save_time.isoformat() if self.last_save_time else None,
            "is_running": self.is_running,
            "interval_seconds": self.interval_seconds,
            "saves": []
        }
        
        for file in sorted(self.save_directory.glob("autosave_*.json")):
            try:
                stat = file.stat()
                with open(file, 'r') as f:
                    data = json.load(f)
                
                info["saves"].append({
                    "filename": file.name,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "timestamp": data.get("timestamp")
                })
            except Exception as e:
                logging.error(f"Error reading save info for {file}: {e}")
        
        return info


class AutoSaveDataProvider:
    """Helper class for creating data providers for auto-save."""
    
    @staticmethod
    def create_text_widget_provider(widget, name: str) -> Callable[[], Dict[str, Any]]:
        """Create a provider for a text widget."""
        def provider():
            try:
                return {
                    "name": name,
                    "content": widget.get("1.0", "end-1c"),
                    "cursor_position": widget.index("insert")
                }
            except (tk.TclError, AttributeError, RuntimeError):
                # Widget may be destroyed or not initialized
                return {"name": name, "content": "", "cursor_position": "1.0"}
        
        return provider
    
    @staticmethod
    def create_recording_state_provider(app) -> Callable[[], Dict[str, Any]]:
        """Create a provider for recording state."""
        def provider():
            return {
                "is_recording": getattr(app, 'soap_recording', False),
                "recording_paused": getattr(app, 'soap_recording_paused', False),
                "current_recording_id": getattr(app, 'current_recording_id', None),
                "recording_start_time": getattr(app, 'recording_start_time', None)
            }
        
        return provider
    
    @staticmethod  
    def create_settings_provider(settings_dict) -> Callable[[], Dict[str, Any]]:
        """Create a provider for application settings."""
        def provider():
            # Only save non-sensitive settings
            safe_settings = {k: v for k, v in settings_dict.items() 
                           if not any(sensitive in k.lower() 
                                    for sensitive in ['key', 'password', 'secret', 'token'])}
            return safe_settings
        
        return provider