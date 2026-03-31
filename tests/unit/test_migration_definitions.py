"""
Tests for Migration and get_all_migrations in src/database/migration_definitions.py

Covers Migration dataclass (required fields, optional down_sql, field storage);
get_all_migrations() list structure (length, versions in order, non-empty SQL,
no duplicate versions, names are strings).
No network, no Tkinter, no actual DB connections.
"""

import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from database.db_migrations import Migration
from database.migration_definitions import get_all_migrations


# ===========================================================================
# Migration class
# ===========================================================================

class TestMigration:
    def test_version_stored(self):
        m = Migration(version=5, name="test", up_sql="CREATE TABLE t (id INT)")
        assert m.version == 5

    def test_name_stored(self):
        m = Migration(version=1, name="Initial schema", up_sql="CREATE TABLE t (id INT)")
        assert m.name == "Initial schema"

    def test_up_sql_stored(self):
        sql = "CREATE TABLE patients (id INT PRIMARY KEY)"
        m = Migration(version=1, name="n", up_sql=sql)
        assert m.up_sql == sql

    def test_down_sql_none_by_default(self):
        m = Migration(version=1, name="n", up_sql="CREATE TABLE t (id INT)")
        assert m.down_sql is None

    def test_down_sql_stored_when_provided(self):
        m = Migration(version=1, name="n", up_sql="CREATE TABLE t (id INT)",
                      down_sql="DROP TABLE t")
        assert m.down_sql == "DROP TABLE t"

    def test_version_is_int(self):
        m = Migration(version=3, name="n", up_sql="sql")
        assert isinstance(m.version, int)

    def test_name_is_str(self):
        m = Migration(version=1, name="my migration", up_sql="sql")
        assert isinstance(m.name, str)

    def test_up_sql_is_str(self):
        m = Migration(version=1, name="n", up_sql="CREATE TABLE x (id INT)")
        assert isinstance(m.up_sql, str)


# ===========================================================================
# get_all_migrations
# ===========================================================================

class TestGetAllMigrations:
    @pytest.fixture(autouse=True)
    def migrations(self):
        self.migs = get_all_migrations()

    def test_returns_list(self):
        assert isinstance(self.migs, list)

    def test_list_non_empty(self):
        assert len(self.migs) > 0

    def test_at_least_ten_migrations(self):
        assert len(self.migs) >= 10

    def test_exactly_seventeen_migrations(self):
        # Current count is 17 — update if migrations are added
        assert len(self.migs) == 17

    def test_all_migration_instances(self):
        for m in self.migs:
            assert isinstance(m, Migration)

    def test_first_version_is_one(self):
        assert self.migs[0].version == 1

    def test_versions_in_ascending_order(self):
        versions = [m.version for m in self.migs]
        assert versions == sorted(versions)

    def test_no_duplicate_versions(self):
        versions = [m.version for m in self.migs]
        assert len(versions) == len(set(versions))

    def test_all_up_sql_non_empty(self):
        for m in self.migs:
            assert len(m.up_sql.strip()) > 0, f"Migration v{m.version} has empty up_sql"

    def test_all_names_are_strings(self):
        for m in self.migs:
            assert isinstance(m.name, str)

    def test_all_names_non_empty(self):
        for m in self.migs:
            assert len(m.name.strip()) > 0, f"Migration v{m.version} has empty name"

    def test_versions_are_ints(self):
        for m in self.migs:
            assert isinstance(m.version, int)

    def test_first_migration_creates_recordings_table(self):
        first = self.migs[0]
        assert "recordings" in first.up_sql.lower()

    def test_first_migration_has_down_sql(self):
        # First migration should have a rollback
        assert self.migs[0].down_sql is not None

    def test_versions_start_at_one_end_at_count(self):
        # Versions are a contiguous sequence starting at 1
        versions = sorted(m.version for m in self.migs)
        expected = list(range(1, len(self.migs) + 1))
        assert versions == expected

    def test_returns_new_list_each_call(self):
        # Each call returns a fresh list (not a shared reference)
        list1 = get_all_migrations()
        list2 = get_all_migrations()
        assert list1 is not list2

    def test_up_sql_contains_sql_keywords(self):
        for m in self.migs:
            # Each up_sql should contain at least one SQL keyword
            sql_lower = m.up_sql.lower()
            has_sql = any(kw in sql_lower for kw in
                          ["create", "alter", "insert", "drop", "update", "--"])
            assert has_sql, f"Migration v{m.version} up_sql has no SQL keywords"
