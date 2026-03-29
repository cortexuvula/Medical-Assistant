"""
Tests for src/rag/streaming_models.py

Covers StreamEventType enum, StreamEvent dataclass, CancellationToken
(thread-safe cancel/reset/raise), CancellationError, and StreamingSearchState.
No Tkinter, no network, no file I/O.
"""

import sys
import threading
import time
import pytest
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from rag.streaming_models import (
    StreamEventType,
    StreamEvent,
    CancellationToken,
    CancellationError,
    StreamingSearchState,
    StreamingSearchRequest,
)


# ===========================================================================
# StreamEventType enum
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

    def test_total_members(self):
        assert len(list(StreamEventType)) == 11


# ===========================================================================
# StreamEvent dataclass
# ===========================================================================

class TestStreamEvent:
    def test_create_with_event_type(self):
        event = StreamEvent(event_type=StreamEventType.SEARCH_STARTED)
        assert event.event_type == StreamEventType.SEARCH_STARTED

    def test_data_defaults_none(self):
        event = StreamEvent(event_type=StreamEventType.PROGRESS)
        assert event.data is None

    def test_progress_percent_defaults_zero(self):
        event = StreamEvent(event_type=StreamEventType.PROGRESS)
        assert event.progress_percent == 0.0

    def test_message_defaults_empty(self):
        event = StreamEvent(event_type=StreamEventType.PROGRESS)
        assert event.message == ""

    def test_timestamp_is_datetime(self):
        event = StreamEvent(event_type=StreamEventType.SEARCH_STARTED)
        assert isinstance(event.timestamp, datetime)

    def test_timestamp_is_recent(self):
        before = datetime.now()
        event = StreamEvent(event_type=StreamEventType.SEARCH_STARTED)
        after = datetime.now()
        assert before <= event.timestamp <= after

    def test_custom_data(self):
        event = StreamEvent(event_type=StreamEventType.TOKEN, data="hello")
        assert event.data == "hello"

    def test_custom_progress_percent(self):
        event = StreamEvent(event_type=StreamEventType.PROGRESS, progress_percent=50.0)
        assert event.progress_percent == 50.0

    def test_custom_message(self):
        event = StreamEvent(event_type=StreamEventType.SEARCH_STARTED, message="Searching...")
        assert event.message == "Searching..."

    def test_custom_timestamp(self):
        ts = datetime(2024, 1, 15, 10, 30)
        event = StreamEvent(event_type=StreamEventType.SEARCH_STARTED, timestamp=ts)
        assert event.timestamp == ts


# ===========================================================================
# CancellationToken
# ===========================================================================

class TestCancellationTokenInit:
    def test_initially_not_cancelled(self):
        token = CancellationToken()
        assert token.is_cancelled is False

    def test_cancel_reason_initially_none(self):
        token = CancellationToken()
        assert token.cancel_reason is None


class TestCancellationTokenCancel:
    def test_cancel_sets_is_cancelled(self):
        token = CancellationToken()
        token.cancel()
        assert token.is_cancelled is True

    def test_cancel_with_default_reason(self):
        token = CancellationToken()
        token.cancel()
        assert token.cancel_reason is not None
        assert "cancel" in token.cancel_reason.lower() or "user" in token.cancel_reason.lower()

    def test_cancel_with_custom_reason(self):
        token = CancellationToken()
        token.cancel(reason="Timeout exceeded")
        assert token.cancel_reason == "Timeout exceeded"

    def test_cancel_twice_keeps_first_reason(self):
        token = CancellationToken()
        token.cancel(reason="First reason")
        token.cancel(reason="Second reason")
        # Second cancel should not change the reason (already cancelled)
        assert token.cancel_reason == "First reason"

    def test_cancel_twice_stays_cancelled(self):
        token = CancellationToken()
        token.cancel()
        token.cancel()
        assert token.is_cancelled is True


class TestCancellationTokenReset:
    def test_reset_clears_cancelled(self):
        token = CancellationToken()
        token.cancel()
        token.reset()
        assert token.is_cancelled is False

    def test_reset_clears_cancel_reason(self):
        token = CancellationToken()
        token.cancel(reason="Done")
        token.reset()
        assert token.cancel_reason is None

    def test_can_cancel_after_reset(self):
        token = CancellationToken()
        token.cancel(reason="First")
        token.reset()
        token.cancel(reason="Second")
        assert token.is_cancelled is True
        assert token.cancel_reason == "Second"


class TestCancellationTokenRaiseIfCancelled:
    def test_no_raise_when_not_cancelled(self):
        token = CancellationToken()
        token.raise_if_cancelled()  # Should not raise

    def test_raises_cancellation_error_when_cancelled(self):
        token = CancellationToken()
        token.cancel(reason="Test cancel")
        with pytest.raises(CancellationError):
            token.raise_if_cancelled()

    def test_raised_error_contains_reason(self):
        token = CancellationToken()
        token.cancel(reason="Test cancel")
        with pytest.raises(CancellationError, match="Test cancel"):
            token.raise_if_cancelled()

    def test_raises_with_default_reason(self):
        token = CancellationToken()
        token.cancel()
        with pytest.raises(CancellationError):
            token.raise_if_cancelled()


class TestCancellationTokenThreadSafety:
    def test_concurrent_cancel_is_safe(self):
        token = CancellationToken()
        errors = []

        def cancel_task():
            try:
                token.cancel(reason="concurrent")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=cancel_task) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert token.is_cancelled is True

    def test_cancel_visible_across_threads(self):
        token = CancellationToken()
        seen_cancelled = []

        def check_task():
            time.sleep(0.01)
            seen_cancelled.append(token.is_cancelled)

        t = threading.Thread(target=check_task)
        t.start()
        token.cancel()
        t.join()

        assert any(seen_cancelled)


# ===========================================================================
# CancellationError
# ===========================================================================

class TestCancellationError:
    def test_is_exception(self):
        assert issubclass(CancellationError, Exception)

    def test_default_reason(self):
        err = CancellationError()
        assert err.reason == "Operation cancelled"

    def test_custom_reason(self):
        err = CancellationError("Timeout")
        assert err.reason == "Timeout"

    def test_str_contains_reason(self):
        err = CancellationError("My reason")
        assert "My reason" in str(err)

    def test_can_raise_and_catch(self):
        with pytest.raises(CancellationError) as exc_info:
            raise CancellationError("test")
        assert exc_info.value.reason == "test"


# ===========================================================================
# StreamingSearchState
# ===========================================================================

def _make_state() -> StreamingSearchState:
    """Create a StreamingSearchState with minimal dependencies."""
    token = CancellationToken()
    request = StreamingSearchRequest(query="test query")
    return StreamingSearchState(request=request, cancellation_token=token)


class TestStreamingSearchState:
    def test_vector_results_default_empty(self):
        state = _make_state()
        assert state.vector_results == []

    def test_bm25_results_default_empty(self):
        state = _make_state()
        assert state.bm25_results == []

    def test_graph_results_default_empty(self):
        state = _make_state()
        assert state.graph_results == []

    def test_merged_results_default_empty(self):
        state = _make_state()
        assert state.merged_results == []

    def test_error_default_none(self):
        state = _make_state()
        assert state.error is None

    def test_query_embedding_default_none(self):
        state = _make_state()
        assert state.query_embedding is None

    def test_start_time_is_datetime(self):
        state = _make_state()
        assert isinstance(state.start_time, datetime)

    def test_elapsed_ms_is_float(self):
        state = _make_state()
        assert isinstance(state.elapsed_ms, float)

    def test_elapsed_ms_is_non_negative(self):
        state = _make_state()
        assert state.elapsed_ms >= 0.0

    def test_elapsed_ms_increases_over_time(self):
        state = _make_state()
        t1 = state.elapsed_ms
        time.sleep(0.01)
        t2 = state.elapsed_ms
        assert t2 >= t1

    def test_instances_dont_share_lists(self):
        s1 = _make_state()
        s2 = _make_state()
        s1.vector_results.append("x")
        assert s2.vector_results == []

    def test_cancellation_token_stored(self):
        token = CancellationToken()
        request = StreamingSearchRequest(query="test")
        state = StreamingSearchState(request=request, cancellation_token=token)
        assert state.cancellation_token is token

    def test_can_add_to_results(self):
        state = _make_state()
        state.vector_results.append({"score": 0.9, "text": "result"})
        assert len(state.vector_results) == 1
