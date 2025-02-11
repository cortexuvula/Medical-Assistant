import os
import json
import logging

SETTINGS_FILE = "settings.json"
_DEFAULT_SETTINGS = {
    "refine_text": {
        "model": "gpt-3.5-turbo"
    },
    "improve_text": {
        "model": "gpt-3.5-turbo"
    }
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
