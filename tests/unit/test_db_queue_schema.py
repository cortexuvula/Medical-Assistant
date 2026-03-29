"""
Tests for src/database/db_queue_schema.py

Covers _validate_identifier (pure function), ALLOWED_COLUMNS / ALLOWED_INDEXES
constants, QueueDatabaseSchema.__init__, and the internal helpers
_needs_upgrade, _add_processing_columns, and _create_indexes when called
with mocked cursors.
No real SQLite file is written.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from database.db_queue_schema import (
    _validate_identifier,
    ALLOWED_COLUMNS,
    ALLOWED_INDEXES,
    QueueDatabaseSchema,
)


# ===========================================================================
# _validate_identifier
# ===========================================================================

class TestValidateIdentifier:
    def test_valid_simple_name_passes(self):
        _validate_identifier("recordings")  # should not raise

    def test_valid_name_with_underscores_passes(self):
        _validate_identifier("processing_queue")

    def test_valid_name_starting_with_underscore_passes(self):
        _validate_identifier("_internal")

    def test_valid_name_with_digits_passes(self):
        _validate_identifier("table1")

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError):
            _validate_identifier("")

    def test_name_starting_with_digit_raises(self):
        with pytest.raises(ValueError):
            _validate_identifier("1bad")

    def test_name_with_space_raises(self):
        with pytest.raises(ValueError):
            _validate_identifier("bad name")

    def test_name_with_dot_raises(self):
        with pytest.raises(ValueError):
            _validate_identifier("table.column")

    def test_name_with_semicolon_raises(self):
        with pytest.raises(ValueError):
            _validate_identifier("table; DROP TABLE")

    def test_name_with_hyphen_raises(self):
        with pytest.raises(ValueError):
            _validate_identifier("bad-name")

    def test_error_message_contains_identifier_type(self):
        with pytest.raises(ValueError, match="column name"):
            _validate_identifier("bad name", identifier_type="column name")


# ===========================================================================
# ALLOWED_COLUMNS constant
# ===========================================================================

class TestAllowedColumns:
    def test_is_dict(self):
        assert isinstance(ALLOWED_COLUMNS, dict)

    def test_contains_processing_status(self):
        assert "processing_status" in ALLOWED_COLUMNS

    def test_contains_patient_name(self):
        assert "patient_name" in ALLOWED_COLUMNS

    def test_contains_retry_count(self):
        assert "retry_count" in ALLOWED_COLUMNS

    def test_all_keys_are_valid_identifiers(self):
        for key in ALLOWED_COLUMNS:
            _validate_identifier(key)  # should not raise

    def test_values_are_strings(self):
        for val in ALLOWED_COLUMNS.values():
            assert isinstance(val, str)


# ===========================================================================
# ALLOWED_INDEXES constant
# ===========================================================================

class TestAllowedIndexes:
    def test_is_dict(self):
        assert isinstance(ALLOWED_INDEXES, dict)

    def test_each_value_is_tuple_of_two(self):
        for key, val in ALLOWED_INDEXES.items():
            assert isinstance(val, tuple)
            assert len(val) == 2

    def test_contains_recordings_status_index(self):
        assert "idx_recordings_processing_status" in ALLOWED_INDEXES

    def test_contains_queue_status_index(self):
        assert "idx_processing_queue_status" in ALLOWED_INDEXES

    def test_index_names_are_valid_identifiers(self):
        for idx_name in ALLOWED_INDEXES:
            _validate_identifier(idx_name)

    def test_table_names_are_valid_identifiers(self):
        for _, (table_name, _) in ALLOWED_INDEXES.items():
            _validate_identifier(table_name)


# ===========================================================================
# QueueDatabaseSchema.__init__
# ===========================================================================

class TestQueueDatabaseSchemaInit:
    def test_default_db_path(self):
        schema = QueueDatabaseSchema()
        assert schema.db_path == "database.db"

    def test_custom_db_path(self):
        schema = QueueDatabaseSchema(db_path="/tmp/test.db")
        assert schema.db_path == "/tmp/test.db"


# ===========================================================================
# QueueDatabaseSchema._needs_upgrade (mocked cursor)
# ===========================================================================

class TestNeedsUpgrade:
    def _make_schema(self):
        schema = QueueDatabaseSchema(db_path=":memory:")
        return schema

    def test_returns_false_when_recordings_table_missing(self):
        schema = self._make_schema()
        cursor = MagicMock()
        cursor.fetchone.return_value = None  # table does not exist
        result = schema._needs_upgrade(cursor)
        assert result is False

    def test_returns_true_when_processing_status_column_missing(self):
        schema = self._make_schema()
        cursor = MagicMock()
        # First fetchone: recordings table exists
        # Second fetchall: columns without processing_status
        # Third fetchone: processing_queue table also missing (would trigger True first)
        cursor.fetchone.side_effect = [
            ("recordings",),  # recordings table exists
            None,             # processing_queue table missing
        ]
        cursor.fetchall.return_value = [
            (0, "id", "INTEGER", 0, None, 1),
            (1, "filename", "TEXT", 0, None, 0),
        ]  # No processing_status → returns True
        result = schema._needs_upgrade(cursor)
        assert result is True

    def test_returns_true_when_processing_queue_table_missing(self):
        schema = self._make_schema()
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            ("recordings",),  # recordings table exists
            None,             # processing_queue missing
        ]
        # Columns include processing_status
        cursor.fetchall.return_value = [
            (0, "id", "INTEGER", 0, None, 1),
            (1, "processing_status", "TEXT", 0, "pending", 0),
        ]
        result = schema._needs_upgrade(cursor)
        assert result is True

    def test_returns_false_when_fully_upgraded(self):
        schema = self._make_schema()
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            ("recordings",),        # recordings table exists
            ("processing_queue",),  # processing_queue exists
        ]
        cursor.fetchall.return_value = [
            (0, "id", "INTEGER", 0, None, 1),
            (1, "processing_status", "TEXT", 0, "pending", 0),
        ]
        result = schema._needs_upgrade(cursor)
        assert result is False


# ===========================================================================
# QueueDatabaseSchema._add_processing_columns (mocked cursor)
# ===========================================================================

class TestAddProcessingColumns:
    def _make_schema(self):
        return QueueDatabaseSchema(db_path=":memory:")

    def test_skips_when_recordings_table_missing(self):
        schema = self._make_schema()
        cursor = MagicMock()
        cursor.fetchone.return_value = None  # recordings table missing
        schema._add_processing_columns(cursor)
        # Should not execute ALTER TABLE
        assert not any(
            "ALTER" in str(c) for c in cursor.execute.call_args_list
        )

    def test_adds_missing_columns(self):
        schema = self._make_schema()
        cursor = MagicMock()
        cursor.fetchone.return_value = ("recordings",)  # table exists
        # No existing columns
        cursor.fetchall.return_value = [(0, "id", "INTEGER", 0, None, 1)]
        schema._add_processing_columns(cursor)
        # ALTER TABLE should have been called for each column in ALLOWED_COLUMNS
        execute_calls = [str(c) for c in cursor.execute.call_args_list]
        alter_calls = [c for c in execute_calls if "ALTER" in c]
        assert len(alter_calls) == len(ALLOWED_COLUMNS)

    def test_skips_existing_columns(self):
        schema = self._make_schema()
        cursor = MagicMock()
        cursor.fetchone.return_value = ("recordings",)
        # All ALLOWED_COLUMNS already present
        existing = [(i, col, "TEXT", 0, None, 0) for i, col in enumerate(ALLOWED_COLUMNS)]
        cursor.fetchall.return_value = existing
        schema._add_processing_columns(cursor)
        execute_calls = [str(c) for c in cursor.execute.call_args_list]
        alter_calls = [c for c in execute_calls if "ALTER" in c]
        assert len(alter_calls) == 0


# ===========================================================================
# QueueDatabaseSchema._create_indexes (mocked cursor)
# ===========================================================================

class TestCreateIndexes:
    def _make_schema(self):
        return QueueDatabaseSchema(db_path=":memory:")

    def test_creates_indexes_when_recordings_table_exists(self):
        schema = self._make_schema()
        cursor = MagicMock()
        cursor.fetchone.return_value = ("recordings",)  # table exists
        schema._create_indexes(cursor)
        execute_calls = [str(c) for c in cursor.execute.call_args_list]
        # At least some CREATE INDEX calls
        create_calls = [c for c in execute_calls if "CREATE INDEX" in c]
        assert len(create_calls) > 0

    def test_skips_recordings_indexes_when_table_missing(self):
        schema = self._make_schema()
        cursor = MagicMock()
        cursor.fetchone.return_value = None  # recordings table missing
        schema._create_indexes(cursor)
        execute_calls = [str(c) for c in cursor.execute.call_args_list]
        # No index on recordings table should be created
        recordings_index_calls = [
            c for c in execute_calls
            if "CREATE INDEX" in c and "recordings" in c
        ]
        assert len(recordings_index_calls) == 0
