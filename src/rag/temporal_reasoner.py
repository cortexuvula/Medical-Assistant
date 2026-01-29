"""
Temporal Reasoning for RAG System.

Provides time-aware query handling including:
- Temporal keyword detection
- Time-based result filtering
- Relevance decay for older information
"""

from utils.structured_logging import get_logger
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

logger = get_logger(__name__)


@dataclass
class TemporalQuery:
    """Parsed temporal aspects of a query."""
    has_temporal_reference: bool = False
    time_frame: Optional[str] = None  # "recent", "last_week", "before_2024"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    temporal_keywords: list[str] = field(default_factory=list)
    decay_factor: float = 1.0  # 0.0 = no decay (explicit temporal), 1.0 = full decay

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "has_temporal_reference": self.has_temporal_reference,
            "time_frame": self.time_frame,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "temporal_keywords": self.temporal_keywords,
            "decay_factor": self.decay_factor,
        }


class TemporalReasoner:
    """Handles temporal aspects of knowledge graph queries.

    Provides:
    - Temporal keyword detection in queries
    - Time range filtering for results
    - Relevance decay for older information
    """

    # Temporal keyword patterns with their time deltas
    TEMPORAL_PATTERNS = {
        "recent": timedelta(days=30),
        "recently": timedelta(days=30),
        "latest": timedelta(days=7),
        "newest": timedelta(days=7),
        "last week": timedelta(weeks=1),
        "past week": timedelta(weeks=1),
        "last month": timedelta(days=30),
        "past month": timedelta(days=30),
        "last year": timedelta(days=365),
        "past year": timedelta(days=365),
        "this year": None,  # Special handling - year to date
        "this month": None,  # Special handling - month to date
        "current": timedelta(days=14),
        "currently": timedelta(days=14),
        "today": timedelta(days=1),
        "yesterday": timedelta(days=2),
        "last few days": timedelta(days=7),
        "past few days": timedelta(days=7),
        "last few weeks": timedelta(weeks=3),
        "past few weeks": timedelta(weeks=3),
        "2024": None,  # Year reference
        "2025": None,
        "2026": None,
    }

    # Decay constants
    DEFAULT_HALF_LIFE_DAYS = 180  # Info loses half relevance in 6 months
    MAX_DECAY = 0.5  # Don't reduce below 50% relevance
    MIN_DECAY = 0.95  # Start decay from 95% (5% penalty for any age)

    def __init__(
        self,
        half_life_days: int = 180,
        max_decay: float = 0.5,
        enable_decay: bool = True
    ):
        """Initialize the temporal reasoner.

        Args:
            half_life_days: Days until information loses half its relevance
            max_decay: Maximum decay (minimum relevance multiplier)
            enable_decay: Whether to apply time decay
        """
        self.half_life_days = half_life_days
        self.max_decay = max_decay
        self.enable_decay = enable_decay

    def parse_temporal_query(self, query: str) -> TemporalQuery:
        """Extract temporal references from a query.

        Args:
            query: Search query text

        Returns:
            TemporalQuery with parsed temporal information
        """
        query_lower = query.lower()
        now = datetime.now()

        # Check for year references (2024, 2025, etc.)
        year_match = re.search(r'\b(20\d{2})\b', query)
        if year_match:
            year = int(year_match.group(1))
            return TemporalQuery(
                has_temporal_reference=True,
                time_frame=f"year_{year}",
                start_date=datetime(year, 1, 1),
                end_date=datetime(year, 12, 31, 23, 59, 59),
                temporal_keywords=[year_match.group(1)],
                decay_factor=0.0  # No decay for explicit temporal
            )

        # Check for temporal keyword patterns
        matched_keywords = []
        earliest_start = None
        latest_end = now

        for pattern, delta in self.TEMPORAL_PATTERNS.items():
            if pattern in query_lower:
                matched_keywords.append(pattern)

                if delta:
                    # Calculate date range from delta
                    start_date = now - delta
                    if earliest_start is None or start_date < earliest_start:
                        earliest_start = start_date
                else:
                    # Handle special cases
                    if pattern == "this year":
                        earliest_start = datetime(now.year, 1, 1)
                    elif pattern == "this month":
                        earliest_start = datetime(now.year, now.month, 1)

        if matched_keywords:
            return TemporalQuery(
                has_temporal_reference=True,
                time_frame=matched_keywords[0],  # Primary time frame
                start_date=earliest_start,
                end_date=latest_end,
                temporal_keywords=matched_keywords,
                decay_factor=0.0  # No decay for explicit temporal queries
            )

        # No explicit temporal reference - use default decay
        return TemporalQuery(
            has_temporal_reference=False,
            time_frame=None,
            start_date=None,
            end_date=None,
            temporal_keywords=[],
            decay_factor=1.0  # Full decay
        )

    def calculate_time_decay(
        self,
        created_at: datetime,
        reference_time: Optional[datetime] = None
    ) -> float:
        """Calculate time-based relevance decay factor.

        Uses exponential decay based on half-life:
        decay = 2^(-age_days / half_life_days)

        Args:
            created_at: When the content was created
            reference_time: Reference time (defaults to now)

        Returns:
            Decay multiplier (1.0 = no decay, lower = more decay)
        """
        if not self.enable_decay or not created_at:
            return 1.0

        if reference_time is None:
            reference_time = datetime.now()

        # Calculate age in days
        age = reference_time - created_at
        age_days = age.total_seconds() / 86400  # Convert to days

        if age_days <= 0:
            return self.MIN_DECAY  # Very recent, minimal decay

        # Exponential decay
        decay = 2 ** (-age_days / self.half_life_days)

        # Apply bounds
        decay = max(self.max_decay, min(self.MIN_DECAY, decay))

        return decay

    def apply_time_decay(
        self,
        results: list,
        temporal_query: TemporalQuery,
        score_field: str = "combined_score",
        timestamp_field: str = "created_at"
    ) -> list:
        """Apply time-based relevance decay to search results.

        Args:
            results: List of result objects
            temporal_query: Parsed temporal query
            score_field: Name of score attribute to modify
            timestamp_field: Name of timestamp attribute

        Returns:
            Results with adjusted scores
        """
        if not self.enable_decay:
            return results

        # Skip decay for explicit temporal queries
        if not temporal_query.decay_factor:
            return results

        now = datetime.now()

        for result in results:
            # Get timestamp from result
            created_at = None

            # Try to get timestamp from various possible locations
            if hasattr(result, timestamp_field):
                created_at = getattr(result, timestamp_field)
            elif hasattr(result, "metadata") and result.metadata:
                if timestamp_field in result.metadata:
                    created_at = result.metadata[timestamp_field]
                elif "created_at" in result.metadata:
                    created_at = result.metadata["created_at"]

            # Convert string to datetime if needed
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    created_at = None

            if not created_at:
                continue

            # Calculate decay
            decay = self.calculate_time_decay(created_at, now)

            # Apply decay to score
            if hasattr(result, score_field):
                current_score = getattr(result, score_field)
                adjusted_score = current_score * decay
                setattr(result, score_field, adjusted_score)

                # Store decay info for transparency
                if hasattr(result, "__dict__"):
                    result.temporal_decay = 1 - decay

        # Re-sort by adjusted score
        if results and hasattr(results[0], score_field):
            results.sort(key=lambda x: getattr(x, score_field, 0), reverse=True)

        return results

    def filter_by_time_range(
        self,
        results: list,
        start_date: datetime,
        end_date: datetime,
        timestamp_field: str = "created_at"
    ) -> list:
        """Filter results to a specific time range.

        Args:
            results: List of result objects
            start_date: Start of time range (inclusive)
            end_date: End of time range (inclusive)
            timestamp_field: Name of timestamp attribute

        Returns:
            Filtered list of results
        """
        if not start_date and not end_date:
            return results

        filtered = []

        for result in results:
            # Get timestamp
            created_at = None

            if hasattr(result, timestamp_field):
                created_at = getattr(result, timestamp_field)
            elif hasattr(result, "metadata") and result.metadata:
                if timestamp_field in result.metadata:
                    created_at = result.metadata[timestamp_field]
                elif "created_at" in result.metadata:
                    created_at = result.metadata["created_at"]

            # Convert string to datetime if needed
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    created_at = None

            # No timestamp - include by default (or could exclude)
            if not created_at:
                filtered.append(result)
                continue

            # Check range
            in_range = True
            if start_date and created_at < start_date:
                in_range = False
            if end_date and created_at > end_date:
                in_range = False

            if in_range:
                filtered.append(result)

        return filtered

    def process_results(
        self,
        results: list,
        temporal_query: TemporalQuery,
        score_field: str = "combined_score",
        timestamp_field: str = "created_at"
    ) -> list:
        """Process results with temporal reasoning.

        Applies both filtering and decay as appropriate.

        Args:
            results: Search results
            temporal_query: Parsed temporal query
            score_field: Score attribute name
            timestamp_field: Timestamp attribute name

        Returns:
            Processed results
        """
        # Step 1: Filter by time range if explicit temporal reference
        if temporal_query.has_temporal_reference and temporal_query.start_date:
            results = self.filter_by_time_range(
                results,
                temporal_query.start_date,
                temporal_query.end_date,
                timestamp_field
            )

        # Step 2: Apply time decay if no explicit temporal reference
        if not temporal_query.has_temporal_reference:
            results = self.apply_time_decay(
                results,
                temporal_query,
                score_field,
                timestamp_field
            )

        return results

    def get_time_frame_description(self, temporal_query: TemporalQuery) -> str:
        """Get human-readable description of the time frame.

        Args:
            temporal_query: Parsed temporal query

        Returns:
            Description string
        """
        if not temporal_query.has_temporal_reference:
            return "all time"

        if temporal_query.time_frame:
            if temporal_query.time_frame.startswith("year_"):
                return temporal_query.time_frame.replace("year_", "")

            return temporal_query.time_frame

        if temporal_query.start_date and temporal_query.end_date:
            start = temporal_query.start_date.strftime("%Y-%m-%d")
            end = temporal_query.end_date.strftime("%Y-%m-%d")
            return f"{start} to {end}"

        return "specified time range"


# Singleton instance
_reasoner: Optional[TemporalReasoner] = None


def get_temporal_reasoner() -> TemporalReasoner:
    """Get the global temporal reasoner instance.

    Returns:
        TemporalReasoner instance
    """
    global _reasoner
    if _reasoner is None:
        _reasoner = TemporalReasoner()
    return _reasoner


def parse_temporal_query(query: str) -> TemporalQuery:
    """Convenience function to parse temporal aspects of a query.

    Args:
        query: Search query text

    Returns:
        TemporalQuery
    """
    reasoner = get_temporal_reasoner()
    return reasoner.parse_temporal_query(query)
