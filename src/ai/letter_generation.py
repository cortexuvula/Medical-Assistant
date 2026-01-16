"""Letter Generation Module.

Provides functions for generating medical letters, referrals, and extracting conditions.
"""

import logging
from typing import Callable

from ai.providers.router import call_ai, call_ai_streaming
from ai.text_processing import clean_text
from settings.settings import SETTINGS


def create_referral_with_openai(text: str, conditions: str = "") -> str:
    """Create a referral letter using AI.

    Args:
        text: SOAP note or clinical text to base the referral on
        conditions: Optional specific conditions to focus on

    Returns:
        Referral paragraph text
    """
    from utils.error_codes import get_error_message

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
        # AIResult.text gives the text content; str(result) also works for backward compatibility
        return clean_text(result.text, remove_citations=False)
    except Exception as e:
        logging.error(f"Error creating referral: {str(e)}")
        title, message = get_error_message("UNKNOWN_ERROR", f"Failed to create referral: {str(e)}")
        return f"[Error: {title}] {message}"


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
    # Clean both markdown and citations; use result.text to get the text content
    return clean_text(result.text)


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
    # Use result.text to get the text content from AIResult
    return clean_text(result.text)


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
    # Use result.text to get the text content from AIResult
    return clean_text(result.text)
