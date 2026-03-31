"""
Tests for FallbackCacheProvider — resilient caching with automatic failover.

Module under test: src/rag/cache/fallback_provider.py
"""

import sys
import time
import threading
import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime

sys.path.insert(0, "src")
from rag.cache.fallback_provider import FallbackCacheProvider
from rag.cache.base import CacheStats, CacheBackend


# ---------------------------------------------------------------------------
# Mock helper
# ---------------------------------------------------------------------------

def make_provider(
    healthy=True,
    get_return=None,
    set_return=True,
    get_batch_return=None,
    set_batch_return=0,
    delete_return=True,
    clear_return=0,
    cleanup_return=0,
):
    """Create a fully-configured mock cache provider."""
    m = MagicMock()
    m.health_check.return_value = healthy
    m.get.return_value = get_return
    m.set.return_value = set_return
    m.get_batch.return_value = get_batch_return or {}
    m.set_batch.return_value = set_batch_return
    m.delete.return_value = delete_return
    m.clear.return_value = clear_return
    m.cleanup.return_value = cleanup_return
    stats = CacheStats(backend="mock", total_entries=0, extra_info={})
    m.get_stats.return_value = stats
    return m


# ---------------------------------------------------------------------------
# TestInit
# ---------------------------------------------------------------------------

class TestInit:
    def test_primary_healthy_sets_using_primary_true(self):
        primary = make_provider(healthy=True)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        assert fp._using_primary is True

    def test_primary_unhealthy_sets_using_primary_false(self):
        primary = make_provider(healthy=False)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        assert fp._using_primary is False

    def test_primary_unhealthy_sets_last_primary_failure(self):
        primary = make_provider(healthy=False)
        secondary = make_provider(healthy=True)
        before = time.time()
        fp = FallbackCacheProvider(primary, secondary)
        after = time.time()
        assert fp._last_primary_failure is not None
        assert before <= fp._last_primary_failure <= after

    def test_retry_interval_stores_param(self):
        primary = make_provider(healthy=True)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary, retry_primary_seconds=120)
        assert fp._retry_interval == 120

    def test_default_retry_interval_is_60(self):
        primary = make_provider(healthy=True)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        assert fp._retry_interval == 60

    def test_primary_healthy_last_primary_failure_is_none(self):
        primary = make_provider(healthy=True)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        assert fp._last_primary_failure is None

    def test_health_check_called_exactly_once_on_init(self):
        primary = make_provider(healthy=True)
        secondary = make_provider(healthy=True)
        FallbackCacheProvider(primary, secondary)
        primary.health_check.assert_called_once()


# ---------------------------------------------------------------------------
# TestGetProvider
# ---------------------------------------------------------------------------

class TestGetProvider:
    def test_using_primary_returns_primary(self):
        primary = make_provider(healthy=True)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        assert fp._get_provider() is primary

    def test_not_using_primary_returns_secondary(self):
        primary = make_provider(healthy=False)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        assert fp._get_provider() is secondary

    def test_retry_interval_expired_primary_healthy_restores_primary(self):
        primary = make_provider(healthy=False)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        # Simulate that failure happened longer ago than retry_interval
        fp._last_primary_failure = time.time() - 120
        # Now primary responds healthy
        primary.health_check.return_value = True
        provider = fp._get_provider()
        assert provider is primary
        assert fp._using_primary is True
        assert fp._last_primary_failure is None

    def test_retry_interval_expired_primary_still_unhealthy_stays_secondary(self):
        primary = make_provider(healthy=False)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        before_retry = time.time() - 120
        fp._last_primary_failure = before_retry
        # primary stays unhealthy
        primary.health_check.return_value = False
        provider = fp._get_provider()
        assert provider is secondary
        assert fp._using_primary is False
        # failure time should have been updated
        assert fp._last_primary_failure > before_retry

    def test_before_retry_interval_stays_on_secondary_without_health_check(self):
        primary = make_provider(healthy=False)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        # Reset call count after __init__
        primary.health_check.reset_mock()
        # Very recent failure — retry window not elapsed
        fp._last_primary_failure = time.time() - 1
        provider = fp._get_provider()
        assert provider is secondary
        primary.health_check.assert_not_called()

    def test_retry_health_check_raises_connection_error_updates_failure_time(self):
        primary = make_provider(healthy=False)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        old_failure = time.time() - 200
        fp._last_primary_failure = old_failure
        primary.health_check.side_effect = ConnectionError("down")
        provider = fp._get_provider()
        assert provider is secondary
        assert fp._last_primary_failure > old_failure


# ---------------------------------------------------------------------------
# TestGet
# ---------------------------------------------------------------------------

class TestGet:
    def test_primary_succeeds_returns_result(self):
        vec = [0.1, 0.2, 0.3]
        primary = make_provider(healthy=True, get_return=vec)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.get("hash1", "model-a")
        assert result == vec
        primary.get.assert_called_once_with("hash1", "model-a")

    def test_primary_raises_connection_error_switches_to_secondary(self):
        vec = [0.4, 0.5]
        primary = make_provider(healthy=True)
        primary.get.side_effect = ConnectionError("timeout")
        secondary = make_provider(healthy=True, get_return=vec)
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.get("hash1", "model-a")
        assert result == vec
        assert fp._using_primary is False

    def test_not_using_primary_gets_from_secondary(self):
        vec = [0.9]
        primary = make_provider(healthy=False)
        secondary = make_provider(healthy=True, get_return=vec)
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.get("hash2", "model-b")
        assert result == vec
        primary.get.assert_not_called()

    def test_primary_raises_secondary_also_raises_returns_none(self):
        primary = make_provider(healthy=True)
        primary.get.side_effect = ConnectionError("primary down")
        secondary = make_provider(healthy=True)
        secondary.get.side_effect = OSError("secondary down")
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.get("hash3", "model-c")
        assert result is None

    def test_primary_raises_key_error_switches_to_secondary(self):
        vec = [1.0, 2.0]
        primary = make_provider(healthy=True)
        primary.get.side_effect = KeyError("missing key")
        secondary = make_provider(healthy=True, get_return=vec)
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.get("hash4", "model-d")
        assert result == vec
        assert fp._using_primary is False

    def test_primary_raises_timeout_error_switches_to_secondary(self):
        primary = make_provider(healthy=True)
        primary.get.side_effect = TimeoutError("timed out")
        secondary = make_provider(healthy=True, get_return=[7.7])
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.get("hash5", "model-e")
        assert result == [7.7]

    def test_primary_raises_os_error_switches_to_secondary(self):
        primary = make_provider(healthy=True)
        primary.get.side_effect = OSError("io error")
        secondary = make_provider(healthy=True, get_return=[3.3])
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.get("hashX", "model-f")
        assert result == [3.3]


# ---------------------------------------------------------------------------
# TestSet
# ---------------------------------------------------------------------------

class TestSet:
    def test_primary_succeeds_returns_true(self):
        primary = make_provider(healthy=True, set_return=True)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.set("hash1", [1.0], "model-a")
        assert result is True
        primary.set.assert_called_once_with("hash1", [1.0], "model-a")

    def test_primary_raises_connection_error_switches_and_calls_secondary(self):
        primary = make_provider(healthy=True)
        primary.set.side_effect = ConnectionError("redis down")
        secondary = make_provider(healthy=True, set_return=True)
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.set("hash2", [2.0], "model-b")
        assert result is True
        assert fp._using_primary is False
        secondary.set.assert_called_once_with("hash2", [2.0], "model-b")

    def test_primary_raises_secondary_also_raises_returns_false(self):
        primary = make_provider(healthy=True)
        primary.set.side_effect = ConnectionError("primary down")
        secondary = make_provider(healthy=True)
        secondary.set.side_effect = ConnectionError("secondary down")
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.set("hash3", [3.0], "model-c")
        assert result is False

    def test_not_using_primary_set_goes_to_secondary(self):
        primary = make_provider(healthy=False)
        secondary = make_provider(healthy=True, set_return=True)
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.set("hash4", [4.0], "model-d")
        assert result is True
        # primary.set should not have been called as the active provider
        # (secondary is provider; primary.set may be called for consistency if
        # _using_primary were True, but it is False here)
        secondary.set.assert_called()

    def test_primary_raises_timeout_error_switches_to_secondary(self):
        primary = make_provider(healthy=True)
        primary.set.side_effect = TimeoutError("timeout")
        secondary = make_provider(healthy=True, set_return=True)
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.set("hash5", [5.0], "model-e")
        assert result is True

    def test_primary_raises_os_error_switches_to_secondary(self):
        primary = make_provider(healthy=True)
        primary.set.side_effect = OSError("io error")
        secondary = make_provider(healthy=True, set_return=True)
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.set("hashY", [6.0], "model-f")
        assert result is True


# ---------------------------------------------------------------------------
# TestGetBatch
# ---------------------------------------------------------------------------

class TestGetBatch:
    def test_primary_succeeds_returns_batch(self):
        batch = {"h1": [0.1], "h2": [0.2]}
        primary = make_provider(healthy=True, get_batch_return=batch)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.get_batch(["h1", "h2"], "model-a")
        assert result == batch

    def test_primary_raises_connection_error_falls_back_to_secondary(self):
        batch = {"h1": [1.0]}
        primary = make_provider(healthy=True)
        primary.get_batch.side_effect = ConnectionError("down")
        secondary = make_provider(healthy=True, get_batch_return=batch)
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.get_batch(["h1"], "model-a")
        assert result == batch
        assert fp._using_primary is False

    def test_secondary_also_raises_returns_empty_dict(self):
        primary = make_provider(healthy=True)
        primary.get_batch.side_effect = ConnectionError("primary down")
        secondary = make_provider(healthy=True)
        secondary.get_batch.side_effect = ConnectionError("secondary down")
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.get_batch(["h1", "h2"], "model-a")
        assert result == {}

    def test_not_using_primary_gets_batch_from_secondary(self):
        batch = {"h3": [3.0]}
        primary = make_provider(healthy=False)
        secondary = make_provider(healthy=True, get_batch_return=batch)
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.get_batch(["h3"], "model-b")
        assert result == batch
        primary.get_batch.assert_not_called()

    def test_primary_raises_timeout_error_falls_back_to_secondary(self):
        batch = {"h4": [4.0]}
        primary = make_provider(healthy=True)
        primary.get_batch.side_effect = TimeoutError("timeout")
        secondary = make_provider(healthy=True, get_batch_return=batch)
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.get_batch(["h4"], "model-c")
        assert result == batch


# ---------------------------------------------------------------------------
# TestSetBatch
# ---------------------------------------------------------------------------

class TestSetBatch:
    def test_primary_succeeds_returns_count(self):
        primary = make_provider(healthy=True, set_batch_return=3)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        entries = [("h1", [1.0]), ("h2", [2.0]), ("h3", [3.0])]
        result = fp.set_batch(entries, "model-a")
        assert result == 3
        primary.set_batch.assert_called_once_with(entries, "model-a")

    def test_primary_raises_connection_error_falls_back_to_secondary(self):
        primary = make_provider(healthy=True)
        primary.set_batch.side_effect = ConnectionError("down")
        secondary = make_provider(healthy=True, set_batch_return=2)
        fp = FallbackCacheProvider(primary, secondary)
        entries = [("h1", [1.0]), ("h2", [2.0])]
        result = fp.set_batch(entries, "model-a")
        assert result == 2
        assert fp._using_primary is False

    def test_secondary_also_raises_returns_zero(self):
        primary = make_provider(healthy=True)
        primary.set_batch.side_effect = ConnectionError("primary down")
        secondary = make_provider(healthy=True)
        secondary.set_batch.side_effect = ConnectionError("secondary down")
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.set_batch([("h1", [1.0])], "model-a")
        assert result == 0

    def test_not_using_primary_set_batch_goes_to_secondary(self):
        primary = make_provider(healthy=False)
        secondary = make_provider(healthy=True, set_batch_return=5)
        fp = FallbackCacheProvider(primary, secondary)
        entries = [("h1", [1.0])]
        result = fp.set_batch(entries, "model-b")
        assert result == 5

    def test_primary_raises_os_error_falls_back_to_secondary(self):
        primary = make_provider(healthy=True)
        primary.set_batch.side_effect = OSError("io error")
        secondary = make_provider(healthy=True, set_batch_return=4)
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.set_batch([("h1", [1.0])], "model-c")
        assert result == 4


# ---------------------------------------------------------------------------
# TestDelete
# ---------------------------------------------------------------------------

class TestDelete:
    def test_primary_succeeds_also_deletes_from_secondary(self):
        primary = make_provider(healthy=True, delete_return=True)
        secondary = make_provider(healthy=True, delete_return=True)
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.delete("hash1", "model-a")
        assert result is True
        primary.delete.assert_called_once_with("hash1", "model-a")
        secondary.delete.assert_called_once_with("hash1", "model-a")

    def test_primary_raises_connection_error_switches_returns_secondary_result(self):
        primary = make_provider(healthy=True)
        primary.delete.side_effect = ConnectionError("redis down")
        secondary = make_provider(healthy=True, delete_return=True)
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.delete("hash2", "model-b")
        assert result is True
        assert fp._using_primary is False
        secondary.delete.assert_called_with("hash2", "model-b")

    def test_using_secondary_also_calls_primary_delete_for_consistency(self):
        primary = make_provider(healthy=False, delete_return=True)
        secondary = make_provider(healthy=True, delete_return=True)
        fp = FallbackCacheProvider(primary, secondary)
        assert fp._using_primary is False
        fp.delete("hash3", "model-c")
        secondary.delete.assert_called_with("hash3", "model-c")
        primary.delete.assert_called_with("hash3", "model-c")

    def test_primary_raises_during_consistency_delete_does_not_propagate(self):
        primary = make_provider(healthy=True, delete_return=True)
        secondary = make_provider(healthy=True, delete_return=True)
        secondary.delete.side_effect = ConnectionError("secondary delete fail")
        fp = FallbackCacheProvider(primary, secondary)
        # Should not raise even though secondary.delete raises
        result = fp.delete("hash4", "model-d")
        assert result is True

    def test_primary_and_secondary_both_raise_returns_false(self):
        primary = make_provider(healthy=True)
        primary.delete.side_effect = ConnectionError("primary down")
        secondary = make_provider(healthy=True)
        secondary.delete.side_effect = ConnectionError("secondary down")
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.delete("hash5", "model-e")
        assert result is False

    def test_primary_returns_false_returns_false(self):
        primary = make_provider(healthy=True, delete_return=False)
        secondary = make_provider(healthy=True, delete_return=True)
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.delete("hash6", "model-f")
        assert result is False


# ---------------------------------------------------------------------------
# TestClear
# ---------------------------------------------------------------------------

class TestClear:
    def test_both_succeed_returns_sum(self):
        primary = make_provider(healthy=True, clear_return=5)
        secondary = make_provider(healthy=True, clear_return=3)
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.clear()
        assert result == 8

    def test_primary_raises_connection_error_still_calls_secondary(self):
        primary = make_provider(healthy=True)
        primary.clear.side_effect = ConnectionError("primary down")
        secondary = make_provider(healthy=True, clear_return=7)
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.clear()
        assert result == 7
        secondary.clear.assert_called_once()

    def test_secondary_raises_connection_error_returns_primary_total(self):
        primary = make_provider(healthy=True, clear_return=4)
        secondary = make_provider(healthy=True)
        secondary.clear.side_effect = ConnectionError("secondary down")
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.clear()
        assert result == 4

    def test_both_raise_returns_zero(self):
        primary = make_provider(healthy=True)
        primary.clear.side_effect = OSError("primary down")
        secondary = make_provider(healthy=True)
        secondary.clear.side_effect = OSError("secondary down")
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.clear()
        assert result == 0

    def test_clear_always_calls_both_providers(self):
        primary = make_provider(healthy=True, clear_return=1)
        secondary = make_provider(healthy=True, clear_return=2)
        fp = FallbackCacheProvider(primary, secondary)
        fp.clear()
        primary.clear.assert_called_once()
        secondary.clear.assert_called_once()


# ---------------------------------------------------------------------------
# TestCleanup
# ---------------------------------------------------------------------------

class TestCleanup:
    def test_both_succeed_returns_sum(self):
        primary = make_provider(healthy=True, cleanup_return=10)
        secondary = make_provider(healthy=True, cleanup_return=5)
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.cleanup(max_age_days=30, max_entries=1000)
        assert result == 15

    def test_primary_raises_still_calls_secondary(self):
        primary = make_provider(healthy=True)
        primary.cleanup.side_effect = ConnectionError("primary down")
        secondary = make_provider(healthy=True, cleanup_return=8)
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.cleanup()
        assert result == 8
        secondary.cleanup.assert_called_once()

    def test_secondary_raises_returns_primary_total(self):
        primary = make_provider(healthy=True, cleanup_return=6)
        secondary = make_provider(healthy=True)
        secondary.cleanup.side_effect = OSError("secondary down")
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.cleanup()
        assert result == 6

    def test_both_raise_returns_zero(self):
        primary = make_provider(healthy=True)
        primary.cleanup.side_effect = ConnectionError("p")
        secondary = make_provider(healthy=True)
        secondary.cleanup.side_effect = ConnectionError("s")
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.cleanup()
        assert result == 0

    def test_cleanup_passes_args_to_both_providers(self):
        primary = make_provider(healthy=True, cleanup_return=0)
        secondary = make_provider(healthy=True, cleanup_return=0)
        fp = FallbackCacheProvider(primary, secondary)
        fp.cleanup(max_age_days=14, max_entries=500)
        primary.cleanup.assert_called_once_with(14, 500)
        secondary.cleanup.assert_called_once_with(14, 500)


# ---------------------------------------------------------------------------
# TestHealthCheck
# ---------------------------------------------------------------------------

class TestHealthCheck:
    def test_both_healthy_returns_true(self):
        primary = make_provider(healthy=True)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        assert fp.health_check() is True

    def test_only_primary_healthy_returns_true(self):
        primary = make_provider(healthy=True)
        secondary = make_provider(healthy=False)
        fp = FallbackCacheProvider(primary, secondary)
        assert fp.health_check() is True

    def test_only_secondary_healthy_returns_true(self):
        primary = make_provider(healthy=False)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        # Reset call count after __init__ which called health_check
        primary.health_check.reset_mock()
        primary.health_check.return_value = False
        assert fp.health_check() is True

    def test_both_unhealthy_returns_false(self):
        primary = make_provider(healthy=False)
        secondary = make_provider(healthy=False)
        fp = FallbackCacheProvider(primary, secondary)
        primary.health_check.return_value = False
        secondary.health_check.return_value = False
        assert fp.health_check() is False

    def test_primary_health_check_raises_treated_as_unhealthy(self):
        primary = make_provider(healthy=True)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        primary.health_check.side_effect = ConnectionError("down")
        # Secondary is healthy, so overall result is True
        assert fp.health_check() is True

    def test_secondary_health_check_raises_treated_as_unhealthy(self):
        primary = make_provider(healthy=True)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        secondary.health_check.side_effect = OSError("down")
        assert fp.health_check() is True

    def test_both_raise_returns_false(self):
        primary = make_provider(healthy=True)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        primary.health_check.side_effect = ConnectionError("p")
        secondary.health_check.side_effect = ConnectionError("s")
        assert fp.health_check() is False


# ---------------------------------------------------------------------------
# TestGetStats
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_using_primary_stats_have_fallback_mode_false(self):
        primary = make_provider(healthy=True)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        stats = fp.get_stats()
        assert stats.extra_info.get("fallback_mode") is False

    def test_using_primary_backend_contains_primary(self):
        primary = make_provider(healthy=True)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        stats = fp.get_stats()
        assert "primary" in stats.backend

    def test_using_primary_backend_starts_with_fallback(self):
        primary = make_provider(healthy=True)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        stats = fp.get_stats()
        assert stats.backend.startswith("fallback")

    def test_not_using_primary_stats_have_fallback_mode_true(self):
        primary = make_provider(healthy=False)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        stats = fp.get_stats()
        assert stats.extra_info.get("fallback_mode") is True

    def test_not_using_primary_backend_contains_secondary(self):
        primary = make_provider(healthy=False)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        stats = fp.get_stats()
        assert "secondary" in stats.backend

    def test_not_using_primary_with_failure_time_has_next_retry_in_extra_info(self):
        primary = make_provider(healthy=False)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        assert fp._last_primary_failure is not None
        stats = fp.get_stats()
        assert "next_primary_retry" in stats.extra_info

    def test_using_primary_no_next_primary_retry_key(self):
        primary = make_provider(healthy=True)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        stats = fp.get_stats()
        assert "next_primary_retry" not in stats.extra_info

    def test_next_primary_retry_is_iso_format_string(self):
        primary = make_provider(healthy=False)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        stats = fp.get_stats()
        retry_str = stats.extra_info["next_primary_retry"]
        # Should parse as ISO datetime without raising
        parsed = datetime.fromisoformat(retry_str)
        assert parsed > datetime.now()


# ---------------------------------------------------------------------------
# TestClose
# ---------------------------------------------------------------------------

class TestClose:
    def test_both_close_called(self):
        primary = make_provider(healthy=True)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        fp.close()
        primary.close.assert_called_once()
        secondary.close.assert_called_once()

    def test_primary_close_raises_connection_error_secondary_still_closed(self):
        primary = make_provider(healthy=True)
        primary.close.side_effect = ConnectionError("close failed")
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        fp.close()  # Should not raise
        secondary.close.assert_called_once()

    def test_secondary_close_raises_os_error_no_exception_propagated(self):
        primary = make_provider(healthy=True)
        secondary = make_provider(healthy=True)
        secondary.close.side_effect = OSError("close failed")
        fp = FallbackCacheProvider(primary, secondary)
        # Should not raise
        fp.close()

    def test_primary_close_raises_attribute_error_no_exception_propagated(self):
        primary = make_provider(healthy=True)
        primary.close.side_effect = AttributeError("no close method")
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        fp.close()  # Should not raise
        secondary.close.assert_called_once()

    def test_both_close_raise_no_exception_propagated(self):
        primary = make_provider(healthy=True)
        primary.close.side_effect = ConnectionError("p")
        secondary = make_provider(healthy=True)
        secondary.close.side_effect = OSError("s")
        fp = FallbackCacheProvider(primary, secondary)
        fp.close()  # Should not raise


# ---------------------------------------------------------------------------
# TestSwitchToSecondary (internal)
# ---------------------------------------------------------------------------

class TestSwitchToSecondary:
    def test_switch_sets_using_primary_false(self):
        primary = make_provider(healthy=True)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        fp._switch_to_secondary(ConnectionError("test"))
        assert fp._using_primary is False

    def test_switch_sets_last_primary_failure(self):
        primary = make_provider(healthy=True)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        before = time.time()
        fp._switch_to_secondary(ConnectionError("test"))
        after = time.time()
        assert fp._last_primary_failure is not None
        assert before <= fp._last_primary_failure <= after

    def test_switch_when_already_on_secondary_does_not_reset_failure_time(self):
        primary = make_provider(healthy=False)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        original_failure = fp._last_primary_failure
        time.sleep(0.01)
        fp._switch_to_secondary(ConnectionError("test"))
        # Already on secondary — _switch_to_secondary checks _using_primary
        # which is already False, so it should not update
        assert fp._last_primary_failure == original_failure


# ---------------------------------------------------------------------------
# TestConcurrency
# ---------------------------------------------------------------------------

class TestConcurrency:
    def test_concurrent_get_calls_thread_safe(self):
        vec = [1.0, 2.0, 3.0]
        primary = make_provider(healthy=True, get_return=vec)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        results = []
        errors = []

        def worker():
            try:
                results.append(fp.get("hash", "model"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 20
        assert all(r == vec for r in results)

    def test_concurrent_switch_to_secondary_idempotent(self):
        primary = make_provider(healthy=True)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        errors = []

        def switch():
            try:
                fp._switch_to_secondary(ConnectionError("test"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=switch) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert fp._using_primary is False


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_get_returns_none_when_cache_miss_on_primary(self):
        primary = make_provider(healthy=True, get_return=None)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.get("missing", "model")
        assert result is None

    def test_set_batch_zero_entries(self):
        primary = make_provider(healthy=True, set_batch_return=0)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.set_batch([], "model")
        assert result == 0

    def test_get_batch_empty_hashes_list(self):
        primary = make_provider(healthy=True, get_batch_return={})
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        result = fp.get_batch([], "model")
        assert result == {}

    def test_stats_extra_info_fallback_backend_when_using_primary(self):
        primary = make_provider(healthy=True)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        stats = fp.get_stats()
        assert stats.extra_info.get("fallback_backend") == "sqlite"

    def test_stats_extra_info_primary_backend_when_using_secondary(self):
        primary = make_provider(healthy=False)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary)
        stats = fp.get_stats()
        assert stats.extra_info.get("primary_backend") == "redis"

    def test_retry_interval_zero_always_retries_primary(self):
        primary = make_provider(healthy=False)
        secondary = make_provider(healthy=True)
        fp = FallbackCacheProvider(primary, secondary, retry_primary_seconds=0)
        # Immediately after init, elapsed >= 0 so retry should happen
        primary.health_check.return_value = True
        provider = fp._get_provider()
        assert provider is primary
