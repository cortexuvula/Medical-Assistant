"""
GROQ STT provider implementation.
"""

import os
import time
import tempfile
import logging
import traceback
from typing import Optional
from pydub import AudioSegment

from .base import BaseSTTProvider
from exceptions import TranscriptionError, APIError, RateLimitError, ServiceUnavailableError
from resilience import resilient_api_call
from config import get_config
from security_decorators import secure_api_call
from security import get_security_manager

class GroqProvider(BaseSTTProvider):
    """Implementation of the GROQ STT provider."""
    
    def __init__(self, api_key: str = "", language: str = "en-US"):
        """Initialize the GROQ provider.
        
        Args:
            api_key: GROQ API key
            language: Language code for speech recognition
        """
        super().__init__(api_key, language)
    
    def transcribe(self, segment: AudioSegment) -> str:
        """Transcribe audio using GROQ API.
        
        Args:
            segment: Audio segment to transcribe
            
        Returns:
            Transcription text
        """
        if not self._check_api_key():
            raise TranscriptionError("GROQ API key not configured")
        
        temp_file = None
        file_obj = None
        transcript = ""
            
        try:
            # Convert segment to WAV for API
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp:
                temp_file = temp.name
                segment.export(temp_file, format="wav")
                
            # Get file size and adjust timeout accordingly
            file_size_kb = os.path.getsize(temp_file) / 1024
            
            # Add a minute of timeout for each 500KB of audio, with a minimum of base timeout
            config = get_config()
            base_timeout = config.api.timeout
            timeout_seconds = max(base_timeout, int(file_size_kb / 500) * 60)
            self.logger.info(f"Setting GROQ timeout to {timeout_seconds} seconds for {file_size_kb:.2f} KB file")

            # Using OpenAI client since GROQ uses a compatible API
            from openai import OpenAI
            
            # Get API key from secure storage if needed
            security_manager = get_security_manager()
            api_key = self.api_key or security_manager.get_api_key("groq")
            if not api_key:
                raise TranscriptionError("GROQ API key not found")
            
            # Initialize client with GROQ base URL
            client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
            
            # Print API call details to terminal
            logging.debug("\n===== GROQ API CALL =====")
            logging.debug(f"File: {os.path.basename(temp_file)} (audio/wav)")
            logging.debug(f"Audio file size: {file_size_kb:.2f} KB")
            logging.debug(f"Timeout set to: {timeout_seconds} seconds")
            logging.debug("=========================\n")
            
            # Open and read the audio file
            with open(temp_file, "rb") as audio_file:
                # Make API call with timeout
                response = client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-large-v3-turbo",  # GROQ's Whisper model (updated name)
                    language=self.language.split('-')[0],  # Use language code without region
                    timeout=timeout_seconds
                )
            
            # Process response
            if hasattr(response, 'text'):
                transcript = response.text
                
                # Print successful response info to terminal
                logging.debug("\n===== GROQ API RESPONSE =====")
                logging.debug(f"Response successfully received")
                if transcript:
                    text_preview = transcript[:100] + "..." if len(transcript) > 100 else transcript
                    logging.debug(f"Text preview: {text_preview}")
                logging.debug("============================\n")
            else:
                raise TranscriptionError("Unexpected response format from GROQ API")
                
        except TranscriptionError:
            # Re-raise transcription errors
            raise
        except Exception as e:
            # Wrap unexpected errors
            error_msg = f"Unexpected error during GROQ transcription: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise TranscriptionError(error_msg)
                
        finally:
            # Make sure file handle is closed
            if file_obj and not file_obj.closed:
                try:
                    file_obj.close()
                except Exception as e:
                    self.logger.warning(f"Error closing file handle: {str(e)}")
            
            # Try to clean up temp file
            if temp_file and os.path.exists(temp_file):
                try:
                    # On Windows, sometimes we need to wait a moment before the file can be deleted
                    time.sleep(0.5)
                    os.unlink(temp_file)
                except Exception as e:
                    # Log but don't fail if cleanup fails - this shouldn't affect functionality
                    self.logger.warning(f"Failed to delete temp file {temp_file}: {str(e)}")
                    # We'll just let Windows clean it up later
            
        # Return whatever transcript we got, empty string if we failed
        return transcript
