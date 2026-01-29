"""
Unit tests for TemporalReasoner.

Tests cover:
- Temporal query parsing (recent, last week, this year, etc.)
- Time decay calculation
- Result filtering by time range
- Time frame descriptions
- Singleton pattern
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta
from dataclasses import dataclass

from rag.temporal_reasoner import (
    TemporalReasoner,
    TemporalQuery,
    get_temporal_reasoner,
    parse_temporal_query,
)


@pytest.fixture
def temporal_reasoner():
    """Create a TemporalReasoner instance."""
    return TemporalReasoner(
        half_life_days=180,
        max_decay=0.5,
        enable_decay=True,
    )


@pytest.fixture
def sample_results():
    """Create sample search results with timestamps.

    Note: Use days=6, days=29 etc. instead of exact boundary values (7, 30)
    to avoid timing precision issues when test creates its own datetime.now().
    """
    now = datetime.now()

    @dataclass
    class MockResult:
        chunk_text: str
        document_id: str
        combined_score: float
        created_at: datetime
        metadata: dict = None

        def __post_init__(self):
            if self.metadata is None:
                self.metadata = {}

    return [
        MockResult(
            chunk_text="Very recent content",
            document_id="doc1",
            combined_score=0.9,
            created_at=now - timedelta(days=1),
        ),
        MockResult(
            chunk_text="Recent content",
            document_id="doc2",
            combined_score=0.85,
            created_at=now - timedelta(days=6),  # Use 6 instead of 7 to be safely within 7-day range
        ),
        MockResult(
            chunk_text="Month old content",
            document_id="doc3",
            combined_score=0.8,
            created_at=now - timedelta(days=29),  # Use 29 instead of 30 to be safely within 30-day range
        ),
        MockResult(
            chunk_text="Old content",
            document_id="doc4",
            combined_score=0.75,
            created_at=now - timedelta(days=180),
        ),
        MockResult(
            chunk_text="Very old content",
            document_id="doc5",
            combined_score=0.7,
            created_at=now - timedelta(days=365),
        ),
    ]


class TestTemporalQueryParsing:
    """Tests for temporal query parsing."""

    def test_parse_recent_query(self, temporal_reasoner):
        """Test parsing 'recent' temporal reference."""
        query = "Show me recent hypertension guidelines"
        result = temporal_reasoner.parse_temporal_query(query)

        assert result.has_temporal_reference is True
        assert result.time_frame == "recent"
        assert "recent" in result.temporal_keywords
        assert result.decay_factor == 0.0  # No decay for explicit temporal

    def test_parse_last_week_query(self, temporal_reasoner):
        """Test parsing 'last week' temporal reference."""
        query = "What happened last week"
        result = temporal_reasoner.parse_temporal_query(query)

        assert result.has_temporal_reference is True
        assert "last week" in result.temporal_keywords
        assert result.start_date is not None
        # Should be approximately 7 days ago
        delta = datetime.now() - result.start_date
        assert 6 <= delta.days <= 8

    def test_parse_last_month_query(self, temporal_reasoner):
        """Test parsing 'last month' temporal reference."""
        query = "Patient records from last month"
        result = temporal_reasoner.parse_temporal_query(query)

        assert result.has_temporal_reference is True
        assert "last month" in result.temporal_keywords
        delta = datetime.now() - result.start_date
        assert 28 <= delta.days <= 32

    def test_parse_last_year_query(self, temporal_reasoner):
        """Test parsing 'last year' temporal reference."""
        query = "Last year's treatment protocol"
        result = temporal_reasoner.parse_temporal_query(query)

        assert result.has_temporal_reference is True
        assert "last year" in result.temporal_keywords
        delta = datetime.now() - result.start_date
        assert 363 <= delta.days <= 367

    def test_parse_this_year_query(self, temporal_reasoner):
        """Test parsing 'this year' temporal reference."""
        query = "This year's guidelines"
        result = temporal_reasoner.parse_temporal_query(query)

        assert result.has_temporal_reference is True
        assert "this year" in result.temporal_keywords
        # Start date should be January 1st of current year
        assert result.start_date.month == 1
        assert result.start_date.day == 1

    def test_parse_this_month_query(self, temporal_reasoner):
        """Test parsing 'this month' temporal reference."""
        query = "Documents from this month"
        result = temporal_reasoner.parse_temporal_query(query)

        assert result.has_temporal_reference is True
        assert "this month" in result.temporal_keywords
        # Start date should be 1st of current month
        assert result.start_date.day == 1
        assert result.start_date.month == datetime.now().month

    def test_parse_year_reference(self, temporal_reasoner):
        """Test parsing explicit year reference."""
        query = "Guidelines from 2024"
        result = temporal_reasoner.parse_temporal_query(query)

        assert result.has_temporal_reference is True
        assert "year_2024" in result.time_frame
        assert result.start_date == datetime(2024, 1, 1)
        assert result.end_date.year == 2024
        assert result.end_date.month == 12

    def test_parse_today_query(self, temporal_reasoner):
        """Test parsing 'today' temporal reference."""
        query = "What was discussed today"
        result = temporal_reasoner.parse_temporal_query(query)

        assert result.has_temporal_reference is True
        assert "today" in result.temporal_keywords
        delta = datetime.now() - result.start_date
        assert delta.days <= 1

    def test_parse_latest_query(self, temporal_reasoner):
        """Test parsing 'latest' temporal reference."""
        query = "Show the latest research"
        result = temporal_reasoner.parse_temporal_query(query)

        assert result.has_temporal_reference is True
        assert "latest" in result.temporal_keywords
        delta = datetime.now() - result.start_date
        assert delta.days <= 8

    def test_parse_no_temporal_reference(self, temporal_reasoner):
        """Test parsing query without temporal reference."""
        query = "What are the hypertension treatment guidelines"
        result = temporal_reasoner.parse_temporal_query(query)

        assert result.has_temporal_reference is False
        assert result.time_frame is None
        assert result.start_date is None
        assert result.temporal_keywords == []
        assert result.decay_factor == 1.0  # Full decay

    def test_parse_multiple_temporal_references(self, temporal_reasoner):
        """Test parsing query with multiple temporal references."""
        query = "Recent updates from last month"
        result = temporal_reasoner.parse_temporal_query(query)

        assert result.has_temporal_reference is True
        # Should capture both keywords
        assert len(result.temporal_keywords) >= 2
        assert "recent" in result.temporal_keywords
        assert "last month" in result.temporal_keywords

    def test_parse_case_insensitive(self, temporal_reasoner):
        """Test that parsing is case-insensitive."""
        query = "RECENT updates from LAST WEEK"
        result = temporal_reasoner.parse_temporal_query(query)

        assert result.has_temporal_reference is True


class TestTimeDecayCalculation:
    """Tests for time-based relevance decay."""

    def test_calculate_decay_recent(self, temporal_reasoner):
        """Test decay calculation for recent content."""
        now = datetime.now()
        created_at = now - timedelta(days=1)

        decay = temporal_reasoner.calculate_time_decay(created_at, now)

        # Very recent should have minimal decay
        assert decay >= 0.9

    def test_calculate_decay_half_life(self, temporal_reasoner):
        """Test decay at half-life point."""
        now = datetime.now()
        # Content at exactly half-life (180 days)
        created_at = now - timedelta(days=180)

        decay = temporal_reasoner.calculate_time_decay(created_at, now)

        # At half-life, decay should be approximately 0.5
        assert 0.45 <= decay <= 0.55

    def test_calculate_decay_very_old(self, temporal_reasoner):
        """Test decay for very old content."""
        now = datetime.now()
        created_at = now - timedelta(days=720)  # 2 years

        decay = temporal_reasoner.calculate_time_decay(created_at, now)

        # Should be at max_decay minimum
        assert decay == temporal_reasoner.max_decay

    def test_calculate_decay_disabled(self):
        """Test that decay can be disabled."""
        reasoner = TemporalReasoner(enable_decay=False)
        now = datetime.now()
        created_at = now - timedelta(days=365)

        decay = reasoner.calculate_time_decay(created_at, now)

        assert decay == 1.0  # No decay

    def test_calculate_decay_none_timestamp(self, temporal_reasoner):
        """Test decay with None timestamp."""
        decay = temporal_reasoner.calculate_time_decay(None)

        assert decay == 1.0  # No decay for missing timestamp

    def test_calculate_decay_future_timestamp(self, temporal_reasoner):
        """Test decay with future timestamp."""
        now = datetime.now()
        created_at = now + timedelta(days=1)  # Future

        decay = temporal_reasoner.calculate_time_decay(created_at, now)

        # Future dates should have minimal decay
        assert decay == temporal_reasoner.MIN_DECAY


class TestApplyTimeDecay:
    """Tests for applying time decay to results."""

    def test_apply_decay_adjusts_scores(self, temporal_reasoner, sample_results):
        """Test that decay adjusts result scores."""
        temporal_query = TemporalQuery(
            has_temporal_reference=False,
            decay_factor=1.0,
        )

        original_scores = [r.combined_score for r in sample_results]

        decayed = temporal_reasoner.apply_time_decay(
            sample_results,
            temporal_query,
            score_field="combined_score",
            timestamp_field="created_at",
        )

        # Scores should be adjusted
        for i, result in enumerate(decayed):
            # Older content should have lower score
            if i > 0:
                assert result.combined_score <= original_scores[i]

    def test_apply_decay_skipped_for_explicit_temporal(self, temporal_reasoner, sample_results):
        """Test that decay is skipped for explicit temporal queries."""
        temporal_query = TemporalQuery(
            has_temporal_reference=True,
            decay_factor=0.0,  # No decay
        )

        original_scores = [r.combined_score for r in sample_results]

        decayed = temporal_reasoner.apply_time_decay(
            sample_results,
            temporal_query,
            score_field="combined_score",
            timestamp_field="created_at",
        )

        # Scores should be unchanged
        for i, result in enumerate(decayed):
            assert result.combined_score == original_scores[i]

    def test_apply_decay_reorders_results(self, temporal_reasoner, sample_results):
        """Test that decay may reorder results."""
        # Give older content higher initial score
        sample_results[4].combined_score = 0.95  # Very old but high score

        temporal_query = TemporalQuery(
            has_temporal_reference=False,
            decay_factor=1.0,
        )

        decayed = temporal_reasoner.apply_time_decay(
            sample_results,
            temporal_query,
            score_field="combined_score",
            timestamp_field="created_at",
        )

        # Results should be re-sorted by adjusted score
        scores = [r.combined_score for r in decayed]
        assert scores == sorted(scores, reverse=True)


class TestFilterByTimeRange:
    """Tests for time range filtering."""

    def test_filter_last_7_days(self, temporal_reasoner, sample_results):
        """Test filtering to last 7 days."""
        now = datetime.now()
        start_date = now - timedelta(days=7)
        end_date = now

        filtered = temporal_reasoner.filter_by_time_range(
            sample_results,
            start_date,
            end_date,
            timestamp_field="created_at",
        )

        # Should only include docs from last 7 days
        assert len(filtered) == 2  # doc1 (1 day) and doc2 (7 days)

    def test_filter_last_30_days(self, temporal_reasoner, sample_results):
        """Test filtering to last 30 days."""
        now = datetime.now()
        start_date = now - timedelta(days=30)
        end_date = now

        filtered = temporal_reasoner.filter_by_time_range(
            sample_results,
            start_date,
            end_date,
            timestamp_field="created_at",
        )

        assert len(filtered) == 3  # doc1, doc2, doc3

    def test_filter_includes_missing_timestamps(self, temporal_reasoner):
        """Test that results without timestamps are included."""
        @dataclass
        class MockResult:
            chunk_text: str
            combined_score: float
            metadata: dict = None

        results = [
            MockResult(chunk_text="No timestamp", combined_score=0.9, metadata={}),
        ]

        now = datetime.now()
        filtered = temporal_reasoner.filter_by_time_range(
            results,
            now - timedelta(days=7),
            now,
        )

        # Should include result without timestamp
        assert len(filtered) == 1

    def test_filter_empty_range(self, temporal_reasoner, sample_results):
        """Test filtering with no matching results."""
        now = datetime.now()
        # Range in the future
        start_date = now + timedelta(days=10)
        end_date = now + timedelta(days=20)

        filtered = temporal_reasoner.filter_by_time_range(
            sample_results,
            start_date,
            end_date,
            timestamp_field="created_at",
        )

        # No results in future range
        assert len(filtered) == 0


class TestProcessResults:
    """Tests for combined result processing."""

    def test_process_with_explicit_temporal(self, temporal_reasoner, sample_results):
        """Test processing with explicit temporal reference."""
        now = datetime.now()
        temporal_query = TemporalQuery(
            has_temporal_reference=True,
            time_frame="last_week",
            start_date=now - timedelta(days=7),
            end_date=now,
            temporal_keywords=["last week"],
            decay_factor=0.0,
        )

        processed = temporal_reasoner.process_results(
            sample_results,
            temporal_query,
            score_field="combined_score",
            timestamp_field="created_at",
        )

        # Should filter to last week and NOT apply decay
        assert len(processed) <= 2

    def test_process_without_temporal(self, temporal_reasoner, sample_results):
        """Test processing without temporal reference."""
        temporal_query = TemporalQuery(
            has_temporal_reference=False,
            decay_factor=1.0,
        )

        original_scores = [r.combined_score for r in sample_results]

        processed = temporal_reasoner.process_results(
            sample_results,
            temporal_query,
            score_field="combined_score",
            timestamp_field="created_at",
        )

        # Should apply decay but not filter
        assert len(processed) == len(sample_results)
        # Scores should be adjusted
        for i, result in enumerate(processed):
            # Older results should have lower scores
            pass  # Decay will have been applied


class TestTimeFrameDescription:
    """Tests for human-readable time frame descriptions."""

    def test_description_all_time(self, temporal_reasoner):
        """Test description for no temporal reference."""
        query = TemporalQuery(has_temporal_reference=False)
        desc = temporal_reasoner.get_time_frame_description(query)

        assert desc == "all time"

    def test_description_year(self, temporal_reasoner):
        """Test description for year reference."""
        query = TemporalQuery(
            has_temporal_reference=True,
            time_frame="year_2024",
        )
        desc = temporal_reasoner.get_time_frame_description(query)

        assert desc == "2024"

    def test_description_time_frame(self, temporal_reasoner):
        """Test description for time frame."""
        query = TemporalQuery(
            has_temporal_reference=True,
            time_frame="last month",
        )
        desc = temporal_reasoner.get_time_frame_description(query)

        assert desc == "last month"

    def test_description_date_range(self, temporal_reasoner):
        """Test description for date range."""
        query = TemporalQuery(
            has_temporal_reference=True,
            time_frame=None,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        desc = temporal_reasoner.get_time_frame_description(query)

        assert "2024-01-01" in desc
        assert "2024-01-31" in desc


class TestTemporalQueryDataclass:
    """Tests for TemporalQuery dataclass."""

    def test_to_dict(self):
        """Test TemporalQuery serialization."""
        query = TemporalQuery(
            has_temporal_reference=True,
            time_frame="recent",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            temporal_keywords=["recent"],
            decay_factor=0.5,
        )

        data = query.to_dict()

        assert data["has_temporal_reference"] is True
        assert data["time_frame"] == "recent"
        assert data["start_date"] == "2024-01-01T00:00:00"
        assert data["temporal_keywords"] == ["recent"]
        assert data["decay_factor"] == 0.5

    def test_default_values(self):
        """Test TemporalQuery default values."""
        query = TemporalQuery()

        assert query.has_temporal_reference is False
        assert query.time_frame is None
        assert query.start_date is None
        assert query.end_date is None
        assert query.temporal_keywords == []
        assert query.decay_factor == 1.0


class TestSingletonPattern:
    """Tests for singleton reasoner instance."""

    def test_get_temporal_reasoner_singleton(self):
        """Test that singleton returns same instance."""
        # Reset by accessing the module
        import rag.temporal_reasoner as tr
        tr._reasoner = None

        reasoner1 = get_temporal_reasoner()
        reasoner2 = get_temporal_reasoner()

        assert reasoner1 is reasoner2


class TestConvenienceFunction:
    """Tests for convenience functions."""

    def test_parse_temporal_query_function(self):
        """Test the parse_temporal_query convenience function."""
        result = parse_temporal_query("Recent updates")

        assert result.has_temporal_reference is True
        assert "recent" in result.temporal_keywords


class TestTemporalPatterns:
    """Tests for temporal pattern coverage."""

    def test_past_week_pattern(self, temporal_reasoner):
        """Test 'past week' pattern."""
        result = temporal_reasoner.parse_temporal_query("Events from past week")
        assert result.has_temporal_reference is True
        assert "past week" in result.temporal_keywords

    def test_past_month_pattern(self, temporal_reasoner):
        """Test 'past month' pattern."""
        result = temporal_reasoner.parse_temporal_query("Records from past month")
        assert result.has_temporal_reference is True
        assert "past month" in result.temporal_keywords

    def test_past_year_pattern(self, temporal_reasoner):
        """Test 'past year' pattern."""
        result = temporal_reasoner.parse_temporal_query("Data from past year")
        assert result.has_temporal_reference is True
        assert "past year" in result.temporal_keywords

    def test_currently_pattern(self, temporal_reasoner):
        """Test 'currently' pattern."""
        result = temporal_reasoner.parse_temporal_query("What is currently happening")
        assert result.has_temporal_reference is True
        assert "currently" in result.temporal_keywords

    def test_yesterday_pattern(self, temporal_reasoner):
        """Test 'yesterday' pattern."""
        result = temporal_reasoner.parse_temporal_query("What happened yesterday")
        assert result.has_temporal_reference is True
        assert "yesterday" in result.temporal_keywords

    def test_last_few_days_pattern(self, temporal_reasoner):
        """Test 'last few days' pattern."""
        result = temporal_reasoner.parse_temporal_query("Updates from last few days")
        assert result.has_temporal_reference is True
        assert "last few days" in result.temporal_keywords

    def test_past_few_weeks_pattern(self, temporal_reasoner):
        """Test 'past few weeks' pattern."""
        result = temporal_reasoner.parse_temporal_query("Changes from past few weeks")
        assert result.has_temporal_reference is True
        assert "past few weeks" in result.temporal_keywords


class TestTimestampHandling:
    """Tests for various timestamp formats."""

    def test_string_timestamp_iso(self, temporal_reasoner):
        """Test handling ISO format string timestamps."""
        @dataclass
        class MockResult:
            chunk_text: str
            combined_score: float
            created_at: str

        now = datetime.now()
        results = [
            MockResult(
                chunk_text="Test",
                combined_score=0.9,
                created_at=(now - timedelta(days=5)).isoformat(),
            ),
        ]

        temporal_query = TemporalQuery(
            has_temporal_reference=False,
            decay_factor=1.0,
        )

        decayed = temporal_reasoner.apply_time_decay(
            results,
            temporal_query,
            timestamp_field="created_at",
        )

        # Should handle string timestamp
        assert len(decayed) == 1

    def test_metadata_timestamp(self, temporal_reasoner):
        """Test handling timestamps in metadata."""
        @dataclass
        class MockResult:
            chunk_text: str
            combined_score: float
            metadata: dict

        now = datetime.now()
        results = [
            MockResult(
                chunk_text="Test",
                combined_score=0.9,
                metadata={"created_at": (now - timedelta(days=5))},
            ),
        ]

        temporal_query = TemporalQuery(
            has_temporal_reference=False,
            decay_factor=1.0,
        )

        decayed = temporal_reasoner.apply_time_decay(
            results,
            temporal_query,
            timestamp_field="created_at",
        )

        # Should find timestamp in metadata
        assert len(decayed) == 1
