"""Ollama Provider Module.

Handles all API calls to local Ollama models.

Return Types:
    - call_ollama: Returns AIResult for type-safe error handling
    - fallback_ollama_chat: Returns AIResult for type-safe error handling
    - str(result) provides backward compatibility with code expecting strings
"""

import os
import json
import time

from utils.structured_logging import get_logger

logger = get_logger(__name__)

from ai.logging_utils import log_api_call_debug
from ai.providers.base import get_model_key_for_task
from utils.error_codes import get_error_message
from utils.validation import sanitize_prompt
from utils.exceptions import AIResult
from utils.http_client_manager import get_http_client_manager
from settings.settings import SETTINGS


def call_ollama(system_message: str, prompt: str, temperature: float) -> AIResult:
    """Call local Ollama API to generate a response.

    Args:
        system_message: System message to guide the AI's response
        prompt: User prompt
        temperature: Temperature parameter (0.0 to 1.0)

    Returns:
        AIResult: Type-safe result wrapper. Use result.text for content,
                  result.is_success to check status. str(result) returns
                  text or error string for backward compatibility.
    """
    # Sanitize inputs first
    prompt = sanitize_prompt(prompt)
    system_message = sanitize_prompt(system_message)

    # Get pooled session for connection reuse
    session = get_http_client_manager().get_requests_session("ollama")

    # Get Ollama API URL from environment or use default
    ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
    base_url = ollama_url.rstrip("/")  # Remove trailing slash if present

    # Get model from settings based on the task
    model_key = get_model_key_for_task(system_message, prompt)
    model = SETTINGS.get(model_key, {}).get("ollama_model", "llama3")

    logger.info(f"Making Ollama API call with model: {model}")

    # Use consolidated debug logging
    log_api_call_debug("Ollama", model, temperature, system_message, prompt)

    # Format the request payload for Ollama API
    # Use the 'generate' endpoint instead of 'chat' for more consistent responses
    # across different Ollama models
    payload = {
        "model": model,
        "prompt": f"<s>[INST] <<SYS>>\n{system_message}\n<</SYS>>\n\n{prompt}[/INST]",
        "temperature": temperature,
        "stream": False
    }

    # Implement retry logic with increasing timeouts
    max_retries = 3
    timeout_values = [60, 120, 180]  # Increasing timeouts for each retry

    for attempt in range(max_retries):
        try:
            logger.info(f"Ollama API attempt {attempt+1}/{max_retries} with timeout {timeout_values[attempt]}s")

            # Check if Ollama service is running before making the request
            try:
                health_check = session.get(f"{base_url}/api/version", timeout=5)
                if health_check.status_code != 200:
                    logger.error(f"Ollama service health check failed: {health_check.status_code}")
                    if attempt == max_retries - 1:  # Last attempt
                        title, message = get_error_message("CONN_OLLAMA_NOT_RUNNING", f"Service at {ollama_url} returned status {health_check.status_code}")
                        return AIResult.failure(message, error_code=title)
                    time.sleep(2)  # Wait before next retry
                    continue
            except Exception as e:
                logger.error(f"Ollama service health check error: {str(e)}")
                if attempt == max_retries - 1:  # Last attempt
                    title, message = get_error_message("CONN_OLLAMA_NOT_RUNNING", str(e))
                    return AIResult.failure(message, error_code=title, exception=e)
                time.sleep(2)  # Wait before next retry
                continue

            # Try the '/api/generate' endpoint which works more consistently across models
            response = session.post(
                f"{base_url}/api/generate",
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=timeout_values[attempt]
            )

            response.raise_for_status()  # Raise exception for error status codes

            # Safely parse the JSON response with improved error handling
            try:
                response_text = response.text.strip()
                if not response_text:
                    raise ValueError("Empty response from Ollama API")

                # Handle case where the response might contain multiple JSON objects
                # (common with some Ollama models)
                if '\n' in response_text:
                    # Take only the last complete JSON object
                    try:
                        lines = response_text.strip().split('\n')
                        result = json.loads(lines[-1])
                    except json.JSONDecodeError:
                        # If that fails, try to parse the first line
                        result = json.loads(lines[0])
                else:
                    result = json.loads(response_text)

                # Extract the response based on generate API format
                if "response" in result:
                    return AIResult.success(result["response"].strip(), model=model, provider="ollama")
                else:
                    logger.warning(f"Unexpected Ollama API response format: {result}")
                    # Fallback to chat API if generate fails
                    return fallback_ollama_chat(model, system_message, prompt, temperature, timeout_values[attempt])

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Ollama API response: {e}")
                logger.error(f"Raw response: {response.text[:500]}...")  # Log first 500 chars
                if attempt == max_retries - 1:  # Last attempt
                    # Try the fallback method
                    return fallback_ollama_chat(model, system_message, prompt, temperature, timeout_values[attempt])
                time.sleep(2)
                continue

        except Exception as e:
            if "Timeout" in type(e).__name__:
                logger.error(f"Ollama API timeout with model {model} (attempt {attempt+1}/{max_retries})")
                if attempt == max_retries - 1:  # Last attempt
                    title, message = get_error_message("CONN_TIMEOUT", f"Model '{model}' took longer than {timeout_values[attempt]} seconds to respond")
                    return AIResult.failure(message, error_code=title, exception=e)
                time.sleep(2)  # Wait before next retry
                continue

            logger.error(f"Ollama API error with model {model}: {str(e)}")
            if attempt == max_retries - 1:  # Last attempt
                # Check if it's a model not found error
                if "model" in str(e).lower() and "not found" in str(e).lower():
                    title, message = get_error_message("CFG_MODEL_NOT_INSTALLED", str(e), model)
                else:
                    title, message = get_error_message("UNKNOWN_ERROR", str(e))
                return AIResult.failure(message, error_code=title, exception=e)
            time.sleep(2)  # Wait before next retry
            continue

    # If all retries failed
    title, message = get_error_message("CONN_SERVICE_DOWN", f"Failed after {max_retries} attempts with model '{model}'")
    return AIResult.failure(message, error_code=title)


def fallback_ollama_chat(model: str, system_message: str, prompt: str, temperature: float, timeout: int) -> AIResult:
    """Fallback method to use the chat API endpoint if generate fails.

    Args:
        model: Model name
        system_message: System message
        prompt: User prompt
        temperature: Temperature setting
        timeout: Request timeout in seconds

    Returns:
        AIResult: Type-safe result wrapper. Use result.text for content,
                  result.is_success to check status. str(result) returns
                  text or error string for backward compatibility.
    """
    ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
    base_url = ollama_url.rstrip("/")

    # Get pooled session for connection reuse
    session = get_http_client_manager().get_requests_session("ollama")

    logger.info(f"Trying fallback chat API for Ollama model: {model}")

    chat_payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "stream": False
    }

    try:
        response = session.post(
            f"{base_url}/api/chat",
            headers={"Content-Type": "application/json"},
            data=json.dumps(chat_payload),
            timeout=timeout
        )

        response.raise_for_status()

        try:
            result = json.loads(response.text.strip())
            if "message" in result and "content" in result["message"]:
                return AIResult.success(result["message"]["content"].strip(), model=model, provider="ollama")
            else:
                return AIResult.failure(
                    f"Unable to get proper response from Ollama. Raw response: {response.text[:100]}...",
                    error_code="OLLAMA_INVALID_RESPONSE"
                )
        except json.JSONDecodeError as e:
            return AIResult.failure(
                "Could not parse Ollama response as JSON. Please try a different model or check Ollama installation.",
                error_code="OLLAMA_PARSE_ERROR",
                exception=e
            )

    except Exception as e:
        logger.error(f"Fallback Ollama chat API error: {str(e)}")
        return AIResult.failure(
            f"Error with Ollama API: {str(e)}. Please check if model '{model}' is properly installed.",
            error_code="OLLAMA_API_ERROR",
            exception=e
        )
