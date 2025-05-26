#!/usr/bin/env python3
"""
Utility to migrate existing settings.json to the new configuration system.
"""

import json
import os
import sys
from pathlib import Path
from config import Config
from settings_migrator import SettingsMigrator


def migrate_settings():
    """Migrate settings.json to new configuration system."""
    print("Medical Assistant Settings Migration Tool")
    print("=" * 40)
    
    # Check if settings.json exists
    settings_file = Path("settings.json")
    if not settings_file.exists():
        print("No settings.json file found. Nothing to migrate.")
        return
    
    # Load existing settings
    try:
        with open(settings_file, 'r', encoding='utf-8') as f:
            old_settings = json.load(f)
        print(f"Loaded settings from {settings_file}")
    except Exception as e:
        print(f"Error loading settings.json: {e}")
        return
    
    # Detect environment
    env = os.getenv('MEDICAL_ASSISTANT_ENV', 'production')
    print(f"Target environment: {env}")
    
    # Initialize configuration
    config = Config(env)
    migrator = SettingsMigrator()
    
    # Migrate settings
    print("\nMigrating settings...")
    migrator.migrate_from_dict(old_settings)
    
    # Save to environment-specific config
    config_file = config._get_config_file()
    print(f"Saving to {config_file}")
    
    try:
        # Load existing env config if it exists
        env_config = {}
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                env_config = json.load(f)
        
        # Merge migrated settings
        migrated_config = config.to_dict()
        
        # Only save the differences from defaults
        differences = {}
        
        # Compare each section
        for section in ['api', 'audio', 'storage', 'ui', 'transcription', 'deepgram', 'elevenlabs']:
            if section in migrated_config:
                differences[section] = {}
                for key, value in migrated_config[section].items():
                    # Only include if different from default
                    if section in env_config and key in env_config[section]:
                        if env_config[section][key] != value:
                            differences[section][key] = value
        
        # Handle AI tasks specially
        if 'ai_tasks' in migrated_config:
            differences['ai_tasks'] = {}
            for task_name, task_config in migrated_config['ai_tasks'].items():
                differences['ai_tasks'][task_name] = {}
                for key, value in task_config.items():
                    if key not in ['prompt', 'system_message']:  # Don't override prompts
                        differences['ai_tasks'][task_name][key] = value
        
        # Clean up empty sections
        differences = {k: v for k, v in differences.items() if v}
        
        # Save differences
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(differences, f, indent=2)
        
        print(f"✓ Migration complete! Settings saved to {config_file}")
        
        # Backup old settings
        backup_file = settings_file.with_suffix('.json.backup')
        settings_file.rename(backup_file)
        print(f"✓ Original settings backed up to {backup_file}")
        
        print("\nNext steps:")
        print("1. Review the migrated configuration in", config_file)
        print("2. Set up your API keys in a .env file (see .env.example)")
        print("3. Test the application with the new configuration")
        
    except Exception as e:
        print(f"Error saving configuration: {e}")
        return


if __name__ == "__main__":
    migrate_settings()