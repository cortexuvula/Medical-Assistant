"""Anthropic Provider Module.

Handles all API calls to Anthropic's Claude models including streaming support.
"""

import logging
import httpx
from typing import List, Dict, Callable

from anthropic import Anthropic
from anthropic.types import Message as AnthropicMessage

from ai.logging_utils import log_api_call_debug
from utils.error_codes import get_error_message, format_api_error
from utils.validation import validate_api_key, validate_model_name
from utils.exceptions import APIError, RateLimitError, AuthenticationError, ServiceUnavailableError, TimeoutError as AppTimeoutError
from utils.resilience import resilient_api_call
from utils.security import get_security_manager
from utils.security_decorators import secure_api_call
from utils.timeout_config import get_timeout
from utils.http_client_manager import get_http_client_manager


@secure_api_call("anthropic")
@resilient_api_call(
    max_retries=3,
    initial_delay=1.0,
    backoff_factor=2.0,
    failure_threshold=5,
    recovery_timeout=60
)
def _anthropic_api_call(client: Anthropic, model: str, messages: List[Dict[str, str]], temperature: float, max_tokens: int = 4096) -> AnthropicMessage:
    """Make the actual API call to Anthropic with explicit timeout.

    Args:
        client: Anthropic client instance
        model: Model name
        messages: List of messages
        temperature: Temperature setting
        max_tokens: Maximum tokens in response

    Returns:
        API response

    Raises:
        APIError: On API failures
        AppTimeoutError: On request timeout
    """
    timeout_seconds = get_timeout("anthropic")

    try:
        # Convert OpenAI-style messages to Anthropic format
        system_message = None
        user_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            elif msg["role"] == "user":
                user_messages.append({"role": "user", "content": msg["content"]})
            elif msg["role"] == "assistant":
                user_messages.append({"role": "assistant", "content": msg["content"]})

        # Create the message with Anthropic's API
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_message if system_message else None,
            messages=user_messages
        )
        return response
    except httpx.TimeoutException as e:
        raise AppTimeoutError(
            f"Anthropic request timed out after {timeout_seconds}s: {e}",
            timeout_seconds=timeout_seconds,
            service="anthropic"
        )
    except Exception as e:
        error_msg = str(e)
        if "rate_limit" in error_msg.lower():
            raise RateLimitError(f"Anthropic rate limit exceeded: {error_msg}")
        elif "authentication" in error_msg.lower() or "api key" in error_msg.lower():
            raise AuthenticationError(f"Anthropic authentication failed: {error_msg}")
        elif "timeout" in error_msg.lower():
            raise AppTimeoutError(
                f"Anthropic request timeout: {error_msg}",
                timeout_seconds=timeout_seconds,
                service="anthropic"
            )
        else:
            raise APIError(f"Anthropic API error: {error_msg}")


def call_anthropic(model: str, system_message: str, prompt: str, temperature: float) -> str:
    """Call Anthropic's Claude API with explicit timeout.

    Args:
        model: Model to use (e.g., claude-opus-4-20250514)
        system_message: System message to guide the AI's response
        prompt: User prompt
        temperature: Temperature parameter (0.0 to 1.0)

    Returns:
        AI-generated response as a string
    """
    # Get security manager
    security_manager = get_security_manager()

    # Get API key from secure storage or environment
    api_key = security_manager.get_api_key("anthropic")
    if not api_key:
        logging.error("Anthropic API key not provided")
        title, message = get_error_message("API_KEY_MISSING", "Anthropic API key not found")
        return f"[Error: {title}] {message}"

    # Validate API key format
    is_valid, error = validate_api_key("anthropic", api_key)
    if not is_valid:
        logging.error(f"Invalid Anthropic API key: {error}")
        title, message = get_error_message("API_KEY_INVALID", error)
        return f"[Error: {title}] {message}"

    # Validate model name
    is_valid, error = validate_model_name(model, "anthropic")
    if not is_valid:
        title, message = get_error_message("CFG_INVALID_SETTINGS", error)
        return f"[Error: {title}] {message}"

    # Enhanced sanitization
    prompt = security_manager.sanitize_input(prompt, "prompt")
    system_message = security_manager.sanitize_input(system_message, "prompt")

    try:
        logging.info(f"Making Anthropic API call with model: {model}")

        # Use consolidated debug logging
        log_api_call_debug("Anthropic", model, temperature, system_message, prompt)

        # Use pooled HTTP client for connection reuse (saves 50-200ms per call)
        timeout_seconds = get_timeout("anthropic")
        http_client = get_http_client_manager().get_httpx_client("anthropic", timeout_seconds)
        client = Anthropic(
            api_key=api_key,
            http_client=http_client
        )

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ]

        response = _anthropic_api_call(client, model, messages, temperature)
        return response.content[0].text.strip()
    except AppTimeoutError as e:
        logging.error(f"Anthropic API timeout with model {model}: {str(e)}")
        title, message = get_error_message("CONN_TIMEOUT", f"Request timed out after {e.timeout_seconds}s")
        return f"[Error: {title}] {message}"
    except (APIError, ServiceUnavailableError) as e:
        logging.error(f"Anthropic API error with model {model}: {str(e)}")
        error_code, details = format_api_error("anthropic", e)
        title, message = get_error_message(error_code, details, model)
        return f"[Error: {title}] {message}"
    except Exception as e:
        logging.error(f"Unexpected error calling Anthropic: {str(e)}")
        title, message = get_error_message("API_UNEXPECTED_ERROR", str(e))
        return f"[Error: {title}] {message}"


def call_anthropic_streaming(
    model: str,
    system_message: str,
    prompt: str,
    temperature: float,
    on_chunk: Callable[[str], None]
) -> str:
    """Call Anthropic API with streaming response.

    Displays response progressively instead of waiting for complete response.
    Reduces perceived latency by 50% for long responses.

    Args:
        model: Model name
        system_message: System message
        prompt: User prompt
        temperature: Temperature setting
        on_chunk: Callback function called with each text chunk

    Returns:
        Complete response text
    """
    security_manager = get_security_manager()

    # Get API key
    api_key = security_manager.get_api_key("anthropic")
    if not api_key:
        error_msg = "[Error] Anthropic API key not found"
        on_chunk(error_msg)
        return error_msg

    # Validate inputs
    is_valid, error = validate_api_key("anthropic", api_key)
    if not is_valid:
        error_msg = f"[Error] Invalid Anthropic API key: {error}"
        on_chunk(error_msg)
        return error_msg

    is_valid, error = validate_model_name(model, "anthropic")
    if not is_valid:
        error_msg = f"[Error] Invalid model: {error}"
        on_chunk(error_msg)
        return error_msg

    # Enhanced sanitization
    prompt = security_manager.sanitize_input(prompt, "prompt")
    system_message = security_manager.sanitize_input(system_message, "prompt")

    try:
        logging.info(f"Making streaming Anthropic API call with model: {model}")
        log_api_call_debug("Anthropic (streaming)", model, temperature, system_message, prompt)

        timeout_seconds = get_timeout("anthropic")
        http_client = get_http_client_manager().get_httpx_client("anthropic", timeout_seconds)
        client = Anthropic(api_key=api_key, http_client=http_client)

        full_response = ""
        with client.messages.stream(
            model=model,
            max_tokens=4096,
            temperature=temperature,
            system=system_message,
            messages=[{"role": "user", "content": prompt}]
        ) as stream:
            for text in stream.text_stream:
                full_response += text
                on_chunk(text)

        return full_response.strip()

    except Exception as e:
        logging.error(f"Streaming Anthropic error with model {model}: {str(e)}")
        error_msg = f"[Error] {str(e)}"
        on_chunk(error_msg)
        return error_msg
