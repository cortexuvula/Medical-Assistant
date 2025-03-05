import openai
import os
import requests
import logging
import re  # NEW: Import re for regex manipulation
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

# Updated call_ai function with more detailed logging
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
    else:  # OpenAI is the default
        actual_model = SETTINGS.get(model_key, {}).get("model", model)
        logging.info(f"Using provider: OpenAI with model: {actual_model}")
        return call_openai(actual_model, system_message, prompt, temperature, max_tokens)

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

# NEW: Add Grok API call function
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
    model = SETTINGS.get("refine_text", {}).get("model", _DEFAULT_SETTINGS["refine_text"]["model"])
    full_prompt = f"{REFINE_PROMPT}\n\nOriginal: {text}\n\nCorrected:"
    return call_ai(model, REFINE_SYSTEM_MESSAGE, full_prompt, OPENAI_TEMPERATURE_REFINEMENT, OPENAI_MAX_TOKENS_REFINEMENT)

def improve_text_with_openai(text: str) -> str:
    model = SETTINGS.get("improve_text", {}).get("model", _DEFAULT_SETTINGS["improve_text"]["model"])
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
    full_prompt = SOAP_PROMPT_TEMPLATE.format(text=text)
    result = call_ai("gpt-4o", SOAP_SYSTEM_MESSAGE, full_prompt, 0.7, 4000)
    cleaned = remove_markdown(result)
    # Remove citation markers from the result
    cleaned = remove_citations(cleaned)
    return cleaned.strip()

def create_referral_with_openai(text: str, conditions: str = "") -> str:
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
            "gpt-4o", 
            "You are a physician writing referral letters to other physicians. Be concise but thorough.", 
            new_prompt, 
            0.7, 
            500  # Increased from 250 to give more space for the response
        )
        return remove_markdown(result)
    except Exception as e:
        logging.error(f"Error creating referral: {str(e)}")
        return f"Error creating referral: {str(e)}"

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
