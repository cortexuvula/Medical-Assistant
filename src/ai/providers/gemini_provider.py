"""Gemini Provider Module.

Handles all API calls to Google's Gemini models.
"""

import os
import logging

import google.generativeai as genai

from ai.logging_utils import log_api_call_debug
from utils.error_codes import get_error_message, format_api_error
from utils.validation import validate_api_key
from utils.exceptions import APIError, RateLimitError, AuthenticationError, ServiceUnavailableError, APITimeoutError
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
def _gemini_api_call(model: genai.GenerativeModel, prompt_content: str, generation_config: dict) -> str:
    """Make the actual API call to Google Gemini with resilience.

    Args:
        model: Configured GenerativeModel instance
        prompt_content: Combined system + user prompt content
        generation_config: Generation configuration including temperature

    Returns:
        Generated text response

    Raises:
        APIError: On API failures
        APITimeoutError: On request timeout
    """
    timeout_seconds = get_timeout("gemini")

    try:
        response = model.generate_content(
            prompt_content,
            generation_config=genai.GenerationConfig(**generation_config),
            request_options={"timeout": timeout_seconds}
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


def call_gemini(model_name: str, system_message: str, prompt: str, temperature: float) -> str:
    """Call Google Gemini API.

    Args:
        model_name: Model to use (e.g., gemini-1.5-flash, gemini-1.5-pro)
        system_message: System message to guide the AI's response
        prompt: User prompt
        temperature: Temperature parameter (0.0 to 1.0)

    Returns:
        AI-generated response as a string
    """
    # Get security manager
    security_manager = get_security_manager()

    # Get API key from secure storage or environment
    api_key = security_manager.get_api_key("gemini")
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        logging.error("Gemini API key not provided")
        title, message = get_error_message("API_KEY_MISSING", "Gemini API key not found")
        return f"[Error: {title}] {message}"

    # Validate API key format
    is_valid, error = validate_api_key("gemini", api_key)
    if not is_valid:
        logging.error(f"Invalid Gemini API key: {error}")
        title, message = get_error_message("API_KEY_INVALID", error)
        return f"[Error: {title}] {message}"

    # Enhanced sanitization
    prompt = security_manager.sanitize_input(prompt, "prompt")
    system_message = security_manager.sanitize_input(system_message, "prompt")

    try:
        logging.info(f"Making Gemini API call with model: {model_name}")

        # Use consolidated debug logging
        log_api_call_debug("Gemini", model_name, temperature, system_message, prompt)

        # Configure the Gemini API with the API key
        genai.configure(api_key=api_key)

        # Create the model with system instruction
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_message
        )

        # Configure generation parameters
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": 4096,
        }

        # Make the API call
        response_text = _gemini_api_call(model, prompt, generation_config)
        return response_text.strip()

    except APITimeoutError as e:
        logging.error(f"Gemini API timeout with model {model_name}: {str(e)}")
        title, message = get_error_message("CONN_TIMEOUT", f"Request timed out after {e.timeout_seconds}s")
        return f"[Error: {title}] {message}"
    except (APIError, ServiceUnavailableError) as e:
        logging.error(f"Gemini API error with model {model_name}: {str(e)}")
        error_code, details = format_api_error("gemini", e)
        title, message = get_error_message(error_code, details, model_name)
        return f"[Error: {title}] {message}"
    except Exception as e:
        logging.error(f"Unexpected error calling Gemini: {str(e)}")
        title, message = get_error_message("API_UNEXPECTED_ERROR", str(e))
        return f"[Error: {title}] {message}"
