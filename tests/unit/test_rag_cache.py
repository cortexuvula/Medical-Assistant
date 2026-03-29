"""
Tests for src/rag/cache/base.py and src/rag/cache/factory.py

Covers:
- CacheBackend enum (values)
- CacheConfig dataclass (defaults, custom values)
- CacheStats dataclass (defaults, fields)
- CacheEntry dataclass (fields, timestamps)
- BaseCacheProvider is abstract
- get_cache_config_from_env (defaults, env var overrides)
- reset_cache_provider (clears singleton)
No network, no file I/O, no Redis/SQLite.
"""

import sys
import os
import pytest
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from rag.cache.base import (
    CacheBackend, CacheConfig, CacheStats, CacheEntry, BaseCacheProvider
)
from rag.cache.factory import (
    get_cache_config_from_env, reset_cache_provider
)
import rag.cache.factory as _factory_module


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Remove cache-related env vars before each test."""
    for var in [
        "REDIS_URL", "REDIS_PREFIX",
        "EMBEDDING_CACHE_BACKEND",
        "EMBEDDING_CACHE_FALLBACK",
        "EMBEDDING_CACHE_MAX_ENTRIES",
        "EMBEDDING_CACHE_MAX_AGE_DAYS",
        "EMBEDDING_CACHE_RETRY_SECONDS",
    ]:
        monkeypatch.delenv(var, raising=False)
    # Also reset the global singleton
    reset_cache_provider()
    yield
    reset_cache_provider()


# ===========================================================================
# CacheBackend enum
# ===========================================================================

class TestCacheBackend:
    def test_sqlite_value(self):
        assert CacheBackend.SQLITE.value == "sqlite"

    def test_redis_value(self):
        assert CacheBackend.REDIS.value == "redis"

    def test_fallback_value(self):
        assert CacheBackend.FALLBACK.value == "fallback"

    def test_auto_value(self):
        assert CacheBackend.AUTO.value == "auto"

    def test_has_four_members(self):
        assert len(list(CacheBackend)) == 4

    def test_all_values_are_strings(self):
        for member in CacheBackend:
            assert isinstance(member.value, str)


# ===========================================================================
# CacheConfig defaults
# ===========================================================================

class TestCacheConfigDefaults:
    def test_default_backend_is_auto(self):
        cfg = CacheConfig()
        assert cfg.backend == CacheBackend.AUTO

    def test_default_redis_url_is_none(self):
        cfg = CacheConfig()
        assert cfg.redis_url is None

    def test_default_redis_prefix(self):
        cfg = CacheConfig()
        assert cfg.redis_prefix == "medassist:embedding:"

    def test_default_sqlite_path_is_none(self):
        cfg = CacheConfig()
        assert cfg.sqlite_path is None

    def test_default_max_entries(self):
        cfg = CacheConfig()
        assert cfg.max_entries == 10000

    def test_default_max_age_days(self):
        cfg = CacheConfig()
        assert cfg.max_age_days == 30

    def test_default_enable_fallback(self):
        cfg = CacheConfig()
        assert cfg.enable_fallback is True

    def test_default_retry_primary_seconds(self):
        cfg = CacheConfig()
        assert cfg.retry_primary_seconds == 60


class TestCacheConfigCustom:
    def test_custom_backend(self):
        cfg = CacheConfig(backend=CacheBackend.REDIS)
        assert cfg.backend == CacheBackend.REDIS

    def test_custom_redis_url(self):
        cfg = CacheConfig(redis_url="redis://localhost:6379")
        assert cfg.redis_url == "redis://localhost:6379"

    def test_custom_max_entries(self):
        cfg = CacheConfig(max_entries=500)
        assert cfg.max_entries == 500

    def test_custom_enable_fallback_false(self):
        cfg = CacheConfig(enable_fallback=False)
        assert cfg.enable_fallback is False

    def test_custom_retry_seconds(self):
        cfg = CacheConfig(retry_primary_seconds=120)
        assert cfg.retry_primary_seconds == 120


# ===========================================================================
# CacheStats defaults
# ===========================================================================

class TestCacheStats:
    def test_backend_stored(self):
        stats = CacheStats(backend="sqlite")
        assert stats.backend == "sqlite"

    def test_default_total_entries_zero(self):
        stats = CacheStats(backend="redis")
        assert stats.total_entries == 0

    def test_default_hit_count_zero(self):
        stats = CacheStats(backend="redis")
        assert stats.hit_count == 0

    def test_default_miss_count_zero(self):
        stats = CacheStats(backend="redis")
        assert stats.miss_count == 0

    def test_default_hit_rate_zero(self):
        stats = CacheStats(backend="redis")
        assert stats.hit_rate == 0.0

    def test_default_cache_size_zero(self):
        stats = CacheStats(backend="redis")
        assert stats.cache_size_bytes == 0

    def test_default_oldest_entry_none(self):
        stats = CacheStats(backend="redis")
        assert stats.oldest_entry is None

    def test_default_last_cleanup_none(self):
        stats = CacheStats(backend="redis")
        assert stats.last_cleanup is None

    def test_default_is_healthy_true(self):
        stats = CacheStats(backend="redis")
        assert stats.is_healthy is True

    def test_extra_info_is_dict(self):
        stats = CacheStats(backend="redis")
        assert isinstance(stats.extra_info, dict)


# ===========================================================================
# CacheEntry
# ===========================================================================

class TestCacheEntry:
    def test_text_hash_stored(self):
        e = CacheEntry(text_hash="abc123", model="ada-002", embedding=[0.1, 0.2])
        assert e.text_hash == "abc123"

    def test_model_stored(self):
        e = CacheEntry(text_hash="hash", model="text-embedding-3", embedding=[1.0])
        assert e.model == "text-embedding-3"

    def test_embedding_stored(self):
        vec = [0.1, 0.2, 0.3]
        e = CacheEntry(text_hash="h", model="m", embedding=vec)
        assert e.embedding == vec

    def test_created_at_is_datetime(self):
        e = CacheEntry(text_hash="h", model="m", embedding=[])
        assert isinstance(e.created_at, datetime)

    def test_last_accessed_is_datetime(self):
        e = CacheEntry(text_hash="h", model="m", embedding=[])
        assert isinstance(e.last_accessed, datetime)

    def test_created_at_recent(self):
        before = datetime.now()
        e = CacheEntry(text_hash="h", model="m", embedding=[])
        after = datetime.now()
        assert before <= e.created_at <= after


# ===========================================================================
# BaseCacheProvider is abstract
# ===========================================================================

class TestBaseCacheProviderAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            BaseCacheProvider()

    def test_concrete_subclass_must_implement_get(self):
        class _Incomplete(BaseCacheProvider):
            pass
        with pytest.raises(TypeError):
            _Incomplete()


# ===========================================================================
# get_cache_config_from_env — defaults
# ===========================================================================

class TestGetCacheConfigFromEnvDefaults:
    def test_default_backend_is_auto(self):
        cfg = get_cache_config_from_env()
        assert cfg.backend == CacheBackend.AUTO

    def test_default_redis_url_is_none(self):
        cfg = get_cache_config_from_env()
        assert cfg.redis_url is None

    def test_default_redis_prefix(self):
        cfg = get_cache_config_from_env()
        assert cfg.redis_prefix == "medassist:embedding:"

    def test_default_max_entries(self):
        cfg = get_cache_config_from_env()
        assert cfg.max_entries == 10000

    def test_default_max_age_days(self):
        cfg = get_cache_config_from_env()
        assert cfg.max_age_days == 30

    def test_default_enable_fallback_true(self):
        cfg = get_cache_config_from_env()
        assert cfg.enable_fallback is True

    def test_returns_cache_config(self):
        cfg = get_cache_config_from_env()
        assert isinstance(cfg, CacheConfig)


# ===========================================================================
# get_cache_config_from_env — env var overrides
# ===========================================================================

class TestGetCacheConfigFromEnvOverrides:
    def test_redis_backend_env(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_CACHE_BACKEND", "redis")
        cfg = get_cache_config_from_env()
        assert cfg.backend == CacheBackend.REDIS

    def test_sqlite_backend_env(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_CACHE_BACKEND", "sqlite")
        cfg = get_cache_config_from_env()
        assert cfg.backend == CacheBackend.SQLITE

    def test_fallback_backend_env(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_CACHE_BACKEND", "fallback")
        cfg = get_cache_config_from_env()
        assert cfg.backend == CacheBackend.FALLBACK

    def test_unknown_backend_defaults_to_auto(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_CACHE_BACKEND", "unknown")
        cfg = get_cache_config_from_env()
        assert cfg.backend == CacheBackend.AUTO

    def test_redis_url_env(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://myhost:6379")
        cfg = get_cache_config_from_env()
        assert cfg.redis_url == "redis://myhost:6379"

    def test_redis_prefix_env(self, monkeypatch):
        monkeypatch.setenv("REDIS_PREFIX", "myapp:emb:")
        cfg = get_cache_config_from_env()
        assert cfg.redis_prefix == "myapp:emb:"

    def test_max_entries_env(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_CACHE_MAX_ENTRIES", "5000")
        cfg = get_cache_config_from_env()
        assert cfg.max_entries == 5000

    def test_max_age_days_env(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_CACHE_MAX_AGE_DAYS", "7")
        cfg = get_cache_config_from_env()
        assert cfg.max_age_days == 7

    def test_enable_fallback_false_env(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_CACHE_FALLBACK", "false")
        cfg = get_cache_config_from_env()
        assert cfg.enable_fallback is False

    def test_enable_fallback_true_env(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_CACHE_FALLBACK", "true")
        cfg = get_cache_config_from_env()
        assert cfg.enable_fallback is True

    def test_invalid_max_entries_uses_default(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_CACHE_MAX_ENTRIES", "not_a_number")
        cfg = get_cache_config_from_env()
        assert cfg.max_entries == 10000

    def test_invalid_max_age_days_uses_default(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_CACHE_MAX_AGE_DAYS", "bad")
        cfg = get_cache_config_from_env()
        assert cfg.max_age_days == 30

    def test_retry_seconds_env(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_CACHE_RETRY_SECONDS", "120")
        cfg = get_cache_config_from_env()
        assert cfg.retry_primary_seconds == 120

    def test_invalid_retry_seconds_uses_default(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_CACHE_RETRY_SECONDS", "bad")
        cfg = get_cache_config_from_env()
        assert cfg.retry_primary_seconds == 60


# ===========================================================================
# reset_cache_provider
# ===========================================================================

class TestResetCacheProvider:
    def test_reset_clears_singleton(self):
        # Reset returns singleton to None
        reset_cache_provider()
        assert _factory_module._cache_provider is None

    def test_reset_on_none_no_error(self):
        # Second reset should not raise
        reset_cache_provider()
        reset_cache_provider()
