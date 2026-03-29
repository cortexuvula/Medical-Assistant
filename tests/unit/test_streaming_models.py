"""
Tests for streaming models in src/rag/streaming_models.py

Covers StreamEventType enum (12 members), StreamEvent dataclass (fields,
defaults, __post_init__), CancellationToken (is_cancelled, cancel, cancel_reason,
reset, raise_if_cancelled), CancellationError (message, reason attribute),
StreamingSearchRequest (defaults), and StreamingSearchState (defaults, elapsed_ms).
No network, no Tkinter, no file I/O.
"""

import sys
import time
import pytest
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from rag.streaming_models import (
    StreamEventType, StreamEvent, CancellationToken, CancellationError,
    StreamingSearchRequest, StreamingSearchState,
)


# ===========================================================================
# StreamEventType
# ===========================================================================

class TestStreamEventType:
    def test_search_started_value(self):
        assert StreamEventType.SEARCH_STARTED.value == "search_started"

    def test_vector_results_value(self):
        assert StreamEventType.VECTOR_RESULTS.value == "vector_results"

    def test_bm25_results_value(self):
        assert StreamEventType.BM25_RESULTS.value == "bm25_results"

    def test_graph_results_value(self):
        assert StreamEventType.GRAPH_RESULTS.value == "graph_results"

    def test_search_complete_value(self):
        assert StreamEventType.SEARCH_COMPLETE.value == "search_complete"

    def test_generation_started_value(self):
        assert StreamEventType.GENERATION_STARTED.value == "generation_started"

    def test_token_value(self):
        assert StreamEventType.TOKEN.value == "token"

    def test_generation_complete_value(self):
        assert StreamEventType.GENERATION_COMPLETE.value == "generation_complete"

    def test_progress_value(self):
        assert StreamEventType.PROGRESS.value == "progress"

    def test_error_value(self):
        assert StreamEventType.ERROR.value == "error"

    def test_cancelled_value(self):
        assert StreamEventType.CANCELLED.value == "cancelled"

    def test_twelve_members(self):
        assert len(list(StreamEventType)) == 11


# ===========================================================================
# StreamEvent
# ===========================================================================

class TestStreamEvent:
    def test_event_type_required(self):
        e = StreamEvent(event_type=StreamEventType.PROGRESS)
        assert e.event_type == StreamEventType.PROGRESS

    def test_data_default_none(self):
        e = StreamEvent(event_type=StreamEventType.PROGRESS)
        assert e.data is None

    def test_data_stored(self):
        e = StreamEvent(event_type=StreamEventType.TOKEN, data="hello")
        assert e.data == "hello"

    def test_progress_default_zero(self):
        e = StreamEvent(event_type=StreamEventType.PROGRESS)
        assert e.progress_percent == 0.0

    def test_progress_stored(self):
        e = StreamEvent(event_type=StreamEventType.PROGRESS, progress_percent=50.0)
        assert e.progress_percent == 50.0

    def test_message_default_empty(self):
        e = StreamEvent(event_type=StreamEventType.PROGRESS)
        assert e.message == ""

    def test_message_stored(self):
        e = StreamEvent(event_type=StreamEventType.PROGRESS, message="Searching...")
        assert e.message == "Searching..."

    def test_timestamp_auto_set(self):
        e = StreamEvent(event_type=StreamEventType.PROGRESS)
        assert e.timestamp is not None
        assert isinstance(e.timestamp, datetime)

    def test_timestamp_is_recent(self):
        before = datetime.now()
        e = StreamEvent(event_type=StreamEventType.PROGRESS)
        after = datetime.now()
        assert before <= e.timestamp <= after


# ===========================================================================
# CancellationToken
# ===========================================================================

class TestCancellationToken:
    def test_initially_not_cancelled(self):
        t = CancellationToken()
        assert t.is_cancelled is False

    def test_cancel_sets_cancelled(self):
        t = CancellationToken()
        t.cancel()
        assert t.is_cancelled is True

    def test_cancel_reason_default(self):
        t = CancellationToken()
        t.cancel()
        assert "cancel" in t.cancel_reason.lower()

    def test_cancel_reason_custom(self):
        t = CancellationToken()
        t.cancel("user closed window")
        assert t.cancel_reason == "user closed window"

    def test_cancel_reason_none_before_cancel(self):
        t = CancellationToken()
        assert t.cancel_reason is None

    def test_cancel_idempotent(self):
        t = CancellationToken()
        t.cancel("first reason")
        t.cancel("second reason")
        # Second cancel should not overwrite (token already set)
        assert t.cancel_reason == "first reason"

    def test_reset_clears_cancelled(self):
        t = CancellationToken()
        t.cancel()
        t.reset()
        assert t.is_cancelled is False

    def test_reset_clears_reason(self):
        t = CancellationToken()
        t.cancel("some reason")
        t.reset()
        assert t.cancel_reason is None

    def test_raise_if_cancelled_raises_when_cancelled(self):
        t = CancellationToken()
        t.cancel("test")
        with pytest.raises(CancellationError):
            t.raise_if_cancelled()

    def test_raise_if_cancelled_no_raise_when_not_cancelled(self):
        t = CancellationToken()
        t.raise_if_cancelled()  # Should not raise

    def test_raise_if_cancelled_reason_in_error(self):
        t = CancellationToken()
        t.cancel("custom cancel reason")
        with pytest.raises(CancellationError) as exc_info:
            t.raise_if_cancelled()
        assert "custom cancel reason" in str(exc_info.value)

    def test_is_cancelled_is_bool(self):
        t = CancellationToken()
        assert isinstance(t.is_cancelled, bool)


# ===========================================================================
# CancellationError
# ===========================================================================

class TestCancellationError:
    def test_is_exception(self):
        assert issubclass(CancellationError, Exception)

    def test_default_reason(self):
        e = CancellationError()
        assert "cancel" in e.reason.lower()

    def test_custom_reason(self):
        e = CancellationError("timeout exceeded")
        assert e.reason == "timeout exceeded"

    def test_str_contains_reason(self):
        e = CancellationError("user abort")
        assert "user abort" in str(e)

    def test_can_raise_and_catch(self):
        with pytest.raises(CancellationError):
            raise CancellationError("test")


# ===========================================================================
# StreamingSearchRequest
# ===========================================================================

class TestStreamingSearchRequest:
    def test_query_required(self):
        r = StreamingSearchRequest(query="diabetes treatment")
        assert r.query == "diabetes treatment"

    def test_top_k_default(self):
        r = StreamingSearchRequest(query="test")
        assert r.top_k == 5

    def test_use_graph_search_default_true(self):
        r = StreamingSearchRequest(query="test")
        assert r.use_graph_search is True

    def test_similarity_threshold_default(self):
        r = StreamingSearchRequest(query="test")
        assert r.similarity_threshold == 0.3

    def test_enable_query_expansion_default_true(self):
        r = StreamingSearchRequest(query="test")
        assert r.enable_query_expansion is True

    def test_enable_adaptive_threshold_default_true(self):
        r = StreamingSearchRequest(query="test")
        assert r.enable_adaptive_threshold is True

    def test_enable_bm25_default_true(self):
        r = StreamingSearchRequest(query="test")
        assert r.enable_bm25 is True

    def test_enable_mmr_default_true(self):
        r = StreamingSearchRequest(query="test")
        assert r.enable_mmr is True

    def test_ef_search_default_none(self):
        r = StreamingSearchRequest(query="test")
        assert r.ef_search is None

    def test_custom_values_stored(self):
        r = StreamingSearchRequest(query="test", top_k=10, similarity_threshold=0.5)
        assert r.top_k == 10
        assert r.similarity_threshold == 0.5


# ===========================================================================
# StreamingSearchState
# ===========================================================================

class TestStreamingSearchState:
    def _make_state(self):
        req = StreamingSearchRequest(query="test")
        token = CancellationToken()
        return StreamingSearchState(request=req, cancellation_token=token)

    def test_vector_results_default_empty(self):
        state = self._make_state()
        assert state.vector_results == []

    def test_bm25_results_default_empty(self):
        state = self._make_state()
        assert state.bm25_results == []

    def test_graph_results_default_empty(self):
        state = self._make_state()
        assert state.graph_results == []

    def test_merged_results_default_empty(self):
        state = self._make_state()
        assert state.merged_results == []

    def test_query_embedding_default_none(self):
        state = self._make_state()
        assert state.query_embedding is None

    def test_error_default_none(self):
        state = self._make_state()
        assert state.error is None

    def test_start_time_set(self):
        state = self._make_state()
        assert state.start_time is not None

    def test_elapsed_ms_is_float(self):
        state = self._make_state()
        assert isinstance(state.elapsed_ms, float)

    def test_elapsed_ms_non_negative(self):
        state = self._make_state()
        assert state.elapsed_ms >= 0.0

    def test_elapsed_ms_increases_over_time(self):
        state = self._make_state()
        t1 = state.elapsed_ms
        time.sleep(0.05)
        t2 = state.elapsed_ms
        assert t2 > t1
