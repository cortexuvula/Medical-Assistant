"""
GROQ STT provider implementation.
"""

import os
import time
import traceback
from io import BytesIO
from typing import Optional
from pydub import AudioSegment

from .base import BaseSTTProvider
from utils.exceptions import TranscriptionError, APIError, RateLimitError, ServiceUnavailableError
from utils.resilience import resilient_api_call
from utils.http_client_manager import get_http_client_manager
from core.config import get_config
from utils.security_decorators import secure_api_call
from utils.security import get_security_manager
from settings.settings import SETTINGS

# API endpoint constants
GROQ_API_BASE_URL = "https://api.groq.com/openai/v1"


class GroqProvider(BaseSTTProvider):
    """Implementation of the GROQ STT provider."""

    @property
    def provider_name(self) -> str:
        """Return the provider identifier."""
        return "groq"

    @property
    def supports_diarization(self) -> bool:
        """Groq does not support speaker diarization."""
        return False

    def __init__(self, api_key: str = "", language: str = "en-US"):
        """Initialize the GROQ provider.

        Args:
            api_key: GROQ API key
            language: Language code for speech recognition
        """
        super().__init__(api_key, language)

    @secure_api_call("groq")
    @resilient_api_call(
        max_retries=3,
        initial_delay=1.0,
        backoff_factor=2.0,
        failure_threshold=5,
        recovery_timeout=60
    )
    def _make_api_call(self, client, audio_file, language: str, model: str, prompt: str, timeout: int):
        """Make the actual API call to GROQ with retry logic.

        Args:
            client: OpenAI client configured for GROQ
            audio_file: Open file handle for audio
            language: Language code
            model: Whisper model to use
            prompt: Optional context/spelling hints
            timeout: Request timeout

        Returns:
            API response

        Raises:
            APIError: On API failures
            RateLimitError: On rate limit exceeded
            ServiceUnavailableError: On service unavailable
        """
        try:
            # Build request kwargs
            request_kwargs = {
                "file": audio_file,
                "model": model,
                "language": language,
                "timeout": timeout
            }
            # Add prompt if provided (helps with context and spelling)
            if prompt:
                request_kwargs["prompt"] = prompt

            response = client.audio.transcriptions.create(**request_kwargs)
            return response
        except Exception as e:
            error_msg = str(e).lower()
            if "rate limit" in error_msg or "429" in error_msg:
                raise RateLimitError(f"GROQ rate limit exceeded: {e}")
            elif "timeout" in error_msg:
                raise ServiceUnavailableError(f"GROQ request timeout: {e}")
            elif "503" in error_msg or "unavailable" in error_msg:
                raise ServiceUnavailableError(f"GROQ service unavailable: {e}")
            else:
                raise APIError(f"GROQ API error: {e}")

    def transcribe(self, segment: AudioSegment) -> str:
        """Transcribe audio using GROQ API.

        Uses BytesIO buffer instead of temp files for 2-5 seconds faster processing.

        Args:
            segment: Audio segment to transcribe

        Returns:
            Transcription text
        """
        if not self._check_api_key():
            raise TranscriptionError("GROQ API key not configured")

        transcript = ""

        try:
            # Export audio to BytesIO buffer instead of temp file (saves 2-5 seconds)
            audio_buffer = BytesIO()
            segment.export(audio_buffer, format="wav")
            audio_buffer.seek(0)
            audio_buffer.name = "audio.wav"  # OpenAI API needs a filename

            # Get buffer size and adjust timeout accordingly
            file_size_kb = len(audio_buffer.getvalue()) / 1024

            # Add a minute of timeout for each 500KB of audio, with a minimum of base timeout
            config = get_config()
            base_timeout = config.api.timeout
            timeout_seconds = max(base_timeout, int(file_size_kb / 500) * 60)
            self.logger.info(f"Setting GROQ timeout to {timeout_seconds} seconds for {file_size_kb:.2f} KB audio")

            # Using OpenAI client since GROQ uses a compatible API
            from openai import OpenAI

            # Get API key from secure storage if needed
            security_manager = get_security_manager()
            api_key = self.api_key or security_manager.get_api_key("groq")
            if not api_key:
                raise TranscriptionError("GROQ API key not found")

            # Use pooled HTTP client for connection reuse (saves 50-200ms per call)
            http_client = get_http_client_manager().get_httpx_client("groq", timeout_seconds)
            client = OpenAI(api_key=api_key, base_url=GROQ_API_BASE_URL, http_client=http_client)

            # Get Groq settings
            groq_settings = SETTINGS.get("groq", {})
            model = groq_settings.get("model", "whisper-large-v3-turbo")
            # Use language from settings if set, otherwise use instance language
            language = groq_settings.get("language", "") or self.language.split('-')[0]
            prompt = groq_settings.get("prompt", "")

            # Log API call details
            self.logger.debug(f"GROQ API call: model={model}, language={language}, file_size={file_size_kb:.2f}KB")

            # Make API call with retry logic using BytesIO buffer
            try:
                response = self._make_api_call(
                    client,
                    audio_buffer,
                    language,
                    model,
                    prompt,
                    timeout_seconds
                )
            except (APIError, RateLimitError, ServiceUnavailableError) as e:
                self.logger.error(f"GROQ API call failed after retries: {e}")
                raise TranscriptionError(f"GROQ transcription failed: {e}")

            # Process response
            if hasattr(response, 'text'):
                transcript = response.text
                self.logger.info(f"GROQ transcription successful: {len(transcript)} characters")
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

        # Return whatever transcript we got, empty string if we failed
        return transcript
