"""
Controller Boundary Tests

Tests that controllers can be instantiated with a ServiceRegistry
instead of requiring the full application object. Verifies:
- Dual-mode constructor (app or registry)
- Protocol-backed services accessed via registry
- Backward-compatible app property for widget access

These tests are durable — they test the constructor contract and
service access patterns, not internal controller logic.
"""

import pytest
from unittest.mock import Mock, PropertyMock, MagicMock


def _make_mock_registry():
    """Create a mock ServiceRegistry with typed service mocks."""
    registry = Mock()

    # Protocol-backed services
    registry.status_manager = Mock()
    registry.status_manager.info = Mock()
    registry.status_manager.error = Mock()
    registry.status_manager.success = Mock()
    registry.status_manager.warning = Mock()
    registry.status_manager.update_provider_info = Mock()

    registry.recording_manager = Mock()
    type(registry.recording_manager).is_recording = PropertyMock(return_value=False)
    type(registry.recording_manager).is_paused = PropertyMock(return_value=False)
    registry.recording_manager.start_recording = Mock()
    registry.recording_manager.stop_recording = Mock()
    registry.recording_manager.pause_recording = Mock()
    registry.recording_manager.resume_recording = Mock()
    registry.recording_manager.cancel_recording = Mock()

    registry.audio_handler = Mock()
    registry.audio_handler.soap_mode = False
    registry.audio_handler.silence_threshold = 0.5
    registry.audio_handler.set_stt_provider = Mock()

    registry.ui_state_manager = Mock()
    registry.ui_state_manager.set_recording_state = Mock()

    registry.database = Mock()
    registry.database.add_recording = Mock(return_value=1)
    registry.database.update_recording = Mock(return_value=True)
    registry.database.get_recording = Mock(return_value=None)

    registry.processing_queue = Mock()
    registry.processing_queue.add_recording = Mock()
    registry.processing_queue.get_status = Mock(return_value={})

    registry.notification_manager = Mock()

    # Tk scheduling
    registry.after = Mock(return_value="after_id")

    # UI widgets
    registry.soap_text = Mock()
    registry.letter_text = Mock()
    registry.notebook = Mock()

    return registry


class TestConfigControllerBoundary:
    """Test ConfigController dual-mode constructor and registry access."""

    def test_init_with_registry(self):
        from core.controllers.config_controller import ConfigController
        registry = _make_mock_registry()
        controller = ConfigController(registry=registry)
        assert controller._registry is registry

    def test_init_with_app_builds_registry(self):
        from core.controllers.config_controller import ConfigController
        app = Mock()
        app.status_manager = Mock()
        app.recording_manager = Mock()
        app.audio_handler = Mock()
        app.ui_state_manager = Mock()
        app.db = Mock()
        controller = ConfigController(app)
        assert controller._registry is not None
        assert controller.app is app

    def test_init_without_both_raises(self):
        from core.controllers.config_controller import ConfigController
        with pytest.raises(ValueError, match="requires either app or registry"):
            ConfigController()

    def test_status_manager_via_registry(self):
        from core.controllers.config_controller import ConfigController
        registry = _make_mock_registry()
        # Need app for widget access
        app = Mock()
        controller = ConfigController(app, registry=registry)
        # Trigger a method that uses status_manager
        controller.on_transcription_fallback("groq", "deepgram")
        # The registry's after should have been called (for thread-safe UI update)
        registry.after.assert_called()

    def test_audio_handler_via_registry(self):
        from core.controllers.config_controller import ConfigController
        registry = _make_mock_registry()
        app = Mock()
        app._available_stt_providers = ["groq"]
        app._stt_display_names = ["GROQ"]
        app.stt_combobox = Mock()
        app.stt_combobox.current = Mock(return_value=0)
        controller = ConfigController(app, registry=registry)
        controller.on_stt_change()
        registry.audio_handler.set_stt_provider.assert_called_once_with("groq")


class TestPersistenceControllerBoundary:
    """Test PersistenceController dual-mode constructor."""

    def test_init_with_registry(self):
        from core.controllers.persistence_controller import PersistenceController
        registry = _make_mock_registry()
        controller = PersistenceController(registry=registry)
        assert controller._registry is registry

    def test_init_with_app(self):
        from core.controllers.persistence_controller import PersistenceController
        app = Mock()
        app.status_manager = Mock()
        controller = PersistenceController(app)
        assert controller.app is app

    def test_init_without_both_raises(self):
        from core.controllers.persistence_controller import PersistenceController
        with pytest.raises(ValueError, match="requires either app or registry"):
            PersistenceController()


class TestProcessingControllerBoundary:
    """Test ProcessingController dual-mode constructor and registry access."""

    def test_init_with_registry(self):
        from core.controllers.processing_controller import ProcessingController
        registry = _make_mock_registry()
        controller = ProcessingController(registry=registry)
        assert controller._registry is registry

    def test_init_with_app(self):
        from core.controllers.processing_controller import ProcessingController
        app = Mock()
        app.status_manager = Mock()
        app.db = Mock()
        controller = ProcessingController(app)
        assert controller.app is app

    def test_init_without_both_raises(self):
        from core.controllers.processing_controller import ProcessingController
        with pytest.raises(ValueError, match="requires either app or registry"):
            ProcessingController()

    def test_status_manager_accessible_via_registry(self):
        from core.controllers.processing_controller import ProcessingController
        registry = _make_mock_registry()
        controller = ProcessingController(registry=registry)
        assert controller._registry.status_manager is registry.status_manager

    def test_database_accessible_via_registry(self):
        from core.controllers.processing_controller import ProcessingController
        registry = _make_mock_registry()
        controller = ProcessingController(registry=registry)
        assert controller._registry.database is registry.database


class TestRecordingControllerBoundary:
    """Test RecordingController dual-mode constructor and registry access."""

    def test_init_with_registry(self):
        from core.controllers.recording_controller import RecordingController
        registry = _make_mock_registry()
        # RecordingController creates sub-handlers that need app
        app = Mock()
        controller = RecordingController(app, registry=registry)
        assert controller._registry is registry

    def test_init_with_app(self):
        from core.controllers.recording_controller import RecordingController
        app = Mock()
        app.status_manager = Mock()
        app.recording_manager = Mock()
        app.audio_handler = Mock()
        app.ui_state_manager = Mock()
        controller = RecordingController(app)
        assert controller.app is app

    def test_init_without_both_raises(self):
        from core.controllers.recording_controller import RecordingController
        with pytest.raises(ValueError, match="requires either app or registry"):
            RecordingController()

    def test_recording_manager_via_registry(self):
        from core.controllers.recording_controller import RecordingController
        registry = _make_mock_registry()
        app = Mock()
        controller = RecordingController(app, registry=registry)
        # Access recording state via registry
        assert controller._registry.recording_manager.is_recording is False

    def test_status_manager_via_registry(self):
        from core.controllers.recording_controller import RecordingController
        registry = _make_mock_registry()
        app = Mock()
        controller = RecordingController(app, registry=registry)
        assert controller._registry.status_manager is registry.status_manager
