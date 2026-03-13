"""
Modulate.ai Velma Transcribe STT provider implementation.

Provides speech-to-text transcription with unique features including:
- 20+ emotion detection per utterance
- Speaker diarization with accent detection
- Deepfake/synthetic speech detection
- PII/PHI redaction
"""

import time
import traceback
from io import BytesIO
from typing import Optional, Dict, List, Any
from pydub import AudioSegment

from .base import BaseSTTProvider, TranscriptionResult
from settings.settings_manager import settings_manager
from utils.exceptions import TranscriptionError, APIError, RateLimitError, ServiceUnavailableError
from utils.resilience import resilient_api_call
from utils.security_decorators import secure_api_call
from utils.http_client_manager import get_http_client_manager

# API endpoint constants
MODULATE_TRANSCRIBE_URL = "https://api.modulate.ai/transcribe"


class ModulateProvider(BaseSTTProvider):
    """Implementation of the Modulate.ai Velma Transcribe STT provider.

    Features beyond standard transcription:
    - Emotion detection (20+ emotions per utterance)
    - Speaker diarization with accent detection
    - Deepfake/synthetic speech detection
    - PII/PHI automatic redaction
    """

    @staticmethod
    def _clean_speaker_label(speaker_id) -> str:
        """Convert speaker_id like 'speaker_0' to clean label '0'."""
        sid = str(speaker_id)
        if sid.startswith("speaker_"):
            return sid[len("speaker_"):]
        return sid

    @property
    def provider_name(self) -> str:
        """Return the provider identifier."""
        return "modulate"

    @property
    def supports_diarization(self) -> bool:
        """Modulate.ai supports speaker diarization."""
        return True

    def __init__(self, api_key: str = "", language: str = "en-US"):
        """Initialize the Modulate.ai provider.

        Args:
            api_key: Modulate.ai API key
            language: Language code for speech recognition
        """
        super().__init__(api_key, language)

    @secure_api_call("modulate")
    @resilient_api_call(
        max_retries=3,
        initial_delay=1.0,
        backoff_factor=2.0,
        failure_threshold=5,
        recovery_timeout=60
    )
    def _make_api_call(self, url: str, headers: dict, files: dict, data: dict, timeout: int):
        """Make the actual API call to Modulate.ai with retry logic.

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
        import requests

        try:
            # Use pooled HTTP session for connection reuse
            session = get_http_client_manager().get_requests_session("modulate")
            response = session.post(
                url,
                headers=headers,
                files=files,
                data=data,
                timeout=timeout
            )
            # Check for HTTP errors
            if response.status_code == 429:
                raise RateLimitError(f"Modulate.ai rate limit exceeded: {response.text}")
            elif response.status_code >= 500:
                raise ServiceUnavailableError(f"Modulate.ai service error {response.status_code}: {response.text}")
            elif response.status_code >= 400:
                raise APIError(f"Modulate.ai API error {response.status_code}: {response.text}")
            return response
        except requests.exceptions.Timeout:
            raise ServiceUnavailableError("Modulate.ai request timeout")
        except requests.exceptions.ConnectionError as e:
            raise ServiceUnavailableError(f"Modulate.ai connection error: {e}")
        except (RateLimitError, ServiceUnavailableError, APIError):
            raise
        except Exception as e:
            raise APIError(f"Modulate.ai API error: {e}")

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

    def _get_modulate_settings(self) -> dict:
        """Get Modulate.ai settings from settings manager.

        Returns:
            Dictionary of Modulate.ai settings with defaults
        """
        return settings_manager.get("modulate", {})

    def transcribe(self, segment: AudioSegment) -> str:
        """Transcribe audio using Modulate.ai Velma Transcribe API.

        Uses BytesIO buffer instead of temp files for faster processing.

        Args:
            segment: Audio segment to transcribe

        Returns:
            Transcription text or empty string if failed
        """
        if not self._check_api_key():
            return ""

        transcript = ""
        audio_details = self._validate_and_log_audio(segment)

        try:
            # Export audio to BytesIO buffer
            audio_buffer = BytesIO()
            segment.export(audio_buffer, format="wav")
            audio_buffer.seek(0)

            url = MODULATE_TRANSCRIBE_URL
            headers = {
                'Authorization': f'Bearer {self.api_key}'
            }

            # Calculate timeout based on file size
            file_size_kb = len(audio_buffer.getvalue()) / 1024
            timeout_seconds = max(60, int(file_size_kb / 500) * 60)
            self.logger.info(f"Setting Modulate.ai timeout to {timeout_seconds} seconds for {file_size_kb:.2f} KB file")

            # Get settings
            modulate_settings = self._get_modulate_settings()

            # Prepare data for request
            data = {
                'model': modulate_settings.get("model", "velma-v1"),
                'language': modulate_settings.get("language", self.language or "en-US"),
            }

            # Add diarization parameters
            enable_diarization = modulate_settings.get("enable_diarization", True)
            if enable_diarization:
                data['diarize'] = 'true'

                num_speakers = modulate_settings.get("num_speakers")
                if num_speakers is not None:
                    data['num_speakers'] = str(num_speakers)
            else:
                data['diarize'] = 'false'

            # Add emotion detection
            enable_emotions = modulate_settings.get("enable_emotions", True)
            if enable_emotions:
                data['enable_emotions'] = 'true'

            # Add deepfake detection
            enable_deepfake_detection = modulate_settings.get("enable_deepfake_detection", False)
            if enable_deepfake_detection:
                data['enable_deepfake_detection'] = 'true'

            # Add PII/PHI redaction
            enable_pii_redaction = modulate_settings.get("enable_pii_redaction", False)
            if enable_pii_redaction:
                data['enable_pii_redaction'] = 'true'

            # Log API call details
            self.logger.debug("\n===== MODULATE API CALL =====")
            self.logger.debug(f"URL: {url}")
            self.logger.debug(f"Headers: {{'Authorization': 'Bearer ****API_KEY_HIDDEN****'}}")
            self.logger.debug(f"Data parameters: {data}")
            self.logger.debug(f"File: audio.wav (BytesIO buffer)")
            self.logger.debug(f"Audio file size: {file_size_kb:.2f} KB")
            self.logger.debug(f"Timeout set to: {timeout_seconds} seconds")
            self.logger.debug("=============================\n")

            self.logger.info(f"Modulate.ai request data: {data}")

            # Create file tuple for request
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
                self.logger.error(f"Modulate.ai API call failed after retries: {e}")
                raise TranscriptionError(f"Modulate.ai transcription failed: {e}")

            # Process response
            if response.status_code == 200:
                try:
                    result = response.json()
                except (ValueError, Exception) as json_err:
                    self.logger.error(f"Modulate.ai returned invalid JSON: {json_err}")
                    raise TranscriptionError(f"Modulate.ai returned invalid JSON response: {json_err}")

                self.logger.debug("\n===== MODULATE API RESPONSE =====")
                self.logger.debug(f"Status: {response.status_code} OK")
                self.logger.debug(f"Response size: {len(response.text)} bytes")

                if 'words' in result:
                    self.logger.debug(f"Words transcribed: {len(result['words'])}")
                if 'text' in result:
                    text_preview = result['text'][:100] + "..." if len(result['text']) > 100 else result['text']
                    self.logger.debug(f"Text preview: {text_preview}")

                # Log emotion detection results
                emotion_data = result.get('emotion_data', [])
                if emotion_data:
                    self.logger.debug(f"\n=== Emotion Detection Results ===")
                    self.logger.debug(f"Detected emotions for {len(emotion_data)} utterances")
                    for i, utterance in enumerate(emotion_data[:3]):
                        emotions = utterance.get('emotions', {})
                        top_emotion = max(emotions, key=emotions.get) if emotions else 'unknown'
                        self.logger.debug(f"  Utterance {i+1}: top_emotion={top_emotion}, scores={emotions}")

                # Log deepfake detection results
                deepfake_data = result.get('deepfake_detection', {})
                if deepfake_data:
                    is_synthetic = deepfake_data.get('is_synthetic', False)
                    confidence = deepfake_data.get('confidence', 0.0)
                    self.logger.info(f"Deepfake detection: is_synthetic={is_synthetic}, confidence={confidence:.2f}")
                    if is_synthetic:
                        self.logger.warning("WARNING: Deepfake/synthetic speech detected in audio!")

                # Log accent detection results
                accent_data = result.get('accent_detection', {})
                if accent_data:
                    self.logger.debug(f"Accent detection: {accent_data}")

                # Log response structure
                self.logger.debug("\n=== Response Structure ===")
                for key in result:
                    self.logger.debug(f"Key: {key}, Type: {type(result[key])}")

                # Process diarized transcript
                has_speaker_info = False
                diarization_location = None

                if 'speakers' in result:
                    has_speaker_info = True
                    diarization_location = "root.speakers"

                if 'words' in result and result['words']:
                    word_fields = set()
                    for entry in result['words']:
                        for key in entry.keys():
                            word_fields.add(key)
                            if 'speaker' in key.lower():
                                has_speaker_info = True
                                if key == 'speaker_id' or diarization_location is None:
                                    diarization_location = f"words.{key}"

                    self.logger.debug(f"Word-level fields (from {len(result['words'])} entries): {word_fields}")

                # Log unique speakers found
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
                    print(f"[Modulate.ai Diarization] {len(unique_speakers)} speaker(s) detected | IDs: {sorted(unique_speakers)}")

                # Format transcript based on diarization data
                if has_speaker_info and diarization_location:
                    if diarization_location.startswith("words."):
                        speaker_field = diarization_location.split('.')[1]
                        transcript = self._format_diarized_transcript(result['words'], speaker_field)
                    elif diarization_location == "root.speakers" and 'speakers' in result:
                        transcript = self._format_diarized_from_speakers(result)
                    else:
                        transcript = result.get("text", "")
                else:
                    transcript = result.get("text", "")
                    if enable_diarization:
                        self.logger.warning(
                            f"No speaker information found in Modulate.ai response. "
                            f"Diarize was enabled. Using plain text fallback."
                        )

            else:
                error_msg = f"Modulate.ai API error: {response.status_code} - {response.text}"
                self.logger.error(error_msg)
                self.logger.debug(f"\n===== MODULATE ERROR =====")
                self.logger.debug(f"Status: {response.status_code}")
                self.logger.debug(f"Response: {response.text}")
                self.logger.debug("==========================\n")

        except TranscriptionError:
            raise
        except Exception as e:
            error_msg = f"Error with Modulate.ai transcription: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.logger.debug("\n===== MODULATE EXCEPTION =====")
            self.logger.debug(f"Error: {str(e)}")
            self.logger.debug(f"Traceback: {traceback.format_exc()}")
            self.logger.debug("==============================\n")

        # Check for possible truncation
        if transcript and audio_details:
            duration_seconds = audio_details.get('duration_seconds', 0)
            expected_chars_min = duration_seconds * 3
            if len(transcript) < expected_chars_min and duration_seconds > 10:
                self.logger.warning(
                    f"Possible transcription truncation detected: got {len(transcript)} chars "
                    f"for {duration_seconds:.1f}s audio (expected at least {expected_chars_min:.0f}). "
                    f"Audio params: frame_rate={audio_details.get('frame_rate')}, "
                    f"channels={audio_details.get('channels')}, sample_width={audio_details.get('sample_width')}"
                )

        return transcript

    def transcribe_with_result(self, segment: AudioSegment) -> TranscriptionResult:
        """Transcribe audio and return structured result with emotion metadata.

        Overrides base class to capture the full Modulate.ai response including
        emotion_data, deepfake_detection, and accent_detection in metadata.

        Args:
            segment: Audio segment to transcribe

        Returns:
            TranscriptionResult with text, metadata including emotion_data
        """
        if not self._check_api_key():
            return TranscriptionResult.failure_result(error="Modulate.ai API key not configured")

        audio_details = self._validate_and_log_audio(segment)

        try:
            # Export audio to BytesIO buffer
            audio_buffer = BytesIO()
            segment.export(audio_buffer, format="wav")
            audio_buffer.seek(0)

            url = MODULATE_TRANSCRIBE_URL
            headers = {
                'Authorization': f'Bearer {self.api_key}'
            }

            file_size_kb = len(audio_buffer.getvalue()) / 1024
            timeout_seconds = max(60, int(file_size_kb / 500) * 60)

            modulate_settings = self._get_modulate_settings()

            data = {
                'model': modulate_settings.get("model", "velma-v1"),
                'language': modulate_settings.get("language", self.language or "en-US"),
            }

            # Enable all features for full result
            enable_diarization = modulate_settings.get("enable_diarization", True)
            if enable_diarization:
                data['diarize'] = 'true'
                num_speakers = modulate_settings.get("num_speakers")
                if num_speakers is not None:
                    data['num_speakers'] = str(num_speakers)
            else:
                data['diarize'] = 'false'

            enable_emotions = modulate_settings.get("enable_emotions", True)
            if enable_emotions:
                data['enable_emotions'] = 'true'

            enable_deepfake_detection = modulate_settings.get("enable_deepfake_detection", False)
            if enable_deepfake_detection:
                data['enable_deepfake_detection'] = 'true'

            enable_pii_redaction = modulate_settings.get("enable_pii_redaction", False)
            if enable_pii_redaction:
                data['enable_pii_redaction'] = 'true'

            files = {
                'file': ('audio.wav', audio_buffer, 'audio/wav')
            }

            try:
                response = self._make_api_call(
                    url,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=timeout_seconds
                )
            except (APIError, RateLimitError, ServiceUnavailableError) as e:
                self.logger.error(f"Modulate.ai API call failed after retries: {e}")
                return TranscriptionResult.failure_result(error=f"Modulate.ai transcription failed: {e}")

            if response.status_code == 200:
                try:
                    result = response.json()
                except (ValueError, Exception) as json_err:
                    return TranscriptionResult.failure_result(
                        error=f"Modulate.ai returned invalid JSON response: {json_err}"
                    )

                # Extract text (with diarization formatting if available)
                transcript = ""
                has_speaker_info = False
                diarization_location = None

                if 'words' in result and result['words']:
                    for entry in result['words']:
                        for key in entry.keys():
                            if 'speaker' in key.lower():
                                has_speaker_info = True
                                if key == 'speaker_id' or diarization_location is None:
                                    diarization_location = f"words.{key}"

                if has_speaker_info and diarization_location and diarization_location.startswith("words."):
                    speaker_field = diarization_location.split('.')[1]
                    transcript = self._format_diarized_transcript(result['words'], speaker_field)
                elif 'speakers' in result:
                    transcript = self._format_diarized_from_speakers(result)
                else:
                    transcript = result.get("text", "")

                # Build metadata with Modulate.ai-specific data
                metadata = {}

                # Emotion data
                emotion_data = result.get('emotion_data', [])
                if emotion_data:
                    metadata['emotion_data'] = emotion_data
                    # Compute summary of dominant emotions
                    emotion_summary = {}
                    for utterance in emotion_data:
                        emotions = utterance.get('emotions', {})
                        if emotions:
                            top_emotion = max(emotions, key=emotions.get)
                            emotion_summary[top_emotion] = emotion_summary.get(top_emotion, 0) + 1
                    metadata['emotion_summary'] = emotion_summary

                # Deepfake detection
                deepfake_data = result.get('deepfake_detection', {})
                if deepfake_data:
                    metadata['deepfake_detection'] = deepfake_data

                # Accent detection
                accent_data = result.get('accent_detection', {})
                if accent_data:
                    metadata['accent_detection'] = accent_data

                # PII redaction info
                pii_data = result.get('pii_redaction', {})
                if pii_data:
                    metadata['pii_redaction'] = pii_data

                # Speaker info
                if 'speakers' in result:
                    metadata['speakers'] = result['speakers']

                # Word-level data
                words = result.get('words', [])

                # Confidence score if available
                confidence = result.get('confidence')

                return TranscriptionResult.success_result(
                    text=transcript,
                    confidence=confidence,
                    duration_seconds=audio_details.get('duration_seconds'),
                    words=words,
                    metadata=metadata
                )
            else:
                return TranscriptionResult.failure_result(
                    error=f"Modulate.ai API error {response.status_code}: {response.text}"
                )

        except Exception as e:
            self.logger.error(f"Modulate.ai transcribe_with_result failed: {e}", exc_info=True)
            return TranscriptionResult.failure_result(error=str(e))

    def _format_diarized_transcript(self, words: List[Dict], speaker_field: str) -> str:
        """Format word-level diarization data into a readable transcript.

        Groups consecutive words by the same speaker into paragraphs
        with speaker labels.

        Args:
            words: List of word entries from the API response
            speaker_field: The field name containing speaker ID

        Returns:
            Formatted transcript with speaker labels
        """
        if not words:
            return ""

        segments = []
        current_speaker = None
        current_words = []

        for word_entry in words:
            speaker = word_entry.get(speaker_field)
            text = word_entry.get('text', word_entry.get('word', ''))

            if not text:
                continue

            if speaker != current_speaker and current_words:
                label = self._clean_speaker_label(current_speaker) if current_speaker else "?"
                segments.append(f"Speaker {label}: {' '.join(current_words)}")
                current_words = []

            current_speaker = speaker
            current_words.append(text.strip())

        # Append last segment
        if current_words:
            label = self._clean_speaker_label(current_speaker) if current_speaker else "?"
            segments.append(f"Speaker {label}: {' '.join(current_words)}")

        return "\n\n".join(segments)

    def _format_diarized_from_speakers(self, result: dict) -> str:
        """Format transcript from a root-level speakers structure.

        Args:
            result: Full API response containing 'speakers' and 'text' keys

        Returns:
            Formatted transcript with speaker labels
        """
        speakers = result.get('speakers', [])
        if not speakers:
            return result.get('text', '')

        segments = []
        for speaker_segment in speakers:
            speaker_id = speaker_segment.get('speaker_id', speaker_segment.get('id', '?'))
            label = self._clean_speaker_label(speaker_id)
            text = speaker_segment.get('text', '')
            if text:
                segments.append(f"Speaker {label}: {text}")

        return "\n\n".join(segments) if segments else result.get('text', '')

    def test_connection(self) -> bool:
        """Test if the Modulate.ai provider is properly configured and accessible.

        Sends a minimal request to validate the API key.

        Returns:
            True if connection test passes, False otherwise
        """
        if not self._check_api_key():
            return False

        try:
            import requests

            # Create a minimal 0.5-second silent audio segment for validation
            silent_segment = AudioSegment.silent(duration=500, frame_rate=16000)
            audio_buffer = BytesIO()
            silent_segment.export(audio_buffer, format="wav")
            audio_buffer.seek(0)

            session = get_http_client_manager().get_requests_session("modulate")
            response = session.post(
                MODULATE_TRANSCRIBE_URL,
                headers={'Authorization': f'Bearer {self.api_key}'},
                files={'file': ('test.wav', audio_buffer, 'audio/wav')},
                data={'model': 'velma-v1'},
                timeout=30
            )

            if response.status_code == 200:
                self.logger.info("Modulate.ai connection test successful")
                return True
            elif response.status_code == 401:
                self.logger.warning("Modulate.ai authentication failed: invalid API key")
                return False
            elif response.status_code == 403:
                self.logger.warning("Modulate.ai access forbidden: check API key permissions")
                return False
            else:
                self.logger.warning(f"Modulate.ai connection test returned status {response.status_code}: {response.text}")
                return False

        except requests.exceptions.Timeout:
            self.logger.warning("Modulate.ai connection test timed out")
            return False
        except requests.exceptions.ConnectionError as e:
            self.logger.warning(f"Modulate.ai connection test failed: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Modulate.ai connection test error: {e}")
            return False
