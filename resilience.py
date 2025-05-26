"""
Resilience patterns for Medical Assistant application.
Includes retry decorators and circuit breaker implementation.
"""

import time
import functools
import logging
from typing import Callable, Any, Optional, Union, Tuple, Type
from datetime import datetime, timedelta
from enum import Enum
from threading import Lock

from exceptions import (
    APIError, RateLimitError, ServiceUnavailableError,
    AuthenticationError, MedicalAssistantError
)

logger = logging.getLogger(__name__)


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