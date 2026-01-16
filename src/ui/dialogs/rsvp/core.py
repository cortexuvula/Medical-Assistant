"""
RSVP Core Engine

Core RSVP (Rapid Serial Visual Presentation) functionality including:
- Text parsing into words with punctuation tracking
- Sentence boundary detection for context display
- ORP (Optimal Recognition Point) calculation
- Timing calculations based on WPM and punctuation
"""

from typing import List, Tuple
from dataclasses import dataclass, field


@dataclass
class RSVPSettings:
    """Settings for RSVP display."""
    wpm: int = 300
    font_size: int = 48
    chunk_size: int = 1
    dark_theme: bool = True
    audio_cue: bool = False
    show_context: bool = False

    # Speed constants
    MIN_WPM: int = field(default=50, repr=False)
    MAX_WPM: int = field(default=2000, repr=False)
    WPM_STEP: int = field(default=25, repr=False)

    # Font constants
    MIN_FONT_SIZE: int = field(default=24, repr=False)
    MAX_FONT_SIZE: int = field(default=96, repr=False)

    def validate_wpm(self, value) -> int:
        """Validate WPM with bounds checking."""
        try:
            wpm = int(value)
            return max(self.MIN_WPM, min(self.MAX_WPM, wpm))
        except (TypeError, ValueError):
            return 300

    def validate_font_size(self, value) -> int:
        """Validate font size with bounds checking."""
        try:
            size = int(value)
            return max(self.MIN_FONT_SIZE, min(self.MAX_FONT_SIZE, size))
        except (TypeError, ValueError):
            return 48

    def validate_chunk_size(self, value) -> int:
        """Validate chunk size (1, 2, or 3)."""
        try:
            chunk = int(value)
            return chunk if chunk in (1, 2, 3) else 1
        except (TypeError, ValueError):
            return 1


class RSVPEngine:
    """Core engine for RSVP text processing and timing."""

    # Punctuation delay multipliers
    DELAY_SENTENCE = 2.5    # End of sentence (.!?)
    DELAY_CLAUSE = 1.5      # Clause punctuation (,;:)
    DELAY_NORMAL = 1.0      # Regular words

    def __init__(self):
        """Initialize the RSVP engine."""
        self.words: List[Tuple[str, str]] = []  # (word, punct_type)
        self.sentences: List[Tuple[int, int, str]] = []  # (start_idx, end_idx, text)
        self.text: str = ""

    def parse_text(self, text: str) -> None:
        """Parse text into words with punctuation tracking.

        Args:
            text: Raw text to parse
        """
        self.text = text
        raw_words = text.split()
        self.words = []
        self.sentences = []

        current_sentence_start = 0
        current_sentence_words = []

        for word in raw_words:
            if not word:
                continue

            word_index = len(self.words)

            # Determine punctuation type for timing
            if word[-1:] in '.!?':
                punct_type = 'sentence'
            elif word[-1:] in ',;:':
                punct_type = 'clause'
            else:
                punct_type = 'none'

            self.words.append((word, punct_type))
            current_sentence_words.append(word)

            # Track sentence boundaries
            if punct_type == 'sentence':
                sentence_text = ' '.join(current_sentence_words)
                self.sentences.append((current_sentence_start, word_index, sentence_text))
                current_sentence_start = word_index + 1
                current_sentence_words = []

        # Add final sentence if not terminated
        if current_sentence_words:
            sentence_text = ' '.join(current_sentence_words)
            self.sentences.append((current_sentence_start, len(self.words) - 1, sentence_text))

    def get_word_count(self) -> int:
        """Get total word count."""
        return len(self.words)

    def get_word(self, index: int) -> Tuple[str, str]:
        """Get word and punctuation type at index."""
        if 0 <= index < len(self.words):
            return self.words[index]
        return ("", "none")

    def get_chunk(self, start_index: int, chunk_size: int) -> List[str]:
        """Get a chunk of words starting at index.

        Args:
            start_index: Starting word index
            chunk_size: Number of words to get

        Returns:
            List of words
        """
        end_idx = min(start_index + chunk_size, len(self.words))
        return [w[0] for w in self.words[start_index:end_idx]]

    def get_sentence_for_index(self, word_index: int) -> str:
        """Get the sentence containing the word at given index."""
        for start, end, text in self.sentences:
            if start <= word_index <= end:
                return text
        return ""

    def get_sentence_start_index(self, word_index: int) -> int:
        """Get the starting word index of the sentence containing word_index."""
        for start, end, _ in self.sentences:
            if start <= word_index <= end:
                return start
        return 0

    def calculate_delay_ms(self, index: int, wpm: int) -> int:
        """Calculate display delay for word at index.

        Args:
            index: Word index
            wpm: Words per minute setting

        Returns:
            Delay in milliseconds
        """
        if index >= len(self.words):
            return 200

        base_delay = int(60000 / wpm)
        _, punct_type = self.words[index]

        multipliers = {
            'sentence': self.DELAY_SENTENCE,
            'clause': self.DELAY_CLAUSE,
            'none': self.DELAY_NORMAL
        }

        return int(base_delay * multipliers.get(punct_type, self.DELAY_NORMAL))

    @staticmethod
    def calculate_orp(word: str) -> int:
        """Calculate Optimal Recognition Point index for a word.

        The ORP is the character position where the eye should focus
        for optimal reading speed and comprehension.

        Args:
            word: The word to calculate ORP for

        Returns:
            Character index of the ORP
        """
        # Clean word of trailing punctuation for length calculation
        clean_word = word.rstrip('.,;:!?"\'-')
        length = len(clean_word)

        if length <= 1:
            return 0
        if length <= 3:
            return 0
        if length <= 5:
            return 1
        if length <= 9:
            return 2
        return 3

    @staticmethod
    def calculate_time_remaining(words_remaining: int, wpm: int) -> str:
        """Calculate estimated time remaining.

        Args:
            words_remaining: Number of words left
            wpm: Current words per minute

        Returns:
            Formatted time string
        """
        if wpm <= 0:
            return "..."

        seconds_remaining = (words_remaining * 60) / wpm

        if seconds_remaining < 60:
            return f"~{int(seconds_remaining)} sec remaining"
        else:
            minutes = int(seconds_remaining // 60)
            seconds = int(seconds_remaining % 60)
            return f"~{minutes}:{seconds:02d} remaining"


# Theme color definitions
class RSVPTheme:
    """Color theme definitions for RSVP display."""

    # Dark theme colors
    DARK = {
        'bg': "#1E1E1E",
        'text': "#FFFFFF",
        'orp': "#FF6B6B",
        'control_bg': "#2D2D2D",
        'progress_bg': "#3D3D3D",
        'context': "#666666",
        'input_bg': "#252525",
    }

    # Light theme colors
    LIGHT = {
        'bg': "#F5F5F5",
        'text': "#1E1E1E",
        'orp': "#E53935",
        'control_bg': "#E0E0E0",
        'progress_bg': "#D0D0D0",
        'context': "#999999",
        'input_bg': "#FFFFFF",
    }

    @classmethod
    def get_colors(cls, dark_theme: bool) -> dict:
        """Get color dictionary for theme.

        Args:
            dark_theme: True for dark theme, False for light

        Returns:
            Dictionary of color values
        """
        return cls.DARK if dark_theme else cls.LIGHT


__all__ = ['RSVPEngine', 'RSVPSettings', 'RSVPTheme']
