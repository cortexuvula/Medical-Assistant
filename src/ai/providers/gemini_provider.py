"""Gemini Provider Module.

Handles all API calls to Google's Gemini models using the new google-genai SDK.

Return Types:
    - call_gemini: Returns AIResult for type-safe error handling
    - str(result) provides backward compatibility with code expecting strings
"""

import os

from utils.structured_logging import get_logger

logger = get_logger(__name__)

# Import new google-genai SDK
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None
    types = None

from ai.logging_utils import log_api_call_debug
from utils.error_codes import get_error_message, format_api_error
from utils.validation import validate_api_key
from utils.exceptions import (
    APIError, RateLimitError, AuthenticationError, ServiceUnavailableError,
    APITimeoutError, AIResult
)
from utils.resilience import resilient_api_call
from utils.security import get_security_manager
from utils.security_decorators import secure_api_call
from utils.timeout_config import get_timeout


@secure_api_call("gemini")
@resilient_api_call(
    max_retries=3,
    initial_delay=1.0,
    backoff_factor=2.0,
    failure_threshold=5,
    recovery_timeout=60
)
def _gemini_api_call(
    client,
    model_name: str,
    prompt_content: str,
    system_message: str,
    temperature: float,
    max_output_tokens: int = 4096
) -> str:
    """Make the actual API call to Google Gemini with resilience.

    Args:
        client: Configured genai.Client instance
        model_name: Model to use
        prompt_content: User prompt content
        system_message: System instruction
        temperature: Generation temperature
        max_output_tokens: Maximum output tokens

    Returns:
        Generated text response

    Raises:
        APIError: On API failures
        APITimeoutError: On request timeout
    """
    timeout_seconds = get_timeout("gemini")

    try:
        # Build generation config
        config = types.GenerateContentConfig(
            system_instruction=system_message if system_message else None,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

        # Make the API call using the new SDK pattern
        response = client.models.generate_content(
            model=model_name,
            contents=prompt_content,
            config=config,
        )
        return response.text
    except Exception as e:
        error_msg = str(e)
        if "quota" in error_msg.lower() or "rate" in error_msg.lower():
            raise RateLimitError(f"Gemini rate limit exceeded: {error_msg}")
        elif "api key" in error_msg.lower() or "invalid" in error_msg.lower() or "permission" in error_msg.lower():
            raise AuthenticationError(f"Gemini authentication failed: {error_msg}")
        elif "timeout" in error_msg.lower() or "deadline" in error_msg.lower():
            raise APITimeoutError(
                f"Gemini request timeout: {error_msg}",
                timeout_seconds=timeout_seconds,
                service="gemini"
            )
        else:
            raise APIError(f"Gemini API error: {error_msg}")


def call_gemini(model_name: str, system_message: str, prompt: str, temperature: float) -> AIResult:
    """Call Google Gemini API.

    Args:
        model_name: Model to use (e.g., gemini-2.0-flash, gemini-1.5-pro)
        system_message: System message to guide the AI's response
        prompt: User prompt
        temperature: Temperature parameter (0.0 to 1.0)

    Returns:
        AIResult: Type-safe result wrapper. Use result.text for content,
                  result.is_success to check status. str(result) returns
                  text or error string for backward compatibility.
    """
    if not GENAI_AVAILABLE:
        logger.error("google-genai SDK not installed")
        return AIResult.failure(
            "google-genai SDK not installed. Install with: pip install google-genai",
            error_code="DEPENDENCY_MISSING"
        )

    # Get security manager
    security_manager = get_security_manager()

    # Get API key from secure storage or environment
    api_key = security_manager.get_api_key("gemini")
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        logger.error("Gemini API key not provided")
        title, message = get_error_message("API_KEY_MISSING", "Gemini API key not found")
        return AIResult.failure(message, error_code=title)

    # Validate API key format
    is_valid, error = validate_api_key("gemini", api_key)
    if not is_valid:
        logger.error(f"Invalid Gemini API key: {error}")
        title, message = get_error_message("API_KEY_INVALID", error)
        return AIResult.failure(message, error_code=title)

    # Enhanced sanitization
    prompt = security_manager.sanitize_input(prompt, "prompt")
    system_message = security_manager.sanitize_input(system_message, "prompt")

    try:
        logger.info(f"Making Gemini API call with model: {model_name}")

        # Use consolidated debug logging
        log_api_call_debug("Gemini", model_name, temperature, system_message, prompt)

        # Create client with API key (new SDK pattern)
        client = genai.Client(api_key=api_key)

        # Make the API call
        response_text = _gemini_api_call(
            client=client,
            model_name=model_name,
            prompt_content=prompt,
            system_message=system_message,
            temperature=temperature
        )
        return AIResult.success(response_text.strip(), model=model_name, provider="gemini")

    except APITimeoutError as e:
        logger.error(f"Gemini API timeout with model {model_name}: {str(e)}")
        title, message = get_error_message("CONN_TIMEOUT", f"Request timed out after {e.timeout_seconds}s")
        return AIResult.failure(message, error_code=title, exception=e)
    except (APIError, ServiceUnavailableError) as e:
        logger.error(f"Gemini API error with model {model_name}: {str(e)}")
        error_code, details = format_api_error("gemini", e)
        title, message = get_error_message(error_code, details, model_name)
        return AIResult.failure(message, error_code=title, exception=e)
    except Exception as e:
        logger.error(f"Unexpected error calling Gemini: {str(e)}")
        title, message = get_error_message("API_UNEXPECTED_ERROR", str(e))
        return AIResult.failure(message, error_code=title, exception=e)
