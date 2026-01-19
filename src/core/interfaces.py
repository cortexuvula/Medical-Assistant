"""
Interface definitions for Medical Assistant controllers.

This module defines Protocol classes that specify the interfaces controllers
expect from their dependencies. Using these protocols enables:
- Better testability through dependency injection
- Clearer contracts between components
- Reduced tight coupling

Controllers can gradually migrate from direct app reference to using
these interfaces as their dependencies are extracted.
"""

from typing import Protocol, Optional, Callable, Dict, Any, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from core.app import MedicalDictationApp


class StatusManagerProtocol(Protocol):
    """Protocol for status manager interface."""

    def info(self, message: str) -> None:
        """Display an info message."""
        ...

    def error(self, message: str) -> None:
        """Display an error message."""
        ...

    def success(self, message: str) -> None:
        """Display a success message."""
        ...

    def warning(self, message: str) -> None:
        """Display a warning message."""
        ...


class RecordingManagerProtocol(Protocol):
    """Protocol for recording manager interface."""

    @property
    def is_recording(self) -> bool:
        """Check if recording is active."""
        ...

    @property
    def is_paused(self) -> bool:
        """Check if recording is paused."""
        ...

    def start_recording(self, callback: Callable) -> bool:
        """Start a new recording session."""
        ...

    def stop_recording(self) -> Optional[Dict[str, Any]]:
        """Stop the current recording and return data."""
        ...

    def pause_recording(self) -> None:
        """Pause the current recording."""
        ...

    def resume_recording(self) -> None:
        """Resume a paused recording."""
        ...

    def cancel_recording(self) -> None:
        """Cancel the current recording without saving."""
        ...


class AudioHandlerProtocol(Protocol):
    """Protocol for audio handler interface."""

    soap_mode: bool
    silence_threshold: float

    def listen_in_background(
        self,
        mic_name: str,
        callback: Callable,
        phrase_time_limit: Optional[int] = None,
        stream_purpose: str = "default"
    ) -> Callable:
        """Start background listening and return stop function."""
        ...

    def transcribe_audio(self, audio_data: Any) -> str:
        """Transcribe audio data to text."""
        ...

    def cleanup_resources(self) -> None:
        """Clean up audio resources."""
        ...


class UIStateManagerProtocol(Protocol):
    """Protocol for UI state manager interface."""

    def set_recording_state(
        self,
        recording: bool,
        paused: bool = False,
        caller: str = ""
    ) -> None:
        """Update UI to reflect recording state."""
        ...


class DatabaseProtocol(Protocol):
    """Protocol for database interface."""

    def add_recording(
        self,
        filename: str,
        processing_status: str = 'pending',
        patient_name: str = 'Patient'
    ) -> int:
        """Add a new recording to the database."""
        ...

    def update_recording(self, recording_id: int, **kwargs) -> None:
        """Update a recording in the database."""
        ...

    def get_recording(self, recording_id: int) -> Optional[Dict[str, Any]]:
        """Get a recording by ID."""
        ...


class AutoSaveManagerProtocol(Protocol):
    """Protocol for auto-save manager interface."""

    def save(self, data: Dict[str, Any]) -> bool:
        """Save data to auto-save storage."""
        ...

    def load(self) -> Optional[Dict[str, Any]]:
        """Load data from auto-save storage."""
        ...

    def clear(self) -> None:
        """Clear auto-save data."""
        ...

    def exists(self) -> bool:
        """Check if auto-save data exists."""
        ...


class ProcessingQueueProtocol(Protocol):
    """Protocol for processing queue interface."""

    def add_recording(self, recording_data: Dict[str, Any]) -> Optional[str]:
        """Add a recording to the processing queue."""
        ...

    def get_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        ...

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a queued task."""
        ...


class NotificationManagerProtocol(Protocol):
    """Protocol for notification manager interface."""

    def show_info(self, title: str, message: str) -> None:
        """Show an info notification."""
        ...

    def show_success(
        self,
        patient_name: str,
        recording_id: int,
        task_id: str,
        processing_time: float
    ) -> None:
        """Show a success notification."""
        ...

    def show_error(
        self,
        patient_name: str,
        error_message: str,
        recording_id: int,
        task_id: str
    ) -> None:
        """Show an error notification."""
        ...


# Type aliases for cleaner dependency declarations
UIUpdater = Callable[[bool, str], None]
SoundPlayer = Callable[[bool], None]


class ControllerDependencies:
    """Container for controller dependencies.

    This class provides a way to bundle dependencies for controllers,
    making it easier to inject them and test controllers in isolation.

    Example usage:
        deps = ControllerDependencies(
            status_manager=app.status_manager,
            recording_manager=app.recording_manager,
            audio_handler=app.audio_handler,
            ui_state_manager=app.ui_state_manager
        )
        controller = RecordingController(deps)
    """

    def __init__(
        self,
        status_manager: Optional[StatusManagerProtocol] = None,
        recording_manager: Optional[RecordingManagerProtocol] = None,
        audio_handler: Optional[AudioHandlerProtocol] = None,
        ui_state_manager: Optional[UIStateManagerProtocol] = None,
        database: Optional[DatabaseProtocol] = None,
        autosave_manager: Optional[AutoSaveManagerProtocol] = None,
        processing_queue: Optional[ProcessingQueueProtocol] = None,
        notification_manager: Optional[NotificationManagerProtocol] = None,
        ui_updater: Optional[UIUpdater] = None,
        sound_player: Optional[SoundPlayer] = None,
    ):
        self.status_manager = status_manager
        self.recording_manager = recording_manager
        self.audio_handler = audio_handler
        self.ui_state_manager = ui_state_manager
        self.database = database
        self.autosave_manager = autosave_manager
        self.processing_queue = processing_queue
        self.notification_manager = notification_manager
        self.ui_updater = ui_updater
        self.sound_player = sound_player

    @classmethod
    def from_app(cls, app: 'MedicalDictationApp') -> 'ControllerDependencies':
        """Create dependencies from app instance.

        This is a convenience method for transitioning existing code.
        New code should inject dependencies explicitly.

        Args:
            app: The main application instance

        Returns:
            ControllerDependencies with app's components
        """
        return cls(
            status_manager=getattr(app, 'status_manager', None),
            recording_manager=getattr(app, 'recording_manager', None),
            audio_handler=getattr(app, 'audio_handler', None),
            ui_state_manager=getattr(app, 'ui_state_manager', None),
            database=getattr(app, 'db', None),
            autosave_manager=getattr(app, 'autosave_manager', None),
            processing_queue=getattr(app, 'processing_queue', None),
            notification_manager=getattr(app, 'notification_manager', None),
            ui_updater=lambda recording, caller: app._update_recording_ui_state(recording, caller),
            sound_player=lambda start: app.play_recording_sound(start=start),
        )
