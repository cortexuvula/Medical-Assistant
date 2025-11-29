"""
Database Schema Updates for Processing Queue

Adds processing queue related columns and tables to the existing database.
"""

import sqlite3
import logging
from datetime import datetime
from typing import Optional
from contextlib import contextmanager


class QueueDatabaseSchema:
    """Manages database schema updates for processing queue functionality."""

    def __init__(self, db_path: str = "database.db"):
        self.db_path = db_path

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections.

        Ensures proper connection handling with automatic cleanup.
        Uses check_same_thread=True for safety since this is a single-use utility.

        Yields:
            Tuple of (connection, cursor)
        """
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            check_same_thread=True  # Safe: schema upgrades run in single thread
        )
        cursor = conn.cursor()
        try:
            yield conn, cursor
        finally:
            conn.close()

    def upgrade_schema(self):
        """Apply all schema upgrades for processing queue support."""
        with self._get_connection() as (conn, cursor):
            try:
                # Check if upgrades are needed
                if not self._needs_upgrade(cursor):
                    logging.info("Database schema is up to date")
                    return

                logging.info("Upgrading database schema for processing queue support...")

                # Add new columns to recordings table
                self._add_processing_columns(cursor)

                # Create processing_queue table
                self._create_processing_queue_table(cursor)

                # Create indexes for performance
                self._create_indexes(cursor)

                # Commit all changes
                conn.commit()
                logging.info("Database schema upgrade completed successfully")

            except Exception as e:
                conn.rollback()
                logging.error(f"Failed to upgrade database schema: {str(e)}")
                raise
    
    def _needs_upgrade(self, cursor) -> bool:
        """Check if schema upgrades are needed."""
        # First check if recordings table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='recordings'
        """)
        
        if not cursor.fetchone():
            # If recordings table doesn't exist, we can't upgrade it
            # This will be created by Database.create_tables()
            return False
        
        # Check if processing_status column exists
        cursor.execute("PRAGMA table_info(recordings)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if "processing_status" not in columns:
            return True
        
        # Check if processing_queue table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='processing_queue'
        """)
        
        if not cursor.fetchone():
            return True
        
        return False
    
    def _add_processing_columns(self, cursor):
        """Add processing-related columns to recordings table."""
        # First check if recordings table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='recordings'
        """)
        
        if not cursor.fetchone():
            logging.warning("Cannot add processing columns - recordings table does not exist")
            return
        
        # Get existing columns
        cursor.execute("PRAGMA table_info(recordings)")
        existing_columns = [col[1] for col in cursor.fetchall()]
        
        # Define new columns to add
        new_columns = [
            ("processing_status", "TEXT DEFAULT 'pending'"),
            ("processing_started_at", "TIMESTAMP"),
            ("processing_completed_at", "TIMESTAMP"),
            ("error_message", "TEXT"),
            ("retry_count", "INTEGER DEFAULT 0"),
            ("patient_name", "TEXT"),
            ("audio_path", "TEXT"),
            ("duration", "REAL"),
            ("metadata", "TEXT")  # JSON string for additional data
        ]
        
        # Add columns that don't exist
        for column_name, column_def in new_columns:
            if column_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE recordings ADD COLUMN {column_name} {column_def}")
                    logging.info(f"Added column {column_name} to recordings table")
                except sqlite3.OperationalError as e:
                    # Column might already exist in some databases
                    if "duplicate column name" not in str(e).lower():
                        raise
    
    def _create_processing_queue_table(self, cursor):
        """Create the processing_queue table."""
        # Check if recordings table exists before creating a table with foreign key to it
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='recordings'
        """)
        
        if not cursor.fetchone():
            logging.warning("Cannot create processing_queue table - recordings table does not exist")
            return
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS processing_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recording_id INTEGER NOT NULL,
            task_id TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'queued',
            priority INTEGER DEFAULT 5,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            error_count INTEGER DEFAULT 0,
            last_error TEXT,
            result TEXT,  -- JSON string for results
            FOREIGN KEY (recording_id) REFERENCES recordings(id) ON DELETE CASCADE
        )
        ''')
        
        logging.info("Created processing_queue table")
    
    def _create_indexes(self, cursor):
        """Create indexes for better query performance."""
        # Check if recordings table exists before creating indexes on it
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='recordings'
        """)
        has_recordings_table = cursor.fetchone() is not None
        
        indexes = []
        
        # Only add recordings index if the table exists
        if has_recordings_table:
            indexes.append(("idx_recordings_processing_status", "recordings(processing_status)"))
        
        # Always add processing_queue indexes (table should exist by now)
        indexes.extend([
            # Index for queue status queries
            ("idx_processing_queue_status", "processing_queue(status)"),
            
            # Index for task lookups
            ("idx_processing_queue_task_id", "processing_queue(task_id)"),
            
            # Composite index for queue ordering
            ("idx_processing_queue_priority_created", "processing_queue(priority DESC, created_at ASC)")
        ])
        
        for index_name, index_def in indexes:
            try:
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {index_def}")
                logging.info(f"Created index {index_name}")
            except sqlite3.OperationalError as e:
                # Index might already exist
                if "already exists" not in str(e).lower():
                    raise


def upgrade_database():
    """Convenience function to upgrade the database schema."""
    upgrader = QueueDatabaseSchema()
    upgrader.upgrade_schema()


if __name__ == "__main__":
    # Run the upgrade if called directly
    logging.basicConfig(level=logging.INFO)
    upgrade_database()