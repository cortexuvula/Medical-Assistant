"""
Database Queue Mixin

Provides processing queue operations for the Database class.
"""

import sqlite3
import json
import logging
import re
from typing import Optional, Dict, List, Any

from database.schema import (
    RecordingSchema,
    QUEUE_UPDATE_FIELDS, BATCH_UPDATE_FIELDS
)

logger = logging.getLogger(__name__)

# Valid SQL identifier pattern
_VALID_IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


def _validate_field_name(field: str, allowlist, context: str = "query") -> str:
    """Validate a field name against an allowlist."""
    if not field:
        raise ValueError(f"Empty field name not allowed in {context}")

    if not isinstance(field, str):
        raise ValueError(f"Field name must be a string in {context}, got {type(field).__name__}")

    if field not in allowlist:
        raise ValueError(f"Field '{field}' is not allowed in {context}. Allowed fields: {sorted(allowlist)}")

    if not _VALID_IDENTIFIER_PATTERN.match(field):
        raise ValueError(f"Field '{field}' has invalid format in {context}")

    return field


class QueueMixin:
    """Mixin providing processing queue operations."""

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


__all__ = ["QueueMixin"]
