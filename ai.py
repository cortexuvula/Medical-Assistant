import openai
import logging
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

def adjust_text_with_openai(text: str) -> str:
    model = SETTINGS.get("refine_text", {}).get("model", _DEFAULT_SETTINGS["refine_text"]["model"])
    full_prompt = f"{REFINE_PROMPT}\n\nOriginal: {text}\n\nCorrected:"
    return call_openai(model, REFINE_SYSTEM_MESSAGE, full_prompt, OPENAI_TEMPERATURE_REFINEMENT, OPENAI_MAX_TOKENS_REFINEMENT)

def improve_text_with_openai(text: str) -> str:
    model = SETTINGS.get("improve_text", {}).get("model", _DEFAULT_SETTINGS["improve_text"]["model"])
    full_prompt = f"{IMPROVE_PROMPT}\n\nOriginal: {text}\n\nImproved:"
    return call_openai(model, IMPROVE_SYSTEM_MESSAGE, full_prompt, OPENAI_TEMPERATURE_IMPROVEMENT, OPENAI_MAX_TOKENS_IMPROVEMENT)

def create_soap_note_with_openai(text: str) -> str:
    full_prompt = SOAP_PROMPT_TEMPLATE.format(text=text)
    # Assuming "gpt-4o" is the intended model for SOAP note generation
    return call_openai("gpt-4o", SOAP_SYSTEM_MESSAGE, full_prompt, 0.7, 4000)
