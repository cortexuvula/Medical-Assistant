"""
Tests for src/database/schema.py

Covers ColumnType enum; ColumnDefinition.to_sql() (primary key, autoincrement,
nullable, default string/int/bool); RecordingSchema constants (SELECT_COLUMNS,
UPDATE_COLUMNS), is_valid_field, validate_fields, get_select_sql, row_to_dict;
QueueSchema.row_to_dict; BatchSchema.row_to_dict.
No network, no Tkinter, no actual DB connections.
"""

import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from database.schema import (
    ColumnType, ColumnDefinition, RecordingSchema, QueueSchema, BatchSchema
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

    def test_has_boolean(self):
        assert hasattr(ColumnType, "BOOLEAN")

    def test_all_values_are_strings(self):
        for member in ColumnType:
            assert isinstance(member.value, str)


# ===========================================================================
# ColumnDefinition.to_sql
# ===========================================================================

class TestColumnDefinitionToSql:
    def test_primary_key_integer(self):
        cd = ColumnDefinition(name="id", type=ColumnType.INTEGER,
                              primary_key=True, autoincrement=True)
        sql = cd.to_sql()
        assert "id" in sql
        assert "INTEGER" in sql
        assert "PRIMARY KEY" in sql
        assert "AUTOINCREMENT" in sql

    def test_primary_key_without_autoincrement(self):
        cd = ColumnDefinition(name="pk", type=ColumnType.TEXT, primary_key=True)
        sql = cd.to_sql()
        assert "PRIMARY KEY" in sql
        assert "AUTOINCREMENT" not in sql

    def test_not_null_non_primary(self):
        cd = ColumnDefinition(name="filename", type=ColumnType.TEXT, nullable=False)
        sql = cd.to_sql()
        assert "NOT NULL" in sql

    def test_nullable_column_no_not_null(self):
        cd = ColumnDefinition(name="notes", type=ColumnType.TEXT, nullable=True)
        sql = cd.to_sql()
        assert "NOT NULL" not in sql

    def test_default_string_quoted(self):
        cd = ColumnDefinition(name="status", type=ColumnType.TEXT,
                              nullable=True, default="pending")
        sql = cd.to_sql()
        assert "DEFAULT 'pending'" in sql

    def test_default_integer_not_quoted(self):
        cd = ColumnDefinition(name="count", type=ColumnType.INTEGER,
                              nullable=True, default=0)
        sql = cd.to_sql()
        assert "DEFAULT 0" in sql

    def test_default_bool_true_is_1(self):
        cd = ColumnDefinition(name="active", type=ColumnType.INTEGER,
                              nullable=True, default=True)
        sql = cd.to_sql()
        assert "DEFAULT 1" in sql

    def test_default_bool_false_is_0(self):
        cd = ColumnDefinition(name="deleted", type=ColumnType.INTEGER,
                              nullable=True, default=False)
        sql = cd.to_sql()
        assert "DEFAULT 0" in sql

    def test_no_default_no_default_clause(self):
        cd = ColumnDefinition(name="text", type=ColumnType.TEXT)
        assert "DEFAULT" not in cd.to_sql()

    def test_returns_string(self):
        cd = ColumnDefinition(name="x", type=ColumnType.INTEGER)
        assert isinstance(cd.to_sql(), str)

    def test_column_name_in_sql(self):
        cd = ColumnDefinition(name="my_column", type=ColumnType.TEXT)
        assert "my_column" in cd.to_sql()


# ===========================================================================
# RecordingSchema constants
# ===========================================================================

class TestRecordingSchemaConstants:
    def test_select_columns_is_tuple(self):
        assert isinstance(RecordingSchema.SELECT_COLUMNS, tuple)

    def test_select_columns_non_empty(self):
        assert len(RecordingSchema.SELECT_COLUMNS) > 0

    def test_select_columns_has_id(self):
        assert "id" in RecordingSchema.SELECT_COLUMNS

    def test_select_columns_has_filename(self):
        assert "filename" in RecordingSchema.SELECT_COLUMNS

    def test_select_columns_has_transcript(self):
        assert "transcript" in RecordingSchema.SELECT_COLUMNS

    def test_select_columns_has_soap_note(self):
        assert "soap_note" in RecordingSchema.SELECT_COLUMNS

    def test_columns_class_attr_present(self):
        assert hasattr(RecordingSchema, "COLUMNS")

    def test_all_select_columns_are_strings(self):
        for col in RecordingSchema.SELECT_COLUMNS:
            assert isinstance(col, str)


# ===========================================================================
# RecordingSchema.is_valid_field
# ===========================================================================

class TestIsValidField:
    def test_id_is_valid(self):
        assert RecordingSchema.is_valid_field("id") is True

    def test_transcript_is_valid(self):
        assert RecordingSchema.is_valid_field("transcript") is True

    def test_filename_is_valid(self):
        assert RecordingSchema.is_valid_field("filename") is True

    def test_fake_field_invalid(self):
        assert RecordingSchema.is_valid_field("fake_column") is False

    def test_empty_string_invalid(self):
        assert RecordingSchema.is_valid_field("") is False

    def test_returns_bool(self):
        assert isinstance(RecordingSchema.is_valid_field("id"), bool)


# ===========================================================================
# RecordingSchema.validate_fields
# ===========================================================================

class TestValidateFields:
    def test_valid_fields_returned(self):
        result = RecordingSchema.validate_fields(["id", "transcript"])
        assert "id" in result
        assert "transcript" in result

    def test_invalid_fields_raise_value_error(self):
        with pytest.raises(ValueError):
            RecordingSchema.validate_fields(["id", "nonexistent_col"])

    def test_empty_list_returns_empty(self):
        result = RecordingSchema.validate_fields([])
        assert result == [] or isinstance(result, list)

    def test_all_invalid_raises_value_error(self):
        with pytest.raises(ValueError):
            RecordingSchema.validate_fields(["fake1", "fake2"])

    def test_returns_list_for_valid(self):
        assert isinstance(RecordingSchema.validate_fields(["id"]), list)


# ===========================================================================
# RecordingSchema.get_select_sql
# ===========================================================================

class TestGetSelectSql:
    def test_returns_string(self):
        assert isinstance(RecordingSchema.get_select_sql(), str)

    def test_default_contains_id(self):
        assert "id" in RecordingSchema.get_select_sql()

    def test_default_contains_transcript(self):
        assert "transcript" in RecordingSchema.get_select_sql()

    def test_custom_columns_respected(self):
        sql = RecordingSchema.get_select_sql(columns=("id", "filename"))
        assert "id" in sql
        assert "filename" in sql

    def test_non_empty(self):
        assert len(RecordingSchema.get_select_sql().strip()) > 0


# ===========================================================================
# RecordingSchema.row_to_dict
# ===========================================================================

class TestRecordingSchemaRowToDict:
    def test_returns_dict(self):
        # Minimal row matching SELECT_COLUMNS length
        cols = RecordingSchema.SELECT_COLUMNS
        row = tuple(range(len(cols)))
        result = RecordingSchema.row_to_dict(row)
        assert isinstance(result, dict)

    def test_id_mapped(self):
        cols = RecordingSchema.SELECT_COLUMNS
        row = tuple(range(len(cols)))
        result = RecordingSchema.row_to_dict(row)
        assert "id" in result

    def test_custom_columns(self):
        columns = ("id", "filename")
        row = (42, "test.wav")
        result = RecordingSchema.row_to_dict(row, columns=columns)
        assert result["id"] == 42
        assert result["filename"] == "test.wav"


# ===========================================================================
# QueueSchema
# ===========================================================================

class TestQueueSchema:
    def test_has_columns_attribute(self):
        assert hasattr(QueueSchema, "COLUMNS") or hasattr(QueueSchema, "SELECT_COLUMNS")

    def test_row_to_dict_returns_dict(self):
        cols = QueueSchema.COLUMNS if hasattr(QueueSchema, "COLUMNS") else QueueSchema.SELECT_COLUMNS
        n = len(cols)
        result = QueueSchema.row_to_dict(tuple(range(n)))
        assert isinstance(result, dict)


# ===========================================================================
# BatchSchema
# ===========================================================================

class TestBatchSchema:
    def test_has_columns_attribute(self):
        assert hasattr(BatchSchema, "COLUMNS") or hasattr(BatchSchema, "SELECT_COLUMNS")

    def test_row_to_dict_returns_dict(self):
        cols = BatchSchema.COLUMNS if hasattr(BatchSchema, "COLUMNS") else BatchSchema.SELECT_COLUMNS
        n = len(cols)
        result = BatchSchema.row_to_dict(tuple(range(n)))
        assert isinstance(result, dict)
