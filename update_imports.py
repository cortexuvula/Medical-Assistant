#!/usr/bin/env python3
"""
Script to update all imports after directory restructuring.
"""

import os
import re
from pathlib import Path

# Define import mappings
IMPORT_MAPPINGS = {
    # Core imports
    "from app import": "from core.app import",
    "import app": "import core.app",
    "from app_initializer import": "from core.app_initializer import",
    "from config import": "from core.config import",
    
    # UI imports
    "from dialogs import": "from ui.dialogs.dialogs import",
    "from audio_dialogs import": "from ui.dialogs.audio_dialogs import",
    "from folder_dialogs import": "from ui.dialogs.folder_dialogs import",
    "from temperature_dialog import": "from ui.dialogs.temperature_dialog import",
    "from recordings_dialog_manager import": "from ui.dialogs.recordings_dialog_manager import",
    "from chat_ui import": "from ui.chat_ui import",
    "from workflow_ui import": "from ui.workflow_ui import",
    "from theme_manager import": "from ui.theme_manager import",
    "from tooltip import": "from ui.tooltip import",
    "from menu_manager import": "from ui.menu_manager import",
    "from status_manager import": "from ui.status_manager import",
    
    # Audio imports
    "from audio import": "from audio.audio import",
    "import audio": "import audio.audio",
    "from recording_manager import": "from audio.recording_manager import",
    "from soap_audio_processor import": "from audio.soap_audio_processor import",
    "from ffmpeg_utils import": "from audio.ffmpeg_utils import",
    
    # AI imports
    "from ai import": "from ai.ai import",
    "import ai": "import ai.ai",
    "from ai_processor import": "from ai.ai_processor import",
    "from chat_processor import": "from ai.chat_processor import",
    "from soap_processor import": "from ai.soap_processor import",
    "from prompts import": "from ai.prompts import",
    
    # Database imports
    "from database import": "from database.database import",
    "from database_v2 import": "from database.database_v2 import",
    "from db_manager import": "from database.db_manager import",
    "from db_migrations import": "from database.db_migrations import",
    "from db_pool import": "from database.db_pool import",
    "from db_queue_schema import": "from database.db_queue_schema import",
    
    # Processing imports
    "from text_processor import": "from processing.text_processor import",
    "from file_processor import": "from processing.file_processor import",
    "from document_generators import": "from processing.document_generators import",
    "from processing_queue import": "from processing.processing_queue import",
    
    # Utils imports
    "from utils import": "from utils.utils import",
    "import utils": "import utils.utils",
    "from cleanup_utils import": "from utils.cleanup_utils import",
    "from validation import": "from utils.validation import",
    "from resilience import": "from utils.resilience import",
    "from security import": "from utils.security import",
    "from security_decorators import": "from utils.security_decorators import",
    "from error_codes import": "from utils.error_codes import",
    "from exceptions import": "from utils.exceptions import",
    
    # Manager imports
    "from file_manager import": "from managers.file_manager import",
    "from api_key_manager import": "from managers.api_key_manager import",
    "from data_folder_manager import": "from managers.data_folder_manager import",
    "from log_manager import": "from managers.log_manager import",
    "from notification_manager import": "from managers.notification_manager import",
    
    # Settings imports
    "from settings import": "from settings.settings import",
    "import settings": "import settings.settings",
    "from settings_migrator import": "from settings.settings_migrator import",
    "from migrate_settings import": "from settings.migrate_settings import",
    
    # Hooks imports (for runtime hooks)
    "import suppress_console": "from hooks import suppress_console",
    
    # STT providers import
    "from stt_providers import": "from stt_providers import",
}

def update_file_imports(file_path):
    """Update imports in a single file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Apply import mappings
        for old_import, new_import in IMPORT_MAPPINGS.items():
            # Use word boundaries for more precise matching
            pattern = r'\b' + re.escape(old_import)
            content = re.sub(pattern, new_import, content)
        
        # Special case for relative imports within the same package
        if '/src/' in str(file_path):
            # Get the package path
            parts = str(file_path).split('/src/')[1].split('/')
            package = parts[0] if len(parts) > 1 else None
            
            if package:
                # Update imports within the same package to use relative imports
                for module in ['ui', 'audio', 'ai', 'database', 'processing', 'utils', 'managers', 'settings']:
                    if package == module:
                        # Convert absolute imports to relative imports for same package
                        content = re.sub(f'from {module}\\.([a-zA-Z_]+) import', 'from .\\1 import', content)
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated imports in: {file_path}")
            return True
    except Exception as e:
        print(f"Error updating {file_path}: {e}")
    return False

def main():
    """Update all Python files in the src directory."""
    src_dir = Path("src")
    updated_count = 0
    
    for py_file in src_dir.rglob("*.py"):
        if update_file_imports(py_file):
            updated_count += 1
    
    print(f"\nTotal files updated: {updated_count}")
    
    # Also update test files
    print("\nUpdating test files...")
    test_dir = Path("tests")
    test_count = 0
    
    for py_file in test_dir.rglob("*.py"):
        if update_file_imports(py_file):
            test_count += 1
    
    print(f"Test files updated: {test_count}")

if __name__ == "__main__":
    main()