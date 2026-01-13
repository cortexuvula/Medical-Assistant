"""Logging utilities for AI module.

Provides consolidated debug logging for API calls with sensitive data sanitization.
"""

import logging
from utils.validation import sanitize_for_logging


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
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        # Sanitize all content before logging
        safe_system = sanitize_for_logging(system_message, max_length=100)
        safe_prompt = sanitize_for_logging(prompt, max_length=100)

        logging.debug(f"\n===== {provider.upper()} API CALL =====")
        logging.debug(f"Model: {model}, Temperature: {temperature}")
        logging.debug(f"System: {safe_system}")
        logging.debug(f"Prompt: {safe_prompt}")
        logging.debug("="*40)
