"""
RAG (Retrieval-Augmented Generation) Document Management System.

This package provides:
- Document upload and processing (PDF, DOCX, TXT, images)
- OCR for scanned documents
- OpenAI embeddings generation
- Neon PostgreSQL vector storage (pgvector)
- Graphiti knowledge graph integration
- Hybrid search combining vector similarity and graph relationships

Search Quality Improvements:
- Adaptive similarity threshold
- Medical query expansion (synonyms and abbreviations)
- BM25 hybrid search (keyword-based)
- MMR result diversity (Maximal Marginal Relevance)
"""

from rag.models import (
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
    QueryExpansion,
    RAGDocument,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGSettings,
    UploadStatus,
    VectorSearchQuery,
    VectorSearchResult,
)

from rag.search_config import SearchQualityConfig, get_search_quality_config

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
    "QueryExpansion",
    "RAGDocument",
    "RAGQueryRequest",
    "RAGQueryResponse",
    "RAGSettings",
    "SearchQualityConfig",
    "UploadStatus",
    "VectorSearchQuery",
    "VectorSearchResult",
    # Functions
    "get_search_quality_config",
]
