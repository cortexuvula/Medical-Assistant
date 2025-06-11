"""
Database migration system for Medical Assistant.
"""

import os
import sqlite3
import logging
from typing import List, Dict, Optional, Callable
from datetime import datetime
from pathlib import Path

from database.db_pool import get_db_manager
from utils.exceptions import DatabaseError


class Migration:
    """Represents a database migration."""
    
    def __init__(self, version: int, name: str, up_sql: str, down_sql: Optional[str] = None):
        """Initialize a migration.
        
        Args:
            version: Migration version number
            name: Migration name/description
            up_sql: SQL to apply the migration
            down_sql: SQL to rollback the migration (optional)
        """
        self.version = version
        self.name = name
        self.up_sql = up_sql
        self.down_sql = down_sql
        self.applied_at = None


class MigrationManager:
    """Manages database migrations."""
    
    def __init__(self):
        """Initialize migration manager."""
        self.logger = logging.getLogger(__name__)
        self.db_manager = get_db_manager()
        self._migrations = []
        self._init_migrations_table()
    
    def _init_migrations_table(self):
        """Create the migrations tracking table if it doesn't exist."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        self.db_manager.execute(create_table_sql)
        self.logger.info("Migrations table initialized")
    
    def register(self, migration: Migration):
        """Register a migration.
        
        Args:
            migration: Migration to register
        """
        self._migrations.append(migration)
        self._migrations.sort(key=lambda m: m.version)
    
    def get_current_version(self) -> int:
        """Get the current database schema version.
        
        Returns:
            Current version number or 0 if no migrations applied
        """
        result = self.db_manager.fetchone(
            "SELECT MAX(version) FROM schema_migrations"
        )
        return result[0] if result and result[0] else 0
    
    def get_applied_migrations(self) -> List[Dict]:
        """Get list of applied migrations.
        
        Returns:
            List of applied migration records
        """
        rows = self.db_manager.fetchall(
            "SELECT version, name, applied_at FROM schema_migrations ORDER BY version"
        )
        return [
            {"version": row[0], "name": row[1], "applied_at": row[2]}
            for row in rows
        ]
    
    def get_pending_migrations(self) -> List[Migration]:
        """Get list of pending migrations.
        
        Returns:
            List of migrations that haven't been applied yet
        """
        current_version = self.get_current_version()
        return [m for m in self._migrations if m.version > current_version]
    
    def migrate(self, target_version: Optional[int] = None) -> int:
        """Apply migrations up to target version.
        
        Args:
            target_version: Target version to migrate to (None = latest)
            
        Returns:
            Number of migrations applied
            
        Raises:
            DatabaseError: If migration fails
        """
        current_version = self.get_current_version()
        pending = self.get_pending_migrations()
        
        if target_version is None:
            target_version = self._migrations[-1].version if self._migrations else 0
        
        if target_version <= current_version:
            self.logger.info(f"Already at version {current_version}, nothing to migrate")
            return 0
        
        applied_count = 0
        
        for migration in pending:
            if migration.version > target_version:
                break
            
            try:
                self._apply_migration(migration)
                applied_count += 1
            except Exception as e:
                self.logger.error(f"Migration {migration.version} failed: {e}")
                raise DatabaseError(f"Migration {migration.version} '{migration.name}' failed: {e}")
        
        self.logger.info(f"Applied {applied_count} migrations, now at version {self.get_current_version()}")
        return applied_count
    
    def _apply_migration(self, migration: Migration):
        """Apply a single migration.
        
        Args:
            migration: Migration to apply
        """
        self.logger.info(f"Applying migration {migration.version}: {migration.name}")
        
        with self.db_manager.transaction() as conn:
            # Execute migration SQL
            if ";" in migration.up_sql:
                # Multiple statements
                conn.executescript(migration.up_sql)
            else:
                # Single statement
                conn.execute(migration.up_sql)
            
            # Record migration
            conn.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                (migration.version, migration.name)
            )
    
    def rollback(self, target_version: int = 0) -> int:
        """Rollback migrations to target version.
        
        Args:
            target_version: Target version to rollback to (0 = initial state)
            
        Returns:
            Number of migrations rolled back
            
        Raises:
            DatabaseError: If rollback fails or migration has no down_sql
        """
        current_version = self.get_current_version()
        
        if target_version >= current_version:
            self.logger.info(f"Already at version {current_version}, nothing to rollback")
            return 0
        
        # Get migrations to rollback in reverse order
        to_rollback = [
            m for m in reversed(self._migrations)
            if m.version > target_version and m.version <= current_version
        ]
        
        rolled_back_count = 0
        
        for migration in to_rollback:
            if migration.down_sql is None:
                raise DatabaseError(
                    f"Cannot rollback migration {migration.version} '{migration.name}': "
                    "no down_sql provided"
                )
            
            try:
                self._rollback_migration(migration)
                rolled_back_count += 1
            except Exception as e:
                self.logger.error(f"Rollback of migration {migration.version} failed: {e}")
                raise DatabaseError(
                    f"Rollback of migration {migration.version} '{migration.name}' failed: {e}"
                )
        
        self.logger.info(
            f"Rolled back {rolled_back_count} migrations, now at version {self.get_current_version()}"
        )
        return rolled_back_count
    
    def _rollback_migration(self, migration: Migration):
        """Rollback a single migration.
        
        Args:
            migration: Migration to rollback
        """
        self.logger.info(f"Rolling back migration {migration.version}: {migration.name}")
        
        with self.db_manager.transaction() as conn:
            # Execute rollback SQL
            if ";" in migration.down_sql:
                # Multiple statements
                conn.executescript(migration.down_sql)
            else:
                # Single statement
                conn.execute(migration.down_sql)
            
            # Remove migration record
            conn.execute(
                "DELETE FROM schema_migrations WHERE version = ?",
                (migration.version,)
            )


# Define migrations
def get_migrations() -> List[Migration]:
    """Get all database migrations.
    
    Returns:
        List of migrations in order
    """
    migrations = []
    
    # Migration 1: Initial schema
    migrations.append(Migration(
        version=1,
        name="Initial schema",
        up_sql="""
        CREATE TABLE IF NOT EXISTS recordings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            transcript TEXT,
            soap_note TEXT,
            referral TEXT,
            letter TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """,
        down_sql="DROP TABLE IF EXISTS recordings"
    ))
    
    # Migration 2: Add indexes for search performance
    migrations.append(Migration(
        version=2,
        name="Add search indexes",
        up_sql="""
        CREATE INDEX IF NOT EXISTS idx_recordings_timestamp ON recordings(timestamp);
        CREATE INDEX IF NOT EXISTS idx_recordings_filename ON recordings(filename);
        """,
        down_sql="""
        DROP INDEX IF EXISTS idx_recordings_timestamp;
        DROP INDEX IF EXISTS idx_recordings_filename;
        """
    ))
    
    # Migration 3: Add full-text search support
    migrations.append(Migration(
        version=3,
        name="Add full-text search",
        up_sql="""
        -- Create virtual table for full-text search
        CREATE VIRTUAL TABLE IF NOT EXISTS recordings_fts USING fts5(
            transcript,
            soap_note,
            referral,
            letter,
            content=recordings,
            content_rowid=id
        );
        
        -- Create triggers to keep FTS table in sync
        CREATE TRIGGER IF NOT EXISTS recordings_ai AFTER INSERT ON recordings BEGIN
            INSERT INTO recordings_fts(rowid, transcript, soap_note, referral, letter)
            VALUES (new.id, new.transcript, new.soap_note, new.referral, new.letter);
        END;
        
        CREATE TRIGGER IF NOT EXISTS recordings_ad AFTER DELETE ON recordings BEGIN
            DELETE FROM recordings_fts WHERE rowid = old.id;
        END;
        
        CREATE TRIGGER IF NOT EXISTS recordings_au AFTER UPDATE ON recordings BEGIN
            UPDATE recordings_fts 
            SET transcript = new.transcript,
                soap_note = new.soap_note,
                referral = new.referral,
                letter = new.letter
            WHERE rowid = new.id;
        END;
        
        -- Populate FTS table with existing data
        INSERT INTO recordings_fts(rowid, transcript, soap_note, referral, letter)
        SELECT id, transcript, soap_note, referral, letter FROM recordings;
        """,
        down_sql="""
        DROP TRIGGER IF EXISTS recordings_au;
        DROP TRIGGER IF EXISTS recordings_ad;
        DROP TRIGGER IF EXISTS recordings_ai;
        DROP TABLE IF EXISTS recordings_fts;
        """
    ))
    
    # Migration 4: Add metadata fields
    migrations.append(Migration(
        version=4,
        name="Add metadata fields",
        up_sql="""
        ALTER TABLE recordings ADD COLUMN duration_seconds REAL;
        ALTER TABLE recordings ADD COLUMN file_size_bytes INTEGER;
        ALTER TABLE recordings ADD COLUMN stt_provider TEXT;
        ALTER TABLE recordings ADD COLUMN ai_provider TEXT;
        ALTER TABLE recordings ADD COLUMN tags TEXT;  -- JSON array of tags
        """,
        down_sql=None  # SQLite doesn't support DROP COLUMN easily
    ))
    
    # Migration 5: Add patient information (encrypted)
    migrations.append(Migration(
        version=5,
        name="Add patient information",
        up_sql="""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT UNIQUE NOT NULL,  -- Encrypted patient identifier
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        
        ALTER TABLE recordings ADD COLUMN patient_id INTEGER REFERENCES patients(id);
        CREATE INDEX IF NOT EXISTS idx_recordings_patient_id ON recordings(patient_id);
        """,
        down_sql="""
        DROP INDEX IF EXISTS idx_recordings_patient_id;
        DROP TABLE IF EXISTS patients;
        """
    ))
    
    # Migration 6: Add chat column for ChatGPT-style conversations
    migrations.append(Migration(
        version=6,
        name="Add chat column",
        up_sql="""
        ALTER TABLE recordings ADD COLUMN chat TEXT;
        
        -- Update FTS table to include chat
        DROP TRIGGER IF EXISTS recordings_ai;
        DROP TRIGGER IF EXISTS recordings_au;
        DROP TABLE IF EXISTS recordings_fts;
        
        -- Recreate FTS table with chat column
        CREATE VIRTUAL TABLE IF NOT EXISTS recordings_fts USING fts5(
            transcript,
            soap_note,
            referral,
            letter,
            chat,
            content=recordings,
            content_rowid=id
        );
        
        -- Recreate triggers with chat column
        CREATE TRIGGER IF NOT EXISTS recordings_ai AFTER INSERT ON recordings BEGIN
            INSERT INTO recordings_fts(rowid, transcript, soap_note, referral, letter, chat)
            VALUES (new.id, new.transcript, new.soap_note, new.referral, new.letter, new.chat);
        END;
        
        CREATE TRIGGER IF NOT EXISTS recordings_ad AFTER DELETE ON recordings BEGIN
            DELETE FROM recordings_fts WHERE rowid = old.id;
        END;
        
        CREATE TRIGGER IF NOT EXISTS recordings_au AFTER UPDATE ON recordings BEGIN
            UPDATE recordings_fts 
            SET transcript = new.transcript,
                soap_note = new.soap_note,
                referral = new.referral,
                letter = new.letter,
                chat = new.chat
            WHERE rowid = new.id;
        END;
        
        -- Populate FTS table with existing data
        INSERT INTO recordings_fts(rowid, transcript, soap_note, referral, letter, chat)
        SELECT id, transcript, soap_note, referral, letter, chat FROM recordings;
        """,
        down_sql=None  # Complex migration, no rollback
    ))
    
    return migrations


# Global migration manager
_migration_manager: Optional[MigrationManager] = None


def get_migration_manager() -> MigrationManager:
    """Get the global migration manager.
    
    Returns:
        MigrationManager: Global migration manager instance
    """
    global _migration_manager
    if _migration_manager is None:
        _migration_manager = MigrationManager()
        # Register all migrations
        for migration in get_migrations():
            _migration_manager.register(migration)
    return _migration_manager


def run_migrations():
    """Run all pending migrations."""
    manager = get_migration_manager()
    
    current_version = manager.get_current_version()
    pending = manager.get_pending_migrations()
    
    if not pending:
        print(f"Database is up to date (version {current_version})")
        return
    
    print(f"Current database version: {current_version}")
    print(f"Found {len(pending)} pending migrations:")
    for migration in pending:
        print(f"  - Version {migration.version}: {migration.name}")
    
    # Apply migrations
    try:
        applied = manager.migrate()
        print(f"\nSuccessfully applied {applied} migrations")
        print(f"Database is now at version {manager.get_current_version()}")
    except DatabaseError as e:
        print(f"\nError applying migrations: {e}")
        raise


if __name__ == "__main__":
    # Run migrations when executed directly
    logging.basicConfig(level=logging.INFO)
    run_migrations()