"""
Modulate.ai Velma-2 Batch STT provider implementation.

Provides speech-to-text transcription via the Velma-2 Batch API with:
- Speaker diarization (1-indexed speaker labels)
- Emotion detection (26 emotion categories per utterance)
- Accent detection (13 accent categories per utterance)
- PII/PHI tagging

API docs: https://www.modulate-developer-apis.com/web/docs.html
"""

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

# API endpoint constants — model is selected by endpoint path
MODULATE_BASE_URL = "https://modulate-developer-apis.com"
MODULATE_BATCH_ENGLISH_URL = f"{MODULATE_BASE_URL}/api/velma-2-stt-batch-english-vfast"
MODULATE_BATCH_MULTILINGUAL_URL = f"{MODULATE_BASE_URL}/api/velma-2-stt-batch"

# Map settings model name to endpoint URL
MODEL_ENDPOINTS = {
    "batch-english-fast": MODULATE_BATCH_ENGLISH_URL,
    "batch-multilingual": MODULATE_BATCH_MULTILINGUAL_URL,
    # Keep "default" as an alias for English fast (cheapest, fastest)
    "default": MODULATE_BATCH_ENGLISH_URL,
}

# Valid emotion values from the API
VALID_EMOTIONS = frozenset([
    "Neutral", "Calm", "Happy", "Amused", "Excited", "Proud", "Affectionate",
    "Interested", "Hopeful", "Frustrated", "Angry", "Contemptuous", "Concerned",
    "Afraid", "Sad", "Ashamed", "Bored", "Tired", "Surprised", "Anxious",
    "Stressed", "Disgusted", "Disappointed", "Confused", "Relieved", "Confident",
])

# Map Velma emotion strings to clinical emotion names used by emotion_processor
EMOTION_TO_CLINICAL = {
    "Anxious": "anxiety",
    "Afraid": "fear",
    "Sad": "sadness",
    "Angry": "anger",
    "Frustrated": "frustration",
    "Confused": "confusion",
    "Happy": "joy",
    "Calm": "calm",
    "Surprised": "surprise",
    "Stressed": "stress",
    "Concerned": "concern",
    "Disgusted": "disgust",
    "Disappointed": "disappointment",
    "Hopeful": "hope",
    "Tired": "fatigue",
    "Bored": "boredom",
    "Ashamed": "shame",
    "Neutral": "neutral",
    "Excited": "excitement",
    "Amused": "amusement",
    "Proud": "pride",
    "Affectionate": "affection",
    "Interested": "interest",
    "Contemptuous": "contempt",
    "Relieved": "relief",
    "Confident": "confidence",
}


class ModulateProvider(BaseSTTProvider):
    """Implementation of the Modulate.ai Velma-2 Batch STT provider.

    Features beyond standard transcription:
    - Emotion detection (26 emotion categories per utterance)
    - Speaker diarization (1-indexed speaker labels)
    - Accent detection (13 accent categories)
    - PII/PHI tagging
    """

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
            language: Language code (used for model selection hint only;
                      the API auto-detects language)
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

        Args:
            url: API endpoint URL
            headers: Request headers including X-API-Key
            files: Files to upload (upload_file field)
            data: Form data with feature flags
            timeout: Request timeout in seconds

        Returns:
            API response

        Raises:
            APIError: On API failures (400-level)
            RateLimitError: On rate limit exceeded (429)
            ServiceUnavailableError: On service unavailable (500-level)
        """
        import requests

        try:
            session = get_http_client_manager().get_requests_session("modulate")
            response = session.post(
                url,
                headers=headers,
                files=files,
                data=data,
                timeout=timeout
            )
            if response.status_code == 429:
                raise RateLimitError(f"Modulate.ai rate limit exceeded: {response.text}")
            elif response.status_code >= 500:
                raise ServiceUnavailableError(f"Modulate.ai service error {response.status_code}: {response.text}")
            elif response.status_code == 403:
                raise APIError(f"Modulate.ai access forbidden (model not enabled): {response.text}")
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

    def _get_endpoint_url(self, settings: dict) -> str:
        """Determine the API endpoint URL based on model setting.

        Args:
            settings: Modulate settings dict

        Returns:
            Full endpoint URL
        """
        model = settings.get("model", "default")
        return MODEL_ENDPOINTS.get(model, MODULATE_BATCH_ENGLISH_URL)

    def _get_modulate_settings(self) -> dict:
        """Get Modulate.ai settings from settings manager."""
        return settings_manager.get("modulate", {})

    def _build_request(self, segment: AudioSegment, settings: dict) -> tuple:
        """Build the API request components.

        Args:
            segment: Audio segment to transcribe
            settings: Modulate settings dict

        Returns:
            Tuple of (url, headers, files, data, timeout)
        """
        # Upsample low sample rate audio for better transcription quality
        if segment.frame_rate < 16000:
            self.logger.info(f"Upsampling audio from {segment.frame_rate} Hz to 16000 Hz for better quality")
            segment = segment.set_frame_rate(16000)

        # Export audio to BytesIO buffer (MP3 for smaller upload size)
        audio_buffer = BytesIO()
        segment.export(audio_buffer, format="mp3")
        audio_buffer.seek(0)

        url = self._get_endpoint_url(settings)
        headers = {
            'X-API-Key': self.api_key
        }

        # Calculate timeout based on file size (min 60s, scale with size)
        file_size_kb = len(audio_buffer.getvalue()) / 1024
        timeout = max(60, int(file_size_kb / 500) * 60)

        self.logger.info(f"Setting Modulate.ai timeout to {timeout} seconds for {file_size_kb:.2f} KB file")

        # Build form data with feature flags
        data = {}

        # Speaker diarization (default: true per API)
        enable_diarization = settings.get("enable_diarization", True)
        data['speaker_diarization'] = 'true' if enable_diarization else 'false'

        # Emotion detection (default: false per API, but we default to true in settings)
        enable_emotions = settings.get("enable_emotions", True)
        data['emotion_signal'] = 'true' if enable_emotions else 'false'

        # Accent detection
        enable_accent = settings.get("enable_accent_detection", False)
        data['accent_signal'] = 'true' if enable_accent else 'false'

        # PII/PHI tagging
        enable_pii = settings.get("enable_pii_tagging", False)
        data['pii_phi_tagging'] = 'true' if enable_pii else 'false'

        self.logger.info(f"Modulate.ai request: url={url}, data={data}")

        files = {
            'upload_file': ('audio.mp3', audio_buffer, 'audio/mpeg')
        }

        return url, headers, files, data, timeout

    def _format_diarized_transcript(self, utterances: List[Dict]) -> str:
        """Format utterances into a diarized transcript with speaker labels.

        Groups consecutive utterances by the same speaker.

        Args:
            utterances: List of utterance dicts from the API response

        Returns:
            Formatted transcript with speaker labels
        """
        if not utterances:
            return ""

        segments = []
        current_speaker = None
        current_texts = []

        for utt in utterances:
            speaker = utt.get("speaker")
            text = utt.get("text", "").strip()
            if not text:
                continue

            if speaker != current_speaker and current_texts:
                label = current_speaker if current_speaker is not None else "?"
                segments.append(f"Speaker {label}: {' '.join(current_texts)}")
                current_texts = []

            current_speaker = speaker
            current_texts.append(text)

        if current_texts:
            label = current_speaker if current_speaker is not None else "?"
            segments.append(f"Speaker {label}: {' '.join(current_texts)}")

        return "\n\n".join(segments)

    def _build_emotion_data(self, utterances: List[Dict]) -> dict:
        """Transform utterances into the emotion_data format expected by emotion_processor.

        The emotion_processor expects:
        {
            "segments": [{"text": ..., "emotions": {"anxiety": 0.72, ...}, ...}],
            "overall": {"dominant_emotion": ..., "average_emotions": {...}}
        }

        The real API returns a single emotion string per utterance, so we
        synthesize a score dict (1.0 for detected emotion, 0.0 for others).

        Args:
            utterances: List of utterance dicts from the API response

        Returns:
            Dict in the format expected by emotion_processor
        """
        segments = []
        emotion_counts = {}

        for utt in utterances:
            emotion_str = utt.get("emotion")
            if not emotion_str:
                continue

            # Map to clinical emotion name
            clinical_name = EMOTION_TO_CLINICAL.get(emotion_str, emotion_str.lower())

            segment = {
                "text": utt.get("text", ""),
                "emotions": {clinical_name: 1.0},  # deprecated, backward compat
                "start_time": utt.get("start_ms", 0) / 1000.0,
                "end_time": (utt.get("start_ms", 0) + utt.get("duration_ms", 0)) / 1000.0,
                "speaker": f"speaker_{utt.get('speaker', 0)}",
                "emotion_label": clinical_name,  # PRIMARY: clinical mapped name
                "emotion_raw": emotion_str,  # original API label
            }
            segments.append(segment)

            # Count emotions for overall summary
            emotion_counts[clinical_name] = emotion_counts.get(clinical_name, 0) + 1

        if not segments:
            return {}

        # Build overall summary
        total = sum(emotion_counts.values())
        dominant = max(emotion_counts, key=emotion_counts.get) if emotion_counts else "neutral"

        return {
            "version": 2,
            "segments": segments,
            "overall": {
                "dominant_emotion": dominant,
                "emotion_distribution": dict(emotion_counts),
                "total_segments": total,
            }
        }

    def transcribe(self, segment: AudioSegment, **kwargs) -> str:
        """Transcribe audio using Modulate.ai Velma-2 Batch API.

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
            settings = self._get_modulate_settings()
            url, headers, files, data, timeout = self._build_request(segment, settings)

            try:
                response = self._make_api_call(
                    url, headers=headers, files=files, data=data, timeout=timeout
                )
            except (APIError, RateLimitError, ServiceUnavailableError) as e:
                self.logger.error(f"Modulate.ai API call failed after retries: {e}")
                raise TranscriptionError(f"Modulate.ai transcription failed: {e}")

            if response.status_code == 200:
                try:
                    result = response.json()
                except (ValueError, Exception) as json_err:
                    self.logger.error(f"Modulate.ai returned invalid JSON: {json_err}")
                    raise TranscriptionError(f"Modulate.ai returned invalid JSON: {json_err}")

                self.logger.info(f"Modulate.ai response keys: {list(result.keys())}")
                self.logger.info(f"Modulate.ai text length: {len(result.get('text', ''))}, "
                                f"duration_ms: {result.get('duration_ms')}, "
                                f"utterances count: {len(result.get('utterances', []))}")

                utterances = result.get("utterances", [])

                # Log speaker/emotion info
                if utterances:
                    speakers = set(u.get("speaker") for u in utterances if u.get("speaker") is not None)
                    emotions = [u.get("emotion") for u in utterances if u.get("emotion")]
                    self.logger.info(
                        f"Modulate.ai result: {len(utterances)} utterances, "
                        f"{len(speakers)} unique speakers: {sorted(speakers)}, "
                        f"emotions: {set(emotions)}"
                    )
                    # Log first few utterances for diarization debugging
                    for i, u in enumerate(utterances[:5]):
                        self.logger.info(
                            f"  utterance[{i}]: speaker={u.get('speaker')}, "
                            f"emotion={u.get('emotion')}, text={u.get('text', '')[:60]}"
                        )

                # Format transcript with diarization labels
                enable_diarization = settings.get("enable_diarization", True)
                if enable_diarization and utterances:
                    transcript = self._format_diarized_transcript(utterances)
                else:
                    transcript = result.get("text", "")

            else:
                self.logger.error(f"Modulate.ai API error: {response.status_code} - {response.text}")

        except TranscriptionError:
            raise
        except Exception as e:
            self.logger.error(f"Error with Modulate.ai transcription: {e}", exc_info=True)

        # Check for possible truncation
        if transcript and audio_details:
            duration_seconds = audio_details.get('duration_seconds', 0)
            expected_chars_min = duration_seconds * 3
            if len(transcript) < expected_chars_min and duration_seconds > 10:
                self.logger.warning(
                    f"Possible truncation: {len(transcript)} chars for {duration_seconds:.1f}s audio"
                )

        return transcript

    def transcribe_with_result(self, segment: AudioSegment) -> TranscriptionResult:
        """Transcribe audio and return structured result with emotion metadata.

        Returns TranscriptionResult with emotion_data transformed into the
        format expected by the emotion_processor.

        Args:
            segment: Audio segment to transcribe

        Returns:
            TranscriptionResult with text and metadata
        """
        if not self._check_api_key():
            return TranscriptionResult.failure_result(error="Modulate.ai API key not configured")

        audio_details = self._validate_and_log_audio(segment)

        try:
            settings = self._get_modulate_settings()
            url, headers, files, data, timeout = self._build_request(segment, settings)

            try:
                response = self._make_api_call(
                    url, headers=headers, files=files, data=data, timeout=timeout
                )
            except (APIError, RateLimitError, ServiceUnavailableError) as e:
                self.logger.error(f"Modulate.ai API call failed after retries: {e}")
                return TranscriptionResult.failure_result(error=f"Modulate.ai transcription failed: {e}")

            if response.status_code == 200:
                try:
                    result = response.json()
                except (ValueError, Exception) as json_err:
                    return TranscriptionResult.failure_result(
                        error=f"Modulate.ai returned invalid JSON: {json_err}"
                    )

                utterances = result.get("utterances", [])

                # Format transcript with diarization labels
                enable_diarization = settings.get("enable_diarization", True)
                if enable_diarization and utterances:
                    transcript = self._format_diarized_transcript(utterances)
                else:
                    transcript = result.get("text", "")

                # Build metadata
                metadata = {}

                # Transform emotions into format for emotion_processor
                emotion_data = self._build_emotion_data(utterances)
                if emotion_data:
                    metadata['emotion_data'] = emotion_data

                # Raw utterances for detailed inspection
                metadata['utterances'] = utterances

                # Accent summary
                accents = [u.get("accent") for u in utterances if u.get("accent")]
                if accents:
                    metadata['accent_detection'] = {
                        "accents": list(set(accents)),
                        "per_utterance": accents,
                    }

                # Duration from API
                duration_ms = result.get("duration_ms")
                duration_seconds = duration_ms / 1000.0 if duration_ms else audio_details.get('duration_seconds')

                return TranscriptionResult.success_result(
                    text=transcript,
                    confidence=None,  # API doesn't return confidence scores
                    duration_seconds=duration_seconds,
                    words=None,  # API returns utterances, not words
                    metadata=metadata
                )
            else:
                return TranscriptionResult.failure_result(
                    error=f"Modulate.ai API error {response.status_code}: {response.text}"
                )

        except Exception as e:
            self.logger.error(f"Modulate.ai transcribe_with_result failed: {e}", exc_info=True)
            return TranscriptionResult.failure_result(error=str(e))

    def _validate_and_log_audio(self, segment: AudioSegment) -> dict:
        """Validate audio segment and log its details."""
        details = {
            'duration_ms': len(segment),
            'duration_seconds': len(segment) / 1000,
            'frame_rate': segment.frame_rate,
            'channels': segment.channels,
            'sample_width': segment.sample_width,
            'frame_count': segment.frame_count()
        }

        self.logger.info(
            f"Audio segment details: duration_ms={details['duration_ms']}, "
            f"frame_rate={details['frame_rate']}, channels={details['channels']}, "
            f"sample_width={details['sample_width']}, frame_count={details['frame_count']}"
        )

        if details['frame_rate'] not in [8000, 16000, 22050, 44100, 48000]:
            self.logger.warning(f"Unusual sample rate: {details['frame_rate']}")

        return details

    def test_connection(self) -> bool:
        """Test if the Modulate.ai provider is properly configured and accessible.

        Sends a minimal silent audio to validate the API key and endpoint.

        Returns:
            True if connection test passes, False otherwise
        """
        if not self._check_api_key():
            return False

        try:
            import requests

            # Create a minimal 0.5-second silent audio segment
            silent_segment = AudioSegment.silent(duration=500, frame_rate=16000)
            audio_buffer = BytesIO()
            silent_segment.export(audio_buffer, format="wav")
            audio_buffer.seek(0)

            session = get_http_client_manager().get_requests_session("modulate")
            response = session.post(
                MODULATE_BATCH_ENGLISH_URL,
                headers={'X-API-Key': self.api_key},
                files={'upload_file': ('test.wav', audio_buffer, 'audio/wav')},
                timeout=30
            )

            if response.status_code == 200:
                self.logger.info("Modulate.ai connection test successful")
                return True
            elif response.status_code == 401:
                self.logger.warning("Modulate.ai authentication failed: invalid API key")
                return False
            elif response.status_code == 403:
                self.logger.warning("Modulate.ai access forbidden: model not enabled for your organization")
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
