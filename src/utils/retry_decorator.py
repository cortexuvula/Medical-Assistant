"""
Retry decorator with exponential backoff for database operations.

This module provides decorators for automatically retrying failed operations
with exponential backoff, specialized for database and network operations.

Components:
    - exponential_backoff: Generic retry decorator with configurable backoff
    - db_retry: Database-specific retry with sqlite3 exception handling
    - db_resilient: Combined retry + circuit breaker for database operations
    - network_retry: Network-specific retry with requests exception handling
    - DatabaseCircuitBreaker: Circuit breaker for persistent database failures

Error Handling:
    - Retries on: OperationalError (locked), DatabaseError, ConnectionError, TimeoutError
    - Does not retry: IntegrityError, ProgrammingError (these indicate bugs)
    - Raises DatabaseError: When circuit breaker is OPEN

Usage:
    # For most database operations (recommended):
    @db_retry(max_retries=3)
    def query_database():
        ...

    # For critical operations needing circuit breaker:
    @db_resilient(max_retries=3, failure_threshold=5)
    def critical_db_operation():
        ...

Note:
    This module is specialized for database/low-level operations.
    For API-level operations with circuit breaker support, see utils.resilience.
"""

import functools
import time
import random
import sqlite3
from datetime import datetime, timedelta
from enum import Enum
from threading import Lock
from typing import Callable, Optional, Tuple, Type, Any

from utils.structured_logging import get_logger

logger = get_logger(__name__)


class DatabaseCircuitState(Enum):
    """Circuit breaker states for database operations."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing fast, no DB calls
    HALF_OPEN = "half_open"  # Testing if DB recovered


class DatabaseCircuitBreaker:
    """
    Circuit breaker for database operations.

    Prevents repeated failed database calls when the database is persistently
    unavailable (disk full, corrupted, permissions issues).

    States:
        - CLOSED: Normal operation, database calls proceed
        - OPEN: Database calls fail immediately with DatabaseError
        - HALF_OPEN: Testing recovery, one call allowed through
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        name: Optional[str] = None
    ):
        """
        Initialize database circuit breaker.

        Args:
            failure_threshold: Consecutive failures before opening circuit
            recovery_timeout: Seconds to wait before testing recovery
            name: Optional name for logging
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name or "database"

        self._failure_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._state = DatabaseCircuitState.CLOSED
        self._lock = Lock()

    @property
    def state(self) -> DatabaseCircuitState:
        """Get current circuit state, transitioning to HALF_OPEN if timeout elapsed."""
        with self._lock:
            if self._state == DatabaseCircuitState.OPEN:
                if self._last_failure_time and \
                   datetime.now() - self._last_failure_time > timedelta(seconds=self.recovery_timeout):
                    self._state = DatabaseCircuitState.HALF_OPEN
                    logger.info(f"Database circuit breaker '{self.name}' entering HALF_OPEN state")
            return self._state

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call function through circuit breaker.

        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result of func call

        Raises:
            sqlite3.DatabaseError: When circuit is OPEN
        """
        from utils.exceptions import DatabaseError

        if self.state == DatabaseCircuitState.OPEN:
            raise DatabaseError(
                f"Database circuit breaker '{self.name}' is OPEN. "
                f"Database unavailable, will retry in {self.recovery_timeout}s."
            )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            self._on_failure(e)
            raise

    def _on_success(self):
        """Handle successful database call."""
        with self._lock:
            if self._state == DatabaseCircuitState.HALF_OPEN:
                self._state = DatabaseCircuitState.CLOSED
                logger.info(f"Database circuit breaker '{self.name}' CLOSED after successful call")
            self._failure_count = 0
            self._last_failure_time = None

    def _on_failure(self, error: Exception):
        """Handle failed database call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now()

            if self._failure_count >= self.failure_threshold:
                self._state = DatabaseCircuitState.OPEN
                logger.error(
                    f"Database circuit breaker '{self.name}' OPENED after "
                    f"{self._failure_count} consecutive failures. Last error: {error}"
                )
            elif self._state == DatabaseCircuitState.HALF_OPEN:
                self._state = DatabaseCircuitState.OPEN
                logger.warning(
                    f"Database circuit breaker '{self.name}' reopened after "
                    f"failure in HALF_OPEN state: {error}"
                )

    def reset(self):
        """Manually reset the circuit breaker to CLOSED state."""
        with self._lock:
            self._failure_count = 0
            self._last_failure_time = None
            self._state = DatabaseCircuitState.CLOSED
            logger.info(f"Database circuit breaker '{self.name}' manually reset")

    def get_status(self) -> dict:
        """Get circuit breaker status for monitoring."""
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "failure_threshold": self.failure_threshold,
                "last_failure": self._last_failure_time.isoformat() if self._last_failure_time else None,
                "recovery_timeout": self.recovery_timeout
            }


# Global circuit breaker instance for database operations
_db_circuit_breaker: Optional[DatabaseCircuitBreaker] = None
_db_circuit_lock = Lock()


def get_db_circuit_breaker() -> DatabaseCircuitBreaker:
    """Get or create the global database circuit breaker."""
    global _db_circuit_breaker
    if _db_circuit_breaker is None:
        with _db_circuit_lock:
            if _db_circuit_breaker is None:
                _db_circuit_breaker = DatabaseCircuitBreaker(
                    failure_threshold=5,
                    recovery_timeout=30,
                    name="global_database"
                )
    return _db_circuit_breaker


def exponential_backoff(
    max_retries: int = 3,
    initial_delay: float = 0.1,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
    Decorator that retries a function with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before first retry
        max_delay: Maximum delay in seconds between retries
        exponential_base: Base for exponential backoff calculation
        jitter: Whether to add random jitter to prevent thundering herd
        exceptions: Tuple of exception types to catch and retry
        on_retry: Optional callback called on each retry with (exception, attempt_number)
        
    Returns:
        Decorated function that implements retry logic
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        # Final attempt failed, re-raise the exception
                        logger.error(
                            f"{func.__name__} failed after {max_retries + 1} attempts: {e}"
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        initial_delay * (exponential_base ** attempt),
                        max_delay
                    )
                    
                    # Add jitter if enabled
                    if jitter:
                        delay *= (0.5 + random.random())
                    
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )
                    
                    # Call retry callback if provided
                    if on_retry:
                        on_retry(e, attempt + 1)
                    
                    time.sleep(delay)
            
        return wrapper
    return decorator


# Specialized decorator for database operations
def db_retry(max_retries: int = 3, initial_delay: float = 0.1):
    """
    Specialized retry decorator for database operations.
    
    Handles common database exceptions with appropriate retry logic.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before first retry
        
    Returns:
        Decorated function with database-specific retry logic
    """
    import sqlite3
    
    # Database-specific exceptions that are worth retrying
    retryable_exceptions = (
        sqlite3.OperationalError,  # Database locked, disk I/O error
        sqlite3.DatabaseError,     # General database errors
        ConnectionError,           # Connection issues
        TimeoutError,             # Timeout errors
    )
    
    def on_retry_callback(exception: Exception, attempt: int):
        """Log database retry attempts."""
        if "database is locked" in str(exception).lower():
            logger.info(f"Database locked, retry attempt {attempt}")
        elif "disk I/O error" in str(exception).lower():
            logger.warning(f"Disk I/O error, retry attempt {attempt}")
        else:
            logger.info(f"Database operation retry attempt {attempt}: {exception}")
    
    return exponential_backoff(
        max_retries=max_retries,
        initial_delay=initial_delay,
        max_delay=5.0,  # Cap at 5 seconds for database operations
        exponential_base=2.0,
        jitter=True,
        exceptions=retryable_exceptions,
        on_retry=on_retry_callback
    )


# Composite decorator for resilient database operations
def db_resilient(
    max_retries: int = 3,
    initial_delay: float = 0.1,
    failure_threshold: int = 5,
    recovery_timeout: int = 30
) -> Callable:
    """
    Decorator combining retry and circuit breaker for database operations.

    Use this for critical database operations that should fail fast when
    the database is persistently unavailable.

    Args:
        max_retries: Maximum retry attempts per call
        initial_delay: Initial delay between retries
        failure_threshold: Consecutive failures before opening circuit
        recovery_timeout: Seconds to wait before testing recovery

    Returns:
        Decorated function with retry and circuit breaker protection

    Example:
        @db_resilient(max_retries=3, failure_threshold=5)
        def save_critical_data(data):
            cursor.execute("INSERT INTO table VALUES (?)", (data,))
    """
    def decorator(func: Callable) -> Callable:
        # Create a dedicated circuit breaker for this function
        breaker = DatabaseCircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            name=func.__name__
        )

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # First check circuit breaker
            from utils.exceptions import DatabaseError

            if breaker.state == DatabaseCircuitState.OPEN:
                raise DatabaseError(
                    f"Database circuit breaker for '{func.__name__}' is OPEN. "
                    f"Failing fast to prevent cascade failures."
                )

            # Then apply retry logic
            retryable_exceptions = (
                sqlite3.OperationalError,
                sqlite3.DatabaseError,
                ConnectionError,
                TimeoutError,
            )

            last_exception = None
            delay = initial_delay

            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    breaker._on_success()
                    return result
                except retryable_exceptions as e:
                    last_exception = e
                    breaker._on_failure(e)

                    # Check if circuit just opened
                    if breaker.state == DatabaseCircuitState.OPEN:
                        logger.error(f"Circuit breaker opened for {func.__name__}, stopping retries")
                        raise

                    if attempt == max_retries:
                        logger.error(f"{func.__name__} failed after {max_retries + 1} attempts")
                        raise

                    # Calculate delay with jitter
                    actual_delay = delay * (0.5 + random.random())
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {actual_delay:.2f}s..."
                    )
                    time.sleep(actual_delay)
                    delay = min(delay * 2.0, 5.0)

            if last_exception:
                raise last_exception

        # Attach circuit breaker for manual control
        wrapper.circuit_breaker = breaker
        return wrapper

    return decorator


# Convenience function for network operations
def network_retry(max_retries: int = 5, initial_delay: float = 1.0):
    """
    Specialized retry decorator for network operations.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before first retry
        
    Returns:
        Decorated function with network-specific retry logic
    """
    import requests
    import urllib3
    
    # Network-specific exceptions that are worth retrying
    retryable_exceptions = (
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
        urllib3.exceptions.ReadTimeoutError,
        ConnectionError,
        TimeoutError,
    )
    
    return exponential_backoff(
        max_retries=max_retries,
        initial_delay=initial_delay,
        max_delay=30.0,  # Allow longer delays for network operations
        exponential_base=2.0,
        jitter=True,
        exceptions=retryable_exceptions
    )