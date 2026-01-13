import openai
import os
import logging
import re
import requests
import json
import httpx
from typing import List, Dict, Any, Optional, Callable, Generator
from openai import OpenAI
from openai.types.chat import ChatCompletion
from anthropic import Anthropic
from anthropic.types import Message as AnthropicMessage
from ai.prompts import (
    REFINE_PROMPT, REFINE_SYSTEM_MESSAGE,
    IMPROVE_PROMPT, IMPROVE_SYSTEM_MESSAGE,
    SOAP_PROMPT_TEMPLATE, SOAP_SYSTEM_MESSAGE,
    get_soap_system_message
)
from settings.settings import SETTINGS, _DEFAULT_SETTINGS
from utils.error_codes import get_error_message, format_api_error
from utils.validation import validate_api_key, sanitize_prompt, validate_model_name, sanitize_for_logging
from utils.exceptions import APIError, RateLimitError, AuthenticationError, ServiceUnavailableError, TimeoutError as AppTimeoutError
from utils.resilience import resilient_api_call
from utils.security import get_security_manager
from utils.security_decorators import secure_api_call, rate_limited
from utils.timeout_config import get_timeout, get_timeout_tuple
from utils.http_client_manager import get_http_client_manager
from utils.constants import (
    PROVIDER_OPENAI, PROVIDER_ANTHROPIC,
    PROVIDER_OLLAMA, PROVIDER_GEMINI
)
import google.generativeai as genai


def log_api_call_debug(provider: str, model: str, temperature: float, system_message: str, prompt: str) -> None:
    """Consolidated debug logging for API calls with sensitive data sanitization.

    All logged content is sanitized to prevent accidental exposure of:
    - API keys
    - Authorization tokens
    - PII (emails, phone numbers, SSNs)
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
        AppTimeoutError: On request timeout
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
        raise AppTimeoutError(
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
            raise AppTimeoutError(
                f"OpenAI request timeout: {error_msg}",
                timeout_seconds=timeout_seconds,
                service="openai"
            )
        else:
            raise APIError(f"OpenAI API error: {error_msg}")

def call_openai(model: str, system_message: str, prompt: str, temperature: float) -> str:
    # Get security manager
    security_manager = get_security_manager()

    # Validate inputs
    is_valid, error = validate_model_name(model, "openai")
    if not is_valid:
        title, message = get_error_message("CFG_INVALID_SETTINGS", error)
        return f"[Error: {title}] {message}"

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
        return response.choices[0].message.content.strip()
    except AppTimeoutError as e:
        logging.error(f"OpenAI API timeout with model {model}: {str(e)}")
        title, message = get_error_message("CONN_TIMEOUT", f"Request timed out after {e.timeout_seconds}s")
        return f"[Error: {title}] {message}"
    except (APIError, ServiceUnavailableError) as e:
        logging.error(f"OpenAI API error with model {model}: {str(e)}")
        error_code, details = format_api_error("openai", e)
        title, message = get_error_message(error_code, details, model)
        # Return error message that includes troubleshooting hints
        return f"[Error: {title}] {message}"
    except Exception as e:
        logging.error(f"Unexpected error calling OpenAI: {str(e)}")
        title, message = get_error_message("API_UNEXPECTED_ERROR", str(e))
        return f"[Error: {title}] {message}"


def call_openai_streaming(
    model: str,
    system_message: str,
    prompt: str,
    temperature: float,
    on_chunk: Callable[[str], None]
) -> str:
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
        Complete response text
    """
    security_manager = get_security_manager()

    # Validate inputs
    is_valid, error = validate_model_name(model, "openai")
    if not is_valid:
        title, message = get_error_message("CFG_INVALID_SETTINGS", error)
        error_msg = f"[Error: {title}] {message}"
        on_chunk(error_msg)
        return error_msg

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

        return full_response.strip()

    except Exception as e:
        logging.error(f"Streaming OpenAI error with model {model}: {str(e)}")
        error_msg = f"[Error] {str(e)}"
        on_chunk(error_msg)
        return error_msg


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


def call_ai_streaming(
    model: str,
    system_message: str,
    prompt: str,
    temperature: float,
    on_chunk: Callable[[str], None]
) -> str:
    """Route streaming API calls to the appropriate provider.

    Args:
        model: Model to use
        system_message: System message
        prompt: User prompt
        temperature: Temperature setting
        on_chunk: Callback for each text chunk

    Returns:
        Complete response text
    """
    from settings.settings import load_settings
    current_settings = load_settings()

    VALID_PROVIDERS = {PROVIDER_OPENAI, PROVIDER_ANTHROPIC}
    provider = current_settings.get("ai_provider", "openai")

    # Only OpenAI and Anthropic support streaming currently
    if provider == PROVIDER_ANTHROPIC:
        model_key = get_model_key_for_task(system_message, prompt)
        actual_model = current_settings.get(model_key, {}).get("anthropic_model", "claude-sonnet-4-20250514")
        return call_anthropic_streaming(actual_model, system_message, prompt, temperature, on_chunk)
    elif provider == PROVIDER_OPENAI:
        model_key = get_model_key_for_task(system_message, prompt)
        actual_model = current_settings.get(model_key, {}).get("model", model)
        return call_openai_streaming(actual_model, system_message, prompt, temperature, on_chunk)
    else:
        # Fall back to non-streaming for unsupported providers
        logging.info(f"Streaming not supported for {provider}, using non-streaming")
        result = call_ai(model, system_message, prompt, temperature)
        on_chunk(result)
        return result


def call_ollama(system_message: str, prompt: str, temperature: float) -> str:
    import json
    import time

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
                
        except requests.exceptions.Timeout:
            logging.error(f"Ollama API timeout with model {model} (attempt {attempt+1}/{max_retries})")
            if attempt == max_retries - 1:  # Last attempt
                title, message = get_error_message("CONN_TIMEOUT", f"Model '{model}' took longer than {timeout_values[attempt]} seconds to respond")
                return f"[Error: {title}] {message}"
            time.sleep(2)  # Wait before next retry
            continue
            
        except Exception as e:
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
    """Fallback method to use the chat API endpoint if generate fails"""
    import json

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
        AppTimeoutError: On request timeout
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
            raise AppTimeoutError(
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

    except AppTimeoutError as e:
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


def adjust_text_with_openai(text: str) -> str:
    model = SETTINGS["refine_text"]["model"]  # Use actual settings, not defaults
    
    full_prompt = f"{REFINE_PROMPT}\n\nOriginal: {text}\n\nCorrected:"
    # Get temperature from settings or use a reasonable default
    temperature = SETTINGS.get("refine_text", {}).get("temperature", 0.0)
    return call_ai(model, REFINE_SYSTEM_MESSAGE, full_prompt, temperature)

def improve_text_with_openai(text: str) -> str:
    model = SETTINGS["improve_text"]["model"]  # Use actual settings, not defaults
    
    full_prompt = f"{IMPROVE_PROMPT}\n\nOriginal: {text}\n\nImproved:"
    # Get temperature from settings or use a reasonable default
    temperature = SETTINGS.get("improve_text", {}).get("temperature", 0.5)
    return call_ai(model, IMPROVE_SYSTEM_MESSAGE, full_prompt, temperature)

def clean_text(text: str, remove_markdown: bool = True, remove_citations: bool = True) -> str:
    """Clean text by removing markdown formatting and/or citation markers.

    Args:
        text: The text to clean
        remove_markdown: Whether to remove markdown formatting
        remove_citations: Whether to remove citation markers like [1], [2]

    Returns:
        Cleaned text
    """
    if remove_markdown:
        # Remove code blocks
        text = re.sub(r"```.+?```", "", text, flags=re.DOTALL)
        # Remove inline code
        text = re.sub(r"`(.+?)`", r"\1", text)
        # Remove markdown headings
        text = re.sub(r"^\s*#+\s*", "", text, flags=re.MULTILINE)
        # Remove bold and italic markers
        text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)
        text = re.sub(r"(\*|_)(.*?)\1", r"\2", text)

    if remove_citations:
        # Remove citation markers like [1], [2] etc.
        text = re.sub(r'(\[\d+\])+', '', text)

    return text.strip()


def format_soap_paragraphs(text: str) -> str:
    """Ensure proper paragraph separation between SOAP note sections.

    Adds blank lines before major section headers if not already present.
    Also handles cases where headers appear mid-line by splitting them.

    Args:
        text: SOAP note text

    Returns:
        Text with proper paragraph separation
    """
    # SOAP section headers that should have a blank line before them (lowercase for matching)
    section_headers = [
        "icd-9 code",
        "icd-10 code",
        "icd code",
        "subjective",
        "objective",
        "assessment",
        "differential diagnosis",
        "plan",
        "follow up",
        "follow-up",
        "clinical synopsis",
    ]

    # Normalize line endings first
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Handle case where section headers appear mid-line (e.g., "content Subjective:")
    # Split them onto separate lines
    for header in section_headers:
        # Pattern: non-whitespace followed by whitespace followed by header with colon
        # This splits "some text Subjective:" into "some text\nSubjective:"
        pattern = rf'(\S)\s+({re.escape(header)}:)'
        text = re.sub(pattern, r'\1\n\2', text, flags=re.IGNORECASE)
        # Also handle header without colon at end of content
        pattern2 = rf'(\S)\s+({re.escape(header)})\s*$'
        text = re.sub(pattern2, r'\1\n\2', text, flags=re.IGNORECASE | re.MULTILINE)

    lines = text.split('\n')
    result_lines = []
    detected_headers = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        # Remove leading dash/bullet for header detection
        stripped_no_bullet = stripped.lstrip('-').lstrip('•').lstrip('*').strip()
        stripped_lower = stripped_no_bullet.lower()

        # Check if this line STARTS with a section header
        is_section_header = False
        matched_header = None
        for header in section_headers:
            if stripped_lower.startswith(header):
                # Verify it's actually a header (followed by :, space, or end of string)
                rest = stripped_lower[len(header):]
                if not rest or rest[0] in (':', ' ', '\t'):
                    is_section_header = True
                    matched_header = header
                    break

        if is_section_header:
            detected_headers.append(matched_header)

        # Add blank line before section header if needed (not for first section)
        if is_section_header and i > 0:
            # Check if previous line is already blank
            if result_lines and result_lines[-1].strip() != '':
                result_lines.append('')

        result_lines.append(line)

    logging.info(f"format_soap_paragraphs: {len(lines)} lines -> {len(result_lines)} lines, detected headers: {detected_headers}")
    return '\n'.join(result_lines)

def create_soap_note_streaming(
    text: str,
    context: str = "",
    on_chunk: Callable[[str], None] = None
) -> str:
    """Create a SOAP note with streaming display.

    Displays response progressively instead of waiting for complete response.
    Provides better user feedback during long generation operations.

    Args:
        text: Transcript text to convert to SOAP note
        context: Optional additional medical context
        on_chunk: Callback function called with each text chunk for progressive display

    Returns:
        Complete SOAP note text
    """
    from datetime import datetime
    from settings.settings import load_settings

    # Reload settings to get latest
    current_settings = load_settings()

    model = current_settings.get("soap_note", {}).get("model", "gpt-4")

    # Get ICD code version from settings
    icd_version = current_settings.get("soap_note", {}).get("icd_code_version", "ICD-9")

    # Get current AI provider for provider-specific prompt
    current_provider = current_settings.get("ai_provider", "openai")

    # Get dynamic system message based on ICD code preference and provider
    system_message = get_soap_system_message(icd_version, provider=current_provider)

    # Check for per-provider custom system message first
    provider_message_key = f"{current_provider}_system_message"
    custom_message = current_settings.get("soap_note", {}).get(provider_message_key, "")

    # Fall back to legacy single system_message if provider-specific is empty
    if not custom_message or not custom_message.strip():
        custom_message = current_settings.get("soap_note", {}).get("system_message", "")

    # Use custom message if provided, otherwise keep dynamic default
    if custom_message and custom_message.strip():
        system_message = custom_message

    # Get temperature from settings
    temperature = current_settings.get("soap_note", {}).get("temperature", 0.4)

    # Get current time and date in the specified format
    current_datetime = datetime.now()
    time_date_str = current_datetime.strftime("Time %H:%M Date %d %b %Y")

    # Build the transcript with time/date prepended
    transcript_with_datetime = f"{time_date_str}\n\n{text}"

    # If context is provided, prepend it to the prompt
    if context and context.strip():
        full_prompt = f"Previous medical context:\n{context}\n\n{SOAP_PROMPT_TEMPLATE.format(text=transcript_with_datetime)}"
    else:
        full_prompt = SOAP_PROMPT_TEMPLATE.format(text=transcript_with_datetime)

    # Use streaming API call
    if on_chunk:
        result = call_ai_streaming(model, system_message, full_prompt, temperature, on_chunk)
    else:
        # Fall back to non-streaming if no callback provided
        result = call_ai(model, system_message, full_prompt, temperature)

    # Trace logging for SOAP formatting (INFO level to appear in logs)
    logging.info(f"SOAP streaming raw response: {len(result)} chars, {result.count(chr(10))} newlines")
    # Log first 200 chars to see structure (repr shows actual newlines as \n)
    logging.info(f"SOAP raw preview: {repr(result[:200])}")

    # Clean both markdown and citations, then format paragraphs
    cleaned_soap = clean_text(result)
    logging.info(f"SOAP after clean_text: {len(cleaned_soap)} chars, {cleaned_soap.count(chr(10))} newlines")

    cleaned_soap = format_soap_paragraphs(cleaned_soap)

    # Count blank lines (consecutive newlines) to verify formatting
    blank_line_count = cleaned_soap.count('\n\n')
    logging.info(f"SOAP after format_soap_paragraphs: {len(cleaned_soap)} chars, {cleaned_soap.count(chr(10))} newlines, {blank_line_count} blank lines")
    logging.info(f"SOAP final preview: {repr(cleaned_soap[:200])}")

    # Check if the AI already generated a Clinical Synopsis section
    # (Some providers like Anthropic include it in the response)
    has_synopsis = "clinical synopsis" in cleaned_soap.lower()

    # Only generate/append synopsis if not already present
    if not has_synopsis:
        # Check if synopsis generation is enabled through agent manager
        try:
            from managers.agent_manager import agent_manager

            # Use agent manager to generate synopsis
            synopsis = agent_manager.generate_synopsis(cleaned_soap, context)

            if synopsis:
                # Append synopsis to SOAP note (without decoration to match AI format)
                synopsis_section = f"\n\nClinical Synopsis:\n- {synopsis}"
                cleaned_soap += synopsis_section
                # Also stream the synopsis if callback provided
                if on_chunk:
                    on_chunk(synopsis_section)
                logging.info("Added synopsis to SOAP note")
            else:
                from ai.agents.models import AgentType
                if not agent_manager.is_agent_enabled(AgentType.SYNOPSIS):
                    logging.info("Synopsis generation is disabled")
                else:
                    logging.warning("Synopsis generation failed")

        except Exception as e:
            logging.error(f"Error with synopsis generation: {e}")
    else:
        logging.info("AI already generated Clinical Synopsis, skipping agent synopsis")

    return cleaned_soap


def create_soap_note_with_openai(text: str, context: str = "") -> str:
    from datetime import datetime

    # We don't need to check the provider here since call_ai will handle it
    # Just pass the model name based on the type of note we're creating
    model = SETTINGS["soap_note"]["model"]  # Use actual settings, not defaults

    # Get ICD code version from settings (default to ICD-9 for backwards compatibility)
    icd_version = SETTINGS.get("soap_note", {}).get("icd_code_version", "ICD-9")

    # Get current AI provider for provider-specific prompt
    current_provider = SETTINGS.get("ai_provider", "openai")

    # Get dynamic system message based on ICD code preference and provider
    system_message = get_soap_system_message(icd_version, provider=current_provider)

    # Check for per-provider custom system message first
    provider_message_key = f"{current_provider}_system_message"
    custom_message = SETTINGS.get("soap_note", {}).get(provider_message_key, "")

    # Fall back to legacy single system_message if provider-specific is empty
    if not custom_message or not custom_message.strip():
        custom_message = SETTINGS.get("soap_note", {}).get("system_message", "")

    # Use custom message if provided, otherwise keep dynamic default
    if custom_message and custom_message.strip():
        system_message = custom_message

    # Get temperature from settings (default 0.4 for consistent output)
    temperature = SETTINGS.get("soap_note", {}).get("temperature", 0.4)

    # Get current time and date in the specified format
    current_datetime = datetime.now()
    time_date_str = current_datetime.strftime("Time %H:%M Date %d %b %Y")

    # Build the transcript with time/date prepended
    transcript_with_datetime = f"{time_date_str}\n\n{text}"

    # If context is provided, prepend it to the prompt
    if context and context.strip():
        full_prompt = f"Previous medical context:\n{context}\n\n{SOAP_PROMPT_TEMPLATE.format(text=transcript_with_datetime)}"
    else:
        full_prompt = SOAP_PROMPT_TEMPLATE.format(text=transcript_with_datetime)

    result = call_ai(model, system_message, full_prompt, temperature)

    # Trace logging for SOAP formatting (INFO level to appear in logs)
    logging.info(f"SOAP raw AI response: {len(result)} chars, {result.count(chr(10))} newlines")
    # Log first 200 chars to see structure (repr shows actual newlines as \n)
    logging.info(f"SOAP raw preview: {repr(result[:200])}")

    # Clean both markdown and citations, then format paragraphs
    cleaned_soap = clean_text(result)
    logging.info(f"SOAP after clean_text: {len(cleaned_soap)} chars, {cleaned_soap.count(chr(10))} newlines")

    cleaned_soap = format_soap_paragraphs(cleaned_soap)

    # Count blank lines (consecutive newlines) to verify formatting
    blank_line_count = cleaned_soap.count('\n\n')
    logging.info(f"SOAP after format_soap_paragraphs: {len(cleaned_soap)} chars, {cleaned_soap.count(chr(10))} newlines, {blank_line_count} blank lines")
    logging.info(f"SOAP final preview: {repr(cleaned_soap[:200])}")

    # Check if the AI already generated a Clinical Synopsis section
    # (Some providers like Anthropic include it in the response)
    has_synopsis = "clinical synopsis" in cleaned_soap.lower()

    # Only generate/append synopsis if not already present
    if not has_synopsis:
        # Check if synopsis generation is enabled through agent manager
        try:
            from managers.agent_manager import agent_manager

            # Use agent manager to generate synopsis
            synopsis = agent_manager.generate_synopsis(cleaned_soap, context)

            if synopsis:
                # Append synopsis to SOAP note (without decoration to match AI format)
                synopsis_section = f"\n\nClinical Synopsis:\n- {synopsis}"
                cleaned_soap += synopsis_section
                logging.info("Added synopsis to SOAP note")
            else:
                # Check if it's due to being disabled or an error
                from ai.agents.models import AgentType
                if not agent_manager.is_agent_enabled(AgentType.SYNOPSIS):
                    logging.info("Synopsis generation is disabled")
                else:
                    logging.warning("Synopsis generation failed")

        except Exception as e:
            logging.error(f"Error with synopsis generation: {e}")
            # Continue without synopsis if there's an error
    else:
        logging.info("AI already generated Clinical Synopsis, skipping agent synopsis")
    
    return cleaned_soap

def create_referral_with_openai(text: str, conditions: str = "") -> str:
    model = SETTINGS["referral"]["model"]  # Use actual settings, not defaults
    
    # Add conditions to the prompt if provided
    if conditions:
        new_prompt = f"Write a referral paragraph using the following SOAP Note, focusing specifically on these conditions: {conditions}\n\nSOAP Note:\n{text}"
        logging.info(f"Creating referral with focus on conditions: {conditions}")
    else:
        new_prompt = "Write a referral paragraph using the SOAP Note given to you\n\n" + text
        logging.info("Creating referral with no specific focus conditions")
    
    # Add a shorter timeout and increase max tokens slightly
    try:
        result = call_ai(
            model, 
            "You are a physician writing referral letters to other physicians. Be concise but thorough.", 
            new_prompt, 
            0.7
        )
        return clean_text(result, remove_citations=False)
    except Exception as e:
        logging.error(f"Error creating referral: {str(e)}")
        title, message = get_error_message("UNKNOWN_ERROR", f"Failed to create referral: {str(e)}")
        return f"[Error: {title}] {message}"

# Helper function to determine which model key to use based on the task
def get_model_key_for_task(system_message: str, prompt: str) -> str:
    if "SOAP" in system_message or "SOAP" in prompt:
        return "soap_note"
    elif "refine" in system_message.lower() or "refine" in prompt.lower():
        return "refine_text"
    elif "improve" in system_message.lower() or "improve" in prompt.lower():
        return "improve_text"
    elif "referral" in system_message.lower() or "referral" in prompt.lower():
        return "referral"
    elif "medication" in system_message.lower() or "medication" in prompt.lower() or "drug" in system_message.lower() or "drug" in prompt.lower():
        return "medication"
    return "improve_text"  # Default fallback - use improve_text which has valid model

# NEW FUNCTIONS: Add these to the end of the ai.py file

def get_possible_conditions(text: str) -> str:
    """Extract possible medical conditions from text for referrals.
    
    Args:
        text: Source text to analyze
        
    Returns:
        Comma-separated string of medical conditions
    """
    prompt = ("Extract up to a maximun of 5 relevant medical conditions for a referral from the following text. "
              "Keep the condition names simple and specific and not longer that 3 words. "
              "Return them as a comma-separated list. Text: " + text)
    result = call_ai("gpt-4", "You are a physician specialized in referrals.", prompt, 0.7)
    # Clean both markdown and citations
    return clean_text(result)

def _get_recipient_guidance(recipient_type: str) -> dict:
    """Get recipient-specific guidance for letter generation.

    Args:
        recipient_type: Type of letter recipient

    Returns:
        Dictionary with 'focus', 'exclude', 'tone', and 'format' guidance
    """
    guidance = {
        "insurance": {
            "focus": [
                "Medical necessity and justification",
                "Diagnosis codes and clinical findings supporting the request",
                "Treatment history and failed alternatives",
                "Expected outcomes and prognosis",
                "Specific procedure/medication/service being requested"
            ],
            "exclude": [
                "Unrelated medical conditions not pertinent to the claim",
                "Personal or social history unless directly relevant",
                "Detailed examination findings unrelated to the request"
            ],
            "tone": "Formal, factual, and medically precise",
            "format": "Include patient identifiers, policy/claim numbers if known, clear request statement"
        },
        "employer": {
            "focus": [
                "Fitness for duty assessment",
                "Work restrictions or accommodations needed",
                "Expected duration of restrictions",
                "Specific job duties that can/cannot be performed"
            ],
            "exclude": [
                "Detailed diagnosis information (use general terms)",
                "Specific medications or treatments",
                "Unrelated medical conditions",
                "Sensitive mental health details unless directly relevant to work capacity"
            ],
            "tone": "Professional, concise, focused on functional capacity",
            "format": "Brief, clear statements about work ability without excessive medical detail"
        },
        "specialist": {
            "focus": [
                "Reason for referral and clinical question",
                "Relevant history and examination findings",
                "Current medications relevant to the referral",
                "Specific concerns or questions for the specialist"
            ],
            "exclude": [
                "Unrelated medical conditions",
                "Medications not relevant to the referral reason",
                "Detailed social history unless relevant"
            ],
            "tone": "Professional colleague-to-colleague communication",
            "format": "Standard medical referral format with clear clinical question"
        },
        "patient": {
            "focus": [
                "Clear explanation of diagnosis in lay terms",
                "Treatment plan and instructions",
                "Follow-up requirements",
                "Warning signs to watch for"
            ],
            "exclude": [
                "Complex medical jargon",
                "Information that might cause unnecessary anxiety",
                "Details meant for other healthcare providers"
            ],
            "tone": "Warm, clear, educational, reassuring",
            "format": "Easy to read, use bullet points for instructions, avoid medical abbreviations"
        },
        "school": {
            "focus": [
                "Attendance or participation limitations",
                "Accommodations needed for learning",
                "Duration of restrictions",
                "Activity limitations (PE, etc.)"
            ],
            "exclude": [
                "Detailed diagnosis information",
                "Medication names and dosages",
                "Sensitive health information",
                "Information beyond what school needs to know"
            ],
            "tone": "Professional, brief, focused on educational needs",
            "format": "Concise statement of limitations and accommodations without medical details"
        },
        "legal": {
            "focus": [
                "Objective clinical findings",
                "Causation opinions if requested",
                "Functional limitations and prognosis",
                "Timeline of treatment",
                "Medical records summary"
            ],
            "exclude": [
                "Speculation beyond medical expertise",
                "Legal conclusions",
                "Information not supported by medical evidence"
            ],
            "tone": "Objective, factual, defensible, precise",
            "format": "Formal medical-legal format with clear opinions stated as such"
        },
        "government": {
            "focus": [
                "Functional limitations affecting daily activities",
                "Duration and permanence of condition",
                "Treatment history and response",
                "Objective findings supporting disability claim"
            ],
            "exclude": [
                "Subjective complaints not supported by findings",
                "Information beyond the specific request",
                "Speculation about eligibility"
            ],
            "tone": "Formal, objective, thorough documentation",
            "format": "Follow agency-specific requirements if known, detailed functional assessment"
        },
        "other": {
            "focus": ["Information relevant to the stated purpose"],
            "exclude": ["Unnecessary medical details"],
            "tone": "Professional and appropriate to context",
            "format": "Standard professional letter format"
        }
    }
    return guidance.get(recipient_type, guidance["other"])


def _build_letter_prompt(text: str, recipient_type: str = "other", specs: str = "") -> str:
    """Build the prompt for letter generation with recipient-specific guidance.

    Args:
        text: Content to base the letter on
        recipient_type: Type of recipient (insurance, employer, specialist, etc.)
        specs: Additional special instructions for letter formatting/content

    Returns:
        Complete prompt for AI
    """
    guidance = _get_recipient_guidance(recipient_type)

    # Recipient type display names
    recipient_names = {
        "insurance": "an Insurance Company",
        "employer": "an Employer/Workplace",
        "specialist": "a Specialist Colleague",
        "patient": "the Patient",
        "school": "a School/Educational Institution",
        "legal": "Legal Counsel/Attorney",
        "government": "a Government Agency",
        "other": "the specified recipient"
    }
    recipient_display = recipient_names.get(recipient_type, "the recipient")

    prompt_parts = []

    prompt_parts.append(f"Create a professional medical letter addressed to {recipient_display}.")
    prompt_parts.append("")

    # Critical filtering instructions
    prompt_parts.append("**CRITICAL INSTRUCTION - CONTENT FOCUS:**")
    prompt_parts.append(f"This letter is specifically for {recipient_display}.")
    prompt_parts.append("")

    prompt_parts.append("INCLUDE in the letter:")
    for item in guidance["focus"]:
        prompt_parts.append(f"- {item}")
    prompt_parts.append("")

    prompt_parts.append("EXCLUDE from the letter (DO NOT include):")
    for item in guidance["exclude"]:
        prompt_parts.append(f"- {item}")
    prompt_parts.append("")

    prompt_parts.append(f"TONE: {guidance['tone']}")
    prompt_parts.append(f"FORMAT: {guidance['format']}")
    prompt_parts.append("")

    if specs.strip():
        prompt_parts.append(f"ADDITIONAL INSTRUCTIONS: {specs}")
        prompt_parts.append("")

    prompt_parts.append("Clinical Information (extract ONLY relevant details for this recipient):")
    prompt_parts.append(text)
    prompt_parts.append("")

    prompt_parts.append("Generate the letter with proper formatting including date, recipient address, greeting, body, closing, and signature line.")

    return "\n".join(prompt_parts)


def _get_letter_system_message(recipient_type: str = "other") -> str:
    """Get the system message for letter generation based on recipient type.

    Args:
        recipient_type: Type of recipient

    Returns:
        System message for letter AI
    """
    base_message = """You are an expert medical professional specializing in writing professional medical letters.

CRITICAL RULE - RECIPIENT-FOCUSED CONTENT:
When writing letters, you MUST tailor the content specifically to the recipient type:
- ONLY include information relevant and appropriate for that recipient
- EXCLUDE sensitive details that the recipient does not need to know
- Use appropriate medical terminology (technical for colleagues, lay terms for patients/employers)
- Follow privacy principles - share minimum necessary information

"""

    recipient_specific = {
        "insurance": """For INSURANCE letters:
- Focus on medical necessity and justification
- Include diagnosis codes and supporting clinical evidence
- Document failed alternatives and treatment history
- Be factual and precise - insurers need clear medical justification
- Do NOT include unrelated conditions or excessive clinical detail""",

        "employer": """For EMPLOYER letters:
- Focus on functional capacity and work restrictions
- Use general terms, NOT specific diagnoses (e.g., "medical condition" not "depression")
- State what the patient CAN and CANNOT do at work
- Include duration of restrictions
- Do NOT disclose sensitive diagnoses, medications, or detailed medical information""",

        "specialist": """For SPECIALIST/COLLEAGUE letters:
- Focus only on conditions relevant to the referral
- Include pertinent clinical findings and current relevant medications
- State your specific clinical question
- Do NOT include unrelated medical conditions or medications""",

        "patient": """For PATIENT letters:
- Use clear, simple language without medical jargon
- Explain diagnoses and treatments in understandable terms
- Include actionable instructions and follow-up plans
- Be reassuring while conveying important information""",

        "school": """For SCHOOL letters:
- Focus ONLY on educational impact and accommodations needed
- Do NOT disclose specific diagnoses or treatments
- State functional limitations relevant to school activities
- Keep it brief and focused on what the school needs to know""",

        "legal": """For LEGAL letters:
- Be objective and factual - opinions must be clearly stated as such
- Document findings and causation if requested
- Provide thorough timeline and treatment summary
- Avoid speculation beyond medical expertise""",

        "government": """For GOVERNMENT/DISABILITY letters:
- Focus on functional limitations affecting daily activities
- Document objective findings supporting the claim
- Include treatment history and response
- Be thorough but stick to documented medical evidence"""
    }

    specific = recipient_specific.get(recipient_type, "Tailor content appropriately for the specified recipient.")

    return base_message + specific


def create_letter_with_ai(text: str, recipient_type: str = "other", specs: str = "") -> str:
    """Generate a professional medical letter based on provided text, recipient type, and specifications.

    Args:
        text: Content to base the letter on
        recipient_type: Type of recipient (insurance, employer, specialist, patient, school, legal, government, other)
        specs: Additional special instructions for letter formatting/content

    Returns:
        Complete formatted letter
    """
    # Build the prompt with recipient-specific guidance
    prompt = _build_letter_prompt(text, recipient_type, specs)

    # Get recipient-specific system message
    system_message = _get_letter_system_message(recipient_type)

    # Make the AI call
    result = call_ai("gpt-4o", system_message, prompt, 0.7)

    # Clean up any markdown formatting and citations from the result
    return clean_text(result)


def create_letter_streaming(
    text: str,
    recipient_type: str = "other",
    specs: str = "",
    on_chunk: Callable[[str], None] = None
) -> str:
    """Generate a professional medical letter with streaming display.

    Displays response progressively instead of waiting for complete response.
    Provides better user feedback during long generation operations.

    Args:
        text: Content to base the letter on
        recipient_type: Type of recipient (insurance, employer, specialist, patient, school, legal, government, other)
        specs: Additional special instructions for letter formatting/content
        on_chunk: Callback function called with each text chunk for progressive display

    Returns:
        Complete formatted letter
    """
    # Build the prompt with recipient-specific guidance
    prompt = _build_letter_prompt(text, recipient_type, specs)

    # Get recipient-specific system message
    system_message = _get_letter_system_message(recipient_type)

    # Use streaming API call
    if on_chunk:
        result = call_ai_streaming("gpt-4o", system_message, prompt, 0.7, on_chunk)
    else:
        # Fall back to non-streaming if no callback provided
        result = call_ai("gpt-4o", system_message, prompt, 0.7)

    # Clean up any markdown formatting and citations from the result
    return clean_text(result)

def call_ai(model: str, system_message: str, prompt: str, temperature: float,
            provider: str = None) -> str:
    """
    Route API calls to the appropriate provider based on the selected AI provider in settings

    Args:
        model: Model to use (may be overridden by provider-specific settings)
        system_message: System message to guide the AI's response
        prompt: Content to send to the model
        temperature: Temperature parameter to control randomness (may be overridden by settings)
        provider: Optional override for AI provider (if None, uses global ai_provider setting)

    Returns:
        AI-generated response as a string
    """
    # Save prompt to debug file (only in debug mode to protect PHI/PII)
    # SECURITY: This logs medical data - only enable for development debugging
    from settings.settings import SETTINGS
    if SETTINGS.get("enable_llm_debug_logging", False):
        try:
            from datetime import datetime
            from managers.data_folder_manager import data_folder_manager
            from utils.validation import sanitize_for_logging

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
            logging.debug(f"Saved sanitized LLM prompt to: {debug_file_path}")
        except Exception as e:
            logging.debug(f"Failed to save prompt to debug file: {e}")
    
    # Reload settings from file to ensure we have the latest provider selection
    from settings.settings import load_settings
    current_settings = load_settings()

    # Validate provider against allowed list to prevent arbitrary key access
    VALID_PROVIDERS = {PROVIDER_OPENAI, PROVIDER_OLLAMA, PROVIDER_ANTHROPIC, PROVIDER_GEMINI}

    # Track if provider was explicitly passed (affects model selection)
    provider_explicitly_set = provider is not None and provider != ""

    # Use passed-in provider if specified, otherwise use global setting
    if not provider_explicitly_set:
        provider = current_settings.get("ai_provider", "openai")

    if provider not in VALID_PROVIDERS:
        logging.warning(f"Invalid AI provider '{provider}', falling back to OpenAI")
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

    # Handle different providers and get appropriate model
    # When provider is explicitly set, use the passed-in model; otherwise look it up from settings
    if provider == PROVIDER_OLLAMA:
        logging.info(f"Using provider: Ollama for task: {model_key}")
        # Debug logging will happen in the actual API call
        return call_ollama(system_message, prompt, temperature)
    elif provider == PROVIDER_ANTHROPIC:
        if provider_explicitly_set and model:
            actual_model = model
        else:
            actual_model = current_settings.get(model_key, {}).get("anthropic_model", "claude-sonnet-4-20250514")
        logging.info(f"Using provider: Anthropic with model: {actual_model}")
        # Debug logging will happen in the actual API call
        return call_anthropic(actual_model, system_message, prompt, temperature)
    elif provider == PROVIDER_GEMINI:
        if provider_explicitly_set and model:
            actual_model = model
        else:
            actual_model = current_settings.get(model_key, {}).get("gemini_model", "gemini-1.5-flash")
        logging.info(f"Using provider: Gemini with model: {actual_model}")
        # Debug logging will happen in the actual API call
        return call_gemini(actual_model, system_message, prompt, temperature)
    else:  # OpenAI is the default
        if provider_explicitly_set and model:
            actual_model = model
        else:
            actual_model = current_settings.get(model_key, {}).get("model", model)
        logging.info(f"Using provider: OpenAI with model: {actual_model}")
        # Debug logging will happen in the actual API call
        return call_openai(actual_model, system_message, prompt, temperature)
