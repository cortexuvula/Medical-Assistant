"""Translation providers module."""

from .base import BaseTranslationProvider
from .deep_translator_provider import DeepTranslatorProvider

__all__ = [
    'BaseTranslationProvider',
    'DeepTranslatorProvider'
]