"""
Security setup for Medical Assistant.

Handles initialization of API keys and security managers.
"""

from typing import TYPE_CHECKING

from .base import BaseSetup
from utils.constants import (
    PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_GEMINI,
    PROVIDER_GROQ, PROVIDER_CEREBRAS,
    STT_DEEPGRAM, STT_ELEVENLABS, STT_MODULATE,
)

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
            self.app.openai_api_key = self.app.security_manager.get_api_key(PROVIDER_OPENAI) or ""
            self.app.groq_api_key = self.app.security_manager.get_api_key(PROVIDER_GROQ) or ""
            self.app.deepgram_api_key = self.app.security_manager.get_api_key(STT_DEEPGRAM) or ""
            self.app.elevenlabs_api_key = self.app.security_manager.get_api_key(STT_ELEVENLABS) or ""
            self.app.anthropic_api_key = self.app.security_manager.get_api_key(PROVIDER_ANTHROPIC) or ""
            self.app.gemini_api_key = self.app.security_manager.get_api_key(PROVIDER_GEMINI) or ""
            self.app.modulate_api_key = self.app.security_manager.get_api_key(STT_MODULATE) or ""
            self.app.cerebras_api_key = self.app.security_manager.get_api_key(PROVIDER_CEREBRAS) or ""

            # Log which keys are configured (without revealing values)
            configured_keys = []
            for provider in [PROVIDER_OPENAI, PROVIDER_GROQ, STT_DEEPGRAM, STT_ELEVENLABS, PROVIDER_ANTHROPIC, PROVIDER_GEMINI, STT_MODULATE, PROVIDER_CEREBRAS]:
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
            self.app.modulate_api_key = ""
            self.app.cerebras_api_key = ""

    def cleanup(self) -> None:
        """Clean up security resources."""
        # Security manager handles its own cleanup
        pass
