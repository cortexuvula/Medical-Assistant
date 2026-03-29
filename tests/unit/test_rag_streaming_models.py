"""
Tests for src/rag/streaming_models.py

Covers StreamEventType enum, StreamEvent dataclass, CancellationToken
(is_cancelled, cancel, reset, raise_if_cancelled, cancel_reason,
thread-safe repeated cancel), CancellationError, StreamingSearchRequest
defaults, and StreamingSearchState (defaults, elapsed_ms).
Pure in-memory/threading logic — no network, no Tkinter, no file I/O.
"""

import sys
import time
import threading
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
    StreamingSearchRequest,
    StreamingSearchState,
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
        assert len(StreamEventType) == 11

    def test_all_values_are_strings(self):
        for member in StreamEventType:
            assert isinstance(member.value, str)


# ===========================================================================
# StreamEvent dataclass
# ===========================================================================

class TestStreamEvent:
    def test_required_event_type(self):
        e = StreamEvent(StreamEventType.PROGRESS)
        assert e.event_type == StreamEventType.PROGRESS

    def test_data_defaults_none(self):
        e = StreamEvent(StreamEventType.TOKEN)
        assert e.data is None

    def test_progress_percent_defaults_zero(self):
        e = StreamEvent(StreamEventType.PROGRESS)
        assert e.progress_percent == pytest.approx(0.0)

    def test_message_defaults_empty_string(self):
        e = StreamEvent(StreamEventType.PROGRESS)
        assert e.message == ""

    def test_timestamp_is_datetime(self):
        e = StreamEvent(StreamEventType.SEARCH_STARTED)
        assert isinstance(e.timestamp, datetime)

    def test_custom_data(self):
        data = {"results": [1, 2, 3]}
        e = StreamEvent(StreamEventType.VECTOR_RESULTS, data=data)
        assert e.data == {"results": [1, 2, 3]}

    def test_custom_progress(self):
        e = StreamEvent(StreamEventType.PROGRESS, progress_percent=50.0)
        assert e.progress_percent == pytest.approx(50.0)

    def test_custom_message(self):
        e = StreamEvent(StreamEventType.ERROR, message="Network error")
        assert e.message == "Network error"

    def test_timestamp_recent(self):
        before = datetime.now()
        e = StreamEvent(StreamEventType.PROGRESS)
        after = datetime.now()
        assert before <= e.timestamp <= after


# ===========================================================================
# CancellationToken
# ===========================================================================

class TestCancellationToken:
    def test_not_cancelled_by_default(self):
        token = CancellationToken()
        assert token.is_cancelled is False

    def test_cancel_reason_none_by_default(self):
        token = CancellationToken()
        assert token.cancel_reason is None

    def test_cancel_sets_is_cancelled(self):
        token = CancellationToken()
        token.cancel()
        assert token.is_cancelled is True

    def test_cancel_sets_reason(self):
        token = CancellationToken()
        token.cancel("Timeout")
        assert token.cancel_reason == "Timeout"

    def test_cancel_default_reason(self):
        token = CancellationToken()
        token.cancel()
        assert "User requested" in token.cancel_reason

    def test_reset_clears_cancelled(self):
        token = CancellationToken()
        token.cancel()
        token.reset()
        assert token.is_cancelled is False

    def test_reset_clears_reason(self):
        token = CancellationToken()
        token.cancel("Some reason")
        token.reset()
        assert token.cancel_reason is None

    def test_raise_if_cancelled_raises_when_cancelled(self):
        token = CancellationToken()
        token.cancel("Stopped")
        with pytest.raises(CancellationError):
            token.raise_if_cancelled()

    def test_raise_if_cancelled_no_raise_when_active(self):
        token = CancellationToken()
        token.raise_if_cancelled()  # Should not raise

    def test_second_cancel_does_not_change_reason(self):
        token = CancellationToken()
        token.cancel("First reason")
        token.cancel("Second reason")
        # First cancel wins
        assert token.cancel_reason == "First reason"

    def test_cancel_and_reset_and_cancel_again(self):
        token = CancellationToken()
        token.cancel("First")
        token.reset()
        token.cancel("Second")
        assert token.cancel_reason == "Second"
        assert token.is_cancelled is True

    def test_thread_safe_cancel(self):
        """Multiple threads cancelling should not corrupt state."""
        token = CancellationToken()
        errors = []

        def do_cancel():
            try:
                token.cancel("thread cancel")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=do_cancel) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert token.is_cancelled is True


# ===========================================================================
# CancellationError
# ===========================================================================

class TestCancellationError:
    def test_is_exception(self):
        assert issubclass(CancellationError, Exception)

    def test_default_message(self):
        e = CancellationError()
        assert "Operation cancelled" in str(e)

    def test_custom_reason(self):
        e = CancellationError("Timeout exceeded")
        assert e.reason == "Timeout exceeded"

    def test_str_contains_reason(self):
        e = CancellationError("Stopped by user")
        assert "Stopped by user" in str(e)

    def test_raise_and_catch(self):
        with pytest.raises(CancellationError) as exc_info:
            raise CancellationError("Test")
        assert exc_info.value.reason == "Test"

    def test_raise_if_cancelled_error_has_reason(self):
        token = CancellationToken()
        token.cancel("Specific reason")
        with pytest.raises(CancellationError) as exc_info:
            token.raise_if_cancelled()
        assert "Specific reason" in str(exc_info.value)


# ===========================================================================
# StreamingSearchRequest defaults
# ===========================================================================

class TestStreamingSearchRequest:
    def test_query_required(self):
        req = StreamingSearchRequest(query="hypertension treatment")
        assert req.query == "hypertension treatment"

    def test_top_k_defaults_5(self):
        req = StreamingSearchRequest(query="x")
        assert req.top_k == 5

    def test_use_graph_search_defaults_true(self):
        req = StreamingSearchRequest(query="x")
        assert req.use_graph_search is True

    def test_similarity_threshold_defaults_0_3(self):
        req = StreamingSearchRequest(query="x")
        assert req.similarity_threshold == pytest.approx(0.3)

    def test_enable_query_expansion_defaults_true(self):
        req = StreamingSearchRequest(query="x")
        assert req.enable_query_expansion is True

    def test_enable_adaptive_threshold_defaults_true(self):
        req = StreamingSearchRequest(query="x")
        assert req.enable_adaptive_threshold is True

    def test_enable_bm25_defaults_true(self):
        req = StreamingSearchRequest(query="x")
        assert req.enable_bm25 is True

    def test_enable_mmr_defaults_true(self):
        req = StreamingSearchRequest(query="x")
        assert req.enable_mmr is True

    def test_ef_search_defaults_none(self):
        req = StreamingSearchRequest(query="x")
        assert req.ef_search is None

    def test_custom_values(self):
        req = StreamingSearchRequest(
            query="stroke", top_k=10, enable_bm25=False, ef_search=100
        )
        assert req.top_k == 10
        assert req.enable_bm25 is False
        assert req.ef_search == 100


# ===========================================================================
# StreamingSearchState
# ===========================================================================

class TestStreamingSearchState:
    def _make_state(self) -> StreamingSearchState:
        req = StreamingSearchRequest(query="test")
        token = CancellationToken()
        return StreamingSearchState(request=req, cancellation_token=token)

    def test_request_stored(self):
        state = self._make_state()
        assert state.request.query == "test"

    def test_vector_results_defaults_empty(self):
        assert self._make_state().vector_results == []

    def test_bm25_results_defaults_empty(self):
        assert self._make_state().bm25_results == []

    def test_graph_results_defaults_empty(self):
        assert self._make_state().graph_results == []

    def test_merged_results_defaults_empty(self):
        assert self._make_state().merged_results == []

    def test_query_embedding_defaults_none(self):
        assert self._make_state().query_embedding is None

    def test_query_expansion_defaults_none(self):
        assert self._make_state().query_expansion is None

    def test_error_defaults_none(self):
        assert self._make_state().error is None

    def test_start_time_is_datetime(self):
        assert isinstance(self._make_state().start_time, datetime)

    def test_elapsed_ms_is_float(self):
        elapsed = self._make_state().elapsed_ms
        assert isinstance(elapsed, float)

    def test_elapsed_ms_is_non_negative(self):
        state = self._make_state()
        assert state.elapsed_ms >= 0.0

    def test_elapsed_ms_increases_over_time(self):
        state = self._make_state()
        t1 = state.elapsed_ms
        time.sleep(0.02)
        t2 = state.elapsed_ms
        assert t2 > t1

    def test_instances_dont_share_lists(self):
        s1 = self._make_state()
        s2 = self._make_state()
        s1.vector_results.append("result")
        assert s2.vector_results == []
