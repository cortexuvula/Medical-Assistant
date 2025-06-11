#!/usr/bin/env python3
"""
Test script to diagnose audio recording issues.
Run this to test if audio is being captured correctly.
"""

import numpy as np
import sounddevice as sd
from pydub import AudioSegment
import time
import os

def test_recording():
    print("Audio Recording Test")
    print("=" * 50)
    
    # List audio devices
    print("\nAvailable audio devices:")
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            print(f"{i}: {device['name']} (Channels: {device['max_input_channels']})")
    
    # Get default device
    default_device = sd.default.device[0]
    print(f"\nDefault input device: {default_device}")
    
    # Test parameters
    sample_rate = 48000
    duration = 3  # seconds
    
    print(f"\nRecording {duration} seconds of audio...")
    print("Please speak into your microphone...")
    
    # Record audio
    recording = sd.rec(int(duration * sample_rate), 
                      samplerate=sample_rate, 
                      channels=1, 
                      dtype='float32')
    sd.wait()  # Wait for recording to complete
    
    print(f"\nRecording complete!")
    print(f"Recording shape: {recording.shape}")
    print(f"Recording dtype: {recording.dtype}")
    print(f"Max amplitude: {np.abs(recording).max():.6f}")
    print(f"Mean amplitude: {np.abs(recording).mean():.6f}")
    
    # Check if audio is silent
    if np.abs(recording).max() < 0.001:
        print("\nWARNING: Recording appears to be silent!")
        print("Please check your microphone settings and permissions.")
    
    # Convert to AudioSegment
    print("\nConverting to AudioSegment...")
    
    # Flatten array if needed
    if len(recording.shape) > 1:
        recording = recording.flatten()
    
    # Convert to int16
    audio_clipped = np.clip(recording, -1.0, 1.0)
    audio_int16 = (audio_clipped * 32767).astype(np.int16)
    
    # Create AudioSegment
    audio_segment = AudioSegment(
        data=audio_int16.tobytes(),
        sample_width=2,
        frame_rate=sample_rate,
        channels=1
    )
    
    print(f"AudioSegment created: {len(audio_segment)}ms duration")
    
    # Save test file
    test_file = "test_recording.mp3"
    audio_segment.export(test_file, format="mp3")
    print(f"\nTest audio saved to: {test_file}")
    print(f"File size: {os.path.getsize(test_file)} bytes")
    
    # Play back the recording (optional)
    try:
        print("\nPlaying back recording...")
        sd.play(recording, sample_rate)
        sd.wait()
        print("Playback complete!")
    except Exception as e:
        print(f"Playback failed: {e}")
    
    print("\n" + "=" * 50)
    print("Test complete! Check the test_recording.mp3 file.")
    print("If the file contains only static, there may be an audio input issue.")

if __name__ == "__main__":
    test_recording()