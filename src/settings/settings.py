import os
import json
import logging
import time
import threading
from core.config import get_config
from settings.settings_migrator import get_migrator
from managers.data_folder_manager import data_folder_manager

SETTINGS_FILE = str(data_folder_manager.settings_file_path)

# Settings cache for avoiding repeated file reads (saves 10-50ms per access)
_settings_cache: dict = None
_settings_cache_time: float = 0.0
_settings_cache_lock = threading.Lock()
SETTINGS_CACHE_TTL = 5.0  # Cache valid for 5 seconds
DEFAULT_STORAGE_FOLDER = os.path.join(os.path.expanduser("~"), "Documents", "Medical-Dictation", "Storage")

# NEW: Default AI Provider setting (default is OpenAI)
DEFAULT_AI_PROVIDER = "openai"
# NEW: Default Speech-to-Text provider setting (updated to include GROQ as default)
DEFAULT_STT_PROVIDER = "groq"
# NEW: Default theme setting
DEFAULT_THEME = "flatly"  # Light theme default

_DEFAULT_SETTINGS = {
    "ai_config": {
        "synopsis_enabled": True,
        "synopsis_max_words": 200
    },
    "agent_config": {
        "synopsis": {
            "enabled": True,
            "provider": "openai",
            "model": "gpt-4",
            "temperature": 0.3,
            "max_tokens": 300,
            "system_prompt": """You are a medical documentation specialist. Your task is to create concise, 
        clinically relevant synopses from SOAP notes. The synopsis should:
        
        1. Be under 200 words
        2. Capture the key clinical findings and plan
        3. Use clear, professional medical language
        4. Focus on the most important diagnostic and treatment information
        5. Maintain the clinical context and patient safety considerations
        
        Format the synopsis as a single paragraph that a healthcare provider could quickly read
        to understand the essential clinical picture."""
        },
        "diagnostic": {
            "enabled": False,
            "provider": "openai",
            "model": "gpt-4",
            "temperature": 0.1,
            "max_tokens": 500,
            "system_prompt": """You are a medical diagnostic assistant with expertise in differential diagnosis.
        
Your role is to:
1. Analyze symptoms, signs, and clinical findings
2. Generate a comprehensive differential diagnosis list with ICD-9 codes
3. Rank diagnoses by likelihood based on the clinical presentation
4. Suggest appropriate investigations to narrow the differential
5. Highlight any red flags or concerning features

Guidelines:
- Always provide multiple diagnostic possibilities
- Include ICD-9 codes for each differential diagnosis (format: xxx.xx)
- Consider common conditions before rare ones (think horses, not zebras)
- Include both benign and serious conditions when appropriate
- Never provide definitive diagnoses - only suggestions for clinical consideration
- Always recommend appropriate follow-up and investigations
- Flag any emergency conditions that need immediate attention
- Use ONLY ICD-9 codes, not ICD-10 codes

Format your response as:
1. CLINICAL SUMMARY: Brief overview of key findings
2. DIFFERENTIAL DIAGNOSES: Listed by likelihood with ICD-9 codes and brief reasoning
   Example: 1. Migraine without aura (346.10) - Classic presentation with family history
3. RED FLAGS: Any concerning features requiring urgent attention
4. RECOMMENDED INVESTIGATIONS: Tests to help narrow the differential
5. CLINICAL PEARLS: Key points to remember for this presentation"""
        },
        "medication": {
            "enabled": False,
            "provider": "openai",
            "model": "gpt-4",
            "temperature": 0.2,
            "max_tokens": 400,
            "system_prompt": "You are a medication management assistant. Help with medication selection, dosing, and interaction checking. Always emphasize the importance of clinical judgment and patient-specific factors. Include warnings about contraindications and potential side effects."
        },
        "referral": {
            "enabled": False,
            "provider": "openai",
            "model": "gpt-4",
            "temperature": 0.3,
            "max_tokens": 350,
            "system_prompt": "You are a referral letter specialist. Generate professional, concise referral letters that include: 1. Clear reason for referral 2. Relevant clinical history 3. Current medications 4. Specific questions or requests 5. Urgency level. Format letters professionally and appropriately for the specialty."
        },
        "data_extraction": {
            "enabled": False,
            "provider": "openai",
            "model": "gpt-3.5-turbo",
            "temperature": 0.0,
            "max_tokens": 300,
            "system_prompt": "You are a clinical data extraction specialist. Extract structured data from clinical text including: Vital signs, Laboratory values, Medications with dosages, Diagnoses with ICD codes, Procedures. Return data in a structured, consistent format."
        },
        "workflow": {
            "enabled": False,
            "provider": "openai",
            "model": "gpt-4",
            "temperature": 0.3,
            "max_tokens": 500,
            "system_prompt": "You are a clinical workflow coordinator. Help manage multi-step medical processes including: Patient intake workflows, Diagnostic workup planning, Treatment protocols, Follow-up scheduling. Provide clear, step-by-step guidance while maintaining flexibility for clinical judgment."
        }
    },
    "refine_text": {
        "prompt": """Refine the punctuation and capitalization of the following text so that any voice command cues like 'full stop' are replaced with the appropriate punctuation and sentences start with a capital letter.""",
        "model": "gpt-3.5-turbo",  # OpenAI model
        "grok_model": "grok-1",    # Grok model
        "perplexity_model": "sonar-medium-chat",  # Perplexity model
        "ollama_model": "llama3",   # Ollama model
        "anthropic_model": "claude-sonnet-4-20250514",  # Anthropic model
        "gemini_model": "gemini-2.0-flash",  # Gemini model
        "temperature": 0.0,  # Default temperature for refine_text
        "openai_temperature": 0.0,  # OpenAI-specific temperature
        "grok_temperature": 0.0,    # Grok-specific temperature
        "perplexity_temperature": 0.0, # Perplexity-specific temperature
        "ollama_temperature": 0.0,   # Ollama-specific temperature
        "anthropic_temperature": 0.0,  # Anthropic-specific temperature
        "gemini_temperature": 0.0  # Gemini-specific temperature
    },
    "improve_text": {
        "prompt": "Improve the clarity, readability, and overall quality of the following transcript text.",
        "model": "gpt-3.5-turbo",  # OpenAI model
        "grok_model": "grok-1",    # Grok model
        "perplexity_model": "sonar-medium-chat",  # Perplexity model
        "ollama_model": "llama3",   # Ollama model
        "anthropic_model": "claude-sonnet-4-20250514",  # Anthropic model
        "gemini_model": "gemini-2.0-flash",  # Gemini model
        "temperature": 0.7,  # Default temperature for improve_text
        "openai_temperature": 0.7,  # OpenAI-specific temperature
        "grok_temperature": 0.7,    # Grok-specific temperature
        "perplexity_temperature": 0.7, # Perplexity-specific temperature
        "ollama_temperature": 0.7,   # Ollama-specific temperature
        "anthropic_temperature": 0.7,  # Anthropic-specific temperature
        "gemini_temperature": 0.7  # Gemini-specific temperature
    },
    "soap_note": {
        "system_message": "",  # DEPRECATED - legacy field, use per-provider fields below
        # Per-provider system messages (empty = use provider-optimized default)
        "openai_system_message": "",
        "anthropic_system_message": "",
        "grok_system_message": "",
        "perplexity_system_message": "",
        "ollama_system_message": "",
        "gemini_system_message": "",
        "icd_code_version": "ICD-9",  # Options: "ICD-9", "ICD-10", "both"
        "model": "gpt-3.5-turbo",  # OpenAI model
        "grok_model": "grok-1",    # Grok model
        "perplexity_model": "sonar-medium-chat",  # Perplexity model
        "ollama_model": "llama3",   # Ollama model
        "anthropic_model": "claude-sonnet-4-20250514",  # Anthropic model
        "gemini_model": "gemini-1.5-pro",  # Gemini model (Pro for SOAP notes)
        "temperature": 0.4,  # Default temperature for soap_note (lower for more consistent output)
        "openai_temperature": 0.4,  # OpenAI-specific temperature
        "grok_temperature": 0.4,    # Grok-specific temperature
        "perplexity_temperature": 0.4, # Perplexity-specific temperature
        "ollama_temperature": 0.4,   # Ollama-specific temperature
        "anthropic_temperature": 0.4,  # Anthropic-specific temperature
        "gemini_temperature": 0.4  # Gemini-specific temperature
    },
    "referral": {
        "prompt": "Write a referral paragraph using the SOAP Note given to you",
        "model": "gpt-3.5-turbo",  # OpenAI model
        "grok_model": "grok-1",    # Grok model
        "perplexity_model": "sonar-medium-chat",  # Perplexity model
        "ollama_model": "llama3",   # Ollama model
        "anthropic_model": "claude-sonnet-4-20250514",  # Anthropic model
        "gemini_model": "gemini-2.0-flash",  # Gemini model
        "temperature": 0.7,  # Default temperature for referral
        "openai_temperature": 0.7,  # OpenAI-specific temperature
        "grok_temperature": 0.7,    # Grok-specific temperature
        "perplexity_temperature": 0.7, # Perplexity-specific temperature
        "ollama_temperature": 0.7,   # Ollama-specific temperature
        "anthropic_temperature": 0.7,  # Anthropic-specific temperature
        "gemini_temperature": 0.7  # Gemini-specific temperature
    },
    "advanced_analysis": {
        "provider": "",  # Empty = use global ai_provider, or "openai", "anthropic", etc.
        "prompt": """Analyze this medical encounter transcript and provide a clinical assessment.

If patient context is provided, incorporate it into your differential.

TRANSCRIPT:""",
        "system_message": """You are an experienced clinical decision support AI assisting with real-time differential diagnosis during patient encounters.

INSTRUCTIONS:
1. Analyze the transcript carefully, noting key symptoms, history, and clinical findings
2. Generate a structured clinical assessment
3. Be specific - cite evidence from the transcript to support each diagnosis
4. Flag any concerning findings that require immediate attention
5. Suggest questions that would help narrow the differential

OUTPUT FORMAT (use this exact structure):

CHIEF COMPLAINT:
[One sentence summary of the presenting problem]

KEY CLINICAL FINDINGS:
- [Finding 1 from transcript]
- [Finding 2 from transcript]
- [Additional relevant findings...]

RED FLAGS:
[List any urgent/emergent findings requiring immediate attention, or "None identified"]

DIFFERENTIAL DIAGNOSES (ranked by likelihood):
1. [Diagnosis] - [HIGH/MEDIUM/LOW confidence]
   Supporting: [transcript evidence]
   Against: [contradicting evidence or "None"]

2. [Diagnosis] - [HIGH/MEDIUM/LOW confidence]
   Supporting: [transcript evidence]
   Against: [contradicting evidence or "None"]

3. [Diagnosis] - [HIGH/MEDIUM/LOW confidence]
   Supporting: [transcript evidence]
   Against: [contradicting evidence or "None"]

4. [Diagnosis] - [MEDIUM/LOW confidence]
   Supporting: [transcript evidence]
   Against: [contradicting evidence or "None"]

5. [Diagnosis] - [LOW confidence]
   Supporting: [transcript evidence]
   Against: [contradicting evidence or "None"]

RECOMMENDED WORKUP:
Priority 1 (Urgent): [tests/imaging needed immediately]
Priority 2 (Soon): [tests to order]
Priority 3 (Outpatient): [non-urgent workup]

QUESTIONS TO ASK:
- [Question that would help narrow differential]
- [Question about red flag symptoms]
- [Question about relevant history]

IMMEDIATE ACTIONS:
[Any urgent interventions or consults needed, or "Routine evaluation appropriate"]""",
        "model": "gpt-4",  # OpenAI model
        "grok_model": "grok-1",    # Grok model
        "perplexity_model": "sonar-reasoning-pro",  # Perplexity model
        "ollama_model": "llama3",   # Ollama model
        "anthropic_model": "claude-sonnet-4-20250514",  # Anthropic model
        "gemini_model": "gemini-1.5-pro",  # Gemini model (Pro for advanced analysis)
        "temperature": 0.3,  # Default temperature for advanced analysis
        "openai_temperature": 0.3,  # OpenAI-specific temperature
        "grok_temperature": 0.3,    # Grok-specific temperature
        "perplexity_temperature": 0.3, # Perplexity-specific temperature
        "ollama_temperature": 0.3,   # Ollama-specific temperature
        "anthropic_temperature": 0.3,  # Anthropic-specific temperature
        "gemini_temperature": 0.3  # Gemini-specific temperature
    },
    "elevenlabs": {
        "model_id": "scribe_v1",  # Changed from scribe_v1 to match the supported model
        "language_code": "",  # Empty string for auto-detection
        "tag_audio_events": True,
        "num_speakers": None,  # None means auto-detection
        "timestamps_granularity": "word",
        "diarize": True
    },
    "deepgram": {
        "model": "nova-2-medical",  # Options: nova-2, nova-2-medical, enhanced, etc.
        "language": "en-US",        # Language code
        "smart_format": True,       # Enable smart formatting for better punctuation
        "diarize": False,           # Speaker diarization
        "profanity_filter": False,  # Filter profanity
        "redact": False,            # Redact PII (personally identifiable information)
        "alternatives": 1           # Number of alternative transcriptions
    },
    "storage_folder": DEFAULT_STORAGE_FOLDER,
    "ai_provider": DEFAULT_AI_PROVIDER,
    "stt_provider": DEFAULT_STT_PROVIDER,
    "theme": DEFAULT_THEME,
    "custom_context_templates": {},  # User-defined context templates
    "window_width": 0,  # Will be set based on user preference, 0 means use default calculation
    "window_height": 0,  # Will be set based on user preference, 0 means use default calculation
    "chat_interface": {
        "enabled": True,
        "max_input_length": 2000,
        "max_context_length": 8000,
        "max_history_items": 10,
        "show_suggestions": True,
        "auto_apply_changes": True,  # Whether to auto-apply AI suggestions to documents
        "temperature": 0.3  # AI temperature for chat responses
    },
    "custom_chat_suggestions": {
        "global": [
            "Explain in simple terms",
            "What are the next steps?",
            "Check for errors"
        ],  # Always available suggestions
        "transcript": {
            "with_content": [
                "Highlight key medical findings",
                "Extract patient concerns"
            ],
            "without_content": [
                "Upload and transcribe audio file",
                "Paste medical conversation"
            ]
        },
        "soap": {
            "with_content": [
                "Review for completeness",
                "Add ICD-10 codes"
            ],
            "without_content": [
                "Create SOAP from transcript",
                "Generate structured note"
            ]
        },
        "referral": {
            "with_content": [
                "Check urgency level",
                "Verify specialist info"
            ],
            "without_content": [
                "Draft specialist referral",
                "Create consultation request"
            ]
        },
        "letter": {
            "with_content": [
                "Make patient-friendly",
                "Check medical accuracy"
            ],
            "without_content": [
                "Write patient explanation",
                "Create follow-up letter"
            ]
        }
    },
    "quick_continue_mode": True,  # Enable background processing by default
    "max_background_workers": 2,
    "show_processing_notifications": True,
    "auto_retry_failed": True,
    "max_retry_attempts": 3,
    "notification_style": "toast",  # toast, statusbar, popup
    "auto_update_ui_on_completion": True,  # Auto-populate tabs when processing completes
    "autosave_enabled": True,  # Enable auto-save by default
    "autosave_interval": 300,  # Auto-save every 5 minutes (300 seconds)
    "recording_autosave_enabled": True,  # Enable recording auto-save during recordings
    "recording_autosave_interval": 60,   # Save recording every 60 seconds
    "translation": {
        "provider": "deep_translator",  # Translation provider (deep_translator)
        "sub_provider": "google",       # Sub-provider (google, deepl, microsoft)
        "patient_language": "es",       # Default patient language (Spanish)
        "doctor_language": "en",        # Default doctor language (English)
        "auto_detect": True,           # Auto-detect patient language
        "input_device": "",            # Translation-specific microphone
        "output_device": "",           # Translation-specific speaker/output device
        # LLM-based medical translation refinement (hybrid approach)
        "llm_refinement_enabled": False,  # Enable LLM refinement for medical terms
        "refinement_provider": "openai",  # AI provider for refinement
        "refinement_model": "gpt-3.5-turbo",  # Model for refinement (cost-efficient)
        "refinement_temperature": 0.1   # Low temp for consistent translations
    },
    "tts": {
        "provider": "pyttsx3",         # TTS provider (pyttsx3, elevenlabs, google)
        "voice": "default",            # Voice ID/name (provider-specific)
        "rate": 150,                   # Speech rate (words per minute)
        "volume": 1.0,                 # Volume level (0.0 to 1.0)
        "language": "en",              # Default TTS language
        "elevenlabs_model": "eleven_turbo_v2_5"  # ElevenLabs model (eleven_turbo_v2_5, eleven_multilingual_v2, eleven_monolingual_v1)
    },
    "translation_canned_responses": {
        "categories": ["greeting", "symptom", "history", "instruction", "clarify", "general"],
        "responses": {
            # Greetings/General
            "How are you feeling today?": "greeting",
            "How can I help you?": "greeting",
            "Everything looks normal": "general",
            "I understand your concern": "general",
            
            # Symptom questions
            "Can you describe your symptoms?": "symptom",
            "How long have you had these symptoms?": "symptom",
            "Does it hurt when I press here?": "symptom",
            "On a scale of 1-10, how severe is the pain?": "symptom",
            "Is the pain constant or does it come and go?": "symptom",
            
            # Medical history
            "Are you taking any medications?": "history",
            "Do you have any allergies?": "history",
            "Have you had this problem before?": "history",
            "Do you have any medical conditions?": "history",
            
            # Instructions
            "I need to examine you": "instruction",
            "Please take a deep breath": "instruction",
            "Open your mouth and say 'Ah'": "instruction",
            "Take this medication twice a day": "instruction",
            "Please follow up in one week": "instruction",
            "Rest and drink plenty of fluids": "instruction",
            
            # Clarifications
            "Can you show me where it hurts?": "clarify",
            "When did this start?": "clarify",
            "Is there anything else bothering you?": "clarify"
        }
    },
    "custom_vocabulary": {
        "enabled": True,              # Enable vocabulary corrections
        "default_specialty": "general",  # Default medical specialty
        "corrections": {
            # Example entries - users can add their own
            # Format: "find_text": {"replacement": "...", "category": "...", "specialty": "...", ...}
        }
    }
}

def merge_settings_with_defaults(settings: dict, defaults: dict) -> dict:
    """Recursively merge settings with defaults, ensuring all default keys exist."""
    merged = settings.copy()
    
    for key, default_value in defaults.items():
        if key not in merged:
            # Key is missing, add it from defaults
            merged[key] = default_value
        elif isinstance(default_value, dict) and isinstance(merged.get(key), dict):
            # Both are dicts, merge recursively
            merged[key] = merge_settings_with_defaults(merged[key], default_value)
        elif key == "system_prompt" and isinstance(merged.get(key), str) and merged.get(key) == "":
            # Special case: replace ONLY empty system prompts with defaults
            merged[key] = default_value
    
    return merged

def load_settings(force_refresh: bool = False) -> dict:
    """Load settings with caching to avoid repeated file reads.

    Caches settings for SETTINGS_CACHE_TTL seconds to improve performance.
    Saves 10-50ms per access when cache is valid.

    Args:
        force_refresh: Force reload from disk ignoring cache

    Returns:
        Settings dictionary
    """
    global _settings_cache, _settings_cache_time

    current_time = time.time()

    # Check cache first (thread-safe read)
    if not force_refresh and _settings_cache is not None:
        if current_time - _settings_cache_time < SETTINGS_CACHE_TTL:
            return _settings_cache

    # Need to reload - acquire lock for thread safety
    with _settings_cache_lock:
        # Double-check after acquiring lock
        if not force_refresh and _settings_cache is not None:
            if current_time - _settings_cache_time < SETTINGS_CACHE_TTL:
                return _settings_cache

        # Load from file
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    loaded_settings = json.load(f)
                    # Debug: Log what we're loading
                    synopsis_provider = loaded_settings.get("agent_config", {}).get("synopsis", {}).get("provider", "NOT SET")
                    logging.debug(f"Loading settings from file, synopsis provider: {synopsis_provider}")
                    # Merge with defaults to ensure all keys exist
                    merged = merge_settings_with_defaults(loaded_settings, _DEFAULT_SETTINGS)
                    # Debug: Log after merge
                    merged_provider = merged.get("agent_config", {}).get("synopsis", {}).get("provider", "NOT SET")
                    logging.debug(f"After merge, synopsis provider: {merged_provider}")

                    # Update cache
                    _settings_cache = merged
                    _settings_cache_time = current_time
                    return merged
            except Exception as e:
                logging.error("Error loading settings", exc_info=True)

        result = _DEFAULT_SETTINGS.copy()
        _settings_cache = result
        _settings_cache_time = current_time
        return result


def invalidate_settings_cache() -> None:
    """Invalidate the settings cache to force reload on next access."""
    global _settings_cache, _settings_cache_time
    with _settings_cache_lock:
        _settings_cache = None
        _settings_cache_time = 0.0

def save_settings(settings: dict) -> None:
    """Save settings to file and invalidate cache."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)
        # Invalidate cache so next load gets fresh data
        invalidate_settings_cache()
    except Exception as e:
        logging.error("Error saving settings", exc_info=True)

# Load settings on module import
SETTINGS = load_settings()

# Initialize new configuration system
_config = get_config()
_migrator = get_migrator()

# Don't mess with settings if we have agent_config (modern format)
# The migrator is only for converting very old settings formats
if "agent_config" not in SETTINGS:
    # Store original before migration
    original_loaded_settings = SETTINGS.copy()
    
    # Old settings format, needs migration
    _migrator.migrate_from_dict(SETTINGS)
    # Override SETTINGS with migrated values for backward compatibility
    migrated_settings = _migrator.get_legacy_format()
    SETTINGS = migrated_settings
    
    # Restore any sections that got lost
    for preserve_key in ["custom_chat_suggestions", "chat_interface"]:
        if preserve_key in original_loaded_settings:
            SETTINGS[preserve_key] = original_loaded_settings[preserve_key]
            
    # Fix empty synopsis prompt only for migrated settings
    if "agent_config" in SETTINGS and "synopsis" in SETTINGS["agent_config"]:
        synopsis_config = SETTINGS["agent_config"]["synopsis"]
        current_prompt = synopsis_config.get("system_prompt", "")
        if not current_prompt or not current_prompt.strip():
            try:
                from ai.agents.synopsis import SynopsisAgent
                synopsis_config["system_prompt"] = SynopsisAgent.DEFAULT_CONFIG.system_prompt
                logging.info("Updated empty synopsis system prompt with default")
            except ImportError:
                synopsis_config["system_prompt"] = _DEFAULT_SETTINGS["agent_config"]["synopsis"]["system_prompt"]
    
    # Save the migrated settings
    save_settings(SETTINGS)
else:
    # Modern format with agent_config - just ensure empty prompts are fixed
    made_changes = False
    
    if "synopsis" in SETTINGS["agent_config"]:
        synopsis_config = SETTINGS["agent_config"]["synopsis"]
        current_prompt = synopsis_config.get("system_prompt", "")
        if not current_prompt or not current_prompt.strip():
            try:
                from ai.agents.synopsis import SynopsisAgent
                synopsis_config["system_prompt"] = SynopsisAgent.DEFAULT_CONFIG.system_prompt
                made_changes = True
                logging.info("Updated empty synopsis system prompt with default")
            except ImportError:
                synopsis_config["system_prompt"] = _DEFAULT_SETTINGS["agent_config"]["synopsis"]["system_prompt"]
                made_changes = True
    
    # Only save if we fixed an empty prompt
    if made_changes:
        save_settings(SETTINGS)
