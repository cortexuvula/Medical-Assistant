"""Extended tests for MigrationManager class methods.

Tests migrate(), rollback(), get_applied_migrations(), get_pending_migrations(),
_apply_migration_12(), and run_migrations() using mocked db_manager.
"""

import sqlite3
import tempfile
import os
import pytest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch, call


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_migration(version, name="migration", up_sql="SELECT 1", down_sql=None):
    from database.db_migrations import Migration
    return Migration(version=version, name=name, up_sql=up_sql, down_sql=down_sql)


def _make_db_manager(current_version=0, applied_rows=None):
    """Create a mock db_manager with configurable responses."""
    if applied_rows is None:
        applied_rows = []

    mock_db = MagicMock()
    # fetchone: MAX(version) query
    if current_version == 0:
        mock_db.fetchone.return_value = (None,)
    else:
        mock_db.fetchone.return_value = (current_version,)
    # fetchall: applied migrations
    mock_db.fetchall.return_value = applied_rows
    # execute: no-op
    mock_db.execute.return_value = None

    # transaction() context manager - returns a mock connection
    mock_conn = MagicMock()
    mock_conn.execute.return_value = MagicMock()
    mock_conn.executescript.return_value = None

    @contextmanager
    def _transaction():
        yield mock_conn

    mock_db.transaction = _transaction
    return mock_db, mock_conn


def _make_manager_with_mock_db(current_version=0, applied_rows=None):
    """Create a MigrationManager with a mocked db_manager."""
    mock_db, mock_conn = _make_db_manager(current_version, applied_rows)
    with patch("database.db_migrations.get_db_manager", return_value=mock_db):
        from database.db_migrations import MigrationManager
        manager = MigrationManager()
    return manager, mock_db, mock_conn


# ── MigrationManager initialization ──────────────────────────────────────────

class TestMigrationManagerInit:
    def test_creates_instance(self):
        manager, _, _ = _make_manager_with_mock_db()
        assert manager is not None

    def test_no_migrations_initially(self):
        manager, _, _ = _make_manager_with_mock_db()
        assert manager._migrations == []

    def test_init_creates_migrations_table(self):
        mock_db, _ = _make_db_manager()
        with patch("database.db_migrations.get_db_manager", return_value=mock_db):
            from database.db_migrations import MigrationManager
            MigrationManager()
        mock_db.execute.assert_called_once()
        call_sql = mock_db.execute.call_args[0][0].lower()
        assert "schema_migrations" in call_sql


# ── register ──────────────────────────────────────────────────────────────────

class TestRegister:
    def test_register_adds_migration(self):
        manager, _, _ = _make_manager_with_mock_db()
        m = _make_migration(1, "create_table")
        manager.register(m)
        assert len(manager._migrations) == 1

    def test_migrations_sorted_by_version(self):
        manager, _, _ = _make_manager_with_mock_db()
        manager.register(_make_migration(3, "third"))
        manager.register(_make_migration(1, "first"))
        manager.register(_make_migration(2, "second"))
        versions = [m.version for m in manager._migrations]
        assert versions == [1, 2, 3]


# ── get_current_version ───────────────────────────────────────────────────────

class TestGetCurrentVersion:
    def test_returns_zero_when_no_migrations(self):
        manager, _, _ = _make_manager_with_mock_db(current_version=0)
        assert manager.get_current_version() == 0

    def test_returns_latest_version(self):
        manager, _, _ = _make_manager_with_mock_db(current_version=5)
        assert manager.get_current_version() == 5

    def test_handles_none_from_db(self):
        mock_db, _ = _make_db_manager()
        mock_db.fetchone.return_value = (None,)
        with patch("database.db_migrations.get_db_manager", return_value=mock_db):
            from database.db_migrations import MigrationManager
            manager = MigrationManager()
        assert manager.get_current_version() == 0


# ── get_applied_migrations ────────────────────────────────────────────────────

class TestGetAppliedMigrations:
    def test_returns_empty_when_none_applied(self):
        manager, _, _ = _make_manager_with_mock_db(applied_rows=[])
        result = manager.get_applied_migrations()
        assert result == []

    def test_returns_list_of_dicts(self):
        rows = [(1, "create_table", "2024-01-01")]
        manager, mock_db, _ = _make_manager_with_mock_db(applied_rows=rows)
        mock_db.fetchall.return_value = rows
        result = manager.get_applied_migrations()
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["version"] == 1
        assert result[0]["name"] == "create_table"

    def test_multiple_applied_migrations(self):
        rows = [
            (1, "first", "2024-01-01"),
            (2, "second", "2024-01-02"),
            (3, "third", "2024-01-03"),
        ]
        manager, mock_db, _ = _make_manager_with_mock_db()
        mock_db.fetchall.return_value = rows
        result = manager.get_applied_migrations()
        assert len(result) == 3
        assert result[2]["version"] == 3


# ── get_pending_migrations ────────────────────────────────────────────────────

class TestGetPendingMigrations:
    def test_all_pending_when_version_zero(self):
        manager, _, _ = _make_manager_with_mock_db(current_version=0)
        manager.register(_make_migration(1))
        manager.register(_make_migration(2))
        pending = manager.get_pending_migrations()
        assert len(pending) == 2

    def test_none_pending_when_up_to_date(self):
        manager, _, _ = _make_manager_with_mock_db(current_version=3)
        manager.register(_make_migration(1))
        manager.register(_make_migration(2))
        manager.register(_make_migration(3))
        pending = manager.get_pending_migrations()
        assert pending == []

    def test_partial_pending(self):
        manager, _, _ = _make_manager_with_mock_db(current_version=2)
        manager.register(_make_migration(1))
        manager.register(_make_migration(2))
        manager.register(_make_migration(3))
        pending = manager.get_pending_migrations()
        assert len(pending) == 1
        assert pending[0].version == 3


# ── migrate ───────────────────────────────────────────────────────────────────

class TestMigrate:
    def test_returns_zero_when_nothing_to_migrate(self):
        """Already at latest version: migrate() should do nothing."""
        manager, mock_db, _ = _make_manager_with_mock_db(current_version=3)
        manager.register(_make_migration(1))
        manager.register(_make_migration(2))
        manager.register(_make_migration(3))
        # Patch get_current_version to always return 3 (up to date)
        from unittest.mock import patch as _patch
        with _patch.object(manager, 'get_current_version', return_value=3), \
             _patch.object(manager, 'get_pending_migrations', return_value=[]):
            count = manager.migrate()
        assert count == 0

    def test_applies_pending_migrations(self):
        """When 2 migrations are pending they should both be applied."""
        manager, mock_db, mock_conn = _make_manager_with_mock_db(current_version=0)
        m1 = _make_migration(1, "first", "CREATE TABLE t1 (id INTEGER)")
        m2 = _make_migration(2, "second", "CREATE TABLE t2 (id INTEGER)")
        manager.register(m1)
        manager.register(m2)

        applied = []
        original_apply = manager._apply_migration

        def track_apply(migration):
            applied.append(migration.version)

        from unittest.mock import patch as _patch
        with _patch.object(manager, 'get_current_version', return_value=0), \
             _patch.object(manager, 'get_pending_migrations', return_value=[m1, m2]), \
             _patch.object(manager, '_apply_migration', side_effect=track_apply):
            count = manager.migrate()

        assert count == 2
        assert applied == [1, 2]

    def test_applies_migrations_up_to_target(self):
        """Migrations beyond target_version should be skipped."""
        manager, mock_db, mock_conn = _make_manager_with_mock_db(current_version=0)
        m1 = _make_migration(1, "first", "CREATE TABLE t1 (id INTEGER)")
        m2 = _make_migration(2, "second", "CREATE TABLE t2 (id INTEGER)")
        m3 = _make_migration(3, "third", "CREATE TABLE t3 (id INTEGER)")
        manager.register(m1)
        manager.register(m2)
        manager.register(m3)

        applied = []
        from unittest.mock import patch as _patch
        with _patch.object(manager, 'get_current_version', return_value=0), \
             _patch.object(manager, 'get_pending_migrations', return_value=[m1, m2, m3]), \
             _patch.object(manager, '_apply_migration', side_effect=lambda m: applied.append(m.version)):
            count = manager.migrate(target_version=2)

        assert count == 2
        assert 3 not in applied

    def test_migrate_records_each_migration(self):
        """_apply_migration should be called for each pending migration."""
        manager, mock_db, mock_conn = _make_manager_with_mock_db(current_version=0)
        m1 = _make_migration(1, "first", "CREATE TABLE t1 (id INTEGER)")
        manager.register(m1)

        # Use real _apply_migration to check conn.execute is called
        from unittest.mock import patch as _patch
        with _patch.object(manager, 'get_current_version', return_value=0), \
             _patch.object(manager, 'get_pending_migrations', return_value=[m1]):
            manager.migrate()

        # Verify INSERT into schema_migrations was called
        insert_calls = [
            c for c in mock_conn.execute.call_args_list
            if "INSERT" in str(c)
        ]
        assert len(insert_calls) >= 1

    def test_migration_failure_raises_database_error(self):
        """A failing migration should raise DatabaseError."""
        from utils.exceptions import DatabaseError
        manager, mock_db, mock_conn = _make_manager_with_mock_db(current_version=0)
        m1 = _make_migration(1, "bad_migration", "INVALID SQL THAT FAILS")
        manager.register(m1)

        # Make conn.execute raise an error
        mock_conn.execute.side_effect = Exception("SQL execution failed")

        from unittest.mock import patch as _patch
        with _patch.object(manager, 'get_current_version', return_value=0), \
             _patch.object(manager, 'get_pending_migrations', return_value=[m1]):
            with pytest.raises(DatabaseError) as exc_info:
                manager.migrate()
        assert "Migration 1" in str(exc_info.value)

    def test_no_migrations_registered_returns_zero(self):
        """No registered migrations → migrate() returns 0."""
        manager, mock_db, _ = _make_manager_with_mock_db(current_version=0)
        # No migrations registered, target_version would be 0
        from unittest.mock import patch as _patch
        with _patch.object(manager, 'get_current_version', return_value=0), \
             _patch.object(manager, 'get_pending_migrations', return_value=[]):
            count = manager.migrate()
        assert count == 0


# ── _apply_migration ──────────────────────────────────────────────────────────

class TestApplyMigration:
    def test_single_statement_uses_execute(self):
        manager, mock_db, mock_conn = _make_manager_with_mock_db()
        migration = _make_migration(1, "test", "CREATE TABLE t (id INTEGER)")
        manager._apply_migration(migration)
        # execute should be called (no semicolons in single statement)
        mock_conn.execute.assert_called()

    def test_multi_statement_uses_executescript(self):
        manager, mock_db, mock_conn = _make_manager_with_mock_db()
        up_sql = "CREATE TABLE a (id INTEGER); CREATE TABLE b (id INTEGER);"
        migration = _make_migration(1, "multi", up_sql)
        manager._apply_migration(migration)
        mock_conn.executescript.assert_called_once()


# ── _apply_migration_12 ────────────────────────────────────────────────────────

class TestApplyMigration12:
    def test_adds_patient_name_when_missing(self):
        manager, _, _ = _make_manager_with_mock_db()
        mock_conn = MagicMock()
        # PRAGMA returns columns WITHOUT patient_name
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (0, "id", "INTEGER", 0, None, 1),
            (1, "timestamp", "TEXT", 0, None, 0),
        ]
        mock_conn.execute.return_value = mock_cursor
        manager._apply_migration_12(mock_conn)
        # Check ALTER TABLE was called
        alter_calls = [c for c in mock_conn.execute.call_args_list if "ALTER TABLE" in str(c)]
        assert len(alter_calls) == 1

    def test_skips_patient_name_when_exists(self):
        manager, _, _ = _make_manager_with_mock_db()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # PRAGMA returns columns WITH patient_name
        mock_cursor.fetchall.return_value = [
            (0, "id", "INTEGER", 0, None, 1),
            (1, "patient_name", "TEXT", 0, None, 0),
        ]
        mock_conn.execute.return_value = mock_cursor
        manager._apply_migration_12(mock_conn)
        # No ALTER TABLE should be called
        alter_calls = [c for c in mock_conn.execute.call_args_list if "ALTER TABLE" in str(c)]
        assert len(alter_calls) == 0

    def test_creates_indices_regardless(self):
        manager, _, _ = _make_manager_with_mock_db()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (0, "id", "INTEGER", 0, None, 1),
            (1, "patient_name", "TEXT", 0, None, 0),
        ]
        mock_conn.execute.return_value = mock_cursor
        manager._apply_migration_12(mock_conn)
        index_calls = [c for c in mock_conn.execute.call_args_list if "CREATE INDEX" in str(c)]
        assert len(index_calls) == 2


# ── rollback ─────────────────────────────────────────────────────────────────

class TestRollback:
    def test_returns_zero_when_nothing_to_rollback(self):
        manager, mock_db, _ = _make_manager_with_mock_db(current_version=0)
        count = manager.rollback()
        assert count == 0

    def test_rollback_already_at_target_returns_zero(self):
        manager, mock_db, _ = _make_manager_with_mock_db(current_version=3)
        # target_version=3 means already there
        count = manager.rollback(target_version=3)
        assert count == 0

    def test_rollback_requires_down_sql(self):
        from utils.exceptions import DatabaseError
        manager, mock_db, _ = _make_manager_with_mock_db(current_version=2)
        # Register migrations without down_sql
        manager.register(_make_migration(1, "first", "CREATE TABLE t1 (id INTEGER)"))
        manager.register(_make_migration(2, "second", "CREATE TABLE t2 (id INTEGER)"))
        with pytest.raises(DatabaseError) as exc_info:
            manager.rollback(target_version=0)
        assert "no down_sql" in str(exc_info.value).lower()

    def test_rollback_applies_down_sql(self):
        manager, mock_db, mock_conn = _make_manager_with_mock_db(current_version=2)
        manager.register(_make_migration(1, "first", "CREATE TABLE t1 (id INTEGER)", "DROP TABLE t1"))
        manager.register(_make_migration(2, "second", "CREATE TABLE t2 (id INTEGER)", "DROP TABLE t2"))
        count = manager.rollback(target_version=0)
        assert count == 2

    def test_rollback_deletes_migration_records(self):
        manager, mock_db, mock_conn = _make_manager_with_mock_db(current_version=1)
        manager.register(_make_migration(1, "first", "CREATE TABLE t1 (id INTEGER)", "DROP TABLE t1"))
        manager.rollback(target_version=0)
        delete_calls = [c for c in mock_conn.execute.call_args_list if "DELETE" in str(c)]
        assert len(delete_calls) >= 1

    def test_rollback_failure_raises_database_error(self):
        from utils.exceptions import DatabaseError
        manager, mock_db, mock_conn = _make_manager_with_mock_db(current_version=1)
        manager.register(_make_migration(1, "first", "CREATE TABLE t (id INTEGER)", "DROP TABLE t"))
        mock_conn.execute.side_effect = Exception("DB error")
        with pytest.raises(DatabaseError) as exc_info:
            manager.rollback(target_version=0)
        assert "Rollback" in str(exc_info.value)


# ── _rollback_migration ───────────────────────────────────────────────────────

class TestRollbackMigration:
    def test_single_statement_down_sql_uses_execute(self):
        manager, mock_db, mock_conn = _make_manager_with_mock_db()
        migration = _make_migration(1, "test", "CREATE TABLE t (id INTEGER)", "DROP TABLE t")
        manager._rollback_migration(migration)
        mock_conn.execute.assert_called()

    def test_multi_statement_down_sql_uses_executescript(self):
        manager, mock_db, mock_conn = _make_manager_with_mock_db()
        down_sql = "DROP TABLE a; DROP TABLE b;"
        migration = _make_migration(1, "multi", "CREATE TABLE a (id INTEGER); CREATE TABLE b (id INTEGER);", down_sql)
        manager._rollback_migration(migration)
        mock_conn.executescript.assert_called_once()


# ── run_migrations ────────────────────────────────────────────────────────────

class TestRunMigrations:
    def test_run_migrations_does_nothing_when_up_to_date(self):
        """When all migrations are applied, run_migrations is a no-op."""
        from database.db_migrations import MigrationManager
        mock_manager = MagicMock(spec=MigrationManager)
        mock_manager.get_current_version.return_value = 3
        mock_manager.get_pending_migrations.return_value = []

        with patch("database.db_migrations.get_migration_manager", return_value=mock_manager):
            import database.db_migrations as dbm
            dbm.run_migrations()

        mock_manager.migrate.assert_not_called()

    def test_run_migrations_applies_pending(self):
        """When pending migrations exist, they should be applied."""
        from database.db_migrations import MigrationManager, Migration
        mock_manager = MagicMock(spec=MigrationManager)
        mock_manager.get_current_version.return_value = 0
        mock_manager.get_pending_migrations.return_value = [
            Migration(1, "first", "CREATE TABLE t1 (id INTEGER)")
        ]
        mock_manager.migrate.return_value = 1

        with patch("database.db_migrations.get_migration_manager", return_value=mock_manager):
            import database.db_migrations as dbm
            dbm.run_migrations()

        mock_manager.migrate.assert_called_once()

    def test_run_migrations_raises_on_failure(self):
        """DatabaseError from migrate() should propagate."""
        from utils.exceptions import DatabaseError
        from database.db_migrations import MigrationManager, Migration
        mock_manager = MagicMock(spec=MigrationManager)
        mock_manager.get_current_version.return_value = 0
        mock_manager.get_pending_migrations.return_value = [
            Migration(1, "first", "INVALID SQL")
        ]
        mock_manager.migrate.side_effect = DatabaseError("Migration failed")

        with patch("database.db_migrations.get_migration_manager", return_value=mock_manager):
            import database.db_migrations as dbm
            with pytest.raises(DatabaseError):
                dbm.run_migrations()
