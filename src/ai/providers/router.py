"""AI Provider Router Module.

Routes API calls to the appropriate provider based on settings.
Supports OpenAI, Anthropic, Ollama, and Gemini providers.

Error Handling:
    - Returns AIResult for all operations (never raises exceptions to callers)
    - AIResult.is_success: True if API call succeeded, False otherwise
    - AIResult.text: The response text on success
    - AIResult.error: Error message on failure
    - str(result) provides backward compatibility with code expecting strings
    - Provider-specific errors (rate limits, auth failures) captured in AIResult

Logging:
    - Uses structured logging via get_logger(__name__)
    - Logs provider selection, model, and response timing
    - API errors logged with full context before wrapping in AIResult

Usage:
    result = call_ai(model, system_msg, prompt, temperature)
    if result.is_success:
        response_text = result.text
    else:
        handle_error(result.error)
"""

import logging
from typing import Callable

from utils.structured_logging import get_logger, timed

logger = get_logger(__name__)

from ai.providers.base import get_model_key_for_task
from ai.providers.openai_provider import call_openai, call_openai_streaming
from ai.providers.anthropic_provider import call_anthropic, call_anthropic_streaming
from ai.providers.ollama_provider import call_ollama
from ai.providers.gemini_provider import call_gemini
from ai.providers.groq_provider import call_groq, call_groq_streaming
from ai.providers.cerebras_provider import call_cerebras, call_cerebras_streaming

from utils.constants import (
    PROVIDER_OPENAI, PROVIDER_ANTHROPIC,
    PROVIDER_OLLAMA, PROVIDER_GEMINI,
    PROVIDER_GROQ, PROVIDER_CEREBRAS
)
from utils.exceptions import AIResult

# Provider fallback chain — tried in order when primary fails.
# Ollama (local) and Gemini excluded: different availability characteristics.
FALLBACK_CHAIN = [PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_GROQ, PROVIDER_CEREBRAS]


def _call_provider(provider: str, model: str, system_message: str, prompt: str,
                   temperature: float, current_settings: dict, model_key: str,
                   provider_explicitly_set: bool) -> AIResult:
    """Dispatch a single AI call to a specific provider.

    This is a pure extraction of the provider dispatch logic from call_ai(),
    enabling the fallback chain to retry with different providers.
    """
    if provider == PROVIDER_OLLAMA:
        return call_ollama(system_message, prompt, temperature)
    elif provider == PROVIDER_ANTHROPIC:
        if provider_explicitly_set and model:
            actual_model = model
        else:
            actual_model = current_settings.get(model_key, {}).get("anthropic_model", "claude-sonnet-4-20250514")
        return call_anthropic(actual_model, system_message, prompt, temperature)
    elif provider == PROVIDER_GEMINI:
        if provider_explicitly_set and model:
            actual_model = model
        else:
            actual_model = current_settings.get(model_key, {}).get("gemini_model", "gemini-1.5-flash")
        return call_gemini(actual_model, system_message, prompt, temperature)
    elif provider == PROVIDER_GROQ:
        if provider_explicitly_set and model:
            actual_model = model
        else:
            actual_model = current_settings.get(model_key, {}).get("groq_model", "llama-3.3-70b-versatile")
        return call_groq(actual_model, system_message, prompt, temperature)
    elif provider == PROVIDER_CEREBRAS:
        if provider_explicitly_set and model:
            actual_model = model
        else:
            actual_model = current_settings.get(model_key, {}).get("cerebras_model", "llama-3.3-70b")
        return call_cerebras(actual_model, system_message, prompt, temperature)
    else:  # OpenAI is the default
        if provider_explicitly_set and model:
            actual_model = model
        else:
            actual_model = current_settings.get(model_key, {}).get("model", model)
        return call_openai(actual_model, system_message, prompt, temperature)


def _log_usage(result: AIResult, provider: str, model: str) -> AIResult:
    """Log token usage from an AI result if present.

    Args:
        result: The AIResult from a provider call
        provider: Provider name (for log context)
        model: Model name (for log context)

    Returns:
        The same AIResult, unchanged
    """
    if result.is_success and result.usage:
        prompt_tokens = result.usage.get("prompt_tokens", 0)
        completion_tokens = result.usage.get("completion_tokens", 0)
        total_tokens = result.usage.get("total_tokens", 0)
        logger.info(
            f"Token usage [{provider}/{model}]: "
            f"prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}"
        )
    return result


@timed("ai_call_streaming", level=logging.INFO)
def call_ai_streaming(
    model: str,
    system_message: str,
    prompt: str,
    temperature: float,
    on_chunk: Callable[[str], None]
) -> AIResult:
    """Route streaming API calls to the appropriate provider.

    Args:
        model: Model to use
        system_message: System message
        prompt: User prompt
        temperature: Temperature setting
        on_chunk: Callback for each text chunk

    Returns:
        AIResult: Type-safe result wrapper. Use result.text for content,
                  result.is_success to check status. str(result) returns
                  text or error string for backward compatibility.
    """
    from settings.settings_manager import settings_manager
    current_settings = settings_manager.get_all()

    VALID_PROVIDERS = {PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_GROQ, PROVIDER_CEREBRAS}
    provider = current_settings.get("ai_provider", PROVIDER_OPENAI)

    model_key = get_model_key_for_task(system_message, prompt)

    if provider == PROVIDER_ANTHROPIC:
        actual_model = current_settings.get(model_key, {}).get("anthropic_model", "claude-sonnet-4-20250514")
        return call_anthropic_streaming(actual_model, system_message, prompt, temperature, on_chunk)
    elif provider == PROVIDER_GROQ:
        actual_model = current_settings.get(model_key, {}).get("groq_model", "llama-3.3-70b-versatile")
        return call_groq_streaming(actual_model, system_message, prompt, temperature, on_chunk)
    elif provider == PROVIDER_CEREBRAS:
        actual_model = current_settings.get(model_key, {}).get("cerebras_model", "llama-3.3-70b")
        return call_cerebras_streaming(actual_model, system_message, prompt, temperature, on_chunk)
    elif provider == PROVIDER_OPENAI:
        actual_model = current_settings.get(model_key, {}).get("model", model)
        return call_openai_streaming(actual_model, system_message, prompt, temperature, on_chunk)
    else:
        # Fall back to non-streaming for unsupported providers
        logger.info(f"Streaming not supported for {provider}, using non-streaming")
        result = call_ai(model, system_message, prompt, temperature)
        on_chunk(str(result))  # Use str() for backward compatibility with on_chunk
        return result


@timed("ai_call", level=logging.INFO)
def call_ai(model: str, system_message: str, prompt: str, temperature: float,
            provider: str = None) -> AIResult:
    """Route API calls to the appropriate provider based on the selected AI provider in settings.

    Args:
        model: Model to use (may be overridden by provider-specific settings)
        system_message: System message to guide the AI's response
        prompt: Content to send to the model
        temperature: Temperature parameter to control randomness (may be overridden by settings)
        provider: Optional override for AI provider (if None, uses global ai_provider setting)

    Returns:
        AIResult: Type-safe result wrapper. Use result.text for content,
                  result.is_success to check status. str(result) returns
                  text or error string for backward compatibility.
    """
    from settings.settings_manager import settings_manager
    from utils.validation import sanitize_for_logging

    # Save prompt to debug file (only in debug mode to protect PHI/PII)
    # SECURITY: This logs medical data - only enable for development debugging
    if settings_manager.get("enable_llm_debug_logging", False):
        try:
            from datetime import datetime
            from managers.data_folder_manager import data_folder_manager

            debug_file_path = data_folder_manager.logs_folder / "last_llm_prompt.txt"
            with open(debug_file_path, 'w', encoding='utf-8') as f:
                f.write(f"=== LLM PROMPT DEBUG ===\n")
                f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Model: {model}\n")
                f.write(f"Temperature: {temperature}\n")
                f.write(f"\n--- SYSTEM MESSAGE (sanitized) ---\n")
                # Sanitize to remove potential PHI/PII before logging
                f.write(sanitize_for_logging(system_message, max_length=2000))
                f.write(f"\n\n--- USER PROMPT (sanitized) ---\n")
                f.write(sanitize_for_logging(prompt, max_length=2000))
                f.write(f"\n\n=== END OF PROMPT ===\n")
            logger.debug(f"Saved sanitized LLM prompt to: {debug_file_path}")
        except Exception as e:
            logger.debug(f"Failed to save prompt to debug file: {e}")

    # Reload settings from file to ensure we have the latest provider selection
    current_settings = settings_manager.get_all()

    # Validate provider against allowed list to prevent arbitrary key access
    VALID_PROVIDERS = {PROVIDER_OPENAI, PROVIDER_OLLAMA, PROVIDER_ANTHROPIC, PROVIDER_GEMINI, PROVIDER_GROQ, PROVIDER_CEREBRAS}

    # Track if provider was explicitly passed (affects model selection)
    provider_explicitly_set = provider is not None and provider != ""

    # Use passed-in provider if specified, otherwise use global setting
    if not provider_explicitly_set:
        provider = current_settings.get("ai_provider", PROVIDER_OPENAI)

    if provider not in VALID_PROVIDERS:
        logger.warning(f"Invalid AI provider '{provider}', falling back to OpenAI")
        provider = PROVIDER_OPENAI

    model_key = get_model_key_for_task(system_message, prompt)

    # Get provider-specific temperature if available
    provider_temp_key = f"{provider}_temperature"
    provider_temp = current_settings.get(model_key, {}).get(provider_temp_key)

    # If provider-specific temperature exists, use it, otherwise use the passed temperature
    if provider_temp is not None:
        temperature = provider_temp
    else:
        # Try to get the generic temperature for this model type
        generic_temp = current_settings.get(model_key, {}).get("temperature")
        if generic_temp is not None:
            temperature = generic_temp

    # Try primary provider, then fallback chain if it fails
    result = _call_provider(provider, model, system_message, prompt, temperature,
                            current_settings, model_key, provider_explicitly_set)

    if result.is_success:
        return _log_usage(result, provider, model)

    # If provider was explicitly set by caller, respect that choice — no fallback
    if provider_explicitly_set:
        return result

    # Fallback chain: try other providers that have API keys configured
    logger.warning(f"Primary provider {provider} failed: {result.error}. Trying fallbacks...")

    from utils.security import get_security_manager
    security_manager = get_security_manager()

    for fallback_provider in FALLBACK_CHAIN:
        if fallback_provider == provider:
            continue  # Already tried

        # Check if API key exists for this provider
        api_key = security_manager.get_api_key(fallback_provider)
        if not api_key:
            continue

        logger.info(f"Attempting fallback provider: {fallback_provider}")
        fallback_result = _call_provider(fallback_provider, model, system_message, prompt,
                                         temperature, current_settings, model_key,
                                         provider_explicitly_set=False)
        if fallback_result.is_success:
            logger.info(f"Fallback to {fallback_provider} succeeded")
            return _log_usage(fallback_result, fallback_provider, model)
        logger.warning(f"Fallback {fallback_provider} also failed: {fallback_result.error}")

    # All providers failed
    logger.error("All providers in fallback chain failed")
    return result  # Return original error
