"""
Streaming Speech-to-Text Provider for Real-time Transcription

Implements streaming STT using Deepgram's WebSocket API for advanced voice mode.
"""

import asyncio
import json
import logging
import websockets
from typing import Optional, Callable, Dict, Any
import numpy as np
from datetime import datetime
import threading
import queue
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
from settings.settings import SETTINGS, _DEFAULT_SETTINGS


class StreamingSTTProvider:
    """Handles streaming speech-to-text for real-time transcription."""
    
    def __init__(self, api_key: str = "", language: str = "en-US"):
        """Initialize streaming STT provider.
        
        Args:
            api_key: Deepgram API key
            language: Language code for recognition
        """
        self.api_key = api_key
        self.language = language
        self.client = None
        self.connection = None
        self.is_connected = False
        
        # Callbacks
        self.on_transcript: Optional[Callable] = None
        self.on_final_transcript: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        self.on_metadata: Optional[Callable] = None
        
        # Audio buffer for smooth streaming
        self.audio_queue = queue.Queue()
        self.streaming_thread = None
        
        # Transcription state
        self.current_utterance = ""
        self.final_transcripts = []
        
    def set_callbacks(self,
                     on_transcript: Optional[Callable] = None,
                     on_final_transcript: Optional[Callable] = None,
                     on_error: Optional[Callable] = None,
                     on_metadata: Optional[Callable] = None):
        """Set callback functions for streaming events.
        
        Args:
            on_transcript: Called for interim transcripts
            on_final_transcript: Called for final transcripts
            on_error: Called on errors
            on_metadata: Called with metadata updates
        """
        self.on_transcript = on_transcript
        self.on_final_transcript = on_final_transcript
        self.on_error = on_error
        self.on_metadata = on_metadata
        
    async def start_stream(self):
        """Start the streaming STT connection."""
        try:
            # Initialize Deepgram client
            self.client = DeepgramClient(self.api_key)
            
            # Get Deepgram settings
            deepgram_settings = SETTINGS.get("deepgram", _DEFAULT_SETTINGS["deepgram"])
            
            # Configure live transcription options
            options = LiveOptions(
                model=deepgram_settings.get("model", "nova-2-medical"),
                language=deepgram_settings.get("language", self.language),
                smart_format=deepgram_settings.get("smart_format", True),
                diarize=deepgram_settings.get("diarize", False),
                profanity_filter=deepgram_settings.get("profanity_filter", False),
                redact=deepgram_settings.get("redact", False),
                # Streaming-specific options
                punctuate=True,
                interim_results=True,
                utterance_end_ms=1000,  # End utterance after 1s of silence
                vad_events=True,  # Voice activity detection events
                encoding="linear16",
                sample_rate=16000
            )
            
            # Create WebSocket connection
            self.connection = self.client.listen.websocket.v("1")
            
            # Set up event handlers
            self._setup_event_handlers()
            
            # Start the connection
            start_result = self.connection.start(options)
            if start_result:
                self.is_connected = True
                logging.info("Streaming STT connection established")
                
                # Start audio streaming thread
                self.streaming_thread = threading.Thread(target=self._stream_audio)
                self.streaming_thread.daemon = True
                self.streaming_thread.start()
                
                return True
            else:
                logging.error("Failed to start streaming STT connection")
                return False
                
        except Exception as e:
            logging.error(f"Error starting streaming STT: {e}")
            if self.on_error:
                self.on_error(str(e))
            return False
            
    def _setup_event_handlers(self):
        """Set up Deepgram event handlers."""
        
        # Handle interim results
        def on_message(client, result, **kwargs):
            sentence = result.channel.alternatives[0].transcript
            
            if len(sentence) > 0:
                # Update current utterance
                self.current_utterance = sentence
                
                # Call interim transcript callback
                if self.on_transcript:
                    self.on_transcript({
                        "transcript": sentence,
                        "is_final": False,
                        "timestamp": datetime.now(),
                        "confidence": result.channel.alternatives[0].confidence
                    })
                    
                logging.debug(f"Interim transcript: {sentence}")
                
        self.connection.on(LiveTranscriptionEvents.Transcript, on_message)
                
        # Handle final results
        def on_final_message(client, result, **kwargs):
            # Check if this is a final result
            if result.is_final:
                sentence = result.channel.alternatives[0].transcript
                
                if len(sentence) > 0:
                    # Add to final transcripts
                    self.final_transcripts.append(sentence)
                    
                    # Call final transcript callback
                    if self.on_final_transcript:
                        self.on_final_transcript({
                            "transcript": sentence,
                            "is_final": True,
                            "timestamp": datetime.now(),
                            "confidence": result.channel.alternatives[0].confidence,
                            "words": result.channel.alternatives[0].words if hasattr(result.channel.alternatives[0], 'words') else []
                        })
                        
                    logging.info(f"Final transcript: {sentence}")
                    
                    # Clear current utterance
                    self.current_utterance = ""
                    
        self.connection.on(LiveTranscriptionEvents.Transcript, on_final_message)
                    
        # Handle metadata
        def on_metadata(client, metadata, **kwargs):
            if self.on_metadata:
                self.on_metadata({
                    "duration": metadata.duration,
                    "channels": metadata.channels,
                    "sample_rate": metadata.sample_rate
                })
                
        self.connection.on(LiveTranscriptionEvents.Metadata, on_metadata)
                
        # Handle errors
        def on_error(client, error, **kwargs):
            logging.error(f"Streaming STT error: {error}")
            if self.on_error:
                self.on_error(f"Deepgram error: {error}")
                
        self.connection.on(LiveTranscriptionEvents.Error, on_error)
                
        # Handle connection close
        def on_close(client, close, **kwargs):
            logging.info("Streaming STT connection closed")
            self.is_connected = False
            
        self.connection.on(LiveTranscriptionEvents.Close, on_close)
            
    def _stream_audio(self):
        """Stream audio data from queue to Deepgram."""
        while self.is_connected:
            try:
                # Get audio from queue (with timeout to check connection)
                audio_data = self.audio_queue.get(timeout=0.1)
                
                if self.connection and self.is_connected:
                    # Convert numpy array to bytes if needed
                    if isinstance(audio_data, np.ndarray):
                        # Ensure int16 format for Deepgram
                        if audio_data.dtype != np.int16:
                            # Convert float32 to int16
                            if audio_data.dtype == np.float32:
                                audio_data = (audio_data * 32767).astype(np.int16)
                            else:
                                audio_data = audio_data.astype(np.int16)
                        
                        audio_bytes = audio_data.tobytes()
                    else:
                        audio_bytes = audio_data
                        
                    # Send to Deepgram
                    self.connection.send(audio_bytes)
                    
            except queue.Empty:
                # Send keep-alive (silence) to prevent timeout
                # Deepgram expects data within 10 seconds
                try:
                    if self.connection and self.is_connected:
                        # Send a small amount of silence (16-bit zeros)
                        silence = np.zeros(160, dtype=np.int16)  # 10ms of silence at 16kHz
                        self.connection.send(silence.tobytes())
                except Exception as e:
                    logging.debug(f"Error sending keep-alive: {e}")
                continue
            except Exception as e:
                logging.error(f"Error streaming audio: {e}")
                
    def send_audio(self, audio_data: np.ndarray):
        """Send audio data for transcription.
        
        Args:
            audio_data: Audio data as numpy array
        """
        if not self.is_connected:
            logging.warning("Cannot send audio - not connected")
            return
            
        self.audio_queue.put(audio_data)
        
    def get_full_transcript(self) -> str:
        """Get the complete transcript so far.
        
        Returns:
            Full transcript text
        """
        # Combine final transcripts with current utterance
        full_text = " ".join(self.final_transcripts)
        
        if self.current_utterance:
            full_text += " " + self.current_utterance
            
        return full_text.strip()
        
    def clear_transcript(self):
        """Clear the transcript history."""
        self.final_transcripts.clear()
        self.current_utterance = ""
        
    async def stop_stream(self):
        """Stop the streaming STT connection."""
        self.is_connected = False
        
        # Wait for streaming thread to finish
        if self.streaming_thread:
            self.streaming_thread.join(timeout=2)
            
        # Finish sending any remaining audio
        if self.connection:
            try:
                # The finish method might not be async
                result = self.connection.finish()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logging.error(f"Error finishing stream: {e}")
                
        logging.info("Streaming STT stopped")
        
    def is_active(self) -> bool:
        """Check if streaming is active.
        
        Returns:
            True if actively streaming
        """
        return self.is_connected and self.connection is not None


class StreamingSTTManager:
    """Manages multiple streaming STT providers for advanced voice mode."""
    
    def __init__(self):
        """Initialize the streaming STT manager."""
        self.providers: Dict[str, StreamingSTTProvider] = {}
        self.active_provider: Optional[str] = None
        
    def create_provider(self, provider_type: str, api_key: str, 
                       language: str = "en-US") -> StreamingSTTProvider:
        """Create a streaming STT provider.
        
        Args:
            provider_type: Type of provider (currently only 'deepgram')
            api_key: API key for the provider
            language: Language code
            
        Returns:
            StreamingSTTProvider instance
        """
        if provider_type == "deepgram":
            provider = StreamingSTTProvider(api_key, language)
            self.providers[provider_type] = provider
            return provider
        else:
            raise ValueError(f"Unsupported streaming STT provider: {provider_type}")
            
    def get_provider(self, provider_type: str) -> Optional[StreamingSTTProvider]:
        """Get a streaming STT provider.
        
        Args:
            provider_type: Type of provider
            
        Returns:
            Provider instance or None
        """
        return self.providers.get(provider_type)
        
    def set_active(self, provider_type: str):
        """Set the active streaming STT provider.
        
        Args:
            provider_type: Type of provider to activate
        """
        if provider_type in self.providers:
            self.active_provider = provider_type
        else:
            raise ValueError(f"Provider {provider_type} not found")
            
    def get_active(self) -> Optional[StreamingSTTProvider]:
        """Get the active streaming STT provider.
        
        Returns:
            Active provider or None
        """
        if self.active_provider:
            return self.providers.get(self.active_provider)
        return None
        
    async def stop_all(self):
        """Stop all streaming STT providers."""
        for provider in self.providers.values():
            if provider.is_active():
                await provider.stop_stream()
                
    def clear_all(self):
        """Clear all providers."""
        asyncio.run(self.stop_all())
        self.providers.clear()
        self.active_provider = None