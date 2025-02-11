import pyaudio

def get_valid_microphones() -> list[str]:
    pa = pyaudio.PyAudio()
    devices = [pa.get_device_info_by_index(i) for i in range(pa.get_device_count())]
    valid_names = [
        device["name"]
        for device in devices
        if device.get("maxInputChannels", 0) > 0 and any(
            keyword in device.get("name", "").lower() for keyword in ["microphone", "mic", "input", "usb"]
        )
    ]
    pa.terminate()
    return valid_names
