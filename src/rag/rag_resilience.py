"""
RAG-specific circuit breakers and resilience utilities.

Provides singleton circuit breakers for external services used by the RAG system,
enabling graceful degradation when services become unavailable.
"""

import logging
from typing import Optional

from utils.resilience import CircuitBreaker, CircuitState
from utils.exceptions import ServiceUnavailableError

logger = logging.getLogger(__name__)

# Singleton circuit breakers for RAG services
_neo4j_circuit_breaker: Optional[CircuitBreaker] = None
_neon_circuit_breaker: Optional[CircuitBreaker] = None
_openai_embedding_circuit_breaker: Optional[CircuitBreaker] = None


def get_neo4j_circuit_breaker() -> CircuitBreaker:
    """Get the singleton Neo4j circuit breaker.

    Configuration:
        - failure_threshold: 3 (trip after 3 consecutive failures)
        - recovery_timeout: 30s (try to recover after 30 seconds)

    Returns:
        CircuitBreaker instance for Neo4j operations
    """
    global _neo4j_circuit_breaker
    if _neo4j_circuit_breaker is None:
        # Load config from settings if available
        failure_threshold = 3
        recovery_timeout = 30

        try:
            from settings.settings import SETTINGS
            resilience_config = SETTINGS.get("rag_resilience", {})
            failure_threshold = resilience_config.get("neo4j_failure_threshold", 3)
            recovery_timeout = resilience_config.get("neo4j_recovery_timeout", 30)
        except Exception:
            pass

        _neo4j_circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=Exception,
            name="neo4j"
        )
        logger.info(
            f"Neo4j circuit breaker initialized: "
            f"threshold={failure_threshold}, recovery={recovery_timeout}s"
        )

    return _neo4j_circuit_breaker


def get_neon_circuit_breaker() -> CircuitBreaker:
    """Get the singleton Neon PostgreSQL circuit breaker.

    Configuration:
        - failure_threshold: 5 (more tolerant for primary storage)
        - recovery_timeout: 30s

    Returns:
        CircuitBreaker instance for Neon operations
    """
    global _neon_circuit_breaker
    if _neon_circuit_breaker is None:
        failure_threshold = 5
        recovery_timeout = 30

        try:
            from settings.settings import SETTINGS
            resilience_config = SETTINGS.get("rag_resilience", {})
            failure_threshold = resilience_config.get("neon_failure_threshold", 5)
            recovery_timeout = resilience_config.get("neon_recovery_timeout", 30)
        except Exception:
            pass

        _neon_circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=Exception,
            name="neon"
        )
        logger.info(
            f"Neon circuit breaker initialized: "
            f"threshold={failure_threshold}, recovery={recovery_timeout}s"
        )

    return _neon_circuit_breaker


def get_openai_embedding_circuit_breaker() -> CircuitBreaker:
    """Get the singleton OpenAI Embedding circuit breaker.

    Configuration:
        - failure_threshold: 5 (tolerant for transient rate limits)
        - recovery_timeout: 60s (allow rate limit reset)

    Returns:
        CircuitBreaker instance for OpenAI embedding operations
    """
    global _openai_embedding_circuit_breaker
    if _openai_embedding_circuit_breaker is None:
        failure_threshold = 5
        recovery_timeout = 60

        try:
            from settings.settings import SETTINGS
            resilience_config = SETTINGS.get("rag_resilience", {})
            failure_threshold = resilience_config.get("embedding_failure_threshold", 5)
            recovery_timeout = resilience_config.get("embedding_recovery_timeout", 60)
        except Exception:
            pass

        _openai_embedding_circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=Exception,
            name="openai_embedding"
        )
        logger.info(
            f"OpenAI Embedding circuit breaker initialized: "
            f"threshold={failure_threshold}, recovery={recovery_timeout}s"
        )

    return _openai_embedding_circuit_breaker


def is_neo4j_available() -> bool:
    """Quick check if Neo4j circuit is closed (service available).

    Use this for fast-path checks before attempting Neo4j operations.
    Does not perform actual connectivity checks.

    Returns:
        True if circuit is CLOSED or HALF_OPEN (worth trying)
        False if circuit is OPEN (service known to be unavailable)
    """
    cb = get_neo4j_circuit_breaker()
    return cb.state != CircuitState.OPEN


def is_neon_available() -> bool:
    """Quick check if Neon circuit is closed (service available).

    Returns:
        True if circuit is CLOSED or HALF_OPEN
        False if circuit is OPEN
    """
    cb = get_neon_circuit_breaker()
    return cb.state != CircuitState.OPEN


def is_openai_embedding_available() -> bool:
    """Quick check if OpenAI Embedding circuit is closed.

    Returns:
        True if circuit is CLOSED or HALF_OPEN
        False if circuit is OPEN
    """
    cb = get_openai_embedding_circuit_breaker()
    return cb.state != CircuitState.OPEN


def get_circuit_breaker_states() -> dict:
    """Get current state of all RAG circuit breakers.

    Returns:
        Dict mapping service name to circuit state
    """
    return {
        "neo4j": get_neo4j_circuit_breaker().state.value,
        "neon": get_neon_circuit_breaker().state.value,
        "openai_embedding": get_openai_embedding_circuit_breaker().state.value,
    }


def reset_circuit_breaker(service: str) -> bool:
    """Manually reset a circuit breaker to CLOSED state.

    Use after fixing an underlying service issue.

    Args:
        service: Service name ("neo4j", "neon", "openai_embedding")

    Returns:
        True if reset successful, False if unknown service
    """
    if service == "neo4j":
        get_neo4j_circuit_breaker().reset()
        logger.info("Neo4j circuit breaker manually reset")
        return True
    elif service == "neon":
        get_neon_circuit_breaker().reset()
        logger.info("Neon circuit breaker manually reset")
        return True
    elif service == "openai_embedding":
        get_openai_embedding_circuit_breaker().reset()
        logger.info("OpenAI Embedding circuit breaker manually reset")
        return True
    else:
        logger.warning(f"Unknown circuit breaker service: {service}")
        return False


def reset_all_circuit_breakers():
    """Reset all RAG circuit breakers to CLOSED state."""
    reset_circuit_breaker("neo4j")
    reset_circuit_breaker("neon")
    reset_circuit_breaker("openai_embedding")
    logger.info("All RAG circuit breakers reset")


class CircuitOpenError(ServiceUnavailableError):
    """Raised when a circuit breaker is open and blocking requests."""

    def __init__(self, service: str, recovery_timeout: int):
        self.service = service
        self.recovery_timeout = recovery_timeout
        super().__init__(
            f"{service} circuit breaker is OPEN. "
            f"Service unavailable, will retry in {recovery_timeout}s."
        )
