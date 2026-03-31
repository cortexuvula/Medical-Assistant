"""
Tests for src/core/service_registry.py

Covers: ServiceRegistry instantiation, default None slots, AssertionError on
unregistered service access, successful retrieval after assignment, from_app()
classmethod, and validate() method.
"""

import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from core.service_registry import ServiceRegistry


# ---------------------------------------------------------------------------
# Minimal mock objects that satisfy the relevant protocols
# ---------------------------------------------------------------------------

class _FakeStatus:
    def info(self, msg: str) -> None:
        pass

    def error(self, msg: str, exception=None, context=None) -> None:
        pass

    def success(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        pass


class _FakeRecordingManager:
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


class _FakeAudioHandler:
    soap_mode: bool = False
    silence_threshold: float = 0.03

    def listen_in_background(self, mic_name, callback, phrase_time_limit=None, stream_purpose="default"):
        return lambda: None

    def transcribe_audio(self, audio_data) -> str:
        return ""

    def cleanup_resources(self) -> None:
        pass


class _FakeUIStateManager:
    def set_recording_state(self, recording: bool, paused: bool = False, caller: str = "") -> None:
        pass


class _FakeDatabase:
    def add_recording(self, filename, transcript=None, soap_note=None, referral=None, letter=None, **kwargs) -> int:
        return 1

    def update_recording(self, recording_id: int, **kwargs) -> bool:
        return True

    def get_recording(self, recording_id: int):
        return None


class _FakeAutoSave:
    def save(self, data) -> bool:
        return True

    def load(self):
        return None

    def clear(self) -> None:
        pass

    def exists(self) -> bool:
        return False


class _FakeProcessingQueue:
    def add_recording(self, recording_data):
        return None

    def get_status(self):
        return {}

    def cancel_task(self, task_id: str) -> bool:
        return False


class _FakeNotificationManager:
    def show_completion(self, patient_name, recording_id, task_id, processing_time) -> None:
        pass

    def show_error(self, patient_name, error_message, recording_id, task_id) -> None:
        pass


class _FakeApp:
    """Minimal stand-in for MedicalDictationApp used by from_app()."""
    def __init__(self):
        self.status_manager = _FakeStatus()
        self.recording_manager = _FakeRecordingManager()
        self.audio_handler = _FakeAudioHandler()
        self.ui_state_manager = _FakeUIStateManager()
        self.db = _FakeDatabase()
        self.autosave_manager = _FakeAutoSave()
        self.processing_queue = _FakeProcessingQueue()
        self.notification_manager = _FakeNotificationManager()
        self.soap_text = "soap_text_widget"
        self.letter_text = "letter_text_widget"
        self.notebook = "notebook_widget"

    def after(self, ms, func, *args):
        return None


def _empty_registry() -> ServiceRegistry:
    return ServiceRegistry()


# ===========================================================================
# Initialization — all slots None
# ===========================================================================

class TestInit:
    def test_can_instantiate_with_no_args(self):
        reg = ServiceRegistry()
        assert reg is not None

    def test_is_service_registry_instance(self):
        assert isinstance(ServiceRegistry(), ServiceRegistry)

    def test_status_manager_none(self):
        assert _empty_registry()._status_manager is None

    def test_recording_manager_none(self):
        assert _empty_registry()._recording_manager is None

    def test_audio_handler_none(self):
        assert _empty_registry()._audio_handler is None

    def test_ui_state_manager_none(self):
        assert _empty_registry()._ui_state_manager is None

    def test_database_none(self):
        assert _empty_registry()._database is None

    def test_autosave_manager_none(self):
        assert _empty_registry()._autosave_manager is None

    def test_processing_queue_none(self):
        assert _empty_registry()._processing_queue is None

    def test_notification_manager_none(self):
        assert _empty_registry()._notification_manager is None

    def test_soap_text_none(self):
        assert _empty_registry()._soap_text is None

    def test_letter_text_none(self):
        assert _empty_registry()._letter_text is None

    def test_notebook_none(self):
        assert _empty_registry()._notebook is None

    def test_after_fn_none(self):
        assert _empty_registry()._after_fn is None


# ===========================================================================
# Property accessors — raise AssertionError when None
# ===========================================================================

class TestPropertyAccessorAssertions:
    def test_status_manager_raises_when_none(self):
        with pytest.raises(AssertionError, match="status_manager"):
            _ = _empty_registry().status_manager

    def test_recording_manager_raises_when_none(self):
        with pytest.raises(AssertionError, match="recording_manager"):
            _ = _empty_registry().recording_manager

    def test_audio_handler_raises_when_none(self):
        with pytest.raises(AssertionError, match="audio_handler"):
            _ = _empty_registry().audio_handler

    def test_ui_state_manager_raises_when_none(self):
        with pytest.raises(AssertionError, match="ui_state_manager"):
            _ = _empty_registry().ui_state_manager

    def test_database_raises_when_none(self):
        with pytest.raises(AssertionError, match="database"):
            _ = _empty_registry().database

    def test_autosave_manager_raises_when_none(self):
        with pytest.raises(AssertionError, match="autosave_manager"):
            _ = _empty_registry().autosave_manager

    def test_processing_queue_raises_when_none(self):
        with pytest.raises(AssertionError, match="processing_queue"):
            _ = _empty_registry().processing_queue

    def test_notification_manager_raises_when_none(self):
        with pytest.raises(AssertionError, match="notification_manager"):
            _ = _empty_registry().notification_manager

    def test_after_raises_when_none(self):
        with pytest.raises(AssertionError, match="after"):
            _empty_registry().after(0, lambda: None)


# ===========================================================================
# UI widget property getters (return None when unset, value when set)
# ===========================================================================

class TestUIWidgetGetters:
    def test_soap_text_returns_none_when_unset(self):
        assert _empty_registry().soap_text is None

    def test_letter_text_returns_none_when_unset(self):
        assert _empty_registry().letter_text is None

    def test_notebook_returns_none_when_unset(self):
        assert _empty_registry().notebook is None

    def test_soap_text_returns_value_when_set(self):
        r = _empty_registry()
        r._soap_text = "soap_widget"
        assert r.soap_text == "soap_widget"

    def test_letter_text_returns_value_when_set(self):
        r = _empty_registry()
        r._letter_text = "letter_widget"
        assert r.letter_text == "letter_widget"

    def test_notebook_returns_value_when_set(self):
        r = _empty_registry()
        r._notebook = "nb_widget"
        assert r.notebook == "nb_widget"


# ===========================================================================
# Successful retrieval after direct assignment
# ===========================================================================

class TestServiceAccessors:
    def test_status_manager_round_trip(self):
        reg = _empty_registry()
        sm = _FakeStatus()
        reg._status_manager = sm
        assert reg.status_manager is sm

    def test_recording_manager_round_trip(self):
        reg = _empty_registry()
        rm = _FakeRecordingManager()
        reg._recording_manager = rm
        assert reg.recording_manager is rm

    def test_audio_handler_round_trip(self):
        reg = _empty_registry()
        ah = _FakeAudioHandler()
        reg._audio_handler = ah
        assert reg.audio_handler is ah

    def test_ui_state_manager_round_trip(self):
        reg = _empty_registry()
        ui = _FakeUIStateManager()
        reg._ui_state_manager = ui
        assert reg.ui_state_manager is ui

    def test_database_round_trip(self):
        reg = _empty_registry()
        db = _FakeDatabase()
        reg._database = db
        assert reg.database is db

    def test_autosave_manager_round_trip(self):
        reg = _empty_registry()
        asm = _FakeAutoSave()
        reg._autosave_manager = asm
        assert reg.autosave_manager is asm

    def test_processing_queue_round_trip(self):
        reg = _empty_registry()
        pq = _FakeProcessingQueue()
        reg._processing_queue = pq
        assert reg.processing_queue is pq

    def test_notification_manager_round_trip(self):
        reg = _empty_registry()
        nm = _FakeNotificationManager()
        reg._notification_manager = nm
        assert reg.notification_manager is nm

    def test_multiple_services_set_independently(self):
        reg = _empty_registry()
        sm = _FakeStatus()
        db = _FakeDatabase()
        reg._status_manager = sm
        reg._database = db
        assert reg.status_manager is sm
        assert reg.database is db

    def test_setting_one_service_does_not_unlock_others(self):
        reg = _empty_registry()
        reg._status_manager = _FakeStatus()
        with pytest.raises(AssertionError):
            _ = reg.recording_manager
        with pytest.raises(AssertionError):
            _ = reg.database

    def test_after_fn_callable_when_set(self):
        reg = _empty_registry()
        called_with = []

        def fake_after(ms, func, *args):
            called_with.append((ms, func, args))

        reg._after_fn = fake_after
        cb = lambda: None
        reg.after(100, cb)
        assert len(called_with) == 1
        assert called_with[0][0] == 100
        assert called_with[0][1] is cb

    def test_overwrite_service_slot(self):
        reg = _empty_registry()
        sm1 = _FakeStatus()
        sm2 = _FakeStatus()
        reg._status_manager = sm1
        assert reg.status_manager is sm1
        reg._status_manager = sm2
        assert reg.status_manager is sm2


# ===========================================================================
# from_app classmethod
# ===========================================================================

class TestFromApp:
    def test_returns_service_registry(self):
        r = ServiceRegistry.from_app(_FakeApp())
        assert isinstance(r, ServiceRegistry)

    def test_status_manager_populated(self):
        app = _FakeApp()
        r = ServiceRegistry.from_app(app)
        assert r._status_manager is app.status_manager

    def test_recording_manager_populated(self):
        app = _FakeApp()
        r = ServiceRegistry.from_app(app)
        assert r._recording_manager is app.recording_manager

    def test_audio_handler_populated(self):
        app = _FakeApp()
        r = ServiceRegistry.from_app(app)
        assert r._audio_handler is app.audio_handler

    def test_database_populated(self):
        app = _FakeApp()
        r = ServiceRegistry.from_app(app)
        assert r._database is app.db

    def test_soap_text_populated(self):
        r = ServiceRegistry.from_app(_FakeApp())
        assert r._soap_text == "soap_text_widget"

    def test_letter_text_populated(self):
        r = ServiceRegistry.from_app(_FakeApp())
        assert r._letter_text == "letter_text_widget"

    def test_notebook_populated(self):
        r = ServiceRegistry.from_app(_FakeApp())
        assert r._notebook == "notebook_widget"

    def test_after_fn_populated_when_app_has_after(self):
        r = ServiceRegistry.from_app(_FakeApp())
        assert r._after_fn is not None

    def test_app_without_attribute_stores_none(self):
        class _MinimalApp:
            db = None
        r = ServiceRegistry.from_app(_MinimalApp())
        assert r._database is None


# ===========================================================================
# validate
# ===========================================================================

class TestValidate:
    def test_returns_list(self):
        assert isinstance(_empty_registry().validate(), list)

    def test_empty_registry_has_errors(self):
        errors = _empty_registry().validate()
        assert len(errors) > 0

    def test_errors_mention_unregistered_services(self):
        error_text = "\n".join(_empty_registry().validate())
        assert "status_manager" in error_text

    def test_error_messages_are_strings(self):
        for err in _empty_registry().validate():
            assert isinstance(err, str)

    def test_six_errors_when_all_unregistered(self):
        # Six protocol-backed services are checked by validate()
        assert len(_empty_registry().validate()) == 6

    def test_status_manager_no_longer_reported_as_not_registered_after_set(self):
        r = _empty_registry()
        r._status_manager = _FakeStatus()
        errors = r.validate()
        not_registered = [e for e in errors if "not registered" in e and "status_manager" in e]
        assert len(not_registered) == 0

    def test_valid_full_registry_returns_empty_list(self):
        r = _empty_registry()
        r._status_manager = _FakeStatus()
        r._recording_manager = _FakeRecordingManager()
        r._audio_handler = _FakeAudioHandler()
        r._ui_state_manager = _FakeUIStateManager()
        r._database = _FakeDatabase()
        r._notification_manager = _FakeNotificationManager()
        assert r.validate() == []

    def test_from_app_classmethod_exists(self):
        assert callable(getattr(ServiceRegistry, "from_app", None))
