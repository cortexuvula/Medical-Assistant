import sys
import multiprocessing

# Import console suppression patch first (Windows only)
try:
    import suppress_console
except ImportError:
    pass  # Not critical if it fails

# Check Python version before importing app
if sys.version_info < (3, 10):
    print("Error: This application requires Python 3.10 or higher.")
    print(f"Your current Python version is {sys.version}")
    print("\nPlease update your Python version or create a new environment with Python 3.10+.")
    print("\nSuggested fix: Use conda to create a new environment with Python 3.10:")
    print("conda create -n medical_dictation python=3.10")
    print("conda activate medical_dictation")
    print("pip install -r requirements.txt")
    sys.exit(1)

# Import configuration and validate before starting app
from config import init_config, get_config
from exceptions import ConfigurationError, DatabaseError
import logging
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize configuration
try:
    # Get environment from env variable or default to production
    env = os.getenv('MEDICAL_ASSISTANT_ENV', 'production')
    logger.info(f"Initializing configuration for environment: {env}")
    
    config = init_config(env)
    logger.info("Configuration loaded successfully")
    
    # Validate API keys
    api_key_status = config.validate_api_keys()
    logger.info(f"API key validation: {api_key_status}")
    
    # Log configuration summary
    logger.info(f"Storage folder: {config.storage.base_folder}")
    logger.info(f"Default STT provider: {config.transcription.default_provider}")
    logger.info(f"UI theme: {config.ui.theme}")
    
    # Initialize database and run migrations
    logger.info("Initializing database...")
    from db_migrations import get_migration_manager
    
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
        print(f"\nDatabase Error: {e}")
        print("\nPlease run 'python migrate_database.py' to fix database issues.")
        sys.exit(1)
    
except ConfigurationError as e:
    logger.error(f"Configuration error: {e}")
    print(f"\nConfiguration Error: {e}")
    print("\nPlease check your configuration files in the 'config' directory.")
    sys.exit(1)
except Exception as e:
    logger.error(f"Unexpected error during configuration: {e}", exc_info=True)
    print(f"\nUnexpected Error: {e}")
    sys.exit(1)

# Import app only if configuration is valid
from app import main

if __name__ == "__main__":
    # Required for Windows when using multiprocessing in frozen executables
    multiprocessing.freeze_support()
    main()
