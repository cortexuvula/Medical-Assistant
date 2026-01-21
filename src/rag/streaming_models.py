"""
Streaming models for RAG system.

Provides event-based streaming for progressive result display
and cancellation support for long-running operations.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


class StreamEventType(Enum):
    """Types of events emitted during streaming RAG operations."""

    # Search phase events
    SEARCH_STARTED = "search_started"
    VECTOR_RESULTS = "vector_results"
    BM25_RESULTS = "bm25_results"
    GRAPH_RESULTS = "graph_results"
    SEARCH_COMPLETE = "search_complete"

    # Generation phase events
    GENERATION_STARTED = "generation_started"
    TOKEN = "token"  # Individual token during streaming generation
    GENERATION_COMPLETE = "generation_complete"

    # Status events
    PROGRESS = "progress"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class StreamEvent:
    """Event emitted during streaming RAG operations.

    Attributes:
        event_type: Type of the event
        data: Event-specific data payload
        progress_percent: Overall progress (0-100)
        timestamp: When the event occurred
        message: Human-readable status message
    """

    event_type: StreamEventType
    data: Optional[Any] = None
    progress_percent: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    message: str = ""

    def __post_init__(self):
        """Ensure timestamp is set."""
        if self.timestamp is None:
            self.timestamp = datetime.now()


class CancellationToken:
    """Thread-safe cancellation token for async operations.

    Usage:
        token = CancellationToken()

        # In worker thread:
        if token.is_cancelled:
            return  # Stop work

        # In main thread:
        token.cancel()  # Request cancellation
    """

    def __init__(self):
        """Initialize cancellation token."""
        self._cancelled = threading.Event()
        self._cancel_reason: Optional[str] = None
        self._lock = threading.Lock()

    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested.

        Returns:
            True if cancelled, False otherwise
        """
        return self._cancelled.is_set()

    @property
    def cancel_reason(self) -> Optional[str]:
        """Get the reason for cancellation.

        Returns:
            Cancellation reason string or None
        """
        with self._lock:
            return self._cancel_reason

    def cancel(self, reason: str = "User requested cancellation") -> None:
        """Request cancellation of the operation.

        Args:
            reason: Human-readable reason for cancellation
        """
        with self._lock:
            if not self._cancelled.is_set():
                self._cancel_reason = reason
                self._cancelled.set()

    def reset(self) -> None:
        """Reset the cancellation token for reuse.

        Warning: Only reset if you're sure no operations are using this token.
        """
        with self._lock:
            self._cancelled.clear()
            self._cancel_reason = None

    def raise_if_cancelled(self) -> None:
        """Raise CancellationError if cancellation was requested.

        Raises:
            CancellationError: If cancellation was requested
        """
        if self.is_cancelled:
            raise CancellationError(self._cancel_reason or "Operation cancelled")


class CancellationError(Exception):
    """Exception raised when an operation is cancelled."""

    def __init__(self, reason: str = "Operation cancelled"):
        """Initialize cancellation error.

        Args:
            reason: Human-readable cancellation reason
        """
        super().__init__(reason)
        self.reason = reason


# Type alias for streaming callbacks
StreamCallback = Callable[[StreamEvent], None]


@dataclass
class StreamingSearchRequest:
    """Request for streaming hybrid search.

    Attributes:
        query: Search query text
        top_k: Number of results to return
        use_graph_search: Whether to include graph search
        similarity_threshold: Minimum similarity score
        enable_query_expansion: Whether to expand medical terms
        enable_adaptive_threshold: Whether to use adaptive thresholds
        enable_bm25: Whether to include BM25 keyword search
        enable_mmr: Whether to apply MMR diversity reranking
        ef_search: HNSW ef_search parameter (None for default)
    """

    query: str
    top_k: int = 5
    use_graph_search: bool = True
    similarity_threshold: float = 0.3
    enable_query_expansion: bool = True
    enable_adaptive_threshold: bool = True
    enable_bm25: bool = True
    enable_mmr: bool = True
    ef_search: Optional[int] = None


@dataclass
class StreamingSearchState:
    """Internal state for streaming search operation.

    Tracks partial results as they arrive from different search sources.
    """

    request: StreamingSearchRequest
    cancellation_token: CancellationToken
    vector_results: list = field(default_factory=list)
    bm25_results: list = field(default_factory=list)
    graph_results: list = field(default_factory=list)
    merged_results: list = field(default_factory=list)
    query_embedding: Optional[list[float]] = None
    query_expansion: Optional[Any] = None
    start_time: datetime = field(default_factory=datetime.now)
    error: Optional[Exception] = None

    def __post_init__(self):
        """Ensure start_time is set."""
        if self.start_time is None:
            self.start_time = datetime.now()

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        delta = datetime.now() - self.start_time
        return delta.total_seconds() * 1000
