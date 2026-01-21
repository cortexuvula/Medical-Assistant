"""
Fallback cache provider with Redis primary and SQLite backup.

Provides resilient caching by automatically falling back to SQLite
when Redis is unavailable.
"""

import logging
import threading
import time
from datetime import datetime
from typing import Optional

from rag.cache.base import BaseCacheProvider, CacheConfig, CacheStats

logger = logging.getLogger(__name__)


class FallbackCacheProvider(BaseCacheProvider):
    """Cache provider with automatic fallback.

    Features:
    - Primary provider (Redis) with automatic fallback to secondary (SQLite)
    - Periodic retry of primary provider
    - Transparent operation - callers don't need to handle failures
    - Stats tracking for both providers
    """

    def __init__(
        self,
        primary: BaseCacheProvider,
        secondary: BaseCacheProvider,
        retry_primary_seconds: int = 60,
    ):
        """Initialize fallback provider.

        Args:
            primary: Primary cache provider (typically Redis)
            secondary: Fallback cache provider (typically SQLite)
            retry_primary_seconds: Interval to retry primary after failure
        """
        self._primary = primary
        self._secondary = secondary
        self._retry_interval = retry_primary_seconds
        self._using_primary = True
        self._last_primary_failure: Optional[float] = None
        self._lock = threading.Lock()

        # Test primary on startup
        if not self._primary.health_check():
            logger.warning("Primary cache unavailable, using fallback")
            self._using_primary = False
            self._last_primary_failure = time.time()

    def _get_provider(self) -> BaseCacheProvider:
        """Get current active provider, trying to restore primary if needed."""
        with self._lock:
            if self._using_primary:
                return self._primary

            # Check if we should retry primary
            if self._last_primary_failure:
                elapsed = time.time() - self._last_primary_failure
                if elapsed >= self._retry_interval:
                    try:
                        if self._primary.health_check():
                            logger.info("Primary cache restored")
                            self._using_primary = True
                            self._last_primary_failure = None
                            return self._primary
                    except Exception:
                        pass
                    # Update failure time for next retry
                    self._last_primary_failure = time.time()

            return self._secondary

    def _switch_to_secondary(self, error: Exception):
        """Switch to secondary provider after primary failure."""
        with self._lock:
            if self._using_primary:
                logger.warning(f"Primary cache failed: {error}, switching to fallback")
                self._using_primary = False
                self._last_primary_failure = time.time()

    def get(self, text_hash: str, model: str) -> Optional[list[float]]:
        """Get a cached embedding."""
        provider = self._get_provider()

        try:
            result = provider.get(text_hash, model)
            return result
        except Exception as e:
            if provider is self._primary:
                self._switch_to_secondary(e)
                # Retry with secondary
                try:
                    return self._secondary.get(text_hash, model)
                except Exception:
                    pass
            return None

    def set(self, text_hash: str, embedding: list[float], model: str) -> bool:
        """Cache an embedding."""
        provider = self._get_provider()

        try:
            result = provider.set(text_hash, embedding, model)

            # If using secondary, also try to update primary for consistency
            if provider is self._secondary and self._using_primary:
                try:
                    self._primary.set(text_hash, embedding, model)
                except Exception:
                    pass

            return result
        except Exception as e:
            if provider is self._primary:
                self._switch_to_secondary(e)
                try:
                    return self._secondary.set(text_hash, embedding, model)
                except Exception:
                    pass
            return False

    def get_batch(
        self,
        text_hashes: list[str],
        model: str,
    ) -> dict[str, list[float]]:
        """Get multiple cached embeddings."""
        provider = self._get_provider()

        try:
            return provider.get_batch(text_hashes, model)
        except Exception as e:
            if provider is self._primary:
                self._switch_to_secondary(e)
                try:
                    return self._secondary.get_batch(text_hashes, model)
                except Exception:
                    pass
            return {}

    def set_batch(
        self,
        entries: list[tuple[str, list[float]]],
        model: str,
    ) -> int:
        """Cache multiple embeddings."""
        provider = self._get_provider()

        try:
            result = provider.set_batch(entries, model)

            # If using secondary, also try to update primary
            if provider is self._secondary and self._using_primary:
                try:
                    self._primary.set_batch(entries, model)
                except Exception:
                    pass

            return result
        except Exception as e:
            if provider is self._primary:
                self._switch_to_secondary(e)
                try:
                    return self._secondary.set_batch(entries, model)
                except Exception:
                    pass
            return 0

    def delete(self, text_hash: str, model: str) -> bool:
        """Delete a cached embedding."""
        provider = self._get_provider()

        try:
            result = provider.delete(text_hash, model)

            # Also delete from both providers for consistency
            if provider is self._primary:
                try:
                    self._secondary.delete(text_hash, model)
                except Exception:
                    pass
            else:
                try:
                    self._primary.delete(text_hash, model)
                except Exception:
                    pass

            return result
        except Exception as e:
            if provider is self._primary:
                self._switch_to_secondary(e)
                try:
                    return self._secondary.delete(text_hash, model)
                except Exception:
                    pass
            return False

    def clear(self) -> int:
        """Clear all cached embeddings."""
        total = 0

        # Clear both providers
        try:
            total += self._primary.clear()
        except Exception as e:
            logger.warning(f"Failed to clear primary cache: {e}")

        try:
            total += self._secondary.clear()
        except Exception as e:
            logger.warning(f"Failed to clear secondary cache: {e}")

        return total

    def cleanup(
        self,
        max_age_days: Optional[int] = None,
        max_entries: Optional[int] = None,
    ) -> int:
        """Clean up old or excess cache entries."""
        total = 0

        # Cleanup both providers
        try:
            total += self._primary.cleanup(max_age_days, max_entries)
        except Exception as e:
            logger.warning(f"Failed to cleanup primary cache: {e}")

        try:
            total += self._secondary.cleanup(max_age_days, max_entries)
        except Exception as e:
            logger.warning(f"Failed to cleanup secondary cache: {e}")

        return total

    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        with self._lock:
            using_primary = self._using_primary

        if using_primary:
            stats = self._primary.get_stats()
            stats.extra_info["fallback_mode"] = False
            stats.extra_info["fallback_backend"] = "sqlite"
        else:
            stats = self._secondary.get_stats()
            stats.extra_info["fallback_mode"] = True
            stats.extra_info["primary_backend"] = "redis"

            # Include when primary might be retried
            if self._last_primary_failure:
                next_retry = self._last_primary_failure + self._retry_interval
                stats.extra_info["next_primary_retry"] = datetime.fromtimestamp(
                    next_retry
                ).isoformat()

        stats.backend = f"fallback ({'primary' if using_primary else 'secondary'})"
        return stats

    def health_check(self) -> bool:
        """Check if at least one cache is operational."""
        # At least one must be healthy
        primary_healthy = False
        secondary_healthy = False

        try:
            primary_healthy = self._primary.health_check()
        except Exception:
            pass

        try:
            secondary_healthy = self._secondary.health_check()
        except Exception:
            pass

        return primary_healthy or secondary_healthy

    def close(self):
        """Close both cache providers."""
        try:
            self._primary.close()
        except Exception:
            pass

        try:
            self._secondary.close()
        except Exception:
            pass
