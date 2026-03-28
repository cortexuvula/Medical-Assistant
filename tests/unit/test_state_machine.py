"""Tests for ui.state_machine — FSM implementation with recording and processing variants."""

import pytest
from unittest.mock import Mock, patch, call

from ui.state_machine import (
    StateMachine,
    StateTransitionError,
    RecordingStateMachine,
    ProcessingStateMachine,
)


class TestStateMachineInit:
    def test_initial_state_is_set(self):
        sm = StateMachine("idle")
        assert sm.current_state == "idle"

    def test_history_starts_with_initial_state(self):
        sm = StateMachine("start")
        assert sm.history == ["start"]

    def test_previous_state_is_none_at_start(self):
        sm = StateMachine("idle")
        assert sm.previous_state is None

    def test_initial_state_auto_added(self):
        sm = StateMachine("idle")
        assert sm.can_transition_to("anything")


class TestStateMachineAddState:
    def test_add_state_returns_self_for_chaining(self):
        sm = StateMachine("idle")
        result = sm.add_state("recording")
        assert result is sm

    def test_chained_add_states(self):
        sm = StateMachine("idle")
        sm.add_state("a").add_state("b").add_state("c")
        # Should be able to transition since no restrictions on 'idle' by default
        assert sm.can_transition_to("a")


class TestStateMachineTransitions:
    def test_valid_transition_succeeds(self):
        sm = StateMachine("idle")
        sm.add_state("idle", transitions={"recording"})
        sm.add_state("recording")
        assert sm.transition_to("recording") is True
        assert sm.current_state == "recording"

    def test_invalid_transition_raises_error(self):
        sm = StateMachine("idle")
        sm.add_state("idle", transitions={"recording"})
        sm.add_state("processing")
        with pytest.raises(StateTransitionError):
            sm.transition_to("processing")

    def test_same_state_transition_returns_true(self):
        sm = StateMachine("idle")
        assert sm.transition_to("idle") is True

    def test_same_state_transition_does_not_call_callbacks(self):
        on_enter = Mock()
        on_exit = Mock()
        sm = StateMachine("idle")
        sm.add_state("idle", on_enter=on_enter, on_exit=on_exit)
        sm.transition_to("idle")
        on_enter.assert_not_called()
        on_exit.assert_not_called()

    def test_force_transition_bypasses_validation(self):
        sm = StateMachine("idle")
        sm.add_state("idle", transitions={"recording"})
        sm.add_state("error")
        assert sm.transition_to("error", force=True) is True
        assert sm.current_state == "error"

    def test_no_restrictions_allows_any_transition(self):
        sm = StateMachine("idle")
        sm.add_state("idle")  # No transitions specified
        sm.add_state("anywhere")
        assert sm.can_transition_to("anywhere") is True

    def test_can_transition_to_with_restrictions(self):
        sm = StateMachine("idle")
        sm.add_state("idle", transitions={"recording"})
        assert sm.can_transition_to("recording") is True
        assert sm.can_transition_to("processing") is False


class TestStateMachineCallbacks:
    def test_on_exit_called_on_transition(self):
        on_exit = Mock()
        sm = StateMachine("idle")
        sm.add_state("idle", on_exit=on_exit)
        sm.add_state("recording")
        sm.transition_to("recording")
        on_exit.assert_called_once()

    def test_on_enter_called_on_transition(self):
        on_enter = Mock()
        sm = StateMachine("idle")
        sm.add_state("idle")
        sm.add_state("recording", on_enter=on_enter)
        sm.transition_to("recording")
        on_enter.assert_called_once()

    def test_on_state_change_called_with_old_and_new(self):
        change_cb = Mock()
        sm = StateMachine("idle", on_state_change=change_cb)
        sm.add_state("recording")
        sm.transition_to("recording")
        change_cb.assert_called_once_with("idle", "recording")

    @patch("ui.state_machine.logger")
    def test_on_exit_exception_is_caught(self, mock_logger):
        on_exit = Mock(side_effect=RuntimeError("exit boom"))
        sm = StateMachine("idle")
        sm.add_state("idle", on_exit=on_exit)
        sm.add_state("recording")
        # Should not raise, exception is caught
        assert sm.transition_to("recording") is True
        assert sm.current_state == "recording"

    @patch("ui.state_machine.logger")
    def test_on_enter_exception_is_caught(self, mock_logger):
        on_enter = Mock(side_effect=RuntimeError("enter boom"))
        sm = StateMachine("idle")
        sm.add_state("recording", on_enter=on_enter)
        assert sm.transition_to("recording") is True
        assert sm.current_state == "recording"

    @patch("ui.state_machine.logger")
    def test_on_state_change_exception_is_caught(self, mock_logger):
        change_cb = Mock(side_effect=ValueError("change boom"))
        sm = StateMachine("idle", on_state_change=change_cb)
        sm.add_state("recording")
        assert sm.transition_to("recording") is True


class TestStateMachineHistory:
    def test_history_tracks_transitions(self):
        sm = StateMachine("idle")
        sm.add_state("a")
        sm.add_state("b")
        sm.transition_to("a")
        sm.transition_to("b")
        assert sm.history == ["idle", "a", "b"]

    def test_previous_state_after_transition(self):
        sm = StateMachine("idle")
        sm.add_state("recording")
        sm.transition_to("recording")
        assert sm.previous_state == "idle"

    def test_history_is_a_copy(self):
        sm = StateMachine("idle")
        history = sm.history
        history.append("tampered")
        assert sm.history == ["idle"]

    def test_history_trimmed_at_max_50(self):
        sm = StateMachine("s0")
        for i in range(1, 60):
            sm.add_state(f"s{i}")
            sm.transition_to(f"s{i}")
        assert len(sm.history) <= 50


class TestStateMachineAllowTransition:
    def test_allow_transition_adds_target(self):
        sm = StateMachine("idle")
        sm.add_state("idle", transitions=set())
        sm.allow_transition("idle", "recording")
        assert sm.can_transition_to("recording") is True

    def test_allow_transition_returns_self(self):
        sm = StateMachine("idle")
        result = sm.allow_transition("idle", "recording")
        assert result is sm


class TestStateMachineReset:
    def test_reset_returns_to_initial_state(self):
        sm = StateMachine("idle")
        sm.add_state("recording")
        sm.transition_to("recording")
        sm.reset()
        assert sm.current_state == "idle"
        assert sm.history == ["idle"]

    def test_reset_with_new_initial_state(self):
        sm = StateMachine("idle")
        sm.add_state("error")
        sm.reset(initial_state="error")
        assert sm.current_state == "error"


class TestStateMachineStateChecks:
    def test_is_in_state_true(self):
        sm = StateMachine("idle")
        assert sm.is_in_state("idle") is True

    def test_is_in_state_false(self):
        sm = StateMachine("idle")
        assert sm.is_in_state("recording") is False

    def test_is_in_any_state_true(self):
        sm = StateMachine("idle")
        assert sm.is_in_any_state("idle", "recording") is True

    def test_is_in_any_state_false(self):
        sm = StateMachine("idle")
        assert sm.is_in_any_state("recording", "processing") is False


class TestRecordingStateMachine:
    def test_starts_in_idle(self):
        rsm = RecordingStateMachine()
        assert rsm.current_state == "idle"
        assert rsm.is_idle is True

    def test_start_recording(self):
        rsm = RecordingStateMachine()
        assert rsm.start_recording() is True
        assert rsm.is_recording is True

    def test_pause_recording(self):
        rsm = RecordingStateMachine()
        rsm.start_recording()
        assert rsm.pause_recording() is True
        assert rsm.is_paused is True

    def test_resume_recording(self):
        rsm = RecordingStateMachine()
        rsm.start_recording()
        rsm.pause_recording()
        assert rsm.resume_recording() is True
        assert rsm.is_recording is True

    def test_stop_recording(self):
        rsm = RecordingStateMachine()
        rsm.start_recording()
        assert rsm.stop_recording() is True
        assert rsm.is_processing is True

    def test_complete_processing(self):
        rsm = RecordingStateMachine()
        rsm.start_recording()
        rsm.stop_recording()
        assert rsm.complete_processing() is True
        assert rsm.is_completed is True

    def test_set_error_force_from_any_state(self):
        rsm = RecordingStateMachine()
        rsm.start_recording()
        assert rsm.set_error() is True
        assert rsm.current_state == "error"

    def test_cancel_recording_force_to_idle(self):
        rsm = RecordingStateMachine()
        rsm.start_recording()
        rsm.pause_recording()
        assert rsm.cancel_recording() is True
        assert rsm.is_idle is True

    def test_reset_to_idle(self):
        rsm = RecordingStateMachine()
        rsm.start_recording()
        rsm.stop_recording()
        assert rsm.reset_to_idle() is True
        assert rsm.is_idle is True

    def test_is_active_when_recording(self):
        rsm = RecordingStateMachine()
        rsm.start_recording()
        assert rsm.is_active is True

    def test_is_active_when_paused(self):
        rsm = RecordingStateMachine()
        rsm.start_recording()
        rsm.pause_recording()
        assert rsm.is_active is True

    def test_is_not_active_when_idle(self):
        rsm = RecordingStateMachine()
        assert rsm.is_active is False

    def test_invalid_transition_from_idle_to_paused(self):
        rsm = RecordingStateMachine()
        with pytest.raises(StateTransitionError):
            rsm.pause_recording()

    def test_callbacks_invoked(self):
        on_idle = Mock()
        on_recording = Mock()
        rsm = RecordingStateMachine(on_idle=on_idle, on_recording=on_recording)
        rsm.start_recording()
        on_recording.assert_called_once()

    def test_state_change_callback(self):
        change_cb = Mock()
        rsm = RecordingStateMachine(on_state_change=change_cb)
        rsm.start_recording()
        change_cb.assert_called_with("idle", "recording")


class TestProcessingStateMachine:
    def test_starts_in_idle(self):
        psm = ProcessingStateMachine()
        assert psm.current_state == "idle"

    def test_start_processing(self):
        psm = ProcessingStateMachine()
        assert psm.start_processing() is True
        assert psm.current_state == "processing"

    def test_complete(self):
        psm = ProcessingStateMachine()
        psm.start_processing()
        assert psm.complete() is True
        assert psm.current_state == "completed"

    def test_fail(self):
        psm = ProcessingStateMachine()
        psm.start_processing()
        assert psm.fail() is True
        assert psm.current_state == "error"

    def test_reset_returns_to_idle(self):
        psm = ProcessingStateMachine()
        psm.start_processing()
        psm.complete()
        psm.reset()
        assert psm.current_state == "idle"

    def test_callbacks_invoked(self):
        on_processing = Mock()
        on_completed = Mock()
        psm = ProcessingStateMachine(on_processing=on_processing, on_completed=on_completed)
        psm.start_processing()
        on_processing.assert_called_once()
        psm.complete()
        on_completed.assert_called_once()
