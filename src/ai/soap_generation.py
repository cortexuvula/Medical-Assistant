"""SOAP Note Generation Module.

Provides functions for generating and formatting SOAP notes.
"""

import re
import logging
from typing import Callable

from ai.providers.router import call_ai, call_ai_streaming
from ai.text_processing import clean_text
from ai.prompts import SOAP_PROMPT_TEMPLATE, get_soap_system_message
from settings.settings import SETTINGS


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

    logging.info(f"format_soap_paragraphs: {len(lines)} lines -> {len(result_lines)} lines, detected headers: {detected_headers}")
    return '\n'.join(result_lines)


def _prepare_soap_generation(text: str, context: str, settings: dict = None) -> tuple:
    """Prepare common parameters for SOAP note generation.

    Args:
        text: Transcript text to convert
        context: Optional medical context
        settings: Settings dict (uses SETTINGS global if None)

    Returns:
        Tuple of (model, system_message, full_prompt, temperature)
    """
    from datetime import datetime

    # Use provided settings or global
    if settings is None:
        settings = SETTINGS

    model = settings.get("soap_note", {}).get("model", "gpt-4")
    icd_version = settings.get("soap_note", {}).get("icd_code_version", "ICD-9")
    current_provider = settings.get("ai_provider", "openai")

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

    # Build prompt with context
    if context and context.strip():
        full_prompt = f"Previous medical context:\n{context}\n\n{SOAP_PROMPT_TEMPLATE.format(text=transcript_with_datetime)}"
    else:
        full_prompt = SOAP_PROMPT_TEMPLATE.format(text=transcript_with_datetime)

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
    logging.info(f"SOAP raw AI response: {len(result)} chars, {result.count(chr(10))} newlines")
    logging.info(f"SOAP raw preview: {repr(result[:200])}")

    # Clean both markdown and citations, then format paragraphs
    cleaned_soap = clean_text(result)
    logging.info(f"SOAP after clean_text: {len(cleaned_soap)} chars, {cleaned_soap.count(chr(10))} newlines")

    cleaned_soap = format_soap_paragraphs(cleaned_soap)

    # Count blank lines to verify formatting
    blank_line_count = cleaned_soap.count('\n\n')
    logging.info(f"SOAP after format_soap_paragraphs: {len(cleaned_soap)} chars, {cleaned_soap.count(chr(10))} newlines, {blank_line_count} blank lines")
    logging.info(f"SOAP final preview: {repr(cleaned_soap[:200])}")

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
    from settings.settings import load_settings

    # Reload settings to get latest
    current_settings = load_settings()

    # Prepare generation parameters
    model, system_message, full_prompt, temperature = _prepare_soap_generation(
        text, context, settings=current_settings
    )

    # Use streaming API call
    if on_chunk:
        result = call_ai_streaming(model, system_message, full_prompt, temperature, on_chunk)
    else:
        # Fall back to non-streaming if no callback provided
        result = call_ai(model, system_message, full_prompt, temperature)

    return _postprocess_soap_result(result, context, on_chunk)


def create_soap_note_with_openai(text: str, context: str = "") -> str:
    """Create a SOAP note using AI.

    Args:
        text: Transcript text to convert to SOAP note
        context: Optional additional medical context

    Returns:
        Complete SOAP note text
    """
    # Prepare generation parameters
    model, system_message, full_prompt, temperature = _prepare_soap_generation(
        text, context, settings=SETTINGS
    )

    result = call_ai(model, system_message, full_prompt, temperature)

    return _postprocess_soap_result(result, context)
