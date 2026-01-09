import sqlite3
import datetime
import json
import threading
import logging
import re
from typing import Optional, Dict, List, Any, Union, Set, FrozenSet
from contextlib import contextmanager
from managers.data_folder_manager import data_folder_manager
from utils.retry_decorator import db_retry

# Import centralized schema definitions
from database.schema import (
    RecordingSchema, QueueSchema, BatchSchema,
    RECORDING_FIELDS, RECORDING_INSERT_FIELDS, RECORDING_UPDATE_FIELDS,
    QUEUE_UPDATE_FIELDS, BATCH_UPDATE_FIELDS
)

logger = logging.getLogger(__name__)

# Valid SQL identifier pattern (alphanumeric and underscore, must start with letter/underscore)
_VALID_IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


def _validate_field_name(field: str, allowlist: FrozenSet[str], context: str = "query") -> str:
    """Validate a field name against an allowlist.

    Args:
        field: The field name to validate
        allowlist: Set of allowed field names
        context: Description of where this field is being used (for error messages)

    Returns:
        The validated field name

    Raises:
        ValueError: If the field name is not in the allowlist or has invalid format
    """
    if not field:
        raise ValueError(f"Empty field name not allowed in {context}")

    if not isinstance(field, str):
        raise ValueError(f"Field name must be a string in {context}, got {type(field).__name__}")

    # Check against allowlist first (most important security check)
    if field not in allowlist:
        raise ValueError(f"Field '{field}' is not allowed in {context}. Allowed fields: {sorted(allowlist)}")

    # Additional validation: ensure it matches valid SQL identifier pattern
    # This is defense-in-depth even though allowlist should catch everything
    if not _VALID_IDENTIFIER_PATTERN.match(field):
        raise ValueError(f"Field '{field}' has invalid format in {context}")

    return field


def _validate_fields(fields: List[str], allowlist: FrozenSet[str], context: str = "query") -> List[str]:
    """Validate multiple field names against an allowlist.

    Args:
        fields: List of field names to validate
        allowlist: Set of allowed field names
        context: Description of where these fields are being used

    Returns:
        List of validated field names

    Raises:
        ValueError: If any field name is invalid
    """
    return [_validate_field_name(f, allowlist, context) for f in fields]


class Database:
    """Thread-safe database wrapper using thread-local connections with automatic cleanup.

    Each thread gets its own connection, preventing race conditions
    when the same Database instance is used across multiple threads.

    Connection Lifecycle:
    - Connections are created lazily when first accessed by a thread
    - Connections are tracked and can be cleaned up via close_all_connections()
    - The __del__ method attempts cleanup when the Database instance is garbage collected
    - For best practice, explicitly call close_all_connections() during application shutdown
    """

    # Class-level registry of all Database instances for global cleanup
    _instances: List['Database'] = []
    _instances_lock = threading.Lock()

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
        # Track all thread IDs that have connections (for cleanup)
        self._thread_connections: Dict[int, sqlite3.Connection] = {}
        # Flag to indicate if this instance has been closed
        self._closed = False

        # Register this instance for global cleanup
        with Database._instances_lock:
            Database._instances.append(self)

        # Ensure migrations are applied
        self._ensure_migrations()

    def _ensure_migrations(self):
        """Ensure all database migrations are applied."""
        try:
            from database.db_migrations import get_migration_manager, DatabaseError
            migration_manager = get_migration_manager()
            pending = migration_manager.get_pending_migrations()
            if pending:
                logging.info(f"Found {len(pending)} pending database migrations")
                migration_manager.migrate()
                logging.info("Database migrations applied successfully")
        except Exception as e:
            logging.error(f"Failed to apply database migrations: {e}")
            # Don't raise - allow app to continue even if migrations fail

        # Ensure critical columns exist (fixes cases where migration recorded but column missing)
        self._ensure_critical_columns()

    def _ensure_critical_columns(self):
        """Ensure critical columns exist in the recordings table."""
        critical_columns = [
            ("chat", "TEXT"),
            ("duration_seconds", "REAL"),
            ("file_size_bytes", "INTEGER"),
            ("stt_provider", "TEXT"),
            ("ai_provider", "TEXT"),
            ("tags", "TEXT"),
        ]

        try:
            conn = self._get_connection()
            cursor = conn.execute("PRAGMA table_info(recordings)")
            existing_columns = {row[1] for row in cursor.fetchall()}

            for column_name, column_type in critical_columns:
                if column_name not in existing_columns:
                    logging.info(f"Adding missing column '{column_name}' to recordings table")
                    try:
                        conn.execute(f"ALTER TABLE recordings ADD COLUMN {column_name} {column_type}")
                        conn.commit()
                        logging.info(f"Successfully added column '{column_name}'")
                    except sqlite3.OperationalError as e:
                        if "duplicate column" not in str(e).lower():
                            logging.error(f"Failed to add column '{column_name}': {e}")
        except Exception as e:
            logging.error(f"Error checking/adding critical columns: {e}")

    def __del__(self):
        """Destructor to clean up connections when Database instance is garbage collected.

        Note: This is a best-effort cleanup. For reliable cleanup, explicitly call
        close_all_connections() during application shutdown.
        """
        try:
            self._cleanup_all_connections()
        except (sqlite3.Error, OSError, RuntimeError):
            # Suppress database/OS errors during garbage collection
            # These are expected if the interpreter is shutting down
            pass

    def __enter__(self):
        """Context manager entry - returns self for use in with statements."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - closes all connections."""
        self.close_all_connections()
        return False  # Don't suppress exceptions

    def _cleanup_all_connections(self) -> None:
        """Internal method to clean up all tracked connections.

        This closes all connections that were opened by any thread.
        Thread-safe and idempotent.
        """
        if self._closed:
            return

        with self._lock:
            if self._closed:
                return

            self._closed = True

            # Close all tracked connections
            for thread_id, conn in list(self._thread_connections.items()):
                try:
                    if conn is not None:
                        conn.close()
                        logger.debug(f"Closed database connection for thread {thread_id}")
                except Exception as e:
                    logger.warning(f"Error closing connection for thread {thread_id}: {e}")

            self._thread_connections.clear()

            # Clear thread-local storage for current thread
            if hasattr(self._local, 'conn'):
                self._local.conn = None
            if hasattr(self._local, 'cursor'):
                self._local.cursor = None

        # Unregister this instance
        with Database._instances_lock:
            if self in Database._instances:
                Database._instances.remove(self)

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create a connection for the current thread.

        Returns:
            sqlite3.Connection for the current thread

        Raises:
            RuntimeError: If the database has been closed
        """
        if self._closed:
            raise RuntimeError("Database has been closed")

        if not hasattr(self._local, 'conn') or self._local.conn is None:
            conn = self._create_connection()
            self._local.conn = conn

            # Track this connection for cleanup
            thread_id = threading.current_thread().ident
            with self._lock:
                self._thread_connections[thread_id] = conn

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
        thread_id = threading.current_thread().ident
        thread_name = threading.current_thread().name

        # MONITORING: Log connection creation for leak detection
        current_count = len(self._thread_connections)
        if current_count > 10:
            logger.warning(
                f"High connection count ({current_count}) detected. "
                f"Creating new connection for thread {thread_id} ({thread_name}). "
                "This may indicate a connection leak."
            )
        else:
            logger.debug(f"Creating database connection for thread {thread_id} ({thread_name})")

        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            check_same_thread=True  # Enforce single-thread per connection
        )
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")  # 30 second busy timeout
        conn.execute("PRAGMA foreign_keys=ON")

        logger.debug(f"Database connection created for thread {thread_id}. Total connections: {current_count + 1}")
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
        except BaseException:
            # Catch all exceptions including KeyboardInterrupt to ensure rollback
            # Re-raise after rollback to preserve original exception
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
        except BaseException:
            # Catch all exceptions including KeyboardInterrupt to ensure rollback
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
        """Close the database connection for the current thread.

        This removes the connection from tracking and closes it.
        Safe to call multiple times.
        """
        thread_id = threading.current_thread().ident

        if hasattr(self._local, 'conn') and self._local.conn is not None:
            try:
                self._local.conn.close()
                logger.debug(f"Disconnected database connection for thread {thread_id}")
            except Exception as e:
                logger.warning(f"Error closing database connection: {e}")
            finally:
                self._local.conn = None
                self._local.cursor = None

                # Remove from tracked connections
                with self._lock:
                    self._thread_connections.pop(thread_id, None)

    def close_all_connections(self) -> None:
        """Close ALL connections across all threads.

        This method closes connections for all threads that have used this
        Database instance, not just the calling thread. Use this during
        application shutdown for complete cleanup.

        After calling this method, the Database instance should not be used.
        """
        self._cleanup_all_connections()

    def get_connection_count(self) -> int:
        """Get the number of active tracked connections.

        Returns:
            Number of connections currently tracked (may include stale connections
            from terminated threads).
        """
        with self._lock:
            return len(self._thread_connections)

    def cleanup_stale_connections(self) -> int:
        """Clean up connections from threads that are no longer alive.

        This method identifies connections from threads that have terminated
        and closes them. Useful for long-running applications.

        Returns:
            Number of stale connections that were cleaned up.
        """
        if self._closed:
            return 0

        cleaned = 0
        current_threads = {t.ident for t in threading.enumerate()}

        with self._lock:
            stale_thread_ids = [
                tid for tid in self._thread_connections.keys()
                if tid not in current_threads
            ]

            for thread_id in stale_thread_ids:
                conn = self._thread_connections.pop(thread_id, None)
                if conn is not None:
                    try:
                        conn.close()
                        cleaned += 1
                        logger.debug(f"Cleaned up stale connection from thread {thread_id}")
                    except Exception as e:
                        logger.warning(f"Error closing stale connection: {e}")

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} stale database connection(s)")

        return cleaned

    @classmethod
    def cleanup_all_instances(cls) -> None:
        """Class method to clean up all Database instances.

        Call this during application shutdown to ensure all database
        connections are properly closed.
        """
        with cls._instances_lock:
            for instance in list(cls._instances):
                try:
                    instance._cleanup_all_connections()
                except Exception as e:
                    logger.warning(f"Error during global database cleanup: {e}")
            
    def create_tables(self) -> None:
        """Create the recordings table if it doesn't exist.

        This creates a table with all columns used by SELECT_COLUMNS to ensure
        queries work correctly. Additional columns may be added by migrations.
        """
        with self.connection() as (conn, cursor):
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS recordings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                transcript TEXT,
                soap_note TEXT,
                referral TEXT,
                letter TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                processing_status TEXT DEFAULT 'pending',
                patient_name TEXT
            )
            ''')
    
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

        Raises:
        - ValueError: If any field name in kwargs is not in the allowlist
        """
        # Start with core fields (these are hardcoded and safe)
        fields = ['filename', 'transcript', 'soap_note', 'referral', 'letter', 'timestamp']
        values = [filename, transcript, soap_note, referral, letter, datetime.datetime.now()]

        # Add any extra fields from kwargs - only if they pass allowlist validation
        for field in kwargs:
            # Validate against allowlist - raises ValueError if invalid
            _validate_field_name(field, RECORDING_INSERT_FIELDS, "add_recording")

            # Skip core fields that are already added
            if field in ('filename', 'transcript', 'soap_note', 'referral', 'letter', 'timestamp'):
                continue

            fields.append(field)
            value = kwargs[field]
            # Handle metadata serialization
            if field == 'metadata' and isinstance(value, dict):
                value = json.dumps(value)
            values.append(value)

        # Validate all fields before building query (defense in depth)
        validated_fields = _validate_fields(fields, RECORDING_INSERT_FIELDS, "add_recording")

        # Build query with validated field names
        placeholders = ','.join(['?' for _ in validated_fields])
        field_names = ','.join(validated_fields)
        query = f"INSERT INTO recordings ({field_names}) VALUES ({placeholders})"

        with self.connection() as (conn, cursor):
            cursor.execute(query, values)
            return cursor.lastrowid
    
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
        # Handle metadata serialization if present
        if 'metadata' in kwargs and isinstance(kwargs['metadata'], dict):
            kwargs['metadata'] = json.dumps(kwargs['metadata'])

        # Filter to only allowed fields and validate each one
        update_fields = {}
        for field, value in kwargs.items():
            if field in RECORDING_UPDATE_FIELDS:
                # Validate the field name (defense in depth)
                _validate_field_name(field, RECORDING_UPDATE_FIELDS, "update_recording")
                update_fields[field] = value

        if not update_fields:
            return False

        # Build parameterized query with validated field names
        validated_field_names = list(update_fields.keys())
        query = "UPDATE recordings SET "
        query += ", ".join([f"{field} = ?" for field in validated_field_names])
        query += " WHERE id = ?"

        values = list(update_fields.values())
        values.append(recording_id)

        with self.connection() as (conn, cursor):
            cursor.execute(query, values)
            return cursor.rowcount > 0
    
    def delete_recording(self, recording_id: int) -> bool:
        """
        Delete a recording from the database

        Parameters:
        - recording_id: ID of the recording to delete

        Returns:
        - True if successful, False otherwise
        """
        with self.connection() as (conn, cursor):
            cursor.execute("DELETE FROM recordings WHERE id = ?", (recording_id,))
            return cursor.rowcount > 0
    
    def get_recording(self, recording_id: int) -> Optional[Dict[str, Any]]:
        """Get a recording by ID"""
        with self.connection() as (conn, cursor):
            # Use explicit column selection to guarantee order matches schema
            columns = ', '.join(RecordingSchema.SELECT_COLUMNS)
            cursor.execute(f"SELECT {columns} FROM recordings WHERE id = ?", (recording_id,))
            recording = cursor.fetchone()

            if recording:
                return RecordingSchema.row_to_dict(recording, RecordingSchema.SELECT_COLUMNS)
            return None
    
    def get_all_recordings(self) -> List[Dict[str, Any]]:
        """Get all recordings"""
        with self.connection() as (conn, cursor):
            # Use explicit column selection to guarantee order matches schema
            columns = ', '.join(RecordingSchema.SELECT_COLUMNS)
            cursor.execute(f"SELECT {columns} FROM recordings ORDER BY timestamp DESC")
            recordings = cursor.fetchall()

            return [RecordingSchema.row_to_dict(r, RecordingSchema.SELECT_COLUMNS) for r in recordings]

    def get_recordings_paginated(
        self,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "timestamp",
        descending: bool = True
    ) -> List[Dict[str, Any]]:
        """Get recordings with efficient SQL-level pagination.

        This is more efficient than get_all_recordings() for large datasets
        as it only fetches the required rows from the database.

        Args:
            limit: Maximum number of recordings to return
            offset: Number of recordings to skip
            order_by: Column to order by (must be a valid column name)
            descending: If True, order descending (newest first)

        Returns:
            List of recording dictionaries
        """
        # Validate order_by column to prevent SQL injection
        valid_columns = {"id", "timestamp", "filename", "duration"}
        if order_by not in valid_columns:
            order_by = "timestamp"  # Default to safe value

        order_direction = "DESC" if descending else "ASC"

        # Use explicit column selection to guarantee order matches schema
        columns = ', '.join(RecordingSchema.SELECT_COLUMNS)
        query = f"SELECT {columns} FROM recordings ORDER BY {order_by} {order_direction} LIMIT ? OFFSET ?"

        with self.connection() as (conn, cursor):
            cursor.execute(query, (limit, offset))
            recordings = cursor.fetchall()

            return [RecordingSchema.row_to_dict(r, RecordingSchema.SELECT_COLUMNS) for r in recordings]

    def get_recordings_lightweight(
        self,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "timestamp",
        descending: bool = True
    ) -> List[Dict[str, Any]]:
        """Get recordings with minimal columns for UI list views.

        This method fetches only essential columns (id, filename, patient_name,
        timestamp, duration, processing_status) avoiding large text fields like
        transcript, soap_note, referral, and letter. Use this for displaying
        recording lists where full content isn't needed.

        Args:
            limit: Maximum number of recordings to return
            offset: Number of recordings to skip
            order_by: Column to order by (must be a valid column name)
            descending: If True, order descending (newest first)

        Returns:
            List of lightweight recording dictionaries

        Performance:
            Compared to get_all_recordings() or get_recordings_paginated(),
            this method transfers 50-100x less data per record.
        """
        # Validate order_by column to prevent SQL injection
        valid_columns = {"id", "timestamp", "filename", "duration", "patient_name", "processing_status"}
        if order_by not in valid_columns:
            order_by = "timestamp"  # Default to safe value

        order_direction = "DESC" if descending else "ASC"

        # Use lightweight columns that exclude large text fields
        columns = ', '.join(RecordingSchema.LIGHTWEIGHT_COLUMNS)

        # Also compute has_soap and has_referral as derived columns
        query = f"""
            SELECT {columns},
                   CASE WHEN soap_note IS NOT NULL AND soap_note != '' THEN 1 ELSE 0 END as has_soap,
                   CASE WHEN referral IS NOT NULL AND referral != '' THEN 1 ELSE 0 END as has_referral
            FROM recordings
            ORDER BY {order_by} {order_direction}
            LIMIT ? OFFSET ?
        """

        with self.connection() as (conn, cursor):
            cursor.execute(query, (limit, offset))
            recordings = cursor.fetchall()

            # Map results to dictionaries with the extra derived columns
            result = []
            extended_columns = RecordingSchema.LIGHTWEIGHT_COLUMNS + ('has_soap', 'has_referral')
            for r in recordings:
                record = dict(zip(extended_columns, r))
                # Convert boolean flags to Python bools
                record['has_soap'] = bool(record.get('has_soap', 0))
                record['has_referral'] = bool(record.get('has_referral', 0))
                result.append(record)

            return result

    def get_recordings_by_ids(self, recording_ids: List[int]) -> List[Dict[str, Any]]:
        """Get multiple recordings by their IDs.

        Parameters:
        - recording_ids: List of recording IDs to fetch

        Returns:
        - List of recording dictionaries
        """
        if not recording_ids:
            return []

        # Use explicit column selection to guarantee order matches schema
        columns = ', '.join(RecordingSchema.SELECT_COLUMNS)
        placeholders = ','.join(['?' for _ in recording_ids])
        query = f"SELECT {columns} FROM recordings WHERE id IN ({placeholders})"

        with self.connection() as (conn, cursor):
            cursor.execute(query, recording_ids)
            recordings = cursor.fetchall()

            return [RecordingSchema.row_to_dict(r, RecordingSchema.SELECT_COLUMNS) for r in recordings]
        
    def search_recordings(self, search_term: str) -> List[Dict[str, Any]]:
        """Search for recordings containing the search term in any text field

        Parameters:
        - search_term: Text to search for in filename, transcript, soap_note, referral, or letter

        Returns:
        - List of matching recordings
        """
        # Use explicit column selection to guarantee order matches schema
        columns = ', '.join(RecordingSchema.SELECT_COLUMNS)
        query = f"""SELECT {columns} FROM recordings
                 WHERE filename LIKE ?
                 OR transcript LIKE ?
                 OR soap_note LIKE ?
                 OR referral LIKE ?
                 OR letter LIKE ?
                 ORDER BY timestamp DESC"""
        search_pattern = f"%{search_term}%"
        params = (search_pattern, search_pattern, search_pattern, search_pattern, search_pattern)

        with self.connection() as (conn, cursor):
            cursor.execute(query, params)
            recordings = cursor.fetchall()

            return [RecordingSchema.row_to_dict(r, RecordingSchema.SELECT_COLUMNS) for r in recordings]
    
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

        # Use explicit column selection to guarantee order matches schema
        columns = ', '.join(RecordingSchema.SELECT_COLUMNS)

        with self.connection() as (conn, cursor):
            cursor.execute(
                f"SELECT {columns} FROM recordings WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp DESC",
                (start_date.isoformat(), end_date.isoformat())
            )
            recordings = cursor.fetchall()

            return [RecordingSchema.row_to_dict(r, RecordingSchema.SELECT_COLUMNS) for r in recordings]

    
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
        try:
            with self.connection() as (conn, cursor):
                cursor.execute(
                    "INSERT INTO processing_queue (recording_id, task_id, priority, status) VALUES (?, ?, ?, ?)",
                    (recording_id, task_id, priority, "queued")
                )
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Task ID already exists
            return None
    
    def update_queue_status(self, task_id: str, status: str, **kwargs: Any) -> bool:
        """Update processing queue entry status.

        Parameters:
        - task_id: Task identifier
        - status: New status
        - kwargs: Additional fields to update (started_at, completed_at, error_count, last_error, result)
        """
        # Build update query - 'status' is a hardcoded field name (safe)
        field_assignments = ["status = ?"]
        values = [status]

        # Validate and add additional fields from kwargs
        for field in kwargs:
            if field in QUEUE_UPDATE_FIELDS:
                # Validate field name against allowlist
                _validate_field_name(field, QUEUE_UPDATE_FIELDS, "update_queue_status")
                field_assignments.append(f"{field} = ?")
                value = kwargs[field]
                # Serialize result if it is a dict
                if field == "result" and isinstance(value, dict):
                    value = json.dumps(value)
                values.append(value)

        values.append(task_id)
        query = f"UPDATE processing_queue SET {', '.join(field_assignments)} WHERE task_id = ?"

        with self.connection() as (conn, cursor):
            cursor.execute(query, values)
            return cursor.rowcount > 0
    
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
        added_count = 0
        options_json = json.dumps(options) if options else None

        with self.transaction() as (conn, cursor):
            # Create batch entry
            cursor.execute("""
                INSERT INTO batch_processing (batch_id, total_count, options, status)
                VALUES (?, ?, ?, ?)
            """, (batch_id, len(recording_ids), options_json, 'processing'))

            # Add each recording to the queue
            for recording_id in recording_ids:
                task_id = f"{batch_id}_{recording_id}"
                try:
                    cursor.execute("""
                        INSERT INTO processing_queue (recording_id, task_id, batch_id, priority, status)
                        VALUES (?, ?, ?, ?, ?)
                    """, (recording_id, task_id, batch_id, priority, "queued"))
                    added_count += 1
                except sqlite3.IntegrityError:
                    # Skip if already in queue
                    pass

        return added_count
    
    def update_batch_status(self, batch_id: str, **kwargs: Any) -> bool:
        """Update batch processing status.

        Parameters:
        - batch_id: Batch identifier
        - kwargs: Fields to update (completed_count, failed_count, completed_at, status)

        Returns:
        - True if successful, False otherwise
        """
        # Filter and validate fields against allowlist
        update_fields = {}
        for field, value in kwargs.items():
            if field in BATCH_UPDATE_FIELDS:
                # Validate field name (defense in depth)
                _validate_field_name(field, BATCH_UPDATE_FIELDS, "update_batch_status")
                update_fields[field] = value

        if not update_fields:
            return False

        field_assignments = []
        values = []
        for field, value in update_fields.items():
            field_assignments.append(f"{field} = ?")
            values.append(value)

        values.append(batch_id)
        query = f"UPDATE batch_processing SET {', '.join(field_assignments)} WHERE batch_id = ?"

        with self.connection() as (conn, cursor):
            cursor.execute(query, values)
            return cursor.rowcount > 0
    
    def get_batch_status(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Get batch processing status.

        Parameters:
        - batch_id: Batch identifier

        Returns:
        - Batch status dictionary or None if not found
        """
        # Define batch columns for this query (includes 'options' not in standard schema)
        batch_query_columns = (
            'batch_id', 'total_count', 'completed_count', 'failed_count',
            'created_at', 'started_at', 'completed_at', 'options', 'status'
        )

        with self.connection() as (conn, cursor):
            cursor.execute("""
                SELECT batch_id, total_count, completed_count, failed_count,
                       created_at, started_at, completed_at, options, status
                FROM batch_processing
                WHERE batch_id = ?
            """, (batch_id,))

            row = cursor.fetchone()

            if row:
                batch_data = dict(zip(batch_query_columns, row))

                # Parse options JSON
                if batch_data['options']:
                    batch_data['options'] = json.loads(batch_data['options'])

                return batch_data

            return None

    def get_pending_recordings(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recordings that are pending processing."""
        # Extended columns including queue info (beyond standard recording schema)
        pending_columns = RecordingSchema.BASIC_COLUMNS + ('task_id', 'priority')

        with self.connection() as (conn, cursor):
            cursor.execute("""
                SELECT r.*, pq.task_id, pq.priority
                FROM recordings r
                LEFT JOIN processing_queue pq ON r.id = pq.recording_id
                WHERE r.processing_status = "pending" OR r.processing_status IS NULL
                ORDER BY pq.priority DESC, r.timestamp ASC
                LIMIT ?
            """, (limit,))

            recordings = cursor.fetchall()

            return [dict(zip(pending_columns, r)) for r in recordings]
    
    def get_processing_stats(self) -> Dict[str, int]:
        """Get processing queue statistics."""
        stats = {}

        with self.connection() as (conn, cursor):
            # Count by status
            cursor.execute("""
                SELECT processing_status, COUNT(*)
                FROM recordings
                WHERE processing_status IS NOT NULL
                GROUP BY processing_status
            """)

            for status, count in cursor.fetchall():
                stats[f"recordings_{status}"] = count

            # Queue stats
            cursor.execute("""
                SELECT status, COUNT(*)
                FROM processing_queue
                GROUP BY status
            """)

            for status, count in cursor.fetchall():
                stats[f"queue_{status}"] = count

        return stats
    
    def clear_all_recordings(self) -> bool:
        """Clear all recordings from the database and delete associated audio files.

        Returns:
        - True if successful, False otherwise
        """
        import os

        filenames = []

        with self.transaction() as (conn, cursor):
            # First, get all filenames to delete the audio files
            cursor.execute("SELECT filename FROM recordings WHERE filename IS NOT NULL AND filename != ''")
            filenames = [row[0] for row in cursor.fetchall()]

            # Delete all recordings from database
            cursor.execute("DELETE FROM recordings")

            # Reset the auto-increment counter
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='recordings'")

            # Also clear the processing queue if it exists
            try:
                cursor.execute("DELETE FROM processing_queue")
                cursor.execute("DELETE FROM sqlite_sequence WHERE name='processing_queue'")
            except sqlite3.OperationalError:
                # Table might not exist
                pass

        # Delete the audio files (outside transaction - file operations should not affect DB commit)
        for filename in filenames:
            if filename and os.path.exists(filename):
                try:
                    os.remove(filename)
                    logger.info(f"Deleted audio file: {filename}")
                except Exception as e:
                    logger.warning(f"Failed to delete audio file {filename}: {e}")

        return True
    
    def get_failed_recordings(self, limit: int = 100) -> List[Dict]:
        """Get recordings that have failed processing.

        Parameters:
        - limit: Maximum number of recordings to return

        Returns:
        - List of recording dictionaries with failed status
        """
        with self.connection() as (conn, cursor):
            columns = ', '.join(RecordingSchema.SELECT_COLUMNS)
            cursor.execute(f"""
                SELECT {columns} FROM recordings
                WHERE processing_status = 'failed'
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))

            recordings = cursor.fetchall()
            return [RecordingSchema.row_to_dict(r, RecordingSchema.SELECT_COLUMNS) for r in recordings]

    # =========================================================================
    # Analysis Results Methods
    # =========================================================================

    def save_analysis_result(
        self,
        analysis_type: str,
        result_text: str,
        recording_id: Optional[int] = None,
        analysis_subtype: Optional[str] = None,
        result_json: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        patient_context: Optional[Dict[str, Any]] = None,
        source_type: Optional[str] = None,
        source_text: Optional[str] = None
    ) -> Optional[int]:
        """
        Save a medical analysis result to the database.

        Parameters:
        - analysis_type: Type of analysis ('medication', 'diagnostic', 'workflow')
        - result_text: The analysis result text
        - recording_id: Optional link to a recording
        - analysis_subtype: Subtype (e.g., 'comprehensive', 'interactions')
        - result_json: Optional structured JSON result
        - metadata: Optional metadata (model, counts, etc.)
        - patient_context: Optional patient context used
        - source_type: Source of analysis ('transcript', 'soap', 'custom')
        - source_text: The input text that was analyzed

        Returns:
        - ID of the created analysis result, or None on failure
        """
        with self.connection() as (conn, cursor):
            cursor.execute("""
                INSERT INTO analysis_results (
                    recording_id, analysis_type, analysis_subtype,
                    result_text, result_json, metadata_json,
                    patient_context_json, source_type, source_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                recording_id,
                analysis_type,
                analysis_subtype,
                result_text,
                json.dumps(result_json) if result_json else None,
                json.dumps(metadata) if metadata else None,
                json.dumps(patient_context) if patient_context else None,
                source_type,
                source_text
            ))
            return cursor.lastrowid

    def get_analysis_result(self, analysis_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a single analysis result by ID.

        Parameters:
        - analysis_id: The analysis result ID

        Returns:
        - Analysis result dictionary or None if not found
        """
        with self.connection() as (conn, cursor):
            cursor.execute("""
                SELECT id, recording_id, analysis_type, analysis_subtype,
                       result_text, result_json, metadata_json,
                       patient_context_json, source_type, source_text,
                       created_at, updated_at
                FROM analysis_results
                WHERE id = ?
            """, (analysis_id,))

            row = cursor.fetchone()
            if row:
                return self._parse_analysis_row(row)
            return None

    def get_analysis_results_for_recording(
        self,
        recording_id: int,
        analysis_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all analysis results for a recording.

        Parameters:
        - recording_id: The recording ID
        - analysis_type: Optional filter by analysis type

        Returns:
        - List of analysis result dictionaries
        """
        with self.connection() as (conn, cursor):
            if analysis_type:
                cursor.execute("""
                    SELECT id, recording_id, analysis_type, analysis_subtype,
                           result_text, result_json, metadata_json,
                           patient_context_json, source_type, source_text,
                           created_at, updated_at
                    FROM analysis_results
                    WHERE recording_id = ? AND analysis_type = ?
                    ORDER BY created_at DESC
                """, (recording_id, analysis_type))
            else:
                cursor.execute("""
                    SELECT id, recording_id, analysis_type, analysis_subtype,
                           result_text, result_json, metadata_json,
                           patient_context_json, source_type, source_text,
                           created_at, updated_at
                    FROM analysis_results
                    WHERE recording_id = ?
                    ORDER BY created_at DESC
                """, (recording_id,))

            rows = cursor.fetchall()
            return [self._parse_analysis_row(row) for row in rows]

    def get_recent_analysis_results(
        self,
        analysis_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get recent analysis results.

        Parameters:
        - analysis_type: Optional filter by analysis type
        - limit: Maximum number of results to return

        Returns:
        - List of analysis result dictionaries
        """
        with self.connection() as (conn, cursor):
            if analysis_type:
                cursor.execute("""
                    SELECT id, recording_id, analysis_type, analysis_subtype,
                           result_text, result_json, metadata_json,
                           patient_context_json, source_type, source_text,
                           created_at, updated_at
                    FROM analysis_results
                    WHERE analysis_type = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (analysis_type, limit))
            else:
                cursor.execute("""
                    SELECT id, recording_id, analysis_type, analysis_subtype,
                           result_text, result_json, metadata_json,
                           patient_context_json, source_type, source_text,
                           created_at, updated_at
                    FROM analysis_results
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))

            rows = cursor.fetchall()
            return [self._parse_analysis_row(row) for row in rows]

    def delete_analysis_result(self, analysis_id: int) -> bool:
        """
        Delete an analysis result.

        Parameters:
        - analysis_id: The analysis result ID

        Returns:
        - True if deleted, False if not found
        """
        with self.connection() as (conn, cursor):
            cursor.execute("DELETE FROM analysis_results WHERE id = ?", (analysis_id,))
            return cursor.rowcount > 0

    def _parse_analysis_row(self, row: tuple) -> Dict[str, Any]:
        """
        Parse an analysis result database row into a dictionary.

        Parameters:
        - row: Database row tuple

        Returns:
        - Parsed dictionary with JSON fields decoded
        """
        columns = (
            'id', 'recording_id', 'analysis_type', 'analysis_subtype',
            'result_text', 'result_json', 'metadata_json',
            'patient_context_json', 'source_type', 'source_text',
            'created_at', 'updated_at'
        )
        result = dict(zip(columns, row))

        # Parse JSON fields
        for json_field in ('result_json', 'metadata_json', 'patient_context_json'):
            if result.get(json_field):
                try:
                    result[json_field] = json.loads(result[json_field])
                except (json.JSONDecodeError, TypeError):
                    pass  # Keep as string if parsing fails

        return result
