"""
Base cache provider interface.

Defines the abstract interface for embedding cache backends.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from utils.structured_logging import get_logger

logger = get_logger(__name__)


class CacheBackend(Enum):
    """Available cache backends."""
    SQLITE = "sqlite"
    REDIS = "redis"
    FALLBACK = "fallback"  # Redis with SQLite fallback
    AUTO = "auto"  # Auto-detect based on environment


@dataclass
class CacheConfig:
    """Configuration for cache provider.

    Attributes:
        backend: Cache backend type
        redis_url: Redis connection URL (for Redis/fallback)
        redis_prefix: Key prefix for Redis (default: medassist:embedding:)
        sqlite_path: Path to SQLite database (for SQLite/fallback)
        max_entries: Maximum cache entries
        max_age_days: Maximum entry age for eviction
        enable_fallback: Whether to fall back to SQLite if Redis fails
        retry_primary_seconds: How often to retry primary in fallback mode
    """
    backend: CacheBackend = CacheBackend.AUTO
    redis_url: Optional[str] = None
    redis_prefix: str = "medassist:embedding:"
    sqlite_path: Optional[str] = None
    max_entries: int = 10000
    max_age_days: int = 30
    enable_fallback: bool = True
    retry_primary_seconds: int = 60


@dataclass
class CacheStats:
    """Cache statistics.

    Attributes:
        backend: Current backend type
        total_entries: Total entries in cache
        hit_count: Cache hits since startup
        miss_count: Cache misses since startup
        hit_rate: Hit rate (0.0 to 1.0)
        cache_size_bytes: Approximate cache size
        oldest_entry: Timestamp of oldest entry
        last_cleanup: Timestamp of last cleanup
        is_healthy: Whether cache is operational
    """
    backend: str
    total_entries: int = 0
    hit_count: int = 0
    miss_count: int = 0
    hit_rate: float = 0.0
    cache_size_bytes: int = 0
    oldest_entry: Optional[datetime] = None
    last_cleanup: Optional[datetime] = None
    is_healthy: bool = True
    extra_info: dict = field(default_factory=dict)


@dataclass
class CacheEntry:
    """A single cache entry.

    Attributes:
        text_hash: Hash of the input text
        model: Embedding model name
        embedding: The embedding vector
        created_at: When entry was created
        last_accessed: When entry was last accessed
    """
    text_hash: str
    model: str
    embedding: list[float]
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)


class BaseCacheProvider(ABC):
    """Abstract base class for cache providers.

    All cache providers must implement these methods to provide
    a consistent interface for embedding caching.
    """

    @abstractmethod
    def get(self, text_hash: str, model: str) -> Optional[list[float]]:
        """Get a cached embedding.

        Args:
            text_hash: SHA-256 hash of the input text
            model: Embedding model name

        Returns:
            Embedding vector if found, None otherwise
        """
        pass

    @abstractmethod
    def set(self, text_hash: str, embedding: list[float], model: str) -> bool:
        """Cache an embedding.

        Args:
            text_hash: SHA-256 hash of the input text
            embedding: Embedding vector
            model: Embedding model name

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_batch(
        self,
        text_hashes: list[str],
        model: str,
    ) -> dict[str, list[float]]:
        """Get multiple cached embeddings.

        Args:
            text_hashes: List of SHA-256 hashes
            model: Embedding model name

        Returns:
            Dict mapping text_hash to embedding for found entries
        """
        pass

    @abstractmethod
    def set_batch(
        self,
        entries: list[tuple[str, list[float]]],
        model: str,
    ) -> int:
        """Cache multiple embeddings.

        Args:
            entries: List of (text_hash, embedding) tuples
            model: Embedding model name

        Returns:
            Number of entries successfully cached
        """
        pass

    @abstractmethod
    def delete(self, text_hash: str, model: str) -> bool:
        """Delete a cached embedding.

        Args:
            text_hash: SHA-256 hash of the input text
            model: Embedding model name

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def clear(self) -> int:
        """Clear all cached embeddings.

        Returns:
            Number of entries cleared
        """
        pass

    @abstractmethod
    def cleanup(
        self,
        max_age_days: Optional[int] = None,
        max_entries: Optional[int] = None,
    ) -> int:
        """Clean up old or excess cache entries.

        Args:
            max_age_days: Delete entries older than this (default from config)
            max_entries: Keep only this many entries (default from config)

        Returns:
            Number of entries removed
        """
        pass

    @abstractmethod
    def get_stats(self) -> CacheStats:
        """Get cache statistics.

        Returns:
            CacheStats with current metrics
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Check if cache is operational.

        Returns:
            True if healthy, False otherwise
        """
        pass

    def close(self):
        """Close any open connections.

        Override in subclasses that need cleanup.
        """
        pass
