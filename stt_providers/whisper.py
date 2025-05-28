"""
Whisper STT provider implementation.
"""

import os
import logging
import tempfile
from typing import Optional
from pydub import AudioSegment

from .base import BaseSTTProvider

class WhisperProvider(BaseSTTProvider):
    """Implementation of the local Whisper STT provider."""
    
    def __init__(self, api_key: str = "", language: str = "en-US"):
        """Initialize the Whisper provider.
        
        Args:
            api_key: Not used for local Whisper
            language: Language code for speech recognition
        """
        super().__init__(api_key, language)
        self.is_available = self._check_whisper_available()
    
    def _check_whisper_available(self) -> bool:
        """Check if Whisper is available on the system.
        
        Returns:
            True if Whisper is available, False otherwise
        """
        try:
            import whisper
            self.logger.info("Local Whisper model is available")
            return True
        except ImportError:
            self.logger.warning("Local Whisper model is not available")
            return False
    
    def transcribe(self, segment: AudioSegment) -> str:
        """Transcribe audio using local Whisper model.
        
        Args:
            segment: Audio segment to transcribe
            
        Returns:
            Transcription text
        """
        if not self.is_available:
            self.logger.warning("Whisper is not available")
            return ""
        
        temp_file = None
        transcript = ""
            
        try:
            # Import inside function to avoid startup delays
            import whisper
            
            # Convert segment to WAV for Whisper
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp:
                temp_file = temp.name
                segment.export(temp_file, format="wav")
            
            # Get file size for logging
            file_size_kb = os.path.getsize(temp_file) / 1024
            
            # Print API call details to terminal
            logging.debug("\n===== LOCAL WHISPER TRANSCRIPTION =====")
            logging.debug(f"File: {os.path.basename(temp_file)} (audio/wav)")
            logging.debug(f"Audio file size: {file_size_kb:.2f} KB")
            logging.debug(f"Language: {self.language}")
            logging.debug("======================================\n")
            
            # Load model - use small model for speed
            model = whisper.load_model("small")
            
            # Perform transcription
            result = model.transcribe(
                temp_file,
                language=self.language.split('-')[0],  # Use language code without region
                fp16=False  # Avoid GPU errors on some systems
            )
            
            # Extract transcript text
            if "text" in result:
                transcript = result["text"].strip()
                
                # Print successful response info to terminal
                logging.debug("\n===== WHISPER RESULT =====")
                if transcript:
                    text_preview = transcript[:100] + "..." if len(transcript) > 100 else transcript
                    logging.debug(f"Text preview: {text_preview}")
                logging.debug("========================\n")
            else:
                self.logger.error("Unexpected response format from Whisper")
            
        except Exception as e:
            error_msg = f"Error with Whisper transcription: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            
            # Print exception details to terminal
            logging.debug("\n===== WHISPER EXCEPTION =====")
            logging.debug(f"Error: {str(e)}")
            import traceback
            logging.debug(f"Traceback: {traceback.format_exc()}")
            logging.debug("============================\n")
            
        finally:
            # Try to clean up temp file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception as e:
                    # Log but don't fail if cleanup fails - this shouldn't affect functionality
                    self.logger.warning(f"Failed to delete temp file {temp_file}: {str(e)}")
            
        # Return whatever transcript we got, empty string if we failed
        return transcript
