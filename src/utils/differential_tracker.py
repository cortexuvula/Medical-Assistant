"""
Differential Diagnosis Tracker Module

Tracks evolution of differential diagnoses across periodic analyses,
detecting new, unchanged, moved, and removed diagnoses.
"""

import re
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum

from utils.structured_logging import get_logger

logger = get_logger(__name__)


class DifferentialStatus(Enum):
    """Status of a differential diagnosis compared to previous analysis."""
    NEW = "new"           # Not in previous analysis
    UNCHANGED = "same"    # Same position and confidence
    MOVED_UP = "up"       # Moved to higher rank (lower number)
    MOVED_DOWN = "down"   # Moved to lower rank (higher number)
    CONFIDENCE_UP = "conf_up"    # Same position, higher confidence
    CONFIDENCE_DOWN = "conf_down"  # Same position, lower confidence


@dataclass
class Differential:
    """Represents a single differential diagnosis."""
    rank: int
    diagnosis: str
    confidence: int  # Numeric confidence 0-100%
    icd_code: Optional[str] = None
    supporting: str = ""
    against: str = ""

    def normalized_name(self) -> str:
        """Return normalized diagnosis name for comparison."""
        # Remove common variations, extra spaces, convert to lowercase
        name = self.diagnosis.lower().strip()
        # Remove common suffixes/prefixes that might vary
        name = re.sub(r'\s+', ' ', name)  # Normalize whitespace
        return name

    @property
    def confidence_level(self) -> str:
        """Return confidence as HIGH/MEDIUM/LOW for backward compatibility."""
        if self.confidence >= 70:
            return "HIGH"
        elif self.confidence >= 40:
            return "MEDIUM"
        else:
            return "LOW"

    @property
    def confidence_display(self) -> str:
        """Return formatted confidence for display (e.g., '78% (HIGH)')."""
        return f"{self.confidence}% ({self.confidence_level})"


@dataclass
class DifferentialEvolution:
    """Tracks the evolution of a differential between analyses."""
    differential: Differential
    status: DifferentialStatus
    previous_rank: Optional[int] = None
    previous_confidence: Optional[int] = None  # Now numeric

    def get_indicator(self) -> str:
        """Get a visual indicator for the evolution status."""
        indicators = {
            DifferentialStatus.NEW: "🆕",
            DifferentialStatus.UNCHANGED: "➡️",
            DifferentialStatus.MOVED_UP: "⬆️",
            DifferentialStatus.MOVED_DOWN: "⬇️",
            DifferentialStatus.CONFIDENCE_UP: "📈",
            DifferentialStatus.CONFIDENCE_DOWN: "📉",
        }
        return indicators.get(self.status, "")

    def get_change_description(self) -> str:
        """Get a text description of the change."""
        if self.status == DifferentialStatus.NEW:
            return "NEW"
        elif self.status == DifferentialStatus.UNCHANGED:
            return ""
        elif self.status == DifferentialStatus.MOVED_UP:
            return f"(was #{self.previous_rank})"
        elif self.status == DifferentialStatus.MOVED_DOWN:
            return f"(was #{self.previous_rank})"
        elif self.status == DifferentialStatus.CONFIDENCE_UP:
            return f"(was {self.previous_confidence}%)"
        elif self.status == DifferentialStatus.CONFIDENCE_DOWN:
            return f"(was {self.previous_confidence}%)"
        return ""

    def get_confidence_delta(self) -> Optional[int]:
        """Get the change in confidence percentage."""
        if self.previous_confidence is not None:
            return self.differential.confidence - self.previous_confidence
        return None


class DifferentialTracker:
    """Tracks differential diagnosis evolution across analyses."""

    # Minimum confidence change to trigger CONFIDENCE_UP/DOWN status
    CONFIDENCE_CHANGE_THRESHOLD = 5  # 5% change needed

    def __init__(self):
        """Initialize the tracker."""
        self.previous_differentials: List[Differential] = []
        self.removed_differentials: List[Differential] = []

    def clear(self) -> None:
        """Clear all tracked differentials."""
        self.previous_differentials = []
        self.removed_differentials = []
        logger.info("Differential tracker cleared")

    def _parse_confidence(self, text: str) -> int:
        """Parse confidence from various formats.

        Supports:
        - Numeric: "78%", "78", "78% confidence"
        - Text: "HIGH", "MEDIUM", "LOW"
        - Combined: "78% (HIGH)"

        Args:
            text: The confidence text to parse

        Returns:
            Numeric confidence 0-100
        """
        # Try numeric format first: "78%", "78% confidence", "78"
        numeric_match = re.search(r'(\d{1,3})%?', text)
        if numeric_match:
            value = int(numeric_match.group(1))
            # Clamp to valid range
            return max(0, min(100, value))

        # Fall back to text format
        text_upper = text.upper().strip()
        if "HIGH" in text_upper:
            return 80
        elif "MEDIUM" in text_upper:
            return 55
        elif "LOW" in text_upper:
            return 25

        # Default to medium if unrecognized
        return 50

    def parse_differentials(self, analysis_text: str) -> List[Differential]:
        """Parse differential diagnoses from analysis text.

        Supports both old format (HIGH/MEDIUM/LOW) and new format (X% confidence with ICD-10).

        Args:
            analysis_text: The full analysis text containing differentials

        Returns:
            List of Differential objects
        """
        differentials = []

        try:
            # Find the DIFFERENTIAL DIAGNOSES section
            diff_section_match = re.search(
                r'DIFFERENTIAL DIAGNOSES.*?(?=\n(?:RECOMMENDED|QUESTIONS|IMMEDIATE|$))',
                analysis_text,
                re.DOTALL | re.IGNORECASE
            )

            if not diff_section_match:
                logger.debug("No differential diagnoses section found")
                return differentials

            diff_section = diff_section_match.group(0)

            # Pattern to match numbered differentials with flexible confidence format
            # New format: "1. [Diagnosis] - [X]% confidence (ICD-10: [code])"
            # Old format: "1. [Diagnosis] - [HIGH/MEDIUM/LOW confidence]"
            # Also handles: "1. [Diagnosis] - [X]% (HIGH)"
            pattern = r'(\d+)\.\s*([^-\n]+?)\s*-\s*(\d{1,3}%?\s*(?:\([^)]*\))?\s*(?:confidence)?|HIGH|MEDIUM|LOW)\s*(?:confidence)?(?:\s*\(ICD-10:\s*([A-Z]\d{2}(?:\.\d{1,4})?)\))?'

            matches = re.finditer(pattern, diff_section, re.IGNORECASE)

            for match in matches:
                rank = int(match.group(1))
                diagnosis = match.group(2).strip()
                confidence_text = match.group(3).strip()
                icd_code = match.group(4) if match.group(4) else None

                # Parse confidence to numeric value
                confidence = self._parse_confidence(confidence_text)

                # Try to extract ICD code from diagnosis text if not in pattern match
                if not icd_code:
                    icd_match = re.search(r'\(ICD-10:\s*([A-Z]\d{2}(?:\.\d{1,4})?)\)', match.group(0))
                    if icd_match:
                        icd_code = icd_match.group(1)

                # Try to extract supporting/against evidence
                # Look for text after this match until the next numbered item
                start_pos = match.end()
                next_match = re.search(r'\n\d+\.', diff_section[start_pos:])

                if next_match:
                    details = diff_section[start_pos:start_pos + next_match.start()]
                else:
                    details = diff_section[start_pos:]

                supporting = ""
                against = ""

                supporting_match = re.search(r'Supporting:\s*(.+?)(?=Against:|$)', details, re.DOTALL | re.IGNORECASE)
                if supporting_match:
                    supporting = supporting_match.group(1).strip()

                against_match = re.search(r'Against:\s*(.+?)(?=\n\n|$)', details, re.DOTALL | re.IGNORECASE)
                if against_match:
                    against = against_match.group(1).strip()

                differential = Differential(
                    rank=rank,
                    diagnosis=diagnosis,
                    confidence=confidence,
                    icd_code=icd_code,
                    supporting=supporting,
                    against=against
                )
                differentials.append(differential)

            logger.debug(f"Parsed {len(differentials)} differentials")

        except Exception as e:
            logger.error(f"Error parsing differentials: {e}")

        return differentials

    def compare_differentials(self, current: List[Differential]) -> Tuple[List[DifferentialEvolution], List[Differential]]:
        """Compare current differentials with previous ones.

        Args:
            current: List of current differential diagnoses

        Returns:
            Tuple of (evolved differentials with status, removed differentials)
        """
        evolutions = []
        removed = []

        # Build lookup for previous differentials by normalized name
        prev_lookup: Dict[str, Differential] = {
            d.normalized_name(): d for d in self.previous_differentials
        }

        # Track which previous differentials are still present
        seen_previous = set()

        for diff in current:
            norm_name = diff.normalized_name()

            if norm_name in prev_lookup:
                # Differential exists in previous analysis
                seen_previous.add(norm_name)
                prev_diff = prev_lookup[norm_name]

                # Determine status
                status = self._determine_status(prev_diff, diff)

                evolution = DifferentialEvolution(
                    differential=diff,
                    status=status,
                    previous_rank=prev_diff.rank,
                    previous_confidence=prev_diff.confidence
                )
            else:
                # New differential
                evolution = DifferentialEvolution(
                    differential=diff,
                    status=DifferentialStatus.NEW
                )

            evolutions.append(evolution)

        # Find removed differentials
        for norm_name, prev_diff in prev_lookup.items():
            if norm_name not in seen_previous:
                removed.append(prev_diff)

        return evolutions, removed

    def _determine_status(self, prev: Differential, curr: Differential) -> DifferentialStatus:
        """Determine the evolution status between previous and current differential.

        Now uses numeric confidence values for comparison.
        """
        # Check rank change first
        if curr.rank < prev.rank:
            return DifferentialStatus.MOVED_UP
        elif curr.rank > prev.rank:
            return DifferentialStatus.MOVED_DOWN

        # Same rank, check confidence change (now numeric)
        confidence_delta = curr.confidence - prev.confidence

        # Only trigger confidence change if above threshold
        if confidence_delta >= self.CONFIDENCE_CHANGE_THRESHOLD:
            return DifferentialStatus.CONFIDENCE_UP
        elif confidence_delta <= -self.CONFIDENCE_CHANGE_THRESHOLD:
            return DifferentialStatus.CONFIDENCE_DOWN

        return DifferentialStatus.UNCHANGED

    def update(self, current: List[Differential]) -> None:
        """Update the tracker with current differentials for next comparison.

        Args:
            current: List of current differential diagnoses
        """
        self.previous_differentials = current.copy()

    def format_evolution_text(self, evolutions: List[DifferentialEvolution],
                             removed: List[Differential],
                             analysis_count: int) -> str:
        """Format evolution information as text to append to analysis.

        Args:
            evolutions: List of differential evolutions
            removed: List of removed differentials
            analysis_count: Current analysis number

        Returns:
            Formatted evolution text
        """
        if analysis_count <= 1:
            # First analysis, no evolution to show
            return ""

        lines = ["\n\n--- DIFFERENTIAL EVOLUTION ---"]

        # Summary line
        new_count = sum(1 for e in evolutions if e.status == DifferentialStatus.NEW)
        up_count = sum(1 for e in evolutions if e.status == DifferentialStatus.MOVED_UP)
        down_count = sum(1 for e in evolutions if e.status == DifferentialStatus.MOVED_DOWN)
        removed_count = len(removed)

        summary_parts = []
        if new_count:
            summary_parts.append(f"{new_count} new")
        if up_count:
            summary_parts.append(f"{up_count} moved up")
        if down_count:
            summary_parts.append(f"{down_count} moved down")
        if removed_count:
            summary_parts.append(f"{removed_count} removed")

        if summary_parts:
            lines.append(f"Summary: {', '.join(summary_parts)} since last analysis")

        # Group by status
        new_diffs = [e for e in evolutions if e.status == DifferentialStatus.NEW]
        moved_up = [e for e in evolutions if e.status == DifferentialStatus.MOVED_UP]
        moved_down = [e for e in evolutions if e.status == DifferentialStatus.MOVED_DOWN]
        conf_up = [e for e in evolutions if e.status == DifferentialStatus.CONFIDENCE_UP]
        conf_down = [e for e in evolutions if e.status == DifferentialStatus.CONFIDENCE_DOWN]
        unchanged = [e for e in evolutions if e.status == DifferentialStatus.UNCHANGED]

        if new_diffs:
            lines.append("\n🆕 NEW:")
            for e in new_diffs:
                icd_str = f" (ICD-10: {e.differential.icd_code})" if e.differential.icd_code else ""
                lines.append(f"   • {e.differential.diagnosis} - {e.differential.confidence}%{icd_str}")

        if moved_up:
            lines.append("\n⬆️ MOVED UP:")
            for e in moved_up:
                delta = f"+{e.differential.confidence - e.previous_confidence}%" if e.previous_confidence else ""
                lines.append(f"   • {e.differential.diagnosis}: #{e.previous_rank} → #{e.differential.rank} ({e.previous_confidence}% → {e.differential.confidence}%)")

        if moved_down:
            lines.append("\n⬇️ MOVED DOWN:")
            for e in moved_down:
                lines.append(f"   • {e.differential.diagnosis}: #{e.previous_rank} → #{e.differential.rank} ({e.previous_confidence}% → {e.differential.confidence}%)")

        if conf_up:
            lines.append("\n📈 CONFIDENCE INCREASED:")
            for e in conf_up:
                delta = e.differential.confidence - e.previous_confidence
                lines.append(f"   • {e.differential.diagnosis}: {e.previous_confidence}% → {e.differential.confidence}% (+{delta}%)")

        if conf_down:
            lines.append("\n📉 CONFIDENCE DECREASED:")
            for e in conf_down:
                delta = e.previous_confidence - e.differential.confidence
                lines.append(f"   • {e.differential.diagnosis}: {e.previous_confidence}% → {e.differential.confidence}% (-{delta}%)")

        if removed:
            lines.append("\n❌ REMOVED FROM DIFFERENTIAL:")
            for d in removed:
                icd_str = f", ICD-10: {d.icd_code}" if d.icd_code else ""
                lines.append(f"   • {d.diagnosis} (was #{d.rank}, {d.confidence}%{icd_str})")

        if unchanged:
            lines.append(f"\n➡️ UNCHANGED: {len(unchanged)} diagnosis(es)")

        lines.append("")

        return "\n".join(lines)
