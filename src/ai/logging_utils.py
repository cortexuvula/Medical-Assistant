"""Logging utilities for AI module.

Provides consolidated debug logging for API calls with sensitive data sanitization.
"""

from utils.structured_logging import get_logger
from utils.validation import sanitize_for_logging

logger = get_logger(__name__)


def log_api_call_debug(provider: str, model: str, temperature: float, system_message: str, prompt: str) -> None:
    """Consolidated debug logging for API calls with sensitive data sanitization.

    All logged content is sanitized to prevent accidental exposure of:
    - API keys
    - Authorization tokens
    - PII (emails, phone numbers, SSNs)

    Args:
        provider: Name of the AI provider (e.g., "OpenAI", "Anthropic")
        model: Model name being used
        temperature: Temperature setting for the API call
        system_message: System message content
        prompt: User prompt content
    """
    if logger.isEnabledFor(10):  # 10 = DEBUG level
        # Sanitize all content before logging
        safe_system = sanitize_for_logging(system_message, max_length=100)
        safe_prompt = sanitize_for_logging(prompt, max_length=100)

        logger.debug(f"\n===== {provider.upper()} API CALL =====")
        logger.debug(f"Model: {model}, Temperature: {temperature}")
        logger.debug(f"System: {safe_system}")
        logger.debug(f"Prompt: {safe_prompt}")
        logger.debug("="*40)
