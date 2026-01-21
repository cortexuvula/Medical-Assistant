"""
Pydantic models for RAG document management system.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Supported document types for RAG processing."""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    IMAGE = "image"  # PNG, JPG, JPEG, TIFF, BMP


class UploadStatus(str, Enum):
    """Document upload and processing status."""
    PENDING = "pending"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    SYNCING = "syncing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentMetadata(BaseModel):
    """Metadata extracted from or associated with a document."""
    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    creation_date: Optional[datetime] = None
    modification_date: Optional[datetime] = None
    language: str = "en"
    category: Optional[str] = None
    custom_tags: list[str] = Field(default_factory=list)


class DocumentChunk(BaseModel):
    """A chunk of text extracted from a document."""
    chunk_index: int
    chunk_text: str
    token_count: int
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    neon_id: Optional[str] = None
    embedding: Optional[list[float]] = None


class RAGDocument(BaseModel):
    """A document in the RAG system."""
    document_id: str = Field(default_factory=lambda: str(uuid4()))
    filename: str
    file_type: DocumentType
    file_path: Optional[str] = None
    file_size_bytes: int = 0
    page_count: int = 0
    ocr_required: bool = False
    upload_status: UploadStatus = UploadStatus.PENDING
    chunk_count: int = 0
    neon_synced: bool = False
    graphiti_synced: bool = False
    error_message: Optional[str] = None
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    chunks: list[DocumentChunk] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        use_enum_values = True


class EmbeddingRequest(BaseModel):
    """Request for generating embeddings."""
    texts: list[str]
    model: str = "text-embedding-3-small"


class EmbeddingResponse(BaseModel):
    """Response from embedding generation."""
    embeddings: list[list[float]]
    model: str
    total_tokens: int


class VectorSearchQuery(BaseModel):
    """Query for vector similarity search."""
    query_text: str
    query_embedding: Optional[list[float]] = None
    top_k: int = 10
    similarity_threshold: float = 0.7
    filter_document_ids: Optional[list[str]] = None
    filter_metadata: Optional[dict[str, Any]] = None


class VectorSearchResult(BaseModel):
    """A single result from vector search."""
    document_id: str
    chunk_index: int
    chunk_text: str
    similarity_score: float
    metadata: Optional[dict[str, Any]] = None


class GraphSearchResult(BaseModel):
    """A result from knowledge graph search."""
    entity_name: str
    entity_type: str
    fact: str
    source_document_id: Optional[str] = None
    relevance_score: float = 0.0


class HybridSearchResult(BaseModel):
    """Combined result from hybrid search."""
    chunk_text: str
    document_id: str
    document_filename: str
    chunk_index: int
    vector_score: float = 0.0
    graph_score: float = 0.0
    combined_score: float = 0.0
    related_entities: list[str] = Field(default_factory=list)
    metadata: Optional[dict[str, Any]] = None


class RAGQueryRequest(BaseModel):
    """Request for RAG query."""
    query: str
    top_k: int = 5
    use_graph_search: bool = True
    similarity_threshold: float = 0.7
    include_metadata: bool = True


class RAGQueryResponse(BaseModel):
    """Response from RAG query."""
    query: str
    results: list[HybridSearchResult]
    total_results: int
    processing_time_ms: float
    context_text: str  # Formatted context for LLM


class DocumentUploadRequest(BaseModel):
    """Request for document upload."""
    file_paths: list[str]
    category: Optional[str] = None
    custom_tags: list[str] = Field(default_factory=list)
    enable_ocr: bool = True
    enable_graph: bool = True


class DocumentUploadProgress(BaseModel):
    """Progress update for document upload."""
    document_id: str
    filename: str
    status: UploadStatus
    progress_percent: float = 0.0
    current_step: str = ""
    error_message: Optional[str] = None


class DocumentListItem(BaseModel):
    """Summary item for document library display."""
    document_id: str
    filename: str
    file_type: DocumentType
    file_size_bytes: int
    page_count: int
    chunk_count: int
    upload_status: UploadStatus
    neon_synced: bool
    graphiti_synced: bool
    created_at: datetime
    category: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class RAGSettings(BaseModel):
    """Settings for RAG system configuration."""
    # Neon PostgreSQL settings
    neon_database_url: Optional[str] = None
    neon_pool_size: int = 5

    # OpenAI Embeddings settings
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    embedding_batch_size: int = 100

    # Chunking settings
    chunk_size_tokens: int = 500
    chunk_overlap_tokens: int = 50
    max_chunks_per_document: int = 1000

    # Search settings
    default_top_k: int = 5
    default_similarity_threshold: float = 0.7
    enable_graph_search: bool = True

    # Graphiti settings
    graphiti_neo4j_uri: Optional[str] = None
    graphiti_neo4j_user: Optional[str] = None
    graphiti_neo4j_password: Optional[str] = None

    # Processing settings
    max_file_size_mb: int = 50
    enable_ocr: bool = True
    ocr_language: str = "eng"
    supported_extensions: list[str] = Field(
        default_factory=lambda: [".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"]
    )
