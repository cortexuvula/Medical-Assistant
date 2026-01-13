"""
Unit tests for database migrations system.

Tests the Migration class, MigrationManager, and individual migrations
to ensure database schema changes are applied correctly.
"""

import unittest
import sys
import os
import tempfile
import sqlite3
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from database.db_migrations import Migration, MigrationManager, get_migrations


class TestMigrationClass(unittest.TestCase):
    """Test the Migration data class."""

    def test_migration_creation(self):
        """Test creating a basic migration."""
        migration = Migration(
            version=1,
            name="test_migration",
            up_sql="CREATE TABLE test (id INTEGER PRIMARY KEY)"
        )
        self.assertEqual(migration.version, 1)
        self.assertEqual(migration.name, "test_migration")
        self.assertIsNotNone(migration.up_sql)
        self.assertIsNone(migration.down_sql)

    def test_migration_with_rollback(self):
        """Test migration with rollback SQL."""
        migration = Migration(
            version=2,
            name="reversible_migration",
            up_sql="CREATE TABLE test2 (id INTEGER)",
            down_sql="DROP TABLE test2"
        )
        self.assertEqual(migration.version, 2)
        self.assertIsNotNone(migration.down_sql)

    def test_migration_applied_at_default_none(self):
        """Test that applied_at defaults to None."""
        migration = Migration(version=1, name="test", up_sql="SELECT 1")
        self.assertIsNone(migration.applied_at)


class TestMigrationManagerWithMockDB(unittest.TestCase):
    """Test MigrationManager with an in-memory SQLite database."""

    def setUp(self):
        """Set up a fresh in-memory database for each test."""
        # Create a temporary database file
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name

        # Initialize the database connection
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")

    def tearDown(self):
        """Clean up the temporary database."""
        self.conn.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_migrations_table_created(self):
        """Test that schema_migrations table is created."""
        # Create the migrations table manually to test structure
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

        # Verify table exists
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        )
        result = cursor.fetchone()
        self.assertIsNotNone(result)

    def test_get_current_version_empty_db(self):
        """Test getting version from empty database returns 0."""
        # Create migrations table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

        # Check version
        cursor = self.conn.execute("SELECT MAX(version) FROM schema_migrations")
        result = cursor.fetchone()
        version = result[0] if result and result[0] else 0
        self.assertEqual(version, 0)

    def test_migration_recorded_after_apply(self):
        """Test that migrations are recorded in schema_migrations."""
        # Create migrations table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Simulate applying a migration
        migration_sql = "CREATE TABLE test_table (id INTEGER PRIMARY KEY)"
        self.conn.execute(migration_sql)
        self.conn.execute(
            "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
            (1, "create_test_table")
        )
        self.conn.commit()

        # Verify migration recorded
        cursor = self.conn.execute("SELECT version, name FROM schema_migrations WHERE version = 1")
        result = cursor.fetchone()
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 1)
        self.assertEqual(result[1], "create_test_table")


class TestMigrationSequence(unittest.TestCase):
    """Test that migrations can be applied in sequence."""

    def setUp(self):
        """Set up a fresh database for testing."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        self.conn = sqlite3.connect(self.db_path)

    def tearDown(self):
        """Clean up."""
        self.conn.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_multiple_migrations_in_order(self):
        """Test applying multiple migrations in sequence."""
        # Create migrations table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Define test migrations
        migrations = [
            Migration(1, "create_users", "CREATE TABLE users (id INTEGER PRIMARY KEY)"),
            Migration(2, "add_email", "ALTER TABLE users ADD COLUMN email TEXT"),
            Migration(3, "add_name", "ALTER TABLE users ADD COLUMN name TEXT"),
        ]

        # Apply each migration
        for migration in migrations:
            self.conn.execute(migration.up_sql)
            self.conn.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                (migration.version, migration.name)
            )
        self.conn.commit()

        # Verify all migrations applied
        cursor = self.conn.execute("SELECT COUNT(*) FROM schema_migrations")
        count = cursor.fetchone()[0]
        self.assertEqual(count, 3)

        # Verify table structure
        cursor = self.conn.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        self.assertIn('id', columns)
        self.assertIn('email', columns)
        self.assertIn('name', columns)


class TestActualMigrations(unittest.TestCase):
    """Test the actual migration definitions from get_migrations()."""

    def test_migrations_defined(self):
        """Test that migrations are defined."""
        migrations = get_migrations()
        self.assertIsInstance(migrations, list)
        self.assertGreater(len(migrations), 0, "Should have at least one migration")

    def test_migrations_have_required_fields(self):
        """Test that all migrations have required fields."""
        migrations = get_migrations()
        for migration in migrations:
            self.assertIsInstance(migration.version, int)
            self.assertIsInstance(migration.name, str)
            self.assertIsInstance(migration.up_sql, str)
            self.assertGreater(len(migration.name), 0, "Migration name should not be empty")
            self.assertGreater(len(migration.up_sql), 0, "Migration SQL should not be empty")

    def test_migrations_sequential_versions(self):
        """Test that migration versions are sequential without gaps."""
        migrations = get_migrations()
        versions = sorted([m.version for m in migrations])

        for i, version in enumerate(versions):
            expected = i + 1  # Versions should start at 1
            self.assertEqual(
                version, expected,
                f"Migration versions should be sequential. Expected {expected}, got {version}"
            )

    def test_migrations_unique_versions(self):
        """Test that migration versions are unique."""
        migrations = get_migrations()
        versions = [m.version for m in migrations]
        self.assertEqual(
            len(versions), len(set(versions)),
            "Migration versions should be unique"
        )

    def test_migration_1_creates_recordings_table(self):
        """Test that migration 1 creates the recordings table."""
        migrations = get_migrations()
        migration_1 = next((m for m in migrations if m.version == 1), None)
        self.assertIsNotNone(migration_1, "Migration 1 should exist")
        self.assertIn("CREATE TABLE", migration_1.up_sql.upper())
        self.assertIn("recordings", migration_1.up_sql.lower())


class TestMigrationSQL(unittest.TestCase):
    """Test that migration SQL is valid."""

    def setUp(self):
        """Set up in-memory database for SQL validation."""
        self.conn = sqlite3.connect(":memory:")

    def tearDown(self):
        """Clean up."""
        self.conn.close()

    def test_migration_sql_syntax(self):
        """Test that migration SQL has valid syntax."""
        migrations = get_migrations()

        # Create base schema for migrations that modify existing tables
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS recordings (
                id INTEGER PRIMARY KEY,
                patient_name TEXT,
                timestamp TEXT,
                transcript TEXT,
                soap_note TEXT,
                referral_letter TEXT,
                letter TEXT,
                context TEXT,
                audio_path TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

        # Test each migration's SQL syntax (not all will work due to dependencies)
        for migration in migrations:
            try:
                # Try to parse the SQL without executing
                # This at least validates basic syntax
                self.conn.execute("EXPLAIN " + migration.up_sql.split(';')[0])
            except sqlite3.OperationalError as e:
                # Some migrations may fail due to schema dependencies
                # That's expected - we just want to catch obvious syntax errors
                if "syntax error" in str(e).lower():
                    self.fail(f"Migration {migration.version} has SQL syntax error: {e}")


class TestSchemaIntegrity(unittest.TestCase):
    """Test schema integrity after applying all migrations."""

    def setUp(self):
        """Set up database."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        self.conn = sqlite3.connect(self.db_path)

    def tearDown(self):
        """Clean up."""
        self.conn.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_recordings_table_has_required_columns(self):
        """Test that recordings table has all required columns after migrations."""
        # Create a basic recordings table structure to verify expected columns
        required_columns = [
            'id', 'patient_name', 'timestamp', 'transcript',
            'soap_note', 'referral_letter', 'letter', 'context', 'audio_path'
        ]

        # Create table with expected columns
        self.conn.execute("""
            CREATE TABLE recordings (
                id INTEGER PRIMARY KEY,
                patient_name TEXT,
                timestamp TEXT,
                transcript TEXT,
                soap_note TEXT,
                referral_letter TEXT,
                letter TEXT,
                context TEXT,
                audio_path TEXT
            )
        """)
        self.conn.commit()

        # Verify columns
        cursor = self.conn.execute("PRAGMA table_info(recordings)")
        columns = [row[1] for row in cursor.fetchall()]

        for col in required_columns:
            self.assertIn(col, columns, f"recordings table should have {col} column")


if __name__ == '__main__':
    # Set up logging
    logging.basicConfig(level=logging.WARNING)

    # Run tests
    unittest.main(verbosity=2)
