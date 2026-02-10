"""
ElevenLabs STT provider implementation.
"""

import os
import time
import traceback
from io import BytesIO
from typing import Optional, Dict, List, Any
from pydub import AudioSegment

from .base import BaseSTTProvider
from settings.settings_manager import settings_manager
from utils.exceptions import TranscriptionError, APIError, RateLimitError, ServiceUnavailableError
from utils.resilience import resilient_api_call
from utils.security_decorators import secure_api_call
from utils.http_client_manager import get_http_client_manager

# API endpoint constants
ELEVENLABS_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"


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

        Uses pooled HTTP session for connection reuse (saves 50-200ms per call).

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
        import requests  # Import here to handle requests.exceptions

        try:
            # Use pooled HTTP session for connection reuse
            session = get_http_client_manager().get_requests_session("elevenlabs")
            response = session.post(
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

    def _validate_and_log_audio(self, segment: AudioSegment) -> dict:
        """Validate audio segment and log its details.

        Args:
            segment: AudioSegment to validate

        Returns:
            Dictionary with audio details
        """
        details = {
            'duration_ms': len(segment),
            'duration_seconds': len(segment) / 1000,
            'frame_rate': segment.frame_rate,
            'channels': segment.channels,
            'sample_width': segment.sample_width,
            'frame_count': segment.frame_count()
        }

        self.logger.info(f"Audio segment details: duration_ms={details['duration_ms']}, "
                        f"frame_rate={details['frame_rate']}, channels={details['channels']}, "
                        f"sample_width={details['sample_width']}, frame_count={details['frame_count']}")

        # Warn if parameters seem unusual
        if details['frame_rate'] not in [16000, 22050, 44100, 48000]:
            self.logger.warning(f"Unusual sample rate: {details['frame_rate']}")
        if details['channels'] not in [1, 2]:
            self.logger.warning(f"Unusual channel count: {details['channels']}")
        if details['sample_width'] not in [1, 2, 4]:
            self.logger.warning(f"Unusual sample width: {details['sample_width']}")

        return details

    def transcribe(self, segment: AudioSegment) -> str:
        """Transcribe audio using ElevenLabs API.

        Uses BytesIO buffer instead of temp files for 2-5 seconds faster processing.

        Args:
            segment: Audio segment to transcribe

        Returns:
            Transcription text
        """
        if not self._check_api_key():
            return ""

        transcript = ""
        # Validate and log audio segment details before processing (outside try for access in truncation check)
        audio_details = self._validate_and_log_audio(segment)

        try:

            # Export audio to BytesIO buffer instead of temp file (saves 2-5 seconds)
            audio_buffer = BytesIO()
            segment.export(audio_buffer, format="wav")
            audio_buffer.seek(0)

            url = ELEVENLABS_STT_URL
            headers = {
                'xi-api-key': self.api_key
            }

            # Get buffer size and adjust timeout accordingly
            file_size_kb = len(audio_buffer.getvalue()) / 1024
            
            # Add a minute of timeout for each 500KB of audio, with a minimum of 60 seconds
            timeout_seconds = max(60, int(file_size_kb / 500) * 60)
            self.logger.info(f"Setting ElevenLabs timeout to {timeout_seconds} seconds for {file_size_kb:.2f} KB file")
            
            # Get settings
            elevenlabs_settings = settings_manager.get("elevenlabs", {})

            # Prepare data for request - model_id from settings (scribe_v2 is new default)
            data = {
                'model_id': elevenlabs_settings.get("model_id", "scribe_v2")
            }

            # Add temperature if set (controls creativity/accuracy tradeoff)
            temperature = elevenlabs_settings.get("temperature")
            if temperature is not None:
                data['temperature'] = temperature

            # Add diarization parameters
            diarize = elevenlabs_settings.get("diarize", True)
            
            if diarize:
                # ElevenLabs API expects lowercase "true"/"false" in multipart form data;
                # Python's requests library sends bool True as "True" (capital T) which
                # the API may silently ignore.
                data['diarize'] = 'true'
                
                # Get number of speakers setting
                num_speakers = elevenlabs_settings.get("num_speakers", None)
                if num_speakers is not None:
                    data['num_speakers'] = str(num_speakers)
                # When num_speakers is None, omit it so API auto-detects
                # and diarization_threshold takes effect
                    
                # Setting additional parameters that might help with diarization
                language_code = elevenlabs_settings.get("language_code", "")
                if language_code:
                    data['language_code'] = language_code
                    
                timestamps_granularity = elevenlabs_settings.get("timestamps_granularity", "word")
                if timestamps_granularity:
                    data['timestamps_granularity'] = timestamps_granularity

                # Add diarization threshold if set (fine-tune speaker detection)
                # Only effective when num_speakers is omitted (per ElevenLabs docs)
                diarization_threshold = elevenlabs_settings.get("diarization_threshold")
                if diarization_threshold is not None:
                    data['diarization_threshold'] = str(diarization_threshold)

            # Add audio event tagging setting (controls ambient sound descriptions)
            # When False, transcription won't include things like "[keyboard clicking]"
            tag_audio_events = elevenlabs_settings.get("tag_audio_events", True)
            data['tag_audio_events'] = str(tag_audio_events).lower()

            # Add entity detection if configured (scribe_v2 feature)
            # Options: "phi" (health info), "pii" (personal info), "pci" (payment info), "offensive"
            entity_detection = elevenlabs_settings.get("entity_detection", [])
            if entity_detection:
                data['entity_detection'] = entity_detection

            # Add keyterms if configured (scribe_v2 feature)
            # Up to 100 medical terms to bias recognition
            keyterms = elevenlabs_settings.get("keyterms", [])
            if keyterms:
                data['keyterms'] = keyterms

            # Print API call details to terminal
            self.logger.debug("\n===== ELEVENLABS API CALL =====")
            self.logger.debug(f"URL: {url}")
            self.logger.debug(f"Headers: {{'xi-api-key': '****API_KEY_HIDDEN****'}}")
            self.logger.debug(f"Data parameters: {data}")
            self.logger.debug(f"File: audio.wav (BytesIO buffer)")
            self.logger.debug(f"Audio file size: {file_size_kb:.2f} KB")
            self.logger.debug(f"Timeout set to: {timeout_seconds} seconds")
            self.logger.debug("===============================\n")

            self.logger.info(f"ElevenLabs request data: {data}")

            # Create file tuple for request with the BytesIO buffer
            files = {
                'file': ('audio.wav', audio_buffer, 'audio/wav')
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
                self.logger.debug("\n===== ELEVENLABS API RESPONSE =====")
                self.logger.debug(f"Status: {response.status_code} OK")
                self.logger.debug(f"Response size: {len(response.text)} bytes")
                
                if 'words' in result:
                    word_count = len(result['words'])
                    self.logger.debug(f"Words transcribed: {word_count}")
                if 'text' in result:
                    text_preview = result['text'][:100] + "..." if len(result['text']) > 100 else result['text']
                    self.logger.debug(f"Text preview: {text_preview}")

                # Handle entity detection results (scribe_v2 feature)
                detected_entities = result.get('entities', [])
                if detected_entities:
                    self.logger.debug(f"\n=== Entity Detection Results ===")
                    self.logger.debug(f"Detected {len(detected_entities)} entities:")
                    for entity in detected_entities:
                        entity_type = entity.get('entity_type', 'unknown')
                        entity_text = entity.get('text', '')
                        self.logger.info(f"Detected {entity_type}: '{entity_text}'")
                        self.logger.debug(f"  - {entity_type}: '{entity_text}' (chars {entity.get('start_char')}-{entity.get('end_char')})")

                # Print response structure for debugging
                self.logger.debug("\n=== Response Structure ===")
                for key in result:
                    self.logger.debug(f"Key: {key}, Type: {type(result[key])}")
                    if key == 'words' and result['words']:
                        self.logger.debug(f"Sample word entry: {result['words'][0]}")
                        self.logger.debug(f"Available fields in word entry: {list(result['words'][0].keys())}")
                
                # More detailed debug info for speaker diarization
                self.logger.info(f"Diarization debug: requested={diarize}, response_keys={list(result.keys())}")
                self.logger.debug("\n=== Diarization Debug ===")
                
                # Check for diarization data in different possible locations
                has_speaker_info = False
                diarization_location = None
                
                # Check if the result itself has a 'speakers' field
                if 'speakers' in result:
                    has_speaker_info = True
                    diarization_location = "root.speakers"
                    self.logger.debug(f"Found speakers data at root level: {result['speakers']}")
                
                # Check if there's a separate 'diarization' field
                if 'diarization' in result:
                    has_speaker_info = True
                    diarization_location = "root.diarization"
                    self.logger.debug(f"Found diarization data: {result['diarization']}")
                
                # Check word-level speaker information
                # Scan multiple word entries (not just the first) because spacing/
                # punctuation/audio_event entries may lack speaker_id
                if 'words' in result and result['words']:
                    word_fields = set()
                    sample_count = min(20, len(result['words']))
                    for entry in result['words'][:sample_count]:
                        for key in entry.keys():
                            word_fields.add(key)
                            if 'speaker' in key.lower():
                                has_speaker_info = True
                                # Prefer 'speaker_id' over other speaker-related fields
                                # (e.g. 'speaker_confidence') to avoid picking a float
                                if key == 'speaker_id' or diarization_location is None:
                                    diarization_location = f"words.{key}"

                    self.logger.debug(f"Word-level fields (from first {sample_count} entries): {word_fields}")

                    # Print first 3 words with full details
                    self.logger.debug("\nFirst 3 word entries (full details):")
                    for i, word in enumerate(result['words'][:3]):
                        self.logger.debug(f"Word {i+1}: {word}")
                
                # Log unique speakers found for diagnostics
                if has_speaker_info and diarization_location and diarization_location.startswith("words."):
                    speaker_field_name = diarization_location.split('.')[1]
                    unique_speakers = set()
                    for w in result['words']:
                        sid = w.get(speaker_field_name)
                        if sid is not None:
                            unique_speakers.add(sid)
                    self.logger.info(
                        f"Diarization result: {len(unique_speakers)} unique speakers detected "
                        f"(field: {speaker_field_name}, speakers: {unique_speakers})"
                    )
                    # Console-visible diagnostic so user can see diarization results
                    diag_parts = [
                        f"[ElevenLabs Diarization] {len(unique_speakers)} speaker(s) detected",
                        f"IDs: {sorted(unique_speakers)}",
                    ]
                    if 'num_speakers' in data:
                        diag_parts.append(f"num_speakers sent: {data['num_speakers']}")
                    else:
                        diag_parts.append("num_speakers: auto-detect")
                    if 'diarization_threshold' in data:
                        diag_parts.append(f"threshold: {data['diarization_threshold']}")
                    print(" | ".join(diag_parts))

                # Based on our findings, determine if and how to process diarization
                if has_speaker_info:
                    self.logger.debug(f"\nFound speaker information at: {diarization_location}")
                    
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
                    
                    self.logger.debug(f"\nGenerated diarized transcript with speaker labels")
                else:
                    # Use plain text if not diarized
                    transcript = result.get("text", "")
                    self.logger.warning(
                        f"No speaker information found in ElevenLabs response. "
                        f"Diarize was {'enabled' if diarize else 'disabled'}. "
                        f"Word count: {len(result.get('words', []))}. "
                        f"Word fields: {set().union(*(w.keys() for w in result.get('words', [])[:5])) if result.get('words') else 'N/A'}. "
                        f"Using plain text fallback."
                    )

                # Warn if diarization was enabled but only one speaker came through
                if diarize and transcript and transcript.count("Speaker ") <= 1:
                    tips = [
                        "Diarization was enabled but only one speaker detected.",
                        "Tips: (1) Leave 'Number of Speakers' empty to let the API auto-detect.",
                        "(2) Lower the 'Diarization Threshold' (e.g. 0.3) for more sensitive detection.",
                        "(3) Ensure audio has clear speech from multiple speakers.",
                        "(4) Check that 'num_speakers' is not being forced to a fixed value.",
                    ]
                    self.logger.warning(" ".join(tips))
                    print(f"[ElevenLabs Diarization] WARNING: Only 1 speaker detected. "
                          f"Try leaving 'Number of Speakers' empty in ElevenLabs Settings.")

            else:
                error_msg = f"ElevenLabs API error: {response.status_code} - {response.text}"
                self.logger.error(error_msg)
                self.logger.debug(f"\n===== ELEVENLABS ERROR =====")
                self.logger.debug(f"Status: {response.status_code}")
                self.logger.debug(f"Response: {response.text}")
                self.logger.debug("============================\n")
                
        except Exception as e:
            error_msg = f"Error with ElevenLabs transcription: {str(e)}"
            self.logger.error(error_msg, exc_info=True)

            # Print exception details to terminal
            self.logger.debug("\n===== ELEVENLABS EXCEPTION =====")
            self.logger.debug(f"Error: {str(e)}")
            self.logger.debug(f"Traceback: {traceback.format_exc()}")
            self.logger.debug("================================\n")

        # Check for possible truncation
        if transcript and audio_details:
            duration_seconds = audio_details.get('duration_seconds', 0)
            # Expect at least 3 characters per second of speech (very conservative)
            expected_chars_min = duration_seconds * 3
            if len(transcript) < expected_chars_min and duration_seconds > 10:
                self.logger.warning(
                    f"Possible transcription truncation detected: got {len(transcript)} chars "
                    f"for {duration_seconds:.1f}s audio (expected at least {expected_chars_min:.0f}). "
                    f"Audio params: frame_rate={audio_details.get('frame_rate')}, "
                    f"channels={audio_details.get('channels')}, sample_width={audio_details.get('sample_width')}"
                )
                # Try file-based fallback if enabled
                elevenlabs_settings = settings_manager.get("elevenlabs", {})
                if elevenlabs_settings.get("retry_with_file", False):
                    self.logger.info("Attempting file-based transcription fallback...")
                    fallback_transcript = self._transcribe_via_temp_file(segment)
                    if fallback_transcript and len(fallback_transcript) > len(transcript):
                        self.logger.info(f"File fallback succeeded: {len(fallback_transcript)} chars vs {len(transcript)}")
                        transcript = fallback_transcript

        # Return whatever transcript we got, empty string if we failed
        # No temp file cleanup needed with BytesIO
        return transcript

    def _transcribe_via_temp_file(self, segment: AudioSegment) -> str:
        """Fallback transcription using temp file instead of BytesIO.

        This can help when BytesIO export produces corrupted audio.

        Args:
            segment: AudioSegment to transcribe

        Returns:
            Transcription text or empty string if failed
        """
        import tempfile
        import os

        temp_path = None
        try:
            # Create temp file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name
                segment.export(temp_path, format="wav")

            self.logger.info(f"Created temp file for fallback: {temp_path} ({os.path.getsize(temp_path)} bytes)")

            # Read file and send to API
            url = ELEVENLABS_STT_URL
            headers = {'xi-api-key': self.api_key}

            elevenlabs_settings = settings_manager.get("elevenlabs", {})
            data = {
                'model_id': elevenlabs_settings.get("model_id", "scribe_v2"),
                'diarize': str(elevenlabs_settings.get("diarize", True)).lower(),
            }

            # Only send num_speakers if explicitly set (omit for auto-detection)
            num_speakers = elevenlabs_settings.get("num_speakers", None)
            if num_speakers is not None:
                data['num_speakers'] = str(num_speakers)

            # Forward diarization_threshold (only effective when num_speakers omitted)
            diarization_threshold = elevenlabs_settings.get("diarization_threshold")
            if diarization_threshold is not None:
                data['diarization_threshold'] = str(diarization_threshold)

            # Add entity detection if configured
            entity_detection = elevenlabs_settings.get("entity_detection", [])
            if entity_detection:
                data['entity_detection'] = entity_detection

            # Add keyterms if configured
            keyterms = elevenlabs_settings.get("keyterms", [])
            if keyterms:
                data['keyterms'] = keyterms

            with open(temp_path, 'rb') as audio_file:
                files = {'file': ('audio.wav', audio_file, 'audio/wav')}
                response = self._make_api_call(url, headers=headers, files=files, data=data, timeout=300)

            if response.status_code == 200:
                result = response.json()
                return result.get("text", "")
            else:
                self.logger.error(f"File fallback failed: {response.status_code} - {response.text}")
                return ""

        except Exception as e:
            self.logger.error(f"File fallback error: {e}", exc_info=True)
            return ""
        finally:
            # Clean up temp file
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

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
        self.logger.debug("\nFormatting transcript with the following word data structure:")
        sample_words = words[:3] if len(words) > 3 else words
        for i, word in enumerate(sample_words):
            self.logger.debug(f"Sample word {i}: {word}")
        
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
                self.logger.debug(f"Warning: No speaker info found in word data: {word_data}")
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
                self.logger.debug(f"Warning: No speaker info found in word data: {word_data}")
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
                self.logger.debug(f"Warning: No speaker info found in segment data: {segment}")
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
                self.logger.debug(f"Warning: No speaker info found in speaker data: {speaker}")
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
