import pyaudio

def get_valid_microphones() -> list[str]:
    pa = pyaudio.PyAudio()
    valid_names = []
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info.get("maxInputChannels", 0) > 0 and any(
            k in info.get("name", "").lower() for k in ["microphone", "mic", "input", "usb"]
        ):
            valid_names.append(info.get("name", ""))
    pa.terminate()
    return valid_names
