"""
Tests for LRUCache in src/ai/model_provider.py

Covers get/set/remove/clear/cleanup_expired/size/stats, LRU eviction
ordering, TTL expiry, edge cases, and thread-safety.
Pure in-memory logic — no network, no Tkinter, no file I/O.

~90+ tests organised across 9 test classes.
"""

import sys
import threading
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Heavy-dependency stubs — must happen BEFORE adding src/ to sys.path so that
# the real packages are never attempted during collection.
# ---------------------------------------------------------------------------
for _mod in [
    "openai",
    "anthropic",
    "requests",
    "google",
    "google.genai",
    "google.generativeai",
]:
    sys.modules.setdefault(_mod, MagicMock())

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.model_provider import LRUCache  # noqa: E402  (must follow path setup)

# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def cache() -> LRUCache:
    """Default cache for most tests: max_size=5, ttl=60 s."""
    return LRUCache(max_size=5, ttl_seconds=60)


# ===========================================================================
# 1. Initialisation
# ===========================================================================

class TestLRUCacheInit:
    """Verify constructor arguments are stored correctly."""

    def test_default_max_size_is_10(self):
        c = LRUCache()
        assert c.stats()["max_size"] == 10

    def test_default_ttl_is_3600(self):
        c = LRUCache()
        assert c.stats()["ttl_seconds"] == 3600

    def test_custom_max_size_stored(self):
        c = LRUCache(max_size=42)
        assert c.stats()["max_size"] == 42

    def test_custom_ttl_stored(self):
        c = LRUCache(ttl_seconds=7200)
        assert c.stats()["ttl_seconds"] == 7200

    def test_initial_size_is_zero(self):
        assert LRUCache().size == 0

    def test_stats_on_empty_cache(self):
        s = LRUCache().stats()
        assert s["size"] == 0
        assert s["keys"] == []


# ===========================================================================
# 2. get()
# ===========================================================================

class TestGet:
    """Covers get behaviour: misses, hits, LRU promotion, TTL expiry."""

    def test_get_on_empty_cache_returns_none(self, cache):
        assert cache.get("missing") is None

    def test_get_after_set_returns_value(self, cache):
        cache.set("k", "hello")
        assert cache.get("k") == "hello"

    def test_get_missing_key_returns_none(self, cache):
        cache.set("x", 1)
        assert cache.get("y") is None

    def test_get_moves_key_to_most_recent(self):
        """After get, the accessed key is at the end of the ordered dict."""
        c = LRUCache(max_size=3, ttl_seconds=3600)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        c.get("a")           # promote "a"
        c.set("d", 4)        # eviction should remove "b" (now LRU), not "a"
        assert c.get("a") == 1
        assert c.get("b") is None

    def test_get_expired_entry_returns_none(self):
        with patch("ai.model_provider.time") as mock_time:
            mock_time.time.return_value = 1000.0
            c = LRUCache(max_size=5, ttl_seconds=60)
            c.set("k", "v")
            mock_time.time.return_value = 1061.0   # 61 s later — expired
            assert c.get("k") is None

    def test_get_expired_entry_removes_it_from_cache(self):
        with patch("ai.model_provider.time") as mock_time:
            mock_time.time.return_value = 1000.0
            c = LRUCache(max_size=5, ttl_seconds=60)
            c.set("k", "v")
            mock_time.time.return_value = 1061.0
            c.get("k")
            assert c.size == 0

    def test_get_just_before_expiry_still_returns_value(self):
        with patch("ai.model_provider.time") as mock_time:
            mock_time.time.return_value = 1000.0
            c = LRUCache(max_size=5, ttl_seconds=60)
            c.set("k", "v")
            mock_time.time.return_value = 1059.9   # < 60 s — not expired
            assert c.get("k") == "v"

    def test_get_string_value(self, cache):
        cache.set("s", "hello world")
        assert cache.get("s") == "hello world"

    def test_get_integer_value(self, cache):
        cache.set("i", 42)
        assert cache.get("i") == 42

    def test_get_list_value(self, cache):
        cache.set("l", [1, 2, 3])
        assert cache.get("l") == [1, 2, 3]

    def test_get_dict_value(self, cache):
        d = {"model": "gpt-4", "tokens": 100}
        cache.set("d", d)
        assert cache.get("d") == d

    def test_get_none_value_returns_none_but_entry_exists(self, cache):
        """set(key, None) stores an entry; get returns None (same as miss)."""
        cache.set("null_key", None)
        # Size proves the entry exists even though get() returns None
        assert cache.size == 1
        assert cache.get("null_key") is None


# ===========================================================================
# 3. set()
# ===========================================================================

class TestSet:
    """Covers set: insertion, overwrite, eviction, timestamp refresh."""

    def test_set_then_get_returns_value(self, cache):
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_set_increases_size_by_one(self, cache):
        before = cache.size
        cache.set("new_key", 99)
        assert cache.size == before + 1

    def test_set_existing_key_does_not_increase_size(self, cache):
        cache.set("k", 1)
        before = cache.size
        cache.set("k", 2)
        assert cache.size == before

    def test_set_overwrites_existing_key(self, cache):
        cache.set("k", "old")
        cache.set("k", "new")
        assert cache.get("k") == "new"

    def test_set_overwrite_moves_key_to_end(self):
        """Overwriting existing key should promote it (LRU order)."""
        c = LRUCache(max_size=3, ttl_seconds=3600)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        c.set("a", 99)   # refresh "a" → now most recent
        c.set("d", 4)    # "b" is LRU, evicted
        assert c.get("a") == 99
        assert c.get("b") is None

    def test_set_at_max_size_evicts_oldest(self):
        c = LRUCache(max_size=3, ttl_seconds=3600)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        c.set("d", 4)     # evicts "a"
        assert c.get("a") is None
        assert c.get("d") == 4

    def test_set_at_max_size_keeps_size_at_max(self):
        c = LRUCache(max_size=3, ttl_seconds=3600)
        for i in range(6):
            c.set(f"k{i}", i)
        assert c.size == 3

    def test_max_size_1_second_set_evicts_first(self):
        c = LRUCache(max_size=1, ttl_seconds=3600)
        c.set("a", 1)
        c.set("b", 2)
        assert c.get("a") is None
        assert c.get("b") == 2

    def test_max_size_3_fourth_item_evicts_first(self):
        c = LRUCache(max_size=3, ttl_seconds=3600)
        c.set("x", 1)
        c.set("y", 2)
        c.set("z", 3)
        c.set("w", 4)
        assert c.get("x") is None
        assert c.get("y") == 2
        assert c.get("z") == 3
        assert c.get("w") == 4

    def test_set_updates_timestamp_on_overwrite(self):
        """After overwrite, the entry should not expire at the original time."""
        with patch("ai.model_provider.time") as mock_time:
            mock_time.time.return_value = 1000.0
            c = LRUCache(max_size=5, ttl_seconds=60)
            c.set("k", "v1")

            mock_time.time.return_value = 1050.0   # 50 s — overwrite
            c.set("k", "v2")

            mock_time.time.return_value = 1070.0   # 70 s since original set
            # but only 20 s since overwrite → should NOT be expired
            assert c.get("k") == "v2"

    def test_set_large_value(self, cache):
        big = list(range(1000))
        cache.set("big", big)
        assert cache.get("big") == big

    def test_set_empty_string_key(self, cache):
        cache.set("", "empty_key")
        assert cache.get("") == "empty_key"

    def test_set_numeric_string_keys(self, cache):
        cache.set("1", "one")
        cache.set("2", "two")
        assert cache.get("1") == "one"
        assert cache.get("2") == "two"

    def test_set_does_not_evict_below_max_size(self):
        c = LRUCache(max_size=5, ttl_seconds=3600)
        for i in range(4):
            c.set(f"k{i}", i)
        assert c.size == 4
        assert c.get("k0") == 0   # none evicted yet


# ===========================================================================
# 4. remove()
# ===========================================================================

class TestRemove:
    """Covers remove: return value, side-effects, edge cases."""

    def test_remove_existing_key_returns_true(self, cache):
        cache.set("k", "v")
        assert cache.remove("k") is True

    def test_remove_missing_key_returns_false(self, cache):
        assert cache.remove("nonexistent") is False

    def test_remove_empty_cache_returns_false(self):
        assert LRUCache().remove("k") is False

    def test_remove_actually_deletes_entry(self, cache):
        cache.set("k", "v")
        cache.remove("k")
        assert cache.get("k") is None

    def test_remove_decreases_size(self, cache):
        cache.set("a", 1)
        cache.set("b", 2)
        cache.remove("a")
        assert cache.size == 1

    def test_double_remove_second_returns_false(self, cache):
        cache.set("k", "v")
        cache.remove("k")
        assert cache.remove("k") is False

    def test_remove_does_not_affect_other_keys(self, cache):
        cache.set("a", 1)
        cache.set("b", 2)
        cache.remove("a")
        assert cache.get("b") == 2

    def test_remove_returns_bool_type(self, cache):
        cache.set("k", "v")
        result = cache.remove("k")
        assert isinstance(result, bool)


# ===========================================================================
# 5. clear()
# ===========================================================================

class TestClear:
    """Covers clear: empties cache, idempotent on empty."""

    def test_clear_empties_cache(self, cache):
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.size == 0

    def test_clear_on_empty_cache_no_error(self):
        LRUCache().clear()   # should not raise

    def test_size_is_zero_after_clear(self, cache):
        for i in range(5):
            cache.set(f"k{i}", i)
        cache.clear()
        assert cache.size == 0

    def test_get_returns_none_for_all_keys_after_clear(self, cache):
        keys = ["x", "y", "z"]
        for k in keys:
            cache.set(k, k)
        cache.clear()
        for k in keys:
            assert cache.get(k) is None

    def test_clear_then_set_works_normally(self, cache):
        cache.set("old", 1)
        cache.clear()
        cache.set("new", 2)
        assert cache.get("new") == 2
        assert cache.size == 1


# ===========================================================================
# 6. cleanup_expired()
# ===========================================================================

class TestCleanupExpired:
    """Covers cleanup_expired: return count, selective removal, no-op cases."""

    def test_cleanup_on_fresh_cache_returns_zero(self, cache):
        cache.set("k", "v")
        assert cache.cleanup_expired() == 0

    def test_cleanup_on_empty_cache_returns_zero(self):
        assert LRUCache().cleanup_expired() == 0

    def test_cleanup_removes_expired_entries(self):
        with patch("ai.model_provider.time") as mock_time:
            mock_time.time.return_value = 1000.0
            c = LRUCache(max_size=10, ttl_seconds=60)
            c.set("a", 1)
            c.set("b", 2)
            mock_time.time.return_value = 1065.0
            c.cleanup_expired()
            assert c.size == 0

    def test_cleanup_returns_count_of_removed(self):
        with patch("ai.model_provider.time") as mock_time:
            mock_time.time.return_value = 1000.0
            c = LRUCache(max_size=10, ttl_seconds=60)
            c.set("a", 1)
            c.set("b", 2)
            c.set("c", 3)
            mock_time.time.return_value = 1065.0
            assert c.cleanup_expired() == 3

    def test_cleanup_keeps_non_expired_entries(self):
        with patch("ai.model_provider.time") as mock_time:
            mock_time.time.return_value = 1000.0
            c = LRUCache(max_size=10, ttl_seconds=3600)
            c.set("fresh", "keep")
            mock_time.time.return_value = 1001.0
            c.cleanup_expired()
            assert c.get("fresh") == "keep"

    def test_cleanup_mix_expired_and_fresh(self):
        with patch("ai.model_provider.time") as mock_time:
            # "old" set at t=1000, TTL=60 → expires at t=1060
            mock_time.time.return_value = 1000.0
            c = LRUCache(max_size=10, ttl_seconds=60)
            c.set("old", "stale")

            # "fresh" set at t=1062, TTL=60 → expires at t=1122
            mock_time.time.return_value = 1062.0
            c.set("fresh", "keep")

            # cleanup at t=1063: "old" expired, "fresh" not
            mock_time.time.return_value = 1063.0
            removed = c.cleanup_expired()
            assert removed == 1
            assert c.get("fresh") == "keep"

    def test_cleanup_all_entries_expired(self):
        with patch("ai.model_provider.time") as mock_time:
            mock_time.time.return_value = 500.0
            c = LRUCache(max_size=10, ttl_seconds=10)
            for i in range(5):
                c.set(f"k{i}", i)
            mock_time.time.return_value = 512.0
            removed = c.cleanup_expired()
            assert removed == 5
            assert c.size == 0

    def test_cleanup_returns_integer(self, cache):
        result = cache.cleanup_expired()
        assert isinstance(result, int)

    def test_cleanup_idempotent_second_call_returns_zero(self):
        with patch("ai.model_provider.time") as mock_time:
            mock_time.time.return_value = 1000.0
            c = LRUCache(max_size=10, ttl_seconds=60)
            c.set("k", "v")
            mock_time.time.return_value = 1065.0
            c.cleanup_expired()
            assert c.cleanup_expired() == 0

    def test_cleanup_does_not_remove_exactly_at_ttl_boundary(self):
        """Entry at exactly TTL seconds is NOT expired (uses strict >)."""
        with patch("ai.model_provider.time") as mock_time:
            mock_time.time.return_value = 1000.0
            c = LRUCache(max_size=5, ttl_seconds=60)
            c.set("k", "v")
            mock_time.time.return_value = 1060.0   # exactly 60 s — not > 60
            removed = c.cleanup_expired()
            assert removed == 0


# ===========================================================================
# 7. size property
# ===========================================================================

class TestSize:
    """Covers the size property under various cache operations."""

    def test_size_starts_at_zero(self):
        assert LRUCache().size == 0

    def test_size_increases_with_each_set(self, cache):
        for i in range(4):
            cache.set(f"k{i}", i)
            assert cache.size == i + 1

    def test_size_decreases_with_remove(self, cache):
        cache.set("a", 1)
        cache.set("b", 2)
        cache.remove("a")
        assert cache.size == 1

    def test_size_stays_at_max_when_eviction_happens(self):
        c = LRUCache(max_size=3, ttl_seconds=3600)
        for i in range(6):
            c.set(f"k{i}", i)
        assert c.size == 3

    def test_size_is_zero_after_clear(self, cache):
        for i in range(5):
            cache.set(f"k{i}", i)
        cache.clear()
        assert cache.size == 0

    def test_size_is_int(self, cache):
        assert isinstance(cache.size, int)


# ===========================================================================
# 8. stats()
# ===========================================================================

class TestStats:
    """Covers the stats() dict: keys present, values correct."""

    def test_stats_returns_dict(self, cache):
        assert isinstance(cache.stats(), dict)

    def test_stats_has_four_keys(self, cache):
        expected_keys = {"size", "max_size", "ttl_seconds", "keys"}
        assert set(cache.stats().keys()) == expected_keys

    def test_stats_size_matches_actual_size(self, cache):
        cache.set("a", 1)
        cache.set("b", 2)
        s = cache.stats()
        assert s["size"] == cache.size == 2

    def test_stats_max_size_matches_constructor_arg(self):
        c = LRUCache(max_size=17, ttl_seconds=3600)
        assert c.stats()["max_size"] == 17

    def test_stats_ttl_seconds_matches_constructor_arg(self):
        c = LRUCache(max_size=5, ttl_seconds=999)
        assert c.stats()["ttl_seconds"] == 999

    def test_stats_keys_is_list(self, cache):
        cache.set("x", 1)
        assert isinstance(cache.stats()["keys"], list)

    def test_stats_keys_lists_current_keys(self, cache):
        cache.set("alpha", 1)
        cache.set("beta", 2)
        keys = cache.stats()["keys"]
        assert "alpha" in keys
        assert "beta" in keys

    def test_stats_keys_empty_on_empty_cache(self):
        assert LRUCache().stats()["keys"] == []

    def test_stats_keys_does_not_include_removed_key(self, cache):
        cache.set("gone", 1)
        cache.remove("gone")
        assert "gone" not in cache.stats()["keys"]

    def test_stats_keys_does_not_include_cleared_keys(self, cache):
        cache.set("a", 1)
        cache.clear()
        assert cache.stats()["keys"] == []

    def test_stats_keys_does_not_include_expired_keys(self):
        with patch("ai.model_provider.time") as mock_time:
            mock_time.time.return_value = 1000.0
            c = LRUCache(max_size=5, ttl_seconds=60)
            c.set("expires", "soon")
            mock_time.time.return_value = 1065.0
            c.get("expires")  # triggers lazy deletion
            assert "expires" not in c.stats()["keys"]

    def test_stats_size_decrements_after_remove(self, cache):
        cache.set("k", "v")
        cache.remove("k")
        assert cache.stats()["size"] == 0


# ===========================================================================
# 9. LRU eviction order
# ===========================================================================

class TestLRUEvictionOrder:
    """Confirms that least-recently-used entries are evicted first."""

    def test_access_oldest_protects_it_from_eviction(self):
        c = LRUCache(max_size=3, ttl_seconds=3600)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        c.get("a")           # a is now most-recent; b is LRU
        c.set("d", 4)
        assert c.get("a") == 1
        assert c.get("b") is None
        assert c.get("c") == 3
        assert c.get("d") == 4

    def test_fifo_order_without_any_gets(self):
        c = LRUCache(max_size=3, ttl_seconds=3600)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        c.set("d", 4)    # evicts "a"
        c.set("e", 5)    # evicts "b"
        assert c.get("a") is None
        assert c.get("b") is None
        assert c.get("c") == 3

    def test_multiple_gets_reorder_eviction(self):
        c = LRUCache(max_size=4, ttl_seconds=3600)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        c.set("d", 4)
        # Access in order a, b (now c and d are oldest)
        c.get("a")
        c.get("b")
        c.set("e", 5)  # evicts c
        c.set("f", 6)  # evicts d
        assert c.get("c") is None
        assert c.get("d") is None
        assert c.get("a") == 1
        assert c.get("b") == 2

    def test_overwrite_promotes_to_most_recent(self):
        c = LRUCache(max_size=3, ttl_seconds=3600)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        c.set("a", 10)   # overwrite; "a" is now most-recent, "b" is LRU
        c.set("d", 4)
        assert c.get("b") is None
        assert c.get("a") == 10

    def test_inserting_many_entries_only_max_remain(self):
        c = LRUCache(max_size=5, ttl_seconds=3600)
        for i in range(20):
            c.set(f"k{i}", i)
        assert c.size == 5

    def test_last_five_entries_remain_after_overflow(self):
        c = LRUCache(max_size=5, ttl_seconds=3600)
        for i in range(10):
            c.set(f"k{i}", i)
        for i in range(5):
            assert c.get(f"k{i}") is None       # evicted
        for i in range(5, 10):
            assert c.get(f"k{i}") == i           # retained

    def test_set_read_interleaving_respects_lru_order(self):
        # Capacity 3.
        # State after each step (oldest → newest):
        #   set a  → [a]
        #   set b  → [a, b]
        #   get a  → [b, a]        (a promoted)
        #   set c  → [b, a, c]     (full)
        #   set d  → evicts b → [a, c, d]
        c = LRUCache(max_size=3, ttl_seconds=3600)
        c.set("a", 1)
        c.set("b", 2)
        c.get("a")       # a → recent; b is LRU
        c.set("c", 3)    # full: [b(LRU), a, c(MRU)]
        c.set("d", 4)    # evicts b (LRU)
        assert c.get("b") is None
        assert c.get("a") == 1
        assert c.get("c") == 3
        assert c.get("d") == 4

    def test_stats_keys_reflects_lru_order(self):
        """The keys list in stats should reflect insertion/promotion order."""
        c = LRUCache(max_size=3, ttl_seconds=3600)
        c.set("first", 1)
        c.set("second", 2)
        c.set("third", 3)
        keys = c.stats()["keys"]
        assert keys == ["first", "second", "third"]

    def test_get_reorders_key_in_stats(self):
        c = LRUCache(max_size=3, ttl_seconds=3600)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        c.get("a")       # "a" moves to end
        keys = c.stats()["keys"]
        assert keys[-1] == "a"

    def test_eviction_under_mixed_get_set(self):
        c = LRUCache(max_size=2, ttl_seconds=3600)
        c.set("a", 1)
        c.set("b", 2)
        c.get("a")       # a is most-recent; b is LRU
        c.set("c", 3)    # evicts b
        assert c.get("b") is None
        assert c.get("a") == 1
        assert c.get("c") == 3


# ===========================================================================
# 10. Concurrency / thread-safety
# ===========================================================================

class TestConcurrency:
    """Basic thread-safety smoke tests using Python threads."""

    def test_concurrent_set_no_exception(self):
        c = LRUCache(max_size=50, ttl_seconds=3600)
        errors: list = []

        def writer(n: int) -> None:
            try:
                for i in range(20):
                    c.set(f"k_{n}_{i}", n * i)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert c.size <= 50

    def test_concurrent_get_set_no_exception(self):
        c = LRUCache(max_size=10, ttl_seconds=3600)
        errors: list = []

        def reader_writer(n: int) -> None:
            try:
                for i in range(15):
                    c.set(f"key{n}", n + i)
                    c.get(f"key{n}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=reader_writer, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []

    def test_concurrent_remove_no_exception(self):
        c = LRUCache(max_size=100, ttl_seconds=3600)
        for i in range(50):
            c.set(f"k{i}", i)

        errors: list = []

        def remover(start: int) -> None:
            try:
                for i in range(start, start + 10):
                    c.remove(f"k{i}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=remover, args=(t * 10,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []

    def test_concurrent_clear_no_exception(self):
        c = LRUCache(max_size=50, ttl_seconds=3600)
        errors: list = []

        def setter() -> None:
            try:
                for i in range(10):
                    c.set(f"k{i}", i)
            except Exception as exc:
                errors.append(exc)

        def clearer() -> None:
            try:
                for _ in range(5):
                    c.clear()
            except Exception as exc:
                errors.append(exc)

        threads = (
            [threading.Thread(target=setter) for _ in range(3)]
            + [threading.Thread(target=clearer) for _ in range(2)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []

    def test_concurrent_cleanup_no_exception(self):
        with patch("ai.model_provider.time") as mock_time:
            mock_time.time.return_value = 1000.0
            c = LRUCache(max_size=50, ttl_seconds=60)
            for i in range(20):
                c.set(f"k{i}", i)

            mock_time.time.return_value = 1065.0
            errors: list = []

            def cleanup_worker() -> None:
                try:
                    c.cleanup_expired()
                except Exception as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=cleanup_worker) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert errors == []
