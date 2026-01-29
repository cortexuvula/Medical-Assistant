"""
Database Recording Mixin

Provides recording CRUD operations for the Database class.
"""

import datetime
import json
from typing import Optional, Dict, List, Any, Union, Generator

from utils.retry_decorator import db_retry
from database.schema import (
    RecordingSchema,
    RECORDING_FIELDS, RECORDING_INSERT_FIELDS, RECORDING_UPDATE_FIELDS
)
from utils.structured_logging import get_logger

logger = get_logger(__name__)


def _validate_field_name(field: str, allowlist, context: str = "query") -> str:
    """Validate a field name against an allowlist."""
    import re
    _VALID_IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

    if not field:
        raise ValueError(f"Empty field name not allowed in {context}")

    if not isinstance(field, str):
        raise ValueError(f"Field name must be a string in {context}, got {type(field).__name__}")

    if field not in allowlist:
        raise ValueError(f"Field '{field}' is not allowed in {context}. Allowed fields: {sorted(allowlist)}")

    if not _VALID_IDENTIFIER_PATTERN.match(field):
        raise ValueError(f"Field '{field}' has invalid format in {context}")

    return field


def _validate_fields(fields: List[str], allowlist, context: str = "query") -> List[str]:
    """Validate multiple field names against an allowlist."""
    return [_validate_field_name(f, allowlist, context) for f in fields]


class RecordingMixin:
    """Mixin providing recording CRUD operations."""

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

    def iter_recordings_batched(
        self,
        batch_size: int = 100,
        order_by: str = "timestamp",
        descending: bool = True,
        lightweight: bool = True
    ) -> Generator[List[Dict[str, Any]], None, None]:
        """Generator that yields recordings in batches for memory-efficient processing.

        Unlike get_all_recordings() which loads everything at once (potentially 100MB+
        with 10k recordings), this method streams results in batches, keeping memory
        usage under ~1MB per batch.

        Args:
            batch_size: Number of recordings per batch (default: 100)
            order_by: Column to order by (must be a valid column name)
            descending: If True, order descending (newest first)
            lightweight: If True, use lightweight columns (recommended for UI lists)

        Yields:
            List of recording dictionaries for each batch

        Example:
            for batch in db.iter_recordings_batched(batch_size=100):
                for recording in batch:
                    process(recording)
        """
        # Validate order_by column to prevent SQL injection
        valid_columns = {"id", "timestamp", "filename", "duration", "patient_name", "processing_status"}
        if order_by not in valid_columns:
            order_by = "timestamp"

        order_direction = "DESC" if descending else "ASC"

        # Choose columns based on lightweight flag
        if lightweight:
            columns = ', '.join(RecordingSchema.LIGHTWEIGHT_COLUMNS)
            # Add has_* flags for UI compatibility
            query = f"""
                SELECT {columns},
                       CASE WHEN transcript IS NOT NULL AND transcript != '' THEN 1 ELSE 0 END as has_transcript,
                       CASE WHEN soap_note IS NOT NULL AND soap_note != '' THEN 1 ELSE 0 END as has_soap,
                       CASE WHEN referral IS NOT NULL AND referral != '' THEN 1 ELSE 0 END as has_referral,
                       CASE WHEN letter IS NOT NULL AND letter != '' THEN 1 ELSE 0 END as has_letter
                FROM recordings
                ORDER BY {order_by} {order_direction}
                LIMIT ? OFFSET ?
            """
            extended_columns = RecordingSchema.LIGHTWEIGHT_COLUMNS + (
                'has_transcript', 'has_soap', 'has_referral', 'has_letter'
            )
        else:
            columns = ', '.join(RecordingSchema.SELECT_COLUMNS)
            query = f"SELECT {columns} FROM recordings ORDER BY {order_by} {order_direction} LIMIT ? OFFSET ?"
            extended_columns = None

        offset = 0
        while True:
            with self.connection() as (conn, cursor):
                cursor.execute(query, (batch_size, offset))
                rows = cursor.fetchall()

                if not rows:
                    break

                # Convert to dictionaries
                if lightweight and extended_columns:
                    batch = []
                    for r in rows:
                        record = dict(zip(extended_columns, r))
                        record['has_transcript'] = bool(record.get('has_transcript', 0))
                        record['has_soap'] = bool(record.get('has_soap', 0))
                        record['has_referral'] = bool(record.get('has_referral', 0))
                        record['has_letter'] = bool(record.get('has_letter', 0))
                        batch.append(record)
                else:
                    batch = [RecordingSchema.row_to_dict(r, RecordingSchema.SELECT_COLUMNS) for r in rows]

                yield batch

                # If we got fewer rows than requested, we're done
                if len(rows) < batch_size:
                    break

                offset += batch_size

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

        # Compute has_* flags as derived columns (avoids loading full text)
        query = f"""
            SELECT {columns},
                   CASE WHEN transcript IS NOT NULL AND transcript != '' THEN 1 ELSE 0 END as has_transcript,
                   CASE WHEN soap_note IS NOT NULL AND soap_note != '' THEN 1 ELSE 0 END as has_soap,
                   CASE WHEN referral IS NOT NULL AND referral != '' THEN 1 ELSE 0 END as has_referral,
                   CASE WHEN letter IS NOT NULL AND letter != '' THEN 1 ELSE 0 END as has_letter
            FROM recordings
            ORDER BY {order_by} {order_direction}
            LIMIT ? OFFSET ?
        """

        with self.connection() as (conn, cursor):
            cursor.execute(query, (limit, offset))
            recordings = cursor.fetchall()

            # Map results to dictionaries with the extra derived columns
            result = []
            extended_columns = RecordingSchema.LIGHTWEIGHT_COLUMNS + (
                'has_transcript', 'has_soap', 'has_referral', 'has_letter'
            )
            for r in recordings:
                record = dict(zip(extended_columns, r))
                # Convert boolean flags to Python bools
                record['has_transcript'] = bool(record.get('has_transcript', 0))
                record['has_soap'] = bool(record.get('has_soap', 0))
                record['has_referral'] = bool(record.get('has_referral', 0))
                record['has_letter'] = bool(record.get('has_letter', 0))
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
            except Exception as e:
                # Table might not exist
                logger.debug(f"Could not clear processing_queue (table may not exist): {e}")

        # Delete the audio files (outside transaction - file operations should not affect DB commit)
        for filename in filenames:
            if filename and os.path.exists(filename):
                try:
                    os.remove(filename)
                    logger.info(f"Deleted audio file: {filename}")
                except Exception as e:
                    logger.warning(f"Failed to delete audio file {filename}: {e}")

        return True


__all__ = ["RecordingMixin"]
