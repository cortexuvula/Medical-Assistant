"""
Unit tests for BatchProcessor.

Tests cover batch processing of recordings and audio files,
including queue management, progress tracking, and error handling.
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, MagicMock, patch, PropertyMock
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestBatchProcessorInitialization:
    """Tests for BatchProcessor initialization."""

    def test_initialization(self):
        """Test basic initialization."""
        from src.processing.batch_processor import BatchProcessor

        mock_app = Mock()
        processor = BatchProcessor(mock_app)

        assert processor.app is mock_app


class TestProcessBatchRecordings:
    """Tests for batch recording processing."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.processing.batch_processor import BatchProcessor

        self.mock_app = Mock()
        self.mock_app.db = Mock()
        self.mock_app.status_manager = Mock()
        self.mock_app.processing_queue = Mock()

        self.processor = BatchProcessor(self.mock_app)

    def test_no_recordings_found(self):
        """Test handling when no recordings are found."""
        self.mock_app.db.get_recordings_by_ids.return_value = []
        callback = Mock()

        self.processor.process_batch_recordings([1, 2, 3], {}, on_complete=callback)

        self.mock_app.status_manager.error.assert_called_once()
        callback.assert_called_once()

    def test_no_recordings_found_without_callback(self):
        """Test handling when no recordings found and no callback."""
        self.mock_app.db.get_recordings_by_ids.return_value = []

        # Should not raise
        self.processor.process_batch_recordings([1, 2, 3], {})

        self.mock_app.status_manager.error.assert_called_once()

    def test_priority_mapping_low(self):
        """Test priority mapping for low priority."""
        recordings = [{'id': 1, 'filename': 'test.wav', 'transcript': 'text'}]
        self.mock_app.db.get_recordings_by_ids.return_value = recordings
        self.mock_app.processing_queue.add_batch_recordings.return_value = "batch-123"

        self.processor.process_batch_recordings([1], {"priority": "low", "process_soap": True})

        call_args = self.mock_app.processing_queue.add_batch_recordings.call_args
        batch_options = call_args[0][1]
        assert batch_options["priority"] == 3

    def test_priority_mapping_normal(self):
        """Test priority mapping for normal priority."""
        recordings = [{'id': 1, 'filename': 'test.wav', 'transcript': 'text'}]
        self.mock_app.db.get_recordings_by_ids.return_value = recordings
        self.mock_app.processing_queue.add_batch_recordings.return_value = "batch-123"

        self.processor.process_batch_recordings([1], {"priority": "normal", "process_soap": True})

        call_args = self.mock_app.processing_queue.add_batch_recordings.call_args
        batch_options = call_args[0][1]
        assert batch_options["priority"] == 5

    def test_priority_mapping_high(self):
        """Test priority mapping for high priority."""
        recordings = [{'id': 1, 'filename': 'test.wav', 'transcript': 'text'}]
        self.mock_app.db.get_recordings_by_ids.return_value = recordings
        self.mock_app.processing_queue.add_batch_recordings.return_value = "batch-123"

        self.processor.process_batch_recordings([1], {"priority": "high", "process_soap": True})

        call_args = self.mock_app.processing_queue.add_batch_recordings.call_args
        batch_options = call_args[0][1]
        assert batch_options["priority"] == 7

    def test_priority_mapping_default(self):
        """Test default priority when not specified."""
        recordings = [{'id': 1, 'filename': 'test.wav', 'transcript': 'text'}]
        self.mock_app.db.get_recordings_by_ids.return_value = recordings
        self.mock_app.processing_queue.add_batch_recordings.return_value = "batch-123"

        self.processor.process_batch_recordings([1], {"process_soap": True})

        call_args = self.mock_app.processing_queue.add_batch_recordings.call_args
        batch_options = call_args[0][1]
        assert batch_options["priority"] == 5  # Default to normal

    def test_skip_existing_soap(self):
        """Test skipping recordings with existing SOAP notes."""
        recordings = [
            {'id': 1, 'filename': 'test1.wav', 'transcript': 'text', 'soap_note': 'existing'},
            {'id': 2, 'filename': 'test2.wav', 'transcript': 'text', 'soap_note': None}
        ]
        self.mock_app.db.get_recordings_by_ids.return_value = recordings
        self.mock_app.processing_queue.add_batch_recordings.return_value = "batch-123"

        self.processor.process_batch_recordings(
            [1, 2],
            {"skip_existing": True, "process_soap": True}
        )

        call_args = self.mock_app.processing_queue.add_batch_recordings.call_args
        batch_recordings = call_args[0][0]
        # Only recording 2 should be processed
        assert len(batch_recordings) == 1
        assert batch_recordings[0]["recording_id"] == 2

    def test_skip_existing_referral(self):
        """Test skipping recordings with existing referrals."""
        recordings = [
            {'id': 1, 'filename': 'test1.wav', 'transcript': 'text', 'referral': 'existing'},
        ]
        self.mock_app.db.get_recordings_by_ids.return_value = recordings

        callback = Mock()
        self.processor.process_batch_recordings(
            [1],
            {"skip_existing": True, "process_referral": True},
            on_complete=callback
        )

        # All skipped, should show info message
        self.mock_app.status_manager.info.assert_called()
        callback.assert_called_once()

    def test_skip_existing_letter(self):
        """Test skipping recordings with existing letters."""
        recordings = [
            {'id': 1, 'filename': 'test1.wav', 'transcript': 'text', 'letter': 'existing'},
        ]
        self.mock_app.db.get_recordings_by_ids.return_value = recordings

        callback = Mock()
        self.processor.process_batch_recordings(
            [1],
            {"skip_existing": True, "process_letter": True},
            on_complete=callback
        )

        # All skipped
        self.mock_app.status_manager.info.assert_called()
        callback.assert_called_once()

    def test_dont_skip_when_disabled(self):
        """Test not skipping when skip_existing is False."""
        recordings = [
            {'id': 1, 'filename': 'test1.wav', 'transcript': 'text', 'soap_note': 'existing'},
        ]
        self.mock_app.db.get_recordings_by_ids.return_value = recordings
        self.mock_app.processing_queue.add_batch_recordings.return_value = "batch-123"

        self.processor.process_batch_recordings(
            [1],
            {"skip_existing": False, "process_soap": True}
        )

        call_args = self.mock_app.processing_queue.add_batch_recordings.call_args
        batch_recordings = call_args[0][0]
        assert len(batch_recordings) == 1

    def test_all_recordings_skipped(self):
        """Test when all recordings are skipped."""
        recordings = [
            {'id': 1, 'filename': 'test.wav', 'transcript': 'text', 'soap_note': 'existing'},
        ]
        self.mock_app.db.get_recordings_by_ids.return_value = recordings
        callback = Mock()

        self.processor.process_batch_recordings(
            [1],
            {"skip_existing": True, "process_soap": True},
            on_complete=callback
        )

        self.mock_app.status_manager.info.assert_called()
        assert "already have" in self.mock_app.status_manager.info.call_args[0][0].lower()
        callback.assert_called_once()

    def test_initializes_processing_queue_if_needed(self):
        """Test that processing queue is initialized if not present."""
        del self.mock_app.processing_queue
        recordings = [{'id': 1, 'filename': 'test.wav', 'transcript': 'text'}]
        self.mock_app.db.get_recordings_by_ids.return_value = recordings

        with patch('processing.processing_queue.ProcessingQueue') as MockQueue:
            mock_queue = Mock()
            mock_queue.add_batch_recordings.return_value = "batch-123"
            MockQueue.return_value = mock_queue

            self.processor.process_batch_recordings([1], {"process_soap": True})

            MockQueue.assert_called_once_with(self.mock_app)

    def test_sets_batch_callback(self):
        """Test that batch callback is set on processing queue."""
        recordings = [{'id': 1, 'filename': 'test.wav', 'transcript': 'text'}]
        self.mock_app.db.get_recordings_by_ids.return_value = recordings
        self.mock_app.processing_queue.add_batch_recordings.return_value = "batch-123"

        self.processor.process_batch_recordings([1], {"process_soap": True})

        self.mock_app.processing_queue.set_batch_callback.assert_called_once()

    def test_progress_callback_on_start(self):
        """Test progress callback is called at start."""
        recordings = [{'id': 1, 'filename': 'test.wav', 'transcript': 'text'}]
        self.mock_app.db.get_recordings_by_ids.return_value = recordings
        self.mock_app.processing_queue.add_batch_recordings.return_value = "batch-123"

        progress_callback = Mock()

        self.processor.process_batch_recordings(
            [1],
            {"process_soap": True},
            on_progress=progress_callback
        )

        progress_callback.assert_called()
        # First call should be "Starting batch processing"
        first_call = progress_callback.call_args_list[0]
        assert "starting" in first_call[0][0].lower()

    def test_batch_callback_progress_event(self):
        """Test batch callback handles progress event."""
        recordings = [{'id': 1, 'filename': 'test.wav', 'transcript': 'text'}]
        self.mock_app.db.get_recordings_by_ids.return_value = recordings
        self.mock_app.processing_queue.add_batch_recordings.return_value = "batch-123"

        progress_callback = Mock()

        self.processor.process_batch_recordings(
            [1],
            {"process_soap": True},
            on_progress=progress_callback
        )

        # Get the batch callback that was set
        batch_callback = self.mock_app.processing_queue.set_batch_callback.call_args[0][0]

        # Simulate progress event
        batch_callback("progress", "batch-123", 1, 5)

        # Progress callback should have been called
        assert progress_callback.call_count >= 2  # Initial + progress

    def test_batch_callback_completed_event_success(self):
        """Test batch callback handles completion with success."""
        recordings = [{'id': 1, 'filename': 'test.wav', 'transcript': 'text'}]
        self.mock_app.db.get_recordings_by_ids.return_value = recordings
        self.mock_app.processing_queue.add_batch_recordings.return_value = "batch-123"

        complete_callback = Mock()

        self.processor.process_batch_recordings(
            [1],
            {"process_soap": True},
            on_complete=complete_callback
        )

        # Get the batch callback that was set
        batch_callback = self.mock_app.processing_queue.set_batch_callback.call_args[0][0]

        # Simulate completed event
        batch_callback("completed", "batch-123", 5, 5, failed=0)

        complete_callback.assert_called_once()
        self.mock_app.status_manager.success.assert_called()

    def test_batch_callback_completed_event_with_failures(self):
        """Test batch callback handles completion with failures."""
        recordings = [{'id': 1, 'filename': 'test.wav', 'transcript': 'text'}]
        self.mock_app.db.get_recordings_by_ids.return_value = recordings
        self.mock_app.processing_queue.add_batch_recordings.return_value = "batch-123"

        self.processor.process_batch_recordings(
            [1],
            {"process_soap": True}
        )

        # Get the batch callback that was set
        batch_callback = self.mock_app.processing_queue.set_batch_callback.call_args[0][0]

        # Simulate completed event with failures
        batch_callback("completed", "batch-123", 5, 5, failed=2)

        self.mock_app.status_manager.warning.assert_called()
        assert "failed" in self.mock_app.status_manager.warning.call_args[0][0].lower()

    def test_recording_data_structure(self):
        """Test the structure of recording data passed to queue."""
        recordings = [{
            'id': 1,
            'filename': 'test.wav',
            'transcript': 'Patient complains of headache',
            'patient_name': 'John Doe'
        }]
        self.mock_app.db.get_recordings_by_ids.return_value = recordings
        self.mock_app.processing_queue.add_batch_recordings.return_value = "batch-123"

        self.processor.process_batch_recordings(
            [1],
            {"process_soap": True, "process_referral": False, "continue_on_error": False}
        )

        call_args = self.mock_app.processing_queue.add_batch_recordings.call_args
        batch_recordings = call_args[0][0]

        assert len(batch_recordings) == 1
        rec_data = batch_recordings[0]
        assert rec_data["recording_id"] == 1
        assert rec_data["filename"] == "test.wav"
        assert rec_data["transcript"] == "Patient complains of headache"
        assert rec_data["patient_name"] == "John Doe"
        assert rec_data["process_options"]["generate_soap"] is True
        assert rec_data["process_options"]["generate_referral"] is False
        assert rec_data["continue_on_error"] is False

    def test_multiple_recordings(self):
        """Test processing multiple recordings."""
        recordings = [
            {'id': 1, 'filename': 'test1.wav', 'transcript': 'text1'},
            {'id': 2, 'filename': 'test2.wav', 'transcript': 'text2'},
            {'id': 3, 'filename': 'test3.wav', 'transcript': 'text3'}
        ]
        self.mock_app.db.get_recordings_by_ids.return_value = recordings
        self.mock_app.processing_queue.add_batch_recordings.return_value = "batch-123"

        self.processor.process_batch_recordings(
            [1, 2, 3],
            {"process_soap": True}
        )

        call_args = self.mock_app.processing_queue.add_batch_recordings.call_args
        batch_recordings = call_args[0][0]
        assert len(batch_recordings) == 3


class TestProcessBatchFiles:
    """Tests for batch file processing."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.processing.batch_processor import BatchProcessor

        self.mock_app = Mock()
        self.mock_app.db = Mock()
        self.mock_app.status_manager = Mock()
        self.mock_app.processing_queue = Mock()
        self.mock_app.audio_handler = Mock()

        self.processor = BatchProcessor(self.mock_app)

    def test_no_valid_files(self):
        """Test handling when no valid files are provided."""
        callback = Mock()

        self.processor.process_batch_files(
            ["/nonexistent/file.wav"],
            {},
            on_complete=callback
        )

        self.mock_app.status_manager.error.assert_called_once()
        callback.assert_called_once()

    def test_empty_file_list(self):
        """Test handling of empty file list."""
        callback = Mock()

        self.processor.process_batch_files(
            [],
            {},
            on_complete=callback
        )

        self.mock_app.status_manager.error.assert_called_once()
        callback.assert_called_once()

    def test_filters_invalid_paths(self):
        """Test that invalid paths are filtered out."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            valid_file = f.name
            f.write(b'fake audio data')

        try:
            self.mock_app.audio_handler.groq_provider.transcribe.return_value = "transcript"
            self.mock_app.db.add_recording.return_value = 1
            self.mock_app.processing_queue.add_recording.return_value = "task-123"

            with patch('pydub.AudioSegment') as MockAudio:
                MockAudio.from_file.return_value = Mock()

                with patch.dict('src.settings.settings.SETTINGS', {'stt_provider': 'groq'}):
                    self.processor.process_batch_files(
                        [valid_file, "/invalid/path.wav"],
                        {"process_soap": True}
                    )

            # Should process the valid file
            assert self.mock_app.db.add_recording.called
        finally:
            os.unlink(valid_file)

    def test_initializes_processing_queue_if_needed(self):
        """Test that processing queue is initialized if not present."""
        del self.mock_app.processing_queue

        callback = Mock()

        with patch('processing.processing_queue.ProcessingQueue') as MockQueue:
            self.processor.process_batch_files(
                ["/nonexistent.wav"],
                {},
                on_complete=callback
            )

    def test_priority_mapping(self):
        """Test priority mapping for file processing."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            valid_file = f.name
            f.write(b'fake audio data')

        try:
            self.mock_app.audio_handler.groq_provider.transcribe.return_value = "transcript"
            self.mock_app.db.add_recording.return_value = 1
            self.mock_app.processing_queue.add_recording.return_value = "task-123"

            with patch('pydub.AudioSegment') as MockAudio:
                MockAudio.from_file.return_value = Mock()

                with patch.dict('src.settings.settings.SETTINGS', {'stt_provider': 'groq'}):
                    self.processor.process_batch_files(
                        [valid_file],
                        {"priority": "high", "process_soap": True}
                    )

            # Check the recording data passed to add_recording
            call_args = self.mock_app.processing_queue.add_recording.call_args
            recording_data = call_args[0][0]
            assert recording_data["priority"] == 7
        finally:
            os.unlink(valid_file)

    def test_transcription_with_deepgram(self):
        """Test transcription using Deepgram provider."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            valid_file = f.name
            f.write(b'fake audio data')

        try:
            self.mock_app.audio_handler.deepgram_provider.transcribe.return_value = "deepgram transcript"
            self.mock_app.db.add_recording.return_value = 1
            self.mock_app.processing_queue.add_recording.return_value = "task-123"

            with patch('pydub.AudioSegment') as MockAudio:
                MockAudio.from_file.return_value = Mock()

                with patch.dict('src.settings.settings.SETTINGS', {'stt_provider': 'deepgram'}):
                    self.processor.process_batch_files(
                        [valid_file],
                        {"process_soap": True}
                    )

            self.mock_app.audio_handler.deepgram_provider.transcribe.assert_called_once()
        finally:
            os.unlink(valid_file)

    def test_transcription_with_elevenlabs(self):
        """Test transcription using ElevenLabs provider."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            valid_file = f.name
            f.write(b'fake audio data')

        try:
            self.mock_app.audio_handler.elevenlabs_provider.transcribe.return_value = "elevenlabs transcript"
            self.mock_app.db.add_recording.return_value = 1
            self.mock_app.processing_queue.add_recording.return_value = "task-123"

            with patch('pydub.AudioSegment') as MockAudio:
                MockAudio.from_file.return_value = Mock()

                with patch.dict('src.settings.settings.SETTINGS', {'stt_provider': 'elevenlabs'}):
                    self.processor.process_batch_files(
                        [valid_file],
                        {"process_soap": True}
                    )

            self.mock_app.audio_handler.elevenlabs_provider.transcribe.assert_called_once()
        finally:
            os.unlink(valid_file)

    def test_transcription_with_whisper(self):
        """Test transcription using local Whisper provider."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            valid_file = f.name
            f.write(b'fake audio data')

        try:
            self.mock_app.audio_handler.whisper_provider.transcribe.return_value = "whisper transcript"
            self.mock_app.db.add_recording.return_value = 1
            self.mock_app.processing_queue.add_recording.return_value = "task-123"

            with patch('pydub.AudioSegment') as MockAudio:
                MockAudio.from_file.return_value = Mock()

                with patch.dict('src.settings.settings.SETTINGS', {'stt_provider': 'local whisper'}):
                    self.processor.process_batch_files(
                        [valid_file],
                        {"process_soap": True}
                    )

            self.mock_app.audio_handler.whisper_provider.transcribe.assert_called_once()
        finally:
            os.unlink(valid_file)

    def test_transcription_failure_continue_on_error(self):
        """Test handling transcription failure with continue_on_error=True."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            valid_file = f.name
            f.write(b'fake audio data')

        try:
            self.mock_app.audio_handler.groq_provider.transcribe.side_effect = Exception("Transcription failed")

            progress_callback = Mock()

            with patch('pydub.AudioSegment') as MockAudio:
                MockAudio.from_file.return_value = Mock()

                with patch.dict('src.settings.settings.SETTINGS', {'stt_provider': 'groq'}):
                    self.processor.process_batch_files(
                        [valid_file],
                        {"process_soap": True, "continue_on_error": True},
                        on_progress=progress_callback
                    )

            # Should report failure via progress callback but continue
            assert any("failed" in str(call).lower() for call in progress_callback.call_args_list)
        finally:
            os.unlink(valid_file)

    def test_transcription_failure_stop_on_error(self):
        """Test handling transcription failure with continue_on_error=False."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            valid_file = f.name
            f.write(b'fake audio data')

        try:
            self.mock_app.audio_handler.groq_provider.transcribe.side_effect = Exception("Transcription failed")
            complete_callback = Mock()

            with patch('pydub.AudioSegment') as MockAudio:
                MockAudio.from_file.return_value = Mock()

                with patch.dict('src.settings.settings.SETTINGS', {'stt_provider': 'groq'}):
                    with pytest.raises(Exception):
                        self.processor.process_batch_files(
                            [valid_file],
                            {"process_soap": True, "continue_on_error": False},
                            on_complete=complete_callback
                        )

            # Complete callback should still be called
            complete_callback.assert_called_once()
        finally:
            os.unlink(valid_file)

    def test_empty_transcript_handling(self):
        """Test handling when transcription returns empty result."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            valid_file = f.name
            f.write(b'fake audio data')

        try:
            self.mock_app.audio_handler.groq_provider.transcribe.return_value = None
            progress_callback = Mock()

            with patch('pydub.AudioSegment') as MockAudio:
                MockAudio.from_file.return_value = Mock()

                with patch.dict('src.settings.settings.SETTINGS', {'stt_provider': 'groq'}):
                    self.processor.process_batch_files(
                        [valid_file],
                        {"process_soap": True},
                        on_progress=progress_callback
                    )

            # Should not add to database
            self.mock_app.db.add_recording.assert_not_called()
        finally:
            os.unlink(valid_file)

    def test_database_save_failure(self):
        """Test handling when database save fails."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            valid_file = f.name
            f.write(b'fake audio data')

        try:
            self.mock_app.audio_handler.groq_provider.transcribe.return_value = "transcript"
            self.mock_app.db.add_recording.return_value = None  # Failure

            with patch('pydub.AudioSegment') as MockAudio:
                MockAudio.from_file.return_value = Mock()

                with patch.dict('src.settings.settings.SETTINGS', {'stt_provider': 'groq'}):
                    with pytest.raises(Exception):
                        self.processor.process_batch_files(
                            [valid_file],
                            {"process_soap": True, "continue_on_error": False}
                        )
        finally:
            os.unlink(valid_file)

    def test_progress_callback_called(self):
        """Test that progress callback is called during processing."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            valid_file = f.name
            f.write(b'fake audio data')

        try:
            self.mock_app.audio_handler.groq_provider.transcribe.return_value = "transcript"
            self.mock_app.db.add_recording.return_value = 1
            self.mock_app.processing_queue.add_recording.return_value = "task-123"

            progress_callback = Mock()

            with patch('pydub.AudioSegment') as MockAudio:
                MockAudio.from_file.return_value = Mock()

                with patch.dict('src.settings.settings.SETTINGS', {'stt_provider': 'groq'}):
                    self.processor.process_batch_files(
                        [valid_file],
                        {"process_soap": True},
                        on_progress=progress_callback
                    )

            assert progress_callback.call_count >= 2  # At least processing and queued
        finally:
            os.unlink(valid_file)

    def test_completion_callback_called(self):
        """Test that completion callback is called."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            valid_file = f.name
            f.write(b'fake audio data')

        try:
            self.mock_app.audio_handler.groq_provider.transcribe.return_value = "transcript"
            self.mock_app.db.add_recording.return_value = 1
            self.mock_app.processing_queue.add_recording.return_value = "task-123"

            complete_callback = Mock()

            with patch('pydub.AudioSegment') as MockAudio:
                MockAudio.from_file.return_value = Mock()

                with patch.dict('src.settings.settings.SETTINGS', {'stt_provider': 'groq'}):
                    self.processor.process_batch_files(
                        [valid_file],
                        {"process_soap": True},
                        on_complete=complete_callback
                    )

            complete_callback.assert_called_once()
        finally:
            os.unlink(valid_file)

    def test_success_message_on_completion(self):
        """Test that success message is shown on completion."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            valid_file = f.name
            f.write(b'fake audio data')

        try:
            self.mock_app.audio_handler.groq_provider.transcribe.return_value = "transcript"
            self.mock_app.db.add_recording.return_value = 1
            self.mock_app.processing_queue.add_recording.return_value = "task-123"

            with patch('pydub.AudioSegment') as MockAudio:
                MockAudio.from_file.return_value = Mock()

                with patch.dict('src.settings.settings.SETTINGS', {'stt_provider': 'groq'}):
                    self.processor.process_batch_files(
                        [valid_file],
                        {"process_soap": True}
                    )

            self.mock_app.status_manager.success.assert_called_once()
        finally:
            os.unlink(valid_file)

    def test_recording_data_structure(self):
        """Test the structure of recording data passed to queue."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            valid_file = f.name
            f.write(b'fake audio data')

        try:
            self.mock_app.audio_handler.groq_provider.transcribe.return_value = "test transcript"
            self.mock_app.db.add_recording.return_value = 42
            self.mock_app.processing_queue.add_recording.return_value = "task-123"

            with patch('pydub.AudioSegment') as MockAudio:
                MockAudio.from_file.return_value = Mock()

                with patch.dict('src.settings.settings.SETTINGS', {'stt_provider': 'groq'}):
                    self.processor.process_batch_files(
                        [valid_file],
                        {"process_soap": True, "process_referral": False}
                    )

            call_args = self.mock_app.processing_queue.add_recording.call_args
            recording_data = call_args[0][0]

            assert recording_data["recording_id"] == 42
            assert recording_data["transcript"] == "test transcript"
            assert recording_data["audio_path"] == valid_file
            assert recording_data["process_options"]["generate_soap"] is True
            assert recording_data["process_options"]["generate_referral"] is False
        finally:
            os.unlink(valid_file)

    def test_unknown_stt_provider(self):
        """Test handling of unknown STT provider."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            valid_file = f.name
            f.write(b'fake audio data')

        try:
            progress_callback = Mock()

            with patch('pydub.AudioSegment') as MockAudio:
                MockAudio.from_file.return_value = Mock()

                with patch.dict('src.settings.settings.SETTINGS', {'stt_provider': 'unknown_provider'}):
                    self.processor.process_batch_files(
                        [valid_file],
                        {"process_soap": True, "continue_on_error": True},
                        on_progress=progress_callback
                    )

            # Should report the unknown provider error
            assert any("unknown" in str(call).lower() or "failed" in str(call).lower()
                      for call in progress_callback.call_args_list)
        finally:
            os.unlink(valid_file)

    def test_multiple_files_processing(self):
        """Test processing multiple files."""
        files = []
        try:
            for i in range(3):
                f = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                f.write(b'fake audio data')
                f.close()
                files.append(f.name)

            self.mock_app.audio_handler.groq_provider.transcribe.return_value = "transcript"
            self.mock_app.db.add_recording.side_effect = [1, 2, 3]
            self.mock_app.processing_queue.add_recording.return_value = "task-123"

            with patch('pydub.AudioSegment') as MockAudio:
                MockAudio.from_file.return_value = Mock()

                with patch.dict('src.settings.settings.SETTINGS', {'stt_provider': 'groq'}):
                    self.processor.process_batch_files(
                        files,
                        {"process_soap": True}
                    )

            assert self.mock_app.db.add_recording.call_count == 3
            assert self.mock_app.processing_queue.add_recording.call_count == 3
        finally:
            for f in files:
                os.unlink(f)


class TestBatchProcessorEdgeCases:
    """Edge case tests for BatchProcessor."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.processing.batch_processor import BatchProcessor

        self.mock_app = Mock()
        self.mock_app.db = Mock()
        self.mock_app.status_manager = Mock()
        self.mock_app.processing_queue = Mock()

        self.processor = BatchProcessor(self.mock_app)

    def test_recording_with_missing_fields(self):
        """Test handling recordings with missing optional fields."""
        recordings = [{'id': 1}]  # Minimal recording
        self.mock_app.db.get_recordings_by_ids.return_value = recordings
        self.mock_app.processing_queue.add_batch_recordings.return_value = "batch-123"

        self.processor.process_batch_recordings([1], {"process_soap": True})

        call_args = self.mock_app.processing_queue.add_batch_recordings.call_args
        batch_recordings = call_args[0][0]
        rec_data = batch_recordings[0]

        # Should use defaults for missing fields
        assert rec_data["filename"] == ""
        assert rec_data["transcript"] == ""
        assert rec_data["patient_name"] == "Unknown"

    def test_directory_path_rejected(self):
        """Test that directory paths are rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            callback = Mock()

            self.processor.process_batch_files(
                [tmpdir],  # Directory, not file
                {},
                on_complete=callback
            )

            self.mock_app.status_manager.error.assert_called_once()

    def test_none_processing_queue_attribute(self):
        """Test handling when processing_queue is None."""
        self.mock_app.processing_queue = None
        recordings = [{'id': 1, 'filename': 'test.wav', 'transcript': 'text'}]
        self.mock_app.db.get_recordings_by_ids.return_value = recordings

        with patch('processing.processing_queue.ProcessingQueue') as MockQueue:
            mock_queue = Mock()
            mock_queue.add_batch_recordings.return_value = "batch-123"
            MockQueue.return_value = mock_queue

            self.processor.process_batch_recordings([1], {"process_soap": True})

            MockQueue.assert_called_once()
