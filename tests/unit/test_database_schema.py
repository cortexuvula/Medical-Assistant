"""
Tests for src/database/schema.py

Covers ColumnType enum, ColumnDefinition.to_sql, RecordingSchema
(attributes, row_to_dict auto-detection, is_valid_field, validate_fields,
get_select_sql), QueueSchema (row_to_dict), BatchSchema (row_to_dict),
and legacy compatibility aliases.
Pure logic — no DB or Tkinter dependencies.
"""

import sys
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from database.schema import (
    ColumnType, ColumnDefinition,
    RecordingSchema, QueueSchema, BatchSchema,
    RECORDING_FIELDS, RECORDING_INSERT_FIELDS, RECORDING_UPDATE_FIELDS,
    QUEUE_UPDATE_FIELDS, BATCH_UPDATE_FIELDS,
    RECORDING_COLUMNS, RECORDING_COLUMNS_EXTENDED,
)


# ===========================================================================
# ColumnType enum
# ===========================================================================

class TestColumnType:
    def test_integer_value(self):
        assert ColumnType.INTEGER.value == "INTEGER"

    def test_text_value(self):
        assert ColumnType.TEXT.value == "TEXT"

    def test_real_value(self):
        assert ColumnType.REAL.value == "REAL"

    def test_blob_value(self):
        assert ColumnType.BLOB.value == "BLOB"

    def test_datetime_value(self):
        assert ColumnType.DATETIME.value == "DATETIME"

    def test_boolean_maps_to_integer(self):
        # SQLite stores boolean as INTEGER
        assert ColumnType.BOOLEAN.value == "INTEGER"


# ===========================================================================
# ColumnDefinition.to_sql
# ===========================================================================

class TestColumnDefinitionToSql:
    def test_primary_key_with_autoincrement(self):
        col = ColumnDefinition("id", ColumnType.INTEGER, primary_key=True, autoincrement=True)
        sql = col.to_sql()
        assert "id" in sql
        assert "INTEGER" in sql
        assert "PRIMARY KEY" in sql
        assert "AUTOINCREMENT" in sql

    def test_primary_key_without_autoincrement(self):
        col = ColumnDefinition("id", ColumnType.INTEGER, primary_key=True, autoincrement=False)
        sql = col.to_sql()
        assert "PRIMARY KEY" in sql
        assert "AUTOINCREMENT" not in sql

    def test_not_null_when_nullable_false(self):
        col = ColumnDefinition("name", ColumnType.TEXT, nullable=False)
        sql = col.to_sql()
        assert "NOT NULL" in sql

    def test_no_not_null_when_nullable_true(self):
        col = ColumnDefinition("name", ColumnType.TEXT, nullable=True)
        sql = col.to_sql()
        assert "NOT NULL" not in sql

    def test_default_string_value(self):
        col = ColumnDefinition("status", ColumnType.TEXT, default="pending")
        sql = col.to_sql()
        assert "DEFAULT 'pending'" in sql

    def test_default_bool_true(self):
        col = ColumnDefinition("active", ColumnType.INTEGER, default=True)
        sql = col.to_sql()
        assert "DEFAULT 1" in sql

    def test_default_bool_false(self):
        col = ColumnDefinition("deleted", ColumnType.INTEGER, default=False)
        sql = col.to_sql()
        assert "DEFAULT 0" in sql

    def test_default_integer_value(self):
        col = ColumnDefinition("count", ColumnType.INTEGER, default=0)
        sql = col.to_sql()
        assert "DEFAULT 0" in sql

    def test_no_default_when_none(self):
        col = ColumnDefinition("notes", ColumnType.TEXT, nullable=True)
        sql = col.to_sql()
        assert "DEFAULT" not in sql

    def test_column_name_appears_first(self):
        col = ColumnDefinition("filename", ColumnType.TEXT, nullable=False)
        sql = col.to_sql()
        assert sql.startswith("filename")


# ===========================================================================
# RecordingSchema — class attributes
# ===========================================================================

class TestRecordingSchemaAttributes:
    def test_column_names_derived_from_columns(self):
        expected = tuple(col.name for col in RecordingSchema.COLUMNS)
        assert RecordingSchema.COLUMN_NAMES == expected

    def test_id_in_column_names(self):
        assert "id" in RecordingSchema.COLUMN_NAMES

    def test_basic_columns_is_subset_of_all_fields(self):
        for col in RecordingSchema.BASIC_COLUMNS:
            assert col in RecordingSchema.ALL_FIELDS

    def test_select_columns_contains_processing_status(self):
        assert "processing_status" in RecordingSchema.SELECT_COLUMNS

    def test_full_columns_contains_all_migration4_fields(self):
        for field in ("duration_seconds", "file_size_bytes", "stt_provider", "ai_provider", "tags"):
            assert field in RecordingSchema.FULL_COLUMNS

    def test_insert_fields_is_frozenset(self):
        assert isinstance(RecordingSchema.INSERT_FIELDS, frozenset)

    def test_update_fields_is_frozenset(self):
        assert isinstance(RecordingSchema.UPDATE_FIELDS, frozenset)

    def test_all_fields_covers_all_column_names(self):
        for name in RecordingSchema.COLUMN_NAMES:
            assert name in RecordingSchema.ALL_FIELDS

    def test_id_not_in_insert_fields(self):
        # id is autoincrement — should not be inserted manually
        assert "id" not in RecordingSchema.INSERT_FIELDS

    def test_lightweight_columns_excludes_large_text_fields(self):
        for heavy in ("transcript", "soap_note", "referral", "letter"):
            assert heavy not in RecordingSchema.LIGHTWEIGHT_COLUMNS


# ===========================================================================
# RecordingSchema.row_to_dict
# ===========================================================================

class TestRecordingSchemaRowToDict:
    def _row(self, length):
        return tuple(range(length))

    def test_explicit_columns_used(self):
        row = (1, "test.mp3", "some text")
        columns = ("id", "filename", "transcript")
        result = RecordingSchema.row_to_dict(row, columns=columns)
        assert result == {"id": 1, "filename": "test.mp3", "transcript": "some text"}

    def test_auto_detects_lightweight_columns(self):
        n = len(RecordingSchema.LIGHTWEIGHT_COLUMNS)
        row = self._row(n)
        result = RecordingSchema.row_to_dict(row)
        assert list(result.keys()) == list(RecordingSchema.LIGHTWEIGHT_COLUMNS)

    def test_auto_detects_basic_columns(self):
        n = len(RecordingSchema.BASIC_COLUMNS)
        row = self._row(n)
        result = RecordingSchema.row_to_dict(row)
        assert list(result.keys()) == list(RecordingSchema.BASIC_COLUMNS)

    def test_auto_detects_select_columns(self):
        n = len(RecordingSchema.SELECT_COLUMNS)
        row = self._row(n)
        result = RecordingSchema.row_to_dict(row)
        assert list(result.keys()) == list(RecordingSchema.SELECT_COLUMNS)

    def test_auto_detects_db_columns_16(self):
        n = len(RecordingSchema.DB_COLUMNS_16)
        row = self._row(n)
        result = RecordingSchema.row_to_dict(row)
        assert list(result.keys()) == list(RecordingSchema.DB_COLUMNS_16)

    def test_auto_detects_full_columns(self):
        n = len(RecordingSchema.FULL_COLUMNS)
        row = self._row(n)
        result = RecordingSchema.row_to_dict(row)
        assert len(result) == n

    def test_unknown_length_raises_value_error(self):
        row = tuple(range(3))  # 3 columns — no match
        with pytest.raises(ValueError, match="Row length"):
            RecordingSchema.row_to_dict(row)

    def test_returns_dict(self):
        n = len(RecordingSchema.BASIC_COLUMNS)
        row = self._row(n)
        result = RecordingSchema.row_to_dict(row)
        assert isinstance(result, dict)


# ===========================================================================
# RecordingSchema.is_valid_field
# ===========================================================================

class TestRecordingSchemaIsValidField:
    def test_known_field_returns_true(self):
        assert RecordingSchema.is_valid_field("transcript") is True

    def test_id_returns_true(self):
        assert RecordingSchema.is_valid_field("id") is True

    def test_unknown_field_returns_false(self):
        assert RecordingSchema.is_valid_field("nonexistent_column") is False

    def test_empty_string_returns_false(self):
        assert RecordingSchema.is_valid_field("") is False

    def test_all_column_names_are_valid(self):
        for name in RecordingSchema.COLUMN_NAMES:
            assert RecordingSchema.is_valid_field(name) is True


# ===========================================================================
# RecordingSchema.validate_fields
# ===========================================================================

class TestRecordingSchemaValidateFields:
    def test_valid_fields_returns_list(self):
        fields = ["transcript", "soap_note"]
        result = RecordingSchema.validate_fields(fields)
        assert result == fields

    def test_invalid_field_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid fields"):
            RecordingSchema.validate_fields(["nonexistent"])

    def test_for_update_rejects_readonly_field(self):
        # 'id' is not in UPDATE_FIELDS
        with pytest.raises(ValueError):
            RecordingSchema.validate_fields(["id"], for_update=True)

    def test_for_update_accepts_update_fields(self):
        fields = ["transcript", "processing_status"]
        result = RecordingSchema.validate_fields(fields, for_update=True)
        assert result == fields

    def test_empty_list_returns_empty(self):
        result = RecordingSchema.validate_fields([])
        assert result == []


# ===========================================================================
# RecordingSchema.get_select_sql
# ===========================================================================

class TestRecordingSchemaGetSelectSql:
    def test_default_uses_select_columns(self):
        sql = RecordingSchema.get_select_sql()
        expected = ", ".join(RecordingSchema.SELECT_COLUMNS)
        assert sql == expected

    def test_custom_columns_used(self):
        columns = ("id", "filename", "transcript")
        sql = RecordingSchema.get_select_sql(columns=columns)
        assert sql == "id, filename, transcript"

    def test_returns_string(self):
        assert isinstance(RecordingSchema.get_select_sql(), str)

    def test_comma_separated(self):
        sql = RecordingSchema.get_select_sql()
        parts = [p.strip() for p in sql.split(",")]
        assert len(parts) == len(RecordingSchema.SELECT_COLUMNS)


# ===========================================================================
# QueueSchema
# ===========================================================================

class TestQueueSchema:
    def test_column_names_derived_from_columns(self):
        expected = tuple(col.name for col in QueueSchema.COLUMNS)
        assert QueueSchema.COLUMN_NAMES == expected

    def test_id_in_column_names(self):
        assert "id" in QueueSchema.COLUMN_NAMES

    def test_recording_id_in_column_names(self):
        assert "recording_id" in QueueSchema.COLUMN_NAMES

    def test_row_to_dict_returns_dict(self):
        n = len(QueueSchema.COLUMN_NAMES)
        row = tuple(range(n))
        result = QueueSchema.row_to_dict(row)
        assert isinstance(result, dict)
        assert len(result) == n

    def test_row_to_dict_correct_keys(self):
        n = len(QueueSchema.COLUMN_NAMES)
        row = tuple(range(n))
        result = QueueSchema.row_to_dict(row)
        assert list(result.keys()) == list(QueueSchema.COLUMN_NAMES)

    def test_update_fields_is_frozenset(self):
        assert isinstance(QueueSchema.UPDATE_FIELDS, frozenset)

    def test_update_fields_contains_status(self):
        assert "status" in QueueSchema.UPDATE_FIELDS

    def test_all_fields_is_frozenset(self):
        assert isinstance(QueueSchema.ALL_FIELDS, frozenset)


# ===========================================================================
# BatchSchema
# ===========================================================================

class TestBatchSchema:
    def test_column_names_derived_from_columns(self):
        expected = tuple(col.name for col in BatchSchema.COLUMNS)
        assert BatchSchema.COLUMN_NAMES == expected

    def test_batch_id_in_column_names(self):
        assert "batch_id" in BatchSchema.COLUMN_NAMES

    def test_row_to_dict_returns_dict(self):
        n = len(BatchSchema.COLUMN_NAMES)
        row = tuple(range(n))
        result = BatchSchema.row_to_dict(row)
        assert isinstance(result, dict)
        assert len(result) == n

    def test_row_to_dict_correct_keys(self):
        n = len(BatchSchema.COLUMN_NAMES)
        row = tuple(range(n))
        result = BatchSchema.row_to_dict(row)
        assert list(result.keys()) == list(BatchSchema.COLUMN_NAMES)

    def test_select_columns_is_tuple(self):
        assert isinstance(BatchSchema.SELECT_COLUMNS, tuple)

    def test_update_fields_excludes_batch_id(self):
        assert "batch_id" not in BatchSchema.UPDATE_FIELDS

    def test_status_in_update_fields(self):
        assert "status" in BatchSchema.UPDATE_FIELDS


# ===========================================================================
# Legacy compatibility aliases
# ===========================================================================

class TestLegacyAliases:
    def test_recording_fields_equals_all_fields(self):
        assert RECORDING_FIELDS == RecordingSchema.ALL_FIELDS

    def test_recording_insert_fields_equals_insert_fields(self):
        assert RECORDING_INSERT_FIELDS == RecordingSchema.INSERT_FIELDS

    def test_recording_update_fields_equals_update_fields(self):
        assert RECORDING_UPDATE_FIELDS == RecordingSchema.UPDATE_FIELDS

    def test_queue_update_fields_equals_queue_schema(self):
        assert QUEUE_UPDATE_FIELDS == QueueSchema.UPDATE_FIELDS

    def test_batch_update_fields_equals_batch_schema(self):
        assert BATCH_UPDATE_FIELDS == BatchSchema.UPDATE_FIELDS

    def test_recording_columns_is_list(self):
        assert isinstance(RECORDING_COLUMNS, list)

    def test_recording_columns_extended_is_list(self):
        assert isinstance(RECORDING_COLUMNS_EXTENDED, list)

    def test_recording_columns_matches_basic_columns(self):
        assert RECORDING_COLUMNS == list(RecordingSchema.BASIC_COLUMNS)

    def test_recording_columns_extended_matches_select_columns(self):
        assert RECORDING_COLUMNS_EXTENDED == list(RecordingSchema.SELECT_COLUMNS)
