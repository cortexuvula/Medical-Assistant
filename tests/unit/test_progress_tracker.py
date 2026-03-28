"""Tests for utils.progress_tracker — progress tracking utilities."""

import pytest
from unittest.mock import Mock, patch, call

from utils.progress_tracker import (
    ProgressInfo,
    ProgressTracker,
    DocumentGenerationProgress,
)


class TestProgressInfo:
    def test_str_without_estimated_remaining(self):
        info = ProgressInfo(
            current=3, total=10, percentage=30.0,
            message="Working...", time_elapsed=5.0,
        )
        result = str(info)
        assert "Working..." in result
        assert "30%" in result
        assert "remaining" not in result

    def test_str_with_estimated_remaining(self):
        info = ProgressInfo(
            current=5, total=10, percentage=50.0,
            message="Half done", time_elapsed=10.0,
            estimated_remaining=10.0,
        )
        result = str(info)
        assert "Half done" in result
        assert "50%" in result
        assert "10s remaining" in result

    def test_dataclass_fields(self):
        info = ProgressInfo(
            current=1, total=5, percentage=20.0,
            message="msg", time_elapsed=2.0,
        )
        assert info.current == 1
        assert info.total == 5
        assert info.percentage == 20.0
        assert info.message == "msg"
        assert info.time_elapsed == 2.0
        assert info.estimated_remaining is None


class TestProgressTracker:
    @patch("utils.progress_tracker.time")
    def test_sends_initial_progress_on_init(self, mock_time):
        mock_time.time.return_value = 100.0
        cb = Mock()
        ProgressTracker(total_steps=5, callback=cb, initial_message="Starting")
        assert cb.call_count == 1
        info = cb.call_args[0][0]
        assert info.current == 0
        assert info.percentage == 0.0
        assert info.message == "Starting"

    @patch("utils.progress_tracker.time")
    def test_update_increments_step(self, mock_time):
        mock_time.time.return_value = 100.0
        cb = Mock()
        tracker = ProgressTracker(total_steps=5, callback=cb)
        mock_time.time.return_value = 101.0
        tracker.update("Step 1")
        info = cb.call_args[0][0]
        assert info.current == 1
        assert info.message == "Step 1"

    @patch("utils.progress_tracker.time")
    def test_update_custom_increment(self, mock_time):
        mock_time.time.return_value = 100.0
        cb = Mock()
        tracker = ProgressTracker(total_steps=10, callback=cb)
        mock_time.time.return_value = 102.0
        tracker.update("Jump ahead", increment=3)
        info = cb.call_args[0][0]
        assert info.current == 3

    @patch("utils.progress_tracker.time")
    def test_update_clamps_to_total(self, mock_time):
        mock_time.time.return_value = 100.0
        cb = Mock()
        tracker = ProgressTracker(total_steps=2, callback=cb)
        mock_time.time.return_value = 101.0
        tracker.update(increment=10)
        info = cb.call_args[0][0]
        assert info.current == 2

    @patch("utils.progress_tracker.time")
    def test_set_progress_to_specific_step(self, mock_time):
        mock_time.time.return_value = 100.0
        cb = Mock()
        tracker = ProgressTracker(total_steps=10, callback=cb)
        mock_time.time.return_value = 105.0
        tracker.set_progress(7, "At step 7")
        info = cb.call_args[0][0]
        assert info.current == 7
        assert info.message == "At step 7"

    @patch("utils.progress_tracker.time")
    def test_set_progress_clamps_to_total(self, mock_time):
        mock_time.time.return_value = 100.0
        cb = Mock()
        tracker = ProgressTracker(total_steps=5, callback=cb)
        tracker.set_progress(99)
        info = cb.call_args[0][0]
        assert info.current == 5

    @patch("utils.progress_tracker.time")
    def test_complete_sets_to_total(self, mock_time):
        mock_time.time.return_value = 100.0
        cb = Mock()
        tracker = ProgressTracker(total_steps=5, callback=cb)
        mock_time.time.return_value = 110.0
        tracker.complete("All done")
        info = cb.call_args[0][0]
        assert info.current == 5
        assert info.percentage == 100.0
        assert info.message == "All done"

    @patch("utils.progress_tracker.time")
    def test_estimated_remaining_calculated(self, mock_time):
        mock_time.time.return_value = 100.0
        cb = Mock()
        tracker = ProgressTracker(total_steps=4, callback=cb)
        # After 2 seconds, complete 1 of 4 steps → avg 2s/step → 3 steps remaining → ~6s
        mock_time.time.return_value = 102.0
        tracker.update("Step 1")
        info = cb.call_args[0][0]
        assert info.estimated_remaining is not None
        assert info.estimated_remaining == pytest.approx(6.0, abs=0.5)

    @patch("utils.progress_tracker.time")
    def test_no_estimated_remaining_at_completion(self, mock_time):
        mock_time.time.return_value = 100.0
        cb = Mock()
        tracker = ProgressTracker(total_steps=1, callback=cb)
        mock_time.time.return_value = 101.0
        tracker.complete()
        info = cb.call_args[0][0]
        # At 100% there should be no estimated remaining
        assert info.estimated_remaining is None

    @patch("utils.progress_tracker.time")
    def test_no_callback_does_not_error(self, mock_time):
        mock_time.time.return_value = 100.0
        tracker = ProgressTracker(total_steps=5, callback=None)
        tracker.update("step")
        tracker.complete()

    @patch("utils.progress_tracker.time")
    def test_callback_exception_is_caught(self, mock_time):
        mock_time.time.return_value = 100.0
        cb = Mock(side_effect=RuntimeError("callback crash"))
        # Should not raise — exception is caught internally
        tracker = ProgressTracker(total_steps=5, callback=cb)
        tracker.update("step")


class TestDocumentGenerationProgress:
    def test_create_soap_tracker(self):
        cb = Mock()
        tracker = DocumentGenerationProgress.create_soap_tracker(cb)
        assert isinstance(tracker, ProgressTracker)
        assert tracker.total_steps == len(DocumentGenerationProgress.SOAP_STEPS)

    def test_create_referral_tracker(self):
        cb = Mock()
        tracker = DocumentGenerationProgress.create_referral_tracker(cb)
        assert isinstance(tracker, ProgressTracker)
        assert tracker.total_steps == len(DocumentGenerationProgress.REFERRAL_STEPS)

    def test_create_diagnostic_tracker(self):
        cb = Mock()
        tracker = DocumentGenerationProgress.create_diagnostic_tracker(cb)
        assert isinstance(tracker, ProgressTracker)
        assert tracker.total_steps == len(DocumentGenerationProgress.DIAGNOSTIC_STEPS)

    def test_soap_tracker_sends_initial_callback(self):
        cb = Mock()
        DocumentGenerationProgress.create_soap_tracker(cb)
        assert cb.call_count == 1
        info = cb.call_args[0][0]
        assert "SOAP" in info.message
