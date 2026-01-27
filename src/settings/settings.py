"""
Settings Management Module

This module provides centralized settings management for the Medical Assistant
application. Settings are organized into logical domains for easier maintenance.

Organization:
- _DEFAULTS_*: Domain-specific default settings constants
- _DEFAULT_SETTINGS: Combined settings dict (built from domain constants)
- load_settings/save_settings: Core I/O functions
- SETTINGS: Global settings dict (loaded on import)
"""

import os
import json
import time
import threading
from typing import Dict, Any, Optional
from utils.structured_logging import get_logger
from core.config import get_config
from settings.settings_migration import get_migrator
from managers.data_folder_manager import data_folder_manager

logger = get_logger(__name__)

SETTINGS_FILE = str(data_folder_manager.settings_file_path)

# Settings cache for avoiding repeated file reads (saves 10-50ms per access)
_settings_cache: Optional[Dict[str, Any]] = None
_settings_cache_time: float = 0.0
_settings_cache_lock = threading.Lock()
SETTINGS_CACHE_TTL = 60.0  # Cache valid for 60 seconds

# Global defaults
DEFAULT_STORAGE_FOLDER = os.path.join(os.path.expanduser("~"), "Documents", "Medical-Dictation", "Storage")
DEFAULT_AI_PROVIDER = "openai"
DEFAULT_STT_PROVIDER = "elevenlabs"
DEFAULT_THEME = "flatly"


# =============================================================================
# HELPER FUNCTIONS FOR SETTINGS GENERATION
# =============================================================================

def _make_provider_model_config(
    openai_model: str = "gpt-3.5-turbo",
    ollama_model: str = "llama3",
    anthropic_model: str = "claude-sonnet-4-20250514",
    gemini_model: str = "gemini-2.0-flash",
    temperature: float = 0.7
) -> Dict[str, Any]:
    """Generate provider-specific model and temperature configuration.

    Reduces duplication for settings that need model/temperature per provider.

    Args:
        openai_model: OpenAI model name
        ollama_model: Ollama model name
        anthropic_model: Anthropic model name
        gemini_model: Gemini model name
        temperature: Default temperature for all providers

    Returns:
        Dict with model and temperature keys for each provider
    """
    return {
        "model": openai_model,
        "ollama_model": ollama_model,
        "anthropic_model": anthropic_model,
        "gemini_model": gemini_model,
        "temperature": temperature,
        "openai_temperature": temperature,
        "ollama_temperature": temperature,
        "anthropic_temperature": temperature,
        "gemini_temperature": temperature,
    }


# =============================================================================
# DOMAIN-SPECIFIC DEFAULT SETTINGS
# =============================================================================

# AI Configuration defaults
_DEFAULTS_AI_CONFIG = {
    "synopsis_enabled": True,
    "synopsis_max_words": 200
}

# Agent Configuration defaults
_DEFAULTS_AGENT_CONFIG = {
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
        "max_tokens": 800,
        "auto_run_after_soap": False,
        "system_prompt": """You are a medical diagnostic assistant with expertise in differential diagnosis.

Your role is to:
1. Analyze symptoms, signs, and clinical findings
2. Generate a comprehensive differential diagnosis list with ICD codes
3. Rank diagnoses by likelihood with confidence levels based on the clinical presentation
4. Suggest appropriate investigations to narrow the differential
5. Highlight any red flags or concerning features

Guidelines:
- Always provide multiple diagnostic possibilities (aim for 5-7 differentials)
- Include BOTH ICD-10 (primary) and ICD-9 codes for each differential diagnosis
  - ICD-10 format: Letter + 2 digits + optional decimal (e.g., J06.9, G43.909)
  - ICD-9 format: 3 digits + optional decimal (e.g., 346.10, 250.00)
- Assign confidence levels: HIGH (>70%), MEDIUM (40-70%), or LOW (<40%)
- Consider common conditions before rare ones (think horses, not zebras)
- Include both benign and serious conditions when appropriate
- Never provide definitive diagnoses - only suggestions for clinical consideration
- Always recommend appropriate follow-up and investigations
- Flag any emergency conditions that need immediate attention
- Consider patient demographics (age, sex) when ranking differentials
- Factor in past medical history and current medications if provided

Format your response as:
1. CLINICAL SUMMARY: Brief overview of key findings including patient demographics if available

2. DIFFERENTIAL DIAGNOSES: Listed by likelihood with ICD codes, confidence, and reasoning
   Format: #. Diagnosis Name (ICD-10: X00.0, ICD-9: 000.0) [Confidence: HIGH/MEDIUM/LOW]
   - Supporting evidence: [findings that support this diagnosis]
   - Against: [findings that argue against, or "None identified"]
   Example:
   1. Migraine without aura (ICD-10: G43.009, ICD-9: 346.10) [Confidence: HIGH]
      - Supporting evidence: Unilateral headache, photophobia, nausea, family history
      - Against: None identified

3. RED FLAGS: Any concerning features requiring urgent attention (or "None identified")

4. RECOMMENDED INVESTIGATIONS: Tests to help narrow the differential, prioritized
   - Priority 1 (Urgent): Tests needed immediately
   - Priority 2 (Soon): Tests to order within days
   - Priority 3 (Routine): Non-urgent workup

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
        "enabled": True,
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
}

# Text processing defaults (refine, improve, referral)
_DEFAULTS_TEXT_PROCESSING = {
    "refine_text": {
        "prompt": """Refine the punctuation and capitalization of the following text so that any voice command cues like 'full stop' are replaced with the appropriate punctuation and sentences start with a capital letter.""",
        **_make_provider_model_config(
            openai_model="gpt-3.5-turbo",
            temperature=0.0
        )
    },
    "improve_text": {
        "prompt": "Improve the clarity, readability, and overall quality of the following transcript text.",
        **_make_provider_model_config(
            openai_model="gpt-3.5-turbo",
            temperature=0.7
        )
    },
    "referral": {
        "prompt": "Write a referral paragraph using the SOAP Note given to you",
        **_make_provider_model_config(
            openai_model="gpt-3.5-turbo",
            temperature=0.7
        )
    }
}

# SOAP note generation defaults
_DEFAULTS_SOAP_NOTE = {
    "system_message": "",  # DEPRECATED - legacy field, use per-provider fields below
    "openai_system_message": "",
    "anthropic_system_message": "",
    "ollama_system_message": "",
    "gemini_system_message": "",
    "icd_code_version": "ICD-9",  # Options: "ICD-9", "ICD-10", "both"
    **_make_provider_model_config(
        openai_model="gpt-3.5-turbo",
        gemini_model="gemini-1.5-pro",  # Pro for SOAP notes
        temperature=0.4  # Lower for consistent output
    )
}

# Advanced analysis defaults
_DEFAULTS_ADVANCED_ANALYSIS = {
    "provider": "",  # Empty = use global ai_provider
    "specialty": "general",  # Clinical specialty focus
    "prompt": """Analyze this medical encounter transcript and provide a clinical assessment.

If patient context is provided, incorporate it into your differential.

TRANSCRIPT:""",
    "system_message": """You are an experienced clinical decision support AI assisting with real-time differential diagnosis during patient encounters.

CONFIDENCE SCORING (REQUIRED):
- Provide NUMERIC confidence (0-100%) for each diagnosis
- Scale: 80-100% very likely, 60-79% likely, 40-59% possible, 20-39% less likely, <20% unlikely but serious
- Consider patient demographics and pre-test probability

SAFETY REQUIREMENTS:
- ALWAYS include a "MUST-NOT-MISS" section for serious/treatable conditions
- Mark time-critical conditions with urgency window
- Even low-probability diagnoses must be included if missing them causes harm

OUTPUT FORMAT:

CHIEF COMPLAINT:
[One sentence summary]

KEY CLINICAL FINDINGS:
• [Finding 1 with clinical significance]
• [Finding 2 with clinical significance]

🚨 MUST-NOT-MISS (actively rule out):
⚠️ [Serious Diagnosis] - [X]% (ICD-10: [code])
   Rule out with: [specific test/finding]
   Time-sensitive: [Yes/No - specify window if yes]

DIFFERENTIAL DIAGNOSES (ranked by likelihood):
1. [Diagnosis] - [X]% confidence (ICD-10: [code])
   Supporting: [evidence from transcript]
   Against: [contradicting evidence]

2. [Diagnosis] - [X]% confidence (ICD-10: [code])
   Supporting: [evidence]
   Against: [evidence]

[Continue for 3-5 diagnoses]

RED FLAGS IDENTIFIED:
🚨 CRITICAL (immediate action): [Finding] - [why critical, time window if applicable]
⚠️ HIGH (within hours): [Finding] - [evaluation needed]
⚡ MODERATE (this visit): [Finding] - [workup recommendation]
[Omit severity levels with no findings. Categorize by clinical urgency: CRITICAL = potential life-threat, HIGH = needs same-day evaluation, MODERATE = needs attention but not emergent]

RECOMMENDED WORKUP:
🔴 URGENT (now):
   • [Test] - Sens [X]%/Spec [Y]% for [condition] - rules out [diagnosis #s]
🟡 SOON (this visit):
   • [Test] - [diagnostic utility] - helps distinguish [A] from [B]
🟢 OUTPATIENT (if stable):
   • [Test] - [rationale]
[Include sensitivity/specificity for key tests when clinically relevant for ruling in/out diagnoses]

QUESTIONS TO NARROW DIFFERENTIAL:
• [Question 1] - would help distinguish [diagnosis A] from [diagnosis B]
• [Question 2] - addresses red flag symptom

⚡ BIAS CHECK:
[Only include if applicable - omit section entirely if analysis appears balanced and thorough]
- Anchoring: [If top diagnosis matches chief complaint too closely, suggest alternatives to consider]
- Availability: [If common diagnosis dominates, note rarer serious conditions to consider]
- Premature closure: [If history incomplete, note what additional information would help]
- Confirmation bias: [Note any findings that DON'T fit your leading diagnosis]

IMMEDIATE ACTIONS:
[Urgent interventions needed, or "Routine evaluation appropriate"]

---
Analysis #{number} | Elapsed: {time}""",
    **_make_provider_model_config(
        openai_model="gpt-4",
        gemini_model="gemini-1.5-pro",  # Pro for advanced analysis
        temperature=0.3
    )
}

# STT provider defaults
_DEFAULTS_STT_PROVIDERS = {
    "elevenlabs": {
        "model_id": "scribe_v2",
        "language_code": "",  # Auto-detection
        "tag_audio_events": True,
        "num_speakers": None,  # Auto-detection (up to 48)
        "timestamps_granularity": "word",
        "diarize": True,
        "entity_detection": [],
        "keyterms": []
    },
    "deepgram": {
        "model": "nova-2-medical",
        "language": "en-US",
        "smart_format": True,
        "diarize": False,
        "profanity_filter": False,
        "redact": False,
        "alternatives": 1
    }
}

# Chat interface defaults
_DEFAULTS_CHAT = {
    "chat_interface": {
        "enabled": True,
        "max_input_length": 2000,
        "max_context_length": 8000,
        "max_history_items": 10,
        "show_suggestions": True,
        "auto_apply_changes": True,
        "temperature": 0.3
    },
    "custom_chat_suggestions": {
        "global": [
            {"text": "Explain in simple terms", "favorite": False},
            {"text": "What are the next steps?", "favorite": False},
            {"text": "Check for errors", "favorite": False}
        ],
        "transcript": {
            "with_content": [
                {"text": "Highlight key medical findings", "favorite": False},
                {"text": "Extract patient concerns", "favorite": False}
            ],
            "without_content": [
                {"text": "Upload and transcribe audio file", "favorite": False},
                {"text": "Paste medical conversation", "favorite": False}
            ]
        },
        "soap": {
            "with_content": [
                {"text": "Review for completeness", "favorite": False},
                {"text": "Add ICD-10 codes", "favorite": False}
            ],
            "without_content": [
                {"text": "Create SOAP from transcript", "favorite": False},
                {"text": "Generate structured note", "favorite": False}
            ]
        },
        "referral": {
            "with_content": [
                {"text": "Check urgency level", "favorite": False},
                {"text": "Verify specialist info", "favorite": False}
            ],
            "without_content": [
                {"text": "Draft specialist referral", "favorite": False},
                {"text": "Create consultation request", "favorite": False}
            ]
        },
        "letter": {
            "with_content": [
                {"text": "Make patient-friendly", "favorite": False},
                {"text": "Check medical accuracy", "favorite": False}
            ],
            "without_content": [
                {"text": "Write patient explanation", "favorite": False},
                {"text": "Create follow-up letter", "favorite": False}
            ]
        }
    }
}

# Translation and TTS defaults
_DEFAULTS_TRANSLATION_TTS = {
    "translation": {
        "provider": "deep_translator",
        "sub_provider": "google",
        "patient_language": "es",
        "doctor_language": "en",
        "auto_detect": True,
        "input_device": "",
        "output_device": "",
        "llm_refinement_enabled": False,
        "refinement_provider": "openai",
        "refinement_model": "gpt-3.5-turbo",
        "refinement_temperature": 0.1
    },
    "tts": {
        "provider": "pyttsx3",
        "voice": "default",
        "rate": 150,
        "volume": 1.0,
        "language": "en",
        "elevenlabs_model": "eleven_turbo_v2_5"
    },
    "translation_canned_responses": {
        "categories": ["greeting", "symptom", "history", "instruction", "clarify", "general"],
        "responses": {
            "How are you feeling today?": "greeting",
            "How can I help you?": "greeting",
            "Everything looks normal": "general",
            "I understand your concern": "general",
            "Can you describe your symptoms?": "symptom",
            "How long have you had these symptoms?": "symptom",
            "Does it hurt when I press here?": "symptom",
            "On a scale of 1-10, how severe is the pain?": "symptom",
            "Is the pain constant or does it come and go?": "symptom",
            "Are you taking any medications?": "history",
            "Do you have any allergies?": "history",
            "Have you had this problem before?": "history",
            "Do you have any medical conditions?": "history",
            "I need to examine you": "instruction",
            "Please take a deep breath": "instruction",
            "Open your mouth and say 'Ah'": "instruction",
            "Take this medication twice a day": "instruction",
            "Please follow up in one week": "instruction",
            "Rest and drink plenty of fluids": "instruction",
            "Can you show me where it hurts?": "clarify",
            "When did this start?": "clarify",
            "Is there anything else bothering you?": "clarify"
        }
    }
}

# Feature and processing defaults
_DEFAULTS_FEATURES = {
    "quick_continue_mode": True,
    "max_background_workers": 2,
    "show_processing_notifications": True,
    "auto_retry_failed": True,
    "max_retry_attempts": 3,
    "notification_style": "toast",
    "auto_update_ui_on_completion": True,
    "autosave_enabled": True,
    "autosave_interval": 300,
    "recording_autosave_enabled": True,
    "recording_autosave_interval": 60
}

# UI and storage defaults
_DEFAULTS_UI_STORAGE = {
    "storage_folder": DEFAULT_STORAGE_FOLDER,
    "ai_provider": DEFAULT_AI_PROVIDER,
    "stt_provider": DEFAULT_STT_PROVIDER,
    "theme": DEFAULT_THEME,
    "custom_context_templates": {},
    "window_width": 0,
    "window_height": 0
}

# Custom vocabulary defaults
_DEFAULTS_VOCABULARY = {
    "custom_vocabulary": {
        "enabled": True,
        "default_specialty": "general",
        "corrections": {}
    }
}

# RSVP reader defaults
_DEFAULTS_RSVP = {
    "rsvp": {
        "wpm": 300,
        "font_size": 48,
        "chunk_size": 1,
        "auto_start": False,
        "dark_theme": True,
        "audio_cue": False,
        "show_context": False
    }
}

# RAG search quality defaults
_DEFAULTS_RAG_SEARCH_QUALITY = {
    "rag_search_quality": {
        "enable_adaptive_threshold": True,
        "min_threshold": 0.2,
        "max_threshold": 0.8,
        "target_result_count": 5,
        "enable_query_expansion": True,
        "expand_abbreviations": True,
        "expand_synonyms": True,
        "max_expansion_terms": 3,
        "enable_bm25": True,
        "vector_weight": 0.5,
        "bm25_weight": 0.3,
        "graph_weight": 0.2,
        "enable_mmr": True,
        "mmr_lambda": 0.7
    }
}

# Logging Configuration defaults
_DEFAULTS_LOGGING = {
    "logging": {
        "level": "INFO",  # DEBUG, INFO, WARNING, ERROR, CRITICAL
        "file_level": "DEBUG",  # Level for file logs
        "console_level": "INFO",  # Level for console output
        "max_file_size_kb": 200,
        "backup_count": 2,
    }
}

# RAG Resilience defaults
_DEFAULTS_RAG_RESILIENCE = {
    "rag_resilience": {
        "neo4j_failure_threshold": 3,
        "neo4j_recovery_timeout": 30,
        "neon_failure_threshold": 5,
        "neon_recovery_timeout": 30,
        "embedding_failure_threshold": 5,
        "embedding_recovery_timeout": 60,
        "health_check_cache_ttl": 30,
    }
}


# =============================================================================
# COMBINED DEFAULT SETTINGS
# =============================================================================

_DEFAULT_SETTINGS: Dict[str, Any] = {
    "ai_config": _DEFAULTS_AI_CONFIG,
    "agent_config": _DEFAULTS_AGENT_CONFIG,
    **_DEFAULTS_TEXT_PROCESSING,
    "soap_note": _DEFAULTS_SOAP_NOTE,
    "advanced_analysis": _DEFAULTS_ADVANCED_ANALYSIS,
    **_DEFAULTS_STT_PROVIDERS,
    **_DEFAULTS_UI_STORAGE,
    **_DEFAULTS_CHAT,
    **_DEFAULTS_FEATURES,
    **_DEFAULTS_TRANSLATION_TTS,
    **_DEFAULTS_VOCABULARY,
    **_DEFAULTS_RSVP,
    **_DEFAULTS_RAG_SEARCH_QUALITY,
    **_DEFAULTS_LOGGING,
    **_DEFAULTS_RAG_RESILIENCE,
}


# =============================================================================
# SETTINGS I/O FUNCTIONS
# =============================================================================

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


def _migrate_suggestions_to_favorites(suggestions):
    """Convert string-based suggestions to object format with favorite flag.

    Handles nested dictionaries for context-specific suggestions.
    If suggestions are already in object format, returns them unchanged.

    Args:
        suggestions: Can be a list of strings/objects, or a dict with nested structure

    Returns:
        Suggestions in the new object format with 'text' and 'favorite' keys
    """
    if isinstance(suggestions, list):
        migrated = []
        for s in suggestions:
            if isinstance(s, dict) and "text" in s:
                # Already in new format
                migrated.append(s)
            elif isinstance(s, str):
                # Convert string to object format
                migrated.append({"text": s, "favorite": False})
            # Skip invalid entries
        return migrated
    elif isinstance(suggestions, dict):
        # Recursively handle nested dictionaries (e.g., transcript -> with_content/without_content)
        return {
            key: _migrate_suggestions_to_favorites(value)
            for key, value in suggestions.items()
        }
    return suggestions


def load_settings(force_refresh: bool = False, validate: bool = True) -> dict:
    """Load settings with caching to avoid repeated file reads.

    Caches settings for SETTINGS_CACHE_TTL seconds to improve performance.
    Saves 10-50ms per access when cache is valid.

    Args:
        force_refresh: Force reload from disk ignoring cache
        validate: Run Pydantic validation on loaded settings (logs warnings)

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
                    logger.debug(f"Loading settings from file, synopsis provider: {synopsis_provider}")
                    # Merge with defaults to ensure all keys exist
                    merged = merge_settings_with_defaults(loaded_settings, _DEFAULT_SETTINGS)
                    # Debug: Log after merge
                    merged_provider = merged.get("agent_config", {}).get("synopsis", {}).get("provider", "NOT SET")
                    logger.debug(f"After merge, synopsis provider: {merged_provider}")

                    # Migrate custom_chat_suggestions to new object format (with favorite flag)
                    if "custom_chat_suggestions" in merged:
                        merged["custom_chat_suggestions"] = _migrate_suggestions_to_favorites(
                            merged["custom_chat_suggestions"]
                        )

                    # Validate settings if requested
                    if validate:
                        try:
                            from settings.settings_models import validate_settings
                            validated, result = validate_settings(merged)
                            for warning in result.warnings:
                                logger.warning(f"Settings validation: {warning}")
                            for error in result.errors:
                                logger.error(f"Settings validation error: {error}")
                        except ImportError:
                            pass  # Pydantic not available, skip validation

                    # Update cache
                    _settings_cache = merged
                    _settings_cache_time = current_time
                    return merged
            except Exception as e:
                logger.error("Error loading settings", exc_info=True)

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
        logger.error("Error saving settings", exc_info=True)

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
                logger.info("Updated empty synopsis system prompt with default")
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
                logger.info("Updated empty synopsis system prompt with default")
            except ImportError:
                synopsis_config["system_prompt"] = _DEFAULT_SETTINGS["agent_config"]["synopsis"]["system_prompt"]
                made_changes = True
    
    # Only save if we fixed an empty prompt
    if made_changes:
        save_settings(SETTINGS)
