"""Text Processing Module.

Provides text cleaning, refining, and improvement functions.
"""

import re

from ai.providers.router import call_ai
from ai.prompts import (
    REFINE_PROMPT, REFINE_SYSTEM_MESSAGE,
    IMPROVE_PROMPT, IMPROVE_SYSTEM_MESSAGE
)
from settings.settings_manager import settings_manager


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


def adjust_text_with_openai(text: str) -> str:
    """Refine text using AI to correct grammar and improve clarity.

    Args:
        text: The text to refine

    Returns:
        Refined text
    """
    refine_config = settings_manager.get_model_config("refine_text")
    model = refine_config.get("model", "gpt-4")

    full_prompt = f"{REFINE_PROMPT}\n\nOriginal: {text}\n\nCorrected:"
    # Get temperature from settings or use a reasonable default
    temperature = refine_config.get("temperature", 0.0)
    return call_ai(model, REFINE_SYSTEM_MESSAGE, full_prompt, temperature)


def improve_text_with_openai(text: str) -> str:
    """Improve text using AI to enhance readability and style.

    Args:
        text: The text to improve

    Returns:
        Improved text
    """
    improve_config = settings_manager.get_model_config("improve_text")
    model = improve_config.get("model", "gpt-4")

    full_prompt = f"{IMPROVE_PROMPT}\n\nOriginal: {text}\n\nImproved:"
    # Get temperature from settings or use a reasonable default
    temperature = improve_config.get("temperature", 0.5)
    return call_ai(model, IMPROVE_SYSTEM_MESSAGE, full_prompt, temperature)
