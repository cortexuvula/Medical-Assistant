"""
Log Manager Module

Handles application logging configuration including file rotation,
console output, and log formatting.
"""

import os
import logging
from concurrent_log_handler import ConcurrentRotatingFileHandler
from data_folder_manager import data_folder_manager


class LogManager:
    """Manages application logging configuration."""
    
    def __init__(self, log_level=logging.INFO):
        """Initialize the log manager.
        
        Args:
            log_level: The logging level to use (default: logging.INFO)
        """
        self.log_level = log_level
        self.log_dir = str(data_folder_manager.logs_folder)
        self.log_file = os.path.join(self.log_dir, "medical_dictation.log")
        
    def setup_logging(self):
        """Set up logging with rotation to keep file size manageable."""
        # Create logs directory if it doesn't exist
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # Clear any existing handlers to avoid duplicates
        root_logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # Create and configure rotating file handler
        # Set maxBytes to a reasonable size that will hold approximately 1000 entries
        # Each log entry is roughly 100-200 bytes, so 200KB should hold ~1000 entries
        file_handler = ConcurrentRotatingFileHandler(
            self.log_file, 
            maxBytes=200*1024,  # 200 KB
            backupCount=2  # Keep 2 backup files in addition to the current one
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        # Also add console handler for stdout output
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        logging.info("Logging initialized")
        logging.info(f"Log file path: {self.log_file}")
        
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