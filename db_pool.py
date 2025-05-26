"""
Database connection pool implementation for Medical Assistant.
"""

import sqlite3
import queue
import threading
import logging
from typing import Optional, ContextManager, Any
from contextlib import contextmanager
from pathlib import Path

from config import get_config
from exceptions import DatabaseError


class ConnectionPool:
    """Thread-safe SQLite connection pool."""
    
    def __init__(self, database_path: str, pool_size: int = 5, timeout: float = 30.0):
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
        self._all_connections = []
        self._lock = threading.Lock()
        self._closed = False
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
        conn = sqlite3.connect(
            self.database_path,
            timeout=self.timeout,
            check_same_thread=False  # Allow connections to be used across threads
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
        if self._closed:
            raise DatabaseError("Connection pool is closed")
        
        conn = None
        try:
            # Get connection from pool with timeout
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
                try:
                    # Check if connection is still valid
                    conn.execute("SELECT 1")
                    self._pool.put(conn)
                except sqlite3.Error:
                    # Connection is broken, create a new one
                    self.logger.warning("Replacing broken database connection")
                    try:
                        conn.close()
                    except:
                        pass
                    new_conn = self._create_connection()
                    self._pool.put(new_conn)
                    with self._lock:
                        self._all_connections.remove(conn)
                        self._all_connections.append(new_conn)
    
    def close(self):
        """Close all connections in the pool."""
        with self._lock:
            if self._closed:
                return
            
            self._closed = True
            
            # Close all connections
            for conn in self._all_connections:
                try:
                    conn.close()
                except Exception as e:
                    self.logger.error(f"Error closing connection: {e}")
            
            self._all_connections.clear()
            
            # Clear the queue
            while not self._pool.empty():
                try:
                    self._pool.get_nowait()
                except queue.Empty:
                    break
    
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
    
    def __new__(cls):
        """Singleton pattern for connection manager."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize connection manager."""
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
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
            except Exception:
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