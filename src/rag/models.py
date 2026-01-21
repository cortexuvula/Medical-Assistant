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
    bm25_score: float = 0.0  # BM25 keyword search score
    combined_score: float = 0.0
    mmr_score: float = 0.0  # MMR diversity-adjusted score
    feedback_boost: float = 0.0  # User feedback relevance boost
    related_entities: list[str] = Field(default_factory=list)
    metadata: Optional[dict[str, Any]] = None
    embedding: Optional[list[float]] = None  # For MMR computation


class QueryExpansion(BaseModel):
    """Tracks query expansion for medical terminology."""
    original_query: str
    expanded_terms: list[str] = Field(default_factory=list)
    abbreviation_expansions: dict[str, list[str]] = Field(default_factory=dict)
    synonym_expansions: dict[str, list[str]] = Field(default_factory=dict)
    expanded_query: str = ""

    def get_all_search_terms(self) -> list[str]:
        """Get all terms to search for (original + expanded)."""
        terms = [self.original_query]
        terms.extend(self.expanded_terms)
        for expansions in self.abbreviation_expansions.values():
            terms.extend(expansions)
        for expansions in self.synonym_expansions.values():
            terms.extend(expansions)
        return list(set(terms))


class RAGQueryRequest(BaseModel):
    """Request for RAG query."""
    query: str
    top_k: int = 5
    use_graph_search: bool = True
    similarity_threshold: float = 0.7
    include_metadata: bool = True
    enable_query_expansion: bool = True
    enable_adaptive_threshold: bool = True
    enable_bm25: bool = True
    enable_mmr: bool = True
    enable_feedback_boost: bool = True  # Apply user feedback relevance boosts
    enable_temporal_reasoning: bool = True  # Apply temporal decay and filtering


class TemporalInfo(BaseModel):
    """Temporal query information for response."""
    has_temporal_reference: bool = False
    time_frame: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    temporal_keywords: list[str] = Field(default_factory=list)
    decay_applied: bool = False


class RAGQueryResponse(BaseModel):
    """Response from RAG query."""
    query: str
    results: list[HybridSearchResult]
    total_results: int
    processing_time_ms: float
    context_text: str  # Formatted context for LLM
    query_expansion: Optional[QueryExpansion] = None  # Expansion info if enabled
    adaptive_threshold_used: Optional[float] = None  # Actual threshold used
    bm25_enabled: bool = False
    mmr_applied: bool = False
    feedback_boosts_applied: bool = False  # Whether user feedback boosts were applied
    temporal_info: Optional[TemporalInfo] = None  # Temporal reasoning info
    temporal_filtering_applied: bool = False  # Whether results were time-filtered


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

    # Search quality settings
    enable_adaptive_threshold: bool = True
    adaptive_min_threshold: float = 0.2
    adaptive_max_threshold: float = 0.8
    enable_query_expansion: bool = True
    enable_bm25: bool = True
    vector_weight: float = 0.5
    bm25_weight: float = 0.3
    graph_weight: float = 0.2
    enable_mmr: bool = True
    mmr_lambda: float = 0.7

    # HNSW index settings (pgvector approximate nearest neighbor)
    # m: Number of bi-directional links per node (higher = better recall, more memory)
    # ef_construction: Size of dynamic candidate list during build (higher = better quality)
    # ef_search: Size of dynamic candidate list during search (higher = better recall, slower)
    hnsw_m: int = 16  # Default for 10K-100K documents
    hnsw_ef_construction: int = 64  # Balance between build time and quality
    hnsw_ef_search: int = 40  # Fast default, increase for better recall

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
