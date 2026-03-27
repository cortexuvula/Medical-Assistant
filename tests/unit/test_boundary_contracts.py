"""
Boundary Contract Tests

Tests that concrete implementations satisfy their protocol contracts
and that the ServiceRegistry correctly wires and validates services.

These tests are *durable* — they test stable interfaces, not internal
implementation details. They survive refactoring of the concrete classes.
"""

import pytest
from unittest.mock import Mock, MagicMock, PropertyMock


class TestProtocolCompliance:
    """Verify concrete classes structurally satisfy their protocols."""

    def test_status_manager_satisfies_protocol(self):
        from core.interfaces import StatusManagerProtocol
        from ui.status_manager import StatusManager
        # StatusManager requires tk widgets — check structural compliance
        assert hasattr(StatusManager, 'info')
        assert hasattr(StatusManager, 'error')
        assert hasattr(StatusManager, 'success')
        assert hasattr(StatusManager, 'warning')
        assert callable(getattr(StatusManager, 'info'))

    def test_recording_manager_satisfies_protocol(self):
        from core.interfaces import RecordingManagerProtocol
        from audio.recording_manager import RecordingManager
        assert hasattr(RecordingManager, 'start_recording')
        assert hasattr(RecordingManager, 'stop_recording')
        assert hasattr(RecordingManager, 'pause_recording')
        assert hasattr(RecordingManager, 'resume_recording')
        assert hasattr(RecordingManager, 'cancel_recording')
        assert hasattr(RecordingManager, 'is_recording')
        assert hasattr(RecordingManager, 'is_paused')

    def test_notification_manager_satisfies_protocol(self):
        from core.interfaces import NotificationManagerProtocol
        from managers.notification_manager import NotificationManager
        assert hasattr(NotificationManager, 'show_completion')
        assert hasattr(NotificationManager, 'show_error')

    def test_ui_state_manager_satisfies_protocol(self):
        from core.interfaces import UIStateManagerProtocol
        from core.ui_state_manager import UIStateManager
        assert hasattr(UIStateManager, 'set_recording_state')

    def test_database_satisfies_protocol(self):
        from core.interfaces import DatabaseProtocol
        from database.database import Database
        assert hasattr(Database, 'add_recording')
        assert hasattr(Database, 'update_recording')
        assert hasattr(Database, 'get_recording')

    def test_processing_queue_satisfies_protocol(self):
        from core.interfaces import ProcessingQueueProtocol
        from processing.processing_queue import ProcessingQueue
        assert hasattr(ProcessingQueue, 'add_recording')
        assert hasattr(ProcessingQueue, 'get_status')
        assert hasattr(ProcessingQueue, 'cancel_task')


class TestDocumentTargetProtocol:
    """Verify DocumentTargetProtocol is well-defined."""

    def test_mock_satisfies_document_target(self):
        from core.interfaces import DocumentTargetProtocol
        mock_target = Mock()
        mock_target.soap_text = Mock()
        mock_target.letter_text = Mock()
        mock_target.notebook = Mock()
        assert isinstance(mock_target, DocumentTargetProtocol)

    def test_incomplete_mock_fails_document_target(self):
        from core.interfaces import DocumentTargetProtocol
        mock_target = Mock(spec=[])  # Empty spec — no attributes
        assert not isinstance(mock_target, DocumentTargetProtocol)


class TestServiceRegistry:
    """Test ServiceRegistry construction, access, and validation."""

    def _make_mock_app(self):
        """Create a mock app with the attributes ServiceRegistry.from_app expects."""
        app = Mock()
        app.status_manager = Mock()
        app.status_manager.info = Mock()
        app.status_manager.error = Mock()
        app.status_manager.success = Mock()
        app.status_manager.warning = Mock()
        app.recording_manager = Mock()
        app.recording_manager.start_recording = Mock()
        app.recording_manager.stop_recording = Mock()
        app.recording_manager.pause_recording = Mock()
        app.recording_manager.resume_recording = Mock()
        app.recording_manager.cancel_recording = Mock()
        type(app.recording_manager).is_recording = PropertyMock(return_value=False)
        type(app.recording_manager).is_paused = PropertyMock(return_value=False)
        app.audio_handler = Mock()
        app.audio_handler.soap_mode = False
        app.audio_handler.silence_threshold = 0.5
        app.audio_handler.listen_in_background = Mock()
        app.audio_handler.transcribe_audio = Mock()
        app.audio_handler.cleanup_resources = Mock()
        app.ui_state_manager = Mock()
        app.ui_state_manager.set_recording_state = Mock()
        app.db = Mock()
        app.db.add_recording = Mock()
        app.db.update_recording = Mock()
        app.db.get_recording = Mock()
        app.autosave_manager = Mock()
        app.processing_queue = Mock()
        app.processing_queue.add_recording = Mock()
        app.processing_queue.get_status = Mock()
        app.processing_queue.cancel_task = Mock()
        app.notification_manager = Mock()
        app.notification_manager.show_completion = Mock()
        app.notification_manager.show_error = Mock()
        app.soap_text = Mock()
        app.letter_text = Mock()
        app.notebook = Mock()
        app.after = Mock(return_value="after_id")
        return app

    def test_from_app_populates_all_services(self):
        from core.service_registry import ServiceRegistry
        app = self._make_mock_app()
        registry = ServiceRegistry.from_app(app)

        assert registry.status_manager is app.status_manager
        assert registry.recording_manager is app.recording_manager
        assert registry.audio_handler is app.audio_handler
        assert registry.ui_state_manager is app.ui_state_manager
        assert registry.database is app.db
        assert registry.processing_queue is app.processing_queue
        assert registry.notification_manager is app.notification_manager
        assert registry.soap_text is app.soap_text
        assert registry.letter_text is app.letter_text
        assert registry.notebook is app.notebook

    def test_from_app_handles_missing_attributes(self):
        from core.service_registry import ServiceRegistry
        app = Mock(spec=[])  # Empty — no attributes
        registry = ServiceRegistry.from_app(app)
        # Should not raise — attributes will be None
        errors = registry.validate()
        assert len(errors) > 0  # All services missing

    def test_validate_reports_missing_services(self):
        from core.service_registry import ServiceRegistry
        registry = ServiceRegistry()
        errors = registry.validate()
        assert any("not registered" in e for e in errors)

    def test_validate_passes_with_valid_app(self):
        from core.service_registry import ServiceRegistry
        app = self._make_mock_app()
        registry = ServiceRegistry.from_app(app)
        errors = registry.validate()
        # May have some errors for AutoSaveManager (not protocol-checked)
        # but core services should pass
        protocol_errors = [e for e in errors if "not registered" in e]
        assert len(protocol_errors) == 0

    def test_typed_accessor_asserts_on_none(self):
        from core.service_registry import ServiceRegistry
        registry = ServiceRegistry()
        with pytest.raises(AssertionError, match="status_manager not registered"):
            _ = registry.status_manager

    def test_after_delegates_to_app(self):
        from core.service_registry import ServiceRegistry
        app = self._make_mock_app()
        registry = ServiceRegistry.from_app(app)
        callback = Mock()
        registry.after(100, callback, "arg1")
        app.after.assert_called_once_with(100, callback, "arg1")

    def test_registry_satisfies_document_target_protocol(self):
        """ServiceRegistry itself satisfies DocumentTargetProtocol when populated."""
        from core.service_registry import ServiceRegistry
        from core.interfaces import DocumentTargetProtocol
        app = self._make_mock_app()
        registry = ServiceRegistry.from_app(app)
        assert isinstance(registry, DocumentTargetProtocol)
