"""
Translation Dialog - Re-export Facade

This module provides backward compatibility by re-exporting the TranslationDialog
from the refactored translation package.

DEPRECATED: Import directly from ui.dialogs.translation instead.
"""

from .translation import TranslationDialog

__all__ = ["TranslationDialog"]
