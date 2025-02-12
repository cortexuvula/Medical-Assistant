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
        logging.error("OpenAI API error", exc_info=True)
        return prompt

# NEW: Updated function to call Perplexity API using OpenAI client with base_url set to https://api.perplexity.ai
def call_perplexity(system_message: str, prompt: str, temperature: float, max_tokens: int) -> str:
    from openai import OpenAI
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        logging.error("Perplexity API key not provided")
        return prompt
    client = OpenAI(api_key=api_key, base_url="https://api.perplexity.ai")
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": prompt}
    ]
    try:
        response = client.chat.completions.create(
            model="sonar-reasoning-pro",
            messages=messages,
        )
        result = response.choices[0].message.content.strip()
        # NEW: Remove text between <think> and </think>
        result = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL).strip()
        return result
    except Exception as e:
        logging.error("Perplexity API error: %s", e)
        return prompt

# NEW: Unified API call that uses provider setting
def call_ai(model: str, system_message: str, prompt: str, temperature: float, max_tokens: int) -> str:
    provider = SETTINGS.get("ai_provider", "openai")
    if provider == "perplexity":
        # Use default model for Perplexity API: sonar-reasoning-pro
        model = "sonar-reasoning-pro"
        return call_perplexity(system_message, prompt, temperature, max_tokens)
    else:
        return call_openai(model, system_message, prompt, temperature, max_tokens)

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

def create_soap_note_with_openai(text: str) -> str:
    full_prompt = SOAP_PROMPT_TEMPLATE.format(text=text)
    result = call_ai("gpt-4o", SOAP_SYSTEM_MESSAGE, full_prompt, 0.7, 4000)
    # NEW: Remove markdown formatting from the result
    return remove_markdown(result)

def create_referral_with_openai(text: str) -> str:
    new_prompt = "Write a referral paragraph using the SOAP Note given to you\n\n" + text
    result = call_ai("gpt-4o", "You are a physician writing referral letters to other physicians.", new_prompt, 0.7, 250)
    # NEW: Remove markdown formatting from the result
    return remove_markdown(result)
