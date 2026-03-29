"""Tests for utils.retry_decorator: DatabaseCircuitBreaker and exponential_backoff."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

import sqlite3
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from utils.retry_decorator import (
    DatabaseCircuitBreaker,
    DatabaseCircuitState,
    exponential_backoff,
    db_retry,
    get_db_circuit_breaker,
)
from utils.exceptions import DatabaseError

import utils.retry_decorator as rd


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_global_cb():
    """Reset the global circuit-breaker singleton between tests."""
    old = rd._db_circuit_breaker
    rd._db_circuit_breaker = None
    yield
    rd._db_circuit_breaker = old


# ---------------------------------------------------------------------------
# TestDatabaseCircuitBreaker  (25 tests)
# ---------------------------------------------------------------------------

class TestDatabaseCircuitBreaker:

    # --- construction & defaults ---

    def test_initial_state_is_closed(self):
        cb = DatabaseCircuitBreaker()
        assert cb.state == DatabaseCircuitState.CLOSED

    def test_initial_failure_count_is_zero(self):
        cb = DatabaseCircuitBreaker()
        assert cb._failure_count == 0

    def test_custom_name_stored(self):
        cb = DatabaseCircuitBreaker(name="my_db")
        assert cb.name == "my_db"

    def test_default_name_is_database(self):
        cb = DatabaseCircuitBreaker()
        assert cb.name == "database"

    # --- reset ---

    def test_reset_returns_to_closed_state(self):
        cb = DatabaseCircuitBreaker(failure_threshold=1)
        cb._on_failure(sqlite3.OperationalError("err"))
        assert cb.state == DatabaseCircuitState.OPEN
        cb.reset()
        assert cb.state == DatabaseCircuitState.CLOSED

    def test_reset_clears_failure_count(self):
        cb = DatabaseCircuitBreaker(failure_threshold=3)
        for _ in range(2):
            cb._on_failure(sqlite3.OperationalError("err"))
        cb.reset()
        assert cb._failure_count == 0

    # --- call: CLOSED state ---

    def test_call_invokes_func_when_closed(self):
        func = MagicMock(return_value=42)
        cb = DatabaseCircuitBreaker()
        cb.call(func, 1, key="val")
        func.assert_called_once_with(1, key="val")

    def test_call_returns_func_return_value(self):
        func = MagicMock(return_value="result")
        cb = DatabaseCircuitBreaker()
        assert cb.call(func) == "result"

    # --- call: OPEN state ---

    def test_call_on_open_raises_database_error(self):
        cb = DatabaseCircuitBreaker(failure_threshold=1)
        cb._on_failure(sqlite3.OperationalError("err"))
        assert cb.state == DatabaseCircuitState.OPEN
        with pytest.raises(DatabaseError):
            cb.call(MagicMock())

    def test_call_on_open_does_not_invoke_func(self):
        func = MagicMock()
        cb = DatabaseCircuitBreaker(failure_threshold=1)
        cb._on_failure(sqlite3.OperationalError("err"))
        try:
            cb.call(func)
        except DatabaseError:
            pass
        func.assert_not_called()

    # --- _on_failure ---

    def test_on_failure_increments_failure_count(self):
        cb = DatabaseCircuitBreaker()
        cb._on_failure(sqlite3.OperationalError("err"))
        assert cb._failure_count == 1

    def test_on_failure_five_times_opens_circuit(self):
        cb = DatabaseCircuitBreaker(failure_threshold=5)
        for _ in range(5):
            cb._on_failure(sqlite3.OperationalError("err"))
        assert cb._state == DatabaseCircuitState.OPEN

    def test_on_failure_four_times_stays_closed(self):
        cb = DatabaseCircuitBreaker(failure_threshold=5)
        for _ in range(4):
            cb._on_failure(sqlite3.OperationalError("err"))
        assert cb._state == DatabaseCircuitState.CLOSED

    # --- call propagates sqlite errors ---

    def test_call_with_operational_error_reraises(self):
        def bad():
            raise sqlite3.OperationalError("locked")

        cb = DatabaseCircuitBreaker()
        with pytest.raises(sqlite3.OperationalError):
            cb.call(bad)

    def test_call_with_operational_error_increments_failure_count(self):
        def bad():
            raise sqlite3.OperationalError("locked")

        cb = DatabaseCircuitBreaker()
        try:
            cb.call(bad)
        except sqlite3.OperationalError:
            pass
        assert cb._failure_count == 1

    def test_call_with_database_error_reraises(self):
        def bad():
            raise sqlite3.DatabaseError("db error")

        cb = DatabaseCircuitBreaker()
        with pytest.raises(sqlite3.DatabaseError):
            cb.call(bad)

    def test_call_with_database_error_increments_failure_count(self):
        def bad():
            raise sqlite3.DatabaseError("db error")

        cb = DatabaseCircuitBreaker()
        try:
            cb.call(bad)
        except sqlite3.DatabaseError:
            pass
        assert cb._failure_count == 1

    def test_call_with_non_db_exception_propagates_without_on_failure(self):
        def bad():
            raise ValueError("not a db error")

        cb = DatabaseCircuitBreaker()
        with pytest.raises(ValueError):
            cb.call(bad)
        # ValueError is not caught by the except clause, so _on_failure is NOT called
        assert cb._failure_count == 0

    # --- _on_success ---

    def test_on_success_from_half_open_closes_circuit(self):
        cb = DatabaseCircuitBreaker()
        cb._state = DatabaseCircuitState.HALF_OPEN
        cb._on_success()
        assert cb._state == DatabaseCircuitState.CLOSED

    def test_on_success_resets_failure_count(self):
        cb = DatabaseCircuitBreaker(failure_threshold=10)
        for _ in range(3):
            cb._on_failure(sqlite3.OperationalError("err"))
        cb._on_success()
        assert cb._failure_count == 0

    # --- OPEN -> HALF_OPEN timeout transition ---

    def test_open_transitions_to_half_open_after_timeout(self):
        cb = DatabaseCircuitBreaker(failure_threshold=1, recovery_timeout=30)
        cb._state = DatabaseCircuitState.OPEN
        cb._last_failure_time = datetime.now() - timedelta(seconds=31)
        assert cb.state == DatabaseCircuitState.HALF_OPEN

    def test_open_stays_open_when_timeout_not_elapsed(self):
        cb = DatabaseCircuitBreaker(failure_threshold=1, recovery_timeout=30)
        cb._state = DatabaseCircuitState.OPEN
        cb._last_failure_time = datetime.now() - timedelta(seconds=10)
        assert cb.state == DatabaseCircuitState.OPEN

    # --- HALF_OPEN -> OPEN on failure ---

    def test_half_open_transitions_to_open_on_failure(self):
        cb = DatabaseCircuitBreaker()
        cb._state = DatabaseCircuitState.HALF_OPEN
        cb._on_failure(sqlite3.OperationalError("err"))
        assert cb._state == DatabaseCircuitState.OPEN

    # --- get_status ---

    def test_get_status_returns_dict_with_all_keys(self):
        cb = DatabaseCircuitBreaker()
        status = cb.get_status()
        for key in ("name", "state", "failure_count", "failure_threshold",
                    "last_failure", "recovery_timeout"):
            assert key in status

    def test_get_status_state_matches_current_state_value(self):
        cb = DatabaseCircuitBreaker()
        assert cb.get_status()["state"] == cb._state.value

    def test_get_status_last_failure_none_initially(self):
        cb = DatabaseCircuitBreaker()
        assert cb.get_status()["last_failure"] is None

    def test_get_status_last_failure_is_iso_string_after_failure(self):
        cb = DatabaseCircuitBreaker()
        cb._on_failure(sqlite3.OperationalError("err"))
        last_failure = cb.get_status()["last_failure"]
        assert last_failure is not None
        # Should be parseable as ISO-format datetime
        datetime.fromisoformat(last_failure)


# ---------------------------------------------------------------------------
# TestExponentialBackoff  (10 tests)
# ---------------------------------------------------------------------------

class TestExponentialBackoff:

    def test_successful_call_returns_result(self):
        @exponential_backoff(max_retries=3)
        def always_ok():
            return 99

        assert always_ok() == 99

    def test_retry_once_then_succeed(self):
        call_count = {"n": 0}

        @exponential_backoff(max_retries=3, initial_delay=0.0, jitter=False)
        def fail_once():
            call_count["n"] += 1
            if call_count["n"] < 2:
                raise ValueError("oops")
            return "ok"

        with patch("utils.retry_decorator.time.sleep"):
            result = fail_once()

        assert result == "ok"
        assert call_count["n"] == 2

    def test_exhausts_retries_and_raises(self):
        @exponential_backoff(max_retries=3, initial_delay=0.0, jitter=False)
        def always_fail():
            raise ValueError("always bad")

        with patch("utils.retry_decorator.time.sleep"):
            with pytest.raises(ValueError, match="always bad"):
                always_fail()

    def test_on_retry_callback_is_called_on_each_retry(self):
        callback = MagicMock()

        @exponential_backoff(max_retries=3, initial_delay=0.0, jitter=False, on_retry=callback)
        def always_fail():
            raise ValueError("err")

        with patch("utils.retry_decorator.time.sleep"):
            with pytest.raises(ValueError):
                always_fail()

        assert callback.call_count == 3  # called before each of the 3 retries

    def test_on_retry_callback_receives_exception_and_attempt_number(self):
        received = []

        def cb(exc, attempt):
            received.append((exc, attempt))

        @exponential_backoff(max_retries=2, initial_delay=0.0, jitter=False, on_retry=cb)
        def always_fail():
            raise ValueError("boom")

        with patch("utils.retry_decorator.time.sleep"):
            with pytest.raises(ValueError):
                always_fail()

        assert len(received) == 2
        assert all(isinstance(exc, ValueError) for exc, _ in received)
        assert [attempt for _, attempt in received] == [1, 2]

    def test_max_retries_zero_fails_on_first_exception(self):
        call_count = {"n": 0}

        @exponential_backoff(max_retries=0)
        def always_fail():
            call_count["n"] += 1
            raise ValueError("no retries")

        with pytest.raises(ValueError):
            always_fail()

        assert call_count["n"] == 1

    def test_only_retries_on_specified_exception_type(self):
        call_count = {"n": 0}

        @exponential_backoff(
            max_retries=3,
            initial_delay=0.0,
            jitter=False,
            exceptions=(sqlite3.OperationalError,),
        )
        def fail_with_sqlite():
            call_count["n"] += 1
            raise sqlite3.OperationalError("locked")

        with patch("utils.retry_decorator.time.sleep"):
            with pytest.raises(sqlite3.OperationalError):
                fail_with_sqlite()

        assert call_count["n"] == 4  # 1 initial + 3 retries

    def test_does_not_retry_on_unspecified_exception_type(self):
        call_count = {"n": 0}

        @exponential_backoff(
            max_retries=3,
            initial_delay=0.0,
            jitter=False,
            exceptions=(sqlite3.OperationalError,),
        )
        def fail_with_value_error():
            call_count["n"] += 1
            raise ValueError("not retried")

        with pytest.raises(ValueError):
            fail_with_value_error()

        assert call_count["n"] == 1  # no retries for ValueError

    def test_jitter_false_sleeps_exact_delay(self):
        sleep_calls = []

        @exponential_backoff(
            max_retries=2,
            initial_delay=1.0,
            max_delay=100.0,
            exponential_base=2.0,
            jitter=False,
        )
        def always_fail():
            raise ValueError("err")

        with patch("utils.retry_decorator.time.sleep", side_effect=lambda d: sleep_calls.append(d)):
            with pytest.raises(ValueError):
                always_fail()

        # attempt 0 -> delay = 1.0 * 2**0 = 1.0
        # attempt 1 -> delay = 1.0 * 2**1 = 2.0
        assert sleep_calls == [1.0, 2.0]

    def test_max_retries_three_means_four_total_calls(self):
        call_count = {"n": 0}

        @exponential_backoff(max_retries=3, initial_delay=0.0, jitter=False)
        def always_fail():
            call_count["n"] += 1
            raise ValueError("err")

        with patch("utils.retry_decorator.time.sleep"):
            with pytest.raises(ValueError):
                always_fail()

        assert call_count["n"] == 4  # 1 initial + 3 retries


# ---------------------------------------------------------------------------
# TestGetDbCircuitBreaker  (2 tests)
# ---------------------------------------------------------------------------

class TestGetDbCircuitBreaker:

    def test_returns_database_circuit_breaker_instance(self):
        cb = get_db_circuit_breaker()
        assert isinstance(cb, DatabaseCircuitBreaker)

    def test_returns_singleton(self):
        cb1 = get_db_circuit_breaker()
        cb2 = get_db_circuit_breaker()
        assert cb1 is cb2


# ---------------------------------------------------------------------------
# TestDbRetry  (brief thin-wrapper coverage)
# ---------------------------------------------------------------------------

class TestDbRetry:

    def test_db_retry_retries_on_operational_error(self):
        call_count = {"n": 0}

        @db_retry(max_retries=2, initial_delay=0.0)
        def flaky():
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise sqlite3.OperationalError("locked")
            return "done"

        with patch("utils.retry_decorator.time.sleep"):
            result = flaky()

        assert result == "done"
        assert call_count["n"] == 3

    def test_db_retry_raises_after_exhausting_retries(self):
        @db_retry(max_retries=2, initial_delay=0.0)
        def always_locked():
            raise sqlite3.OperationalError("locked")

        with patch("utils.retry_decorator.time.sleep"):
            with pytest.raises(sqlite3.OperationalError):
                always_locked()

    def test_db_retry_does_not_retry_non_db_exception(self):
        call_count = {"n": 0}

        @db_retry(max_retries=3, initial_delay=0.0)
        def bad():
            call_count["n"] += 1
            raise KeyError("not a db error")

        with pytest.raises(KeyError):
            bad()

        assert call_count["n"] == 1
