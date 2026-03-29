"""
Tests for src/core/interfaces.py

Covers all Protocol classes and ControllerDependencies.
"""

import sys
import pytest
from typing import Protocol, Optional, Dict, Any, Callable
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from core.interfaces import (
    StatusManagerProtocol,
    RecordingManagerProtocol,
    AudioHandlerProtocol,
    UIStateManagerProtocol,
    DatabaseProtocol,
    AutoSaveManagerProtocol,
    ProcessingQueueProtocol,
    NotificationManagerProtocol,
    DocumentTargetProtocol,
    ControllerDependencies,
)


# ---------------------------------------------------------------------------
# Minimal concrete implementations for isinstance tests
# ---------------------------------------------------------------------------

class _ConcreteStatus:
    def info(self, message: str) -> None:
        pass

    def error(self, message: str, exception=None, context=None) -> None:
        pass

    def success(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        pass


class _ConcreteRecordingManager:
    @property
    def is_recording(self) -> bool:
        return False

    @property
    def is_paused(self) -> bool:
        return False

    def start_recording(self, callback) -> bool:
        return True

    def stop_recording(self):
        return None

    def pause_recording(self) -> bool:
        return True

    def resume_recording(self) -> bool:
        return True

    def cancel_recording(self) -> None:
        pass


class _ConcreteAudioHandler:
    soap_mode: bool = False
    silence_threshold: float = 0.03

    def listen_in_background(self, mic_name, callback, phrase_time_limit=None, stream_purpose="default"):
        return lambda: None

    def transcribe_audio(self, audio_data) -> str:
        return ""

    def cleanup_resources(self) -> None:
        pass


class _ConcreteUIStateManager:
    def set_recording_state(self, recording: bool, paused: bool = False, caller: str = "") -> None:
        pass


class _ConcreteDatabase:
    def add_recording(self, filename, transcript=None, soap_note=None, referral=None, letter=None, **kwargs) -> int:
        return 1

    def update_recording(self, recording_id: int, **kwargs) -> bool:
        return True

    def get_recording(self, recording_id: int):
        return None


class _ConcreteAutoSave:
    def save(self, data) -> bool:
        return True

    def load(self):
        return None

    def clear(self) -> None:
        pass

    def exists(self) -> bool:
        return False


class _ConcreteProcessingQueue:
    def add_recording(self, recording_data) -> Optional[str]:
        return None

    def get_status(self) -> Dict[str, Any]:
        return {}

    def cancel_task(self, task_id: str) -> bool:
        return False


class _ConcreteNotificationManager:
    def show_completion(self, patient_name, recording_id, task_id, processing_time) -> None:
        pass

    def show_error(self, patient_name, error_message, recording_id, task_id) -> None:
        pass


class _ConcreteDocumentTarget:
    soap_text = None
    letter_text = None
    notebook = None


# Incomplete classes — missing required methods
class _IncompleteStatus:
    def info(self, message: str) -> None:
        pass
    # missing error, success, warning


class _IncompleteRecordingManager:
    @property
    def is_recording(self) -> bool:
        return False
    # missing is_paused and recording control methods


class _IncompleteDatabase:
    def add_recording(self, filename, **kwargs) -> int:
        return 1
    # missing update_recording, get_recording


# ---------------------------------------------------------------------------
# Import / existence tests
# ---------------------------------------------------------------------------

class TestImports:
    def test_status_manager_protocol_importable(self):
        assert StatusManagerProtocol is not None

    def test_recording_manager_protocol_importable(self):
        assert RecordingManagerProtocol is not None

    def test_audio_handler_protocol_importable(self):
        assert AudioHandlerProtocol is not None

    def test_ui_state_manager_protocol_importable(self):
        assert UIStateManagerProtocol is not None

    def test_database_protocol_importable(self):
        assert DatabaseProtocol is not None

    def test_autosave_manager_protocol_importable(self):
        assert AutoSaveManagerProtocol is not None

    def test_processing_queue_protocol_importable(self):
        assert ProcessingQueueProtocol is not None

    def test_notification_manager_protocol_importable(self):
        assert NotificationManagerProtocol is not None

    def test_document_target_protocol_importable(self):
        assert DocumentTargetProtocol is not None

    def test_controller_dependencies_importable(self):
        assert ControllerDependencies is not None


# ---------------------------------------------------------------------------
# Runtime-checkable assertions
# ---------------------------------------------------------------------------

class TestRuntimeCheckable:
    """All Protocol classes must be runtime_checkable so isinstance works."""

    def test_status_manager_is_runtime_checkable(self):
        obj = _ConcreteStatus()
        # Should not raise TypeError
        isinstance(obj, StatusManagerProtocol)

    def test_recording_manager_is_runtime_checkable(self):
        obj = _ConcreteRecordingManager()
        isinstance(obj, RecordingManagerProtocol)

    def test_audio_handler_is_runtime_checkable(self):
        obj = _ConcreteAudioHandler()
        isinstance(obj, AudioHandlerProtocol)

    def test_ui_state_manager_is_runtime_checkable(self):
        obj = _ConcreteUIStateManager()
        isinstance(obj, UIStateManagerProtocol)

    def test_database_is_runtime_checkable(self):
        obj = _ConcreteDatabase()
        isinstance(obj, DatabaseProtocol)

    def test_autosave_manager_is_runtime_checkable(self):
        obj = _ConcreteAutoSave()
        isinstance(obj, AutoSaveManagerProtocol)

    def test_processing_queue_is_runtime_checkable(self):
        obj = _ConcreteProcessingQueue()
        isinstance(obj, ProcessingQueueProtocol)

    def test_notification_manager_is_runtime_checkable(self):
        obj = _ConcreteNotificationManager()
        isinstance(obj, NotificationManagerProtocol)

    def test_document_target_is_runtime_checkable(self):
        obj = _ConcreteDocumentTarget()
        isinstance(obj, DocumentTargetProtocol)


# ---------------------------------------------------------------------------
# StatusManagerProtocol isinstance
# ---------------------------------------------------------------------------

class TestStatusManagerProtocol:
    def test_concrete_satisfies_protocol(self):
        assert isinstance(_ConcreteStatus(), StatusManagerProtocol)

    def test_plain_object_does_not_satisfy(self):
        assert not isinstance(object(), StatusManagerProtocol)

    def test_incomplete_class_does_not_satisfy(self):
        assert not isinstance(_IncompleteStatus(), StatusManagerProtocol)

    def test_concrete_has_info(self):
        assert callable(getattr(_ConcreteStatus(), "info", None))

    def test_concrete_has_error(self):
        assert callable(getattr(_ConcreteStatus(), "error", None))

    def test_concrete_has_success(self):
        assert callable(getattr(_ConcreteStatus(), "success", None))

    def test_concrete_has_warning(self):
        assert callable(getattr(_ConcreteStatus(), "warning", None))


# ---------------------------------------------------------------------------
# RecordingManagerProtocol isinstance
# ---------------------------------------------------------------------------

class TestRecordingManagerProtocol:
    def test_concrete_satisfies_protocol(self):
        assert isinstance(_ConcreteRecordingManager(), RecordingManagerProtocol)

    def test_plain_object_does_not_satisfy(self):
        assert not isinstance(object(), RecordingManagerProtocol)

    def test_is_recording_property_accessible(self):
        rm = _ConcreteRecordingManager()
        assert isinstance(rm.is_recording, bool)

    def test_is_paused_property_accessible(self):
        rm = _ConcreteRecordingManager()
        assert isinstance(rm.is_paused, bool)

    def test_concrete_has_start_recording(self):
        assert callable(getattr(_ConcreteRecordingManager(), "start_recording", None))

    def test_concrete_has_stop_recording(self):
        assert callable(getattr(_ConcreteRecordingManager(), "stop_recording", None))

    def test_concrete_has_pause_recording(self):
        assert callable(getattr(_ConcreteRecordingManager(), "pause_recording", None))

    def test_concrete_has_resume_recording(self):
        assert callable(getattr(_ConcreteRecordingManager(), "resume_recording", None))

    def test_concrete_has_cancel_recording(self):
        assert callable(getattr(_ConcreteRecordingManager(), "cancel_recording", None))


# ---------------------------------------------------------------------------
# AudioHandlerProtocol isinstance
# ---------------------------------------------------------------------------

class TestAudioHandlerProtocol:
    def test_concrete_satisfies_protocol(self):
        assert isinstance(_ConcreteAudioHandler(), AudioHandlerProtocol)

    def test_plain_object_does_not_satisfy(self):
        assert not isinstance(object(), AudioHandlerProtocol)

    def test_has_listen_in_background(self):
        assert callable(getattr(_ConcreteAudioHandler(), "listen_in_background", None))

    def test_has_transcribe_audio(self):
        assert callable(getattr(_ConcreteAudioHandler(), "transcribe_audio", None))

    def test_has_cleanup_resources(self):
        assert callable(getattr(_ConcreteAudioHandler(), "cleanup_resources", None))


# ---------------------------------------------------------------------------
# UIStateManagerProtocol isinstance
# ---------------------------------------------------------------------------

class TestUIStateManagerProtocol:
    def test_concrete_satisfies_protocol(self):
        assert isinstance(_ConcreteUIStateManager(), UIStateManagerProtocol)

    def test_plain_object_does_not_satisfy(self):
        assert not isinstance(object(), UIStateManagerProtocol)

    def test_has_set_recording_state(self):
        assert callable(getattr(_ConcreteUIStateManager(), "set_recording_state", None))


# ---------------------------------------------------------------------------
# DatabaseProtocol isinstance
# ---------------------------------------------------------------------------

class TestDatabaseProtocol:
    def test_concrete_satisfies_protocol(self):
        assert isinstance(_ConcreteDatabase(), DatabaseProtocol)

    def test_plain_object_does_not_satisfy(self):
        assert not isinstance(object(), DatabaseProtocol)

    def test_incomplete_does_not_satisfy(self):
        assert not isinstance(_IncompleteDatabase(), DatabaseProtocol)

    def test_has_add_recording(self):
        assert callable(getattr(_ConcreteDatabase(), "add_recording", None))

    def test_has_update_recording(self):
        assert callable(getattr(_ConcreteDatabase(), "update_recording", None))

    def test_has_get_recording(self):
        assert callable(getattr(_ConcreteDatabase(), "get_recording", None))


# ---------------------------------------------------------------------------
# AutoSaveManagerProtocol isinstance
# ---------------------------------------------------------------------------

class TestAutoSaveManagerProtocol:
    def test_concrete_satisfies_protocol(self):
        assert isinstance(_ConcreteAutoSave(), AutoSaveManagerProtocol)

    def test_plain_object_does_not_satisfy(self):
        assert not isinstance(object(), AutoSaveManagerProtocol)

    def test_has_save(self):
        assert callable(getattr(_ConcreteAutoSave(), "save", None))

    def test_has_load(self):
        assert callable(getattr(_ConcreteAutoSave(), "load", None))

    def test_has_clear(self):
        assert callable(getattr(_ConcreteAutoSave(), "clear", None))

    def test_has_exists(self):
        assert callable(getattr(_ConcreteAutoSave(), "exists", None))


# ---------------------------------------------------------------------------
# ProcessingQueueProtocol isinstance
# ---------------------------------------------------------------------------

class TestProcessingQueueProtocol:
    def test_concrete_satisfies_protocol(self):
        assert isinstance(_ConcreteProcessingQueue(), ProcessingQueueProtocol)

    def test_plain_object_does_not_satisfy(self):
        assert not isinstance(object(), ProcessingQueueProtocol)

    def test_has_add_recording(self):
        assert callable(getattr(_ConcreteProcessingQueue(), "add_recording", None))

    def test_has_get_status(self):
        assert callable(getattr(_ConcreteProcessingQueue(), "get_status", None))

    def test_has_cancel_task(self):
        assert callable(getattr(_ConcreteProcessingQueue(), "cancel_task", None))


# ---------------------------------------------------------------------------
# NotificationManagerProtocol isinstance
# ---------------------------------------------------------------------------

class TestNotificationManagerProtocol:
    def test_concrete_satisfies_protocol(self):
        assert isinstance(_ConcreteNotificationManager(), NotificationManagerProtocol)

    def test_plain_object_does_not_satisfy(self):
        assert not isinstance(object(), NotificationManagerProtocol)

    def test_has_show_completion(self):
        assert callable(getattr(_ConcreteNotificationManager(), "show_completion", None))

    def test_has_show_error(self):
        assert callable(getattr(_ConcreteNotificationManager(), "show_error", None))


# ---------------------------------------------------------------------------
# DocumentTargetProtocol isinstance
# ---------------------------------------------------------------------------

class TestDocumentTargetProtocol:
    def test_concrete_satisfies_protocol(self):
        assert isinstance(_ConcreteDocumentTarget(), DocumentTargetProtocol)

    def test_plain_object_without_attrs_does_not_satisfy(self):
        assert not isinstance(object(), DocumentTargetProtocol)

    def test_has_soap_text_attr(self):
        obj = _ConcreteDocumentTarget()
        assert hasattr(obj, "soap_text")

    def test_has_letter_text_attr(self):
        obj = _ConcreteDocumentTarget()
        assert hasattr(obj, "letter_text")

    def test_has_notebook_attr(self):
        obj = _ConcreteDocumentTarget()
        assert hasattr(obj, "notebook")


# ---------------------------------------------------------------------------
# ControllerDependencies
# ---------------------------------------------------------------------------

class TestControllerDependencies:
    def test_instantiate_with_no_args(self):
        deps = ControllerDependencies()
        assert deps is not None

    def test_all_fields_none_by_default(self):
        deps = ControllerDependencies()
        assert deps.status_manager is None
        assert deps.recording_manager is None
        assert deps.audio_handler is None
        assert deps.ui_state_manager is None
        assert deps.database is None
        assert deps.autosave_manager is None
        assert deps.processing_queue is None
        assert deps.notification_manager is None
        assert deps.document_target is None
        assert deps.ui_updater is None
        assert deps.sound_player is None

    def test_set_status_manager(self):
        sm = _ConcreteStatus()
        deps = ControllerDependencies(status_manager=sm)
        assert deps.status_manager is sm

    def test_set_recording_manager(self):
        rm = _ConcreteRecordingManager()
        deps = ControllerDependencies(recording_manager=rm)
        assert deps.recording_manager is rm

    def test_set_database(self):
        db = _ConcreteDatabase()
        deps = ControllerDependencies(database=db)
        assert deps.database is db

    def test_set_all_fields(self):
        sm = _ConcreteStatus()
        rm = _ConcreteRecordingManager()
        ah = _ConcreteAudioHandler()
        ui = _ConcreteUIStateManager()
        db = _ConcreteDatabase()
        asm = _ConcreteAutoSave()
        pq = _ConcreteProcessingQueue()
        nm = _ConcreteNotificationManager()
        dt = _ConcreteDocumentTarget()
        ui_updater = lambda r, c: None
        sound_player = lambda s: None

        deps = ControllerDependencies(
            status_manager=sm,
            recording_manager=rm,
            audio_handler=ah,
            ui_state_manager=ui,
            database=db,
            autosave_manager=asm,
            processing_queue=pq,
            notification_manager=nm,
            document_target=dt,
            ui_updater=ui_updater,
            sound_player=sound_player,
        )
        assert deps.status_manager is sm
        assert deps.recording_manager is rm
        assert deps.audio_handler is ah
        assert deps.ui_state_manager is ui
        assert deps.database is db
        assert deps.autosave_manager is asm
        assert deps.processing_queue is pq
        assert deps.notification_manager is nm
        assert deps.document_target is dt
        assert deps.ui_updater is ui_updater
        assert deps.sound_player is sound_player

    def test_partial_construction_leaves_others_none(self):
        sm = _ConcreteStatus()
        deps = ControllerDependencies(status_manager=sm)
        assert deps.recording_manager is None
        assert deps.database is None

    def test_has_from_app_classmethod(self):
        assert callable(getattr(ControllerDependencies, "from_app", None))
