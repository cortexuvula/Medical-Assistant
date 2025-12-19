"""Regression tests for database operations.

These tests verify that all CRUD operations, search functionality,
pagination, and thread safety work correctly.
"""
import pytest
import sqlite3
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestDatabaseInitialization:
    """Tests for database initialization and connection management."""

    def test_database_creates_file(self, tmp_path):
        """Database should create the SQLite file on initialization."""
        from src.database.database import Database

        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        db.create_tables()

        assert db_path.exists(), "Database file should be created"
        db.close_all_connections()

    def test_database_context_manager(self, tmp_path):
        """Database should work as a context manager."""
        from src.database.database import Database

        db_path = tmp_path / "test.db"

        with Database(str(db_path)) as db:
            db.create_tables()
            assert db_path.exists()

        # Connection should be closed after context exit
        # File should still exist
        assert db_path.exists()

    def test_create_tables_creates_recordings_table(self, tmp_path):
        """create_tables() should create the recordings table."""
        from src.database.database import Database

        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        db.create_tables()

        # Verify table exists
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='recordings'"
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None, "recordings table should exist"
        db.close_all_connections()

    def test_connection_per_thread(self, tmp_path):
        """Each thread should get its own connection."""
        from src.database.database import Database

        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        db.create_tables()

        connections = []

        def get_conn():
            conn = db._get_connection()
            connections.append(id(conn))

        # Create connections from multiple threads
        threads = [threading.Thread(target=get_conn) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All connections should be different
        assert len(set(connections)) == 3, "Each thread should have unique connection"
        db.close_all_connections()


class TestDatabaseCRUD:
    """Tests for Create, Read, Update, Delete operations."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create a fresh database for each test."""
        from src.database.database import Database

        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        db.create_tables()
        yield db
        db.close_all_connections()

    def test_add_recording_returns_id(self, db):
        """add_recording() should return the new recording ID."""
        recording_id = db.add_recording(
            filename="test.wav",
            transcript="Test transcript"
        )

        assert recording_id is not None
        assert isinstance(recording_id, int)
        assert recording_id > 0

    def test_add_recording_with_all_fields(self, db):
        """add_recording() should accept all optional fields."""
        recording_id = db.add_recording(
            filename="test.wav",
            transcript="Test transcript",
            soap_note="S: Test\nO: Test\nA: Test\nP: Test",
            referral="Dear Doctor...",
            letter="To whom it may concern..."
        )

        recording = db.get_recording(recording_id)

        assert recording is not None
        assert recording["filename"] == "test.wav"
        assert recording["transcript"] == "Test transcript"
        assert recording["soap_note"] == "S: Test\nO: Test\nA: Test\nP: Test"
        assert recording["referral"] == "Dear Doctor..."
        assert recording["letter"] == "To whom it may concern..."

    def test_add_recording_minimal(self, db):
        """add_recording() should work with just filename."""
        recording_id = db.add_recording(filename="minimal.wav")

        recording = db.get_recording(recording_id)

        assert recording is not None
        assert recording["filename"] == "minimal.wav"
        assert recording["transcript"] is None

    def test_get_recording_by_id(self, db):
        """get_recording() should return correct recording."""
        recording_id = db.add_recording(
            filename="test.wav",
            transcript="Specific content"
        )

        recording = db.get_recording(recording_id)

        assert recording is not None
        assert recording["id"] == recording_id
        assert recording["transcript"] == "Specific content"

    def test_get_recording_nonexistent(self, db):
        """get_recording() should return None for non-existent ID."""
        recording = db.get_recording(99999)

        assert recording is None

    def test_update_recording_single_field(self, db):
        """update_recording() should update a single field."""
        recording_id = db.add_recording(
            filename="test.wav",
            transcript="Original"
        )

        result = db.update_recording(recording_id, transcript="Updated")

        assert result is True
        recording = db.get_recording(recording_id)
        assert recording["transcript"] == "Updated"

    def test_update_recording_multiple_fields(self, db):
        """update_recording() should update multiple fields."""
        recording_id = db.add_recording(filename="test.wav")

        result = db.update_recording(
            recording_id,
            transcript="New transcript",
            soap_note="New SOAP"
        )

        assert result is True
        recording = db.get_recording(recording_id)
        assert recording["transcript"] == "New transcript"
        assert recording["soap_note"] == "New SOAP"

    def test_update_recording_nonexistent(self, db):
        """update_recording() should return False for non-existent ID."""
        result = db.update_recording(99999, transcript="Test")

        assert result is False

    def test_update_recording_invalid_field(self, db):
        """update_recording() should ignore invalid fields."""
        recording_id = db.add_recording(filename="test.wav")

        # Invalid field should be ignored, but valid ones still work
        result = db.update_recording(
            recording_id,
            invalid_field="value",
            transcript="Valid update"
        )

        recording = db.get_recording(recording_id)
        assert recording["transcript"] == "Valid update"

    def test_delete_recording(self, db):
        """delete_recording() should remove the recording."""
        recording_id = db.add_recording(filename="test.wav")

        result = db.delete_recording(recording_id)

        assert result is True
        assert db.get_recording(recording_id) is None

    def test_delete_recording_nonexistent(self, db):
        """delete_recording() should return False for non-existent ID."""
        result = db.delete_recording(99999)

        assert result is False


class TestDatabaseQuery:
    """Tests for query and search operations."""

    @pytest.fixture
    def db_with_data(self, tmp_path):
        """Create database with sample data."""
        from src.database.database import Database

        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        db.create_tables()

        # Add sample recordings
        db.add_recording(filename="rec1.wav", transcript="Patient has headache")
        db.add_recording(filename="rec2.wav", transcript="Patient has chest pain")
        db.add_recording(filename="rec3.wav", transcript="Follow up visit")
        db.add_recording(filename="rec4.wav", soap_note="S: Headache reported")
        db.add_recording(filename="rec5.wav", letter="Dear Dr. Smith")

        yield db
        db.close_all_connections()

    def test_get_all_recordings(self, db_with_data):
        """get_all_recordings() should return all recordings."""
        recordings = db_with_data.get_all_recordings()

        assert len(recordings) == 5
        assert all("id" in r for r in recordings)
        assert all("filename" in r for r in recordings)

    def test_get_all_recordings_ordered_by_timestamp(self, db_with_data):
        """get_all_recordings() should return newest first."""
        recordings = db_with_data.get_all_recordings()

        # Should be ordered by timestamp descending
        # Last added should be first
        assert recordings[0]["filename"] == "rec5.wav"

    def test_get_recordings_paginated(self, db_with_data):
        """get_recordings_paginated() should respect limit and offset."""
        # Get first 2
        page1 = db_with_data.get_recordings_paginated(limit=2, offset=0)
        assert len(page1) == 2

        # Get next 2
        page2 = db_with_data.get_recordings_paginated(limit=2, offset=2)
        assert len(page2) == 2

        # Pages should have different recordings
        page1_ids = {r["id"] for r in page1}
        page2_ids = {r["id"] for r in page2}
        assert page1_ids.isdisjoint(page2_ids)

    def test_search_recordings_in_transcript(self, db_with_data):
        """search_recordings() should find matches in transcript."""
        results = db_with_data.search_recordings("headache")

        assert len(results) >= 1
        assert any("headache" in r["transcript"].lower() for r in results if r.get("transcript"))

    def test_search_recordings_in_soap_note(self, db_with_data):
        """search_recordings() should find matches in SOAP note."""
        results = db_with_data.search_recordings("Headache")

        # Should find the one with "Headache" in soap_note
        assert len(results) >= 1

    def test_search_recordings_in_letter(self, db_with_data):
        """search_recordings() should find matches in letter."""
        results = db_with_data.search_recordings("Dr. Smith")

        assert len(results) >= 1

    def test_search_recordings_no_results(self, db_with_data):
        """search_recordings() should return empty list for no matches."""
        results = db_with_data.search_recordings("xyznonexistent")

        assert results == []

    def test_get_recordings_by_ids(self, db_with_data):
        """get_recordings_by_ids() should return correct recordings."""
        all_recs = db_with_data.get_all_recordings()
        target_ids = [all_recs[0]["id"], all_recs[2]["id"]]

        results = db_with_data.get_recordings_by_ids(target_ids)

        assert len(results) == 2
        result_ids = {r["id"] for r in results}
        assert result_ids == set(target_ids)

    def test_get_recordings_by_ids_empty(self, db_with_data):
        """get_recordings_by_ids() should return empty list for empty input."""
        results = db_with_data.get_recordings_by_ids([])

        assert results == []


class TestDatabaseFieldValidation:
    """Tests for field validation and SQL injection prevention."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create a fresh database for each test."""
        from src.database.database import Database

        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        db.create_tables()
        yield db
        db.close_all_connections()

    def test_field_validation_rejects_invalid_field(self):
        """Field validation should reject fields not in allowlist."""
        from src.database.database import _validate_field_name
        from src.database.schema import RECORDING_UPDATE_FIELDS

        with pytest.raises(ValueError) as exc_info:
            _validate_field_name("invalid_field", RECORDING_UPDATE_FIELDS, "test")

        assert "not allowed" in str(exc_info.value).lower()

    def test_field_validation_rejects_sql_injection(self):
        """Field validation should reject SQL injection attempts."""
        from src.database.database import _validate_field_name
        from src.database.schema import RECORDING_UPDATE_FIELDS

        injection_attempts = [
            "field; DROP TABLE recordings;--",
            "field' OR '1'='1",
            "field\"; DELETE FROM recordings;--",
        ]

        for attempt in injection_attempts:
            with pytest.raises(ValueError):
                _validate_field_name(attempt, RECORDING_UPDATE_FIELDS, "test")

    def test_field_validation_accepts_valid_fields(self):
        """Field validation should accept valid fields."""
        from src.database.database import _validate_field_name
        from src.database.schema import RECORDING_UPDATE_FIELDS

        valid_fields = ["transcript", "soap_note", "referral", "letter"]

        for field in valid_fields:
            result = _validate_field_name(field, RECORDING_UPDATE_FIELDS, "test")
            assert result == field


class TestDatabaseThreadSafety:
    """Tests for thread-safe database operations."""

    def test_concurrent_writes(self, tmp_path):
        """Database should handle concurrent writes safely."""
        from src.database.database import Database

        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        db.create_tables()

        errors = []
        ids = []
        lock = threading.Lock()

        def add_recording(i):
            try:
                rec_id = db.add_recording(
                    filename=f"concurrent_{i}.wav",
                    transcript=f"Transcript {i}"
                )
                with lock:
                    ids.append(rec_id)
            except Exception as e:
                with lock:
                    errors.append(e)

        # Create 10 concurrent writes
        threads = [threading.Thread(target=add_recording, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent writes: {errors}"
        assert len(ids) == 10, "All recordings should be created"
        assert len(set(ids)) == 10, "All IDs should be unique"

        db.close_all_connections()

    def test_concurrent_reads_and_writes(self, tmp_path):
        """Database should handle concurrent reads and writes."""
        from src.database.database import Database

        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        db.create_tables()

        # Add initial data
        for i in range(5):
            db.add_recording(filename=f"initial_{i}.wav")

        errors = []

        def read_all():
            try:
                for _ in range(10):
                    db.get_all_recordings()
                    time.sleep(0.01)
            except Exception as e:
                errors.append(("read", e))

        def write_new(i):
            try:
                db.add_recording(filename=f"new_{i}.wav")
            except Exception as e:
                errors.append(("write", e))

        # Mix of readers and writers
        threads = []
        for i in range(3):
            threads.append(threading.Thread(target=read_all))
            threads.append(threading.Thread(target=write_new, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent operations: {errors}"

        db.close_all_connections()


class TestDatabaseCleanup:
    """Tests for database cleanup and connection management."""

    def test_close_all_connections(self, tmp_path):
        """close_all_connections() should close all thread connections."""
        from src.database.database import Database

        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        db.create_tables()

        # Create connections from multiple threads
        def use_db():
            db.add_recording(filename="test.wav")

        threads = [threading.Thread(target=use_db) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have connections
        assert db.get_connection_count() >= 1

        # Close all
        db.close_all_connections()

        # Should be marked as closed
        assert db._closed is True

    def test_cleanup_stale_connections(self, tmp_path):
        """cleanup_stale_connections() should remove dead thread connections."""
        from src.database.database import Database

        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        db.create_tables()

        # Create connection from a thread that will end
        def use_and_exit():
            db.add_recording(filename="test.wav")

        thread = threading.Thread(target=use_and_exit)
        thread.start()
        thread.join()

        # Thread is dead, but connection might still be tracked
        initial_count = db.get_connection_count()

        # Cleanup stale connections
        cleaned = db.cleanup_stale_connections()

        # Should have cleaned up at least the dead thread's connection
        assert db.get_connection_count() <= initial_count

        db.close_all_connections()

    def test_clear_all_recordings(self, tmp_path):
        """clear_all_recordings() should remove all recordings."""
        from src.database.database import Database

        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        db.create_tables()

        # Add some recordings
        for i in range(5):
            db.add_recording(filename=f"test_{i}.wav")

        assert len(db.get_all_recordings()) == 5

        # Clear all
        result = db.clear_all_recordings()

        assert result is True
        assert len(db.get_all_recordings()) == 0

        db.close_all_connections()


class TestDatabaseQueue:
    """Tests for processing queue operations."""

    @pytest.fixture
    def db_with_queue(self, tmp_path):
        """Create database with queue tables."""
        from src.database.database import Database

        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        db.create_tables()

        # Create queue tables manually for testing
        with db.connection() as (conn, cursor):
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processing_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recording_id INTEGER NOT NULL,
                    task_id TEXT UNIQUE NOT NULL,
                    batch_id TEXT,
                    priority INTEGER DEFAULT 5,
                    status TEXT DEFAULT 'queued',
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    error_count INTEGER DEFAULT 0,
                    last_error TEXT,
                    result TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS batch_processing (
                    batch_id TEXT PRIMARY KEY,
                    total_count INTEGER DEFAULT 0,
                    completed_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    options TEXT,
                    status TEXT DEFAULT 'pending'
                )
            """)

        yield db
        db.close_all_connections()

    def test_add_to_processing_queue(self, db_with_queue):
        """add_to_processing_queue() should add entry to queue."""
        rec_id = db_with_queue.add_recording(filename="test.wav")
        queue_id = db_with_queue.add_to_processing_queue(rec_id, "task_123")

        assert queue_id is not None
        assert queue_id > 0

    def test_add_to_processing_queue_duplicate(self, db_with_queue):
        """add_to_processing_queue() should return None for duplicate task_id."""
        rec_id = db_with_queue.add_recording(filename="test.wav")
        db_with_queue.add_to_processing_queue(rec_id, "task_123")

        # Try to add duplicate
        result = db_with_queue.add_to_processing_queue(rec_id, "task_123")

        assert result is None

    def test_update_queue_status(self, db_with_queue):
        """update_queue_status() should update queue entry."""
        rec_id = db_with_queue.add_recording(filename="test.wav")
        db_with_queue.add_to_processing_queue(rec_id, "task_123")

        result = db_with_queue.update_queue_status("task_123", "processing")

        assert result is True

    def test_add_batch_to_processing_queue(self, db_with_queue):
        """add_batch_to_processing_queue() should add batch entries."""
        rec_ids = [
            db_with_queue.add_recording(filename=f"test_{i}.wav")
            for i in range(3)
        ]

        added = db_with_queue.add_batch_to_processing_queue(
            rec_ids,
            "batch_123",
            priority=7
        )

        assert added == 3

    def test_get_batch_status(self, db_with_queue):
        """get_batch_status() should return batch info."""
        rec_ids = [
            db_with_queue.add_recording(filename=f"test_{i}.wav")
            for i in range(2)
        ]

        db_with_queue.add_batch_to_processing_queue(rec_ids, "batch_123")

        status = db_with_queue.get_batch_status("batch_123")

        assert status is not None
        assert status["batch_id"] == "batch_123"
        assert status["total_count"] == 2


@pytest.mark.regression
class TestDatabaseRegressionSuite:
    """Comprehensive regression tests to run before releases."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create a fresh database for each test."""
        from src.database.database import Database

        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        db.create_tables()
        yield db
        db.close_all_connections()

    def test_full_crud_cycle(self, db):
        """Test complete Create-Read-Update-Delete cycle."""
        # Create
        rec_id = db.add_recording(
            filename="cycle_test.wav",
            transcript="Original transcript"
        )
        assert rec_id is not None

        # Read
        recording = db.get_recording(rec_id)
        assert recording["transcript"] == "Original transcript"

        # Update
        db.update_recording(rec_id, transcript="Updated transcript")
        recording = db.get_recording(rec_id)
        assert recording["transcript"] == "Updated transcript"

        # Delete
        db.delete_recording(rec_id)
        assert db.get_recording(rec_id) is None

    def test_large_transcript_handling(self, db):
        """Test handling of large transcripts."""
        large_transcript = "A" * 100000  # 100KB of text

        rec_id = db.add_recording(
            filename="large.wav",
            transcript=large_transcript
        )

        recording = db.get_recording(rec_id)
        assert recording["transcript"] == large_transcript
        assert len(recording["transcript"]) == 100000

    def test_special_characters_in_content(self, db):
        """Test handling of special characters."""
        special_content = "Test with 'quotes', \"double quotes\", and\nnewlines\tand\ttabs"

        rec_id = db.add_recording(
            filename="special.wav",
            transcript=special_content
        )

        recording = db.get_recording(rec_id)
        assert recording["transcript"] == special_content

    def test_unicode_content(self, db):
        """Test handling of unicode characters."""
        unicode_content = "Test with émojis 🏥💊 and ñ, ü, 中文, العربية"

        rec_id = db.add_recording(
            filename="unicode.wav",
            transcript=unicode_content
        )

        recording = db.get_recording(rec_id)
        assert recording["transcript"] == unicode_content

    def test_null_vs_empty_string(self, db):
        """Test distinction between NULL and empty string."""
        # NULL transcript
        rec1 = db.add_recording(filename="null.wav", transcript=None)
        # Empty transcript
        rec2 = db.add_recording(filename="empty.wav", transcript="")

        recording1 = db.get_recording(rec1)
        recording2 = db.get_recording(rec2)

        assert recording1["transcript"] is None
        assert recording2["transcript"] == ""
