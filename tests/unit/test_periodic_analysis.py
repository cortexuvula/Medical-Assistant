"""
Comprehensive unit tests for periodic_analysis module.

Tests cover edge cases, error handling, and logic paths not covered
by the existing test_periodic_analyzer.py file:
- _perform_analysis internal logic (stop_event, no callback, exceptions)
- _countdown_loop full decrement flow
- _schedule_next_analysis when not running
- stop() variations (no wait, timeout, countdown callback errors)
- add_to_history defaults and trimming edge cases
- get_combined_history_text formatting
- get_history_summary metadata flags
- Multiple start/stop cycles
- AudioSegmentExtractor edge cases
"""

import pytest
import threading
import time
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime

from audio.periodic_analysis import PeriodicAnalyzer, AudioSegmentExtractor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def analyzer():
    """PeriodicAnalyzer with a very short interval for fast tests."""
    return PeriodicAnalyzer(interval_seconds=1, max_history_items=5)


@pytest.fixture
def cb():
    """Simple mock analysis callback."""
    return Mock()


# ---------------------------------------------------------------------------
# PeriodicAnalyzer.__init__ edge cases
# ---------------------------------------------------------------------------

class TestInitEdgeCases:
    def test_max_history_items_none_uses_default(self):
        a = PeriodicAnalyzer(max_history_items=None)
        assert a.max_history_items == PeriodicAnalyzer.DEFAULT_MAX_HISTORY

    def test_max_history_items_zero_uses_default(self):
        """0 is falsy so it falls through to default."""
        a = PeriodicAnalyzer(max_history_items=0)
        assert a.max_history_items == PeriodicAnalyzer.DEFAULT_MAX_HISTORY

    def test_callback_complete_event_initially_set(self):
        a = PeriodicAnalyzer()
        assert a._callback_complete.is_set()

    def test_stop_event_initially_clear(self):
        a = PeriodicAnalyzer()
        assert not a._stop_event.is_set()


# ---------------------------------------------------------------------------
# _perform_analysis internal paths
# ---------------------------------------------------------------------------

class TestPerformAnalysis:
    def test_returns_early_when_stop_event_set(self, analyzer, cb):
        """_perform_analysis should exit immediately if stop_event is set."""
        analyzer._stop_event.set()
        analyzer._is_running = True
        analyzer._callback = cb
        analyzer._start_time = time.time()

        analyzer._perform_analysis()

        cb.assert_not_called()
        # callback_complete should remain set (never cleared)
        assert analyzer._callback_complete.is_set()

    def test_returns_early_when_not_running(self, analyzer, cb):
        """_perform_analysis should exit if _is_running is False."""
        analyzer._is_running = False
        analyzer._callback = cb
        analyzer._start_time = time.time()

        analyzer._perform_analysis()

        cb.assert_not_called()
        assert analyzer._callback_complete.is_set()

    def test_returns_early_when_no_callback(self, analyzer):
        """_perform_analysis should exit if _callback is None."""
        analyzer._is_running = True
        analyzer._callback = None
        analyzer._start_time = time.time()

        analyzer._perform_analysis()

        assert analyzer._callback_complete.is_set()

    def test_increments_analysis_count(self, analyzer, cb):
        """_perform_analysis should increment _analysis_count."""
        analyzer._is_running = True
        analyzer._callback = cb
        analyzer._start_time = time.time()
        # Prevent scheduling next analysis
        analyzer._stop_event.set()

        initial = analyzer._analysis_count
        # We need to temporarily clear stop event for the initial check,
        # but set it before scheduling. Use a side effect on callback.
        analyzer._stop_event.clear()

        def set_stop(*args):
            analyzer._stop_event.set()

        cb.side_effect = set_stop

        analyzer._perform_analysis()

        assert analyzer._analysis_count == initial + 1

    def test_callback_exception_is_caught(self, analyzer):
        """_perform_analysis should catch callback exceptions."""
        failing_cb = Mock(side_effect=RuntimeError("boom"))
        analyzer._is_running = True
        analyzer._callback = failing_cb
        analyzer._start_time = time.time()
        analyzer._stop_event.clear()

        # Should not raise
        # Prevent infinite scheduling by setting stop event after call
        def stop_after(*args):
            analyzer._stop_event.set()
            raise RuntimeError("boom")

        failing_cb.side_effect = stop_after

        analyzer._perform_analysis()

        assert analyzer._callback_complete.is_set()
        failing_cb.assert_called_once()

    def test_callback_receives_correct_args(self, analyzer, cb):
        """_perform_analysis passes (analysis_number, elapsed_time) to callback."""
        analyzer._is_running = True
        analyzer._callback = cb
        analyzer._start_time = time.time() - 42.5  # pretend 42.5s elapsed
        analyzer._analysis_count = 3  # will be incremented to 4
        analyzer._stop_event.clear()

        def stop_after(*args):
            analyzer._stop_event.set()

        cb.side_effect = stop_after

        analyzer._perform_analysis()

        args = cb.call_args[0]
        assert args[0] == 4  # analysis_number
        assert args[1] >= 42.0  # elapsed_time (approximately)

    def test_schedules_next_when_not_stopped(self, analyzer, cb):
        """_perform_analysis should schedule next if not stopped."""
        analyzer._is_running = True
        analyzer._callback = cb
        analyzer._start_time = time.time()

        with patch.object(analyzer, '_schedule_next_analysis') as mock_sched:
            analyzer._perform_analysis()
            mock_sched.assert_called_once()

    def test_no_schedule_when_stopped(self, analyzer, cb):
        """_perform_analysis should NOT schedule next if stopped."""
        analyzer._is_running = True
        analyzer._callback = cb
        analyzer._start_time = time.time()

        def stop_after(*args):
            analyzer._stop_event.set()

        cb.side_effect = stop_after

        with patch.object(analyzer, '_schedule_next_analysis') as mock_sched:
            analyzer._perform_analysis()
            mock_sched.assert_not_called()

    def test_callback_complete_cleared_then_set(self, analyzer, cb):
        """_perform_analysis clears callback_complete, then sets it in finally."""
        events = []

        def track_callback(*args):
            events.append(analyzer._callback_complete.is_set())
            analyzer._stop_event.set()

        cb.side_effect = track_callback
        analyzer._is_running = True
        analyzer._callback = cb
        analyzer._start_time = time.time()

        analyzer._perform_analysis()

        # During callback, event should have been cleared
        assert events == [False]
        # After, it should be set
        assert analyzer._callback_complete.is_set()


# ---------------------------------------------------------------------------
# _schedule_next_analysis
# ---------------------------------------------------------------------------

class TestScheduleNextAnalysis:
    def test_does_nothing_when_not_running(self, analyzer):
        """Should return early when _is_running is False."""
        analyzer._is_running = False
        analyzer._schedule_next_analysis()
        assert analyzer._countdown_thread is None

    def test_starts_countdown_thread(self, analyzer, cb):
        """Should start a daemon countdown thread."""
        analyzer._is_running = True
        analyzer._stop_event.clear()
        analyzer._callback = cb

        analyzer._schedule_next_analysis()

        try:
            assert analyzer._countdown_thread is not None
            assert analyzer._countdown_thread.daemon is True
            assert analyzer._seconds_remaining == analyzer.interval_seconds
        finally:
            analyzer._stop_event.set()
            time.sleep(0.1)


# ---------------------------------------------------------------------------
# _countdown_loop
# ---------------------------------------------------------------------------

class TestCountdownLoop:
    def test_decrements_to_zero_and_triggers_analysis(self, analyzer, cb):
        """Full countdown should decrement and call _perform_analysis."""
        analyzer._is_running = True
        analyzer._callback = cb
        analyzer._start_time = time.time()
        analyzer.interval_seconds = 2
        analyzer._seconds_remaining = 2

        with patch.object(analyzer, '_perform_analysis') as mock_perform:
            analyzer._countdown_loop()
            mock_perform.assert_called_once()

    def test_exits_when_stop_event_set_mid_countdown(self, analyzer):
        """Countdown loop should exit when stop event is set."""
        analyzer._seconds_remaining = 10

        def set_stop_after_delay():
            time.sleep(0.2)
            analyzer._stop_event.set()

        t = threading.Thread(target=set_stop_after_delay)
        t.start()

        start = time.time()
        analyzer._countdown_loop()
        elapsed = time.time() - start

        t.join()
        # Should have exited well before 10 seconds
        assert elapsed < 3.0

    def test_countdown_callback_called_with_zero_before_analysis(self, analyzer, cb):
        """Should signal 0 to countdown callback before performing analysis."""
        countdown_cb = Mock()
        analyzer._is_running = True
        analyzer._callback = cb
        analyzer._start_time = time.time()
        analyzer._countdown_callback = countdown_cb
        analyzer._seconds_remaining = 1
        analyzer.interval_seconds = 1

        with patch.object(analyzer, '_perform_analysis'):
            analyzer._countdown_loop()

        # Check that 0 was passed at some point
        zero_calls = [c for c in countdown_cb.call_args_list if c[0][0] == 0]
        assert len(zero_calls) >= 1

    def test_countdown_loop_handles_exception(self, analyzer):
        """Countdown loop should catch exceptions without crashing."""
        analyzer._seconds_remaining = 2

        def exploding_callback(remaining):
            raise RuntimeError("countdown exploded")

        analyzer._countdown_callback = exploding_callback
        # stop_event not set, but countdown callback will fail; loop should continue
        # Set stop after brief delay to end the test
        def stop_soon():
            time.sleep(1.5)
            analyzer._stop_event.set()

        t = threading.Thread(target=stop_soon)
        t.start()

        # Should not raise
        analyzer._countdown_loop()
        t.join()


# ---------------------------------------------------------------------------
# stop() variations
# ---------------------------------------------------------------------------

class TestStopVariations:
    def test_stop_without_waiting_for_callback(self, analyzer, cb):
        """stop(wait_for_callback=False) should not block on callback."""
        analyzer.start(cb)
        time.sleep(0.1)

        start = time.time()
        analyzer.stop(wait_for_callback=False)
        elapsed = time.time() - start

        assert elapsed < 2.0
        assert not analyzer.is_running

    def test_stop_countdown_callback_exception_during_stop(self, analyzer, cb):
        """stop() should handle exception in countdown callback(-1)."""
        failing_countdown = Mock(side_effect=Exception("stop error"))
        analyzer.set_countdown_callback(failing_countdown)
        analyzer.start(cb)
        time.sleep(0.1)

        # Should not raise
        analyzer.stop()
        assert not analyzer.is_running

    def test_multiple_stop_calls_are_safe(self, analyzer, cb):
        """Multiple stop calls should be idempotent."""
        analyzer.start(cb)
        time.sleep(0.1)

        analyzer.stop()
        analyzer.stop()
        analyzer.stop()

        assert not analyzer.is_running

    def test_stop_cancels_timer_if_present(self, analyzer, cb):
        """stop() should cancel _timer if it exists (legacy path)."""
        mock_timer = Mock()
        mock_timer.is_alive.return_value = True

        analyzer._is_running = True
        analyzer._timer = mock_timer
        analyzer._stop_event.clear()

        analyzer.stop(wait_for_callback=False)

        mock_timer.cancel.assert_called_once()

    def test_stop_joins_countdown_thread(self, analyzer, cb):
        """stop() should join countdown thread if alive."""
        analyzer.start(cb)
        time.sleep(0.1)

        # The countdown thread should be started
        assert analyzer._countdown_thread is not None

        analyzer.stop()
        # After stop, countdown_thread ref should be cleared
        # (set to None in stop method under lock)
        assert not analyzer.is_running


# ---------------------------------------------------------------------------
# start() / stop() cycles
# ---------------------------------------------------------------------------

class TestStartStopCycles:
    def test_multiple_start_stop_cycles(self, analyzer, cb):
        """Analyzer should work correctly across multiple start/stop cycles."""
        for i in range(3):
            analyzer.start(cb)
            assert analyzer.is_running
            assert analyzer.analysis_count == 0
            time.sleep(0.1)
            analyzer.stop()
            assert not analyzer.is_running

    def test_start_after_stop_clears_stop_event(self, analyzer, cb):
        """start() should clear _stop_event so countdown works again."""
        analyzer.start(cb)
        analyzer.stop()
        assert analyzer._stop_event.is_set()

        analyzer.start(cb)
        assert not analyzer._stop_event.is_set()
        analyzer.stop()


# ---------------------------------------------------------------------------
# add_to_history edge cases
# ---------------------------------------------------------------------------

class TestAddToHistoryEdgeCases:
    def test_default_metadata_is_empty_dict(self, analyzer):
        """add_to_history with no metadata should store empty dict."""
        analyzer.add_to_history("result", 10.0)
        entry = analyzer.analysis_history[0]
        assert entry["metadata"] == {}

    def test_analysis_number_matches_current_count(self, analyzer):
        """analysis_number in entry should match _analysis_count at time of add."""
        analyzer._analysis_count = 7
        analyzer.add_to_history("result", 10.0)
        assert analyzer.analysis_history[0]["analysis_number"] == 7

    def test_trim_removes_oldest_entry(self, analyzer):
        """When max exceeded, oldest entry is removed."""
        analyzer.max_history_items = 3
        analyzer.add_to_history("A", 1.0)
        analyzer.add_to_history("B", 2.0)
        analyzer.add_to_history("C", 3.0)
        analyzer.add_to_history("D", 4.0)

        history = analyzer.analysis_history
        assert len(history) == 3
        assert history[0]["result_text"] == "B"
        assert history[-1]["result_text"] == "D"

    def test_trim_at_exact_boundary(self, analyzer):
        """Adding exactly max_history_items should not trim."""
        analyzer.max_history_items = 3
        analyzer.add_to_history("A", 1.0)
        analyzer.add_to_history("B", 2.0)
        analyzer.add_to_history("C", 3.0)

        assert len(analyzer.analysis_history) == 3


# ---------------------------------------------------------------------------
# get_history_summary edge cases
# ---------------------------------------------------------------------------

class TestGetHistorySummaryEdgeCases:
    def test_has_metadata_flag_false_when_empty(self, analyzer):
        analyzer.add_to_history("result", 10.0, metadata={})
        summary = analyzer.get_history_summary()
        # Empty dict is falsy
        assert summary["entries"][0]["has_metadata"] is False

    def test_has_metadata_flag_true_when_present(self, analyzer):
        analyzer.add_to_history("result", 10.0, metadata={"key": "val"})
        summary = analyzer.get_history_summary()
        assert summary["entries"][0]["has_metadata"] is True

    def test_short_preview_not_truncated(self, analyzer):
        analyzer.add_to_history("short text", 10.0)
        summary = analyzer.get_history_summary()
        assert summary["entries"][0]["preview"] == "short text"

    def test_exactly_200_chars_not_truncated(self, analyzer):
        text = "x" * 200
        analyzer.add_to_history(text, 10.0)
        summary = analyzer.get_history_summary()
        assert summary["entries"][0]["preview"] == text

    def test_201_chars_truncated(self, analyzer):
        text = "x" * 201
        analyzer.add_to_history(text, 10.0)
        summary = analyzer.get_history_summary()
        preview = summary["entries"][0]["preview"]
        assert preview.endswith("...")
        assert len(preview) == 203

    def test_single_entry_summary(self, analyzer):
        analyzer.add_to_history("only one", 42.0)
        summary = analyzer.get_history_summary()
        assert summary["total_analyses"] == 1
        assert summary["first_analysis"] == summary["last_analysis"]
        assert summary["total_duration_seconds"] == 42.0


# ---------------------------------------------------------------------------
# get_combined_history_text formatting
# ---------------------------------------------------------------------------

class TestGetCombinedHistoryTextFormatting:
    def test_zero_seconds_format(self, analyzer):
        analyzer._analysis_count = 1
        analyzer.add_to_history("result", 0.0)
        text = analyzer.get_combined_history_text()
        assert "0:00" in text

    def test_exact_minute_format(self, analyzer):
        analyzer._analysis_count = 1
        analyzer.add_to_history("result", 120.0)
        text = analyzer.get_combined_history_text()
        assert "2:00" in text

    def test_seconds_padded(self, analyzer):
        analyzer._analysis_count = 1
        analyzer.add_to_history("result", 65.0)
        text = analyzer.get_combined_history_text()
        assert "1:05" in text

    def test_separator_present(self, analyzer):
        analyzer._analysis_count = 1
        analyzer.add_to_history("first", 60.0)
        analyzer._analysis_count = 2
        analyzer.add_to_history("second", 120.0)
        text = analyzer.get_combined_history_text()
        assert "─" in text

    def test_result_text_included(self, analyzer):
        analyzer._analysis_count = 1
        analyzer.add_to_history("specific result content", 30.0)
        text = analyzer.get_combined_history_text()
        assert "specific result content" in text


# ---------------------------------------------------------------------------
# set_interval
# ---------------------------------------------------------------------------

class TestSetInterval:
    def test_set_interval_updates_value(self, analyzer):
        analyzer.set_interval(300)
        assert analyzer.interval_seconds == 300

    def test_set_interval_small_value(self, analyzer):
        analyzer.set_interval(1)
        assert analyzer.interval_seconds == 1


# ---------------------------------------------------------------------------
# set_countdown_callback
# ---------------------------------------------------------------------------

class TestSetCountdownCallback:
    def test_set_to_none(self, analyzer):
        analyzer.set_countdown_callback(Mock())
        analyzer.set_countdown_callback(None)
        assert analyzer._countdown_callback is None

    def test_replace_callback(self, analyzer):
        cb1 = Mock()
        cb2 = Mock()
        analyzer.set_countdown_callback(cb1)
        analyzer.set_countdown_callback(cb2)
        assert analyzer._countdown_callback is cb2


# ---------------------------------------------------------------------------
# clear_history
# ---------------------------------------------------------------------------

class TestClearHistory:
    def test_clear_empty_history(self, analyzer):
        """Clearing empty history should not raise."""
        analyzer.clear_history()
        assert analyzer.analysis_history == []

    def test_clear_populated_history(self, analyzer):
        for i in range(5):
            analyzer.add_to_history(f"r{i}", float(i))
        analyzer.clear_history()
        assert analyzer.analysis_history == []


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

class TestProperties:
    def test_analysis_count_thread_safe(self, analyzer):
        """analysis_count property acquires lock."""
        analyzer._analysis_count = 42
        assert analyzer.analysis_count == 42

    def test_is_running_reflects_state(self, analyzer, cb):
        assert analyzer.is_running is False
        analyzer.start(cb)
        assert analyzer.is_running is True
        analyzer.stop()
        assert analyzer.is_running is False


# ---------------------------------------------------------------------------
# AudioSegmentExtractor
# ---------------------------------------------------------------------------

class TestAudioSegmentExtractorEdgeCases:
    def test_returns_combined_audio_directly(self):
        """Should return the AudioSegment object from get_combined_audio."""
        mock_rm = Mock()
        mock_asm = Mock()
        audio_obj = Mock()
        audio_obj.__len__ = Mock(return_value=44100)
        mock_asm.get_combined_audio.return_value = audio_obj

        result = AudioSegmentExtractor.extract_audio_segment(mock_rm, mock_asm)
        assert result is audio_obj

    def test_none_audio_returns_none(self):
        mock_rm = Mock()
        mock_asm = Mock()
        mock_asm.get_combined_audio.return_value = None

        result = AudioSegmentExtractor.extract_audio_segment(mock_rm, mock_asm)
        assert result is None

    def test_zero_length_audio_returns_none(self):
        mock_rm = Mock()
        mock_asm = Mock()
        audio_obj = Mock()
        audio_obj.__len__ = Mock(return_value=0)
        mock_asm.get_combined_audio.return_value = audio_obj

        result = AudioSegmentExtractor.extract_audio_segment(mock_rm, mock_asm)
        assert result is None

    def test_exception_returns_none(self):
        mock_rm = Mock()
        mock_asm = Mock()
        mock_asm.get_combined_audio.side_effect = ValueError("bad audio")

        result = AudioSegmentExtractor.extract_audio_segment(mock_rm, mock_asm)
        assert result is None

    def test_recording_manager_not_used(self):
        """recording_manager param is accepted but not used for extraction."""
        mock_rm = Mock()
        mock_asm = Mock()
        audio_obj = Mock()
        audio_obj.__len__ = Mock(return_value=100)
        mock_asm.get_combined_audio.return_value = audio_obj

        AudioSegmentExtractor.extract_audio_segment(mock_rm, mock_asm)

        # recording_manager should have no calls
        assert mock_rm.method_calls == []

    def test_attribute_error_returns_none(self):
        """Should handle audio_state_manager missing get_combined_audio."""
        mock_rm = Mock()
        mock_asm = Mock(spec=[])  # No methods

        result = AudioSegmentExtractor.extract_audio_segment(mock_rm, mock_asm)
        assert result is None


# ---------------------------------------------------------------------------
# Integration-style: full analysis cycle
# ---------------------------------------------------------------------------

class TestFullAnalysisCycle:
    def test_single_full_cycle(self):
        """Run a complete start -> analysis -> stop cycle."""
        analyzer = PeriodicAnalyzer(interval_seconds=1, max_history_items=10)
        results = []

        def on_analysis(num, elapsed):
            results.append((num, elapsed))
            # Add to history like the real app would
            analyzer.add_to_history(f"Result {num}", elapsed)

        countdown_values = []
        analyzer.set_countdown_callback(lambda v: countdown_values.append(v))

        analyzer.start(on_analysis)
        # Wait for at least one analysis
        time.sleep(2.0)
        analyzer.stop()

        # Should have run at least once
        assert len(results) >= 1
        assert results[0][0] == 1  # first analysis number
        assert len(analyzer.analysis_history) >= 1
        # Countdown should have been called
        assert len(countdown_values) > 0
        # -1 should be in countdown values (from stop)
        assert -1 in countdown_values

    def test_stop_prevents_further_analysis(self):
        """After stop, no more analyses should run."""
        analyzer = PeriodicAnalyzer(interval_seconds=1, max_history_items=10)
        call_count = []

        def on_analysis(num, elapsed):
            call_count.append(num)

        analyzer.start(on_analysis)
        time.sleep(1.5)
        analyzer.stop()

        count_at_stop = len(call_count)
        time.sleep(1.5)

        # No additional analyses after stop
        assert len(call_count) == count_at_stop
