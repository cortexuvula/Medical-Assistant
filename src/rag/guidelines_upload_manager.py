"""
Guidelines Upload Manager.

Orchestrates the clinical guideline upload pipeline:
1. Validate file
2. Extract text (with OCR if needed)
3. Chunk text semantically (smaller chunks for guidelines)
4. Generate embeddings
5. Store metadata + embeddings in Neon PostgreSQL (guidelines DB)
6. Sync to Neo4j knowledge graph (optional)

Uses SEPARATE infrastructure from the main RAG system:
- CLINICAL_GUIDELINES_DATABASE_URL for Neon PostgreSQL
- CLINICAL_GUIDELINES_NEO4J_* for Neo4j knowledge graph
"""

import json
import os
import threading
from datetime import date
from pathlib import Path
from typing import Callable, Optional
from uuid import uuid4

from rag.guidelines_models import GuidelineUploadStatus
from utils.structured_logging import get_logger

logger = get_logger(__name__)

# Maximum file size (50 MB)
MAX_FILE_SIZE = 50 * 1024 * 1024

# Guidelines use smaller chunks than general RAG documents
GUIDELINES_CHUNK_SIZE = 300
GUIDELINES_CHUNK_OVERLAP = 50

# Supported file extensions
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md"}


class GuidelinesUploadManager:
    """Manages the clinical guideline upload lifecycle.

    Follows the same lazy-init singleton pattern as RAGDocumentManager
    but targets the separate guidelines database infrastructure.
    """

    def __init__(self):
        self._document_processor = None
        self._embedding_manager = None
        self._vector_store = None
        self._graphiti_client = None
        self._processing_lock = threading.Lock()

    def _get_document_processor(self):
        """Get document processor configured for guidelines (smaller chunks)."""
        if self._document_processor is None:
            from rag.document_processor import DocumentProcessor
            self._document_processor = DocumentProcessor(
                chunk_size_tokens=GUIDELINES_CHUNK_SIZE,
                chunk_overlap_tokens=GUIDELINES_CHUNK_OVERLAP,
            )
        return self._document_processor

    def _get_embedding_manager(self):
        """Get embedding manager (reuses CachedEmbeddingManager)."""
        if self._embedding_manager is None:
            from rag.embedding_manager import CachedEmbeddingManager
            self._embedding_manager = CachedEmbeddingManager()
        return self._embedding_manager

    def _get_vector_store(self):
        """Get guidelines vector store (separate from main RAG)."""
        if self._vector_store is None:
            from rag.guidelines_vector_store import get_guidelines_vector_store
            self._vector_store = get_guidelines_vector_store()
        return self._vector_store

    def _get_graphiti_client(self):
        """Get guidelines Graphiti client (separate Neo4j instance)."""
        if self._graphiti_client is None:
            try:
                from rag.guidelines_graphiti_client import get_guidelines_graphiti_client
                self._graphiti_client = get_guidelines_graphiti_client()
            except Exception:
                return None
        return self._graphiti_client

    def upload_guideline(
        self,
        file_path: str,
        specialty: Optional[str] = None,
        source: Optional[str] = None,
        version: Optional[str] = None,
        effective_date: Optional[date] = None,
        document_type: Optional[str] = None,
        title: Optional[str] = None,
        extract_recommendations: bool = True,
        enable_graph: bool = True,
        enable_ocr: bool = True,
        progress_callback: Optional[Callable[[GuidelineUploadStatus, float, Optional[str]], None]] = None,
    ) -> None:
        """Upload and process a single clinical guideline document.

        Args:
            file_path: Path to the guideline file
            specialty: Medical specialty (e.g. "cardiology")
            source: Source organization (e.g. "AHA/ACC")
            version: Guideline version string
            effective_date: When the guideline became effective
            document_type: Type of guideline (e.g. "treatment_protocol")
            title: Human-readable title for the guideline
            extract_recommendations: Whether to tag recommendation sections
            enable_graph: Whether to sync to Neo4j knowledge graph
            enable_ocr: Whether to use OCR for scanned documents
            progress_callback: Callback(status, progress_percent, error_message)
        """
        file_path = str(Path(file_path).resolve())
        filename = os.path.basename(file_path)
        guideline_id = str(uuid4())

        def report(status: GuidelineUploadStatus, progress: float, error: Optional[str] = None):
            if progress_callback:
                progress_callback(status, progress, error)

        try:
            # --- Validate ---
            report(GuidelineUploadStatus.PENDING, 0)

            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            file_size = os.path.getsize(file_path)
            if file_size > MAX_FILE_SIZE:
                raise ValueError(
                    f"File exceeds maximum size ({MAX_FILE_SIZE // (1024 * 1024)} MB)"
                )

            ext = Path(file_path).suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                raise ValueError(f"Unsupported file type: {ext}")

            # --- Step 1: Extract text (0-25%) ---
            report(GuidelineUploadStatus.EXTRACTING, 5)

            processor = self._get_document_processor()
            text, metadata, page_count, ocr_used = processor.extract_text(
                file_path, enable_ocr=enable_ocr
            )

            if not text or not text.strip():
                raise ValueError("No text could be extracted from the file")

            # Use extracted metadata title as fallback
            if not title and metadata.title:
                title = metadata.title
            if not title:
                title = Path(file_path).stem

            report(GuidelineUploadStatus.EXTRACTING, 25)

            # --- Step 2: Chunk text (25-50%) ---
            report(GuidelineUploadStatus.CHUNKING, 30)

            chunks = processor.chunk_text(text)
            chunk_count = len(chunks)

            if chunk_count == 0:
                raise ValueError("Text chunking produced no chunks")

            logger.info(f"Guideline '{filename}' chunked into {chunk_count} pieces")
            report(GuidelineUploadStatus.CHUNKING, 50)

            # --- Step 3: Generate embeddings (50-75%) ---
            report(GuidelineUploadStatus.EMBEDDING, 55)

            embedding_manager = self._get_embedding_manager()
            chunk_texts = [c.chunk_text for c in chunks]
            embedding_response = embedding_manager.generate_embeddings(chunk_texts)

            report(GuidelineUploadStatus.EMBEDDING, 75)

            # --- Step 4: Store in Neon (75-90%) ---
            report(GuidelineUploadStatus.SYNCING, 78)

            vector_store = self._get_vector_store()

            # 4a: Insert guideline metadata row
            self._insert_guideline_metadata(
                vector_store=vector_store,
                guideline_id=guideline_id,
                title=title,
                specialty=specialty or "general",
                source=source or "OTHER",
                version=version,
                effective_date=effective_date,
                document_type=document_type,
                file_path=file_path,
                metadata={
                    "filename": filename,
                    "file_size_bytes": file_size,
                    "page_count": page_count,
                    "chunk_count": chunk_count,
                    "ocr_used": ocr_used,
                    "extract_recommendations": extract_recommendations,
                },
            )

            report(GuidelineUploadStatus.SYNCING, 82)

            # 4b: Upsert chunk embeddings
            batch_data = []
            for chunk, embedding in zip(chunks, embedding_response.embeddings):
                chunk_metadata = {
                    "filename": filename,
                    "chunk_index": chunk.chunk_index,
                    "token_count": chunk.token_count,
                }
                batch_data.append((
                    chunk.chunk_index,       # chunk_index
                    chunk.chunk_text,        # chunk_text
                    embedding,               # embedding
                    "recommendation",        # section_type
                    None,                    # recommendation_class
                    None,                    # evidence_level
                    chunk_metadata,          # metadata
                ))

            vector_store.upsert_embeddings_batch(guideline_id, batch_data)

            report(GuidelineUploadStatus.SYNCING, 90)

            # --- Step 5: Sync to Neo4j knowledge graph (90-100%, optional) ---
            if enable_graph:
                graphiti = self._get_graphiti_client()
                if graphiti:
                    try:
                        report(GuidelineUploadStatus.SYNCING, 92)
                        graphiti.add_guideline_episode_sync(
                            guideline_id=guideline_id,
                            content=text,
                            metadata={
                                "title": title,
                                "source": source,
                                "version": version,
                                "specialty": specialty,
                                "document_type": document_type,
                            },
                            source_description="clinical_guideline",
                        )
                        logger.info(f"Synced guideline '{filename}' to knowledge graph")
                    except Exception as e:
                        logger.warning(f"Knowledge graph sync failed for '{filename}': {e}")
                        # Non-fatal: guideline is still usable without graph

            # --- Complete ---
            report(GuidelineUploadStatus.COMPLETED, 100)
            logger.info(
                f"Successfully uploaded guideline: {filename} "
                f"(id={guideline_id}, {chunk_count} chunks)"
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to upload guideline '{filename}': {error_msg}")
            report(GuidelineUploadStatus.FAILED, 0, error_msg)
            raise

    def _insert_guideline_metadata(
        self,
        vector_store,
        guideline_id: str,
        title: str,
        specialty: str,
        source: str,
        version: Optional[str],
        effective_date: Optional[date],
        document_type: Optional[str],
        file_path: Optional[str],
        metadata: Optional[dict],
    ) -> None:
        """Insert a row into the guidelines metadata table via the vector store's pool.

        The guidelines table stores document-level metadata (title, specialty, source, etc.)
        while guideline_embeddings stores the per-chunk vectors.
        """
        pool = vector_store._get_pool()

        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO guidelines
                    (id, title, specialty, source, version, effective_date,
                     document_type, file_path, metadata)
                    VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        specialty = EXCLUDED.specialty,
                        source = EXCLUDED.source,
                        version = EXCLUDED.version,
                        effective_date = EXCLUDED.effective_date,
                        document_type = EXCLUDED.document_type,
                        file_path = EXCLUDED.file_path,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    """,
                    (
                        guideline_id,
                        title,
                        specialty,
                        source,
                        version,
                        effective_date,
                        document_type,
                        file_path,
                        json.dumps(metadata) if metadata else None,
                    ),
                )
                conn.commit()

        logger.debug(f"Inserted guideline metadata for {guideline_id}")


# Singleton instance
_guidelines_upload_manager: Optional[GuidelinesUploadManager] = None


def get_guidelines_upload_manager() -> GuidelinesUploadManager:
    """Get the global guidelines upload manager instance.

    Returns:
        GuidelinesUploadManager instance
    """
    global _guidelines_upload_manager
    if _guidelines_upload_manager is None:
        _guidelines_upload_manager = GuidelinesUploadManager()
    return _guidelines_upload_manager


def reset_guidelines_upload_manager():
    """Reset the global guidelines upload manager instance."""
    global _guidelines_upload_manager
    _guidelines_upload_manager = None
