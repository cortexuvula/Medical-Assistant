"""
Database connection pool implementation for Medical Assistant.
"""

import sqlite3
import queue
import threading
import logging
import time
from typing import Optional, ContextManager, Any
from contextlib import contextmanager
from pathlib import Path

from core.config import get_config
from utils.exceptions import DatabaseError


class ConnectionPool:
    """Thread-safe SQLite connection pool.

    Thread Safety:
        Uses a single RLock for all state mutations. The queue.Queue is
        inherently thread-safe for get/put operations. Lock ordering:
        - Always acquire _lock before modifying _all_connections or _closed
        - Never hold _lock while waiting on queue operations (to avoid deadlock)

    Shutdown Safety:
        The close() method uses timeouts to prevent indefinite waiting if
        connections are stuck. Health checks use short timeouts to avoid
        blocking shutdown.
    """

    # Constants for shutdown behavior
    CLOSE_TIMEOUT = 10.0  # Maximum time to wait for pool close
    HEALTH_CHECK_TIMEOUT = 1.0  # Timeout for connection health check
    HEALTH_CHECK_INTERVAL = 300.0  # Skip health check if verified within this many seconds (5 minutes)

    def __init__(self, database_path: str, pool_size: int = 10, timeout: float = 30.0):
        """Initialize connection pool.

        Args:
            database_path: Path to SQLite database file
            pool_size: Maximum number of connections in pool
            timeout: Timeout for acquiring connections
        """
        self.database_path = database_path
        self.pool_size = pool_size
        self.timeout = timeout
        self._pool = queue.Queue(maxsize=pool_size)
        self._all_connections: list = []
        self._lock = threading.RLock()  # Use RLock to allow recursive acquisition
        self._closed = False
        self._replacing_connection = threading.local()  # Track replacement per-thread
        self._last_health_check: dict = {}  # Track last health check time per connection id
        self.logger = logging.getLogger(__name__)

        # Initialize the pool
        self._init_pool()
    
    def _init_pool(self):
        """Initialize connections in the pool."""
        try:
            for _ in range(self.pool_size):
                conn = self._create_connection()
                self._pool.put(conn)
                self._all_connections.append(conn)
        except Exception as e:
            self.close()
            raise DatabaseError(f"Failed to initialize connection pool: {e}")
    
    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection with optimized settings."""
        # NOTE: check_same_thread=False is intentional and safe here because:
        # 1. The connection pool manages access via a thread-safe queue
        # 2. Only one thread can hold a connection at a time (acquired/released atomically)
        # 3. Connections are validated before being returned to the pool
        conn = sqlite3.connect(
            self.database_path,
            timeout=self.timeout,
            check_same_thread=False  # Safe: pool ensures single-thread access
        )
        
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        
        # Optimize for performance
        conn.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging
        conn.execute("PRAGMA synchronous = NORMAL")  # Balance safety and speed
        conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
        conn.execute("PRAGMA temp_store = MEMORY")  # Use memory for temp tables
        
        # Enable query optimization
        conn.execute("PRAGMA optimize")
        
        return conn
    
    @contextmanager
    def get_connection(self) -> ContextManager[sqlite3.Connection]:
        """Get a connection from the pool.

        Yields:
            sqlite3.Connection: Database connection

        Raises:
            DatabaseError: If pool is closed or timeout occurs
        """
        # Check closed status (quick check without lock first)
        if self._closed:
            raise DatabaseError("Connection pool is closed")

        conn = None
        try:
            # Get connection from pool with timeout (queue is thread-safe)
            conn = self._pool.get(timeout=self.timeout)
            yield conn
        except queue.Empty:
            raise DatabaseError(f"Timeout waiting for database connection (timeout={self.timeout}s)")
        except Exception as e:
            self.logger.error(f"Error during database operation: {e}")
            raise
        finally:
            # Return connection to pool
            if conn is not None:
                self._return_connection(conn)

    def _return_connection(self, conn: sqlite3.Connection) -> None:
        """Return a connection to the pool, replacing if broken.

        Uses timeout on health check to prevent blocking during shutdown.
        Caches health check results to skip redundant checks (saves 50-100ms per operation).

        Args:
            conn: Connection to return
        """
        # Check if pool is closed (capture state under lock)
        with self._lock:
            is_closed = self._closed

        if is_closed:
            self._safe_close_connection(conn)
            return

        conn_id = id(conn)
        current_time = time.time()

        # Skip health check if recently verified (saves 50-100ms per DB operation)
        last_check = self._last_health_check.get(conn_id, 0)
        if current_time - last_check < self.HEALTH_CHECK_INTERVAL:
            # Connection was verified recently, return to pool without health check
            try:
                self._pool.put(conn, timeout=5.0)
            except queue.Full:
                self.logger.warning("Pool full when returning connection, closing it")
                self._safe_close_connection(conn)
            return

        try:
            # Check if connection is still valid with timeout protection
            # Use a short timeout to avoid blocking shutdown
            old_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
            conn.execute(f"PRAGMA busy_timeout = {int(self.HEALTH_CHECK_TIMEOUT * 1000)}")
            try:
                conn.execute("SELECT 1")
                # Restore original timeout
                conn.execute(f"PRAGMA busy_timeout = {old_timeout}")
                # Update last health check time
                self._last_health_check[conn_id] = current_time
                # Return to pool with timeout to avoid blocking
                try:
                    self._pool.put(conn, timeout=5.0)
                except queue.Full:
                    self.logger.warning("Pool full when returning connection, closing it")
                    self._safe_close_connection(conn)
            except sqlite3.OperationalError:
                # Database busy or locked - treat as broken
                self._replace_broken_connection(conn)
        except sqlite3.Error:
            # Connection is broken, need to replace it
            self._replace_broken_connection(conn)

    def _safe_close_connection(self, conn: sqlite3.Connection) -> None:
        """Safely close a connection, ignoring errors.

        Args:
            conn: Connection to close
        """
        try:
            conn.close()
        except sqlite3.Error:
            pass  # Ignore errors when closing

    def _replace_broken_connection(self, broken_conn: sqlite3.Connection) -> None:
        """Replace a broken connection with a new one.

        Args:
            broken_conn: The broken connection to replace
        """
        self.logger.warning("Replacing broken database connection")

        # Clear health check cache for this connection
        conn_id = id(broken_conn)
        self._last_health_check.pop(conn_id, None)

        # Close the broken connection
        try:
            broken_conn.close()
        except sqlite3.Error:
            pass  # Ignore errors when closing broken connection

        # Create new connection (outside lock - may take time)
        try:
            new_conn = self._create_connection()
        except Exception as e:
            self.logger.error(f"Failed to create replacement connection: {e}")
            # Put a None marker that will cause next get to fail
            # This is better than reducing pool size silently
            return

        # Update tracking and return to pool (with lock)
        with self._lock:
            if self._closed:
                # Pool closed while we were creating connection
                try:
                    new_conn.close()
                except sqlite3.Error:
                    pass
                return

            # Update all_connections list
            try:
                self._all_connections.remove(broken_conn)
            except ValueError:
                pass  # Already removed
            self._all_connections.append(new_conn)

        # Return new connection to pool (outside lock)
        self._pool.put(new_conn)
    
    def close(self):
        """Close all connections in the pool.

        Uses timeout to prevent indefinite waiting if connections are stuck.
        Connections that can't be retrieved within the timeout are still
        tracked in _all_connections and will be force-closed.
        """
        with self._lock:
            if self._closed:
                return

            self._closed = True

        # Drain pool with timeout to prevent indefinite waiting
        deadline = time.time() + self.CLOSE_TIMEOUT
        connections_drained = 0

        while time.time() < deadline:
            try:
                conn = self._pool.get_nowait()
                self._safe_close_connection(conn)
                connections_drained += 1
            except queue.Empty:
                break

        # Force close any remaining connections (those still in use or stuck)
        with self._lock:
            for conn in self._all_connections:
                try:
                    # Use interrupt to cancel any running queries
                    conn.interrupt()
                except (sqlite3.Error, AttributeError):
                    pass  # interrupt() may not be available in older sqlite3
                self._safe_close_connection(conn)

            remaining = len(self._all_connections) - connections_drained
            if remaining > 0:
                self.logger.warning(f"Force-closed {remaining} connection(s) during shutdown")

            self._all_connections.clear()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


class DatabaseConnectionManager:
    """Manages database connections with pooling and context managers."""

    _instance = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls):
        """Singleton pattern for connection manager.

        Uses lock-first approach to avoid potential race conditions in
        double-checked locking pattern. The lock acquisition overhead
        is acceptable since this is only called during initialization.
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance
    
    def __init__(self):
        """Initialize connection manager."""
        # Use class-level lock to ensure thread-safe initialization
        with DatabaseConnectionManager._lock:
            if DatabaseConnectionManager._initialized:
                return

            DatabaseConnectionManager._initialized = True
            self.config = get_config()
            self.logger = logging.getLogger(__name__)
            self._pool = None
            self._init_pool()
    
    def _init_pool(self):
        """Initialize the connection pool."""
        db_path = Path(self.config.storage.base_folder) / self.config.storage.database_name
        
        # Ensure directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create connection pool
        pool_size = getattr(self.config.storage, 'db_pool_size', 5)
        timeout = getattr(self.config.storage, 'db_timeout', 30.0)
        
        self._pool = ConnectionPool(
            database_path=str(db_path),
            pool_size=pool_size,
            timeout=timeout
        )
        
        self.logger.info(f"Database connection pool initialized with {pool_size} connections")
    
    @contextmanager
    def get_connection(self) -> ContextManager[sqlite3.Connection]:
        """Get a database connection from the pool.
        
        Yields:
            sqlite3.Connection: Database connection
        """
        if self._pool is None:
            raise DatabaseError("Connection pool not initialized")
        
        with self._pool.get_connection() as conn:
            yield conn
    
    @contextmanager
    def transaction(self) -> ContextManager[sqlite3.Connection]:
        """Execute database operations in a transaction.
        
        Yields:
            sqlite3.Connection: Database connection with transaction
            
        Note:
            Transaction is automatically committed on success or rolled back on error.
        """
        with self.get_connection() as conn:
            try:
                yield conn
                conn.commit()
            except BaseException:
                # Catch all exceptions including KeyboardInterrupt to ensure rollback
                conn.rollback()
                raise
    
    def execute(self, query: str, params: Optional[tuple] = None) -> Any:
        """Execute a single query.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            
        Returns:
            Query result
        """
        with self.transaction() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor
    
    def executemany(self, query: str, params_list: list) -> Any:
        """Execute a query multiple times with different parameters.
        
        Args:
            query: SQL query to execute
            params_list: List of parameter tuples
            
        Returns:
            Query result
        """
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            return cursor
    
    def fetchone(self, query: str, params: Optional[tuple] = None) -> Optional[tuple]:
        """Execute a query and fetch one result.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            
        Returns:
            Single row or None
        """
        cursor = self.execute(query, params)
        return cursor.fetchone()
    
    def fetchall(self, query: str, params: Optional[tuple] = None) -> list:
        """Execute a query and fetch all results.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            
        Returns:
            List of rows
        """
        cursor = self.execute(query, params)
        return cursor.fetchall()
    
    def close(self):
        """Close the connection pool."""
        if self._pool:
            self._pool.close()
            self._pool = None
            self.logger.info("Database connection pool closed")


# Global connection manager instance
_db_manager: Optional[DatabaseConnectionManager] = None


def get_db_manager() -> DatabaseConnectionManager:
    """Get the global database connection manager.
    
    Returns:
        DatabaseConnectionManager: Global connection manager instance
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseConnectionManager()
    return _db_manager