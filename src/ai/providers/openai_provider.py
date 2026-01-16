"""OpenAI Provider Module.

Handles all API calls to OpenAI's GPT models including streaming support.

Return Types:
    - call_openai: Returns AIResult for type-safe error handling
    - call_openai_streaming: Returns AIResult for type-safe error handling
    - str(result) provides backward compatibility with code expecting strings
"""

import logging
import httpx
from typing import List, Dict, Callable, Union

from openai import OpenAI
from openai.types.chat import ChatCompletion

from ai.logging_utils import log_api_call_debug
from utils.error_codes import get_error_message, format_api_error
from utils.validation import validate_model_name
from utils.exceptions import (
    APIError, RateLimitError, AuthenticationError, ServiceUnavailableError,
    APITimeoutError, AIResult
)
from utils.resilience import resilient_api_call
from utils.security import get_security_manager
from utils.security_decorators import secure_api_call
from utils.timeout_config import get_timeout
from utils.http_client_manager import get_http_client_manager


@secure_api_call("openai")
@resilient_api_call(
    max_retries=3,
    initial_delay=1.0,
    backoff_factor=2.0,
    failure_threshold=5,
    recovery_timeout=60
)
def _openai_api_call(model: str, messages: List[Dict[str, str]], temperature: float) -> ChatCompletion:
    """Make the actual API call to OpenAI with explicit timeout.

    Args:
        model: Model name
        messages: List of messages
        temperature: Temperature setting

    Returns:
        API response

    Raises:
        APIError: On API failures
        APITimeoutError: On request timeout
    """
    timeout_seconds = get_timeout("openai")

    try:
        # Use pooled HTTP client for connection reuse (saves 50-200ms per call)
        http_client = get_http_client_manager().get_httpx_client("openai", timeout_seconds)
        client = OpenAI(http_client=http_client)

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        return response
    except httpx.TimeoutException as e:
        raise APITimeoutError(
            f"OpenAI request timed out after {timeout_seconds}s: {e}",
            timeout_seconds=timeout_seconds,
            service="openai"
        )
    except Exception as e:
        error_msg = str(e)
        if "rate limit" in error_msg.lower():
            raise RateLimitError(f"OpenAI rate limit exceeded: {error_msg}")
        elif "authentication" in error_msg.lower() or "invalid api key" in error_msg.lower():
            raise AuthenticationError(f"OpenAI authentication failed: {error_msg}")
        elif "timeout" in error_msg.lower():
            raise APITimeoutError(
                f"OpenAI request timeout: {error_msg}",
                timeout_seconds=timeout_seconds,
                service="openai"
            )
        else:
            raise APIError(f"OpenAI API error: {error_msg}")


def call_openai(model: str, system_message: str, prompt: str, temperature: float) -> AIResult:
    """Call OpenAI API to generate a response.

    Args:
        model: Model to use (e.g., gpt-4, gpt-3.5-turbo)
        system_message: System message to guide the AI's response
        prompt: User prompt
        temperature: Temperature parameter (0.0 to 1.0)

    Returns:
        AIResult: Type-safe result wrapper. Use result.text for content,
                  result.is_success to check status. str(result) returns
                  text or error string for backward compatibility.
    """
    # Get security manager
    security_manager = get_security_manager()

    # Validate inputs
    is_valid, error = validate_model_name(model, "openai")
    if not is_valid:
        title, message = get_error_message("CFG_INVALID_SETTINGS", error)
        return AIResult.failure(message, error_code=title)

    # Enhanced sanitization
    prompt = security_manager.sanitize_input(prompt, "prompt")
    system_message = security_manager.sanitize_input(system_message, "prompt")

    try:
        logging.info(f"Making OpenAI API call with model: {model}")

        # Use consolidated debug logging
        log_api_call_debug("OpenAI", model, temperature, system_message, prompt)

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ]

        response = _openai_api_call(model, messages, temperature)
        text = response.choices[0].message.content.strip()
        return AIResult.success(text, model=model, provider="openai")
    except APITimeoutError as e:
        logging.error(f"OpenAI API timeout with model {model}: {str(e)}")
        title, message = get_error_message("CONN_TIMEOUT", f"Request timed out after {e.timeout_seconds}s")
        return AIResult.failure(message, error_code=title, exception=e)
    except (APIError, ServiceUnavailableError) as e:
        logging.error(f"OpenAI API error with model {model}: {str(e)}")
        error_code, details = format_api_error("openai", e)
        title, message = get_error_message(error_code, details, model)
        return AIResult.failure(message, error_code=title, exception=e)
    except Exception as e:
        logging.error(f"Unexpected error calling OpenAI: {str(e)}")
        title, message = get_error_message("API_UNEXPECTED_ERROR", str(e))
        return AIResult.failure(message, error_code=title, exception=e)


def call_openai_streaming(
    model: str,
    system_message: str,
    prompt: str,
    temperature: float,
    on_chunk: Callable[[str], None]
) -> AIResult:
    """Call OpenAI API with streaming response.

    Displays response progressively instead of waiting for complete response.
    Reduces perceived latency by 50% for long responses.

    Args:
        model: Model name
        system_message: System message
        prompt: User prompt
        temperature: Temperature setting
        on_chunk: Callback function called with each text chunk

    Returns:
        AIResult: Type-safe result wrapper. Use result.text for content,
                  result.is_success to check status. str(result) returns
                  text or error string for backward compatibility.
    """
    security_manager = get_security_manager()

    # Validate inputs
    is_valid, error = validate_model_name(model, "openai")
    if not is_valid:
        title, message = get_error_message("CFG_INVALID_SETTINGS", error)
        result = AIResult.failure(message, error_code=title)
        on_chunk(str(result))
        return result

    # Enhanced sanitization
    prompt = security_manager.sanitize_input(prompt, "prompt")
    system_message = security_manager.sanitize_input(system_message, "prompt")

    try:
        logging.info(f"Making streaming OpenAI API call with model: {model}")
        log_api_call_debug("OpenAI (streaming)", model, temperature, system_message, prompt)

        timeout_seconds = get_timeout("openai")
        http_client = get_http_client_manager().get_httpx_client("openai", timeout_seconds)
        client = OpenAI(http_client=http_client)

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ]

        full_response = ""
        with client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            stream=True
        ) as stream:
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    full_response += text
                    on_chunk(text)

        return AIResult.success(full_response.strip(), model=model, provider="openai")

    except Exception as e:
        logging.error(f"Streaming OpenAI error with model {model}: {str(e)}")
        result = AIResult.failure(str(e), error_code="STREAMING_ERROR", exception=e)
        on_chunk(str(result))
        return result
