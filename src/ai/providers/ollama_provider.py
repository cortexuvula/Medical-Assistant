"""Ollama Provider Module.

Handles all API calls to local Ollama models.
"""

import os
import json
import time
import logging

from ai.logging_utils import log_api_call_debug
from ai.providers.base import get_model_key_for_task
from utils.error_codes import get_error_message
from utils.validation import sanitize_prompt
from utils.http_client_manager import get_http_client_manager
from settings.settings import SETTINGS


def call_ollama(system_message: str, prompt: str, temperature: float) -> str:
    """Call local Ollama API to generate a response.

    Args:
        system_message: System message to guide the AI's response
        prompt: User prompt
        temperature: Temperature parameter (0.0 to 1.0)

    Returns:
        AI-generated response as a string
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

    logging.info(f"Making Ollama API call with model: {model}")

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
            logging.info(f"Ollama API attempt {attempt+1}/{max_retries} with timeout {timeout_values[attempt]}s")

            # Check if Ollama service is running before making the request
            try:
                health_check = session.get(f"{base_url}/api/version", timeout=5)
                if health_check.status_code != 200:
                    logging.error(f"Ollama service health check failed: {health_check.status_code}")
                    if attempt == max_retries - 1:  # Last attempt
                        title, message = get_error_message("CONN_OLLAMA_NOT_RUNNING", f"Service at {ollama_url} returned status {health_check.status_code}")
                        return f"[Error: {title}] {message}"
                    time.sleep(2)  # Wait before next retry
                    continue
            except Exception as e:
                logging.error(f"Ollama service health check error: {str(e)}")
                if attempt == max_retries - 1:  # Last attempt
                    title, message = get_error_message("CONN_OLLAMA_NOT_RUNNING", str(e))
                    return f"[Error: {title}] {message}"
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
                    return result["response"].strip()
                else:
                    logging.warning(f"Unexpected Ollama API response format: {result}")
                    # Fallback to chat API if generate fails
                    return fallback_ollama_chat(model, system_message, prompt, temperature, timeout_values[attempt])

            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse Ollama API response: {e}")
                logging.error(f"Raw response: {response.text[:500]}...")  # Log first 500 chars
                if attempt == max_retries - 1:  # Last attempt
                    # Try the fallback method
                    return fallback_ollama_chat(model, system_message, prompt, temperature, timeout_values[attempt])
                time.sleep(2)
                continue

        except Exception as e:
            if "Timeout" in type(e).__name__:
                logging.error(f"Ollama API timeout with model {model} (attempt {attempt+1}/{max_retries})")
                if attempt == max_retries - 1:  # Last attempt
                    title, message = get_error_message("CONN_TIMEOUT", f"Model '{model}' took longer than {timeout_values[attempt]} seconds to respond")
                    return f"[Error: {title}] {message}"
                time.sleep(2)  # Wait before next retry
                continue

            logging.error(f"Ollama API error with model {model}: {str(e)}")
            if attempt == max_retries - 1:  # Last attempt
                # Check if it's a model not found error
                if "model" in str(e).lower() and "not found" in str(e).lower():
                    title, message = get_error_message("CFG_MODEL_NOT_INSTALLED", str(e), model)
                else:
                    title, message = get_error_message("UNKNOWN_ERROR", str(e))
                return f"[Error: {title}] {message}"
            time.sleep(2)  # Wait before next retry
            continue

    # If all retries failed
    title, message = get_error_message("CONN_SERVICE_DOWN", f"Failed after {max_retries} attempts with model '{model}'")
    return f"[Error: {title}] {message}"


def fallback_ollama_chat(model: str, system_message: str, prompt: str, temperature: float, timeout: int) -> str:
    """Fallback method to use the chat API endpoint if generate fails.

    Args:
        model: Model name
        system_message: System message
        prompt: User prompt
        temperature: Temperature setting
        timeout: Request timeout in seconds

    Returns:
        AI-generated response as a string
    """
    ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
    base_url = ollama_url.rstrip("/")

    # Get pooled session for connection reuse
    session = get_http_client_manager().get_requests_session("ollama")

    logging.info(f"Trying fallback chat API for Ollama model: {model}")

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
                return result["message"]["content"].strip()
            else:
                return f"Error: Unable to get proper response from Ollama. Raw response: {response.text[:100]}..."
        except json.JSONDecodeError:
            return f"Error: Could not parse Ollama response as JSON. Please try a different model or check Ollama installation."

    except Exception as e:
        logging.error(f"Fallback Ollama chat API error: {str(e)}")
        return f"Error with Ollama API: {str(e)}. Please check if model '{model}' is properly installed."
