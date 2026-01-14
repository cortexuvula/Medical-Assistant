"""
Database Connection Mixin

Provides thread-safe connection management for the Database class.
"""

import sqlite3
import threading
import logging
from contextlib import contextmanager
from typing import Dict

from utils.retry_decorator import db_retry

logger = logging.getLogger(__name__)


class ConnectionMixin:
    """Mixin providing thread-local connection management."""

    # These attributes are initialized by the Database class
    db_path: str
    _local: threading.local
    _lock: threading.Lock
    _thread_connections: Dict[int, sqlite3.Connection]
    _closed: bool

    def __del__(self):
        """Destructor to clean up connections when Database instance is garbage collected.

        Note: This is a best-effort cleanup. For reliable cleanup, explicitly call
        close_all_connections() during application shutdown.
        """
        try:
            self._cleanup_all_connections()
        except (sqlite3.Error, OSError, RuntimeError):
            # Suppress database/OS errors during garbage collection
            # These are expected if the interpreter is shutting down
            pass

    def __enter__(self):
        """Context manager entry - returns self for use in with statements."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - closes all connections."""
        self.close_all_connections()
        return False  # Don't suppress exceptions

    def _cleanup_all_connections(self) -> None:
        """Internal method to clean up all tracked connections.

        This closes all connections that were opened by any thread.
        Thread-safe and idempotent.
        """
        if self._closed:
            return

        with self._lock:
            if self._closed:
                return

            self._closed = True

            # Close all tracked connections
            for thread_id, conn in list(self._thread_connections.items()):
                try:
                    if conn is not None:
                        conn.close()
                        logger.debug(f"Closed database connection for thread {thread_id}")
                except Exception as e:
                    logger.warning(f"Error closing connection for thread {thread_id}: {e}")

            self._thread_connections.clear()

            # Clear thread-local storage for current thread
            if hasattr(self._local, 'conn'):
                self._local.conn = None
            if hasattr(self._local, 'cursor'):
                self._local.cursor = None

        # Unregister this instance (if Database._instances exists)
        if hasattr(self.__class__, '_instances_lock'):
            with self.__class__._instances_lock:
                if self in self.__class__._instances:
                    self.__class__._instances.remove(self)

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create a connection for the current thread.

        Returns:
            sqlite3.Connection for the current thread

        Raises:
            RuntimeError: If the database has been closed
        """
        if self._closed:
            raise RuntimeError("Database has been closed")

        if not hasattr(self._local, 'conn') or self._local.conn is None:
            conn = self._create_connection()
            self._local.conn = conn

            # Track this connection for cleanup
            thread_id = threading.current_thread().ident
            with self._lock:
                self._thread_connections[thread_id] = conn

        return self._local.conn

    def _get_cursor(self) -> sqlite3.Cursor:
        """Get or create a cursor for the current thread.

        Returns:
            sqlite3.Cursor for the current thread
        """
        if not hasattr(self._local, 'cursor') or self._local.cursor is None:
            self._local.cursor = self._get_connection().cursor()
        return self._local.cursor

    @db_retry(max_retries=3, initial_delay=0.1)
    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection with optimized settings.

        Returns:
            Configured sqlite3.Connection
        """
        thread_id = threading.current_thread().ident
        thread_name = threading.current_thread().name

        # MONITORING: Log connection creation for leak detection
        current_count = len(self._thread_connections)
        if current_count > 10:
            logger.warning(
                f"High connection count ({current_count}) detected. "
                f"Creating new connection for thread {thread_id} ({thread_name}). "
                "This may indicate a connection leak."
            )
        else:
            logger.debug(f"Creating database connection for thread {thread_id} ({thread_name})")

        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            check_same_thread=True  # Enforce single-thread per connection
        )
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")  # 30 second busy timeout
        conn.execute("PRAGMA foreign_keys=ON")

        logger.debug(f"Database connection created for thread {thread_id}. Total connections: {current_count + 1}")
        return conn

    @contextmanager
    def connection(self):
        """Context manager for database operations.

        Yields:
            Tuple of (connection, cursor) for the current thread

        Example:
            with db.connection() as (conn, cursor):
                cursor.execute("SELECT * FROM recordings")
                results = cursor.fetchall()
        """
        conn = self._get_connection()
        cursor = self._get_cursor()
        try:
            yield conn, cursor
        except BaseException:
            # Catch all exceptions including KeyboardInterrupt to ensure rollback
            # Re-raise after rollback to preserve original exception
            conn.rollback()
            raise
        else:
            conn.commit()

    @contextmanager
    def transaction(self):
        """Context manager for explicit transaction handling.

        Automatically commits on success, rolls back on exception.

        Yields:
            Tuple of (connection, cursor) for the current thread
        """
        conn = self._get_connection()
        cursor = self._get_cursor()
        try:
            yield conn, cursor
            conn.commit()
        except BaseException:
            # Catch all exceptions including KeyboardInterrupt to ensure rollback
            conn.rollback()
            raise

    # Legacy methods for backward compatibility
    @db_retry(max_retries=3, initial_delay=0.1)
    def connect(self) -> None:
        """Establish connection to the database.

        Note: This method is kept for backward compatibility.
        Prefer using the connection() context manager instead.
        """
        # Get or create thread-local connection
        self._get_connection()

    @property
    def conn(self) -> sqlite3.Connection:
        """Get the connection for the current thread.

        Returns:
            sqlite3.Connection for the current thread
        """
        return self._get_connection()

    @property
    def cursor(self) -> sqlite3.Cursor:
        """Get the cursor for the current thread.

        Returns:
            sqlite3.Cursor for the current thread
        """
        return self._get_cursor()

    def disconnect(self) -> None:
        """Close the database connection for the current thread.

        This removes the connection from tracking and closes it.
        Safe to call multiple times.
        """
        thread_id = threading.current_thread().ident

        if hasattr(self._local, 'conn') and self._local.conn is not None:
            try:
                self._local.conn.close()
                logger.debug(f"Disconnected database connection for thread {thread_id}")
            except Exception as e:
                logger.warning(f"Error closing database connection: {e}")
            finally:
                self._local.conn = None
                self._local.cursor = None

                # Remove from tracked connections
                with self._lock:
                    self._thread_connections.pop(thread_id, None)

    def close_all_connections(self) -> None:
        """Close ALL connections across all threads.

        This method closes connections for all threads that have used this
        Database instance, not just the calling thread. Use this during
        application shutdown for complete cleanup.

        After calling this method, the Database instance should not be used.
        """
        self._cleanup_all_connections()

    def get_connection_count(self) -> int:
        """Get the number of active tracked connections.

        Returns:
            Number of connections currently tracked (may include stale connections
            from terminated threads).
        """
        with self._lock:
            return len(self._thread_connections)

    def cleanup_stale_connections(self) -> int:
        """Clean up connections from threads that are no longer alive.

        This method identifies connections from threads that have terminated
        and closes them. Useful for long-running applications.

        Returns:
            Number of stale connections that were cleaned up.
        """
        if self._closed:
            return 0

        cleaned = 0
        current_threads = {t.ident for t in threading.enumerate()}

        with self._lock:
            stale_thread_ids = [
                tid for tid in self._thread_connections.keys()
                if tid not in current_threads
            ]

            for thread_id in stale_thread_ids:
                conn = self._thread_connections.pop(thread_id, None)
                if conn is not None:
                    try:
                        conn.close()
                        cleaned += 1
                        logger.debug(f"Cleaned up stale connection from thread {thread_id}")
                    except Exception as e:
                        logger.warning(f"Error closing stale connection: {e}")

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} stale database connection(s)")

        return cleaned


__all__ = ["ConnectionMixin"]
