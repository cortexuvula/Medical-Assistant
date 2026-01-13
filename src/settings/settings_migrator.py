"""
Settings migration helper to bridge old settings.py with new config.py system.
"""

import os
import json
import logging
from typing import Dict, Any
from core.config import get_config, Config


class SettingsMigrator:
    """Migrates settings from old format to new configuration system."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = get_config()
    
    def migrate_from_dict(self, old_settings: Dict[str, Any]):
        """Migrate settings from old dictionary format to new config."""
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

                # Update provider-specific temperatures
                for provider in ["openai", "anthropic", "ollama", "gemini"]:
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
        """Convert current config back to legacy format for compatibility."""
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


# Global migrator instance
_migrator: SettingsMigrator = None


def get_migrator() -> SettingsMigrator:
    """Get the global settings migrator instance."""
    global _migrator
    if _migrator is None:
        _migrator = SettingsMigrator()
    return _migrator