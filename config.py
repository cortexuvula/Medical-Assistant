"""
Configuration management system for Medical Assistant.
Provides centralized configuration with validation and environment support.
"""

import os
import json
import logging
from typing import Any, Dict, Optional, Union, List
from dataclasses import dataclass, field, asdict
from pathlib import Path
from data_folder_manager import data_folder_manager
from enum import Enum

from exceptions import ConfigurationError
from validation import validate_api_key, validate_model_name


class Environment(Enum):
    """Supported environments."""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


class AIProvider(Enum):
    """Supported AI providers."""
    OPENAI = "openai"
    PERPLEXITY = "perplexity"
    GROK = "grok"
    OLLAMA = "ollama"


class STTProvider(Enum):
    """Supported STT providers."""
    GROQ = "groq"
    DEEPGRAM = "deepgram"
    ELEVENLABS = "elevenlabs"
    WHISPER = "whisper"


class Theme(Enum):
    """Supported UI themes."""
    FLATLY = "flatly"
    DARKLY = "darkly"
    COSMO = "cosmo"
    JOURNAL = "journal"
    LUMEN = "lumen"
    MINTY = "minty"
    PULSE = "pulse"
    SIMPLEX = "simplex"
    SLATE = "slate"
    SOLAR = "solar"
    SUPERHERO = "superhero"
    UNITED = "united"


@dataclass
class APIConfig:
    """Configuration for API settings."""
    timeout: int = 60  # Default API timeout in seconds
    max_retries: int = 3
    initial_retry_delay: float = 1.0
    backoff_factor: float = 2.0
    max_retry_delay: float = 60.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 60


@dataclass
class AudioConfig:
    """Configuration for audio settings."""
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    format: str = "wav"
    silence_threshold: int = 500
    silence_duration: float = 1.0
    max_recording_duration: int = 300  # 5 minutes
    playback_speed: float = 1.0
    buffer_size: int = 4096


@dataclass
class StorageConfig:
    """Configuration for storage settings."""
    base_folder: str = field(default_factory=lambda: str(Path.home() / "Documents" / "Medical-Dictation" / "Storage"))
    database_name: str = "medical_assistant.db"
    export_formats: List[str] = field(default_factory=lambda: ["txt", "pdf", "docx"])
    auto_save: bool = True
    auto_save_interval: int = 60  # seconds
    max_file_size_mb: int = 100
    temp_file_cleanup_age_hours: int = 24


@dataclass
class UIConfig:
    """Configuration for UI settings."""
    theme: str = Theme.FLATLY.value
    window_width: int = 0  # 0 means auto-calculate
    window_height: int = 0  # 0 means auto-calculate
    min_window_width: int = 800
    min_window_height: int = 600
    font_size: int = 10
    font_family: str = "Segoe UI"
    show_tooltips: bool = True
    animation_speed: int = 200  # milliseconds
    autoscroll_transcript: bool = True


@dataclass
class TranscriptionConfig:
    """Configuration for transcription settings."""
    default_provider: str = STTProvider.GROQ.value
    chunk_duration_seconds: int = 30
    overlap_seconds: int = 2
    min_confidence: float = 0.7
    enable_punctuation: bool = True
    enable_diarization: bool = False
    max_alternatives: int = 1
    language: str = "en-US"


@dataclass
class AITaskConfig:
    """Configuration for a specific AI task."""
    prompt: str
    system_message: str = ""
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    provider_models: Dict[str, str] = field(default_factory=dict)
    provider_temperatures: Dict[str, float] = field(default_factory=dict)


@dataclass
class DeepgramConfig:
    """Deepgram-specific configuration."""
    model: str = "nova-2-medical"
    language: str = "en-US"
    smart_format: bool = True
    diarize: bool = False
    profanity_filter: bool = False
    redact: bool = False
    alternatives: int = 1


@dataclass
class ElevenLabsConfig:
    """ElevenLabs-specific configuration."""
    model_id: str = "scribe_v1"
    language_code: str = ""  # Empty for auto-detection
    tag_audio_events: bool = True
    num_speakers: Optional[int] = None
    timestamps_granularity: str = "word"
    diarize: bool = True


class Config:
    """Main configuration class with validation and environment support."""
    
    def __init__(self, environment: Optional[str] = None):
        """Initialize configuration.
        
        Args:
            environment: Environment name (development, production, testing)
        """
        self.logger = logging.getLogger(__name__)
        self.environment = self._get_environment(environment)
        self.config_dir = data_folder_manager.config_folder
        self.config_dir.mkdir(exist_ok=True)
        
        # Initialize configuration components
        self.api = APIConfig()
        self.audio = AudioConfig()
        self.storage = StorageConfig()
        self.ui = UIConfig()
        self.transcription = TranscriptionConfig()
        self.deepgram = DeepgramConfig()
        self.elevenlabs = ElevenLabsConfig()
        
        # AI task configurations
        self.ai_tasks = {
            "refine_text": AITaskConfig(
                prompt="Refine the punctuation and capitalization of the following text so that any voice command cues like 'full stop' are replaced with the appropriate punctuation and sentences start with a capital letter.",
                model="gpt-3.5-turbo",
                temperature=0.0,
                provider_models={
                    "grok": "grok-1",
                    "perplexity": "sonar-medium-chat",
                    "ollama": "llama3"
                }
            ),
            "improve_text": AITaskConfig(
                prompt="Improve the clarity, readability, and overall quality of the following transcript text.",
                model="gpt-3.5-turbo",
                temperature=0.7,
                provider_models={
                    "grok": "grok-1",
                    "perplexity": "sonar-medium-chat",
                    "ollama": "llama3"
                }
            ),
            "soap_note": AITaskConfig(
                prompt="Generate a SOAP note from the transcript",
                system_message=self._get_soap_system_message(),
                model="gpt-3.5-turbo",
                temperature=0.7,
                provider_models={
                    "grok": "grok-1",
                    "perplexity": "sonar-medium-chat",
                    "ollama": "llama3"
                }
            ),
            "referral": AITaskConfig(
                prompt="Write a referral paragraph using the SOAP Note given to you",
                model="gpt-3.5-turbo",
                temperature=0.7,
                provider_models={
                    "grok": "grok-1",
                    "perplexity": "sonar-medium-chat",
                    "ollama": "llama3"
                }
            )
        }
        
        # Load configuration
        self._load_config()
    
    def _get_environment(self, environment: Optional[str]) -> Environment:
        """Get the current environment."""
        if environment:
            try:
                return Environment(environment.lower())
            except ValueError:
                self.logger.warning(f"Invalid environment '{environment}', using development")
                return Environment.DEVELOPMENT
        
        # Check environment variable
        env_value = os.getenv("MEDICAL_ASSISTANT_ENV", "development").lower()
        try:
            return Environment(env_value)
        except ValueError:
            self.logger.warning(f"Invalid environment variable '{env_value}', using development")
            return Environment.DEVELOPMENT
    
    def _get_soap_system_message(self) -> str:
        """Get the SOAP note system message."""
        # This is the same as in settings.py but could be loaded from a file
        return """You are a supportive general family practice physician tasked with analyzing transcripts from patient consultations with yourself.   
Your role is to craft detailed SOAP notes using a step-by-step thought process, visualizing your thoughts and adhering to the following guidelines:

### General prompt:
    a. Base your SOAP notes on the content of the transcripts, emphasizing accuracy and thoroughness. Write the SOAP note from a first-person perspective. 
    b. Use clear, professional medical language appropriate for family practice records.
    c. Use dash notation for listings.
    d. Use only unformatted text as your output.
    e. If the consultation was an in-person consult and there are no details about a physical examination, then state in the Objective section that physical examination was deferred. 
    f. If there is a mention of VML in the transcript, this is the local laboratory. Please substitute it with Valley Medical Laboratories.
    g. Only use ICD-9 codes.
    h. When medications are mentioned, then add to the SOAP note that side effects were discussed. The patient should consult their pharmacist to do a full medicine review. 

### Negative Prompt:
    a. Do not use the word transcript, rather use during the visit.
    b.  Avoid using the patient's name, rather use patient.

### Positive Prompt:
    a. Incorporate comprehensive patient history in the 'Subjective' section, including medical history, medications, allergies, and other relevant details.
    b. Ensure the 'Objective' section includes detailed descriptions of physical examinations if the consult was an in-person consult, if it was a phone consult, then state the consult was a telehealth visit. Include pertinent investigation results, highlighting relevant positive and negative findings crucial for differential diagnosis.
    c. Develop a 'Plan' that outlines immediate management steps and follow-up strategies, considering patient centered care aspects.
    d. Only output in plain text format.

** Always return your response in plain text without markdown **"""
    
    def _get_config_file(self) -> Path:
        """Get the configuration file path for the current environment."""
        return self.config_dir / f"config.{self.environment.value}.json"
    
    def _get_default_config_file(self) -> Path:
        """Get the default configuration file path."""
        return self.config_dir / "config.default.json"
    
    def _load_config(self):
        """Load configuration from files."""
        # First load default configuration
        default_config = self._load_config_file(self._get_default_config_file())
        
        # Then load environment-specific configuration
        env_config = self._load_config_file(self._get_config_file())
        
        # Merge configurations (environment overrides default)
        config = self._merge_configs(default_config, env_config)
        
        # Apply configuration
        self._apply_config(config)
        
        # Validate configuration
        self._validate_config()
    
    def _load_config_file(self, file_path: Path) -> Dict[str, Any]:
        """Load configuration from a JSON file."""
        if not file_path.exists():
            return {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading config file {file_path}: {e}")
            return {}
    
    def _merge_configs(self, default: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Merge two configuration dictionaries."""
        result = default.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _apply_config(self, config: Dict[str, Any]):
        """Apply configuration to the instance."""
        # Apply API configuration
        if "api" in config:
            for key, value in config["api"].items():
                if hasattr(self.api, key):
                    setattr(self.api, key, value)
        
        # Apply audio configuration
        if "audio" in config:
            for key, value in config["audio"].items():
                if hasattr(self.audio, key):
                    setattr(self.audio, key, value)
        
        # Apply storage configuration
        if "storage" in config:
            for key, value in config["storage"].items():
                if hasattr(self.storage, key):
                    setattr(self.storage, key, value)
        
        # Apply UI configuration
        if "ui" in config:
            for key, value in config["ui"].items():
                if hasattr(self.ui, key):
                    setattr(self.ui, key, value)
        
        # Apply transcription configuration
        if "transcription" in config:
            for key, value in config["transcription"].items():
                if hasattr(self.transcription, key):
                    setattr(self.transcription, key, value)
        
        # Apply provider-specific configurations
        if "deepgram" in config:
            for key, value in config["deepgram"].items():
                if hasattr(self.deepgram, key):
                    setattr(self.deepgram, key, value)
        
        if "elevenlabs" in config:
            for key, value in config["elevenlabs"].items():
                if hasattr(self.elevenlabs, key):
                    setattr(self.elevenlabs, key, value)
        
        # Apply AI task configurations
        if "ai_tasks" in config:
            for task_name, task_config in config["ai_tasks"].items():
                if task_name in self.ai_tasks:
                    for key, value in task_config.items():
                        if hasattr(self.ai_tasks[task_name], key):
                            setattr(self.ai_tasks[task_name], key, value)
    
    def _validate_config(self):
        """Validate the configuration."""
        errors = []
        
        # Validate theme
        try:
            Theme(self.ui.theme)
        except ValueError:
            errors.append(f"Invalid theme: {self.ui.theme}")
        
        # Validate STT provider
        try:
            STTProvider(self.transcription.default_provider)
        except ValueError:
            errors.append(f"Invalid STT provider: {self.transcription.default_provider}")
        
        # Validate numeric ranges
        if self.api.timeout <= 0:
            errors.append("API timeout must be positive")
        
        if self.api.max_retries < 0:
            errors.append("Max retries must be non-negative")
        
        if self.audio.sample_rate <= 0:
            errors.append("Sample rate must be positive")
        
        if self.storage.max_file_size_mb <= 0:
            errors.append("Max file size must be positive")
        
        # Validate paths
        storage_path = Path(self.storage.base_folder)
        if not storage_path.exists():
            try:
                storage_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create storage folder: {e}")
        
        # Validate AI models
        for task_name, task_config in self.ai_tasks.items():
            is_valid, error = validate_model_name(task_config.model, "openai")
            if not is_valid:
                errors.append(f"Invalid model for {task_name}: {error}")
        
        if errors:
            raise ConfigurationError(
                f"Configuration validation failed: {'; '.join(errors)}",
                details={"errors": errors}
            )
    
    def save(self):
        """Save current configuration to file."""
        config = self.to_dict()
        config_file = self._get_config_file()
        
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            self.logger.info(f"Configuration saved to {config_file}")
        except Exception as e:
            raise ConfigurationError(f"Failed to save configuration: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "environment": self.environment.value,
            "api": asdict(self.api),
            "audio": asdict(self.audio),
            "storage": asdict(self.storage),
            "ui": asdict(self.ui),
            "transcription": asdict(self.transcription),
            "deepgram": asdict(self.deepgram),
            "elevenlabs": asdict(self.elevenlabs),
            "ai_tasks": {
                name: asdict(config) for name, config in self.ai_tasks.items()
            }
        }
    
    def get_api_key(self, provider: str) -> Optional[str]:
        """Get API key for a provider from environment variables."""
        key_mapping = {
            "openai": "OPENAI_API_KEY",
            "perplexity": "PERPLEXITY_API_KEY",
            "groq": "GROQ_API_KEY",
            "deepgram": "DEEPGRAM_API_KEY",
            "elevenlabs": "ELEVENLABS_API_KEY"
        }
        
        env_var = key_mapping.get(provider.lower())
        if not env_var:
            return None
        
        return os.getenv(env_var)
    
    def validate_api_keys(self) -> Dict[str, bool]:
        """Validate all configured API keys."""
        results = {}
        
        for provider in ["openai", "perplexity", "groq", "deepgram", "elevenlabs"]:
            api_key = self.get_api_key(provider)
            if api_key:
                is_valid, _ = validate_api_key(provider, api_key)
                results[provider] = is_valid
            else:
                results[provider] = False
        
        return results


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def init_config(environment: Optional[str] = None) -> Config:
    """Initialize the global configuration with a specific environment."""
    global _config
    _config = Config(environment)
    return _config