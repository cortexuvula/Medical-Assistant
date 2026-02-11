"""
Recommendation Class and Evidence Level Extractor.

Extracts structured metadata from clinical guideline text chunks:
- Recommendation class (I, IIa, IIb, III)
- Evidence level (A, B, B-R, B-NR, C, C-LD, C-EO)
- Section type (recommendation, warning, contraindication, monitoring, evidence, rationale)
"""

import re
from dataclasses import dataclass
from typing import Optional

from utils.structured_logging import get_logger

logger = get_logger(__name__)


@dataclass
class ExtractionResult:
    """Result of recommendation/evidence extraction from a text chunk."""
    section_type: str = "recommendation"
    recommendation_class: Optional[str] = None
    evidence_level: Optional[str] = None
    confidence: float = 0.0


# Recommendation class patterns (ordered by specificity)
_CLASS_PATTERNS = [
    # Explicit "Class IIa" / "COR IIa" notation
    (re.compile(r'\b(?:Class|COR)\s+(III)\b', re.IGNORECASE), "III"),
    (re.compile(r'\b(?:Class|COR)\s+(IIb)\b', re.IGNORECASE), "IIb"),
    (re.compile(r'\b(?:Class|COR)\s+(IIa)\b', re.IGNORECASE), "IIa"),
    (re.compile(r'\b(?:Class|COR)\s+(I)\b', re.IGNORECASE), "I"),
    # "Class of Recommendation: I" format
    (re.compile(r'(?:Class\s+of\s+Recommendation|COR)\s*[:=]\s*(III|IIb|IIa|I)\b', re.IGNORECASE), None),
    # Standalone in tables or headers: "I (Strong)" etc.
    (re.compile(r'\b(III)\s*\((?:No\s+Benefit|Harm)\)', re.IGNORECASE), "III"),
    (re.compile(r'\b(IIb)\s*\((?:Weak|May)\)', re.IGNORECASE), "IIb"),
    (re.compile(r'\b(IIa)\s*\((?:Moderate|Should)\)', re.IGNORECASE), "IIa"),
    (re.compile(r'\b(I)\s*\((?:Strong|Is\s+Recommended)\)', re.IGNORECASE), "I"),
]

# Evidence level patterns
_EVIDENCE_PATTERNS = [
    # Explicit "Level B-R" / "LOE B-R" notation
    (re.compile(r'\b(?:Level|LOE)\s+(C-EO)\b', re.IGNORECASE), "C-EO"),
    (re.compile(r'\b(?:Level|LOE)\s+(C-LD)\b', re.IGNORECASE), "C-LD"),
    (re.compile(r'\b(?:Level|LOE)\s+(B-NR)\b', re.IGNORECASE), "B-NR"),
    (re.compile(r'\b(?:Level|LOE)\s+(B-R)\b', re.IGNORECASE), "B-R"),
    (re.compile(r'\b(?:Level|LOE)\s+(C)\b', re.IGNORECASE), "C"),
    (re.compile(r'\b(?:Level|LOE)\s+(B)\b', re.IGNORECASE), "B"),
    (re.compile(r'\b(?:Level|LOE)\s+(A)\b', re.IGNORECASE), "A"),
    # "Level of Evidence: A" format
    (re.compile(r'(?:Level\s+of\s+Evidence|LOE)\s*[:=]\s*(C-EO|C-LD|B-NR|B-R|[ABC])\b', re.IGNORECASE), None),
    # "(Level A)" format
    (re.compile(r'\(Level\s+(C-EO|C-LD|B-NR|B-R|[ABC])\)', re.IGNORECASE), None),
]

# Section type detection patterns
_SECTION_TYPE_PATTERNS = [
    (re.compile(r'\b(?:WARNING|CAUTION|BLACK\s*BOX)\b', re.IGNORECASE), "warning"),
    (re.compile(r'\b(?:CONTRAINDICATION|CONTRAINDICATED|DO\s+NOT)\b', re.IGNORECASE), "contraindication"),
    (re.compile(r'\b(?:MONITOR|MONITORING|SURVEILLANCE|FOLLOW[- ]UP)\b', re.IGNORECASE), "monitoring"),
    (re.compile(r'\b(?:EVIDENCE|TRIAL|STUDY|RCT|META-ANALYSIS)\b', re.IGNORECASE), "evidence"),
    (re.compile(r'\b(?:RATIONALE|SUPPORTING\s+TEXT|BACKGROUND)\b', re.IGNORECASE), "rationale"),
]


class RecommendationExtractor:
    """Extracts recommendation class, evidence level, and section type
    from clinical guideline text chunks.
    """

    def extract(self, text: str) -> ExtractionResult:
        """Extract recommendation metadata from a text chunk.

        Args:
            text: Text content of a guideline chunk

        Returns:
            ExtractionResult with extracted metadata
        """
        if not text:
            return ExtractionResult()

        rec_class = self._extract_recommendation_class(text)
        evidence = self._extract_evidence_level(text)
        section_type = self._extract_section_type(text)

        # Calculate confidence based on what was found
        confidence = 0.0
        if rec_class:
            confidence += 0.4
        if evidence:
            confidence += 0.4
        if section_type != "recommendation":
            confidence += 0.2

        return ExtractionResult(
            section_type=section_type,
            recommendation_class=rec_class,
            evidence_level=evidence,
            confidence=confidence,
        )

    def _extract_recommendation_class(self, text: str) -> Optional[str]:
        """Extract recommendation class from text."""
        for pattern, fixed_value in _CLASS_PATTERNS:
            match = pattern.search(text)
            if match:
                if fixed_value:
                    return fixed_value
                # Use captured group
                return match.group(1).upper() if match.lastindex else None
        return None

    def _extract_evidence_level(self, text: str) -> Optional[str]:
        """Extract evidence level from text."""
        for pattern, fixed_value in _EVIDENCE_PATTERNS:
            match = pattern.search(text)
            if match:
                if fixed_value:
                    return fixed_value
                # Normalize captured group
                raw = match.group(1) if match.lastindex else None
                if raw:
                    return raw.upper()
        return None

    def _extract_section_type(self, text: str) -> str:
        """Detect section type from text content.

        Returns the most specific match, defaulting to 'recommendation'.
        """
        for pattern, section_type in _SECTION_TYPE_PATTERNS:
            if pattern.search(text):
                return section_type
        return "recommendation"

    def extract_batch(self, chunks: list[str]) -> list[ExtractionResult]:
        """Extract recommendation metadata from multiple chunks.

        Args:
            chunks: List of text chunks

        Returns:
            List of ExtractionResult objects, one per chunk
        """
        return [self.extract(chunk) for chunk in chunks]
