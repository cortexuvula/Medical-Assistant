"""
Advanced Search Syntax Parser for RAG.

Parses advanced search syntax including:
- type:pdf - Document type filter
- date:2024, date:last-month - Date range filters
- entity:medication:aspirin - Entity filters
- score:>0.8 - Minimum score threshold
- -term - Exclusion terms
- "exact phrase" - Exact phrase matching
"""

import re
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ParsedQuery:
    """Parsed search query with extracted filters."""
    text: str  # Main search text after filter extraction
    original_query: str  # Original unmodified query
    document_types: list[str] = field(default_factory=list)  # ["pdf", "docx"]
    date_range: Optional[tuple[datetime, datetime]] = None  # (start, end)
    entity_filters: dict[str, list[str]] = field(default_factory=dict)  # {"medication": ["aspirin"]}
    exclude_terms: list[str] = field(default_factory=list)  # Terms prefixed with -
    exact_phrases: list[str] = field(default_factory=list)  # Quoted phrases
    min_score: float = 0.0  # Minimum similarity score threshold

    @property
    def has_filters(self) -> bool:
        """Check if any filters are active."""
        return bool(
            self.document_types or
            self.date_range or
            self.entity_filters or
            self.exclude_terms or
            self.exact_phrases or
            self.min_score > 0
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "text": self.text,
            "original_query": self.original_query,
            "document_types": self.document_types,
            "date_range": [d.isoformat() for d in self.date_range] if self.date_range else None,
            "entity_filters": self.entity_filters,
            "exclude_terms": self.exclude_terms,
            "exact_phrases": self.exact_phrases,
            "min_score": self.min_score
        }


class SearchSyntaxParser:
    """Parses advanced search syntax for RAG queries."""

    # Regex patterns for syntax elements
    PATTERNS = {
        "type": re.compile(r'\btype:(\w+)\b', re.IGNORECASE),
        "date": re.compile(r'\bdate:([^\s]+)\b', re.IGNORECASE),
        "entity": re.compile(r'\bentity:(\w+):([^\s]+)\b', re.IGNORECASE),
        "score": re.compile(r'\bscore:>(\d+\.?\d*)\b', re.IGNORECASE),
        "exclude": re.compile(r'(?:^|\s)-(\w+)\b'),
        "exact": re.compile(r'"([^"]+)"'),
    }

    # Supported document types
    SUPPORTED_TYPES = ["pdf", "docx", "txt", "image", "png", "jpg", "jpeg"]

    # Date range aliases
    DATE_ALIASES = {
        "today": lambda: (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),
                          datetime.now()),
        "yesterday": lambda: (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1),
                              datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)),
        "last-week": lambda: (datetime.now() - timedelta(days=7), datetime.now()),
        "last-month": lambda: (datetime.now() - timedelta(days=30), datetime.now()),
        "last-year": lambda: (datetime.now() - timedelta(days=365), datetime.now()),
        "this-week": lambda: (datetime.now() - timedelta(days=datetime.now().weekday()),
                              datetime.now()),
        "this-month": lambda: (datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0),
                               datetime.now()),
        "this-year": lambda: (datetime.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0),
                              datetime.now()),
    }

    # Entity type normalization
    ENTITY_TYPE_ALIASES = {
        "med": "medication",
        "medication": "medication",
        "drug": "medication",
        "condition": "condition",
        "disease": "condition",
        "diagnosis": "condition",
        "symptom": "symptom",
        "sx": "symptom",
        "procedure": "procedure",
        "lab": "lab_test",
        "test": "lab_test",
        "anatomy": "anatomy",
        "body": "anatomy",
    }

    def parse(self, query: str) -> ParsedQuery:
        """Parse a query string with advanced syntax.

        Args:
            query: Raw query string with potential filters

        Returns:
            ParsedQuery with extracted filters and clean text
        """
        parsed = ParsedQuery(
            text="",
            original_query=query
        )

        working_query = query

        # Extract document types
        working_query, doc_types = self._extract_types(working_query)
        parsed.document_types = doc_types

        # Extract date ranges
        working_query, date_range = self._extract_dates(working_query)
        parsed.date_range = date_range

        # Extract entity filters
        working_query, entities = self._extract_entities(working_query)
        parsed.entity_filters = entities

        # Extract minimum score
        working_query, min_score = self._extract_min_score(working_query)
        parsed.min_score = min_score

        # Extract exclusions
        working_query, excludes = self._extract_excludes(working_query)
        parsed.exclude_terms = excludes

        # Extract exact phrases
        working_query, phrases = self._extract_phrases(working_query)
        parsed.exact_phrases = phrases

        # Clean up remaining text
        parsed.text = self._clean_query(working_query)

        logger.debug(
            f"Parsed query: text='{parsed.text}', "
            f"types={parsed.document_types}, "
            f"date_range={parsed.date_range is not None}, "
            f"entities={len(parsed.entity_filters)}, "
            f"excludes={len(parsed.exclude_terms)}, "
            f"phrases={len(parsed.exact_phrases)}, "
            f"min_score={parsed.min_score}"
        )

        return parsed

    def _extract_types(self, query: str) -> tuple[str, list[str]]:
        """Extract document type filters from query.

        Args:
            query: Query string

        Returns:
            Tuple of (remaining query, list of document types)
        """
        types = []
        matches = self.PATTERNS["type"].findall(query)

        for match in matches:
            type_lower = match.lower()
            if type_lower in self.SUPPORTED_TYPES:
                # Normalize image types
                if type_lower in ["png", "jpg", "jpeg"]:
                    type_lower = "image"
                if type_lower not in types:
                    types.append(type_lower)

        # Remove type patterns from query
        query = self.PATTERNS["type"].sub("", query)
        return query, types

    def _extract_dates(self, query: str) -> tuple[str, Optional[tuple[datetime, datetime]]]:
        """Extract date range filters from query.

        Args:
            query: Query string

        Returns:
            Tuple of (remaining query, date range or None)
        """
        matches = self.PATTERNS["date"].findall(query)

        if not matches:
            return query, None

        date_str = matches[0].lower()

        # Check for aliases
        if date_str in self.DATE_ALIASES:
            date_range = self.DATE_ALIASES[date_str]()
            query = self.PATTERNS["date"].sub("", query)
            return query, date_range

        # Try to parse as year (e.g., "2024")
        try:
            year = int(date_str)
            if 1990 <= year <= 2100:
                start = datetime(year, 1, 1)
                end = datetime(year, 12, 31, 23, 59, 59)
                query = self.PATTERNS["date"].sub("", query)
                return query, (start, end)
        except ValueError:
            pass

        # Try to parse as YYYY-MM
        try:
            dt = datetime.strptime(date_str, "%Y-%m")
            start = dt.replace(day=1)
            # Get last day of month
            if dt.month == 12:
                end = dt.replace(year=dt.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end = dt.replace(month=dt.month + 1, day=1) - timedelta(days=1)
            end = end.replace(hour=23, minute=59, second=59)
            query = self.PATTERNS["date"].sub("", query)
            return query, (start, end)
        except ValueError:
            pass

        # Try to parse as YYYY-MM-DD
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            start = dt.replace(hour=0, minute=0, second=0)
            end = dt.replace(hour=23, minute=59, second=59)
            query = self.PATTERNS["date"].sub("", query)
            return query, (start, end)
        except ValueError:
            pass

        logger.debug(f"Could not parse date: {date_str}")
        query = self.PATTERNS["date"].sub("", query)
        return query, None

    def _extract_entities(self, query: str) -> tuple[str, dict[str, list[str]]]:
        """Extract entity filters from query.

        Args:
            query: Query string

        Returns:
            Tuple of (remaining query, entity filters dict)
        """
        entities = {}
        matches = self.PATTERNS["entity"].findall(query)

        for entity_type, entity_value in matches:
            # Normalize entity type
            type_lower = entity_type.lower()
            normalized_type = self.ENTITY_TYPE_ALIASES.get(type_lower, type_lower)

            if normalized_type not in entities:
                entities[normalized_type] = []

            # Handle comma-separated values
            for value in entity_value.split(','):
                value = value.strip()
                if value and value not in entities[normalized_type]:
                    entities[normalized_type].append(value)

        # Remove entity patterns from query
        query = self.PATTERNS["entity"].sub("", query)
        return query, entities

    def _extract_min_score(self, query: str) -> tuple[str, float]:
        """Extract minimum score threshold from query.

        Args:
            query: Query string

        Returns:
            Tuple of (remaining query, minimum score)
        """
        matches = self.PATTERNS["score"].findall(query)

        if not matches:
            return query, 0.0

        try:
            score = float(matches[0])
            # Normalize to 0-1 range
            if score > 1:
                score = score / 100.0
            score = max(0.0, min(1.0, score))
        except ValueError:
            score = 0.0

        query = self.PATTERNS["score"].sub("", query)
        return query, score

    def _extract_excludes(self, query: str) -> tuple[str, list[str]]:
        """Extract exclusion terms from query.

        Args:
            query: Query string

        Returns:
            Tuple of (remaining query, list of exclusion terms)
        """
        excludes = []
        matches = self.PATTERNS["exclude"].findall(query)

        for term in matches:
            if term and term not in excludes:
                excludes.append(term.lower())

        # Remove exclusion patterns from query
        query = self.PATTERNS["exclude"].sub(" ", query)
        return query, excludes

    def _extract_phrases(self, query: str) -> tuple[str, list[str]]:
        """Extract exact phrase matches from query.

        Args:
            query: Query string

        Returns:
            Tuple of (remaining query, list of exact phrases)
        """
        phrases = []
        matches = self.PATTERNS["exact"].findall(query)

        for phrase in matches:
            if phrase and phrase not in phrases:
                phrases.append(phrase)

        # Remove phrase patterns from query (keep phrases in clean text too)
        # But remove the quotes
        query = self.PATTERNS["exact"].sub(r"\1", query)
        return query, phrases

    def _clean_query(self, query: str) -> str:
        """Clean up query after filter extraction.

        Args:
            query: Query with filters removed

        Returns:
            Clean query text
        """
        # Remove multiple spaces
        query = re.sub(r'\s+', ' ', query)
        # Remove leading/trailing whitespace
        query = query.strip()
        return query

    def format_help(self) -> str:
        """Get help text for search syntax.

        Returns:
            Formatted help string
        """
        return """
Advanced Search Syntax:

Document Type Filters:
  type:pdf          Search only PDF documents
  type:docx         Search only Word documents
  type:txt          Search only text files

Date Filters:
  date:today        Documents from today
  date:yesterday    Documents from yesterday
  date:last-week    Documents from last 7 days
  date:last-month   Documents from last 30 days
  date:this-year    Documents from this year
  date:2024         Documents from 2024
  date:2024-06      Documents from June 2024

Entity Filters:
  entity:medication:aspirin    Find documents about aspirin
  entity:condition:diabetes    Find documents about diabetes
  entity:symptom:pain          Find documents about pain

Score Threshold:
  score:>0.8        Only results with similarity > 80%
  score:>50         Only results with similarity > 50%

Exclusions:
  -deprecated       Exclude results containing "deprecated"
  -old              Exclude results containing "old"

Exact Phrases:
  "heart failure"   Match exact phrase "heart failure"
  "blood pressure"  Match exact phrase "blood pressure"

Examples:
  diabetes treatment type:pdf date:last-year
  "myocardial infarction" entity:medication:aspirin
  hypertension type:docx -outdated score:>0.7
"""


# Singleton instance
_parser: Optional[SearchSyntaxParser] = None


def get_search_syntax_parser() -> SearchSyntaxParser:
    """Get the global search syntax parser instance.

    Returns:
        SearchSyntaxParser instance
    """
    global _parser
    if _parser is None:
        _parser = SearchSyntaxParser()
    return _parser


def parse_search_query(query: str) -> ParsedQuery:
    """Convenience function to parse a search query.

    Args:
        query: Raw query string

    Returns:
        ParsedQuery with extracted filters
    """
    parser = get_search_syntax_parser()
    return parser.parse(query)
