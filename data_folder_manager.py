"""
Data folder management for Medical Assistant application.
Centralizes all application data files into a proper folder structure.
"""
import os
import sys
from pathlib import Path
from typing import Optional


class DataFolderManager:
    """Manages the application data folder structure."""
    
    def __init__(self):
        self._app_data_folder: Optional[Path] = None
        self._init_data_folder()
    
    def _init_data_folder(self):
        """Initialize the data folder based on the running environment."""
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            app_dir = Path(sys.executable).parent
        else:
            # Running as script
            app_dir = Path(__file__).parent
        
        # Create AppData folder next to the executable/script
        self._app_data_folder = app_dir / "AppData"
        self._ensure_folders_exist()
    
    def _ensure_folders_exist(self):
        """Ensure all required folders exist."""
        # Create main AppData folder
        self._app_data_folder.mkdir(exist_ok=True)
        
        # Create subfolders
        (self._app_data_folder / "config").mkdir(exist_ok=True)
        (self._app_data_folder / "logs").mkdir(exist_ok=True)
        (self._app_data_folder / "data").mkdir(exist_ok=True)
    
    @property
    def app_data_folder(self) -> Path:
        """Get the main AppData folder path."""
        return self._app_data_folder
    
    @property
    def env_file_path(self) -> Path:
        """Get the .env file path."""
        return self._app_data_folder / ".env"
    
    @property
    def settings_file_path(self) -> Path:
        """Get the settings.json file path."""
        return self._app_data_folder / "settings.json"
    
    @property
    def database_file_path(self) -> Path:
        """Get the database file path."""
        return self._app_data_folder / "medical_assistant.db"
    
    @property
    def config_folder(self) -> Path:
        """Get the config folder path."""
        return self._app_data_folder / "config"
    
    @property
    def logs_folder(self) -> Path:
        """Get the logs folder path."""
        return self._app_data_folder / "logs"
    
    @property
    def data_folder(self) -> Path:
        """Get the general data folder path."""
        return self._app_data_folder / "data"
    
    def migrate_existing_files(self):
        """Migrate existing files to the new structure."""
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            old_dir = Path(sys.executable).parent
        else:
            # Running as script
            old_dir = Path(__file__).parent
        
        # Files to migrate
        files_to_migrate = [
            (".env", self.env_file_path),
            ("settings.json", self.settings_file_path),
            ("medical_assistant.db", self.database_file_path),
            ("database.db", self.database_file_path),  # Old database name
            ("database", self.database_file_path),      # Sometimes without extension
            ("last_llm_prompt.txt", self.logs_folder / "last_llm_prompt.txt"),  # Debug file
        ]
        
        for old_name, new_path in files_to_migrate:
            old_path = old_dir / old_name
            if old_path.exists() and not new_path.exists():
                try:
                    old_path.rename(new_path)
                    print(f"Migrated {old_name} to {new_path}")
                except Exception as e:
                    print(f"Failed to migrate {old_name}: {e}")
        
        # Migrate config folder contents
        old_config = old_dir / "config"
        if old_config.exists() and old_config.is_dir():
            for config_file in old_config.glob("*.json"):
                new_config_path = self.config_folder / config_file.name
                if not new_config_path.exists():
                    try:
                        config_file.rename(new_config_path)
                        print(f"Migrated {config_file.name} to config folder")
                    except Exception as e:
                        print(f"Failed to migrate {config_file.name}: {e}")


# Global instance
data_folder_manager = DataFolderManager()