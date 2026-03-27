"""
Service Registry for Medical Assistant.

Typed service container that replaces passing `app: Any` to components.
Components receive the registry (or specific protocols) instead of the
entire application, narrowing their dependency surface.

Migration path:
    1. ServiceRegistry.from_app(app) bridges existing code
    2. New/migrated components accept registry or specific protocols
    3. Old code continues working — from_app() wraps the existing app

Usage:
    # In AppInitializer, after all managers are created:
    app.service_registry = ServiceRegistry.from_app(app)

    # In a migrated controller:
    class MyController:
        def __init__(self, *, registry: ServiceRegistry):
            self._status = registry.status_manager
            self._db = registry.database
"""

from typing import Any, Callable, List, Optional, TYPE_CHECKING

from core.interfaces import (
    AudioHandlerProtocol,
    AutoSaveManagerProtocol,
    DatabaseProtocol,
    DocumentTargetProtocol,
    NotificationManagerProtocol,
    ProcessingQueueProtocol,
    RecordingManagerProtocol,
    StatusManagerProtocol,
    UIStateManagerProtocol,
)

if TYPE_CHECKING:
    from core.app import MedicalDictationApp


class ServiceRegistry:
    """Typed service container replacing app: Any passing.

    Holds references to service implementations keyed by their protocol
    type. Provides typed property accessors so consumers get the correct
    protocol type without casting.

    The ``from_app()`` classmethod populates the registry from a live
    app instance — this is the migration bridge so no existing code
    needs to change until it is ready.
    """

    def __init__(self) -> None:
        # Service slots — populated via from_app() or direct assignment
        self._status_manager: Optional[StatusManagerProtocol] = None
        self._recording_manager: Optional[RecordingManagerProtocol] = None
        self._audio_handler: Optional[AudioHandlerProtocol] = None
        self._ui_state_manager: Optional[UIStateManagerProtocol] = None
        self._database: Optional[DatabaseProtocol] = None
        self._autosave_manager: Optional[AutoSaveManagerProtocol] = None
        self._processing_queue: Optional[ProcessingQueueProtocol] = None
        self._notification_manager: Optional[NotificationManagerProtocol] = None

        # UI widget references (not protocol-typed — Tkinter widgets)
        self._soap_text: Any = None
        self._letter_text: Any = None
        self._notebook: Any = None

        # Tk scheduling delegate
        self._after_fn: Optional[Callable] = None

    # ------------------------------------------------------------------
    # Typed accessors for protocol-backed services
    # ------------------------------------------------------------------

    @property
    def status_manager(self) -> StatusManagerProtocol:
        assert self._status_manager is not None, "status_manager not registered"
        return self._status_manager

    @property
    def recording_manager(self) -> RecordingManagerProtocol:
        assert self._recording_manager is not None, "recording_manager not registered"
        return self._recording_manager

    @property
    def audio_handler(self) -> AudioHandlerProtocol:
        assert self._audio_handler is not None, "audio_handler not registered"
        return self._audio_handler

    @property
    def ui_state_manager(self) -> UIStateManagerProtocol:
        assert self._ui_state_manager is not None, "ui_state_manager not registered"
        return self._ui_state_manager

    @property
    def database(self) -> DatabaseProtocol:
        assert self._database is not None, "database not registered"
        return self._database

    @property
    def autosave_manager(self) -> AutoSaveManagerProtocol:
        assert self._autosave_manager is not None, "autosave_manager not registered"
        return self._autosave_manager

    @property
    def processing_queue(self) -> ProcessingQueueProtocol:
        assert self._processing_queue is not None, "processing_queue not registered"
        return self._processing_queue

    @property
    def notification_manager(self) -> NotificationManagerProtocol:
        assert self._notification_manager is not None, "notification_manager not registered"
        return self._notification_manager

    # ------------------------------------------------------------------
    # UI widget accessors (satisfies DocumentTargetProtocol)
    # ------------------------------------------------------------------

    @property
    def soap_text(self) -> Any:
        return self._soap_text

    @property
    def letter_text(self) -> Any:
        return self._letter_text

    @property
    def notebook(self) -> Any:
        return self._notebook

    def after(self, ms: int, func: Callable, *args: Any) -> Any:
        """Schedule a callback on the Tk main loop."""
        assert self._after_fn is not None, "after() delegate not registered"
        return self._after_fn(ms, func, *args)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_app(cls, app: 'MedicalDictationApp') -> 'ServiceRegistry':
        """Populate registry from an existing app instance.

        This is the migration bridge: existing code keeps passing ``app``
        everywhere, and the registry wraps it. New/migrated code receives
        the registry instead.
        """
        registry = cls()

        # Protocol-backed services
        registry._status_manager = getattr(app, 'status_manager', None)
        registry._recording_manager = getattr(app, 'recording_manager', None)
        registry._audio_handler = getattr(app, 'audio_handler', None)
        registry._ui_state_manager = getattr(app, 'ui_state_manager', None)
        registry._database = getattr(app, 'db', None)
        registry._autosave_manager = getattr(app, 'autosave_manager', None)
        registry._processing_queue = getattr(app, 'processing_queue', None)
        registry._notification_manager = getattr(app, 'notification_manager', None)

        # UI widgets
        registry._soap_text = getattr(app, 'soap_text', None)
        registry._letter_text = getattr(app, 'letter_text', None)
        registry._notebook = getattr(app, 'notebook', None)

        # Tk scheduling
        if hasattr(app, 'after'):
            registry._after_fn = app.after

        return registry

    # ------------------------------------------------------------------
    # Validation (development mode)
    # ------------------------------------------------------------------

    def validate(self) -> List[str]:
        """Check that all registered services satisfy their protocols.

        Returns a list of error messages. Empty list means all valid.
        Only meaningful when called after from_app() or manual registration.
        """
        errors: List[str] = []

        checks = [
            ('status_manager', self._status_manager, StatusManagerProtocol),
            ('recording_manager', self._recording_manager, RecordingManagerProtocol),
            ('audio_handler', self._audio_handler, AudioHandlerProtocol),
            ('ui_state_manager', self._ui_state_manager, UIStateManagerProtocol),
            ('database', self._database, DatabaseProtocol),
            ('notification_manager', self._notification_manager, NotificationManagerProtocol),
        ]

        for name, instance, protocol in checks:
            if instance is None:
                errors.append(f"{name}: not registered (None)")
            elif not isinstance(instance, protocol):
                errors.append(  # type: ignore[unreachable]
                    f"{name}: {type(instance).__name__} does not satisfy "
                    f"{protocol.__name__}"
                )

        return errors
