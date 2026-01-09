"""
Database Schema Definitions

This module provides centralized definitions for all database table schemas,
column names, and related utilities. By defining schemas in one place, we:

1. Eliminate duplicate column definitions across the codebase
2. Provide type-safe column access
3. Enable easy schema updates and migrations
4. Ensure consistency between query building and result parsing

Usage:
    from database.schema import RecordingSchema, QueueSchema

    # Get columns for SELECT queries
    columns = RecordingSchema.SELECT_COLUMNS

    # Parse a row into a dictionary
    record = RecordingSchema.row_to_dict(row)

    # Validate field names
    if RecordingSchema.is_valid_field('transcript'):
        ...
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple, FrozenSet, Sequence
from enum import Enum


class ColumnType(Enum):
    """Database column types."""
    INTEGER = "INTEGER"
    TEXT = "TEXT"
    REAL = "REAL"
    BLOB = "BLOB"
    DATETIME = "DATETIME"
    BOOLEAN = "INTEGER"  # SQLite uses INTEGER for boolean


@dataclass(frozen=True)
class ColumnDefinition:
    """Definition of a database column.

    Attributes:
        name: Column name
        type: Column data type
        nullable: Whether the column can be NULL
        default: Default value (None means no default)
        primary_key: Whether this is the primary key
        autoincrement: Whether to auto-increment (only for INTEGER PRIMARY KEY)
    """
    name: str
    type: ColumnType
    nullable: bool = True
    default: Any = None
    primary_key: bool = False
    autoincrement: bool = False

    def to_sql(self) -> str:
        """Generate SQL column definition.

        Returns:
            SQL string for CREATE TABLE statement
        """
        parts = [self.name, self.type.value]

        if self.primary_key:
            parts.append("PRIMARY KEY")
            if self.autoincrement:
                parts.append("AUTOINCREMENT")
        elif not self.nullable:
            parts.append("NOT NULL")

        if self.default is not None:
            if isinstance(self.default, str):
                parts.append(f"DEFAULT '{self.default}'")
            elif isinstance(self.default, bool):
                parts.append(f"DEFAULT {1 if self.default else 0}")
            else:
                parts.append(f"DEFAULT {self.default}")

        return " ".join(parts)


class RecordingSchema:
    """Schema definition for the recordings table.

    This class provides centralized access to recording table columns,
    eliminating duplicate definitions across the codebase.
    """

    # Column definitions with full metadata
    COLUMNS: Tuple[ColumnDefinition, ...] = (
        ColumnDefinition("id", ColumnType.INTEGER, primary_key=True, autoincrement=True),
        ColumnDefinition("filename", ColumnType.TEXT, nullable=False),
        ColumnDefinition("transcript", ColumnType.TEXT, nullable=True),
        ColumnDefinition("soap_note", ColumnType.TEXT, nullable=True),
        ColumnDefinition("referral", ColumnType.TEXT, nullable=True),
        ColumnDefinition("letter", ColumnType.TEXT, nullable=True),
        ColumnDefinition("chat", ColumnType.TEXT, nullable=True),
        ColumnDefinition("timestamp", ColumnType.DATETIME, nullable=True),
        ColumnDefinition("processing_status", ColumnType.TEXT, default="pending"),
        ColumnDefinition("processing_started_at", ColumnType.DATETIME, nullable=True),
        ColumnDefinition("processing_completed_at", ColumnType.DATETIME, nullable=True),
        ColumnDefinition("error_message", ColumnType.TEXT, nullable=True),
        ColumnDefinition("retry_count", ColumnType.INTEGER, default=0),
        ColumnDefinition("patient_name", ColumnType.TEXT, nullable=True),
        ColumnDefinition("audio_path", ColumnType.TEXT, nullable=True),
        ColumnDefinition("duration", ColumnType.REAL, nullable=True),
        ColumnDefinition("metadata", ColumnType.TEXT, nullable=True),
        # Added by migration 4
        ColumnDefinition("duration_seconds", ColumnType.REAL, nullable=True),
        ColumnDefinition("file_size_bytes", ColumnType.INTEGER, nullable=True),
        ColumnDefinition("stt_provider", ColumnType.TEXT, nullable=True),
        ColumnDefinition("ai_provider", ColumnType.TEXT, nullable=True),
        ColumnDefinition("tags", ColumnType.TEXT, nullable=True),
    )

    # Column name list for SELECT queries (most common use case)
    # This is the canonical list - use this instead of hardcoding columns
    COLUMN_NAMES: Tuple[str, ...] = tuple(col.name for col in COLUMNS)

    # Basic columns for simple queries (legacy compatibility)
    BASIC_COLUMNS: Tuple[str, ...] = (
        'id', 'filename', 'transcript', 'soap_note',
        'referral', 'letter', 'timestamp'
    )

    # Extended columns including processing status
    SELECT_COLUMNS: Tuple[str, ...] = (
        'id', 'filename', 'transcript', 'soap_note', 'referral', 'letter',
        'timestamp', 'processing_status', 'patient_name'
    )

    # Lightweight columns for list views (minimal data for UI display)
    # This avoids fetching large text columns (transcript, soap_note, referral, letter)
    LIGHTWEIGHT_COLUMNS: Tuple[str, ...] = (
        'id', 'filename', 'patient_name', 'timestamp', 'duration',
        'processing_status'
    )

    # Full column set for comprehensive queries (22 columns with all migration 4 additions)
    FULL_COLUMNS: Tuple[str, ...] = (
        'id', 'filename', 'transcript', 'soap_note', 'referral', 'letter',
        'chat', 'timestamp', 'processing_status', 'processing_started_at',
        'processing_completed_at', 'error_message', 'retry_count',
        'patient_name', 'audio_path', 'duration', 'metadata',
        'duration_seconds', 'file_size_bytes', 'stt_provider', 'ai_provider', 'tags'
    )

    # Database columns without chat field (16 columns - legacy databases)
    DB_COLUMNS_16: Tuple[str, ...] = (
        'id', 'filename', 'transcript', 'soap_note', 'referral', 'letter',
        'timestamp', 'processing_status', 'processing_started_at',
        'processing_completed_at', 'error_message', 'retry_count',
        'patient_name', 'audio_path', 'duration', 'metadata'
    )

    # Fields allowed for INSERT operations
    INSERT_FIELDS: FrozenSet[str] = frozenset({
        'filename', 'transcript', 'soap_note', 'referral', 'letter', 'timestamp',
        'processing_status', 'patient_name', 'audio_path', 'duration', 'metadata',
        'duration_seconds', 'file_size_bytes', 'stt_provider', 'ai_provider', 'tags'
    })

    # Fields allowed for UPDATE operations
    UPDATE_FIELDS: FrozenSet[str] = frozenset({
        'filename', 'transcript', 'soap_note', 'referral', 'letter', 'chat',
        'processing_status', 'processing_started_at', 'processing_completed_at',
        'error_message', 'retry_count', 'patient_name', 'audio_path', 'duration', 'metadata',
        'duration_seconds', 'file_size_bytes', 'stt_provider', 'ai_provider', 'tags'
    })

    # All valid field names
    ALL_FIELDS: FrozenSet[str] = frozenset(COLUMN_NAMES)

    @classmethod
    def row_to_dict(cls, row: Sequence, columns: Optional[Tuple[str, ...]] = None) -> Dict[str, Any]:
        """Convert a database row to a dictionary.

        Args:
            row: Database row tuple
            columns: Column names to use (defaults to auto-detection based on row length)

        Returns:
            Dictionary with column names as keys
        """
        row_len = len(row)

        # If columns specified and length matches, use them
        if columns is not None and row_len == len(columns):
            return dict(zip(columns, row))

        # Auto-detect based on row length
        if row_len == len(cls.LIGHTWEIGHT_COLUMNS):
            columns = cls.LIGHTWEIGHT_COLUMNS
        elif row_len == len(cls.BASIC_COLUMNS):
            columns = cls.BASIC_COLUMNS
        elif row_len == len(cls.SELECT_COLUMNS):
            columns = cls.SELECT_COLUMNS
        elif row_len == len(cls.DB_COLUMNS_16):
            columns = cls.DB_COLUMNS_16
        elif row_len == len(cls.FULL_COLUMNS):
            columns = cls.FULL_COLUMNS
        elif row_len == len(cls.COLUMN_NAMES):
            columns = cls.COLUMN_NAMES
        else:
            raise ValueError(
                f"Row length ({row_len}) doesn't match any known column set. "
                f"Known lengths: {len(cls.LIGHTWEIGHT_COLUMNS)}, {len(cls.BASIC_COLUMNS)}, "
                f"{len(cls.SELECT_COLUMNS)}, {len(cls.DB_COLUMNS_16)}, {len(cls.FULL_COLUMNS)}, "
                f"{len(cls.COLUMN_NAMES)}"
            )

        return dict(zip(columns, row))

    @classmethod
    def is_valid_field(cls, field: str) -> bool:
        """Check if a field name is valid.

        Args:
            field: Field name to check

        Returns:
            True if the field is valid
        """
        return field in cls.ALL_FIELDS

    @classmethod
    def validate_fields(cls, fields: List[str], for_update: bool = False) -> List[str]:
        """Validate a list of field names.

        Args:
            fields: List of field names to validate
            for_update: If True, validate against UPDATE_FIELDS

        Returns:
            The validated field list

        Raises:
            ValueError: If any field is invalid
        """
        allowed = cls.UPDATE_FIELDS if for_update else cls.ALL_FIELDS

        invalid = [f for f in fields if f not in allowed]
        if invalid:
            raise ValueError(
                f"Invalid fields: {invalid}. Allowed: {sorted(allowed)}"
            )
        return fields

    @classmethod
    def get_select_sql(cls, columns: Optional[Tuple[str, ...]] = None) -> str:
        """Get column list for SELECT statement.

        Args:
            columns: Specific columns to select (defaults to SELECT_COLUMNS)

        Returns:
            Comma-separated column list
        """
        if columns is None:
            columns = cls.SELECT_COLUMNS
        return ", ".join(columns)


class QueueSchema:
    """Schema definition for the processing_queue table."""

    COLUMNS: Tuple[ColumnDefinition, ...] = (
        ColumnDefinition("id", ColumnType.INTEGER, primary_key=True, autoincrement=True),
        ColumnDefinition("recording_id", ColumnType.INTEGER, nullable=False),
        ColumnDefinition("task_type", ColumnType.TEXT, nullable=False),
        ColumnDefinition("priority", ColumnType.INTEGER, default=0),
        ColumnDefinition("status", ColumnType.TEXT, default="pending"),
        ColumnDefinition("created_at", ColumnType.DATETIME, nullable=True),
        ColumnDefinition("started_at", ColumnType.DATETIME, nullable=True),
        ColumnDefinition("completed_at", ColumnType.DATETIME, nullable=True),
        ColumnDefinition("error_count", ColumnType.INTEGER, default=0),
        ColumnDefinition("last_error", ColumnType.TEXT, nullable=True),
        ColumnDefinition("result", ColumnType.TEXT, nullable=True),
        ColumnDefinition("batch_id", ColumnType.INTEGER, nullable=True),
    )

    COLUMN_NAMES: Tuple[str, ...] = tuple(col.name for col in COLUMNS)

    # Fields allowed for UPDATE operations
    UPDATE_FIELDS: FrozenSet[str] = frozenset({
        'status', 'started_at', 'completed_at', 'error_count', 'last_error', 'result'
    })

    ALL_FIELDS: FrozenSet[str] = frozenset(COLUMN_NAMES)

    @classmethod
    def row_to_dict(cls, row: Sequence) -> Dict[str, Any]:
        """Convert a queue row to a dictionary."""
        return dict(zip(cls.COLUMN_NAMES, row))


class BatchSchema:
    """Schema definition for the batch_processing table."""

    COLUMNS: Tuple[ColumnDefinition, ...] = (
        ColumnDefinition("batch_id", ColumnType.INTEGER, primary_key=True, autoincrement=True),
        ColumnDefinition("total_count", ColumnType.INTEGER, nullable=False),
        ColumnDefinition("completed_count", ColumnType.INTEGER, default=0),
        ColumnDefinition("failed_count", ColumnType.INTEGER, default=0),
        ColumnDefinition("created_at", ColumnType.DATETIME, nullable=True),
        ColumnDefinition("started_at", ColumnType.DATETIME, nullable=True),
        ColumnDefinition("completed_at", ColumnType.DATETIME, nullable=True),
        ColumnDefinition("status", ColumnType.TEXT, default="pending"),
    )

    COLUMN_NAMES: Tuple[str, ...] = tuple(col.name for col in COLUMNS)

    SELECT_COLUMNS: Tuple[str, ...] = (
        'batch_id', 'total_count', 'completed_count', 'failed_count',
        'created_at', 'started_at', 'completed_at', 'status'
    )

    # Fields allowed for UPDATE operations
    UPDATE_FIELDS: FrozenSet[str] = frozenset({
        'completed_count', 'failed_count', 'started_at', 'completed_at', 'status'
    })

    ALL_FIELDS: FrozenSet[str] = frozenset(COLUMN_NAMES)

    @classmethod
    def row_to_dict(cls, row: Sequence) -> Dict[str, Any]:
        """Convert a batch row to a dictionary."""
        return dict(zip(cls.COLUMN_NAMES, row))


# =============================================================================
# Legacy Compatibility Aliases
# =============================================================================
# These provide backward compatibility with the old field allowlists

RECORDING_FIELDS = RecordingSchema.ALL_FIELDS
RECORDING_INSERT_FIELDS = RecordingSchema.INSERT_FIELDS
RECORDING_UPDATE_FIELDS = RecordingSchema.UPDATE_FIELDS
QUEUE_UPDATE_FIELDS = QueueSchema.UPDATE_FIELDS
BATCH_UPDATE_FIELDS = BatchSchema.UPDATE_FIELDS

# Legacy column list (for backward compatibility with code expecting a list)
RECORDING_COLUMNS = list(RecordingSchema.BASIC_COLUMNS)
RECORDING_COLUMNS_EXTENDED = list(RecordingSchema.SELECT_COLUMNS)
