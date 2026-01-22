"""
Embedding manager for RAG system.

Handles embedding generation using OpenAI's text-embedding models.
Supports batch processing and caching for efficiency.

Enhanced with:
- Rate limiting to prevent API cost overruns
- Circuit breaker integration for resilience
- Better handling of 429 rate limit responses
- Batch throttling for large document uploads
- Structured exception handling with RAG-specific errors
"""

import asyncio
import hashlib
import json
import logging
import os
import pathlib
import time
from typing import Optional

from dotenv import load_dotenv
from utils.structured_logging import timed

from src.rag.models import EmbeddingRequest, EmbeddingResponse
from src.rag.exceptions import (
    EmbeddingError,
    RateLimitError as RAGRateLimitError,
    CircuitBreakerOpenError,
    RAGConnectionError,
    RAGErrorCodes,
)

# Load environment variables from multiple possible locations
def _load_env():
    """Load .env from multiple possible locations."""
    paths = [
        pathlib.Path(__file__).parent.parent.parent / '.env',  # Project root
        pathlib.Path.cwd() / '.env',  # Current working directory
    ]
    try:
        from managers.data_folder_manager import data_folder_manager
        paths.append(data_folder_manager.env_file_path)  # AppData
    except Exception:
        pass

    for p in paths:
        try:
            if p.exists():
                load_dotenv(dotenv_path=str(p))
                return
        except Exception:
            pass
    load_dotenv()  # Try default search

_load_env()

logger = logging.getLogger(__name__)

# Throttle delay between batches (ms)
BATCH_THROTTLE_MS = 100


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

    def _check_rate_limit(self) -> None:
        """Check rate limit before making API call.

        Raises:
            RateLimitError: If rate limit is exceeded
        """
        try:
            from src.utils.security import get_security_manager
            from src.utils.exceptions import RateLimitError

            security_manager = get_security_manager()
            is_allowed, wait_time = security_manager.check_rate_limit("openai_embeddings")

            if not is_allowed:
                raise RateLimitError(
                    f"Embedding rate limit exceeded. Please wait {wait_time:.1f} seconds.",
                    retry_after=int(wait_time) + 1
                )
        except ImportError:
            pass  # Security module not available

    def _check_circuit_breaker(self) -> bool:
        """Check if embedding circuit breaker allows requests.

        Returns:
            True if requests are allowed, False if circuit is open
        """
        try:
            from src.rag.rag_resilience import is_openai_embedding_available
            return is_openai_embedding_available()
        except ImportError:
            return True  # No circuit breaker available

    def _record_success(self) -> None:
        """Record successful embedding operation."""
        try:
            from src.rag.rag_resilience import get_openai_embedding_circuit_breaker
            cb = get_openai_embedding_circuit_breaker()
            cb._on_success()
        except Exception:
            pass

    def _record_failure(self) -> None:
        """Record failed embedding operation."""
        try:
            from src.rag.rag_resilience import get_openai_embedding_circuit_breaker
            cb = get_openai_embedding_circuit_breaker()
            cb._on_failure()
        except Exception:
            pass

    @timed("rag_generate_embeddings")
    def generate_embeddings(self, texts: list[str]) -> EmbeddingResponse:
        """Generate embeddings for multiple texts.

        Includes rate limiting, circuit breaker, and batch throttling.

        Args:
            texts: List of texts to embed

        Returns:
            EmbeddingResponse with embeddings and token count

        Raises:
            RateLimitError: If rate limit exceeded
            ServiceUnavailableError: If circuit breaker is open
        """
        if not texts:
            return EmbeddingResponse(embeddings=[], model=self.model, total_tokens=0)

        # Check circuit breaker
        if not self._check_circuit_breaker():
            raise CircuitBreakerOpenError(
                "Embedding service unavailable - circuit breaker open",
                service="openai_embedding",
            )

        client = self._get_client()
        all_embeddings = []
        total_tokens = 0

        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]

            # Clean texts (remove newlines and excessive whitespace)
            cleaned_batch = [self._clean_text(t) for t in batch]

            # Check rate limit before each batch
            self._check_rate_limit()

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
                    self._record_success()
                    break

                except Exception as e:
                    error_str = str(e).lower()
                    error_type = type(e).__name__

                    # Handle rate limit errors specially
                    if "rate" in error_str and "limit" in error_str:
                        # Try to extract retry-after from the error
                        retry_after = 60  # Default
                        try:
                            # OpenAI errors often have a response attribute
                            if hasattr(e, 'response') and hasattr(e.response, 'headers'):
                                retry_after = int(e.response.headers.get('retry-after', 60))
                        except Exception:
                            pass

                        logger.warning(
                            f"Embedding rate limit hit, waiting {retry_after}s "
                            f"(attempt {attempt + 1}/{self.max_retries})"
                        )
                        time.sleep(retry_after)
                        continue

                    # Handle authentication errors
                    if "authentication" in error_str or "unauthorized" in error_str or "401" in error_str:
                        self._record_failure()
                        raise EmbeddingError(
                            f"Authentication failed for embedding API: {e}",
                            model=self.model,
                            error_code=RAGErrorCodes.EMBEDDING_FAILED,
                        ) from e

                    # Handle connection errors
                    if "connection" in error_str or "timeout" in error_str:
                        logger.warning(f"Embedding connection error (attempt {attempt + 1}): {error_type}")
                        if attempt == self.max_retries - 1:
                            self._record_failure()
                            raise RAGConnectionError(
                                f"Failed to connect to embedding service: {e}",
                                service="openai_embedding",
                            ) from e
                        time.sleep(2 ** attempt)
                        continue

                    logger.warning(f"Embedding attempt {attempt + 1} failed: {error_type} - {e}")
                    if attempt == self.max_retries - 1:
                        self._record_failure()
                        raise EmbeddingError(
                            f"Embedding generation failed after {self.max_retries} attempts: {e}",
                            model=self.model,
                            input_length=sum(len(t) for t in cleaned_batch),
                        ) from e

                    # Exponential backoff
                    time.sleep(2 ** attempt)

            # Throttle between batches to prevent burst overload
            if i + self.batch_size < len(texts):
                time.sleep(BATCH_THROTTLE_MS / 1000.0)

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
                    error_str = str(e).lower()
                    logger.warning(f"Async embedding attempt {attempt + 1} failed: {type(e).__name__} - {e}")

                    if attempt == self.max_retries - 1:
                        # Wrap in specific exception
                        if "rate" in error_str and "limit" in error_str:
                            raise RAGRateLimitError(f"Rate limit exceeded: {e}") from e
                        elif "connection" in error_str or "timeout" in error_str:
                            raise RAGConnectionError(
                                f"Connection failed: {e}",
                                service="openai_embedding",
                            ) from e
                        else:
                            raise EmbeddingError(
                                f"Async embedding failed: {e}",
                                model=self.model,
                            ) from e

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
    """Embedding cache with pluggable backend support.

    Supports SQLite (default), Redis, or fallback mode via cache providers.
    Uses the new cache provider pattern for flexibility.
    """

    def __init__(self, provider=None):
        """Initialize embedding cache.

        Args:
            provider: Optional BaseCacheProvider instance.
                     If None, uses global provider from factory.
        """
        self._provider = provider
        self._provider_initialized = False

    def _get_provider(self):
        """Get or create cache provider."""
        if self._provider is None and not self._provider_initialized:
            try:
                from rag.cache.factory import get_cache_provider
                self._provider = get_cache_provider()
                self._provider_initialized = True
            except Exception as e:
                logger.warning(f"Failed to get cache provider: {e}")
                self._provider_initialized = True  # Don't retry
                return None
        return self._provider

    def get_cached_embedding(self, text_hash: str, model: str) -> Optional[list[float]]:
        """Get cached embedding if available.

        Args:
            text_hash: Hash of the text
            model: Embedding model used

        Returns:
            Cached embedding or None
        """
        provider = self._get_provider()
        if not provider:
            return None

        try:
            return provider.get(text_hash, model)
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
        provider = self._get_provider()
        if not provider:
            return

        try:
            provider.set(text_hash, embedding, model)
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
        provider = self._get_provider()
        if not provider:
            return {}

        try:
            return provider.get_batch(text_hashes, model)
        except Exception as e:
            logger.warning(f"Failed to get cached embeddings batch: {e}")
            return {}

    def cache_embeddings_batch(
        self,
        entries: list[tuple[str, list[float]]],
        model: str
    ) -> int:
        """Cache multiple embeddings.

        Args:
            entries: List of (text_hash, embedding) tuples
            model: Embedding model used

        Returns:
            Number of entries successfully cached
        """
        provider = self._get_provider()
        if not provider:
            return 0

        try:
            return provider.set_batch(entries, model)
        except Exception as e:
            logger.warning(f"Failed to cache embeddings batch: {e}")
            return 0

    def cleanup_old_cache(self, max_age_days: int = 30, max_entries: int = 10000):
        """Clean up old cache entries.

        Args:
            max_age_days: Remove entries older than this
            max_entries: Maximum entries to keep
        """
        provider = self._get_provider()
        if not provider:
            return

        try:
            removed = provider.cleanup(max_age_days, max_entries)
            if removed > 0:
                logger.info(f"Cleaned up {removed} embedding cache entries")
        except Exception as e:
            logger.warning(f"Failed to cleanup cache: {e}")

    def get_stats(self):
        """Get cache statistics.

        Returns:
            CacheStats or None if provider unavailable
        """
        provider = self._get_provider()
        if not provider:
            return None

        try:
            return provider.get_stats()
        except Exception as e:
            logger.warning(f"Failed to get cache stats: {e}")
            return None

    def health_check(self) -> bool:
        """Check if cache is operational.

        Returns:
            True if healthy, False otherwise
        """
        provider = self._get_provider()
        if not provider:
            return False

        try:
            return provider.health_check()
        except Exception:
            return False


class CachedEmbeddingManager(EmbeddingManager):
    """Embedding manager with pluggable cache backend.

    Supports SQLite (default), Redis, or fallback caching
    via the cache provider pattern.
    """

    def __init__(self, *args, cache_provider=None, **kwargs):
        """Initialize cached embedding manager.

        Args:
            *args: Passed to EmbeddingManager
            cache_provider: Optional BaseCacheProvider instance
            **kwargs: Passed to EmbeddingManager
        """
        super().__init__(*args, **kwargs)
        self.cache = EmbeddingCache(provider=cache_provider)

    def generate_embeddings(self, texts: list[str]) -> EmbeddingResponse:
        """Generate embeddings with caching.

        Uses batch operations for efficiency with both cache
        lookups and storage.

        Args:
            texts: List of texts to embed

        Returns:
            EmbeddingResponse with embeddings
        """
        if not texts:
            return EmbeddingResponse(embeddings=[], model=self.model, total_tokens=0)

        # Compute hashes
        hashes = [self.compute_text_hash(t) for t in texts]

        # Check cache in batch
        cached = self.cache.get_cached_embeddings_batch(hashes, self.model)

        # Find texts that need embedding
        texts_to_embed = []
        indices_to_embed = []
        hashes_to_embed = []

        for i, (text, hash_val) in enumerate(zip(texts, hashes)):
            if hash_val not in cached:
                texts_to_embed.append(text)
                indices_to_embed.append(i)
                hashes_to_embed.append(hash_val)

        # Generate embeddings for uncached texts
        total_tokens = 0
        if texts_to_embed:
            response = super().generate_embeddings(texts_to_embed)
            total_tokens = response.total_tokens

            # Prepare batch cache entries
            cache_entries = []
            for idx, hash_val, embedding in zip(
                indices_to_embed, hashes_to_embed, response.embeddings
            ):
                cached[hash_val] = embedding
                cache_entries.append((hash_val, embedding))

            # Cache new embeddings in batch
            if cache_entries:
                self.cache.cache_embeddings_batch(cache_entries, self.model)

        # Build result in original order
        embeddings = [cached[h] for h in hashes]

        return EmbeddingResponse(
            embeddings=embeddings,
            model=self.model,
            total_tokens=total_tokens,
        )

    def get_cache_stats(self):
        """Get cache statistics.

        Returns:
            CacheStats or None
        """
        return self.cache.get_stats()

    def cleanup_cache(self, max_age_days: int = 30, max_entries: int = 10000):
        """Clean up old cache entries.

        Args:
            max_age_days: Remove entries older than this
            max_entries: Maximum entries to keep
        """
        self.cache.cleanup_old_cache(max_age_days, max_entries)
