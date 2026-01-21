"""
Lightweight health monitoring for RAG services.

Provides cached health checks for external services (Neo4j, Neon, OpenAI)
to avoid excessive health check overhead while maintaining accurate status.

Features:
- Cached health results with configurable TTL
- Circuit breaker integration for instant unavailable detection
- Thread-safe operations
- Singleton pattern for consistent state
"""

import logging
import os
import pathlib
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

from dotenv import load_dotenv

from src.utils.timeout_config import get_timeout

# Load environment variables from .env file
_root_env = pathlib.Path(__file__).parent.parent.parent / '.env'
if _root_env.exists():
    load_dotenv(dotenv_path=str(_root_env))
else:
    try:
        from managers.data_folder_manager import data_folder_manager
        load_dotenv(dotenv_path=str(data_folder_manager.env_file_path))
    except Exception:
        pass

logger = logging.getLogger(__name__)


@dataclass
class ServiceHealth:
    """Health status for a single service."""
    service: str
    healthy: bool
    last_check: datetime
    latency_ms: float = 0.0
    error_message: Optional[str] = None
    circuit_state: str = "unknown"

    def is_stale(self, ttl_seconds: int) -> bool:
        """Check if this health result has expired."""
        age = (datetime.now() - self.last_check).total_seconds()
        return age > ttl_seconds

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "service": self.service,
            "healthy": self.healthy,
            "last_check": self.last_check.isoformat(),
            "latency_ms": self.latency_ms,
            "error_message": self.error_message,
            "circuit_state": self.circuit_state,
        }


class RAGHealthManager:
    """Manages health checks for RAG system services.

    Provides cached health status with configurable TTL to balance
    freshness with performance. Integrates with circuit breakers
    for instant unavailable detection.
    """

    def __init__(self, cache_ttl_seconds: int = 30):
        """Initialize health manager.

        Args:
            cache_ttl_seconds: How long health results are cached (default: 30s)
        """
        self._cache: Dict[str, ServiceHealth] = {}
        self._cache_ttl = cache_ttl_seconds
        self._lock = threading.Lock()

        # Load TTL from settings if available
        try:
            from src.settings.settings import SETTINGS
            resilience_config = SETTINGS.get("rag_resilience", {})
            self._cache_ttl = resilience_config.get(
                "health_check_cache_ttl", cache_ttl_seconds
            )
        except Exception:
            pass

    def _get_cached(self, service: str) -> Optional[ServiceHealth]:
        """Get cached health result if still valid.

        Args:
            service: Service name

        Returns:
            Cached ServiceHealth or None if stale/missing
        """
        with self._lock:
            cached = self._cache.get(service)
            if cached and not cached.is_stale(self._cache_ttl):
                return cached
            return None

    def _cache_result(
        self,
        service: str,
        healthy: bool,
        error_message: Optional[str] = None,
        latency_ms: float = 0.0,
        circuit_state: str = "unknown",
    ) -> ServiceHealth:
        """Cache a health check result.

        Args:
            service: Service name
            healthy: Whether service is healthy
            error_message: Optional error message
            latency_ms: Check latency in milliseconds
            circuit_state: Current circuit breaker state

        Returns:
            The cached ServiceHealth object
        """
        health = ServiceHealth(
            service=service,
            healthy=healthy,
            last_check=datetime.now(),
            latency_ms=latency_ms,
            error_message=error_message,
            circuit_state=circuit_state,
        )

        with self._lock:
            self._cache[service] = health

        return health

    def check_neo4j(self, force: bool = False) -> ServiceHealth:
        """Check Neo4j health with caching.

        Args:
            force: If True, bypass cache

        Returns:
            ServiceHealth for Neo4j
        """
        if not force:
            cached = self._get_cached("neo4j")
            if cached:
                return cached

        # Check circuit breaker first (instant)
        circuit_state = "unknown"
        try:
            from src.rag.rag_resilience import get_neo4j_circuit_breaker
            cb = get_neo4j_circuit_breaker()
            circuit_state = cb.state.value

            if circuit_state == "open":
                return self._cache_result(
                    "neo4j",
                    healthy=False,
                    error_message="Circuit breaker open",
                    circuit_state=circuit_state,
                )
        except ImportError:
            pass

        # Perform actual health check
        start_time = time.time()
        try:
            from src.rag.graph_data_provider import GraphDataProvider
            provider = GraphDataProvider()
            healthy = provider.health_check()
            latency_ms = (time.time() - start_time) * 1000

            return self._cache_result(
                "neo4j",
                healthy=healthy,
                latency_ms=latency_ms,
                circuit_state=circuit_state,
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return self._cache_result(
                "neo4j",
                healthy=False,
                error_message=str(e),
                latency_ms=latency_ms,
                circuit_state=circuit_state,
            )

    def check_neon(self, force: bool = False) -> ServiceHealth:
        """Check Neon PostgreSQL health with caching.

        Args:
            force: If True, bypass cache

        Returns:
            ServiceHealth for Neon
        """
        if not force:
            cached = self._get_cached("neon")
            if cached:
                return cached

        # Check circuit breaker first (instant)
        circuit_state = "unknown"
        try:
            from src.rag.rag_resilience import get_neon_circuit_breaker
            cb = get_neon_circuit_breaker()
            circuit_state = cb.state.value

            if circuit_state == "open":
                return self._cache_result(
                    "neon",
                    healthy=False,
                    error_message="Circuit breaker open",
                    circuit_state=circuit_state,
                )
        except ImportError:
            pass

        # Perform actual health check
        start_time = time.time()
        try:
            from src.rag.neon_vector_store import get_vector_store
            store = get_vector_store()
            if store:
                healthy = store.health_check()
            else:
                healthy = False
            latency_ms = (time.time() - start_time) * 1000

            return self._cache_result(
                "neon",
                healthy=healthy,
                latency_ms=latency_ms,
                circuit_state=circuit_state,
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return self._cache_result(
                "neon",
                healthy=False,
                error_message=str(e),
                latency_ms=latency_ms,
                circuit_state=circuit_state,
            )

    def check_openai(self, force: bool = False) -> ServiceHealth:
        """Check OpenAI API health with caching.

        Uses a lightweight models list call rather than embedding.

        Args:
            force: If True, bypass cache

        Returns:
            ServiceHealth for OpenAI
        """
        if not force:
            cached = self._get_cached("openai")
            if cached:
                return cached

        # Check circuit breaker first (instant)
        circuit_state = "unknown"
        try:
            from src.rag.rag_resilience import get_openai_embedding_circuit_breaker
            cb = get_openai_embedding_circuit_breaker()
            circuit_state = cb.state.value

            if circuit_state == "open":
                return self._cache_result(
                    "openai",
                    healthy=False,
                    error_message="Circuit breaker open",
                    circuit_state=circuit_state,
                )
        except ImportError:
            pass

        # Perform lightweight API check
        start_time = time.time()
        try:
            from openai import OpenAI
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
                return self._cache_result(
                    "openai",
                    healthy=False,
                    error_message="API key not configured",
                    circuit_state=circuit_state,
                )

            client = OpenAI(api_key=api_key)
            timeout = get_timeout("health_check", default=5.0)

            # Use a lightweight API call (list first model)
            # This is faster than an embedding call
            models = client.models.list()
            # Just accessing the iterator is enough to verify connectivity
            _ = next(iter(models.data), None)

            latency_ms = (time.time() - start_time) * 1000

            return self._cache_result(
                "openai",
                healthy=True,
                latency_ms=latency_ms,
                circuit_state=circuit_state,
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return self._cache_result(
                "openai",
                healthy=False,
                error_message=str(e),
                latency_ms=latency_ms,
                circuit_state=circuit_state,
            )

    def get_all_health(self, force: bool = False) -> Dict[str, ServiceHealth]:
        """Get health status for all services.

        Args:
            force: If True, bypass cache for all checks

        Returns:
            Dict mapping service name to ServiceHealth
        """
        return {
            "neo4j": self.check_neo4j(force=force),
            "neon": self.check_neon(force=force),
            "openai": self.check_openai(force=force),
        }

    def get_summary(self) -> dict:
        """Get a summary of all service health.

        Returns:
            Dict with overall health and per-service status
        """
        all_health = self.get_all_health()

        all_healthy = all(h.healthy for h in all_health.values())
        any_circuit_open = any(
            h.circuit_state == "open" for h in all_health.values()
        )

        return {
            "all_healthy": all_healthy,
            "any_circuit_open": any_circuit_open,
            "services": {
                name: health.to_dict()
                for name, health in all_health.items()
            },
            "checked_at": datetime.now().isoformat(),
        }

    def clear_cache(self):
        """Clear all cached health results."""
        with self._lock:
            self._cache.clear()
        logger.info("Health check cache cleared")


# Singleton instance
_health_manager: Optional[RAGHealthManager] = None


def get_health_manager() -> RAGHealthManager:
    """Get the global health manager instance.

    Returns:
        RAGHealthManager singleton
    """
    global _health_manager
    if _health_manager is None:
        _health_manager = RAGHealthManager()
    return _health_manager


def reset_health_manager():
    """Reset the global health manager instance."""
    global _health_manager
    if _health_manager:
        _health_manager.clear_cache()
    _health_manager = None
