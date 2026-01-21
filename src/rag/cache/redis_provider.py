"""
Redis cache provider for embeddings.

Provides distributed multi-user caching using Redis.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from rag.cache.base import BaseCacheProvider, CacheConfig, CacheStats

logger = logging.getLogger(__name__)

# Optional Redis import
try:
    import redis
    from redis import ConnectionPool

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None
    ConnectionPool = None


class RedisCacheProvider(BaseCacheProvider):
    """Redis-based embedding cache provider.

    Features:
    - Distributed caching for multi-user scenarios
    - Connection pooling for efficiency
    - LRU tracking via sorted sets
    - Configurable key prefix and TTL
    - Automatic reconnection handling
    """

    # Key version for cache invalidation
    KEY_VERSION = "v1"

    # LRU tracking sorted set suffix
    LRU_SET_SUFFIX = ":lru"

    def __init__(self, config: CacheConfig):
        """Initialize Redis cache provider.

        Args:
            config: Cache configuration

        Raises:
            ImportError: If redis package not installed
            ValueError: If redis_url not provided
        """
        if not REDIS_AVAILABLE:
            raise ImportError(
                "Redis package not installed. "
                "Install with: pip install redis>=4.0.0"
            )

        if not config.redis_url:
            raise ValueError("redis_url must be provided for Redis cache")

        self._config = config
        self._prefix = config.redis_prefix
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[redis.Redis] = None

        # Stats tracking
        self._hit_count = 0
        self._miss_count = 0

        # Initialize connection
        self._init_connection()

    def _init_connection(self):
        """Initialize Redis connection pool."""
        try:
            self._pool = ConnectionPool.from_url(
                self._config.redis_url,
                max_connections=10,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
                retry_on_timeout=True,
            )
            self._client = redis.Redis(connection_pool=self._pool)

            # Test connection
            self._client.ping()
            logger.info(f"Connected to Redis at {self._config.redis_url}")

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    def _get_client(self) -> redis.Redis:
        """Get Redis client, reconnecting if needed."""
        if self._client is None:
            self._init_connection()
        return self._client

    def _make_key(self, text_hash: str, model: str) -> str:
        """Create Redis key from hash and model.

        Format: {prefix}{version}:{model}:{text_hash}
        """
        return f"{self._prefix}{self.KEY_VERSION}:{model}:{text_hash}"

    def _make_lru_key(self, model: str) -> str:
        """Create LRU sorted set key for a model."""
        return f"{self._prefix}{self.KEY_VERSION}:{model}{self.LRU_SET_SUFFIX}"

    def get(self, text_hash: str, model: str) -> Optional[list[float]]:
        """Get a cached embedding."""
        try:
            client = self._get_client()
            key = self._make_key(text_hash, model)

            data = client.get(key)

            if data:
                # Update LRU timestamp
                lru_key = self._make_lru_key(model)
                client.zadd(lru_key, {text_hash: time.time()})

                self._hit_count += 1
                return json.loads(data)
            else:
                self._miss_count += 1
                return None

        except Exception as e:
            logger.error(f"Redis get failed: {e}")
            self._miss_count += 1
            return None

    def set(self, text_hash: str, embedding: list[float], model: str) -> bool:
        """Cache an embedding."""
        try:
            client = self._get_client()
            key = self._make_key(text_hash, model)

            # Calculate TTL from max_age_days
            ttl_seconds = self._config.max_age_days * 24 * 60 * 60

            # Store embedding with TTL
            embedding_json = json.dumps(embedding)
            client.setex(key, ttl_seconds, embedding_json)

            # Update LRU tracking
            lru_key = self._make_lru_key(model)
            client.zadd(lru_key, {text_hash: time.time()})

            return True

        except Exception as e:
            logger.error(f"Redis set failed: {e}")
            return False

    def get_batch(
        self,
        text_hashes: list[str],
        model: str,
    ) -> dict[str, list[float]]:
        """Get multiple cached embeddings."""
        if not text_hashes:
            return {}

        try:
            client = self._get_client()
            keys = [self._make_key(h, model) for h in text_hashes]

            # Use pipeline for batch get
            pipe = client.pipeline()
            for key in keys:
                pipe.get(key)
            values = pipe.execute()

            results = {}
            found_hashes = []

            for text_hash, value in zip(text_hashes, values):
                if value:
                    results[text_hash] = json.loads(value)
                    found_hashes.append(text_hash)

            # Update LRU for found entries
            if found_hashes:
                lru_key = self._make_lru_key(model)
                now = time.time()
                client.zadd(lru_key, {h: now for h in found_hashes})

            # Update stats
            self._hit_count += len(results)
            self._miss_count += len(text_hashes) - len(results)

            return results

        except Exception as e:
            logger.error(f"Redis batch get failed: {e}")
            self._miss_count += len(text_hashes)
            return {}

    def set_batch(
        self,
        entries: list[tuple[str, list[float]]],
        model: str,
    ) -> int:
        """Cache multiple embeddings."""
        if not entries:
            return 0

        try:
            client = self._get_client()
            ttl_seconds = self._config.max_age_days * 24 * 60 * 60

            # Use pipeline for batch set
            pipe = client.pipeline()
            lru_updates = {}
            now = time.time()

            for text_hash, embedding in entries:
                key = self._make_key(text_hash, model)
                embedding_json = json.dumps(embedding)
                pipe.setex(key, ttl_seconds, embedding_json)
                lru_updates[text_hash] = now

            pipe.execute()

            # Update LRU tracking
            lru_key = self._make_lru_key(model)
            client.zadd(lru_key, lru_updates)

            return len(entries)

        except Exception as e:
            logger.error(f"Redis batch set failed: {e}")
            return 0

    def delete(self, text_hash: str, model: str) -> bool:
        """Delete a cached embedding."""
        try:
            client = self._get_client()
            key = self._make_key(text_hash, model)

            deleted = client.delete(key)

            # Remove from LRU tracking
            lru_key = self._make_lru_key(model)
            client.zrem(lru_key, text_hash)

            return deleted > 0

        except Exception as e:
            logger.error(f"Redis delete failed: {e}")
            return False

    def clear(self) -> int:
        """Clear all cached embeddings."""
        try:
            client = self._get_client()

            # Find all keys with our prefix
            pattern = f"{self._prefix}*"
            keys = list(client.scan_iter(pattern))

            if keys:
                client.delete(*keys)

            # Reset stats
            self._hit_count = 0
            self._miss_count = 0

            logger.info(f"Cleared {len(keys)} cache entries from Redis")
            return len(keys)

        except Exception as e:
            logger.error(f"Redis clear failed: {e}")
            return 0

    def cleanup(
        self,
        max_age_days: Optional[int] = None,
        max_entries: Optional[int] = None,
    ) -> int:
        """Clean up old or excess cache entries.

        Note: Redis TTL handles age-based expiration automatically.
        This method primarily handles max_entries enforcement.
        """
        max_entries = max_entries or self._config.max_entries
        removed = 0

        try:
            client = self._get_client()

            # Find all LRU tracking sets
            pattern = f"{self._prefix}{self.KEY_VERSION}:*{self.LRU_SET_SUFFIX}"
            lru_keys = list(client.scan_iter(pattern))

            for lru_key in lru_keys:
                # Get count in this set
                count = client.zcard(lru_key)

                if count > max_entries:
                    # Get entries to remove (oldest by score)
                    excess = count - max_entries
                    model = lru_key.replace(
                        f"{self._prefix}{self.KEY_VERSION}:", ""
                    ).replace(self.LRU_SET_SUFFIX, "")

                    # Get oldest entries
                    oldest = client.zrange(lru_key, 0, excess - 1)

                    # Delete embedding keys
                    keys_to_delete = [
                        self._make_key(h.decode() if isinstance(h, bytes) else h, model)
                        for h in oldest
                    ]
                    if keys_to_delete:
                        client.delete(*keys_to_delete)

                    # Remove from LRU set
                    client.zremrangebyrank(lru_key, 0, excess - 1)
                    removed += excess

            if removed > 0:
                logger.info(f"Cleaned up {removed} cache entries from Redis")

            return removed

        except Exception as e:
            logger.error(f"Redis cleanup failed: {e}")
            return 0

    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        try:
            client = self._get_client()

            # Count all embedding keys (excluding LRU sets)
            pattern = f"{self._prefix}{self.KEY_VERSION}:*"
            total_entries = 0
            cache_size = 0

            for key in client.scan_iter(pattern):
                key_str = key.decode() if isinstance(key, bytes) else key
                if not key_str.endswith(self.LRU_SET_SUFFIX):
                    total_entries += 1
                    # Get memory usage for this key
                    try:
                        mem = client.memory_usage(key)
                        if mem:
                            cache_size += mem
                    except Exception:
                        pass

            # Get Redis server info
            info = client.info("memory")

            # Calculate hit rate
            total_requests = self._hit_count + self._miss_count
            hit_rate = self._hit_count / total_requests if total_requests > 0 else 0.0

            return CacheStats(
                backend="redis",
                total_entries=total_entries,
                hit_count=self._hit_count,
                miss_count=self._miss_count,
                hit_rate=hit_rate,
                cache_size_bytes=cache_size,
                is_healthy=True,
                extra_info={
                    "redis_url": self._config.redis_url,
                    "redis_memory_used": info.get("used_memory_human", "unknown"),
                    "key_prefix": self._prefix,
                    "key_version": self.KEY_VERSION,
                },
            )

        except Exception as e:
            logger.error(f"Failed to get Redis stats: {e}")
            return CacheStats(
                backend="redis",
                is_healthy=False,
                extra_info={"error": str(e)},
            )

    def health_check(self) -> bool:
        """Check if Redis is operational."""
        try:
            client = self._get_client()
            return client.ping()
        except Exception:
            return False

    def close(self):
        """Close Redis connection pool."""
        if self._pool:
            try:
                self._pool.disconnect()
            except Exception:
                pass
            self._pool = None
            self._client = None
