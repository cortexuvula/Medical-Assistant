"""
Log Manager Module

Handles application logging configuration including file rotation,
console output, and log formatting.
"""

import os
import logging
from concurrent_log_handler import ConcurrentRotatingFileHandler
from managers.data_folder_manager import data_folder_manager
from utils.structured_logging import (
    get_logger,
    _get_configured_log_level,
    get_log_level_from_string,
)

logger = get_logger(__name__)


def _get_logging_settings() -> dict:
    """Get logging settings from settings file.

    Returns:
        Dict with logging configuration
    """
    defaults = {
        "level": "INFO",
        "file_level": "DEBUG",
        "console_level": "INFO",
        "max_file_size_kb": 200,
        "backup_count": 2,
    }

    try:
        # Try to load from settings (avoiding circular imports)
        import json
        from pathlib import Path

        settings_paths = [
            Path.home() / "AppData" / "Local" / "MedicalAssistant" / "settings.json",
            Path.home() / ".config" / "MedicalAssistant" / "settings.json",
            Path.home() / "Library" / "Application Support" / "MedicalAssistant" / "settings.json",
        ]

        for settings_path in settings_paths:
            if settings_path.exists():
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    logging_settings = settings.get("logging", {})
                    # Merge with defaults
                    return {**defaults, **logging_settings}
    except Exception:
        pass

    return defaults


class LogManager:
    """Manages application logging configuration."""

    def __init__(self, log_level=None):
        """Initialize the log manager.

        Args:
            log_level: The logging level to use. If None, reads from settings/environment.
        """
        self._settings = _get_logging_settings()

        # Use provided level, or get from settings/environment
        if log_level is not None:
            self.log_level = log_level
        else:
            self.log_level = _get_configured_log_level()

        # Get file and console levels from settings
        self.file_level = get_log_level_from_string(self._settings.get("file_level", "DEBUG"))
        self.console_level = get_log_level_from_string(self._settings.get("console_level", "INFO"))

        # Check for environment override
        env_level = os.environ.get("MEDICAL_ASSISTANT_LOG_LEVEL", "").upper()
        if env_level:
            # Environment overrides both file and console
            level = get_log_level_from_string(env_level)
            self.file_level = level
            self.console_level = level

        self.log_dir = str(data_folder_manager.logs_folder)
        self.log_file = os.path.join(self.log_dir, "medical_dictation.log")

        # Get file size and backup settings
        self.max_file_size = self._settings.get("max_file_size_kb", 200) * 1024
        self.backup_count = self._settings.get("backup_count", 2)

    def setup_logging(self):
        """Set up logging with rotation to keep file size manageable."""
        # Create logs directory if it doesn't exist
        os.makedirs(self.log_dir, exist_ok=True)

        # Configure root logger with the minimum of file/console levels
        root_logger = logging.getLogger()
        root_logger.setLevel(min(self.file_level, self.console_level))

        # Clear any existing handlers to avoid duplicates
        root_logger.handlers.clear()

        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

        # Create and configure rotating file handler
        file_handler = ConcurrentRotatingFileHandler(
            self.log_file,
            maxBytes=self.max_file_size,
            backupCount=self.backup_count
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(self.file_level)
        root_logger.addHandler(file_handler)

        # Also add console handler for stdout output
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(self.console_level)
        root_logger.addHandler(console_handler)

        logging.info("Logging initialized")
        logging.info(f"Log file path: {self.log_file}")
        logging.debug(f"Log levels - file: {logging.getLevelName(self.file_level)}, console: {logging.getLevelName(self.console_level)}")
        
    def get_log_file_path(self) -> str:
        """Get the path to the current log file.
        
        Returns:
            Path to the log file
        """
        return self.log_file
        
    def get_log_directory(self) -> str:
        """Get the log directory path.
        
        Returns:
            Path to the log directory
        """
        return self.log_dir


def setup_application_logging():
    """Convenience function to set up logging for the application."""
    log_manager = LogManager()
    log_manager.setup_logging()
    return log_manager