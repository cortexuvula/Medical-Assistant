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

from typing import Protocol, Optional, Callable, Dict, Any, List, TYPE_CHECKING, runtime_checkable
from datetime import datetime

if TYPE_CHECKING:
    from core.app import MedicalDictationApp


@runtime_checkable
class StatusManagerProtocol(Protocol):
    """Protocol for status manager interface."""

    def info(self, message: str) -> None:
        """Display an info message."""
        ...

    def error(self, message: str, exception: Optional[Exception] = None,
              context: Optional[str] = None) -> None:
        """Display an error message."""
        ...

    def success(self, message: str) -> None:
        """Display a success message."""
        ...

    def warning(self, message: str) -> None:
        """Display a warning message."""
        ...


@runtime_checkable
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

    def pause_recording(self) -> bool:
        """Pause the current recording."""
        ...

    def resume_recording(self) -> bool:
        """Resume a paused recording."""
        ...

    def cancel_recording(self) -> None:
        """Cancel the current recording without saving."""
        ...


@runtime_checkable
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


@runtime_checkable
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


@runtime_checkable
class DatabaseProtocol(Protocol):
    """Protocol for database interface."""

    def add_recording(
        self,
        filename: str,
        transcript: Optional[str] = None,
        soap_note: Optional[str] = None,
        referral: Optional[str] = None,
        letter: Optional[str] = None,
        **kwargs: Any
    ) -> int:
        """Add a new recording to the database."""
        ...

    def update_recording(self, recording_id: int, **kwargs: Any) -> bool:
        """Update a recording in the database."""
        ...

    def get_recording(self, recording_id: int) -> Optional[Dict[str, Any]]:
        """Get a recording by ID."""
        ...


@runtime_checkable
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


@runtime_checkable
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


@runtime_checkable
class NotificationManagerProtocol(Protocol):
    """Protocol for notification manager interface."""

    def show_completion(
        self,
        patient_name: str,
        recording_id: int,
        task_id: str,
        processing_time: float
    ) -> None:
        """Show a completion notification."""
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


@runtime_checkable
class DocumentTargetProtocol(Protocol):
    """What result dialogs need to add content to documents.

    This narrows the interface from 'entire app' to just the widgets
    and methods dialogs actually use when adding results to documents.
    """

    soap_text: Any  # tk.Text widget
    letter_text: Any  # tk.Text widget
    notebook: Any  # ttk.Notebook widget


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
        document_target: Optional[DocumentTargetProtocol] = None,
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
        self.document_target = document_target
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
            document_target=app,  # App satisfies DocumentTargetProtocol
            ui_updater=lambda recording, caller: app._update_recording_ui_state(recording, caller),  # type: ignore[arg-type]
            sound_player=lambda start: app.play_recording_sound(start=start),
        )
