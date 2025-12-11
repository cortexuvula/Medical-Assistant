"""
ElevenLabs STT provider implementation.
"""

import os
import time
import tempfile
import logging
import traceback
import requests
from typing import Optional, Dict, List, Any
from pydub import AudioSegment

from .base import BaseSTTProvider
from settings.settings import SETTINGS
from utils.exceptions import TranscriptionError, APIError, RateLimitError, ServiceUnavailableError
from utils.resilience import resilient_api_call
from utils.security_decorators import secure_api_call

class ElevenLabsProvider(BaseSTTProvider):
    """Implementation of the ElevenLabs STT provider."""

    @property
    def provider_name(self) -> str:
        """Return the provider identifier."""
        return "elevenlabs"

    @property
    def supports_diarization(self) -> bool:
        """ElevenLabs supports speaker diarization."""
        return True

    def __init__(self, api_key: str = "", language: str = "en-US"):
        """Initialize the ElevenLabs provider.

        Args:
            api_key: ElevenLabs API key
            language: Language code for speech recognition
        """
        super().__init__(api_key, language)

    @secure_api_call("elevenlabs")
    @resilient_api_call(
        max_retries=3,
        initial_delay=1.0,
        backoff_factor=2.0,
        failure_threshold=5,
        recovery_timeout=60
    )
    def _make_api_call(self, url: str, headers: dict, files: dict, data: dict, timeout: int):
        """Make the actual API call to ElevenLabs with retry logic.

        Args:
            url: API endpoint URL
            headers: Request headers
            files: Files to upload
            data: Request data
            timeout: Request timeout

        Returns:
            API response

        Raises:
            APIError: On API failures
            RateLimitError: On rate limit exceeded
            ServiceUnavailableError: On service unavailable
        """
        try:
            response = requests.post(
                url,
                headers=headers,
                files=files,
                data=data,
                timeout=timeout
            )
            # Check for HTTP errors
            if response.status_code == 429:
                raise RateLimitError(f"ElevenLabs rate limit exceeded: {response.text}")
            elif response.status_code >= 500:
                raise ServiceUnavailableError(f"ElevenLabs service error {response.status_code}: {response.text}")
            elif response.status_code >= 400:
                raise APIError(f"ElevenLabs API error {response.status_code}: {response.text}")
            return response
        except requests.exceptions.Timeout:
            raise ServiceUnavailableError("ElevenLabs request timeout")
        except requests.exceptions.ConnectionError as e:
            raise ServiceUnavailableError(f"ElevenLabs connection error: {e}")
        except (RateLimitError, ServiceUnavailableError, APIError):
            raise
        except Exception as e:
            raise APIError(f"ElevenLabs API error: {e}")

    def transcribe(self, segment: AudioSegment) -> str:
        """Transcribe audio using ElevenLabs API.
        
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
                
            url = "https://api.elevenlabs.io/v1/speech-to-text"
            headers = {
                'xi-api-key': self.api_key
            }
            
            # Check file size and adjust timeout accordingly
            file_size_kb = os.path.getsize(temp_file) / 1024
            
            # Add a minute of timeout for each 500KB of audio, with a minimum of 60 seconds
            timeout_seconds = max(60, int(file_size_kb / 500) * 60)
            self.logger.info(f"Setting ElevenLabs timeout to {timeout_seconds} seconds for {file_size_kb:.2f} KB file")
            
            # Prepare data for request
            data = {
                'model_id': 'scribe_v1'
            }
            
            # Add diarization parameters
            elevenlabs_settings = SETTINGS.get("elevenlabs", {})
            diarize = elevenlabs_settings.get("diarize", True)
            
            if diarize:
                # ElevenLabs API expects a boolean value
                data['diarize'] = True
                
                # Get number of speakers setting
                num_speakers = elevenlabs_settings.get("num_speakers", None)
                if num_speakers is not None:
                    data['num_speakers'] = num_speakers
                else:
                    data['num_speakers'] = 2  # Default to 2 speakers for diarization
                    
                # Setting additional parameters that might help with diarization
                language_code = elevenlabs_settings.get("language_code", "")
                if language_code:
                    data['language_code'] = language_code
                    
                timestamps_granularity = elevenlabs_settings.get("timestamps_granularity", "word")
                if timestamps_granularity:
                    data['timestamps_granularity'] = timestamps_granularity
            
            # Print API call details to terminal
            logging.debug("\n===== ELEVENLABS API CALL =====")
            logging.debug(f"URL: {url}")
            logging.debug(f"Headers: {{'xi-api-key': '****API_KEY_HIDDEN****'}}")
            logging.debug(f"Data parameters: {data}")
            logging.debug(f"File: {os.path.basename(temp_file)} (audio/wav)")
            logging.debug(f"Audio file size: {file_size_kb:.2f} KB")
            logging.debug(f"Timeout set to: {timeout_seconds} seconds")
            logging.debug("===============================\n")
            
            self.logger.info(f"ElevenLabs request data: {data}")

            # Use context manager to ensure file is always closed properly
            with open(temp_file, 'rb') as file_obj:
                # Create file tuple for request with the file object
                files = {
                    'file': ('audio.wav', file_obj, 'audio/wav')
                }

                # Make the request with retry logic
                try:
                    response = self._make_api_call(
                        url,
                        headers=headers,
                        files=files,
                        data=data,
                        timeout=timeout_seconds
                    )
                except (APIError, RateLimitError, ServiceUnavailableError) as e:
                    self.logger.error(f"ElevenLabs API call failed after retries: {e}")
                    raise TranscriptionError(f"ElevenLabs transcription failed: {e}")

            # Process response
            if response.status_code == 200:
                result = response.json()
                
                # Print successful response info to terminal
                logging.debug("\n===== ELEVENLABS API RESPONSE =====")
                logging.debug(f"Status: {response.status_code} OK")
                logging.debug(f"Response size: {len(response.text)} bytes")
                
                if 'words' in result:
                    word_count = len(result['words'])
                    logging.debug(f"Words transcribed: {word_count}")
                if 'text' in result:
                    text_preview = result['text'][:100] + "..." if len(result['text']) > 100 else result['text']
                    logging.debug(f"Text preview: {text_preview}")

                # Print response structure for debugging
                logging.debug("\n=== Response Structure ===")
                for key in result:
                    logging.debug(f"Key: {key}, Type: {type(result[key])}")
                    if key == 'words' and result['words']:
                        logging.debug(f"Sample word entry: {result['words'][0]}")
                        logging.debug(f"Available fields in word entry: {list(result['words'][0].keys())}")
                
                # More detailed debug info for speaker diarization
                logging.debug("\n=== Diarization Debug ===")
                logging.debug(f"Diarization requested: {diarize}")
                
                # Check for diarization data in different possible locations
                has_speaker_info = False
                diarization_location = None
                
                # Check if the result itself has a 'speakers' field
                if 'speakers' in result:
                    has_speaker_info = True
                    diarization_location = "root.speakers"
                    logging.debug(f"Found speakers data at root level: {result['speakers']}")
                
                # Check if there's a separate 'diarization' field
                if 'diarization' in result:
                    has_speaker_info = True
                    diarization_location = "root.diarization"
                    logging.debug(f"Found diarization data: {result['diarization']}")
                
                # Check word-level speaker information
                if 'words' in result and result['words']:
                    word_fields = set()
                    for key in result['words'][0].keys():
                        word_fields.add(key)
                        if 'speaker' in key.lower():
                            has_speaker_info = True
                            diarization_location = f"words.{key}"
                    
                    logging.debug(f"Word-level fields: {word_fields}")
                    
                    # Print first 3 words with full details
                    logging.debug("\nFirst 3 word entries (full details):")
                    for i, word in enumerate(result['words'][:3]):
                        logging.debug(f"Word {i+1}: {word}")
                
                # Based on our findings, determine if and how to process diarization
                if has_speaker_info:
                    logging.debug(f"\nFound speaker information at: {diarization_location}")
                    
                    # Method 1: If we have word-level speaker info
                    if diarization_location and diarization_location.startswith("words."):
                        speaker_field = diarization_location.split('.')[1]
                        transcript = self._format_diarized_transcript_with_field(result['words'], speaker_field)
                    
                    # Method 2: If we have a separate diarization structure, build transcript accordingly
                    elif diarization_location == "root.diarization" and 'diarization' in result:
                        transcript = self._format_diarized_transcript_from_segments(result)
                    
                    # Method 3: If there's a root.speakers field but not word-level
                    elif diarization_location == "root.speakers" and 'speakers' in result:
                        transcript = self._format_diarized_transcript_from_speakers(result)
                    
                    # Fallback: Use the general formatting approach
                    else:
                        transcript = self._format_diarized_transcript(result['words'])
                    
                    logging.debug(f"\nGenerated diarized transcript with speaker labels")
                else:
                    # Use plain text if not diarized
                    transcript = result.get("text", "")
                    logging.debug(f"\nUsing plain text transcript (no speaker information found)")
                    
            else:
                error_msg = f"ElevenLabs API error: {response.status_code} - {response.text}"
                self.logger.error(error_msg)
                logging.debug(f"\n===== ELEVENLABS ERROR =====")
                logging.debug(f"Status: {response.status_code}")
                logging.debug(f"Response: {response.text}")
                logging.debug("============================\n")
                
        except Exception as e:
            error_msg = f"Error with ElevenLabs transcription: {str(e)}"
            self.logger.error(error_msg, exc_info=True)

            # Print exception details to terminal
            logging.debug("\n===== ELEVENLABS EXCEPTION =====")
            logging.debug(f"Error: {str(e)}")
            logging.debug(f"Traceback: {traceback.format_exc()}")
            logging.debug("================================\n")

        finally:
            # File handle is automatically closed by context manager
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

    def _format_diarized_transcript(self, words: list) -> str:
        """Format diarized words from ElevenLabs into a readable transcript with speaker labels.
        
        Args:
            words: List of words from the ElevenLabs response
            
        Returns:
            Formatted text with speaker labels
        """
        if not words:
            return ""
        
        result = []
        current_speaker = None
        current_text = []
        
        # Debug the first few words to understand structure
        logging.debug("\nFormatting transcript with the following word data structure:")
        sample_words = words[:3] if len(words) > 3 else words
        for i, word in enumerate(sample_words):
            logging.debug(f"Sample word {i}: {word}")
        
        for word_data in words:
            # Check various possible field names for speaker information
            speaker = None
            
            # Try different possible field names for speaker information
            if "speaker" in word_data:
                speaker = word_data.get("speaker")
            elif "speaker_id" in word_data:
                speaker = word_data.get("speaker_id")
            elif "speaker_turn" in word_data:
                speaker = word_data.get("speaker_turn")
            
            # If we still don't have speaker info, try to get it from a nested field
            if speaker is None and "speaker_data" in word_data:
                speaker_data = word_data.get("speaker_data", {})
                if isinstance(speaker_data, dict):
                    speaker = speaker_data.get("id") or speaker_data.get("speaker") or speaker_data.get("speaker_id")
            
            # If we can't find any speaker info, skip this word or use default
            if speaker is None:
                # For debugging, print the problematic word data
                logging.debug(f"Warning: No speaker info found in word data: {word_data}")
                # Use previous speaker if available, otherwise use "Unknown"
                speaker = current_speaker if current_speaker is not None else "Unknown"
            
            # Get the actual word text
            word = word_data.get("word", "")
            if not word and "text" in word_data:
                word = word_data.get("text", "")
            
            # Skip empty words
            if not word.strip():
                continue
            
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

    def _format_diarized_transcript_with_field(self, words: list, speaker_field: str) -> str:
        """Format diarized words from ElevenLabs into a readable transcript with speaker labels.
        
        Args:
            words: List of words from the ElevenLabs response
            speaker_field: Field name for speaker information
            
        Returns:
            Formatted text with speaker labels
        """
        if not words:
            return ""
        
        result = []
        current_speaker = None
        current_text = []
        
        for word_data in words:
            speaker = word_data.get(speaker_field)
            
            # If we can't find any speaker info, skip this word or use default
            if speaker is None:
                # For debugging, print the problematic word data
                logging.debug(f"Warning: No speaker info found in word data: {word_data}")
                # Use previous speaker if available, otherwise use "Unknown"
                speaker = current_speaker if current_speaker is not None else "Unknown"
            
            # Get the actual word text
            word = word_data.get("word", "")
            if not word and "text" in word_data:
                word = word_data.get("text", "")
            
            # Skip empty words
            if not word.strip():
                continue
            
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

    def _format_diarized_transcript_from_segments(self, result: dict) -> str:
        """Format diarized transcript from ElevenLabs segments.
        
        Args:
            result: ElevenLabs response with diarization data
            
        Returns:
            Formatted text with speaker labels
        """
        if not result or 'diarization' not in result:
            return ""
        
        diarization = result['diarization']
        if not diarization:
            return ""
        
        result = []
        current_speaker = None
        current_text = []
        
        for segment in diarization:
            speaker = segment.get("speaker")
            
            # If we can't find any speaker info, skip this segment or use default
            if speaker is None:
                # For debugging, print the problematic segment data
                logging.debug(f"Warning: No speaker info found in segment data: {segment}")
                # Use previous speaker if available, otherwise use "Unknown"
                speaker = current_speaker if current_speaker is not None else "Unknown"
            
            # Get the actual segment text
            text = segment.get("text", "")
            
            # Skip empty segments
            if not text.strip():
                continue
            
            # If new speaker, start a new paragraph
            if speaker != current_speaker:
                # Add previous paragraph if it exists
                if current_text:
                    speaker_label = f"Speaker {current_speaker}: " if current_speaker is not None else ""
                    result.append(f"{speaker_label}{''.join(current_text)}")
                    current_text = []
                
                current_speaker = speaker
            
            # Add segment to current text
            current_text.append(text)
        
        # Add the last paragraph
        if current_text:
            speaker_label = f"Speaker {current_speaker}: " if current_speaker is not None else ""
            result.append(f"{speaker_label}{''.join(current_text)}")
        
        return "\n\n".join(result)

    def _format_diarized_transcript_from_speakers(self, result: dict) -> str:
        """Format diarized transcript from ElevenLabs speakers.
        
        Args:
            result: ElevenLabs response with speakers data
            
        Returns:
            Formatted text with speaker labels
        """
        if not result or 'speakers' not in result:
            return ""
        
        speakers = result['speakers']
        if not speakers:
            return ""
        
        result = []
        current_speaker = None
        current_text = []
        
        for speaker in speakers:
            speaker_id = speaker.get("id")
            segments = speaker.get("segments", [])
            
            # If we can't find any speaker info, skip this speaker or use default
            if speaker_id is None:
                # For debugging, print the problematic speaker data
                logging.debug(f"Warning: No speaker info found in speaker data: {speaker}")
                # Use previous speaker if available, otherwise use "Unknown"
                speaker_id = current_speaker if current_speaker is not None else "Unknown"
            
            # If new speaker, start a new paragraph
            if speaker_id != current_speaker:
                # Add previous paragraph if it exists
                if current_text:
                    speaker_label = f"Speaker {current_speaker}: " if current_speaker is not None else ""
                    result.append(f"{speaker_label}{''.join(current_text)}")
                    current_text = []
                
                current_speaker = speaker_id
            
            # Add segments to current text
            for segment in segments:
                text = segment.get("text", "")
                current_text.append(text)
        
        # Add the last paragraph
        if current_text:
            speaker_label = f"Speaker {current_speaker}: " if current_speaker is not None else ""
            result.append(f"{speaker_label}{''.join(current_text)}")
        
        return "\n\n".join(result)
