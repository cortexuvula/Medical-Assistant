import os
import json
import logging

SETTINGS_FILE = "settings.json"
DEFAULT_STORAGE_FOLDER = "C:/Users/corte/Documents/Medical-Dictation/Storage"

# NEW: Default AI Provider setting (default is OpenAI)
DEFAULT_AI_PROVIDER = "openai"
# NEW: Default Speech-to-Text provider setting (updated to include ElevenLabs)
DEFAULT_STT_PROVIDER = "deepgram"
# NEW: Default theme setting
DEFAULT_THEME = "flatly"  # Light theme default

_DEFAULT_SETTINGS = {
    "refine_text": {
        "prompt": """Refine the punctuation and capitalization of the following text so that any voice command cues like 'full stop' are replaced with the appropriate punctuation and sentences start with a capital letter.""",
        "model": "gpt-3.5-turbo",  # OpenAI model
        "grok_model": "grok-1",    # Grok model
        "perplexity_model": "sonar-medium-chat",  # Perplexity model
        "ollama_model": "llama3",   # Ollama model
        "temperature": 0.0,  # Default temperature for refine_text
        "openai_temperature": 0.0,  # OpenAI-specific temperature
        "grok_temperature": 0.0,    # Grok-specific temperature
        "perplexity_temperature": 0.0, # Perplexity-specific temperature
        "ollama_temperature": 0.0   # Ollama-specific temperature
    },
    "improve_text": {
        "prompt": "Improve the clarity, readability, and overall quality of the following transcript text.",
        "model": "gpt-3.5-turbo",  # OpenAI model
        "grok_model": "grok-1",    # Grok model
        "perplexity_model": "sonar-medium-chat",  # Perplexity model
        "ollama_model": "llama3",   # Ollama model
        "temperature": 0.7,  # Default temperature for improve_text
        "openai_temperature": 0.7,  # OpenAI-specific temperature
        "grok_temperature": 0.7,    # Grok-specific temperature
        "perplexity_temperature": 0.7, # Perplexity-specific temperature
        "ollama_temperature": 0.7   # Ollama-specific temperature
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
        "temperature": 0.7,  # Default temperature for soap_note
        "openai_temperature": 0.7,  # OpenAI-specific temperature
        "grok_temperature": 0.7,    # Grok-specific temperature
        "perplexity_temperature": 0.7, # Perplexity-specific temperature
        "ollama_temperature": 0.7   # Ollama-specific temperature
    },
    "referral": {
        "prompt": "Write a referral paragraph using the SOAP Note given to you",
        "model": "gpt-3.5-turbo",  # OpenAI model
        "grok_model": "grok-1",    # Grok model
        "perplexity_model": "sonar-medium-chat",  # Perplexity model
        "ollama_model": "llama3",   # Ollama model
        "temperature": 0.7,  # Default temperature for referral
        "openai_temperature": 0.7,  # OpenAI-specific temperature
        "grok_temperature": 0.7,    # Grok-specific temperature
        "perplexity_temperature": 0.7, # Perplexity-specific temperature
        "ollama_temperature": 0.7   # Ollama-specific temperature
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
    "theme": DEFAULT_THEME
}

def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
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
