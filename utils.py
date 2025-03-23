import soundcard

def get_valid_microphones() -> list[str]:
    """Get list of valid microphone names using soundcard."""
    try:
        # Get all microphones
        mics = soundcard.all_microphones()
        
        # Extract names
        return [mic.name for mic in mics]
    except Exception:
        # Return empty list on error
        return []
