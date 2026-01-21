"""
RAG Embedding Cache Package.

Provides pluggable cache backends for embedding storage:
- SQLite: Local single-user cache (default)
- Redis: Distributed multi-user cache
- Fallback: Redis with SQLite fallback
"""

from rag.cache.base import BaseCacheProvider, CacheBackend, CacheConfig, CacheStats
from rag.cache.factory import create_cache_provider, get_cache_provider, reset_cache_provider

__all__ = [
    "BaseCacheProvider",
    "CacheBackend",
    "CacheConfig",
    "CacheStats",
    "create_cache_provider",
    "get_cache_provider",
    "reset_cache_provider",
]
