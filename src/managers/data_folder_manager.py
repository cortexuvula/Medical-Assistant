"""
Data folder management for Medical Assistant application.
Centralizes all application data files into a proper folder structure.
"""
import os
import shutil
import sys
from pathlib import Path
from typing import Optional
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class DataFolderManager:
    """Manages the application data folder structure."""

    def __init__(self):
        self._app_data_folder: Optional[Path] = None
        self._init_data_folder()

    def _init_data_folder(self):
        """Initialize the data folder based on the running environment."""
        if getattr(sys, 'frozen', False):
            if sys.platform == 'darwin':
                # macOS: use ~/Library/Application Support/MedicalAssistant
                # Storing data inside the .app bundle is problematic because
                # the bundle is treated as a single file, code-signing would
                # be invalidated, and app updates replace the entire bundle.
                self._app_data_folder = (
                    Path.home() / "Library" / "Application Support" / "MedicalAssistant"
                )
            else:
                # Windows / Linux: keep AppData next to executable
                app_dir = Path(sys.executable).parent
                self._app_data_folder = app_dir / "AppData"
        else:
            # Running as script - get project root
            # Navigate from src/managers/data_folder_manager.py to project root
            current_file = Path(__file__).resolve()
            # Go up from managers -> src -> project root
            app_dir = current_file.parent.parent.parent
            self._app_data_folder = app_dir / "AppData"

        self._ensure_folders_exist()

        # On macOS frozen builds, migrate data from the old in-bundle location
        if getattr(sys, 'frozen', False) and sys.platform == 'darwin':
            self._migrate_from_bundle()
    
    def _ensure_folders_exist(self):
        """Ensure all required folders exist."""
        # Create main AppData folder (parents=True for macOS Application Support path)
        self._app_data_folder.mkdir(parents=True, exist_ok=True)
        
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
    
    def _migrate_from_bundle(self):
        """Migrate data from the old in-bundle AppData location on macOS.

        Previous builds stored data at
        /Applications/MedicalAssistant.app/Contents/MacOS/AppData/.
        Copy any files found there to the new ~/Library/Application Support/
        location so users don't lose settings, database, or .env credentials.
        """
        old_bundle_dir = Path(sys.executable).parent / "AppData"
        if not old_bundle_dir.exists() or not old_bundle_dir.is_dir():
            return

        migrated = 0
        for item in old_bundle_dir.rglob("*"):
            if not item.is_file():
                continue
            rel = item.relative_to(old_bundle_dir)
            dest = self._app_data_folder / rel
            if dest.exists():
                continue
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(item), str(dest))
                migrated += 1
            except Exception as e:
                logger.warning(f"Failed to migrate {rel} from bundle: {e}")

        if migrated:
            logger.info(
                f"Migrated {migrated} file(s) from old bundle AppData to "
                f"{self._app_data_folder}"
            )

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
                    logger.info(f"Migrated {old_name} to {new_path}")
                except Exception as e:
                    logger.warning(f"Failed to migrate {old_name}: {e}")

        # Migrate config folder contents
        old_config = old_dir / "config"
        if old_config.exists() and old_config.is_dir():
            for config_file in old_config.glob("*.json"):
                new_config_path = self.config_folder / config_file.name
                if not new_config_path.exists():
                    try:
                        config_file.rename(new_config_path)
                        logger.info(f"Migrated {config_file.name} to config folder")
                    except Exception as e:
                        logger.warning(f"Failed to migrate {config_file.name}: {e}")


# Global instance
data_folder_manager = DataFolderManager()