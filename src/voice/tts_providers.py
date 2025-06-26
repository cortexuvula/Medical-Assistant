"""
Text-to-Speech Providers for Advanced Voice Mode

Integrates multiple TTS providers with streaming support for real-time voice synthesis.
"""

import logging
import asyncio
from typing import Optional, Callable, Dict, Any, List, Union, AsyncGenerator
import numpy as np
from io import BytesIO
import base64
import json
import aiohttp
from elevenlabs.client import ElevenLabs
from elevenlabs import Voice, VoiceSettings
import openai
from pydub import AudioSegment
from abc import ABC, abstractmethod
from settings.settings import SETTINGS


class BaseTTSProvider(ABC):
    """Base class for TTS providers."""
    
    def __init__(self, api_key: str = ""):
        """Initialize TTS provider.
        
        Args:
            api_key: API key for the provider
        """
        self.api_key = api_key
        self.is_streaming = False
        
    @abstractmethod
    async def synthesize(self, text: str, voice: str = "default", 
                        streaming: bool = False) -> Union[bytes, AsyncGenerator]:
        """Synthesize speech from text.
        
        Args:
            text: Text to synthesize
            voice: Voice ID or name
            streaming: Whether to stream audio chunks
            
        Returns:
            Audio bytes or async generator for streaming
        """
        pass
        
    @abstractmethod
    def get_voices(self) -> List[Dict[str, str]]:
        """Get available voices.
        
        Returns:
            List of voice information
        """
        pass


class ElevenLabsTTSProvider(BaseTTSProvider):
    """ElevenLabs TTS provider with streaming support."""
    
    def __init__(self, api_key: str = ""):
        """Initialize ElevenLabs TTS provider.
        
        Args:
            api_key: ElevenLabs API key
        """
        super().__init__(api_key)
        self.client = ElevenLabs(api_key=api_key) if api_key else None
        
        # Default voice settings
        self.default_settings = VoiceSettings(
            stability=0.75,
            similarity_boost=0.75,
            style=0.5,
            use_speaker_boost=True
        )
        
    async def synthesize(self, text: str, voice: str = "Rachel", 
                        streaming: bool = False) -> Union[bytes, AsyncGenerator]:
        """Synthesize speech using ElevenLabs.
        
        Args:
            text: Text to synthesize
            voice: Voice ID or name (default: Rachel)
            streaming: Whether to stream audio chunks
            
        Returns:
            Audio bytes or async generator for streaming
        """
        if not self.client:
            raise ValueError("ElevenLabs client not initialized - check API key")
            
        try:
            if streaming:
                # Return async generator for streaming
                return self._stream_audio(text, voice)
            else:
                # Generate complete audio using the client
                # Use the text_to_speech.convert method for the new API
                audio_response = self.client.text_to_speech.convert(
                    text=text,
                    voice_id=voice,
                    model_id="eleven_multilingual_v2",
                    voice_settings=self.default_settings
                )
                
                # Convert iterator to bytes
                audio_chunks = []
                for chunk in audio_response:
                    audio_chunks.append(chunk)
                
                audio_bytes = b''.join(audio_chunks)
                return audio_bytes
                
        except Exception as e:
            logging.error(f"ElevenLabs synthesis error: {e}")
            raise
            
    async def _stream_audio(self, text: str, voice: str):
        """Stream audio chunks from ElevenLabs.
        
        Args:
            text: Text to synthesize
            voice: Voice ID or name
            
        Yields:
            Audio chunks
        """
        try:
            # Use ElevenLabs streaming API through client with new API
            audio_stream = self.client.text_to_speech.convert_as_stream(
                text=text,
                voice_id=voice,
                model_id="eleven_multilingual_v2",
                voice_settings=self.default_settings,
                chunk_size=1024
            )
            
            # Convert sync generator to async
            for chunk in audio_stream:
                yield chunk
                await asyncio.sleep(0)  # Allow other tasks
                
        except Exception as e:
            logging.error(f"ElevenLabs streaming error: {e}")
            raise
            
    def get_voices(self) -> List[Dict[str, str]]:
        """Get available ElevenLabs voices.
        
        Returns:
            List of voice information
        """
        if not self.client:
            return []
            
        try:
            voices = self.client.voices.get_all()
            
            return [
                {
                    "id": voice.voice_id,
                    "name": voice.name,
                    "description": voice.description,
                    "preview_url": voice.preview_url
                }
                for voice in voices.voices
            ]
        except Exception as e:
            logging.error(f"Error getting ElevenLabs voices: {e}")
            return []
            
    def update_voice_settings(self, stability: float = 0.75, 
                            similarity_boost: float = 0.75,
                            style: float = 0.5,
                            use_speaker_boost: bool = True):
        """Update default voice settings.
        
        Args:
            stability: Voice stability (0-1)
            similarity_boost: Voice similarity (0-1)
            style: Style exaggeration (0-1)
            use_speaker_boost: Whether to use speaker boost
        """
        self.default_settings = VoiceSettings(
            stability=stability,
            similarity_boost=similarity_boost,
            style=style,
            use_speaker_boost=use_speaker_boost
        )


class OpenAITTSProvider(BaseTTSProvider):
    """OpenAI TTS provider with streaming support."""
    
    def __init__(self, api_key: str = ""):
        """Initialize OpenAI TTS provider.
        
        Args:
            api_key: OpenAI API key
        """
        super().__init__(api_key)
        if api_key:
            openai.api_key = api_key
            
        # Available voices
        self.voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        self.default_voice = "nova"  # Natural sounding female voice
        
    async def synthesize(self, text: str, voice: str = None, 
                        streaming: bool = False) -> Union[bytes, AsyncGenerator]:
        """Synthesize speech using OpenAI TTS.
        
        Args:
            text: Text to synthesize
            voice: Voice name (alloy, echo, fable, onyx, nova, shimmer)
            streaming: Whether to stream audio chunks
            
        Returns:
            Audio bytes or async generator for streaming
        """
        if not openai.api_key:
            raise ValueError("OpenAI API key not set")
            
        voice = voice or self.default_voice
        
        if voice not in self.voices:
            logging.warning(f"Invalid voice '{voice}', using default '{self.default_voice}'")
            voice = self.default_voice
            
        try:
            if streaming:
                return self._stream_audio(text, voice)
            else:
                # Generate complete audio
                response = await self._generate_audio(text, voice)
                return response
                
        except Exception as e:
            logging.error(f"OpenAI TTS error: {e}")
            raise
            
    async def _generate_audio(self, text: str, voice: str) -> bytes:
        """Generate complete audio from OpenAI.
        
        Args:
            text: Text to synthesize
            voice: Voice name
            
        Returns:
            Audio bytes
        """
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {openai.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "tts-1-hd",  # High quality model
                "input": text,
                "voice": voice,
                "response_format": "mp3"
            }
            
            async with session.post(
                "https://api.openai.com/v1/audio/speech",
                headers=headers,
                json=data
            ) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    error_text = await response.text()
                    raise Exception(f"OpenAI TTS API error: {error_text}")
                    
    async def _stream_audio(self, text: str, voice: str):
        """Stream audio chunks from OpenAI.
        
        Args:
            text: Text to synthesize
            voice: Voice name
            
        Yields:
            Audio chunks
        """
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {openai.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "tts-1",  # Optimized for streaming
                "input": text,
                "voice": voice,
                "response_format": "mp3",
                "stream": True
            }
            
            async with session.post(
                "https://api.openai.com/v1/audio/speech",
                headers=headers,
                json=data
            ) as response:
                if response.status == 200:
                    async for chunk in response.content.iter_chunked(1024):
                        yield chunk
                else:
                    error_text = await response.text()
                    raise Exception(f"OpenAI TTS streaming error: {error_text}")
                    
    def get_voices(self) -> List[Dict[str, str]]:
        """Get available OpenAI voices.
        
        Returns:
            List of voice information
        """
        return [
            {"id": "alloy", "name": "Alloy", "description": "Neutral and fast"},
            {"id": "echo", "name": "Echo", "description": "British-sounding male"},
            {"id": "fable", "name": "Fable", "description": "British-sounding narrator"},
            {"id": "onyx", "name": "Onyx", "description": "Deep male voice"},
            {"id": "nova", "name": "Nova", "description": "Natural female voice"},
            {"id": "shimmer", "name": "Shimmer", "description": "Soft female voice"}
        ]


class TTSManager:
    """Manages multiple TTS providers for advanced voice mode."""
    
    def __init__(self):
        """Initialize TTS manager."""
        self.providers: Dict[str, BaseTTSProvider] = {}
        self.active_provider: Optional[str] = None
        
        # Audio format conversion settings
        self.output_format = "mp3"
        self.output_sample_rate = 24000
        
    def register_provider(self, name: str, provider: BaseTTSProvider):
        """Register a TTS provider.
        
        Args:
            name: Provider name
            provider: Provider instance
        """
        self.providers[name] = provider
        logging.info(f"Registered TTS provider: {name}")
        
    def create_provider(self, provider_type: str, api_key: str) -> BaseTTSProvider:
        """Create and register a TTS provider.
        
        Args:
            provider_type: Type of provider ('elevenlabs' or 'openai')
            api_key: API key for the provider
            
        Returns:
            Provider instance
        """
        if provider_type == "elevenlabs":
            provider = ElevenLabsTTSProvider(api_key)
        elif provider_type == "openai":
            provider = OpenAITTSProvider(api_key)
        else:
            raise ValueError(f"Unsupported TTS provider: {provider_type}")
            
        self.register_provider(provider_type, provider)
        return provider
        
    def set_active(self, provider_name: str):
        """Set the active TTS provider.
        
        Args:
            provider_name: Name of provider to activate
        """
        if provider_name in self.providers:
            self.active_provider = provider_name
            logging.info(f"Active TTS provider set to: {provider_name}")
        else:
            raise ValueError(f"Provider '{provider_name}' not found")
            
    def get_active(self) -> Optional[BaseTTSProvider]:
        """Get the active TTS provider.
        
        Returns:
            Active provider or None
        """
        if self.active_provider:
            return self.providers.get(self.active_provider)
        return None
        
    async def synthesize(self, text: str, voice: Optional[str] = None,
                        streaming: bool = False,
                        provider_name: Optional[str] = None) -> Union[bytes, AsyncGenerator]:
        """Synthesize speech using active or specified provider.
        
        Args:
            text: Text to synthesize
            voice: Voice ID or name
            streaming: Whether to stream audio
            provider_name: Specific provider to use (uses active if None)
            
        Returns:
            Audio bytes or async generator for streaming
        """
        # Get provider
        if provider_name:
            provider = self.providers.get(provider_name)
            if not provider:
                raise ValueError(f"Provider '{provider_name}' not found")
        else:
            provider = self.get_active()
            if not provider:
                raise ValueError("No active TTS provider")
                
        # Synthesize
        result = await provider.synthesize(text, voice, streaming)
        
        # Convert format if needed (for non-streaming)
        if not streaming and isinstance(result, bytes):
            result = self._convert_audio_format(result)
            
        return result
        
    def _convert_audio_format(self, audio_bytes: bytes) -> bytes:
        """Convert audio to desired output format.
        
        Args:
            audio_bytes: Input audio bytes
            
        Returns:
            Converted audio bytes
        """
        try:
            # Load audio
            audio = AudioSegment.from_file(BytesIO(audio_bytes))
            
            # Convert sample rate if needed
            if audio.frame_rate != self.output_sample_rate:
                audio = audio.set_frame_rate(self.output_sample_rate)
                
            # Export in desired format
            output = BytesIO()
            audio.export(output, format=self.output_format)
            output.seek(0)
            
            return output.read()
            
        except Exception as e:
            logging.error(f"Error converting audio format: {e}")
            return audio_bytes  # Return original on error
            
    def get_voices(self, provider_name: Optional[str] = None) -> List[Dict[str, str]]:
        """Get available voices from provider.
        
        Args:
            provider_name: Specific provider (uses active if None)
            
        Returns:
            List of voice information
        """
        if provider_name:
            provider = self.providers.get(provider_name)
        else:
            provider = self.get_active()
            
        if provider:
            return provider.get_voices()
        return []
        
    def list_providers(self) -> List[str]:
        """List registered providers.
        
        Returns:
            List of provider names
        """
        return list(self.providers.keys())