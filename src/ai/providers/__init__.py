"""AI Providers Package.

This package contains provider-specific implementations for different AI services.
"""

from ai.providers.base import get_model_key_for_task
from ai.providers.openai_provider import (
    call_openai,
    call_openai_streaming,
)
from ai.providers.anthropic_provider import (
    call_anthropic,
    call_anthropic_streaming,
)
from ai.providers.ollama_provider import (
    call_ollama,
    fallback_ollama_chat,
)
from ai.providers.gemini_provider import call_gemini
from ai.providers.router import call_ai, call_ai_streaming

__all__ = [
    'get_model_key_for_task',
    'call_openai', 'call_openai_streaming',
    'call_anthropic', 'call_anthropic_streaming',
    'call_ollama', 'fallback_ollama_chat',
    'call_gemini',
    'call_ai', 'call_ai_streaming',
]
