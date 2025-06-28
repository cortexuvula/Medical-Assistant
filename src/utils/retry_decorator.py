"""
Retry decorator with exponential backoff for database operations.

This module provides a decorator that can be used to automatically retry
failed operations with exponential backoff.
"""

import functools
import logging
import time
import random
from typing import Callable, Optional, Tuple, Type


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
                        logging.error(
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
                    
                    logging.warning(
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
            logging.info(f"Database locked, retry attempt {attempt}")
        elif "disk I/O error" in str(exception).lower():
            logging.warning(f"Disk I/O error, retry attempt {attempt}")
        else:
            logging.info(f"Database operation retry attempt {attempt}: {exception}")
    
    return exponential_backoff(
        max_retries=max_retries,
        initial_delay=initial_delay,
        max_delay=5.0,  # Cap at 5 seconds for database operations
        exponential_base=2.0,
        jitter=True,
        exceptions=retryable_exceptions,
        on_retry=on_retry_callback
    )


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