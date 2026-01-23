import sys
import multiprocessing

# Import console suppression patch first (Windows only)
try:
    from hooks.suppress_console import suppress_console
except ImportError:
    pass  # Not critical if it fails

# Check Python version before importing app (print to stderr - logging not yet configured)
if sys.version_info < (3, 10):
    sys.stderr.write("Error: This application requires Python 3.10 or higher.\n")
    sys.stderr.write(f"Your current Python version is {sys.version}\n")
    sys.stderr.write("\nPlease update your Python version or create a new environment with Python 3.10+.\n")
    sys.stderr.write("\nSuggested fix: Use conda to create a new environment with Python 3.10:\n")
    sys.stderr.write("conda create -n medical_dictation python=3.10\n")
    sys.stderr.write("conda activate medical_dictation\n")
    sys.stderr.write("pip install -r requirements.txt\n")
    sys.exit(1)

# Single instance check - uses PID file (more reliable than sockets on macOS)
from utils.single_instance import ensure_single_instance, show_already_running_message

if not ensure_single_instance():
    show_already_running_message()
    sys.exit(0)

# Import configuration and validate before starting app
from core.config import init_config, get_config
from utils.exceptions import ConfigurationError, DatabaseError
import os
from managers.data_folder_manager import data_folder_manager

# Set up structured logging (console) and file logging
from utils.structured_logging import setup_logging, get_logger
from managers.log_manager import setup_application_logging
setup_logging()  # Console logging
setup_application_logging()  # File logging with rotation
logger = get_logger(__name__)

# Initialize configuration
try:
    # Migrate existing files to AppData folder
    logger.debug("Migrating existing files to AppData folder...")
    data_folder_manager.migrate_existing_files()
    
    # Get environment from env variable or default to production
    env = os.getenv('MEDICAL_ASSISTANT_ENV', 'production')
    logger.info(f"Initializing configuration for environment: {env}")
    
    config = init_config(env)
    logger.info("Configuration loaded successfully")
    
    # Validate API keys
    api_key_status = config.validate_api_keys()
    logger.info(f"API key validation: {api_key_status}")
    
    # Log configuration summary
    logger.debug(f"Configuration: storage={config.storage.base_folder}, STT={config.transcription.default_provider}, theme={config.ui.theme}")
    
    # Initialize database and run migrations
    logger.info("Initializing database...")
    from database.db_migrations import get_migration_manager
    
    try:
        migration_manager = get_migration_manager()
        current_version = migration_manager.get_current_version()
        pending = migration_manager.get_pending_migrations()

        if pending:
            logger.info(f"Database at version {current_version}, applying {len(pending)} migrations...")
            migration_manager.migrate()
            logger.info(f"Database updated to version {migration_manager.get_current_version()}")
        else:
            logger.info(f"Database up to date (version {current_version})")
    except DatabaseError as e:
        logger.error(f"Database initialization failed: {e}")
        logger.error("Please run 'python migrate_database.py' to fix database issues.")
        sys.exit(1)

    # Run startup diagnostics to check service health
    logger.info("Running startup diagnostics...")
    try:
        from utils.health_checker import run_startup_diagnostics
        health_report = run_startup_diagnostics()
        if not health_report.can_operate:
            logger.warning("Some critical services unavailable - limited functionality")
        elif health_report.unhealthy_services:
            logger.info(f"Optional services unavailable: {', '.join(health_report.unhealthy_services)}")
    except Exception as e:
        logger.warning(f"Startup diagnostics failed (non-critical): {e}")

except ConfigurationError as e:
    logger.error(f"Configuration error: {e}")
    logger.error("Please check your configuration files in the 'config' directory.")
    sys.exit(1)
except Exception as e:
    logger.error(f"Unexpected error during configuration: {e}", exc_info=True)
    sys.exit(1)

# Import app only if configuration is valid
from core.app import main

if __name__ == "__main__":
    # Required for Windows when using multiprocessing in frozen executables
    multiprocessing.freeze_support()
    main()
