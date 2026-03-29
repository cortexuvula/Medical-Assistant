"""
Comprehensive unit tests for src/utils/progress_tracker.py.

Covers ProgressInfo, ProgressTracker, and DocumentGenerationProgress.
"""

import sys
import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from utils.progress_tracker import ProgressInfo, ProgressTracker, DocumentGenerationProgress


# ---------------------------------------------------------------------------
# ProgressInfo tests
# ---------------------------------------------------------------------------

class TestProgressInfoDataclass:
    """Tests for ProgressInfo dataclass fields and defaults."""

    def test_basic_construction(self):
        info = ProgressInfo(current=3, total=10, percentage=30.0,
                            message="Working", time_elapsed=1.5)
        assert info.current == 3
        assert info.total == 10
        assert info.percentage == 30.0
        assert info.message == "Working"
        assert info.time_elapsed == 1.5
        assert info.estimated_remaining is None

    def test_estimated_remaining_default_is_none(self):
        info = ProgressInfo(current=0, total=5, percentage=0.0,
                            message="Start", time_elapsed=0.0)
        assert info.estimated_remaining is None

    def test_estimated_remaining_can_be_set(self):
        info = ProgressInfo(current=1, total=2, percentage=50.0,
                            message="Halfway", time_elapsed=2.0,
                            estimated_remaining=2.0)
        assert info.estimated_remaining == 2.0

    def test_zero_current_and_total(self):
        info = ProgressInfo(current=0, total=0, percentage=0.0,
                            message="Empty", time_elapsed=0.0)
        assert info.current == 0
        assert info.total == 0

    def test_complete_at_100_percent(self):
        info = ProgressInfo(current=10, total=10, percentage=100.0,
                            message="Done", time_elapsed=5.0)
        assert info.percentage == 100.0

    def test_fields_are_mutable(self):
        info = ProgressInfo(current=1, total=5, percentage=20.0,
                            message="Going", time_elapsed=0.5)
        info.current = 2
        assert info.current == 2


class TestProgressInfoStr:
    """Tests for ProgressInfo.__str__."""

    def test_str_without_estimated_remaining(self):
        info = ProgressInfo(current=5, total=10, percentage=50.0,
                            message="Processing", time_elapsed=1.0)
        assert str(info) == "Processing (50%)"

    def test_str_with_estimated_remaining(self):
        info = ProgressInfo(current=5, total=10, percentage=50.0,
                            message="Processing", time_elapsed=1.0,
                            estimated_remaining=10.0)
        assert str(info) == "Processing (50% - 10s remaining)"

    def test_str_percentage_rounds_to_zero_decimals(self):
        info = ProgressInfo(current=1, total=3, percentage=33.333,
                            message="Almost", time_elapsed=0.5)
        result = str(info)
        assert "33%" in result

    def test_str_percentage_rounds_up(self):
        info = ProgressInfo(current=2, total=3, percentage=66.666,
                            message="More", time_elapsed=0.5)
        result = str(info)
        assert "67%" in result

    def test_str_100_percent(self):
        info = ProgressInfo(current=10, total=10, percentage=100.0,
                            message="Complete", time_elapsed=3.0)
        assert str(info) == "Complete (100%)"

    def test_str_0_percent(self):
        info = ProgressInfo(current=0, total=10, percentage=0.0,
                            message="Start", time_elapsed=0.0)
        assert str(info) == "Start (0%)"

    def test_str_estimated_remaining_rounds_to_zero_decimals(self):
        info = ProgressInfo(current=3, total=6, percentage=50.0,
                            message="Halfway", time_elapsed=1.5,
                            estimated_remaining=2.7)
        result = str(info)
        assert "3s remaining" in result

    def test_str_estimated_remaining_zero_is_falsy_so_no_remaining(self):
        """estimated_remaining=0 is falsy; __str__ uses the no-remaining branch."""
        info = ProgressInfo(current=10, total=10, percentage=100.0,
                            message="Done", time_elapsed=2.0,
                            estimated_remaining=0.0)
        result = str(info)
        assert "remaining" not in result
        assert str(info) == "Done (100%)"

    def test_str_message_with_special_characters(self):
        info = ProgressInfo(current=1, total=4, percentage=25.0,
                            message="Step 1/4: Prepare & upload",
                            time_elapsed=0.1)
        assert "Step 1/4: Prepare & upload" in str(info)

    def test_str_with_large_estimated_remaining(self):
        info = ProgressInfo(current=1, total=100, percentage=1.0,
                            message="Starting", time_elapsed=0.1,
                            estimated_remaining=999.9)
        assert "1000s remaining" in str(info)


# ---------------------------------------------------------------------------
# ProgressTracker.__init__ tests
# ---------------------------------------------------------------------------

class TestProgressTrackerInit:
    """Tests for ProgressTracker initialisation."""

    def test_init_fires_callback_immediately(self):
        cb = MagicMock()
        ProgressTracker(total_steps=5, callback=cb)
        cb.assert_called_once()

    def test_init_callback_receives_progress_info(self):
        cb = MagicMock()
        ProgressTracker(total_steps=5, callback=cb)
        args = cb.call_args[0]
        assert len(args) == 1
        assert isinstance(args[0], ProgressInfo)

    def test_init_progress_info_has_correct_total(self):
        cb = MagicMock()
        ProgressTracker(total_steps=8, callback=cb)
        info = cb.call_args[0][0]
        assert info.total == 8

    def test_init_progress_info_current_is_zero(self):
        cb = MagicMock()
        ProgressTracker(total_steps=8, callback=cb)
        info = cb.call_args[0][0]
        assert info.current == 0

    def test_init_progress_info_percentage_is_zero(self):
        cb = MagicMock()
        ProgressTracker(total_steps=8, callback=cb)
        info = cb.call_args[0][0]
        assert info.percentage == 0.0

    def test_init_default_message(self):
        cb = MagicMock()
        ProgressTracker(total_steps=4, callback=cb)
        info = cb.call_args[0][0]
        assert info.message == "Processing..."

    def test_init_custom_message(self):
        cb = MagicMock()
        ProgressTracker(total_steps=4, callback=cb, initial_message="Custom start")
        info = cb.call_args[0][0]
        assert info.message == "Custom start"

    def test_init_no_callback_does_not_raise(self):
        tracker = ProgressTracker(total_steps=5)
        assert tracker.callback is None

    def test_init_none_callback_explicit(self):
        tracker = ProgressTracker(total_steps=5, callback=None)
        assert tracker.callback is None

    def test_init_total_steps_stored(self):
        tracker = ProgressTracker(total_steps=12)
        assert tracker.total_steps == 12

    def test_init_current_step_zero(self):
        tracker = ProgressTracker(total_steps=12)
        assert tracker.current_step == 0

    def test_init_step_times_empty_list(self):
        tracker = ProgressTracker(total_steps=5)
        assert tracker.step_times == []

    def test_init_start_time_set(self):
        before = time.time()
        tracker = ProgressTracker(total_steps=5)
        after = time.time()
        assert before <= tracker.start_time <= after

    def test_init_estimated_remaining_none_at_step_zero(self):
        cb = MagicMock()
        ProgressTracker(total_steps=5, callback=cb)
        info = cb.call_args[0][0]
        assert info.estimated_remaining is None


# ---------------------------------------------------------------------------
# ProgressTracker.update tests
# ---------------------------------------------------------------------------

class TestProgressTrackerUpdate:
    """Tests for ProgressTracker.update."""

    def test_update_increments_step_by_one_default(self):
        tracker = ProgressTracker(total_steps=10)
        tracker.update()
        assert tracker.current_step == 1

    def test_update_calls_callback(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=10, callback=cb)
        cb.reset_mock()
        tracker.update()
        cb.assert_called_once()

    def test_update_callback_receives_progress_info(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=10, callback=cb)
        cb.reset_mock()
        tracker.update(message="Step 1")
        info = cb.call_args[0][0]
        assert isinstance(info, ProgressInfo)

    def test_update_increments_custom_amount(self):
        tracker = ProgressTracker(total_steps=10)
        tracker.update(increment=3)
        assert tracker.current_step == 3

    def test_update_capped_at_total(self):
        tracker = ProgressTracker(total_steps=5)
        tracker.update(increment=100)
        assert tracker.current_step == 5

    def test_update_multiple_increments_accumulate(self):
        tracker = ProgressTracker(total_steps=10)
        tracker.update(increment=2)
        tracker.update(increment=3)
        assert tracker.current_step == 5

    def test_update_message_changes_current_message(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=10, callback=cb)
        cb.reset_mock()
        tracker.update(message="New message")
        info = cb.call_args[0][0]
        assert info.message == "New message"

    def test_update_no_message_keeps_previous_message(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=10, callback=cb, initial_message="Init")
        cb.reset_mock()
        tracker.update()
        info = cb.call_args[0][0]
        assert info.message == "Init"

    def test_update_percentage_correct_after_increment(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=10, callback=cb)
        cb.reset_mock()
        tracker.update(increment=5)
        info = cb.call_args[0][0]
        assert info.percentage == 50.0

    def test_update_at_total_gives_100_percent(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=4, callback=cb)
        cb.reset_mock()
        tracker.update(increment=4)
        info = cb.call_args[0][0]
        assert info.percentage == 100.0

    def test_update_tracks_step_times(self):
        tracker = ProgressTracker(total_steps=10)
        tracker.update()
        assert len(tracker.step_times) == 1

    def test_update_without_callback_does_not_raise(self):
        tracker = ProgressTracker(total_steps=5)
        tracker.update(message="No callback", increment=1)

    def test_update_current_step_not_negative_on_zero_increment(self):
        tracker = ProgressTracker(total_steps=5)
        tracker.update(increment=0)
        assert tracker.current_step == 0

    def test_update_current_info_current_matches_tracker_step(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=6, callback=cb)
        cb.reset_mock()
        tracker.update(increment=2)
        info = cb.call_args[0][0]
        assert info.current == tracker.current_step


# ---------------------------------------------------------------------------
# ProgressTracker.set_progress tests
# ---------------------------------------------------------------------------

class TestProgressTrackerSetProgress:
    """Tests for ProgressTracker.set_progress."""

    def test_set_progress_sets_step(self):
        tracker = ProgressTracker(total_steps=10)
        tracker.set_progress(7)
        assert tracker.current_step == 7

    def test_set_progress_calls_callback(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=10, callback=cb)
        cb.reset_mock()
        tracker.set_progress(3)
        cb.assert_called_once()

    def test_set_progress_capped_at_total(self):
        tracker = ProgressTracker(total_steps=5)
        tracker.set_progress(99)
        assert tracker.current_step == 5

    def test_set_progress_to_zero(self):
        tracker = ProgressTracker(total_steps=10)
        tracker.update(increment=5)
        tracker.set_progress(0)
        assert tracker.current_step == 0

    def test_set_progress_message_updates(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=10, callback=cb)
        cb.reset_mock()
        tracker.set_progress(4, message="Custom")
        info = cb.call_args[0][0]
        assert info.message == "Custom"

    def test_set_progress_no_message_keeps_existing(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=10, callback=cb, initial_message="Keep")
        cb.reset_mock()
        tracker.set_progress(4)
        info = cb.call_args[0][0]
        assert info.message == "Keep"

    def test_set_progress_percentage_correct(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=10, callback=cb)
        cb.reset_mock()
        tracker.set_progress(1)
        info = cb.call_args[0][0]
        assert info.percentage == 10.0

    def test_set_progress_without_callback_does_not_raise(self):
        tracker = ProgressTracker(total_steps=5)
        tracker.set_progress(3)

    def test_set_progress_info_current_matches(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=10, callback=cb)
        cb.reset_mock()
        tracker.set_progress(7)
        info = cb.call_args[0][0]
        assert info.current == 7

    def test_set_progress_total_stays_same(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=10, callback=cb)
        cb.reset_mock()
        tracker.set_progress(5)
        info = cb.call_args[0][0]
        assert info.total == 10


# ---------------------------------------------------------------------------
# ProgressTracker.complete tests
# ---------------------------------------------------------------------------

class TestProgressTrackerComplete:
    """Tests for ProgressTracker.complete."""

    def test_complete_sets_step_to_total(self):
        tracker = ProgressTracker(total_steps=7)
        tracker.complete()
        assert tracker.current_step == 7

    def test_complete_calls_callback(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=7, callback=cb)
        cb.reset_mock()
        tracker.complete()
        cb.assert_called_once()

    def test_complete_default_message(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=5, callback=cb)
        cb.reset_mock()
        tracker.complete()
        info = cb.call_args[0][0]
        assert info.message == "Complete"

    def test_complete_custom_message(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=5, callback=cb)
        cb.reset_mock()
        tracker.complete(message="All done!")
        info = cb.call_args[0][0]
        assert info.message == "All done!"

    def test_complete_info_percentage_100(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=5, callback=cb)
        cb.reset_mock()
        tracker.complete()
        info = cb.call_args[0][0]
        assert info.percentage == 100.0

    def test_complete_info_current_equals_total(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=5, callback=cb)
        cb.reset_mock()
        tracker.complete()
        info = cb.call_args[0][0]
        assert info.current == info.total

    def test_complete_without_callback_does_not_raise(self):
        tracker = ProgressTracker(total_steps=5)
        tracker.complete()

    def test_complete_when_already_at_total_stays_at_total(self):
        tracker = ProgressTracker(total_steps=3)
        tracker.update(increment=3)
        tracker.complete()
        assert tracker.current_step == 3

    def test_complete_estimated_remaining_is_none(self):
        """At step==total, estimated_remaining should be None."""
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=5, callback=cb)
        cb.reset_mock()
        tracker.complete()
        info = cb.call_args[0][0]
        assert info.estimated_remaining is None


# ---------------------------------------------------------------------------
# ProgressTracker._send_progress / percentage calculation tests
# ---------------------------------------------------------------------------

class TestProgressTrackerSendProgress:
    """Tests for _send_progress internals and percentage edge cases."""

    def test_percentage_0_of_10(self):
        cb = MagicMock()
        ProgressTracker(total_steps=10, callback=cb)
        info = cb.call_args[0][0]
        assert info.percentage == 0.0

    def test_percentage_5_of_10(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=10, callback=cb)
        cb.reset_mock()
        tracker.update(increment=5)
        info = cb.call_args[0][0]
        assert info.percentage == 50.0

    def test_percentage_10_of_10(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=10, callback=cb)
        cb.reset_mock()
        tracker.complete()
        info = cb.call_args[0][0]
        assert info.percentage == 100.0

    def test_percentage_total_zero_no_division_error(self):
        """total_steps=0 must return 0% not raise ZeroDivisionError."""
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=0, callback=cb)
        info = cb.call_args[0][0]
        assert info.percentage == 0.0

    def test_no_callback_send_progress_does_not_raise(self):
        tracker = ProgressTracker(total_steps=5)
        tracker._send_progress()

    def test_callback_exception_is_swallowed(self):
        def bad_callback(info):
            raise RuntimeError("boom")

        tracker = ProgressTracker(total_steps=5, callback=bad_callback)
        # If exception propagated, the line below would never run
        tracker.update(message="Should not raise")
        # Just reaching here proves exception was swallowed

    def test_callback_exception_on_init_swallowed(self):
        def bad_callback(info):
            raise ValueError("init error")

        # Must not raise during __init__
        tracker = ProgressTracker(total_steps=5, callback=bad_callback)
        assert tracker is not None

    def test_time_elapsed_is_non_negative(self):
        cb = MagicMock()
        ProgressTracker(total_steps=5, callback=cb)
        info = cb.call_args[0][0]
        assert info.time_elapsed >= 0.0

    def test_estimated_remaining_present_mid_progress(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=10, callback=cb)
        cb.reset_mock()
        tracker.update(increment=5)
        info = cb.call_args[0][0]
        # At step 5/10 (not complete), estimated_remaining should be set
        assert info.estimated_remaining is not None

    def test_estimated_remaining_none_when_complete(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=10, callback=cb)
        cb.reset_mock()
        tracker.complete()
        info = cb.call_args[0][0]
        assert info.estimated_remaining is None

    def test_estimated_remaining_none_at_step_zero(self):
        cb = MagicMock()
        ProgressTracker(total_steps=10, callback=cb)
        info = cb.call_args[0][0]
        assert info.estimated_remaining is None

    def test_callback_called_with_progress_info_instance(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=4, callback=cb)
        cb.reset_mock()
        tracker.update()
        assert isinstance(cb.call_args[0][0], ProgressInfo)

    def test_callback_total_never_changes(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=6, callback=cb)
        tracker.update(increment=2)
        tracker.update(increment=2)
        tracker.complete()
        for c in cb.call_args_list:
            assert c[0][0].total == 6

    def test_percentage_one_of_four(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=4, callback=cb)
        cb.reset_mock()
        tracker.update(increment=1)
        info = cb.call_args[0][0]
        assert info.percentage == 25.0

    def test_percentage_three_of_four(self):
        cb = MagicMock()
        tracker = ProgressTracker(total_steps=4, callback=cb)
        cb.reset_mock()
        tracker.update(increment=3)
        info = cb.call_args[0][0]
        assert info.percentage == 75.0


# ---------------------------------------------------------------------------
# DocumentGenerationProgress class attribute tests
# ---------------------------------------------------------------------------

class TestDocumentGenerationProgressAttributes:
    """Tests for DocumentGenerationProgress class-level constants."""

    def test_soap_steps_is_list(self):
        assert isinstance(DocumentGenerationProgress.SOAP_STEPS, list)

    def test_soap_steps_length_six(self):
        assert len(DocumentGenerationProgress.SOAP_STEPS) == 6

    def test_referral_steps_is_list(self):
        assert isinstance(DocumentGenerationProgress.REFERRAL_STEPS, list)

    def test_referral_steps_length_five(self):
        assert len(DocumentGenerationProgress.REFERRAL_STEPS) == 5

    def test_diagnostic_steps_is_list(self):
        assert isinstance(DocumentGenerationProgress.DIAGNOSTIC_STEPS, list)

    def test_diagnostic_steps_length_six(self):
        assert len(DocumentGenerationProgress.DIAGNOSTIC_STEPS) == 6

    def test_soap_steps_each_item_is_tuple(self):
        for item in DocumentGenerationProgress.SOAP_STEPS:
            assert isinstance(item, tuple), f"Expected tuple, got {type(item)}"

    def test_referral_steps_each_item_is_tuple(self):
        for item in DocumentGenerationProgress.REFERRAL_STEPS:
            assert isinstance(item, tuple)

    def test_diagnostic_steps_each_item_is_tuple(self):
        for item in DocumentGenerationProgress.DIAGNOSTIC_STEPS:
            assert isinstance(item, tuple)

    def test_soap_steps_first_item_fraction(self):
        weight, label = DocumentGenerationProgress.SOAP_STEPS[0]
        assert 0.0 < weight <= 1.0

    def test_soap_steps_last_item_weight_is_1(self):
        weight, label = DocumentGenerationProgress.SOAP_STEPS[-1]
        assert weight == 1.0

    def test_referral_steps_last_item_weight_is_1(self):
        weight, label = DocumentGenerationProgress.REFERRAL_STEPS[-1]
        assert weight == 1.0

    def test_diagnostic_steps_last_item_weight_is_1(self):
        weight, label = DocumentGenerationProgress.DIAGNOSTIC_STEPS[-1]
        assert weight == 1.0

    def test_soap_steps_labels_are_strings(self):
        for _, label in DocumentGenerationProgress.SOAP_STEPS:
            assert isinstance(label, str)

    def test_referral_steps_labels_are_strings(self):
        for _, label in DocumentGenerationProgress.REFERRAL_STEPS:
            assert isinstance(label, str)

    def test_diagnostic_steps_labels_are_strings(self):
        for _, label in DocumentGenerationProgress.DIAGNOSTIC_STEPS:
            assert isinstance(label, str)

    def test_soap_steps_weights_monotonically_non_decreasing(self):
        weights = [w for w, _ in DocumentGenerationProgress.SOAP_STEPS]
        assert weights == sorted(weights)

    def test_referral_steps_weights_monotonically_non_decreasing(self):
        weights = [w for w, _ in DocumentGenerationProgress.REFERRAL_STEPS]
        assert weights == sorted(weights)

    def test_diagnostic_steps_weights_monotonically_non_decreasing(self):
        weights = [w for w, _ in DocumentGenerationProgress.DIAGNOSTIC_STEPS]
        assert weights == sorted(weights)


# ---------------------------------------------------------------------------
# DocumentGenerationProgress factory method tests
# ---------------------------------------------------------------------------

class TestDocumentGenerationProgressFactories:
    """Tests for create_soap_tracker, create_referral_tracker, create_diagnostic_tracker."""

    def test_create_soap_tracker_returns_progress_tracker(self):
        cb = MagicMock()
        tracker = DocumentGenerationProgress.create_soap_tracker(cb)
        assert isinstance(tracker, ProgressTracker)

    def test_create_soap_tracker_total_steps_equals_soap_steps_len(self):
        cb = MagicMock()
        tracker = DocumentGenerationProgress.create_soap_tracker(cb)
        assert tracker.total_steps == len(DocumentGenerationProgress.SOAP_STEPS)

    def test_create_soap_tracker_total_steps_is_6(self):
        cb = MagicMock()
        tracker = DocumentGenerationProgress.create_soap_tracker(cb)
        assert tracker.total_steps == 6

    def test_create_soap_tracker_fires_initial_callback(self):
        cb = MagicMock()
        DocumentGenerationProgress.create_soap_tracker(cb)
        cb.assert_called_once()

    def test_create_soap_tracker_initial_message(self):
        cb = MagicMock()
        DocumentGenerationProgress.create_soap_tracker(cb)
        info = cb.call_args[0][0]
        assert "SOAP" in info.message or "Starting" in info.message

    def test_create_referral_tracker_returns_progress_tracker(self):
        cb = MagicMock()
        tracker = DocumentGenerationProgress.create_referral_tracker(cb)
        assert isinstance(tracker, ProgressTracker)

    def test_create_referral_tracker_total_steps_equals_referral_steps_len(self):
        cb = MagicMock()
        tracker = DocumentGenerationProgress.create_referral_tracker(cb)
        assert tracker.total_steps == len(DocumentGenerationProgress.REFERRAL_STEPS)

    def test_create_referral_tracker_total_steps_is_5(self):
        cb = MagicMock()
        tracker = DocumentGenerationProgress.create_referral_tracker(cb)
        assert tracker.total_steps == 5

    def test_create_referral_tracker_fires_initial_callback(self):
        cb = MagicMock()
        DocumentGenerationProgress.create_referral_tracker(cb)
        cb.assert_called_once()

    def test_create_referral_tracker_initial_message(self):
        cb = MagicMock()
        DocumentGenerationProgress.create_referral_tracker(cb)
        info = cb.call_args[0][0]
        assert "referral" in info.message.lower() or "Starting" in info.message

    def test_create_diagnostic_tracker_returns_progress_tracker(self):
        cb = MagicMock()
        tracker = DocumentGenerationProgress.create_diagnostic_tracker(cb)
        assert isinstance(tracker, ProgressTracker)

    def test_create_diagnostic_tracker_total_steps_equals_diagnostic_steps_len(self):
        cb = MagicMock()
        tracker = DocumentGenerationProgress.create_diagnostic_tracker(cb)
        assert tracker.total_steps == len(DocumentGenerationProgress.DIAGNOSTIC_STEPS)

    def test_create_diagnostic_tracker_total_steps_is_6(self):
        cb = MagicMock()
        tracker = DocumentGenerationProgress.create_diagnostic_tracker(cb)
        assert tracker.total_steps == 6

    def test_create_diagnostic_tracker_fires_initial_callback(self):
        cb = MagicMock()
        DocumentGenerationProgress.create_diagnostic_tracker(cb)
        cb.assert_called_once()

    def test_create_diagnostic_tracker_initial_message(self):
        cb = MagicMock()
        DocumentGenerationProgress.create_diagnostic_tracker(cb)
        info = cb.call_args[0][0]
        assert "diagnostic" in info.message.lower() or "Starting" in info.message

    def test_create_soap_tracker_usable_for_full_workflow(self):
        """Full workflow: create, update all steps, then complete."""
        received = []
        tracker = DocumentGenerationProgress.create_soap_tracker(received.append)
        for i, (_, msg) in enumerate(DocumentGenerationProgress.SOAP_STEPS[:-1]):
            tracker.update(message=msg)
        tracker.complete()
        assert received[-1].percentage == 100.0

    def test_create_referral_tracker_usable_for_full_workflow(self):
        received = []
        tracker = DocumentGenerationProgress.create_referral_tracker(received.append)
        for _ in range(5):
            tracker.update()
        assert received[-1].current == 5

    def test_create_diagnostic_tracker_usable_for_full_workflow(self):
        received = []
        tracker = DocumentGenerationProgress.create_diagnostic_tracker(received.append)
        tracker.complete()
        assert received[-1].current == received[-1].total
