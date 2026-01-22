"""
RAG-specific Exceptions

This module defines a hierarchy of exceptions for the RAG (Retrieval-Augmented
Generation) module. These exceptions provide more context than generic exceptions
and enable better error handling and recovery strategies.

Exception Hierarchy:
    RAGError (base)
    ├── EmbeddingError - Embedding generation failures
    ├── VectorSearchError - Vector similarity search failures
    ├── GraphQueryError - Knowledge graph query failures
    ├── DocumentProcessingError - Document ingestion failures
    ├── ConnectionError - Service connectivity issues
    └── ConfigurationError - RAG configuration issues

Usage:
    from rag.exceptions import EmbeddingError, VectorSearchError

    try:
        embeddings = await generate_embeddings(text)
    except EmbeddingError as e:
        logger.error(f"Embedding failed for model {e.model}: {e}")
        # Handle or re-raise with context
"""

from typing import Optional, Any, Dict


class RAGError(Exception):
    """
    Base exception for all RAG-related errors.

    Attributes:
        message: Human-readable error message
        error_code: Machine-readable error code for categorization
        details: Additional context about the error
        recoverable: Whether the error is potentially recoverable
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = True,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "RAG_E000"
        self.details = details or {}
        self.recoverable = recoverable

    def __str__(self) -> str:
        base = f"[{self.error_code}] {self.message}"
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            base += f" ({detail_str})"
        return base


class EmbeddingError(RAGError):
    """
    Errors during embedding generation.

    Raised when:
    - API call to embedding service fails
    - Rate limits are exceeded
    - Invalid input for embedding
    - Model not available

    Attributes:
        model: The embedding model that failed
        input_length: Length of input that caused the error (if applicable)
    """

    def __init__(
        self,
        message: str,
        model: Optional[str] = None,
        input_length: Optional[int] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        if model:
            details["model"] = model
        if input_length:
            details["input_length"] = input_length

        super().__init__(
            message,
            error_code=kwargs.pop("error_code", RAGErrorCodes.EMBEDDING_FAILED),
            details=details,
            **kwargs,
        )
        self.model = model
        self.input_length = input_length


class VectorSearchError(RAGError):
    """
    Errors during vector similarity search.

    Raised when:
    - Vector store query fails
    - Connection to vector database lost
    - Invalid search parameters
    - Search timeout

    Attributes:
        store_type: The vector store type (e.g., "neon", "pinecone")
        query_type: Type of query that failed (e.g., "similarity", "hybrid")
    """

    def __init__(
        self,
        message: str,
        store_type: Optional[str] = None,
        query_type: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        if store_type:
            details["store_type"] = store_type
        if query_type:
            details["query_type"] = query_type

        super().__init__(
            message,
            error_code=kwargs.pop("error_code", RAGErrorCodes.VECTOR_SEARCH_FAILED),
            details=details,
            **kwargs,
        )
        self.store_type = store_type
        self.query_type = query_type


class GraphQueryError(RAGError):
    """
    Errors during knowledge graph queries.

    Raised when:
    - Neo4j query fails
    - Graph database connection lost
    - Invalid Cypher query
    - Query timeout

    Attributes:
        query: The query that failed (sanitized)
        graph_type: Type of graph database
    """

    def __init__(
        self,
        message: str,
        query: Optional[str] = None,
        graph_type: str = "neo4j",
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        if query:
            # Truncate long queries in details
            details["query"] = query[:200] + "..." if len(query) > 200 else query
        details["graph_type"] = graph_type

        super().__init__(
            message,
            error_code=kwargs.pop("error_code", RAGErrorCodes.GRAPH_QUERY_FAILED),
            details=details,
            **kwargs,
        )
        self.query = query
        self.graph_type = graph_type


class DocumentProcessingError(RAGError):
    """
    Errors during document processing and ingestion.

    Raised when:
    - Document parsing fails
    - Chunk generation fails
    - Document too large
    - Invalid document format

    Attributes:
        document_id: ID of the document that failed
        processing_stage: Stage where processing failed
    """

    def __init__(
        self,
        message: str,
        document_id: Optional[str] = None,
        processing_stage: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        if document_id:
            details["document_id"] = document_id
        if processing_stage:
            details["stage"] = processing_stage

        super().__init__(
            message,
            error_code=kwargs.pop("error_code", RAGErrorCodes.DOCUMENT_PROCESSING_FAILED),
            details=details,
            **kwargs,
        )
        self.document_id = document_id
        self.processing_stage = processing_stage


class RAGConnectionError(RAGError):
    """
    Errors when connecting to RAG services.

    Raised when:
    - Cannot connect to vector store
    - Cannot connect to graph database
    - Cannot connect to embedding service
    - Network timeout

    Attributes:
        service: The service that failed to connect
        endpoint: The endpoint URL (sanitized)
    """

    def __init__(
        self,
        message: str,
        service: Optional[str] = None,
        endpoint: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        if service:
            details["service"] = service
        if endpoint:
            # Don't include credentials in endpoint
            sanitized = endpoint.split("@")[-1] if "@" in endpoint else endpoint
            details["endpoint"] = sanitized

        super().__init__(
            message,
            error_code=kwargs.pop("error_code", RAGErrorCodes.CONNECTION_FAILED),
            details=details,
            recoverable=kwargs.pop("recoverable", True),
            **kwargs,
        )
        self.service = service
        self.endpoint = endpoint


class RAGConfigurationError(RAGError):
    """
    Errors in RAG configuration.

    Raised when:
    - Missing required configuration
    - Invalid configuration values
    - Incompatible configuration options

    Attributes:
        config_key: The configuration key that has an issue
        expected: What was expected
        actual: What was found
    """

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        expected: Optional[str] = None,
        actual: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        if config_key:
            details["config_key"] = config_key
        if expected:
            details["expected"] = expected
        if actual:
            details["actual"] = actual

        super().__init__(
            message,
            error_code=kwargs.pop("error_code", RAGErrorCodes.CONFIGURATION_ERROR),
            details=details,
            recoverable=False,
            **kwargs,
        )
        self.config_key = config_key
        self.expected = expected
        self.actual = actual


class RateLimitError(RAGError):
    """
    Rate limit exceeded errors.

    Raised when:
    - API rate limits are exceeded
    - Too many requests in time window

    Attributes:
        retry_after: Seconds to wait before retry
        limit_type: Type of limit (requests, tokens, etc.)
    """

    def __init__(
        self,
        message: str,
        retry_after: Optional[int] = None,
        limit_type: str = "requests",
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        if retry_after:
            details["retry_after"] = retry_after
        details["limit_type"] = limit_type

        super().__init__(
            message,
            error_code=kwargs.pop("error_code", RAGErrorCodes.RATE_LIMIT_EXCEEDED),
            details=details,
            recoverable=True,
            **kwargs,
        )
        self.retry_after = retry_after
        self.limit_type = limit_type


class CircuitBreakerOpenError(RAGError):
    """
    Circuit breaker is open - service temporarily unavailable.

    Raised when:
    - Too many consecutive failures
    - Service marked as unavailable

    Attributes:
        service: The service that tripped the circuit breaker
        recovery_time: When the circuit breaker will attempt recovery
    """

    def __init__(
        self,
        message: str,
        service: Optional[str] = None,
        recovery_time: Optional[float] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        if service:
            details["service"] = service
        if recovery_time:
            details["recovery_time"] = recovery_time

        super().__init__(
            message,
            error_code=kwargs.pop("error_code", RAGErrorCodes.CIRCUIT_BREAKER_OPEN),
            details=details,
            recoverable=True,
            **kwargs,
        )
        self.service = service
        self.recovery_time = recovery_time


# =============================================================================
# Error Codes
# =============================================================================

class RAGErrorCodes:
    """Error codes for RAG operations."""

    # General
    RAG_ERROR = "RAG_E000"

    # Embedding errors (E001-E099)
    EMBEDDING_FAILED = "RAG_E001"
    EMBEDDING_MODEL_NOT_FOUND = "RAG_E002"
    EMBEDDING_INPUT_TOO_LONG = "RAG_E003"
    EMBEDDING_BATCH_FAILED = "RAG_E004"

    # Vector search errors (E100-E199)
    VECTOR_SEARCH_FAILED = "RAG_E100"
    VECTOR_STORE_UNAVAILABLE = "RAG_E101"
    VECTOR_INDEX_NOT_FOUND = "RAG_E102"
    VECTOR_QUERY_TIMEOUT = "RAG_E103"

    # Graph query errors (E200-E299)
    GRAPH_QUERY_FAILED = "RAG_E200"
    GRAPH_CONNECTION_FAILED = "RAG_E201"
    GRAPH_CYPHER_SYNTAX_ERROR = "RAG_E202"
    GRAPH_QUERY_TIMEOUT = "RAG_E203"

    # Document processing errors (E300-E399)
    DOCUMENT_PROCESSING_FAILED = "RAG_E300"
    DOCUMENT_PARSE_ERROR = "RAG_E301"
    DOCUMENT_TOO_LARGE = "RAG_E302"
    DOCUMENT_INVALID_FORMAT = "RAG_E303"

    # Connection errors (E400-E499)
    CONNECTION_FAILED = "RAG_E400"
    CONNECTION_TIMEOUT = "RAG_E401"
    AUTHENTICATION_FAILED = "RAG_E402"

    # Configuration errors (E500-E599)
    CONFIGURATION_ERROR = "RAG_E500"
    MISSING_CONFIGURATION = "RAG_E501"
    INVALID_CONFIGURATION = "RAG_E502"

    # Rate limit and circuit breaker (E600-E699)
    RATE_LIMIT_EXCEEDED = "RAG_E600"
    CIRCUIT_BREAKER_OPEN = "RAG_E601"


# =============================================================================
# Helper Functions
# =============================================================================

def wrap_exception(
    original: Exception,
    rag_exception_class: type,
    message: Optional[str] = None,
    **kwargs,
) -> RAGError:
    """
    Wrap a generic exception in a RAG-specific exception.

    Args:
        original: The original exception
        rag_exception_class: The RAG exception class to use
        message: Custom message (uses original message if not provided)
        **kwargs: Additional arguments for the RAG exception

    Returns:
        RAG exception wrapping the original
    """
    msg = message or str(original)
    rag_error = rag_exception_class(msg, **kwargs)
    rag_error.__cause__ = original
    return rag_error


def is_retriable_error(error: Exception) -> bool:
    """
    Check if an error is potentially retriable.

    Args:
        error: The exception to check

    Returns:
        True if the error might succeed on retry
    """
    if isinstance(error, RAGError):
        return error.recoverable

    # Common retriable errors
    retriable_types = (
        ConnectionError,
        TimeoutError,
        OSError,  # Network errors
    )

    # Check for common retriable error messages
    retriable_messages = (
        "rate limit",
        "timeout",
        "connection",
        "unavailable",
        "temporarily",
        "retry",
        "overloaded",
    )

    if isinstance(error, retriable_types):
        return True

    error_str = str(error).lower()
    return any(msg in error_str for msg in retriable_messages)


def get_retry_delay(error: Exception, attempt: int = 1) -> float:
    """
    Calculate retry delay based on error type and attempt number.

    Args:
        error: The exception
        attempt: Current attempt number (1-based)

    Returns:
        Recommended delay in seconds
    """
    base_delay = 1.0

    if isinstance(error, RateLimitError) and error.retry_after:
        return float(error.retry_after)

    if isinstance(error, CircuitBreakerOpenError) and error.recovery_time:
        return error.recovery_time

    # Exponential backoff with jitter
    import random
    delay = base_delay * (2 ** (attempt - 1))
    jitter = random.uniform(0, delay * 0.1)
    return min(delay + jitter, 60.0)  # Cap at 60 seconds
