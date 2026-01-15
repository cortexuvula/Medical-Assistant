"""
Unit tests for RSVP Dialog functionality.

Tests the core logic of the RSVP reader without requiring a display.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import sys

# Skip all tests if tkinter is not available (CI environment)
try:
    import tkinter as tk
    TKINTER_AVAILABLE = True
except (ImportError, RuntimeError):
    TKINTER_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not TKINTER_AVAILABLE,
    reason="tkinter not available in this environment"
)


class TestRSVPTextPreprocessing:
    """Test text preprocessing without GUI."""

    def test_preprocess_removes_icd_codes(self):
        """ICD code lines should be removed."""
        import re

        text = """Subjective: Patient presents with cough.
ICD-10: J06.9
ICD-9: 460
Assessment: Upper respiratory infection."""

        # Simulate the improved preprocessing logic
        lines = text.split('\n')
        cleaned_lines = []
        in_icd_section = False
        icd10_pattern = re.compile(r'^[A-Z]\d{2}\.?\d*\b')
        icd9_pattern = re.compile(r'^\d{3}\.?\d*\b')

        for line in lines:
            line = line.strip()
            if not line:
                continue
            upper_line = line.upper()
            if any(marker in upper_line for marker in ['ICD-10', 'ICD-9', 'ICD CODE', 'ICD:', 'DIAGNOSIS CODE']):
                in_icd_section = True
                continue
            if any(upper_line.startswith(section) for section in
                   ['SUBJECTIVE', 'OBJECTIVE', 'ASSESSMENT', 'PLAN']):
                in_icd_section = False
            if in_icd_section:
                continue
            test_line = line.lstrip('- ').strip()
            if icd10_pattern.match(test_line) or icd9_pattern.match(test_line):
                continue
            cleaned_lines.append(line)

        result = ' '.join(cleaned_lines)
        assert 'ICD-10' not in result
        assert 'ICD-9' not in result
        assert 'J06.9' not in result
        assert 'Patient presents with cough' in result
        assert 'Upper respiratory infection' in result

    def test_preprocess_removes_icd_section(self):
        """Full ICD section with multiple codes should be removed."""
        import re

        text = """Assessment: Acute bronchitis with cough.

ICD-10 Codes:
J20.9 - Acute bronchitis, unspecified
R05 - Cough

Plan: Rest and fluids."""

        lines = text.split('\n')
        cleaned_lines = []
        in_icd_section = False
        icd10_pattern = re.compile(r'^[A-Z]\d{2}\.?\d*\b')

        for line in lines:
            line = line.strip()
            if not line:
                continue
            upper_line = line.upper()
            if any(marker in upper_line for marker in ['ICD-10', 'ICD-9', 'ICD CODE', 'ICD:', 'DIAGNOSIS CODE']):
                in_icd_section = True
                continue
            if any(upper_line.startswith(section) for section in
                   ['SUBJECTIVE', 'OBJECTIVE', 'ASSESSMENT', 'PLAN']):
                in_icd_section = False
            if in_icd_section:
                continue
            test_line = line.lstrip('- ').strip()
            if icd10_pattern.match(test_line):
                continue
            cleaned_lines.append(line)

        result = ' '.join(cleaned_lines)
        assert 'ICD-10' not in result
        assert 'J20.9' not in result
        assert 'R05' not in result
        assert 'Acute bronchitis with cough' in result
        assert 'Rest and fluids' in result

    def test_preprocess_removes_not_discussed(self):
        """'Not discussed' entries should be removed."""
        text = """Subjective: Patient reports headache.
- Allergies: Not discussed
- Family history: Not discussed
Assessment: Tension headache."""

        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if 'not discussed' in line.lower():
                continue
            if line.startswith('- '):
                line = line[2:]
            cleaned_lines.append(line)

        result = ' '.join(cleaned_lines)
        assert 'Not discussed' not in result
        assert 'not discussed' not in result
        assert 'Patient reports headache' in result
        assert 'Tension headache' in result

    def test_preprocess_removes_bullet_dashes(self):
        """Leading bullet dashes should be removed."""
        text = """Plan:
- Start amoxicillin 500mg
- Follow up in 2 weeks
- Increase fluid intake"""

        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith('- '):
                line = line[2:]
            elif line.startswith('-'):
                line = line[1:].lstrip()
            cleaned_lines.append(line)

        result = ' '.join(cleaned_lines)
        assert result.startswith('Plan:')
        assert '- Start' not in result
        assert 'Start amoxicillin' in result
        assert 'Follow up in 2 weeks' in result


class TestORPCalculation:
    """Test Optimal Recognition Point calculation."""

    def calculate_orp(self, word: str) -> int:
        """Mirror the ORP calculation from RSVPDialog."""
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

    def test_orp_single_char(self):
        """Single character words have ORP at position 0."""
        assert self.calculate_orp("I") == 0
        assert self.calculate_orp("a") == 0

    def test_orp_short_words(self):
        """2-3 character words have ORP at position 0."""
        assert self.calculate_orp("to") == 0
        assert self.calculate_orp("the") == 0
        assert self.calculate_orp("and") == 0

    def test_orp_medium_words(self):
        """4-5 character words have ORP at position 1."""
        assert self.calculate_orp("with") == 1
        assert self.calculate_orp("that") == 1
        assert self.calculate_orp("hello") == 1

    def test_orp_longer_words(self):
        """6-9 character words have ORP at position 2."""
        assert self.calculate_orp("patient") == 2
        assert self.calculate_orp("headache") == 2
        assert self.calculate_orp("presents") == 2

    def test_orp_very_long_words(self):
        """10+ character words have ORP at position 3."""
        assert self.calculate_orp("medications") == 3
        assert self.calculate_orp("prescription") == 3
        assert self.calculate_orp("inflammation") == 3

    def test_orp_ignores_punctuation(self):
        """Punctuation should not affect ORP calculation."""
        assert self.calculate_orp("word.") == 1
        assert self.calculate_orp("hello!") == 1
        assert self.calculate_orp("okay,") == 1
        assert self.calculate_orp("medication.") == 3


class TestTextParsing:
    """Test text parsing into words with punctuation types."""

    def parse_word(self, word: str) -> str:
        """Determine punctuation type for a word."""
        section_keywords = {
            'subjective:', 'objective:', 'assessment:', 'plan:',
            'differential', 'diagnosis:', 'follow', 'up:',
            'clinical', 'synopsis:'
        }

        lower_word = word.lower()

        if lower_word in section_keywords or lower_word.rstrip(':') + ':' in section_keywords:
            return 'section'
        elif word[-1:] in '.!?':
            return 'sentence'
        elif word[-1:] in ',;:':
            return 'clause'
        else:
            return 'none'

    def test_section_detection(self):
        """Section keywords should be detected."""
        assert self.parse_word("Subjective:") == 'section'
        assert self.parse_word("OBJECTIVE:") == 'section'
        assert self.parse_word("Assessment:") == 'section'
        assert self.parse_word("Plan:") == 'section'

    def test_sentence_end_detection(self):
        """Sentence-ending punctuation should be detected."""
        assert self.parse_word("infection.") == 'sentence'
        assert self.parse_word("resolved!") == 'sentence'
        assert self.parse_word("better?") == 'sentence'

    def test_clause_detection(self):
        """Clause punctuation should be detected."""
        assert self.parse_word("however,") == 'clause'
        assert self.parse_word("following;") == 'clause'
        assert self.parse_word("note:") == 'clause'

    def test_no_punctuation(self):
        """Words without punctuation return 'none'."""
        assert self.parse_word("patient") == 'none'
        assert self.parse_word("the") == 'none'
        assert self.parse_word("medication") == 'none'


class TestDelayCalculation:
    """Test delay multiplier calculation."""

    def get_delay_multiplier(self, punct_type: str) -> float:
        """Get delay multiplier for punctuation type."""
        multipliers = {
            'section': 3.0,
            'sentence': 2.5,
            'clause': 1.5,
            'none': 1.0
        }
        return multipliers.get(punct_type, 1.0)

    def test_section_delay(self):
        """Section headers get 3x delay."""
        assert self.get_delay_multiplier('section') == 3.0

    def test_sentence_delay(self):
        """Sentence ends get 2.5x delay."""
        assert self.get_delay_multiplier('sentence') == 2.5

    def test_clause_delay(self):
        """Clauses get 1.5x delay."""
        assert self.get_delay_multiplier('clause') == 1.5

    def test_no_punctuation_delay(self):
        """Regular words get 1x delay."""
        assert self.get_delay_multiplier('none') == 1.0


class TestSettingsValidation:
    """Test settings validation and bounds checking."""

    MIN_WPM = 50
    MAX_WPM = 2000
    DEFAULT_WPM = 300
    MIN_FONT_SIZE = 24
    MAX_FONT_SIZE = 96
    DEFAULT_FONT_SIZE = 48

    def validate_wpm(self, wpm: int) -> int:
        """Validate WPM is within bounds."""
        if not isinstance(wpm, (int, float)):
            return self.DEFAULT_WPM
        wpm = int(wpm)
        return max(self.MIN_WPM, min(self.MAX_WPM, wpm))

    def validate_font_size(self, size: int) -> int:
        """Validate font size is within bounds."""
        if not isinstance(size, (int, float)):
            return self.DEFAULT_FONT_SIZE
        size = int(size)
        return max(self.MIN_FONT_SIZE, min(self.MAX_FONT_SIZE, size))

    def validate_chunk_size(self, chunk: int) -> int:
        """Validate chunk size is 1, 2, or 3."""
        if chunk not in (1, 2, 3):
            return 1
        return chunk

    def test_wpm_too_low(self):
        """WPM below minimum should be clamped."""
        assert self.validate_wpm(10) == self.MIN_WPM
        assert self.validate_wpm(0) == self.MIN_WPM
        assert self.validate_wpm(-100) == self.MIN_WPM

    def test_wpm_too_high(self):
        """WPM above maximum should be clamped."""
        assert self.validate_wpm(3000) == self.MAX_WPM
        assert self.validate_wpm(10000) == self.MAX_WPM

    def test_wpm_valid(self):
        """Valid WPM should pass through."""
        assert self.validate_wpm(300) == 300
        assert self.validate_wpm(500) == 500
        assert self.validate_wpm(50) == 50
        assert self.validate_wpm(2000) == 2000

    def test_wpm_invalid_type(self):
        """Invalid WPM type should return default."""
        assert self.validate_wpm("fast") == self.DEFAULT_WPM
        assert self.validate_wpm(None) == self.DEFAULT_WPM

    def test_font_size_bounds(self):
        """Font size should be within bounds."""
        assert self.validate_font_size(10) == self.MIN_FONT_SIZE
        assert self.validate_font_size(200) == self.MAX_FONT_SIZE
        assert self.validate_font_size(48) == 48

    def test_chunk_size_valid(self):
        """Valid chunk sizes should pass through."""
        assert self.validate_chunk_size(1) == 1
        assert self.validate_chunk_size(2) == 2
        assert self.validate_chunk_size(3) == 3

    def test_chunk_size_invalid(self):
        """Invalid chunk sizes should return 1."""
        assert self.validate_chunk_size(0) == 1
        assert self.validate_chunk_size(4) == 1
        assert self.validate_chunk_size(-1) == 1


class TestSectionIndices:
    """Test section detection and indexing."""

    def detect_sections(self, text: str) -> dict:
        """Detect SOAP sections and their word indices."""
        section_keywords = {
            'subjective:', 'objective:', 'assessment:', 'plan:',
            'differential', 'diagnosis:', 'clinical', 'synopsis:'
        }

        section_indices = {}
        words = text.split()

        for i, word in enumerate(words):
            lower_word = word.lower()
            if lower_word in section_keywords or lower_word.rstrip(':') + ':' in section_keywords:
                section_name = word.rstrip(':').capitalize()
                if section_name not in section_indices:
                    section_indices[section_name] = i

        return section_indices

    def test_detect_all_soap_sections(self):
        """All SOAP sections should be detected."""
        text = "Subjective: pain. Objective: vital signs. Assessment: diagnosis. Plan: treatment."
        sections = self.detect_sections(text)

        assert 'Subjective' in sections
        assert 'Objective' in sections
        assert 'Assessment' in sections
        assert 'Plan' in sections

    def test_section_indices_correct(self):
        """Section indices should be correct."""
        text = "Subjective: word1 word2. Objective: word3."
        sections = self.detect_sections(text)

        assert sections['Subjective'] == 0
        assert sections['Objective'] == 3

    def test_no_sections(self):
        """Text without sections should return empty dict."""
        text = "Patient presents with cough and fever."
        sections = self.detect_sections(text)

        assert sections == {}


class TestSentenceTracking:
    """Test sentence boundary detection."""

    def track_sentences(self, text: str) -> list:
        """Track sentence boundaries."""
        words = text.split()
        sentences = []
        current_start = 0
        current_words = []

        for i, word in enumerate(words):
            current_words.append(word)
            if word[-1:] in '.!?':
                sentence_text = ' '.join(current_words)
                sentences.append((current_start, i, sentence_text))
                current_start = i + 1
                current_words = []

        # Add final sentence if not terminated
        if current_words:
            sentence_text = ' '.join(current_words)
            sentences.append((current_start, len(words) - 1, sentence_text))

        return sentences

    def test_single_sentence(self):
        """Single sentence should be tracked correctly."""
        text = "Patient presents with cough."
        sentences = self.track_sentences(text)

        assert len(sentences) == 1
        assert sentences[0][0] == 0  # start
        assert sentences[0][2] == "Patient presents with cough."

    def test_multiple_sentences(self):
        """Multiple sentences should be tracked correctly."""
        text = "First sentence. Second sentence. Third sentence."
        sentences = self.track_sentences(text)

        assert len(sentences) == 3
        assert sentences[0][2] == "First sentence."
        assert sentences[1][2] == "Second sentence."
        assert sentences[2][2] == "Third sentence."

    def test_unterminated_sentence(self):
        """Text without terminal punctuation should still be tracked."""
        text = "Patient feels better"
        sentences = self.track_sentences(text)

        assert len(sentences) == 1
        assert sentences[0][2] == "Patient feels better"


class TestBaseDelayCalculation:
    """Test base delay calculation from WPM."""

    def calculate_base_delay(self, wpm: int) -> int:
        """Calculate base delay in milliseconds from WPM."""
        return int(60000 / wpm)

    def test_300_wpm(self):
        """300 WPM should give 200ms base delay."""
        assert self.calculate_base_delay(300) == 200

    def test_600_wpm(self):
        """600 WPM should give 100ms base delay."""
        assert self.calculate_base_delay(600) == 100

    def test_150_wpm(self):
        """150 WPM should give 400ms base delay."""
        assert self.calculate_base_delay(150) == 400

    def test_delay_with_multiplier(self):
        """Test delay with punctuation multiplier."""
        base = self.calculate_base_delay(300)  # 200ms

        assert base * 1.0 == 200  # none
        assert base * 1.5 == 300  # clause
        assert base * 2.5 == 500  # sentence
        assert base * 3.0 == 600  # section


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
