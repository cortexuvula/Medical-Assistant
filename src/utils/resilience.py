"""
Resilience patterns for Medical Assistant application.
Includes retry decorators and circuit breaker implementation.

Components:
    - retry: Basic retry decorator with exponential backoff
    - smart_retry: Intelligent retry based on error classification
    - CircuitBreaker: Circuit breaker pattern for failing fast
    - circuit_breaker: Decorator wrapper for CircuitBreaker
    - resilient_api_call: Composite of retry + circuit breaker (recommended)

Error Handling:
    - Retries on: RateLimitError, ServiceUnavailableError, timeouts, connection errors
    - Does not retry: AuthenticationError, InvalidRequestError, validation errors
    - Raises ServiceUnavailableError: When circuit breaker is OPEN

Usage:
    # For AI provider calls (recommended):
    @resilient_api_call(max_retries=3, failure_threshold=5)
    def call_openai_api():
        ...

    # For simpler retry needs:
    @smart_retry(max_retries=3)
    def fetch_data():
        ...

    # Access circuit breaker state:
    if call_openai_api.circuit_breaker.state == CircuitState.OPEN:
        print("Service is unavailable")

Logging:
    Uses structured logging with operation context.
    Logs include: function name, retry attempts, delay times, circuit state changes.

Note:
    This module provides API-level resilience patterns including circuit breaker.
    For database-specific retry logic, see utils.retry_decorator.
"""

import time
import functools
from typing import Callable, Any, Optional, Union, Tuple, Type
from datetime import datetime, timedelta
from enum import Enum
from threading import Lock

from utils.exceptions import (
    APIError, RateLimitError, ServiceUnavailableError,
    AuthenticationError, MedicalAssistantError
)
from utils.structured_logging import get_logger

logger = get_logger(__name__)


# HTTP status codes that are safe to retry (transient errors)
RETRYABLE_HTTP_CODES = frozenset({
    408,  # Request Timeout
    429,  # Too Many Requests (Rate Limit)
    500,  # Internal Server Error (sometimes transient)
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
})

# Error types that indicate transient failures
RETRYABLE_ERROR_TYPES = frozenset({
    'timeout',
    'connection_error',
    'rate_limit',
    'server_error',
    'temporary_failure',
})


def is_retryable_error(error: Exception, status_code: Optional[int] = None) -> bool:
    """
    Determine if an error is safe to retry.

    Args:
        error: The exception that was raised
        status_code: HTTP status code if available

    Returns:
        True if the error should be retried, False otherwise
    """
    # Check status code first if provided
    if status_code is not None and status_code in RETRYABLE_HTTP_CODES:
        return True

    # Check exception type
    if isinstance(error, RateLimitError):
        return True
    if isinstance(error, ServiceUnavailableError):
        return True

    # Check for timeout-related errors
    error_str = str(error).lower()
    if any(keyword in error_str for keyword in ['timeout', 'timed out', 'connection reset']):
        return True

    # Check for connection errors
    if any(keyword in error_str for keyword in ['connection refused', 'connection error', 'network']):
        return True

    # Don't retry authentication or validation errors
    if isinstance(error, AuthenticationError):
        return False
    if 'invalid' in error_str or 'unauthorized' in error_str or 'forbidden' in error_str:
        return False

    # Default: don't retry unknown errors
    return False


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class RetryConfig:
    """Configuration for retry decorator."""
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0,
        max_delay: float = 60.0,
        exceptions: Tuple[Type[Exception], ...] = (APIError,),
        exclude_exceptions: Tuple[Type[Exception], ...] = (AuthenticationError,)
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay
        self.exceptions = exceptions
        self.exclude_exceptions = exclude_exceptions


def retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    exceptions: Tuple[Type[Exception], ...] = (APIError,),
    exclude_exceptions: Tuple[Type[Exception], ...] = (AuthenticationError,)
) -> Callable:
    """
    Retry decorator with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        backoff_factor: Multiplier for delay after each retry
        max_delay: Maximum delay between retries
        exceptions: Tuple of exceptions to retry on
        exclude_exceptions: Tuple of exceptions to not retry on
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exclude_exceptions:
                    # Don't retry on excluded exceptions
                    raise
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"Max retries ({max_retries}) reached for {func.__name__}")
                        raise
                    
                    # Handle rate limit errors with specific retry-after
                    if isinstance(e, RateLimitError) and e.retry_after:
                        delay = min(e.retry_after, max_delay)
                    
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                        f"after {delay:.1f}s due to: {str(e)}"
                    )
                    
                    time.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)
            
            if last_exception:
                raise last_exception

        return wrapper
    return decorator


def smart_retry(
    max_retries: int = 3,
    initial_delay: float = 0.5,
    backoff_factor: float = 2.0,
    max_delay: float = 30.0
) -> Callable:
    """
    Smart retry decorator that only retries on transient errors.

    Uses is_retryable_error() to determine if an error should be retried,
    providing smarter retry logic than the basic retry decorator.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        backoff_factor: Multiplier for delay after each retry
        max_delay: Maximum delay between retries
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # Extract status code if available
                    status_code = getattr(e, 'status_code', None)
                    if status_code is None and hasattr(e, 'response'):
                        status_code = getattr(e.response, 'status_code', None)

                    # Check if error is retryable
                    if not is_retryable_error(e, status_code):
                        logger.debug(f"Non-retryable error in {func.__name__}: {e}")
                        raise

                    if attempt == max_retries:
                        logger.error(f"Max retries ({max_retries}) reached for {func.__name__}")
                        raise

                    # Handle rate limit errors with specific retry-after
                    if isinstance(e, RateLimitError) and e.retry_after:
                        delay = min(e.retry_after, max_delay)

                    logger.warning(
                        f"Smart retry {attempt + 1}/{max_retries} for {func.__name__} "
                        f"after {delay:.1f}s due to: {str(e)}"
                    )

                    time.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)

            if last_exception:
                raise last_exception

        return wrapper
    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.
    
    The circuit breaker has three states:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Requests fail immediately without calling the function
    - HALF_OPEN: Test if the service has recovered
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Type[Exception] = Exception,
        name: Optional[str] = None
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception: Exception type to count as failure
            name: Optional name for logging
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name
        
        self._failure_count = 0
        self._last_failure_time = None
        self._state = CircuitState.CLOSED
        self._lock = Lock()
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._last_failure_time and \
                   datetime.now() - self._last_failure_time > timedelta(seconds=self.recovery_timeout):
                    self._state = CircuitState.HALF_OPEN
                    logger.info(f"Circuit breaker {self.name} entering HALF_OPEN state")
            return self._state
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call function through circuit breaker.
        
        Args:
            func: Function to call
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Result of func call
            
        Raises:
            ServiceUnavailableError: When circuit is open
        """
        if self.state == CircuitState.OPEN:
            raise ServiceUnavailableError(
                f"Circuit breaker {self.name} is OPEN. Service unavailable."
            )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                logger.info(f"Circuit breaker {self.name} closed after successful call")
            self._failure_count = 0
            self._last_failure_time = None
    
    def _on_failure(self):
        """Handle failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now()
            
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.error(
                    f"Circuit breaker {self.name} opened after "
                    f"{self._failure_count} failures"
                )
            elif self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit breaker {self.name} reopened after failure in HALF_OPEN state")
    
    def reset(self):
        """Manually reset the circuit breaker."""
        with self._lock:
            self._failure_count = 0
            self._last_failure_time = None
            self._state = CircuitState.CLOSED
            logger.info(f"Circuit breaker {self.name} manually reset")


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: Type[Exception] = APIError,
    name: Optional[str] = None
) -> Callable:
    """
    Circuit breaker decorator.
    
    Args:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before attempting recovery
        expected_exception: Exception type to count as failure
        name: Optional name for the circuit breaker
    """
    def decorator(func: Callable) -> Callable:
        # Use function name if no name provided
        breaker_name = name or func.__name__
        breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
            name=breaker_name
        )
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            return breaker.call(func, *args, **kwargs)
        
        # Attach circuit breaker instance for manual control
        wrapper.circuit_breaker = breaker
        return wrapper
    
    return decorator


# Composite decorator for both retry and circuit breaker
def resilient_api_call(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    failure_threshold: int = 5,
    recovery_timeout: int = 60
) -> Callable:
    """
    Decorator combining retry and circuit breaker patterns.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries
        backoff_factor: Multiplier for delay after each retry
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before attempting recovery
    """
    def decorator(func: Callable) -> Callable:
        # Apply circuit breaker first, then retry
        @circuit_breaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=APIError
        )
        @retry(
            max_retries=max_retries,
            initial_delay=initial_delay,
            backoff_factor=backoff_factor,
            exceptions=(APIError, ServiceUnavailableError)
        )
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator