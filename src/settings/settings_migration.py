"""
Settings Migration Module

Provides migration utilities for converting between old and new settings formats.
This module combines the migration orchestration and the migrator class.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from utils.structured_logging import get_logger

from core.config import Config, get_config

logger = get_logger(__name__)


class SettingsMigrator:
    """Migrates settings from old format to new configuration system."""

    def __init__(self):
        self.config = get_config()

    def migrate_from_dict(self, old_settings: Dict[str, Any]) -> None:
        """Migrate settings from old dictionary format to new config.

        Args:
            old_settings: Dictionary containing old-format settings
        """
        # Migrate AI task settings
        for task in ["refine_text", "improve_text", "soap_note", "referral"]:
            if task in old_settings and task in self.config.ai_tasks:
                task_settings = old_settings[task]
                ai_task = self.config.ai_tasks[task]

                # Update prompt
                if "prompt" in task_settings:
                    ai_task.prompt = task_settings["prompt"]

                # Update system message
                if "system_message" in task_settings:
                    ai_task.system_message = task_settings["system_message"]

                # Update model
                if "model" in task_settings:
                    ai_task.model = task_settings["model"]

                # Update temperature
                if "temperature" in task_settings:
                    ai_task.temperature = task_settings["temperature"]

                # Update provider-specific models
                if "ollama_model" in task_settings:
                    ai_task.provider_models["ollama"] = task_settings["ollama_model"]
                if "anthropic_model" in task_settings:
                    ai_task.provider_models["anthropic"] = task_settings["anthropic_model"]
                if "gemini_model" in task_settings:
                    ai_task.provider_models["gemini"] = task_settings["gemini_model"]
                if "groq_model" in task_settings:
                    ai_task.provider_models["groq"] = task_settings["groq_model"]
                if "cerebras_model" in task_settings:
                    ai_task.provider_models["cerebras"] = task_settings["cerebras_model"]

                # Update provider-specific temperatures
                for provider in ["openai", "anthropic", "ollama", "gemini", "groq", "cerebras"]:
                    temp_key = f"{provider}_temperature"
                    if temp_key in task_settings:
                        ai_task.provider_temperatures[provider] = task_settings[temp_key]

        # Migrate Deepgram settings
        if "deepgram" in old_settings:
            deepgram_settings = old_settings["deepgram"]
            for key in ["model", "language", "smart_format", "diarize",
                        "profanity_filter", "redact", "alternatives"]:
                if key in deepgram_settings:
                    setattr(self.config.deepgram, key, deepgram_settings[key])

        # Migrate ElevenLabs settings
        if "elevenlabs" in old_settings:
            elevenlabs_settings = old_settings["elevenlabs"]
            for key in ["model_id", "language_code", "tag_audio_events",
                        "num_speakers", "timestamps_granularity", "diarize"]:
                if key in elevenlabs_settings:
                    setattr(self.config.elevenlabs, key, elevenlabs_settings[key])

        # Migrate storage folder
        if "storage_folder" in old_settings:
            self.config.storage.base_folder = old_settings["storage_folder"]

        # Migrate UI settings
        if "theme" in old_settings:
            self.config.ui.theme = old_settings["theme"]
        if "window_width" in old_settings:
            self.config.ui.window_width = old_settings["window_width"]
        if "window_height" in old_settings:
            self.config.ui.window_height = old_settings["window_height"]

        # Migrate provider settings
        if "stt_provider" in old_settings:
            self.config.transcription.default_provider = old_settings["stt_provider"]

    def get_legacy_format(self) -> Dict[str, Any]:
        """Convert current config back to legacy format for compatibility.

        Returns:
            Dictionary in legacy settings format
        """
        legacy = {}

        # Convert AI tasks
        for task_name, task_config in self.config.ai_tasks.items():
            legacy[task_name] = {
                "prompt": task_config.prompt,
                "model": task_config.model,
                "temperature": task_config.temperature
            }

            if task_config.system_message:
                legacy[task_name]["system_message"] = task_config.system_message

            # Add provider-specific models
            for provider, model in task_config.provider_models.items():
                legacy[task_name][f"{provider}_model"] = model

            # Add provider-specific temperatures
            for provider, temp in task_config.provider_temperatures.items():
                legacy[task_name][f"{provider}_temperature"] = temp

        # Convert Deepgram settings
        legacy["deepgram"] = {
            "model": self.config.deepgram.model,
            "language": self.config.deepgram.language,
            "smart_format": self.config.deepgram.smart_format,
            "diarize": self.config.deepgram.diarize,
            "profanity_filter": self.config.deepgram.profanity_filter,
            "redact": self.config.deepgram.redact,
            "alternatives": self.config.deepgram.alternatives
        }

        # Convert ElevenLabs settings
        legacy["elevenlabs"] = {
            "model_id": self.config.elevenlabs.model_id,
            "language_code": self.config.elevenlabs.language_code,
            "tag_audio_events": self.config.elevenlabs.tag_audio_events,
            "num_speakers": self.config.elevenlabs.num_speakers,
            "timestamps_granularity": self.config.elevenlabs.timestamps_granularity,
            "diarize": self.config.elevenlabs.diarize
        }

        # Convert other settings
        legacy["storage_folder"] = self.config.storage.base_folder
        legacy["ai_provider"] = "openai"  # Default
        legacy["stt_provider"] = self.config.transcription.default_provider
        legacy["theme"] = self.config.ui.theme
        legacy["window_width"] = self.config.ui.window_width
        legacy["window_height"] = self.config.ui.window_height

        return legacy


# Global migrator instance (lazy initialized)
_migrator: Optional[SettingsMigrator] = None


def get_migrator() -> SettingsMigrator:
    """Get the global settings migrator instance.

    Returns:
        The singleton SettingsMigrator instance
    """
    global _migrator
    if _migrator is None:
        _migrator = SettingsMigrator()
    return _migrator


def migrate_settings() -> None:
    """Migrate settings.json to new configuration system.

    This function orchestrates the full migration process:
    1. Locates existing settings.json file
    2. Loads and migrates settings to new format
    3. Saves to environment-specific config file
    4. Backs up original settings
    """
    from managers.data_folder_manager import data_folder_manager

    logger.info("Medical Assistant Settings Migration Tool")
    logger.info("=" * 40)

    # Check if settings.json exists in old location first
    old_settings_file = Path("settings.json")
    settings_file = data_folder_manager.settings_file_path

    # Try old location if new location doesn't have it
    if not settings_file.exists() and old_settings_file.exists():
        settings_file = old_settings_file
    elif not settings_file.exists():
        logger.info("No settings.json file found. Nothing to migrate.")
        return

    # Load existing settings
    try:
        with open(settings_file, 'r', encoding='utf-8') as f:
            old_settings = json.load(f)
        logger.info(f"Loaded settings from {settings_file}")
    except Exception as e:
        logger.error(f"Error loading settings.json: {e}")
        return

    # Detect environment
    env = os.getenv('MEDICAL_ASSISTANT_ENV', 'production')
    logger.info(f"Target environment: {env}")

    # Initialize configuration
    config = Config(env)
    migrator = SettingsMigrator()

    # Migrate settings
    logger.info("Migrating settings...")
    migrator.migrate_from_dict(old_settings)

    # Save to environment-specific config
    config_file = config._get_config_file()
    logger.info(f"Saving to {config_file}")

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

        logger.info(f"Migration complete! Settings saved to {config_file}")

        # Backup old settings
        backup_file = settings_file.with_suffix('.json.backup')
        settings_file.rename(backup_file)
        logger.info(f"Original settings backed up to {backup_file}")

        logger.info("Next steps:")
        logger.info(f"1. Review the migrated configuration in {config_file}")
        logger.info("2. Set up your API keys in a .env file (see .env.example)")
        logger.info("3. Test the application with the new configuration")

    except Exception as e:
        logger.error(f"Error saving configuration: {e}")
        return


# Allow running as script
if __name__ == "__main__":
    migrate_settings()


__all__ = [
    "SettingsMigrator",
    "get_migrator",
    "migrate_settings",
]
