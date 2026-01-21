"""
Cache provider factory.

Creates cache providers based on configuration and environment variables.
"""

import logging
import os
from typing import Optional

from rag.cache.base import BaseCacheProvider, CacheBackend, CacheConfig

logger = logging.getLogger(__name__)

# Global singleton instance
_cache_provider: Optional[BaseCacheProvider] = None


def get_cache_config_from_env() -> CacheConfig:
    """Get cache configuration from environment variables.

    Environment Variables:
        REDIS_URL: Redis connection URL (e.g., redis://localhost:6379)
        REDIS_PREFIX: Key prefix (default: medassist:embedding:)
        EMBEDDING_CACHE_BACKEND: Backend type (sqlite, redis, fallback, auto)
        EMBEDDING_CACHE_FALLBACK: Enable fallback mode (true/false)
        EMBEDDING_CACHE_MAX_ENTRIES: Maximum cache entries
        EMBEDDING_CACHE_MAX_AGE_DAYS: Maximum entry age

    Returns:
        CacheConfig populated from environment
    """
    # Get Redis URL
    redis_url = os.environ.get("REDIS_URL")

    # Get backend type
    backend_str = os.environ.get("EMBEDDING_CACHE_BACKEND", "auto").lower()
    if backend_str == "redis":
        backend = CacheBackend.REDIS
    elif backend_str == "sqlite":
        backend = CacheBackend.SQLITE
    elif backend_str == "fallback":
        backend = CacheBackend.FALLBACK
    else:
        backend = CacheBackend.AUTO

    # Get other settings
    redis_prefix = os.environ.get("REDIS_PREFIX", "medassist:embedding:")
    enable_fallback = os.environ.get("EMBEDDING_CACHE_FALLBACK", "true").lower() == "true"

    try:
        max_entries = int(os.environ.get("EMBEDDING_CACHE_MAX_ENTRIES", "10000"))
    except ValueError:
        max_entries = 10000

    try:
        max_age_days = int(os.environ.get("EMBEDDING_CACHE_MAX_AGE_DAYS", "30"))
    except ValueError:
        max_age_days = 30

    try:
        retry_seconds = int(os.environ.get("EMBEDDING_CACHE_RETRY_SECONDS", "60"))
    except ValueError:
        retry_seconds = 60

    return CacheConfig(
        backend=backend,
        redis_url=redis_url,
        redis_prefix=redis_prefix,
        max_entries=max_entries,
        max_age_days=max_age_days,
        enable_fallback=enable_fallback,
        retry_primary_seconds=retry_seconds,
    )


def create_cache_provider(config: Optional[CacheConfig] = None) -> BaseCacheProvider:
    """Create a cache provider based on configuration.

    Args:
        config: Cache configuration (default: from environment)

    Returns:
        Configured cache provider

    Raises:
        ValueError: If Redis requested but not available/configured
    """
    if config is None:
        config = get_cache_config_from_env()

    # Determine actual backend to use
    backend = config.backend

    if backend == CacheBackend.AUTO:
        # Auto-detect: use Redis if available and configured
        if config.redis_url:
            try:
                # Try to create Redis provider
                from rag.cache.redis_provider import RedisCacheProvider

                redis_provider = RedisCacheProvider(config)

                if config.enable_fallback:
                    # Create fallback with SQLite secondary
                    from rag.cache.sqlite_provider import SQLiteCacheProvider
                    from rag.cache.fallback_provider import FallbackCacheProvider

                    sqlite_provider = SQLiteCacheProvider(config)
                    provider = FallbackCacheProvider(
                        primary=redis_provider,
                        secondary=sqlite_provider,
                        retry_primary_seconds=config.retry_primary_seconds,
                    )
                    logger.info("Created fallback cache (Redis → SQLite)")
                    return provider
                else:
                    logger.info("Created Redis cache provider")
                    return redis_provider

            except ImportError:
                logger.warning("Redis package not installed, falling back to SQLite")
            except Exception as e:
                logger.warning(f"Failed to create Redis provider: {e}, falling back to SQLite")

        # Default to SQLite
        from rag.cache.sqlite_provider import SQLiteCacheProvider

        provider = SQLiteCacheProvider(config)
        logger.info("Created SQLite cache provider")
        return provider

    elif backend == CacheBackend.REDIS:
        from rag.cache.redis_provider import RedisCacheProvider

        if not config.redis_url:
            raise ValueError("REDIS_URL must be set for Redis backend")

        provider = RedisCacheProvider(config)
        logger.info("Created Redis cache provider")
        return provider

    elif backend == CacheBackend.FALLBACK:
        from rag.cache.redis_provider import RedisCacheProvider
        from rag.cache.sqlite_provider import SQLiteCacheProvider
        from rag.cache.fallback_provider import FallbackCacheProvider

        if not config.redis_url:
            raise ValueError("REDIS_URL must be set for fallback backend")

        try:
            redis_provider = RedisCacheProvider(config)
        except Exception as e:
            logger.warning(f"Redis unavailable: {e}, using SQLite only")
            return SQLiteCacheProvider(config)

        sqlite_provider = SQLiteCacheProvider(config)
        provider = FallbackCacheProvider(
            primary=redis_provider,
            secondary=sqlite_provider,
            retry_primary_seconds=config.retry_primary_seconds,
        )
        logger.info("Created fallback cache (Redis → SQLite)")
        return provider

    else:  # SQLITE
        from rag.cache.sqlite_provider import SQLiteCacheProvider

        provider = SQLiteCacheProvider(config)
        logger.info("Created SQLite cache provider")
        return provider


def get_cache_provider() -> BaseCacheProvider:
    """Get the global cache provider singleton.

    Creates the provider on first access based on environment configuration.

    Returns:
        BaseCacheProvider instance
    """
    global _cache_provider

    if _cache_provider is None:
        _cache_provider = create_cache_provider()

    return _cache_provider


def reset_cache_provider():
    """Reset the global cache provider.

    Closes any open connections and clears the singleton.
    Useful for testing or reconfiguration.
    """
    global _cache_provider

    if _cache_provider is not None:
        try:
            _cache_provider.close()
        except Exception as e:
            logger.warning(f"Error closing cache provider: {e}")
        _cache_provider = None
