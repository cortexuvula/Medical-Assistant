#!/usr/bin/env python3
"""
Tests for ProcessingController - text processing and queue management.

This module tests the ProcessingController class which handles:
- Text refinement and improvement via AI
- Copy/clear/append operations
- Active widget management
- Queue processing for recordings
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import tkinter as tk

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest


class MockApp:
    """Mock application for testing ProcessingController."""

    def __init__(self):
        self.transcript_text = Mock()
        self.soap_text = Mock()
        self.referral_text = Mock()
        self.letter_text = Mock()
        self.chat_text = Mock()
        self.context_text = Mock()
        self.notebook = Mock()
        self.progress_bar = Mock()
        self.refine_button = Mock()
        self.improve_button = Mock()
        self.status_manager = Mock()
        self.ai_processor = Mock()
        self.db = Mock()
        self.file_manager = Mock()
        self.audio_handler = Mock()
        self.audio_segments = []
        self.text_chunks = []
        self.capitalize_next = False
        self.current_recording_id = None
        self.quick_continue_var = Mock()
        self.processing_queue = Mock()
        self.combined_soap_chunks = None
        self.io_executor = Mock()
        self.executor = Mock()

        # Setup transcript_text mock behavior
        self.transcript_text.get.return_value = "Test transcript text"
        self.soap_text.get.return_value = "Test SOAP note"
        self.context_text.get.return_value = "Patient: John Doe"
        self.notebook.index.return_value = 0

    def after(self, ms, func):
        """Mock after() to immediately execute callback."""
        func()

    def clipboard_clear(self):
        pass

    def clipboard_append(self, text):
        self.clipboard_content = text

    def update(self):
        pass

    def update_status(self, message, status_type="info"):
        pass


class TestProcessingControllerInit:
    """Test ProcessingController initialization."""

    def test_import_processing_controller(self):
        """Test ProcessingController can be imported."""
        from core.controllers.processing_controller import ProcessingController
        assert ProcessingController is not None

    def test_processing_controller_creation(self):
        """Test ProcessingController can be created with mock app."""
        from core.controllers.processing_controller import ProcessingController

        mock_app = MockApp()
        controller = ProcessingController(mock_app)

        assert controller is not None
        assert controller.app == mock_app

    def test_processing_controller_lazy_handlers(self):
        """Test export handlers are lazy-loaded."""
        from core.controllers.processing_controller import ProcessingController

        mock_app = MockApp()
        controller = ProcessingController(mock_app)

        # Handlers should be None initially
        assert controller._pdf_handler is None
        assert controller._word_handler is None
        assert controller._fhir_handler is None


class TestActiveWidgetManagement:
    """Test active widget selection based on tab."""

    def test_get_active_widget_transcript_tab(self):
        """Test get_active_text_widget returns transcript for tab 0."""
        from core.controllers.processing_controller import ProcessingController

        mock_app = MockApp()
        mock_app.notebook.index.return_value = 0
        controller = ProcessingController(mock_app)

        widget = controller.get_active_text_widget()
        assert widget == mock_app.transcript_text

    def test_get_active_widget_soap_tab(self):
        """Test get_active_text_widget returns SOAP for tab 1."""
        from core.controllers.processing_controller import ProcessingController

        mock_app = MockApp()
        mock_app.notebook.index.return_value = 1
        controller = ProcessingController(mock_app)

        widget = controller.get_active_text_widget()
        assert widget == mock_app.soap_text

    def test_get_active_widget_referral_tab(self):
        """Test get_active_text_widget returns referral for tab 2."""
        from core.controllers.processing_controller import ProcessingController

        mock_app = MockApp()
        mock_app.notebook.index.return_value = 2
        controller = ProcessingController(mock_app)

        widget = controller.get_active_text_widget()
        assert widget == mock_app.referral_text

    def test_get_active_widget_letter_tab(self):
        """Test get_active_text_widget returns letter for tab 3."""
        from core.controllers.processing_controller import ProcessingController

        mock_app = MockApp()
        mock_app.notebook.index.return_value = 3
        controller = ProcessingController(mock_app)

        widget = controller.get_active_text_widget()
        assert widget == mock_app.letter_text

    def test_get_active_widget_name(self):
        """Test get_active_widget_name returns correct names."""
        from core.controllers.processing_controller import ProcessingController

        mock_app = MockApp()
        controller = ProcessingController(mock_app)

        mock_app.notebook.index.return_value = 0
        assert controller.get_active_widget_name() == "transcript"

        mock_app.notebook.index.return_value = 1
        assert controller.get_active_widget_name() == "soap"

        mock_app.notebook.index.return_value = 2
        assert controller.get_active_widget_name() == "referral"

        mock_app.notebook.index.return_value = 3
        assert controller.get_active_widget_name() == "letter"


class TestTextOperations:
    """Test basic text operations."""

    def test_copy_text(self):
        """Test copy_text copies to clipboard via pyperclip."""
        from unittest.mock import patch as mock_patch
        from core.controllers.processing_controller import ProcessingController

        mock_app = MockApp()
        mock_app.transcript_text.get.return_value = "Text to copy"
        controller = ProcessingController(mock_app)

        with mock_patch('pyperclip.copy') as mock_pyperclip:
            controller.copy_text()
            mock_pyperclip.assert_called_once_with("Text to copy")

    def test_append_text_basic(self):
        """Test append_text adds text to transcript."""
        from core.controllers.processing_controller import ProcessingController

        mock_app = MockApp()
        mock_app.transcript_text.get.return_value = "Existing text"
        controller = ProcessingController(mock_app)

        controller.append_text("new text")

        mock_app.transcript_text.insert.assert_called()

    def test_append_text_capitalizes_after_sentence(self):
        """Test append_text capitalizes after period."""
        from core.controllers.processing_controller import ProcessingController

        mock_app = MockApp()
        mock_app.transcript_text.get.return_value = "First sentence."
        controller = ProcessingController(mock_app)

        controller.append_text("second sentence")

        # Should capitalize first letter
        call_args = mock_app.transcript_text.insert.call_args
        assert call_args is not None
        assert "Second sentence" in str(call_args) or "second sentence" in str(call_args)

    def test_delete_last_word(self):
        """Test delete_last_word removes last word."""
        from core.controllers.processing_controller import ProcessingController

        mock_app = MockApp()
        mock_app.transcript_text.get.return_value = "First second third"
        controller = ProcessingController(mock_app)

        controller.delete_last_word()

        mock_app.transcript_text.delete.assert_called()
        mock_app.transcript_text.insert.assert_called()


class TestPatientNameExtraction:
    """Test patient name extraction from context."""

    def test_extract_patient_name_with_prefix(self):
        """Test extracting patient name with 'Patient:' prefix."""
        from core.controllers.processing_controller import ProcessingController

        mock_app = MockApp()
        controller = ProcessingController(mock_app)

        name = controller.extract_patient_name("Patient: John Doe\nAge: 45")
        assert name == "John Doe"

    def test_extract_patient_name_with_name_prefix(self):
        """Test extracting patient name with 'Name:' prefix."""
        from core.controllers.processing_controller import ProcessingController

        mock_app = MockApp()
        controller = ProcessingController(mock_app)

        name = controller.extract_patient_name("Name: Jane Smith\nDOB: 1980-01-01")
        assert name == "Jane Smith"

    def test_extract_patient_name_no_match(self):
        """Test extraction returns None when no name found."""
        from core.controllers.processing_controller import ProcessingController

        mock_app = MockApp()
        controller = ProcessingController(mock_app)

        name = controller.extract_patient_name("Some random text without name")
        assert name is None

    def test_extract_patient_name_empty_value(self):
        """Test extraction returns None for empty name value."""
        from core.controllers.processing_controller import ProcessingController

        mock_app = MockApp()
        controller = ProcessingController(mock_app)

        name = controller.extract_patient_name("Patient: \nAge: 45")
        assert name is None


class TestFieldNameMapping:
    """Test database field name mapping for widgets."""

    def test_get_field_name_for_soap(self):
        """Test field name for SOAP widget."""
        from core.controllers.processing_controller import ProcessingController

        mock_app = MockApp()
        controller = ProcessingController(mock_app)

        field = controller._get_field_name_for_widget(mock_app.soap_text)
        assert field == "soap_note"

    def test_get_field_name_for_referral(self):
        """Test field name for referral widget."""
        from core.controllers.processing_controller import ProcessingController

        mock_app = MockApp()
        controller = ProcessingController(mock_app)

        field = controller._get_field_name_for_widget(mock_app.referral_text)
        assert field == "referral"

    def test_get_field_name_for_letter(self):
        """Test field name for letter widget."""
        from core.controllers.processing_controller import ProcessingController

        mock_app = MockApp()
        controller = ProcessingController(mock_app)

        field = controller._get_field_name_for_widget(mock_app.letter_text)
        assert field == "letter"

    def test_get_field_name_for_transcript(self):
        """Test field name for transcript widget."""
        from core.controllers.processing_controller import ProcessingController

        mock_app = MockApp()
        controller = ProcessingController(mock_app)

        field = controller._get_field_name_for_widget(mock_app.transcript_text)
        assert field == "transcript"

    def test_get_field_name_for_unknown(self):
        """Test field name returns None for unknown widget."""
        from core.controllers.processing_controller import ProcessingController

        mock_app = MockApp()
        controller = ProcessingController(mock_app)

        unknown_widget = Mock()
        field = controller._get_field_name_for_widget(unknown_widget)
        assert field is None


class TestAIResultHandling:
    """Test AI processing result handling."""

    def test_handle_ai_result_success(self):
        """Test successful AI result updates widget."""
        from core.controllers.processing_controller import ProcessingController

        mock_app = MockApp()
        controller = ProcessingController(mock_app)

        result = Mock()
        result.success = True
        result.value = {"text": "Refined text"}

        widget = Mock()
        widget.edit_separator = Mock()

        with patch('core.controllers.processing_controller.get_undo_history_manager'):
            controller._handle_ai_result(result, "refine", widget)

        widget.delete.assert_called_once()
        widget.insert.assert_called_once()
        mock_app.status_manager.success.assert_called()

    def test_handle_ai_result_failure(self):
        """Test failed AI result shows error."""
        from core.controllers.processing_controller import ProcessingController

        mock_app = MockApp()
        controller = ProcessingController(mock_app)

        result = Mock()
        result.success = False
        result.error = "API error"

        widget = Mock()

        controller._handle_ai_result(result, "improve", widget)

        mock_app.status_manager.error.assert_called()
        widget.delete.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
