import sys
import pytest
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from rag.cache.base import (
    CacheBackend, CacheConfig, CacheStats, CacheEntry, BaseCacheProvider
)
from typing import Optional


# ---------------------------------------------------------------------------
# Minimal concrete implementation used throughout the test suite
# ---------------------------------------------------------------------------

class _ConcreteCacheProvider(BaseCacheProvider):
    """Minimal valid implementation of BaseCacheProvider for testing."""

    def get(self, text_hash: str, model: str) -> Optional[list[float]]:
        return None

    def set(self, text_hash: str, embedding: list[float], model: str) -> bool:
        return True

    def get_batch(self, text_hashes: list[str], model: str) -> dict[str, list[float]]:
        return {}

    def set_batch(self, entries: list[tuple[str, list[float]]], model: str) -> int:
        return 0

    def delete(self, text_hash: str, model: str) -> bool:
        return False

    def clear(self) -> int:
        return 0

    def cleanup(
        self,
        max_age_days: Optional[int] = None,
        max_entries: Optional[int] = None,
    ) -> int:
        return 0

    def get_stats(self) -> CacheStats:
        return CacheStats(backend="test")

    def health_check(self) -> bool:
        return True


# ===========================================================================
# CacheBackend Enum
# ===========================================================================

class TestCacheBackendValues:
    def test_sqlite_value(self):
        assert CacheBackend.SQLITE.value == "sqlite"

    def test_redis_value(self):
        assert CacheBackend.REDIS.value == "redis"

    def test_fallback_value(self):
        assert CacheBackend.FALLBACK.value == "fallback"

    def test_auto_value(self):
        assert CacheBackend.AUTO.value == "auto"

    def test_member_count(self):
        assert len(CacheBackend) == 4

    def test_all_members_present(self):
        names = {m.name for m in CacheBackend}
        assert names == {"SQLITE", "REDIS", "FALLBACK", "AUTO"}

    def test_lookup_by_value_sqlite(self):
        assert CacheBackend("sqlite") is CacheBackend.SQLITE

    def test_lookup_by_value_redis(self):
        assert CacheBackend("redis") is CacheBackend.REDIS

    def test_lookup_by_value_fallback(self):
        assert CacheBackend("fallback") is CacheBackend.FALLBACK

    def test_lookup_by_value_auto(self):
        assert CacheBackend("auto") is CacheBackend.AUTO

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            CacheBackend("unknown")

    def test_members_are_enum_instances(self):
        for member in CacheBackend:
            assert isinstance(member, CacheBackend)

    def test_equality_by_identity(self):
        assert CacheBackend.SQLITE is CacheBackend.SQLITE

    def test_inequality_between_members(self):
        assert CacheBackend.SQLITE != CacheBackend.REDIS

    def test_enum_name_attribute(self):
        assert CacheBackend.AUTO.name == "AUTO"

    def test_repr_contains_name(self):
        assert "AUTO" in repr(CacheBackend.AUTO)


# ===========================================================================
# CacheConfig Dataclass
# ===========================================================================

class TestCacheConfigDefaults:
    def setup_method(self):
        self.cfg = CacheConfig()

    def test_default_backend(self):
        assert self.cfg.backend is CacheBackend.AUTO

    def test_default_redis_url_is_none(self):
        assert self.cfg.redis_url is None

    def test_default_redis_prefix(self):
        assert self.cfg.redis_prefix == "medassist:embedding:"

    def test_default_sqlite_path_is_none(self):
        assert self.cfg.sqlite_path is None

    def test_default_max_entries(self):
        assert self.cfg.max_entries == 10000

    def test_default_max_age_days(self):
        assert self.cfg.max_age_days == 30

    def test_default_enable_fallback(self):
        assert self.cfg.enable_fallback is True

    def test_default_retry_primary_seconds(self):
        assert self.cfg.retry_primary_seconds == 60


class TestCacheConfigCustomValues:
    def test_custom_backend(self):
        cfg = CacheConfig(backend=CacheBackend.SQLITE)
        assert cfg.backend is CacheBackend.SQLITE

    def test_custom_redis_url(self):
        cfg = CacheConfig(redis_url="redis://localhost:6379/0")
        assert cfg.redis_url == "redis://localhost:6379/0"

    def test_custom_redis_prefix(self):
        cfg = CacheConfig(redis_prefix="myapp:emb:")
        assert cfg.redis_prefix == "myapp:emb:"

    def test_custom_sqlite_path(self):
        cfg = CacheConfig(sqlite_path="/tmp/test.db")
        assert cfg.sqlite_path == "/tmp/test.db"

    def test_custom_max_entries(self):
        cfg = CacheConfig(max_entries=500)
        assert cfg.max_entries == 500

    def test_custom_max_age_days(self):
        cfg = CacheConfig(max_age_days=7)
        assert cfg.max_age_days == 7

    def test_disable_fallback(self):
        cfg = CacheConfig(enable_fallback=False)
        assert cfg.enable_fallback is False

    def test_custom_retry_primary_seconds(self):
        cfg = CacheConfig(retry_primary_seconds=120)
        assert cfg.retry_primary_seconds == 120

    def test_all_custom_values(self):
        cfg = CacheConfig(
            backend=CacheBackend.REDIS,
            redis_url="redis://host:6379",
            redis_prefix="pfx:",
            sqlite_path="/var/db.sqlite",
            max_entries=999,
            max_age_days=14,
            enable_fallback=False,
            retry_primary_seconds=30,
        )
        assert cfg.backend is CacheBackend.REDIS
        assert cfg.redis_url == "redis://host:6379"
        assert cfg.redis_prefix == "pfx:"
        assert cfg.sqlite_path == "/var/db.sqlite"
        assert cfg.max_entries == 999
        assert cfg.max_age_days == 14
        assert cfg.enable_fallback is False
        assert cfg.retry_primary_seconds == 30


class TestCacheConfigFieldTypes:
    def test_backend_type(self):
        assert isinstance(CacheConfig().backend, CacheBackend)

    def test_max_entries_type(self):
        assert isinstance(CacheConfig().max_entries, int)

    def test_max_age_days_type(self):
        assert isinstance(CacheConfig().max_age_days, int)

    def test_enable_fallback_type(self):
        assert isinstance(CacheConfig().enable_fallback, bool)

    def test_retry_primary_seconds_type(self):
        assert isinstance(CacheConfig().retry_primary_seconds, int)

    def test_redis_prefix_type(self):
        assert isinstance(CacheConfig().redis_prefix, str)


# ===========================================================================
# CacheStats Dataclass
# ===========================================================================

class TestCacheStatsDefaults:
    def setup_method(self):
        self.stats = CacheStats(backend="sqlite")

    def test_backend_stored(self):
        assert self.stats.backend == "sqlite"

    def test_default_total_entries(self):
        assert self.stats.total_entries == 0

    def test_default_hit_count(self):
        assert self.stats.hit_count == 0

    def test_default_miss_count(self):
        assert self.stats.miss_count == 0

    def test_default_hit_rate(self):
        assert self.stats.hit_rate == 0.0

    def test_default_cache_size_bytes(self):
        assert self.stats.cache_size_bytes == 0

    def test_default_oldest_entry_is_none(self):
        assert self.stats.oldest_entry is None

    def test_default_last_cleanup_is_none(self):
        assert self.stats.last_cleanup is None

    def test_default_is_healthy_true(self):
        assert self.stats.is_healthy is True

    def test_default_extra_info_is_empty_dict(self):
        assert self.stats.extra_info == {}

    def test_extra_info_is_independent_per_instance(self):
        s1 = CacheStats(backend="a")
        s2 = CacheStats(backend="b")
        s1.extra_info["key"] = "value"
        assert "key" not in s2.extra_info


class TestCacheStatsCustomCreation:
    def test_custom_backend(self):
        s = CacheStats(backend="redis")
        assert s.backend == "redis"

    def test_custom_total_entries(self):
        s = CacheStats(backend="sqlite", total_entries=42)
        assert s.total_entries == 42

    def test_custom_hit_count(self):
        s = CacheStats(backend="sqlite", hit_count=10)
        assert s.hit_count == 10

    def test_custom_miss_count(self):
        s = CacheStats(backend="sqlite", miss_count=5)
        assert s.miss_count == 5

    def test_custom_hit_rate(self):
        s = CacheStats(backend="sqlite", hit_rate=0.75)
        assert s.hit_rate == pytest.approx(0.75)

    def test_custom_cache_size_bytes(self):
        s = CacheStats(backend="sqlite", cache_size_bytes=1024)
        assert s.cache_size_bytes == 1024

    def test_custom_oldest_entry(self):
        dt = datetime(2024, 1, 1, 12, 0, 0)
        s = CacheStats(backend="sqlite", oldest_entry=dt)
        assert s.oldest_entry == dt

    def test_custom_last_cleanup(self):
        dt = datetime(2024, 6, 15, 8, 30, 0)
        s = CacheStats(backend="sqlite", last_cleanup=dt)
        assert s.last_cleanup == dt

    def test_is_healthy_false(self):
        s = CacheStats(backend="sqlite", is_healthy=False)
        assert s.is_healthy is False

    def test_custom_extra_info(self):
        s = CacheStats(backend="sqlite", extra_info={"version": "1.0"})
        assert s.extra_info == {"version": "1.0"}

    def test_all_custom_fields(self):
        dt1 = datetime(2024, 1, 1)
        dt2 = datetime(2024, 6, 1)
        s = CacheStats(
            backend="fallback",
            total_entries=100,
            hit_count=80,
            miss_count=20,
            hit_rate=0.8,
            cache_size_bytes=2048,
            oldest_entry=dt1,
            last_cleanup=dt2,
            is_healthy=True,
            extra_info={"pool_size": 5},
        )
        assert s.backend == "fallback"
        assert s.total_entries == 100
        assert s.hit_count == 80
        assert s.miss_count == 20
        assert s.hit_rate == pytest.approx(0.8)
        assert s.cache_size_bytes == 2048
        assert s.oldest_entry == dt1
        assert s.last_cleanup == dt2
        assert s.is_healthy is True
        assert s.extra_info == {"pool_size": 5}


# ===========================================================================
# CacheEntry Dataclass
# ===========================================================================

class TestCacheEntryConstruction:
    def test_required_fields_text_hash(self):
        entry = CacheEntry(
            text_hash="abc123",
            model="text-embedding-ada-002",
            embedding=[0.1, 0.2, 0.3],
        )
        assert entry.text_hash == "abc123"

    def test_required_fields_model(self):
        entry = CacheEntry(
            text_hash="abc123",
            model="text-embedding-ada-002",
            embedding=[0.1, 0.2, 0.3],
        )
        assert entry.model == "text-embedding-ada-002"

    def test_required_fields_embedding(self):
        emb = [0.1, 0.2, 0.3]
        entry = CacheEntry(text_hash="h", model="m", embedding=emb)
        assert entry.embedding == emb

    def test_created_at_defaults_to_datetime(self):
        before = datetime.now()
        entry = CacheEntry(text_hash="h", model="m", embedding=[])
        after = datetime.now()
        assert before <= entry.created_at <= after

    def test_last_accessed_defaults_to_datetime(self):
        before = datetime.now()
        entry = CacheEntry(text_hash="h", model="m", embedding=[])
        after = datetime.now()
        assert before <= entry.last_accessed <= after

    def test_custom_created_at(self):
        dt = datetime(2023, 5, 10, 10, 0, 0)
        entry = CacheEntry(text_hash="h", model="m", embedding=[], created_at=dt)
        assert entry.created_at == dt

    def test_custom_last_accessed(self):
        dt = datetime(2023, 8, 20, 15, 30, 0)
        entry = CacheEntry(text_hash="h", model="m", embedding=[], last_accessed=dt)
        assert entry.last_accessed == dt

    def test_embedding_preserves_order(self):
        emb = [0.9, 0.1, 0.5, 0.3]
        entry = CacheEntry(text_hash="h", model="m", embedding=emb)
        assert entry.embedding == [0.9, 0.1, 0.5, 0.3]

    def test_embedding_empty_list(self):
        entry = CacheEntry(text_hash="h", model="m", embedding=[])
        assert entry.embedding == []

    def test_embedding_large_vector(self):
        emb = [float(i) / 1536 for i in range(1536)]
        entry = CacheEntry(text_hash="h", model="m", embedding=emb)
        assert len(entry.embedding) == 1536

    def test_missing_text_hash_raises(self):
        with pytest.raises(TypeError):
            CacheEntry(model="m", embedding=[0.1])  # type: ignore[call-arg]

    def test_missing_model_raises(self):
        with pytest.raises(TypeError):
            CacheEntry(text_hash="h", embedding=[0.1])  # type: ignore[call-arg]

    def test_missing_embedding_raises(self):
        with pytest.raises(TypeError):
            CacheEntry(text_hash="h", model="m")  # type: ignore[call-arg]

    def test_independent_default_timestamps_across_instances(self):
        e1 = CacheEntry(text_hash="a", model="m", embedding=[])
        e2 = CacheEntry(text_hash="b", model="m", embedding=[])
        # Both should be datetime instances; not necessarily the same object
        assert isinstance(e1.created_at, datetime)
        assert isinstance(e2.created_at, datetime)

    def test_text_hash_is_str(self):
        entry = CacheEntry(text_hash="deadbeef", model="m", embedding=[0.0])
        assert isinstance(entry.text_hash, str)

    def test_model_is_str(self):
        entry = CacheEntry(text_hash="h", model="my-model", embedding=[0.0])
        assert isinstance(entry.model, str)


# ===========================================================================
# BaseCacheProvider ABC
# ===========================================================================

class TestBaseCacheProviderAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            BaseCacheProvider()  # type: ignore[abstract]

    def test_concrete_subclass_instantiates(self):
        provider = _ConcreteCacheProvider()
        assert provider is not None

    def test_concrete_subclass_is_instance_of_base(self):
        provider = _ConcreteCacheProvider()
        assert isinstance(provider, BaseCacheProvider)

    def test_close_does_not_raise(self):
        provider = _ConcreteCacheProvider()
        provider.close()  # must not raise

    def test_close_returns_none(self):
        provider = _ConcreteCacheProvider()
        result = provider.close()
        assert result is None

    def test_abstract_method_get_is_callable(self):
        provider = _ConcreteCacheProvider()
        result = provider.get("hash", "model")
        assert result is None

    def test_abstract_method_set_is_callable(self):
        provider = _ConcreteCacheProvider()
        result = provider.set("hash", [0.1, 0.2], "model")
        assert result is True

    def test_abstract_method_get_batch_is_callable(self):
        provider = _ConcreteCacheProvider()
        result = provider.get_batch(["h1", "h2"], "model")
        assert isinstance(result, dict)

    def test_abstract_method_set_batch_is_callable(self):
        provider = _ConcreteCacheProvider()
        result = provider.set_batch([("h1", [0.1])], "model")
        assert result == 0

    def test_abstract_method_delete_is_callable(self):
        provider = _ConcreteCacheProvider()
        result = provider.delete("hash", "model")
        assert result is False

    def test_abstract_method_clear_is_callable(self):
        provider = _ConcreteCacheProvider()
        result = provider.clear()
        assert result == 0

    def test_abstract_method_cleanup_is_callable(self):
        provider = _ConcreteCacheProvider()
        result = provider.cleanup()
        assert result == 0

    def test_abstract_method_cleanup_with_args(self):
        provider = _ConcreteCacheProvider()
        result = provider.cleanup(max_age_days=7, max_entries=100)
        assert result == 0

    def test_abstract_method_get_stats_returns_cache_stats(self):
        provider = _ConcreteCacheProvider()
        stats = provider.get_stats()
        assert isinstance(stats, CacheStats)

    def test_abstract_method_health_check_returns_bool(self):
        provider = _ConcreteCacheProvider()
        result = provider.health_check()
        assert isinstance(result, bool)

    def test_subclass_missing_one_method_cannot_instantiate(self):
        """A subclass that omits one abstract method stays abstract."""

        class _Incomplete(BaseCacheProvider):
            def get(self, text_hash, model):
                return None
            # missing set, get_batch, set_batch, delete, clear,
            # cleanup, get_stats, health_check

        with pytest.raises(TypeError):
            _Incomplete()

    def test_close_can_be_called_multiple_times(self):
        provider = _ConcreteCacheProvider()
        provider.close()
        provider.close()  # idempotent — must not raise

    def test_close_is_inherited_concrete_method(self):
        # BaseCacheProvider.close is defined directly on the class
        assert "close" in BaseCacheProvider.__dict__

    def test_get_batch_returns_dict(self):
        provider = _ConcreteCacheProvider()
        result = provider.get_batch([], "m")
        assert isinstance(result, dict)

    def test_set_batch_empty_list(self):
        provider = _ConcreteCacheProvider()
        result = provider.set_batch([], "m")
        assert result == 0
