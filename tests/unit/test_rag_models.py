"""
Tests for src/rag/models.py

Covers DocumentType enum, UploadStatus enum, and all Pydantic model defaults
and logic: DocumentMetadata, DocumentChunk, RAGDocument, EmbeddingRequest,
EmbeddingResponse, VectorSearchQuery, HybridSearchResult,
QueryExpansion.get_all_search_terms(), RAGQueryRequest, TemporalInfo,
RAGSettings.  No network, no Tkinter, no file I/O.
"""

import sys
import pytest
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from rag.models import (
    DocumentType,
    UploadStatus,
    DocumentMetadata,
    DocumentChunk,
    RAGDocument,
    EmbeddingRequest,
    EmbeddingResponse,
    VectorSearchQuery,
    VectorSearchResult,
    GraphSearchResult,
    HybridSearchResult,
    QueryExpansion,
    RAGQueryRequest,
    TemporalInfo,
    RAGQueryResponse,
    DocumentUploadRequest,
    DocumentUploadProgress,
    DocumentListItem,
    RAGSettings,
)


# ===========================================================================
# DocumentType enum
# ===========================================================================

class TestDocumentType:
    def test_pdf_value(self):
        assert DocumentType.PDF.value == "pdf"

    def test_docx_value(self):
        assert DocumentType.DOCX.value == "docx"

    def test_txt_value(self):
        assert DocumentType.TXT.value == "txt"

    def test_image_value(self):
        assert DocumentType.IMAGE.value == "image"

    def test_total_members(self):
        assert len(list(DocumentType)) == 4

    def test_is_str_enum(self):
        # DocumentType inherits from str, so it compares equal to its value
        assert DocumentType.PDF == "pdf"


# ===========================================================================
# UploadStatus enum
# ===========================================================================

class TestUploadStatus:
    def test_pending_value(self):
        assert UploadStatus.PENDING.value == "pending"

    def test_extracting_value(self):
        assert UploadStatus.EXTRACTING.value == "extracting"

    def test_chunking_value(self):
        assert UploadStatus.CHUNKING.value == "chunking"

    def test_embedding_value(self):
        assert UploadStatus.EMBEDDING.value == "embedding"

    def test_syncing_value(self):
        assert UploadStatus.SYNCING.value == "syncing"

    def test_completed_value(self):
        assert UploadStatus.COMPLETED.value == "completed"

    def test_failed_value(self):
        assert UploadStatus.FAILED.value == "failed"

    def test_synced_value(self):
        assert UploadStatus.SYNCED.value == "synced"

    def test_total_members(self):
        assert len(list(UploadStatus)) == 8

    def test_is_str_enum(self):
        assert UploadStatus.PENDING == "pending"


# ===========================================================================
# DocumentMetadata
# ===========================================================================

class TestDocumentMetadata:
    def test_title_defaults_none(self):
        m = DocumentMetadata()
        assert m.title is None

    def test_author_defaults_none(self):
        m = DocumentMetadata()
        assert m.author is None

    def test_subject_defaults_none(self):
        m = DocumentMetadata()
        assert m.subject is None

    def test_keywords_defaults_empty_list(self):
        m = DocumentMetadata()
        assert m.keywords == []

    def test_language_defaults_en(self):
        m = DocumentMetadata()
        assert m.language == "en"

    def test_category_defaults_none(self):
        m = DocumentMetadata()
        assert m.category is None

    def test_custom_tags_defaults_empty_list(self):
        m = DocumentMetadata()
        assert m.custom_tags == []

    def test_instances_dont_share_keywords(self):
        m1 = DocumentMetadata()
        m2 = DocumentMetadata()
        m1.keywords.append("test")
        assert m2.keywords == []

    def test_custom_values_accepted(self):
        m = DocumentMetadata(title="Test Title", author="Dr. Smith", language="fr")
        assert m.title == "Test Title"
        assert m.author == "Dr. Smith"
        assert m.language == "fr"


# ===========================================================================
# DocumentChunk
# ===========================================================================

class TestDocumentChunk:
    def test_required_fields(self):
        chunk = DocumentChunk(chunk_index=0, chunk_text="Hello", token_count=1)
        assert chunk.chunk_index == 0
        assert chunk.chunk_text == "Hello"
        assert chunk.token_count == 1

    def test_start_page_defaults_none(self):
        chunk = DocumentChunk(chunk_index=0, chunk_text="text", token_count=5)
        assert chunk.start_page is None

    def test_end_page_defaults_none(self):
        chunk = DocumentChunk(chunk_index=0, chunk_text="text", token_count=5)
        assert chunk.end_page is None

    def test_neon_id_defaults_none(self):
        chunk = DocumentChunk(chunk_index=0, chunk_text="text", token_count=5)
        assert chunk.neon_id is None

    def test_embedding_defaults_none(self):
        chunk = DocumentChunk(chunk_index=0, chunk_text="text", token_count=5)
        assert chunk.embedding is None

    def test_custom_values(self):
        chunk = DocumentChunk(
            chunk_index=3,
            chunk_text="content here",
            token_count=50,
            start_page=1,
            end_page=2,
            neon_id="abc123",
        )
        assert chunk.chunk_index == 3
        assert chunk.start_page == 1
        assert chunk.neon_id == "abc123"


# ===========================================================================
# RAGDocument
# ===========================================================================

class TestRAGDocument:
    def test_document_id_auto_generated(self):
        doc = RAGDocument(filename="test.pdf", file_type=DocumentType.PDF)
        assert doc.document_id is not None
        assert len(doc.document_id) > 0

    def test_two_documents_have_different_ids(self):
        d1 = RAGDocument(filename="a.pdf", file_type=DocumentType.PDF)
        d2 = RAGDocument(filename="b.pdf", file_type=DocumentType.PDF)
        assert d1.document_id != d2.document_id

    def test_filename_required(self):
        doc = RAGDocument(filename="test.pdf", file_type=DocumentType.PDF)
        assert doc.filename == "test.pdf"

    def test_file_type_required(self):
        doc = RAGDocument(filename="test.pdf", file_type=DocumentType.PDF)
        # use_enum_values → stored as string "pdf"
        assert doc.file_type == "pdf"

    def test_file_size_defaults_zero(self):
        doc = RAGDocument(filename="test.pdf", file_type=DocumentType.PDF)
        assert doc.file_size_bytes == 0

    def test_page_count_defaults_zero(self):
        doc = RAGDocument(filename="test.pdf", file_type=DocumentType.PDF)
        assert doc.page_count == 0

    def test_upload_status_defaults_pending(self):
        doc = RAGDocument(filename="test.pdf", file_type=DocumentType.PDF)
        assert doc.upload_status == UploadStatus.PENDING.value

    def test_chunk_count_defaults_zero(self):
        doc = RAGDocument(filename="test.pdf", file_type=DocumentType.PDF)
        assert doc.chunk_count == 0

    def test_neon_synced_defaults_false(self):
        doc = RAGDocument(filename="test.pdf", file_type=DocumentType.PDF)
        assert doc.neon_synced is False

    def test_graphiti_synced_defaults_false(self):
        doc = RAGDocument(filename="test.pdf", file_type=DocumentType.PDF)
        assert doc.graphiti_synced is False

    def test_error_message_defaults_none(self):
        doc = RAGDocument(filename="test.pdf", file_type=DocumentType.PDF)
        assert doc.error_message is None

    def test_metadata_defaults_document_metadata(self):
        doc = RAGDocument(filename="test.pdf", file_type=DocumentType.PDF)
        assert isinstance(doc.metadata, DocumentMetadata)

    def test_chunks_defaults_empty_list(self):
        doc = RAGDocument(filename="test.pdf", file_type=DocumentType.PDF)
        assert doc.chunks == []

    def test_created_at_is_datetime(self):
        doc = RAGDocument(filename="test.pdf", file_type=DocumentType.PDF)
        assert isinstance(doc.created_at, datetime)

    def test_ocr_required_defaults_false(self):
        doc = RAGDocument(filename="test.pdf", file_type=DocumentType.PDF)
        assert doc.ocr_required is False


# ===========================================================================
# EmbeddingRequest
# ===========================================================================

class TestEmbeddingRequest:
    def test_texts_required(self):
        req = EmbeddingRequest(texts=["hello", "world"])
        assert req.texts == ["hello", "world"]

    def test_model_default(self):
        req = EmbeddingRequest(texts=["hello"])
        assert req.model == "text-embedding-3-small"

    def test_custom_model(self):
        req = EmbeddingRequest(texts=["hello"], model="text-embedding-3-large")
        assert req.model == "text-embedding-3-large"


# ===========================================================================
# VectorSearchQuery
# ===========================================================================

class TestVectorSearchQuery:
    def test_query_text_required(self):
        q = VectorSearchQuery(query_text="diabetes")
        assert q.query_text == "diabetes"

    def test_top_k_defaults_10(self):
        q = VectorSearchQuery(query_text="test")
        assert q.top_k == 10

    def test_similarity_threshold_defaults_0_7(self):
        q = VectorSearchQuery(query_text="test")
        assert q.similarity_threshold == pytest.approx(0.7)

    def test_query_embedding_defaults_none(self):
        q = VectorSearchQuery(query_text="test")
        assert q.query_embedding is None

    def test_filter_document_ids_defaults_none(self):
        q = VectorSearchQuery(query_text="test")
        assert q.filter_document_ids is None

    def test_filter_metadata_defaults_none(self):
        q = VectorSearchQuery(query_text="test")
        assert q.filter_metadata is None


# ===========================================================================
# VectorSearchResult
# ===========================================================================

class TestVectorSearchResult:
    def test_required_fields(self):
        r = VectorSearchResult(
            document_id="doc1",
            chunk_index=0,
            chunk_text="some text",
            similarity_score=0.85,
        )
        assert r.document_id == "doc1"
        assert r.similarity_score == pytest.approx(0.85)

    def test_metadata_defaults_none(self):
        r = VectorSearchResult(
            document_id="doc1", chunk_index=0, chunk_text="text", similarity_score=0.5
        )
        assert r.metadata is None


# ===========================================================================
# GraphSearchResult
# ===========================================================================

class TestGraphSearchResult:
    def test_required_fields(self):
        r = GraphSearchResult(entity_name="aspirin", entity_type="medication", fact="reduces pain")
        assert r.entity_name == "aspirin"
        assert r.entity_type == "medication"
        assert r.fact == "reduces pain"

    def test_relevance_score_defaults_zero(self):
        r = GraphSearchResult(entity_name="aspirin", entity_type="medication", fact="reduces pain")
        assert r.relevance_score == pytest.approx(0.0)

    def test_source_document_id_defaults_none(self):
        r = GraphSearchResult(entity_name="aspirin", entity_type="medication", fact="reduces pain")
        assert r.source_document_id is None


# ===========================================================================
# HybridSearchResult
# ===========================================================================

class TestHybridSearchResult:
    def _make(self, **kwargs):
        defaults = dict(
            chunk_text="result text",
            document_id="doc1",
            document_filename="doc.pdf",
            chunk_index=0,
        )
        defaults.update(kwargs)
        return HybridSearchResult(**defaults)

    def test_vector_score_defaults_zero(self):
        assert self._make().vector_score == pytest.approx(0.0)

    def test_graph_score_defaults_zero(self):
        assert self._make().graph_score == pytest.approx(0.0)

    def test_bm25_score_defaults_zero(self):
        assert self._make().bm25_score == pytest.approx(0.0)

    def test_combined_score_defaults_zero(self):
        assert self._make().combined_score == pytest.approx(0.0)

    def test_mmr_score_defaults_zero(self):
        assert self._make().mmr_score == pytest.approx(0.0)

    def test_feedback_boost_defaults_zero(self):
        assert self._make().feedback_boost == pytest.approx(0.0)

    def test_related_entities_defaults_empty_list(self):
        assert self._make().related_entities == []

    def test_metadata_defaults_none(self):
        assert self._make().metadata is None

    def test_embedding_defaults_none(self):
        assert self._make().embedding is None

    def test_instances_dont_share_related_entities(self):
        r1 = self._make()
        r2 = self._make()
        r1.related_entities.append("entity")
        assert r2.related_entities == []

    def test_custom_scores(self):
        r = self._make(vector_score=0.9, bm25_score=0.7)
        assert r.vector_score == pytest.approx(0.9)
        assert r.bm25_score == pytest.approx(0.7)


# ===========================================================================
# QueryExpansion.get_all_search_terms
# ===========================================================================

class TestQueryExpansionGetAllSearchTerms:
    def test_original_query_always_included(self):
        qe = QueryExpansion(original_query="diabetes")
        terms = qe.get_all_search_terms()
        assert "diabetes" in terms

    def test_expanded_terms_included(self):
        qe = QueryExpansion(original_query="dm", expanded_terms=["diabetes mellitus"])
        terms = qe.get_all_search_terms()
        assert "diabetes mellitus" in terms

    def test_abbreviation_expansions_included(self):
        qe = QueryExpansion(
            original_query="htn",
            abbreviation_expansions={"htn": ["hypertension", "high blood pressure"]},
        )
        terms = qe.get_all_search_terms()
        assert "hypertension" in terms
        assert "high blood pressure" in terms

    def test_synonym_expansions_included(self):
        qe = QueryExpansion(
            original_query="diabetes",
            synonym_expansions={"diabetes": ["DM", "diabetes mellitus"]},
        )
        terms = qe.get_all_search_terms()
        assert "DM" in terms

    def test_deduplication(self):
        # Same term in multiple sources → only appears once
        qe = QueryExpansion(
            original_query="diabetes",
            expanded_terms=["diabetes"],  # duplicate of original
        )
        terms = qe.get_all_search_terms()
        assert terms.count("diabetes") == 1

    def test_returns_list(self):
        qe = QueryExpansion(original_query="test")
        assert isinstance(qe.get_all_search_terms(), list)

    def test_empty_expansions_returns_just_original(self):
        qe = QueryExpansion(original_query="diabetes")
        terms = qe.get_all_search_terms()
        assert len(terms) == 1
        assert terms[0] == "diabetes"

    def test_expanded_query_defaults_empty_string(self):
        qe = QueryExpansion(original_query="test")
        assert qe.expanded_query == ""


# ===========================================================================
# RAGQueryRequest
# ===========================================================================

class TestRAGQueryRequest:
    def test_query_required(self):
        req = RAGQueryRequest(query="diabetes")
        assert req.query == "diabetes"

    def test_top_k_defaults_5(self):
        req = RAGQueryRequest(query="test")
        assert req.top_k == 5

    def test_use_graph_search_defaults_true(self):
        req = RAGQueryRequest(query="test")
        assert req.use_graph_search is True

    def test_similarity_threshold_defaults_0_7(self):
        req = RAGQueryRequest(query="test")
        assert req.similarity_threshold == pytest.approx(0.7)

    def test_enable_query_expansion_defaults_true(self):
        req = RAGQueryRequest(query="test")
        assert req.enable_query_expansion is True

    def test_enable_bm25_defaults_true(self):
        req = RAGQueryRequest(query="test")
        assert req.enable_bm25 is True

    def test_enable_mmr_defaults_true(self):
        req = RAGQueryRequest(query="test")
        assert req.enable_mmr is True

    def test_enable_adaptive_threshold_defaults_true(self):
        req = RAGQueryRequest(query="test")
        assert req.enable_adaptive_threshold is True

    def test_enable_feedback_boost_defaults_true(self):
        req = RAGQueryRequest(query="test")
        assert req.enable_feedback_boost is True

    def test_enable_temporal_reasoning_defaults_true(self):
        req = RAGQueryRequest(query="test")
        assert req.enable_temporal_reasoning is True

    def test_include_metadata_defaults_true(self):
        req = RAGQueryRequest(query="test")
        assert req.include_metadata is True


# ===========================================================================
# TemporalInfo
# ===========================================================================

class TestTemporalInfo:
    def test_has_temporal_reference_defaults_false(self):
        ti = TemporalInfo()
        assert ti.has_temporal_reference is False

    def test_time_frame_defaults_none(self):
        ti = TemporalInfo()
        assert ti.time_frame is None

    def test_start_date_defaults_none(self):
        ti = TemporalInfo()
        assert ti.start_date is None

    def test_end_date_defaults_none(self):
        ti = TemporalInfo()
        assert ti.end_date is None

    def test_temporal_keywords_defaults_empty(self):
        ti = TemporalInfo()
        assert ti.temporal_keywords == []

    def test_decay_applied_defaults_false(self):
        ti = TemporalInfo()
        assert ti.decay_applied is False

    def test_custom_values(self):
        ti = TemporalInfo(
            has_temporal_reference=True,
            time_frame="last month",
            decay_applied=True,
        )
        assert ti.has_temporal_reference is True
        assert ti.time_frame == "last month"
        assert ti.decay_applied is True


# ===========================================================================
# RAGSettings
# ===========================================================================

class TestRAGSettings:
    def test_neon_database_url_defaults_none(self):
        s = RAGSettings()
        assert s.neon_database_url is None

    def test_neon_pool_size_defaults_5(self):
        s = RAGSettings()
        assert s.neon_pool_size == 5

    def test_embedding_model_default(self):
        s = RAGSettings()
        assert s.embedding_model == "text-embedding-3-small"

    def test_embedding_dimensions_default(self):
        s = RAGSettings()
        assert s.embedding_dimensions == 1536

    def test_chunk_size_tokens_default(self):
        s = RAGSettings()
        assert s.chunk_size_tokens == 500

    def test_chunk_overlap_tokens_default(self):
        s = RAGSettings()
        assert s.chunk_overlap_tokens == 50

    def test_default_top_k_default(self):
        s = RAGSettings()
        assert s.default_top_k == 5

    def test_default_similarity_threshold_default(self):
        s = RAGSettings()
        assert s.default_similarity_threshold == pytest.approx(0.7)

    def test_enable_graph_search_defaults_true(self):
        s = RAGSettings()
        assert s.enable_graph_search is True

    def test_enable_adaptive_threshold_defaults_true(self):
        s = RAGSettings()
        assert s.enable_adaptive_threshold is True

    def test_vector_weight_default(self):
        s = RAGSettings()
        assert s.vector_weight == pytest.approx(0.5)

    def test_bm25_weight_default(self):
        s = RAGSettings()
        assert s.bm25_weight == pytest.approx(0.3)

    def test_graph_weight_default(self):
        s = RAGSettings()
        assert s.graph_weight == pytest.approx(0.2)

    def test_enable_mmr_defaults_true(self):
        s = RAGSettings()
        assert s.enable_mmr is True

    def test_mmr_lambda_default(self):
        s = RAGSettings()
        assert s.mmr_lambda == pytest.approx(0.7)

    def test_hnsw_m_default(self):
        s = RAGSettings()
        assert s.hnsw_m == 16

    def test_hnsw_ef_construction_default(self):
        s = RAGSettings()
        assert s.hnsw_ef_construction == 64

    def test_hnsw_ef_search_default(self):
        s = RAGSettings()
        assert s.hnsw_ef_search == 40

    def test_max_file_size_mb_default(self):
        s = RAGSettings()
        assert s.max_file_size_mb == 50

    def test_enable_ocr_defaults_true(self):
        s = RAGSettings()
        assert s.enable_ocr is True

    def test_ocr_language_default(self):
        s = RAGSettings()
        assert s.ocr_language == "eng"

    def test_supported_extensions_contains_pdf(self):
        s = RAGSettings()
        assert ".pdf" in s.supported_extensions

    def test_supported_extensions_contains_docx(self):
        s = RAGSettings()
        assert ".docx" in s.supported_extensions

    def test_supported_extensions_contains_txt(self):
        s = RAGSettings()
        assert ".txt" in s.supported_extensions

    def test_graphiti_settings_default_none(self):
        s = RAGSettings()
        assert s.graphiti_neo4j_uri is None
        assert s.graphiti_neo4j_user is None
        assert s.graphiti_neo4j_password is None


# ===========================================================================
# DocumentUploadRequest
# ===========================================================================

class TestDocumentUploadRequest:
    def test_file_paths_required(self):
        req = DocumentUploadRequest(file_paths=["/tmp/test.pdf"])
        assert req.file_paths == ["/tmp/test.pdf"]

    def test_category_defaults_none(self):
        req = DocumentUploadRequest(file_paths=[])
        assert req.category is None

    def test_custom_tags_defaults_empty(self):
        req = DocumentUploadRequest(file_paths=[])
        assert req.custom_tags == []

    def test_enable_ocr_defaults_true(self):
        req = DocumentUploadRequest(file_paths=[])
        assert req.enable_ocr is True

    def test_enable_graph_defaults_true(self):
        req = DocumentUploadRequest(file_paths=[])
        assert req.enable_graph is True


# ===========================================================================
# DocumentUploadProgress
# ===========================================================================

class TestDocumentUploadProgress:
    def test_required_fields(self):
        prog = DocumentUploadProgress(
            document_id="doc1",
            filename="test.pdf",
            status=UploadStatus.EXTRACTING,
        )
        assert prog.document_id == "doc1"
        assert prog.filename == "test.pdf"

    def test_progress_percent_defaults_zero(self):
        prog = DocumentUploadProgress(
            document_id="doc1", filename="test.pdf", status=UploadStatus.PENDING
        )
        assert prog.progress_percent == pytest.approx(0.0)

    def test_current_step_defaults_empty(self):
        prog = DocumentUploadProgress(
            document_id="doc1", filename="test.pdf", status=UploadStatus.PENDING
        )
        assert prog.current_step == ""

    def test_error_message_defaults_none(self):
        prog = DocumentUploadProgress(
            document_id="doc1", filename="test.pdf", status=UploadStatus.PENDING
        )
        assert prog.error_message is None
