"""SOAP Note Generation Module.

Provides functions for generating and formatting SOAP notes.
"""

import re
from typing import Callable

from utils.structured_logging import get_logger

logger = get_logger(__name__)

from ai.providers.router import call_ai, call_ai_streaming
from ai.text_processing import clean_text
from ai.prompts import SOAP_PROMPT_TEMPLATE, get_soap_system_message
from settings.settings_manager import settings_manager
from utils.constants import PROVIDER_OPENAI
from utils.validation import sanitize_prompt
from utils.icd_validator import extract_icd_codes, validate_code


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

    # Handle case where content follows header on the same line
    # e.g., "Subjective: - Chief complaint: ..." -> "Subjective:\n- Chief complaint: ..."
    for header in section_headers:
        pattern = rf'({re.escape(header)}:)\s*(- )'
        text = re.sub(pattern, r'\1\n\2', text, flags=re.IGNORECASE)

    # Split multiple bullet points concatenated on the same line
    # Only split " - " when followed by a capital letter (start of new item)
    text = re.sub(r' (- [A-Z])', r'\n\1', text)

    lines = text.split('\n')
    result_lines = []
    detected_headers = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        # Remove leading dash/bullet for header detection
        stripped_no_bullet = stripped.lstrip('-').lstrip('\u2022').lstrip('*').strip()
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

    logger.info(f"format_soap_paragraphs: {len(lines)} lines -> {len(result_lines)} lines, detected headers: {detected_headers}")
    return '\n'.join(result_lines)


def _prepare_soap_generation(text: str, context: str, settings: dict = None, emotion_context: str = "") -> tuple:
    """Prepare common parameters for SOAP note generation.

    Args:
        text: Transcript text to convert
        context: Optional medical context
        settings: Settings dict (uses settings_manager if None)
        emotion_context: Optional voice emotion analysis summary from Modulate STT

    Returns:
        Tuple of (model, system_message, full_prompt, temperature)
    """
    from datetime import datetime

    # Use provided settings or global
    if settings is None:
        settings = settings_manager.get_all()

    model = settings.get("soap_note", {}).get("model", "gpt-4")
    icd_version = settings.get("soap_note", {}).get("icd_code_version", "ICD-9")
    current_provider = settings.get("ai_provider", PROVIDER_OPENAI)

    # Sanitize inputs to prevent prompt injection via transcript content
    text = sanitize_prompt(text)
    if context:
        context = sanitize_prompt(context)

    # Get dynamic system message based on ICD code preference and provider
    system_message = get_soap_system_message(icd_version, provider=current_provider)

    # Check for per-provider custom system message first
    provider_message_key = f"{current_provider}_system_message"
    custom_message = settings.get("soap_note", {}).get(provider_message_key, "")

    # Fall back to legacy single system_message if provider-specific is empty
    if not custom_message or not custom_message.strip():
        custom_message = settings.get("soap_note", {}).get("system_message", "")

    # Use custom message if provided, otherwise keep dynamic default
    if custom_message and custom_message.strip():
        system_message = custom_message

    temperature = settings.get("soap_note", {}).get("temperature", 0.4)

    # Build time/date string
    time_date_str = datetime.now().strftime("Time %H:%M Date %d %b %Y")
    transcript_with_datetime = f"{time_date_str}\n\n{text}"

    # Build prompt with context and optional emotion data
    # Truncate context to prevent token overflow when combined with long transcripts
    max_context_length = 8000
    if context and len(context) > max_context_length:
        context = context[:max_context_length] + "...[truncated]"
        logger.info(f"Context truncated to {max_context_length} chars for SOAP generation")

    parts = []
    if context and context.strip():
        parts.append(f"Previous medical context:\n{context}")
    if emotion_context and emotion_context.strip():
        parts.append(f"Voice Emotional Analysis:\n{emotion_context}")
    parts.append(SOAP_PROMPT_TEMPLATE.format(text=transcript_with_datetime))
    full_prompt = "\n\n".join(parts)

    return model, system_message, full_prompt, temperature


def _postprocess_soap_result(result: str, context: str, on_chunk: Callable[[str], None] = None) -> str:
    """Post-process SOAP note result: clean, format, and add synopsis.

    Args:
        result: Raw AI response
        context: Medical context for synopsis generation
        on_chunk: Optional callback for streaming synopsis

    Returns:
        Cleaned and formatted SOAP note
    """
    # Trace logging for SOAP formatting
    logger.info(f"SOAP raw AI response: {len(result)} chars, {result.count(chr(10))} newlines")
    logger.info(f"SOAP raw preview: {repr(result[:200])}")

    # Clean both markdown and citations, then format paragraphs
    cleaned_soap = clean_text(result)
    logger.info(f"SOAP after clean_text: {len(cleaned_soap)} chars, {cleaned_soap.count(chr(10))} newlines")

    cleaned_soap = format_soap_paragraphs(cleaned_soap)

    # Count blank lines to verify formatting
    blank_line_count = cleaned_soap.count('\n\n')
    logger.info(f"SOAP after format_soap_paragraphs: {len(cleaned_soap)} chars, {cleaned_soap.count(chr(10))} newlines, {blank_line_count} blank lines")
    logger.info(f"SOAP final preview: {repr(cleaned_soap[:200])}")

    # Check if the AI already generated a Clinical Synopsis section
    has_synopsis = "clinical synopsis" in cleaned_soap.lower()

    # Only generate/append synopsis if not already present
    if not has_synopsis:
        try:
            from managers.agent_manager import agent_manager

            synopsis = agent_manager.generate_synopsis(cleaned_soap, context)

            if synopsis:
                synopsis_section = f"\n\nClinical Synopsis:\n- {synopsis}"
                cleaned_soap += synopsis_section
                if on_chunk:
                    on_chunk(synopsis_section)
                logger.info("Added synopsis to SOAP note")
            else:
                from ai.agents.models import AgentType
                if not agent_manager.is_agent_enabled(AgentType.SYNOPSIS):
                    logger.info("Synopsis generation is disabled")
                else:
                    logger.error("Synopsis generation failed")
        except Exception as e:
            logger.error(f"Error with synopsis generation: {e}")
    else:
        logger.info("AI already generated Clinical Synopsis, skipping agent synopsis")

    return cleaned_soap


def _validate_soap_output(soap_text: str) -> tuple:
    """Validate clinical content in SOAP note and return warnings separately.

    Checks ICD codes against the static dictionary and flags invalid ones.
    This is a lightweight post-generation validation — it does NOT make
    additional AI calls.

    Args:
        soap_text: Completed SOAP note text

    Returns:
        Tuple of (soap_text unchanged, list of warning strings)
    """
    if not soap_text:
        return (soap_text, [])

    warnings = []

    # Validate ICD codes against static dictionary
    extracted_codes = extract_icd_codes(soap_text)
    for code in extracted_codes:
        result = validate_code(code)
        if not result.is_valid:
            warnings.append(
                f"ICD code '{code}': invalid format — {result.warning or 'does not match ICD-9 or ICD-10 pattern'}"
            )
        elif not result.description:
            # Valid format but not in common codes database
            warnings.append(
                f"ICD code '{code}': valid format but not in common codes database — please verify"
            )

    if warnings:
        logger.info(f"SOAP validation: {len(warnings)} warning(s) found")

    return (soap_text, warnings)


def create_soap_note_streaming(
    text: str,
    context: str = "",
    on_chunk: Callable[[str], None] = None,
    emotion_context: str = ""
) -> str:
    """Create a SOAP note with streaming display.

    Displays response progressively instead of waiting for complete response.
    Provides better user feedback during long generation operations.

    Args:
        text: Transcript text to convert to SOAP note
        context: Optional additional medical context
        on_chunk: Callback function called with each text chunk for progressive display
        emotion_context: Optional voice emotion analysis summary from Modulate STT

    Returns:
        Complete SOAP note text
    """
    # Reload settings to get latest
    current_settings = settings_manager.get_all()

    # Prepare generation parameters
    model, system_message, full_prompt, temperature = _prepare_soap_generation(
        text, context, settings=current_settings, emotion_context=emotion_context
    )

    # Use streaming API call
    if on_chunk:
        result = call_ai_streaming(model, system_message, full_prompt, temperature, on_chunk)
    else:
        # Fall back to non-streaming if no callback provided
        result = call_ai(model, system_message, full_prompt, temperature)

    # Extract text from AIResult for post-processing
    result_text = result.text if hasattr(result, 'text') else str(result)
    soap_text = _postprocess_soap_result(result_text, context, on_chunk)

    # Validate ICD codes (warnings returned separately, not appended to SOAP text)
    soap_text, icd_warnings = _validate_soap_output(soap_text)
    return soap_text, icd_warnings


def create_soap_note_with_openai(text: str, context: str = "", emotion_context: str = "") -> str:
    """Create a SOAP note using AI.

    Args:
        text: Transcript text to convert to SOAP note
        context: Optional additional medical context
        emotion_context: Optional voice emotion analysis summary from Modulate STT

    Returns:
        Complete SOAP note text
    """
    # Prepare generation parameters
    model, system_message, full_prompt, temperature = _prepare_soap_generation(
        text, context, settings=settings_manager.get_all(), emotion_context=emotion_context
    )

    result = call_ai(model, system_message, full_prompt, temperature)

    # Extract text from AIResult for post-processing
    result_text = result.text if hasattr(result, 'text') else str(result)
    soap_text = _postprocess_soap_result(result_text, context)

    # Validate ICD codes (warnings returned separately, not appended to SOAP text)
    return _validate_soap_output(soap_text)
