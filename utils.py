import soundcard
import sounddevice as sd
import logging

def get_valid_microphones() -> list[str]:
    """Get list of valid microphone names using both soundcard and sounddevice."""
    mic_names = []
    
    try:
        # First try using soundcard
        soundcard_mics = soundcard.all_microphones()
        sc_names = [mic.name for mic in soundcard_mics]
        
        # Then get sounddevice microphones
        sd_devices = sd.query_devices()
        sd_names = []
        
        for i, device in enumerate(sd_devices):
            # Only include input devices
            if device['max_input_channels'] > 0:
                # Add device ID to name for proper identification
                name = f"{device['name']} (Device {i})"
                sd_names.append(name)
        
        # Combine both lists, prioritizing sounddevice for Voicemeeter
        if sd_names:
            # Put Voicemeeter devices at the top of the list for easier selection
            voicemeeter_names = [name for name in sd_names if 'voicemeeter' in name.lower() or 'vb-audio' in name.lower()]
            other_names = [name for name in sd_names if not ('voicemeeter' in name.lower() or 'vb-audio' in name.lower())]
            
            # Build the final list with Voicemeeter devices first
            mic_names = voicemeeter_names + other_names + sc_names
        else:
            mic_names = sc_names
            
        # Log the found microphones
        logging.info(f"Found {len(mic_names)} microphones")
        for i, name in enumerate(mic_names):
            logging.info(f"  Mic {i}: {name}")
            
        return mic_names
    except Exception as e:
        # Log the error and return empty list
        logging.error(f"Error getting microphones: {str(e)}", exc_info=True)
        return []

def get_device_index_from_name(device_name: str) -> int:
    """Get device index from name for sounddevice.
    
    For names that include a device ID (e.g., "Device 3"), extract that ID.
    Otherwise, search for a matching device by name.
    
    Args:
        device_name: Name of the device to find
        
    Returns:
        Device index or 0 if not found
    """
    try:
        # Check if the name contains a device ID
        if "Device " in device_name:
            # Extract the device ID from the name
            device_id_str = device_name.split("Device ")[-1].split(")")[0]
            try:
                return int(device_id_str)
            except ValueError:
                pass
        
        # If no device ID found, search by name
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            # Remove the "Device X" part if present for comparison
            name_to_compare = device_name.split(" (Device ")[0] if " (Device " in device_name else device_name
            
            if name_to_compare in device['name'] and device['max_input_channels'] > 0:
                return i
                
        # If not found, log warning and return 0 (default device)
        logging.warning(f"Could not find device '{device_name}', using default device (0)")
        return 0
        
    except Exception as e:
        logging.error(f"Error getting device index: {str(e)}", exc_info=True)
        return 0
