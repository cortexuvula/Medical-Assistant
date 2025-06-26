import os
import json
import logging
from core.config import get_config
from settings.settings_migrator import get_migrator
from managers.data_folder_manager import data_folder_manager

SETTINGS_FILE = str(data_folder_manager.settings_file_path)
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
        "anthropic_model": "claude-3-sonnet-20240229",  # Anthropic model
        "temperature": 0.0,  # Default temperature for refine_text
        "openai_temperature": 0.0,  # OpenAI-specific temperature
        "grok_temperature": 0.0,    # Grok-specific temperature
        "perplexity_temperature": 0.0, # Perplexity-specific temperature
        "ollama_temperature": 0.0,   # Ollama-specific temperature
        "anthropic_temperature": 0.0  # Anthropic-specific temperature
    },
    "improve_text": {
        "prompt": "Improve the clarity, readability, and overall quality of the following transcript text.",
        "model": "gpt-3.5-turbo",  # OpenAI model
        "grok_model": "grok-1",    # Grok model
        "perplexity_model": "sonar-medium-chat",  # Perplexity model
        "ollama_model": "llama3",   # Ollama model
        "anthropic_model": "claude-3-sonnet-20240229",  # Anthropic model
        "temperature": 0.7,  # Default temperature for improve_text
        "openai_temperature": 0.7,  # OpenAI-specific temperature
        "grok_temperature": 0.7,    # Grok-specific temperature
        "perplexity_temperature": 0.7, # Perplexity-specific temperature
        "ollama_temperature": 0.7,   # Ollama-specific temperature
        "anthropic_temperature": 0.7  # Anthropic-specific temperature
    },
    "soap_note": {
        "system_message": """You are a supportive general family practice physician tasked with analyzing transcripts from patient consultations with yourself.   
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
  

### Example Transcript

Patient: "I've been having severe headaches for the past week. They are mostly on one side of my head and are accompanied by nausea and sensitivity to light."

Physician: "Do you have any history of migraines in your family?"

Patient: "Yes, my mother and sister both have migraines. I've also had these headaches on and off since I was a teenager."

Physician: "Have you tried any medications for the pain?"

Patient: "I've taken over-the-counter painkillers, but they don't seem to help much."

Physician: "Let's check your blood pressure and do a quick neurological exam."

*Physician performs the examination.*

Physician: "Your blood pressure is normal, and there are no signs of any serious neurological issues. Based on your symptoms and family history, it sounds like you might be experiencing migraines. I recommend trying a prescription medication specifically for migraines. I'll also refer you to a neurologist for further evaluation."

### Example SOAP Note

SOAP Note:
ICD-9 Code: 346.90

Subjective:
The patient reports severe headaches for the past week, predominantly on one side of the head. Symptoms include nausea and sensitivity to light. There is a family history of migraines (mother and sister). The patient has experienced similar headaches since adolescence. Over-the-counter painkillers have been ineffective.

Objective:
Blood pressure: 120/80 mmHg. Neurological examination normal, no signs of focal deficits.

Assessment:
The patient is likely experiencing migraines based on the symptom pattern and family history.

Differential Diagnosis:
- Migraine without aura
- Tension headache
- Cluster headache

Plan:
- Prescribe a triptan medication for acute migraine relief.
- Refer to neurology for further evaluation and management.
- Advise on lifestyle modifications and trigger avoidance.
- Side effects were discussed, and the patient was encouraged to consult their pharmacist for a medicine review.

Follow up:
- Follow up in 4 weeks to assess the effectiveness of the medication.
- Schedule neurology appointment within the next month.


### Notes:


** Always return your response in plain text without markdown **

""",
        "model": "gpt-3.5-turbo",  # OpenAI model
        "grok_model": "grok-1",    # Grok model
        "perplexity_model": "sonar-medium-chat",  # Perplexity model
        "ollama_model": "llama3",   # Ollama model
        "anthropic_model": "claude-3-sonnet-20240229",  # Anthropic model
        "temperature": 0.7,  # Default temperature for soap_note
        "openai_temperature": 0.7,  # OpenAI-specific temperature
        "grok_temperature": 0.7,    # Grok-specific temperature
        "perplexity_temperature": 0.7, # Perplexity-specific temperature
        "ollama_temperature": 0.7,   # Ollama-specific temperature
        "anthropic_temperature": 0.7  # Anthropic-specific temperature
    },
    "referral": {
        "prompt": "Write a referral paragraph using the SOAP Note given to you",
        "model": "gpt-3.5-turbo",  # OpenAI model
        "grok_model": "grok-1",    # Grok model
        "perplexity_model": "sonar-medium-chat",  # Perplexity model
        "ollama_model": "llama3",   # Ollama model
        "anthropic_model": "claude-3-sonnet-20240229",  # Anthropic model
        "temperature": 0.7,  # Default temperature for referral
        "openai_temperature": 0.7,  # OpenAI-specific temperature
        "grok_temperature": 0.7,    # Grok-specific temperature
        "perplexity_temperature": 0.7, # Perplexity-specific temperature
        "ollama_temperature": 0.7,   # Ollama-specific temperature
        "anthropic_temperature": 0.7  # Anthropic-specific temperature
    },
    "advanced_analysis": {
        "prompt": "Transcript:",
        "system_message": """You are a medical AI assistant helping to analyze patient consultations. Provide clear, structured differential diagnoses with relevant investigations and treatment recommendations. Format your response without markdown and clear sections for:
1. Differential Diagnoses (list 5 with brief explanations)
2. Recommended Investigations
3. Treatment Plan""",
        "model": "gpt-4",  # OpenAI model
        "grok_model": "grok-1",    # Grok model
        "perplexity_model": "sonar-reasoning-pro",  # Perplexity model
        "ollama_model": "llama3",   # Ollama model
        "anthropic_model": "claude-3-sonnet-20240229",  # Anthropic model
        "temperature": 0.3,  # Default temperature for advanced analysis
        "openai_temperature": 0.3,  # OpenAI-specific temperature
        "grok_temperature": 0.3,    # Grok-specific temperature
        "perplexity_temperature": 0.3, # Perplexity-specific temperature
        "ollama_temperature": 0.3,   # Ollama-specific temperature
        "anthropic_temperature": 0.3  # Anthropic-specific temperature
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
    "voice_mode": {
        "ai_provider": "openai",
        "ai_model": "gpt-4",
        "ai_temperature": 0.7,
        "system_prompt": """You are a medical AI assistant in voice mode. Provide helpful, conversational responses about medical topics. Keep responses concise and natural for voice interaction. When discussing medical conditions, be clear about when professional medical advice is needed.""",
        "tts_provider": "openai",
        "tts_voice": "nova",
        "stt_provider": "deepgram",
        "enable_interruptions": True,
        "response_delay_ms": 500,
        "max_context_length": 4000,
        "openai_model": "gpt-4",
        "grok_model": "grok-1",
        "perplexity_model": "sonar-reasoning-pro",
        "ollama_model": "llama3",
        "anthropic_model": "claude-3-sonnet-20240229",
        "openai_temperature": 0.7,
        "grok_temperature": 0.7,
        "perplexity_temperature": 0.7,
        "ollama_temperature": 0.7,
        "anthropic_temperature": 0.7
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

def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                loaded_settings = json.load(f)
                # Merge with defaults to ensure all keys exist
                return merge_settings_with_defaults(loaded_settings, _DEFAULT_SETTINGS)
        except Exception as e:
            logging.error("Error loading settings", exc_info=True)
    return _DEFAULT_SETTINGS.copy()

def save_settings(settings: dict) -> None:
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)
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
