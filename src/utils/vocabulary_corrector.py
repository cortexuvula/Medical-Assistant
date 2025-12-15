"""
Vocabulary Corrector - Core correction engine for post-STT text processing.

This module provides find/replace corrections for medical transcriptions,
supporting categories (doctors, medications, terminology, abbreviations)
and medical specialty context filtering.
"""

import re
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class CorrectionResult:
    """Result of applying vocabulary corrections."""
    original_text: str
    corrected_text: str
    corrections_applied: List[Dict[str, Any]] = field(default_factory=list)
    specialty_used: str = "general"
    total_replacements: int = 0


class VocabularyCorrector:
    """Applies vocabulary corrections to text using configurable rules.

    This class handles find/replace operations with:
    - Word boundary detection (prevents partial word matches)
    - Case-insensitive matching (configurable per entry)
    - Specialty-based filtering
    - Priority ordering
    """

    def __init__(self):
        """Initialize the corrector."""
        self.logger = logging.getLogger(__name__)
        self._compiled_patterns: Dict[tuple, re.Pattern] = {}

    def apply_corrections(
        self,
        text: str,
        corrections: Dict[str, Dict],
        specialty: Optional[str] = None,
        default_case_sensitive: bool = False
    ) -> CorrectionResult:
        """Apply vocabulary corrections to text.

        Args:
            text: Original text from STT
            corrections: Dictionary of correction rules
                Format: {"find_text": {"replacement": "...", "category": "...",
                         "specialty": "..." or None, "case_sensitive": bool}}
            specialty: Medical specialty filter (None = apply all)
            default_case_sensitive: Default case sensitivity if not specified per entry

        Returns:
            CorrectionResult with corrected text and metadata
        """
        if not text:
            return CorrectionResult(
                original_text="",
                corrected_text="",
                specialty_used=specialty or "general"
            )

        if not corrections:
            return CorrectionResult(
                original_text=text,
                corrected_text=text,
                specialty_used=specialty or "general"
            )

        corrected_text = text
        corrections_applied = []
        total_replacements = 0

        # Sort corrections by priority (higher first), then by length (longer first)
        # Longer matches should be processed first to avoid partial replacements
        sorted_corrections = sorted(
            corrections.items(),
            key=lambda x: (-x[1].get("priority", 0), -len(x[0]))
        )

        for find_text, rule in sorted_corrections:
            # Skip disabled entries
            if not rule.get("enabled", True):
                continue

            # Filter by specialty if specified
            entry_specialty = rule.get("specialty")
            if specialty and entry_specialty and entry_specialty != specialty and entry_specialty != "general":
                continue

            replacement = rule.get("replacement", "")
            if not replacement:
                continue

            is_case_sensitive = rule.get("case_sensitive", default_case_sensitive)

            # Get or create compiled pattern
            pattern = self._get_pattern(find_text, is_case_sensitive)
            if not pattern:
                continue

            # Count matches before replacement
            matches = pattern.findall(corrected_text)
            match_count = len(matches)

            if match_count > 0:
                # Apply replacement
                corrected_text = pattern.sub(replacement, corrected_text)
                total_replacements += match_count

                corrections_applied.append({
                    "find": find_text,
                    "replace": replacement,
                    "category": rule.get("category", "general"),
                    "count": match_count
                })

                self.logger.debug(
                    f"Applied correction: '{find_text}' -> '{replacement}' ({match_count}x)"
                )

        return CorrectionResult(
            original_text=text,
            corrected_text=corrected_text,
            corrections_applied=corrections_applied,
            specialty_used=specialty or "general",
            total_replacements=total_replacements
        )

    def _get_pattern(self, find_text: str, case_sensitive: bool) -> Optional[re.Pattern]:
        """Get compiled regex pattern for find text.

        Uses word boundary matching to prevent partial word replacements.
        For example, "htn" won't match "washington".

        Args:
            find_text: Text to find
            case_sensitive: Whether to match case exactly

        Returns:
            Compiled regex pattern or None if invalid
        """
        cache_key = (find_text, case_sensitive)

        if cache_key in self._compiled_patterns:
            return self._compiled_patterns[cache_key]

        try:
            # Use word boundaries to prevent partial matches
            # \b matches word boundaries (start/end of word)
            pattern_str = r'\b' + re.escape(find_text) + r'\b'

            flags = 0 if case_sensitive else re.IGNORECASE
            pattern = re.compile(pattern_str, flags)

            self._compiled_patterns[cache_key] = pattern
            return pattern

        except re.error as e:
            self.logger.error(f"Invalid pattern for '{find_text}': {e}")
            return None

    def clear_cache(self):
        """Clear compiled pattern cache.

        Call this when corrections are modified to ensure
        updated patterns are used.
        """
        self._compiled_patterns.clear()
        self.logger.debug("Pattern cache cleared")

    def test_correction(
        self,
        text: str,
        find_text: str,
        replacement: str,
        case_sensitive: bool = False
    ) -> CorrectionResult:
        """Test a single correction on text.

        Useful for previewing corrections in the UI.

        Args:
            text: Text to test on
            find_text: Text to find
            replacement: Replacement text
            case_sensitive: Whether to match case

        Returns:
            CorrectionResult with test results
        """
        corrections = {
            find_text: {
                "replacement": replacement,
                "category": "test",
                "case_sensitive": case_sensitive,
                "enabled": True
            }
        }
        return self.apply_corrections(text, corrections)
