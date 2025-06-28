"""
WebSocket Server for Real-time Audio Streaming

Handles bidirectional audio streaming for advanced voice mode functionality.
"""

import asyncio
import json
import logging
import websockets
from websockets.server import WebSocketServerProtocol
from typing import Dict, Set, Optional, Callable, Any
import numpy as np
import base64
from datetime import datetime
import threading


class AudioWebSocketServer:
    """WebSocket server for handling real-time audio streaming."""
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        """Initialize WebSocket server.
        
        Args:
            host: Server host address
            port: Server port
        """
        self.host = host
        self.port = port
        self.clients: Set[WebSocketServerProtocol] = set()
        self.audio_handlers: Dict[str, Callable] = {}
        self.server = None
        self.server_thread = None
        self.loop = None
        
        # Audio settings
        self.sample_rate = 16000  # 16kHz for voice
        self.chunk_size = 1024  # Audio chunk size
        
        # Client state tracking
        self.client_states: Dict[str, Dict[str, Any]] = {}
        
    def register_handler(self, event: str, handler: Callable):
        """Register an event handler.
        
        Args:
            event: Event name (e.g., 'audio_data', 'start_session', 'end_session')
            handler: Callback function to handle the event
        """
        self.audio_handlers[event] = handler
        logging.info(f"Registered handler for event: {event}")
        
    async def handle_client(self, websocket: WebSocketServerProtocol, path: str):
        """Handle WebSocket client connection.
        
        Args:
            websocket: WebSocket connection
            path: Connection path
        """
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logging.info(f"Client connected: {client_id}")
        
        # Initialize client state
        self.client_states[client_id] = {
            "connected_at": datetime.now(),
            "session_active": False,
            "audio_format": "int16",  # Default format
            "sample_rate": self.sample_rate,
            "websocket": websocket
        }
        
        self.clients.add(websocket)
        
        try:
            # Send initial configuration
            await self.send_config(websocket)
            
            # Handle messages
            async for message in websocket:
                await self.process_message(client_id, message)
                
        except websockets.exceptions.ConnectionClosed:
            logging.info(f"Client disconnected: {client_id}")
        except Exception as e:
            logging.error(f"Error handling client {client_id}: {e}")
        finally:
            # Cleanup
            self.clients.discard(websocket)
            if client_id in self.client_states:
                # Trigger end session if active
                if self.client_states[client_id].get("session_active"):
                    await self._trigger_handler("end_session", {
                        "client_id": client_id,
                        "reason": "disconnect"
                    })
                del self.client_states[client_id]
                
    async def send_config(self, websocket: WebSocketServerProtocol):
        """Send initial configuration to client.
        
        Args:
            websocket: WebSocket connection
        """
        config = {
            "type": "config",
            "data": {
                "sample_rate": self.sample_rate,
                "chunk_size": self.chunk_size,
                "audio_format": "int16",
                "version": "1.0"
            }
        }
        await websocket.send(json.dumps(config))
        
    async def process_message(self, client_id: str, message: Any):
        """Process incoming WebSocket message.
        
        Args:
            client_id: Client identifier
            message: Raw message data
        """
        try:
            # Handle binary audio data
            if isinstance(message, bytes):
                await self._handle_audio_data(client_id, message)
                return
                
            # Handle JSON messages
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type == "start_session":
                await self._handle_start_session(client_id, data.get("data", {}))
            elif message_type == "end_session":
                await self._handle_end_session(client_id, data.get("data", {}))
            elif message_type == "audio_config":
                await self._handle_audio_config(client_id, data.get("data", {}))
            elif message_type == "text_input":
                await self._handle_text_input(client_id, data.get("data", {}))
            else:
                logging.warning(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            logging.error(f"Invalid JSON from client {client_id}")
        except Exception as e:
            logging.error(f"Error processing message from {client_id}: {e}")
            
    async def _handle_audio_data(self, client_id: str, audio_bytes: bytes):
        """Handle incoming audio data.
        
        Args:
            client_id: Client identifier
            audio_bytes: Raw audio bytes
        """
        if not self.client_states[client_id].get("session_active"):
            return
            
        # Convert bytes to numpy array based on format
        audio_format = self.client_states[client_id].get("audio_format", "int16")
        
        if audio_format == "int16":
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
        elif audio_format == "float32":
            audio_array = np.frombuffer(audio_bytes, dtype=np.float32)
        else:
            logging.error(f"Unsupported audio format: {audio_format}")
            return
            
        # Trigger audio data handler
        await self._trigger_handler("audio_data", {
            "client_id": client_id,
            "audio": audio_array,
            "sample_rate": self.client_states[client_id]["sample_rate"],
            "timestamp": datetime.now()
        })
        
    async def _handle_start_session(self, client_id: str, data: Dict[str, Any]):
        """Handle session start request.
        
        Args:
            client_id: Client identifier
            data: Session data
        """
        self.client_states[client_id]["session_active"] = True
        self.client_states[client_id]["session_data"] = data
        
        # Send acknowledgment
        websocket = self.client_states[client_id]["websocket"]
        await websocket.send(json.dumps({
            "type": "session_started",
            "data": {"session_id": client_id}
        }))
        
        # Trigger handler
        await self._trigger_handler("start_session", {
            "client_id": client_id,
            "data": data
        })
        
    async def _handle_end_session(self, client_id: str, data: Dict[str, Any]):
        """Handle session end request.
        
        Args:
            client_id: Client identifier
            data: Session end data
        """
        self.client_states[client_id]["session_active"] = False
        
        # Send acknowledgment
        websocket = self.client_states[client_id]["websocket"]
        await websocket.send(json.dumps({
            "type": "session_ended",
            "data": {"session_id": client_id}
        }))
        
        # Trigger handler
        await self._trigger_handler("end_session", {
            "client_id": client_id,
            "data": data
        })
        
    async def _handle_audio_config(self, client_id: str, data: Dict[str, Any]):
        """Handle audio configuration update.
        
        Args:
            client_id: Client identifier
            data: Audio configuration
        """
        # Update client audio settings
        if "sample_rate" in data:
            self.client_states[client_id]["sample_rate"] = data["sample_rate"]
        if "audio_format" in data:
            self.client_states[client_id]["audio_format"] = data["audio_format"]
            
        logging.info(f"Updated audio config for {client_id}: {data}")
        
    async def _handle_text_input(self, client_id: str, data: Dict[str, Any]):
        """Handle text input from client.
        
        Args:
            client_id: Client identifier
            data: Text input data
        """
        await self._trigger_handler("text_input", {
            "client_id": client_id,
            "text": data.get("text", ""),
            "context": data.get("context", {})
        })
        
    async def _trigger_handler(self, event: str, data: Dict[str, Any]):
        """Trigger registered event handler.
        
        Args:
            event: Event name
            data: Event data
        """
        if event in self.audio_handlers:
            handler = self.audio_handlers[event]
            if asyncio.iscoroutinefunction(handler):
                await handler(data)
            else:
                # Run sync handler in executor
                await asyncio.get_event_loop().run_in_executor(None, handler, data)
                
    async def send_audio(self, client_id: str, audio_data: np.ndarray):
        """Send audio data to specific client.
        
        Args:
            client_id: Client identifier
            audio_data: Audio data as numpy array
        """
        if client_id not in self.client_states:
            logging.warning(f"Client {client_id} not found")
            return
            
        websocket = self.client_states[client_id]["websocket"]
        
        # Convert numpy array to bytes
        audio_bytes = audio_data.tobytes()
        
        # Send as binary frame
        await websocket.send(audio_bytes)
        
    async def send_text(self, client_id: str, text: str, metadata: Optional[Dict] = None):
        """Send text to specific client.
        
        Args:
            client_id: Client identifier
            text: Text to send
            metadata: Optional metadata
        """
        if client_id not in self.client_states:
            logging.warning(f"Client {client_id} not found")
            return
            
        websocket = self.client_states[client_id]["websocket"]
        
        message = {
            "type": "text_response",
            "data": {
                "text": text,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        if metadata:
            message["data"]["metadata"] = metadata
            
        await websocket.send(json.dumps(message))
        
    async def broadcast_audio(self, audio_data: np.ndarray):
        """Broadcast audio to all connected clients.
        
        Args:
            audio_data: Audio data as numpy array
        """
        if not self.clients:
            return
            
        audio_bytes = audio_data.tobytes()
        
        # Send to all clients
        disconnected = set()
        for websocket in self.clients:
            try:
                await websocket.send(audio_bytes)
            except:
                disconnected.add(websocket)
                
        # Remove disconnected clients
        self.clients -= disconnected
        
    def start(self):
        """Start the WebSocket server in a separate thread."""
        self.server_thread = threading.Thread(target=self._run_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        logging.info(f"WebSocket server starting on ws://{self.host}:{self.port}")
        
    def _run_server(self):
        """Run the WebSocket server."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        start_server = websockets.serve(
            self.handle_client,
            self.host,
            self.port,
            max_size=10 * 1024 * 1024  # 10MB max message size
        )
        
        self.server = self.loop.run_until_complete(start_server)
        self.loop.run_forever()
        
    def stop(self):
        """Stop the WebSocket server."""
        if self.server:
            logging.info("Stopping WebSocket server...")
            
            # Close all client connections
            for client_id, state in self.client_states.items():
                websocket = state.get("websocket")
                if websocket:
                    asyncio.run_coroutine_threadsafe(
                        websocket.close(),
                        self.loop
                    )
            
            # Stop server
            self.server.close()
            
            # Stop event loop
            if self.loop:
                self.loop.call_soon_threadsafe(self.loop.stop)
                
            # Wait for thread to finish
            if self.server_thread:
                self.server_thread.join(timeout=5)
                
            logging.info("WebSocket server stopped")
            
    def is_running(self) -> bool:
        """Check if server is running.
        
        Returns:
            True if server is running
        """
        return self.server_thread and self.server_thread.is_alive()