"""Ollama Provider Module.

Handles all API calls to local Ollama models.

Return Types:
    - call_ollama: Returns AIResult for type-safe error handling
    - fallback_ollama_generate: Returns AIResult for type-safe error handling
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


_cached_models = {"models": None, "timestamp": 0}


def _get_first_available_model(session, base_url: str) -> str:
    """Query Ollama for installed models and return the first one.

    Caches the result for 60 seconds to avoid repeated API calls.
    """
    now = time.time()
    if _cached_models["models"] is not None and now - _cached_models["timestamp"] < 60:
        return _cached_models["models"]

    try:
        resp = session.get(f"{base_url}/api/tags", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            models = [m["name"] for m in data.get("models", [])]
            if models:
                logger.info(f"Ollama auto-detected models: {models}")
                _cached_models["models"] = models[0]
                _cached_models["timestamp"] = now
                return models[0]
    except Exception as e:
        logger.warning(f"Failed to auto-detect Ollama models: {e}")

    return ""


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
    model = SETTINGS.get(model_key, {}).get("ollama_model", "")

    # If no task-specific model configured, use global default or auto-detect
    if not model:
        model = SETTINGS.get("ollama_default_model", "")
    if not model:
        model = _get_first_available_model(session, base_url)
    if not model:
        model = "llama3"  # last-resort default

    logger.info(f"Making Ollama API call with model: {model}")

    # Use consolidated debug logging
    log_api_call_debug("Ollama", model, temperature, system_message, prompt)

    # Format the request payload for Ollama chat API
    # Use the 'chat' endpoint which handles prompt formatting for all models
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "stream": False
    }

    # Implement retry logic with increasing timeouts
    # Local models need longer timeouts, especially on cold start (loading weights)
    max_retries = 3
    timeout_values = [120, 180, 300]

    # Check if Ollama service is running
    try:
        health_check = session.get(f"{base_url}/api/version", timeout=5)
        if health_check.status_code != 200:
            title, message = get_error_message("CONN_OLLAMA_NOT_RUNNING", f"Service at {ollama_url} returned status {health_check.status_code}")
            return AIResult.failure(message, error_code=title)
    except Exception as e:
        logger.error(f"Ollama service not reachable: {str(e)}")
        title, message = get_error_message("CONN_OLLAMA_NOT_RUNNING", str(e))
        return AIResult.failure(message, error_code=title, exception=e)

    # Try /api/chat first (model-agnostic), fall back to /api/generate
    endpoints = [
        ("chat", payload),
        ("generate", {
            "model": model,
            "prompt": f"{system_message}\n\n{prompt}",
            "temperature": temperature,
            "stream": False,
        }),
    ]

    last_error = None
    for endpoint_name, endpoint_payload in endpoints:
        url = f"{base_url}/api/{endpoint_name}"

        for attempt in range(max_retries):
            timeout = timeout_values[attempt]
            try:
                logger.info(f"Ollama API {endpoint_name} attempt {attempt+1}/{max_retries} with timeout {timeout}s")

                response = session.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    data=json.dumps(endpoint_payload),
                    timeout=timeout,
                )

                # 404 means endpoint or model not found — skip to next endpoint
                if response.status_code == 404:
                    error_body = response.text[:200]
                    logger.warning(f"Ollama {endpoint_name} returned 404: {error_body}")
                    last_error = f"404 from /api/{endpoint_name}: {error_body}"
                    break  # break retry loop, try next endpoint

                response.raise_for_status()

                response_text = response.text.strip()
                if not response_text:
                    raise ValueError("Empty response from Ollama API")

                result = json.loads(response_text)

                # Chat API format
                if "message" in result and "content" in result["message"]:
                    return AIResult.success(result["message"]["content"].strip(), model=model, provider="ollama")
                # Generate API format
                if "response" in result:
                    return AIResult.success(result["response"].strip(), model=model, provider="ollama")

                logger.warning(f"Unexpected Ollama response keys: {list(result.keys())}")
                last_error = f"Unexpected response format from /api/{endpoint_name}"
                break  # try next endpoint

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Ollama {endpoint_name} response: {e}")
                last_error = str(e)
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                break  # try next endpoint

            except Exception as e:
                last_error = str(e)
                if "Timeout" in type(e).__name__:
                    logger.error(f"Ollama {endpoint_name} timeout (attempt {attempt+1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    break  # try next endpoint

                logger.error(f"Ollama {endpoint_name} error: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                break  # try next endpoint
        else:
            # All retries exhausted for this endpoint without break
            continue
        # break was hit — try next endpoint
        continue

    # Both endpoints failed
    if last_error and "404" in str(last_error):
        title, message = get_error_message(
            "CFG_MODEL_NOT_INSTALLED",
            f"Model '{model}' may not be installed. Run: ollama pull {model}",
            model,
        )
    else:
        title, message = get_error_message(
            "CONN_SERVICE_DOWN",
            f"Failed after trying both /api/chat and /api/generate with model '{model}'. Last error: {last_error}",
        )
    return AIResult.failure(message, error_code=title)


def fallback_ollama_generate(model: str, system_message: str, prompt: str, temperature: float, timeout: int) -> AIResult:
    """Fallback method using the generate API endpoint if chat fails.

    Args:
        model: Model name
        system_message: System message
        prompt: User prompt
        temperature: Temperature setting
        timeout: Request timeout in seconds

    Returns:
        AIResult: Type-safe result wrapper.
    """
    ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
    base_url = ollama_url.rstrip("/")

    session = get_http_client_manager().get_requests_session("ollama")

    logger.info(f"Trying fallback generate API for Ollama model: {model}")

    generate_payload = {
        "model": model,
        "prompt": f"{system_message}\n\n{prompt}",
        "temperature": temperature,
        "stream": False
    }

    try:
        response = session.post(
            f"{base_url}/api/generate",
            headers={"Content-Type": "application/json"},
            data=json.dumps(generate_payload),
            timeout=timeout
        )

        response.raise_for_status()

        try:
            result = json.loads(response.text.strip())
            if "response" in result:
                return AIResult.success(result["response"].strip(), model=model, provider="ollama")
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
        logger.error(f"Fallback Ollama generate API error: {str(e)}")
        return AIResult.failure(
            f"Error with Ollama API: {str(e)}. Please check if model '{model}' is properly installed.",
            error_code="OLLAMA_API_ERROR",
            exception=e
        )
