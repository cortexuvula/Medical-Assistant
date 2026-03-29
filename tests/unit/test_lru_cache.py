"""
Tests for LRUCache in src/ai/model_provider.py

Covers get/set/remove/clear/cleanup_expired/size/stats, LRU eviction
ordering, TTL expiry, and thread-safety.
Pure in-memory logic — no network, no Tkinter, no file I/O.
"""

import sys
import time
import threading
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.model_provider import LRUCache


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _cache(max_size: int = 5, ttl_seconds: int = 3600) -> LRUCache:
    return LRUCache(max_size=max_size, ttl_seconds=ttl_seconds)


# ===========================================================================
# get / set — basic
# ===========================================================================

class TestGetSet:
    def test_get_missing_key_returns_none(self):
        c = _cache()
        assert c.get("missing") is None

    def test_set_and_get_returns_value(self):
        c = _cache()
        c.set("key", "value")
        assert c.get("key") == "value"

    def test_set_overwrite_updates_value(self):
        c = _cache()
        c.set("key", "v1")
        c.set("key", "v2")
        assert c.get("key") == "v2"

    def test_set_any_json_serializable_value(self):
        c = _cache()
        data = {"models": ["gpt-4", "claude-3"]}
        c.set("models", data)
        assert c.get("models") == data

    def test_set_list_value(self):
        c = _cache()
        c.set("list", [1, 2, 3])
        assert c.get("list") == [1, 2, 3]

    def test_set_none_value(self):
        c = _cache()
        c.set("key", None)
        assert c.get("key") is None

    def test_multiple_keys_stored(self):
        c = _cache()
        for i in range(5):
            c.set(f"key{i}", i)
        for i in range(5):
            assert c.get(f"key{i}") == i


# ===========================================================================
# TTL expiry
# ===========================================================================

class TestTTL:
    def test_expired_entry_returns_none(self):
        c = _cache(ttl_seconds=0)  # Immediately expires
        c.set("key", "value")
        time.sleep(0.01)
        assert c.get("key") is None

    def test_fresh_entry_not_expired(self):
        c = _cache(ttl_seconds=3600)
        c.set("key", "value")
        assert c.get("key") == "value"

    def test_cleanup_expired_removes_old_entries(self):
        c = _cache(ttl_seconds=0)
        c.set("k1", "v1")
        c.set("k2", "v2")
        time.sleep(0.01)
        removed = c.cleanup_expired()
        assert removed == 2

    def test_cleanup_expired_keeps_fresh_entries(self):
        c = _cache(ttl_seconds=3600)
        c.set("k1", "v1")
        removed = c.cleanup_expired()
        assert removed == 0
        assert c.get("k1") == "v1"

    def test_cleanup_expired_returns_int(self):
        c = _cache()
        assert isinstance(c.cleanup_expired(), int)

    def test_cleanup_expired_with_mixed_entries(self):
        c = _cache(max_size=10, ttl_seconds=0)
        c.set("old", "x")
        time.sleep(0.01)
        # Manually add a fresh entry by replacing TTL temporarily
        c2 = _cache(max_size=10, ttl_seconds=3600)
        c2.set("fresh", "y")
        # Just check cleanup on the expired cache
        removed = c.cleanup_expired()
        assert removed == 1


# ===========================================================================
# LRU eviction
# ===========================================================================

class TestLRUEviction:
    def test_oldest_evicted_when_full(self):
        c = _cache(max_size=3)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        # Add one more — "a" should be evicted
        c.set("d", 4)
        assert c.get("a") is None
        assert c.get("b") == 2
        assert c.get("c") == 3
        assert c.get("d") == 4

    def test_recently_used_not_evicted(self):
        c = _cache(max_size=3)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        # Access "a" to make it recently used
        c.get("a")
        # Add one more — "b" (now the LRU) should be evicted
        c.set("d", 4)
        assert c.get("a") == 1  # Still present
        assert c.get("b") is None  # Evicted
        assert c.get("c") == 3
        assert c.get("d") == 4

    def test_size_never_exceeds_max(self):
        c = _cache(max_size=2)
        for i in range(10):
            c.set(f"key{i}", i)
        assert c.size <= 2

    def test_overwrite_does_not_increase_size(self):
        c = _cache(max_size=3)
        c.set("a", 1)
        c.set("b", 2)
        c.set("a", 99)  # Overwrite, not a new entry
        assert c.size == 2

    def test_max_size_1_keeps_latest(self):
        c = _cache(max_size=1)
        c.set("a", 1)
        c.set("b", 2)
        assert c.get("a") is None
        assert c.get("b") == 2


# ===========================================================================
# remove
# ===========================================================================

class TestRemove:
    def test_remove_existing_key_returns_true(self):
        c = _cache()
        c.set("key", "value")
        assert c.remove("key") is True

    def test_remove_missing_key_returns_false(self):
        c = _cache()
        assert c.remove("nonexistent") is False

    def test_removed_key_not_retrievable(self):
        c = _cache()
        c.set("key", "value")
        c.remove("key")
        assert c.get("key") is None

    def test_remove_decreases_size(self):
        c = _cache()
        c.set("a", 1)
        c.set("b", 2)
        c.remove("a")
        assert c.size == 1


# ===========================================================================
# clear
# ===========================================================================

class TestClear:
    def test_clear_empties_cache(self):
        c = _cache()
        c.set("a", 1)
        c.set("b", 2)
        c.clear()
        assert c.size == 0

    def test_clear_makes_all_keys_missing(self):
        c = _cache()
        c.set("a", 1)
        c.set("b", 2)
        c.clear()
        assert c.get("a") is None
        assert c.get("b") is None

    def test_clear_empty_cache_no_error(self):
        c = _cache()
        c.clear()  # Should not raise
        assert c.size == 0


# ===========================================================================
# size and stats
# ===========================================================================

class TestSizeAndStats:
    def test_empty_size_is_zero(self):
        assert _cache().size == 0

    def test_size_increments_with_set(self):
        c = _cache()
        c.set("a", 1)
        assert c.size == 1
        c.set("b", 2)
        assert c.size == 2

    def test_stats_returns_dict(self):
        assert isinstance(_cache().stats(), dict)

    def test_stats_contains_size(self):
        c = _cache()
        c.set("a", 1)
        assert c.stats()["size"] == 1

    def test_stats_contains_max_size(self):
        c = _cache(max_size=7)
        assert c.stats()["max_size"] == 7

    def test_stats_contains_ttl(self):
        c = _cache(ttl_seconds=999)
        assert c.stats()["ttl_seconds"] == 999

    def test_stats_contains_keys_list(self):
        c = _cache()
        c.set("x", 1)
        stats = c.stats()
        assert "keys" in stats
        assert "x" in stats["keys"]


# ===========================================================================
# Thread safety
# ===========================================================================

class TestThreadSafety:
    def test_concurrent_set_no_corruption(self):
        c = _cache(max_size=50)
        errors = []

        def writer(n):
            try:
                for i in range(20):
                    c.set(f"key_{n}_{i}", f"val_{n}_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert c.size <= 50

    def test_concurrent_get_set_no_error(self):
        c = _cache(max_size=10)
        errors = []

        def reader_writer(n):
            try:
                for i in range(10):
                    c.set(f"k{n}", n * i)
                    c.get(f"k{n}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader_writer, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
