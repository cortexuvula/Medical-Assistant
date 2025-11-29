import sqlite3
import datetime
import json
import threading
import logging
from typing import Optional, Dict, List, Any, Union
from contextlib import contextmanager
from managers.data_folder_manager import data_folder_manager
from utils.retry_decorator import db_retry

logger = logging.getLogger(__name__)


class Database:
    """Thread-safe database wrapper using thread-local connections.

    Each thread gets its own connection, preventing race conditions
    when the same Database instance is used across multiple threads.
    """

    def __init__(self, db_path: str = None) -> None:
        """Initialize database connection manager.

        Args:
            db_path: Path to SQLite database file. Defaults to app data folder.
        """
        self.db_path = db_path if db_path else str(data_folder_manager.database_file_path)
        # Thread-local storage for connections
        self._local = threading.local()
        # Lock for connection management
        self._lock = threading.Lock()

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create a connection for the current thread.

        Returns:
            sqlite3.Connection for the current thread
        """
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = self._create_connection()
        return self._local.conn

    def _get_cursor(self) -> sqlite3.Cursor:
        """Get or create a cursor for the current thread.

        Returns:
            sqlite3.Cursor for the current thread
        """
        if not hasattr(self._local, 'cursor') or self._local.cursor is None:
            self._local.cursor = self._get_connection().cursor()
        return self._local.cursor

    @db_retry(max_retries=3, initial_delay=0.1)
    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection with optimized settings.

        Returns:
            Configured sqlite3.Connection
        """
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            check_same_thread=True  # Enforce single-thread per connection
        )
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")  # 30 second busy timeout
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def connection(self):
        """Context manager for database operations.

        Yields:
            Tuple of (connection, cursor) for the current thread

        Example:
            with db.connection() as (conn, cursor):
                cursor.execute("SELECT * FROM recordings")
                results = cursor.fetchall()
        """
        conn = self._get_connection()
        cursor = self._get_cursor()
        try:
            yield conn, cursor
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()

    @contextmanager
    def transaction(self):
        """Context manager for explicit transaction handling.

        Automatically commits on success, rolls back on exception.

        Yields:
            Tuple of (connection, cursor) for the current thread
        """
        conn = self._get_connection()
        cursor = self._get_cursor()
        try:
            yield conn, cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    # Legacy methods for backward compatibility
    @db_retry(max_retries=3, initial_delay=0.1)
    def connect(self) -> None:
        """Establish connection to the database.

        Note: This method is kept for backward compatibility.
        Prefer using the connection() context manager instead.
        """
        # Get or create thread-local connection
        self._get_connection()

    @property
    def conn(self) -> sqlite3.Connection:
        """Get the connection for the current thread.

        Returns:
            sqlite3.Connection for the current thread
        """
        return self._get_connection()

    @property
    def cursor(self) -> sqlite3.Cursor:
        """Get the cursor for the current thread.

        Returns:
            sqlite3.Cursor for the current thread
        """
        return self._get_cursor()

    def disconnect(self) -> None:
        """Close the database connection for the current thread."""
        if hasattr(self._local, 'conn') and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception as e:
                logger.warning(f"Error closing database connection: {e}")
            finally:
                self._local.conn = None
                self._local.cursor = None

    def close_all_connections(self) -> None:
        """Close all thread-local connections.

        Note: This only closes the connection for the calling thread.
        Other threads must close their own connections.
        """
        self.disconnect()
            
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
    
    def get_recordings_by_ids(self, recording_ids: List[int]) -> List[Dict[str, Any]]:
        """Get multiple recordings by their IDs.
        
        Parameters:
        - recording_ids: List of recording IDs to fetch
        
        Returns:
        - List of recording dictionaries
        """
        if not recording_ids:
            return []
            
        self.connect()
        placeholders = ','.join(['?' for _ in recording_ids])
        query = f"SELECT * FROM recordings WHERE id IN ({placeholders})"
        self.cursor.execute(query, recording_ids)
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
    
    def add_batch_to_processing_queue(self, recording_ids: List[int], batch_id: str, 
                                     priority: int = 5, options: Dict[str, Any] = None) -> int:
        """Add multiple recordings to the processing queue as a batch.
        
        Parameters:
        - recording_ids: List of recording IDs to process
        - batch_id: Unique batch identifier
        - priority: Processing priority (0-10, default 5)
        - options: Optional batch processing options
        
        Returns:
        - Number of recordings added to queue
        """
        self.connect()
        added_count = 0
        
        try:
            # Create batch entry
            options_json = json.dumps(options) if options else None
            self.cursor.execute("""
                INSERT INTO batch_processing (batch_id, total_count, options, status)
                VALUES (?, ?, ?, ?)
            """, (batch_id, len(recording_ids), options_json, 'processing'))
            
            # Add each recording to the queue
            for recording_id in recording_ids:
                task_id = f"{batch_id}_{recording_id}"
                try:
                    self.cursor.execute("""
                        INSERT INTO processing_queue (recording_id, task_id, batch_id, priority, status)
                        VALUES (?, ?, ?, ?, ?)
                    """, (recording_id, task_id, batch_id, priority, "queued"))
                    added_count += 1
                except sqlite3.IntegrityError:
                    # Skip if already in queue
                    pass
            
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise e
        finally:
            self.disconnect()
        
        return added_count
    
    def update_batch_status(self, batch_id: str, **kwargs: Any) -> bool:
        """Update batch processing status.
        
        Parameters:
        - batch_id: Batch identifier
        - kwargs: Fields to update (completed_count, failed_count, completed_at, status)
        
        Returns:
        - True if successful, False otherwise
        """
        self.connect()
        
        allowed_fields = ['completed_count', 'failed_count', 'started_at', 'completed_at', 'status']
        update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not update_fields:
            self.disconnect()
            return False
        
        fields = []
        values = []
        for field in update_fields:
            fields.append(f"{field} = ?")
            values.append(update_fields[field])
        
        values.append(batch_id)
        query = f"UPDATE batch_processing SET {', '.join(fields)} WHERE batch_id = ?"
        
        self.cursor.execute(query, values)
        rows_affected = self.cursor.rowcount
        self.conn.commit()
        self.disconnect()
        
        return rows_affected > 0
    
    def get_batch_status(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Get batch processing status.
        
        Parameters:
        - batch_id: Batch identifier
        
        Returns:
        - Batch status dictionary or None if not found
        """
        self.connect()
        self.cursor.execute("""
            SELECT batch_id, total_count, completed_count, failed_count,
                   created_at, started_at, completed_at, options, status
            FROM batch_processing
            WHERE batch_id = ?
        """, (batch_id,))
        
        row = self.cursor.fetchone()
        self.disconnect()
        
        if row:
            columns = ['batch_id', 'total_count', 'completed_count', 'failed_count',
                      'created_at', 'started_at', 'completed_at', 'options', 'status']
            batch_data = dict(zip(columns, row))
            
            # Parse options JSON
            if batch_data['options']:
                batch_data['options'] = json.loads(batch_data['options'])
            
            return batch_data
        
        return None
    
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
    
    def get_failed_recordings(self, limit: int = 100) -> List[Dict]:
        """Get recordings that have failed processing.
        
        Parameters:
        - limit: Maximum number of recordings to return
        
        Returns:
        - List of recording dictionaries with failed status
        """
        self.connect()
        self.cursor.execute("""
            SELECT * FROM recordings 
            WHERE processing_status = 'failed'
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        
        recordings = self.cursor.fetchall()
        self.disconnect()
        
        # Convert to list of dictionaries
        result = []
        for rec in recordings:
            recording_dict = dict(rec)
            # Parse metadata JSON if present
            if recording_dict.get('metadata'):
                try:
                    recording_dict['metadata'] = json.loads(recording_dict['metadata'])
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass  # Leave as string if parsing fails
            result.append(recording_dict)
        
        return result
