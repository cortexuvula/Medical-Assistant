"""
Embedding manager for RAG system.

Handles embedding generation using OpenAI's text-embedding models.
Supports batch processing and caching for efficiency.
"""

import asyncio
import hashlib
import json
import logging
from typing import Optional

from src.rag.models import EmbeddingRequest, EmbeddingResponse

logger = logging.getLogger(__name__)


class EmbeddingManager:
    """Manages embedding generation using OpenAI API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
        batch_size: int = 100,
        max_retries: int = 3,
    ):
        """Initialize the embedding manager.

        Args:
            api_key: OpenAI API key (will use environment if not provided)
            model: Embedding model to use
            dimensions: Output dimensions for embeddings
            batch_size: Maximum texts per API request
            max_retries: Maximum retries for failed requests
        """
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.max_retries = max_retries
        self._client = None
        self._api_key = api_key

    def _get_client(self):
        """Get or create OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError:
                raise ImportError("openai is required for embeddings. Install with: pip install openai")

            if self._api_key:
                self._client = OpenAI(api_key=self._api_key)
            else:
                # Try to get from environment or settings
                import os
                api_key = os.environ.get("OPENAI_API_KEY")

                if not api_key:
                    # Try to get from application settings
                    try:
                        from src.managers.api_key_manager import get_api_key_manager
                        manager = get_api_key_manager()
                        api_key = manager.get_key("openai")
                    except Exception:
                        pass

                if not api_key:
                    raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable or configure in settings.")

                self._client = OpenAI(api_key=api_key)

        return self._client

    def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding
        """
        result = self.generate_embeddings([text])
        return result.embeddings[0]

    def generate_embeddings(self, texts: list[str]) -> EmbeddingResponse:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            EmbeddingResponse with embeddings and token count
        """
        if not texts:
            return EmbeddingResponse(embeddings=[], model=self.model, total_tokens=0)

        client = self._get_client()
        all_embeddings = []
        total_tokens = 0

        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]

            # Clean texts (remove newlines and excessive whitespace)
            cleaned_batch = [self._clean_text(t) for t in batch]

            for attempt in range(self.max_retries):
                try:
                    response = client.embeddings.create(
                        input=cleaned_batch,
                        model=self.model,
                    )

                    # Extract embeddings in order
                    batch_embeddings = [None] * len(cleaned_batch)
                    for item in response.data:
                        batch_embeddings[item.index] = item.embedding

                    all_embeddings.extend(batch_embeddings)
                    total_tokens += response.usage.total_tokens
                    break

                except Exception as e:
                    logger.warning(f"Embedding attempt {attempt + 1} failed: {e}")
                    if attempt == self.max_retries - 1:
                        raise
                    # Exponential backoff
                    import time
                    time.sleep(2 ** attempt)

        return EmbeddingResponse(
            embeddings=all_embeddings,
            model=self.model,
            total_tokens=total_tokens,
        )

    async def generate_embeddings_async(self, texts: list[str]) -> EmbeddingResponse:
        """Generate embeddings asynchronously.

        Args:
            texts: List of texts to embed

        Returns:
            EmbeddingResponse with embeddings and token count
        """
        if not texts:
            return EmbeddingResponse(embeddings=[], model=self.model, total_tokens=0)

        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("openai is required for embeddings. Install with: pip install openai")

        # Get API key
        api_key = self._api_key
        if not api_key:
            import os
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                try:
                    from src.managers.api_key_manager import get_api_key_manager
                    manager = get_api_key_manager()
                    api_key = manager.get_key("openai")
                except Exception:
                    pass

        if not api_key:
            raise ValueError("OpenAI API key not found")

        async_client = AsyncOpenAI(api_key=api_key)

        all_embeddings = []
        total_tokens = 0

        # Create tasks for each batch
        async def process_batch(batch: list[str]) -> tuple[list[list[float]], int]:
            cleaned_batch = [self._clean_text(t) for t in batch]

            for attempt in range(self.max_retries):
                try:
                    response = await async_client.embeddings.create(
                        input=cleaned_batch,
                        model=self.model,
                    )

                    batch_embeddings = [None] * len(cleaned_batch)
                    for item in response.data:
                        batch_embeddings[item.index] = item.embedding

                    return batch_embeddings, response.usage.total_tokens

                except Exception as e:
                    logger.warning(f"Async embedding attempt {attempt + 1} failed: {e}")
                    if attempt == self.max_retries - 1:
                        raise
                    await asyncio.sleep(2 ** attempt)

        # Process batches concurrently (but respect rate limits)
        batches = [texts[i:i + self.batch_size] for i in range(0, len(texts), self.batch_size)]

        # Limit concurrent requests to avoid rate limits
        semaphore = asyncio.Semaphore(5)

        async def limited_process(batch):
            async with semaphore:
                return await process_batch(batch)

        results = await asyncio.gather(*[limited_process(b) for b in batches])

        for embeddings, tokens in results:
            all_embeddings.extend(embeddings)
            total_tokens += tokens

        return EmbeddingResponse(
            embeddings=all_embeddings,
            model=self.model,
            total_tokens=total_tokens,
        )

    def _clean_text(self, text: str) -> str:
        """Clean text for embedding.

        Args:
            text: Text to clean

        Returns:
            Cleaned text
        """
        # Replace newlines with spaces
        text = text.replace("\n", " ")
        # Collapse multiple spaces
        import re
        text = re.sub(r"\s+", " ", text)
        # Truncate if too long (model limit is ~8191 tokens)
        # Rough estimate: 4 chars per token
        max_chars = 30000
        if len(text) > max_chars:
            text = text[:max_chars]
        return text.strip()

    def compute_similarity(self, embedding1: list[float], embedding2: list[float]) -> float:
        """Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding
            embedding2: Second embedding

        Returns:
            Cosine similarity score (0 to 1)
        """
        import math

        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        norm1 = math.sqrt(sum(a * a for a in embedding1))
        norm2 = math.sqrt(sum(b * b for b in embedding2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def compute_text_hash(self, text: str) -> str:
        """Compute hash of text for caching.

        Args:
            text: Text to hash

        Returns:
            SHA256 hash string
        """
        cleaned = self._clean_text(text)
        return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()


class EmbeddingCache:
    """Local cache for embeddings using SQLite."""

    def __init__(self, db_manager=None):
        """Initialize embedding cache.

        Args:
            db_manager: Database manager instance
        """
        self._db_manager = db_manager

    def _get_db_manager(self):
        """Get or create database manager."""
        if self._db_manager is None:
            try:
                from src.database.db_pool import get_db_manager
                self._db_manager = get_db_manager()
            except Exception as e:
                logger.warning(f"Failed to get database manager: {e}")
                return None
        return self._db_manager

    def get_cached_embedding(self, text_hash: str, model: str) -> Optional[list[float]]:
        """Get cached embedding if available.

        Args:
            text_hash: Hash of the text
            model: Embedding model used

        Returns:
            Cached embedding or None
        """
        db = self._get_db_manager()
        if not db:
            return None

        try:
            row = db.fetchone(
                """
                SELECT embedding_json FROM rag_embedding_cache
                WHERE text_hash = ? AND model = ?
                """,
                (text_hash, model)
            )

            if row and row[0]:
                # Update last used timestamp and count
                db.execute(
                    """
                    UPDATE rag_embedding_cache
                    SET last_used_at = CURRENT_TIMESTAMP, use_count = use_count + 1
                    WHERE text_hash = ? AND model = ?
                    """,
                    (text_hash, model)
                )
                return json.loads(row[0])
        except Exception as e:
            logger.warning(f"Failed to get cached embedding: {e}")

        return None

    def cache_embedding(self, text_hash: str, embedding: list[float], model: str):
        """Cache an embedding.

        Args:
            text_hash: Hash of the text
            embedding: Embedding vector
            model: Embedding model used
        """
        db = self._get_db_manager()
        if not db:
            return

        try:
            embedding_json = json.dumps(embedding)
            db.execute(
                """
                INSERT OR REPLACE INTO rag_embedding_cache
                (text_hash, embedding_json, model, created_at, last_used_at, use_count)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
                """,
                (text_hash, embedding_json, model)
            )
        except Exception as e:
            logger.warning(f"Failed to cache embedding: {e}")

    def get_cached_embeddings_batch(
        self,
        text_hashes: list[str],
        model: str
    ) -> dict[str, list[float]]:
        """Get multiple cached embeddings.

        Args:
            text_hashes: List of text hashes
            model: Embedding model used

        Returns:
            Dict mapping hash to embedding for found entries
        """
        db = self._get_db_manager()
        if not db:
            return {}

        result = {}
        try:
            # SQLite doesn't support arrays, so we need to query individually
            # For better performance, we could use a temp table
            placeholders = ",".join("?" * len(text_hashes))
            rows = db.fetchall(
                f"""
                SELECT text_hash, embedding_json FROM rag_embedding_cache
                WHERE text_hash IN ({placeholders}) AND model = ?
                """,
                (*text_hashes, model)
            )

            for row in rows:
                result[row[0]] = json.loads(row[1])

            # Update usage stats for found entries
            if result:
                db.execute(
                    f"""
                    UPDATE rag_embedding_cache
                    SET last_used_at = CURRENT_TIMESTAMP, use_count = use_count + 1
                    WHERE text_hash IN ({placeholders}) AND model = ?
                    """,
                    (*text_hashes, model)
                )
        except Exception as e:
            logger.warning(f"Failed to get cached embeddings batch: {e}")

        return result

    def cleanup_old_cache(self, max_age_days: int = 30, max_entries: int = 10000):
        """Clean up old cache entries.

        Args:
            max_age_days: Remove entries older than this
            max_entries: Maximum entries to keep
        """
        db = self._get_db_manager()
        if not db:
            return

        try:
            # Remove old entries
            db.execute(
                """
                DELETE FROM rag_embedding_cache
                WHERE last_used_at < datetime('now', '-' || ? || ' days')
                """,
                (max_age_days,)
            )

            # Keep only top N by use count if over limit
            db.execute(
                f"""
                DELETE FROM rag_embedding_cache
                WHERE id NOT IN (
                    SELECT id FROM rag_embedding_cache
                    ORDER BY use_count DESC, last_used_at DESC
                    LIMIT ?
                )
                """,
                (max_entries,)
            )

            logger.info("Cleaned up embedding cache")
        except Exception as e:
            logger.warning(f"Failed to cleanup cache: {e}")


class CachedEmbeddingManager(EmbeddingManager):
    """Embedding manager with local caching."""

    def __init__(self, *args, **kwargs):
        """Initialize cached embedding manager."""
        super().__init__(*args, **kwargs)
        self.cache = EmbeddingCache()

    def generate_embeddings(self, texts: list[str]) -> EmbeddingResponse:
        """Generate embeddings with caching.

        Args:
            texts: List of texts to embed

        Returns:
            EmbeddingResponse with embeddings
        """
        if not texts:
            return EmbeddingResponse(embeddings=[], model=self.model, total_tokens=0)

        # Compute hashes
        hashes = [self.compute_text_hash(t) for t in texts]

        # Check cache
        cached = self.cache.get_cached_embeddings_batch(hashes, self.model)

        # Find texts that need embedding
        texts_to_embed = []
        indices_to_embed = []
        for i, (text, hash_val) in enumerate(zip(texts, hashes)):
            if hash_val not in cached:
                texts_to_embed.append(text)
                indices_to_embed.append(i)

        # Generate embeddings for uncached texts
        total_tokens = 0
        if texts_to_embed:
            response = super().generate_embeddings(texts_to_embed)
            total_tokens = response.total_tokens

            # Cache new embeddings
            for idx, embedding in zip(indices_to_embed, response.embeddings):
                hash_val = hashes[idx]
                cached[hash_val] = embedding
                self.cache.cache_embedding(hash_val, embedding, self.model)

        # Build result in original order
        embeddings = [cached[h] for h in hashes]

        return EmbeddingResponse(
            embeddings=embeddings,
            model=self.model,
            total_tokens=total_tokens,
        )
