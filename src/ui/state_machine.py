"""
UI State Machine Module

Provides a state machine implementation for managing UI state transitions,
particularly for complex workflows like recording.
"""

from enum import Enum, auto
from typing import Optional, Callable, Dict, List, Set, Any
from dataclasses import dataclass, field
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


@dataclass
class StateConfig:
    """Configuration for a state."""
    name: str
    on_enter: Optional[Callable[[], None]] = None
    on_exit: Optional[Callable[[], None]] = None
    allowed_transitions: Set[str] = field(default_factory=set)


class StateMachine:
    """Generic state machine for UI state management.

    This class provides a flexible state machine that can be used to manage
    UI state transitions with proper validation and callbacks.

    Usage:
        # Define states
        sm = StateMachine("idle")
        sm.add_state("idle", on_enter=show_idle_ui, transitions={"recording", "loading"})
        sm.add_state("recording", on_enter=show_recording_ui, transitions={"paused", "idle"})
        sm.add_state("paused", on_enter=show_paused_ui, transitions={"recording", "idle"})

        # Transition between states
        sm.transition_to("recording")  # Calls on_exit for idle, on_enter for recording
        sm.transition_to("paused")     # Valid transition
        sm.transition_to("loading")    # Raises StateTransitionError (not allowed from paused)
    """

    def __init__(
        self,
        initial_state: str,
        on_state_change: Optional[Callable[[str, str], None]] = None
    ):
        """Initialize the state machine.

        Args:
            initial_state: The starting state name
            on_state_change: Optional callback(old_state, new_state) on any transition
        """
        self._states: Dict[str, StateConfig] = {}
        self._current_state: str = initial_state
        self._on_state_change = on_state_change
        self._transition_history: List[str] = [initial_state]
        self._max_history = 50

        # Add the initial state automatically
        self.add_state(initial_state)

    @property
    def current_state(self) -> str:
        """Get the current state name."""
        return self._current_state

    @property
    def history(self) -> List[str]:
        """Get the state transition history."""
        return self._transition_history.copy()

    @property
    def previous_state(self) -> Optional[str]:
        """Get the previous state, if any."""
        if len(self._transition_history) > 1:
            return self._transition_history[-2]
        return None

    def add_state(
        self,
        name: str,
        on_enter: Optional[Callable[[], None]] = None,
        on_exit: Optional[Callable[[], None]] = None,
        transitions: Optional[Set[str]] = None
    ) -> 'StateMachine':
        """Add a state to the state machine.

        Args:
            name: State name
            on_enter: Callback when entering this state
            on_exit: Callback when exiting this state
            transitions: Set of allowed target state names

        Returns:
            Self for method chaining
        """
        self._states[name] = StateConfig(
            name=name,
            on_enter=on_enter,
            on_exit=on_exit,
            allowed_transitions=transitions or set()
        )
        return self

    def allow_transition(self, from_state: str, to_state: str) -> 'StateMachine':
        """Allow a transition between two states.

        Args:
            from_state: Source state name
            to_state: Target state name

        Returns:
            Self for method chaining
        """
        if from_state in self._states:
            self._states[from_state].allowed_transitions.add(to_state)
        return self

    def can_transition_to(self, target_state: str) -> bool:
        """Check if a transition to the target state is allowed.

        Args:
            target_state: The state to check

        Returns:
            True if transition is allowed
        """
        if self._current_state not in self._states:
            return True  # No restrictions if current state not configured

        current_config = self._states[self._current_state]
        if not current_config.allowed_transitions:
            return True  # No restrictions if no transitions defined

        return target_state in current_config.allowed_transitions

    def transition_to(self, target_state: str, force: bool = False) -> bool:
        """Transition to a new state.

        Args:
            target_state: The state to transition to
            force: If True, skip validation and force the transition

        Returns:
            True if transition was successful

        Raises:
            StateTransitionError: If transition is not allowed and force=False
        """
        if target_state == self._current_state:
            logging.debug(f"Already in state: {target_state}")
            return True

        # Validate transition
        if not force and not self.can_transition_to(target_state):
            raise StateTransitionError(
                f"Cannot transition from '{self._current_state}' to '{target_state}'"
            )

        old_state = self._current_state

        # Execute on_exit callback for current state
        if self._current_state in self._states:
            current_config = self._states[self._current_state]
            if current_config.on_exit:
                try:
                    current_config.on_exit()
                except Exception as e:
                    logging.error(f"Error in on_exit for state '{self._current_state}': {e}")

        # Update state
        self._current_state = target_state

        # Add to history
        self._transition_history.append(target_state)
        if len(self._transition_history) > self._max_history:
            self._transition_history = self._transition_history[-self._max_history:]

        # Execute on_enter callback for new state
        if target_state in self._states:
            new_config = self._states[target_state]
            if new_config.on_enter:
                try:
                    new_config.on_enter()
                except Exception as e:
                    logging.error(f"Error in on_enter for state '{target_state}': {e}")

        # Execute global state change callback
        if self._on_state_change:
            try:
                self._on_state_change(old_state, target_state)
            except Exception as e:
                logging.error(f"Error in on_state_change callback: {e}")

        logging.debug(f"State transition: {old_state} -> {target_state}")
        return True

    def reset(self, initial_state: Optional[str] = None) -> None:
        """Reset the state machine to initial state.

        Args:
            initial_state: Optional new initial state (uses first state if not provided)
        """
        if initial_state:
            self._current_state = initial_state
        elif self._transition_history:
            self._current_state = self._transition_history[0]

        self._transition_history = [self._current_state]

    def is_in_state(self, state: str) -> bool:
        """Check if currently in a specific state.

        Args:
            state: State name to check

        Returns:
            True if in the specified state
        """
        return self._current_state == state

    def is_in_any_state(self, *states: str) -> bool:
        """Check if currently in any of the specified states.

        Args:
            *states: State names to check

        Returns:
            True if in any of the specified states
        """
        return self._current_state in states


# =============================================================================
# Recording State Machine
# =============================================================================

class RecordingState(Enum):
    """Recording workflow states."""
    IDLE = auto()
    RECORDING = auto()
    PAUSED = auto()
    PROCESSING = auto()
    COMPLETED = auto()
    ERROR = auto()


class RecordingStateMachine(StateMachine):
    """Specialized state machine for recording workflow.

    This provides a pre-configured state machine for the recording workflow
    with proper state transitions and UI callbacks.
    """

    def __init__(
        self,
        on_idle: Optional[Callable[[], None]] = None,
        on_recording: Optional[Callable[[], None]] = None,
        on_paused: Optional[Callable[[], None]] = None,
        on_processing: Optional[Callable[[], None]] = None,
        on_completed: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[], None]] = None,
        on_state_change: Optional[Callable[[str, str], None]] = None
    ):
        """Initialize the recording state machine.

        Args:
            on_idle: Callback when entering idle state
            on_recording: Callback when entering recording state
            on_paused: Callback when entering paused state
            on_processing: Callback when entering processing state
            on_completed: Callback when entering completed state
            on_error: Callback when entering error state
            on_state_change: Callback for any state change
        """
        super().__init__("idle", on_state_change)

        # Configure states with transitions
        self.add_state(
            "idle",
            on_enter=on_idle,
            transitions={"recording", "error"}
        )
        self.add_state(
            "recording",
            on_enter=on_recording,
            transitions={"paused", "processing", "idle", "error"}
        )
        self.add_state(
            "paused",
            on_enter=on_paused,
            transitions={"recording", "processing", "idle", "error"}
        )
        self.add_state(
            "processing",
            on_enter=on_processing,
            transitions={"completed", "error", "idle"}
        )
        self.add_state(
            "completed",
            on_enter=on_completed,
            transitions={"idle", "recording"}
        )
        self.add_state(
            "error",
            on_enter=on_error,
            transitions={"idle", "recording"}
        )

    def start_recording(self) -> bool:
        """Start recording."""
        return self.transition_to("recording")

    def pause_recording(self) -> bool:
        """Pause recording."""
        return self.transition_to("paused")

    def resume_recording(self) -> bool:
        """Resume recording from paused state."""
        return self.transition_to("recording")

    def stop_recording(self) -> bool:
        """Stop recording and start processing."""
        return self.transition_to("processing")

    def cancel_recording(self) -> bool:
        """Cancel recording and return to idle."""
        return self.transition_to("idle", force=True)

    def complete_processing(self) -> bool:
        """Mark processing as complete."""
        return self.transition_to("completed")

    def set_error(self) -> bool:
        """Set error state."""
        return self.transition_to("error", force=True)

    def reset_to_idle(self) -> bool:
        """Reset to idle state."""
        return self.transition_to("idle", force=True)

    @property
    def is_idle(self) -> bool:
        """Check if in idle state."""
        return self.is_in_state("idle")

    @property
    def is_recording(self) -> bool:
        """Check if in recording state."""
        return self.is_in_state("recording")

    @property
    def is_paused(self) -> bool:
        """Check if in paused state."""
        return self.is_in_state("paused")

    @property
    def is_processing(self) -> bool:
        """Check if in processing state."""
        return self.is_in_state("processing")

    @property
    def is_completed(self) -> bool:
        """Check if in completed state."""
        return self.is_in_state("completed")

    @property
    def is_active(self) -> bool:
        """Check if recording is active (recording or paused)."""
        return self.is_in_any_state("recording", "paused")


# =============================================================================
# Processing State Machine
# =============================================================================

class ProcessingStateMachine(StateMachine):
    """State machine for document processing workflow."""

    def __init__(
        self,
        on_idle: Optional[Callable[[], None]] = None,
        on_processing: Optional[Callable[[], None]] = None,
        on_completed: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[], None]] = None,
        on_state_change: Optional[Callable[[str, str], None]] = None
    ):
        """Initialize the processing state machine."""
        super().__init__("idle", on_state_change)

        self.add_state(
            "idle",
            on_enter=on_idle,
            transitions={"processing", "error"}
        )
        self.add_state(
            "processing",
            on_enter=on_processing,
            transitions={"completed", "error", "idle"}
        )
        self.add_state(
            "completed",
            on_enter=on_completed,
            transitions={"idle", "processing"}
        )
        self.add_state(
            "error",
            on_enter=on_error,
            transitions={"idle", "processing"}
        )

    def start_processing(self) -> bool:
        """Start processing."""
        return self.transition_to("processing")

    def complete(self) -> bool:
        """Mark processing as complete."""
        return self.transition_to("completed")

    def fail(self) -> bool:
        """Mark processing as failed."""
        return self.transition_to("error")

    def reset(self, initial_state: Optional[str] = None) -> None:
        """Reset to idle state."""
        super().reset("idle")
