"""
Database migration system for Medical Assistant.
"""

import logging
import os
import sqlite3
from typing import List, Dict, Optional, Callable
from datetime import datetime
from pathlib import Path

from database.db_pool import get_db_manager
from utils.exceptions import DatabaseError
from utils.structured_logging import get_logger

logger = get_logger(__name__)


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
        self.logger = get_logger(__name__)
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
            # Special handling for migration 12 - conditionally add patient_name column
            if migration.version == 12:
                self._apply_migration_12(conn)
            else:
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

    def _apply_migration_12(self, conn):
        """Apply migration 12 with conditional column addition.

        This migration adds the patient_name column if it doesn't exist,
        then creates performance indices.

        Args:
            conn: Database connection within transaction
        """
        # Check if patient_name column already exists
        cursor = conn.execute("PRAGMA table_info(recordings)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'patient_name' not in columns:
            self.logger.info("Adding patient_name column to recordings table")
            conn.execute("ALTER TABLE recordings ADD COLUMN patient_name TEXT")
        else:
            self.logger.info("patient_name column already exists, skipping")

        # Create indices (these use IF NOT EXISTS so they're safe)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_recordings_patient_name ON recordings(patient_name)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_recordings_timestamp_desc ON recordings(timestamp DESC)"
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
    from database.migration_definitions import get_all_migrations
    return get_all_migrations()


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
        logger.info(f"Database is up to date (version {current_version})")
        return

    logger.info(f"Current database version: {current_version}")
    logger.info(f"Found {len(pending)} pending migrations:")
    for migration in pending:
        logger.info(f"  - Version {migration.version}: {migration.name}")

    # Apply migrations
    try:
        applied = manager.migrate()
        logger.info(f"Successfully applied {applied} migrations")
        logger.info(f"Database is now at version {manager.get_current_version()}")
    except DatabaseError as e:
        logger.error(f"Error applying migrations: {e}")
        raise


if __name__ == "__main__":
    # Run migrations when executed directly
    logging.basicConfig(level=logging.INFO)
    run_migrations()