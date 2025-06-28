"""
Voice Activity Detection (VAD) for Advanced Voice Mode

Detects speech in audio streams to enable natural turn-taking and reduce unnecessary processing.
"""

import logging
import numpy as np
import webrtcvad
from collections import deque
from typing import Optional, Callable, Tuple
import struct


class VoiceActivityDetector:
    """Detects voice activity in audio streams using WebRTC VAD."""
    
    def __init__(self, sample_rate: int = 16000, frame_duration_ms: int = 30,
                 aggressiveness: int = 3):
        """Initialize Voice Activity Detector.
        
        Args:
            sample_rate: Audio sample rate (8000, 16000, 32000, or 48000 Hz)
            frame_duration_ms: Frame duration (10, 20, or 30 ms)
            aggressiveness: VAD aggressiveness (0-3, higher = more aggressive)
        """
        # Validate parameters
        if sample_rate not in [8000, 16000, 32000, 48000]:
            raise ValueError(f"Sample rate {sample_rate} not supported. Use 8000, 16000, 32000, or 48000")
        if frame_duration_ms not in [10, 20, 30]:
            raise ValueError(f"Frame duration {frame_duration_ms}ms not supported. Use 10, 20, or 30")
        if aggressiveness not in [0, 1, 2, 3]:
            raise ValueError(f"Aggressiveness {aggressiveness} not supported. Use 0-3")
            
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.frame_size = int(sample_rate * frame_duration_ms / 1000)
        
        # Initialize WebRTC VAD
        self.vad = webrtcvad.Vad(aggressiveness)
        
        # Speech state tracking
        self.is_speech = False
        self.speech_start_time = None
        self.speech_end_time = None
        
        # Ring buffer for smoothing decisions
        self.ring_buffer_size = 10  # Number of frames to consider
        self.ring_buffer = deque(maxlen=self.ring_buffer_size)
        
        # Thresholds for speech detection
        self.speech_threshold = 0.7  # 70% of frames must be speech to trigger
        self.silence_threshold = 0.3  # 30% or less to trigger silence
        
        # Callbacks
        self.on_speech_start: Optional[Callable] = None
        self.on_speech_end: Optional[Callable] = None
        
        # Audio buffer for incomplete frames
        self.audio_buffer = np.array([], dtype=np.int16)
        
    def process_audio(self, audio_data: np.ndarray) -> bool:
        """Process audio data and detect voice activity.
        
        Args:
            audio_data: Audio data as numpy array (float32 or int16)
            
        Returns:
            True if speech is detected in the current state
        """
        # Convert to int16 if needed
        if audio_data.dtype == np.float32:
            audio_data = (audio_data * 32767).astype(np.int16)
        elif audio_data.dtype != np.int16:
            audio_data = audio_data.astype(np.int16)
            
        # Add to buffer
        self.audio_buffer = np.concatenate([self.audio_buffer, audio_data])
        
        # Process complete frames
        while len(self.audio_buffer) >= self.frame_size:
            # Extract frame
            frame = self.audio_buffer[:self.frame_size]
            self.audio_buffer = self.audio_buffer[self.frame_size:]
            
            # Process frame
            self._process_frame(frame)
            
        return self.is_speech
        
    def _process_frame(self, frame: np.ndarray):
        """Process a single audio frame.
        
        Args:
            frame: Audio frame as int16 numpy array
        """
        # Convert to bytes for WebRTC VAD
        frame_bytes = frame.tobytes()
        
        # Run VAD
        try:
            is_speech = self.vad.is_speech(frame_bytes, self.sample_rate)
        except Exception as e:
            logging.error(f"VAD error: {e}")
            is_speech = False
            
        # Add to ring buffer
        self.ring_buffer.append(is_speech)
        
        # Calculate speech ratio in buffer
        if len(self.ring_buffer) >= self.ring_buffer_size:
            speech_ratio = sum(self.ring_buffer) / len(self.ring_buffer)
            
            # Update speech state
            self._update_speech_state(speech_ratio)
            
    def _update_speech_state(self, speech_ratio: float):
        """Update speech state based on ratio.
        
        Args:
            speech_ratio: Ratio of speech frames in ring buffer
        """
        import time
        
        if not self.is_speech and speech_ratio >= self.speech_threshold:
            # Speech started
            self.is_speech = True
            self.speech_start_time = time.time()
            
            logging.debug("Speech started")
            
            if self.on_speech_start:
                self.on_speech_start()
                
        elif self.is_speech and speech_ratio <= self.silence_threshold:
            # Speech ended
            self.is_speech = False
            self.speech_end_time = time.time()
            
            # Calculate speech duration
            if self.speech_start_time:
                duration = self.speech_end_time - self.speech_start_time
                logging.debug(f"Speech ended (duration: {duration:.2f}s)")
                
                if self.on_speech_end:
                    self.on_speech_end(duration)
                    
    def reset(self):
        """Reset VAD state."""
        self.is_speech = False
        self.speech_start_time = None
        self.speech_end_time = None
        self.ring_buffer.clear()
        self.audio_buffer = np.array([], dtype=np.int16)
        
    def set_aggressiveness(self, level: int):
        """Set VAD aggressiveness level.
        
        Args:
            level: Aggressiveness (0-3)
        """
        if level not in [0, 1, 2, 3]:
            raise ValueError(f"Invalid aggressiveness level: {level}")
            
        self.vad.set_mode(level)
        
    def get_state(self) -> dict:
        """Get current VAD state.
        
        Returns:
            State dictionary
        """
        return {
            "is_speech": self.is_speech,
            "buffer_size": len(self.ring_buffer),
            "speech_ratio": sum(self.ring_buffer) / len(self.ring_buffer) if self.ring_buffer else 0
        }


class EnergyBasedVAD:
    """Simple energy-based VAD for environments where WebRTC VAD is not available."""
    
    def __init__(self, sample_rate: int = 16000, frame_duration_ms: int = 30):
        """Initialize energy-based VAD.
        
        Args:
            sample_rate: Audio sample rate
            frame_duration_ms: Frame duration in milliseconds
        """
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.frame_size = int(sample_rate * frame_duration_ms / 1000)
        
        # Energy thresholds
        self.energy_threshold = 0.01  # Initial threshold
        self.background_energy = 0.001  # Background noise estimate
        self.alpha = 0.1  # Smoothing factor for background energy
        
        # State
        self.is_speech = False
        self.frame_energies = deque(maxlen=50)  # Keep last 50 frame energies
        
        # Callbacks
        self.on_speech_start: Optional[Callable] = None
        self.on_speech_end: Optional[Callable] = None
        
        # Audio buffer
        self.audio_buffer = np.array([], dtype=np.float32)
        
    def process_audio(self, audio_data: np.ndarray) -> bool:
        """Process audio and detect voice activity based on energy.
        
        Args:
            audio_data: Audio data as numpy array
            
        Returns:
            True if speech is detected
        """
        # Convert to float32 if needed
        if audio_data.dtype != np.float32:
            if audio_data.dtype == np.int16:
                audio_data = audio_data.astype(np.float32) / 32768.0
            else:
                audio_data = audio_data.astype(np.float32)
                
        # Add to buffer
        self.audio_buffer = np.concatenate([self.audio_buffer, audio_data])
        
        # Process complete frames
        while len(self.audio_buffer) >= self.frame_size:
            # Extract frame
            frame = self.audio_buffer[:self.frame_size]
            self.audio_buffer = self.audio_buffer[self.frame_size:]
            
            # Calculate frame energy
            energy = np.sqrt(np.mean(frame ** 2))
            self.frame_energies.append(energy)
            
            # Update background energy estimate
            if not self.is_speech:
                self.background_energy = (1 - self.alpha) * self.background_energy + self.alpha * energy
                
            # Update threshold dynamically
            self.energy_threshold = max(0.01, 3 * self.background_energy)
            
            # Detect speech
            self._detect_speech(energy)
            
        return self.is_speech
        
    def _detect_speech(self, energy: float):
        """Detect speech based on energy.
        
        Args:
            energy: Frame energy
        """
        import time
        
        # Simple threshold-based detection with hysteresis
        if not self.is_speech and energy > self.energy_threshold * 1.5:
            # Speech started
            self.is_speech = True
            
            logging.debug(f"Speech started (energy: {energy:.4f}, threshold: {self.energy_threshold:.4f})")
            
            if self.on_speech_start:
                self.on_speech_start()
                
        elif self.is_speech and energy < self.energy_threshold * 0.7:
            # Check if energy has been low for several frames
            recent_energies = list(self.frame_energies)[-5:]
            if all(e < self.energy_threshold for e in recent_energies):
                # Speech ended
                self.is_speech = False
                
                logging.debug("Speech ended")
                
                if self.on_speech_end:
                    self.on_speech_end(0)  # Duration not tracked in this simple implementation
                    
    def reset(self):
        """Reset VAD state."""
        self.is_speech = False
        self.frame_energies.clear()
        self.audio_buffer = np.array([], dtype=np.float32)
        
    def get_energy_stats(self) -> dict:
        """Get energy statistics.
        
        Returns:
            Energy statistics
        """
        if self.frame_energies:
            energies = np.array(self.frame_energies)
            return {
                "current_threshold": self.energy_threshold,
                "background_energy": self.background_energy,
                "mean_energy": np.mean(energies),
                "max_energy": np.max(energies),
                "min_energy": np.min(energies)
            }
        return {
            "current_threshold": self.energy_threshold,
            "background_energy": self.background_energy
        }


class HybridVAD:
    """Hybrid VAD that combines multiple detection methods for robustness."""
    
    def __init__(self, sample_rate: int = 16000, frame_duration_ms: int = 30):
        """Initialize hybrid VAD.
        
        Args:
            sample_rate: Audio sample rate
            frame_duration_ms: Frame duration
        """
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        
        # Initialize sub-detectors
        try:
            self.webrtc_vad = VoiceActivityDetector(sample_rate, frame_duration_ms)
            self.use_webrtc = True
        except Exception as e:
            logging.warning(f"WebRTC VAD not available: {e}")
            self.webrtc_vad = None
            self.use_webrtc = False
            
        self.energy_vad = EnergyBasedVAD(sample_rate, frame_duration_ms)
        
        # State
        self.is_speech = False
        
        # Callbacks
        self.on_speech_start: Optional[Callable] = None
        self.on_speech_end: Optional[Callable] = None
        
        # Set up internal callbacks
        self._setup_callbacks()
        
    def _setup_callbacks(self):
        """Set up callbacks for sub-detectors."""
        def on_start():
            if not self.is_speech:
                self.is_speech = True
                if self.on_speech_start:
                    self.on_speech_start()
                    
        def on_end(duration):
            # Only trigger end if both detectors agree
            webrtc_speech = self.webrtc_vad.is_speech if self.webrtc_vad else False
            energy_speech = self.energy_vad.is_speech
            
            if not webrtc_speech and not energy_speech:
                self.is_speech = False
                if self.on_speech_end:
                    self.on_speech_end(duration)
                    
        # Set callbacks
        if self.webrtc_vad:
            self.webrtc_vad.on_speech_start = on_start
            self.webrtc_vad.on_speech_end = on_end
            
        self.energy_vad.on_speech_start = on_start
        self.energy_vad.on_speech_end = on_end
        
    def process_audio(self, audio_data: np.ndarray) -> bool:
        """Process audio with hybrid detection.
        
        Args:
            audio_data: Audio data
            
        Returns:
            True if speech detected
        """
        # Process with both detectors
        energy_result = self.energy_vad.process_audio(audio_data.copy())
        
        if self.webrtc_vad:
            webrtc_result = self.webrtc_vad.process_audio(audio_data.copy())
            # Combine results (OR operation for sensitivity)
            self.is_speech = webrtc_result or energy_result
        else:
            self.is_speech = energy_result
            
        return self.is_speech
        
    def reset(self):
        """Reset all detectors."""
        self.is_speech = False
        self.energy_vad.reset()
        if self.webrtc_vad:
            self.webrtc_vad.reset()
            
    def get_state(self) -> dict:
        """Get combined state information.
        
        Returns:
            State dictionary
        """
        state = {
            "is_speech": self.is_speech,
            "energy_stats": self.energy_vad.get_energy_stats()
        }
        
        if self.webrtc_vad:
            state["webrtc_state"] = self.webrtc_vad.get_state()
            
        return state