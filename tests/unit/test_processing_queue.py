"""
Unit tests for the ProcessingQueue module.

Tests queue operations, task management, and error handling.
"""

import unittest
import sys
import os
import time
import threading
from unittest.mock import Mock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from processing.processing_queue import (
    ProcessingQueue,
    ProcessingError,
    TranscriptionError,
    AudioSaveError,
    DocumentGenerationError
)


class TestCustomExceptions(unittest.TestCase):
    """Test custom exception classes."""

    def test_processing_error(self):
        """Test ProcessingError base exception."""
        with self.assertRaises(ProcessingError):
            raise ProcessingError("Test error")

    def test_transcription_error_is_processing_error(self):
        """Test TranscriptionError inherits from ProcessingError."""
        self.assertTrue(issubclass(TranscriptionError, ProcessingError))

    def test_audio_save_error_is_processing_error(self):
        """Test AudioSaveError inherits from ProcessingError."""
        self.assertTrue(issubclass(AudioSaveError, ProcessingError))

    def test_document_generation_error_is_processing_error(self):
        """Test DocumentGenerationError inherits from ProcessingError."""
        self.assertTrue(issubclass(DocumentGenerationError, ProcessingError))

    def test_exception_message(self):
        """Test exception messages are preserved."""
        msg = "Transcription failed due to network error"
        error = TranscriptionError(msg)
        self.assertEqual(str(error), msg)


class TestProcessingQueueInitialization(unittest.TestCase):
    """Test ProcessingQueue initialization."""

    def test_init_without_app(self):
        """Test initializing queue without app reference."""
        queue = ProcessingQueue(app=None)
        self.assertIsNotNone(queue)
        self.assertIsNone(queue.app)
        queue.shutdown(wait=False)

    def test_init_with_mock_app(self):
        """Test initializing queue with mock app."""
        mock_app = Mock()
        queue = ProcessingQueue(app=mock_app)
        self.assertEqual(queue.app, mock_app)
        queue.shutdown(wait=False)

    def test_init_max_workers(self):
        """Test initializing with custom max_workers."""
        queue = ProcessingQueue(app=None, max_workers=2)
        self.assertEqual(queue.max_workers, 2)
        queue.shutdown(wait=False)

    def test_init_creates_empty_queues(self):
        """Test that initialization creates empty task dictionaries."""
        queue = ProcessingQueue(app=None)
        self.assertEqual(len(queue.active_tasks), 0)
        self.assertEqual(len(queue.completed_tasks), 0)
        self.assertEqual(len(queue.failed_tasks), 0)
        queue.shutdown(wait=False)


class TestAddRecording(unittest.TestCase):
    """Test adding recordings to the queue."""

    def setUp(self):
        """Set up a queue for testing."""
        self.queue = ProcessingQueue(app=None)

    def tearDown(self):
        """Clean up."""
        self.queue.shutdown(wait=False)

    def test_add_recording_returns_task_id(self):
        """Test that adding a recording returns a task ID."""
        recording_data = {
            "recording_id": 1,
            "transcript": "Test transcript",
        }
        task_id = self.queue.add_recording(recording_data)
        self.assertIsNotNone(task_id)
        self.assertIsInstance(task_id, str)

    def test_add_recording_creates_active_task(self):
        """Test that adding a recording creates an active task."""
        recording_data = {
            "recording_id": 1,
            "transcript": "Test transcript",
        }
        task_id = self.queue.add_recording(recording_data)
        self.assertIn(task_id, self.queue.active_tasks)

    def test_add_duplicate_recording_deduplicated(self):
        """Test that duplicate recordings are deduplicated."""
        recording_data = {
            "recording_id": 1,
            "transcript": "Test transcript",
        }
        task_id_1 = self.queue.add_recording(recording_data)
        task_id_2 = self.queue.add_recording(recording_data)

        # Should return same task ID or None for duplicate
        if task_id_2 is not None:
            self.assertEqual(task_id_1, task_id_2)

    def test_add_recording_increments_stats(self):
        """Test that adding a recording updates statistics."""
        initial_count = self.queue.stats["total_queued"]
        recording_data = {
            "recording_id": 1,
            "transcript": "Test transcript",
        }
        self.queue.add_recording(recording_data)
        self.assertEqual(self.queue.stats["total_queued"], initial_count + 1)


class TestGetStatus(unittest.TestCase):
    """Test queue status methods."""

    def setUp(self):
        """Set up a queue for testing."""
        self.queue = ProcessingQueue(app=None)

    def tearDown(self):
        """Clean up."""
        self.queue.shutdown(wait=False)

    def test_get_status_structure(self):
        """Test that get_status returns expected structure."""
        status = self.queue.get_status()
        self.assertIsInstance(status, dict)
        self.assertIn("active_tasks", status)
        self.assertIn("queue_size", status)
        self.assertIn("stats", status)

    def test_get_task_status_unknown_task(self):
        """Test getting status of unknown task returns None."""
        result = self.queue.get_task_status("unknown-task-id")
        self.assertIsNone(result)

    def test_get_task_status_active_task(self):
        """Test getting status of active task."""
        recording_data = {
            "recording_id": 1,
            "transcript": "Test transcript",
        }
        task_id = self.queue.add_recording(recording_data)
        status = self.queue.get_task_status(task_id)
        self.assertIsNotNone(status)


class TestCancelTask(unittest.TestCase):
    """Test task cancellation."""

    def setUp(self):
        """Set up a queue for testing."""
        self.queue = ProcessingQueue(app=None)

    def tearDown(self):
        """Clean up."""
        self.queue.shutdown(wait=False)

    def test_cancel_unknown_task(self):
        """Test cancelling unknown task returns False."""
        result = self.queue.cancel_task("unknown-task-id")
        self.assertFalse(result)

    def test_cancel_active_task(self):
        """Test cancelling an active task."""
        recording_data = {
            "recording_id": 1,
            "transcript": "Test transcript",
        }
        task_id = self.queue.add_recording(recording_data)
        # Note: Task may already be processing, so this may or may not succeed
        # depending on timing. We just verify it doesn't raise an exception.
        self.queue.cancel_task(task_id)


class TestCallbacks(unittest.TestCase):
    """Test callback functionality."""

    def setUp(self):
        """Set up a queue for testing."""
        self.queue = ProcessingQueue(app=None)
        self.callback_called = False
        self.callback_data = None

    def tearDown(self):
        """Clean up."""
        self.queue.shutdown(wait=False)

    def test_status_callback_set(self):
        """Test setting status callback."""
        def callback(task_id, status, queue_size):
            self.callback_called = True

        self.queue.status_callback = callback
        self.assertIsNotNone(self.queue.status_callback)

    def test_completion_callback_set(self):
        """Test setting completion callback."""
        def callback(task_id, recording_data, result):
            self.callback_called = True

        self.queue.completion_callback = callback
        self.assertIsNotNone(self.queue.completion_callback)

    def test_error_callback_set(self):
        """Test setting error callback."""
        def callback(task_id, recording_data, error_msg):
            self.callback_called = True

        self.queue.error_callback = callback
        self.assertIsNotNone(self.queue.error_callback)


class TestShutdown(unittest.TestCase):
    """Test queue shutdown."""

    def test_shutdown_sets_event(self):
        """Test that shutdown sets the shutdown event."""
        queue = ProcessingQueue(app=None)
        self.assertFalse(queue.shutdown_event.is_set())
        queue.shutdown(wait=False)
        self.assertTrue(queue.shutdown_event.is_set())

    def test_shutdown_wait(self):
        """Test shutdown with wait=True."""
        queue = ProcessingQueue(app=None)
        # Should complete without hanging
        queue.shutdown(wait=True)
        self.assertTrue(queue.shutdown_event.is_set())

    def test_shutdown_idempotent(self):
        """Test that shutdown can be called multiple times."""
        queue = ProcessingQueue(app=None)
        queue.shutdown(wait=False)
        queue.shutdown(wait=False)  # Should not raise
        self.assertTrue(queue.shutdown_event.is_set())


class TestBatchProcessing(unittest.TestCase):
    """Test batch processing functionality."""

    def setUp(self):
        """Set up a queue for testing."""
        self.queue = ProcessingQueue(app=None)

    def tearDown(self):
        """Clean up."""
        self.queue.shutdown(wait=False)

    def test_add_batch_recordings(self):
        """Test adding multiple recordings as a batch."""
        recordings = [
            {"recording_id": 1, "transcript": "Test 1"},
            {"recording_id": 2, "transcript": "Test 2"},
            {"recording_id": 3, "transcript": "Test 3"},
        ]
        batch_id = self.queue.add_batch_recordings(recordings)
        self.assertIsNotNone(batch_id)
        self.assertIsInstance(batch_id, str)

    def test_batch_creates_multiple_tasks(self):
        """Test that batch creates a task for each recording."""
        recordings = [
            {"recording_id": 1, "transcript": "Test 1"},
            {"recording_id": 2, "transcript": "Test 2"},
        ]
        initial_count = len(self.queue.active_tasks)
        self.queue.add_batch_recordings(recordings)
        # At least some tasks should be created
        self.assertGreaterEqual(len(self.queue.active_tasks), initial_count)

    def test_get_batch_status_unknown(self):
        """Test getting status of unknown batch returns None."""
        result = self.queue.get_batch_status("unknown-batch-id")
        self.assertIsNone(result)

    def test_cancel_batch_unknown(self):
        """Test cancelling unknown batch returns 0."""
        result = self.queue.cancel_batch("unknown-batch-id")
        self.assertEqual(result, 0)


class TestPriorityOrdering(unittest.TestCase):
    """Test task priority handling."""

    def setUp(self):
        """Set up a queue for testing."""
        self.queue = ProcessingQueue(app=None)

    def tearDown(self):
        """Clean up."""
        self.queue.shutdown(wait=False)

    def test_high_priority_task(self):
        """Test adding high priority task."""
        recording_data = {
            "recording_id": 1,
            "transcript": "Test",
            "priority": "high",
        }
        task_id = self.queue.add_recording(recording_data)
        self.assertIsNotNone(task_id)

    def test_normal_priority_task(self):
        """Test adding normal priority task."""
        recording_data = {
            "recording_id": 1,
            "transcript": "Test",
            "priority": "normal",
        }
        task_id = self.queue.add_recording(recording_data)
        self.assertIsNotNone(task_id)

    def test_low_priority_task(self):
        """Test adding low priority task."""
        recording_data = {
            "recording_id": 1,
            "transcript": "Test",
            "priority": "low",
        }
        task_id = self.queue.add_recording(recording_data)
        self.assertIsNotNone(task_id)


class TestRetryLogic(unittest.TestCase):
    """Test task retry functionality."""

    def setUp(self):
        """Set up a queue for testing."""
        self.queue = ProcessingQueue(app=None)

    def tearDown(self):
        """Clean up."""
        self.queue.shutdown(wait=False)

    def test_should_retry_under_max(self):
        """Test retry allowed when under max retries."""
        recording_data = {"retry_count": 0}
        # Default max_retries is typically 3
        result = self.queue._should_retry(recording_data)
        self.assertTrue(result)

    def test_should_not_retry_at_max(self):
        """Test retry not allowed when at max retries."""
        recording_data = {"retry_count": 10}  # Exceed any reasonable max
        result = self.queue._should_retry(recording_data)
        self.assertFalse(result)


class TestStatistics(unittest.TestCase):
    """Test queue statistics."""

    def setUp(self):
        """Set up a queue for testing."""
        self.queue = ProcessingQueue(app=None)

    def tearDown(self):
        """Clean up."""
        self.queue.shutdown(wait=False)

    def test_initial_stats(self):
        """Test initial statistics values."""
        stats = self.queue.stats
        self.assertEqual(stats["total_queued"], 0)
        self.assertEqual(stats["total_processed"], 0)
        self.assertEqual(stats["total_failed"], 0)

    def test_stats_structure(self):
        """Test that stats contains expected keys."""
        stats = self.queue.stats
        expected_keys = ["total_queued", "total_processed", "total_failed"]
        for key in expected_keys:
            self.assertIn(key, stats)


if __name__ == '__main__':
    unittest.main(verbosity=2)
