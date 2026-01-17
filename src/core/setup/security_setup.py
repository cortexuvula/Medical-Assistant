"""
Security setup for Medical Assistant.

Handles initialization of API keys and security managers.
"""

from typing import TYPE_CHECKING

from .base import BaseSetup

if TYPE_CHECKING:
    from core.app import MedicalDictationApp


class SecuritySetup(BaseSetup):
    """Setup component for security and API keys.

    Initializes:
    - Security manager
    - API key loading and validation
    """

    def initialize(self) -> None:
        """Initialize security components."""
        self._log_start("Security setup")

        # Initialize security manager and load API keys
        from utils.security import get_security_manager
        self.app.security_manager = get_security_manager()

        # Load API keys into application
        self._load_api_keys()

        self._log_complete("Security setup")

    def _load_api_keys(self) -> None:
        """Load API keys from secure storage."""
        try:
            # Get API keys from security manager
            self.app.openai_api_key = self.app.security_manager.get_api_key("openai") or ""
            self.app.groq_api_key = self.app.security_manager.get_api_key("groq") or ""
            self.app.deepgram_api_key = self.app.security_manager.get_api_key("deepgram") or ""
            self.app.elevenlabs_api_key = self.app.security_manager.get_api_key("elevenlabs") or ""
            self.app.anthropic_api_key = self.app.security_manager.get_api_key("anthropic") or ""
            self.app.gemini_api_key = self.app.security_manager.get_api_key("gemini") or ""

            # Log which keys are configured (without revealing values)
            configured_keys = []
            for provider in ['openai', 'groq', 'deepgram', 'elevenlabs', 'anthropic', 'gemini']:
                if self.app.security_manager.get_api_key(provider):
                    configured_keys.append(provider)

            if configured_keys:
                self.logger.info(f"API keys configured for: {', '.join(configured_keys)}")
            else:
                self.logger.warning("No API keys configured")

        except Exception as e:
            self._log_error("API key loading", e)
            # Set empty keys on error
            self.app.openai_api_key = ""
            self.app.groq_api_key = ""
            self.app.deepgram_api_key = ""
            self.app.elevenlabs_api_key = ""
            self.app.anthropic_api_key = ""
            self.app.gemini_api_key = ""

    def cleanup(self) -> None:
        """Clean up security resources."""
        # Security manager handles its own cleanup
        pass
