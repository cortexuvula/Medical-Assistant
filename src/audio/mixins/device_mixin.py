"""
Audio Device Management Mixin

Provides device enumeration and management for the AudioHandler class.
"""

import logging
import platform
import re
from typing import List, Dict, Any, Optional, Tuple

# Import audio libraries conditionally
try:
    import soundcard
    SOUNDCARD_AVAILABLE = True
except (ImportError, AssertionError, OSError):
    soundcard = None
    SOUNDCARD_AVAILABLE = False

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except (ImportError, OSError):
    sd = None
    SOUNDDEVICE_AVAILABLE = False

from audio.constants import SAMPLE_RATE_48K


class DeviceMixin:
    """Mixin providing device management methods for AudioHandler.

    This mixin expects the following attributes on the class:
    - sample_rate: Current sample rate
    - channels: Current channel count
    """

    def get_input_devices(self) -> List[Dict[str, Any]]:
        """Get a list of available input devices using soundcard.

        Returns:
            List of dictionaries with device information (name, id, channels, object)
        """
        try:
            devices = []
            if not SOUNDCARD_AVAILABLE:
                logging.warning("Soundcard not available, returning empty device list")
                return []

            mics = soundcard.all_microphones(include_loopback=False)

            for i, mic in enumerate(mics):
                device_info = {
                    "id": i,
                    "name": mic.name,
                    "channels": mic.channels,
                    "object": mic
                }
                devices.append(device_info)

            return devices
        except Exception as e:
            logging.error(f"Error getting input devices: {str(e)}", exc_info=True)
            return []

    def _resolve_device_index(self, device_name: str) -> Optional[int]:
        """Resolve device name to sounddevice index.

        Args:
            device_name: The target device name string.

        Returns:
            Device index or None if not found.
        """
        if not SOUNDDEVICE_AVAILABLE:
            logging.error("Sounddevice not available, cannot resolve device index")
            return None

        # Sanitize device name to prevent log injection attacks
        from utils.validation import sanitize_device_name
        device_name = sanitize_device_name(device_name)
        logging.debug(f"Resolving sounddevice index for: '{device_name}'")

        devices = sd.query_devices()
        device_id = None
        current_platform = platform.system().lower()

        # Build list of input devices
        input_device_indices = []
        for i, dev in enumerate(devices):
            is_input = dev['max_input_channels'] > 0
            if is_input:
                input_device_indices.append(i)

        # 1. Try exact name match
        for i in input_device_indices:
            if devices[i]['name'] == device_name:
                device_id = i
                logging.debug(f"Exact match found: Index={device_id}, Name='{devices[i]['name']}'")
                break

        # 2. If no exact match, try case-insensitive match
        if device_id is None:
            for i in input_device_indices:
                if devices[i]['name'].lower() == device_name.lower():
                    device_id = i
                    logging.debug(f"Case-insensitive match found: Index={device_id}, Name='{devices[i]['name']}'")
                    break

        # 3. Try partial match
        if device_id is None:
            for i in input_device_indices:
                if device_name in devices[i]['name'] or devices[i]['name'] in device_name:
                    device_id = i
                    logging.debug(f"Partial match found: Index={device_id}, Name='{devices[i]['name']}'")
                    break

        # 3.5 Platform-specific matching
        if device_id is None and current_platform == 'windows':
            # On Windows, try matching without WASAPI/WDM suffixes
            device_name_clean = device_name.replace(' (Device ', '|').split('|')[0]
            for i in input_device_indices:
                dev_name = devices[i]['name']
                dev_name_clean = dev_name
                for suffix in [' (Windows WASAPI)', ' (Windows WDM-KS)', ' (Windows DirectSound)']:
                    dev_name_clean = dev_name_clean.replace(suffix, '')

                if device_name_clean.lower() in dev_name_clean.lower() or dev_name_clean.lower() in device_name_clean.lower():
                    device_id = i
                    logging.debug(f"Windows platform match found: Index={device_id}, Name='{devices[i]['name']}'")
                    break

        # 4. Special handling for device names with "(Device X)" suffix
        if device_id is None and "(Device " in device_name:
            try:
                match = re.search(r'\(Device (\d+)\)', device_name)
                if match:
                    potential_id = int(match.group(1))
                    if potential_id in input_device_indices:
                        device_id = potential_id
                        logging.info(f"Extracted device index from name: Index={device_id}, Name='{devices[device_id]['name']}'")
            except Exception as e:
                logging.debug(f"Failed to extract device index from name: {e}")

        if device_id is None:
            logging.error(f"Could not find device '{device_name}' in sounddevice list")

        return device_id

    def _setup_audio_parameters(self, device_id: int) -> Tuple[int, int]:
        """Setup audio parameters for the device.

        Args:
            device_id: The sounddevice device index.

        Returns:
            Tuple of (channels, sample_rate).
        """
        if not SOUNDDEVICE_AVAILABLE:
            logging.error("Sounddevice not available")
            return 1, SAMPLE_RATE_48K

        device_info = sd.query_devices(device_id)

        # Determine optimal channel count
        channels = 1  # Default to mono
        max_channels = device_info.get('max_input_channels', 1)

        try:
            if max_channels >= 1:
                channels = 1
            else:
                logging.warning(f"Device {device_info['name']} reports {max_channels} input channels")
        except Exception as e:
            logging.warning(f"Error determining channel count for {device_info['name']}: {e}. Defaulting to {channels}.")

        self.channels = channels
        # Use 48000 Hz for better quality, falling back to device default if not supported
        device_default = int(device_info.get('default_samplerate', SAMPLE_RATE_48K))
        self.sample_rate = SAMPLE_RATE_48K if device_default >= SAMPLE_RATE_48K else device_default

        return channels, self.sample_rate


__all__ = ["DeviceMixin"]
