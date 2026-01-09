"""
Tests for the resilience module (retry and circuit breaker patterns).
"""

import pytest
import time
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from utils.exceptions import APIError, RateLimitError, ServiceUnavailableError, AuthenticationError
from utils.resilience import retry, CircuitBreaker, circuit_breaker, resilient_api_call, CircuitState


class TestRetryDecorator:
    """Test cases for the retry decorator."""
    
    def test_successful_call_no_retry(self):
        """Test that successful calls don't trigger retries."""
        mock_func = Mock(return_value="success")
        
        @retry(max_retries=3)
        def test_func():
            return mock_func()
        
        result = test_func()
        assert result == "success"
        assert mock_func.call_count == 1
    
    def test_retry_on_api_error(self):
        """Test that API errors trigger retries."""
        mock_func = Mock(side_effect=[APIError("Failed"), APIError("Failed"), "success"])
        
        @retry(max_retries=3, initial_delay=0.1)
        def test_func():
            return mock_func()
        
        result = test_func()
        assert result == "success"
        assert mock_func.call_count == 3
    
    def test_max_retries_exceeded(self):
        """Test that exception is raised after max retries."""
        mock_func = Mock(side_effect=APIError("Failed"))
        
        @retry(max_retries=2, initial_delay=0.1)
        def test_func():
            return mock_func()
        
        with pytest.raises(APIError):
            test_func()
        
        assert mock_func.call_count == 3  # Initial + 2 retries
    
    def test_no_retry_on_excluded_exception(self):
        """Test that excluded exceptions don't trigger retries."""
        mock_func = Mock(side_effect=AuthenticationError("Auth failed"))
        
        @retry(max_retries=3, exclude_exceptions=(AuthenticationError,))
        def test_func():
            return mock_func()
        
        with pytest.raises(AuthenticationError):
            test_func()
        
        assert mock_func.call_count == 1
    
    def test_rate_limit_retry_after(self):
        """Test that rate limit errors use retry-after header."""
        error = RateLimitError("Rate limited", retry_after=2)
        mock_func = Mock(side_effect=[error, "success"])

        @retry(max_retries=3, initial_delay=0.1)
        def test_func():
            return mock_func()

        # Mock time.sleep to verify it's called with the correct delay
        with patch('utils.resilience.time.sleep') as mock_sleep:
            result = test_func()

        assert result == "success"
        assert mock_func.call_count == 2
        # Verify sleep was called with the retry_after value (2 seconds)
        mock_sleep.assert_called_once_with(2)
    
    def test_exponential_backoff(self):
        """Test exponential backoff between retries."""
        mock_func = Mock(side_effect=[APIError("Failed"), APIError("Failed"), "success"])
        
        @retry(max_retries=3, initial_delay=0.1, backoff_factor=2.0)
        def test_func():
            return mock_func()
        
        start_time = time.time()
        result = test_func()
        elapsed = time.time() - start_time
        
        assert result == "success"
        assert mock_func.call_count == 3
        # Should wait 0.1 + 0.2 = 0.3 seconds minimum
        assert elapsed >= 0.3


class TestCircuitBreaker:
    """Test cases for the circuit breaker pattern."""
    
    def test_circuit_closed_successful_calls(self):
        """Test circuit remains closed on successful calls."""
        breaker = CircuitBreaker(failure_threshold=3)
        mock_func = Mock(return_value="success")
        
        for _ in range(5):
            result = breaker.call(mock_func)
            assert result == "success"
        
        assert breaker.state == CircuitState.CLOSED
        assert mock_func.call_count == 5
    
    def test_circuit_opens_after_failures(self):
        """Test circuit opens after failure threshold."""
        breaker = CircuitBreaker(failure_threshold=3, expected_exception=APIError)
        mock_func = Mock(side_effect=APIError("Failed"))
        
        for i in range(3):
            with pytest.raises(APIError):
                breaker.call(mock_func)
        
        assert breaker.state == CircuitState.OPEN
        assert mock_func.call_count == 3
        
        # Next call should fail immediately without calling function
        with pytest.raises(ServiceUnavailableError):
            breaker.call(mock_func)
        
        assert mock_func.call_count == 3  # No additional calls
    
    def test_circuit_half_open_after_timeout(self):
        """Test circuit enters half-open state after recovery timeout."""
        breaker = CircuitBreaker(
            failure_threshold=1, 
            recovery_timeout=1,  # 1 second
            expected_exception=APIError
        )
        mock_func = Mock(side_effect=APIError("Failed"))
        
        # Open the circuit
        with pytest.raises(APIError):
            breaker.call(mock_func)
        
        assert breaker.state == CircuitState.OPEN
        
        # Wait for recovery timeout
        time.sleep(1.1)
        
        # Circuit should be half-open now
        assert breaker.state == CircuitState.HALF_OPEN
    
    def test_circuit_closes_on_half_open_success(self):
        """Test circuit closes when half-open call succeeds."""
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=1,
            expected_exception=APIError
        )
        
        # Open the circuit
        with pytest.raises(APIError):
            breaker.call(Mock(side_effect=APIError("Failed")))
        
        # Wait for half-open
        time.sleep(1.1)
        
        # Successful call should close circuit
        result = breaker.call(Mock(return_value="success"))
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED
    
    def test_circuit_reopens_on_half_open_failure(self):
        """Test circuit reopens when half-open call fails."""
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=1,
            expected_exception=APIError
        )
        
        # Open the circuit
        with pytest.raises(APIError):
            breaker.call(Mock(side_effect=APIError("Failed")))
        
        # Wait for half-open
        time.sleep(1.1)
        
        # Failed call should reopen circuit
        with pytest.raises(APIError):
            breaker.call(Mock(side_effect=APIError("Still failing")))
        
        assert breaker.state == CircuitState.OPEN
    
    def test_manual_reset(self):
        """Test manual circuit reset."""
        breaker = CircuitBreaker(failure_threshold=1, expected_exception=APIError)
        
        # Open the circuit
        with pytest.raises(APIError):
            breaker.call(Mock(side_effect=APIError("Failed")))
        
        assert breaker.state == CircuitState.OPEN
        
        # Manual reset
        breaker.reset()
        assert breaker.state == CircuitState.CLOSED


class TestCircuitBreakerDecorator:
    """Test cases for the circuit breaker decorator."""
    
    def test_decorator_basic_functionality(self):
        """Test circuit breaker decorator basic functionality."""
        mock = Mock(side_effect=[APIError("Failed"), APIError("Failed"), "success"])
        
        @circuit_breaker(failure_threshold=2, recovery_timeout=1)
        def test_func():
            return mock()
        
        # First two calls should fail and open circuit
        with pytest.raises(APIError):
            test_func()
        with pytest.raises(APIError):
            test_func()
        
        # Circuit should be open
        with pytest.raises(ServiceUnavailableError):
            test_func()
        
        # Wait for recovery
        time.sleep(1.1)
        
        # Should work now
        result = test_func()
        assert result == "success"
    
    def test_decorator_exposes_circuit_breaker(self):
        """Test that decorator exposes circuit breaker instance."""
        @circuit_breaker(failure_threshold=3)
        def test_func():
            return "success"
        
        assert hasattr(test_func, 'circuit_breaker')
        assert isinstance(test_func.circuit_breaker, CircuitBreaker)


class TestResilientApiCall:
    """Test cases for the combined resilient API call decorator."""
    
    def test_combined_retry_and_circuit_breaker(self):
        """Test that retry and circuit breaker work together."""
        call_count = 0
        
        @resilient_api_call(
            max_retries=2,
            initial_delay=0.1,
            failure_threshold=5,
            recovery_timeout=1
        )
        def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise APIError("Failed")
            return "success"
        
        # Should retry twice and succeed on third attempt
        result = test_func()
        assert result == "success"
        assert call_count == 3
        
        # Reset for next test
        call_count = 0
        
        # Create a new function that always fails to test circuit opening
        @resilient_api_call(
            max_retries=2,
            initial_delay=0.1,
            failure_threshold=3,
            recovery_timeout=1
        )
        def always_fail_func():
            raise APIError("Always fails")
        
        # Make it fail enough times to open circuit
        for _ in range(3):
            try:
                always_fail_func()
            except (APIError, ServiceUnavailableError):
                pass
        
        # Circuit should be open now
        with pytest.raises(ServiceUnavailableError):
            always_fail_func()


# Integration test
def test_integration_with_actual_api_call():
    """Test integration with a simulated API call."""
    class MockAPIClient:
        def __init__(self):
            self.call_count = 0
            self.should_fail_until = 3
        
        @resilient_api_call(
            max_retries=3,
            initial_delay=0.1,
            failure_threshold=5
        )
        def make_request(self, endpoint: str):
            self.call_count += 1
            if self.call_count < self.should_fail_until:
                raise APIError(f"Request to {endpoint} failed")
            return {"status": "success", "data": "test"}
    
    client = MockAPIClient()
    
    # Should succeed after retries
    result = client.make_request("/test")
    assert result["status"] == "success"
    assert client.call_count == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])