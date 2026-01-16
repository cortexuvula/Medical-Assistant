"""
RSVP Reader Dialog Components

This package provides modular components for the RSVP (Rapid Serial Visual
Presentation) reader dialog:

- core.py: RSVPEngine, RSVPSettings, RSVPTheme - Core text processing and themes
- input_mode.py: InputModePanel - Text input and file loading UI
- reading_mode.py: ReadingModePanel - Word display and playback controls
"""

from .core import RSVPEngine, RSVPSettings, RSVPTheme
from .input_mode import InputModePanel
from .reading_mode import ReadingModePanel

__all__ = [
    'RSVPEngine',
    'RSVPSettings',
    'RSVPTheme',
    'InputModePanel',
    'ReadingModePanel',
]
