"""
RAG (Retrieval-Augmented Generation) Document Management System.

This package provides:
- Document upload and processing (PDF, DOCX, TXT, images)
- OCR for scanned documents
- OpenAI embeddings generation
- Neon PostgreSQL vector storage (pgvector)
- Graphiti knowledge graph integration
- Hybrid search combining vector similarity and graph relationships
"""

from src.rag.models import (
    DocumentChunk,
    DocumentListItem,
    DocumentMetadata,
    DocumentType,
    DocumentUploadProgress,
    DocumentUploadRequest,
    EmbeddingRequest,
    EmbeddingResponse,
    GraphSearchResult,
    HybridSearchResult,
    RAGDocument,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGSettings,
    UploadStatus,
    VectorSearchQuery,
    VectorSearchResult,
)

__all__ = [
    # Models
    "DocumentChunk",
    "DocumentListItem",
    "DocumentMetadata",
    "DocumentType",
    "DocumentUploadProgress",
    "DocumentUploadRequest",
    "EmbeddingRequest",
    "EmbeddingResponse",
    "GraphSearchResult",
    "HybridSearchResult",
    "RAGDocument",
    "RAGQueryRequest",
    "RAGQueryResponse",
    "RAGSettings",
    "UploadStatus",
    "VectorSearchQuery",
    "VectorSearchResult",
]
