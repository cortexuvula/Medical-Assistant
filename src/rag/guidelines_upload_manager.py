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

import hashlib
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
        expiration_date: Optional[date] = None,
        document_type: Optional[str] = None,
        title: Optional[str] = None,
        extract_recommendations: bool = True,
        enable_graph: bool = True,
        enable_ocr: bool = True,
        skip_duplicates: bool = True,
        progress_callback: Optional[Callable[[GuidelineUploadStatus, float, Optional[str]], None]] = None,
    ) -> Optional[str]:
        """Upload and process a single clinical guideline document.

        Args:
            file_path: Path to the guideline file
            specialty: Medical specialty (e.g. "cardiology")
            source: Source organization (e.g. "AHA/ACC")
            version: Guideline version string
            effective_date: When the guideline became effective
            expiration_date: When the guideline expires (optional)
            document_type: Type of guideline (e.g. "treatment_protocol")
            title: Human-readable title for the guideline
            extract_recommendations: Whether to tag recommendation sections
            enable_graph: Whether to sync to Neo4j knowledge graph
            enable_ocr: Whether to use OCR for scanned documents
            skip_duplicates: Skip if guideline with same title/source/version exists
            progress_callback: Callback(status, progress_percent, error_message)

        Returns:
            guideline_id if uploaded, None if skipped as duplicate
        """
        file_path = str(Path(file_path).resolve())
        filename = os.path.basename(file_path)

        # Generate title early for duplicate checking
        if not title:
            title = Path(file_path).stem

        # Pre-upload duplicate check (by filename/title/source/version - no content hash yet)
        if skip_duplicates:
            vector_store = self._get_vector_store()
            existing_id = vector_store.find_duplicate_guideline(
                title, source, version, filename=filename
            )
            if existing_id:
                logger.info(
                    f"Skipping duplicate guideline: '{title}' "
                    f"(filename: {filename}, source: {source}, version: {version})",
                    existing_id=existing_id
                )
                if progress_callback:
                    progress_callback(
                        GuidelineUploadStatus.COMPLETED,
                        100.0,
                        "Skipped (duplicate)"
                    )
                return None

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

            # Compute content hash for deduplication (Issue 16)
            content_hash = hashlib.md5(text.encode("utf-8")).hexdigest()

            # Post-extraction duplicate check by content hash
            if skip_duplicates:
                vector_store = self._get_vector_store()
                existing_id = vector_store.find_duplicate_guideline(
                    title, source, version, content_hash=content_hash
                )
                if existing_id:
                    logger.info(
                        f"Skipping duplicate guideline (content hash match): '{title}'",
                        existing_id=existing_id
                    )
                    if progress_callback:
                        progress_callback(
                            GuidelineUploadStatus.COMPLETED,
                            100.0,
                            "Skipped (duplicate content)"
                        )
                    return None

            # Content validation: warn if text doesn't look medical (Issue 12)
            content_warning = None
            try:
                content_warning = self._validate_medical_content(text[:5000])
            except Exception:
                pass  # Non-blocking

            # Use extracted metadata title as fallback
            if not title and metadata.title:
                title = metadata.title
            if not title:
                title = Path(file_path).stem

            report(GuidelineUploadStatus.EXTRACTING, 25)

            # --- Step 2: Chunk text (25-50%) ---
            report(GuidelineUploadStatus.CHUNKING, 30)

            # Try structure-aware chunking first, fall back to flat chunking
            guideline_chunks = None
            try:
                from rag.guidelines_chunker import GuidelinesChunker
                chunker = GuidelinesChunker(
                    max_chunk_tokens=GUIDELINES_CHUNK_SIZE,
                    overlap_tokens=GUIDELINES_CHUNK_OVERLAP,
                )
                guideline_chunks = chunker.chunk_text(text)
            except Exception as e:
                logger.debug(f"Structure-aware chunking not available, using fallback: {e}")

            if guideline_chunks:
                chunks = guideline_chunks
                use_structured_chunks = True
            else:
                chunks = processor.chunk_text(text)
                use_structured_chunks = False

            chunk_count = len(chunks)

            if chunk_count == 0:
                raise ValueError("Text chunking produced no chunks")

            logger.info(f"Guideline '{filename}' chunked into {chunk_count} pieces"
                        f" (structured={use_structured_chunks})")
            report(GuidelineUploadStatus.CHUNKING, 50)

            # --- Step 2b: Extract recommendation metadata (Issue 9) ---
            rec_extractor = None
            if extract_recommendations:
                try:
                    from rag.recommendation_extractor import RecommendationExtractor
                    rec_extractor = RecommendationExtractor()
                except Exception as e:
                    logger.debug(f"Recommendation extractor not available: {e}")

            # --- Step 3: Generate embeddings (50-75%) ---
            report(GuidelineUploadStatus.EMBEDDING, 55)

            embedding_manager = self._get_embedding_manager()
            if use_structured_chunks:
                chunk_texts = [c.chunk_text for c in chunks]
            else:
                chunk_texts = [c.chunk_text for c in chunks]
            embedding_response = embedding_manager.generate_embeddings(chunk_texts)

            report(GuidelineUploadStatus.EMBEDDING, 75)

            # --- Step 4: Store in Neon (75-90%) ---
            report(GuidelineUploadStatus.SYNCING, 78)

            vector_store = self._get_vector_store()

            # 4a: Insert guideline metadata row
            guideline_metadata = {
                "file_size_bytes": file_size,
                "page_count": page_count,
                "chunk_count": chunk_count,
                "ocr_used": ocr_used,
                "extract_recommendations": extract_recommendations,
                "structured_chunking": use_structured_chunks,
            }
            if content_warning:
                guideline_metadata["content_warning"] = content_warning

            self._insert_guideline_metadata(
                vector_store=vector_store,
                guideline_id=guideline_id,
                title=title,
                filename=filename,
                specialty=specialty or "general",
                source=source or "OTHER",
                version=version,
                effective_date=effective_date,
                expiration_date=expiration_date,
                document_type=document_type,
                file_path=file_path,
                content_hash=content_hash,
                metadata=guideline_metadata,
            )

            report(GuidelineUploadStatus.SYNCING, 82)

            # 4b: Upsert chunk embeddings
            batch_data = []
            for chunk, embedding in zip(chunks, embedding_response.embeddings):
                chunk_text = chunk.chunk_text
                chunk_idx = chunk.chunk_index
                token_count = getattr(chunk, 'token_count', len(chunk_text) // 4)

                # Extract recommendation metadata per chunk (Issue 9)
                section_type = "recommendation"
                recommendation_class = None
                evidence_level = None

                if rec_extractor:
                    try:
                        extraction = rec_extractor.extract(chunk_text)
                        section_type = extraction.section_type
                        recommendation_class = extraction.recommendation_class
                        evidence_level = extraction.evidence_level
                    except Exception:
                        pass

                # Use structured chunk metadata if available
                if use_structured_chunks and hasattr(chunk, 'section_heading'):
                    section_heading = chunk.section_heading
                    is_rec = getattr(chunk, 'is_recommendation', False)
                else:
                    section_heading = None
                    is_rec = False

                chunk_metadata = {
                    "filename": filename,
                    "chunk_index": chunk_idx,
                    "token_count": token_count,
                }
                if section_heading:
                    chunk_metadata["section_heading"] = section_heading
                if is_rec:
                    chunk_metadata["is_recommendation"] = True
                if content_warning:
                    chunk_metadata["content_warning"] = content_warning

                batch_data.append((
                    chunk_idx,               # chunk_index
                    chunk_text,              # chunk_text
                    embedding,               # embedding
                    section_type,            # section_type
                    recommendation_class,    # recommendation_class
                    evidence_level,          # evidence_level
                    chunk_metadata,          # metadata
                ))

            # Upsert embeddings with cleanup on failure (Issue 4/7)
            try:
                vector_store.upsert_embeddings_batch(guideline_id, batch_data)
            except Exception as embed_error:
                logger.error(f"Embedding upsert failed for '{filename}', cleaning up metadata")
                try:
                    vector_store.delete_guideline_complete(guideline_id)
                except Exception as cleanup_err:
                    logger.warning(f"Cleanup after embedding failure also failed: {cleanup_err}")
                raise embed_error

            # Mark neon_synced after successful embedding upsert (Issue 3)
            self._update_sync_status(vector_store, guideline_id, neon_synced=True)

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
                        # Mark neo4j_synced after successful graph sync (Issue 3)
                        self._update_sync_status(vector_store, guideline_id, neo4j_synced=True)
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
            return guideline_id

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
        filename: str,
        specialty: str,
        source: str,
        version: Optional[str],
        effective_date: Optional[date],
        expiration_date: Optional[date] = None,
        document_type: Optional[str] = None,
        file_path: Optional[str] = None,
        content_hash: Optional[str] = None,
        metadata: Optional[dict] = None,
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
                    (id, title, filename, specialty, source, version,
                     effective_date, expiration_date, document_type,
                     file_path, content_hash, metadata)
                    VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        filename = EXCLUDED.filename,
                        specialty = EXCLUDED.specialty,
                        source = EXCLUDED.source,
                        version = EXCLUDED.version,
                        effective_date = EXCLUDED.effective_date,
                        expiration_date = EXCLUDED.expiration_date,
                        document_type = EXCLUDED.document_type,
                        file_path = EXCLUDED.file_path,
                        content_hash = EXCLUDED.content_hash,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    """,
                    (
                        guideline_id,
                        title,
                        filename,
                        specialty,
                        source,
                        version,
                        effective_date,
                        expiration_date,
                        document_type,
                        file_path,
                        content_hash,
                        json.dumps(metadata) if metadata else None,
                    ),
                )
                conn.commit()

        logger.debug(f"Inserted guideline metadata for {guideline_id}")

    def _update_sync_status(
        self,
        vector_store,
        guideline_id: str,
        neon_synced: Optional[bool] = None,
        neo4j_synced: Optional[bool] = None,
    ) -> None:
        """Update sync status flags for a guideline (Issue 3).

        Args:
            vector_store: GuidelinesVectorStore instance
            guideline_id: UUID of the guideline
            neon_synced: Set neon_synced flag (True after embedding upsert succeeds)
            neo4j_synced: Set neo4j_synced flag (True after graph sync succeeds)
        """
        set_clauses = []
        params = []

        if neon_synced is not None:
            set_clauses.append("neon_synced = %s")
            params.append(neon_synced)
        if neo4j_synced is not None:
            set_clauses.append("neo4j_synced = %s")
            params.append(neo4j_synced)

        if not set_clauses:
            return

        set_clauses.append("updated_at = NOW()")
        params.append(guideline_id)

        pool = vector_store._get_pool()
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"UPDATE guidelines SET {', '.join(set_clauses)} WHERE id = %s::uuid",
                        params,
                    )
                    conn.commit()
        except Exception as e:
            logger.warning(f"Failed to update sync status for {guideline_id}: {e}")

    def _validate_medical_content(self, text: str) -> Optional[str]:
        """Validate that text appears to contain medical content (Issue 12).

        Uses simple heuristic: check for common medical terms.
        Returns a warning message if content doesn't look medical, None otherwise.
        Non-blocking - returns warning only, doesn't prevent upload.
        """
        medical_terms = {
            "patient", "treatment", "diagnosis", "clinical", "therapy",
            "medication", "drug", "dose", "symptom", "disease",
            "guideline", "recommendation", "evidence", "study",
            "risk", "benefit", "protocol", "management", "assessment",
            "blood", "heart", "lung", "kidney", "liver",
        }

        text_lower = text.lower()
        found = sum(1 for term in medical_terms if term in text_lower)

        if found < 3:
            warning = (
                f"Low medical content score ({found} medical terms found in first 5000 chars). "
                "This file may not be a clinical guideline."
            )
            logger.warning(warning)
            return warning
        return None


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
