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
    confidence: str  # HIGH, MEDIUM, LOW
    supporting: str = ""
    against: str = ""

    def normalized_name(self) -> str:
        """Return normalized diagnosis name for comparison."""
        # Remove common variations, extra spaces, convert to lowercase
        name = self.diagnosis.lower().strip()
        # Remove common suffixes/prefixes that might vary
        name = re.sub(r'\s+', ' ', name)  # Normalize whitespace
        return name


@dataclass
class DifferentialEvolution:
    """Tracks the evolution of a differential between analyses."""
    differential: Differential
    status: DifferentialStatus
    previous_rank: Optional[int] = None
    previous_confidence: Optional[str] = None

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
            return f"(was {self.previous_confidence})"
        elif self.status == DifferentialStatus.CONFIDENCE_DOWN:
            return f"(was {self.previous_confidence})"
        return ""


class DifferentialTracker:
    """Tracks differential diagnosis evolution across analyses."""

    # Confidence level ordering for comparison
    CONFIDENCE_ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

    def __init__(self):
        """Initialize the tracker."""
        self.previous_differentials: List[Differential] = []
        self.removed_differentials: List[Differential] = []

    def clear(self) -> None:
        """Clear all tracked differentials."""
        self.previous_differentials = []
        self.removed_differentials = []
        logger.info("Differential tracker cleared")

    def parse_differentials(self, analysis_text: str) -> List[Differential]:
        """Parse differential diagnoses from analysis text.

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

            # Pattern to match numbered differentials
            # Format: "1. [Diagnosis] - [HIGH/MEDIUM/LOW confidence]"
            pattern = r'(\d+)\.\s*([^-\n]+?)\s*-\s*(HIGH|MEDIUM|LOW)\s*(?:confidence)?'

            matches = re.finditer(pattern, diff_section, re.IGNORECASE)

            for match in matches:
                rank = int(match.group(1))
                diagnosis = match.group(2).strip()
                confidence = match.group(3).upper()

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
        """Determine the evolution status between previous and current differential."""
        prev_conf_level = self.CONFIDENCE_ORDER.get(prev.confidence, 0)
        curr_conf_level = self.CONFIDENCE_ORDER.get(curr.confidence, 0)

        # Check rank change first
        if curr.rank < prev.rank:
            return DifferentialStatus.MOVED_UP
        elif curr.rank > prev.rank:
            return DifferentialStatus.MOVED_DOWN

        # Same rank, check confidence change
        if curr_conf_level > prev_conf_level:
            return DifferentialStatus.CONFIDENCE_UP
        elif curr_conf_level < prev_conf_level:
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
                lines.append(f"   • {e.differential.diagnosis} ({e.differential.confidence})")

        if moved_up:
            lines.append("\n⬆️ MOVED UP:")
            for e in moved_up:
                lines.append(f"   • {e.differential.diagnosis}: #{e.previous_rank} → #{e.differential.rank}")

        if moved_down:
            lines.append("\n⬇️ MOVED DOWN:")
            for e in moved_down:
                lines.append(f"   • {e.differential.diagnosis}: #{e.previous_rank} → #{e.differential.rank}")

        if conf_up:
            lines.append("\n📈 CONFIDENCE INCREASED:")
            for e in conf_up:
                lines.append(f"   • {e.differential.diagnosis}: {e.previous_confidence} → {e.differential.confidence}")

        if conf_down:
            lines.append("\n📉 CONFIDENCE DECREASED:")
            for e in conf_down:
                lines.append(f"   • {e.differential.diagnosis}: {e.previous_confidence} → {e.differential.confidence}")

        if removed:
            lines.append("\n❌ REMOVED:")
            for d in removed:
                lines.append(f"   • {d.diagnosis} (was #{d.rank}, {d.confidence})")

        if unchanged:
            lines.append(f"\n➡️ UNCHANGED: {len(unchanged)} diagnosis(es)")

        lines.append("")

        return "\n".join(lines)
