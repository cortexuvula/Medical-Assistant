"""
Cancellation support for RAG operations.

Provides thread-safe cancellation tokens and errors for
async document uploads and other long-running operations.

Re-exports from streaming_models for consistency.
"""

# Re-export from streaming_models for convenience
from rag.streaming_models import CancellationError, CancellationToken

__all__ = ["CancellationToken", "CancellationError"]
