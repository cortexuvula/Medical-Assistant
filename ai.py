import openai
import os
import logging
import re
import requests
import json
from openai import OpenAI  
from prompts import (
    REFINE_PROMPT, REFINE_SYSTEM_MESSAGE,
    IMPROVE_PROMPT, IMPROVE_SYSTEM_MESSAGE,
    SOAP_PROMPT_TEMPLATE, SOAP_SYSTEM_MESSAGE
)
from settings import SETTINGS, _DEFAULT_SETTINGS
from error_codes import get_error_message, format_api_error
from validation import validate_api_key, sanitize_prompt, validate_model_name
from exceptions import APIError, RateLimitError, AuthenticationError, ServiceUnavailableError
from resilience import resilient_api_call
from security import get_security_manager
from security_decorators import secure_api_call, rate_limited


def log_api_call_debug(provider: str, model: str, temperature: float, system_message: str, prompt: str):
    """Consolidated debug logging for API calls to reduce repetition."""
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.debug(f"\n===== {provider.upper()} API CALL =====")
        logging.debug(f"Model: {model}, Temperature: {temperature}")
        logging.debug(f"System: {system_message[:100]}..." if len(system_message) > 100 else f"System: {system_message}")
        logging.debug(f"Prompt: {prompt[:100]}..." if len(prompt) > 100 else f"Prompt: {prompt}")
        logging.debug("="*40)

@secure_api_call("openai")
@resilient_api_call(
    max_retries=3,
    initial_delay=1.0,
    backoff_factor=2.0,
    failure_threshold=5,
    recovery_timeout=60
)
def _openai_api_call(model: str, messages: list, temperature: float):
    """Make the actual API call to OpenAI.
    
    Args:
        model: Model name
        messages: List of messages
        temperature: Temperature setting
        
    Returns:
        API response
        
    Raises:
        APIError: On API failures
    """
    try:
        response = openai.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        return response
    except Exception as e:
        error_msg = str(e)
        if "rate limit" in error_msg.lower():
            raise RateLimitError(f"OpenAI rate limit exceeded: {error_msg}")
        elif "authentication" in error_msg.lower() or "invalid api key" in error_msg.lower():
            raise AuthenticationError(f"OpenAI authentication failed: {error_msg}")
        elif "timeout" in error_msg.lower():
            raise ServiceUnavailableError(f"OpenAI request timeout: {error_msg}")
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
    except (APIError, ServiceUnavailableError) as e:
        logging.error(f"OpenAI API error with model {model}: {str(e)}")
        error_code, details = format_api_error("openai", e)
        title, message = get_error_message(error_code, details, model)
        # Return error message that includes troubleshooting hints
        return f"[Error: {title}] {message}\n\nOriginal text: {prompt[:100]}..."
    except Exception as e:
        logging.error(f"Unexpected error calling OpenAI: {str(e)}")
        title, message = get_error_message("API_UNEXPECTED_ERROR", str(e))
        return f"[Error: {title}] {message}\n\nOriginal text: {prompt[:100]}..."

@secure_api_call("perplexity")
@resilient_api_call(
    max_retries=3,
    initial_delay=1.0,
    backoff_factor=2.0,
    failure_threshold=5,
    recovery_timeout=60
)
def _perplexity_api_call(client, model: str, messages: list, temperature: float):
    """Make the actual API call to Perplexity.
    
    Args:
        client: OpenAI client configured for Perplexity
        model: Model name
        messages: List of messages
        temperature: Temperature setting
        
    Returns:
        API response
        
    Raises:
        APIError: On API failures
    """
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        return response
    except Exception as e:
        error_msg = str(e)
        if "rate limit" in error_msg.lower():
            raise RateLimitError(f"Perplexity rate limit exceeded: {error_msg}")
        elif "authentication" in error_msg.lower() or "invalid api key" in error_msg.lower():
            raise AuthenticationError(f"Perplexity authentication failed: {error_msg}")
        elif "timeout" in error_msg.lower():
            raise ServiceUnavailableError(f"Perplexity request timeout: {error_msg}")
        else:
            raise APIError(f"Perplexity API error: {error_msg}")

def call_perplexity(system_message: str, prompt: str, temperature: float) -> str:
    
    # Get security manager
    security_manager = get_security_manager()
    
    # Get API key from secure storage or environment
    api_key = security_manager.get_api_key("perplexity")
    if not api_key:
        logging.error("Perplexity API key not provided")
        title, message = get_error_message("API_KEY_MISSING", "Perplexity API key not found")
        return f"[Error: {title}] {message}\n\nOriginal text: {prompt[:100]}..."
    
    # Validate API key format
    is_valid, error = validate_api_key("perplexity", api_key)
    if not is_valid:
        logging.error(f"Invalid Perplexity API key: {error}")
        title, message = get_error_message("API_KEY_INVALID", error)
        return f"[Error: {title}] {message}\n\nOriginal text: {prompt[:100]}..."
    
    # Enhanced sanitization
    prompt = security_manager.sanitize_input(prompt, "prompt")
    system_message = security_manager.sanitize_input(system_message, "prompt")
    client = OpenAI(api_key=api_key, base_url="https://api.perplexity.ai")
    
    # Get model from the appropriate settings based on the task
    model_key = get_model_key_for_task(system_message, prompt)
    model = SETTINGS.get(model_key, {}).get("perplexity_model", "sonar-medium-chat")
    logging.info(f"Making Perplexity API call with model: {model}")
    
    # Use consolidated debug logging
    log_api_call_debug("Perplexity", model, temperature, system_message, prompt)
    
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": prompt}
    ]
    try:
        response = _perplexity_api_call(client, model, messages, temperature)
        result = response.choices[0].message.content.strip()
        # Remove text between <think> and </think>
        result = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL).strip()
        return result
    except (APIError, ServiceUnavailableError) as e:
        logging.error(f"Perplexity API error with model {model}: {str(e)}")
        error_code, details = format_api_error("perplexity", e)
        title, message = get_error_message(error_code, details, model)
        return f"[Error: {title}] {message}\n\nOriginal text: {prompt[:100]}..."
    except Exception as e:
        logging.error(f"Perplexity API error with model {model}: {str(e)}")
        error_code, details = format_api_error("perplexity", e)
        title, message = get_error_message(error_code, details, model)
        return f"[Error: {title}] {message}\n\nOriginal text: {prompt[:100]}..."

def call_ollama(system_message: str, prompt: str, temperature: float) -> str:
    import requests
    import json
    import time
    
    # Sanitize inputs first
    prompt = sanitize_prompt(prompt)
    system_message = sanitize_prompt(system_message)
    
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
                health_check = requests.get(f"{base_url}/api/version", timeout=5)
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
            response = requests.post(
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
    import requests
    import json
    
    ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
    base_url = ollama_url.rstrip("/")
    
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
        response = requests.post(
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

def call_grok(model: str, system_message: str, prompt: str, temperature: float) -> str:
    api_key = os.getenv("GROK_API_KEY")
    if not api_key:
        logging.error("Grok API key not provided")
        title, message = get_error_message("API_KEY_MISSING", "Grok API key not found")
        return f"[Error: {title}] {message}\n\nOriginal text: {prompt[:100]}..."
    
    # Validate API key and inputs
    is_valid, error = validate_api_key("grok", api_key)
    if not is_valid:
        logging.error(f"Invalid Grok API key: {error}")
        title, message = get_error_message("API_KEY_INVALID", error)
        return f"[Error: {title}] {message}\n\nOriginal text: {prompt[:100]}..."
    
    # Sanitize inputs
    prompt = sanitize_prompt(prompt)
    system_message = sanitize_prompt(system_message)
    
    logging.info(f"Making Grok API call with model: {model}")
    
    # Use consolidated debug logging
    log_api_call_debug("Grok", model, temperature, system_message, prompt)
    
    client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": prompt}
    ]
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Grok API error with model {model}: {str(e)}")
        error_code, details = format_api_error("grok", e)
        title, message = get_error_message(error_code, details, model)
        return f"[Error: {title}] {message}\n\nOriginal text: {prompt[:100]}..."

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

def create_soap_note_with_openai(text: str, context: str = "") -> str:
    from datetime import datetime
    
    # We don't need to check the provider here since call_ai will handle it
    # Just pass the model name based on the type of note we're creating
    model = SETTINGS["soap_note"]["model"]  # Use actual settings, not defaults
    
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
    
    result = call_ai(model, SOAP_SYSTEM_MESSAGE, full_prompt, 0.7)
    # Clean both markdown and citations
    return clean_text(result)

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
    return "refine_text"  # Default fallback

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

def _build_letter_prompt(text: str, specs: str = "") -> str:
    """Build the prompt for letter generation.
    
    Args:
        text: Content to base the letter on
        specs: Special instructions for letter formatting/content
        
    Returns:
        Complete prompt for AI
    """
    prompt = f"Create a professional letter based on the following text content:\n\n{text}\n\n"
    if specs.strip():
        prompt += f"Special instructions: {specs}\n\n"
    
    prompt += "Format the letter properly with date, recipient, greeting, body, closing, and signature."
    return prompt

def _get_letter_system_message() -> str:
    """Get the system message for letter generation.
    
    Returns:
        System message for letter AI
    """
    return ("You are an expert medical professional specializing in writing professional medical letters. "
            "Create well-formatted correspondence that is clear, concise, and appropriate for medical communication.")

def create_letter_with_ai(text: str, specs: str = "") -> str:
    """Generate a professional medical letter based on provided text and specifications.
    
    Args:
        text: Content to base the letter on
        specs: Special instructions for letter formatting/content
        
    Returns:
        Complete formatted letter
    """
    # Build the prompt
    prompt = _build_letter_prompt(text, specs)
    
    # Get system message
    system_message = _get_letter_system_message()
    
    # Use the currently selected AI provider
    
    # Make the AI call
    result = call_ai("gpt-4o", system_message, prompt, 0.7)
    
    # Clean up any markdown formatting and citations from the result
    return clean_text(result)

def call_ai(model: str, system_message: str, prompt: str, temperature: float) -> str:
    """
    Route API calls to the appropriate provider based on the selected AI provider in settings
    
    Args:
        model: Model to use (may be overridden by provider-specific settings)
        system_message: System message to guide the AI's response
        prompt: Content to send to the model
        temperature: Temperature parameter to control randomness (may be overridden by settings)
        
    Returns:
        AI-generated response as a string
    """
    # Save prompt to debug file
    try:
        from datetime import datetime
        from data_folder_manager import data_folder_manager
        debug_file_path = data_folder_manager.logs_folder / "last_llm_prompt.txt"
        with open(debug_file_path, 'w', encoding='utf-8') as f:
            f.write(f"=== LLM PROMPT DEBUG ===\n")
            f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Model: {model}\n")
            f.write(f"Temperature: {temperature}\n")
            f.write(f"\n--- SYSTEM MESSAGE ---\n")
            f.write(system_message)
            f.write(f"\n\n--- USER PROMPT ---\n")
            f.write(prompt)
            f.write(f"\n\n=== END OF PROMPT ===\n")
        logging.info(f"Saved LLM prompt to: {debug_file_path}")
    except Exception as e:
        logging.error(f"Failed to save prompt to debug file: {e}")
    
    # Reload settings from file to ensure we have the latest provider selection
    from settings import load_settings
    current_settings = load_settings()
    
    provider = current_settings.get("ai_provider", "openai")
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
    if provider == "perplexity":
        logging.info(f"Using provider: Perplexity for task: {model_key}")
        # Debug logging will happen in the actual API call
        return call_perplexity(system_message, prompt, temperature)
    elif provider == "grok":
        actual_model = current_settings.get(model_key, {}).get("grok_model", "grok-1")
        logging.info(f"Using provider: Grok with model: {actual_model}")
        # Debug logging will happen in the actual API call
        return call_grok(actual_model, system_message, prompt, temperature)
    elif provider == "ollama":
        logging.info(f"Using provider: Ollama for task: {model_key}")
        # Debug logging will happen in the actual API call
        return call_ollama(system_message, prompt, temperature)
    else:  # OpenAI is the default
        actual_model = current_settings.get(model_key, {}).get("model", model)
        logging.info(f"Using provider: OpenAI with model: {actual_model}")
        # Debug logging will happen in the actual API call
        return call_openai(actual_model, system_message, prompt, temperature)
