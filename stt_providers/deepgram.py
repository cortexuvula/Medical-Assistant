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
from settings import SETTINGS, _DEFAULT_SETTINGS

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
    
    def transcribe(self, segment: AudioSegment) -> str:
        """Transcribe audio using Deepgram API with improved error handling.
        
        Args:
            segment: AudioSegment to transcribe
            
        Returns:
            Transcription text or empty string if failed
        """
        if not self.client:
            self.logger.warning("Deepgram client not initialized - check API key")
            return ""
        
        max_retries = 2
        retry_delay = 2  # seconds
        attempt = 0
        
        # Get Deepgram settings from SETTINGS
        deepgram_settings = SETTINGS.get("deepgram", _DEFAULT_SETTINGS["deepgram"])
        
        # Prepare a buffer outside the retry loop so we can close it properly
        buf = None
        transcript = ""
        
        try:
            while attempt <= max_retries:
                try:
                    self.logger.info(f"Deepgram transcription attempt {attempt+1}/{max_retries+1}")
                    
                    # Clean up previous buffer if it exists
                    if buf:
                        buf.close()
                        
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
                    print("\n===== DEEPGRAM API CALL =====")
                    print(f"Attempt: {attempt+1}/{max_retries+1}")
                    print(f"Model: {options.model}")
                    print(f"Language: {options.language}")
                    print(f"Smart Format: {options.smart_format}")
                    print(f"Diarize: {options.diarize}")
                    print(f"Profanity Filter: {options.profanity_filter}")
                    print(f"Redact: {options.redact}")
                    print(f"Alternatives: {options.alternatives}")
                    print(f"Buffer size: {buf.getbuffer().nbytes / 1024:.2f} KB")
                    print("==============================\n")
                    
                    # Set higher timeout for large files
                    timeout_seconds = max(60, int(buf.getbuffer().nbytes / (500 * 1024)) * 60)
                    self.logger.info(f"Setting Deepgram timeout to {timeout_seconds} seconds")
                    
                    # Make API call
                    response = self.client.listen.rest.v("1").transcribe_file(
                        {"buffer": buf}, 
                        options,
                        timeout=timeout_seconds
                    )
                    
                    # Process response
                    response_json = json.loads(response.to_json(indent=4))
                    
                    # Print successful response info to terminal
                    print("\n===== DEEPGRAM API RESPONSE =====")
                    print(f"Request ID: {response_json.get('request_id', 'unknown')}")
                    
                    # Extract metadata
                    if "metadata" in response_json:
                        metadata = response_json["metadata"]
                        print(f"Duration: {metadata.get('duration', 'unknown')} seconds")
                        print(f"Channels: {metadata.get('channels', 'unknown')}")
                        print(f"Sample rate: {metadata.get('sample_rate', 'unknown')} Hz")
                    
                    # Extract transcript for preview
                    transcript_preview = ""
                    if "results" in response_json and response_json["results"].get("channels"):
                        alternatives = response_json["results"]["channels"][0].get("alternatives", [])
                        if alternatives and "transcript" in alternatives[0]:
                            transcript = alternatives[0]["transcript"]
                            transcript_preview = transcript[:100] + "..." if len(transcript) > 100 else transcript
                            print(f"Transcript preview: {transcript_preview}")
                    
                    print("=================================\n")
                    
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
                            
                            # If we got a transcript, we can break out of the retry loop
                            break
                    
                    # If we get here, response structure wasn't as expected
                    self.logger.warning(f"Unexpected Deepgram response structure on attempt {attempt+1}")
                    
                    # Increment attempt counter and retry if needed
                    attempt += 1
                    if attempt <= max_retries:
                        self.logger.info(f"Retrying Deepgram transcription in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                
                except Exception as e:
                    self.logger.error(f"Deepgram transcription error on attempt {attempt+1}: {str(e)}", exc_info=True)
                    print(f"\n===== DEEPGRAM ERROR =====")
                    print(f"Attempt {attempt+1}/{max_retries+1}")
                    print(f"Error: {str(e)}")
                    print("===========================\n")
                    
                    # Increment attempt counter and retry if needed
                    attempt += 1
                    if attempt <= max_retries:
                        self.logger.info(f"Retrying Deepgram transcription in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                    else:
                        self.logger.error("Maximum retry attempts reached for Deepgram transcription")
                        break
        
        finally:
            # Clean up the buffer
            if buf:
                try:
                    buf.close()
                except Exception as e:
                    self.logger.warning(f"Error closing buffer: {str(e)}")
        
        # Return whatever transcript we have (or empty string on failure)
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
