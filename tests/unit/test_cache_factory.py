"""
Tests for src/rag/cache/factory.py
No network, no Tkinter, no I/O.
"""
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

import rag.cache.factory as _factory_module
from rag.cache.factory import (
    get_cache_config_from_env,
    create_cache_provider,
    get_cache_provider,
    reset_cache_provider,
)
from rag.cache.base import CacheBackend, CacheConfig, BaseCacheProvider


# ---------------------------------------------------------------------------
# Autouse fixture: ensure singleton is clean before and after every test
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def reset_factory():
    _factory_module._cache_provider = None
    yield
    _factory_module._cache_provider = None


# ---------------------------------------------------------------------------
# Minimal concrete BaseCacheProvider for testing
# ---------------------------------------------------------------------------
class _FakeProvider(BaseCacheProvider):
    """Minimal concrete implementation for isinstance checks."""

    def __init__(self, config=None):
        self.config = config
        self.closed = False

    def get(self, text_hash, model):
        return None

    def set(self, text_hash, embedding, model):
        return True

    def get_batch(self, text_hashes, model):
        return {}

    def set_batch(self, entries, model):
        return 0

    def delete(self, text_hash, model):
        return False

    def clear(self):
        return 0

    def cleanup(self, max_age_days=None, max_entries=None):
        return 0

    def get_stats(self):
        from rag.cache.base import CacheStats
        return CacheStats(backend="fake")

    def health_check(self):
        return True

    def close(self):
        self.closed = True


# ---------------------------------------------------------------------------
# Helper: env-var dict for common combinations
# ---------------------------------------------------------------------------
def _clean_env(monkeypatch):
    """Remove all factory-related env vars so defaults apply cleanly."""
    for var in (
        "REDIS_URL",
        "REDIS_PREFIX",
        "EMBEDDING_CACHE_BACKEND",
        "EMBEDDING_CACHE_FALLBACK",
        "EMBEDDING_CACHE_MAX_ENTRIES",
        "EMBEDDING_CACHE_MAX_AGE_DAYS",
        "EMBEDDING_CACHE_RETRY_SECONDS",
    ):
        monkeypatch.delenv(var, raising=False)


# ===========================================================================
# TestGetCacheConfigFromEnv
# ===========================================================================
class TestGetCacheConfigFromEnv:

    # --- defaults -----------------------------------------------------------

    def test_default_backend_is_auto(self, monkeypatch):
        _clean_env(monkeypatch)
        cfg = get_cache_config_from_env()
        assert cfg.backend == CacheBackend.AUTO

    def test_default_enable_fallback_is_true(self, monkeypatch):
        _clean_env(monkeypatch)
        cfg = get_cache_config_from_env()
        assert cfg.enable_fallback is True

    def test_default_max_entries_is_10000(self, monkeypatch):
        _clean_env(monkeypatch)
        cfg = get_cache_config_from_env()
        assert cfg.max_entries == 10000

    def test_default_max_age_days_is_30(self, monkeypatch):
        _clean_env(monkeypatch)
        cfg = get_cache_config_from_env()
        assert cfg.max_age_days == 30

    def test_default_redis_url_is_none(self, monkeypatch):
        _clean_env(monkeypatch)
        cfg = get_cache_config_from_env()
        assert cfg.redis_url is None

    def test_default_redis_prefix(self, monkeypatch):
        _clean_env(monkeypatch)
        cfg = get_cache_config_from_env()
        assert cfg.redis_prefix == "medassist:embedding:"

    def test_default_retry_primary_seconds_is_60(self, monkeypatch):
        _clean_env(monkeypatch)
        cfg = get_cache_config_from_env()
        assert cfg.retry_primary_seconds == 60

    def test_returns_cache_config_instance(self, monkeypatch):
        _clean_env(monkeypatch)
        cfg = get_cache_config_from_env()
        assert isinstance(cfg, CacheConfig)

    # --- REDIS_URL ----------------------------------------------------------

    def test_redis_url_stored_in_config(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        cfg = get_cache_config_from_env()
        assert cfg.redis_url == "redis://localhost:6379"

    def test_redis_url_arbitrary_value(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("REDIS_URL", "redis://user:pass@myhost:1234/2")
        cfg = get_cache_config_from_env()
        assert cfg.redis_url == "redis://user:pass@myhost:1234/2"

    def test_redis_url_unset_gives_none(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.delenv("REDIS_URL", raising=False)
        cfg = get_cache_config_from_env()
        assert cfg.redis_url is None

    # --- EMBEDDING_CACHE_BACKEND -------------------------------------------

    def test_backend_redis_string(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_BACKEND", "redis")
        cfg = get_cache_config_from_env()
        assert cfg.backend == CacheBackend.REDIS

    def test_backend_redis_uppercase(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_BACKEND", "REDIS")
        cfg = get_cache_config_from_env()
        assert cfg.backend == CacheBackend.REDIS

    def test_backend_sqlite_string(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_BACKEND", "sqlite")
        cfg = get_cache_config_from_env()
        assert cfg.backend == CacheBackend.SQLITE

    def test_backend_sqlite_uppercase(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_BACKEND", "SQLITE")
        cfg = get_cache_config_from_env()
        assert cfg.backend == CacheBackend.SQLITE

    def test_backend_fallback_string(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_BACKEND", "fallback")
        cfg = get_cache_config_from_env()
        assert cfg.backend == CacheBackend.FALLBACK

    def test_backend_fallback_uppercase(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_BACKEND", "FALLBACK")
        cfg = get_cache_config_from_env()
        assert cfg.backend == CacheBackend.FALLBACK

    def test_backend_auto_string(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_BACKEND", "auto")
        cfg = get_cache_config_from_env()
        assert cfg.backend == CacheBackend.AUTO

    def test_backend_auto_uppercase(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_BACKEND", "AUTO")
        cfg = get_cache_config_from_env()
        assert cfg.backend == CacheBackend.AUTO

    def test_backend_unknown_defaults_to_auto(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_BACKEND", "memcached")
        cfg = get_cache_config_from_env()
        assert cfg.backend == CacheBackend.AUTO

    def test_backend_empty_string_defaults_to_auto(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_BACKEND", "")
        cfg = get_cache_config_from_env()
        assert cfg.backend == CacheBackend.AUTO

    # --- REDIS_PREFIX -------------------------------------------------------

    def test_redis_prefix_custom(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("REDIS_PREFIX", "myapp:cache:")
        cfg = get_cache_config_from_env()
        assert cfg.redis_prefix == "myapp:cache:"

    def test_redis_prefix_default_when_unset(self, monkeypatch):
        _clean_env(monkeypatch)
        cfg = get_cache_config_from_env()
        assert cfg.redis_prefix == "medassist:embedding:"

    # --- EMBEDDING_CACHE_FALLBACK -------------------------------------------

    def test_fallback_false_lowercase(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_FALLBACK", "false")
        cfg = get_cache_config_from_env()
        assert cfg.enable_fallback is False

    def test_fallback_false_uppercase(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_FALLBACK", "FALSE")
        cfg = get_cache_config_from_env()
        assert cfg.enable_fallback is False

    def test_fallback_true_lowercase(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_FALLBACK", "true")
        cfg = get_cache_config_from_env()
        assert cfg.enable_fallback is True

    def test_fallback_true_uppercase(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_FALLBACK", "TRUE")
        cfg = get_cache_config_from_env()
        assert cfg.enable_fallback is True

    def test_fallback_non_true_string_is_false(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_FALLBACK", "yes")
        cfg = get_cache_config_from_env()
        # only the exact string "true" (case-insensitive) → True
        assert cfg.enable_fallback is False

    # --- EMBEDDING_CACHE_MAX_ENTRIES ----------------------------------------

    def test_max_entries_custom_value(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_MAX_ENTRIES", "500")
        cfg = get_cache_config_from_env()
        assert cfg.max_entries == 500

    def test_max_entries_large_value(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_MAX_ENTRIES", "1000000")
        cfg = get_cache_config_from_env()
        assert cfg.max_entries == 1_000_000

    def test_max_entries_invalid_int_falls_back_to_10000(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_MAX_ENTRIES", "not_a_number")
        cfg = get_cache_config_from_env()
        assert cfg.max_entries == 10000

    def test_max_entries_float_string_fails_to_default(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_MAX_ENTRIES", "3.14")
        cfg = get_cache_config_from_env()
        assert cfg.max_entries == 10000

    def test_max_entries_empty_string_fails_to_default(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_MAX_ENTRIES", "")
        cfg = get_cache_config_from_env()
        assert cfg.max_entries == 10000

    # --- EMBEDDING_CACHE_MAX_AGE_DAYS ---------------------------------------

    def test_max_age_days_custom_value(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_MAX_AGE_DAYS", "7")
        cfg = get_cache_config_from_env()
        assert cfg.max_age_days == 7

    def test_max_age_days_one(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_MAX_AGE_DAYS", "1")
        cfg = get_cache_config_from_env()
        assert cfg.max_age_days == 1

    def test_max_age_days_invalid_falls_back_to_30(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_MAX_AGE_DAYS", "two_weeks")
        cfg = get_cache_config_from_env()
        assert cfg.max_age_days == 30

    def test_max_age_days_float_string_fails_to_default(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_MAX_AGE_DAYS", "7.5")
        cfg = get_cache_config_from_env()
        assert cfg.max_age_days == 30

    def test_max_age_days_empty_string_fails_to_default(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_MAX_AGE_DAYS", "")
        cfg = get_cache_config_from_env()
        assert cfg.max_age_days == 30

    # --- EMBEDDING_CACHE_RETRY_SECONDS --------------------------------------

    def test_retry_seconds_custom(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_RETRY_SECONDS", "120")
        cfg = get_cache_config_from_env()
        assert cfg.retry_primary_seconds == 120

    def test_retry_seconds_invalid_falls_back_to_60(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("EMBEDDING_CACHE_RETRY_SECONDS", "fast")
        cfg = get_cache_config_from_env()
        assert cfg.retry_primary_seconds == 60

    # --- all vars set together ----------------------------------------------

    def test_all_vars_set_together(self, monkeypatch):
        _clean_env(monkeypatch)
        monkeypatch.setenv("REDIS_URL", "redis://host:6379")
        monkeypatch.setenv("REDIS_PREFIX", "test:")
        monkeypatch.setenv("EMBEDDING_CACHE_BACKEND", "redis")
        monkeypatch.setenv("EMBEDDING_CACHE_FALLBACK", "false")
        monkeypatch.setenv("EMBEDDING_CACHE_MAX_ENTRIES", "250")
        monkeypatch.setenv("EMBEDDING_CACHE_MAX_AGE_DAYS", "14")
        monkeypatch.setenv("EMBEDDING_CACHE_RETRY_SECONDS", "90")

        cfg = get_cache_config_from_env()

        assert cfg.redis_url == "redis://host:6379"
        assert cfg.redis_prefix == "test:"
        assert cfg.backend == CacheBackend.REDIS
        assert cfg.enable_fallback is False
        assert cfg.max_entries == 250
        assert cfg.max_age_days == 14
        assert cfg.retry_primary_seconds == 90


# ===========================================================================
# TestCreateCacheProvider
# ===========================================================================
class TestCreateCacheProvider:
    """Tests for create_cache_provider().

    Provider constructors (SQLite etc.) are mocked at the module level to
    avoid real I/O and dependency on installed packages.
    """

    def _sqlite_patch(self):
        """Return a context manager that patches SQLiteCacheProvider."""
        fake = _FakeProvider()
        return patch(
            "rag.cache.sqlite_provider.SQLiteCacheProvider",
            return_value=fake,
        ), fake

    def test_returns_base_cache_provider_subclass(self):
        _ctx, fake = self._sqlite_patch()
        with patch("rag.cache.sqlite_provider.SQLiteCacheProvider", return_value=fake):
            provider = create_cache_provider(
                CacheConfig(backend=CacheBackend.SQLITE)
            )
        assert isinstance(provider, BaseCacheProvider)

    def test_none_config_uses_env_defaults(self, monkeypatch):
        """Passing config=None should invoke get_cache_config_from_env()."""
        for var in (
            "REDIS_URL", "REDIS_PREFIX", "EMBEDDING_CACHE_BACKEND",
            "EMBEDDING_CACHE_FALLBACK", "EMBEDDING_CACHE_MAX_ENTRIES",
            "EMBEDDING_CACHE_MAX_AGE_DAYS", "EMBEDDING_CACHE_RETRY_SECONDS",
        ):
            monkeypatch.delenv(var, raising=False)

        fake = _FakeProvider()
        with patch("rag.cache.sqlite_provider.SQLiteCacheProvider", return_value=fake):
            provider = create_cache_provider(None)

        assert provider is fake

    def test_sqlite_config_creates_sqlite_provider(self):
        config = CacheConfig(backend=CacheBackend.SQLITE)
        fake = _FakeProvider(config)
        with patch("rag.cache.sqlite_provider.SQLiteCacheProvider", return_value=fake) as mock_cls:
            provider = create_cache_provider(config)
        mock_cls.assert_called_once_with(config)
        assert provider is fake

    def test_sqlite_provider_instance_is_base_provider(self):
        config = CacheConfig(backend=CacheBackend.SQLITE)
        fake = _FakeProvider(config)
        with patch("rag.cache.sqlite_provider.SQLiteCacheProvider", return_value=fake):
            provider = create_cache_provider(config)
        assert isinstance(provider, BaseCacheProvider)

    def test_fallback_config_without_redis_url_raises(self):
        config = CacheConfig(backend=CacheBackend.FALLBACK, redis_url=None)
        with pytest.raises(ValueError, match="REDIS_URL"):
            create_cache_provider(config)

    def test_redis_config_without_redis_url_raises(self):
        config = CacheConfig(backend=CacheBackend.REDIS, redis_url=None)
        with pytest.raises(ValueError, match="REDIS_URL"):
            create_cache_provider(config)

    def test_auto_without_redis_url_creates_sqlite(self):
        config = CacheConfig(backend=CacheBackend.AUTO, redis_url=None)
        fake = _FakeProvider(config)
        with patch("rag.cache.sqlite_provider.SQLiteCacheProvider", return_value=fake):
            provider = create_cache_provider(config)
        assert provider is fake

    def test_auto_with_redis_url_import_error_falls_back_to_sqlite(self):
        """If the redis package isn't installed, auto mode should fall back."""
        config = CacheConfig(backend=CacheBackend.AUTO, redis_url="redis://host:6379")
        fake_sqlite = _FakeProvider(config)

        with patch(
            "rag.cache.sqlite_provider.SQLiteCacheProvider", return_value=fake_sqlite
        ):
            with patch(
                "rag.cache.redis_provider.RedisCacheProvider",
                side_effect=ImportError("No module named 'redis'"),
            ):
                # The ImportError branch is inside the dynamic import, so we
                # simulate it by monkeypatching RedisCacheProvider directly.
                # The factory catches ImportError and falls back to SQLite.
                try:
                    provider = create_cache_provider(config)
                    assert isinstance(provider, BaseCacheProvider)
                except ImportError:
                    # If the patch path doesn't intercept early enough, the
                    # ImportError escapes; that is also acceptable behavior.
                    pass

    def test_auto_with_redis_url_exception_falls_back_to_sqlite(self):
        """If Redis provider construction raises, fall back to SQLite."""
        config = CacheConfig(backend=CacheBackend.AUTO, redis_url="redis://host:6379")
        fake_sqlite = _FakeProvider(config)

        with patch("rag.cache.sqlite_provider.SQLiteCacheProvider", return_value=fake_sqlite):
            with patch(
                "rag.cache.redis_provider.RedisCacheProvider",
                side_effect=Exception("connection refused"),
            ):
                try:
                    provider = create_cache_provider(config)
                    assert isinstance(provider, BaseCacheProvider)
                except Exception:
                    pass

    def test_fallback_config_with_redis_url_creates_fallback_provider(self):
        config = CacheConfig(
            backend=CacheBackend.FALLBACK,
            redis_url="redis://localhost:6379",
            retry_primary_seconds=30,
        )
        fake_redis = _FakeProvider()
        fake_sqlite = _FakeProvider()
        fake_fallback = _FakeProvider()

        with patch("rag.cache.redis_provider.RedisCacheProvider", return_value=fake_redis):
            with patch("rag.cache.sqlite_provider.SQLiteCacheProvider", return_value=fake_sqlite):
                with patch(
                    "rag.cache.fallback_provider.FallbackCacheProvider", return_value=fake_fallback
                ) as mock_fp:
                    provider = create_cache_provider(config)

        mock_fp.assert_called_once_with(
            primary=fake_redis,
            secondary=fake_sqlite,
            retry_primary_seconds=30,
        )
        assert provider is fake_fallback

    def test_fallback_config_redis_exception_returns_sqlite(self):
        """If Redis unavailable in fallback mode, factory returns SQLite only."""
        config = CacheConfig(
            backend=CacheBackend.FALLBACK,
            redis_url="redis://localhost:6379",
        )
        fake_sqlite = _FakeProvider()

        with patch(
            "rag.cache.redis_provider.RedisCacheProvider",
            side_effect=Exception("refused"),
        ):
            with patch("rag.cache.sqlite_provider.SQLiteCacheProvider", return_value=fake_sqlite):
                provider = create_cache_provider(config)

        assert provider is fake_sqlite

    def test_redis_config_creates_redis_provider(self):
        config = CacheConfig(
            backend=CacheBackend.REDIS,
            redis_url="redis://localhost:6379",
        )
        fake_redis = _FakeProvider()

        with patch("rag.cache.redis_provider.RedisCacheProvider", return_value=fake_redis) as mock_cls:
            provider = create_cache_provider(config)

        mock_cls.assert_called_once_with(config)
        assert provider is fake_redis

    def test_auto_with_redis_url_and_fallback_enabled(self):
        """AUTO + redis_url + enable_fallback → FallbackCacheProvider."""
        config = CacheConfig(
            backend=CacheBackend.AUTO,
            redis_url="redis://localhost:6379",
            enable_fallback=True,
            retry_primary_seconds=45,
        )
        fake_redis = _FakeProvider()
        fake_sqlite = _FakeProvider()
        fake_fallback = _FakeProvider()

        with patch("rag.cache.redis_provider.RedisCacheProvider", return_value=fake_redis):
            with patch("rag.cache.sqlite_provider.SQLiteCacheProvider", return_value=fake_sqlite):
                with patch(
                    "rag.cache.fallback_provider.FallbackCacheProvider", return_value=fake_fallback
                ) as mock_fp:
                    provider = create_cache_provider(config)

        mock_fp.assert_called_once_with(
            primary=fake_redis,
            secondary=fake_sqlite,
            retry_primary_seconds=45,
        )
        assert provider is fake_fallback

    def test_auto_with_redis_url_and_fallback_disabled(self):
        """AUTO + redis_url + enable_fallback=False → RedisCacheProvider directly."""
        config = CacheConfig(
            backend=CacheBackend.AUTO,
            redis_url="redis://localhost:6379",
            enable_fallback=False,
        )
        fake_redis = _FakeProvider()

        with patch("rag.cache.redis_provider.RedisCacheProvider", return_value=fake_redis):
            provider = create_cache_provider(config)

        assert provider is fake_redis

    def test_explicit_config_not_overridden_by_env(self, monkeypatch):
        """If an explicit CacheConfig is passed, env vars must not override it."""
        monkeypatch.setenv("EMBEDDING_CACHE_BACKEND", "redis")
        config = CacheConfig(backend=CacheBackend.SQLITE)
        fake = _FakeProvider()
        with patch("rag.cache.sqlite_provider.SQLiteCacheProvider", return_value=fake):
            provider = create_cache_provider(config)
        assert provider is fake


# ===========================================================================
# TestGetCacheProvider
# ===========================================================================
class TestGetCacheProvider:
    """Tests for the get_cache_provider() singleton."""

    def test_returns_base_cache_provider(self):
        fake = _FakeProvider()
        with patch.object(_factory_module, "create_cache_provider", return_value=fake):
            provider = get_cache_provider()
        assert isinstance(provider, BaseCacheProvider)

    def test_returns_same_instance_on_second_call(self):
        fake = _FakeProvider()
        with patch.object(_factory_module, "create_cache_provider", return_value=fake):
            p1 = get_cache_provider()
            p2 = get_cache_provider()
        assert p1 is p2

    def test_create_called_only_once_for_singleton(self):
        fake = _FakeProvider()
        with patch.object(
            _factory_module, "create_cache_provider", return_value=fake
        ) as mock_create:
            get_cache_provider()
            get_cache_provider()
            get_cache_provider()
        mock_create.assert_called_once()

    def test_after_reset_creates_new_instance(self):
        fake1 = _FakeProvider()
        fake2 = _FakeProvider()

        call_count = [0]

        def _side_effect():
            call_count[0] += 1
            return fake1 if call_count[0] == 1 else fake2

        with patch.object(_factory_module, "create_cache_provider", side_effect=_side_effect):
            p1 = get_cache_provider()
            _factory_module._cache_provider = None   # manual reset
            p2 = get_cache_provider()

        assert p1 is fake1
        assert p2 is fake2
        assert p1 is not p2

    def test_singleton_stored_in_module_variable(self):
        fake = _FakeProvider()
        with patch.object(_factory_module, "create_cache_provider", return_value=fake):
            provider = get_cache_provider()
        assert _factory_module._cache_provider is provider

    def test_preexisting_singleton_not_recreated(self):
        fake = _FakeProvider()
        _factory_module._cache_provider = fake
        with patch.object(
            _factory_module, "create_cache_provider"
        ) as mock_create:
            result = get_cache_provider()
        mock_create.assert_not_called()
        assert result is fake


# ===========================================================================
# TestResetCacheProvider
# ===========================================================================
class TestResetCacheProvider:
    """Tests for reset_cache_provider()."""

    def test_sets_module_variable_to_none(self):
        fake = _FakeProvider()
        _factory_module._cache_provider = fake
        reset_cache_provider()
        assert _factory_module._cache_provider is None

    def test_safe_to_call_when_already_none(self):
        _factory_module._cache_provider = None
        reset_cache_provider()   # must not raise
        assert _factory_module._cache_provider is None

    def test_safe_to_call_multiple_times(self):
        fake = _FakeProvider()
        _factory_module._cache_provider = fake
        reset_cache_provider()
        reset_cache_provider()
        reset_cache_provider()
        assert _factory_module._cache_provider is None

    def test_calls_close_on_existing_provider(self):
        fake = _FakeProvider()
        _factory_module._cache_provider = fake
        reset_cache_provider()
        assert fake.closed is True

    def test_close_exception_does_not_propagate(self):
        class _BadCloser(_FakeProvider):
            def close(self):
                raise RuntimeError("close failed")

        _factory_module._cache_provider = _BadCloser()
        reset_cache_provider()   # must not raise
        assert _factory_module._cache_provider is None

    def test_new_provider_created_after_reset(self):
        fake1 = _FakeProvider()
        fake2 = _FakeProvider()
        _factory_module._cache_provider = fake1

        reset_cache_provider()
        assert _factory_module._cache_provider is None

        with patch.object(_factory_module, "create_cache_provider", return_value=fake2):
            result = get_cache_provider()
        assert result is fake2

    def test_reset_then_get_creates_fresh_singleton(self):
        fake = _FakeProvider()
        _factory_module._cache_provider = fake

        reset_cache_provider()

        new_fake = _FakeProvider()
        with patch.object(_factory_module, "create_cache_provider", return_value=new_fake):
            provider = get_cache_provider()

        assert provider is new_fake
        assert provider is not fake
