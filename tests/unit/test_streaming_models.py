"""
Tests for src/rag/streaming_models.py

Covers StreamEventType enum, StreamEvent dataclass, CancellationToken
(thread-safe cancellation), and CancellationError.

No network, no Tkinter, no I/O.
"""
import sys
import threading
import time
import pytest
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from rag.streaming_models import (
    StreamEventType,
    StreamEvent,
    CancellationToken,
    CancellationError,
)


# ---------------------------------------------------------------------------
# TestStreamEventType
# ---------------------------------------------------------------------------

class TestStreamEventType:
    """Tests for the StreamEventType enum."""

    def test_search_started_exists(self):
        assert hasattr(StreamEventType, "SEARCH_STARTED")

    def test_vector_results_exists(self):
        assert hasattr(StreamEventType, "VECTOR_RESULTS")

    def test_bm25_results_exists(self):
        assert hasattr(StreamEventType, "BM25_RESULTS")

    def test_graph_results_exists(self):
        assert hasattr(StreamEventType, "GRAPH_RESULTS")

    def test_search_complete_exists(self):
        assert hasattr(StreamEventType, "SEARCH_COMPLETE")

    def test_generation_started_exists(self):
        assert hasattr(StreamEventType, "GENERATION_STARTED")

    def test_token_exists(self):
        assert hasattr(StreamEventType, "TOKEN")

    def test_generation_complete_exists(self):
        assert hasattr(StreamEventType, "GENERATION_COMPLETE")

    def test_progress_exists(self):
        assert hasattr(StreamEventType, "PROGRESS")

    def test_error_exists(self):
        assert hasattr(StreamEventType, "ERROR")

    def test_cancelled_exists(self):
        assert hasattr(StreamEventType, "CANCELLED")

    def test_search_started_value_is_string(self):
        assert isinstance(StreamEventType.SEARCH_STARTED.value, str)

    def test_vector_results_value_is_string(self):
        assert isinstance(StreamEventType.VECTOR_RESULTS.value, str)

    def test_bm25_results_value_is_string(self):
        assert isinstance(StreamEventType.BM25_RESULTS.value, str)

    def test_graph_results_value_is_string(self):
        assert isinstance(StreamEventType.GRAPH_RESULTS.value, str)

    def test_search_complete_value_is_string(self):
        assert isinstance(StreamEventType.SEARCH_COMPLETE.value, str)

    def test_generation_started_value_is_string(self):
        assert isinstance(StreamEventType.GENERATION_STARTED.value, str)

    def test_token_value_is_string(self):
        assert isinstance(StreamEventType.TOKEN.value, str)

    def test_generation_complete_value_is_string(self):
        assert isinstance(StreamEventType.GENERATION_COMPLETE.value, str)

    def test_progress_value_is_string(self):
        assert isinstance(StreamEventType.PROGRESS.value, str)

    def test_error_value_is_string(self):
        assert isinstance(StreamEventType.ERROR.value, str)

    def test_cancelled_value_is_string(self):
        assert isinstance(StreamEventType.CANCELLED.value, str)

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

    def test_enum_has_eleven_members(self):
        assert len(StreamEventType) == 11

    def test_members_are_unique(self):
        values = [e.value for e in StreamEventType]
        assert len(values) == len(set(values))

    def test_lookup_by_value(self):
        et = StreamEventType("token")
        assert et is StreamEventType.TOKEN

    def test_is_enum_instance(self):
        from enum import Enum
        assert issubclass(StreamEventType, Enum)


# ---------------------------------------------------------------------------
# TestStreamEvent
# ---------------------------------------------------------------------------

class TestStreamEvent:
    """Tests for the StreamEvent dataclass."""

    def test_create_with_event_type_only(self):
        event = StreamEvent(event_type=StreamEventType.PROGRESS)
        assert event.event_type is StreamEventType.PROGRESS

    def test_default_data_is_none(self):
        event = StreamEvent(event_type=StreamEventType.TOKEN)
        assert event.data is None

    def test_default_progress_percent_is_zero(self):
        event = StreamEvent(event_type=StreamEventType.SEARCH_STARTED)
        assert event.progress_percent == 0.0

    def test_default_message_is_empty_string(self):
        event = StreamEvent(event_type=StreamEventType.PROGRESS)
        assert event.message == ""

    def test_timestamp_is_set_by_default(self):
        event = StreamEvent(event_type=StreamEventType.PROGRESS)
        assert isinstance(event.timestamp, datetime)

    def test_timestamp_is_recent(self):
        before = datetime.now()
        event = StreamEvent(event_type=StreamEventType.PROGRESS)
        after = datetime.now()
        assert before <= event.timestamp <= after

    def test_custom_data_string(self):
        event = StreamEvent(event_type=StreamEventType.TOKEN, data="hello")
        assert event.data == "hello"

    def test_custom_data_dict(self):
        payload = {"results": [1, 2, 3]}
        event = StreamEvent(event_type=StreamEventType.VECTOR_RESULTS, data=payload)
        assert event.data == payload

    def test_custom_data_list(self):
        event = StreamEvent(event_type=StreamEventType.BM25_RESULTS, data=[1, 2, 3])
        assert event.data == [1, 2, 3]

    def test_custom_progress_percent(self):
        event = StreamEvent(event_type=StreamEventType.PROGRESS, progress_percent=50.0)
        assert event.progress_percent == 50.0

    def test_custom_progress_at_100(self):
        event = StreamEvent(event_type=StreamEventType.GENERATION_COMPLETE, progress_percent=100.0)
        assert event.progress_percent == 100.0

    def test_custom_message(self):
        event = StreamEvent(event_type=StreamEventType.SEARCH_STARTED, message="Searching...")
        assert event.message == "Searching..."

    def test_custom_timestamp(self):
        ts = datetime(2024, 1, 15, 10, 30, 0)
        event = StreamEvent(event_type=StreamEventType.ERROR, timestamp=ts)
        assert event.timestamp == ts

    def test_post_init_replaces_none_timestamp(self):
        event = StreamEvent(event_type=StreamEventType.PROGRESS, timestamp=None)
        assert isinstance(event.timestamp, datetime)

    def test_error_event_with_exception_data(self):
        exc = ValueError("something failed")
        event = StreamEvent(event_type=StreamEventType.ERROR, data=exc)
        assert isinstance(event.data, ValueError)

    def test_cancelled_event_fields(self):
        event = StreamEvent(
            event_type=StreamEventType.CANCELLED,
            message="User cancelled",
            progress_percent=42.0,
        )
        assert event.event_type is StreamEventType.CANCELLED
        assert event.message == "User cancelled"
        assert event.progress_percent == 42.0

    def test_generation_complete_event(self):
        event = StreamEvent(
            event_type=StreamEventType.GENERATION_COMPLETE,
            data={"text": "final answer"},
            progress_percent=100.0,
        )
        assert event.progress_percent == 100.0
        assert event.data["text"] == "final answer"

    def test_two_events_have_independent_timestamps(self):
        e1 = StreamEvent(event_type=StreamEventType.SEARCH_STARTED)
        e2 = StreamEvent(event_type=StreamEventType.SEARCH_COMPLETE)
        assert e1.timestamp <= e2.timestamp

    def test_data_can_be_none_explicitly(self):
        event = StreamEvent(event_type=StreamEventType.PROGRESS, data=None)
        assert event.data is None

    def test_data_can_be_integer(self):
        event = StreamEvent(event_type=StreamEventType.PROGRESS, data=42)
        assert event.data == 42


# ---------------------------------------------------------------------------
# TestCancellationToken
# ---------------------------------------------------------------------------

class TestCancellationToken:
    """Tests for CancellationToken."""

    def test_not_cancelled_initially(self):
        token = CancellationToken()
        assert not token.is_cancelled

    def test_cancel_reason_none_initially(self):
        token = CancellationToken()
        assert token.cancel_reason is None

    def test_cancel_sets_cancelled(self):
        token = CancellationToken()
        token.cancel()
        assert token.is_cancelled

    def test_cancel_with_default_reason(self):
        token = CancellationToken()
        token.cancel()
        assert token.cancel_reason == "User requested cancellation"

    def test_cancel_with_custom_reason(self):
        token = CancellationToken()
        token.cancel(reason="Timeout exceeded")
        assert token.cancel_reason == "Timeout exceeded"

    def test_cancel_is_idempotent_reason_preserved(self):
        token = CancellationToken()
        token.cancel(reason="first")
        token.cancel(reason="second")
        assert token.cancel_reason == "first"

    def test_cancel_idempotent_still_cancelled(self):
        token = CancellationToken()
        token.cancel()
        token.cancel()
        assert token.is_cancelled

    def test_reset_clears_cancelled(self):
        token = CancellationToken()
        token.cancel()
        token.reset()
        assert not token.is_cancelled

    def test_reset_clears_reason(self):
        token = CancellationToken()
        token.cancel(reason="old reason")
        token.reset()
        assert token.cancel_reason is None

    def test_reset_allows_reuse(self):
        token = CancellationToken()
        token.cancel()
        token.reset()
        token.cancel(reason="new reason")
        assert token.is_cancelled
        assert token.cancel_reason == "new reason"

    def test_reset_on_fresh_token_is_safe(self):
        token = CancellationToken()
        token.reset()  # no-op, must not raise
        assert not token.is_cancelled

    def test_raise_if_cancelled_raises_when_cancelled(self):
        token = CancellationToken()
        token.cancel(reason="stopped")
        with pytest.raises(CancellationError):
            token.raise_if_cancelled()

    def test_raise_if_cancelled_does_not_raise_when_not_cancelled(self):
        token = CancellationToken()
        token.raise_if_cancelled()  # must not raise

    def test_raise_if_cancelled_reason_in_exception(self):
        token = CancellationToken()
        token.cancel(reason="explicit reason")
        with pytest.raises(CancellationError) as exc_info:
            token.raise_if_cancelled()
        assert exc_info.value.reason == "explicit reason"

    def test_raise_if_cancelled_default_reason_contains_cancelled(self):
        token = CancellationToken()
        token.cancel()
        with pytest.raises(CancellationError) as exc_info:
            token.raise_if_cancelled()
        assert "cancel" in exc_info.value.reason.lower()

    def test_raise_if_cancelled_does_not_raise_after_reset(self):
        token = CancellationToken()
        token.cancel()
        token.reset()
        token.raise_if_cancelled()  # must not raise

    def test_is_cancelled_returns_bool(self):
        token = CancellationToken()
        assert isinstance(token.is_cancelled, bool)

    def test_cancel_reason_returns_string_after_cancel(self):
        token = CancellationToken()
        token.cancel()
        assert isinstance(token.cancel_reason, str)

    def test_multiple_resets_work(self):
        token = CancellationToken()
        for _ in range(3):
            token.cancel()
            token.reset()
        assert not token.is_cancelled
        assert token.cancel_reason is None

    def test_thread_safety_cancel_from_other_thread(self):
        """Cancel from a background thread; main thread sees it."""
        token = CancellationToken()
        results = []

        def worker():
            time.sleep(0.01)
            token.cancel(reason="from thread")
            results.append("done")

        t = threading.Thread(target=worker)
        t.start()
        t.join(timeout=2)

        assert token.is_cancelled
        assert token.cancel_reason == "from thread"
        assert results == ["done"]

    def test_thread_safety_multiple_threads_cancel_first_reason_wins(self):
        """Many threads racing to cancel; only one reason persists."""
        token = CancellationToken()
        barrier = threading.Barrier(10)

        def worker(n):
            barrier.wait()
            token.cancel(reason=f"thread-{n}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2)

        assert token.is_cancelled
        assert token.cancel_reason is not None
        assert token.cancel_reason.startswith("thread-")

    def test_thread_safety_read_during_cancel_no_exceptions(self):
        """Reading is_cancelled while another thread cancels does not crash."""
        token = CancellationToken()
        errors = []

        def reader():
            for _ in range(2000):
                try:
                    _ = token.is_cancelled
                except Exception as e:
                    errors.append(e)

        def canceller():
            time.sleep(0.001)
            token.cancel()

        r = threading.Thread(target=reader)
        c = threading.Thread(target=canceller)
        r.start()
        c.start()
        r.join(timeout=2)
        c.join(timeout=2)

        assert not errors


# ---------------------------------------------------------------------------
# TestCancellationError
# ---------------------------------------------------------------------------

class TestCancellationError:
    """Tests for CancellationError."""

    def test_is_exception_subclass(self):
        assert issubclass(CancellationError, Exception)

    def test_default_reason(self):
        err = CancellationError()
        assert err.reason == "Operation cancelled"

    def test_default_message_in_str(self):
        err = CancellationError()
        assert str(err) == "Operation cancelled"

    def test_custom_reason(self):
        err = CancellationError("Request timed out")
        assert err.reason == "Request timed out"

    def test_custom_reason_in_str(self):
        err = CancellationError("Request timed out")
        assert str(err) == "Request timed out"

    def test_reason_attribute_exists(self):
        err = CancellationError("test")
        assert hasattr(err, "reason")

    def test_can_be_raised_and_caught_as_cancellation_error(self):
        with pytest.raises(CancellationError):
            raise CancellationError("oops")

    def test_can_be_caught_as_base_exception(self):
        with pytest.raises(Exception):
            raise CancellationError("oops")

    def test_reason_preserved_after_raise(self):
        with pytest.raises(CancellationError) as exc_info:
            raise CancellationError("my reason")
        assert exc_info.value.reason == "my reason"

    def test_empty_reason_string(self):
        err = CancellationError("")
        assert err.reason == ""

    def test_long_reason_string(self):
        long_reason = "x" * 1000
        err = CancellationError(long_reason)
        assert err.reason == long_reason

    def test_exception_args_contain_reason(self):
        err = CancellationError("some reason")
        assert "some reason" in err.args
