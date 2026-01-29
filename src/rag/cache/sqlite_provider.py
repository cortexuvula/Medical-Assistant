"""
SQLite cache provider for embeddings.

Provides local single-user caching using SQLite database.
"""

import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Optional

from rag.cache.base import BaseCacheProvider, CacheConfig, CacheStats
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class SQLiteCacheProvider(BaseCacheProvider):
    """SQLite-based embedding cache provider.

    Features:
    - Thread-safe connection pooling
    - LRU eviction with configurable limits
    - Automatic cleanup on startup
    - Batch operations for efficiency
    """

    # Database schema version for migrations
    SCHEMA_VERSION = 1

    def __init__(self, config: CacheConfig):
        """Initialize SQLite cache provider.

        Args:
            config: Cache configuration
        """
        self._config = config
        self._db_path = config.sqlite_path or self._get_default_path()
        self._local = threading.local()
        self._lock = threading.Lock()

        # Stats tracking
        self._hit_count = 0
        self._miss_count = 0

        # Initialize database
        self._init_db()

    def _get_default_path(self) -> str:
        """Get default database path."""
        # Use app data directory
        if os.name == "nt":  # Windows
            base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
            app_dir = os.path.join(base, "MedicalAssistant")
        else:  # macOS/Linux
            base = os.path.expanduser("~")
            app_dir = os.path.join(base, ".medical_assistant")

        os.makedirs(app_dir, exist_ok=True)
        return os.path.join(app_dir, "embedding_cache.db")

    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                self._db_path,
                timeout=30.0,
                check_same_thread=False,
            )
            self._local.conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrency
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn

    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS embedding_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text_hash TEXT NOT NULL,
                model TEXT NOT NULL,
                embedding_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(text_hash, model)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_embedding_cache_hash_model
            ON embedding_cache(text_hash, model)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_embedding_cache_accessed
            ON embedding_cache(last_accessed)
        """)
        conn.commit()

        # Run startup cleanup
        self._startup_cleanup()

    def _startup_cleanup(self):
        """Run cleanup on startup."""
        try:
            self.cleanup(
                max_age_days=self._config.max_age_days,
                max_entries=self._config.max_entries,
            )
        except Exception as e:
            logger.warning(f"Startup cleanup failed: {e}")

    def get(self, text_hash: str, model: str) -> Optional[list[float]]:
        """Get a cached embedding."""
        try:
            conn = self._get_conn()
            cursor = conn.execute(
                """
                SELECT embedding_json FROM embedding_cache
                WHERE text_hash = ? AND model = ?
                """,
                (text_hash, model),
            )
            row = cursor.fetchone()

            if row:
                # Update last accessed time
                conn.execute(
                    """
                    UPDATE embedding_cache
                    SET last_accessed = CURRENT_TIMESTAMP
                    WHERE text_hash = ? AND model = ?
                    """,
                    (text_hash, model),
                )
                conn.commit()

                self._hit_count += 1
                return json.loads(row["embedding_json"])
            else:
                self._miss_count += 1
                return None

        except Exception as e:
            logger.error(f"Cache get failed: {e}")
            self._miss_count += 1
            return None

    def set(self, text_hash: str, embedding: list[float], model: str) -> bool:
        """Cache an embedding."""
        try:
            conn = self._get_conn()
            embedding_json = json.dumps(embedding)

            conn.execute(
                """
                INSERT OR REPLACE INTO embedding_cache
                (text_hash, model, embedding_json, created_at, last_accessed)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (text_hash, model, embedding_json),
            )
            conn.commit()
            return True

        except Exception as e:
            logger.error(f"Cache set failed: {e}")
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
            conn = self._get_conn()
            placeholders = ",".join(["?"] * len(text_hashes))
            cursor = conn.execute(
                f"""
                SELECT text_hash, embedding_json FROM embedding_cache
                WHERE text_hash IN ({placeholders}) AND model = ?
                """,
                (*text_hashes, model),
            )

            results = {}
            found_hashes = []

            for row in cursor:
                hash_val = row["text_hash"]
                results[hash_val] = json.loads(row["embedding_json"])
                found_hashes.append(hash_val)

            # Update last accessed for found entries
            if found_hashes:
                placeholders = ",".join(["?"] * len(found_hashes))
                conn.execute(
                    f"""
                    UPDATE embedding_cache
                    SET last_accessed = CURRENT_TIMESTAMP
                    WHERE text_hash IN ({placeholders}) AND model = ?
                    """,
                    (*found_hashes, model),
                )
                conn.commit()

            # Update stats
            self._hit_count += len(results)
            self._miss_count += len(text_hashes) - len(results)

            return results

        except Exception as e:
            logger.error(f"Cache batch get failed: {e}")
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
            conn = self._get_conn()
            count = 0

            for text_hash, embedding in entries:
                try:
                    embedding_json = json.dumps(embedding)
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO embedding_cache
                        (text_hash, model, embedding_json, created_at, last_accessed)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        """,
                        (text_hash, model, embedding_json),
                    )
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to cache entry {text_hash}: {e}")

            conn.commit()
            return count

        except Exception as e:
            logger.error(f"Cache batch set failed: {e}")
            return 0

    def delete(self, text_hash: str, model: str) -> bool:
        """Delete a cached embedding."""
        try:
            conn = self._get_conn()
            cursor = conn.execute(
                """
                DELETE FROM embedding_cache
                WHERE text_hash = ? AND model = ?
                """,
                (text_hash, model),
            )
            conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Cache delete failed: {e}")
            return False

    def clear(self) -> int:
        """Clear all cached embeddings."""
        try:
            conn = self._get_conn()
            cursor = conn.execute("DELETE FROM embedding_cache")
            count = cursor.rowcount
            conn.commit()

            # Reset stats
            self._hit_count = 0
            self._miss_count = 0

            logger.info(f"Cleared {count} cache entries")
            return count

        except Exception as e:
            logger.error(f"Cache clear failed: {e}")
            return 0

    def cleanup(
        self,
        max_age_days: Optional[int] = None,
        max_entries: Optional[int] = None,
    ) -> int:
        """Clean up old or excess cache entries."""
        max_age_days = max_age_days or self._config.max_age_days
        max_entries = max_entries or self._config.max_entries

        removed = 0

        try:
            conn = self._get_conn()

            # Remove old entries
            cutoff = datetime.now() - timedelta(days=max_age_days)
            cursor = conn.execute(
                """
                DELETE FROM embedding_cache
                WHERE last_accessed < ?
                """,
                (cutoff.isoformat(),),
            )
            removed += cursor.rowcount

            # Remove excess entries (keep most recently accessed)
            cursor = conn.execute("SELECT COUNT(*) FROM embedding_cache")
            count = cursor.fetchone()[0]

            if count > max_entries:
                excess = count - max_entries
                conn.execute(
                    """
                    DELETE FROM embedding_cache
                    WHERE id IN (
                        SELECT id FROM embedding_cache
                        ORDER BY last_accessed ASC
                        LIMIT ?
                    )
                    """,
                    (excess,),
                )
                removed += excess

            conn.commit()

            if removed > 0:
                logger.info(f"Cleaned up {removed} cache entries")

            return removed

        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
            return 0

    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        try:
            conn = self._get_conn()

            # Get total entries
            cursor = conn.execute("SELECT COUNT(*) FROM embedding_cache")
            total_entries = cursor.fetchone()[0]

            # Get cache size estimate
            cursor = conn.execute(
                "SELECT SUM(LENGTH(embedding_json)) FROM embedding_cache"
            )
            size_result = cursor.fetchone()[0]
            cache_size = size_result if size_result else 0

            # Get oldest entry
            cursor = conn.execute(
                "SELECT MIN(created_at) FROM embedding_cache"
            )
            oldest_result = cursor.fetchone()[0]
            oldest_entry = None
            if oldest_result:
                try:
                    oldest_entry = datetime.fromisoformat(oldest_result)
                except (ValueError, TypeError):
                    pass

            # Calculate hit rate
            total_requests = self._hit_count + self._miss_count
            hit_rate = self._hit_count / total_requests if total_requests > 0 else 0.0

            return CacheStats(
                backend="sqlite",
                total_entries=total_entries,
                hit_count=self._hit_count,
                miss_count=self._miss_count,
                hit_rate=hit_rate,
                cache_size_bytes=cache_size,
                oldest_entry=oldest_entry,
                is_healthy=True,
                extra_info={
                    "db_path": self._db_path,
                    "max_entries": self._config.max_entries,
                    "max_age_days": self._config.max_age_days,
                },
            )

        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return CacheStats(
                backend="sqlite",
                is_healthy=False,
                extra_info={"error": str(e)},
            )

    def health_check(self) -> bool:
        """Check if cache is operational."""
        try:
            conn = self._get_conn()
            cursor = conn.execute("SELECT 1")
            cursor.fetchone()
            return True
        except Exception:
            return False

    def close(self):
        """Close database connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None
