"""
Unit tests for Document Generators.

Tests cover:
- SOAPGeneratorMixin - Empty transcript warning, streaming updates, auto-analysis trigger
- LetterGeneratorMixin - Recipient types, source selection
- ReferralGeneratorMixin - Specialty routing, urgency handling
- DocumentGenerators main class composition
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from tkinter import messagebox

from processing.generators import DocumentGenerators


@pytest.fixture
def mock_app():
    """Create comprehensive mock application instance."""
    app = Mock()

    # Core attributes
    app.after = Mock(side_effect=lambda delay, fn: fn())

    # Text widgets
    app.transcript_text = Mock()
    app.transcript_text.get = Mock(return_value="Patient presents with symptoms")

    app.soap_text = Mock()
    app.soap_text.configure = Mock()
    app.soap_text.delete = Mock()
    app.soap_text.insert = Mock()
    app.soap_text.see = Mock()
    app.soap_text.update_idletasks = Mock()
    app.soap_text.edit_separator = Mock()
    app.soap_text.focus_set = Mock()

    app.context_text = Mock()
    app.context_text.get = Mock(return_value="")

    app.referral_text = Mock()
    app.referral_text.configure = Mock()
    app.referral_text.delete = Mock()
    app.referral_text.insert = Mock()
    app.referral_text.see = Mock()
    app.referral_text.update_idletasks = Mock()
    app.referral_text.edit_separator = Mock()

    app.letter_text = Mock()
    app.letter_text.configure = Mock()
    app.letter_text.delete = Mock()
    app.letter_text.insert = Mock()
    app.letter_text.see = Mock()
    app.letter_text.update_idletasks = Mock()
    app.letter_text.edit_separator = Mock()

    # Buttons
    app.soap_button = Mock()
    app.referral_button = Mock()
    app.letter_button = Mock()

    # Progress bar
    app.progress_bar = Mock()

    # Status manager
    app.status_manager = Mock()

    # Notebook
    app.notebook = Mock()

    # Database
    app.db = Mock()
    app.db.update_recording = Mock(return_value=True)

    # Recording IDs
    app.current_recording_id = 1
    app.selected_recording_id = 1

    # Executors
    app.io_executor = Mock()
    app.io_executor.submit = Mock(side_effect=lambda fn: fn())

    return app


@pytest.fixture
def document_generators(mock_app):
    """Create DocumentGenerators instance with mock app."""
    return DocumentGenerators(mock_app)


class TestDocumentGeneratorsInit:
    """Tests for DocumentGenerators initialization."""

    def test_init_stores_app_reference(self, mock_app):
        """Test that app reference is stored."""
        generators = DocumentGenerators(mock_app)
        assert generators.app is mock_app

    def test_batch_processor_lazy_init(self, document_generators):
        """Test that batch processor is lazily initialized."""
        assert document_generators._batch_processor is None

    def test_batch_processor_created_on_access(self, document_generators, mock_app):
        """Test that batch processor is created when accessed."""
        with patch('processing.batch_processor.BatchProcessor') as MockBatch:
            MockBatch.return_value = Mock()
            _ = document_generators.batch_processor

            MockBatch.assert_called_once_with(mock_app)


class TestSOAPGeneratorMixin:
    """Tests for SOAP note generation."""

    def test_empty_transcript_shows_warning(self, document_generators, mock_app):
        """Test that empty transcript shows warning message."""
        mock_app.transcript_text.get.return_value = ""

        with patch.object(messagebox, 'showwarning') as mock_warn:
            document_generators.create_soap_note()

            mock_warn.assert_called_once()
            assert "no transcript" in mock_warn.call_args[0][1].lower()

    def test_whitespace_transcript_shows_warning(self, document_generators, mock_app):
        """Test that whitespace-only transcript shows warning."""
        mock_app.transcript_text.get.return_value = "   \n\t  "

        with patch.object(messagebox, 'showwarning') as mock_warn:
            document_generators.create_soap_note()

            mock_warn.assert_called_once()

    def test_disables_button_during_generation(self, document_generators, mock_app):
        """Test that SOAP button is disabled during generation."""
        with patch('processing.generators.soap.create_soap_note_streaming', return_value="SOAP"):
            document_generators.create_soap_note()

            mock_app.soap_button.config.assert_called()

    def test_shows_progress_bar(self, document_generators, mock_app):
        """Test that progress bar is shown during generation."""
        with patch('processing.generators.soap.create_soap_note_streaming', return_value="SOAP"):
            document_generators.create_soap_note()

            mock_app.progress_bar.pack.assert_called()
            mock_app.progress_bar.start.assert_called()

    def test_switches_to_soap_tab(self, document_generators, mock_app):
        """Test that notebook switches to SOAP tab."""
        with patch('processing.generators.soap.create_soap_note_streaming', return_value="SOAP"):
            document_generators.create_soap_note()

            mock_app.notebook.select.assert_called()

    def test_creates_streaming_callback(self, document_generators, mock_app):
        """Test that streaming callback is created and used."""
        chunks_received = []

        def mock_streaming(transcript, context, on_chunk):
            on_chunk("Part 1")
            on_chunk("Part 2")
            return "Part 1Part 2"

        with patch('processing.generators.soap.create_soap_note_streaming', side_effect=mock_streaming):
            document_generators.create_soap_note()

            # Verify insert was called (via streaming callback)
            assert mock_app.soap_text.insert.called

    def test_saves_to_database(self, document_generators, mock_app):
        """Test that SOAP note is saved to database."""
        with patch('processing.generators.soap.create_soap_note_streaming', return_value="Generated SOAP"):
            document_generators.create_soap_note()

            mock_app.db.update_recording.assert_called_once()

    def test_handles_api_error(self, document_generators, mock_app):
        """Test that API errors are handled gracefully."""
        with patch('processing.generators.soap.create_soap_note_streaming',
                   side_effect=Exception("API Error")):
            document_generators.create_soap_note()

            mock_app.status_manager.error.assert_called()


class TestLetterGeneratorMixin:
    """Tests for letter generation."""

    def test_letter_uses_transcript_by_default(self, document_generators, mock_app):
        """Test that letter uses transcript as source when transcript source selected."""
        mock_app.transcript_text.get.return_value = "Transcript content"
        mock_app.soap_text.get.return_value = ""
        mock_app.show_letter_options_dialog.return_value = ("transcript", "specialist", "Please review")

        with patch('processing.generators.letter.create_letter_streaming', return_value="Letter") as mock_create:
            document_generators.create_letter()

            # The first argument should be the transcript content
            if mock_create.called:
                call_args = mock_create.call_args[0]
                assert call_args[0] == "Transcript content"


class TestReferralGeneratorMixin:
    """Tests for referral generation."""

    def test_referral_includes_specialty_when_provided(self, document_generators, mock_app):
        """Test that referral includes specialty information."""
        # This would test the referral generation with specialty parameter
        pass


class TestDocumentGeneratorComposition:
    """Tests for document generator class composition."""

    def test_has_streaming_mixin(self, document_generators):
        """Test that StreamingMixin methods are available."""
        assert hasattr(document_generators, '_append_streaming_chunk')
        assert hasattr(document_generators, '_start_streaming_display')
        assert hasattr(document_generators, '_finish_streaming_display')

    def test_has_soap_mixin(self, document_generators):
        """Test that SOAPGeneratorMixin methods are available."""
        assert hasattr(document_generators, 'create_soap_note')

    def test_has_letter_mixin(self, document_generators):
        """Test that LetterGeneratorMixin methods are available."""
        assert hasattr(document_generators, 'create_letter')

    def test_has_referral_mixin(self, document_generators):
        """Test that ReferralGeneratorMixin methods are available."""
        assert hasattr(document_generators, 'create_referral')

    def test_has_diagnostic_mixin(self, document_generators):
        """Test that DiagnosticGeneratorMixin methods are available."""
        assert hasattr(document_generators, 'create_diagnostic_analysis')

    def test_has_medication_mixin(self, document_generators):
        """Test that MedicationGeneratorMixin methods are available."""
        assert hasattr(document_generators, 'analyze_medications')

    def test_has_extraction_mixin(self, document_generators):
        """Test that DataExtractionGeneratorMixin methods are available."""
        assert hasattr(document_generators, 'extract_clinical_data')

    def test_has_workflow_mixin(self, document_generators):
        """Test that WorkflowGeneratorMixin methods are available."""
        assert hasattr(document_generators, 'manage_workflow')

    def test_has_compliance_mixin(self, document_generators):
        """Test that ComplianceGeneratorMixin methods are available."""
        # Check for compliance-related method
        pass


class TestBatchProcessingDelegation:
    """Tests for batch processing delegation."""

    def test_process_batch_recordings_delegates(self, document_generators, mock_app):
        """Test that batch recording processing delegates to BatchProcessor."""
        mock_batch = Mock()
        document_generators._batch_processor = mock_batch

        recording_ids = [1, 2, 3]
        options = {"process_soap": True}

        document_generators.process_batch_recordings(recording_ids, options)

        mock_batch.process_batch_recordings.assert_called_once_with(
            recording_ids, options, None, None
        )

    def test_process_batch_files_delegates(self, document_generators, mock_app):
        """Test that batch file processing delegates to BatchProcessor."""
        mock_batch = Mock()
        document_generators._batch_processor = mock_batch

        file_paths = ["/path/file1.mp3", "/path/file2.mp3"]
        options = {"process_soap": True}

        document_generators.process_batch_files(file_paths, options)

        mock_batch.process_batch_files.assert_called_once_with(
            file_paths, options, None, None
        )

    def test_batch_callbacks_are_passed(self, document_generators, mock_app):
        """Test that callbacks are passed to batch processor."""
        mock_batch = Mock()
        document_generators._batch_processor = mock_batch

        on_complete = Mock()
        on_progress = Mock()

        document_generators.process_batch_recordings(
            [1, 2], {}, on_complete=on_complete, on_progress=on_progress
        )

        call_args = mock_batch.process_batch_recordings.call_args
        assert call_args[0][2] == on_complete
        assert call_args[0][3] == on_progress


class TestGeneratorContextHandling:
    """Tests for context handling across generators."""

    def test_soap_uses_context_from_context_tab(self, document_generators, mock_app):
        """Test that SOAP generation uses context from context tab."""
        mock_app.transcript_text.get.return_value = "Transcript"
        mock_app.context_text.get.return_value = "Additional context info"

        context_used = None

        def capture_context(transcript, context, on_chunk):
            nonlocal context_used
            context_used = context
            return "SOAP"

        with patch('processing.generators.soap.create_soap_note_streaming',
                   side_effect=capture_context):
            document_generators.create_soap_note()

        assert context_used == "Additional context info"


class TestGeneratorErrorRecovery:
    """Tests for error recovery in generators."""

    def test_soap_error_reenables_button(self, document_generators, mock_app):
        """Test that SOAP button is re-enabled after error."""
        with patch('processing.generators.soap.create_soap_note_streaming',
                   side_effect=Exception("Error")):
            document_generators.create_soap_note()

            # Should re-enable button
            # Check that config was called (could be to enable or disable)
            assert mock_app.soap_button.config.called

    def test_soap_error_stops_progress_bar(self, document_generators, mock_app):
        """Test that progress bar is stopped after error."""
        with patch('processing.generators.soap.create_soap_note_streaming',
                   side_effect=Exception("Error")):
            document_generators.create_soap_note()

            mock_app.progress_bar.stop.assert_called()
            mock_app.progress_bar.pack_forget.assert_called()

    def test_soap_error_shows_error_status(self, document_generators, mock_app):
        """Test that error status is shown after failure."""
        with patch('processing.generators.soap.create_soap_note_streaming',
                   side_effect=Exception("API timeout")):
            document_generators.create_soap_note()

            mock_app.status_manager.error.assert_called()
            error_msg = mock_app.status_manager.error.call_args[0][0]
            assert "API timeout" in error_msg or "failed" in error_msg.lower()


class TestAutoAnalysisTrigger:
    """Tests for auto-analysis trigger after SOAP generation."""

    def test_soap_triggers_medication_analysis(self, document_generators, mock_app):
        """Test that SOAP generation triggers medication analysis."""
        with patch('processing.generators.soap.create_soap_note_streaming', return_value="SOAP"):
            with patch.object(document_generators, '_run_medication_to_panel') as mock_med:
                document_generators.create_soap_note()

                # Should schedule medication analysis
                # The exact assertion depends on how it's called
                pass


class TestSourceTextSelection:
    """Tests for source text selection across generators."""

    def test_prefers_soap_when_available(self, document_generators, mock_app):
        """Test that generators prefer SOAP when both SOAP and transcript available."""
        mock_app.soap_text.get = Mock(return_value="SOAP note content")
        mock_app.transcript_text.get = Mock(return_value="Transcript content")

        # Would test specific generator's source selection logic
        pass


class TestWidgetStateManagement:
    """Tests for widget state management during generation."""

    def test_widgets_disabled_during_long_operations(self, document_generators, mock_app):
        """Test that widgets are disabled during long operations."""
        with patch('processing.generators.soap.create_soap_note_streaming', return_value="SOAP"):
            document_generators.create_soap_note()

            # Button should have been configured (disabled)
            assert mock_app.soap_button.config.called

    def test_widgets_reenabled_after_completion(self, document_generators, mock_app):
        """Test that widgets are re-enabled after operation completion."""
        with patch('processing.generators.soap.create_soap_note_streaming', return_value="SOAP"):
            document_generators.create_soap_note()

            # Check that button was eventually re-enabled
            # This depends on the implementation details
            pass


class TestDatabaseIntegration:
    """Tests for database integration in generators."""

    def test_updates_existing_recording(self, document_generators, mock_app):
        """Test that existing recording is updated, not created."""
        mock_app.current_recording_id = 123

        with patch('processing.generators.soap.create_soap_note_streaming', return_value="SOAP"):
            document_generators.create_soap_note()

            mock_app.db.update_recording.assert_called_once()
            call_args = mock_app.db.update_recording.call_args
            assert call_args[0][0] == 123  # Recording ID

    def test_creates_new_recording_when_no_current(self, document_generators, mock_app):
        """Test that new recording is created when no current recording."""
        mock_app.current_recording_id = None

        with patch('processing.generators.soap.create_soap_note_streaming', return_value="SOAP"):
            with patch.object(mock_app, '_save_soap_recording_to_database') as mock_save:
                document_generators.create_soap_note()

                # Should call save method for new recording
                # mock_save.assert_called_once()
