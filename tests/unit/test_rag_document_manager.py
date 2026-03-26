"""
Comprehensive unit tests for RAGDocumentManager.

Tests all public methods with happy path and error cases.
All external dependencies (database, vector store, embeddings, etc.) are mocked.
"""

import json
import os
import threading
from datetime import datetime
from unittest.mock import MagicMock, Mock, call, patch

import pytest

# We need to mock imports that happen inside the manager before importing it
import sys

# Ensure src is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from rag.models import (
    DocumentChunk,
    DocumentListItem,
    DocumentMetadata,
    DocumentType,
    DocumentUploadProgress,
    EmbeddingResponse,
    RAGDocument,
    UploadStatus,
)
from rag.streaming_models import CancellationError, CancellationToken
from managers.rag_document_manager import (
    MAX_FILE_SIZE,
    RAGDocumentManager,
    get_rag_document_manager,
    reset_rag_document_manager,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manager(
    db=None, processor=None, embedding=None, vector=None, graphiti=None,
):
    """Create a RAGDocumentManager with mocked dependencies."""
    return RAGDocumentManager(
        db_manager=db or MagicMock(),
        document_processor=processor or MagicMock(),
        embedding_manager=embedding or MagicMock(),
        vector_store=vector or MagicMock(),
        graphiti_client=graphiti,
    )


def _make_chunk(index=0, text="chunk text", tokens=10, start=1, end=1):
    return DocumentChunk(
        chunk_index=index,
        chunk_text=text,
        token_count=tokens,
        start_page=start,
        end_page=end,
    )


def _make_metadata():
    return DocumentMetadata(
        title="Test Doc",
        author="Author",
        category="cardiology",
        custom_tags=["tag1"],
    )


# ---------------------------------------------------------------------------
# Singleton tests
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_rag_document_manager_returns_instance(self):
        reset_rag_document_manager()
        with patch("managers.rag_document_manager.RAGDocumentManager") as cls:
            cls.return_value = MagicMock()
            mgr = get_rag_document_manager()
            assert mgr is not None
            # Second call returns same instance
            mgr2 = get_rag_document_manager()
            assert mgr is mgr2
        reset_rag_document_manager()

    def test_reset_clears_singleton(self):
        reset_rag_document_manager()
        with patch("managers.rag_document_manager.RAGDocumentManager") as cls:
            cls.return_value = MagicMock(name="first")
            first = get_rag_document_manager()
            reset_rag_document_manager()
            cls.return_value = MagicMock(name="second")
            second = get_rag_document_manager()
            assert first is not second
        reset_rag_document_manager()


# ---------------------------------------------------------------------------
# Lazy getter tests
# ---------------------------------------------------------------------------

class TestLazyGetters:
    def test_get_db_manager_lazy_import(self):
        mgr = RAGDocumentManager()  # no deps injected
        with patch("managers.rag_document_manager.get_db_manager", create=True) as mock_get:
            # Patch the import inside the method
            with patch.dict("sys.modules", {"database.db_pool": MagicMock(get_db_manager=mock_get)}):
                mock_get.return_value = MagicMock()
                db = mgr._get_db_manager()
                assert db is not None

    def test_get_graphiti_client_returns_none_on_failure(self):
        mgr = RAGDocumentManager()
        with patch.dict("sys.modules", {"rag.graphiti_client": None}):
            # Force an import error
            result = mgr._get_graphiti_client()
            # Should return None gracefully
            assert result is None


# ---------------------------------------------------------------------------
# upload_document tests
# ---------------------------------------------------------------------------

class TestUploadDocument:
    def test_upload_document_happy_path(self, tmp_path):
        # Create a temp file
        test_file = tmp_path / "test.pdf"
        test_file.write_text("sample content")

        db = MagicMock()
        processor = MagicMock()
        embedding = MagicMock()
        vector = MagicMock()

        chunks = [_make_chunk(0, "chunk 0"), _make_chunk(1, "chunk 1")]
        metadata = _make_metadata()

        processor.get_document_type.return_value = DocumentType.PDF
        processor.extract_text.return_value = ("full text", metadata, 5, False)
        processor.chunk_text.return_value = chunks

        embedding.generate_embeddings.return_value = EmbeddingResponse(
            embeddings=[[0.1, 0.2], [0.3, 0.4]],
            model="text-embedding-3-small",
            total_tokens=20,
        )

        vector.upsert_embeddings_batch.return_value = [101, 102]

        mgr = _make_manager(db=db, processor=processor, embedding=embedding, vector=vector)

        progress_calls = []
        doc = mgr.upload_document(
            file_path=str(test_file),
            category="cardiology",
            tags=["heart"],
            enable_graph=False,
            progress_callback=lambda p: progress_calls.append(p),
        )

        assert doc.upload_status == UploadStatus.COMPLETED
        assert doc.chunk_count == 2
        assert doc.neon_synced is True
        assert doc.page_count == 5
        assert doc.ocr_required is False
        assert len(progress_calls) > 0
        # Verify database calls
        assert db.execute.call_count >= 1
        vector.upsert_embeddings_batch.assert_called_once()

    def test_upload_document_file_not_found(self):
        mgr = _make_manager()
        with pytest.raises(FileNotFoundError, match="File not found"):
            mgr.upload_document(file_path="/nonexistent/file.pdf")

    def test_upload_document_file_too_large(self, tmp_path):
        test_file = tmp_path / "big.pdf"
        test_file.write_text("x")

        mgr = _make_manager()
        with patch("os.path.getsize", return_value=MAX_FILE_SIZE + 1):
            with pytest.raises(ValueError, match="exceeds maximum size"):
                mgr.upload_document(file_path=str(test_file))

    def test_upload_document_unsupported_type(self, tmp_path):
        test_file = tmp_path / "weird.xyz"
        test_file.write_text("data")

        processor = MagicMock()
        processor.get_document_type.return_value = None

        mgr = _make_manager(processor=processor)
        with pytest.raises(ValueError, match="Unsupported file type"):
            mgr.upload_document(file_path=str(test_file))

    def test_upload_document_extraction_failure(self, tmp_path):
        test_file = tmp_path / "bad.pdf"
        test_file.write_text("content")

        processor = MagicMock()
        processor.get_document_type.return_value = DocumentType.PDF
        processor.extract_text.side_effect = RuntimeError("OCR failed")

        db = MagicMock()
        mgr = _make_manager(db=db, processor=processor)

        progress_calls = []
        doc = mgr.upload_document(
            file_path=str(test_file),
            progress_callback=lambda p: progress_calls.append(p),
        )

        assert doc.upload_status == UploadStatus.FAILED
        assert doc.error_message == "OCR failed"
        # Should have a failed progress callback
        assert any(p.status == UploadStatus.FAILED for p in progress_calls)

    def test_upload_document_with_graph_enabled(self, tmp_path):
        test_file = tmp_path / "test.pdf"
        test_file.write_text("content")

        processor = MagicMock()
        processor.get_document_type.return_value = DocumentType.PDF
        processor.extract_text.return_value = ("text", _make_metadata(), 1, False)
        processor.chunk_text.return_value = [_make_chunk()]

        embedding = MagicMock()
        embedding.generate_embeddings.return_value = EmbeddingResponse(
            embeddings=[[0.1]], model="m", total_tokens=5,
        )

        vector = MagicMock()
        vector.upsert_embeddings_batch.return_value = [1]

        graphiti = MagicMock()
        mgr = _make_manager(
            processor=processor, embedding=embedding,
            vector=vector, graphiti=graphiti,
        )

        with patch("threading.Thread") as mock_thread_cls:
            mock_thread_instance = MagicMock()
            mock_thread_cls.return_value = mock_thread_instance

            doc = mgr.upload_document(str(test_file), enable_graph=True)

            # Graph thread should have been started
            mock_thread_cls.assert_called_once()
            mock_thread_instance.start.assert_called_once()
            assert doc.upload_status == UploadStatus.COMPLETED

    def test_upload_document_embedding_failure(self, tmp_path):
        test_file = tmp_path / "test.pdf"
        test_file.write_text("content")

        processor = MagicMock()
        processor.get_document_type.return_value = DocumentType.PDF
        processor.extract_text.return_value = ("text", _make_metadata(), 1, False)
        processor.chunk_text.return_value = [_make_chunk()]

        embedding = MagicMock()
        embedding.generate_embeddings.side_effect = RuntimeError("API error")

        db = MagicMock()
        mgr = _make_manager(db=db, processor=processor, embedding=embedding)

        doc = mgr.upload_document(str(test_file))
        assert doc.upload_status == UploadStatus.FAILED
        assert "API error" in doc.error_message

    def test_upload_document_category_and_tags_applied(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        processor = MagicMock()
        processor.get_document_type.return_value = DocumentType.TXT
        meta = DocumentMetadata()
        processor.extract_text.return_value = ("text", meta, 1, False)
        processor.chunk_text.return_value = [_make_chunk()]

        embedding = MagicMock()
        embedding.generate_embeddings.return_value = EmbeddingResponse(
            embeddings=[[0.1]], model="m", total_tokens=5,
        )
        vector = MagicMock()
        vector.upsert_embeddings_batch.return_value = [1]

        mgr = _make_manager(processor=processor, embedding=embedding, vector=vector)

        doc = mgr.upload_document(
            str(test_file),
            category="neurology",
            tags=["brain", "mri"],
            enable_graph=False,
        )

        assert doc.metadata.category == "neurology"
        assert doc.metadata.custom_tags == ["brain", "mri"]


# ---------------------------------------------------------------------------
# upload_document_async tests
# ---------------------------------------------------------------------------

class TestUploadDocumentAsync:
    def test_async_happy_path(self, tmp_path):
        test_file = tmp_path / "test.pdf"
        test_file.write_text("content")

        processor = MagicMock()
        processor.get_document_type.return_value = DocumentType.PDF
        processor.extract_text.return_value = ("text", _make_metadata(), 2, False)
        processor.chunk_text.return_value = [_make_chunk(0), _make_chunk(1)]

        embedding = MagicMock()
        embedding.generate_embeddings.return_value = EmbeddingResponse(
            embeddings=[[0.1], [0.2]], model="m", total_tokens=10,
        )

        vector = MagicMock()
        vector.upsert_embeddings_batch.return_value = [10, 20]

        db = MagicMock()
        mgr = _make_manager(db=db, processor=processor, embedding=embedding, vector=vector)

        progress_reports = []
        result = mgr.upload_document_async(
            file_path=str(test_file),
            options={"category": "test", "tags": ["t"], "enable_graph": False},
            progress_callback=lambda s, p: progress_reports.append((s, p)),
        )

        assert result is not None
        assert result["status"] == "completed"
        assert result["chunk_count"] == 2
        assert len(progress_reports) > 0

    def test_async_cancellation(self, tmp_path):
        test_file = tmp_path / "test.pdf"
        test_file.write_text("content")

        token = CancellationToken()
        token.cancel("User cancelled")

        db = MagicMock()
        mgr = _make_manager(db=db)

        with pytest.raises(CancellationError):
            mgr.upload_document_async(
                file_path=str(test_file),
                cancellation_token=token,
            )

        # Should have attempted rollback (document_id is None at cancellation point
        # so rollback may not be called if cancelled before document creation)

    def test_async_cancellation_after_extraction(self, tmp_path):
        test_file = tmp_path / "test.pdf"
        test_file.write_text("content")

        processor = MagicMock()
        processor.get_document_type.return_value = DocumentType.PDF
        processor.extract_text.return_value = ("text", _make_metadata(), 1, False)

        token = CancellationToken()
        call_count = 0

        original_raise = token.raise_if_cancelled

        def cancel_on_second_check():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                token.cancel("Cancelled mid-process")
            original_raise()

        token.raise_if_cancelled = cancel_on_second_check

        db = MagicMock()
        mgr = _make_manager(db=db, processor=processor)

        with pytest.raises(CancellationError):
            mgr.upload_document_async(
                file_path=str(test_file),
                options={"enable_graph": False},
                cancellation_token=token,
            )

        # Rollback should have been called since document_id was set
        db.execute.assert_called()

    def test_async_file_not_found(self):
        mgr = _make_manager()
        with pytest.raises(FileNotFoundError):
            mgr.upload_document_async(file_path="/no/such/file.pdf")

    def test_async_file_too_large(self, tmp_path):
        test_file = tmp_path / "big.pdf"
        test_file.write_text("x")

        mgr = _make_manager()
        with patch("os.path.getsize", return_value=MAX_FILE_SIZE + 1):
            with pytest.raises(ValueError, match="exceeds maximum size"):
                mgr.upload_document_async(file_path=str(test_file))

    def test_async_unsupported_type(self, tmp_path):
        test_file = tmp_path / "file.xyz"
        test_file.write_text("data")

        processor = MagicMock()
        processor.get_document_type.return_value = None

        mgr = _make_manager(processor=processor)
        with pytest.raises(ValueError, match="Unsupported file type"):
            mgr.upload_document_async(file_path=str(test_file))

    def test_async_embedding_failure_marks_failed(self, tmp_path):
        test_file = tmp_path / "test.pdf"
        test_file.write_text("content")

        processor = MagicMock()
        processor.get_document_type.return_value = DocumentType.PDF
        processor.extract_text.return_value = ("text", _make_metadata(), 1, False)
        processor.chunk_text.return_value = [_make_chunk()]

        embedding = MagicMock()
        embedding.generate_embeddings.side_effect = RuntimeError("Embedding API down")

        db = MagicMock()
        mgr = _make_manager(db=db, processor=processor, embedding=embedding)

        with pytest.raises(RuntimeError, match="Embedding API down"):
            mgr.upload_document_async(file_path=str(test_file))

        # Should have updated status to FAILED
        # Find the call that sets FAILED status
        failed_calls = [
            c for c in db.execute.call_args_list
            if len(c.args) >= 2 and isinstance(c.args[1], tuple) and "failed" in str(c.args[1])
        ]
        assert len(failed_calls) > 0

    def test_async_default_options(self, tmp_path):
        """Options default to empty dict when None."""
        test_file = tmp_path / "test.pdf"
        test_file.write_text("content")

        processor = MagicMock()
        processor.get_document_type.return_value = DocumentType.PDF
        processor.extract_text.return_value = ("text", DocumentMetadata(), 1, False)
        processor.chunk_text.return_value = [_make_chunk()]

        embedding = MagicMock()
        embedding.generate_embeddings.return_value = EmbeddingResponse(
            embeddings=[[0.1]], model="m", total_tokens=5,
        )
        vector = MagicMock()
        vector.upsert_embeddings_batch.return_value = [1]

        mgr = _make_manager(processor=processor, embedding=embedding, vector=vector)

        with patch("threading.Thread") as mock_thread_cls:
            mock_thread_cls.return_value = MagicMock()
            result = mgr.upload_document_async(str(test_file), options=None)

        assert result["status"] == "completed"


# ---------------------------------------------------------------------------
# rollback_upload tests
# ---------------------------------------------------------------------------

class TestRollbackUpload:
    def test_rollback_success(self):
        db = MagicMock()
        vector = MagicMock()
        mgr = _make_manager(db=db, vector=vector)

        result = mgr._rollback_upload("doc-123")

        assert result is True
        vector.delete_document.assert_called_once_with("doc-123")
        assert db.execute.call_count == 2  # chunks + document

    def test_rollback_neon_failure_continues(self):
        db = MagicMock()
        vector = MagicMock()
        vector.delete_document.side_effect = RuntimeError("Neon down")
        mgr = _make_manager(db=db, vector=vector)

        result = mgr._rollback_upload("doc-123")

        # Should still succeed (neon failure is warned but not fatal)
        assert result is True
        assert db.execute.call_count == 2

    def test_rollback_db_failure(self):
        db = MagicMock()
        db.execute.side_effect = RuntimeError("DB error")
        vector = MagicMock()
        mgr = _make_manager(db=db, vector=vector)

        result = mgr._rollback_upload("doc-123")
        assert result is False


# ---------------------------------------------------------------------------
# upload_documents_batch tests
# ---------------------------------------------------------------------------

class TestUploadDocumentsBatch:
    def test_batch_all_success(self, tmp_path):
        files = []
        for i in range(3):
            f = tmp_path / f"doc{i}.txt"
            f.write_text(f"content {i}")
            files.append(str(f))

        processor = MagicMock()
        processor.get_document_type.return_value = DocumentType.TXT
        processor.extract_text.return_value = ("text", DocumentMetadata(), 1, False)
        processor.chunk_text.return_value = [_make_chunk()]

        embedding = MagicMock()
        embedding.generate_embeddings.return_value = EmbeddingResponse(
            embeddings=[[0.1]], model="m", total_tokens=5,
        )
        vector = MagicMock()
        vector.upsert_embeddings_batch.return_value = [1]

        mgr = _make_manager(processor=processor, embedding=embedding, vector=vector)

        results = mgr.upload_documents_batch(
            files, enable_graph=False,
        )

        assert len(results) == 3
        assert all(d.upload_status == UploadStatus.COMPLETED for d in results)

    def test_batch_one_failure(self, tmp_path):
        good = tmp_path / "good.txt"
        good.write_text("ok")

        processor = MagicMock()
        processor.get_document_type.return_value = DocumentType.TXT
        processor.extract_text.return_value = ("text", DocumentMetadata(), 1, False)
        processor.chunk_text.return_value = [_make_chunk()]

        embedding = MagicMock()
        embedding.generate_embeddings.return_value = EmbeddingResponse(
            embeddings=[[0.1]], model="m", total_tokens=5,
        )
        vector = MagicMock()
        vector.upsert_embeddings_batch.return_value = [1]

        mgr = _make_manager(processor=processor, embedding=embedding, vector=vector)

        results = mgr.upload_documents_batch(
            ["/nonexistent/file.pdf", str(good)],
            enable_graph=False,
        )

        assert len(results) == 2
        assert results[0].upload_status == UploadStatus.FAILED
        assert results[1].upload_status == UploadStatus.COMPLETED

    def test_batch_with_progress_callback(self, tmp_path):
        f = tmp_path / "doc.txt"
        f.write_text("text")

        processor = MagicMock()
        processor.get_document_type.return_value = DocumentType.TXT
        processor.extract_text.return_value = ("text", DocumentMetadata(), 1, False)
        processor.chunk_text.return_value = [_make_chunk()]

        embedding = MagicMock()
        embedding.generate_embeddings.return_value = EmbeddingResponse(
            embeddings=[[0.1]], model="m", total_tokens=5,
        )
        vector = MagicMock()
        vector.upsert_embeddings_batch.return_value = [1]

        mgr = _make_manager(processor=processor, embedding=embedding, vector=vector)

        batch_progress = []
        results = mgr.upload_documents_batch(
            [str(f)],
            enable_graph=False,
            progress_callback=lambda idx, prog: batch_progress.append((idx, prog)),
        )

        assert len(results) == 1
        assert len(batch_progress) > 0
        # All progress calls should have index 0
        assert all(idx == 0 for idx, _ in batch_progress)

    def test_batch_empty_list(self):
        mgr = _make_manager()
        results = mgr.upload_documents_batch([])
        assert results == []


# ---------------------------------------------------------------------------
# delete_document tests
# ---------------------------------------------------------------------------

class TestDeleteDocument:
    def test_delete_success(self):
        db = MagicMock()
        vector = MagicMock()
        mgr = _make_manager(db=db, vector=vector)

        result = mgr.delete_document("doc-456")

        assert result is True
        vector.delete_document.assert_called_once_with("doc-456")
        assert db.execute.call_count == 2

    def test_delete_failure(self):
        db = MagicMock()
        vector = MagicMock()
        vector.delete_document.side_effect = RuntimeError("fail")
        mgr = _make_manager(db=db, vector=vector)

        result = mgr.delete_document("doc-456")
        assert result is False


# ---------------------------------------------------------------------------
# get_documents tests
# ---------------------------------------------------------------------------

class TestGetDocuments:
    def _make_row(self, doc_id="d1", filename="test.pdf", file_type="pdf",
                  size=1000, pages=5, chunks=10, status="completed",
                  neon=1, graphiti=0, created="2026-01-01T00:00:00",
                  metadata_json=None):
        if metadata_json is None:
            metadata_json = json.dumps({"category": "cardio", "custom_tags": ["tag1"]})
        return (doc_id, filename, file_type, size, pages, chunks, status,
                neon, graphiti, created, metadata_json)

    def test_get_documents_no_filters(self):
        db = MagicMock()
        db.fetchall.return_value = [self._make_row()]

        mgr = _make_manager(db=db)
        docs = mgr.get_documents()

        assert len(docs) == 1
        assert docs[0].document_id == "d1"
        assert docs[0].filename == "test.pdf"
        assert docs[0].file_type == DocumentType.PDF
        assert docs[0].category == "cardio"
        assert docs[0].tags == ["tag1"]
        assert docs[0].neon_synced is True
        assert docs[0].graphiti_synced is False

    def test_get_documents_with_status_filter(self):
        db = MagicMock()
        db.fetchall.return_value = []

        mgr = _make_manager(db=db)
        mgr.get_documents(status_filter=UploadStatus.COMPLETED)

        query_arg = db.fetchall.call_args[0][0]
        assert "upload_status = ?" in query_arg
        params = db.fetchall.call_args[0][1]
        assert "completed" in params

    def test_get_documents_with_type_filter(self):
        db = MagicMock()
        db.fetchall.return_value = []

        mgr = _make_manager(db=db)
        mgr.get_documents(type_filter=DocumentType.PDF)

        query_arg = db.fetchall.call_args[0][0]
        assert "file_type = ?" in query_arg

    def test_get_documents_with_search_query(self):
        db = MagicMock()
        db.fetchall.return_value = []

        mgr = _make_manager(db=db)
        mgr.get_documents(search_query="cardiology")

        query_arg = db.fetchall.call_args[0][0]
        assert "filename LIKE ?" in query_arg
        params = db.fetchall.call_args[0][1]
        assert "%cardiology%" in params

    def test_get_documents_with_all_filters(self):
        db = MagicMock()
        db.fetchall.return_value = []

        mgr = _make_manager(db=db)
        mgr.get_documents(
            status_filter=UploadStatus.COMPLETED,
            type_filter=DocumentType.PDF,
            search_query="test",
            limit=50,
        )

        params = db.fetchall.call_args[0][1]
        assert len(params) == 4  # status, type, search, limit

    def test_get_documents_invalid_metadata_json(self):
        db = MagicMock()
        row = self._make_row(metadata_json="not valid json")
        db.fetchall.return_value = [row]

        mgr = _make_manager(db=db)
        docs = mgr.get_documents()

        assert len(docs) == 1
        assert docs[0].category is None
        assert docs[0].tags == []

    def test_get_documents_none_metadata_json(self):
        db = MagicMock()
        row = ("d1", "test.pdf", "pdf", 100, 1, 1, "completed", 1, 0,
               "2026-01-01T00:00:00", None)
        db.fetchall.return_value = [row]

        mgr = _make_manager(db=db)
        docs = mgr.get_documents()

        assert len(docs) == 1
        assert docs[0].category is None

    def test_get_documents_empty_result(self):
        db = MagicMock()
        db.fetchall.return_value = []

        mgr = _make_manager(db=db)
        docs = mgr.get_documents()
        assert docs == []

    def test_get_documents_null_fields_handled(self):
        """Test that None values in row fields are handled gracefully."""
        db = MagicMock()
        row = ("d1", "test.pdf", None, None, None, None, None, 0, 0, None, None)
        db.fetchall.return_value = [row]

        mgr = _make_manager(db=db)
        docs = mgr.get_documents()

        assert len(docs) == 1
        assert docs[0].file_type == DocumentType.TXT  # default
        assert docs[0].file_size_bytes == 0
        assert docs[0].upload_status == UploadStatus.PENDING  # default


# ---------------------------------------------------------------------------
# get_document_count tests
# ---------------------------------------------------------------------------

class TestGetDocumentCount:
    def test_returns_count(self):
        db = MagicMock()
        db.fetchone.return_value = (42,)

        mgr = _make_manager(db=db)
        assert mgr.get_document_count() == 42

    def test_returns_zero_on_none(self):
        db = MagicMock()
        db.fetchone.return_value = None

        mgr = _make_manager(db=db)
        assert mgr.get_document_count() == 0


# ---------------------------------------------------------------------------
# _save_document_to_db tests
# ---------------------------------------------------------------------------

class TestSaveDocumentToDb:
    def test_save_document_calls_execute(self):
        db = MagicMock()
        mgr = _make_manager(db=db)

        doc = RAGDocument(
            document_id="test-id",
            filename="test.pdf",
            file_type=DocumentType.PDF,
            file_path="/tmp/test.pdf",
            file_size_bytes=1000,
            metadata=DocumentMetadata(
                title="Title", author="Author", category="cat",
                custom_tags=["t1"],
            ),
        )

        mgr._save_document_to_db(doc)

        db.execute.assert_called_once()
        args = db.execute.call_args[0]
        assert "INSERT INTO rag_documents" in args[0]
        params = args[1]
        assert params[0] == "test-id"
        assert params[1] == "test.pdf"

    def test_save_document_metadata_json_serialized(self):
        db = MagicMock()
        mgr = _make_manager(db=db)

        doc = RAGDocument(
            filename="doc.txt",
            file_type=DocumentType.TXT,
            metadata=DocumentMetadata(title="My Title", custom_tags=["a", "b"]),
        )
        mgr._save_document_to_db(doc)

        params = db.execute.call_args[0][1]
        metadata_json = params[11]  # metadata_json is the 12th param
        parsed = json.loads(metadata_json)
        assert parsed["title"] == "My Title"
        assert parsed["custom_tags"] == ["a", "b"]


# ---------------------------------------------------------------------------
# _save_chunks_to_db tests
# ---------------------------------------------------------------------------

class TestSaveChunksToDb:
    def test_saves_all_chunks(self):
        db = MagicMock()
        mgr = _make_manager(db=db)

        chunks = [_make_chunk(0, "a"), _make_chunk(1, "b"), _make_chunk(2, "c")]
        mgr._save_chunks_to_db("doc-1", chunks)

        assert db.execute.call_count == 3

    def test_saves_zero_chunks(self):
        db = MagicMock()
        mgr = _make_manager(db=db)

        mgr._save_chunks_to_db("doc-1", [])
        db.execute.assert_not_called()


# ---------------------------------------------------------------------------
# _update_document_status tests
# ---------------------------------------------------------------------------

class TestUpdateDocumentStatus:
    def test_update_status_without_error(self):
        db = MagicMock()
        mgr = _make_manager(db=db)

        mgr._update_document_status("doc-1", UploadStatus.EXTRACTING)

        db.execute.assert_called_once()
        query = db.execute.call_args[0][0]
        assert "error_message" not in query
        params = db.execute.call_args[0][1]
        assert params[0] == "extracting"

    def test_update_status_with_error(self):
        db = MagicMock()
        mgr = _make_manager(db=db)

        mgr._update_document_status("doc-1", UploadStatus.FAILED, "Something broke")

        db.execute.assert_called_once()
        query = db.execute.call_args[0][0]
        assert "error_message" in query
        params = db.execute.call_args[0][1]
        assert "failed" in params
        assert "Something broke" in params


# ---------------------------------------------------------------------------
# _update_document_record tests
# ---------------------------------------------------------------------------

class TestUpdateDocumentRecord:
    def test_updates_full_record(self):
        db = MagicMock()
        mgr = _make_manager(db=db)

        doc = RAGDocument(
            document_id="doc-1",
            filename="test.pdf",
            file_type=DocumentType.PDF,
            page_count=10,
            chunk_count=5,
            neon_synced=True,
            upload_status=UploadStatus.COMPLETED,
            metadata=DocumentMetadata(title="T", category="c"),
        )

        mgr._update_document_record(doc)

        db.execute.assert_called_once()
        query = db.execute.call_args[0][0]
        assert "UPDATE rag_documents" in query
        params = db.execute.call_args[0][1]
        assert params[0] == 10  # page_count
        assert params[-1] == "doc-1"  # document_id in WHERE


# ---------------------------------------------------------------------------
# _process_knowledge_graph_background tests
# ---------------------------------------------------------------------------

class TestProcessKnowledgeGraphBackground:
    def test_happy_path(self):
        db = MagicMock()
        graphiti = MagicMock()
        mgr = _make_manager(db=db, graphiti=graphiti)

        mgr._process_knowledge_graph_background(
            "doc-1", "full text", "test.pdf", "cardiology", "Test Title"
        )

        graphiti.add_document_episode_sync.assert_called_once_with(
            document_id="doc-1",
            content="full text",
            metadata={
                "filename": "test.pdf",
                "category": "cardiology",
                "title": "Test Title",
            },
            source_description="medical_document",
        )
        # Should update graphiti_synced
        db.execute.assert_called_once()
        assert "graphiti_synced = 1" in db.execute.call_args[0][0]

    def test_graphiti_client_none(self):
        mgr = RAGDocumentManager()
        # _get_graphiti_client returns None
        with patch.object(mgr, "_get_graphiti_client", return_value=None):
            # Should return without error
            mgr._process_knowledge_graph_background(
                "doc-1", "text", "file.pdf", None, None
            )

    def test_graphiti_error_handled(self):
        db = MagicMock()
        graphiti = MagicMock()
        graphiti.add_document_episode_sync.side_effect = RuntimeError("Neo4j down")
        mgr = _make_manager(db=db, graphiti=graphiti)

        # Should not raise
        mgr._process_knowledge_graph_background(
            "doc-1", "text", "file.pdf", None, None
        )

        # graphiti_synced should NOT be updated
        db.execute.assert_not_called()


# ---------------------------------------------------------------------------
# sync_from_remote tests
# ---------------------------------------------------------------------------

class TestSyncFromRemote:
    def test_sync_new_documents(self):
        db = MagicMock()
        vector = MagicMock()
        vector.get_remote_document_summaries.return_value = [
            {"document_id": "remote-1", "filename": "remote.pdf", "chunk_count": 5},
            {"document_id": "remote-2", "filename": "remote2.pdf", "chunk_count": 3,
             "category": "neuro", "tags": ["brain"]},
        ]
        db.fetchone.return_value = None  # Not existing locally

        mgr = _make_manager(db=db, vector=vector)
        count = mgr.sync_from_remote()

        assert count == 2
        assert db.execute.call_count == 2

    def test_sync_skips_existing(self):
        db = MagicMock()
        vector = MagicMock()
        vector.get_remote_document_summaries.return_value = [
            {"document_id": "existing-1", "filename": "exists.pdf", "chunk_count": 5},
        ]
        db.fetchone.return_value = ("existing-1",)  # Already exists

        mgr = _make_manager(db=db, vector=vector)
        count = mgr.sync_from_remote()

        assert count == 0
        # Only fetchone called, no execute for insert
        db.execute.assert_not_called()

    def test_sync_empty_remote(self):
        db = MagicMock()
        vector = MagicMock()
        vector.get_remote_document_summaries.return_value = []

        mgr = _make_manager(db=db, vector=vector)
        count = mgr.sync_from_remote()
        assert count == 0

    def test_sync_none_remote(self):
        db = MagicMock()
        vector = MagicMock()
        vector.get_remote_document_summaries.return_value = None

        mgr = _make_manager(db=db, vector=vector)
        count = mgr.sync_from_remote()
        assert count == 0

    def test_sync_remote_fetch_error(self):
        vector = MagicMock()
        vector.get_remote_document_summaries.side_effect = RuntimeError("Connection failed")

        mgr = _make_manager(vector=vector)
        count = mgr.sync_from_remote()
        assert count == 0

    def test_sync_individual_insert_error(self):
        db = MagicMock()
        vector = MagicMock()
        vector.get_remote_document_summaries.return_value = [
            {"document_id": "r1", "filename": "a.pdf", "chunk_count": 1},
            {"document_id": "r2", "filename": "b.pdf", "chunk_count": 2},
        ]
        db.fetchone.return_value = None  # Not existing

        # First insert succeeds, second fails
        db.execute.side_effect = [None, RuntimeError("insert failed")]

        mgr = _make_manager(db=db, vector=vector)
        count = mgr.sync_from_remote()

        # Only the first should count
        assert count == 1

    def test_sync_metadata_json_includes_synced_flag(self):
        db = MagicMock()
        vector = MagicMock()
        vector.get_remote_document_summaries.return_value = [
            {"document_id": "r1", "filename": "a.pdf", "chunk_count": 1,
             "category": "test_cat", "tags": ["t1"]},
        ]
        db.fetchone.return_value = None

        mgr = _make_manager(db=db, vector=vector)
        mgr.sync_from_remote()

        insert_params = db.execute.call_args[0][1]
        metadata_json = insert_params[11]  # metadata_json position
        parsed = json.loads(metadata_json)
        assert parsed["synced_from_remote"] is True
        assert parsed["category"] == "test_cat"
        assert parsed["custom_tags"] == ["t1"]
