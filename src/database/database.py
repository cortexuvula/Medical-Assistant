import sqlite3
import datetime
import json
from typing import Optional, Dict, List, Any, Union
from managers.data_folder_manager import data_folder_manager
from utils.retry_decorator import db_retry

class Database:
    def __init__(self, db_path: str = None) -> None:
        """Initialize database connection"""
        self.db_path = db_path if db_path else str(data_folder_manager.database_file_path)
        self.conn = None
        self.cursor = None
        
    @db_retry(max_retries=3, initial_delay=0.1)
    def connect(self) -> None:
        """Establish connection to the database"""
        self.conn = sqlite3.connect(self.db_path, timeout=30.0)  # 30 second timeout
        self.cursor = self.conn.cursor()
        
    def disconnect(self) -> None:
        """Close the database connection"""
        if self.conn:
            self.conn.close()
            
    def create_tables(self) -> None:
        """Create the recordings table if it doesn't exist"""
        self.connect()
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS recordings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            transcript TEXT,
            soap_note TEXT,
            referral TEXT,
            letter TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        self.conn.commit()
        self.disconnect()
    
    @db_retry(max_retries=3, initial_delay=0.2)
    def add_recording(self, filename: str, transcript: Optional[str] = None, soap_note: Optional[str] = None, 
                     referral: Optional[str] = None, letter: Optional[str] = None, **kwargs) -> int:
        """Add a new recording to the database
        
        Parameters:
        - filename: Path to the recording file
        - transcript: Text transcript of the recording
        - soap_note: Generated SOAP note
        - referral: Generated referral
        - letter: Generated letter
        - kwargs: Additional fields (processing_status, patient_name, etc.)
        
        Returns:
        - ID of the new recording
        """
        self.connect()
        
        # Build fields and values dynamically
        fields = ['filename', 'transcript', 'soap_note', 'referral', 'letter', 'timestamp']
        values = [filename, transcript, soap_note, referral, letter, datetime.datetime.now()]
        
        # Add any extra fields from kwargs
        allowed_extras = ['processing_status', 'patient_name', 'audio_path', 'duration', 'metadata']
        for field in allowed_extras:
            if field in kwargs:
                fields.append(field)
                value = kwargs[field]
                # Handle metadata serialization
                if field == 'metadata' and isinstance(value, dict):
                    value = json.dumps(value)
                values.append(value)
        
        # Build query
        placeholders = ','.join(['?' for _ in fields])
        field_names = ','.join(fields)
        query = f"INSERT INTO recordings ({field_names}) VALUES ({placeholders})"
        
        self.cursor.execute(query, values)
        row_id = self.cursor.lastrowid
        self.conn.commit()
        self.disconnect()
        return row_id
    
    @db_retry(max_retries=3, initial_delay=0.2)
    def update_recording(self, recording_id: int, **kwargs: Any) -> bool:
        """
        Update a recording in the database
        
        Parameters:
        - recording_id: ID of the recording to update
        - kwargs: Fields to update (filename, transcript, soap_note, referral, letter, 
                  processing_status, processing_started_at, processing_completed_at, 
                  error_message, retry_count, patient_name, audio_path, duration, metadata)
        
        Returns:
        - True if successful, False otherwise
        """
        allowed_fields = ['filename', 'transcript', 'soap_note', 'referral', 'letter', 'chat',
                         'processing_status', 'processing_started_at', 'processing_completed_at',
                         'error_message', 'retry_count', 'patient_name', 'audio_path', 
                         'duration', 'metadata']
        
        # Handle metadata serialization if present
        if 'metadata' in kwargs and isinstance(kwargs['metadata'], dict):
            kwargs['metadata'] = json.dumps(kwargs['metadata'])
        
        # Validate field names to prevent any potential injection through kwargs keys
        update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields and k.isidentifier()}
        
        if not update_fields:
            return False
        
        self.connect()
        # Build parameterized query - field names are validated above, values use ? placeholders
        query = "UPDATE recordings SET "
        query += ", ".join([f"{field} = ?" for field in update_fields.keys()])
        query += " WHERE id = ?"
        
        values = list(update_fields.values())
        values.append(recording_id)
        
        self.cursor.execute(query, values)
        rows_affected = self.cursor.rowcount
        self.conn.commit()
        self.disconnect()
        
        return rows_affected > 0
    
    def delete_recording(self, recording_id: int) -> bool:
        """
        Delete a recording from the database
        
        Parameters:
        - recording_id: ID of the recording to delete
        
        Returns:
        - True if successful, False otherwise
        """
        self.connect()
        self.cursor.execute("DELETE FROM recordings WHERE id = ?", (recording_id,))
        rows_affected = self.cursor.rowcount
        self.conn.commit()
        self.disconnect()
        
        return rows_affected > 0
    
    def get_recording(self, recording_id: int) -> Optional[Dict[str, Any]]:
        """Get a recording by ID"""
        self.connect()
        self.cursor.execute("SELECT * FROM recordings WHERE id = ?", (recording_id,))
        recording = self.cursor.fetchone()
        self.disconnect()
        
        if recording:
            columns = ['id', 'filename', 'transcript', 'soap_note', 'referral', 'letter', 'timestamp']
            return dict(zip(columns, recording))
        return None
    
    def get_all_recordings(self) -> List[Dict[str, Any]]:
        """Get all recordings"""
        self.connect()
        self.cursor.execute("SELECT * FROM recordings ORDER BY timestamp DESC")
        recordings = self.cursor.fetchall()
        self.disconnect()
        
        columns = ['id', 'filename', 'transcript', 'soap_note', 'referral', 'letter', 'timestamp']
        return [dict(zip(columns, recording)) for recording in recordings]
        
    def search_recordings(self, search_term: str) -> List[Dict[str, Any]]:
        """Search for recordings containing the search term in any text field
        
        Parameters:
        - search_term: Text to search for in filename, transcript, soap_note, referral, or letter
        
        Returns:
        - List of matching recordings
        """
        self.connect()
        query = """SELECT * FROM recordings 
                 WHERE filename LIKE ? 
                 OR transcript LIKE ? 
                 OR soap_note LIKE ? 
                 OR referral LIKE ? 
                 OR letter LIKE ? 
                 ORDER BY timestamp DESC"""
        search_pattern = f"%{search_term}%"
        params = (search_pattern, search_pattern, search_pattern, search_pattern, search_pattern)
        
        self.cursor.execute(query, params)
        recordings = self.cursor.fetchall()
        self.disconnect()
        
        columns = ['id', 'filename', 'transcript', 'soap_note', 'referral', 'letter', 'timestamp']
        return [dict(zip(columns, recording)) for recording in recordings]
    
    def get_recordings_by_date_range(self, start_date: Union[str, datetime.datetime], end_date: Union[str, datetime.datetime]) -> List[Dict[str, Any]]:
        """Get recordings created within a date range
        
        Parameters:
        - start_date: Start date (datetime object or ISO format string)
        - end_date: End date (datetime object or ISO format string)
        
        Returns:
        - List of recordings within the date range
        """
        if isinstance(start_date, str):
            start_date = datetime.datetime.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = datetime.datetime.fromisoformat(end_date)
            
        # Add one day to end_date to make the range inclusive
        end_date = end_date + datetime.timedelta(days=1)
        
        self.connect()
        self.cursor.execute(
            "SELECT * FROM recordings WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp DESC",
            (start_date.isoformat(), end_date.isoformat())
        )
        recordings = self.cursor.fetchall()
        self.disconnect()
        
        columns = ['id', 'filename', 'transcript', 'soap_note', 'referral', 'letter', 'timestamp']
        return [dict(zip(columns, recording)) for recording in recordings]

    
    # Queue-related methods
    def create_queue_tables(self) -> None:
        """Create queue-related tables if they do not exist."""
        from database.db_queue_schema import QueueDatabaseSchema
        upgrader = QueueDatabaseSchema(self.db_path)
        upgrader.upgrade_schema()
    
    def add_to_processing_queue(self, recording_id: int, task_id: str, priority: int = 5) -> Optional[int]:
        """Add a recording to the processing queue.
        
        Parameters:
        - recording_id: ID of the recording to process
        - task_id: Unique task identifier
        - priority: Processing priority (0-10, default 5)
        
        Returns:
        - Queue entry ID if successful, None otherwise
        """
        self.connect()
        try:
            self.cursor.execute("INSERT INTO processing_queue (recording_id, task_id, priority, status) VALUES (?, ?, ?, ?)", 
                              (recording_id, task_id, priority, "queued"))
            queue_id = self.cursor.lastrowid
            self.conn.commit()
            return queue_id
        except sqlite3.IntegrityError:
            # Task ID already exists
            return None
        finally:
            self.disconnect()
    
    def update_queue_status(self, task_id: str, status: str, **kwargs: Any) -> bool:
        """Update processing queue entry status.
        
        Parameters:
        - task_id: Task identifier
        - status: New status
        - kwargs: Additional fields to update (started_at, completed_at, error_count, last_error, result)
        """
        self.connect()
        
        # Build update query
        fields = ["status = ?"]
        values = [status]
        
        allowed_fields = ["started_at", "completed_at", "error_count", "last_error", "result"]
        for field in allowed_fields:
            if field in kwargs:
                fields.append(f"{field} = ?")
                value = kwargs[field]
                # Serialize result if it is a dict
                if field == "result" and isinstance(value, dict):
                    value = json.dumps(value)
                values.append(value)
        
        values.append(task_id)
        query = f"UPDATE processing_queue SET {', '.join(fields)} WHERE task_id = ?"
        
        self.cursor.execute(query, values)
        rows_affected = self.cursor.rowcount
        self.conn.commit()
        self.disconnect()
        
        return rows_affected > 0
    
    def get_pending_recordings(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recordings that are pending processing."""
        self.connect()
        self.cursor.execute("""
            SELECT r.*, pq.task_id, pq.priority 
            FROM recordings r
            LEFT JOIN processing_queue pq ON r.id = pq.recording_id
            WHERE r.processing_status = "pending" OR r.processing_status IS NULL
            ORDER BY pq.priority DESC, r.timestamp ASC
            LIMIT ?
        """, (limit,))
        
        recordings = self.cursor.fetchall()
        self.disconnect()
        
        # Extended columns including queue info
        columns = ["id", "filename", "transcript", "soap_note", "referral", "letter", 
                  "timestamp", "task_id", "priority"]
        return [dict(zip(columns, recording)) for recording in recordings]
    
    def get_processing_stats(self) -> Dict[str, int]:
        """Get processing queue statistics."""
        self.connect()
        
        stats = {}
        
        # Count by status
        self.cursor.execute("""
            SELECT processing_status, COUNT(*) 
            FROM recordings 
            WHERE processing_status IS NOT NULL
            GROUP BY processing_status
        """)
        
        for status, count in self.cursor.fetchall():
            stats[f"recordings_{status}"] = count
        
        # Queue stats
        self.cursor.execute("""
            SELECT status, COUNT(*) 
            FROM processing_queue 
            GROUP BY status
        """)
        
        for status, count in self.cursor.fetchall():
            stats[f"queue_{status}"] = count
        
        self.disconnect()
        return stats
    
    def clear_all_recordings(self) -> bool:
        """Clear all recordings from the database and delete associated audio files.
        
        Returns:
        - True if successful, False otherwise
        """
        self.connect()
        try:
            # First, get all filenames to delete the audio files
            self.cursor.execute("SELECT filename FROM recordings WHERE filename IS NOT NULL AND filename != ''")
            filenames = [row[0] for row in self.cursor.fetchall()]
            
            # Delete all recordings from database
            self.cursor.execute("DELETE FROM recordings")
            
            # Reset the auto-increment counter
            self.cursor.execute("DELETE FROM sqlite_sequence WHERE name='recordings'")
            
            # Also clear the processing queue if it exists
            try:
                self.cursor.execute("DELETE FROM processing_queue")
                self.cursor.execute("DELETE FROM sqlite_sequence WHERE name='processing_queue'")
            except sqlite3.OperationalError:
                # Table might not exist
                pass
            
            self.conn.commit()
            self.disconnect()
            
            # Delete the audio files
            import os
            import logging
            for filename in filenames:
                if filename and os.path.exists(filename):
                    try:
                        os.remove(filename)
                        logging.info(f"Deleted audio file: {filename}")
                    except Exception as e:
                        logging.warning(f"Failed to delete audio file {filename}: {e}")
            
            return True
        except Exception as e:
            self.disconnect()
            raise e
