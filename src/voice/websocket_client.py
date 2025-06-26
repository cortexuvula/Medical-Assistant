"""
WebSocket Client for Real-time Audio Streaming

Handles client-side WebSocket communication for advanced voice mode.
"""

import asyncio
import json
import logging
import websockets
from typing import Optional, Callable, Dict, Any
import numpy as np
import threading
from datetime import datetime
import queue


class AudioWebSocketClient:
    """WebSocket client for real-time audio streaming."""
    
    def __init__(self, server_url: str = "ws://localhost:8765"):
        """Initialize WebSocket client.
        
        Args:
            server_url: WebSocket server URL
        """
        self.server_url = server_url
        self.websocket = None
        self.loop = None
        self.client_thread = None
        self.is_connected = False
        self.session_active = False
        
        # Event handlers
        self.handlers: Dict[str, Callable] = {}
        
        # Audio configuration
        self.audio_config = {
            "sample_rate": 16000,
            "chunk_size": 1024,
            "audio_format": "int16"
        }
        
        # Queues for thread-safe communication
        self.audio_send_queue = queue.Queue()
        self.message_send_queue = queue.Queue()
        
    def register_handler(self, event: str, handler: Callable):
        """Register an event handler.
        
        Args:
            event: Event name
            handler: Callback function
        """
        self.handlers[event] = handler
        logging.info(f"Registered handler for event: {event}")
        
    async def connect(self):
        """Connect to WebSocket server."""
        try:
            self.websocket = await websockets.connect(
                self.server_url,
                max_size=10 * 1024 * 1024  # 10MB max
            )
            self.is_connected = True
            logging.info(f"Connected to WebSocket server: {self.server_url}")
            
            # Start message handlers
            await asyncio.gather(
                self._receive_messages(),
                self._send_queued_messages(),
                self._send_queued_audio()
            )
            
        except Exception as e:
            logging.error(f"Failed to connect to WebSocket server: {e}")
            self.is_connected = False
            raise
            
    async def _receive_messages(self):
        """Receive and process messages from server."""
        try:
            async for message in self.websocket:
                if isinstance(message, bytes):
                    # Handle binary audio data
                    await self._handle_audio_data(message)
                else:
                    # Handle JSON messages
                    await self._handle_json_message(message)
                    
        except websockets.exceptions.ConnectionClosed:
            logging.info("WebSocket connection closed")
        except Exception as e:
            logging.error(f"Error receiving messages: {e}")
        finally:
            self.is_connected = False
            
    async def _handle_audio_data(self, audio_bytes: bytes):
        """Handle incoming audio data.
        
        Args:
            audio_bytes: Raw audio bytes
        """
        # Convert bytes to numpy array
        audio_format = self.audio_config.get("audio_format", "int16")
        
        if audio_format == "int16":
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
        elif audio_format == "float32":
            audio_array = np.frombuffer(audio_bytes, dtype=np.float32)
        else:
            logging.error(f"Unsupported audio format: {audio_format}")
            return
            
        # Trigger handler
        await self._trigger_handler("audio_received", {
            "audio": audio_array,
            "sample_rate": self.audio_config["sample_rate"],
            "timestamp": datetime.now()
        })
        
    async def _handle_json_message(self, message: str):
        """Handle JSON message from server.
        
        Args:
            message: JSON message string
        """
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type == "config":
                await self._handle_config(data.get("data", {}))
            elif message_type == "session_started":
                await self._handle_session_started(data.get("data", {}))
            elif message_type == "session_ended":
                await self._handle_session_ended(data.get("data", {}))
            elif message_type == "text_response":
                await self._handle_text_response(data.get("data", {}))
            else:
                logging.warning(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            logging.error("Invalid JSON received")
        except Exception as e:
            logging.error(f"Error handling JSON message: {e}")
            
    async def _handle_config(self, config: Dict[str, Any]):
        """Handle server configuration.
        
        Args:
            config: Server configuration
        """
        self.audio_config.update(config)
        logging.info(f"Updated audio config: {self.audio_config}")
        
        # Trigger handler
        await self._trigger_handler("config_received", config)
        
    async def _handle_session_started(self, data: Dict[str, Any]):
        """Handle session started notification.
        
        Args:
            data: Session data
        """
        self.session_active = True
        await self._trigger_handler("session_started", data)
        
    async def _handle_session_ended(self, data: Dict[str, Any]):
        """Handle session ended notification.
        
        Args:
            data: Session end data
        """
        self.session_active = False
        await self._trigger_handler("session_ended", data)
        
    async def _handle_text_response(self, data: Dict[str, Any]):
        """Handle text response from server.
        
        Args:
            data: Text response data
        """
        await self._trigger_handler("text_received", data)
        
    async def _trigger_handler(self, event: str, data: Dict[str, Any]):
        """Trigger registered event handler.
        
        Args:
            event: Event name
            data: Event data
        """
        if event in self.handlers:
            handler = self.handlers[event]
            if asyncio.iscoroutinefunction(handler):
                await handler(data)
            else:
                # Run sync handler in executor
                await asyncio.get_event_loop().run_in_executor(None, handler, data)
                
    async def _send_queued_messages(self):
        """Send queued messages to server."""
        while self.is_connected:
            try:
                # Non-blocking get with timeout
                message = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.message_send_queue.get(timeout=0.1)
                )
                
                if self.websocket:
                    await self.websocket.send(json.dumps(message))
                    
            except queue.Empty:
                await asyncio.sleep(0.01)
            except Exception as e:
                logging.error(f"Error sending message: {e}")
                
    async def _send_queued_audio(self):
        """Send queued audio data to server."""
        while self.is_connected:
            try:
                # Non-blocking get with timeout
                audio_data = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.audio_send_queue.get(timeout=0.1)
                )
                
                if self.websocket and self.session_active:
                    audio_bytes = audio_data.tobytes()
                    await self.websocket.send(audio_bytes)
                    
            except queue.Empty:
                await asyncio.sleep(0.01)
            except Exception as e:
                logging.error(f"Error sending audio: {e}")
                
    def start_session(self, session_data: Optional[Dict[str, Any]] = None):
        """Start a voice session.
        
        Args:
            session_data: Optional session configuration
        """
        message = {
            "type": "start_session",
            "data": session_data or {}
        }
        self.message_send_queue.put(message)
        
    def end_session(self, reason: str = "user_request"):
        """End the current voice session.
        
        Args:
            reason: Reason for ending session
        """
        message = {
            "type": "end_session",
            "data": {"reason": reason}
        }
        self.message_send_queue.put(message)
        
    def send_audio(self, audio_data: np.ndarray):
        """Send audio data to server.
        
        Args:
            audio_data: Audio data as numpy array
        """
        if not self.is_connected or not self.session_active:
            return
            
        self.audio_send_queue.put(audio_data)
        
    def send_text(self, text: str, context: Optional[Dict[str, Any]] = None):
        """Send text input to server.
        
        Args:
            text: Text input
            context: Optional context data
        """
        message = {
            "type": "text_input",
            "data": {
                "text": text,
                "context": context or {}
            }
        }
        self.message_send_queue.put(message)
        
    def update_audio_config(self, config: Dict[str, Any]):
        """Update audio configuration.
        
        Args:
            config: Audio configuration updates
        """
        self.audio_config.update(config)
        
        message = {
            "type": "audio_config",
            "data": config
        }
        self.message_send_queue.put(message)
        
    def start(self):
        """Start the WebSocket client in a separate thread."""
        self.client_thread = threading.Thread(target=self._run_client)
        self.client_thread.daemon = True
        self.client_thread.start()
        
    def _run_client(self):
        """Run the WebSocket client."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            self.loop.run_until_complete(self.connect())
        except Exception as e:
            logging.error(f"Client error: {e}")
        finally:
            self.loop.close()
            
    def stop(self):
        """Stop the WebSocket client."""
        if self.is_connected and self.websocket:
            # End session if active
            if self.session_active:
                self.end_session("client_shutdown")
                
            # Close connection
            asyncio.run_coroutine_threadsafe(
                self.websocket.close(),
                self.loop
            )
            
        # Wait for thread to finish
        if self.client_thread:
            self.client_thread.join(timeout=5)
            
        logging.info("WebSocket client stopped")
        
    def is_active(self) -> bool:
        """Check if client is connected and active.
        
        Returns:
            True if connected and active
        """
        return self.is_connected and self.client_thread and self.client_thread.is_alive()