"""
Tests for ServiceRegistry in src/core/service_registry.py

Covers initialization (all slots None), property accessors (assert on None),
soap_text/letter_text/notebook getters, from_app() classmethod,
validate() (errors when unregistered, count, message content).
No network, no Tkinter, no real services.
"""

import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from core.service_registry import ServiceRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_registry() -> ServiceRegistry:
    return ServiceRegistry()


class _FakeApp:
    """Minimal stand-in for MedicalDictationApp."""
    def __init__(self):
        self.status_manager = object()
        self.recording_manager = object()
        self.audio_handler = object()
        self.ui_state_manager = object()
        self.db = object()
        self.autosave_manager = object()
        self.processing_queue = object()
        self.notification_manager = object()
        self.soap_text = "soap_text_widget"
        self.letter_text = "letter_text_widget"
        self.notebook = "notebook_widget"

    def after(self, ms, func, *args):
        return None


# ===========================================================================
# Initialization — all slots None
# ===========================================================================

class TestInit:
    def test_status_manager_none(self):
        r = _empty_registry()
        assert r._status_manager is None

    def test_recording_manager_none(self):
        r = _empty_registry()
        assert r._recording_manager is None

    def test_audio_handler_none(self):
        r = _empty_registry()
        assert r._audio_handler is None

    def test_ui_state_manager_none(self):
        r = _empty_registry()
        assert r._ui_state_manager is None

    def test_database_none(self):
        r = _empty_registry()
        assert r._database is None

    def test_autosave_manager_none(self):
        r = _empty_registry()
        assert r._autosave_manager is None

    def test_processing_queue_none(self):
        r = _empty_registry()
        assert r._processing_queue is None

    def test_notification_manager_none(self):
        r = _empty_registry()
        assert r._notification_manager is None

    def test_soap_text_none(self):
        r = _empty_registry()
        assert r._soap_text is None

    def test_letter_text_none(self):
        r = _empty_registry()
        assert r._letter_text is None

    def test_notebook_none(self):
        r = _empty_registry()
        assert r._notebook is None

    def test_after_fn_none(self):
        r = _empty_registry()
        assert r._after_fn is None


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
# UI widget property getters (return None when unset)
# ===========================================================================

class TestUIWidgetGetters:
    def test_soap_text_returns_none_when_unset(self):
        r = _empty_registry()
        assert r.soap_text is None

    def test_letter_text_returns_none_when_unset(self):
        r = _empty_registry()
        assert r.letter_text is None

    def test_notebook_returns_none_when_unset(self):
        r = _empty_registry()
        assert r.notebook is None

    def test_soap_text_returns_value_when_set(self):
        r = _empty_registry()
        r._soap_text = "widget"
        assert r.soap_text == "widget"

    def test_letter_text_returns_value_when_set(self):
        r = _empty_registry()
        r._letter_text = "widget"
        assert r.letter_text == "widget"

    def test_notebook_returns_value_when_set(self):
        r = _empty_registry()
        r._notebook = "widget"
        assert r.notebook == "widget"


# ===========================================================================
# from_app classmethod
# ===========================================================================

class TestFromApp:
    def test_returns_service_registry(self):
        app = _FakeApp()
        r = ServiceRegistry.from_app(app)
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
        app = _FakeApp()
        r = ServiceRegistry.from_app(app)
        assert r._soap_text == "soap_text_widget"

    def test_letter_text_populated(self):
        app = _FakeApp()
        r = ServiceRegistry.from_app(app)
        assert r._letter_text == "letter_text_widget"

    def test_notebook_populated(self):
        app = _FakeApp()
        r = ServiceRegistry.from_app(app)
        assert r._notebook == "notebook_widget"

    def test_after_fn_populated_when_app_has_after(self):
        app = _FakeApp()
        r = ServiceRegistry.from_app(app)
        assert r._after_fn is not None

    def test_app_without_attribute_stores_none(self):
        """from_app uses getattr with None fallback for missing attributes."""
        class _MinimalApp:
            db = None
        r = ServiceRegistry.from_app(_MinimalApp())
        assert r._database is None


# ===========================================================================
# validate
# ===========================================================================

class TestValidate:
    def test_returns_list(self):
        r = _empty_registry()
        assert isinstance(r.validate(), list)

    def test_empty_registry_has_errors(self):
        r = _empty_registry()
        errors = r.validate()
        assert len(errors) > 0

    def test_errors_mention_unregistered_services(self):
        r = _empty_registry()
        errors = r.validate()
        error_text = "\n".join(errors)
        assert "status_manager" in error_text

    def test_error_messages_are_strings(self):
        for err in _empty_registry().validate():
            assert isinstance(err, str)

    def test_six_errors_when_all_unregistered(self):
        # Six protocol-backed services are checked
        r = _empty_registry()
        assert len(r.validate()) == 6

    def test_none_errors_when_valid_objects_assigned(self):
        """
        When non-None objects are set for each checked service,
        validate should return no 'not registered' errors (though
        protocol satisfaction is checked — stubs may fail isinstance).
        """
        r = _empty_registry()
        r._status_manager = object()
        errors = r.validate()
        # status_manager no longer 'not registered' — but may fail isinstance
        not_registered = [e for e in errors if "not registered" in e and "status_manager" in e]
        assert len(not_registered) == 0
