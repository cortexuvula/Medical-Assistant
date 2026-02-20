"""Groq LLM Provider Module.

Handles all API calls to Groq's LLM models (Llama, Mixtral, etc.)
via their OpenAI-compatible API, including streaming support.

Return Types:
    - call_groq: Returns AIResult for type-safe error handling
    - call_groq_streaming: Returns AIResult for type-safe error handling
    - str(result) provides backward compatibility with code expecting strings
"""

import httpx
from typing import List, Dict, Callable

from openai import OpenAI

from utils.structured_logging import get_logger

logger = get_logger(__name__)

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

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


@secure_api_call("groq")
@resilient_api_call(
    max_retries=3,
    initial_delay=1.0,
    backoff_factor=2.0,
    failure_threshold=5,
    recovery_timeout=60
)
def _groq_api_call(model: str, messages: List[Dict[str, str]], temperature: float):
    """Make the actual API call to Groq with explicit timeout.

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
    timeout_seconds = get_timeout("groq")

    try:
        security_manager = get_security_manager()
        api_key = security_manager.get_api_key("groq")
        if not api_key:
            raise AuthenticationError("Groq API key not configured")

        http_client = get_http_client_manager().get_httpx_client("groq", timeout_seconds)
        client = OpenAI(
            api_key=api_key,
            base_url=GROQ_BASE_URL,
            http_client=http_client,
        )

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        return response
    except httpx.TimeoutException as e:
        raise APITimeoutError(
            f"Groq request timed out after {timeout_seconds}s: {e}",
            timeout_seconds=timeout_seconds,
            service="groq"
        )
    except Exception as e:
        error_msg = str(e)
        if "rate limit" in error_msg.lower():
            raise RateLimitError(f"Groq rate limit exceeded: {error_msg}")
        elif "authentication" in error_msg.lower() or "invalid api key" in error_msg.lower():
            raise AuthenticationError(f"Groq authentication failed: {error_msg}")
        elif "timeout" in error_msg.lower():
            raise APITimeoutError(
                f"Groq request timeout: {error_msg}",
                timeout_seconds=timeout_seconds,
                service="groq"
            )
        else:
            raise APIError(f"Groq API error: {error_msg}")


def call_groq(model: str, system_message: str, prompt: str, temperature: float) -> AIResult:
    """Call Groq API to generate a response.

    Args:
        model: Model to use (e.g., llama-3.3-70b-versatile)
        system_message: System message to guide the AI's response
        prompt: User prompt
        temperature: Temperature parameter (0.0 to 1.0)

    Returns:
        AIResult: Type-safe result wrapper.
    """
    security_manager = get_security_manager()

    is_valid, error = validate_model_name(model, "groq")
    if not is_valid:
        title, message = get_error_message("CFG_INVALID_SETTINGS", error)
        return AIResult.failure(message, error_code=title)

    prompt = security_manager.sanitize_input(prompt, "prompt")
    system_message = security_manager.sanitize_input(system_message, "prompt")

    try:
        logger.info(f"Making Groq API call with model: {model}")
        log_api_call_debug("Groq", model, temperature, system_message, prompt)

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ]

        response = _groq_api_call(model, messages, temperature)
        text = response.choices[0].message.content.strip()
        return AIResult.success(text, model=model, provider="groq")
    except APITimeoutError as e:
        logger.error(f"Groq API timeout with model {model}: {str(e)}")
        title, message = get_error_message("CONN_TIMEOUT", f"Request timed out after {e.timeout_seconds}s")
        return AIResult.failure(message, error_code=title, exception=e)
    except (APIError, ServiceUnavailableError) as e:
        logger.error(f"Groq API error with model {model}: {str(e)}")
        error_code, details = format_api_error("groq", e)
        title, message = get_error_message(error_code, details, model)
        return AIResult.failure(message, error_code=title, exception=e)
    except Exception as e:
        logger.error(f"Unexpected error calling Groq: {str(e)}")
        title, message = get_error_message("API_UNEXPECTED_ERROR", str(e))
        return AIResult.failure(message, error_code=title, exception=e)


def call_groq_streaming(
    model: str,
    system_message: str,
    prompt: str,
    temperature: float,
    on_chunk: Callable[[str], None]
) -> AIResult:
    """Call Groq API with streaming response.

    Args:
        model: Model name
        system_message: System message
        prompt: User prompt
        temperature: Temperature setting
        on_chunk: Callback function called with each text chunk

    Returns:
        AIResult: Type-safe result wrapper.
    """
    security_manager = get_security_manager()

    is_valid, error = validate_model_name(model, "groq")
    if not is_valid:
        title, message = get_error_message("CFG_INVALID_SETTINGS", error)
        result = AIResult.failure(message, error_code=title)
        on_chunk(str(result))
        return result

    prompt = security_manager.sanitize_input(prompt, "prompt")
    system_message = security_manager.sanitize_input(system_message, "prompt")

    try:
        logger.info(f"Making streaming Groq API call with model: {model}")
        log_api_call_debug("Groq (streaming)", model, temperature, system_message, prompt)

        api_key = security_manager.get_api_key("groq")
        if not api_key:
            result = AIResult.failure("Groq API key not configured", error_code="AUTH_ERROR")
            on_chunk(str(result))
            return result

        timeout_seconds = get_timeout("groq")
        http_client = get_http_client_manager().get_httpx_client("groq", timeout_seconds)
        client = OpenAI(
            api_key=api_key,
            base_url=GROQ_BASE_URL,
            http_client=http_client,
        )

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

        return AIResult.success(full_response.strip(), model=model, provider="groq")

    except Exception as e:
        logger.error(f"Streaming Groq error with model {model}: {str(e)}")
        result = AIResult.failure(str(e), error_code="STREAMING_ERROR", exception=e)
        on_chunk(str(result))
        return result
