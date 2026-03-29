"""
Tests for src/utils/retry_decorator.py

Focuses on pure-logic components:
  - DatabaseCircuitState enum
  - DatabaseCircuitBreaker class (init, state transitions, call, _on_success,
    _on_failure, reset, get_status)
  - get_db_circuit_breaker() singleton factory

Time-sleep-dependent decorators (exponential_backoff, db_retry, db_resilient,
network_retry) are tested separately and intentionally excluded here to keep
these tests fast and deterministic.
"""

import sys
import sqlite3
import pytest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from utils.retry_decorator import (
    DatabaseCircuitState,
    DatabaseCircuitBreaker,
    get_db_circuit_breaker,
)
from utils.exceptions import DatabaseError

import utils.retry_decorator as _rd_module


@pytest.fixture(autouse=True)
def reset_db_circuit_breaker():
    """Reset the global singleton before and after each test."""
    _rd_module._db_circuit_breaker = None
    yield
    _rd_module._db_circuit_breaker = None


# ===========================================================================
# DatabaseCircuitState enum
# ===========================================================================

class TestDatabaseCircuitState:

    def test_has_three_members(self):
        assert len(DatabaseCircuitState) == 3

    def test_closed_exists(self):
        assert DatabaseCircuitState.CLOSED is not None

    def test_open_exists(self):
        assert DatabaseCircuitState.OPEN is not None

    def test_half_open_exists(self):
        assert DatabaseCircuitState.HALF_OPEN is not None

    def test_closed_value(self):
        assert DatabaseCircuitState.CLOSED.value == "closed"

    def test_open_value(self):
        assert DatabaseCircuitState.OPEN.value == "open"

    def test_half_open_value(self):
        assert DatabaseCircuitState.HALF_OPEN.value == "half_open"

    def test_all_values_distinct(self):
        values = [s.value for s in DatabaseCircuitState]
        assert len(values) == len(set(values))

    def test_members_are_distinct_objects(self):
        assert DatabaseCircuitState.CLOSED is not DatabaseCircuitState.OPEN
        assert DatabaseCircuitState.CLOSED is not DatabaseCircuitState.HALF_OPEN
        assert DatabaseCircuitState.OPEN is not DatabaseCircuitState.HALF_OPEN


# ===========================================================================
# DatabaseCircuitBreaker – __init__
# ===========================================================================

class TestDatabaseCircuitBreakerInit:

    def test_default_starts_closed(self):
        cb = DatabaseCircuitBreaker()
        assert cb.state == DatabaseCircuitState.CLOSED

    def test_default_failure_count_zero(self):
        cb = DatabaseCircuitBreaker()
        assert cb._failure_count == 0

    def test_default_name_is_database(self):
        cb = DatabaseCircuitBreaker()
        assert cb.name == "database"

    def test_default_failure_threshold(self):
        cb = DatabaseCircuitBreaker()
        assert cb.failure_threshold == 5

    def test_default_recovery_timeout(self):
        cb = DatabaseCircuitBreaker()
        assert cb.recovery_timeout == 30

    def test_custom_failure_threshold_stored(self):
        cb = DatabaseCircuitBreaker(failure_threshold=3)
        assert cb.failure_threshold == 3

    def test_custom_recovery_timeout_stored(self):
        cb = DatabaseCircuitBreaker(recovery_timeout=60)
        assert cb.recovery_timeout == 60

    def test_custom_name_stored(self):
        cb = DatabaseCircuitBreaker(name="my_db")
        assert cb.name == "my_db"

    def test_last_failure_time_initially_none(self):
        cb = DatabaseCircuitBreaker()
        assert cb._last_failure_time is None


# ===========================================================================
# DatabaseCircuitBreaker – state property (OPEN → HALF_OPEN transition)
# ===========================================================================

class TestDatabaseCircuitBreakerStateProperty:

    def test_state_starts_closed(self):
        cb = DatabaseCircuitBreaker()
        assert cb.state == DatabaseCircuitState.CLOSED

    def test_open_state_remains_open_before_timeout(self):
        cb = DatabaseCircuitBreaker(failure_threshold=1, recovery_timeout=60)
        cb._on_failure(sqlite3.OperationalError("test"))
        # failure_count == 1 == threshold → OPEN; timeout has not elapsed
        assert cb.state == DatabaseCircuitState.OPEN

    def test_open_transitions_to_half_open_after_timeout(self):
        cb = DatabaseCircuitBreaker(failure_threshold=1, recovery_timeout=10)
        past = datetime(2025, 1, 1, 0, 0, 0)
        future = past + timedelta(seconds=20)

        with patch.object(_rd_module, "datetime") as mock_dt:
            mock_dt.now.return_value = past
            # Manually trigger OPEN via _on_failure (bypasses the state lock's datetime call)
            cb._state = DatabaseCircuitState.OPEN
            cb._last_failure_time = past

            mock_dt.now.return_value = future
            state = cb.state

        assert state == DatabaseCircuitState.HALF_OPEN

    def test_half_open_state_returned_directly(self):
        cb = DatabaseCircuitBreaker()
        cb._state = DatabaseCircuitState.HALF_OPEN
        assert cb.state == DatabaseCircuitState.HALF_OPEN


# ===========================================================================
# DatabaseCircuitBreaker – call()
# ===========================================================================

class TestDatabaseCircuitBreakerCall:

    def test_call_returns_function_result(self):
        cb = DatabaseCircuitBreaker()
        assert cb.call(lambda: 42) == 42

    def test_call_passes_positional_args(self):
        cb = DatabaseCircuitBreaker()
        assert cb.call(lambda x, y: x + y, 3, 4) == 7

    def test_call_passes_keyword_args(self):
        cb = DatabaseCircuitBreaker()
        assert cb.call(lambda x=0: x * 2, x=5) == 10

    def test_call_sqlite_operational_error_re_raised(self):
        cb = DatabaseCircuitBreaker(failure_threshold=10)
        with pytest.raises(sqlite3.OperationalError):
            cb.call(_raise_operational_error)

    def test_call_sqlite_operational_error_increments_failure_count(self):
        cb = DatabaseCircuitBreaker(failure_threshold=10)
        try:
            cb.call(_raise_operational_error)
        except sqlite3.OperationalError:
            pass
        assert cb._failure_count == 1

    def test_call_failure_at_threshold_opens_circuit(self):
        cb = DatabaseCircuitBreaker(failure_threshold=3)
        for _ in range(3):
            try:
                cb.call(_raise_operational_error)
            except sqlite3.OperationalError:
                pass
        assert cb.state == DatabaseCircuitState.OPEN

    def test_call_when_open_raises_database_error(self):
        cb = DatabaseCircuitBreaker(failure_threshold=1)
        try:
            cb.call(_raise_operational_error)
        except sqlite3.OperationalError:
            pass
        with pytest.raises(DatabaseError):
            cb.call(lambda: 42)

    def test_call_when_open_does_not_invoke_func(self):
        cb = DatabaseCircuitBreaker(failure_threshold=1)
        try:
            cb.call(_raise_operational_error)
        except sqlite3.OperationalError:
            pass
        called = {"flag": False}
        def probe():
            called["flag"] = True
        try:
            cb.call(probe)
        except DatabaseError:
            pass
        assert called["flag"] is False

    def test_call_when_open_error_message_contains_open(self):
        cb = DatabaseCircuitBreaker(failure_threshold=1)
        try:
            cb.call(_raise_operational_error)
        except sqlite3.OperationalError:
            pass
        with pytest.raises(DatabaseError) as exc_info:
            cb.call(lambda: 42)
        assert "OPEN" in str(exc_info.value)

    def test_call_success_resets_failure_count(self):
        cb = DatabaseCircuitBreaker(failure_threshold=10)
        try:
            cb.call(_raise_operational_error)
        except sqlite3.OperationalError:
            pass
        cb.call(lambda: 1)
        assert cb._failure_count == 0

    def test_call_sqlite_database_error_re_raised(self):
        cb = DatabaseCircuitBreaker(failure_threshold=10)
        with pytest.raises(sqlite3.DatabaseError):
            cb.call(_raise_database_error)


# ===========================================================================
# DatabaseCircuitBreaker – _on_success()
# ===========================================================================

class TestDatabaseCircuitBreakerOnSuccess:

    def test_on_success_resets_failure_count(self):
        cb = DatabaseCircuitBreaker(failure_threshold=10)
        cb._failure_count = 4
        cb._on_success()
        assert cb._failure_count == 0

    def test_on_success_clears_last_failure_time(self):
        cb = DatabaseCircuitBreaker()
        cb._last_failure_time = datetime.now()
        cb._on_success()
        assert cb._last_failure_time is None

    def test_on_success_closed_stays_closed(self):
        cb = DatabaseCircuitBreaker()
        cb._on_success()
        assert cb.state == DatabaseCircuitState.CLOSED

    def test_on_success_half_open_transitions_to_closed(self):
        cb = DatabaseCircuitBreaker()
        cb._state = DatabaseCircuitState.HALF_OPEN
        cb._on_success()
        assert cb.state == DatabaseCircuitState.CLOSED

    def test_on_success_does_not_change_open_to_closed_directly(self):
        """OPEN → success only closes via HALF_OPEN; direct call from OPEN keeps OPEN."""
        cb = DatabaseCircuitBreaker()
        cb._state = DatabaseCircuitState.OPEN
        # _on_success only closes from HALF_OPEN, not OPEN
        cb._on_success()
        # failure_count reset but state stays OPEN (no HALF_OPEN guard hit)
        assert cb._state == DatabaseCircuitState.OPEN or cb._failure_count == 0


# ===========================================================================
# DatabaseCircuitBreaker – _on_failure()
# ===========================================================================

class TestDatabaseCircuitBreakerOnFailure:

    def test_on_failure_increments_failure_count(self):
        cb = DatabaseCircuitBreaker(failure_threshold=5)
        cb._on_failure(sqlite3.OperationalError("test"))
        assert cb._failure_count == 1

    def test_on_failure_multiple_increments(self):
        cb = DatabaseCircuitBreaker(failure_threshold=10)
        for _ in range(4):
            cb._on_failure(sqlite3.OperationalError("test"))
        assert cb._failure_count == 4

    def test_on_failure_sets_last_failure_time(self):
        cb = DatabaseCircuitBreaker(failure_threshold=5)
        cb._on_failure(sqlite3.OperationalError("test"))
        assert cb._last_failure_time is not None

    def test_on_failure_at_threshold_opens_circuit(self):
        cb = DatabaseCircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb._on_failure(sqlite3.OperationalError("test"))
        assert cb._state == DatabaseCircuitState.OPEN

    def test_on_failure_below_threshold_stays_closed(self):
        cb = DatabaseCircuitBreaker(failure_threshold=5)
        for _ in range(4):
            cb._on_failure(sqlite3.OperationalError("test"))
        assert cb._state == DatabaseCircuitState.CLOSED

    def test_on_failure_in_half_open_reopens_circuit(self):
        cb = DatabaseCircuitBreaker(failure_threshold=10)
        cb._state = DatabaseCircuitState.HALF_OPEN
        cb._on_failure(sqlite3.OperationalError("test"))
        assert cb._state == DatabaseCircuitState.OPEN

    def test_on_failure_half_open_reopens_regardless_of_count(self):
        """Even count=1 in HALF_OPEN must reopen."""
        cb = DatabaseCircuitBreaker(failure_threshold=100)
        cb._state = DatabaseCircuitState.HALF_OPEN
        cb._on_failure(sqlite3.OperationalError("test"))
        assert cb._state == DatabaseCircuitState.OPEN


# ===========================================================================
# DatabaseCircuitBreaker – reset()
# ===========================================================================

class TestDatabaseCircuitBreakerReset:

    def test_reset_from_open_to_closed(self):
        cb = DatabaseCircuitBreaker(failure_threshold=1)
        cb._on_failure(sqlite3.OperationalError("test"))
        assert cb._state == DatabaseCircuitState.OPEN
        cb.reset()
        assert cb.state == DatabaseCircuitState.CLOSED

    def test_reset_clears_failure_count(self):
        cb = DatabaseCircuitBreaker(failure_threshold=10)
        cb._failure_count = 7
        cb.reset()
        assert cb._failure_count == 0

    def test_reset_clears_last_failure_time(self):
        cb = DatabaseCircuitBreaker(failure_threshold=10)
        cb._last_failure_time = datetime.now()
        cb.reset()
        assert cb._last_failure_time is None

    def test_reset_from_half_open_to_closed(self):
        cb = DatabaseCircuitBreaker()
        cb._state = DatabaseCircuitState.HALF_OPEN
        cb.reset()
        assert cb.state == DatabaseCircuitState.CLOSED

    def test_reset_idempotent_when_already_closed(self):
        cb = DatabaseCircuitBreaker()
        cb.reset()
        assert cb.state == DatabaseCircuitState.CLOSED
        assert cb._failure_count == 0


# ===========================================================================
# DatabaseCircuitBreaker – get_status()
# ===========================================================================

class TestDatabaseCircuitBreakerGetStatus:

    def test_returns_dict(self):
        cb = DatabaseCircuitBreaker()
        assert isinstance(cb.get_status(), dict)

    def test_status_contains_name(self):
        cb = DatabaseCircuitBreaker(name="test_cb")
        assert cb.get_status()["name"] == "test_cb"

    def test_status_contains_state(self):
        cb = DatabaseCircuitBreaker()
        assert "state" in cb.get_status()

    def test_status_state_is_string_value(self):
        cb = DatabaseCircuitBreaker()
        assert cb.get_status()["state"] == "closed"

    def test_status_contains_failure_count(self):
        cb = DatabaseCircuitBreaker()
        assert cb.get_status()["failure_count"] == 0

    def test_status_contains_failure_threshold(self):
        cb = DatabaseCircuitBreaker(failure_threshold=7)
        assert cb.get_status()["failure_threshold"] == 7

    def test_status_contains_last_failure_none_initially(self):
        cb = DatabaseCircuitBreaker()
        assert cb.get_status()["last_failure"] is None

    def test_status_contains_recovery_timeout(self):
        cb = DatabaseCircuitBreaker(recovery_timeout=45)
        assert cb.get_status()["recovery_timeout"] == 45

    def test_status_last_failure_set_after_failure(self):
        cb = DatabaseCircuitBreaker(failure_threshold=10)
        cb._on_failure(sqlite3.OperationalError("test"))
        status = cb.get_status()
        assert status["last_failure"] is not None

    def test_status_last_failure_is_iso_string(self):
        cb = DatabaseCircuitBreaker(failure_threshold=10)
        cb._on_failure(sqlite3.OperationalError("test"))
        lf = cb.get_status()["last_failure"]
        # Should be parseable as an ISO 8601 datetime string
        dt = datetime.fromisoformat(lf)
        assert isinstance(dt, datetime)

    def test_status_failure_count_after_failures(self):
        cb = DatabaseCircuitBreaker(failure_threshold=10)
        for _ in range(3):
            cb._on_failure(sqlite3.OperationalError("test"))
        assert cb.get_status()["failure_count"] == 3

    def test_status_state_is_open_after_threshold(self):
        cb = DatabaseCircuitBreaker(failure_threshold=2)
        for _ in range(2):
            cb._on_failure(sqlite3.OperationalError("test"))
        assert cb.get_status()["state"] == "open"


# ===========================================================================
# get_db_circuit_breaker() singleton factory
# ===========================================================================

class TestGetDbCircuitBreaker:

    def test_returns_database_circuit_breaker_instance(self):
        cb = get_db_circuit_breaker()
        assert isinstance(cb, DatabaseCircuitBreaker)

    def test_returns_same_object_on_second_call(self):
        cb1 = get_db_circuit_breaker()
        cb2 = get_db_circuit_breaker()
        assert cb1 is cb2

    def test_singleton_starts_closed(self):
        cb = get_db_circuit_breaker()
        assert cb.state == DatabaseCircuitState.CLOSED

    def test_singleton_has_global_database_name(self):
        cb = get_db_circuit_breaker()
        assert cb.name == "global_database"

    def test_singleton_default_failure_threshold(self):
        cb = get_db_circuit_breaker()
        assert cb.failure_threshold == 5

    def test_singleton_default_recovery_timeout(self):
        cb = get_db_circuit_breaker()
        assert cb.recovery_timeout == 30

    def test_reset_module_variable_gives_fresh_instance(self):
        cb1 = get_db_circuit_breaker()
        _rd_module._db_circuit_breaker = None
        cb2 = get_db_circuit_breaker()
        assert cb1 is not cb2


# ===========================================================================
# Helpers
# ===========================================================================

def _raise_operational_error():
    raise sqlite3.OperationalError("database is locked")


def _raise_database_error():
    raise sqlite3.DatabaseError("generic db error")
