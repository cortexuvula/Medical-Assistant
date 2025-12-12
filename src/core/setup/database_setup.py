"""
Database setup for Medical Assistant.

Handles initialization of database connections and migrations.
"""

from typing import TYPE_CHECKING

from .base import BaseSetup

if TYPE_CHECKING:
    from core.app import MedicalDictationApp


class DatabaseSetup(BaseSetup):
    """Setup component for database initialization.

    Initializes:
    - Database connection pool
    - Database migrations
    - Queue database schema
    """

    def initialize(self) -> None:
        """Initialize database components."""
        self._log_start("Database setup")

        # Initialize main database
        self._init_database()

        # Run migrations
        self._run_migrations()

        self._log_complete("Database setup")

    def _init_database(self) -> None:
        """Initialize the main database connection."""
        from database.database import Database

        self.app.db = Database()
        self.logger.info("Database initialized")

    def _run_migrations(self) -> None:
        """Run database migrations."""
        try:
            # Run main database migrations
            from database.db_migrations import run_migrations
            run_migrations(self.app.db.conn)
            self.logger.info("Database migrations completed")

            # Initialize queue schema
            from database.db_queue_schema import QueueDatabaseSchema
            queue_schema = QueueDatabaseSchema(self.app.db.conn)
            queue_schema.initialize()
            self.logger.info("Queue database schema initialized")

        except Exception as e:
            self._log_error("Database migrations", e)
            raise

    def cleanup(self) -> None:
        """Close database connections."""
        if hasattr(self.app, 'db') and self.app.db:
            self._log_start("Database cleanup")
            try:
                self.app.db.close()
            except Exception as e:
                self._log_error("Database cleanup", e)
            self._log_complete("Database cleanup")
