# Configuration System

The Medical Assistant uses a hierarchical configuration system with environment-specific overrides.

## Configuration Files

- `config.default.json` - Base configuration with all default values
- `config.development.json` - Development environment overrides
- `config.production.json` - Production environment overrides  
- `config.testing.json` - Testing environment overrides

## Environment Selection

The environment is determined by:
1. The `MEDICAL_ASSISTANT_ENV` environment variable
2. Defaults to `production` if not set

## Configuration Structure

### API Settings (`api`)
- `timeout` - Default API timeout in seconds
- `max_retries` - Maximum retry attempts for failed API calls
- `initial_retry_delay` - Initial delay between retries
- `backoff_factor` - Multiplier for exponential backoff
- `circuit_breaker_threshold` - Failures before circuit opens
- `circuit_breaker_timeout` - Time before circuit recovery attempt

### Audio Settings (`audio`)
- `sample_rate` - Audio sample rate in Hz
- `channels` - Number of audio channels
- `chunk_size` - Audio buffer chunk size
- `silence_threshold` - Threshold for silence detection
- `silence_duration` - Duration of silence to stop recording
- `max_recording_duration` - Maximum recording length in seconds

### Storage Settings (`storage`)
- `base_folder` - Base directory for file storage
- `database_name` - SQLite database filename
- `export_formats` - Supported export formats
- `auto_save` - Enable automatic saving
- `auto_save_interval` - Interval between auto-saves
- `max_file_size_mb` - Maximum file size limit

### UI Settings (`ui`)
- `theme` - UI theme name (flatly, darkly, etc.)
- `window_width/height` - Window dimensions (0 = auto)
- `font_size` - Default font size
- `font_family` - Default font family
- `show_tooltips` - Enable/disable tooltips
- `animation_speed` - UI animation speed in ms

### Transcription Settings (`transcription`)
- `default_provider` - Default STT provider (groq, deepgram, etc.)
- `chunk_duration_seconds` - Audio chunk size for processing
- `overlap_seconds` - Overlap between chunks
- `min_confidence` - Minimum confidence threshold
- `language` - Default language code

### Provider-Specific Settings
- `deepgram` - Deepgram-specific settings
- `elevenlabs` - ElevenLabs-specific settings

### AI Task Settings (`ai_tasks`)
Configuration for each AI task (refine_text, improve_text, soap_note, referral):
- `model` - Default model to use
- `temperature` - Temperature setting
- `provider_models` - Model overrides per provider
- `provider_temperatures` - Temperature overrides per provider

## Customization

To customize settings:

1. Create/edit the appropriate environment file
2. Add only the settings you want to override
3. The system will merge your overrides with defaults

Example override in `config.production.json`:
```json
{
  "api": {
    "timeout": 30,
    "max_retries": 2
  },
  "ui": {
    "theme": "darkly"
  }
}
```

## API Keys

API keys should be set as environment variables:
- `OPENAI_API_KEY`
- `PERPLEXITY_API_KEY`
- `GROQ_API_KEY`
- `DEEPGRAM_API_KEY`
- `ELEVENLABS_API_KEY`

See `.env.example` for a template.