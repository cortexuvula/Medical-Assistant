"""
STT Provider Failover Manager

Provides automatic failover between multiple STT providers when the primary
provider fails. This increases reliability for transcription operations.
"""

import logging
from typing import List, Optional, Dict, Any
from pydub import AudioSegment

from stt_providers.base import BaseSTTProvider, TranscriptionResult


logger = logging.getLogger(__name__)


class STTFailoverManager:
    """Manages automatic failover between multiple STT providers.

    This class maintains a list of STT providers and attempts transcription
    with each provider in order until one succeeds. It tracks which providers
    are currently healthy and can skip unhealthy providers temporarily.

    Example:
        # Create providers
        primary = DeepgramProvider(api_key="...")
        backup = GroqProvider(api_key="...")
        fallback = WhisperProvider()

        # Create failover manager
        manager = STTFailoverManager([primary, backup, fallback])

        # Transcribe with automatic failover
        result = manager.transcribe(audio_segment)
    """

    def __init__(
        self,
        providers: List[BaseSTTProvider],
        max_failures_before_skip: int = 3,
        skip_duration_seconds: float = 300.0
    ):
        """Initialize the failover manager.

        Args:
            providers: Ordered list of STT providers (primary first)
            max_failures_before_skip: Number of consecutive failures before
                temporarily skipping a provider
            skip_duration_seconds: How long to skip a failing provider (seconds)
        """
        self.providers = providers
        self.max_failures_before_skip = max_failures_before_skip
        self.skip_duration_seconds = skip_duration_seconds

        # Track provider health
        self._failure_counts: Dict[str, int] = {}
        self._skip_until: Dict[str, float] = {}
        self._last_successful_provider: Optional[str] = None

    def transcribe(self, segment: AudioSegment) -> str:
        """Transcribe audio with automatic failover.

        Attempts transcription with each configured provider in order,
        failing over to the next provider if one fails.

        Args:
            segment: Audio segment to transcribe

        Returns:
            Transcribed text, or empty string if all providers fail
        """
        result = self.transcribe_with_result(segment)
        return result.text if result.success else ""

    def transcribe_with_result(self, segment: AudioSegment) -> TranscriptionResult:
        """Transcribe audio with automatic failover, returning structured result.

        Args:
            segment: Audio segment to transcribe

        Returns:
            TranscriptionResult with transcription or error details
        """
        import time
        current_time = time.time()
        errors = []
        providers_tried = []

        for provider in self.providers:
            provider_name = provider.provider_name

            # Check if provider is temporarily skipped
            skip_until = self._skip_until.get(provider_name, 0)
            if current_time < skip_until:
                logger.debug(
                    f"Skipping {provider_name} (temporarily disabled until "
                    f"{skip_until - current_time:.0f}s from now)"
                )
                continue

            # Check if provider is configured
            if not provider.is_configured:
                logger.debug(f"Skipping {provider_name} (not configured)")
                continue

            providers_tried.append(provider_name)
            logger.info(f"Attempting transcription with {provider_name}")

            try:
                # Try transcription
                if hasattr(provider, 'transcribe_with_result'):
                    result = provider.transcribe_with_result(segment)
                    if result.success and result.text:
                        self._record_success(provider_name)
                        result.metadata['provider'] = provider_name
                        result.metadata['failover_attempts'] = len(providers_tried)
                        return result
                    else:
                        error_msg = result.error or "Empty transcription"
                        errors.append(f"{provider_name}: {error_msg}")
                        self._record_failure(provider_name)
                else:
                    # Fallback to basic transcribe method
                    text = provider.transcribe(segment)
                    if text:
                        self._record_success(provider_name)
                        return TranscriptionResult.success_result(
                            text=text,
                            duration_seconds=len(segment) / 1000.0,
                            metadata={
                                'provider': provider_name,
                                'failover_attempts': len(providers_tried)
                            }
                        )
                    else:
                        errors.append(f"{provider_name}: Empty transcription")
                        self._record_failure(provider_name)

            except Exception as e:
                error_msg = f"{provider_name}: {str(e)}"
                logger.warning(f"Transcription failed with {provider_name}: {e}")
                errors.append(error_msg)
                self._record_failure(provider_name)

        # All providers failed
        all_errors = "; ".join(errors) if errors else "No configured providers available"
        logger.error(f"All STT providers failed: {all_errors}")

        return TranscriptionResult.failure_result(
            error=f"All providers failed: {all_errors}",
            metadata={
                'providers_tried': providers_tried,
                'errors': errors
            }
        )

    def _record_success(self, provider_name: str):
        """Record a successful transcription for a provider."""
        self._failure_counts[provider_name] = 0
        self._skip_until[provider_name] = 0
        self._last_successful_provider = provider_name
        logger.debug(f"{provider_name} succeeded, reset failure count")

    def _record_failure(self, provider_name: str):
        """Record a failed transcription for a provider."""
        import time

        count = self._failure_counts.get(provider_name, 0) + 1
        self._failure_counts[provider_name] = count

        if count >= self.max_failures_before_skip:
            skip_until = time.time() + self.skip_duration_seconds
            self._skip_until[provider_name] = skip_until
            logger.warning(
                f"{provider_name} has failed {count} times, "
                f"temporarily disabled for {self.skip_duration_seconds:.0f}s"
            )

    def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """Get the current status of all providers.

        Returns:
            Dictionary mapping provider names to their status info.
        """
        import time
        current_time = time.time()
        status = {}

        for provider in self.providers:
            name = provider.provider_name
            skip_until = self._skip_until.get(name, 0)

            status[name] = {
                'configured': provider.is_configured,
                'failure_count': self._failure_counts.get(name, 0),
                'temporarily_disabled': current_time < skip_until,
                'disabled_until': skip_until if current_time < skip_until else None,
                'last_successful': name == self._last_successful_provider
            }

        return status

    def reset_provider(self, provider_name: str):
        """Reset failure tracking for a specific provider.

        Use this to re-enable a provider after fixing a configuration issue.

        Args:
            provider_name: Name of the provider to reset
        """
        self._failure_counts[provider_name] = 0
        self._skip_until[provider_name] = 0
        logger.info(f"Reset failure tracking for {provider_name}")

    def reset_all_providers(self):
        """Reset failure tracking for all providers."""
        self._failure_counts.clear()
        self._skip_until.clear()
        logger.info("Reset failure tracking for all STT providers")

    def get_available_providers(self) -> List[str]:
        """Get list of currently available (not skipped) provider names.

        Returns:
            List of provider names that are configured and not temporarily disabled.
        """
        import time
        current_time = time.time()
        available = []

        for provider in self.providers:
            name = provider.provider_name
            if provider.is_configured:
                skip_until = self._skip_until.get(name, 0)
                if current_time >= skip_until:
                    available.append(name)

        return available

    def test_all_providers(self) -> Dict[str, bool]:
        """Test connectivity for all providers.

        Returns:
            Dictionary mapping provider names to their connection test results.
        """
        results = {}
        for provider in self.providers:
            try:
                results[provider.provider_name] = provider.test_connection()
            except Exception as e:
                logger.warning(f"Connection test failed for {provider.provider_name}: {e}")
                results[provider.provider_name] = False
        return results


def create_failover_manager_from_settings() -> STTFailoverManager:
    """Create a failover manager using settings from the application.

    Returns:
        Configured STTFailoverManager with providers based on settings.
    """
    from settings.settings import SETTINGS

    providers = []

    # Try to create Deepgram provider
    try:
        deepgram_key = SETTINGS.get("deepgram", {}).get("api_key", "")
        if deepgram_key:
            from stt_providers.deepgram import DeepgramProvider
            providers.append(DeepgramProvider(api_key=deepgram_key))
            logger.info("Added Deepgram to failover chain")
    except Exception as e:
        logger.warning(f"Could not create Deepgram provider: {e}")

    # Try to create Groq provider
    try:
        groq_key = SETTINGS.get("groq", {}).get("api_key", "")
        if groq_key:
            from stt_providers.groq import GroqProvider
            providers.append(GroqProvider(api_key=groq_key))
            logger.info("Added Groq to failover chain")
    except Exception as e:
        logger.warning(f"Could not create Groq provider: {e}")

    # Try to create ElevenLabs STT provider
    try:
        elevenlabs_key = SETTINGS.get("elevenlabs", {}).get("api_key", "")
        if elevenlabs_key:
            from stt_providers.elevenlabs import ElevenLabsSTTProvider
            providers.append(ElevenLabsSTTProvider(api_key=elevenlabs_key))
            logger.info("Added ElevenLabs to failover chain")
    except Exception as e:
        logger.warning(f"Could not create ElevenLabs provider: {e}")

    # Always add Whisper as fallback (local, no API key needed)
    try:
        from stt_providers.whisper import WhisperProvider
        providers.append(WhisperProvider())
        logger.info("Added Whisper (local) as final fallback")
    except Exception as e:
        logger.warning(f"Could not create Whisper provider: {e}")

    if not providers:
        logger.error("No STT providers could be initialized!")

    return STTFailoverManager(providers)
