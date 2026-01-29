"""
RAG Document Manager.

Orchestrates the document processing pipeline:
1. Upload and validate files
2. Extract text (with OCR if needed)
3. Chunk text semantically
4. Generate embeddings
5. Store in Neon vector database
6. Add to knowledge graph (optional)
"""

import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from uuid import uuid4

from src.rag.models import (
    DocumentChunk,
    DocumentListItem,
    DocumentMetadata,
    DocumentType,
    DocumentUploadProgress,
    RAGDocument,
    UploadStatus,
)
from rag.cancellation import CancellationError, CancellationToken

logger = logging.getLogger(__name__)

# Maximum file size (50 MB)
MAX_FILE_SIZE = 50 * 1024 * 1024


class RAGDocumentManager:
    """Manages RAG document lifecycle."""

    def __init__(
        self,
        db_manager=None,
        document_processor=None,
        embedding_manager=None,
        vector_store=None,
        graphiti_client=None,
    ):
        """Initialize RAG document manager.

        Args:
            db_manager: Database manager for local SQLite
            document_processor: DocumentProcessor instance
            embedding_manager: EmbeddingManager instance
            vector_store: NeonVectorStore instance
            graphiti_client: GraphitiClient instance (optional)
        """
        self._db_manager = db_manager
        self._document_processor = document_processor
        self._embedding_manager = embedding_manager
        self._vector_store = vector_store
        self._graphiti_client = graphiti_client
        self._processing_lock = threading.Lock()

    def _get_db_manager(self):
        """Get database manager."""
        if self._db_manager is None:
            from src.database.db_pool import get_db_manager
            self._db_manager = get_db_manager()
        return self._db_manager

    def _get_document_processor(self):
        """Get document processor."""
        if self._document_processor is None:
            from src.rag.document_processor import DocumentProcessor
            self._document_processor = DocumentProcessor()
        return self._document_processor

    def _get_embedding_manager(self):
        """Get embedding manager."""
        if self._embedding_manager is None:
            from src.rag.embedding_manager import CachedEmbeddingManager
            self._embedding_manager = CachedEmbeddingManager()
        return self._embedding_manager

    def _get_vector_store(self):
        """Get vector store."""
        if self._vector_store is None:
            from src.rag.neon_vector_store import get_vector_store
            self._vector_store = get_vector_store()
        return self._vector_store

    def _get_graphiti_client(self):
        """Get graphiti client."""
        if self._graphiti_client is None:
            try:
                from src.rag.graphiti_client import get_graphiti_client
                self._graphiti_client = get_graphiti_client()
            except Exception as e:
                logger.debug(f"Failed to get Graphiti client: {e}")
                return None
        return self._graphiti_client

    def upload_document(
        self,
        file_path: str,
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
        enable_ocr: bool = True,
        enable_graph: bool = True,
        progress_callback: Optional[Callable[[DocumentUploadProgress], None]] = None,
    ) -> RAGDocument:
        """Upload and process a single document.

        Args:
            file_path: Path to the document file
            category: Optional category
            tags: Optional list of tags
            enable_ocr: Whether to use OCR
            enable_graph: Whether to add to knowledge graph
            progress_callback: Optional callback for progress updates

        Returns:
            RAGDocument with processing results
        """
        file_path = str(Path(file_path).resolve())
        filename = os.path.basename(file_path)

        # Validate file
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE:
            raise ValueError(f"File exceeds maximum size ({MAX_FILE_SIZE // (1024*1024)} MB)")

        # Determine document type
        processor = self._get_document_processor()
        doc_type = processor.get_document_type(file_path)
        if not doc_type:
            raise ValueError(f"Unsupported file type: {filename}")

        # Create document record
        document_id = str(uuid4())
        doc = RAGDocument(
            document_id=document_id,
            filename=filename,
            file_type=doc_type,
            file_path=file_path,
            file_size_bytes=file_size,
            upload_status=UploadStatus.PENDING,
        )

        # Save initial record to database
        self._save_document_to_db(doc)

        # Report progress
        def report_progress(status: UploadStatus, progress: float, step: str = ""):
            doc.upload_status = status
            if progress_callback:
                progress_callback(DocumentUploadProgress(
                    document_id=document_id,
                    filename=filename,
                    status=status,
                    progress_percent=progress,
                    current_step=step,
                ))
            self._update_document_status(document_id, status)

        try:
            # Step 1: Extract text
            report_progress(UploadStatus.EXTRACTING, 10, "Extracting text...")

            text, metadata, page_count, ocr_used = processor.extract_text(
                file_path, enable_ocr=enable_ocr
            )

            doc.page_count = page_count
            doc.ocr_required = ocr_used
            doc.metadata = metadata
            if category:
                doc.metadata.category = category
            if tags:
                doc.metadata.custom_tags = tags

            # Step 2: Chunk text
            report_progress(UploadStatus.CHUNKING, 30, "Creating chunks...")

            chunks = processor.chunk_text(text)
            doc.chunks = chunks
            doc.chunk_count = len(chunks)

            # Save chunks to local database
            self._save_chunks_to_db(document_id, chunks)

            # Step 3: Generate embeddings
            report_progress(UploadStatus.EMBEDDING, 50, "Generating embeddings...")

            embedding_manager = self._get_embedding_manager()
            chunk_texts = [c.chunk_text for c in chunks]
            embedding_response = embedding_manager.generate_embeddings(chunk_texts)

            # Step 4: Sync to Neon
            report_progress(UploadStatus.SYNCING, 70, "Syncing to vector store...")

            vector_store = self._get_vector_store()

            # Prepare batch data
            batch_data = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embedding_response.embeddings)):
                chunk_metadata = {
                    "filename": filename,
                    "chunk_index": chunk.chunk_index,
                    "start_page": chunk.start_page,
                    "end_page": chunk.end_page,
                }
                if doc.metadata.category:
                    chunk_metadata["category"] = doc.metadata.category
                if doc.metadata.custom_tags:
                    chunk_metadata["tags"] = doc.metadata.custom_tags

                batch_data.append((
                    chunk.chunk_index,
                    chunk.chunk_text,
                    embedding,
                    chunk_metadata,
                ))

            # Upsert to Neon
            neon_ids = vector_store.upsert_embeddings_batch(document_id, batch_data)

            # Update chunk records with Neon IDs
            for chunk, neon_id in zip(chunks, neon_ids):
                chunk.neon_id = str(neon_id)

            doc.neon_synced = True

            # Step 5: Add to knowledge graph (optional) - runs in BACKGROUND
            if enable_graph:
                graphiti = self._get_graphiti_client()
                if graphiti:
                    # Start background thread for knowledge graph processing
                    graph_thread = threading.Thread(
                        target=self._process_knowledge_graph_background,
                        args=(document_id, text, filename, category, doc.metadata.title),
                        daemon=True,
                        name=f"graphiti-{document_id[:8]}",
                    )
                    graph_thread.start()
                    logger.info(f"Started background knowledge graph processing for {filename}")

            # Complete - document is usable now, graph processing continues in background
            report_progress(UploadStatus.COMPLETED, 100, "Complete")

            # Update final document record
            self._update_document_record(doc)

            logger.info(f"Successfully processed document: {filename} ({doc.chunk_count} chunks)")

        except Exception as e:
            doc.upload_status = UploadStatus.FAILED
            doc.error_message = str(e)
            self._update_document_status(document_id, UploadStatus.FAILED, str(e))
            logger.error(f"Failed to process document {filename}: {e}")

            if progress_callback:
                progress_callback(DocumentUploadProgress(
                    document_id=document_id,
                    filename=filename,
                    status=UploadStatus.FAILED,
                    progress_percent=0,
                    error_message=str(e),
                ))

        return doc

    def upload_document_async(
        self,
        file_path: str,
        options: Optional[dict] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Optional[dict]:
        """Upload and process a document with cancellation support.

        This method is designed to be called from RAGUploadQueueManager
        and supports cancellation at each processing step.

        Args:
            file_path: Path to the document file
            options: Upload options dict with keys:
                - category: Optional category
                - tags: Optional list of tags
                - enable_ocr: Whether to use OCR (default True)
                - enable_graph: Whether to add to knowledge graph (default True)
            progress_callback: Callback(status_message, progress_percent)
            cancellation_token: Token for cancellation support

        Returns:
            Dict with document_id and status, or None if cancelled/failed

        Raises:
            CancellationError: If cancelled during processing
        """
        options = options or {}
        category = options.get("category")
        tags = options.get("tags")
        enable_ocr = options.get("enable_ocr", True)
        enable_graph = options.get("enable_graph", True)

        file_path = str(Path(file_path).resolve())
        filename = os.path.basename(file_path)
        document_id = None

        def check_cancelled():
            """Check if cancelled and raise if so."""
            if cancellation_token:
                cancellation_token.raise_if_cancelled()

        def report(status: str, progress: float):
            """Report progress to callback."""
            if progress_callback:
                progress_callback(status, progress)

        try:
            # Validate file
            check_cancelled()

            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            file_size = os.path.getsize(file_path)
            if file_size > MAX_FILE_SIZE:
                raise ValueError(f"File exceeds maximum size ({MAX_FILE_SIZE // (1024*1024)} MB)")

            # Determine document type
            processor = self._get_document_processor()
            doc_type = processor.get_document_type(file_path)
            if not doc_type:
                raise ValueError(f"Unsupported file type: {filename}")

            # Create document record
            document_id = str(uuid4())
            doc = RAGDocument(
                document_id=document_id,
                filename=filename,
                file_type=doc_type,
                file_path=file_path,
                file_size_bytes=file_size,
                upload_status=UploadStatus.PENDING,
            )

            # Save initial record
            self._save_document_to_db(doc)
            report("Extracting text...", 10.0)

            # Step 1: Extract text
            check_cancelled()
            self._update_document_status(document_id, UploadStatus.EXTRACTING)

            text, metadata, page_count, ocr_used = processor.extract_text(
                file_path, enable_ocr=enable_ocr
            )

            doc.page_count = page_count
            doc.ocr_required = ocr_used
            doc.metadata = metadata
            if category:
                doc.metadata.category = category
            if tags:
                doc.metadata.custom_tags = tags

            # Step 2: Chunk text
            check_cancelled()
            report("Chunking text...", 30.0)
            self._update_document_status(document_id, UploadStatus.CHUNKING)

            chunks = processor.chunk_text(text)
            doc.chunks = chunks
            doc.chunk_count = len(chunks)

            # Save chunks to local database
            self._save_chunks_to_db(document_id, chunks)

            # Step 3: Generate embeddings
            check_cancelled()
            report("Generating embeddings...", 50.0)
            self._update_document_status(document_id, UploadStatus.EMBEDDING)

            embedding_manager = self._get_embedding_manager()
            chunk_texts = [c.chunk_text for c in chunks]
            embedding_response = embedding_manager.generate_embeddings(chunk_texts)

            # Step 4: Sync to Neon
            check_cancelled()
            report("Syncing to vector store...", 70.0)
            self._update_document_status(document_id, UploadStatus.SYNCING)

            vector_store = self._get_vector_store()

            # Prepare batch data
            batch_data = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embedding_response.embeddings)):
                chunk_metadata = {
                    "filename": filename,
                    "chunk_index": chunk.chunk_index,
                    "start_page": chunk.start_page,
                    "end_page": chunk.end_page,
                }
                if doc.metadata.category:
                    chunk_metadata["category"] = doc.metadata.category
                if doc.metadata.custom_tags:
                    chunk_metadata["tags"] = doc.metadata.custom_tags

                batch_data.append((
                    chunk.chunk_index,
                    chunk.chunk_text,
                    embedding,
                    chunk_metadata,
                ))

            # Upsert to Neon
            neon_ids = vector_store.upsert_embeddings_batch(document_id, batch_data)

            # Update chunk records with Neon IDs
            for chunk, neon_id in zip(chunks, neon_ids):
                chunk.neon_id = str(neon_id)

            doc.neon_synced = True

            # Step 5: Add to knowledge graph (optional) - runs in BACKGROUND
            if enable_graph:
                graphiti = self._get_graphiti_client()
                if graphiti:
                    # Start background thread for knowledge graph processing
                    graph_thread = threading.Thread(
                        target=self._process_knowledge_graph_background,
                        args=(document_id, text, filename, category, doc.metadata.title),
                        daemon=True,
                        name=f"graphiti-{document_id[:8]}",
                    )
                    graph_thread.start()
                    logger.info(f"Started background knowledge graph processing for {filename}")

            # Complete
            check_cancelled()
            report("Completing upload...", 90.0)

            doc.upload_status = UploadStatus.COMPLETED
            self._update_document_record(doc)

            logger.info(f"Async upload completed: {filename} ({doc.chunk_count} chunks)")

            return {
                "document_id": document_id,
                "filename": filename,
                "chunk_count": doc.chunk_count,
                "status": "completed",
            }

        except CancellationError as e:
            # Cancelled - rollback any partial data
            logger.info(f"Upload cancelled for {filename}: {e}")
            if document_id:
                self._rollback_upload(document_id)
            raise  # Re-raise for queue manager to handle

        except Exception as e:
            # Failed - mark as failed but keep record
            logger.error(f"Async upload failed for {filename}: {e}")
            if document_id:
                self._update_document_status(document_id, UploadStatus.FAILED, str(e))
            raise

    def _rollback_upload(self, document_id: str) -> bool:
        """Rollback a partial upload by deleting all associated data.

        Called when an upload is cancelled mid-process to ensure
        no orphaned data remains.

        Args:
            document_id: Document ID to rollback

        Returns:
            True if rollback successful, False otherwise
        """
        try:
            logger.info(f"Rolling back upload for document: {document_id}")

            # Delete from Neon vector store first
            try:
                vector_store = self._get_vector_store()
                vector_store.delete_document(document_id)
                logger.debug(f"Rolled back Neon data for {document_id}")
            except Exception as e:
                logger.warning(f"Could not rollback Neon data for {document_id}: {e}")

            # Delete from local database
            db = self._get_db_manager()

            # Delete chunks first (foreign key)
            db.execute(
                "DELETE FROM rag_document_chunks WHERE document_id = ?",
                (document_id,)
            )

            # Delete document record
            db.execute(
                "DELETE FROM rag_documents WHERE document_id = ?",
                (document_id,)
            )

            logger.info(f"Successfully rolled back upload for {document_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to rollback upload for {document_id}: {e}")
            return False

    def upload_documents_batch(
        self,
        file_paths: list[str],
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
        enable_ocr: bool = True,
        enable_graph: bool = True,
        progress_callback: Optional[Callable[[int, DocumentUploadProgress], None]] = None,
    ) -> list[RAGDocument]:
        """Upload multiple documents.

        Args:
            file_paths: List of file paths
            category: Optional category for all
            tags: Optional tags for all
            enable_ocr: Whether to use OCR
            enable_graph: Whether to add to knowledge graph
            progress_callback: Callback(file_index, progress)

        Returns:
            List of RAGDocument results
        """
        results = []

        for i, file_path in enumerate(file_paths):
            def file_progress(progress: DocumentUploadProgress, idx: int = i):
                if progress_callback:
                    progress_callback(idx, progress)

            try:
                doc = self.upload_document(
                    file_path=file_path,
                    category=category,
                    tags=tags,
                    enable_ocr=enable_ocr,
                    enable_graph=enable_graph,
                    progress_callback=file_progress,
                )
                results.append(doc)
            except Exception as e:
                logger.error(f"Failed to upload {file_path}: {e}")
                # Create failed document record
                doc = RAGDocument(
                    filename=os.path.basename(file_path),
                    file_type=DocumentType.TXT,  # Default
                    upload_status=UploadStatus.FAILED,
                    error_message=str(e),
                )
                results.append(doc)

        return results

    def delete_document(self, document_id: str) -> bool:
        """Delete a document and all its data.

        Args:
            document_id: Document ID to delete

        Returns:
            True if successful
        """
        try:
            # Delete from Neon
            vector_store = self._get_vector_store()
            vector_store.delete_document(document_id)

            # Delete from local database
            db = self._get_db_manager()

            # Delete chunks first (foreign key)
            db.execute(
                "DELETE FROM rag_document_chunks WHERE document_id = ?",
                (document_id,)
            )

            # Delete document
            db.execute(
                "DELETE FROM rag_documents WHERE document_id = ?",
                (document_id,)
            )

            logger.info(f"Deleted document: {document_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            return False

    def get_documents(
        self,
        status_filter: Optional[UploadStatus] = None,
        type_filter: Optional[DocumentType] = None,
        search_query: Optional[str] = None,
        limit: int = 100,
    ) -> list[DocumentListItem]:
        """Get list of documents.

        Args:
            status_filter: Filter by status
            type_filter: Filter by type
            search_query: Search in filename
            limit: Maximum results

        Returns:
            List of DocumentListItem
        """
        db = self._get_db_manager()

        query = """
            SELECT document_id, filename, file_type, file_size_bytes,
                   page_count, chunk_count, upload_status, neon_synced,
                   graphiti_synced, created_at, metadata_json
            FROM rag_documents
            WHERE 1=1
        """
        params = []

        if status_filter:
            query += " AND upload_status = ?"
            params.append(status_filter.value if hasattr(status_filter, 'value') else status_filter)

        if type_filter:
            query += " AND file_type = ?"
            params.append(type_filter.value if hasattr(type_filter, 'value') else type_filter)

        if search_query:
            query += " AND filename LIKE ?"
            params.append(f"%{search_query}%")

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = db.fetchall(query, tuple(params))

        documents = []
        for row in rows:
            metadata = {}
            if row[10]:  # metadata_json
                try:
                    metadata = json.loads(row[10])
                except Exception as e:
                    logger.debug(f"Failed to parse metadata JSON for document: {e}")

            documents.append(DocumentListItem(
                document_id=row[0],
                filename=row[1],
                file_type=DocumentType(row[2]) if row[2] else DocumentType.TXT,
                file_size_bytes=row[3] or 0,
                page_count=row[4] or 0,
                chunk_count=row[5] or 0,
                upload_status=UploadStatus(row[6]) if row[6] else UploadStatus.PENDING,
                neon_synced=bool(row[7]),
                graphiti_synced=bool(row[8]),
                created_at=datetime.fromisoformat(row[9]) if row[9] else datetime.now(),
                category=metadata.get("category"),
                tags=metadata.get("custom_tags", []),
            ))

        return documents

    def get_document_count(self) -> int:
        """Get total document count.

        Returns:
            Number of documents
        """
        db = self._get_db_manager()
        result = db.fetchone("SELECT COUNT(*) FROM rag_documents")
        return result[0] if result else 0

    def _save_document_to_db(self, doc: RAGDocument):
        """Save document record to local database."""
        db = self._get_db_manager()

        metadata_json = json.dumps({
            "title": doc.metadata.title,
            "author": doc.metadata.author,
            "subject": doc.metadata.subject,
            "keywords": doc.metadata.keywords,
            "category": doc.metadata.category,
            "custom_tags": doc.metadata.custom_tags,
        })

        db.execute(
            """
            INSERT INTO rag_documents
            (document_id, filename, file_type, file_path, file_size_bytes,
             page_count, ocr_required, upload_status, chunk_count,
             neon_synced, graphiti_synced, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                doc.document_id,
                doc.filename,
                doc.file_type.value if hasattr(doc.file_type, 'value') else doc.file_type,
                doc.file_path,
                doc.file_size_bytes,
                doc.page_count,
                doc.ocr_required,
                doc.upload_status.value if hasattr(doc.upload_status, 'value') else doc.upload_status,
                doc.chunk_count,
                doc.neon_synced,
                doc.graphiti_synced,
                metadata_json,
            )
        )

    def _save_chunks_to_db(self, document_id: str, chunks: list[DocumentChunk]):
        """Save chunks to local database."""
        db = self._get_db_manager()

        for chunk in chunks:
            db.execute(
                """
                INSERT INTO rag_document_chunks
                (document_id, chunk_index, chunk_text, token_count, start_page, end_page)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    chunk.chunk_index,
                    chunk.chunk_text,
                    chunk.token_count,
                    chunk.start_page,
                    chunk.end_page,
                )
            )

    def _update_document_status(
        self,
        document_id: str,
        status: UploadStatus,
        error_message: Optional[str] = None,
    ):
        """Update document status in database."""
        db = self._get_db_manager()

        if error_message:
            db.execute(
                """
                UPDATE rag_documents
                SET upload_status = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE document_id = ?
                """,
                (
                    status.value if hasattr(status, 'value') else status,
                    error_message,
                    document_id,
                )
            )
        else:
            db.execute(
                """
                UPDATE rag_documents
                SET upload_status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE document_id = ?
                """,
                (status.value if hasattr(status, 'value') else status, document_id)
            )

    def _process_knowledge_graph_background(
        self,
        document_id: str,
        text: str,
        filename: str,
        category: Optional[str],
        title: Optional[str],
    ):
        """Process knowledge graph in background thread.

        Args:
            document_id: Document ID
            text: Full document text
            filename: Document filename
            category: Document category
            title: Document title
        """
        try:
            logger.info(f"Background: Starting knowledge graph processing for {filename}")

            graphiti = self._get_graphiti_client()
            if not graphiti:
                logger.warning(f"Background: Graphiti client not available for {filename}")
                return

            # Add document to knowledge graph
            graphiti.add_document_episode_sync(
                document_id=document_id,
                content=text,
                metadata={
                    "filename": filename,
                    "category": category,
                    "title": title,
                },
                source_description="medical_document",
            )

            # Update database to mark graphiti_synced = True
            db = self._get_db_manager()
            db.execute(
                """
                UPDATE rag_documents
                SET graphiti_synced = 1, updated_at = CURRENT_TIMESTAMP
                WHERE document_id = ?
                """,
                (document_id,)
            )

            logger.info(f"Background: Completed knowledge graph processing for {filename}")

        except Exception as e:
            logger.error(f"Background: Knowledge graph processing failed for {filename}: {e}")
            # Don't update graphiti_synced - it stays False

    def sync_from_remote(self) -> int:
        """Sync document records from remote Neon into local SQLite.

        For each document in the remote vector store that is NOT already
        in the local rag_documents table, inserts a new record with
        status="synced" so it appears in the library dialog.

        Returns:
            Number of new documents synced
        """
        try:
            vector_store = self._get_vector_store()
            remote_docs = vector_store.get_remote_document_summaries()
        except Exception as e:
            logger.warning(f"Could not fetch remote document summaries: {e}")
            return 0

        if not remote_docs:
            return 0

        db = self._get_db_manager()
        synced_count = 0

        for rdoc in remote_docs:
            doc_id = rdoc["document_id"]

            # Check if already exists locally
            existing = db.fetchone(
                "SELECT document_id FROM rag_documents WHERE document_id = ?",
                (doc_id,)
            )
            if existing:
                continue

            # Insert a synced record
            metadata_json = json.dumps({
                "category": rdoc.get("category"),
                "custom_tags": rdoc.get("tags", []),
                "synced_from_remote": True,
            })

            try:
                db.execute(
                    """
                    INSERT INTO rag_documents
                    (document_id, filename, file_type, file_path, file_size_bytes,
                     page_count, ocr_required, upload_status, chunk_count,
                     neon_synced, graphiti_synced, metadata_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        doc_id,
                        rdoc.get("filename", "Unknown"),
                        "unknown",  # We don't know the original file type
                        None,       # No local file path
                        0,          # Unknown file size
                        0,          # Unknown page count
                        False,
                        UploadStatus.SYNCED.value,  # Distinguishes from locally-uploaded
                        rdoc.get("chunk_count", 0),
                        True,       # It's in Neon
                        False,
                        metadata_json,
                    )
                )
                synced_count += 1
            except Exception as e:
                logger.debug(f"Could not insert synced document {doc_id}: {e}")

        if synced_count > 0:
            logger.info(f"Synced {synced_count} document(s) from remote Neon store")

        return synced_count

    def _update_document_record(self, doc: RAGDocument):
        """Update full document record."""
        db = self._get_db_manager()

        metadata_json = json.dumps({
            "title": doc.metadata.title,
            "author": doc.metadata.author,
            "subject": doc.metadata.subject,
            "keywords": doc.metadata.keywords,
            "category": doc.metadata.category,
            "custom_tags": doc.metadata.custom_tags,
        })

        db.execute(
            """
            UPDATE rag_documents
            SET page_count = ?, ocr_required = ?, upload_status = ?,
                chunk_count = ?, neon_synced = ?, graphiti_synced = ?,
                metadata_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE document_id = ?
            """,
            (
                doc.page_count,
                doc.ocr_required,
                doc.upload_status.value if hasattr(doc.upload_status, 'value') else doc.upload_status,
                doc.chunk_count,
                doc.neon_synced,
                doc.graphiti_synced,
                metadata_json,
                doc.document_id,
            )
        )


# Singleton instance
_document_manager: Optional[RAGDocumentManager] = None


def get_rag_document_manager() -> RAGDocumentManager:
    """Get the global RAG document manager instance.

    Returns:
        RAGDocumentManager instance
    """
    global _document_manager
    if _document_manager is None:
        _document_manager = RAGDocumentManager()
    return _document_manager


def reset_rag_document_manager():
    """Reset the global RAG document manager instance."""
    global _document_manager
    _document_manager = None
