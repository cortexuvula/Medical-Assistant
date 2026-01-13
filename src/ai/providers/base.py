"""Base utilities for AI providers.

Contains shared functions used across multiple provider implementations.
"""


def get_model_key_for_task(system_message: str, prompt: str) -> str:
    """Determine which model settings key to use based on the task.

    Analyzes the system message and prompt to determine the appropriate
    model configuration key from settings.

    Args:
        system_message: System message to guide the AI's response
        prompt: User prompt content

    Returns:
        Settings key for the appropriate model configuration
    """
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
