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
        logging.info(f"Finding device index for: {device_name}")
        
        # First try getting all available devices to log them
        devices = sd.query_devices()
        logging.info(f"Available devices when searching for '{device_name}':")
        for i, device in enumerate(devices):
            is_input = device['max_input_channels'] > 0
            logging.info(f"  [{i}] {device['name']} - Input: {is_input}")
        
        # Check if the name contains a device ID
        import re
        device_id_pattern = r'\(Device (\d+)\)'
        device_id_match = re.search(device_id_pattern, device_name)
        
        if device_id_match:
            # Extract the device ID from the name
            device_id = int(device_id_match.group(1))
            
            # Verify the device ID exists and is an input device
            if device_id < len(devices) and devices[device_id]['max_input_channels'] > 0:
                logging.info(f"Found device by ID: {device_id} ({devices[device_id]['name']})")
                return device_id
            else:
                logging.warning(f"Device ID {device_id} is invalid or not an input device")
        
        # If no valid device ID found, try exact name match first
        for i, device in enumerate(devices):
            if device['name'] == device_name.split(" (Device ")[0] and device['max_input_channels'] > 0:
                logging.info(f"Found device by exact name: {i} ({device['name']})")
                return i
        
        # Try partial match with special handling for Voicemeeter devices
        for i, device in enumerate(devices):
            # For Voicemeeter devices, be more strict with matching
            is_voicemeeter = "voicemeeter" in device_name.lower() or "vb-audio" in device_name.lower()
            
            if is_voicemeeter:
                # For Voicemeeter, try to match the specific device type
                # e.g., "Out A1" or "VAIO" as these are important distinctions
                name_parts = device_name.lower().split()
                device_parts = device['name'].lower().split()
                
                # Check for key Voicemeeter designations (A1, B1, VAIO, AUX, etc.)
                key_designations = ["a1", "a2", "a3", "b1", "b2", "b3", "vaio", "aux", "vban"]
                matching_designations = any(
                    designation in name_parts and designation in device_parts
                    for designation in key_designations
                )
                
                if ("voicemeeter" in device['name'].lower() and matching_designations and 
                    device['max_input_channels'] > 0):
                    logging.info(f"Found Voicemeeter device with matching designation: {i} ({device['name']})")
                    return i
            else:
                # For regular devices, a more relaxed matching is fine
                name_to_compare = device_name.split(" (Device ")[0] if " (Device " in device_name else device_name
                
                if name_to_compare in device['name'] and device['max_input_channels'] > 0:
                    logging.info(f"Found device by partial name: {i} ({device['name']})")
                    return i
        
        # If we get here, we couldn't find a matching device
        # As a last resort, get the default input device
        default_device = sd.query_devices(kind='input')
        default_index = default_device['index'] if 'index' in default_device else 0
        logging.warning(f"Could not find device '{device_name}', using default device {default_index} ({default_device['name']})")
        return default_index
        
    except Exception as e:
        logging.error(f"Error getting device index: {str(e)}", exc_info=True)
        return 0
