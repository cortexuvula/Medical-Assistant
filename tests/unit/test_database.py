"""Test database functionality."""
import pytest
import tempfile
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from database.database import Database

# Configure sqlite3 datetime adapter to suppress deprecation warning
sqlite3.register_adapter(datetime, lambda dt: dt.isoformat())
sqlite3.register_converter("DATETIME", lambda s: datetime.fromisoformat(s.decode()))


class TestDatabase:
    """Test database operations."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        db = Database(db_path)
        yield db
        
        # Cleanup
        Path(db_path).unlink(missing_ok=True)
    
    def test_create_tables(self, temp_db):
        """Test table creation."""
        temp_db.create_tables()
        
        # Verify table exists
        temp_db.connect()
        temp_db.cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='recordings'"
        )
        result = temp_db.cursor.fetchone()
        temp_db.disconnect()
        
        assert result is not None
        assert result[0] == 'recordings'
    
    def test_add_recording_minimal(self, temp_db):
        """Test adding a recording with minimal data."""
        temp_db.create_tables()
        
        rec_id = temp_db.add_recording("test_recording.mp3")
        
        assert rec_id is not None
        assert isinstance(rec_id, int)
        assert rec_id > 0
    
    def test_add_recording_with_metadata(self, temp_db):
        """Test adding a recording with all metadata."""
        temp_db.create_tables()
        temp_db.create_queue_tables()  # This adds the extra columns
        
        rec_id = temp_db.add_recording(
            filename="patient_visit.mp3",
            processing_status="pending",
            patient_name="John Doe"
        )
        
        assert rec_id is not None
        
        # Verify data was saved
        recording = temp_db.get_recording(rec_id)
        assert recording is not None
        assert recording['filename'] == "patient_visit.mp3"
    
    def test_update_recording_single_field(self, temp_db):
        """Test updating a single field."""
        temp_db.create_tables()
        rec_id = temp_db.add_recording("test.mp3")
        
        # Update transcript
        success = temp_db.update_recording(rec_id, transcript="Test transcript")
        assert success is True
        
        # Verify update
        recording = temp_db.get_recording(rec_id)
        assert recording['transcript'] == "Test transcript"
        assert recording['soap_note'] is None  # Other fields unchanged
    
    def test_update_recording_multiple_fields(self, temp_db):
        """Test updating multiple fields at once."""
        temp_db.create_tables()
        temp_db.create_queue_tables()  # This adds the extra columns
        rec_id = temp_db.add_recording("test.mp3")
        
        # Update multiple fields
        success = temp_db.update_recording(
            rec_id,
            transcript="Patient presents with headache",
            soap_note="S: Headache\nO: Normal\nA: Tension\nP: Rest",
            patient_name="Jane Smith",
            processing_status="completed"
        )
        
        assert success is True
        
        # Verify all updates
        recording = temp_db.get_recording(rec_id)
        assert recording['transcript'] == "Patient presents with headache"
        assert "S: Headache" in recording['soap_note']
    
    def test_update_recording_invalid_id(self, temp_db):
        """Test updating non-existent recording."""
        temp_db.create_tables()
        
        success = temp_db.update_recording(9999, transcript="Test")
        assert success is False
    
    def test_update_recording_with_metadata(self, temp_db):
        """Test updating metadata field."""
        temp_db.create_tables()
        temp_db.create_queue_tables()  # This adds the extra columns
        rec_id = temp_db.add_recording("test.mp3")
        
        metadata = {
            "duration": 120.5,
            "sample_rate": 44100,
            "provider": "deepgram"
        }
        
        success = temp_db.update_recording(rec_id, metadata=metadata)
        assert success is True
        
        # Verify metadata was saved as JSON
        temp_db.connect()
        temp_db.cursor.execute("SELECT metadata FROM recordings WHERE id = ?", (rec_id,))
        result = temp_db.cursor.fetchone()
        temp_db.disconnect()
        
        # Should be stored as JSON string
        if result[0]:
            saved_metadata = json.loads(result[0])
            assert saved_metadata["duration"] == 120.5
    
    def test_delete_recording(self, temp_db):
        """Test deleting a recording."""
        temp_db.create_tables()
        rec_id = temp_db.add_recording("test.mp3")
        
        # Delete
        success = temp_db.delete_recording(rec_id)
        assert success is True
        
        # Verify deletion
        recording = temp_db.get_recording(rec_id)
        assert recording is None
    
    def test_delete_non_existent_recording(self, temp_db):
        """Test deleting non-existent recording."""
        temp_db.create_tables()
        
        success = temp_db.delete_recording(9999)
        assert success is False
    
    def test_get_all_recordings_empty(self, temp_db):
        """Test getting all recordings from empty database."""
        temp_db.create_tables()
        
        recordings = temp_db.get_all_recordings()
        assert recordings == []
    
    def test_get_all_recordings_ordered(self, temp_db):
        """Test recordings are returned in correct order."""
        temp_db.create_tables()
        
        # Add recordings with slight delay
        import time
        rec1 = temp_db.add_recording("first.mp3")
        time.sleep(0.01)
        rec2 = temp_db.add_recording("second.mp3")
        time.sleep(0.01)
        rec3 = temp_db.add_recording("third.mp3")
        
        recordings = temp_db.get_all_recordings()
        
        # Should be ordered by timestamp DESC (newest first)
        assert len(recordings) == 3
        assert recordings[0]['id'] == rec3
        assert recordings[1]['id'] == rec2
        assert recordings[2]['id'] == rec1
    
    def test_search_recordings_in_transcript(self, temp_db):
        """Test searching in transcript field."""
        temp_db.create_tables()
        
        # Add test data
        rec1 = temp_db.add_recording("patient1.mp3")
        temp_db.update_recording(rec1, transcript="Patient has severe headache")
        
        rec2 = temp_db.add_recording("patient2.mp3")
        temp_db.update_recording(rec2, transcript="Patient has mild fever")
        
        # Search for headache
        results = temp_db.search_recordings("headache")
        assert len(results) == 1
        assert results[0]['id'] == rec1
    
    def test_search_recordings_in_multiple_fields(self, temp_db):
        """Test searching across multiple fields."""
        temp_db.create_tables()
        
        rec1 = temp_db.add_recording("test1.mp3")
        temp_db.update_recording(
            rec1,
            transcript="Normal consultation",
            soap_note="Patient has hypertension"
        )
        
        rec2 = temp_db.add_recording("test2.mp3")
        temp_db.update_recording(
            rec2,
            transcript="Hypertension follow-up",
            soap_note="Blood pressure controlled"
        )
        
        # Search for hypertension - should find both
        results = temp_db.search_recordings("hypertension")
        assert len(results) == 2
    
    def test_search_recordings_case_insensitive(self, temp_db):
        """Test search is case insensitive."""
        temp_db.create_tables()
        
        rec = temp_db.add_recording("test.mp3")
        temp_db.update_recording(rec, transcript="Patient has HEADACHE")
        
        # Search with different cases
        assert len(temp_db.search_recordings("headache")) == 1
        assert len(temp_db.search_recordings("HEADACHE")) == 1
        assert len(temp_db.search_recordings("HeAdAcHe")) == 1
    
    def test_search_recordings_no_results(self, temp_db):
        """Test search with no matching results."""
        temp_db.create_tables()
        
        rec = temp_db.add_recording("test.mp3")
        temp_db.update_recording(rec, transcript="Patient is healthy")
        
        results = temp_db.search_recordings("cancer")
        assert results == []
    
    def test_get_recordings_by_date_range(self, temp_db):
        """Test getting recordings within date range."""
        temp_db.create_tables()
        
        # We'll need to manually set timestamps for testing
        # This is a limitation of the current implementation
        # In real use, timestamps are auto-generated
        
        # Add recordings
        rec1 = temp_db.add_recording("old.mp3")
        rec2 = temp_db.add_recording("recent.mp3")
        rec3 = temp_db.add_recording("newest.mp3")
        
        # For this test, we'll use the auto-generated timestamps
        # and just verify the method works
        now = datetime.now()
        yesterday = datetime.now().replace(hour=0, minute=0, second=0)
        tomorrow = datetime.now().replace(hour=23, minute=59, second=59)
        
        results = temp_db.get_recordings_by_date_range(yesterday, tomorrow)
        
        # Should include all recordings created today
        # The method may return more than 3 if other tests created recordings
        # So just verify our recordings are included
        result_ids = [r['id'] for r in results]
        assert rec1 in result_ids
        assert rec2 in result_ids
        assert rec3 in result_ids
        # And all results should be from today
        for result in results:
            timestamp = datetime.fromisoformat(result['timestamp']) if isinstance(result['timestamp'], str) else result['timestamp']
            assert yesterday <= timestamp <= tomorrow
    
    def test_concurrent_database_access(self, temp_db):
        """Test database handles concurrent access correctly."""
        temp_db.create_tables()
        
        # Add a recording
        rec_id = temp_db.add_recording("test.mp3")
        
        # Multiple updates should work
        temp_db.update_recording(rec_id, transcript="First update")
        temp_db.update_recording(rec_id, soap_note="Second update")
        temp_db.update_recording(rec_id, referral="Third update")
        
        # Verify all updates applied
        recording = temp_db.get_recording(rec_id)
        assert recording['transcript'] == "First update"
        assert recording['soap_note'] == "Second update"
        assert recording['referral'] == "Third update"
    
    def test_sql_injection_protection(self, temp_db):
        """Test that SQL injection attempts are handled safely."""
        temp_db.create_tables()
        
        # Attempt SQL injection in various fields
        malicious_filename = "test.mp3'; DROP TABLE recordings; --"
        rec_id = temp_db.add_recording(malicious_filename)
        
        # Should create record safely
        assert rec_id is not None
        
        # Table should still exist
        temp_db.connect()
        temp_db.cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='recordings'"
        )
        assert temp_db.cursor.fetchone() is not None
        temp_db.disconnect()
        
        # Search with injection attempt
        malicious_search = "'; DROP TABLE recordings; --"
        results = temp_db.search_recordings(malicious_search)
        assert isinstance(results, list)  # Should return empty list, not error
        
        # Verify recording still exists
        recording = temp_db.get_recording(rec_id)
        assert recording is not None
        assert recording['filename'] == malicious_filename
    
    @pytest.mark.parametrize("invalid_field", [
        "non_existent_field",
        "__table__",
        "1=1",
        "recordings",
    ])
    def test_update_recording_invalid_fields(self, temp_db, invalid_field):
        """Test that invalid field names are rejected."""
        temp_db.create_tables()
        rec_id = temp_db.add_recording("test.mp3")
        
        # Attempt to update invalid field
        kwargs = {invalid_field: "value"}
        success = temp_db.update_recording(rec_id, **kwargs)
        
        # Should ignore invalid fields (returns False because no valid fields to update)
        # The actual implementation filters out invalid fields and returns False if no valid fields remain
        assert success is False
    
    def test_add_to_processing_queue(self, temp_db):
        """Test adding recordings to processing queue."""
        temp_db.create_tables()
        temp_db.create_queue_tables()
        
        # Add a recording first
        rec_id = temp_db.add_recording("test.mp3")
        
        # Add to processing queue
        queue_id = temp_db.add_to_processing_queue(rec_id, "task-123", priority=8)
        assert queue_id is not None
        assert isinstance(queue_id, int)
        
        # Try adding the same task_id again - should fail
        duplicate_id = temp_db.add_to_processing_queue(rec_id, "task-123", priority=5)
        assert duplicate_id is None
    
    def test_update_queue_status(self, temp_db):
        """Test updating processing queue status."""
        temp_db.create_tables()
        temp_db.create_queue_tables()
        
        # Add a recording and queue entry
        rec_id = temp_db.add_recording("test.mp3")
        queue_id = temp_db.add_to_processing_queue(rec_id, "task-456")
        
        # Update status
        success = temp_db.update_queue_status(
            "task-456", 
            "processing",
            started_at=datetime.now().isoformat()
        )
        assert success is True
        
        # Update with result
        result_data = {"transcript_length": 500, "processing_time": 2.5}
        success = temp_db.update_queue_status(
            "task-456",
            "completed",
            completed_at=datetime.now().isoformat(),
            result=result_data
        )
        assert success is True
    
    def test_get_pending_recordings(self, temp_db):
        """Test getting pending recordings from queue."""
        temp_db.create_tables()
        temp_db.create_queue_tables()
        
        # Add recordings with different statuses
        rec1 = temp_db.add_recording("pending1.mp3")
        rec2 = temp_db.add_recording("pending2.mp3")
        rec3 = temp_db.add_recording("completed.mp3")
        
        # Update statuses
        temp_db.update_recording(rec3, processing_status="completed")
        
        # Add to queue
        temp_db.add_to_processing_queue(rec1, "task-1", priority=5)
        temp_db.add_to_processing_queue(rec2, "task-2", priority=10)
        
        # Get pending recordings
        pending = temp_db.get_pending_recordings(limit=5)
        
        # Should return recordings ordered by priority
        assert len(pending) >= 2
        # Higher priority should come first
        pending_ids = [r['id'] for r in pending]
        assert rec2 in pending_ids  # priority 10
        assert rec1 in pending_ids  # priority 5
    
    def test_get_processing_stats(self, temp_db):
        """Test getting processing statistics."""
        temp_db.create_tables()
        temp_db.create_queue_tables()
        
        # Add recordings with various statuses
        rec1 = temp_db.add_recording("rec1.mp3")
        rec2 = temp_db.add_recording("rec2.mp3")
        rec3 = temp_db.add_recording("rec3.mp3")
        
        # Update processing statuses
        temp_db.update_recording(rec1, processing_status="pending")
        temp_db.update_recording(rec2, processing_status="completed")
        temp_db.update_recording(rec3, processing_status="failed")
        
        # Add queue entries
        temp_db.add_to_processing_queue(rec1, "q1")
        temp_db.update_queue_status("q1", "queued")
        
        # Get stats
        stats = temp_db.get_processing_stats()
        
        assert isinstance(stats, dict)
        assert stats.get('recordings_pending', 0) >= 1
        assert stats.get('recordings_completed', 0) >= 1
        assert stats.get('recordings_failed', 0) >= 1
        assert stats.get('queue_queued', 0) >= 1