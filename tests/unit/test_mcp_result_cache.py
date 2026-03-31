"""
Tests for ResultCache in src/ai/mcp/mcp_tool_wrapper.py

Covers get (miss, hit, expired), set (store, LRU eviction when at capacity),
clear, and get_stats (hits/misses/hit_rate/size/max_size).
No network, no Tkinter, no external dependencies.
"""

import sys
import time
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ai.mcp.mcp_tool_wrapper import ResultCache
from ai.tools.base_tool import ToolResult


def _result(val="ok") -> ToolResult:
    return ToolResult(success=True, output=val)


# ===========================================================================
# get — miss
# ===========================================================================

class TestResultCacheGet:
    def test_miss_returns_none(self):
        cache = ResultCache()
        assert cache.get("nonexistent") is None

    def test_hit_returns_result(self):
        cache = ResultCache()
        r = _result("hello")
        cache.set("key1", r)
        assert cache.get("key1") is r

    def test_expired_returns_none(self):
        cache = ResultCache(default_ttl=0.01)  # 10ms TTL
        cache.set("key", _result())
        time.sleep(0.05)  # Wait past TTL
        assert cache.get("key") is None

    def test_not_expired_returns_result(self):
        cache = ResultCache(default_ttl=60.0)
        r = _result("fresh")
        cache.set("key", r)
        assert cache.get("key") is r

    def test_different_keys_isolated(self):
        cache = ResultCache()
        cache.set("a", _result("A"))
        cache.set("b", _result("B"))
        assert cache.get("a").output == "A"
        assert cache.get("b").output == "B"


# ===========================================================================
# set — capacity and LRU eviction
# ===========================================================================

class TestResultCacheSet:
    def test_set_stores_result(self):
        cache = ResultCache()
        cache.set("k", _result("val"))
        assert cache.get("k") is not None

    def test_evicts_oldest_when_full(self):
        cache = ResultCache(max_size=2)
        cache.set("a", _result())
        cache.set("b", _result())
        cache.set("c", _result())  # Should evict "a"
        assert cache.get("a") is None

    def test_newest_survives_eviction(self):
        cache = ResultCache(max_size=2)
        cache.set("a", _result())
        cache.set("b", _result())
        cache.set("c", _result())
        assert cache.get("b") is not None
        assert cache.get("c") is not None

    def test_overwrite_same_key(self):
        cache = ResultCache()
        cache.set("k", _result("first"))
        cache.set("k", _result("second"))
        result = cache.get("k")
        assert result.output == "second"

    def test_size_stays_at_max(self):
        cache = ResultCache(max_size=3)
        for i in range(10):
            cache.set(f"key{i}", _result())
        assert cache.get_stats()["size"] <= 3


# ===========================================================================
# clear
# ===========================================================================

class TestResultCacheClear:
    def test_clear_empties_cache(self):
        cache = ResultCache()
        cache.set("a", _result())
        cache.set("b", _result())
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_clear_resets_size_to_zero(self):
        cache = ResultCache()
        cache.set("x", _result())
        cache.clear()
        assert cache.get_stats()["size"] == 0

    def test_clear_empty_cache_no_error(self):
        cache = ResultCache()
        cache.clear()  # Should not raise


# ===========================================================================
# get_stats
# ===========================================================================

class TestResultCacheStats:
    def test_initial_stats_all_zero(self):
        cache = ResultCache()
        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["size"] == 0

    def test_stats_has_all_keys(self):
        cache = ResultCache()
        stats = cache.get_stats()
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats
        assert "size" in stats
        assert "max_size" in stats

    def test_max_size_matches_constructor(self):
        cache = ResultCache(max_size=50)
        assert cache.get_stats()["max_size"] == 50

    def test_miss_increments_misses(self):
        cache = ResultCache()
        cache.get("nonexistent")
        assert cache.get_stats()["misses"] == 1

    def test_hit_increments_hits(self):
        cache = ResultCache()
        cache.set("k", _result())
        cache.get("k")
        assert cache.get_stats()["hits"] == 1

    def test_hit_rate_100_percent_all_hits(self):
        cache = ResultCache()
        cache.set("k", _result())
        cache.get("k")
        stats = cache.get_stats()
        assert stats["hit_rate"] == "100.0%"

    def test_hit_rate_zero_percent_all_misses(self):
        cache = ResultCache()
        cache.get("nonexistent")
        stats = cache.get_stats()
        assert stats["hit_rate"] == "0.0%"

    def test_hit_rate_zero_when_no_requests(self):
        cache = ResultCache()
        stats = cache.get_stats()
        assert stats["hit_rate"] == "0.0%"

    def test_size_increments_on_set(self):
        cache = ResultCache()
        cache.set("a", _result())
        cache.set("b", _result())
        assert cache.get_stats()["size"] == 2

    def test_hit_rate_is_string(self):
        cache = ResultCache()
        assert isinstance(cache.get_stats()["hit_rate"], str)
