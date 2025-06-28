"""
Voice Interaction Manager for Advanced Voice Mode

Orchestrates the conversation flow between STT, AI, and TTS for real-time voice interactions.
"""

import logging
import asyncio
import threading
from typing import Optional, Dict, Any, List, Callable
from enum import Enum
import time
from datetime import datetime
import numpy as np
from queue import Queue
import json
import os

from .streaming_stt import StreamingSTTProvider
from .tts_providers import TTSManager
from .audio_playback import AudioPlaybackManager
from .websocket_server import AudioWebSocketServer
from .websocket_client import AudioWebSocketClient
from ai.ai import call_ai
from settings.settings import SETTINGS


class ConversationState(Enum):
    """States of the voice conversation."""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"


class VoiceInteractionManager:
    """Manages voice interactions for advanced voice mode."""
    
    def __init__(self, audio_handler=None):
        """Initialize voice interaction manager.
        
        Args:
            audio_handler: Audio handler for recording (optional)
        """
        self.audio_handler = audio_handler
        
        # Components
        self.stt_provider: Optional[StreamingSTTProvider] = None
        self.tts_manager = TTSManager()
        self.playback_manager = AudioPlaybackManager()
        self.websocket_server: Optional[AudioWebSocketServer] = None
        self.websocket_client: Optional[AudioWebSocketClient] = None
        
        # State management
        self.state = ConversationState.IDLE
        self.is_active = False
        self.session_id = None
        
        # Conversation context
        self.conversation_history: List[Dict[str, Any]] = []
        self.medical_context = {}
        self.current_utterance = ""
        self.last_ai_response = ""
        
        # Settings - load from saved voice mode configuration
        voice_mode_config = SETTINGS.get("voice_mode", {})
        
        # Determine which model to use based on provider
        ai_provider = voice_mode_config.get("ai_provider", SETTINGS.get("ai_provider", "openai"))
        if ai_provider == "openai":
            ai_model = voice_mode_config.get("openai_model", "gpt-4")
        elif ai_provider == "perplexity":
            ai_model = voice_mode_config.get("perplexity_model", "sonar-reasoning-pro")
        elif ai_provider == "grok":
            ai_model = voice_mode_config.get("grok_model", "grok-1")
        elif ai_provider == "ollama":
            ai_model = voice_mode_config.get("ollama_model", "llama3")
        elif ai_provider == "anthropic":
            ai_model = voice_mode_config.get("anthropic_model", "claude-3-sonnet-20240229")
        else:
            ai_model = voice_mode_config.get("ai_model", "gpt-4")
        
        self.settings = {
            "ai_provider": ai_provider,
            "ai_model": ai_model,
            "ai_temperature": voice_mode_config.get("ai_temperature", 0.7),
            "tts_provider": voice_mode_config.get("tts_provider", "openai"),
            "tts_voice": voice_mode_config.get("tts_voice", "nova"),
            "stt_provider": voice_mode_config.get("stt_provider", "deepgram"),
            "enable_interruptions": voice_mode_config.get("enable_interruptions", True),
            "response_delay_ms": voice_mode_config.get("response_delay_ms", 500),
            "max_context_length": voice_mode_config.get("max_context_length", 4000),
            "system_prompt": voice_mode_config.get("system_prompt", 
                """You are a medical AI assistant in voice mode. Provide helpful, conversational responses about medical topics. Keep responses concise and natural for voice interaction. When discussing medical conditions, be clear about when professional medical advice is needed.""")
        }
        
        # Callbacks
        self.on_state_change: Optional[Callable] = None
        self.on_transcript: Optional[Callable] = None
        self.on_ai_response: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        
        # Processing queue
        self.processing_queue = Queue()
        self.processing_thread = None
        
        # Voice activity detection
        self.vad_enabled = True
        self.silence_threshold = 1.5  # seconds
        self.last_speech_time = time.time()
        
    def configure(self, settings: Dict[str, Any]):
        """Update configuration settings.
        
        Args:
            settings: Configuration dictionary
        """
        self.settings.update(settings)
        logging.info(f"Updated voice interaction settings: {settings}")
        
    async def initialize(self, use_websocket: bool = False):
        """Initialize voice interaction components.
        
        Args:
            use_websocket: Whether to use WebSocket for audio streaming
        """
        try:
            # Initialize STT
            if self.settings["stt_provider"] == "deepgram":
                api_key = os.getenv("DEEPGRAM_API_KEY", "")
                if not api_key:
                    raise ValueError("Deepgram API key not found")
                    
                self.stt_provider = StreamingSTTProvider(api_key)
                self.stt_provider.set_callbacks(
                    on_transcript=self._handle_interim_transcript,
                    on_final_transcript=self._handle_final_transcript,
                    on_error=self._handle_stt_error
                )
                
            # Initialize TTS
            tts_provider = self.settings["tts_provider"]
            if tts_provider == "elevenlabs":
                api_key = os.getenv("ELEVENLABS_API_KEY", "")
            elif tts_provider == "openai":
                api_key = os.getenv("OPENAI_API_KEY", "")
            else:
                raise ValueError(f"Unsupported TTS provider: {tts_provider}")
                
            if not api_key:
                raise ValueError(f"{tts_provider} API key not found")
                
            self.tts_manager.create_provider(tts_provider, api_key)
            self.tts_manager.set_active(tts_provider)
            
            # Initialize WebSocket if requested
            if use_websocket:
                await self._init_websocket()
                
            # Set up audio playback callbacks
            self.playback_manager.on_playback_start = self._handle_playback_start
            self.playback_manager.on_playback_end = self._handle_playback_end
            self.playback_manager.on_playback_error = self._handle_playback_error
            
            # Start processing thread
            self.processing_thread = threading.Thread(target=self._process_queue)
            self.processing_thread.daemon = True
            self.processing_thread.start()
            
            logging.info("Voice interaction manager initialized")
            
        except Exception as e:
            logging.error(f"Failed to initialize voice interaction: {e}")
            if self.on_error:
                self.on_error(f"Initialization error: {e}")
            raise
            
    async def _init_websocket(self):
        """Initialize WebSocket for remote audio streaming."""
        # Start WebSocket server
        self.websocket_server = AudioWebSocketServer()
        self.websocket_server.register_handler("audio_data", self._handle_websocket_audio)
        self.websocket_server.register_handler("start_session", self._handle_websocket_start)
        self.websocket_server.register_handler("end_session", self._handle_websocket_end)
        self.websocket_server.start()
        
    async def start_session(self, session_data: Optional[Dict[str, Any]] = None):
        """Start a voice interaction session.
        
        Args:
            session_data: Optional session configuration
        """
        if self.is_active:
            logging.warning("Voice session already active")
            return
            
        try:
            self.session_id = f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.is_active = True
            
            # Clear conversation history
            self.conversation_history.clear()
            
            # Update medical context if provided
            if session_data and "medical_context" in session_data:
                self.medical_context = session_data["medical_context"]
                
            # Start STT streaming
            if self.stt_provider:
                await self.stt_provider.start_stream()
                
            # Set initial state
            self._set_state(ConversationState.LISTENING)
            
            logging.info(f"Started voice session: {self.session_id}")
            
        except Exception as e:
            logging.error(f"Failed to start voice session: {e}")
            self.is_active = False
            if self.on_error:
                self.on_error(f"Session start error: {e}")
                
    async def end_session(self):
        """End the current voice interaction session."""
        if not self.is_active:
            return
            
        try:
            self.is_active = False
            
            # Stop STT streaming
            if self.stt_provider:
                await self.stt_provider.stop_stream()
                
            # Stop any ongoing playback
            if self.playback_manager.is_active():
                self.playback_manager.stop()
                
            # Set state to idle
            self._set_state(ConversationState.IDLE)
            
            # Save conversation history if needed
            self._save_conversation_history()
            
            logging.info(f"Ended voice session: {self.session_id}")
            
        except Exception as e:
            logging.error(f"Error ending voice session: {e}")
            
    def process_audio(self, audio_data: np.ndarray):
        """Process incoming audio data.
        
        Args:
            audio_data: Audio data as numpy array
        """
        if not self.is_active or self.state != ConversationState.LISTENING:
            return
            
        # Update last speech time for VAD
        if self.vad_enabled and self._detect_speech(audio_data):
            self.last_speech_time = time.time()
            
        # Send to STT
        if self.stt_provider and self.stt_provider.is_active():
            self.stt_provider.send_audio(audio_data)
            
    def _detect_speech(self, audio_data: np.ndarray) -> bool:
        """Simple voice activity detection.
        
        Args:
            audio_data: Audio data
            
        Returns:
            True if speech detected
        """
        # Calculate RMS energy
        if len(audio_data) == 0:
            return False
            
        # Handle potential invalid values
        try:
            # Filter out invalid values (nan, inf)
            valid_data = audio_data[np.isfinite(audio_data)]
            if len(valid_data) == 0:
                return False
                
            rms = np.sqrt(np.mean(valid_data ** 2))
            
            # Simple threshold-based detection
            # This should be replaced with proper VAD (e.g., webrtcvad)
            return rms > 0.01
        except Exception as e:
            logging.warning(f"Error calculating RMS: {e}")
            return False
        
    def _handle_interim_transcript(self, data: Dict[str, Any]):
        """Handle interim transcript from STT.
        
        Args:
            data: Transcript data
        """
        self.current_utterance = data["transcript"]
        
        # Notify UI
        if self.on_transcript:
            self.on_transcript({
                "text": self.current_utterance,
                "is_final": False,
                "timestamp": data["timestamp"]
            })
            
    def _handle_final_transcript(self, data: Dict[str, Any]):
        """Handle final transcript from STT.
        
        Args:
            data: Transcript data
        """
        transcript = data["transcript"]
        
        # Add to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": transcript,
            "timestamp": data["timestamp"]
        })
        
        # Notify UI
        if self.on_transcript:
            self.on_transcript({
                "text": transcript,
                "is_final": True,
                "timestamp": data["timestamp"]
            })
            
        # Queue for processing
        self.processing_queue.put({
            "type": "user_input",
            "text": transcript,
            "timestamp": data["timestamp"]
        })
        
        # Clear current utterance
        self.current_utterance = ""
        
    def _handle_stt_error(self, error: str):
        """Handle STT error.
        
        Args:
            error: Error message
        """
        logging.error(f"STT error: {error}")
        if self.on_error:
            self.on_error(f"Speech recognition error: {error}")
            
    def _process_queue(self):
        """Process queued user inputs."""
        while True:
            try:
                # Get item from queue
                item = self.processing_queue.get(timeout=1)
                
                if item["type"] == "user_input":
                    # Process user input
                    asyncio.run(self._process_user_input(item["text"]))
                    
            except:
                # Queue empty or timeout
                continue
                
    async def _process_user_input(self, text: str):
        """Process user input and generate response.
        
        Args:
            text: User input text
        """
        try:
            # Set processing state
            self._set_state(ConversationState.PROCESSING)
            
            # Build context
            context = self._build_conversation_context()
            
            # Add current input
            prompt = f"{context}\nUser: {text}\nAssistant:"
            
            # Get AI response
            response = await self._get_ai_response(prompt)
            
            # Add to conversation history
            self.conversation_history.append({
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now()
            })
            
            # Notify UI
            if self.on_ai_response:
                self.on_ai_response({
                    "text": response,
                    "timestamp": datetime.now()
                })
                
            # Synthesize and play response
            await self._speak_response(response)
            
        except Exception as e:
            logging.error(f"Error processing user input: {e}")
            self._set_state(ConversationState.LISTENING)
            
    def _build_conversation_context(self) -> str:
        """Build conversation context for AI.
        
        Returns:
            Context string
        """
        context_parts = [self.settings["system_prompt"]]
        
        # Add medical context if available
        if self.medical_context:
            context_parts.append(f"\nMedical Context:\n{json.dumps(self.medical_context, indent=2)}")
            
        # Add conversation history (limited by max_context_length)
        history_text = ""
        for entry in self.conversation_history[-10:]:  # Last 10 exchanges
            role = entry["role"].capitalize()
            content = entry["content"]
            history_text += f"\n{role}: {content}"
            
        # Truncate if needed
        max_length = self.settings["max_context_length"]
        if len(history_text) > max_length:
            history_text = "..." + history_text[-max_length:]
            
        context_parts.append(history_text)
        
        return "\n".join(context_parts)
        
    async def _get_ai_response(self, prompt: str) -> str:
        """Get AI response for prompt.
        
        Args:
            prompt: AI prompt
            
        Returns:
            AI response text
        """
        try:
            # Use configured AI settings
            provider = self.settings["ai_provider"]
            model = self.settings["ai_model"]
            temperature = self.settings["ai_temperature"]
            
            # Call AI
            response = call_ai(
                model,
                self.settings["system_prompt"],
                prompt,
                temperature
            )
            
            return response.strip()
            
        except Exception as e:
            logging.error(f"AI response error: {e}")
            return "I'm sorry, I encountered an error processing your request."
            
    async def _speak_response(self, text: str):
        """Synthesize and play AI response.
        
        Args:
            text: Response text to speak
        """
        try:
            # Set speaking state
            self._set_state(ConversationState.SPEAKING)
            
            # Store last response
            self.last_ai_response = text
            
            # Get TTS provider
            tts_provider = self.tts_manager.get_active()
            if not tts_provider:
                logging.error("No active TTS provider")
                return
                
            # Synthesize with streaming
            voice = self.settings["tts_voice"]
            # For now, disable streaming to get complete audio
            audio_stream = await tts_provider.synthesize(text, voice, streaming=False)
            
            # Play audio stream
            if hasattr(audio_stream, '__aiter__'):
                # Streaming audio - collect all chunks first
                logging.info("Collecting streaming audio chunks...")
                audio_chunks = []
                async for chunk in audio_stream:
                    if self.state == ConversationState.INTERRUPTED:
                        break
                    audio_chunks.append(chunk)
                
                # Combine all chunks
                if audio_chunks:
                    complete_audio = b''.join(audio_chunks)
                    logging.info(f"Collected {len(audio_chunks)} chunks, total size: {len(complete_audio)} bytes")
                    audio_array = self._audio_bytes_to_array(complete_audio)
                    if audio_array is not None:
                        # Play audio and wait for completion
                        self.playback_manager.play_audio(audio_array, block=True)
            else:
                # Complete audio
                logging.info(f"Got complete audio of size: {len(audio_stream)} bytes")
                audio_array = self._audio_bytes_to_array(audio_stream)
                if audio_array is not None:
                    # Play audio and wait for completion
                    self.playback_manager.play_audio(audio_array, block=True)
                    
        except Exception as e:
            logging.error(f"TTS playback error: {e}")
        finally:
            # Return to listening state after playback completes
            if self.state != ConversationState.INTERRUPTED:
                self._set_state(ConversationState.LISTENING)
                
    def _audio_bytes_to_array(self, audio_bytes: bytes) -> Optional[np.ndarray]:
        """Convert audio bytes to numpy array.
        
        Args:
            audio_bytes: Audio data as bytes
            
        Returns:
            Numpy array or None
        """
        try:
            # Check if audio_bytes is valid
            if not audio_bytes or len(audio_bytes) == 0:
                logging.warning("Empty audio bytes received")
                return None
                
            from pydub import AudioSegment
            import tempfile
            import os
            
            logging.debug(f"Converting audio bytes of length: {len(audio_bytes)}")
            
            # Check if it's actually MP3 data
            if len(audio_bytes) > 4:
                # MP3 files typically start with FF FB, FF F3, or ID3
                header = audio_bytes[:4]
                if header[:3] == b'ID3' or header[:2] in [b'\xff\xfb', b'\xff\xf3', b'\xff\xf2', b'\xff\xfa']:
                    logging.debug("Detected MP3 format from header")
                else:
                    logging.debug(f"Unknown format header: {header.hex()}")
                    # Save for debugging
                    debug_path = f"/tmp/debug_audio_{os.getpid()}.dat"
                    with open(debug_path, 'wb') as f:
                        f.write(audio_bytes)
                    logging.debug(f"Saved audio for debugging to: {debug_path}")
            
            # Use a more robust approach with ffmpeg directly
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3', mode='wb') as tmp_input:
                tmp_input.write(audio_bytes)
                tmp_input_path = tmp_input.name
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav', mode='wb') as tmp_output:
                tmp_output_path = tmp_output.name
            
            try:
                # Use ffmpeg directly to convert to WAV
                import subprocess
                
                # Force MP3 input format and convert to WAV
                cmd = [
                    'ffmpeg',
                    '-i', tmp_input_path,  # Let ffmpeg auto-detect format
                    '-acodec', 'pcm_s16le',  # 16-bit PCM
                    '-ar', '24000',  # 24kHz sample rate
                    '-ac', '1',  # Mono
                    '-y',  # Overwrite output
                    '-loglevel', 'error',  # Only show errors
                    tmp_output_path
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    logging.error(f"FFmpeg conversion failed: {result.stderr}")
                    return None
                
                # Load the WAV file
                audio = AudioSegment.from_wav(tmp_output_path)
                
                # Get samples
                samples = np.array(audio.get_array_of_samples())
                
                # Normalize to float32
                samples = samples.astype(np.float32) / 32768.0
                
                logging.debug(f"Successfully converted audio: {len(samples)} samples")
                return samples
                
            finally:
                # Clean up temp files
                for path in [tmp_input_path, tmp_output_path]:
                    try:
                        os.unlink(path)
                    except:
                        pass
            
        except Exception as e:
            logging.error(f"Error converting audio bytes: {e}")
            return None
            
    def interrupt(self):
        """Interrupt current speech."""
        if self.state == ConversationState.SPEAKING:
            self._set_state(ConversationState.INTERRUPTED)
            self.playback_manager.stop()
            
            # Clear queued audio
            self.playback_manager.clear_queue()
            
            # Return to listening
            self._set_state(ConversationState.LISTENING)
            
    def _set_state(self, state: ConversationState):
        """Set conversation state.
        
        Args:
            state: New state
        """
        if state != self.state:
            old_state = self.state
            self.state = state
            
            logging.info(f"Voice state: {old_state.value} -> {state.value}")
            
            # Notify callback
            if self.on_state_change:
                self.on_state_change(state.value)
                
    def _handle_playback_start(self):
        """Handle playback start event."""
        logging.debug("TTS playback started")
        
    def _handle_playback_end(self):
        """Handle playback end event."""
        logging.debug("TTS playback ended")
        
        # Return to listening if still in speaking state
        if self.state == ConversationState.SPEAKING:
            self._set_state(ConversationState.LISTENING)
            
    def _handle_playback_error(self, error: str):
        """Handle playback error.
        
        Args:
            error: Error message
        """
        logging.error(f"Playback error: {error}")
        self._set_state(ConversationState.LISTENING)
        
    def _handle_websocket_audio(self, data: Dict[str, Any]):
        """Handle audio data from WebSocket.
        
        Args:
            data: Audio data from WebSocket
        """
        audio_array = data["audio"]
        self.process_audio(audio_array)
        
    def _handle_websocket_start(self, data: Dict[str, Any]):
        """Handle WebSocket session start.
        
        Args:
            data: Session data
        """
        client_id = data["client_id"]
        session_data = data.get("data", {})
        
        # Start session for this client
        asyncio.run(self.start_session(session_data))
        
    def _handle_websocket_end(self, data: Dict[str, Any]):
        """Handle WebSocket session end.
        
        Args:
            data: Session end data
        """
        asyncio.run(self.end_session())
        
    def _save_conversation_history(self):
        """Save conversation history for the session."""
        # This could save to database or file
        # For now, just log it
        logging.info(f"Conversation history for session {self.session_id}:")
        for entry in self.conversation_history:
            role = entry["role"]
            content = entry["content"]
            timestamp = entry["timestamp"]
            logging.info(f"[{timestamp}] {role}: {content}")
            
    def get_conversation_transcript(self) -> str:
        """Get the full conversation transcript.
        
        Returns:
            Formatted transcript
        """
        transcript_lines = []
        
        for entry in self.conversation_history:
            role = entry["role"].capitalize()
            content = entry["content"]
            timestamp = entry["timestamp"].strftime("%H:%M:%S")
            transcript_lines.append(f"[{timestamp}] {role}: {content}")
            
        return "\n".join(transcript_lines)
        
    def update_medical_context(self, context: Dict[str, Any]):
        """Update medical context for the conversation.
        
        Args:
            context: Medical context data
        """
        self.medical_context.update(context)
        logging.info(f"Updated medical context: {list(context.keys())}")
        
    async def cleanup(self):
        """Clean up resources."""
        # End session if active
        if self.is_active:
            await self.end_session()
            
        # Stop WebSocket server
        if self.websocket_server:
            self.websocket_server.stop()
            
        # Stop playback
        if self.playback_manager:
            self.playback_manager.stop()
            
        logging.info("Voice interaction manager cleaned up")