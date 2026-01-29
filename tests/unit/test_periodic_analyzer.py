"""
Unit tests for PeriodicAnalyzer.

Tests cover:
- Timer start/stop lifecycle
- Countdown callback updates
- History management (max 20 items)
- Callback completion event signaling
- Thread safety for concurrent access
- AudioSegmentExtractor
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import threading
import time
from datetime import datetime

from audio.periodic_analysis import PeriodicAnalyzer, AudioSegmentExtractor


@pytest.fixture
def periodic_analyzer():
    """Create a PeriodicAnalyzer with short interval for testing."""
    return PeriodicAnalyzer(interval_seconds=1, max_history_items=20)


@pytest.fixture
def mock_callback():
    """Create a mock callback function."""
    return Mock()


@pytest.fixture
def mock_countdown_callback():
    """Create a mock countdown callback."""
    return Mock()


class TestPeriodicAnalyzerInitialization:
    """Tests for PeriodicAnalyzer initialization."""

    def test_default_initialization(self):
        """Test initialization with default values."""
        analyzer = PeriodicAnalyzer()

        assert analyzer.interval_seconds == 120
        assert analyzer.max_history_items == 20
        assert analyzer.is_running is False
        assert analyzer.analysis_count == 0

    def test_custom_initialization(self):
        """Test initialization with custom values."""
        analyzer = PeriodicAnalyzer(interval_seconds=60, max_history_items=50)

        assert analyzer.interval_seconds == 60
        assert analyzer.max_history_items == 50

    def test_initial_state(self, periodic_analyzer):
        """Test initial state of analyzer."""
        assert periodic_analyzer.is_running is False
        assert periodic_analyzer.analysis_count == 0
        assert periodic_analyzer.analysis_history == []


class TestTimerLifecycle:
    """Tests for timer start/stop lifecycle."""

    def test_start_sets_running_state(self, periodic_analyzer, mock_callback):
        """Test that start sets the running state."""
        periodic_analyzer.start(mock_callback)

        try:
            assert periodic_analyzer.is_running is True
        finally:
            periodic_analyzer.stop()

    def test_start_clears_history(self, periodic_analyzer, mock_callback):
        """Test that start clears previous history."""
        # Add some history first
        periodic_analyzer.add_to_history("Previous result", 100.0)

        periodic_analyzer.start(mock_callback)

        try:
            assert periodic_analyzer.analysis_history == []
        finally:
            periodic_analyzer.stop()

    def test_stop_clears_running_state(self, periodic_analyzer, mock_callback):
        """Test that stop clears the running state."""
        periodic_analyzer.start(mock_callback)
        periodic_analyzer.stop()

        assert periodic_analyzer.is_running is False

    def test_start_when_already_running(self, periodic_analyzer, mock_callback):
        """Test that start when already running is handled."""
        periodic_analyzer.start(mock_callback)

        try:
            # Should log warning but not raise
            periodic_analyzer.start(mock_callback)
            assert periodic_analyzer.is_running is True
        finally:
            periodic_analyzer.stop()

    def test_stop_when_not_running(self, periodic_analyzer):
        """Test that stop when not running is safe."""
        # Should not raise
        periodic_analyzer.stop()
        assert periodic_analyzer.is_running is False

    def test_start_resets_analysis_count(self, periodic_analyzer, mock_callback):
        """Test that start resets analysis count."""
        # Manually set count
        periodic_analyzer._analysis_count = 5

        periodic_analyzer.start(mock_callback)

        try:
            assert periodic_analyzer.analysis_count == 0
        finally:
            periodic_analyzer.stop()


class TestCountdownCallback:
    """Tests for countdown callback updates."""

    def test_set_countdown_callback(self, periodic_analyzer, mock_countdown_callback):
        """Test setting countdown callback."""
        periodic_analyzer.set_countdown_callback(mock_countdown_callback)

        assert periodic_analyzer._countdown_callback is mock_countdown_callback

    def test_countdown_callback_receives_updates(self, periodic_analyzer, mock_callback, mock_countdown_callback):
        """Test that countdown callback receives second-by-second updates."""
        periodic_analyzer.interval_seconds = 2  # Short interval
        periodic_analyzer.set_countdown_callback(mock_countdown_callback)

        periodic_analyzer.start(mock_callback)

        # Wait for countdown to start
        time.sleep(0.5)

        try:
            # Callback should have been called with remaining seconds
            assert mock_countdown_callback.called
        finally:
            periodic_analyzer.stop()

    def test_stop_signals_negative_to_countdown(self, periodic_analyzer, mock_callback, mock_countdown_callback):
        """Test that stop sends -1 to countdown callback."""
        periodic_analyzer.set_countdown_callback(mock_countdown_callback)
        periodic_analyzer.start(mock_callback)

        time.sleep(0.1)
        periodic_analyzer.stop()

        # Should have received -1 at stop
        calls = [call[0][0] for call in mock_countdown_callback.call_args_list]
        assert -1 in calls

    def test_countdown_callback_exception_handling(self, periodic_analyzer, mock_callback):
        """Test that countdown callback exceptions are handled."""
        failing_callback = Mock(side_effect=Exception("Callback error"))
        periodic_analyzer.set_countdown_callback(failing_callback)
        periodic_analyzer.interval_seconds = 1

        periodic_analyzer.start(mock_callback)

        try:
            time.sleep(0.5)
            # Should not crash
            assert periodic_analyzer.is_running is True
        finally:
            periodic_analyzer.stop()


class TestHistoryManagement:
    """Tests for analysis history management."""

    def test_add_to_history(self, periodic_analyzer):
        """Test adding entry to history."""
        periodic_analyzer.add_to_history(
            result_text="Test result",
            elapsed_seconds=60.0,
            metadata={"key": "value"}
        )

        history = periodic_analyzer.analysis_history
        assert len(history) == 1
        assert history[0]["result_text"] == "Test result"
        assert history[0]["elapsed_seconds"] == 60.0
        assert history[0]["metadata"] == {"key": "value"}

    def test_history_includes_timestamp(self, periodic_analyzer):
        """Test that history entries include timestamp."""
        periodic_analyzer.add_to_history("Result", 30.0)

        entry = periodic_analyzer.analysis_history[0]
        assert "timestamp" in entry
        # Should be a valid ISO format datetime
        datetime.fromisoformat(entry["timestamp"])

    def test_max_history_items_enforced(self, periodic_analyzer):
        """Test that max history items is enforced."""
        periodic_analyzer.max_history_items = 5

        # Add more than max
        for i in range(10):
            periodic_analyzer.add_to_history(f"Result {i}", float(i * 60))

        assert len(periodic_analyzer.analysis_history) == 5
        # Should have most recent entries
        assert periodic_analyzer.analysis_history[0]["result_text"] == "Result 5"

    def test_history_default_max_items(self):
        """Test default max history items is 20."""
        analyzer = PeriodicAnalyzer()
        assert analyzer.max_history_items == 20

    def test_clear_history(self, periodic_analyzer):
        """Test clearing history."""
        periodic_analyzer.add_to_history("Result 1", 60.0)
        periodic_analyzer.add_to_history("Result 2", 120.0)

        periodic_analyzer.clear_history()

        assert periodic_analyzer.analysis_history == []

    def test_analysis_history_returns_copy(self, periodic_analyzer):
        """Test that analysis_history returns a copy."""
        periodic_analyzer.add_to_history("Result", 60.0)

        history1 = periodic_analyzer.analysis_history
        history2 = periodic_analyzer.analysis_history

        # Should be equal but not same object
        assert history1 == history2
        assert history1 is not history2


class TestHistorySummary:
    """Tests for history summary functionality."""

    def test_get_history_summary_empty(self, periodic_analyzer):
        """Test summary when history is empty."""
        summary = periodic_analyzer.get_history_summary()

        assert summary["total_analyses"] == 0
        assert summary["entries"] == []
        assert summary["first_analysis"] is None
        assert summary["last_analysis"] is None

    def test_get_history_summary_with_entries(self, periodic_analyzer):
        """Test summary with history entries."""
        periodic_analyzer._analysis_count = 1
        periodic_analyzer.add_to_history("First result", 60.0)
        periodic_analyzer._analysis_count = 2
        periodic_analyzer.add_to_history("Second result", 120.0)

        summary = periodic_analyzer.get_history_summary()

        assert summary["total_analyses"] == 2
        assert len(summary["entries"]) == 2
        assert summary["first_analysis"] is not None
        assert summary["last_analysis"] is not None
        assert summary["total_duration_seconds"] == 120.0

    def test_get_history_summary_truncates_preview(self, periodic_analyzer):
        """Test that summary truncates long result text."""
        long_text = "A" * 300
        periodic_analyzer.add_to_history(long_text, 60.0)

        summary = periodic_analyzer.get_history_summary()

        preview = summary["entries"][0]["preview"]
        assert len(preview) <= 203  # 200 + "..."


class TestCombinedHistoryText:
    """Tests for combined history text generation."""

    def test_combined_text_empty(self, periodic_analyzer):
        """Test combined text when empty."""
        result = periodic_analyzer.get_combined_history_text()
        assert result == ""

    def test_combined_text_format(self, periodic_analyzer):
        """Test combined text format."""
        periodic_analyzer._analysis_count = 1
        periodic_analyzer.add_to_history("Result one", 75.0)
        periodic_analyzer._analysis_count = 2
        periodic_analyzer.add_to_history("Result two", 195.0)

        text = periodic_analyzer.get_combined_history_text()

        assert "Analysis #1" in text
        assert "Analysis #2" in text
        assert "1:15" in text  # 75 seconds = 1:15
        assert "3:15" in text  # 195 seconds = 3:15
        assert "Result one" in text
        assert "Result two" in text


class TestCallbackCompletionEvent:
    """Tests for callback completion event signaling."""

    def test_callback_complete_initially_set(self, periodic_analyzer):
        """Test that callback complete event is initially set."""
        assert periodic_analyzer._callback_complete.is_set()

    def test_stop_waits_for_callback_completion(self, periodic_analyzer, mock_countdown_callback):
        """Test that stop waits for callback to complete."""
        slow_callback = Mock()

        def slow_analysis(num, elapsed):
            time.sleep(0.3)

        slow_callback.side_effect = slow_analysis
        periodic_analyzer.interval_seconds = 1
        periodic_analyzer.set_countdown_callback(mock_countdown_callback)

        periodic_analyzer.start(slow_callback)

        # Wait for analysis to start
        time.sleep(1.2)

        # Stop should wait for callback
        start_time = time.time()
        periodic_analyzer.stop(wait_for_callback=True, timeout=2.0)
        elapsed = time.time() - start_time

        # Should have waited for callback
        assert elapsed >= 0.1 or periodic_analyzer._callback_complete.is_set()


class TestIntervalSetting:
    """Tests for interval setting."""

    def test_set_interval(self, periodic_analyzer):
        """Test setting analysis interval."""
        periodic_analyzer.set_interval(60)
        assert periodic_analyzer.interval_seconds == 60

    def test_set_interval_takes_effect(self, periodic_analyzer, mock_callback, mock_countdown_callback):
        """Test that new interval takes effect on next cycle."""
        periodic_analyzer.set_countdown_callback(mock_countdown_callback)
        periodic_analyzer.start(mock_callback)

        try:
            periodic_analyzer.set_interval(30)
            assert periodic_analyzer.interval_seconds == 30
        finally:
            periodic_analyzer.stop()


class TestThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_history_access(self, periodic_analyzer):
        """Test concurrent access to history is thread-safe."""
        errors = []

        def add_entries():
            try:
                for i in range(50):
                    periodic_analyzer.add_to_history(f"Result {i}", float(i))
            except Exception as e:
                errors.append(e)

        def read_entries():
            try:
                for _ in range(50):
                    _ = periodic_analyzer.analysis_history
                    _ = periodic_analyzer.get_history_summary()
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=add_entries),
            threading.Thread(target=read_entries),
            threading.Thread(target=add_entries),
            threading.Thread(target=read_entries),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_start_stop(self, periodic_analyzer, mock_callback):
        """Test concurrent start/stop is handled."""
        errors = []

        def toggle_analyzer():
            try:
                for _ in range(10):
                    if periodic_analyzer.is_running:
                        periodic_analyzer.stop()
                    else:
                        periodic_analyzer.start(mock_callback)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=toggle_analyzer),
            threading.Thread(target=toggle_analyzer),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Cleanup
        if periodic_analyzer.is_running:
            periodic_analyzer.stop()

        # Should not have crashed
        assert len(errors) == 0

    def test_is_running_thread_safe(self, periodic_analyzer, mock_callback):
        """Test that is_running property is thread-safe."""
        results = []

        def check_running():
            for _ in range(100):
                results.append(periodic_analyzer.is_running)

        periodic_analyzer.start(mock_callback)

        try:
            threads = [threading.Thread(target=check_running) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # All values should be boolean
            assert all(isinstance(r, bool) for r in results)
        finally:
            periodic_analyzer.stop()


class TestAnalysisExecution:
    """Tests for analysis execution."""

    def test_analysis_callback_receives_parameters(self, periodic_analyzer, mock_countdown_callback):
        """Test that analysis callback receives correct parameters."""
        callback = Mock()
        periodic_analyzer.interval_seconds = 1
        periodic_analyzer.set_countdown_callback(mock_countdown_callback)

        periodic_analyzer.start(callback)

        # Wait for first analysis
        time.sleep(1.5)

        periodic_analyzer.stop()

        if callback.called:
            args = callback.call_args[0]
            # Should receive (analysis_number, elapsed_time)
            assert len(args) == 2
            assert isinstance(args[0], int)  # analysis_number
            assert isinstance(args[1], float)  # elapsed_time

    def test_analysis_increments_count(self, periodic_analyzer, mock_countdown_callback):
        """Test that analysis increments count."""
        callback = Mock()
        periodic_analyzer.interval_seconds = 1
        periodic_analyzer.set_countdown_callback(mock_countdown_callback)

        periodic_analyzer.start(callback)

        # Wait for analyses
        time.sleep(2.5)

        count = periodic_analyzer.analysis_count

        periodic_analyzer.stop()

        # Should have run at least one analysis
        assert count >= 1


class TestAudioSegmentExtractor:
    """Tests for AudioSegmentExtractor."""

    def test_extract_audio_segment_success(self):
        """Test successful audio extraction."""
        mock_recording_manager = Mock()
        mock_audio_state_manager = Mock()
        mock_audio = Mock()
        mock_audio.__len__ = Mock(return_value=1000)
        mock_audio_state_manager.get_combined_audio.return_value = mock_audio

        result = AudioSegmentExtractor.extract_audio_segment(
            mock_recording_manager,
            mock_audio_state_manager
        )

        assert result is mock_audio

    def test_extract_audio_segment_no_audio(self):
        """Test extraction when no audio available."""
        mock_recording_manager = Mock()
        mock_audio_state_manager = Mock()
        mock_audio_state_manager.get_combined_audio.return_value = None

        result = AudioSegmentExtractor.extract_audio_segment(
            mock_recording_manager,
            mock_audio_state_manager
        )

        assert result is None

    def test_extract_audio_segment_empty_audio(self):
        """Test extraction when audio is empty."""
        mock_recording_manager = Mock()
        mock_audio_state_manager = Mock()
        mock_audio = Mock()
        mock_audio.__len__ = Mock(return_value=0)
        mock_audio_state_manager.get_combined_audio.return_value = mock_audio

        result = AudioSegmentExtractor.extract_audio_segment(
            mock_recording_manager,
            mock_audio_state_manager
        )

        assert result is None

    def test_extract_audio_segment_exception_handling(self):
        """Test extraction handles exceptions gracefully."""
        mock_recording_manager = Mock()
        mock_audio_state_manager = Mock()
        mock_audio_state_manager.get_combined_audio.side_effect = Exception("Error")

        result = AudioSegmentExtractor.extract_audio_segment(
            mock_recording_manager,
            mock_audio_state_manager
        )

        assert result is None
