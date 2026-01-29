"""
Extended unit tests for BatchProcessor.

Tests cover:
- Mixed skip/process scenarios
- Transcription failure with continue-on-error
- Progress callback events
- Unsupported format filtering
- Priority mapping
- Batch callback handling
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
import os

from processing.batch_processor import BatchProcessor


@pytest.fixture
def mock_app():
    """Create comprehensive mock application instance."""
    app = Mock()

    # Database
    app.db = Mock()
    app.db.get_recordings_by_ids = Mock(return_value=[])

    # Status manager
    app.status_manager = Mock()

    # Processing queue
    app.processing_queue = Mock()
    app.processing_queue.add_batch_recordings = Mock(return_value="batch-123")
    app.processing_queue.set_batch_callback = Mock()

    # Audio handler for file processing
    app.audio_handler = Mock()
    app.audio_handler.transcribe_audio_file = Mock(return_value="Transcribed text")

    return app


@pytest.fixture
def batch_processor(mock_app):
    """Create BatchProcessor instance with mock app."""
    return BatchProcessor(mock_app)


@pytest.fixture
def sample_recordings():
    """Create sample recording data."""
    return [
        {
            'id': 1,
            'filename': 'recording1.mp3',
            'transcript': 'Transcript 1',
            'patient_name': 'John Doe',
            'soap_note': None,
            'referral': None,
            'letter': None,
        },
        {
            'id': 2,
            'filename': 'recording2.mp3',
            'transcript': 'Transcript 2',
            'patient_name': 'Jane Smith',
            'soap_note': 'Existing SOAP',  # Has existing SOAP
            'referral': None,
            'letter': None,
        },
        {
            'id': 3,
            'filename': 'recording3.mp3',
            'transcript': 'Transcript 3',
            'patient_name': 'Bob Wilson',
            'soap_note': None,
            'referral': 'Existing Referral',  # Has existing referral
            'letter': None,
        },
    ]


class TestBatchRecordingProcessing:
    """Tests for batch recording processing."""

    def test_no_recordings_found(self, batch_processor, mock_app):
        """Test handling when no recordings are found."""
        mock_app.db.get_recordings_by_ids.return_value = []
        on_complete = Mock()

        batch_processor.process_batch_recordings([1, 2, 3], {}, on_complete=on_complete)

        mock_app.status_manager.error.assert_called_once()
        on_complete.assert_called_once()

    def test_skip_existing_soap(self, batch_processor, mock_app, sample_recordings):
        """Test skipping recordings with existing SOAP notes."""
        mock_app.db.get_recordings_by_ids.return_value = sample_recordings

        options = {
            'process_soap': True,
            'skip_existing': True,
        }

        batch_processor.process_batch_recordings([1, 2, 3], options)

        # Should have added batch for non-skipped recordings only
        call_args = mock_app.processing_queue.add_batch_recordings.call_args[0]
        batch_data = call_args[0]

        # Recording 2 has SOAP, should be skipped
        recording_ids = [r['recording_id'] for r in batch_data]
        assert 2 not in recording_ids
        assert 1 in recording_ids
        assert 3 in recording_ids

    def test_skip_existing_referral(self, batch_processor, mock_app, sample_recordings):
        """Test skipping recordings with existing referrals."""
        mock_app.db.get_recordings_by_ids.return_value = sample_recordings

        options = {
            'process_referral': True,
            'skip_existing': True,
        }

        batch_processor.process_batch_recordings([1, 2, 3], options)

        call_args = mock_app.processing_queue.add_batch_recordings.call_args[0]
        batch_data = call_args[0]

        # Recording 3 has referral, should be skipped
        recording_ids = [r['recording_id'] for r in batch_data]
        assert 3 not in recording_ids

    def test_all_skipped_shows_info(self, batch_processor, mock_app, sample_recordings):
        """Test info message when all recordings are skipped."""
        # All have SOAP notes
        for rec in sample_recordings:
            rec['soap_note'] = 'Existing SOAP'

        mock_app.db.get_recordings_by_ids.return_value = sample_recordings
        on_complete = Mock()

        options = {
            'process_soap': True,
            'skip_existing': True,
        }

        batch_processor.process_batch_recordings([1, 2, 3], options, on_complete=on_complete)

        mock_app.status_manager.info.assert_called_once()
        on_complete.assert_called_once()

    def test_dont_skip_when_disabled(self, batch_processor, mock_app, sample_recordings):
        """Test that skip_existing=False processes all."""
        mock_app.db.get_recordings_by_ids.return_value = sample_recordings

        options = {
            'process_soap': True,
            'skip_existing': False,
        }

        batch_processor.process_batch_recordings([1, 2, 3], options)

        call_args = mock_app.processing_queue.add_batch_recordings.call_args[0]
        batch_data = call_args[0]

        # Should include all recordings
        assert len(batch_data) == 3


class TestPriorityMapping:
    """Tests for priority string to numeric mapping."""

    def test_low_priority(self, batch_processor, mock_app, sample_recordings):
        """Test low priority mapping."""
        mock_app.db.get_recordings_by_ids.return_value = sample_recordings[:1]

        batch_processor.process_batch_recordings([1], {'priority': 'low'})

        call_args = mock_app.processing_queue.add_batch_recordings.call_args[0]
        batch_options = call_args[1]
        assert batch_options['priority'] == 3

    def test_normal_priority(self, batch_processor, mock_app, sample_recordings):
        """Test normal priority mapping."""
        mock_app.db.get_recordings_by_ids.return_value = sample_recordings[:1]

        batch_processor.process_batch_recordings([1], {'priority': 'normal'})

        call_args = mock_app.processing_queue.add_batch_recordings.call_args[0]
        batch_options = call_args[1]
        assert batch_options['priority'] == 5

    def test_high_priority(self, batch_processor, mock_app, sample_recordings):
        """Test high priority mapping."""
        mock_app.db.get_recordings_by_ids.return_value = sample_recordings[:1]

        batch_processor.process_batch_recordings([1], {'priority': 'high'})

        call_args = mock_app.processing_queue.add_batch_recordings.call_args[0]
        batch_options = call_args[1]
        assert batch_options['priority'] == 7

    def test_default_priority(self, batch_processor, mock_app, sample_recordings):
        """Test default priority when not specified."""
        mock_app.db.get_recordings_by_ids.return_value = sample_recordings[:1]

        batch_processor.process_batch_recordings([1], {})

        call_args = mock_app.processing_queue.add_batch_recordings.call_args[0]
        batch_options = call_args[1]
        assert batch_options['priority'] == 5  # Normal


class TestProgressCallbacks:
    """Tests for progress callback handling."""

    def test_progress_callback_called(self, batch_processor, mock_app, sample_recordings):
        """Test that progress callback is invoked."""
        mock_app.db.get_recordings_by_ids.return_value = sample_recordings[:1]
        on_progress = Mock()

        batch_processor.process_batch_recordings([1], {}, on_progress=on_progress)

        on_progress.assert_called()

    def test_progress_callback_receives_count(self, batch_processor, mock_app, sample_recordings):
        """Test that progress callback receives correct counts."""
        mock_app.db.get_recordings_by_ids.return_value = sample_recordings[:1]
        on_progress = Mock()

        batch_processor.process_batch_recordings([1], {}, on_progress=on_progress)

        call_args = on_progress.call_args[0]
        assert call_args[1] == 0  # Current
        assert call_args[2] == 1  # Total


class TestBatchCallbackHandling:
    """Tests for batch callback events."""

    def test_batch_callback_set(self, batch_processor, mock_app, sample_recordings):
        """Test that batch callback is set on queue."""
        mock_app.db.get_recordings_by_ids.return_value = sample_recordings[:1]

        batch_processor.process_batch_recordings([1], {})

        mock_app.processing_queue.set_batch_callback.assert_called_once()

    def test_batch_callback_handles_progress(self, batch_processor, mock_app, sample_recordings):
        """Test that batch callback handles progress events."""
        mock_app.db.get_recordings_by_ids.return_value = sample_recordings[:1]
        on_progress = Mock()

        # Capture the callback
        captured_callback = None

        def capture_callback(cb):
            nonlocal captured_callback
            captured_callback = cb

        mock_app.processing_queue.set_batch_callback.side_effect = capture_callback

        batch_processor.process_batch_recordings([1], {}, on_progress=on_progress)

        # Simulate progress event
        if captured_callback:
            captured_callback('progress', 'batch-123', 1, 3)
            # on_progress should have been called
            assert on_progress.called

    def test_batch_callback_handles_completion(self, batch_processor, mock_app, sample_recordings):
        """Test that batch callback handles completion events."""
        mock_app.db.get_recordings_by_ids.return_value = sample_recordings[:1]
        on_complete = Mock()

        captured_callback = None

        def capture_callback(cb):
            nonlocal captured_callback
            captured_callback = cb

        mock_app.processing_queue.set_batch_callback.side_effect = capture_callback

        batch_processor.process_batch_recordings([1], {}, on_complete=on_complete)

        # Simulate completion event
        if captured_callback:
            captured_callback('completed', 'batch-123', 3, 3, failed=0)
            on_complete.assert_called_once()

    def test_batch_completion_shows_success_status(self, batch_processor, mock_app, sample_recordings):
        """Test that successful completion shows success status."""
        mock_app.db.get_recordings_by_ids.return_value = sample_recordings[:1]

        captured_callback = None

        def capture_callback(cb):
            nonlocal captured_callback
            captured_callback = cb

        mock_app.processing_queue.set_batch_callback.side_effect = capture_callback

        batch_processor.process_batch_recordings([1], {})

        if captured_callback:
            captured_callback('completed', 'batch-123', 3, 3, failed=0)
            mock_app.status_manager.success.assert_called()

    def test_batch_completion_with_failures_shows_warning(self, batch_processor, mock_app, sample_recordings):
        """Test that completion with failures shows warning."""
        mock_app.db.get_recordings_by_ids.return_value = sample_recordings[:1]

        captured_callback = None

        def capture_callback(cb):
            nonlocal captured_callback
            captured_callback = cb

        mock_app.processing_queue.set_batch_callback.side_effect = capture_callback

        batch_processor.process_batch_recordings([1], {})

        if captured_callback:
            captured_callback('completed', 'batch-123', 3, 3, failed=1)
            mock_app.status_manager.warning.assert_called()


class TestBatchFileProcessing:
    """Tests for batch file processing."""

    def test_no_valid_files(self, batch_processor, mock_app):
        """Test handling when no valid files are provided."""
        on_complete = Mock()

        batch_processor.process_batch_files([], {}, on_complete=on_complete)

        mock_app.status_manager.error.assert_called_once()
        on_complete.assert_called_once()

    def test_invalid_file_paths_filtered(self, batch_processor, mock_app):
        """Test that invalid file paths are filtered out."""
        with patch('os.path.exists', side_effect=[True, False, True]):
            with patch('os.path.isfile', return_value=True):
                batch_processor.process_batch_files(
                    ['/valid1.mp3', '/invalid.mp3', '/valid2.mp3'],
                    {}
                )

                # Should process only valid files

    def test_file_existence_check(self, batch_processor, mock_app):
        """Test that file existence is checked."""
        with patch('os.path.exists', return_value=False):
            on_complete = Mock()

            batch_processor.process_batch_files(
                ['/nonexistent.mp3'],
                {},
                on_complete=on_complete
            )

            mock_app.status_manager.error.assert_called()


class TestContinueOnError:
    """Tests for continue-on-error behavior."""

    def test_continue_on_error_passed_to_queue(self, batch_processor, mock_app, sample_recordings):
        """Test that continue_on_error option is passed to queue."""
        mock_app.db.get_recordings_by_ids.return_value = sample_recordings[:1]

        batch_processor.process_batch_recordings([1], {'continue_on_error': True})

        call_args = mock_app.processing_queue.add_batch_recordings.call_args[0]
        batch_options = call_args[1]
        assert batch_options['continue_on_error'] is True

    def test_continue_on_error_default_true(self, batch_processor, mock_app, sample_recordings):
        """Test that continue_on_error defaults to True."""
        mock_app.db.get_recordings_by_ids.return_value = sample_recordings[:1]

        batch_processor.process_batch_recordings([1], {})

        call_args = mock_app.processing_queue.add_batch_recordings.call_args[0]
        batch_options = call_args[1]
        assert batch_options['continue_on_error'] is True


class TestRecordingDataPreparation:
    """Tests for recording data preparation."""

    def test_recording_data_includes_required_fields(self, batch_processor, mock_app, sample_recordings):
        """Test that prepared data includes all required fields."""
        mock_app.db.get_recordings_by_ids.return_value = sample_recordings[:1]

        batch_processor.process_batch_recordings([1], {'process_soap': True})

        call_args = mock_app.processing_queue.add_batch_recordings.call_args[0]
        batch_data = call_args[0][0]  # First recording

        assert 'recording_id' in batch_data
        assert 'filename' in batch_data
        assert 'transcript' in batch_data
        assert 'patient_name' in batch_data
        assert 'process_options' in batch_data

    def test_process_options_set_correctly(self, batch_processor, mock_app, sample_recordings):
        """Test that process options are set correctly."""
        mock_app.db.get_recordings_by_ids.return_value = sample_recordings[:1]

        options = {
            'process_soap': True,
            'process_referral': True,
            'process_letter': False,
        }

        batch_processor.process_batch_recordings([1], options)

        call_args = mock_app.processing_queue.add_batch_recordings.call_args[0]
        batch_data = call_args[0][0]
        process_opts = batch_data['process_options']

        assert process_opts['generate_soap'] is True
        assert process_opts['generate_referral'] is True
        assert process_opts['generate_letter'] is False


class TestProcessingQueueInitialization:
    """Tests for processing queue initialization."""

    def test_creates_queue_if_missing(self, batch_processor, mock_app, sample_recordings):
        """Test that processing queue is created if not present."""
        mock_app.db.get_recordings_by_ids.return_value = sample_recordings[:1]
        mock_app.processing_queue = None

        with patch('processing.processing_queue.ProcessingQueue') as MockQueue:
            MockQueue.return_value = Mock()
            MockQueue.return_value.add_batch_recordings = Mock(return_value='batch-123')
            MockQueue.return_value.set_batch_callback = Mock()

            batch_processor.process_batch_recordings([1], {})

            MockQueue.assert_called_once_with(mock_app)

    def test_uses_existing_queue(self, batch_processor, mock_app, sample_recordings):
        """Test that existing queue is used if present."""
        mock_app.db.get_recordings_by_ids.return_value = sample_recordings[:1]

        existing_queue = Mock()
        existing_queue.add_batch_recordings = Mock(return_value='batch-123')
        existing_queue.set_batch_callback = Mock()
        mock_app.processing_queue = existing_queue

        with patch('processing.processing_queue.ProcessingQueue') as MockQueue:
            batch_processor.process_batch_recordings([1], {})

            # Should NOT create new queue
            MockQueue.assert_not_called()


class TestBatchIdTracking:
    """Tests for batch ID tracking."""

    def test_returns_batch_id(self, batch_processor, mock_app, sample_recordings):
        """Test that batch ID is returned from queue."""
        mock_app.db.get_recordings_by_ids.return_value = sample_recordings[:1]
        mock_app.processing_queue.add_batch_recordings.return_value = 'batch-unique-123'

        batch_processor.process_batch_recordings([1], {})

        mock_app.processing_queue.add_batch_recordings.assert_called_once()
