"""
Controllers package for Medical Assistant.

This package contains consolidated domain-focused controllers that manage
application functionality. Controllers are organized by domain:

- ConfigController: Provider configuration and microphone management
- WindowController: Navigation, window state, and log viewing
- PersistenceController: Autosave and keyboard shortcuts
- ProcessingController: Queue, text, and document export
- RecordingController: Recording, periodic analysis, and recovery
"""

from core.controllers.config_controller import ConfigController
from core.controllers.window_controller import WindowController
from core.controllers.persistence_controller import PersistenceController
from core.controllers.processing_controller import ProcessingController
from core.controllers.recording_controller import RecordingController

__all__ = [
    "ConfigController",
    "WindowController",
    "PersistenceController",
    "ProcessingController",
    "RecordingController",
]
