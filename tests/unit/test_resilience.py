"""
Tests for src/utils/resilience.py

Covers:
- RETRYABLE_HTTP_CODES frozenset
- RETRYABLE_ERROR_TYPES frozenset
- is_retryable_error() classification logic
- CircuitState enum
- RetryConfig defaults and custom values
- CircuitBreaker init, state transitions, call(), _on_success, _on_failure, reset()

Excluded: retry / smart_retry / circuit_breaker / resilient_api_call decorators
(they use time.sleep and are not pure-logic).
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from utils.resilience import (
    RETRYABLE_HTTP_CODES,
    RETRYABLE_ERROR_TYPES,
    is_retryable_error,
    CircuitState,
    RetryConfig,
    CircuitBreaker,
)
from utils.exceptions import (
    PermanentError,
    RetryableError,
    RateLimitError,
    ServiceUnavailableError,
    AuthenticationError,
    APIError,
)


# ---------------------------------------------------------------------------
# Helpers — concrete classes using the mixin pattern defined in exceptions.py
# ---------------------------------------------------------------------------

class ConcretePermanentError(Exception, PermanentError):
    """An error that explicitly inherits PermanentError mixin."""


class ConcreteRetryableError(Exception, RetryableError):
    """An error that explicitly inherits RetryableError mixin."""


class ConcreteAPIError(APIError):
    """Generic APIError subclass for tests that need an APIError instance."""


# ===========================================================================
# 1. RETRYABLE_HTTP_CODES
# ===========================================================================

class TestRetryableHttpCodes:
    """Tests for the RETRYABLE_HTTP_CODES frozenset constant."""

    def test_is_frozenset(self):
        assert isinstance(RETRYABLE_HTTP_CODES, frozenset)

    def test_contains_six_codes(self):
        assert len(RETRYABLE_HTTP_CODES) == 6

    def test_contains_408(self):
        assert 408 in RETRYABLE_HTTP_CODES

    def test_contains_429(self):
        assert 429 in RETRYABLE_HTTP_CODES

    def test_contains_500(self):
        assert 500 in RETRYABLE_HTTP_CODES

    def test_contains_502(self):
        assert 502 in RETRYABLE_HTTP_CODES

    def test_contains_503(self):
        assert 503 in RETRYABLE_HTTP_CODES

    def test_contains_504(self):
        assert 504 in RETRYABLE_HTTP_CODES

    def test_does_not_contain_200(self):
        assert 200 not in RETRYABLE_HTTP_CODES

    def test_does_not_contain_400(self):
        assert 400 not in RETRYABLE_HTTP_CODES

    def test_does_not_contain_401(self):
        assert 401 not in RETRYABLE_HTTP_CODES

    def test_does_not_contain_403(self):
        assert 403 not in RETRYABLE_HTTP_CODES

    def test_immutable(self):
        """frozenset should raise AttributeError on mutation attempt."""
        try:
            RETRYABLE_HTTP_CODES.add(999)  # type: ignore[attr-defined]
            assert False, "Expected AttributeError"
        except AttributeError:
            pass


# ===========================================================================
# 2. RETRYABLE_ERROR_TYPES
# ===========================================================================

class TestRetryableErrorTypes:
    """Tests for the RETRYABLE_ERROR_TYPES frozenset constant."""

    def test_is_frozenset(self):
        assert isinstance(RETRYABLE_ERROR_TYPES, frozenset)

    def test_contains_five_types(self):
        assert len(RETRYABLE_ERROR_TYPES) == 5

    def test_contains_timeout(self):
        assert "timeout" in RETRYABLE_ERROR_TYPES

    def test_contains_connection_error(self):
        assert "connection_error" in RETRYABLE_ERROR_TYPES

    def test_contains_rate_limit(self):
        assert "rate_limit" in RETRYABLE_ERROR_TYPES

    def test_contains_server_error(self):
        assert "server_error" in RETRYABLE_ERROR_TYPES

    def test_contains_temporary_failure(self):
        assert "temporary_failure" in RETRYABLE_ERROR_TYPES

    def test_does_not_contain_auth_error(self):
        assert "auth_error" not in RETRYABLE_ERROR_TYPES

    def test_does_not_contain_permanent_failure(self):
        assert "permanent_failure" not in RETRYABLE_ERROR_TYPES

    def test_immutable(self):
        try:
            RETRYABLE_ERROR_TYPES.add("new_type")  # type: ignore[attr-defined]
            assert False, "Expected AttributeError"
        except AttributeError:
            pass


# ===========================================================================
# 3. is_retryable_error
# ===========================================================================

class TestIsRetryableErrorMixins:
    """Mixin-class-based classification tests."""

    def test_permanent_error_mixin_returns_false(self):
        err = ConcretePermanentError("permanent")
        assert is_retryable_error(err) is False

    def test_retryable_error_mixin_returns_true(self):
        err = ConcreteRetryableError("transient")
        assert is_retryable_error(err) is True

    def test_permanent_mixin_overrides_retryable_status_code(self):
        """PermanentError mixin wins even if a retryable status code is given."""
        err = ConcretePermanentError("permanent with status")
        assert is_retryable_error(err, status_code=503) is False

    def test_retryable_mixin_overrides_non_retryable_message(self):
        """RetryableError mixin wins even if message looks like invalid/forbidden."""
        err = ConcreteRetryableError("invalid data")
        assert is_retryable_error(err) is True


class TestIsRetryableErrorStatusCode:
    """HTTP status code classification tests."""

    def test_status_code_429_returns_true(self):
        err = ValueError("some error")
        assert is_retryable_error(err, status_code=429) is True

    def test_status_code_503_returns_true(self):
        err = ValueError("some error")
        assert is_retryable_error(err, status_code=503) is True

    def test_status_code_500_returns_true(self):
        err = ValueError("some error")
        assert is_retryable_error(err, status_code=500) is True

    def test_status_code_502_returns_true(self):
        err = ValueError("some error")
        assert is_retryable_error(err, status_code=502) is True

    def test_status_code_504_returns_true(self):
        err = ValueError("some error")
        assert is_retryable_error(err, status_code=504) is True

    def test_status_code_408_returns_true(self):
        err = ValueError("some error")
        assert is_retryable_error(err, status_code=408) is True

    def test_status_code_400_returns_false(self):
        err = ValueError("some error")
        assert is_retryable_error(err, status_code=400) is False

    def test_status_code_200_returns_false(self):
        err = ValueError("some error")
        assert is_retryable_error(err, status_code=200) is False

    def test_no_status_code_unknown_error_returns_false(self):
        err = ValueError("unknown error")
        assert is_retryable_error(err) is False


class TestIsRetryableErrorExceptionTypes:
    """Exception-type-based classification tests."""

    def test_rate_limit_error_returns_true(self):
        err = RateLimitError("Rate limit hit")
        assert is_retryable_error(err) is True

    def test_rate_limit_error_with_retry_after_returns_true(self):
        err = RateLimitError("Rate limit hit", retry_after=30)
        assert is_retryable_error(err) is True

    def test_service_unavailable_error_returns_true(self):
        err = ServiceUnavailableError("Service down")
        assert is_retryable_error(err) is True

    def test_authentication_error_returns_false(self):
        err = AuthenticationError("Invalid API key")
        assert is_retryable_error(err) is False

    def test_generic_api_error_unknown_returns_false(self):
        """A plain APIError with no matching keywords/status should return False."""
        err = APIError("Unexpected internal error")
        # No retryable marker, no retryable status, no retryable keywords
        assert is_retryable_error(err) is False

    def test_generic_exception_returns_false(self):
        err = Exception("something unexpected happened")
        assert is_retryable_error(err) is False


class TestIsRetryableErrorMessageKeywords:
    """Error-message-based classification tests."""

    def test_timeout_keyword_returns_true(self):
        err = Exception("Operation timeout exceeded")
        assert is_retryable_error(err) is True

    def test_timed_out_keyword_returns_true(self):
        err = Exception("Request timed out after 30s")
        assert is_retryable_error(err) is True

    def test_connection_reset_returns_true(self):
        err = Exception("connection reset by peer")
        assert is_retryable_error(err) is True

    def test_connection_refused_returns_true(self):
        err = Exception("connection refused")
        assert is_retryable_error(err) is True

    def test_connection_error_keyword_returns_true(self):
        err = Exception("A connection error occurred")
        assert is_retryable_error(err) is True

    def test_network_keyword_returns_true(self):
        err = Exception("network unreachable")
        assert is_retryable_error(err) is True

    def test_case_insensitive_timeout(self):
        err = Exception("TIMEOUT when reaching the server")
        assert is_retryable_error(err) is True

    def test_invalid_keyword_returns_false(self):
        err = Exception("invalid request parameters")
        assert is_retryable_error(err) is False

    def test_unauthorized_keyword_returns_false(self):
        err = Exception("unauthorized access")
        assert is_retryable_error(err) is False

    def test_forbidden_keyword_returns_false(self):
        err = Exception("forbidden endpoint")
        assert is_retryable_error(err) is False

    def test_empty_message_returns_false(self):
        err = Exception("")
        assert is_retryable_error(err) is False


# ===========================================================================
# 4. CircuitState enum
# ===========================================================================

class TestCircuitStateEnum:
    """Tests for the CircuitState enum."""

    def test_has_three_members(self):
        assert len(CircuitState) == 3

    def test_closed_member_exists(self):
        assert hasattr(CircuitState, "CLOSED")

    def test_open_member_exists(self):
        assert hasattr(CircuitState, "OPEN")

    def test_half_open_member_exists(self):
        assert hasattr(CircuitState, "HALF_OPEN")

    def test_closed_value(self):
        assert CircuitState.CLOSED.value == "closed"

    def test_open_value(self):
        assert CircuitState.OPEN.value == "open"

    def test_half_open_value(self):
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_members_are_distinct(self):
        states = {CircuitState.CLOSED, CircuitState.OPEN, CircuitState.HALF_OPEN}
        assert len(states) == 3


# ===========================================================================
# 5. RetryConfig defaults
# ===========================================================================

class TestRetryConfigDefaults:
    """Tests for RetryConfig default parameter values."""

    def setup_method(self):
        self.config = RetryConfig()

    def test_max_retries_default(self):
        assert self.config.max_retries == 3

    def test_initial_delay_default(self):
        assert self.config.initial_delay == 1.0

    def test_backoff_factor_default(self):
        assert self.config.backoff_factor == 2.0

    def test_max_delay_default(self):
        assert self.config.max_delay == 60.0

    def test_exceptions_default_contains_api_error(self):
        assert APIError in self.config.exceptions

    def test_exclude_exceptions_default_contains_auth_error(self):
        assert AuthenticationError in self.config.exclude_exceptions


# ===========================================================================
# 6. RetryConfig custom values
# ===========================================================================

class TestRetryConfigCustomValues:
    """Tests for RetryConfig with non-default arguments."""

    def test_custom_max_retries(self):
        config = RetryConfig(max_retries=10)
        assert config.max_retries == 10

    def test_custom_initial_delay(self):
        config = RetryConfig(initial_delay=0.5)
        assert config.initial_delay == 0.5

    def test_custom_backoff_factor(self):
        config = RetryConfig(backoff_factor=3.0)
        assert config.backoff_factor == 3.0

    def test_custom_max_delay(self):
        config = RetryConfig(max_delay=120.0)
        assert config.max_delay == 120.0

    def test_custom_exceptions(self):
        config = RetryConfig(exceptions=(ValueError, RuntimeError))
        assert ValueError in config.exceptions
        assert RuntimeError in config.exceptions

    def test_custom_exclude_exceptions(self):
        config = RetryConfig(exclude_exceptions=(TypeError,))
        assert TypeError in config.exclude_exceptions

    def test_all_custom_values(self):
        config = RetryConfig(
            max_retries=5,
            initial_delay=0.25,
            backoff_factor=1.5,
            max_delay=30.0,
        )
        assert config.max_retries == 5
        assert config.initial_delay == 0.25
        assert config.backoff_factor == 1.5
        assert config.max_delay == 30.0


# ===========================================================================
# 7. CircuitBreaker init
# ===========================================================================

class TestCircuitBreakerInit:
    """Tests for CircuitBreaker.__init__."""

    def test_starts_in_closed_state(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED

    def test_failure_count_starts_at_zero(self):
        cb = CircuitBreaker()
        assert cb._failure_count == 0

    def test_name_stored(self):
        cb = CircuitBreaker(name="test_breaker")
        assert cb.name == "test_breaker"

    def test_name_none_by_default(self):
        cb = CircuitBreaker()
        assert cb.name is None

    def test_failure_threshold_stored(self):
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.failure_threshold == 3

    def test_recovery_timeout_stored(self):
        cb = CircuitBreaker(recovery_timeout=120)
        assert cb.recovery_timeout == 120

    def test_expected_exception_stored(self):
        cb = CircuitBreaker(expected_exception=ValueError)
        assert cb.expected_exception is ValueError

    def test_default_failure_threshold(self):
        cb = CircuitBreaker()
        assert cb.failure_threshold == 5

    def test_default_recovery_timeout(self):
        cb = CircuitBreaker()
        assert cb.recovery_timeout == 60

    def test_last_failure_time_none_initially(self):
        cb = CircuitBreaker()
        assert cb._last_failure_time is None


# ===========================================================================
# 8. CircuitBreaker.call — success and failure cases
# ===========================================================================

class TestCircuitBreakerCall:
    """Tests for CircuitBreaker.call()."""

    def test_call_returns_function_result_on_success(self):
        cb = CircuitBreaker(failure_threshold=5)
        result = cb.call(lambda: 42)
        assert result == 42

    def test_call_passes_positional_args(self):
        cb = CircuitBreaker()
        result = cb.call(lambda x, y: x + y, 3, 4)
        assert result == 7

    def test_call_passes_keyword_args(self):
        cb = CircuitBreaker()
        result = cb.call(lambda x, y=0: x * y, 6, y=7)
        assert result == 42

    def test_call_raises_on_function_exception(self):
        import pytest

        cb = CircuitBreaker(expected_exception=ValueError)

        def raise_val():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            cb.call(raise_val)

    def test_call_increments_failure_count_on_exception(self):
        cb = CircuitBreaker(expected_exception=ValueError, failure_threshold=10)

        def raise_val():
            raise ValueError("fail")

        try:
            cb.call(raise_val)
        except ValueError:
            pass
        assert cb._failure_count == 1

    def test_call_resets_failure_count_on_success_after_failure(self):
        cb = CircuitBreaker(expected_exception=ValueError, failure_threshold=10)

        def raise_val():
            raise ValueError("fail")

        try:
            cb.call(raise_val)
        except ValueError:
            pass

        assert cb._failure_count == 1
        cb.call(lambda: None)
        assert cb._failure_count == 0

    def test_call_does_not_count_unexpected_exception_type(self):
        """Exceptions NOT matching expected_exception bypass failure counting."""
        cb = CircuitBreaker(expected_exception=ValueError, failure_threshold=5)

        def raise_runtime():
            raise RuntimeError("unexpected")

        try:
            cb.call(raise_runtime)
        except RuntimeError:
            pass
        # failure_count stays 0 because RuntimeError is not ValueError
        assert cb._failure_count == 0


# ===========================================================================
# 9. CircuitBreaker: threshold failures → OPEN state
# ===========================================================================

class TestCircuitBreakerOpens:
    """Tests that the circuit opens after reaching the failure threshold."""

    def _exhaust_failures(self, cb, count):
        def raise_err():
            raise Exception("fail")

        for _ in range(count):
            try:
                cb.call(raise_err)
            except Exception:
                pass

    def test_state_remains_closed_below_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, expected_exception=Exception)
        self._exhaust_failures(cb, 2)
        assert cb.state == CircuitState.CLOSED

    def test_state_becomes_open_at_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, expected_exception=Exception)
        self._exhaust_failures(cb, 3)
        assert cb._state == CircuitState.OPEN

    def test_state_becomes_open_above_threshold(self):
        cb = CircuitBreaker(failure_threshold=2, expected_exception=Exception)
        self._exhaust_failures(cb, 5)
        assert cb._state == CircuitState.OPEN

    def test_failure_count_tracked_correctly(self):
        cb = CircuitBreaker(failure_threshold=4, expected_exception=Exception)
        self._exhaust_failures(cb, 4)
        assert cb._failure_count == 4

    def test_last_failure_time_set_on_failure(self):
        from datetime import datetime

        cb = CircuitBreaker(failure_threshold=5, expected_exception=Exception)
        self._exhaust_failures(cb, 1)
        assert cb._last_failure_time is not None
        assert isinstance(cb._last_failure_time, datetime)


# ===========================================================================
# 10. CircuitBreaker when OPEN: raises ServiceUnavailableError without calling func
# ===========================================================================

class TestCircuitBreakerOpenState:
    """Tests for behaviour when the circuit is OPEN."""

    def _open_breaker(self, threshold=2):
        cb = CircuitBreaker(failure_threshold=threshold, expected_exception=Exception)
        for _ in range(threshold):
            try:
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass
        return cb

    def test_raises_service_unavailable_when_open(self):
        import pytest

        cb = self._open_breaker(threshold=2)
        with pytest.raises(ServiceUnavailableError):
            cb.call(lambda: "should not be called")

    def test_function_not_called_when_open(self):
        import pytest

        cb = self._open_breaker(threshold=2)
        called = []

        def track():
            called.append(True)
            return "ok"

        with pytest.raises(ServiceUnavailableError):
            cb.call(track)

        assert called == [], "Function should not be invoked when circuit is OPEN"

    def test_service_unavailable_message_contains_breaker_name(self):
        import pytest

        cb = CircuitBreaker(
            failure_threshold=1,
            expected_exception=Exception,
            name="my_service",
        )
        try:
            cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        except Exception:
            pass

        with pytest.raises(ServiceUnavailableError) as exc_info:
            cb.call(lambda: None)

        assert "my_service" in str(exc_info.value)


# ===========================================================================
# 11. CircuitBreaker._on_success in HALF_OPEN → CLOSED, resets failure_count
# ===========================================================================

class TestCircuitBreakerOnSuccess:
    """Tests for _on_success behaviour."""

    def test_on_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=10, expected_exception=Exception)
        cb._failure_count = 7
        cb._on_success()
        assert cb._failure_count == 0

    def test_on_success_in_closed_state_stays_closed(self):
        cb = CircuitBreaker()
        cb._on_success()
        assert cb._state == CircuitState.CLOSED

    def test_on_success_in_half_open_transitions_to_closed(self):
        cb = CircuitBreaker()
        cb._state = CircuitState.HALF_OPEN
        cb._failure_count = 3
        cb._on_success()
        assert cb._state == CircuitState.CLOSED

    def test_on_success_in_half_open_resets_failure_count(self):
        cb = CircuitBreaker()
        cb._state = CircuitState.HALF_OPEN
        cb._failure_count = 5
        cb._on_success()
        assert cb._failure_count == 0

    def test_on_success_clears_last_failure_time(self):
        from datetime import datetime

        cb = CircuitBreaker()
        cb._last_failure_time = datetime.now()
        cb._on_success()
        assert cb._last_failure_time is None


# ===========================================================================
# 12. CircuitBreaker.reset
# ===========================================================================

class TestCircuitBreakerReset:
    """Tests for CircuitBreaker.reset()."""

    def test_reset_returns_to_closed_from_open(self):
        cb = CircuitBreaker(failure_threshold=2, expected_exception=Exception)
        cb._state = CircuitState.OPEN
        cb._failure_count = 5
        cb.reset()
        assert cb._state == CircuitState.CLOSED

    def test_reset_clears_failure_count(self):
        cb = CircuitBreaker()
        cb._failure_count = 99
        cb.reset()
        assert cb._failure_count == 0

    def test_reset_clears_last_failure_time(self):
        from datetime import datetime

        cb = CircuitBreaker()
        cb._last_failure_time = datetime.now()
        cb.reset()
        assert cb._last_failure_time is None

    def test_reset_from_half_open_to_closed(self):
        cb = CircuitBreaker()
        cb._state = CircuitState.HALF_OPEN
        cb.reset()
        assert cb._state == CircuitState.CLOSED

    def test_reset_allows_calls_after_open(self):
        """After reset, calls should succeed again without raising ServiceUnavailableError."""
        cb = CircuitBreaker(failure_threshold=1, expected_exception=Exception)
        try:
            cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        except Exception:
            pass
        assert cb._state == CircuitState.OPEN

        cb.reset()
        result = cb.call(lambda: "ok")
        assert result == "ok"

    def test_reset_idempotent_when_already_closed(self):
        cb = CircuitBreaker()
        cb.reset()
        cb.reset()
        assert cb._state == CircuitState.CLOSED
        assert cb._failure_count == 0

    def test_reset_followed_by_new_failures_reopens(self):
        cb = CircuitBreaker(failure_threshold=2, expected_exception=Exception)
        cb._state = CircuitState.OPEN
        cb.reset()

        for _ in range(2):
            try:
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass

        assert cb._state == CircuitState.OPEN


# ===========================================================================
# 13. CircuitBreaker._on_failure edge cases
# ===========================================================================

class TestCircuitBreakerOnFailure:
    """Tests for _on_failure behaviour."""

    def test_on_failure_increments_count(self):
        cb = CircuitBreaker(failure_threshold=5)
        cb._on_failure()
        assert cb._failure_count == 1

    def test_on_failure_multiple_increments(self):
        cb = CircuitBreaker(failure_threshold=5)
        for _ in range(4):
            cb._on_failure()
        assert cb._failure_count == 4

    def test_on_failure_at_threshold_opens_circuit(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb._on_failure()
        assert cb._state == CircuitState.OPEN

    def test_on_failure_in_half_open_reopens(self):
        cb = CircuitBreaker(failure_threshold=5)
        cb._state = CircuitState.HALF_OPEN
        cb._on_failure()
        assert cb._state == CircuitState.OPEN

    def test_on_failure_in_half_open_reopens_before_threshold(self):
        """A single failure in HALF_OPEN reopens immediately regardless of threshold."""
        cb = CircuitBreaker(failure_threshold=10)
        cb._state = CircuitState.HALF_OPEN
        cb._failure_count = 0
        cb._on_failure()
        assert cb._state == CircuitState.OPEN

    def test_on_failure_sets_last_failure_time(self):
        from datetime import datetime

        cb = CircuitBreaker(failure_threshold=5)
        cb._on_failure()
        assert cb._last_failure_time is not None
        assert isinstance(cb._last_failure_time, datetime)
