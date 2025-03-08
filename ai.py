import openai
import os
import requests
import logging
import re  
from prompts import (
    REFINE_PROMPT, REFINE_SYSTEM_MESSAGE,
    IMPROVE_PROMPT, IMPROVE_SYSTEM_MESSAGE,
    SOAP_PROMPT_TEMPLATE, SOAP_SYSTEM_MESSAGE
)
from settings import SETTINGS, _DEFAULT_SETTINGS

# Constants for OpenAI API calls
OPENAI_TEMPERATURE_REFINEMENT = 0.0
OPENAI_MAX_TOKENS_REFINEMENT = 4000
OPENAI_TEMPERATURE_IMPROVEMENT = 0.5
OPENAI_MAX_TOKENS_IMPROVEMENT = 4000

def call_openai(model: str, system_message: str, prompt: str, temperature: float, max_tokens: int) -> str:
    try:
        logging.info(f"Making OpenAI API call with model: {model}")
        response = openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI API error with model {model}: {str(e)}")
        return prompt

def call_perplexity(system_message: str, prompt: str, temperature: float, max_tokens: int) -> str:
    from openai import OpenAI
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        logging.error("Perplexity API key not provided")
        return prompt
    client = OpenAI(api_key=api_key, base_url="https://api.perplexity.ai")
    
    # Get model from the appropriate settings based on the task
    model_key = get_model_key_for_task(system_message, prompt)
    model = SETTINGS.get(model_key, {}).get("perplexity_model", "sonar-medium-chat")
    logging.info(f"Making Perplexity API call with model: {model}")
    
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": prompt}
    ]
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
        )
        result = response.choices[0].message.content.strip()
        # Remove text between <think> and </think>
        result = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL).strip()
        return result
    except Exception as e:
        logging.error(f"Perplexity API error with model {model}: {str(e)}")
        return prompt

# NEW: Add Ollama API call function
def call_ollama(system_message: str, prompt: str, temperature: float, max_tokens: int) -> str:
    import requests
    import json
    import time
    
    # Get Ollama API URL from environment or use default
    ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
    base_url = ollama_url.rstrip("/")  # Remove trailing slash if present
    
    # Get model from settings based on the task
    model_key = get_model_key_for_task(system_message, prompt)
    model = SETTINGS.get(model_key, {}).get("ollama_model", "llama3")
    
    logging.info(f"Making Ollama API call with model: {model}")
    
    # Format the request payload for Ollama API
    # Use the 'generate' endpoint instead of 'chat' for more consistent responses
    # across different Ollama models
    payload = {
        "model": model,
        "prompt": f"<s>[INST] <<SYS>>\n{system_message}\n<</SYS>>\n\n{prompt}[/INST]",
        "temperature": temperature,
        "max_tokens": max_tokens,
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
                        return f"Error: Ollama service not available. Please check if Ollama is running at {ollama_url}"
                    time.sleep(2)  # Wait before next retry
                    continue
            except Exception as e:
                logging.error(f"Ollama service health check error: {str(e)}")
                if attempt == max_retries - 1:  # Last attempt
                    return f"Error: Cannot connect to Ollama service at {ollama_url}. Please check if Ollama is running."
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
                    return fallback_ollama_chat(model, system_message, prompt, temperature, max_tokens, timeout_values[attempt])
                    
            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse Ollama API response: {e}")
                logging.error(f"Raw response: {response.text[:500]}...")  # Log first 500 chars
                if attempt == max_retries - 1:  # Last attempt
                    # Try the fallback method
                    return fallback_ollama_chat(model, system_message, prompt, temperature, max_tokens, timeout_values[attempt])
                time.sleep(2)
                continue
                
        except requests.exceptions.Timeout:
            logging.error(f"Ollama API timeout with model {model} (attempt {attempt+1}/{max_retries})")
            if attempt == max_retries - 1:  # Last attempt
                return f"Error: The request to Ollama timed out after {timeout_values[attempt]} seconds. The model '{model}' might be too large or complex for the current setup."
            time.sleep(2)  # Wait before next retry
            continue
            
        except Exception as e:
            logging.error(f"Ollama API error with model {model}: {str(e)}")
            if attempt == max_retries - 1:  # Last attempt
                return f"Error connecting to Ollama: {str(e)}. Please check your connection and try again."
            time.sleep(2)  # Wait before next retry
            continue
    
    # If all retries failed
    return f"Error: Failed to get a response from Ollama after {max_retries} attempts. Please try again later or choose a different model."

def fallback_ollama_chat(model, system_message, prompt, temperature, max_tokens, timeout):
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
        "max_tokens": max_tokens,
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

def call_grok(model: str, system_message: str, prompt: str, temperature: float, max_tokens: int) -> str:
    from openai import OpenAI
    api_key = os.getenv("GROK_API_KEY")
    if not api_key:
        logging.error("Grok API key not provided")
        return prompt
    
    logging.info(f"Making Grok API call with model: {model}")
    
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
            max_tokens=max_tokens
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Grok API error with model {model}: {str(e)}")
        return prompt

def adjust_text_with_openai(text: str) -> str:
    provider = SETTINGS.get("ai_provider", "openai")
    if provider == "openai":
        model = SETTINGS.get("refine_text", {}).get("model", _DEFAULT_SETTINGS["refine_text"]["model"])
    elif provider == "perplexity":
        model = SETTINGS.get("refine_text", {}).get("perplexity_model", _DEFAULT_SETTINGS["refine_text"]["perplexity_model"])
    elif provider == "grok":
        model = SETTINGS.get("refine_text", {}).get("grok_model", _DEFAULT_SETTINGS["refine_text"]["grok_model"])
    elif provider == "ollama":
        model = SETTINGS.get("refine_text", {}).get("ollama_model", _DEFAULT_SETTINGS["refine_text"]["ollama_model"])
    else:
        model = _DEFAULT_SETTINGS["refine_text"]["model"]
    
    full_prompt = f"{REFINE_PROMPT}\n\nOriginal: {text}\n\nCorrected:"
    return call_ai(model, REFINE_SYSTEM_MESSAGE, full_prompt, OPENAI_TEMPERATURE_REFINEMENT, OPENAI_MAX_TOKENS_REFINEMENT)

def improve_text_with_openai(text: str) -> str:
    provider = SETTINGS.get("ai_provider", "openai")
    if provider == "openai":
        model = SETTINGS.get("improve_text", {}).get("model", _DEFAULT_SETTINGS["improve_text"]["model"])
    elif provider == "perplexity":
        model = SETTINGS.get("improve_text", {}).get("perplexity_model", _DEFAULT_SETTINGS["improve_text"]["perplexity_model"])
    elif provider == "grok":
        model = SETTINGS.get("improve_text", {}).get("grok_model", _DEFAULT_SETTINGS["improve_text"]["grok_model"])
    elif provider == "ollama":
        model = SETTINGS.get("improve_text", {}).get("ollama_model", _DEFAULT_SETTINGS["improve_text"]["ollama_model"])
    else:
        model = _DEFAULT_SETTINGS["improve_text"]["model"]
    
    full_prompt = f"{IMPROVE_PROMPT}\n\nOriginal: {text}\n\nImproved:"
    return call_ai(model, IMPROVE_SYSTEM_MESSAGE, full_prompt, OPENAI_TEMPERATURE_IMPROVEMENT, OPENAI_MAX_TOKENS_IMPROVEMENT)

# NEW: Helper function to remove markdown formatting from text
def remove_markdown(text: str) -> str:
    import re
    # Remove code blocks
    text = re.sub(r"```.+?```", "", text, flags=re.DOTALL)
    # Remove inline code
    text = re.sub(r"`(.+?)`", r"\1", text)
    # Remove markdown headings
    text = re.sub(r"^\s*#+\s*", "", text, flags=re.MULTILINE)
    # Remove bold and italic markers
    text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)
    text = re.sub(r"(\*|_)(.*?)\1", r"\2", text)
    return text.strip()

# New helper to remove citation markers like [1], [2] etc.
def remove_citations(text: str) -> str:
    return re.sub(r'(\[\d+\])+', '', text)

def create_soap_note_with_openai(text: str) -> str:
    provider = SETTINGS.get("ai_provider", "openai")
    if provider == "openai":
        model = SETTINGS.get("soap_note", {}).get("model", _DEFAULT_SETTINGS["soap_note"]["model"])
    elif provider == "perplexity":
        model = SETTINGS.get("soap_note", {}).get("perplexity_model", _DEFAULT_SETTINGS["soap_note"]["perplexity_model"])
    elif provider == "grok":
        model = SETTINGS.get("soap_note", {}).get("grok_model", _DEFAULT_SETTINGS["soap_note"]["grok_model"])
    elif provider == "ollama":
        model = SETTINGS.get("soap_note", {}).get("ollama_model", _DEFAULT_SETTINGS["soap_note"]["ollama_model"])
    else:
        model = _DEFAULT_SETTINGS["soap_note"]["model"]
    
    full_prompt = SOAP_PROMPT_TEMPLATE.format(text=text)
    result = call_ai(model, SOAP_SYSTEM_MESSAGE, full_prompt, 0.7, 4000)
    cleaned = remove_markdown(result)
    # Remove citation markers from the result
    cleaned = remove_citations(cleaned)
    return cleaned.strip()

def create_referral_with_openai(text: str, conditions: str = "") -> str:
    provider = SETTINGS.get("ai_provider", "openai")
    if provider == "openai":
        model = SETTINGS.get("referral", {}).get("model", _DEFAULT_SETTINGS["referral"]["model"])
    elif provider == "perplexity":
        model = SETTINGS.get("referral", {}).get("perplexity_model", _DEFAULT_SETTINGS["referral"]["perplexity_model"])
    elif provider == "grok":
        model = SETTINGS.get("referral", {}).get("grok_model", _DEFAULT_SETTINGS["referral"]["grok_model"])
    elif provider == "ollama":
        model = SETTINGS.get("referral", {}).get("ollama_model", _DEFAULT_SETTINGS["referral"]["ollama_model"])
    else:
        model = _DEFAULT_SETTINGS["referral"]["model"]
    
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
            0.7, 
            500  # Increased from 250 to give more space for the response
        )
        return remove_markdown(result)
    except Exception as e:
        logging.error(f"Error creating referral: {str(e)}")
        return f"Error creating referral: {str(e)}"

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
    result = call_ai("gpt-4", "You are a physician specialized in referrals.", prompt, 0.7, 100)
    conditions = remove_markdown(result).strip()
    conditions = remove_citations(conditions)
    return conditions

def create_letter_with_ai(text: str, specs: str = "") -> str:
    """Generate a professional medical letter based on provided text and specifications.
    
    Args:
        text: Content to base the letter on
        specs: Special instructions for letter formatting/content
        
    Returns:
        Complete formatted letter
    """
    # Create a prompt for the AI
    prompt = f"Create a professional letter based on the following text content:\n\n{text}\n\n"
    if specs.strip():
        prompt += f"Special instructions: {specs}\n\n"
    
    prompt += "Format the letter properly with date, recipient, greeting, body, closing, and signature."
    
    # Call the AI with the letter generation prompt
    system_message = "You are an expert medical professional specializing in writing professional medical letters. Create well-formatted correspondence that is clear, concise, and appropriate for medical communication."
    
    # Use the currently selected AI provider
    from settings import SETTINGS
    current_provider = SETTINGS.get("ai_provider", "openai")
    
    result = call_ai("gpt-4o", system_message, prompt, 0.7, 2000)
    
    # Clean up any markdown formatting from the result
    clean_result = remove_markdown(result)
    clean_result = remove_citations(clean_result)
    
    return clean_result

def call_ai(model: str, system_message: str, prompt: str, temperature: float, max_tokens: int) -> str:
    provider = SETTINGS.get("ai_provider", "openai")
    model_key = get_model_key_for_task(system_message, prompt)
    
    # Handle different providers and get appropriate model
    if provider == "perplexity":
        logging.info(f"Using provider: Perplexity for task: {model_key}")
        return call_perplexity(system_message, prompt, temperature, max_tokens)
    elif provider == "grok":
        actual_model = SETTINGS.get(model_key, {}).get("grok_model", "grok-1")
        logging.info(f"Using provider: Grok with model: {actual_model}")
        return call_grok(actual_model, system_message, prompt, temperature, max_tokens)
    elif provider == "ollama":
        logging.info(f"Using provider: Ollama for task: {model_key}")
        return call_ollama(system_message, prompt, temperature, max_tokens)
    else:  # OpenAI is the default
        actual_model = SETTINGS.get(model_key, {}).get("model", model)
        logging.info(f"Using provider: OpenAI with model: {actual_model}")
        return call_openai(actual_model, system_message, prompt, temperature, max_tokens)
