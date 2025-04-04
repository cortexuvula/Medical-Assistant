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
            return ""
        
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
            
            # Add a minute of timeout for each 500KB of audio, with a minimum of 60 seconds
            timeout_seconds = max(60, int(file_size_kb / 500) * 60)
            self.logger.info(f"Setting GROQ timeout to {timeout_seconds} seconds for {file_size_kb:.2f} KB file")

            # Using OpenAI client since GROQ uses a compatible API
            from openai import OpenAI
            
            # Initialize client with GROQ base URL
            client = OpenAI(api_key=self.api_key, base_url="https://api.groq.com/openai/v1")
            
            # Print API call details to terminal
            print("\n===== GROQ API CALL =====")
            print(f"File: {os.path.basename(temp_file)} (audio/wav)")
            print(f"Audio file size: {file_size_kb:.2f} KB")
            print(f"Timeout set to: {timeout_seconds} seconds")
            print("=========================\n")
            
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
                print("\n===== GROQ API RESPONSE =====")
                print(f"Response successfully received")
                if transcript:
                    text_preview = transcript[:100] + "..." if len(transcript) > 100 else transcript
                    print(f"Text preview: {text_preview}")
                print("============================\n")
            else:
                self.logger.error("Unexpected response format from GROQ API")
                print("\n===== GROQ API ERROR =====")
                print(f"Unexpected response format: {response}")
                print("==========================\n")
                
        except Exception as e:
            error_msg = f"Error with GROQ transcription: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            
            # Print exception details to terminal
            print("\n===== GROQ EXCEPTION =====")
            print(f"Error: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            print("==========================\n")
                
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
