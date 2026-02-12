"""AI Module - Backward Compatibility Shim.

All functions have been refactored into focused modules for better maintainability.
This file re-exports them for backward compatibility with existing imports.

Module structure:
- ai/logging_utils.py - Debug logging utilities
- ai/text_processing.py - Text cleaning and improvement
- ai/soap_generation.py - SOAP note generation
- ai/letter_generation.py - Letter and referral generation
- ai/providers/ - AI provider implementations
  - base.py - Shared utilities
  - openai_provider.py - OpenAI API calls
  - anthropic_provider.py - Anthropic API calls
  - ollama_provider.py - Ollama API calls
  - gemini_provider.py - Gemini API calls
  - router.py - Provider routing
"""

# Re-export logging utilities
from ai.logging_utils import log_api_call_debug

# Re-export text processing functions
from ai.text_processing import (
    clean_text,
    adjust_text_with_openai,
    improve_text_with_openai,
)

# Re-export SOAP generation functions
from ai.soap_generation import (
    format_soap_paragraphs,
    create_soap_note_with_openai,
    create_soap_note_streaming,
)

# Re-export letter generation functions
from ai.letter_generation import (
    create_letter_with_ai,
    create_letter_streaming,
    create_referral_with_openai,
    get_possible_conditions,
)

# Re-export provider router functions
from ai.providers.router import call_ai, call_ai_streaming

# Re-export individual provider functions
from ai.providers.openai_provider import call_openai, call_openai_streaming
from ai.providers.anthropic_provider import call_anthropic, call_anthropic_streaming
from ai.providers.ollama_provider import call_ollama, fallback_ollama_generate
from ai.providers.gemini_provider import call_gemini

# Re-export base utilities
from ai.providers.base import get_model_key_for_task

# Define public API
__all__ = [
    # Logging
    'log_api_call_debug',
    # Text processing
    'clean_text',
    'adjust_text_with_openai',
    'improve_text_with_openai',
    # SOAP generation
    'format_soap_paragraphs',
    'create_soap_note_with_openai',
    'create_soap_note_streaming',
    # Letter generation
    'create_letter_with_ai',
    'create_letter_streaming',
    'create_referral_with_openai',
    'get_possible_conditions',
    # Provider routing
    'call_ai',
    'call_ai_streaming',
    # Individual providers
    'call_openai',
    'call_openai_streaming',
    'call_anthropic',
    'call_anthropic_streaming',
    'call_ollama',
    'fallback_ollama_generate',
    'call_gemini',
    # Utilities
    'get_model_key_for_task',
]
