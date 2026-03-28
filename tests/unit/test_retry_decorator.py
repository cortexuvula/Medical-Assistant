"""Unit tests for utils.retry_decorator — retry + circuit breaker for DB operations."""

import unittest
import sqlite3
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from utils.retry_decorator import (
    DatabaseCircuitState,
    DatabaseCircuitBreaker,
    get_db_circuit_breaker,
    exponential_backoff,
    db_retry,
    db_resilient,
)
import utils.retry_decorator as retry_module


class TestDatabaseCircuitState(unittest.TestCase):

    def test_closed_value(self):
        assert DatabaseCircuitState.CLOSED.value == "closed"

    def test_open_value(self):
        assert DatabaseCircuitState.OPEN.value == "open"

    def test_half_open_value(self):
        assert DatabaseCircuitState.HALF_OPEN.value == "half_open"


class TestDatabaseCircuitBreaker(unittest.TestCase):

    def test_initial_state_is_closed(self):
        cb = DatabaseCircuitBreaker()
        assert cb.state == DatabaseCircuitState.CLOSED

    def test_default_parameters(self):
        cb = DatabaseCircuitBreaker()
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 30

    def test_custom_name(self):
        cb = DatabaseCircuitBreaker(name="test_breaker")
        assert cb.name == "test_breaker"

    def test_default_name(self):
        cb = DatabaseCircuitBreaker()
        assert cb.name == "database"

    def test_call_succeeds(self):
        cb = DatabaseCircuitBreaker()
        result = cb.call(lambda: 42)
        assert result == 42

    def test_call_passes_args(self):
        cb = DatabaseCircuitBreaker()
        result = cb.call(lambda x, y: x + y, 3, 4)
        assert result == 7

    def test_call_passes_kwargs(self):
        cb = DatabaseCircuitBreaker()
        result = cb.call(lambda x=0: x * 2, x=5)
        assert result == 10

    def test_call_when_open_raises(self):
        cb = DatabaseCircuitBreaker(failure_threshold=1)
        try:
            cb.call(self._fail_with_operational_error)
        except sqlite3.OperationalError:
            pass
        with self.assertRaises(Exception) as ctx:
            cb.call(lambda: 42)
        assert "OPEN" in str(ctx.exception)

    def test_failure_increments_count(self):
        cb = DatabaseCircuitBreaker(failure_threshold=10)
        try:
            cb.call(self._fail_with_operational_error)
        except sqlite3.OperationalError:
            pass
        assert cb._failure_count == 1

    def test_opens_at_threshold(self):
        cb = DatabaseCircuitBreaker(failure_threshold=3)
        for _ in range(3):
            try:
                cb.call(self._fail_with_operational_error)
            except sqlite3.OperationalError:
                pass
        assert cb.state == DatabaseCircuitState.OPEN

    def test_success_resets_failure_count(self):
        cb = DatabaseCircuitBreaker(failure_threshold=5)
        try:
            cb.call(self._fail_with_operational_error)
        except sqlite3.OperationalError:
            pass
        cb.call(lambda: 1)
        assert cb._failure_count == 0

    @patch("utils.retry_decorator.datetime")
    def test_open_transitions_to_half_open(self, mock_dt):
        cb = DatabaseCircuitBreaker(failure_threshold=1, recovery_timeout=10)
        past = datetime(2025, 1, 1, 0, 0, 0)
        future = past + timedelta(seconds=20)

        mock_dt.now.return_value = past
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        cb._on_failure(sqlite3.OperationalError("test"))

        mock_dt.now.return_value = future
        assert cb.state == DatabaseCircuitState.HALF_OPEN

    def test_half_open_success_closes(self):
        cb = DatabaseCircuitBreaker(failure_threshold=1, recovery_timeout=0)
        try:
            cb.call(self._fail_with_operational_error)
        except sqlite3.OperationalError:
            pass
        cb._state = DatabaseCircuitState.HALF_OPEN
        cb.call(lambda: 1)
        assert cb.state == DatabaseCircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        cb = DatabaseCircuitBreaker(failure_threshold=10)
        cb._state = DatabaseCircuitState.HALF_OPEN
        cb._on_failure(sqlite3.OperationalError("test"))
        assert cb._state == DatabaseCircuitState.OPEN

    def test_reset(self):
        cb = DatabaseCircuitBreaker(failure_threshold=1)
        try:
            cb.call(self._fail_with_operational_error)
        except sqlite3.OperationalError:
            pass
        cb.reset()
        assert cb.state == DatabaseCircuitState.CLOSED
        assert cb._failure_count == 0

    def test_get_status(self):
        cb = DatabaseCircuitBreaker(name="test")
        status = cb.get_status()
        assert status["name"] == "test"
        assert status["state"] == "closed"
        assert status["failure_count"] == 0
        assert status["last_failure"] is None

    def test_get_status_after_failure(self):
        cb = DatabaseCircuitBreaker(failure_threshold=10)
        try:
            cb.call(self._fail_with_operational_error)
        except sqlite3.OperationalError:
            pass
        status = cb.get_status()
        assert status["failure_count"] == 1
        assert status["last_failure"] is not None

    @staticmethod
    def _fail_with_operational_error():
        raise sqlite3.OperationalError("database is locked")


class TestGetDbCircuitBreaker(unittest.TestCase):

    def tearDown(self):
        retry_module._db_circuit_breaker = None

    def test_returns_instance(self):
        cb = get_db_circuit_breaker()
        assert isinstance(cb, DatabaseCircuitBreaker)

    def test_returns_same_instance(self):
        cb1 = get_db_circuit_breaker()
        cb2 = get_db_circuit_breaker()
        assert cb1 is cb2


class TestExponentialBackoff(unittest.TestCase):

    @patch("utils.retry_decorator.time.sleep")
    @patch("utils.retry_decorator.random.random", return_value=0.5)
    def test_retries_on_exception(self, mock_random, mock_sleep):
        counter = {"calls": 0}

        @exponential_backoff(max_retries=2, exceptions=(ValueError,))
        def failing():
            counter["calls"] += 1
            raise ValueError("fail")

        with self.assertRaises(ValueError):
            failing()
        assert counter["calls"] == 3  # 1 initial + 2 retries

    @patch("utils.retry_decorator.time.sleep")
    def test_succeeds_without_retry(self, mock_sleep):
        @exponential_backoff(max_retries=3, exceptions=(ValueError,))
        def succeeding():
            return 42

        assert succeeding() == 42
        mock_sleep.assert_not_called()

    @patch("utils.retry_decorator.time.sleep")
    @patch("utils.retry_decorator.random.random", return_value=0.5)
    def test_succeeds_after_retry(self, mock_random, mock_sleep):
        counter = {"calls": 0}

        @exponential_backoff(max_retries=3, exceptions=(ValueError,))
        def sometimes_fails():
            counter["calls"] += 1
            if counter["calls"] < 2:
                raise ValueError("fail")
            return "ok"

        assert sometimes_fails() == "ok"
        assert counter["calls"] == 2

    @patch("utils.retry_decorator.time.sleep")
    @patch("utils.retry_decorator.random.random", return_value=0.5)
    def test_on_retry_callback(self, mock_random, mock_sleep):
        callback = Mock()

        @exponential_backoff(max_retries=1, exceptions=(ValueError,), on_retry=callback)
        def failing():
            raise ValueError("fail")

        with self.assertRaises(ValueError):
            failing()
        callback.assert_called_once()

    @patch("utils.retry_decorator.time.sleep")
    @patch("utils.retry_decorator.random.random", return_value=0.5)
    def test_delay_capped_at_max(self, mock_random, mock_sleep):
        @exponential_backoff(
            max_retries=5, initial_delay=10.0, max_delay=15.0,
            exponential_base=2.0, exceptions=(ValueError,)
        )
        def failing():
            raise ValueError("fail")

        with self.assertRaises(ValueError):
            failing()
        for call_args in mock_sleep.call_args_list:
            delay = call_args[0][0]
            # With jitter factor (0.5 + 0.5) = 1.0, max delay is 15.0 * 1.0
            assert delay <= 15.0 * 1.5 + 0.01


class TestDbRetry(unittest.TestCase):

    @patch("utils.retry_decorator.time.sleep")
    @patch("utils.retry_decorator.random.random", return_value=0.5)
    def test_retries_on_operational_error(self, mock_random, mock_sleep):
        counter = {"calls": 0}

        @db_retry(max_retries=2)
        def failing():
            counter["calls"] += 1
            raise sqlite3.OperationalError("database is locked")

        with self.assertRaises(sqlite3.OperationalError):
            failing()
        assert counter["calls"] == 3

    @patch("utils.retry_decorator.time.sleep")
    def test_succeeds_immediately(self, mock_sleep):
        @db_retry(max_retries=3)
        def ok():
            return "success"

        assert ok() == "success"
        mock_sleep.assert_not_called()


class TestDbResilient(unittest.TestCase):

    @patch("utils.retry_decorator.time.sleep")
    @patch("utils.retry_decorator.random.random", return_value=0.5)
    def test_has_circuit_breaker_attribute(self, mock_random, mock_sleep):
        @db_resilient(max_retries=2)
        def func():
            return 1

        assert hasattr(func, "circuit_breaker")
        assert isinstance(func.circuit_breaker, DatabaseCircuitBreaker)

    @patch("utils.retry_decorator.time.sleep")
    def test_succeeds_normally(self, mock_sleep):
        @db_resilient(max_retries=2)
        def func():
            return "ok"

        assert func() == "ok"

    @patch("utils.retry_decorator.time.sleep")
    @patch("utils.retry_decorator.random.random", return_value=0.5)
    def test_opens_circuit_on_repeated_failure(self, mock_random, mock_sleep):
        @db_resilient(max_retries=1, failure_threshold=2)
        def failing():
            raise sqlite3.OperationalError("locked")

        for _ in range(3):
            try:
                failing()
            except Exception:
                pass

        assert failing.circuit_breaker.state == DatabaseCircuitState.OPEN

    @patch("utils.retry_decorator.time.sleep")
    @patch("utils.retry_decorator.random.random", return_value=0.5)
    def test_fails_fast_when_open(self, mock_random, mock_sleep):
        @db_resilient(max_retries=1, failure_threshold=1)
        def failing():
            raise sqlite3.OperationalError("locked")

        try:
            failing()
        except Exception:
            pass

        with self.assertRaises(Exception) as ctx:
            failing()
        assert "OPEN" in str(ctx.exception)


if __name__ == "__main__":
    unittest.main()
