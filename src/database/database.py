"""
Database Module

Thread-safe database wrapper using thread-local connections with automatic cleanup.
This module uses mixins to organize functionality while maintaining a unified interface.

Error Handling:
    - Migration failures are logged but don't prevent app startup (graceful degradation)
    - Critical column additions log with ErrorContext for debugging
    - Database connection errors should propagate to callers
"""

import sqlite3
import threading
import re
from typing import Dict, List, FrozenSet

from managers.data_folder_manager import data_folder_manager
from utils.error_handling import ErrorContext
from utils.structured_logging import get_logger

# Import centralized schema definitions
from database.schema import (
    RecordingSchema, QueueSchema, BatchSchema,
    RECORDING_FIELDS, RECORDING_INSERT_FIELDS, RECORDING_UPDATE_FIELDS,
    QUEUE_UPDATE_FIELDS, BATCH_UPDATE_FIELDS
)

# Import mixins
from database.mixins import (
    ConnectionMixin,
    RecordingMixin,
    QueueMixin,
    AnalysisMixin,
    DiagnosticsMixin,
)

logger = get_logger(__name__)

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


class Database(ConnectionMixin, RecordingMixin, QueueMixin, AnalysisMixin, DiagnosticsMixin):
    """Thread-safe database wrapper using thread-local connections with automatic cleanup.

    Each thread gets its own connection, preventing race conditions
    when the same Database instance is used across multiple threads.

    Connection Lifecycle:
    - Connections are created lazily when first accessed by a thread
    - Connections are tracked and can be cleaned up via close_all_connections()
    - The __del__ method attempts cleanup when the Database instance is garbage collected
    - For best practice, explicitly call close_all_connections() during application shutdown

    This class inherits functionality from multiple mixins:
    - ConnectionMixin: Thread-local connection management
    - RecordingMixin: Recording CRUD operations
    - QueueMixin: Processing queue operations
    - AnalysisMixin: Analysis results operations
    - DiagnosticsMixin: Differential diagnosis and investigation operations
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
            from database.db_migrations import get_migration_manager
            migration_manager = get_migration_manager()
            pending = migration_manager.get_pending_migrations()
            if pending:
                logging.info(f"Found {len(pending)} pending database migrations")
                migration_manager.migrate()
                logging.info("Database migrations applied successfully")
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Apply database migrations",
                exception=e,
                error_code="DATABASE_MIGRATION_ERROR",
                db_path=self.db_path
            )
            ctx.log()
            # Don't raise - allow app to continue even if migrations fail
            # The app may still function with an older schema

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
                    logger.info(f"Adding missing column '{column_name}' to recordings table")
                    try:
                        conn.execute(f"ALTER TABLE recordings ADD COLUMN {column_name} {column_type}")
                        conn.commit()
                        logger.info(f"Successfully added column '{column_name}'")
                    except sqlite3.OperationalError as e:
                        if "duplicate column" not in str(e).lower():
                            ctx = ErrorContext.capture(
                                operation="Add database column",
                                exception=e,
                                error_code="DATABASE_ALTER_TABLE_ERROR",
                                column_name=column_name,
                                column_type=column_type,
                                db_path=self.db_path
                            )
                            ctx.log()
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Ensure critical database columns",
                exception=e,
                error_code="DATABASE_SCHEMA_CHECK_ERROR",
                db_path=self.db_path
            )
            ctx.log()

        # Also ensure analysis_results table exists
        self._ensure_analysis_results_table()

    def _ensure_analysis_results_table(self):
        """Ensure analysis_results table exists for storing medical analysis results."""
        try:
            conn = self._get_connection()
            # Check if table exists
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='analysis_results'"
            )
            if cursor.fetchone() is None:
                logging.info("Creating missing analysis_results table")
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS analysis_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        recording_id INTEGER,
                        analysis_type TEXT NOT NULL,
                        analysis_subtype TEXT,
                        result_text TEXT NOT NULL,
                        result_json TEXT,
                        metadata_json TEXT,
                        patient_context_json TEXT,
                        source_type TEXT,
                        source_text TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (recording_id) REFERENCES recordings(id) ON DELETE SET NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_analysis_recording_id ON analysis_results(recording_id);
                    CREATE INDEX IF NOT EXISTS idx_analysis_type ON analysis_results(analysis_type);
                    CREATE INDEX IF NOT EXISTS idx_analysis_created_at ON analysis_results(created_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_analysis_type_created ON analysis_results(analysis_type, created_at DESC);
                """)
                conn.commit()
                logging.info("Created analysis_results table successfully")
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Ensure analysis_results table",
                exception=e,
                error_code="DATABASE_TABLE_CREATE_ERROR",
                table_name="analysis_results",
                db_path=self.db_path
            )
            ctx.log()

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


# Export validation functions for use by other modules
__all__ = [
    "Database",
    "_validate_field_name",
    "_validate_fields",
]
