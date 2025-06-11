"""
Deepgram STT provider implementation.
"""

import json
import time
import logging
from io import BytesIO
import traceback
from typing import List, Optional
from pydub import AudioSegment
from deepgram import DeepgramClient, PrerecordedOptions

from .base import BaseSTTProvider
from settings.settings import SETTINGS, _DEFAULT_SETTINGS
from utils.exceptions import TranscriptionError, APIError, RateLimitError, ServiceUnavailableError
from utils.resilience import resilient_api_call, retry
from core.config import get_config
from utils.security_decorators import secure_api_call

class DeepgramProvider(BaseSTTProvider):
    """Implementation of the Deepgram STT provider."""
    
    def __init__(self, api_key: str = "", language: str = "en-US"):
        """Initialize the Deepgram provider.
        
        Args:
            api_key: Deepgram API key
            language: Language code for speech recognition
        """
        super().__init__(api_key, language)
        self.client = DeepgramClient(api_key=api_key) if api_key else None
    
    @secure_api_call("deepgram")
    @resilient_api_call(
        max_retries=3,
        initial_delay=1.0,
        backoff_factor=2.0,
        failure_threshold=5,
        recovery_timeout=60
    )
    def _make_api_call(self, buffer: BytesIO, options: PrerecordedOptions, timeout: int):
        """Make the actual API call to Deepgram.
        
        Args:
            buffer: Audio buffer
            options: Deepgram options
            timeout: Request timeout
            
        Returns:
            API response
            
        Raises:
            APIError: On API failures
        """
        try:
            response = self.client.listen.rest.v("1").transcribe_file(
                {"buffer": buffer}, 
                options,
                timeout=timeout
            )
            return response
        except Exception as e:
            # Convert to our custom exceptions
            error_msg = str(e)
            if "rate limit" in error_msg.lower():
                raise RateLimitError(f"Deepgram rate limit exceeded: {error_msg}")
            elif "timeout" in error_msg.lower():
                raise ServiceUnavailableError(f"Deepgram request timeout: {error_msg}")
            else:
                raise APIError(f"Deepgram API error: {error_msg}")
    
    def transcribe(self, segment: AudioSegment) -> str:
        """Transcribe audio using Deepgram API with improved error handling.
        
        Args:
            segment: AudioSegment to transcribe
            
        Returns:
            Transcription text or empty string if failed
        """
        if not self.client:
            raise TranscriptionError("Deepgram client not initialized - check API key")
        
        # Get Deepgram settings from SETTINGS
        deepgram_settings = SETTINGS.get("deepgram", _DEFAULT_SETTINGS["deepgram"])
        
        # Prepare a buffer
        buf = None
        transcript = ""
        
        try:
            # Prepare audio for Deepgram
            buf = BytesIO()
            segment.export(buf, format="wav")
            buf.seek(0)
            
            # Set up options using the settings
            options = PrerecordedOptions(
                model=deepgram_settings.get("model", "nova-2-medical"), 
                language=deepgram_settings.get("language", "en-US"),
                smart_format=deepgram_settings.get("smart_format", True),
                diarize=deepgram_settings.get("diarize", False),
                profanity_filter=deepgram_settings.get("profanity_filter", False),
                redact=deepgram_settings.get("redact", False),
                alternatives=deepgram_settings.get("alternatives", 1)
            )
            
            # Print API call details to terminal
            logging.debug("\n===== DEEPGRAM API CALL =====")
            logging.debug(f"Model: {options.model}")
            logging.debug(f"Language: {options.language}")
            logging.debug(f"Smart Format: {options.smart_format}")
            logging.debug(f"Diarize: {options.diarize}")
            logging.debug(f"Profanity Filter: {options.profanity_filter}")
            logging.debug(f"Redact: {options.redact}")
            logging.debug(f"Alternatives: {options.alternatives}")
            logging.debug(f"Buffer size: {buf.getbuffer().nbytes / 1024:.2f} KB")
            logging.debug("==============================\n")
            
            # Set higher timeout for large files
            config = get_config()
            base_timeout = config.api.timeout
            timeout_seconds = max(base_timeout, int(buf.getbuffer().nbytes / (500 * 1024)) * 60)
            self.logger.info(f"Setting Deepgram timeout to {timeout_seconds} seconds")
            
            # Make API call with resilience patterns
            try:
                response = self._make_api_call(buf, options, timeout_seconds)
            except (APIError, ServiceUnavailableError) as e:
                self.logger.error(f"API call failed: {str(e)}")
                logging.debug(f"\n===== DEEPGRAM ERROR =====")
                logging.debug(f"Error: {str(e)}")
                logging.debug("===========================\n")
                raise TranscriptionError(f"Failed to transcribe audio: {str(e)}")
            
            # Process response
            response_json = json.loads(response.to_json(indent=4))
            
            # Print successful response info to terminal
            logging.debug("\n===== DEEPGRAM API RESPONSE =====")
            logging.debug(f"Request ID: {response_json.get('request_id', 'unknown')}")
            
            # Extract metadata
            if "metadata" in response_json:
                metadata = response_json["metadata"]
                logging.debug(f"Duration: {metadata.get('duration', 'unknown')} seconds")
                logging.debug(f"Channels: {metadata.get('channels', 'unknown')}")
                logging.debug(f"Sample rate: {metadata.get('sample_rate', 'unknown')} Hz")
            
            # Extract transcript for preview
            transcript_preview = ""
            if "results" in response_json and response_json["results"].get("channels"):
                alternatives = response_json["results"]["channels"][0].get("alternatives", [])
                if alternatives and "transcript" in alternatives[0]:
                    transcript = alternatives[0]["transcript"]
                    transcript_preview = transcript[:100] + "..." if len(transcript) > 100 else transcript
                    logging.debug(f"Transcript preview: {transcript_preview}")
            
            logging.debug("=================================\n")
            
            # Check if diarization is enabled
            is_diarized = deepgram_settings.get("diarize", False)
            
            # Check for results
            if "results" in response_json and response_json["results"].get("channels"):
                alternatives = response_json["results"]["channels"][0].get("alternatives", [])
                
                if alternatives and "transcript" in alternatives[0]:
                    transcript = alternatives[0]["transcript"]
                    
                    # Process diarization if enabled
                    if is_diarized and "words" in alternatives[0]:
                        transcript = self._format_diarized_transcript(alternatives[0]["words"])
                else:
                    raise TranscriptionError("No transcript found in Deepgram response")
            else:
                raise TranscriptionError("Invalid response structure from Deepgram")
        
        except TranscriptionError:
            # Re-raise transcription errors
            raise
        except Exception as e:
            # Wrap unexpected errors
            self.logger.error(f"Unexpected error during transcription: {str(e)}", exc_info=True)
            raise TranscriptionError(f"Transcription failed: {str(e)}")
        finally:
            # Clean up the buffer
            if buf:
                try:
                    buf.close()
                except Exception as e:
                    self.logger.warning(f"Error closing buffer: {str(e)}")
        
        return transcript

    def _format_diarized_transcript(self, words: list) -> str:
        """Format diarized words from Deepgram into a readable transcript with speaker labels.
        
        Args:
            words: List of words from the Deepgram response
            
        Returns:
            Formatted text with speaker labels
        """
        if not words:
            return ""
        
        result = []
        current_speaker = None
        current_text = []
        
        for word_data in words:
            # Check if this word has speaker info
            if "speaker" not in word_data:
                continue
                
            speaker = word_data.get("speaker")
            word = word_data.get("word", "")
            
            # If new speaker, start a new paragraph
            if speaker != current_speaker:
                # Add previous paragraph if it exists
                if current_text:
                    speaker_label = f"Speaker {current_speaker}: " if current_speaker is not None else ""
                    result.append(f"{speaker_label}{''.join(current_text)}")
                    current_text = []
                
                current_speaker = speaker
            
            # Add word to current text
            # Add space before word if needed
            if current_text and not word.startswith(("'", ".", ",", "!", "?", ":", ";")):
                current_text.append(" ")
            current_text.append(word)
        
        # Add the last paragraph
        if current_text:
            speaker_label = f"Speaker {current_speaker}: " if current_speaker is not None else ""
            result.append(f"{speaker_label}{''.join(current_text)}")
        
        return "\n\n".join(result)
