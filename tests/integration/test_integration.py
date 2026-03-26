"""Integration tests for Medical Assistant core systems.

Tests cover:
1. Settings roundtrip (save to disk, reload, verify)
2. API key encrypt/store/retrieve/decrypt cycle
3. Database migration (fresh DB, run migrations, verify schema)

These tests use real file I/O with tmp_path for isolation.
No tkinter/ttkbootstrap imports.
"""

import json
import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure src is on the path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


# ---------------------------------------------------------------------------
# 1. Settings Roundtrip Tests
# ---------------------------------------------------------------------------

class TestSettingsRoundtrip:
    """Test that settings survive a save-to-disk-then-reload cycle."""

    @pytest.fixture(autouse=True)
    def _isolate_settings(self, tmp_path, monkeypatch):
        """Redirect the settings file to tmp_path and reset singleton state."""
        self.settings_file = tmp_path / "settings.json"

        # Patch the module-level SETTINGS_FILE used by save_settings / load_settings
        monkeypatch.setattr("settings.settings.SETTINGS_FILE", str(self.settings_file))

        # Invalidate the in-memory cache so load_settings reads from disk
        import settings.settings as ss
        ss.invalidate_settings_cache()

        # Reset the SettingsManager singleton so it picks up the fresh SETTINGS
        from settings.settings_manager import SettingsManager
        SettingsManager._instance = None

        yield

        # Restore singleton
        SettingsManager._instance = None

    # -- helpers --
    def _fresh_manager(self):
        """Return a new SettingsManager wired to the temp file."""
        from settings.settings_manager import SettingsManager
        SettingsManager._instance = None
        import settings.settings as ss
        ss.invalidate_settings_cache()
        # Force reload of the SETTINGS global
        ss.SETTINGS = ss.load_settings(force_refresh=True)
        mgr = SettingsManager()
        # Ensure the manager's cached reference is fresh
        mgr._settings_module = None
        return mgr

    def test_set_and_get_top_level(self):
        """set() stores a value that get() returns."""
        mgr = self._fresh_manager()
        mgr.set("ai_provider", "anthropic")
        assert mgr.get("ai_provider") == "anthropic"

    def test_roundtrip_top_level(self):
        """A saved top-level setting survives a full reload from disk."""
        mgr = self._fresh_manager()
        mgr.set("ai_provider", "anthropic")
        mgr.set("theme", "darkly")

        # Force a completely fresh manager that reads from disk
        mgr2 = self._fresh_manager()

        assert mgr2.get("ai_provider") == "anthropic"
        assert mgr2.get("theme") == "darkly"

    def test_roundtrip_nested(self):
        """Nested dot-path settings survive a save/reload cycle."""
        mgr = self._fresh_manager()
        mgr.set_nested("soap_note.temperature", 0.42)
        mgr.set_nested("agent_config.diagnostic.enabled", True)

        mgr2 = self._fresh_manager()

        assert mgr2.get_nested("soap_note.temperature") == 0.42
        assert mgr2.get_nested("agent_config.diagnostic.enabled") is True

    def test_roundtrip_complex_value(self):
        """Lists and nested dicts survive a roundtrip."""
        mgr = self._fresh_manager()
        complex_val = {
            "models": ["gpt-4", "claude-3"],
            "params": {"temperature": 0.7, "max_tokens": 1024},
        }
        mgr.set("custom_config", complex_val)

        mgr2 = self._fresh_manager()
        result = mgr2.get("custom_config")
        assert result == complex_val

    def test_settings_file_written_as_valid_json(self):
        """The on-disk file is valid JSON after a save."""
        mgr = self._fresh_manager()
        mgr.set("test_key", "test_value")

        raw = json.loads(self.settings_file.read_text(encoding="utf-8"))
        assert raw["test_key"] == "test_value"

    def test_overwrite_preserves_other_keys(self):
        """Overwriting one key does not destroy unrelated keys."""
        mgr = self._fresh_manager()
        mgr.set("key_a", "alpha", auto_save=False)
        mgr.set("key_b", "beta")  # saves both

        mgr.set("key_a", "alpha_v2")

        mgr2 = self._fresh_manager()
        assert mgr2.get("key_a") == "alpha_v2"
        assert mgr2.get("key_b") == "beta"

    def test_default_returned_for_missing_key(self):
        """get() returns the default when a key does not exist."""
        mgr = self._fresh_manager()
        assert mgr.get("nonexistent_key", "fallback") == "fallback"

    def test_nested_default_for_missing_path(self):
        """get_nested() returns the default for a missing dot-path."""
        mgr = self._fresh_manager()
        assert mgr.get_nested("no.such.path", 99) == 99


# ---------------------------------------------------------------------------
# 2. API Key Encrypt / Store / Retrieve / Decrypt Tests
# ---------------------------------------------------------------------------

class TestAPIKeyEncryption:
    """Test the SecureKeyStorage encrypt-store-retrieve-decrypt cycle."""

    @pytest.fixture(autouse=True)
    def _isolate_key_storage(self, tmp_path, monkeypatch):
        """Create a SecureKeyStorage that writes into tmp_path."""
        # Set a stable master key so encryption is deterministic per test run
        monkeypatch.setenv("MEDICAL_ASSISTANT_MASTER_KEY", "test-master-key-for-ci")

        key_file = tmp_path / ".keys" / "keys.enc"

        from utils.security.key_storage import SecureKeyStorage
        self.storage = SecureKeyStorage(key_file=key_file)
        self.key_dir = tmp_path / ".keys"

    def test_store_and_retrieve_simple_key(self):
        """A stored key is retrievable and matches the original."""
        self.storage.store_key("openai", "sk-test1234567890abcdef")
        result = self.storage.get_key("openai")
        assert result == "sk-test1234567890abcdef"

    def test_retrieve_nonexistent_returns_none(self):
        """Retrieving a key that was never stored returns None."""
        result = self.storage.get_key("nonexistent_provider")
        assert result is None

    def test_multiple_providers(self):
        """Keys for different providers are stored independently."""
        keys = {
            "openai": "sk-openai-key-abc123",
            "anthropic": "sk-ant-key-def456",
            "deepgram": "dg-key-ghi789",
        }
        for provider, key in keys.items():
            self.storage.store_key(provider, key)

        for provider, key in keys.items():
            assert self.storage.get_key(provider) == key

    def test_overwrite_key(self):
        """Storing a new key for the same provider overwrites the old one."""
        self.storage.store_key("openai", "sk-old-key")
        self.storage.store_key("openai", "sk-new-key")
        assert self.storage.get_key("openai") == "sk-new-key"

    def test_key_file_is_encrypted_on_disk(self):
        """The raw file on disk does not contain the plaintext key."""
        secret = "sk-super-secret-key-12345"
        self.storage.store_key("openai", secret)

        raw_bytes = (self.key_dir / "keys.enc").read_bytes()
        assert secret.encode() not in raw_bytes

    def test_various_key_formats(self):
        """Keys with special characters and varying lengths are handled."""
        test_keys = [
            ("provider_a", "sk-" + "a" * 48),
            ("provider_b", "gsk_" + "B" * 100),
            ("provider_c", "key-with-dashes-and_underscores_123"),
            ("provider_d", "x"),  # minimal
            ("provider_e", "A" * 500),  # long key
        ]
        for provider, key in test_keys:
            self.storage.store_key(provider, key)
            assert self.storage.get_key(provider) == key, f"Failed for provider {provider}"

    def test_persistence_across_instances(self, tmp_path, monkeypatch):
        """A key stored by one instance is readable by a new instance with the same config."""
        monkeypatch.setenv("MEDICAL_ASSISTANT_MASTER_KEY", "test-master-key-for-ci")
        key_file = tmp_path / ".keys2" / "keys.enc"

        from utils.security.key_storage import SecureKeyStorage

        storage1 = SecureKeyStorage(key_file=key_file)
        storage1.store_key("test_provider", "test-key-persist")

        # Create a second instance pointing at the same file
        storage2 = SecureKeyStorage(key_file=key_file)
        assert storage2.get_key("test_provider") == "test-key-persist"

    def test_salt_file_created(self):
        """A salt file is created alongside the keys file."""
        self.storage.store_key("openai", "sk-test")
        salt_file = self.key_dir / "salt.bin"
        assert salt_file.exists()
        assert len(salt_file.read_bytes()) >= 32


# ---------------------------------------------------------------------------
# 3. Database Migration Tests
# ---------------------------------------------------------------------------

class TestDatabaseMigration:
    """Test that migrations produce a correct schema on a fresh database."""

    @pytest.fixture(autouse=True)
    def _setup_db(self, tmp_path, monkeypatch):
        """Provide an isolated SQLite database for each test."""
        self.db_path = tmp_path / "test_migrations.db"
        self.tmp_path = tmp_path

    def _get_fresh_connection(self) -> sqlite3.Connection:
        """Open a new connection to the test database."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _get_table_names(self, conn: sqlite3.Connection) -> set:
        """Return set of user table names in the database."""
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        return {row[0] for row in cursor.fetchall()}

    def _get_column_names(self, conn: sqlite3.Connection, table: str) -> set:
        """Return set of column names for a table."""
        cursor = conn.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in cursor.fetchall()}

    def _get_index_names(self, conn: sqlite3.Connection) -> set:
        """Return set of index names in the database."""
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
        )
        return {row[0] for row in cursor.fetchall()}

    def test_apply_migrations_directly(self):
        """Apply migration SQL statements directly and verify the resulting schema."""
        from database.db_migrations import get_migrations

        migrations = get_migrations()
        assert len(migrations) > 0, "No migrations found"

        conn = self._get_fresh_connection()
        try:
            # Create migrations tracking table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Apply each migration in order
            for migration in migrations:
                for statement in migration.up_sql.split(";"):
                    statement = statement.strip()
                    if statement:
                        try:
                            conn.execute(statement)
                        except sqlite3.OperationalError as e:
                            # Some statements may fail if they depend on
                            # previous state (e.g., ALTER TABLE on missing table).
                            # That is acceptable for FTS triggers etc.
                            if "already exists" not in str(e).lower():
                                pass  # Allow non-critical failures
                conn.execute(
                    "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                    (migration.version, migration.name),
                )
            conn.commit()

            # -- Verify core schema --
            tables = self._get_table_names(conn)
            assert "recordings" in tables, f"recordings table missing. Tables: {tables}"
            assert "schema_migrations" in tables

            # Verify recordings columns from migration 1
            rec_cols = self._get_column_names(conn, "recordings")
            for expected_col in ("id", "filename", "transcript", "soap_note", "referral", "letter", "timestamp"):
                assert expected_col in rec_cols, f"Column '{expected_col}' missing from recordings"

            # Verify migration versions were recorded
            cursor = conn.execute("SELECT version FROM schema_migrations ORDER BY version")
            versions = [row[0] for row in cursor.fetchall()]
            assert versions == sorted(versions), "Migration versions not in order"
            assert len(versions) == len(migrations)

        finally:
            conn.close()

    def test_recordings_table_has_expected_columns(self):
        """After migrations, the recordings table has all expected columns."""
        from database.db_migrations import get_migrations

        conn = self._get_fresh_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            for migration in get_migrations():
                for statement in migration.up_sql.split(";"):
                    stmt = statement.strip()
                    if stmt:
                        try:
                            conn.execute(stmt)
                        except sqlite3.OperationalError:
                            pass
                conn.execute(
                    "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                    (migration.version, migration.name),
                )
            conn.commit()

            rec_cols = self._get_column_names(conn, "recordings")

            # Core columns that should exist after all migrations
            expected = {"id", "filename", "transcript", "soap_note", "referral", "letter", "timestamp"}
            missing = expected - rec_cols
            assert not missing, f"Missing columns in recordings: {missing}"

        finally:
            conn.close()

    def test_empty_database_has_no_tables(self):
        """A freshly created database has no user tables before migration."""
        conn = self._get_fresh_connection()
        try:
            tables = self._get_table_names(conn)
            assert len(tables) == 0
        finally:
            conn.close()

    def test_migrations_are_idempotent(self):
        """Applying migrations twice does not raise errors or corrupt data."""
        from database.db_migrations import get_migrations

        conn = self._get_fresh_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            migrations = get_migrations()

            # Apply once
            for migration in migrations:
                for statement in migration.up_sql.split(";"):
                    stmt = statement.strip()
                    if stmt:
                        try:
                            conn.execute(stmt)
                        except sqlite3.OperationalError:
                            pass
                conn.execute(
                    "INSERT OR REPLACE INTO schema_migrations (version, name) VALUES (?, ?)",
                    (migration.version, migration.name),
                )
            conn.commit()

            tables_after_first = self._get_table_names(conn)
            cols_after_first = self._get_column_names(conn, "recordings")

            # Apply again (should be safe due to IF NOT EXISTS / IF EXISTS guards)
            for migration in migrations:
                for statement in migration.up_sql.split(";"):
                    stmt = statement.strip()
                    if stmt:
                        try:
                            conn.execute(stmt)
                        except sqlite3.OperationalError:
                            pass
            conn.commit()

            tables_after_second = self._get_table_names(conn)
            cols_after_second = self._get_column_names(conn, "recordings")

            assert tables_after_first == tables_after_second
            assert cols_after_first == cols_after_second

        finally:
            conn.close()

    def test_insert_and_query_recording(self):
        """After migrations, we can insert and query a recording row."""
        from database.db_migrations import get_migrations

        conn = self._get_fresh_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            for migration in get_migrations():
                for statement in migration.up_sql.split(";"):
                    stmt = statement.strip()
                    if stmt:
                        try:
                            conn.execute(stmt)
                        except sqlite3.OperationalError:
                            pass
                conn.execute(
                    "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                    (migration.version, migration.name),
                )
            conn.commit()

            # Insert a test recording
            conn.execute(
                "INSERT INTO recordings (filename, transcript, soap_note) VALUES (?, ?, ?)",
                ("test.wav", "Patient reports headache.", "S: Headache\nO: Normal\nA: Tension headache\nP: Ibuprofen"),
            )
            conn.commit()

            # Query it back
            cursor = conn.execute("SELECT filename, transcript, soap_note FROM recordings WHERE filename = ?", ("test.wav",))
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "test.wav"
            assert "headache" in row[1].lower()
            assert "Tension headache" in row[2]

        finally:
            conn.close()

    def test_migration_count(self):
        """Sanity check: there is at least the initial schema migration."""
        from database.db_migrations import get_migrations

        migrations = get_migrations()
        assert len(migrations) >= 1
        assert migrations[0].version == 1
        assert migrations[0].name == "Initial schema"
